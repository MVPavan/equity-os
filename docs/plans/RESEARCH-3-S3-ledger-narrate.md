# RESEARCH-3 S3 — `ledger narrate` — Implementation Plan

**Origin:** `docs/specs/2026-10-27-research-3-thesis-analysis.md` §4, §5 "S3" (approved r4, gpt-6.1-sol `APPROVE`), with §0,
§1, §2, §3, §6 and the owner rulings. Bead `eqos-bnx`, slice 3 → S3. S2 closed live on 2026-11-02 at `f1bf13d7`. Format and
lessons: `docs/plans/RESEARCH-3-S2-management-credibility.md`, `docs/plans/RESEARCH-3-S1-risk-probe.md`.
**Status:** draft r1 (2026-11-02), for Sol's plan review. Not approved.
**Goal:** `ledger narrate <version>` turns an `APPROVED` head N into DRAFT N+1: N's sections and claims unchanged, plus model
notes that carry no number of their own. The panel decides N+1 with the same evidence bundle the model saw. The four Apar
heads end narrated and approved.
**Out of scope:**
- RESEARCH-4 (forward view), the memory draft (spec §4), any thesis successor. `thesis_narrative` is report text; it changes
  no canonical thesis (invariant 11).
- New evidence for the model: wider transcript spans, segment lines (`eqos-djv`, `eqos-ghv`), new `ACTUALS`, mapping-file
  changes. See D-3 and C-7.
- Any change to `run_draft.py`, `api/cli.py` (both 798 lines), `credibility.py`, `risk_probe.py`, the migrations, or the text a
  run writes.
**Constraints:**
- The model never computes or states a number (invariant 6); every status stays code-computed. Spec §1 applies to every line.
- No migration: section keys are free text and a narrative section adds no claim.
- Crisp minimal code (`.claude/rules/core/04-agent-stack.md` "Code size"). Python rules: `.claude/rules/python/`.
- Never open `stage4_holdout.yaml`, `stage4_manifest.yaml`, `data/holdout/`, `data/raw/onboarding/`.

## Live base (verified read-only at `f1bf13d7`)

| Period | Head | Status | Sections | Claims | `FLAGGED` rows | `REVISED_*` in the record |
|---|---|---|---|---|---|---|
| FY26_Q2 | v20 | `APPROVED` | 11 | 91 | R4 (S, T), R6 (T) | none |
| FY26_Q3 | v21 | `APPROVED` | 11 | 86 | R4 (S) | none |
| FY26_Q4 | v22 | `APPROVED` | 11 | 101 | R1 (T), R2 (L, T), R3 (L), R4 (S, T), R6 (L, T) | one `REVISED_UP` (conductor) |
| FY27_Q1 | v23 | `APPROVED` | 11 | 91 | R4 (S) | two `REVISED_UP` (conductor, margin) |

Thesis v13 is `APPROVED`: eight sections, 15,660 characters. No later version exists (max id 23). Every S2 `ledger check` shows
only `MATCH`, none `MATCH_UNTRUSTED`. No row in any head reaches `ACHIEVED`, `MISSED`, `ON_TRACK` or `BEHIND`.

## Spec against code at HEAD

Checked at `f1bf13d7`. S2's C-1 stands: spec §0 line numbers moved; this plan cites HEAD.

| # | Spec says | Code or data says | Recommended resolution |
|---|---|---|---|
| C-1 | §4: narrate adds a `NARRATIVE` section `open_questions`; "only `NARRATIVE` keys are added"; N is byte-identical | N already has `open_questions` (`run_draft.py:118`, `:787`), and a version's section keys are unique (`migrations/0012_report_ledger.sql:50`). The insert would fail. | Key the model's questions `analyst_questions`. Same duty, one renamed key. No lifecycle or section change to N. |
| C-2 | §4: N's sections are byte-identical in N+1 | Three of them then say something false of N+1: `not_performed` lists the driver analysis, thesis narrative and credibility judgment as absent (`run_draft.py:126-130`), `thesis_impact` says the narrative is not drafted (`falsifier_status.py:228`), and `management_credibility` says no judgment or trend is drafted. The live heads hold this text, so changing `NOT_DONE` cannot help them. | Spec. Keep the bytes. A fixed code-built paragraph at the top of `drivers` says those lines describe the predecessor (D1). The narrative sections follow `not_performed`, so the reader meets the disclosure in order. |
| C-3 | §4: the bundle is claims, operands, spans and locations | The bundle holds no status: `FLAGGED` and `REVISED_*` live in section text, so the model could not know which notes are due. It also holds no thesis text, though `thesis_narrative` must assess a thesis N only cites by threshold (`falsifier_status.py:226-231`). | Additive. The drafting prompt also carries N's rendered narrative. The bundle gains the rendered thesis version N's `thesis.*` claims resolve to. The panel's text already holds N's sections inside N+1. Thesis prose is not citable. |
| C-4 | §4: location capture "one of N's admitted captures (`allowed_captures`)" | `allowed_captures` needs the run's `Prior` and originals (`run_draft.py:713`); N does not store them. | One test: (capture, anchor) is a citable location of the bundle and `resolve_location` passes (`citations.py:355-377`). Every citable location is a span N cites, and N passed `_check_sources` (`run_draft.py:685-704`) at its write, so admission, entity and cutoff follow. All four location refusals in §5 stay as tests. |
| C-5 | §4: "first seen at or before N's derivation cutoff" excludes a later disclosure | On a retrospective run the derivation cutoff is the run's own time (v22: 2026-11-02; source cutoff 2026-06-04), and all Apar captures were first seen by September 2026. The test alone would pass a later quarter's transcript. | Citable-location membership is what refuses it on Apar. The later-disclosure test uses that real capture and asserts a refusal, not which check fired. Certain from `resolve_location` and the v22 heading. |
| C-6 | §4: after a panel rejection, the next write is "rework or full successor" | The panel never names claims (`panel.py:156-158`), so `rejected` is empty, `plan` returns `None` (`rework.py:215-219`), and `--full-successor` refuses (`run_draft.py:287-289`). The only route is an ordinary `run`. | Code. P6 and gate (f). This also confirms why S2's (d2) cannot pass: it demands the full-successor heading (`scratchpad/research3-s2/cred_gate.py:164`). |
| C-7 | §4 expects `drivers` to explain results | Citable spans are only N's guidance quotes, four to eight short fragments per head. No transcript commentary on causes reaches the model, and no segment line exists. | Spec. `drivers` states what the cited claims support and names each cause as not established. Disclosed (D1), follow-up bead. This falls short of what a reader wants from a driver section; widening it is new evidence scope, not S3. |
| C-8 | §5: "Rework from an approved narrated version" | An approved head has no rejected claims (`rework.py:143-146`), so a `run` on it is an ordinary rerun. Selective rework needs a narrated head under `REQUEST_CHANGES --claim`, which only follows `SUBMIT` (`lifecycle.py:67-70`). | Test both: an ordinary `run` from an approved narrated head, and a selective rework of an `IN_REVIEW` narrated version after an owner `decide --claim`. Each drops the narrative, stays `AS_KNOWN`, and narrates again once approved. |
| C-9 | §4: `panel.py:194-196` "gains" the bundle | `RecordedReviewer` binds the SHA-256 of the exact subject text (`recorded_reviewer.py:80`), and `ledger export` writes the narrative only (`ledger_cli.py:354-359`). Appending the bundle makes the hash the operator can compute wrong. | P5: the panel text is narrative plus bundle, only for a narrated version; a new `ledger export --panel-text` writes those exact bytes, so the binding proves Sol received them. Every earlier version's text is unchanged. |
| C-10 | §4: "Every claim is `MATCH`" | The run and panel paths accept `MATCH_UNTRUSTED` (`lifecycle.py:104`). | Spec, strictly, at narrate only. All four heads are all `MATCH`, so this costs Apar nothing. |
| C-11 | §4: the only structural exemptions are dates and period labels; "ids … all block" | Rows are named `R6`, `F11` in N. A model cannot type them. | Spec. It names a row in words and by placeholder (`{{c:probe.R6|ref}}`); the scan removes placeholders first. The prompt says so. |
| C-12 | §4 forbids `one`, `two`, `ten` and similar anywhere in a narrative section | Common English: "one of", "no one". Expect refused first drafts. | Spec. The prompt lists the lexicon. A refusal writes nothing, so the remedy is to rerun the command. No repair loop (cut). |

