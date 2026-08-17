# DISP-R-1 amendment design r1

**Status: DESIGN ONLY — NOT APPROVED FOR EXECUTION.**

The user has approved **designing** this amendment and has approved **adding a
formal `HR-0005` human-review record** to it. The user has **not** approved
**executing** it. Nothing in this document may be applied to any canonical
file. No canonical byte, no Beads record, and no Git state was changed to
produce it. The only files written were probes under `scratchpad/disp-r1/`
and a throwaway staging root under `/tmp/`.

**Supersedes** `docs/goals/reviews/ledger/equity-os-blueprint-disp-r1-amendment-design-r0.md`
(SHA-256 `675cb4877d9eef6b49ea8b825c8dc11fa9f1b5363e88df0dbc657e3d52727326`),
which is **BLOCKED** and must not be executed.

Predetermined independent review path:
`docs/goals/reviews/ledger/equity-os-blueprint-disp-r1-amendment-design-r1-review-r0.md`

---

## Decisions of record

| # | Decision | Source | Effect on this design |
|---|---|---|---|
| D1 | The amendment **must** carry a formal human-review record — r0 §5.7 option **(b)**. Option (a) is dead. | **User decision, 2026-08-15** | The transaction creates `HR-0005` + `HRD-0005-001`, links `DISP-R-1`, and appends one transition. Scope is **four** canonical files, not two. |
| D2 | The recorded `decision_type` is `RECONCILE_AUTHORITY`. | Live closed vocabulary, `validate_ledger_structural.py:994-999` | `AMEND_VALIDATOR_PIN` is **not** in `decision_types`; it survives only as an informal English label, never as a recorded value. §4.2. |
| D3 | The amendment is **line-count-preserving** for goal lines 1-5847. | This document's own finding N1 (§3.6) | Program spans B/C/D are exactly line-neutral; all added prose is appended below line 5847. |
| D4 | Strict ordering: **T1 → 447-review recorder → T2.** | Review finding F3, proved here by J5 | §8.3. Mandatory, not advisory. |

---

## 0. Verified pre-state

Every hash below was computed fresh with `sha256sum` at the start of this work
and re-verified byte-identical at the end.

| Artifact | SHA-256 |
|---|---|
| `docs/goals/equity-os-blueprint-completion.md` | `f15f7ab5a4e425dec3877ab7f1f7594687979060e4dbcd49390a8a8d5fedb85f` |
| `docs/goals/equity-os-blueprint-component-ledger.jsonl` | `de236d7e8dcf02e307ec58797f5722ae2f85d1d8cdba57d4ecc07df5383c9c97` |
| `docs/goals/equity-os-blueprint-human-review-needed.md` | `094fcdfab74a3f4c6fdb82b1520fc4d13b636ac0e9ed10194e5d607aed2ce9af` |
| `scripts/equity_os_blueprint/validate_ledger_structural.py` | `731d0d8b208b577967c92e3992e7ec1a4333cdecbf89f6951c32d2ec469436f9` |
| `scripts/equity_os_blueprint/validate_ledger_preimplementation.py` | `f7a225a1f99cb85c92cde3094505a92a746552280eb45dae0253a71ab9048013` |
| `scripts/equity_os_blueprint/extract_goal_validators.py` | `5d20d796666d1154fb3c84ba4fa7407ee82819510a5ac06254f7f4a3126c6f2a` |
| `CONTEXT.md` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `docs/specs/equity-os-s20-memory-benchmark-gbrain.md` | `4948d0f84240cd58b107da1272ed2b90a386bc3fb9ebb6228faac8b98be9c483` |
| `…-disp-r1-amendment-design-r0.md` (superseded) | `675cb4877d9eef6b49ea8b825c8dc11fa9f1b5363e88df0dbc657e3d52727326` |

Baseline validator state, run against canonical bytes:

```
python3 scripts/equity_os_blueprint/extract_goal_validators.py --check          # exit 0
python3 scripts/equity_os_blueprint/validate_ledger_structural.py --repo-root . # exit 0
python3 scripts/equity_os_blueprint/validate_ledger_preimplementation.py \
    --repo-root . --report-blockers                                             # exit 2
```

The preimplementation report is `ready=false` with `pending_reviews` = **447**,
`stale_reviews` = **0**, and exactly one `unmet_no_implementation_proof` entry:
`DISP-R-1` / `REQ-DISP-R-1-NO-IMPLEMENTATION`, historical ref
`EV-DISP-R-1-SPEC-DRAFT`, reason codes `CURRENT_REVIEWER_ROLE_EVIDENCE_REVIEW_MISSING`,
`HISTORICAL_REFS_UNCOVERED`, `REQUIREMENT_UNRESOLVED`.

Further live counts used below, freshly measured:

| Quantity | Value | How measured |
|---|---|---|
| Live transition objects in the ledger | **648** | sum of `len(row["transition_history"])` |
| Pinned baseline **prefix** length sum | **454** | `sum(BASELINE_PREFIX_LENGTHS.values())`, `validate_ledger_structural.py:2907` |
| `DISP-R-1` baseline prefix length | **2** | `BASELINE_PREFIX_LENGTHS["DISP-R-1"]` |
| `DISP-R-1` current history length | **4** | live row |
| Goal line count | **5894** | `wc -l` |
| Transitions citing `HRD-0004-001` | **194**, across **144** rows | scan of `human_resolution_sha256` |

---

## 1. Facts first — the deadlock, mechanically reproduced

This section is carried from r0. The independent review verified every claim in
it (items 1a-1f, all **CONFIRMED**), except three line cites corrected here per
minor finding **M1**.

### 1.1 The line cites

Verified against `validate_ledger_structural.py` @
`731d0d8b208b577967c92e3992e7ec1a4333cdecbf89f6951c32d2ec469436f9`:

- `:2674-2686` — `EXPECTED_DISP_R1_REQUIREMENT`, a literal dict pinning
  `"status": "UNRESOLVED"` and `"evidence_ref_ids": []` alongside the
  requirement's identity fields.
- `:2756` — `assert EXPECTED_DISP_R1_REQUIREMENT in disp_r1["required_evidence"]`.
- `:2760` — `assert disp_r1_proven is False`.
- `:2761-2763` — asserts `{"REQUIREMENT_UNRESOLVED",
  "CURRENT_REVIEWER_ROLE_EVIDENCE_REVIEW_MISSING"} <= set(disp_r1_reasons)`.
- `:2821-2822` — `assert overlapping == set().union(*EXPECTED_PRIOR_HR_LINKS.values())`
  and `assert len(overlapping) == 23`. **This is the fourth pin, which r0
  missed.** See §3.5.
- `validate_ledger_preimplementation.py:126-217` — the closed predicate and the
  `unmet_no_implementation_proof` accumulator, with boundaries `:128`, `:132`,
  `:217`.
- Goal SUCCESS condition 5 at `docs/goals/equity-os-blueprint-completion.md:5752-5756`.

**Corrections from M1** (substance unchanged in every case):

| Cited in r0 | Actual | What is there |
|---|---|---|
| structural `:352-357` | **`:350-355`** | `reviewed_input_sha256` / `reviewed_inventory_sha256` recomputation |
| structural `:341-348` | **`:340-349`** | reviewer/verdict/timestamp block |
| goal `:461-474` | **goal `:460-474`** | the A6 typed-evidence paragraph |

### 1.2 The mechanism, precisely

The block is a single `in` test against a whole-object literal, at `:2756`, and
it runs **unconditionally at module top level**. The two `args.reconciliation_check`
guards in the file cover `:31-32` and `:2912-3244`; the DISP-R-1 statements at
`:2752`, `:2753`, `:2756`, `:2757`, `:2760`, `:2761`, `:2764` are all top-level
`Assign`/`Assert` nodes outside both guards, verified by AST walk. A grep for
`DISP-R-1` and `no_implementation` inside `:2912-3244` returns nothing.

### 1.3 Both horns reproduced

Probe `scratchpad/disp-r1/probe_deadlock.py` (r0), independently reproduced by
the reviewer.

**Horn B — leave the requirement unresolved.** Canonical bytes: exit 2,
`ready=False`, the single DISP-R-1 unmet entry with all three reason codes.

**Horn A — satisfy the requirement properly.** A candidate ledger in which
`REQ-DISP-R-1-NO-IMPLEMENTATION` is `SATISFIED` with
`evidence_ref_ids=["EV-DISP-R-1-SPEC-DRAFT"]` and `evidence_inventory_review` is
a `COMPLETE`/`CLEAN` `REVIEWER`-role review bound to `CONTEXT.md` with both
content digests recomputed over the post-state row fails structural validation
at **exactly `:2756`**.

Against that same satisfying candidate the *preimplementation* validator
reports `exit=2 ready=False  DISP-R-1 unmet entries=0  pending_reviews=446
stale_reviews=0`. The DISP-R-1 blocker is gone. The closed predicate, the
ledger schema, the review schema, and the preimplementation gate all already
admit a correct proof. **Only the structural pins stand in the way.**

### 1.4 The goal's own prose already licenses the proof

`docs/goals/equity-os-blueprint-completion.md:460-474`, verbatim:

> `rejection_record.no_implementation_evidence_ref_ids` is an immutable
> historical record of which references supported the rejection when it was
> recorded; membership never establishes current proof by itself. Structural
> validation owns the exact current no-implementation requirement map. A
> rejected component has current no-implementation proof only when every
> historical ref is covered by the union of `evidence_ref_ids` on its mapped
> requirements, every mapped requirement is currently `SATISFIED`, every
> referenced evidence object validates against current bytes, and
> `evidence_inventory_review` is a current content-bound `COMPLETE`/`CLEAN`
> review performed under role `REVIEWER`, whose evidence refs include every
> historical ref and whose timestamp is no earlier than their current captures,
> and whose reviewed-input and reviewed-inventory digests equal the validator's
> current projections. False is a valid structural state and an explicit
> preimplementation and terminal blocker; no description substring or refreshed
> content digest substitutes for this closed predicate.

Goal SUCCESS condition 5, `:5752-5756`, verbatim:

> Every still-`Deferred` row is `CONDITIONAL_UNACTIVATED` with its trigger
> represented by a current fully resolved predicate that recomputes `FALSE`,
> and has no delivery work; every derived rejected canonical component is
> `REJECTED_ACCOUNTED` with a validated rejection record, explicit rationale,
> and current no-implementation proof.

The prose defines a *reachable* proof condition and SUCCESS *requires* reaching
it. Outside the three embedded program spans (goal lines 1356-4600, 4607-4865,
4873-5700), the string `DISP-R-1` occurs in the goal exactly **once**, at line
5831, inside the immutable HR-0004 approval record, which this amendment does
not touch. The reviewer independently confirmed: 19 total hits, exactly one
outside the spans.

**The goal's prose and the goal's extracted validator disagree.** The amendment
corrects the validator side.

### 1.5 Deliberate temporary measure, or oversight? — Both, in separable parts

**The unproven post-state was deliberate.** r7 §3.6
(`…-ledger-remediation-design-r7.md:576-593`):

