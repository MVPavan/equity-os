"""Turning retained evidence into precision-carrying sides of one comparison.

Three sources say something about the same quarter: the NSE XBRL value retained
in a gold file, a Screener section acquired in Phase 2, and a Tijori page sealed
in the snapshot store. This module reads all three *offline* and states each as a
:class:`SideValue` — an amount, its unit, and the half unit in the last place the
side itself declared. Nothing here compares anything, and nothing here fetches.

The precision is the point. A comparison that invents its tolerance either
manufactures agreement or reports whole-crore rounding as a vendor defect, so
every side's ``half_ulp`` comes from :func:`fundamentals.verify.crossfoot.half_ulp`
applied to that side's own declared ``decimals`` and ``scale``. A gold source
value that declares no precision refuses the whole spine rather than being
guessed at.

Which vendor rows exist, and what they may be compared against, is the registry's
business: :data:`fundamentals.verify.three_source_map.REGISTRY` is read at call
time, never bound at import, so a caller that replaces it gets the registry it
replaced rather than the one that happened to be loaded first.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Final

import structlog
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from fundamentals.contracts.acquisition_outcome import OutcomeCode
from fundamentals.contracts.snapshot import CaptureRecord
from fundamentals.ingest.screener_financials_models import (
    FinancialsMetadata,
    PeriodKind,
    RowStatus,
    Section,
    SectionTable,
    TableRow,
    Unit,
)
from fundamentals.ingest.tijori_source import TijoriSource
from fundamentals.ingest.tijori_tables import TijoriParseError
from fundamentals.reconcile.gold_file import read_gold_file
from fundamentals.store.snapshot_store import SnapshotStore
from fundamentals.verify import three_source_map
from fundamentals.verify.crossfoot import half_ulp
from fundamentals.verify.three_source_map import MappedSource, SourceLineMapping

_LOGGER = structlog.get_logger(__name__)

METADATA_FILENAME: Final = "screener_financials_meta.json"
SECTION_FILE_PREFIX: Final = "section_"
SECTION_FILE_SUFFIX: Final = ".json"

CRORE_UNIT: Final = "INR crore"
PER_SHARE_UNIT: Final = "INR per share"
DEFAULT_XBRL_SOURCE_ID: Final = "nse-indas-xbrl-consolidated"

# A Screener amount in Rs. Crore is published as a whole crore, so its last
# reported place is the unit itself; an EPS in rupees carries as many places as
# the page printed and no more.
CRORE_DECIMALS: Final = 0
SCREENER_SCALE: Final = 1

# Only the quarterly table can answer a quarterly comparison. The profit-loss
# table is annual and, for a March year end, still renders a column whose date
# equals the quarter end — reading it would compare twelve months against three
# and call the gap a vendor defect. The rule is the section, never the date.
QUARTER_BEARING_SECTIONS: frozenset[Section] = frozenset({Section.QUARTERS})

_MISSING_DIRECTORY = "no Screener acquisition at {path}"
_MISSING_METADATA = "no {filename} at {path}: the sections say nothing about who they are"
_UNREADABLE_METADATA = "{path} is not a readable FinancialsMetadata document"
_UNREADABLE_SECTION = "{path} is not a readable SectionTable document"
_UNKNOWN_SECTION_FILE = "{path} names no known section"
_SYMBOL_MISMATCH = "metadata symbol {found!r} is not the requested {requested!r}"
_BASIS_MISMATCH = "metadata basis {found!r} is not the requested {requested!r}"
_UNREADABLE_GOLD = "{path} is not a readable gold file"
_GOLD_SYMBOL_MISMATCH = "gold file symbol {found!r} is not the requested {requested!r}"
_UNKNOWN_PRECISION_MESSAGE = (
    "gold source value for {concept} declares no decimals; the spine is refused "
    "rather than compared under a guessed tolerance"
)
_CAPTURE_NOT_OK = "capture {capture_id} is {code}, not OK; it holds no values to read"
_CAPTURE_UNREADABLE = "capture {capture_id} could not be re-read from the store"
_CAPTURE_UNPARSABLE = "capture {capture_id} did not parse into observations: {error}"

_SKIPPED_ROW = "three_source_row_skipped"
_SKIPPED_ALIAS = "three_source_alias_unmapped"
_DUPLICATE_CONCEPT = "three_source_duplicate_gold_concept"


class Side(StrEnum):
    """The three sources one comparison row puts beside each other."""

    XBRL = "xbrl"
    SCREENER = "screener"
    TIJORI = "tijori"


class PrecisionRefusal(StrEnum):
    """Why a side's precision made it unusable rather than merely coarse."""

    UNKNOWN_PRECISION = "unknown_precision"


