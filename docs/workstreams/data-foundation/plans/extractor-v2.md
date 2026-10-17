# Extractor v2 (structural Ind AS signal) Implementation Plan

Status: draft — pending Sol review

**Origin:** bead `eqos-71x`; D6 [Amendment 2026-10-16 (attempt 2 burn)](D6.md#amendment-2026-10-16-attempt-2-burn-eqos-h410)
option A ("a new bead, its own version advance"), the owner's B-now-A-later choice; D6 Freeze step 6
(later phases may change `IMPL`; the Stage 4 e2e keeps replaying attempt 3 at `HEAD`). It must land
before D7, whose exit onboards a three-member batch through D6 (roadmap D7 stage 2, edge `D7 → D6`).
**Goal:** first-party XBRL ingest accepts the `in-capmkt-ent` + `IntegratedFinance_IndAS` entry point
as an Ind AS declaration, through one predicate shared by discovery and ingest, under advanced
extractor versions, so every non-financial development company that is otherwise verified onboards.
**Out of scope:** a bulk re-extraction tool or migration; any edit to a frozen manifest, the holdout
record, `d6-capability.md` or a committed migration; new frameworks (Indian GAAP, NBFC/bank forms);
the Stage 4 manifest oracle's independent restatement (`tests/fundamentals/manifest_support.py:36–40`);
vendor extractors (no `VENDOR_EXTRACTORS` file changes).
**Constraints:**
- An extractor-pinned edit advances the version; the same version with other content is refused
  (`compare/run_config.py:1–8`, `evidence/repository.py:257–276`).
- Fail closed: anything without a positive Ind AS declaration is rejected, as today.
- `discovery.py` is at 800 lines and `extract/xbrl_parser.py` at 799 (cap 800): no net line added there.
- Migrations 0001–0023 immutable; frozen manifests and `stage4_*.yaml` never edited (or opened).
- `mypy --strict`, ruff, frozen Pydantic, structlog; owner code-size rule.

## Findings (from code and retained bytes)

**How extractor versions work.** An extractor pin hashes its version string with the bytes of its
source files (`run_config.py:159–191`). `EXTRACTOR_SOURCES` (`:55–74`) lists
`evidence/member_identity.py` and `evidence/first_party_extract.py` under **both** XBRL and PDF, so any
edit to either changes both pins. Constants: `XBRL_EXTRACTOR_VERSION = "xbrl-occurrences/1"`
(`evidence/xbrl_adapter.py:42`), `PDF_EXTRACTOR_VERSION = "pdf-occurrences/2"` (`evidence/pdf_adapter.py:52`),
the ingest defaults (`first_party_ingest.py:104–107`). Every run pins **both** first-party extractors
(`load_run_config`, `run_config.py:224–227,237–238`), so an unbumped PDF pin would make even an
XBRL-only onboarding run raise `VersionContentDriftError` on any database that has pinned
`pdf-occurrences/2`. Both versions must advance, although PDF behaviour does not change.
`ConfigVersions`/`ONBOARDING_VERSIONS` carry no extractor field (`contracts/config_versions.py:13–24`);
extractors are always the current code's.

**Pin tests.** `test_compare_config_pins.py` is generic (pins change with sources) and needs no edit.
The D3.6 frozen-file check is the upgrade test `test_onboarding_on_a_seed_commit_database_drifts_no_pin_and_changes_no_row`
(`test_derived_settings.py:475`): `_seed_pins` (`:449–470`) pins the seed commit's (`SEED_COMMIT = "82a84db"`,
`:69`) source bytes under the **current** version names, so after the bump it pins
`xbrl-occurrences/2` to v1 bytes and onboarding drifts — it fails by construction (as D6 predicted).

**Stored generations.** Occurrences and attempts carry `extractor_version`; a member's generation is
looked up by `(capture, extractor_version)` (`first_party_extract.py:228–235`), so ingesting a stored
capture under v2 writes a new generation stamped `PARSER_REEXTRACTION` (`:486–503`); v1 rows are never
rewritten (`test_evidence_reprocessing.py:60–131`). New runs select only interpretations under the
pinned extractor (`evidence/selection.py:415–421`), so an existing entity needs a v2 ingest before a
new run sees first-party values (inference: such a run reports them missing, it does not read v1).
**Replay** uses the stored manifest's pins and by-id reads, never re-extracting (`compare/run.py:160–197`),
so every stored v1 run replays unchanged. v1 cannot be *re-run* after the bump: naming
`xbrl-occurrences/1` hashes current bytes and drifts against its stored pin. "v1 kept for replay"
therefore means stored rows and pins, which is sufficient.

