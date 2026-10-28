# Lane 2 — first-party PDF extraction diagnosis

Lane 2 diagnosis by gpt-6.1-sol (2026-10-28), read-only. Its evidence stays in the gitignored `scratchpad/lane2/`. The LIVE-RUN-1 impact statements are inferred from the code, not observed.

Read-only diagnosis, 2026-10-28. Inspected checkout HEAD: `7b77d2d8c562b816cd7fc72e0a5c17ddd33d8491`.

**Observed** means reproduced locally from retained bytes or read directly in current source/artifacts. **Inferred** means a consequence of those observations; proposed fixes have not been implemented. Historical bead descriptions are distinguished from current reproduction.

## Scope, inputs and verification boundary

- Read lane 2 in `docs/plans/2026-10-28-parallel-sol-lanes.md` first, then all four beads with `bd show`.
- Resolved PDFs through `config/aparinds-fy26-q2.yaml`, `config/aparinds-fy26-q3.yaml`, `config/aparinds-fy26-q4-pg.yaml`, and `config/aparinds-fy27-q1-pg.yaml`. Also checked plain `aparinds-fy27-q1.yaml`, which LIVE-RUN-1 names. Only Q4 and Q1 have `-pg` config files.
- Independently matched every results PDF's SHA-256 to both its config and `data/raw/watchlist/aparinds/retrieval-manifest.json`: Q2 `8be1b8de71997d30f2dccd78cfc42d87c5564e2ab16357ca611763c1f3784ae5`; Q3 `2f9c6d5a0c1d6394276602c97a08bd1624ea5e61197a57a1d95d260db6383699`; Q4 `17f5bc047416a795ecdf8c9be5c09ff1699d00cb2feed885bf2a2e43a2d4a377`; Q1 `c0c2b2fa5510a776331c2092f03301c65dbea5a98ee42ecbc31f768513278612`.
- Ran production `load_pdf`, `verify_pdf_framework`, `specs_from_config`, `locate_statement`, `extract_statement_rows`, `selector_matches`, `header_period`, and `parse_printed_number` in process. Read corresponding retained XBRLs structurally with lxml. Rendered source PDF crops locally and inspected the employee cell and Q1 segment page.
- Loaded `.env` into each extraction shell without printing it. No PostgreSQL connection, network, test suite, Beads write, Git write, permission change, forbidden path, or production-code/config edit. All created files are under `scratchpad/lane2/`. Tests below are descriptions only.