class InputError(Exception):
    """Retained evidence could not be turned into comparable sides."""


class UnreadableInputError(InputError):
    """A file or capture is absent, corrupt, or not the document it claims to be."""


class IdentityMismatchError(InputError):
    """Retained evidence names a company or basis other than the one requested."""


class PrecisionError(InputError):
    """A side declares no usable precision, so no tolerance can be derived."""

    def __init__(self, refusal: PrecisionRefusal, message: str) -> None:
        """Carry the refusal beside the message, so a caller branches on the reason."""
        super().__init__(message)
        self.refusal: PrecisionRefusal = refusal


class SideValue(BaseModel):
    """One source's figure for one line, stated with the precision it declared.

    ``origin`` traces the figure back to the exact retained bytes — a gold file
    digest, a capture id, or a section file digest — so a reported difference can
    be re-derived without the vendor.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    side: Side
    amount: Decimal
    half_ulp: Decimal = Field(gt=0)
    unit: str = Field(min_length=1)
    raw_label: str = Field(min_length=1)
    period_end: date
    origin: str = Field(min_length=1)
    mapping_id: str | None = None


class ScreenerInputs(BaseModel):
    """One Screener acquisition as it was retained, narrowed by nothing."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    metadata: FinancialsMetadata
    sections: dict[Section, SectionTable]
    file_sha256: dict[Section, str]


class GoldSpine(BaseModel):
    """The XBRL side of one quarter, keyed by concept, with its file digest."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    gold_sha256: str = Field(min_length=1)
    values: dict[str, SideValue]


def _alias_index() -> dict[str, SourceLineMapping]:
    """Index the live registry by alias, read at call time rather than at import."""
    return {
        entry.alias_qname: entry
        for entry in three_source_map.REGISTRY
        if entry.alias_qname is not None
    }


def _section_of(name: str) -> Section | None:
    """Read a registry entry's section as a Screener section, or ``None``."""
    try:
        return Section(name)
    except ValueError:
        return None


def read_screener_sections(
    root: Path, *, symbol: str, basis: str = "consolidated"
) -> ScreenerInputs:
    """Read one retained Screener acquisition, refusing evidence of another one.

    A directory name is a filing convention, not evidence: standalone figures
    read as consolidated reconcile against the wrong spine and report agreement,
    so the metadata written beside the sections must say who and what they are.
    """
    directory = root / symbol / basis
    if not directory.is_dir():
        raise UnreadableInputError(_MISSING_DIRECTORY.format(path=directory))

    metadata_path = directory / METADATA_FILENAME
    if not metadata_path.is_file():
        raise UnreadableInputError(
            _MISSING_METADATA.format(filename=METADATA_FILENAME, path=directory)
        )
    try:
        metadata = FinancialsMetadata.model_validate_json(metadata_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValidationError) as error:
        raise UnreadableInputError(_UNREADABLE_METADATA.format(path=metadata_path)) from error

    if metadata.symbol != symbol:
        raise IdentityMismatchError(
            _SYMBOL_MISMATCH.format(found=metadata.symbol, requested=symbol)
        )
    if metadata.basis.value != basis:
        raise IdentityMismatchError(
            _BASIS_MISMATCH.format(found=metadata.basis.value, requested=basis)
        )

    sections: dict[Section, SectionTable] = {}
    digests: dict[Section, str] = {}
    for path in sorted(directory.glob(f"{SECTION_FILE_PREFIX}*{SECTION_FILE_SUFFIX}")):
        name = path.name[len(SECTION_FILE_PREFIX) : -len(SECTION_FILE_SUFFIX)]
        section = _section_of(name)
        if section is None:
            raise UnreadableInputError(_UNKNOWN_SECTION_FILE.format(path=path))
        try:
            payload = path.read_bytes()
            table = SectionTable.model_validate(json.loads(payload.decode("utf-8")))
        except (OSError, UnicodeDecodeError, ValueError, ValidationError) as error:
            raise UnreadableInputError(_UNREADABLE_SECTION.format(path=path)) from error
        sections[table.section] = table
        digests[table.section] = hashlib.sha256(payload).hexdigest()

    return ScreenerInputs(metadata=metadata, sections=sections, file_sha256=digests)


