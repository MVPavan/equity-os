Verdict: REQUEST_CHANGES

# D1a phase-end re-review — Codex session (handoff run), round 2

Review basis: `scratchpad/execution/data-foundation-autonomous-2026-10-13/review-phase-r2.diff`, snapshot `snap-phase-r2`, SCOPE_BASE `615f032`; current approved D1a plan, canonical data spec, October 13 autonomous goal, and D1a-phase-review-r1. Area A freeze was confirmed by root before the verdict. This is the round-2 snapshot verdict; concurrent follow-up fixes require a separate re-review.

Strengths: the verified-byte PDF parser, complete XBRL anchor equality checks, explicit blank-row ambiguity, server-owned clock cache, honest qualification downgrade, recursive formula constituents, source-scoped package resolution, one-connection execution, report provenance and literal tracer assertions address substantial defects. Evidence appears in `ingest/pdf_source.py:154`, `evidence/xbrl_adapter.py:92`, `extract/pdf_statement_pages.py:365`, migration `0005:24`, `contracts/qualification.py:188`, `evidence/derived.py:282`, `compare/engine.py:469`, `compare/run.py:117`, `compare/report.py:198`, and `test_compare_tracer.py:164` (all Python paths under `src/fundamentals/` or `tests/fundamentals/` respectively).

## Issues, ranked by severity

No Critical issue was verified. Six Important issues block phase acceptance; the module-size issue is Minor.

### R2-1 — Important, spec/correctness: run selection still revives a superseded canonical value

- Evidence: `src/fundamentals/compare/engine.py:557` builds candidates only from the requested key digest, plus one first pinned witness; `engine.py:569` passes that narrowed collection to `select_key`. The repaired supersession pass at `src/fundamentals/evidence/selection.py:183` cannot see a correction filed under a different key.
- Trigger: interpretation 1 maps an occurrence to revenue; same-pin manual correction 2 supersedes it and maps to other income. The correction is not the capture's first witness.
- Consequence: revenue still returns VALUE from interpretation 1. The same routing defect can leave an obsolete condition value available to formula qualification when a correction moves its key.
- Verified focused pure probe: calling the actual `RunEngine._select` with the public selection fixtures returned `revenue_from_operations VALUE 1` after the cross-key correction; exit 0.
- Smallest adequate fix: pass the complete capture interpretation collection into `select_key`, which already owns eligibility, pinned-generation supersession and key matching. Cover actual run resolution and replay with the cross-key correction, rather than testing only `select_key`.
- Prior finding: B1 PARTIAL. C1's older-triple filtering is fixed, but this cross-key revision edge still affects its consumer.

### R2-2 — Important, spec/trust boundary: a foreign namespace satisfies the report-nature declaration requirement

- Evidence: `src/fundamentals/evidence/member_identity.py:123` extracts only the concept's local name, and `member_identity.py:132` marks report nature declared without checking `fact.namespace_uri == instance.taxonomy.namespace`.
- Trigger: strip `contextRef` from both genuine taxonomy report-nature facts in the retained Q2 FY26 XBRL and add a foreign `urn:untrusted` fact with the same local name, correct text and an existing context.
- Consequence: the file has no genuine context-bound report-nature declaration but identity verification succeeds. The independent instance-scope check fixes the original wrong-basis request, while the required valid declaration is still spoofable.
- Verified focused pure in-memory retained XML probe: `genuine_context_bound_report_nature 0`; `foreign_context_bound_report_nature 1`; `verified True reason None`; exit 0. No original or other file was modified.
- Smallest adequate fix: recognize identity/report-nature concepts only in the selected taxonomy's namespace, retaining independent scope and entity checks. Add the foreign-declaration regression.
- Prior finding: A1 PARTIAL.

### R2-3 — Important, spec/correctness: actual runs discard most incomplete INVALID keys