> `DISP-R-1` is deliberately not counted as having current no-implementation
> proof after this transaction. […] The unchanged rejection record continues to
> account for the pinned rejection authority, but its historical
> `no_implementation_evidence_ref_ids=["EV-DISP-R-1-SPEC-DRAFT"]` does not
> satisfy the requirement. **A later substantive review may establish current
> proof only by changing the requirement and review through the ordinary
> evidenced process; this reconciliation does not perform or imply that review.**

**The permanence of the pin was an over-implementation.** r7 §8.1 (`:1541-1551`)
scopes the pin with "**In reconciliation mode**" and "**in this post-state**";
the generated validator placed it at module top level.

Calibration, unchanged from r0 and endorsed by the reviewer:

- **Certain:** the pin executes unconditionally on every structural run
  (AST-verified), and no DISP-R-1 assertion exists inside the reconciliation
  block (grep-verified, returns nothing).
- **Certain:** r7 §3.6 explicitly contemplates a later change establishing proof.
- **Inference (strong):** r7 §8.1's scoping language means top-level placement
  exceeds what §8.1 specified.
- **Speculation, flagged as such:** whether that placement was a mistake or a
  deliberate belt-and-braces choice. No evidence either way.

---

## 2. What a genuine current proof would be

### 2.1 The requirement, as it stands

```json
{"approval_ids":[],"description":"Current S20 draft preserves D-02 as dormant and contains no implementation claim","evidence_id":"REQ-DISP-R-1-NO-IMPLEMENTATION","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"R-1 current no-implementation proof","status":"UNRESOLVED"}
```

`rejection_record.no_implementation_evidence_ref_ids` is `["EV-DISP-R-1-SPEC-DRAFT"]`.

### 2.2 The artifact and its digest binding

`EV-DISP-R-1-SPEC-DRAFT` already binds the right artifact:

```json
{"captured_at":"2026-08-15T07:13:28Z","content_sha256":"4948d0f84240cd58b107da1272ed2b90a386bc3fb9ebb6228faac8b98be9c483","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-DISP-R-1-SPEC-DRAFT","path":"docs/specs/equity-os-s20-memory-benchmark-gbrain.md","scope":"Current draft specification bytes for DISP-R-1","start_line":null}
```

`sha256sum docs/specs/equity-os-s20-memory-benchmark-gbrain.md` =
`4948d0f8…be9c483`. The evidence object is current against live bytes, which is
why `HISTORICAL_REF_STALE` does not appear in the reason codes.

`FILE_BYTES` over the whole spec is the correct binding: the claim is negative
and whole-file, so a `UTF8_LINE_SPAN` over an excerpt would be strictly weaker.
No new evidence object is needed for the proof itself. The reviewer
independently agreed with this argument.

### 2.3 What S20 actually says about D-02 — verified

The spec (268 lines) preserves D-02 as dormant and makes no implementation
claim: `:7`, `:17`, `:20`, `:35`, `:39`, `:174`, `:251`. The independent
reviewer read all 268 lines and **confirmed every cite is exact** and that
"S20 can honestly support the proof."

**This remains a corroborating read, not the required review.** The
`REVIEWER`-role evidence review of S20 is a separate act by a separate agent at
a real timestamp, and §5 turns on exactly that.

### 2.4 What the review must look like — from the live schema

Read from `validate_ledger_structural.py:238-357`:

- `review_fields` = `{review_type, status, reviewer, model, effort, verdict,
  timestamp, evidence_ref_ids, reviewed_input_sha256, reviewed_inventory_sha256}`.
- A `COMPLETE` review must have **exactly** `review_fields | {role,
  role_binding_path, role_binding_sha256}` (`:325`); a `PENDING` review exactly
  `review_fields` (`:327`). DISP-R-1's current review is `PENDING` and correctly
  lacks the role-binding keys — **no schema change is needed** to record a
  `COMPLETE` review.
- `assert_reviewer_role_binding` (`:250-262`): `role == "REVIEWER"`,
  `role_binding_path == "CONTEXT.md"`, `role_binding_sha256` a 64-hex digest,
  non-empty `model` and `effort`.
- `verdict == "CLEAN"`, non-empty `reviewer`, `timestamp <= validation_now` and
  `>=` every linked ref's `captured_at` (**`:340-349`**).
- `reviewed_input_sha256` == `canonical_sha256(review_input_projection(row))`
  and `reviewed_inventory_sha256` == `canonical_sha256(review_inventory_projection(row, "EVIDENCE"))`
  (**`:350-355`**).

Two consequences:

1. `review_input_projection` includes `required_evidence` (`:277`), so the
   requirement's `status` flip changes the digest the review must carry. The
   review must be sealed against the **post-state** row, and is the last field
   written.
2. `role_binding_sha256` is an immutable historical capture (docstring
   `:252-255`), so a later `CONTEXT.md` edit does not invalidate completed
   reviews. Current `CONTEXT.md` = `8f2795af…3198ce`.

Per `CONTEXT.md:137-147`, `REVIEWER` is "an independent subagent that reviews an
implementer's output. Always a separate agent and context from the implementer
of the same artifact." The recorded `model` and `effort` must be the
actually-invoked values.

---

## 3. The amendment — four spans

### 3.1 Design principle

Do not delete a protection — **make it two-sided**. Each pin today asserts one
permitted state; the amendment asserts exactly **two** permitted states, with
the second gated on an independently-computed closed predicate. Deleting any
assert outright would be smaller but strictly worse.

The requirement's **identity** stays pinned byte-for-byte. Only `status` and
`evidence_ref_ids` become mobile, and only together. The HR-0001..3 overlap set
stays pinned; exactly one further overlap becomes admissible, and only for a
fully-conforming `HR-0005`.

### 3.2 Span A — goal prose, **appended below line 5847**

Unlike r0, this prose is **not** inserted after the A6 paragraph. It is
appended at the end of the goal file. The reason is finding **N1** (§3.6): goal
lines 1-5847 must keep their line numbering.

**Operation:** append the exact block below to the end of
`docs/goals/equity-os-blueprint-completion.md`, preceded by exactly one blank
line. The canonical file's last line is `goal.` (line 5894) and it ends with a
single `\n`.

```
## A12 amendment — DISP-R-1 closed two-state proof rule

Structural validation additionally owns the mapped requirement's immutable
identity and its closed two-state rule. `DISP-R-1` has exactly two permitted
proof states: its mapped requirement is `UNRESOLVED` with no evidence refs and
the closed predicate is false with its fixed reason codes, or the requirement
is `SATISFIED` with evidence refs covering every historical rejection-record
ref and the closed predicate is independently true with no reasons. The
requirement's identity fields never change, and no third state exists, so a
`SATISFIED` status can never be asserted by fiat, by a refreshed content
digest, or by the historical `rejection_record` references alone.

Exactly one human-review entry beyond `HR-0004` may link `DISP-R-1`. That
entry is `HR-0005`, it may project no other component, it may link `DISP-R-1`
only alongside `HR-0004`, and it must carry a single active
`RECONCILE_AUTHORITY` resolution by a human actor under
`GOAL_OR_PROCESS_AUTHORIZATION`. No other component may gain a second
human-review link.

This section is appended below goal line 5847 because
`HR-EV-0004-APPROVAL-RECORD` is a `UTF8_LINE_SPAN` over goal lines 5791-5847
that structural validation re-verifies against live bytes on every run. Every
amendment to this goal must preserve the line numbering of lines 1-5847.
```

The A6 required marker — `has current no-implementation proof only when` — is
untouched and still present in prose. No lane token is introduced. Verified:
`extract_goal_validators.py --check` on the candidate goal → exit **0**,
including the D.1 required-marker and D.2 lane-token checks.

### 3.3 Span B — the pinned literal (goal `:4028-4040`, structural `:2674-2686`)

**13 lines → 13 lines.**

**Before** (exact, 1 occurrence):

```python
EXPECTED_DISP_R1_REQUIREMENT = {
    "approval_ids": [],
    "description": (
        "Current S20 draft preserves D-02 as dormant and contains no "
        "implementation claim"
    ),
    "evidence_id": "REQ-DISP-R-1-NO-IMPLEMENTATION",
    "evidence_ref_ids": [],
    "evidence_type": "ARTIFACT",
    "proof_mode": "CONTENT_HASH",
    "scope": "R-1 current no-implementation proof",
    "status": "UNRESOLVED",
}
```

**After** (exact):

```python
# Immutable identity of the mapped DISP-R-1 proof requirement (A12).
EXPECTED_DISP_R1_REQUIREMENT_IDENTITY = {
    "approval_ids": [],
    "description": (
        "Current S20 draft preserves D-02 as dormant and contains no "
        "implementation claim"
    ),
    "evidence_id": "REQ-DISP-R-1-NO-IMPLEMENTATION",
    "evidence_type": "ARTIFACT",
    "proof_mode": "CONTENT_HASH",
    "scope": "R-1 current no-implementation proof",
}
DISP_R1_MUTABLE_FIELDS = {"status", "evidence_ref_ids"}  # move only together
```

### 3.4 Span C — the post-state asserts (goal `:4110-4122`, structural `:2756-2768`)

**13 lines → 13 lines.** `disp_r1 = by_id["DISP-R-1"]` and the
`rejection_record` assert at `:2752-2755` are unchanged and are not part of the
replaced span.

**Before** (exact, 1 occurrence):

```python
assert EXPECTED_DISP_R1_REQUIREMENT in disp_r1["required_evidence"]
disp_r1_proven, disp_r1_reasons = current_no_implementation_proof(disp_r1)
# r7 §3.6 requires this post-state to be explicitly unproven, and r7 §8.1 fixes
# the two reason codes that a digest refresh alone can never remove.
assert disp_r1_proven is False
assert {
    "REQUIREMENT_UNRESOLVED", "CURRENT_REVIEWER_ROLE_EVIDENCE_REVIEW_MISSING"
} <= set(disp_r1_reasons)
assert any(
    item["component_id"] == "DISP-R-1"
    and item["requirement_id"] == "REQ-DISP-R-1-NO-IMPLEMENTATION"
    for item in unmet_no_implementation_proof
)
```

**After** (exact):

```python
# A12 closed two-state rule. r7 §3.6/§8.1 kept this post-state explicitly
# unproven with reason codes a digest refresh can never remove; that stays the
# only alternative to a fully evidenced current proof, and no third state exists.
disp_r1_requirement = next(item for item in disp_r1["required_evidence"] if item["evidence_id"] == "REQ-DISP-R-1-NO-IMPLEMENTATION")
assert {key: value for key, value in disp_r1_requirement.items() if key not in DISP_R1_MUTABLE_FIELDS} == EXPECTED_DISP_R1_REQUIREMENT_IDENTITY
disp_r1_proven, disp_r1_reasons = current_no_implementation_proof(disp_r1)
disp_r1_unmet = [item for item in unmet_no_implementation_proof if item["component_id"] == "DISP-R-1"]
if disp_r1_requirement["status"] == "UNRESOLVED":
    assert disp_r1_proven is False and {"REQUIREMENT_UNRESOLVED", "CURRENT_REVIEWER_ROLE_EVIDENCE_REVIEW_MISSING"} <= set(disp_r1_reasons)
    assert any(item["requirement_id"] == "REQ-DISP-R-1-NO-IMPLEMENTATION" for item in disp_r1_unmet)
else:
    assert disp_r1_requirement["status"] == "SATISFIED" and disp_r1_proven is True and disp_r1_reasons == [] and not disp_r1_unmet
    assert set(disp_r1_requirement["evidence_ref_ids"]) >= set(disp_r1["rejection_record"]["no_implementation_evidence_ref_ids"])
```

