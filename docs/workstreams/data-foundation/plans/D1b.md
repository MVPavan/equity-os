# D1b Implementation Plan

Status: approved-for-implementation
Prepared: 2026-10-13, Codex session (handoff run)
Revision: r2; independent re-review APPROVE, 2026-10-13, Codex session (handoff run).
Tracking: `eqos-u0u`; stages `eqos-u0u.1`–`eqos-u0u.6`; prerequisite `eqos-u0u.7`.

**Origin:** [approved roadmap](../roadmap.md), D1b; live stage acceptance read on
2026-10-13; [approved data spec](../../../specs/2026-10-11-canonical-financial-data-and-cross-source-comparison.md)
§2–§5, §8, Stage 1 and Testing Decisions; [approved ledger/lifecycle spec](../../../specs/2026-10-12-report-ledger-memory-and-data-lifecycle.md)
§6, especially amendments 11–12.

**Goal:** retained vendor evidence flows through canonical interpretation, independent
corroboration, diagnostics and an append-only review queue, and Apar plus the ten-company
acceptance exactly matches a separately source-verified, approved and previously committed manifest.

**Out of scope:** live vendor acquisition, new credentials or changes to `data/raw/`.
**Out of scope:** legacy cutover, report admission, the full D3 ledger/panel service, memory,
onboarding, new exchange shareholding acquisition and retention/purge machinery.
**Out of scope:** declaring absent evidence to be publication absence, choosing unexplained
financial definitions, or expanding standalone coverage beyond NETWEB's consolidated refusal.

**Constraints:** “Never modify `data/raw/`. Use retained captures only.”
**Constraints:** “Financial logic: exact `Fraction` arithmetic, fail closed, never zero-fill,
never backdate.”
**Constraints:** “Knowledge times come from `eqos.store_now()`.”
**Constraints:** “Expected values come from source documents, never from code output.”
**Constraints:** “Tests use `eqos_test_*` databases only.”
**Constraints:** “Never edit applied migrations `0001`–`0004`.”
**Constraints:** “`0005` becomes immutable at its first commit; subsequent schema work takes the
next free number.”
**Constraints:** “Unit tests only for dynamic financial logic (never declarations).”

## File map

Paths below are the implementation surface, not changes authorized by this document-writing
task. Existing first-party code belongs to the D1a fix workers until their handoff. One shared
contract/schema writer owns Tasks 2 and 6; other writers begin after its interface handoff.
The config owner publishes joined drafts in Task 13 before any v2 generation; Task 11 then
provides first-party v2 generations. Task 12 owns the D1b project-verifier deliverable.

| Create or modify | Responsibility | Task / owner |
|---|---|---|
| Create `docs/specs/artifacts/stage1-source-inventory.md` | Read-only inventory, authority/time/hash proofs, period/basis coverage and parked obligations | 1, evidence verifier |
| Modify `docs/specs/artifacts/dictionary-v1-manifest.md` | Cited disposition of all 17 deferred ids; reconcile current 259-row baseline | 1, dictionary owner |
| Create `config/dictionary/v2/metadata.yaml`, `pl.yaml`, `balance_sheet.yaml`, `cash_flow.yaml`, `segment.yaml`, `shareholding.yaml`, `derived.yaml`, `templates.yaml`, `applicability.yaml` only if evidenced rows are added | Complete next declarative dictionary/formula version; preserve published v1 | 1, dictionary owner |
| Create `migrations/0006_review_queue.sql` | Queue/disposition immutability plus necessary vendor representation, source identity and version-pin schema extensions in one planned migration | 2, schema owner |
| Modify `src/fundamentals/contracts/canonical.py`, `contracts/comparison.py`, `contracts/evidence.py`, `contracts/source_catalog.py` | Vendor representation, extractor, pair/selection provenance and surface-authority contracts; preserve first-party types | 2, contract owner |
| Create `src/fundamentals/contracts/review_queue.py`, `src/fundamentals/compare/approval_receipts.py` | Queue/disposition/overlay contracts and authenticated, proposal-bound approval receipt verification | 2, 7, contract/approval owner |
| Modify `src/fundamentals/compare/run_models.py`, `compare/run_config.py`, `compare/run_store.py` | Source-qualified value/pair identities, requested vendor surfaces, content pins, persisted/replayed vendor inputs | 2, 6, shared contract/run owner |
| Modify `src/fundamentals/evidence/repository.py`, `evidence/repository_rows.py`, `evidence/mapping.py`, `evidence/interpret.py`, `evidence/capture_interpretation.py` | Vendor generation reads/writes and native selector/period interpretation without XML/PDF assumptions | 2, shared contract/evidence owner |
| Create `config/source_authority/v1.yaml` | Joined source × surface role/authority artifact, published with the mapping bundle | 13, config owner |
| Create `src/fundamentals/evidence/vendor_common.py`, `evidence/vendor_screener.py` | Common retained intake/eligibility handoff and Screener extraction | 2, 3, shared intake/Screener owners |
| Create `config/mappings/v2.yaml`, `config/mappings/screener/v2/financials.yaml`, `config/mappings/screener/v2/constructions.yaml`, `config/mappings/constructions/v2.yaml` | Joined v2 index, direct/vendor-computed mappings and first-party aggregate comparison bridge | 3 drafts, 13 publication; config owner |
| Create `src/fundamentals/evidence/vendor_tijori.py`, `evidence/vendor_upstox.py`; create `config/mappings/tijori/v2/financials.yaml`, `config/mappings/upstox/v2/statements.yaml` | Retained Tijori/Upstox seams and mappings; measurement-bearing entries require real inputs | 4, vendor owner |
| Modify `src/fundamentals/compare/tables.py`; create `compare/routing.py`, `compare/trust.py` | Exhaustive corroboration, pair routing and trust from a named overlay | 5, comparison owner |
| Create `src/fundamentals/compare/vendor_inputs.py`, `compare/queue.py`; modify `compare/resolve_loader.py`, `compare/resolve_models.py`, `compare/resolve.py`, `compare/engine.py`, `compare/engine_rows.py`, `compare/run.py`, `compare/report.py` | Resolve vendor evidence/attempts, publish queue items with results, replay and report every surface | 6, shared run owner |
| Modify `src/fundamentals/api/compare_cli.py`; create `api/compare_queue_cli.py` | Public vendor/version run selection and authenticated queue/disposition/interpretation-approval commands | 7, CLI owner |
| Modify `src/fundamentals/evidence/first_party_ingest.py`, `evidence/capture_interpretation.py`, `evidence/alignment.py` only as needed; create `tests/fundamentals/test_first_party_mapping_generation.py` | Append-only first-party v2 interpretations, scoped requalification/alignment and v1 replay handoff | 11, first-party generation owner |
| Create `scripts/verify_project.sh`, `tests/fundamentals/test_verify_project.py` | Project-wide exits/governance/quality/pilot verifier with honest NOT BUILT/nonzero behavior | 12, verifier owner |
| Create `tests/fundamentals/test_vendor_config_publication.py` | Joined-artifact publication/drift/refusal proof through actual loaders | 13, config owner |
| Create `docs/blueprint/amendments/2026-10-11-data-layer-postgresql.md` | Exactly the data spec's two register changes with actual approval evidence | 8, amendment owner |
| Create `tests/fundamentals/vendor_retained_support.py`, `test_evidence_vendor.py`, `test_vendor_schema.py` | Hash-bound real inputs and public adapter/schema integration proofs | 2–4, test owner |
| Modify `tests/fundamentals/test_canon_dictionary_load.py`, `test_evidence_mapping.py`, `test_evidence_contract_boundaries.py`, `test_compare_runs.py`, `test_compare_config_pins.py`, `test_compare_run_rules.py`, `test_pg_migrations.py` | Preserve existing behavior while proving next-version, selector, source and persistence seams | 1–3, 6, shared test owner |
| Create `tests/fundamentals/test_compare_corroboration.py`, `test_compare_diagnostic.py`, `test_compare_queue.py` | Dynamic rules plus retained evidence → run → queue integration | 5–7, test owner |
| Create `tests/fundamentals/test_amendment_records.py`, `test_frozen_manifests.py` | Shared approval/link and independent-oracle/commit-order checks | 8–9, governance test owner |
| Create `tests/fundamentals/fixtures/data_foundation/stage1_manifest.yaml` | Independent frozen oracle, source locators/hashes, fixture transformations and approvals | 9, evidence verifier |
| Create `tests/fundamentals/test_data_stage1_e2e.py` only after Task 9's approved manifest commit | Every-row Stage 1 acceptance and CLI demonstration | 10, e2e owner |

Existing parsers under `ingest/` remain the parsing seams: Screener `FinancialsArtifact`,
`SectionTable` and raw page/schedule readers; Tijori `build_all_tijori_tables`; Upstox
`read_income_statement`, `read_balance_sheet`, `read_cash_flow`, `read_key_ratios`.
Use their offline inputs; never instantiate a network fetcher. Existing `SnapshotStore`,
`CaptureRecord`, `CaptureReference`, `Occurrence`, `Interpretation` and `AcquisitionAttempt`
remain the evidence/store contracts. New modules adapt these seams rather than replacing them.

## Current evidence and build gates

Read-only inventory on 2026-10-13 found the following under `data/raw/watchlist/`:

| Retained input | Verified observation | Sufficiency / gate |
|---|---|---|
| `aparinds/` | 8 XML, 15 PDF, retrieval manifest | First-party Apar qualification/tracer is available; use manifest-bound originals and current D1a fixes |
| `cgpower/`, `eternal/`, `hfcl/`, `lauruslabs/`, `mtartech/`, `polycab/`, `sonacoms/`, `thermax/`, `titan/` | Each has a PDF and at least one XML | Candidate nine-company Q3 FY25 filing evidence; each period, identity, basis and retrieval provenance still needs Task 1 verification |
| `netweb/` | One PDF, no XML | Retained standalone evidence; cannot manufacture paired consolidated extraction |
| `screener-financials/<SYMBOL>/<basis>/` | Ten HTML pages total, one per symbol/basis, and 22 JSON files per symbol; NETWEB standalone, the other nine consolidated; all ten page hashes match metadata | Real financial/schedule parsing seams available, including Dec 2024 columns; hash match is not authority or first-seen proof |
| Screener metadata | All ten `complete=true`; CGPOWER, LAURUSLABS, POLYCAB, SONACOMS have `verified=false`; six others `verified=true` | Verify individual section/schedule scope. An aggregate flag cannot qualify every surface or mapping |
| Apar Screener, Tijori, Upstox | No corresponding retained files in the authorized root | Apar opex qualification, Tijori remeasurement and real Upstox diagnostic fixtures are parked; no live acquisition is authorized |
| NETWEB degenerate consolidated Screener / empty consolidated Upstox | No retained response identified | The negative capture-specific proof is parked; standalone-only applicability can still be proved from actual issuer evidence |

