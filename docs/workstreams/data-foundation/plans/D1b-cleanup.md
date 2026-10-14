# D1b cleanup plan: delete the scaffolding, keep the minimum

Status: **approved** — gpt-6.1-sol (high), verdict APPROVE on r3, 2026-10-14 (after r1: 19 findings,
r2: 4 more). Implementation notes from the approval: G2 needs a persistent, FK-backed
construction-to-trace link (`Interpretation` has no trace-id field and result values forbid carrying
both interpretation and trace ids; choose the smallest compatible representation); exercise the lock
order through `RunStore.publish`, not only direct queue publication. Owner directive 2026-10-14: crisp, minimal code; delete what is not needed and
write the smallest solution that meets the spec.

## Why

The Codex D1b run (commits after `22a3c78`) added about 14,000 source, 1,215 SQL and 16,100 test
lines. These counts are added lines before deletions. The run accepted only one D1b stage: D1b.4,
a document. Two necessity audits (Opus, 2026-10-14) judged each file against the data spec, the
core roadmap's D1b rows, the invariants and the testing policy. Codex's own plans and sub-tasks did
not count as requirements.

- **Most of the code has no requirement behind it.** It builds a threat model the spec does not
  have:
  - Callers hand runs "handoffs" and "generations". The code re-derives each one, compares,
    reloads it by id and compares again.
  - Config "publication" is checked against git history at load time.
  - "Witnesses" re-prove inputs that the run manifest already pins.
- **Requirements are still unmet:**
  - D1b.1: the Tijori and Upstox adapters are placeholders with no mappings, and `test_evidence_vendor.py` covers almost none of its Verify cell.
  - D1b.3: there are no queue commands, the report shows no queue items or trust, and first-party-only runs never route items to the queue.
  - D1b.3: some Verify behaviour has tests (queue reuse/link; failure → `INCOMPLETE` → `UNAVAILABLE` on replay), but only over constructed fixtures, not in the named Verify file.
- **One invariant breach.** Migration `0006:83-98` disables the append-only trigger and updates
  stored `result_source_values`.
- **One false premise.** Tijori was declared "unavailable", but
  `data/raw/snapshots/v1/tijori/financials/` holds 10 authenticated captures (2026-09-05, HTTP 200).
  Upstox statement bodies really are absent.

**Database state.** On 2026-10-14 I checked the real `equity_os` database with a read-only query.
It has only the `public` schema: no `eqos` schema and no `eqos_meta.schema_migrations`. No
migration has ever been applied there. Only disposable `eqos_test_*` databases hold `0001`–`0010`,
and no stored history needs preserving. So migrations `0006`–`0010` can be **rewritten**, not
dropped by a new migration.

## Target design (spec §3–§5, component boundaries)

1. **Source authority** lives in `contracts/source_catalog.py`.
   - One small declaration per allowed `(source, surface)` holds its role (`INDEPENDENT_VENDOR` or `DIAGNOSTIC`) and its retention authority (spec §3).
   - Upstox is registered as diagnostic-only.
   - An unregistered surface gives `NOT_AUTHORISED` before capture or interpretation.
   - There is no separate content-pinned authority artifact.
2. **Vendor ingest is an evidence-side step,** like first-party ingest. It lives in
   `evidence/vendor_ingest.py`:
   - Check authority (point 1).
   - Read the registered capture from the snapshot store, once.
   - Extract with a thin surface adapter (`vendor_screener`, `vendor_tijori`, `vendor_upstox`) over
     the existing `ingest/` parsers.
   - Interpret with the existing `interpret_generation`.
   - Store the attempt, occurrences and interpretations.
   - A missing or failed capture becomes one capture-less `ACQUISITION` attempt row.
   - Clocks (spec §4): publication time is stored as evidenced, or `UNKNOWN`. When it is unknown,
     the verified capture-registration time is the availability boundary for eligibility. These are
     two separate fields, as `vendor_screener.py` stores them today. A test asserts both the stored
     clock status and the eligibility.
