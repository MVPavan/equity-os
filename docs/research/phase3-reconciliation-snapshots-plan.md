# Phase 3 plan — reconciliation + snapshots (eqos-kx4.4)

**FROZEN 2026-09-05** by the owner (PavanMV) with the four decisions in §9 taken.
History: draft by Codex Sol high, reviewed by Opus 5 high (first contact) and
Fable 5.1 high (outer critic), orchestrator synthesis, third critique by Codex
Sol high; review digests live in the session scratchpad and are summarised on
bead `eqos-kx4.4`.

## v3 header (as frozen)

Supersedes v2 after the third critique (`critique-sol-v2.md`, REVISE; eight
findings, all classified valid-actionable except the kernel-extraction alternative,
recorded as a rejected trade-off). Ground truth: `BRIEF.md`. Claims about code are
VERIFIED against HEAD caf22e7; local-inventory facts are marked `MEASURED:`;
anything else `INFERENCE:` or `OWNER:`. Third and final critique cycle.

## 1 Scope

Three deliverables: (D1) a shared capture-level outcome code, (D2) one
capture-record contract plus one store the next commands adopt, (D4) a
three-source tolerance compare (XBRL spine ⊕ Screener ⊕ Tijori) built by
generalising Lane B, with an offline base-rate measurement as the exit.
Entity map (D3) shipped. Series versions, parse-level outcome mapping, FactStore
loading for watchlist stocks, and any export surface are OUT (§8).

## 2 Decisions (one per brief question)

**Q1 Snapshot identity.** Capture id = `<retrieved_at UTC, microseconds>-<content
sha256[:12]>` inside `<root>/<source_id>/<surface>/<request_key>/`. Every attempt
is a record (attempt history is evidence); bytes deduplicate content-addressed
under `<root>/blobs/<source_id>/<sha256[:2]>/<sha256>`, and the capture dir
holds a hard link `body.<ext>` to the blob, so `ls` of a route still lists its
captures in time order and dedupe is a filesystem property. *Rejected:* UUID4
ids (v1) — lose chronological listing and crash idempotence; the one-second
collision they fix is unreachable in-run (`DEFAULT_MIN_REQUEST_SPACING_SECONDS
= 1.1`, `upstox_source.py:77`) and vanishes at microsecond precision.

**Q2 Store medium.** Filesystem only. The route directory IS the request index
(no `by-request/`, no SQLite). Records are published last (`record.json`), body
first; read-back verifies sha256 on commit (as `screener_financials_cli.
_write_verified` does today) and on every `read_body`. *Rejected:* SQLite index
— no query today needs it; a later index must be rebuildable from records.

**Q3 Series versions (eqos-f2m).** NOT built. Non-preclusion only: `CaptureRecord`
carries a stable `capture_id`, `request` identity, `content_sha256`,
`retrieved_at`, `record_sha256`, which is everything a later `CaptureCoverage`
needs to reference. Bound to state before f2m builds it: observed-timestamp
coverage must be run-length or gap-list encoded, never one timestamp per bar.

**Q4 Taxonomy shape.** One capture-level enum `OutcomeCode` in `contracts/`:
OK, OK_EMPTY, NOT_OFFERED (the vendor has no such surface for this entity,
e.g. no consolidated basis), PLAN_LOCKED, AUTH_EXPIRED, IDENTITY_MISMATCH,
SCHEMA_DRIFT, RATE_LIMITED, TRANSPORT_ERROR, CLIENT_BLOCKED, REQUEST_REJECTED;
`RETRYABLE_CODES = {RATE_LIMITED, TRANSPORT_ERROR}`. `OutcomeRecord{code,
native_kind: str, native_value: str}` keeps the native wire value verbatim, so
no earned distinction is flattened. *Rejected:* v1's seven-family typed-detail
union and OutcomeScope — two copies of every native member and no reader for
section/island/run scopes exists (all readers today are per-source, in `api/`).
Dissent recorded: Fable reads `BASIS_UNAVAILABLE` as "a fact about the company",
not a vendor gap; the record keeps `native_value=basis_unavailable`, so the
code-level choice loses nothing. `NOT_STATIC`, `SKIPPED`, `UNPARSEABLE`,
`ZERO_RESULTS`, `INCOMPLETE` are parse/run-level and are NOT mapped (kx4.5).

