# Inventory-review recording design — r1

**Role:** `IMPLEMENTER` (CONTEXT.md "Agent roles (harness-wide)").
**Scope:** design only. This document changes no canonical file. It specifies
how the 447 `PENDING` content-bound inventory reviews on the canonical ledger
become `COMPLETE` under the active goal contract.

**Style/discipline reference:** `docs/goals/reviews/ledger/equity-os-blueprint-ledger-remediation-design-r7.md`
(pre-state hashes, exact mechanical rules, candidate proofs, transaction
safety). This design deliberately does **not** reuse r7's approval machinery —
§4 shows why no approval machinery applies here at all.

## 0. Supersession and round lineage

**This r1 supersedes r0 in full.** The operational design of
`docs/goals/reviews/ledger/equity-os-blueprint-inventory-review-recording-design-r0.md`
(SHA-256 `5ec10de959d56145c00d186924c01c2d8cc3af5c488a78e4aadf5afbefcd7dea`) is
superseded; r0 is retained only as round lineage and must not be executed
against.

**Correcting authority.** The sole authority for the r0→r1 delta is the
independent review
`docs/goals/reviews/ledger/equity-os-blueprint-inventory-review-recording-design-r0-review-r0.md`
(SHA-256 `91b0ce64d70fabc4acb33344281efd162af816fc47c8f6de0eeacfc079e7a462`),
role `REVIEWER`, verdict **CLEAN**, 0 Critical / 0 Important / 10 Minor. r1
changes exactly what those ten findings require, plus this supersession and
header plumbing. Nothing else is reworded: every unflagged section is
byte-identical to r0 so that r1 can be reviewed differentially.

**Predetermined next independent review path:**
`docs/goals/reviews/ledger/equity-os-blueprint-inventory-review-recording-design-r1-review-r0.md`
(round `r0` of the r1 artifact; review-round ceiling per goal L982-1000). That
review must be an independent `REVIEWER`-role agent and context, distinct from
this `IMPLEMENTER` dispatch and from the r0 reviewer (goal L947-949,
CONTEXT.md L137-139).

### 0.1 Disposition of the ten r0-review Minor findings

Every number below was recomputed in this round against the §1.1 bytes; none
is transcribed from the review.

| # | r0-review finding | Disposition | Where |
|---:|---|---|---|
| M-1 | §7.5 evidence-object counts wrong (490→937) | **Fixed.** Recomputed independently: **405 → 852** (×2.10). Reviewer's figures confirmed. | §7.5 |
| M-2 | §6.4 `evidence_refs` distribution wrong in deltas and row classes | **Fixed.** Recomputed: non-register **1/2/5 → 4/5/8**; register **2/5 → 4/7**; aliases unchanged at 1. Postcondition §6.2 check 11 now asserts the measured per-class shift. | §6.2, §6.4 |
| M-3 | §6.2 check 1 self-contradictory and mechanically impossible | **Fixed by specifying the mechanism.** Check 1 is retained and made executable via `ast`-extraction + `exec` in an isolated namespace — no import. Probe G executes it. | §6.2, §6.3 |
| M-4 | §3.8 step 2 "three review slots" impossible for register rows | **Fixed.** Now "applicable review slots", with the applicability rule restated. | §3.8 |
| M-5 | Three imprecise goal citations in §1.2 | **Fixed.** L233-236 → **L208-211**; L379 → **L495-496**; L452-453 → **L280**. L623-624 retained (correct). | §1.2 |
| M-6 | §5.2 batch rows 6–8 arithmetic (DISP-R-1 is one of the 32) | **Fixed.** Now 4 disposition batches: `DISP-R-1` alone + 3 × ~10–11 rows over the remaining 31. Batch count 17 → **18**. | §5.2 |
| M-7 | Per-spec table sits under the register-row axis but tabulates 96 spec-owning rows | **Fixed.** The 96-row table is relabelled and moved to a standalone ownership-context subsection (§5.2a); a new **register-only** per-spec table (60 rows / 120 reviews) is what sizes batches 13–18. | §5.2, §5.2a |
| M-8 | Dangling §6.3→§7 cross-reference | **Fixed.** §6.3 now states the observed `git status` inline; the dangling pointer is removed. | §6.3 |
| M-9 | Four transaction-hardening gaps vs r7 §6.2 | **Closed, not waived.** (a) exclusive repo-local lock; (b) symlink/non-regular ledger-target rejection; (c) `RECOVERY_REQUIRED` terminal journal state; (d) **mandatory** rollback rehearsal on a disposable full-tree replica with four named legs and a machine-checkable proof object asserted before the first real write. | §3.8, §3.10 |
| M-10 | 447 `model` values naming a vendor model unaddressed | **Fixed.** §7.3 now states explicitly that this is contract-required historical invocation record, not `TERM-0001`-scope obligation drift, with validator citations. | §7.3 |

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
`scope_derivation.semantic_review = null` (goal **L208-211**, "For a
`register_row`, `scope_derivation.rule` is `REGISTER_STATUS`, its
`related_register_ids` is empty, its `authority_effect` and `semantic_review`
are `null`" — mechanized at goal L2886
`assert derivation["semantic_review"] is None`), and for an alias all three
review slots are `null` (goal **L495-496** `evidence_inventory_review=null`,
goal **L280** `scope_derivation=null` — which removes the `SCOPE` slot
entirely — and goal **L623-624** `approval_inventory_review=null`).

