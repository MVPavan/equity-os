"""Stage 4 held-out record checks (plan D6 D1.1-D1.7).

Every check takes a repo path and reads the record, git history and the private selection bytes
under ``data/holdout/attempt-<n>/`` at runtime. Private files are located by content (recorded
SHA-256 or shape), except the selector's hit inventory ``exclusion_hits.txt`` (lines
``<symbol_sha256> token<i> <object|file> <git object id|repo path>``). A skip's evidence is
the master CSV for ``NOT_EQ``/``NON_IN_ISIN``, otherwise a JSON envelope
``{"symbol": ..., "responses": {"integrated"|"legacy"|"bse"|"xbrl": {"status": 200, "body": ...}}}``
holding every response its rules read (``xbrl``: listing link → instance text). A failure names
only the check and its step, plus a redacted path for a leak, and never a recorded value (D1.7).
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import subprocess
from collections import defaultdict
from collections.abc import Callable, Iterable
from datetime import UTC, date, datetime, timedelta, timezone
from functools import cache
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

from fundamentals.canon.dictionary import load_dictionary
from fundamentals.contracts.onboarding import ONBOARDING_VERSIONS
from fundamentals.entity.verification import VERIFIED, financial_rule, instance_state
from fundamentals.evidence.mapping import MappingSet, UnsupportedSchemaError, load_mapping_set
from fundamentals.evidence.xbrl_adapter import parse_instance

RECORD = "tests/fundamentals/fixtures/data_foundation/stage4_holdout.yaml"
FREEZE = "tests/fundamentals/fixtures/data_foundation/stage4_freeze.yaml"
LEAK_EXEMPT = (RECORD, "tests/fundamentals/fixtures/data_foundation/stage4_manifest.yaml")
CAPABILITY = "docs/workstreams/data-foundation/d6-capability.md"
DISCOVERY = "src/fundamentals/entity/discovery.py"
HOLDOUT = "data/holdout"
IMPL = ("src", "config", "migrations", "scripts", "pyproject.toml", "uv.lock")
LEAK_ROOTS = ("src", "config", "tests")
SELECTION_ROOTS = ("src", "config", "tests", "migrations", "scripts", "docs", "scratchpad")
CATALOGUE = {  # D1.2 amendment: exempt only while the bytes match the pin
    "scratchpad/upstox/entity-map-v2/entity_map.json": (
        "9f61287c82e46244b0823a5fac25da7313a5d0ba39c325b434139ce5aafbbc2a"
    ),
    "scratchpad/upstox/entity-map-2026-09-04/entity_map.json": (
        "c2f81973797cb4d362c76061c41dd7d17579ba244ebf20f28119ef0c23c911f7"
    ),
}
FINANCIAL, INDUSTRY = "Financial Services", "Industry"
REVIEWER, APPROVE, UPSTOX = "gpt-6.1-sol", "APPROVE", "UPSTOX"
NOT_EQ, NON_IN_ISIN, NO_FILINGS = "NOT_EQ", "NON_IN_ISIN", "NO_CONSOLIDATED_INCAPMKT"
BSE_NOT_ONE, TOKEN_HIT, NO_XBRL = "BSE_NOT_ONE", "TOKEN_HIT", "XBRL_NOT_ADMITTED"
SKIP_REASONS = (NOT_EQ, NON_IN_ISIN, NO_FILINGS, NO_XBRL, BSE_NOT_ONE, TOKEN_HIT)
XBRL_RULE_FROM = 3  # D1.3 amendment 2026-10-16 (eqos-h4h.10): attempts drawn after burn 2
CONFIG = Path(__file__).resolve().parents[2] / "config"
KEYS = {  # D1.1
    "record": {"attempts", "burns"},
    "attempt": {"n", "identifier", "selection", "prediction", "approval"},
    "selection": {
        *("seed_commit", "selection_commit", "as_of", "frame", "exclusion_inventory_sha256"),
        *("universe_sha256", "n_universe", "catalogue_exemptions", "start_index", "skips"),
        "selected_index",
    },
    "frame": {"url", "sha256", "retrieved_at", "column", "excluded_values"},
    "exemption": {"path", "sha256"},
    "skip": {"index", "symbol_sha256", "reason", "evidence_sha256"},
    "prediction": {
        *("capability_commit", "capability_sha256", "outcome", "excluded_units"),
        *("diagnostic_excluded", "run_status"),
    },
    "approval": {"reviewer", "verdict", "date", "payload_sha256"},
    "burn": {"attempt", "reason_code", "bead", "freeze_descriptor_sha256", "date"},
}
SHA1, SHA256 = re.compile(r"[0-9a-f]{40}"), re.compile(r"[0-9a-f]{64}")
IST = timezone(timedelta(hours=5, minutes=30))  # Asia/Kolkata, no DST
MASTER_HEADER = b"SYMBOL,NAME OF COMPANY"
FINANCIALS, CONSOLIDATED = "Integrated Filing- Financials", "Consolidated"
DAY, MOMENT, WINDOW = "%d-%b-%Y", "%d-%b-%Y %H:%M:%S", 6
CHECKS: dict[str, Callable[[Path], None]] = {}


class RefusedError(Exception):
    """A check step that did not hold; carries the step name, never a value."""


def need(ok: bool, step: str) -> None:
    """Refuse the step unless ``ok``."""
    if not ok:
        raise RefusedError(step)


def holdout_check(name: str) -> Callable[[Callable[[Path], None]], Callable[[Path], None]]:
    """Register a check whose every failure is an opaque ``pytest.fail`` naming it (D1.7)."""

    def register(check: Callable[[Path], None]) -> Callable[[Path], None]:
        def run(repo: Path) -> None:
            try:
                check(repo)
                return
            except RefusedError as refused:
                step = str(refused)
            except Exception as error:  # opaque: the type only, a message may carry a value
                step = type(error).__name__
            pytest.fail(f"stage4_holdout {name}: {step}", pytrace=False)

        CHECKS[name] = run
        return run

    return register


def sha256(data: bytes) -> str:
    """Hex SHA-256 of bytes."""
    return hashlib.sha256(data).hexdigest()


def git(repo: Path, *args: str, stdin: bytes | None = None) -> bytes:
    """Stdout of a git command in the repo."""
    return subprocess.run(
        ["git", *args], cwd=repo, input=stdin, capture_output=True, check=True
    ).stdout


def is_ancestor(repo: Path, older: str, newer: str) -> bool:
    """Whether ``older`` is ``newer`` or one of its ancestors."""
    args = ["git", "merge-base", "--is-ancestor", older, newer]
    return subprocess.run(args, cwd=repo, capture_output=True).returncode == 0


def commits(repo: Path, *args: str) -> list[str]:
    """Commit ids ``git rev-list`` prints for the arguments."""
    return git(repo, "rev-list", *args).decode().split()


def paths(repo: Path, *args: str) -> list[str]:
    """Paths ``git ls-files -z`` prints for the arguments."""
    return [p for p in git(repo, "ls-files", "-z", *args).decode().split("\0") if p]


def under(path: str, roots: Iterable[str]) -> bool:
    """Whether a repo path is one of the roots or inside one."""
    return any(path == root or path.startswith(f"{root}/") for root in roots)


def record(repo: Path) -> dict[str, Any]:
    """The attempts record as checked out."""
    return cast(dict[str, Any], yaml.safe_load((repo / RECORD).read_bytes()))


def freezes(repo: Path) -> list[dict[str, Any]]:
    """The freeze descriptor entries, ``freezes: [...]`` with the last current (D6 step 2)."""
    path = repo / FREEZE
    doc = (yaml.safe_load(path.read_bytes()) or {}) if path.exists() else {}
    return cast(list[dict[str, Any]], doc.get("freezes") or [])


def attempt_payload_sha256(attempt: dict[str, Any]) -> str:
    """SHA-256 of the attempt without ``approval``, ``yaml.safe_dump(sort_keys=True)`` (D1.1)."""
    body = {key: value for key, value in attempt.items() if key != "approval"}
    return sha256(yaml.safe_dump(body, sort_keys=True).encode())


def kolkata_date(retrieved_at: Any) -> date:
    """The Asia/Kolkata date of a retrieval time (a naive time is UTC)."""
    moment = retrieved_at
    if not isinstance(moment, datetime):
        moment = datetime.fromisoformat(str(retrieved_at))
    return (moment if moment.tzinfo else moment.replace(tzinfo=UTC)).astimezone(IST).date()


def normalised(name: str) -> str:
    """A company name without its trailing ``Limited``/``Ltd.`` (D1.6)."""
    return re.sub(r"\s+(?:Limited|Ltd\.?)\s*$", "", name.strip(), flags=re.IGNORECASE)


def matcher(tokens: Iterable[str]) -> re.Pattern[bytes]:
    """D1.6 match: bytes, ASCII case-insensitive, no alphanumeric neighbour, words by ``\\s+``."""
    words = [rb"\s+".join(re.escape(w.encode()) for w in t.split()) for t in tokens if t.strip()]
    body = b"|".join(words)
    return re.compile(rb"(?<![A-Za-z0-9])(?:" + body + rb")(?![A-Za-z0-9])", re.IGNORECASE)


def contents(repo: Path, oids: list[str]) -> dict[str, bytes]:
    """The bytes of each blob or tree among the objects (``git cat-file --batch``)."""
    out = git(repo, "cat-file", "--batch", stdin="".join(f"{o}\n" for o in oids).encode())
    found, pos = {}, 0
    for oid in oids:
        end = out.index(b"\n", pos)
        _, kind, size = out[pos:end].split()
        body, pos = out[end + 1 : end + 1 + int(size)], end + 2 + int(size)
        if kind in (b"blob", b"tree"):
            found[oid] = body
    return found


def reachable(repo: Path, commit: str) -> dict[str, str]:
    """Every object ``rev-list --objects`` lists from the commit, with the path it names."""
    listed = git(repo, "rev-list", "--objects", commit).decode().splitlines()
    return {oid: path for oid, _, path in (line.partition(" ") for line in listed)}


def object_hits(repo: Path, commit: str, pattern: re.Pattern[bytes]) -> list[str]:
    """Paths of the blobs and trees reachable from the commit whose bytes match; deleted,
    renamed, merge-only and binary content and every entry name are read."""
    listed = reachable(repo, commit)
    bodies = contents(repo, list(listed))
    return [listed[oid] for oid, body in bodies.items() if pattern.search(body)]


def file_hits(repo: Path, files: Iterable[str], pattern: re.Pattern[bytes]) -> list[str]:
    """Working-tree files whose path or bytes match."""
    return [
        p
        for p in files
        if pattern.search(p.encode())
        or ((repo / p).is_file() and pattern.search((repo / p).read_bytes()))
    ]


def selection_hits(repo: Path, commit: str, pattern: re.Pattern[bytes]) -> list[str]:
    """D1.2 token scan at selection: every blob and tree reachable from the commit, untracked and
    ignored files under the development roots (a catalogue map only while its bytes match the
    pin), and ``data/`` directory names to depth 2 outside ``data/holdout``."""
    others = [
        p
        for p in paths(repo, "--others", "--", *SELECTION_ROOTS)
        if CATALOGUE.get(p) != sha256((repo / p).read_bytes())
    ]
    dirs = [
        str(d.relative_to(repo))
        for d in [*repo.glob("data/*"), *repo.glob("data/*/*")]
        if d.is_dir() and not under(str(d.relative_to(repo)), [HOLDOUT])
    ]
    return [
        *object_hits(repo, commit, pattern),
        *file_hits(repo, others, pattern),
        *(d for d in dirs if pattern.search(d.encode())),
    ]


def period_end(row: dict[str, Any]) -> date:
    """A listing row's period end (integrated ``qe_Date``, legacy ``toDate``)."""
    return datetime.strptime(row["qe_Date"] if "qe_Date" in row else row["toDate"], DAY).date()


