# LIVE-RUN-1 report export gaps (eqos-dna.1) — Implementation Plan

Status: approved (GPT-6.1 Sol high, closing verification APPROVE, 2026-10-29; review rounds r1-r3 + closing r1-r2)

**Origin:** bead `eqos-dna.1`. The Sol panel returned `REQUEST_CHANGES` on `REPORT_VERSION:7`
(APARINDS FY26_Q2, brief `LIVE-RUN-1-A04-B02-v1`); its verbatim reply is
`scratchpad/live-run-1/live/responses/FY26_Q2.md`. The panel found no numeric error. Its six
findings concern only what the run draft's narrative shows and links. Requirements:
`docs/specs/equity-os-s06-output-materiality-falsifiers.md` (S06: lines 107-137 and 300-330),
`docs/specs/equity-os-s14-earnings-review-workflow-rework.md` (S14) and
`.claude/project/invariants.md` (invariant 7).

**Goal:** a fresh FY26_Q2 run draft whose narrative carries claim references, the taxonomy-drift
basis, qualified guidance horizons, separated falsifier wording and explicit
not-performed/open-questions sections, plus a tested path that retires version 7 through the
panel's `REQUEST_CHANGES` so the new version can go to the same panel.

**Out of scope:**
- Writing analyst content: forward scenarios, forensic checks, management-credibility tracking,
  a narrative thesis-impact assessment, or analyst-drafted open questions. Those are product
  register items A-04/B-02 (`.claude/project/brief.md`). Task 4 records only the questions the
  extracted data itself leaves open.
- A materiality engine (S06 policy, candidate claim inventory and per-claim decisions). It does
  not exist, and building it needs a spec and owner ruling (see "Finding 1" below).
- Any migration. Committed migrations are frozen, and no task needs a new one.
- Changing `ledger export` or the status note. Both already emit the stored narrative bytes;
  every fix lives in what the run draft stores.
- Inferring a guidance target period that the extraction did not capture.
- Imported versions (`import_mapping.py` narratives must still hash to their source bytes).
- A heading line naming version 7 as the superseded attempt. The chain is recorded in
  `predecessor_id` and shown by `ledger export --stock … --status-notes`.
- FY26_Q3 to FY27_Q1. They resume under the unchanged LIVE-RUN-1 step R once FY26_Q2 is
  `APPROVED`.

**Constraints:**
- "Every material numerical claim links to a fact ID or calculation trace; … every material
  factual claim resolves to an exact source location" (invariant 7).
- "Narrative numbers come only from claim placeholders: any other numeral blocks unless it is
  structural" (`src/fundamentals/ledger/numeral_scan.py:3-4`). New static text must have no
  numerals. That includes register ids such as A-04, which the structural regex does not
  cover.
- The narrative is the stored sections with placeholders filled. Its SHA-256 is the content
  hash, and the panel binds it (`src/fundamentals/ledger/display.py:98-106`,
  `src/fundamentals/ledger/recorded_reviewer.py:76-82`). The binding covers the narrative and
  sealed digest only, not the supporting files a panel brief points at (see L9).
- Owner rule (2026-10-14): the smallest change that meets the findings; reviews judge size.
- Every live write is permanent; live steps stop at the first deviation (LIVE-RUN-1 Task 5
  failure branch).

## Investigation findings

### Version 7 rework path (from the code)

**A new FY26_Q2 draft cannot be written while version 7 is `IN_REVIEW`.**
- `preflight` and `write_run_draft` both call `_require_closed`. It raises "head version … is
  open" when the period head's status is in `OPEN` (`src/fundamentals/ledger/run_draft.py:235`,
  `:302`, `:421-425`).
- `OPEN = {DRAFT, IN_REVIEW}` (`src/fundamentals/ledger/lifecycle.py:103`).
- After `SUBMIT`, the only legal decisions are `APPROVE`, `REQUEST_CHANGES` and `REJECT`
  (`lifecycle.py:67-70`; `migrations/0014_ledger_review_fixes.sql:117`).
- So version 7 must first be decided. `ledger panel` with the preserved `REQUEST_CHANGES`
  response records the real decider: the panel, with Sol's text as the rationale.

**`ledger panel` path.**
1. `_panel` parses the binding, checks that it names `REPORT_VERSION:7` and refuses a
   `rehearsal` provider off `eqos_test_*` (`src/fundamentals/api/ledger_cli.py:273-301`).
2. `panel.review` runs the version gate twice: head is `SUBMIT`, and a passing `AS_KNOWN`
   claim check. It maps the verdict to `DecisionKind.REQUEST_CHANGES`
   (`src/fundamentals/ledger/panel.py:48`, `:109-158`, `:187-196`).
3. `RecordedReviewer.review` refuses unless the digest and narrative SHA-256 match
   (`recorded_reviewer.py:76-82`).
4. A gate failure refuses before any row is written.

**State it leaves.**
- One `panel_reviews` row: verdict `REQUEST_CHANGES`, the whole response as the rationale, and
  responder fields as data (`panel.py:148-155`).
- One `decisions` row: decider `PANEL`, `panel_review_id`, `sealed_digest`, and
  `rejected_claims` NULL. `append_decision` passes no claims, and the store writes `() → NULL`
  (`store.py:193`, `:213`; the column check is `migrations/0039_rework.sql:5-7`).
- No validation row. `append_decision` inserts one only for `APPROVE` (`lifecycle.py:429`).
- Version 7 becomes `CHANGES_REQUESTED` (`lifecycle.py:98`). That state is terminal: every
  further decision is refused (`tests/fundamentals/test_ledger_integrity.py:343-346`).

**The rerun that follows.**
- `rework.rejected` returns `()` for a decision naming no claims, so `rework.plan` returns
  `None` (`src/fundamentals/ledger/rework.py:136-142`, `:211-215`).
- `preflight` therefore sets no rework (`run_draft.py:247-250`). `--full-successor` refuses,
  because it needs claim rejections (`run_draft.py:240-243`).
- The ordinary run writes a full fresh version with `predecessor_id = 7` (`run_draft.py:336`).
  The run re-binds the falsifier sections to thesis version 6 as before.
- `ledger submit` accepts it: its predecessor is `CHANGES_REQUESTED`, which is not `OPEN`
  (`lifecycle.py:160-168`).
- Once the new version is approved, the imported `HISTORICAL` root is superseded through the
  descendant chain (`lifecycle.py` `_STATUS`). Version 7 stays `CHANGES_REQUESTED`.

