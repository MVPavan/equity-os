"""D3.6 acceptance: ``ledger export`` reproduces every imported Apar version's content hash
(plan Task 6; P2).

The five retained versions are imported on an ``eqos_test_*`` database (``ledger_cited_support``)
and exported through the CLI. The export is the narrative alone: it hashes to the stored content
hash, an earnings update's equals its source Markdown, re-export is byte-identical, and a status
change (owner ``WITHDRAW``, a successor's approval) leaves it unchanged.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from ledger_cited_support import Cited, cited
from ledger_support import RULING
from pg_support import PgTestDatabase
from test_ledger_import import CONFIG, PINNED, REPO, update_paths
from test_ledger_lifecycle import POLICY, SECTION, policy_claim

from equity_os.contracts.publication.ledger import (
    DecisionKind,
    ReportKind,
    SubjectKind,
    VersionDraft,
    VersionStatus,
)
from equity_os.interface.commands.sourcing.screener_cli_dispatch import EXIT_OK
from equity_os.interface.entry.cli import main
from equity_os.publication.approval import lifecycle
from equity_os.publication.approval.lifecycle import version_status
from equity_os.publication.drafting.display import content_hash
from equity_os.publication.revision.importer import import_versions, load_import_config
from equity_os.storage.database.settings import PgRole
from equity_os.storage.records import store

__all__ = ["cited"]


def _export(version_id: int, out: Path) -> bytes:
    """One ``ledger export`` run through the CLI; the bytes it wrote."""
    assert main(["ledger", "export", str(version_id), "--out", str(out)]) == EXIT_OK
    return out.read_bytes()


def _approve_successor(cited: Cited, predecessor: int) -> int:
    """A successor of ``predecessor`` drafted, submitted and approved (so checked) by the owner."""
    paths = {"catalog": cited.catalog, "snapshots": cited.snapshots}
    owner = cited.pools[PgRole.OWNER]
    (report_id,) = cited.query(
        "SELECT report_id FROM eqos.report_versions WHERE id = %s", predecessor
    )[0]
    policy = lifecycle.decide(
        owner,
        subject_kind=SubjectKind.REPORT,
        subject_id=report_id,
        kind=DecisionKind.SET_POLICY,
        ruling=RULING,
        policy=POLICY,
    )
    claims = (policy_claim(policy.id),)
    draft = VersionDraft(
        report_id=report_id,
        predecessor_id=predecessor,
        author="fixture-author",
        knowledge_cutoff=policy.recorded_at,
        content_hash=content_hash((SECTION,), claims),
        sections=(SECTION,),
        claims=claims,
    )
    with cited.runtime() as cursor:
        successor = store.create_version(cursor, draft)
    lifecycle.submit(cited.pools[PgRole.RUNTIME], successor, **paths)
    lifecycle.decide(
        owner,
        subject_kind=SubjectKind.REPORT_VERSION,
        subject_id=successor,
        kind=DecisionKind.APPROVE,
        ruling=RULING,
        **paths,
    )
    return successor


@pytest.mark.pg
@pytest.mark.retained
def test_export_reproduces_every_imported_content_hash(
    cited: Cited, pg_db: PgTestDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every imported version exports to bytes hashing to its stored content hash (an update's
    are its source Markdown), identically on re-export and after its status changes."""
    results = import_versions(
        cited.pools[PgRole.PANEL],
        load_import_config(CONFIG),
        repo=REPO,
        catalog=cited.catalog,
        snapshots=cited.snapshots,
    )
    versions = {(r.period, r.kind): r.version_id for r in results}
    assert len(versions) == 5 and None not in versions.values()
    for name, value in pg_db.cli_env().items():
        monkeypatch.setenv(name, value)
    out = cited.tmp_path / "export.md"
    exported: dict[int, bytes] = {}
    for (period, kind), version_id in versions.items():
        assert version_id is not None
        body = _export(version_id, out)
        with cited.runtime() as cursor:
            stored = store.read_version(cursor, version_id).content_hash
        assert hashlib.sha256(body).hexdigest() == stored
        if kind is ReportKind.EARNINGS_UPDATE:
            assert stored == PINNED[update_paths(period)[0]]
        assert _export(version_id, out) == body
        exported[version_id] = body

    q0 = versions[("FY26_Q2", ReportKind.BOOTSTRAP_THESIS)]
    update = versions[("FY26_Q2", ReportKind.EARNINGS_UPDATE)]
    assert q0 is not None and update is not None
    lifecycle.decide(
        cited.pools[PgRole.OWNER],
        subject_kind=SubjectKind.REPORT_VERSION,
        subject_id=q0,
        kind=DecisionKind.WITHDRAW,
        ruling=RULING,
    )
    _approve_successor(cited, update)
    with cited.runtime() as cursor:
        statuses = (version_status(cursor, q0), version_status(cursor, update))
    assert statuses == (VersionStatus.WITHDRAWN, VersionStatus.SUPERSEDED)
    for version_id in (q0, update):
        assert _export(version_id, out) == exported[version_id]