**Frozen manifests.** Only the Stage 1 manifest names extractors (`stage1_manifest.yaml:17`:
`[xbrl-occurrences/1, pdf-occurrences/2, …]`, approval-hashed); Stage 2 and ledger manifests do not.
Per D6 Q3 the Stage 4 manifest reuses the Stage 1 runs schema (not opened). No e2e asserts these names:
the Stage 1 e2e ingests fresh under the default versions and compares values
(`stage1_e2e_support.py:77,250`); the Stage 4 e2e asserts `record.pinned == load_run_config(...)` at
`HEAD` (`test_data_stage4_e2e.py:175–176`), result rows carry no extractor field, and neither the e2e
nor `stage4_support.py` reads an extractor name. **Ruling proposed:** a frozen header records the
versions it was authored under; reproduction is proved by its e2e values, not the names.

**D6 draw checker hazard.** `stage4_filings.xbrl_admitted` (`:98–116`) recomputes attempt ≥3 skips
(`stage4_support.py:56,482–491`) through the production `framework_state`. Widening it would admit
candidates the attempt-3 draw skipped as `XBRL_NOT_ADMITTED` and break the recorded draw. The checker
must keep the frozen (v1) admission rule.

**The signal (measured, `data/raw/onboarding-dev/` + Apar `data/raw/watchlist/aparinds/nse/`, by lxml
over every `nse/*.xml`, 25 files, 24 distinct):**

| Group | Distinct instances | schemaRef | `IntegratedFinance_*` namespace | v1 framework accepts |
|---|---|---|---|---|
| Non-financial integrated (Apar ×6, 10 other dev cos) | 16 | `in-capmkt-ent-2025/2026-01-31.xsd` (16/16) | `IndAS` 16/16 | 7 (Apar ×6, LAURUSLABS) |
| Bank HDFCBANK | 2 | `in-capmkt-ent-2026-01-31.xsd` | `Banking` 2/2 | 0 |
| NBFC BAJFINANCE (file named `NBFC_INDAS`) | 2 | same | `NBFC` 2/2 | 0 |
| Insurers HDFCLIFE, SBILIFE | 3 | `in-capmkt-ent-2025-01-31.xsd` | `LI` 3/3 | 0 |
| Apar legacy `in-bse-fin` | 2 | `Ind-AS_entry_point_2020-03-31.xsd` | none | 2 (schemaRef) |

The signal is the root `xmlns:in-capmkt-ent`/`in-capmkt-roles` declarations under
`http://www.sebi.gov.in/xbrl/IntegratedFinance_IndAS/<date>/…` (no element uses them) plus a relative
`in-capmkt-ent-*` schemaRef — exactly Task 0b's `financial_rule` (`entity/verification.py:74–81,153–166`).
Phrase absent in 9 dev companies: CGPOWER, ETERNAL, HFCL, MTARTECH, NETWEB, POLYCAB, SONACOMS,
THERMAX, TITAN (ETERNAL's notes cite "Indian Accounting Standard 34 … (Ind AS 34)", not the pinned
phrase). It is a taxonomy-form choice by the filer — the same kind of structural declaration v1
already accepts from `Ind-AS_entry_point` (`member_identity.py:48–52,184–186`). **Not measured:** a
non-financial, non-Ind-AS integrated filing — none is retained, so the signal's absence for such a
filer is unproven. Listed non-financial companies on the NSE main board report under Ind AS
(background knowledge, not evidence); the residual case is an SME-platform filer. Smallest probe if
Sol wants it: retain one NSE Emerge integrated filing and record its namespace. Unknown forms already
fail closed.

## Design

One predicate, `integrated_ind_as(body: bytes) -> bool`, in `member_identity.py` (the lowest common
layer; `evidence` must not import `entity`), holding the moved `IND_AS_ENTRY_POINT` regex and
`in-capmkt-ent-` prefix; its body is today's `financial_rule`. Uses:
- ingest: `verify_xbrl_framework(instance, framework, *, body: bytes)` adds an Ind AS declaration
  (evidence "IntegratedFinance_IndAS entry point") when `integrated_ind_as(body)`; schemaRef and
  text-block declarations unchanged, so v2 accepts a strict superset of v1 and rejects nothing new.
  `_read_xbrl` passes the `body` it already holds (`first_party_extract.py:393,402`).
