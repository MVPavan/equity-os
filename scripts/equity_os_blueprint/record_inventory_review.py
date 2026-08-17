#!/usr/bin/env python3
"""Record COMPLETE content-bound inventory reviews on the blueprint ledger.

Implements `docs/goals/reviews/ledger/
equity-os-blueprint-inventory-review-recording-design-r4.md`
(SHA-256 `9ed08e186102bfe371d08b85b9101cbe4798562bb80bb616edabb84cae5fe5b5`),
which supersedes r3
(`98d96672e9eec34f8b9698246257b6acc4b81d8113894d66e1105cbd188b61cc`). The r4
delta is the fence- and blockquote-aware scan, the widened verdict line with the
`MISSING_VERDICT` / `AMBIGUOUS_VERDICT` reasons, and named reason tokens in
every skip abort (r3 review F-1, F-2, M1). The r3 delta was the
machine-readable verdict-artifact contract in §2.2.1 (bead `eqos-w78`); every
other section is r2 unchanged.

Section references in this file are to that design, which is authoritative.
The tool writes exactly one canonical path — the component ledger — through a
journaled, single-rename transaction (§3.8), and never touches the goal, either
validator, the extractor, the human-review artifact, or `CONTEXT.md`.

Usage:

    python3 scripts/equity_os_blueprint/record_inventory_review.py \\
      --repo-root . --batch <batch-manifest.json> [--dry-run]

This module is importable: all behaviour lives in functions and the CLI is
guarded by `__main__`. The rollback rehearsal harness (§3.10) drives it by
import and monkeypatches `os` / `post_replacement_verify`, so this file carries
no fault-injection hooks of its own.
"""

from __future__ import annotations

import argparse
import ast
import copy
import datetime
import hashlib
import json
import os
import re
import signal
import stat
import subprocess
import sys
from pathlib import Path, PurePosixPath

# ---------------------------------------------------------------------------
# Constants (§1.1 pinned bytes, §2.2 naming, §3.8/§3.10 transaction surfaces).
# ---------------------------------------------------------------------------

LEDGER_RELPATH = "docs/goals/equity-os-blueprint-component-ledger.jsonl"
HUMAN_REVIEW_RELPATH = "docs/goals/equity-os-blueprint-human-review-needed.md"
STRUCTURAL_RELPATH = "scripts/equity_os_blueprint/validate_ledger_structural.py"
PREIMPL_RELPATH = (
    "scripts/equity_os_blueprint/validate_ledger_preimplementation.py"
)
EXTRACTOR_RELPATH = "scripts/equity_os_blueprint/extract_goal_validators.py"
CONTEXT_RELPATH = "CONTEXT.md"

# §1.1. The recorder pins the validator surfaces it digests against; drift
# means the digest contract may have changed (§3.8 step 2).
PINNED_STRUCTURAL_SHA256 = (
    "77faeaf3dee13d5d2bfb50c255b054cde94ef0118751b247e23248e343964fff"
)
PINNED_PREIMPL_SHA256 = (
    "f7a225a1f99cb85c92cde3094505a92a746552280eb45dae0253a71ab9048013"
)
PINNED_EXTRACTOR_SHA256 = (
    "5d20d796666d1154fb3c84ba4fa7407ee82819510a5ac06254f7f4a3126c6f2a"
)
# §3.10 assert 7: the state a rehearsal replica is built at, by construction.
PINNED_LEDGER_PRESTATE_SHA256 = (
    "e52ed95c842a5546d1ae04108c06f4a38f49dd9a846d94bdbe8f612f38947c49"
)

WORKSPACE_RELDIR = "scratchpad/inventory-reviews"
LOCK_RELPATH = WORKSPACE_RELDIR + "/lock"
JOURNAL_RELDIR = WORKSPACE_RELDIR + "/journal"
STAGING_RELDIR = WORKSPACE_RELDIR + "/staging"
REHEARSAL_PROOF_RELPATH = WORKSPACE_RELDIR + "/rehearsal/proof.json"

REHEARSAL_SCHEMA = "inventory-review-rollback-rehearsal/v2"
MANIFEST_SCHEMA = "inventory-review-batch/v1"
# §3.2's key sets, closed — enforced in both directions (r5, r4-review M-2).
MANIFEST_TOP_LEVEL_KEYS = (
    "schema", "batch_id", "ledger_prehash_sha256", "baseline_dirty_paths",
    "reviews",
)
MANIFEST_ENTRY_KEYS = (
    "component_id", "review_type", "artifact_path", "artifact_sha256",
    "reviewer", "model", "effort", "role", "role_binding_path",
    "role_binding_sha256", "review_round", "verdict", "timestamp",
)

INVENTORY_ARTIFACT_ROOT = "docs/goals/reviews/ledger/inventory"

REVIEW_TYPES = ("APPROVAL", "EVIDENCE", "SCOPE")
ALIAS_KIND = "derivative_alias"
REGISTER_KIND = "register_row"

ROLE = "REVIEWER"
ROLE_BINDING_PATH = "CONTEXT.md"
VERDICT_CLEAN = "CLEAN"
STATUS_PENDING = "PENDING"
STATUS_COMPLETE = "COMPLETE"

# §3.6: the one REJECTED_ACCOUNTED row, whose EVIDENCE review must stay
# unable to prove the no-implementation requirement.
DISP_R1_COMPONENT_ID = "DISP-R-1"
DISP_R1_HISTORICAL_EVIDENCE_ID = "EV-DISP-R-1-SPEC-DRAFT"
# r6 §3.6 (r5-review I-3): HR-0005 made the no-implementation requirement
# two-state. The carve-out holds only in the UNRESOLVED state.
DISP_R1_NO_IMPLEMENTATION_REQUIREMENT_ID = "REQ-DISP-R-1-NO-IMPLEMENTATION"
DISP_R1_CARVE_OUT_STATUS = "UNRESOLVED"

# §3.8 step 10. Only COMMITTED and ROLLED_BACK are terminal.
JOURNAL_PREPARED = "PREPARED"
JOURNAL_COMMITTED = "COMMITTED"
JOURNAL_ROLLED_BACK = "ROLLED_BACK"
JOURNAL_RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
TERMINAL_JOURNAL_STATES = frozenset({JOURNAL_COMMITTED, JOURNAL_ROLLED_BACK})

# Fields the recorder parses out of a verdict artifact (r3 §2.2.1) and
# cross-checks against the manifest entry. Nothing here is ever defaulted.
# `captured_at` is NOT an artifact field: r3 §2.2.1 derives the evidence
# object's captured_at from the artifact's own review `timestamp`.
ARTIFACT_FIELDS = (
    "component_id", "review_type", "review_round", "reviewer", "role",
    "role_binding_path", "role_binding_sha256", "model", "effort", "verdict",
    "timestamp",
)
# r3 §2.2.1 form B — a bare `key: value` line.
ARTIFACT_FIELD_RE = re.compile(r"^([a-z0-9_]+):[ \t]*(\S.*?)[ \t]*$")
# r3 §2.2.1 form A — a two-cell Markdown table row. The label cell is resolved
# through the CLOSED alias table below, so both the snake_case artifacts
# (`| \`model\` (actually invoked) | \`claude-opus-5\` |`) and the prose-label
# artifacts (`| Model actually invoked | \`claude-opus-5\` |`) are read by the
# same rule. Neither cell may contain a `|`.
ARTIFACT_TABLE_FIELD_RE = re.compile(r"^\|([^|]*)\|([^|]*)\|[ \t]*$")
# r3 §2.2.1 form A' — a three-cell `| <label> | <path> | <sha256> |` row. Only
# the role-binding labels below are read in this shape.
ARTIFACT_TABLE_ROW3_RE = re.compile(r"^\|([^|]*)\|([^|]*)\|([^|]*)\|[ \t]*$")
# r3 §2.2.1 — trailing parenthetical on a label cell, stripped only when the
# remaining label is itself an accepted alias.
ARTIFACT_LABEL_PARENTHETICAL_RE = re.compile(r"^(.*?)[ \t]*\([^()]*\)$")
# r3 §2.2.1 — the CLOSED, enumerated label alias table: canonical field name ->
# every label string (after normalisation: backticks stripped, whitespace
# collapsed, case-folded) observed across the 444 verdict artifacts. It is a
# closed enumeration, never a heuristic: a label absent from this table carries
# nothing, and widening it requires a design round.
ARTIFACT_LABEL_ALIASES = {
    "component_id": ("component_id", "component id"),
    "review_type": ("review_type", "review type"),
    "review_round": ("review_round", "review round", "round"),
    "reviewer": ("reviewer", "reviewer identity / session"),
    "role": ("role",),
    "role_binding_path": ("role_binding_path", "role binding path"),
    "role_binding_sha256": (
        "role_binding_sha256", "role binding sha-256",
        "role binding sha-256 at review time",
    ),
    "model": ("model", "model actually invoked"),
    "effort": ("effort", "effort actually invoked"),
    "verdict": ("verdict",),
    "timestamp": (
        "timestamp", "review timestamp", "review utc", "review utc timestamp",
    ),
}
ARTIFACT_LABEL_TO_FIELD = {
    label: field
    for field, labels in ARTIFACT_LABEL_ALIASES.items()
    for label in labels
}
# r3 §2.2.1 — the three-cell shape's accepted labels: column 2 is the role
# binding path, column 3 its SHA-256.
ARTIFACT_ROLE_BINDING_ROW3_LABELS = ("role binding", "role binding table")
# r4 §2.2.1 — the verdict line. The word `verdict` is matched case-insensitively
# and may be bold-wrapped; the value is taken exact-case. An optional
# ` — <remainder>` / ` - <remainder>` tail (the house non-clean form,
# `**verdict: ISSUES_FOUND — 1 Critical, 0 Important, 0 Minor**`) is matched and
# discarded; the bare TOKEN before it is the verdict.
ARTIFACT_VERDICT_RE = re.compile(
    r"^[ \t]*(?:\*\*)?[ \t]*[Vv][Ee][Rr][Dd][Ii][Cc][Tt][ \t]*:[ \t]*"
    r"([A-Za-z0-9_]+)"
    r"(?:[ \t]+(?:—|-)[ \t]+\S.*?)?"
    r"[ \t]*(?:\*\*)?[ \t]*$"
)
# r6 §2.2.1 (r5-review I-2) — the near-miss tripwire. The carrier regex above
# must match to end of line, so a line that announces a verdict and then
# deviates (`Verdict: NOT CLEAN — …`, `**Verdict: ISSUES_FOUND (1 Critical)**`)
# is not a malformed carrier under r5 — it is not a carrier at all, and the
# artifact's header assertion stands unopposed. A scanned line matching this
# prefix that is not a valid carrier is refused by name instead.
ARTIFACT_VERDICT_PREFIX_RE = re.compile(
    r"^[ \t]*(?:\*\*)?[ \t]*[Vv][Ee][Rr][Dd][Ii][Cc][Tt][ \t]*:"
)
# r6 §2.2.1 (r5-review I-2) — blockquote markers, stripped before a skipped
# blockquote line is tested for a conflicting quoted verdict.
ARTIFACT_BLOCKQUOTE_MARKER_RE = re.compile(r"^[ \t]*(?:>[ \t]?)+")
# r4 §2.2.1 — fence and blockquote guards. A line opening or closing a fenced
# block, every line inside one, and every blockquote line are not scanned for
# identity rows or verdict lines: quoted text is not asserted text.
ARTIFACT_FENCE_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})")
ARTIFACT_BLOCKQUOTE_RE = re.compile(r"^[ \t]*>")
# r5 §2.2.1 (r4-review M-1) — an HTML comment renders as nothing at all and is
# unscanned. r5's companion rule for indented lines is **dropped in r6**
# (r5-review I-1): an indented chunk inside a list item, or after a paragraph
# line, is ordinary asserted prose in CommonMark, not a code block, so skipping
# it re-opened the laundering class the guard exists to close.
ARTIFACT_HTML_COMMENT_OPEN = "<!--"
ARTIFACT_HTML_COMMENT_CLOSE = "-->"
# r3 §2.2.1 — `review_round` is written `r0` or `0`; both normalize to digits.
ARTIFACT_REVIEW_ROUND_RE = re.compile(r"^r?(\d+)$")
ARTIFACT_VERDICT_FIELD = "verdict"
ARTIFACT_REVIEW_ROUND_FIELD = "review_round"