The Screener metadata contains `fetched_at`, page SHA-256 and parser flags, but no protected
registration receipt, surface authority or first-seen proof. Reopen raw bytes, check the source
rights decision and bind identity/basis per surface. Record old `fetched_at` only as a capture's
claim. New local retained registration uses the actual store clock; never backdate registration
to 2026-09-04. Current source-rights authority is
[A05-DECISION-005](../../../evidence/phase-0a/a-05-rights-decision-005-subscriber-scraping.md),
within its private-use boundary; source classification alone does not establish permitted surfaces.

Missing local bytes mean operational unavailability, not `NOT_PUBLISHED`. An unknown or
unapproved surface records `NOT_AUTHORISED`; a permitted surface lacking retained input records
an honest failed/unavailable retained-input attempt, with no invented capture hash or transport
claim. Preserve `AcquisitionAttempt.extraction_context_sha256`: hash the actual request and any
mapping/dictionary/context used to determine the outcome; failed capture-free attempts retain
their actual request identity. Never substitute one surface's complete capture for another's
failed request. `NOT_PUBLISHED` requires a retained source response establishing absence.

These gaps prevent Stage 1 exit, including the requirement for complete happy-path runs.
They do not prevent document preparation, available Screener integration, exhaustive dynamic
rules, queue persistence/dispositions, source refusal paths or the amendment record. Parked
measurement obligations remain named in Task 1 and cannot be converted into synthetic source
fixtures, a reduced frozen manifest, skipped tests or stage closure. Preparation of a manifest
schema is permitted; freezing/approving the full manifest is blocked by missing source proof.

## Existing interfaces and required extensions

The checkout is D1a-shaped: `Representation` has only XBRL/PDF;
`SourceValue`/`SourceRef` identify a side by role and representation;
`RunScope.sources` accepts only first-party surfaces; `PinnedVersions` has only XBRL/PDF
extractor pins; `corroboration_status` refuses a nonempty vendor set. None is already a
vendor adapter API. Task 2 defines the minimal extensions and Task 6 connects them.

The current public run API is `request_for(entity_id, period_end, basis, *, cutoff,
config_root, code_version, database_identity, mode, sources, versions, extractor_pins)`,
`execute_run(request, *, pool, config_root, extractor_pins, publish_hook)`,
`replay_run(run_id, *, pool, config_root, reader)` and
`load_results(run_id, *, pool)`. Preserve one entity per run; the eleven-company gate is a
collection of named runs. Preserve current source and attempt filtering in `RunLoader` and
the manifest's selected/failed attempt ids. Do not infer a vendor API by passing vendor ids
through the current first-party-only validator.

Proposed contracts below are deliverables, not claims that those symbols exist today:

| Contract | Required shape / consumer |
|---|---|
| `VendorRequest` | Source id, surface, schema identity, entity id, exact requested period, basis, framework, applicable family and retained input binding; Tasks 3–4 |
| `VendorGeneration` | Capture reference when real bytes exist; tuple of occurrences, interpretations and attempts; content-pinned extractor; never a fabricated first-party package; Task 6 |
| `VendorSurfaceRequest` | Source id and surface; immutable sorted tuple added as `RunScope.vendor_sources`, with an empty default for existing first-party requests; Task 6 |
| Vendor representations | Add HTML and JSON for occurrences/interpretations/attempts; first-party package membership and extraction remain restricted to XBRL/PDF. Preserve all first-party loops and constructors |
| Source-qualified side | Add `source_id` and `surface` to `SourceValue` and `SourceRef`, and roles `INDEPENDENT_VENDOR` / `DIAGNOSTIC`; both Upstox surfaces and multiple HTML vendors must coexist in one result |
| Pair and selection provenance | Add `PairKind.CORROBORATION` for first-party ↔ independent vendor, `PairKind.DIAGNOSTIC` for Upstox ↔ Screener/first-party and other-representation checks, and `SelectionSource.VENDOR_CAPTURE` for a selected operand of the same vendor surface/capture. Update matching SQL checks and source-qualified pair/trace reconstruction; preserve EXTRACTION and REPORTED_VS_DERIVED |
| Vendor pins | Add vendor extractor pins keyed by source and surface to `PinnedVersions`, and their interpretation-version selection; content hashes cover parser/adapter sources and source-authority artifacts. Preserve old first-party manifests and replay semantics |
| `QueueItem` | Measurement key, pair/extraction identity, outcome, input hash, severity, diagnostic flag, source/attempt/evidence references and predecessor when inputs change |
| `QueueDisposition` | Item id, one of the six spec disposition kinds, reason, proposer/decider identity, evidence reference, and explained amount only from code or the owner |
| `QueueOverlay` | Named run, monotonic recorded position and as-of time, open items and accepted dispositions; only this overlay affects the trust view, never immutable results |
| `ApprovalReceipt` / `VerifiedApprovalReceipt` | Append-only receipt id, subject kind/id, proposal id/hash, sealed subject digest, ACCEPT/REJECT, decision/review evidence ids/hash, actual decider provenance, authenticated producer database identity and store-recorded time; the verified form is obtained only by reloading the protected receipt row, never by deserializing caller claims |
| `PublishedVendorConfig` | Task 13's immutable mapping-set/authority/dictionary/normalisation/extractor pin bundle plus included and explicitly unavailable/excluded surfaces; only this joined release can produce v2 stored generations |
| `FirstPartyGenerationHandoff` | Per package/source/capture: original occurrence ids when reusable, new v2 interpretation and context-qualified attempt ids, alignment/qualification evidence ids, content pins and actual recorded-at bounds; produced by Task 11 |

Source-authority and qualification artifacts must join the resolved input pins. Reuse
`QualificationFixture(capture_id, capture_sha256, entity_id, discriminating)` and
`QualificationScope.fixture_evidence`; a list of hashes or prose “five companies” is not
demonstrated evidence. Conditions use stored interpretation ids through `ProvenCondition`.
Unknown provenance, basis, periods or precision fails closed, and API JSON digits alone do not
declare precision. Interpretation ambiguity, retained missing-value states and `INVALID`
precedence remain intact.

The existing database authentication boundary is `PgRole.MIGRATOR`/`eqos_migrator` and
`PgRole.RUNTIME`/`eqos_runtime` in `pg/settings.py`, opened by `pg/pool.py`; there is no panel
role today. D1b uses these already configured roles without creating roles, credentials or a
network service. Migration 0006 gives runtime access only to items and amount-free proposals;
receipt/final-decision writes are refused to runtime both in SQL and command dispatch. A
trusted coordinator composition call authenticated as the existing migrator records verified
external review evidence under the dated single-reviewer route, or a direct owner ruling
actually present in the active session. The producer binds immutable review/ruling evidence to
the subject and proposal digest; a path, self-reported actor, hash or `--owner` flag alone cannot
authorize a receipt. Database-recorded `session_user`/role and `eqos.store_now()` are authoritative,
not a custom GUC or command argument. Final record commands require that privileged connection
and reload a matching verified receipt. This is a bounded local receipt producer/consumer;
D3 later integrates its service and finer role policy, not a prerequisite for D1b acceptance.
Missing or unverifiable actual review/owner evidence refuses the decision and leaves its
acceptance open; privileged database authentication alone does not turn arbitrary input into
an owner ruling. Owner-provided amounts require the exact bound owner ruling; otherwise a
calculation trace supplies the amount. No runtime amount-bearing proposal/final record is allowed.

## Tasks

### Task 1: Verify retained scope and resolve every deferred row

Goal: each source obligation has an evidence-backed usable/parked verdict, and every deferred
formula id has an evidenced construction or a cited exclusion without changing an unexplained definition.

Stage: `eqos-u0u.7` (prerequisite for vendor formula comparison and Tasks 9–10).

Files:
- Create: `docs/specs/artifacts/stage1-source-inventory.md`; next dictionary version only for genuinely evidenced additions.
- Modify: `docs/specs/artifacts/dictionary-v1-manifest.md` disposition section; preserve the published v1 rows.
- Test: `tests/fundamentals/test_canon_dictionary_load.py` for a real next-version loader/coverage change.

Interfaces:
- Consumes: approved inventory/spec; current 259-row dictionary and deferred table; raw retained HTML/JSON/XML/PDF; rights decision and actual registration evidence.
- Produces: `stage1-source-inventory.md` with source/period/basis, path/hash/anchor, authority and honest time proof, verdict and parked reason; all 17 cited dispositions; a complete next dictionary version for justified additions, including the spec-required `other_income_incl_exceptional` bridge defined as `other_income + exceptional_items_before_tax`.

Approach: inspect raw published rows and schedules, not generated sections alone. Account for
`borrowings_total`, `ebit_vendor`, `profit_excl_exceptional`, `profit_for_pe`, `free_cash_flow`,
`roce_pct`, `roe_pct`, `roa_pct`, `debt_to_equity`, `interest_coverage`, `current_ratio`,
`quick_ratio`, `dividend_payout_pct`, `inventory_days`, `payable_days`,
`cash_conversion_cycle_days`, `working_capital_days`. A label/formula string with unresolved
operands, gross/net capex or balance-sheet temporal role is insufficient. Cited exclusion may
resolve the prerequisite's explicit acceptance alternative, but cannot erase the missing vendor
measurement obligations in Stage 1. The spec's `exceptional_items` shorthand resolves to actual
dictionary id `exceptional_items_before_tax`; the new `other_income_incl_exceptional` row lives
in `config/dictionary/v2/derived.yaml` with units, signed operands and source evidence.
Reconcile its hand-verified addition/counts rather than adding a dangling aggregate id.
Record per-surface scheduling/refusal/provenance defects,
including the four unverified Screener packages. Verify watchlist filings against named periods
and source authority without writing raw manifests.

Verification: independent source review of all 17 dispositions and the inventory;
`uv run pytest tests/fundamentals/test_canon_dictionary_load.py` when a dictionary changes:
next-version load/coverage proves the hand-authored counts and previous version remains readable.

Test seams: public dictionary loader for actual semantic additions; source verification for
declarative/excluded rows, rather than tests that merely restate labels.