def quarter_ends(as_of: date) -> set[date]:
    """The six latest calendar quarter-ends on or before ``as_of``."""
    ends = [
        date(year, month, day)
        for year in range(as_of.year - 2, as_of.year + 1)
        for month, day in ((3, 31), (6, 30), (9, 30), (12, 31))
    ]
    return set([end for end in ends if end <= as_of][-WINDOW:])


def qualifying_periods(rows: Iterable[dict[str, Any]], as_of: date) -> int | None:
    """The number of distinct qualifying period ends (``qualifying_filings``)."""
    filings = qualifying_filings(rows, as_of)
    return None if filings is None else len(filings)


def qualifying_filings(
    rows: Iterable[dict[str, Any]], as_of: date
) -> dict[date, str | None] | None:
    """D1.3 filing-window rule over rows of both NSE listings: collapse each (period_end, basis)
    to its latest broadcast; each distinct period end of a collapsed consolidated in-capmkt row
    with that row's XBRL link; None when a group's latest broadcast is tied. Broadcast is the
    listing's own field only: a group with a row that has none (missing, empty or blank) cannot
    be ordered and yields no qualifying period. Rows equal on the parsed fields (period end,
    basis, broadcast, listing, type, XBRL link) are one filing; any other field, e.g. ``seq_Id``,
    is ignored."""
    window = quarter_ends(as_of)
    groups: dict[tuple[date, str], list[tuple[datetime | None, bool, str | None]]]
    groups = defaultdict(list)
    parsed = {}
    for row in rows:
        integrated = "qe_Date" in row
        text = (row.get("broadcast_Date" if integrated else "broadCastDate") or "").strip()
        when = datetime.strptime(text, MOMENT) if text else None
        xbrl = (row.get("xbrl") or "").strip() or None
        key = (period_end(row), row.get("consolidated"), when, integrated, row.get("type"), xbrl)
        parsed[key] = None
    for end, basis, when, integrated, kind, xbrl in parsed:
        if end in window and basis:
            qualifies = integrated and kind == FINANCIALS and basis == CONSOLIDATED
            groups[end, basis].append((when, qualifies, xbrl))
    periods = {}
    for (end, _), filings in groups.items():
        times = [when for when, *_ in filings]
        if None in times:
            continue
        latest = max(cast(list[datetime], times))
        top = [(qualifies, xbrl) for when, qualifies, xbrl in filings if when == latest]
        if len(top) > 1:
            return None
        if top[0][0]:
            periods[end] = top[0][1]
    return periods