The `UNRESOLVED` branch deliberately omits an `evidence_ref_ids == []` assert:
the global schema already enforces the `UNRESOLVED` ↔ empty-refs coupling at
`:2138-2141` (proved live by attack **K5**, which is rejected at `:2141`).

**Style note, stated plainly.** Four of these lines exceed the 79-column
convention the rest of the program follows. That is a direct cost of D3
(line-count preservation) and I am not hiding it: the alternative is to shift
goal line numbering, which breaks `HR-EV-0004-APPROVAL-RECORD` (§3.6). No
mechanical check in this repo enforces line length; `extract_goal_validators.py`
syntax-checks each extracted program and passed. If the reviewer prefers
readability over line-neutrality, the only other route is §3.6 remedy R-B,
whose cost is 194 rewritten transitions across 144 rows.

### 3.5 Span D — the HR overlap pin (goal `:4171-4176`, structural `:2817-2822`)

**This span is new in r1.** It is the fourth pinned assertion that r0 never
found and that the independent review proved (probes B4/B5) is a hard blocker on
the user's chosen option (b). **6 lines → 6 lines.**

I reproduced the blocker independently by construction before designing around
it: probe **G3** builds the complete, correctly-formed `HR-0005` package
(entry + `RECONCILE_AUTHORITY` resolution + ledger link + appended
`AUTHORITY_RECONCILIATION` transition + recomputed `transition_history_sha256`)
and runs the **canonical** structural validator against it:

```
Traceback (most recent call last):
  File ".../validate_ledger_structural.py", line 2821, in <module>
    assert overlapping == set().union(*EXPECTED_PRIOR_HR_LINKS.values())
AssertionError
```

`DISP-R-1` gains a second human-review link, so it enters `overlapping`, which
is pinned to exactly the 23 HR-0001..3 rows.

**Before** (exact, 1 occurrence):

```python
    overlapping = {
        component_id for component_id, links in human_review_links.items()
        if len(links) > 1
    }
    assert overlapping == set().union(*EXPECTED_PRIOR_HR_LINKS.values())
    assert len(overlapping) == 23
```

**After** (exact):

```python
    overlapping = {c for c, links in human_review_links.items() if len(links) > 1}
    hr0005 = human_entries.get("HR-0005")  # A12: the sole admissible addition
    amendment_overlap = {"DISP-R-1"} if hr0005 else set()
    assert overlapping == set().union(*EXPECTED_PRIOR_HR_LINKS.values()) | amendment_overlap
    assert len(overlapping) == 23 + len(amendment_overlap)
    assert not hr0005 or (human_scope_components["HR-0005"] == frozenset({"DISP-R-1"}) and human_review_links["DISP-R-1"] == frozenset({"HR-0004", "HR-0005"}) and hr0005["entry_type"] == "DECISION" and hr0005["decision_authority"]["approval_type"] == "GOAL_OR_PROCESS_AUTHORIZATION" and [r["decision_id"] for r in human_resolutions.values() if r["human_review_id"] == "HR-0005"] == [r["decision_id"] for r in active_human_resolutions.values() if r["human_review_id"] == "HR-0005" and r["decision_type"] == "RECONCILE_AUTHORITY" and r["actor"]["actor_type"] == "HUMAN" and r["actor"]["role"] == "CURRENT_USER" and r["authority_basis"]["approval_type"] == "GOAL_OR_PROCESS_AUTHORIZATION"])
```

Why this shape, and why it is two-sided:

- Absent an `HR-0005` entry the assertion is **byte-for-byte equivalent to
  today's**: `amendment_overlap` is empty, the equality is the same set, and the
  count is 23. No other entry and no other row can ever enter the overlap set.
- The admission is gated on `HR-0005` being fully conforming: it must project
  **exactly** `{"DISP-R-1"}` (projection, not just `component_ids`, so a
  register/spec/bead-mediated widening cannot slip through), `DISP-R-1`'s links
  must be exactly `{HR-0004, HR-0005}`, and the entry's resolution list must be
  identical to its *active* `RECONCILE_AUTHORITY` human-actor resolutions under
  `GOAL_OR_PROCESS_AUTHORIZATION`. A superseded, revoked, agent-authored, or
  wrongly-typed resolution makes the two lists differ and the assert fails.
- The last equality is a list-vs-list comparison of `decision_id`s, so it also
  pins "exactly one resolution on this entry".

The scope assertion is **load-bearing, not decorative**: attacks **H1** (an
`HR-0005` scoped to a different HR-0004 row) and **H2** (`HR-0005` scoped to
`DISP-R-1` *plus* a second row) are both rejected at that exact line
(candidate `:2820`).

### 3.6 N1 — a second Critical this design found: the goal is line-anchored

**Neither r0 nor the independent review examined this, and it invalidates the
whole three-span package and the four-span package alike unless handled.**

`HR-0004`'s entry evidence `HR-EV-0004-APPROVAL-RECORD` is a `UTF8_LINE_SPAN`
over **`docs/goals/equity-os-blueprint-completion.md` lines 5791-5847**, with
`content_sha256` `1647f803ac50eb03ab9d702822cc724c16b26e31f75d444ead8e0cee36d4df30`.
`validate_human_evidence` (`:864-894`) recomputes that digest from **live
bytes on every structural run** (`:892`).

Every one of r0's three spans sits above line 5791 and adds lines. r0's package
grows the goal by **+70 lines**, so after replacement lines 5791-5847 hold
different text:

| Span 5791-5847 digest | Value |
|---|---|
| canonical goal | `1647f803ac50eb03ab9d702822cc724c16b26e31f75d444ead8e0cee36d4df30` |
| r0-style +70-line candidate | `6cd04e97211f8ccf7dfd3f344424568c973cc26a42ab980eecda746dd7803d31` |

**Proved by construction, not argued.** I built a staging root containing a real
copy of the repo, put the amended goal in place, and ran the amended structural
validator against the correct `HR-0005` four-file post-state:

| Staging run | Result |
|---|---|
| control — canonical goal in the staging root | exit **0** |
| r0-style amended goal in the staging root | exit **1**, `line 892, in validate_human_evidence: assert evidence["content_sha256"] == digest` |

This is exactly the class of failure that only appears *after* canonical
replacement: every probe in r0, every probe in the independent review, and my
own probes G1/G2 passed only because they ran with `--repo-root .` pointing at
the **unamended** on-disk goal.

**Blast radius, measured.** I enumerated every line-anchored reference into the
goal across the ledger and the human-review artifact: exactly **one** —
`HR-0004/HR-EV-0004-APPROVAL-RECORD`. No ledger row has `source_path` equal to
the goal, and no other `UTF8_LINE_SPAN` targets it.

**Two remedies, and why D3 chose the first:**

| | Remedy | Cost |
|---|---|---|
| **R-A** (chosen) | Keep goal lines 1-5847 line-count-identical: spans B/C/D exactly line-neutral, all added prose appended below 5847 | Four over-long code lines (§3.4) and prose placed at the end of the goal rather than beside A6 |
| R-B (rejected) | Rebind `HR-EV-0004-APPROVAL-RECORD`'s `start_line`/`end_line` to the shifted span | Changes HR-0004's entry `content_sha256` → `HRD-0004-001.entry_authority_sha256` and `content_sha256` → **194 transitions across 144 ledger rows** that carry `human_resolution_sha256`, their chain tails and `transition_history_sha256`. Retroactively rewrites the immutable HR-0004 authority chain — precisely what the ledger exists to prevent. |

R-A is verified end-to-end (§3.8, tests N/P). Note the bonus: because the
extracted structural validator is also line-neutral (**3244 → 3244 lines**),
every existing line cite in r7, r0, r2 and the review remains valid after T1.

### 3.7 What is *not* changed

- The preimplementation program: **byte-identical**. Verified — the
  candidate-extracted preimplementation validator hashes to
  `f7a225a1f99cb85c92cde3094505a92a746552280eb45dae0253a71ab9048013`.
- The terminal program: no DISP-R-1 pin exists in it. It is never a checked-in
  script.
- The requirement's identity fields, `rejection_record`, and the S20 spec.
- The HR-0004 approval record at goal `:5791-5847`: **byte-identical**, and
  proved so by digest (§3.6, test P4).
- `extract_goal_validators.py`, `generate_initial_ledger.py`,
  `record_inventory_review.py`: unchanged.
- **143 of the 144 HR-0004-scoped ledger rows**: unchanged. Only `DISP-R-1`
  moves.

**Correction to r0.** r0 §3.5 claimed "The canonical ledger: zero rows change."
That is **false** under decision D1. `DISP-R-1`'s `human_review_id`,
`transition_history` and `transition_history_sha256` all change. r0's §3.7 T3
result ("the amendment is ledger-neutral") remains true of the *goal/validator
change in isolation* — verified again here as test G2/N2 — but it is **not** a
property of T1.

### 3.8 Mechanical verification

All probes under `scratchpad/disp-r1/` (gitignored). Canonical files were
read-only throughout; the only writes outside `scratchpad/` were to a throwaway
`/tmp/disp-r1-stage` staging root.

**Construction and hashes** (`probe_r1_neutral.py`):

| Test | Result |
|---|---|
| Each of spans B/C/D occurs **exactly once** in the goal | PASS |
| Each of spans B/C/D is exactly line-neutral (13→13, 13→13, 6→6) | PASS |
| Candidate goal lines 5791-5847 **byte-identical** to canonical | PASS |
| First/last differing line within the common prefix | 4028 / 4176 — all below 5791 |
| `extract_goal_validators.py --check` on the candidate goal | exit **0** |
| Candidate preimplementation validator = canonical bytes | PASS |
| Candidate structural validator line count = canonical (3244) | PASS |

**Post-state hashes of the two deterministic files:**

| Path | Pre-state SHA-256 | Post-state SHA-256 |
|---|---|---|
| `docs/goals/equity-os-blueprint-completion.md` | `f15f7ab5a4e425dec3877ab7f1f7594687979060e4dbcd49390a8a8d5fedb85f` | `fa527d076b4bfb6b3e627d7d8fbda799cad3117f9db6ce0d8088d256ec898304` |
| `scripts/equity_os_blueprint/validate_ledger_structural.py` | `731d0d8b208b577967c92e3992e7ec1a4333cdecbf89f6951c32d2ec469436f9` | `59053b0bb7173055a8c768907e6ddb9f1bbab8cc48f2f639ded04b9526170419` |

