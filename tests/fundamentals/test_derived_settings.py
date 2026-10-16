"""D6 Task 4 (T4): derived settings, onboarding ingest, the PDF exclusion and the comparison.

Development fixtures only (APARINDS, served by ``onboarding_support``'s replay roots and fake
transport); synthetic edits are labelled. No socket is opened.
"""

from __future__ import annotations

import hashlib
import json
import shlex
import subprocess
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
from evidence_support import XBRL_ONLY, Ingest, dictionary, ingest, mapping_set, policy
from onboarding_support import (
    APAR,
    APAR_ISIN,
    APAR_SCRIP,
    INCOMPLETE,
    JUN,
    MAR,
    cli,
    edit,
    freeze,
    freeze_repo,
    fresh_db,
    rows,
    serving_transport,
    world,
    write_root,
)
from pg_support import PgTestDatabase
from pydantic import ValidationError
from retained_support import APAR_IDENTITY, REPO_ROOT

from fundamentals.api import onboard_cli
from fundamentals.api.cli import main
from fundamentals.compare import run_config
from fundamentals.compare.run import load_results, replay_run
from fundamentals.compare.run_config import (
    EXTRACTOR_SOURCES,
    EXTRACTOR_VERSIONS,
    VENDOR_EXTRACTORS,
    vendor_version_pin,
)
from fundamentals.compare.run_models import FIRST_PARTY_SOURCES, RunScope
from fundamentals.compare.run_store import RunStore
from fundamentals.contracts.canonical import Basis, Representation
from fundamentals.contracts.comparison import SourceState
from fundamentals.contracts.onboarding import VerificationState, VerificationUnit
from fundamentals.contracts.source_catalog import (
    TIJORI_SEARCH,
    UPSTOX_INSTRUMENTS,
)
from fundamentals.entity.derived_settings import derive
from fundamentals.entity.discovery import Capture, Discovery, Request, Response
from fundamentals.evidence.repository import EvidenceRepository, VersionPin
from fundamentals.pg.identity_seed import SettingKey, load_issuer_identity

__all__ = ["cli", "dictionary", "ingest", "mapping_set", "policy"]
pytestmark = pytest.mark.retained

SEED_COMMIT = "82a84db"  # the plan commit: every extractor-pinned source as of the freeze plan
MAR_END, JUN_END = date(2026, 3, 31), date(2026, 6, 30)
FAILURE = 5
PIN_FLAGS = ("--dictionary", "v2", "--mapping-set", "v5")


def _discovery(served: list[dict[str, Any]]) -> Discovery:
    """A discovery whose anchors verified, carrying the served responses as captures."""
    at = datetime(2026, 10, 16, 2, 20, 24, tzinfo=UTC)
    return Discovery(
        symbol=APAR,
        name="APAR INDUSTRIES LIMITED",
        isin=APAR_ISIN,
        scrip=APAR_SCRIP,
        entity_id=None,
        states={unit: (VerificationState.VERIFIED, None) for unit in VerificationUnit},
        captures=tuple(
            Capture(
                request=Request(
                    unit=item["unit"],
                    source_id=item["source_id"],
                    surface=item["surface"],
                    url=item["url"],
                ),
                response=Response(outcome="OK", body=item["body"], retrieved_at=at),
            )
            for item in served
        ),
    )


def test_apar_derives_the_identity_files_settings_from_its_filings() -> None:
    """Oracle: config/identity/aparinds.yaml (fiscal year end 3, consolidated and standalone)
    and the two filings' OneD facts (INR, Crores, the IndAS in-capmkt-ent entry point). Each value
    is valid from the earliest period end declaring it; the location names the latest instance."""
    oracle = load_issuer_identity(APAR_IDENTITY)
    derived = derive(_discovery(world(APAR)))
    assert derived.basis_status is oracle.basis_status
    assert [f.period_end for f in derived.filings] == [JUN_END, MAR_END]
    (jun,) = [item for item in world(APAR) if JUN in item["url"]]
    location = {"url": jun["url"], "sha256": hashlib.sha256(jun["body"]).hexdigest()}
    assert {(s.key, s.value, s.valid_from) for s in derived.settings} == {
        (SettingKey.FISCAL_YEAR_END_MONTH, str(oracle.fiscal_year_end_month), MAR_END),
        (SettingKey.PRESENTATION_CURRENCY, "INR", MAR_END),
        (SettingKey.FILING_ROUNDING_LEVEL, "Crores", MAR_END),
        (SettingKey.REPORTING_FRAMEWORK, "IND_AS", MAR_END),
        (SettingKey.DOCUMENT_LOCATION, json.dumps(location, sort_keys=True), JUN_END),
    }