RFC3339_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z")
HEX64_RE = re.compile(r"[0-9a-f]{64}")

# §3.3: the four functions ast-extracted from the structural validator as the
# reference implementation for the projection-equivalence check (§6.2 check 1).
REFERENCE_FUNCTIONS = (
    "canonical_sha256", "normalized_human_review_id",
    "review_input_projection", "review_inventory_projection",
)


class RecorderAbort(Exception):
    """A precondition or postcondition failed; nothing was committed."""


class RecoveryRequired(Exception):
    """§3.8 step 10: a rollback whose result could not be proven."""


# ---------------------------------------------------------------------------
# §3.3 Digest computation — transcribed verbatim from the structural validator.
#
# These four functions are byte-for-byte copies of
# `validate_ledger_structural.py` (`canonical_sha256` :72-76,
# `normalized_human_review_id` :427-437, `review_input_projection` :265-289,
# `review_inventory_projection` :291-315). They are NOT imported: the validator
# is straight-line with a module-level `parse_args()` and no `__main__` guard,
# so importing it would consume this process's `sys.argv` and run a full
# validation pass as an import side effect (§3.3). `check_projection_
# equivalence` proves the transcription still matches the checked-in bytes.
# ---------------------------------------------------------------------------

def canonical_sha256(value):
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def normalized_human_review_id(value):
    """Closed r7 §3.2 human-review-link representation, as a set."""
    if value is None:
        return frozenset()
    if isinstance(value, str):
        assert re.fullmatch(r"HR-\d{4}", value)
        return frozenset({value})
    assert isinstance(value, list) and len(value) >= 2
    assert all(re.fullmatch(r"HR-\d{4}", item) for item in value)
    assert value == sorted(set(value))
    return frozenset(value)


def review_input_projection(row):
    scope = row["scope_derivation"]
    scope_without_review = None
    if isinstance(scope, dict):
        scope_without_review = {
            key: value for key, value in scope.items() if key != "semantic_review"
        }
    fields = {
        "component_id", "canonical_component_id", "kind", "source_path",
        "source_anchor", "source_start_line", "source_end_line", "source_hash",
        "text_digest", "authority_rank", "register_id", "source_title",
        "required_acceptance_text", "blueprint_phase", "priority",
        "activation_source_status", "source_status", "dependencies",
        "primary_spec", "disposition_refs", "gate_refs", "activation_predicate",
        "activation_record", "rejection_record", "program_disposition",
        "bead_ids", "roadmap_ref", "plan_refs", "implementation_refs",
        "tracked_work", "required_evidence", "evidence_refs",
        "verification_command", "required_approvals", "approval_records",
        "review_round", "open_findings", "human_review_id",
        "security_exception_ids", "blocked_scope", "transition_history_sha256",
    }
    projection = {field: row[field] for field in sorted(fields)}
    projection["scope_derivation"] = scope_without_review
    projection["human_review_id"] = sorted(
        normalized_human_review_id(row["human_review_id"])
    )
    return projection


def review_inventory_projection(row, review_type):
    if review_type == "SCOPE":
        scope = row["scope_derivation"]
        assert isinstance(scope, dict)
        return {
            "scope_derivation": {
                key: value for key, value in scope.items()
                if key != "semantic_review"
            },
            "disposition_refs": row["disposition_refs"],
            "gate_refs": row["gate_refs"],
            "activation_predicate": row["activation_predicate"],
            "related_register_ids": scope["related_register_ids"],
        }
    if review_type == "EVIDENCE":
        return {
            "required_evidence": row["required_evidence"],
            "evidence_refs": row["evidence_refs"],
            "verification_command": row["verification_command"],
        }
    assert review_type == "APPROVAL"
    return {
        "required_approvals": row["required_approvals"],
        "approval_records": row["approval_records"],
        "human_review_id": sorted(normalized_human_review_id(row["human_review_id"])),
        "security_exception_ids": row["security_exception_ids"],
    }


def reference_projections(repo_root):
    """§3.3: ast-extract the four digest functions; never import the validator.

    Only the four top-level FunctionDef nodes are compiled, so no module-level
    statement of the validator runs and `sys.argv` is untouched. The namespace
    is seeded with exactly the three stdlib modules those functions close over;
    any further free name raises NameError at call time.
    """
    source = (repo_root / STRUCTURAL_RELPATH).read_text(encoding="utf-8")
    tree = ast.parse(source)
    picked = {
        node.name: node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in REFERENCE_FUNCTIONS
    }
    if set(picked) != set(REFERENCE_FUNCTIONS):
        raise RecorderAbort(
            "§3.3 drift tripwire: expected top-level functions "
            f"{sorted(REFERENCE_FUNCTIONS)} in {STRUCTURAL_RELPATH}, found "
            f"{sorted(picked)}"
        )
    module = ast.Module(
        body=[picked[name] for name in REFERENCE_FUNCTIONS], type_ignores=[]
    )
    ast.fix_missing_locations(module)
    namespace = {"hashlib": hashlib, "json": json, "re": re}
    exec(compile(module, STRUCTURAL_RELPATH, "exec"), namespace)  # noqa: S102
    return namespace


def check_projection_equivalence(repo_root, sample_rows):
    """§6.2 check 1: transcription must match the checked-in validator bytes.

    Fails early and names the drifted function. §3.8 step 5 (running the real
    validator on the candidate) is the definitive backstop; this check exists
    because that one fails late and anonymously.
    """
    reference = reference_projections(repo_root)
    for row in sample_rows:
        mine_input = canonical_sha256(review_input_projection(row))
        theirs_input = reference["canonical_sha256"](
            reference["review_input_projection"](row)
        )
        if mine_input != theirs_input:
            raise RecorderAbort(
                "§6.2 check 1: review_input_projection/canonical_sha256 drifted "
                f"on {row['component_id']}: {mine_input} != {theirs_input}"
            )
        for review_type in applicable_review_types(row):
            mine = canonical_sha256(review_inventory_projection(row, review_type))
            theirs = reference["canonical_sha256"](
                reference["review_inventory_projection"](row, review_type)
            )
            if mine != theirs:
                raise RecorderAbort(
                    "§6.2 check 1: review_inventory_projection drifted on "
                    f"{row['component_id']}/{review_type}: {mine} != {theirs}"
                )


def equivalence_sample(rows, batch_component_ids):
    """§6.2 check 1 sample: every batch row, plus >=5 untouched rows over >=3
    kinds covering all three review_type values."""
    sample = [row for row in rows if row["component_id"] in batch_component_ids]
    untouched, kinds = [], set()
    for row in rows:
        if row["kind"] == ALIAS_KIND or row["component_id"] in batch_component_ids:
            continue
        if row["kind"] in kinds and len(untouched) >= 5 and len(kinds) >= 3:
            continue
        untouched.append(row)
        kinds.add(row["kind"])
        if len(untouched) >= 5 and len(kinds) >= 3 and any(
            candidate["kind"] != REGISTER_KIND for candidate in untouched
        ) and any(candidate["kind"] == REGISTER_KIND for candidate in untouched):
            break
    if len(untouched) < 5 or len(kinds) < 3:
        raise RecorderAbort("§6.2 check 1: could not build the required sample")
    covered = set()
    for row in untouched:
        covered.update(applicable_review_types(row))
    if covered != set(REVIEW_TYPES):
        raise RecorderAbort(
            f"§6.2 check 1: sample covers {sorted(covered)}, not all review types"
        )
    return sample + untouched


