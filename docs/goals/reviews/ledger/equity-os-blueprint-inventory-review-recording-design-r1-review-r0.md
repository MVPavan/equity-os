# Independent differential review — inventory-review recording design r1

**Reviewed artifact:** `docs/goals/reviews/ledger/equity-os-blueprint-inventory-review-recording-design-r1.md`
**Reviewed artifact SHA-256:** `1bc340ac3d50024de4aed21f95b7b9ae17c03e66b0745420d4e8c3928a9070d7`
(recomputed at review start `2026-08-15T08:24:08Z` and at review end
`2026-08-15T08:31:10Z` — unchanged; the artifact was not modified by this review)

**Role:** `REVIEWER` (CONTEXT.md "Agent roles (harness-wide)")
**Role binding path:** `CONTEXT.md`
**Role binding SHA-256:** `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce`
(recomputed this session)
**Model invoked:** `claude-opus-5`
**Effort:** `high`
**Independence:** this reviewer authored no part of r0, r1, or the r0 review, and
ran in a separate agent and context from the `IMPLEMENTER` dispatch that produced
r1 (goal L947-949, CONTEXT.md L137-139).
**Review round:** `r0` of the r1 artifact
**UTC timestamp:** `2026-08-15T08:31:10Z`

**Differential basis.** Prior review
`docs/goals/reviews/ledger/equity-os-blueprint-inventory-review-recording-design-r0-review-r0.md`
(SHA-256 `91b0ce64d70fabc4acb33344281efd162af816fc47c8f6de0eeacfc079e7a462`),
CLEAN with ten Minors, over r0
(`5ec10de959d56145c00d186924c01c2d8cc3af5c488a78e4aadf5afbefcd7dea`) — both
digests recomputed here and matching.

---

## 1. Diff accounting — every hunk traced

`diff -u r0 r1` yields **18 hunks**. Each traces to one of the ten Minors or to
§0 supersession / header plumbing. **No unexplained change.**

| Hunk | Location | Attribution |
|---|---|---|
| 1 | title `r0` → `r1` | header plumbing |
| 2 | new §0 + §0.1 disposition table | supersession |
| 3 | §1.2 citations | M-5 |
| 4 | §1.2 evidence totals + per-class breakdown | M-1 / M-2 |
| 5 | §3.3 `ast`-extraction mechanism | M-3 |
| 6 | §3.8 step 1 lock | M-9a |
| 7 | §3.8 step 2 rehearsal precondition + `lstat` shape check | M-9b / M-9d |
| 8 | §3.8 step 2 applicable slots | M-4 |
| 9 | §3.8 step 9 addendum + new step 10 | M-9c |
| 10 | new §3.10 rehearsal | M-9d |
| 11 | §5.2 register-only table + split | M-7 |
| 12 | §5.2 batch plan 17 → 18 + arithmetic check | M-6 |
| 13 | new §5.2a relocated ownership table | M-7 |
| 14 | §6.2 check 1 rewrite | M-3 |
| 15 | §6.2 new check 11 | M-2 |
| 16 | §6.3 inline `git status` | M-8 |
| 17 | §6.3 probes G, H | M-3 / M-1 / M-2 |
| 18 | §6.4 table, §7.3 model note + batch renumber, §7.5 counts, §7.9 rehearsal | M-2 / M-10 / M-6 / M-1 / M-9d |

§0's claim that "every unflagged section is byte-identical to r0" is confirmed by
construction: the diff contains nothing outside these hunks.

---

## 2. Per-finding verification

Every number below was recomputed by this reviewer against the §1.1 bytes. No
figure was transcribed from r1 or from the r0 review.