"S2 C-12" below is row C-12 of the S2 plan, the owner's trend requirement. Spec OD-1's C-12 is a register item measuring machine
effort; S3 adds nothing to it.

## Investigation findings

**F-1. Carrying a claim is proven.** A rework re-inserts `read_version` claims as held (`rework.py:110-113`, `store.py:89-125`),
including FIGURE, CALCULATION, THESIS_CLAIM and SOURCE_QUOTE citations. Narrate copies them the same way, so
`bound_contract` (`citations.py:346-352`) still binds each quote: it matches on location and text, never on version.

**F-2. No span read is needed for the bundle.** A passing `SOURCE_QUOTE` claim's `citation.quote` equals the retained span
(`claim_check.py:116-118`). N is approved, so the bundle reads the quotes from the claims and needs no snapshot store. The panel
role already reads these tables (`panel.py:194`) and the trace operands (`citations.py:184-201`).

**F-3. Existing checks already cover four guardrails.** `render_section` refuses an unknown key and a bad style
(`display.py:98-108`, `:55-63`; no registered style token holds a digit, `contracts/ledger.py:109-117`). `scan_section` refuses
an unlabelled paragraph and a failing location (`numeral_scan.py:59-69`). Narrate adds only what these miss.

**F-4. Rework needs one set changed.** `plan` keeps every section outside `DERIVED | DISCLOSED` (`rework.py:243`), and
`Gate.close` calls `section_body` on each (`:124-126`), which has no intro for a narrative key (`run_draft.py:798`). Adding the
narrative keys to that exclusion is the whole change; narrative sections own no claims, so `:225` needs nothing.

**F-5. The client exists, with two gaps.** `ThesisModelClient`, `ClaudeOpusClient` and the watchdog give injection, an explicit
timeout and one bounded retry (`thesis/client.py:34-49`, `thesis/subprocess_runner.py:80-133`, `thesis/settings.py:41-42`).
- The prompt is a single argv item (`claude_client.py:60-63`), and Linux caps one at 131,072 bytes. Largest prompt estimated
  at about 75 KB (v22 narrative 35 KB, thesis 16 KB, bundle about 20 KB, rules). A larger one fails at launch as a refusal
  (`subprocess_runner.py:111-112`).
- `build_command` cannot restrict the CLI. `claude -p` from the checkout would by default have file tools and read project
  instructions. `claude --help` (2.1.314) lists `--tools ""` and `--setting-sources`; `--bare` is unusable because it refuses
  OAuth. See OD-1.

**F-6. Later runs are unaffected.** `preflight` selects claims by section key (`run_draft.py:316-337`) and `read_record` reads
only `management_credibility`, so a narrated previous-quarter head carries as before. A rejected N+1 is the period's head, so
the next quarter's `run` refuses until it is recovered (`:310-313`). Nothing in S3 runs a later quarter meanwhile.

## S3 duties carried from S1 and S2

**Duty 1: S2 C-12, the trend and what it means.** The owner's goal asks where credibility is rising or falling and what that
means for the thesis (`docs/goals/2026-10-27-research-report-targets.md:15`).

*What this record can say.* Every row is `UNRESOLVED`, because no Apar quote names a single target year. The only movements are
two `REVISED_UP`s between stated ranges, and Sol ruled those describe movement, never achievement or better credibility. So:
- **Can claim:** which stated figures moved, in which report; that no commitment has been tested against a filed result; that the
  thesis therefore cannot lean on guidance as evidence either way; what would make a row testable (a single-year quote, a
  registered filed measure).
- **Cannot claim:** that credibility rises, falls or holds. Zero scored outcomes is no trend, not a flat one. **On Apar the
  owner's question gets an honest "not assessable", not an answer**, and it stays so until two scored windows exist for one
  metric and scope. The mechanism is delivered and proven on synthetic rows; the substance waits on data. The S3 close must
  say so.

*Mechanism (P3).*
1. Code, not the model, builds one row per commitment episode at the top of `credibility_notes`: metric, scope, last event,
   outcome, trend. The trend comes from scored outcomes only: within one (metric, scope), compare consecutive `FY<yy>` windows'
   `.latest` outcomes, where `ACHIEVED` and `ON_TRACK` are met, `MISSED` and `BEHIND` are not. Not met then met is `RISING`, the
   reverse `FALLING`, the same `STEADY`. Otherwise `NOT_ASSESSABLE` (no scored comparison). A revision event never enters it.
2. With no scored row, a fixed sentence says no trend can be stated (D2).
3. The model then writes what the record means for the thesis, labelled `{{e:inferred}}`, citing thesis-relevant claims.

