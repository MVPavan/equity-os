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

from equity_os.contracts.measurement.canonical import Basis
from equity_os.contracts.measurement.evidence import Interpretation, Occurrence, RunMode
from equity_os.contracts.measurement.measurement_key import (
    DimensionSet,
    MeasurementKey,
    PeriodInterval,
)
from equity_os.contracts.measurement.observation import AccountingFramework
from equity_os.contracts.sourcing.source_catalog import SCREENER_PAGE, TIJORI_PAGE
from equity_os.contracts.verification.comparison import SourceState
from equity_os.contracts.verification.vendor_first import FilingFailure, FilingState, VendorOutcome
from equity_os.normalisation.mapping.interpret import _key_period
from equity_os.normalisation.mapping.mapping import CONTEXT_BASIS, CONTEXT_SCHEMA_IDENTITY
from equity_os.storage.records.repository import EvidenceRepository
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
from equity_os.verification.comparison.run_family import RUN_FAMILIES
from equity_os.verification.comparison.run_models import ResultRow, RunRequest
from equity_os.verification.comparison.selection import period_end

_Page = tuple[str | None, str]
_FullKey = tuple[int, str, PeriodInterval, Basis, AccountingFramework, DimensionSet]
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
    """§6.11 #3: every full key both vendors' pinned entries map onto the columns their stored
    occurrences evidence in the run's scope, against the run's rows. Built from the store, not
    from interpretations, so a lost or invalid interpretation leaves its key expected. A
    dimensioned key with no row refuses with Task 5's reason; any other gap is missing.
    """
    inputs, request, config = replay_inputs(run_id, pool=pool, config_root=config_root)
    scope = request.scope
    (entity_id,) = scope.entity_ids
    month = fiscal_year_end(inputs.settings, entity_id, request.cutoff, max(scope.period_ends))
    pins = {(pin.source_id, pin.surface): pin.version for pin in request.pinned.vendor_extractors}
    framework = RUN_FAMILIES[scope.family].framework
    repository = EvidenceRepository(pool)
    mapped: dict[_Page, set[_FullKey]] = {page: set() for page in _PAGES}
    for capture in inputs.capture_refs:
        page = (capture.source_id, capture.surface)
        if page not in mapped or page not in pins:
            continue
        assert capture.capture_ref_id is not None
        columns: dict[tuple[object, object, PeriodInterval], Occurrence] = {}
        for item in repository.list_capture_occurrences(capture.capture_ref_id, pins[page]):
            context = item.native_context
            if item.period is not None:
                schema, basis = context.get(CONTEXT_SCHEMA_IDENTITY), context.get(CONTEXT_BASIS)
                columns.setdefault((schema, basis, item.period), item)
        for (schema, basis, period), witness in columns.items():
            for entry in config.mapping_set.entries:
                if (
                    (entry.source, entry.surface) == page
                    and entry.schema_identity == schema
                    and basis in {member.value for member in entry.basis.intersection(scope.bases)}
                    and period.kind(month) in entry.period_kinds
                    and (key_period := _key_period(witness, entry, month, {})) is not None
                    and period_end(key_period) in scope.period_ends
                ):
                    dimensions = DimensionSet.of(entry.dimension_members)
                    key = (entity_id, entry.canonical_id, key_period, Basis(basis), framework)
                    mapped[page].add((*key, dimensions))
    expected = mapped[SCREENER_PAGE] & mapped[TIJORI_PAGE]
    rows = load_results(run_id, pool=pool)
    present = {_full_key(row.key) for row in rows}
    three_way = expected & {_full_key(row.key) for row in rows if _three_way(row)}
    refused = {
        f"{canonical_id}|{period_end(period)}|{basis}|{dimensions.pairs}": _DIMENSIONED.format(
            entity_id=entity, period_end=period_end(period), rows=[canonical_id]
        )
        for entity, canonical_id, period, basis, _, dimensions in sorted(
            expected - present, key=str
        )
        if dimensions.pairs
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


def _full_key(key: MeasurementKey) -> _FullKey:
    """The spec's full key: entity, canonical id, period, basis, framework, dimensions."""
    return (key.entity_id, key.canonical_id, key.period, key.basis, key.framework, key.dimensions)


def _three_way(row: ResultRow) -> bool:
    """Whether Screener, Tijori and a first-party side all hold a value."""
    found = {
        (value.source_id, value.surface)
        for value in row.source_values
        if value.state is SourceState.VALUE
    }
    return {*_PAGES, _FIRST_PARTY} <= found