@cache
def onboarding_mapping_set() -> MappingSet:
    """The mapping set discovery parses instances under (``ONBOARDING_VERSIONS``)."""
    dictionary = load_dictionary(CONFIG / "dictionary", ONBOARDING_VERSIONS.dictionary)
    return load_mapping_set(
        CONFIG / "mappings", ONBOARDING_VERSIONS.mapping_set, dictionary=dictionary
    )


def xbrl_admitted(body: bytes, period_end: date) -> bool:
    """Discovery's XBRL step for one instance of a qualifying period (D4.2 steps 3-4): the
    financial rule, the onboarding mapping set's schema, then ``instance_state`` (scope, period
    and first-party ingest's own framework predicate)."""
    if not financial_rule(body):
        return False
    try:
        instance = parse_instance(body, mapping_set=onboarding_mapping_set())
    except UnsupportedSchemaError:
        return False
    return instance_state(instance, period_end) == VERIFIED


def csv_rows(data: bytes) -> list[dict[str, str]]:
    """CSV rows with stripped header names and values."""
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
    return [{k.strip(): (v or "").strip() for k, v in row.items() if k} for row in reader]


def listing_rows(doc: Any, symbol: str) -> list[dict[str, Any]]:
    """The symbol's rows of one NSE listing response (legacy list or integrated ``data``)."""
    items = doc.get("data") if isinstance(doc, dict) else doc
    return [
        r
        for r in (items if isinstance(items, list) else [])
        if isinstance(r, dict) and r.get("symbol") == symbol and {"qe_Date", "toDate"} & r.keys()
    ]


