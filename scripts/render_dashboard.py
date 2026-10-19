"""Render docs/status/dashboard.html from live bd state, git history and docs/status/activity.json.

Run after every chunk of work:  uv run python scripts/render_dashboard.py
Stage statuses come from bd only; the architecture map below names which stages build each part.
"""

from __future__ import annotations

import html
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "status" / "dashboard.html"
ACTIVITY = ROOT / "docs" / "status" / "activity.json"

PHASES = [  # (label, epic id, name)
    ("D1a", "eqos-3f9", "Canonical comparison tracer"),
    ("D1b", "eqos-u0u", "Vendors, corroboration, queue"),
    ("D2", "eqos-01q", "Legacy store migration and cutover"),
    ("D3", "eqos-uqu", "Report ledger"),
    ("D4", "eqos-4hi", "Long-term memory"),
    ("D5", "eqos-tfb", "Generated views"),
    ("D6", "eqos-h4h", "Identifier-only onboarding"),
    ("D7", "eqos-3oq", "Coverage model"),
    ("D8", "eqos-17r", "Shareholding filing source — parked (owner 2026-10-17)"),
    ("D9", "eqos-4fc", "Retention and replay"),
]
# Pilot prerequisites are not all beads; their state is recorded here and updated by hand.
PREP = [
    ("PREP-1", "SEBI 2026 taxonomy mappings", "done"),
    ("PREP-2", "Workflow reads only PostgreSQL", "done"),
    ("PREP-3", "Resumable workflow states", "done"),
    ("PREP-4", "Source-of-truth matrix", "done"),
    ("PREP-5", "Rejected-claim rework path", "done"),
    ("PREP-6", "Review telemetry on ledger claims", "done"),
    ("PREP-7", "Frozen pilot manifest", "done"),
    ("PREP-8", "verify_project.sh", "done"),
]
# Architecture: (id, column, row, label, sublabel, stage refs). A ref is a phase label ("D3"),
# a stage ("D2.4"), "PREP-n", "pilot", or "built" (pre-roadmap foundation, already working).
NODES = [
    ("src_x", 0, 0, "Exchange filings", "NSE/BSE XBRL", ["built"]),
    ("src_p", 0, 1, "Results PDFs", "first-party documents", ["built"]),
    ("src_v", 0, 2, "Vendors", "Screener · Tijori · Upstox", ["built"]),
    ("src_l", 0, 4, "Legacy SQLite", "aparinds.sqlite, 43 rows", ["built"]),
    ("ingest", 1, 0, "Ingest & intake", "snapshots · provenance", ["built", "D1a"]),
    ("extract", 1, 1, "Extraction", "XBRL · PDF occurrences", ["built", "D1a", "PREP-1"]),
    ("vend", 1, 2, "Vendor ingest", "binding checks · pins", ["D1b"]),
    ("limport", 1, 4, "Legacy import", "preflight · approvals", ["D2.1", "D2.2"]),
    ("evidence", 2, 0, "Evidence store", "captures · readings", ["D1a"]),
    ("canon", 2, 1, "Canon", "dictionary · mappings v5", ["D1a", "PREP-1"]),
    ("queue", 2, 2, "Review queue & trust", "severity · traces", ["D1b"]),
    ("recon", 2, 4, "Reconcile & cutover", "state machine · rollback", ["D2.6"]),
    ("compare", 3, 0, "Comparison runs", "routing · replay", ["D1a", "D1b"]),
    ("admit", 3, 1, "Admission", "AGREE-only facts", ["D2.4"]),
    ("factstore", 3, 2, "PostgreSQL fact store", "FactStoreLike · FactRef", ["D2.3"]),
    ("backup", 3, 3, "Backup / restore", "matched sets · replay", ["D2.5"]),
    ("accept", 3, 4, "Stage 2 acceptance", "frozen manifest · e2e", ["D2.7", "D2.8"]),
    ("report", 4, 0, "Earnings report", "tax · ETR · headline PBT", ["built", "D2.4"]),
    ("ledger", 4, 1, "Report ledger", "versions · claims", ["D3"]),
    ("memory", 4, 2, "Long-term memory", "promotion · supersession", ["D4"]),
    ("views", 4, 3, "Generated views", "read-only", ["D5"]),
    ("onboard", 5, 0, "Onboarding", "by identifier alone", ["D6"]),
    ("coverage", 5, 1, "Coverage", "universe · watchlist", ["D7"]),
    ("share", 5, 2, "Shareholding", "filing source", ["D8"]),
    ("retain", 5, 3, "Retention & replay", "purge · replay", ["D9"]),
    ("prep", 6, 1, "Pilot prerequisites", "workflow · manifest", [p[0] for p in PREP[1:]]),
    ("pilot", 6, 2, "Apar pilot", "PQ0–PQ3 on PostgreSQL", ["pilot"]),
]
EDGES = [
    ("src_x", "ingest"),
    ("src_p", "extract"),
    ("src_v", "vend"),
    ("src_l", "limport"),
    ("ingest", "evidence"),
    ("extract", "evidence"),
    ("extract", "canon"),
    ("vend", "queue"),
    ("evidence", "compare"),
    ("canon", "compare"),
    ("queue", "compare"),
    ("queue", "admit"),
    ("limport", "recon"),
    ("recon", "factstore"),
    ("recon", "accept"),
    ("compare", "admit"),
    ("admit", "factstore"),
    ("factstore", "backup"),
    ("backup", "accept"),
    ("evidence", "backup"),
    ("compare", "report"),
    ("factstore", "report"),
    ("factstore", "ledger"),
    ("report", "ledger"),
    ("ledger", "memory"),
    ("ledger", "views"),
    ("onboard", "coverage"),
    ("share", "coverage"),
    ("memory", "retain"),
    ("ledger", "retain"),
    ("coverage", "prep"),
    ("retain", "prep"),
    ("prep", "pilot"),
]
STAGE_TITLE = re.compile(r"^\[(D\d[ab]?)\.(\d+)\]\s*(.*)$")
COL_W, ROW_H, NODE_W, NODE_H, PAD_X, PAD_Y, ROWS = 214, 100, 172, 70, 16, 40, 5