*(r1 citation correction, r0-review M-5: r0 cited L233-236, L379, and
L452-453. L233-236 is `scope_derivation` array hygiene, L377-381 is
`REJECTED_PROPOSAL` approval records, and L450-455 is the `evidence_refs`
schema. Each line range above was re-read in this round. The non-register
`semantic_review` rule — cited correctly elsewhere as "L~262-278" — is at
L274-280. The claims themselves were unchanged and independently verified.)*

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
- `evidence_refs` list lengths today: 1 (90 rows), 2 (100 rows), 5 (23 rows) —
  **405 evidence objects in total** (90×1 + 100×2 + 23×5). Broken out by the
  row classes that matter for the post-state (§6.4): non-register canonical
  109 rows at 1 (46) / 2 (48) / 5 (15); register 60 rows at 2 (52) / 5 (8) —
  **no register row has length 1**; aliases 44 rows all at 1.
- `required_evidence` items total 354 across the 213 rows. This is a *separate*
  list from `evidence_refs` and is never added to it by this tool.
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

**How the reference implementation is obtained — `ast` extraction, never
import** *(r1, r0-review M-3)*. The structural validator is **not importable**:
it is straight-line with a module-level `parser.parse_args()` at
`validate_ledger_structural.py:18-25` and **no `if __name__ == "__main__"`
guard**, so `import` would consume the recorder's own `sys.argv` and execute an
entire validation run as an import side effect. §3.1's "must never import from
the validator scripts" therefore stands unchanged; r0's §6.2 check 1 wording
("by importing the same functions") was both self-contradictory and mechanically
impossible, and is replaced by this mechanism:

```python
import ast, hashlib, json, re

SRC = "scripts/equity_os_blueprint/validate_ledger_structural.py"
WANTED = ("canonical_sha256", "normalized_human_review_id",
          "review_input_projection", "review_inventory_projection")

source = REPO_ROOT.joinpath(SRC).read_text(encoding="utf-8")
tree = ast.parse(source)
picked = {n.name: n for n in tree.body
          if isinstance(n, ast.FunctionDef) and n.name in WANTED}
assert set(picked) == set(WANTED)            # abort if the validator moved them
module = ast.Module(body=[picked[n] for n in WANTED], type_ignores=[])
ast.fix_missing_locations(module)
reference = {"hashlib": hashlib, "json": json, "re": re}
exec(compile(module, SRC, "exec"), reference)
```

Why this is safe and sufficient:

- Only four top-level `FunctionDef` nodes are compiled. No module-level
  statement of the validator — including `parse_args()`, the row load, and
  every top-level `assert` — is in the compiled body, so nothing executes as a
  side effect and `sys.argv` is untouched.
- The isolated namespace is seeded with exactly the three stdlib modules those
  four functions close over (`hashlib`, `json`, `re`). Any further free name
  raises `NameError` at call time rather than silently binding to a recorder
  global — a loud failure, before any write.
- `normalized_human_review_id` is included because `review_input_projection`
  and the `APPROVAL` inventory projection both call it; extracting the two
  projections alone would `NameError`.
