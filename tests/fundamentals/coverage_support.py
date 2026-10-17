"""Shared fixtures of the D7 coverage tests: retained instrument captures, the screen export,
pinned onboarding generations and owner CLI runs.

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
from datetime import datetime
from pathlib import Path

from retained_support import REPO_ROOT

from fundamentals.api.cli import main

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