**Test coverage on PostgreSQL.**
- *Exercised.* The decision-row shape (a panel `REQUEST_CHANGES` with a review and no claims)
  is inserted only by direct store calls in the `rig` fixture
  (`tests/fundamentals/test_prep6_review.py:104-126`). That proves the triggers accept it.
- *Never exercised:*
  - `panel.review` or `ledger panel` with a `REQUEST_CHANGES` verdict.
    `test_ledger_panel_cli.py:128` covers `APPROVE`, and `:197` covers refusals.
    `test_ledger_panel.py` has only the unit verdict map (`:298`, case `:289`) and a
    direct-SQL refusal (`:406`, case `:420`).
  - A rerun after a claim-less `REQUEST_CHANGES`. The PREP-5 tests reject named claims
    through the owner (`test_prep5_rework.py:304-310`).
  - Reusing a quarter's staged manifest and intake store for a second operator run.
- Basis: grep restricted to test files containing `REQUEST_CHANGES`. Task 1 closes these gaps
  before any live write.

### Finding 1 — materiality: the records do not exist

- No materiality policy, candidate claim inventory or per-claim decision exists in code or
  schema. `grep -ril materiality src/ migrations/` matches only
  `src/fundamentals/verify/crossfoot.py:26`, a reconciliation-tolerance comment.
- S06 requires those records for `EarningsReviewOutputV0` (lines 129-130) and blocks approval
  without them (invariant 2, lines 315-321). The run draft is a ledger report version, not
  that contract.
- The panel cited `"ledger": null` (`FY26_Q2.json:1080`) as missing materiality evidence. That
  field is `EarningsUpdate.ledger`, an unused `ManagementLedger` slot
  (`src/fundamentals/output/earnings_update.py:192`), not a materiality record.
- **Smallest honest option (Task 4):** state in the narrative that no claim carries a
  materiality decision because this pipeline does not produce them.
