# Inventory-review recording design — r0

**Role:** `IMPLEMENTER` (CONTEXT.md "Agent roles (harness-wide)").
**Scope:** design only. This document changes no canonical file. It specifies
how the 447 `PENDING` content-bound inventory reviews on the canonical ledger
become `COMPLETE` under the active goal contract.

**Style/discipline reference:** `docs/goals/reviews/ledger/equity-os-blueprint-ledger-remediation-design-r7.md`
(pre-state hashes, exact mechanical rules, candidate proofs, transaction
safety). This design deliberately does **not** reuse r7's approval machinery —
§4 shows why no approval machinery applies here at all.

---

## 1. Verified pre-state

### 1.1 Pinned hashes

Captured at design time by `sha256sum` from repo root `/data/codes/equity-os`,
working tree at `8617e52` with `.beads/issues.jsonl` dirty (unrelated).

| Path | SHA-256 |
|---|---|
| `docs/goals/equity-os-blueprint-completion.md` | `f15f7ab5a4e425dec3877ab7f1f7594687979060e4dbcd49390a8a8d5fedb85f` |
| `docs/goals/equity-os-blueprint-component-ledger.jsonl` | `de236d7e8dcf02e307ec58797f5722ae2f85d1d8cdba57d4ecc07df5383c9c97` |
| `docs/goals/equity-os-blueprint-human-review-needed.md` | `094fcdfab74a3f4c6fdb82b1520fc4d13b636ac0e9ed10194e5d607aed2ce9af` |
| `scripts/equity_os_blueprint/validate_ledger_structural.py` | `731d0d8b208b577967c92e3992e7ec1a4333cdecbf89f6951c32d2ec469436f9` |
| `scripts/equity_os_blueprint/validate_ledger_preimplementation.py` | `f7a225a1f99cb85c92cde3094505a92a746552280eb45dae0253a71ab9048013` |
| `scripts/equity_os_blueprint/extract_goal_validators.py` | `5d20d796666d1154fb3c84ba4fa7407ee82819510a5ac06254f7f4a3126c6f2a` |
| `CONTEXT.md` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |

All seven match the values supplied in the task brief. Post-HR-0004 state
(txn `HR0004-2026-08-15T07:13:28Z-8966070df856`).

Baseline validator results at these bytes:

| Command | Exit |
|---|---|
| `python3 scripts/equity_os_blueprint/validate_ledger_structural.py --repo-root .` | `0` |
| `python3 scripts/equity_os_blueprint/validate_ledger_preimplementation.py --repo-root . --report-blockers` | `2` |

Baseline blocker report: `ready=false`, `pending_reviews=447`,
`stale_reviews=0`, `unmet_no_implementation_proof=1`.

### 1.2 Exact review inventory — freshly computed

213 rows = 169 canonical + 44 aliases. Which review types apply is **not** a
prose rule; it is `validate_ledger_preimplementation.py:200-204`, which builds
`checks` as `APPROVAL` + `EVIDENCE` always, and appends `SCOPE` only
`if row["kind"] != "register_row"`. `validate_ledger_structural.py` reaches the
same result structurally: for a `register_row` the contract fixes
`scope_derivation.semantic_review = null` (goal L233-236), and for an alias all
three review slots are `null` (goal L379, L452-453, L623-624).

| Kind | Rows | `SCOPE` | `EVIDENCE` | `APPROVAL` | Reviews |
|---|---:|---:|---:|---:|---:|
| `register_row` | 60 | 0 | 60 | 60 | 120 |
| `phase_gate_clause` | 35 | 35 | 35 | 35 | 105 |
| `disposition_item` | 32 | 32 | 32 | 32 | 96 |
| `first_release_deferral` | 13 | 13 | 13 | 13 | 39 |
| `sequence_clause` | 11 | 11 | 11 | 11 | 33 |
| `scale_trigger` | 8 | 8 | 8 | 8 | 24 |
| `document_strategy_clause` | 6 | 6 | 6 | 6 | 18 |
| `authority_clause` | 4 | 4 | 4 | 4 | 12 |
| **Canonical total** | **169** | **109** | **169** | **169** | **447** |
| `derivative_alias` | 44 | — | — | — | 0 |

**Correction to the task brief.** The brief states 107 `semantic_review` and a
441 total. The freshly computed figures are **109** and **447**
(169 canonical − 60 `register_row` = 109 non-register rows). Both the ledger
scan and the preimplementation blocker report agree:
`Counter({'APPROVAL': 169, 'EVIDENCE': 169, 'SCOPE': 109})`, 447 records. Every
number in this document is computed, not transcribed.

All 447 pending reviews carry exactly the 10-key `PENDING` key set
(`validate_ledger_structural.py:238-242`), with no role-binding keys present:

```
('effort','evidence_ref_ids','model','review_type','reviewed_input_sha256',
 'reviewed_inventory_sha256','reviewer','status','timestamp','verdict')
```

Other pre-state facts the reviewers will meet:

- `program_disposition` across canonical rows: `REQUIRED_NOW` 148,
  `CONDITIONAL_UNACTIVATED` 20, `REJECTED_ACCOUNTED` 1 (`DISP-R-1`).
- `required_evidence` list lengths: 0 on all 44 aliases; 1–6 on canonical rows.
- `required_approvals` list lengths: 0 on 84 rows (44 aliases + **40 canonical
  rows**), 1–5 on the rest. Those 40 canonical empties are load-bearing: the
  goal (L~186) says empty `required_approvals` is "a completed, evidenced
  determination that no approval is required, not an unknown inventory". The
  `APPROVAL` reviewer must affirm each emptiness, not skip the row.