- Evidence: `src/fundamentals/compare/engine.py:173` indexes only interpretations having a complete key. `engine.py:557` uses that index and a single witness. `src/fundamentals/evidence/selection.py:307` can match an INVALID partial key, but the affected interpretation never reaches it.
- Trigger: a unit-invalid revenue/segment interpretation retains canonical id, period, basis, framework and dimensions, but has `key=None`; another interpretation is the capture's first pinned witness.
- Consequence: the run reports NO_VALUE without UNIT_MISMATCH rather than INVALID/NOT_COMPARABLE. The public helper regression only passes because it supplies the invalid interpretation directly.
- Verification: source-inspected producer/consumer path; no PostgreSQL probe rerun.
- Smallest adequate fix: the complete-capture candidate routing from R2-1, plus a run/replay regression using a non-witness incomplete INVALID interpretation.
- Prior finding: A4 PARTIAL.

### R2-4 — Important, spec/correctness: ambiguous owners attribution loses every affected target

- Evidence: `src/fundamentals/evidence/mapping.py:350` returns all repeated-label candidates when section identity is unestablished; `src/fundamentals/evidence/interpret.py:145` writes INVALID with `canonical_id=None`; `src/fundamentals/evidence/selection.py:310` requires a canonical id to match an incomplete key. `tests/fundamentals/test_evidence_pdf_ingest.py:78` confirms that the retained first owners row is ambiguous.
- Trigger: the retained PDF's 251.70 crore first owners row has no evidenced attribution heading. It could belong to the profit/OCI/TCI owners candidates.
- Consequence: the stored raw interpretation is INVALID, but the canonical profit-attributable-owners run cell becomes NO_VALUE because no candidate-target identity survives. This incorrectly implements the approved fail-closed rule; the rule itself is accepted.
- Verification: source-inspected exact retained-test and selection path.
- Smallest adequate fix: persist the evidenced candidate target identities and let matching selection return INVALID for each affected target, without assigning a numeric value or inventing unit/period/dimension semantics. Keep that target evidence immutable and replayable. Assert the actual run state, not only `Interpretation.status`.
- Prior finding: A2 PARTIAL.

### R2-5 — Important, spec/correctness: newly recorded package-owned family failures are ignored

- Evidence: `src/fundamentals/evidence/first_party_ingest.py:242` writes the intrinsic generation before `first_party_ingest.py:310` recomputes package-owned unlocated-family attempts. `src/fundamentals/evidence/first_party_extract.py:175` writes those pending attempts separately. `src/fundamentals/compare/engine_attempts.py:129` accepts a family failure only when its timestamp equals the original overall generation's timestamp.
- Trigger: a structurally present statement cannot be located in the PDF. The package-owned PARSE_FAILED attempt is recorded after the overall COMPLETE attempt. This occurs on fresh ingestion as well as on a reused PDF capture.
- Consequence: comparison ignores the current package's real family failure and can report absence/older values instead of UNAVAILABLE. Ingest-only tests prove that the attempt exists but do not prove its downstream state.
- Verification: source-inspected timestamp/transaction flow. `tests/fundamentals/test_evidence_reprocessing.py:255` covers ingest recording only.
- Smallest adequate fix: resolve explicit failures owned by the selected package at their honest store timestamps, separately from capture-generation timestamp association. Require the appropriate capture/extractor/context and cutoff, and preserve replay. Do not backdate or invent a new capture extraction.
- Prior finding: A11 PARTIAL.

### R2-6 — Important, spec/data integrity: comparison mixes incompatible PDF statement-spec generations

