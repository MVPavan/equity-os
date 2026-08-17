# Independent review — DISP-R-1 amendment design r2

| Field | Value |
|---|---|
| Reviewed path | `docs/goals/reviews/ledger/equity-os-blueprint-disp-r1-amendment-design-r2.md` |
| Reviewed-input SHA-256 | `d96a4bf6f1b47043ca95287837f5c181f3cc9bddc260f381dbcd2905e0e76ec3` (recomputed at start **and** end — identical) |
| Role | `REVIEWER` |
| Role binding path | `CONTEXT.md` |
| Role binding SHA-256 | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` (recomputed at start **and** end — identical) |
| Model | `claude-opus-5` |
| Effort | `high` |
| UTC timestamp | `2026-08-17T14:19:05Z` |
| Independence | I authored none of the reviewed material and reused none of the Implementer's probes, none of the r0 reviewer's probes, and none of the r1 reviewer's probes. Every result below comes from my own constructions under `scratchpad/disp-r1/review-r2/` and a throwaway staging root under `/tmp/`. |

**No canonical byte, Beads record, or Git state was changed.** All eight §0
pre-state hashes were re-verified byte-identical at the start and end.
`git status` at the end shows exactly the nine paths that were already dirty
before I began, plus this review file.

**My probes** (all read-only w.r.t. canonical files):

| Probe | Purpose |
|---|---|
| `build.py` | Enumerates r2's fenced blocks and rebuilds the candidate goal + all three extracted validators from r2's **own bytes**, never a retyping |
| `hr0005.py` | Builds the complete `HR-0005` / `HRD-0005-001` / `TR-DISP-R-1-004` four-file package from §4 |
| `attacks.py` | Entry-identity, scope, supersession, actor and decision-type attacks (A1-A6, E2) |
| `shortcuts.py` | Forbidden shortcuts K1/K2/K3/K5/K6 on the `HR-0005` post-state, with an independent re-sealing harness and a positive control |
| `/tmp/disp-r1-rev-r2-stage`, `/tmp/disp-r1-neg` | Real repo copies with the amended goal at its **canonical** path — the N1 proof and its negative control |

---

## Per-item verification table

| # | Item | Method | Result |
|---|---|---|---|
| **1** | Review r1 **F1** (209 → 212) fixed | Independent row diff of my rebuilt post-state against the canonical ledger, then byte search of r2 | **CONFIRMED — fixed at both occurrences.** My diff: `rows total 213, changed ['DISP-R-1'], unchanged 212`, fields changed exactly `human_review_id`, `transition_history`, `transition_history_sha256`, transition objects 648 → 649. §6.6 pc 9 (`:1067`) and the §7 question (`:1135`) both now read **212**. The only remaining `209` strings are `:1209` line cites and the §6.6/§12 notes recording the correction |
| **2** | Review r1 **M1** (line-cite drift, §2.4/§4.1-4.3) fixed | Re-measured **all 43** corrected cites against `validate_ledger_structural.py` @ `731d0d8b…` | **CONFIRMED — every corrected cite is exact.** `:280`, `:831`, `:832`, `:937`, `:1018`, `:1020-1026`, `:1027`, `:1029`, `:1030`, `:1031-1034`, `:1036`, `:1038-1041`, `:1048-1049`, `:1051`, `:1052-1053`, `:1055-1060`, `:1080`, `:1090-1098`, `:1099`, `:2074`, `:2075`, `:2076-2077`, `:2086-2088` all land on exactly what r2 says. I also re-measured the §4 in-vocabulary cites r2 did **not** flag (`:910-915`, `:916-919`, `:924-926`, `:934`, `:942-943`, `:945-948`, `:951`, `:975`, `:980-983`, `:988-999`, `:1008-1016`, `:1061-1066`, `:1744-1753`, `:1835-1858`, `:2070`) — all exact |
| **3** | Review r1 **M2** (recorder cite) fixed | Not re-measured — the file is untracked and actively edited; r2 states this and instructs re-measurement | **ACCEPTED AS HANDLED.** r2 reports the check at `:1086` against a named file hash, states plainly that it matches neither r1's `:1070` nor M2's `:1067`, and warns the cite is volatile with the exact `grep` to re-run. This is the right disposition for a moving target |
| **4** | Review r1 **M3** (§3.5 rests on H1/H2) fixed | Built my own H1/H2 equivalents (A3: `HR-0005` scoped to `DISP-R-1` + `DEF-01`; A6: `HR-0005` scoped elsewhere, `DISP-R-1` unlinked) and my own E2 | **CONFIRMED — the substantive fix is right.** My A3 and A6 are both rejected at **`:1209`**, reproducing the r1 reviewer's result and *not* r1's `:2820`. My **E2** (an entry byte-identical to the conforming `HR-0005` but named `HR-0006`) is rejected at candidate **`:2820`**, span D's first assert — so §3.5's re-grounding on E2 is correct. One residual labelling defect, see **N2** |
| **5** | Review r1 **M4** (two placeholders are post-state bytes of existing files) fixed | Read §6.2.3 | **CONFIRMED — recorded in substance**, including the compensating control (pc 9/11/12 + §6.5 rollback) and the HR-0004 calibration. I independently agree the two hashes are not pre-derivable: the ledger post-state depends on `HRD-0005-001.content_sha256`, which covers the approval-instant `timestamp` |
| **6** | Review r1 **M5** (`role_binding_sha256` cite) fixed | Read `:259` and `:260` | **CONFIRMED.** `:259` is `assert review["role_binding_path"] == ROLE_BINDING_PATH`; `:260` is `assert re.fullmatch(r"[0-9a-f]{64}", …)`. r2's re-measurement to `:260` is correct and M5's `:259` was wrong |
| **7a** | Spans are line-neutral and reproduce r2's two pinned post-state hashes | Extracted r2's fenced spans by fence enumeration, applied to the canonical goal, re-extracted with the canonical extractor | **CONFIRMED, both hashes exact.** Each `before` occurs **exactly once**; B 13→13, C 13→13, D 6→6. Candidate goal = **`fa527d076b4bfb6b3e627d7d8fbda799cad3117f9db6ce0d8088d256ec898304`**; candidate structural = **`59053b0bb7173055a8c768907e6ddb9f1bbab8cc48f2f639ded04b9526170419`**; candidate preimplementation = `f7a225a1…` (**byte-identical** to canonical); 3244 → 3244 lines; goal 5894 → 5918 lines with all growth below 5847 |
| **7b** | Spans land at the cited lines | `awk` over my candidate validator | **CONFIRMED.** Span B at candidate `:2674-2686`, span C at `:2756-2768`, span D at `:2817-2822`, with `:2820` = the overlap-equality assert and `:2822` = the `HR-0005` conformance assert. Goal `:4028-4040`, `:4110-4122`, `:4171-4176` verified against canonical bytes |
| **8a** | The Critical: canonical validator dies at `:2821` | Built the full `HR-0005` four-file package myself (entry + `RECONCILE_AUTHORITY` resolution + ledger link + appended `AUTHORITY_RECONCILIATION` transition + recomputed `transition_history_sha256`) and ran the **canonical** structural validator | **CONFIRMED — exit 1, `AssertionError` at line 2821**, `assert overlapping == set().union(*EXPECTED_PRIOR_HR_LINKS.values())`. Independently reproduced |
| **8b** | With r2's span D, the same package validates | Applied B/C/D verbatim from r2's own fenced blocks, re-extracted, ran the amended validator on the identical package | **CONFIRMED — exit 0** |
| **8c** | Span D is two-sided | Amended validator against the **canonical** ledger + human-review pair | **CONFIRMED — exit 0** |
| **9** | `extract_goal_validators.py --check` on the amended goal | Run with explicit paths, **and** canonically (no arguments) inside a staging repo root with the amended goal at its canonical path | **CONFIRMED — exit 0 both ways** |
| **10** | N1 (goal is line-anchored) and remedy R-A | Built a real repo copy at `/tmp/disp-r1-rev-r2-stage` with the amended goal **and** amended validators at their canonical paths, plus a negative control at `/tmp/disp-r1-neg` with 70 lines inserted above 5791 | **CONFIRMED end-to-end.** P1 `--check` → **0**; P2 amended structural on the `HR-0005` post-state → **0**; P3 preimplementation → **2**, `ready=false`, `pending_reviews`=**447**, `stale_reviews`=**0**, DISP-R-1 unmet entry **byte-identical to §0**; P4 span `5791-5847` digest → **`1647f803…`**. **Negative control: exit 1 at `:892`**, `assert evidence["content_sha256"] == digest` in `validate_human_evidence`. N1 is real and R-A remedies it |
| **11** | Gate neutrality (T1 moves the gate by zero rows) | Preimplementation on canonical vs on my post-state | **CONFIRMED — identical.** Both `ready=false`, 447 pending, 0 stale, and the same single `DISP-R-1` unmet entry with the same three reason codes |
| **12** | Forbidden shortcuts still fail after all four spans | Built K1/K2/K3/K5 plus my own **K6** on the `HR-0005` post-state, with an independent iterative re-sealing harness driven by the validator's **own** projection functions, and a positive control | **ALL REJECTED, and every cited line reproduces.** K1 (SATISFIED + refs, no `COMPLETE` review) → `:2767`; K2 (genuine `COMPLETE` review on the historical ref, requirement left `UNRESOLVED`) → `:2764`; K3 (`description` weakened to "S20 exists", then satisfied) → `:2760`; K5 (SATISFIED with empty refs) → `:2141`; **K6** (mine — SATISFIED with a genuine review but requirement refs omitting the historical ref) → `:2767`. **Positive control** (genuine full T2 with the union of refs) → **exit 0**, confirming the `else` branch is reachable only by a real proof |
| **13** | The `UNRESOLVED` ↔ empty-refs coupling span C deliberately omits | Read `:2138-2141` | **CONFIRMED.** `:2139` is `assert item["evidence_ref_ids"] == []` in the `UNRESOLVED` arm and `:2141` is `assert item["evidence_ref_ids"]` in the `else` arm. The omission is safe |
| **14** | Laundering through a new HR entry | 7 constructions: A1-A6, E2 | **SIX REJECTED, ONE ACCEPTED.** E2 (`HR-0006`) → `:2820`; A2 (superseded + active resolution) → `:2822`; A3 (scope widened) → `:1209`; A4 (`decision_type=SATISFY_APPROVAL`) → `:1108`; A5 (`actor_type=AGENT`) → `:1030`; A6 (`HR-0005` present, `DISP-R-1` unlinked) → `:1209`. **A1 reaches exit 0 — see finding F1** |
| **15** | Ordering rule (D4/§8.3) | Built the recorder-first case myself: sealed `DISP-R-1`'s three reviews against the pre-T1 row, then landed T1 without re-sealing | **CONFIRMED AND SOUND.** Control (reviews sealed, no T1) → **exit 0**. J5 (T1 lands after) → **exit 1** inside `validate_inventory_review` at `:350`, the `reviewed_input_sha256` mismatch. r2 cites the call site `:1135`; same failure, different report depth. `DISP-R-1` genuinely has **three** reviews — `approval_inventory_review`, `evidence_inventory_review`, and `scope_derivation.semantic_review` — and 169 + 169 + 109 = **447**, confirming that count too |
| **16** | §7 approval question mechanics | Byte inspection of line 1135 | **CONFIRMED.** Single-line blockquote, **4906 chars, no embedded newline**, ends `?`, **130 backticks (balanced)**, exactly the **four** declared placeholder tokens and no others (`<DISP_R1_DESIGN_SHA256>`×2, `<DISP_R1_REVIEW_SHA256>`, `<HUMAN_REVIEW_POST_SHA256>`, `<LEDGER_POST_SHA256>`), lines 1134 and 1136 both blank. Header line 3 and §7's own preamble both state DESIGN ONLY / NOT APPROVED, and the text is framed as a question to be asked — it **presupposes no approval the user has not given** |
| **17** | Every hash in the §7 question | Independent measurement of all 10 | **ALL 10 CONFIRMED.** Seven §0 pre-state hashes (`f15f7ab5`, `731d0d8b`, `de236d7e`, `094fcdfa`, `f7a225a1`, `5d20d796`, `8f2795af`) re-measured from live bytes; `fa527d07` and `59053b0b` reproduced by my own rebuild; `1647f803` reproduced with the validator's own `resolve_utf8_line_span` semantics |
| **18** | Every count in the §7 question | Independent measurement of each | **ALL CONFIRMED EXCEPT ONE CLAIM.** 212 unchanged rows ✔; 23 `overlapping` rows ✔ (`EXPECTED_PRIOR_HR_LINKS` union = 23, live overlapping = 23); 447 pending ✔; 0 stale ✔; 454 prefix sum over 210 keys with `DISP-R-1`=2 ✔; 648 → 649 ✔; sequence 4 ✔; four files ✔; three fields ✔; goal lines 1-5847 / span 5791-5847 ✔. **The claim that a conforming `HR-0005` "carries exactly one active `RECONCILE_AUTHORITY` resolution" is not enforced — see F1** |
| **19** | §6.6 postconditions | Checked 9, 10, 11, 12 against my construction; 1-8 against my rebuild and staging runs | **VERIFIED.** pc 1 `fa527d07…` ✔; pc 2 `59053b0b…` ✔; pc 4 preimplementation/extractor/`CONTEXT.md`/S20 unchanged ✔; pc 5 `1647f803…` ✔; pc 6 `--check` → 0 ✔; pc 7 structural → 0 ✔; pc 8 → 2/447/0/identical blocker ✔; pc 9 one row, three fields, 212 unchanged ✔; pc 10 648 → 649 with prefix sum still 454 ✔; pc 11 five entries, 2 resolutions, `HR-0005` `RESOLVED` ✔; pc 12 requirement still `UNRESOLVED` with empty refs, 447 still `PENDING` ✔. pc 13 enumeration is stale — see **N3** |
| **20** | §12 provenance | Hashed both copies of the r1 review | **CONFIRMED.** `scratchpad/disp-r1/review/design-r1-findings.md` = `ad07b96942100a8b18562d2907ecd6c5da6ebace7f1eb9979379132984d874b1`, and the artifact at the predetermined docs path is **byte-identical**. r1's verdict line reads exactly `BLOCKED — 0 Critical, 1 Important, 5 Minor`, matching r2's changelog and §12 |
| **21** | Consistency with the orchestrator pre-decision | Read §4.4, §5.3, §7, §9.2 item 6 | **CONSISTENT.** r2 does not silently bind the wrong artifacts — it flags the `-design-r1` paths as a **blocking precondition** in §9.2 item 6 and in the header, which is the correct posture for a round that cannot know its own review's filename. One stale premise inside that item, see **N4** |
| **22** | Miscellaneous cited facts | Direct read | **CONFIRMED.** Goal SUCCESS condition 5 at `:5752-5756` verbatim; the A6 paragraph at goal `:460-474` verbatim; `DISP-R-1` occurs **19** times in the goal, exactly **one** outside the three program spans, at `:5831`; `:2707-2709`/`:2719` carry the predicate's coverage test; `CONTEXT.md:137-147` defines `REVIEWER` and binds it to Claude Opus 5, high effort |

---

## Findings

### F1 — Important — span D does **not** enforce "exactly one active `RECONCILE_AUTHORITY` resolution", and the §7 approval question tells the user that it does

Span D's final assert compares two lists:

```
[r["decision_id"] for r in human_resolutions.values()        if r["human_review_id"] == "HR-0005"]
==
[r["decision_id"] for r in active_human_resolutions.values() if r["human_review_id"] == "HR-0005" and … RECONCILE_AUTHORITY … HUMAN … CURRENT_USER … GOAL_OR_PROCESS_AUTHORIZATION]
```

When `HR-0005` carries **zero** resolutions both sides are `[]` and the
conjunct is **vacuously true**. The equality pins "at most one, and every one
conforming" — not "exactly one".

**This is not a theoretical gap. I built the state and it validates.** Attack
**A1**: an `HR-0005` entry with `resolution_decision_ids: []`, `state:
"OPEN_BLOCKING"`, correctly scoped to `{"DISP-R-1"}`, with `DISP-R-1` linked to
`["HR-0004", "HR-0005"]` by an appended `AUTHORITY_RECONCILIATION` transition
whose `human_resolution_decision_id` recycles **HR-0004's own** active
resolution `HRD-0004-001`. That recycling is legal because
`transition_resolution` (`:1772-1779`) only requires the row to lie in the
citing entry's scope, and `DISP-R-1` is one of HR-0004's 144 scoped components.

```
amended structural on the A1 package          -> exit 0
amended preimplementation on the A1 package   -> exit 2, ready=false, 447 pending, 0 stale
```

Nothing downstream catches it: the preimplementation gate reports the same
447/0 and the same `DISP-R-1` blocker, and no assert anywhere requires a
human-review entry to be resolved (HR-0001..3 are legitimately `OPEN_BLOCKING`
with empty `resolution_decision_ids`).

**What this falsifies.** Three design claims and, decisively, one clause of the
approval question:

1. §3.5: "The last equality is a list-vs-list comparison of `decision_id`s, so
   it also pins '**exactly one resolution on this entry**'." It does not.
2. §3.5 bullet 2 and §3.9's "Launder authority through a new HR entry" row:
   the admission is *not* gated on "an active human `RECONCILE_AUTHORITY`
   resolution" existing on `HR-0005`.
3. **§7, line 1135** — the pin is relaxed "only while a conforming `HR-0005`
   exists that projects no other component, links `DISP-R-1` only alongside
   `HR-0004`, and **carries exactly one active `RECONCILE_AUTHORITY` resolution
   by a human actor under `GOAL_OR_PROCESS_AUTHORIZATION`**". The first two
   conjuncts are enforced (my A3/A6/E2 confirm). The third is not.

**Why this is Important and not Critical.** It enables no false
no-implementation proof: span C's `else` branch is untouched, and K1, K2, K3,
K5 and my K6 are all still rejected while a genuine T2 still reaches exit 0.
T1's own postcondition 11 (`resolutions` length 2, `HR-0005.state ==
"RESOLVED"`) would catch A1 for *this* transaction and force a rollback.

**Why it must be fixed before the question is asked.** The §7 bytes are the
authority record the user's rank-1 approval attaches to and that
`HR-EV-0005-DESIGN` binds by digest. Under the HR-0004/r7 bar, a statement that
overstates an enforced control — in the very sentence describing the control
being relaxed — is exactly what the hash binding exists to prevent. And unlike
r1's F1 this is not a prose fix: the amended validator is **permanently
canonical** after T1, so the weakness outlives the transaction and applies to
every future state, which is precisely the laundering route §3.9 claims to
close.

**Remedy, verified by construction.** Insert one conjunct at the head of span
D's final assert:

```python
assert not hr0005 or (len(hr0005["resolution_decision_ids"]) == 1 and human_scope_components["HR-0005"] == …
```

`entry["resolution_decision_ids"] == all_by_entry[entry_id]` is already asserted
globally at `:1099`, so this is exact. I patched r2's span D inside the goal,
re-extracted, and re-ran everything:

| Check | Result |
|---|---|
| Goal line count | 5918 → 5918 (**still line-neutral**) |
| Extracted structural line count | 3244 (**unchanged**) |
| `extract_goal_validators.py --check` | exit **0** |
| Goal `5791-5847` span digest | **`1647f803…`** (unchanged) |
| Conforming `HR-0005` package | exit **0** |
| Canonical ledger + human-review pair | exit **0** |
| **A1** | **exit 1 at `:2822`** |
| A2, E2 | still rejected at `:2822`, `:2820` |

The fix costs nothing structurally, but it changes span D's bytes and therefore
**both pinned post-state hashes in §6.2.1 and §7 must be recomputed**. My build
of the patched package gives goal `b77ea73d90fb6f7499a7fcf74f50c471bb03dd5a6f1bf0c71f510af917d0b0c9`
and structural `77faeaf3dee13d5d2bfb50c255b054cde94ef0118751b247e23248e343964fff`;
the Implementer must derive its own values from its own final span text rather
than adopt mine.

Alternatively the §7 clause could be weakened to match the validator — but that
would leave §3.5 and §3.9 overstating the control too, and would knowingly ship
the laundering route. Fixing the validator is the right call.

---

## Minor findings

- **N1 — §3.4 and §9.1 R6 undercount the over-long lines by half, and omit span
  D entirely.** Both say "**four** over-long lines in span C". Measured on my
  extracted candidate, **eight** of span C's thirteen lines exceed 79 columns
  (`:2758` 81, `:2759` 132, `:2760` 143, `:2762` 102, `:2764` 138, `:2765` 100,
  `:2767` 130, `:2768` 129), and span D adds three more (`:2817` 82, `:2820` 92,
  and **`:2822` at 687 characters**). For calibration the canonical program
  already has 126 lines over 79 columns, but its widest line is **99** — so
  span C's 143 and span D's 687 are genuine outliers, and the 687-char line is
  not disclosed at all. The paragraph is explicitly framed as "stated plainly
  … I am not hiding it", which makes the count worth getting right. No
  mechanical check enforces this and it changes nothing else.

- **N2 — §3.8's H1/H2 rejection line is mislabelled, and contradicts the note
  directly below it.** The table reads "`:2820` (span D **scope pin**)", but
  candidate `:2820` is the overlap-equality assert; the scope pin is `:2822`.
  Ten lines later §3.8 correctly says H1/H2 "must not be read as evidence that
  span D's scope assertion fires". Both of my own H1/H2 equivalents (A3, A6)
  are rejected at `:1209`, matching the r1 reviewer and not `:2820`.
  Recommend dropping the parenthetical, or relabelling it "span D overlap
  equality". Related: §8.2's J-table lacks the "Rejected, e.g. at" caveat the
  H- and K-tables carry, and its J5 cite (`:1135`) is the call site where I
  measure `:350` — same failure, different report depth.

- **N3 — §6.6 postcondition 13's dirty-path enumeration is already incomplete.**
  It lists five paths. Measured today the set is **nine**:
  `.beads/issues.jsonl` (modified) and untracked
  `…-design-r0.md`, `…-design-r0-review-r0.md`, **`…-design-r1.md`**,
  `…-design-r1-review-r0.md`, `…-design-r2.md`,
  `…-inventory-review-recording-design-r3.md`,
  `docs/goals/reviews/ledger/inventory/`,
  `scripts/equity_os_blueprint/record_inventory_review.py`. Four of those
  post-date r2 (mtimes 14:04-14:12 vs r2's 14:00), so only **`…-design-r1.md`**
  was a genuine omission at authoring time. The postcondition already carries
  the right instruction — "The executor must re-measure this set immediately
  before step 1 of §6.5 and journal it" — so impact is low, but the enumeration
  should either be corrected or replaced outright by the re-measure instruction,
  since any frozen list will keep going stale.

- **N4 — §9.2 open question 6 rests on a premise that no longer holds.** Its
  stated reason for not re-pointing the paths is "(r1's own predetermined path
  was never used — the r1 review landed at
  `scratchpad/disp-r1/review/design-r1-findings.md`)". The r1 review now exists
  at the predetermined path
  `docs/goals/reviews/ledger/…-design-r1-review-r0.md` and is **byte-identical**
  to the scratchpad copy (both `ad07b969…`), so the lineage convention *is*
  established and was simply not yet visible when r2 was written. I record this
  only because the parenthetical is the justification a future reader will rely
  on; **the path re-pointing itself is out of scope for this review** per the
  orchestrator pre-decision, which already schedules it for r3.

- **N5 — two names for the same two placeholders.** §4.4's table and §6.2.3's
  items 1-2 call them `<DESIGN_R1_SHA256>` and `<REVIEW_R0_SHA256>`; §6.2.3's
  residual-risk paragraph and §7 call the same two values
  `<DISP_R1_DESIGN_SHA256>` and `<DISP_R1_REVIEW_SHA256>`. §7's declaration
  ("Placeholders — and only these") is internally exact and I verified the
  question carries exactly those four tokens, so nothing is ambiguous *within*
  §7 — but an executor resolving placeholders across sections has to notice that
  four names denote two values. Recommend one naming scheme.

- **N6 — "line-for-line" in the §7 question is looser than the design's own
  term.** The question says it "preserves goal lines 1-5847 **line-for-line**".
  Goal lines 4028-4176 do change bytes; what is preserved is the *line count and
  numbering*, which is what D3 ("line-count-preserving") and §3.6 R-A
  ("line-count-identical") say. The surrounding clause makes the purpose clear
  and the question separately discloses the span replacements, so I do not think
  a reader is misled — but the design's own wording is more precise and costs
  nothing.

---

## Ruling

**The r1 findings are fixed, and fixed by construction rather than by
assertion.** F1's `209 → 212` is corrected at both occurrences and I confirmed
**212** by an independent row-by-row diff rather than by arithmetic. All 43 of
M1's re-measured cites are exact, and so are the §4 cites r2 did not flag. M5's
own cite was itself wrong and r2 caught it (`:260`, not `:259`). M2 is handled
correctly for a volatile untracked file. M3's re-grounding on E2 is right — my
E2 is rejected at candidate `:2820` while my H1/H2 equivalents die earlier at
`:1209`, exactly as the r1 reviewer found. M4 is recorded honestly.

**The Critical and N1 both reproduce.** A fully-formed `HR-0005` package I built
myself kills the canonical validator at **line 2821**; with r2's spans applied
verbatim from its own fenced blocks the identical package reaches **exit 0**,
while the canonical pair still reaches exit 0 under the same amended validator.
Both pinned post-state hashes reproduce exactly. In a real repo copy with the
amended goal at its **canonical** path, `--check` → 0, structural → 0,
preimplementation → 2/447/0 with a byte-identical blocker, and the
`5791-5847` digest holds at `1647f803…`; a line-shifting goal in the same root
dies at `:892`. R-A works.

**One Important finding stands.** Span D's conformance assert is vacuous when
`HR-0005` carries no resolution, and I demonstrated a state — an unresolved,
`OPEN_BLOCKING` `HR-0005` whose ledger link borrows HR-0004's own resolution —
that the amended validator **accepts**. That is the laundering route §3.9 claims
to close and the specific guarantee §7 asks the user to approve. It grants no
false proof and T1's own postconditions would catch it for this transaction, so
it is not Critical. But the amended validator becomes canonical, the weakness
outlives T1, and the fix changes the very bytes the approval binds — so it
cannot be patched afterwards. The one-conjunct remedy is verified line-neutral,
extractor-clean, span-digest-preserving, and sufficient.

Everything else in this review — every hash, every count, every attack
rejection, every ordering and staging result — was computed against r2's actual
spans and would be unchanged by that fix, except the two pinned post-state
hashes, which must be recomputed.

---

Verdict: BLOCKED — 0 Critical, 1 Important, 6 Minor
