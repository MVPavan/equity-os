"""Permanent existing-API refusal for vendor declarations on an unjoined v1 run."""

import pytest
from evidence_support import dictionary, ingest, mapping_set, policy
from run_support import Runner, runner

from fundamentals.compare.run_models import VendorSurfaceRequest

__all__ = ["dictionary", "ingest", "mapping_set", "policy", "runner"]
pytestmark = pytest.mark.pg


def test_vendor_declared_v1_request_refuses_without_joined_handoffs(runner: Runner) -> None:
    """An explicit vendor source never silently goes through the first-party v1 resolver."""
    request = runner.request()
    request = request.model_copy(
        update={
            "scope": request.scope.model_copy(
                update={
                    "vendor_sources": (
                        VendorSurfaceRequest(
                            source_id="screener-subscriber", surface="SCREENER_FINANCIALS"
                        ),
                    )
                }
            )
        }
    )
    tables = ("capture_refs", "occurrences", "interpretations", "acquisition_attempts", "runs")

    def counts() -> tuple[int, ...]:
        with runner.pool.connection() as connection:
            return tuple(
                connection.execute("SELECT count(*) FROM eqos." + table).fetchone()[0]
                for table in tables
            )

    before = counts()
    with pytest.raises(ValueError, match="(?i)(vendor|publication|joined|handoff)"):
        runner.execute(request)
    assert counts() == before


def _fact_and_run_counts(runner: Runner) -> dict[str, int]:
    """Snapshot generation and per-run facts; pre-registered fixture evidence may exist."""
    tables = (
        "capture_refs",
        "occurrences",
        "interpretations",
        "acquisition_attempts",
        "runs",
        "run_versions",
        "run_inputs",
        "results",
        "result_source_values",
        "result_surfaced_restatements",
        "pair_outcomes",
        "pair_adjustments",
        "queue_items",
        "queue_item_inputs",
        "queue_run_items",
    )
    with runner.pool.connection() as connection:
        return {
            table: int(connection.execute("SELECT count(*) FROM eqos." + table).fetchone()[0])
            for table in tables
        }


@pytest.mark.parametrize(
    "surface", ("income-statement", "balance-sheet", "cash-flow", "key-ratios")
)
def test_upstox_without_surface_authority_refuses_before_any_fact_or_run_write(
    runner: Runner, surface: str
) -> None:
    """The real release's diagnostic ledger never authorizes an Upstox public run."""
    from fundamentals.compare.run_config import ConfigVersions

    request = runner.request(versions=ConfigVersions(dictionary="v2", mapping_set="v2"))
    request = request.model_copy(
        update={
            "scope": request.scope.model_copy(
                update={
                    "vendor_sources": (VendorSurfaceRequest(source_id="upstox", surface=surface),)
                }
            )
        }
    )
    before = _fact_and_run_counts(runner)
    with pytest.raises(ValueError, match="(?i)(vendor|authority|publication|joined|handoff)"):
        runner.execute(request)
    assert _fact_and_run_counts(runner) == before


def test_complete_vendor_declaration_without_first_party_handoff_refuses_before_writes(
    runner: Runner,
) -> None:
    """Completing a declaration cannot authorize a latest-evidence or v1 fallback."""
    from datetime import date

    from fundamentals.compare.run_config import ConfigVersions
    from fundamentals.compare.vendor_request import OfflineComposerContext
    from fundamentals.contracts.canonical import Basis, Representation, StatementFamily
    from fundamentals.contracts.measurement_key import PeriodInterval
    from fundamentals.contracts.observation import AccountingFramework

    request = runner.request(versions=ConfigVersions(dictionary="v2", mapping_set="v2"))
    declaration = VendorSurfaceRequest(
        source_id="screener-subscriber",
        surface="SCREENER_FINANCIALS",
        representation=Representation.HTML,
        schema_identity="screener-financials-html-v1",
        entity_id=runner.ingest.entity_id,
        period=PeriodInterval.duration(date(2025, 7, 1), date(2025, 9, 30)),
        basis=Basis.CONSOLIDATED,
        framework=AccountingFramework.IND_AS,
        statement_family=StatementFamily.PL,
        composer_context=OfflineComposerContext(),
        expected_logical_scope_sha256="0" * 64,
    )
    request = request.model_copy(
        update={"scope": request.scope.model_copy(update={"vendor_sources": (declaration,)})}
    )
    before = _fact_and_run_counts(runner)
    with pytest.raises(ValueError, match="(?i)(first.party|vendor|joined|handoff)"):
        runner.execute(request)
    assert _fact_and_run_counts(runner) == before


@pytest.fixture
def vendor_case(pg_db, tmp_path):
    """Explicitly synthetic source/publication mechanisms in an isolated test DB."""
    from vendor_runs_support import build_case

    with pg_db.runtime_pool() as pool:
        yield build_case(pg_db, pool, tmp_path)


