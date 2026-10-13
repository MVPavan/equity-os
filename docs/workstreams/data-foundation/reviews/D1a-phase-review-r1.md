# D1a phase-end review, round 1 — findings and status

Reviewer: gpt-6.1-sol (high), three areas, verdict REQUEST_CHANGES (2026-10-12). Copied from the local
review scratchpad so later sessions can resume. Cite a finding as `D1a-R1-<id>` (e.g. D1a-R1-A5).
The status column was set 2026-10-13 from the paused fix rounds; the code in the working tree is
the authority — verify each status before relying on it.

## Status at handoff (2026-10-13)

| Finding | Status |
|---|---|
| A1, A5, A6, A8, A13 | Fixed in the uncommitted working tree (A13 via new migration 0005) |
| A4 | Interpretation side fixed; selection side belongs to the Area B round |
| A7 | Partial: store refuses differing payloads; still needed — refuse duplicate fact ids in `xbrl_adapter.py`, plus a test |
| A2, A3, A9, A10, A11, A12, A14 | Not started |
| Area A extra | `mypy --strict` has 3 errors: `xbrl_parser.py:208`, `capture_interpretation.py:326`, `capture_interpretation.py:332` |
| C1–C11 | Partially edited in the working tree, no worker report — re-check each one |
| B1–B9 | Not started |

Rulings on A2 and A9: the PDF text layer gives no reliable heading-vs-blank-row signal. Take the
fail-closed reading (ambiguous attribution or ambiguous blank row → INVALID, never a neighbour's
value, never zero) and record the choice in the D1a plan build notes.

## Area A

```text
Round-1 dispositions: 12 RESOLVED; NOT RESOLVED 3 (=A5), 7 (=A9), 9 (=A10), 10 (=A8).

A1 member_identity.py:99, xbrl_parser.py:744: basis verification only checks context-bound report-nature facts, never compares the
   requested basis with instance.scope. Repro: strip contextRef from both report-nature declarations -> standalone request verifies.
   Fix: compare requested basis with the independently parsed scope AND require valid declaration evidence; else IDENTITY_REJECTED.
A2 config/mappings/pdf/v1/results_layout.yaml:135, pdf_statement_pages.py:328: owners-profit selector uses ordinal 1 with no section;
   removing the first owners row maps OCI owners 22.95 cr as profit attributable to owners (true 251.70). Fix: anchor these rows to
   their evidenced section/subtotal context; ambiguous attribution -> INVALID, never a neighbour's value.
A3 first_party_extract.py:314, ingest/pdf_source.py:151: PDF hashed then reopened by path -> parsed bytes may differ from hashed bytes.
   Fix: read bytes once, verify hash, parse that buffer (or the sealed capture blob).
A4 interpret.py:173: UNIT_MISMATCH interpretation has key=None, so selection returns NO_VALUE with no reason. INTERPRETATION SIDE
   (this round): an INVALID interpretation keeps every key part the evidence establishes (canonical id from the mapping entry, period,
   basis, framework, dimensions) and leaves unknown parts (currency/value_kind) null — never invent unit semantics. The selection-side
   change (treat a matching INVALID candidate as INVALID state) is done in the later Area B round — do NOT edit evidence/selection.py.
A5 interpret.py:139, capture_interpretation.py:260: runtime-ambiguous operand (mapping_entry_id=None) dropped by construction grouping ->
   construction MAPPED with operand NOT_PRESENTED. Fix: ambiguous/invalid operands make the construction INVALID (invalid beats missing).
A6 xbrl_parser.py:288, interpret.py:170: unit QNames kept as lexical prefix strings; rebinding iso4217 to a foreign URI still yields INR.
   Fix: resolve unit numerator/denominator QNames to (namespace URI, local name) and validate against the ISO 4217 / xbrli URIs.
A7 xbrl_adapter.py:109, repository.py:718: duplicate XBRL fact ids collapse distinct facts onto one occurrence. Fix: refuse duplicate
   anchors within a capture unless payloads are identical (then one occurrence); verify full payload equality on stored reuse.
A8 xbrl_parser.py:719, first_party_extract.py:284: malformed contexts (missing entity/period) raise AttributeError and escape with no
   attempt. Fix: validate structure; convert malformed-input failures to XbrlParseError -> one PARSE_FAILED attempt.
A9 pdf_statement_pages.py:323: a labelled row blank across both bases is treated as a heading and dropped (36->35 rows). Fix: keep
   labelled data rows whose label is in the statement's data-row region even if every cell is blank; blank cells -> absent/INVALID
   per existing dash/blank rules, never zero. Distinguish true headings by layout evidence, not by blankness.
A10 mapping.py:417: overlap check misses two "contains" predicates that can both match one string (Tax / exp vs "Tax exp"). Fix: treat
   two contains predicates on the same field as potentially overlapping unless provably disjoint (e.g. differing equality predicates);
   refuse at load when targets differ.
A11 first_party_extract.py:188/:135, xbrl_adapter.py:56: extraction reuse ignores inputs that decide outcomes. ORCHESTRATOR RULING:
   separate capture-only extraction (reusable by capture + extractor version + extractor content pin) from decisions that depend on
   mapping set, PDF statement specs or package context. Include the mapping-set version in the reuse identity of UNSUPPORTED_SCHEMA
   outcomes; include the statement-spec content hash in PDF location outcomes; recompute family (unlocated) failures for the package
   being assembled even when the generation is reused. Fail closed.
A12 first_party_ingest.py:149: extractor versions not content-pinned at ingest. Fix: pin extractor content (the existing extractor-hash
   function used by run_config) in eqos.version_pins at ingest, before reuse; drift -> VersionContentDriftError. Update the Stage 4a note.
A13 migrations/0004_monotonic_store_clock.sql:27: store_now() trusts a caller-settable GUC eqos.store_now_us. Fix in a NEW migration
   0005 (0004 is applied and checksum-locked — never edit it): CREATE OR REPLACE the function so per-transaction caching uses
   server-controlled state (e.g. compare the cached value's txid_current() / a temp table owned by the function's definer), never a
   value a runtime session can set. Test: a runtime session setting the GUC cannot move or freeze the clock.
A14 tests/fundamentals/test_pg_evidence_schema.py is 983 lines. Split by responsibility (bd chore exists; fix it here).
```

