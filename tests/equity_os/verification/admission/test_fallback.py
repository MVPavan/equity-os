"""VENDOR-1 Task 10: ``eqos compare fallback`` over Apar's Q2 FY26 (spec §6.8, acceptance 11).

A Screener and Tijori run of the quarter with its filing withheld refuses trigger cells; the
command then requests that period's filing through a transport replaying the retained NSE
listings, XBRL instance and results PDF. The unedited retained filing ends FILING_UNRESOLVED.
SYNTHETIC, made here in memory: the announcements listing (one row naming the retained results
PDF; no retained listing covers that span), and each other case's edit of what is served, of the
issuer config or of the run's pins. The ADMITTED case is such an edit (the instance without its
share of associates, XBRL-only); it proves the workflow can end ADMITTED, not that retained Apar
is admitted. No socket is opened.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from contextlib import nullcontext
from datetime import date
from functools import partial
from pathlib import Path
from typing import Any

import pytest
import stage1_e2e_support
import yaml
from onboarding_support import fresh_db
from retained_support import APAR_RAW_ROOT, apar_original
from stage1_e2e_support import CONFIG, RUNS, Stage

from equity_os.companies.identity.identity_seed import EvidenceInputKind, SettingKey
from equity_os.companies.onboarding.discovery import Request
from equity_os.contracts.measurement.canonical import Basis, Representation
from equity_os.contracts.verification.comparison import SourceRole
from equity_os.interface.commands.extraction import evidence_cli
from equity_os.interface.commands.verification import compare_cli
from equity_os.interface.entry.cli import main
from equity_os.sourcing.documents.first_party_documents import ANNOUNCEMENTS, nse_listing_url
from equity_os.sourcing.exchange.nse_filings import INTEGRATED_LISTING, LEGACY_LISTING, listing_url
from equity_os.storage.facts.pg_fact_store import create_native_store
from equity_os.storage.records.repository import EvidenceRepository
from equity_os.verification.admission.admission import admit_run
from equity_os.verification.comparison import run_config
from equity_os.verification.comparison.run import DatabaseIdentity, execute_run, request_for
from equity_os.verification.comparison.run_config import (
    ConfigVersions,
    extractor_pin,
    load_run_config,
)
from equity_os.verification.comparison.run_models import ResultRow, RunRequest
from equity_os.verification.comparison.run_store import RunStore

pytestmark = [pytest.mark.pg, pytest.mark.retained]

V9 = ConfigVersions(dictionary="v2", mapping_set="v9", alignment_rules="v2")
Q2 = date(2025, 9, 30)
SYMBOL, ISIN = "APARINDS", "INE372A01015"
SCREENER, TIJORI = ("screener-subscriber", "SCREENER_FINANCIALS"), ("tijori", "financials")
LEGACY_URL = listing_url(LEGACY_LISTING[0], SYMBOL, LEGACY_LISTING[1])
INTEGRATED_URL = listing_url(INTEGRATED_LISTING[0], SYMBOL, INTEGRATED_LISTING[1])
XBRL_URL = "https://nsearchives.nseindia.com/corporate/xbrl/INTEGRATED_FILING_INDAS_1560713_29102025085858_WEB.xml"
STANDALONE_URL = "https://nsearchives.nseindia.com/corporate/xbrl/INTEGRATED_FILING_INDAS_1560684_29102025083842_WEB.xml"
PDF_URL = "https://nsearchives.nseindia.com/corporate/APARINDS_29102025133102_OutcomeofBM.pdf"
# The span runs from the period end to seven days after the XBRL broadcast (29 Oct 2025).
ANNOUNCEMENTS_URL = nse_listing_url(ANNOUNCEMENTS, SYMBOL, Q2, date(2025, 11, 5))
ISSUER_CONFIG = CONFIG / "runs/aparinds-fy26-q2.yaml"
_ASSOCIATES = (
    rb"<in-capmkt:ShareOfProfitLossOfAssociatesAndJointVenturesAccountedForUsingEquityMethod "
    rb"[^>]*>[^<]*</in-capmkt:ShareOfProfitLossOfAssociatesAndJointVenturesAccountedForUsing"
    rb"EquityMethod>"
)
TRIGGERS = {"CHECK_REQUIRED", "VENDOR_UNMAPPED", "VENDORS_DISAGREE", "VENDORS_IMPRECISE"}
SETTLED = {"ADMITTED", "NOT_DISCLOSED", "NOT_APPLICABLE"}
ORIGINAL = {"CHECK_REQUIRED", "VENDOR_UNMAPPED", "VENDORS_IMPRECISE"}  # the run's trigger reasons
H1, Q = date(2025, 4, 1), date(2025, 7, 1)  # a cell is named by its concept and period start
ANNUAL_ONLY = "results.annual_disclosure"
# Representative cells of the unedited retained filing: its genuine refusals, and what settles.
RETAINED = {
    ("cfo", H1): ["REVIEW_OPEN", None],
    ("ppe", Q2): ["FILING_UNRESOLVED", "EXTRACTION_NOT_AGREE"],
    ("sales", Q): ["FILING_UNRESOLVED", "EXTRACTION_NOT_AGREE"],
    ("biological_assets", Q2): ["NOT_DISCLOSED", None],
    ("excise_duty", Q): ["NOT_APPLICABLE", ANNUAL_ONLY],
}
SYNTHETIC = {
    ("biological_assets", Q2): ["NOT_DISCLOSED", None],
    ("excise_duty", Q): ["NOT_APPLICABLE", ANNUAL_ONLY],
}
_NATURE = rb'(NatureOfReportStandaloneConsolidated contextRef="[^"]+">)Consolidated'
OUTCOMES = (
    "SELECT run_id, period_end, basis, outcome, rerun_id, cells FROM eqos.vendor_fallback_outcomes"
)
ADMISSIONS = (
    "SELECT a.id, r.key_digest FROM eqos.fact_admissions a "
    "JOIN eqos.results r ON r.id = a.result_id WHERE a.run_id = %s"
)
PACKAGES = "SELECT count(*) FROM eqos.filing_packages"
COVERAGE = "SELECT count(*) FROM eqos.decisions"
XBRL_SOURCE = "SELECT DISTINCT source_id FROM eqos.capture_refs WHERE surface = 'NSE_XBRL_INSTANCE'"
STORED = (
    "SELECT period_end, basis, outcome, cells FROM eqos.vendor_fallback_outcomes",
    "SELECT source_id, surface, request_key, blob_sha256 FROM eqos.capture_refs ORDER BY 1, 2, 3",
    PACKAGES,
    # each package's binding, period, basis and evidence hash, with its members' captures
    "SELECT p.entity_id, p.family, p.reporting_period_end, p.basis, p.framework, "
    "p.reporting_kind, p.knowledge_time, p.evidence_sha256, m.representation, m.knowledge_time, "
    "m.knowledge_time_raw, m.knowledge_time_status, c.source_id, c.surface, c.request_key, "
    "c.capture_id, c.blob_sha256 FROM eqos.filing_packages p "
    "JOIN eqos.package_members m ON m.package_id = p.id "
    "JOIN eqos.capture_refs c ON c.id = m.capture_ref_id ORDER BY 3, 4, 9, 13, 14, 15, 16",
)


def _served() -> dict[str, bytes]:
    """The retained bodies by URL, and the SYNTHETIC announcements listing."""
    listings = APAR_RAW_ROOT / "nse-listing"
    announcement = {
        "seq_id": "1",
        "symbol": SYMBOL,
        "sm_isin": ISIN,
        "desc": "Outcome of Board Meeting",
        "attchmntText": "Outcome of Board Meeting - Financial Results for the quarter",
        "attchmntFile": PDF_URL,
        "an_dt": "29-Oct-2025 13:33:43",
    }
    return {
        LEGACY_URL: next(listings.glob("financial-results-*.json")).read_bytes(),
        INTEGRATED_URL: next(listings.glob("integrated-filing-*.json")).read_bytes(),
        XBRL_URL: apar_original("FY26_Q2", "xbrl-consolidated").read_bytes(),
        ANNOUNCEMENTS_URL: json.dumps([announcement]).encode(),
        PDF_URL: apar_original("FY26_Q2", "results").read_bytes(),
    }


def _withheld(served: dict[str, bytes], tmp_path: Path) -> Path | None:
    """Serve the retained filing; the issuer config joins the results PDF."""
    del served, tmp_path
    return ISSUER_CONFIG


def _associates_omitted(served: dict[str, bytes], tmp_path: Path) -> Path | None:
    """SYNTHETIC: the instance omits the share of associates, so no filed profit before tax
    including associates is constructed; an XBRL-only package (no issuer config)."""
    del tmp_path
    served[XBRL_URL], count = re.subn(_ASSOCIATES, b"", served[XBRL_URL])
    assert count == 2
    return None


def _unlisted(served: dict[str, bytes], tmp_path: Path) -> Path | None:
    """SYNTHETIC: the integrated listing carries no Q2 FY26 row, so no filing is acquirable."""
    payload = json.loads(served[INTEGRATED_URL])
    kept = [row for row in payload["data"] if row.get("qe_Date") != "30-SEP-2025"]
    served[INTEGRATED_URL] = json.dumps({"data": kept}).encode()
    return _withheld(served, tmp_path)


def _truncated(served: dict[str, bytes], tmp_path: Path) -> Path | None:
    """SYNTHETIC: the instance is served truncated, so its extraction fails."""
    served[XBRL_URL] = served[XBRL_URL][:4096]
    return _withheld(served, tmp_path)


def _standalone(served: dict[str, bytes], tmp_path: Path) -> Path | None:
    """SYNTHETIC: the standalone row's instance is the associates-omitted consolidated one,
    restated standalone; XBRL-only."""
    _associates_omitted(served, tmp_path)
    served[STANDALONE_URL] = re.sub(_NATURE, rb"\1Standalone", served.pop(XBRL_URL))
    return None


def _pdf_missing(served: dict[str, bytes], tmp_path: Path) -> Path | None:
    """SYNTHETIC: the results PDF the issuer config wants cannot be fetched."""
    del served[PDF_URL]
    return _withheld(served, tmp_path)


def _repinned(served: dict[str, bytes], tmp_path: Path) -> Path | None:
    """SYNTHETIC: the issuer config pins another PDF than the one acquired."""
    del served
    config = yaml.safe_load(ISSUER_CONFIG.read_bytes())
    config["results_pdf"]["sha256"] = "0" * 64
    path = tmp_path / "issuer.yaml"
    path.write_text(yaml.safe_dump(config))
    return path


FULL = (LEGACY_URL, INTEGRATED_URL, XBRL_URL, ANNOUNCEMENTS_URL, PDF_URL)
STANDALONE = (*FULL[:2], STANDALONE_URL, *FULL[3:])
STAGE_FAILURES = {
    _unlisted: None,
    _truncated: "EXTRACTION_FAILED",
    _repinned: "INTAKE_REFUSED",
    _pdf_missing: "PDF_UNACQUIRED",
}


@pytest.mark.parametrize(
    ("edit", "basis", "outcome", "packages", "fetched", "dispositions", "cells"),
    [
        (
            _withheld,
            Basis.CONSOLIDATED,
            "FILING_UNRESOLVED",
            1,
            FULL,
            SETTLED | {"REVIEW_OPEN", "FILING_UNRESOLVED"},
            RETAINED,
        ),
        (_associates_omitted, Basis.CONSOLIDATED, "ADMITTED", 1, FULL, SETTLED, SYNTHETIC),
        (_unlisted, Basis.CONSOLIDATED, "FILING_UNAVAILABLE", 0, FULL[:2], ORIGINAL, {}),
        (_truncated, Basis.CONSOLIDATED, "FILING_UNRESOLVED", 1, FULL, ORIGINAL, {}),
        # Screener has no standalone capture, so absence is never established on this basis.
        (
            _standalone,
            Basis.STANDALONE,
            "STILL_REFUSED",
            1,
            STANDALONE,
            {"ADMITTED", "NOT_APPLICABLE", "VENDOR_UNMAPPED"},
            {("biological_assets", Q2): ["VENDOR_UNMAPPED", None]},
        ),
        (_repinned, Basis.CONSOLIDATED, "FILING_UNRESOLVED", 0, FULL, ORIGINAL, {}),
        (_pdf_missing, Basis.CONSOLIDATED, "FILING_UNRESOLVED", 0, FULL, ORIGINAL, {}),
    ],
    ids=[
        "retained",
        "admitted",
        "unavailable",
        "unresolved",
        "standalone",
        "pdf-pin",
        "pdf-missing",
    ],
)
def test_fallback_acquires_only_the_triggering_period(
    pg_db: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    edit: Callable[[dict[str, bytes], Path], Path | None],
    basis: Basis,
    outcome: str,
    packages: int,
    fetched: tuple[str, ...],
    dispositions: set[str],
    cells: dict[tuple[str, date], list[Any]],
) -> None:
    """One stored terminal outcome per case, with every original trigger's disposition; only
    Apar's Q2 FY26 filing is requested, and coverage is unchanged (acceptance 11). An admitted
    cell names its rerun admission; a NOT_DISCLOSED or NOT_APPLICABLE cell has no admission. A
    stage failure before the rerun leaves the original refusals, with the stage's reason."""
    served = _served()
    issuer = edit(served, tmp_path)
    with _Fallback(pg_db, tmp_path, monkeypatch, basis) as run:
        code = run.main(served, issuer)
        ((stored_run, period, stored_basis, stored, rerun, stored_cells),) = run.read(OUTCOMES)
        assert run.read(COVERAGE) == [run.coverage]
        assert run.read(PACKAGES) == [(packages,)]
        sources = {source for (source,) in run.read(XBRL_SOURCE)}
        admissions = dict(run.read(ADMISSIONS, rerun))
    lines = capsys.readouterr().out.splitlines()
    assert [line.split("\t")[2] for line in lines if line.startswith("fetch\t")] == list(fetched)
    assert lines[-1] == f"fallback\t{run.entity_id}\t{Q2}\t{basis.value}\t{outcome}"
    assert code == (0 if outcome == "ADMITTED" else 4)
    assert (stored_run, period, stored_basis, stored) == (run.run_id, Q2, basis.value, outcome)
    assert stored_cells.keys() == run.triggers.keys()
    assert {disposition for disposition, _ in stored_cells.values()} == dispositions
    named = {(row.key.canonical_id, _start(row)): row.row_id for row in run.rows.values()}
    assert {cell: stored_cells[named[cell]] for cell in cells} == cells
    assert (rerun is None) is (edit in STAGE_FAILURES)
    if rerun is None:  # the original refusals stand, each with the stage's failure
        failure = STAGE_FAILURES[edit]
        assert stored_cells == {i: [r, failure] for i, r in run.triggers.items()}
    for row_id, (disposition, detail) in stored_cells.items():
        digest = run.rows[row_id].key.digest()
        assert (disposition == "ADMITTED") is (digest in admissions.values())
        if disposition == "ADMITTED":
            assert admissions[detail] == digest
    if fetched[2:]:
        assert sources == {f"nse-indas-xbrl-{basis.value.lower()}"}


