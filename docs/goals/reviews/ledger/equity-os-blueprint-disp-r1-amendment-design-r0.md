# DISP-R-1 amendment design r0

**Status: DESIGN ONLY — NOT APPROVED FOR EXECUTION.**

The user has approved *designing* this amendment. The user has **not** approved
executing it. Nothing in this document may be applied to any canonical file.
No canonical byte, no Beads record, and no Git state was changed to produce it.
The only files written were probes under `scratchpad/disp-r1/`.

Predetermined independent review path:
`docs/goals/reviews/ledger/equity-os-blueprint-disp-r1-amendment-design-r0-review-r0.md`

---

## 0. Verified pre-state

Every hash below was computed fresh with `sha256sum` at the start and re-verified
at the end of this work. All seven match the values supplied in the task brief.

| Artifact | SHA-256 |
|---|---|
| `docs/goals/equity-os-blueprint-completion.md` | `f15f7ab5a4e425dec3877ab7f1f7594687979060e4dbcd49390a8a8d5fedb85f` |
| `docs/goals/equity-os-blueprint-component-ledger.jsonl` | `de236d7e8dcf02e307ec58797f5722ae2f85d1d8cdba57d4ecc07df5383c9c97` |
| `docs/goals/equity-os-blueprint-human-review-needed.md` | `094fcdfab74a3f4c6fdb82b1520fc4d13b636ac0e9ed10194e5d607aed2ce9af` |
| `scripts/equity_os_blueprint/validate_ledger_structural.py` | `731d0d8b208b577967c92e3992e7ec1a4333cdecbf89f6951c32d2ec469436f9` |
| `scripts/equity_os_blueprint/validate_ledger_preimplementation.py` | `f7a225a1f99cb85c92cde3094505a92a746552280eb45dae0253a71ab9048013` |
| `scripts/equity_os_blueprint/extract_goal_validators.py` | `5d20d796666d1154fb3c84ba4fa7407ee82819510a5ac06254f7f4a3126c6f2a` |
| `CONTEXT.md` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |

Supporting artifacts, freshly hashed here because the amendment reasons about
their bytes:

| Artifact | SHA-256 |
|---|---|
| `docs/specs/equity-os-s20-memory-benchmark-gbrain.md` | `4948d0f84240cd58b107da1272ed2b90a386bc3fb9ebb6228faac8b98be9c483` |

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

The three reason codes matter: r7 §8.1 predicted exactly this triple, including
that `HISTORICAL_REFS_UNCOVERED` "is a true conjunct of the closed predicate
under the emptied `evidence_ref_ids` and must also be emitted". The live
behaviour matches the design.

---

## 1. Facts first — the deadlock, mechanically reproduced

### 1.1 The brief's line cites are correct

Verified against `validate_ledger_structural.py` @
`731d0d8b208b577967c92e3992e7ec1a4333cdecbf89f6951c32d2ec469436f9`:

- `:2674-2686` — `EXPECTED_DISP_R1_REQUIREMENT` is a literal dict pinning
  `"status": "UNRESOLVED"` and `"evidence_ref_ids": []` alongside the
  requirement's identity fields. **Confirmed, exact.**
- `:2756` — `assert EXPECTED_DISP_R1_REQUIREMENT in disp_r1["required_evidence"]`.
  **Confirmed.**
- `:2760` — `assert disp_r1_proven is False`. **Confirmed.**
- `:2761-2763` — asserts `{"REQUIREMENT_UNRESOLVED",
  "CURRENT_REVIEWER_ROLE_EVIDENCE_REVIEW_MISSING"} <= set(disp_r1_reasons)`.
  **Confirmed.**
- `validate_ledger_preimplementation.py:126-217` — the closed predicate and the
  `unmet_no_implementation_proof` accumulator. **Confirmed**, with the precise
  boundaries `:128` (`NO_IMPLEMENTATION_REQUIREMENT_MAP`), `:132` (`def
  current_no_implementation_proof`), `:217` (`unmet_no_implementation_proof = []`).
- Goal SUCCESS condition 5 (`docs/goals/equity-os-blueprint-completion.md:5752-5756`)
  requires current no-implementation proof. **Confirmed** (quoted in §1.4).

### 1.2 One correction to the brief's framing

The brief says the pin means "satisfying the requirement fails structural
validation". True, but the mechanism is narrower and more important than
"the validators are pinned":

**The block is a single `in` test against a whole-object literal, at
`:2756`, and it runs unconditionally at module top level.** I verified the
placement with an AST walk rather than by eye: the two `args.reconciliation_check`
guards in the file cover `:31-32` and `:2912-3244`. The DISP-R-1 statements at
`:2752`, `:2753`, `:2756`, `:2757`, `:2760`, `:2761`, `:2764` are all top-level
`Assign`/`Assert` nodes — outside both guards. A grep for `DISP-R-1` and
`no_implementation` inside `:2912-3244` returns **nothing**.

That placement is a genuine divergence from the design that authorized it, and
it is the crux of item 1 — see §1.5.

### 1.3 Both horns reproduced

Probe: `scratchpad/disp-r1/probe_deadlock.py`. It reads canonical bytes and
writes only a candidate ledger under `scratchpad/disp-r1/`.

**Horn B — leave the requirement unresolved.** Canonical bytes, unchanged:

```
preimplementation --report-blockers -> exit 2, ready=False,
  unmet_no_implementation_proof = [{"component_id": "DISP-R-1", ...,
    "reason_codes": ["CURRENT_REVIEWER_ROLE_EVIDENCE_REVIEW_MISSING",
                     "HISTORICAL_REFS_UNCOVERED", "REQUIREMENT_UNRESOLVED"]}]
```

**Horn A — satisfy the requirement properly.** The probe builds a candidate
ledger in which `REQ-DISP-R-1-NO-IMPLEMENTATION` is `SATISFIED` with
`evidence_ref_ids=["EV-DISP-R-1-SPEC-DRAFT"]`, and `evidence_inventory_review`
is a `COMPLETE`/`CLEAN` `REVIEWER`-role review bound to `CONTEXT.md` with both
content digests recomputed over the post-state row:

```
reviewed_input_sha256     = e5058b00f6db5bbbdfcdffdc5667cdeeb0df50d11a2ab69d762e96d9b823461a
reviewed_inventory_sha256 = 1a15a5a645ec7660ad7782c9f28d808024c1ae719adb5225f999200226f16700

structural --ledger-path <candidate> --human-review-path <copy>  -> exit 1
  File ".../validate_ledger_structural.py", line 2756, in <module>
    assert EXPECTED_DISP_R1_REQUIREMENT in disp_r1["required_evidence"]
  AssertionError
```

The failure is at **exactly `:2756`**, as the brief predicted.

**The decisive extra measurement.** Running the *preimplementation* validator
against that same satisfying candidate:

```
exit=2 ready=False  DISP-R-1 unmet entries=0  pending_reviews=446  stale_reviews=0
```