# ---------------------------------------------------------------------------
# Row helpers (§1.2 applicability, §3.7 serialization).
# ---------------------------------------------------------------------------

def applicable_review_types(row):
    """§1.2 / §3.8 step 2: derived from `kind`, exactly as
    `validate_ledger_preimplementation.py:200-204` does it."""
    kind = row["kind"]
    if kind == ALIAS_KIND:
        return ()
    if kind == REGISTER_KIND:
        return ("APPROVAL", "EVIDENCE")
    return ("APPROVAL", "EVIDENCE", "SCOPE")


def review_slot(row, review_type):
    if review_type == "SCOPE":
        scope = row["scope_derivation"]
        return None if not isinstance(scope, dict) else scope.get("semantic_review")
    if review_type == "EVIDENCE":
        return row["evidence_inventory_review"]
    return row["approval_inventory_review"]


def set_review_slot(row, review_type, review):
    if review_type == "SCOPE":
        row["scope_derivation"]["semantic_review"] = review
    elif review_type == "EVIDENCE":
        row["evidence_inventory_review"] = review
    else:
        row["approval_inventory_review"] = review


def serialize_rows(rows):
    """§3.7 byte-exact writer contract, verified by round-trip against the
    canonical ledger digest."""
    return "".join(
        json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        + "\n"
        for row in rows
    )


def load_rows(path):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    if not lines or not all(line.strip() for line in lines):
        raise RecorderAbort(f"ledger {path} is empty or has blank lines")
    return [json.loads(line) for line in lines]


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sha256_bytes(payload):
    return hashlib.sha256(payload).hexdigest()


def evidence_ref_id_for(component_id, review_type):
    return f"EV-{component_id}-INVREV-{review_type}"


def fsync_path(path):
    handle = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(handle)
    finally:
        os.close(handle)


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


def parse_utc_rfc3339(value, what):
    if not isinstance(value, str) or not RFC3339_RE.fullmatch(value):
        raise RecorderAbort(f"{what} is not UTC RFC3339 ...Z: {value!r}")
    return datetime.datetime.fromisoformat(value[:-1] + "+00:00")


# ---------------------------------------------------------------------------
# §2.2 verdict artifacts and the batch manifest.
# ---------------------------------------------------------------------------

def strip_wrapping_backticks(value):
    """r3 §2.2.1: a value cell wrapped in exactly one backtick pair is unwrapped.

    Only a whole-value wrapping is removed, so prose that merely contains a
    backticked span (`Independent `REVIEWER`-role subagent, session `x``) is
    left byte-for-byte alone.
    """
    if len(value) >= 2 and value.startswith("`") and value.endswith("`"):
        inner = value[1:-1]
        if "`" not in inner and inner.strip():
            return inner
    return value


def normalize_artifact_label(cell):
    """r3 §2.2.1 label normalisation: strip backticks, trim, collapse
    whitespace, case-fold. Nothing else — no stemming, no fuzzy matching."""
    return re.sub(r"\s+", " ", cell.replace("`", "").strip()).casefold()


def artifact_field_for_label(cell):
    """r3 §2.2.1: resolve a table label cell to a canonical field, or None.

    The alias table is closed. A trailing parenthetical is stripped ONLY when
    the remaining label is itself in the table — so `role binding SHA-256 (at
    review time)` resolves, `source_hash (whole file)` does not resolve to
    anything, and `role binding location` (a different fact) never resolves to
    `role_binding_path`.
    """
    label = normalize_artifact_label(cell)
    field = ARTIFACT_LABEL_TO_FIELD.get(label)
    if field is not None:
        return field
    stripped = ARTIFACT_LABEL_PARENTHETICAL_RE.match(label)
    if stripped is None:
        return None
    return ARTIFACT_LABEL_TO_FIELD.get(stripped.group(1).strip())


def strip_comment_markers(line):
    """r6 §2.2.1: the text a commented-out line would read as, markers removed."""
    return line.replace(ARTIFACT_HTML_COMMENT_OPEN, " ").replace(
        ARTIFACT_HTML_COMMENT_CLOSE, " ").strip()


def parse_verdict_artifact(path):
    """r4 §2.2.1: parse the values the recorder copies; abort on any it cannot
    read.

    The artifact is human-readable Markdown. A field is carried by a two-cell
    Markdown table row (form A), the three-cell role-binding row (form A'), or a
    bare `key: value` line (form B); the verdict additionally by the standalone
    verdict line. Table labels resolve through the closed §2.2.1 alias table.
    A field with no accepted row (`MISSING_FIELD`) or with two accepted rows
    carrying different values (`AMBIGUOUS_FIELD`) is an abort — never a default;
    two rows carrying the same value are accepted. The verdict has its own two
    named reasons, `MISSING_VERDICT` and `AMBIGUOUS_VERDICT`. `captured_at` is
    not read here: r4 §2.2.1 derives it from `timestamp`.

    Scanning skips three constructs (r6 §2.2.1): a fenced block's delimiter
    lines and contents, any `>`-prefixed blockquote line, and any HTML comment.
    Indented lines ARE scanned — r5 skipped them and r6 drops that rule
    (r5-review I-1), since indentation inside a list item or after a paragraph
    line is ordinary asserted prose. Quoting a superseded round's
    `verdict: CLEAN` inside a fence therefore cannot launder a non-clean
    artifact; a contradicting verdict quoted in a blockquote or a comment is
    refused as `CONFLICTING_QUOTED_VERDICT`, and a scanned line that announces a
    verdict without being a valid carrier as `MALFORMED_VERDICT_LINE`
    (r5-review I-2). A fence or comment still open at EOF is
    `UNTERMINATED_FENCE` / `UNTERMINATED_COMMENT` (r5, r4-review I-1) —
    unscanned-to-EOF is refused, not silently trusted.
    """
    text = Path(path).read_text(encoding="utf-8")
    found = {}

    def record(field, value):
        if field not in ARTIFACT_FIELDS or not value:
            return
        if field == ARTIFACT_REVIEW_ROUND_FIELD:
            round_match = ARTIFACT_REVIEW_ROUND_RE.match(value)
            if round_match is None:
                raise RecorderAbort(
                    f"{path}: MALFORMED_REVIEW_ROUND — review_round {value!r} is "
                    "neither `r<N>` nor `<N>`"
                )
            value = round_match.group(1)
        found.setdefault(field, set()).add(value)

    def cell_value(cell):
        return strip_wrapping_backticks(cell.strip())

    open_fence = None  # (marker char, run length) of the open fence, or None
    open_comment = False  # inside an HTML comment whose `-->` has not been seen
    quoted_verdicts = set()  # r6: verdict tokens carried by skipped bq/comment lines

    def note_quoted_verdict(stripped):
        """r6 §2.2.1 (r5-review I-2): remember a verdict a skipped line quotes."""
        quoted_match = ARTIFACT_VERDICT_RE.match(stripped)
        if quoted_match is not None:
            quoted_verdicts.add(quoted_match.group(1))

    for line in text.splitlines():
        # The fence state machine runs first, so a fence delimiter inside an
        # open comment toggles fence state and the comment does NOT swallow it
        # (r6 §2.2.1, r5-review M-1: r5's prose claimed the opposite). Both
        # states can therefore be open at once, and the fence branch wins —
        # `UNTERMINATED_FENCE` is the reason reported when both are open at EOF.
        fence_match = ARTIFACT_FENCE_RE.match(line)
        if fence_match is not None:
            marker = fence_match.group(1)
            if open_fence is None:
                open_fence = (marker[0], len(marker))
            elif (marker[0] == open_fence[0]
                    and len(marker) >= open_fence[1]
                    and line.strip().strip(open_fence[0]) == ""):
                open_fence = None
            continue
        if open_fence is not None:
            continue
        if open_comment:
            if ARTIFACT_HTML_COMMENT_CLOSE in line:
                open_comment = False
            note_quoted_verdict(strip_comment_markers(line))
            continue
        if ARTIFACT_HTML_COMMENT_OPEN in line:
            tail = line.partition(ARTIFACT_HTML_COMMENT_OPEN)[2]
            open_comment = ARTIFACT_HTML_COMMENT_CLOSE not in tail
            note_quoted_verdict(strip_comment_markers(line))
            continue
        if ARTIFACT_BLOCKQUOTE_RE.match(line):
            note_quoted_verdict(ARTIFACT_BLOCKQUOTE_MARKER_RE.sub("", line))
            continue
        verdict_match = ARTIFACT_VERDICT_RE.match(line)
        if verdict_match is not None:
            record(ARTIFACT_VERDICT_FIELD, verdict_match.group(1))
            continue
        # r6 §2.2.1 (r5-review I-2): a scanned line that announces a verdict but
        # is not a valid carrier is refused by name rather than ignored.
        if ARTIFACT_VERDICT_PREFIX_RE.match(line):
            raise RecorderAbort(
                f"{path}: MALFORMED_VERDICT_LINE — {line.strip()!r} announces a "
                "verdict but is not one of §2.2.1's two admissible carrier "
                "forms; the artifact is refused rather than read past"
            )
        row3 = ARTIFACT_TABLE_ROW3_RE.match(line)
        if row3 is not None:
            if (normalize_artifact_label(row3.group(1))
                    in ARTIFACT_ROLE_BINDING_ROW3_LABELS):
                record("role_binding_path", cell_value(row3.group(2)))
                record("role_binding_sha256", cell_value(row3.group(3)))
            continue
        row2 = ARTIFACT_TABLE_FIELD_RE.match(line)
        if row2 is not None:
            field = artifact_field_for_label(row2.group(1))
            if field is not None:
                record(field, cell_value(row2.group(2)))
            continue
        bare = ARTIFACT_FIELD_RE.match(line)
        if bare is not None and bare.group(1) in ARTIFACT_FIELDS:
            record(bare.group(1), cell_value(bare.group(2)))

    # r5 §2.2.1 (r4-review I-1): a fence still open at EOF means every line from
    # the stray delimiter to EOF was unscanned. That is not a quoting decision
    # the artifact made, and it can swallow a real non-clean verdict without
    # tripping AMBIGUOUS_VERDICT. Refuse the artifact instead of guessing which
    # of its assertions were seen. Same reasoning for an unterminated comment.
    if open_fence is not None:
        raise RecorderAbort(
            f"{path}: UNTERMINATED_FENCE — a {open_fence[0] * open_fence[1]} "
            "fence is still open at end of file; every line from it to EOF was "
            "unscanned"
        )
    if open_comment:
        raise RecorderAbort(
            f"{path}: UNTERMINATED_COMMENT — an HTML comment is still open at "
            "end of file; every line from it to EOF was unscanned"
        )
    # r4 §2.2.1: the verdict is the field the whole gate turns on, so its two
    # failure modes carry their own names rather than folding into the generic
    # field reasons.
    verdict_values = found.get(ARTIFACT_VERDICT_FIELD, set())
    if not verdict_values:
        raise RecorderAbort(
            f"{path}: MISSING_VERDICT — no verdict line or verdict row outside "
            "fenced blocks, blockquotes and HTML comments"
        )
    if len(verdict_values) > 1:
        raise RecorderAbort(
            f"{path}: AMBIGUOUS_VERDICT — the artifact states more than one "
            f"verdict: {sorted(verdict_values)}"
        )
    # r6 §2.2.1 (r5-review I-2): a blockquote is a callout in this repository as
    # often as it is a quotation, and an HTML comment renders as nothing. Both
    # stay unscanned — but a conclusion written in one that contradicts the
    # accepted verdict is refused by name rather than silently outvoted. A
    # fenced block is exempt: §2.2 licenses it as *the* device for quoting a
    # superseded round.
    conflicting = sorted(quoted_verdicts - verdict_values)
    if conflicting:
        raise RecorderAbort(
            f"{path}: CONFLICTING_QUOTED_VERDICT — a blockquoted or "
            f"commented-out line states verdict {conflicting} while the "
            f"artifact's scanned verdict is {sorted(verdict_values)}; quote a "
            "superseded round inside a fenced block instead"
        )
    missing = [
        field for field in ARTIFACT_FIELDS
        if field not in found and field != ARTIFACT_VERDICT_FIELD
    ]
    if missing:
        raise RecorderAbort(f"{path}: MISSING_FIELD — no accepted row for {missing}")
    ambiguous = {
        field: sorted(values) for field, values in found.items()
        if len(values) > 1 and field != ARTIFACT_VERDICT_FIELD
    }
    if ambiguous:
        raise RecorderAbort(
            f"{path}: AMBIGUOUS_FIELD — two or more accepted rows disagree: "
            f"{ambiguous}"
        )
    return {field: found[field].pop() for field in ARTIFACT_FIELDS}