def test_fallback_keeps_the_run_extractor(
    pg_db: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A run under a non-default XBRL extractor is ingested and rerun under that extractor (the
    rerun admits values only extracted under it); a vendor extractor that drifted since the run
    is refused before anything is fetched (§6.8 step 3)."""
    pin = extractor_pin(Representation.XBRL, version="xbrl-fallback-test")
    served = _served()
    issuer = _associates_omitted(served, tmp_path)
    with _Fallback(pg_db, tmp_path, monkeypatch, Basis.CONSOLIDATED, xbrl=pin) as run:
        with monkeypatch.context() as drift:
            current, sources = run_config.VENDOR_EXTRACTORS["tijori"]
            drift.setitem(run_config.VENDOR_EXTRACTORS, "tijori", (f"{current}-drift", sources))
            assert run.main(served, issuer) == 5
            assert not run.read(OUTCOMES)
        assert "fetch\t" not in capsys.readouterr().out
        assert run.main(served, issuer) == 0
        ((rerun,),) = run.read("SELECT rerun_id FROM eqos.vendor_fallback_outcomes")
        assert RunStore(run.pool).read_manifest(rerun).pinned.extractor_xbrl == pin
        assert run.read(ADMISSIONS, rerun)


def test_fallback_replays_its_generation_on_a_fresh_database(
    pg_db: Any, pg_template: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FIVE-1 Task 2: the fallback's fetches are kept as an entity generation under
    ``--raw-root``; ``--generation`` replays it on a fresh database with no transport (one
    serving nothing) and stores the same outcome, captures and packages (each package's binding,
    period, basis, evidence hash and member captures), writing nothing new."""
    served = _served()
    issuer = _associates_omitted(served, tmp_path)
    stored = []
    for index, (db, extra) in enumerate([(pg_db, ()), (None, ("--generation", "1"))]):
        work = tmp_path / str(index)
        work.mkdir()
        with fresh_db(pg_template) if db is None else nullcontext(db) as database:
            with _Fallback(database, work, monkeypatch, Basis.CONSOLIDATED) as run:
                raw = ("--raw-root", str(tmp_path / "0" / "raw"))
                assert run.main(served if db is not None else {}, issuer, *raw, *extra) == 0
                stored.append([run.read(query) for query in STORED])
        assert sorted(path.name for path in (tmp_path / "0" / "raw").iterdir()) == ["gen-1"]
    assert stored[0][3] and stored[0] == stored[1]


def test_fallback_refuses_a_run_triggering_two_groups(
    pg_db: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A stored run whose scope holds two quarters (``compare run`` makes one) triggers two
    company-periods; the fallback refuses before any fetch, storing no outcome and writing no
    generation (each group would request the same listings)."""
    june = date(2025, 6, 30)
    with _Fallback(pg_db, tmp_path, monkeypatch, Basis.CONSOLIDATED) as run:
        for vendor, label in run.stage.run["vendor_inputs"].items():
            run.stage.vendor(vendor, label.split()[0], end=june)
        manifest = RunStore(run.pool).read_manifest(run.run_id)
        scope = manifest.scope.model_copy(update={"period_ends": (june, Q2)})
        fields = manifest.model_dump(include=set(RunRequest.model_fields))
        cutoff = run.stage.repository.store_clock()
        request = RunRequest.model_validate({**fields, "scope": scope, "cutoff": cutoff})
        run.run_id = execute_run(request, pool=run.pool, config_root=CONFIG).run_id
        assert run.main(_served(), None) == 5
        assert not run.read(OUTCOMES)
    out, err = capsys.readouterr()
    assert "fetch\t" not in out
    assert "triggers 2 company-periods" in err
    assert not list((tmp_path / "raw").iterdir())


@pytest.mark.parametrize(
    ("edit", "printed", "packages"),
    [
        (_associates_omitted, "package", 1),
        (_unlisted, "FILING_UNAVAILABLE", 0),
        (_truncated, "FILING_UNRESOLVED", 1),
        (_repinned, "FILING_UNRESOLVED", 0),
    ],
    ids=["ingested", "unavailable", "extraction-failed", "intake-refused"],
)
def test_evidence_acquire_ingests_one_named_period(
    pg_db: Any,
    pg_template: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    edit: Callable[[dict[str, bytes], Path], Path | None],
    printed: str,
    packages: int,
) -> None:
    """FIVE-1 Task 3: ``evidence acquire`` fetches and ingests the named period's filing as the
    fallback does, writing no run, admission or outcome. It prints the stored package id, or
    why none, and exits INCOMPLETE without one. An ingested generation replays on a fresh
    database with no transport into equal captures and package and member metadata; the new
    package's knowledge time is the acquisition's, so an ``AS_KNOWN`` run at the earlier cutoff
    does not select it."""
    served = _served()
    issuer = edit(served, tmp_path)
    counts = "SELECT (SELECT count(*) FROM eqos.runs), (SELECT count(*) FROM eqos.fact_admissions)"
    with _Fallback(pg_db, tmp_path, monkeypatch, Basis.CONSOLIDATED) as run:
        before = run.read(counts)
        capsys.readouterr()
        code = run.acquire(served, issuer)
        (line,) = capsys.readouterr().out.splitlines()
        stored = [run.read(query) for query in STORED]
        assert run.read(counts) == before
        assert not run.read(OUTCOMES)
        if printed == "package":  # the triggering run re-executed at its own cutoff
            manifest = RunStore(run.pool).read_manifest(run.run_id)
            request = RunRequest.model_validate(
                manifest.model_dump(include=set(RunRequest.model_fields))
            )
            again = execute_run(request, pool=run.pool, config_root=CONFIG).run_id
            assert _first_party(run.pool, again) == _first_party(run.pool, run.run_id)
    assert line.split("\t")[:2] == [str(Q2), printed]
    assert code == (0 if printed == "package" else 4)
    assert stored[2] == [(packages,)] and bool(stored[3]) == bool(packages)
    if printed != "package":
        return
    work = tmp_path / "replay"
    work.mkdir()
    with (
        fresh_db(pg_template) as database,
        _Fallback(database, work, monkeypatch, Basis.CONSOLIDATED) as run,
    ):
        raw = ("--raw-root", str(tmp_path / "raw"), "--generation", "1")
        capsys.readouterr()
        assert run.acquire({}, issuer, *raw) == 0
        assert capsys.readouterr().out.splitlines() == [line]
        assert [run.read(query) for query in STORED] == stored


def test_evidence_acquire_refuses_before_any_request(
    pg_db: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An unknown entity, and a period before the SYNTHETIC ZZWINDOW's onboarding settings
    window (its fiscal-year-end month is valid from 2025-04-01), refuse with no request sent
    and no generation written."""
    sent: list[Request] = []
    for name, value in pg_db.cli_env().items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(evidence_cli, "live_transport", lambda: sent.append)
    with pg_db.runtime_pool() as pool:
        repository = EvidenceRepository(pool)
        evidence = repository.put_evidence_input(EvidenceInputKind.DISCOVERY, "ZZWINDOW", "e" * 64)
        with pool.connection() as conn:
            (entity_id,) = conn.execute(
                "INSERT INTO eqos.reporting_entities (entity_key, market, display_name, "
                "evidence_input_id) VALUES ('ZZWINDOW', 'IN', 'ZZWINDOW', %s) RETURNING id",
                (evidence,),
            ).fetchone()
        repository.put_settings_record(
            entity_id, SettingKey.FISCAL_YEAR_END_MONTH, "3", evidence, date(2025, 4, 1)
        )
    raw = tmp_path / "raw"
    raw.mkdir()
    for entity, period in (("ZZUNKNOWN", "2025-06-30"), ("ZZWINDOW", "2025-03-31")):
        argv = [
            *("evidence", "acquire", "--entity", entity, "--basis", "consolidated"),
            *("--period-end", period, "--mapping-set", V9.mapping_set),
            *("--dictionary", V9.dictionary, "--config-root", str(CONFIG)),
            *("--snapshot-root", str(tmp_path / "snapshots"), "--raw-root", str(raw)),
        ]
        assert main(argv) == 2
    err = capsys.readouterr().err
    assert "'ZZUNKNOWN' is not seeded" in err
    assert "no fiscal-year-end month governs 2025-03-31" in err
    assert not sent
    assert not list(raw.iterdir())


class _Fallback:
    """A Screener and Tijori run of Q2 FY26 on ``basis`` with its filing withheld, then the
    command over a transport of the case's bodies."""

    def __init__(
        self,
        pg_db: Any,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        basis: Basis,
        xbrl: Any = None,
    ) -> None:
        self.pg_db, self.tmp_path, self.monkeypatch = pg_db, tmp_path, monkeypatch
        self.basis, self.xbrl = basis, xbrl

    def __enter__(self) -> _Fallback:
        """Set up the run, its triggers and the coverage it must leave unchanged."""
        self.monkeypatch.setattr(time, "sleep", lambda _: None)
        for name, value in self.pg_db.cli_env().items():
            self.monkeypatch.setenv(name, value)
        self._pool = self.pg_db.runtime_pool()
        self.pool = self._pool.__enter__()
        stage = Stage(self.pg_db, self.pool, self.tmp_path, RUNS["APARINDS-Q2FY26"])
        stage.config, stage.versions = load_run_config(CONFIG, V9), V9
        self.entity_id, self.stage = stage.entity_id, stage
        self.run_id = _vendor_run(stage, self.basis, self.monkeypatch, self.xbrl)
        self.store_id = create_native_store(self.pool, "fallback")
        self.rows = {row.row_id: row for row in RunStore(self.pool).read_results(self.run_id)}
        ((self.coverage),) = self.read(COVERAGE)
        for root in ("snapshots", "raw"):
            (self.tmp_path / root).mkdir(mode=0o700)
        return self

    def __exit__(self, *exc: object) -> None:
        """Close the pool."""
        self._pool.__exit__(*exc)

    def main(self, served: dict[str, bytes], issuer: Path | None, *extra: str) -> int:
        """``eqos compare fallback`` over a transport of ``served``, with any ``extra`` flags;
        the run's triggers as admission reads them."""
        self.monkeypatch.setattr(compare_cli, "live_transport", lambda: _transport(served))
        self.triggers = {
            row_id: refusal.value
            for row_id, refusal in admit_run(
                self.run_id, pool=self.pool, store_id=self.store_id, config_root=CONFIG
            ).refusals
            if refusal.value in TRIGGERS
        }
        argv = [
            *("compare", "fallback", "--run", str(self.run_id), "--store-id", self.store_id),
            *("--snapshot-root", str(self.tmp_path / "snapshots")),
            *("--raw-root", str(self.tmp_path / "raw")),
            *(("--issuer-config", str(issuer)) if issuer else ()),
            *extra,
        ]
        return main(argv)

    def acquire(self, served: dict[str, bytes], issuer: Path | None, *extra: str) -> int:
        """``eqos evidence acquire`` of Q2 FY26 over a transport of ``served``."""
        self.monkeypatch.setattr(evidence_cli, "live_transport", lambda: _transport(served))
        symbol = self.stage.repository.issuer_identifiers(self.entity_id).nse_symbol
        argv = [
            *("evidence", "acquire", "--entity", symbol, "--basis", "consolidated"),
            *("--period-end", str(Q2), "--mapping-set", V9.mapping_set),
            *("--dictionary", V9.dictionary, "--config-root", str(CONFIG)),
            *("--snapshot-root", str(self.tmp_path / "snapshots")),
            *("--raw-root", str(self.tmp_path / "raw")),
            *(("--issuer-config", str(issuer)) if issuer else ()),
            *extra,
        ]
        return main(argv)

    def read(self, query: str, *params: Any) -> list[Any]:
        """One query's rows."""
        with self.pool.connection() as conn:
            return conn.execute(query, params).fetchall()


def _first_party(pool: Any, run_id: int) -> list[Any]:
    """Each row's first-party sides of a run, by row."""
    return [
        [v for v in row.source_values if v.source_role is SourceRole.FIRST_PARTY]
        for row in RunStore(pool).read_results(run_id)
    ]


def _start(row: ResultRow) -> date:
    """A cell's period start, or its instant."""
    return row.key.period.start or row.key.period.instant or Q2


def _transport(served: dict[str, bytes]) -> Callable[[Request], tuple[int, bytes]]:
    """Serve the case's bodies by URL; anything else is a 404."""

    def send(request: Request) -> tuple[int, bytes]:
        body = served.get(request.url)
        return (200, body) if body is not None else (404, b"")

    return send


def _vendor_run(stage: Stage, basis: Basis, monkeypatch: pytest.MonkeyPatch, xbrl: Any) -> int:
    """A Screener and Tijori run of Q2 FY26 on ``basis`` with no filing ingested, after the Ind AS
    setting onboarding records; ``xbrl``, if given, is its XBRL extractor pin."""
    discovery = stage.repository.put_evidence_input(EvidenceInputKind.DISCOVERY, SYMBOL, "d" * 64)
    stage.repository.put_settings_record(
        stage.entity_id, SettingKey.REPORTING_FRAMEWORK, "IND_AS", discovery
    )
    if basis is Basis.CONSOLIDATED:
        stage.vendors()
        vendors = (SCREENER, TIJORI)
    else:  # Tijori's page carries both bases' tables; read its standalone ones
        adapter = stage1_e2e_support.tijori
        monkeypatch.setattr(
            stage1_e2e_support, "tijori", lambda *args: partial(adapter(*args), basis=basis)
        )
        stage.vendor("/".join(TIJORI), "A-TIJ", basis=basis)
        vendors = (TIJORI,)
    settings = stage.pg_db.settings
    pins = None if xbrl is None else {Representation.XBRL: xbrl}
    request = request_for(
        stage.entity_id,
        Q2,
        basis,
        cutoff=stage.repository.store_clock(),
        config_root=CONFIG,
        code_version="test-commit",
        database_identity=DatabaseIdentity(
            host=settings.host, port=settings.port, name=stage.pg_db.dbname
        ),
        vendors=vendors,
        versions=V9,
        extractor_pins=pins,
    )
    return execute_run(request, pool=stage.pool, config_root=CONFIG, extractor_pins=pins).run_id