- `evidence_refs` list lengths today: 1 (90 rows), 2 (100 rows), 5 (23 rows).
- 648 transition entries exist across the 213 rows.
- Human-review links: `HR-0004` alone on 111 canonical rows, plus
  `['HR-0001','HR-0004']` ×9, `['HR-0002','HR-0004']` ×5,
  `['HR-0003','HR-0004']` ×9.

---

## 2. The reviewer verdict artifact

### 2.1 What a `COMPLETE` review object must contain

`validate_ledger_structural.py:320-354` is authoritative. A `COMPLETE` review
carries **exactly** the 10 `PENDING` keys plus `role`, `role_binding_path`,
`role_binding_sha256` — 13 keys, no more, no fewer — and must satisfy:

| Field | Required value |
|---|---|
| `review_type` | `SCOPE` \| `EVIDENCE` \| `APPROVAL`, unchanged from `PENDING` |
| `status` | `COMPLETE` |
| `reviewer` | nonempty string |
| `role` | `REVIEWER` (asserted twice: in `REVIEW_ROLES`, then `== "REVIEWER"`) |
| `role_binding_path` | exactly `CONTEXT.md` |
| `role_binding_sha256` | lowercase 64-hex; `CONTEXT.md` bytes **at review time**, never re-verified against current bytes |
| `model` | nonempty string, actually invoked; never compared to a constant |
| `effort` | nonempty string, actually invoked; never compared to a constant |
| `verdict` | exactly `CLEAN` — the only accepted value |
| `timestamp` | UTC RFC3339 `…Z`, `<= now`, and `>=` every linked evidence `captured_at` |
| `evidence_ref_ids` | nonempty, a subset of the **same row's** `evidence_refs` IDs |
| `reviewed_input_sha256` | `canonical_sha256(review_input_projection(row))` |
| `reviewed_inventory_sha256` | `canonical_sha256(review_inventory_projection(row, review_type))` |

"Clean `REVIEWER`-role review" is therefore mechanically closed: **`verdict`
has exactly one legal value, `CLEAN`.** There is no `ISSUES_FOUND` /`BLOCKED`
verdict representable in a `COMPLETE` review object. A non-clean outcome is not
recordable as a review at all — see §5.4.

At the current `CONTEXT.md` bytes, `role_binding_sha256` would be
`8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce`. The
recorder must recompute this at record time, not copy this literal.

`model`/`effort` record what was *actually* invoked. Under the current
CONTEXT.md binding table that is Claude Opus 5 at high effort for the
`REVIEWER` role, but the recorder must take these from the verdict artifact the
dispatch produced, never from a hard-coded default.

### 2.2 Verdict artifact storage and evidence binding

**Storage.** One Markdown artifact per (component, review type), at a durable
repository path:

```
docs/goals/reviews/ledger/inventory/<COMPONENT_ID>/<REVIEW_TYPE>-r<N>.md
```

e.g. `docs/goals/reviews/ledger/inventory/SEQ-01/SCOPE-r0.md`. 447 files under
169 directories. Per-component directories keep `git status` and per-batch
diffs legible; a flat directory of 447 files does not.

Durable repo paths are mandatory, not stylistic: `evidence_refs[].path` is
resolved and hashed by the validator on **every** run
(`validate_ledger_structural.py:210-233`), and a missing target fails the
structural gate permanently. A scratchpad path would make the ledger
unvalidatable the moment `scratchpad/` is cleaned.

**Evidence object kind.** Exactly one new `evidence_refs` entry per review:

| Field | Value |
|---|---|
| `evidence_ref_id` | `EV-<COMPONENT_ID>-INVREV-<REVIEW_TYPE>` |
| `path` | the verdict artifact path above |
| `scope` | `"<REVIEW_TYPE> inventory-review verdict artifact for <COMPONENT_ID>"` |
| `digest_mode` | `FILE_BYTES` |
| `start_line`, `end_line` | `null`, `null` (required by `FILE_BYTES`) |
| `content_sha256` | SHA-256 of the artifact's bytes |
| `captured_at` | UTC RFC3339, `<=` the review `timestamp` |

`FILE_BYTES` over `UTF8_LINE_SPAN`: the whole verdict artifact is the evidence,
and a line-span binding would silently re-scope on any edit above the span, and
can exit `2` with `UNRESOLVABLE_UTF8_LINE_SPAN` if the file shortens.

`evidence_ref_id` uniqueness is **global**, not per-row
(`validate_ledger_structural.py:214` asserts against a ledger-wide
`evidence_by_id`). The `EV-<CID>-INVREV-<TYPE>` scheme is globally unique
because `component_id` is unique and no existing ID contains the `-INVREV-`
infix (verified: zero collisions across all 447 insertions in the full-scale
probe, §6.3).

**`evidence_ref_ids` on the review.** Exactly the one ID above, with one
carve-out (`DISP-R-1`, §3.6). The validator requires the set to be a subset of
the row's local evidence IDs and to be nonempty; it does not require it to be a
singleton.

**Verdict artifact content.** Human-readable Markdown recording: component ID,
review type, round, reviewer identity/session, role `REVIEWER`, the
`CONTEXT.md` binding path and its digest at review time, the actually-invoked
model and effort, UTC timestamp, the exact input hashes read (goal, ledger,
pinned register, disposition report, structural validator), the reviewed
inventory as the reviewer saw it, the reasoning, and an explicit
`verdict: CLEAN` line. The existing program-level artifacts
(`equity-os-blueprint-{evidence,approval}-inventory-r0.md`,
`equity-os-blueprint-scope-derivation-r0.md`) are the format precedent. Note
those are *program-level* completeness reviews (preimplementation gate bullet
4) and are **not** substitutes for the 447 per-component reviews (bullet 9);
they are separate obligations and both must hold.

The verdict artifact's own bytes are not parsed by any validator. The ledger
review object is the machine-readable record; the artifact is its evidence and
its audit trail. The recorder must therefore parse the artifact for the values
it copies, and must abort on any field it cannot read — never default.

