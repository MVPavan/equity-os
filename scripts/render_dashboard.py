"""Render docs/status/dashboard.html from live bd state, git history and docs/status/activity.json.

Run after every chunk of work:  uv run python scripts/render_dashboard.py
Every drawn element takes its state from STATUS (bd refs plus the hand-kept HAND table) and BUGS.
Rendering asserts that no boxes, arrows or labels collide and that every text line fits its box.
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
    ("D8", "eqos-17r", "Shareholding filing source — resumed (owner 2026-10-20)"),
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
# Hand states where bd has no record, in bd's vocabulary plus "paused". Updated by hand.
HAND = {
    "built": ("closed", "Pre-roadmap foundation (Phase 0A / 0.5), working before D1a"),
    # VENDOR-1 (epic eqos-awnc) tracks tasks in docs/plans/VENDOR-1-P1.md, not as beads. States
    # as of 2026-11-07 per the orchestrator and git log (code approved by Sol at 87be969e).
    "V1.T1": ("closed", "Migration 0047 and the vendor-first contracts"),
    "V1.T2": ("closed", "Tijori display rules, shared fixture, vendor reingest"),
    "V1.T3": ("closed", "Mapping set v9: inventory and standalone entries"),
    "V1.T4": ("closed", "Standalone-only onboarding"),
    "V1.T5": ("closed", "Vendor-only runs, run status, default vendor sides"),
    "V1.T6": ("closed", "Policy, predicates and run pins"),
    "V1.T7": ("closed", "Check class, eligibility artifact, vendor measure"),
    "V1.T8": ("closed", "One admission path"),
    "V1.T9": ("closed", "Citation, retention, report values and labels"),
    "V1.T10": ("closed", "Fallback workflow"),
    "V1.T11": ("closed", "Document amendments"),
    "V1.T12": ("in_progress", "Pre-live gate (rails fixed, eqos-ju19; rerun pending)"),
    "V1.T13": ("open", "Live: migrate, re-interpret, re-ingest Apar"),
    "V1.T14": ("open", "Apar re-measurement"),
    # docs/specs/2026-11-06-vendor-first.md §3 and §7–§9.
    "V1.P2": ("in_progress", "VENDOR-1 Phase 2: vendor text (concall summaries, numeral rule)"),
    "V1.P3": ("in_progress", "VENDOR-1 Phase 3: banks (ICICIBANK)"),
    "FIVE": ("open", "Five-company test: APARINDS, ICICIBANK, LAURUSLABS, MTARTECH, NETWEB"),
    # bd eqos-msq notes: daily intake paused at the owner's request, 2026-11-05.
    "INTAKE": ("paused", "Daily document intake, paused by the owner 2026-11-05"),
    # config/sourcing/sources.yaml: the online category is listed as planned, no code.
    "ONLINE": ("open", "Online sources, planned in config/sourcing/sources.yaml"),
    # activity.json 2026-11-03: RESEARCH-3 built `ledger narrate`; it closed with its goal unmet.
    "R3": ("closed", "RESEARCH-3: ledger narrate built"),
}
V1_TASKS = [k for k in HAND if k.startswith("V1.T")]

# THE status table: element -> refs. A ref is a phase ("D3") or stage ("D2.4") label, a bd id
# (an epic also counts its children "id.N"), a PREP key or a HAND key. No refs: not started.
STATUS = {
    "interface/commands": ["built", "V1.T5", "V1.T7", "V1.T10"],
    "interface/entry": ["built", "V1.T9"],
    "interface/workflows": ["built"],
    "repo/tests & gate": ["PREP-8"],
    "exchanges/NSE/BSE XBRL": ["built", "D8"],
    "exchanges/Results PDFs": ["built"],
    "exchanges/Announcements": ["eqos-msq", "INTAKE"],
    "vendors/Screener": ["D1b", "V1.T2"],
    "vendors/Tijori": ["D1b", "V1.T2"],
    "vendors/Upstox": ["D1b"],
    "local/Legacy SQLite": ["D2"],
    "local/config/": ["built", "V1.T2", "V1.T3", "V1.T6"],
    "sourcing/documents": ["eqos-msq", "INTAKE"],
    "sourcing/exchange": ["built", "D8", "V1.T4", "V1.T10"],
    "sourcing/news": ["eqos-8kh"],
    "sourcing/online": ["ONLINE"],
    "sourcing/surfaces": ["eqos-aa6"],
    "sourcing/transport": ["built"],
    "sourcing/vendors": ["D1b"],
    "extraction/guidance": ["built"],
    "extraction/model": ["eqos-aa6"],
    "extraction/news": ["eqos-8kh"],
    "extraction/packages": ["built", "D1a", "D8", "V1.T4"],
    "extraction/results_pdf": ["built", "eqos-os3"],
    "extraction/surfaces": ["eqos-aa6"],
    "extraction/vendors": ["D1b", "V1.T2"],
    "extraction/xbrl": ["built", "D1a", "D8"],
    "normalisation/derivation": ["built"],
    "normalisation/dictionary": ["D1a"],
    "normalisation/mapping": ["D1a", "V1.T3"],
    "verification/admission": ["D2.4", "V1.T6", "V1.T7", "V1.T8", "V1.T10", "V1.T14"],
    "verification/comparison": ["D1a", "D1b", "V1.T5", "V1.T6"],
    "verification/diagnostics": ["D1b"],
    "verification/review_queue": ["D1b"],
    "storage/backup": ["D2.5", "D9"],
    "storage/database": ["D2", "D5", "V1.T1", "V1.T13"],
    "storage/facts": ["D2"],
    "storage/memory": ["D4"],
    "storage/raw_files": ["D1a", "D9"],
    "storage/records": ["D1a", "D3"],
    "storage/retention": ["D9", "V1.T9"],
    "storage/search": [],
    "system of record/PostgreSQL": ["D2", "V1.T13"],
    "analysis/calculations": ["built", "V1.T9"],
    "analysis/lenses": ["built", "eqos-3v3w"],
    "analysis/thesis_models": ["eqos-d1v", "V1.T9"],
    "publication/approval": ["D3"],
    "publication/checking": ["D3", "V1.T9"],
    "publication/drafting": ["D3", "V1.T9"],
    "publication/export": ["D3", "V1.T9"],
    "publication/narration": ["R3"],
    "publication/revision": ["D3", "PREP-5"],
    "companies/identity": ["built", "D6"],
    "companies/onboarding": ["D6", "V1.T4"],
    "coverage/screens": ["D7", "eqos-351"],
    "coverage/universe": ["D7"],
    "coverage/watchlist": ["D7"],
    "contracts/companies": ["D6"],
    "contracts/measurement": ["built", "V1.T6"],
    "contracts/publication": ["D3"],
    "contracts/sourcing": ["built", "V1.T4"],
    "contracts/storage": ["D4", "D9"],
    "contracts/verification": ["V1.T1"],
    # data flow (open bugs show on the block diagram only)
    "flow/onboard": ["D6", "V1.T4"],
    "flow/coverage": ["D7"],
    "flow/config": ["built", "V1.T2", "V1.T3", "V1.T6"],
    "flow/queue": ["D1b"],
    "flow/elig": ["V1.T7", "V1.T14"],
    "flow/capture": ["D1b", "eqos-aa6"],
    "flow/vext": ["D1b", "V1.T2"],
    "flow/mapping": ["D1a", "V1.T3"],
    "flow/compare": ["D1a", "D1b", "V1.T5", "V1.T6"],
    "flow/admit": ["D2.4", "V1.T8", "V1.T14"],
    "flow/lab1": ["V1.T8", "V1.T9", "V1.T14"],
    "flow/lab2": ["V1.T8", "V1.T9", "V1.T14"],
    "flow/filings": ["built", "V1.T10"],
    "flow/fext": ["built", "D1a"],
    "flow/legacy": ["D2"],
    "flow/fallback": ["V1.T10"],
    "flow/facts": ["D2", "V1.T8", "V1.T9"],
    "flow/calc": ["built", "V1.T9"],
    "flow/draft": ["D3", "V1.T9"],
    "flow/cite": ["D3", "V1.T9"],
    "flow/seal": ["D3"],
    "flow/ledger": ["D3"],
    "flow/export": ["D3", "V1.T9"],
    "flow/retain": ["D2.5", "D9", "V1.T9"],
    "flow/intake": ["INTAKE"],
    "flow/p2": ["V1.P2"],
    "flow/p3": ["V1.P3"],
    "flow/five": ["FIVE"],
}
# Open bug beads -> the block they break (bd, 2026-11-06). Test flakes go to the test block,
# never to a product block. An open bug missing here is listed on the page as unmapped.
BUGS = {
    "eqos-3ndm": "sourcing/documents",
    "eqos-tmof": "sourcing/documents",
    "eqos-shv": "sourcing/exchange",
    "eqos-n21": "extraction/results_pdf",
    "eqos-dol": "extraction/results_pdf",
    "eqos-ghv": "extraction/results_pdf",
    "eqos-djv": "normalisation/mapping",
    "eqos-wrv": "storage/raw_files",
    "eqos-j0z": "storage/raw_files",
    "eqos-pds3": "analysis/thesis_models",
    "eqos-sbe9": "publication/checking",
    "eqos-h4h.8": "companies/onboarding",
    "eqos-e4w": "coverage/screens",
    "eqos-ya8": "coverage/screens",
    "eqos-7d3a": "interface/workflows",
    **{b: "repo/tests & gate" for b in ("eqos-1kq", "eqos-7fa", "eqos-hdz", "eqos-til1")},
    **{b: "repo/tests & gate" for b in ("eqos-bs1b", "eqos-j8dq")},
}
# Block diagram. "= band", "+ bucket | role | columns", then "name | line 1 | line 2" per block;
# a block's STATUS key is "bucket/name".
LAYOUT = """
= Interface — on top
+ interface | CLI entry, workflows | 3
commands | CLI commands | grouped by bucket
entry | eqos · eqos-operator | parser · composition
workflows | pipeline · goal | runner · reports
+ repo | tooling | 1
tests & gate | pytest suites | verify.sh gate
= External sources
+ exchanges | first-party | 3
NSE/BSE XBRL | Ind AS instances | shareholding filings
Results PDFs | first-party results | OCR lane for scans
Announcements | exchange documents | transcripts · ARs
+ vendors | main for numbers | 3
Screener | HTML tables | main source (V1)
Tijori | JSON islands | main source (V1)
Upstox | instruments · prices | diagnostic only
+ local | inputs | 2
Legacy SQLite | aparinds.sqlite | imported once (D2)
config/ | versioned YAML | dict · maps · policy
= Intake
+ sourcing | fetch and retain | 4
documents | first-party docs | kept, not read
exchange | NSE XBRL · BSE PDFs | results_filing (T10)
news | announcements · | ET Markets RSS
online | web · regulators | reserved, planned
surfaces | raw-first vendor | surface capture
transport | shared polite | HTTP session
vendors | Screener · Tijori | Upstox fetchers
+ extraction | captures to occurrences | 4
guidance | management guidance | ranges, rule-based
model | model proposes | labels; code maps
news | issuer match · | event classes
packages | results packages | member ingest
results_pdf | PDF → occurrences | units · OCR lane
surfaces | vendor surface | parsers · cells
vendors | Screener · Tijori | Upstox readers
xbrl | XBRL → occurrences | taxonomy · dims
= Meaning
+ normalisation | occurrences to keys | 3
derivation | formulas · Q4=FY−9M | TTM · intervals
dictionary | canonical rows | versioned formulas
mapping | occurrences → keys | mapping set v9
+ verification | compare, admit, triage | 4
admission | one admission path | labels · eligibility
comparison | comparison runs | T1 · filing state
diagnostics | Lane B · gold file | log, never decide
review_queue | triage mismatches | trust as a view
= Storage
+ storage | durable state | 4
backup | matched backup | restore · replay
database | PostgreSQL pool | migrations → 0047
facts | fact stores | import · cutover
memory | long-term memory | retrieval at cutoff
raw_files | retained captures | sealed, no-clobber
records | append-only rows | evidence · ledger
retention | holds · purge | witness captures
search | search over records | reserved, later
+ system of record | | 1
PostgreSQL | eqos schema | migrations 0001–0047
= Analysis and publication
+ analysis | numbers by code | 3
calculations | computed values | stored traces
lenses | one question each | forward (RESEARCH-4)
thesis_models | two model drafts | code cross-checks
+ publication | report ledger | 3
approval | submit · panel | owner claim review
checking | citations · claims | numeral scans
drafting | earnings update | claims with labels
export | narrative export | status notes
narration | ledger narrate | evidence bundle
revision | rework · imports | earlier reports
= Company and coverage scope
+ companies | who the issuer is | 2
identity | entity map | Upstox catalog
onboarding | one NSE symbol | standalone-only (V1)
+ coverage | which companies | 3
screens | owner screens | Screener · Tijori
universe | universe registry | Upstox capture
watchlist | watchlist config | loader in entry
= Contracts — shared base
+ contracts | shared types every bucket imports | 6
companies | identity models | statement bases
measurement | observations · facts | provenance · keys
publication | ledger models | versions · claims
sourcing | source catalog | captures
storage | memory, retention | vocabulary
verification | comparison · trust | vendor-first enums
"""
# Data flow nodes: "id | column row | title | line 1 | line 2" (STATUS key "flow/id").
FLOW_NODES = """
onboard | 0 0 | Onboarding | one NSE symbol; basis | status from listings
coverage | 1 0 | Coverage | universe · watchlist · | owner screens
config | 2 0 | config/ YAML | dictionary · mapping v9 | vendor-first policy
queue | 3 0 | Review queue | mismatches · HIGH items | dispositions · trust
elig | 5 0 | Eligibility | check class; one | counterexample blocks
capture | 0 1 | Capture | Screener + Tijori | retained raw captures
vext | 1 1 | Vendor extraction | captures → occurrences | Tijori display rules
mapping | 2 1 | Mapping | occurrences → | interpretations
compare | 3 1 | 3-way comparison | Screener, Tijori, filing | T1 + filing state
admit | 4 1 | Admission | one path, rows 0a–6 | vendor value first
lab1 | 5 1 | Label A | “checked against | filing”
filings | 0 2 | Exchange filings | results XBRL + PDF | fallback only
fext | 1 2 | Filing extraction | XBRL · results PDF | → occurrences
legacy | 3 2 | Legacy SQLite | imported once (D2) | cutover done
fallback | 4 2 | Fallback workflow | compare fallback --run | acquire, ingest, rerun
lab2 | 5 2 | Label B | “vendors agree, not | checked against filing”
ledger | 0 3 | Report ledger | versions · claims | append-only
seal | 1 3 | Sealing | submit · panel · | owner approval
cite | 2 3 | Citation check | both witnesses kept | claim check · anchors
draft | 3 3 | Draft | earnings update | claims carry labels
calc | 4 3 | Calculations | admitted operands | weakest input label
facts | 5 3 | Fact store | PostgreSQL · selection | read_selected + label
export | 0 4 | Export | narrative + status | note (source notes)
intake | 1 4 | Document intake | daily pass over | announcements
p2 | 2 4 | Vendor text (P2) | concall summaries | as cited vendor text
p3 | 3 4 | Banks (P3) | ICICIBANK route | standalone basis
five | 4 4 | Five-company test | 5 issuers incl. | ICICIBANK, NETWEB
retain | 5 4 | Retention | witness captures held | replay · backup
"""
# Edges: "from > to | route | label; lines | side". An empty route joins neighbours straight;
# otherwise points are ports ("R"/"L" node dy, "T"/"B" node dx) or corners ("c" x-node dx
# y-node dy, offsets from node centres). Side: "l"/"r" of a vertical run, "b" below a
# horizontal run, empty for above and below.
FLOW_EDGES = """
coverage > onboard | | which; companies |
onboard > capture | | issuer, basis status | r
config > mapping | | mapping set v9 | r
capture > vext | | vendor; captures |
vext > mapping | | occurrences |
mapping > compare | | interpretations |
compare > admit | | T1 + filing; state |
compare > queue | | mismatches | r
queue > admit | R queue 0, c admit -30 queue 0, T admit -30 | open HIGH: 0a |
elig > admit | L elig 0, c admit 30 elig 0, T admit 30 | eligible class |
admit > lab1 | R admit -14, L lab1 -14 | rows 1, 2, 5 |
admit > lab2 | R admit 18, c admit 108 admit 18, c admit 108 lab2 0, L lab2 0 | row 3 |
admit > fallback | | refused rows; 4 and 6 trigger | l
fallback > filings | B fallback 0, c fallback 0 fallback 50, c filings 0 fallback 50, B filings 0 \
| acquire one period's filing | b
filings > fext | | first-party; package |
fext > mapping | R fext 0, c mapping 0 fext 0, B mapping 0 | XBRL + PDF |
legacy > facts | B legacy 0, c legacy 0 legacy 68, c facts -40 legacy 68, T facts -40 | |
lab1 > facts | R lab1 0, c lab1 98 lab1 0, c lab1 98 facts -14, R facts -14 | |
lab2 > facts | | |
facts > calc | | selected; + label |
calc > draft | | computed; values |
draft > cite | | claims |
cite > seal | | cited; claims |
seal > ledger | | sealed; version |
ledger > export | | status note | r
facts > retain | | holds witnesses | l
"""
STATES = {  # class -> legend text
    "done": "done",
    "active": "in progress",
    "planned": "planned",
    "none": "not started",
    "broken": "broken (open bug)",
    "paused": "paused by owner",
}
STAGE_TITLE = re.compile(r"^\[(D\d[ab]?)\.(\d+)\]\s*(.*)$")
BW, BH, GAP, PAD, HEAD = 128, 64, 10, 10, 26  # block diagram: block, gaps, container header
NW, NH, COLW, ROWH, FX, FY = 150, 64, 232, 124, 20, 24  # data flow: node, grid cell, origin
Box = tuple[float, float, float, float]
Ctx = dict[str, dict[str, str] | dict[str, list[str]]]


def rows(table: str) -> list[list[str]]:
    """The non-empty lines of a text table, split on '|'."""
    return [[c.strip() for c in ln.split("|")] for ln in table.strip().splitlines()]


def sh(*args: str) -> str:
    """Run a command in the repo and return stdout."""
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True, check=True).stdout


def load() -> tuple[dict[str, list[dict[str, str]]], list[dict[str, object]]]:
    """Roadmap stages per phase and all issues, from bd."""
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
    for stage_rows in stages.values():
        stage_rows.sort(key=lambda row: int(row["key"].split(".")[1]))
    return stages, issues


def resolve(ref: str, stages: dict[str, list[dict[str, str]]], status: dict[str, str]) -> list[str]:
    """The bd-style statuses behind one ref."""
    prep = {key: state for key, _, state in PREP}
    if ref in HAND:
        return [HAND[ref][0]]
    if ref in prep:
        return ["closed" if prep[ref] == "done" else "open"]
    phase = ref.split(".")[0]
    if phase in stages:
        return [r["status"] for r in stages[phase] if ref in (phase, r["key"])]
    found = [s for i, s in status.items() if i == ref or i.startswith(ref + ".")]
    assert found, f"unknown ref {ref}"
    return found


def fold(statuses: list[str], broken: bool) -> str:
    """Fold statuses into one of STATES."""
    if broken:
        return "broken"
    if not statuses:
        return "none"
    if "paused" in statuses:
        return "paused"
    if all(s == "closed" for s in statuses):
        return "done"
    if any(s in ("closed", "in_progress") for s in statuses):
        return "active"
    return "planned"


def text_w(text: str, size: float, kind: str = "") -> float:
    """A conservative width estimate for one line of SVG text."""
    return len(text) * size * {"b": 0.6, "m": 0.61}.get(kind, 0.54)


def overlap(a: Box, b: Box) -> bool:
    """True when two boxes (x, y, w, h) intersect."""
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def assert_apart(boxes: dict[str, Box], what: str) -> None:
    """Fail loud when any two boxes collide."""
    items = list(boxes.items())
    for i, (na, a) in enumerate(items):
        for nb, b in items[i + 1 :]:
            assert not overlap(a, b), f"{what}: {na} overlaps {nb}"


def box(key: str, x: float, y: float, w: float, title: str, lines: list[str], ctx: Ctx) -> str:
    """One status-coloured box: title, two lines, and its refs or open bugs."""
    st, refs, bugs = ctx["state"][key], STATUS[key], ctx["bugs"].get(key, [])
    shown = [b.removeprefix("eqos-") for b in bugs] or [r for r in refs if r != "built"]
    tag = ("bug " if bugs else "") + " ".join(shown)
    if text_w(tag, 9, "m") > w - 16:
        tag = ("bug " if bugs else "") + f"{shown[0]} +{len(shown) - 1}"
    tag = tag or ("foundation" if refs else "nothing planned")
    for text, size, kind in [(title, 12, "b"), *[(t, 10, "") for t in lines], (tag, 9, "m")]:
        assert text_w(text, size, kind) <= w - 16, f"text too wide in {key}: {text}"
    tip = f"{title}: {STATES[st]} · refs {', '.join(refs) or 'none'}"
    tip += f" · open bugs {', '.join(bugs)}" if bugs else ""
    body = "".join(
        f'<text class="ns" x="9" y="{32 + 12 * i}">{html.escape(t)}</text>'
        for i, t in enumerate(lines)
    )
    return (
        f'<g class="node node-{st}" transform="translate({x},{y})">'
        f"<title>{html.escape(tip)}</title>"
        f'<rect class="ring" x="-3" y="-3" width="{w + 6}" height="{BH + 6}" rx="10"/>'
        f'<rect class="box" width="{w}" height="{BH}" rx="8"/>'
        f'<circle class="dot" cx="{w - 11}" cy="12" r="4"/>'
        f'<text class="nl" x="9" y="17">{html.escape(title)}</text>{body}'
        f'<text class="nt" x="9" y="{BH - 7}">{html.escape(tag)}</text></g>'
    )


def layout() -> list[tuple[str, list[tuple[str, str, int, list[list[str]]]]]]:
    """LAYOUT parsed into bands of (bucket, role, columns, blocks)."""
    bands: list[tuple[str, list[tuple[str, str, int, list[list[str]]]]]] = []
    for row in rows(LAYOUT):
        if row[0].startswith("="):
            bands.append((row[0][1:].strip(), []))
        elif row[0].startswith("+"):
            bands[-1][1].append((row[0][1:].strip(), row[1], int(row[2]), []))
        else:
            bands[-1][1][-1][3].append(row)
    return bands


def block_diagram(ctx: Ctx) -> str:
    """Every bucket as a container of its sub-packages, banded by layer."""
    parts, blocks, conts, y, width = [], {}, {}, 12.0, 0.0
    for band, containers in layout():
        parts.append(
            f'<text class="colhead" x="12" y="{y + 12}" style="text-anchor:start">'
            f"{html.escape(band)}</text>"
        )
        y, x, tallest = y + 20, 12.0, 0.0
        for name, role, cols, items in containers:
            cw = cols * BW + (cols - 1) * GAP + 2 * PAD
            ch = HEAD + -(-len(items) // cols) * (BH + GAP) + PAD - GAP
            conts[name] = (x, y, cw, ch)
            head = name + (f" · {role}" if role else "")
            assert text_w(head, 12, "b") <= cw - 16, f"container head too wide: {head}"
            parts.append(
                f'<g class="cont"><rect x="{x}" y="{y}" width="{cw}" height="{ch}" rx="12"/>'
                f'<text class="ch" x="{x + 12}" y="{y + 18}"><tspan class="chb">'
                f"{html.escape(name)}</tspan>{html.escape(' · ' + role) if role else ''}</text></g>"
            )
            for i, (title, l1, l2) in enumerate(items):
                bx, by = x + PAD + (i % cols) * (BW + GAP), y + HEAD + (i // cols) * (BH + GAP)
                blocks[f"{name}/{title}"] = (bx, by, BW, BH)
                parts.append(box(f"{name}/{title}", bx, by, BW, title, [l1, l2], ctx))
            x, tallest = x + cw + 16, max(tallest, ch)
        width, y = max(width, x), y + tallest + 18
    assert_apart(blocks, "block diagram")
    assert_apart(conts, "block diagram containers")
    return (
        f'<svg viewBox="0 0 {width - 4} {y}" role="img" '
        f'aria-label="Package buckets and sub-packages coloured by build status">'
        f"{''.join(parts)}</svg>"
    )


def point(spec: list[str], pos: dict[str, Box]) -> tuple[float, float]:
    """One route point: a port on a node's edge, or a corner offset from node centres."""
    if spec[0] == "c":
        xn, dx, yn, dy = spec[1], float(spec[2]), spec[3], float(spec[4])
        return pos[xn][0] + NW / 2 + dx, pos[yn][1] + NH / 2 + dy
    x, y, off = pos[spec[1]][0], pos[spec[1]][1], float(spec[2])
    return {
        "R": (x + NW, y + NH / 2 + off),
        "L": (x, y + NH / 2 + off),
        "T": (x + NW / 2 + off, y),
        "B": (x + NW / 2 + off, y + NH),
    }[spec[0]]


