# Independent review — DISP-R-1 amendment design r3

| Field | Value |
|---|---|
| Reviewed path | `docs/goals/reviews/ledger/equity-os-blueprint-disp-r1-amendment-design-r3.md` |
| Reviewed-input SHA-256 | `4755b62b8367b1dfa1ce6da5f40d79a069e7f2f43814b8a32fc82ad4b0a473dc` (recomputed at start **and** end — identical) |
| Role | `REVIEWER` |
| Role binding path | `CONTEXT.md` |
| Role binding SHA-256 | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` (recomputed at start **and** end — identical) |
| Model | `claude-opus-5` |
| Effort | `high` |
| UTC timestamp (start / end) | `2026-08-17T14:36:35Z` / `2026-08-17T14:51:24Z` |
| Independence | I authored none of the reviewed material. I did not read or reuse the Implementer's `scratchpad/disp-r1/build-r3/` probes, nor the r0/r1/r2 reviewers' probes. Every result below comes from my own constructions under `scratchpad/disp-r1/review-r3/` and two throwaway staging roots. I read the Implementer's build report (`scratchpad/disp-r1/build-r3/build-r3-report.md`) as a claim to be falsified, and every number in it that I quote below I re-derived myself first. |

**No canonical byte, Beads record, or Git state was changed.** All eight §0
pre-state hashes were re-verified byte-identical at the start and end.

**My probes** (all read-only w.r.t. canonical files):

| Probe | Purpose |
|---|---|
| `build.py` | Enumerates r3's fenced blocks positionally and rebuilds the candidate goal + all extracted validators from r3's **own bytes**. Takes the round as `argv[1]`, so `build.py r2` is my calibration control. Also emits the column census |
| `pkg.py` | Builds the `HR-0005` four-file package from §4 and the live schema, plus attacks A1/A2/E2 (rebuilt independently) and my own B1-B6, each run against **canonical**, **r2 span D** and **r3 span D** |
| `pkg2.py` | Attacks on span D's enclosing guard and on the routes where the overlap *count* still matches (B3, B7-B10) |
| `stage.py` | Real repo copies with the amended goal **and** amended validator at their **canonical** paths — P1-P4, gate neutrality, and a line-shifting negative control |

---

## Per-item verification table

| # | Item | Method | Result |
|---|---|---|---|
| **1** | §0's eight pre-state hashes | `sha256sum` at start and end | **ALL EIGHT CONFIRMED, unchanged.** `f15f7ab5`, `de236d7e`, `094fcdfa`, `731d0d8b`, `f7a225a1`, `5d20d796`, `8f2795af`, `4948d0f8`. Superseded-round hashes also confirmed: r0 `675cb487…`, r1 `fd00a14a…`, r2 `d96a4bf6…` |
| **2** | My harness is calibrated, not tuned to r3 | `build.py r2` against r2's fenced blocks | **CONFIRMED.** Reproduces r2's published `fa527d076b4bfb6b3e627d7d8fbda799cad3117f9db6ce0d8088d256ec898304` and `59053b0bb7173055a8c768907e6ddb9f1bbab8cc48f2f639ded04b9526170419` **exactly**, and r2's span D line at **687** characters. Only then did I run it against r3 |
| **3** | Spans are line-neutral; r3's two pinned post-state hashes | Extracted r3's fenced spans by my own fence enumeration, applied to the canonical goal, re-extracted with the canonical extractor | **CONFIRMED, both hashes exact.** Each `before` occurs **exactly once**; B 13→13, C 13→13, D 6→6. Goal 5894 → 5918 with all growth below 5847; first/last differing line **4028 / 4176**. Candidate goal = **`b77ea73d90fb6f7499a7fcf74f50c471bb03dd5a6f1bf0c71f510af917d0b0c9`**; candidate structural = **`77faeaf3dee13d5d2bfb50c255b054cde94ef0118751b247e23248e343964fff`**; candidate preimplementation **byte-identical** to canonical `f7a225a1…`; structural 3244 → 3244 lines; `extract_goal_validators.py --check` → exit **0** |
| **4** | r3's delta from r2 is *only* span D | Line diff of my two extracted candidate validators and of the two candidate goals | **CONFIRMED — exactly one line differs.** Candidate structural `:2822` (goal `:4176`); nothing else. Span B and span C digests are byte-identical between r2 and r3. Since span C's asserts execute at `:2756-2768`, strictly **before** `:2822`, r3's decision not to re-run the K-shortcuts and the J-chain is sound *by construction*, and §3.8 discloses the decision rather than implying coverage |
| **5** | Spans land at the cited lines | `awk` over my candidate validator | **CONFIRMED.** B at candidate `:2674-2686`, C at `:2756-2768`, D at `:2817-2822`, with `:2820` = the overlap equality and `:2822` = the conformance assert |
| **6** | The Critical still reproduces: canonical validator dies at `:2821` | Built the full `HR-0005` four-file package myself (entry + `RECONCILE_AUTHORITY` resolution + ledger link + appended `AUTHORITY_RECONCILIATION` transition + recomputed `transition_history_sha256`) from §4 and the live schema | **CONFIRMED — exit 1 at line 2821**, `assert overlapping == set().union(*EXPECTED_PRIOR_HR_LINKS.values())` |
| **7** | **F1 — span D now enforces EXACTLY ONE active `RECONCILE_AUTHORITY` resolution; my independently rebuilt A1 is REJECTED** | Rebuilt the A1 state from scratch: `HR-0005` with `resolution_decision_ids: []`, `state: "OPEN_BLOCKING"`, scoped to `{"DISP-R-1"}`, `DISP-R-1` linked `["HR-0004","HR-0005"]` by an appended transition whose `human_resolution_decision_id` **recycles HR-0004's own `HRD-0004-001`**. Ran the identical package bytes against all three validators | **CONFIRMED — FIXED, and F1 independently reproduced first.** `canonical → exit 1 :2821` · **`r2 span D → exit 0`** (the review's F1, reproduced on my own bytes) · **`r3 span D → exit 1 at :2822`**. The recycling is legal exactly as r2's review said — `transition_resolution` (`:1772-1779`) requires only that the row lie in the citing entry's scope, and I confirmed `DISP-R-1` is one of HR-0004's **144** scoped components |
| **8** | The fix is exact, not merely sufficient | Read `:1089-1099` against canonical bytes | **CONFIRMED.** `:1091` is the global `assert len(active_ids) <= 1`; `:1099` is `assert entry["resolution_decision_ids"] == all_by_entry[entry_id]`, and `all_by_entry` is a `defaultdict(list)` accumulated over **all** resolutions (`:1086`), not just active ones. So `len(...) == 1` pins exactly one resolution in existence, and the trailing list equality forces that one to be active, `HUMAN`, `CURRENT_USER`, `RECONCILE_AUTHORITY`, under `GOAL_OR_PROCESS_AUTHORIZATION`. r3 §3.5's justification is accurate |
| **9** | Two-sidedness survives the fix | Amended validator on the untouched canonical ledger + human-review pair, and on the conforming `HR-0005` package | **CONFIRMED — exit 0 in both directions, under both r2's and r3's span D.** A2 (superseded + active) → `:2822`; E2 (conforming entry named `HR-0006`) → `:2820`. Both rebuilt by me, not taken on report |
| **10** | **Attack on the amended validator — actor, decision-type, authority-type** | My own B1/B2/B5 | **ALL REJECTED.** B1 (`actor_type=AGENT`) → `:1030`; B2 (`decision_type=SATISFY_APPROVAL`) → `:1108`; **B5 (`approval_type=PRODUCT_OWNER_DECISION`, otherwise conforming) → `:2822`** — B5 is the clean proof that span D's `decision_authority.approval_type` conjunct is load-bearing and reachable, not shadowed by an earlier check |
| **11** | **Attack — laundering via a third entry on `DISP-R-1`** | My own B7: conforming `HR-0005` **plus** `HR-0006` also scoped to and linked to `DISP-R-1` | **REJECTED at `:2822`.** This is the sharpest test of the amendment: `overlapping` is still exactly `base ∪ {"DISP-R-1"}` and `len` is still 24, so **both** of span D's first two asserts pass. Only the explicit `human_review_links["DISP-R-1"] == frozenset({"HR-0004","HR-0005"})` conjunct catches it. That conjunct is genuinely load-bearing |
| **12** | **Attack — can any *other* row enter `overlapping`?** | My own B3 (`HR-0006` double-linking `DISP-R-2`, an `HR-0002` row) and B10 (`HR-0006` double-linking `DEF-01`, an HR-0004-only row) | **BOTH REJECTED.** B3 → `:2814` (`EXPECTED_PRIOR_HR_LINKS` pin); B10 → **`:2820`** the amended overlap equality. §3.9's "no other row may ever enter `overlapping`" is verified by construction, not argued |
| **13** | **Attack — can span D be skipped entirely?** | Span D is **not** top-level; it sits under `if "HR-0004" in human_entries:` (`:2788`). My own B8 (drop the `HR-0004` entry) and B9 (drop it *and* strip `HR-0004` from every row's links) | **GUARD UNREACHABLE.** B8 → `:1196`; B9 → `:1105`. Link removal is separately blocked by the append-only `assert old_links < new_links` (`:2074`) and the `replay == controlled_state(row)` check (`:2083`). No claim in r3 depends on span D being unguarded, and I AST-verified the claim r3 *does* make (§1.2): `:2752`, `:2753`, `:2756`, `:2757`, `:2760`, `:2761`, `:2764` are all top-level nodes, and `:2912-3244` contains **zero** `DISP-R-1`/`no_implementation` hits |
| **14** | **Attack — ordering** | The J-chain was not re-run for r3 and r3 says so. I verified the *precondition* for that disclosure instead (item 4) and re-measured the projection membership §8.3 turns on | **DISCLOSURE SOUND, one cite wrong.** `review_input_projection` (`:264-286`) does contain `human_review_id` (`:282`) and `transition_history_sha256` (`:283`) and `required_evidence` (`:280`), so J5's substance holds. The cite pair printed in §8.3 is wrong — see **N1(b)** |
| **15** | **N1 (line-anchoring) and remedy R-A, end-to-end** | Built a real repo copy with the amended goal **and** amended validator at their **canonical** paths, plus a negative control with the goal shifted +70 lines | **CONFIRMED end-to-end.** P1 `extract_goal_validators.py --check`, **no arguments**, run inside the staging root → **exit 0**. P2 amended structural on the `HR-0005` post-state → **exit 0**; on the canonical pair → **exit 0**. P4 span `5791-5847` digest → **`1647f803ac50eb03ab9d702822cc724c16b26e31f75d444ead8e0cee36d4df30`**, reproduced with the validator's **own** `resolve_utf8_line_span` semantics (`"\n".join(lines[5790:5847]).strip(...)`), and byte-identical between canonical and candidate. **Negative control → exit 1 at `:892`**, `assert evidence["content_sha256"] == digest`. N1 is real and R-A remedies it |
| **16** | Gate neutrality (T1 moves the gate by zero rows) | Preimplementation on my post-state ledger vs on canonical, both `--report-blockers` | **CONFIRMED — the two reports are string-identical.** Both `exit=2`, `ready=False`, `pending_reviews`=**447**, `stale_reviews`=**0**, and one unmet entry: `DISP-R-1` / `REQ-DISP-R-1-NO-IMPLEMENTATION`, historical ref `EV-DISP-R-1-SPEC-DRAFT`, reason codes `CURRENT_REVIEWER_ROLE_EVIDENCE_REVIEW_MISSING`, `HISTORICAL_REFS_UNCOVERED`, `REQUIREMENT_UNRESOLVED` — identical to §0 |
| **17** | §7 approval question **mechanics** | Byte inspection of the reviewed file | **CONFIRMED.** Single-line blockquote at line **1234**, **4924** characters, **no** embedded newline, lines 1233 and 1235 both blank; ends with `?`; **130** backticks, balanced; exactly the **four** declared placeholder tokens and no others (`<DISP_R1_DESIGN_SHA256>`×2, `<DISP_R1_REVIEW_SHA256>`, `<HUMAN_REVIEW_POST_SHA256>`, `<LEDGER_POST_SHA256>`) — a regex sweep for `<...>` returns those five occurrences and nothing else. It **presupposes no approval**: the header line 3 banner and §7's own preamble both state DESIGN ONLY / NOT APPROVED, and the text is framed as a question to be answered |
| **18** | **Every hash in the §7 question** | Independent measurement of all 10 | **ALL 10 CONFIRMED, 10 distinct values, no duplicates.** Seven §0 pre-state hashes re-measured from live bytes; `b77ea73d…` and `77faeaf3…` reproduced by my own rebuild; `1647f803…` reproduced with the validator's own span semantics. **Neither `fa527d07` nor `59053b0b` appears in the question** — r2's dead hashes survive in r3 only in three places that explicitly label them dead or use them as my calibration control |
| **19** | **Every count in the §7 question** | Independent measurement of each | **ALL CONFIRMED.** 213 rows (`wc -l` = 213, 213 unique `component_id`s) → **212** unchanged ✔; **3** fields on `DISP-R-1` ✔; `TR-DISP-R-1-004` at sequence **4** (history length 4) ✔; **23** `overlapping` rows, equal to the live `EXPECTED_PRIOR_HR_LINKS` union ✔; **454** prefix sum over **210** keys with `DISP-R-1` = 2 ✔; **648 → 649** live transition objects ✔; **447** pending / **0** stale ✔; four files ✔; goal lines 1-5847 and span 5791-5847 ✔. **The "carries exactly one active `RECONCILE_AUTHORITY` resolution" clause — r2's F1 — is now true of the span D bytes**, proved by item 7 |
| **20** | §6.6 postconditions 9-12 | Row-by-row diff of my post-state against canonical | **ALL VERIFIED.** pc 9: changed rows = `['DISP-R-1']`, 212 unchanged, exactly the three named fields ✔. pc 10: 648 → 649, `DISP-R-1` history 4 → 5, appended at sequence 4, `history[:2]` unchanged so the 454 **prefix** manifest is untouched ✔. pc 11: entries = `{HR-0001..HR-0005}`, `resolutions` length 2, `HR-0005.state == "RESOLVED"` ✔. pc 12: requirement still `UNRESOLVED` with empty refs, all **447** reviews still `PENDING` ✔. pc 5 ✔ (item 15), pc 6/7/8 ✔ (items 3/15/16), pc 1/2 ✔ (item 3), pc 4 ✔. pc 13 — see **N2** |
| **21** | r2 review **M1** (over-long lines) fixed | My own column census on my extracted r3 candidate | **CONFIRMED EXACT.** Span C **8 of 13** over 79 columns at widths `:2758` 81, `:2759` 132, `:2760` 143, `:2762` 102, `:2764` 138, `:2765` 100, `:2767` 130, `:2768` 129 — matching §3.4 value for value. Span D **3 of 6**: `:2817` 82, `:2820` 92, **`:2822` 735**. Canonical program **126** lines over 79, widest **99**. The "+48 characters from the F1 fix" claim checks out: 735 − 687 = 48. R6 restated to match |
| **22** | r2 review **M2** (`:2820` mislabelled) fixed | Read §3.5, §3.8 H-table, §8.2; cross-checked against my own attack lines | **CONFIRMED.** `:2820` is labelled "span D overlap equality" at both H-table rows and in the note below; span D is now grounded on A1/A2 (`:2822`) and E2 (`:2820`), which is exactly what my constructions hit. §8.2 gains the construction-dependence caveat and records that J5's `:1135` is the call site of the r2 reviewer's deeper `:350` — I confirmed `:350-352` is the `reviewed_input_sha256` recomputation |
| **23** | r2 review **M3** (pc 13 stale enumeration) fixed | Read pc 13; re-measured `git status --porcelain` twice | **FIXED IN SUBSTANCE — the authoritative form is now the quoted re-measure-and-journal instruction** and the snapshot is explicitly labelled "not a postcondition". That is the right disposition. The snapshot's own arithmetic is wrong — see **N2** |
| **24** | r2 review **M4** (§9.2 item 6 dead premise) fixed, and consistency with the orchestrator pre-decision | Read the header, §4.4, §5.3 item 2, §7, §9.2 item 6; hashed both copies of the r1 review; checked all three prior review paths | **CONFIRMED, AND CONSISTENT WITH THE PRE-DECISION.** Item 6 is closed rather than patched. r0, r1 and r2 reviews all exist at `…-design-r<N>-review-r0.md`; the r1 review at that path is **byte-identical** to the scratchpad copy (both `ad07b96942100a8b18562d2907ecd6c5da6ebace7f1eb9979379132984d874b1`), so r2's dead parenthetical is correctly retired. **r3 binds `…-design-r3.md` and `…-design-r3-review-r0.md`** in the header, §4.4, §5.3 item 2 and the §7 question — the required re-pointing is done, and the residual condition (re-point again if the r3 review lands elsewhere) is recorded |
| **25** | r2 review **M5** (two names for two placeholders) fixed | `grep` across the whole document | **CONFIRMED.** `<DESIGN_R1_SHA256>` / `<REVIEW_R0_SHA256>` survive at exactly two lines (921, 1579), both of which *record their retirement*. Every live use is `<DISP_R1_DESIGN_SHA256>` / `<DISP_R1_REVIEW_SHA256>` |
| **26** | r2 review **M6** ("line-for-line") fixed | `grep` | **CONFIRMED.** The §7 question reads "preserves the **line count and numbering** of goal lines 1-5847". The string "line-for-line" survives only at line 1580, in §13's description of the fix. A related imprecision remains in the same sentence — see **N5** |
| **27** | Changelog / §12 / §13 provenance | Hashed every cited artifact and read every cited verdict line | **ALL CONFIRMED.** r2 review = `1f228878ded7c8d2b7bb7d6c85e5c8aab5ab2d079a656c5e9a9177835d83d496`, verdict line reads exactly `BLOCKED — 0 Critical, 1 Important, 6 Minor` ✔. r1 review `ad07b969…`, `BLOCKED — 0 Critical, 1 Important, 5 Minor` ✔. r0 review `BLOCKED — 1 Critical, 3 Important, 6 Minor` ✔. The N1-N6 ↔ M1-M6 mapping is stated in §13 and is order-preserving, and §13 warns against confusing it with this document's own §10 N1/N2 |
| **28** | §4 field-by-field spec, re-measured against the live schema | Read `:799-1099`, `:1732-1758`, `:2060-2088` and checked every cite in §4.1-§4.3 | **CONFIRMED — every field value, digest basis and cite is exact**, including `:910-915`, `:916-919`, `:924`, `:926`, `:934`, `:937`, `:831`, `:832`, `:942`, `:943`, `:945`, `:946-948`, `:836`, `:951`, `:975`, `:953`, `:1090-1098`, `:1099`, `:980-983`, `:1008`, `:1009`, `:1010`, `:1011-1016`, `:1018`, `:1020-1026`, `:1027`, `:1029`, `:1030`, `:1031-1034`, `:1036`, `:1038-1041`, `:1048-1049`, `:1051`, `:1052-1053`, `:1055-1060`, `:1061`, `:1063`, `:1064-1066`, `:1080`, `:1062`, `:1744-1749`, `:1750-1753`, `:2070`, `:2074`, `:2075`, `:2076-2077`, `:2083`, `:2086-2088`. Independently confirmed live values: `HRD-0004-001.content_sha256` = `f263f2dabc91ad1186a813564c485b2edec5c83720624c2e7a49e6d43d3f9dc7`, `DISP-R-1` tail `entry_sha256` = `b121cf3000723f2130d934ccd548d8e07035a52371e90e0ef37f652707bdfb51`, current `transition_history_sha256` = `27733590d3ced98b9f6943c7f31a09fa6b8312625b510efd9a91429cc166481d`. One cite is one line off — see **N1(d)** |
| **29** | Miscellaneous cited facts | Direct read / measurement | **CONFIRMED.** Goal SUCCESS condition 5 at `:5752-5756` verbatim ✔; A6 paragraph at goal `:460-474` verbatim ✔; `DISP-R-1` occurs **19** times in the goal, exactly **one** outside the three program spans, at `:5831` ✔; `:2138-2141` is the `UNRESOLVED` ↔ empty-refs coupling ✔; `:2707-2709`/`:2719` carry the coverage test ✔; `:233`, `:250-262`, `:325`/`:327`, `:340-349`, `:350-355` ✔; preimplementation `:128`/`:132`/`:217` ✔; §6.7's `:2923`/`:2926` pin `51091042…`/`54c1e183…` and `:3034`/`:3035` are as described ✔; `CONTEXT.md:137-147` binds `REVIEWER` ✔; `194` transitions across `144` rows cite `HRD-0004-001` ✔; §9.2 item 5's substance holds — `record_inventory_review.py` contains **zero** occurrences of `EXPECTED_DISP_R1_REQUIREMENT` or `disp_r1_proven` ✔ |
| **30** | Nothing outside my own files changed | `git status --porcelain` at start and end | **CONFIRMED, with one exception that is not mine.** All my probes live under `scratchpad/`, which `.gitignore:8` excludes. The only delta between my start and end measurements is `docs/goals/reviews/ledger/equity-os-blueprint-inventory-review-recording-design-r4.md`, mtime **14:38:55Z** — written by the concurrent 447-review workstream *during* this review, two minutes after my baseline. I did not create, modify or read-modify any file under `docs/` other than writing this review |

---

## Findings

**No Critical findings. No Important findings.** F1 is fixed by construction and
I proved it on state I built myself, not by reading r3's prose: the same A1
package bytes reach exit 0 under r2's span D and exit 1 at `:2822` under r3's,
while the conforming package and the untouched canonical pair both still reach
exit 0. Every M1-M6 disposition is verified the same way — by re-measurement,
not by taking the disposition table at its word.

The five minor findings below are precision defects. **None changes an enforced
control, none falsifies a claim about what the amended validator does, and none
requires re-deriving either pinned post-state hash.** They can all be fixed
without touching a fenced span, so `b77ea73d…` and `77faeaf3…` survive any fix
to them — which is what distinguishes them from r2's F1.

### Minor findings

- **N1 — four line cites are measurably off.** This document's whole discipline
  is cite precision, and three prior rounds corrected exactly this class, so
  these are worth naming even though the substance is right in every case:
  - **(a) §0, the `454` row: `validate_ledger_structural.py:2907`.** Measured,
    `assert sum(BASELINE_PREFIX_LENGTHS.values()) == 454` is at **`:2897`**.
    `:2907` is `assert canonical_sha256(baseline_prefix_projection) ==
    BASELINE_PREFIX_DIGEST` — the prefix *digest*, a different assert. Inherited
    verbatim from r2 line 85 and never re-measured. (§9.2 item 3's separate
    `:2902-2907` cite for "the prefix check" is correct and should stay.)
  - **(b) §8.3: "both are inside `review_input_projection` (`:280`, `:282`)"**
    for `human_review_id` and `transition_history_sha256`. Measured,
    `human_review_id` is at `:282` and `transition_history_sha256` at **`:283`**;
    `:280` holds `"tracked_work", "required_evidence", "evidence_refs"` and
    neither named field. The correct pair is `:282`, `:283`.
  - **(c) §5.2 item 1** quotes goal `:447-448`. The quoted sentence — "The
    validator never fills these digests, and this draft contains no fabricated
    live review values." — spans goal **`:446-447`**; `:448` is blank.
  - **(d) §4.4: "`start_line`/`end_line` `null` (required for `FILE_BYTES`,
    `:879`)".** `:879` is the branch test `if evidence["digest_mode"] ==
    "FILE_BYTES":`; the assert that imposes the requirement is **`:880`**. This
    is the weakest of the four — the cite arguably points at the branch that
    imposes it — but the neighbouring cites in the same paragraph (`:873`,
    `:874-876`, `:878`) all point at asserts, so the convention is inconsistent.

- **N2 — §6.6 postcondition 13 says "eleven" paths and then enumerates twelve.**
  The enumeration is `.beads/issues.jsonl` + `record_inventory_review.py` +
  `inventory/` + the **six** `…-design-r{0,1,2}{,-review-r0}.md` artifacts +
  **this document** + the **two** `…-inventory-review-recording-design-r3{,-review-r0}.md`
  files = 1+1+1+6+1+2 = **twelve**. My own measurement at 14:36:35Z was exactly
  those twelve; the Implementer's own build report §4 also lists twelve lines
  under a claim of eleven. The enumeration and the live set agree with each
  other and disagree only with the word "eleven". Impact is genuinely low —
  pc 13's authoritative form is now the re-measure instruction and the snapshot
  is explicitly labelled "not a postcondition", which is the correct fix for
  r2's M3 — but this is the third consecutive round in which a count inside this
  one postcondition is wrong, and it is trivially fixable. **The demotion also
  proved itself during this review:** a thirteenth path
  (`…-inventory-review-recording-design-r4.md`) appeared at 14:38:55Z, two
  minutes after my baseline.

- **N3 — §9.2 item 5's `record_inventory_review.py` cites are stale and, unlike
  §8.3's, carry no volatility caveat.** §8.3 handles this file exactly right: it
  names the measured hash and line count, states that neither r1's nor the r2
  review's cite matches, and instructs the executor to re-measure with a given
  `grep` rather than trust the cite. That warning has already been vindicated —
  the file is now `6df41f2c…`, **1651** lines (r3 measured `fe897813…`, 1468),
  and the postcondition check has moved from `:1086` to **`:1272`** with its
  message at `:1274-1275`. But §9.2 item 5 cites `:583`, `:664`, `:670` for the
  recorder's r2 §3.6 carve-out with no such caveat, and all three are now
  unrelated code (a verdict message, a `stat` check, a digest-mismatch message);
  the carve-out lives at `:100` and `:788` today. **The conclusion is
  unaffected** — I re-verified that the recorder contains zero occurrences of
  `EXPECTED_DISP_R1_REQUIREMENT` or `disp_r1_proven`, so "the rename in §3.3
  breaks no code" holds. Recommend extending §8.3's volatility warning to cover
  every cite into that file, or dropping the three line numbers in item 5.

- **N4 — §6.2.1 and §11 point the executor at a probe that produces the *dead*
  post-state hashes, and §3.8 says so.** §6.2.1 states "Both post-state hashes
  are freshly computed by probe, reproducible by running `probe_r1_neutral.py`",
  and §11 describes that probe as the one that "produces the two pinned
  post-state hashes". But §3.8 states plainly that "`build_r3.py` and `pkg_r3.py`
  must run before `probe_r1*.py` is compared against anything: the r1-era probes
  carry r2's span D and therefore r2's dead hashes", and §3.8's own construction
  table correctly attributes the r3 build to `build-r3/build_r3.py`. The file's
  mtime (Aug 15 12:57, r1-era) confirms it was not updated for r3. So an
  executor following §6.2.1's reproduction instruction would compute
  `fa527d07…`/`59053b0b…` and conclude the design's own §6.2.1 table is wrong.
  Both references should name `build-r3/build_r3.py r3`. This is a documentation
  contradiction, not a hash error: I reproduced **both** r3 hashes from r3's own
  fenced blocks with my own harness.

- **N5 — "byte-equivalent to today" in the §7 question, and "byte-for-byte
  equivalent to today's" in §3.5, are literally false about the bytes.** Span D's
  `before` and `after` differ in every line; what is preserved when `HR-0005` is
  absent is the assertion's *effect*, not its bytes — `amendment_overlap` is
  empty, the equality reduces to the same set, the count reduces to 23, and the
  third assert is vacuously true. I confirmed the intended meaning is true: the
  untouched canonical pair reaches exit 0 under the amended validator, and B10
  shows no other row can enter the set. This is the same class as r2's M6
  ("line-for-line"), which was fixed **in the very same sentence** of the §7
  question while this phrase five clauses later was left. A reader is unlikely to
  be misled — the question separately discloses the span replacements and pins a
  *new* post-state hash for the validator — but §7 is the byte-bound authority
  record, "equivalent in effect" costs nothing, and the design's own D3/R-A
  vocabulary is already more precise.

---

## Ruling

**The r2 Important finding is fixed, and fixed the right way.** r3 did not
weaken the §7 claim to match the validator; it strengthened the validator to
match the claim. I rebuilt the A1 attack independently from §4 and the live
schema — an unresolved, `OPEN_BLOCKING` `HR-0005` whose ledger link borrows
HR-0004's own resolution — and confirmed on identical package bytes that r2's
span D **accepts** it at exit 0 while r3's **rejects** it at `:2822`. The single
added conjunct is exact rather than merely sufficient: `:1099` equates
`resolution_decision_ids` with *all* resolutions on the entry, and `:1091`
already caps active ones at one, so `len(...) == 1` plus the trailing list
equality pins exactly one resolution which must be active, human, `CURRENT_USER`,
`RECONCILE_AUTHORITY`, under `GOAL_OR_PROCESS_AUTHORIZATION`.

**Two-sidedness and gate neutrality both survive the fix.** The untouched
canonical pair still reaches exit 0, the conforming package still reaches exit 0,
and in a real repo copy with the amended goal and validator at their **canonical**
paths the preimplementation report is *string-identical* to the canonical
baseline — same 447 pending, same 0 stale, same single `DISP-R-1` blocker with
the same three reason codes. A line-shifting goal in the same harness dies at
`:892`, so N1 is real and R-A works.

**I attacked the amended validator on six routes the prior rounds did not.**
The three that could plausibly have laundered authority all fail: a *third*
entry on `DISP-R-1` passes both of span D's set-and-count asserts and is caught
only by the explicit link-set conjunct (`:2822`); a second entry double-linking
any other row is caught by the amended overlap equality (`:2820`); and span D's
enclosing `if "HR-0004" in human_entries:` guard cannot be turned off, because
link removal is append-only-blocked and dropping the entry fails at `:1196`.
A conforming entry under the wrong `approval_type` also reaches and fails at
`:2822`, confirming that conjunct is reachable rather than shadowed.

**Every hash and every count in the §7 question is measured, not asserted.**
All ten 64-hex values reproduce — seven from live canonical bytes, two from my
own rebuild of r3's fenced spans, one from the validator's own span semantics —
and none of r2's dead hashes appears in the question. The question is a single
4924-character line, ends in `?`, carries exactly the four declared placeholders
and nothing else, has balanced backticks, and presupposes no approval. The one
clause r2's F1 falsified is now true of the bytes.

**Five minor findings stand, and none of them blocks.** Four line cites are off
by one to ten lines with the substance correct in every case; postcondition 13
says "eleven" while enumerating twelve; §9.2 item 5's cites into the volatile
recorder lack the caveat §8.3 correctly applies to the same file; §6.2.1 and §11
name an r1-era probe that would reproduce the dead hashes; and "byte-equivalent"
overstates a preservation that is real in effect but not in bytes. All five are
prose fixes outside the fenced spans. I verified by line diff that r3 differs
from r2 in exactly one line of the extracted validator, so fixing any of these
cannot disturb `b77ea73d…` or `77faeaf3…`, and I confirmed both hashes against
the document's own bytes with a harness first calibrated against r2's published
values.

Under the stated bar — CLEAN only with 0 Critical and 0 Important — this round
qualifies. I would fix N1-N5 before the §7 question is put to the user, since
the question's bytes are what the approval binds, but none of them is a reason
to withhold the verdict.

---

Verdict: CLEAN — 0 Critical, 0 Important, 5 Minor
