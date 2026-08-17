# Inventory-review recording design — r6

**Role:** `IMPLEMENTER` (CONTEXT.md "Agent roles (harness-wide)").
**Scope:** design only. This document changes no canonical file. It specifies
how the 447 `PENDING` content-bound inventory reviews on the canonical ledger
become `COMPLETE` under the active goal contract.

**Style/discipline reference:** `docs/goals/reviews/ledger/equity-os-blueprint-ledger-remediation-design-r7.md`
(pre-state hashes, exact mechanical rules, candidate proofs, transaction
safety). This design deliberately does **not** reuse r7's approval machinery —
§4 shows why no approval machinery applies here at all.

## 0. Supersession and round lineage

### 0.0 r5 → r6 — why this round exists (bead `eqos-w78`, round 5)

**Changelog.** r6: fixes r5 review I-1, I-2, I-3, M1–M4; re-pinned to
post-HR-0005 state.

**Lineage pin — the superseded bytes.** r5
(`docs/goals/reviews/ledger/equity-os-blueprint-inventory-review-recording-design-r5.md`)
is superseded in full at its **final** digest, SHA-256
`eb81474d043ae4568059120bad3fd948a238d52d3a33c7d4bd713bbd389de4b4` — the bytes
the r5 review actually read, recomputed by that reviewer at review start and
review end and found identical (r5-review §0.1). r5 remains on disk unmodified
as round lineage and must not be executed against.

**Correcting authority.** The independent review
`docs/goals/reviews/ledger/equity-os-blueprint-inventory-review-recording-design-r5-review-r0.md`,
SHA-256 `cb156f4e54b5d20d428bd70519a5ddebf027a12c34f8dc84aabe8a64f020571f`,
role `REVIEWER`, verdict **BLOCKED**, 0 Critical / 3 Important / 4 Minor. r6
changes exactly what those seven findings require, plus this supersession and
the re-pin I-3 forces.