Both were produced by the probe from the exact `before`/`after` text in
§3.2-3.5 and the fixed pre-state. They are **not** placeholders. The ledger and
human-review post-state hashes are **not** pre-derivable — see §6.2.3.

**Validation** (`probe_r1.py`, `probe_r1_seq.py`, plus the staging runs):

| # | Test | Expected | Result |
|---|---|---|---|
| G2 / N2 | Amended structural on the **canonical** ledger + human-review pair | 0 | **0** |
| G3 | **Canonical** structural on the correct `HR-0005` four-file post-state | nonzero | **1** at `:2821` — the Critical, independently reproduced |
| G1 | Amended structural on the `HR-0005` post-state, unamended goal on disk | 0 | **0** |
| P1 | `extract_goal_validators.py --check` in the staging root, post-replacement | 0 | **0** |
| P2 | Amended structural in the staging root (**amended goal in place**) on the `HR-0005` post-state | 0 | **0** |
| P3 | Amended preimplementation in the staging root on the post-state ledger | 2 | **2**, `ready=false`, `pending_reviews`=**447**, `stale_reviews`=**0**, the DISP-R-1 unmet entry **identical to §0** |
| P4 | Goal lines 5791-5847 digest after replacement | `1647f803…` | **`1647f803…`** |

**Attacks on the new HR-0005 admission** (`probe_r1.py` part H, re-run against
the line-neutral validator). All rejected. Per **M4**, rejection lines are
construction-dependent — these are the lines *my* constructions hit, not a claim
of uniqueness:

| # | Attack | Exit | Rejected, e.g. at |
|---|---|---|---|
| H1 | `HR-0005` scoped to a different HR-0004 row | 1 | `:2820` (span D scope pin) |
| H2 | `HR-0005` scoped to `DISP-R-1` **plus** a second row | 1 | `:2820` (span D scope pin) |
| H3 | `decision_type` = `ACCEPT_RISK` instead of `RECONCILE_AUTHORITY` | 1 | `:1062` closed vocabulary |
| H4 | `HR-0005` entry with no recorded resolution | 1 | `:2077` |
| H5 | Ledger link with no appended transition object | 1 | `:2083` `assert replay == controlled_state(row)` |
| H6 | `HR-0005` entry with no ledger link | 1 | `:1209` reverse-link check |
| H7 | `transition_type` = `REFERENCE_APPEND` | 1 | `:2079` |
| H8 | Resolution actor role `IMPLEMENTER` | 1 | `:1041` competent-roles check |

**Forbidden shortcuts, re-run on the `HR-0005` post-state** (`probe_r1_seq.py`
part K). All rejected:

| # | Shortcut | Exit | Rejected, e.g. at |
|---|---|---|---|
| K1 | `status=SATISFIED` + refs, **no** current REVIEWER review | 1 | `:2767` |
| K2 | Fresh `COMPLETE` REVIEWER review on the historical ref, requirement left `UNRESOLVED` | 1 | `:2764` |
| K3 | Requirement `description` weakened to "S20 exists", then satisfied | 1 | `:2760` identity pin |
| K4 | Genuine proof, then evidence recaptured **after** the review | 1 | `:1135` `validate_inventory_review` |
| K5 | `status=SATISFIED` with **empty** `evidence_ref_ids` | 1 | `:2141` global schema |

r0's equivalent S1-S4 results and the reviewer's 14 independent attack
constructions (A5-A14, all rejected) are preserved and unaffected: none of them
touches the HR overlap set, and spans B/C are semantically identical to r0's.

Reproduce with:

```
python3 scratchpad/disp-r1/probe_deadlock.py
python3 scratchpad/disp-r1/probe_r1_neutral.py
python3 scratchpad/disp-r1/probe_r1.py
python3 scratchpad/disp-r1/probe_r1_seq.py
```

### 3.9 Why this does not weaken the protection

| Abuse | What blocks it | Enforced at |
|---|---|---|
| Prove by digest refresh alone | Refreshing an evidence object changes `evidence_refs`, which is in `review_input_projection`, so any pre-existing review's `reviewed_input_sha256` no longer matches | `:350-355` |
| Prove by historical rejection-record refs | `HISTORICAL_REFS_UNCOVERED` requires the refs on the *requirement*; the review must itself link every historical ref | predicate `:2707-2709`, `:2719` |
| Prove without a current REVIEWER-role review | `disp_r1_proven is True` in the new `else` branch is reachable only when the closed predicate returns no reasons | span C `else` branch |
| Prove by weakening the requirement's wording | Identity fields still pinned byte-for-byte | span C identity assert |
| Launder authority through a new HR entry | `HR-0005` may project only `DISP-R-1`, only alongside `HR-0004`, only under an active human `RECONCILE_AUTHORITY` resolution; no other row may ever enter `overlapping` | span D |

The structural predicate is a slightly weaker copy of the preimplementation one
— it omits `HISTORICAL_REF_STALE`, the non-empty `model`/`effort` check, and the
`review_state(...) == "COMPLETE"` digest recomputation. Each omitted conjunct is
enforced **globally** elsewhere in structural validation, which the independent
reviewer confirmed in substance:

- evidence byte-freshness for **every** evidence object: **`:233`**
  (`assert evidence["content_sha256"] == actual_digest`);
- non-empty `model`/`effort` on every `COMPLETE` review: **`:261-262`**;
- both review digests recomputed on every `COMPLETE` review: **`:350-355`**
  (r0 cited `:352-357`; corrected per M1).

### 3.10 Extractor markers — a deliberate non-change

r7 §7.3 D.1 established one required marker substring per amendment item
A1-A11. A strict reading says a new item A12 deserves a new entry in
`REQUIRED_MARKERS`.

I am **not** proposing that. `extract_goal_validators.py` is hand-maintained,
not extracted from the goal, so adding a marker widens the change to a fifth
file; the D.2 lane-token check plus the existing A6 marker already cover the
prose region, and the extractor's `--check` passes on the candidate. The
independent reviewer examined this and **agreed** (M6).

The §3.2 prose does carry the heading `## A12 amendment — DISP-R-1 closed
two-state proof rule` and the substring `has exactly two permitted proof
states`, so if a future reviewer disagrees, adding
`"A12": "has exactly two permitted proof states"` to `REQUIRED_MARKERS` is a
one-line change requiring no prose edit.

---

## 4. The `HR-0005` record, specified in full

r0 specified no `HR-0005` content at all. This section closes finding **F2**.
Every field set and every closed vocabulary below is read from the live schema
in `validate_ledger_structural.py`, and the whole shape was validated
end-to-end by probe G1/P2 (exit 0).

### 4.1 The entry — exactly the 15 `entry_fields` (`:910-915`)

| Field | Value | In-vocabulary proof |
|---|---|---|
| `human_review_id` | `"HR-0005"` | matches `HR-\d{4}` (`:924`); not already present (`:925`) — live entries are `HR-0001..HR-0004` |
| `entry_type` | `"DECISION"` | ∈ `{"DECISION", "SECURITY_EXCEPTION"}` (`:926`) |
| `scope` | exactly the 6 `scope_fields_human` keys (`:916-919`): `component_ids` = `["DISP-R-1"]`; `register_ids`, `spec_ids`, `bead_ids`, `blocked_component_ids` all `[]`; non-empty `scope_text` | each list sorted+deduplicated (`:934`); `scope_text` non-empty (`:936`); projected component set non-empty (`:832`) and ⊆ `by_id` (`:833`) |
| `question` | the §7 approval question, rewritten for the four-file scope | non-empty string (`:942`) |
| `why_human_external` | "Amending the active goal contract and its extracted structural validator is a rank-1 process decision no agent may grant." | non-empty (`:942`) |
| `recommendation` | "Approve only the exact hash-bound four-file package." | non-empty (`:942`) |
| `safe_default` | "Change no canonical byte." | non-empty (`:942`) |
| `evidence` | **two** objects — see §4.4 | `validate_human_evidence` (`:864-894`) |
| `continuable_work` | `[]` | must be a list (`:943`) |
| `decision_authority` | exactly `{approval_type, authority, competent_roles}` = `{"GOAL_OR_PROCESS_AUTHORIZATION", "Explicit rank-1 current-user authority over the active goal process", ["CURRENT_USER"]}` | key set pinned (`:945`); `approval_type` ∈ `approval_types − {DELEGATED_ARTIFACT_APPROVAL}` (`:946-948`) — `GOAL_OR_PROCESS_AUTHORIZATION` is member 1 of `approval_types` (`:836`); non-empty `competent_roles` (`:951`). Matches the HR-0004 precedent exactly. |
| `security_exception_detail` | `null` | required `null` when `entry_type == "DECISION"` (`:975`) |
| `blocking` | `true` | must be bool (`:953`) |
| `state` | `"RESOLVED"` | derived, not chosen: `"RESOLVED"` iff exactly one active resolution (`:1089-1099`) |
| `resolution_decision_ids` | `["HRD-0005-001"]` | must equal `all_by_entry[entry_id]` in order (`:1100`) |
| `content_sha256` | `canonical_sha256(entry minus content_sha256)` | `:980-983` |

Span D additionally pins `entry_type`, `decision_authority.approval_type`, and
the projected component set for `HR-0005` specifically.

### 4.2 The resolution — exactly the 15 `resolution_fields` (`:988-993`)

| Field | Value | In-vocabulary proof |
|---|---|---|
| `decision_id` | `"HRD-0005-001"` | unique (`:1008`) |
| `sequence` | **1** | must equal the index in the global list (`:1009`); `HRD-0004-001` is index 0 |
| `record_type` | `"DECISION"` | ∈ `{"DECISION", "REVOCATION"}` (`:1061`/`:1076`) |
| `decision_type` | **`"RECONCILE_AUTHORITY"`** | ∈ `decision_types` (`:1062`), whose members are `ACTIVATE_DEFERRED`, `REJECT_COMPONENT`, `REOPEN_ACCEPTED`, `RECONCILE_AUTHORITY`, `APPROVE_SECURITY_EXCEPTION`, `DENY_SECURITY_EXCEPTION`, `SATISFY_APPROVAL`, `DENY_APPROVAL`, `EXPIRE_APPROVAL` (`:994-999`). **`AMEND_VALIDATOR_PIN` is not in that set** and can never be recorded (decision D2; attack H3 confirms `ACCEPT_RISK` is rejected at `:1062`). Also required by the transition, which calls `transition_resolution(entry, row, {"RECONCILE_AUTHORITY"})` (`:2076`), and by span D. |
| `human_review_id` | `"HR-0005"` | must exist as an entry (`:1017`) |
| `scope` | **identical object** to the entry's `scope` | `:1023` |
| `actor` | exactly `{identity_id, display_name, role, actor_type}` = `{"mvpavan42@gmail.com", "Current authenticated chat user", "CURRENT_USER", "HUMAN"}` | key set pinned (`:1025`); `actor_type == "HUMAN"` (`:1026`); all three strings non-empty (`:1027`); `role` ∈ entry `competent_roles` (`:1041`). Identical in form to `HRD-0004-001`'s actor. |
| `authority_basis` | exactly `{approval_type, authority, role, evidence_ids}`, first two equal to the entry's `decision_authority`, `role` = actor role, `evidence_ids` = `["HR-EV-0005-DESIGN", "HR-EV-0005-REVIEW"]` | key set pinned (`:1031`); equality checks (`:1034-1041`); non-empty and ⊆ entry+resolution evidence (`:1046-1047`) |
| `timestamp` | the UTC instant of the user's approval | ≥ `HRD-0004-001`'s `2026-08-15T07:13:28Z` (`:1051`), ≤ validation time (`:1049`), ≥ every cited evidence `captured_at` (`:1054-1058`) |
| `evidence` | `[]` | list; the authority evidence lives on the entry |
| `supersedes_decision_id` | `null` | required `null` when no prior active decision exists on this entry (`:1064-1066`) |
| `revokes_decision_id` | `null` | required `null` for `record_type == "DECISION"` (`:1063`) |
| `entry_authority_sha256` | `canonical_sha256(entry minus {state, resolution_decision_ids, content_sha256})` | `:1019-1022` |
| `previous_resolution_sha256` | **`f263f2dabc91ad1186a813564c485b2edec5c83720624c2e7a49e6d43d3f9dc7`** — `HRD-0004-001.content_sha256`, freshly read from the canonical artifact | `:1010` |
| `content_sha256` | `canonical_sha256(resolution minus content_sha256)` | `:1011-1016` |