def load_manifest(path):
    manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise RecorderAbort(
            f"batch manifest schema must be {MANIFEST_SCHEMA!r}, got "
            f"{manifest.get('schema')!r}"
        )
    for key in ("batch_id", "ledger_prehash_sha256", "baseline_dirty_paths",
                "reviews"):
        if key not in manifest:
            raise RecorderAbort(f"batch manifest is missing {key!r}")
    # r5 §3.2 (r4-review M-2): §3.2 says "exactly these keys", so enforce the
    # closed set. A stale r2-shaped entry carrying `captured_at` — the field r3
    # deliberately removed and §2.2.1 now derives — must be refused by name, not
    # silently ignored.
    extra_top = sorted(set(manifest) - set(MANIFEST_TOP_LEVEL_KEYS))
    if extra_top:
        raise RecorderAbort(
            f"MANIFEST_UNKNOWN_KEY — batch manifest carries unknown top-level "
            f"keys {extra_top}; §3.2 fixes the set at "
            f"{list(MANIFEST_TOP_LEVEL_KEYS)}"
        )
    if not HEX64_RE.fullmatch(manifest["ledger_prehash_sha256"]):
        raise RecorderAbort("ledger_prehash_sha256 must be lowercase 64-hex")
    if not isinstance(manifest["reviews"], list) or not manifest["reviews"]:
        raise RecorderAbort("batch manifest has no reviews")
    seen = set()
    for entry in manifest["reviews"]:
        for key in MANIFEST_ENTRY_KEYS:
            if key not in entry:
                raise RecorderAbort(
                    f"manifest review entry is missing {key!r}: {entry}"
                )
        extra = sorted(set(entry) - set(MANIFEST_ENTRY_KEYS))
        if extra:
            raise RecorderAbort(
                f"MANIFEST_UNKNOWN_KEY — manifest review entry for "
                f"{(entry['component_id'], entry['review_type'])} carries "
                f"unknown keys {extra}; §3.2 fixes the set at "
                f"{list(MANIFEST_ENTRY_KEYS)}"
            )
        key = (entry["component_id"], entry["review_type"])
        if key in seen:
            raise RecorderAbort(f"duplicate manifest entry for {key}")
        seen.add(key)
        if entry["review_type"] not in REVIEW_TYPES:
            raise RecorderAbort(f"bad review_type in manifest: {entry}")
    return manifest


def validate_batch_entry(repo_root, entry, now):
    """§3.8 step 2: every verdict artifact exists, is a regular file, parses,
    and carries a CLEAN REVIEWER verdict whose fields match the manifest."""
    component_id = entry["component_id"]
    review_type = entry["review_type"]
    relpath = entry["artifact_path"]
    parsed_rel = PurePosixPath(relpath)
    # r6 §2.2.1 (r5-review M-3): the manifest-side path checks carry named
    # reason tokens too, so "triage is mechanical" holds for operator errors in
    # the manifest and not only for artifact-content failures.
    if parsed_rel.is_absolute() or ".." in parsed_rel.parts:
        raise RecorderAbort(
            f"MANIFEST_BAD_ARTIFACT_PATH — artifact_path must be repo-relative: "
            f"{relpath}"
        )
    expected_dir = f"{INVENTORY_ARTIFACT_ROOT}/{component_id}"
    if str(parsed_rel.parent) != expected_dir:
        raise RecorderAbort(
            f"{relpath}: MANIFEST_BAD_ARTIFACT_PATH — §2.2 requires the "
            f"artifact under {expected_dir}/"
        )
    name_match = re.fullmatch(rf"{review_type}-r(\d+)\.md", parsed_rel.name)
    if name_match is None:
        raise RecorderAbort(
            f"{relpath}: MANIFEST_BAD_ARTIFACT_PATH — §2.2 requires the name "
            "<REVIEW_TYPE>-r<N>.md"
        )
    target = repo_root / relpath
    info = os.lstat(target)  # never follow a symlinked verdict artifact
    if not stat.S_ISREG(info.st_mode):
        raise RecorderAbort(
            f"{relpath}: ARTIFACT_NOT_REGULAR_FILE — a symlink or non-regular "
            "path is never followed"
        )
    actual_sha256 = sha256_file(target)
    if actual_sha256 != entry["artifact_sha256"]:
        raise RecorderAbort(
            f"{relpath}: MANIFEST_DISAGREEMENT — manifest pins "
            f"{entry['artifact_sha256']}, file is {actual_sha256}"
        )
    parsed = parse_verdict_artifact(target)
    # r5 §2.2.1 (r4-review M-5): the checks below run BEFORE the manifest
    # comparison, so the reason token names what actually disagreed. Under r4
    # the manifest loop ran first and shadowed every one of them with
    # MANIFEST_DISAGREEMENT whenever the manifest was truthful, which is the
    # normal case. Accept/reject outcomes are unchanged by the reorder; only the
    # token changes, and mechanical triage is what the token is for.
    if parsed["component_id"] != component_id:
        raise RecorderAbort(
            f"{relpath}: PATH_BODY_MISMATCH — the body states component_id "
            f"{parsed['component_id']!r} but the artifact is at "
            f"{expected_dir}/"
        )
    if parsed["review_type"] != review_type:
        raise RecorderAbort(
            f"{relpath}: PATH_BODY_MISMATCH — the body states review_type "
            f"{parsed['review_type']!r} but the filename states {review_type!r}"
        )
    if parsed["review_round"] != name_match.group(1):
        raise RecorderAbort(
            f"{relpath}: ROUND_FILENAME_MISMATCH — review_round "
            f"{parsed['review_round']!r} does not match the filename round "
            f"r{name_match.group(1)}"
        )
    if parsed["verdict"] != VERDICT_CLEAN:
        raise RecorderAbort(
            f"{relpath}: NOT_CLEAN — verdict is {parsed['verdict']!r}; §5.4 — a "
            "non-clean review is not recordable, the review stays PENDING"
        )
    if parsed["role"] != ROLE:
        raise RecorderAbort(f"{relpath}: ROLE_MISMATCH — role must be {ROLE}")
    if parsed["role_binding_path"] != ROLE_BINDING_PATH:
        raise RecorderAbort(
            f"{relpath}: ROLE_MISMATCH — role_binding_path must be "
            f"{ROLE_BINDING_PATH}"
        )
    if not HEX64_RE.fullmatch(parsed["role_binding_sha256"]):
        raise RecorderAbort(
            f"{relpath}: ROLE_MISMATCH — role_binding_sha256 must be lowercase "
            "64-hex"
        )
    # r5 §2.2.1 (r4-review M-4): unreachable by construction — every accepted
    # value is stripped and a value normalizing to empty carries nothing, so no
    # parsed value can be whitespace-only. Retained as a defensive assertion and
    # disclosed as unreachable in §2.2.1's reason table rather than deleted.
    for field in ("reviewer", "model", "effort"):
        if not parsed[field].strip():
            raise RecorderAbort(f"{relpath}: MISSING_FIELD — {field} is empty")
    if not RFC3339_RE.fullmatch(parsed["timestamp"]):
        raise RecorderAbort(
            f"{relpath}: FUTURE_TIMESTAMP — timestamp {parsed['timestamp']!r} is "
            "not UTC RFC3339 ...Z"
        )
    timestamp = parse_utc_rfc3339(parsed["timestamp"], f"{relpath} timestamp")
    if timestamp > now:
        raise RecorderAbort(
            f"{relpath}: FUTURE_TIMESTAMP — timestamp is after now"
        )
    # r5 §2.2.1 (r4-review M-5): the manifest comparison runs last, so it fires
    # only for an artifact that is otherwise self-consistent, path-consistent,
    # CLEAN, REVIEWER-bound and non-future — i.e. only when the disagreement
    # really is manifest-vs-artifact.
    for field in ARTIFACT_FIELDS:
        if str(entry[field]) != parsed[field]:
            raise RecorderAbort(
                f"{relpath}: MANIFEST_DISAGREEMENT — field {field!r} is "
                f"{parsed[field]!r} in the artifact but {entry[field]!r} in the "
                "manifest"
            )
    # r5 §2.2.1: the evidence object's captured_at IS the review timestamp — the
    # artifact bytes were final at the moment the reviewer finished. The
    # structural validator asserts `timestamp >= captured_at`
    # (`validate_ledger_structural.py:346-349`), which equality satisfies. This
    # value is what run_batch writes (r4-review M-3: r4 computed it here and
    # then wrote the manifest's timestamp instead, leaving this line dead).
    parsed["captured_at"] = parsed["timestamp"]
    return parsed