Dependencies: None for read-only inventory; D1a dictionary/evidence fix handoff before changing shared artifacts.

Risks: missing vendor evidence stays parked. An unresolved construction is never promoted by numerical agreement.

### Task 2: Establish source-qualified evidence and queue schema

Goal: the existing immutable evidence store can hold multiple vendor surfaces and append-only
queue/disposition records without altering first-party package semantics or old runs.

Stage: `eqos-u0u.3` (shared persistence prerequisite supporting `eqos-u0u.1`; this does not close either stage).

Files:
- Create: `migrations/0006_review_queue.sql`, `src/fundamentals/contracts/review_queue.py`, `src/fundamentals/compare/approval_receipts.py`, `src/fundamentals/evidence/vendor_common.py`, `tests/fundamentals/test_vendor_schema.py`.
- Modify: the shared contract/evidence/run-model/config/store paths in the file map.
- Test: `test_vendor_schema.py`, `test_pg_migrations.py`, `test_evidence_contract_boundaries.py`, `test_compare_runs.py`, `test_compare_config_pins.py`.

Interfaces:
- Consumes: `CaptureRecord`, `CaptureReference`, `Occurrence`, `Interpretation`, `AcquisitionAttempt` including extraction context pin; current run manifests and new qualification fixture evidence; applied migrations 0001–0005.
- Produces: the proposed vendor/common-intake/source-qualified-side/pin contracts, typed corroboration/diagnostic `PairKind` and `SelectionSource.VENDOR_CAPTURE`, `QueueItem`, `QueueDisposition`, `QueueOverlay`, `ApprovalReceipt`/`VerifiedApprovalReceipt`; their immutable SQL identities, checks, references and runtime/privileged permission boundary.

Approach: one schema writer prepares the full 0006 contract before its first commit: source-qualified
result uniqueness/pair lookup, vendor representation checks, extractor/authority pins and queue
keys/dispositions, protected approval receipts/final decisions and explicit runtime refusal of
amount-bearing/final writes. Extend `pair_outcomes.pair_kind` and
`calculation_trace_operands.selection_source` checks for the produced typed values; a vendor
VALUE operand must name its actual selected interpretation or child trace, with
source/surface/capture provenance. Preserve the VALUE-provenance check from 0002.
Keep package-member and alignment-proof checks first-party-only. Migrate old
source identities from their existing capture/occurrence provenance; a synthetic source id is
not an acceptable migration default. Ensure old manifest content digests and replay remain
verifiable through explicit version-aware reads. Source/value identity additions must update both
SQL publication and reconstruction; changing only a Pydantic type loses surfaces on reload.
Generalize native selectors and extractor selection only where vendors need it; retain existing
XBRL/PDF validation. Hand off the common retained-intake interface at this task's end, so
Tasks 3 and 4 do not depend on each other's completed mapping release. All D1a changes are
handed off before these shared files are edited.

Verification: `uv run pytest tests/fundamentals/test_vendor_schema.py tests/fundamentals/test_pg_migrations.py tests/fundamentals/test_evidence_contract_boundaries.py tests/fundamentals/test_compare_runs.py tests/fundamentals/test_compare_config_pins.py`:
upgrade from the real 0005 schema; multiple vendor surfaces and typed pair kinds survive reload;
vendor computed operands round-trip with VENDOR_CAPTURE provenance; runtime final/amount writes
and evidence/queue UPDATE/DELETE fail; producer receipt checks hold; v1 replay/pins remain valid.

Test seams: real PostgreSQL isolated test database, SQL permission/identity constraints,
`EvidenceRepository` generation writes and `RunStore` round-trip publication.

Dependencies: committed root-owned 0005 and stable D1a schema/run/evidence handoff; not vendor acquisition.

Risks: test-first; migration 0006 becomes immutable when committed. Further schema changes use
the next number. This task is one atomic schema/serialization commit group.

### Task 3: Admit authorized retained Screener financials

Goal: eligible raw Screener cells become lossless vendor occurrences and scoped canonical
interpretations; absent/unauthorized/invalid surfaces remain explicit without first-party substitution.

Stage: `eqos-u0u.1`.

Files:
- Create: draft `config/mappings/screener/v2/financials.yaml`, `config/mappings/screener/v2/constructions.yaml`, `config/mappings/constructions/v2.yaml`, `src/fundamentals/evidence/vendor_screener.py`, `tests/fundamentals/vendor_retained_support.py`, `test_evidence_vendor.py`.
- Modify: shared source catalog/mapping hooks only through the contract owner; preserve published mapping v1.
- Test: `test_evidence_vendor.py`, `test_evidence_mapping.py`.

Interfaces:
- Consumes: Task 1 inventory/dispositions, Task 2 vendor contracts, `FinancialsArtifact`/`SectionTable`, raw HTML/schedule JSON and documented source authority.
- Produces: available Screener intake/extraction and `VendorGeneration` in isolated draft-proof contexts; reviewed draft authority/member/construction content for Task 13. This task never pins or publishes the shared mapping-set v2.

Approach: distinguish page, schedule, quarter, annual and ratio surfaces by their actual schema
and request identity. Use raw lexemes, native row/column/JSON anchors, displayed scale/decimals,
exact intervals and actual basis. Revalidate generated section metadata against raw bodies;
neither `complete` nor `verified` proves every section or equivalence. Unregistered surfaces
produce `NOT_AUTHORISED`; identity/schema/partial/parse failures use existing typed outcomes.
Register retained bytes at the actual local time in an isolated store outside `data/raw/`.
`Total Liabilities` maps to no liabilities row; `Borrowings + Other Liabilities` may map only
to `liabilities_incl_nci`, using same-vendor/capture operands. First-party NCI is never added to
the vendor side. Vendor EPS remains related, not equivalent. Preserve unmapped numeric lines.
No Apar Screener result is emitted from the ten other companies' inputs.
Screener Other Income targets `other_income_incl_exceptional`, the evidenced
`other_income + exceptional_items_before_tax` aggregate (spec shorthand `exceptional_items`),
not `other_income` alone. The first-party bridge in `constructions/v2.yaml` computes from
first-party operands with their scoped tiers/traces; vendor-published Other Income remains an
occurrence. Genuinely vendor-computed values use the separate Screener construction artifact
and same-surface/same-capture operands. Bridge/entry evidence cites the spec and retained rows;
absent source discrimination keeps EQUIVALENCE_UNPROVEN. Prove nonzero exceptional-item behavior
through retained evidence/allowed reinterpretation, never label-based equivalence. Draft tests
use task-isolated configuration identities. Task 13 joins all drafts before any v2 first use.

Verification: `uv run pytest tests/fundamentals/test_evidence_vendor.py tests/fundamentals/test_evidence_mapping.py`:
real available page/schedule extraction round-trips through PostgreSQL, source/timestamp refusal
holds, missing values stay missing, Other Income/exceptional and liability/NCI traps behave as
specified. Final v2 integration follows Task 13. Missing Apar and
consolidated-negative captures are reported as parked acceptance cases, not passed or skipped.

Test seams: retained-only adapter → snapshot registration → `EvidenceRepository` occurrences/
interpretations/attempts; no network adapters. Hash mismatch, out-of-root path and unsupported
surface fail before interpretation; registration-before-cutoff eligibility is observable.

Dependencies: Task 2; Task 1 for any added vendor formula; available retained-authority proof for each admitted surface.

Risks: test-first for trust-boundary/temporal behavior. Partial adapter proof does not satisfy the full live stage acceptance.

### Task 4: Connect Tijori and Upstox offline seams with honest evidence gates

Goal: real retained Tijori/Upstox inputs can use the shared vendor contracts, while absent inputs
produce operational outcomes and never qualify definitions or diagnostic source values.

Stage: `eqos-u0u.1`.

Files:
- Create: `src/fundamentals/evidence/vendor_tijori.py`, `vendor_upstox.py`; mapping member paths in the file map only for evidenced entries.
- Modify: None in the shared index/authority artifact; hand reviewed drafts to Task 13's config owner.
- Test: `tests/fundamentals/test_evidence_vendor.py`, `vendor_retained_support.py`.

Interfaces:
- Consumes: Task 2 common contracts/intake; offline Tijori table builders and Upstox statement readers; retained response authority/hash/identity/period/precision proof when available.
- Produces: offline seams and reviewed authority/member drafts for Task 13, explicitly excluded/unproven when evidence is absent; isolated-draft `VendorGeneration` for admissible bytes, otherwise capture-free unavailable/refused attempts; Tijori qualification only after source remeasurement.

Approach: preserve response periodicity: Tijori final annual-table column requires evidence of
TTM interval; Upstox full statements remain annual even for a quarterly request. Response
basis verification is independent of the requested basis/table suffix. Unknown API precision
gives `PRECISION_UNSUPPORTED`. Tijori `qt_c` Net Profit targets
`profit_continuing_after_tax`, never `profit_for_period`; its candidate quarterly consolidated
`in-bse-fin`/zero-discontinued-operations scope stays unproven until the nine real Q3 FY25
measurements at displayed precision establish at least five agreeing companies including a
discriminating case. HFCL, LAURUSLABS, THERMAX and TITAN are explicitly checked.
Upstox summary `operating_profit` targets `profit_before_tax` (pre-associate PBT, inventory
§2a), not EBIT/operating profit or headline `profit_before_tax_incl_associates`; summary `revenue`
targets `total_income`, not `revenue_from_operations`. Both remain EQUIVALENCE_UNPROVEN until
their own surface/schema/basis/period scope has source-backed qualification. A response that
cannot discriminate pre-/post-associate meaning stays unproven/ambiguous with refused qualified
comparison; its PBT label cannot promote the candidate mapping. Numeric Upstox proofs remain
parked with absent retained bodies.
Preserve both key-compatible Upstox summary/full-statement values. Without evidenced
precedence, either disjoint intervals or evidenced contradictory semantics on the same key
gives `VENDOR_INTERNAL_CONFLICT`; ordinary intersecting values with compatible semantics do
not. Prove semantic contradiction with intersecting intervals through retained-source/allowed
reinterpretation, alongside disjoint and ordinary-intersection cases; retain both occurrences.
Neither missing local files nor a request parameter establishes an empty vendor response.

Verification: `uv run pytest tests/fundamentals/test_evidence_vendor.py`: refusal/unavailable
intake uses actual request identities, and every retained-backed acceptance case matches its
source proof. Currently park real TTM, annual-response, empty-response, contradiction and Tijori
qualification measurements because those retained responses are missing; this stage stays open.

