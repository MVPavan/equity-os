"""Vendor-only runs, run status and default vendor sides through ``eqos compare run`` (VENDOR-1
spec §6.3, plan Tasks 5 and 5b).

PYTEST_DONT_REWRITE: failing assertions must not print licensed vendor data.

LAURUSLABS Q3 FY25 consolidated from its retained Screener page and Tijori capture, with no
filing package: the group's context comes from the vendor rows and identity settings. Expected
vendor values are those of ``test_compare_vendor_runs`` (crore): Screener and Tijori Sales
"1,415", Tijori Net Profit 90.61. Task 5b's tests compare them by SHA-256 of ``str(value)``.

Task 5b files the same two captures under ``LATER`` (2025-09-30): a query over the staged
occurrences' ``valid_time`` shows both captures evidence every quarter end from 2024-06-30 to
2026-06-30, so each serves Q3 FY25 as well as ``LATER``.
"""

from __future__ import annotations

import hashlib
import shutil
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml
from test_compare_vendor_runs import (
    CONFIG,
    CRORE,
    LAURUS,
    Q3_END,
    SCREENER_PAGE,
    Issuer,
    _label,
    _row,
    _states,
    _value,
)
from test_evidence_vendor import screener, tijori

from equity_os.companies.identity.identity_seed import SettingKey
from equity_os.contracts.measurement.canonical import Basis, Representation
from equity_os.contracts.measurement.evidence import AttemptStage, FilingFamily, RunMode
from equity_os.contracts.sourcing.acquisition_outcome import ExtractionOutcome
from equity_os.contracts.verification.comparison import CorroborationStatus, SourceState
from equity_os.extraction.packages.capture_intake import FirstPartySurface
from equity_os.extraction.surfaces import vendor_ingest
from equity_os.extraction.vendors.screener.screener_financials_models import Section
from equity_os.extraction.vendors.tijori import vendor_tijori
from equity_os.interface.commands.verification.compare_cli import DEFAULT_VENDORS
from equity_os.interface.entry.cli import main
from equity_os.verification.comparison.run import (
    ResultRow,
    RunExitStatus,
    RunInputKind,
    RunManifest,
    RunStatus,
    load_results,
    replay_run,
)
from equity_os.verification.comparison.run_config import ConfigVersions, load_run_config
from equity_os.verification.comparison.run_models import RunInputDisposition
from equity_os.verification.comparison.run_store import RunStore
from equity_os.verification.comparison.selection import (
    NO_ELIGIBLE_PACKAGE,
    NOT_INTERPRETED_UNDER_PINS,
)
from equity_os.verification.comparison.vendor_sides import NO_ATTEMPT

pytestmark = [pytest.mark.pg, pytest.mark.retained]

RUN = ("compare", "run", "--entity", "LAURUSLABS", "--period-end", Q3_END.isoformat())
OPTIONS = ("--basis", "consolidated", "--dictionary", "v2", "--mapping-set", "v2")
TIJORI = "tijori/financials"
SCREENER = "screener-subscriber/SCREENER_FINANCIALS"
_RESULTS = FilingFamily.FINANCIAL_RESULTS
LATER = date(2025, 9, 30)
# SHA-256 of str() of the vendors' Q3 FY25 revenue, kept out of the source (learnings 2026-11-07).
REVENUE_SHA256 = "bdd855706df3885dd73e09aa7eeb27af3b1e94950f4ac5603a729b59bc4dd560"


@pytest.fixture
def laurus(pg_db: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Issuer]:
    """LAURUSLABS seeded with an Ind AS framework setting; the CLI points at its database."""
    for name, value in pg_db.cli_env().items():
        monkeypatch.setenv(name, value)
    with pg_db.runtime_pool() as pool:
        issuer = Issuer(LAURUS, pg_db, pool, tmp_path)
        month = issuer.repository.settings_as_of(
            issuer.entity_id, SettingKey.FISCAL_YEAR_END_MONTH, issuer.repository.store_clock()
        )
        assert month is not None
        issuer.repository.put_settings_record(
            issuer.entity_id, SettingKey.REPORTING_FRAMEWORK, "IND_AS", month.evidence_input_id
        )
        yield issuer


