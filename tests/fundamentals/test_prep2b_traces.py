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
from typing import Any

import pytest
from evidence_support import CONFIG, XBRL_KIND, Ingest, ingest, policy
from retained_support import REPO_ROOT, apar_catalog, apar_store
from temporal_fixture_support import FIXTURE_ACQUIRED_AT, run_trusted_fixture_pipeline

from fundamentals.api.config import load_config
from fundamentals.api.pipeline import PipelineResult, XbrlInput
from fundamentals.canon.dictionary import CanonicalDictionary, load_dictionary
from fundamentals.contracts.canonical import Representation, TemporalRole, ValueKind
from fundamentals.contracts.comparison import SelectionSource
from fundamentals.contracts.config_versions import ConfigVersions
from fundamentals.contracts.evidence import RunMode
from fundamentals.contracts.ledger import (
    CitationKind,
    ClaimState,
    NumericClaim,
)
from fundamentals.contracts.measurement_key import PeriodInterval
from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.contracts.role import FactRole
from fundamentals.evidence.capture_intake import SURFACE_OF
from fundamentals.evidence.mapping import MappingSet, load_mapping_set
from fundamentals.ledger.citations import resolve_citation
from fundamentals.ledger.claim_check import CRORE, PERCENT, check_claim
from fundamentals.ledger.import_mapping import measurement_key
from fundamentals.ledger.run_traces import (
    MARGIN_KEY,
    MARGIN_LABEL,
    Line,
    RunDraftError,
    _shown,
    bind_computed,
)
from fundamentals.output.pnl_lines import GAP_LABEL, OPERAND_MISSING, format_crore
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
# The fixture's pins: dictionary v2, mapping set v5.
VERSIONS = ConfigVersions(dictionary="v2", mapping_set="v5")
SOURCE_OF = (
    "SELECT source_id FROM eqos.capture_refs WHERE blob_sha256 = %s AND surface = %s ORDER BY id"
)
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
    claims = _claims(
        bind_computed(
            ingest.repository, result.update, entity_id=ingest.entity_id, versions=VERSIONS
        )
    )
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
        bind_computed(
            ingest.repository, result.update, entity_id=ingest.entity_id, versions=VERSIONS
        )
    _ingest(ingest, "fy27-q1", (2,))
    gap = result.update.calculations[0].model_copy(update={"result": "33.66"})
    calculations = (gap, *result.update.calculations[1:])
    changed = result.model_copy(
        update={"update": result.update.model_copy(update={"calculations": calculations})}
    )
    with pytest.raises(RunDraftError, match="calc.1"):
        bind_computed(
            ingest.repository, changed.update, entity_id=ingest.entity_id, versions=VERSIONS
        )
    assert _traces(ingest) == count


def test_an_interpretation_figure_resolves_only_for_its_issuer(
    ingest: Ingest, tmp_path: Path
) -> None:
    """The filed tax figure cites the issuer's interpretation: on another stock's report, under
    another stock's key, or both, it is ``UNRESOLVED`` — never a match on a foreign record."""
    result = _run("fy27-q1", tmp_path)
    _ingest(ingest, "fy27-q1")
    figure = _claims(
        bind_computed(
            ingest.repository, result.update, entity_id=ingest.entity_id, versions=VERSIONS
        )
    )["calc.2"]
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
    claims = _claims(
        bind_computed(
            ingest.repository, result.update, entity_id=ingest.entity_id, versions=VERSIONS
        )
    )
    assert {_state(ingest, claim) for claim in claims.values()} == {ClaimState.MATCH}