**Scope of change — stated with its exceptions (r6, r5-review M-4).** Every
section not named in the table below is byte-identical to r5, **except** for
three classes of mechanical bookkeeping that carry no semantic content and are
listed here rather than left to be rediscovered: the title line (`r5` → `r6`),
the lineage-heading renumbering (r5's §0.0/§0.0a/§0.0b/§0.0c become
§0.0a/§0.0b/§0.0c/§0.0d, this section taking the §0.0 slot), and the four
cross-references that renumbering moves (§0.0a's "the rule r4 established in
§0.0b", §2.2.1's parenthetical and its "§0.0b records why"). r5 made the same
class of change under an unqualified claim; this clause is the correction.

| Finding | Severity | Disposition | Where |
|---|---|---|---|
| **I-1** — r5's indented-line skip (M-1b) re-opened the F-1 laundering class: an indented chunk inside a list item, or after a paragraph line, is CommonMark *content*, not a code block, so `X1`/`X2` — a `CLEAN` header plus an indented `ISSUES_FOUND` conclusion — were **accepted** under r5 | Important | **Fixed by dropping rule M-1(b) entirely.** Indented lines are scanned again; r4's behaviour is restored. M-1(a) (HTML comments unscanned) is kept. §2.2's "indent to quote" advice is removed — a fenced block is the one licensed quoting device. Remeasured over the 444: **0** indented scanned verdict lines and **0** indented candidate identity rows, so the drop is zero-regression in both directions (`scratchpad/w78/r6/measure_r6.py`, and `regress_r5_r6.py`: 0 divergences over 444). The reviewer's `X1`/`X2`, rebuilt independently, are now **`AMBIGUOUS_VERDICT`**. | §2.2, §2.2.1, recorder |
| **I-2** — a `Verdict:`-prefixed line that fails the carrier regex is not a malformed carrier but *no carrier at all*, so `X3` (parenthesised remainder), `X4` (two-word token `NOT CLEAN`) and `X5` (blockquoted conclusion) were accepted with the header's `CLEAN` standing unopposed | Important | **Fixed by two tripwires, not by widening the regex.** (1) Any **scanned** line matching `^[ \t]*(?:\*\*)?[ \t]*[Vv][Ee][Rr][Dd][Ii][Cc][Tt][ \t]*:` that is not a valid carrier → `MALFORMED_VERDICT_LINE`. (2) A **skipped** blockquote or HTML-comment line whose text carries a verdict token different from the accepted verdict → `CONFLICTING_QUOTED_VERDICT`; this is the residual of I-1/I-2 the reviewer named. Fenced blocks are deliberately exempt — §2.2 licenses a fence as *the* device for quoting a superseded round. Measured before implementing: **0** of the 444 carry a near-miss verdict line and **0** carry a conflicting quoted verdict, so both are zero-regression. `X3`/`X4` → `MALFORMED_VERDICT_LINE`; `X5` and its commented-out sibling → `CONFLICTING_QUOTED_VERDICT`. | §2.2.1, recorder |
| **I-3** — the package's pinned pre-state was superseded mid-round by the concurrent HR-0005 commit `501f3e7`; every §1.1 pin, both manifests and the rehearsal proof described a state that no longer existed, and the recorder refused every batch at §3.10 assert 6 | Important | **Fixed by re-pinning to the post-HR-0005 state**, all four values recomputed this round: goal `b77ea73d…`, ledger `e52ed95c…`, human-review `51bc4f9a…`, structural validator `77faeaf3…` (preimplementation `f7a225a1…`, extractor `5d20d796…` and `CONTEXT.md` `8f2795af…` are unchanged). The recorder's `PINNED_STRUCTURAL_SHA256` and `PINNED_LEDGER_PRESTATE_SHA256` are re-pinned, which changes the recorder's bytes and therefore **forced a fresh five-leg rehearsal** — re-run this round, 5/5, with a new proof bound to the new recorder digest. Both manifests were regenerated against the live ledger prehash and the current dirty-path baseline, and both `--dry-run` invocations re-executed. §3.6 is reconciled with the post-HR-0005 validator and now states the **two-state** rule. | §1.1, §3.6, §3.10, §6.3, recorder, manifests |
| **M-1** — §2.2.1's HTML-comment clause describes behaviour the code does not have: it claims a comment swallows fence delimiters and that the two states are "mutually exclusive", but the fence machine runs unconditionally first | Minor | **Fixed by restating the clause to the code's actual behaviour**, the cheaper of the two offered remedies and the one that changes no byte of parse output: the fence machine runs first, so a fence delimiter inside an open comment **does** toggle fence state, both states can be open at once, and the precedence at EOF is stated — `UNTERMINATED_FENCE` wins when both are open. Corpus incidence remains 0 of 444 containing `<!--`. | §2.2.1, recorder comments |
| **M-2** — §3.10's L5 "the temp and preimage files are required to survive" is contradicted by the rehearsal's own `temp_files_surviving: 0`, and `rollback()` consumed a corrupted preimage before hashing it, so the journal named a file that no longer existed | Minor | **Fixed in both places.** The recorder now hashes the preimage **before** the restoring rename and records `preimage_sha256_before_restore` and `surviving_preimage_exists` in the `RECOVERY_REQUIRED` journal payload, so an operator can tell "corrupted" from "removed". §3.10's L5 note is corrected to what the code does: the staged temp file is consumed by the forward `os.replace` and the preimage by the restoring rename, so `temp_files_surviving: 0` is the honest L5 outcome, and L5's exemption from the temp-free check is stated as a non-assertion rather than as a claim that those files survive. | §3.10, recorder |
| **M-3** — the manifest-side path checks abort with prose only, so "triage is mechanical" has a hole exactly where operator error lives | Minor | **Fixed in code.** A non-repo-relative `artifact_path`, a path outside `…/inventory/<CID>/`, and a filename that is not `<REVIEW_TYPE>-r<N>.md` now abort `MANIFEST_BAD_ARTIFACT_PATH`; a symlink or other non-regular file aborts `ARTIFACT_NOT_REGULAR_FILE`. Both are added to §2.2.1's reason table, which now carries **eighteen** tokens. | §2.2.1, recorder |
| **M-4** — "Every section not named in the table below is byte-identical to r4" is not literally true: the title line, the lineage renumbering and one cross-reference also changed | Minor | **Fixed by carrying the exception**, in the "Scope of change" paragraph above, enumerated rather than waved at. | §0.0 |

**Measured effect of r6** (all 444 artifacts): parse output is **byte-identical
to r5's** — 444 parse, 0 abort, 0 field divergences
(`scratchpad/w78/r6/regress_r5_r6.py`, against a copy of the r5 recorder saved
before any edit at its dispatched digest `8d0410cd…`). Both dry-run batches now
produce **different** `candidate_sha256` values from r5's — `52debc48…` and
`63e86747…` against r5's `b1689280…` and `b85b8efe…` — and the difference is
attributable **entirely to the new ledger pre-state**, not to any r6 behavioural
edit: a copy of the r5 recorder with *only* its two pin constants updated
produces `52debc48…` and `63e86747…` **bit-identically**
(`scratchpad/w78/r6/record_r5_repinned_only.py`). r6 changes which artifacts are
refused; it changes no written byte. Ten fixtures — the
reviewer's `X1`–`X5` rebuilt independently, a commented-out sibling, and four
controls including a fenced quote of a superseded `ISSUES_FOUND` — all behave as
this table states (`scratchpad/w78/r6/fixtures_r6.py`).

**Predetermined next independent review path:**
`docs/goals/reviews/ledger/equity-os-blueprint-inventory-review-recording-design-r6-review-r0.md`,
an independent `REVIEWER`-role agent and context, distinct from this
`IMPLEMENTER` dispatch and from the r0, r1, r2, r3, r4 and r5 reviewers (goal
L947-949, CONTEXT.md L137-139).

### 0.0a r4 → r5 — why r5 existed (bead `eqos-w78`, round 4)

**Changelog.** r5: fixes r4 review I-1, I-2, M1–M5.

**Lineage pin — the superseded bytes.** r4
(`docs/goals/reviews/ledger/equity-os-blueprint-inventory-review-recording-design-r4.md`)
is superseded in full at its **final** digest, SHA-256
`9ed08e186102bfe371d08b85b9101cbe4798562bb80bb616edabb84cae5fe5b5` — the bytes
the r4 review actually read, recomputed by that reviewer at review start and
review end and found identical (r4-review §0.1). r4 remains on disk unmodified
as round lineage and must not be executed against. Per the rule r4 established
in §0.0b, **a round is never amended in place**; this correction is a new round
with the superseded digest pinned.

**Correcting authority.** The independent review
`docs/goals/reviews/ledger/equity-os-blueprint-inventory-review-recording-design-r4-review-r0.md`,
SHA-256 `9a455342a3ad83d6cf37f9741a5e46395f615ebd5809cb5dc541f160bc841134`,
role `REVIEWER`, verdict **BLOCKED**, 0 Critical / 2 Important / 5 Minor. r5
changes exactly what those seven findings require, plus this supersession.
Every section not named in the table below is byte-identical to r4, so r5 can
be reviewed differentially.

| Finding | Severity | Disposition | Where |
|---|---|---|---|
| **I-1** — a fence still open at EOF silently suppresses a verdict the artifact states in its own voice; the design specifies fence opening and closing but not termination | Important | **Fixed.** After the line loop, an open fence is a hard skip with the named reason `UNTERMINATED_FENCE`; the symmetric `UNTERMINATED_COMMENT` covers the construct M-1 adds. Both are stated in §2.2.1's fence rules and in the skip-reason table. Zero-regression by construction: 0 of the 444 artifacts has an unterminated fence (remeasured this round). The reviewer's `N6` fixture, rebuilt independently, parses `CLEAN` under r4 and is **rejected `UNTERMINATED_FENCE`** under r5. | §2.2.1, recorder |
| **I-2** — §3.10's Status and §7.9's closing parenthetical say the recorder does not exist and the rehearsal has not been performed; both were false in r4 | Important | **Fixed.** Both paragraphs now state what is true: the recorder's digest, the rehearsal proof's path/digest and its recorder binding, and the dry-run results. Named here rather than amended silently, which is what preserves the "byte-identical outside the named sections" property. | **§3.10**, **§7.9** |
| **M-1** — only fences and blockquotes count as non-asserted text; HTML comments and indented code blocks do not | Minor | **Fixed by widening the guard, on measurement.** Adopted **both** halves: an HTML comment (single- or multi-line) is unscanned, and a line indented by ≥4 spaces or a leading tab is unscanned. Measured before adopting (`scratchpad/w78/r5/measure_m1.py`): **0** of 444 artifacts contain `<!--`, **0** accepted identity rows are indented, **0** scanned verdict lines are indented, and **0** fence delimiters are indented — so the fence state machine is untouched and the widening cannot change any current parse. Verified after: parse output byte-identical to r4 over all 444. | §2.2, §2.2.1, recorder |
| **M-2** — §3.2 says "exactly these required keys"; `load_manifest` enforced presence only | Minor | **Fixed in code**, the stricter of the two offered remedies. The top-level and per-entry key sets are now closed in both directions, with the named reason `MANIFEST_UNKNOWN_KEY`. A stale r2-shaped entry carrying `captured_at` is refused by name instead of silently ignored (measured: r4 accepted it, r5 rejects it). | §3.2, recorder |
| **M-3** — the implemented `captured_at` provenance was not the expression §2.2.1 states; `validate_batch_entry`'s computation was dead code | Minor | **Fixed in code**, so the document's statement becomes true rather than being restated. `run_batch` now keeps the parsed `captured_at` and `build_candidate` writes **that** value; the manifest's `timestamp` is no longer the source. Behaviour is unchanged — the two are equal by the `MANIFEST_DISAGREEMENT` check — and the candidate digests are bit-identical, which is the proof the change is provenance-only. | §2.2.1, recorder |
| **M-4** — a documented `MISSING_FIELD` condition is unreachable | Minor | **Fixed by disclosure, check retained.** The whitespace-only clause is flagged **unreachable by construction** in the reason table, with the reason (values are stripped, and a value normalizing to empty carries nothing). Retained as a defensive assertion, following r4's precedent for the unexercised 2-cell `verdict` alias: disclose, do not silently drop. | §2.2.1 |
| **M-5** — path/body disagreements abort under `MANIFEST_DISAGREEMENT` rather than a path-specific token; `ROLE_MISMATCH` and `FUTURE_TIMESTAMP` are likewise shadowed whenever the manifest is truthful | Minor | **Fixed in code**, the stronger of the two offered remedies. The manifest comparison now runs **last**, after the path cross-check, the verdict, role and timestamp checks, and §2.2.1 states that precedence as contract. Path/body disagreements get their own token, `PATH_BODY_MISMATCH`. The set of accepted artifacts is unchanged — only which name a rejection carries, which is what the token exists for. | §2.2.1, recorder |

**Measured effect of r5** (all 444 artifacts): parse output is **byte-identical
to r4's** — 444 parse, 0 abort, 0 field divergences
(`scratchpad/w78/r5/regress_r4_r5.py`, against a copy of the r4 recorder saved
before any edit at its dispatched digest `32947a02…`). Both dry-run batches
produce the same `candidate_sha256` values as r4. The r4 review's `N6`
(unterminated fence) and `N3` (multi-line HTML comment) fixtures, rebuilt
independently, are now rejected; its `N1` fixture — a truthful `CLEAN` artifact
quoting a superseded `ISSUES_FOUND` in an indented block — aborted the whole
batch as `AMBIGUOUS_VERDICT` under r4 and is **accepted** under r5, which is
what M-1(b) asks for.

**Predetermined next independent review path:**
`docs/goals/reviews/ledger/equity-os-blueprint-inventory-review-recording-design-r5-review-r0.md`,
an independent `REVIEWER`-role agent and context, distinct from this
`IMPLEMENTER` dispatch and from the r0, r1, r2, r3 and r4 reviewers (goal
L947-949, CONTEXT.md L137-139).

### 0.0b r3 → r4 — why r4 existed (bead `eqos-w78`, round 3)

**Changelog.** r4: fixes r3 review F-1, F-2, M1–M7.

**Lineage pin — the superseded bytes.** r3
(`docs/goals/reviews/ledger/equity-os-blueprint-inventory-review-recording-design-r3.md`)
is superseded in full at its **final** digest, SHA-256
`98d96672e9eec34f8b9698246257b6acc4b81d8113894d66e1105cbd188b61cc` — the bytes
the r3 review actually read, recomputed by that reviewer at review start and
review end (r3-review §0.1). r3 remains on disk unmodified as round lineage and
must not be executed against. Pinning it here is the fix for r3-review **F-9**:
r3 was amended in place without pinning its pre-amendment bytes, which cost the
differential-review property. From r4 on, **a round is never amended in place**;
a correction is a new round with the superseded digest pinned.

**Correcting authority.** The independent review
`docs/goals/reviews/ledger/equity-os-blueprint-inventory-review-recording-design-r3-review-r0.md`,
SHA-256 `e05baabd249edd56bad211b9dbea200b28929e797ad33701f93063b4811ffd24`,
role `REVIEWER`, verdict **BLOCKED**, 1 Critical / 1 Important / 7 Minor. r4
changes exactly what those nine findings require, plus this supersession.
Every section not named in the table below is byte-identical to r3, so r4 can
be reviewed differentially.

| Finding | Severity | Disposition | Where |
|---|---|---|---|
| **F-1** — a fenced/quoted `verdict: CLEAN` launders a non-clean artifact into a `CLEAN` recording; the verdict regex does not match this repository's house non-clean form | Critical | **Fixed, both halves.** The parser is now fence- and blockquote-aware, and the verdict rule accepts an optional ` — <remainder>` / ` - <remainder>` tail with the bare TOKEN as the verdict. Two new named skip reasons, `MISSING_VERDICT` and `AMBIGUOUS_VERDICT`. §2.2 now states the non-clean line format for r1+ artifacts, so a reviewer writing a non-clean artifact has a contract to conform to. | §2.2, **§2.2.1** |
| **F-2** — the value-normalization clause says "in both forms" but three forms exist; the literal prose parses 58 artifacts differently from the code | Important | **Fixed.** "in **all three forms** (A, A′ and B)", with A′'s two value cells named explicitly. The code was the correct side; behaviour is unchanged. Reconfirmed: a parser built from the r4 prose and the recorder agree on all 444, 0 `AMBIGUOUS_FIELD`. | **§2.2.1** |
| **M1** (F-3) — five of the eight named skip reasons never appear in an abort message | Minor | **Fixed in code.** `ROUND_FILENAME_MISMATCH`, `NOT_CLEAN`, `MANIFEST_DISAGREEMENT`, `ROLE_MISMATCH` and `FUTURE_TIMESTAMP` are now named in the `RecorderAbort` text, alongside the three that already were and the two new verdict reasons. | recorder |
| **M2** (F-4) — the A′ example label is attributed 58 artifacts; the literal label covers 40 | Minor | **Fixed.** 40 carry `role binding`, 18 carry `role binding table`; 58 total, both aliases listed. | **§2.2.1** |
| **M3** (F-5) — "116 pairs with two accepted rows" silently excludes the verdict line | Minor | **Fixed.** Both figures are now stated with their scope: 116 excluding the verdict line, **560** including it; 0 disagree either way. | **§2.2.1** |
| **M4** (F-6) — the 2-cell `verdict` alias is reached by 0 artifacts, contradicting "every string below was measured" | Minor | **Fixed by disclosure, alias retained.** It is kept (dropping it would silently widen what an artifact may leave unstated) and flagged **unexercised — 0 of 444**. | **§2.2.1** |
| **M5** (F-7) — an empty-valued accepted row is silently dropped and this is unstated | Minor | **Fixed.** The empty-cell rule is now stated: an accepted row whose value normalizes to the empty string carries nothing, exactly as if the row were absent. 0 divergences either way over the 444. | **§2.2.1** |
| **M6** (F-8) — the supplied dry-run evidence cannot test `MANIFEST_DISAGREEMENT`, because the manifests are built by the recorder's own parser | Minor | **Fixed in evidence.** A hand-crafted, non-tautological `MANIFEST_DISAGREEMENT` suite (manifest lying about `model`, `effort`, `timestamp`, `reviewer`, `review_round`, `artifact_sha256`) is in the r4 build report; all six are rejected, the truthful control is accepted. The tautology note stays in `make_manifest.py`'s docstring. | build report |
| **M7** (F-9) — the "amended in place" scope claim is unverifiable | Minor | **Fixed.** See the lineage pin above; no r4 section is amended in place. | §0.0 |

**One deviation from the dispatched remedy — stated, not buried.** The r4
dispatch specified the verdict rule as "**exactly one** verdict line per
artifact outside fences/blockquotes; two or more → `AMBIGUOUS_VERDICT`
regardless of equality of token". Measured before implementing
(`scratchpad/w78/r4/count_verdict_lines.py`): **all 444 artifacts on disk carry
exactly two verdict lines** — the header assertion and the conclusion
assertion, always the same token, none inside a fence. That literal rule would
therefore reject **444 of 444**, contradicting the same dispatch's
zero-regression requirement. r4 implements the rule keyed on **distinct verdict
values**, not on line count:

| Verdict carriers outside fences/blockquotes | Distinct values | Outcome |
|---:|---:|---|
| 0 | — | skip, reason `MISSING_VERDICT` |
| ≥ 1 | 1 | **accept** that value |
| ≥ 2 | ≥ 2 | skip, reason `AMBIGUOUS_VERDICT` |

This closes F-1 strictly more thoroughly than the line-count rule would in the
case that matters: an attacker who *un*-fences the quoted `verdict: CLEAN` gets
`AMBIGUOUS_VERDICT` rather than a silent second opinion, and one who leaves it
fenced gets the honest `ISSUES_FOUND` and then `NOT_CLEAN`. It is weaker only
for the "same verdict stated twice" case — which is the house format every one
of the 444 artifacts uses, and which asserts nothing contradictory.

**Measured effect of r4** (all 444 artifacts): parse output is **byte-identical
to r3's** — 444 parse, 0 do not, 0 field divergences
(`scratchpad/w78/r4/diff_parse.py`). The r3 review's own attack fixture
`scratchpad/w78/review/c3.md` parses `CLEAN` under r3 and **`ISSUES_FOUND`**
under r4, and is refused as `NOT_CLEAN`.

**Predetermined next independent review path:**
`docs/goals/reviews/ledger/equity-os-blueprint-inventory-review-recording-design-r4-review-r0.md`,
an independent `REVIEWER`-role agent and context, distinct from this
`IMPLEMENTER` dispatch and from the r0, r1, r2 and r3 reviewers (goal L947-949,
CONTEXT.md L137-139).

### 0.0c r2 → r3 — why r3 existed (bead `eqos-w78`)

**Changelog (r3, retained verbatim as lineage).** r3 amended: closed
label-alias table (Orchestrator decision). The amendment was made in place —
that document is still r3 — and was confined to that §0.0 (change 4 and the
"Measured effect" paragraph) and to §2.2.1 (the label alias table, the
three-cell row shape, the per-field one-accepted-row rule, and the two renamed
skip reasons). No other section moved. r3-review F-9 correctly notes this
in-place amendment was unverifiable; r4 §0.0 pins r3's final digest and forbids
the practice going forward.

**This r3 supersedes r2 in full.** r2
(`docs/goals/reviews/ledger/equity-os-blueprint-inventory-review-recording-design-r2.md`,
SHA-256 `adf908ac8cec01a55a53438624c6a8913f673f5b7cecd3e955fc4919f73803fb`) is
retained as round lineage and must not be executed against. **Every section
below other than this §0.0, the new §2.2.1, the amended `captured_at` row in
§2.2, and the amended §3.2 manifest paragraph is byte-identical to r2**, so r3
can be reviewed differentially. §0.1's r1→r2 dispositions all remain in force.

**Correcting authority.** Bead `eqos-w78` (P0 bug, filed 2026-08-16 on the
first live use of the recorder). Nothing else in this round is discretionary.

**The defect.** r2 §2.2 specifies the verdict artifact's *content* — "an
explicit `verdict: CLEAN` line", plus the listed identity fields — but never
states a **machine-readable contract**: which byte patterns the recorder
extracts, and how. The recorder implemented one bare `key: value` regex
(`^([a-z0-9_]+):[ \t]*(\S.*?)[ \t]*$`) and additionally demanded an artifact
field `captured_at` that §2.2 never asks the reviewer to write. The independent
`REVIEWER` agents, following §2.2's stated format precedent (the program-level
inventory artifacts, which use Markdown tables), recorded their identity fields
in Markdown table rows. Result: **0 of the 444 verdict artifacts written so far
parsed**, and `--dry-run` aborted on batch 1.