@pytest.mark.pg
def test_an_altered_fiscal_year_end_adds_a_later_valid_from_row(
    cli: Callable[..., int], pg_db: PgTestDatabase, tmp_path: Path
) -> None:
    """SYNTHETIC: the Jun filing declares a December year end. Onboarding writes a second
    fiscal-year-end row valid from Jun, each citing the XBRL_ENTITY DISCOVERY input, and the
    governing rule picks 3 for the Mar period and 12 for Jun."""
    served = world(APAR)
    edit(served, JUN, b">2027-03-31<", b">2026-12-31<")
    assert cli(APAR, write_root(tmp_path / "raw", served, APAR)) == INCOMPLETE
    found = rows(
        pg_db,
        "SELECT s.value_text, s.valid_from, i.kind, i.label FROM eqos.settings_records s "
        "JOIN eqos.evidence_inputs i ON i.id = s.evidence_input_id "
        "WHERE s.setting_key = %s ORDER BY s.valid_from",
        SettingKey.FISCAL_YEAR_END_MONTH.value,
    )
    label = f"discovery:{APAR}:XBRL_ENTITY"
    assert found == [("3", MAR_END, "DISCOVERY", label), ("12", JUN_END, "DISCOVERY", label)]
    (basis,) = rows(
        pg_db,
        "SELECT b.basis_status, i.label FROM eqos.entity_basis_status b "
        "JOIN eqos.evidence_inputs i ON i.id = b.evidence_input_id",
    )
    assert basis == ("CONSOLIDATED_AND_STANDALONE", f"discovery:{APAR}:EXCHANGE")
    with pg_db.runtime_pool() as pool:
        repository = EvidenceRepository(pool)
        entity_id = repository.entity_id(APAR)
        assert entity_id is not None
        governing = {
            end: repository.settings_as_of(
                entity_id, SettingKey.FISCAL_YEAR_END_MONTH, repository.store_clock(), end
            )
            for end in (MAR_END, JUN_END)
        }
    assert {end: row.value_text for end, row in governing.items() if row} == {
        MAR_END: "3",
        JUN_END: "12",
    }


# --- onboarding, then the printed comparison --------------------------------------------------


def _onboard(db: PgTestDatabase, root: Path, snapshots: Path, capsys: Any) -> tuple[int, str]:
    """``main(["onboard", …])`` in replay on ``db``: the exit and the printed command."""
    capsys.readouterr()
    code = main(["onboard", APAR, "--raw-root", str(root), "--snapshot-root", str(snapshots)])
    (command,) = [
        line.removeprefix(onboard_cli.COMPARE_PREFIX)
        for line in capsys.readouterr().out.splitlines()
        if line.startswith(onboard_cli.COMPARE_PREFIX)
    ]
    return code, command


def _compare(command: str, capsys: Any) -> tuple[int, int | None]:
    """The printed command through ``main`` (after the program name): exit and run id."""
    capsys.readouterr()
    code = main(shlex.split(command)[1:])
    printed = dict(
        line.split("\t", 1) for line in capsys.readouterr().out.splitlines() if "\t" in line
    )
    return code, int(printed["run"]) if "run" in printed else None


def _failures(db: PgTestDatabase, run_id: int) -> tuple[str, set[str]]:
    """The run's status and its operational failures projected to representation/surface."""
    with db.runtime_pool() as pool:
        manifest = RunStore(pool).read_manifest(run_id)
    projected = {f.split("\t", 1)[0].split(":", 1)[0] for f in manifest.operational_failures}
    return manifest.status.value, projected