def sh(*args: str) -> str:
    """Run a command in the repo and return stdout."""
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True, check=True).stdout


def load_stages() -> tuple[dict[str, list[dict[str, str]]], list[dict[str, str]], dict[str, str]]:
    """Roadmap stages per phase, all issues, and the pilot bead status, from bd."""
    issues = json.loads(sh("bd", "list", "--all", "--json", "--limit", "0"))
    stages: dict[str, list[dict[str, str]]] = {label: [] for label, _, _ in PHASES}
    for issue in issues:
        match = STAGE_TITLE.match(issue["title"])
        if match and match.group(1) in stages:
            stages[match.group(1)].append(
                {
                    "key": f"{match.group(1)}.{match.group(2)}",
                    "id": issue["id"],
                    "title": match.group(3),
                    "status": issue["status"],
                }
            )
    for rows in stages.values():
        rows.sort(key=lambda row: int(row["key"].split(".")[1]))
    pilot = next((i["status"] for i in issues if i["id"] == "eqos-4j2.8"), "open")
    return stages, issues, {"pilot": pilot}


def state_of(statuses: list[str]) -> str:
    """Fold bd statuses into done / active / todo."""
    if statuses and all(s == "closed" for s in statuses):
        return "done"
    if any(s in ("closed", "in_progress") for s in statuses):
        return "active"
    return "todo"


def node_state(
    refs: list[str], stages: dict[str, list[dict[str, str]]], extra: dict[str, str]
) -> str:
    """Status of one architecture part from the stages that build it."""
    prep = {key: state for key, _, state in PREP}
    statuses: list[str] = []
    for ref in refs:
        if ref == "built":
            statuses.append("closed")
        elif ref in stages:
            statuses += [row["status"] for row in stages[ref]]
        elif ref in prep:
            statuses.append({"done": "closed", "active": "in_progress"}.get(prep[ref], "open"))
        elif ref == "pilot":
            statuses.append(extra["pilot"])
        else:
            phase = ref.split(".")[0]
            statuses += [row["status"] for row in stages.get(phase, []) if row["key"] == ref]
    return state_of(statuses)