- discovery: `financial_rule(body)` returns `integrated_ind_as(body)` (the sector rule is the same
  signal, Task 0b); `framework_state(instance, body)` calls `verify_xbrl_framework` as ingest does;
  `discovery.py:538` passes `zip(instances, bodies)` on the same single line (≤100 columns).
Passing `body` rather than adding a `namespaces` field to `RawXbrlInstance` avoids the 799-line parser.
Versions: `xbrl-occurrences/2`, `pdf-occurrences/3`. Pinned files touched: `member_identity.py`,
`first_party_extract.py`, `xbrl_adapter.py`, `pdf_adapter.py` — the D3.6 "amendment that advances
the version" branch, made explicit here.

## File map

| File | Change | Responsibility |
|---|---|---|
| `src/fundamentals/evidence/member_identity.py` | modify (pinned) | `integrated_ind_as`; `verify_xbrl_framework(..., body=)` |
| `src/fundamentals/evidence/first_party_extract.py` | modify (pinned) | pass `body=` at `:402` |
| `src/fundamentals/evidence/xbrl_adapter.py` | modify (pinned) | `XBRL_EXTRACTOR_VERSION = "xbrl-occurrences/2"` |
| `src/fundamentals/evidence/pdf_adapter.py` | modify (pinned) | `PDF_EXTRACTOR_VERSION = "pdf-occurrences/3"` |
| `src/fundamentals/entity/verification.py` | modify | `financial_rule` delegates; `framework_state(instance, body)`; drop moved constants |
| `src/fundamentals/entity/discovery.py` | modify (1 line) | pass bodies to `framework_state` |
| `tests/fundamentals/test_identity_namespace.py` | modify | structural signal unit cases; `body=` at existing calls |
| `tests/fundamentals/test_evidence_refusals.py` | modify | phrase-only removal now ingests; no-declaration case also renames the namespace |
| `tests/fundamentals/test_derived_settings.py` | modify | upgrade test seeds pins under the seed's version names |
| `tests/fundamentals/stage4_filings.py` | modify | `xbrl_admitted` keeps the frozen v1 framework rule |
| `tests/fundamentals/test_onboarding_verification.py` | modify | parity 16/16; frozen rule 7; phrase-removed Apar onboards |
| `docs/workstreams/data-foundation/roadmap.md`, `plans/D6.md` | modify | phase row, D7 edge, support-limit note |

## Tasks

### Task 1: Framework predicate v2 and extractor version advance

Goal: XBRL ingest of an in-capmkt IntegratedFinance_IndAS instance without the notes phrase is
`COMPLETE` under `xbrl-occurrences/2`; Banking/NBFC/LI or unknown forms without a declaration stay
`IDENTITY_REJECTED`; a database holding v1 pins onboards with no drift and no changed row.
Files: Modify the six `src/` files above. Test: `test_identity_namespace.py`, `test_evidence_refusals.py`,
`test_derived_settings.py`.
Interfaces:
- Produces: `member_identity.integrated_ind_as(body: bytes) -> bool`;
  `verify_xbrl_framework(instance: RawXbrlInstance, framework: AccountingFramework, *, body: bytes) -> IdentityVerdict`;
  `verification.framework_state(instance: RawXbrlInstance, body: bytes) -> Verdict`;
  `XBRL_EXTRACTOR_VERSION = "xbrl-occurrences/2"`, `PDF_EXTRACTOR_VERSION = "pdf-occurrences/3"`.
