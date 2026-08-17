# Independent review — DISP-R-1 amendment design r1

| Field | Value |
|---|---|
| Reviewed path | `docs/goals/reviews/ledger/equity-os-blueprint-disp-r1-amendment-design-r1.md` |
| Reviewed-input SHA-256 | `fd00a14ae7dcc3e7aa6854d307f46a7f9503278ec8c49f77a388a7b1d1ab75ee` (recomputed at start **and** end — identical) |
| Role | `REVIEWER` |
| Role binding path | `CONTEXT.md` |
| Role binding SHA-256 | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` (recomputed at start **and** end — identical) |
| Model | `claude-opus-5` |
| Effort | `high` |
| UTC timestamp | `2026-08-16T13:52:32Z` |
| Independence | I authored none of the reviewed material and reused none of the Implementer's probes nor the r0 reviewer's probes. Every result below comes from my own constructions under `scratchpad/disp-r1/review-r1/`. |

**No canonical byte, Beads record, or Git state was changed.** All eight §0
pre-state hashes were re-verified byte-identical at the start and end.
`git status` at the end shows exactly the five paths that were already dirty
before I began: `.beads/issues.jsonl` (modified) and untracked
`docs/goals/reviews/ledger/equity-os-blueprint-disp-r1-amendment-design-r0.md`,
`…-design-r1.md`, `docs/goals/reviews/ledger/inventory/`,
`scripts/equity_os_blueprint/record_inventory_review.py`. I did not touch
`scratchpad/inventory-reviews/`, `docs/goals/reviews/ledger/inventory/`, or
`scripts/equity_os_blueprint/`.

**My probes** (all read-only w.r.t. canonical files, all under
`scratchpad/disp-r1/review-r1/`):

| Probe | Purpose |
|---|---|
| `extract_spans.py` | Enumerates the design's fenced blocks so the spans under test are r1's own bytes, not a retyping |
| `build.py` | Rebuilds the candidate goal + all three extracted validators from those blocks |
| `hr0005.py` | Builds the complete `HR-0005` entry / `HRD-0005-001` resolution / `TR-DISP-R-1-004` transition four-file package from §4 |
| `run.py` | F1: canonical vs amended validator on that package |
| `attacks.py` | Shortcuts K1–K4b, laundering attacks H1–H9, ordering J1/J4/J5, span-D edge cases E1/E2 |
| `stage/` | A real staging repo root with the amended goal at its canonical path (the N1 proof) |

---

## Per-item verification table

| # | Item | Method | Result |
|---|---|---|---|
| **1a** | Canonical validator dies at `:2821-2822` without span D | Built the full `HR-0005` candidate myself (entry + `RECONCILE_AUTHORITY` resolution + ledger link + appended `AUTHORITY_RECONCILIATION` transition + recomputed `transition_history_sha256`), ran the **canonical** structural validator | **CONFIRMED** — exit 1, `AssertionError` at **line 2821**, `assert overlapping == set().union(*EXPECTED_PRIOR_HR_LINKS.values())`. Exactly the Critical r1 claims |
| **1b** | With r1's span D applied **exactly as written**, the same candidate validates | Applied spans B/C/D verbatim from the design's own fenced blocks, re-extracted, ran the amended validator on the identical package | **CONFIRMED — exit 0.** Span D provably works |
| **1c** | Span D is two-sided (no `HR-0005` ⇒ byte-equivalent to today) | Amended validator against the **canonical** ledger + human-review pair | **CONFIRMED — exit 0** |
| **1d** | Span D admits `HR-0005` and nothing else | E2: an otherwise byte-identical entry named `HR-0006` | **REJECTED** at candidate `:2820` (span D's first assert) |
| **1e** | Spans are line-neutral and reproduce r1's pinned post-state hashes | Independent rebuild from §3.2–3.5 | **CONFIRMED.** B 13→13, C 13→13, D 6→6, each `before` occurring **exactly once**. Candidate goal = `fa527d076b4bfb6b3e627d7d8fbda799cad3117f9db6ce0d8088d256ec898304`; candidate structural = `59053b0bb7173055a8c768907e6ddb9f1bbab8cc48f2f639ded04b9526170419`; candidate preimplementation = `f7a225a1f99cb85c92cde3094505a92a746552280eb45dae0253a71ab9048013` (byte-identical to canonical); 3244 → 3244 lines. **Both §6.2.1 post-state hashes reproduce exactly** |
| **2a** | `HR-0005` entry — all 15 `entry_fields`, all in-vocabulary | Built every field per §4.1 against the live schema `:910-915`; ran it | **CONFIRMED.** `HR-\d{4}` match, `HR-0005` absent from the live entries (`HR-0001..HR-0004`), `entry_type=DECISION` ⇒ `security_exception_detail=null`, six `scope_fields_human` keys with sorted/deduped lists and non-empty `scope_text`, `decision_authority` exactly the three keys with `GOAL_OR_PROCESS_AUTHORIZATION` (member 1 of `approval_types`, `:836`, and ∉ the `DELEGATED_ARTIFACT_APPROVAL` exclusion), `state=RESOLVED` derived, `content_sha256` over the entry minus itself. No out-of-vocabulary value; no missing field |
| **2b** | `HRD-0005-001` — all 15 `resolution_fields` | Built per §4.2 | **CONFIRMED.** `sequence=1` (the live payload holds exactly one resolution, `HRD-0004-001` at index 0); `previous_resolution_sha256` = `f263f2dabc91ad1186a813564c485b2edec5c83720624c2e7a49e6d43d3f9dc7`, which I read from the canonical artifact and which **is** `HRD-0004-001.content_sha256`; `entry_authority_sha256` over entry minus `{state, resolution_decision_ids, content_sha256}`; `scope` object-identical to the entry's; actor `HUMAN`/`CURRENT_USER` ∈ `competent_roles`; `authority_basis` first two fields equal to `decision_authority`; both null-required fields null. **Every digest basis is the one the validator recomputes** |
| **2c** | `decision_type` **must** be `RECONCILE_AUTHORITY` | Read the closed `decision_types` (`:994-999`); ran H3 | **CONFIRMED, three independent reasons.** (i) `AMEND_VALIDATOR_PIN` is **not** in `decision_types`, so it can never be recorded; (ii) `transition_resolution(entry, row, {"RECONCILE_AUTHORITY"})` at `:2077` is the only route for an `AUTHORITY_RECONCILIATION` change to `human_review_id`; (iii) span D pins it. H3 (`SATISFY_APPROVAL`, an in-vocabulary but wrong type) is **rejected** |
| **2d** | `TR-DISP-R-1-004` — all 14 `transition_fields` | Built per §4.3 | **CONFIRMED.** `sequence=4` (the live row holds `TR-DISP-R-1-000..003`); `previous_entry_sha256` = `b121cf3000723f2130d934ccd548d8e07035a52371e90e0ef37f652707bdfb51`, which I read as the live tail's `entry_sha256`; `old_value="HR-0004"` → `new_value=["HR-0004","HR-0005"]` satisfies append-only link growth; `evidence_ref_ids=["EV-DISP-R-1-SOURCE"]` ⊆ the row's own IDs; `transition_history_sha256` recomputed over the five `entry_sha256` values. Live transition-object count 648 → 649 |
| **3** | r0's other Important and Minor findings fixed | Item-by-item | **CONFIRMED — all fixed.** F2 §4 (2a–2d above). F3 §8.3 (item 6). F4 §5.3/§6.3/§6.4/§6.5. M1: `:340-349`, `:350-355`, goal `:460`–`:474` all **exact**. M2: reproduced — `--check` with not-yet-written `--*-output` paths exits **1**, `stale generated validators`. M3: postcondition 13's enumeration matches my `git status` **exactly**. M4: both attack tables read "Rejected, e.g. at". M5: 454 is the prefix sum over 210 keys with `DISP-R-1`=2; the live count is **648**, freshly measured. M6: recorded |
| **4** | The four forbidden shortcuts still fail after all four spans | Built K1–K4b myself on the `HR-0005` post-state, run against the amended validator | **ALL REJECTED.** no-review `:2767`; historical-refs-only (review links the historical ref, requirement `UNRESOLVED`) `:2764`; `SATISFIED` with empty refs `:2141`; identity tampering on `description` `:2760` and on `scope` `:2760`; digest refresh (evidence recaptured after the review) `:350`. A capture refresh alone leaves the row in the `UNRESOLVED` branch with proof still false |
| **4b** | Any way at all to fake a DISP-R-1 proof? | 14 constructions: K1, K2, K2b, K3, K3b, K4, K4b, H1–H9, E1, E2 | **NONE FOUND.** No Critical here. The only route to the `else` branch is a genuine `COMPLETE`/`CLEAN`/`REVIEWER` review sealed against the post-state row (positive control: exit 0). Laundering through a new HR entry fails at every angle — different scope `:1198`, widened scope `:1209`, wrong `decision_type` `:1108`, no resolution `:1915`/`:1209`, no transition `:2083`, no link `:1209`, `REFERENCE_APPEND` `:2079`, `IMPLEMENTER` actor `:1041`, `DELEGATED_ARTIFACT_APPROVAL` `:946`, non-`HR-0005` entry `:2820` |
| **5** | `extract_goal_validators.py --check` on the amended goal | Run with explicit paths after extraction, **and** canonically (no arguments) inside the staging root with the amended goal at its canonical path | **CONFIRMED — exit 0 both ways**, including the D.1 required-marker and D.2 lane-token checks |
| **6** | Ordering rule vs the recorder — sound, complete, and current live state | Built J5/J1/J4 myself; inspected the live ledger | **CONFIRMED and SOUND.** J5 (recorder seals `DISP-R-1` first, T1 lands after, no re-seal) → **exit 1** at `:350`, the `reviewed_input_sha256` mismatch inside `validate_inventory_review` — the mechanical proof of F3. J1 (T1 first, then seal) → **exit 0**. J4 (recorder re-runs after T2 and drops the union) → **exit 1** at `:2767`. **No already-recorded row is affected:** the live ledger and human-review artifact are still byte-identical to §0, the ledger holds **0 COMPLETE reviews of 447**, and there is no `docs/goals/reviews/ledger/inventory/DISP-R-1/` directory. The recorder has produced 109 review *documents* but has sealed **nothing** into the ledger, so neither remedy (i) nor (ii) is needed today — T1 can simply land first. The second reason for "T2 last" also checks out: the recorder's own postcondition requires `len(unmet_no_implementation_proof) == 1`, and my T2 post-state reports 0 |
| **7a** | The four post-state hashes | Independent rebuild + row-by-row diff | **Two CONFIRMED exactly** (goal `fa527d07…`, structural `59053b0b…`). The other two are declared placeholders; see **M4** below — I agree they are not pre-derivable |
| **7b** | The 15 postconditions | Checked each against my construction | **14 of 15 verified as stated.** Postcondition 9 is **wrong on one number** — see **F1**. Postcondition 5 verified: goal `5791-5847` digest is `1647f803ac50eb03ab9d702822cc724c16b26e31f75d444ead8e0cee36d4df30` before *and* after, and line 5847 is still the last line of the HR-0004 record. Postcondition 8 verified: preimplementation on the post-state is **exit 2, `ready=false`, `pending_reviews`=447, `stale_reviews`=0**, with the `DISP-R-1` unmet entry **byte-identical** to §0's. Postconditions 10, 11, 12, 13 verified |
| **7c** | Rehearsal (§6.3) | Executed its substance in a staging repo root | **SOUND.** Step 8's insistence on a real repo copy rather than symlinks is correct and necessary: with the amended goal at its canonical path, `--check` → 0, amended structural on the `HR-0005` post-state → 0, span digest `1647f803…`, preimplementation → 2/447/0. **Negative control:** an r0-style +70-line goal in the same staging root fails at **`:892`**, `assert evidence["content_sha256"] == digest`. N1 is real and R-A remedies it |
| **7d** | N1 blast radius | Enumerated every reference into the goal across the ledger and the human-review payload | **CONFIRMED — exactly one:** `HR-0004`/`HR-EV-0004-APPROVAL-RECORD`, `UTF8_LINE_SPAN` 5791–5847. No row has `source_path` equal to the goal |
| **7e** | §7 approval question | Byte inspection of line 1075 | Single-line blockquote, 4904 chars, **no embedded newline**, 130 backticks (**balanced**), ends `?`, exactly the four declared placeholder tokens, **10 concrete 64-hex hashes — all 10 independently verified**. Header and line 3 both state DESIGN ONLY / NOT APPROVED FOR EXECUTION, and the question is framed as a question to be asked, so it **presupposes no approval the user has not given**. **But one factual count in it is wrong — see F1** |
| **8** | §6.7 / N2 | Ran `--reconciliation-check` today | **CONFIRMED** — aborts at `:2923`, the baseline-ledger hash assertion, before any other check. No fifth span is needed |
| **9** | Miscellaneous cited facts | Direct read | **CONFIRMED:** goal SUCCESS condition 5 at `:5752-5756` verbatim; the A6 paragraph at goal `:460-474` verbatim; `DISP-R-1` occurs 19 times in the goal, exactly **one** outside the three program spans, at `:5831`; `BASELINE_PREFIX_LENGTHS` has 210 keys summing to **454** with `DISP-R-1`=2; `:26` asserts the ledger/human-review pair; `:2138-2141` carries the `UNRESOLVED` ↔ empty-refs coupling; `CONTEXT.md:137-138` defines `REVIEWER` and `:147` binds it to Claude Opus 5, high effort; `record_inventory_review.py` contains **zero** occurrences of `EXPECTED_DISP_R1_REQUIREMENT` or `disp_r1_proven` |

---

## Findings

### F1 — Important — "the other 209 rows" is wrong; the correct count is **212**, and it appears both in an executable postcondition and in the exact bytes the user is asked to approve

The canonical ledger holds **213** rows (`wc -l` = 213, 213 non-blank lines,
213 unique `component_id`s). T1 changes exactly one of them. The other rows
therefore number **212**, not 209.

Verified by construction, not by arithmetic alone. I diffed my independently
built four-file post-state against the canonical ledger row by row:

```
rows total: 213   changed: ['DISP-R-1']   unchanged: 212
fields changed on DISP-R-1: ['human_review_id', 'transition_history', 'transition_history_sha256']
transition objects: 648 -> 649
```

Everything else in that sentence is exactly right — one row, those three
fields, 648 → 649. Only the count of untouched rows is wrong, and 209
corresponds to no quantity in the system I could find (the nearest neighbour is
210, the number of keys in `BASELINE_PREFIX_LENGTHS`, minus one).

It occurs twice, and both occurrences matter:

1. **`:1009`, §6.6 postcondition 9** — "A byte diff of the other 209 rows shows
   no change." This is an instruction an executor must discharge, and as
   written it cannot be discharged: there are 212 such rows. The postcondition's
   *substance* ("**Exactly one** ledger row changed … and on it exactly three
   fields") is correct and I confirmed it; only the count is wrong.
2. **`:1075`, the §7 approval question** — "leaving the other 209 rows, every
   requirement status, every approval record, and all 447 `PENDING` inventory
   reviews byte-unchanged." This is the byte string the user's rank-1 authority
   would attach to, that `HR-0005.question` is to carry, and that
   `HR-EV-0005-DESIGN` binds by digest. Under the r7/HR-0004 bar every count in
   that question is load-bearing; approving a description that misstates the
   ledger is exactly what the hash-binding exists to prevent.

This is not Critical: it enables no bypass, permits no fake proof, and would
not by itself cause an incorrect canonical write. It is Important because it
**must be corrected before the question is asked**, and correcting it changes
this document's bytes, hence `<DISP_R1_DESIGN_SHA256>`, hence the review the
approval binds — so it cannot be patched after approval.

**Remedy:** replace both occurrences of `209` with `212`. Nothing else in §6.6
or §7 needs to change; I re-verified every other count in the question (23
overlap rows, 144 HR-0004-scoped rows, 447 pending reviews, 0 stale, 454 prefix
entries, 648 → 649 transition objects, four files, three fields, sequence 4).

---

## Minor findings

- **M1 — line-cite drift throughout §4, which is new text in r1 and so is not
  covered by r0's M1 correction.** Substance is correct in every case — I built
  each field against the live schema and the package validates — but an executor
  reading the cites will land one to five lines off. Actual lines:
  §4.1 `scope_text` non-empty is **`:937`** (not `:936`); the projected-set
  non-empty assert is **`:831`** and the ⊆-`by_id` assert is **`:832`** (not
  `:832`/`:833`); the derived-`state` block is **`:1090-1098`** and
  `resolution_decision_ids` is **`:1099`** (not `:1089-1099`/`:1100`).
  §4.2 entry-exists is **`:1018`** (not `:1017`); `scope` identity **`:1027`**
  (not `:1023`); actor key set **`:1029`** (not `:1025`); `actor_type=="HUMAN"`
  **`:1030`** (not `:1026`); actor strings **`:1031-1034`** (not `:1027`);
  `authority_basis` key set **`:1036`** (not `:1031`); the equality checks
  **`:1038-1041`** (not `:1034-1041`); `evidence_ids` non-empty/⊆
  **`:1048-1049`** (not `:1046-1047`); `timestamp <= validation_now`
  **`:1051`** (not `:1049`); the monotonic-vs-previous check **`:1052-1053`**
  (not `:1051`); evidence-`captured_at` **`:1055-1060`** (not `:1054-1058`);
  `entry_authority_sha256` **`:1020-1026`** (not `:1019-1022`); the
  `REVOCATION` arm **`:1080`** (not `:1076`).
  §4.3 `old_links < new_links` **`:2074`** (not `:2072`);
  `new_links <= set(human_entries)` **`:2075`** (not `:2073`); the
  `AUTHORITY_RECONCILIATION` requirement **`:2076-2077`** (not `:2075-2076`);
  `transition_history_sha256` **`:2086-2088`** (not `:2085-2087`).
  §2.4 `required_evidence` inside `review_input_projection` is **`:280`** (not
  `:277`) — note §8.3 cites `:280`, `:282`, `:316` and those three are exact.

- **M2 — §8.3's recorder cite.** `record_inventory_review.py:1070` is the
  message string; the check itself is at **`:1067`**
  (`if len(report["unmet_no_implementation_proof"]) != 1:`). Substance correct,
  and I confirmed T2's post-state reports 0, so the recorder would indeed fail
  its own postcondition if it ran after T2.

- **M3 — §3.5's "candidate `:2820`" for H1/H2 is construction-dependent.** My
  independently built H1 (`HR-0005` scoped elsewhere) and H2 (`HR-0005` scoped
  to `DISP-R-1` plus a second row) are rejected earlier, at **`:1198`** and
  **`:1209`**, by the per-row reverse-link checks, before span D is reached.
  r1's own M4 caveat covers this, but §3.5 states the scope assertion is
  "load-bearing, not decorative" on the strength of H1/H2 specifically, and
  those two do not in fact demonstrate it. It **is** load-bearing — my E2
  demonstrates it cleanly: an otherwise byte-identical entry named `HR-0006` is
  rejected at candidate **`:2820`**, and E1 (entry with no resolution and no
  link) is rejected at `:1209`. Recommend swapping the E2-style construction in
  as the §3.5 justification.

- **M4 — two of the four §7 placeholders stand for post-state bytes of files
  that already exist, not for nonexistent files.** `<LEDGER_POST_SHA256>` and
  `<HUMAN_REVIEW_POST_SHA256>` are placeholders for values the user cannot see
  when approving. I traced the dependency and **agree they are not
  pre-derivable**: the ledger post-state hash depends on the transition's
  `human_resolution_sha256`, which is `HRD-0005-001.content_sha256`, which
  covers the resolution `timestamp` — the instant of the approval itself.
  Fixing that timestamp in advance would be fabrication, so there is no
  construction that removes the dependency. §6.2.3, §7, R8, §6.3 step 7 and
  postcondition 3 all state and mitigate it honestly. Residual risk, stated for
  the record: the user approves two hashes sight-unseen, and the compensating
  control is that postconditions 9, 11 and 12 bound the construction tightly
  enough that no materially different post-state can satisfy them. Note this is
  *stronger* than the HR-0004 precedent, whose approved question (goal
  `:5803-5826`) bound no post-state hashes at all.

- **M5 — pre-existing, not introduced by this amendment.** A `COMPLETE`
  review's `reviewer`, `model`, `effort` and `role_binding_sha256` are never
  cross-checked against any external record — `role_binding_sha256` is only
  required to be 64 hex (`:259`), deliberately, per its docstring. So the
  `else` branch the amendment opens ultimately rests on the honesty of whoever
  records T2's review. r1 flags precisely this as R4 and is right that it is
  inherent to any content review. Recording that I looked for a structural
  bypass here and found none; this is a property of the review schema for all
  447 reviews, not a weakening introduced by span C.

---

## Ruling on the Critical

r1's Critical is real and r1's fix works. I reproduced both halves by
construction rather than by reading: the canonical validator dies at **line
2821** on a fully-formed `HR-0005` package I built myself, and with r1's span D
applied **exactly as written** — extracted verbatim from the design's own
fenced block, not retyped — the identical package reaches **exit 0**, while the
canonical ledger/human-review pair still reaches exit 0 under the same amended
validator. Span D is two-sided, admits `HR-0005` and no other entry, and closes
the nine laundering routes I tried.

N1 is also real, and its remedy holds end-to-end: in a staging repo root with
the amended goal at its canonical path, `HR-EV-0004-APPROVAL-RECORD` still
recomputes to `1647f803…`, whereas an r0-style line-adding goal in the same
root fails at `:892`.

The single Important finding is a wrong integer in the approval question and in
postcondition 9. It is mechanical to fix and it does not disturb any other
result in this review — every hash, every attack rejection, every ordering
result above was computed against the design's actual spans and would be
unchanged by correcting `209` to `212`. But because the question is the
authority record and this document's digest is bound into `HR-0005`, it must be
corrected and re-reviewed before the question is asked.

---

Verdict: BLOCKED — 0 Critical, 1 Important, 5 Minor