def bse_candidates(text: str, isin: str) -> list[str]:
    """The exact-ISIN ``<li>`` candidates of a ``PeerSmartSearch`` response."""
    exact = f"<strong>{isin}</strong>"
    return [li for li in re.findall(r"<li\b.*?</li>", text, re.S) if exact in li]


def selection_scope(path: str) -> bool:
    """Whether a recorded file hit lies where the D1.2 scan reads: a development-root file other
    than a catalogue map, or a ``data/`` directory name to depth 2 outside ``data/holdout``."""
    if path.startswith("data/"):
        return path.count("/") <= 2 and not under(path, [HOLDOUT])
    return under(path, SELECTION_ROOTS) and path not in CATALOGUE


class Selection:
    """One attempt's private selection bytes, located by content (D1.2, D1.3)."""

    def __init__(self, repo: Path, attempt: dict[str, Any]) -> None:
        self.repo, self.attempt, self.sel = repo, attempt, attempt["selection"]
        self.root = repo / HOLDOUT / f"attempt-{attempt['n']}"
        files = [p.read_bytes() for p in sorted(self.root.rglob("*")) if p.is_file()]
        self.files = {sha256(data): data for data in files}
        need(self.sel["frame"]["sha256"] in self.files, "frame bytes")
        self.frame = {r["Symbol"]: r for r in csv_rows(self.files[self.sel["frame"]["sha256"]])}
        masters = [data for data in self.files.values() if data.startswith(MASTER_HEADER)]
        need(len(masters) == 1, "master bytes")
        self.master_bytes = masters[0]
        self.master = csv_rows(masters[0])

    def universe(self) -> list[str]:
        """Frame symbols outside the hashed exclusion inventory, ASCII-sorted and hash-checked.
        Each exclusion is recomputed: the financials from the frame (one reason), every other
        (one other reason) from the hit inventory (``token_hits``)."""
        sel, frame = self.sel, self.sel["frame"]
        need(sel["exclusion_inventory_sha256"] in self.files, "inventory bytes")
        lines = self.files[sel["exclusion_inventory_sha256"]].decode().splitlines()
        inventory = dict(re.split(r"[\s,]+", line.strip(), maxsplit=1) for line in lines if line)
        financial = {
            sha256(s.encode())
            for s, r in self.frame.items()
            if r[frame["column"]] in frame["excluded_values"]
        }
        need(financial <= inventory.keys(), "financial exclusions")
        reasons = [
            {inventory[h] for h in group} for group in (financial, inventory.keys() - financial)
        ]
        need(all(len(r) <= 1 for r in reasons) and not reasons[0] & reasons[1], "exclusion reasons")
        hit = self.token_hits()
        need(inventory.keys() - financial <= hit <= inventory.keys(), "token exclusions")
        universe = sorted(
            (s for s in self.frame if sha256(s.encode()) not in inventory), key=str.encode
        )
        size = len(inventory) + len(universe)
        need(len(universe) == sel["n_universe"] and size == len(self.frame), "universe size")
        listed = "".join(f"{symbol}\n" for symbol in universe).encode()
        need(sha256(listed) == sel["universe_sha256"], "universe hash")
        return universe

    def token_hits(self) -> set[str]:
        """Symbol hashes of the hit inventory, every line refused unless it holds: an object hit
        is recomputed against that object, reachable from ``selection_commit``; an untracked file
        or ``data/`` name is not reproducible after selection, so its line must lie in scope."""
        by_hash = {sha256(s.encode()): s for s in self.frame}
        text = (self.root / "exclusion_hits.txt").read_text()
        lines = [line.split(" ", 3) for line in text.splitlines() if line]
        need(
            all(
                len(p) == 4
                and p[0] in by_hash
                and re.fullmatch(r"token\d+", p[1])
                and p[2] in ("object", "file")
                for p in lines
            ),
            "hit inventory",
        )
        objects = {p[3] for p in lines if p[2] == "object"}
        need(objects <= reachable(self.repo, self.sel["selection_commit"]).keys(), "hit objects")
        bodies = contents(self.repo, sorted(objects))
        for digest, _, kind, location in lines:
            if kind == "file":
                need(selection_scope(location), "hit files")
                continue
            pattern = matcher(self.frame_tokens(by_hash[digest]))
            need(bool(pattern.search(bodies.get(location, b""))), "hit objects")
        return {p[0] for p in lines}

    def isin(self, symbol: str) -> str | None:
        """The ISIN of the symbol's one ``EQ`` row in the master, if any."""
        rows = [r for r in self.master if r["SYMBOL"] == symbol and r["SERIES"] == "EQ"]
        return rows[0]["ISIN NUMBER"] if len(rows) == 1 else None

    def listing(self, symbol: str) -> list[dict[str, Any]]:
        """The symbol's rows of every retained NSE listing (legacy and integrated)."""
        rows = []
        for digest, data in self.files.items():
            if digest in CATALOGUE.values():
                continue
            try:
                doc = json.loads(data)
            except ValueError:
                continue
            rows += listing_rows(doc, symbol)
        return rows

    def bse(self, isin: str) -> list[str]:
        """The exact-ISIN candidates of the retained ``PeerSmartSearch`` response for the ISIN."""
        exact = f"<strong>{isin}</strong>".encode()
        found = [d.decode() for d in self.files.values() if b"<li" in d and exact in d]
        need(len(found) <= 1, "bse evidence")
        return bse_candidates("".join(found), isin)

    def instance(self, link: str) -> bytes:
        """The one retained instance named by a listing link's file name (names carry no
        identifier)."""
        name = link.rsplit("/", 1)[-1]
        found = [p for p in self.root.rglob("*") if p.is_file() and p.name == name]
        need(len(found) == 1, "instance bytes")
        return found[0].read_bytes()

    def frame_tokens(self, symbol: str) -> list[str]:
        """D1.2 tokens of a frame row: symbol, ISIN, normalised name."""
        row = self.frame[symbol]
        return [symbol, row["ISIN Code"], normalised(row["Company Name"])]

    def holdout_tokens(self) -> list[str]:
        """D1.6 tokens of the drawn company: symbol, ISIN, BSE scrip, normalised names."""
        symbol = self.attempt["identifier"]
        isin = cast(str, self.isin(symbol))
        (li,) = self.bse(isin)
        scrip = cast(re.Match[str], re.search(r"</strong>(?:&nbsp;|\s)*(\d+)", li)).group(1)
        (name,) = [r["NAME OF COMPANY"] for r in self.master if r["SYMBOL"] == symbol]
        return [*self.frame_tokens(symbol), isin, scrip, normalised(name)]

    def failed_rule(self, symbol: str, evidence: dict[str, Any] | None = None) -> str | None:
        """The first D1.3 rule the candidate fails: from a skip's evidence envelope when given
        (each response a rule reads present with status 200, else refused), else from the
        retained bytes."""

        def body(name: str) -> Any:
            response = cast(dict[str, Any], evidence)["responses"].get(name) or {}
            need(response.get("status") == 200, "skip evidence")
            return response["body"]

        isin = self.isin(symbol)
        if isin is None:
            return NOT_EQ
        if not isin.startswith("IN"):
            return NON_IN_ISIN
        rows = (
            self.listing(symbol)
            if evidence is None
            else [
                *listing_rows(body("integrated"), symbol),
                *listing_rows(body("legacy"), symbol),
            ]
        )
        filings = qualifying_filings(rows, date.fromisoformat(str(self.sel["as_of"])))
        if filings is None or len(filings) < 2:
            return NO_FILINGS
        if self.attempt["n"] >= XBRL_RULE_FROM:
            latest = sorted(filings.items(), reverse=True)[:2]
            if any(link is None for _, link in latest):
                return NO_XBRL
            if evidence is None:
                bodies = {link: self.instance(cast(str, link)) for _, link in latest}
            else:
                bodies = {link: text.encode() for link, text in body("xbrl").items()}
            need(bodies.keys() == {link for _, link in latest}, "skip evidence")
            if not all(xbrl_admitted(bodies[link], end) for end, link in latest):
                return NO_XBRL
        bse = self.bse(isin) if evidence is None else bse_candidates(body("bse"), isin)
        if len(bse) != 1:
            return BSE_NOT_ONE
        pattern = matcher(self.frame_tokens(symbol))
        if object_hits(self.repo, self.sel["selection_commit"], pattern):
            return TOKEN_HIT
        return None

    def check_skip(self, symbol: str, skip: dict[str, Any]) -> None:
        """The skip's evidence file reproduces its reason: the master for an ``EQUITY_L`` rule,
        else an envelope naming the symbol; a missing or failed response refuses, never skips."""
        need(skip["symbol_sha256"] == sha256(symbol.encode()), "skip evidence")
        data = self.files.get(skip["evidence_sha256"])
        need(data is not None, "skip evidence")
        if skip["reason"] in (NOT_EQ, NON_IN_ISIN):
            need(data == self.master_bytes, "skip evidence")
            rule = self.failed_rule(symbol)
        else:
            try:
                evidence = json.loads(cast(bytes, data))
            except ValueError:
                evidence = None
            named = isinstance(evidence, dict) and evidence.get("symbol") == symbol
            need(named and isinstance(evidence.get("responses"), dict), "skip evidence")
            rule = self.failed_rule(symbol, evidence)
        need(rule == skip["reason"], "skip reason")


