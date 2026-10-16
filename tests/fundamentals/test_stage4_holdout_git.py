"""Stage 4 held-out checks over synthetic git repos (plan D6 D1.3, D1.5, D1.6; T1b C9-C11).

Every company value here is invented (``ZZ`` prefix); the real record is checked only through
``test_frozen_manifests.py -k stage4_holdout``.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import pytest
import yaml
from stage4_support import (
    CHECKS,
    DISCOVERY,
    FREEZE,
    RECORD,
    attempt_payload_sha256,
    matcher,
    qualifying_periods,
    selection_hits,
    sha256,
)

ID, ISIN, SCRIP = "ZZHOLD", "INE000Z01011", "999123"
FRAME = (
    "Company Name,Industry,Symbol,Series,ISIN Code\n"
    f"Zz Holdout Widgets Ltd.,Capital Goods,{ID},EQ,{ISIN}\n"
)
MASTER = (
    "SYMBOL,NAME OF COMPANY, SERIES, DATE OF LISTING, PAID UP VALUE, MARKET LOT, ISIN NUMBER,"
    f" FACE VALUE\n{ID},Zz Holdout Widgets Limited,EQ,01-JAN-2000,10,1,{ISIN},10\n"
)
BSE = (
    f"\"<li class='q'><a>ZZ HOLDOUT<br /><span>{ID}&nbsp;"
    f'<strong>{ISIN}</strong>&nbsp;{SCRIP}</span></a></li>"'
)
FAILED = pytest.fail.Exception


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def commit(repo: Path, files: dict[str, str | bytes | None]) -> str:
    """Write (None: remove) the files, commit them and return the commit id."""
    for path, content in files.items():
        if content is None:
            git(repo, "rm", "-q", path)
            continue
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_bytes(content if isinstance(content, bytes) else content.encode())
        git(repo, "add", path)
    git(repo, "commit", "-q", "--allow-empty", "-m", "c")
    return git(repo, "rev-parse", "HEAD")


def untracked(path: Path, text: str) -> None:
    """Write a file git does not track."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q", "-b", "main")
    for key, value in (("user.email", "t@example.com"), ("user.name", "t")):
        git(tmp_path, "config", key, value)
    git(tmp_path, "config", "commit.gpgsign", "false")
    private = tmp_path / "data/holdout/attempt-1"
    private.mkdir(parents=True)
    for name, content in (("a.csv", FRAME), ("b.csv", MASTER), ("c.html", BSE)):
        (private / name).write_text(content)
    commit(tmp_path, {".gitignore": "data/\nscratchpad/\n", "src/app.py": "x = 1\n"})
    return tmp_path


def approved(n: int, seed: str, selection: str) -> dict[str, Any]:
    """An attempt entry carrying an approval over its own payload."""
    frame = {"sha256": sha256(FRAME.encode()), "retrieved_at": "2026-10-15T20:00:00Z"}
    selected = {"seed_commit": seed, "selection_commit": selection, "frame": frame}
    attempt: dict[str, Any] = {"n": n, "identifier": ID, "selection": selected}
    approval = {"reviewer": "gpt-6.1-sol", "verdict": "APPROVE", "date": date(2026, 10, 16)}
    return attempt | {"approval": approval | {"payload_sha256": attempt_payload_sha256(attempt)}}


def dump(attempts: list[dict[str, Any]], burns: list[dict[str, Any]] | None = None) -> str:
    return yaml.safe_dump({"attempts": attempts, "burns": burns or []}, sort_keys=False)


def frozen(*entries: tuple[str, dict[str, Any]]) -> str:
    """Freeze descriptors citing each attempt's implementation commit and payload hash."""
    return yaml.safe_dump(
        {
            "freezes": [
                {
                    "attempt": a["n"],
                    "implementation_commit": impl,
                    "holdout_payload_sha256": attempt_payload_sha256(a),
                }
                for impl, a in entries
            ]
        }
    )