*Guardrails against implying more.*
- The rows are sealed code output the model never edits.
- With no scored row, a closed verdict lexicon (P4) refuses the draft: over all of `credibility_notes`, and over any sentence in
  another narrative section that mentions credibility, management or guidance. Refused: "credibility is rising", "the higher
  range shows better delivery".
- The panel brief quotes Sol's `REVISED_UP` ruling and asks for any softer implication that passes the lexicon ("confidently",
  "comfortable"). That residue is the panel's, per spec §4's coverage statement.

**Duty 2: the R6 wording finding.** Located in `scratchpad/research3-s1/task6/live/responses/`: `FY26_Q2-v14-p1.md:7` (with the
required content), carried in `FY26_Q2-v14-p2.md:5` and `FY26_Q2-r1.md:3`, parked by the S1 plan (`:1025-1026`).
`FY26_Q4-r1.md` itself holds no R6 finding; its line 9 reads the implications as acceptable. The finding: R6's fixed sentence
"if this leverage is high for the business, balance-sheet risk may be higher" is too generic to guide investigation.
*Resolution:* the template stays as approved, since N is byte-identical and S1 kept it conditional on purpose. `risk_notes` carries
the interpretation. R6 is due on FY26_Q2 (T) and FY26_Q4 (L, T); P4's notes-due check refuses a draft without it. Sol's three
required elements go in the prompt and the brief: the flag identifies increased borrowings relative to equity; the note separates a
trend flag from a limit breach; it names the unresolved funding or repayment question. The panel judges the content. The bundle
holds no funding detail, so the question stays open and is stated as one. Stale quarters render R6 `COMPUTED`, so no R6 note is due.

**Duty 3: the sections.** `drivers` (C-7), `credibility_notes` (Duty 1), `thesis_narrative` (the assessment S06 asks for,
`docs/specs/equity-os-s06-output-materiality-falsifiers.md`, `thesis_impact` row: unchanged, strengthened, weakened, reversed or
uncertain, with supporting claims, labelled `{{e:opinion}}`), plus `risk_notes` and `analyst_questions` (C-1). Each section's
paragraphs carry labels; spec §1 applies.

**Duty 4: the live base.** Thesis v13; heads v20, v21, v22, v23 (table above; Task 4).

## Design decisions (for review)

- **P1, three writes-free steps, then one transaction.** Read N; call the client outside any transaction; run every check; only then
  open the write transaction, lock (WATCHLIST, then the version, as `run_draft.py:354-359`), recheck head, status and sealed digest,
  insert, and check `AS_KNOWN` in place. Any failure leaves every table unchanged. N+1 keeps N's `knowledge_cutoff`, `pinned_run_ids`
  and claims, `report_id`, and `predecessor_id = N`.
- **P2, sections.** `NARRATIVE` is a frozenset beside `DERIVED`: `drivers`, `risk_notes`, `credibility_notes`, `thesis_narrative`,
  `analyst_questions`, in that order, ordinals following N's. The model returns `## <key>` blocks; any missing, repeated or other key
  refuses, which covers "an extra section key" and "an edited deterministic section". Code writes each heading and prepends D1 and the
  trend block. Code copies N's sections, so no comparison against model text exists to fail.
- **P3, the trend** is a pure function over N's `management_credibility` body. See Duty 1. This rule is a methodology choice,
  approved by Sol with this plan; see OD-3.
- **P4, checks narrate adds.** `scan_narrative` over every narrative body, code-built lines included: digits outside dates and period
  labels; the spec's number-word lexicon, whole-word and case-insensitive; a placeholder touching anything but whitespace or
  `( ) , . ;`; any `{{` left after placeholder, class and location markers are removed (`{{c:fact.revenue}}` has no pipe, holds no
  digit, and would print raw). Over the model's text only: the verdict lexicon, with no scored row (`rising`, `falling`, `improv*`,
  `deteriorat*`, `better`, `worse`, `stronger`, `weaker`, `credible`, `reliable`, `trustworth*`, `achiev*`, `deliver*`, `on track`,
  `beat*`, `missed`, `conservative`, `aggressive`); citable-location membership (C-4); and notes due: each `FLAGGED` probe row needs a
  placeholder with prefix `probe.R<n>` in `risk_notes`, and each `REVISED_*`, `MISSED` or `BEHIND` row one with prefix
  `episode.<id>` in `credibility_notes`. Prefix, because a guard-flagged row has no ratio claim. N+1 then passes the existing
  `check_version` (F-3), with strict `MATCH` (C-10).
- **P5, the panel text.** `panel_text(cursor, draft, limits)` is the narrative for a version with no `NARRATIVE` key, otherwise the
  narrative plus the bundle. `review` takes the limits and `_gate` uses it at `panel.py:196`; `ledger panel` and
  `ledger export --panel-text` load them. N+1's `author` is `fundamentals-narrate:<client label>:bundle:<sha256>`, sealed
  (`migrations/0012_report_ledger.sql:234`), so a rebuilt bundle that differs refuses at the panel, proving both calls read the same
  evidence, and the drafting model is on record, with no new column.
- **P6, a rejected narrative.** `REQUEST_CHANGES` or `REJECT` on N+1 → an ordinary `run` writes deterministic M with N+1 as predecessor
  and no narrative → gate (f) compares M with N → `check`, `submit`, panel `APPROVE` on M → `ledger narrate M` → gates → panel on
  M+1. Spec §4 requires that order, with no lifecycle change. Cost: one rerun, one model call and two Sol rounds per rejection. Narrate
  refuses N+1 itself (it carries `NARRATIVE`, and N is no longer head). The fix in the next draft comes from a code or prompt change,
  or just a redraft, as the rejection's reason decides; a code change re-enters the phase-end loop first.
- **P7, untrusted text.** Quotes reach the prompt as data inside a marked block, with the instruction to ignore directions in them.
  With tools off, a hostile quote can only change the draft's wording, which the output checks and the panel still see.

Considered and cut, for the owner's size rule:
- A repair loop re-prompting on a refusal (rerun the command).
- Storing the bundle, the prompt or the raw response (the bundle is deterministic; author seals its digest).
- A separate `allowed_captures` recomputation (C-4).
- Enforcing label honesty in code, such as "model paragraphs must be `inferred`" (spec §4 gives it to the panel).
- Checking the thesis stance word in code (panel).
- Reading spans from originals (F-2).
- A narrate re-check at `submit` or panel (narrate is the only writer of these keys, and the version is then sealed).
- A new client class, a prompt template file, a CLI per section, an operator wrapper.
- Any `NOT_DONE` or template edit (C-2, Duty 2).