The DISP-R-1 blocker is **gone**, and the pending-review count drops 447 → 446.
So the deadlock is not a deep contradiction between two independent gates. The
closed predicate, the ledger schema, the review schema, and the preimplementation
gate all already admit a correct proof. **The only thing standing in the way is
the top-level pin in the structural validator.** That is what makes a minimal
amendment possible.

### 1.4 The goal's own prose already licenses the proof

`docs/goals/equity-os-blueprint-completion.md:461-474`, verbatim:

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

Read together: the prose defines a *reachable* proof condition and SUCCESS
*requires* reaching it. The prose contains no statement anywhere that DISP-R-1
must remain unproven. I confirmed this: outside the three embedded program spans
(goal lines 1356-4600, 4607-4865, 4873-5700), the string `DISP-R-1` occurs in
the goal exactly **once**, at line 5831 — inside the immutable HR-0004 approval
record, which this amendment does not touch.

**So the goal's prose and the goal's extracted validator disagree.** The prose
says "proof is reachable and SUCCESS requires it"; the validator says "proof is
permanently forbidden". The amendment removes the contradiction on the
validator side, which is the side that is wrong.

### 1.5 Deliberate temporary measure, or oversight? — Both, in separable parts

**The unproven post-state was deliberate.** r7 §3.6 (`…-ledger-remediation-design-r7.md:576-593`)
states it in terms that leave no doubt, and explicitly anticipates the change
this document designs:

> `DISP-R-1` is deliberately not counted as having current no-implementation
> proof after this transaction. […] The unchanged rejection record continues to
> account for the pinned rejection authority, but its historical
> `no_implementation_evidence_ref_ids=["EV-DISP-R-1-SPEC-DRAFT"]` does not
> satisfy the requirement. **A later substantive review may establish current
> proof only by changing the requirement and review through the ordinary
> evidenced process; this reconciliation does not perform or imply that review.**

That is a deliberate, correct, temporary safety measure. HR-0004 was a
digest-repair transaction; letting it also *manufacture* a no-implementation
proof out of a digest refresh would have been exactly the abuse r7 was written
to prevent. Retaining the unproven state was right.

**The permanence of the pin was an over-implementation.** r7 §8.1
(`:1541-1551`) assigns ownership of the pin to reconciliation mode:

> **In reconciliation mode** it also owns the exact r7/review binding comparison
> from §5.3, the exact `DISP-R-1 -> REQ-DISP-R-1-NO-IMPLEMENTATION` proof map,
> the rule that false current proof is structurally valid, and the rule that
> every post-state `(approval_type, required_authority)` pair exists in the
> baseline or in §3.7's authorized additions. It requires the §3.6 unresolved
> object and false current-proof result **in this post-state**.

"In reconciliation mode" and "in this post-state" both scope the requirement to
the HR-0004 transaction check. The corresponding r7 §8.3 postcondition
(`:1702-1705`) is likewise phrased as a postcondition *of that transaction*.
The generated validator instead placed the pin at module top level, where it
binds every future validation run forever.

I want to be precise about the strength of this claim, because it is the one
place where I am reading intent:

- **Certain:** the pin executes unconditionally on every structural run
  (AST-verified, §1.2), and no DISP-R-1 assertion exists inside the
  reconciliation block (grep-verified, returns nothing).
- **Certain:** r7 §3.6 explicitly contemplates a later change establishing proof.
- **Inference (strong):** r7 §8.1's "In reconciliation mode … in this
  post-state" language scopes the pin to reconciliation, so top-level placement
  exceeds what §8.1 specified.
- **Speculation, and I flag it as such:** whether the author placed it at top
  level by mistake or as a deliberate belt-and-braces choice. I found no
  evidence either way. r7 §8.1 does say the *reporting* validators must emit
  the blocker, which requires a live predicate but not a live `assert`.

The honest one-line answer: **the unproven state was a deliberate temporary
safety measure; making it a permanent unconditional assertion was an
over-implementation of r7 §8.1, which scoped that requirement to reconciliation
mode.** Either way the practical consequence is identical and r7 §3.6 already
authorizes the remedy in principle — the remedy just needs its own approval.

---

## 2. What a genuine current proof would be

### 2.1 The requirement, as it stands

From the canonical ledger row `DISP-R-1`:

```json
{"approval_ids":[],"description":"Current S20 draft preserves D-02 as dormant and contains no implementation claim","evidence_id":"REQ-DISP-R-1-NO-IMPLEMENTATION","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"R-1 current no-implementation proof","status":"UNRESOLVED"}
```

`rejection_record.no_implementation_evidence_ref_ids` is `["EV-DISP-R-1-SPEC-DRAFT"]`.

### 2.2 The artifact and its digest binding

`EV-DISP-R-1-SPEC-DRAFT` already exists on the row and already binds the right
artifact:

```json
{"captured_at":"2026-08-15T07:13:28Z","content_sha256":"4948d0f84240cd58b107da1272ed2b90a386bc3fb9ebb6228faac8b98be9c483","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-DISP-R-1-SPEC-DRAFT","path":"docs/specs/equity-os-s20-memory-benchmark-gbrain.md","scope":"Current draft specification bytes for DISP-R-1","start_line":null}
```

I verified `sha256sum docs/specs/equity-os-s20-memory-benchmark-gbrain.md` =
`4948d0f84240cd58b107da1272ed2b90a386bc3fb9ebb6228faac8b98be9c483`. **The
evidence object is current against live bytes**, which is why
`HISTORICAL_REF_STALE` does not appear in the reason codes.

`FILE_BYTES` over the whole spec is the correct binding for this requirement.
The claim is negative and whole-file — "contains no implementation claim" — so a
`UTF8_LINE_SPAN` over some excerpt would be strictly weaker: it would let text
added elsewhere in the file escape the digest. No new evidence object is needed
for the proof itself.

### 2.3 What S20 actually says about D-02 — verified

I read the spec (268 lines, 30,261 bytes). It does preserve D-02 as dormant and
makes no implementation claim:

- `:7` — "S20 is dormant-only. It defines activation predicates, evidence,
  evaluation, and fail-closed behavior; **it does not activate any row, install
  GBrain, run a benchmark, or approve adoption.**"
- `:17` — the D-02 register row is quoted with Status `Deferred`, annotated
  "Dormant benchmark contract."
- `:35` — D-02 mapped `Deferred` → `CONDITIONAL_UNACTIVATED`: "Preserve
  benchmark design and activation evidence; **do not run or claim results.**"
- `:39` — "Because every owned row was Deferred at activation, S20 may not enter
  `PLANNED`, `IMPLEMENTING`, or `VERIFIED` until the exact row being advanced is
  validly activated."
- `:174` — "D-02, D-04, and D-05 implementation/delivery references remain
  absent while their individual Status is Deferred."
- `:251` — "Structural checks prove no owned Deferred row has implementation
  references or an active delivery state before its own valid activation."