def _decimal_places(raw_text: str) -> int:
    """Count the digits the page actually printed after the decimal point."""
    fragment = raw_text.strip()
    if "." not in fragment:
        return 0
    return len(fragment.rsplit(".", 1)[1])


def _screener_precision(unit: Unit, raw_text: str) -> tuple[str, int] | None:
    """The normalized unit and declared decimals of one Screener cell, if amount-like.

    Percentages, day counts and ratios are not amounts, and comparing one against
    a filed monetary fact would be a category error, so they yield no side.
    """
    if unit is Unit.RS_CRORE:
        return CRORE_UNIT, CRORE_DECIMALS
    if unit is Unit.RUPEES:
        return PER_SHARE_UNIT, _decimal_places(raw_text)
    return None


def _top_level_row(table: SectionTable, row_selector: str) -> TableRow | None:
    """The table's own row with this label.

    Every entry of ``table.rows`` is a page row; schedule sub-rows live under
    ``table.schedules``. ``schedule_parent`` on a page row is the name its own
    expander requests (Sales, Net Profit and Expenses carry one on the live
    page), so it must not be read as "this row is a sub-row".
    """
    for row in table.rows:
        if row.label == row_selector:
            return row
    return None


def _screener_side_value(
    inputs: ScreenerInputs, entry: SourceLineMapping, period_end: date
) -> SideValue | None:
    """One registry entry's figure for one quarter, or ``None`` with a logged reason."""
    if entry.row_selector is None:
        return None
    section = _section_of(entry.section)
    if section is None or section not in QUARTER_BEARING_SECTIONS:
        _LOGGER.debug(_SKIPPED_ROW, mapping_id=entry.mapping_id, reason="section_not_quarterly")
        return None
    table = inputs.sections.get(section)
    if table is None:
        return None
    row = _top_level_row(table, entry.row_selector)
    if row is None:
        return None
    if row.status is not RowStatus.MODELED:
        _LOGGER.debug(_SKIPPED_ROW, mapping_id=entry.mapping_id, reason=row.status.value)
        return None
    period = next(
        (
            candidate
            for candidate in table.periods
            if candidate.kind is PeriodKind.DATE and candidate.period_end == period_end
        ),
        None,
    )
    if period is None:
        return None
    cell = next((item for item in row.cells if item.period_index == period.index), None)
    if cell is None or cell.value is None:
        return None
    precision = _screener_precision(row.unit, cell.raw_text)
    if precision is None:
        _LOGGER.debug(_SKIPPED_ROW, mapping_id=entry.mapping_id, reason=row.unit.value)
        return None
    unit, decimals = precision
    return SideValue(
        side=Side.SCREENER,
        amount=cell.value,
        half_ulp=half_ulp(decimals, SCREENER_SCALE),
        unit=unit,
        raw_label=row.label,
        period_end=period_end,
        origin=inputs.file_sha256[section],
        mapping_id=entry.mapping_id,
    )


def screener_side_values(inputs: ScreenerInputs, *, period_end: date) -> tuple[SideValue, ...]:
    """Every declared Screener line that carries a figure for this quarter."""
    values = []
    for entry in three_source_map.REGISTRY:
        if entry.source is not MappedSource.SCREENER:
            continue
        value = _screener_side_value(inputs, entry, period_end)
        if value is not None:
            values.append(value)
    return tuple(values)


