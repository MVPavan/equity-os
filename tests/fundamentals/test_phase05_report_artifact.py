"""Slice phase05-sA — footnote provenance, the JSON report artifact, and the store path.

Three contracts, all exercised on the committed SYNTHETIC Q1 FY25 fixtures the
existing ``test_pipeline_e2e`` module runs on (no real filing bytes, no network):

* a concept the run never cross-checked must render and store with the XBRL
  source only — a footnote must point at a source that states the value;
* ``run --out-json`` must emit an ``EarningsUpdate`` that round-trips exactly,
  and must refuse to replace an artifact it did not create;
* the composition root must create the store's parent directory, so a config
  that names a not-yet-existing directory runs instead of failing to open SQLite.
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from typing import Any

import pytest
import yaml

from fundamentals.api.cli import main, run_command
from fundamentals.api.cli_parser import build_parser
from fundamentals.api.config import FundamentalsConfig, load_config
from fundamentals.api.pipeline import PipelineResult, XbrlInput, run_pipeline
from fundamentals.contracts.fact import Fact, ReconciliationStatus
from fundamentals.output.earnings_update import EarningsUpdate
from fundamentals.store.fact_store import FactStore

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_PATH = _REPO_ROOT / "config" / "fundamentals.yaml"
_SYNTHETIC_XBRL = (
    _REPO_ROOT / "tests" / "fundamentals" / "fixtures" / "synthetic_q1_fy25_consolidated.xml"
)

_ISSUER_ARG = "INFY"
_QUARTER_ARG = "Q1-FY25"

# Profit before tax is a role concept the results PDF also prints, so dropping it
# from ``cross_check`` reproduces the defect's shape: extracted from the PDF, but
# never compared against it.
_UNCOMPARED_CONCEPT = "in-bse-fin:ProfitBeforeTax"
_COMPARED_CONCEPT = "in-bse-fin:RevenueFromOperations"

_SELECT_ALL_FACT_JSON = "SELECT fact_json FROM facts"


def _config() -> FundamentalsConfig:
    return load_config(_CONFIG_PATH)


def _synthetic_xbrl_input(config: FundamentalsConfig) -> XbrlInput:
    """Build the XBRL input from the committed synthetic instance (same as the e2e module)."""
    xml_bytes = _SYNTHETIC_XBRL.read_bytes()
    return XbrlInput(
        xml_bytes=xml_bytes,
        file_sha256=hashlib.sha256(xml_bytes).hexdigest(),
        source_id=config.xbrl.source_id,
        retrieved_at=config.quarter.knowledge_cutoff,
    )


def _run(config: FundamentalsConfig, store: FactStore) -> PipelineResult:
    """Run the deterministic pipeline for ``config`` against the synthetic fixtures."""
    return run_pipeline(
        config=config,
        xbrl_input=_synthetic_xbrl_input(config),
        results_pdf_path=str(config.results_pdf_path(_CONFIG_PATH)),
        results_pdf_sha256=config.results_pdf.sha256,
        transcript_pdf_path=str(config.transcript_pdf_path(_CONFIG_PATH)),
        transcript_pdf_sha256=config.transcript_pdf.sha256,
        store=store,
    )


def _config_without_cross_check(concept: str) -> FundamentalsConfig:
    """The e2e config with one concept removed from ``concepts.cross_check``."""
    config = _config()
    assert concept in config.concepts.cross_check, concept
    remaining = tuple(name for name in config.concepts.cross_check if name != concept)
    concepts = config.concepts.model_copy(update={"cross_check": remaining})
    return config.model_copy(update={"concepts": concepts})


def _stored_source_ids(db_path: Path, concept: str) -> set[str]:
    """Every source id persisted for ``concept``, canonical or not, read from the DB file."""
    connection = sqlite3.connect(str(db_path))
    try:
        rows = connection.execute(_SELECT_ALL_FACT_JSON).fetchall()
    finally:
        connection.close()
    facts = [Fact.model_validate_json(row[0]) for row in rows]
    return {
        fact.observation.provenance.source_id
        for fact in facts
        if fact.observation.concept_qname == concept
    }


def _run_argv(*, out_json: Path | None = None, config_path: Path | None = None) -> list[str]:
    argv = ["run", "--issuer", _ISSUER_ARG, "--quarter", _QUARTER_ARG]
    if config_path is not None:
        argv += ["--config", str(config_path)]
    if out_json is not None:
        argv += ["--out-json", str(out_json)]
    return argv


def _config_file_with_store_db(tmp_path: Path, store_db: str) -> Path:
    """Copy the e2e config to a temp repo root, pointing ``store_db`` at ``store_db``.

    ``repo_root`` is the config file's grandparent, so the copy lives in
    ``<tmp>/config/``; the held-source paths are made absolute so they still
    resolve back to the committed synthetic fixtures.
    """
    data: dict[str, Any] = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8"))
    data["raw_dir"] = str(_REPO_ROOT / str(data["raw_dir"]))
    data["xbrl"]["local_path"] = str(_REPO_ROOT / str(data["xbrl"]["local_path"]))
    data["store_db"] = store_db
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "fundamentals.yaml"
    config_file.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return config_file


def test_uncompared_concept_carries_only_xbrl_source(tmp_path: Path) -> None:
    # A footnote must point at a source that STATES the value; a concept excluded from
    # cross_check was never compared to the PDF, so PDF provenance would be an unverified claim.
    config = _config_without_cross_check(_UNCOMPARED_CONCEPT)
    db_path = tmp_path / "facts.sqlite"
    store = FactStore(str(db_path))
    try:
        result = _run(config, store)
    finally:
        store.close()

    facts = {fact.concept_qname: fact for fact in result.update.facts}
    uncompared = facts[_UNCOMPARED_CONCEPT]
    assert [source.source_id for source in uncompared.sources] == [config.xbrl.source_id]
    assert uncompared.reconciliation_status is ReconciliationStatus.CROSS_FOOT_PASS

    # Positive control: a concept still in cross_check keeps both confirming sources.
    compared = facts[_COMPARED_CONCEPT]
    assert {source.source_id for source in compared.sources} == {
        config.xbrl.source_id,
        config.results_pdf.source_id,
    }
    assert compared.reconciliation_status is ReconciliationStatus.CROSS_SOURCE_CONFIRMED

    assert _stored_source_ids(db_path, _UNCOMPARED_CONCEPT) == {config.xbrl.source_id}
    assert _stored_source_ids(db_path, _COMPARED_CONCEPT) == {
        config.xbrl.source_id,
        config.results_pdf.source_id,
    }


def test_run_writes_json_artifact_that_round_trips(tmp_path: Path) -> None:
    # A downstream consumer must be able to re-read the exact rendered update; a lossy
    # dump would let the JSON artifact and the markdown disagree about the same run.
    out_json = tmp_path / "update.json"
    exit_code = main(_run_argv(out_json=out_json))

    assert exit_code == 0
    assert out_json.exists()

    result = run_command(build_parser().parse_args(_run_argv(out_json=tmp_path / "unused.json")))
    loaded = EarningsUpdate.model_validate_json(out_json.read_text(encoding="utf-8"))
    assert loaded == result.update


def test_run_json_artifact_refuses_to_clobber(tmp_path: Path) -> None:
    # An artifact this run did not create is evidence of another run; replacing it would
    # destroy that record, so the second write must fail the way every other api/ write does.
    out_json = tmp_path / "update.json"
    assert main(_run_argv(out_json=out_json)) == 0
    first_payload = out_json.read_bytes()

    with pytest.raises(SystemExit) as excinfo:
        main(_run_argv(out_json=out_json))

    assert str(out_json) in str(excinfo.value)
    assert out_json.read_bytes() == first_payload


def test_store_parent_directory_is_created(tmp_path: Path) -> None:
    # The persistent store path is configuration, not data: naming a directory that does not
    # exist yet must not make the run fail to open SQLite on a fresh checkout.
    config_file = _config_file_with_store_db(tmp_path, "data/store/synthetic.sqlite")
    db_path = tmp_path / "data" / "store" / "synthetic.sqlite"
    assert not db_path.parent.exists()

    exit_code = main(_run_argv(config_path=config_file))

    assert exit_code == 0
    assert db_path.exists()