3. **Runs keep `RunRequest`** (cutoff, mode, pins, code version) and drop the handoff arguments.
   - Vendor selection in `RunScope.sources` is plain `(source, surface)` entries.
   - The CLI wires those entries and the vendor mapping set.
   - Runs read stored vendor and first-party rows by scope and cutoff.
4. **`compare/vendor_sides.py`** builds the vendor sides. Selection follows spec §4: the latest
   attempt decides, with no fallback. It builds:
   - (a) a corroboration pair for each independent vendor against first-party;
   - (b) diagnostic pairs from Upstox against first-party **and** against Screener;
   - (c) when extraction is not `AGREE`, vendor pairs against the other first-party representation;
   - (d) detection of contradictions between compatible surfaces of one vendor, giving `VENDOR_INTERNAL_CONFLICT`.
   
   It calls `corroboration_result` / `diagnostic_pair` and routes each pair as it is built.
5. **Queue.**
   - **Publishing (`queue.py`).** A routed item is published in the run transaction:
     - keyed by input hash;
     - an identical item is reused, a changed one links to its predecessor;
     - run membership is recorded.
   - **Item evidence.** Evidence references stay in the `queue_item_inputs` child table, with
     foreign keys to occurrences, interpretations and attempts (spec: foreign keys enforce every
     reference). A small seal trigger refuses an input row whose item was not created in the same
     transaction, so an item's evidence can never grow later.
   - **Visibility.** Queue publication, disposition writes and overlay-boundary creation take one
     shared transaction-level advisory lock **before the transaction's first `store_now()` call**.
     The clock caches its time per transaction, and run insertion precedes queue publication. The
     as-of overlay is then one query with a stable committed boundary.
   - **Dispositions** are recorded by a CLI command, with a server-owned timestamp. Role gating is D3's.
6. **Pins** are only the spec's manifest pins: dictionary, mapping set, extractors (including the
   vendor extractor), policies. There are no publication, receipt, authority or witness pins.
   - The serialized `PinnedVersions` and `RunScope` shapes for first-party-only runs must stay
     byte-identical to D1a's. Any serializer is reduced to omitting the new empty fields.
7. **One construction engine.** A v1 construction operand may be a mapping entry or a `Selector`.
   - It is restricted to additive constructions over one capture and one surface.
   - It reuses v1 normalisation and evaluation, and keeps operand provenance.
   - It writes a calculation trace through the existing D1a trace writer, with the same contract as
     derived formulas: formula version, operand interpretation ids, values, bounds, rounding policy
     and operand qualification evidence (spec §2). So the output is computed, shown as computed, and
     carries a `calculation_trace_id`. No exemption.
   - It covers Screener Borrowings + Other Liabilities → `liabilities_incl_nci`.

## Slices

Each group is one commit, with ruff, `mypy --strict`, the full `tests/fundamentals` suite and the
tracer green afterwards.

Between G1 and the D1b finish (below), vendor runs do not exist. Vendor-run tests whose assertions
are requirement-bearing (for example failure → `INCOMPLETE` → `UNAVAILABLE` on replay) move in G1
onto first-party fixtures where the behaviour is source-independent. The rest are rebuilt in the
D1b finish. First-party runs and D1a behaviour stay intact
throughout.