## File map

| File | Change | Responsibility | Lines |
|---|---|---|---|
| `src/fundamentals/ledger/narrate.py` | create | Flow (P1), prompt, section assembly (P2), `NarrateConfig` and its loader, `NarrateRefusedError` | ≈ 190 |
| `src/fundamentals/ledger/narrate_checks.py` | create | `parse_draft`, trend rows (P3), verdict lexicon, notes due, location membership (P4) | ≈ 110 |
| `src/fundamentals/ledger/evidence_bundle.py` | create | `BundleLimits`, `Bundle`, `build_bundle`, `panel_text` (P5) | ≈ 95 |
| `src/fundamentals/ledger/numeral_scan.py` | modify | `scan_narrative`, sharing the date and period patterns | +35 |
| `src/fundamentals/ledger/falsifier_status.py` | modify | `NARRATIVE` beside `DERIVED` | +2 |
| `src/fundamentals/ledger/rework.py` | modify | `:243` skips `NARRATIVE`; docstring | +2 |
| `src/fundamentals/ledger/panel.py` | modify | `review(limits=)`; `_gate` uses `panel_text` | +8 |
| `src/fundamentals/thesis/settings.py`, `thesis/claude_client.py` | modify | `extra_args: tuple[str, ...] = ()`, appended in `build_command` | +2 |
| `src/fundamentals/api/ledger_cli.py` | modify | `narrate` action; `export --panel-text`; `_panel` loads limits | +45 |
| `config/narrate.yaml` | create | Provider, model id, args, timeout, retries, limits (OD-1) | ≈ 12 |
| `tests/fundamentals/test_narrate_checks.py` | create | Pure: scan table, parse, trend, verdict lexicon, notes due, bundle shape | ≈ 150 |
| `tests/fundamentals/test_narrate_flow.py` | create | Pilot: full path, refusal table with zero deltas, panel, rework | ≈ 240 |

**Size.** About **490 production lines** against the spec's 400–600, and **390 test lines** against 300–400. Why this holds where S2's
1,060 and 1,900+ did not:
- S2 added a sealed record grammar, a window rule, financial outcomes and a correction path. S3 adds no persistent state and no
  financial logic: its one rule is the trend, about 30 lines.
- The refusals are one parametrized table: a list of bad drafts, one assertion on the outcome. Spec §5 lists fourteen; each stays
  a row, not a test function.
- Adverse trend cases are pure.
- No existing test file changes, so no reseal.
- `run_draft.py` and `cli.py` stay untouched.

**The check.** After the first green implementation round, the orchestrator runs `wc -l` on these files. Over 600 production or 400
test lines is a stop: name what grew, cut or justify it in the bead before review.

## Test-first order, gate and sealing

1. **Tests round (one Opus round, before any production change).** Write the two test files in final form. Production names are imported
   inside tests and fixtures, so each file collects on pre-change source. The pilot fixture comes from `test_prep2b_run_draft.py`
   (`dictionary`, `mapping_set`, `pilot`), as `test_credibility_binding.py:42` does. `_rerun` and `_request_changes` come from their
   existing modules. Nothing is added to `test_prep5_rework.py` (760), `test_prep2b_run_draft.py` (763) or
   `test_credibility_binding.py` (734); over 800 lines routes `CONTRACT` (`scripts/verify.sh:470-473`). The round reports `wc -l`.
2. **Red capture, orchestrator only:** `scripts/verify.sh red RESEARCH-3-S3 tests/fundamentals/test_narrate_checks.py
   tests/fundamentals/test_narrate_flow.py`. Every node must fail, with none missing; a node passing pre-change is vacuous, and is
   fixed before production code.
3. **Implement** Tasks 1–3 without touching sealed files. A sealed test changes only through `scripts/verify.sh reseal RESEARCH-3-S3
   <proof-file>`, whose proof shows the amended assertion failing against the implementation it was wrong about.
4. **Gate.** `S3_BASE` is the plan's approved commit, recorded in the bead at the tests round. Every S3 gate runs
   `VERIFY_SCOPE_BASE=$S3_BASE scripts/verify.sh gate RESEARCH-3-S3` on its own; its `ROUTE:` line is read before anything else, and it
   is never chained with a live write.
5. **Workers.** The gate uses at most 8 (`-n 8 --dist loadfile`). Focused runs use `-n 0`, and none runs beside a gate: the
   machine is shared, 8 in total.

## Tasks

### Task 1: Scan and pure checks

Goal: every spec §4 deterministic refusal that needs no database, as pure functions.

Files:
- Modify: `src/fundamentals/ledger/numeral_scan.py`, `src/fundamentals/ledger/falsifier_status.py`
- Create: `src/fundamentals/ledger/narrate_checks.py`
- Test: `tests/fundamentals/test_narrate_checks.py`

Interfaces:
- Consumes: `PLACEHOLDER` (`display`); `CLASS_MARKER`, `LOCATION_MARKER` (`numeral_scan`); `CREDIBILITY`, `RISK_PROBE`.
- Produces:
  - `NARRATIVE: frozenset[str]` and `NARRATIVE_ORDER: tuple[str, ...]` (`falsifier_status`).
  - `scan_narrative(text: str) -> tuple[str, ...]`: reasons, empty when clean. Each names the offending token.
  - `parse_draft(text: str) -> Mapping[str, str]`, refusing per P2.
  - `class Trend(StrEnum)`: `RISING, FALLING, STEADY, NOT_ASSESSABLE`.
  - `trend_rows(credibility_body: str) -> tuple[str, ...]`; `any_scored(credibility_body: str) -> bool`.
  - `verdict_words(section: str, text: str) -> tuple[str, ...]`.
  - `notes_due(probe_body: str, credibility_body: str) -> Mapping[str, tuple[str, ...]]`: section key to required key prefixes.
  - `missing_notes(due, bodies) -> tuple[str, ...]`; `bad_locations(text: str, citable: frozenset[tuple[str, str]]) -> tuple[str, ...]`.

Approach: `scan_narrative` shares the date and period alternatives with `_STRUCTURAL` (`numeral_scan.py:33-34`) through named
constants, leaving `scan_section`'s behaviour unchanged. A trend row reads the keys in the row's own placeholders for metric, scope and
window, so no record grammar is added; it names its episode through `{{c:…|ref}}` and holds no digit. D1 and D2 are constants here;
a test runs `scan_narrative` over them.

