# Independent review r0 of ledger remediation design r7

## Binding

| Field | Value |
|---|---|
| Reviewed design path | `docs/goals/reviews/ledger/equity-os-blueprint-ledger-remediation-design-r7.md` |
| Reviewed-input SHA-256 | `4b604e006d1ab727a27b980011f223debca60b1febd738a4c46d21e67574bedf` |
| Reviewer role | `REVIEWER` |
| Reviewer model (actually invoked) | `claude-opus-5` |
| Reviewer effort (actually invoked) | `high` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| Role-binding section | `CONTEXT.md` §"Agent roles (harness-wide)" (line 127) |
| Review UTC timestamp | `2026-08-14T23:20:58Z` |
| Session identity | `506ceb89-ffa3-4946-a8b1-df24a01bc0ff` |

The reviewed-input SHA-256 above was computed from the reviewed file's bytes at
review start and recomputed unchanged at review end. This reviewer authored none
of the reviewed material and is a separate agent and context from the author of
r7 and of every prior revision.

This is a differential review on top of this lane's prior r6 review
(`scratchpad/hr0004/review/r6-review-findings.md`, SHA-256
`4d6a197d51a50a4dfa58620cdc9590ec0c900ac8d81ab5f2c7c1e1af54a3705b`,
`Verdict: BLOCKED — 0 Critical, 1 Important, 2 Minor`), whose non-findings were
verified exact there against r6 SHA-256
`87220b14d9a090b7a6700eeab4de7a0c4dd316056a30ce9ae7ee2c8eb84d0964`.

## 1. Hunk accounting — every r6→r7 change traced

`diff r6 r7` yields 621 diff lines. Every hunk traces to one of the three r6
findings or to supersession/path/placeholder/lineage plumbing. No unexplained
change:

| Hunk group | Trace |
|---|---|
| Title; next-action review path; §5.1/§5.2/§10 path renames; `<R6_*>`→`<R7_*>`; ~25 `r6`→`r7` word swaps in §§1, 1.1, 2, 3.2, 3.5, 3.7, 3.8, 3.9, 4, 5.1, 5.3, 6.1–6.3, 7, 8.1, 8.3, 8.4, 10 | plumbing |
| Header paragraph: "r6 and r7 changed the goal amendment set again"; "**No r5-bound or r6-bound approval was ever asked for or given**" | supersession plumbing |
| §1 opening: starts from r6 SHA; cites r6-review path, SHA, verdict line and counts; keeps the r5→r4→candidate-review lineage | supersession plumbing |
| §1.2 intro: r5 dispositions restated as carried forward and independently verified closed | lineage plumbing |
| §1.3 new disposition table (I-R6-1, M-R6-1, M-R6-2) | required |
| §2 intro: "equals the r4, r5, and r6 §2 values" | plumbing |
| §3.8 "Goal prose" pointer restated for B.1's widened scope | I-R6-1 |
| §4 scope-invariance restatement extended to r7 | I-R6-1 traceability |
| §7.3 B.1: heading clause, 791–824 anchor, 791-not-792 rationale, exact merged 791–796 replacement | I-R6-1 (a) |
| §7.3 D.2: case-insensitive matching, third exemption, rationale, re-run authoring verification | I-R6-1 (b) |
| §8.3 postcondition: case-insensitivity + path-literal exemption stated in the same terms; "including B.1's 791–824 anchor" | I-R6-1 (b) |
| §7.3 B.2 wrapping note rewritten | M-R6-1 |
| §5.3 and §8.4 line reflows (no wording change) | M-R6-2 |

§1.3's claim "No other change was made to r6's operational design" is true on
this accounting.

## 2. Focused checks — all recomputed from live bytes

**I-R6-1 (a), B.1 anchor extension — CLOSED.** The goal's §"Agent routing and
delegated authority" heading is line 789 (r7 states 789; the r6 review's
parenthetical "790" was the off-by-one, not r7). Line 790 is blank, the body
paragraph is exactly 791–796 ending `lane.` with 797 blank, and 797–824 hold the
role table, the `Use these explicit invocation classes:` line, the CLI block
(807–813), and the 815–824 paragraph — so **791–824 is the entire body**, as
stated. The exact replacement given for the merged 791–796 paragraph is fixed
text, ≤78 columns, uses only `ORCHESTRATOR`/`IMPLEMENTER`/`REVIEWER` and one
`CONTEXT.md` "Agent roles (harness-wide)" pointer, and I confirmed
programmatically that it contains **zero** D.2 lane tokens under case-insensitive
word-boundary matching, so the amended paragraph passes D.2 on its own bytes.
The lowercase `codex exec` mandate and its dangling-fragment risk are gone.

**I-R6-1 (b), D.2 case-insensitivity and exemption — CLOSED; enumeration re-run
independently.** Against the pre-state goal (SHA-256 `dabad7bf…5ddc67f`, 4146
lines) with D.2's own closed token list (`Sol`, `Terra`, `Luna`, `xhigh`,
`gpt-5.6`, `Codex`, `Agent Matrix`) and word-boundary semantics, my own scan
gives:

- **77** matching lines case-insensitively; **74** case-sensitively; the
  case-sensitive set is a strict subset and the three lines only the
  case-insensitive scan reaches are exactly **71, 791, 4018**.
- Subtracting B.1 **with** the 791–824 anchor, B.2, B.3, the §"Activation record"
  span (heading at line 4101, file ends 4146) and the three program spans
  (1226–3326, 3333–3414, 3422–4012, derived from fence lines
  807/813, 1207/1212, 1226/3326, 3333/3414, 3422/4012) leaves a residual of
  exactly **two lines, 71 and 4018, carrying three matches**. With r6's 792
  anchor the residual is {71, **791**, 4018} — reproducing the r6 finding
  exactly, and confirming the anchor extension is what removes 791.
- All three residual matches are `codex` immediately preceded by `.` and
  immediately followed by `/`, so **every** residual match satisfies exemption 3
  and zero fall outside it. `.codex/project/invariants.md` and
  `.codex/project/verification.md` both exist on disk; neither line 71 nor 4018
  is inside any §7.3 amendment span or program span, so both stay byte-unchanged
  through the transaction and the post-state check passes.
- Activation-record occurrences under case-insensitive matching are exactly
  4114, 4115, 4116, 4132, 4135 (all inside the §7.3 C preserved span); in-program
  occurrences are exactly 1486, 1487, 3246, 3247 — i.e. the case-insensitive
  scan adds nothing inside the exempt spans either.