### 4.3 The ledger change — one appended transition on `DISP-R-1`

Exactly the 14 `transition_fields` (`:1744-1749`):

| Field | Value | In-vocabulary proof |
|---|---|---|
| `transition_id` | `"TR-DISP-R-1-004"` | non-empty, globally unique (`:1836-1838`) |
| `sequence` | **4** | must equal the index (`:1835`); the row currently holds 4 entries, `TR-DISP-R-1-000..003` |
| `transition_type` | `"AUTHORITY_RECONCILIATION"` | ∈ `transition_types` (`:1750-1753`, `:1839`); required for a `human_review_id` change carrying a resolution (`:2075-2076`). Attack H7 confirms `REFERENCE_APPEND` is rejected at `:2079`. |
| `field` | `"human_review_id"` | routed at `:2070` |
| `actor` | exactly `{actor_id, actor_type, role}`, `actor_type` ∈ `{HUMAN, AGENT, SYSTEM}` | `:1840-1846` |
| `invoked_model` | the executing agent's model string, or `null` | `:1847-1849` |
| `timestamp` | the transaction instant, ≤ validation time | `:1850` |
| `old_value` | `"HR-0004"` | current row value |
| `new_value` | `["HR-0004", "HR-0005"]` | append-only link growth `old_links < new_links` (`:2072`) and `new_links <= set(human_entries)` (`:2073`) |
| `evidence_ref_ids` | non-empty ⊆ the row's own evidence IDs — `["EV-DISP-R-1-SOURCE"]` | `:1851-1853` |
| `human_resolution_decision_id` | `"HRD-0005-001"` | resolved and required active (`:1772-1779`) |
| `human_resolution_sha256` | `HRD-0005-001.content_sha256` | `:1772-1776` |
| `previous_entry_sha256` | **`b121cf3000723f2130d934ccd548d8e07035a52371e90e0ef37f652707bdfb51`** — the current tail's `entry_sha256`, freshly read | `:1854` |
| `entry_sha256` | `canonical_sha256(entry minus entry_sha256)` | `:1855-1858` |

Then on the row: `human_review_id` → `["HR-0004", "HR-0005"]`, and
`transition_history_sha256` → `canonical_sha256([e["entry_sha256"] for e in history])`
over the **five** entries (`:2085-2087`). Current value
`27733590d3ced98b9f6943c7f31a09fa6b8312625b510efd9a91429cc166481d`.

Attack H5 confirms the transition is mandatory: linking without appending fails
at `:2083` (`assert replay == controlled_state(row)`), because `human_review_id`
is a controlled field.

### 4.4 The entry's evidence — two objects, and why not the HR-0004 precedent

HR-0004 bound its entry evidence to a `UTF8_LINE_SPAN` over the goal's **own
post-state approval-record span** (`goal:5791-5847`). **`HR-0005` must not
follow that precedent.** Doing so would require the goal to gain an
approval-record section — a fifth changed span, a self-referential digest
ordering, and (per §3.6) a guaranteed line-number shift. The independent
reviewer reached the same conclusion in F2 and I concur.

`HR-0005` binds instead to the two artifacts that actually carry the authority,
each `FILE_BYTES` over the whole file:

| `evidence_ref_id` | `path` | `digest_mode` | `content_sha256` |
|---|---|---|---|
| `HR-EV-0005-DESIGN` | `docs/goals/reviews/ledger/equity-os-blueprint-disp-r1-amendment-design-r1.md` | `FILE_BYTES` | `<DESIGN_R1_SHA256>` |
| `HR-EV-0005-REVIEW` | `docs/goals/reviews/ledger/equity-os-blueprint-disp-r1-amendment-design-r1-review-r0.md` | `FILE_BYTES` | `<REVIEW_R0_SHA256>` |

Both with `start_line`/`end_line` `null` (required for `FILE_BYTES`, `:879`),
non-empty `scope`, and `captured_at` ≤ validation time (`:878`). Both paths must
exist at execution time (`:873`) and must not be the ledger or the human-review
artifact (`:874-876`).

**These two digests are the only values in the `HR-0005` record that cannot be
computed today**, because this design document's final bytes and its review do
not exist yet. They are declared placeholders, not fabricated values.

---

## 5. Sequencing — the amendment unlocks only; evidence is recorded later

### 5.1 Decision

**Two transactions.** T1 (this amendment, including `HR-0005`) unlocks the
possibility and records **no** S20 evidence. T2 (a separate, later transaction)
records the evidence and satisfies the requirement.

### 5.2 Why not combine them

1. **The review cannot be fabricated.** The `REVIEWER`-role review of S20 must
   happen at a real point in time against real bytes, by an agent that is not
   the implementer of the artifact (`CONTEXT.md:137-139`). Goal `:447-448`: "The
   validator never fills these digests, and this draft contains no fabricated
   live review values."
2. **A combined transaction is self-referential.** `reviewed_input_sha256`
   covers `required_evidence` (§2.4), so the review must be sealed against a
   post-state row that does not exist until the transaction produces it.
3. **T2's inputs do not exist yet.** T2 must run after the 447-review recorder
   (§8), whose output bytes are not yet written.
4. **T1 moves the preimplementation gate by zero rows** (test P3), which makes it
   far easier to approve, rehearse, verify, and roll back.

### 5.3 What must exist BEFORE T1 can run

1. This design document, at its final bytes.
2. An independent `REVIEWER`-role review at the predetermined path
   `…-disp-r1-amendment-design-r1-review-r0.md`, verdict `CLEAN`, whose recorded
   reviewed-input SHA-256 equals this document's SHA-256, with its actual
   invoked model and effort recorded, under the `CONTEXT.md` "Agent roles"
   binding. Per project policy the reviewer must be a different agent and
   context from this Implementer.
3. **The drafted `HR-0005` entry, the `HRD-0005-001` resolution, and the
   `TR-DISP-R-1-004` transition object at their exact final bytes** — added per
   finding F4, because the user's approval must bind them.
4. Explicit user approval of the §7 question, with all placeholders resolved.
5. Canonical pre-state hashes still equal to §0.

Notably **absent**: no S20 review, no evidence capture, no recorder output.

### 5.4 What must exist BEFORE T2 can run

1. T1 landed and verified.
2. The 447-review recorder workstream complete (§8), so T2's re-sealing is not
   subsequently overwritten.
3. A real, independent `REVIEWER`-role review of
   `docs/specs/equity-os-s20-memory-benchmark-gbrain.md` at its then-current
   bytes, reaching `CLEAN` on the question in §2.3, at a real timestamp no
   earlier than `EV-DISP-R-1-SPEC-DRAFT.captured_at`.
4. Its own design, review, and user approval. **T2 is out of scope for this
   document.**

---

## 6. Transaction design for T1 (at the HR-0004 r7 bar)

T1 reuses r7's proven machinery **by reference**: §6.2 transaction boundary and
rollback, §6.3 candidate-validation root with overlay teardown and fail-closed
exit 2, §8.2 candidate command shapes. r7's 144-ID structured scope and its
reconciliation-mode baseline comparison are **not** reused.

### 6.1 Pre-state hashes — all bound

Every hash in §0 is a precondition. T1 aborts without any write if any differs.

### 6.2 Exact scope — four files, nothing else

#### 6.2.1 The two deterministic files

| Path | Change | Pre-state SHA-256 | Post-state SHA-256 |
|---|---|---|---|
| `docs/goals/equity-os-blueprint-completion.md` | 3 exact line-neutral span replacements + 1 appended prose section (§3.2-3.5) | `f15f7ab5a4e425dec3877ab7f1f7594687979060e4dbcd49390a8a8d5fedb85f` | `fa527d076b4bfb6b3e627d7d8fbda799cad3117f9db6ce0d8088d256ec898304` |
| `scripts/equity_os_blueprint/validate_ledger_structural.py` | regenerated by the extractor | `731d0d8b208b577967c92e3992e7ec1a4333cdecbf89f6951c32d2ec469436f9` | `59053b0bb7173055a8c768907e6ddb9f1bbab8cc48f2f639ded04b9526170419` |

Both post-state hashes are freshly computed by probe, reproducible by running
`probe_r1_neutral.py`.

#### 6.2.2 The two record files

| Path | Change | Pre-state SHA-256 | Post-state SHA-256 |
|---|---|---|---|
| `docs/goals/equity-os-blueprint-human-review-needed.md` | append `HR-0005` entry (§4.1) + `HRD-0005-001` resolution (§4.2) to the canonical JSON payload | `094fcdfab74a3f4c6fdb82b1520fc4d13b636ac0e9ed10194e5d607aed2ce9af` | `<HUMAN_REVIEW_POST_SHA256>` |
| `docs/goals/equity-os-blueprint-component-ledger.jsonl` | `DISP-R-1` only: append `TR-DISP-R-1-004`, set `human_review_id`, recompute `transition_history_sha256` (§4.3) | `de236d7e8dcf02e307ec58797f5722ae2f85d1d8cdba57d4ecc07df5383c9c97` | `<LEDGER_POST_SHA256>` |

#### 6.2.3 Why those two post-state hashes cannot be pre-derived — stated plainly

They are deterministic functions of the construction in §4 and of **four free
inputs that do not exist yet**:

1. `<DESIGN_R1_SHA256>` — this document's final bytes;
2. `<REVIEW_R0_SHA256>` — the predetermined independent review's final bytes;
3. the entry-evidence `captured_at` instants;
4. the `HRD-0005-001` / `TR-DISP-R-1-004` timestamps, which are the instant of
   the user's approval and therefore necessarily **after** the question is asked.