- `:20` — "R-1 disposition | 'Disposition: Reject.' | The proposal to cancel
  D-02 is rejected; S20 retains it."

On the substance, a REVIEWER should be able to reach `CLEAN`. **This is my
reading as the Implementer and it is explicitly not the required review** — the
REVIEWER-role review is a separate act by a separate agent, and §4 turns on
exactly that.

### 2.4 What the review must look like — from the live schema

Read from `validate_ledger_structural.py:238-357`, not from prose:

- `review_fields` = `{review_type, status, reviewer, model, effort, verdict,
  timestamp, evidence_ref_ids, reviewed_input_sha256, reviewed_inventory_sha256}`.
- A `COMPLETE` review must have **exactly** `review_fields | {role,
  role_binding_path, role_binding_sha256}` (`:325`); a `PENDING` review exactly
  `review_fields` (`:327`). DISP-R-1's current review is `PENDING` and correctly
  lacks the role-binding keys — **so no schema change is needed to record a
  COMPLETE review.** I checked this specifically because a closed key set would
  have been a second, independent deadlock horn. It is not.
- `assert_reviewer_role_binding` (`:250-262`): `role == "REVIEWER"`,
  `role_binding_path == "CONTEXT.md"`, `role_binding_sha256` a 64-hex digest,
  and non-empty `model` and `effort` strings.
- `verdict == "CLEAN"`, non-empty `reviewer`, `timestamp <= validation_now` and
  `>=` every linked ref's `captured_at` (`:341-348`).
- `reviewed_input_sha256` == `canonical_sha256(review_input_projection(row))`
  and `reviewed_inventory_sha256` == `canonical_sha256(review_inventory_projection(row, "EVIDENCE"))`
  (`:352-357`).

Two consequences that drive §4 and §7:

1. **`review_input_projection` includes `required_evidence`** (`:277`). The
   requirement's own `status` flip therefore changes the digest the review must
   carry. The review must be sealed against the **post-state** row, and it is
   the last field written.
2. **`role_binding_sha256` is an immutable historical capture**, deliberately
   not a declared evidence object (docstring at `:252-255`), so a later
   `CONTEXT.md` edit does not invalidate completed reviews. Current
   `CONTEXT.md` = `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce`.

Per `CONTEXT.md:137-147`, `REVIEWER` is "an independent subagent that reviews an
implementer's output. Always a separate agent and context from the implementer
of the same artifact", currently bound to Claude Opus 5, high effort. The
`model` and `effort` recorded must be the actually-invoked values.

---

## 3. The minimal amendment

### 3.1 Design principle

Do not delete the protection — **make it two-sided**. Today the validator asserts
one permitted state. The amendment asserts that DISP-R-1 is in one of exactly
**two** permitted states, with the second gated on the closed predicate being
independently true. Deleting the asserts outright would be smaller but strictly
worse: it would let a ledger set `status=SATISFIED` with no review at all and
still pass structural validation.

The requirement's **identity** stays pinned byte-for-byte. Only `status` and
`evidence_ref_ids` become mobile, and only together.

### 3.2 Change 1 of 3 — goal prose

Location: `docs/goals/equity-os-blueprint-completion.md`, the typed
evidence/verification section, immediately after the A6 paragraph quoted in
§1.4. Outside all three program spans.

**Before** (exact, 1 occurrence):

```
False is a valid structural state and an explicit
preimplementation and terminal blocker; no description substring or refreshed
content digest substitutes for this closed predicate.
```

**After** (exact):

```
False is a valid structural state and an explicit
preimplementation and terminal blocker; no description substring or refreshed
content digest substitutes for this closed predicate.

Structural validation additionally owns the mapped requirement's immutable
identity and its closed two-state rule. `DISP-R-1` has exactly two permitted
proof states: its mapped requirement is `UNRESOLVED` with no evidence refs and
the closed predicate is false with its fixed reason codes, or the requirement
is `SATISFIED` with evidence refs covering every historical rejection-record
ref and the closed predicate is independently true with no reasons. The
requirement's identity fields never change, and no third state exists, so a
`SATISFIED` status can never be asserted by fiat.
```

The A6 required marker — `has current no-implementation proof only when` — is
untouched and still present in prose. No lane token is introduced.

### 3.3 Change 2 of 3 — the pinned literal (structural program)

Goal lines 4028-4040; generated `validate_ledger_structural.py:2674-2686`.

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
# The immutable identity of the mapped DISP-R-1 proof requirement. Only
# `status` and `evidence_ref_ids` may ever move, together, under the closed
# two-state rule asserted below.
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
DISP_R1_MUTABLE_FIELDS = {"status", "evidence_ref_ids"}
```

### 3.4 Change 3 of 3 — the post-state asserts (structural program)

Goal lines 4110-4122; generated `validate_ledger_structural.py:2756-2768`.
`disp_r1 = by_id["DISP-R-1"]` and the `rejection_record` assert at `:2752-2755`
are **unchanged** and are not part of the replaced span.

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
disp_r1_requirement = next(
    item for item in disp_r1["required_evidence"]
    if item["evidence_id"] == "REQ-DISP-R-1-NO-IMPLEMENTATION"
)
assert {
    key: value for key, value in disp_r1_requirement.items()
    if key not in DISP_R1_MUTABLE_FIELDS
} == EXPECTED_DISP_R1_REQUIREMENT_IDENTITY
disp_r1_proven, disp_r1_reasons = current_no_implementation_proof(disp_r1)
# r7 §3.6/§8.1 kept this post-state explicitly unproven and fixed the reason
# codes a digest refresh alone can never remove. That state remains the only
# alternative to a fully evidenced current proof: either the requirement is
# untouched and unresolved, or it is SATISFIED and the closed predicate is
# independently true. There is no third state, so proof cannot be asserted by
# fiat, by a digest refresh, or by the historical rejection-record refs.
if disp_r1_requirement["status"] == "UNRESOLVED":
    assert disp_r1_proven is False
    assert {
        "REQUIREMENT_UNRESOLVED",
        "CURRENT_REVIEWER_ROLE_EVIDENCE_REVIEW_MISSING",
    } <= set(disp_r1_reasons)
    assert any(
        item["component_id"] == "DISP-R-1"
        and item["requirement_id"] == "REQ-DISP-R-1-NO-IMPLEMENTATION"
        for item in unmet_no_implementation_proof
    )
else:
    assert disp_r1_requirement["status"] == "SATISFIED"
    assert set(disp_r1_requirement["evidence_ref_ids"]) >= set(
        disp_r1["rejection_record"]["no_implementation_evidence_ref_ids"]
    )
    assert disp_r1_proven is True
    assert disp_r1_reasons == []
    assert not any(
        item["component_id"] == "DISP-R-1"
        for item in unmet_no_implementation_proof
    )
```

Note the `UNRESOLVED` branch deliberately omits an
`evidence_ref_ids == []` assert: the global schema already enforces the
`UNRESOLVED` ↔ empty-refs coupling at `:2138-2141`, and duplicating it here
would add a line that can never fail.