- That disclosure does **not** satisfy S06 invariant 2. Whether a disclosed materiality gap is
  acceptable for this LIVE-RUN-1 record is a ruling, not a code question (see "Rulings
  needed").

### Data the pipeline already holds (findings 3 and 4)

- **Taxonomy drift.**
  - Each change carries `taxonomy_drift` (`src/fundamentals/contracts/comparative.py:46`). It
    is set only when the issuer config's comparator sets `accept_taxonomy_drift`
    (`src/fundamentals/api/run_comparatives.py:168-169`;
    `config/aparinds-fy26-q2.yaml:111`).
  - Both figures are bound under one canonical measurement key, `key.canonical_id`
    (`src/fundamentals/ledger/run_traces.py:327`, `:342`).
  - The existing Markdown renderer already words it as "taxonomy drift accepted: …"
    (`earnings_update.py:305-307`).
  - The run-draft line drops it (`run_traces.py:450-463`).
- **Guidance horizon.**
  - `GuidanceClaim.horizon` is a free string (`src/fundamentals/contracts/guidance_claim.py:41`).
    The APARINDS configs set only `annual` or `medium_term`.
  - No fiscal year or window is captured anywhere, so the horizon must be marked
    unspecified.

## File map

| File | Change | Task |
|---|---|---|
| `tests/fundamentals/test_ledger_panel_cli.py` | +1 PG e2e test: panel `REQUEST_CHANGES` → rerun → submit → panel `APPROVE` | 1 |
| `src/fundamentals/contracts/ledger.py` | `DisplayStyle.ref: bool = False` | 2 |
| `src/fundamentals/ledger/display.py` | `ref` token; `render_claim` renders the claim reference | 2 |
| `src/fundamentals/ledger/import_mapping.py` | `refs(keys)` beside `_slot` | 2 |
| `src/fundamentals/ledger/run_draft.py` | refs on results and guidance lines; horizon qualifier; `open_questions` and `not_performed` sections | 2, 3, 4 |
| `src/fundamentals/ledger/run_traces.py` | `Line.drift`; refs and drift note in `_shown`; `DISCLOSED` section keys | 2, 3, 4 |
| `src/fundamentals/ledger/falsifier_status.py` | observed/trigger wording; refs on falsifier lines | 2, 3 |
| `src/fundamentals/ledger/rework.py` | `plan` leaves the `DISCLOSED` sections out of the rework contract, as it does `DERIVED` | 4 |
| `tests/fundamentals/test_ledger_display.py` | `ref` rendering per citation kind | 2 |
| `tests/fundamentals/test_report_export_gaps.py` (new) | the new line formats and sections on one FY26_Q2 draft, and a selective rework of it. A new file, because `test_prep2b_run_draft.py` is already 755 lines and the gate routes CONTRACT on a hashed test file over 800 (`scripts/verify.sh:467-473`) | 2, 3, 4 |
| `tests/fundamentals/test_falsifier_status.py` | only assertions on line text that Task 3 rewords | 3 |
| `tests/fundamentals/test_prep5_rework.py` | contract-shape check (`:376`) skips `DERIVED \| DISCLOSED`; relabel regression (`:614`) expects the guidance line and its question to change | 4 |
| `tests/fundamentals/test_pilot_e2e.py` | section-order assertion (`keys[-3:]`, `sections[-2:]`) follows the new trailing sections | 4 |
| `scratchpad/live-run-1/f5_check.py` (gitignored, not committed) | exit 1 when any check fails | L1a, L6 |

Estimated total: about 75 source lines and about 165 test lines, plus three lines in the
scratchpad F5 helper.

## Tasks

### Task 1: Prove the claim-less panel REQUEST_CHANGES rework path on PostgreSQL

Goal: on an `eqos_test_*` database, the live sequence works end to end. `ledger panel`
`REQUEST_CHANGES` on a submitted FY26_Q2 version leaves the state described above. A second
operator run reuses the same staged manifest and intake store and writes a successor. That
successor submits, and `ledger panel` `APPROVE` approves it.

Files:
- Test: `tests/fundamentals/test_ledger_panel_cli.py`

Interfaces:
- Consumes: existing helpers in that file: `_operator`, `_ledger`, `_panel`, `_bound` and
  `_line(version_id, digest, sha, verdict)`. Also `version_status`, `store.read_version` and
  `pilot.query`.
- Produces: the proven live order and argv, which the live steps below mirror. If the
  manifest-reuse leg fails, the failure decides whether live re-stages (see Risks).

Approach:
- Split `_operator` into a stage part and a run part, or give it a `stage: bool` flag, so
  the second run reuses the first call's locator and store, exactly as live will.
- Sequence: operator FY26_Q2 → `submit` → `_panel` with a `verdict=REQUEST_CHANGES` binding
  line.
- Assert after the panel step:
  - exit 0;
  - the version is `CHANGES_REQUESTED`;
  - the decision row is `REQUEST_CHANGES` by `PANEL` with `rejected_claims` NULL;
  - the review row has verdict `REQUEST_CHANGES` and the response verbatim;
  - a second `_panel` on the same version refuses.
- Then run the operator again without re-staging, and assert the new version:
  - has `predecessor_id` equal to the first version;
  - has no "Full successor" heading line;
  - submits.
- Then `_panel` `APPROVE` on the new version. It becomes `APPROVED`; the first version stays
  `CHANGES_REQUESTED` with its sealed digest unchanged.
- This is a characterization test of existing code. If it fails, stop and debug before
  Tasks 2-4 (systematic-debugging), because the live path depends on it.

Verification: `uv run pytest tests/fundamentals/test_ledger_panel_cli.py -n 8 --dist loadfile`
→ all pass. Then `scripts/verify.sh gate` at the end of the plan.

Test seams: the `ledger` and `fundamentals-operator` CLI mains and the `eqos.decisions` /
`eqos.panel_reviews` rows read back through `pilot.query`.

Dependencies: None.

Size: S (one test of about 50 lines, one helper split). Implementer: Opus (PG e2e, lifecycle).

Risks:
- The second operator run may refuse a reused manifest or intake store. If it does, the test
  records the required re-stage (fresh `--source-admission-store` and `--out-manifest`), and
  live step L4 follows the test, not this plan's default.

### Red proof (after Task 1, before any source change)

The phase-end gate needs `scratchpad/gate/LIVE-RUN-1-gaps-red.json`. Without it the gate fails
CONTRACT (`scripts/verify.sh:365-369`). A refactor baseline cannot stand in: that route fails
on any added test (`:528-558`).

1. **Test round (Opus, tests only, no `src/` edits).** Write every test that Tasks 2-4 list,
   in their final form. That includes the edits to existing assertions whose text Tasks 3-4
   change (`test_falsifier_status.py`, the `test_pilot_e2e.py` section-order assertion, and
   the two `test_prep5_rework.py` assertions in Task 4).
2. **Record (orchestrator).**
   `scripts/verify.sh red LIVE-RUN-1-gaps <node id> …`. Pass only the node ids of new or
   changed tests that must fail before the source change: no whole files, because one
   already-passing collected test fails the proof (`:221-227`). No `-n`: the proof hashes the
   `tests/` modules loaded in its own process (`:132-149`). Expected: `red-proof OK n/n`.
   - A target that already passes is a contract gap: fix the test and record again.
   - `test_pilot_e2e.py`'s key-based assertion passes before the change, so it is not a
     target. Its edit still lands in step 1.
3. **Frozen from here.** The proof seals the SHA-256 of each target's file and of every
   `tests/` module the run imported, conftests and helpers included (`:196-214`). The gate
   fails `tests-untouched` if any of them changes (`:369-387`). Implementers of Tasks 2-4 are
   briefed "do not edit `tests/`". A test that turns out wrong is resealed only by the
   orchestrator (`scripts/verify.sh reseal`), with the reason recorded in the bead.

### Task 2: Claim references on every claim line (finding 2)

Goal: every line of the run draft that shows a claim also shows, for each claim, its key and
its stored citation. The citation is the kind plus every non-null locator field: source
SHA-256, capture ref, anchor, fact origin and id, interpretation id, calculation trace id, or
cited thesis claim id and digest. A reader can resolve each number from the narrative alone.

Files:
- Modify: `src/fundamentals/contracts/ledger.py`, `src/fundamentals/ledger/display.py`,
  `src/fundamentals/ledger/import_mapping.py`, `src/fundamentals/ledger/run_draft.py`,
  `src/fundamentals/ledger/run_traces.py`, `src/fundamentals/ledger/falsifier_status.py`
- Test (written in the red-proof test round): `tests/fundamentals/test_ledger_display.py`,
  `tests/fundamentals/test_report_export_gaps.py`

Interfaces:
- Consumes: `NumericClaim.citation` (`Citation` fields), `_slot(claim_key, style)`.
- Produces:
  - `DisplayStyle.ref: bool = False`. The style token is `ref`.
  - `render_claim(claim, style)` with `style.ref` returns
    `[<claim_key>: <KIND> <field>=<value>, …]`, over the citation's non-null fields in model
    order, excluding `kind` and `quote`.
  - `refs(keys: Sequence[str]) -> str` in `import_mapping.py` returns the space-joined
    `{{c:<key>|ref}}` placeholders.

Approach:
- Add `"ref": "ref"` to `display._FLAGS` and the field to `DisplayStyle`. When `ref` is set,
  `render_claim` returns the reference before any value formatting.
- Append ` ` + `refs(keys of the line's claims)` to each claim line:
  - `_results` and `_guided` in `run_draft.py`;
  - both branches of `_shown` in `run_traces.py` that hold claims;
  - each evaluated falsifier line, placed before the trailing status, so that lines still end
    with `HELD (not triggered)` / `WEAKENED (triggered)`.
- Lines without claims (unavailable changes, missing operands) get no refs.
- The references are placeholders, so `scan_section` removes them before its numeral search.
  The rendered digits never reach the scan.
- The rework `Gate` compares produced line text with the stored text. Both now carry refs, so
  reworks of new versions stay consistent.

Verification:
- `uv run pytest tests/fundamentals/test_ledger_display.py tests/fundamentals/test_prep2b_run_draft.py tests/fundamentals/test_report_export_gaps.py -n 8 --dist loadfile`
  → pass.
- A FY26_Q2 draft's rendered `results` line for `fact.revenue` contains `[fact.revenue: FIGURE`
  and its fact origin id.
- `ledger check` and `submit` still pass in the e2e: no `UNREGISTERED_NUMBER`.

Tests (behaviour, not shape):
- `ref` renders a `FIGURE`, `CALCULATION`, `SOURCE_QUOTE` and `THESIS_CLAIM` claim, with
  exactly that claim's non-null locators. One parametrized unit test.
- One run-draft assertion that every placeholder key on a claim line also appears there with
  `ref`.

Dependencies: the red proof (after Task 1).

Size: S-M (about 25 source lines). Implementer: Opus (touches the sealed narrative format).

Risks:
- `scratchpad/live-run-1/f5_check.py` check (d) compares placeholder styles against the
  rehearsal record. The `ref` style adds `ref` entries; live step L1a records a fresh one.
- A selective rework of a pre-change version would see moved lines. No such version has
  claim rejections on live today; Task 1's no-claim path does not use `plan`.

### Task 3: Drift basis, horizon qualifier, falsifier wording (findings 3, 4 and 6)

Goal:
- **Drift.** A change line whose comparison carries accepted taxonomy drift states it and its
  basis: "taxonomy drift accepted in the issuer config: <drift>; both figures read as
  <canonical id>".
- **Horizon.** A guidance line whose horizon is not a fiscal-period label states "target
  period not specified by the extracted guidance".
- **Falsifier wording.** A falsifier line reads "observed <value>; triggers when <operator>
  <threshold>: <STATUS> (<triggered|not triggered>)", so no sentence asserts the comparison.

Files:
- Modify: `src/fundamentals/ledger/run_traces.py`, `src/fundamentals/ledger/run_draft.py`,
  `src/fundamentals/ledger/falsifier_status.py`
- Test (red-proof test round): `tests/fundamentals/test_report_export_gaps.py`,
  `tests/fundamentals/test_falsifier_status.py` (only where it asserts line text)

Interfaces:
- Consumes: `change.taxonomy_drift`, `TAXONOMY_DRIFT_PREFIX`
  (`fundamentals.contracts.comparative`), `key.canonical_id` and `claim.horizon`.
- Produces:
  - `Line.drift: str | None = None`, set in `bind_computed` from `change.taxonomy_drift`
    (prefix removed) and `key.canonical_id`.
  - `_shown` appends the drift note to a change line with claims.

Approach:
- **Drift.** In `bind_computed`, pass the drift text and canonical id into the `Line` it
  builds for each change. `_shown` appends the note after the percent.
- **Horizon.** One predicate, `_specified(horizon) -> bool`, used by `_guided` here and by
  Task 4: true only when the horizon fully matches `FY\d{2,4}(?:_Q[1-4])?`. That is a fiscal
  year or an explicit fiscal quarter, the period-label forms `numeral_scan` already treats as
  structural (`src/fundamentals/ledger/numeral_scan.py:29`). A bare `Q3` or `H1`, which the
  scanner also accepts, names no fiscal year and stays unspecified. Any other horizon gets the
  unspecified note. Never derive a year.
- **Falsifier wording.** In `derived`, reword the evaluated-row line, and keep the "HELD (not
  triggered)" suffix that `tests/fundamentals/test_pilot_e2e.py:339` and the F5 helper regex
  rely on. Reword the section intro to match: "observed traced value, trigger condition
  (operator and thesis threshold), status".