Input 4 is not removable: HR-0004 had the same structure. **I will not fabricate
these hashes.** The rehearsal (§6.3) computes them from the fully specified
construction and records them in the journal *before* any canonical write, and
the executor must match them exactly.

For calibration, a probe run with stand-in values for inputs 1-4 produced
ledger `b337e4e2df8bca48250b74d472a9ed46e4059c36a8c3fa8e7b04f7a5a0fd1fcb` and
human-review `9ad3aa457d5a4c0729956fe7a1c9814425b9b1da1fe6a50def228dbd84f969a5`.
**These are probe artifacts under stand-in inputs. They are not the post-state
and must never be used as such.**

#### 6.2.4 Explicitly forbidden

`validate_ledger_preimplementation.py` (must stay
`f7a225a1f99cb85c92cde3094505a92a746552280eb45dae0253a71ab9048013`),
`extract_goal_validators.py`, `generate_initial_ledger.py`,
`record_inventory_review.py`, `CONTEXT.md`, any spec, any blueprint file, any
other ledger row, any Beads record, any Git commit or push.

### 6.3 Mandatory rehearsal

Before any canonical write, in a staging root outside the canonical tree
(r7 §6.3 pattern), with the overlay torn down afterwards. **Rewritten per
finding F4 to cover all four files, and per §3.6 to validate against the
amended goal in place.**

1. Copy the canonical goal to `<staging>/candidate-goal.md`.
2. Apply the three span replacements, asserting **exactly one** occurrence of
   each `before` span and **exactly equal line counts** before and after. Any
   count other than 1, or any line-count change, aborts.
3. Append the §3.2 prose block, preceded by exactly one blank line.
4. Assert the candidate goal's lines 5791-5847 are **byte-identical** to the
   canonical goal's, and that their span digest is
   `1647f803ac50eb03ab9d702822cc724c16b26e31f75d444ead8e0cee36d4df30`.
5. `sha256sum <staging>/candidate-goal.md` must equal
   `fa527d076b4bfb6b3e627d7d8fbda799cad3117f9db6ce0d8088d256ec898304`.
6. Extract all three programs from the candidate goal to staging paths.
   `sha256sum <staging>/candidate-validate-structural.py` must equal
   `59053b0bb7173055a8c768907e6ddb9f1bbab8cc48f2f639ded04b9526170419`, and the
   candidate preimplementation validator must equal
   `f7a225a1f99cb85c92cde3094505a92a746552280eb45dae0253a71ab9048013`.
7. Build `<staging>/candidate-human-review.md` and `<staging>/candidate-ledger.jsonl`
   per §4, using the now-known values of the four free inputs. Record both
   resulting hashes in the journal as `<HUMAN_REVIEW_POST_SHA256>` and
   `<LEDGER_POST_SHA256>`.
8. **Build a staging repo root** containing a real copy of the repository with
   the candidate goal and candidate structural validator in their canonical
   paths — not symlinks, because `repo_path` asserts `is_relative_to(root)`
   after `resolve()`.
9. Run the §6.4 proof commands against that staging root.
10. Tear down the staging root. Any failure aborts with **zero** canonical
    writes.

### 6.4 Candidate proof commands and expected exit codes

Paths abbreviated. `<root>` is the §6.3 step 8 staging root.

| # | Command | Expected |
|---|---|---|
| P1 | `extract_goal_validators.py --check --goal-path <cand-goal> --structural-output <cand-struct> --preimplementation-output <cand-pre>` | **0**. **Per M2: this is only meaningful *after* §6.3 step 6 has written those outputs.** Run with explicit `--*-output` paths that do not yet exist, `--check` exits 1 with `stale generated validators`; it is not an independent gate. |
| P2 | `<cand-struct> --repo-root <root> --ledger-path <cand-ledger> --human-review-path <cand-human>` | **0** |
| P3 | `<cand-pre> --repo-root <root> --ledger-path <cand-ledger> --report-blockers` | **2**, `ready=false`, DISP-R-1 blocker with all three reason codes, `pending_reviews`=447, `stale_reviews`=0 |
| P4 | Recompute the goal `5791-5847` span digest in `<root>` | `1647f803ac50eb03ab9d702822cc724c16b26e31f75d444ead8e0cee36d4df30` |
| P5 | `<cand-struct> --repo-root <root>` against the §3.8 H1-H8 and K1-K5 candidates | **nonzero for each** |
| P6 | `<cand-struct> --repo-root <root>` against the §8.2 J2 union candidate | **0** |

P2 and P3 run against the **candidate** ledger and human-review artifact as a
required pair (`:26` asserts `(--ledger-path is None) == (--human-review-path is
None)`). P3 asserting **unchanged** blocker output is the gate-neutrality proof:
T1 must not move the preimplementation gate by one row. All six were executed in
this design as tests P1-P4, H*, K*, and J2.

### 6.5 Journaled atomic replacement and rollback

Follow r7 §6.2. **Four files must move together or none.** The ledger and
human-review artifact are mutually referential through `human_review_links`; the
goal and validator through `--check`.

1. Record a journal entry naming all four paths, all four pre-state hashes, and
   all four intended post-state hashes (two pinned in §6.2.1, two computed at
   §6.3 step 7).
2. Re-verify all four live pre-state hashes immediately before writing. Any
   drift aborts.
3. Write all four files via write-to-temp-then-atomic-rename **within the same
   journaled step**.
4. Verify all four post-state hashes.
5. On **any** failure at any step — including a partial write — restore all four
   files from the journaled preimages and re-verify all four pre-state hashes.
   Preimages are retained until every postcondition in §6.6 passes.

There is no valid intermediate state.

### 6.6 Postconditions

All must hold, or roll back. **Rewritten per F1.5 and F4** — r0's postconditions
1, 2, 3, 6, 7 and 9 were all false under decision D1.

1. Goal SHA-256 = `fa527d076b4bfb6b3e627d7d8fbda799cad3117f9db6ce0d8088d256ec898304`.
2. Structural validator SHA-256 = `59053b0bb7173055a8c768907e6ddb9f1bbab8cc48f2f639ded04b9526170419`.
3. Ledger SHA-256 = the journaled `<LEDGER_POST_SHA256>`; human-review artifact
   SHA-256 = the journaled `<HUMAN_REVIEW_POST_SHA256>`.
4. Preimplementation validator, extractor, `CONTEXT.md`, and the S20 spec
   **byte-unchanged** at their §0 hashes.
5. Goal lines 5791-5847 digest = `1647f803ac50eb03ab9d702822cc724c16b26e31f75d444ead8e0cee36d4df30`,
   and goal line 5847 is still the last line of the HR-0004 approval record.
6. `extract_goal_validators.py --check` → exit **0** (no arguments; canonical).
7. `validate_ledger_structural.py --repo-root .` → exit **0**.
8. `validate_ledger_preimplementation.py --repo-root . --report-blockers` →
   exit **2**, `ready=false`, `pending_reviews`=447, `stale_reviews`=0, and the
   DISP-R-1 unmet entry **identical** to §0's.
9. **Exactly one** ledger row changed (`DISP-R-1`), and on it exactly three
   fields: `human_review_id`, `transition_history`, `transition_history_sha256`.
   A byte diff of the other 209 rows shows no change.
10. Live transition-object count = **649** (648 + 1). The pinned baseline
    *prefix* invariant is untouched: `sum(BASELINE_PREFIX_LENGTHS.values())` is
    still 454 and `DISP-R-1`'s prefix length is still 2 (its history grows
    4 → 5, which is a suffix append). **Per M5, 454 is a prefix sum, not the
    live object count.**
11. `human_entries` = `{HR-0001, HR-0002, HR-0003, HR-0004, HR-0005}`;
    `human_payload["resolutions"]` has length 2; `HR-0005.state == "RESOLVED"`.
12. No delivery state, gate state, activation, requirement status, or inventory
    review changed. `REQ-DISP-R-1-NO-IMPLEMENTATION` is still `UNRESOLVED` with
    empty `evidence_ref_ids`; all 447 reviews are still `PENDING`.
13. `git status` shows exactly the four authorized modified paths, plus whatever
    was already dirty when the transaction starts. **Per M3, the pre-existing
    set as measured at the end of this design work is:** `.beads/issues.jsonl`
    (modified); and untracked —
    `scripts/equity_os_blueprint/record_inventory_review.py`,
    `docs/goals/reviews/ledger/inventory/`,
    `docs/goals/reviews/ledger/equity-os-blueprint-disp-r1-amendment-design-r0.md`,
    **this document**, and the predetermined review artifact once written. All
    are owned by the 447-review workstream or by this design, and none is
    touched by T1. The executor must re-measure this set immediately before
    step 1 of §6.5 and journal it, because the 447-review workstream is
    actively adding files under `docs/goals/reviews/ledger/inventory/`.
14. The staging root is removed; no temporary candidate file survives.
15. No Beads mutation, no commit, no push.

### 6.7 A note on `--reconciliation-check` mode

`--reconciliation-check` was the one-shot HR-0004-transaction check. It pins its
baseline artifacts by hash at `:2923` and `:2926` to
`51091042dae87d2f41fbbf02d77ab1619c6a1008a022baec4233c44a0e295e13` and
`54c1e183def8e0b1b91504effbf20c233b3d1352fd65d4910e89c2b913ee5702` — the
**pre-HR-0004** ledger and human-review artifact, which HR-0004 itself replaced.
Those bytes no longer exist anywhere in the working tree or in Git history.

I verified this by running the mode today against the current canonical
artifacts: it aborts at `:2923`, the baseline-ledger hash assertion, before
reaching any other check.

