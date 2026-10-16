"""Stage 4 held-out checks over synthetic git repos (plan D6 D1.3, D1.5, D1.6; T1b C9-C11).

Every company value here is invented (``ZZ`` prefix); the real record is checked only through
``test_frozen_manifests.py -k stage4_holdout``.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import pytest
import yaml
from stage4_filings import qualifying_periods
from stage4_support import (
    BSE_NOT_ONE,
    CHECKS,
    DISCOVERY,
    FREEZE,
    NO_FILINGS,
    NO_XBRL,
    RECORD,
    TOKEN_HIT,
    RefusedError,
    Selection,
    attempt_payload_sha256,
    descriptor_sha256,
    matcher,
    selection_hits,
    sha256,
)

ID, ISIN, SCRIP = "ZZHOLD", "INE000Z01011", "999123"
COMPANIES = [  # symbol, name, Industry, ISIN
    (ID, "Zz Holdout Widgets", "Capital Goods", ISIN),
    ("ZZBANK", "Zz Bank", "Financial Services", "INE000Z01029"),
    ("ZZUSED", "Zz Used", "Chemicals", "INE000Z01037"),
    ("ZZDATA", "Zz Data", "Chemicals", "INE000Z01045"),
    ("ZZSKIP", "Zz Skip", "Chemicals", "INE000Z01052"),
]
FRAME = "Company Name,Industry,Symbol,Series,ISIN Code\n" + "".join(
    f"{name} Ltd.,{industry},{symbol},EQ,{isin}\n" for symbol, name, industry, isin in COMPANIES
)
MASTER = (
    "SYMBOL,NAME OF COMPANY, SERIES, DATE OF LISTING, PAID UP VALUE, MARKET LOT, ISIN NUMBER,"
    " FACE VALUE\n"
) + "".join(f"{s},{n} Limited,EQ,01-JAN-2000,10,1,{i},10\n" for s, n, _, i in COMPANIES)
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


def churn(repo: Path, violation: str, kind: str, path: str, *versions: str) -> None:
    """For the kind's churn violation, commit its edited (or appended) version, then the
    original ``versions[0]`` back."""
    for i, how in enumerate(("edited-then-restored", "appended-then-deleted"), start=1):
        if violation == f"{kind}-{how}":
            commit(repo, {path: versions[i]})
            commit(repo, {path: versions[0]})


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
    other = one | {"identifier": "ZZOTHER"}
    churn(repo, violation, "attempt", RECORD, dump([one]), dump([other]), dump([one, other]))
    churn(
        repo,
        violation,
        "freeze",
        FREEZE,
        frozen((impl, one)),
        frozen((impl, other)),
        frozen((impl, one), (impl, other)),
    )
    if violation == "record-edited":
        one = one | {"identifier": "ZZOTHER"}
        commit(repo, {RECORD: dump([one])})
    if redraw:
        (entry,) = yaml.safe_load(frozen((impl, one)))["freezes"]
        cited = {  # the descriptor hash a burn cites: its own attempt's entry, unless violated
            "burn-wrong-hash": "f" * 64,
            "burn-another-attempt": descriptor_sha256(entry | {"attempt": 2}),
        }.get(violation, descriptor_sha256(entry))
        burns = [
            {"attempt": 1, "reason_code": "E2E_DEFECT", "bead": "eqos-zz"}
            | {"freeze_descriptor_sha256": cited, "date": "2026-10-16"}
        ]
        burn = commit(repo, {RECORD: dump([one], burns)})
        edited, extra = burns[0] | {"bead": "eqos-yy"}, burns[0] | {"attempt": 2}
        texts = (dump([one], burns), dump([one], [edited]), dump([one], [*burns, extra]))
        churn(repo, violation, "burn", RECORD, *texts)
        fix = commit(repo, {"src/app.py": "x = 3\n"})
        two = approved(2, burn, fix)
        commit(repo, {RECORD: dump([one, two], burns)})
        commit(repo, {FREEZE: frozen((impl, one), (fix, two))})
    if violation == "impl-after-freeze":
        commit(repo, {"src/app.py": "x = 4\n"})
    if violation in REMOVALS:
        commit(repo, {FREEZE: REMOVALS[violation]})


REMOVALS = {"freeze-list-emptied": "freezes: []\n", "freeze-file-deleted": None}


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
        ("burn-wrong-hash", "burn descriptor"),
        ("burn-another-attempt", "burn descriptor"),
        *(
            (f"{kind}-{how}", "entry changed after its commit")
            for kind in ("attempt", "burn", "freeze")
            for how in ("edited-then-restored", "appended-then-deleted")
        ),
        *((removal, "entry changed after its commit") for removal in REMOVALS),
    ],
)
def test_ordering_refuses_violations(repo: Path, violation: str, step: str) -> None:
    """Each D1.5 violation fails the ordering check, which names only its step."""
    history(repo, violation)
    with pytest.raises(FAILED) as failed:
        CHECKS["ordering"](repo)
    assert str(failed.value) == f"stage4_holdout ordering: {step}"


def test_ordering_accepts_a_repository_never_frozen(repo: Path) -> None:
    """No freeze file in any commit: there is no freeze history to remove."""
    leak_repo(repo)
    CHECKS["ordering"](repo)


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
    "copied-blob-then-deleted-in-scope-copy": lambda r: [
        commit(r, {"docs/a.md": f"{ISIN}\n", "src/a.py": f"{ISIN}\n"}),
        commit(r, {"src/a.py": None}),
    ],
    "record-blob-copied-then-deleted": lambda r: [
        commit(r, {"tests/copy.yaml": (r / RECORD).read_bytes()}),
        commit(r, {"tests/copy.yaml": None}),
    ],
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
        ([listing_row(JUN, T1), listing_row(JUN, T1, xbrl="b.xml"), listing_row(MAR, T1)], None),
        ([listing_row(JUN, T1), listing_row("31-MAR-2025", T1)], 1),
        ([listing_row(JUN, T2, consolidated="Standalone"), listing_row(MAR, T1)], 1),
        ([listing_row(JUN, T1), listing_row(JUN, None, seq_Id="2"), listing_row(MAR, T1)], 1),
        ([listing_row(JUN, T1), listing_row(JUN, "", seq_Id="2"), listing_row(MAR, T1)], 1),
        ([listing_row(JUN, T1), listing_row(JUN, T1), listing_row(MAR, T1)], 2),
        ([listing_row(JUN, T1), listing_row(JUN, T1, seq_Id="2"), listing_row(MAR, T1)], 2),
        ([listing_row(JUN, " ", seq_Id="2"), listing_row(MAR, T1)], 1),
    ],
    ids=[
        "two-revisions-one-period",
        "two-distinct-periods",
        "equal-broadcast-skips",
        "period-outside-window",
        "standalone-not-counted",
        "unbroadcast-row-voids-its-period",
        "empty-broadcast-voids-its-period",
        "identical-rows-collapse-once",
        "rows-differing-only-in-seq-id-collapse-once",
        "blank-broadcast-voids-its-period",
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


def ok(body: object) -> dict[str, object]:
    """A retained successful response."""
    return {"status": 200, "body": body}


def bse(symbol: str, isin: str) -> str:
    """A ``PeerSmartSearch`` body with one exact-ISIN candidate."""
    return f"<li class='q'><a>{symbol}<br /><span>{symbol}&nbsp;<strong>{isin}</strong></span></li>"


def draw_state(repo: Path) -> dict[str, Any]:
    """Attempt 1's private draw inputs: ZZBANK financial, ZZUSED hit by a committed object,
    ZZDATA by a ``data/`` name, ZZSKIP skipped NO_CONSOLIDATED_INCAPMKT, ZZHOLD drawn."""
    selection = commit(repo, {"docs/used.md": "uses ZZUSED\n"})
    hits = {"ZZUSED": f"object {git(repo, 'rev-parse', f'{selection}:docs/used.md')}"}
    integrated = {"data": [listing_row(JUN, T1, symbol="ZZSKIP")]}
    return {
        "selection": selection,
        "reasons": {"ZZBANK": "FINANCIAL", "ZZUSED": TOKEN_HIT, "ZZDATA": TOKEN_HIT},
        "hits": hits | {"ZZDATA": "file data/raw/zzdata"},
        "responses": {"integrated": ok(integrated), "legacy": ok([])},
        "reason": NO_FILINGS,
        "evidence": None,
    }


def draw_check(repo: Path, state: dict[str, Any]) -> Selection:
    """Write the state's private bytes, then recompute the universe and ZZSKIP's skip."""
    private = repo / f"data/holdout/attempt-{state.get('n', 1)}"
    inventory = "".join(sorted(f"{sha256(s.encode())} {r}\n" for s, r in state["reasons"].items()))
    hits = "".join(f"{sha256(s.encode())} token0 {at}\n" for s, at in state["hits"].items())
    envelope = json.dumps({"symbol": "ZZSKIP", "responses": state["responses"]})
    for name, text in (
        ("inventory.txt", inventory),
        ("exclusion_hits.txt", hits),
        ("e.json", envelope),
    ):
        (private / name).write_text(text)
    universe = sorted(s for s, *_ in COMPANIES if s not in state["reasons"])
    selection = {
        "selection_commit": state["selection"],
        "as_of": "2026-10-16",
        "frame": {"sha256": sha256(FRAME.encode()), "column": "Industry"}
        | {"excluded_values": ["Financial Services"]},
        "exclusion_inventory_sha256": sha256(inventory.encode()),
        "universe_sha256": sha256("".join(f"{s}\n" for s in universe).encode()),
        "n_universe": len(universe),
    }
    drawn = Selection(repo, {"n": state.get("n", 1), "identifier": ID, "selection": selection})
    assert drawn.universe() == universe
    evidence = state["evidence"] or sha256(envelope.encode())
    skip = {"symbol_sha256": sha256(b"ZZSKIP"), "reason": state["reason"]}
    drawn.check_skip("ZZSKIP", skip | {"evidence_sha256": evidence})
    return drawn


def later_hit(repo: Path, state: dict[str, Any]) -> None:
    """ZZUSED's hit cites an object committed after ``selection_commit``."""
    later = commit(repo, {"docs/later.md": "later ZZUSED\n"})
    state["hits"]["ZZUSED"] = f"object {git(repo, 'rev-parse', f'{later}:docs/later.md')}"