Verification: `uv run pytest tests/fundamentals/test_narrate_checks.py -n 0`. Named cases:
- (a) The refusal table: `forty`, `doubled`, `-fold`, `percent`, `bps`; `amount:123`; a numbered item; `[^1]`; `sha256 <hex>`; `R6`; `× 100`; `-{{c:k|}}`; `{{c:k|}}x`;
  `amount:{{c:k|}}`; `{{c:k|}}%`; `{{c:fact.revenue}}`. Allowed: a date, `FY26_Q2`, `Q3`, `({{c:k|}})`, `{{c:k|unit}},`.
- (b) A digit in a style field through `render_section`'s real refusal.
- (c) `parse_draft`: missing, repeated and extra keys; a deterministic key such as `risk_probe`.
- (d) Trend, on bodies from `credibility.build`: `MISSED` then `ACHIEVED` is `RISING`, the reverse `FALLING`, same `STEADY`; `BEHIND` then `ACHIEVED` is `RISING`; a
  lone scored window and every `UNRESOLVED` row are `NOT_ASSESSABLE`; two `REVISED_UP`s change nothing.
- (e) `verdict_words`: on v22's shape, "credibility is rising" and "better delivery" refuse; "revenue fell against a year earlier" outside `credibility_notes` passes; with a scored row, nothing refuses.
- (f) `notes_due` on the literal shapes of v20 and v23's rows; a guard-flagged row's prefix.
- (g) D1, D2 and every trend row pass `scan_section` and `scan_narrative`.

Test seams: pure functions. Dependencies: None.

Risks: the lexicon over-refuses ordinary English (C-12). Accepted: a refusal costs one model call.

### Task 2: The bundle and the panel

Goal: `build_bundle` is deterministic from a version's claims; the panel reviewer receives it; the binding covers it.

Files:
- Create: `src/fundamentals/ledger/evidence_bundle.py`
- Modify: `src/fundamentals/ledger/panel.py`
- Test: `tests/fundamentals/test_narrate_checks.py` (shape), `tests/fundamentals/test_narrate_flow.py` (panel)

Interfaces:
- Consumes: `store.read_version`, `narrative`, `render_claim`, `parse_style`; `TRACES` (`citations`).
- Produces:
  - `BundleLimits` (frozen): `max_span_chars: int`, `max_total_bytes: int`.
  - `Bundle` (frozen): `text: str`, `citable: frozenset[tuple[str, str]]`, property `sha256 -> str`.
  - `build_bundle(cursor: Cursor[Any], draft: VersionDraft, limits: BundleLimits) -> Bundle`.
  - `panel_text(cursor: Cursor[Any], draft: VersionDraft, limits: BundleLimits | None) -> str`.
  - `review(..., limits: BundleLimits | None = None)`.

Approach, in order, per spec §4:
- Each claim: key, value as rendered, citation kind, capture id and anchor. Each trace: operand claim keys, flattening child traces, mapping an operand's `key_digest` to claims with that digest; an operand no claim holds shows `unclaimed`.
- Each distinct SOURCE_QUOTE span in full (F-2). A span over `max_span_chars` is omitted and not citable.
- The citable list, written as the `{{s:<capture id>|<anchor>}}` markers the model may use.
- The rendered thesis (C-3), resolved through `cited_claim_id` on N's `thesis.*` claims, no lock taken. No `thesis.*` claim refuses.
- Over `max_total_bytes` refuses.

N and N+1 hold the same claims, so the bundle is identical from either. A narrated version whose rebuilt `sha256` differs from its author's refuses at the panel gate. A narrated version with `limits=None` refuses. A version with no narrative key returns exactly today's text.

Verification: `uv run pytest tests/fundamentals/test_narrate_checks.py -k bundle -n 0`, then the Task 3 panel nodes. Cases:
- two builds are byte-equal; a span one character over is absent and not citable; one at the limit is whole;
- operands map on a probe trace and through a child sum;
- a cap one byte short refuses;
- no truncation: every present span equals its claim's quote;
- `test_ledger_panel.py` stays green unchanged, which proves the non-narrated text did not move.

Test seams: `build_bundle` on the pilot's version. Dependencies: Task 1.

Risks: `panel.py` is on the approval path. Its change is one branch on the presence of a narrative key.

### Task 3: The flow, the CLI, the rework skip

Goal: spec §5's full path works end to end with a fake client, and each refused case leaves every table unchanged.

Files:
- Create: `src/fundamentals/ledger/narrate.py`, `config/narrate.yaml`
- Modify: `src/fundamentals/ledger/rework.py`, `src/fundamentals/api/ledger_cli.py`, `src/fundamentals/thesis/settings.py`, `src/fundamentals/thesis/claude_client.py`
- Test: `tests/fundamentals/test_narrate_flow.py`

Interfaces:
- Consumes: Tasks 1, 2; `_head`, `_READ_COMMITTED` (`run_draft`); `check_version`, `version_status`, `_LOCK`, `_NOW`, `DecisionRefusedError` (`lifecycle`); `store.create_version`, `sealed_digest`; `content_hash`; `ThesisModelClient`, `ThesisClientError`; `ClaudeOpusClient`, `CodexSolClient`.
- Produces:
  - `class NarrateRefusedError(DecisionRefusedError)`, carried by `LEDGER_FAILURES` (`ledger_cli.py:132-143`) as a `ValueError`.
  - `class Provider(StrEnum)`: `CLAUDE, CODEX`.
  - `NarrateConfig` (frozen): `provider: Provider`, `claude: ClaudeClientConfig`, `codex: CodexClientConfig`, `limits: BundleLimits`.
  - `load_narrate_config(path: Path) -> NarrateConfig`; `narrate_client(config: NarrateConfig) -> ThesisModelClient`.
  - `narrate(pool: ConnectionPool, version_id: int, *, client: ThesisModelClient, limits: BundleLimits, catalog: SourceCatalog, snapshots: SnapshotStore) -> int`.
  - `ledger narrate <version> --stock … --snapshot-root … [--watchlist] [--issuer-config]… [--narrate-config config/narrate.yaml]`, as the runtime role, printing the new version id.
  - `ledger export <version> --panel-text --out <path> [--narrate-config …]`.