---

## 3. The recording tool

### 3.1 Durable script, not a one-shot — and why

**Proposed path: `scripts/equity_os_blueprint/record_inventory_review.py`.**

The goal permits it. L1174-1178: "Once this goal is approved and activated, the
user authorizes repo-local writes, edits, narrowly scoped deletions, Beads
operations, narrow commits, pushes, and other repository operations necessary
to achieve this goal." Nothing in the protected-assets or default-deny sections
(L1180-1256) restricts adding a new script under `scripts/`.

r7 §6.1's "one-shot migrator … never becomes a repository mutation" rule does
**not** transfer. That constraint existed because the HR-0004 migrator rewrote
the goal and all three validator surfaces under a byte-verbatim user approval
scoped to exactly six canonical paths; a persistent migrator would have been a
standing capability to re-run an approved-once authority change. This tool
rewrites neither the goal nor any validator, needs no user approval (§4), and
runs **many times across many sessions** over 447 reviews. The verification
contract (L1321-1325) requires the coordinator to run each command and read its
output; a durable, hash-pinned script is reproducible, reviewable, and
diffable, whereas 40-odd unreproducible one-shots are the exact "agent reports
are not proof" failure mode.

`record_inventory_review.py` is a **new** file. It is not extracted from the
goal, so `extract_goal_validators.py --check` is unaffected (verified: the
extractor's `OUTPUTS` names only the two validator scripts). It must never
import from or write to the validator scripts.

### 3.2 Interface

```
python3 scripts/equity_os_blueprint/record_inventory_review.py \
  --repo-root . --batch <batch-manifest.json> [--dry-run]
```

The batch manifest is a JSON file listing, per (component, review type), the
verdict artifact path and the values parsed from it. `--dry-run` performs every
precondition check and digest computation and writes nothing.

### 3.3 Digest computation — byte-identical helper, verified

Both validators compute review digests with an identical function:

```python
def canonical_sha256(value):            # structural :72-76
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
```

`validate_ledger_preimplementation.py:49-53` defines `digest()` with the same
body. The two validators' projection functions are also equivalent: structural
`normalized_human_review_id` returns a `frozenset` wrapped in `sorted(...)` at
both call sites; preimplementation's returns an already-sorted list. Verified
equivalent by construction and by the full-scale probe passing both validators.

The recorder **must not** re-derive these projections from prose. It must carry
transcribed copies of `review_input_projection` / `review_inventory_projection`
and `canonical_sha256`, and §6.2 pins an equivalence check that fails the run if
the transcription ever drifts from the checked-in structural validator.

Structurally, per row:

- `reviewed_input_sha256` is **identical across all three review types on a
  row** — the input projection does not depend on `review_type`.
- `reviewed_inventory_sha256` is per type.

### 3.4 The ordering rule — the single load-bearing mechanic

`review_input_projection` includes `evidence_refs`, and the `EVIDENCE`
inventory projection includes `evidence_refs` as well. Therefore **appending
review evidence for one review type mutates the input digest of every other
review on the same row.**

The recorder must, per row, run two strictly ordered phases:

> **Phase A** — append *all* review-evidence objects for every review type
> being completed on that row (and any carve-out evidence), completing every
> mutation to the row's digest-covered state.
> **Phase B** — compute `reviewed_input_sha256` **once**, compute each
> `reviewed_inventory_sha256`, and write all review objects.

Counter-proof that this is not optional (§6.3, probe C): a recorder that
appends-and-digests per type produced, on `SEQ-02` alone,
`AssertionError` at `validate_ledger_structural.py:350`
(`reviewed_input_sha256` mismatch), structural exit `1`.

Corollary: a row must be completed **all-at-once or not at all**. Completing
`SCOPE` in batch 1 and `EVIDENCE` in batch 2 stales `SCOPE`. **Row atomicity is
a hard batching constraint (§5.1), not a preference.**

### 3.5 No transition entry — and why one is forbidden

The task brief asks which transition type/actor/reason the contract requires
for review completion. **The contract requires none, and forbids one.** Two
independent mechanisms:

1. `validate_ledger_structural.py:1732-1743` defines `controlled_direct_fields`.
   It contains no review object, no `evidence_refs`, no `required_evidence`, no
   `required_approvals`, no `approval_records`, no `review_round`. Line 1909
   asserts `field in controlled_fields`. A transition entry naming
   `evidence_inventory_review` (or `evidence_refs`) fails there.
   **Verified** (§6.3, probe D): `AssertionError` at
   `validate_ledger_structural.py:1909`, exit `1`.
2. `transition_history_sha256` is *inside* `review_input_projection`. Appending
   any entry to a row rewrites that digest and stales all three of that row's
   reviews. **Verified** (§6.3, probe E): the same entry on a row whose reviews
   were already `COMPLETE` failed at line 350 instead.

So recording inventory reviews is a **transition-free** operation.
`transition_history` and `transition_history_sha256` are read-only inputs. This
is coherent with the contract: transitions record *controlled state*
(disposition, delivery, gate, source, authority), and a review is proof about
that state, not a change to it. The 648 existing transition entries must be
byte-identical before and after every batch (§6.2 check 6).

**Do not reuse HR-0004's approval machinery.** No `approval_records`, no
`human_resolution_decision_id`, no `RECONCILE_AUTHORITY` resolution, no
human-review entry. §4 gives the contract citations.

### 3.6 The `DISP-R-1` carve-out — mandatory, and counter-intuitive

`DISP-R-1` is the one `REJECTED_ACCOUNTED` canonical row. The structural
validator pins its state as an **exact object manifest**
(`validate_ledger_structural.py:2674-2686`, `EXPECTED_DISP_R1_REQUIREMENT`) and
then asserts (`:2756-2763`):

```python
assert EXPECTED_DISP_R1_REQUIREMENT in disp_r1["required_evidence"]
disp_r1_proven, disp_r1_reasons = current_no_implementation_proof(disp_r1)
assert disp_r1_proven is False
assert {"REQUIREMENT_UNRESOLVED",
        "CURRENT_REVIEWER_ROLE_EVIDENCE_REVIEW_MISSING"} <= set(disp_r1_reasons)
```

Two consequences the recorder must encode:

1. `REQ-DISP-R-1-NO-IMPLEMENTATION` must remain `status=UNRESOLVED` with
   `evidence_ref_ids=[]`. **Verified** (§6.3, probe B): satisfying it — the
   obvious way to clear the last preimplementation blocker — fails structural
   validation at `:2756`, exit `1`.
2. `DISP-R-1`'s `EVIDENCE` review must **not** link
   `EV-DISP-R-1-SPEC-DRAFT`. `current_no_implementation_proof` computes
   `review_ok` partly as `set(historical) <= set(review["evidence_ref_ids"])`
   (`:2705-2718`). Linking the historical ref alongside a `COMPLETE`, CLEAN,
   digest-current review would set `review_ok = True`, removing
   `CURRENT_REVIEWER_ROLE_EVIDENCE_REVIEW_MISSING` from the reason codes and
   failing the `:2761-2763` assertion.

This is deliberate: r7 §3.6 requires this post-state to be *explicitly
unproven*. The recorder therefore hard-codes: `DISP-R-1` `EVIDENCE` review
links **only** `EV-DISP-R-1-INVREV-EVIDENCE`, and the recorder never touches
`required_evidence` on any row.

Consequence for the gate: see §3.9.

### 3.7 Ledger serialization — byte-exact writer contract

Verified by round-trip: re-serializing all 213 parsed rows with

```python
json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"
```

reproduces the canonical ledger **byte for byte** (SHA-256
`de236d7e8dcf02e307ec58797f5722ae2f85d1d8cdba57d4ecc07df5383c9c97`, matching
§1.1). `sort_keys=True` with default separators does **not**
(`d3202bee…`), nor does no-sort. The file has a trailing newline and zero blank
lines. The recorder must use exactly this form, so that every diff hunk is a
touched row and nothing else.

Note the writer's key ordering is *sorted*, which is also the order a new key
lands in — so adding `role`/`role_binding_path`/`role_binding_sha256` produces
no whole-object reordering churn.

### 3.8 Transaction safety — journaled, atomic, per batch

Adapted from r7 §6.2, scaled down to a single non-authority target. Per batch:

1. **Recovery check.** Any nonterminal journal under
   `scratchpad/inventory-reviews/journal/` stops the run with an explicit
   recovery notice naming the journal path, its state, and its unproven paths.
2. **Preconditions, before any write.**
   - `git status --short` — the dirty-path set outside the batch's targets must
     equal the recorded baseline exactly.
   - Ledger prehash equals the recorded prehash.
   - `sha256sum` of both validator scripts and `extract_goal_validators.py`
     equal §1.1 (drift means the digest contract may have changed).
   - `python3 scripts/equity_os_blueprint/extract_goal_validators.py --check`
     exits `0`.
   - Structural validator exits `0` on the current canonical ledger.
   - Projection-equivalence self-check (§6.2 check 1).
   - Every verdict artifact in the batch exists, is a regular file, parses, and
     carries `verdict: CLEAN`, role `REVIEWER`, a nonempty model and effort, a
     64-hex `role_binding_sha256`, and a timestamp `<= now`.
   - Every target row's three review slots are `PENDING` (idempotence guard: a
     row already `COMPLETE` is refused, never re-recorded).
   - Same-directory atomic-replacement probe inside the private staging
     directory (rename one probe over a second existing probe), never inside
     `docs/goals/`.