## Area B

```text
Sol verified: exact arithmetic/outward rounding; OPM 8.06% (2304550/285771) from PDF amounts; child traces before parent; 253 rows load.

Important
B1 selection.py:175 filters to the requested key before :134 removes superseded candidates. Repro: interp 1 maps an occurrence to
   revenue; same-pin MANUAL_CORRECTION interp 2 supersedes it and maps to other income; selecting revenue still returns interp 1.
   Fix: apply supersession across the eligible pinned generation before key filtering (spec §4, Task 6).
B2 selection.py:85 package eligibility ignores member knowledge-time status (occurrences at :53 require KNOWN). Repro: member status
   UNKNOWN with timestamps before cutoff -> package still selected. Fix: reject packages whose publication time is not evidenced
   (design decision 5; Stage 4b ruling).
B3 derived.py:224/:255 nested formulas reuse the parent's qualification context. Repro: quarter formula consumes net_current_assets
   via CLOSING; child scope limited to QUARTER; child output is INSTANT but trace records EQUIVALENCE_DEMONSTRATED. Fix: resolve
   period kind and condition evidence per nested output (spec §2; design decision 8; Task 7).
B4 derived.py:239 AVERAGE + dimensional aggregation crashes (ValueError: too many values to unpack). Fix: compose aggregation with
   averaging, or reject the combination at dictionary load (fail closed) — pick one, report which.
B5 derived.py:276 and :245 aggregation/averaging resolve constituents via _selected() only, bypassing nested formulas. Repro:
   aggregate of summable segment_capital_employed with only assets and liabilities reported -> OPERAND_MISSING. Fix: recursively
   evaluate derived constituents (with child traces) before aggregation or averaging.
B6 contracts/qualification.py:67/:163 EQUIVALENCE_DEMONSTRATED with zero fixtures, no sample rule, no conditions. Fix: require
   verifiable qualification evidence (spec §2, owner decision D3: fixtures across distinct companies + a discriminating case);
   otherwise the tier is not preserved. Filing-specific alignment proofs keep their separate exemption.
B7 Dictionary omits separately filed Apar measures: derivative assets/liabilities current and non-current (balance_sheet.yaml
   :38,:62,:92,:122 mention folded amounts); segment other elimination (segment.yaml:34) and inter-segment liabilities. PDF p6:
   non-current derivative assets 2.49 cr, current derivative assets 79.69 cr, non-current derivative liabilities dash (3.75
   comparative), current derivative liabilities 25.08 cr. PDF p4: other elimination 4.11 cr deducted; inter-segment liabilities
   656.59 cr deducted. Fix: add distinct rows (+ mappings where the source evidences them), update the manifest
   docs/specs/artifacts/dictionary-v1-manifest.md (rule 3) and row-count tests. Dictionary v1 is not yet frozen (frozen manifest is D1b's).

Minor
B8 canon/dictionary.py is 927 lines (> 800). Split validation into a focused module, no behaviour change.
B9 test_canon_formula.py:381 and derived.yaml:102 label 57,154.2 / 54,022.9 / 1,079.0 / 398.8 as crore; they are INR million
   (PDF p3: 5,715.42 / 5,402.29 / 107.90 / 39.88 crore). Fix units/labels and intermediate expectations.
```