| # | r1's claimed fix | Method | Result |
|---:|---|---|---|
| M-1 | 490→937 corrected to **405 → 852**, ×2.10 | Full ledger scan of all 213 rows | **Correct.** 90×1 + 100×2 + 23×5 = **405**; 405 + 447 = **852**; ratio **2.1037**. `required_evidence` = **354** (405+354 = 759, so the old figure matched neither), confirming r1's diagnosis. §1.2, §6.3 probe H, and §7.5 agree with each other and with measurement. |
| M-2 | Per-class distributions corrected | Recomputed before/after lengths by row class | **Correct and complete.** Non-register canonical (109): 1 (46) / 2 (48) / 5 (15) → **4 (46) / 5 (48) / 8 (15)**, +3. Register (60): 2 (52) / 5 (8) → **4 (52) / 7 (8)**, +2; **no register row has length 1** — confirmed. Aliases (44): 1 → 1, unchanged. §1.2, §6.2 check 11, §6.4 and probe H are mutually consistent and all match. Check 11's per-row form `len(after) == len(before) + applicable_reviews(row)` is the correct generalization. |
| M-3 | Import replaced by `ast`-extract + `exec` | **Executed the §3.3 block verbatim**, then proved digest equivalence against the real validator | **Executes as written — all three sub-claims hold.** (a) All four `FunctionDef` nodes (`canonical_sha256`, `normalized_human_review_id`, `review_input_projection`, `review_inventory_projection`) are top-level and were extracted; post-`exec` namespace is exactly those four plus the three seeded stdlib modules. (b) No module-level side effect: run with a deliberately hostile `--repo-root SHOULD_BE_IGNORED`, `sys.argv` was untouched and no `SystemExit` occurred; no `args`/`rows` binding appeared. (c) Built a candidate ledger whose `reviewed_input_sha256`/`reviewed_inventory_sha256` came **only** from the extracted functions, on real rows covering **all three review types** (`PG-05-01` SCOPE+EVIDENCE+APPROVAL, `REG-A-01` EVIDENCE+APPROVAL) — the real `validate_ledger_structural.py` exits **0**, i.e. the validator's own `:350`/`:353` recomputation agrees byte for byte. Negative control (one digest zeroed) fails at **`:350`**, exit 1. Also observed as predicted: one input digest per row shared across its types; the EVIDENCE inventory digest shifts after the Phase-A evidence append while SCOPE/APPROVAL do not — §3.4's ordering rule is load-bearing exactly as stated. |
| M-4 | "three review slots" → "applicable review slots" | Read `validate_ledger_preimplementation.py:199-205`; scanned all 213 rows | **Correct.** The cited `:200-204` does contain the whole rule (`APPROVAL`/`EVIDENCE` unconditional; `SCOPE` appended only `if row["kind"] != "register_row"`). The stated applicability — 3 / 2 / 0 by class — reproduces the measured 109 SCOPE + 169 EVIDENCE + 169 APPROVAL. The added assert that a register row's `semantic_review` **is** `null` is sound and independently backed by the structural validator's own `assert derivation["semantic_review"] is None` (`validate_ledger_structural.py:1532`, goal L2886). |
| M-5 | Three citations corrected | Re-read each cited range in the goal file (`f15f7ab5…`) | **All four §1.2 citations correct.** L208-211 verbatim: "For a `register_row`, `scope_derivation.rule` is `REGISTER_STATUS`, its `related_register_ids` is empty, its `authority_effect` and `semantic_review` are `null`". L495-496: "An alias has `evidence_inventory_review=null`." L280: "An alias has `scope_derivation=null`." L623-624: "An alias has `approval_inventory_review=null`." L2886 mechanization confirmed. The non-register rule at L274-280 confirmed. **Residual:** the same two superseded citations survive in §8 and one imprecise citation survives in §5.2 — Minor 2 below. |
| M-6 | 17 → 18 batches; `DISP-R-1` is one of the 32 | Recounted kinds and disposition rows | **Correct.** 32 `disposition_item` rows, `DISP-R-1` among them ⇒ 31 remain; the 11/10/10 split sums to 31. Batch-plan arithmetic re-derived independently: rows 4+6+8+11+13+1+31+35+60 = **169**; reviews 12+18+24+33+39+3+93+105+120 = **447**. Both match §1.2 and the blocker report. |
| M-7 | Register-only table added; 96-row table relocated to §5.2a | Recomputed both tables from the ledger | **Correct, and the misreading is now closed.** Register-only per-spec counts match r1 cell for cell (25 specs, all owning ≥1 register row; total **60 rows / 120 reviews**). The stated batch split **8 / 11 / 9 / 10 / 11 / 11** = 60 reproduces exactly for S01–S04, S05–S08, S09–S11, S12–S14, S15–S18, S19–S25. The §5.2a table reproduces row for row: 96 spec-owning canonical rows = **60 register + 36 non-register (16 `disposition_item`, 12 `first_release_deferral`, 8 `scale_trigger`)**; 228 spec-owned + 219 null-spec reviews = **447**. The S10 illustration is exact: 8 owned rows but only **2** register, the other 6 being 4 `scale_trigger` / 1 `first_release_deferral` / 1 `disposition_item`. The 96-row table can no longer be read as batch sizing: it now sits *after* the batch plan under a heading that negates it, and the register-only table says "never the §5.2a ownership table below". |
| M-8 | Dangling §6.3→§7 pointer replaced with inline status | Ran `git status --short` at review start and end | **Correct.** Observed status matches r1's quoted block exactly, modulo this review's own new file. No canonical path dirty. |
| M-9 | Four hardening measures | Clause-by-clause against r7 §6.2; reachability analysis of the journal state machine | **Three closed cleanly; the fourth closed with two gaps (Minors 3–5).** See §3 below. |
| M-10 | 447 `model` values addressed in §7.3 | Read `validate_ledger_structural.py:243-245, 261-262, 325` | **Correct and precisely scoped.** `model` is one of the mandatory 13 keys and is only ever checked as a nonempty `str` — no constant comparison anywhere. The historical-record vs obligation-string distinction is the right one, and the `TERM-0001` boundary (the 123 `required_authority` literals in `required_approvals`, untouched by this tool) is stated accurately. |