### 3.5 What is *not* changed

- The preimplementation program: **byte-identical**. Verified — the
  candidate-extracted preimplementation validator hashes to
  `f7a225a1f99cb85c92cde3094505a92a746552280eb45dae0253a71ab9048013`, equal to
  the canonical file.
- The terminal program: no DISP-R-1 pin exists in it (grep over goal lines
  5200-5720 for `disp_r1|EXPECTED_DISP|is False` returns nothing). Its hash
  changes only because it is re-extracted, not because its text changes; the
  terminal program is never a checked-in script.
- The canonical ledger: **zero rows change**. See T3 in §3.7.
- The canonical human-review artifact: unchanged.
- `extract_goal_validators.py`: unchanged. See §3.8.
- The HR-0004 approval record at goal `:5831`: unchanged. It is an immutable
  record of a past exchange and correctly continues to describe what HR-0004
  did.

### 3.6 Why this does not weaken the protection

The three abuses the pin was guarding against, and what blocks each **after**
the amendment:

| Abuse | What blocks it | Enforced at |
|---|---|---|
| Prove by digest refresh alone | Refreshing an evidence object changes `evidence_refs`, which is in `review_input_projection`, so any pre-existing review's `reviewed_input_sha256` no longer matches and the review is rejected | `:352-357` |
| Prove by historical rejection-record refs | `HISTORICAL_REFS_UNCOVERED` requires the refs to be listed on the *requirement*; membership in `rejection_record` sets nothing. And the review must itself link every historical ref | predicate `:2707-2709`, `:2719` |
| Prove without a current REVIEWER-role review | `disp_r1_proven is True` in the new `else` branch is only reachable when the closed predicate returns no reasons, which requires the `COMPLETE`/`CLEAN`/`REVIEWER` review | new `else` branch |
| Prove by weakening the requirement's wording | Identity fields still pinned byte-for-byte | new identity assert |

The structural predicate is a slightly weaker copy of the preimplementation one
— it omits `HISTORICAL_REF_STALE`, the non-empty `model`/`effort` check, and the
`review_state(...) == "COMPLETE"` digest recomputation. I checked whether that
weakness matters and it does not, because each omitted conjunct is enforced
globally elsewhere in structural validation:

- evidence byte-freshness for **every** evidence object: `:220-233`
  (`assert evidence["content_sha256"] == actual_digest`);
- non-empty `model`/`effort` on every `COMPLETE` review: `:261-262`;
- both review digests recomputed on every `COMPLETE` review: `:352-357`.

### 3.7 Mechanical verification of the amendment

Probe: `scratchpad/disp-r1/probe_amendment.py`. It applies the three
replacements to a **candidate** goal under `scratchpad/disp-r1/`, extracts
candidate validators from it, and tests them. Canonical files are read-only
throughout.

| Test | What it proves | Result |
|---|---|---|
| T1 | Each of the three spans occurs **exactly once** in the goal; all three replace cleanly | PASS |
| T2 | `extract_goal_validators.py --check` on the candidate goal → **exit 0**, including the D.1 required-marker check and the D.2 lane-token check | PASS |
| T3 | Amended structural validator on the **unchanged canonical ledger** → **exit 0** | PASS |
| T4 | Amended structural validator on the properly evidenced candidate → **exit 0** (was exit 1 at `:2756`) | PASS |
| T5 | All four forbidden shortcuts still rejected | PASS |

T5 in detail, each failing at a named line of the amended validator:

| Shortcut | Exit | Rejected at |
|---|---|---|
| S1 — `status=SATISFIED` + refs, **no** current REVIEWER review | 1 | `line 2789: assert disp_r1_proven is True` |
| S2 — fresh COMPLETE REVIEWER review "proving" it via the historical ref, requirement left `UNRESOLVED` | 1 | `line 2152: validate_inventory_review(..., "EVIDENCE")` |
| S3 — requirement `description` weakened to "S20 exists", then satisfied | 1 | `line 2762: assert {…} == EXPECTED_DISP_R1_REQUIREMENT_IDENTITY` |
| S4 — genuine proof, then evidence recaptured **after** the review | 1 | `line 2152: validate_inventory_review(..., "EVIDENCE")` |

T3 is the most important single result: **the amendment is ledger-neutral.**
Applying it changes no ledger row and the current canonical ledger continues to
validate. That is what makes the two-transaction sequencing in §4 safe.

Reproduce with:

```
python3 scratchpad/disp-r1/probe_deadlock.py
python3 scratchpad/disp-r1/probe_amendment.py
python3 scratchpad/disp-r1/probe_interaction.py
```

### 3.8 Extractor markers — a deliberate non-change, with a flagged option

r7 §7.3 D.1 established one required marker substring per amendment item
A1-A11, so prose/validator drift fails loudly. A strict reading says a new
amendment item A12 deserves a new marker in `REQUIRED_MARKERS`.

I am **not** proposing that, for one reason: `extract_goal_validators.py` is
hand-maintained, not extracted from the goal, so adding a marker widens the
change from "the goal and its generated validator" to "the goal, its generated
validator, and the extraction harness" — and the D.2 lane-token check plus the
existing A6 marker already cover the prose this amendment touches. The new
prose paragraph in §3.2 sits directly under the A6 marker text, so A6's
presence check already fails if that region is deleted.

**This is a judgment call and I flag it for the reviewer.** Adding
`"A12": "has exactly two permitted proof states"` to `REQUIRED_MARKERS` would
be more faithful to r7 §7.3 D.1's discipline at the cost of one extra changed
file. If the reviewer prefers fidelity to minimality, the §3.2 prose already
contains that exact substring, so the addition is a one-line change requiring
no prose edit.

---

## 4. Sequencing — the amendment unlocks only; evidence is recorded later

### 4.1 Decision

**Two transactions.** T1 (this amendment) unlocks the possibility and records
**no** S20 evidence. T2 (a separate, later transaction) records the evidence and
satisfies the requirement.

### 4.2 Why not combine them

1. **The review cannot be fabricated, and combining would require pre-dating
   it.** The REVIEWER-role review of S20 must happen at a real point in time
   against real bytes, by an agent that is not the implementer of the artifact
   (`CONTEXT.md:137-139`). The goal itself sets this standard at `:447-448`:
   "The validator never fills these digests, and this draft contains no
   fabricated live review values."
2. **A combined transaction is self-referential.** `reviewed_input_sha256`
   covers `required_evidence` (§2.4), so the review must be sealed against the
   post-state row — a row that does not exist until the transaction produces
   it. The reviewer would have to attest to a candidate artifact generated by
   the very transaction awaiting their attestation. That is achievable via a
   rehearsal, but it makes the reviewer's object of review a temporary file,
   which is a materially weaker audit trail than reviewing a committed state.