**Root cause, stated plainly.** The build review exercised the recorder only
against verdict artifacts the **builder itself** wrote, in the builder's own
`key: value` shape — so tool and fixture agreed with each other and with
nothing else. The r0/r1/r2 design reviews checked §2.2's *content* list against
the ledger schema, but there was no machine-readable contract for them to check
the tool against. A format contract that only one side of the interface has
ever seen is not a contract.

**Direction, and what it forbids.** The 444 artifacts are review evidence: each
one is an independent `REVIEWER` dispatch's durable record, content-bound by
`content_sha256` in the evidence object. **The tool adapts to the evidence, not
the reverse.** No verdict artifact under
`docs/goals/reviews/ledger/inventory/` is rewritten, reformatted, or
regenerated to suit the recorder — not in this round and not in any later one.

**What r3 changes.**

| # | Change | Where |
|---:|---|---|
| 1 | A closed, machine-readable verdict-artifact contract: the two accepted field forms, the verdict-line form, the closed field list, normalization, and the named skip reasons. | new **§2.2.1** |
| 2 | `captured_at` is **removed from the artifact field list** and given an explicit provenance: the recorder derives it from the artifact's own review `timestamp`. | **§2.2.1**, §2.2 evidence table |
| 3 | The batch manifest no longer carries `captured_at` per review entry — it is derived, not declared. | **§2.2.1**, §3.2 |
| 4 | A **closed, enumerated label alias table** for the prose-labelled artifact family, plus the three-cell `\| Role binding \| CONTEXT.md \| <sha> \|` row shape and a per-field "exactly one accepted row" rule. | **§2.2.1** |

**Measured effect** (all 444 artifacts, parser run at r3 §2.2.1 as amended):
**444 parse, 0 do not.** Before change 4 the figure was 370/74: the 74 are a
second, prose-labelled artifact family (`| Component ID | ... |`,
`| Review timestamp (UTC) | ... |`, `| Reviewer identity / session | ... |`,
`| Role binding | CONTEXT.md | <sha> |`) written by a different Reviewer
cohort, with per-cohort label drift ("Review round" / "Round", "Review
timestamp (UTC)" / "Review UTC" / "Review UTC timestamp").

**Orchestrator decision (this amendment).** Those 74 artifacts are genuine
independent review evidence and will **not** be re-reviewed. The recorder reads
them — but through a **closed, enumerated alias table** (§2.2.1), never through
a heuristic. Every accepted label is a literal string measured in the artifacts
on disk and written into the table by hand; an unlisted label carries nothing,
and widening the table requires a new design round. This is the opposite of the
guessing that produced `eqos-w78`: the earlier defect was a tool asserting a
format no reviewer had agreed to, whereas the alias table is an exhaustive
transcription of the formats the reviewers actually wrote, with a mechanical
sweep over all 444 artifacts as its proof.

Consequently the earlier "30 components stay `PENDING` until a fresh `REVIEWER`
round" plan is withdrawn: those components are recordable. The components that
remain unrecordable are the ones with a non-clean verdict or no artifact at all
(§5.4) — freshly measured: 15 components carry at least one `ISSUES_FOUND`
verdict (20 of the 444 artifacts) and `DISP-R-1` has no `r0` artifact, leaving
153 of the 169 review-bearing rows recordable and 16 blocked (44 rows are
aliases with no review slots; 153 + 16 + 44 = 213).

**Predetermined next independent review path:**
`docs/goals/reviews/ledger/equity-os-blueprint-inventory-review-recording-design-r3-review-r0.md`,
an independent `REVIEWER`-role agent and context, distinct from this
`IMPLEMENTER` dispatch and from the r0, r1, and r2 reviewers (goal L947-949,
CONTEXT.md L137-139).

### 0.0d Round lineage below this point

**r2 superseded r1 in full.** The operational design of
`docs/goals/reviews/ledger/equity-os-blueprint-inventory-review-recording-design-r1.md`
(SHA-256 `1bc340ac3d50024de4aed21f95b7b9ae17c03e66b0745420d4e8c3928a9070d7`) is
superseded; r1 — and, transitively, r0
(`5ec10de959d56145c00d186924c01c2d8cc3af5c488a78e4aadf5afbefcd7dea`) — is
retained only as round lineage and must not be executed against.

**Correcting authority.** The sole authority for the r1→r2 delta is the
independent review
`docs/goals/reviews/ledger/equity-os-blueprint-inventory-review-recording-design-r1-review-r0.md`
(SHA-256 `60e41dc0e1d93ec72b6829d503a9fedd897539e7c9df258c1d73121d04b3d5d9`),
role `REVIEWER`, verdict **CLEAN**, 0 Critical / 0 Important / 5 Minor. r2
changes exactly what those five findings require, plus this supersession and
header plumbing. Nothing else is reworded: every unflagged section is
byte-identical to r1 so that r2 can be reviewed differentially.

**Predetermined next independent review path:**
`docs/goals/reviews/ledger/equity-os-blueprint-inventory-review-recording-design-r2-review-r0.md`
(round `r0` of the r2 artifact; review-round ceiling per goal L982-1000). That
review must be an independent `REVIEWER`-role agent and context, distinct from
this `IMPLEMENTER` dispatch and from the r0 and r1 reviewers (goal L947-949,
CONTEXT.md L137-139).

### 0.1 Disposition of the five r1-review Minor findings

Every citation below was re-read in this round against the cited bytes, and
every hash and count was recomputed; nothing is transcribed from the review.
Where the review's own line numbers were off, this round uses the measured
values and says so.

| # | r1-review finding | Disposition | Where |
|---:|---|---|---|
| 1 | §7.4 carries a stale batch range ("9–17") that r1's 17→18 renumbering created | **Fixed.** Now **9–18**. The whole document was swept for further renumbering residue: `9–17` was the **only** stale range or count. Verified consistent: §5.2's 18-batch table (1–5, 6, 7–9, 10–12, 13–18), §3.10's recorder-hash assert (r2 assert 5) and its "18-batch program", §7.3's "before batch 13", §0.1's own "13–18". | §7.4 |
| 2 | The M-5 citation correction was applied in §1.2 only | **Fixed everywhere, with two of the review's own numbers corrected.** §8 row 1: goal L233-236, L379 → **L208-211, L495-496**. §8 row 3 and §5.4: `validate_ledger_structural.py:337` → **`:342`** (`:337` is the `PENDING`-branch null assertion; the `CLEAN` rule is `:342`). §5.4's paired `PENDING` cite `:329-336` → **`:332-338`** (the actual `PENDING` branch). §5.2 and §1.2: "goal L~262-278" → **L235-245** for the kind→rule mapping — the review said L236-244; the lead-in sentence is at L235 and the table body runs L237-245, so both of the review's endpoints were off by one. | §1.2, §5.2, §5.4, §8 |
| 3 | §3.10 assert 5 (as numbered in r1) — its ledger clause is ambiguous — one reading aborts every batch after the first | **Fixed, load-bearing.** Assert 5 is split into a validator pin (assert 6) and a ledger pin (assert 7). The proof field is renamed `ledger_prestate_sha256` → **`replica_ledger_prestate_sha256`**, and assert 7 states in terms that admit no other reading that the compared value is the **rehearsal replica's own starting ledger digest**, never the live canonical ledger, and that all three quantities it compares are constants fixed before batch 1. The live ledger keeps its own per-batch check: §3.8 step 2's "Ledger prehash equals the recorded prehash", unchanged. | §3.10 |
| 4 | The rehearsal legs never exercise `RECOVERY_REQUIRED` | **Fixed.** Fifth leg **L5** added: preimage corrupted/removed before rollback, requiring journal `RECOVERY_REQUIRED`, the full step-10 unproven-path payload, a nonzero exit, and a second recorder invocation refused at step 1. Added to the legs table, the proof-object schema, and the step-2 asserts (new assert 4), with the `temp_files_surviving == 0` requirement correctly scoped to L1–L4, since step 10 preserves those files by design. Because findings 3 and 4 together change the proof object's shape, its `schema` string is bumped `inventory-review-rollback-rehearsal/v1` → **`/v2`**, so a stale r1-shaped proof is rejected by name. | §3.10, §7.9 |
| 5 | The "mandatory" rehearsal gate is self-attested | **Fixed.** One paragraph now states plainly that the gate is an operator-discipline control over a gitignored workstream evidence artifact — not an enforcement boundary and not ledger evidence. | §3.10 |

**Lineage.** The ten r0-review Minors dispositioned in r1 §0.1 are all still in
force in r2; none is reopened, and the r1-review confirmed each of them closed.
r2 touches r1's M-5 fix only to extend it (finding 2 above) and r1's M-9d fix
only to complete it (findings 3–5).

---

## 1. Verified pre-state

### 1.1 Pinned hashes

Captured at design time by `sha256sum` from the repository root, working tree
at `501f3e7` with `.beads/issues.jsonl` dirty (unrelated).

**Re-pinned in r6 (r5-review I-3).** r0–r5 pinned the post-HR-0004 state. The
concurrent commit `501f3e708099f26e15d0bbd018f1cb9b496fa490` — *"feat(ledger):
execute HR-0005 RECONCILE_AUTHORITY amendment (DISP-R-1 unpinned)"* — landed
between the r5 build and the r5 review and advanced the goal, the ledger, the
human-review register and the structural validator. All seven values below were
recomputed at the top of this round; the four that moved are marked.

| Path | SHA-256 |
|---|---|
| `docs/goals/equity-os-blueprint-completion.md` | `b77ea73d90fb6f7499a7fcf74f50c471bb03dd5a6f1bf0c71f510af917d0b0c9` **(moved in HR-0005; was `f15f7ab5…`)** |
| `docs/goals/equity-os-blueprint-component-ledger.jsonl` | `e52ed95c842a5546d1ae04108c06f4a38f49dd9a846d94bdbe8f612f38947c49` **(moved in HR-0005; was `de236d7e…`)** |
| `docs/goals/equity-os-blueprint-human-review-needed.md` | `51bc4f9afa8a3e3478affc5452118e7dc71dd3e3b28568b4faabcbcd2a72a9ce` **(moved in HR-0005; was `094fcdfa…`)** |
| `scripts/equity_os_blueprint/validate_ledger_structural.py` | `77faeaf3dee13d5d2bfb50c255b054cde94ef0118751b247e23248e343964fff` **(moved in HR-0005; was `731d0d8b…`)** |
| `scripts/equity_os_blueprint/validate_ledger_preimplementation.py` | `f7a225a1f99cb85c92cde3094505a92a746552280eb45dae0253a71ab9048013` |
| `scripts/equity_os_blueprint/extract_goal_validators.py` | `5d20d796666d1154fb3c84ba4fa7407ee82819510a5ac06254f7f4a3126c6f2a` |
| `CONTEXT.md` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |

All seven match the values supplied in the r6 task brief and were recomputed
from the working tree at the start and the end of this round. Post-**HR-0005**
state. The recorder pins three of them as constants —
`PINNED_STRUCTURAL_SHA256`, `PINNED_PREIMPL_SHA256`, `PINNED_EXTRACTOR_SHA256`
— plus `PINNED_LEDGER_PRESTATE_SHA256`; all four were re-pinned in r6 where they
moved, which is what changes the recorder's bytes and forces the fresh
rehearsal recorded in §3.10.

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
`semantic_review` rule is at **L274-280**. The claims themselves were unchanged
and independently verified.)*