Approach: test-first. Red: in `test_evidence_refusals.py`, replacing only `XBRL_DECLARATION` must give
an XBRL `COMPLETE` attempt whose reason names the entry point (today `IDENTITY_REJECTED`); the existing
no-declaration case additionally rewrites `IntegratedFinance_IndAS` → `IntegratedFinance_ZZ` in the
marked copy and stays rejected. In `test_identity_namespace.py`, parametrise over one retained
instance per form (a phrase-free dev IndAS instance accepted; HDFCBANK, BAJFINANCE, HDFCLIFE
rejected — each with ingest's own verdict, reason "declares no accounting framework");
the foreign-text test passes a body without the signal. Then move the predicate, add the clause, wire
the callers, bump both constants with a comment citing this plan. Upgrade test: `_seed_pins` names the
seed's versions explicitly (`xbrl-occurrences/1`, `pdf-occurrences/2`, read from the seed commit's
`xbrl_adapter.py`/`pdf_adapter.py` bytes), so it proves v1 pins coexist with v2 — assertions unchanged.
Verification: `uv run pytest tests/fundamentals/test_identity_namespace.py tests/fundamentals/test_evidence_refusals.py tests/fundamentals/test_derived_settings.py tests/fundamentals/test_compare_config_pins.py tests/fundamentals/test_evidence_reprocessing.py`
green; red run recorded first; `wc -l src/fundamentals/entity/discovery.py` ≤ 800; mypy, ruff.
Test seams: `ingest_first_party` attempts (outcome, reason); `verify_xbrl_framework` verdict;
`fundamentals onboard` exit and stored rows in the upgrade test.
Dependencies: None.
Risks: forgetting the PDF bump passes in fresh test DBs but drifts on every real DB — the upgrade
test is the guard. Implementer: Opus.

### Task 2: Discovery parity and the frozen draw rule

