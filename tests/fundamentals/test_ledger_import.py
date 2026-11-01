"""D3.5 acceptance: imports of the Apar earnings updates, the Q0 thesis and the management ledger
(plan D6-D8, Task 5).

The mapping tests read the retained sources, pinned by SHA-256 below, and prove the mapping
lossless both ways: the sections render back to the Markdown bytes, and an altered numeral or an
unmapped twin field fails. The import tests run on an ``eqos_test_*`` database holding the D2
legacy import and its acquisitions (``ledger_cited_support``), through the panel login.
"""

from __future__ import annotations

import copy
import fnmatch
import hashlib
import json
import re
import shutil
import subprocess
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml
from ledger_cited_support import Cited, cited
from pg_support import PgTestDatabase
from retained_support import STORE_DIR

from fundamentals.api.cli import main
from fundamentals.api.screener_cli_dispatch import EXIT_REFUSED
from fundamentals.contracts.canonical import ValueKind
from fundamentals.contracts.evidence import RunMode
from fundamentals.contracts.guidance_claim import EpistemicClass
from fundamentals.contracts.ledger import (
    Citation,
    CitationKind,
    ClaimState,
    DeciderRole,
    DecisionKind,
    NumericClaim,
    ReportKind,
    Rounding,
    SubjectKind,
    VersionStatus,
)
from fundamentals.ledger import store
from fundamentals.ledger.display import content_hash, narrative, render_section
from fundamentals.ledger.falsifier_status import approved_thesis, derived, evaluate
from fundamentals.ledger.import_mapping import (
    UNMAPPED_FIELDS,
    LosslessError,
    MappedVersion,
    map_earnings_update,
    map_q0,
)
from fundamentals.ledger.importer import (
    ImportConfig,
    evidence_holds,
    import_thesis_successor,
    import_versions,
    load_import_config,
)
from fundamentals.ledger.lifecycle import version_status
from fundamentals.ledger.run_traces import CALCS, Line
from fundamentals.output.pnl_lines import ETR_LABEL
from fundamentals.pg.settings import PgRole
from fundamentals.verify.thesis_predicates import Disposition, parse_thesis

__all__ = ["cited"]

REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / "config" / "ledger_import.yaml"
QUARTERS = ("FY26_Q2", "FY26_Q3", "FY26_Q4", "FY27_Q1")
LEDGER = "data/ledger/aparinds-management-ledger.json"
Q0_MD = "docs/evidence/phase-0.5/q0-approved-thesis.md"
Q0_YAML = "docs/evidence/phase-0.5/q0-approved-thesis.yaml"
UPDATE = "data/reports/aparinds/{}/earnings-update.{}"
PINNED = {
    **{
        UPDATE.format(*name): sha256
        for name, sha256 in {
            ("FY26_Q2", "md"): "271b1e7082ce0639ad334901c4c9af141ba69a244fa2aaf601991d727d80e45a",
            ("FY26_Q3", "md"): "60ca3029ba729c6a8fb515723f3acb6080c56c68d70cf436a6f034ce5e279f6d",
            ("FY26_Q4", "md"): "205b540c973b11cf7f10855975c639875bb0a2789680fe079469154db4f1e0ea",
            ("FY27_Q1", "md"): "1b7ce209b97afec76b37683e9d1368f81b80d768f54ed63028f19fd7313c64fe",
            ("FY26_Q2", "json"): "43b40e815f1e135262eeef57b96d33277b4a8f15bdef12318d6a90a622d7afe4",
            ("FY26_Q3", "json"): "a70b7eb958fc58cc7701b23e1b68550793aece7df0a35542d6d8790091050a07",
            ("FY26_Q4", "json"): "24c770cdf82f35be67a9d0612c3942930425903348c030a0f2f8ba57a680817d",
            ("FY27_Q1", "json"): "a5ebfaf49f46ffe93f47e7d98424005c855ab13c94c5f992652f3c2d257cf616",
        }.items()
    },
    LEDGER: "5e611ac5081f7e9c654783e630b5fd07911a9a470d00c541ad4a99699495d91f",
    Q0_MD: "c2b9a9861c49196b3655fc684881edc17b540d28602f2a2b9fb8ff93f442396b",
    Q0_YAML: "2ed9fd0f804da991249b9720f1c65909d5c66e22287a33ce80a0e962aa57c188",
}
# Ledger entries per update (D7 evidence) and the claims every update carries besides them:
# six facts, and per comparative and comparator a prior, a change and a percent; three calcs.
LEDGER_ENTRIES = {"FY26_Q2": 2, "FY26_Q3": 3, "FY26_Q4": 4, "FY27_Q1": 4}
CLAIM_PREFIXES = {"fact.": 6, "cmp.": 36, "calc.": 3}
THRESHOLDS = {"F1": "11.55", "F2": "5.53", "F3": "14.90", "F4": "0", "F5": "26.78"}
GROWTH_KEY = "ledger.cables_revenue_growth.annual.consolidated"
ENTITY = 1


