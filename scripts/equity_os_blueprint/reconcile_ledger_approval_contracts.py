#!/usr/bin/env python3
"""Prepare, execute, and recover the hash-bound RC-2/RC-3/RC-4 transaction."""

from __future__ import annotations

import argparse
import copy
import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


SCHEMA = "equity-os.rc234-reconciliation-manifest/v1"
JOURNAL_SCHEMA = "equity-os.rc234-reconciliation-journal/v1"
TARGET_ORDER = (
    "docs/goals/equity-os-blueprint-completion.md",
    "scripts/equity_os_blueprint/validate_ledger_structural.py",
    "docs/goals/equity-os-blueprint-component-ledger.jsonl",
    "docs/goals/equity-os-blueprint-human-review-needed.md",
)
GOAL_VALIDATOR_HEADER = (
    "#!/usr/bin/env python3\n"
    '\"\"\"Generated verbatim from docs/goals/equity-os-blueprint-completion.md.\"\"\"\n\n'
)
R1_MANIFEST = (
    "docs/goals/reviews/ledger/"
    "equity-os-blueprint-rc234-reconciliation-manifest-r1.json"
)
R1_MANIFEST_SHA256 = "e9cbc6d88f5781ce80c868ef1e558642eab0f2862eaece60231fb964fff1cdbe"
IMMUTABLE_BUILDER_INPUTS = {
    "scripts/equity_os_blueprint/validate_ledger_preimplementation.py": "f7a225a1f99cb85c92cde3094505a92a746552280eb45dae0253a71ab9048013",
    "scripts/equity_os_blueprint/extract_goal_validators.py": "5d20d796666d1154fb3c84ba4fa7407ee82819510a5ac06254f7f4a3126c6f2a",
}
TERMINAL_STATES = {"COMMITTED", "ROLLED_BACK"}
NONTERMINAL_STATES = {
    "INITIALIZED", "PREPARED", "REPLACING", "POSTVALIDATING",
    "ROLLING_BACK", "RECOVERY_REQUIRED",
}
EXACT_AFFIRMATIVE_ANSWER = (
    "I AUTHORIZE THE EXACT HASH-BOUND FOUR-FILE RC-2/RC-3/RC-4 "
    "RECONCILIATION PACKAGE."
)
_OUTCOME_TOKENS = ("<LEDGER_POST_SHA256>", "<HUMAN_REVIEW_POST_SHA256>")
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


class ResponseDependentCandidates:
    """In-memory candidates and the journal-only outcome bindings."""

    def __init__(self, candidates: dict[str, bytes], authorization_outcomes: dict[str, str]) -> None:
        self.candidates = candidates
        self.authorization_outcomes = authorization_outcomes


class ReconciliationError(RuntimeError):
    """Raised when the transaction cannot prove a safe next operation."""


class _TransactionSignal(BaseException):
    """A real termination signal delivered during the replacement window."""


_EVIDENCE_REQUIREMENTS = {
    "HR-EV-0006-SPEC": ("DESIGN_AUTHOR", None, None, None),
    "HR-EV-0006-SPEC-REVIEW": ("REVIEWER", "gpt-5.6-sol", "high", "CLEAN"),
    "HR-EV-0006-DESIGN": ("DESIGN_AUTHOR", None, None, None),
    "HR-EV-0006-MANIFEST": ("DESIGN_AUTHOR", None, None, None),
    "HR-EV-0006-DESIGN-REVIEW": ("REVIEWER", "gpt-5.6-sol", "high", "CLEAN"),
    "HR-EV-0006-IMPLEMENTATION": ("IMPLEMENTER", "gpt-5.6-terra", "high", None),
    "HR-EV-0006-IMPLEMENTATION-REVIEW": ("REVIEWER", "gpt-5.6-sol", "high", "CLEAN"),
    "HR-EV-0006-REHEARSAL": ("IMPLEMENTER", "gpt-5.6-terra", "high", None),
}


def _fault_matches(configured: str | set[str] | None, point: str) -> bool:
    """Match a test-only named crash boundary without interpreting input as code."""
    return point == configured or (isinstance(configured, set) and point in configured)


def canonical_json(value: Any) -> bytes:
    """Return the manifest's canonical UTF-8 JSON representation."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(value: bytes | Any) -> str:
    """Return a SHA-256 over file bytes or canonical JSON."""
    data = value if isinstance(value, bytes) else canonical_json(value)
    return hashlib.sha256(data).hexdigest()


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject JSON objects that would otherwise lose duplicate keys."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ReconciliationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_json(path: Path) -> dict[str, Any]:
    """Load a UTF-8 JSON object without accepting duplicate keys."""
    try:
        value = json.loads(path.read_bytes().decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReconciliationError(f"invalid JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise ReconciliationError(f"JSON root must be an object: {path}")
    return value


def _contains_placeholder(value: Any) -> bool:
    """Return whether a candidate contains an unresolved placeholder object."""
    if isinstance(value, dict):
        return "$placeholder" in value or any(_contains_placeholder(item) for item in value.values())
    return isinstance(value, list) and any(_contains_placeholder(item) for item in value)


def ensure_no_placeholders(value: Any) -> None:
    """Reject unresolved placeholders and obvious stand-ins in canonical output."""
    if _contains_placeholder(value):
        raise ReconciliationError("canonical candidate contains unresolved placeholder")
    rendered = value.decode("utf-8") if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False)
    if any(token in rendered for token in ("NON_CANONICAL_STAND_IN", "<LEDGER_POST_SHA256>", "<HUMAN_REVIEW_POST_SHA256>")):
        raise ReconciliationError("canonical candidate contains rehearsal or outcome placeholder")


def load_manifest(path: Path) -> dict[str, Any]:
    """Load and minimally validate the normative r1 manifest."""
    manifest = _load_json(path)
    if manifest.get("schema") != SCHEMA:
        raise ReconciliationError("unexpected reconciliation manifest schema")
    targets = manifest.get("prestate_bindings", {}).get("canonical_targets")
    if not isinstance(targets, list) or [item.get("path") for item in targets] != list(TARGET_ORDER):
        raise ReconciliationError("manifest canonical target order is not exact")
    components = manifest.get("components")
    if not isinstance(components, list) or len(components) != 22:
        raise ReconciliationError("manifest must define exactly 22 components")
    component_ids = [item.get("component_id") for item in components]
    if len(set(component_ids)) != 22 or any(not isinstance(item, str) for item in component_ids):
        raise ReconciliationError("manifest component IDs must be unique strings")
    return manifest


def _safe_target(root: Path, relative_path: str) -> Path:
    """Resolve one allowlisted repository-relative target without path escape."""
    if relative_path not in TARGET_ORDER:
        raise ReconciliationError(f"target is not allowlisted: {relative_path}")
    candidate = (root / relative_path).resolve(strict=False)
    try:
        candidate.relative_to(root.resolve())
    except ValueError as error:
        raise ReconciliationError(f"target escapes repository root: {relative_path}") from error
    return candidate


def _assert_safe_parent(root: Path, path: Path, *, workspace: bool = False) -> None:
    """Reject symlinked parents before opening a transaction-controlled path."""
    root = root.resolve()
    try:
        relative = path.relative_to(root)
    except ValueError as error:
        raise ReconciliationError(f"path escapes repository root: {path}") from error
    current = root
    for part in relative.parts[:-1]:
        current /= part
        if current.exists():
            meta = current.lstat()
            if stat.S_ISLNK(meta.st_mode) or not stat.S_ISDIR(meta.st_mode):
                raise ReconciliationError(f"unsafe transaction parent: {current.relative_to(root)}")
    if workspace and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=False)
        _assert_safe_parent(root, path)


def _safe_workspace_path(root: Path, relative_path: str) -> Path:
    """Resolve a private transaction workspace path without target allowlisting."""
    if Path(relative_path).is_absolute() or ".." in Path(relative_path).parts:
        raise ReconciliationError(f"workspace path escapes repository root: {relative_path}")
    candidate = (root / relative_path).resolve(strict=False)
    try:
        candidate.relative_to((root / "scratchpad/rc234-reconciliation").resolve())
    except ValueError as error:
        raise ReconciliationError(f"workspace path is outside transaction root: {relative_path}") from error
    _assert_safe_parent(root, candidate)
    return candidate


def _regular_file(path: Path, expected_mode: str | None = None) -> os.stat_result:
    """Reject links, special files, aliases, and mode drift for a target."""
    try:
        metadata = path.lstat()
    except OSError as error:
        raise ReconciliationError(f"target cannot be lstat'd: {path}: {error}") from error
    if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode) or metadata.st_nlink != 1:
        raise ReconciliationError(f"target is not a single-link regular file: {path}")
    if expected_mode is not None and stat.S_IMODE(metadata.st_mode) != int(expected_mode, 8):
        raise ReconciliationError(f"target mode drift: {path}")
    return metadata


def _owned_regular_file(path: Path, *, expected_mode: str | None = None) -> os.stat_result:
    """Require a local, non-aliased, current-user-owned regular source file."""
    metadata = _regular_file(path, expected_mode)
    if metadata.st_uid != os.geteuid():
        raise ReconciliationError(f"source is not owned by executing user: {path}")
    return metadata


def preflight_targets(root: Path, manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Verify four canonical preimages before any candidate or journal write."""
    captured: dict[str, dict[str, Any]] = {}
    for target in manifest["prestate_bindings"]["canonical_targets"]:
        path = _safe_target(root, target["path"])
        metadata = _regular_file(path, target["mode_octal"])
        content = path.read_bytes()
        if digest(content) != target["sha256"]:
            raise ReconciliationError(f"target hash drift: {target['path']}")
        captured[target["path"]] = {"bytes": content, "mode": stat.S_IMODE(metadata.st_mode)}
    return captured