DRAW_MUTATIONS: dict[str, tuple[Callable[[Path, dict[str, Any]], object], str]] = {
    "financial-relabelled": (
        lambda r, s: s["reasons"].update(ZZBANK=TOKEN_HIT),
        "exclusion reasons",
    ),
    "eligible-company-excluded": (
        lambda r, s: s["reasons"].update(ZZSKIP=TOKEN_HIT),
        "token exclusions",
    ),
    "file-hit-line-dropped": (lambda r, s: s["hits"].pop("ZZDATA"), "token exclusions"),
    "used-company-omitted": (  # from both inventories, the universe recomputed around it
        lambda r, s: [s["reasons"].pop("ZZUSED"), s["hits"].pop("ZZUSED")],
        "historical exclusions",
    ),
    "file-hit-out-of-scope": (
        lambda r, s: s["hits"].update(ZZDATA="file data/holdout/attempt-1/x"),
        "hit files",
    ),
    "hit-object-without-token": (
        lambda r, s: s["hits"].update(ZZUSED=f"object {git(r, 'rev-parse', 'HEAD:src/app.py')}"),
        "hit objects",
    ),
    "hit-object-after-selection": (later_hit, "hit objects"),
    "skip-response-missing": (lambda r, s: s["responses"].pop("legacy"), "skip evidence"),
    "skip-response-failed": (
        lambda r, s: s["responses"].update(legacy={"status": 503, "body": []}),
        "skip evidence",
    ),
    # an HTTP-200 listing that is not the listing's own envelope is no inventory: it refuses
    # rather than skip (an empty list, as ``legacy`` above, is evidence)
    "skip-integrated-error-object": (
        lambda r, s: s["responses"].update(integrated=ok({"error": "x"})),
        "listing",
    ),
    "skip-integrated-bare-list": (lambda r, s: s["responses"].update(integrated=ok([])), "listing"),
    "skip-legacy-error-object": (
        lambda r, s: s["responses"].update(legacy=ok({"data": []})),
        "listing",
    ),
    "skip-row-not-an-object": (
        lambda r, s: s["responses"].update(integrated=ok({"data": ["row"]})),
        "listing",
    ),
    "skip-row-without-period": (
        lambda r, s: s["responses"].update(integrated=ok({"data": [{"symbol": "ZZSKIP"}]})),
        "listing",
    ),
    "skip-evidence-another-file": (
        lambda r, s: s.update(evidence=sha256(FRAME.encode())),
        "skip evidence",
    ),
    "skip-reason-not-reproduced": (lambda r, s: s.update(reason=BSE_NOT_ONE), "skip reason"),
    "token-hit-skip-unsupported": (
        lambda r, s: s.update(
            reason=TOKEN_HIT,
            responses={
                "integrated": ok(
                    {"data": [listing_row(e, T1, symbol="ZZSKIP") for e in (JUN, MAR)]}
                ),
                "legacy": ok([]),
                "bse": ok(bse("ZZSKIP", "INE000Z01052")),
            },
        ),
        "skip reason",
    ),
}