def _vendor_revenue(case, run_id):
    from vendor_runs_support import PL_REVENUE

    from fundamentals.compare.run import load_results
    from fundamentals.contracts.comparison import SourceRole

    (row,) = [
        row
        for row in load_results(run_id, pool=case.pool)
        if row.key.canonical_id == PL_REVENUE
        and row.key.period == case.producer_case[3].period
        and row.value_identity.value == "REPORTED"
    ]
    (value,) = [
        value for value in row.source_values if value.source_role is SourceRole.INDEPENDENT_VENDOR
    ]
    return row, value


def test_synthetic_public_vendor_run_has_source_qualified_value_pair_and_sealed_overlay(
    vendor_case,
):
    """Independent synthetic source literals agree without inventing equivalence."""
    from decimal import Decimal

    from fundamentals.compare.queue import read_queue_overlay
    from fundamentals.contracts.comparison import PairKind, PairOutcome, SourceState

    record = vendor_case.execute()
    row, value = _vendor_revenue(vendor_case, record.run_id)
    assert value.state is SourceState.VALUE
    assert value.value == Decimal("12000000000")  # independent source fixture: 1,200 crore
    assert value.lower == Decimal("11995000000")
    assert value.upper == Decimal("12005000000")
    assert (value.source_id, value.surface, value.representation.value) == (
        "screener-subscriber",
        "SCREENER_FINANCIALS",
        "HTML",
    )
    assert value.interpretation_id in {
        item.interpretation_id for item in vendor_case.generation.interpretations
    }
    (pair,) = [pair for pair in row.pairs if pair.pair_kind is PairKind.CORROBORATION]
    assert pair.right.source_id == value.source_id
    assert pair.right.surface == value.surface
    assert pair.outcome is PairOutcome.AGREE_UNQUALIFIED
    overlay = record.queue_overlay
    assert overlay is not None and overlay.memberships and overlay.open_items
    assert {member.run_id for member in overlay.memberships} == {record.run_id}
    assert (
        read_queue_overlay(
            vendor_case.pool,
            run_id=record.run_id,
            as_of=overlay.as_of,
            recorded_position=overlay.recorded_position,
        )
        == overlay
    )


def test_synthetic_public_replay_uses_only_manifest_ids_after_later_failure(
    vendor_case, monkeypatch
):
    from run_support import SpyReader, forbid_current_reads
    from test_compare_vendor_inputs import arguments

    from fundamentals.compare.run import load_results
    from fundamentals.compare.vendor_inputs import (
        append_vendor_generation,
        compose_vendor_generation,
    )

    record = vendor_case.execute()
    expected = load_results(record.run_id, pool=vendor_case.pool)
    old = vendor_case.producer_case
    missing = old[3].model_copy(update={"retained": None, "capture_ref_id": None})
    missing_case = (*old[:3], missing, *old[4:])
    failure = compose_vendor_generation(**arguments(missing_case))
    failure_scope = append_vendor_generation(failure, **arguments(missing_case))
    assert failure_scope.logical_scope_sha256 == old[3].expected_logical_scope_sha256
    forbid_current_reads(monkeypatch)
    spy = SpyReader(vendor_case.repository)
    assert vendor_case.replay(record.run_id, reader=spy) == expected
    assert {
        "get_settings_records",
        "get_evidence_inputs",
        "get_attempts",
        "get_interpretations",
    } <= set(spy.calls)


def test_same_logical_capture_free_failure_suppresses_stale_public_vendor_value(vendor_case):
    from test_compare_vendor_inputs import arguments

    from fundamentals.compare.run import RunStatus, load_results
    from fundamentals.compare.vendor_inputs import (
        append_vendor_generation,
        compose_vendor_generation,
    )
    from fundamentals.contracts.comparison import SourceState

    before = vendor_case.execute()
    assert _vendor_revenue(vendor_case, before.run_id)[1].state is SourceState.VALUE
    old = vendor_case.producer_case
    missing = old[3].model_copy(update={"retained": None, "capture_ref_id": None})
    failure_case = (*old[:3], missing, *old[4:])
    failure = compose_vendor_generation(**arguments(failure_case))
    scope = append_vendor_generation(failure, **arguments(failure_case))
    assert scope.request_sha256 != vendor_case.generation.request.identity_sha256()
    assert scope.logical_scope_sha256 == old[3].expected_logical_scope_sha256
    record = vendor_case.execute()
    _, value = _vendor_revenue(vendor_case, record.run_id)
    assert record.run_id != before.run_id
    assert record.manifest.status is RunStatus.INCOMPLETE
    assert value.state is SourceState.UNAVAILABLE and value.value is None
    assert value.attempt_id in scope.attempt_ids
    assert value.interpretation_id is None
    assert any(
        item.ref_id == value.attempt_id and item.disposition.value == "FAILED_ATTEMPT"
        for item in record.manifest.inputs
    )
    assert vendor_case.replay(record.run_id) == load_results(record.run_id, pool=vendor_case.pool)


