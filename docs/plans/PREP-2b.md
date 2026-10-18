# PREP-2b Implementation Plan — the run writes its earnings update as a ledger draft

**Origin:** `docs/backend-roadmap.md` §3 PREP-2 and §4 PILOT-4; beads `eqos-4j2.17` and
`eqos-4j2.18` (folded in as Task 1); `docs/plans/PREP-2.md` "Split out — PREP-2b" (carried
PREP-2 r1 F2–F12); D3 plan. r3 2026-10-18: Sol r1, r2 REVISE; r3 **APPROVE** (GPT-6.1 Sol, 2026-10-18).
**Goal:** each PostgreSQL `fundamentals run` of an Apar quarter reads its guidance prior from the
predecessor quarter's approved head and writes one `DRAFT` earnings-update version holding every
material number the emitted update retains — reported figures, comparator figures, QoQ/YoY
changes, §9 calculations, guidance — each bound to a fact, interpretation or calculation trace
(guidance: its source quote), so a real submit → check → approve works. For the four pilot
quarters this is a **retrospective workflow demonstration** (contract below).
**Out of scope:** a `ledger submit` CLI; the pilot's operational runs; guidance first stated in
a quarter no sealed import covers (ruling 4); a general trace subsystem; SQLite runs (no draft).
**Constraints:**
- Every task leaves `uv run pytest tests/fundamentals`, `uv run mypy --strict src`, `uv run ruff
  check src tests` green; test adaptations live in the task that changes the interface (F12).
- No migration edits or additions; nothing under `data/` edited; tests on `eqos_test_*` only.
- `config/aparinds-fy26-q4.yaml` stays byte-identical (frozen pin, old cutoff); pilot Q4 uses `-pg`.
- Do not touch `evidence/vendor_ingest.py`, hashed extractors, `compare/resolve_loader.py`,
  `pg/legacy_import.py`, `contracts/source_catalog.py`; do not fork `ledger/import_mapping.py`.
- Invariant 7: every material number links to a fact id or trace. Never backdate any time.

## Findings that shape the design (verified in code)

1. **Run facts post-date the cutoff:** `knowledge_time = completed_at` (`source_admission.py:404-422`),
   counted in every mode (`claim_check.py:30,89-94`) → two cutoffs (ruling 1, F3).
2. **No proof of historical possession exists for any Apar original (F4).** Admission needs
   `max(acquired, first_seen, registered_at) ≤ cutoff` (`source_admission.py:314-326`), all
   stamped `_utc_now()` (`api/source_intake.py:112-124`); the pinned `retrieval-manifest-v2.json`
   shows every original retrieved 2026-09-06/07; `filed_at_nse` is publication, not possession.
3. **Config cutoffs are 5h30 late (eqos-4j2.18).** Each non-frozen `knowledge_cutoff` is the
   transcript's `filed_at_nse` labelled `Z`; NSE wall time is Asia/Kolkata
   (`evidence/capture_intake.py:128-133`, `parse_filed_at`).
4. **Trace operands are interpretations only** (`citations.py:106-124,321-331`); interpretation
   `FIGURE`s resolve only inside a D1 run (`:184-188`). Only ETR has a registered formula;
   `conclude` stores cross-period operands as `DURATION` rows (`period_aggregation.py:115-128`)
   and only packages a given result (`canon/formula.py:490`).
5. **The other-income gap is emitted truncated:** `pipeline_steps.py:242` renders
   `int(other_income)` (FY26_Q4 19.72 → 19, FY27_Q1 33.65 → 33).
6. **Guidance binds only through sealed imports (M9)** (`citations.py:126-140`); all four pilot
   quarters are sealed imports, so run quotes at the same location bind with no code change.
7. A run draft is the next version on the imported report (`store.py:84`); runtime inserts need
   `READ COMMITTED`, watchlist, bootstrap and a WATCHLIST lock (`0026:80-111`).
8. `translate` ignores the issuer (`role_translation.py:37-56`); run facts carry `nse-symbol`/`APARINDS`.
9. Memory retrieval filters by actual store time (`memory/retrieval.py:49`): records made now are
   invisible at any historical cutoff.