Approach:
- **Refusals before any model call:** N's status is not `APPROVED`; N is not its period's head (`_head` filters to earnings updates, so a thesis id refuses too); N carries a `NARRATIVE` key; bundle faults.
- **The prompt** (a constant, digit-free where it can be) holds: the output format and five keys; the marker syntax; the scan rules and both lexicons; the notes due for this version, by key prefix; R6's three elements when R6 is due; that rows are named in words and by placeholder (C-11); that `credibility_notes` must state what the record means for the thesis without a verdict, and must not restate the code rows; that `drivers` names a cause not established rather than guessing; that `thesis_narrative` gives one S06 stance as `{{e:opinion}}`; P7. Then N's narrative and the bundle.
- **`ThesisClientError` becomes `NarrateRefusedError`.** Timeout and retries are the config's (`subprocess_runner.py:80-133`). No retry above them.
- **Assembly and checks** run before the write transaction, in P4's order, and all reasons are reported together.
- **`rework.py:243`** adds `NARRATIVE`.
- **`config/narrate.yaml`** per OD-1. No secret in it.

Verification: `uv run pytest tests/fundamentals/test_narrate_flow.py tests/fundamentals/test_ledger_panel.py tests/fundamentals/test_ledger_panel_cli.py tests/fundamentals/test_prep5_rework.py -n 0` (compose postgres plus retained originals). Named tests in `test_narrate_flow.py`:
- `test_full_path_narrated_version_supersedes_its_head`: `run` → submit → panel `APPROVE` → narrate with a fake client → N+1 sections are N's plus five keys in order; every claim's `model_dump` equal; cutoff, pins and predecessor as P1; `AS_KNOWN` all `MATCH` → submit → panel with a fake reviewer that records `subject_text`, which holds the bundle → `APPROVED`, N `SUPERSEDED`.
- `test_a_recorded_response_binds_the_panel_text`: a binding over `export --panel-text` bytes decides; one over plain `export` bytes refuses.
- `test_each_bad_draft_writes_nothing` (parametrized; spec §5's list, every table's count unchanged, the refusal naming its cause): number word; `amount:123`; numbered item; each of `-{{c:…|}}`, `{{c:…|}}x`, `amount:{{c:…|}}`; digit in a style field; unknown claim key; a location in another issuer's document; a same-issuer later disclosure (C-5); a capture outside the package; an eligible location that is not citable; an extra key; a deterministic key; a due note missing; a verdict word on a no-score body.
- `test_narrate_refuses_the_wrong_version` (parametrized): `DRAFT`, `IN_REVIEW`, not the head, already narrated, a thesis id. The client is never called.
- `test_a_bundle_over_the_cap_refuses`, and a client error refusing, each writing nothing.
- `test_a_stale_head_refuses_under_lock`: a fake client's `generate` writes a new head, and narrate refuses with no second version.
- `test_a_rejected_narrative_reruns_without_it` (P6): panel `REQUEST_CHANGES` on N+1; `--full-successor` refuses; an ordinary rerun writes M, with no narrative key, `AS_KNOWN`, predecessor N+1; narrate on M refuses until M is approved, then succeeds.
- `test_rework_drops_the_narrative` (C-8, parametrized): an ordinary `run` from an approved narrated head; a selective rework after `REQUEST_CHANGES --claim` on an `IN_REVIEW` one. Each carries no narrative, `AS_KNOWN`, and narrates once approved.
- `test_the_c12_case`: the fake client's honest paragraph on the pilot's unscored rows gives N+1 with every row `NOT_ASSESSABLE`, D2 present, and the code rows byte-equal to `trend_rows`; "credibility is rising" refuses. The synthetic `RISING` and `FALLING` are Task 1 (d).

Test seams: an injected fake `ThesisModelClient`; the pilot's four-quarter run on its own `eqos_test_*` database. Dependencies: Tasks 1, 2.

Risks: medium. Two writers hold the same locks in the same order as `write_run_draft`. A wrong refusal costs a rerun; a wrong acceptance reaches only a panel that reads every sentence.

### Task 4: Narrate the four Apar heads and close S3 (operational, orchestrator)

Goal: four new `APPROVED` versions, each N+1 of its head, in order FY26_Q2, FY26_Q3, FY26_Q4, FY27_Q1, each with Sol's `APPROVE` through `ledger panel`.

Files:
- Create (never committed): `scratchpad/research3-s3/narr_gate.py`, `s3q.sh`, `s3panel.sh`, `make_brief.py`, adapted from S2's. Outputs under `scratchpad/research3-s3/task4/`.

Interfaces:
- Consumes: Tasks 1–3 at the phase-approved commit, with a passing gate and Sol's `APPROVE`; heads v20–v23; S2's `$RM`, `$CFGS`, `$LOC`, `$INTAKE`, `$SNAP` (`scratchpad/live-run-1/live-scratch/lq.sh`), `counts.py`, `delta.py`, `digests.py`.
- Produces: four `APPROVED` versions, their exports, a post-run backup.

**Freeze before rehearsal (S2 lesson).** A read-only scratch dump computes, for v20–v23: the bundle's SHA-256, the code-built D1 text and trend rows, and the notes due. Sol's phase-end review judges them. The orchestrator commits them here as frozen expectations, naming Sol's verdict and date. Task 4 does not start before that commit. A rehearsal value that differs is a deviation; it never replaces a frozen one. **Model prose is not frozen and cannot be:** each call differs, so rehearsal text is never expected to equal live text, and every live panel reads its own.

**Expected counts delta (provisional until the freeze).**

| Quarter | `narrate` (`report_versions`, `report_sections`, `numeric_claims`) |
|---|---|
| FY26_Q2 | +1, +16, +91 |
| FY26_Q3 | +1, +16, +86 |
| FY26_Q4 | +1, +16, +101 |
| FY27_Q1 | +1, +16, +91 |

`calculation_traces`, `facts` and `validations` +0 on `narrate`: its `check_version` inserts nothing. A refused `narrate`: every table 0. `check`: `validations` +1. `submit`: `decisions` +1. `export`: none. `panel`: `decisions` +1, `panel_reviews` +1, `validations` +1. Recovery `run` (P6, rehearsal only): +1, +11, the quarter's claims; traces +0 (S2 F-8).