- Evidence: `src/fundamentals/evidence/first_party_extract.py:258` filters generation reuse by PDF spec context and `first_party_extract.py:278` re-resolves current anchors. `src/fundamentals/evidence/first_party_ingest.py:406` filters returned interpretation reuse by those occurrence ids. However, `src/fundamentals/compare/resolve_loader.py:241` loads every interpretation of the capture, and `src/fundamentals/compare/engine_attempts.py:120` chooses an overall attempt without binding selection to its PDF spec context.
- Trigger: ingest a capture under wide specs, then under narrower specs with the same extractor. Correct narrow ingest output excludes old balance-sheet anchors; old stored interpretations remain append-only.
- Consequence: comparison reloads and may select those old wider-context balance-sheet values even though the latest location decision excluded them. Hashing an attempt context alone does not bind the selected occurrence set to that decision.
- Verification: source-inspected active-anchor producer versus loader/resolver consumer; `tests/fundamentals/test_evidence_reprocessing.py:186` proves narrow/wide ingest behavior without a run check.
- Smallest adequate fix: bind and resolve the selected generation's active occurrence membership, or explicitly fail closed when available incompatible PDF contexts cannot be separated. Apply the rule to operands, conditions, comparatives and replay. A null legacy context also lacks verifiable membership.
- Prior finding: A11 PARTIAL; this is separate from R2-5.

### R2-7 — Minor, plan module-size limit exceeded by one line

- Evidence: `src/fundamentals/extract/pdf_statement_pages.py:801`; fresh `wc -l` reports 801. The D1a plan at `docs/workstreams/data-foundation/plans/D1a.md:40` caps modules at 800.
- Consequence: explicit structural convention breached; no independent behavioral defect follows from the extra line.
- Smallest adequate fix: remove one unnecessary blank line or make an equally minimal formatting cleanup. No refactor is warranted.

## Original-finding matrix — every A1–A14 / B1–B9 / C1–C11

PARTIAL means NOT ADDRESSED for acceptance: part of the repair exists, but the specific boundary remains incomplete. No original finding was omitted. Every ADDRESSED judgment below is source-verified; reported test executions are identified separately in the verification section.