- The drift text holds only dates and taxonomy names. Its numerals are dates, which the
  structural pattern covers. Task 1's FY26_Q2 e2e submits a drifted YoY line and so proves
  this.

Verification: the same pytest scope as Task 2, plus `test_falsifier_status.py` → pass.
- The FY26_Q2 draft's YoY revenue line contains "taxonomy drift accepted"; its QoQ line does
  not.
- The guidance lines contain "target period not specified".
- The F1 line contains "observed" and "triggers when below".

Tests:
- One run-draft assertion covers all three line texts on FY26_Q2.
- One parametrized unit check: `FY27` and `FY27_Q2` get no note; `annual` and `Q2` do.

Dependencies: Task 2. It edits the same lines, so it runs serially after Task 2.

Size: S (about 15 source lines). Implementer: Sonnet (decided wording, mechanical edits), or
fold into Task 2's Opus round to avoid a second pass over the same lines (recommended).

Risks: none beyond Task 2's.

### Task 4: Scope disclosures and outstanding open questions (findings 5 and 1)

Goal: every run draft ends with two sections.
- `open_questions` lists the questions the extracted data itself leaves open, in S06's
  open-question shape (`docs/specs/equity-os-s06-output-materiality-falsifiers.md:126`):
  question, why it matters, required evidence, owner/status. Only data the pipeline holds goes
  in; no analyst conclusion is written. Today that means one question per guidance claim
  whose horizon is not specified (Task 3's `_specified`):
  `- Which fiscal year or window does the <metric label> guidance cover? Why it matters: the
  guidance cannot be checked against an outcome period without it. Evidence required: the
  transcript context around the quoted guidance {{c:<key>|ref}}, or a later management
  statement naming the period. Status: open; owner not assigned.`
  The section intro says the pipeline drafts no analyst questions, so the list is not a
  finding that no other questions exist. With nothing outstanding, the section shows the usual
  `- none` under that intro.
- `not_performed` names what this version does not contain, as fixed lines:
  - forward scenarios;
  - forensic checks;
  - a management-credibility assessment;
  - a narrative thesis-impact assessment;
  - materiality decisions: no claim carries a materiality decision, because the pipeline
    produces no materiality policy, candidate inventory or per-claim decision.

Files:
- Modify: `src/fundamentals/ledger/run_draft.py`, `src/fundamentals/ledger/run_traces.py`,
  `src/fundamentals/ledger/rework.py`
- Test (red-proof test round): `tests/fundamentals/test_report_export_gaps.py`,
  `tests/fundamentals/test_pilot_e2e.py`

Interfaces:
- Consumes: `INTROS`, `section_body`, `_sections`, the guidance claims `_guidance` returns,
  `_specified`.
- Produces:
  - `OPEN_QUESTIONS, NOT_PERFORMED = "open_questions", "not_performed"` and
    `DISCLOSED = frozenset({OPEN_QUESTIONS, NOT_PERFORMED})` in `run_traces.py`, beside
    `CHANGES, CALCS`. `rework.py` already imports `run_traces`; it cannot import `run_draft`,
    which imports it.
  - `INTROS` gains both keys (each intro one `{{e:computed}}` paragraph, no numerals). Their
    lines are `_question(claim)` for each unspecified-horizon guidance claim, and a
    `NOT_PERFORMED` tuple. `section_body` is unchanged.

Approach:
- `_sections` emits every `INTROS` key except these two before the falsifier sections, and
  these two after them.
- **Rework: regenerated outside the contract.** Both sections are a pure function of the
  run's guidance claims, so every write regenerates them, as it does the derived falsifier
  sections. `rework.plan` builds the contract from
  `version.sections` minus `DERIVED` (`src/fundamentals/ledger/rework.py:227`). It becomes
  minus `DERIVED | DISCLOSED`; one docstring sentence (`rework.py:16-18`) names them too. Their
  claims need no filter: the sections own no claims, and a question's placeholder names a
  guidance claim (`display.narrative` renders every section against all the version's claims,
  `display.py:98-102`).
  - Why not feed them through the `Gate`: `gate_lines` sends only results and guidance
    (`run_draft.py:392-405`), and `bind_computed` only changes and calculations
    (`run_traces.py:432-436`). So `Gate.close` would rebuild each section from no recorded
    lines: `- none` against the stored questions, and an empty body against the fixed
    `not_performed` bullets (`rework.py:120-122`). Any selective rework of a new draft would
    refuse, including the existing guidance rework in
    `tests/fundamentals/test_prep5_rework.py:530`. Feeding the questions through `Gate.line`
    would also refuse, because each question repeats a guidance key already seen
    (`rework.py:94`). Participating would need a `Gate` change; leaving them out takes one
    set union.
  - The questions are built from the guidance claims `_guidance` returns
    (`run_draft.py:503-520`). A rework keeps each claim's key whether its line is carried or
    rerun (`rework.py:97-109`), so a rework's questions name the same keys as its guidance
    lines.
- The question's only placeholder is the claim's `ref` (Task 2), so it adds no numeral. The
  metric label already appears on the guidance line, so it adds no new numeral exposure.
- Text uses no register ids or spec numbers, which would trip `numeral_scan`.
- Update the RESEARCH-1 section-order assertion in `test_pilot_e2e.py` (lines 325-327) to
  locate `thesis_impact`/`observable_falsifiers` by key, not by position.

Verification: the same pytest scope, plus
`uv run pytest tests/fundamentals/test_pilot_e2e.py tests/fundamentals/test_prep5_rework.py -n 8 --dist loadfile`
→ pass.
- A FY26_Q2 draft ends with `## open_questions` and `## not_performed`, and `submit` raises no
  version-level state.
- Its `open_questions` holds exactly two questions, one per guidance claim (both horizons are
  `annual` or `medium_term`). Each names its metric label, carries its claim's `ref` and reads
  "Status: open".

Tests:
- One run-draft assertion on FY26_Q2: each unspecified-horizon guidance claim is an
  outstanding question with its ref and "Status: open", and `not_performed` names materiality.
  This proves that unresolved guidance stays visibly outstanding.
- Task 3's horizon unit check also asserts that a specified horizon yields no question.
- One selective-rework regression on a revised FY26_Q2 draft. Use the `submitted_q2`,
  `_request_changes` and `_successor` patterns of `test_prep5_rework.py`. The owner rejects one
  guidance claim, and the rerun succeeds. The successor's `open_questions` and `not_performed`
  bodies equal the predecessor's byte for byte, and the rejected claim's question is still
  there. It fails before Task 4 because the sections do not exist yet, so it is a red-proof
  target.
- The existing PREP-5 rework tests (`test_prep5_rework.py`) run on drafts that now carry both
  sections, so they also guard this. Two of their assertions change in the test round
  (orchestrator ruling on plan review r3):
  - the contract-shape check (`:376`) skips `DERIVED | DISCLOSED`, not `DERIVED` only;
  - the relabel regression (`:614`) requires exactly the guidance line and its question to
    change, consistently, with all other content unchanged.
  Every other assertion in the file stays unchanged and green.

Dependencies: Task 3 (`_specified`; same file; serial).

Size: S (about 25 source lines). Implementer: Opus (the rework contract is in scope).

Risks:
- Sol may still hold finding 1 under ruling (a). The code cannot close it.

### Phase end

`scripts/verify.sh gate LIVE-RUN-1-gaps` (ruff, format, `mypy --strict src`, full pytest at
8 workers) → pass. It needs the red proof above with every sealed test file unchanged. Then the
Sol phase-end review loop on the Tasks 1-4 diff (`.claude/rules/core/04-agent-stack.md`), and
a commit, before any live step.

## Version 7 rework: live steps (orchestrator, in order)

Environment and paths are LIVE-RUN-1 Task 5's (`scratchpad/live-run-1/live-scratch/lq.sh`):
`R=scratchpad/live-run-1`, `OUT=$R/live`, `$SNAP`, `$CFGS`, `$LOC`, `$INTAKE`, `$THESIS6`, and
`X` (runs on `equity_os`).
- The rehearsal adds `RR=$R/rehearsal-r2` and `XR`, which is `X` with
  `EQOS_PG_DB=eqos_test_live2`.
- A counts file follows every write step, on live and in the rehearsal. Each live delta must
  equal the rehearsal's delta for the same step. Exception: an L10 `REQUEST_CHANGES` or `REJECT`
  has no rehearsal delta; it is a stop-and-rule outcome.
- `db check-live` also follows every live write step. It runs on live only, because it refuses
  `eqos_test_*` databases (`src/fundamentals/api/db_cli.py:136`). In the rehearsal, run a copy
  of `$R/rehearsal-scratch/check0042.py` instead: it calls `check_live` directly on the named
  `eqos_test_*` database. Its `migrations_dir` is `migrations/`, the same directory live's
  `db check-live --migrations-dir` uses (`live-scratch/lq.sh`). Live was migrated 0042 -> 0045
  on 2026-10-29 (owner ruling; backup c0d7d1cb0f2d42b9b274c368b75cc079 taken first).
- Stop at the first deviation; never re-run a write step that partly committed.
- Version 7's files (`$OUT/out/FY26_Q2.json`, `FY26_Q2.md`, `FY26_Q2-v7.md`,
  `$OUT/logs/*-FY26_Q2.*`, `$OUT/responses/FY26_Q2.*`) stay where they are, unchanged. Every
  successor artifact gets a fresh `-r2` or `-v<v8>` name.