Approach:
1. **Rehearsal, all four quarters, on a restored copy.** `db backup` → `db restore --database eqos_test_s3_runs`, roots as `cp -a` copies under `$OUT/roots/`; `OUT=scratchpad/research3-s3/task4/$ENV`, preflighted as S2 Task 4. The real client runs, because the argv, flags and prompt size are what the rehearsal must prove. Five to seven model calls. The rehearsal panel uses a `rehearsal` verdict file and an orchestrator-written response, whose binding hashes `export --panel-text`.
   - **Client probe, first.** Through the exact configured argv, a scratch prompt asks the CLI to read a repo file and name any tools. It must have none, and must show no project instructions; OD-1 falls back otherwise.
   - **Rejected-narrative drill, on FY26_Q2** (P6): narrate, gates, submit; a rehearsal `REQUEST_CHANGES` with no claims; `run --full-successor` refuses, all 0; an ordinary `run` writes M; gate (f) passes on M; check, submit, rehearsal `APPROVE`; narrate M; gates; rehearsal `APPROVE`. Attempt paths `<Q>-r<n>`. The remaining quarters continue from it.
   - **No `src` copy.** No S3 drill needs changed code, so no overlay. If a code fix must be drilled, a copied `src` cannot run the operator (`risk_probe.py:445`, `cli_parser.py:51` anchor on `parents[3]`): use S2's symlink overlay with only the changed file differing.
   - `db check-live` refuses a test database; rehearsal health is the deltas, `ledger check` and the gates, with `digests.py` at close.
2. **Live, per quarter; stop at the first deviation; never re-run a write that partly committed.**
   - `ledger narrate <N>` → prints `<v>`; delta checked. A refusal: read the reason; rerun if it is a wording fault, up to three times per quarter; otherwise stop. Each rerun is a fresh model call and writes nothing.
   - `ledger check` → all `MATCH`; delta checked.
   - **Gates, read-only, to `$OUT/gate/<Q>.txt`:**
     - (a) N is `APPROVED`, head, and is `<v>`'s predecessor; `<v>` has N's cutoff and pins.
     - (b) `<v>`'s first eleven sections are N's byte for byte; the next five are `NARRATIVE_ORDER`, ordinals following.
     - (c) Every N claim's full `model_dump()` equals `<v>`'s, key sets equal: **no number moved and none was added.**
     - (d) Bundle SHA, D1 and trend rows equal the frozen values; the author names that SHA.
     - (e) An independent scratch recheck of the model text, not importing the code: digits, placeholder keys, locations against the bundle, and notes due (R6 on FY26_Q2 and FY26_Q4; each `REVISED_UP` on FY26_Q4 and FY27_Q1).
     - (f) **Recovery only, replacing S2's (d2)**, on a deterministic M against N, not against the rejected N+1: section keys equal; every section byte-identical except `heading`, where only the cutoff, `Prior:` and `Memory retrieved` lines may differ; every claim's full `model_dump()` equal; the rejected N+1 named as M's predecessor. No delta file: a fix that moves a deterministic section is a code change and needs its own frozen delta, as S2's. M+1 is then gated against M by (a)–(e).
     - (g) Deltas and (a)–(e)'s results equal the rehearsal's, model text excepted.
   - `ledger submit` → `ledger export --panel-text` and `ledger export` to `$OUT/out/` → a fresh Sol round, brief below; reply saved to `$OUT/responses/<Q>.md`, read before recording; verdict to `$OUT/verdicts/<Q>.json`.
   - `ledger panel <v> …` → `APPROVED`; delta checked; `db check-live` exits 0 after every write.
3. **Close.** `ledger export --stock APARINDS --out $OUT/export --status-notes`; post-run `db backup`; `digests.py` shows every earlier sealed digest unchanged; bead notes record ids, backup id, verdicts, and what Duty 1 could not answer.

**Panel brief, each quarter.** "List ALL issues in a single exhaustive report", as the stack requires, plus:
- Read every model sentence against the evidence it cites: spec §4's residual list (quantities as "half", comparatives, magnitude words, implied arithmetic, direction claims, honest labels).
- Sol's ruling, quoted: both `REVISED_UP` events describe movement between stated ranges, never an achieved outcome or better credibility. Report any softer implication.
- R6, on FY26_Q2 and FY26_Q4: the three required elements; state whether the S1 finding closes.
- S2 C-12: does the note say honestly what the record cannot show, and give a real thesis consequence?
- `drivers`: reject a cause the evidence does not state.
- The rulings S2 listed (OD-1, OD-2, OD-5 to OD-9), and D1's explanation of the byte-identical sections.
- Points at the panel text's path and its SHA.

**S3 panel scope (recommended here, in force once Sol approves; every brief states it; the owner may overturn it).**
- **Materiality.** The owner's 2026-10-29 ruling named LIVE-RUN-1. S1 and S2 extended the treatment to their drafts; S3 would be a **third** extension: approvable with materiality disclosed as not built, S06 unchanged, A-10 open. Flagged in the handoff.
- **Drivers and thesis assessment** are now delivered, within C-7's limit. The panel judges them, rather than their disclosure.
- **Limits.** The approval is limited to the S3 demonstration. Forward scenarios are RESEARCH-4. A-04 and B-02 are not declared satisfied; `CORE_RESEARCH_RELEASE` stays NO.

Verification: four new `APPROVED` versions; all gates pass on each; the drill passed; `db check-live` exits 0 after every live write; every delta matches.

Dependencies: Tasks 1–3 committed, gate `ROUTE: PASS`, Sol's phase-end `APPROVE`, the frozen-expectations commit.

Risks:
- Permanent writes. A panel rejection is recorded and follows P6. Up to two Sol rounds each, and a rejected N+1 blocks that period's next run until recovered (F-6).
- Sol may find `drivers` too thin to approve under C-7. That is a real outcome, not a defect to prompt around: the orchestrator rules, per the stack's three-round rule, whether to park it with the reason recorded or open the evidence bead first.
- Sol at capacity: retry; never substitute (stack).

## Report disclosures (fixed, digit-free, code-built; S1 lesson 2)

| Id | Where | Sentence (implementer may tighten wording, not drop content; each must pass `scan_narrative`) |
|---|---|---|
| D1 | Top of `drivers`, `{{e:computed}}` | The sections above are the approved deterministic version this draft succeeds, unchanged, so their statements that no driver analysis, thesis-impact narrative, credibility judgment or analyst questions exist describe that version. The notes below were drafted by a model from the evidence bundle alone, which holds this version's claims and the quotes they cite, not the whole transcript: a cause management gave outside those quotes is absent, and absence here does not show that no cause exists. The model computes nothing: every number in these notes is a placeholder filled from a checked claim. |
| D2 | `credibility_notes`, no scored row, `{{e:computed}}` | No row reaches a scored outcome, so this record cannot show credibility rising or falling. A revision event states that a stated figure moved; it is neither an achievement nor better credibility. |
| Row | `credibility_notes`, `{{e:computed}}` | Each episode's metric, scope, last event, outcome, trend and `ref`. `NOT_ASSESSABLE` reads "no scored comparison". |