## Retrospective contract (Sol r2 ruling on decision 8)

The pilot is a retrospective workflow demonstration. It cannot prove historical possession or
absence of hindsight.
- **(a) Selection ≠ knowledge time.** The source cutoff selects the historical package: only the
  config-pinned, reviewed originals of the quarter, the comparator XBRL and captures the approved
  prior cites, each published (`filed_at_nse`, IST-parsed) at or before the source cutoff. Later
  publications, restatements and later-quarter information are refused.
- **(b) Honest times.** Actual acquisition, registration, extraction, selection, approval and
  promotion times are kept. `--retrospective` waives only historical-possession eligibility, only
  for verified registered originals; identity, hash, rights, completeness and future-time
  (`bound ≤ now`) checks stay.
- **(c) Labelled.** The designation and both cutoffs persist in the sealed version content
  (heading) and in the emitted Markdown and JSON (`retrospective`, `source_cutoff`,
  `derivation_cutoff`); admissions record `mode="retrospective_registered"`.
- **(d) Approval unchanged.** Ordinary admission unchanged; AS_KNOWN approval checks the honest
  derivation cutoff; RETROSPECTIVE validations cannot bind approval (`lifecycle.py:131`).
- **(e) Memory and manifest.** Positive retrieval at actual sequential evaluation boundaries
  (after prior promotion, later events excluded); separately, historical source cutoffs exclude
  every newly created record (test 6). Task 2 amends pilot scope, PILOT-5, PREP-7.

## Design decisions

- **Two cutoffs (ruling 1).** Version `knowledge_cutoff` = the run's completion instant
  (derivation cutoff; exact, aware). The quarter's corrected exact cutoff is the **source
  cutoff**. Before insert, every capture behind every claim (carried included, F3) passes the
  set check and the source-time check: ordinary — first seen ≤ source cutoff; retrospective —
  published ≤ source cutoff per contract (a). Both cutoffs in the heading.
- **FIGURE claims cite the run's selected native fact rows**, resolved in `citations._fact` after
  verifying the fact's issuer against the report's entity (F2). Unselected rows resolve with no
  `SELECTED` time and fail `POST_CUTOFF`, so the writer cites only selected revisions (F10).
- **Comparator figures and computed values bind through interpretations (ruling 2).** A
  `FIGURE` with an `interpretation_id` and no `run_id` resolves the interpretation's own value,
  key and input times. Each computed value is a `calculation_traces` row: the result is computed
  from the resolved operands, then packaged by `conclude` and stored by
  `EvidenceRepository.put_calculation_trace`; the writer refuses unless it equals the run's
  value. Keys follow D3's computed-key convention (`import_mapping._key`/`computed`, made public).
- **Formulas (decision 7, accepted).** Three code-side formulas in `run_traces.py`, version `1`,
  no dictionary v3; ETR reuses registered `effective_tax_rate_pct`/`1`. ₹ crore `Decimal`, exact,
  resolved operands unrounded, `EQUIVALENCE_UNPROVEN`. `run.difference` a − b (gap: total income −
  revenue, same period; QoQ/YoY absolute: current − prior); `run.sum` a + b (headline PBT: PBT +
  associates, same period); `run.change_pct` (a − b) / b × 100, a current, b prior, at
  `PERCENT_CONTEXT_PRECISION` (`comparatives.py:241`), b = 0 → no claim (`REASON_PRIOR_ZERO`);
  ETR tax / PBT × 100 quantized 0.01 (`pnl_lines.py:38`), PBT = 0 refuses (`pipeline_steps.py:230`).
- **Prior = predecessor's head, `APPROVED` only (ruling 3)**, pinned by id + sealed digest.
- **Write-time order (F5, F6):** one `READ COMMITTED` transaction locks WATCHLIST(entity) then
  REPORT_VERSION(prior), re-reads predecessor head, `APPROVED` status, digest and current head (not
  open). Decisions take only REPORT_VERSION; runtime inserts take WATCHLIST first: no cycle.