3. **Build in memory.** Apply Phase A then Phase B (§3.4) to a deep copy.
   Serialize per §3.7.
4. **Stage.** Write the candidate to a same-directory temp file with exclusive
   creation, set its mode to the target's recorded pre-state mode, `fsync` the
   file and directory. Every temp path is registered in a cleanup set unlinked
   on any non-`COMMITTED` exit via `try`/`finally`.
5. **Validate the candidate, not the target.** Run the structural validator
   with `--ledger-path <temp> --human-review-path <canonical>` (the validator
   requires both or neither) and require exit `0`; run the preimplementation
   validator with `--report-blockers --ledger-path <temp>` and require the
   monotonic-shrink property of §6.2 check 4.
6. **Journal.** Write and `fsync` a journal with batch ID, target path,
   pre/post hashes, pre-state mode, temp path, preimage path, the exact
   component/review-type list, validator exits, and state `PREPARED`.
7. **Replace.** Compare the live ledger to its recorded prehash, then
   same-directory atomic rename. Verify the replaced file's mode. Update and
   `fsync` the journal.
8. **Post-verify.** Rerun both validators on the canonical path; compare the
   canonical posthash to the prepared candidate hash; re-derive the dirty-path
   set and require only the ledger and the batch's verdict artifacts to differ
   from baseline. Only then mark and `fsync` `COMMITTED`.
9. **Rollback.** On any failure after replacement, restore the preimage by
   same-directory atomic rename, restore the exact pre-state mode, `fsync`,
   verify bytes **and** mode, mark `ROLLED_BACK`, exit nonzero. The replacement
   and post-replacement blocks are guarded at `BaseException` level (or by
   `SIGINT`/`SIGTERM` handlers routing into the same path) and re-raise after
   rollback, so `KeyboardInterrupt` cannot leave a mixed ledger.