Test seams: public offline table/statement parsing → vendor attempt/occurrence storage; reuse
existing parser tests for transport-free seams. New source claims require real retained bodies,
not synthetic parser fixtures or figures copied from research prose.

Dependencies: Task 2 common-intake/contract handoff; independent of Task 3 completion.
Task 13 joins this task's completed draft portion. Numeric qualification additionally requires
authorized retained inputs and does not gate available-seam preparation. No fetch task is included.

Risks: test-first at actual admission boundaries; scaffoldable code is not verified source coverage.

### Task 5: Implement corroboration, pair routing and overlay trust

Goal: every row of the spec's corroboration table is decided in order and every problematic
pair is independently routed, with diagnostics excluded from statuses/completeness/trust.

Stage: `eqos-u0u.2`.

Files:
- Create: `src/fundamentals/compare/routing.py`, `trust.py`, `tests/fundamentals/test_compare_corroboration.py`, `test_compare_diagnostic.py`.
- Modify: `src/fundamentals/compare/tables.py`.
- Test: the two new comparison files plus existing `test_compare_extraction_tables.py`.

Interfaces:
- Consumes: Task 2 source-qualified sides, existing `ComparisonSide`, `pair_outcome`, first-party extraction/derived-extraction statuses, `ComparisonPolicy` v1 threshold, `QueueOverlay`.
- Produces: full `corroboration_status`; typed `QueueItem` proposals from pair/status/occurrence rules; `trusted` evaluation over a named run and explicit overlay time/position.

Approach: keep first-match precedence, especially F INVALID and vendor INVALID, and MISMATCH
over another vendor's AGREE. Independent values alone enter the corroboration state vector.
Route NOT_COMPARABLE even when another vendor gives CORROBORATED. Diagnostic mismatch/anomaly
always routes `PARSE_CHECK_DISAGREE` MEDIUM, taking precedence over generic STRUCTURAL/HIGH;
diagnostic internal conflict is NOT_COMPARABLE/MEDIUM and retains both occurrences. Operational
unavailability remains run-level. Only applicability permits NOT_APPLICABLE; filing-only September
half-year balance-sheet rows need complete/absent counterpart evidence, not failed vendor input.
Trust requires extraction AGREE (or NOT_APPLICABLE with a first-party value), corroboration
CORROBORATED and no open non-diagnostic HIGH item at the overlay position.

Verification: `uv run pytest tests/fundamentals/test_compare_corroboration.py tests/fundamentals/test_compare_diagnostic.py tests/fundamentals/test_compare_extraction_tables.py`:
all 15 ordered conditions (1, 2, 2a, 3, 4, 4a, 5, 6, 7, 8, 9, 10, 11, 12, 13), including
INVALID branches 2a/4a and first-match interactions, and routing precedence; mismatch plus agreement is
CONFLICT; INVALID never becomes FILING_ONLY/NO_SOURCE; diagnostics do not affect trust/completeness.

Test seams: pure dynamic financial decision tables may use typed inputs; retained integration
demonstrations remain separately required in Tasks 6/10. Table tests are not vendor qualification evidence.

Dependencies: Task 2 contracts. Real surface integration depends on Tasks 3–4; pure rule preparation is independent of missing captures.

Risks: test-first; all routes are independent of the final cell status.

### Task 6: Publish and replay vendor runs with an append-only queue

Goal: requested vendor surfaces and failed attempts are pinned and replayed exactly; queue
items share atomic run publication and unchanged evidence reuses the open item.

Stage: `eqos-u0u.3`.

Files:
- Create: `src/fundamentals/compare/vendor_inputs.py`, `queue.py`, `tests/fundamentals/test_compare_queue.py`.
- Modify: shared resolver/engine/run/store/report paths and run/config tests named in the file map.
- Test: `test_compare_queue.py`, `test_compare_runs.py`, `test_compare_config_pins.py`, `test_compare_run_rules.py`.

Interfaces:
- Consumes: Task 2 schema/identities; Tasks 3–4 adapters; Task 13 `PublishedVendorConfig`; Task 11 `FirstPartyGenerationHandoff`; Task 5 corroboration/proposals; explicit `RunScope.vendor_sources` and vendor pins.
- Produces: resolved vendor capture/occurrence/interpretation/attempt and authority/qualification evidence ids in `RunManifest`; immutable source-qualified results and pairs; atomic queue records; deterministic `QueueOverlay` reads.

Approach: resolve each source × surface × entity × period × basis × framework independently
under cutoff, mode and extractor/context pins. Latest eligible failed attempt prevents stale
successful vendor resurrection; demonstrated NOT_PUBLISHED gives no value only with source
evidence. Select no interpretations outside requested sources. Replay uses only manifest ids
and content pins, including failed/capture-free attempts and qualification-condition evidence.
Non-diagnostic UNAVAILABLE makes INCOMPLETE even if another vendor determines corroboration;
diagnostic failure is visible without changing run completeness. Preserve first-party
representative selection and report other-representation vendor pairs as diagnostics when
extraction is not AGREE. Vendor computed values use operands from the same vendor surface and
capture, with normal trace/tier/period checks; never use filing operands on the vendor side.
Persist runs, values, pairs and queue proposals in one transaction with current retry semantics.
Queue identity is measurement key + source-qualified pair/extraction + outcome + input hash;
new inputs produce a linked new item. Store no review state in the run identity or immutable result.
Extend existing `request_for` with keyword `vendor_sources: tuple[VendorSurfaceRequest, ...] = ()`
and content-pinned vendor extractor selection; preserve first-party `sources` and existing
`versions: ConfigVersions | None` compatibility. Extend `ConfigVersions` with the selected
source-authority/vendor bundle version; resolve dictionary, mapping, normalisation, definition
and policy choices together. `execute_run` consumes the request's exact pins and refuses
draft/unpublished/mismatched bundles. API defaults remain explicit compatibility v1 first-party
requests; vendors require an explicitly published vendor bundle/mapping version. Unknown or
unrequested surfaces never enter resolution. Task 11 supplies appended v2 first-party records;
v1 interpretations cannot supply v2 by weakening exact pin filters.

Verification: `uv run pytest tests/fundamentals/test_compare_queue.py tests/fundamentals/test_compare_runs.py tests/fundamentals/test_compare_config_pins.py tests/fundamentals/test_compare_run_rules.py`:
failure → INCOMPLETE; failed attempt replay → UNAVAILABLE; unchanged concurrent requests → one
run/item; rollback/unreachable database → no partial result/queue; pin change → new run;
diagnostic failure → complete run; UNMAPPED → LOW; typed/source-qualified corroboration and
diagnostic pairs and vendor-computed trace provenance survive replay; public version/surface
selection rejects unknown/unpublished inputs; surface filters and input hashes survive replay.

Test seams: retained available Screener → PostgreSQL run/results/queue → manifest-only replay;
withhold or mark a real capture for failure rather than inventing financial values. Full diagnostic
trusted-cell source proof is parked until independent vendor plus Upstox evidence is available.

Dependencies: Tasks 2, 3, 5, 11 and 13; Task 4's actual numeric surfaces additionally require
their evidence. Stable D1a run/replay handoff.

Risks: test-first; avoid nested pool checkout or dropping failed attempts because no package owns them.

### Task 7: Expose review commands, overlay reports and exit statuses

Goal: analysts can inspect each source and pair, record auditable dispositions and view trust
at a named overlay without editing old results or inventing an approval.

Stage: `eqos-u0u.3`.

Files:
- Create: `src/fundamentals/api/compare_queue_cli.py`.
- Modify: `src/fundamentals/api/compare_cli.py`, `src/fundamentals/compare/run.py`, `compare/report.py`, `compare/queue.py`, `compare/approval_receipts.py` through their single owner.
- Test: `tests/fundamentals/test_compare_queue.py`.

Interfaces:
- Consumes: Task 6 public request/config/run/queue/overlay, `RunExitStatus` (0 success, 3 success with open HIGH, 4 INCOMPLETE, 5 failure), Task 2 protected receipt/role boundary, actual independently verified reviewer or owner evidence, `QueueDisposition`, `DefinitionSet`.
- Produces: extended `fundamentals compare run` vendor/version interface; `compare queue list`, `compare queue propose-disposition`, `compare queue record-disposition --receipt <id>`, and `compare interpretation approve --receipt <id>`; trusted `produce_approval_receipt` composition interface and database-backed `verify_approval_receipt`; overlay-time/position reports and operational/diagnostic failures.

Approach: list/filter severity/status/run; require item id, disposition kind, verbatim reason,
actual decider/evidence and recorded store time. Runtime callers may submit amount-free
proposals only. `produce_approval_receipt` consumes a trusted coordinator context and immutable
review/ruling evidence, checks the exact subject/proposal/subject digest, and writes through
the already authenticated `PgRole.MIGRATOR` connection. Runtime cannot call this producer or
write receipts/final decisions. The trusted context is constructed by the coordinator from
the actual independent review invocation/result or active direct owner instruction, never
from a CLI actor string or a JSON deserialization. SQL records authenticated `session_user`
and store time and restricts receipt/final writes to the existing privileged role. A caller
cannot gain approval by recomputing a SHA-256, choosing `--owner`, replaying another proposal's
receipt or presenting a review of another sealed digest. `verify_approval_receipt` reloads the
append-only protected row and bound evidence; final commands require that verified receipt
plus privileged authentication, honor REJECT without accepting the proposal, and reuse an
identical already recorded decision idempotently. Owner overrides bind the actual owner ruling;
amounts must resolve to its explicitly bound value or a code calculation trace. No new
credential/role/service/network is introduced. D3 consumes this standalone boundary later.
If actual independent review/owner evidence is absent or unverifiable, refuse the decision
and keep the corresponding bounded acceptance open; this never authorizes a fabricated receipt.
Interpretation approval appends its record/interpretation and never overwrites history. `ACCEPTED_AS_DEFINITION`
closes review only through its actual disposition; it proposes an evidenced definition for a
new immutable definition set, changes no result, and only a new run pinning that set may classify
a definition difference. Do not accept a freely supplied amount as code computation. Queue
overlay affects live trust and exit-high status, never run identity/replay classification.
The public run CLI adds repeatable `--source <first-party-surface>` and
`--vendor-source <source-id:surface>` plus explicit `--mapping-set-version`,
`--dictionary-version`, `--normalisation-policy-version`, `--definition-set-version`,
`--source-authority-version`, `--comparison-policy-version`, `--rounding-policy-version` and
`--alignment-rules-version` through `ConfigVersions`.
No vendor flag keeps current v1 first-party-only behavior. Supplying vendor surfaces requires
an explicitly selected Task 13 published bundle; omission, unknown surface or incompatible
version combination fails closed. The CLI passes these exact values into Task 6's extended
`request_for` and preserves them in the manifest; it never silently stays on v1 or expands
unrequested vendors. The available Screener registration → explicit v2 vendor CLI run is
proved independently of absent Tijori/Upstox positives; their requested failures remain visible.