*(r2 citation correction, r1-review Minor 2. r1 said the non-register
`semantic_review` rule was "cited correctly elsewhere as L~262-278". That
elsewhere is §5.2, where the citation is attached to a different claim — that
the `SCOPE` rule is fixed by kind — whose source is the kind→rule mapping table
at **L235-245** (lead-in "Rules are fixed by kind:" at L235, table body
L237-245; re-read this round). L262-278 spans `ACTIVE_NEGATIVE_CONTROL` and the
`semantic_review` paragraph, so it was right for the rule §1.2 cites and wrong
for the claim §5.2 attaches it to. §5.2 now cites L235-245. Note the r1 review
gave this location as "L236-244"; both endpoints are off by one against the
bytes, so this round uses the measured range.)*

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
| `captured_at` | UTC RFC3339, `<=` the review `timestamp`. **§2.2.1: derived — set equal to the review `timestamp`. Never read from the artifact and never declared in the manifest.** |

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

**The verdict line — both cases, stated (r4, r3-review F-1).** r0–r3 specified a
line format only for the clean case, so a reviewer writing a **non-clean**
artifact had no format to conform to and reasonably reached for this
repository's house form. Both are now contract:

| Case | Line a reviewer writes | Parsed verdict |
|---|---|---|
| clean | `**verdict: CLEAN**` | `CLEAN` |
| non-clean | `**verdict: ISSUES_FOUND — 3 Critical, 1 Important, 4 Minor**` | `ISSUES_FOUND` |

The token immediately after `verdict:` is the verdict; everything from the
` — ` (em dash, or ` - `) onward is a human-readable remainder the recorder
matches and discards. `CLEAN` is still the only **recordable** value (§5.4) —
this widening is about *reading the artifact correctly*, not about recording
more of them. A reviewer writing an `r1` artifact for one of the 15 components
that carry an `ISSUES_FOUND` `r0` should use the non-clean row above, and may
quote the superseded round — **inside a fenced block**. That is the one
licensed quoting device (§2.2.1). Blockquotes and HTML comments are also
unscanned, but a verdict token stated in one that contradicts the artifact's own
verdict is refused as `CONFLICTING_QUOTED_VERDICT` rather than silently
outvoted, because `>` is used as a callout in this repository at least as often
as it is used to quote (r6, r5-review I-2). **Indentation is not a quoting
device**: r5 briefly made indented lines unscanned and r6 drops that rule, since
an indented chunk inside a list item, or after a paragraph line, renders as
ordinary asserted prose (r5-review I-1). A fenced block or an HTML comment that
is never closed is a hard skip, not a licence to stop reading the artifact: see
`UNTERMINATED_FENCE` in §2.2.1.

The verdict artifact's own bytes are not parsed by any validator. The ledger
review object is the machine-readable record; the artifact is its evidence and
its audit trail. The recorder must therefore parse the artifact for the values
it copies, and must abort on any field it cannot read — never default.

### 2.2.1 Machine-readable verdict-artifact contract

*(New in r3, per §0.0c; corrected in r4 per §0.0b, in r5 per §0.0a, and in r6 per §0.0. This subsection is the
**whole** contract between a verdict artifact and the recorder. Anything not
stated here is not parsed.)*

The artifact stays human-readable Markdown; §2.2's content list is unchanged.
This subsection states only which byte patterns the recorder extracts.

**Which lines are scanned at all — quoted constructs (r4, r3-review F-1;
widened in r5, r4-review I-1 and M-1; narrowed again in r6, r5-review I-1).**
Before any rule below is applied, the recorder walks the artifact line by line
holding two bits of state, the open fence and the open HTML comment:

- A line matching the fence pattern

  ~~~
  ^[ \t]*(`{3,}|~{3,})
  ~~~

  **opens** a fenced block if none is open, recording the marker character
  (backtick or tilde) and the run length; if one is open, it **closes** it when
  the marker character is the same, the run is at least as long, and the rest of
  the line is blank. The delimiter line itself is never scanned.
- Every line while a fence is open is **not scanned**.
- **(r5; clause corrected in r6, r5-review M-1)** With no fence open, a line
  containing `<!--` **opens** an HTML comment unless the same line also contains
  a later `-->`; the line itself is never scanned either way. Every line while a
  comment is open is **not scanned** — **except a fence delimiter**. The fence
  state machine runs unconditionally first, so a line matching the fence pattern
  toggles fence state whether or not a comment is open, and the two states are
  therefore **not** mutually exclusive: both can be open at once, in which case
  the `-->` line is consumed by the fence branch and the comment does not close.
  r5's text asserted the opposite ("a comment, once open, swallows everything up
  to and including the first line containing `-->`"; "the two states are
  therefore mutually exclusive") and described behaviour the recorder does not
  have. **Precedence at EOF, now stated:** if both states are open when the file
  ends, the reported reason is `UNTERMINATED_FENCE`. Both readings fail closed
  and 0 of the 444 artifacts contain `<!--` at all, so this correction changes no
  parse; it makes the contract text true.
- A line matching `^[ \t]*>` — a Markdown blockquote — is **not scanned**,
  whether or not a fence is open.
- **(r6, r5-review I-1) Indentation is not a quoting device.** r5 added a rule
  making any line matching `^(?: {4,}|\t)` unscanned, on the premise that it is
  a Markdown indented code block. That premise is false in the two most common
  contexts: an indented chunk **inside a list item** is content indentation, and
  an indented line **after a paragraph line** is a lazy paragraph continuation —
  an indented code block cannot interrupt a paragraph. Both render as ordinary
  asserted prose, and 13 of the 444 artifacts already contain such lines. r6
  **drops the rule**; indented lines are scanned exactly as in r4. Remeasured
  before and after the change: **0** indented scanned verdict lines and **0**
  indented candidate identity rows across the 444, so the drop is zero-regression
  in both directions.
- **(r6, r5-review I-2) Near-miss verdict lines are refused, not ignored.** The
  verdict carrier regex below must match to end of line, so a **scanned** line
  that announces a verdict and then deviates — `**Verdict: ISSUES_FOUND (1
  Critical, 0 Important, 0 Minor)**`, `**Verdict: NOT CLEAN — 1 Critical**` — is
  not a malformed carrier: it is not a carrier at all, and the artifact's header
  assertion stands unopposed. Any scanned line matching
  `^[ \t]*(?:\*\*)?[ \t]*[Vv][Ee][Rr][Dd][Ii][Cc][Tt][ \t]*:` that is not a
  valid carrier is therefore a hard skip with the named reason
  `MALFORMED_VERDICT_LINE`. This is a tripwire, deliberately not a wider regex:
  §2.2 fixes two admissible line forms as contract, and anything else is a
  reviewer writing outside the contract, which the recorder must refuse rather
  than interpret. Measured over the 444: **0** such lines exist today.
- **(r6, r5-review I-2) A quoted verdict that contradicts the artifact's own is
  refused.** Blockquote and HTML-comment lines stay unscanned — but the recorder
  additionally collects any verdict token they carry (blockquote markers and
  comment delimiters stripped first) and, if a collected token differs from the
  accepted verdict, skips the artifact with the named reason
  `CONFLICTING_QUOTED_VERDICT`. **Fenced blocks are exempt by design**: §2.2
  licenses a fence as *the* device for quoting a superseded round, so a fenced
  `verdict: ISSUES_FOUND` inside a truthful `CLEAN` artifact is legitimate and
  stays accepted. The asymmetry is deliberate — `>` is used as a callout in this
  repository (this very subsection states its `captured_at` decision inside one)
  and 375 of the 444 artifacts contain blockquote lines, so a contradicting
  verdict in one is far more likely to be an assertion the recorder failed to
  read than a quotation. Measured over the 444: **0** conflicting quoted
  verdicts exist today. Together with `MALFORMED_VERDICT_LINE` this closes the
  residual the r5 review identified: every construct that a human reads as a
  verdict either counts toward `AMBIGUOUS_VERDICT` or aborts under its own name.
- **(r5, r4-review I-1) Termination is part of the contract.** If a fence is
  still open when the file ends, the artifact is skipped with the named reason
  `UNTERMINATED_FENCE`; if an HTML comment is still open, `UNTERMINATED_COMMENT`.
  r4 specified opening and closing and said nothing about termination, and the
  unstated consequence was that every line from a stray delimiter to EOF was
  silently unscanned — which lets an artifact's own non-clean conclusion be
  swallowed while its header still asserts `CLEAN`, and defeats
  `AMBIGUOUS_VERDICT` precisely because one of the two contradicting assertions
  is never seen. The recorder must not decide which of an artifact's assertions
  it happened to read; it refuses the artifact.

A line that is not scanned carries **no** identity row and **no** verdict line.
Quoted text is not asserted text: an artifact may quote a superseded round, a
transcript, or another artifact's verdict without those bytes becoming its own
claims. This is stated explicitly because a fence-blind parser lets a quoted
`verdict: CLEAN` override the artifact's own non-clean verdict — the r3 defect.
Measured over the 444 artifacts on disk: 422 contain fenced blocks, and **0**
accepted identity rows and **0** verdict lines fall inside a fence or a
blockquote, so this guard is a zero-regression hardening (proof:
`scratchpad/w78/r4/diff_parse.py`, parse output byte-identical to r3's).

**Every change to this guard has been decided on measurement, not on taste —
including the one that reverses a previous round.** r5 measured the corpus
before widening (`scratchpad/w78/r5/measure_m1.py`): of the 444 artifacts, **0**
contain `<!--` anywhere, **0** carry an indented accepted identity row, **0**
carry an indented scanned verdict line, and **0** contain an indented fence
delimiter. Those four zeros licensed the widening as parse-neutral — but
parse-neutral on today's corpus is not the same as sound, and the r5 review
showed the indented-line half was not: it made a construct that *renders as an
assertion* unscanned, which is the laundering direction the whole guard exists
to block. r6 measured the same corpus again before narrowing
(`scratchpad/w78/r6/measure_r6.py`): the same zeros hold for the drop, and
**0** near-miss verdict lines and **0** conflicting quoted verdicts exist, which
is what licenses the two I-2 tripwires. The lesson recorded for later rounds:
**a zero-incidence measurement licenses a rule as parse-neutral; it never
licenses the premise the rule rests on.**
`UNTERMINATED_FENCE` is zero-regression on the same footing: 0 of the 444 has a
fence open at EOF, independently corroborated by the r4 round's finding that the
fence-blind r3 parser and the fence-aware r4 parser produce byte-identical output
over the whole corpus. Verified after implementing: parse output byte-identical
to r4's over all 444 (`scratchpad/w78/r5/regress_r4_r5.py`), and byte-identical
again from r5 to r6 (`scratchpad/w78/r6/regress_r5_r6.py`).

**Parsed fields — the closed list.** Exactly eleven, in this order:

```
component_id, review_type, review_round, reviewer, role,
role_binding_path, role_binding_sha256, model, effort, verdict, timestamp
```

`captured_at` is **not** in this list (it was in r2's implementation and is
removed — see "captured_at provenance" below). No other key is read; a
snake_case key that is not on this list is ignored wherever it appears, so the
`text_digest`, `source_status`, `evidence_id`, … rows that appear in the
artifacts' *reasoning* tables cannot collide with an identity field.

**Field-extraction rule — form A (two-cell Markdown table row).** A line
matching

```
^\|(?P<label>[^|]*)\|(?P<value>[^|]*)\|[ \t]*$
```

carries `field → value`, where `field` is the result of resolving `label`
through the **label alias table** below. Neither cell may contain a `|`. A label
that the alias table does not accept carries nothing — a table header (`Field`,
`Input`, `Digest`), a separator (`---`), a reasoning-table key
(`` `text_digest` (line span) ``, `Recomputed span digest`), and a
near-miss prose label that means something else (`Role binding location`, whose
value is a line range, not a path) are all silently ignored, exactly as before.

**Field-extraction rule — form A′ (three-cell role-binding row).** A line
matching

```
^\|(?P<label>[^|]*)\|(?P<path>[^|]*)\|(?P<sha256>[^|]*)\|[ \t]*$
```

whose normalized `label` is one of

```
role binding
role binding table
```

carries **two** fields: `role_binding_path` ← column 2 and
`role_binding_sha256` ← column 3. This is the only three-cell shape read; the
row `| Role binding | CONTEXT.md | 8f2795af… |` appears in the input-hash tables
of 58 of the 74 prose-cohort artifacts — **40 under the label `role binding` and
18 under `role binding table`** (r4: r3 attributed all 58 to the first label;
r3-review F-4) — always agreeing with that artifact's own two-cell rows. Every other three-cell row (`| Active goal | <path> | <sha> |`,
`| Structural validator | <path> | <sha> |`, …) carries nothing.

**Label normalization.** Before any alias lookup, a label cell is normalized by,
in this order: (1) remove **all** backtick characters, (2) strip leading and
trailing whitespace, (3) collapse every internal whitespace run to one space,
(4) case-fold. Nothing else — no stemming, no punctuation stripping, no fuzzy or
prefix matching.

**Trailing-parenthetical rule — stated explicitly.** After normalization, if the
label is not in the alias table **and** it ends with a parenthetical group
matching `\([^()]*\)`, that group and the whitespace before it are removed and
the alias table is consulted **once** more. The stripped form is accepted only
if it is itself an accepted alias. Nothing else is retried. This is what makes
`` `model` (actually invoked) ``, `` `timestamp` (UTC) ``,
`Role binding SHA-256 (at review time)`, and
`Role binding SHA-256 (CONTEXT.md bytes at review time)` all resolve, while
`` `source_hash` (whole file) ``, `` `text_digest` (line span) ``, and
`` `reviewed_inventory_sha256` (`APPROVAL`) `` resolve to nothing, because
`source_hash`, `text_digest`, and `reviewed_inventory_sha256` are not on the
closed field list.

**Label alias table — closed and enumerated.** Every string below was measured
in the 444 artifacts on disk — with **one exception, flagged in the table
itself**: the 2-cell `verdict` label is reached by 0 artifacts (r4; r3-review
F-6) (survey: `scratchpad/w78/alias-survey.txt`), and
labels are listed in their normalized form. A label not in this table is not a
field. Widening this table is a design change, not an implementation detail.

| Canonical field | Accepted labels (normalized) | Shape |
|---|---|---|
| `component_id` | `component_id`, `component id` | 2-cell |
| `review_type` | `review_type`, `review type` | 2-cell |
| `review_round` | `review_round`, `review round`, `round` | 2-cell |
| `reviewer` | `reviewer`, `reviewer identity / session` | 2-cell |
| `role` | `role` | 2-cell |
| `role_binding_path` | `role_binding_path`, `role binding path` | 2-cell; also column 2 of form A′ |
| `role_binding_sha256` | `role_binding_sha256`, `role binding sha-256`, `role binding sha-256 at review time` | 2-cell; also column 3 of form A′ |
| `model` | `model`, `model actually invoked` | 2-cell |
| `effort` | `effort`, `effort actually invoked` | 2-cell |
| `verdict` | `verdict` | 2-cell — **unexercised: 0 of the 444 artifacts carry the verdict this way; the verdict line is the only carrier in practice** (r4; r3-review F-6). Retained, not dropped: keeping it means a hand-written artifact that tabulates its verdict is still read rather than silently missing a field. |
| `timestamp` | `timestamp`, `review timestamp`, `review utc`, `review utc timestamp` | 2-cell |

The implementation is `ARTIFACT_LABEL_ALIASES` /
`ARTIFACT_ROLE_BINDING_ROW3_LABELS` in
`scripts/equity_os_blueprint/record_inventory_review.py`, which must stay
literally equal to this table.

`review timestamp` is reachable only via the trailing-parenthetical rule
(`Review timestamp (UTC)`); it is listed because the rule consults this table
with the stripped label.

**Nothing is inferred from the path.** No field is ever taken from the file name
or the containing directory. `component_id`, `review_type`, and `review_round`
must be present in the artifact **body** or the artifact is skipped. The
recorder then cross-checks the parsed values against the path
(`…/inventory/<CID>/<REVIEW_TYPE>-r<N>.md`) and aborts on a mismatch — the path
is a check on the body, never a source for it. A path/body disagreement aborts
under its own reason token, `PATH_BODY_MISMATCH` for `component_id` and
`review_type` and `ROUND_FILENAME_MISMATCH` for the round (r5, r4-review M-5).

**Check precedence — contract, because the reason token is the triage surface
(r5, r4-review M-5).** After the artifact parses, the recorder applies its
checks in this order, and the **first** failure names the abort:

0. manifest-side path shape, **before the artifact is read at all** —
   `MANIFEST_BAD_ARTIFACT_PATH`, `ARTIFACT_NOT_REGULAR_FILE` (r6, r5-review M-3)
1. path/body cross-check — `PATH_BODY_MISMATCH`, `ROUND_FILENAME_MISMATCH`
2. verdict recordability — `NOT_CLEAN`
3. role binding — `ROLE_MISMATCH`
4. timestamp shape and futurity — `FUTURE_TIMESTAMP`
5. **manifest agreement — `MANIFEST_DISAGREEMENT`, last**

r4 ran step 5 first, so whenever the manifest was truthful — the normal case —
every failure in steps 1–4 was reported as `MANIFEST_DISAGREEMENT`, and the
dedicated branches were unreachable. The token then misdescribed what disagreed,
which matters across an 18-batch, 447-review program where triage is meant to be
mechanical. Putting the manifest comparison last means `MANIFEST_DISAGREEMENT`
fires only for an artifact that is otherwise path-consistent, `CLEAN`,
`REVIEWER`-bound and non-future — i.e. only when the disagreement really is
manifest-versus-artifact. **The set of accepted artifacts is unchanged by this
ordering**; only the name a rejection carries changes.

**Field-extraction rule — form B (bare line).** A line matching

```
^(?P<key>[a-z0-9_]+):[ \t]*(?P<value>\S.*?)[ \t]*$
```

carries `key → value`. This is r2's original rule, retained unchanged so that
artifacts written in the bare form remain readable.

**Value normalization.** In **all three forms** — A's single value cell, **A′'s
two value cells (the path in column 2 and the SHA-256 in column 3)**, and B's
value — in this order (r4: r3 said "in both forms", which left A′ unspecified
and made the prose parse 58 artifacts differently from the code; r3-review F-2):

1. Strip leading/trailing whitespace.
2. If the whole value is wrapped in exactly one backtick pair and the inside
   contains no backtick and is not blank, remove that pair. A value that merely
   *contains* a backticked span — e.g.
   `` Reviewer-role subagent, session `47c148f8-…` `` — is kept byte-for-byte.
3. **Empty value (r4, r3-review F-7).** If the normalized value is the empty
   string, the row carries **nothing** — it is treated exactly as if the row
   were absent, and contributes neither a value nor an `AMBIGUOUS_FIELD`. Form
   A's `[^|]*` cell admits `| Model actually invoked |  |`; such a row does not
   make the field present. If that leaves the field with no accepted row at all,
   the outcome is `MISSING_FIELD`, which is the intended reading: a blank cell
   states nothing. Measured over the 444: **0 divergences either way** — no
   artifact has an empty accepted cell today.
4. For `review_round` only: the value must match `^r?(\d+)$` and normalizes to
   the digits (`r0` → `0`). Any other shape is a hard abort, not a skip: it
   means the artifact disagrees with its own filename convention. The recorder
   then requires the normalized value to equal the round in the filename
   `<REVIEW_TYPE>-r<N>.md`.

**The verdict line (widened in r4; r3-review F-1).** A **scanned** line matching

```
^[ \t]*(?:\*\*)?[ \t]*[Vv][Ee][Rr][Dd][Ii][Cc][Tt][ \t]*:[ \t]*(?P<verdict>[A-Za-z0-9_]+)(?:[ \t]+(?:—|-)[ \t]+\S.*?)?[ \t]*(?:\*\*)?[ \t]*$
```

sets `verdict`. In words: optional bold, the word `verdict` (case-insensitive),
a colon, a bare **TOKEN**, and — optionally — a separator of whitespace + an em
dash `—` or a hyphen `-` + whitespace, followed by a non-empty remainder. **The
TOKEN is the verdict**; the remainder is human prose and is discarded. So
`**verdict: CLEAN**`, `**Verdict: CLEAN**`, `verdict: CLEAN`,
`**Verdict: ISSUES_FOUND — 1 Critical, 0 Important, 0 Minor**` and
`Verdict: BLOCKED - 2 Critical` are all verdict lines. The **value is taken
exact-case** and is never case-folded — `CLEAN` is the only recordable value and
`Clean` is not it. A verdict line takes precedence over form A/B on the same
line. Lines inside fenced blocks, blockquotes or HTML comments are not scanned
and are therefore not verdict lines, however they are written — but a **scanned**
line that announces a verdict without matching this regex to end of line is
`MALFORMED_VERDICT_LINE`, and a blockquoted or commented-out line carrying a
verdict token that contradicts the accepted one is `CONFLICTING_QUOTED_VERDICT`
(r6, r5-review I-2).

**The verdict rule — exactly one verdict, per artifact.** The verdict is the
single field the whole gate turns on, so it carries its own two named reasons
rather than folding into the generic field reasons. The recorder collects the
verdict values from **all** carriers outside fences and blockquotes (verdict
lines, plus the 2-cell `verdict` row if present) and requires:

| Verdict carriers | Distinct values | Outcome |
|---:|---:|---|
| 0 | — | skip, reason `MISSING_VERDICT` |
| ≥ 1 | 1 | **accept** that value — unless a blockquote or HTML comment carries a different token, which is `CONFLICTING_QUOTED_VERDICT` (r6) |
| ≥ 2 | ≥ 2 | skip, reason `AMBIGUOUS_VERDICT` |

A scanned near-miss (`MALFORMED_VERDICT_LINE`) aborts before this table is
reached: an artifact that announces a verdict the recorder cannot read is not
counted as having stated none.

The rule is keyed on **distinct values**, not on the number of lines, and §0.0b
records why: every one of the 444 artifacts states its verdict twice — once in
the header, once in the conclusion — always with the same token. Two agreeing
assertions are the house format and assert nothing contradictory; **two
disagreeing assertions are a hard skip**, no precedence, no last-one-wins. An
artifact that says both `CLEAN` and `ISSUES_FOUND` in its own voice is not
evidence of either.

**Exactly one accepted row per field per artifact.** For each of the eleven
fields, the recorder collects the set of normalized values carried by **all**
accepted rows and lines (any label, any shape) and then requires:

| Accepted rows for the field | Distinct normalized values | Outcome |
|---:|---:|---|
| 0 | — | skip, reason `MISSING_FIELD` |
| ≥ 1 | 1 | **accept** that value |
| ≥ 2 | ≥ 2 | skip, reason `AMBIGUOUS_FIELD` |

So two rows carrying the **same** value are fine — real artifacts state
`**verdict: CLEAN**` in both the header and the conclusion, and 58 of the 74
prose-cohort artifacts state the role-binding SHA-256 twice (a two-cell identity
row and the three-cell input-hash row), always identically. Two rows carrying
**different** values is a hard abort for the whole batch — never a "last one
wins", never a default. An artifact that contradicts itself about its own
identity is not evidence of anything. Measured over all 444 artifacts, with the
scope of each figure stated (r4; r3-review F-5): **116** (artifact, field) pairs
have two accepted rows **excluding** the verdict line — that is exactly 58 × 2,
the A′ role-binding duplications — and **560** **including** the header /
conclusion verdict duplication that this paragraph cites as its first example.
**0** disagree under either scope.

The verdict field is additionally governed by the verdict rule above; where the
two overlap they agree, since both key on the set of distinct values.

**Named skip reasons.** An artifact that does not satisfy the contract is
skipped with the named reason below. A skipped artifact's `(component, review
type)` is dropped from the batch and its review object **stays `PENDING`** per
§5.4; because §3.4 requires a row to be completed all-at-once, dropping one
review type drops that whole component from the batch. Nothing is written for
it, nothing is defaulted, and the artifact on disk is left untouched.

| Reason | Condition |
|---|---|
| `MISSING_FIELD` | one or more of the eleven fields (other than `verdict`) has no accepted row after forms A, A′ and B are applied. *(The recorder also carries a whitespace-only check on `reviewer` / `model` / `effort` under this token. It is **unreachable by construction** and is disclosed rather than dropped (r5, r4-review M-4): every accepted value is stripped, form B's regex requires `\S` at the start, and value-normalization rule 3 makes a value that normalizes to empty carry nothing at all — so no parsed value can be whitespace-only. It is retained as a defensive assertion, on the same footing as the unexercised 2-cell `verdict` alias.)* |
| `AMBIGUOUS_FIELD` | a field (other than `verdict`) has two or more accepted rows carrying different normalized values |
| `MISSING_VERDICT` | **(r4)** no verdict carrier among the scanned lines — no verdict line and no 2-cell `verdict` row outside fences, blockquotes and HTML comments |
| `AMBIGUOUS_VERDICT` | **(r4)** two or more verdict carriers stating different verdicts. **(r6)** Indented lines count again, so an indented conclusion contradicting the header lands here rather than being skipped |
| `MALFORMED_VERDICT_LINE` | **(r6, r5-review I-2)** a **scanned** line matches `^[ \t]*(?:\*\*)?[ \t]*[Vv][Ee][Rr][Dd][Ii][Cc][Tt][ \t]*:` but is not a valid verdict carrier — it announces a verdict the recorder cannot read, and is refused rather than read past |
| `CONFLICTING_QUOTED_VERDICT` | **(r6, r5-review I-2)** a **skipped** blockquote or HTML-comment line carries a verdict token different from the accepted verdict. Fenced blocks are exempt: §2.2 licenses a fence as the device for quoting a superseded round |
| `UNTERMINATED_FENCE` | **(r5, r4-review I-1)** a fenced block is still open when the file ends, so every line from the stray delimiter to EOF was unscanned. Refused rather than parsed from whatever happened to precede it |
| `UNTERMINATED_COMMENT` | **(r5)** an HTML comment is still open when the file ends — the same failure for the construct M-1 added |
| `MALFORMED_REVIEW_ROUND` | `review_round` matches neither `r<N>` nor `<N>` |
| `ROUND_FILENAME_MISMATCH` | normalized `review_round` ≠ the round in the filename |
| `PATH_BODY_MISMATCH` | **(r5, r4-review M-5)** the body's `component_id` ≠ the containing directory, or the body's `review_type` ≠ the filename |
| `NOT_CLEAN` | `verdict` is present but ≠ `CLEAN` (§5.4: not recordable, stays `PENDING`) |
| `ROLE_MISMATCH` | `role` ≠ `REVIEWER`, or `role_binding_path` ≠ `CONTEXT.md`, or `role_binding_sha256` is not lowercase 64-hex |
| `FUTURE_TIMESTAMP` | `timestamp` is not UTC RFC3339 `…Z`, or is after `now` |
| `MANIFEST_DISAGREEMENT` | a parsed field ≠ the manifest's value for that field. Reached **last** (see the precedence list above), so it never stands in for one of the reasons above |
| `MANIFEST_UNKNOWN_KEY` | **(r5, r4-review M-2)** the manifest carries a key outside §3.2's closed sets — e.g. a stale r2-shaped entry declaring `captured_at`, which §2.2.1 derives and no manifest may supply |
| `MANIFEST_BAD_ARTIFACT_PATH` | **(r6, r5-review M-3)** the manifest's `artifact_path` is not repo-relative, is not under `…/inventory/<COMPONENT_ID>/`, or is not named `<REVIEW_TYPE>-r<N>.md`. An operator error in the manifest, named like every other |
| `ARTIFACT_NOT_REGULAR_FILE` | **(r6, r5-review M-3)** the manifest's `artifact_path` resolves to a symlink or other non-regular file. `os.lstat` is used, so a symlink is never followed |

In the current recorder every one of these is surfaced as a `RecorderAbort`
whose message names the file **and the reason token verbatim**, which aborts the
batch. This is a real property as of r4, not an aspiration: r3 named only
`MISSING_FIELD`, `AMBIGUOUS_FIELD` and `MALFORMED_REVIEW_ROUND`, and the other
five aborted with descriptive prose only (r3-review F-3). All eighteen tokens
above now appear literally in the abort text, so triage across an 18-batch,
447-review program is mechanical — including, since r6, the four manifest-side
path failures that r5 reported with prose only (r5-review M-3). That is deliberate: a
batch is assembled by an operator who has already decided which reviews are
recordable, so an unrecordable entry in the manifest is an operator error, not
a routine filter. The manifest — not the parser — is where a component is
excluded from a batch.

**`captured_at` provenance — the decision.**

> The recorder sets the `EV-<CID>-INVREV-<TYPE>` evidence object's
> `captured_at` **equal to that artifact's own review `timestamp`**.

**And that is now the implemented expression, not merely an equal one (r5,
r4-review M-3).** r4 computed `captured_at` from the parsed artifact value in
`validate_batch_entry` and then discarded it: `run_batch` dropped the return
value and `build_candidate` wrote the **manifest's** `timestamp` instead. The two
were always equal — the `MANIFEST_DISAGREEMENT` check enforces
`manifest.timestamp == parsed.timestamp` — so there was no behavioural defect,
but the stated provenance and the implemented provenance were different
expressions joined by a third invariant, and the parsed value was dead code. r5
threads the parsed value through to the write, so the sentence above describes
the code path rather than a coincidence. Behaviour is unchanged, and the proof is
that both dry-run batches produce bit-identical `candidate_sha256` values before
and after the change.

Rationale, and the two alternatives rejected:

- **Why the review timestamp.** `captured_at` means "when these evidence bytes
  were captured". The verdict artifact's bytes are final at the moment the
  reviewer finishes the review and states the timestamp; there is no separate
  later capture event. The structural validator requires
  `review.timestamp >= evidence.captured_at` for every linked evidence ref —
  `assert all(timestamp >= parse_utc_rfc3339(evidence_by_id[ref_id]["captured_at"]) for ref_id in review["evidence_ref_ids"])`,
  `validate_ledger_structural.py:346-349` — i.e. **`>=`, so equality is
  accepted**. It also requires `captured_at <= validation_now` (`:219`), which
  holds because the recorder independently rejects a future `timestamp`.
- **Why not the file mtime.** Not durable: mtime is set by whichever `git
  checkout`, clone, or copy last materialised the file, so the same evidence
  would carry a different `captured_at` in every working tree. A ledger field
  must be reproducible from the repository's content, not from its filesystem
  metadata.
- **Why not "now" at recording time.** Recording happens strictly after the
  review, so `now > timestamp`, which violates `:346-349` and fails the
  structural gate. It is also semantically wrong: it would date the evidence to
  when the *tool* ran, not when the *review* happened.

Because `captured_at` is derived, it is **not** a manifest field either (§3.2).
Deriving it in one place removes the possibility of an artifact, a manifest,
and a ledger row disagreeing about it.

**Artifacts that do not satisfy this contract.** Measured over the 444
artifacts present at r4: **all 444 satisfy it** (370 under the
snake_case labels alone, the remaining 74 through the alias table). Every one
of the 444 was additionally cross-checked: parsed `component_id`,
`review_type`, and `review_round` agree with the path for all 444, `role` is
`REVIEWER`, `role_binding_path` is `CONTEXT.md`, `role_binding_sha256` is
lowercase 64-hex, `timestamp` is UTC RFC3339 `…Z`, and `reviewer` / `model` /
`effort` are nonempty — 0 problems
(`scratchpad/w78/parse-crosscheck.txt`). 424 carry `CLEAN`; the 20 carrying
`ISSUES_FOUND` parse fine and are correctly refused as unrecordable by §5.4,
not by the parser. No artifact under `docs/goals/reviews/ledger/inventory/` was
edited, reformatted, or regenerated in this amendment.

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

**Manifest schema `inventory-review-batch/v1` (r3).** Top level:
`schema`, `batch_id`, `ledger_prehash_sha256`, `baseline_dirty_paths`,
`reviews`. Each `reviews[]` entry carries exactly these required keys:

```
component_id, review_type, artifact_path, artifact_sha256,
reviewer, model, effort, role, role_binding_path, role_binding_sha256,
review_round, verdict, timestamp
```

— that is, `artifact_path` and `artifact_sha256` plus the eleven §2.2.1 parsed
fields. **`captured_at` is no longer a manifest field** (r2's implementation
required it): §2.2.1 derives the evidence object's `captured_at` from the
artifact's parsed `timestamp`. `review_round` is the normalized digits (`"0"`,
not `"r0"`), matching §2.2.1's normalization. Every one of the eleven parsed
fields must equal the artifact's parsed value byte-for-byte, or the batch aborts
with `MANIFEST_DISAGREEMENT`.

**"Exactly these keys" is enforced in both directions (r5, r4-review M-2).**
Both key sets above are **closed**: a top-level or per-entry key outside them
aborts the batch with the named reason `MANIFEST_UNKNOWN_KEY`. r4 checked
presence only, so a stale r2-shaped entry still declaring `captured_at` was
accepted and its declared value silently ignored — fail-safe, because the derived
value wins, but a stale manifest must be refused by name exactly as the rehearsal
proof's superseded `/v1` schema is (§3.10 assert 1). An operator who needs a new
manifest field changes §3.2 and this list; the recorder does not accept one
quietly.

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

### 3.6 The `DISP-R-1` carve-out — mandatory, counter-intuitive, and now two-state

**Rewritten in r6 (r5-review I-3).** r0–r5 cited the pre-HR-0005 validator, which
pinned `DISP-R-1`'s no-implementation requirement as a single frozen object and
asserted exactly one admissible outcome. HR-0005 (commit `501f3e7`, "DISP-R-1
unpinned") replaced that with a **two-state** rule, and this section states both
states and which one the recorder is built for.

`DISP-R-1` is the one `REJECTED_ACCOUNTED` canonical row. The post-HR-0005
structural validator pins the requirement's **identity** — every field except
the two it allows to move — and then branches on its `status`
(`validate_ledger_structural.py:2675-2686` `EXPECTED_DISP_R1_REQUIREMENT_IDENTITY`,
`:2686` `DISP_R1_MUTABLE_FIELDS = {"status", "evidence_ref_ids"}  # move only
together`, and the assertion block at `:2759-2768`):

```python
disp_r1_requirement = next(item for item in disp_r1["required_evidence"]
                           if item["evidence_id"] == "REQ-DISP-R-1-NO-IMPLEMENTATION")
assert {k: v for k, v in disp_r1_requirement.items()
        if k not in DISP_R1_MUTABLE_FIELDS} == EXPECTED_DISP_R1_REQUIREMENT_IDENTITY
disp_r1_proven, disp_r1_reasons = current_no_implementation_proof(disp_r1)
if disp_r1_requirement["status"] == "UNRESOLVED":
    assert disp_r1_proven is False and {"REQUIREMENT_UNRESOLVED",
        "CURRENT_REVIEWER_ROLE_EVIDENCE_REVIEW_MISSING"} <= set(disp_r1_reasons)
    assert any(item["requirement_id"] == "REQ-DISP-R-1-NO-IMPLEMENTATION"
               for item in disp_r1_unmet)
else:
    assert disp_r1_requirement["status"] == "SATISFIED" and disp_r1_proven is True ...
```

**State 1 — `UNRESOLVED`. This is the live state, and the one the recorder is
built for.** Verified against the canonical ledger this round:
`REQ-DISP-R-1-NO-IMPLEMENTATION` carries `status: "UNRESOLVED"` and
`evidence_ref_ids: []`, and `DISP-R-1`'s `evidence_inventory_review` is
`PENDING`. While that holds, the validator requires the proof to stay
**explicitly unproven**, and two consequences bind the recorder:

1. `REQ-DISP-R-1-NO-IMPLEMENTATION` must remain `status=UNRESOLVED` with
   `evidence_ref_ids=[]`. **Verified** (§6.3, probe B): satisfying it — the
   obvious way to clear the last preimplementation blocker — fails structural
   validation, exit `1`. The recorder never touches `required_evidence` on any
   row, so it cannot reach this field at all.
2. `DISP-R-1`'s `EVIDENCE` review must **not** link `EV-DISP-R-1-SPEC-DRAFT`.
   `current_no_implementation_proof` computes `review_ok` partly as
   `set(historical) <= set(review["evidence_ref_ids"])`
   (`validate_ledger_structural.py:2719`). Linking the historical ref alongside
   a `COMPLETE`, CLEAN, digest-current review would set `review_ok = True`,
   removing `CURRENT_REVIEWER_ROLE_EVIDENCE_REVIEW_MISSING` from the reason
   codes and failing the `UNRESOLVED` branch's assertion.

The recorder therefore hard-codes, **exactly as written since r0**: `DISP-R-1`'s
`EVIDENCE` review links **only** `EV-DISP-R-1-INVREV-EVIDENCE`
(`build_candidate`, with an `assert` that the historical ref is absent).

**State 2 — `SATISFIED`. The recorder refuses the row.** If a later amendment
moves the requirement to `SATISFIED` — moving `status` and `evidence_ref_ids`
together, as `DISP_R1_MUTABLE_FIELDS` requires — the validator's `else` branch
demands `disp_r1_proven is True` with **no** reason codes, which via the
`review_ok` expression above requires `DISP-R-1`'s `EVIDENCE` inventory review
to link `EV-DISP-R-1-SPEC-DRAFT`: precisely the link consequence 2 forbids. The
carve-out and the post-state are then mutually exclusive, and a recorder that
kept its carve-out would write a row that fails structural validation.

**The rule, therefore:** the recorder reads
`REQ-DISP-R-1-NO-IMPLEMENTATION.status` from the live ledger before building any
candidate containing `DISP-R-1`. While it is `UNRESOLVED` the carve-out applies
unchanged. If it is `SATISFIED`, the recorder **refuses** the `DISP-R-1` row with
the named reason `DISP_R1_RESERVED_FOR_T2` and records nothing for it — because
in that state re-sealing all three `DISP-R-1` reviews with the correct evidence
links is **T2's** responsibility, not this tool's (DISP-R-1 amendment design r3
§8.3). This is a fail-closed refusal by construction: batching `DISP-R-1`
belongs to whichever workstream owns the state it is in, and the two must not
both write it.

Consequence for the gate while state 1 holds: see §3.9.

### 3.7 Ledger serialization — byte-exact writer contract

Verified by round-trip: re-serializing all 213 parsed rows with

```python
json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"
```

reproduces the canonical ledger **byte for byte** (verified in the r1 round at
the then-canonical `de236d7e…`; the same three settings reproduce the live
post-HR-0005 ledger `e52ed95c…`, matching §1.1, which every `--dry-run`'s
`structural_candidate_exit: 0` re-demonstrates). `sort_keys=True` with default separators does **not**
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

**This blocker is unclearable by any ledger edit *this tool can make***, because
while `REQ-DISP-R-1-NO-IMPLEMENTATION` is `UNRESOLVED` the post-HR-0005
`validate_ledger_structural.py:2763-2765` asserts the proof must remain
unproven, and this tool never writes `required_evidence`. **Restated in r6
(r5-review I-3):** HR-0005 already performed the goal amendment this paragraph
anticipated, so clearing the blocker no longer requires changing the validator —
it requires moving the requirement to `SATISFIED` together with its
`evidence_ref_ids` and re-sealing `DISP-R-1`'s three reviews, which is T2's
transaction (§3.6 state 2). Either way it is an
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
against the canonical tree, and every replica it creates is deleted after the
proof is written. A leg that leaves its replica unusable gets a fresh one —
which in practice means L5 *(r2, r1-review Minor 4)*, since it deliberately
wedges the tool. The rehearsal batch is a real batch definition (batch 1's
rows) with synthetic verdict artifacts inside the replica.

**Five named legs, all required.** *(r2, r1-review Minor 4: r1 had four legs,
none of which exercised the `RECOVERY_REQUIRED` state r1 itself added in
response to r0-review M-9c. L5 closes that.)*

| Leg | Injection | Required outcome |
|---|---|---|
| **L1 — forward baseline** | none | Batch commits: journal `COMMITTED`, replica ledger posthash equals the prepared candidate hash, structural `0`, preimplementation pending shrinks by exactly `\|R(B)\|`, no temp file survives, lock released |
| **L2 — forced-failure rollback** | fault injected **after** the rename and **before** `COMMITTED` (a post-verify hook forced to raise) | Journal `ROLLED_BACK`; replica ledger bytes **and** mode identical to preimage; no temp file survives; exit nonzero; lock released |
| **L3 — `SIGINT` during replacement** | `SIGINT` delivered inside the replacement block | Same as L2, and the process re-raises `KeyboardInterrupt` after rollback completes |
| **L4 — `SIGTERM` during replacement** | `SIGTERM` delivered inside the replacement block | Same as L2, via the `SIGTERM` handler routing into the identical rollback path |
| **L5 — unprovable rollback → `RECOVERY_REQUIRED`** | the preimage is **corrupted or removed** after the rename and before the forced rollback, so step 9 cannot prove the restored bytes | Journal `RECOVERY_REQUIRED` carrying the **full step-10 unproven-path payload** — the unproven path, expected and observed SHA-256, expected and observed mode, the surviving preimage and temp paths, and the batch's component/review-type list; exit nonzero; lock released; and **a second recorder invocation in the same replica is refused at step 1**, naming that journal, without performing any write |

L1 exists so that L2–L5's "did not silently commit" is distinguishable from
"never wrote anything": the rehearsal must first demonstrate that the same code
path *does* mutate the replica.

L5 runs **last and on its own fresh replica**, because it deliberately leaves
that replica wedged — the wedging is the property under test. Two consequences
follow from step 10's design and must not be mistaken for L5 failures: the
replica's ledger is *not* required to match the preimage (step 9 could not
prove it — that is the injected condition), and **the recorder makes no claim
about which working files survive**, so `temp_files_surviving` is simply not
asserted for L5. **Corrected in r6 (r5-review M-2):** r2–r5 said those files are
"required to survive, because step 10 preserves them for the operator", which
the rehearsal's own evidence contradicts — every L5 run records
`temp_files_surviving: 0`. Reading the code, 0 is the honest outcome: the staged
temp file is consumed by the forward `os.replace` at step 7, and the preimage is
consumed by step 9's restoring rename before step 10 is ever reached. What step
10 does preserve is the **record**: the journal's unproven-path payload, which
r6 widens with `preimage_sha256_before_restore` — the preimage's digest read
**before** the restoring rename, the fix for r5's second M-2 half — and
`surviving_preimage_exists`, so an operator can tell a corrupted preimage from a
removed one even though `surviving_preimage_path` may name a file that is gone.
The `temp_files_surviving == 0` **assertion** therefore applies to L1–L4 only,
where it is a real property.

**Machine-checkable proof object.** Written once, by the rehearsal harness, and
asserted by the recorder:

```json
{
  "schema": "inventory-review-rollback-rehearsal/v2",
  "recorder_sha256": "<sha256 of record_inventory_review.py as rehearsed>",
  "structural_validator_sha256": "77faeaf3…",
  "preimplementation_validator_sha256": "f7a225a1…",
  "replica_ledger_prestate_sha256": "e52ed95c…",
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
      "lock_released": true},
    "L5_recovery_required": {"passed": true, "journal_state": "RECOVERY_REQUIRED",
      "unproven_path": "<canonical ledger path inside the replica>",
      "expected_sha256": "<preimage digest>", "observed_sha256": "<observed>",
      "expected_mode": "<preimage mode>", "observed_mode": "<observed>",
      "surviving_paths_recorded_in_journal": true,
      "exit_code": 1, "second_invocation_refused_at_step_1": true,
      "lock_released": true}
  },
  "transcript_path": "scratchpad/inventory-reviews/rehearsal/transcript.txt",
  "transcript_sha256": "<sha256 of that transcript>"
}
```

**What the recorder asserts at step 2** — all of it, or abort:

1. The file exists, parses, and
   `schema == "inventory-review-rollback-rehearsal/v2"`. *(r2: bumped from
   `/v1`. The object's shape changed in this round — five legs instead of four,
   and `ledger_prestate_sha256` renamed — so a `/v1` proof must be rejected by
   name rather than limped through the remaining asserts.)*
2. All **five** legs present, each `"passed": true`, with the exact
   `journal_state` shown above. `temp_files_surviving == 0` on **L1–L4**; L5 is
   exempt by construction (step 10 preserves those files) and instead requires
   `surviving_paths_recorded_in_journal == true`.
3. L2/L3/L4 each carry `bytes_match_preimage` **and** `mode_match_preimage`
   true — mode alone or bytes alone is a failed rehearsal.
4. **L5** carries `journal_state == "RECOVERY_REQUIRED"`, a nonempty
   `unproven_path`, all four of `expected_sha256` / `observed_sha256` /
   `expected_mode` / `observed_mode` present as keys, with `observed_sha256`
   **not** equal to `expected_sha256` — a removed preimage is recorded as
   `observed_sha256: null` and `observed_mode: null`, which is a valid L5
   outcome and satisfies that inequality — `exit_code != 0`, and
   `second_invocation_refused_at_step_1 == true`. *(r2, r1-review Minor 4.)* An
   L5 that committed, that rolled back cleanly, or that exited zero is a
   **failed** rehearsal: the branch being rehearsed is precisely the one that
   fires when the rollback cannot be proven, and a rehearsal that never reached
   it has not exercised it.
5. `recorder_sha256` equals the SHA-256 of the recorder **about to run**. Any
   edit to the recorder — including a one-line fix between batches —
   **invalidates the rehearsal and requires a fresh one.** This is the clause
   that keeps the rehearsal honest across an 18-batch program.
6. **Validator pin.** `structural_validator_sha256` and
   `preimplementation_validator_sha256` each equal the corresponding §1.1 value
   **and** equal the SHA-256 of that validator script as it exists at this
   invocation. Either validator changing invalidates the rehearsal, because the
   digest contract it rehearsed against may have changed. Both are fixed
   constants for the life of the program; this assert cannot drift across
   batches.
7. **Rehearsal ledger pre-state — the replica's own starting bytes, never the
   live ledger.** *(r2, r1-review Minor 3, load-bearing. r1 folded this into
   assert 5 as "the three pinned hashes equal §1.1", glossed as "a validator or
   ledger-pre-state change invalidates the rehearsal", which could be read as a
   comparison against the live canonical ledger — a reading that would abort
   every batch from 2 onward, since batch 1's commit necessarily changes the
   live ledger. r1's field name `ledger_prestate_sha256` invited that reading
   and is renamed here to `replica_ledger_prestate_sha256`.)*
   `replica_ledger_prestate_sha256` records the SHA-256 of the ledger **inside
   the disposable replica, at the moment that rehearsal began**. The recorder
   asserts exactly three things about it, and nothing else: that it is
   lowercase 64-hex; that it equals the pre-state digest recorded in the
   rehearsal transcript; and that it equals the §1.1 ledger digest
   `e52ed95c842a5546d1ae04108c06f4a38f49dd9a846d94bdbe8f612f38947c49` (r6: the
   post-HR-0005 value; r0–r5 pinned `de236d7e…`), which is
   the state the replica is built at by construction (see **Where** above).
   **The live canonical ledger is not read by this assert, at batch 1 or at any
   later batch.** All three compared quantities are constants captured before
   the first real write and unchanged by any commit, so this assert evaluates
   identically for all 18 batches and can abort none of them.

   The live ledger has its own, separate, per-batch check, unchanged from r1:
   §3.8 step 2's "Ledger prehash equals the recorded prehash", which compares
   the live canonical file against **that batch's** recorded prehash. The two
   checks answer different questions — assert 7 asks "was this rehearsal run
   against the state this program starts from?", step 2 asks "is the live
   ledger the file this batch was prepared against?" — and neither is a
   substitute for the other.
8. `transcript_sha256` matches the transcript's current bytes, and the
   transcript is a regular file.

The rehearsal transcript and proof object are part of this workstream's
evidence bundle. They are **not** ledger evidence objects: they live under
gitignored `scratchpad/` and are never linked from `evidence_refs`, so §2.2's
durable-path rule is untouched.

**What this gate is, and is not.** *(r2, r1-review Minor 5.)* The rehearsal
gate is an **operator-discipline control over a gitignored workstream evidence
artifact — not an enforcement boundary, and not ledger evidence**: the recorder
reads a `scratchpad/` file it cannot authenticate, so a hand-written proof
object would pass, and no validator, gate, ledger record, or contract
obligation depends on the gate existing. Its hash bindings (asserts 5–8) defend
against the realistic failure — a stale proof silently outliving a recorder or
validator edit — not against deliberate forgery, and a later reader must not
credit it as more than that.

**Status (rewritten in r5, r4-review I-2; re-measured in full in r6 after the
HR-0005 re-pin, r5-review I-3 — every digest in the r5 table named a state that
no longer exists).** As of r6, all of the following are true and were measured
this round:

| Fact | Value |
|---|---|
| Recorder | `scripts/equity_os_blueprint/record_inventory_review.py` exists, SHA-256 `94c65444cda07978ecef4ec7b6a241e4dab2f62677795bdfc0c718a821423341` (untracked; the r5 bytes were `8d0410cd…`, the r4 bytes `32947a02…`) |
| Rehearsal | **performed, again this round** — the I-3 re-pin changed the recorder's bytes and therefore invalidated r5's proof — on five fresh full-tree replicas at the post-HR-0005 pre-state `e52ed95c…`: **5/5 legs pass** (`scratchpad/w78/r6/rehearsal-r6.log`) |
| Proof object | `scratchpad/inventory-reviews/rehearsal/proof.json`, SHA-256 `437f7492f8fa357b78b70fb47e55e31fe328ff4d94457a24097a1c943702fe1c`, schema `inventory-review-rollback-rehearsal/v2` (r5's proof `b075280c…` is superseded; a copy is kept at `scratchpad/w78/r6/proof-before-r6.json`) |
| Recorder binding | the proof's `recorder_sha256` is `94c65444…` — **equal to the live recorder's bytes**, i.e. the proof is bound to the tool that would perform the write |
| Transcript | `scratchpad/inventory-reviews/rehearsal/transcript.txt`, SHA-256 `75c61cb73aab8694bff704e7519b2fc74c74daa440e6135288557b1d8c6e6cc6`, equal to the proof's `transcript_sha256` |
| §3.8 executed | twice this round under `--dry-run` **against the live post-HR-0005 ledger `e52ed95c…`**, both exit **0**: `batch-01-authority_clause` (12 reviews, pending 447 → 435, `stale_after` 0, `structural_candidate_exit` 0, `preimpl_exit` 2, `candidate_sha256` `52debc487066fe87819a05389a797b8a3046379ef9e7ee9b9b92c8433dd47572`) and `batch-doc-document_strategy_clause` (18 reviews, 447 → 429, `stale_after` 0, `candidate_sha256` `63e86747bc6359b6cb6b10e32a0f60a3bb511ac27e1bf560368f0a25ddb6fdac`); `committed: false` for both, canonical ledger `e52ed95c…` unchanged after both runs |

The gate demonstrably works in the direction that matters, and r6 is its second
independent demonstration. In r5 the first `--dry-run` after the recorder edits
refused at **assert 5** (`the recorder changed since the rehearsal`). In this
round the r5 package's own dry-runs refused at **assert 6** the moment HR-0005
moved the structural validator — the r5 reviewer reproduced exactly that, exit 1
on both batches — and clearing it required re-pinning the recorder, which
invalidated the rehearsal under assert 5, which required a fresh rehearsal. Both
asserts fired for real, in the correct order, on a change nobody in this
workstream made. Any further edit to the recorder or to the §1.1 pinned bytes
invalidates this proof again, by design.

**No real (non-dry-run) batch has been executed against the canonical ledger.**
The only non-dry-run recorder invocations in this round's evidence are the five
rehearsal legs, each inside its own disposable replica, deleted afterwards. The
rehearsal remains a hard precondition on the first real write, and it is now
satisfied for this recorder's exact bytes — not for any later ones.

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
`SCOPE` rule is fixed by kind (goal **L235-245**, the kind→rule mapping table —
*r2, r1-review Minor 2: r1 cited L~262-278 here, which is
`ACTIVE_NEGATIVE_CONTROL` plus the `semantic_review` paragraph, not the mapping
table*): `PROGRAM_WIDE_ACTIVE_CONTROL`
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
asserted for every `COMPLETE` review (`validate_ledger_structural.py:342`), and
a `PENDING` review must have `verdict=null` (`:332-338`, the null assertion
itself at `:337`). There is no schema slot for a negative verdict. *(r2,
r1-review Minor 2: r1 cited `:337` for the `CLEAN` rule and `:329-336` for the
`PENDING` branch; both re-read this round — `:337` is
`assert review[field] is None` inside the `PENDING` branch, which begins at
`:332`, and the `CLEAN` rule is `:342`.)*

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
here instead.)*

**r6 re-verification after HR-0005 (r5-review I-3).** Probes A–H were executed
against the **pre**-HR-0005 §1.1 bytes and are not re-executed here; what r6
re-executed against the live post-HR-0005 tree is the state every one of them
depends on, and the three probes whose results the design cites as current:

| Re-executed in r6 | Result |
|---|---|
| All seven §1.1 hashes | recomputed at the start and end of the round; the four moved values are pinned in §1.1 |
| `validate_ledger_structural.py --repo-root .` | exit **0** on the live tree, before and after this round's edits |
| `DISP-R-1` two-state read (`scratchpad/w78/r6/disp_r1_probe.py`) | `REQ-DISP-R-1-NO-IMPLEMENTATION.status` = `UNRESOLVED`, `evidence_ref_ids` = `[]`, `evidence_inventory_review.status` = `PENDING` — **state 1 of §3.6**, so the carve-out applies unchanged. The same probe mutates a copy to `SATISFIED` in memory and confirms the recorder then refuses the row `DISP_R1_RESERVED_FOR_T2`. Canonical ledger untouched (`e52ed95c…` before and after) |
| Both `--dry-run` batches | exit **0** against the live ledger `e52ed95c…`; see §3.10's Status row for the figures |
| Five-leg rehearsal | 5/5 at the post-HR-0005 pre-state |

Probe F's serialization round-trip is the one probe whose *cited digest* moved:
it reproduced the pre-HR-0005 ledger `de236d7e…` byte-for-byte, and the writer
contract it verifies is unchanged — the live ledger `e52ed95c…` is produced by
the same three settings, as every dry-run's `structural_candidate_exit: 0`
re-demonstrates. The probe table below is retained as executed, with its
original digests, and must be read as an r1-round record.

Probes A–H were executed in the r1 round against the then-§1.1 bytes and are
carried forward unchanged; the r2 round re-verified all seven §1.1 hashes and the three
baseline gate exits (`extract=0`, `structural=0`, `preimpl=2` with 447 pending
/ 0 stale / 1 no-implementation, `ready=false`) and **executed no new ledger
probes**, because none of the five r1-review findings is a factual claim about
the ledger. `git status --short`, observed in the r2 round:

```
 M .beads/issues.jsonl