# ---------------------------------------------------------------------------
# §3.4 Phase A / Phase B candidate construction.
# ---------------------------------------------------------------------------

def build_candidate(rows, entries, captured_at_by_key):
    """§3.4: per row, append ALL review evidence (Phase A), then compute the
    input digest once and write every review object (Phase B).

    `captured_at_by_key` maps `(component_id, review_type)` to the `captured_at`
    that `validate_batch_entry` derived from the **artifact's own** parsed
    `timestamp` (r5 §2.2.1; r4-review M-3 — r4 wrote the manifest's timestamp
    here, equal by the MANIFEST_DISAGREEMENT check but not the stated source).

    Appending evidence for one review type mutates the input digest of every
    other review on the same row, so a row is completed all-at-once or not at
    all. Nothing outside `evidence_refs` and the three review slots is touched:
    no transition entry (§3.5), no `required_evidence` (§3.6).
    """
    candidate = copy.deepcopy(rows)
    by_id = {row["component_id"]: row for row in candidate}
    by_component = {}
    for entry in entries:
        by_component.setdefault(entry["component_id"], []).append(entry)

    for component_id, component_entries in sorted(by_component.items()):
        row = by_id[component_id]
        # r6 §3.6 (r5-review I-3): post-HR-0005 the no-implementation
        # requirement is two-state. The carve-out below is correct only while it
        # is UNRESOLVED; once it is SATISFIED the validator requires DISP-R-1's
        # EVIDENCE review to link the historical ref, which the carve-out
        # forbids, and re-sealing all three reviews is T2's job (DISP-R-1
        # amendment design r3 §8.3). Refuse the row rather than write one that
        # cannot validate.
        if component_id == DISP_R1_COMPONENT_ID:
            requirement = next(
                item for item in row["required_evidence"]
                if item["evidence_id"] == DISP_R1_NO_IMPLEMENTATION_REQUIREMENT_ID
            )
            if requirement["status"] != DISP_R1_CARVE_OUT_STATUS:
                raise RecorderAbort(
                    f"{component_id}: DISP_R1_RESERVED_FOR_T2 — "
                    f"{DISP_R1_NO_IMPLEMENTATION_REQUIREMENT_ID} is "
                    f"{requirement['status']!r}, not "
                    f"{DISP_R1_CARVE_OUT_STATUS!r}; in that state DISP-R-1's "
                    "three reviews are T2's to re-seal (§3.6)"
                )
        types = sorted(entry["review_type"] for entry in component_entries)
        applicable = sorted(applicable_review_types(row))
        if types != applicable:
            raise RecorderAbort(
                f"{component_id}: §3.4 row atomicity — batch carries {types} but "
                f"the row's applicable set is {applicable}"
            )
        entry_by_type = {
            entry["review_type"]: entry for entry in component_entries
        }

        # Phase A — every digest-covered mutation on this row.
        for review_type in types:
            entry = entry_by_type[review_type]
            row["evidence_refs"].append({
                "evidence_ref_id": evidence_ref_id_for(component_id, review_type),
                "path": entry["artifact_path"],
                "scope": (
                    f"{review_type} inventory-review verdict artifact for "
                    f"{component_id}"
                ),
                "digest_mode": "FILE_BYTES",
                "start_line": None,
                "end_line": None,
                "content_sha256": entry["artifact_sha256"],
                # r5 §2.2.1: derived from the artifact's parsed timestamp, never
                # supplied by the manifest.
                "captured_at": captured_at_by_key[(component_id, review_type)],
            })

        # Phase B — one input digest for the row, then the review objects.
        input_digest = canonical_sha256(review_input_projection(row))
        for review_type in types:
            entry = entry_by_type[review_type]
            evidence_ref_ids = [evidence_ref_id_for(component_id, review_type)]
            if component_id == DISP_R1_COMPONENT_ID and review_type == "EVIDENCE":
                # §3.6: linking EV-DISP-R-1-SPEC-DRAFT would make
                # `current_no_implementation_proof` return review_ok=True and
                # break the structural assertion at :2756-2763.
                assert DISP_R1_HISTORICAL_EVIDENCE_ID not in evidence_ref_ids
            set_review_slot(row, review_type, {
                "review_type": review_type,
                "status": STATUS_COMPLETE,
                "reviewer": entry["reviewer"],
                "role": ROLE,
                "role_binding_path": ROLE_BINDING_PATH,
                "role_binding_sha256": entry["role_binding_sha256"],
                "model": entry["model"],
                "effort": entry["effort"],
                "verdict": VERDICT_CLEAN,
                "timestamp": entry["timestamp"],
                "evidence_ref_ids": evidence_ref_ids,
                "reviewed_input_sha256": input_digest,
                "reviewed_inventory_sha256": canonical_sha256(
                    review_inventory_projection(row, review_type)
                ),
            })
    return candidate


def check_candidate_shape(before_rows, after_rows, entries):
    """§6.2 checks 5, 6, 8 and 11 on the in-memory candidate."""
    batch_ids = {entry["component_id"] for entry in entries}
    before_by_id = {row["component_id"]: row for row in before_rows}
    after_by_id = {row["component_id"]: row for row in after_rows}
    if set(before_by_id) != set(after_by_id):
        raise RecorderAbort("candidate added or removed ledger rows")

    total_transitions_before = 0
    total_transitions_after = 0
    for component_id, before in before_by_id.items():
        after = after_by_id[component_id]
        total_transitions_before += len(before["transition_history"])
        total_transitions_after += len(after["transition_history"])
        # §3.5 / §6.2 check 6 — transitions are read-only inputs.
        if (before["transition_history"] != after["transition_history"]
                or before["transition_history_sha256"]
                != after["transition_history_sha256"]):
            raise RecorderAbort(f"{component_id}: §3.5 transition history changed")
        if component_id not in batch_ids:
            # §6.2 check 8 (row locality) and check 5 (aliases untouched).
            if json.dumps(before, sort_keys=True) != json.dumps(after, sort_keys=True):
                raise RecorderAbort(
                    f"{component_id}: §6.2 check 8 — row outside the batch changed"
                )
            continue
        if before["kind"] == ALIAS_KIND:
            raise RecorderAbort(f"{component_id}: an alias is never a batch target")
        expected_growth = len(applicable_review_types(before))
        actual_growth = len(after["evidence_refs"]) - len(before["evidence_refs"])
        if actual_growth != expected_growth:
            raise RecorderAbort(
                f"{component_id}: §6.2 check 11 — evidence_refs grew by "
                f"{actual_growth}, expected {expected_growth}"
            )
        # §3.6: the recorder never touches required_evidence on any row.
        if before["required_evidence"] != after["required_evidence"]:
            raise RecorderAbort(
                f"{component_id}: §3.6 — required_evidence must never be touched"
            )
        for field in ("required_approvals", "approval_records",
                      "program_disposition", "delivery_status", "gate_result",
                      "source_status", "open_findings", "review_round",
                      "blocked_scope", "human_review_id"):
            if before[field] != after[field]:
                raise RecorderAbort(f"{component_id}: §6.4 — {field} changed")
    if total_transitions_before != total_transitions_after:
        raise RecorderAbort("§6.2 check 6 — total transition-entry count changed")

    # §3.6 consequence 2, asserted directly rather than left to the validator.
    disp_r1 = after_by_id.get(DISP_R1_COMPONENT_ID)
    if disp_r1 is not None and DISP_R1_COMPONENT_ID in batch_ids:
        review = disp_r1["evidence_inventory_review"]
        if review["evidence_ref_ids"] != [
            evidence_ref_id_for(DISP_R1_COMPONENT_ID, "EVIDENCE")
        ]:
            raise RecorderAbort(
                "§3.6: DISP-R-1's EVIDENCE review must link only "
                f"{evidence_ref_id_for(DISP_R1_COMPONENT_ID, 'EVIDENCE')}"
            )
        historical = disp_r1["rejection_record"]["no_implementation_evidence_ref_ids"]
        if set(historical) & set(review["evidence_ref_ids"]):
            raise RecorderAbort(
                "§3.6: DISP-R-1's EVIDENCE review must not link the historical "
                "no-implementation evidence"
            )

    # §2.2: evidence_ref_id uniqueness is ledger-wide.
    seen = set()
    for row in after_rows:
        for evidence in row["evidence_refs"]:
            if evidence["evidence_ref_id"] in seen:
                raise RecorderAbort(
                    f"duplicate evidence_ref_id {evidence['evidence_ref_id']}"
                )
            seen.add(evidence["evidence_ref_id"])