def keyed(node: Any, kind: str) -> dict[str, Any]:
    """The node, refused unless it is a mapping with exactly the D1.1 keys of its kind."""
    need(isinstance(node, dict) and node.keys() == KEYS[kind], f"{kind} keys")
    return cast(dict[str, Any], node)


@holdout_check("schema")
def check_schema(repo: Path) -> None:
    """Exact D1.1 keys, full commit ids, SHA-256 values, skip reasons and index bounds."""
    doc = keyed(record(repo), "record")
    for burn in doc["burns"] or []:
        keyed(burn, "burn")
    for attempt in doc["attempts"]:
        sel, prediction = keyed(attempt, "attempt")["selection"], attempt["prediction"]
        keyed(sel, "selection")
        keyed(prediction, "prediction")
        exemptions = [keyed(e, "exemption") for e in sel["catalogue_exemptions"]]
        skips = [keyed(s, "skip") for s in sel["skips"]]
        need(all(s["reason"] in SKIP_REASONS for s in skips), "skip reason")
        need(isinstance(attempt["identifier"], str) and bool(attempt["identifier"]), "identifier")
        ids = (sel["seed_commit"], sel["selection_commit"], prediction["capability_commit"])
        need(all(SHA1.fullmatch(str(c)) for c in ids), "commit ids")
        hashes = [
            keyed(sel["frame"], "frame")["sha256"],
            *(sel["exclusion_inventory_sha256"], sel["universe_sha256"]),
            *(
                prediction["capability_sha256"],
                keyed(attempt["approval"], "approval")["payload_sha256"],
            ),
            *(e["sha256"] for e in exemptions),
            *(s[k] for s in skips for k in ("symbol_sha256", "evidence_sha256")),
        ]
        need(all(SHA256.fullmatch(str(h)) for h in hashes), "sha256 values")
        size = sel["n_universe"]
        bounds = (sel["start_index"], sel["selected_index"], *(s["index"] for s in skips))
        need(isinstance(size, int) and all(0 <= i < size for i in bounds), "indices")