## Area C

```text
All Important; none Critical. Sol confirmed: publication in one transaction; replay separates by-id reads from fresh resolution.

C1 engine_rows.py:252, resolve_loader.py:231: qualification condition proofs use every known interpretation triple, not the
   run-pinned current ones. Repro: older zero-valued interp proves a condition while the pinned one is INVALID ->
   EQUIVALENCE_DEMONSTRATED. Fix: select condition evidence under the same pins and revision rules as operands.
C2 engine.py:362, :625: formula rows select packages with statement family DERIVED, so a BALANCE_SHEET/PL correction falls back to
   the predecessor for formula context. Repro: Q3 BS correction -> current_assets_total applicable from pkg 11 but
   net_current_assets NOT_APPLICABLE via pkg 10. Fix: derive formula context from the operand statements' selected packages.
C3 engine.py:657, :760: runs use extraction_status for formula rows, never derived_extraction_status, and build no operand
   tagging adjustments. Repro: finance costs TAGGING_DIFFERENCE but derived opex DISAGREE, zero adjustments. Fix: wire the
   derived table into run evaluation, persisting adjustments (pair_adjustments).
C4 resolve_loader.py:156, engine_attempts.py:175: RunScope.sources recorded/hashed but never filters; package-less failures from
   other sources/surfaces impose UNAVAILABLE. Fix: enforce requested source bindings for packages, attempts and comparatives.
C5 run.py:112, run_config.py:209: execute_run holds a pool connection while pin_config/repository.pin_versions takes another ->
   PoolTimeout with a 1-connection pool; deadlock risk under concurrency. Fix: pin on the supplied connection (or release first).
C6 compare_cli.py:156, report.py:57: report loads the dictionary by version without checking its content hash against the manifest
   pin. Fix: verify the pin (VersionContentDriftError) before rendering.
C7 run_models.py:257, engine.py:194: row_id omits entity, so multi-entity runs fail. ORCHESTRATOR RULING: D1a/D1b runs are
   single-entity — RunScope must hold exactly one entity; refuse more at construction/CLI with a clear error. Record in build notes.
C8 compare_cli.py:100: expected config errors (ComparisonPolicyError, definition-set ValueError, malformed YAML) escape instead of
   exit 5 (RunExitStatus.FAILURE). Fix: catch the specific expected errors, not bare Exception.
C9 report.py:94, :115: reported lines omit interpretation_id and source anchor; failed sides omit attempt id; pair rendering drops
   reason, definition-record reference and adjustments; no epistemic labels. Fix: render these (invariants 7–8; spec §5).
C10 test_compare_tracer.py:155: revenue, total income, total expenses and EPS checked only for status, not value. Fix: assert the
   displayed values per representation as literals from the PDF (revenue 5,715.42; total expenses 5,402.29; EPS 62.66; total
   income from PDF p3 — read it from the source, do not copy code output).
C11 run.py:122, run_models.py:162: manifest operational_failures never populated. Fix: populate deterministically from the
   failures that decide the run's UNAVAILABLE states; replay must reproduce them.
```