def test_vendor_only_run_completes_with_default_vendor_sides(
    laurus: Issuer, capsys: pytest.CaptureFixture[str]
) -> None:
    """No package and no flags: both default vendor sides. A vendor never captured for the
    period is absence (``NO_ATTEMPT``), not failure, so the run is ``COMPLETE``; first-party
    sides are ``NO_VALUE``/``NO_ELIGIBLE_PACKAGE``. Once Tijori is captured its values join."""
    laurus.screener(Q3_END)
    first_id, first = _compare(laurus, capsys)
    assert first.status is RunStatus.COMPLETE and first.operational_failures == ()
    assert first.scope.vendors == DEFAULT_VENDORS
    revenue = _row(_results(laurus, first_id), "revenue_from_operations")
    assert _states(revenue) == {
        "XBRL": SourceState.NO_VALUE,
        "PDF": SourceState.NO_VALUE,
        SCREENER: SourceState.VALUE,
        TIJORI: SourceState.UNAVAILABLE,
    }
    first_party = {value.reason for value in revenue.source_values if value.source_id is None}
    assert first_party == {NO_ELIGIBLE_PACKAGE}
    assert _value(revenue, TIJORI).reason == NO_ATTEMPT

    laurus.tijori()
    second_id, second = _compare(laurus, capsys)
    assert second.status is RunStatus.COMPLETE
    rows = _results(laurus, second_id)
    revenue = _row(rows, "revenue_from_operations")
    assert {_value(revenue, label).value for label in (SCREENER, TIJORI)} == {1415 * CRORE}
    pat = _row(rows, "profit_continuing_after_tax")
    assert _value(pat, TIJORI).value == Decimal("90.61") * CRORE
    for run_id in (first_id, second_id):
        assert replay_run(run_id, pool=laurus.pool, config_root=CONFIG) == _results(laurus, run_id)


def test_failed_first_party_acquisition_still_makes_the_run_incomplete(
    laurus: Issuer, capsys: pytest.CaptureFixture[str]
) -> None:
    """A failed results-PDF acquisition for the period is a failure even with no package."""
    vendor = laurus.screener(Q3_END).attempt
    (failed,) = laurus.repository.put_attempts(
        [
            vendor.model_copy(
                update={
                    "attempt_id": None,
                    "stage": AttemptStage.ACQUISITION,
                    "surface": FirstPartySurface.NSE_RESULTS_PDF.value,
                    "representation": Representation.PDF,
                    "statement_family": None,
                    "extractor_version": "",
                    "extraction_context_sha256": None,
                    "package_id": None,
                    "capture": None,
                    "outcome": ExtractionOutcome.FAILED,
                }
            )
        ]
    )
    run_id, manifest = _compare(laurus, capsys, RunExitStatus.INCOMPLETE)
    failures = manifest.operational_failures  # derived PDF sides fail through their operands
    assert f"PDF\tFAILED\tattempt={failed.attempt_id}" in failures
    assert all(item.startswith("PDF\t") for item in failures)
    assert replay_run(run_id, pool=laurus.pool, config_root=CONFIG) == _results(laurus, run_id)