def edge_path(x1: float, y1: float, x2: float, y2: float) -> str:
    """A curve between two boxes that never crosses a box in between."""
    if x2 > x1:  # next column(s): right edge to left edge
        sx, sy, ex, ey = x1 + NODE_W, y1 + NODE_H / 2, x2, y2 + NODE_H / 2
        mid = (sx + ex) / 2
        return f"M{sx},{sy} C{mid},{sy} {mid},{ey} {ex},{ey}"
    cx = x1 + NODE_W / 2
    if abs(y2 - y1) == ROW_H:  # adjacent rows: straight drop or rise
        sy, ey = (y1 + NODE_H, y2) if y2 > y1 else (y1, y2 + NODE_H)
        return f"M{cx},{sy} L{cx},{ey}"
    sx, sy, ey = x1 + NODE_W, y1 + NODE_H / 2, y2 + NODE_H / 2  # skip rows: bulge right
    return f"M{sx},{sy} C{sx + 18},{sy} {sx + 18},{ey} {sx},{ey}"


def svg_diagram(states: dict[str, str]) -> str:
    """The architecture map: nodes coloured by state, edges flowing into active work."""
    pos = {n[0]: (PAD_X + n[1] * COL_W, PAD_Y + n[2] * ROW_H) for n in NODES}
    heads = [
        "Sources",
        "Acquire",
        "Evidence & canon",
        "Compare & store",
        "Outputs",
        "Later core",
        "Pilot",
    ]
    parts = [
        f'<text class="colhead" x="{PAD_X + i * COL_W + NODE_W / 2}" y="22">{h}</text>'
        for i, h in enumerate(heads)
    ]
    for a, b in EDGES:
        (x1, y1), (x2, y2) = pos[a], pos[b]
        d = edge_path(x1, y1, x2, y2)
        cls = "edge-" + (
            "flow" if states[b] == "active" else "done" if states[b] == "done" else "todo"
        )
        parts.append(f'<path class="edge {cls}" d="{d}"/>')
    for nid, _, _, label, sub, refs in NODES:
        x, y = pos[nid]
        st = states[nid]
        shown = [r for r in refs if r != "built"]
        tag = ", ".join(shown) if len(shown) < 4 else f"{shown[0]} … {shown[-1]}"
        tag = tag or "foundation"
        parts.append(
            f'<g class="node node-{st}" transform="translate({x},{y})">'
            f"<title>{html.escape(label)}: {st} ({html.escape(tag)})</title>"
            f'<rect class="ring" x="-4" y="-4" width="{NODE_W + 8}" height="{NODE_H + 8}" rx="12"/>'
            f'<rect class="box" width="{NODE_W}" height="{NODE_H}" rx="9"/>'
            f'<circle class="dot" cx="{NODE_W - 13}" cy="13" r="4.5"/>'
            f'<text class="nl" x="10" y="24">{html.escape(label)}</text>'
            f'<text class="ns" x="10" y="42">{html.escape(sub)}</text>'
            f'<text class="nt" x="10" y="59">{html.escape(tag)}</text></g>'
        )
    width = PAD_X * 2 + 6 * COL_W + NODE_W
    height = PAD_Y + ROWS * ROW_H
    return (
        f'<svg viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="Architecture map coloured by build status">{"".join(parts)}</svg>'
    )


def css(status: str) -> str:
    """Map one bd status to its done / active / todo class."""
    return {"closed": "done", "in_progress": "active"}.get(status, "todo")