3. **T2's inputs do not exist yet.** T2 must run after the 447-review recorder
   (§7), whose output bytes are not yet written. A combined transaction's
   approval question could not name real post-state hashes today; T1's can name
   every one of them.
4. **T1 is provably ledger-neutral** (T3). A change that touches two files and
   alters no ledger row is far easier to approve, rehearse, verify, and roll
   back than one that also rewrites a ledger row and three review objects.

### 4.3 What must exist BEFORE T1 can run

1. This design document, at its final bytes.
2. An independent `REVIEWER`-role review at the predetermined path
   `…-disp-r1-amendment-design-r0-review-r0.md`, verdict `CLEAN`, whose
   recorded reviewed-input SHA-256 equals this document's SHA-256, with its
   actual invoked model and effort recorded, under the `CONTEXT.md` "Agent
   roles" binding. Per project policy the reviewer must be a different agent
   and context from this Implementer.
3. Explicit user approval of the §6 question, with all placeholders resolved.
4. Canonical pre-state hashes still equal to §0.

Notably **absent**: no S20 review, no evidence capture, no recorder output.
T1 depends on none of them.

### 4.4 What must exist BEFORE T2 can run

1. T1 landed and verified.
2. The 447-review recorder workstream complete (§7), so T2's re-sealing is not
   subsequently overwritten.
3. A real, independent `REVIEWER`-role review of
   `docs/specs/equity-os-s20-memory-benchmark-gbrain.md` at its then-current
   bytes, reaching `CLEAN` on the question in §2.3, performed at a real
   timestamp no earlier than `EV-DISP-R-1-SPEC-DRAFT.captured_at`.
4. Its own design, review, and user approval. **T2 is out of scope for this
   document** and is named here only so the sequencing is honest.

---

## 5. Transaction design for T1 (at the HR-0004 r7 bar)

T1 reuses r7's proven machinery **by reference**: §6.2 transaction boundary and
rollback, §6.3 candidate-validation root with overlay teardown and fail-closed
exit 2, §8.2 candidate command shapes. r7's *approval* machinery (the §5.3
approval-evidence record, the 144-ID structured scope, the reconciliation-mode
baseline comparison) is **not** reused: T1 is not a `RECONCILE_AUTHORITY`
transaction, changes no ledger row, and needs no structured component scope.

### 5.1 Pre-state hashes — all bound

Every hash in §0 is a precondition. T1 aborts without any write if any differs.

### 5.2 Exact scope — two files, nothing else

| Path | Change | Pre-state SHA-256 | Post-state SHA-256 |
|---|---|---|---|
| `docs/goals/equity-os-blueprint-completion.md` | 3 exact span replacements (§3.2-3.4) | `f15f7ab5a4e425dec3877ab7f1f7594687979060e4dbcd49390a8a8d5fedb85f` | `ed92d7ba3939c123142c645ffdd3d567ecbe217cc6b7e90821b6a9539155039a` |
| `scripts/equity_os_blueprint/validate_ledger_structural.py` | regenerated by the extractor | `731d0d8b208b577967c92e3992e7ec1a4333cdecbf89f6951c32d2ec469436f9` | `ba9c730f59412544e86553a4c9def6117d1acf8780c8c47661c83353619d4c61` |

**Both post-state hashes are freshly computed, not placeholders.** The amendment
text in §3.2-3.4 is exact and the pre-state is fixed, so the post-state is
deterministic; the probe produced these bytes. They are reproducible by running
`probe_amendment.py` and hashing `scratchpad/disp-r1/candidate-goal.md` and
`scratchpad/disp-r1/candidate-validate-structural.py`.

Explicitly forbidden paths: the ledger, the human-review artifact,
`validate_ledger_preimplementation.py` (must stay
`f7a225a1f99cb85c92cde3094505a92a746552280eb45dae0253a71ab9048013`),
`extract_goal_validators.py`, `generate_initial_ledger.py`,
`record_inventory_review.py`, any spec, any blueprint file, any Beads record,
any Git commit or push.

### 5.3 Mandatory rehearsal

Before any canonical write, in a staging root outside the canonical tree
(r7 §6.3 pattern), with the overlay torn down afterwards:

1. Copy the canonical goal to `<staging>/candidate-goal.md`.
2. Apply the three replacements, asserting **exactly one** occurrence of each
   `before` span. Any count other than 1 aborts.
3. `sha256sum <staging>/candidate-goal.md` must equal
   `ed92d7ba3939c123142c645ffdd3d567ecbe217cc6b7e90821b6a9539155039a`.
4. Extract all three programs from the candidate goal to staging paths; the
   extractor syntax-checks each.
5. `sha256sum <staging>/candidate-validate-structural.py` must equal
   `ba9c730f59412544e86553a4c9def6117d1acf8780c8c47661c83353619d4c61`, and the
   candidate preimplementation validator must equal
   `f7a225a1f99cb85c92cde3094505a92a746552280eb45dae0253a71ab9048013`.
6. Run the §5.4 proof commands against the staged candidates.
7. Tear down the staging root. Any failure aborts with **zero** canonical writes.

### 5.4 Candidate proof commands and expected exit codes

| # | Command (paths abbreviated) | Expected |
|---|---|---|
| P1 | `extract_goal_validators.py --check --goal-path <cand-goal> --structural-output <cand-struct> --preimplementation-output <cand-pre> --terminal-output <cand-term>` | **0** |
| P2 | `<cand-struct> --repo-root . --ledger-path <canonical ledger> --human-review-path <canonical human-review>` | **0** |
| P3 | `<cand-pre> --repo-root . --report-blockers` | **2**, `ready=false`, DISP-R-1 blocker with all three reason codes, `pending_reviews`=447, `stale_reviews`=0 |
| P4 | `<cand-struct>` against the §3.7 S1/S2/S3/S4 shortcut ledgers | **nonzero for each** |
| P5 | `<cand-struct>` against the §3.7 T4 satisfying candidate | **0** |

P3 asserting **unchanged** blocker output is the ledger-neutrality proof: T1
must not move the gate by one row.

### 5.5 Journaled atomic replacement and rollback

Follow r7 §6.2 exactly. Only two files may be replaced.

1. Record a journal entry naming both paths, both pre-state hashes, and both
   intended post-state hashes.
2. Re-verify both live pre-state hashes immediately before writing. Any drift
   aborts.
3. Write both files via write-to-temp-then-atomic-rename **within the same
   journaled step**.
4. Verify both post-state hashes.
5. On **any** failure at any step — including a partial write — restore both
   files from the journaled preimages and re-verify both pre-state hashes.
   Preimages are retained until the postconditions in §5.6 all pass.

There is no valid intermediate state: goal and validator must move together or
not at all, or `extract_goal_validators.py --check` fails.

### 5.6 Postconditions

All must hold, or roll back:

1. Goal SHA-256 = `ed92d7ba3939c123142c645ffdd3d567ecbe217cc6b7e90821b6a9539155039a`.
2. Structural validator SHA-256 = `ba9c730f59412544e86553a4c9def6117d1acf8780c8c47661c83353619d4c61`.
3. Ledger, human-review artifact, preimplementation validator, extractor, and
   `CONTEXT.md` **byte-unchanged** at their §0 hashes.
4. `extract_goal_validators.py --check` → exit **0** (no arguments; canonical).
5. `validate_ledger_structural.py --repo-root .` → exit **0**.
6. `validate_ledger_preimplementation.py --repo-root . --report-blockers` →
   exit **2**, `ready=false`, `pending_reviews`=447, `stale_reviews`=0, and the
   DISP-R-1 unmet entry **identical** to §0's.
7. No ledger row changed; the 454-entry transition prefix invariant untouched
   (T1 appends no transition; DISP-R-1's baseline prefix length is 2 and its
   history remains 4 entries).
8. No delivery state, gate state, or activation advanced. Trivially true —
   T1 touches no ledger.
9. `git status` shows exactly the two authorized modified paths plus whatever
   was already dirty at §0 (`.beads/issues.jsonl` modified,
   `scripts/equity_os_blueprint/record_inventory_review.py` untracked — both
   owned by other work and untouched by T1).
10. The staging root is removed; no temporary candidate file survives.
11. No Beads mutation, no commit, no push.

### 5.7 UNSETTLED — does T1 also require a human-review reconciliation record?

**This is the one open scope question in the transaction design, and I am not
resolving it unilaterally.**

T1 changes the *contract document itself*. The goal's Activation record
(`:5849-5874`) pins the approved contract as `C0` =
`0e63f684d43ef2afcea998135c6d77f83c023a76c4075f42a2f2c6aba3f0028f`. The live
goal is `f15f7ab5a4e425dec3877ab7f1f7594687979060e4dbcd49390a8a8d5fedb85f` — the
contract has **already** drifted once, and HR-0004 was the reconciliation that
re-approved it. SUCCESS condition 1 (`:5738-5739`) reads:

> Authority hashes match the activation snapshot, or every change has been
> reconciled and re-approved under the source-drift rules.

Two facts I verified:

- **No validator mechanically checks the goal's own bytes.** Neither checked-in
  validator contains `f15f7ab5…`, `0e63f684…`, or any self-hash of the goal, and
  the goal file contains no self-hash. So T1 as designed in §5.2 passes every
  mechanical gate. Postcondition 4-6 in §5.6 were all confirmed by probe.
- **r2 expected a heavier transaction.** `…-inventory-review-recording-design-r2.md:631-636`
  states that clearing this blocker "requires amending the goal […] which is an
  `AUTHORITY_RECONCILIATION` under a fresh `RECONCILE_AUTHORITY` human
  resolution — a separate, user-approved transaction with its own reviewed
  design."

So the two options are:

| | Scope | Satisfies SUCCESS condition 1's audit trail | Risk |
|---|---|---|---|
| **(a)** T1 as designed in §5.2 | 2 files, user approval question only | **No canonical record** that this contract change was reconciled and re-approved | Passes all mechanical gates today, but leaves a gap a final blueprint-compliance audit (condition 8) should catch |
| **(b)** T1 + a new `HR-0005` entry and `RECONCILE_AUTHORITY` resolution | 3 files (adds the canonical human-review artifact) | Yes — matches the HR-0004 precedent and r2's expectation | **Untested.** I did not verify that adding `HR-0005` passes structural validation |

**My recommendation is (b)**, because condition 1 is a stated SUCCESS
requirement and a user approval recorded only in chat is exactly the kind of
uncaptured authority the ledger exists to prevent. But I am flagging rather than
adopting it, for a reason I can state precisely: structural validation pins
`EXPECTED_PRIOR_HR_LINKS` for `HR-0001..3` (`:2776-2821`) and gates HR-0004
behind `if "HR-0004" in human_entries` (`:2788`). Whether a fifth entry passes the
entry-digest, resolution-chain, and prior-link assertions is **untested by me**,
and asserting otherwise would be fabrication.

*What would settle it:* construct a candidate human-review artifact containing
`HR-0005` under `scratchpad/disp-r1/` and run the amended structural validator
against it with `--human-review-path`. That is a bounded next probe. If (b) is
chosen, §5.2, §5.6, and the §6 question all need a third file added to scope and
the design re-reviewed — which is why this is called out here rather than
silently folded in.

Everything else in §5 is independent of this choice.

---

## 6. The user approval question

**Conditional on §5.7.** The question below states option (a) — the two-file
scope. If the reviewer or user chooses option (b), this question must be
reissued with the canonical human-review artifact added to the authorized scope
and an `HR-0005` reconciliation record described. Do not ask this question until
§5.7 is settled.

The user has approved **designing** this amendment. They have **not** approved
executing it. This question must be asked and answered affirmatively before any
canonical byte changes.

Placeholders — and only these — remain unresolved, because the artifacts do not
yet exist. Every other value is freshly computed:

- `<DISP_R1_DESIGN_SHA256>` — this document's SHA-256, computable only once its
  bytes are final.
- `<DISP_R1_REVIEW_SHA256>` — the SHA-256 of the predetermined independent
  review at `…-disp-r1-amendment-design-r0-review-r0.md`, which does not exist yet.