def history(repo: Path, violation: str = "", redraw: bool = True) -> None:
    """Attempt 1 drawn, implemented and frozen; then burned, fixed, redrawn and refrozen."""
    seed = git(repo, "rev-parse", "HEAD")
    if violation == "impl-before-record":
        commit(repo, {"src/app.py": "x = 2\n"})
    selection = commit(repo, {"docs/notes.md": "n\n"})
    if violation == "record-parent":
        commit(repo, {"docs/notes.md": "m\n"})
    one = approved(1, seed, selection)
    commit(repo, {RECORD: dump([one])})
    impl = commit(repo, {DISCOVERY: "d = 1\n"})
    commit(repo, {FREEZE: frozen((impl, one))})
    if violation == "record-edited":
        one = one | {"identifier": "ZZOTHER"}
        commit(repo, {RECORD: dump([one])})
    if redraw:
        burns = [{"attempt": 1, "reason_code": "E2E_DEFECT", "bead": "eqos-zz"}]
        burn = commit(repo, {RECORD: dump([one], burns)})
        fix = commit(repo, {"src/app.py": "x = 3\n"})
        two = approved(2, burn, fix)
        commit(repo, {RECORD: dump([one, two], burns)})
        commit(repo, {FREEZE: frozen((impl, one), (fix, two))})
    if violation == "impl-after-freeze":
        commit(repo, {"src/app.py": "x = 4\n"})


@pytest.mark.parametrize("redraw", [False, True], ids=["initial", "burn-refreeze-redraw"])
def test_ordering_accepts_the_d15_sequence(repo: Path, redraw: bool) -> None:
    history(repo, redraw=redraw)
    CHECKS["ordering"](repo)


@pytest.mark.parametrize(
    ("violation", "step"),
    [
        ("impl-before-record", "IMPL commit before record"),
        ("record-edited", "entry changed after its commit"),
        ("impl-after-freeze", "IMPL change after freeze"),
        ("record-parent", "record parent is not selection_commit"),
    ],
)
def test_ordering_refuses_violations(repo: Path, violation: str, step: str) -> None:
    """Each D1.5 violation fails the ordering check, which names only its step."""
    history(repo, violation)
    with pytest.raises(FAILED) as failed:
        CHECKS["ordering"](repo)
    assert str(failed.value) == f"stage4_holdout ordering: {step}"


def leak_repo(repo: Path) -> None:
    """A drawn attempt-1 record (the exempt carrier of the identifier) and a clean tree."""
    seed = git(repo, "rev-parse", "HEAD")
    selection = commit(repo, {"docs/notes.md": "n\n"})
    commit(repo, {RECORD: dump([approved(1, seed, selection)]), "tests/test_x.py": "ok = 1\n"})


def merge_only(repo: Path) -> None:
    """A token introduced only by a merge resolution, deleted in the next commit."""
    git(repo, "checkout", "-q", "-b", "side")
    commit(repo, {"docs/side.md": "s\n"})
    git(repo, "checkout", "-q", "main")
    commit(repo, {"docs/main.md": "m\n"})
    git(repo, "merge", "-q", "--no-ff", "--no-commit", "side")
    commit(repo, {"src/merged.py": f"code = '{ISIN}'\n"})
    commit(repo, {"src/merged.py": None})


LEAKS: dict[str, Callable[[Path], object]] = {
    "alternate-token-isin": lambda r: commit(r, {"src/a.py": f"x = '{ISIN.lower()}'\n"}),
    "token-in-file-name": lambda r: commit(r, {f"tests/{ID.lower()}_case.py": "ok = 1\n"}),
    "token-in-binary-blob": lambda r: commit(r, {"config/b.bin": b"\x00\xff" + SCRIP.encode()}),
    "token-added-then-deleted": lambda r: [
        commit(r, {"src/a.py": "doc = '''Zz Holdout\n   Widgets'''\n"}),
        commit(r, {"src/a.py": None}),
    ],
    "merge-resolution-only": merge_only,
    "untracked-file": lambda r: untracked(r / "src/scratch.py", f"{ID}\n"),
}


def test_leak_scan_passes_a_clean_repo(repo: Path) -> None:
    """The record itself carries the identifier but is exempt by path (D1.6)."""
    leak_repo(repo)
    CHECKS["leaks"](repo)