Verification: `uv run pytest tests/fundamentals/test_compare_queue.py`: immutable results before/
after authenticated ACCEPT/REJECT; new set produces a new run; as-of overlay selection;
runtime final/amount writes and forged/wrong-subject/wrong-digest receipts are refused;
an actual review-bound receipt supports ACCEPTED_AS_DEFINITION without waiting for D3;
CLI returns all four existing exit categories; report prints source role/surface, values/states,
both statuses, pairs, difference/gap, provenance, queue and overlay position. Add actual CLI
available-retained registration → published-v2 vendor run → replay, explicit v1 first-party-only
compatibility, new definition-set/new-run and unknown/unrequested-surface/version refusal cases.

Test seams: actual CLI dispatch and authenticated runtime/migrator test connections on isolated
PostgreSQL; trusted coordinator evidence → protected receipt → final decision/overlay; raw
caller metadata is refused and cannot manufacture the trusted context. Verification must
exercise SQL privileges as well as application checks, including matching forged digests.

Dependencies: Tasks 2 and 6 and actual external review evidence for each final decision.
D3 and D6.3 later consume this boundary; neither is a prerequisite for D1b dispositions.

Risks: test-first for append-only/authentication/approval boundaries. A protected producer must
verify actual approval evidence; privileged login alone is not proof of a reviewer/owner decision.

### Task 8: Record the financial-data register amendment

Goal: the amendment names exactly the two data-spec changes and carries actual approval evidence.

Stage: `eqos-u0u.4`.

Files:
- Create: `docs/blueprint/amendments/2026-10-11-data-layer-postgresql.md`, `tests/fundamentals/test_amendment_records.py`.
- Modify: None.
- Test: `test_amendment_records.py` (data-layer record).

Interfaces:
- Consumes: data-spec Decision-register amendment; canonical register §G; actual fresh review/approval text/date/identity from the coordinator.
- Produces: linked amendment record for the PostgreSQL financial-data override and full-Indian-market financial-data target, with approval references usable by later gates.

Approach: use the owner goal's fresh Codex session review route. “Panel” means the current
single-reviewer approval under the dated roadmap ruling; do not fabricate multi-family reviews.
Preparation is independent of vendors, but missing approval leaves the record proposed.

Verification: `uv run pytest tests/fundamentals/test_amendment_records.py -k data_layer`:
exactly two changed items, correct spec/register links and real approval evidence/date/verdict.

Dependencies: None for draft; independent reviewer approval for stage acceptance.

Risks: no authority expansion to unattended capture, automated initiation, foreign or financial-sector adapters.

### Task 9: Freeze the complete source-verified Stage 1 oracle

Goal: an independent verifier hand-authors every applicable row and fixture outcome from sources,
obtains approval and commits the manifest before any e2e test is created.

Stage: `eqos-u0u.5`.

Files:
- Create: `tests/fundamentals/fixtures/data_foundation/stage1_manifest.yaml`, `tests/fundamentals/test_frozen_manifests.py`.
- Modify: Task 1 source inventory only through its owner as evidence is verified.
- Test: `test_frozen_manifests.py`.

Interfaces:
- Consumes: Task 1 complete verified source inventory and all 17 dispositions; approved dictionary/mapping definitions; actual retained bytes/rights/time proofs; source-backed fixture contracts below; independent review text.
- Produces: frozen `stage1_manifest.yaml` with source paths/capture hashes/anchors, per-company entity/period/basis/settings/applicability, values/units/intervals/tiers, pair outcomes/reasons/triage, every source state, both statuses, queue/trust, run status and pinned versions; hand-verification and approval records; prior manifest commit evidence.

Approach: source verification may proceed before implementation; no result generator or test
helper may write the oracle. Freeze only when every mandatory source obligation is evidenced.
Record fixture transformations of real evidence and the exact cutoff/mode/registration order.
An independently derived expectation that happens to differ from implementation is retained
and investigated. Missing inputs currently park full freezing/approval; never freeze a reduced
happy-path manifest as Stage 1 completion.

Verification: `uv run pytest tests/fundamentals/test_frozen_manifests.py -k stage1`:
hashes/anchors/hand-verification/approval resolve and full manifest coverage exists. The commit-order
check first accepts an approved committed manifest while the e2e path has never existed; once
Task 10 adds that path, it proves strict ancestry/order, not tied commit timestamps. Stage 5 cannot
pass with missing mandatory source proof.

Test seams: real files + approved records + Git history read-only; expected source figures are
independent of adapters/run output. No e2e file is created, even as scaffolding, in this task.

Dependencies: Task 1 evidence completion, Task 13 published source definitions from Tasks 3–4,
Task 11 generation/qualification provenance, actual independent approval and coordinator commit.
Expected figures have no dependency on code output.

Risks: oracle contamination or same-commit creation defeats independence. Full fixture list is mandatory.

### Task 10: Match every Stage 1 row and demonstrate the analyst report

Goal: all eleven named company runs and all required transformed fixtures match the approved
manifest exactly, and the Apar CLI report presents every source/status/queue outcome.

Stage: `eqos-u0u.6`.

Files:
- Create: `tests/fundamentals/test_data_stage1_e2e.py`.
- Modify: retained test support only through its owner, without writing expected answers.
- Test: `test_data_stage1_e2e.py`, `test_frozen_manifests.py`.

Interfaces:
- Consumes: Task 9 previously committed manifest; Tasks 3–7 integrated adapters/run/report/queue; Task 8 approved amendment; Task 11 exact-version first-party generation/qualification, Task 13 published config; stable D1a calculation/selection/replay behavior.
- Produces: exact every-row evidence → results → queue → report/replay proof and D1b exit evidence.

Approach: test every applicable dictionary instance, including dimensional and derived rows,
not selected headline fields. Compare all source states, reasons, values/units/intervals, both
statuses, pairs, traces, queue proposals and run status. Public report includes overlay time.
Use one entity per run and explicit request surfaces/cutoffs. Required missing inputs fail the
fixture preflight; no marker exclusion, synthetic substitution or skip can satisfy acceptance.

Verification: `uv run pytest tests/fundamentals/test_data_stage1_e2e.py tests/fundamentals/test_frozen_manifests.py`:
exact match with no missing applicable rows; Apar PBT 340.56/340.53 crore, headline 340.53,
OPM 8.06% trace and extraction headline agreements; all special outcomes below. The same run
is shown by `uv run fundamentals compare report --run <persisted-run-id>` inside the test's
isolated database environment. Run the full stable integration gate once after sources freeze.

Test seams: real retained files → isolated PostgreSQL → CLI report/queue → manifest-only replay;
database unreachable and concurrent rerun boundaries are observed without touching `equity_os`.

Dependencies: Tasks 3–9, 11 and 13 complete, reviewed and committed where required; Task 12's
verifier behavior deliverable; D1a full acceptance/fix handoff. Missing mandatory vendor
evidence keeps this task parked. Task 12's full project command may still report later NOT BUILT.

Risks: test-first after the manifest commit; a rehearsal or incomplete vendor run is not D1b exit.

### Task 11: Append matching-version first-party generations

Goal: the joined vendor mapping-set version has real first-party interpretations and scoped
qualification/alignment evidence, while prior v1 runs and historical cutoffs remain honest.

Stage: `eqos-u0u.1` (first-party handoff prerequisite for vendor comparison).

Files:
- Create: `tests/fundamentals/test_first_party_mapping_generation.py`.
- Modify: `src/fundamentals/evidence/first_party_ingest.py`, `capture_interpretation.py`, `alignment.py` only where needed; repository/resolve handoffs through the shared owner.
- Test: `test_first_party_mapping_generation.py`, `test_evidence_reprocessing.py`, `test_compare_runs.py`, `test_compare_config_pins.py`.

Interfaces:
- Consumes: Task 13 `PublishedVendorConfig`, retained intake and reusable first-party occurrences; actual D1a ingest/qualification/alignment contracts and exact mapping/normalisation/extractor filters.
- Produces: `FirstPartyGenerationHandoff` with package/source/capture ids, reused occurrence ids, new mapping-v2 interpretation/context-qualified attempt ids, actual recorded times and content-pinned qualification/alignment evidence; reproducible matching-version selection.

Approach: use current `ingest_first_party`/`interpret_generation` under the published mapping
version. Reuse original bytes/occurrences only when their extractor/context identities permit;
append new interpretations, qualification records and attempts when context changes. Re-extract
when actual extractor/content pins require it. Requalify inherited first-party mapping scopes
and filing-specific alignment against the same source proof and exact new interpretation ids;
do not copy an old qualification reference that resolves under incompatible pins. Recorded-at
uses the actual store time, never relabels/backdates v1. AS_KNOWN before new interpretation
registration cannot select v2; a later eligible cutoff or explicitly retrospective request
can, with the mode displayed. Preserve exact pin filtering and v1 manifest replay from v1 ids.
The generation owner supplies ids by repository reads plus `IngestReport.attempts`; the current
report does not already expose a tuple of interpretation ids. If Q4/FY or FY27 files are selected,
their unsupported SEBI taxonomy/PDF revenue prerequisite (`eqos-51d`/PREP-1) must have actual
fresh extraction proof; otherwise park those selected fixtures rather than inheriting the Q2 tracer.

Verification: `uv run pytest tests/fundamentals/test_first_party_mapping_generation.py tests/fundamentals/test_evidence_reprocessing.py tests/fundamentals/test_compare_config_pins.py`:
producer-local published-v2 first-party generations have matching pins and qualifications;
v1 ids remain selectable under v1 pins; early AS_KNOWN excludes late v2 interpretations;
same pinned re-ingest is idempotent; new context/extractor requires its own generation;
no mutation of prior occurrences/interpretations. Task 6 and phase acceptance require the
first-party+available-Screener run and identical v1 run replay after joining this producer handoff.

