"""Shared fixtures of the D7 coverage tests: retained instrument captures, the screen export,
pinned onboarding generations, owner CLI runs and the watchlist seed.

Re-marked snapshots are SYNTHETIC: written only under ``tmp_path``, never committed. The screen
export is ``SYNTHETIC-FORMAT`` until the owner supplies a real one (plan D7 Q1): a hand-written
``Name,BSE Code,NSE Code`` file for Task 2 development only, never a manifest source.
"""

from __future__ import annotations

import contextlib
import gzip
import hashlib
import io
import json
import shutil
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool
from retained_support import REPO_ROOT

from fundamentals.api.cli import main
from fundamentals.contracts.ledger import DecisionKind, DecisionRecord, SubjectKind
from fundamentals.contracts.onboarding import VerificationUnit
from fundamentals.contracts.source_catalog import SCREEN_EXPORT
from fundamentals.entity.discovery import OK, Capture, Request, Response, store_captures
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.ledger import lifecycle
from fundamentals.pg.settings import PgRole
from fundamentals.store.snapshot_store import SnapshotStore

INSTRUMENTS = (
    REPO_ROOT
    / "data/raw/upstox/instruments/complete/20260904T082313Z-459ec0544e40"
    / "upstox_instruments.raw.json.gz"
)
_META = "upstox_instruments_meta.json"
SCREEN_CSV = Path(__file__).parent / "fixtures" / "coverage" / "screen_export.csv"
SCREEN_CSV_PROVENANCE = "SYNTHETIC-FORMAT"
SCREEN_HEADER = "Name,BSE Code,NSE Code"
# Development companies and their v2-smoke generations (plan D7 R8), all PARTIAL at preflight.
LIVE_SMOKE = REPO_ROOT / "data/raw/onboarding-dev/live-smoke"
GENERATIONS = {"ETERNAL": 1, "POLYCAB": 1, "TITAN": 1, "THERMAX": 3, "CGPOWER": 1}


def pinned_copies(root: Path, symbols: tuple[str, ...]) -> Path:
    """``root/<SYMBOL>/gen-<n>``: copies of each symbol's pinned generation only."""
    for symbol in symbols:
        generation = f"gen-{GENERATIONS[symbol]}"
        shutil.copytree(LIVE_SMOKE / symbol / generation, root / symbol / generation)
    return root


def remark(body: bytes, segment: str, old: str, new: str) -> bytes:
    """SYNTHETIC: the instrument file with one listing's trading symbol re-marked."""
    rows = json.loads(gzip.decompress(body))
    (row,) = [r for r in rows if r.get("segment") == segment and r.get("trading_symbol") == old]
    row["trading_symbol"] = new
    return gzip.compress(json.dumps(rows).encode(), mtime=0)


def capture(folder: Path, body: bytes, retrieved_at: datetime) -> Path:
    """A retained capture directory holding ``body`` retrieved at ``retrieved_at``."""
    folder.mkdir(parents=True)
    meta = json.loads((INSTRUMENTS.parent / _META).read_text())
    meta |= {
        "content_sha256": hashlib.sha256(body).hexdigest(),
        "byte_count": len(body),
        "retrieved_at": retrieved_at.isoformat(),
    }
    (folder / _META).write_text(json.dumps(meta))
    path = folder / INSTRUMENTS.name
    path.write_bytes(body)
    return path


