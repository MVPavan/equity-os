# Independent review — inventory-review recording design r2 (round r0)

**Reviewed artifact:**
`docs/goals/reviews/ledger/equity-os-blueprint-inventory-review-recording-design-r2.md`
**SHA-256 (recomputed at review start and end, unchanged):**
`adf908ac8cec01a55a53438624c6a8913f673f5b7cecd3e955fc4919f73803fb`

**Role:** `REVIEWER` (CONTEXT.md "Agent roles (harness-wide)").
**Role binding path:** `CONTEXT.md`
**Role binding SHA-256 (recomputed this round):**
`8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce`
**Model actually invoked:** `claude-opus-5`
**Effort actually invoked:** `high`
**Timestamp (UTC):** `2026-08-15T08:47:05Z`

**Independence.** This review was produced by a `REVIEWER`-role agent and
context distinct from the `IMPLEMENTER` dispatch that produced r2 (goal
L947-949, CONTEXT.md L137-139). This lane authored none of the reviewed
content.

**Scope.** FOCUSED differential against r1
(`1bc340ac3d50024de4aed21f95b7b9ae17c03e66b0745420d4e8c3928a9070d7`), which
this lane reviewed CLEAN with five Minors in
`…-design-r1-review-r0.md`
(`60e41dc0e1d93ec72b6829d503a9fedd897539e7c9df258c1d73121d04b3d5d9`). r1's
substance is not re-derived. Every line number below was measured against the
target bytes in this round; none is transcribed from either document.

**Mutations.** None. No canonical file was modified; no git or `bd` write was
performed. Probe output was written only under
`scratchpad/inventory-reviews/review/`. `git status --short` is unchanged from
the r2 round's own record apart from this review file.

---

## 1. Differential — every hunk traced

`diff -u r1 r2` yields **14 hunks**. Each traces to one of the five r1-review
Minors or to §0 supersession plumbing:

| Hunk | Location | Traces to |
|---|---|---|
| 1 | Title `r1` → `r2` | §0 plumbing |
| 2 | §0 supersession block | §0 plumbing |
| 3 | §0.1 disposition table + lineage paragraph | §0 plumbing |
| 4 | §1.2 r2 citation note | Minor 2 |
| 5 | §3.10 **Where** paragraph; "Five named legs" | Minor 4 |
| 6 | §3.10 legs table — L5 row | Minor 4 |
| 7 | §3.10 L1 rationale reworded; L5 fresh-replica paragraph | Minor 4 |
| 8 | §3.10 proof object — `/v2`, field rename | Minors 3, 4 |
| 9 | §3.10 proof object — `L5_recovery_required` block | Minor 4 |
| 10 | §3.10 step-2 asserts restructured 1–6 → 1–8 | Minors 3, 4 |
| 11 | §3.10 "What this gate is, and is not" | Minor 5 |
| 12 | §5.2 kind→rule citation | Minor 2 |
| 13 | §5.4 structural-validator citations | Minor 2 |
| 14 | §6.3 round-provenance paragraph + `git status` block | §0 plumbing (see Minor 2 below) |

No unexplained hunk. Hunk 14 is round-freshness bookkeeping rather than a
Minor fix; its content is correct and honest, but §0's self-description does
not name it — recorded as Minor 2 below, not as a defect in the change itself.

---

## 2. Per-finding verification

