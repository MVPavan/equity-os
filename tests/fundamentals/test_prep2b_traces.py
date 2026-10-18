"""PREP-2b Task 4: a run's comparator figures and computed values bind to stored traces.

Each quarter's run (trusted fixture clocks: report behaviour only) is bound against the
evidence ingest of its own XBRL and its two comparators. Every retained computed value is a
stored trace over mapped interpretations and checks ``MATCH`` at the value the run emitted;
every comparator figure and the filed tax cite their interpretation. A value the run did not
derive from those interpretations refuses before anything is stored.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from evidence_support import CONFIG, XBRL_KIND, Ingest, ingest, policy
from retained_support import REPO_ROOT, apar_catalog, apar_store
from temporal_fixture_support import FIXTURE_ACQUIRED_AT, run_trusted_fixture_pipeline

from fundamentals.api.config import load_config
from fundamentals.api.pipeline import PipelineResult, XbrlInput
from fundamentals.canon.dictionary import CanonicalDictionary, load_dictionary
from fundamentals.contracts.canonical import Representation
from fundamentals.contracts.evidence import RunMode
from fundamentals.contracts.ledger import (
    CitationKind,
    ClaimState,
    NumericClaim,
)
from fundamentals.evidence.mapping import MappingSet, load_mapping_set
from fundamentals.ledger.citations import resolve_citation
from fundamentals.ledger.claim_check import check_claim
from fundamentals.ledger.run_traces import Line, RunDraftError, bind_computed
from fundamentals.output.pnl_lines import GAP_LABEL, format_crore
from fundamentals.store.fact_store import FactStore

__all__ = ["ingest", "policy"]

pytestmark = [pytest.mark.pg, pytest.mark.retained]

COMPARATOR_KIND = "xbrl-consolidated-comparator"
# Each run quarter's XBRL, then its QoQ and YoY comparators: manifest quarter, kind, period end.
QUARTERS = {
    "fy26-q4-pg": (
        ("FY26_Q4", XBRL_KIND, date(2026, 3, 31)),
        ("FY26_Q3", XBRL_KIND, date(2025, 12, 31)),
        ("FY25_Q4", COMPARATOR_KIND, date(2025, 3, 31)),
    ),
    "fy27-q1": (
        ("FY27_Q1", XBRL_KIND, date(2026, 6, 30)),
        ("FY26_Q4", XBRL_KIND, date(2026, 3, 31)),
        ("FY26_Q1", COMPARATOR_KIND, date(2025, 6, 30)),
    ),
}
# The other-income gap the retained FY26_Q4 and FY27_Q1 updates state (total income − revenue);
# the run once printed them truncated (19, 33).
GAPS = {"fy26-q4-pg": "19.72", "fy27-q1": "33.65"}
TRACES = "SELECT count(*) FROM eqos.calculation_traces"
MAPPED_VERSIONS = (
    "SELECT DISTINCT mapping_set_version FROM eqos.interpretations WHERE status = 'MAPPED' "
    "ORDER BY 1"
)


@pytest.fixture(scope="module")
def dictionary() -> CanonicalDictionary:
    """Canonical dictionary v2."""
    return load_dictionary(CONFIG / "dictionary", "v2")


@pytest.fixture(scope="module")
def mapping_set(dictionary: CanonicalDictionary) -> MappingSet:
    """Mapping set v5: the 2026 in-capmkt taxonomy of FY26_Q4 and FY27_Q1 (PREP-1)."""
    return load_mapping_set(CONFIG / "mappings", "v5", dictionary=dictionary)


def _run(quarter: str, tmp_path: Path) -> PipelineResult:
    """The quarter's pipeline run on a scratch SQLite store."""
    path = REPO_ROOT / "config" / f"aparinds-{quarter}.yaml"
    config = load_config(path)
    xml = config.xbrl_local_path(path).read_bytes()
    return run_trusted_fixture_pipeline(
        config=config,
        config_path=path,
        xbrl_input=XbrlInput(
            xml_bytes=xml,
            file_sha256=hashlib.sha256(xml).hexdigest(),
            source_id=config.xbrl.source_id,
            retrieved_at=FIXTURE_ACQUIRED_AT,
        ),
        results_pdf_path=str(config.results_pdf_path(path)),
        results_pdf_sha256=config.results_pdf.sha256,
        transcript_pdf_path=str(config.transcript_pdf_path(path)),
        transcript_pdf_sha256=config.transcript_pdf.sha256,
        store=FactStore(tmp_path / f"{quarter}.sqlite"),
    )


def _ingest(ingest: Ingest, quarter: str, members: tuple[int, ...] = (0, 1, 2)) -> None:
    """Evidence-ingest the run quarter's XBRL and its comparators (the listed ones)."""
    for index in members:
        filed, kind, period_end = QUARTERS[quarter][index]
        ingest.run(ingest.intake({Representation.XBRL: kind}, filed), period_end)


def _traces(ingest: Ingest) -> int:
    """How many calculation traces are stored."""
    with ingest.pg_db.runtime_pool() as pool, pool.connection() as conn:
        row = conn.execute(TRACES).fetchone()
    assert row is not None
    return int(row[0])