def phase_row(label: str, name: str, rows: list[tuple[str, str, str]], note: str = "") -> str:
    """A collapsible phase line; rows are (key, title, state class)."""
    done = sum(st == "done" for _, _, st in rows)
    overall = (
        "done"
        if done == len(rows)
        else "active"
        if done or any(st == "active" for _, _, st in rows)
        else "todo"
    )
    cells = "".join(
        f'<span class="cell c-{st}" title="{k} {html.escape(t)} ({st})">{k.split(".")[-1]}</span>'
        for k, t, st in rows
    )
    items = "".join(
        f'<li><span class="pill p-{st}">{st}</span> <b>{k}</b> {html.escape(t)}</li>'
        for k, t, st in rows
    )
    return (
        f'<details class="phase ph-{overall}"><summary><span class="plabel">{label}</span>'
        f'<span class="pname">{html.escape(name)}</span><span class="cells">{cells}</span>'
        f'<span class="pcount">{done}/{len(rows)}</span></summary><ul>{items}</ul>{note}</details>'
    )


def phase_rows(stages: dict[str, list[dict[str, str]]]) -> str:
    """One row per core phase plus the pilot prerequisites."""
    out = [
        phase_row(
            label,
            name,
            [(r["key"], r["title"], css(r["status"])) for r in stages[label]],
            f'<p class="muted">bd epic {epic}</p>',
        )
        for label, epic, name in PHASES
    ]
    prep = [(k.replace("PREP-", "PREP."), n, st) for k, n, st in PREP]
    out.append(phase_row("PREP", "Pilot prerequisites", prep))
    return "".join(out)


def render() -> str:
    """Build the full page."""
    stages, issues, extra = load_stages()
    activity = json.loads(ACTIVITY.read_text(encoding="utf-8"))
    states = {n[0]: node_state(n[5], stages, extra) for n in NODES}
    all_rows = [r for rows in stages.values() for r in rows]
    built = sum(r["status"] == "closed" for r in all_rows)
    current = next(
        (
            label
            for label, _, _ in PHASES
            if state_of([r["status"] for r in stages[label]]) != "done"
        ),
        "—",
    )
    cur_rows = stages.get(current, [])
    cur_done = sum(r["status"] == "closed" for r in cur_rows)
    bugs = [
        i for i in issues if i["status"] in ("open", "in_progress") and i["issue_type"] == "bug"
    ]
    p1 = [i for i in bugs if i["priority"] <= 1]
    commits = sh("git", "log", "--oneline", "-10").strip().splitlines()
    now = activity["now"]
    log = "".join(
        f'<li><span class="muted tab">{html.escape(e["date"])}</span> {html.escape(e["text"])}</li>'
        for e in activity["log"]
    )
    nxt = "".join(f"<li>{html.escape(t)}</li>" for t in activity["next"])
    bug_rows = "".join(
        f'<li><span class="pill p-{"high" if i["priority"] <= 1 else "todo"}">'
        f"P{i['priority']}</span> "
        f"<b>{i['id']}</b> {html.escape(i['title'])}</li>"
        for i in sorted(bugs, key=lambda i: i["priority"])
    )
    commit_rows = "".join(
        f"<li><code>{html.escape(c[:7])}</code> {html.escape(c[8:])}</li>" for c in commits
    )
    stamp = datetime.now(UTC).astimezone().strftime("%Y-%m-%d %H:%M %Z")
    return TEMPLATE.format(
        stamp=stamp,
        built=built,
        total=len(all_rows),
        current=current,
        cur_done=cur_done,
        cur_total=len(cur_rows),
        bugs=len(bugs),
        p1=len(p1),
        now_title=html.escape(now["title"]),
        now_detail=html.escape(now["detail"]),
        diagram=svg_diagram(states),
        phases=phase_rows(stages),
        log=log,
        next=nxt,
        bug_rows=bug_rows,
        commit_rows=commit_rows,
        pct=round(100 * built / max(len(all_rows), 1)),
        prep_done=sum(st == "done" for _, _, st in PREP),
        prep_total=len(PREP),
    )


TEMPLATE = (ROOT / "scripts" / "dashboard_template.html").read_text(encoding="utf-8")

if __name__ == "__main__":
    OUT.write_text(render(), encoding="utf-8")
    print(OUT.relative_to(ROOT))