def test_missing_inputs_refuse_the_group(
    laurus: Issuer, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """No vendor capture evidences a currency; a dimensioned row a requested vendor maps has no
    package to enumerate its members. Each refuses with its reason and stores no run."""
    _refused(laurus, capsys, "evidenced reporting currencies []")
    root = tmp_path / "config-dimensioned"
    shutil.copytree(CONFIG, root)
    mappings = root / "normalisation/mappings"
    index = yaml.safe_load((mappings / "v2.yaml").read_text(encoding="utf-8"))
    (mappings / "v99.yaml").write_text(yaml.safe_dump(index | {"version": "v99"}), "utf-8")
    entries = mappings / "tijori/v1/financials.yaml"
    data = yaml.safe_load(entries.read_text(encoding="utf-8"))
    probe = data["entries"][0] | {
        "entry_id": "tijori.qt_c.segment_revenue_probe",
        "canonical_id": "segment_revenue",
        "dimension_members": {"elimination_basis": "POST_ELIMINATION"},
    }
    probe["selector"] = probe["selector"] | {"labels": ["Segment Revenue Probe"]}
    data["entries"].append(probe)
    entries.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    laurus.config = load_run_config(root, ConfigVersions(dictionary="v2", mapping_set="v99"))
    laurus.screener(Q3_END)
    laurus.tijori()
    reason = "members of dimensioned rows ['segment_revenue'] cannot be enumerated"
    _refused(laurus, capsys, reason, "--config-root", str(root), "--mapping-set", "v99")


def test_a_capture_filed_under_a_later_period_serves_an_earlier_quarter(
    laurus: Issuer, capsys: pytest.CaptureFixture[str]
) -> None:
    """Spec §6.3 (amended 2026-11-07), §6.11 #3/#5: the Screener and Tijori captures, filed
    under ``LATER``, also evidence Q3 FY25, so a Q3 run with no vendor flags compares XBRL,
    Screener and Tijori three ways instead of reporting both vendors ``NO_ATTEMPT``; a
    ``LATER`` run decides from the same captures. Each run replays equal."""
    laurus.first_party()
    page = laurus.vendor(
        (*SCREENER_PAGE, "", ""),
        screener(LAURUS.symbol, Basis.CONSOLIDATED, Section.QUARTERS),
        "screener-v1",
        LATER,
    ).attempt
    table = laurus.vendor(
        LAURUS.tijori,
        tijori(LAURUS.tijori[2], LAURUS.symbol),
        vendor_tijori.EXTRACTOR_VERSION,
        LATER,
    ).attempt
    run_id, manifest = _compare(laurus, capsys)
    assert manifest.status is RunStatus.COMPLETE and manifest.operational_failures == ()
    rows = _results(laurus, run_id)
    revenue = _row(rows, "revenue_from_operations")
    assert _states(revenue) == {
        "XBRL": SourceState.VALUE,
        "PDF": SourceState.NO_VALUE,
        SCREENER: SourceState.VALUE,
        TIJORI: SourceState.VALUE,
    }
    assert revenue.corroboration_status is CorroborationStatus.AGREES_UNQUALIFIED
    for label, attempt in ((SCREENER, page), (TIJORI, table)):
        value = _value(revenue, label)
        assert hashlib.sha256(str(value.value).encode()).hexdigest() == REVENUE_SHA256
        assert value.attempt_id == attempt.attempt_id and attempt.period_end == LATER
        assert (RunInputKind.ATTEMPT, attempt.attempt_id) in {
            (item.kind, item.ref_id) for item in manifest.inputs
        }
    later_id, later = _compare(laurus, capsys, RunExitStatus.SUCCESS, "--period-end", str(LATER))
    assert later.status is RunStatus.COMPLETE
    for decided in (rows, _results(laurus, later_id)):
        assert {
            (_label(value), value.attempt_id)
            for row in decided
            for value in row.source_values
            if value.source_id is not None and value.state is SourceState.VALUE
        } == {(SCREENER, page.attempt_id), (TIJORI, table.attempt_id)}
    for item in (run_id, later_id):
        assert replay_run(item, pool=laurus.pool, config_root=CONFIG) == _results(laurus, item)


@pytest.mark.parametrize("mode", [RunMode.AS_KNOWN, RunMode.RETROSPECTIVE])
def test_an_uninterpreted_capture_filed_elsewhere_is_unavailable_not_absent(
    laurus: Issuer,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    mode: RunMode,
) -> None:
    """A Tijori capture filed under ``LATER`` evidences Q3, but no interpretation of it is
    known to the run: ``AS_KNOWN`` cuts off at its attempt, before its interpretations are
    recorded; ``RETROSPECTIVE`` follows an ingest that crashed between the two writes. The
    loader's witness occurrence tells the engine the capture evidences Q3, so its sides are
    ``UNAVAILABLE`` / ``NOT_INTERPRETED_UNDER_PINS`` (failure), never ``NO_ATTEMPT`` (absence)."""
    laurus.first_party()
    laurus.screener(Q3_END)
    capture = (LAURUS.tijori, tijori(LAURUS.tijori[2], LAURUS.symbol))
    if mode is RunMode.AS_KNOWN:
        attempt = laurus.vendor(*capture, vendor_tijori.EXTRACTOR_VERSION, LATER).attempt
        recorded = laurus.repository.list_capture_interpretations(attempt.capture.capture_ref_id)
        assert attempt.attempted_at < min(item.recorded_at for item in recorded)
        flags = ("--cutoff", attempt.attempted_at.isoformat())
    else:

        def crash(*_: Any, **__: Any) -> Any:
            raise RuntimeError

        monkeypatch.setattr(vendor_ingest, "_interpretations", crash)
        with pytest.raises(RuntimeError):
            laurus.vendor(*capture, vendor_tijori.EXTRACTOR_VERSION, LATER)
        (attempt,) = laurus.repository.list_attempts(laurus.entity_id, LATER)
        flags = ("--mode", "retrospective")
    run_id, manifest = _compare(laurus, capsys, RunExitStatus.INCOMPLETE, *flags)
    assert manifest.operational_failures
    assert all(item.startswith(f"{TIJORI}\t") for item in manifest.operational_failures)
    rows = _results(laurus, run_id)
    tijori_sides = {
        (value.state, value.reason)
        for row in rows
        if row.key.period.end == Q3_END
        for value in row.source_values
        if _label(value) == TIJORI
    }
    assert tijori_sides == {(SourceState.UNAVAILABLE, NOT_INTERPRETED_UNDER_PINS)}
    capture_id = attempt.capture.capture_ref_id
    witness = min(
        (
            item
            for item in laurus.repository.list_capture_occurrences(capture_id)
            if item.valid_time == Q3_END
        ),
        key=lambda item: item.occurrence_id or 0,
    )
    assert any(
        (item.kind, item.ref_id, item.disposition)
        == (RunInputKind.OCCURRENCE, witness.occurrence_id, RunInputDisposition.NOT_SELECTED)
        for item in manifest.inputs
    )
    assert replay_run(run_id, pool=laurus.pool, config_root=CONFIG) == rows


def _compare(
    laurus: Issuer,
    capsys: pytest.CaptureFixture[str],
    status: RunExitStatus = RunExitStatus.SUCCESS,
    *args: str,
) -> tuple[int, RunManifest]:
    """Run ``compare run`` with no vendor flags; the printed run's id and stored manifest."""
    assert main([*RUN, *OPTIONS, *args]) == status
    (run_id,) = [
        int(line.split("\t")[1])
        for line in capsys.readouterr().out.splitlines()
        if line.startswith("run\t")
    ]
    return run_id, RunStore(laurus.pool).read_manifest(run_id)


def _results(laurus: Issuer, run_id: int) -> tuple[ResultRow, ...]:
    return load_results(run_id, pool=laurus.pool)


def _refused(laurus: Issuer, capsys: pytest.CaptureFixture[str], reason: str, *args: str) -> None:
    """``compare run`` exits ``FAILURE`` naming the reason, and no run is stored."""
    capsys.readouterr()
    assert main([*RUN, *OPTIONS, *args]) == RunExitStatus.FAILURE
    assert reason in capsys.readouterr().err
    store = RunStore(laurus.pool)
    assert store.latest_run(laurus.entity_id, Q3_END, Basis.CONSOLIDATED, _RESULTS) is None