| Finding | Verdict | Exact evidence and remaining boundary |
|---|---|---|
| A1 | PARTIAL | `src/fundamentals/evidence/member_identity.py:109` checks independent scope and requires a declaration, but `:132` accepts a foreign namespace. R2-2. |
| A2 | PARTIAL | `config/mappings/pdf/v1/results_layout.yaml:135` removes ordinal owner attribution; `src/fundamentals/evidence/mapping.py:350` stores ambiguity, but `interpret.py:145` drops candidate target identities. R2-4. |
| A3 | ADDRESSED | `src/fundamentals/ingest/pdf_source.py:154` reads once; `:160` parses the same buffer. Path replacement regression at `tests/fundamentals/test_extraction_integrity.py:26`. |
| A4 | PARTIAL | `src/fundamentals/evidence/interpret.py:179` keeps evidenced dimensions and canonical identity; `selection.py:299` matches a partial INVALID. Actual run filtering at `compare/engine.py:557` excludes non-witness keyless interpretations. R2-3. |
| A5 | ADDRESSED | `src/fundamentals/evidence/capture_interpretation.py:228` derives ambiguous alternatives; `:324` joins them to every affected construction group; `interpret.py:239` and `:318` retain invalid grouping. Regression `tests/fundamentals/test_evidence_interpretation_keys.py:99`. |
| A6 | ADDRESSED | `src/fundamentals/extract/xbrl_parser.py:300` resolves namespace URI/local name and canonicalizes only ISO4217/xbrli namespaces. Foreign rebinding regression `tests/fundamentals/test_evidence_interpretation_keys.py:72`. |
| A7 | ADDRESSED | `src/fundamentals/evidence/xbrl_adapter.py:92` compares full duplicate payloads, excluding document position only; `repository.py:747` refuses stored payload drift. Tests `tests/fundamentals/test_xbrl_anchor_integrity.py:62`, `:96`. |
| A8 | ADDRESSED | `src/fundamentals/extract/xbrl_parser.py:185` validates missing entity/period; `:729` converts invalid dates/model validation to XbrlParseError; `evidence/first_party_extract.py:400` records PARSE_FAILED. |
| A9 | ADDRESSED | `src/fundamentals/extract/pdf_statement_pages.py:365` distinguishes explicit headings and retains unknown blank labelled rows; `:395` flags ambiguous classification; `evidence/interpret.py:507` makes their mapped interpretation INVALID. `tests/fundamentals/test_evidence_pdf_ingest.py:123`. Approved fail-closed choice accepted. |
| A10 | ADDRESSED | `src/fundamentals/evidence/mapping.py:454` treats contains predicates conservatively; `:459` proves section disjointness only with equality constraints. `tests/fundamentals/test_extraction_integrity.py:48` and owned loader regression verify Tax/exp overlap. |
| A11 | PARTIAL | `src/fundamentals/evidence/first_party_extract.py:205` pins mapping/spec decisions and `first_party_ingest.py:310` recomputes package failures; downstream timestamp association and active-context membership remain defective. R2-5/R2-6. |
| A12 | ADDRESSED | `src/fundamentals/evidence/first_party_ingest.py:151` uses shared extractor content pins before staging/reuse; `compare/run_config.py:53` includes identity/extraction/PDF loading source; `tests/fundamentals/test_evidence_reprocessing.py:164`. Plan build note `D1a.md:1861` records it. |
| A13 | ADDRESSED | `migrations/0005_store_clock_cache_and_keyless_dimensions.sql:24` uses private server-owned backend/transaction cache; `:15` and `:22` revoke public access; `:35` ignores client GUCs. Runtime GUC/cache-privilege regression `tests/fundamentals/test_store_clock.py:120`. Applied 0004 remains outside the fix diff. |
| A14 | ADDRESSED | `tests/fundamentals/test_pg_evidence_schema.py:1` now 479 lines; common schema support at `tests/fundamentals/pg_evidence_schema_support.py:1` is 551 lines. Fresh line-count check passes the named split requirement. |
| B1 | PARTIAL | `src/fundamentals/evidence/selection.py:183` fixes helper order; `compare/engine.py:557` still narrows before calling it. Pure actual-consumer probe proves stale VALUE. R2-1. |
| B2 | ADDRESSED | `src/fundamentals/contracts/evidence.py:236` enforces known member publication and both cutoffs; `evidence/selection.py:85` uses it. `tests/fundamentals/test_evidence_contract_boundaries.py:25`. |
| B3 | ADDRESSED | `src/fundamentals/evidence/derived.py:241` resolves per-nested-key qualification; `compare/engine_formula.py:205` provides selected row/key/package context; `tests/fundamentals/test_derived_regressions.py:64` has a positive parent-scope witness and a quarter-only child evaluated at an instant. |
| B4 | ADDRESSED | `src/fundamentals/canon/dictionary_validation.py:261` rejects AVERAGE plus aggregation with TEMPORAL_ROLE_MISFIT. Approved fail-closed loader choice accepted; no unsupported composition claimed. |
| B5 | ADDRESSED | `src/fundamentals/evidence/derived.py:282` recursively evaluates derived constituents, `:271` averages them, `:310` aggregates them. Child-first trace regressions `tests/fundamentals/test_derived_regressions.py:143`, `:213`. |
| B6 | ADDRESSED | `src/fundamentals/contracts/qualification.py:188` requires typed capture/hash/company evidence, five distinct companies, unique captures/hashes, discriminating fixture and nonblank sample rule; `:175` otherwise downgrades. Filing alignment remains separate in `evidence/derived.py:114`. No production five-company equivalence is claimed from synthetic tests. |
| B7 | ADDRESSED | Six rows declared in `config/dictionary/v1/balance_sheet.yaml:38` and `segment.yaml:34`; six exact PDF mappings start at `config/mappings/pdf/v1/results_layout.yaml:636`; `docs/specs/artifacts/dictionary-v1-manifest.md:52` records total 259. Literal amounts/dash regression `tests/fundamentals/test_evidence_pdf_ingest.py:138`. |
| B8 | ADDRESSED | `src/fundamentals/canon/dictionary.py:1` is 517 lines; `dictionary_validation.py:1` is 453 lines. Ordered validator dispatch preserved at `dictionary_validation.py:36`. |
| B9 | ADDRESSED | `config/dictionary/v1/derived.yaml:102` labels INR million; `tests/fundamentals/test_canon_formula.py:376` scales by million and `:393`/`:402` assert correct literal INR intermediates. |
| C1 | ADDRESSED | `src/fundamentals/compare/engine_formula.py:241` obtains conditions from run-pinned selected cells and `resolve.py:206` pins chosen condition interpretation ids. Original older-triple proof defect is fixed; R2-1 separately covers cross-key supersession at the shared consumer. `tests/fundamentals/test_compare_run_rules.py:166`. |
| C2 | ADDRESSED | `src/fundamentals/compare/engine.py:287` uses formula leaf families for applicability; `engine_formula.py:136` resolves selected operand-family package and `:205` recomputes nested context. Statement-correction regression `tests/fundamentals/test_compare_run_rules.py:239`. |
| C3 | ADDRESSED | `src/fundamentals/compare/engine_formula.py:184` builds operand extraction outcomes; `:186` uses derived_extraction_status; `:326` offers scoped adjustments; `engine.py:775` persists them. Actual run/replay/report regression `tests/fundamentals/test_compare_run_rules.py:275`. |
| C4 | ADDRESSED | `src/fundamentals/compare/resolve_loader.py:163` filters attempts, `:194` filters candidate packages; `engine.py:473` and `:491` enforce requested member surfaces; `resolve.py:203` records selected source scope. PDF-only correction/excluded-source regression `tests/fundamentals/test_compare_run_rules.py:372`. |
| C5 | ADDRESSED | `src/fundamentals/compare/run.py:117` pins before resolution; `run_config.py:223` releases pin connection before `:230` takes definition-set connection. One-connection regression `tests/fundamentals/test_compare_run_rules.py:423`. |
| C6 | ADDRESSED | `src/fundamentals/compare/report.py:119` verifies dictionary version/content pin before rendering. CLI drift regression `tests/fundamentals/test_compare_run_rules.py:438`. |
| C7 | ADDRESSED | `src/fundamentals/compare/run_models.py:127` requires exactly one entity with explicit refusal. Single-entity owner ruling accepted; `tests/fundamentals/test_compare_run_rules.py:403`. |
| C8 | ADDRESSED | `src/fundamentals/api/compare_cli.py:107` catches specific expected policy/config/YAML exceptions; `compare/definitions.py:85` validates filing refs during loading and `:133` wraps typed loader failures. Failure exit/no-run regressions `tests/fundamentals/test_compare_run_rules.py:484`. |
| C9 | ADDRESSED | `src/fundamentals/compare/report.py:193` emits epistemic class; `:198` emits interpretation/anchor/trace/attempt/reason; `:215` renders pair reason, difference, gap, definition and adjustments. `tests/fundamentals/test_compare_run_rules.py:507`. |
| C10 | ADDRESSED | `tests/fundamentals/test_compare_tracer.py:164` asserts each representation's literal revenue/total income/expenses values; `:171` asserts literal EPS. Literal table binds 5,715.42 / 5,742.85 / 5,402.29 crore and 62.66 rupees/share. |
| C11 | ADDRESSED | `src/fundamentals/compare/run.py:135` populates sorted distinct operational failures; `:200` derives them from deciding unavailable source rows, including reason/attempt; retained run/replay regression `tests/fundamentals/test_compare_run_rules.py:507`. |