| # | Group | Implementer | Done when |
|---|---|---|---|
| G1 | **Delete the handoff/witness/publication stack and move the queue to the target design (one atomic group,** because the schema rewrite and the queue code depend on each other). See the G1 detail below. | Opus | Nothing imports the deleted modules; no runtime git call for publication or approval (commit recording in `compare_cli._code_version` stays); no DB-name branch in `src`; first-party manifests byte-identical; routing, corroboration and diagnostic assertions pass on the draft API; queue reuse/link/concurrency tests and one concurrent historical-reread overlay test pass; tracer green |
| G2 | **One construction engine.** Fold `native_construction.py` into v1 constructions with selector operands (design point 7). Drop the native analysis in `mapping*.py`. Replace the native tests with one parametrized retained test (detail below). | Opus | The parametrized test passes |
| G3 | **Config tidy.** Delete `config/mappings/constructions/v2.yaml` **and its entry in `config/mappings/v2.yaml`**, keeping the dictionary-derived `other_income_incl_exceptional` formula. Migrate or delete only the construction-specific assertions in `test_vendor_dictionary_bridge.py`, keeping the signed-arithmetic and missing/invalid formula assertions. Remove the stale "UNPUBLISHED DRAFT / Task 13" notes. | Sonnet | Grep is clean; bridge formula tests green |
| G4 | **Docs and tracker.** Mark superseded (one header line each): `plans/D1b.md`, `D1b-first-party-intake-witness.md`, `D1b-native-constructions.md`, `D1b-publication-repair.md`, `D1b-queue-visibility-repair.md`, `D1b-vendor-acquisition-repair.md`, `D1b-vendor-runs.md`. Fix the roadmap Progress prose. Close or supersede beads `eqos-u0u.9`–`.30` with reasons. Re-measure line counts. | Sonnet | `bd list --parent eqos-u0u` shows only D1b.1–.6 and real follow-ups |

**G1 detail.** One commit group, because the call sites interlock.

*Delete:*
- `evidence/`:
  - `retained_intake_*.py`, `first_party_generation.py`, `first_party_context.py`;
  - `vendor_config.py`, `vendor_config_files.py`, `vendor_publication_receipt.py`, `vendor_common.py`, `vendor_offline.py`.
- `compare/`:
  - `retained_intake_replay.py`;
  - `vendor_handoffs.py`, `vendor_handoff_attempts.py`, `vendor_resolution.py`, `vendor_inputs.py`, `vendor_input_proof.py`, `vendor_request.py`, `vendor_rows.py`, `vendor_row_evidence.py`.
- `config/vendor_publication/` and `config/source_authority/`.

*Revert or convert the consumers:*
- `first_party_ingest.py` goes back to its `22a3c78` shape.
- `resolve.py` loses its witness calls and `resolve_joined_inputs`.
- `repository.py` loses the witness enrichment, `pin_versions_guarded` and `uses_pool`, keeping `pin_versions()` working.
- `capture_intake.py` loses its witness import.
- `run.py` loses the handoff parameters and the `_is_test_database` / `allow_synthetic_vendor_config` switches.
- `run_config.py` loses its publication logic.
- `run_models.py` loses `VendorSurfaceRequest` and its imports.
- `run_store.py` loses `_validate_vendor_manifest` and the re-publish compare.
- `contracts/evidence.py` drops the authority and publication pins, keeping the serializer only as needed for design point 6.
- `canon/dictionary.read_bytes` goes.
- `vendor_screener.py`, `vendor_tijori.py` and `vendor_upstox.py` become plain bytes → occurrences functions, with authority from the catalog (design point 1).

*Tests:*
- Delete the tests and support files that cover only deleted code.
- Keep the schema-seeding support needed by the migrations as they stand after G1.

*Migrations:* rewrite them as one `0006_vendor_and_queue.sql` in this group; `0007`–`0010` are deleted. It contains:
- the widened representation CHECKs;
- nullable `source_id`/`surface` on result values and pins, with **no backfill**;
- source-qualified uniqueness for result values: `UNIQUE NULLS NOT DISTINCT (result_id, source_role, source_id, surface, representation)`, replacing 0001's three-column key;
- `pair_kind` widened to `CORROBORATION`/`DIAGNOSTIC`;
- operand selection widened to `VENDOR_CAPTURE`;
- the vendor-extractor pin;
- `queue_items`, `queue_item_inputs` (foreign keys plus the same-transaction seal), `queue_run_items` and `queue_dispositions` (no proposal or receipt columns);
- append-only and truncate triggers, the `store_now` time triggers;
- runtime `INSERT` grants on queue tables and dispositions.

*Verify:* a fresh `eqos_test_*` database migrates `0001`–`0006`, and the schema tests are green. One schema test stores two independent HTML vendors and two diagnostic surfaces in one run.

