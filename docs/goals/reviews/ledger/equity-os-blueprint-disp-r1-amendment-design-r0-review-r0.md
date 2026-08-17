# Independent review — DISP-R-1 amendment design r0

| Field | Value |
|---|---|
| Reviewed path | `docs/goals/reviews/ledger/equity-os-blueprint-disp-r1-amendment-design-r0.md` |
| Reviewed-input SHA-256 | `675cb4877d9eef6b49ea8b825c8dc11fa9f1b5363e88df0dbc657e3d52727326` (recomputed at start **and** end — identical) |
| Role | `REVIEWER` |
| Role binding path | `CONTEXT.md` |
| Role binding SHA-256 | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` (recomputed at start **and** end — identical) |
| Model | `claude-opus-5` |
| Effort | `high` |
| UTC timestamp | `2026-08-15T12:39:33Z` |
| Independence | I authored none of the reviewed material and did not build the Implementer's probes; every result below is from my own probes under `scratchpad/disp-r1/review/`. |

**No canonical byte, Beads record, or Git state was changed.** All seven §0
pre-state hashes plus the S20 spec hash were re-verified byte-identical at the
start and end of this review. `git status` shows only the three paths that were
already dirty before I began.

**Reviewer's own probes** (all read-only w.r.t. canonical files):

| Probe | Purpose |
|---|---|
| `scratchpad/disp-r1/review/rev_build.py` | Rebuilds the candidate goal + validators from the design's own §3.2–3.4 fenced blocks |
| `scratchpad/disp-r1/review/rev_attack.py` | Deadlock horns + 14 independent attempts to fake a DISP-R-1 proof |
| `scratchpad/disp-r1/review/rev_interaction.py` | Recorder-vs-proof conflict I1/I3/I4 |
| `scratchpad/disp-r1/review/rev_hr0005.py` | The §5.7 option-(b) `HR-0005` question the design left untested (B0–B4), plus B5 |

---

## Per-item verification table

| # | Item | Method | Result |
|---|---|---|---|
| 1a | Horn A — satisfying the requirement fails structural at `:2756` | Built a properly evidenced candidate ledger myself (requirement `SATISFIED` + `COMPLETE`/`CLEAN`/`REVIEWER` evidence review sealed against the post-state row); ran canonical structural | **CONFIRMED** — exit 1, `AssertionError` at **line 2756** |
| 1b | Horn B — leaving it unresolved keeps `ready=false` | `validate_ledger_preimplementation.py --repo-root . --report-blockers` on canonical bytes | **CONFIRMED** — exit 2, `ready=false`, `pending_reviews`=447, `stale_reviews`=0, exactly one `unmet_no_implementation_proof` for `DISP-R-1`/`REQ-DISP-R-1-NO-IMPLEMENTATION` with the three reason codes as stated |
| 1c | Cited lines are exact | `grep -n` on `validate_ledger_structural.py` | **CONFIRMED** — `:2671` map, `:2674` literal, `:2688` predicate, `:2752` `disp_r1 = by_id[...]`, `:2756`, `:2760`, `:2761-2763` all exact |
| 1d | SUCCESS condition 5 demands *current* no-implementation proof | Read goal `:5752-5756`; read the terminal program's `rejected` loop | **CONFIRMED** — condition 5 verbatim as quoted; terminal asserts `proven` for every rejected row |
| 1e | Prose/validator contradiction; `DISP-R-1` appears once outside the program spans | `grep -n DISP-R-1` filtered against the three fence spans (`1357-4599`, `4608-4864`, `4874-5699`) | **CONFIRMED** — 19 total hits, exactly **one** outside the spans, at `:5831` (HR-0004 approval record) |
| 1f | r7 §3.6 / §8.1 quotes | Read r7 `:576-593`, `:1541-1551`, `:1702-1705` | **CONFIRMED verbatim.** The §1.5 "deliberate vs over-implementation" split is correctly labelled *inference*, and I agree with the calibration |
| 2a | Amendment is reproducible and ledger-neutral | Rebuilt the candidate from the design's own before/after blocks; each `before` span occurs **exactly once**; hashed | **CONFIRMED** — candidate goal = `ed92d7ba…39155039a`, candidate structural = `ba9c730f…3353619d4c61`, candidate preimplementation = `f7a225a1…` (byte-identical to canonical). Amended structural on the **unchanged canonical ledger** → exit **0**; amended preimplementation report **byte-identical** to the canonical baseline |
| 2b | Four named forbidden shortcuts still fail | Built S1–S4 myself | **CONFIRMED** — all rejected (S1 `:2789`, S2 `:2775`, S3 `:2762`, S4 `:346` inside `validate_inventory_review` called from `:2152`) |
| 2c | Ten further attacks I invented | Built A5–A14 | **ALL REJECTED.** Wrong evidence ref `:2786`; forged `IMPLEMENTER` role `:258`; third status value `:2125`; duplicate requirement object `:2119`; extra key on the requirement `:2762`; requirement deleted `:2704`; historical refs emptied `:1693`; `program_disposition` flipped `:1565`; empty `model`/`effort` `:261`; null `reviewed_*` digests `:350` |
| 2d | Three "missing" conjuncts enforced globally | Read `:233`, `:261-262`, `:350-355`; confirmed the evidence loop and `validate_inventory_review` call sites are unconditional | **CONFIRMED in substance.** See Minor M1 — the design cites `:352-357`; the actual span is `:350-355` |
| 2e | **Any way to fake a DISP-R-1 proof after the amendment?** | 14 independent constructions | **NONE FOUND.** No Critical here |
| 3 | `extract_goal_validators.py --check` still passes | Ran the extractor against my own candidate goal | **CONFIRMED** — D.1 required-marker and D.2 lane-token checks both pass on the candidate; `--check` → exit **0** after extraction. See Minor M2 |
| 4a | r2 §3.6 forbids exactly the ref the proof needs | Read r2 `:453-484` | **CONFIRMED verbatim** |
| 4b | The conflict is real and the union resolves it | Built the recorder post-state myself and ran the amended validator | **CONFIRMED** — I1 exit **0**; I3 (digests recomputed, `EVIDENCE` review omits the spec ref) exit **1** at `:2789`; I4 (union) exit **0** |
| 4c | "T1 may land at any time" | Reasoned against the option-(b) post-state | **FALSE under the user's decision** — see **F3** |
| 5 | S20 can honestly support the requirement | Read all 268 lines of `docs/specs/equity-os-s20-memory-benchmark-gbrain.md` | **CONFIRMED — yes.** Every §2.3 line cite is exact (`:7`, `:17`, `:20`, `:35`, `:39`, `:174`, `:251`). See ruling below |
| 6 | Transaction design at the r7 bar | Read r7 §6.2 `:1044`, §6.3 `:1130`, §8.2 `:1562`, §8.3 `:1637` | **Sound for the two-file scope**, but **incomplete for the scope the user has now chosen** — see **F4** |
| 7 | §6 approval question | Byte inspection of line 843 | Single-line blockquote, 3332 chars, backticks balanced, exactly two placeholder tokens, 9 concrete hashes — **all 9 independently verified**, including both post-state hashes. Header correctly states design-only. **But the question states option (a)** — see **F1** |
| 8 | `APR-DISP-R-1-01` / S20 header ruling | Read r7 §3.8 `:688-712`; read the terminal program's `active` and `rejected` loops | **CONFIRMED both halves.** r7 §3.8 scopes its role-vocabulary replacement to the review schema and reason codes; `required_authority` belongs to §3.7. Terminal's `required_approvals`-SATISFIED assertion is `for row in active`; `DISP-R-1` is in `rejected`, whose loop requires only `proven`, a non-null rejection record, empty `implementation_refs`, and a non-advanced `delivery_status`. It gates nothing today |

---

## Findings

### F1 — Critical — Option (b), which the user has chosen, is blocked by a fourth pinned assertion the design did not find; §5.2, §5.4, §5.6, §6 and §7.3 are all false under it

§5.7 lists option (b) as "3 files (adds the canonical human-review artifact)"
and marks the risk as merely "**Untested.** I did not verify that adding
`HR-0005` passes structural validation." I tested it. It does not, and the
reason is not a corner case — it is a hard pin that the amendment as designed
does not touch.

Verified by construction (`rev_hr0005.py`, all against my rebuilt amended
structural validator):

| Probe | Construction | Result |
|---|---|---|
| **B0** | `HR-0005` with an empty component scope (the only shape that would keep the ledger untouched) | exit 1 — `assert projected`, structural **`:832`**. *Every* human-review entry must project at least one component |
| **B2** | `HR-0005` scoped `DISP-R-1`, ledger row **not** linked | exit 1 — **`:1209`**. Every canonical component in an entry's scope must carry that entry ID in its row's `human_review_id` |
| **B1** | `HR-0005` scoped `DISP-R-1`, ledger row linked, no transition appended | exit 1 — `assert replay == controlled_state(row)`, **`:2083`**. `human_review_id` is a controlled field; changing it requires an appended transition object |
| **B4** | Fully correct option (b): entry + `RECONCILE_AUTHORITY` resolution `HRD-0005-001` + ledger link + appended `AUTHORITY_RECONCILIATION` transition `TR-DISP-R-1-004` + recomputed `transition_history_sha256` | exit 1 — **`:2821`** `assert overlapping == set().union(*EXPECTED_PRIOR_HR_LINKS.values())` (and `:2822` `assert len(overlapping) == 23`). `DISP-R-1` now carries two HR links, so it enters `overlapping`, which is pinned to exactly the 23 HR-0001..3 rows |
| **B5** | The identical B4 candidate, run against a scratch validator with only that pin relaxed to `… \| {"DISP-R-1"}` / `== 24` | exit **0** |

B5 is the proof that nothing *else* blocks option (b) — and equally the proof
that the pin at `:2821-2822` is a real, additional, load-bearing blocker.

Consequences for the design as written, all of which must change:

1. **§3.3/§3.4 are not the whole amendment.** A **fourth** exact span
   replacement is required in the goal's structural program, relaxing the
   `overlapping` / `len(overlapping) == 23` pin to admit the new link. Design
   the relaxation two-sidedly, as §3.1 rightly insists — do not simply delete it.
2. **§3.5 "The canonical ledger: zero rows change" is false.** `DISP-R-1`'s
   `human_review_id` and `transition_history_sha256` both change, and one
   transition object is appended (454-prefix invariant survives — prefix length
   for `DISP-R-1` is 2, verified at `:2867` — but §5.6 postcondition 7's "T1
   appends no transition" is false).
3. **§3.7 T3 is no longer a property of the transaction.** T3 remains true of
   the *goal/validator* change in isolation; it is not true of T1.
4. **§5.2's scope table and both post-state hashes are wrong.**
   `ed92d7ba…` and `ba9c730f…` are the post-state of the three-span amendment
   only. Adding the fourth span changes both. The scope becomes **four**
   canonical files: goal, structural validator, human-review artifact, ledger.
5. **§5.3 rehearsal, §5.4 P2/P3, §5.6 postconditions 1, 2, 3, 6, 7, 9** all
   need reworking. Note especially that structural validation takes
   `--ledger-path` and `--human-review-path` as a required *pair* (`:26`), so
   the rehearsal must validate the candidate ledger and candidate human-review
   artifact together.
6. **§6's question is not the question to ask.** §6 explicitly self-guards
   ("Do not ask this question until §5.7 is settled"), which is correct
   discipline — but the settlement has now happened, and the question as
   written would authorize a two-file package that provably fails structural
   validation.

*This is not a "the reviewer prefers (b)" finding.* Under option (a) the
document is internally coherent. The user has settled §5.7 as (b), and under
(b) the design is not executable as written.

### F2 — Important — The design specifies no `HR-0005` content; the goal's human-review entry schema requires a complete one

§5.7 names option (b) as "a new `HR-0005` entry and `RECONCILE_AUTHORITY`
resolution" and stops there. That is a one-line gesture, not a specification,
and it is now the load-bearing part of the transaction. Read from the live
schema (`validate_ledger_structural.py:909-1103`), an executable `HR-0005`
must carry **exactly** the following, or the transaction cannot land:

**Entry** — exactly the 15 `entry_fields`, no more, no fewer:

- `human_review_id` = `"HR-0005"`, matching `HR-\d{4}`, not already present;
- `entry_type` = `"DECISION"` (so `security_exception_detail` must be `null`);
- `scope` = exactly the six `scope_fields_human` keys, each list sorted and
  deduplicated, `scope_text` non-empty, and — per B0 — a **non-empty projected
  component set**. `component_ids` must be `["DISP-R-1"]` (the only row the
  amendment's authority actually touches); `register_ids`, `spec_ids`,
  `bead_ids`, `blocked_component_ids` all `[]`;
- non-empty `question`, `why_human_external`, `recommendation`, `safe_default`.
  The `question` should be the §6 question rewritten for the four-file scope;
- `evidence`: at least one evidence object whose `content_sha256` matches
  **live bytes**, whose `captured_at` ≤ validation time, and whose `path` is
  neither the ledger nor the human-review artifact. HR-0004's precedent binds
  its entry evidence to a `UTF8_LINE_SPAN` over the goal's *own post-state
  approval-record span* (`goal:5791-5847`) — **if HR-0005 follows that
  precedent the goal must also gain an approval-record section, which is a
  fifth changed span and a self-referential digest ordering the design does not
  address.** Binding instead to this design document and its review at their
  final bytes avoids that and is the cleaner choice;
- `continuable_work` list; `blocking` bool;
- `decision_authority` = exactly `{approval_type, authority, competent_roles}`,
  with `approval_type` ∈ `approval_types − {DELEGATED_ARTIFACT_APPROVAL}` —
  `GOAL_OR_PROCESS_AUTHORIZATION` per the HR-0004 precedent — and non-empty
  `competent_roles` containing the resolving actor's role;
- `state` exactly as derived (`"RESOLVED"` once the resolution exists);
- `resolution_decision_ids` = the exact ordered list;
- `content_sha256` = `canonical_sha256(entry minus content_sha256)`.

**Resolution** — exactly the 15 `resolution_fields`:

- `sequence` = the next index in the global resolution list (**1**, since
  `HRD-0004-001` is index 0);
- `record_type` = `"DECISION"`; **`decision_type` must be
  `"RECONCILE_AUTHORITY"`** — the closed `decision_types` set contains no
  `AMEND_VALIDATOR_PIN`, so §6's prose label cannot be the recorded type;
- `human_review_id` = `"HR-0005"`; `scope` **identical** to the entry's scope
  object; `actor` = exactly `{identity_id, display_name, role, actor_type}`
  with `actor_type = "HUMAN"` and `role` ∈ the entry's `competent_roles`;
- `authority_basis` = exactly `{approval_type, authority, role, evidence_ids}`
  with the first two equal to the entry's `decision_authority` and non-empty
  `evidence_ids` drawn from entry+resolution evidence;
- `timestamp` ≥ `HRD-0004-001`'s timestamp and ≤ validation time, and ≥ every
  cited evidence object's `captured_at`;
- `supersedes_decision_id` = `null` (no prior active decision on this entry),
  `revokes_decision_id` = `null`;
- `entry_authority_sha256` = `canonical_sha256(entry minus {state,
  resolution_decision_ids, content_sha256})`;
- `previous_resolution_sha256` = `HRD-0004-001.content_sha256`;
- `content_sha256` = `canonical_sha256(resolution minus content_sha256)`.

**Ledger transition** — one appended object on `DISP-R-1`, exactly the 14
`transition_fields`: `transition_id` `"TR-DISP-R-1-004"`, `sequence` 4,
`transition_type` `"AUTHORITY_RECONCILIATION"`, `field` `"human_review_id"`,
`old_value` `"HR-0004"`, `new_value` `["HR-0004","HR-0005"]` (append-only link
growth is enforced at `:2071-2073`), non-empty `evidence_ref_ids` ⊆ the row's
local evidence IDs, `human_resolution_decision_id`/`human_resolution_sha256`
bound to `HRD-0005-001`, `previous_entry_sha256` = the current tail's
`entry_sha256`, and a recomputed `entry_sha256`; then
`transition_history_sha256` recomputed over the five `entry_sha256` values.

I verified this whole shape end-to-end in B4/B5 — it is correct, and only the
`overlapping` pin stands between it and exit 0.

### F3 — Important — §7.3's "T1 may land at any time" no longer holds; T1 must precede the recorder

§7.3's first clause is justified solely by T3 ledger-neutrality and I1. Under
option (b), T1 mutates `DISP-R-1`'s `human_review_id` and
`transition_history_sha256`. Both are inside `review_input_projection`
(`:280`, `:282`) and `human_review_id` is also inside the `APPROVAL` inventory
projection (`:316`). So if the recorder seals `DISP-R-1`'s three reviews first
and T1 lands afterwards, all three reviews go **stale** and structural
validation fails. The ordering rule must be restated as a strict chain:

> **T1 first, then the 447-review recorder, then T2 last.**

The design's own I5 result (the blast radius of a `DISP-R-1` change is confined
to that row's three reviews) is the mechanism; it just was not applied to T1
itself, because under option (a) T1 changed no row. Risk R1 and R8 both need
this third ordering constraint added.

### F4 — Important — §4.3, §5.3 and §5.4 do not cover the artifacts option (b) adds

- **§4.3 "What must exist BEFORE T1 can run"** lists four items and states
  "Notably **absent**: no S20 review, no evidence capture, no recorder output."
  That remains true, but the list is now incomplete: it must also require the
  drafted `HR-0005` entry, its resolution, and the `DISP-R-1` transition object
  at their exact final bytes, since the user's approval must bind them.
- **§5.3 rehearsal** covers goal and validator hashes only (steps 1–5). It must
  additionally build the candidate ledger and candidate human-review artifact,
  bind their post-state hashes, and — because the pair is required at `:26` —
  run structural against both together.
- **§5.4 P2/P3** run the candidate validators against the *canonical* ledger and
  human-review artifact. Under (b) they must run against the *candidate* ones,
  and P3's expectation must be restated: `ready=false`, `pending_reviews`
  still 447, `stale_reviews` 0, and the `DISP-R-1` unmet entry unchanged
  (I confirmed the entry is unaffected by the `human_review_id` change — B5
  reaches exit 0 with the requirement still `UNRESOLVED`).
- **§5.5 journaled replacement** is written for two files. Four files must move
  atomically or none: the ledger and human-review artifact are mutually
  referential through `human_review_links`, and the goal and validator through
  `--check`.

---

## Minor findings

- **M1 — line-cite drift.** §2.4 and §3.6 cite `:352-357` for the review-digest
  recomputation; the actual span is **`:350-355`**. §2.4 cites `:341-348` for
  the verdict/timestamp block; actual **`:340-349`**. §1.4 cites goal
  `:461-474` for the A6 paragraph; it begins at **`:460`**. Substance is
  correct in every case.
- **M2 — §5.4 P1 is not runnable in isolation.** `extract_goal_validators.py
  --check` with explicit `--*-output` paths exits **1** (`stale generated
  validators`) unless those files already exist with matching content; only
  after §5.3 step 4's extraction does it exit 0. I reproduced both. P1 should
  say "after step 4" explicitly, so an executor does not read it as an
  independent gate.
- **M3 — §5.6 postcondition 9's git enumeration is incomplete.** It names
  `.beads/issues.jsonl` (modified) and `record_inventory_review.py`
  (untracked), but omits the design document itself — untracked at `??` right
  now — and the predetermined review artifact, which will also be untracked.
- **M4 — §3.7 T5's rejection lines are construction-dependent.** My
  independently built S2 rejects at `:2775` (the `UNRESOLVED` branch's
  `assert disp_r1_proven is False`), not at `:2152`, because I sealed the
  review digests against the post-state row. Both are correct rejections of the
  same shortcut class; the table should read "rejected, e.g. at …" rather than
  asserting a unique line.
- **M5 — §6's "preserves all 454 existing transition objects" is imprecise.**
  454 is the sum of `BASELINE_PREFIX_LENGTHS` (the pinned *prefix* invariant);
  the live ledger holds **648** transition objects. The wording mirrors
  HR-0004's approved question, so it is consistent with precedent, but under
  (b) it will need rewording anyway since one object is appended.
- **M6 — §3.8's extractor-marker judgment call.** I agree with the design's
  choice to leave `REQUIRED_MARKERS` alone: the D.1 check is a presence check
  over prose outside the program spans, the new paragraph sits directly under
  the A6 marker, and the D.2 lane-token check passed on my candidate. No
  finding; recording that I examined it.

---

## Ruling on item 5 — can S20 honestly support the proof?

**Yes.** I read all 268 lines. The requirement's description — "Current S20
draft preserves D-02 as dormant and contains no implementation claim" — is a
fair and complete description of the file's current bytes:

- **D-02 preserved:** `:20` records the R-1 disposition as *Reject* — "The
  proposal to cancel D-02 is rejected; S20 retains it" — and `:17` quotes the
  D-02 register row with Status `Deferred`, annotated "Dormant benchmark
  contract."
- **Dormant:** `:7` "S20 is dormant-only … it does not activate any row,
  install GBrain, run a benchmark, or approve adoption." `:35` maps D-02
  `Deferred` → `CONDITIONAL_UNACTIVATED`, "do not run or claim results."
  `:39` forbids `PLANNED`/`IMPLEMENTING`/`VERIFIED` without valid activation.
- **No implementation claim:** the entire document is written in contract mood.
  `:174` "D-02, D-04, and D-05 implementation/delivery references remain absent
  while their individual Status is Deferred." `:251` "Structural checks prove
  no owned Deferred row has implementation references or an active delivery
  state before its own valid activation." The acceptance-test list at `:234-253`
  is explicitly prefaced "**After valid activation** of the applicable rows",
  and `:223` states "This file claims no approval." I found no results, no
  benchmark output, no adoption decision, and no delivery reference anywhere in
  the file.
- **The digest binding is correct.** `EV-DISP-R-1-SPEC-DRAFT` is `FILE_BYTES`
  over the whole spec and matches live bytes
  (`4948d0f8…be9c483`), which is why `HISTORICAL_REF_STALE` does not appear in
  the reason codes. The design's argument that `FILE_BYTES` is strictly
  stronger than a line span for a whole-file negative claim is right.

Two qualifications, both material:

1. **This is a corroborating read, not the required review.** The proof needs a
   `REVIEWER`-role evidence review recorded on the ledger row at a real
   timestamp, and I am the reviewer of *this design document*, not of S20. My
   agreement removes a risk (that the design rests on a claim the artifact
   cannot bear); it does not supply the evidence. The design says the same in
   §2.3 and is right to.
2. **The S20 header (`:3`, "AWAITING FRESH SOL XHIGH REVIEW") does not
   contradict the requirement.** It is a statement about the *approval* gate
   (`APR-DISP-R-1-01`, `DELEGATED_ARTIFACT_APPROVAL`), not about implementation.
   Per item 8, that approval gates nothing today. It does mean the two
   prohibited-lane strings are still sitting on the row and in the spec header;
   the design is right to flag them and right to leave them out of scope.

---

## What `HR-0005` requires that r0 lacks — summary

r0 names `HR-0005` in one table cell and one recommendation sentence. It lacks,
in order of consequence:

1. **The fourth amendment span** relaxing the `overlapping` /
   `len(overlapping) == 23` pin at `:2821-2822` — without which `HR-0005`
   cannot exist at all (F1, probe B4/B5).
2. **The ledger mutation and its transition object** — `DISP-R-1`
   `human_review_id` → `["HR-0004","HR-0005"]`, appended
   `AUTHORITY_RECONCILIATION` transition, recomputed
   `transition_history_sha256` (F1, F2).
3. **The complete `HR-0005` entry and `HRD-0005-001` resolution**, at the exact
   field sets, digests, chain links and closed-vocabulary values enumerated in
   F2 — including that the recorded `decision_type` must be
   `RECONCILE_AUTHORITY`, not `AMEND_VALIDATOR_PIN`.
4. **Four post-state hashes instead of two**, a rehearsal and proof-command set
   that exercises the candidate ledger and human-review artifact as a pair, and
   postconditions rewritten accordingly (F4).
5. **A reissued §6 question** naming the four-file scope, the `HR-0005` record
   it creates, and the one appended transition — replacing the current
   two-file, zero-ledger-change, zero-transition question (F1.6).
6. **A strict ordering rule** — T1 before the recorder before T2 (F3).

---

Verdict: BLOCKED — 1 Critical, 3 Important, 6 Minor