- **Validate inside the draft transaction (F7, ruling 5):** after `store.create_version`, run
  `scan_section` and `lifecycle.check_version(AS_KNOWN)` on the same cursor; any non-`PASSING`
  claim or version state raises and rolls back.
- **Preflight before the pipeline (F8, ruling 6):** refuse before any fact write when the prior is
  unusable, the current head is open, or a required original (XBRL, results PDF, transcript,
  comparator XBRL) lacks a first-party capture, catalog entry, snapshot or mapped interpretation.
  A later concurrent change refuses at write time; the run's facts persist (append-only), no version.
- **Narrative:** heading (designation, both cutoffs, first-seen times, prior `version:<id>` +
  `digest`), results, comparatives, calculations, guidance; `{{e:…}}` placeholders. Reused, not
  forked: `import_mapping` keys, `UNITS`, `quote_qualifiers`, `content_hash`, `format_crore`.

## Size (estimates, not measured)
| Task | src Δ | tests Δ |
|---|---|---|
| 1 four config cutoffs; `test_prep2b_cutoffs.py` | 4 lines | +40 |
| 3 `ledger/citations.py` native FIGURE + issuer | +30 | +70 |
| 4 `ledger/run_traces.py` (new), `citations.py`, `import_mapping.py`, `pipeline_steps.py` | +150 | +130 |
| 5 `api/source_admission.py`, `cli.py`, `cli_parser.py` (retrospective) | +45 | +60 |
| 6 `ledger/run_draft.py` (new), `cli.py`, `pipeline.py`, emitters; stage-2 fixture | +240 | +380 |
| 7 delete JSON ledger (`pipeline*.py`, `config.py`, `management_ledger.py`, 4 configs) | −380 | −790 |

Task 2 is docs only. Net ≈ src +85, tests ≈ −110. Task 1 first; 3–5 independent; 6 largest.

### Task 1: Correct the four config cutoffs to IST (eqos-4j2.18)

Goal: `knowledge_cutoff` = `parse_filed_at(transcript filed_at_nse)`: FY26_Q2
`2025-11-06T06:35:34Z`, FY26_Q3 `2026-02-04T09:18:22Z`, FY26_Q4 `-pg` `2026-06-04T10:43:48Z`,
FY27_Q1 `2026-07-31T10:14:41Z`; `config/aparinds-fy26-q4.yaml` byte-identical.
Files: Modify the four configs (`quarter.knowledge_cutoff`, line 22) and the stale time comments
at `tests/fundamentals/legacy_support.py:26,28`; Create `tests/fundamentals/test_prep2b_cutoffs.py`.
Consequences (probed): no file in src, tests, `config/` or `docs/` pins these four digests;
`config/ledger_import.yaml` pins only the manifest and a date-only Q0 cutoff (unchanged). An
`ApprovedIntakeContext` hashes config bytes at intake (`source_intake.py:159`): one approved on
old bytes refuses and is rebuilt (none committed). Readers stay valid: `test_admission.py:269`,
`legacy_support.py:25-29` brackets, `ledger_cited_support.py:351` (synthetic literal); Q2 is the
intake fixture of four test modules — full suite re-run.
Test: per config, cutoff == `parse_filed_at` of its manifest transcript row; FY26_Q2
`2025-11-06T09:00Z` (old 5h30 window) is after it — its refusal is proving test 3.
Verification: the test file, `git diff --quiet config/aparinds-fy26-q4.yaml`, full suite. Risks: low.

### Task 2: Amend the roadmap to the retrospective contract

Goal: `docs/backend-roadmap.md` §4 Scope states plainly the pilot is a retrospective workflow
demonstration that cannot prove historical possession or absence of hindsight. PILOT-4: guidance
cites its source quote (ledger spec :201-209); each version carries the label and both cutoffs.
PILOT-5: positive retrieval at actual sequential evaluation boundaries after the prior promotion,
later events excluded; separately, historical source cutoffs return nothing the pilot created.
PREP-7: per quarter the IST-correct source cutoff, reviewed package (ids + sha256), designation.
Docs only. Verification: `.claude/project/verification.md` structural checks.

### Task 3: Run-written facts resolve as FIGURE citations, issuer-checked