def read(path: str, root: Path = REPO) -> bytes:
    """A retained source's bytes, failing (never skipping) unless they hash to the pin."""
    body = (root / path).read_bytes()
    assert hashlib.sha256(body).hexdigest() == PINNED[path], f"{path} is not the pinned file"
    return body


def update_paths(quarter: str) -> tuple[str, str]:
    """The Markdown and JSON twin of one earnings update."""
    return UPDATE.format(quarter, "md"), UPDATE.format(quarter, "json")


def retained() -> frozenset[str]:
    """The blob SHA-256s of the retrieval manifest the config pins."""
    return frozenset(entry["sha256"] for entry in json.loads(read_manifest())["entries"])


def map_all(
    alter: Callable[[str, bytes, bytes], tuple[bytes, bytes]] = lambda _, md, twin: (md, twin),
    ledger: bytes | None = None,
) -> dict[str, MappedVersion]:
    """Every earnings update mapped in quarter order, after ``alter`` edits one's bytes."""
    mapped: dict[str, MappedVersion] = {}
    for quarter in QUARTERS:
        md, twin = alter(quarter, *(read(path) for path in update_paths(quarter)))
        mapped[quarter] = map_one(quarter, md, twin, mapped, ledger)
    return mapped


def map_one(
    quarter: str,
    md: bytes,
    twin: bytes,
    mapped: dict[str, MappedVersion],
    ledger: bytes | None = None,
) -> MappedVersion:
    """One earnings update mapped after the earlier quarters in ``mapped``."""
    return map_earnings_update(
        md,
        twin,
        read(LEDGER) if ledger is None else ledger,
        period=quarter,
        entity_id=ENTITY,
        mapped_quarters=dict(mapped),
        retained=retained(),
    )


@pytest.mark.retained
@pytest.mark.parametrize("quarter", QUARTERS)
def test_retained_updates_map_losslessly(quarter: str) -> None:
    """The slot evidence (D7): every update's sections, rendered through its claims, are its
    Markdown bytes, so its content hash is the file's SHA-256; every claim slot is explicit."""
    mapped = map_all()[quarter]
    md = read(update_paths(quarter)[0])
    assert narrative(mapped.sections, mapped.claims) == md
    assert content_hash(mapped.sections, mapped.claims) == PINNED[update_paths(quarter)[0]]
    keys = [claim.claim_key for claim in mapped.claims]
    for prefix, count in {**CLAIM_PREFIXES, "ledger.": LEDGER_ENTRIES[quarter]}.items():
        assert sum(key.startswith(prefix) for key in keys) == count, prefix
    assert len(keys) == len(set(keys))
    assert {gate for gate, _ in mapped.qa_records} == {
        "cross_check",
        "cross_foot",
        "sec_cross_check",
    }


@pytest.mark.retained
def test_shared_display_is_one_claim_with_its_alias() -> None:
    """FY26_Q3 ``**20%**`` is both ``guidance[0]`` and the cables-growth ledger entry: one
    ``SOURCE_QUOTE`` claim, the guidance only its alias (label on the contract); its quote shows
    in ``quote`` style and its qualifier is omitted from the bold bounds."""
    mapped = map_all()["FY26_Q3"]
    (claim,) = (c for c in mapped.claims if c.claim_key == GROWTH_KEY)
    assert claim.citation.kind is CitationKind.SOURCE_QUOTE
    assert (claim.lower_bound, claim.upper_bound, claim.qualifiers) == (20, 20, ("plus",))
    assert claim.metric_label == "Cables revenue growth guidance"
    assert claim.citation.quote == "tracking on a 20%-plus CAGR growth"
    (line,) = (
        line
        for s in mapped.sections
        for line in s.body.splitlines()
        if "cables_revenue_growth" in line
    )
    assert f"{{{{c:{GROWTH_KEY}|quote}}}}" in line
    assert "**20%** for annual" in render_section(line, mapped.claims)