**Q5 Existing enums.** Kept, unchanged, including wire values. A
`to_outcome_code()` function lives beside `AcquisitionOutcome` (Upstox) and
`PageOutcome` (Screener); Tijori's typed errors and `TijoriTableAccessMetadata`
(feature lock present-and-disabled → PLAN_LOCKED) map in the cut-over slice.
`test_upstox_scope_guards.py::test_the_lane_declares_no_shared_acquisition_
taxonomy` (a substring scan) is narrowed by intent to an AST assertion: no class
named `AcquisitionOutcome` under `contracts/`.

**Q6 Compare inputs and the map.** XBRL spine = the gold file. MEASURED: 10
gold files under `data/gold/` for NINE stocks (TITAN twice, no NETWEB); `data/`
is gitignored, so the set is local, not committed. INFERENCE: FactStore holds
no watchlist rows (the `run` pipeline is config-driven; not checked). Gold
`SourceValue` carries no precision, and it is lost in `agreement._source_values`
(`:258`), not in `_gold_fact`; S4 adds optional `decimals: int | None` there
(no schema bump: optional field, reader tolerant). The spine value is the XBRL
`source_value` selected by source id, never `GoldFact.value` (a reconciled
representative). Gold is regenerated offline through the existing FIXTURE path
over cached raw (`report_cli._cached_stock` → `run_stock(..., out_dir=gold_dir)`);
`validate --live` is NOT used. The owners-of-parent candidate is an auxiliary
concept, absent from gold; it is measured once by an orchestrator read of the
retained XBRL, outside the comparator's contract.
Screener = Phase 2 `SectionTable` JSON read by a NEW offline reader
(`verify/three_source_inputs.py`) that includes `quarters`, keeps section
identity, row status, unit and provenance, and verifies symbol/basis against
`FinancialsMetadata`. *Rejected:* Lane B's `load_screener_sections` — its
`COMPARED_SECTIONS` omit `quarters` (`upstox_crosscheck.py:49`) and it narrows
rows to a label→value map. Tijori = `ingest/tijori_pl.parse_pl_bytes` over the
RETAINED body (S3), with `retrieved_at` taken from the capture, never a fetch.
Precision contract: every side is converted to a crore-denominated half-ULP
through `verify.crossfoot.half_ulp(decimals, scale)` (Tijori `-7`/`10**7` →
0.5 crore; XBRL from its own decimals/scale; Screener whole-crore → 0.5);
`StatedValue` never receives an Observation's raw `decimals`.
Name map = ONE registry, `verify/three_source_map.py`: each entry binds a vendor
selector (source, section, parent-qualified row) AND the observation-alias →
`FactRole` binding `fact_view._DERIVED_ROLE_ALIASES` holds today, so
`fact_view` keeps its configured-role behaviour reading the registry (pinned by
`baseline`). Each entry carries `means`, exclusions and an `EvidenceTier`. Net
profit has two candidate entries with their own tier each; equal values never
promote a tier (P2 rule); the replay investigates meaning, then the owner
freezes the entry and the measurement is reported separately. *Rejected:* a
second map (v1); FactStore "pinned revision ref" (no such type).

**Q7 What a mismatch does.** Lane B's decision A: exit 0 always; `--warn-exit`
opt-in → 1 after a warn; 3 = unreadable input (the reader's errors translated,
never a bare `SystemExit(str)`, which exits 1 today); 2 = store/preflight
refusal (`SnapshotError` translated). Sibling commands today exit 0/2/3 plus 1
from bare `SystemExit`; the new command declares all four explicitly. Report and
`warnings.tsv` under `data/research/three-source/<run>/` by default; subscriber
`raw_text` only under `--include-values`. No block before a measured base rate.

**Q8 Slices.** S1 outcome code → S2 store → S3 tijori-tables cut-over → S4
registry + spine precision → S5 inputs + comparator → S6 CLI + measurement (§5).
*Rejected trade-off (Sol):* extracting a shared numeric/classification kernel
from Lane B behind a compatibility adapter — correct in principle, but it
reopens three sealed Lane B slices for no behaviour gain; `half_ulp`,
`relative_difference`, `EvidenceTier` and `MutationClass` are already importable.

**Q9 Out.** §8.

## 3 Module layout (all ≤ 800 lines; api → components → contracts)