def test_different_full_duration_failure_does_not_suppress_quarter_vendor_value(vendor_case):
    from datetime import date

    from test_compare_vendor_inputs import arguments

    from fundamentals.compare.vendor_inputs import (
        append_vendor_generation,
        compose_vendor_generation,
    )
    from fundamentals.compare.vendor_request import logical_scope_sha256, request_from_declaration
    from fundamentals.contracts.comparison import SourceState
    from fundamentals.contracts.measurement_key import PeriodInterval

    old = vendor_case.producer_case
    changed = old[3].model_copy(
        update={
            "retained": None,
            "capture_ref_id": None,
            "period": PeriodInterval.duration(date(2024, 10, 1), date(2025, 9, 30)),
        }
    )
    pin = next(pin for pin in old[2].pinned.vendor_extractors if pin.surface == changed.surface)
    changed = changed.model_copy(
        update={
            "expected_logical_scope_sha256": logical_scope_sha256(
                request_from_declaration(changed), extractor_pin=pin, composer_context=old[4]
            )
        }
    )
    other = (*old[:3], changed, *old[4:])
    scope = append_vendor_generation(
        compose_vendor_generation(**arguments(other)), **arguments(other)
    )
    assert scope.logical_scope_sha256 != old[3].expected_logical_scope_sha256
    record = vendor_case.execute()
    assert _vendor_revenue(vendor_case, record.run_id)[1].state is SourceState.VALUE
    assert not set(scope.attempt_ids) & {
        item.ref_id for item in record.manifest.inputs if item.kind.value == "ATTEMPT"
    }


@pytest.mark.parametrize("change", ("row", "context", "anchor"))
def test_forged_generation_context_or_missing_anchor_refuses_before_writes(vendor_case, change):
    generation = vendor_case.generation
    options = {}
    if change == "row":
        first, *others = generation.occurrences
        generation = generation.model_copy(
            update={"occurrences": (first.model_copy(update={"raw_value_text": "991"}), *others)}
        )
        options["vendor_generations"] = (generation,)
    elif change == "context":
        options["first_party_generation"] = vendor_case.first_party.model_copy(
            update={"fiscal_year_end_month": 12}
        )
    else:
        options["vendor_input_anchor"] = None
    before = vendor_case.counts()
    with pytest.raises(ValueError):
        vendor_case.execute(**options)
    assert vendor_case.counts() == before


def test_last_forged_claim_refuses_before_appending_first_valid_claim(vendor_case):
    from test_compare_vendor_inputs import arguments

    from fundamentals.compare.vendor_inputs import compose_vendor_generation
    from fundamentals.compare.vendor_request import logical_scope_sha256, request_from_declaration
    from fundamentals.contracts.canonical import StatementFamily
    from fundamentals.contracts.measurement_key import PeriodInterval
    from fundamentals.ingest.screener_financials_models import Section

    old = vendor_case.producer_case
    context = old[4].model_copy(update={"section": Section.BALANCE_SHEET})
    other = old[3].model_copy(
        update={
            "statement_family": StatementFamily.BALANCE_SHEET,
            "period": PeriodInterval.at(vendor_case.first_party.reporting_period_end),
            "retained": None,
            "capture_ref_id": None,
            "composer_context": context,
        }
    )
    pin = next(pin for pin in old[2].pinned.vendor_extractors if pin.surface == other.surface)
    other = other.model_copy(
        update={
            "expected_logical_scope_sha256": logical_scope_sha256(
                request_from_declaration(other), extractor_pin=pin, composer_context=context
            )
        }
    )
    other_case = (*old[:3], other, context, old[5])
    claim = compose_vendor_generation(**arguments(other_case))
    first, *rest = claim.attempts
    claim = claim.model_copy(
        update={"attempts": (first.model_copy(update={"reason": "forged"}), *rest)}
    )
    request = vendor_case.request()
    request = request.model_copy(
        update={"scope": request.scope.model_copy(update={"vendor_sources": (old[3], other)})}
    )
    before = vendor_case.counts()
    with pytest.raises(ValueError, match="(?i)(claim|attempt|composer)"):
        vendor_case.execute(request, vendor_generations=(vendor_case.generation, claim))
    assert vendor_case.counts() == before