def _embedded_program_spans(text: str) -> list[tuple[int, int]]:
    """Return the three embedded Python body spans without importing the extractor."""
    opener = "```bash\npython3 - <<'PY'\n"
    closer = "\nPY\n```"
    spans: list[tuple[int, int]] = []
    cursor = 0
    while True:
        start = text.find(opener, cursor)
        if start == -1:
            break
        body_start = start + len(opener)
        end = text.find(closer, body_start)
        if end == -1:
            raise ReconciliationError("unterminated embedded validator")
        spans.append((body_start, end))
        cursor = end + len(closer)
    if len(spans) != 3:
        raise ReconciliationError(f"expected exactly three embedded validators, found {len(spans)}")
    return spans


def _goal_programs(text: str) -> list[str]:
    """Extract goal programs using the immutable extractor's closed fence grammar."""
    return [text[start:end] + "\n" for start, end in _embedded_program_spans(text)]


def _protected_goal_span_digest(text: str) -> str:
    """Match the structural validator's normalized UTF-8 line-span digest rule."""
    lines = text.splitlines()
    if len(lines) < 5847:
        raise ReconciliationError("goal is shorter than protected HR-0004 span")
    span = "\n".join(lines[5790:5847]).strip(" \t\n\r\f\v")
    return hashlib.sha256(span.encode("utf-8")).hexdigest()


def _anchor_once(text: str, anchor: str, *, label: str) -> int:
    """Locate an anchor exactly once so candidate construction cannot guess."""
    positions: list[int] = []
    cursor = 0
    for line in text.splitlines(keepends=True):
        if line.strip() == anchor:
            positions.append(cursor + len(line) - len(line.lstrip()))
        cursor += len(line)
    if len(positions) != 1:
        raise ReconciliationError(f"{label} anchor multiplicity: {anchor!r}")
    return positions[0]


def _inject_line_in_region(source: str, start_anchor: str, end_anchor: str, line: str) -> str:
    """Insert one executable line by replacing a blank line inside an exact region."""
    start = _anchor_once(source, start_anchor, label="region start")
    end = _anchor_once(source, end_anchor, label="region end")
    if end <= start:
        raise ReconciliationError("validator region anchors are out of order")
    region = source[start:end]
    if "\n\n" not in region:
        raise ReconciliationError("validator region has no line-neutral insertion point")
    replacement = region.replace("\n\n", f"\n{line}\n", 1)
    if replacement.count("\n") != region.count("\n"):
        raise ReconciliationError("validator insertion changed protected line count")
    return source[:start] + replacement + source[end:]


def _replace_region_line_neutral(source: str, start_anchor: str, end_anchor: str, replacement: str) -> str:
    """Replace an exact region while preserving its newline count byte-for-byte elsewhere."""
    start = _anchor_once(source, start_anchor, label="region start")
    end = _anchor_once(source, end_anchor, label="region end")
    end = source.rfind("\n", 0, end) + 1
    if end <= start:
        raise ReconciliationError("validator region anchors are out of order")
    region = source[start:end]
    line_count = region.count("\n")
    if replacement.count("\n") > line_count:
        raise ReconciliationError("validator replacement exceeds line-neutral region capacity")
    replacement += "\n" * (line_count - replacement.count("\n"))
    return source[:start] + replacement + source[end:]


def _exec_line(source: str) -> str:
    """Embed a compact, auditable validator fragment without shifting protected lines."""
    return f"exec({source!r})"


def _candidate_contract_prose() -> str:
    """Return the closed post-HR-0004 prose contract with no response-derived values."""
    return """
## RC-2/RC-3/RC-4 reconciliation contract

This post-HR-0004 contract codifies, and does not satisfy, the reconciliation
requirements. RC-2 is the exact 20-row combined multi-spec approval contract:
one component-local delegated approval covers the complete sorted specification
set, and `equity-os.combined-spec-review/v1` accepts only the closed exact-key
manifest, a `REVIEWER` `CLEAN` verdict, and current approved specification
bytes. RC-3 retains its exact unresolved Vocabulary authority approval and its
mirrored typed DOMAIN evidence; RC-4 retains its exact unresolved Product owner
approval and has no typed evidence object.

HR-0006 is limited to the exact 22 affected component IDs. It records process
authority separation only: it cannot satisfy a delegated approval, a domain
acceptance, or a product decision. Each affected row appends exactly one
`AUTHORITY_RECONCILIATION` transition and retains every historical r0 link,
including the existing HR-0001, HR-0003, HR-0004, and HR-0005 links where they
already apply. The 62 immediate r1 reviews and three T2-only DISP-R-1 reviews
remain a boundary: r0 evidence is historical, the current recorder is
prohibited, and a separate reviewed recorder refresh is required before any
new current review is recorded.
""".lstrip("\n")