- **L0. Preconditions (read-only).**
  - Tasks 1-4 are committed with Sol `APPROVE`; the gate passed.
  - `db check-live` passes.
  - Fresh counts and digests are recorded.
  - Version 7 is still `IN_REVIEW`.
  - `uv run fundamentals ledger export 7` hashes to the `narrative_sha256` in
    `$OUT/responses/FY26_Q2.md`'s `EQOS-BINDING` line. This proves the binding still names
    the stored bytes.
- **L1. Verdict file.** Write `$OUT/verdicts/FY26_Q2-v7.json` with exactly `provider: codex`,
  `model: gpt-6.1-sol`, `effort: high` and `brief_version: LIVE-RUN-1-A04-B02-v1`.
- **L1a. Rehearse L2-L8 and an L10 approval on a restored copy (no live write).**
  - *Helper.* `f5_check.py` prints `FAIL` but exits 0 (`f5_check.py:116-122`). Change it to
    exit 1 when any check printed `FAIL` (scratchpad, about three lines). The printed lines
    stay the authority; the exit status is a backstop.
  - *Restore.* `eqos_test_live2` and `$RR` must not exist.
    - Create `$RR` and `$RR/{out,logs,counts,verdicts,responses,locators}`, all with mode 700
      (`mkdir -m 700`).
    - Run `X fundamentals db backup --out $RR/set --snapshot-root $SNAP`, which reads live.
      Save the path from its `published\t<path>` line as `SET`
      (`src/fundamentals/api/db_cli.py:152`). Backup publishes into `$RR/set/<backup-id>`
      (`src/fundamentals/pg/backup.py:266`), and restore reads the manifest directly inside
      `--set` (`backup.py:448`).
    - Run `X fundamentals db restore --set $SET --database eqos_test_live2 --snapshot-root $RR/root --live-snapshot-root $SNAP`.
      This is the LIVE-RUN-1 rehearsal form (`docs/plans/LIVE-RUN-1-prerequisites.md:611-614`).
      `--backup-dir` defaults to the set's parent, `$RR/set`. It runs through `X`, not `XR`:
      the restore name guard (`backup.py:330` → `test_databases.py:38`) refuses when the
      configured database matches the `eqos_test_` prefix. Use `XR` only after this restore.
    - Copy with `cp -a $LOC/FY26_Q2.json $RR/locators/` and `cp -a $INTAKE $RR/intake`. That
      takes the complete intake tree, `.source-intake` included, and keeps its private modes.
      Check that `find . -printf '%m %P\n' | sort` gives the same output in `$INTAKE` and in
      `$RR/intake`.
    - This copy is what proves that the locator and intake store work from a new root. Task 1
      reuses the same root, so it cannot prove that. If Task 1 proved a re-stage necessary,
      re-stage into `$RR` with step R's stage argv instead.
  - *Run.* Use `XR`, `SNAP=$RR/root`, `LOC=$RR/locators`, `INTAKE=$RR/intake`, and
    `$RR/out`, `$RR/logs`, `$RR/counts` and `$RR/verdicts`. Run L2, L4, L5, the F5 command below, L7, L8 and the approval
    rehearsal below with the live argv.
    - L2 uses `$RR/verdicts/FY26_Q2-v7.json`, labelled `provider: rehearsal` (the panel CLI
      accepts it only on `eqos_test_*`), with the real `$OUT/responses/FY26_Q2.md`. The
      restore keeps version 7's digest and narrative, so the binding holds.
    - Record counts (`counts.py … eqos_test_live2`) and the delta of each write. These deltas
      are the expected live deltas.
  - *F5 rehearsal.* The qualifiers file must not exist yet; the helper records it.
    `XR python $R/f5_check.py --db eqos_test_live2 --version <r8> --thesis-digest $THESIS6 --qualifiers $RR/qualifiers-FY26_Q2-r2.json > $RR/logs/f5-FY26_Q2-r2.log 2>&1`
    - Passes only when the exit status is 0 and the log is exactly `(a) pass`, `(b) pass`,
      `(c) pass`, `(d) recorded`, `(e) pass`, `status HELD`.
  - *Compare.* Compare the new file with version 7's `$R/rehearsal/qualifiers-FY26_Q2.json`.
    - For `etr` and `f5`, `qualifiers` are equal.
    - `styles` differ only by added `ref` entries: one per line that shows the ETR claim, and
      one for `thesis.F5`.
    - Record the diff in the bead.
  - *Approval rehearsal (write, `eqos_test_live2` only).* After the rehearsal export (L8,
    `N=sha256` of `$RR/out/FY26_Q2-v<r8>.md`), record a successor approval as
    `rehearsal-scratch/approve.sh` does:
    - `$RR/verdicts/FY26_Q2-v<r8>.json` with exactly `provider: rehearsal`, `model: none`,
      `effort: none`, `brief_version: LIVE-RUN-1-rehearsal`.
    - `$RR/responses/FY26_Q2-v<r8>.md`: one line saying it is an orchestrator-written rehearsal
      response, then exactly
      `EQOS-BINDING subject=REPORT_VERSION:<r8> sealed_digest=<rd8> narrative_sha256=<N> verdict=APPROVE`.
    - Run L10's argv through `XR` with those two files → `decision\t<id>`.
    - Record its counts delta and, read-only, the resulting statuses (`<r8>` `APPROVED`,
      version 7 `CHANGES_REQUESTED`). L10's live `APPROVE` is checked against both.
  - *On any failure* (exit status, delta, printed line or comparison): stop, with no live
    write. Diagnose (systematic-debugging) on a fresh restore (`eqos_test_live3`, …), never on
    live. A code fix re-enters the phase (gate and Sol) before L1a reruns.
  - Keep `eqos_test_live2` until L10, then drop it:
    `$R/venv.sh env EQOS_PG_DB=postgres uv run --no-sync python $R/rehearsal-scratch/drop.py eqos_test_live2 > $RR/logs/drop.log 2>&1`.
    `drop.py:11` asserts the configured database is neither `equity_os` nor `eqos_test_*`, so
    neither `X` nor `XR` can run it. `postgres` is the maintenance database it connects to anyway
    (`test_databases.py:22`). The earlier rehearsal's invocation was not recorded
    (`$R/rehearsal/logs/drop.log` holds only the before/after lists, and the prerequisites plan
    says only "drop the rehearsal DB"). Pass: `after` lacks `eqos_test_live2`.