> Do you approve one `AMEND_VALIDATOR_PIN` transaction bound to independently reviewed `docs/goals/reviews/ledger/equity-os-blueprint-disp-r1-amendment-design-r0.md` SHA-256 `<DISP_R1_DESIGN_SHA256>` and predetermined independent review `docs/goals/reviews/ledger/equity-os-blueprint-disp-r1-amendment-design-r0-review-r0.md` SHA-256 `<DISP_R1_REVIEW_SHA256>`, whose explicit verdict is `CLEAN`, whose explicit reviewed-input SHA-256 is `<DISP_R1_DESIGN_SHA256>` equal to that design SHA-256, and whose reviewer role is `REVIEWER` under the `CONTEXT.md` "Agent roles" binding with its actual invoked model and effort recorded in the review; active-goal pre-state SHA-256 `f15f7ab5a4e425dec3877ab7f1f7594687979060e4dbcd49390a8a8d5fedb85f`, structural-validator pre-state SHA-256 `731d0d8b208b577967c92e3992e7ec1a4333cdecbf89f6951c32d2ec469436f9`, ledger pre-state SHA-256 `de236d7e8dcf02e307ec58797f5722ae2f85d1d8cdba57d4ecc07df5383c9c97`, human-review pre-state SHA-256 `094fcdfab74a3f4c6fdb82b1520fc4d13b636ac0e9ed10194e5d607aed2ce9af`, preimplementation-validator pre-state SHA-256 `f7a225a1f99cb85c92cde3094505a92a746552280eb45dae0253a71ab9048013`, extractor pre-state SHA-256 `5d20d796666d1154fb3c84ba4fa7407ee82819510a5ac06254f7f4a3126c6f2a`, and role-binding `CONTEXT.md` SHA-256 `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce`, authorizing only one atomic change to exactly two files — the active goal to post-state SHA-256 `ed92d7ba3939c123142c645ffdd3d567ecbe217cc6b7e90821b6a9539155039a` and its extracted `scripts/equity_os_blueprint/validate_ledger_structural.py` to post-state SHA-256 `ba9c730f59412544e86553a4c9def6117d1acf8780c8c47661c83353619d4c61` — that replaces the permanently pinned `EXPECTED_DISP_R1_REQUIREMENT` whole-object literal and its unconditional `assert disp_r1_proven is False` with a pinned requirement-identity object plus a closed two-state rule under which `REQ-DISP-R-1-NO-IMPLEMENTATION` is either `UNRESOLVED` with the existing false-proof reason codes exactly as today, or `SATISFIED` only when its evidence refs cover every historical rejection-record ref and the closed current no-implementation-proof predicate is independently true with no reason codes; keeps the requirement's `description`, `scope`, `evidence_id`, `evidence_type`, `proof_mode`, and `approval_ids` pinned byte-for-byte so no weakened wording can be substituted; preserves the rule that a digest refresh alone, the historical `rejection_record` refs alone, or any state lacking a current content-bound `COMPLETE`/`CLEAN` `REVIEWER`-role evidence review can never establish proof; records no S20 evidence, performs no review, and satisfies no requirement, leaving `REQ-DISP-R-1-NO-IMPLEMENTATION` `UNRESOLVED` with empty evidence refs and the preimplementation gate `ready=false` with all 447 pending reviews and the identical DISP-R-1 blocker; changes no ledger row, no human-review byte, no preimplementation validator byte, no extractor byte, no spec, and no blueprint byte; preserves all 454 existing transition objects and appends none; creates no human-review entry and no Beads or Git mutation; and aborts without canonical change on any design hash, review path/hash/verdict/reviewed-input/role binding, pre-state hash, rehearsal, extraction, validation, postcondition, or replacement failure?

Recommendation: approve only that exact package, and only after the §7 ordering
rule is agreed with the 447-review workstream. Safe default: change no canonical
byte; DISP-R-1 remains permanently unprovable and goal SUCCESS remains
unreachable.

---

## 7. Interaction with the 447-review recording workstream

### 7.1 The conflict is harder than digest staleness

The brief anticipated digest staleness as the hazard. Staleness is real (§7.3),
but it is not the main problem. The main problem is a **direct contradiction on
a single field**.

