"""The eligibility artifact, its measurement, run coverage and counterexamples (VENDOR-1 spec
§6.6, §6.11 #3).

``measure`` reads every stored run pinning a vendor-first policy, each under its own pins. Only
cells whose T1 is ``VENDORS_AGREE`` count; per check class it keeps the distinct key-periods
(``key_digest``) whose filing agrees and those whose filing differs. The artifact holds counts
and run ids, never a vendor value. A counterexample in the store overrides the artifact.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any, LiteralString

import yaml
from psycopg import Cursor
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, ConfigDict

from equity_os.contracts.measurement.evidence import (
    Interpretation,
    InterpretationOrigin,
    InterpretationStatus,
    RunMode,
)
from equity_os.contracts.measurement.measurement_key import MeasurementKey
from equity_os.contracts.sourcing.source_catalog import SCREENER_PAGE, TIJORI_PAGE
from equity_os.contracts.verification.comparison import SourceState
from equity_os.contracts.verification.vendor_first import FilingFailure, FilingState, VendorOutcome
from equity_os.verification.admission.vendor_first import (
    check_class,
    filing_admissible,
    filing_state,
    issuer_class,
    vendor_outcome,
)
from equity_os.verification.comparison.engine_context import fiscal_year_end
from equity_os.verification.comparison.engine_vendor_context import _DIMENSIONED
from equity_os.verification.comparison.resolve_models import ResolvedInputs
from equity_os.verification.comparison.run import load_results, replay_inputs
from equity_os.verification.comparison.run_config import LoadedConfig
from equity_os.verification.comparison.run_models import ResultRow, RunRequest
from equity_os.verification.comparison.selection import period_end

_Page = tuple[str | None, str]
_PAGES = (SCREENER_PAGE, TIJORI_PAGE)
_FIRST_PARTY = (None, None)  # a first-party side names no vendor source or surface
_COUNTED = (FilingState.FILING_AGREES, FilingState.FILING_DIFFERS)
_EARLY = "available_from {given} is earlier than counted run {run_id} recorded at {recorded}"
_RUNS: LiteralString = (
    "SELECT r.id, r.created_at FROM eqos.runs r JOIN eqos.run_versions v ON v.run_id = r.id "
    "WHERE v.pin = 'vendor_first_policy' ORDER BY r.id"
)
_COUNTEREXAMPLE_AT: LiteralString = (
    "SELECT min(recorded_at) AS at FROM eqos.vendor_counterexamples "
    "WHERE class_digest = %s AND recorded_at <= %s"
)
_RECORD: LiteralString = (
    "INSERT INTO eqos.vendor_counterexamples (class_digest, result_id, run_id) "
    "VALUES (%s, %s, %s) ON CONFLICT DO NOTHING"
)


class EligibilityError(ValueError):
    """A measurement the store's runs do not allow."""


class ClassEvidence(BaseModel):
    """One check class's distinct agreeing and differing key-periods, their runs, the verdict."""

    model_config = ConfigDict(frozen=True)

    class_digest: str
    agrees: int
    differs: int
    run_ids: tuple[int, ...]
    eligible: bool


class EligibilityArtifact(BaseModel):
    """The reviewed eligibility baseline: when it is known from, the code that made it."""

    model_config = ConfigDict(frozen=True)

    available_from: datetime
    code_version: str
    classes: tuple[ClassEvidence, ...]


class Coverage(BaseModel):
    """One run's expected keys: three-way, refused with a reason, or an unexplained gap."""

    model_config = ConfigDict(frozen=True)

    expected: int
    three_way: int
    refused: Mapping[str, str]
    missing: int


def load_eligibility(path: Path) -> EligibilityArtifact:
    """Load an eligibility artifact file."""
    return EligibilityArtifact.model_validate(yaml.safe_load(path.read_bytes()))


def counted_runs(pool: ConnectionPool) -> list[tuple[int, datetime]]:
    """Every stored run pinning a vendor-first policy, with its recorded time, by id."""
    with pool.connection() as conn:
        return [(row[0], row[1]) for row in conn.execute(_RUNS).fetchall()]


def measure(
    pool: ConnectionPool, available_from: datetime, *, config_root: Path, code_version: str
) -> EligibilityArtifact:
    """The eligibility artifact over every counted run; refuses an ``available_from`` earlier
    than any counted run's recorded time."""
    runs = counted_runs(pool)
    for run_id, recorded in runs:
        if available_from < recorded:
            raise EligibilityError(
                _EARLY.format(given=available_from, run_id=run_id, recorded=recorded)
            )
    found: dict[str, tuple[set[str], set[str], set[int]]] = defaultdict(
        lambda: (set(), set(), set())
    )
    minimum: dict[str, int] = {}
    for run_id, _ in runs:
        for row, digest, state, clean in _agreeing(pool, run_id, config_root):
            if state in _COUNTED:
                agrees, differs, run_ids = found[digest]
                (agrees if state is FilingState.FILING_AGREES else differs).add(row.key.digest())
                run_ids.add(run_id)
                minimum[digest] = clean
    return EligibilityArtifact(
        available_from=available_from,
        code_version=code_version,
        classes=tuple(
            ClassEvidence(
                class_digest=digest,
                agrees=len(agrees),
                differs=len(differs),
                run_ids=tuple(sorted(run_ids)),
                eligible=len(agrees) >= minimum[digest] and not differs,
            )
            for digest, (agrees, differs, run_ids) in sorted(found.items())
        ),
    )