def test_draw_recomputes_exclusions_and_skips(repo: Path) -> None:
    """Each exclusion's reason and the skip's evidence-bound reason recompute (D1.2, D1.3)."""
    draw_check(repo, draw_state(repo))


@pytest.mark.parametrize("name", DRAW_MUTATIONS)
def test_draw_refuses_unsupported_exclusions_and_skips(repo: Path, name: str) -> None:
    """An unproven exclusion, or a skip whose response is missing, failed or unbound, refuses."""
    state = draw_state(repo)
    mutate, step = DRAW_MUTATIONS[name]
    mutate(repo, state)
    with pytest.raises(RefusedError) as refused:
        draw_check(repo, state)
    assert str(refused.value) == step


APAR_XBRL = Path(__file__).resolve().parents[2] / "data/raw/watchlist/aparinds/nse"
APAR_LATEST = {  # Apar's two latest integrated instances, by period end
    JUN: "INTEGRATED_FILING_INDAS_1701114_24072026063426_WEB.xml",
    MAR: "INTEGRATED_FILING_INDAS_1675395_28052026085114_WEB.xml",
}


XBRL_DEFECTS = {  # SYNTHETIC: case -> {period end: (old, new)}
    "declared": {},
    "no_phrase": {JUN: (b"Indian Accounting Standard", b"Zz Accounting Standard")},
    # discovery refuses on the older instance's financial signal before parsing either, so the
    # latest one's unreadable report nature (a parse failure) is never reached
    "paired": {
        JUN: (b">Consolidated</in-capmkt:NatureOf", b">Zz</in-capmkt:NatureOf"),
        MAR: (b"IntegratedFinance_IndAS", b"IntegratedFinance_ZZ"),
    },
}