| # | r1-review Minor | How verified this round | Result |
|---:|---|---|---|
| M-1 | §7.4 stale batch range `9–17` | Read r2 L1270-1277; independently swept the whole document for every occurrence of `17` and every batch range/count | **Correct and complete.** L1273 reads `9–18`. The sweep confirms the implementer's claim: the only surviving `17` tokens are the r1 SHA (L17), the two explicit historical notes (L47, L935, L1274), spec IDs `S17`/`S18` (L905, L985-986), batch **17** as a legitimate row of the 18-batch register sub-table (L927), and unrelated citations. §5.2's plan table (L938-949) is internally consistent — rows `4+6+8+11+13+1+31+35+60 = 169`, reviews `12+18+24+33+39+3+93+105+120 = 447`, both recomputed here; the register sub-table L923-928 sums `8+11+9+10+11+11 = 60` and `16+22+18+20+22+22 = 120`. No renumbering residue survives. |
| M-2 | Citations corrected in §1.2 only | Re-read every cited range in the goal file (`f15f7ab5…`, hash reverified) and the structural validator (`731d0d8b…`, hash reverified) | **Correct and complete.** §8 L1337 now cites goal **L208-211** — verbatim "For a `register_row`, `scope_derivation.rule` is `REGISTER_STATUS`, its `related_register_ids` is empty, its `authority_effect` and `semantic_review` are `null`" — and **L495-496** — "An alias has `evidence_inventory_review=null`." §8 L1339 and §5.4 L1287 now cite **`:342`** = `assert review["verdict"] == "CLEAN"`. §5.4's paired `PENDING` cite **`:332-338`** is the exact `PENDING` branch (`:332` `if review["status"] == "PENDING":` through `:338` `assert review["evidence_ref_ids"] == []`), with the null assertion itself correctly located at `:337`. §8's retained `:250-262` is `assert_reviewer_role_binding`, covering the role/binding/model/effort half. §5.2 L1191 now cites **L235-245**. |
| M-2a | Kind→rule table line range — adjudication | Read goal L204-283 directly | **The implementer is right; the r1 review was wrong at both ends.** Goal L235 carries the lead-in "Rules are fixed by kind:", L236 is blank, L237-238 are the table header and separator, L239-245 are the seven kind rows ending with `document_strategy_clause` at L245. The r1 review's **L236-244** starts on a blank line, drops the lead-in, and truncates the last kind row. **L235-245 is correct.** One wording nit inside the correction: r2's parenthetical calls L237-245 the "table body", where L237-238 are header/separator and the body proper is L239-245 — the cited range itself is exact. |
| M-3 | assert 5 ledger clause ambiguous — one reading aborts batches 2–18 | Read r2 L730-793 and §3.8 L528-566 | **Correct, complete, and load-bearing.** r1's assert 5 is split into assert 6 (validator pin) and assert 7 (ledger pin); r1's assert 4 becomes assert 5, and §0.1 and L805's "asserts 5–8" both track the renumbering. Assert 7 enumerates *exactly three* comparisons — 64-hex form, equality with the rehearsal transcript's pre-state digest, and equality with the §1.1 literal `de236d7e…` — and states at L780-783 that "The live canonical ledger is not read by this assert, at batch 1 or at any later batch," all three quantities being constants captured before the first write. **No reading of the final text can abort batches 2–18**: every compared quantity is fixed before batch 1 and unaffected by any commit. The field rename `ledger_prestate_sha256` → `replica_ledger_prestate_sha256` is applied at L699 and no stale occurrence of the old name survives outside the two explicit change notes (L735, L771). |
| M-3a | §3.8 step 2 still does the live per-batch prehash check | Read §3.8 step 2, L541 | **Confirmed, byte-identical to r1** (absent from the diff). "Ledger prehash equals the recorded prehash" remains a step-2 precondition, and L785-791 correctly distinguishes it from assert 7. The two checks are not conflated and neither is weakened. |
| M-4 | Legs never exercise `RECOVERY_REQUIRED` | Read r2 L666-753 against §3.8 step 10 (L596-608) | **Correct and complete in all three required places.** Legs table row L5 at L676 requires journal `RECOVERY_REQUIRED`, the full step-10 unproven-path payload, nonzero exit, lock released, and a second invocation refused at step 1. Proof schema carries `L5_recovery_required` at L717-723 with every one of those fields. Step-2 assert 4 (L743-753) — a **pre-first-write** assert, per §3.10's Rule at L651-654 and §3.8 step 2's first bullet at L529-530 — enforces them, including the `observed_sha256 != expected_sha256` inequality with the `null`-for-removed-preimage case handled explicitly. Each required outcome maps to a real step-10 behavior: the payload list at L599-602 matches the leg's, and step 10's "nonterminal for the recovery check in step 1" (L604) is exactly what L5's second-invocation clause tests. `/v1` → `/v2` at L695 and L733 correctly forces rejection of a stale r1-shaped proof by name. |
| M-4a | Is scoping `temp_files_surviving == 0` to L1–L4 correct, or a hole? | Compared assert 2 (L737-740) against §3.8 step 10 (L599-602) | **Correct, not a hole.** Step 10 records "the surviving preimage and temp paths" for the operator by design, so requiring zero surviving temp files on L5 would demand the opposite of the behavior under test and make a correct L5 unpassable. The exemption is not a weakening: L5 substitutes `surviving_paths_recorded_in_journal == true`, which asserts the positive property step 10 actually owes. L1–L4 keep the original requirement unchanged. The reasoning is stated in the document itself at L682-688. |
| M-5 | "Mandatory" rehearsal gate is self-attested | Read r2 L800-808 | **Correct, and slightly stronger than asked.** The paragraph states that the gate is an operator-discipline control over a gitignored workstream evidence artifact, not an enforcement boundary and not ledger evidence; that the recorder cannot authenticate the file so a hand-written proof would pass; that no validator, gate, ledger record, or contract obligation depends on it; and that its hash bindings defend against a stale proof outliving a recorder or validator edit, not against forgery. Nothing is overstated. |
| — | Pinned pre-state still holds | `sha256sum` on all seven §1.1 paths | **All seven match** the §1.1 table exactly. |
| — | Baseline gate exits (r2 §6.3 claims a re-run) | Ran `extract_goal_validators.py --check`, `validate_ledger_structural.py --repo-root .`, `validate_ledger_preimplementation.py --repo-root . --report-blockers` | **Confirmed:** `extract=0`, `structural=0`, `preimpl=2`, `ready=false`, `pending_reviews=447`, `stale_reviews=0`, `unmet_no_implementation_proof=1`. r2's §6.3 claim is accurate. |
| — | Did r2 break anything r1 had right? | Full hunk-by-hunk read | **No.** The one substantive rewording of correct r1 text — L678, "L2–L4's *restored to pre-state*" → "L2–L5's *did not silently commit*" — is required by L5, whose replica is deliberately **not** restored to pre-state; the generalization is correct rather than a loss. §0.1's lineage paragraph (L53-56) accurately states that the ten r0-review Minors remain in force and that none is reopened, which matches the r1 review's own conclusion. |