*Queue (same group):*
- Delete `approval_receipts.py` and `queue_overlay.py`.
- Shrink `queue.py` and `contracts/review_queue.py` to design point 5.
- Delete the legacy `corroboration_status` vendor branch. Keep the first-party behaviour that `engine.py:766` uses (rows 1/2/2a/5/7).
- Delete the non-draft routing API in the same commit that **moves the assertions** in `test_compare_corroboration.py` and `test_compare_diagnostic.py` (`route_pair`/`route_status`/`route_unmapped_occurrence`) onto the draft API.

**G2 detail.** The single parametrized retained test, on the THERMAX page, covers:
- the oracle value;
- a missing operand gives the construction's missing state;
- an invalid operand wins over a missing one;
- a duplicate operand gives ambiguity;
- an operand from another capture is refused;
- exact normalisation and interval;
- the computed label and the stored calculation trace (replayed);
- key compatibility and qualification-tier assertions kept from the native tests.

**Deletion guard.** A test may be deleted only if it covers deleted code **and** no requirement
rests on its assertions. A requirement-bearing assertion moves to the replacement code's test in
the same commit.

## After cleanup: finish D1b with the minimum

Same rules, one stage at a time, straight from the roadmap Verify cells.

1. **D1b.1:**
   - Build `evidence/vendor_ingest.py`.
   - Build real Tijori (~120 lines) and Upstox (~100 lines) adapters, with `config/mappings/tijori/` and `config/mappings/upstox/`.
   - Rewrite `test_evidence_vendor.py` as one parametrized integration test over retained captures, one case per Verify claim.
2. **D1b.2:**
   - Build `compare/vendor_sides.py` (design point 4).
   - Keep the 15-condition table test and the diagnostic tests.
   - Add stored-evidence tests for (b), (c) and (d).
3. **D1b.3:**
   - Route every run, first-party included.
   - Apply the open-HIGH exit status to every run.
   - Add `fundamentals compare queue list` / `queue dispose`, and show queue items and trust in the report.
   - Rewrite `test_compare_queue.py` to cover its Verify cell exactly.
4. **One `pg` vendor integration test** over retained Apar Screener + Tijori captures plus
   first-party. It covers:
   - CORROBORATION pairs;
   - the failed-vendor `UNAVAILABLE` / `INCOMPLETE` case;
   - replay.
5. **D1b.5 and D1b.6:** the frozen manifest, then the end-to-end test.

## Acceptance blockers (recorded, not worked around)

- **Upstox.** No retained Upstox statement captures exist yet. These cases need them:
  - D1b.1: the annual and empty-response cases;
  - D1b.2: the NETWEB/POLYCAB internal-conflict cases;
  - D1b.6: the diagnostic fixture.

  The owner's Analytics Token exists outside the repo, and `fundamentals upstox` is the existing
  acquisition CLI. D1b.1 acquires the needed statement captures through the snapshot store, as a
  live fetch the owner authorised on 2026-10-14. Until then, the synthetic decision-table tests stay
  and do not claim retained acceptance.
- **SONACOMS: dropped by the owner (2026-10-14).** Its retained XML lacks the framework declaration
  and original publication-time evidence. Stage 1 now covers Apar plus nine companies. The spec
  Success Criteria records this amendment.

## Expected size (audit estimates; re-measured in G4)

| | Codex delta (added lines) | Target |
|---|---|---|
| Source | ~14,000 | ~2,200, including working Tijori/Upstox code |
| SQL | ~1,215 | ~120 |
| Tests | ~16,100 | ~2,000 |

## Guards

- **Tracer.** `tests/fundamentals/test_compare_tracer.py` must keep the Apar values:
  - PBT 340.56 / 340.53 crore;
  - OPM 8.06%;
  - revenue 5,715.42 crore;
  - total expenses 5,402.29 crore;
  - profit 251.70 crore;
  - EPS 62.66.
- **D1a manifests** stay byte-identical.
- **Invariants unchanged:** exact `Fraction`, fail closed, no zero-fill, store clock.
