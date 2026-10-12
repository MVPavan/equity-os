# D1a Canonical Comparison Tracer Implementation Plan

Status: approved
Approved by: gpt-6.1-sol high, `APPROVE`, 2026-10-12, after review rounds 1–3, a fresh critical
review and a scoped re-review (`.claude/rules/core/04-agent-stack.md`; resolution tables at the end).

**Origin:** Phase D1a row of [`docs/workstreams/data-foundation/roadmap.md`](../roadmap.md). Epic
`eqos-3f9`, stages `eqos-3f9.1`–`eqos-3f9.7`, acceptance read from bd on 2026-10-12. The spec is
[data spec](../../../specs/2026-10-11-canonical-financial-data-and-cross-source-comparison.md)
§0–§6 and the Stage 1 Success Criteria named in the roadmap row, as amended by
[ledger spec](../../../specs/2026-10-12-report-ledger-memory-and-data-lifecycle.md) §6. The
evidence base is [`docs/research/canonical-field-coverage-inventory.md`](../../../research/canonical-field-coverage-inventory.md).

**Goal:** Take Apar Q2 FY26 consolidated from retained first-party captures (XBRL and results PDF)
through occurrences, interpretations, the extraction check and a stored run on PostgreSQL. The
`fundamentals compare report` CLI then shows the spec-stated values.

**Scope guard (orchestrator ruling).** D1a does not build generalized issuer discovery, temporal
identity events, OCR, vendor adapters, retention machinery, queue workflows or universal PDF
support. It builds only retained-evidence contracts: Apar's retained captures, read through
evidenced, issuer-configured rules. A task step that would need any of these stops and reports.

**Out of scope:**
- Vendor adapters, vendor source authority, the full corroboration table, trust view and diagnostic routing (D1b.1–D1b.2); the review queue and the open-HIGH exit path (D1b.3; D1a reserves the code); the register amendment and frozen Stage 1 manifest (D1b.4–D1b.5).
- Any write to the legacy SQLite fact store (D2); temporal identity events and onboarding (D6; D1a seeds from the existing entity map and one evidenced APARINDS input); retention, purge and tombstones (D9; D1a only keeps vendor values separable); shareholding beyond declaring the family (D8); live fetching and OCR (D1a reads retained originals and the PDF's text layer).
- Refactoring `src/fundamentals/verify/three_source.py`. It stays untouched; its private structural detector duplicates `compare/triage.py` (follow-up, see Self-review).

**Constraints:**
- PostgreSQL `postgres:18.6` from `compose.yaml`, on `127.0.0.1`, configured port (locally 55432), with the data directory bind-mounted from the configured host path (data spec §6, owner decisions).
- "Tests use their own test database, never the main one" (data spec §6).
- Evidence tables are immutable. Triggers reject update and delete; the runtime role lacks UPDATE and DELETE; a separate migration role owns the schema (data spec §6).
- "Foreign keys enforce every reference; optional key parts use an explicit empty value or nulls-equal unique constraints" (data spec §6).
- "Pooled access with explicit connect and statement timeouts; parameterised queries only" (data spec §6, `.claude/rules/python/safety.md`).
- Writes are idempotent insert-on-conflict. Run publication is one transaction, and a failed run leaves nothing visible (data spec §5–§6).
- Credentials come from the untracked `.env` through `pydantic-settings` at the composition root, injected at construction. They never appear in logs, manifests or committed files; manifests record host, port and database name only (data spec §6, D1).
- "Until Stage 2 cutover, legacy SQLite stays the fact system of record; Stage 1 writes only evidence tables" (data spec §0).
- Nothing is zero-filled. Absence is never a value (data spec §1, §4; invariant 10).
- The model never computes numbers. All arithmetic is deterministic code with stored traces (invariants 6–7).
- Ledger §6 item 4: a later purge role may delete vendor values in result rows but never outcomes. Per-source values therefore live in their own child rows, separate from status and outcome rows, even though D1a stores only first-party values.
- Python rules: `ruff`, `mypy --strict`, frozen Pydantic models, enums for fixed sets, structlog, no `print`, `uv` only, files at most 800 lines (`.claude/rules/python/coding-style.md`). New contracts never import `ingest/` modules.
- Tests: integration and e2e first, on the PostgreSQL test database. Unit tests only for dynamic logic: interval, rational and period-aggregation arithmetic, decision tables, applicability and selection (`.claude/rules/python/testing.md`, roadmap Test focus).
- Fixtures are the real retained captures. Correction, revision and ambiguity fixtures withhold, mark or re-interpret those captures and never invent filed values. A **marked copy** is a byte copy of a retained capture with one declared edit, registered under a test-only source id prefixed `marked-` with its own SHA-256; the test names the edit. Unit tests of pure table and arithmetic functions may use constructed operands and constructed timestamps.
- **No backdating (orchestrator ruling).** First-seen time is when the system registered the capture and is never set to equal knowledge time. Every `pg` test that needs a historical or between-registrations cutoff takes it from the store's recorded first-seen or recorded-at times, never from a hard-coded calendar date, except a pre-capture cutoff that asserts nothing is eligible.

## Design decisions fixed by this plan

1. **Driver and pool: `psycopg` 3 (`psycopg[binary]`) with `psycopg-pool`, used synchronously.**
   The codebase is synchronous (`sqlite3`, no asyncio). Psycopg 3 gives server-side binding, exact
   `numeric` ↔ `Decimal`, `connect_timeout`, per-connection `statement_timeout` via `options`,
   `sql.Identifier` and a maintained pool. Rejected: asyncpg (async only), SQLAlchemy (unneeded
   ORM). Add `pydantic-settings` (required by the coding-style rule).
2. **Roles.** There are three. The **admin** role is the container superuser from `.env`
   (`EQOS_PG_USER`), used only for bootstrap and test-database lifecycle. The **migrator** role,
   fixed name `eqos_migrator`, owns schema `eqos` and every object in it. The **runtime** role,
   fixed name `eqos_runtime`, gets USAGE on the schema, SELECT and INSERT on the tables, and USAGE
   on the sequences. Role names are fixed so migration SQL can grant to them without templating.
   Passwords come from `.env`.
3. **Test database: a per-test database cloned from a migrated template, in the same compose
   service.**
   - Per session, as admin: ensure both roles (create missing, never alter), create
     `eqos_test_tpl_<session-hex>`, migrate it as `eqos_migrator`, close every connection to it.
   - Per test: `CREATE DATABASE eqos_test_<uuid-hex> TEMPLATE …`, dropped after the test; teardown
     drops the template. No DELETE or TRUNCATE is needed (the triggers forbid them).
   - Guards: every created or dropped name starts with the configured prefix (default
     `eqos_test_`); the harness refuses to run if the prefix would match `EQOS_PG_DB`, and never
     runs DDL or DML against any other database. Lifecycle DDL uses an admin **maintenance
     connection** to the `postgres` database, never `EQOS_PG_DB`; the name guards run before any
     connection is opened and again before each create and drop.
4. **Retained captures in tests.** Apar originals live in gitignored
   `data/raw/watchlist/aparinds/`. They are pinned by SHA-256 in
   `data/raw/watchlist/aparinds/retrieval-manifest.json` and in `config/aparinds-fy26-q*.yaml`.
   - Tests stage them into a temporary snapshot store through the first-party intake of design
     decision 12, so every occurrence carries a real capture reference.
   - A missing original, a hash mismatch or an unreachable test database **fails** the test with a
     clear message and never skips it. This is the fail-loud rule: the Verify cells require these
     files green.
   - Markers: `pg` (needs the compose service) and `retained` (reads gitignored originals); a test
     needing both carries both. `-m "not pg"` and `-m "not retained"` are the only opt-outs,
     documented in `.claude/project/verification.md` (Task 1).
5. **Knowledge time and first-seen time.**
   - The retrieval manifest has two `filed_at_nse` formats. `DD-Mon-YYYY HH:MM:SS` (e.g.
     `29-Oct-2025 20:58:58`) is naive NSE wall time: localise to Asia/Kolkata, store UTC. An ISO
     string with an offset (the FY25–FY26 Q1 `xbrl-consolidated-comparator` entries, e.g.
     `2024-10-30T10:47:06+00:00`) keeps its offset as written, stored UTC. Any other shape is
     refused. The raw string is always kept.
   - Recorded doubt: in the ISO entries the clock equals the filename's timestamp (`…30102024104705`
     ↔ `10:47:06+00:00`), which suggests IST wall time labelled UTC. D1a does not reinterpret it;
     the doubt is a follow-up (Self-review), and the status stays `KNOWN`.
   - Knowledge time is **per package member**: Q2 FY26's results PDF is `29-Oct-2025 13:33:43` and
     its XBRL `29-Oct-2025 20:58:58`. Each occurrence carries its member's knowledge time.
   - **Package knowledge time** is the latest member knowledge time. A package is eligible at a
     cutoff only when its knowledge time and every member's first-seen time are at or before it,
     so extraction never pairs a half-visible submission. A single occurrence's own eligibility
     (`is_eligible`) is still judged on its own two clocks.
   - First-seen time is the capture registration time recorded by the store (no backdating).
     Interpretation `recorded_at` is the store clock at write, so it is at or after its capture's
     first-seen time; it is never set to a knowledge time either.
   - **Eligibility boundary.** Eligibility takes an `EligibilityBoundary` (frozen:
     `knowledge_cutoff`, `first_seen_cutoff`). A run uses its cutoff for both. Ingest's comparative
     check (Task 6) uses the honest ingest-time boundary: `knowledge_cutoff` = the ingesting
     package's knowledge time, `first_seen_cutoff` = the ingest's own registration time. So an
     original is eligible exactly when it is already stored and was filed no later, and neither
     clock is bent.
6. **Run identity hash (ruling (a), confirmed).** Identity = request scope + mode + every pinned
   version with its content SHA-256 + the resolved input set. It excludes the cutoff and the code
   commit; the manifest records the commit and the report prints it. The resolved input set is
   every `run_inputs` row (kind, id, disposition), including negative outcomes: failed attempts,
   packages and interpretations considered but not selected, surfaced restatements, and all
   identity, settings, basis-status, segment-member and statement-presence evidence that affected
   selection, applicability or calculation. **Consequence:** a logic change with unchanged inputs
   and versions returns the old run (`created=False`). An outcome-changing logic change must bump
   the extractor, normalisation-policy, formula-set or comparison-policy version; extractor pins
   hash their source files (decision 7), so an unbumped extractor edit is refused rather than
   silently reusing a run.
7. **Versioned config is content-pinned.** Every versioned artifact has a version string, and its
   loader computes a SHA-256 of the resolved content. The pinned artifacts and their content
   sources:

   | Pin | Content source |
   |---|---|
   | `dictionary` | `config/dictionary/v1/*.yaml` except `derived.yaml` |
   | `formula_set` | `config/dictionary/v1/derived.yaml` (version in `metadata.yaml`) |
   | `mapping_set` | `config/mappings/v1.yaml` plus its member files (incl. constructions and statement anchors) |
   | `normalisation_policy` | `config/normalisation_policy/v1.yaml` |
   | `extractor_xbrl` | `XBRL_EXTRACTOR_VERSION` plus the bytes of `evidence/xbrl_adapter.py` and `extract/xbrl_parser.py` |
   | `extractor_pdf` | `PDF_EXTRACTOR_VERSION` plus the bytes of `evidence/pdf_adapter.py`, `extract/pdf_statement_pages.py`, `extract/pdf_header_text.py` and `extract/pdf_printed_unit.py` |
   | `alignment_rules`, `rounding_policy`, `comparison_policy`, `definition_set` | their one YAML file each |

   If a stored run or definition set names the same version with different content, the new run
   is refused with `VersionContentDriftError` (in `fundamentals.contracts.versioning`, Task 3, so
   every loader can raise it). Published versions are immutable (data spec §1).
8. **Formulas are declarative operator trees** in YAML: add, sub, mul and div nodes over operand
   references and decimal literals. Formula strings are never parsed or evaluated
   (`.claude/rules/python/safety.md`; data spec §1: vendor formula strings are never executable).
   Every formula — dictionary formula, construction rule or vendor-definition row — carries its own
   evidenced tier (default `EQUIVALENCE_UNPROVEN`) and a `QualificationScope | None`, and its
   scoped tier is resolved against the evaluation's `QualificationContext` like any mapping
   (`scoped_tier`). There is no exemption: the effective tier is the weakest of the formula's scoped
   tier and every operand's scoped tier (data spec §2, computed values).
9. **Duplicate selectors (ruling (c), confirmed).** Mapping level: two mapping entries matching the
   same native field and context predicate under one (source, surface, schema identity, basis,
   period kind) scope raise `MappingLoadError(DUPLICATE_SELECTOR)`. The mapping loader also
   rejects two entries that, after template expansion, emit the same canonical measurement
   (canonical id + dimension selector) from one scope. Aliases resolving to the same canonical
   target are allowed; the same native name under different taxonomies is legitimate. The
   dictionary-level refusal (two rows, aliases or template instantiations resolving to one
   canonical selector) stays.
10. **`ORIGINAL` revision cause (ruling (b), confirmed).** `ORIGINAL` is the initial-record
    sentinel: the first occurrence of an anchor within a capture, and the first interpretation of
    an occurrence (or construction) under a (mapping set, normalisation policy, extractor) triple.
    It is never set on a record whose `supersedes_*` is set. A comparative interpretation equal to
    the original package's selection is `ORIGINAL`; only a differing one is
    `COMPARATIVE_RESTATEMENT`. Re-processing a stored capture (Task 5 reuse levels): a new
    extractor's occurrences and interpretations are `PARSER_REEXTRACTION`, a new normalisation
    policy's interpretations `NORMALISATION_POLICY_CHANGE`, each superseding the same anchor's and
    entry's latest prior-triple interpretation (outside any pinned candidate set); a
    mapping-set-only change is `ORIGINAL` under its new triple. Every revision uses only the spec's seven causes.
    **Cause precedence (one rule, applied once when an interpretation is first written):**
    (1) a reprocessing cause — `PARSER_REEXTRACTION`, then `NORMALISATION_POLICY_CHANGE` — when a
    prior-triple interpretation of the same anchor and entry exists, with its predecessor set;
    (2) else `COMPARATIVE_RESTATEMENT` when the comparative check (Task 6) names it; (3) else
    `ORIGINAL`. A reprocessed comparative therefore keeps its reprocessing cause and predecessor;
    whether it differs from its original is still surfaced at run time (Task 9), never by the
    stored cause.
11. **Corroboration in D1a is first-party-only groundwork.** Task 8 implements corroboration rows
    1, 2, 2a, 5 and 7 (data spec §5) for an empty vendor set. That is enough to report
    `NOT_APPLICABLE`, `UNAVAILABLE`, `NOT_COMPARABLE`, `NO_SOURCE` and `FILING_ONLY`. A non-empty
    vendor set raises `VendorCorroborationNotImplemented`. D1b.2 (`eqos-u0u.2`) extends the same
    `corroboration_status` in the same module with the vendor rows and tests the whole table row by
    row. This is an extension, not a parallel implementation.
12. **First-party intake.** The existing `ApprovedIntakeContext` requires exactly three vetted
    roles (XBRL, results PDF, transcript) and `cli.py` passes `intake_context=None` by default, so
    it cannot stage an XBRL-only package (FY25 Q2) and gives the ordinary CLI no authority. D1a
    adds a package-shaped intake in `fundamentals/evidence/capture_intake.py`:
    - `RetainedCaptureBinding` (frozen: `representation`, `source_id`, `relative_path`,
      `expected_sha256`, `filed_at_raw`), one per member present;
    - `RetainedIntake` (frozen: `bindings`, `retrieval_manifest_sha256`,
      `issuer_config_sha256: str | None`, `store_anchor: DirectoryAnchor`,
      `input_anchor: DirectoryAnchor`);
    - `retained_intake_from_manifest(manifest_path: Path, *, issuer: str, quarter: str, kinds: Mapping[Representation, str], store_root: Path, input_root: Path, issuer_config: Path | None) -> RetainedIntake`.
      Bindings come only from manifest entries matching issuer, quarter and kind; relative paths are
      resolved under `input_root` (`nse/` or `nse_pdf/` + filename), never absolute.
    **Source authority (data spec l.329).** The operator names files but grants no authority.
    Before staging, each binding's (`source_id`, surface) is checked against this table through an
    injected `SourceCatalog` (`BUILTIN_SOURCES` extended with the issuer config's `results_pdf`
    declaration, as `api/watchlist_config.stock_catalog` does):

    | Representation | `surface` (`FirstPartySurface`) | `source_id` | Declared by |
    |---|---|---|---|
    | XBRL | `NSE_XBRL_INSTANCE` | `nse-indas-xbrl-consolidated` | `BUILTIN_SOURCES` (`source_catalog.py:155`) |
    | PDF | `NSE_RESULTS_PDF` | issuer config `results_pdf.source_id` (e.g. `aparinds-fy26-q2-results-pdf`) | issuer config, `source_class: first_party` |

    Authorised iff `catalog.describe(source_id)` resolves to `FIRST_PARTY`, `may_reconcile`, and
    the pair is in the table; anything else records a `NOT_AUTHORISED` acquisition attempt and
    stages nothing. Tests add a first-party `marked-` namespace to the injected catalog; the CLI
    never does. Vendor and retention authority stay in D1b/D9. Staging reuses one core extracted
    from `stage_local_source` into `fundamentals.store.capture_local.capture_local_original`
    (below `api/`; `api/source_intake.py` re-exports it, behaviour and tests unchanged).
13. **`EvidenceTier` moves to contracts.** `EvidenceTier` and its ordering (`TIER_ORDER`,
    `weakest(*tiers)`) live in `src/fundamentals/contracts/evidence_tier.py`.
    `fundamentals.ingest.screener_crosscheck` re-exports it, so existing importers are unchanged.
    New code imports it from contracts only.
14. **Exit codes** for `fundamentals compare run`. Code 2 is avoided because argparse uses it for
    usage errors.

    | Code | `RunExitStatus` | Status |
    |---|---|---|
    | 0 | `SUCCESS` | Used in D1a |
    | 3 | `SUCCESS_WITH_OPEN_HIGH` | Declared now, first emitted by D1b.3 |
    | 4 | `INCOMPLETE` | Used in D1a |
    | 5 | `FAILURE` | Used in D1a |

## File map

Responsibility, one line each. "Create" unless marked (M) for modify.

| Path | Responsibility | Task |
|---|---|---|
| `pyproject.toml` (M) | Add `psycopg[binary]`, `psycopg-pool`, `pydantic-settings` via `uv add`; register the `pg` and `retained` markers | 1 |
| `.env.example` (M) | Add `EQOS_PG_HOST`, `EQOS_PG_MIGRATOR_PASSWORD`, `EQOS_PG_RUNTIME_PASSWORD`, `EQOS_PG_TEST_DB_PREFIX` with placeholder values | 1 |
| `compose.yaml` (M, only if needed) | No change expected. Task 1 verifies the §6 service contract and edits only on a found gap | 1 |
| `.claude/project/verification.md` (M), `.codex/project/verification.md` (M) | `pg` needs the compose service up; `retained` needs the gitignored originals; the two opt-outs; the `.codex` copy drops its "no real test gate" lines | 1 |
| `src/fundamentals/pg/__init__.py` | Package marker | 1 |
| `src/fundamentals/pg/settings.py` | `PgSettings` (pydantic-settings), `PgRole`, role-name constants, conninfo building | 1 |
| `src/fundamentals/pg/pool.py` | Pool construction with timeouts; `DatabaseUnavailableError` | 1 |
| `src/fundamentals/pg/migrations.py` | Ordered, checksum-guarded, gap-tolerant migration runner; role bootstrap | 1 |
| `src/fundamentals/api/db_cli.py` | `fundamentals db bootstrap` and `fundamentals db migrate` | 1 |
| `src/fundamentals/api/cli_parser.py` (M), `src/fundamentals/api/cli.py` (M) | Register `db`, `evidence` and `compare` subcommands and dispatch them | 1, 5, 9 |
| `tests/fundamentals/pg_support.py` | Template and per-test database lifecycle, guards, fixtures | 1 |
| `tests/fundamentals/conftest.py` | Import `pg_db` and its session template fixture from `pg_support` so every standalone Verify command collects them | 1 |
| `tests/fundamentals/test_pg_migrations.py` | Runner ordering, checksum drift, gap tolerance, guards | 1 |
| `migrations/0001_evidence.sql` | Schema `eqos`: identity, evidence and run tables, constraints, immutability triggers, grants | 2 |
| `src/fundamentals/contracts/basis_status.py` | `BasisStatus` (shared by Task 2's seed and Task 3's applicability) | 2 |
| `config/identity/aparinds.yaml` | Evidenced APARINDS identity input (ISIN, scrip, symbol, basis status, fiscal year end) citing capture hashes | 2 |
| `src/fundamentals/pg/identity_seed.py` | Identity-input loader; seed entity, security, listing, basis-status and settings rows | 2 |
| `tests/fundamentals/test_pg_evidence_schema.py` | D1a.1 acceptance | 2 |
| `src/fundamentals/contracts/evidence_tier.py` | `EvidenceTier`, `TIER_ORDER`, `weakest` | 3 |
| `src/fundamentals/ingest/screener_crosscheck.py` (M) | Re-export `EvidenceTier` from contracts; no behaviour change | 3 |
| `src/fundamentals/contracts/canonical.py` | Shared enums: family, value kind, basis, period kind, temporal role, applicability, value identity, representation | 3 |
| `src/fundamentals/contracts/qualification.py` | `QualificationScope`, typed conditions, `QualificationContext`, `ScopedTier`, `scoped_tier` | 3 |
| `src/fundamentals/contracts/versioning.py` | `VersionContentDriftError` (raised by every versioned loader and the run) | 3 |
| `src/fundamentals/contracts/measurement_key.py` | `PeriodInterval`, `DimensionSet`, `MeasurementKey`, period-kind derivation | 3 |
| `config/dictionary/v1/*.yaml` | Dictionary v1 rows per family, templates, applicability rules, metadata; `derived.yaml` is the formula set | 3 |
| `src/fundamentals/canon/__init__.py` | Package marker | 3 |
| `src/fundamentals/canon/dictionary.py` | Dictionary models and the validating loader | 3 |
| `src/fundamentals/canon/applicability.py` | Applicability decision from context only | 3 |
| `docs/specs/artifacts/dictionary-v1-manifest.md` | Hand-authored resolved v1 manifest: counts per family, template instantiation rules | 3 |
| `tests/fundamentals/test_canon_dictionary_load.py`, `tests/fundamentals/test_canon_applicability.py` | D1a.2 acceptance | 3 |
| `config/rounding_policy/v1.yaml` | Pinned storage scale per value kind | 4 |
| `src/fundamentals/contracts/comparison.py` | `SourceState`, `CalculationState` (Task 4); pair, extraction, corroboration, triage and reason enums (Task 8) | 4, 8 |
| `src/fundamentals/contracts/interval.py` | `Interval` value type and its exact-rational arithmetic (no imports above `contracts/`) | 4 |
| `src/fundamentals/canon/interval.py` | Re-exports `Interval`; half-even storage, outward rounding, rounding policy | 4 |
| `src/fundamentals/canon/formula.py` | Temporal-role key resolution, dimensional aggregation, formula evaluation, calculation-state table, traces | 4 |
| `src/fundamentals/canon/period_aggregation.py` | Q4 = FY − 9M, H2 = FY − H1, TTM; revision compatibility | 4 |
| `tests/fundamentals/test_canon_formula.py`, `tests/fundamentals/test_canon_interval.py` | D1a.3 acceptance | 4 |
| `src/fundamentals/extract/pdf_statement_pages.py` | Family-specific statement-page discovery, scope blocks, column intervals and banded row extraction | 11 |
| `src/fundamentals/api/config.py` (M) | Optional `statement_pages` marker overrides on `PdfParseConfig` | 11 |
| `config/aparinds-fy26-q2.yaml` (M) | Additive `pdf_parse.statement_pages` entry: the evidenced page-6 unit variant "Rs. in crones" | 11 |
| `tests/fundamentals/test_pdf_statement_pages.py` | Retained Q2 FY26 P&L, BS, CF and segment pages located and read (`retained`) | 11 |
| `src/fundamentals/contracts/evidence.py` | Occurrence, interpretation, package, capture-reference, attempt models and enums (Task 5); `RunMode`, `PinnedVersions`, `KeySelection` (Task 6) | 5, 6 |
| `src/fundamentals/contracts/acquisition_outcome.py` (M) | Add `ExtractionOutcome` and its translation, extending the contract without replacing it | 5 |
| `src/fundamentals/extract/xbrl_parser.py` (M) | Add public `iter_raw_facts` (numeric and text facts, nil, raw text, decimals, unit, dimensions). `parse_instance` unchanged | 5 |
| `src/fundamentals/store/capture_local.py` | `capture_local_original`, extracted from `stage_local_source` (store layer, below `api/`) | 5 |
| `src/fundamentals/api/source_intake.py` (M) | Import and re-export `capture_local_original`; behaviour unchanged | 5 |
| `config/normalisation_policy/v1.yaml` | Scale by raw unit/scale, sign defaults, dash rules (one in v1, construction-scoped, Task 5) | 5 |
| `config/mappings/v1.yaml`, `config/mappings/xbrl/v1/*.yaml`, `config/mappings/pdf/v1/*.yaml`, `config/mappings/constructions/v1.yaml`, `config/mappings/statement_anchors/v1.yaml` | Mapping set v1: metadata, `in-capmkt` and `in-bse-fin` entries, PDF layout entries, source-scoped constructions, structural statement anchors | 5 |
| `src/fundamentals/evidence/__init__.py` | Package marker | 5 |
| `src/fundamentals/evidence/capture_intake.py` | Retained first-party intake and source-authority check (design decision 12) | 5 |
| `src/fundamentals/evidence/member_identity.py` | Verify a member's document identity against seeded issuer identifiers | 5 |
| `src/fundamentals/evidence/mapping.py` | Mapping-set models and validating loader; `UNSUPPORTED_SCHEMA` | 5 |
| `src/fundamentals/evidence/xbrl_adapter.py` | Capture bytes to XBRL occurrences | 5 |
| `src/fundamentals/evidence/pdf_adapter.py` | Capture bytes to PDF occurrences per statement family | 5 |
| `src/fundamentals/evidence/interpret.py` | Occurrence plus mapping to an interpretation; source-scoped constructions | 5 |
| `src/fundamentals/evidence/presence.py` | Structural statement presence and package reporting kind | 5 |
| `src/fundamentals/evidence/repository.py` | Idempotent PostgreSQL reads and writes for evidence and run tables | 2, 5, 7, 9 |
| `src/fundamentals/evidence/first_party_ingest.py` | Stage captures, build the package, run adapters, interpret, write (Task 5); comparative revision cause (Task 6) | 5, 6 |
| `src/fundamentals/api/evidence_cli.py` | `fundamentals evidence ingest` | 5 |
| `tests/fundamentals/retained_support.py` | Resolve and hash-verify Apar originals; marked copies; build `RetainedIntake` for tests | 5 |
| `tests/fundamentals/test_evidence_first_party.py` | D1a.4 acceptance (adapters, values, traces, fixtures) | 5, 7 |
| `src/fundamentals/evidence/selection.py` | Eligibility, package selection, interpretation selection, the opening-instant rule, restatement test | 6 |
| `tests/fundamentals/test_evidence_selection.py` | D1a.4 acceptance (selection: unit plus revision-fixture integration) | 6 |
| `config/mappings/alignment/v1.yaml` | Filing-specific alignment rules: subtotal identities and layout anchors | 7 |
| `src/fundamentals/evidence/alignment.py` | Prove XBRL–PDF alignment per filing and key; record proofs | 7 |
| `src/fundamentals/evidence/derived.py` | Scoped tiers; evaluate derived rows per representation; persist traces | 7 |
| `config/comparison_policy/v1.yaml` | Policy v1: magnitude threshold 0.5% | 8 |
| `config/definition_sets/v1.yaml` | Definition set v1 (empty record list) | 8 |
| `src/fundamentals/compare/__init__.py` | Package marker | 8 |
| `src/fundamentals/compare/policy.py` | Comparison-policy model and loader | 8 |
| `src/fundamentals/compare/definitions.py` | Definition-set models, loader, idempotent publish | 8 |
| `src/fundamentals/compare/triage.py` | `STRUCTURAL` / `MAGNITUDE` / `NOISE` classification | 8 |
| `src/fundamentals/compare/tables.py` | Pair, extraction, derived-extraction and first-party-only corroboration tables | 8 |
| `tests/fundamentals/test_compare_extraction_tables.py` | D1a.5 acceptance | 8 |
| `src/fundamentals/compare/run.py` | Run request, manifest, identity hash, atomic publication, replay | 9 |
| `src/fundamentals/compare/resolve.py` | Per-run resolution: context, attempt states, selection, derivation | 9 |
| `src/fundamentals/compare/report.py` | Render a stored run's report for one company and period | 9 |
| `src/fundamentals/api/compare_cli.py` | `fundamentals compare run` and `fundamentals compare report`; exit codes | 9 |
| `tests/fundamentals/test_compare_runs.py` | D1a.6 acceptance | 9 |
| `tests/fundamentals/test_compare_tracer.py` | D1a.7 acceptance (tracer e2e) | 10 |

