"""PREP-2: the Apar pilot run opens no SQLite store and refuses without an OPEN PostgreSQL one.

The committed configs name only the PostgreSQL store; a run without one, or against a store that
is not reopened, refuses before writing and never constructs the legacy ``FactStore``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pg_support import PgTestDatabase
from psycopg_pool import ConnectionPool
from retained_support import REPO_ROOT
from temporal_fixture_support import install_trusted_fixture_cli
from test_legacy_import import Rig

import fundamentals.api.cli as cli
import fundamentals.pg.cutover as cutover
from fundamentals.api.cli import main
from fundamentals.api.config import load_config
from fundamentals.pg.cutover import FactStoreRequiredError
from fundamentals.store.fact_store import FactStore
from fundamentals.store.pg_fact_store import FactStoreFrozenError

PILOT_STORE = "sqlite-cb02b0f12a1708d0"
# Q4 runs from its -pg copy: the frozen Stage 5 manifest pins aparinds-fy26-q4.yaml's bytes.
PILOT_CONFIGS = [
    REPO_ROOT / "config" / f"aparinds-{quarter}.yaml"
    for quarter in ("fy26-q2", "fy26-q3", "fy26-q4-pg", "fy27-q1")
]
COUNTS = "SELECT (SELECT count(*) FROM eqos.fact_rows), (SELECT count(*) FROM eqos.report_versions)"


def test_committed_pilot_configs_name_only_postgres() -> None:
    """Every Apar quarter routes to the imported store and configures no SQLite file."""
    assert len(PILOT_CONFIGS) == 4
    for path in PILOT_CONFIGS:
        config = load_config(path)
        assert (config.fact_store_id, config.store_db) == (PILOT_STORE, None), path.name


def _pilot_copy(tmp_path: Path, **override: object) -> Path:
    """The Q3 FY26 pilot config with repo-absolute sources and a ledger under ``tmp_path``."""
    source = REPO_ROOT / "config" / "aparinds-fy26-q3.yaml"
    body = yaml.safe_load(source.read_text(encoding="utf-8"))
    body["raw_dir"] = str(REPO_ROOT / body["raw_dir"])
    body["xbrl"]["local_path"] = str(REPO_ROOT / body["xbrl"]["local_path"])
    for comparator in body["comparators"].values():
        comparator["local_path"] = str(REPO_ROOT / comparator["local_path"])
    body |= override
    path = tmp_path / "config" / source.name
    path.parent.mkdir(exist_ok=True)
    path.write_text(yaml.safe_dump(body, allow_unicode=True), encoding="utf-8")
    return path


@pytest.mark.pg
@pytest.mark.retained
def test_pilot_run_refuses_without_postgres_store(
    pg_db: PgTestDatabase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No store id refuses before any pool; an imported, not reopened store refuses frozen.
    Neither builds a SQLite store nor writes a fact or report version."""
    rig = Rig(pg_db, tmp_path)
    rig.register()
    rig.run(*rig.pair())
    for name, value in pg_db.cli_env().items():
        monkeypatch.setenv(name, value)
    install_trusted_fixture_cli(monkeypatch)

    def no_sqlite(*_: object) -> FactStore:
        raise AssertionError("the pilot run must not construct a SQLite FactStore")

    monkeypatch.setattr(cutover, "FactStore", no_sqlite)
    before = rig.query(COUNTS)

    def run(config: Path) -> int:
        out = ["--out-json", str(tmp_path / "run.json"), "--out", str(tmp_path / "run.md")]
        return main(
            ["run", "--issuer", "APARINDS", "--quarter", "Q3-FY26", "--config", str(config), *out]
        )

    with monkeypatch.context() as patch:

        def no_pool(*_: object) -> ConnectionPool:
            raise AssertionError("a run without a store id must refuse before any pool")

        patch.setattr(cli, "open_pool", no_pool)
        with pytest.raises(FactStoreRequiredError):
            run(_pilot_copy(tmp_path, fact_store_id=None))
    with pytest.raises(FactStoreFrozenError) as frozen:
        run(_pilot_copy(tmp_path))
    assert frozen.value.state == "IMPORTED"
    assert rig.query(COUNTS) == before