@pytest.mark.retained
def test_q0_yaml_only_content_becomes_sections_and_policy_claims() -> None:
    """Q0's Markdown sections are its bytes; assumptions, falsifiers and open questions follow as
    sections in YAML order; each threshold is a self-cited ``POLICY`` claim at its lexeme's
    precision (``14.90`` keeps its zero)."""
    from fundamentals.ledger.falsifier_status import KINDS

    mapped = map_q0(read(Q0_MD), read(Q0_YAML), cutoff=date(2025, 11, 6), metrics=KINDS)
    rendered = narrative(mapped.sections, mapped.claims)
    assert rendered.startswith(read(Q0_MD))
    tail = rendered[len(read(Q0_MD)) :].decode()
    assert [s.section_key for s in mapped.sections][-3:] == [
        "assumptions",
        "falsifiers",
        "open_questions",
    ]
    assert tail.startswith("## assumptions\n\n- [FACT] Q2 FY26 combines")
    assert "- F3: PAT year-on-year growth falls below half its Q0 rate. (14.90)\n" in tail
    claims = {c.claim_key: c for c in mapped.claims}
    assert {k: str(c.value) for k, c in claims.items()} == {
        f"falsifier.{fid}": lexeme for fid, lexeme in THRESHOLDS.items()
    }
    assert all(
        c.citation.kind is CitationKind.POLICY and c.citation.policy_decision_id is None
        for c in claims.values()
    )
    assert mapped.bound == ()


def _alter_md(quarter: str, md: bytes, twin: bytes) -> tuple[bytes, bytes]:
    return (md.replace(b"5,479.73", b"5,479.74", 1) if quarter == "FY26_Q3" else md), twin


def _alter_twin(quarter: str, md: bytes, twin: bytes) -> tuple[bytes, bytes]:
    return md, (
        twin.replace(b'"value": "5479.73"', b'"value": "5479.74"', 1)
        if quarter == "FY26_Q3"
        else twin
    )


def _alter_cutoff(quarter: str, md: bytes, twin: bytes) -> tuple[bytes, bytes]:
    return (md.replace(b"**2026-02-04**", b"**2026-02-05**") if quarter == "FY26_Q3" else md), twin


def _extra_field(quarter: str, md: bytes, twin: bytes) -> tuple[bytes, bytes]:
    if quarter != "FY26_Q3":
        return md, twin
    return md, json.dumps({**json.loads(twin), "analyst_note": "unmapped"}).encode()


def _orphan_guidance(quarter: str, md: bytes, twin: bytes) -> tuple[bytes, bytes]:
    if quarter != "FY26_Q3":
        return md, twin
    body = json.loads(twin)
    orphan = {**body["guidance"][0], "quote": "an unledgered 30% promise", "lower_bound": "30"}
    return md, json.dumps({**body, "guidance": [*body["guidance"], orphan]}).encode()


@pytest.mark.retained
@pytest.mark.parametrize(
    "alter", [_alter_md, _alter_twin, _alter_cutoff, _extra_field, _orphan_guidance]
)
def test_an_altered_numeral_or_unmapped_field_fails_the_mapping(
    alter: Callable[[str, bytes, bytes], tuple[bytes, bytes]],
) -> None:
    """One altered numeral (in a slot, in a twin value, in a literal line) or a twin field with
    no slot, alias or literal fails that version's lossless check."""
    with pytest.raises(LosslessError, match="FY26_Q3"):
        map_all(alter)


@pytest.mark.retained
@pytest.mark.parametrize(
    ("lexeme", "bad"),
    [
        (b'"5479.73"', b'"n/a"'),
        # FY26_Q3's period_start, period_end and knowledge_cutoff (their first occurrences).
        (b'"2025-10-01"', b'"not-a-date"'),
        (b'"2025-12-31"', b'"not-a-date"'),
        (b'"2026-02-04"', b'"not-a-date"'),
    ],
)
def test_a_source_that_does_not_parse_fails_only_its_version(lexeme: bytes, bad: bytes) -> None:
    """A nonnumeric twin value or an unparsable date is that version's lossless failure, not an
    import-wide error: the earlier quarter still maps."""

    def alter(quarter: str, md: bytes, twin: bytes) -> tuple[bytes, bytes]:
        return md, (twin.replace(lexeme, bad, 1) if quarter == "FY26_Q3" else twin)

    with pytest.raises(LosslessError, match="FY26_Q3: not lossless: does not parse"):
        map_all(alter)