?? docs/goals/reviews/ledger/equity-os-blueprint-inventory-review-recording-design-r0.md
?? docs/goals/reviews/ledger/equity-os-blueprint-inventory-review-recording-design-r0-review-r0.md
?? docs/goals/reviews/ledger/equity-os-blueprint-inventory-review-recording-design-r1.md
?? docs/goals/reviews/ledger/equity-os-blueprint-inventory-review-recording-design-r1-review-r0.md
```

The `.beads/issues.jsonl` modification is the pre-existing unrelated dirt noted
in §1.1; the untracked files are r0, its review, r1, and r1's review — plus
this document once written. No canonical path is dirty. The §6.1 command block
is what re-derives this.

| Probe | What it demonstrates | Result |
|---|---|---|
| **A. 6-row sample** — `REG-A-01`, `DISP-G-1`, `SEQ-01`, `PG-2-04`, `DISP-R-1`, `ALIAS-001`; Phase A/B ordering; `DISP-R-1` carve-out applied | The recording mechanics are legal | structural **0**; preimpl pending **447 → 433** (exactly 14 = 2+3+3+3+3), stale **0**, alias untouched |
| **B. Full 447 + satisfy `REQ-DISP-R-1-NO-IMPLEMENTATION`** | The "obvious" gate-clearing move is forbidden **to this tool** | preimpl `--report-blockers` **ready=true**, pending 0/stale 0/noimpl 0 — but **structural fails**, `AssertionError` at `validate_ledger_structural.py:2756` (pre-HR-0005 line numbering; the post-HR-0005 equivalent is the `UNRESOLVED` branch at `:2763-2765`), exit **1**. Post-HR-0005 the recorder no longer reaches this probe's shape at all: it refuses the `DISP-R-1` row `DISP_R1_RESERVED_FOR_T2` (§3.6) |
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
   digest and 9–18 to another *(r2, r1-review Minor 1: r1 left this range at
   "9–17", the pre-renumbering count; the plan has 18 batches, §5.2)*. That is
   contract-legal and intended, but it will
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
   reviewer identity.
   *(r1: r0-review M-9d correctly refused to let this concession stand alone.
   §3.10 makes a five-leg rollback rehearsal *(r2, r1-review Minor 4: the
   fifth leg exercises `RECOVERY_REQUIRED`)* on a disposable full-tree
   replica a **hard precondition** on the first real write, with a
   machine-checkable proof object the recorder asserts and that is invalidated
   by any edit to the recorder or to the §1.1 pinned bytes.)*

   **Rewritten in r5 (r4-review I-2).** r0–r4 closed this item by saying the
   recorder's manifest parsing, lock, journal/rollback path, `SIGINT`/`SIGTERM`
   guards, `RECOVERY_REQUIRED` path and precondition set were "specified here and
   not yet implemented or tested", that "nothing in §3.8 has been executed", and
   that "the rehearsal has **not** been performed — `record_inventory_review.py`
   does not exist yet". As of r5 every one of those statements is false, and
   leaving them standing was the one place where this round's own discipline — no
   claim without fresh evidence — produced its inverse: a stale claim carried
   forward because no finding had named it. What is true, measured this round and
   tabulated with digests in §3.10's Status:

   - The recorder exists at SHA-256 `94c65444…` (r6; r5's bytes were
     `8d0410cd…`). Manifest parsing, the lock, the journal, the rollback path,
     the `SIGINT`/`SIGTERM` guards, the `RECOVERY_REQUIRED` path and the
     precondition set are implemented.
   - The five-leg rehearsal has been **performed** — 5/5 legs pass, on five
     fresh full-tree replicas at the post-HR-0005 pre-state — and the proof
     object at `scratchpad/inventory-reviews/rehearsal/proof.json`
     (`437f7492…`) binds `recorder_sha256 = 94c65444…`, the live bytes.
   - §3.8 has been executed twice under `--dry-run`, both exit 0, both leaving
     the canonical ledger at `e52ed95c…`.

   **What remains genuinely untested**, stated so nothing above is credited with
   more than it proves: no non-dry-run batch has ever run against the canonical
   ledger, so §3.8 steps 6–10 are evidenced only by the rehearsal replicas; and
   §3.10 is operator discipline over a gitignored, unauthenticated proof file,
   not an enforcement boundary. This is still the largest untested surface in the
   design — it is no longer an *unimplemented* one. **Added in r6:** §3.6's
   state-2 branch (`DISP_R1_RESERVED_FOR_T2`) is exercised only in memory, by
   `scratchpad/w78/r6/disp_r1_probe.py` mutating a copy of the row — the ledger
   has never been in that state, and putting it there is T1/T2's business, not
   this design's.

---

## 8. Summary of contract answers

| Question | Answer | Citation |
|---|---|---|
| Which reviews apply per kind? | `EVIDENCE`+`APPROVAL` on all 169 canonical; `SCOPE` additionally on the 109 non-register; none on 44 aliases | `validate_ledger_preimplementation.py:200-204`; goal L208-211, L495-496 |
| Exact counts? | 109 / 169 / 169 = **447** | freshly computed; blocker report |
| What is a "clean `REVIEWER`-role review"? | `verdict == "CLEAN"` (only legal value), `role == "REVIEWER"`, `role_binding_path == "CONTEXT.md"`, 64-hex binding digest, nonempty actually-invoked model/effort | `validate_ledger_structural.py:250-262, 342` |
| Which transition type for review completion? | **None.** Transition entries for review/evidence fields are rejected, and any transition stales the row's reviews | `:1732-1743, :1909`; probes D, E |
| Fresh user authority required? | **No** — for any of the 447 | goal L615-617, L624-626, L886-893, L957-976 |
| Does this open the preimplementation gate? | **No** — 1 `DISP-R-1` blocker remains while §3.6 state 1 holds; clearing it is T2's transaction, not this tool's | `:2759-2768`; probes B, B′; §3.6 |