Exemption 3 is **closed and mechanical**: it is a character-level predicate on
each match ("first character immediately preceded by `.`, last character
immediately followed by `/`"), it consults nothing else about the surrounding
text, and it cannot re-admit line 791 (whose `` `codex exec` `` is preceded by a
backtick and followed by a space). §8.3 now restates both qualifiers —
case-insensitivity and the path-literal exemption — in the same terms as D.2 and
additionally requires the three exempted occurrences to remain byte-unchanged, so
the postcondition is exactly the property the check supports. The plain-reading
falsehood the r6 review identified is gone.

**M-R6-1 — CLOSED.** Checked all ten B.2 entries against the pre-state goal: the
quoted sentence continues onto the following line for 345, 441, 512, 519–520,
632, 981 and 4076, and ends on its own line for 123, 185, 497 — exactly r7's
seven/three split. The stated patch unit (the sentence, not the physical line)
is now explicit, so no strict exact-match implementer can stall on an unnamed
case. B.2's table rows and replacement rule are byte-unchanged from r6, and I
re-verified every quoted pre-state fragment against the goal.

**M-R6-2 — CLOSED.** The §5.3 and §8.4 lines are reflowed with identical wording
(word-for-word equal to r6 modulo line breaks). Lines longer than 90 columns
drop from 7 in r6 to 5 in r7; all five remaining are pre-existing JSON literals,
hash lines and path lines that cannot be wrapped.

**Pinned inputs — all recomputed, all equal.** Goal `dabad7bf…5ddc67f`, ledger
`51091042…95e13`, human review `54c1e183…13ee5702`, v2 register
`26d51b31…5fad7164`, disposition report `a9021c15…14322738`; scripts
`f880f507…9554e9` (structural), `ed73ffe1…6cd5b39c` (preimplementation),
`7d9e130c…5ac8934d` (extractor). Supersession chain: r4 `c1ab1258…4b295e00`,
r5 `faa7bc26…c64d19a`, r6 `87220b14…b84d0964`, r6-review
`4d6a197d…54a3705b` and its `Verdict: BLOCKED — 0 Critical, 1 Important, 2
Minor`, r5-review `2bac0bb9…5b877c8bdec8`, candidate review-r0
`Verdict: BLOCKED — 1 Critical, 7 Important` (line 578) — every value matches the
file it names. `scratchpad/hr0004/approval-evidence.md` is bound to r4 only and
contains no r5 or r6 SHA, so "no r5-bound or r6-bound approval was ever asked for
or given" is exact.

**Digests — re-derived independently.** Expanding §4's own ID ranges: 144 unique
IDs, 141 pre-existing in the 210-row ledger, new set exactly `{ALIAS-044,
AUTH-REG-002, AUTH-REG-003}`, canonical-JSON sorted-array digest
`bf6fee00d0f4510316b42b50ec13f74148df9ed44e472f2ad8be114ee3add894` — equals §4
and §5.2. Ledger: 210 rows, kind counts `60/35/13/8/32/2/11/6/43` as §2 states,
**454** transition objects, sorted-ID→ordered-array digest
`d4ce9646438d388bf26c8faa82d689209296726af2c29d1e56942218c613d9b1` — equals §2
and §8.1. All 454 `invoked_model` values are `gpt-5.6-sol` and both 23-value
finding-review/adjudication model sets are uniform, as §3.8 asserts;
`evidence_inventory_review` and `approval_inventory_review` are non-null on
167 rows each.

**§5.2 invariance.** Normalising only the revision tokens
(`design-r6`↔`design-r7`, `<R6_*>`↔`<R7_*>`, "that r6/r7 design"), the r6 and r7
question lines are **byte-identical**. The whole file contains exactly two
distinct placeholders in three occurrences (`<R7_SHA256>` ×2,
`<R7_REVIEW_SHA256>` ×1), no residual `<R6_*>`/`<R5_*>` token, no other
angle-bracket token beyond the pre-existing `<NN>`, and no `TBD`/`TODO`. Same
pre-state, same scope, same values.

**Load-bearing r6 items a §7.3 change could have disturbed.** §7.3 A (A1–A11),
§7.3 B's lead-in rule, the B.2 table, §7.3 C, §7.3 D.1, §8.1's ownership list and
both marker/lane checks, the §3.5.1 pinned `REQ-PG-2-04-COMMAND-PROOF` literal,
the §3.7 closed authority vocabulary, and the §7.2 one-row `program_disposition`
manifest are all byte-unchanged from r6 and were verified exact in this lane's r5
and r6 reviews. No section anywhere in r7 still requires case-sensitive
matching; the only remaining "case-sensitive" mentions are historical
explanations of the defect.

**§1.3 completeness and honesty.** All three r6 findings appear, each disposition
statement is true as written, and each cited section really contains the change.

## 3. Minor findings (non-blocking; recorded, no correction required)

**M-R7-1 — §1.3's plumbing enumeration reads as exhaustive and is not.** "Apart
from supersession, path, placeholder, and lineage plumbing — the header
paragraph, §1's opening, §1.2's intro, §2's … and §4's scope-invariance
restatement — the §1.3 rows below are the whole r6→r7 delta" omits the title
line, the next-action and §5.1/§5.2/§10 path renames, the placeholder renames,
and ~25 bare `r6`→`r7` word swaps. All are covered by the leading category, so
the sentence is true under its category reading; only the appositive list is
partial. Same class as M-R6-1 one level up.

**M-R7-2 — B.1's new heading clause is stated generally but applied to one
anchor.** The heading reads "passages containing an explicit `xhigh` or
`gpt-5.6-sol` token, **plus the paragraph line those passages continue from**",
while §3.8 and the enumeration extend only the §"Agent routing" passage. At
least one other anchor continues from its predecessor in the same way: the
1158–1173 passage continues the sentence begun on line 1157 ("Classify only
non-code external web research and" / "heavy or numerous public-equity
source-document reading as the Luna lane."). If that lane-classification sentence
is removed rather than rewritten in place, line 1157's half-sentence is orphaned.
Non-blocking: no lane token remains on 1157, so D.2 still passes; no live
vendor-tool mandate survives (unlike line 791); the residual would be visible
editorial breakage in a block the implementer is already rewriting; and B.1's own
heading clause, read generally, already reaches 1157. The other anchors that
continue from a preceding line (251, 386, 423, 516, 654, 752, 829) survive a
local token substitution grammatically intact — I checked each boundary.

**M-R7-3 — stale count in D.2's prose.** After the exemption list grew to three
items, D.2 still says the check "is positional only through the two region
delimiters above". This is literally true (only exemptions 1 and 2 are
positional; exemption 3 is contextual) but reads as an un-updated count.

**M-R7-4 — an absolute claim inside the fixed 791–796 replacement.** "this goal
states no invocation surface, tool, model name, or effort level of its own" sits
in the same file as the deliberately preserved §"Activation record", whose rows
record approved Sol/Terra/Luna routing and effort policy. The phrase "of its own"
carries the forward-looking-rule vs historical-record distinction that §3.8 and
§7.3 C draw, so the claim is defensible as written; flagged only because it is
new fixed goal text making a whole-file assertion.

## 4. Summary

r7 closes all three r6 findings, and closes them completely. The B.1 anchor now
covers the entire §"Agent routing" body from 791, with fixed replacement text for
the merged paragraph that is itself lane-token-free; D.2's matching is
case-insensitive with one closed, mechanical, character-level path-literal
exemption; and §8.3 restates both qualifiers in D.2's own terms plus a
byte-unchanged requirement on the exempted occurrences. My independent
case-insensitive enumeration reproduces r7's arithmetic exactly — 77 lines
case-insensitively, 74 case-sensitively, the only-CI set {71, 791, 4018}, a
residual of {71, 4018} with three matches, all exempt, and zero outside the
exemption — and reproduces the r6 defect when the 792 anchor is restored, which
is direct evidence the fix is the operative one. B.2's wrapping note is now
correct on all ten entries as I re-verified line by line, and the two over-long
lines are reflowed with no wording change. Every binding fact still holds: the
five §2 pre-state hashes, the three script hashes, the r4/r5/r6 SHAs and the
r6-review digest and verdict, the 144-ID scope digest, the 454-transition-map
digest, and a §5.2 question byte-identical to r6's modulo the revision tokens.
Four Minor observations are recorded above; none affects an operational
requirement, a mechanical check, or any bound value.

Counts: 0 Critical, 0 Important, 4 Minor.

Verdict: CLEAN