@pytest.mark.parametrize("revenue", ["zero", "missing"])
def test_a_margin_without_revenue_is_a_claimless_line(
    ingest: Ingest, tmp_path: Path, revenue: str
) -> None:
    """A zero or missing revenue (its changes and the income gap dropped) gives the PBT margin
    no claim and no trace: the line renders ``OPERAND_MISSING`` instead of dividing."""
    update = _run("fy27-q1", tmp_path).update
    _ingest(ingest, "fy27-q1")
    (fact,) = (fact for fact in update.facts if fact.role is FactRole.REVENUE)
    others = tuple(f for f in update.facts if f is not fact)
    facts = others if revenue == "missing" else (*others, fact.model_copy(update={"value": 0}))
    changed = update.model_copy(
        update={
            "facts": facts,
            "comparatives": tuple(
                c for c in update.comparatives if c.concept_qname != fact.concept_qname
            ),
            "calculations": tuple(c for c in update.calculations if c.label != GAP_LABEL),
        }
    )
    count = _traces(ingest)
    lines = bind_computed(ingest.repository, changed, entity_id=ingest.entity_id, versions=VERSIONS)
    (margin,) = (line for line in lines if line.label == MARGIN_LABEL)
    assert margin.claims == () and _shown(margin) == f"- {MARGIN_LABEL} = {OPERAND_MISSING}"
    claims = _claims(lines)
    assert MARGIN_KEY not in claims
    traced = [c for c in claims.values() if c.citation.calculation_trace_id is not None]
    assert _traces(ingest) - count == len(traced)


# RESEARCH-3 S1 Task 2 ------------------------------------------------------------------------

DIGESTS = (
    "SELECT content_sha256 FROM eqos.calculation_traces WHERE id = ANY(%s) ORDER BY content_sha256"
)
# Every trace one fy27-q1 binding stores, by content hash, printed from the source before the
# RESEARCH-3 binder refactor (never typed): a changed hash breaks every approved version's replay.
TRACE_DIGESTS = (
    "102f943bee4e6fa79a2b9b76b79a921f04f076b41d091bc1b1ad1f0315903e43",
    "109488f9994b58a367f8d710690ca5bcff570143114975df183991068dd35a27",
    "1bb56b015eb7fbabc9fcfa056be4d43a2be3caf31bc30fbe685e65fdfa03b373",
    "38b3df2a0fd2366e29cc80f3440fd21967c77ae3c0e715fd1d5b5ee47b4b13e1",
    "43b98779e6402c5bf8416e9c9ba2ecdf82007e45718dfbe12c7358a0db39beb1",
    "43ed97ee1a27263c90a0ed3ef8d6ee50c2b05ca7ed492f4eec507138473d7c0f",
    "4c5ab957ab9d956297c8c1eac6dfd068d098b4f79a9d7ea67651746170320b7d",
    "52c13c378abe79ccc88de181c0cc7cdd122bace4ed45b1b3a351e8130b270063",
    "652048eb0020bd237f41f733d241f115cf810af05081f15c4bd587be23591413",
    "6c534ae6e831072e76586028fdac286a51804958666ceccc76f9e1f5eec1b0f4",
    "6e7585807e62a99f0620272b09758ba0a031f13b1979dfa4cbf4cc12265f9e70",
    "7168e3c0b5b4815e0fb4e26783c6d51ee85f4d11d3f32832463a1e19013eea25",
    "7cf12346bf3f7dad77622dd3b722adf74671780140c282c633168be2f2d25957",
    "8293a0141f42a4c30fd798c232596b5d8381d7c23849c5855ddbf02e9a694460",
    "898ed3d76090807c997b9c74199ecc8750567451d0f3f95ee9d14de139182b30",
    "95e14fe12ad446e7d3105d1cf70e39dc5b3b4a4dbc37d6085f59afcabfe4657b",
    "9a0323a8b23db9af25e859575e1e0c4b370293ec2f0b64385482932ee1580700",
    "a1260cebf4db4f41c112c955b864cc8974dcfc425ff61ff0150985a387a990b7",
    "a9ac4f10e8d46842c58cc817a137f8a932ca70cfc3e7d8437541d6f52521015e",
    "c59919e80e368c35ebddf015341e670cf373c44dbdfbb7035c8fe4dd0c05ade2",
    "c7d04222a76a13c680e47bb4f06b15c7383b9f7910a4948e2a9bbaedcda9219c",
    "ca150bff375bfb1deb519d0c1bf7040c0515bc1d1ef0e96a6b3c449779ec0285",
    "d12b46bc5a7fa0bfb5567088a09e0e585d027c2c74d7b78b407809ffc79b0d77",
    "d3cd7e9b24178a4921855c17891dc8bae214421b9a52bbbcdbeee95ca16a5ecd",
    "e68f102237ce136ab38b008cb021025440a833b2d686bfd50de5597d9a5f45bb",
    "f68c6d5a5e4c9562f272178cd727f4a7e2e93e50c5f8501c7a33d9f2de0bc354",
    "f85082c58dba488391a5fe036c845bd4295d5c2ef29185ea44aa3b488eba0423",
    "fbe64df4925e7ab07c34222a5c86f7c15000eb5f5b1623136578df83c0c126a8",
)
FY25_Q4 = "943873742981759927022eb5963d1ed0a4e1d2fe2aac8d9feda0fcf3c64f4cc2"
FY25 = (date(2024, 4, 1), date(2025, 3, 31))
# A leap fiscal year (366 days); no retained Apar statement has one, so the annual revenue
# operand is re-keyed to it: D must come from the operand's own interval, not the calendar.
FY24 = PeriodInterval.duration(date(2023, 4, 1), date(2024, 3, 31))