def _claims(lines: tuple[Line, ...]) -> dict[str, NumericClaim]:
    """Every bound claim by key."""
    return {claim.claim_key: claim for line in lines for claim in line.claims}


def _state(ingest: Ingest, claim: NumericClaim, entity_id: int | None = None) -> ClaimState:
    """The AS_KNOWN check of ``claim`` on a report of ``entity_id`` (default: the run's
    issuer) now, on the real resolver."""
    with ingest.pg_db.runtime_pool() as pool, pool.connection() as conn:
        resolved = resolve_citation(
            conn.cursor(),
            claim,
            entity_id=ingest.entity_id if entity_id is None else entity_id,
            overlay_position=datetime.now(UTC),
            catalog=apar_catalog(),
            snapshots=apar_store(ingest.tmp_path),
        )
    now = datetime.now(UTC)
    return check_claim(claim, resolved, mode=RunMode.AS_KNOWN, cutoff=now, imported=False)


@pytest.mark.parametrize("quarter", sorted(QUARTERS))
def test_every_computed_value_binds_and_matches(
    ingest: Ingest, tmp_path: Path, quarter: str
) -> None:
    """Every comparator figure, change, gap, tax, ETR and headline PBT checks ``MATCH``; the
    gap is emitted exactly, from its exact operands."""
    result = _run(quarter, tmp_path)
    _ingest(ingest, quarter)
    claims = _claims(bind_computed(ingest.repository, result.update, entity_id=ingest.entity_id))
    assert {key: _state(ingest, claim) for key, claim in claims.items()} == {
        key: ClaimState.MATCH for key in claims
    }
    facts = {fact.role.value: fact.value for fact in result.update.facts}
    gap = result.update.calculations[0]
    income, revenue = facts["total_income"], facts["revenue"]
    assert (gap.label, gap.result) == (GAP_LABEL, GAPS[quarter])
    assert gap.trace == f"Total income {format_crore(income)} − Revenue {format_crore(revenue)}"
    assert income - revenue == Decimal(GAPS[quarter])
    kinds = {key: claim.citation.kind for key, claim in claims.items()}
    assert {kinds[key] for key in ("calc.1", "calc.3", "calc.4")} == {CitationKind.CALCULATION}
    assert kinds["calc.2"] is CitationKind.FIGURE


def test_a_missing_comparator_or_a_changed_value_refuses_before_any_write(
    ingest: Ingest, tmp_path: Path
) -> None:
    """No YoY comparator ingested, or a gap the interpretations do not give: nothing stored."""
    result = _run("fy27-q1", tmp_path)
    _ingest(ingest, "fy27-q1", (0, 1))
    count = _traces(ingest)
    with pytest.raises(RunDraftError, match="no single mapped interpretation"):
        bind_computed(ingest.repository, result.update, entity_id=ingest.entity_id)
    _ingest(ingest, "fy27-q1", (2,))
    gap = result.update.calculations[0].model_copy(update={"result": "33.66"})
    calculations = (gap, *result.update.calculations[1:])
    changed = result.model_copy(
        update={"update": result.update.model_copy(update={"calculations": calculations})}
    )
    with pytest.raises(RunDraftError, match="calc.1"):
        bind_computed(ingest.repository, changed.update, entity_id=ingest.entity_id)
    assert _traces(ingest) == count


def test_an_interpretation_figure_resolves_only_for_its_issuer(
    ingest: Ingest, tmp_path: Path
) -> None:
    """The filed tax figure cites the issuer's interpretation: on another stock's report, under
    another stock's key, or both, it is ``UNRESOLVED`` — never a match on a foreign record."""
    result = _run("fy27-q1", tmp_path)
    _ingest(ingest, "fy27-q1")
    figure = _claims(bind_computed(ingest.repository, result.update, entity_id=ingest.entity_id))[
        "calc.2"
    ]
    assert _state(ingest, figure) is ClaimState.MATCH
    assert figure.measurement_key is not None
    other = ingest.entity_id + 1
    foreign = figure.model_copy(
        update={"measurement_key": figure.measurement_key.model_copy(update={"entity_id": other})}
    )
    for claim, report in ((figure, other), (foreign, ingest.entity_id), (foreign, other)):
        assert _state(ingest, claim, report) is ClaimState.UNRESOLVED


def test_an_older_mapping_versions_interpretations_do_not_block_the_run(
    ingest: Ingest, mapping_set: MappingSet, tmp_path: Path
) -> None:
    """The run XBRL also interpreted under mapping v4 beside v5 (append-only, same capture and
    keys): the run binds within its own pinned context, so every value still matches."""
    result = _run("fy27-q1", tmp_path)
    filed, kind, period_end = QUARTERS["fy27-q1"][0]
    older = mapping_set.model_copy(update={"version": "v4"})
    ingest.run(ingest.intake({Representation.XBRL: kind}, filed), period_end, mapping_set=older)
    _ingest(ingest, "fy27-q1")
    with ingest.pg_db.runtime_pool() as pool, pool.connection() as conn:
        versions = conn.execute(MAPPED_VERSIONS).fetchall()
    assert versions == [("v4",), ("v5",)]
    claims = _claims(bind_computed(ingest.repository, result.update, entity_id=ingest.entity_id))
    assert {_state(ingest, claim) for claim in claims.values()} == {ClaimState.MATCH}