@holdout_check("payload")
def check_payload(repo: Path) -> None:
    """Each attempt carries Sol's APPROVE over its own payload hash. Entries never change after
    their introducing commit (ordering), so this holds at every commit from ``record_k`` on,
    including the parent of the first IMPL commit after ``record_1`` (D1.5)."""
    for attempt in record(repo)["attempts"]:
        approval = attempt["approval"]
        need(approval["reviewer"] == REVIEWER, "approval reviewer")
        need(approval["verdict"] == APPROVE, "approval verdict")
        need(bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(approval["date"]))), "approval date")
        need(approval["payload_sha256"] == attempt_payload_sha256(attempt), "payload_sha256")


@holdout_check("draw")
def check_draw(repo: Path) -> None:
    """D1.2-D1.3 recomputed from the private bytes: ``as_of``, catalogue pins, universe, seed,
    walk, each skip's reason and the selected candidate passing every rule."""
    for attempt in record(repo)["attempts"]:
        sel = attempt["selection"]
        need(str(sel["as_of"]) == kolkata_date(sel["frame"]["retrieved_at"]).isoformat(), "as_of")
        pins = {e["path"]: e["sha256"] for e in sel["catalogue_exemptions"]}
        need(pins == CATALOGUE and len(sel["catalogue_exemptions"]) == 2, "catalogue_exemptions")
        frame = sel["frame"]
        need(frame["column"] == INDUSTRY and FINANCIAL in frame["excluded_values"], "frame column")
        selection = Selection(repo, attempt)
        need(set(CATALOGUE.values()) <= selection.files.keys(), "catalogue copies")
        universe = selection.universe()
        seed = f"{sel['seed_commit']}:{frame['sha256']}:{attempt['n']}".encode("ascii")
        start = int(sha256(seed), 16) % len(universe)
        skips = sel["skips"]
        need(sel["start_index"] == start, "start_index")
        walk = [(start + j) % len(universe) for j in range(len(skips) + 1)]
        need([s["index"] for s in skips] == walk[:-1], "skip walk")
        selected = sel["selected_index"] == walk[-1]
        need(selected and universe[walk[-1]] == attempt["identifier"], "selected_index")
        for skip in skips:
            selection.check_skip(universe[skip["index"]], skip)
        need(selection.failed_rule(attempt["identifier"]) is None, "selected candidate")