def test_trace_digests_are_unchanged(ingest: Ingest, tmp_path: Path) -> None:
    """Characterization (not a red node): the existing run traces keep their content hashes."""
    result = _run("fy27-q1", tmp_path)
    _ingest(ingest, "fy27-q1")
    lines = bind_computed(
        ingest.repository, result.update, entity_id=ingest.entity_id, versions=VERSIONS
    )
    ids = [c.citation.calculation_trace_id for c in _claims(lines).values()]
    with ingest.pg_db.runtime_pool() as pool, pool.connection() as conn:
        rows = conn.execute(DIGESTS, ([i for i in ids if i is not None],)).fetchall()
    assert tuple(row[0] for row in rows) == TRACE_DIGESTS


@pytest.mark.parametrize("formula", ["days", "outflow"])
def test_probe_formulas_store_closing_and_outflow_traces(ingest: Ingest, formula: str) -> None:
    """``run.days`` divides a closing balance by a flow and multiplies by the flow window's own
    inclusive day count (366 in a leap year), recording the balance ``CLOSING``;
    ``run.outflow_pct`` negates the inflow-positive capex line, so spending reads positive."""
    from fundamentals.ledger.run_traces import DAYS, OUTFLOW_PCT, _Binder

    ingest.run(ingest.intake({Representation.XBRL: COMPARATOR_KIND}, "FY25_Q4"), FY25[1])
    surface = SURFACE_OF[Representation.XBRL].value
    with ingest.pg_db.runtime_pool() as pool, pool.connection() as conn:
        found = conn.execute(SOURCE_OF, (FY25_Q4, surface)).fetchone()
    assert found is not None
    source = Provenance(
        source_id=found[0],
        file_sha256=FY25_Q4,
        anchor_type=SourceAnchorType.XBRL_CONTEXT,
        context_ref="FourD",
        retrieved_at=datetime.now(UTC),
    )
    binder = _Binder(ingest.repository, ingest.entity_id, *FY25, VERSIONS)

    def filed(canonical_id: str, period: PeriodInterval) -> Any:
        key = binder.key(canonical_id, CRORE).model_copy(update={"period": period})
        operand = binder.filed(source, key, SelectionSource.HISTORICAL_PACKAGE)
        assert operand is not None, canonical_id
        return operand

    revenue = filed("revenue_from_operations", PeriodInterval.duration(*FY25))
    if formula == "days":
        balance = filed("trade_receivables_current", PeriodInterval.at(FY25[1]))
        leap = revenue[1].model_copy(
            update={"key": revenue[1].key.model_copy(update={"period": FY24})}
        )
        output = measurement_key("probe.R1", ValueKind.DAYS, ingest.entity_id, *FY25)
        result = binder.evaluate("probe.R1", DAYS, output, (balance, (revenue[0], leap)))
        want = balance[1].exact / revenue[1].exact * 366
        roles = (TemporalRole.CLOSING, TemporalRole.DURATION)
    else:
        capex = filed("cf_capex_ppe", PeriodInterval.duration(*FY25))
        assert capex[1].exact < 0  # the canonical outflow is negative (spec §0)
        output = binder.key("probe.R5", PERCENT)
        result = binder.evaluate("probe.R5", OUTFLOW_PCT, output, (capex, revenue))
        want = -capex[1].exact / revenue[1].exact * 100
        roles = (TemporalRole.DURATION, TemporalRole.DURATION)
    (stored,) = ingest.repository.get_calculation_traces(
        [binder.store(output.canonical_id, result)]
    )
    assert stored.trace.exact_value == want and want > 0
    assert tuple(o.temporal_role for o in stored.trace.operands) == roles