Goal: discovery admits exactly the instances v2 ingest accepts (16/16 non-financial, all 11 dev
symbols); the D6 draw checker still recomputes attempt-3 skips under the v1 rule (7 admitted);
phrase-removed Apar onboards `PARTIAL` with its XBRL ingest `COMPLETE`.
Files: Modify `tests/fundamentals/stage4_filings.py`, `tests/fundamentals/test_onboarding_verification.py`.
Interfaces:
- Consumes: Task 1's `verify_xbrl_framework(..., body=)`, `framework_state(instance, body)`.
- Produces: `stage4_filings.xbrl_admitted` unchanged in signature, now evaluating the frozen rule.
Approach: `xbrl_admitted` replaces `framework_state(instance)` with the v1 decision —
`verify_xbrl_framework(instance, IND_AS, body=<a body without the signal>)`, i.e. v2 minus the
structural clause, which is exactly v1 (docstring: "frozen D6 admission capability; never the
production rule"). Fallback if Sol rejects that: restate v1 test-side from the public
`FRAMEWORK_DECLARATIONS`, `IND_AS_ENTRY_POINT_PREFIX`, `TEXT_BLOCK_SUFFIX`, `normalize_text_tokens`.
`test_discovery_admits_exactly_the_instances_first_party_ingest_accepts` (`:104–131`) asserts v2 ingest
parity against discovery's `financial_rule` + `framework_state`, `admitted == 16`, symbols = the 11;
and `xbrl_admitted` admits exactly 7, `{APAR, LAURUSLABS}` (characterises the frozen rule).
REFUSALS `no_framework_declaration` (`:380–389`) becomes a success case: same edit, exit `INCOMPLETE`
(`PARTIAL`), XBRL attempt `COMPLETE`, occurrences under `XBRL_EXTRACTOR_VERSION`. Combined-defect
cases using `_NO_PHRASE` (`:530,564–574`) drop it (it no longer refuses); delete a case that becomes a
duplicate. `test_stage4_holdout_git.py` needs no edit (its `no_phrase` skip holds under the frozen rule).
Verification: `uv run pytest tests/fundamentals/test_onboarding_verification.py tests/fundamentals/test_stage4_holdout_git.py tests/fundamentals/test_data_stage4_e2e.py`
green, then the full gate below.
Test seams: `financial_rule`, `framework_state`, `xbrl_admitted`; `fundamentals onboard` replay exit and rows.
Dependencies: Task 1.
Risks: the Stage 4 e2e (opaque) is predicted green (attempt 3's instances passed v1, v2 is a
superset, no assertion reads extractor names). If red: stop, do not patch; a Sol-reviewed amendment
records the reason. Implementers never open the opaque files. Implementer: Opus.

### Task 3: Acceptance smoke and records

Goal: a live full-onboard smoke over all 11 development symbols matches the predictions below, and
the roadmap records the phase.
Files: Modify `roadmap.md` (Progress row "D6b Extractor v2 (`eqos-71x`)", edge `D7 → D6b`), `D6.md`
support-limit note (point here), this plan's status and observed table.
Interfaces: Consumes Tasks 1–2 at a committed `HEAD`.
Approach: orchestrator runs `scratchpad/execution/d6/live_onboard_smoke.py` (credentials sourced by
the orchestrator, scratch `eqos_test_*` DB) — retained live-smoke generations for refused companies
stop at XBRL (THERMAX, SONACOMS: 5 captures), so fresh generations are required. Predicted before
implementation:

| Symbol | v1 observed / expected | v2 predicted |
|---|---|---|
| APARINDS, LAURUSLABS | `PARTIAL` (observed 2026-10-16) | `PARTIAL`, unchanged |
| NETWEB | `UNSUPPORTED (STANDALONE_BASIS)` | unchanged (refused before XBRL) |
| THERMAX, SONACOMS | `UNSUPPORTED (NO_FRAMEWORK_DECLARATION)` observed; identity and period passed | `PARTIAL` |
| CGPOWER, ETERNAL, HFCL, MTARTECH, POLYCAB, TITAN | `NO_FRAMEWORK_DECLARATION` (from retained instances) | `PARTIAL` (identity, BSE, vendor units unobserved) |

Pass criterion (v2's claim): zero `NO_FRAMEWORK_DECLARATION` outcomes and zero first-party attempts
rejected "declares no accounting framework" across the 11, and at least 3 `PARTIAL`/`ONBOARDED`
(D7's batch). Any other refusal or conflict on the six unobserved companies is recorded with its
reason and gets a bead; it is not a v2 defect. A failed request is re-run (R-ACQ).
Verification: smoke output saved under `scratchpad/execution/extractor-v2/`; table filled in this plan.
Dependencies: Tasks 1–2, phase-end Sol review.
Risks: network or authority failures; doc-only edits by Sonnet.

## Verification (phase gate)

- `uv run ruff check src tests/fundamentals`; `uv run ruff format --check src tests/fundamentals`;
  `uv run mypy --strict src`; `uv run pytest tests/fundamentals` (pg + retained up; no `-m` opt-outs),
  or `scripts/verify.sh gate <slice>`.
- Explicitly green within it: `test_data_stage1_e2e.py`, `test_data_stage2_e2e.py`,
  `test_data_stage4_e2e.py` (attempt-3 replay at `HEAD`, incl. `test_stage4_freeze_held_to_closure`),
  `test_ledger_stage{1,2,3}_e2e.py`, `test_frozen_manifests.py`, `test_stage4_holdout_git.py`,
  `test_compare_config_pins.py`, `test_evidence_reprocessing.py`.
- `git status` shows only the mapped files.

## Risks

- **Signal strength:** a namespace declaration is a form choice, not a sentence; inference that the
  IndAS form implies Ind AS. Mitigation: form-specific URI, 16/16 vs 0/7; fail closed elsewhere.
- **Existing databases:** stored entities show no first-party values in a new run until re-ingested
  under v2 (lazy re-extraction, by design). Replays of stored runs are unaffected.
- **Historical draw:** handled by the frozen rule; its 7-count test catches accidental widening.
- **Line caps:** `discovery.py` must stay at 800 — the one-line change must not wrap.

## Open questions

- O1 (orchestrator): re-extract the live database's stored Apar generations now, or lazily on the
  pilot's next ingest? Recommended: lazily; nothing in D7 reads them.
- O2 (Sol): accept the "frozen header records authoring versions" ruling for Stage 1 (and Stage 4)?
- O3 (Sol): is the dummy-body form of the frozen rule acceptable, or restate v1 test-side?
- Owner: none. The structural signal was the owner's option A (2026-10-16); no financial judgment.

## What could be cut

- `framework_state` and its discovery line: with `financial_rule ≡ integrated_ind_as`, discovery's
  framework check can no longer refuse (only Ind AS phrases exist). Kept (≈5 lines) because it makes
  discovery apply ingest's exact predicate by construction — the attempt-2 burn class. Cut if Sol
  prefers.
- The `D6.md` note (roadmap row suffices); the 6 unobserved smoke symbols (3 suffice for D7, but the
  bead asks for broad onboarding).
- Not cuttable: the PDF bump (every run pins both extractors) and the frozen draw rule.