| Path | Responsibility |
|---|---|
| NEW `contracts/acquisition_outcome.py` | `OutcomeCode`, `RETRYABLE_CODES`, `OutcomeRecord` |
| NEW `contracts/snapshot.py` | `RequestIdentity`, `BlobRef`, `CaptureRecord`, `SnapshotRights`, `SnapshotError` family |
| NEW `store/no_clobber.py` | the 40-line core of `api/artifact_writer.py` moved, raising typed errors; `api/artifact_writer.py` becomes the `SystemExit` shim (baseline-gated) |
| NEW `store/snapshot_store.py` | `SnapshotStore`: `put_capture`, `get_capture`, `read_body`, `list_captures(request)`, staging + publish-last, read-back verify |
| MOD `ingest/upstox_source.py`, `ingest/screener_session_models.py` | `to_outcome_code()` beside each native enum |
| MOD `ingest/tijori_source.py` | new `fetch_financials_page()` envelope: bytes + typed auth/identity classification, BEFORE any parse; `fetch_table`/`fetch_all_tables`/`fetch_pl` unchanged in behaviour (all read the same GET `/company/<slug>/financials/` via `_fetch_pl_bytes`) |
| MOD `api/tijori_tables_cli.py` | cut over to the store; exit 0/2 unchanged |
| NEW `verify/three_source_map.py` | frozen versioned registry (`SourceLineMapping` with vendor selector + alias→role binding, `mapping_for`, `UnmappedRowError`) |
| NEW `verify/three_source_inputs.py` | offline readers: Screener `SectionTable` JSON (all sections incl. quarters, metadata-verified), Tijori retained body → `parse_pl_bytes`, gold XBRL source value |
| MOD `reconcile/fact_view.py`, `reconcile/agreement.py` | `fact_view` reads the registry for its alias→role table; `SourceValue.decimals: int \| None` populated in `_source_values` |
| MOD `scripts/verify.sh` | `capture_dirs()` also lists `data/raw/snapshots/*` (today it scans only immediate children of `scratchpad/`) |
| NEW `verify/three_source.py` | `compare_triple` → `TripleRow`/`TripleReport`; reuses `EvidenceTier`, `half_ulp`, `relative_difference`, `MutationClass`; defines source-neutral `PairOutcome`/`PairTriage` (Lane B's `CrosscheckOutcome`/`TriageClass` carry Upstox-specific members and stay untouched) |
| NEW `api/three_source_cli.py` | `three-source-crosscheck` command; wired in `cli.py`/`cli_parser.py` |
| NEW tests `test_phase3_{outcomes,snapshot,tijori_retention,map,compare,cli}.py`, `phase3_fixtures.py` | synthetic only |

`verify/` is the home because the repo's boundary is compare-without-voting
(`verify/`) vs vote (`reconcile/`); a package rail (scope guard: nothing under
`verify/three_source*` imports `reconcile` or `store/fact_store`) enforces
"two agreeing vendors never confirm". *Rejected:* v1's `compare/` package and
`contracts/comparison_key.py` extraction (component→component imports are the
convention: `reconcile/`, `api/`, `thesis/` already import `verify.comparison_key`).

## 4 Contracts (Pydantic, frozen, `extra="forbid"`, UTC datetimes)

- `RequestIdentity{schema_version:int, source_id:str, surface:str, request_key:str,
  method: GET|POST, parameters: tuple[(name,value)]}` — parameters allowlisted per
  route; never a cookie, token, CSRF value, or full URL with a secret.
- `BlobRef{source_id:str, content_sha256: Sha256, byte_count:int≥0}` — hash of
  the exact retained bytes before any decode/decompress.
- `CaptureRecord{schema_version, capture_id, request, retrieved_at, http_status:
  int|None, media_type, content_encoding, body: BlobRef|None, outcome:
  OutcomeRecord, rights: SnapshotRights, record_sha256}` — `body=None` ≠ zero-byte
  body; a body-less capture's id is `<ts µs>-nobody`. `outcome` is sealed AFTER
  transport + the adapter's identity/auth gates (logged-in marker,
  `company_details`, `is_auth`) and BEFORE parsing; no later step rewrites it.
  An anonymous shell commits as AUTH_EXPIRED, never OK. Failed attempts inside
  a bounded retry are retained as their own records (RATE_LIMITED etc.).
- `SnapshotRights{use: PRIVATE_INTERNAL, redistribution: PROHIBITED, authority_refs}`
  — A05-DECISION-005 on every Screener/Tijori record; grants nothing.
- `SnapshotError` → `CaptureConflictError`, `IntegrityError`, `UnsafePathError`,
  `MissingSnapshotError`, `SnapshotIOError`. Components never raise `SystemExit`.
- `SourceLineMapping{source: SCREENER|TIJORI, section:str, row_selector:str
  (parent-qualified), means:str, exclusions: tuple[str,...], tier: EvidenceTier,
  concept_qnames: tuple[str,...] (candidates until measured), map_version:str}`.
