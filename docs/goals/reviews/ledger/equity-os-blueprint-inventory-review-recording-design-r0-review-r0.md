# Independent review — inventory-review recording design r0

**Reviewed artifact:** `docs/goals/reviews/ledger/equity-os-blueprint-inventory-review-recording-design-r0.md`
**Reviewed artifact SHA-256:** `5ec10de959d56145c00d186924c01c2d8cc3af5c488a78e4aadf5afbefcd7dea`
(recomputed at review start and at review end — unchanged; the artifact was not
modified by this review)

**Role:** `REVIEWER` (CONTEXT.md "Agent roles (harness-wide)")
**Role binding path:** `CONTEXT.md`
**Role binding SHA-256:** `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce`
(recomputed this session)
**Model invoked:** `claude-opus-5`
**Effort:** `high`
**Independence:** this reviewer authored no part of the reviewed design and ran
in a separate agent and context from the `IMPLEMENTER` dispatch that produced it
(goal L947-949, CONTEXT.md L137-139).
**Review round:** `r0`
**UTC timestamp:** `2026-08-15T07:41:13Z`
**Review round policy:** goal L982-1000 (`r0`…`r4` ceiling; this is `r0`).

---

## 1. Bound inputs (all recomputed this session)

| Path | SHA-256 | Matches dispatch |
|---|---|---|
| `docs/goals/reviews/ledger/equity-os-blueprint-inventory-review-recording-design-r0.md` | `5ec10de959d56145c00d186924c01c2d8cc3af5c488a78e4aadf5afbefcd7dea` | yes |
| `docs/goals/equity-os-blueprint-completion.md` | `f15f7ab5a4e425dec3877ab7f1f7594687979060e4dbcd49390a8a8d5fedb85f` | yes |
| `CONTEXT.md` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` | yes |
| `scripts/equity_os_blueprint/validate_ledger_structural.py` | `731d0d8b208b577967c92e3992e7ec1a4333cdecbf89f6951c32d2ec469436f9` | yes |
| `scripts/equity_os_blueprint/validate_ledger_preimplementation.py` | `f7a225a1f99cb85c92cde3094505a92a746552280eb45dae0253a71ab9048013` | yes |
| `scripts/equity_os_blueprint/extract_goal_validators.py` | `5d20d796666d1154fb3c84ba4fa7407ee82819510a5ac06254f7f4a3126c6f2a` | yes |
| `docs/goals/equity-os-blueprint-component-ledger.jsonl` | `de236d7e8dcf02e307ec58797f5722ae2f85d1d8cdba57d4ecc07df5383c9c97` | yes (design §1.1) |

Baseline re-run this session: structural exit `0`; preimplementation
`--report-blockers` exit `2` with `ready=false`, `pending_reviews=447`,
`stale_reviews=0`, `unmet_no_implementation_proof=1`;
`extract_goal_validators.py --check` exit `0`.

`git status --short` at review start and end: ` M .beads/issues.jsonl` and
`?? docs/goals/reviews/ledger/equity-os-blueprint-inventory-review-recording-design-r0.md`
— unchanged. No canonical file was mutated by this review. All probes wrote only
under the gitignored `scratchpad/rev-probe/`.

**Verification method.** Every numeric and mechanical claim below was
recomputed or re-executed by this reviewer against the pinned bytes. No number
was transcribed from the reviewed design, and no probe result was accepted on
the design's report alone; the design's decisive probe (B′) and its four
counter-probes (B, C, D, E) were independently reconstructed and re-run.

---

## 2. Per-item verification

| # | Dispatch item | Method | Result |
|---:|---|---|---|
| 1 | Review-count table (109 SCOPE / 169 EVIDENCE / 169 APPROVAL = 447 over 169 canonical; 0 for aliases) | Direct ledger scan of all 213 rows plus `validate_ledger_preimplementation.py --report-blockers` | **Exact.** Scan: `SCOPE 109 / EVIDENCE 169 / APPROVAL 169 = 447`, all `PENDING`; blocker report: `Counter({'APPROVAL': 169, 'EVIDENCE': 169, 'SCOPE': 109})`, 447 records, `pending_reviews=447`. Per-kind table reproduced row for row (`register_row` 60/0/60/60=120; `phase_gate_clause` 35→105; `disposition_item` 32→96; `first_release_deferral` 13→39; `sequence_clause` 11→33; `scale_trigger` 8→24; `document_strategy_clause` 6→18; `authority_clause` 4→12; `derivative_alias` 44→0). 10-key `PENDING` key set confirmed identical on all 447. The design's stated correction of the brief (107/441 → 109/447) is right. |
| 2 | Recording is transition-free; a transition would stale the reviews | Read `controlled_direct_fields` (`validate_ledger_structural.py:1732-1743`) and `assert field in controlled_fields` (`:1909`); ran probes D and E | **Confirmed.** `controlled_direct_fields` contains no review object, no `evidence_refs`, no `required_evidence`, no `required_approvals`, no `approval_records`, no `review_round`. Probe D (well-formed `REFERENCE_APPEND` with correct actor object, chained `entry_sha256`, refreshed `transition_history_sha256`, nonempty component-local evidence) fails at **`:1909`** for `field` ∈ {`evidence_inventory_review`, `evidence_refs`, `required_evidence`, `review_round`, `approval_records`}, exit `1`. Probe E (a *legal*-field transition on a row whose reviews are `COMPLETE`) fails at **`:350`**, exit `1` — `transition_history_sha256` is inside `review_input_projection` (`:283`). Both cited mechanisms hold; the design's "none required, and forbidden" is correct. |
| 3 | `reviewed_input_sha256` / `reviewed_inventory_sha256` use the exact validator code path; **any key-subset projection is Critical** | Compared `review_input_projection` / `review_inventory_projection` / `canonical_sha256` (`:264-318`, `:72-76`) against preimplementation `input_projection` / `inventory_projection` / `digest` (`:55-107`, `:49-53`); rebuilt the full 447 at scale | **No key-subset projection. No Critical.** The design mandates transcribed copies of the *whole* 41-field input projection and the three per-type inventory projections, plus a drift check that aborts before any write, plus candidate validation by the real validator. The two validators' projections are output-equivalent (structural wraps a `frozenset` in `sorted(...)` at both call sites; preimplementation returns an already-sorted list; field sets and shapes otherwise identical) — confirmed empirically by a 447-review candidate passing *both*. §3.4's Phase A/B ordering rule is load-bearing and correctly derived: probe C (append-and-digest per type on `SEQ-02`) fails structural at **`:350`**, and preimplementation reports exactly 2 stale (`SEQ-02::EVIDENCE`, `SEQ-02::SCOPE`). Row atomicity is therefore a hard constraint, as §3.4/§5.1 state. |
| 4 | 13-key `COMPLETE` set, role/role_binding rules, model/effort shape-only, timestamp-not-before-evidence, evidence currency and component-locality | Line-by-line against `validate_ledger_structural.py:320-355` and `:250-262`, `:206-234` | **All satisfied, each with a proving line.** 13 keys exactly (`assert set(review) == review_fields | role_binding_fields`, `:325`); `review_type` unchanged (`:328`); `reviewer` nonempty (`:340`); `role` asserted twice — membership in `REVIEW_ROLES` then `== "REVIEWER"` (`:257-258`); `role_binding_path == "CONTEXT.md"` (`:259`); `role_binding_sha256` lowercase 64-hex (`:260`) and never re-verified against current bytes (docstring `:253-255` — the design's characterization is exact); `model`/`effort` shape-only, nonempty `str`, never compared to a constant (`:261-262`); `verdict == "CLEAN"` is the sole legal value (`:342`); timestamp UTC RFC3339 and `<= validation_now` (`:343-344`) and `>=` every linked evidence `captured_at` (`:346-349`); `evidence_ref_ids` nonempty (`:345`) and a subset of the row's **own** `local_evidence_ids` (`:331`) — component-locality confirmed. |
| 5 | No fresh user authority required (L886-893, L615-617, L624-626); anything carrying or implying human authority is Critical | Read each cited goal passage verbatim; field-level diff of a full 447-review candidate against the pre-state | **Correct. No Critical.** L615-617 verbatim: "Ordinary `REVIEWER`-role evidence/inventory review remains automated review; it is never an authority-bearing human resolution." L624-626 verbatim: "Neither this completeness review nor a `REVIEWER`-role approval grants any non-delegated authority." L886-893 assigns exactly this work to post-activation autonomous lifecycle step 1. L957-976 (delegated artifact approval) is a different mechanism, correctly identified as not invoked. L1174-1178 grants the repo-local writes the tool needs. Mechanically: across all 213 rows the full-scale candidate changes **only** `evidence_refs` (169), `evidence_inventory_review` (169), `approval_inventory_review` (169), `scope_derivation.semantic_review` (109) — no `approval_records`, no `required_approvals`, no `human_review_id`, no transitions, no controlled state. The 13-key schema has no field able to carry a human authorization. Nothing in the design carries or implies human authority. |
| 6 | Verdict-artifact format, evidence-object validity, digest binding, storage path | Built all 447 evidence objects in the design's exact shape and validated; read goal L450-455 and L1174-1178 | **Valid.** The object is a well-formed typed evidence ref (goal L451-455: globally unique id, repo-relative path, exact scope, `FILE_BYTES`, null line coordinates, `content_sha256`, UTC `captured_at`); `FILE_BYTES` requires `start_line`/`end_line` null (`:220`) — satisfied. Digest binding is exact: `content_sha256` must equal `sha256(target.read_bytes())`, recomputed on every run (`:221`, `:233`). Global `evidence_ref_id` uniqueness is enforced ledger-wide (`:214`); the `EV-<CID>-INVREV-<TYPE>` scheme produced zero collisions across all 447 insertions in my own probe. The `docs/goals/reviews/ledger/inventory/…` path is repository-durable, permitted by L1174-1178, unrestricted by the protected-asset and default-deny sections, and consistent with the existing artifacts in `docs/goals/reviews/ledger/`. The design's rejection of scratchpad paths is correct — `repo_path(..., must_exist=True)` (`:87-95`, `:215`) makes a vanished target a permanent structural failure. |
| 7 | Transaction safety held to the r7 HR-0004 standard (r7 §6.2) | Clause-by-clause comparison of design §3.8 against r7 §6.2 | **Meets the bar as scaled.** Present and correct: nonterminal-journal recovery check; enforced (not merely captured) dirty-tree baseline; prehash and script-hash preconditions; extractor `--check`; structural exit `0` on the live ledger before any write (which also exercises the validator's `bd --readonly` subprocess at `:789-792`, so r7 step 2's external-dependency concern is covered by ordering); atomic-replacement probe inside private staging, renaming over a second existing probe, never inside `docs/goals/`; exclusive-creation temp files with pre-state mode, `fsync` of file and directory, cleanup set under `try`/`finally`; candidate-only validation before replacement; `PREPARED` journal with pre/post hashes, modes, preimage and temp paths; compare-and-swap immediately before a same-directory atomic rename; post-verify of posthash, both validators, and the dirty-path set before `COMMITTED`; rollback restoring bytes **and** mode with verification; `BaseException`/`SIGINT`/`SIGTERM` guard that re-raises after rollback. The scale-down from r7's six-path machinery is principled and correctly argued: r7's journal-sequenced rollback exists because "rename is atomic per path, not across paths"; with one target the single rename *is* the commit point, so no mixed state is representable. Residual hardening gaps are recorded as Minor 9. |
| 8 | Batching / disjointness / BLOCKED-verdict handling; fabricates nothing | Re-derived the constraints; checked §5.4 against the schema and goal L982-1000 | **Sound; nothing fabricated.** Row atomicity and row-disjointness are derived from the digest projections, not chosen (verified in item 3), and single-writer serialization follows from the compare-and-swap. A non-clean verdict is genuinely unrepresentable: `verdict == "CLEAN"` is asserted for every `COMPLETE` review (`:342`) and a `PENDING` review must carry `verdict=null` (`:332-338`). §5.4's handling is correct and honest — the row stays `PENDING` and is dropped from the batch, the artifact is still persisted (goal L987-989: "Conversation text is not evidence"), the finding goes to `open_findings`, and the design correctly notes that `open_findings` is inside `review_input_projection` and so must be written in the same Phase-A window and will stale that row's completed reviews. It correctly routes `blocked_scope`/`delivery_status` blocking (goal L995-997) to a separate transition-writing tool — `blocked_scope` and `delivery_status` *are* in `controlled_direct_fields`, and a transition entry requires nonempty component-local evidence (`:1851-1853`), exactly as stated. **A BLOCKED review can never be recorded as COMPLETE/CLEAN under this design.** |
| 9 | `DISP-R-1` permanent blocker and the `TERM-0001` `required_authority` flag: accurate, consequences stated honestly | Probes B and B2; read `:2674-2686`, `:2688-2763`; recounted lane tokens; read r7 §7 and bd `eqos-sky` | **Both accurate; consequences stated honestly.** Probe B (satisfy `REQ-DISP-R-1-NO-IMPLEMENTATION` *and* refresh digests) yields preimplementation `ready=true`, pending 0 / stale 0 / noimpl 0, exit `0` — but structural fails at **`:2756`**, exit `1`, exactly as §6.3 claims. Probe B2 (linking `EV-DISP-R-1-SPEC-DRAFT` into `DISP-R-1`'s `EVIDENCE` review) fails at **`:2761`**, confirming §3.6 point 2: `review_ok` includes `set(historical) <= set(review["evidence_ref_ids"])` (`:2707-2718`), so the link would remove `CURRENT_REVIEWER_ROLE_EVIDENCE_REVIEW_MISSING`. The blocker is therefore unclearable by any ledger edit, and §3.9/§7.1 say so plainly — including that any plan claiming this tool opens the preimplementation gate is wrong. `TERM-0001`: 123 requirements on exactly 123 rows carry `"Delegated fresh Sol xhigh specification reviewer"`, matching r7 §7's table (123 / 91 / 23, union 123); `eqos-sky` exists and is open. §7.3's open question is correctly flagged as needing settlement before the register batches, and correctly marked out of scope. |
| 10 | Anything a strict validator implementer would stall on | Re-read §3 and §6 as an implementer; checked the validator's importability | Three genuine stalls found, all Minor and all locally resolvable: the impossible/self-contradictory import in §6.2 check 1 (Minor 3), the "three review slots" precondition that no register row can satisfy (Minor 4), and the disposition-item batch arithmetic (Minor 6). None changes the specified mechanism or its safety. |

### Independent reproduction of the terminal state

Reconstructed the design's probe B′ from scratch — 447 reviews across 169
canonical rows, Phase A then Phase B per row, 13-key `COMPLETE` objects, one
`FILE_BYTES` evidence object per review, the `DISP-R-1` carve-out applied
(`EVIDENCE` review links only its own `INVREV` ref; `required_evidence`
untouched), serialized with `sort_keys=True, ensure_ascii=False,
separators=(",",":")`:

- `validate_ledger_structural.py` → exit **`0`**
- `validate_ledger_preimplementation.py --report-blockers` → exit **`2`**,
  `pending_reviews=0`, `stale_reviews=0`, `unmet_no_implementation_proof=1`
  (`DISP-R-1`, reason codes `CURRENT_REVIEWER_ROLE_EVIDENCE_REVIEW_MISSING`,
  `HISTORICAL_REFS_UNCOVERED`, `REQUIREMENT_UNRESOLVED`)
- 44 alias rows and the trailing byte byte-identical; only the 169 canonical
  lines changed

This is exactly the end state §3.9 and §6.4 predict.

### Pre-state facts in §1.2 and §5.2, independently recomputed

All correct: `program_disposition` 148 / 20 / 1; `required_evidence` lengths 0
on all 44 aliases and 1–6 on canonical; `required_approvals` empty on 84 rows
(44 aliases + 40 canonical) and 1–5 on the rest; `evidence_refs` lengths
1 (90) / 2 (100) / 5 (23); 648 transition entries; human-review links `HR-0004`
alone ×111, `['HR-0001','HR-0004']` ×9, `['HR-0002','HR-0004']` ×5,
`['HR-0003','HR-0004']` ×9; 73 canonical rows with `primary_spec=null` carrying
219 reviews. The 25-row per-spec table in §5.2 reproduces exactly, row for row,
and its Reviews column sums with the null-spec row to 447. The §3.7
serialization round-trip reproduces the canonical ledger byte for byte
(`de236d7e…`), and the default-separator variant produces `d3202bee…`, as
stated.

---

## 3. Findings

Zero Critical. Zero Important.

### Minor

1. **§7.5 evidence-object counts are wrong.** Stated "Current: 490 evidence
   objects across 213 rows. After: 937." Actual: **405** before and **852**
   after (90×1 + 100×2 + 23×5 = 405; +447 = 852), a 2.10× increase, not a
   tripling. Not explained by `required_evidence` items either (354; 405+354 =
   759). The flagged risk — measure structural-validator runtime on batch 1 —
   is unaffected, but the figures contradict §1.2's "Every number in this
   document is computed, not transcribed."

2. **§6.4's `evidence_refs` length distribution is wrong in both deltas and row
   classes.** Stated "1/2/5 → 3/4/7 on non-register rows and 1/2/5 → 2/3/6 on
   register rows." Measured on the full-scale candidate: non-register canonical
   **1/2/5 → 4/5/8** (+3, three reviews per row); register **2/5 → 4/7** (+2,
   and no register row has length 1); aliases unchanged at 1. The stated deltas
   (+2 / +1) belong to no row class. Encoding this as a postcondition would
   abort every batch — loudly and harmlessly, but wrongly.

3. **§6.2 check 1 is both self-contradictory and mechanically impossible as
   written.** It requires digests "obtained by importing the same functions from
   the checked-in `validate_ledger_structural.py`", while §3.1 states the
   recorder "must never import from or write to the validator scripts." The
   validator is also not importable: it is straight-line with a module-level
   `parser.parse_args()` (`:18-25`) and no `if __name__ == "__main__"` guard, so
   an import would consume the recorder's own `sys.argv` and execute the entire
   validation as a side effect. Effect is contained — §3.8 step 5's candidate
   validation catches any transcription drift definitively at `:350`/`:353`
   before the rename — but an implementer stalls here. Specify the extraction
   mechanism (e.g. `ast`/`exec` of the two function definitions from the
   checked-in file) or drop the check in favour of step 5.

4. **§3.8 step 2's "Every target row's three review slots are `PENDING`" cannot
   hold for a register row**, which has `scope_derivation.semantic_review =
   null` and only two slots — as §1.2 of the same document states. Taken
   literally the precondition rejects all 60 register rows in batches 12–17.
   Should read "applicable review slots", matching §5.1.

5. **Three imprecise goal citations in §1.2.** `L233-236` is cited for the
   register-row `semantic_review=null` rule; that passage is about
   `source_register_ids`/`applicable_spec_ids` array hygiene, and the actual
   rule is at ~L274-278 (which §5.2 cites correctly as "L~262-278"). `L379` and
   `L452-453` are cited for alias review nullity; L377-381 concerns
   `REJECTED_PROPOSAL` approval records and L450-455 is the `evidence_refs`
   schema. Only `L623-624` is on target. The underlying claims are true — I
   verified both mechanically and against the embedded validator asserts — and
   the primary citation (`validate_ledger_preimplementation.py:200-204`) is
   exact, so this is citation hygiene, not a substantive error.

6. **§5.2 batch rows 6–8 are internally inconsistent.** `DISP-R-1` *is* one of
   the 32 `disposition_item` rows, so isolating it in its own batch leaves 31
   rows across the other two batches (~15–16 each), not "3 batches (~11 rows
   each)". Either state 4 batches or restate the sizes.

7. **§5.2's per-spec table sits under "Secondary axis within `register_row`" but
   tabulates all 96 spec-owning canonical rows.** All 60 register rows carry a
   `primary_spec`, but so do 36 non-register canonical rows (e.g. S10's 8 rows
   include a `disposition_item` and a `scale_trigger`). Sizing batches 12–17
   directly from this table would pull non-register kinds into the register
   batches, contradicting the batch table above it. The table's numbers are
   exact; only its placement invites the error.

8. **Dangling internal cross-reference.** §6.3 says "No canonical file was
   modified (§7 restates `git status`)", but §7 is "Risks and open questions"
   and contains no `git status`. The claim itself is consistent with the
   unchanged working tree I observed.

9. **Transaction hardening gaps against r7 §6.2**, each defensible given
   single-path atomicity but worth closing or explicitly waiving in r1:
   (a) no exclusive repository-local lock (r7 §6.2 step 1) — the compare-and-swap
   prevents lost updates but leaves a small window between prehash comparison
   and rename; (b) no rejection of a symlinked or non-regular *ledger* target
   (the design applies the regular-file check only to verdict artifacts);
   (c) no `RECOVERY_REQUIRED` terminal journal state for a rollback that cannot
   prove both bytes and mode — the design names only `PREPARED`, `COMMITTED`,
   `ROLLED_BACK`; (d) **no mandatory rollback rehearsal before the first real
   run**, which r7 §6.2 requires precisely because the rollback path has never
   been executed — and §7.9 concedes this design's journal/rollback/`SIGINT`
   path is specified but untested. The residual risk is materially smaller than
   r7's: one atomic rename admits no mixed state, the candidate is validated
   before replacement, and git holds the preimage.

10. **447 `model` values naming a vendor model enter the ledger, and §7.3 does
    not mention it.** The design reasons carefully about lane tokens in
    `required_authority` but never notes that recording itself writes
    `"claude-opus-5"` (or whatever was invoked) into 447 review objects. This is
    contract-required and contract-permitted — the schema mandates `model`, the
    validator compares it to no constant (`:261-262`, comment `:243-245`), it is
    a historical invocation record rather than an obligation string, and r7's
    prohibition covers new *obligation* strings — but one explicit sentence
    would stop a future lane audit or `TERM-0001` follow-on from misreading
    these 447 values as in-scope drift.

---

## 4. Assessment

The design is mechanically sound and unusually well evidenced. Every load-bearing
claim I tested held at the exact line numbers cited: the 447/109/169/169 counts,
the transition rejection at `:1909`, the staling at `:350`, the `DISP-R-1`
assertions at `:2756` and `:2761`, the 13-key schema and every field rule at
`:320-355`, the serialization round-trip, and the full pre-state fact set. The
two genuinely counter-intuitive results — that recording is transition-free and
*forbids* a transition, and that completing all 447 reviews still leaves the
preimplementation gate closed on a structurally-mandated `DISP-R-1` blocker —
are correct, independently reproduced here, and stated without hedging. The
`REQ-DISP-R-1-NO-IMPLEMENTATION` trap in particular is the kind of finding that
would otherwise have been discovered by a failed canonical write.

The design also declines to overreach: it writes no approval machinery, claims
no authority, routes blocking and human-review creation to separate tools, and
names its own untested surface in §7.9. Its largest stated risk — that 447
genuine `REVIEWER` dispatches cannot be mechanically distinguished from lazy
ones — is real, correctly characterized as a dispatch-discipline problem, and
honestly left unmitigated.

The Minor findings are two arithmetic errors in descriptive sections, three
implementer stalls that are resolvable in a line each, citation hygiene, and
four hardening items against the r7 bar. None affects the correctness, safety,
or authority posture of the specified mechanism, and none can produce a
fabricated, unauthorized, or invalid ledger record.

Verdict: CLEAN