def route_of(src: str, dst: str, spec: str, pos: dict[str, Box]) -> list[tuple[float, float]]:
    """An edge's points; with no route given, neighbours in a row or column join straight."""
    if spec:
        return [point(p.split(), pos) for p in spec.split(",")]
    a, b = pos[src], pos[dst]
    if a[1] == b[1]:
        fwd = b[0] > a[0]
        return [
            point(["R" if fwd else "L", src, "0"], pos),
            point(["L" if fwd else "R", dst, "0"], pos),
        ]
    down = b[1] > a[1]
    return [
        point(["B" if down else "T", src, "0"], pos),
        point(["T" if down else "B", dst, "0"], pos),
    ]


def edge_label(route: list[tuple[float, float]], text: list[str], side: str) -> tuple[Box, str]:
    """Label text on the edge's longest run, and the box it takes up."""
    segs = list(zip(route, route[1:], strict=False))
    p, q = max(segs, key=lambda s: abs(s[0][0] - s[1][0]) + abs(s[0][1] - s[1][1]))
    mx, my, w = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2, max(text_w(t, 10) for t in text)
    if p[1] == q[1]:  # horizontal run
        ys = [my + 14 + 12 * i for i in range(len(text))] if side == "b" else [my - 5, my + 13]
        x, anchor, left = mx, "middle", mx - w / 2
    else:
        ys = [my - 6 * (len(text) - 1) + 12 * i + 4 for i in range(len(text))]
        x, anchor, left = (mx - 6, "end", mx - 6 - w) if side == "l" else (mx + 6, "start", mx + 6)
    ys = ys[: len(text)]
    svg = "".join(
        f'<text class="el" x="{x}" y="{y}" text-anchor="{anchor}">{html.escape(t)}</text>'
        for t, y in zip(text, ys, strict=False)
    )
    return (left, ys[0] - 9, w, ys[-1] - ys[0] + 12), svg


