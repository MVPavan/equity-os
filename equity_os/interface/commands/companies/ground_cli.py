"""``onboard <SYMBOL> --ground --structure <path> {--acquire | --generation <n>}``: grounding
(spec 2026-11-06-vendor-first §8 step 1). ``--acquire`` writes the next ``gen-<n>`` under
``--raw-root`` through the live transport; ``--generation`` replays one. The structure JSON goes
to ``--structure``; nothing but captures is written to the database."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from equity_os.companies.onboarding.discovery import (
    Capture,
    Send,
    acquiring_fetch,
    replay_fetch,
    write_generation,
)
from equity_os.companies.onboarding.grounding import ground
from equity_os.interface.commands.sourcing.shareholding_cli import GENERATION_PREFIX
from equity_os.storage.database.pool import open_pool
from equity_os.storage.database.settings import PgRole, PgSettings
from equity_os.storage.raw_files.snapshot_store import SnapshotStore
from equity_os.verification.comparison.run_models import RunExitStatus

AUTHORIZATION = "VENDOR-1 §8 step 1 grounding"
_ONE_MODE = "--ground needs --structure and exactly one of --acquire and --generation"


def run_ground(
    args: argparse.Namespace, transport: Callable[[], Send], clock: Callable[[], datetime]
) -> int:
    """Acquire or replay one grounding generation and write its structure JSON."""
    if args.structure is None or args.acquire == (args.generation is not None):
        raise ValueError(_ONE_MODE)
    root: Path = args.raw_root
    log: list[Capture] = []
    if args.acquire:
        taken = [
            int(p.name.removeprefix(GENERATION_PREFIX)) for p in root.glob(GENERATION_PREFIX + "*")
        ]
        generation = max(taken, default=0) + 1
        fetch = acquiring_fetch(transport(), clock, log)
    else:
        generation = args.generation
        fetch = replay_fetch(root / f"{GENERATION_PREFIX}{generation}")
    store = SnapshotStore(args.snapshot_root)
    try:
        with (
            store.prepare_ordinary_output(),
            open_pool(PgSettings(), PgRole.RUNTIME) as pool,
            pool.connection() as conn,
        ):
            conn.autocommit = True
            structure = ground(conn, store, fetch, args.symbol)
    finally:
        if log:
            folder = root / f"{GENERATION_PREFIX}{generation}"
            write_generation(folder, args.symbol, AUTHORIZATION, generation, log)
    args.structure.write_text(json.dumps({"generation": generation, **structure}, indent=1))
    return RunExitStatus.SUCCESS