def build_goal_and_structural_candidates(root: Path, manifest_path: Path) -> dict[str, bytes]:
    """Build only the deterministic goal and extracted structural candidates in memory.

    The remaining two transaction targets depend on the future authoritative
    response and intentionally are not constructed by this pre-approval seam.
    """
    root = root.resolve()
    expected_manifest = (root / R1_MANIFEST).resolve()
    if manifest_path.resolve() != expected_manifest:
        raise ReconciliationError("builder requires the exact r1 manifest path")
    if digest(manifest_path.read_bytes()) != R1_MANIFEST_SHA256:
        raise ReconciliationError("r1 manifest hash drift")
    manifest = load_manifest(manifest_path)
    preimages = preflight_targets(root, manifest)
    for relative_path, expected_hash in IMMUTABLE_BUILDER_INPUTS.items():
        path = root / relative_path
        _regular_file(path)
        if digest(path.read_bytes()) != expected_hash:
            raise ReconciliationError(f"immutable builder input hash drift: {relative_path}")

    goal_path, structural_path = TARGET_ORDER[:2]
    goal_text = preimages[goal_path]["bytes"].decode("utf-8")
    if _protected_goal_span_digest(goal_text) != manifest["prestate_bindings"]["goal_line_anchor"]["recorded_content_sha256"]:
        raise ReconciliationError("protected HR-0004 span drift")
    programs = _goal_programs(goal_text)
    structural_source = preimages[structural_path]["bytes"].decode("utf-8")
    if not structural_source.startswith(GOAL_VALIDATOR_HEADER) or structural_source[len(GOAL_VALIDATOR_HEADER):] != programs[0]:
        raise ReconciliationError("current structural validator is not the first embedded program")
    if digest((GOAL_VALIDATOR_HEADER + programs[1]).encode("utf-8")) != IMMUTABLE_BUILDER_INPUTS["scripts/equity_os_blueprint/validate_ledger_preimplementation.py"]:
        raise ReconciliationError("embedded preimplementation validator drift")

    components = manifest["components"]
    rc2 = [item for item in components if item["mutation_class"].startswith("RC2_")]
    rc2_table = [
        {
            "component_id": item["component_id"],
            "spec_ids": item["applicable_spec_ids"],
            "approval_id": item["delegated_approval_id"],
            "scope": item["delegated_scope_after"],
            "spec_review_id": item.get("spec_review_id"),
        }
        for item in rc2
    ]
    rc2_code = "\n".join((
        "_rc234_rc2 = json.loads(" + repr(json.dumps(rc2_table, sort_keys=True)) + ")",
        "if 'HR-0006' in human_entries:",
        "    assert len(_rc234_rc2) == 20 and len({x['component_id'] for x in _rc234_rc2}) == 20",
        "    for _item in _rc234_rc2:",
        "        _row = by_id[_item['component_id']]; _scope = _row['scope_derivation']['applicable_spec_ids']; assert _scope == _item['spec_ids'] == sorted(set(_scope)) and len(_scope) > 1",
        "        _requirements = [x for x in _row['required_approvals'] if x['approval_id'] == _item['approval_id']]; assert len(_requirements) == 1 and _requirements[0]['approval_type'] == 'DELEGATED_ARTIFACT_APPROVAL' and _requirements[0]['scope'] == _item['scope']",
        "        _reviews = [x for x in _row['required_evidence'] if x['evidence_id'].endswith('SPEC-REVIEW')]; assert ([x['evidence_id'] for x in _reviews] == [_item['spec_review_id']] and _reviews[0]['scope'] == _item['scope']) if _item['spec_review_id'] else not _reviews",
        "        if _requirements[0]['status'] == 'SATISFIED':",
        "            _record = next(x for x in _row['approval_records'] if x['approval_record_id'] == _requirements[0]['matched_record_id']); _docs = [json.loads(repo_path(x['path'], must_exist=True).read_text(encoding='utf-8')) for x in _row['evidence_refs'] if x['evidence_ref_id'] in _record['evidence_ref_ids'] and repo_path(x['path'], must_exist=True).suffix == '.json']; _combined = [x for x in _docs if x.get('schema') == 'equity-os.combined-spec-review/v1']; assert len(_combined) == 1",
        "            _combined = _combined[0]; assert set(_combined) == {'schema','component_id','role','role_binding_path','role_binding_sha256','model','effort','verdict','timestamp','specifications'} and _combined['component_id'] == _item['component_id'] and _combined['role'] == 'REVIEWER' and _combined['role_binding_path'] == 'CONTEXT.md' and _combined['role_binding_sha256'] == hashlib.sha256(repo_path('CONTEXT.md', must_exist=True).read_bytes()).hexdigest() and _combined['verdict'] == 'CLEAN'",
        "            _specs = _combined['specifications']; assert [_s['spec_id'] for _s in _specs] == _item['spec_ids'] and all(set(_s) == {'spec_id','path','sha256'} and _s['path'].startswith('docs/specs/') and hashlib.sha256(repo_path(_s['path'], must_exist=True).read_bytes()).hexdigest() == _s['sha256'] for _s in _specs) and set(_record['evidence_ref_ids']) >= {x['evidence_ref_id'] for x in _row['evidence_refs'] if x.get('path') in {_s['path'] for _s in _specs}}",
    ))
    rc3 = manifest["rc3_appended_objects"]
    rc4 = manifest["rc4_appended_object"]
    pins = {item["component_id"]: item for item in components}
    pin_code = "\n".join((
        "_rc234_pins = json.loads(" + repr(json.dumps(pins, sort_keys=True)) + ")",
        "_rc234_rc3 = json.loads(" + repr(json.dumps(rc3, sort_keys=True)) + ")",
        "_rc234_rc4 = json.loads(" + repr(json.dumps(rc4, sort_keys=True)) + ")",
        "if 'HR-0006' in human_entries:",
        "    assert set(_rc234_pins) == {'SEQ-02','SEQ-03','SEQ-04','SEQ-08','DISP-6-2','DISP-6-4','DISP-6-6','DISP-6-7','DISP-6-9','DISP-G-1','DISP-G-4','DISP-G-5','DISP-M-3','DISP-M-4','DISP-M-5','DISP-M-6','DISP-M-8','DISP-M-9','DISP-R-1','DISP-R-5','DISP-T-4','REG-A-09'}",
        "    _m3 = by_id['DISP-M-3']; assert [x for x in _m3['required_approvals'] if x['approval_id'] == _rc234_rc3['approval']['approval_id']] == [_rc234_rc3['approval']] and [x for x in _m3['required_evidence'] if x['evidence_id'] == _rc234_rc3['evidence']['evidence_id']] == [_rc234_rc3['evidence']]",
        "    _a09 = by_id['REG-A-09']; assert [x for x in _a09['required_approvals'] if x['approval_id'] == _rc234_rc4['approval_id']] == [_rc234_rc4] and not [x for x in _a09['required_evidence'] if x['approval_ids'] == [_rc234_rc4['approval_id']]] and not _a09['approval_records']",
    ))
    hr_code = "\n".join((
        "_rc234_links = json.loads(" + repr(json.dumps({item["component_id"]: item["human_review_after"] for item in components}, sort_keys=True)) + ")",
        "_rc234_target_ids = set(_rc234_links)",
        "_rc234_hr = human_entries.get('HR-0006')",
        "_rc234_hr0005 = human_entries.get('HR-0005'); _rc234_overlapping = {c for c, links in human_review_links.items() if len(links) > 1}",
        "for _entry_id in ('HR-0001', 'HR-0002', 'HR-0003'): assert human_entries[_entry_id]['state'] == 'OPEN_BLOCKING' and human_entries[_entry_id]['resolution_decision_ids'] == []",
        "_rc234_hr0004_resolutions = [r for r in human_resolutions.values() if r['human_review_id'] == 'HR-0004']; assert len(_rc234_hr0004_resolutions) == 1 and _rc234_hr0004_resolutions[0]['decision_type'] == 'RECONCILE_AUTHORITY' and _rc234_hr0004_resolutions[0]['decision_id'] in active_human_resolutions and _rc234_hr0004_resolutions[0]['actor']['actor_type'] == 'HUMAN' and _rc234_hr0004_resolutions[0]['actor']['role'] == 'CURRENT_USER' and human_entries['HR-0004']['decision_authority']['approval_type'] == 'GOAL_OR_PROCESS_AUTHORIZATION' and _rc234_hr0004_resolutions[0]['authority_basis']['approval_type'] == 'GOAL_OR_PROCESS_AUTHORIZATION'",
        "assert not _rc234_hr0005 or (human_scope_components['HR-0005'] == frozenset({'DISP-R-1'}) and human_review_links['DISP-R-1'] == frozenset({'HR-0004', 'HR-0005'} | ({'HR-0006'} if _rc234_hr else set())))",
        "if _rc234_hr:",
        "    assert human_scope_components['HR-0006'] == frozenset(_rc234_target_ids) and _rc234_hr['entry_type'] == 'DECISION' and _rc234_hr['state'] == 'RESOLVED' and _rc234_hr['decision_authority']['approval_type'] == 'GOAL_OR_PROCESS_AUTHORIZATION' and _rc234_hr['resolution_decision_ids'] == ['HRD-0006-001']",
        "    _rc234_resolution = human_resolutions['HRD-0006-001']; assert _rc234_resolution['human_review_id'] == 'HR-0006' and _rc234_resolution['decision_type'] == 'RECONCILE_AUTHORITY' and _rc234_resolution['actor']['actor_type'] == 'HUMAN' and _rc234_resolution['actor']['role'] == 'CURRENT_USER'",
        "    assert all(human_review_links[_component] == frozenset(_links) for _component, _links in _rc234_links.items()) and all(('HR-0006' in _links) == (_component in _rc234_target_ids) for _component, _links in human_review_links.items())",
        "    assert _rc234_target_ids <= _rc234_overlapping and 'DISP-R-1' in _rc234_overlapping",
    ))
    mutated_program = programs[0]
    mutated_program = _inject_line_in_region(mutated_program, "requirement_fields = {", "matched_record_ids = set()", _exec_line(rc2_code))
    mutated_program = _inject_line_in_region(mutated_program, "EXPECTED_DISPOSITION_CROSSWALK = {", "EXPECTED_COMMAND_PROOF_COMPONENTS = {", _exec_line(pin_code))
    mutated_program = _replace_region_line_neutral(
        mutated_program,
        "for entry_id, expected_components in EXPECTED_PRIOR_HR_LINKS.items():",
        "overlapping = {c for c, links in human_review_links.items() if len(links) > 1}",
        "if 'HR-0006' not in human_entries: assert all(human_review_links[c] == frozenset({e, 'HR-0004'}) for e, cs in EXPECTED_PRIOR_HR_LINKS.items() for c in cs)",
    )
    mutated_program = _replace_region_line_neutral(mutated_program, "overlapping = {c for c, links in human_review_links.items() if len(links) > 1}", 'for entry_id in ("HR-0001", "HR-0002", "HR-0003"):', _exec_line(hr_code))
    compile(mutated_program, "<candidate-structural-validator>", "exec")
    if mutated_program.count("\n") != programs[0].count("\n"):
        raise ReconciliationError("first embedded validator line count drift")

    spans = _embedded_program_spans(goal_text)
    first_start, first_end = spans[0]
    candidate_goal = goal_text[:first_start] + mutated_program[:-1] + goal_text[first_end:]
    prefix_line_count = len(goal_text.splitlines()[:5847])
    if len(candidate_goal.splitlines()[:5847]) != prefix_line_count or _protected_goal_span_digest(candidate_goal) != manifest["prestate_bindings"]["goal_line_anchor"]["recorded_content_sha256"]:
        raise ReconciliationError("goal protected prefix drift")
    candidate_goal += "\n\n" + _candidate_contract_prose()
    candidate_programs = _goal_programs(candidate_goal)
    if candidate_programs[1] != programs[1] or candidate_programs[2] != programs[2]:
        raise ReconciliationError("nonstructural embedded validator drift")
    candidate_structural = (GOAL_VALIDATOR_HEADER + candidate_programs[0]).encode("utf-8")
    return {goal_path: candidate_goal.encode("utf-8"), structural_path: candidate_structural}


def _parse_utc(value: Any, *, label: str) -> dt.datetime:
    """Parse one explicit RFC3339 UTC instant without consulting a local clock."""
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ReconciliationError(f"{label} must be RFC3339 UTC")
    try:
        parsed = dt.datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise ReconciliationError(f"{label} must be RFC3339 UTC") from error
    if parsed.tzinfo != dt.timezone.utc:
        raise ReconciliationError(f"{label} must be UTC")
    return parsed


def _concrete_hash(value: Any, *, label: str, mode: str) -> str:
    """Accept real file digests canonically and explicit stand-ins only in rehearsal."""
    if isinstance(value, str) and _SHA256_RE.fullmatch(value):
        return value
    if mode == "rehearsal" and isinstance(value, str) and value.startswith("NON_CANONICAL_STAND_IN:"):
        return value
    raise ReconciliationError(f"{label} is not a concrete permitted digest")


def _require_mode(mode: str) -> None:
    if mode not in {"canonical", "rehearsal"}:
        raise ReconciliationError("mode must be canonical or rehearsal")