@pytest.mark.retained
@pytest.mark.parametrize("yaml_body", [b"", b"- a\n- b\n", b"thesis\n"])
def test_a_q0_yaml_root_that_is_not_a_mapping_fails_only_q0(yaml_body: bytes) -> None:
    """An empty, list-root or scalar-root Q0 YAML fails the Q0 version, not the import."""
    from fundamentals.ledger.falsifier_status import KINDS

    with pytest.raises(LosslessError, match="Q0: not lossless"):
        map_q0(read(Q0_MD), yaml_body, cutoff=date(2025, 11, 6), metrics=KINDS)


@pytest.mark.retained
def test_management_ledger_revisions_alias_the_whole_guidance_contract() -> None:
    """A management-ledger entry whose unit differs from its quarters' claims fails: a revision
    aliases a claim with its entry's whole guidance contract, not only its key and bounds."""
    body = json.loads(read(LEDGER))
    body["entries"][0]["unit"] = "USD per MT"
    with pytest.raises(LosslessError, match="revision of conductor_ebitda_per_mt"):
        map_all(ledger=json.dumps(body).encode())


def _leaves(node: Any, path: tuple[str, ...] = ()) -> Iterator[tuple[tuple[str, ...], Any]]:
    """Every scalar of a parsed twin with its path."""
    items = node.items() if isinstance(node, dict) else enumerate(node)
    for key, value in items:
        if isinstance(value, dict | list):
            yield from _leaves(value, (*path, str(key)))
        else:
            yield (*path, str(key)), value


def _changed(value: Any) -> Any:
    """Another value of the same lexical shape (an ISO time one second on)."""
    if isinstance(value, bool):
        return not value
    if isinstance(value, int | float):
        return value + 1
    if re.fullmatch(r"\d{4}-\d\d-\d\dT.*", value):
        return re.sub(r":(\d\d)(?=[.Z+])", lambda m: f":{(int(m[1]) + 1) % 60:02d}", value, count=1)
    if value in QUARTERS[1:]:  # a valid quarter, the one before (FY26_Q3 to FY26_Q2)
        return QUARTERS[QUARTERS.index(value) - 1]
    return value + ("7" if re.fullmatch(r"-?\d+(\.\d+)?", value) else "~")


def _content(mapped: MappedVersion) -> dict[str, Any]:
    """What an import stores of a mapped version (``ledger`` is only the next quarters' check)."""
    return mapped.model_dump(exclude={"ledger"})


@pytest.mark.retained
@pytest.mark.parametrize("quarter", QUARTERS)
def test_every_twin_field_maps_but_the_approved_bookkeeping(quarter: str) -> None:
    """Changing any twin scalar changes the mapped version or fails it, unless it is one of the
    approved ``UNMAPPED_FIELDS`` (finding 6), which never change the mapped content."""
    mapped = map_all()
    earlier = {q: mapped[q] for q in QUARTERS[: QUARTERS.index(quarter)]}
    md, twin = (read(path) for path in update_paths(quarter))
    raw = json.loads(twin)
    for path, value in _leaves(raw):
        if value is None:
            continue
        tree = copy.deepcopy(raw)
        *parents, leaf = path
        node: Any = tree
        for key in parents:
            node = node[int(key) if isinstance(node, list) else key]
        node[int(leaf) if isinstance(node, list) else leaf] = _changed(value)
        try:
            out = map_one(quarter, md, json.dumps(tree).encode(), earlier)
            changed = _content(out) != _content(mapped[quarter])
        except LosslessError:
            changed = None  # refused: an alias or check holds the field
        exempt = any(fnmatch.fnmatchcase(".".join(path), field) for field in UNMAPPED_FIELDS)
        # An exempt field never changes the mapped content; no other passes unchanged.
        assert changed is not exempt, ".".join(path)


@pytest.mark.retained
def test_q0_altered_threshold_fails() -> None:
    """A Q0 threshold must equal the predicate in its Markdown (``revenue_yoy_pct LT 11.55``)."""
    from fundamentals.ledger.falsifier_status import KINDS

    twin = read(Q0_YAML).replace(b"threshold: 11.55", b"threshold: 11.56")
    with pytest.raises(LosslessError):
        map_q0(read(Q0_MD), twin, cutoff=date(2025, 11, 6), metrics=KINDS)


def _git(repo: Path, *args: str, date_iso: str = "2026-09-07T11:44:46+00:00") -> str:
    """Run git in ``repo`` with a fixed identity and commit date."""
    env = {"GIT_AUTHOR_DATE": date_iso, "GIT_COMMITTER_DATE": date_iso, "PATH": "/usr/bin:/bin"}
    identity = ("-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid")
    done = subprocess.run(
        ["git", *identity, "-C", str(repo), *args],
        check=True,
        capture_output=True,
        env=env,
        timeout=30,
    )
    return done.stdout.decode().strip()