Consequence: the mode's `assert set(human_entries) == set(baseline_entries) |
{"HR-0004"}` at `:3034` and `assert len(human_payload["resolutions"]) == 1` at
`:3035` would both be false after T1, **but they are already unreachable**. T1
introduces no new breakage there, and no fifth amendment span is needed. This is
recorded so the next reader does not rediscover it as a blocker.

---

## 7. The user approval question

The user has approved **designing** this amendment and **adding `HR-0005`**.
They have **not** approved executing it. This question must be asked and
answered affirmatively before any canonical byte changes.

**Placeholders — and only these — remain unresolved.** Every other value below
is freshly computed and concrete:

- `<DISP_R1_DESIGN_SHA256>` — this document's SHA-256, computable only once its
  bytes are final.
- `<DISP_R1_REVIEW_SHA256>` — the SHA-256 of the predetermined independent
  review at `…-disp-r1-amendment-design-r1-review-r0.md`, which does not exist
  yet.
- `<LEDGER_POST_SHA256>` and `<HUMAN_REVIEW_POST_SHA256>` — resolved by the
  §6.3 step 7 rehearsal and journaled before any write, for the reason given in
  §6.2.3. These two files exist, but their post-state bytes depend on the
  approval timestamp, which does not exist until this question is answered.

> Do you approve one `RECONCILE_AUTHORITY` goal-contract amendment transaction, recorded as human-review entry `HR-0005` with resolution `HRD-0005-001`, bound to independently reviewed `docs/goals/reviews/ledger/equity-os-blueprint-disp-r1-amendment-design-r1.md` SHA-256 `<DISP_R1_DESIGN_SHA256>` and predetermined independent review `docs/goals/reviews/ledger/equity-os-blueprint-disp-r1-amendment-design-r1-review-r0.md` SHA-256 `<DISP_R1_REVIEW_SHA256>`, whose explicit verdict is `CLEAN`, whose explicit reviewed-input SHA-256 is `<DISP_R1_DESIGN_SHA256>` equal to that design SHA-256, and whose reviewer role is `REVIEWER` under the `CONTEXT.md` "Agent roles" binding with its actual invoked model and effort recorded in the review; active-goal pre-state SHA-256 `f15f7ab5a4e425dec3877ab7f1f7594687979060e4dbcd49390a8a8d5fedb85f`, structural-validator pre-state SHA-256 `731d0d8b208b577967c92e3992e7ec1a4333cdecbf89f6951c32d2ec469436f9`, ledger pre-state SHA-256 `de236d7e8dcf02e307ec58797f5722ae2f85d1d8cdba57d4ecc07df5383c9c97`, human-review pre-state SHA-256 `094fcdfab74a3f4c6fdb82b1520fc4d13b636ac0e9ed10194e5d607aed2ce9af`, preimplementation-validator pre-state SHA-256 `f7a225a1f99cb85c92cde3094505a92a746552280eb45dae0253a71ab9048013`, extractor pre-state SHA-256 `5d20d796666d1154fb3c84ba4fa7407ee82819510a5ac06254f7f4a3126c6f2a`, and role-binding `CONTEXT.md` SHA-256 `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce`, authorizing only one atomic change to exactly four files — the active goal to post-state SHA-256 `fa527d076b4bfb6b3e627d7d8fbda799cad3117f9db6ce0d8088d256ec898304`, its extracted `scripts/equity_os_blueprint/validate_ledger_structural.py` to post-state SHA-256 `59053b0bb7173055a8c768907e6ddb9f1bbab8cc48f2f639ded04b9526170419`, `docs/goals/equity-os-blueprint-human-review-needed.md` to rehearsal-journaled post-state SHA-256 `<HUMAN_REVIEW_POST_SHA256>`, and `docs/goals/equity-os-blueprint-component-ledger.jsonl` to rehearsal-journaled post-state SHA-256 `<LEDGER_POST_SHA256>` — that replaces the permanently pinned `EXPECTED_DISP_R1_REQUIREMENT` whole-object literal and its unconditional `assert disp_r1_proven is False` with a pinned requirement-identity object plus a closed two-state rule under which `REQ-DISP-R-1-NO-IMPLEMENTATION` is either `UNRESOLVED` with the existing false-proof reason codes exactly as today, or `SATISFIED` only when its evidence refs cover every historical rejection-record ref and the closed current no-implementation-proof predicate is independently true with no reason codes; relaxes the pinned 23-row `overlapping` human-review-link assertion by exactly one admissible member, `DISP-R-1`, and only while a conforming `HR-0005` exists that projects no other component, links `DISP-R-1` only alongside `HR-0004`, and carries exactly one active `RECONCILE_AUTHORITY` resolution by a human actor under `GOAL_OR_PROCESS_AUTHORIZATION`, leaving the assertion byte-equivalent to today whenever `HR-0005` is absent; keeps the requirement's `description`, `scope`, `evidence_id`, `evidence_type`, `proof_mode`, and `approval_ids` pinned byte-for-byte so no weakened wording can be substituted; preserves the rule that a digest refresh alone, the historical `rejection_record` refs alone, or any state lacking a current content-bound `COMPLETE`/`CLEAN` `REVIEWER`-role evidence review can never establish proof; preserves goal lines 1-5847 line-for-line so that the `HR-0004` approval-record evidence span `5791-5847` keeps digest `1647f803ac50eb03ab9d702822cc724c16b26e31f75d444ead8e0cee36d4df30`, appending all new goal prose below line 5847; changes exactly one ledger row, `DISP-R-1`, and on it exactly three fields — `human_review_id` from `"HR-0004"` to `["HR-0004","HR-0005"]`, one appended `AUTHORITY_RECONCILIATION` transition object `TR-DISP-R-1-004` at sequence 4, and the recomputed `transition_history_sha256` — leaving the other 209 rows, every requirement status, every approval record, and all 447 `PENDING` inventory reviews byte-unchanged; records no S20 evidence, performs no S20 review, and satisfies no requirement, leaving `REQ-DISP-R-1-NO-IMPLEMENTATION` `UNRESOLVED` with empty evidence refs and the preimplementation gate `ready=false` with all 447 pending reviews, 0 stale reviews, and the identical `DISP-R-1` blocker with its three unchanged reason codes; changes no preimplementation-validator byte, no extractor byte, no `CONTEXT.md` byte, no spec, and no blueprint byte; preserves the pinned 454-entry baseline transition **prefix** manifest unchanged while the live transition-object count grows from 648 to 649 by that single append; creates no Beads or Git mutation; and aborts without canonical change on any design hash, review path/hash/verdict/reviewed-input/role binding, pre-state hash, goal line-span digest, rehearsal, extraction, validation, postcondition, or replacement failure?

Recommendation: approve only that exact package, and only after the §8.3
ordering rule is agreed with the 447-review workstream. Safe default: change no
canonical byte; `DISP-R-1` remains permanently unprovable and goal SUCCESS
remains unreachable.

---

## 8. Interaction with the 447-review recording workstream

### 8.1 The conflict is a direct contradiction on a single field

`…-inventory-review-recording-design-r2.md` §3.6, verbatim:

> `DISP-R-1`'s `EVIDENCE` review must **not** link `EV-DISP-R-1-SPEC-DRAFT`.
> `current_no_implementation_proof` computes `review_ok` partly as
> `set(historical) <= set(review["evidence_ref_ids"])` (`:2705-2718`). Linking
> the historical ref alongside a `COMPLETE`, CLEAN, digest-current review would
> set `review_ok = True`, removing
> `CURRENT_REVIEWER_ROLE_EVIDENCE_REVIEW_MISSING` from the reason codes and
> failing the `:2761-2763` assertion.
>
> […] The recorder therefore hard-codes: `DISP-R-1` `EVIDENCE` review links
> **only** `EV-DISP-R-1-INVREV-EVIDENCE`, and the recorder never touches
> `required_evidence` on any row.

r2 §3.6 is correct about the current validator. But the no-implementation proof
requires the review to link **every** historical ref — precisely the ref r2
forbids. There is exactly **one** `evidence_inventory_review` slot on the row.
The independent reviewer confirmed this reading verbatim against r2 `:453-484`.

### 8.2 Proved, not argued — on top of the `HR-0005` post-state

Probe `scratchpad/disp-r1/probe_r1_seq.py`, run against the line-neutral amended
structural validator with the `HR-0005` package as the base ledger:

| # | Scenario | Result |
|---|---|---|
| **J1** | Recorder post-state **after T1**, requirement untouched | exit **0** — T1 does not disturb the recorder |
| **J2** | T2 on top: requirement `SATISFIED`, `EVIDENCE` review links the **union** `{EV-DISP-R-1-INVREV-EVIDENCE, EV-DISP-R-1-SPEC-DRAFT}`, all three reviews re-sealed last | exit **0**; preimplementation `pending=444`, `stale=0`, `unmet=0` |
| **J3** | T2 with the `EVIDENCE` review still omitting the spec ref (r2 §3.6 carve-out kept) | exit **1** at `:2767` — the conflict is real |
| **J4** | Recorder re-runs **after** T2 and drops the union | exit **1** at `:2767` |
| **J5** | **T1 lands after the recorder**, DISP-R-1's three reviews not re-sealed | exit **1** at `:1135` `validate_inventory_review` |

J2 confirms r0's I4 result and the reviewer's independent I4: the union works
because the predicate's test is a subset test (`set(historical) <= set(review_refs)`),
so the recorder's own evidence object can coexist with the historical spec ref.

J5 is new in r1 and is the mechanical proof of finding **F3**.

r0's I5 blast-radius result stands: because `review_input_projection` is
per-row, changing `DISP-R-1` invalidates only `DISP-R-1`'s own three reviews.
The other 446 reviews are untouched.

### 8.3 The ordering rule

> **T1 (this amendment, including `HR-0005`) must land BEFORE the 447-review
> recorder runs. The recorder then runs, keeping its r2 §3.6 carve-out exactly
> as written. T2 (the `DISP-R-1` evidence proof) runs strictly last, and must
> re-seal all three of `DISP-R-1`'s reviews, with the `EVIDENCE` review linking
> the union of the recorder's evidence object and `EV-DISP-R-1-SPEC-DRAFT`.**

**This corrects r0 §7.3's "T1 may land at any time", which is false under
decision D1.** T1 mutates `DISP-R-1`'s `human_review_id` and
`transition_history_sha256`; both are inside `review_input_projection` (`:280`,
`:282`) and `human_review_id` is also inside the `APPROVAL` inventory projection
(`:316`). J5 proves the consequence: if the recorder seals `DISP-R-1`'s three
reviews first and T1 lands afterwards, all three go stale and structural
validation fails.

**Robustness to a recorder that has already partly run.** The recorder is built
and CLEAN-reviewed, and batch 1 may already have executed by the time T1 lands.
The rule is therefore stated in terms of `DISP-R-1`, not of the workstream as a
whole:

> **`DISP-R-1`'s three inventory reviews must be sealed strictly after T1.** If
> the recorder has already sealed any of them when T1 becomes ready, then either
> (i) re-run the recorder over `DISP-R-1` alone after T1, re-sealing all three
> against the post-T1 row, or (ii) revert `DISP-R-1`'s three reviews to
> `PENDING` before T1 and let a later recorder batch seal them.
> **Any other row the recorder has already sealed is unaffected** — I5 confirms
> the blast radius of a `DISP-R-1` change is confined to `DISP-R-1`.

Why each part of the chain:

- **T1 before the recorder (for `DISP-R-1`):** J5. Mandatory.
- **Recorder before T2, never after:** if the recorder ran after T2 it would
  overwrite `DISP-R-1`'s `EVIDENCE` review with the INVREV-only form, producing
  exactly J4 — a ledger that fails structural validation. Mandatory.
- **T2 last, re-sealing all three:** satisfying the requirement stales
  `DISP-R-1`'s `APPROVAL` and `SCOPE` reviews too. T2 must recompute all three
  and write them **after** every other field change to the row, including
  `transition_history_sha256` if it appends a transition (both
  `required_evidence` and `transition_history_sha256` are inside
  `review_input_projection`).
- **Second, independent reason for T2 last:** the recorder's own postcondition
  at `record_inventory_review.py:1070` asserts
  `len(report['unmet_no_implementation_proof']) == 1`. T2 clears that blocker;
  the recorder running later would fail its own postcondition. T1 leaves the
  blocker exactly as-is (P3), so T1 does **not** invalidate it.

Consider encoding this chain as blocking Beads dependencies.

### 8.4 Required follow-up on r2

r2 §3.6's factual claims about `validate_ledger_structural.py:2674-2686` and
`:2756-2763` become **stale** the moment T1 lands: the literal is renamed and
the assert becomes two-sided. Its operational instruction to the recorder stays
correct — the recorder never touches `required_evidence`, so under the amendment
`DISP-R-1` stays in the `UNRESOLVED` branch and linking only the INVREV evidence
remains right behaviour. But the *rationale* changes from "this is permanently
forbidden" to "this is forbidden unless the requirement is satisfied in the same
transaction". r2 also needs the §8.3 ordering note.

r2 is a design document, not a canonical artifact, so this is not a validator
failure. It needs an erratum note. That edit is out of scope here and belongs to
whoever owns r2.

Because the amendment is line-neutral in the extracted validator (3244 → 3244
lines), every **line number** cited by r7, r2, r0 and the r0 review remains
correct after T1. Only the *content* at `:2674-2686`, `:2756-2768` and
`:2817-2822` changes.

---

## 9. Risks and open questions

### 9.1 Risks

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | `DISP-R-1`'s reviews are sealed by the recorder before T1, or the recorder re-runs after T2 | **High** | §8.3, including the already-partly-run case. Encode as blocking Beads dependencies. |
| R2 | T2 is treated as a formality once T1 lands, and the S20 review is rushed or self-reviewed | **High** | T1 records no evidence and moves the gate by zero rows (P3). The REVIEWER must be a different agent and context per `CONTEXT.md:137-139`. T2 needs its own design, review, and approval. |
| R3 | A future goal amendment forgets the line-neutrality rule and silently breaks `HR-EV-0004-APPROVAL-RECORD` | **High** | §3.2's appended prose states the rule inside the goal itself; §6.6 postcondition 5 checks it. **A durable fix — rebinding that evidence to `FILE_BYTES` or an anchor-resolved span — is out of scope here and should be its own transaction.** |
| R4 | The `else` branch is reachable with an S20 that *does* contain an implementation claim | Medium | The validator can only check structure; the substantive judgment is the REVIEWER's. Inherent to any content review, and why `description` stays pinned. |
| R5 | Post-state hashes drift if the goal changes before T1 runs | Medium | All four pre-state hashes are bound preconditions; T1 aborts on any drift and the design is re-derived. |
| R6 | The four over-long lines in span C diverge from the program's 79-column style | Low | Stated openly in §3.4; no mechanical check enforces it; the alternative is remedy R-B's 194-transition rewrite. |
| R7 | The extractor's D.1 marker set is not extended | Low | §3.10; reviewer concurred (M6); exact one-line change given if a future reviewer disagrees. |
| R8 | `<LEDGER_POST_SHA256>` / `<HUMAN_REVIEW_POST_SHA256>` are treated as optional | Medium | §6.3 step 7 journals them before any write; §6.6 postcondition 3 checks them; §6.5 rolls back on mismatch. |

### 9.2 Open questions I could not settle

1. **Was the top-level placement of the original pin a mistake or
   belt-and-braces?** Established that it exceeds r7 §8.1's scoping (§1.5), but
   not the author's intent. *What would settle it:* the r7 executor handoff
   notes (r7 §10) or `equity-os-blueprint-hr-0004-recording-r0.md`. **It does not
   change the amendment** — the remedy is the same either way.

2. **`APR-DISP-R-1-01` requires an authority that current policy prohibits.**
   The row carries `"required_authority": "Delegated fresh Sol xhigh
   specification reviewer"`, and the S20 spec header (`:3`) reads
   "**Status: DRAFT — AWAITING FRESH SOL XHIGH REVIEW**". Standing project
   policy prohibits gpt-5.6 lanes. Two things verified, and independently
   confirmed by the reviewer (item 8):
   - This is **not** an r7 §3.8 violation. §3.8 (`:688-712`) scoped its
     role-vocabulary replacement to "the validator-checked review schema and
     reason codes"; `required_authority` is outside that scope.
   - It does **not** gate SUCCESS. The terminal validator's
     `required_approvals`-satisfied assertions are scoped to `active` rows; the
     `rejected` loop requires only `proven`, a non-null `rejection_record`,
     empty `implementation_refs`, and a non-advanced `delivery_status`.
     `DISP-R-1` is rejected, not active.

   It blocks nothing today. *What would settle it:* a user decision on whether
   these two strings should be reworded to the role vocabulary. **Out of scope.**