Counts: 29 ADDRESSED; 5 PARTIAL (A1, A2, A4, A11, B1); 0 OPEN. The six Important defects are the unresolved/new integrated manifestations of those five prior findings.

## Verification evidence and limits

- Reviewer independently read the mandatory code-review skill completely and applied re-review plus trust-boundary checks. The package was supplied after initial named-seam reading; later package hunks were read once. Some hunks cut off needed parser/ingest functions, so focused full-function slices were read to evaluate malformed-input conversion, package-attempt timing, active-anchor reuse and clock security.
- Reviewer ran no git, Beads, Docker, network, owner-database operation or broad suite. Only this scratchpad report was written. Retained bytes were read without changes; focused probes mutated XML and model data only in memory.
- Reviewer ran the stale-key actual-consumer pure probe (exit 0, stale VALUE reproduced), the foreign-namespace actual-parser/identity pure probe (exit 0, spoof verified), and named-module line counts (exit 0, 801-line locator confirmed). No PostgreSQL integration probe was needed to establish the source-visible transaction/candidate failures. Initial namespace probe setup errors were corrected before the successful proof; they are not suite evidence.
- Area B's supplied report records 145 passed/1 deliberately deselected PG test, then 8 passed/41 deselected focused retained tests, source mypy/ruff green. Area A records 49 passed/2 qualification-fixture expectation failures, followed by the two corrected cases passing and an additional loader case passing. Area C records 14 passed/1 extractor-drift failure during concurrent source edits, and 102 passed/1 deliberately deselected PG case for pure tables/config tests. These are audited covering-test claims, not independent fresh phase-gate results.
- Root's stable integrated four-check/tracer output was not yet supplied when this snapshot report was issued. No clean whole-suite or tracer completion is claimed here. Follow-up edits must have their covering tests and output supplied for re-review.
- The absent historical D1a red proof remains explicitly disclosed by the October 13 goal and D1a build notes. This review accepts the authorized four-check/tracer/independent-review closure route; it does not claim historical verify.sh gate success.
- Out-of-scope observations: none asserted as additional blockers. In particular, the approved A2/A9 fail-closed policy, B4 loader rejection and C7 single-entity limit are not relitigated.