def coverage(pool: ConnectionPool, run_id: int, *, config_root: Path) -> Coverage:
    """§6.11 #3: every full key both vendors' entries map in the run's scope, against the run's
    rows. A dimensioned key with no row refuses with Task 5's reason; any other gap is missing.
    """
    inputs, request, config = replay_inputs(run_id, pool=pool, config_root=config_root)
    scope, mapping = request.scope, config.mapping_set
    pins = request.pinned.vendor_extractors
    extractors: dict[_Page, str] = {(pin.source_id, pin.surface): pin.version for pin in pins}
    mapped: dict[_Page, dict[str, MeasurementKey]] = {page: {} for page in _PAGES}
    for item in inputs.interpretations:
        if (
            item.status is InterpretationStatus.MAPPED
            and item.origin is InterpretationOrigin.DIRECT
            and item.key is not None
            and item.mapping_entry_id is not None
            and item.mapping_set_version == mapping.version
            and item.key.basis in scope.bases
            and period_end(item.key.period) in scope.period_ends
        ):
            entry = mapping.entry(item.mapping_entry_id)
            page = (entry.source, entry.surface)
            if page in mapped and item.extractor_version == extractors.get(page):
                mapped[page][item.key.digest()] = item.key
    screener, tijori = (mapped[page] for page in _PAGES)
    expected = screener.keys() & tijori.keys()
    rows = load_results(run_id, pool=pool)
    present = {row.key.digest() for row in rows}
    three_way = expected & {row.key.digest() for row in rows if _three_way(row)}
    refused = {
        digest: _DIMENSIONED.format(
            entity_id=key.entity_id, period_end=period_end(key.period), rows=[key.canonical_id]
        )
        for digest in sorted(expected - present)
        if (key := screener[digest]).dimensions.pairs
    }
    return Coverage(
        expected=len(expected),
        three_way=len(three_way),
        refused=refused,
        missing=len(expected) - len(three_way) - len(refused),
    )


def counterexample_at(
    cursor: Cursor[dict[str, Any]], class_digest: str, cutoff: datetime
) -> datetime | None:
    """The earliest counterexample of a class recorded at or before the cutoff, if any."""
    row = cursor.execute(_COUNTEREXAMPLE_AT, (class_digest, cutoff)).fetchone()
    return None if row is None else row["at"]


def record_counterexample(
    cursor: Cursor[dict[str, Any]], class_digest: str, result_id: int, run_id: int
) -> None:
    """Record that a filing differed from agreeing vendors in a class (once per result)."""
    cursor.execute(_RECORD, (class_digest, result_id, run_id))


def eligible(
    artifact: EligibilityArtifact,
    class_digest: str,
    *,
    cutoff: datetime,
    mode: RunMode,
    cursor: Cursor[dict[str, Any]],
) -> bool:
    """Whether a class is eligible at the cutoff: known (``AS_KNOWN`` sees nothing before
    ``available_from``), eligible in the artifact, and with no counterexample by the cutoff."""
    if mode is RunMode.AS_KNOWN and cutoff < artifact.available_from:
        return False
    return (
        any(item.class_digest == class_digest and item.eligible for item in artifact.classes)
        and counterexample_at(cursor, class_digest, cutoff) is None
    )


def _agreeing(
    pool: ConnectionPool, run_id: int, config_root: Path
) -> Iterator[tuple[ResultRow, str, FilingState, int]]:
    """A run's ``VENDORS_AGREE`` cells under its own pins: each with its check class, filing
    state and the policy's clean minimum. An entity with no issuer class yields nothing."""
    inputs, request, config = replay_inputs(run_id, pool=pool, config_root=config_root)
    policy = config.vendor_first_policy
    assert policy is not None
    (entity_id,) = request.scope.entity_ids
    with pool.connection() as conn:
        issuer = issuer_class(conn, entity_id, request.cutoff)
    if issuer is None:
        return
    interpretations = {item.interpretation_id: item for item in inputs.interpretations}
    occurrences = {item.occurrence_id: item for item in inputs.occurrences}
    for row in load_results(run_id, pool=pool):
        outcome, _ = vendor_outcome(row, interpretations, config.mapping_set, policy)
        if outcome is not VendorOutcome.VENDORS_AGREE:
            continue
        digest = row_class(row, interpretations, inputs, request, config, issuer)
        decision = filing_admissible(row, interpretations, occurrences)
        state = filing_state(row, not isinstance(decision, FilingFailure))
        yield row, digest, state, policy.min_clean_key_periods


def row_class(
    row: ResultRow,
    interpretations: Mapping[int | None, Interpretation],
    inputs: ResolvedInputs,
    request: RunRequest,
    config: LoadedConfig,
    issuer: str,
) -> str:
    """A cell's check class under its own run's pins, inputs and the issuer class."""
    policy = config.vendor_first_policy
    assert policy is not None
    (entity_id,) = request.scope.entity_ids
    month = fiscal_year_end(inputs.settings, entity_id, request.cutoff, period_end(row.key.period))
    return check_class(
        row,
        interpretations,
        mapping=config.mapping_set,
        extractor_pins=request.pinned.vendor_extractors,
        dictionary_version=config.dictionary.version,
        policy_version=policy.version,
        issuer_class=issuer,
        period_kind=row.key.period.kind(month),
    )


def _three_way(row: ResultRow) -> bool:
    """Whether Screener, Tijori and a first-party side all hold a value."""
    found = {
        (value.source_id, value.surface)
        for value in row.source_values
        if value.state is SourceState.VALUE
    }
    return {*_PAGES, _FIRST_PARTY} <= found