Goal: a `FIGURE` citing a selected `pg-native` row resolves (value, key digest, unit/scale,
times) and checks `MATCH`; a row whose observation issuer is not the report's, or with no
first-party capture, is `UNRESOLVED`; an unselected row is `POST_CUTOFF`; legacy rows unchanged.
Files: Modify `ledger/citations.py`; Create `tests/fundamentals/test_prep2b_citations.py`.
Approach: test-first. `_FACT` LEFT JOINs translation; untranslated → parse `fact_json` as `Fact`,
refuse unless `nse-symbol` issuer equals the report entity's (`identity_layers.issuer_values`);
key = `translate(...)`; capture = first-party `capture_refs` with `blob_sha256 = fact.file_sha256`.
Test seams: `check_claim` on the `cited` rig, `OPEN` native store; INFY issuer, same value, fails.
Verification: the test file, `test_ledger_claim_check.py`, `test_ledger_stage2_e2e.py`. Risks: low.

### Task 4: Comparator figures and computed values bind to interpretation-backed traces

Goal: `bind_computed` returns a stored `COMPUTED` trace id per retained computed value (QoQ/YoY
absolute and percent changes, other-income gap, ETR, headline PBT) equal to the run's, and an
interpretation id per comparator figure and the filed tax expense; a missing interpretation or
value mismatch raises `RunDraftError` before any write. The emitted gap is exact.
Files: Create `ledger/run_traces.py`; Modify `ledger/citations.py` (FIGURE via interpretation, no
run), `ledger/import_mapping.py` (expose key helpers), `api/pipeline_steps.py:242-243` (gap result
and operands via `format_crore`); Create `tests/fundamentals/test_prep2b_traces.py`.
Interfaces: `bind_computed(repo: EvidenceRepository, result: PipelineResult, *, entity_id: int)
-> Computed` (`figures: Mapping[str, int]`, `traces: Mapping[str, int]` by claim key).
Approach: find each operand's `MAPPED` interpretation by key digest on the quarter's (or
comparator's) XBRL capture; compare with the run value; compute per the formula table, package
with `conclude` (`TraceKind.FORMULA`, operands `DURATION` under their own keys), store via
`put_calculation_trace` (content-hashed, idempotent). Citation: `FIGURE` with `interpretation_id`
and `run_id is None` → `_INTERPRETATION` query (value, key digest, unit) + `_input_times`.
Test seams: `bind_computed` after `evidence ingest` of two retained Apar XBRLs; `check_claim` on
each id → `MATCH`; emitted gap `19.72` (FY26_Q4) and `33.65` (FY27_Q1) with exact operands, and
each equals its trace-backed check.
Verification: the test file plus `test_ledger_claim_check.py`, `test_pipeline_e2e.py`.
Risks: high (financial logic). Operand semantics must match the run's (`profit_before_tax` is
before associates; `role_translation.py:1-4`); the mismatch refusal is the guard.

### Task 5: Retrospective admission

Goal: `run --retrospective` admits verified registered originals whose real registration
post-dates the source cutoff, with real times and `mode="retrospective_registered"`, only when
each is in the quarter's pinned package and published ≤ source cutoff (contract a–b); without the
flag it refuses as today; trusted-direct and local sources are never retrospective.
Files: Modify `api/source_admission.py`, `api/cli.py` (`run_command`), `api/cli_parser.py`;
Create `tests/fundamentals/test_prep2b_admission.py`.
Interfaces: `prepare_pipeline_sources(..., retrospective: bool = False)`; `AdmittedSource.mode`
gains `"retrospective_registered"`.
Approach: registered branch only: when `retrospective`, replace `bound > cutoff` with the
package + publication check; keep identity, hash, rights, completeness and `bound ≤ now`.
Test seams: `stage_local_source` under an `ApprovedIntakeContext`; `run_command` ± the flag; a
non-package or later-published original refuses with the flag.
Verification: the test file + `test_pipeline_temporal_admission.py`. Depends on 1. Risks: medium.

### Task 6: The run reads its prior and writes a validated DRAFT version