Only one canonical path is ever written: the ledger. Verdict artifacts are
new files created *before* the transaction and are not transaction targets;
their digests are pinned in the batch manifest and re-verified at step 2.
`CONTEXT.md`, the goal, both validators, the extractor, the human-review
artifact, both pinned blueprint authorities, Beads/Dolt state, and the Git
index are never written. Because only one path is replaced, a single atomic
rename is the commit point — the journal exists for crash recovery and audit,
not to sequence multi-path renames.

### 3.9 What this tool does **not** clear

Recording all 447 reviews drives `pending_reviews` to `0` and `stale_reviews`
to `0`, but the preimplementation gate still exits `2` on exactly one blocker:

```json
{"component_id": "DISP-R-1", "requirement_id": "REQ-DISP-R-1-NO-IMPLEMENTATION",
 "historical_evidence_ref_ids": ["EV-DISP-R-1-SPEC-DRAFT"],
 "reason_codes": ["CURRENT_REVIEWER_ROLE_EVIDENCE_REVIEW_MISSING",
                  "HISTORICAL_REFS_UNCOVERED", "REQUIREMENT_UNRESOLVED"]}
```

**This blocker is unclearable by any ledger edit**, because
`validate_ledger_structural.py:2760` asserts it must remain unproven. Clearing
it requires amending the goal (removing/changing `EXPECTED_DISP_R1_REQUIREMENT`
and the `disp_r1_proven is False` assertion), which is an
`AUTHORITY_RECONCILIATION` under a fresh `RECONCILE_AUTHORITY` human resolution
— a separate, user-approved transaction with its own reviewed design. It is
explicitly **out of scope** for this tool, and the tool must never attempt it.

The end state of this workstream is therefore precisely:
**structural `0`, preimplementation `2` with exactly 1 blocker and 0 pending
and 0 stale reviews.** Any plan claiming this tool opens the preimplementation
gate is wrong.

---

## 4. Does recording reviews require fresh USER authority?

**No. Not for any of the 447 reviews.** Three independent citations:

1. **The lifecycle already assigns this work under the granted activation.**
   Goal L886-893 (Autonomous lifecycle step 1): "…run the structural
   validator; obtain clean content-bound `REVIEWER`-role inventory,
   scope-derivation, evidence-inventory, and approval-inventory reviews; then
   run the preimplementation validator." This is post-activation autonomous
   work, dispatched to the `REVIEWER` role, not a human gate.
2. **The contract states these reviews carry no authority — in both
   directions.** Goal L615-617: "Ordinary `REVIEWER`-role evidence/inventory
   review remains automated review; it is never an authority-bearing human
   resolution." Goal L624-626: "Neither this completeness review nor a
   `REVIEWER`-role approval grants any non-delegated authority." A review that
   grants nothing needs nothing granted to it.
3. **Delegated artifact approval (L957-976) is a different mechanism and is not
   invoked.** It covers approving "a spec, roadmap, or JIT plan" and is
   recorded as `DELEGATED_ARTIFACT_APPROVAL` requirements and
   `approval_records`. This tool writes **no** `approval_records`, touches
   **no** `required_approvals`, and creates **no** approval. It is not even a
   delegated approval, let alone a personal one.

The human-review boundary (L1001-1019) is for "the exact fact or authority an
agent cannot establish." Recomputing a SHA-256 over a projection of the ledger
is establishable by an agent; that is why both validators recompute it and
"matching ledger-authored values do not establish truth."

**Mechanical confirmation.** The `COMPLETE` review schema has no
`human_resolution_decision_id`, no `human_resolution_sha256`, no
`approval_record_id`, and no `authority` field — 13 keys exactly, none of which
can carry a human authorization. The contract makes user approval
*unrepresentable* here.

**Isolated exception.** The one part of this problem space that **does** need
fresh user authority is the `DISP-R-1` no-implementation blocker (§3.9): it
requires a goal amendment under an active `RECONCILE_AUTHORITY` human
resolution. That is cleanly separable — it is not a review recording, it is a
contract change, and this tool must not attempt it.

**Standing constraints that still apply.** No commit or push without explicit
authority (repo conservative profile). No `gpt-5.6` / Codex dispatch. Every
`REVIEWER` dispatch must be an independent agent and context from any
`IMPLEMENTER` that produced the reviewed content (goal L947-949, CONTEXT.md
L137-139).

---

## 5. Batching plan for 447 reviews

### 5.1 Hard constraints, derived not chosen

| Constraint | Source |
|---|---|
| A row's applicable reviews are completed **together, in one batch** | §3.4 ordering rule; verified probe C |
| Batches are **disjoint by row** | digest projections are row-local; no cross-row digest exists |
| One writer process at a time on the ledger | single-file compare-and-swap (§3.8); concurrency is in the *reviewers*, not the recorder |
| `DISP-R-1` gets the §3.6 carve-out | verified probes A/B |

Reviewers may run concurrently and freely — reviewing is read-only. Recording
is serialized. Nothing about a `REVIEWER` dispatch on row X depends on row Y.

### 5.2 Batch composition: by kind, then by spec

**Primary axis: kind.** The judgment a reviewer makes is kind-shaped. The
`SCOPE` rule is fixed by kind (goal L~262-278): `PROGRAM_WIDE_ACTIVE_CONTROL`
for `first_release_deferral`, `scale_trigger`, `authority_clause`,
`sequence_clause`, `document_strategy_clause`; `AUTHORITATIVE_OCCURRENCE` for
`disposition_item`; `RELATED_REGISTER_SCOPE` or `ACTIVE_NEGATIVE_CONTROL` for
`phase_gate_clause`. A reviewer holding one kind's rule in context reviews it
consistently; a mixed batch re-loads the rule per row.

**Secondary axis within `register_row`: owning spec.** The 60 register rows are
the only large kind whose `EVIDENCE`/`APPROVAL` inventories are spec-shaped
(each register ID has exactly one primary owner across S01…S25). Grouping them
by `primary_spec.spec_id` lets one reviewer hold one spec's acceptance text.