3. **Should T2 append a transition-history entry?** The 454-entry prefix
   invariant is a *prefix* check (`:2902-2907`), so appending is permitted. Whether
   a `required_evidence` status change is a controlled transition requiring an
   entry is a question for T2's design. Note only the ordering constraint it
   creates (§8.3): `transition_history_sha256` is inside
   `review_input_projection`, so any appended transition must be written
   **before** the reviews are sealed.

4. **Should `HR-EV-0004-APPROVAL-RECORD` be rebound away from a raw line span?**
   §3.6 shows the current binding makes every future goal amendment
   line-fragile, and remedy R-A is a discipline, not a guarantee. Rebinding it
   is a separate transaction with its own blast radius (it changes HR-0004's
   entry digest and 194 transitions). **Flagged, not attempted.** This is the
   most consequential item I am leaving open.

5. **~~Does anything outside these validators depend on
   `EXPECTED_DISP_R1_REQUIREMENT` by name?~~ RESOLVED — no.** A repo-wide grep
   returns hits only in the goal (`:4028`, `:4110`), the generated structural
   validator (`:2674`, `:2756`), and inventory-review design/review documents
   (prose citations). `record_inventory_review.py` contains **zero** occurrences
   of `EXPECTED_DISP_R1_REQUIREMENT` or `disp_r1_proven`, confirmed by read-only
   grep. The recorder hard-codes its own r2 §3.6 carve-out (`:583`, `:664`,
   `:670`) rather than importing the validator literal, so J1 models it
   correctly. The rename in §3.3 breaks no code.

---

## 10. Disposition of every finding in the r0 review

Review: `scratchpad/disp-r1/review/design-r0-findings.md`, verdict
BLOCKED — 1 Critical, 3 Important, 6 Minor.

| Finding | Disposition | Where |
|---|---|---|
| **F1** Critical — fourth pinned assertion at `:2821-2822` blocks option (b); §5.2, §5.4, §5.6, §6, §7.3 all false | **Accepted and fixed.** Reproduced independently by construction (test G3, exit 1 at `:2821`). Span D added (§3.5); scope is four files (§6.2); rehearsal, proof commands and all 15 postconditions rewritten (§6.3-6.6); §7 question reissued; ordering rule corrected (§8.3). | §3.5, §6, §7, §8.3 |
| **F2** Important — no `HR-0005` content specified | **Accepted and fixed.** Complete field-by-field spec with in-vocabulary proof for every value, including D2 (`decision_type` must be `RECONCILE_AUTHORITY`; `AMEND_VALIDATOR_PIN` is not in the closed set). Adopted the reviewer's recommendation to bind entry evidence to the design + review rather than to a goal line span. | §4 |
| **F3** Important — "T1 may land at any time" no longer holds | **Accepted and fixed**, and now proved mechanically by J5 rather than argued. Rule restated as a strict chain, and made robust to a recorder that has already partly run. | §8.3, §8.2 |
| **F4** Important — §4.3/§5.3/§5.4/§5.5 do not cover option (b)'s artifacts | **Accepted and fixed.** §5.3 gains the drafted `HR-0005` artifacts as a precondition; the rehearsal builds and binds all four files and validates the ledger/human-review **pair**; P2/P3 run against candidates; journaled replacement covers four files atomically. | §5.3, §6.3, §6.4, §6.5 |
| **M1** line-cite drift (`:352-357`→`:350-355`, `:341-348`→`:340-349`, goal `:461`→`:460`) | **Accepted, corrected everywhere.** | §1.1, §2.4, §3.9 |
| **M2** P1 not runnable in isolation | **Accepted.** P1 now states explicitly that it is meaningful only after the extraction step, and what it does otherwise. Reproduced: the probe's first `--check` pass exited 1 with `stale generated validators`. | §6.4 |
| **M3** git enumeration incomplete | **Accepted.** Postcondition 13 now enumerates all five pre-existing dirty paths. | §6.6 |
| **M4** rejection lines are construction-dependent | **Accepted.** All attack tables now read "Rejected, e.g. at". | §3.8 |
| **M5** "454 transition objects" is imprecise | **Accepted.** 454 is the pinned **prefix** sum; the live count is **648**, freshly measured, going to 649. Both stated in §0 and postcondition 10, and the §7 question now says so explicitly. | §0, §6.6, §7 |
| **M6** extractor-marker judgment call — reviewer agreed, no finding | **Recorded.** Decision unchanged, with the exact one-line alternative given. | §3.10 |

**Preserved from r0 because the review verified it as correct:** the four
forbidden shortcuts still fail at named lines (re-verified as K1-K4 on the
`HR-0005` post-state); the three "missing" conjuncts are enforced globally at
`:233`, `:261-262`, `:350-357`→`:350-355`; S20 can honestly support the proof
(the reviewer read all 268 lines and confirmed every cite); and the T2
union-of-refs resolution of the r2 §3.6 conflict (re-verified as J2).

**Findings this design adds beyond the review:**

| # | Finding | Severity |
|---|---|---|
| **N1** | `HR-EV-0004-APPROVAL-RECORD` is a `UTF8_LINE_SPAN` over goal lines 5791-5847, re-verified against live bytes on every run. Any goal amendment above line 5791 that changes line counts breaks it. r0's three-span package (+70 lines) fails at `:892` once the amended goal is on disk — invisible to every probe that validated against the unamended goal. Remedied by D3/R-A and proved by staging-root tests. | **Critical** |
| **N2** | `--reconciliation-check` mode is already unrunnable: its baseline hashes pin the pre-HR-0004 artifacts, which no longer exist. It aborts at `:2923` today, so `HR-0005` introduces no new breakage at `:3034`/`:3035` and no fifth span is needed. | Informational |

---

## 11. Probe inventory

All under `scratchpad/disp-r1/` (gitignored). None is a proposed post-state.

| File | Purpose |
|---|---|
| `probe_deadlock.py` | Reproduces both horns (§1.3) — carried from r0 |
| `probe_amendment.py`, `probe_interaction.py` | r0's three-span amendment and recorder-interaction probes; `probe_r1_seq.py` reuses the latter's projection helpers |
| `probe_r1.py` | Four-span amendment (non-neutral form), the `HR-0005` package, tests G1-G4 and attacks H1-H8 |
| `probe_r1_neutral.py` | **The definitive line-neutral amendment** (§3.2-3.5); produces the two pinned post-state hashes |
| `probe_r1_seq.py` | T1 → recorder → T2 chain (J1-J5) and shortcuts K1-K5 |
| `r1/`, `r1n/` | Candidate goals, validators, ledgers and human-review artifacts |
| `review/` | The independent reviewer's own probes and findings — not written by this Implementer |

The `/tmp/disp-r1-stage` staging root used for tests P1-P4 and the N1 proof is
throwaway and outside the repository.