Goal: on a `PgFactStore`, `fundamentals run` refuses before the pipeline when preflight fails,
and otherwise writes one `DRAFT` whose claims all check `MATCH` inside the writing transaction,
carrying unrestated guidance from the pinned prior; the version heading and the emitted Markdown
and JSON carry the retrospective designation and both cutoffs (contract c).
Files: Create `ledger/run_draft.py`, `test_prep2b_run_draft.py`; Modify `api/cli.py`, `api/pipeline.py`
(result fields), `output/earnings_update.py` (label, cutoffs), `test_data_stage2_e2e.py` (watchlist
+ bootstrap import). Interfaces: `Prior` (frozen: `version_id`, `sealed_digest`, `entries:
tuple[NumericClaim, ...]`); `preflight(pool, config, *, catalog, snapshots) -> Prior`;
`write_run_draft(pool, repo, prior, *, config, result, catalog, snapshots) -> int`;
`PipelineResult.guidance_claims`, `.completed_at` (a final `completed()`), `.retrospective`.
Approach: `preflight` resolves entity, predecessor quarter, its head (`APPROVED` or refuse; none
only for the bootstrap period), the current head (open → refuse) and the originals.
`write_run_draft`: `bind_computed` (Task 4); the locked transaction in design order; claims —
six `FIGURE` (selected native rows), comparator `FIGURE`s, computed `CALCULATION`s, one
`SOURCE_QUOTE` per guidance claim, each unrestated prior entry `CARRIED`; status by (metric,
horizon, scope): `REAFFIRMED` only when bounds, unit, `constant_currency` and normalised
qualifiers all equal, else `MODIFIED` (F11); duplicate guidance key refuses; source checks on
every capture; `create_version`; in-transaction validation (F7). `run_command` calls `preflight`
before `run_pipeline` and `write_run_draft` after, only for a `PgFactStore`.
Test seams: `main(["run", ...])` on tmp config copies (`install_trusted_fixture_cli` — synthetic
clocks, report behaviour only); one real-clock path (proving test 6); `lifecycle.submit/validate/decide`.
Verification: proving tests; full `tests/fundamentals`. Depends on 1, 3, 4, 5. Risks: high. Binding depends on the run's quote/anchor equalling the import's (finding 6); a
non-structural numeral in a label blocks validation, which rolls back.

### Task 7: Delete the JSON management-ledger persistence

Goal: no code reads or writes `ledger_path`; the Markdown renders with `ledger=None`; the frozen
Q4 config loads (pydantic ignores the key) and is byte-identical.
Files: Modify `api/pipeline.py` (`:89-92,406-428,570-571`), `pipeline_steps.py`, `config.py`,
`output/management_ledger.py`, four non-frozen configs; Delete `test_management_ledger_replay.py`;
adapt `test_phase05_management_ledger.py`, `test_pipeline_temporal_admission.py`, `test_pipeline_e2e.py`,
`test_data_stage2_e2e.py`, `test_prep2_pilot_pg.py`.
Approach: delete `reconcile_current_guidance`, `reconcile_ledger`, `load_ledger`/`save_ledger`
and what they orphan; keep the ledger models used by rendering. Stale-prior protection lives in
Task 6's tests (F11 of PREP-2 r1).
Verification: `grep -rn "ledger_path\|load_ledger\|save_ledger\|reconcile_ledger" src tests
config/aparinds-fy2*-q*.yaml` lists only the frozen Q4 config; `git diff --quiet
config/aparinds-fy26-q4.yaml`; full suite. Depends on 6. Risks: low.

## Proving tests (markers `pg`, `retained`)

Fixture: `cited` rig + four quarters' transcript captures + `import_versions` + watchlist +
`evidence ingest` of every quarter and comparator XBRL; store `OPEN`; clocks synthetic except 6.
1. `test_prior_refusals` (parametrized, `preflight`): Q3 with an empty ledger; predecessor
   HISTORICAL→DRAFT, APPROVED→DRAFT, DRAFT-only, HISTORICAL-only; current head open; missing
   transcript capture → refuse, `fact_rows`/`fact_selections` counts unchanged; APPROVED →
   pinned id and digest; bootstrap period → `Prior(version_id=None)`.