- `SideValue{source: XBRL|SCREENER|TIJORI, amount: Decimal, half_ulp: Decimal,
  raw_label, capture_id|gold_sha256}` — precision already converted to crore.
- `PairResult{left, right, mapping_id, tier, outcome: PairOutcome
  (AGREE|MISMATCH|ANOMALY|NOT_COMPARABLE|MISSING_LEFT|MISSING_RIGHT|MISSING_BOTH),
  difference, tolerance, relative_difference, triage: PairTriage
  (STRUCTURAL|MAGNITUDE|NOISE|NONE), reasons}` — tier, difference and triage
  live on the PAIR because the three pairs may use different mappings.
  MISMATCH only on tier 1; tier 2 → ANOMALY; tier 3 → NOT_COMPARABLE (Lane B's
  earned split, `screener_crosscheck.py:130-146`).
- `TripleRow{concept_qname, period, xbrl|screener|tijori: SideValue|None,
  pairs: tuple[PairResult, ...] (three)}`.
- `TripleReport{symbol, quarter, map_version, gold_sha256, capture_ids,
  rows, counts}` — no majority vote anywhere; the three pairs are reported.

## 5 Slices, public seams, acceptance behaviours

**S1 Outcome code** (contracts + two `to_outcome_code`; scope guard narrowed).
Seam: `OutcomeCode`, `OutcomeRecord`, `RETRYABLE_CODES`. Tests: every member of
`AcquisitionOutcome` and `PageOutcome` maps and keeps its wire value in
`native_value`; retryability equals `RETRYABLE_OUTCOMES`; `BASIS_UNAVAILABLE`
never maps to OK/OK_EMPTY; parse-level enums have no mapping and the test says
so; AST guard: no `AcquisitionOutcome` class under `contracts/`; `BARRED_MODULES`
still holds for every `upstox*.py`.

**S2 Snapshot store** (contracts/snapshot, store/no_clobber, store/snapshot_store;
artifact_writer shim under `baseline`; `verify.sh capture_dirs()` extended).
Seam: `SnapshotStore`, `CaptureRecord`, `SnapshotError`. Tests: identical bytes
two attempts → one blob, two records; crash before record → no readable
capture, orphan blob only; hash mismatch or truncated blob refused on read;
symlink/traversal refused; secret-shaped parameter refused by `RequestIdentity`;
gzip bytes round-trip verbatim; absent vs empty body distinct and the body-less
id rule holds; capture dir listing is time-ordered; the gate's fixture rails
scan `data/raw/snapshots/*` (proved with a synthetic directory, orchestrator).

**S3 Tijori tables cut-over** (the one command with a real retention defect:
model JSON only). Pipeline: `fetch_financials_page` envelope → typed auth/identity
classification → `put_capture` → `parse_all_tables_bytes` / `parse_pl_bytes`.
Seam: `fetch_financials_page`, `retain_tijori_tables` → `CaptureRecord`; CLI
`--snapshot-root` default `data/raw/snapshots/v1`; exits 0/2 plus the explicit
translation of today's bare `SystemExit` (1) paths. Tests: bytes retained
verbatim; outcome sealed after the identity gate (anonymous shell →
AUTH_EXPIRED; wrong company → IDENTITY_MISMATCH); `financials_locks` stays
metadata on the record — a disabled UI feature never classifies the capture
(PLAN_LOCKED needs route-specific evidence, none exists for this page today);
parse failure keeps the committed capture (outcome OK) and claims no parsed
artifact; replay uses `read_body` → parse with the capture's `retrieved_at`,
never a fetch; no second legacy copy; existing model JSON byte-identical.
Screener financials and Upstox layouts untouched (Lane B reader unaffected;
Upstox → f2m).

**S4 Registry + spine precision** (verify/three_source_map, fact_view reads it,
`SourceValue.decimals`). Seam: `SourceLineMapping`, `mapping_for`,
`UnmappedRowError`. Tests: unmapped row refuses; a tier-1 entry cannot drop its
exclusion; `fact_view.derived_concept_map` output unchanged for every alias
(baseline); old gold loads with `decimals=None` and the bridge refuses it
(UNKNOWN_PRECISION); regenerated gold carries decimals; `Net Profit` selector is
section-qualified (QUARTERS vs PROFIT_LOSS both exist); two candidate entries
with equal values keep their own tiers.