## Tasks

### Task 1: PostgreSQL settings, pool, migration runner and test-database harness

Goal: The project can reach the compose PostgreSQL service through injected settings. It can
bootstrap the migrator and runtime roles and apply SQL migrations in a safe order. Tests get an
isolated, freshly migrated database and can never touch the main one.

Stage: eqos-3f9.1

Files:
- Create: `src/fundamentals/pg/__init__.py`, `src/fundamentals/pg/settings.py`, `src/fundamentals/pg/pool.py`, `src/fundamentals/pg/migrations.py`, `src/fundamentals/api/db_cli.py`, `tests/fundamentals/pg_support.py`, `tests/fundamentals/conftest.py`
- Modify: `pyproject.toml`, `.env.example`, `src/fundamentals/api/cli_parser.py`, `src/fundamentals/api/cli.py`, `.claude/project/verification.md`, `.codex/project/verification.md` (its lines 3–5 still say the repo has no real test gate); `compose.yaml` only if Task 1 finds a gap against the §6 service contract
- Test: `tests/fundamentals/test_pg_migrations.py`

Interfaces:
- Consumes: none.
- Produces:
  - `fundamentals.pg.settings.PgSettings`: a pydantic-settings model, env prefix `EQOS_PG_`, `env_file=".env"`, `extra="ignore"` (`.env` already holds `EQOS_PG_DATA_DIR`, which only compose reads). Fields:

    | Field | Type | Default |
    |---|---|---|
    | `host` | `str` | — |
    | `port` | `int` | — |
    | `db` | `str` | — |
    | `user` | `str` | — (admin) |
    | `password` | `SecretStr` | — |
    | `migrator_password` | `SecretStr` | — |
    | `runtime_password` | `SecretStr` | — |
    | `connect_timeout_s` | `int` | 5 |
    | `statement_timeout_ms` | `int` | 30000 |
    | `pool_min_size` | `int` | 1 |
    | `pool_max_size` | `int` | 4 |
    | `test_db_prefix` | `str` | `"eqos_test_"` |

    Method: `conninfo(role: PgRole, *, dbname: str | None = None) -> str`.
  - `PgRole` StrEnum: `ADMIN`, `MIGRATOR`, `RUNTIME`.
  - Constants: `MIGRATOR_ROLE_NAME = "eqos_migrator"`, `RUNTIME_ROLE_NAME = "eqos_runtime"`, `SCHEMA_NAME = "eqos"`.
  - `fundamentals.pg.pool.open_pool(settings: PgSettings, role: PgRole, *, dbname: str | None = None) -> psycopg_pool.ConnectionPool`. It applies the connect and statement timeouts, waits at most `connect_timeout_s` for the first connection, and raises `DatabaseUnavailableError` (subclass of `Exception`) when unreachable.
  - `fundamentals.pg.migrations`:
    - `AppliedMigration` (frozen: `filename: str`, `sha256: str`, `applied_at: datetime`)
    - `MigrationChecksumError`, `MigrationNameError`
    - `bootstrap_roles(admin: psycopg.Connection, settings: PgSettings, dbname: str) -> None`
    - `apply_migrations(migrator: psycopg.Connection, migrations_dir: Path) -> tuple[AppliedMigration, ...]`
  - CLI: `fundamentals db bootstrap` and `fundamentals db migrate`, both reading `PgSettings` at the composition root.
  - `tests/fundamentals/pg_support.py`:
    - `PgTestDatabase`, frozen, with `dbname: str` and `settings: PgSettings`. Methods: `runtime_pool() -> ConnectionPool`, `migrator_connection() -> psycopg.Connection`, `cli_env() -> dict[str, str]`. `cli_env` gives the `EQOS_PG_*` variables that point a CLI at this database.
    - Pytest fixture `pg_db` (function scope, yields `PgTestDatabase`) built on a session-scoped template fixture `pg_template`.
  - `tests/fundamentals/conftest.py` imports `pg_db` and `pg_template` from `pg_support` (explicit import; `pytest_plugins` is not allowed in a non-root conftest), so `uv run pytest tests/fundamentals/<file>.py` collects them.
  - Pytest markers `pg` and `retained`.