### M-9 detail

- **(a) Lock.** `open(..., "x")` is genuine exclusive creation; the design
  correctly refuses to overclaim — it states the lock does not survive process
  exit, that the compare-and-swap remains the correctness guarantee, and that
  the durable guard is the nonterminal journal. That matches r7 §6.2 step 1's
  intent rather than merely its letter.
- **(b) `lstat`.** Rejecting symlink / directory / FIFO / device / `st_nlink > 1`
  and requiring the resolved path to equal the canonical path does close the
  stated hole: `lstat` (not `stat`) is the right call, since a symlinked target
  would otherwise survive the check and the same-directory rename would replace
  the link. Recording the mode here and comparing at steps 4, 7 and 9 is
  consistent with step 9's new bytes-**and**-mode rule.
- **(c) `RECOVERY_REQUIRED`.** Reachability checked exhaustively. Every failure
  after replacement routes to step 9; a step-9 rollback that cannot prove both
  bytes and mode routes to step 10. Every path that *bypasses* step 10 — crash
  during rollback, crash while writing the `RECOVERY_REQUIRED` journal, CAS
  mismatch at step 7 — leaves the journal at `PREPARED`, which is also
  nonterminal. So the state machine is fail-safe in both directions: there is no
  reachable exit that leaves a terminal journal over an unproven ledger. Step 1
  stops on *any* nonterminal journal, and step 10 explicitly declares
  `RECOVERY_REQUIRED` nonterminal to that check, so the "refuses to run until an
  operator resolves it" claim holds. The declared state set
  `PREPARED → {COMMITTED, ROLLED_BACK, RECOVERY_REQUIRED}` is complete and
  correctly partitioned.
- **(d) Rehearsal.** The four legs are real and correctly placed: L2 injects
  **after the rename and before `COMMITTED`**, which is the only window in which
  the ledger is mutated but uncommitted — the exact window rollback exists for;
  L3/L4 hit the same window via signals. L1 is a necessary control, and the
  design says why. The proof object is genuinely machine-checkable: fixed schema
  string, four named legs with boolean and enum fields, `temp_files_surviving == 0`,
  separate `bytes_match_preimage` **and** `mode_match_preimage`, plus a hashed
  transcript. It **is** invalidated by a recorder-hash change (assert 4, stated
  to bite even on a one-line inter-batch fix) and by a validator-hash change
  (assert 5). It **is** asserted before the first write: §3.8 step 2's first
  bullet, inside the block titled "Preconditions, before any write". Two gaps
  remain — Minors 3 and 4.

---

## 3. Binding facts from r0 — re-verified at these bytes

All re-derived independently this session, not carried over:

| Fact | Evidence |
|---|---|
| 109 / 169 / 169 = **447** over **169** canonical rows | `--report-blockers`: `Counter({'APPROVAL': 169, 'EVIDENCE': 169, 'SCOPE': 109})`, 447 records, 169 distinct components, `stale_reviews=0` |
| Baseline gates | structural exit **0**; preimplementation exit **2**, `ready=false`, `unmet_no_implementation_proof=1` (`DISP-R-1`); `extract_goal_validators.py --check` exit **0** |
| All seven §1.1 pinned hashes | recomputed, all match |
| Recording is transition-free, and a transition is **forbidden** | `controlled_direct_fields` (`:1732-1743`) contains no review object, no `evidence_refs`, `required_evidence`, `required_approvals`, `approval_records`, or `review_round`; `assert field in controlled_fields` at **`:1909`** |
| Full-validator projections, **no key-subset** | §3.3 transcribes the entire 41-field input projection and all three inventory projections; proved by construction — a candidate digested solely from the `ast`-extracted originals passes the real validator at exit 0 |
| No human authority carried | 13-key `COMPLETE` schema (`:325`) has no field able to carry one; `approval_records` / `required_approvals` / `human_review_id` untouched by the specified writes |
| A non-clean verdict is **unrecordable** | `assert review["verdict"] == "CLEAN"` (**`:342`**) is the sole legal `COMPLETE` value; a `PENDING` review must carry `verdict=null` (`:332-338`) |
| `DISP-R-1` permanent blocker and its consequence | `assert EXPECTED_DISP_R1_REQUIREMENT in disp_r1["required_evidence"]` (**`:2756`**) and `assert {...} <= set(disp_r1_reasons)` (**`:2761`**) present as cited; §3.9's "0 pending, 0 stale, gate still exits 2" claim stands unchanged and unhedged |

All probes wrote only under `scratchpad/inventory-reviews/review/r1probe/`.
`git status --short` at review start and end is unchanged apart from this
review's own new file. No canonical file was mutated.

---

## 4. Findings

**Zero Critical. Zero Important.**

### Minor

1. **§7.4 carries a stale batch range that r1's own renumbering created.**
   §5.2 states "total batch count 17 → 18 and all later batch numbers shift by
   one", and §7.3 was duly updated (batch 12 → 13). §7.4 was not: it still reads
   "leaves batches 1–8 bound to one digest and **9–17** to another" (L1163-1164).
   Under the 18-batch plan the range is 9–18. Purely illustrative — no mechanism
   reads it — but it is the one place where r1 broke something r0 had right.

2. **The M-5 citation correction was applied in §1.2 only; the same superseded
   citations survive elsewhere.**
   - §8's summary table (L1225) still cites "goal **L233-236, L379**" for
     "Which reviews apply per kind?" — the exact two pointers §1.2 replaced with
     L208-211 and L495-496, for the same claim. §0.1 records M-5 as "Fixed",
     which is true of §1.2 and not of §8.
   - §8 (L1227) cites `validate_ledger_structural.py:250-262, **337**` for a row
     that includes `verdict == "CLEAN"`. `:337` is `assert review[field] is None`
     inside the `PENDING` branch; the CLEAN rule is at **`:342`**. `:250-262`
     correctly covers the role/binding/model/effort half.
   - §5.2 (L788) cites "goal L~262-278" for "The `SCOPE` rule is fixed by kind",
     but the kind→rule mapping table is at **L236-244**; L262-278 is
     `ACTIVE_NEGATIVE_CONTROL` and the `semantic_review` paragraph. r1's own
     §1.2 note calls this citation "correct elsewhere", which holds for the
     `semantic_review` rule but not for the claim it is actually attached to.

   All three underlying claims are true — I verified each against the goal and
   the validator. This is citation hygiene, but it is the residue of a finding
   declared closed.

3. **§3.10 assert 5's ledger clause cannot do what its own gloss says.** The
   proof object pins `ledger_prestate_sha256` = the §1.1 value, and assert 5
   requires "the three pinned hashes equal §1.1", glossed as "a validator or
   **ledger-pre-state** change invalidates the rehearsal" — while §3.10 also
   requires the proof to be "re-checked on every later batch". The ledger
   necessarily changes when batch 1 commits. So the clause is either vacuous
   (compare two constants — satisfiable for all 18 batches, but then no ledger
   drift can ever invalidate the rehearsal) or unsatisfiable (compare against the
   live ledger — every batch after the first aborts permanently). The literal
   wording supports the satisfiable reading, and §3.8 step 2 elsewhere correctly
   pins only the *validators* to §1.1 while comparing the ledger to a per-batch
   "recorded prehash" — so the safe reading is the intended one and no unsafe
   path exists either way. One clause stating which ledger hash is compared, and
   that the pin is to the rehearsal's own starting state rather than to the live
   file, removes the stall.