@pytest.mark.retained
@pytest.mark.parametrize("case", XBRL_DEFECTS)
def test_draw_skips_a_candidate_discovery_would_refuse(repo: Path, case: str) -> None:
    """D1.3 amendment (eqos-h4h.10), attempt 3 on: a candidate whose two latest qualifying
    instances fail the XBRL prefilter (Apar's, with ingest's Ind AS phrase removed from the June
    one, or a non-financial signal missing from the March one) is skipped XBRL_NOT_ADMITTED, from
    its envelope and from retained bytes alike; the original instances reproduce no such skip."""
    private = (repo / "data/holdout/attempt-1").rename(repo / "data/holdout/attempt-3")
    bodies, rows = {}, []
    for end, name in APAR_LATEST.items():
        body = (APAR_XBRL / name).read_bytes()
        if end in XBRL_DEFECTS[case]:
            old, new = XBRL_DEFECTS[case][end]
            assert old in body
            body = body.replace(old, new)
        (private / name).write_bytes(body)
        bodies[f"x/{name}"] = body.decode()
        rows.append(listing_row(end, T1, symbol="ZZSKIP", xbrl=f"x/{name}"))
    (private / "listing.json").write_text(json.dumps({"data": rows}))
    state = draw_state(repo) | {"n": 3, "reason": NO_XBRL}
    state["responses"] |= {
        "integrated": ok({"data": rows}),
        "xbrl": ok(bodies),
        "bse": ok(bse("ZZSKIP", "INE000Z01052")),
    }
    if case == "declared":
        with pytest.raises(RefusedError, match="skip reason"):
            draw_check(repo, state)
    else:
        assert draw_check(repo, state).failed_rule("ZZSKIP") == NO_XBRL