Approach: Add dependencies with `uv add`. Settings are read only in `db_cli.py`, the other CLI
composition roots and the test harness. Business modules receive a pool or connection. The
migration runner works as follows:
- It takes a session advisory lock.
- It creates `eqos_meta.schema_migrations` (filename primary key, sha256, applied_at) if absent.
- It accepts only files named `NNNN_<snake>.sql`.
- It refuses any applied file whose checksum changed.
- It applies, in filename order, **every file not yet recorded** (set difference, never "greater
  than the highest applied"), each in its own transaction.

`bootstrap_roles` creates a missing role with its configured password and never alters an existing
role. It grants CONNECT and CREATE on the target database to the migrator and CONNECT to the runtime
role. The harness and its two guards follow design decision 3. Before editing `compose.yaml`, check
it against the §6 service contract: pinned `postgres:18.6`, loopback with the configured port, bind
mount at the image's mount point, database name and role from `.env`. Update both
`verification.md` files (`.claude/project/` and `.codex/project/`) with the `pg` and `retained`
requirements, opt-outs and the real test gate.

Verification: `uv run pytest tests/fundamentals/test_pg_migrations.py` passes against the running
compose service. It shows: migrations apply in filename order; a lower-numbered file added after a
higher one is applied on the next run; an edited applied file raises `MigrationChecksumError`; a
re-run applies nothing; the harness refuses a database name without the test prefix and refuses
when the prefix matches `EQOS_PG_DB`, in both cases before any connection is opened (a
connection-factory spy records none), and its lifecycle connection names the `postgres`
maintenance database; `PgSettings` loads with `EQOS_PG_DATA_DIR` present in the env
file. `uv run mypy --strict src` is clean.

Test seams: `apply_migrations` over a temporary migrations directory against a `pg_db` database;
the harness guard functions.

Dependencies: None

Risks: Ordering and guard behaviour is test-first. The guards are the only barrier between tests
and the owner's database, so write the refusal tests before the harness. The template-clone
approach needs zero connections to the template during `CREATE DATABASE … TEMPLATE`; close every
pool before cloning. Running the `pg` suite now requires the compose service up. That changes what
`uv run pytest tests/fundamentals` and `scripts/verify.sh gate` need, and is documented in
`verification.md`.

### Task 2: Evidence schema, identity tables and identity seeding

Goal: Migration `0001_evidence.sql` creates the identity, evidence and run schema. Every reference
is a foreign key in a typed column or a normalized reference table; no evidence id or operand
reference lives only inside an array or JSON. Every table that promises idempotency has an exact
unique key. The runtime role cannot UPDATE or DELETE any row, through either privileges or
triggers. The migration role owns every object. APARINDS identity is seeded from an evidenced
identity input with stable internal ids.

Stage: eqos-3f9.1

Files:
- Create: `migrations/0001_evidence.sql`, `src/fundamentals/contracts/basis_status.py`, `config/identity/aparinds.yaml`, `src/fundamentals/pg/identity_seed.py`
- Test: `tests/fundamentals/test_pg_evidence_schema.py`

Interfaces:
- Consumes: `PgSettings`, `open_pool`, `apply_migrations`, `pg_db`, `MIGRATOR_ROLE_NAME`, `RUNTIME_ROLE_NAME`, `SCHEMA_NAME` (Task 1). `EntityMap`, `Entity`, `IdentifierNamespace` (`fundamentals.contracts.entity_identity`); `build_entity_map` and the synthetic records in `tests/fundamentals/entity_map_fixtures.py` (generic seeding test only; they contain no APARINDS).
- Produces:
  - Tables in schema `eqos`, each with a `bigint` identity primary key. "FK" means a declared foreign key; "XOR(a, b, …)" means `CHECK (num_nonnulls(a, b, …) = 1)`; "≤1(…)" means `num_nonnulls(…) <= 1`; every enum column has a CHECK listing its Python enum's values. Unique keys marked NND are `UNIQUE NULLS NOT DISTINCT`.
  - **Identity and settings tables** (append-only; corrections are new rows, temporal identity events are D6; `reject_mutation` applies to them like every other table):

    | Table | Columns | Unique / checks |
    |---|---|---|
    | `evidence_inputs` | `kind` (`ENTITY_MAP`, `ISSUER_IDENTITY`, `ISSUER_CONFIG`), `label`, `content_sha256`, `recorded_at` | (`kind`, `content_sha256`) |
    | `evidence_input_captures` | `evidence_input_id` FK, `capture_ref_id` FK | (`evidence_input_id`, `capture_ref_id`) |
    | `reporting_entities` | `entity_key`, `market`, `display_name`, `evidence_input_id` FK, `created_at` | (`entity_key`) |
    | `securities` | `entity_id` FK, `isin` nullable, `share_class`, `evidence_input_id` FK | NND (`entity_id`, `share_class`, `isin`); partial unique (`isin`) WHERE `isin IS NOT NULL` |
    | `listings` | `security_id` FK, `venue` (`NSE`/`BSE`), `symbol`, `evidence_input_id` FK | (`venue`, `symbol`, `security_id`) |
    | `entity_basis_status` | `entity_id` FK, `basis_status`, `evidence_input_id` FK, `recorded_at` | (`entity_id`, `basis_status`, `evidence_input_id`) |
    | `settings_records` | `entity_id` FK, `setting_key` (`FISCAL_YEAR_END_MONTH`, `PDF_PRINTED_UNIT`, `PDF_LAYOUT`), `value_text`, `evidence_input_id` FK, `recorded_at` | (`entity_id`, `setting_key`, `value_text`, `evidence_input_id`) |
    | `segment_members` | `entity_id` FK, `axis`, `member`, `display_name`, `valid_from`, `valid_to` nullable, `recorded_at` | NND (`entity_id`, `axis`, `member`, `valid_from`) |
    | `segment_member_evidence` | `segment_member_id` FK, `occurrence_id` FK | (`segment_member_id`, `occurrence_id`) |

  - **Evidence tables:**

    | Table | Columns | Unique / checks |
    |---|---|---|
    | `capture_refs` | `source_id`, `surface`, `request_key`, `capture_id`, `blob_sha256`, `record_sha256`, `registered_at`, `first_seen_at` | (`source_id`, `surface`, `request_key`, `capture_id`) |
    | `filing_packages` | `entity_id` FK, `family`, `reporting_period_end`, `basis`, `framework`, `reporting_kind`, `knowledge_time` (latest member), `supersedes_package_id` FK nullable, `evidence_sha256` | (`entity_id`, `family`, `reporting_period_end`, `basis`, `framework`, `evidence_sha256`) |
    | `package_members` | `package_id` FK, `capture_ref_id` FK, `representation`, `knowledge_time`, `knowledge_time_raw`, `knowledge_time_status` | (`package_id`, `representation`) |
    | `package_statements` | `package_id` FK, `statement_family`, `role` (`PRESENT`, `REPLACED`) | (`package_id`, `statement_family`, `role`) |
    | `package_statement_evidence` | `package_statement_id` FK, `occurrence_id` FK | (`package_statement_id`, `occurrence_id`) |
    | `acquisition_attempts` | `stage` (`ACQUISITION`, `EXTRACTION`), `source_id`, `surface`, `entity_id` FK, `period_end`, `basis`, `framework`, `representation`, `statement_family` nullable, `package_id` FK nullable, `capture_ref_id` FK nullable, `input_sha256`, `extractor_version` (explicit empty for `ACQUISITION`), `outcome`, `reason` nullable, `attempted_at` | NND (`stage`, `source_id`, `surface`, `entity_id`, `period_end`, `basis`, `framework`, `representation`, `statement_family`, `package_id`, `capture_ref_id`, `input_sha256`, `extractor_version`, `outcome`); `stage = 'EXTRACTION'` ⇒ `capture_ref_id IS NOT NULL` and `extractor_version <> ''` |
    | `occurrences` | `capture_ref_id` FK, `representation`, `extractor_version`, `native_field`, `raw_value_text` nullable, `raw_unit`, `raw_scale`, `raw_sign`, `precision_kind` (`EXACT`, `FINITE`, `UNSUPPORTED`), `declared_precision` nullable, `native_context` jsonb, `period_start`/`period_end`/`period_instant` nullable, `missing_state`, `disclosure` jsonb, `anchor` jsonb, `anchor_key`, `valid_time`, `knowledge_time` nullable, `knowledge_time_status`, `first_seen_at`, `revision_cause` | (`capture_ref_id`, `extractor_version`, `anchor_key`); (`id`, `capture_ref_id`) for the composite FK below; `declared_precision IS NOT NULL` ⇔ `precision_kind = 'FINITE'` |
    | `interpretations` | `origin` (`DIRECT`, `CONSTRUCTED`), `occurrence_id` FK nullable, `capture_ref_id` FK, `representation`, `construction_rule_id` nullable, `input_digest` (`DIRECT`: the occurrence id; `CONSTRUCTED`: SHA-256 of the ordered operand ids), `status`, measurement-key columns (`entity_id` FK, `canonical_id` nullable for `UNMAPPED`, `dictionary_version`, period columns, `basis`, `framework`, `currency` nullable, `value_kind` nullable, `dimension_set` jsonb, `dimension_hash`, `key_digest` nullable), `value`, `lower`, `upper` numeric nullable, `tier`, `qualification_ref` nullable, `mapping_set_version`, `mapping_entry_id` nullable, `normalisation_policy_version`, `extractor_version`, `transform_trace` jsonb (descriptive only), `reason` nullable, `revision_cause`, `supersedes_interpretation_id` FK nullable, `recorded_at` | NND (`input_digest`, `mapping_entry_id`, `construction_rule_id`, `mapping_set_version`, `normalisation_policy_version`, `extractor_version`, `supersedes_interpretation_id`) — `revision_cause` is deliberately outside the key, so a repeat ingest returns the stored row and its cause; `origin = 'DIRECT'` ⇔ `occurrence_id IS NOT NULL`; composite FK (`occurrence_id`, `capture_ref_id`) → `occurrences`; `revision_cause = 'ORIGINAL'` ⇒ `supersedes_interpretation_id IS NULL` |
    | `interpretation_operands` | `interpretation_id` FK, `ordinal`, `operand_interpretation_id` FK | (`interpretation_id`, `ordinal`) |
    | `interpretation_condition_evidence` | `interpretation_id` FK, `condition_id`, `holds`, `evidence_interpretation_id` FK | (`interpretation_id`, `condition_id`, `evidence_interpretation_id`) |
    | `alignment_proofs` | `package_id` FK, `key_digest`, `canonical_id`, `rule_id`, `rule_set_version`, `xbrl_interpretation_id` FK, `pdf_interpretation_id` FK, `participants_digest`, `holds` | (`package_id`, `key_digest`, `rule_id`, `rule_set_version`, `participants_digest`) |
    | `alignment_proof_participants` | `alignment_proof_id` FK, `interpretation_id` FK, `representation` | (`alignment_proof_id`, `interpretation_id`) |
    | `calculation_traces` | `content_sha256`, `trace_kind` (`FORMULA`, `DIMENSIONAL_AGGREGATE`, `AVERAGE`, `PERIOD_DERIVATION`), `formula_id`, `formula_version`, `formula_tier`, `formula_qualification_ref`, `rounding_policy_id`, `key_digest`, `value_identity`, `state`, `value`/`lower`/`upper` nullable (rounded), `exact_value`/`exact_lower`/`exact_upper` text nullable (reduced `p/q`), `effective_tier` | (`content_sha256`) |
    | `calculation_trace_operands` | `calculation_trace_id` FK, `ordinal`, `operand_name`, `key_digest`, `temporal_role`, `interpretation_id` FK nullable, `operand_trace_id` FK nullable, `alignment_proof_id` FK nullable, `mapping_entry_id` nullable, `qualification_ref` nullable, `scoped_tier`, `selection_source`, `source_state`, `value`/`lower`/`upper` nullable, `exact_value`/`exact_lower`/`exact_upper` text nullable | (`calculation_trace_id`, `ordinal`); ≤1(`interpretation_id`, `operand_trace_id`) |
    | `definition_sets` | `version`, `content_sha256`, `published_at` | (`version`) |
    | `definition_records` | `definition_set_id` FK, `record_id`, `scope` (`MAPPING`, `MEASUREMENT`, `FILING`), `mapping_entry_id` nullable, `key_digest` nullable, `package_id` FK nullable, `canonical_id`, `operand_name` nullable, `evidence_ref`, `explained_amount`, `unit` | (`definition_set_id`, `record_id`); XOR(`mapping_entry_id`, `key_digest`, `package_id`) and the non-null one matches `scope` |

  - **Run tables:**

    | Table | Columns | Unique / checks |
    |---|---|---|
    | `runs` | `identity_hash`, `cutoff`, `mode`, `status`, `code_version`, `manifest` jsonb (descriptive copy), `manifest_sha256`, `created_at` | (`identity_hash`) |
    | `run_versions` | `run_id` FK, `pin` (the `PinnedVersions` field names), `version`, `content_sha256` | (`run_id`, `pin`) |
    | `run_inputs` | `run_id` FK, `input_kind`, `disposition` (`SELECTED`, `SURFACED`, `NOT_SELECTED`, `FAILED_ATTEMPT`), one nullable FK column per kind: `capture_ref_id`, `package_id`, `occurrence_id`, `interpretation_id`, `attempt_id`, `alignment_proof_id`, `calculation_trace_id`, `evidence_input_id`, `settings_record_id`, `basis_status_id`, `segment_member_id`, `package_statement_id`, `definition_set_id` | XOR over the thirteen FK columns, and the non-null column matches `input_kind`; NND (`run_id`, the thirteen FK columns) |
    | `results` | `run_id` FK, measurement-key columns, `key_digest`, `value_identity`, `applicability`, `applicability_rule_id`, `extraction_status`, `extraction_reason`, `corroboration_status`, `corroboration_reason` | (`run_id`, `key_digest`, `value_identity`) |
    | `result_source_values` | `result_id` FK, `source_role`, `representation`, `source_state`, `reason` nullable, `value` nullable, `lower`/`upper` nullable, `interpretation_id` FK nullable, `calculation_trace_id` FK nullable, `attempt_id` FK nullable, `calculation_state` nullable | (`result_id`, `source_role`, `representation`); ≤1(`interpretation_id`, `calculation_trace_id`) |
    | `result_surfaced_restatements` | `result_id` FK, `interpretation_id` FK | (`result_id`, `interpretation_id`) |
    | `pair_outcomes` | `result_id` FK, `pair_kind` (`EXTRACTION`, `REPORTED_VS_DERIVED`), `left_value_id` FK, `right_value_id` FK (→ `result_source_values`), `outcome`, `reason`, `triage`, `difference`, `interval_gap`, `definition_record_id` FK nullable | (`result_id`, `pair_kind`, `left_value_id`, `right_value_id`) |
    | `pair_adjustments` | `pair_outcome_id` FK, `definition_record_id` FK, `operand_name`, `representation`, `direction`, `amount` | (`pair_outcome_id`, `definition_record_id`, `operand_name`) |

    Pair children hold outcomes; source values hold values; a purge (D9) can delete vendor
    `result_source_values` values without touching outcomes (ledger §6 item 4).
  - **Capture ownership.** Occurrences, interpretations and capture-determined attempts belong to
    the capture, never to a package. A package reaches them only through `package_members`
    (package ↔ capture), so a revised package that reuses an unchanged member (a changed PDF with
    the same XBRL) attaches to the same immutable rows. A constructed interpretation's operands
    must share its `capture_ref_id`. An attempt carries `package_id` only when its outcome depends
    on package context (`IDENTITY_REJECTED` against the package basis, a family `PARSE_FAILED`
    decided by package presence, a failed or absent member); `package_id` is part of its key.
  - **Write classes.** Captures, packages, occurrences, interpretations, attempts, alignment
    proofs, calculation traces and identity/settings rows are **idempotent evidence writes**:
    content-identified, insert-on-conflict, returning the existing id, safe to repeat outside a
    run and harmless if a run later fails (they are evidence, never results). `interpretations.id`
    is `GENERATED BY DEFAULT AS IDENTITY` so ingest can insert ids it reserved with `nextval`
    (Task 5 qualification ordering); every other table uses `GENERATED ALWAYS`. `runs`,
    `run_versions`, `run_inputs`, `results` and their children are written only inside the
    publication transaction (Task 9).
  - `eqos.reject_mutation()` trigger function attached BEFORE UPDATE OR DELETE (row) and BEFORE TRUNCATE (statement) on every table above. Grants: runtime role gets SELECT and INSERT only.
  - `fundamentals.pg.identity_seed`:
    - `fundamentals.contracts.basis_status.BasisStatus` StrEnum: `CONSOLIDATED_AND_STANDALONE`, `STANDALONE_ONLY` (Task 3 consumes it; it is no longer in `canonical.py`).
    - `IssuerIdentityInput` (frozen: `entity_key`, `display_name`, `isin`, `share_class`, `nse_symbol`, `bse_scrip`, `basis_status: BasisStatus`, `fiscal_year_end_month: int`, `citations: tuple[IdentityCitation, ...]`, `content_sha256`). `IdentityCitation` (frozen: `field`, `capture_sha256`, `native_field: str | None`, `context_ref: str | None`, `pages: tuple[int, ...]`).
    - `load_issuer_identity(path: Path) -> IssuerIdentityInput`. It refuses any field without a citation, for every issuer.
    - `seed_issuer_identity(conn: psycopg.Connection, identity: IssuerIdentityInput) -> IdentitySeedReport`.
    - `seed_identity(conn: psycopg.Connection, entity_map: EntityMap, *, source_sha256: str) -> IdentitySeedReport`.
    - `IdentitySeedReport` (frozen: `entity_ids: Mapping[str, int]`, `evidence_input_id: int`, `inserted: int`, `existing: int`, `skipped: tuple[str, ...]`).
  - `EvidenceRepository` reads for identity evidence (Task 5 owns the class; Task 2 defines the SQL it wraps). As-of reads, used only by a fresh run's resolution: `basis_status_as_of(entity_id, cutoff) -> tuple[int, BasisStatus] | None` (latest `recorded_at` ≤ cutoff), `settings_as_of(entity_id, key, cutoff) -> SettingsRecord | None`, `segment_members_as_of(entity_id, axis, cutoff) -> tuple[SegmentMemberRecord, ...]`. Immutable by-id reads, used by replay (Task 9): `get_evidence_inputs(ids) -> tuple[EvidenceInputRecord, ...]`, `get_basis_statuses(ids) -> tuple[BasisStatusRecord, ...]`, `get_settings_records(ids) -> tuple[SettingsRecord, ...]`, `get_segment_members(ids) -> tuple[SegmentMemberRecord, ...]` (with evidence occurrence ids). Each record model is frozen and carries its row id and every column above.
  - `config/identity/aparinds.yaml`: `entity_key: APARINDS`; ISIN `INE372A01015` (`ISIN`), scrip `532259` (`ScripCode`), symbol `APARINDS` (`Symbol`), each cited to the Q2 FY26 `in-capmkt` instance (SHA-256 `90baae0b…d799`, context `OneD`); fiscal year end month 3, cited to `DateOfEndOfFinancialYear` (`2026-03-31`) in the same instance; `basis_status: CONSOLIDATED_AND_STANDALONE`, cited to the Q2 FY26 results PDF (SHA-256 `8be1b8de…4ae5`) pages 1, 3, 6 and 7 (verified: page 1 names the standalone and consolidated results; pages 3, 6 and 7 print the consolidated and standalone P&L, balance sheet and cash flow side by side).

Approach: Write the SQL by hand, in one file, run as the migrator. Every enum-valued column has a
CHECK constraint listing the values of the matching Python enum (Tasks 3–8 define them). The task
copies the value lists from this plan's Interfaces, and later tasks must keep them identical.
Seeding is idempotent:
- one `evidence_inputs` row per input file content;
- one `reporting_entities` row per entity key, with market `IN`;
- one `securities` row per (entity, share class, ISIN), share class `EQUITY`;
- one `listings` row per verified NSE symbol and BSE scrip;
- for an issuer identity input, one `entity_basis_status` and one `settings_records`
  (`FISCAL_YEAR_END_MONTH`) row, both referencing the input;
- conflicts resolve to the existing row, so ids are stable across re-seeds.

Conflicted or unverified entity-map identifiers are not seeded, and the report lists them. Values
are kept separate from outcomes, per the ledger §6 item 4 constraint.

Verification: `uv run pytest tests/fundamentals/test_pg_evidence_schema.py` (marked `pg`) shows:
- for every table, UPDATE and DELETE as `eqos_runtime` raise `InsufficientPrivilege`, and as
  `eqos_migrator` they raise the trigger's exception;
- `eqos_migrator` owns schema `eqos` and every table (catalog query);
- **securities:** inserting the same (`entity_id`, `share_class`, NULL `isin`) twice conflicts;
  inserting one non-null ISIN under two different entities conflicts on the partial index;
- **repeated write:** the same interpretation identity with NULL `supersedes_interpretation_id`
  twice, the same attempt twice and the same calculation trace twice each leave one row;
- **orphan reference:** a `run_inputs` row, a `calculation_trace_operands` row and a
  `segment_member_evidence` row pointing at a missing id each raise `ForeignKeyViolation`;
- **conflicting reference:** a `run_inputs` row with two FK columns set, or with a column not
  matching `input_kind`; a `DIRECT` interpretation whose `capture_ref_id` differs from its
  occurrence's; a definition record whose scope column does not match `scope` — each raises
  `CheckViolation` or `ForeignKeyViolation`;
- **round-trip:** occurrences with `EXACT`, `FINITE` (`declared_precision = -7`) and `UNSUPPORTED`
  precision, and interpretations with a direct `qualification_ref`, a construction-rule
  `qualification_ref` and none, read back field for field; a `FINITE` row without
  `declared_precision` raises `CheckViolation`;
- **shared member:** two packages (an original and a revision) whose `package_members` name the
  same capture both resolve to that capture's single set of occurrences and interpretations;
- `seed_issuer_identity` over `config/identity/aparinds.yaml` twice gives identical ids and
  `inserted == 0` on the second pass; `seed_identity` over the synthetic entity-map fixture does
  the same, with one entity, security and listing row per verified identifier.

Dependencies: 1

Risks: The schema is the shared contract for every later phase, so get the column names right here.
Tasks 5–9 consume these exact names. CHECK lists that drift from Python enums are a defect, so
Task 9's run test round-trips every enum value through an insert. Keep the file below 800 lines by
grouping DDL per table. Apar's basis-status citation is verified (pages above); for any other
issuer, `load_issuer_identity` refuses an uncited basis status rather than guess.

### Task 3: Canonical dictionary v1, shared canonical contracts and applicability

Goal: Dictionary v1 loads from `config/dictionary/v1/`, failing loudly on dangling ids, unit
algebra, cycles, member-of-member lists and duplicate selectors (design decision 9); resolved
counts per family equal the committed manifest. Applicability is decided from context alone,
before any value is examined (rules in Approach). The shared qualification contract exists.

Stage: eqos-3f9.2

Files:
- Create: `src/fundamentals/contracts/evidence_tier.py`, `src/fundamentals/contracts/canonical.py`, `src/fundamentals/contracts/measurement_key.py`, `src/fundamentals/contracts/qualification.py`, `src/fundamentals/contracts/versioning.py`, `src/fundamentals/canon/__init__.py`, `src/fundamentals/canon/dictionary.py`, `src/fundamentals/canon/applicability.py`, `config/dictionary/v1/metadata.yaml`, `config/dictionary/v1/pl.yaml`, `config/dictionary/v1/balance_sheet.yaml`, `config/dictionary/v1/cash_flow.yaml`, `config/dictionary/v1/segment.yaml`, `config/dictionary/v1/shareholding.yaml`, `config/dictionary/v1/derived.yaml`, `config/dictionary/v1/templates.yaml`, `config/dictionary/v1/applicability.yaml`, `docs/specs/artifacts/dictionary-v1-manifest.md`
- Modify: `src/fundamentals/ingest/screener_crosscheck.py` (re-export `EvidenceTier`)
- Test: `tests/fundamentals/test_canon_dictionary_load.py`, `tests/fundamentals/test_canon_applicability.py`

Interfaces:
- Consumes: `AccountingFramework` (`fundamentals.contracts.observation`); `EvidenceTier` (`fundamentals.ingest.screener_crosscheck`, moved by this task); `BasisStatus` (`fundamentals.contracts.basis_status`, Task 2).
- Produces:
  - `fundamentals.contracts.evidence_tier`: `EvidenceTier` (moved unchanged), `TIER_ORDER: tuple[EvidenceTier, ...]` (strongest first: `EQUIVALENCE_DEMONSTRATED`, `RELATED_NOT_EQUIVALENT`, `EQUIVALENCE_UNPROVEN`), `weakest(*tiers: EvidenceTier) -> EvidenceTier`. Every later task imports from here.
  - `fundamentals.contracts.versioning.VersionContentDriftError(ValueError)`: raised by every versioned loader (Tasks 3–8) and the run (Task 9) when a version string is reused with different content.
  - **`fundamentals.contracts.qualification`** (data spec §2 qualification scope; shared by formulas, mapping entries and construction rules):
    - `ConditionPredicate` StrEnum: `EQUALS_ZERO`, `NOT_EQUALS_ZERO`.
    - `QualificationCondition` (frozen: `condition_id: str`, `canonical_id: str`, `predicate: ConditionPredicate`): a fact about the same package, period and basis, e.g. `profit_discontinued_after_tax` `EQUALS_ZERO`.
    - `ProvenCondition` (frozen: `condition_id`, `holds: bool`, `evidence_interpretation_ids: tuple[int, ...]`).
    - `QualificationScope` (frozen: `scope_id`, `schema_identities: frozenset[str]`, `surfaces: frozenset[str]`, `bases: frozenset[Basis]`, `period_kinds: frozenset[PeriodKind]`, `conditions: tuple[QualificationCondition, ...]`, `exclusions: tuple[QualificationCondition, ...]`, `fixture_capture_sha256s: tuple[str, ...]`, `sample_rule: str | None`).
    - `QualificationContext` (frozen: `schema_identity`, `surface`, `basis`, `period_kind`, `proven: Mapping[str, ProvenCondition]`). It is **per measurement** (data spec l.240), never per capture or package: `basis`, `period_kind` and `proven` are for the key's own period and basis.
    - `qualification_context(key: MeasurementKey, *, schema_identity: str, surface: str, fiscal_year_end_month: int, proven: Mapping[str, ProvenCondition]) -> QualificationContext`: `period_kind = key.period.kind(fiscal_year_end_month)`, `basis = key.basis`. The package reporting kind serves applicability only.
    - `ScopedTier` (frozen: `tier: EvidenceTier`, `qualification_ref: str | None`, `condition_evidence: tuple[ProvenCondition, ...]`).
    - `scoped_tier(tier: EvidenceTier, scope: QualificationScope | None, context: QualificationContext) -> ScopedTier`. A demonstrated tier stays demonstrated (with `qualification_ref = scope_id`) only when schema, surface, basis and period kind are in scope, every condition is in `proven` with `holds=True`, and every exclusion is in `proven` with `holds=False`. Anything else — no scope, out of scope, or a condition or exclusion not proven either way — is `EQUIVALENCE_UNPROVEN` with no ref. Never by calendar quarter (data spec §2).
  - **`fundamentals.contracts.canonical` StrEnums:**

    | Enum | Values |
    |---|---|
    | `StatementFamily` | `PL`, `BALANCE_SHEET`, `CASH_FLOW`, `SEGMENT`, `SHAREHOLDING`, `DERIVED` |
    | `ValueKind` | `CURRENCY_AMOUNT`, `PER_SHARE_AMOUNT`, `COUNT`, `PERCENTAGE`, `RATIO`, `DAYS` |
    | `PeriodNature` | `DURATION`, `INSTANT` |
    | `Basis` | `CONSOLIDATED`, `STANDALONE` |
    | `PeriodKind` | `QUARTER`, `HALF_YEAR`, `NINE_MONTH`, `YEAR`, `TTM`, `INSTANT`, `OTHER` |
    | `TemporalRole` | `DURATION`, `CLOSING`, `OPENING`, `AVERAGE` |
    | `ApplicabilityStatus` | `APPLICABLE`, `NOT_APPLICABLE` |
    | `ValueIdentity` | `REPORTED`, `DERIVED` |
    | `DocumentType` | `FINANCIAL_RESULTS`, `SHAREHOLDING_PATTERN` |
    | `ReportingRegime` | `IN_LODR` |
    | `Representation` | `XBRL`, `PDF` |

  - **`fundamentals.contracts.measurement_key`:**
    - `PeriodInterval` (frozen: `start: date | None`, `end: date | None`, `instant: date | None`; exactly one shape is valid), with `kind(fiscal_year_end_month: int) -> PeriodKind`.
    - `DimensionSet` (frozen, sorted `tuple[tuple[str, str], ...]`, explicit empty), with `digest() -> str`.
    - `MeasurementKey` (frozen: `entity_id: int`, `canonical_id: str`, `period: PeriodInterval`, `basis: Basis`, `framework: AccountingFramework`, `currency: str | None`, `value_kind: ValueKind`, `dimensions: DimensionSet`), with `digest() -> str`.
  - **`fundamentals.canon.dictionary`:**
    - `FormulaNode` (frozen operator tree: `op` ∈ {`ADD`, `SUB`, `MUL`, `DIV`, `OPERAND`, `LITERAL`}).
    - `FormulaOperand` (frozen: `name: str`, `canonical_id: str`, `temporal_role: TemporalRole`, `aggregation: DimensionalAggregation | None`).
    - `DimensionalAggregation` (frozen: `axis: str`, `input_members: tuple[str, ...]`, `output_member: str`).
    - `Formula` (frozen: `formula_id`, `version`, `operands`, `expression: FormulaNode`, `output_kind: ValueKind`, `day_count: DayCount | None`, `pbt_id: str | None`, `tier: EvidenceTier`, `qualification: QualificationScope | None`), per design decision 8. v1 formulas are `EQUIVALENCE_UNPROVEN` with no scope unless `derived.yaml` cites qualification evidence.
    - `DictionaryRow` (frozen: `canonical_id`, `family`, `meaning`, `value_kind`, `period_nature`, `sign_convention`, `aggregation_behaviour`, `period_aggregation: PeriodAggregationKind | None`, `applicability_rule_id`, `basis_applicability: frozenset[Basis]`, `dimension_template: str | None`, `formula: Formula | None`, `headline: bool`, `deprecated_by: str | None`).
    - `CanonicalDictionary` (frozen: `version`, `content_sha256`, `formula_set_version`, `formula_set_sha256`), with `row(canonical_id) -> DictionaryRow`, `family_counts() -> Mapping[StatementFamily, int]` and `rows` as a tuple.
    - `load_dictionary(root: Path, version: str) -> CanonicalDictionary`.
    - `DictionaryLoadError(ValueError)`, carrying `defect: DictionaryDefect` (`DANGLING_ID`, `UNIT_ALGEBRA`, `CYCLE`, `MEMBER_OF_MEMBER`, `DUPLICATE_SELECTOR`, `TEMPORAL_ROLE_MISFIT`, `SCHEMA`) and the offending ids.
    - `PeriodAggregationKind` StrEnum: `ADDITIVE_DURATION`, `NONE`.
    - `DayCount` StrEnum: `ACTUAL_DAYS_IN_OUTPUT_INTERVAL`.
  - **`fundamentals.canon.applicability`:**
    - `ApplicabilityContext` (frozen: `regime: ReportingRegime`, `document_type: DocumentType`, `statements_present: frozenset[StatementFamily]`, `period_kind: PeriodKind`, `requested_basis: Basis`, `entity_basis_status: BasisStatus`). `period_kind` is the **package reporting kind** (Task 5 `reporting_kind`): `QUARTER`, `HALF_YEAR`, `NINE_MONTH` or `YEAR`. It has no value fields by construction.
    - `ApplicabilityDecision` (frozen: `status`, `rule_id`).
    - `decide_applicability(row: DictionaryRow, context: ApplicabilityContext) -> ApplicabilityDecision`.
    - `load_applicability_rules` is called by `load_dictionary`.

Approach: Seed rows from the inventory's §2 tables (2a–2f) under the spec's rules:
- every filed line item plus the vendor formula rows;
- both PBT ids: `profit_before_tax` and `profit_before_tax_incl_associates`, with `headline: true`
  on the second;
- `profit_continuing_after_tax`;
- `opex_excl_finance_and_da`, `liabilities_incl_nci`;
- the EPS family as the inventory names it (`eps_basic` = continuing + discontinued,
  `eps_basic_continuing`, `eps_basic_discontinued`, diluted variants);
- OPM, PBT margin, effective tax rate (operand `profit_before_tax`, D6), EBITDA excluding other
  income, receivable days, and a segment-revenue total by dimensional aggregation.

Grouped inventory entries become one id per measure. Templates declare segment, other-expense, OCI
and shareholding-category instantiation; segment templates declare an elimination-basis axis. The
loader validates in a fixed order — schema, dangling ids, temporal-role fit, unit algebra, cycles
(DFS over formula operands), member-of-member, duplicate selectors — and raises on the first defect
class with every offending id. Each failure test loads a temporary copy of v1 with one defect
introduced. `derived.yaml` is the formula set: its version and SHA-256 are pinned separately
(design decision 7).

The manifest markdown is hand-authored from the inventory: counts per family and the instantiation
rules. The count test reads the counts table from that file and compares it with `family_counts()`.
The code under test never writes it.

The `EvidenceTier` move is mechanical: the class body moves verbatim, `screener_crosscheck.py`
imports and re-exports it, and the existing importers (`verify/three_source*.py`,
`verify/laneb_sensitivity_model.py`, `api/upstox_sensitivity_cli.py`) keep working unchanged.

Applicability rules: balance-sheet and cash-flow rows are applicable when `period_kind` is
`HALF_YEAR` or `YEAR`, and when it is `QUARTER` or `NINE_MONTH` only if `statements_present`
contains the family. A `CONSOLIDATED` request against `STANDALONE_ONLY` is `NOT_APPLICABLE`.
`entity_basis_status` always comes from evidenced identity input (Task 2), never from a filing's
own basis declaration; Task 5 validates the declaration separately.

Verification: `uv run pytest tests/fundamentals/test_canon_dictionary_load.py tests/fundamentals/test_canon_applicability.py`
passes. Each listed defect raises `DictionaryLoadError` with the matching `DictionaryDefect`, and
v1's `family_counts()` equals the manifest table. In the applicability test:
- `QUARTER` (Q1) and `NINE_MONTH` (Q3) contexts without `BALANCE_SHEET` give `NOT_APPLICABLE` for
  a balance-sheet row, and with it give `APPLICABLE`;
- the same for a cash-flow row with and without `CASH_FLOW`;
- `HALF_YEAR` and `YEAR` contexts give `APPLICABLE` for both families even with an empty
  `statements_present`;
- a `STANDALONE_ONLY` entity with a `CONSOLIDATED` request gives `NOT_APPLICABLE` for every family.

`uv run pytest tests/fundamentals/test_screener_crosscheck.py` and the `verify/` suites that import
`EvidenceTier` stay green after the move.

`scoped_tier` is unit-tested in `test_canon_applicability.py` (dynamic logic): in scope with conditions proven; a condition proven
false; a condition unproven; an exclusion unproven; out-of-scope basis; no scope; a scope limited to
`QUARTER` gives a quarter key demonstrated and an H1 key of the same package unproven
(`qualification_context` takes the period kind from the key).

Test seams: `decide_applicability` over constructed `ApplicabilityContext`s; `load_dictionary`
over temporary defective copies; `scoped_tier` over constructed contexts.

Dependencies: 2 (`BasisStatus`)

Risks: Authoring every filed line item is the largest content effort in D1a. The inventory is thin
(one `in-capmkt` issuer, nine `in-bse-fin` filings), so rows outside the evidence are declared from
the SEBI format and marked in `meaning` as unevidenced. The manifest is hand-counted; a count
mismatch means one of the two is wrong, and the test must not be "fixed" by copying the loader's
output. Applicability tests are test-first, since this logic decides `NOT_APPLICABLE` vs
`NO_SOURCE`.

### Task 4: Formula, interval and period-aggregation engine

Goal: Derived values come from exact rational arithmetic. Results are stored half-even at the
pinned scale, with bounds rounded outward. Temporal roles select only role-aligned keys. Dimensional
aggregation needs every listed member. Q4 = FY − 9M (also H2 = FY − H1 and TTM) is refused with
`REVISION_INCOMPATIBLE` when an operand has a differing eligible restatement. The calculation-state
table holds row by row. The effective tier is the weakest of the formula's scoped tier and every
operand's scoped tier.

Stage: eqos-3f9.3

Files:
- Create: `config/rounding_policy/v1.yaml`, `src/fundamentals/contracts/comparison.py`, `src/fundamentals/contracts/interval.py`, `src/fundamentals/canon/interval.py`, `src/fundamentals/canon/formula.py`, `src/fundamentals/canon/period_aggregation.py`
- Test: `tests/fundamentals/test_canon_formula.py`, `tests/fundamentals/test_canon_interval.py`

Interfaces:
- Consumes: `MeasurementKey`, `PeriodInterval`, `DimensionSet`, `ValueKind`, `TemporalRole`, `ValueIdentity` (Task 3); `DictionaryRow`, `Formula`, `FormulaNode`, `FormulaOperand`, `DimensionalAggregation`, `CanonicalDictionary` (Task 3); `EvidenceTier`, `weakest` (`fundamentals.contracts.evidence_tier`, Task 3); `QualificationContext`, `ScopedTier`, `scoped_tier` (`fundamentals.contracts.qualification`, Task 3).
- Produces:
  - **`fundamentals.contracts.comparison` StrEnums:**
    - `SourceState`: `VALUE`, `NO_VALUE`, `UNAVAILABLE`, `INVALID`
    - `CalculationState`: `OPERAND_UNAVAILABLE`, `OPERAND_INVALID`, `OPERAND_MISSING`, `REVISION_INCOMPATIBLE`, `UNDEFINED`, `COMPUTED`
    - `SelectionSource`: `PACKAGE_AS_REPORTED`, `PACKAGE_OPENING_DISCLOSURE`, `INSTANT_OWN_SELECTION`, `HISTORICAL_PACKAGE` (moved here from Task 6 so traces can carry it)
  - **`fundamentals.contracts.interval`** (shared value type, so `contracts/evidence.py` never imports `canon/`); **`fundamentals.canon.interval`** re-exports `Interval` and `UndefinedDivisionError` and owns the rounding policy:
    - `Interval` (frozen: `lower: Fraction`, `upper: Fraction`).
    - Constructors: `Interval.exact(value: Fraction | Decimal)`, `Interval.from_precision(value: Decimal, decimals: int)` (± half a unit at that precision). XBRL `decimals="INF"` maps to `Interval.exact`.
    - Arithmetic: `add`, `sub`, `mul`, `div`, `shift(amount: Fraction)`. `div` raises `UndefinedDivisionError` when the denominator contains zero.
    - `intersects(other) -> bool`, `gap(other) -> Fraction`.
    - `RoundingPolicy` (frozen: `policy_id`, `content_sha256`, `scale: Mapping[ValueKind, int]`) and `load_rounding_policy(path: Path) -> RoundingPolicy`.
    - `store_value(value: Fraction, kind: ValueKind, policy) -> Decimal` (half-even) and `store_bounds(interval, kind, policy) -> tuple[Decimal, Decimal]` (lower down, upper up).
  - **`config/rounding_policy/v1.yaml`** scales (decimal places of the stored unit): `CURRENCY_AMOUNT` 2 (base-unit INR, paise), `PER_SHARE_AMOUNT` 2, `COUNT` 0, `PERCENTAGE` 2, `RATIO` 6, `DAYS` 2.
  - **`fundamentals.canon.formula`:**
    - `OperandValue` (frozen: `key: MeasurementKey`, `state: SourceState`, `exact: Fraction | None` (the exact point value), `value: Decimal | None` (its stored rounding, display only), `interval: Interval | None` (exact), `interpretation_id: int | None`, `package_id: int | None`, `calculation_trace_id: int | None`, `child_trace: CalculationTrace | None`, `alignment_proof_id: int | None`, `mapping_entry_id: str | None`, `qualification_ref: str | None`, `scoped_tier: EvidenceTier`, `selection_source: SelectionSource | None` (None only for a missing operand or a computed aggregate/average whose constituents are in a child trace — migration `0002_trace_selection_provenance.sql`), `precision_supported: bool`, `reasons: tuple[str, ...]`).
    - `resolve_operand_keys(output: MeasurementKey, operand: FormulaOperand, *, dictionary: CanonicalDictionary, reporting_currency: str) -> tuple[MeasurementKey, ...]`. `OPENING` is the instant on the day before the start, and `AVERAGE` gives the opening and closing pair.
    - `aggregate_members(aggregation: DimensionalAggregation, values: Mapping[str, OperandValue | None], *, output: MeasurementKey, policy: RoundingPolicy) -> OperandValue` and `average_operand(opening: OperandValue, closing: OperandValue, *, output: MeasurementKey, policy: RoundingPolicy) -> OperandValue`. Each returns an operand whose `child_trace` (`trace_kind` `DIMENSIONAL_AGGREGATE` or `AVERAGE`) lists **every** constituent as a `TraceOperand` — a listed member with no value appears with its state and null ids — and whose tier is the weakest constituent tier. The parent's `TraceOperand.operand_trace_id` references the stored child trace, never a single representative interpretation.
    - `calculation_state(operands: Sequence[OperandValue], *, revision_incompatible: bool, denominator_contains_zero: bool) -> CalculationState`.
    - `state_to_source_state(state: CalculationState) -> SourceState`.
    - `TraceOperand` (frozen: `name`, `key_digest`, `temporal_role`, `interpretation_id`, `operand_trace_id`, `alignment_proof_id`, `mapping_entry_id`, `qualification_ref`, `scoped_tier`, `selection_source`, `source_state`, `value`, `lower`, `upper`, `exact_value: Fraction | None`, `exact_interval: Interval | None`).
    - `CalculationTrace` (frozen: `trace_kind`, `formula_id`, `formula_version`, `formula_tier`, `formula_qualification_ref`, `rounding_policy_id`, `key_digest`, `value_identity`, `operands: tuple[TraceOperand, ...]`, `state`, `value`, `lower`, `upper`, `exact_value: Fraction | None`, `exact_interval: Interval | None`, `effective_tier`), with `content_sha256() -> str` (exact fields included as reduced `p/q`). It maps one-to-one onto `calculation_traces` plus `calculation_trace_operands`.
    - `CalculationResult` (frozen: `state`, `source_state`, `exact: Fraction | None`, `value: Decimal | None`, `interval: Interval | None` (exact), `trace: CalculationTrace`, `effective_tier: EvidenceTier`, `reasons`).
    - `evaluate_formula(row: DictionaryRow, output: MeasurementKey, operands: Mapping[str, OperandValue], policy: RoundingPolicy, *, dictionary: CanonicalDictionary, reporting_currency: str, qualification: QualificationContext, value_identity: ValueIdentity = ValueIdentity.DERIVED, revision_incompatible: bool = False) -> CalculationResult`. The formula's scoped tier is `scoped_tier(row.formula.tier, row.formula.qualification, qualification)`, recorded as `formula_tier` and `formula_qualification_ref`; `effective_tier = weakest(formula scoped tier, every operand scoped_tier)`. No formula is exempt (design decision 8).
  - **`fundamentals.canon.period_aggregation`:**
    - `PeriodDerivation` StrEnum: `Q4_FROM_FY_MINUS_9M`, `H2_FROM_FY_MINUS_H1`, `TTM_FROM_FOUR_QUARTERS`.
    - `AggregationOperand` (frozen: `operand: OperandValue`, `has_differing_restatement: bool`).
    - `NonAdditiveAggregationError`.
    - `derive_period_value(derivation: PeriodDerivation, row: DictionaryRow, output: MeasurementKey, operands: Sequence[AggregationOperand], policy: RoundingPolicy) -> CalculationResult`. It checks operand intervals, shared basis, framework, currency and dimensions, refuses non-additive kinds and instants, and returns `value_identity = DERIVED`. Interval rules: FY − 9M and FY − H1 need the subtrahend **nested** in the FY (same start, ending before the FY end) and the output to be exactly the remainder (day after the subtrahend's end to the FY end); TTM needs four **contiguous** quarters (each starting the day after the previous ends) ending at the output end. Anything else raises `PeriodAlignmentError`.

Approach: All arithmetic is `fractions.Fraction`. Conversion to `Decimal` happens only through
`store_value` and `store_bounds`, for persistence and display only: a computed operand passes its
**exact** value and interval to the parent, never its rounding (data spec l.200). Leaves are
interpretation values, stored unrounded. Replay takes a leaf's exact value from its
interpretation and a computed operand's from its child trace's `exact_*` columns; re-evaluation
must reproduce every stored field. The calculation-state table is a first-match-wins sequence over
the six spec rows, in spec order. The effective tier of a derived side is the weakest of the
formula's scoped tier and every operand tier (data spec §2, computed values), using `weakest` from
contracts. Revision compatibility is passed in as a flag per operand; Task 6 decides "differing
eligible restatement" from evidence.

Verification: `uv run pytest tests/fundamentals/test_canon_formula.py tests/fundamentals/test_canon_interval.py tests/fundamentals/test_canon_period_aggregation.py tests/fundamentals/test_canon_calculation_state.py tests/fundamentals/test_pg_trace_selection_provenance.py`
passes (as built; the original two files were split during review). It covers:
- interval add, sub, mul, div and shift with outward rounding;
- div by an interval containing zero → `UNDEFINED`;
- half-even storage (e.g. a value exactly at the half step) at each v1 scale;
- **exact intermediates:** a formula dividing by `average_operand` of 0 INR and 0.01 INR uses the
  exact 0.005 (computes, `COMPUTED`), never the stored 0.00 (which would be `UNDEFINED`), and the
  child trace stores `exact_value` `1/200`;
- period-derivation interval refusals: a 9M operand not starting at the FY start, and three
  quarters with a gap, raise `PeriodAlignmentError`;
- an exact count's interval and an `INF` precision value's interval are singletons;
- `CLOSING`, `OPENING` (the Apar H1 FY26 output 2025-04-01..2025-09-30 resolves opening cash to
  instant 2025-03-31) and `AVERAGE` key resolution;
- a receivable-days formula evaluates with actual days, and an operand at a non-role-aligned date
  is never selected;
- dimensional aggregation with a missing member → `OPERAND_MISSING`, with the child trace listing
  every member including the missing one; `average_operand`'s child trace lists both instants; a
  member-of-member list is refused at load (Task 3);
- Q4 = FY − 9M computes `DERIVED` with a trace, and with a flagged restated 9M →
  `REVISION_INCOMPATIBLE`;
- EPS through `derive_period_value` → `NonAdditiveAggregationError`;
- one parametrized case per calculation-state row, including `OPERAND_INVALID` for an operand
  carrying a number with `precision_supported=False`;
- effective tier: a demonstrated, in-scope formula with one `EQUIVALENCE_UNPROVEN` operand is
  unproven; an `EQUIVALENCE_UNPROVEN` formula over all-demonstrated operands is unproven; a
  demonstrated formula evaluated **out of its recorded scope** (a context with another basis or
  schema, or an unproven condition) over demonstrated operands is unproven with no
  `formula_qualification_ref`.

Test seams: `evaluate_formula`, `calculation_state`, `derive_period_value`, `Interval` operations,
`store_value` and `store_bounds`.

Dependencies: 3

Risks: Test-first. This is the arithmetic that every computed financial figure goes through. Unit
tests use constructed operands, since these are pure functions. Do not reuse
`laneb_triage.relative_difference` here; it is triage, not storage.

### Task 5: First-party intake, mappings, adapters, occurrences, interpretations and ingest

Goal: `fundamentals evidence ingest` over Apar Q2 FY26 stages the retained XBRL and results PDF
as captures, records one package with both members (each with its own knowledge time), stores a
lossless capture-owned occurrence per used or numeric XBRL fact and per banded consolidated PDF
cell, one scoped interpretation per occurrence plus constructions, and structural presence and
reporting kind. Nothing is zero-filled; `profit_before_tax` 340.56 and
`profit_before_tax_incl_associates` 340.53 crore exist; unknown schemas are `UNSUPPORTED_SCHEMA`;
re-ingest writes nothing; the one-member FY25 Q2 package ingests.

Stage: eqos-3f9.4

Files:
- Create: `src/fundamentals/contracts/evidence.py`, `src/fundamentals/store/capture_local.py`, `src/fundamentals/evidence/__init__.py`, `src/fundamentals/evidence/capture_intake.py`, `src/fundamentals/evidence/member_identity.py`, `src/fundamentals/evidence/mapping.py`, `src/fundamentals/evidence/xbrl_adapter.py`, `src/fundamentals/evidence/pdf_adapter.py`, `src/fundamentals/evidence/interpret.py`, `src/fundamentals/evidence/presence.py`, `src/fundamentals/evidence/repository.py`, `src/fundamentals/evidence/first_party_ingest.py`, `src/fundamentals/api/evidence_cli.py`, `config/normalisation_policy/v1.yaml`, `config/mappings/v1.yaml`, `config/mappings/xbrl/v1/in_capmkt.yaml`, `config/mappings/xbrl/v1/in_bse_fin.yaml`, `config/mappings/pdf/v1/results_layout.yaml`, `config/mappings/constructions/v1.yaml`, `config/mappings/statement_anchors/v1.yaml`, `tests/fundamentals/retained_support.py`
- Modify: `src/fundamentals/contracts/acquisition_outcome.py`, `src/fundamentals/extract/xbrl_parser.py`, `src/fundamentals/api/source_intake.py`, `src/fundamentals/api/cli_parser.py`, `src/fundamentals/api/cli.py`
- Test: `tests/fundamentals/test_evidence_first_party.py`

Interfaces:
- Consumes: Tasks 1–2 (`open_pool`, `pg_db`, the table and column names, `seed_issuer_identity`, `BasisStatus`). Task 3 (`EvidenceTier`, `weakest`, `load_dictionary`, `CanonicalDictionary`, `MeasurementKey`, `PeriodInterval`, `DimensionSet`, `Basis`, `StatementFamily`, `PeriodKind`, `Representation`, `FormulaNode`, `QualificationScope`, `QualificationCondition`, `ProvenCondition`, `QualificationContext`, `ScopedTier`, `scoped_tier`, `VersionContentDriftError`). Task 4 (`Interval` from `fundamentals.contracts.interval`, `SourceState`). Task 11 (`locate_statement_pages`, `extract_statement_rows`, `StatementPageSpec`, `StatementLocation`, `PdfStatementRow`, `PdfCell`, `StatementPageNotFoundError`). Existing code: `stage_local_source`, `ApprovedIntakeContext` (`fundamentals.api.source_intake`); `SnapshotStore`, `DirectoryAnchor`; `CaptureRecord`, `BodyCompleteness` (`fundamentals.contracts.snapshot`); `OutcomeCode`; `FundamentalsConfig`, `load_config` (`fundamentals.api.config`); the taxonomy specs in `fundamentals.extract.xbrl_taxonomies`; `SourceCatalog`, `BUILTIN_SOURCES`, `SourceClass`, `UnknownSourceError` (`fundamentals.contracts.source_catalog`); `NSE_ENTITY_SCHEME`, `SEBI_SCRIP_ENTITY_SCHEME`, `BSE_SCRIP_ENTITY_SCHEME` (`fundamentals.ingest.xbrl_identity`).
- Produces:
  - **`fundamentals.store.capture_local.capture_local_original(store: SnapshotStore, *, input_anchor: DirectoryAnchor, source_id: str, surface: str, request_key: str, expected_sha256: str, media_type: str, rights: SnapshotRights, path: Path) -> CaptureRecord`**: the read, pin check, `CaptureRecord.make` and `store.put_capture` core, called by `stage_local_source` and re-exported from `fundamentals.api.source_intake`.
  - **`fundamentals.evidence.capture_intake`** (design decision 12): `RetainedCaptureBinding`, `RetainedIntake`, `retained_intake_from_manifest`, `FirstPartySurface` StrEnum (`NSE_XBRL_INSTANCE`, `NSE_RESULTS_PDF`), `authorise(binding: RetainedCaptureBinding, *, catalog: SourceCatalog) -> FirstPartySurface | None` (the decision-12 table; `None` = not authorised), `stage_retained_member(store: SnapshotStore, intake: RetainedIntake, representation: Representation) -> CaptureReference`, and `parse_filed_at(raw: str) -> datetime` (design decision 5; raises `FiledAtFormatError` on any other shape).
  - **`fundamentals.evidence.member_identity`** (data spec l.384 `IDENTITY_REJECTED`; bounded to the seeded issuer, no discovery): `IssuerIdentifiers` (frozen: `entity_id`, `isin`, `nse_symbol`, `bse_scrip`, `evidence_input_id`), `IdentityVerdict` (frozen: `verified: bool`, `reason: str | None`, `evidence: tuple[str, ...]`), `verify_xbrl_identity(instance: RawXbrlInstance, identifiers: IssuerIdentifiers) -> IdentityVerdict`, `verify_pdf_identity(pdf: LoadedPdf, identifiers: IssuerIdentifiers) -> IdentityVerdict`, constant `PDF_SYMBOL_MARKER = "Scrip Symbol :"`.
  - **`fundamentals.contracts.acquisition_outcome`:**
    - `ExtractionOutcome` StrEnum: `COMPLETE`, `NOT_PUBLISHED`, `PARTIAL`, `FAILED`, `NOT_AUTHORISED`, `IDENTITY_REJECTED`, `UNSUPPORTED_SCHEMA`, `PARSE_FAILED`.
    - `extraction_outcome_for(record: CaptureRecord, *, parse_failed: bool, unsupported_schema: bool, identity_rejected: bool) -> ExtractionOutcome`.
    - `outcome_source_state(outcome: ExtractionOutcome) -> SourceState | None`. `COMPLETE` → `None` (per-cell state decides); `NOT_PUBLISHED` → `NO_VALUE`; every other outcome → `UNAVAILABLE` (never `NO_VALUE`).
  - **`fundamentals.contracts.evidence` StrEnums:**

    | Enum | Values |
    |---|---|
    | `MissingValueState` | `VALUE`, `ZERO_PRINTED`, `NIL`, `DASH`, `BLANK`, `NOT_PRESENTED`, `SOURCE_NULL` (the spec's set, unchanged) |
    | `PrecisionKind` | `EXACT` (XBRL `INF`, exact counts), `FINITE` (declared decimals), `UNSUPPORTED` (no usable precision) |
    | `RevisionCause` | `ORIGINAL`, `ISSUER_RESTATEMENT`, `ISSUER_CORRECTION`, `COMPARATIVE_RESTATEMENT`, `VENDOR_UPDATE`, `PARSER_REEXTRACTION`, `MANUAL_CORRECTION`, `NORMALISATION_POLICY_CHANGE` |
    | `KnowledgeTimeStatus` | `KNOWN`, `UNKNOWN` |
    | `FilingFamily` | `FINANCIAL_RESULTS`, `SHAREHOLDING` |
    | `InterpretationStatus` | `MAPPED`, `UNMAPPED`, `PERIOD_AMBIGUOUS`, `INVALID` |
    | `InterpretationOrigin` | `DIRECT`, `CONSTRUCTED` |
    | `InterpretationReason` | `UNREADABLE_CELL`, `PRECISION_UNSUPPORTED`, `UNIT_MISMATCH` |
    | `StatementRole` | `PRESENT`, `REPLACED` |
    | `AttemptStage` | `ACQUISITION` (authority, staging, pin check; no extractor), `EXTRACTION` (one adapter invocation under one extractor version) |

    An unreadable PDF cell stays inside the spec's vocabulary: the occurrence keeps its raw text
    (`missing_state` `VALUE`: something was printed), and its interpretation is `INVALID` with
    `UNREADABLE_CELL`. `ORIGINAL` follows design decision 10.
  - **`fundamentals.contracts.evidence` frozen models:**
    - `EligibilityBoundary`: `knowledge_cutoff: datetime`, `first_seen_cutoff: datetime`, with `at(cutoff)` (both clocks at one cutoff, used by runs) and `for_ingest(package_knowledge_time, registered_at)` (design decision 5).
    - `CaptureReference`: `capture_ref_id: int | None`, `source_id`, `surface`, `request_key`, `capture_id`, `blob_sha256`, `record_sha256`, `registered_at`, `first_seen_at`.
    - `PackageMember`: `representation`, `capture: CaptureReference`, `knowledge_time: datetime`, `knowledge_time_raw: str`, `knowledge_time_status`.
    - `FilingPackage`: `package_id: int | None`, `entity_id`, `family`, `reporting_period_end: date`, `basis`, `framework`, `reporting_kind: PeriodKind`, `knowledge_time: datetime` (latest member), `supersedes_package_id: int | None`, `replaced_statements: frozenset[StatementFamily]` (empty = whole package), `statements_present: frozenset[StatementFamily]`, `members: Mapping[Representation, PackageMember]` (one or two), `evidence_sha256`. Method `eligible(boundary: EligibilityBoundary) -> bool` (design decision 5).
    - `Occurrence`: `occurrence_id: int | None`, `capture: CaptureReference` (the owner; no package field, Task 2 capture ownership), `representation`, `extractor_version`, `native_field`, `raw_value_text: str | None`, `raw_unit`, `raw_scale: int`, `raw_sign: int`, `precision_kind: PrecisionKind`, `declared_precision: int | None` (set iff `FINITE`), `native_context: Mapping[str, object]`, `period: PeriodInterval | None`, `missing_state`, `anchor: Mapping[str, object]`, `anchor_key: str`, `knowledge_time: datetime | None`, `knowledge_time_status`, `first_seen_at`, `revision_cause`.
    - `Interpretation`: `interpretation_id: int | None`, `origin`, `occurrence_id: int | None`, `capture_ref_id: int`, `representation`, `construction_rule_id: str | None`, `operand_interpretation_ids: tuple[int, ...]`, `status`, `key: MeasurementKey | None`, `value: Decimal | None`, `interval: Interval | None`, `tier: EvidenceTier` (the scoped tier), `mapping_set_version`, `mapping_entry_id: str | None`, `qualification_ref: str | None`, `condition_evidence: tuple[ProvenCondition, ...]`, `normalisation_policy_version`, `extractor_version`, `transform_trace: Mapping[str, object]`, `reason: InterpretationReason | None`, `revision_cause`, `supersedes_interpretation_id: int | None`, `recorded_at: datetime`.
    - `AcquisitionAttempt`: `attempt_id: int | None`, `stage: AttemptStage`, `source_id`, `surface`, `entity_id`, `period_end: date`, `basis: Basis`, `framework: AccountingFramework`, `representation`, `statement_family: StatementFamily | None`, `package_id: int | None`, `outcome: ExtractionOutcome`, `reason: str | None`, `capture: CaptureReference | None`, `input_sha256`, `extractor_version`, `attempted_at`.
  - **`fundamentals.extract.xbrl_parser.iter_raw_facts(xml_bytes: bytes, *, taxonomies: tuple[TaxonomySpec, ...] = DEFAULT_TAXONOMIES) -> RawXbrlInstance`.**
    `RawXbrlInstance` (frozen): `taxonomy: TaxonomySpec`, `schema_identity: str` (namespace URI), `scope: Scope`, `facts: tuple[RawXbrlFact, ...]`. `RawXbrlFact` (frozen): `fact_id: str | None`, `concept_qname`, `context_ref`, `raw_text: str | None`, `is_nil: bool`, `is_numeric: bool`, `decimals_raw: str | None`, `unit_measure: str | None`, `entity_scheme`, `entity_id`, `raw_period` (start/end/instant as written), `period` (after the declared-period repair), `period_declaration: tuple[str, str] | None` (context ref and concepts of the `DateOfStartOfReportingPeriod`/`DateOfEndOfReportingPeriod` facts that repaired it), `dimensions`, `document_order: int`. The repair is the existing `_apply_declared_periods(_parse_contexts(root), _declared_reporting_periods(root, spec))` (`xbrl_parser.py:430–431`), reused, never re-implemented; the occurrence keeps the raw period and the declaration evidence in `native_context`.
  - **`fundamentals.evidence.mapping`:**
    - `MappingEntry` (frozen: `entry_id`, `source`, `surface`, `schema_identity` (namespace URI plus version), `selector` (native field plus context predicate: period shape, dimension members, PDF statement family, row label variants and column-header pattern), `canonical_id`, `dimension_members: Mapping[str, str]`, `sign: int`, `unit_transform`, `precision_rule`, `period_rule: PdfPeriodRule | None` (PDF only), `tier: EvidenceTier`, `qualification: QualificationScope | None`, `basis: frozenset[Basis]`, `period_kinds: frozenset[PeriodKind]`, `evidence_ref: str`).
    - `PdfPeriodRule` StrEnum (row-aware PDF period, R5): `COLUMN_DURATION` (the header's duration), `COLUMN_OPENING_INSTANT` (the day before the header duration's start), `COLUMN_CLOSING_INSTANT` (the header duration's end), `COLUMN_INSTANT` (an instant header as printed).
    - `ConstructionOperand` (frozen: `name`, `mapping_entry_id`, `dash_rule_id: str | None`): `dash_rule_id` names a normalisation-policy dash rule allowing a printed `DASH` operand to contribute zero to this construction only (data spec §1 Missing-value states: "unless an evidenced source rule reads it as zero"). The dash occurrence's own interpretation stays no value.
    - `ConstructionRule` (frozen: `rule_id`, `source`, `surface`, `schema_identity`, `canonical_id`, `operands: tuple[ConstructionOperand, ...]`, `expression: FormulaNode`, `tier: EvidenceTier`, `qualification: QualificationScope | None`, `evidence_ref`).
    - `StatementAnchor` (frozen: `schema_identity`, `statement_family`, `native_fields: frozenset[str]`, `period_shape` (`INSTANT_AT_PERIOD_END` or `DURATION_ENDING_AT_PERIOD_END`)).
    - `MappingSet` (frozen: `version`, `content_sha256`, `normalisation_policy_version`, `entries`, `constructions`, `statement_anchors`, `supported_schemas: frozenset[str]`), with `match(occurrence: Occurrence) -> MappingEntry | None`.
    - `load_mapping_set(root: Path, version: str, *, dictionary: CanonicalDictionary) -> MappingSet`.
    - `NormalisationPolicy` (frozen: `version`, `content_sha256`, `dash_rules: Mapping[str, DashRule]`), `DashRule` (frozen: `rule_id`, `construction_rule_id`, `operand_name`, `evidence_ref`), `load_normalisation_policy(path: Path) -> NormalisationPolicy`.
    - `MappingLoadError` (defects: `DANGLING_CANONICAL_ID`, `DANGLING_ENTRY_ID`, `DUPLICATE_SELECTOR`, `SCHEMA`), per design decision 9.
    - `UnsupportedSchemaError`.
  - **`fundamentals.evidence.presence`:**
    - `statements_present(occurrences: Sequence[Occurrence], *, period_end: date, anchors: Sequence[StatementAnchor], pdf_locations: Mapping[StatementFamily, StatementLocation | None]) -> Mapping[StatementFamily, tuple[Occurrence, ...]]`: a family is present when any occurrence's native field is one of its anchors with the anchor's period shape at the period end (nil and unmapped count; mapping success and values are never consulted), or the PDF locator found that family's block. The returned occurrences become `package_statement_evidence`.
    - `reporting_kind(occurrences: Sequence[Occurrence], *, period_end: date, fiscal_year_end_month: int) -> PeriodKind`: the kind of the longest duration ending at the period end (`QUARTER`, `HALF_YEAR`, `NINE_MONTH`, `YEAR`); with no duration, the fiscal position of the period end.
  - **Adapters:**
    - `fundamentals.evidence.xbrl_adapter.read_xbrl_occurrences(body: bytes, *, capture: CaptureReference, member: PackageMember, mapping_set: MappingSet) -> tuple[Occurrence, ...]`, constant `XBRL_EXTRACTOR_VERSION`. Raises `UnsupportedSchemaError` when the instance's namespace is not in `supported_schemas`.
    - `fundamentals.evidence.pdf_adapter.read_pdf_occurrences(pdf: LoadedPdf, *, capture: CaptureReference, member: PackageMember, basis: Basis, specs: Mapping[StatementFamily, StatementPageSpec]) -> PdfReadResult`, constant `PDF_EXTRACTOR_VERSION`. `PdfReadResult` (frozen: `occurrences`, `locations: Mapping[StatementFamily, StatementLocation | None]`, `family_failures: Mapping[StatementFamily, str]`).
  - **`fundamentals.evidence.interpret`:**
    - `interpret(occurrence: Occurrence, *, entity_id: int, basis: Basis, mapping_set: MappingSet, dictionary: CanonicalDictionary, fiscal_year_end_month: int, qualification: QualificationContext, recorded_at: datetime) -> Interpretation`: key, value and interval never depend on `qualification`; the tier, `qualification_ref` and `condition_evidence` are `scoped_tier(entry.tier, entry.qualification, qualification)`.
    - `construct(rule: ConstructionRule, operands: Mapping[str, Interpretation], *, dash_rules: NormalisationPolicy, qualification: QualificationContext, recorded_at: datetime) -> Interpretation`: `origin=CONSTRUCTED`, value and interval by exact interval arithmetic over the operand interpretations; `scoped_tier(rule.tier, rule.qualification, qualification)` gives the rule's tier and `qualification_ref`, and `tier = weakest(rule scoped tier, every operand's stored tier)`; `operand_interpretation_ids` set; `input_digest` = SHA-256 of the ordered operand ids. A `DASH` operand with an evidenced `dash_rule_id` contributes exact zero (rule id in the trace); any other operand without a value — `NOT_PRESENTED` (line absent), `BLANK`, `NIL`, an unruled `DASH` — gives no value with the reason in the trace; an `INVALID` operand gives `INVALID`.
    - `prove_conditions(conditions: Sequence[QualificationCondition], *, interpretations: Sequence[Interpretation], period: PeriodInterval, basis: Basis) -> Mapping[str, ProvenCondition]`: a condition is proven only by a same-capture `MAPPED` interpretation of its canonical id for **that period and basis**. Interval exactly {0}: `EQUALS_ZERO` holds, `NOT_EQUALS_ZERO` fails; interval excluding 0: `EQUALS_ZERO` fails, `NOT_EQUALS_ZERO` holds; an interval containing 0 and nonzero values, no such interpretation, or one with no value leaves the condition unproven and absent from the map. Evidence ids are the interpretations' (reserved) ids, never fabricated.
  - **`fundamentals.evidence.repository.EvidenceRepository(pool: ConnectionPool)`.** Every write is idempotent and returns stored ids:
    - writes: `put_evidence_input`, `put_capture_ref`, `put_package` (with members and statements in one transaction), `put_occurrences`, `put_interpretations` (with operands and condition evidence), `put_attempt`, `put_segment_members` (with evidence), `put_settings_record`;
    - current reads (ingest and fresh runs only): `list_packages(entity_id, family, period_end)`, `list_package_lineage(package_id)`, `list_capture_occurrences(capture_ref_id)`, `list_interpretations(occurrence_ids)`, `list_capture_interpretations(capture_ref_id)`, `list_attempts(entity_id, period_end)`, `issuer_identifiers(entity_id) -> IssuerIdentifiers` (seeded securities and listings), `reserve_interpretation_ids(n) -> tuple[int, ...]`, and the as-of reads of Task 2;
    - immutable by-id reads (replay uses only these, Task 9): `get_capture_refs(ids)`, `get_packages(ids)` (members and statements included), `get_package_statements(ids)` (with evidence occurrence ids), `get_occurrences(ids)`, `get_interpretations(ids)` (operands and condition evidence included), `get_attempts(ids)`, and Task 2's by-id identity reads. Tasks 7–9 add the proof, trace and definition-set reads by id.
  - **`fundamentals.evidence.first_party_ingest`:**
    - `ingest_first_party(*, intake: RetainedIntake, catalog: SourceCatalog, snapshot_store: SnapshotStore, repository: EvidenceRepository, dictionary: CanonicalDictionary, mapping_set: MappingSet, entity_id: int, basis: Basis, family: FilingFamily, reporting_period_end: date, pdf_specs: Mapping[StatementFamily, StatementPageSpec] | None, supersedes_package_id: int | None = None, replaced_statements: frozenset[StatementFamily] = frozenset(), extractor_versions: Mapping[Representation, str] | None = None) -> IngestReport`. `extractor_versions` is a test seam (default: the adapters' constants).
    - `IngestReport` (frozen: `package_id`, `occurrence_count`, `interpretation_counts: Mapping[InterpretationStatus, int]`, `attempts: tuple[AcquisitionAttempt, ...]`).
  - **CLI:** `fundamentals evidence ingest --retrieval-manifest <json> --issuer <symbol> --quarter <FYyy_Qn> --period-end <YYYY-MM-DD> --basis consolidated --raw-root <dir> --snapshot-root <dir> [--member xbrl=<kind>] [--member pdf=<kind>] [--issuer-config <yaml>] [--config-root config]`. The composition root builds `PgSettings`, the runtime pool, `RetainedIntake` and the `SourceCatalog` (design decision 12); `--issuer-config` supplies the PDF `pdf_parse` block (printed unit, label overrides) and is required when a PDF member is named.
  - **`tests/fundamentals/retained_support.py`:** `apar_original(quarter: str, kind: str) -> Path` (fails on a missing file or hash mismatch); `marked_copy(source: Path, *, edit: MarkedEdit, tmp_path: Path) -> Path` (`MarkedEdit` names the element/context or page/row and the replacement); `apar_intake(tmp_path, quarter, members) -> RetainedIntake`; `seed_apar(pg_db) -> int` (runs `seed_issuer_identity` over `config/identity/aparinds.yaml` and returns the entity id).

Approach:
- **Intake.** `retained_intake_from_manifest` reads the manifest, selects entries for issuer,
  quarter and kinds, and binds expected SHA-256s and raw filed-at strings. Each binding passes
  `authorise` first (design decision 12); an unauthorised one records a `NOT_AUTHORISED`
  `ACQUISITION` attempt and is never staged or interpreted. Staging calls
  `capture_local_original`. A binding whose file is missing or fails its pin records a `FAILED`
  `ACQUISITION` attempt with no capture (and no package if no member stages), then the ingest
  fails loudly.
- **Reuse levels (data spec l.346: re-mapping adds, never rewrites).** Per capture: (1) the
  registration is always reused (same source id and SHA-256; first first-seen kept; a revised
  package links an unchanged member); (2) occurrences and extraction attempts are reused only if a
  generation exists under the **current extractor version**, else the adapter runs; (3)
  interpretations are reused only if the capture has rows under the current (mapping set,
  normalisation policy, extractor) triple, else every occurrence of that generation is
  interpreted and appended (`recorded_at` = store clock, cause per design decision 10). Older rows
  are never touched, so new pins get new values and older runs still replay.
- **XBRL.** The adapter emits one occurrence per numeric fact, nil facts included as `NIL` with
  `raw_value_text` None, plus every text fact whose concept a mapping entry or statement anchor
  names (e.g. `DescriptionOfReportableSegment`, `NatureOfReportStandaloneConsolidated`) as raw text
  with no value. Precision comes from `decimals` (`INF` → `EXACT`, an integer → `FINITE`, absent
  or unparseable → `UNSUPPORTED`). The raw scale is 0 (XBRL values are already base-unit INR). The
  anchor is the fact id, or the context ref plus document order. `iter_raw_facts` reuses the
  parser's private context, unit, taxonomy and scope helpers, including the declared-period
  repair, and does not change `parse_instance`. The occurrence's knowledge time is its member's.
- **PDF.** Ingest loads the staged PDF with `load_pdf` against the binding's SHA-256 (the same
  bytes as the capture). The adapter calls Task 11's locator per family for the package basis with
  the issuer config's `pdf_parse` block, then emits one occurrence per banded row × column of
  each located block — only the columns under the requested basis's super-header (Task 11); the
  super-header text and column extents go into the anchor as scope evidence. Unit and scale come
  from the row's resolved unit context (Task 11), never one page-wide value: currency rows under
  "Rs. in crores" get raw scale 7; EPS rows under "Earnings per share (EPS) (Rs.)" are
  rupees per share with raw scale 0 (62.66 stays 62.66, never × 10^7). A row with no evidenced
  unit context is emitted with `raw_unit` empty and interprets `INVALID` (`UNIT_MISMATCH`).
  Precision is `FINITE` at the printed decimals. Numeric grammar (fail closed): optional
  parentheses, digit grouping whose last group before the `.` has three digits. Anything else —
  "78,09" (H1 D&A, p.3), "(0,70)" — keeps its raw text and interprets `INVALID`
  (`UNREADABLE_CELL`); commas are never stripped freely. Only recognised markers get a
  missing state: a lone dash
  glyph ("–", "—" or ASCII "-", as printed in the retained tax cells) `DASH`, an empty cell `BLANK`, a printed zero `ZERO_PRINTED`. Any other printed text is `VALUE`
  with the raw text kept; text that does not parse as a number interprets `INVALID` with
  `UNREADABLE_CELL`. The occurrence's `period` is the column header's interval (through the
  header-text helpers) and `native_context` keeps the header text.
- **PDF periods (row-aware).** The key period comes from the column header plus the matched
  entry's `period_rule`, never the header alone. Cash-flow columns are half-year durations, but
  "Cash and cash equivalents at the beginning of the year" maps with `COLUMN_OPENING_INSTANT` and
  "… at the end of the year" with `COLUMN_CLOSING_INSTANT`; segment revenue and results map with
  `COLUMN_DURATION`, and segment assets and liabilities in the same columns with
  `COLUMN_CLOSING_INSTANT`. Opening instants are the day before the header duration's start, and
  the header's duration must agree with the evidenced fiscal-year-end setting (a half year ending
  September for month 3). An undeterminable header, a rule that does not fit the header shape, or
  an entry with no `period_rule` gives `PERIOD_AMBIGUOUS`.
- **PDF failures (fail only what failed).** Per family: a block that cannot be located while the
  package's structural presence (from the XBRL anchors) says the family is present, or a located
  block where no banded numeric row parses, is a `PARSE_FAILED` attempt for (PDF, that family),
  and that family's PDF side is `UNAVAILABLE` at run time. A family absent from every member is
  no failure: applicability decides. An unreadable cell is never a parse failure: its occurrence
  keeps the raw text and its interpretation is `INVALID` (`UNREADABLE_CELL`), so only that cell's
  PDF side is `INVALID` and its extraction `NOT_COMPARABLE`.
- **Mappings.** `profit_before_tax` maps to XBRL `ProfitBeforeTax` (3,405,600,000 in context
  `OneD`), whose position before the associates share is recorded as evidence in the mapping.
  `profit_before_tax_incl_associates` is never assigned by the label "Profit before tax"; it comes
  from a construction (below) in XBRL and from the evidenced layout line in the PDF. `eps_basic`
  maps to `BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations` and
  `eps_basic_continuing` to `BasicEarningsLossPerShareFromContinuingOperations` (both 62.66,
  `decimals="INF"` in Q2 FY26), per the inventory; the PDF prints one "Basic" line, which maps to
  `eps_basic` with the evidence that discontinued EPS is 0 in that filing. The mapping entry, not
  the alignment rule, names the element. Segment entries map `SegmentRevenue` etc. to the
  evidenced canonical member resolved from that context's `DescriptionOfReportableSegment` text,
  never the context ordinal (ordinals differ: `Others` is member 02 in FY25 and 04 in FY26).
  Elimination evidence: XBRL `InterSegmentRevenue`; PDF "Less: Inter-segment revenue" and
  "Less:- Inter-segment assets" lines. Every entry carries its tier; first-party entries are
  `EQUIVALENCE_UNPROVEN` unless qualification evidence exists. The PDF "Basic" → `eps_basic`
  entry's scope carries the typed condition `profit_discontinued_after_tax` `EQUALS_ZERO`; the PDF
  capture prints no discontinued line, so the condition is unproven and the entry is never treated
  as demonstrated on that basis. Extraction
  `AGREE` for Apar comes from Task 7's alignment proofs, not from inflated tiers.
- **Constructions.** v1 declares two:
  - XBRL `profit_before_tax_incl_associates` = `ProfitBeforeTax` +
    `ShareOfProfitLossOfAssociatesAndJointVenturesAccountedForUsingEquityMethod` (3,405,600,000 +
    (−300,000) = 3,405,300,000 in Q2 FY26).
  - PDF `tax_expense` = (a) current tax + (b) deferred tax + (c) current tax in respect of earlier
    years — every filed component (inventory §2, `tax_expense`). Operand (c) carries the v1 dash
    rule `apar-pdf-tax-earlier-years-dash`, evidenced by the Q2 FY26 quarter column: (a) 89.13 +
    (b) (0.30) with (c) printed "-" equals XBRL `TaxExpense` 88.83 crore. Q2 FY26 quarter: 88.83
    crore; Q2 FY25 comparative column: 63.45 + (1.28) + 0.68 = 62.85 crore (equal to the FY25 Q2
    `in-bse-fin` `TaxExpense` 628,500,000 in context `OneD`). An absent (c) line is `NOT_PRESENTED`
    and the construction has no value.

  A constructed interpretation is a reported value assembled from the source's own lines
  (`origin=CONSTRUCTED`, value identity `REPORTED`); a dictionary formula's output is `DERIVED`.
  Constructions are scoped to one capture and representation; they qualify through their own
  rule's scope, never a mapping entry's.
- **Identity (before interpretation; data spec l.384).** Checked against
  `issuer_identifiers(entity_id)`. XBRL: every context entity resolves (`NSE_ENTITY_SCHEME` → NSE
  symbol; `SEBI_SCRIP_ENTITY_SCHEME`/`BSE_SCRIP_ENTITY_SCHEME` → BSE scrip; the retained instances
  use all three), every `ISIN`, `ScripCode` or `Symbol` fact present equals the seeded value, and
  `NatureOfReportStandaloneConsolidated` equals the package basis. PDF: page 1's
  `PDF_SYMBOL_MARKER` line names the seeded NSE symbol (verified on the retained Q2–Q4 FY26
  PDFs). An unknown scheme, a conflict or an absent marker → `IDENTITY_REJECTED` overall
  `EXTRACTION` attempt; nothing from that member is written. Basis *status* is never read from
  the document (Task 3).
- **Interpretation.** Normalises each occurrence from its own raw scale to exact base-unit INR
  (`value × 10^raw_scale`), applies the declared sign, and builds the interval with
  `Interval.from_precision` at the normalised scale (`FINITE`), `Interval.exact` (`EXACT`), or
  `INVALID` with `PRECISION_UNSUPPORTED` (`UNSUPPORTED` with a number). An unmatched
  occurrence becomes `UNMAPPED` with `key=None`. Each newly written interpretation takes its cause
  from the precedence rule in design decision 10 (reprocessing, then comparative, then
  `ORIGINAL`); Task 6 supplies the comparative check.
- **Qualification at ingest (two passes, per measurement).** Values never depend on tiers. In
  one transaction: reserve ids for new interpretation identities (`reserve_interpretation_ids`);
  first pass with an empty `proven` map; `prove_conditions` per distinct (period, basis) of the
  mapped first-pass rows; second pass, each with `qualification_context(its own key, …, the
  proofs for its period and basis)`; insert the second pass under the reserved ids, then the
  condition-evidence rows; commit. Nothing is visible before commit; an insert conflict rolls back
  and retries from a fresh read (at most three times). The package reporting kind never enters
  qualification.
- **Ingest.**
  - Package members and their knowledge times follow design decision 5; the package's knowledge
    time is the latest member's.
  - `statements_present` and `reporting_kind` come from `presence.py`; the presence evidence is
    stored in `package_statement_evidence`. A correction's `replaced_statements` are stored as
    `REPLACED` rows.
  - Each attempt carries its full request identity (stage, source id, surface, entity, period
    end, basis, framework, representation) and is recorded per (representation, statement family) with its `ExtractionOutcome`
    and the hash of the bytes it tried. Every adapter invocation for a member writes exactly one
    overall `EXTRACTION` attempt (`statement_family` NULL: `COMPLETE` when the member was read, else
    its failure) plus any family attempts, all in one transaction and therefore sharing one
    `attempted_at`; that set is the invocation's **attempt generation**, owned by one extractor
    version. Re-ingesting the same bytes with the same extractor reuses it (reuse level 2) and
    writes nothing, so the original generation stands. `package_id` follows Task 2's capture-ownership rule.
  - Segment members are recorded per (entity, axis, canonical member) with the
    `DescriptionOfReportableSegment` occurrence ids as `segment_member_evidence`.

Verification: `uv run pytest tests/fundamentals/test_evidence_first_party.py` (marked `pg` and
`retained`, except the mapping refusals) shows, for Apar Q2 FY26 staged from the retained originals:
- interpretations of `profit_before_tax` = 3,405,600,000 INR (340.56 crore) and the constructed
  `profit_before_tax_incl_associates` = 3,405,300,000 INR (340.53 crore) for
  2025-07-01..2025-09-30, consolidated, the latter listing both operand interpretation ids;
- `eps_basic` = 62.66 with a singleton interval;
- **PDF basis and unit isolation:** every PDF occurrence from pages 3, 6 and 7 lies under the
  "Consolidated" super-header; no standalone cell (e.g. standalone current tax 88.15, standalone
  basic EPS 63.20) is emitted for the consolidated package. PDF current tax 89.13 normalises to
  891,300,000 INR and PDF basic EPS 62.66 stays 62.66 INR per share;
- **PDF row-aware periods:** CF opening cash interprets at instant 2025-03-31 (686.42 crore), CF
  closing cash at 2025-09-30 (309.39 crore), both from half-year columns; segment assets are
  instants at 2025-09-30, distinct keys from segment revenue's durations in the same columns;
  a marked header that cannot be resolved gives `PERIOD_AMBIGUOUS`;
- **tax construction:** PDF `tax_expense` = 888,300,000 INR for Q2 FY26 (dash rule applied and
  traced; the dash occurrence's own interpretation has no value) and 628,500,000 INR for the Q2 FY25
  comparative column (nonzero earlier-years 0.68 included); a marked copy with the (c) line
  removed gives a constructed interpretation with no value;
- **declared-period repair:** in FY25 Q2 (`in-bse-fin`), where `OneD` and `FourD` carry
  identical raw dates, `OneD` facts get 2024-07-01..2024-09-30 and `FourD` facts
  2024-04-01..2024-09-30, each occurrence keeping its raw period and declaration evidence;
- package members carry knowledge times `2025-10-29T08:03:43Z` (PDF) and `2025-10-29T15:28:58Z`
  (XBRL) with raw strings kept; the package knowledge time is the XBRL one; `parse_filed_at` maps
  `2024-10-30T10:47:06+00:00` to that UTC instant unchanged and refuses `2025/10/29`;
- `statements_present` for Q2 FY26 contains `BALANCE_SHEET` and `CASH_FLOW` with evidence
  occurrences (`Assets`, `EquityAndLiabilities` at 2025-09-30), `reporting_kind` is `HALF_YEAR`;
  for Q3 FY26 (no `Assets`/`EquityAndLiabilities`/cash-flow facts in its instance) neither family is
  present and `reporting_kind` is `NINE_MONTH`;
- every `NIL`, `DASH` and `BLANK` occurrence has a null interpretation value, never 0; `NIL` is
  shown with a marked copy of the Q2 FY26 XBRL with one fact set `xsi:nil="true"` (the retained
  Apar files contain no nil facts);
- an unreadable consolidated cell (the first one the retained PDF yields; if none, a marked copy
  with one cell overwritten by unreadable glyphs) keeps its raw text, interprets `INVALID` with
  `UNREADABLE_CELL` and no value, and records no `PARSE_FAILED` attempt for that family;
- **qualification:** a temporary mapping copy giving one entry a demonstrated tier and a
  condition proven by a zero-valued interpretation in the same capture stores
  `qualification_ref` and condition evidence whose ids are stored rows; the same entry with the
  condition's line withheld (marked copy) stores `EQUIVALENCE_UNPROVEN` with no ref;
- **per-measurement qualification:** condition line
  `BasicEarningsLossPerShareFromDiscontinuedOperations` (0 in `OneD` and `FourD` of the retained
  Q2 FY26 instance); a marked copy making the `FourD` fact nonzero gives the entry's quarter
  interpretation demonstrated and its H1 one `EQUIVALENCE_UNPROVEN`; a `QUARTER`-only scope
  likewise demonstrates only the quarter key (package reporting kind `HALF_YEAR`);
- **re-processing:** re-ingesting the unchanged Q2 FY26 captures under a temporary mapping set
  (one entry changed) and a new XBRL `extractor_versions` re-stages nothing and appends
  `PARSER_REEXTRACTION` occurrences and interpretations under the new triple with later
  `recorded_at`; every v1 row is unchanged; this includes a comparative — the
  `CashAndCashEquivalentsCashFlowStatement` `PY_I` instant 2025-03-31 interpretation is
  `PARSER_REEXTRACTION` with its v1 predecessor set, never `ORIGINAL`;
- **identity:** marked XBRL copies changing only the `ScripCode` context identifier, or only the
  `ISIN` fact, record `IDENTITY_REJECTED` and write nothing for that member;
- **authority:** a binding whose source id the catalog does not declare, or declares `derived`,
  records `NOT_AUTHORISED` and stages nothing;
- **shared member:** ingesting a marked copy of the Q2 FY26 PDF as a revision package with the
  unchanged XBRL adds a package, a PDF capture and its rows, but no XBRL occurrence,
  interpretation or attempt; both packages' XBRL member resolves to the same rows;
- every native line no mapping matches is stored as an `UNMAPPED` interpretation, and the count of
  occurrences equals the count of emitted XBRL facts plus PDF cells;
- a marked copy with its namespace re-declared records an `UNSUPPORTED_SCHEMA` attempt and no
  interpretations;
- **dimensional fixture:** segment-revenue interpretations carry the evidenced canonical member in
  `dimensions`, never an ordinal, and FY25 Q2 and FY26 Q2 `Others` resolve to the same member
  despite different ordinals; segment assets carry an `elimination_basis` member, and pre- and
  post-elimination are distinct `MeasurementKey` digests;
- **one-member package:** FY25 Q2 (`in-bse-fin`, XBRL only) ingests with one member and no PDF
  attempt;
- **mapping refusals (no `pg`, no `retained`):** a temporary mapping-set copy with two entries
  sharing native field and context predicate raises `MappingLoadError(DUPLICATE_SELECTOR)`; one
  with a template expansion emitting the same canonical measurement twice raises the same; one
  with an unknown canonical id raises `DANGLING_CANONICAL_ID`; two entries for the same native name
  under `in-capmkt` and `in-bse-fin` load;
- re-running ingest leaves every row count unchanged.

Task 7 adds the alignment, derived and calculation-fixture cases to this file.

Test seams: `interpret`, `construct`, `statements_present`, `reporting_kind`, `parse_filed_at`,
`load_mapping_set`; ingest through `ingest_first_party` and the CLI.

Dependencies: 2, 3, 4, 11

Risks:
- The PDF is scanned with a garbled text layer in places (see `config/aparinds-fy26-q2.yaml`).
  Every-row extraction surfaces rows the targeted parser never read; they are kept as
  occurrences, and unreadable cells keep their raw text as `INVALID`, never dropped. The standalone
  half-year deferred tax prints as "(0,70)" (page 3): the basis binding keeps it out of the
  consolidated package; standalone reading is not in D1a, and a later one must not parse it as
  −70 by comma grouping.
- The `in-bse-fin` mapping file is authored from the inventory's nine Q3 FY25 filings. Only the
  Apar FY25 Q2 filing exercises it in D1a, through the revision fixture in Task 6.
- Modifying `xbrl_parser.py` and `source_intake.py` is additive. Run `test_xbrl.py`,
  `test_source_intake_store.py` and `test_source_intake_cli.py` unchanged and green.

### Task 6: Package and interpretation selection under cutoff and mode

Goal: Package, key and interpretation selection is correct under an eligibility boundary and
mode (both clocks; statement-family correction lineage; omitted lines give no value; other filing
families never interfere; pinned versions and supersession; `AS_KNOWN` by `recorded_at`; the
opening-instant rule), and comparatives get honest causes at ingest and are surfaced at run time
in either ingest order. The first-party revision fixture behaves as written.

Stage: eqos-3f9.4

Files:
- Create: `src/fundamentals/evidence/selection.py`
- Modify: `src/fundamentals/contracts/evidence.py` (add `RunMode`, `VersionPin`, `PinnedVersions`, `KeySelection`), `src/fundamentals/evidence/first_party_ingest.py` (comparative revision cause)
- Test: `tests/fundamentals/test_evidence_selection.py`

Interfaces:
- Consumes: `FilingPackage`, `EligibilityBoundary`, `Occurrence`, `Interpretation`, `FilingFamily`, `RevisionCause`, `InterpretationStatus`, `EvidenceRepository`, `ingest_first_party`, `retained_support` (Task 5); `MeasurementKey`, `PeriodInterval`, `TemporalRole`, `StatementFamily`, `Basis`, `Representation` (Task 3); `SourceState`, `SelectionSource`, `Interval` (Task 4).
- Produces:
  - `fundamentals.contracts.evidence.RunMode` StrEnum: `AS_KNOWN`, `RETROSPECTIVE`.
  - `VersionPin` (frozen: `version: str`, `content_sha256: str`) and `PinnedVersions` (frozen, each field a `VersionPin`): `dictionary`, `formula_set`, `mapping_set`, `normalisation_policy`, `extractor_xbrl`, `extractor_pdf`, `rounding_policy`, `definition_set`, `comparison_policy`, `alignment_rules`.
  - `KeySelection` (frozen: `key: MeasurementKey`, `representation: Representation`, `state: SourceState`, `interpretation: Interpretation | None`, `package_id: int | None`, `source: SelectionSource`, `reason: str | None`, `considered_interpretation_ids: tuple[int, ...]`, `surfaced_restatements: tuple[int, ...]`).
  - `fundamentals.evidence.selection` functions:
    - `is_eligible(occurrence: Occurrence, boundary: EligibilityBoundary) -> bool`
    - `select_package(packages: Sequence[FilingPackage], *, entity_id: int, family: FilingFamily, statement_family: StatementFamily, basis: Basis, framework: AccountingFramework, period_end: date, boundary: EligibilityBoundary) -> FilingPackage | None`
    - `as_reported_periods(package: FilingPackage, occurrences: Sequence[Occurrence]) -> frozenset[PeriodInterval]`
    - `select_interpretation(candidates: Sequence[Interpretation], *, boundary: EligibilityBoundary, mode: RunMode, pinned: PinnedVersions) -> tuple[SourceState, Interpretation | None, str | None]`
    - `select_key(key: MeasurementKey, representation: Representation, *, package: FilingPackage | None, occurrences: Sequence[Occurrence], interpretations: Sequence[Interpretation], boundary: EligibilityBoundary, mode: RunMode, pinned: PinnedVersions) -> KeySelection`
    - `select_opening_operand(key: MeasurementKey, representation: Representation, *, output_package: FilingPackage, package_occurrences: Sequence[Occurrence], package_interpretations: Sequence[Interpretation], boundary: EligibilityBoundary, mode: RunMode, pinned: PinnedVersions, fallback: Callable[[], KeySelection]) -> KeySelection`
    - `differing_restatement(selected: KeySelection, comparatives: Sequence[Interpretation]) -> tuple[int, ...]`: the ids of comparative interpretations for the same key digest whose interval does not intersect the selected interval (`Interval.intersects`). It is used by ingest (cause) and by Task 9 (`surfaced_restatements` and `AggregationOperand.has_differing_restatement`).
    - Reason constants `INTERPRETATION_AMBIGUOUS`, `NO_ELIGIBLE_PACKAGE`, `NOT_EXTRACTED_UNDER_PINS` (Task 9), `NOT_INTERPRETED_UNDER_PINS`.

Approach:
- **Package selection.** Filter by entity, family, basis, framework, reporting-period end and
  `eligible(boundary)`. `AS_KNOWN` drops interpretations with `recorded_at` after
  `boundary.first_seen_cutoff`. Walk each lineage from the newest eligible package back through
  `supersedes_package_id`: the first package whose `replaced_statements` is empty (whole package)
  or contains `statement_family` is selected for that family. So a P&L-only correction is
  selected for P&L while balance sheet and cash flow fall through to the original. No eligible
  package → every as-reported key of that family is `NO_VALUE` with `NO_ELIGIBLE_PACKAGE`.
- **Key selection.** A package reaches occurrences and interpretations only through its member
  captures (Task 2 capture ownership). A member absent for a representation gives `NO_VALUE` for
  that representation (FY25 Q2 PDF), unless a failed attempt decides first (Task 9, independent of
  member presence). Every
  interpretation considered but not selected is listed in `considered_interpretation_ids` so the
  run can record it as a negative input.
- **Pinned candidates (data spec l.404, l.416).** Candidates are interpretations under the pinned
  (mapping set, normalisation policy, extractor) triple, in `AS_KNOWN` also `recorded_at` ≤
  cutoff. A member capture with an available pinned-extractor generation (Task 9) but no available
  interpretation under the triple gives every key of that representation `UNAVAILABLE`
  `NOT_INTERPRETED_UNDER_PINS`; `NO_VALUE` stays for an interpreted capture lacking the line.
- **Comparatives (order-independent).** Occurrences in a package whose period does not end on the
  package's reporting-period end are comparatives. At ingest (this task's change to
  `first_party_ingest.py`): for each mapped comparative interpretation **not already stored**, the
  eligible inputs are the packages already stored for the comparative's period end, family, basis
  and framework, selected with `select_package` under
  `EligibilityBoundary.for_ingest(ingesting package knowledge time, this ingest's registration
  time)` and `select_key` in `RETROSPECTIVE` mode under the ingest's own mapping, normalisation and
  extractor versions — for the same representation if that original member exists, else the
  original's representative (XBRL, else PDF). So an original registered earlier in 2026 is
  eligible for a filing whose knowledge time is 2025, without moving either clock. This check runs only when the
  precedence rule (design decision 10) has not already assigned a reprocessing cause; a
  reprocessed comparative keeps its reprocessing cause and predecessor. Otherwise, if
  `differing_restatement` names it, the interpretation is written `COMPARATIVE_RESTATEMENT`;
  else, or when no original is stored yet, `ORIGINAL`. An interpretation already stored
  (same identity key, Task 2) is returned as is with its id and cause; repeat ingest never
  recomputes or rewrites a cause. At run time, surfacing never relies on the stored cause: Task 9
  recomputes `differing_restatement` over every eligible comparative, so either ingest order gives
  the same run.
- **Retained-evidence fact.** The Q2 FY26 `in-capmkt` instance has only four period shapes
  (2025-07-01..09-30, 2025-04-01..09-30, instants 2025-03-31 and 2025-09-30), so its Q2 FY25
  comparatives exist only in the PDF columns; the XBRL's 2025-03-31 instant is a comparative of the
  FY25 Q4 package.

Verification: `uv run pytest tests/fundamentals/test_evidence_selection.py` passes.
- **Unit (pure, constructed timestamps allowed):**
  - eligibility at, before and after the cutoff on both clocks; package eligibility with a cutoff
    between the two members' knowledge times is false while the PDF occurrence alone is eligible;
  - latest package within family, with a whole-package correction superseding the original;
  - **named-statement correction:** a P&L-only correction (`replaced_statements={PL}`) is selected
    for `PL`, and the original for `BALANCE_SHEET` and `CASH_FLOW`;
  - a correction omitting a line gives `NO_VALUE` for that key;
  - a later shareholding package leaves results keys unchanged, and the reverse;
  - manual correction selected under `RETROSPECTIVE` and under `AS_KNOWN` with a cutoff after it,
    and the original under `AS_KNOWN` with a cutoff before it;
  - two unsuperseded candidates give `INVALID` with `INTERPRETATION_AMBIGUOUS`;
  - interpretations under unpinned mapping versions are ignored; a capture interpreted only under
    another triple gives `UNAVAILABLE` `NOT_INTERPRETED_UNDER_PINS`, and under `AS_KNOWN` with a
    cutoff before the pinned triple's `recorded_at` the same, while `RETROSPECTIVE` selects it;
  - the opening operand uses the package's own disclosure when present (Apar H1 FY26 opening cash
    at 2025-03-31 from the H1 cash-flow statement), otherwise the fallback, with the source
    recorded;
  - `differing_restatement` names a disjoint comparative and not an intersecting one.
- **Integration (`pg`, `retained`), revision fixture, first-party part (no backdating):**
  1. Ingest Apar FY25 Q2 (`in-bse-fin`, XBRL only). Read its recorded first-seen time `T1`.
  2. Assert at a pre-capture cutoff (2025-10-15T00:00Z, before any registration) no Q2 FY25
     occurrence or package is eligible.
  3. Ingest Apar FY26 Q2 (XBRL + PDF). Read its recorded first-seen times; assert each `> T1`
     (fail loudly otherwise).
  4. Cutoffs are read from the store, never written: `R1` = the latest `recorded_at` of FY25 Q2's
     interpretations (≥ `T1`). At `R1` in `AS_KNOWN` (and at `T1` in `RETROSPECTIVE`): only the
     original package is eligible for Q2 FY25 keys; no comparative is eligible or surfaced.
  5. At `R2` = the latest `recorded_at` of the FY26 Q2 interpretations, in `AS_KNOWN`: the FY26
     Q2 PDF comparatives for 2024-07-01..2024-09-30 are eligible; the Q2 FY25 selection is
     unchanged.
  6. **Differing branch:** ingest a marked copy of the FY26 Q2 results PDF (edit: one Q2 FY25
     comparative revenue cell replaced by a different figure) as a separate package for the same
     period end. Its marked comparative is stored `COMPARATIVE_RESTATEMENT` (the stored original
     is eligible under the ingest boundary) and is returned by `differing_restatement` against the
     Q2 FY25 selection, which is unchanged. Every unchanged comparative of the real FY26 Q2
     package is `ORIGINAL`. Re-ingesting the marked copy returns the same interpretation identity
     and cause and adds no row.
  7. **Reverse order:** in a fresh database, ingest the real FY26 Q2 and the same marked copy
     first, then FY25 Q2. Their comparatives are stored `ORIGINAL` (no original was stored at
     their ingest), and re-ingesting the marked copy after FY25 Q2 keeps `ORIGINAL` and its
     identity. At each database's final `R` cutoff, the surfaced set from `differing_restatement`
     is equal across the two databases when compared by semantic key — (key digest, capture
     `blob_sha256`, `anchor_key`) — and capture identity, never by row id.

Test seams: `select_package`, `select_interpretation`, `select_key`, `select_opening_operand`,
`is_eligible`, `differing_restatement`.

Dependencies: 5

Risks: Test-first, because selection decides which filed number every later phase sees. Whether
any real Apar Q2 FY25 comparative differs from the original is unknown until ingest; the marked
copy proves the differing branch either way, and the test reports which real comparatives (if
any) differ.

### Task 7: Filing-specific alignment proofs, scoped tiers and derived evaluation with stored traces

Goal: For a first-party package, XBRL–PDF alignment proofs are computed and stored per measurement
key from declared subtotal and layout rules, each naming the exact participating interpretations.
Operand tiers are scoped (mapping qualification or proof). Derived rows evaluate per
representation over Task 6 selections, and each computed value persists a calculation trace with
per-operand tier evidence and selection source. Apar Q2 FY26 OPM = 8.06% has a stored trace;
receivable days and the segment-revenue total compute with stored traces.

Stage: eqos-3f9.4

Files:
- Create: `config/mappings/alignment/v1.yaml`, `src/fundamentals/evidence/alignment.py`, `src/fundamentals/evidence/derived.py`
- Modify: `src/fundamentals/evidence/repository.py` (add `put_alignment_proofs`, `list_alignment_proofs`, `get_alignment_proofs(ids)`, `put_calculation_trace` (child traces first), `get_calculation_traces(ids)` (operand rows and child traces included))
- Test: `tests/fundamentals/test_evidence_first_party.py` (extend)

Interfaces:
- Consumes: `evaluate_formula`, `resolve_operand_keys`, `aggregate_members`, `average_operand`, `OperandValue`, `CalculationResult`, `CalculationTrace`, `RoundingPolicy`, `load_rounding_policy`, `Interval`, `SelectionSource` (Task 4). `select_key`, `select_opening_operand`, `KeySelection`, `PinnedVersions`, `RunMode` (Task 6). `EvidenceRepository`, `FilingPackage`, `Occurrence`, `Interpretation` (Task 5). `CanonicalDictionary`, `DictionaryRow`, `Representation`, `weakest`, `QualificationContext`, `qualification_context` (Task 3); `prove_conditions` (Task 5).
- Produces:
  - `fundamentals.evidence.alignment`:
    - `AlignmentRule` (frozen: `rule_id`, `kind` ∈ {`SUBTOTAL_IDENTITY`, `LAYOUT_POSITION`}, `canonical_id: str`, `identity: FormulaNode | None` over canonical ids, `layout_anchor: Mapping[Representation, str] | None`).
    - `AlignmentRuleSet` (frozen: `version`, `content_sha256`, `rules`) and `load_alignment_rules(path: Path) -> AlignmentRuleSet`.
    - `AlignmentProof` (frozen: `proof_id: int | None`, `package_id`, `key: MeasurementKey`, `rule_id`, `rule_set_version`, `xbrl_interpretation_id: int`, `pdf_interpretation_id: int`, `participants: tuple[tuple[int, Representation], ...]`, `holds: bool`), with `participants_digest() -> str`.
    - `prove_alignment(package: FilingPackage, selections: Mapping[tuple[str, Representation], KeySelection], rules: AlignmentRuleSet) -> tuple[AlignmentProof, ...]`. Selections are keyed by measurement-key digest, so the quarter and H1 keys, and each segment member, are proven separately.
  - `fundamentals.evidence.derived`:
    - `operand_value(selection: KeySelection, *, proofs: Sequence[AlignmentProof]) -> OperandValue`: `scoped_tier` is `EQUIVALENCE_DEMONSTRATED` (with the proof id) when a holding proof for the selection's package names this exact interpretation; otherwise the interpretation's own stored scoped `tier` and `qualification_ref` (Task 5). That one path covers direct and constructed interpretations alike, so no mapping entry is assumed. `package_id` comes from the selection.
    - `DerivedSide` (frozen: `representation: Representation | None`, `result: CalculationResult`, `trace_id: int`). A `None` representation means shared single-representation operands.
    - `evaluate_derived(row: DictionaryRow, output: MeasurementKey, *, representation: Representation, resolve: Callable[[MeasurementKey, TemporalRole], KeySelection], proofs: Sequence[AlignmentProof], qualification: QualificationContext, policy: RoundingPolicy, repository: EvidenceRepository) -> DerivedSide`. `qualification` is the **output measurement's** context — `qualification_context(output, …)` with the output package member's schema and surface and `prove_conditions` over that member's selected interpretations for the output's period and basis (never the package reporting kind) — and scopes the formula's own tier.

Approach: A subtotal-identity rule holds for a key in a filing when the identity holds within
interval tolerance in **both** representations, using that key's own values for the same period
and dimensions. Examples: total income = revenue + other income; PBT = income − expenses +
exceptional items. A layout rule holds when both anchors are present for that key (e.g. basic EPS
at the EPS block's "Basic" line, and the `eps_basic` mapping's element in the reporting context).
v1 rules cover revenue, other income, total income, total expenses, `profit_before_tax`,
`profit_for_period` and `eps_basic`. They do not cover finance costs or depreciation and
amortisation.

Proofs are stored per package and key with their participating interpretation ids. They count as
demonstrated for that filing and key only (data spec §2) and are never generalised into mapping
tiers. Derived evaluation maps each `KeySelection` through `operand_value`. Operand
`precision_supported` is false when the occurrence's `precision_kind` is `UNSUPPORTED`.
Aggregated and `AVERAGE` operands go through `aggregate_members` and `average_operand`; their
child traces are persisted before the parent so the parent's operand row references them, and the
parent consumes the child's exact value and interval, never its stored rounding (Task 4).
An `OPENING` operand records `PACKAGE_OPENING_DISCLOSURE` or, via the fallback,
`INSTANT_OWN_SELECTION`/`HISTORICAL_PACKAGE`. Evaluation calls `evaluate_formula` and persists the
trace (and its operand rows) by content hash, which makes it idempotent.

Verification: `uv run pytest tests/fundamentals/test_evidence_first_party.py` passes, with the new
cases:
- Apar Q2 FY26 consolidated OPM evaluates per representation to 8.06 (exact 8.064…%, stored at
  the policy's `PERCENTAGE` scale 2), and its trace is stored and re-read with formula id and
  version, operand interpretation ids, values, bounds, scoped tiers with proof ids or qualification
  refs, and rounding policy id. Its effective tier is `EQUIVALENCE_UNPROVEN`, because finance-cost
  and D&A operands have no proof;
- alignment proofs hold for revenue, total income, total expenses, `profit_for_period` and
  `eps_basic` for the quarter key **and** separately for the H1 key, with distinct proof rows;
  each stored proof lists its participants and names no other key's interpretations. v1 has no
  segment rule, so key isolation across members is shown with a temporary rule set adding a
  segment-revenue `LAYOUT_POSITION` rule: two members get distinct proofs, each naming only its
  own member's interpretations;
- **calculation fixture, receivable days:** H1 FY26 consolidated receivable days evaluates with a
  stored trace whose receivables operand is the 2025-09-30 instant (`CLOSING`), never 2025-03-31;
- **calculation fixture, opening operand:** the H1 FY26 opening-cash operand records
  `PACKAGE_OPENING_DISCLOSURE` (the CF statement's 2025-03-31 opening balance); with a marked
  copy lacking that disclosure and the FY25 Q4 package ingested, it records
  `HISTORICAL_PACKAGE` with that package's interpretation id;
- **calculation fixture, segment total:** the Q2 FY26 segment-revenue total by dimensional
  aggregation over the four evidenced members computes with a stored parent trace whose operand
  references a `DIMENSIONAL_AGGREGATE` child trace listing all four member interpretations; the
  marked package with one member's segment revenue withheld gives `OPERAND_MISSING`, and its child
  trace still lists all four members (the withheld one with its state and no id). Both survive a
  re-read through `get_calculation_traces`, and an `AVERAGE` operand's child trace lists both
  instants;
- an `OPERAND_MISSING` derived side (a marked package with the revenue occurrence withheld) has a
  null value and a stored trace;
- **scope:** an operand whose mapping entry is demonstrated but out of scope (a temporary mapping
  copy scoped to `in-bse-fin`) gets `EQUIVALENCE_UNPROVEN`; a temporary `derived.yaml` giving OPM a
  demonstrated tier scoped to `STANDALONE` records an unproven `formula_tier` with no
  `formula_qualification_ref` for the consolidated output; the same formula scoped to `QUARTER`
  is demonstrated for the Q2 OPM output and unproven for the H1 OPM output of the same package.

Dependencies: 4, 5, 6

Risks: Alignment rules are new design with no prior implementation, so the panel should review
them with the plan. If OPM under the v1 dictionary formula does not reproduce 8.06%, the formula
definition or the operand mapping is wrong. Stop and report the operands and computed value, and
never adjust the formula to hit the number. The OPM formula's exact construction must come from
the spec and inventory, and is recorded in `config/dictionary/v1/derived.yaml` with its evidence.

### Task 8: Pair, extraction and derived-extraction decision tables, triage and policy

Goal: The following tables hold row by row, first match wins:
- the pair outcome table, with canonical identity and definition-record scope enforced;
- the extraction status table;
- the derived-extraction status, including the bound tagging-difference adjustment;
- first-party-only corroboration (design decision 11).

Triage classes a difference as `STRUCTURAL`, `MAGNITUDE` (≥ the 0.5% policy v1 threshold) or
`NOISE`. Adjacent integer counts never agree. A single-representation family gives extraction
`NOT_APPLICABLE`.

Stage: eqos-3f9.5

Files:
- Create: `config/comparison_policy/v1.yaml`, `config/definition_sets/v1.yaml`, `src/fundamentals/compare/__init__.py`, `src/fundamentals/compare/policy.py`, `src/fundamentals/compare/definitions.py`, `src/fundamentals/compare/triage.py`, `src/fundamentals/compare/tables.py`
- Modify: `src/fundamentals/contracts/comparison.py` (add the enums below)
- Test: `tests/fundamentals/test_compare_extraction_tables.py`

Interfaces:
- Consumes: `SourceState`, `CalculationState`, `Interval`, `OperandValue`, `evaluate_formula`, `RoundingPolicy` (Task 4); `MeasurementKey`, `ApplicabilityStatus`, `StatementFamily`, `Representation`, `DictionaryRow`, `EvidenceTier`, `weakest`, `QualificationContext` (Task 3); `relative_difference` (`fundamentals.verify.laneb_triage`); `MutationClass` (`fundamentals.verify.laneb_sensitivity_model`).
- Produces:
  - **`fundamentals.contracts.comparison` StrEnums:**

    | Enum | Values |
    |---|---|
    | `PairOutcome` | `NOT_COMPARABLE`, `AGREE`, `AGREE_UNQUALIFIED`, `DEFINITION_DIFFERENCE`, `MISMATCH`, `ANOMALY` |
    | `Triage` | `STRUCTURAL`, `MAGNITUDE`, `NOISE` |
    | `ExtractionStatus` | `NOT_APPLICABLE`, `UNAVAILABLE`, `NOT_COMPARABLE`, `NONE`, `ONE_SIDE_XBRL`, `ONE_SIDE_PDF`, `AGREE`, `AGREE_UNQUALIFIED`, `TAGGING_DIFFERENCE`, `DISAGREE` |
    | `CorroborationStatus` | `NOT_APPLICABLE`, `UNAVAILABLE`, `NOT_COMPARABLE`, `VENDOR_ONLY`, `NO_SOURCE`, `FILING_ONLY`, `CONFLICT`, `CORROBORATED`, `AGREES_UNQUALIFIED`, `ANOMALY`, `DEFINITION_DIFFERENCE` (the full set, so D1b.2 adds no enum values) |
    | `ReasonCode` | `CANONICAL_MISMATCH`, `PERIOD_MISMATCH`, `BASIS_MISMATCH`, `FRAMEWORK_MISMATCH`, `CURRENCY_MISMATCH`, `KIND_MISMATCH`, `DIMENSION_UNRESOLVED`, `PERIOD_AMBIGUOUS`, `PRECISION_UNSUPPORTED`, `SIDE_INVALID`, `UNREADABLE_CELL`, `INTERPRETATION_AMBIGUOUS`, `VENDOR_INTERNAL_CONFLICT`, `OPERAND_INVALID`, `UNDEFINED`, `REVISION_INCOMPATIBLE`, `ADJUSTMENT_OUT_OF_SCOPE`, `ADJUSTMENT_MISMATCH` |
    | `PairKind` | `EXTRACTION`, `REPORTED_VS_DERIVED` |

  - `fundamentals.compare.policy`: `ComparisonPolicy` (frozen: `policy_id`, `version`, `content_sha256`, `magnitude_threshold: Decimal`), and `load_comparison_policy(path: Path) -> ComparisonPolicy` (raises `VersionContentDriftError` from `fundamentals.contracts.versioning`, Task 3).
  - `fundamentals.compare.definitions`: `DefinitionScope` StrEnum (`MAPPING`, `MEASUREMENT`, `FILING`), `DefinitionRecord` (frozen: `record_id: str`, `scope: DefinitionScope`, `scope_ref: str` (a mapping entry id, measurement-key digest or package id), `canonical_id: str`, `operand_name: str | None`, `evidence_ref: str`, `explained_amount: Decimal`, `unit: ValueKind`), `DefinitionSet` (frozen: `version`, `content_sha256`, `records`), `load_definition_set(path: Path) -> DefinitionSet`, and `publish_definition_set(conn: psycopg.Connection, definition_set: DefinitionSet) -> int`. Publishing is idempotent, and `VersionContentDriftError` is raised when the same version is published with other content.
  - `fundamentals.compare.triage`: `structural_class(left: Decimal, right: Decimal) -> MutationClass | None` and `triage(left: Decimal, right: Decimal, policy: ComparisonPolicy) -> Triage`.
  - `fundamentals.compare.tables`:
    - `EvidencedRelationship` (frozen: `left_canonical_id`, `right_canonical_id`, `evidence_ref`) — the only way two different canonical ids pair (none in D1a's first-party pairs).
    - `ComparisonSide` (frozen: `key: MeasurementKey`, `state: SourceState`, `value: Decimal | None`, `interval: Interval | None`, `tier: EvidenceTier` (already scoped or proven), `aligned_by_proof: bool`, `mapping_entry_ids: tuple[str, ...]`, `package_id: int | None`, `calculation_state: CalculationState | None`, `reasons: tuple[ReasonCode, ...]`).
    - `PairResult` (frozen: `outcome: PairOutcome`, `reason: ReasonCode | None`, `triage: Triage | None`, `difference: Decimal | None`, `interval_gap: Decimal | None`, `definition_record_id: str | None`).
    - `pair_outcome(first: ComparisonSide, other: ComparisonSide, *, definitions: DefinitionSet, policy: ComparisonPolicy, relationship: EvidencedRelationship | None = None) -> PairResult`.
    - `ExtractionResult` (frozen: `status`, `reason`, `pair: PairResult | None`, `adjustments: tuple[TaggingAdjustment, ...]`, `rejected_adjustments: tuple[AdjustmentRejection, ...]`).
    - `extraction_status(*, family_has_pair: bool, xbrl: ComparisonSide, pdf: ComparisonSide, definitions: DefinitionSet, policy: ComparisonPolicy) -> ExtractionResult`.
    - `TaggingAdjustment` (frozen: `operand_name: str`, `representation: Representation`, `direction: int` (+1 adds to, −1 subtracts from that representation's operand), `amount: Decimal`, `unit: ValueKind`, `definition_record_id: str`).
    - `OperandExtraction` (frozen: `operand_name`, `xbrl: OperandValue`, `pdf: OperandValue`, `result: ExtractionResult`): an operand's own extraction outcome with both sides, each carrying its key, mapping entry id and `package_id`.
    - `validate_adjustment(adjustment: TaggingAdjustment, *, operand: OperandExtraction, definitions: DefinitionSet) -> TaggingAdjustment | AdjustmentRejection`. Accepted only when all hold: the operand's own result is `TAGGING_DIFFERENCE` citing the same `definition_record_id`; that record's `operand_name` and `canonical_id` match this operand; its scope matches **this operand's** side (`MAPPING`: the operand's mapping entry id; `MEASUREMENT`: the operand's key digest; `FILING`: the operand's `package_id`); `unit` equals the operand's value kind; `amount` equals the record's `explained_amount`; and `direction` moves the named representation toward the other side. `AdjustmentRejection` (frozen: `adjustment`, `reason: ReasonCode`) is recorded, never applied.
    - `derived_extraction_status(*, row: DictionaryRow, output: MeasurementKey, every_operand_single_representation: bool, operands: Mapping[str, OperandExtraction], xbrl: ComparisonSide, pdf: ComparisonSide, adjustments: Sequence[TaggingAdjustment], definitions: DefinitionSet, policy: ComparisonPolicy, rounding: RoundingPolicy, qualification: QualificationContext) -> ExtractionResult`. It re-evaluates only with adjustments that `validate_adjustment` accepts.
    - `corroboration_status(*, applicability: ApplicabilityStatus, first_party: ComparisonSide, vendors: Sequence[ComparisonSide] = ()) -> tuple[CorroborationStatus, ReasonCode | None]`. It raises `VendorCorroborationNotImplemented` when `vendors` is non-empty.

Approach: Each table is a first-match-wins sequence in the spec's row order (data spec §5). The
agreement test is `Interval.intersects`. Difference and gap are reported from the stored values and
intervals.
- **Row 1 key compatibility.** Canonical ids must be equal unless an `EvidencedRelationship` names
  the pair (else `CANONICAL_MISMATCH`); then period, basis, framework, currency, kind and dimension
  members must match, each with its own reason. An `INVALID` side carries its own reason (e.g.
  `UNREADABLE_CELL`).
- **Tiers.** Row 2 needs both sides `EQUIVALENCE_DEMONSTRATED` (as scoped by Task 7) or
  `aligned_by_proof` on both.
- **Definition records** apply only within scope: `MAPPING` when `scope_ref` is in a side's
  `mapping_entry_ids`; `MEASUREMENT` when it equals the shared key digest; `FILING` when it equals
  the first-party side's `package_id`. A record must also match the canonical id.
- **Triage** applies only to `MISMATCH` and `ANOMALY`: `STRUCTURAL` when `structural_class` names
  a class, else `MAGNITUDE` when `relative_difference` ≥ threshold, else `NOISE`.
- **Derived extraction.** If the unadjusted pair would be `DISAGREE`, each `TaggingAdjustment`
  is applied only when `validate_adjustment` accepts it against that operand's own extraction and
  the cited record's scoped evidence (else it is rejected and recorded). The adjustment shifts that representation's operand interval by `direction × amount`; the formula is
  then **re-evaluated** with `evaluate_formula`, so the adjustment propagates through the formula
  and its intervals (e.g. a currency adjustment to PBT goes through ÷ revenue × 100 for PBT
  margin). The status is `TAGGING_DIFFERENCE` only if the re-evaluated intervals intersect;
  otherwise `DISAGREE`. Applied adjustments are returned for storage in `pair_adjustments`.
- Definition set v1 is published empty.

Verification: `uv run pytest tests/fundamentals/test_compare_extraction_tables.py` passes:
- one parametrized case per row of the pair table (rows 1–6, including each row-1 reason and
  `CANONICAL_MISMATCH`);
- **definition scope:** a `FILING` record for another package id does not explain the pair (stays
  `MISMATCH`/`ANOMALY`); the same record with the current package id gives
  `DEFINITION_DIFFERENCE`; a `MAPPING` record for an entry neither side uses does not apply;
- one per row of the extraction table (rows 1–9 incl. 2a), including an `UNREADABLE_CELL` side
  giving `NOT_COMPARABLE`;
- **derived extraction:** a subtraction formula (`opex_excl_finance_and_da`) whose operand's
  tagging adjustment reconciles → `TAGGING_DIFFERENCE`; a percentage formula (PBT margin) where a
  currency adjustment to the PBT operand reconciles only after re-evaluation through ÷ revenue × 100;
  one operand's tagging difference plus an unrelated operand discrepancy → `DISAGREE`; adjustments
  are rejected (and the status stays `DISAGREE`) when the unit mismatches, when they cite another
  operand's record, when they cite a `FILING` record for another package, and when the amount or
  direction differs from the record; a computed match with one unproven operand →
  `AGREE_UNQUALIFIED`; an `EQUIVALENCE_UNPROVEN` formula over demonstrated operands →
  `AGREE_UNQUALIFIED`;
- `NOT_APPLICABLE` when every operand family is single-representation;
- triage at exactly 0.5% → `MAGNITUDE` and just below → `NOISE`; a ×1000 ratio and a sign flip →
  `STRUCTURAL`;
- counts n vs n+1 → outside tolerance;
- a single-representation family → extraction `NOT_APPLICABLE`;
- first-party-only corroboration rows 1, 2, 2a, 5 and 7.

Test seams: `pair_outcome`, `extraction_status`, `derived_extraction_status`,
`corroboration_status`, `triage`.

Dependencies: 3, 4

Risks: Test-first, because these tables decide every status the product reports. Supersession of
`eqos-ya6` applies to the new comparator only; `three_source.py` is not touched.

### Task 9: Runs, manifests, replay and the report CLI

Goal: `fundamentals compare run` publishes one immutable run atomically (versions, inputs incl.
negative ones, results, source values, pairs); identical requests, even concurrent, yield one run;
replay from the manifest alone, through by-id reads only, reproduces stored results after evidence
changes; config changes yield a new run; failed attempts give `UNAVAILABLE` and `INCOMPLETE`
whether or not the member exists; reported and derived values are both stored, never merged; an
unreachable database or mid-publication failure leaves nothing visible; Q3 balance-sheet rows are
`NOT_APPLICABLE`; `fundamentals compare report` renders a stored run.

Stage: eqos-3f9.6

Files:
- Create: `src/fundamentals/compare/run.py`, `src/fundamentals/compare/resolve.py`, `src/fundamentals/compare/report.py`, `src/fundamentals/api/compare_cli.py`
- Modify: `src/fundamentals/evidence/repository.py` (run, version, input, result, pair writes and reads), `src/fundamentals/api/cli_parser.py`, `src/fundamentals/api/cli.py`
- Test: `tests/fundamentals/test_compare_runs.py`

Interfaces:
- Consumes: everything Produced by Tasks 1–8. Specifically: `open_pool`, `DatabaseUnavailableError`, `PgSettings`; `basis_status_as_of`, `settings_as_of`, `segment_members_as_of`; `load_dictionary`, `decide_applicability`, `ApplicabilityContext`; `load_rounding_policy`, `derive_period_value`, `AggregationOperand`, `evaluate_formula`; `load_mapping_set`, `EvidenceRepository`, `outcome_source_state`, `scoped_tier`; `select_package`, `select_key`, `select_opening_operand`, `differing_restatement`, `PinnedVersions`, `RunMode`; `load_alignment_rules`, `prove_alignment`, `operand_value`, `evaluate_derived`; `load_comparison_policy`, `load_definition_set`, `publish_definition_set`, `pair_outcome`, `extraction_status`, `derived_extraction_status`, `corroboration_status`.
- Produces:
  - **`fundamentals.compare.run`:**
    - `RunStatus` StrEnum: `COMPLETE`, `INCOMPLETE`.
    - `RunExitStatus` IntEnum: `SUCCESS = 0`, `SUCCESS_WITH_OPEN_HIGH = 3`, `INCOMPLETE = 4`, `FAILURE = 5`.
    - `RunInputKind` StrEnum: `CAPTURE_REF`, `PACKAGE`, `OCCURRENCE`, `INTERPRETATION`, `ATTEMPT`, `ALIGNMENT_PROOF`, `CALCULATION_TRACE`, `EVIDENCE_INPUT`, `SETTINGS_RECORD`, `BASIS_STATUS`, `SEGMENT_MEMBER`, `PACKAGE_STATEMENT`, `DEFINITION_SET`; `RunInputDisposition` StrEnum: `SELECTED`, `SURFACED`, `NOT_SELECTED`, `FAILED_ATTEMPT`.
    - `RunInput` (frozen: `kind`, `ref_id: int`, `disposition`).
    - `RunScope` (frozen: `entity_ids: tuple[int, ...]`, `period_ends: tuple[date, ...]`, `bases: tuple[Basis, ...]`, `sources: tuple[str, ...]`).
    - `RunRequest` (frozen: `scope`, `cutoff: datetime`, `mode: RunMode`, `pinned: PinnedVersions`, `code_version: str`, `database_identity: DatabaseIdentity` (host, port, name only)).
    - `RunManifest` (frozen): request fields; `inputs: tuple[RunInput, ...]` (sorted; capture SHA-256s carried by the capture-ref inputs); status; operational failures. Method `identity_hash() -> str` (design decision 6).
    - `SourceValue` (frozen: `source_role`, `representation`, `state`, `reason`, `value`, `lower`, `upper`, `interpretation_id`, `calculation_trace_id`, `attempt_id`, `calculation_state`).
    - `ResultRow` (frozen: `row_id: str`, key, `value_identity`, applicability and rule id, extraction result, corroboration status and reason, `source_values: tuple[SourceValue, ...]`, pairs with adjustments, `surfaced_restatements`). `row_id` = `canonical_id|period|basis|dimension members|value_identity`, period as `start..end` or the instant, dimension members as sorted `axis=member` (or `-`).
    - `RunRecord` (frozen: `run_id: int`, `manifest: RunManifest`, `created: bool`).
    - `execute_run(request: RunRequest, *, pool: ConnectionPool, config_root: Path, extractor_pins: Mapping[Representation, VersionPin] | None = None) -> RunRecord`. `extractor_pins` is a test seam (default: the pins computed from the extractor constants and source files, design decision 7).
    - `replay_run(run_id: int, *, pool: ConnectionPool, config_root: Path) -> tuple[ResultRow, ...]`.
    - `load_results(run_id: int, *, pool: ConnectionPool) -> tuple[ResultRow, ...]`.
    - It raises `VersionContentDriftError`, imported from `fundamentals.contracts.versioning` (Task 3), when a pinned version's content differs from what is stored.
  - **`fundamentals.compare.resolve.ReplayReader`** (Protocol): the only reads replay may use, all immutable by id, one per `RunInputKind`:

    | `RunInputKind` | Read |
    |---|---|
    | `CAPTURE_REF` | `get_capture_refs(ids) -> tuple[CaptureReference, ...]` |
    | `PACKAGE` | `get_packages(ids) -> tuple[FilingPackage, ...]` |
    | `PACKAGE_STATEMENT` | `get_package_statements(ids) -> tuple[PackageStatementRecord, ...]` |
    | `OCCURRENCE` | `get_occurrences(ids) -> tuple[Occurrence, ...]` |
    | `INTERPRETATION` | `get_interpretations(ids) -> tuple[Interpretation, ...]` |
    | `ATTEMPT` | `get_attempts(ids) -> tuple[AcquisitionAttempt, ...]` |
    | `ALIGNMENT_PROOF` | `get_alignment_proofs(ids) -> tuple[AlignmentProof, ...]` |
    | `CALCULATION_TRACE` | `get_calculation_traces(ids) -> tuple[CalculationTrace, ...]` |
    | `EVIDENCE_INPUT` | `get_evidence_inputs(ids) -> tuple[EvidenceInputRecord, ...]` |
    | `SETTINGS_RECORD` | `get_settings_records(ids) -> tuple[SettingsRecord, ...]` |
    | `BASIS_STATUS` | `get_basis_statuses(ids) -> tuple[BasisStatusRecord, ...]` |
    | `SEGMENT_MEMBER` | `get_segment_members(ids) -> tuple[SegmentMemberRecord, ...]` |
    | `DEFINITION_SET` | `get_definition_set(id) -> DefinitionSet` |

    `EvidenceRepository` satisfies it; `replay_run` is typed against `ReplayReader`, so no as-of or `list_*` read is reachable from replay.
  - **`fundamentals.compare.resolve`:** `ResolvedInputs` (frozen: packages, occurrences, interpretations, attempts, proofs, traces, identity/settings/statement evidence ids, `inputs: tuple[RunInput, ...]`) and `resolve(request: RunRequest, *, repository: EvidenceRepository, config: LoadedConfig) -> tuple[ResolvedInputs, tuple[ResultRow, ...]]`; `recompute(inputs: ResolvedInputs, request: RunRequest, *, config: LoadedConfig) -> tuple[ResultRow, ...]` (pure over the loaded inputs; used by both execution and replay). `LoadedConfig` (frozen) holds every content-pinned artifact.
  - **`fundamentals.compare.report.render_report(record: RunRecord, results: Sequence[ResultRow], *, dictionary: CanonicalDictionary) -> str`.** It prints `record.run_id` and, from `record.manifest`, cutoff, mode, status and code commit, then one line block per row keyed by `row_id`: each source's value (currency amounts also in crore with two decimals), unit and state, extraction and corroboration statuses, pair outcomes with difference and gap, headline marker, surfaced restatements, and calculation traces for derived rows. `NOT_APPLICABLE` rows are listed with their rule id.
  - **CLI:** `fundamentals compare run --entity <entity_key> --period-end <YYYY-MM-DD> --basis consolidated [--cutoff <ISO-8601 UTC>] [--mode as_known|retrospective] [--config-root config]` prints the run id and status, and exits with `RunExitStatus`. `fundamentals compare report (--run <id> | --entity <key> --period-end <date> --basis <basis>)` prints the report; the second form picks the latest run for that scope.

Approach:
- **Load config.** `execute_run` loads and content-pins every versioned config (design decision 7).
- **Context (before any value is read).** Per entity, basis and period end, for each statement
  family: `select_package` gives the package; the `ApplicabilityContext` is built from regime
  `IN_LODR`, document type from the filing family, `statements_present` from that package's
  `PRESENT` rows, `period_kind` = the package's `reporting_kind` (with no package, the fiscal
  position of the period end from `settings_as_of(FISCAL_YEAR_END_MONTH)`), `requested_basis` from
  the scope, and `entity_basis_status` from `basis_status_as_of(entity, cutoff)`. The package
  statement, settings and basis-status ids used become `SELECTED` inputs. Applicability is decided
  per row from this context.
- **Attempt-to-state (precedes presence rules, independent of member presence).** Per requested
  (entity, period end, basis, representation, statement family):
  - *Candidates* match the request's entity, period end, **basis**, **framework**,
    representation and the selected member's (or failed binding's) **source id and surface**, and
    belong to the selected package, its member capture, or — only when no selected package has a
    member for that representation — the request with no package. Other attempts are kept as
    evidence but never decide this side (data spec l.353, 411–425).
  - *Availability (data spec l.400–407).* `ACQUISITION` attempts: `attempted_at` ≤ cutoff in both
    modes. `EXTRACTION` attempts: only under the run's **pinned extractor**; `AS_KNOWN` needs the
    generation's `attempted_at` ≤ cutoff, `RETROSPECTIVE` only that its capture is eligible.
  - *Resolution, first match wins:* (1) the latest available `ACQUISITION` attempt failed and no
    member exists; (2) the latest available generation under the pinned extractor (round-3 rule:
    its overall attempt plus the family attempts sharing its capture and `attempted_at`) has a
    non-`COMPLETE` overall attempt; (3) or a non-`COMPLETE` family attempt for this family; (4) a
    member exists but no pinned-extractor generation is available → `UNAVAILABLE`
    `NOT_EXTRACTED_UNDER_PINS`; (5) otherwise `select_key`. Other extractors' and older
    generations never decide the state.
  Rules (1)–(3) give `outcome_source_state` (`UNAVAILABLE`, or `NO_VALUE` for `NOT_PUBLISHED`) for
  every key of that representation and family, with the attempt id. No candidate attempt and no
  member → `NO_VALUE`. Failed attempts are `FAILED_ATTEMPT` inputs; `recompute` applies the same
  rule to the manifest's attempts, so replay matches.
- **Select and evaluate.** `select_key` per key and representation (pinned candidates, Task 6); considered-but-not-selected
  interpretations and packages are `NOT_SELECTED` inputs. Surfaced restatements come from
  `differing_restatement` over every eligible comparative and are `SURFACED` inputs. Alignment
  proofs are computed (or reused by content) and are inputs. Derived rows go through
  `evaluate_derived` per representation with the output measurement's qualification context
  (Task 7); its condition-evidence interpretations are `SELECTED` inputs.
- **Reported vs derived.** D1a triggers a period derivation only when the selected package's
  reporting kind is `YEAR`: Q4 = FY − 9M for every `ADDITIVE_DURATION` row, with the 9M operand
  from the `NINE_MONTH` package for the same fiscal year and `has_differing_restatement` from
  `differing_restatement`. The derived value is a separate result row (`value_identity=DERIVED`);
  if a reported Q4 value exists for the same key, both rows are stored and a
  `REPORTED_VS_DERIVED` pair compares them through `pair_outcome`. They are never merged; the
  derived row's trace is kept.
- **Comparison.** Build `ComparisonSide`s (with mapping entry ids and package id); representative
  value: XBRL if present, else PDF. Apply the tables.
- **Publish.** Compute the manifest and identity hash, then publish in **one transaction**:
  insert `runs` with ON CONFLICT (`identity_hash`) DO NOTHING; on conflict roll back and return the
  existing run with `created=False`; otherwise insert `run_versions`, `run_inputs`, `results`,
  `result_source_values`, `result_surfaced_restatements`, `pair_outcomes` and `pair_adjustments`,
  then commit. Evidence writes (proofs, traces) happen before the transaction as idempotent
  evidence writes (Task 2). Serialisation failures retry at most three times, then fail loudly.
- **Status.** Run status is `INCOMPLETE` when any non-diagnostic source state is `UNAVAILABLE`.
- **Replay.** `replay_run` reads only the manifest: `run_versions` for config (refusing a content
  drift) and `run_inputs` ids for every evidence row, loaded through `ReplayReader` by kind, then
  calls `recompute`. Child traces of aggregate and `AVERAGE` operands load with their parents.
- **Composition root.** `compare_cli.py` builds `PgSettings` and the runtime pool. A
  `DatabaseUnavailableError` or any database error before commit maps to `FAILURE` with a
  structlog error carrying no credentials.

Verification: `uv run pytest tests/fundamentals/test_compare_runs.py` (marked `pg` and `retained`) passes, over
Apar FY26 Q2, Q3 and Q4 ingested from retained originals (plus FY25 Q2 where stated):
- two threads run the same default-cutoff request concurrently, giving one `runs` row, one
  `created=True`, and result row counts equal to a single run's;
- `replay_run` equals `load_results` field by field, including the segment-total row's
  parent and child traces (every member listed, also in the withheld-member marked run);
- **replay reads by id only:** `replay_run` over a spy `ReplayReader` wrapping the repository
  succeeds, and the test fails if any `*_as_of` or `list_*` method of the repository is called;
- **replay closure:** after the run, the test (a) ingests a later package for the same period end
  (a marked whole-package correction), (b) seeds a second identity input recording
  `STANDALONE_ONLY` for Apar with a later `recorded_at`, (c) adds a settings record changing the
  fiscal year end month, and (d) ingests a marked package whose statement presence differs. A
  fresh run at a later cutoff differs (consolidated rows `NOT_APPLICABLE`), while `replay_run` of
  the original equals its stored results;
- a temporary config root with a patched dictionary version (adding one row), a patched mapping-set
  version and a definition set v2 each produce a new run id, while the original replays unchanged;
  the same version string with changed content raises `VersionContentDriftError`;
- **new pins, unchanged capture:** pinned to a patched mapping set before re-ingest →
  `UNAVAILABLE` `NOT_INTERPRETED_UNDER_PINS`, `INCOMPLETE`; after re-ingest under it and a new XBRL
  extractor version, a run pinned to both shows the new values and the original still replays;
- **failed extraction:** a package whose PDF member is a marked copy with the P&L block's markers
  removed records `PARSE_FAILED` for (PDF, `PL`); its P&L rows have PDF state `UNAVAILABLE`,
  extraction `UNAVAILABLE`, never `NO_VALUE` or `ONE_SIDE_XBRL`; the run is `INCOMPLETE`, the CLI
  exits 4, and `replay_run` reproduces the `UNAVAILABLE` states and attempt ids;
- **failure resolution beyond members:** (i) package-less — a PDF binding staged against a wrong
  pin records a `FAILED` attempt with no capture and no package; with an XBRL-only package
  selected, P&L PDF state is `UNAVAILABLE` with that attempt id, not `NO_VALUE`; (ii) missing
  member — the same with the attempt carrying the package id gives the same; (iii) historical
  cutoff — a run with cutoff before that attempt's `attempted_at` (read from the store) treats the
  PDF as absent and unattempted, `NO_VALUE`; (iv) replay of each run reproduces its states;
  (v) failure → success — a P&L `PARSE_FAILED` generation under extractor X, then a later
  `COMPLETE` generation under X′ on the same capture (Task 5 seam; reuse level 2 never re-runs an
  extractor already run): a run pinned to X′ after the second gives the extracted values, and
  replays identically;
  (vi) a family failure in the latest generation with an overall `COMPLETE` still gives that
  family `UNAVAILABLE` and leaves other families extracted;
  (vii) **modes** — with (v)'s generations and a cutoff between them: pinned X′, `AS_KNOWN` →
  `UNAVAILABLE` `NOT_EXTRACTED_UNDER_PINS`, `RETROSPECTIVE` → the X′ values; pinned X, both modes
  → `UNAVAILABLE` from the X failure;
  (viii) **isolation** — a `STANDALONE` `PARSE_FAILED` attempt for the same capture and a later
  failed generation under an unpinned extractor leave the consolidated states unchanged;
- **one-member package:** the FY25 Q2 run gives `ONE_SIDE_XBRL` for P&L rows with an XBRL value,
  not `UNAVAILABLE`, and stays `COMPLETE`;
- **reported vs derived:** the FY26 Q4 run stores, for revenue, a `REPORTED` Q4 row and a
  `DERIVED` Q4 row (FY − 9M from the Q3 package) with its trace, plus a `REPORTED_VS_DERIVED` pair;
  both values survive in one run with distinct `row_id`s;
- **identity hash inputs:** a run whose only difference is one additional failed attempt has a
  different identity hash;
- with `EQOS_PG_PORT` pointing at a closed loopback port, `fundamentals compare run` (in-process
  `main`) exits 5, and the test database still has zero `runs` rows from that call;
- `fundamentals compare report --run <id>` prints that run id (from the `RunRecord` passed to
  `render_report`);
- **mid-publication failure:** injecting a failure after `results` are inserted (the
  `publish_hook` seam) leaves zero rows in every run table for that identity hash, and a rerun
  succeeds;
- the Apar FY26 Q3 run reports every balance-sheet and cash-flow row `NOT_APPLICABLE` with its rule
  id, never `NO_SOURCE`; the Q2 run reports them applicable;
- every enum value round-trips through its table's CHECK constraint.

Test seams: `execute_run` and `replay_run` over a `pg_db` pool; `recompute` over loaded inputs;
`publish_hook: Callable[[str], None] | None` (keyword-only, default `None`, called with the stage
name between publication inserts; tests raise from it); the CLI via in-process
`fundamentals.api.cli.main` with `PgTestDatabase.cli_env()`.

Dependencies: 2, 5, 6, 7, 8

Risks: Atomicity and idempotency are integration behaviour, so write the concurrency,
unreachable-database and mid-publication tests first. The replay test must be able to fail; the
four evidence changes above are what make it able to. File size: `resolve.py` holds resolution and
`run.py` publication and replay; split further if either nears 800 lines.

### Task 10: Tracer end-to-end

Goal: The tracer runs over Apar Q2 FY26 retained first-party captures on the test database and goes
through the real CLI path: `fundamentals evidence ingest`, then `fundamentals compare run`, then
`fundamentals compare report`. The report shows:
- revenue, total income, total expenses, `profit_for_period` and basic EPS with extraction `AGREE`;
- `profit_before_tax` 340.56 crore and `profit_before_tax_incl_associates` 340.53 crore;
- headline PBT 340.53;
- `profit_for_period` 251.70 crore;
- OPM 8.06% with its trace, extraction `AGREE_UNQUALIFIED` (finance-cost and D&A operands have no
  alignment proof in v1).

Stage: eqos-3f9.7

Files:
- Test: `tests/fundamentals/test_compare_tracer.py`

Interfaces:
- Consumes: `pg_db`, `PgTestDatabase.cli_env` (Task 1); `config/identity/aparinds.yaml`, `seed_issuer_identity` (Task 2); `retained_support.apar_original`, `fundamentals evidence ingest` (Task 5); `fundamentals compare run` and `report`, `RunExitStatus`, `ResultRow.row_id` format (Task 9); `fundamentals.api.cli.main`.
- Produces: none.

Approach: One test, marked `pg` and `retained`. It seeds APARINDS identity from `config/identity/aparinds.yaml`
(the evidenced identity input; the entity-map fixtures are synthetic and contain no APARINDS),
then invokes the three CLI commands in-process with the test database environment:
`evidence ingest` with the retained manifest, raw root, a temporary snapshot root,
`--issuer-config config/aparinds-fy26-q2.yaml` and both members; then `compare run`; then
`compare report`. It parses the report by `row_id` (e.g.
`profit_before_tax|2025-07-01..2025-09-30|CONSOLIDATED|-|REPORTED`) and asserts the listed values
and statuses. The expected numbers are the spec-stated values plus the retained filing's PAT and
OPM, written as literals in the test with a comment citing data spec Stage 1 Success Criteria and
the capture SHA-256. They are never read from code output. The run exits `SUCCESS` with status
`COMPLETE`, and the report header carries the run id that `compare run` printed.

Verification: `uv run pytest tests/fundamentals/test_compare_tracer.py` passes. Then run the phase
gate:
- `uv run ruff check src tests/fundamentals`
- `uv run ruff format --check src tests/fundamentals`
- `uv run mypy --strict src`
- `uv run pytest tests/fundamentals`, all with the compose service up and the originals present
- `scripts/verify.sh gate D1a`

Dependencies: 9

Risks: This is the phase exit criterion, and any spec-stated value that fails here points back to
Tasks 5 and 7. Diagnose with `systematic-debugging`; never change the expected literals. The report
format is not frozen, so assert values and statuses by `row_id`, not by layout.

### Task 11: PDF statement-page discovery for P&L, balance sheet, cash flow and segment blocks

Goal: Given a loaded results PDF and per-family page specs, the locator finds the consolidated
P&L, balance sheet, cash flow and segment blocks, bounds each block on its page, derives its column
intervals from the header, and returns every banded numeric row with raw cell text. On the retained
Apar Q2 FY26 results PDF all four consolidated blocks are found and named rows read.

Stage: eqos-3f9.4

Files:
- Create: `src/fundamentals/extract/pdf_statement_pages.py`
- Modify: `src/fundamentals/api/config.py` (add optional `statement_pages: Mapping[str, StatementMarkersConfig]` to `PdfParseConfig`, default empty, where `StatementMarkersConfig` is frozen with `title_markers`, `confirmations`, `end_markers` and `unit_markers` tuples; existing configs load unchanged); `config/aparinds-fy26-q2.yaml` (additive `statement_pages` entry for `BALANCE_SHEET` declaring the unit variant below)
- Test: `tests/fundamentals/test_pdf_statement_pages.py`

Interfaces:
- Consumes: `LoadedPdf`, `PdfPage`, `PageWord`, `load_pdf` (`fundamentals.ingest.pdf_source`); the header-text and printed-unit helpers in `fundamentals.extract.pdf_header_text` and `pdf_printed_unit`. `pdf_column_geometry.py` (777 lines, P&L-only `_find_statement_page` at line 349) is not modified or reused; `PdfParseConfig` (`fundamentals.api.config`); `StatementFamily`, `Basis`, `ValueKind` (Task 3).
- Produces:
  - `StatementPageSpec` (frozen: `family: StatementFamily`, `basis_markers: Mapping[Basis, str]` ("Consolidated", "Standalone"), `title_markers: tuple[str, ...]`, `confirmations: tuple[str, ...]`, `end_markers: tuple[str, ...]`, `unit_markers: tuple[UnitMarker, ...]`), and `specs_from_config(pdf_parse: PdfParseConfig) -> Mapping[StatementFamily, StatementPageSpec]` (P&L from the existing block; BS, CF and segment markers from `pdf_parse.statement_pages` when set, else module defaults: "Statement of Assets and Liabilities"; "Cash Flow Statement" and the retained page-7 variant "Statement of cash flows"; "Segment", whose confirmations include "Inter-segment").
  - `UnitMarker` (frozen: `text: str`, `scope: UnitScope` (`PAGE`, `SUBSECTION`), `raw_unit: str`, `raw_scale: int`, `value_kind: ValueKind`). v1 defaults, each evidenced on the retained PDF: "Rs. in crores" (`PAGE`, INR, 7, `CURRENCY_AMOUNT`) and "Earnings per share (EPS) (Rs.)" (`SUBSECTION`, INR per share, 0, `PER_SHARE_AMOUNT`). A subsection marker applies from its line to the block end or the next marker. No fuzzy matching: page 6 of the retained Q2 FY26 PDF prints "(Rs. in crones)", declared as an exact `PAGE` variant (INR, 7) in `config/aparinds-fy26-q2.yaml` citing SHA-256 `8be1b8de…4ae5` p.6; without it those rows get no unit (`INVALID`, `UNIT_MISMATCH`).
  - `ColumnInterval` (frozen: `index: int`, `x0: float`, `x1: float`, `header_text: str`, `basis: Basis`, `super_header_text: str`, `super_header_x0: float`, `super_header_x1: float`).
  - `StatementLocation` (frozen: `family`, `basis: Basis`, `page: int`, `top_line: int`, `bottom_line: int`, `columns: tuple[ColumnInterval, ...]` (only the requested basis's columns), `excluded_columns: int`).
  - `StatementPageNotFoundError`.
  - `locate_statement_pages(pdf: LoadedPdf, specs: Mapping[StatementFamily, StatementPageSpec], *, basis: Basis) -> Mapping[StatementFamily, StatementLocation | None]`.
  - `PdfStatementRow` (frozen: `family`, `page: int`, `line: int`, `label: str`, `unit: UnitMarker | None`, `unit_line: int | None`, `cells: tuple[PdfCell, ...]`) and `PdfCell` (frozen: `column_index`, `raw_text`, `column_header: str`, `super_header_text: str`).
  - `extract_statement_rows(pdf: LoadedPdf, location: StatementLocation) -> tuple[PdfStatementRow, ...]`.

Approach: A page qualifies for a family when, case-insensitively, it carries the requested
basis's marker, one title marker and every confirmation. Pages 3, 6 and 7 of the retained Q2 FY26
PDF print consolidated and standalone columns side by side under "Consolidated" and "Standalone"
super-headers, so basis is bound per **column**, not per page: each numeric column is assigned to
the super-header whose **column-group span** covers it (the span runs from the super-header's
group start to the next super-header or the page's last numeric column, derived from the retained
layout — not the header word's own bounding box, which is narrower than its columns), only the requested basis's columns are kept, and a
column under no super-header or two fails the family (no guessing). The block runs from the title line to the
first end marker (the next statement's title or a notes heading), so a page holding two statements
(e.g. BS and the start of CF) yields two bounded blocks. Column intervals come from the header
row's word x-extents; the BS has two instant columns, the CF two duration columns, the segment block
the same columns as the P&L. A row is banded when its words fall into the column intervals; every
banded row is returned with raw text per cell, even when the text is not a clean number (the
interpretation decides `UNREADABLE_CELL`). Each row gets the nearest preceding unit marker in its
block (subsection before page), or `None`. No OCR is run (the existing `pdf_ocr_recovery` lane is P&L-only and stays out of D1a): a page
whose text layer lacks the markers is not found, and Task 5 turns that into `PARSE_FAILED` only when structural presence says the family
exists.

Verification: `uv run pytest tests/fundamentals/test_pdf_statement_pages.py` (marked `retained`)
passes on the retained Q2 FY26 results PDF:
- all four consolidated families are located, each on a page carrying the consolidated marker;
  on pages 3, 6 and 7 every returned column lies under the "Consolidated" super-header and the
  standalone columns are counted in `excluded_columns`, never returned (e.g. the P&L current-tax
  row returns 89.13 for the quarter, never the standalone 88.15); the CF block is found by its
  page-7 title "Statement of cash flows";
- the P&L rows above the EPS marker carry the crore `PAGE` unit, and the "Basic" row carries the
  `SUBSECTION` rupees-per-share unit with scale 0;
- page-6 BS rows carry the declared "(Rs. in crones)" variant, and no unit without it;
- the BS block yields a "Total assets" row whose current-column text, normalised from crore,
  matches the XBRL `Assets` value at 2025-09-30 (113,125,300,000 INR) within interval tolerance;
- the CF block yields the closing cash row matching XBRL `CashAndCashEquivalentsCashFlowStatement`
  at 2025-09-30 (3,093,900,000 INR) and the opening row matching 2025-03-31 (6,864,200,000 INR);
- the segment block yields one revenue row per evidenced segment and the "Less: Inter-segment
  revenue" row; the quarter revenue rows match XBRL `SegmentRevenue` for the four members;
- the Q3 FY26 results PDF yields no BS or CF block;
- existing `test_pdf.py` and `test_bse_pdf.py` stay green unchanged.

Test seams: `locate_statement_pages`, `extract_statement_rows`.

Dependencies: 3

Risks: The scanned PDF's text layer is garbled in places; markers may need variants, added to the
issuer config with evidence, never fuzzy matching. If a family cannot be located on the retained
PDF, stop and report the page text rather than lowering the markers. The matches above compare
against XBRL values only to prove the locator; they are not alignment proofs.

## Stage coverage

| Stage | Tasks | Acceptance file(s) |
|---|---|---|
| eqos-3f9.1 | 1, 2 | `test_pg_evidence_schema.py` (plus `test_pg_migrations.py`) |
| eqos-3f9.2 | 3 | `test_canon_dictionary_load.py`, `test_canon_applicability.py` |
| eqos-3f9.3 | 4 | `test_canon_formula.py`, `test_canon_interval.py` |
| eqos-3f9.4 | 11, 5, 6, 7 | `test_pdf_statement_pages.py`, `test_evidence_first_party.py`, `test_evidence_selection.py` |
| eqos-3f9.5 | 8 | `test_compare_extraction_tables.py` |
| eqos-3f9.6 | 9 | `test_compare_runs.py` |
| eqos-3f9.7 | 10 | `test_compare_tracer.py` |

Execution order: 1 → 2 → 3 (Task 3 consumes Task 2's `BasisStatus`), then 3 → 4 and 3 → 11 in
parallel. Then 5 (needs 2, 3, 4, 11) → 6 → 7. Task 8 (needs 3, 4) runs in parallel with 5–7.
Then 9 (needs 2, 5, 6, 7, 8) → 10. Every task's dependencies are listed in its own section; the
graph is acyclic, no task depends on a later stage's task, and Task 6's change to
`first_party_ingest.py` follows Task 5. Shared contracts are owned by the earliest consumer's
predecessor: `BasisStatus` (Task 2), qualification and `VersionContentDriftError` (Task 3),
`Interval` (Task 4, `contracts/interval.py`), `EligibilityBoundary` (Task 5).

## Self-review record

- **Spec coverage.** Each D1a acceptance clause in bd maps to a task Verification line. The Stage 1
  criteria in the roadmap's spec refs also map to tasks:
  - correction (incl. named statements), family and revision (first-party part): Task 6;
  - dimensional: Task 5;
  - calculation (receivable days, opening cash, segment total, OPM): Tasks 4 and 7;
  - failed attempt → `UNAVAILABLE`, replay of negative states, unreachable database: Task 9.
- **Gap naming.** Each gap became a task, an exclusion or a follow-up:
  - NOTICED BUT NOT TOUCHING: `fundamentals.ingest.bse_pdf_source._parse_filed_at` stamps a BSE
    wall time as UTC without a zone conversion. Proposed as a follow-up bead.
  - NOTICED BUT NOT TOUCHING: the retrieval manifest's ISO `filed_at_nse` entries (FY25 Q2–FY26
    Q1 comparators) look like IST wall time labelled `+00:00` (design decision 5). Proposed as a
    follow-up bead to verify against NSE and re-record; D1a keeps the raw strings.
  - NOTICED BUT NOT TOUCHING: `verify/three_source.py` keeps a private structural detector that
    duplicates `compare/triage.structural_class`. Proposed as a follow-up bead (removed from D1a
    to keep a shipped module untouched).
  - The `pg` and `retained` markers change what the full test suite needs. Documented in
    `verification.md` (Task 1).
  - The supersession of `eqos-ya6` and the plan path note on `eqos-3f9` are bd writes for the
    orchestrator after approval.

## Round-1 and round-2 review resolution

All closed and confirmed by round 3. Fix locations by task (DD = design decision):

| Findings | Fixed in |
|---|---|
| Rulings (a)–(c), first-seen | DD 5, 6, 9, 10; Constraints "No backdating"; Tasks 2, 5, 6 (steps 1–7), 9 |
| M1, M10 | DD 5, 12; Tasks 2, 5, 10 |
| M2–M8, M11–M18 | Tasks 2, 4–9, 11 (as amended by R1–R13) |
| M19, M20 | DD 13; Task 5 mapping refusals |
| m1–m15 | Tasks 1, 4, 5, 6, 9; DD 11; Self-review follow-ups |
| Round-2 rulings | Scope guard; `ILLEGIBLE` and `DEFINITIONAL` removed (DD 8, Tasks 3, 5, 11); Apar basis-status citation (Task 2) |
| R1, R4, R5, R6 | Task 5 PDF approach, enums, constructions, tests; Task 11 basis binding and units |
| R2, R3 | DD 8; Task 3 qualification contract; Tasks 4, 5, 7 scoped tiers |
| R7, R8, R9 | Task 2 schema (precision, qualification, capture ownership, keys); Tasks 5, 6; DD 5 `EligibilityBoundary` |
| R10–R13 | Task 4 traces; Task 8 adjustments; Task 9 attempt-to-state, `ReplayReader`, replay; Task 2 by-id reads |
| r1–r8 | Task 2 `BasisStatus`; Task 7 key isolation; DD 5; Tasks 5, 9, 11; `contracts/versioning.py`; Task 1 `.codex` file |

## Round-3 review resolution

Sol round 3: 20 of 21 FIXED; R11 PARTIAL (one MAJOR). Resolved by the orchestrator after round 3
under `.claude/rules/core/04-agent-stack.md` step 5.

| Finding | Fixed in |
|---|---|
| R11 residual (older family failure overrides later success) | Task 5 attempt generation (one overall attempt per invocation, shared `attempted_at`); Task 9 attempt-to-state resolves the latest generation only; Task 9 tests (v) failure → success and (vi) in-generation family failure |
| Note: ASCII dash | Task 5 PDF missing-state markers |
| Note: super-header span | Task 11 column-group span |

## Critical-review resolution

Fresh critical review (Sol): 7 MAJOR, 3 MINOR, 5 notes. DD = design decision.

| Finding | Fixed in |
|---|---|
| C1 | DD 10; Task 5 Reuse levels, re-processing test; Task 6 Pinned candidates; Task 9 new-pins test |
| C2 | Task 3 per-measurement `QualificationContext`, `qualification_context`, test; Task 5 qualification and test; Task 7 `evaluate_derived`, `QUARTER` OPM test; Task 9 Select and evaluate |
| C3 | Task 2 `exact_*` columns; Task 4 `exact` fields, Approach (replay), 0/0.01 test; Task 7 Approach |
| C4 | Task 2 `acquisition_attempts`; Task 5 `AttemptStage`, `AcquisitionAttempt`, Ingest; Task 9 candidates, test (viii) |
| C5 | Task 9 availability, rule (4), tests (v), (vii); extractor seams in Tasks 5 and 9 |
| C6 | Task 5 `member_identity.py`, `issuer_identifiers`, Identity, tests; File map |
| C7 | DD 12 authority table; Task 5 `authorise`, Intake, `catalog`, CLI, test |
| c1 | DD 12 and Task 5 `store/capture_local.py`; Task 4 `contracts/interval.py`; File map |
| c2 | DD 4; markers in Tasks 5, 6, 9, 10 |
| c3 | Status line |
| Notes | Reserved ids: Task 2 Write classes, Task 5 qualification; predicates: Task 5 `prove_conditions`; nesting/contiguity: Task 4; maintenance connection: DD 3, Task 1; "Rs. in crones", "78,09": Task 11, Task 5 numeric grammar |
| N1 (critical re-review): revision-cause precedence | Design decision 10 precedence rule; Task 5 Interpretation; Task 6 Comparatives; Task 5 re-processing test (comparative case) |

## Stage 3 build notes (as built, Sol-approved 2026-10-12)

- Monetary operand currency comes from the caller's evidenced `reporting_currency`; dimensionless outputs carry no currency; mixed currencies raise `CurrencyMismatchError`. Negative rounding scales are refused.
- **Task 7 obligation:** `TraceOperand` does not itself enforce the NULL-selection rule. Task 7 must persist child traces first, attach their ids to the parent before hashing and persisting it, and verify provenance by readback; the 0002 CHECK fails closed if a child id is missing.

## Stage 5 build notes (as built, Sol-approved 2026-10-12)

- **Triage is exact (orchestrator ruling, overrides Task 8's "reuse `relative_difference`"):** the `NOISE`/`MAGNITUDE` decision and structural classes use exact `Fraction` arithmetic; Decimal is for displayed values only. The shared helper is unchanged for its other callers.
- `derived_extraction_status` also takes `dictionary` and `reporting_currency` (required by `evaluate_formula`).
- Definition-record `explained_amount` and adjustment `amount` must be positive; `direction` carries the sign. One record applies to an operand at most once, on either representation (matches the `pair_adjustments` key).
- Extraction refuses (`ValueError`) representations from different packages or a valued side with no package id, as for cross-entity pairs.
- **Task 9 obligation:** `load_comparison_policy` hashes the file but cannot detect drift from a path alone; the run must check the comparison-policy pin and raise `VersionContentDriftError` on drift.