- **L2. Retire version 7 (write).** Run
  `uv run fundamentals ledger panel 7 --verdict $OUT/verdicts/FY26_Q2-v7.json --response $OUT/responses/FY26_Q2.md --stock APARINDS --snapshot-root $SNAP $CFGS`.
  - Expected output: `decision\t<id>`.
  - Read-only probe: version 7 `CHANGES_REQUESTED`; the decision is by `PANEL` with
    `rejected_claims` NULL; the review verdict is `REQUEST_CHANGES` and its rationale equals
    the file bytes.
  - Counts delta: exactly `decisions +1`, `panel_reviews +1`.
- **L3. Output preflight.** None of the following exists. `ledger export` overwrites its
  destination (`ledger_cli.py:359`), so this fresh-path preflight is what keeps evidence intact.
  - `$OUT/out/FY26_Q2-r2.json` and `$OUT/out/FY26_Q2-r2.md`;
  - `$OUT/out/FY26_Q2-v*.md` other than `-v7.md`;
  - `$OUT/logs/*-FY26_Q2-r2.*`;
  - `$OUT/responses/FY26_Q2-v*` and `$OUT/verdicts/FY26_Q2-v*` other than `-v7`.
- **L4. Rerun (write).** Repeat the step R `fundamentals-operator run` argv unchanged (same
  `--source-admission-manifest $LOC/FY26_Q2.json`, `--source-admission-store $INTAKE`,
  `--retrospective $RM` and `--compare-run <n>`), except for
  `--out-json $OUT/out/FY26_Q2-r2.json --out $OUT/out/FY26_Q2-r2.md`. Logs go to
  `$OUT/logs/run-FY26_Q2-r2.{out,err}`.
  - Expected: `run_draft_written version=<v8>`.
  - Re-stage first only if Task 1 proved it necessary.
  - Probe: `<v8>`'s `predecessor_id` is 7.