def _commit(repo: Path, files: dict[str, bytes], date_iso: str) -> str:
    """Commit ``files`` into ``repo`` (initialised if new) and return the commit id."""
    if not (repo / ".git").exists():
        repo.mkdir(parents=True, exist_ok=True)
        _git(repo, "init", "-q")
    for path, body in files.items():
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_bytes(body)
    _git(repo, "add", *files)
    _git(repo, "commit", "-q", "-m", "fixture", date_iso=date_iso)
    return _git(repo, "rev-parse", "HEAD")


@pytest.mark.retained
def test_evidence_rule(tmp_path: Path) -> None:
    """The rule holds only for a commit holding the imported bytes, dated the decided-on day
    (UTC); its value is the files' SHA-256s."""
    files = {Q0_MD: read(Q0_MD), Q0_YAML: read(Q0_YAML)}
    held = _commit(tmp_path / "held", files, "2026-09-07T23:59:00+00:00")
    late = _commit(tmp_path / "late", files, "2026-09-08T00:00:01+00:00")
    other = _commit(
        tmp_path / "other", {**files, Q0_MD: b"# other bytes\n"}, "2026-09-07T10:00:00+00:00"
    )
    decided_on = date(2026, 9, 7)
    assert evidence_holds(tmp_path / "held", held, files, decided_on) == ",".join(
        PINNED[path] for path in files
    )
    assert evidence_holds(tmp_path / "late", late, files, decided_on) is None
    assert evidence_holds(tmp_path / "other", other, files, decided_on) is None
    assert evidence_holds(tmp_path / "held", "0" * 40, files, decided_on) is None


def _decisions(cited: Cited, version_id: int) -> list[tuple[Any, ...]]:
    return cited.query(
        "SELECT kind, decider, ruling, decided_on, original_approval_sha256 FROM eqos.decisions "
        "WHERE subject_kind = 'REPORT_VERSION' AND subject_id = %s ORDER BY sequence",
        version_id,
    )


@pytest.mark.pg
@pytest.mark.retained
def test_import_over_retained_sources(cited: Cited) -> None:
    """Acquisitions first; each version sealed by ``IMPORT_SEAL`` through the panel login with its
    sources stored; updates ``HISTORICAL``, Q0 ``APPROVED`` by its evidence; QA records, never
    decisions; a ``RETROSPECTIVE`` validation each; every ledger history revision a claim."""
    config = load_import_config(CONFIG)
    results = import_versions(
        cited.pools[PgRole.PANEL],
        config,
        repo=REPO,
        catalog=cited.catalog,
        snapshots=cited.snapshots,
    )
    assert [(r.period, r.kind, r.status, r.failure) for r in results] == [
        *((q, ReportKind.EARNINGS_UPDATE, VersionStatus.HISTORICAL, None) for q in QUARTERS),
        ("FY26_Q2", ReportKind.BOOTSTRAP_THESIS, VersionStatus.APPROVED, None),
    ]
    versions = {(r.period, r.kind): r.version_id for r in results}
    evidence = ",".join(PINNED[path] for path in (Q0_MD, Q0_YAML))
    with cited.runtime() as cursor:
        drafts = {key: store.read_version(cursor, vid) for key, vid in versions.items() if vid}
        for vid in versions.values():
            assert vid is not None and version_status(cursor, vid) is not VersionStatus.DRAFT
    for (period, kind), draft in drafts.items():
        version_id = versions[(period, kind)]
        assert version_id is not None
        update = kind is ReportKind.EARNINGS_UPDATE
        paths = [*update_paths(period), LEDGER] if update else [Q0_MD, Q0_YAML]
        assert draft.import_sources == tuple((p, read(p)) for p in paths)
        assert draft.content_hash == content_hash(draft.sections, draft.claims)
        if update:
            assert narrative(draft.sections, draft.claims) == read(paths[0])
        expected = [("IMPORT_SEAL", "PANEL", None, None, None)]
        if not update:
            approval = ("IMPORTED_APPROVAL", "PANEL", "accept all", date(2026, 9, 7), evidence)
            expected.append(approval)
        assert _decisions(cited, version_id) == expected
        gates = cited.query("SELECT gate FROM eqos.qa_records WHERE version_id = %s", version_id)
        assert sorted(g for (g,) in gates) == (
            ["cross_check", "cross_foot", "sec_cross_check"] if update else []
        )
        with cited.runtime() as cursor:
            validation = store.latest_validation(cursor, version_id)
        assert validation is not None and validation.mode is RunMode.RETROSPECTIVE
        assert {k for k, _ in validation.claim_states} == {c.claim_key for c in draft.claims}
    states = {
        key: dict(store_states)
        for key, store_states in (
            (key, _states(cited, vid)) for key, vid in versions.items() if vid is not None
        )
    }
    assert states[("FY27_Q1", ReportKind.EARNINGS_UPDATE)]["fact.revenue"] is ClaimState.POST_CUTOFF
    q0 = states[("FY26_Q2", ReportKind.BOOTSTRAP_THESIS)]
    assert q0 == {f"falsifier.{fid}": ClaimState.MATCH for fid in THRESHOLDS}
    acquisitions = cited.query("SELECT count(*) FROM eqos.legacy_acquisitions")
    assert acquisitions[0][0] == len(json.loads(read_manifest())["entries"])
    for entry in json.loads(read(LEDGER))["entries"]:
        claim_key = f"ledger.{entry['metric']}.{entry['horizon']}.{entry['scope']}"
        for revision in entry["history"]:
            draft = drafts[(revision["issuer_quarter"], ReportKind.EARNINGS_UPDATE)]
            (claim,) = (c for c in draft.claims if c.claim_key == claim_key)
            bounds = (Decimal(revision["lower_bound"]), Decimal(revision["upper_bound"]))
            assert (claim.lower_bound, claim.upper_bound) == bounds