Test seams: retained first-party ingest → repository generation/qualification ids → exact-version
selection on isolated PostgreSQL. Task 6 consumes these ids for integrated vendor run/replay.

Dependencies: Task 13 joined publication and stable D1a first-party handoff; Task 1 source coverage.

Risks: test-first; using v1 records as if they had v2 provenance silently erases knowledge-time truth.

### Task 12: Add the project verification command

Goal: one command reports every required D-phase exit, shared governance check, quality gate
and pilot outcome, returning nonzero for any FAIL or NOT BUILT without inventing later success.

Stage: `eqos-u0u.6` (D1b-owned verifier deliverable; eventual PREP-8 extends its pilot coverage).

Files:
- Create: `scripts/verify_project.sh`, `tests/fundamentals/test_verify_project.py`.
- Modify: None outside this owned verifier surface.
- Test: `test_verify_project.py`.

Interfaces:
- Consumes: actual roadmap/core/backend-roadmap exit paths; shared `test_frozen_manifests.py` and `test_amendment_records.py`; four authoritative quality commands; pilot acceptance path when built.
- Produces: executable `scripts/verify_project.sh` with PASS/FAIL/NOT BUILT per named part and nonzero unless every required part passes; PREP-8 handoff for later pilot/phase additions.

Approach: explicitly register D1a, D1b, D2–D9 and the pilot, not only discovered test files.
The currently built exit targets are `tests/fundamentals/test_compare_tracer.py` and, once
Task 10 lands, `tests/fundamentals/test_data_stage1_e2e.py`; shared targets are
`tests/fundamentals/test_frozen_manifests.py` and `tests/fundamentals/test_amendment_records.py`.
D3 additionally registers `test_ledger_export.py` as required by the core definition. Take
later exit names from the corresponding approved phase plan/roadmap; an unresolved pilot
test path is a named NOT BUILT slot, never an invented callable path or an omitted part.
Run built phase exits and available shared governance checks; mark absent exit/governance/pilot
paths NOT BUILT. Run full pytest, strict mypy, Ruff check and format at stable integration,
without retained/PG exclusions. Continue collecting results after a failed part and return
nonzero if any required part failed or is absent. At D1b, later phases/pilot truthfully remain
NOT BUILT; that nonzero is expected incomplete-project evidence, not a failure of the verifier
implementation or a reason to claim project completion. PREP-8 extends the declared registry
as later exits/pilot land; no later feature is built by this task.

Verification: `uv run pytest tests/fundamentals/test_verify_project.py`: subprocess command
contract with controlled command outcomes proves missing part→NOT BUILT/nonzero, failed
part→FAIL/nonzero, continuation to remaining parts, all present/passing→zero, actual command
targets/no marker exclusions and a declared pilot slot. On stable D1b integration run
`scripts/verify_project.sh` once: report actual built exits and later NOT BUILT/nonzero.

Test seams: script subprocess/command dispatch, using an injected test-only command runner or
PATH shim; these outputs test verifier control flow and are never phase acceptance evidence.

Dependencies: None for implementation/control-flow proof. The stable real run follows Tasks
8–10 as a coordinator phase-gate action, not a prerequisite for completing this task.
Task 10 consumes only this implemented/proved command, not its later full-project PASS.

Risks: an absent registry slot or skipped test cannot turn unfinished project work into success.

### Task 13: Join and publish the complete vendor configuration

Goal: all reviewed member/authority drafts join into one immutable release before any shared
v2 pinning, first-party re-interpretation or vendor run; later additions use a new version.

Stage: `eqos-u0u.1`.

Files:
- Create: final `config/mappings/v2.yaml`, `config/source_authority/v1.yaml`, `tests/fundamentals/test_vendor_config_publication.py`.
- Modify: draft mapping/construction paths from Tasks 3–4 only through the sole config owner before this publication; config-loader publication/refusal hooks through Task 2's owner.
- Test: `test_vendor_config_publication.py`, `test_evidence_mapping.py`, `test_compare_config_pins.py`.

Interfaces:
- Consumes: Task 2 common contracts, Task 1 dictionary/dispositions, Task 3 Screener and first-party bridge drafts, Task 4 offline-vendor authority/member drafts plus explicit evidence gaps.
- Produces: `PublishedVendorConfig`: joined mapping index/member hashes, authority/dictionary/
normalisation/extractor pins, approved source/surface inclusion/exclusion decisions and actual publication evidence.

Approach: Tasks 3 and 4 both start from Task 2's common-intake handoff and produce drafts;
neither may pin shared v2, complete an authoritative v2 generation or alter another writer's
draft. Their isolated test configs carry separate draft identities and test-store pins. The
config owner joins every member/construction and authority draft, validates no unresolved
reference, reviews the combined resolved hash and included/parked surface ledger, then freezes
and commits the joined bundle before its first final-v2 use. Missing source bodies permit
explicitly unavailable/excluded mappings, not fabricated precision/qualification entries.
They still block their positive stage acceptance. Task 13's barrier is completed draft/contract
review, not falsely claimed numeric completion of Task 4. Published v2 is thereafter immutable:
new Tijori/Upstox evidence or mapping qualification content gets v3 or a later version, complete
fresh generations and new runs. Source authority likewise gets a new version when its content
changes. Task 11 and Task 6 consume only the released bundle, never a worker's mutable index.

Verification: `uv run pytest tests/fundamentals/test_vendor_config_publication.py tests/fundamentals/test_evidence_mapping.py tests/fundamentals/test_compare_config_pins.py`:
early shared-v2 use is refused; the joined released index resolves exact member hashes;
post-publication mutation is drift/refused; a later version produces a new run while prior
manifest replay still uses original members/pins. Missing vendor source proof is explicitly unavailable.

Test seams: actual mapping/config loaders and version-pin store on isolated PostgreSQL, with
draft/final/version-drift artifact states; no value expectation is generated by the publisher.

Dependencies: Tasks 1–2, Task 3 complete drafts and Task 4 completed draft/contract portion;
independent approval and coordinator release commit. Numeric missing-capture obligations remain parked.

Risks: test-first for publication/drift behavior. One atomic joined configuration release is
required; a single writer alone does not establish a safe publication point.

## Required evidence contracts for the frozen oracle

| Acceptance obligation | Independent source proof / expected behavior | Task coverage / current gate |
|---|---|---|
| Every applicable row for Apar and ten companies | Dictionary version/template members, issuer basis/settings, exact source period, named rows/anchors, complete source vectors and independent values/statuses; no source omissions hidden by a curated row list | 1, 9, 10; full completion parked |
| Apar opex vs Screener | Actual Apar Screener Expenses lexeme/scale/precision and capture hash; first-party total expenses, finance and depreciation anchors; hand exact computation/propagated intervals; pre-register difference/gap/outcome. An unexplained residual is ANOMALY, never an invented definition difference | 1, 3, 9, 10; Apar Screener missing |
| Tijori `qt_c` remeasurement | Nine real Q3 FY25 responses + matching filings, displayed precision and zero-discontinued-operation evidence; retain old 0.5-crore measurement as superseded, never as qualification. At least five agreeing including a discriminating case gives demonstrated scope; otherwise agreeing pairs stay AGREE_UNQUALIFIED | 4, 9, 10; Tijori inputs missing |
| THERMAX revenue | Filing and real Screener/Tijori quarter lexemes/anchors/precision; hand interval gap and relative difference against 0.5% policy; ANOMALY/MAGNITUDE/MEDIUM with unresolved cause | 3–5, 9, 10; Screener side available subject to authority, Tijori proof parked |
| Failure/negative-attempt fixture | Withhold or mark an actual independent-vendor capture; retain acquisition/extraction request identity and attempted store time; later failed attempt supersedes successful surface availability. Only mapped vendor failed → UNAVAILABLE; another valid vendor may determine corroboration but the run remains INCOMPLETE; manifest-only replay reproduces failure | 3, 5–7, 9, 10; available Screener can support failure seam, multi-vendor demonstration parked |
| True NOT_PUBLISHED | Retained response establishing source absence after a complete capture; cells have no value and run stays complete. Missing local files cannot satisfy this fixture | 4, 6, 9, 10; response evidence parked |
| Trusted diagnostic MEDIUM fixture | Actual first-party aligned pair + independently demonstrated Screener/Tijori agreement establishes CORROBORATED; actual Upstox disagreement on the same key is structural. Queue has only MEDIUM PARSE_CHECK_DISAGREE, cell stays trusted, diagnostic failure does not make INCOMPLETE | 4–7, 9, 10; Upstox and complete independent qualification missing |
| NETWEB consolidated refusal and Upstox internal conflict | Standalone-only issuer evidence; actual degenerate Screener/empty Upstox bodies; NETWEB/POLYCAB key-compatible surface values; absent evidenced precedence, disjoint intervals or evidenced contradictory semantics (even with intersecting intervals) gives NOT_COMPARABLE/VENDOR_INTERNAL_CONFLICT/MEDIUM; ordinary compatible intersections do not; retain both occurrences | 2–6, 9, 10; negative and Upstox bodies missing |
| Other Stage 1 regression fixtures | Actual capture transformations and evidence for revision/correction/ambiguity/family independence; Q4 incompatible revision; current/opening receivables/cash roles; segment member/elimination basis; invalid/missing/undefined operands; unproven operand tiers; adjacent exact counts; low unmapped item; cutoff eligibility; concurrent reruns; runtime immutability; unreachable DB | D1a retained proofs + 2–7, 9, 10; preserve and integrate, never synthesize source readings |

## Stage coverage and parallel ownership

| Seeded acceptance | Tasks | Closure condition |
|---|---|---|
| `eqos-u0u.1`: vendor adapters and authority | 2–4, 11, 13 | Joined immutable config, matching-version first-party generations and full vendor acceptance including real Tijori/Upstox/NETWEB proofs; currently open |
| `eqos-u0u.2`: corroboration/trust/diagnostics | 5–6 | Table proof plus retained integration, including real NETWEB/POLYCAB Upstox conflicts; pure rules can proceed |
| `eqos-u0u.3`: queue/dispositions/exit statuses | 2, 6–7 | Authenticated approval receipts, atomic queue, failure replay, accepted/rejected dispositions/new definitions and all exit categories; no D3 prerequisite |
| `eqos-u0u.4`: register amendment | 8 | Exactly two changes and actual fresh approval; independent of vendors |
| `eqos-u0u.5`: frozen manifest | 1, 9 | Full source verification, preregistered opex and Tijori rule, approval and earlier manifest commit |
| `eqos-u0u.6`: Stage 1 e2e | 10, 12 | Exact full manifest/report and project-verifier behavior; no parked mandatory Stage 1 proof. Later project NOT BUILT stays nonzero |
| `eqos-u0u.7`: deferred rows | 1 | All 17 added with evidenced construction or excluded with cited reason; never extrapolated |