def flow_diagram(ctx: Ctx) -> str:
    """How one number flows, capture to export, with the side flows."""
    nodes = rows(FLOW_NODES)
    pos: dict[str, Box] = {}
    for nid, cell, *_ in nodes:
        col, row = (int(v) for v in cell.split())
        pos[nid] = (FX + col * COLW, FY + row * ROWH, NW, NH)
    assert_apart(pos, "data flow")
    parts, labels = [], {}
    for ends, spec, text, side in rows(FLOW_EDGES):
        src, dst = (e.strip() for e in ends.split(">"))
        route = route_of(src, dst, spec, pos)
        for p, q in zip(route, route[1:], strict=False):
            seg = (
                min(p[0], q[0]),
                min(p[1], q[1]),
                abs(p[0] - q[0]) or 0.1,
                abs(p[1] - q[1]) or 0.1,
            )
            for nid, nb in pos.items():  # touching a box's edge is fine, entering it is not
                inner = (nb[0] + 0.5, nb[1] + 0.5, nb[2] - 1, nb[3] - 1)
                assert not overlap(seg, inner), f"edge {src}->{dst} crosses {nid}"
        st = ctx["state"][f"flow/{dst}"]
        d = "M" + " L".join(f"{x},{y}" for x, y in route)
        parts.append(f'<path class="edge edge-{st}" d="{d}" marker-end="url(#ah-{st})"/>')
        if text:
            labels[ends], svg = edge_label(route, [t.strip() for t in text.split(";")], side)
            parts.append(svg)
    for name, lb in labels.items():
        for nid, nb in pos.items():
            assert not overlap(lb, nb), f"label {name} hits {nid}"
    assert_apart(labels, "edge labels")
    for nid, _, title, l1, l2 in nodes:
        parts.append(box(f"flow/{nid}", pos[nid][0], pos[nid][1], NW, title, [l1, l2], ctx))
    parts.append(
        f'<text class="colhead" x="{FX + COLW}" y="{FY + 4 * ROWH - 12}" style="text-anchor:start">'
        "Off the number path today: paused intake, then the next phases</text>"
    )
    marks = "".join(
        f'<marker id="ah-{s}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        f'markerHeight="7" orient="auto"><path class="ah-{s}" d="M0,0 L10,5 L0,10 z"/></marker>'
        for s in STATES
    )
    width, height = FX + 5 * COLW + NW + 44, FY + 4 * ROWH + NH + 12
    return (
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Vendor-first data flow '
        f'coloured by build status"><defs>{marks}</defs>{"".join(parts)}</svg>'
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
    """One row per core phase, the pilot prerequisites and VENDOR-1 Phase 1."""
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
    v1 = [(k, HAND[k][1], css(HAND[k][0])) for k in V1_TASKS]
    note = '<p class="muted">bd epic eqos-awnc · tasks from docs/plans/VENDOR-1-P1.md</p>'
    out.append(phase_row("V1-P1", "VENDOR-1 Phase 1: vendor-first core", v1, note))
    return "".join(out)


def render() -> str:
    """Build the full page."""
    stages, issues = load()
    status = {str(i["id"]): str(i["status"]) for i in issues}
    bugs = [i for i in issues if i["status"] != "closed" and i["issue_type"] == "bug"]
    by_block: dict[str, list[str]] = {}
    for bug in bugs:
        by_block.setdefault(BUGS.get(str(bug["id"]), ""), []).append(str(bug["id"]))
    unmapped = by_block.pop("", [])
    assert set(by_block) <= set(STATUS), (
        f"bugs mapped to unknown blocks: {set(by_block) - set(STATUS)}"
    )
    state = {
        key: fold([s for r in refs for s in resolve(r, stages, status)], key in by_block)
        for key, refs in STATUS.items()
    }
    ctx: Ctx = {"state": state, "bugs": by_block}
    activity = json.loads(ACTIVITY.read_text(encoding="utf-8"))
    all_rows = [r for stage_rows in stages.values() for r in stage_rows]
    built = sum(r["status"] == "closed" for r in all_rows)
    tests = by_block.get("repo/tests & gate", [])
    p1 = [i for i in bugs if int(str(i["priority"])) <= 1]
    commits = sh("git", "log", "--oneline", "-10").strip().splitlines()
    now = activity["now"]
    esc = html.escape
    status_rows = "".join(
        f"<tr><td>{esc(key)}</td><td><code>{esc(', '.join(refs) or '—')}</code>"
        f"{' · bugs <code>' + esc(', '.join(by_block[key])) + '</code>' if key in by_block else ''}"
        f'</td><td><span class="pill p-{state[key]}">{STATES[state[key]]}</span></td></tr>'
        for key, refs in STATUS.items()
    )
    bug_rows = "".join(
        f'<li><span class="pill p-{"broken" if int(str(i["priority"])) <= 1 else "none"}">'
        f"P{i['priority']}</span> <b>{i['id']}</b> {esc(str(i['title']))} "
        f'<span class="muted">→ {esc(BUGS.get(str(i["id"]), "unmapped"))}</span></li>'
        for i in sorted(bugs, key=lambda i: int(str(i["priority"])))
    )
    return TEMPLATE.format(
        stamp=datetime.now(UTC).astimezone().strftime("%Y-%m-%d %H:%M %Z"),
        built=built,
        total=len(all_rows),
        pct=round(100 * built / max(len(all_rows), 1)),
        v1_done=sum(HAND[k][0] == "closed" for k in V1_TASKS),
        v1_total=len(V1_TASKS),
        prep_done=sum(st == "done" for _, _, st in PREP),
        prep_total=len(PREP),
        bugs=len(bugs),
        p1=len(p1),
        test_bugs=len(tests),
        now_title=esc(now["title"]),
        now_detail=esc(now["detail"]),
        legend="".join(f'<span style="--c:var(--{s})">{t}</span>' for s, t in STATES.items()),
        blocks=block_diagram(ctx),
        flow=flow_diagram(ctx),
        status_rows=status_rows,
        unmapped=esc(", ".join(unmapped) or "none"),
        phases=phase_rows(stages),
        log="".join(
            f'<li><span class="muted tab">{esc(e["date"])}</span> {esc(e["text"])}</li>'
            for e in activity["log"]
        ),
        next="".join(f"<li>{esc(t)}</li>" for t in activity["next"]),
        bug_rows=bug_rows,
        commit_rows="".join(f"<li><code>{esc(c[:7])}</code> {esc(c[8:])}</li>" for c in commits),
    )


TEMPLATE = (ROOT / "scripts" / "dashboard_template.html").read_text(encoding="utf-8")

if __name__ == "__main__":
    OUT.write_text(render(), encoding="utf-8")
    print(OUT.relative_to(ROOT))