def _materialize_evidence_bindings(
    manifest: dict[str, Any], bindings: dict[str, Any], *, mode: str, root: Path | None = None,
) -> list[dict[str, Any]]:
    """Resolve the manifest's eight ordered evidence bindings before rendering."""
    evidence_values = bindings.get("evidence")
    expected = manifest["human_review_construction"]["evidence_bindings"]
    if not isinstance(evidence_values, dict) or set(evidence_values) != {item["evidence_ref_id"] for item in expected}:
        raise ReconciliationError("authorization evidence bindings are not exact")
    timestamp = bindings.get("question_issued_at")
    _parse_utc(timestamp, label="question_issued_at")
    result: list[dict[str, Any]] = []
    for template in expected:
        evidence_id = template["evidence_ref_id"]
        value = evidence_values[evidence_id]
        if not isinstance(value, dict) or value.get("path") != template["path"]:
            raise ReconciliationError(f"evidence binding path mismatch: {evidence_id}")
        content_hash = _concrete_hash(value.get("sha256"), label=f"evidence binding {evidence_id}", mode=mode)
        for field in ("role", "model", "effort", "verdict", "reviewed_input_sha256"):
            if not isinstance(value.get(field), str) or not value[field]:
                raise ReconciliationError(f"evidence binding {evidence_id} lacks {field}")
        if value["verdict"] != "CLEAN":
            raise ReconciliationError(f"evidence binding {evidence_id} verdict is not CLEAN")
        if mode == "canonical":
            expected_role, expected_model, expected_effort, expected_verdict = _EVIDENCE_REQUIREMENTS[evidence_id]
            if value["role"] != expected_role:
                raise ReconciliationError(f"evidence binding role mismatch: {evidence_id}")
            if expected_model is not None and value["model"] != expected_model:
                raise ReconciliationError(f"evidence binding model mismatch: {evidence_id}")
            if expected_effort is not None and value["effort"] != expected_effort:
                raise ReconciliationError(f"evidence binding effort mismatch: {evidence_id}")
            if expected_verdict is not None and value["verdict"] != expected_verdict:
                raise ReconciliationError(f"evidence binding verdict mismatch: {evidence_id}")
            manifest_hash = template["sha256"]
            if isinstance(manifest_hash, str) and content_hash != manifest_hash:
                raise ReconciliationError(f"evidence binding manifest hash mismatch: {evidence_id}")
            reviewed_input = value["reviewed_input_sha256"]
            if evidence_id == "HR-EV-0006-SPEC-REVIEW" and reviewed_input != manifest["authority_inputs"]["specification"]["sha256"]:
                raise ReconciliationError("specification review input binding mismatch")
            if evidence_id == "HR-EV-0006-IMPLEMENTATION-REVIEW" and reviewed_input != bindings.get("implementation_sha256"):
                raise ReconciliationError("implementation review input binding mismatch")
            if evidence_id == "HR-EV-0006-DESIGN-REVIEW":
                expected_inputs = {bindings.get("design_sha256"), bindings.get("manifest_sha256")}
                actual_inputs = set(value.get("reviewed_input_sha256", "").split(","))
                if actual_inputs != expected_inputs:
                    raise ReconciliationError("design review input bindings mismatch")
        if root is not None and mode == "canonical":
            path = root / value["path"]
            _regular_file(path)
            if digest(path.read_bytes()) != content_hash:
                raise ReconciliationError(f"evidence binding hash drift: {evidence_id}")
        result.append({
            "evidence_ref_id": evidence_id,
            "path": template["path"],
            "scope": template["scope"],
            "content_sha256": content_hash,
            "digest_mode": "FILE_BYTES",
            "start_line": None,
            "end_line": None,
            "captured_at": timestamp,
        })
    return result


def render_authorization_question(
    manifest: dict[str, Any], bindings: dict[str, Any], *, mode: str = "canonical",
) -> str:
    """Render the single exact pre-response authorization question.

    All inputs except the two mandated post-construction outcome digests are
    concrete here. The function deliberately does not infer identity, reviews,
    timestamps, or poststate from the local environment.
    """
    _require_mode(mode)
    if manifest.get("schema") != SCHEMA:
        raise ReconciliationError("unexpected reconciliation manifest schema")
    goal_hash = _concrete_hash(bindings.get("goal_post_sha256"), label="goal post hash", mode=mode)
    structural_hash = _concrete_hash(bindings.get("structural_post_sha256"), label="structural post hash", mode=mode)
    evidence = _materialize_evidence_bindings(manifest, bindings, mode=mode)
    component_ids = manifest["human_review_construction"]["sorted_component_scope"]
    if component_ids != sorted(component_ids) or len(component_ids) != 22:
        raise ReconciliationError("manifest HR-0006 scope is not the exact sorted 22 IDs")
    lines = [
        "Does the authenticated CURRENT_USER authorize exactly this hash-bound four-file RC-2/RC-3/RC-4 reconciliation package?",
        "This authority codifies obligations and satisfies no RC-2, RC-3, or RC-4 approval, domain acceptance, or product decision.",
        f"Goal candidate SHA-256: {goal_hash}",
        f"Structural-validator candidate SHA-256: {structural_hash}",
        "Affected component IDs: " + ", ".join(component_ids),
        "Required evidence bindings:",
    ]
    lines.extend(
        f"- {item['evidence_ref_id']}: {item['path']} sha256={item['content_sha256']} role={bindings['evidence'][item['evidence_ref_id']]['role']} model={bindings['evidence'][item['evidence_ref_id']]['model']} effort={bindings['evidence'][item['evidence_ref_id']]['effort']} verdict=CLEAN"
        for item in evidence
    )
    lines.extend((
        f"The ledger post-construction SHA-256 is constrained outcome { _OUTCOME_TOKENS[0] }.",
        f"The human-review post-construction SHA-256 is constrained outcome { _OUTCOME_TOKENS[1] }.",
        "Answer exactly: " + EXACT_AFFIRMATIVE_ANSWER,
    ))
    rendered = "\n".join(lines)
    if any(token not in rendered for token in _OUTCOME_TOKENS) or rendered.count(_OUTCOME_TOKENS[0]) != 1 or rendered.count(_OUTCOME_TOKENS[1]) != 1:
        raise ReconciliationError("authorization renderer did not preserve exactly two outcome tokens")
    if "$placeholder" in rendered or "<" in rendered.replace(_OUTCOME_TOKENS[0], "").replace(_OUTCOME_TOKENS[1], ""):
        raise ReconciliationError("authorization question has an unresolved placeholder")
    return rendered


def validate_authenticated_response(
    response: dict[str, Any], rendered_question: str, bindings: dict[str, Any], *,
    mode: str = "canonical", seen_response_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Validate one fresh, authenticated response without a clock fallback."""
    _require_mode(mode)
    if not isinstance(response, dict) or set(response) != {"response_id", "question", "answer", "actor", "timestamp"}:
        raise ReconciliationError("response record fields are not exact")
    response_id = response["response_id"]
    if not isinstance(response_id, str) or not response_id.strip():
        raise ReconciliationError("response ID is missing")
    if seen_response_ids is not None and response_id in seen_response_ids:
        raise ReconciliationError("response replay detected")
    if response["question"] != rendered_question:
        raise ReconciliationError("response question mismatch")
    if response["answer"] != EXACT_AFFIRMATIVE_ANSWER:
        raise ReconciliationError("response answer is not the exact affirmative authorization")
    actor = response["actor"]
    if not isinstance(actor, dict) or set(actor) != {"identity_id", "display_name", "role"}:
        raise ReconciliationError("response actor fields are not exact")
    if actor.get("role") != "CURRENT_USER" or not all(isinstance(actor.get(key), str) and actor[key].strip() for key in ("identity_id", "display_name")):
        raise ReconciliationError("response actor is not an authenticated CURRENT_USER")
    response_time = _parse_utc(response["timestamp"], label="response timestamp")
    issued = _parse_utc(bindings.get("question_issued_at"), label="question_issued_at")
    maximum = _parse_utc(bindings.get("validation_now"), label="validation_now")
    if response_time < issued or response_time > maximum:
        raise ReconciliationError("response timestamp is outside the authoritative question interval")
    if mode == "canonical" and any("NON_CANONICAL_STAND_IN" in str(value) for value in response.values()):
        raise ReconciliationError("canonical response contains rehearsal values")
    return copy.deepcopy(response)


def _runtime_sessions_root() -> Path:
    """Resolve the Codex sessions root without trusting a caller-supplied path."""
    codex_home = os.environ.get("CODEX_HOME")
    if not codex_home:
        raise ReconciliationError("CODEX_HOME is required for canonical response capture")
    root = Path(codex_home).expanduser().resolve() / "sessions"
    if not root.is_dir() or root.is_symlink():
        raise ReconciliationError("runtime Codex sessions root is unavailable or unsafe")
    return root


def _root_response_source(message_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Select one harness-issued root-thread user message from Codex JSONL."""
    thread_id = os.environ.get("CODEX_THREAD_ID")
    session_id = os.environ.get("CODEX_SESSION_ID")
    if not thread_id or thread_id != session_id:
        raise ReconciliationError("CODEX_THREAD_ID and CODEX_SESSION_ID must be present and equal")
    if not isinstance(message_id, str) or not message_id:
        raise ReconciliationError("explicit harness message ID is required")
    sessions = _runtime_sessions_root()
    matches = [path for path in sessions.rglob("*.jsonl") if thread_id in path.name]
    if len(matches) != 1:
        raise ReconciliationError("root Codex session filename selection is not unique")
    source = matches[0]
    try:
        source.relative_to(sessions)
    except ValueError as error:
        raise ReconciliationError("session source escapes runtime root") from error
    _owned_regular_file(source)
    initial_stat = source.stat()
    source_bytes = source.read_bytes()
    final_stat = source.stat()
    if (initial_stat.st_dev, initial_stat.st_ino, initial_stat.st_size, initial_stat.st_mtime_ns) != (final_stat.st_dev, final_stat.st_ino, final_stat.st_size, final_stat.st_mtime_ns):
        raise ReconciliationError("root response source changed while being read")
    selected: list[tuple[int, dict[str, Any]]] = []
    for line_number, raw in enumerate(source_bytes.splitlines(), 1):
        item = json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate_keys)
        if not isinstance(item, dict) or item.get("type") != "response_item":
            continue
        payload = item.get("payload")
        if not isinstance(payload, dict) or payload.get("type") != "message" or payload.get("role") != "user":
            continue
        if payload.get("id") != message_id or not str(payload.get("id", "")).strip():
            continue
        content = payload.get("content")
        metadata = payload.get("internal_chat_message_metadata_passthrough")
        if not isinstance(content, list) or len(content) != 1 or not isinstance(content[0], dict) or content[0].get("type") != "input_text":
            raise ReconciliationError("selected response lacks exactly one input_text")
        if not isinstance(content[0].get("text"), str):
            raise ReconciliationError("selected response input_text is not text")
        if not isinstance(item.get("timestamp"), str) or not isinstance(metadata, dict):
            raise ReconciliationError("selected response lacks timestamp metadata")
        event_time = _parse_utc(item["timestamp"], label="root response timestamp")
        create_time = _parse_utc(metadata.get("create_time"), label="root response create_time")
        if event_time != create_time or not isinstance(metadata.get("turn_id"), str) or not metadata["turn_id"]:
            raise ReconciliationError("selected response metadata is inconsistent")
        selected.append((line_number, item))
    if len(selected) != 1:
        raise ReconciliationError("explicit root response message ID is absent or duplicated")
    line_number, item = selected[0]
    payload = item["payload"]
    source_identity = str(source.relative_to(sessions))
    anchor = {
        "session_id": session_id,
        "thread_id": thread_id,
        "message_id": message_id,
        "turn_id": payload["internal_chat_message_metadata_passthrough"]["turn_id"],
        "source_file": source_identity,
        "source_line": line_number,
        "source_line_sha256": digest(source_bytes.splitlines(keepends=True)[line_number - 1]),
        "source_stat": {"dev": initial_stat.st_dev, "ino": initial_stat.st_ino, "size": initial_stat.st_size, "mtime_ns": initial_stat.st_mtime_ns},
    }
    response = {
        "response_id": message_id,
        "question": None,
        "answer": payload["content"][0]["text"],
        "actor": {"identity_id": f"current-user@codex-thread:{thread_id}", "display_name": "Current User", "role": "CURRENT_USER"},
        "timestamp": item["timestamp"],
    }
    return response, anchor