def _pdf_sides(db: PgTestDatabase, run_id: int) -> set[tuple[SourceState, str | None]]:
    """The run's reported (not calculated) PDF sides: state and reason."""
    with db.runtime_pool() as pool:
        results = load_results(run_id, pool=pool)
    return {
        (value.state, value.reason)
        for row in results
        for value in row.source_values
        if value.representation is Representation.PDF and value.calculation_state is None
    }


@pytest.mark.pg
def test_acquire_replay_ingest_and_the_printed_run_end_to_end(
    pg_db: PgTestDatabase,
    pg_template: PgTestDatabase,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """C1, C2: ``onboard --acquire`` (fake transport) writes the generation with its XBRL-only
    retrieval manifest; replay in a fresh database ingests the current integrated filings
    under ONBOARDING_VERSIONS with no issuer config (A7) and the printed ``compare run``,
    executed verbatim, is INCOMPLETE with failures projecting exactly to PDF
    (EXCLUDED_BY_RULE) and no Screener schedule side. Controls: without the exclusion attempt
    PDF is NO_VALUE and the run COMPLETE; Tijori also excluded adds exactly tijori/financials;
    only Upstox excluded leaves exactly PDF; the CLI's v1 defaults fail or diverge."""
    repo, _, entry = freeze_repo(tmp_path)
    descriptor = freeze(repo, entry)
    raw = tmp_path / "raw"
    monkeypatch.setattr(onboard_cli, "live_transport", lambda: serving_transport(world(APAR)))
    monkeypatch.setattr(onboard_cli, "now", lambda: datetime(2026, 10, 16, 2, 20, 24, tzinfo=UTC))
    for name, value in pg_db.cli_env().items():
        monkeypatch.setenv(name, value)
    acquire = ("--acquire", "--freeze-descriptor", str(descriptor))
    snapshots = str(tmp_path / "acq-snapshots")
    argv = ["onboard", APAR, "--raw-root", str(raw), "--snapshot-root", snapshots, *acquire]
    assert main(argv) == INCOMPLETE
    package = (raw / "gen-1" / onboard_cli.RETRIEVAL_NAME).read_bytes()
    acquisition = json.loads((raw / "gen-1" / onboard_cli.ACQUISITION_NAME).read_text())
    assert acquisition["retrieval_manifest_sha256"] == hashlib.sha256(package).hexdigest()
    entries = json.loads(package)["entries"]
    assert [(e["quarter"], e["kind"]) for e in entries] == [
        (JUN_END.isoformat(), "xbrl-consolidated"),
        (MAR_END.isoformat(), "xbrl-consolidated"),
    ]
    assert JUN in entries[0]["filename"] and MAR in entries[1]["filename"]
    monkeypatch.setattr(onboard_cli, "live_transport", lambda: pytest.fail("replay opened"))

    def replayed(tag: str, root: Path = raw, **patches: Any) -> tuple[PgTestDatabase, str, Any]:
        """Onboard by replay of ``root`` into a fresh database (``patches`` on ``onboard_cli``)."""
        context = fresh_db(pg_template)
        db = context.__enter__()
        for name, value in db.cli_env().items():
            monkeypatch.setenv(name, value)
        with monkeypatch.context() as patch:
            for name, value in patches.items():
                patch.setattr(onboard_cli, name, value)
            code, command = _onboard(db, root, tmp_path / f"snap-{tag}", capsys)
        assert code == INCOMPLETE
        return db, command, context

    db, command, context = replayed("pinned")
    try:
        assert command.split()[:3] == ["fundamentals", "compare", "run"]
        assert " ".join(PIN_FLAGS) in command
        (entity_id,) = rows(db, "SELECT id FROM eqos.reporting_entities")[0]
        assert rows(
            db,
            "SELECT reporting_period_end FROM eqos.filing_packages WHERE entity_id = %s",
            entity_id,
        ) == [(JUN_END,)]
        assert rows(
            db,
            "SELECT surface, reason, capture_ref_id, package_id FROM eqos.acquisition_attempts "
            "WHERE outcome = 'EXCLUDED_BY_RULE'",
        ) == [("NSE_RESULTS_PDF", "R-PDF", None, None)]
        code, run_id = _compare(command, capsys)
        assert code == INCOMPLETE and run_id is not None
        assert _failures(db, run_id) == ("INCOMPLETE", {"PDF"})
        assert _pdf_sides(db, run_id) == {(SourceState.UNAVAILABLE, "EXCLUDED_BY_RULE")}
        with db.runtime_pool() as pool:
            surfaces = {
                str(value.surface).split(":", 1)[0]
                for row in load_results(run_id, pool=pool)
                for value in row.source_values
            }
        assert "SCREENER_SCHEDULE" not in surfaces
        assert {"SCREENER_FINANCIALS", "financials", "income-statement"} <= surfaces
        pinned_rows = _comparable(db, run_id)
        default = [flag for flag in shlex.split(command) if flag not in PIN_FLAGS]
        code, v1_run = _compare(shlex.join(default), capsys)
        assert code == FAILURE or (v1_run is not None and _comparable(db, v1_run) != pinned_rows)
    finally:
        context.__exit__(None, None, None)

    controls: list[tuple[str, Path, dict[str, Any], tuple[str, set[str]]]] = [
        ("no-exclusion", raw, {"exclude_pdf": lambda *args: None}, ("COMPLETE", set())),
        (
            "no-tijori",
            _denied(tmp_path, TIJORI_SEARCH),
            {},
            ("INCOMPLETE", {"PDF", "tijori/financials"}),
        ),
        ("no-upstox", _denied(tmp_path, UPSTOX_INSTRUMENTS), {}, ("INCOMPLETE", {"PDF"})),
    ]
    for tag, root, patches, expected in controls:
        db, command, context = replayed(tag, root, **patches)
        try:
            _, run_id = _compare(command, capsys)
            assert run_id is not None
            assert _failures(db, run_id) == expected, tag
            if tag == "no-exclusion":
                assert {state for state, _ in _pdf_sides(db, run_id)} == {SourceState.NO_VALUE}
        finally:
            context.__exit__(None, None, None)


def _denied(tmp_path: Path, pair: tuple[str, str]) -> Path:
    """A replay root whose ``pair`` request was recorded NOT_AUTHORISED (replay serves the
    recorded denial)."""
    served = world(APAR)
    for item in served:
        if (item["source_id"], item["surface"]) == pair:
            item["outcome"] = "NOT_AUTHORISED"
    return write_root(tmp_path / f"raw-{pair[1]}", served, APAR)


def _comparable(db: PgTestDatabase, run_id: int) -> list[tuple[Any, ...]]:
    """A run's rows by key: each side's state and value."""
    with db.runtime_pool() as pool:
        results = load_results(run_id, pool=pool)
    return sorted(
        (
            row.row_id,
            tuple(
                sorted(
                    (str(v.representation), str(v.surface), v.state, v.value)
                    for v in row.source_values
                )
            ),
        )
        for row in results
    )


# --- no reinterpretation; the upgrade from the seed commit -------------------------------------


@pytest.mark.pg
def test_a_later_setting_row_reinterprets_nothing(
    cli: Callable[..., int],
    pg_db: PgTestDatabase,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Onboard Apar and run; a later setting row (a December year end from Jun) leaves every
    stored occurrence and interpretation, and the run's replay, identical."""
    capsys.readouterr()
    assert cli(APAR, write_root(tmp_path / "raw", world(APAR), APAR)) == INCOMPLETE
    (command,) = [
        line.removeprefix(onboard_cli.COMPARE_PREFIX)
        for line in capsys.readouterr().out.splitlines()
        if line.startswith(onboard_cli.COMPARE_PREFIX)
    ]
    code, run_id = _compare(command, capsys)
    assert code == INCOMPLETE and run_id is not None
    stored = (
        rows(pg_db, "SELECT * FROM eqos.occurrences ORDER BY id"),
        rows(pg_db, "SELECT * FROM eqos.interpretations ORDER BY id"),
    )
    with pg_db.runtime_pool() as pool:
        before = replay_run(run_id, pool=pool, config_root=REPO_ROOT / "config")
        repository = EvidenceRepository(pool)
        entity_id = repository.entity_id(APAR)
        assert entity_id is not None
        (input_id,) = rows(pg_db, "SELECT id FROM eqos.evidence_inputs ORDER BY id LIMIT 1")[0]
        repository.put_settings_record(
            entity_id, SettingKey.FISCAL_YEAR_END_MONTH, "12", input_id, valid_from=JUN_END
        )
        after = replay_run(run_id, pool=pool, config_root=REPO_ROOT / "config")
    assert after == before
    assert (
        rows(pg_db, "SELECT * FROM eqos.occurrences ORDER BY id"),
        rows(pg_db, "SELECT * FROM eqos.interpretations ORDER BY id"),
    ) == stored


def _seed_bytes(relative: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), "show", f"{SEED_COMMIT}:src/fundamentals/{relative}"],
        check=True,
        capture_output=True,
    ).stdout