# ---------------------------------------------------------------------------
# §3.10 rehearsal proof.
# ---------------------------------------------------------------------------

REHEARSAL_LEG_STATES = {
    "L1_forward_baseline": JOURNAL_COMMITTED,
    "L2_forced_failure": JOURNAL_ROLLED_BACK,
    "L3_sigint": JOURNAL_ROLLED_BACK,
    "L4_sigterm": JOURNAL_ROLLED_BACK,
    "L5_recovery_required": JOURNAL_RECOVERY_REQUIRED,
}
ROLLBACK_LEGS = ("L2_forced_failure", "L3_sigint", "L4_sigterm")
TEMP_FREE_LEGS = ("L1_forward_baseline",) + ROLLBACK_LEGS


def assert_rehearsal_proof(repo_root, recorder_sha256):
    """§3.10: the recorder refuses its first real write without a valid proof.

    This gate is an operator-discipline control over a gitignored workstream
    evidence artifact — not an enforcement boundary and not ledger evidence.
    Its hash bindings defend against a stale proof outliving a recorder or
    validator edit, not against deliberate forgery (§3.10).
    """
    proof_path = repo_root / REHEARSAL_PROOF_RELPATH
    if not proof_path.is_file():
        raise RecorderAbort(
            f"§3.10: no rollback-rehearsal proof at {REHEARSAL_PROOF_RELPATH}; "
            "the recorder refuses to write until the five-leg rehearsal is done"
        )
    proof = json.loads(proof_path.read_text(encoding="utf-8"))

    # Assert 1 — schema by name.
    if proof.get("schema") != REHEARSAL_SCHEMA:
        raise RecorderAbort(
            f"§3.10 assert 1: rehearsal schema must be {REHEARSAL_SCHEMA!r}, got "
            f"{proof.get('schema')!r}"
        )
    legs = proof.get("legs")
    if not isinstance(legs, dict):
        raise RecorderAbort("§3.10 assert 2: proof has no legs object")

    # Assert 2 — all five legs, passed, with the exact journal state.
    for leg_name, expected_state in REHEARSAL_LEG_STATES.items():
        leg = legs.get(leg_name)
        if not isinstance(leg, dict):
            raise RecorderAbort(f"§3.10 assert 2: leg {leg_name} missing")
        if leg.get("passed") is not True:
            raise RecorderAbort(f"§3.10 assert 2: leg {leg_name} did not pass")
        if leg.get("journal_state") != expected_state:
            raise RecorderAbort(
                f"§3.10 assert 2: leg {leg_name} journal_state is "
                f"{leg.get('journal_state')!r}, expected {expected_state!r}"
            )
        if leg.get("lock_released") is not True:
            raise RecorderAbort(f"§3.10 assert 2: leg {leg_name} left the lock held")
    for leg_name in TEMP_FREE_LEGS:
        if legs[leg_name].get("temp_files_surviving") != 0:
            raise RecorderAbort(
                f"§3.10 assert 2: leg {leg_name} left temp files behind"
            )
    # L5 is exempt by construction — step 10 preserves those files — and
    # instead must record them in the journal.
    if legs["L5_recovery_required"].get(
            "surviving_paths_recorded_in_journal") is not True:
        raise RecorderAbort(
            "§3.10 assert 2: L5 did not record its surviving paths in the journal"
        )

    # Assert 3 — bytes AND mode on every rollback leg.
    for leg_name in ROLLBACK_LEGS:
        leg = legs[leg_name]
        if leg.get("bytes_match_preimage") is not True:
            raise RecorderAbort(f"§3.10 assert 3: {leg_name} bytes did not match")
        if leg.get("mode_match_preimage") is not True:
            raise RecorderAbort(f"§3.10 assert 3: {leg_name} mode did not match")

    # Assert 4 — L5 really reached RECOVERY_REQUIRED.
    l5 = legs["L5_recovery_required"]
    if not l5.get("unproven_path"):
        raise RecorderAbort("§3.10 assert 4: L5 has no unproven_path")
    for key in ("expected_sha256", "observed_sha256", "expected_mode",
                "observed_mode"):
        if key not in l5:
            raise RecorderAbort(f"§3.10 assert 4: L5 is missing {key}")
    if l5["observed_sha256"] == l5["expected_sha256"]:
        raise RecorderAbort(
            "§3.10 assert 4: L5 observed_sha256 equals expected_sha256 — the "
            "rollback was provable, so the RECOVERY_REQUIRED branch never fired"
        )
    if l5.get("exit_code") in (0, None):
        raise RecorderAbort("§3.10 assert 4: L5 exit_code must be nonzero")
    if l5.get("second_invocation_refused_at_step_1") is not True:
        raise RecorderAbort(
            "§3.10 assert 4: a second invocation was not refused at step 1"
        )

    # Assert 5 — the rehearsal covers the recorder about to run.
    if proof.get("recorder_sha256") != recorder_sha256:
        raise RecorderAbort(
            "§3.10 assert 5: the recorder changed since the rehearsal "
            f"(rehearsed {proof.get('recorder_sha256')}, running "
            f"{recorder_sha256}); a fresh rehearsal is required"
        )

    # Assert 6 — validator pin, against §1.1 and against the current bytes.
    for key, pinned, relpath in (
        ("structural_validator_sha256", PINNED_STRUCTURAL_SHA256,
         STRUCTURAL_RELPATH),
        ("preimplementation_validator_sha256", PINNED_PREIMPL_SHA256,
         PREIMPL_RELPATH),
    ):
        current = sha256_file(repo_root / relpath)
        if proof.get(key) != pinned or current != pinned:
            raise RecorderAbort(
                f"§3.10 assert 6: {key} must equal the §1.1 value {pinned} in "
                f"both the proof ({proof.get(key)}) and the current file "
                f"({current})"
            )

    # Assert 7 — the replica's own starting ledger digest. The live canonical
    # ledger is NOT read here, at batch 1 or at any later batch.
    replica_prestate = proof.get("replica_ledger_prestate_sha256")
    if not isinstance(replica_prestate, str) or not HEX64_RE.fullmatch(
            replica_prestate):
        raise RecorderAbort(
            "§3.10 assert 7: replica_ledger_prestate_sha256 must be lowercase "
            "64-hex"
        )
    if replica_prestate != PINNED_LEDGER_PRESTATE_SHA256:
        raise RecorderAbort(
            "§3.10 assert 7: the rehearsal replica started at "
            f"{replica_prestate}, not the §1.1 ledger pre-state "
            f"{PINNED_LEDGER_PRESTATE_SHA256}"
        )

    # Assert 8 — the transcript, plus assert 7's transcript cross-check.
    transcript_relpath = proof.get("transcript_path")
    if not transcript_relpath:
        raise RecorderAbort("§3.10 assert 8: proof has no transcript_path")
    transcript = repo_root / transcript_relpath
    if not stat.S_ISREG(os.lstat(transcript).st_mode):
        raise RecorderAbort(f"§3.10 assert 8: {transcript_relpath} is not a file")
    actual = sha256_file(transcript)
    if actual != proof.get("transcript_sha256"):
        raise RecorderAbort(
            f"§3.10 assert 8: transcript digest is {actual}, proof says "
            f"{proof.get('transcript_sha256')}"
        )
    transcript_text = transcript.read_text(encoding="utf-8")
    if replica_prestate not in transcript_text:
        raise RecorderAbort(
            "§3.10 assert 7: replica_ledger_prestate_sha256 does not appear in "
            "the rehearsal transcript"
        )
    return proof


# ---------------------------------------------------------------------------
# §3.8 transaction machinery.
# ---------------------------------------------------------------------------

class TransactionLock:
    """§3.8 step 1: exclusive creation, never O_TRUNC.

    The durable guard against re-mutation is the nonterminal journal, not this
    lock: it is not claimed to survive process exit, and a stale lock is cleared
    only by an operator who has first read the journal state.
    """

    def __init__(self, path, batch_id):
        self.path = Path(path)
        self.batch_id = batch_id

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            handle = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                             0o644)
        except FileExistsError:
            holder = self.path.read_text(encoding="utf-8", errors="replace")
            raise RecorderAbort(
                f"§3.8 step 1: transaction lock {self.path} is already held by:\n"
                f"{holder}"
            ) from None
        payload = json.dumps({
            "pid": os.getpid(),
            "batch_id": self.batch_id,
            "started_at": utc_now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        }, indent=2, sort_keys=True) + "\n"
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        return self

    def __exit__(self, exc_type, exc, traceback):
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass
        return False


class Journal:
    """§3.8 steps 6/7/9/10 — a single fsync'd JSON file per batch."""

    def __init__(self, path, record):
        self.path = Path(path)
        self.record = dict(record)

    def write(self, state, **extra):
        self.record["state"] = state
        self.record["updated_at"] = utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")
        self.record.update(extra)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.record, indent=2, sort_keys=True) + "\n"
        with open(self.path, "w", encoding="utf-8") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        fsync_path(self.path.parent)
        return self.record