**S5 Inputs + comparator** (verify/three_source_inputs, verify/three_source).
Seam: `read_screener_sections`, `read_tijori_capture`, `read_gold_spine`,
`compare_triple`, `TripleRow`, `TripleReport`. Tests: quarters and annual
`Net Profit` stay distinct and annual never satisfies a quarterly compare;
metadata symbol/basis mismatch refuses; residual at summed half-ULP AGREEs, one
unit outside MISMATCHes (tier 1) / ANOMALY (tier 2); tier 3 never claims;
precision conversion pinned for XBRL, Tijori (`-7`/`10**7` → 0.5) and Screener
(whole crore → 0.5) and EPS; key incompatibility (basis, period type, currency,
scale) refuses rather than aligns; every `MutationClass` seeded on a vendor
side is detected against a fixed spine, with coverage reported beside
detection; two agreeing vendors cannot overrule the spine; MISSING_BOTH is
distinct from either side missing; nothing under `verify/three_source*`
imports `reconcile` or `fact_store` (rail).

**S6 CLI + measurement** (`three-source-crosscheck --gold-dir --screener-root
--snapshot-root --symbol|--isin-file --out [--warn-exit] [--include-values]`).
Seam: exit codes per Q7, `report.json` + `warnings.tsv`, `summary.tsv`. Tests:
zero network, zero credential reads, no FactStore or reconciler mutation;
mismatch exits 0, `--warn-exit` 1; unreadable gold 3; store refusal 2; values
absent from the report without the flag; repeated run byte-identical except run
metadata. The MANDATORY offline gate is synthetic: a three-source fixture run
plus the seeded-mutation detection matrix. Then the ORCHESTRATOR replays the
nine retained gold+Screener stocks offline as an explicitly PARTIAL two-source
measurement (XBRL↔Screener), hand-labels every tier-1 mismatch, and records base
rate and coverage in a new `docs/research/three-source-first-measurement.md`;
the Tijori pair is measured only after OWNER 1.

## 6 Migration of existing `data/raw` layouts

Cut-over, legacy untouched: only `tijori-tables` moves this phase; Screener
financials keeps its verified-hash, meta-last layout; Upstox moves under f2m.
No bulk rewrite, no re-hashing of retained bodies, no manufactured bodies for
model-only Tijori artifacts. *Rejected:* in-place conversion (rewrites readers
and provenance, cannot recover bodies never retained); legacy-reading adapter
(permanent maintenance of eight layouts).

## 7 Risks, ranked (silent corruption first)

1. Semantic collapse — a plausible row mapped to the wrong profit definition,
   basis, period or unit yields convincing false agreement. Guards: section-
   qualified selectors, `means` + exclusions per entry, both net-profit
   candidates until measured, key compatibility refuses, no reconstruction.
2. A shell page committed as OK — outcome sealed after identity gates (S3 test).
3. Precision inflation — spine without decimals refused; `DEFAULT_MAX_TOLERANCE`
   cap → NOT_COMPARABLE; `relative_difference` on every row from day one.
4. Partial commit — body first, record last, read-back verify.
5. Vendor agreement read as confirmation — package rail + no vote in `verify/`.
6. Report as export — values behind a flag, output under `data/` (gitignored).

## 8 Out of scope

Series versions (f2m); parse-level outcome mapping and the capability registry
(kx4.5); FactStore loading for watchlist stocks (new bead); Screener financials
and Upstox persistence cut-over (f2m / later); knowledge-time cutoff C-15;
export/MCP; scheduling; bank-format map (eqos-hvh); relative tier-2 triage
floor (eqos-ya6); Lane B itself is not modified.

## 9 Owner decisions (taken 2026-09-05)

OWNER 1 — DECIDED: manual `tijori-tables` acquisition approved. Tijori replay data: no Tijori tables are retained on disk today (0
files under `data/raw` match `tijori`). S6's Tijori base rate needs one manual,
operator-triggered `tijori-tables` acquisition for the 10 watchlist stocks after
S3 ships (sequential, spaced, stop-on-429). Approve, or accept an XBRL↔Screener-
only first measurement.
OWNER 2 — DECIDED: `NOT_OFFERED` for `BASIS_UNAVAILABLE` confirmed (Q4 dissent recorded).
OWNER 3 — DECIDED (confirmed): net-profit concept: both candidates stay until the replay decides.
Confirm that the replay, not an admission, fixes the map.
OWNER 4 — DECIDED (confirmed): regenerating the local gold files with `decimals` runs the existing
FIXTURE path over cached raw (the `report` command's route; no network).
Confirm the local gold set may be regenerated (values unchanged, one optional
field added, no schema bump). NETWEB has no gold file and no cached raw; it is
excluded from the first measurement.