---

## 3. Ruling on the deliberate non-fix (§2.1 `:320-354`)

**Acceptable — recorded as a Minor, not a finding that blocks.**
`validate_inventory_review` spans `:320` through `:355`; `:355` is the bare
closing parenthesis of the `reviewed_inventory_sha256` assert that begins at
`:353`. The cited range therefore omits no rule, no assertion subject, and no
branch — the truncation is by one syntactic line, not one semantic line.
Weighing against it: the range is introduced as "authoritative", and this round
corrected two other citations for exactly one-line endpoint errors, so the
standard the document set for itself argues for `:320-355`. Weighing for it:
the citation was never raised by the r1 review, is byte-identical to r0 and r1,
and misleads no reader about what the function requires. The implementer's
decision to leave it and declare it is the honest handling; the cost of
changing it does not exceed the cost of a further round.

---

## 4. Findings

### Critical — none.
### Important — none.

### Minor

1. **§2.1 cites `validate_ledger_structural.py:320-354`; the function ends at
   `:355`.** Pre-existing since r0, unchanged in r2, declared as a deliberate
   non-fix. `:355` closes the final assert's argument list. No rule is
   excluded. Ruled acceptable in §3 above; noted only so the next round has it
   in writing. Suggested wording if ever touched: `:320-355`.

2. **§0's "every unflagged section is byte-identical to r1" is not literally
   true — §6.3 was also rewritten.** L36-38 claims r2 changes "exactly what
   those five findings require, plus this supersession and header plumbing" and
   that every unflagged section is byte-identical. Hunk 14 rewrites §6.3's
   probe-provenance paragraph and `git status` block (L1148-1166), which traces
   to no Minor. The change itself is **correct and required for honesty** — it
   distinguishes probes A–H executed in the r1 round from what the r2 round
   actually re-verified, and I confirmed each of its claims independently (all
   seven §1.1 hashes, the three baseline exits, and the four untracked
   lineage files plus "this document once written", which matches the observed
   working tree). Only §0's self-description under-reports it. One clause in §0
   naming round-provenance bookkeeping as in-scope plumbing would close this.

3. **§3.10's "Where" admits a replica-construction method that a mid-program
   re-rehearsal could read into an assert-7 failure.** L656-659 requires the
   replica to be at "the exact §1.1 pre-state bytes" but offers "or by a plain
   full-tree copy" as a method. Assert 5 mandates a fresh rehearsal after any
   recorder edit, including between batches; an operator who at batch 5 takes a
   plain copy of the *then-current* tree gets a
   `replica_ledger_prestate_sha256` that is not `de236d7e…`, and assert 7's
   third clause fails. This does **not** reopen Minor 3: the governing phrase
   "at the exact §1.1 pre-state bytes" already resolves it, the failure is
   fail-closed and names the mismatch, and the `git worktree add` method
   remains available indefinitely because the pre-state ledger is committed at
   `8617e52`. One clause stating that a mid-program re-rehearsal is rebuilt at
   the §1.1 pre-state commit, not copied from the live tree, would remove the
   ambiguity.

4. **L1's proof block carries no `exit_code`, unlike L2–L5.** L703-705 and the
   legs table L672 state L1's outcome without an exit expectation, and asserts
   2–3 do not add one, so an L1 that committed correctly but exited nonzero
   would pass. Pre-existing from r1 and not flagged in the r1 review;
   `journal_state == "COMMITTED"` plus `structural_exit: 0` covers the
   substance. Cosmetic symmetry only.

---

## 5. Assessment

r2 is a tight, fully traceable differential. All five r1-review Minors are
genuinely and completely fixed, not merely declared fixed — I re-read the
target bytes for every one rather than trusting either document's line
numbers. The two that carried real weight are the strongest work in the round:
the assert 5 → 6/7 split with the `replica_ledger_prestate_sha256` rename
leaves no reading under which the rehearsal pin can abort a later batch, while
preserving the live ledger's independent per-batch prehash check; and L5 closes
the gap where `RECOVERY_REQUIRED` was specified, gated on, and never rehearsed,
with the `temp_files_surviving` exemption scoped correctly rather than waived.
The implementer's adjudication of the kind→rule table range is correct and this
lane's earlier L236-244 was wrong at both ends — that correction is accepted.
The four Minors above are hygiene: one declared non-fix, one over-tight
self-description, one construction ambiguity that fails closed, and one
cosmetic asymmetry. None affects an executable decision, and none is worth a
further round on its own.

Verdict: CLEAN