def read_tijori_capture(
    store: SnapshotStore,
    record: CaptureRecord,
    *,
    slug: str,
    expected_symbol: str,
    expected_company_id: int | None,
    period_end: date,
) -> tuple[SideValue, ...]:
    """Re-derive one retained Tijori capture's figures without touching the vendor.

    A sealed non-OK capture is refused rather than read as an empty company: a
    logged-out shell parses into no rows, which is not evidence of no rows.
    """
    if record.outcome.code is not OutcomeCode.OK:
        raise UnreadableInputError(
            _CAPTURE_NOT_OK.format(capture_id=record.capture_id, code=record.outcome.code.value)
        )
    try:
        body = store.read_body(record)
    except (OSError, ValueError) as error:
        raise UnreadableInputError(
            _CAPTURE_UNREADABLE.format(capture_id=record.capture_id)
        ) from error
    try:
        observations = TijoriSource.parse_pl_bytes(
            body,
            slug=slug,
            expected_symbol=expected_symbol,
            expected_company_id=expected_company_id,
            period_end=period_end,
            retrieved_at=record.retrieved_at,
        )
    except TijoriParseError as error:
        raise UnreadableInputError(
            _CAPTURE_UNPARSABLE.format(capture_id=record.capture_id, error=error)
        ) from error

    aliases = _alias_index()
    values = []
    for observation in observations:
        entry = aliases.get(observation.concept_qname)
        if entry is None:
            _LOGGER.debug(_SKIPPED_ALIAS, alias=observation.concept_qname)
            continue
        values.append(
            SideValue(
                side=Side.TIJORI,
                amount=observation.normalized_value,
                half_ulp=half_ulp(observation.decimals, observation.scale),
                unit=observation.normalized_unit,
                raw_label=entry.row_selector or observation.concept_qname,
                period_end=observation.period_end or period_end,
                origin=record.capture_id,
                mapping_id=entry.mapping_id,
            )
        )
    return tuple(values)


def read_gold_spine(
    path: Path,
    *,
    symbol: str,
    period_end: date,
    xbrl_source_id: str = DEFAULT_XBRL_SOURCE_ID,
) -> GoldSpine:
    """Read the XBRL side of one quarter out of a gold file.

    The spine is the filed source value, never ``GoldFact.value``: the retained
    cross-source value may have been agreed with a vendor in the room, and a
    comparison against it would be partly a comparison against itself.
    """
    try:
        payload = path.read_bytes()
        gold = read_gold_file(path)
    except (OSError, UnicodeDecodeError, ValidationError) as error:
        raise UnreadableInputError(_UNREADABLE_GOLD.format(path=path)) from error

    if gold.symbol != symbol:
        raise IdentityMismatchError(
            _GOLD_SYMBOL_MISMATCH.format(found=gold.symbol, requested=symbol)
        )

    digest = hashlib.sha256(payload).hexdigest()
    values: dict[str, SideValue] = {}
    for fact in gold.facts:
        if fact.comparison_key.period_end != period_end:
            continue
        source_value = next(
            (item for item in fact.source_values if item.source_id == xbrl_source_id), None
        )
        if source_value is None:
            continue
        if source_value.decimals is None:
            raise PrecisionError(
                PrecisionRefusal.UNKNOWN_PRECISION,
                _UNKNOWN_PRECISION_MESSAGE.format(concept=fact.concept_qname),
            )
        if fact.concept_qname in values:
            _LOGGER.warning(_DUPLICATE_CONCEPT, concept=fact.concept_qname, path=str(path))
            continue
        values[fact.concept_qname] = SideValue(
            side=Side.XBRL,
            amount=source_value.normalized_value,
            half_ulp=half_ulp(source_value.decimals, fact.comparison_key.scale),
            unit=source_value.normalized_unit,
            raw_label=fact.concept_qname,
            period_end=period_end,
            origin=digest,
            mapping_id=None,
        )
    return GoldSpine(gold_sha256=digest, values=values)