Tasks 1, 8 and Task 12's verifier implementation can proceed independently. Task 5's pure
tables consume Task 2's reviewed contracts. Tasks 3 and 4 start together after Task 2's common
intake handoff and produce isolated drafts/proofs; Task 13's sole config owner joins all drafts
and approves/freezes/commits the bundle before any final v2 pinning. Then Task 11 appends
matching-version first-party generations, Task 6 integrates vendor runs and Task 7 exposes
the public/authenticated decision boundary. Task 9 source verification is independent of code,
but full freezing remains evidence-gated. Task 10 waits for the prior manifest commit and
Task 12's proved command; the coordinator runs that command after stable integration and
reports later NOT BUILT truthfully. There is no D1b → D3 → D1b approval dependency.

## Fail-closed build notes and verification handoff

- 2026-10-13, Task 12: the approved pilot exit filename is unresolved. The production verifier
  keeps an explicit Pilot NOT BUILT slot without runtime path overrides; only an isolated
  control-flow test copy registers a constructed future target. This preserves the PREP-8 gate.
- The Task 8/12 red proofs preceded implementation and remained honest after format-only line
  wrapping. The coordinator reconstructed both exact pre-format files, matched their original
  sealed SHA-256 hashes, and proved identical parsed ASTs before resealing the formatting hashes.
  No fixture, assertion, node id or recorded red outcome changed; no historical D1a red proof
  is inferred from these D1b proofs.

The [2026-10-13 activated goal](../../../goals/2026-10-13-autonomous-backend-completion.md)
supersedes the [handoff](../handoff-codex-2026-10-13.md)'s one-at-a-time schedule and permits
parallel preparation/relevant verification. It preserves hard protections, genuine producer/
consumer contracts, fresh plan review, stage red proofs, manifest order and full exit gates.
Older project-overlay “pre-code” claims and roadmap v1 counts do not override the current source
tree or 259-row manifest. Root obtains independent review, approval, commits and Beads updates;
this plan is not self-approved and this planning task creates no acceptance test or oracle.

Before dispatching any implementation stage, its test owner writes the relevant failing behavior
proof and the coordinator records `scripts/verify.sh red <slice> <pytest-target>...`.
Use distinct slices `d1b-vendor-schema`, `d1b-screener`, `d1b-vendor-offline`,
`d1b-corroboration`, `d1b-queue`, `d1b-cli`, `d1b-amendment`, `d1b-manifest`, `d1b-e2e`,
`d1b-first-party-v2`, `d1b-project-verifier`, `d1b-config-publication`.
No-test collection, unavailable database or absent mandatory retained input is an infrastructure/
evidence block, not a valid red behavior proof. Already implemented rules use the existing
characterization proof; new acceptance nodes must fail for missing behavior. Never add tests
that assert only a declarative name to manufacture red evidence. Park source-specific cases
with exact missing prerequisites while preserving the full stage acceptance obligation.

During implementation use focused integration/e2e commands above, plus scoped Ruff/format and
strict typing on changed source. Do not repeat the full suite per trivial change. When extractor
sources, contracts and migration inputs are stable, the coordinator runs the full four checks
from the handoff and `scripts/verify.sh gate <slice>` with its genuine saved red proof. Missing
historical D1a red proof remains disclosed; no D1b gate inherits a fictitious proof. Any current
known baseline failures are established from fresh evidence, not the handoff's stale count.
The complete retained/PG integration gate and D1b exit remain required; filtered runs prove
only their stated scope. No live fetch, credential exposure, raw mutation or application DB
access is an acceptable response to a blocked fixture. Record the reason and continue the next
independent eligible task.

At closure obtain the fresh exhaustive phase review and critical review required by the goal;
close each stage only when its exact live acceptance holds. D1b closes only with Task 10 green,
approved amendments/manifest, source-backed fixture coverage and stable integration proof.
Until the missing evidence is available under renewed authorization, report usable seams and
parked obligations separately and keep dependent full Stage 1 acceptance open.

### Paused scoped checkpoint — 2026-10-13

The owner requested completion of existing work and a pause. Tasks 2–5 are frozen and
independently approved within the scopes below and committed. The final formal integration
attempt remains FAIL/STOP; that verdict is preserved. Start no new implementation, source measurement or joined
configuration publication. Resume normal bounded execution only after an explicit resume or new task.
Checkpoint commits: Task 2 `119ae48`, Task 5 `fdae6ee`, Task 3 `7489b8d`, Task 4 `1eeaf69`;
each has a separate committed handoff entry. Migration `0006` is now immutable. Final coverage
suite: 2,877 passed / 1 failed / 8 existing optional skips; all 74 original D1b RED nodes passed
and all current seals match. Full Ruff lint/format and strict mypy pass. The full gate is not PASS.

D1a is verified complete under the recorded four-check/tracer/independent-review closure route.
Its historical red proof is absent; D1b red evidence does not retroactively repair that history.
Independent [schema approval](../reviews/D1b-schema-review.md) covers Task 2 and addresses S1–S5.
Independent [batch approval](../reviews/D1b-batch-review.md) covers Tasks 3–5 and addresses M1.
Together these approve a scoped checkpoint, not full stage acceptance or D1b closure.

| Task | Approved checkpoint | Remaining acceptance boundary |
|---|---|---|
| 2 | Source-qualified contracts, migration `0006`, legacy upgrade/replay compatibility, common retained intake and protected receipt seams | Actual Task 7 trusted-authenticator composition and Task 6 integrated run/queue behavior |
| 3 | Available retained Screener page/schedule extraction, real local registration clocks and isolated draft mappings | Joined v2 publication, source-native liabilities construction, Apar capture and demonstrated vendor equivalence |
| 4 | Capture-free unavailable/refused generations and guarded offline Tijori/Upstox parser wiring | Real authorized bodies, numeric/TTM qualification, true absence and internal-conflict proofs |
| 5 | Ordered pure corroboration, independent pair routing, named-overlay trust and diagnostic-role repair | Persisted queue/overlay reader and retained multi-vendor run/replay integration |

Fail-closed decisions retained at this checkpoint:

- Missing authorized local bindings produce capture-free `FAILED` → `UNAVAILABLE`; they never
  establish `NOT_PUBLISHED`. Unknown/incompatible authority is refused; present bindings cannot
  be relabelled missing. Persistence alone supplies actual `eqos.store_now()` attempt times.
- Screener EPS remains `RELATED_NOT_EQUIVALENT`; other draft meanings remain unproven. Total
  Liabilities stays unmapped. Borrowings + Other Liabilities needs reviewed source-native operands;
  false canonical mappings or first-party NCI cannot supply that vendor construction.
- Missing Apar Screener, real Tijori/Upstox measurements and NETWEB negative responses leave
  mandatory source proofs and the complete eleven-company oracle open. Pure constructed cases
  prove rule behavior only. Retrieval metadata never supplies historical first-seen/publication time.
- Protected SQL roles and proposal/amount seals are proved within Task 2's scope. Nominal Python
  capabilities and constructed test authenticators do not prove real owner/reviewer authority.
  Task 7 still requires trusted authentication; Task 13 alone joins and publishes shared v2 drafts.

Red-proof disclosures: initial red outcomes remain preserved. Task 2's explicitly authorized
fixture reopening corrected real stored ids/provenance without weakening values, node ids or
round-trip/refusal assertions; corrected affected nodes still failed under unchanged `0001`–`0005`.
Task 5's lint cleanup reconstructed the exact original, matched its sealed hash and proved an
equivalent normalized AST; the diagnostic repair has its own genuine red regression. The
coordinator completed the changed-test hash reseals and retained original/reopening evidence.
Task 2 generation scope has an exact recovered sealed preimage with identical whole-module AST;
the original SQL binding file is an exact final prefix, with added S5 cases having their own RED proof.
Task 3's exact original ten-case file was recovered and its sealed SHA and all original helper/test ASTs verified; fourteen appended focused characterization cases do not acquire retrospective RED status. The extended file and retained support are now protected by the coordinator reseal. Task 8/12 format-only reseals remain disclosed above; none constitutes historical D1a red proof.

Source reports remain untracked under `scratchpad/execution/data-foundation-autonomous-2026-10-13/`:
`d1b-task2-report.md`, `vendor-screener-report.md`, `offline-vendor-report.md` and
`d1b-corroboration-report.md`. Durable independent reviews above carry the scoped approval.
Remaining implementation includes Tasks 6/7 run, queue and authenticated CLI integration;
Task 13 joined publication; Task 11 matching-version first-party generations; and Tasks 9/10
the source-verified approved manifest followed by its e2e proof. Preserve genuine dependencies,
prior manifest commit order and all missing vendor obligations before closing any full stage.

Formal gate stop, preserved at pause:

- `scripts/verify.sh gate d1b-vendor-schema` exited 3/STOP. Privacy matches were traced to
  constructed `1010`/`1200` monetary operands, the source-read HFCL Sales oracle `1012`, and
  generic `identity_strength: configured_url_only` source code. The last match came from a long
  indented source line becoming a short generic pattern after whitespace stripping. No private
  capture body, issuer id or credential was identified in those matched lines. `eqos-490` records
  a narrow reviewed scanner-contract follow-up; no gate rail was disabled, no PASS inferred, and
  no post-commit empty-diff rerun used to conceal the original STOP. The independently approved
  offline scope was inspected as unaffected and committed; the full formal acceptance stays held.
- The sole suite failure was the unchanged existing
  `test_refused_retained_cutoff_preserves_database_and_existing_report[False-cutoff1]`. All four
  parametrizations passed with the same coverage option on the focused rerun (1.26s). Cause is
  unknown; an unclosed SQLite ResourceWarning is an observation, not a proven cause. `eqos-hdz`
  preserves the investigation without weakening cutoff/database/report assertions.
- The real project verifier recorded D1a and amendment PASS, 12 NOT BUILT obligations and a
  stale enum-helper failure. Its fresh focused rerun passed; the subsequent coverage suite also
  passed that node. The coverage-suite cutoff failure and privacy STOP remain separate unresolved
  results. No full project or D1b acceptance is claimed.