## Acceptance map (spec §5 S3, plus carried duties)

| # | Acceptance case | Proven by |
|---|---|---|
| A1 | Number words | Task 1 (a); `test_each_bad_draft_…` |
| A2 | `amount:123`, numbered item, decorations, style digit | Task 1 (a)(b); `test_each_bad_draft_…` |
| A3 | Unknown claim key | `test_each_bad_draft_…` |
| A4 | Location: other issuer; later disclosure; outside the package; eligible but not citable | `test_each_bad_draft_…` (C-4, C-5) |
| A5 | Narrate on `DRAFT`, `IN_REVIEW`, not head | `test_narrate_refuses_the_wrong_version` |
| A6 | Edited deterministic section; extra key | Task 1 (c); `test_each_bad_draft_…`; gate (b) |
| A7 | Bundle over the cap | `test_a_bundle_over_the_cap_refuses` |
| A8 | Full path; approval supersedes N | `test_full_path_…` |
| A9 | Span over the maximum absent and not citable | Task 2 |
| A10 | Rework gives no narrative, `AS_KNOWN`, narrates once approved | `test_rework_drops_the_narrative` (C-8) |
| A11 | The panel receives the bundle | `test_full_path_…`; `test_a_recorded_response_…` |
| A12 | Four Apar reports narrated, verdicts recorded, Sol `APPROVE` | Task 4 |
| A13 | **S2 C-12:** a sealed trend per episode from code; `RISING`, `FALLING`, `STEADY` on scored rows; `NOT_ASSESSABLE` plus D2 on Apar; a verdict refused without scores; a thesis-consequence paragraph per quarter, judged by Sol | Task 1 (d)(e); `test_the_c12_case`; Task 4 gate (d), brief |
| A14 | **R6:** a note due and present on FY26_Q2, FY26_Q4; content judged against Sol's three elements | Task 1 (f); Task 4 gate (e), brief |
| A15 | `drivers`, `risk_notes`, `credibility_notes`, `thesis_narrative`, `analyst_questions` present; notes on every `FLAGGED`, `MISSED`, `REVISED_*`, `BEHIND` row | `test_each_bad_draft_…`; gate (b)(e) |
| A16 | A rejected narrative's route and its gate | `test_a_rejected_narrative_…`; Task 4 drill, gate (f) |

## Open decisions

Each proceeds on the recommendation once Sol approves this plan (stack, "Autonomous approval"), and the owner may overturn.

| # | Decision | Recommendation |
|---|---|---|
| OD-1 | **The narrating model.** Spec §4 says "the configured client" and names none. The stack governs implementers and reviewers, not a report's model, so they do not conflict; its "three models, nothing else" is read as limiting the choice. | Claude Opus 5.5 through `ClaudeOpusClient`'s CLI path, `claude-opus-5-5`, named only in `config/narrate.yaml`. It is independent of the Sol panel; the CLI needs no new dependency. Args: `--tools ""` and `--setting-sources` with no project source, proven by the client probe. Not `settings.py`'s defaults, which are stale (`:27`, `:35`). Fallback if the probe fails: `use_api` with an injected key, which needs the `anthropic` package and a secret (owner-side setup). Effort is not configured; the CLI default applies unless a verified flag is added. |
| OD-2 | C-1's key `analyst_questions` | As recommended. |
| OD-3 | P3's trend rule, including interim outcomes counting as met or not met. A methodology choice, not a verdict on Apar. | As written. |
| OD-4 | A third materiality extension | As in Task 4. Flagged to the owner. |

**The owner's financial judgment, decided nowhere here:** whether management is credible; whether the thesis stands, weakens or changes; what a flagged ratio means for a position. `thesis_narrative`'s stance is a labelled draft opinion that the panel may approve as report text. It changes no thesis version, and the owner reads it and decides.

## Verification summary

- `uv run ruff check src tests/fundamentals`, `uv run ruff format --check src tests/fundamentals`, `uv run mypy --strict src`
- Before Task 1: the tests round, then `scripts/verify.sh red RESEARCH-3-S3 <nodes>`, every node red
- `VERIFY_SCOPE_BASE=$S3_BASE scripts/verify.sh gate RESEARCH-3-S3`, its `ROUTE:` line read on its own
- `wc -l` of every changed file: production ≤ 800 each and the budgets above; tests ≤ 800
- `git status` shows only the files in the file map

## Self-review

- **Spec coverage.** Spec §5 Work: CLI → Task 3; bundle and panel → Task 2; client → Task 3, OD-1; guardrails, scan, location eligibility → Tasks 1, 3; `NARRATIVE` rework skip → Task 3. Every acceptance case is in the map.
- **What has nobody named?**
  - The section-key collision → C-1. The false `not_performed` lines in N+1 → C-2, D1.
  - The model not seeing statuses or the thesis → C-3. Admission data absent from N → C-4. A cutoff that excludes nothing on retrospective runs → C-5.
  - The hash binding breaking on an appended bundle → C-9, P5. Proof that both calls read one bundle → P5.
  - `{{c:key}}` without a pipe → P4. Argv size and tools on the CLI → F-5, OD-1.
  - A rejected N+1 blocking the next run → F-6.
  - Hostile text in quotes → P7.
  - Follow-up beads to file at close: transcript evidence for `drivers` (C-7); trend remains unanswerable on Apar until a single-year quote or registered measure exists (Duty 1).
  - The status dashboard is refreshed by the orchestrator after each committed task (routine, not a plan task).
- **Certain, from code or a read at `f1bf13d7`:** every cited line; the live-base table; the CLI flags' existence in `claude --help` 2.1.314; the Linux argv limit is a kernel constant, not measured here.
- **Inferred:**
  - Prompt and bundle sizes, from export and thesis lengths; the bundle's own size is estimated.
  - Every trace operand mapping to a claim by digest; `unclaimed` covers a miss.
  - Claim equality on N+1, from F-1.
  - The line estimates.
- **Unverified, with where each is settled:**
  - That `--tools ""` plus `--setting-sources` removes tools and project instructions in `-p` mode, and how to pass "no sources": the client probe.
  - The lexicon's refusal rate on real drafts: rehearsal.
  - Whether Opus can write useful `drivers` from this evidence, and whether Sol approves them (C-7): rehearsal text, then the panel.
  - The later-disclosure and other-issuer fixtures' mechanics: the tests round, before red sealing.
  - No test, model or write command was run for this plan.