def read_manifest() -> bytes:
    """The retrieval manifest the config pins."""
    return (REPO / load_import_config(CONFIG).retrieval_manifest).read_bytes()


def _states(cited: Cited, version_id: int) -> tuple[tuple[str, ClaimState], ...]:
    with cited.runtime() as cursor:
        validation = store.latest_validation(cursor, version_id)
    assert validation is not None
    return validation.claim_states


@pytest.mark.pg
@pytest.mark.retained
def test_failed_version_persists_nothing_and_other_bytes_give_historical(
    cited: Cited, pg_db: PgTestDatabase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Through ``ledger import`` as the panel login: an update with one altered numeral, and one
    with a nonnumeric value, fail and persist no rows, the command exits refused, and the others
    still import; a backdated report ``retrieved_at`` is kept byte-for-byte in its import source
    and sets no acquisition time; Q0's evidence commit holding other bytes gives ``HISTORICAL``
    with no ``IMPORTED_APPROVAL``."""
    repo = tmp_path / "repo"
    config = load_import_config(CONFIG)
    for path in [*PINNED, config.retrieval_manifest]:
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / path, repo / path)
    commit = _commit(
        repo, {Q0_MD: b"# other bytes\n", Q0_YAML: read(Q0_YAML)}, "2026-09-07T11:00:00+00:00"
    )
    (repo / Q0_MD).write_bytes(read(Q0_MD))
    altered = repo / update_paths("FY27_Q1")[0]
    altered.write_bytes(altered.read_bytes().replace(b"6,591.06", b"6,591.07", 1))
    nonnumeric = repo / update_paths("FY26_Q4")[1]
    nonnumeric.write_bytes(nonnumeric.read_bytes().replace(b'"6602.81"', b'"n/a"', 1))
    # An approved bookkeeping field: a report-written retrieval time, backdated.
    stamped = repo / update_paths("FY26_Q3")[1]
    backdated = re.sub(
        rb'"retrieved_at": "\d{4}', b'"retrieved_at": "1999', stamped.read_bytes(), count=1
    )
    stamped.write_bytes(backdated)
    body = yaml.safe_load(CONFIG.read_text())
    body["q0"]["evidence_commit"] = commit
    config_path = tmp_path / "ledger_import.yaml"
    config_path.write_text(
        yaml.safe_dump(ImportConfig.model_validate(body).model_dump(mode="json"))
    )
    for name, value in pg_db.cli_env().items():
        monkeypatch.setenv(name, value)
    command = ["ledger", "import", "--config", str(config_path), "--repo", str(repo)]
    snapshot_root = str(cited.tmp_path / STORE_DIR)
    assert main([*command, "--snapshot-root", snapshot_root]) == EXIT_REFUSED
    rows = cited.query(
        "SELECT r.period, r.kind, v.id FROM eqos.reports r "
        "JOIN eqos.report_versions v ON v.report_id = r.id ORDER BY v.id"
    )
    assert [(period, kind) for period, kind, _ in rows] == [
        *((q, "EARNINGS_UPDATE") for q in QUARTERS[:2]),
        ("FY26_Q2", "BOOTSTRAP_THESIS"),
    ]
    stored = cited.query(
        "SELECT sha256 FROM eqos.import_sources WHERE version_id = %s AND source_path = %s",
        rows[1][2],
        update_paths("FY26_Q3")[1],
    )
    assert (
        stored
        == [(hashlib.sha256(backdated).hexdigest(),)]
        != [(PINNED[update_paths("FY26_Q3")[1]],)]
    )
    assert cited.query(
        "SELECT count(*) FROM eqos.legacy_acquisitions WHERE retrieved_at < '2000-01-01'"
    ) == [(0,)]
    with cited.runtime() as cursor:
        assert {version_status(cursor, vid) for _, _, vid in rows} == {VersionStatus.HISTORICAL}
    q0_id = rows[-1][2]
    assert [kind for kind, *_ in _decisions(cited, q0_id)] == [DecisionKind.IMPORT_SEAL]
    assert cited.query(
        "SELECT DISTINCT decider FROM eqos.decisions WHERE subject_kind = %s",
        SubjectKind.REPORT_VERSION.value,
    ) == [(DeciderRole.PANEL.value,)]


SUCCESSOR_MD = "docs/evidence/phase-0.5/q0-thesis-successor-1.md"
SUCCESSOR_YAML = "docs/evidence/phase-0.5/q0-thesis-successor-1.yaml"
Q0_ETR, FILED_ETR = b"effective_tax_rate_pct", b"filed_effective_tax_rate_pct"
TODAY = "2026-10-23T10:00:00+00:00"
ROWS = (
    "SELECT (SELECT count(*) FROM eqos.report_versions), (SELECT count(*) FROM eqos.decisions), "
    "(SELECT count(*) FROM eqos.import_sources)"
)


@pytest.mark.pg
@pytest.mark.retained
def test_a_thesis_successor_imports_onto_the_chain(cited: Cited, tmp_path: Path) -> None:
    """The successor (F5 re-registered on the filed tax rate) refuses with nothing written
    while its evidence fails, then imports as Q0's ``APPROVED`` successor, which ``SUPERSEDED``
    Q0 and is the thesis a run binds, evaluating F5 on the ETR line; a repeat refuses."""
    repo = tmp_path / "repo"
    config = load_import_config(CONFIG)
    for path in (config.retrieval_manifest, LEDGER):
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / path, repo / path)
    q0_commit = _commit(repo, {Q0_MD: read(Q0_MD), Q0_YAML: read(Q0_YAML)}, TODAY)
    twin = read(Q0_YAML).replace(Q0_ETR, FILED_ETR)
    files = {SUCCESSOR_MD: read(Q0_MD).replace(Q0_ETR, FILED_ETR), SUCCESSOR_YAML: twin}
    successor_commit = _commit(repo, files, TODAY)
    today = date.fromisoformat(TODAY[:10])
    q0 = config.q0.model_copy(update={"evidence_commit": q0_commit, "decided_on": today})
    entry = q0.model_copy(
        update={
            "markdown": SUCCESSOR_MD,
            "twin": SUCCESSOR_YAML,
            "evidence_commit": successor_commit,
        }
    )
    late = entry.model_copy(update={"decided_on": date(2026, 10, 24)})
    body = {"earnings_updates": (), "q0": q0}
    wrong, right = (config.model_copy(update=body | {"thesis_successor": e}) for e in (late, entry))
    panel, sources = cited.pools[PgRole.PANEL], {"catalog": cited.catalog}
    sources |= {"snapshots": cited.snapshots}
    (root,) = import_versions(panel, right, repo=repo, **sources)
    assert root.status is VersionStatus.APPROVED and root.version_id is not None
    before = cited.query(ROWS)
    refused = import_thesis_successor(panel, wrong, repo=repo, **sources)
    assert refused.failure and cited.query(ROWS) == before
    with cited.runtime() as cursor:
        assert version_status(cursor, root.version_id) is VersionStatus.APPROVED
    imported = import_thesis_successor(panel, right, repo=repo, **sources)
    assert imported.status is VersionStatus.APPROVED and imported.version_id is not None
    ((entity_id,),) = cited.query(
        "SELECT id FROM eqos.reporting_entities WHERE entity_key = %s", config.stock
    )
    with cited.runtime() as cursor:
        assert store.read_version(cursor, imported.version_id).predecessor_id == root.version_id
        assert version_status(cursor, root.version_id) is VersionStatus.SUPERSEDED
        bound = approved_thesis(cursor, entity_id, config.stock, datetime.now(UTC))
        digest = store.sealed_digest(cursor, imported.version_id)
    assert bound is not None and bound.version_id == imported.version_id
    after = cited.query(ROWS)
    again = import_thesis_successor(panel, right, repo=repo, **sources)
    assert "already imported" in (again.failure or "") and cited.query(ROWS) == after
    (f5,) = (f for f in parse_thesis(twin).falsifiers if f.falsifier_id == "F5")
    assert f5.predicate.threshold is not None
    etr = NumericClaim(
        claim_key="calc.3",
        section_key=CALCS,
        citation=Citation(kind=CitationKind.CALCULATION),
        value_kind=ValueKind.PERCENTAGE,
        unit="%",
        value=f5.predicate.threshold,
        precision=2,
        rounding=Rounding.ROUND_HALF_EVEN,
        epistemic_class=EpistemicClass.COMPUTED,
    )
    rows = evaluate(bound, {}, (Line(section=CALCS, label=ETR_LABEL, claims=(etr,)),))
    (row,) = (r for r in rows if r.falsifier_id == "F5")
    held = Disposition.WEAKENED if f5.predicate.holds(etr.value or 0) else Disposition.HELD
    assert (row.disposition, row.claim_key) == (held, "calc.3")
    (threshold,) = derived(bound, rows)[1]
    ((row_id,),) = cited.query(
        "SELECT id FROM eqos.numeric_claims WHERE version_id = %s AND claim_key = 'falsifier.F5'",
        imported.version_id,
    )
    assert threshold.claim_key == "thesis.F5"
    assert threshold.citation == Citation(
        kind=CitationKind.THESIS_CLAIM, cited_claim_id=row_id, cited_sealed_digest=digest
    )


@pytest.mark.pg
@pytest.mark.retained
def test_a_successor_a_run_could_not_bind_is_refused(cited: Cited, tmp_path: Path) -> None:
    """A successor that maps losslessly but whose twin the binder rejects (an op the parser
    does not register, another stock's symbol) is refused with nothing written, so Q0 stays
    the approved head a run binds."""
    repo = tmp_path / "repo"
    config = load_import_config(CONFIG)
    for path in (config.retrieval_manifest, LEDGER):
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / path, repo / path)
    q0_commit = _commit(repo, {Q0_MD: read(Q0_MD), Q0_YAML: read(Q0_YAML)}, TODAY)
    q0 = config.q0.model_copy(
        update={"evidence_commit": q0_commit, "decided_on": date.fromisoformat(TODAY[:10])}
    )
    sources = {"catalog": cited.catalog, "snapshots": cited.snapshots}
    panel = cited.pools[PgRole.PANEL]
    body = {"earnings_updates": (), "q0": q0}
    (root,) = import_versions(panel, config.model_copy(update=body), repo=repo, **sources)
    assert root.version_id is not None
    ((entity_id,),) = cited.query(
        "SELECT id FROM eqos.reporting_entities WHERE entity_key = %s", config.stock
    )
    md, twin = read(Q0_MD), read(Q0_YAML)
    unparseable = (
        md.replace(b"revenue_yoy_pct LT ", b"revenue_yoy_pct BETWEEN "),
        twin.replace(b'op: "LT"', b'op: "BETWEEN"', 1),
    )
    other_stock = (md.replace(b"APARINDS", b"OTHERCO"), twin.replace(b"APARINDS", b"OTHERCO"))
    for bad_md, bad_twin in (unparseable, other_stock):
        commit = _commit(repo, {SUCCESSOR_MD: bad_md, SUCCESSOR_YAML: bad_twin}, TODAY)
        entry = q0.model_copy(
            update={"markdown": SUCCESSOR_MD, "twin": SUCCESSOR_YAML, "evidence_commit": commit}
        )
        before = cited.query(ROWS)
        refused = import_thesis_successor(
            panel,
            config.model_copy(update=body | {"thesis_successor": entry}),
            repo=repo,
            **sources,
        )
        assert "could not bind" in (refused.failure or "") and cited.query(ROWS) == before
        with cited.runtime() as cursor:
            bound = approved_thesis(cursor, entity_id, config.stock, datetime.now(UTC))
        assert bound is not None and bound.version_id == root.version_id