- The `assert set(picked) == set(WANTED)` line is itself a drift tripwire: if a
  future validator renames, nests, or deletes one of the four, the recorder
  aborts at preconditions instead of digesting against a stale transcription.
- This reads the checked-in validator's **current bytes**, which §3.8 step 2
  has already pinned to the §1.1 hash. It is a comparison source only; the
  recorder still writes digests from its own transcribed copies, so a
  transcription error is caught by the check rather than papered over by it.

Executed end-to-end this round: §6.3 probe **G**.

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

1. **Lock, then recovery check.** *(r1, r0-review M-9a.)* Acquire an
   **exclusive repository-local transaction lock** before anything else:
   `open(scratchpad/inventory-reviews/lock, "x")` — exclusive creation, never
   `O_TRUNC` — holding the PID, batch ID, and start time, released in the same
   `try`/`finally` that owns the temp-file cleanup set. A pre-existing lock
   aborts the run naming the holder. This closes r7 §6.2 step 1's requirement
   and narrows — it does not eliminate — the window between the step-7 prehash
   comparison and the rename; the compare-and-swap remains the correctness
   guarantee, the lock removes the concurrent-recorder case that would make
   that window reachable in practice. Per r7 §6.2, the durable guard against
   re-mutation is the nonterminal journal, **not** a process-held lock: the
   design does not claim the lock survives process exit, and a stale lock is
   cleared only by an operator who has first read the journal state.
   Then run the recovery check: any nonterminal journal under
   `scratchpad/inventory-reviews/journal/` stops the run with an explicit
   recovery notice naming the journal path, its state, and its unproven paths.
2. **Preconditions, before any write.**
   - **Rollback-rehearsal proof object present and valid** (§3.10). Asserted
     before the first real write of the program.
   - **Ledger target shape.** `os.lstat` the canonical ledger path and require
     a **regular file**: reject a symlink, directory, FIFO, device, or hardlink
     count > 1, and require that the resolved path equals the canonical path.
     *(r1, r0-review M-9b: r0 applied the regular-file check only to verdict
     artifacts. A symlinked ledger would make the same-directory atomic rename
     replace the link rather than the file, silently detaching the canonical
     path from the validated bytes.)* Record the target's exact filesystem mode
     here; steps 4, 7, and 9 all compare against this value.
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
   - Every target row's **applicable** review slots are `PENDING` (idempotence
     guard: a row already `COMPLETE` is refused, never re-recorded).
     *(r1, r0-review M-4.)* "Applicable" is the §1.2 rule, not a count: a
     non-register canonical row has **three** applicable slots
     (`scope_derivation.semantic_review`, `evidence_inventory_review`,
     `approval_inventory_review`); a `register_row` has **two**, because
     `scope_derivation.semantic_review` is contractually `null` (goal L208-211)
     and must stay `null`; an alias has **none** and is never a batch target.
     The recorder derives the applicable set from `row["kind"]` exactly as
     `validate_ledger_preimplementation.py:200-204` does, and additionally
     asserts that a register row's `semantic_review` **is** `null` — r0's
     literal "three review slots" precondition would have rejected all 60
     register rows in the register batches.
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
   **A rollback may be reported as proven only when both bytes and mode match
   the preimage.**
10. **`RECOVERY_REQUIRED`.** *(r1, r0-review M-9c: r0 named only `PREPARED`,
   `COMMITTED`, `ROLLED_BACK` and had no state for a rollback that fails.)* If
   step 9 cannot prove **both** the preimage bytes and the pre-state mode, the
   recorder writes and `fsync`s journal state `RECOVERY_REQUIRED` carrying the
   exact unproven path, the expected and observed SHA-256, the expected and
   observed mode, the surviving preimage and temp paths, and the batch's
   component/review-type list; then stops **all** ledger mutation and exits
   nonzero with that notice. `RECOVERY_REQUIRED` is terminal-for-the-tool but
   **nonterminal for the recovery check in step 1**, so every subsequent
   invocation refuses to run until an operator resolves it — the same durable
   guard r7 §6.2 relies on. The full journal state set is therefore
   `PREPARED` → {`COMMITTED`, `ROLLED_BACK`, `RECOVERY_REQUIRED`}, of which
   only `COMMITTED` and `ROLLED_BACK` are terminal.

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

### 3.10 Mandatory rollback rehearsal — before the first real batch