`…-inventory-review-recording-design-r2.md` §3.6 ("The `DISP-R-1` carve-out —
mandatory, and counter-intuitive") instructs the recorder, verbatim:

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
requires the review to link **every** historical ref — that is, precisely the
ref r2 forbids. There is exactly **one** `evidence_inventory_review` slot on the
row. Both workstreams need it, with incompatible contents.

### 7.2 Proved, not argued

Probe: `scratchpad/disp-r1/probe_interaction.py`, run against the **amended**
candidate structural validator. It simulates the recorder's DISP-R-1 post-state
per r2 §3.6 (all three reviews `COMPLETE`, `EVIDENCE` linking only the
inventory-review evidence object).

| Scenario | Result |
|---|---|
| **I1** Recorder post-state, requirement untouched | exit **0** — the amendment does not disturb the recorder |
| **I2** Requirement satisfied on top of I1, review digests not recomputed | exit **1** at `line 1135: validate_inventory_review(..., "APPROVAL")` — stale |
| **I3** Digests recomputed, `EVIDENCE` review still omits the spec ref | exit **1** at `line 2789: assert disp_r1_proven is True` — **the conflict is real** |
| **I4** Digests recomputed **and** the `EVIDENCE` review links the **union** `{EV-DISP-R-1-INVREV-EVIDENCE, EV-DISP-R-1-SPEC-DRAFT}` | exit **0** — the only combination that works |
| **I5** Blast radius of changing `DISP-R-1.required_evidence` | exactly `DISP-R-1::APPROVAL`, `DISP-R-1::EVIDENCE`, `DISP-R-1::SCOPE` go stale — **confined to DISP-R-1**, no other row affected |

I3 is the finding that matters: recomputing digests is **not sufficient**. The
union in I4 works because the predicate's test is a subset test
(`set(historical) <= set(review_refs)`), so the recorder's own evidence object
can coexist with the historical spec ref.

I5 is the good news: because `review_input_projection` is per-row, changing
DISP-R-1's `required_evidence` invalidates only DISP-R-1's own three reviews.
The 446 other reviews are untouched.

### 7.3 The ordering rule

> **T1 (this ledger-neutral amendment) may land at any time. The 447-review
> recorder runs next, keeping its r2 §3.6 carve-out exactly as written. T2 (the
> DISP-R-1 evidence proof) runs strictly last, and must re-seal all three of
> DISP-R-1's reviews, with the `EVIDENCE` review linking the union of the
> recorder's evidence object and `EV-DISP-R-1-SPEC-DRAFT`.**

Why each part:

- **T1 anywhere:** T3 proves it is ledger-neutral and I1 proves the recorder's
  post-state still validates under it. It cannot invalidate the recorder's work
  because it touches no ledger row.
- **Recorder before T2, never after:** if the recorder ran after T2, it would
  overwrite DISP-R-1's `EVIDENCE` review with the INVREV-only form, producing
  exactly scenario **I3** — a ledger that fails structural validation. This
  ordering constraint is **mandatory, not advisory**.
- **T2 last, re-sealing all three:** by I5, satisfying the requirement staleness
  DISP-R-1's `APPROVAL` and `SCOPE` reviews too, not just `EVIDENCE`. T2 must
  recompute all three, and must write them **after** every other field change to
  the row, including `transition_history_sha256` if it appends a transition
  (both `required_evidence` and `transition_history_sha256` are inside
  `review_input_projection`).

**The alternative isolation option**, if the workstreams must proceed in
parallel: the recorder excludes DISP-R-1 entirely from its rewrite set, leaving
all three of its reviews `PENDING` for T2 to author together. That trades one
ordering dependency for one carve-out and leaves the preimplementation gate at
3 extra pending reviews until T2. I prefer the sequential rule above, because
the recorder's r2 §3.6 carve-out already exists and I1 proves it stays valid.

### 7.4 Required follow-up on r2

r2 §3.6's factual claims about `validate_ledger_structural.py:2674-2686` and
`:2756-2763` become **stale** the moment T1 lands: the literal is renamed and
the assert becomes two-sided. Its operational instruction to the recorder stays
correct — the recorder never touches `required_evidence`, so under the amendment
DISP-R-1 stays in the `UNRESOLVED` branch and linking only the INVREV evidence
remains the right behaviour. But the *rationale* changes from "this is
permanently forbidden" to "this is forbidden unless the requirement is
satisfied in the same transaction".

r2 is a design document, not a canonical artifact, so this is not a validator
failure. It still needs an erratum note so the next reader is not misled. That
edit is out of scope here and belongs to whoever owns r2.

---

## 8. Risks and open questions

### 8.1 Risks

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | The recorder lands after T2 and breaks the ledger (scenario I3) | **High** | The §7.3 ordering rule, agreed before either T2 or the recorder runs. Consider encoding it as a blocking Beads dependency. |
| R2 | T2 is treated as a formality once T1 lands, and the S20 review is rushed or self-reviewed | **High** | T1 records no evidence and moves the gate by zero rows (P3). The REVIEWER must be a different agent and context per `CONTEXT.md:137-139`. T2 needs its own design, review, and approval. |
| R3 | The amendment's `else` branch is reachable with an S20 that *does* contain an implementation claim | Medium | The validator can only check structure; the substantive judgment is the REVIEWER's. This is inherent to any content review and is why `description` stays pinned. |
| R4 | Post-state hashes in §5.2 drift if the goal changes before T1 runs | Medium | Both pre-state hashes are bound preconditions; T1 aborts on any drift and the design is re-derived. |
| R5 | Concurrent edits from the 447-review workstream touch the goal | Low | That workstream writes `record_inventory_review.py` and `scratchpad/inventory-reviews/`, not the goal. Verified: canonical hashes were byte-identical at the start and end of this work. |
| R6 | The extractor's D.1 marker set is not extended (§3.8) | Low | Flagged for the reviewer as an explicit judgment call, with the exact one-line change if they disagree. |
| R7 | T1 lands with no canonical record that the contract change was reconciled and re-approved, leaving SUCCESS condition 1 unevidenced | **High** | §5.7. Must be settled before the §6 question is asked. |
| R8 | T2 runs before the recorder, failing the recorder's own `unmet_no_implementation_proof == 1` postcondition (`record_inventory_review.py:1070`) | Medium | The §7.3 ordering rule; this is a second independent reason for it. |

### 8.2 Open questions I could not settle

1. **Was the top-level placement of the pin a mistake or belt-and-braces?**
   I established that it exceeds r7 §8.1's "in reconciliation mode … in this
   post-state" scoping (§1.5), but not the author's intent. *What would settle
   it:* the r7 executor handoff notes (r7 §10) or the HR-0004 recording artifact
   `equity-os-blueprint-hr-0004-recording-r0.md`, read specifically for whether
   top-level placement was chosen knowingly. I did not read those for this
   purpose. **It does not change the amendment** — the remedy is the same either
   way — so I did not expand scope to chase it.

2. **`APR-DISP-R-1-01` requires an authority that current policy prohibits.**
   The row carries `"required_authority": "Delegated fresh Sol xhigh
   specification reviewer"`, and the S20 spec header (`:3`) reads
   "**Status: DRAFT — AWAITING FRESH SOL XHIGH REVIEW**". The standing project
   policy prohibits gpt-5.6 lanes. Two things I verified rather than assumed:
   - This is **not** an r7 §3.8 violation. §3.8 scoped its role-vocabulary
     replacement to "the validator-checked review schema and reason codes" and
     said it changed "no ledger row for that purpose". `required_authority` is
     outside that scope.
   - This does **not** gate SUCCESS. The terminal validator's
     `required_approvals`-satisfied assertions are scoped to `active` rows
     (`for row in active`); the `rejected` loop requires only `proven`, a
     non-null `rejection_record`, empty `implementation_refs`, and a
     non-advanced `delivery_status`. DISP-R-1 is rejected, not active.

   So it blocks nothing today, but it is a policy-prohibited authority string
   sitting on the row, and the S20 spec header demands a prohibited reviewer
   lane. *What would settle it:* a user decision on whether these two strings
   should be reworded to the role vocabulary. **Out of scope for this
   amendment** — flagged, not touched.

3. **Should T2 append a transition-history entry?** The 454-entry prefix
   invariant is a *prefix* check (`:2902-2907`, DISP-R-1 baseline prefix length
   2, current history 4), so appending is permitted. Whether a `required_evidence`
   status change is a controlled transition requiring an entry is a question for
   T2's design, not T1's. I note only the ordering constraint it creates
   (§7.3): `transition_history_sha256` is inside `review_input_projection`, so
   any appended transition must be written **before** the reviews are sealed.

4. **Whether T1 needs a human-review reconciliation record — §5.7.** This is
   the **most consequential unresolved item** in this design. It changes the
   transaction's file scope and therefore the §6 approval question. It needs a
   decision before T1 is asked about, and one bounded probe to de-risk option
   (b). *What would settle it:* the reviewer's or user's call on (a) vs (b),
   plus the `HR-0005` candidate-artifact probe named in §5.7.

5. **~~Does anything outside these validators depend on
   `EXPECTED_DISP_R1_REQUIREMENT` by name?~~ RESOLVED — no.** A repo-wide
   `grep -rn EXPECTED_DISP_R1_REQUIREMENT .` returns hits only in the goal
   (`:4028`, `:4110`), the generated structural validator (`:2674`, `:2756`),
   and four inventory-review design/review documents (prose citations, r0/r1/r2
   and one review). The concurrently-developed
   `scripts/equity_os_blueprint/record_inventory_review.py` contains **zero**
   occurrences of `EXPECTED_DISP_R1_REQUIREMENT` or `disp_r1_proven` — I
   confirmed this with a read-only grep, without modifying that file. The
   rename in §3.3 breaks no code.

   Two related observations from the same read-only grep, both **compatible**
   with T1:
   - The recorder hard-codes its own r2 §3.6 carve-out (`:583`, `:664`, `:670`)
     rather than importing the validator literal, so I1 in §7.2 models it
     correctly.
   - The recorder's postcondition at `:1070` asserts
     `len(report['unmet_no_implementation_proof']) == 1`. T1 is ledger-neutral
     and leaves that blocker exactly as-is (§5.4 P3), so T1 does **not**
     invalidate the recorder's postcondition. Note this is a second, independent
     reason T2 must run **after** the recorder: T2 clears that blocker, which
     would make the recorder's own postcondition fail if the recorder ran later.

   The prose citations in the r0/r1/r2 design documents go stale on T1 — see
   §7.4.

---

## 9. Probe inventory

All under `scratchpad/disp-r1/` (gitignored). None is a proposed post-state.

| File | Purpose |
|---|---|
| `probe_deadlock.py` | Reproduces both horns (§1.3) |
| `probe_amendment.py` | Applies and validates the amendment, T1-T5 (§3.7) |
| `probe_interaction.py` | Recorder interaction I1-I5 (§7.2) |
| `candidate-goal.md` | Amended goal, `ed92d7ba…` |
| `candidate-validate-structural.py` | Amended structural validator, `ba9c730f…` |
| `candidate-validate-preimplementation.py` | Byte-identical to canonical, `f7a225a1…` |
| `candidate-ledger.jsonl`, `int-i*.jsonl`, `shortcut-*.jsonl` | Test ledgers |