2. `test_write_time_races` (two connections; `report_versions` counted): after `preflight`,
   (a) a runtime version appended to the predecessor report, (b) the owner `WITHDRAW`s the
   prior → refuse; (c) A holds WATCHLIST, B's append waits; A commits; B's write refuses.
3. `test_source_cutoff`: ordinary — first seen between the exact cutoff and
   `cutoff_instant(date)` → admission refuses; a carried claim's capture first seen after it →
   write refuses. Retrospective — a non-package capture, or one published after the source
   cutoff (incl. inside the old 5h30 window), refuses.
4. `test_draft_negatives`: duplicate guidance key → refuse; a guidance label with a stray
   numeral → in-transaction validation refuses, nothing persists; equal bounds with changed
   unit / `constant_currency` / qualifier → `MODIFIED`, all equal → `REAFFIRMED`.
5. `test_four_quarter_sequence`: Q2 → Q3 → Q4 (`-pg`) → FY27_Q1, each DRAFT → real `submit`,
   `validate(AS_KNOWN)` all `MATCH`, owner `APPROVE` (import `SUPERSEDED`); each pins the prior
   approved id/digest; `CARRIED` citations equal the prior's; `knowledge_cutoff == completed_at`
   (aware); computed claims `CALCULATION`; heading, Markdown, JSON carry label and both cutoffs;
   `export_version` hashes to `content_hash`; a second Q3 run while Q3's draft is open refuses
   before the pipeline (counts unchanged).
6. `test_real_clock_retrospective`: real clocks, no trusted fixture — register a retained Apar
   original via intake, `run --retrospective` → admission (`retrospective_registered`, real
   times ≥ registration) → draft → `submit` → `validate(AS_KNOWN)` passes at the derivation
   cutoff; a `RETROSPECTIVE` validation cannot bind approval; memory/claim retrieval at the
   source cutoff returns none of the records just created.

## Carried requirements and r1 dispositions

PREP-2 r1: F2 no mapper fork (Tasks 4, 6) · F3 PG traces (Task 4) · F4 native facts resolve
(Task 3) · F5 guidance via M9 · F6/F7 prior rules (test 1) · F8 exact cutoffs (Task 1; tests 3,
5) · F9 watchlist/bootstrap/transcripts (Task 6) · F10 real lifecycle (tests 5, 6) · F11 pinned
prior (test 2) · F12 adaptations in the changing task. Sol r1: 1 traces (Task 4) · 2 issuer
(Task 3) · 3 carried cutoff (test 3) · 4 admission (contract, Task 5) · 5 withdrawn prior (2b) ·
6 head advance, lock order (2a/2c) · 7 in-transaction rollback (test 4) · 8 preflight, counts
(test 1) · 9 stage-2 fixture (Task 6) · 10 through FY27_Q1 (test 5) · 11 status rule (test 4) ·
12 `run_command` throughout.

## r2 dispositions

1. Retrospective contract incomplete → contract (a)–(e) above; source-time check kept as a
   publication check in retrospective mode (design, Task 5, test 3); the false PILOT-5 claim
   removed — finding 9; roadmap amended (Task 2); real-clock integration proof (test 6).
2. Gap truncated → Task 4 renders exact gap and operands via `format_crore`; asserts 19.72 /
   33.65 and their trace checks. Decision 7 formulas defined (operand order, units, periods,
   exact arithmetic, rounding, zero denominator); result computed from resolved operands.
3. IST cutoffs → Task 1 (folded `eqos-4j2.18`) with Sol's values, frozen Q4 kept, pins checked,
   old-window publication tested (Task 1; test 3).
Note (old line 214) → test 5 runs Q3 again while its draft is open.

## Sol r3 implementation notes

- Contract (b) covers comparator provenance: `api/run_comparatives.py:76` stamps `retrieved_at`
  with the historical source cutoff; use the registered capture's actual acquisition time.
- A zero-prior percent change omits only the percentage claim; keep the prior and absolute-change
  claims and the explicit unavailable reason.