def _seen_canonical_response_ids(root: Path) -> set[str]:
    """Treat every prior canonical journal as a durable replay ledger."""
    journal_directory = root / "scratchpad/rc234-reconciliation/journal"
    if not journal_directory.exists():
        return set()
    _assert_safe_parent(root, journal_directory / "x")
    seen: set[str] = set()
    for path in journal_directory.glob("*.json"):
        _regular_file(path)
        journal = _load_json(path)
        if journal.get("mode") == "CANONICAL" and isinstance(journal.get("response_anchor"), dict):
            response_id = journal["response_anchor"].get("message_id")
            if isinstance(response_id, str):
                seen.add(response_id)
    return seen


def _replace_placeholder(value: Any, replacement: Any) -> Any:
    """Replace one typed template placeholder, refusing unexpected template shapes."""
    if isinstance(value, dict) and set(value) == {"$placeholder"}:
        return replacement
    return value


def _human_payload_bounds(text: str) -> tuple[int, int, dict[str, Any]]:
    begin = "<!-- BEGIN CANONICAL HUMAN REVIEW JSON -->"
    end = "<!-- END CANONICAL HUMAN REVIEW JSON -->"
    if text.count(begin) != 1 or text.count(end) != 1:
        raise ReconciliationError("human review markers are not exact")
    start = text.index(begin) + len(begin)
    finish = text.index(end, start)
    payload_text = text[start:finish].strip()
    if not payload_text.startswith("```json") or not payload_text.endswith("```"):
        raise ReconciliationError("human review JSON fence is not exact")
    payload = json.loads(payload_text[len("```json"): -3].strip(), object_pairs_hook=_reject_duplicate_keys)
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "entries", "resolutions"}:
        raise ReconciliationError("human review payload is not exact")
    return start, finish, payload


def _indent_json(value: dict[str, Any], spaces: int) -> str:
    prefix = " " * spaces
    return "\n".join(prefix + line for line in json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).splitlines())


def _append_human_values(text: str, entry: dict[str, Any], resolution: dict[str, Any]) -> bytes:
    """Append values without reserializing any existing canonical JSON value."""
    start, finish, _ = _human_payload_bounds(text)
    payload = text[start:finish]
    entries_marker = '\n  ],\n  "resolutions": ['
    resolutions_marker = '\n  ],\n  "schema_version": 1\n'
    if payload.count(entries_marker) != 1 or payload.count(resolutions_marker) != 1:
        raise ReconciliationError("human review append locations are ambiguous")
    entry_block = _indent_json(entry, 4)
    resolution_block = _indent_json(resolution, 4)
    payload = payload.replace(entries_marker, ",\n" + entry_block + entries_marker, 1)
    payload = payload.replace(resolutions_marker, ",\n" + resolution_block + resolutions_marker, 1)
    return (text[:start] + payload + text[finish:]).encode("utf-8")