Row counts and reviews per owning spec (canonical rows; 73 canonical rows have
`primary_spec=null` and are program-wide controls):

| Spec | Rows | Reviews | | Spec | Rows | Reviews |
|---|---:|---:|---|---|---:|---:|
| S01 | 3 | 6 | | S14 | 8 | 21 |
| S02 | 4 | 10 | | S15 | 2 | 4 |
| S03 | 2 | 4 | | S16 | 2 | 4 |
| S04 | 3 | 8 | | S17 | 5 | 12 |
| S05 | 6 | 15 | | S18 | 7 | 17 |
| S06 | 3 | 7 | | S19 | 2 | 4 |
| S07 | 3 | 6 | | S20 | 4 | 9 |
| S08 | 5 | 12 | | S21 | 2 | 5 |
| S09 | 5 | 11 | | S22 | 1 | 2 |
| S10 | 8 | 22 | | S23 | 2 | 5 |
| S11 | 3 | 6 | | S24 | 2 | 5 |
| S12 | 5 | 11 | | S25 | 5 | 13 |
| S13 | 4 | 9 | | *(none)* | 73 | 219 |

**Proposed batch plan — 17 batches, 169 rows, 447 reviews:**

| # | Batch | Rows | Reviews |
|---:|---|---:|---:|
| 1 | `authority_clause` (all) | 4 | 12 |
| 2 | `document_strategy_clause` (all) | 6 | 18 |
| 3 | `scale_trigger` (all) | 8 | 24 |
| 4 | `sequence_clause` (all) | 11 | 33 |
| 5 | `first_release_deferral` (all) | 13 | 39 |
| 6–8 | `disposition_item`, 3 batches (~11 rows each); `DISP-R-1` isolated in its own batch | 32 | 96 |
| 9–11 | `phase_gate_clause`, 3 batches (~12 rows each) | 35 | 105 |
| 12–17 | `register_row`, 6 batches grouped by owning spec (~10 rows each) | 60 | 120 |
| | **Total** | **169** | **447** |

Ordering rationale: smallest and most homogeneous kinds first, so a mechanical
defect in the recorder surfaces on a 4-row batch, not a 35-row one. `DISP-R-1`
goes in its own batch because it is the only row with a carve-out and the only
row whose mishandling breaks the *structural* validator rather than merely the
preimplementation gate.

### 5.3 Per-batch verification

Every batch runs the full §6.2 postcondition set. The batch is not committed
unless all of it passes on the *candidate* first and the *canonical* file
after.

### 5.4 Recording a BLOCKED / non-clean verdict — without fabricating anything

**A non-clean review is not recordable as a review.** `verdict == "CLEAN"` is
asserted for every `COMPLETE` review (`validate_ledger_structural.py:337`), and
a `PENDING` review must have `verdict=null` (`:329-336`). There is no schema
slot for a negative verdict.

So when a `REVIEWER` dispatch returns a non-clean verdict on component `C`:

1. **The review object stays `PENDING`.** The recorder drops `C` from the batch
   entirely. It never writes a partial or "COMPLETE but not clean" object. The
   `PENDING` state *is* the correct, honest representation: the contract's
   completion predicate is unmet.