## Exact successful A1 namespace probe

This command reads the retained source and mutates only in memory; it creates no file and uses no database:

The operator-specific writable UV cache override is omitted from this portable command;
the independently executed probe body and result are unchanged.

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python - <<'PY'
from pathlib import Path
from lxml import etree
from fundamentals.extract.xbrl_parser import iter_raw_facts
from fundamentals.extract.xbrl_taxonomies import _ALL_TAXONOMIES
from fundamentals.evidence.member_identity import (
    IssuerIdentifiers, verify_xbrl_identity, ISIN_CONCEPT,
    SYMBOL_CONCEPT, SCRIP_CODE_CONCEPT,
)
from fundamentals.contracts.canonical import Basis

body = Path(
    "data/raw/watchlist/aparinds/nse/"
    "INTEGRATED_FILING_INDAS_1560713_29102025085858_WEB.xml"
).read_bytes()
root = etree.fromstring(body)
instance = iter_raw_facts(body, taxonomies=_ALL_TAXONOMIES)
spec = instance.taxonomy
nature = root.findall("{" + spec.namespace + "}" + spec.scope_concept)
context = nature[0].get("contextRef")
for declaration in nature:
    declaration.attrib.pop("contextRef", None)
foreign = etree.SubElement(root, "{urn:untrusted}" + spec.scope_concept)
foreign.set("contextRef", context)
foreign.text = spec.consolidated_text
modified = iter_raw_facts(etree.tostring(root), taxonomies=_ALL_TAXONOMIES)
by_local = {
    fact.concept_qname.rsplit(":", 1)[-1]: (fact.raw_text or "").strip()
    for fact in instance.facts
}
identifiers = IssuerIdentifiers(
    entity_id=1, isin=by_local[ISIN_CONCEPT],
    nse_symbol=by_local[SYMBOL_CONCEPT], bse_scrip=by_local[SCRIP_CODE_CONCEPT],
    evidence_input_id=1,
)
verdict = verify_xbrl_identity(modified, identifiers, basis=Basis.CONSOLIDATED)
print("genuine_context_bound_report_nature", sum(
    fact.namespace_uri == spec.namespace
    and fact.concept_qname.rsplit(":", 1)[-1] == spec.scope_concept
    for fact in modified.facts
))
print("foreign_context_bound_report_nature", sum(
    fact.namespace_uri == "urn:untrusted" for fact in modified.facts
))
print("verified", verdict.verified, "reason", verdict.reason)
PY
```

Observed output before the follow-up repair:

```text
genuine_context_bound_report_nature 0
foreign_context_bound_report_nature 1
verified True reason None
```

VERDICT: REQUEST_CHANGES