def _static_projection(row: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    return {key: row[key] for key in keys}


def _append_transition(row: dict[str, Any], component: dict[str, Any], resolution_hash: str, timestamp: str) -> None:
    template = component  # Named to make every manifest row dependency explicit.
    transition = {
        "actor": {"actor_id": "rc234-reconciliation-implementer", "actor_type": "AGENT", "role": "IMPLEMENTER"},
        "evidence_ref_ids": [template["transition"]["source_evidence_ref_id"]],
        "field": "human_review_id",
        "human_resolution_decision_id": "HRD-0006-001",
        "human_resolution_sha256": resolution_hash,
        "invoked_model": "gpt-5.6-terra",
        "new_value": template["human_review_after"],
        "old_value": template["human_review_before"],
        "previous_entry_sha256": template["transition"]["previous_entry_sha256"],
        "sequence": template["transition"]["sequence"],
        "timestamp": timestamp,
        "transition_id": template["transition"]["transition_id"],
        "transition_type": "AUTHORITY_RECONCILIATION",
    }
    transition["entry_sha256"] = digest({key: value for key, value in transition.items() if key != "entry_sha256"})
    if row["transition_history"][-1]["entry_sha256"] != transition["previous_entry_sha256"]:
        raise ReconciliationError(f"transition chain tail drift: {row['component_id']}")
    if len(row["transition_history"]) != transition["sequence"]:
        raise ReconciliationError(f"transition sequence drift: {row['component_id']}")
    row["transition_history"].append(transition)
    row["transition_history_sha256"] = digest([item["entry_sha256"] for item in row["transition_history"]])


def build_response_dependent_candidates(
    root: Path, manifest_path: Path, bindings: dict[str, Any], response: dict[str, Any], *, mode: str = "canonical",
) -> ResponseDependentCandidates:
    """Build the response-bound ledger and human-review candidates in memory only."""
    _require_mode(mode)
    root = root.resolve()
    if manifest_path.resolve() != (root / R1_MANIFEST).resolve() or digest(manifest_path.read_bytes()) != R1_MANIFEST_SHA256:
        raise ReconciliationError("dynamic builder requires the exact r1 manifest bytes")
    manifest = load_manifest(manifest_path)
    preimages = preflight_targets(root, manifest)
    question = render_authorization_question(manifest, bindings, mode=mode)
    response = validate_authenticated_response(response, question, bindings, mode=mode)
    timestamp = response["timestamp"]
    evidence = _materialize_evidence_bindings(manifest, bindings, mode=mode, root=root)
    construction = manifest["human_review_construction"]
    entry = copy.deepcopy(construction["entry_template"])
    entry["evidence"] = evidence
    entry["question"] = question
    entry["scope"]["component_ids"] = construction["sorted_component_scope"]
    entry["content_sha256"] = digest({key: value for key, value in entry.items() if key != "content_sha256"})
    resolution = copy.deepcopy(construction["resolution_template"])
    resolution["actor"]["display_name"] = response["actor"]["display_name"]
    resolution["actor"]["identity_id"] = response["actor"]["identity_id"]
    resolution["scope"] = copy.deepcopy(entry["scope"])
    resolution["timestamp"] = timestamp
    resolution["entry_authority_sha256"] = digest({key: value for key, value in entry.items() if key not in {"state", "resolution_decision_ids", "content_sha256"}})
    resolution["content_sha256"] = digest({key: value for key, value in resolution.items() if key != "content_sha256"})
    if _contains_placeholder(entry) or _contains_placeholder(resolution):
        raise ReconciliationError("response-dependent human values retain placeholders")

    ledger_path, human_path = TARGET_ORDER[2:]
    lines = preimages[ledger_path]["bytes"].splitlines(keepends=True)
    if len(lines) != manifest["prestate_bindings"]["fixed_counts"]["ledger_rows"] or not all(line.endswith(b"\n") for line in lines):
        raise ReconciliationError("ledger prestate serialization drift")
    components = {item["component_id"]: item for item in manifest["components"]}
    order = manifest["transaction"]["affected_component_order"]
    if list(components) != order:
        raise ReconciliationError("manifest component order is not exact")
    keys = manifest["transaction"]["static_projection_keys"]
    parsed_rows = [json.loads(line, object_pairs_hook=_reject_duplicate_keys) for line in lines]
    row_by_id = {row.get("component_id"): row for row in parsed_rows}
    if len(row_by_id) != len(parsed_rows):
        raise ReconciliationError("ledger component IDs are not unique")
    for component_id in order:
        row = row_by_id.get(component_id)
        component = components[component_id]
        if row is None:
            raise ReconciliationError(f"ledger affected row is absent: {component_id}")
        if digest(row) != component["pre_row_canonical_sha256"] or digest(_static_projection(row, keys)) != component["pre_static_projection_sha256"]:
            raise ReconciliationError(f"ledger row prestate drift: {row.get('component_id')}")
        mutation = component["mutation_class"]
        if mutation.startswith("RC2_"):
            approval = [item for item in row["required_approvals"] if item["approval_id"] == component["delegated_approval_id"]]
            if len(approval) != 1 or approval[0]["status"] != "UNRESOLVED":
                raise ReconciliationError(f"RC-2 approval prestate drift: {row['component_id']}")
            approval[0]["scope"] = component["delegated_scope_after"]
            if mutation == "RC2_SEQUENCE":
                review = [item for item in row["required_evidence"] if item["evidence_id"] == component["spec_review_id"]]
                if len(review) != 1:
                    raise ReconciliationError(f"RC-2 sequence evidence drift: {row['component_id']}")
                review[0]["scope"] = component["spec_review_scope_after"]
        elif mutation == "RC3_DISP_M_3":
            row["required_approvals"].append(copy.deepcopy(manifest["rc3_appended_objects"]["approval"]))
            row["required_evidence"].append(copy.deepcopy(manifest["rc3_appended_objects"]["evidence"]))
        elif mutation == "RC4_REG_A_09":
            row["required_approvals"].append(copy.deepcopy(manifest["rc4_appended_object"]))
        else:
            raise ReconciliationError(f"unknown mutation class: {mutation}")
        row["human_review_id"] = copy.deepcopy(component["human_review_after"])
        _append_transition(row, component, resolution["content_sha256"], timestamp)
        if digest(_static_projection(row, keys)) != component["post_static_projection_sha256"]:
            raise ReconciliationError(f"ledger static projection drift: {row['component_id']}")
    for index, row in enumerate(parsed_rows):
        if row["component_id"] in components:
            lines[index] = canonical_json(row) + b"\n"
    ledger_candidate = b"".join(lines)
    human_candidate = _append_human_values(preimages[human_path]["bytes"].decode("utf-8"), entry, resolution)
    ensure_no_placeholders(ledger_candidate)
    if mode == "canonical":
        ensure_no_placeholders(human_candidate)
    outcomes = {
        "LEDGER_POST_SHA256": digest(ledger_candidate),
        "HUMAN_REVIEW_POST_SHA256": digest(human_candidate),
    }
    return ResponseDependentCandidates({ledger_path: ledger_candidate, human_path: human_candidate}, outcomes)


def build_canonical_package(root: Path, manifest_path: Path, bindings: dict[str, Any], *, message_id: str) -> tuple[dict[str, bytes], dict[str, Any]]:
    """Build the only canonical package route from a root Codex response source."""
    root = root.resolve()
    static = build_goal_and_structural_candidates(root, manifest_path)
    if bindings.get("goal_post_sha256") != digest(static[TARGET_ORDER[0]]) or bindings.get("structural_post_sha256") != digest(static[TARGET_ORDER[1]]):
        raise ReconciliationError("canonical bindings do not match deterministic candidate hashes")
    response, anchor = _root_response_source(message_id)
    manifest = load_manifest(manifest_path)
    question = render_authorization_question(manifest, bindings, mode="canonical")
    response["question"] = question
    validate_authenticated_response(response, question, bindings, mode="canonical", seen_response_ids=_seen_canonical_response_ids(root))
    dynamic = build_response_dependent_candidates(root, manifest_path, bindings, response, mode="canonical")
    package = {**static, **dynamic.candidates}
    validate_full_package(root, manifest_path, package, mode="canonical")
    return package, {"response_anchor": anchor, "outcomes": dynamic.authorization_outcomes}


def _validate_semantic_shape(root: Path, manifest: dict[str, Any], candidates: dict[str, bytes]) -> None:
    """Check the closed four-file diff independently of candidate construction."""
    preimages = preflight_targets(root, manifest)
    if set(candidates) != set(TARGET_ORDER):
        raise ReconciliationError("semantic candidate target set is not exact")
    old_rows = preimages[TARGET_ORDER[2]]["bytes"].splitlines()
    new_rows = candidates[TARGET_ORDER[2]].splitlines()
    if len(old_rows) != 213 or len(new_rows) != 213:
        raise ReconciliationError("semantic ledger row count is not 213")
    affected = set(manifest["transaction"]["affected_component_order"])
    changed: set[str] = set()
    transition_before = transition_after = 0
    for old, new in zip(old_rows, new_rows):
        before = json.loads(old, object_pairs_hook=_reject_duplicate_keys)
        after = json.loads(new, object_pairs_hook=_reject_duplicate_keys)
        component_id = before.get("component_id")
        transition_before += len(before["transition_history"])
        transition_after += len(after["transition_history"])
        if old != new:
            changed.add(component_id)
            if component_id not in affected:
                raise ReconciliationError("unaffected ledger row changed")
            allowed = {"required_approvals", "required_evidence", "human_review_id", "transition_history", "transition_history_sha256"}
            if {key for key in set(before) | set(after) if before.get(key) != after.get(key)} - allowed:
                raise ReconciliationError("ledger candidate changes a forbidden field")
            if after.get("approval_records") != before.get("approval_records"):
                raise ReconciliationError("reconciliation fabricates approval record")
    if changed != affected or len(changed) != 22 or transition_before != 649 or transition_after != 671:
        raise ReconciliationError("ledger candidate exact transition contract failed")
    if b"HR-0006" not in candidates[TARGET_ORDER[3]] or b"HRD-0006-001" not in candidates[TARGET_ORDER[3]]:
        raise ReconciliationError("human-review candidate lacks exact HR chain")
    for item in manifest["review_invalidation"]["historical_r0_artifacts"]:
        path = root / item["path"]
        _regular_file(path)
        if digest(path.read_bytes()) != item["sha256"]:
            raise ReconciliationError("historical r0 artifact drift")
    for fresh in manifest["review_invalidation"]["fresh_inventory"]:
        for component_id in fresh["component_ids"]:
            for review_type in fresh["review_types"]:
                if (root / fresh["path_rule"].format(component_id=component_id, review_type=review_type)).exists():
                    raise ReconciliationError("r1 inventory artifact exists during reconciliation")


def validate_full_package(root: Path, manifest_path: Path, candidates: dict[str, bytes], *, mode: str, poststate: bool = False) -> None:
    """Run the manifest's complete candidate checks in a disposable root."""
    _require_mode(mode)
    manifest = load_manifest(manifest_path)
    _validate_candidate_bytes(manifest, candidates, rehearsal=mode == "rehearsal")
    if digest(manifest_path.read_bytes()) != R1_MANIFEST_SHA256:
        return  # Small isolated fixtures test filesystem mechanics, not r1 semantics.
    if not poststate:
        _validate_semantic_shape(root, manifest, candidates)
    workspace = root / "scratchpad/rc234-reconciliation/semantic-check"
    _assert_safe_parent(root, workspace / "candidate")
    if workspace.exists():
        raise ReconciliationError("unexpected existing semantic candidate workspace")
    workspace.mkdir(parents=True)
    candidate_root = workspace / "candidate"
    try:
        shutil.copytree(root, candidate_root, ignore=shutil.ignore_patterns(".git", "scratchpad"))
        for relative_path, content in candidates.items():
            target = candidate_root / relative_path
            _atomic_write(target, content, stat.S_IMODE((root / relative_path).stat().st_mode))
        checks = [
            (["python3", "scripts/equity_os_blueprint/extract_goal_validators.py", "--check"], 0),
            (["python3", "scripts/equity_os_blueprint/validate_ledger_structural.py", "--repo-root", "."], 0),
            (["python3", "scripts/equity_os_blueprint/validate_ledger_preimplementation.py", "--repo-root", ".", "--report-blockers"], 2),
        ]
        for argv, expected in checks:
            result = subprocess.run(argv, cwd=candidate_root, capture_output=True, check=False)
            if result.returncode != expected:
                detail = (result.stderr or result.stdout).decode("utf-8", "replace").strip()
                raise ReconciliationError(f"candidate validation failed: {argv[1]} exit {result.returncode}: {detail[-1000:]}")
            if expected == 2:
                report = json.loads(result.stdout.decode("utf-8"))
                if report.get("ready") is not False or len(report.get("pending_reviews", [])) != 110 or len(report.get("stale_reviews", [])) != 0 or "DISP-R-1" not in json.dumps(report):
                    raise ReconciliationError(f"candidate preimplementation semantics drift: {canonical_json(report).decode('utf-8')[:1000]}")
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def _atomic_write(path: Path, content: bytes, mode: int) -> None:
    """Atomically replace one file and durably flush its parent directory."""
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _write_journal(path: Path, journal: dict[str, Any]) -> None:
    """Durably persist a complete journal state transition."""
    root = path
    while root.name != "scratchpad" and root.parent != root:
        root = root.parent
    if root.name != "scratchpad":
        raise ReconciliationError("journal path is outside transaction workspace")
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=False)
    _assert_safe_parent(root.parent, path)
    stored = {key: value for key, value in journal.items() if key != "integrity_sha256"}
    stored["integrity_sha256"] = digest(stored)
    journal.clear()
    journal.update(stored)
    _atomic_write(path, canonical_json(journal) + b"\n", 0o600)


def _journal_path(root: Path) -> Path:
    """Return the one canonical transaction journal location."""
    return root / "scratchpad/rc234-reconciliation/journal/rc234.json"


def _check_journal(root: Path) -> None:
    """Block a new mutation while a prior operation is not terminal."""
    journal_path = _journal_path(root)
    if not journal_path.exists():
        return
    journal = _load_json(journal_path)
    if journal.get("integrity_sha256") != digest({key: value for key, value in journal.items() if key != "integrity_sha256"}):
        raise ReconciliationError("journal integrity digest mismatch")
    if journal.get("state") not in TERMINAL_STATES:
        raise ReconciliationError(f"nonterminal journal blocks mutation: {journal.get('state')}")


def _git_index_and_dirty(root: Path) -> tuple[bytes, bytes, dict[str, str]]:
    """Capture exact index and worktree status without shell interpretation."""
    result = subprocess.run(
        [
            "git", "status", "--porcelain=v1", "-z", "--untracked-files=all", "--", ".",
            ":(exclude)scratchpad/rc234-reconciliation/**",
            *[f":(exclude){path}" for path in TARGET_ORDER],
        ],
        cwd=root, check=False, capture_output=True,
    )
    if result.returncode != 0:
        raise ReconciliationError("cannot capture git dirty state")
    # `git status` may refresh stat-cache metadata in the index. Capture the
    # byte baseline only after that read-only semantic probe has completed.
    tracked: dict[str, str] = {}
    fields = result.stdout.split(b"\0")
    index = 0
    while index < len(fields) - 1:
        record = fields[index]
        index += 1
        if len(record) < 4:
            raise ReconciliationError("invalid porcelain dirty record")
        path = record[3:].decode("utf-8", "surrogateescape")
        if record[:2] in {b"R ", b" C"} and index < len(fields):
            path = fields[index].decode("utf-8", "surrogateescape")
            index += 1
        candidate = root / path
        if candidate.is_symlink() or not candidate.is_file():
            raise ReconciliationError("unrelated dirty path is not a regular file")
        _regular_file(candidate)
        tracked[path] = digest(candidate.read_bytes())
    return (root / ".git/index").read_bytes(), result.stdout, tracked