@holdout_check("prediction")
def check_prediction(repo: Path) -> None:
    """D1.4 recomputed from the capability table committed before the draw."""
    for attempt in record(repo)["attempts"]:
        prediction = attempt["prediction"]
        text = git(repo, "show", f"{prediction['capability_commit']}:{CAPABILITY}")
        need(sha256(text) == prediction["capability_sha256"], "capability bytes")
        selection_commit = attempt["selection"]["selection_commit"]
        need(is_ancestor(repo, prediction["capability_commit"], selection_commit), "capability")
        (block,) = re.findall(r"```yaml\n(.*?)```", text.decode(), re.S)
        units = yaml.safe_load(block)["units"]
        excluded = sorted(unit for unit, state in units.items() if state != "reachable")
        expected = {
            "outcome": "PARTIAL" if excluded else "ONBOARDED",
            "excluded_units": excluded,
            "diagnostic_excluded": [unit for unit in excluded if unit == UPSTOX],
            "run_status": "INCOMPLETE" if set(excluded) - {UPSTOX} else "COMPLETE",
        }
        recorded = {k: sorted(v) if isinstance(v, list) else v for k, v in prediction.items()}
        need(all(recorded[k] == v for k, v in expected.items()), "prediction")


def introductions(
    repo: Path, path: str, section: str, key: str
) -> dict[Any, tuple[str, dict[str, Any]]]:
    """Each entry's introducing commit and its content there, by entry key; refused unless every
    version (each commit touching the file, then the working tree) extends the previous one
    with all earlier entries present and unchanged (append-only, D1.1)."""
    found: dict[Any, tuple[str, dict[str, Any]]] = {}
    before: list[dict[str, Any]] = []
    versions = git(repo, "log", "--reverse", "--format=%H", "--", path).decode().split()
    for commit in [*versions, None]:
        if commit is None:
            data = (repo / path).read_bytes() if (repo / path).exists() else b""
        elif git(repo, "ls-tree", commit, "--", path):
            data = git(repo, "show", f"{commit}:{path}")
        else:  # the commit deleted the file
            data = b""
        entries = (yaml.safe_load(data) or {}).get(section) or []
        need(entries[: len(before)] == before, "entry changed after its commit")
        for entry in entries[len(before) :]:
            found.setdefault(entry[key], (cast(str, commit), entry))
        before = entries
    return found