def check_recovery_state(journal_dir):
    """§3.8 step 1: any nonterminal journal stops the run."""
    directory = Path(journal_dir)
    if not directory.is_dir():
        return
    for entry in sorted(directory.glob("*.json")):
        try:
            record = json.loads(entry.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RecorderAbort(
                f"§3.8 step 1: journal {entry} is unreadable ({exc}); an "
                "operator must resolve it before any further recording"
            ) from None
        state = record.get("state")
        if state not in TERMINAL_JOURNAL_STATES:
            raise RecorderAbort(
                f"§3.8 step 1: RECOVERY NOTICE — journal {entry} is in "
                f"nonterminal state {state!r}. Unproven paths: "
                f"{record.get('unproven', 'n/a')}. Surviving files: "
                f"temp={record.get('temp_path')} "
                f"preimage={record.get('preimage_path')}. Reviews in that "
                f"batch: {record.get('reviews')}. No further recording will "
                "run until an operator resolves this."
            )


def git_dirty_paths(repo_root):
    """§3.8 step 2 / §6.2 check 7 — `--untracked-files=all` so new verdict
    artifacts appear individually rather than collapsed to a directory."""
    completed = subprocess.run(
        ["git", "-C", str(repo_root), "status", "--short",
         "--untracked-files=all"],
        capture_output=True, text=True, check=True,
    )
    paths = set()
    for line in completed.stdout.splitlines():
        if not line.strip():
            continue
        entry = line[3:].strip()
        if " -> " in entry:
            entry = entry.split(" -> ", 1)[1]
        paths.add(entry.strip('"'))
    return paths


def run_validator(repo_root, relpath, extra_args):
    return subprocess.run(
        [sys.executable, str(repo_root / relpath), "--repo-root", str(repo_root)]
        + extra_args,
        capture_output=True, text=True,
    )


def blocker_report(repo_root, ledger_path=None):
    extra = ["--report-blockers"]
    if ledger_path is not None:
        extra += ["--ledger-path", str(ledger_path)]
    completed = run_validator(repo_root, PREIMPL_RELPATH, extra)
    if completed.returncode not in (0, 2):
        raise RecorderAbort(
            f"preimplementation validator exited {completed.returncode}:\n"
            f"{completed.stderr}"
        )
    return json.loads(completed.stdout), completed.returncode


def structural_exit(repo_root, ledger_path=None):
    extra = []
    if ledger_path is not None:
        extra = ["--ledger-path", str(ledger_path),
                 "--human-review-path", HUMAN_REVIEW_RELPATH]
    completed = run_validator(repo_root, STRUCTURAL_RELPATH, extra)
    return completed.returncode, completed.stderr


def check_ledger_target(repo_root):
    """§3.8 step 2: the ledger must be a plain regular file, not a symlink,
    directory, FIFO, device, or hardlink — a symlinked ledger would make the
    same-directory rename replace the link rather than the file."""
    path = repo_root / LEDGER_RELPATH
    info = os.lstat(path)
    mode = info.st_mode
    if not stat.S_ISREG(mode):
        raise RecorderAbort(f"§3.8 step 2: {LEDGER_RELPATH} is not a regular file")
    if info.st_nlink > 1:
        raise RecorderAbort(
            f"§3.8 step 2: {LEDGER_RELPATH} has {info.st_nlink} hard links"
        )
    if path.resolve() != path.absolute():
        raise RecorderAbort(
            f"§3.8 step 2: {LEDGER_RELPATH} resolves to {path.resolve()}"
        )
    return stat.S_IMODE(mode)


def atomic_replace_probe(staging_dir):
    """§3.8 step 2: prove same-directory atomic replacement works here, inside
    the private staging directory — never inside docs/goals/."""
    staging = Path(staging_dir)
    staging.mkdir(parents=True, exist_ok=True)
    source = staging / "probe.a"
    target = staging / "probe.b"
    source.write_text("a\n", encoding="utf-8")
    target.write_text("b\n", encoding="utf-8")
    os.replace(source, target)
    if target.read_text(encoding="utf-8") != "a\n" or source.exists():
        raise RecorderAbort("§3.8 step 2: same-directory atomic replacement failed")
    target.unlink()


def post_replacement_verify(repo_root, candidate_sha256, expected_dirty,
                            expected_pending, review_count, pre_mode):
    """§3.8 step 8. A module-level function so the rehearsal harness can force
    it to raise without the recorder carrying an injection hook."""
    ledger = repo_root / LEDGER_RELPATH
    actual = sha256_file(ledger)
    if actual != candidate_sha256:
        raise RecorderAbort(
            f"§3.8 step 8: canonical posthash {actual} != prepared candidate "
            f"{candidate_sha256}"
        )
    actual_mode = stat.S_IMODE(os.lstat(ledger).st_mode)
    if actual_mode != pre_mode:
        raise RecorderAbort(
            f"§3.8 step 8: ledger mode is {actual_mode:04o}, expected "
            f"{pre_mode:04o}"
        )
    code, stderr = structural_exit(repo_root)
    if code != 0:
        raise RecorderAbort(
            f"§3.8 step 8: structural validator exited {code} on the canonical "
            f"ledger:\n{stderr}"
        )
    report, _ = blocker_report(repo_root)
    check_blocker_shrink(report, expected_pending, review_count)
    dirty = git_dirty_paths(repo_root)
    if dirty != expected_dirty:
        raise RecorderAbort(
            f"§3.8 step 8: dirty-path set is {sorted(dirty)}, expected "
            f"{sorted(expected_dirty)}"
        )


def check_blocker_shrink(report, pending_before, review_count):
    """§6.2 checks 3 and 4."""
    pending_after = len(report["pending_reviews"])
    if pending_after != pending_before - review_count:
        raise RecorderAbort(
            f"§6.2 check 3: pending is {pending_after}, expected "
            f"{pending_before - review_count}"
        )
    if pending_after >= pending_before:
        raise RecorderAbort("§6.2 check 4: pending did not shrink")
    if report["stale_reviews"]:
        raise RecorderAbort(
            f"§6.2 check 4: {len(report['stale_reviews'])} stale reviews — the "
            "§3.4 ordering rule was violated"
        )
    if len(report["unmet_no_implementation_proof"]) != 1:
        raise RecorderAbort(
            "§6.2 check 4: unmet_no_implementation_proof must stay at exactly 1 "
            f"(DISP-R-1), got {len(report['unmet_no_implementation_proof'])}"
        )


def rollback(repo_root, journal, preimage_path, pre_sha256, pre_mode, reviews):
    """§3.8 steps 9 and 10.

    A rollback is reported as proven only when both bytes and mode match the
    preimage; otherwise the journal goes to RECOVERY_REQUIRED with the full
    unproven-path payload and all ledger mutation stops.
    """
    ledger = repo_root / LEDGER_RELPATH
    observed_sha256 = None
    observed_mode = None
    # r6 §3.8 step 9 (r5-review M-2): hash the preimage BEFORE the restoring
    # rename consumes it. r5 hashed only the restored ledger, so a corrupted
    # preimage was consumed unexamined and the journal's
    # `surviving_preimage_path` then named a file that no longer existed. The
    # digest below is what the journal reports as the preimage's own state.
    try:
        preimage_sha256 = sha256_file(preimage_path)
    except OSError:
        preimage_sha256 = None
    try:
        os.replace(preimage_path, ledger)
        os.chmod(ledger, pre_mode)
        fsync_path(ledger)
        fsync_path(ledger.parent)
        observed_sha256 = sha256_file(ledger)
        observed_mode = stat.S_IMODE(os.lstat(ledger).st_mode)
    except OSError:
        # The preimage is gone or unusable; fall through to RECOVERY_REQUIRED
        # with whatever the ledger currently is.
        try:
            observed_sha256 = sha256_file(ledger)
            observed_mode = stat.S_IMODE(os.lstat(ledger).st_mode)
        except OSError:
            observed_sha256 = None
            observed_mode = None

    if observed_sha256 == pre_sha256 and observed_mode == pre_mode:
        journal.write(JOURNAL_ROLLED_BACK,
                      rolled_back_sha256=observed_sha256,
                      rolled_back_mode=f"{observed_mode:04o}")
        return True

    journal.write(
        JOURNAL_RECOVERY_REQUIRED,
        unproven={
            "path": str(ledger),
            "expected_sha256": pre_sha256,
            "observed_sha256": observed_sha256,
            "expected_mode": f"{pre_mode:04o}",
            "observed_mode": (
                None if observed_mode is None else f"{observed_mode:04o}"
            ),
        },
        surviving_preimage_path=str(preimage_path),
        # r6 (r5-review M-2): the preimage's digest as it was read immediately
        # before the restoring rename, and whether that file still exists. Both
        # are what an operator needs to tell "the preimage was corrupted" from
        # "the preimage was removed".
        preimage_sha256_before_restore=preimage_sha256,
        surviving_preimage_exists=os.path.exists(preimage_path),
        reviews=reviews,
    )
    raise RecoveryRequired(
        f"§3.8 step 10: RECOVERY_REQUIRED — could not prove the rollback of "
        f"{ledger}. Expected sha256={pre_sha256} mode={pre_mode:04o}; observed "
        f"sha256={observed_sha256} mode="
        f"{'None' if observed_mode is None else format(observed_mode, '04o')}. "
        f"Journal: {journal.path}. All ledger mutation has stopped; an operator "
        "must resolve this before any further recording."
    )


# ---------------------------------------------------------------------------
# Batch driver.
# ---------------------------------------------------------------------------

def run_batch(repo_root, manifest_path, dry_run=False):
    """§3.8 steps 1-10 for one batch. Returns a result dict."""
    repo_root = Path(repo_root).resolve()
    recorder_sha256 = sha256_file(Path(__file__).resolve())
    manifest = load_manifest(manifest_path)
    batch_id = manifest["batch_id"]
    entries = manifest["reviews"]
    review_count = len(entries)
    ledger = repo_root / LEDGER_RELPATH

    # Step 1 — lock, then recovery check.
    with TransactionLock(repo_root / LOCK_RELPATH, batch_id):
        check_recovery_state(repo_root / JOURNAL_RELDIR)

        # Step 2 — preconditions, before any write.
        assert_rehearsal_proof(repo_root, recorder_sha256)
        pre_mode = check_ledger_target(repo_root)

        baseline_dirty = set(manifest["baseline_dirty_paths"])
        batch_targets = {LEDGER_RELPATH} | {
            entry["artifact_path"] for entry in entries
        }
        dirty = git_dirty_paths(repo_root)
        outside = dirty - batch_targets
        if outside != baseline_dirty:
            raise RecorderAbort(
                f"§3.8 step 2: dirty paths outside the batch are "
                f"{sorted(outside)}, baseline is {sorted(baseline_dirty)}"
            )

        pre_sha256 = sha256_file(ledger)
        if pre_sha256 != manifest["ledger_prehash_sha256"]:
            raise RecorderAbort(
                f"§3.8 step 2: live ledger is {pre_sha256}, manifest prehash is "
                f"{manifest['ledger_prehash_sha256']}"
            )

        for relpath, pinned in ((STRUCTURAL_RELPATH, PINNED_STRUCTURAL_SHA256),
                                (PREIMPL_RELPATH, PINNED_PREIMPL_SHA256),
                                (EXTRACTOR_RELPATH, PINNED_EXTRACTOR_SHA256)):
            actual = sha256_file(repo_root / relpath)
            if actual != pinned:
                raise RecorderAbort(
                    f"§3.8 step 2: {relpath} is {actual}, §1.1 pins {pinned}"
                )

        extractor = subprocess.run(
            [sys.executable, str(repo_root / EXTRACTOR_RELPATH), "--check"],
            capture_output=True, text=True, cwd=str(repo_root),
        )
        if extractor.returncode != 0:
            raise RecorderAbort(
                f"§3.8 step 2: extract_goal_validators.py --check exited "
                f"{extractor.returncode}:\n{extractor.stderr}"
            )

        code, stderr = structural_exit(repo_root)
        if code != 0:
            raise RecorderAbort(
                f"§3.8 step 2: structural validator exited {code} on the "
                f"canonical ledger:\n{stderr}"
            )

        rows = load_rows(ledger)
        by_id = {row["component_id"]: row for row in rows}
        batch_ids = {entry["component_id"] for entry in entries}
        missing = sorted(batch_ids - set(by_id))
        if missing:
            raise RecorderAbort(f"§3.8 step 2: unknown component_ids {missing}")

        check_projection_equivalence(
            repo_root, equivalence_sample(rows, batch_ids)
        )

        now = utc_now()
        captured_at_by_key = {}
        for entry in entries:
            parsed = validate_batch_entry(repo_root, entry, now)
            captured_at_by_key[(entry["component_id"], entry["review_type"])] = (
                parsed["captured_at"]
            )

        for component_id in sorted(batch_ids):
            row = by_id[component_id]
            applicable = applicable_review_types(row)
            if not applicable:
                raise RecorderAbort(
                    f"{component_id}: an alias has no review slots and is never "
                    "a batch target"
                )
            if row["kind"] == REGISTER_KIND:
                # §1.2 / goal L208-211: contractually null, and it stays null.
                if row["scope_derivation"]["semantic_review"] is not None:
                    raise RecorderAbort(
                        f"{component_id}: a register row's semantic_review must "
                        "be null"
                    )
            for review_type in applicable:
                slot = review_slot(row, review_type)
                if not isinstance(slot, dict) or slot.get("status") != STATUS_PENDING:
                    raise RecorderAbort(
                        f"§6.2 check 9: {component_id}/{review_type} is not "
                        f"PENDING (status={None if not isinstance(slot, dict) else slot.get('status')!r})"
                        "; a completed row is refused, never re-recorded"
                    )

        staging_dir = repo_root / STAGING_RELDIR
        atomic_replace_probe(staging_dir)

        report_before, _ = blocker_report(repo_root)
        pending_before = len(report_before["pending_reviews"])

        # Step 3 — build in memory.
        candidate_rows = build_candidate(rows, entries, captured_at_by_key)
        check_candidate_shape(rows, candidate_rows, entries)
        candidate_bytes = serialize_rows(candidate_rows).encode("utf-8")
        candidate_sha256 = sha256_bytes(candidate_bytes)

        token = f"{os.getpid()}.{int(now.timestamp())}"
        temp_path = ledger.parent / f".{ledger.name}.candidate.{token}"
        preimage_path = ledger.parent / f".{ledger.name}.preimage.{token}"
        cleanup = set()
        preserve_files = False
        journal = None
        result = {
            "batch_id": batch_id, "review_count": review_count,
            "pending_before": pending_before, "dry_run": dry_run,
            "ledger_prehash_sha256": pre_sha256,
            "candidate_sha256": candidate_sha256,
        }

        try:
            # Step 4 — stage.
            handle = os.open(str(temp_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                             pre_mode)
            cleanup.add(temp_path)
            with os.fdopen(handle, "wb") as stream:
                stream.write(candidate_bytes)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temp_path, pre_mode)
            fsync_path(ledger.parent)

            # Step 5 — validate the candidate, not the target.
            code, stderr = structural_exit(repo_root, temp_path)
            if code != 0:
                raise RecorderAbort(
                    f"§3.8 step 5: structural validator exited {code} on the "
                    f"candidate:\n{stderr}"
                )
            report_after, preimpl_code = blocker_report(repo_root, temp_path)
            check_blocker_shrink(report_after, pending_before, review_count)
            result["pending_after"] = len(report_after["pending_reviews"])
            result["stale_after"] = len(report_after["stale_reviews"])
            result["preimpl_exit"] = preimpl_code
            result["structural_candidate_exit"] = 0

            if dry_run:
                # --dry-run runs every precondition and digest computation and
                # validates the candidate, then writes no journal and never
                # touches the canonical ledger.
                result["committed"] = False
                return result

            # Step 6 — journal.
            journal = Journal(
                repo_root / JOURNAL_RELDIR / f"{batch_id}.json",
                {
                    "batch_id": batch_id,
                    "target_path": str(ledger),
                    "pre_sha256": pre_sha256,
                    "post_sha256": candidate_sha256,
                    "pre_mode": f"{pre_mode:04o}",
                    "temp_path": str(temp_path),
                    "preimage_path": str(preimage_path),
                    "reviews": [
                        f"{entry['component_id']}::{entry['review_type']}"
                        for entry in entries
                    ],
                    "structural_candidate_exit": 0,
                    "preimplementation_candidate_exit": preimpl_code,
                    "started_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )
            journal.write(JOURNAL_PREPARED)

            # The preimage lives beside the ledger for the duration of the
            # transaction (step 9 restores it by same-directory rename), so it
            # is transient scaffolding rather than batch output. It is named
            # explicitly here — never filtered by pattern — so an unexpected
            # file in docs/goals/ still fails step 8.
            expected_dirty = baseline_dirty | batch_targets | {
                str(preimage_path.relative_to(repo_root))
            }

            # Steps 7-9 — replace, post-verify, rollback. Guarded at
            # BaseException level so an interrupt cannot leave a mixed ledger.
            previous_sigterm = signal.getsignal(signal.SIGTERM)
            signal.signal(signal.SIGTERM, _sigterm_handler)
            # `attempted` is set BEFORE the rename, and the handler decides
            # whether to roll back by comparing the ledger's current bytes to
            # the prehash rather than by trusting a post-rename assignment. An
            # interrupt delivered between the rename completing and the next
            # bytecode would otherwise skip the rollback entirely.
            attempted = False
            try:
                # Compare-and-swap against the recorded prehash.
                live = sha256_file(ledger)
                if live != pre_sha256:
                    raise RecorderAbort(
                        f"§3.8 step 7: live ledger changed under us ({live} != "
                        f"{pre_sha256})"
                    )
                shutil_copy_preimage(ledger, preimage_path, pre_mode)
                cleanup.add(preimage_path)
                attempted = True
                os.replace(temp_path, ledger)
                cleanup.discard(temp_path)
                os.chmod(ledger, pre_mode)
                fsync_path(ledger)
                fsync_path(ledger.parent)
                actual_mode = stat.S_IMODE(os.lstat(ledger).st_mode)
                if actual_mode != pre_mode:
                    raise RecorderAbort(
                        f"§3.8 step 7: replaced file mode is {actual_mode:04o}"
                    )
                journal.write(JOURNAL_PREPARED, replaced=True)

                # Step 8 — post-verify on the canonical path.
                post_replacement_verify(
                    repo_root, candidate_sha256, expected_dirty, pending_before,
                    review_count, pre_mode,
                )
                journal.write(JOURNAL_COMMITTED)
            except BaseException:
                if attempted and _ledger_needs_rollback(ledger, pre_sha256,
                                                        pre_mode):
                    try:
                        rollback(repo_root, journal, preimage_path, pre_sha256,
                                 pre_mode, journal.record["reviews"])
                        cleanup.discard(preimage_path)
                    except RecoveryRequired:
                        preserve_files = True
                        raise
                raise
            finally:
                signal.signal(signal.SIGTERM, previous_sigterm)

            cleanup.discard(preimage_path)
            try:
                preimage_path.unlink()
            except FileNotFoundError:
                pass
            result["committed"] = True
            result["ledger_posthash_sha256"] = sha256_file(ledger)
            return result
        finally:
            if not preserve_files:
                for path in cleanup:
                    try:
                        Path(path).unlink()
                    except FileNotFoundError:
                        pass


def _ledger_needs_rollback(ledger, pre_sha256, pre_mode):
    """True when the canonical path no longer holds the pre-state bytes/mode.

    Used instead of a post-rename flag so that an interrupt delivered at any
    instruction around the rename still routes into step 9.
    """
    try:
        info = os.lstat(ledger)
    except OSError:
        return True
    return (sha256_file(ledger) != pre_sha256
            or stat.S_IMODE(info.st_mode) != pre_mode)


def shutil_copy_preimage(source, destination, mode):
    """Same-directory preimage copy, so step 9's restore is an atomic rename."""
    payload = Path(source).read_bytes()
    handle = os.open(str(destination), os.O_CREAT | os.O_EXCL | os.O_WRONLY, mode)
    with os.fdopen(handle, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(destination, mode)
    fsync_path(Path(destination).parent)


def _sigterm_handler(signum, frame):
    """§3.8 step 9: route SIGTERM into the same guarded rollback path."""
    raise SystemExit(1)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Record COMPLETE inventory reviews on the blueprint ledger."
    )
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--batch", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = run_batch(args.repo_root, args.batch, dry_run=args.dry_run)
    except RecoveryRequired as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except RecorderAbort as exc:
        print(f"ABORT: {exc}", file=sys.stderr)
        return 1
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