2. **The verdict artifact is still written and committed** at its durable path.
   It is the durable record of the finding, per the review policy (L977-1000
   item 3: "Persist every finding, severity, load-bearing classification,
   evidence, affected cone, fix, reviewer verdict, and round in review
   artifacts and the ledger. Conversation text is not evidence.").
3. **The finding goes to `open_findings`** on `C`, with severity, load-bearing
   status, artifact, evidence, and disposition (goal L~188 "Review and
   blocking"). `open_findings` is not a controlled field, so this too is
   transition-free; but it *is* inside `review_input_projection`, so it must be
   written in the same Phase-A window as any evidence for that row, and it
   stales any already-`COMPLETE` review on `C` — which is correct: a new
   finding on `C` should invalidate `C`'s prior clean reviews.
4. **`blocked_scope` / `delivery_status` blocking** — an unresolved
   load-bearing Critical or Important finding blocks the component and its
   dependent cone (L991-993). That is a **controlled-state** change
   (`blocked_scope`, `delivery_status`) and therefore **does** require a
   `BLOCK` transition entry with nonempty component-local evidence. This is
   outside `record_inventory_review.py`'s remit — it is a different tool with a
   different (transition-writing) safety envelope. This design deliberately
   does not specify it; recording a blocker is a separate bounded task.
5. **A human-review entry is created only if** the finding names a fact or
   authority an agent cannot establish (L1001-1019) — e.g. a register row
   requiring an approval type absent from the closed vocabulary (goal
   L~540-543). Then, and only then, an `HR-####` entry is added to the one
   canonical human-review artifact and the component links it via a
   `REFERENCE_APPEND` transition. Again: a separate tool, separate task.
6. **Fix rounds** follow the review policy: at most `r0`…`r4`, then a fresh
   `REVIEWER`-role adjudicator (L977-1000 items 2 and 4). The verdict artifact
   filename carries the round (`SCOPE-r1.md`), and each round is a new evidence
   object; the *completing* round's artifact is what the ledger review links.

Nothing is fabricated at any step: a review that did not come back clean is
represented by a `PENDING` review, a persisted artifact, and a recorded
finding.

---

## 6. Candidate proofs and postconditions

### 6.1 Pre-state proof commands

```bash
cd /data/codes/equity-os
sha256sum docs/goals/equity-os-blueprint-completion.md \
  docs/goals/equity-os-blueprint-component-ledger.jsonl \
  docs/goals/equity-os-blueprint-human-review-needed.md \
  scripts/equity_os_blueprint/validate_ledger_structural.py \
  scripts/equity_os_blueprint/validate_ledger_preimplementation.py \
  scripts/equity_os_blueprint/extract_goal_validators.py \
  CONTEXT.md
git status --short --branch
python3 scripts/equity_os_blueprint/extract_goal_validators.py --check; echo "extract=$?"
python3 scripts/equity_os_blueprint/validate_ledger_structural.py --repo-root .; echo "structural=$?"
python3 scripts/equity_os_blueprint/validate_ledger_preimplementation.py \
  --repo-root . --report-blockers > /tmp/blockers.json; echo "preimpl=$?"
```

Expected at the §1.1 bytes: hashes as tabulated, `extract=0`, `structural=0`,
`preimpl=2` with 447 pending / 0 stale / 1 no-implementation.

### 6.2 Per-batch postconditions (all must hold)

Let `B` be the batch, `R(B)` its (component, review type) pairs.

1. **Projection equivalence.** The recorder's transcribed
   `review_input_projection` / `review_inventory_projection` /
   `canonical_sha256` produce, for a sample of ≥5 untouched rows spanning ≥3
   kinds, digests identical to those obtained by importing the same functions
   from the checked-in `validate_ledger_structural.py`. Any drift aborts before
   any write.
2. **Structural = 0** on the candidate, then on the canonical file:
   `python3 scripts/equity_os_blueprint/validate_ledger_structural.py --repo-root . [--ledger-path <candidate> --human-review-path docs/goals/equity-os-blueprint-human-review-needed.md]`
3. **Pending shrinks by exactly `|R(B)|`**, and by no more:
   `pending_after == pending_before - |R(B)|`.
4. **Monotone shrink, never growth:** `pending_after < pending_before`,
   `stale_after == 0`, and `unmet_no_implementation_proof` unchanged at
   exactly 1 (`DISP-R-1`). Any `stale_reviews` entry is a hard failure — it
   means the ordering rule of §3.4 was violated.
5. **Alias rows untouched.** All 44 `derivative_alias` rows are byte-identical
   before and after; their three review slots remain `null`.
6. **Transitions untouched.** Total transition-entry count stays 648; every
   row's `transition_history` and `transition_history_sha256` are
   byte-identical before and after.
7. **Diff shape.** `git diff --stat` shows exactly one modified tracked file
   (the ledger) plus `|B|`-worth of new untracked verdict artifacts. No change
   to the goal, either validator, the extractor, the human-review artifact,
   `CONTEXT.md`, or either pinned blueprint authority — assert by re-running
   the §6.1 `sha256sum` and requiring every hash except the ledger's to be
   unchanged.
8. **Row locality.** Every ledger line whose `component_id` is not in `B` is
   byte-identical to its pre-state line.
9. **Idempotence guard.** Re-running the same batch aborts at preconditions
   (`review status != PENDING`), never double-records.
10. **`git diff --check`** clean.

### 6.3 Executed candidate proofs (this design round)

All probes ran against the §1.1 bytes, writing only under
`scratchpad/inventory-reviews/`. No canonical file was modified (§7 restates
`git status`).

| Probe | What it demonstrates | Result |
|---|---|---|
| **A. 6-row sample** — `REG-A-01`, `DISP-G-1`, `SEQ-01`, `PG-2-04`, `DISP-R-1`, `ALIAS-001`; Phase A/B ordering; `DISP-R-1` carve-out applied | The recording mechanics are legal | structural **0**; preimpl pending **447 → 433** (exactly 14 = 2+3+3+3+3), stale **0**, alias untouched |
| **B. Full 447 + satisfy `REQ-DISP-R-1-NO-IMPLEMENTATION`** | The "obvious" gate-clearing move is forbidden | preimpl `--report-blockers` **ready=true**, pending 0/stale 0/noimpl 0 — but **structural fails**, `AssertionError` at `validate_ledger_structural.py:2756`, exit **1** |
| **B′. Full 447 with the §3.6 carve-out** | The correct end state | structural **0**; preimpl pending **0**, stale **0**, noimpl **1** (`DISP-R-1`), exit **2**; preimpl assert-mode also exits 2 on that row |
| **C. Per-type append-and-digest on `SEQ-02`** | The §3.4 ordering rule is load-bearing | `AssertionError` at `validate_ledger_structural.py:350` (`reviewed_input_sha256`), exit **1** |
| **D. `REFERENCE_APPEND` transition with `field="evidence_inventory_review"` on a `PENDING` row** | A transition entry for a review field is rejected outright | `AssertionError` at `validate_ledger_structural.py:1909` (`field in controlled_fields`), exit **1** |
| **E. Same entry on a row whose reviews are `COMPLETE`** | A transition also stales the row's reviews via `transition_history_sha256` | `AssertionError` at `validate_ledger_structural.py:350`, exit **1** |
| **F. Serialization round-trip** | The §3.7 writer contract | `sort_keys=True, ensure_ascii=False, separators=(",",":")` reproduces the canonical ledger byte-for-byte (`de236d7e…`); the two alternatives produce `d3202bee…` |

Probe B′ is the decisive one: **completing all 447 reviews correctly yields
structural 0 / preimplementation 2-with-1-blocker**, exactly as §3.9 predicts.

### 6.4 Terminal postconditions for the whole workstream

- 447 review objects `COMPLETE`, each 13 keys, `verdict=CLEAN`, `role=REVIEWER`,
  `role_binding_path=CONTEXT.md`.
- 447 new `evidence_refs` objects, `FILE_BYTES`, globally unique IDs, each
  resolving to an existing durable verdict artifact.
- 447 verdict artifacts under `docs/goals/reviews/ledger/inventory/`.
- `evidence_refs` length distribution moves 1/2/5 → 3/4/7 on non-register rows
  and 1/2/5 → 2/3/6 on register rows.
- 44 aliases, 648 transition entries, `required_evidence`, `required_approvals`,
  `approval_records`, `program_disposition`, `delivery_status`, `gate_result`,
  `source_status`, and all source coordinates: **unchanged**.
- structural `0`; preimplementation `2` with `pending_reviews=0`,
  `stale_reviews=0`, `unmet_no_implementation_proof=1`.
- No commit or push without explicit user authority.

---

## 7. Risks and open questions

**Stated honestly; none of these are resolved by this document.**

1. **The preimplementation gate does not open.** §3.9. This is the single most
   important finding here and it contradicts the natural reading of the task
   framing. Completing 447 reviews is necessary and not sufficient; `DISP-R-1`
   needs a goal amendment under fresh user authority. If the real objective was
   "open the preimplementation gate", this workstream must be paired with a
   separate `RECONCILE_AUTHORITY` design.

2. **447 genuine reviews is the real cost, and it is large.** The recorder is
   the easy half. The hard half is 447 `REVIEWER`-role dispatches that actually
   read the pinned register/disposition source for each component and form a
   defensible judgment. At CONTEXT.md's `REVIEWER` binding (Claude Opus 5,
   high effort) this is a multi-session program. Any plan that batches reviews
   so coarsely that one dispatch "reviews" 30 components with one paragraph
   each is manufacturing clean verdicts, and the ledger will record them as
   indistinguishable from real ones. **The validators cannot detect a lazy
   review — only its digests.** This is the largest integrity risk in the whole
   workstream and I have no mechanical mitigation to offer; it is a dispatch
   discipline problem.

3. **`required_authority` for `DELEGATED_ARTIFACT_APPROVAL` contains vendor
   lane tokens.** All 123 such requirements carry
   `"Delegated fresh Sol xhigh specification reviewer"`. The goal's lane-token
   check (`extract_goal_validators.check_lane_tokens`) scans the *goal
   document* only, so the ledger is not currently failing — but this string
   contradicts CONTEXT.md L141 ("never hard-coded model or vendor names") and
   the standing project sub-agent policy. r7 §7 defers this to `TERM-0001`
   (filed as `eqos-sky`). Every `APPROVAL` reviewer will encounter it.
   **Open question: does an `APPROVAL` review that observes this string return
   `CLEAN`?** My reading is yes — the string is the *pinned current* authority
   literal, the inventory is complete and correct against it, and the
   structural validator's one-string-per-authority invariant holds. But this
   should be settled *before* batch 12, not litigated per-row. Changing it is
   an atomic 123-row migration plus a stale-review cascade, out of scope here.
   *NOTICED BUT NOT TOUCHING.*

4. **`role_binding_sha256` drift across a long program.** The digest is an
   immutable historical capture and is deliberately never re-verified, so an
   unrelated `CONTEXT.md` edit mid-program leaves batches 1–8 bound to one
   digest and 9–17 to another. That is contract-legal and intended, but it will
   look like an inconsistency in audit. Recommend: capture the digest per batch
   and record which batches carry which, rather than assuming one value.

5. **447 new evidence objects triple the structural validator's file-hashing
   work.** Every run re-reads and re-hashes every declared evidence target.
   Current: 490 evidence objects across 213 rows. After: 937. Runtime should be
   measured on batch 1 and reported; if it degrades badly, batch count may need
   revisiting. I did not measure it.

6. **Verdict artifacts are themselves mutable targets.** Once linked, editing a
   verdict artifact's bytes breaks its `content_sha256` and fails structural
   validation ledger-wide — not just for that row. 447 files that must never be
   touched again (including by a linter, formatter, or trailing-whitespace
   hook) is a real operational hazard. Recommend an explicit note in the
   directory and, if the repo has pre-commit hooks touching Markdown, an
   exclusion.

7. **Ordering interaction with any other ledger work.** Any concurrent tool
   that mutates a row's controlled state, findings, evidence, or transitions
   stales that row's completed reviews. The 447-review program should hold an
   exclusive claim on the ledger for its duration, or accept re-review cost.

8. **`review_round`.** It is in `review_input_projection` but is not a
   controlled field. This design leaves it at its current value (`0` on the
   rows inspected) and does not bump it, because bumping it would stale reviews
   for no contract-required reason. If the review-policy round counter is meant
   to track these per-component reviews, that is an unresolved question I am
   flagging rather than deciding.

9. **Scale of the untested surface.** Probes A–F cover the mechanics
   end-to-end at full 447-row scale, but with synthetic single-line verdict
   artifacts and one reviewer identity. The recorder's manifest parsing,
   journal/rollback path, `SIGINT` guard, and precondition set are **specified
   here and not yet implemented or tested**. This is a design document; nothing
   in §3.8 has been executed.

---

## 8. Summary of contract answers

| Question | Answer | Citation |
|---|---|---|
| Which reviews apply per kind? | `EVIDENCE`+`APPROVAL` on all 169 canonical; `SCOPE` additionally on the 109 non-register; none on 44 aliases | `validate_ledger_preimplementation.py:200-204`; goal L233-236, L379 |
| Exact counts? | 109 / 169 / 169 = **447** | freshly computed; blocker report |
| What is a "clean `REVIEWER`-role review"? | `verdict == "CLEAN"` (only legal value), `role == "REVIEWER"`, `role_binding_path == "CONTEXT.md"`, 64-hex binding digest, nonempty actually-invoked model/effort | `validate_ledger_structural.py:250-262, 337` |
| Which transition type for review completion? | **None.** Transition entries for review/evidence fields are rejected, and any transition stales the row's reviews | `:1732-1743, :1909`; probes D, E |
| Fresh user authority required? | **No** — for any of the 447 | goal L615-617, L624-626, L886-893, L957-976 |
| Does this open the preimplementation gate? | **No** — 1 permanent `DISP-R-1` blocker remains, needing a separate goal amendment | `:2756-2763`; probes B, B′ |