@holdout_check("ordering")
def check_ordering(repo: Path) -> None:
    """D1.5: append-only entries, ``record_k^ == selection_commit``, seeds, IMPL ordering around
    ``record_1``, freeze descriptors after their record and no IMPL change after the current
    freeze."""
    doc, frozen_entries = record(repo), freezes(repo)
    attempts, burns = doc["attempts"], doc["burns"] or []
    need([a["n"] for a in attempts] == list(range(1, len(attempts) + 1)), "attempt numbering")
    need([b["attempt"] for b in burns] == list(range(1, len(burns) + 1)), "burn numbering")
    need(len(attempts) - 1 <= len(burns) <= len(attempts), "current attempt")
    entries = introductions(repo, RECORD, "attempts", "n")
    burned = introductions(repo, RECORD, "burns", "attempt")
    frozen = introductions(repo, FREEZE, "freezes", "attempt")  # an emptied list is a removal
    for entry, intro in [
        *((a, entries[a["n"]]) for a in attempts),
        *((b, burned[b["attempt"]]) for b in burns),
        *((f, frozen[f["attempt"]]) for f in frozen_entries),
    ]:
        need(intro[1] == entry, "entry changed after its commit")
    for attempt in attempts:
        k, sel, record_k = attempt["n"], attempt["selection"], entries[attempt["n"]][0]
        parent = git(repo, "rev-parse", f"{record_k}^").decode().strip()
        need(parent == sel["selection_commit"], "record parent is not selection_commit")
        need(is_ancestor(repo, sel["seed_commit"], sel["selection_commit"]), "seed ancestry")
        need(k == 1 or sel["seed_commit"] == burned[k - 1][0], "seed is not the burn commit")
    record_1, seed_1 = entries[1][0], attempts[0]["selection"]["seed_commit"]
    need(not commits(repo, f"{seed_1}..{record_1}", "--", *IMPL), "IMPL commit before record")
    later = commits(repo, "HEAD", "--not", record_1, "--", *IMPL)
    added = git(repo, "log", "--diff-filter=A", "--format=%H", "--", DISCOVERY).decode().split()
    need(all(is_ancestor(repo, record_1, c) and c != record_1 for c in [*later, *added]), "IMPL")
    for entry in frozen_entries:
        k, commit = entry["attempt"], frozen[entry["attempt"]][0]
        record_k = entries[k][0]
        need(is_ancestor(repo, record_k, commit) and commit != record_k, "freeze before record")
        payload = attempt_payload_sha256(attempts[k - 1])
        need(entry["holdout_payload_sha256"] == payload, "freeze payload")
    current = [f for f in frozen_entries if f["attempt"] == len(attempts) > len(burns)]
    for entry in current:
        change = commits(repo, f"{entry['implementation_commit']}..HEAD", "--", *IMPL)
        need(not change, "IMPL change after freeze")


@holdout_check("leaks")
def check_leaks(repo: Path) -> None:
    """D1.6 over every blob and tree any commit since selection holds under src/ config/ tests/
    (each object with all its paths from every intervening tree, so a copy elsewhere hides
    nothing), the current tree and untracked files there. An object is exempt only if every path
    it ever had is the record's or the Stage 4 manifest's."""
    attempt = record(repo)["attempts"][-1]
    pattern = matcher(Selection(repo, attempt).holdout_tokens())
    places: dict[str, set[str]] = defaultdict(set)
    for commit in commits(repo, f"{attempt['selection']['selection_commit']}..HEAD"):
        for line in git(repo, "ls-tree", "-r", "-t", "-z", commit).decode().split("\0"):
            meta, _, path = line.partition("\t")
            if line and meta.split()[1] in ("blob", "tree"):
                places[meta.split()[2]].add(path)
    scoped = sorted(
        oid
        for oid, where in places.items()
        if any(under(p, LEAK_ROOTS) for p in where) and not where <= set(LEAK_EXEMPT)
    )
    current = paths(repo, "--cached", "--others", "--", *LEAK_ROOTS)
    hits = [
        *(
            min(p for p in places[oid] if under(p, LEAK_ROOTS))
            for oid, body in contents(repo, scoped).items()
            if pattern.search(body)
        ),
        *file_hits(repo, [p for p in current if p not in LEAK_EXEMPT], pattern),
    ]
    for path in hits:
        need(False, f"leak at {pattern.sub(b'<token>', path.encode()).decode()}")


def current(repo: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """The current attempt and its freeze entry (the last of each)."""
    return record(repo)["attempts"][-1], freezes(repo)[-1]


def refused(check: Callable[[], None]) -> bool:
    """Whether a check refuses (an assertion or a refused step)."""
    try:
        check()
    except (AssertionError, RefusedError):
        return True
    return False