def _seed_pins(monkeypatch: pytest.MonkeyPatch, root: Path) -> list[VersionPin]:
    """Every extractor pin computed from the seed commit's bytes of its sources."""
    for relative in {
        *(path for paths in EXTRACTOR_SOURCES.values() for path in paths),
        *(path for _, paths in VENDOR_EXTRACTORS.values() for path in paths),
    }:
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        (root / relative).write_bytes(_seed_bytes(relative))
    with monkeypatch.context() as patch:
        patch.setattr(run_config, "_SOURCE_ROOT", root)
        first_party = [
            VersionPin(
                artifact=f"extractor_{representation.value.lower()}",
                version=version,
                content_sha256=run_config.extractor_pin(representation).content_sha256,
            )
            for representation, version in EXTRACTOR_VERSIONS.items()
        ]
        vendors = [
            vendor_version_pin(run_config.vendor_extractor_pin(source_id, "-"))
            for source_id in VENDOR_EXTRACTORS
        ]
    return first_party + vendors


@pytest.mark.pg
def test_onboarding_on_a_seed_commit_database_drifts_no_pin_and_changes_no_row(
    ingest: Ingest,
    pg_db: PgTestDatabase,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C3 upgrade: a database with Stage-1-style Apar evidence and every extractor pin computed
    from the seed commit's source bytes; onboarding Apar then succeeds (no
    VersionContentDriftError: no pinned source changed) and every pre-existing row stays."""
    ingest.run(ingest.intake(XBRL_ONLY))
    ingest.repository.pin_versions(_seed_pins(monkeypatch, tmp_path / "seed-src"))
    tables = [
        name
        for (name,) in rows(
            pg_db, "SELECT tablename FROM pg_tables WHERE schemaname = 'eqos' ORDER BY 1"
        )
    ]

    def snapshot() -> dict[str, set[str]]:
        return {
            name: {
                json.dumps(row, default=str) for row in rows(pg_db, f"SELECT * FROM eqos.{name}")
            }
            for name in tables
        }

    before = snapshot()
    for name, value in pg_db.cli_env().items():
        monkeypatch.setenv(name, value)
    root = write_root(tmp_path / "raw", world(APAR), APAR)
    snapshots = tmp_path / "snapshots"
    assert (
        main(["onboard", APAR, "--raw-root", str(root), "--snapshot-root", str(snapshots)])
        == INCOMPLETE
    )
    after = snapshot()
    assert all(before[name] <= after[name] for name in tables)
    assert rows(pg_db, "SELECT count(*) FROM eqos.occurrences")[0][0] > len(before["occurrences"])


def test_comparison_vendors_refuse_identity_and_first_party_surfaces() -> None:
    """A catalog surface registered only for onboarding (an identity surface, the XBRL
    instance download) is not a comparison vendor; a vendor surface still is."""

    def scope(vendor: tuple[str, str]) -> RunScope:
        return RunScope(
            entity_ids=(1,),
            period_ends=(JUN_END,),
            bases=(Basis.CONSOLIDATED,),
            sources=FIRST_PARTY_SOURCES,
            vendors=(vendor,),
        )

    for vendor in ("nse", "EQUITY_L"), ("nse-indas-xbrl-consolidated", "NSE_XBRL_INSTANCE"):
        with pytest.raises(ValidationError, match="not a comparison vendor"):
            scope(vendor)
    assert scope(("tijori", "financials")).vendors == (("tijori", "financials"),)