def coverage(*args: str) -> tuple[int, dict[str, str]]:
    """``main(["coverage", …])`` and its tab-separated stdout as a mapping."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = main(["coverage", *args])
    return code, dict(line.split("\t") for line in out.getvalue().splitlines())


_SECURITY = (
    "INSERT INTO eqos.securities (entity_id, isin, share_class, evidence_input_id) "
    "SELECT id, %s, 'EQUITY', evidence_input_id FROM eqos.reporting_entities WHERE id = %s"
)
_RECORD = (
    "INSERT INTO eqos.onboarding_records (identifier, identifier_namespace, outcome, entity_id) "
    "SELECT entity_key, 'NSE_SYMBOL', 'PARTIAL', id FROM eqos.reporting_entities WHERE id = %s "
    "RETURNING id"
)
_RUN = (
    "INSERT INTO eqos.runs (identity_hash, cutoff, mode, status, code_version, manifest, "
    "manifest_sha256) VALUES (%s, now(), 'AS_KNOWN', 'INCOMPLETE', 'seed', %s, %s) RETURNING id"
)
_OWNER_ROWS = (
    "INSERT INTO eqos.screens (text_sha256, screen_text) "
    "VALUES (encode(sha256(convert_to(%(tag)s, 'UTF8')), 'hex'), %(tag)s) RETURNING id",
    "INSERT INTO eqos.screen_runs (screen_id, capture_ref_id) VALUES (%(screen)s, %(capture)s) "
    "RETURNING id",
    "INSERT INTO eqos.registry_listings (segment, isin) VALUES ('NSE_EQ', %(isin)s) "
    "ON CONFLICT DO NOTHING RETURNING id",
    "INSERT INTO eqos.screen_members (screen_run_id, row_number, name, listing_id) "
    "SELECT %(run)s, 1, 'seed', id FROM eqos.registry_listings "
    "WHERE segment = 'NSE_EQ' AND isin = %(isin)s RETURNING id",
    "INSERT INTO eqos.capture_batches (screen_run_id, member_ids) "
    "VALUES (%(run)s, ARRAY[%(member)s]::bigint[]) RETURNING id",
    "INSERT INTO eqos.batch_member_results (batch_id, member_id, outcome, entity_id, "
    "onboarding_record_id, run_id, exit_code) "
    "VALUES (%(batch)s, %(member)s, 'PARTIAL', %(entity)s, %(record)s, %(compare)s, 4) "
    "RETURNING id",
)
_KEYS = ("screen", "run", "listing", "member", "batch", "result")
_COMPLETE = "INSERT INTO eqos.batch_completions (batch_id) VALUES (%s)"
SEED_RULING = "SEED: on the watchlist for the test"


def batched(
    pools: Mapping[PgRole, ConnectionPool],
    entity_id: int,
    snapshots: SnapshotStore,
    *,
    complete: bool = True,
) -> int:
    """SEED: the stock as an admitted (PARTIAL) member of a one-member batch, completed unless
    ``complete`` is false; returns the batch id. The runtime writes the onboarding record, the
    same-entity run and, when the stock has none, a synthetic ISIN; the owner registers a
    SYNTHETIC screen export in ``snapshots`` and writes the rest."""
    tag = uuid.uuid4().hex
    source_id, surface = SCREEN_EXPORT
    export = Capture(
        request=Request(
            unit=VerificationUnit.SCREENER, source_id=source_id, surface=surface, url=tag
        ),
        response=Response(
            outcome=OK, body=f"{SCREEN_HEADER}\n{tag},,\n".encode(), retrieved_at=datetime.now(UTC)
        ),
    )
    with snapshots.prepare_ordinary_output():
        ((_, ref),) = store_captures(snapshots, EvidenceRepository(pools[PgRole.OWNER]), [export])
    with pools[PgRole.RUNTIME].connection() as conn, conn.transaction():
        found = conn.execute(
            "SELECT isin FROM eqos.securities WHERE entity_id = %s AND isin IS NOT NULL",
            (entity_id,),
        ).fetchone()
        isin = f"INSEED{entity_id:06d}" if found is None else found[0]
        if found is None:
            conn.execute(_SECURITY, (isin, entity_id))
        ((record,),) = conn.execute(_RECORD, (entity_id,)).fetchall()
        scope = Jsonb({"scope": {"entity_ids": [entity_id]}})
        ((run,),) = conn.execute(_RUN, (tag, scope, "0" * 64)).fetchall()
    ids: dict[str, object] = {"tag": tag, "isin": isin, "entity": entity_id}
    ids |= {"capture": ref.capture_ref_id, "record": record, "compare": run}
    with pools[PgRole.OWNER].connection() as conn, conn.transaction():
        for key, query in zip(_KEYS, _OWNER_ROWS, strict=True):
            row = conn.execute(query, ids).fetchone()
            ids[key] = None if row is None else row[0]
        if complete:
            conn.execute(_COMPLETE, (ids["batch"],))
    return int(str(ids["batch"]))


def watchlist(
    pools: Mapping[PgRole, ConnectionPool], entity_id: int, snapshots: SnapshotStore
) -> DecisionRecord:
    """SEED: the stock covered by a completed batch, then the owner's ``ADD``."""
    batched(pools, entity_id, snapshots)
    return lifecycle.decide(
        pools[PgRole.OWNER],
        subject_kind=SubjectKind.WATCHLIST,
        subject_id=entity_id,
        kind=DecisionKind.ADD,
        ruling=SEED_RULING,
    )