Reproduction: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scratchpad/lane2/diagnose.py`, followed by `evidence.py` and `focused.py` in the same directory, after sourcing `.env`. Successful script runs exited 0. `extraction.json` contains production-parser rows and locations; `focused.log` contains concise hypothesis checks; `evidence.log` includes raw XML values and headers. One initial diagnostic import used the wrong module for `AccountingFramework`; the scratch script was corrected before the successful runs.

## Common adoption and LIVE-RUN-1 constraints

The current PDF extractor is `pdf-occurrences/4` (`src/fundamentals/evidence/pdf_adapter.py:52`). Its pin covers the adapter, statement parser, identity reader and PDF loader (`src/fundamentals/compare/run_config.py:66`). Preserve that implementation and existing config bytes. Parser fixes belong in a versioned successor implementing the named seam, with a new extractor identity/source digest; `/5` is a proposed successor name, not a version created here. Multiple fixes can share one reviewed successor release.

A new issuer config that changes emitted units also changes occurrences. Existing `/4` occurrences cannot simply be reused: `src/fundamentals/evidence/first_party_extract.py:358` compares complete payloads and explicitly requires an extractor bump on drift. Thus the Q1 unit-config correction needs a new extraction generation as well as a new config filename.

Adopt parser/config fixes by selecting the successor adapter in the ingestion/comparison release, ingesting the same retained capture with the new issuer config and extractor identity, and creating a new comparison run. There is currently no CLI `--extractor` switch: ingestion has an API `extractor_versions` parameter (`src/fundamentals/evidence/first_party_ingest.py:150`), while CLI/default version dispatch must be wired to the successor implementation. Merely relabelling unchanged or changed code with another version string is insufficient.

For mapping fixes, use a new PDF entry file and mapping-set index, replacing the old member in the new set rather than loading overlapping definitions together. `evidence ingest` exposes `--dictionary` / `--mapping-set` / `--issuer-config` (`src/fundamentals/api/evidence_cli.py:111`); `compare run` additionally exposes `--normalisation-policy` (`src/fundamentals/api/compare_cli.py:149`). Do not rewrite prior interpretations or run manifests.

**LIVE-RUN-1 assessment is source-based inference, not production acceptance.** The plan assigns comparison runs 1, 2, 3, 4 to FY26_Q2, Q3, Q4, FY27_Q1 respectively (`docs/plans/LIVE-RUN-1-prerequisites.md:589`). Those IDs and recorded open-HIGH counts come from its 2026-10-27 probe, not a DB query in this diagnosis. The current runner requires the exact `PILOT_VERSIONS` pins, dictionary v2 / mapping v6 / alignment v2 (`src/fundamentals/api/cli.py:139`, `:460`). It admits six required roles only (`:529`; `src/fundamentals/output/earnings_update.py:52`); segments, employee expense and current-tax components are outside that required set. Filed total tax for ETR/F5 comes from XBRL (`src/fundamentals/api/pipeline_steps.py:185`; LIVE-RUN-1 plan `:685`). Consequently these defects affect the comparison evidence but do not, by themselves, establish a blocker to the specified four drafts. New mapping/parser comparisons require an explicit pilot-pin upgrade before the runner can consume them; substituting a new run ID alone will not work.

## eqos-ghv — historical identity rejection; current segment units remain unsupported

### Root cause and retained structure

**Observed:** the issue's original framework rejection is repaired on this checkout. The only matching Q1 framework declaration is on PDF page 7, in the auditor report, with the phrase structure `prepared … applicable Indian Accounting Standards`. The old vocabulary lacked the `applicable` variant. Current `FRAMEWORK_DECLARATIONS` includes it (`src/fundamentals/evidence/member_identity.py:44`), and `verify_pdf_framework` scans every page (`:242`). Replaying the old vocabulary in memory produces exactly `the capture declares no accounting framework`; restoring the current vocabulary verifies page 7 (`scratchpad/lane2/focused.log:1`). Git commit `b4a804bc` independently records the phrase addition and PDF version `/4`.

An identity/framework rejection returns before block reading (`src/fundamentals/evidence/first_party_extract.py:445`). The package then emits generic family-not-located attempts for families absent from `pdf_located` (`:143`). **Inference:** those messages can be downstream consequences of rejected identity, not proof that page discovery independently failed. I could not reproduce the bead's remaining SEGMENT-location claim: with either Q1 config, current defaults locate P&L page 3 and SEGMENT page 4, each with four consolidated columns (`focused.log:3`). Page 4 contains a segment title, a consolidated super-header and inter-segment asset text, satisfying the actual default predicates (`src/fundamentals/extract/pdf_statement_pages.py:269`, `:405`). No new block marker is justified by this reproduction.

**Observed residual:** page 3's hidden unit text is `Ra.in crones`; page 4's is `Rs. in rrores`, although the rendered table uses crore units. `config/aparinds-fy27-q1-pg.yaml:63` declares only the P&L variant. Page 4's rows therefore have `unit=None`. Exact marker resolution (`src/fundamentals/extract/pdf_statement_pages.py:757`) emits empty raw unit / scale 0 (`src/fundamentals/evidence/pdf_adapter.py:199`), and matching monetary rows become `INVALID/UNIT_MISMATCH` (`src/fundamentals/evidence/interpret.py:238`). An in-memory exact SEGMENT unit declaration produces INR / scale 7 without changing discovery (`focused.log:5`).

**Classification:** historical parser-vocabulary omission, already repaired; remaining issuer-config omission caused by a damaged source text layer. It is not currently a reproducible block-location bug.

### Smallest fix and adoption

Keep the existing framework repair. Publish a **new Q1 issuer-config version** retaining the P&L marker and adding `statement_pages.SEGMENT.unit_markers` for exact `Rs. in rrores`, PAGE / INR / scale 7 / CURRENCY_AMOUNT. Use it in a **new PDF extractor generation**, for the payload-reuse reason above. No fuzzy marker matching or discovery fallback is needed.

This resolves the missing-unit defect, not every segment defect. `eqos-djv` below also affects this page. Additionally, the annual header's hidden text reads `Mar 31, 2020`, while the page image prints 2026; `header_period` consequently gives FY20 for that column (`scratchpad/lane2/evidence.log`, Q1 headers). That source-layer defect needs source-image header recovery in the successor parser, not an inferred six-year date adjustment. Do not declare full Q1 segment correctness after adding the unit marker alone.

### Blast radius and LIVE-RUN-1

Historical framework rejection affects Q1 packages under the old vocabulary, not other retained quarters, all of which currently verify their own declaration. Current missing SEGMENT units affect all 35 extracted rows × 4 columns of the Q1 PDF, including current and comparative columns. The plain Q1 config also lacks the P&L marker; `-pg` fixes that P&L unit case. The corresponding comparison package is run 4 in LIVE-RUN-1. Existing repaired six-role evidence is usable according to the plan; the unresolved segment defects do not supply required headline roles. Fresh occurrence ingestion using the plain config is not equivalent to the repaired `-pg` ingestion. The draft pipeline itself uses the separate P&L observation path (`src/fundamentals/api/pipeline.py:306`), so do not infer a new draft failure solely from this occurrence-config difference.

### One regression test to implement later

With the hash-pinned Q1 PDF and successor issuer config, verify framework admission, locate page-4 consolidated revenue rows and assert that the current Conductors cell `3,338.13` has INR / scale 7 and the June-2026 quarter period. It fails now because unit is absent; it should pass after the exact config correction under the new extraction generation. Keep annual-header correctness as a separate acceptance assertion before claiming the entire segment table repaired.

## eqos-djv — results heading fails recognition and leaks the previous section

### Root cause and retained structure

**Observed:** page 4 has one revenue section, a four-row segment-name list, then a results heading and the same four names again. Five columns in Q4 cover three quarters and two fiscal years. Conductors is `3,764.18` under revenue and `276.29` under results for the current quarter.

The parser recognizes only the Q2 heading variant containing the OCR spelling `bofore` and ending in `of` (`src/fundamentals/extract/pdf_statement_pages.py:87`). The Q4 band at line 18 instead has `before`, and Q3 additionally has `(toss)` where Q2 has `(loss)`; Q1's band ends before the trailing `of`. Since section headings require full normalized equality (`:352`), none changes the section state. The four results rows inherit `section="Segment revenue"` (`:378`). This is then faithfully copied into occurrence context (`src/fundamentals/evidence/pdf_adapter.py:209`).

The mapping already requires `section_equals: Segment revenue` for all four revenue entries (`config/mappings/pdf/v2/results_layout.yaml:419`), and selector matching obeys that condition (`src/fundamentals/evidence/mapping_models.py:317`). Thus **the primary root cause is parser section recognition, not absence of a section condition in the mapping**. Adding another revenue predicate without repairing the section state misses the cause.

Local replay reproduces 4 × 5 = **20 duplicated candidate keys / 40 revenue-selected cells** for Q4 (`focused.log:54`). The retained cutover CSV confirms actual mapped readings on both rows, preserved as `MULTIPLE_FRESH` (`data/cutover/run-20261020T122425Z/diff/diff.csv`, `canonical_id=segment_revenue`, `quarter=FY26_Q4`).

**Classification:** parser bug triggered by exact, layout-specific heading variants in the source text layer.

### Smallest fix and adoption

In a **new PDF parser version**, at the successor of `_SECTION_HEADINGS` / `extract_statement_rows`, recognize the three observed additional complete heading bands as results headings. Exact variants are enough; no guessed section boundary or general fuzzy matcher is needed. Preserve source heading text as section evidence. Once the results section is established, the existing revenue mappings cease matching those four profit rows.

That parser-only change fixes erroneous revenue assignment. Mapping the now correctly separated rows to `segment_result` is an additional **new PDF mapping entry/version** if desired, not a prerequisite for removing false revenue. Existing dictionary v2 already defines `segment_result` (`config/dictionary/v2/segment.yaml:24`). Do not append competing entries to frozen pdf/v2, or replace its revenue rows with label ordinals as a substitute for recognizing the heading.

### Blast radius and LIVE-RUN-1

Q2's original heading is recognized: 24 revenue cells, no duplicate candidates. The defect also reproduces in Q3: 24 candidate keys / 48 cells, and Q1: 16 / 32 (`focused.log:41`, `:68`). Q3 and Q1 segment units are missing, so these are selector-level contamination counts, not claims of 48/32 valid persisted monetary interpretations. Q4 has valid crore units and the confirmed 40 mapped readings. All printed periods inside each affected package are exposed, not just its current quarter. These correspond to LIVE-RUN-1 comparison runs 2–4; none supplies required headline roles, so this alone is not a predicted draft-admission blocker. The existing cutover diff remains historical evidence; do not overwrite it after re-extraction.

### One regression test to implement later

Extract and map the retained Q4 page 4 under the successor parser with existing revenue selectors. Assert exactly 20 revenue-selected cells, exactly one candidate for every segment/period, with Conductors current revenue `3,764.18`; assert its `276.29` results cell is outside the revenue section and cannot match a revenue entry. It currently returns 40 cells and fails that assertion. This tests the section boundary, not an ordinal workaround.

## eqos-n21 — the decimal is missing from the source text layer, not stripped by our parser

### Root cause and retained structure

**Observed:** Q4 PDF page 3, consolidated employee-benefits row, annual FY26 column. The rendered cell reads `427.87`; PyMuPDF's positioned word is already `42787` at approximately x=277.74–295.18, y=243.51–250.38 points. See `scratchpad/lane2/FY26_Q4-employee-cell.png` and `FY26_Q4-employee-row.png`. This demonstrates the decimal is lost before our row/number parsing.

`_extract_page` copies `page.get_text("words")` directly (`src/fundamentals/ingest/pdf_source.py:119`); row extraction joins those word texts (`src/fundamentals/extract/pdf_statement_pages.py:342`). `parse_printed_number` accepts the supplied integer and records 0 decimal places (`src/fundamentals/evidence/pdf_adapter.py:95`); it does not remove a point. Normalization then scales 42787 by 10^7 (`src/fundamentals/evidence/interpret.py:708`). The employee mapping is the correct labelled row (`config/mappings/pdf/v2/results_layout.yaml:56`). Retained Q4 XBRL `EmployeeBenefitExpense@FourD` is INR 4,278,700,000 = 427.87 crore. The Q1 PDF's annual comparative independently supplies `427.87`, while its Q4-quarter comparative supplies `114.26` correctly.

**Classification:** source OCR/text-layer defect plus absence of image recovery in the occurrence parser. Neither a mapping bug nor a decimal-grammar bug.

### Smallest fix and adoption

A **new PDF parser version** must read the printed numeric cell from the retained page image for this scanned layout, rather than treating a syntactically valid hidden-text integer as authoritative. Land recovery at the successor PDF-loading/cell-extraction seam feeding `pdf_adapter._occurrence`; retain page/column/cell geometry, original hidden text, image-recovered text and recovery provenance. Reuse the local `OcrEngine` port (`src/fundamentals/ingest/ocr_engine.py:58`) and existing rasterization pattern in `extract/pdf_ocr_recovery.py`, rather than creating a second OCR framework.

Recovery must apply to the declared scanned numeric region even when hidden text parses successfully: a parse-failure-only fallback will never visit `42787`. The existing OCR lane is a quarterly P&L target-line extractor, not a lossless annual occurrence adapter, so merely enabling that lane is insufficient. Do not divide large integers by 100, change crore scale, inject the XBRL value, or put a cell-specific amount in mapping config. No image-recognition engine was run in this diagnosis; the proposed recovery's accuracy remains to be tested.

### Blast radius and LIVE-RUN-1

Observed corruption is one FY26 annual cell in the Q4 package, plus annual `employee_cost_pct`, whose formula divides employee expense by revenue (`config/dictionary/v2/derived.yaml:246`). This produces approximately 186.83% instead of 1.87%. Other four employee cells in that table are parsed with two decimals; the current-quarter cell is 114.26, not 42787 (`focused.log:59`). Generic exposure extends to other damaged hidden-text numbers, but this diagnosis does not assert their count.

The corresponding comparison is LIVE-RUN-1 run 3; the plan records employee expense and employee-cost-ratio HIGH disagreements (`docs/plans/LIVE-RUN-1-prerequisites.md:112`). Neither annual diagnostic is a required current-quarter headline role. Q1's PDF has the correct annual comparative, so source-specific corruption should not be generalized to run 4. Existing comparisons remain affected until a separately versioned re-extraction/run is adopted.

### One regression test to implement later

Run the successor occurrence extractor on the retained Q4 PDF, bind exactly page 3 / employee-benefits / FY26 annual consolidated column, and assert normalized INR 4,278,700,000 with printed precision 2 and an image-recovery anchor. Verify the current-quarter cell remains INR 1,142,600,000. It currently emits INR 427,870,000,000 / precision 0 for the annual cell. Use the retained image, not a mocked pre-corrected string.

### Additional discrepancies explicitly named in this bead

**Observed, separate causes:** Q2 page 6 correctly extracts `Other intangible assets` 1.73 and `Other noncurrent assets` 191.99 from their own rows. The XBRL composites are exactly PDF **106.73 ROU + 1.73 = 108.46**, and **43.22 non-current tax assets + 191.99 = 235.21** (`focused.log:16`, `:28`). Goodwill is 0; it is not the missing component. The same aggregate relationships hold in the PDF's March-2025 comparative: 106.46 + 1.92 = 108.38 and 26.01 + 114.26 = 140.27; the observed PDF components establish the structure, while this run's XBRL only supplies the current instant.

The current dictionary explicitly acknowledges ROU folding but still pairs the broader XBRL and narrower PDF under `other_intangible_assets` (`config/dictionary/v2/balance_sheet.yaml:21`); `other_noncurrent_assets` has the same mismatch (`:47`). The corresponding XBRL entry evidence already documents both folds (`config/mappings/xbrl/v1/in_capmkt.yaml:169`, `:209`). These are **mapping/dictionary semantic mismatches caused by filer aggregation**, not OCR or wrong-row extraction.

The smallest semantic repair is a **new mapping/dictionary version** distinguishing each native component from each aggregate, then source-scoped PDF constructions adding ROU and non-current tax assets to their respective totals (or explicit alignment between the distinct measures). Do not relabel the narrow PDF cells as the broader totals. Run 1's balance-sheet comparison is affected, independently of the annual decimal bug; these measures are not required LIVE-RUN-1 headline inputs. Q4 also exposes the intangible aggregate relationship (104.22 ROU + visually printed 4.48 = XBRL 108.70); its hidden `4,48` is a separate OCR defect, so fixing definitions alone is not a complete Q4 balance-sheet repair.

## eqos-dol — PDF and XBRL current-tax definitions differ

### Root cause and retained structure

**Observed:** page-3 tax tables have three separate component rows: (a) current tax, (b) deferred tax, (c) earlier-years current tax. There is no printed total-tax cell. XBRL `CurrentTax` includes (a)+(c), whereas PDF mapping `pdf.current_tax` emits only (a) (`config/mappings/pdf/v2/results_layout.yaml:101`). The dictionary even records this inconsistency (`config/dictionary/v2/pl.yaml:62`). Row (c) already maps to `tax_earlier_years` (`results_layout.yaml:111`); adding that ID again cannot fix the comparison.

Retained values, crore; signs below follow the printed parentheses:

| Package/column | PDF (a) | PDF (c) | (a)+(c) | Retained XBRL CurrentTax |
|---|---:|---:|---:|---:|
| FY26_Q3 quarter | 74.31 | +1.69 | 76.00 | 76.00 |
| FY26_Q3 nine months | 253.33 | +1.69 | 255.02 | 255.02 |
| FY26_Q4 quarter | 88.84 | -8.58 | 80.26 | 80.26 |
| FY26_Q4 full year | 342.17 | -6.89 | 335.28 | 335.28 |

See `focused.log:43` and `:56`; XBRL values are read from `OneD` / `FourD`, not inferred from a residual. Q4's 8.58 is a **credit**, not a positive adjustment.

The claim “DISAGREE every quarter” is too broad. Under mapping v6/pdf-v2, Q2's three tax rows are **unmapped** because the parser assigns section `10 Tax exp` but selectors require `Expenses` (`results_layout.yaml:105`; `focused.log:13`). Q2's current-period earlier-years value is a dash, so after lawful zero handling (a) already agrees. Q1's current (a) is 182.12, exactly its XBRL CurrentTax; its (c) hidden cell is `.`, not a parsed zero. Older comparable columns with nonzero (c) retain the definition mismatch, but the current Q1 cell does not exhibit the stated numerical disagreement.

**Classification:** config/mapping and dictionary-definition bug, triggered by legitimate source presentation differences. The comparison engine is correctly flagging unequal numbers presented as one canonical measure.

### Smallest fix and adoption

Publish a **new dictionary version**, **new PDF mapping version**, and **new source-scoped construction version**. Define a narrow `current_tax_excluding_prior_years` row for PDF (a), retain existing `tax_earlier_years` for (c), and construct the inclusive canonical `current_tax = (a)+(c)` with signed amounts. Clarify that inclusive definition in the new dictionary. Existing versions v2/v3 of the dictionary and pdf/v2 are frozen; use new version directories/files rather than changing them.

The new mapping must also recognize both evidenced tax sections (`Expenses` and `10 Tax exp`), so Q2 operands are available. Give (a) a new mapping-entry identity and update the successor of `pdf.tax_expense` to use that narrow entry: **total tax remains (a)+(b)+(c)**. Otherwise adding (c) to current tax and then reusing the old three-term total double-counts earlier-years tax. Existing construction is at `config/mappings/constructions/v1.yaml:33`; the loader forbids a direct entry and construction emitting the same canonical measurement (`src/fundamentals/evidence/mapping.py:517`), so the new set must replace, not append to, the old direct-current-tax definition.

For dash periods, add a **new normalisation-policy version** containing a construction-scoped zero rule for the new current-tax construction. The existing rule applies only to `pdf.tax_expense` (`config/normalisation_policy/v1.yaml:29`; `src/fundamentals/evidence/interpret.py:494`). A dot or blank is not that dash and must be recovered from its source image before claiming a value; do not globally interpret it as zero.

Adoption uses new dictionary/mapping/policy pins with the same raw occurrences; a new parser is not required for the four demonstrated nonzero adjustments. The CLI ingest path currently hardcodes normalisation v1 (`src/fundamentals/api/evidence_cli.py:66`, `:155`), so adoption of the new dash policy requires the reviewed CLI policy selection/default change or direct ingestion API with the new policy. `compare run` can explicitly select it. This is a real adoption dependency, not an existing ingest flag.

### Blast radius and LIVE-RUN-1

Confirmed current/YTD false comparisons are Q3/run 2 and Q4/run 3, plus any mapped comparative columns where (c) is nonzero. Q2/run 1 has the separate tax-selector coverage defect; Q1/run 4 has no current-tax numerical mismatch in its current quarter, although comparative cells remain exposed and unreadable (c) blocks some constructions. With mapping pdf/v1, Q2 used the older tax mapping; pin-specific behavior must not be conflated with v6/pdf-v2.

LIVE-RUN-1's existing component HIGH items remain visible. They do not alone prevent six-role admission. The filed total-tax/ETR/F5 path reads XBRL `TaxExpense`, which is already 79.15 for Q3 and 75.48 for Q4, not PDF (a). Therefore this component-definition fix should not change those filed totals or falsifier arithmetic. Any total-tax change after the mapping update would require explanation, especially a change caused by double counting (c).

### One regression test to implement later

For the retained Q4 consolidated quarter and FY26 annual columns, interpret source-scoped (a)/(b)/(c) and construct inclusive current tax under the new dictionary/mapping. Assert 80.26 / 335.28 crore and AGREE with the corresponding XBRL CurrentTax, while total tax stays 75.48 / 333.07 crore. The current mapping yields 88.84 / 342.17 for current tax and fails. This single retained-package case covers signed earlier-years credits and catches accidental double counting in total tax.

## Outcome

All four requested diagnoses are complete at the local source/extraction boundary. No fixes or tests were written to production paths. Production run state and future parser/OCR effectiveness were not verified. The smallest next implementation is a versioned PDF parser/config release for heading/unit/image recovery, plus a separately pinned semantic mapping/dictionary/policy release for tax and the identified balance-sheet aggregates; existing LIVE-RUN-1 pins remain unchanged until an explicit upgrade.