- Do not start another batch while paused. After explicit resume, resolve these recorded gate
  findings before stable acceptance; then resume Tasks 13/11/6/7 and the evidence-gated manifest
  tasks under their actual producer/consumer contracts. Missing vendor source proofs stay parked.

### Resume investigation — 2026-10-13

The owner explicitly resumed the goal. The paused checkpoint above remains historical evidence;
normal bounded execution begins with the recorded gate findings. `eqos-hdz` remains open: 102
source-intake CLI cases passed unchanged with coverage, followed by an authorized original-order
full coverage run with short tracebacks: **2,878 passed, 8 existing skips, exit 0** (453.41s).
The historical cutoff failure did not reproduce; no concrete cause or product/test fix is claimed.
SQLite ResourceWarnings also occurred during passing runs and are not proven causal.

The scanner repair is frozen for fresh independent contract/context review. Root's focused
scanner run passes all 24 cases; actual identifier-only historical replay against `05b2634`
checks 317 captured tokens with no unresolved collision. This is focused scanner evidence,
not a replacement for the full formal gate. Its original FAIL/STOP remains until fresh reviewed
combined gate evidence. No vendor implementation batch starts before that barrier.

Source-native Screener liabilities construction is an available-source engineering prerequisite
for Task 13; missing-body vendor exclusions do not waive it. Read-only exploration confirmed
existing relational interpretation operand links and transform JSONB can preserve native inputs
without fake canonical operands or a new migration. A supplemental Task 14/15 plan is under
independent review; no native construction or final v2 release has started.

- Resume gate repair closure: `eqos-490` is closed by `f48ee20`. Fresh independent r1/r2
  review approves the scanner and all seven exact context records; the final historical-scope
  formal gate against `05b2634` exits 0/PASS: **2,902 passed, 8 existing skips**, all four quality
  checks green, original four RED records unchanged, privacy rails clear. This resolves the
  previous STOP without a post-commit empty-diff rerun. `eqos-hdz` stays open with cause UNKNOWN;
  both current full coverage runs passed its unchanged cases. Formal built-tree acceptance is
  current; full D1b source/configuration/run/queue/frozen-manifest acceptance remains open.

### Native draft integration review — 2026-10-13

The approved supplemental r3 plan was committed in `3b16a13`; three exclusive implementation
lanes returned native contract, retained Screener and complete dictionary/first-party bridge
drafts. Fresh independent spec, code-quality and source/config reviews returned REQUEST_CHANGES.
Their exhaustive twelve-item deduplicated ledger is recorded in
[the native implementation review](../reviews/D1b-native-implementation-review.md).
The actual guarded integration reached product code: **53 passed / 6 failed**. PostgreSQL is
reachable with authorized sandbox escalation; the failures are the native UNMAPPED-only guard
rejecting unrelated mapped rows before selector filtering. No infrastructure change is indicated.

All retained source arithmetic/date/basis/precision and 259+1 dictionary compatibility were
independently confirmed. A fix round owns the shared evidence code and adds behavioral RED cases;
Task 13 publication checks run in a separate exclusive file scope. No draft is accepted or shared
v2 published yet. Fail closed by enforcing explicit consolidated bridge scope and rejecting exact
arithmetic that cannot fit existing Decimal/SQL persistence; do not infer a broader financial
definition, round fractions or change immutable migrations. Root's corrected-contract replay
against the pre-draft configuration remains **5/5 failed** for the absent dictionary/construction
features. Original RED outcomes are retained; reviewed test amendments/additions require explicit
orchestrator resealing. Missing vendor bodies and full D1b acceptance remain open.

### Exact-ID report prerequisite — 2026-10-13

Task 11's bounded existing-ingest report now exposes exact per-member stored source/surface/
extractor/capture/occurrence/interpretation identity. The fresh independent R2 review approves
all three fixes, including legacy empty-default serialization, unchanged re-ingest IDs and
honest partial-member failures. Root verification: **15 guarded PostgreSQL cases pass**, scoped
Ruff lint/format and strict mypy green. The
[review and explicit contract reopening proof](../reviews/D1b-ingest-id-report-review.md)
preserves the original RED outcome and the separate
3/3 genuine identity RED. Verified prerequisite commit: `041bd7b`; `eqos-u0u.15.1` is closed.
The full `eqos-u0u.15` producer remains open for the accepted publication/write-guard API and
actual committed joined release. Its unbuilt test preparation remains outside executable
acceptance in `scratchpad/`; no shared v2 generation or full Task 11/D1b closure is claimed.

### Publication repair plan — 2026-10-13

Independent Task 13 review found nine Important publication/authority/write/replay gaps despite
green focused mechanics. The [publication repair plan](D1b-publication-repair.md) is independently
approved at R3 after all six original plan gaps and both R2 trust-boundary gaps were resolved;
the [review ledger](../reviews/D1b-publication-repair-review.md) records each verdict. Root's
separate formal proof captures **12/12 genuine public-seam RED** before repair code. Migrations
0001–0006 stay immutable; the explicitly scoped optional publication-pin extension uses new 0007.
Implementation may proceed in its assigned files. Final shared v2 candidate/review/receipt
commits, generation proof and actual release acceptance remain pending; no flag, caller model,
path or hash alone is an external approval claim.

### Native mechanism verified checkpoint — 2026-10-13

Task 14's implementation is locally committed as `cd8151b`. Both fresh independent R3 reviews
approve all N01–N12 findings and the complete current-rule reading re-derivation. Root verifies
**131 focused retained/guarded-PostgreSQL/legacy cases**, Ruff lint/format and strict mypy.
The [final review and reopening proof](../reviews/D1b-native-implementation-review.md) records
each resolution, the unchanged RED outcomes, source-correct fixtures and explicit reseals.
Fail closed: these checks accept this bounded mechanism; the task stays open for the combined
formal gate. Dictionary/Screener drafts, shared release, publication-bound producers and full
D1b acceptance retain their own gates. No authority, qualification or missing-source waiver is
inferred from numerical validity.

The complete dictionary and consolidated first-party bridge drafts are committed in `95dd442`;
`eqos-u0u.13` is closed for its bounded draft criteria. All 259 legacy rows remain semantically
unchanged and only the evidenced DERIVED `other_income_incl_exceptional` row is added. Independent
raw-source review verifies the signed arithmetic and displayed precision; four corrected tests
still fail against the pre-draft config and pass in the final integration. These drafts grant no
vendor authority or demonstrated equivalence. Only Task 13's separate committed joined release
may enable their authoritative v2 use.

The broader publication/run check initially reported **52 passed / 7 failed**. Every failure
was `FileExistsError` in the old temporary `config_copy` fixture after real dictionary/v2 became
available, before product behavior. Commit `352648b` replaces only that isolated copied directory
with the intended v1 clone; no acceptance assertion or repository configuration changes.
Fresh unchanged run/rule verification is **31 passed**, with scoped Ruff lint/format green.
This resolves that fixture blocker; publication review's write/path/schema defects remain separate.

### Vendor run and queue supplemental plan — 2026-10-13

The [supplemental Task 6 plan](D1b-vendor-runs.md) is committed in `0f5c2da`, with an
[exhaustive R4 APPROVE review](../reviews/D1b-vendor-run-plan-review.md). It resolves exact versus
logical attempt identity, the single first-party run scope, deterministic byte/by-ID/context
proof, queue payload identity, actual transaction boundaries, source-rights exclusions and
canonical multi-item lock ordering. Source-independent cursor/overlay SQL may proceed separately.
Authoritative vendor execution still waits for the actual accepted release and generation handoffs;
no missing source, financial qualification, protected disposition or full D1b acceptance is waived.

### Publication mechanism checkpoint — 2026-10-13

Verified mechanism commit `00972d2` implements joined review/rights/source/schema enforcement,
descriptor-only cached-byte parsing and same-repository guarded pins, with publication identity
preserved in run manifests and SQL. New migration 0007 is now immutable. The
[R4 implementation review](../reviews/D1b-publication-implementation-review.md) approves every
mechanism finding after the orchestrator's no-waiver ruling and records all original/reopened
proofs. Root's fresh combined integration is **114 passed**. The historical formal gate is still
FAIL: **3,102 passed / 2 reproduced legacy-fixture failures / 8 existing skips**, with all quality
and privacy checks green. Actual code defects are resolved; final fixture corrections, full gate,
committed candidate A/fresh review/receipt C, and authoritative generation/run proofs remain gated.

### Final gate legacy fixture repair — 2026-10-13

Both failures in the 3,102-pass historical gate were isolated to old fixtures: the retained
Screener roundtrip omitted the required actual nine-member production extractor pin, and the
0005-to-0006 upgrade test unintentionally included the newly committed 0007 migration. The
repairs use the actual pin and a private byte-identical 0001–0006 migration directory. All
38 and 11 original assertion ASTs remain unchanged. The two exact guarded-PostgreSQL nodes
now pass (4.73s), with scoped Ruff lint/format clean. Commit `243a6b2` records only those two
fixture files and the reopening proof. The previous full gate remains a recorded FAIL until
a fresh complete run; no financial oracle, migration or production constraint was relaxed.

### First-party producer mechanism checkpoint — 2026-10-13

Commit `535df96` records the Task 11 mechanism: the existing ingest guard requires fresh
published configuration before writes, and the producer returns exact persisted member/row/
attempt/proof identities. One complete settings record supplies qualification context; its
identity/hash is stored in immutable v2 traces and checked before reuse and handoff. R1's
setting-change/retry race and R2's Minor in-memory trace issue are repaired. Independent R2
spec verdict is COMPLIANT, with code-quality and security APPROVE. Root's integrated 114 cases
and final 11 producer/context/guard cases pass, as do scoped Ruff lint/format and strict mypy.
Original refusal/race RED outcomes are preserved and the genuine immutability regression is
protected. Actual released A/C artifacts, Task 6 by-ID consumption and full D1b remain open.

### Retained Screener native draft checkpoint — 2026-10-13

Commit `ee4b000` records the unpublished Task 15 draft and its retained extraction/storage
tests. The consolidated source-native Borrowings + Other Liabilities construction retains
the independently read THERMAX/HFCL values, intervals and exact operand identities. It excludes
Total Liabilities and first-party NCI, remains equivalence-unproven and uses the actual
nine-member extractor pin. Fresh final verification is 7 passed, including guarded PostgreSQL,
with scoped Ruff lint/format clean. All D1b saved test seals match. Publication and complete
source acceptance remain separate gates; no missing-source waiver is granted.
No nominal RELEASED label or caller model is accepted as release authority.