- **L5. Check (write).** `ledger check` commits one validation and its claim states
  (`ledger_cli.py:254-262`, `lifecycle.py:176-202`).
  - Run once:
    `X fundamentals ledger check --version <v8> --stock APARINDS --snapshot-root $SNAP $CFGS > $OUT/logs/check-FY26_Q2-r2.out 2> $OUT/logs/check-FY26_Q2-r2.err`.
  - Expected delta: exactly `validations +1` and `validation_claim_states +<the rehearsal's
    L5 count>` (one per claim; version 7's check added 54).
  - Save the validation id from the first output line, `validation\t<id>`.
  - Post-write checks:
    - check-live passes and the delta matches;
    - a read-only probe shows the saved id is the latest validation of `<v8>`;
    - every claim is `MATCH` or `MATCH_UNTRUSTED`, with guidance quotes bound.
  - Never rerun it: each run appends another permanent validation. If the log is lost or
    truncated, the counts delta shows whether the check committed. If it did, rebuild the log
    read-only from that validation's `validation_claim_states`, including version-level states
    (`f5_check.py`'s `_STATES` query excludes those; see `ledger/store.py:264`).
- **L6. F5 gate (read-only).**
  `X python $R/f5_check.py --db equity_os --version <v8> --thesis-digest $THESIS6 --qualifiers $RR/qualifiers-FY26_Q2-r2.json > $OUT/logs/f5-FY26_Q2-r2.log 2>&1`
  - Passes only when the exit status is 0 and the log is exactly `(a) pass` through
    `(e) pass` and `status HELD`. Check (d) now compares against the record L1a made.
  - On failure: stop before L7. `<v8>` stays `DRAFT`, and that open head blocks every rerun of
    FY26_Q2 (`run_draft.py:421-425`). `WITHDRAW` is illegal on `DRAFT`
    (`src/fundamentals/ledger/lifecycle.py:71`; `migrations/0014_ledger_review_fixes.sql:119`).
    **Orchestrator ruling (2026-10-29):** close the head through the lifecycle, never around
    it. The panel route below works only while the lifecycle gates pass: submit's version-level
    scan (`lifecycle.py:168`) and the panel's `AS_KNOWN` check before any verdict
    (`panel.py:187-193`, `passes` at `lifecycle.py:228`). Tell the two cases apart in this
    order, from outputs already captured:
    1. L5's `$OUT/logs/check-FY26_Q2-r2.out` and post-write probe: every claim `MATCH` or
       `MATCH_UNTRUSTED` and no version-level state. Otherwise it is a gate failure.
    2. `$OUT/logs/f5-FY26_Q2-r2.log`: which of (a)-(e) failed. With step 1 clean, this is an
       F5-only failure.
    3. L7's submit: `sealed_digest\t<d8>`. A refusal naming states is a gate failure.
    4. L10's panel: a refusal before the verdict is recorded is a gate failure.

    *F5-only failure* (gates pass):
    1. Diagnose read-only first (systematic-debugging, on a fresh restore, never on live).
    2. Submit `<v8>` (L7's argv) and export it (L8).
    3. Run a fresh Sol panel round (L9's form, new `clientRequestId`). The brief states the
       failing F5 result and points at `$OUT/logs/f5-FY26_Q2-r2.log`.
    4. Its `REQUEST_CHANGES` or `REJECT` closes the head through `ledger panel` (L10's argv).
       If it returns `APPROVE` despite the failing F5, stop: the orchestrator rules before any
       further write.
    5. A code fix re-enters the phase (gate and Sol) before L1a reruns for the next version.

    *Gate failure* (any of steps 1, 3 or 4, at L5 through L10): stop, with no further write.
    `<v8>` stays `DRAFT` (before or at a refused submit) or `IN_REVIEW` (at a refused panel),
    and it blocks every successor of FY26_Q2. No negative-verdict path or owner-rejection
    route exists, and none is built. The orchestrator makes an incident ruling. This is
    acceptable because L1a ran the same steps on a restore of live taken at L1a, so a gate
    failure on live is out of band: it means live diverged from the rehearsal.
- **L7. Submit (write).** Run `ledger submit <v8> …` → `sealed_digest\t<d8>`.
- **L8. Export.** Run `ledger export <v8> --out $OUT/out/FY26_Q2-v<v8>.md`; record
  `N8=sha256`.
- **L9. Panel round (fresh `delegate_task`, new `clientRequestId`).**
  - Render `panel-brief.txt` with `V=<v8>`, `Q=FY26_Q2`, `D=<d8>` and `N=N8`. Then replace
    exactly three evidence paths:
    - `live/out/FY26_Q2.json` → `live/out/FY26_Q2-r2.json`;
    - `live/logs/check-FY26_Q2.out` → `live/logs/check-FY26_Q2-r2.out`;
    - `live/logs/f5-FY26_Q2.log` → `live/logs/f5-FY26_Q2-r2.log`.
  - Save the result as `$OUT/responses/FY26_Q2-v<v8>.brief.txt`. Before dispatch, check that
    it names none of the three version 7 paths, and that each of the three new paths exists
    and is non-empty. The narrative path `live/out/FY26_Q2-v<v8>.md` is already fresh.
  - *Unpublished-JSON variant.* Applies only when L4 took the inherited recovery: the draft
    committed and JSON publication failed (`cli.py:730`; `LIVE-RUN-1-prerequisites.md:722-730`),
    so `$OUT/out/FY26_Q2-r2.json` does not exist and is never regenerated.
    - Replace the brief's JSON line (`panel-brief.txt:9`) with: "The run's structured JSON
      output for this version was not published: the draft committed before the JSON write
      failed. The narrative file above is the exact ledger export of this version and is the
      subject of review."
    - The check and F5 replacements stay as above; their logs are the preserved validation and
      F5 evidence.
    - The existence check then requires the two log paths and that narrative, names none of
      the three version 7 paths, and contains the replacement sentence. Version 7's JSON is
      never substituted.
    - Not rehearsed: it cannot be induced without fault injection, and it is a text
      substitution.
  - Append version 7's six findings verbatim and the list of fixes, per the agent-stack
    re-review rule.
  - Under ruling (a), add the materiality sentence to the brief's "Known context" (see below).
  - Send that saved brief. Save the reply to `$OUT/responses/FY26_Q2-v<v8>.md` and its task id
    to `.task`.
  - Write `$OUT/verdicts/FY26_Q2-v<v8>.json`.
- **L10. Decide (write).** Run
  `ledger panel <v8> --verdict $OUT/verdicts/FY26_Q2-v<v8>.json --response $OUT/responses/FY26_Q2-v<v8>.md …`.
  - On `APPROVE`: the counts delta equals L1a's approval-rehearsal delta, and a read-only probe
    shows `<v8>` `APPROVED` and version 7 `CHANGES_REQUESTED`, as L1a recorded. Then step R
    continues with FY26_Q3.
  - On `REQUEST_CHANGES`: the orchestrator rules before any further write. Repeating L1-L10
    adds another permanent version.

## Rulings needed

**Orchestrator rulings (2026-10-29):** 1 → (a). The brief's new sentence states the fact (no materiality
records exist in this build); it does not ask the panel to excuse it, and the panel may still withhold approval. 2 → recorded as an
open question for the A-04 register owner (bead note on `eqos-dna.1`); LIVE-RUN-1 does not decide it.

1. **Materiality (finding 1).** Code cannot meet S06 invariant 2: no materiality records exist.
   - (a) **Recommended.** Treat materiality as part of the disclosed A-04 product gap for
     LIVE-RUN-1, as the brief already does for analyst content. Task 4 discloses it in the
     narrative, and brief v1 gains one "Known context" sentence that materiality decisions are
     not built. Record the ruling and the brief change in the bead, because the brief is then
     no longer byte-identical.
   - (b) Build the S06 materiality engine first: a spec, a migration and new contracts. That
     work is large and blocks LIVE-RUN-1.
   - (c) Keep brief v1 unchanged and accept the risk that Sol repeats finding 1.
   - Under `04-agent-stack.md` the orchestrator may rule (a). It is not a financial decision,
     but it narrows a spec invariant, so the owner may prefer to make it.
2. **S06 applicability.** Should a LIVE-RUN-1 run draft be held to `EarningsReviewOutputV0`
   at all? Its `PROVISIONAL_V0` contract is not what the run draft implements. Ruling (a)
   discloses the gap and does not answer this. It stays open for the A-04 register owner.

## Self-review

- **Coverage.**
  - Finding 1 → Task 4 and ruling 1.
  - Finding 2 → Task 2.
  - Findings 3, 4 and 6 → Task 3.
  - Finding 5 → Task 4: the disclosure plus the outstanding guidance-period questions.
  - The rework-path question → the investigation findings and Task 1.
  - The live sequence → L0-L10, rehearsed in L1a.
- **Plan review r1 (`scratchpad/dna1-plan-review-r1.md`).**
  - Successor evidence paths → the live-steps preamble, L3 and L9.
  - F5 rehearsal → L1a and L6.
  - Red proof → "Red proof" and Phase end.
  - Open questions → Task 4.
  - L5 is a write → L5.
  - Stale references → Constraints and the investigation findings. Every file:line in this
    plan was re-checked against the main checkout on 2026-10-29.
- **Gaps named.**
  - The `f5_check.py` record drift → L1a records a fresh record; L6 compares against it.
  - Artifact no-clobber → L3.
  - Manifest reuse → Task 1, L1a and L4.
  - The section-order assertion in the pilot e2e → Task 4.
  - Test-file size cap → a new test file.
  - Selective rework of pre-change versions → Task 2 Risks.
- **Plan review r2 (`scratchpad/dna1-plan-review-r2.md`).**
  - New sections and selective rework → Task 4 Approach (regenerated outside the contract)
    and its rework regression test.
  - L1a restore path → L1a *Restore*, plus the prerequisites plan's restore line.
  - Full intake copy, created directories → L1a *Restore*.
  - `check-live` refuses test databases → the live-steps preamble.
  - Explicit quarter labels → Task 3 `_specified`.
  - S06 applicability left open → ruling 2.
  - `DRAFT` head after a live F5 failure → L6's failure branch.
- **Closing review r1 (`scratchpad/dna1-plan-closing-r1.md`), as ruled.**
  - F5 branch vs lifecycle gates → L6: the check order, the F5-only route, and the gate-failure
    stop (no new closing route).
  - Restore refused under `XR` → L1a *Restore* runs through `X`; `drop.py`'s environment →
    L1a's drop line.
  - No rehearsal delta for L10 → L1a *Approval rehearsal*, checked in L10.
  - Unpublished JSON → L9's variant (not rehearsed).
  - No code estimate change: all four are procedure.
- **Unverified.** `drop.py` under `EQOS_PG_DB=postgres` is inferred from `drop.py:11` and
  `check_test_db_name` (`test_databases.py:46-55`), not from a recorded run. Whether the copied locator and intake tree work under `$RR`. Static
  inspection supports it: the locator and installed-receipt identities hold capture
  coordinates and hashes, not the intake-root path. L1a's copy proves it, and L1a stops before
  any live write if it fails.
- **No migration, no export change.** The fixes are in the stored sections, so `ledger export`
  and the content hash carry them unchanged.