@pytest.mark.parametrize("name", LEAKS)
def test_leak_scan_finds_each_mutation(repo: Path, name: str) -> None:
    """Each D1.6 mutation is a leak; the failure names a path with the token redacted."""
    leak_repo(repo)
    LEAKS[name](repo)
    with pytest.raises(FAILED) as failed:
        CHECKS["leaks"](repo)
    message = str(failed.value)
    assert message.startswith("stage4_holdout leaks: leak at ")
    assert not {ID, ISIN, SCRIP} & set(message.replace("/", " ").replace("_", " ").split())


SELECTION_USES: dict[str, Callable[[Path], object]] = {
    "deleted-before-selection": lambda r: [
        commit(r, {"docs/old.md": f"see {ID}\n"}),
        commit(r, {"docs/old.md": None}),
    ],
    "untracked-development-file": lambda r: untracked(r / "docs/draft.md", f"{ISIN}\n"),
    "ignored-development-file": lambda r: untracked(
        r / "scratchpad/aid.py", "name = 'zz holdout widgets'\n"
    ),
    "data-directory-name": lambda r: (r / f"data/raw/{ID.lower()}").mkdir(parents=True),
}


@pytest.mark.parametrize("name", SELECTION_USES)
def test_development_use_excludes_a_company(repo: Path, name: str) -> None:
    """C9: past, untracked and ignored use at selection all hit; a clean repo does not."""
    pattern = matcher([ID, ISIN, "Zz Holdout Widgets"])
    assert not selection_hits(repo, "HEAD", pattern)
    SELECTION_USES[name](repo)
    assert selection_hits(repo, git(repo, "rev-parse", "HEAD"), pattern)


def listing_row(end: str, broadcast: str | None, **fields: str) -> dict[str, Any]:
    row = {"symbol": ID, "type": "Integrated Filing- Financials", "consolidated": "Consolidated"}
    return row | {"qe_Date": end, "broadcast_Date": broadcast} | fields


JUN, MAR, T1, T2 = "30-JUN-2026", "31-MAR-2026", "01-Aug-2026 10:00:00", "05-Aug-2026 10:00:00"


@pytest.mark.parametrize(
    ("rows", "expected"),
    [
        ([listing_row(JUN, T1), listing_row(JUN, T2, seq_Id="2")], 1),
        ([listing_row(JUN, T1), listing_row(MAR, T1)], 2),
        ([listing_row(JUN, T1), listing_row(JUN, T1, seq_Id="2"), listing_row(MAR, T1)], None),
        ([listing_row(JUN, T1), listing_row("31-MAR-2025", T1)], 1),
        ([listing_row(JUN, T2, consolidated="Standalone"), listing_row(MAR, T1)], 1),
        ([listing_row(JUN, T1), listing_row(JUN, None, seq_Id="2"), listing_row(MAR, T1)], 1),
    ],
    ids=[
        "two-revisions-one-period",
        "two-distinct-periods",
        "equal-broadcast-skips",
        "period-outside-window",
        "standalone-not-counted",
        "unbroadcast-row-voids-its-period",
    ],
)
def test_filing_window_rule(rows: list[dict[str, Any]], expected: int | None) -> None:
    """C11: counts distinct period ends after collapse at a pinned as_of; fewer than two (or a
    tie, None) is NO_CONSOLIDATED_INCAPMKT."""
    assert qualifying_periods(rows, date(2026, 10, 16)) == expected


@pytest.mark.parametrize("as_of", ["2026-10-17", "2026-10-15"], ids=["later", "utc-date"])
def test_draw_refuses_an_as_of_not_from_retrieved_at(repo: Path, as_of: str) -> None:
    """C13: only the Asia/Kolkata date of the frame's retrieved_at (2026-10-16 here) is as_of."""
    attempt = approved(1, "0" * 40, "0" * 40)
    attempt["selection"]["as_of"] = as_of
    (repo / RECORD).parent.mkdir(parents=True)
    (repo / RECORD).write_text(dump([attempt]))
    with pytest.raises(FAILED) as failed:
        CHECKS["draw"](repo)
    assert str(failed.value) == "stage4_holdout draw: as_of"