def test_public_stage_queue_fault_rolls_back_run_tables_and_retry_publishes(vendor_case):
    from fundamentals.compare.run_store import STAGE_QUEUE

    run_tables = (
        "runs",
        "run_versions",
        "run_inputs",
        "results",
        "result_source_values",
        "result_surfaced_restatements",
        "pair_outcomes",
        "pair_adjustments",
        "queue_items",
        "queue_item_inputs",
        "queue_run_items",
        "queue_overlay_snapshots",
    )
    request = vendor_case.request()
    before = vendor_case.counts()

    def fail(stage):
        if stage == STAGE_QUEUE:
            raise RuntimeError("synthetic queue publication fault")

    with pytest.raises(RuntimeError, match="queue publication fault"):
        vendor_case.execute(request, publish_hook=fail)
    after = vendor_case.counts()
    assert {name: after[name] for name in run_tables} == {name: before[name] for name in run_tables}
    record = vendor_case.execute(request)
    assert record.created and record.queue_overlay is not None
    assert vendor_case.counts()["runs"] == before["runs"] + 1


def test_concurrent_identical_public_vendor_runs_have_exact_queue_links(vendor_case):
    import threading

    request = vendor_case.request()
    barrier = threading.Barrier(2)
    records, failures = [], []

    def execute():
        try:
            barrier.wait()
            records.append(vendor_case.execute(request))
        except BaseException as error:  # noqa: BLE001 - surfaced by final assertion
            failures.append(error)

    threads = [threading.Thread(target=execute) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert all(not thread.is_alive() for thread in threads)
    assert failures == []
    assert len({record.run_id for record in records}) == 1
    assert sorted(record.created for record in records) == [False, True]
    overlays = [record.queue_overlay for record in records]
    assert all(overlay is not None for overlay in overlays)
    assert {member.item_id for member in overlays[0].memberships} == {
        member.item_id for member in overlays[1].memberships
    }


def test_public_retrospective_append_uses_registered_synthetic_capture(pg_db, tmp_path):
    from vendor_runs_support import build_case

    from fundamentals.contracts.comparison import SourceState
    from fundamentals.contracts.evidence import RunMode

    with pg_db.runtime_pool() as pool:
        case = build_case(pg_db, pool, tmp_path, persist_vendor=False)
        before = case.counts()
        record = case.execute(case.request(mode=RunMode.RETROSPECTIVE))
        assert _vendor_revenue(case, record.run_id)[1].state is SourceState.VALUE
        assert case.counts()["interpretations"] > before["interpretations"]
        assert record.queue_overlay is not None


def test_basis_row_for_exact_identity_with_wrong_value_refuses_before_writes(vendor_case):
    """An evidence FK cannot replace the source identity artifact's actual basis value."""
    handoff = vendor_case.first_party
    with vendor_case.pg_db.migrator_connection() as connection:
        connection.execute(
            "INSERT INTO eqos.entity_basis_status (entity_id, basis_status, evidence_input_id) "
            "VALUES (%s, 'STANDALONE_ONLY', %s)",
            (handoff.entity_id, handoff.fiscal_year_end_setting_evidence_input_id),
        )
    before = vendor_case.counts()
    with pytest.raises(ValueError, match="(?i)basis context"):
        vendor_case.execute()
    assert vendor_case.counts() == before


@pytest.mark.parametrize("change", ("end", "basis", "framework", "missing", "duplicate", "extra"))
def test_public_closed_scope_and_claim_set_refusals_leave_overlay_and_facts_unchanged(
    vendor_case, change
):
    from datetime import date

    from fundamentals.contracts.canonical import Basis
    from fundamentals.contracts.observation import AccountingFramework

    request = vendor_case.request()
    options = {}
    if change == "end":
        request = request.model_copy(
            update={
                "scope": request.scope.model_copy(update={"period_ends": (date(2025, 12, 31),)})
            }
        )
    elif change == "basis":
        request = request.model_copy(
            update={"scope": request.scope.model_copy(update={"bases": (Basis.STANDALONE,)})}
        )
    elif change == "framework":
        other = vendor_case.producer_case[3].model_copy(
            update={"framework": AccountingFramework.IFRS}
        )
        request = request.model_copy(
            update={"scope": request.scope.model_copy(update={"vendor_sources": (other,)})}
        )
    elif change == "missing":
        options["vendor_generations"] = ()
    elif change == "duplicate":
        options["vendor_generations"] = (vendor_case.generation, vendor_case.generation)
    else:
        other = vendor_case.producer_case[3].model_copy(update={"surface": "SCREENER_SCHEDULE"})
        request = request.model_copy(
            update={
                "scope": request.scope.model_copy(
                    update={"vendor_sources": (vendor_case.producer_case[3], other)}
                )
            }
        )
    before = vendor_case.counts()
    with pytest.raises(ValueError):
        vendor_case.execute(request, **options)
    assert vendor_case.counts() == before