4. **The four rehearsal legs never exercise `RECOVERY_REQUIRED`.** L1 requires
   `COMMITTED`; L2/L3/L4 each require `ROLLED_BACK`. The state r1 added in
   response to M-9c — the branch that fires exactly when the rollback itself
   cannot be proven — is therefore specified, gated on, and never rehearsed,
   which is the same objection M-9d raised against the rollback path. A fifth
   leg (corrupt or remove the preimage before rollback; require journal
   `RECOVERY_REQUIRED`, the full unproven-path payload, nonzero exit, and that a
   subsequent invocation is refused at step 1) would close it, and is cheap
   inside the disposable replica the harness already builds.

5. **The "mandatory" rehearsal gate is self-attested.** The proof object lives
   at gitignored `scratchpad/inventory-reviews/rehearsal/proof.json`. Binding
   `recorder_sha256`, the three §1.1 hashes, and `transcript_sha256` does defend
   against the realistic failure — a stale proof silently outliving a recorder
   edit — but not against a hand-written file. The design is honest that this is
   a workstream evidence artifact and not ledger evidence; worth one sentence
   saying the gate is an operator-discipline control rather than an enforcement
   boundary, so a later reader does not over-credit it.

### Not findings (checked and cleared)

- §3.3's snippet leaves `REPO_ROOT` to the caller — ordinary plumbing; the block
  ran verbatim once bound.
- §6.2 check 1's "covering all three `review_type` values" is satisfiable for the
  register-only batches 13–18, because the ≥5-row sample is explicitly drawn
  from *untouched* rows, separate from the batch.
- §3.8 step 2's `extract_goal_validators.py --check` invocation is correct — the
  extractor takes no `--repo-root` (I confirmed by getting this wrong first).
- A step-7 CAS mismatch leaves a `PREPARED` journal and wedges the tool until an
  operator clears it. Conservative and unchanged from r0; fail-closed is right
  here.

---

## 5. Assessment

All ten Minors are addressed, and the two that carried real risk are addressed
well. **M-3 is fully discharged:** the `ast`-extract + `exec` mechanism is not
merely plausible — it ran verbatim in this review, extracted exactly the four
named functions, executed no module-level statement of the validator (including
`parse_args`), left `sys.argv` untouched, and produced digests the real
structural validator accepted at exit 0 across all three review types on real
rows, with a negative control failing at the predicted `:350`. r1's reasoning
about *why* it is safe — the four-function whitelist, the three-module seeded
namespace as a `NameError` tripwire, `normalized_human_review_id` being required
by both projections, and the `assert set(picked) == set(WANTED)` drift guard —
is correct in every particular; the namespace after `exec` is exactly what §6.3
probe G claims. Keeping check 1 *and* step 5, on the argument that step 5 fails
late with a bare `AssertionError` that names no function, is the right call.

Every recomputed number is exact: 405 → 852, the three per-class distributions,
the 60-row/120-review register table and its 8/11/9/10/11/11 split, the four-way
disposition split over 31 rows, and both totals of the 18-batch plan. The M-7 fix
is structural rather than cosmetic — the 96-row table now sits after the batch
plan under a heading that negates the misreading, and the sizing table points
away from it explicitly. The M-9 hardening is closed rather than waived, and the
`RECOVERY_REQUIRED` state machine is fail-safe on every path I could reach,
including the ones that bypass it.

All r0-verified binding facts survive r1 unchanged and were re-derived here:
447 over 169 rows, transition-free and transition-forbidden, whole-projection
digests with no key subset, no authority carried, no non-clean verdict
representable, and the `DISP-R-1` blocker still permanently closing the
preimplementation gate. The five Minors are one stale cross-reference r1's own
renumbering introduced, citation residue from a fix applied in one section but
not its summary, one ambiguous clause in the rehearsal preconditions, one
unrehearsed leg of the state r1 just added, and one over-strong word for a
self-attested gate. None affects the mechanism, its safety, or its authority
posture, and none can produce a fabricated, unauthorized, or invalid ledger
record.

Verdict: CLEAN