*(r1, new section, r0-review M-9d. r7 §6.2 requires this precisely because the
rollback path has never been executed, and §7.9 concedes this design's
journal / rollback / interrupt path is specified and untested. It is **not**
waived here.)*

**Rule.** `record_inventory_review.py` **refuses to perform its first real
write** until a valid rehearsal proof object exists at
`scratchpad/inventory-reviews/rehearsal/proof.json`. This is a step-2
precondition, checked before batch 1 and re-checked on every later batch.

**Where.** A **disposable full-tree replica** of the repository at the exact
§1.1 pre-state bytes, on the same filesystem, outside the working tree —
created by `git worktree add` at the pre-state commit plus a copy of any dirty
canonical bytes, or by a plain full-tree copy. The rehearsal **never** runs
against the canonical tree, and the replica is deleted after its proof is
written. The rehearsal batch is a real batch definition (batch 1's rows) with
synthetic verdict artifacts inside the replica.

**Four named legs, all required.**

| Leg | Injection | Required outcome |
|---|---|---|
| **L1 — forward baseline** | none | Batch commits: journal `COMMITTED`, replica ledger posthash equals the prepared candidate hash, structural `0`, preimplementation pending shrinks by exactly `\|R(B)\|`, no temp file survives, lock released |
| **L2 — forced-failure rollback** | fault injected **after** the rename and **before** `COMMITTED` (a post-verify hook forced to raise) | Journal `ROLLED_BACK`; replica ledger bytes **and** mode identical to preimage; no temp file survives; exit nonzero; lock released |
| **L3 — `SIGINT` during replacement** | `SIGINT` delivered inside the replacement block | Same as L2, and the process re-raises `KeyboardInterrupt` after rollback completes |
| **L4 — `SIGTERM` during replacement** | `SIGTERM` delivered inside the replacement block | Same as L2, via the `SIGTERM` handler routing into the identical rollback path |

L1 exists so that L2–L4's "restored to pre-state" is distinguishable from
"never wrote anything": the rehearsal must first demonstrate that the same code
path *does* mutate the replica.

**Machine-checkable proof object.** Written once, by the rehearsal harness, and
asserted by the recorder:

```json
{
  "schema": "inventory-review-rollback-rehearsal/v1",
  "recorder_sha256": "<sha256 of record_inventory_review.py as rehearsed>",
  "structural_validator_sha256": "731d0d8b…",
  "preimplementation_validator_sha256": "f7a225a1…",
  "ledger_prestate_sha256": "de236d7e…",
  "replica_root": "<absolute path of the disposable replica, since deleted>",
  "completed_at": "<UTC RFC3339>",
  "legs": {
    "L1_forward_baseline": {"passed": true, "journal_state": "COMMITTED",
      "ledger_changed": true, "structural_exit": 0, "temp_files_surviving": 0,
      "lock_released": true},
    "L2_forced_failure":  {"passed": true, "journal_state": "ROLLED_BACK",
      "bytes_match_preimage": true, "mode_match_preimage": true,
      "temp_files_surviving": 0, "exit_code": 1, "lock_released": true},
    "L3_sigint":          {"passed": true, "journal_state": "ROLLED_BACK",
      "bytes_match_preimage": true, "mode_match_preimage": true,
      "reraised": "KeyboardInterrupt", "temp_files_surviving": 0,
      "lock_released": true},
    "L4_sigterm":         {"passed": true, "journal_state": "ROLLED_BACK",
      "bytes_match_preimage": true, "mode_match_preimage": true,
      "reraised": "SystemExit", "temp_files_surviving": 0,
      "lock_released": true}
  },
  "transcript_path": "scratchpad/inventory-reviews/rehearsal/transcript.txt",
  "transcript_sha256": "<sha256 of that transcript>"
}
```

**What the recorder asserts at step 2** — all of it, or abort:

1. The file exists, parses, and `schema == "inventory-review-rollback-rehearsal/v1"`.
2. All four legs present, each `"passed": true`, with the exact
   `journal_state` shown above and `temp_files_surviving == 0`.
3. L2/L3/L4 each carry `bytes_match_preimage` **and** `mode_match_preimage`
   true — mode alone or bytes alone is a failed rehearsal.
4. `recorder_sha256` equals the SHA-256 of the recorder **about to run**. Any
   edit to the recorder — including a one-line fix between batches —
   **invalidates the rehearsal and requires a fresh one.** This is the clause
   that keeps the rehearsal honest across an 18-batch program.
5. The three pinned hashes equal §1.1. A validator or ledger-pre-state change
   invalidates the rehearsal.
6. `transcript_sha256` matches the transcript's current bytes, and the
   transcript is a regular file.

The rehearsal transcript and proof object are part of this workstream's
evidence bundle. They are **not** ledger evidence objects: they live under
gitignored `scratchpad/` and are never linked from `evidence_refs`, so §2.2's
durable-path rule is untouched.

**Status:** the rehearsal is specified here and **has not been performed** —
`record_inventory_review.py` does not yet exist. §7.9 records this honestly.
The rehearsal is a gate on the first real write, not on this design.

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

**Register-only spec distribution — this is the table that sizes the register
batches.** *(r1, r0-review M-7. Each register row carries exactly 2 reviews;
`register_row` has no `SCOPE` slot.)*

| Spec | Reg. rows | Reviews | | Spec | Reg. rows | Reviews |
|---|---:|---:|---|---|---:|---:|
| S01 | 3 | 6 | | S14 | 3 | 6 |
| S02 | 2 | 4 | | S15 | 2 | 4 |
| S03 | 2 | 4 | | S16 | 2 | 4 |
| S04 | 1 | 2 | | S17 | 3 | 6 |
| S05 | 3 | 6 | | S18 | 4 | 8 |
| S06 | 2 | 4 | | S19 | 2 | 4 |
| S07 | 3 | 6 | | S20 | 3 | 6 |
| S08 | 3 | 6 | | S21 | 1 | 2 |
| S09 | 4 | 8 | | S22 | 1 | 2 |
| S10 | 2 | 4 | | S23 | 1 | 2 |
| S11 | 3 | 6 | | S24 | 1 | 2 |
| S12 | 4 | 8 | | S25 | 2 | 4 |
| S13 | 3 | 6 | | **Total** | **60** | **120** |

All 25 specs own at least one register row, so batches 13–18 are formed by
partitioning **this** table's spec list contiguously — never the §5.2a
ownership table below. No contiguous six-way split gives exactly 10 rows each;
the stated split is:

| Batch | Specs | Reg. rows | Reviews |
|---:|---|---:|---:|
| 13 | S01–S04 | 8 | 16 |
| 14 | S05–S08 | 11 | 22 |
| 15 | S09–S11 | 9 | 18 |
| 16 | S12–S14 | 10 | 20 |
| 17 | S15–S18 | 11 | 22 |
| 18 | S19–S25 | 11 | 22 |
| | **Total** | **60** | **120** |

**Proposed batch plan — 18 batches, 169 rows, 447 reviews** *(r1, r0-review
M-6: r0 said "3 batches (~11 rows each)" for `disposition_item` while also
isolating `DISP-R-1`. `DISP-R-1` **is** one of the 32 `disposition_item` rows —
verified this round — so isolating it leaves **31** rows, not 32. Corrected to
four disposition batches; total batch count 17 → 18 and all later batch numbers
shift by one.)*:

| # | Batch | Rows | Reviews |
|---:|---|---:|---:|
| 1 | `authority_clause` (all) | 4 | 12 |
| 2 | `document_strategy_clause` (all) | 6 | 18 |
| 3 | `scale_trigger` (all) | 8 | 24 |
| 4 | `sequence_clause` (all) | 11 | 33 |
| 5 | `first_release_deferral` (all) | 13 | 39 |
| 6 | `disposition_item` — `DISP-R-1` alone (§3.6 carve-out) | 1 | 3 |
| 7–9 | `disposition_item` — remaining 31 rows, 3 batches (11 / 10 / 10) | 31 | 93 |
| 10–12 | `phase_gate_clause`, 3 batches (12 / 12 / 11) | 35 | 105 |
| 13–18 | `register_row`, 6 batches grouped by owning spec (8 / 11 / 9 / 10 / 11 / 11) | 60 | 120 |
| | **Total** | **169** | **447** |

Arithmetic check: 4+6+8+11+13+1+31+35+60 = **169** rows;
12+18+24+33+39+3+93+105+120 = **447** reviews. Both match §1.2.

Ordering rationale: smallest and most homogeneous kinds first, so a mechanical
defect in the recorder surfaces on a 4-row batch, not a 35-row one. `DISP-R-1`
goes in its own batch because it is the only row with a carve-out and the only
row whose mishandling breaks the *structural* validator rather than merely the
preimplementation gate. Placing it at batch 6 — after five clean kind batches
have exercised the recorder, and before the bulk work — means the carve-out is
proven on the canonical ledger early, on a single row.

### 5.2a Spec-ownership context — **not** a batch-sizing table

*(r1, relocated and relabelled per r0-review M-7. In r0 this table sat directly
under the "Secondary axis within `register_row`" heading, where its counts read
as register-row counts. They are not.)*

This table covers **all 96 spec-owning canonical rows**, of which **60 are
`register_row` and 36 are not** (measured this round: 16 `disposition_item`,
12 `first_release_deferral`, 8 `scale_trigger`). The remaining 73 canonical
rows have `primary_spec=null` and are program-wide controls. Sizing the
register batches from this table would pull non-register kinds into them and
contradict the batch table above — e.g. S10 shows 8 rows here but owns only
**2** register rows (its other 6 are 4 `scale_trigger`, 1
`first_release_deferral`, 1 `disposition_item`).

Its purpose is orientation for a reviewer holding one spec's acceptance text
across *all* its owned rows, whichever batch each row lands in.

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

Reproduced this round row for row; 228 spec-owned reviews + 219 null-spec
reviews = **447**.

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

1. **Projection equivalence.** *(r1, rewritten per r0-review M-3. r0 said "by
   importing the same functions", which contradicted §3.1's no-import rule and
   is impossible against a validator with module-level `parse_args()` and no
   `__main__` guard.)* The recorder's transcribed `review_input_projection` /
   `review_inventory_projection` / `canonical_sha256` must produce digests
   identical to the reference copies **`ast`-extracted and `exec`-ed from the
   checked-in `validate_ledger_structural.py` per §3.3** — no import, no
   module-level side effect, isolated namespace seeded with `hashlib`, `json`,
   `re` only. Compared over a sample of ≥5 untouched rows spanning ≥3 kinds and
   covering all three `review_type` values, plus every row in the current
   batch. Any drift, and any failure of §3.3's
   `assert set(picked) == set(WANTED)` tripwire, aborts before any write.
   Executed this round as probe **G**.

   This check is retained rather than dropped in favour of §3.8 step 5. Step 5
   is the definitive backstop — the real validator rejects a mis-transcribed
   digest at `:350`/`:353` before the rename, so no invalid record can commit —
   but it fails *late*, after a full candidate build and two validator runs, and
   with a bare `AssertionError` that does not say which of the three functions
   drifted. Check 1 fails early and names the function. Both are kept.
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
11. **`evidence_refs` growth is exactly the review count, per row and per
    class.** *(r1, r0-review M-2. r0's §6.4 stated deltas of +2/+1 that belong
    to no row class; encoding those as a postcondition would abort every
    batch.)* For every row in `B`:
    `len(evidence_refs_after) == len(evidence_refs_before) + applicable_reviews(row)`
    — i.e. **+3** on a non-register canonical row and **+2** on a register row.
    For every row not in `B`, the length is unchanged (implied by check 8, but
    asserted explicitly because this is the field the ordering rule of §3.4
    mutates). Terminal per-class shift is §6.4, measured this round.

### 6.3 Executed candidate proofs (this design round)

All probes ran against the §1.1 bytes, writing only under
`scratchpad/inventory-reviews/`. No canonical file was modified. *(r1,
r0-review M-8: r0 pointed at "§7 restates `git status`", but §7 is "Risks and
open questions" and contains no `git status`. The observed status is stated
here instead.)* `git status --short` at the start and end of this r1 round:

```
 M .beads/issues.jsonl
?? docs/goals/reviews/ledger/equity-os-blueprint-inventory-review-recording-design-r0.md
?? docs/goals/reviews/ledger/equity-os-blueprint-inventory-review-recording-design-r0-review-r0.md
?? docs/goals/reviews/ledger/equity-os-blueprint-inventory-review-recording-design-r1.md
```

The `.beads/issues.jsonl` modification is the pre-existing unrelated dirt noted
in §1.1; the three untracked files are r0, its review, and this document. No
canonical path is dirty. The §6.1 command block is what re-derives this.

| Probe | What it demonstrates | Result |
|---|---|---|
| **A. 6-row sample** — `REG-A-01`, `DISP-G-1`, `SEQ-01`, `PG-2-04`, `DISP-R-1`, `ALIAS-001`; Phase A/B ordering; `DISP-R-1` carve-out applied | The recording mechanics are legal | structural **0**; preimpl pending **447 → 433** (exactly 14 = 2+3+3+3+3), stale **0**, alias untouched |
| **B. Full 447 + satisfy `REQ-DISP-R-1-NO-IMPLEMENTATION`** | The "obvious" gate-clearing move is forbidden | preimpl `--report-blockers` **ready=true**, pending 0/stale 0/noimpl 0 — but **structural fails**, `AssertionError` at `validate_ledger_structural.py:2756`, exit **1** |
| **B′. Full 447 with the §3.6 carve-out** | The correct end state | structural **0**; preimpl pending **0**, stale **0**, noimpl **1** (`DISP-R-1`), exit **2**; preimpl assert-mode also exits 2 on that row |
| **C. Per-type append-and-digest on `SEQ-02`** | The §3.4 ordering rule is load-bearing | `AssertionError` at `validate_ledger_structural.py:350` (`reviewed_input_sha256`), exit **1** |
| **D. `REFERENCE_APPEND` transition with `field="evidence_inventory_review"` on a `PENDING` row** | A transition entry for a review field is rejected outright | `AssertionError` at `validate_ledger_structural.py:1909` (`field in controlled_fields`), exit **1** |
| **E. Same entry on a row whose reviews are `COMPLETE`** | A transition also stales the row's reviews via `transition_history_sha256` | `AssertionError` at `validate_ledger_structural.py:350`, exit **1** |
| **F. Serialization round-trip** | The §3.7 writer contract | `sort_keys=True, ensure_ascii=False, separators=(",",":")` reproduces the canonical ledger byte-for-byte (`de236d7e…`); the two alternatives produce `d3202bee…` |
| **G. `ast`-extraction of the four digest functions** *(r1, r0-review M-3)* | §6.2 check 1 is mechanically executable without importing the validator | All four `FunctionDef` nodes found and compiled in isolation; `sys.argv` untouched; namespace after `exec` is exactly `{canonical_sha256, normalized_human_review_id, review_input_projection, review_inventory_projection}` plus the three seeded stdlib modules; **no validation side effect ran**; input and per-type inventory digests computed over a 5-row / 3-kind sample, deterministic across repeats and varying per `review_type` as §3.3 predicts. Exit **0** |
| **H. Evidence-count and distribution recomputation** *(r1, r0-review M-1/M-2)* | The §6.4 and §7.5 figures | Before: **405** evidence objects (90×1 + 100×2 + 23×5); after: **852** (+447), ×2.10. Per class before → after: non-register canonical 1/2/5 (46/48/15) → **4/5/8**; register 2/5 (52/8) → **4/7**; aliases 44×1 → **unchanged at 1**. `required_evidence` items total 354 and are untouched |

Probe B′ is the decisive one: **completing all 447 reviews correctly yields
structural 0 / preimplementation 2-with-1-blocker**, exactly as §3.9 predicts.

### 6.4 Terminal postconditions for the whole workstream

- 447 review objects `COMPLETE`, each 13 keys, `verdict=CLEAN`, `role=REVIEWER`,
  `role_binding_path=CONTEXT.md`.
- 447 new `evidence_refs` objects, `FILE_BYTES`, globally unique IDs, each
  resolving to an existing durable verdict artifact.
- 447 verdict artifacts under `docs/goals/reviews/ledger/inventory/`.
- `evidence_refs` length distribution, **measured on the full-scale candidate
  this round** *(r1, r0-review M-2; r0's "1/2/5 → 3/4/7 non-register and
  1/2/5 → 2/3/6 register" was wrong in both the deltas and the row classes)*:

  | Row class | Rows | Before | After | Delta |
  |---|---:|---|---|---:|
  | non-register canonical | 109 | 1 (46) / 2 (48) / 5 (15) | **4 (46) / 5 (48) / 8 (15)** | **+3** |
  | `register_row` | 60 | 2 (52) / 5 (8) — **no register row has length 1** | **4 (52) / 7 (8)** | **+2** |
  | `derivative_alias` | 44 | 1 (44) | 1 (44) | **0** |

  The delta is exactly the row's applicable review count (§1.2), which is why
  §6.2 check 11 asserts it per row rather than asserting a global histogram.
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
   should be settled *before* batch 13 (r1 renumbering, §5.2), not litigated
   per-row. Changing it is
   an atomic 123-row migration plus a stale-review cascade, out of scope here.
   *NOTICED BUT NOT TOUCHING.*

   **Recording itself writes 447 `model` values naming a vendor model — and
   this is not `TERM-0001`-scope obligation drift.** *(r1, r0-review M-10.)*
   Every `COMPLETE` review object must carry a nonempty `model` recording the
   model actually invoked for that `REVIEWER` dispatch (§2.1), so completing
   all 447 reviews writes 447 such strings — e.g. `"claude-opus-5"` — into the
   canonical ledger. This is **contract-required and contract-permitted**:
   `model` is one of the mandatory 13 keys
   (`validate_ledger_structural.py:325`), and the validator checks only that it
   is a nonempty `str`, never comparing it to any constant
   (`:261-262`, with the explanatory comment at `:243-245`). It is a
   **historical record of what was invoked**, not an obligation string binding
   future work — the same distinction r7 draws when it rewrites vendor lanes in
   the *required-authority vocabulary* while explicitly "rewriting no
   historical model record". `TERM-0001` / `eqos-sky` scope is the 123
   `required_authority` obligation literals in `required_approvals`, which this
   tool never touches (§3.5, §4). A future lane audit or `TERM-0001` follow-on
   must therefore **not** count these 447 `model` values as in-scope drift;
   removing them would destroy the invocation record the schema exists to keep.

4. **`role_binding_sha256` drift across a long program.** The digest is an
   immutable historical capture and is deliberately never re-verified, so an
   unrelated `CONTEXT.md` edit mid-program leaves batches 1–8 bound to one
   digest and 9–17 to another. That is contract-legal and intended, but it will
   look like an inconsistency in audit. Recommend: capture the digest per batch
   and record which batches carry which, rather than assuming one value.

5. **447 new evidence objects roughly double the structural validator's
   file-hashing work.** Every run re-reads and re-hashes every declared
   evidence target. **Current: 405 evidence objects across 213 rows. After:
   852** — a **×2.10** increase, not a tripling. *(r1, r0-review M-1: r0 stated
   490 → 937, which matched neither the `evidence_refs` totals nor
   `evidence_refs` + `required_evidence` (405 + 354 = 759). Recomputed
   independently this round as probe H: 90×1 + 100×2 + 23×5 = **405**;
   405 + 447 = **852**. r0's §1.2 claim that every number was computed did not
   hold for this one.)* No postcondition in r0 was built on 490/937 — the
   figure appeared only in this risk item — so the correction changes no check;
   §6.2 check 11 and §6.4 are where the counts are now enforced. The flagged
   risk stands unchanged: runtime should be measured on batch 1 and reported,
   and if it degrades badly the batch count may need revisiting. **I did not
   measure runtime.**

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

9. **Scale of the untested surface.** Probes A–H cover the digest, ordering,
   carve-out, serialization, and projection-extraction mechanics end-to-end at
   full 447-row scale, but with synthetic single-line verdict artifacts and one
   reviewer identity. The recorder's manifest parsing, lock, journal/rollback
   path, `SIGINT`/`SIGTERM` guards, `RECOVERY_REQUIRED` path, and precondition
   set are **specified here and not yet implemented or tested**. This is a
   design document; nothing in §3.8 has been executed.
   *(r1: r0-review M-9d correctly refused to let this concession stand alone.
   §3.10 now makes a four-leg rollback rehearsal on a disposable full-tree
   replica a **hard precondition** on the first real write, with a
   machine-checkable proof object the recorder asserts and that is invalidated
   by any edit to the recorder or to the §1.1 pinned bytes. The rehearsal has
   **not been performed** — `record_inventory_review.py` does not exist yet —
   so this remains the largest untested surface in the design, but it can no
   longer be skipped silently.)*

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