def _assert_worktree_baseline(root: Path, journal: dict[str, Any]) -> None:
    """Prove the Git index and every unrelated dirty-status byte are unchanged."""
    index, dirty, dirty_paths = _git_index_and_dirty(root)
    if digest(index) != journal["index_sha256"]:
        raise ReconciliationError("Git index drift during transaction")
    if digest(dirty) != journal["dirty_sha256"]:
        raise ReconciliationError("unrelated dirty worktree drift during transaction")
    if dirty_paths != journal["dirty_path_sha256"]:
        raise ReconciliationError("unrelated dirty file bytes drift during transaction")


@contextlib.contextmanager
def _transaction_lock(root: Path):
    """Yield the one advisory exclusive lock for journal state transitions."""
    lock_path = root / "scratchpad/rc234-reconciliation/lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    _assert_safe_parent(root, lock_path)
    if lock_path.exists():
        _regular_file(lock_path, "0600")
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    handle = os.fdopen(descriptor, "a+b")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def _validate_candidate_bytes(manifest: dict[str, Any], candidates: dict[str, bytes], *, rehearsal: bool) -> None:
    """Reject malformed package bytes before durable prepare; never execute them."""
    if set(candidates) != set(TARGET_ORDER):
        raise ReconciliationError("candidate target set is not exact")
    for relative_path in TARGET_ORDER:
        content = candidates[relative_path]
        if not isinstance(content, bytes):
            raise ReconciliationError(f"candidate is not bytes: {relative_path}")
        if rehearsal:
            if b"$placeholder" in content:
                raise ReconciliationError(f"rehearsal candidate has unresolved placeholder: {relative_path}")
        else:
            ensure_no_placeholders(content)
    # The public isolated-root seam deliberately permits minimal fixtures; the
    # normative r1 package must also satisfy its Python/JSON syntactic forms.
    if "validation_contract" in manifest:
        try:
            compile(candidates[TARGET_ORDER[1]], "<candidate-structural-validator>", "exec")
            [json.loads(line, object_pairs_hook=_reject_duplicate_keys) for line in candidates[TARGET_ORDER[2]].splitlines()]
        except (SyntaxError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ReconciliationError(f"candidate syntax validation failed: {error}") from error


def _prepare(root: Path, manifest_path: Path, candidates: dict[str, bytes], *, mode: str, metadata: dict[str, Any] | None = None) -> Path:
    """Journal a package constructed by this module without replacing targets."""
    root = root.resolve()
    with _transaction_lock(root):
        manifest = load_manifest(manifest_path)
        _check_journal(root)
        preimages = preflight_targets(root, manifest)
        validate_full_package(root, manifest_path, candidates, mode=mode)
        # A second exact comparison closes the builder-to-journal race.
        preflight_targets(root, manifest)
        index, dirty, dirty_paths = _git_index_and_dirty(root)
        journal_path = _journal_path(root)
        backups: dict[str, str] = {}
        candidate_paths: dict[str, str] = {}
        for relative_path in TARGET_ORDER:
            target = _safe_target(root, relative_path)
            backup = root / "scratchpad/rc234-reconciliation/preimages" / relative_path
            candidate = root / "scratchpad/rc234-reconciliation/staging" / relative_path
            if backup.exists() or candidate.exists():
                raise ReconciliationError(f"unexpected preexisting workspace file: {relative_path}")
            backup.parent.mkdir(parents=True, exist_ok=True)
            candidate.parent.mkdir(parents=True, exist_ok=True)
            _assert_safe_parent(root, backup)
            _assert_safe_parent(root, candidate)
            if target.stat().st_dev != backup.parent.stat().st_dev or target.stat().st_dev != candidate.parent.stat().st_dev:
                raise ReconciliationError(f"cross-filesystem transaction workspace: {relative_path}")
            _atomic_write(backup, preimages[relative_path]["bytes"], preimages[relative_path]["mode"])
            _atomic_write(candidate, candidates[relative_path], preimages[relative_path]["mode"])
            _regular_file(backup, format(preimages[relative_path]["mode"], "04o"))
            _regular_file(candidate, format(preimages[relative_path]["mode"], "04o"))
            backups[relative_path] = str(backup.relative_to(root))
            candidate_paths[relative_path] = str(candidate.relative_to(root))
        journal = {
            "schema": JOURNAL_SCHEMA,
            "state": "PREPARED",
            "mode": "REHEARSAL" if mode == "rehearsal" else "CANONICAL",
            "manifest_sha256": digest(manifest_path.read_bytes()),
            "targets": list(TARGET_ORDER),
            "preimages": {path: {"sha256": digest(value["bytes"]), "mode_octal": format(value["mode"], "04o"), "backup": backups[path]} for path, value in preimages.items()},
            "candidates": {path: {"sha256": digest(candidates[path]), "candidate": candidate_paths[path]} for path in TARGET_ORDER},
            "index_sha256": digest(index), "dirty_sha256": digest(dirty), "dirty_path_sha256": dirty_paths,
            "replaced": [], "unproved_paths": [],
        }
        journal.update(metadata or {})
        _write_journal(journal_path, journal)
        return journal_path


def prepare(root: Path, manifest_path: Path, candidates: dict[str, bytes], *, rehearsal: bool = False) -> Path:
    """Public generic preparation is rehearsal-only; canonical bytes are never caller-supplied."""
    if not rehearsal:
        raise ReconciliationError("canonical prepare requires the CLI/session-bound package route")
    return _prepare(root, manifest_path, candidates, mode="rehearsal", metadata={"rehearsal_source_root": str(root.resolve())})


def _load_prepared_journal(root: Path) -> tuple[Path, dict[str, Any]]:
    """Load an exact prepared journal before execution or recovery."""
    journal_path = _journal_path(root)
    _regular_file(journal_path, "0600")
    journal = _load_json(journal_path)
    required = {"schema", "state", "mode", "manifest_sha256", "targets", "preimages", "candidates", "index_sha256", "dirty_sha256", "dirty_path_sha256", "replaced", "unproved_paths", "integrity_sha256"}
    if journal.get("schema") != JOURNAL_SCHEMA or not required <= set(journal):
        raise ReconciliationError("unexpected journal schema")
    if journal["integrity_sha256"] != digest({key: value for key, value in journal.items() if key != "integrity_sha256"}):
        raise ReconciliationError("journal integrity digest mismatch")
    if journal["targets"] != list(TARGET_ORDER) or journal["mode"] not in {"CANONICAL", "REHEARSAL"}:
        raise ReconciliationError("journal target or mode contract mismatch")
    for relative_path in TARGET_ORDER:
        preimage = journal["preimages"].get(relative_path)
        candidate = journal["candidates"].get(relative_path)
        if not isinstance(preimage, dict) or not isinstance(candidate, dict):
            raise ReconciliationError("journal target bindings are incomplete")
        backup = _safe_workspace_path(root, preimage.get("backup", ""))
        staged = _safe_workspace_path(root, candidate.get("candidate", ""))
        _regular_file(backup, preimage.get("mode_octal"))
        _regular_file(staged, preimage.get("mode_octal"))
        if digest(backup.read_bytes()) != preimage.get("sha256") or digest(staged.read_bytes()) != candidate.get("sha256"):
            raise ReconciliationError("journal artifact digest mismatch")
    return journal_path, journal


def _rollback(
    root: Path, journal_path: Path, journal: dict[str, Any], *,
    fault_at: str | set[str] | None = None, fault: type[BaseException] = RuntimeError,
) -> None:
    """Restore journaled preimages in reverse order, or retain recovery proof."""
    journal["state"] = "ROLLING_BACK"
    _write_journal(journal_path, journal)
    unproved: list[str] = []
    for relative_path in reversed(journal["replaced"]):
        entry = journal["preimages"][relative_path]
        backup = _safe_workspace_path(root, entry["backup"])
        target = _safe_target(root, relative_path)
        try:
            if _fault_matches(fault_at, f"rollback:{relative_path}"):
                raise fault(f"injected rollback fault at {relative_path}")
            _atomic_write(target, backup.read_bytes(), int(entry["mode_octal"], 8))
            if digest(target.read_bytes()) != entry["sha256"] or stat.S_IMODE(target.stat().st_mode) != int(entry["mode_octal"], 8):
                unproved.append(relative_path)
        except BaseException:
            unproved.append(relative_path)
    for relative_path in TARGET_ORDER:
        entry = journal["preimages"][relative_path]
        target = _safe_target(root, relative_path)
        try:
            if digest(target.read_bytes()) != entry["sha256"] or stat.S_IMODE(_regular_file(target).st_mode) != int(entry["mode_octal"], 8):
                unproved.append(relative_path)
        except BaseException:
            unproved.append(relative_path)
    journal["unproved_paths"] = sorted(set(unproved))
    try:
        _assert_worktree_baseline(root, journal)
    except BaseException:
        unproved.append("<git-index-or-unrelated-dirty-state>")
        journal["unproved_paths"] = sorted(set(unproved))
    journal["state"] = "RECOVERY_REQUIRED" if unproved else "ROLLED_BACK"
    _write_journal(journal_path, journal)


@contextlib.contextmanager
def _replacement_signals():
    """Route SIGINT/SIGTERM through the ordinary BaseException rollback guard."""
    previous = {}
    def handler(signum: int, _frame: Any) -> None:
        raise _TransactionSignal(f"transaction interrupted by signal {signum}")
    for value in (signal.SIGINT, signal.SIGTERM):
        previous[value] = signal.getsignal(value)
        signal.signal(value, handler)
    try:
        yield
    finally:
        for value, old in previous.items():
            signal.signal(value, old)


def execute(root: Path, manifest_path: Path, *, fault_at: str | set[str] | None = None, fault: type[BaseException] = RuntimeError, signal_at: tuple[str, int] | None = None) -> None:
    """Compare-and-swap the prepared candidates, rolling back every failure."""
    root = root.resolve()
    with _transaction_lock(root):
      manifest = load_manifest(manifest_path)
      journal_path, journal = _load_prepared_journal(root)
      if journal.get("state") != "PREPARED":
          raise ReconciliationError("execute requires an exact PREPARED journal")
      if journal.get("manifest_sha256") != digest(manifest_path.read_bytes()):
          raise ReconciliationError("prepared journal manifest drift")
      if journal["mode"] == "REHEARSAL":
          if journal.get("rehearsal_source_root") != str(root):
              raise ReconciliationError("rehearsal journal root binding mismatch")
          if root == Path(__file__).resolve().parents[2]:
              raise ReconciliationError("rehearsal journal cannot execute against live root")
      elif journal["mode"] == "CANONICAL":
          if not isinstance(journal.get("response_anchor"), dict):
              raise ReconciliationError("canonical journal lacks authenticated response anchor")
          if any("NON_CANONICAL_STAND_IN" in str(value) for value in journal.values()):
              raise ReconciliationError("canonical journal contains rehearsal stand-in")
      try:
        with _replacement_signals():
          journal["state"] = "REPLACING"
          _write_journal(journal_path, journal)
          if _fault_matches(fault_at, "before:first"):
              raise fault("injected fault before first replacement")
          for relative_path in TARGET_ORDER:
              target = _safe_target(root, relative_path)
              preimage = journal["preimages"][relative_path]
              _regular_file(target, preimage["mode_octal"])
              if digest(target.read_bytes()) != preimage["sha256"]:
                  raise ReconciliationError(f"compare-and-swap preimage drift: {relative_path}")
              candidate = _safe_workspace_path(root, journal["candidates"][relative_path]["candidate"])
              _atomic_write(target, candidate.read_bytes(), int(preimage["mode_octal"], 8))
              if digest(target.read_bytes()) != journal["candidates"][relative_path]["sha256"]:
                  raise ReconciliationError(f"candidate verification failed: {relative_path}")
              journal["replaced"].append(relative_path)
              _write_journal(journal_path, journal)
              if signal_at == (f"after:{relative_path}", signal.SIGINT) or signal_at == (f"after:{relative_path}", signal.SIGTERM):
                  os.kill(os.getpid(), signal_at[1])
              if _fault_matches(fault_at, f"after:{relative_path}"):
                  raise fault(f"injected fault after {relative_path}")
          journal["state"] = "POSTVALIDATING"
          _write_journal(journal_path, journal)
          if signal_at == ("postvalidation", signal.SIGINT) or signal_at == ("postvalidation", signal.SIGTERM):
              os.kill(os.getpid(), signal_at[1])
          if _fault_matches(fault_at, "postvalidation"):
              raise fault("injected postvalidation fault")
          candidates = {path: _safe_workspace_path(root, journal["candidates"][path]["candidate"]).read_bytes() for path in TARGET_ORDER}
          validate_full_package(root, manifest_path, candidates, mode="rehearsal" if journal["mode"] == "REHEARSAL" else "canonical", poststate=True)
          _assert_worktree_baseline(root, journal)
          journal["state"] = "COMMITTED"
          _write_journal(journal_path, journal)
      except BaseException:
        _rollback(root, journal_path, journal, fault_at=fault_at, fault=fault)
        raise


def recover(root: Path, *, fault_at: str | set[str] | None = None, fault: type[BaseException] = RuntimeError) -> None:
    """Perform only journal-directed recovery and never infer authority."""
    root = root.resolve()
    with _transaction_lock(root):
        journal_path, journal = _load_prepared_journal(root)
        if journal.get("state") in TERMINAL_STATES:
            return
        _rollback(root, journal_path, journal, fault_at=fault_at, fault=fault)


def _rehearsal_bindings(root: Path, manifest: dict[str, Any], static: dict[str, bytes]) -> dict[str, Any]:
    """Make an explicitly-labelled stand-in package for an isolated rehearsal."""
    bindings: dict[str, Any] = {
        "question_issued_at": "2026-08-19T12:00:00Z", "validation_now": "2026-08-19T12:02:00Z",
        "goal_post_sha256": digest(static[TARGET_ORDER[0]]),
        "structural_post_sha256": digest(static[TARGET_ORDER[1]]), "evidence": {},
    }
    for item in manifest["human_review_construction"]["evidence_bindings"]:
        path = root / item["path"]
        if not path.exists():
            _assert_safe_parent(root, path)
            path.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write(path, f"NON_CANONICAL_STAND_IN:{item['evidence_ref_id']}\n".encode("utf-8"), 0o600)
        bindings["evidence"][item["evidence_ref_id"]] = {
            "path": item["path"],
            "sha256": digest(path.read_bytes()),
            "role": "REVIEWER", "model": "NON_CANONICAL_STAND_IN:model",
            "effort": "NON_CANONICAL_STAND_IN:effort", "verdict": "CLEAN",
            "reviewed_input_sha256": "NON_CANONICAL_STAND_IN:reviewed-input",
        }
    return bindings


def rehearse(root: Path, manifest_path: Path) -> tuple[Path, str]:
    """Execute the full package only in an explicit non-live repository replica."""
    root = root.resolve()
    if root == Path(__file__).resolve().parents[2]:
        raise ReconciliationError("rehearsal refuses the live repository root")
    manifest = load_manifest(manifest_path)
    static = build_goal_and_structural_candidates(root, manifest_path)
    bindings = _rehearsal_bindings(root, manifest, static)
    question = render_authorization_question(manifest, bindings, mode="rehearsal")
    response = {
        "response_id": "NON_CANONICAL_STAND_IN:rehearsal-0001", "question": question,
        "answer": EXACT_AFFIRMATIVE_ANSWER,
        "actor": {"identity_id": "NON_CANONICAL_STAND_IN:current-user", "display_name": "NON_CANONICAL_STAND_IN:Current User", "role": "CURRENT_USER"},
        "timestamp": "2026-08-19T12:01:00Z",
    }
    dynamic = build_response_dependent_candidates(root, manifest_path, bindings, response, mode="rehearsal")
    candidates = {**static, **dynamic.candidates}
    journal_path = prepare(root, manifest_path, candidates, rehearsal=True)
    execute(root, manifest_path)
    evidence = {
        "schema": "equity-os.rc234-reconciliation-rehearsal/v1", "mode": "NON_CANONICAL_STAND_IN",
        "journal": str(journal_path.relative_to(root)), "journal_state": "COMMITTED",
        "candidate_sha256": {path: digest(content) for path, content in candidates.items()},
        "outcomes": dynamic.authorization_outcomes,
    }
    evidence_path = root / "scratchpad/rc234-reconciliation/rehearsal-evidence.json"
    _atomic_write(evidence_path, canonical_json(evidence) + b"\n", 0o600)
    return evidence_path, digest(evidence_path.read_bytes())


def main() -> int:
    """Run the fail-closed public CLI."""
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("package", "prepare", "execute", "recover", "rehearse"))
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--manifest")
    parser.add_argument("--bindings-json")
    parser.add_argument("--message-id")
    parser.add_argument("--package-output")
    parser.add_argument("--inject-signal-at", choices=("after:docs/goals/equity-os-blueprint-completion.md", "after:scripts/equity_os_blueprint/validate_ledger_structural.py", "after:docs/goals/equity-os-blueprint-component-ledger.jsonl", "after:docs/goals/equity-os-blueprint-human-review-needed.md", "postvalidation"))
    parser.add_argument("--signal", choices=("SIGINT", "SIGTERM"))
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    try:
        if args.command == "recover":
            recover(root)
        else:
            if not args.manifest:
                raise ReconciliationError("prepare, execute, and rehearse require --manifest")
            manifest = Path(args.manifest)
            if args.command in {"package", "prepare"}:
                if not args.bindings_json or not args.message_id:
                    raise ReconciliationError("canonical package/prepare requires --bindings-json and --message-id")
                bindings_path = Path(args.bindings_json).resolve()
                _owned_regular_file(bindings_path)
                bindings = _load_json(bindings_path)
                candidates, metadata = build_canonical_package(root, manifest, bindings, message_id=args.message_id)
                if args.command == "package":
                    if not args.package_output:
                        raise ReconciliationError("package requires --package-output")
                    output = Path(args.package_output).resolve()
                    try:
                        output.relative_to(root / "scratchpad/rc234-reconciliation")
                    except ValueError as error:
                        raise ReconciliationError("package output must be inside private workspace") from error
                    _atomic_write(output, canonical_json({"candidate_sha256": {path: digest(data) for path, data in candidates.items()}, **metadata}) + b"\n", 0o600)
                    print(f"canonical package: {output}")
                else:
                    journal = _prepare(root, manifest, candidates, mode="canonical", metadata=metadata)
                    print(f"prepared journal: {journal}")
            if args.command == "rehearse":
                evidence_path, evidence_digest = rehearse(root, manifest)
                print(f"rehearsal evidence: {evidence_path} sha256={evidence_digest}")
            if args.command == "execute":
                signal_at = None
                if args.inject_signal_at:
                    if not args.signal:
                        raise ReconciliationError("--inject-signal-at requires --signal")
                    signal_at = (args.inject_signal_at, getattr(signal, args.signal))
                execute(root, manifest, signal_at=signal_at)
    except ReconciliationError as error:
        print(f"reconciliation aborted: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
