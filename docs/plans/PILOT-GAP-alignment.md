# PILOT-GAP-alignment Implementation Plan — six required roles qualify in PQ0–PQ3

**Bead:** `eqos-4j2.33` (blocks `eqos-4j2.24` Tasks 2–3). **Scope:** versioned PDF mapping, alignment
rules, one issuer config and one `compare run` flag, so that revenue, total income, total expenses,
PBT, PAT and basic EPS are `AGREE` and admitted in Q2 FY26, Q3 FY26, Q4 FY26 and Q1 FY27 (PQ0–PQ3).
**Out of scope:** `_decide`, `_qualified`, global qualification, the extractor, normalisation policy,
`evidence ingest` flags (owned by `eqos-4j2.24` Task 2), and fuzzy matching of any kind.
**Constraints:** existing issuer configs, v1 configs, mapping sets v1–v5, migrations 0001–0041 and the
frozen manifests (stage1, pilot) stay unchanged. Gates: `uv run pytest tests/fundamentals`,
`uv run mypy --strict src`, `uv run ruff check src tests/fundamentals` and
`uv run ruff format --check src tests/fundamentals`. Follow the owner's 2026-10-14 minimal-code rule.

Status: **approved — gpt-6.1-sol APPROVE, 2026-10-19** (r1 and r2 REQUEST_CHANGES → r3 APPROVE; fresh closing
review REQUEST_CHANGES 0/2/1 → closing re-review APPROVE).

## Origin

PILOT-GAP-admission r1 F2 left an old Task 0 that inferred refusals from labels. Sol's r2 found it
understated them (`scratchpad/execution/gap-admission/plan-r2-sol.md`, P2 F2): under the current config
all six roles fail in PQ1–PQ3, and PQ0 PBT fails. Ruling: move it into this plan under `eqos-4j2.33`.
Sol's carried conclusions: the existing alignment engine is enough; global qualification cannot help
(it needs five-company evidence); the sign of exceptional items is not a problem. Sol's r1 review of
this plan (`scratchpad/execution/gap-alignment/plan-r1-sol.md`) replaced the nil-exceptional and
nil-earlier-years identities. Its r2 (`plan-r2-sol.md`) put all four quarters on v6, replaced the
circular PBT identity with an evidenced layout rule and section-bound the expense proof; see the
last two sections.

## Probe (2026-10-19, no database)

All numbers below are printed by these scripts, which call production code only (`load_config`,
`compute_file_sha256`, `load_pdf`, `specs_from_config`, `read_pdf_occurrences`,
`read_xbrl_occurrences`, `interpret_generation`, `selects`, `load_mapping_set`,
`load_alignment_rules`, `alignment._interval`, `alignment._prove`, `Interval.intersects`). Each run is
`uv run --no-sync python -I scratchpad/gap-alignment/<script>`; `PQ3_PG=1` makes PQ3 read the
proposed `aparinds-fy27-q1-pg.yaml` (scratch copy). `make_v2.py` builds the proposed pdf/v2, v6 and
alignment/v2 under `scratchpad/gap-alignment/mappings/` (a copy of `config/mappings`). Outputs are
saved beside the scripts as `*.out`.

| Script | Shows |
|---|---|
| `probe1_values.py` (`probe1_v5.out`, `probe1_v6.out`) | each operand's PDF and XBRL interpretation: entry, status, reason, value, raw lexeme, label, section, unit |
| `probe2_unit_lines.py` | the PL page's unit-marker row tokens per quarter |
| `probe3_rows.py` (`probe3_v5.out`, `probe3_pq0_v5.out`) | every PL quarter-column row: page, line, label, section, raw lexeme, missing state |
| `probe4_align.py` (`probe4.out`) | v5→v6 hit diff in all four quarters, and each rule's computed and target intervals per representation |
| `probe5_section.py` (`probe5.out`) | `selects` on PQ1's `(a) Current tax` row with its section mutated |
| `probe6_a1.py` (`probe6.out`) | per operand under v6, whether the PDF and XBRL intervals intersect |
| `probe7_prove.py` (`probe7.out`) | under v6, production `_prove` over in-memory `KeySelection`s for every v1/v2 rule; the PBT layout evidence; anchor, position and expense-section negatives |

All four results-PDF pins match (`compute_file_sha256`): 8be1b8de (PQ0), 2f9c6d5a (PQ1), 17f5bc04
(PQ2), c0c2b2fa (PQ3).

## Findings

1. **Roles.** `REQUIRED_ROLES` (`output/earnings_update.py:52–59`) maps through `LEGACY_CONCEPTS`
   (`canon/role_translation.py:18–25`) to `revenue_from_operations`, `total_income`, `total_expenses`,
   `profit_before_tax`, `profit_for_period` and `eps_basic`.
2. **PQ3's PL unit is unrecognised.** Under `aparinds-fy27-q1.yaml` every PQ3 PL money row has
   `raw_unit ''` and interprets `INVALID`/`UNIT_MISMATCH` (`probe1_v5.out`). The PL page-3 unit row
   prints the words `(Ra.in`, `crones)`, tokens `['ra', 'in', 'crones']` (probe 2; `_marker_tokens("Ra.in
   crones")` gives the same tokens). With a PL `PAGE` marker `"Ra.in crones"` (raw unit `INR`, scale 7)
   in a scratch copy of the config, those rows carry `raw_unit 'INR'` and map (`probe3_v5.out`).
3. **Test ingestion is Q2-only.** `Ingest.intake` (`tests/fundamentals/evidence_support.py:124`) calls
   `apar_intake` without `issuer_config`, so the PDF pin check uses `aparinds-fy26-q2.yaml`;
   `apar_catalog()` (`tests/fundamentals/retained_support.py:183`) registers only the Q2 results PDF.
   `apar_intake` takes `issuer_config` (:208–239) and `Ingest.run` takes `catalog`, `mapping_set` and
   `pdf_specs` overrides. The retrieval manifest has exactly one `results` and one
   `xbrl-consolidated` entry for each of `FY26_Q2`, `FY26_Q3`, `FY26_Q4` and `FY27_Q1`.
4. **PQ1–PQ3 labels.** Rows the v5 PDF mapping misses, as printed (page 3; `probe3_v5.out`):

   | Line meaning | PQ1 2f9c6d5a | PQ2 17f5bc04 | PQ3 c0c2b2fa |
   |---|---|---|---|
   | other income | l17 `4 Other income` 15.31 | l16 same, 19.72 | l16 same, 33.65 |
   | 6(c) inventories | l22 `…stock-in-t` (mapped by v1) | l21 `…stock-in-trac` (301.32) | l21 `…stock-in-trac` (248.96) |
   | exceptional items | l31 `8 Exceptional items (refer note 3)` (24.99) | l30 same, (7.54) | l30 `8 Exceptional items (refer note 7)` `.` |
   | PBT before associates | l32 `9 Profit before tax & share in net profit / (loss) of associates (7` 288.09 | l31 `… (7.8)` 328.80 | l31 `… (7.8)` 622.34 |
   | associates | l33 `10 Share in net profit / (loss) of associates` (0.01) | l32 same, 0.12 | l32 same, 0.26 |
   | PBT incl. associates | l34 `11 Profit before tax (9+10)` 288.08 | l33 same, 328.92 | l33 same, 622.60 |
   | tax (a)/(b)/(c), section `Expenses` | l36–38 74.31 / 3.15 / 1.69 | l35–37 88.84 / (4.78) / (8.58) | l35–37 182.12 / (26.97) / `.` |
   | PAT | l39 `13 Profit after tax (11-12)` 208.93 | l38 `13 Profit after tax (11.12)` 253.44 | l38 `13 Profit after tax (11-12)` 467.45 |
   | OCI | l47 `14 Other comprehensive incomes (OCI)` 62.22 | l46 `… (OCI(` (3.04) | l46 `… (OCI)` (138.56) |
   | TCI | l48 `15 Total comprehensive income for the period/year (13+14)` 271.15 | l47 same, 250.40 | l47 same, 328.89 |
   | basic EPS | l60 `- Basic BA)` 52.01 | l59 `'Basic . ~~PpAR ,` 63.09 | l59 `-Basic / Q ' ) 'O\` 116.37 |

   PQ0 keeps v1's labels; its tax rows sit in section `10 Tax exp` (`probe3_pq0_v5.out`, l31–33).
5. **PQ3 prints two `.` cells**, exceptional items (l30) and earlier-years tax (l37). The adapter keeps
   `.` as `VALUE` (`pdf_adapter.py:244–252`: only `DASH_GLYPHS`, blank and printed zero are marked) and
   interpretation reads it `INVALID`/`UNREADABLE_CELL` (`interpret.py:697–700`); the `pdf.tax_expense`
   construction is then `INVALID`/`UNREADABLE_CELL` too (`probe1_v6.out`). PREP-7's manifest checker
   treats `.` as a zero marker (`tests/fundamentals/pilot_manifest_check.py:74`); production does not, and this plan does
   not change production.
6. **Nil-premise identities hold over an unreadable cell.** v1's
   `total_expenses.total_income_less_profit_before_tax` holds in both representations in PQ3 under v6,
   although the PDF exceptional cell is `UNREADABLE_CELL` (`probe4.out`). `_prove` checks only the
   rule's named operands (`alignment.py:182–233`), so any identity that omits a term by assuming it nil
   would also hold there (it also holds in PQ0, `probe7.out`). The r0 nil-exceptional PBT and
   nil-earlier-years PAT identities had the same defect.
7. **Two premise-free identities hold in all four quarters under v6** (`probe7.out`, production
   `_prove`): total expenses = (a)+(b)+(c)+(d)+(e)+(f)+(g), and PAT = total comprehensive income −
   OCI. Every operand is a mapped, bounded value in both representations. The r1 identity PBT = PBT
   incl. associates − associates is **circular** on the XBRL side and dropped: XBRL
   `profit_before_tax_incl_associates` is the construction ProfitBeforeTax + associates
   (`origin=CONSTRUCTED`, `entry=None`, `probe7.out`; `constructions/v1.yaml`, `v2.yaml:4–13`), so
   that leg holds for any filed PBT.
8. **The tax heading is not recognised.** `_SECTION_HEADINGS` knows `10 Tax exp`
   (`extract/pdf_statement_pages.py:57–61`). PQ1–PQ3 print `12 Tax expenses`, so their tax rows keep
   section `Expenses`. `section_equals: "Expenses"` selects PQ1's `(a) Current tax` row. It refuses the
   same row with section `Discontinued operations` or `10 Tax exp`. v1's `section: "Tax exp"` selects
   only `10 Tax exp` (`probe5.out`). Under v6, PQ0 loses its three tax hits (l31–33) and nothing
   else (`probe4.out`). A second section-bound entry for PQ0's tax rows would be refused as
   `DUPLICATE_SELECTOR` (same measurement; Sol r2). PQ0's `pdf.tax_expense` construction is then
   absent, and v1's `…less_tax` rule yields no proof for PQ0 (`probe7.out`).
9. **v5→v6 hits** (`probe4.out`): PQ0 loses 3 (Finding 8), PQ1 gains 12, PQ2 13 and PQ3 13 (two of
   PQ3's are the `UNREADABLE_CELL` rows). No hit is changed, and no key has two mapped candidates in
   either representation (`probe7.out`).
10. **XBRL side** (`probe1_v5.out`, `probe6.out`). Every operand of the rules above is filed and mapped
    in all four quarters. `ExceptionalItemsBeforeTax` is 0 (PQ0), −249900000 (PQ1), −75400000 (PQ2)
    and 0 (PQ3). The PDF and XBRL intervals intersect for every operand except:
    - `current_tax` in PQ1 (XBRL 760000000, PDF 743100000) and PQ2 (XBRL 802600000, PDF 888400000).
      The XBRL folds earlier-years tax into `CurrentTax`. `tax_expense` intersects.
    - No PDF value: PQ0 `current_tax`, `deferred_tax` and `tax_expense` (Finding 8), PQ3
      `tax_expense`, and the exceptional items of PQ0 and PQ3 (`probe6.out`).
11. **The extractor is hash-pinned.** `evidence/pdf_adapter.py` and `extract/pdf_statement_pages.py`
    are in `EXTRACTOR_SOURCES[PDF]` (`compare/run_config.py:64–73`), hashed with `pdf-occurrences/3`
    (`pdf_adapter.py:52`). `VENDOR_EXTRACTORS` covers vendor sources only.
12. **A delta PDF file is impossible.** `_check_duplicates` (`evidence/mapping.py:484–520`) refuses
    overlapping entries in one surface/schema/source scope. Constructions name operands by exact entry
    id (`capture_interpretation.py:367–386`), so pdf/v2 must be a full copy of v1.
13. **`compare run` has no alignment flag.** It passes only dictionary and mapping set
    (`api/compare_cli.py:144–145`, :260). `ConfigVersions.alignment_rules` exists
    (`contracts/config_versions.py:24`). `compare run` is per `--period-end`, so pins may differ by
    quarter.
14. **PBT layout evidence** (`probe7.out`). In every quarter the XBRL PBT is the DIRECT filed element
    `in-capmkt:ProfitBeforeTax` (entry `capmkt.profit_before_tax` in PQ0–PQ1,
    `capmkt.profit_before_tax.2026` in PQ2–PQ3; both inside the anchor's family). The associates
    share is the filed `ShareOfProfitLossOfAssociatesAndJointVenturesAccountedForUsingEquityMethod`.
    The PDF prints PBT before associates, then associates, then the incl.-associates subtotal (all p3,
    section `Expenses`):

    | Q | PBT (`pdf.profit_before_tax`) | associates | subtotal (`…_incl_associates`) | XBRL `ProfitBeforeTax` meets PBT / subtotal |
    |---|---|---|---|---|
    | PQ0 | l27 `7 … (5.6)` 340.56 | l28 `8 …` (0.03) | l29 `9 Profit before tax (7+8)` 340.53 | yes / no |
    | PQ1 | l32 `9 … (7` 288.09 | l33 `10 …` (0.01) | l34 `11 Profit before tax (9+10)` 288.08 | yes / yes |
    | PQ2 | l31 `9 … (7.8)` 328.80 | l32 `10 …` 0.12 | l33 `11 … (9+10)` 328.92 | yes / no |
    | PQ3 | l31 `9 … (7.8)` 622.34 | l32 `10 …` 0.26 | l33 `11 … (9+10)` 622.60 | yes / no |

    The PBT line's label cites the subtotal arithmetic it sits before (`(5-6)`/`(7.8)`), and the
    subtotal cites `(7+8)`/`(9+10)`, so PBT is the position before associates — what the dictionary
    defines (`dictionary/v2/pl.yaml:52–54`). In PQ1 the subtotal's interval also touches XBRL PBT
    (the associates share is 0.01), so value agreement alone cannot tell the two lines apart there; the
    layout rule does. Production `_prove` on the rule below holds in all four quarters. It does not
    hold when either anchor is swapped to the incl.-associates entry, or when the PDF PBT key is fed
    the line-11 interpretation (the position negative).
15. **Expense lines are section-bound** (`probe7.out`). All seven 6(a)–(g) rows and total expenses sit
    in section `Expenses` in every quarter; with `section_equals: "Expenses"` each entry selects its
    row and refuses it with section `Discontinued operations`.
16. **No other pilot consumer needs PQ0's PDF tax mappings.** The run's tax (`calc.2`) is the XBRL
    `TaxExpense` figure (`api/pipeline_steps.py:185–188`), bound to the XBRL capture's
    interpretations (`ledger/run_traces.py:370–372`, `operand` :145–149 looks up the XBRL surface).
    The PREP-7 manifest check reads PQ0's tax cells from PDF bytes through its own literal
    `PDF_TAX_ROWS` (`tests/fundamentals/pilot_manifest_check.py:106–107`; `PREP-7.md` Decision 2,
    interface steps (0)–(d)), never through a mapping set. This is a read of those call sites, not a
    run.

## Decisions

1. **One pin set for all four quarters**, the admission plan's `PILOT_VERSIONS`: dictionary `v2`,
   mapping set `v6` (v5 with `pdf/v2/results_layout.yaml` in place of `pdf/v1`), alignment `v2`.
   `PILOT-GAP-admission.md` is unchanged. **Accepted narrower coverage:** PQ0's three PDF tax
   mappings (l31–33) and its tax-based PAT proof are dropped; PQ0 PAT is proved by TCI − OCI
   (Findings 8, 16).
2. **New issuer config `config/aparinds-fy27-q1-pg.yaml`**: a copy of `aparinds-fy27-q1.yaml` plus
   `pdf_parse.statement_pages.PL.unit_markers` `{text: "Ra.in crones", scope: PAGE, raw_unit: INR,
   raw_scale: 7, value_kind: CURRENCY_AMOUNT}`, commented with sha256 c0c2b2fa…8612, page 3, words
   `(Ra.in crones)` (the `-q4-pg` precedent). PQ3 ingestion and acceptance use it. PQ0–PQ2 use
   `aparinds-fy26-q2`, `-fy26-q3` and `-fy26-q4-pg`.
3. **pdf/v2** = full copy of v1, a header naming v2, and these exact-label edits. Each `evidence_ref`
   cites sha8, page and line from Finding 4.
   - Label variants added:
     - `other_income`: `4 Other income`.
     - `changes_in_inventories`: `…stock-in-trac`.
     - `profit_before_tax`: the `(7` and `(7.8)` labels.
     - `share_of_profit_associates_jv`: `10 Share in net profit / (loss) of associates`.
     - `profit_before_tax_incl_associates`: `11 Profit before tax (9+10)`.
     - `profit_for_period`: `13 Profit after tax (11-12)` and `(11.12)`.
     - `oci_net`: `14 … (OCI)` and `(OCI(`.
     - `total_comprehensive_income`: `15 … (13+14)`.
     - `eps_basic`: the three EPS variants. PQ3's ends in a backslash, so use a double-quoted YAML
       escape.
   - New `pdf.exceptional_items_before_tax` with `COLUMN_DURATION` and labels `8 Exceptional items
     (refer note 3)` and `(refer note 7)`. Mapping PQ3's line makes its `.` an explicit
     `UNREADABLE_CELL` rather than an absence.
   - `pdf.current_tax`, `pdf.deferred_tax` and `pdf.tax_earlier_years`: `section: "Tax exp"` becomes
     `section_equals: "Expenses"`, the exact PQ1–PQ3 context. PQ0's `10 Tax exp` rows go unmapped
     under v6 (Decision 1).
   - The seven 6(a)–(g) entries and `pdf.total_expenses` gain `section_equals: "Expenses"`
     (Finding 15).
   - The full copy is kept so that v6 keeps every other PDF entry (balance sheet and so on). A
     12-entry subset was considered: it loads, but it would drop that coverage for any other v6 user.
4. **alignment/v2** = v1's rules verbatim except `total_expenses.total_income_less_profit_before_tax`,
   which is dropped (Finding 6), plus three rules (Finding 7):
   - `total_expenses.sum_of_expense_lines`: ADD of the seven 6(a)–(g) operands.
   - `profit_before_tax.before_associates_position`: `LAYOUT_POSITION`, anchors
     `XBRL: capmkt.profit_before_tax`, `PDF: pdf.profit_before_tax`. Its `evidence_ref` cites Finding
     14's elements and per-quarter sha8/page/line triples.
   - `profit_for_period.total_comprehensive_income_less_oci`: `SUB(total_comprehensive_income, oci_net)`.

   No v2 rule reaches a value through an unreadable cell, a nil premise or a construction of its own
   target. v1's PBT
   (`…plus_exceptional`) and PAT (`…less_tax`) rules name the exceptional and tax operands, so they
   fail closed (no proof) where those operands are unreadable.
5. **No production code change** apart from the CLI flag. The extractor route (`.` as a nil marker) is
   rejected in Open question 1.
6. **`compare run --alignment-rules`** (default `v1`) passes `ConfigVersions(alignment_rules=…)`.

Expected holding proofs of alignment v2 under v6 (`probe7.out`, production `_prove`; ✓ holds,
— yields no proof):

| Rule | PQ0 | PQ1 | PQ2 | PQ3 |
|---|---|---|---|---|
| total_income / revenue / other_income (v1) | ✓ | ✓ | ✓ | ✓ |
| total_expenses.sum_of_expense_lines (v2) | ✓ | ✓ | ✓ | ✓ |
| profit_before_tax.income_less_expenses_plus_exceptional (v1) | — no PDF line | ✓ | ✓ | — `UNREADABLE_CELL` |
| profit_before_tax.before_associates_position (v2) | ✓ | ✓ | ✓ | ✓ |
| profit_for_period.pbt_incl_associates_less_tax (v1) | — no PDF tax | ✓ | ✓ | — `UNREADABLE_CELL` |
| profit_for_period.total_comprehensive_income_less_oci (v2) | ✓ | ✓ | ✓ | ✓ |
| eps_basic.basic_line (v1) | ✓ | ✓ | ✓ | ✓ |

## Assumptions

- A1. For the six roles, the PDF and XBRL intervals intersect in all four quarters (`probe6.out`).
  The comparator's own tolerance is assumed to accept intervals that intersect; Task 2 proves it.
  `current_tax` differs in PQ1–PQ2 (Finding 10). It is a construction operand only, never a compared
  role in this plan.
- A2. In production, `KeySelection` picks the one mapped interpretation the probe found per key.
  The probe builds one selection per key itself (no duplicates found) rather than running the
  selector.

## Open questions (recommended rulings)

1. ~~Accept the circular PBT identity~~ — superseded by Sol r2: the layout rule (Decision 4,
   Finding 14) replaces it. A layout rule proves position, not value; the role itself still has to
   `AGREE` value for value.

   The rejected alternative for PQ3 is to read `.` as an evidenced nil. That needs `_missing_state`/`DASH_GLYPHS` edits
   in two pinned files, so `pdf-occurrences/4` and a re-extraction of every pinned database. Even then
   a dash has no value in alignment (`_valued`, `alignment.py:236–252`; dash-as-zero exists only inside
   constructions, `interpret.py:489–505`), so it would also need an alignment-engine change. Rejected:
   it is not needed for 24/24.
2. Noisy EPS labels: exact variants, or change `normalize_text_tokens`? **Exact variants.**
   Normalisation is shared by every mapping set.

## File map

| File | Change | Task |
|---|---|---|
| `config/aparinds-fy27-q1-pg.yaml` | new: `aparinds-fy27-q1.yaml` + PL unit marker (Decision 2) | 1 |
| `config/mappings/pdf/v2/results_layout.yaml` | new: full copy of v1 + Decision 3 edits | 1 |
| `config/mappings/v6.yaml` | new: v5 with `pdf/v2/results_layout.yaml` | 1 |
| `config/mappings/alignment/v2.yaml` | new: Decision 4 | 1 |
| `src/fundamentals/api/compare_cli.py` | `--alignment-rules` (:145, :260, usage :5) | 1 |
| `tests/fundamentals/test_pilot_alignment.py` | new: four-quarter acceptance + negatives | 2 |

`docs/plans/PILOT-GAP-admission.md` is not changed.

## Size (estimate)

- The issuer config has 116 lines, 8 of them new. pdf/v2 copies 671 lines; the draft has 678, with
  26 lines changed or new (`diff | grep -c '^>'`), plus the evidence refs Task 1 writes. v6 has 20
  lines. alignment/v2 has 95 lines (draft `wc -l`): v1's 74, minus 9 dropped, plus 30 new.
- The CLI change is about 3 lines and the test about 170 (r1's 140 plus the layout and section
  negatives).
- There is no new Python logic in `src`.

## Tasks

### Task 1 — issuer config, pdf/v2, mapping set v6, alignment v2, CLI flag (Opus)

- **Files:** the first five rows of the file map. The scratch drafts in
  `scratchpad/gap-alignment/mappings/` and `aparinds-fy27-q1-pg.yaml` are the starting point. Their
  `evidence_ref: "probe"` placeholders must be replaced with Finding 4 citations.
- **Interfaces:**
  - Produces mapping set `v6`, alignment rules `v2`, `aparinds-fy27-q1-pg.yaml` and
    `fundamentals compare run … --alignment-rules <v>`. Without the flag, behaviour is unchanged.
- **Verification:**
  - `load_mapping_set(config/mappings, "v6", dictionary=v2)` and `load_alignment_rules(alignment/v2.yaml)`
    load.
  - Re-running `probe7_prove.py` and `probe4_align.py` with their mapping root pointed at `config/mappings` reproduces the Decision table and Findings 9, 14 and 15.
  - `git diff --stat` shows no change to any existing file under `config/` or `migrations/`.
  - All four gates pass.

### Task 2 — four-quarter acceptance and fail-closed negatives (Opus; after Task 1)

- **File:** `tests/fundamentals/test_pilot_alignment.py`, markers `pg` and `retained`, parametrized
  over (quarter, issuer config): (`FY26_Q2`, `aparinds-fy26-q2`), (`FY26_Q3`, `-fy26-q3`),
  (`FY26_Q4`, `-fy26-q4-pg`), (`FY27_Q1`, `-fy27-q1-pg`); mapping set v6 throughout.
- **Ingestion, per quarter:**
  - `apar_intake(tmp_path, quarter, BOTH, issuer_config=cfg_path)`.
  - Catalog: `BUILTIN_SOURCES.extend(SourceDescriptor(source_id=cfg.results_pdf.source_id,
    source_class=FIRST_PARTY, evidence_role=RECONCILABLE))`.
  - Local fixtures (shared helpers unchanged): `dictionary = load_dictionary(CONFIG / "dictionary", "v2")`
    and `mapping_set = load_mapping_set(CONFIG / "mappings", "v6", dictionary=dictionary)`.
  - `Ingest.run(intake, cfg.quarter.period_end, mapping_set=mapping_set, catalog=…,
    pdf_specs=specs_from_config(cfg.pdf_parse))` — the loaded `MappingSet` object, not a version string.
- **Positive, per quarter:**
  - `execute_run` runs AS_KNOWN under dictionary v2, mapping set v6 and alignment v2.
  - Each of the six `REQUIRED_ROLES` keys is `extraction_status AGREE`.
  - The holding rule ids from `EvidenceRepository.list_alignment_proofs(package_id)` (filtered to
    `rule_set_version == "v2"`) equal the ✓ cells exactly. That also proves the dropped v1 rule is
    absent.
  - `admit_run` admits all six with no refusal for them.
- **Negatives:**
  - PQ3: `pdf.exceptional_items_before_tax` and `pdf.tax_earlier_years` are `INVALID`/`UNREADABLE_CELL`,
    and the `pdf.tax_expense` construction is `INVALID`. There is no proof for v1's `…plus_exceptional`
    and `…less_tax` rules.
  - PQ0: no proof for v1's `…less_tax` rule (no PDF tax under v6). PQ0 under v6 with alignment
    **v1**: PBT is `AGREE_UNQUALIFIED`, and `admit_run` refuses it with `EXTRACTION_NOT_AGREE`.
  - No database:
    - Under `aparinds-fy27-q1.yaml`, PQ3's PL rows from `read_pdf_occurrences` have `raw_unit ""`.
    - Section mutation: pdf/v2's three tax entries (`pdf.current_tax`, `pdf.deferred_tax`,
      `pdf.tax_earlier_years`), the seven 6(a)–(g) entries and `pdf.total_expenses` each `select`
      their PQ1 row in section `Expenses` and do not `select` it with section `Discontinued operations`.
    - CLI wiring: parse real `compare run` arguments with the request boundary mocked; explicit
      `--alignment-rules v2` reaches `ConfigVersions(alignment_rules="v2")`, and omitting the flag
      keeps v1.
    - PBT layout, per quarter over in-memory selections (as `probe7_prove.py`, through the public
      `prove_alignment`): the rule holds; it does not hold with the PDF anchor
      `pdf.profit_before_tax_incl_associates`, with the XBRL anchor
      `capmkt.profit_before_tax_incl_associates`, or with the PDF PBT key fed the incl.-associates
      line.
- **Verification:** `uv run pytest tests/fundamentals/test_pilot_alignment.py -m "pg and retained"`
  passes, then the full gates.
- **Risk:** A1's tolerance step fails for a role. If so, report it; never loosen a rule or a
  tolerance.

## Acceptance

- Under v2/v6/v2, all six required roles are `AGREE` and admitted in PQ0–PQ3. That makes
  24 of 24, shown by Task 2 on the retained originals through the production extractor, comparator
  and admission. Every number in the asserts is a probe-recorded printed or filed value.
- Fail closed:
  - No proof reaches a value through PQ3's `.` cells.
  - PQ0 PBT is refused without alignment v2.
  - The PBT layout rule fails on a wrong anchor or position.
  - The pdf/v2 tax and expense selectors are exact to their section.
- `_decide`, `_qualified`, the extractor, existing configs, migrations and the stage1 and pilot
  manifests are unchanged. The stage1 tests stay green.

## Interactions with `eqos-4j2.24`

- This bead blocks its Tasks 2–3. Its single `PILOT_VERSIONS` (v2/v6/v2) holds for all four
  quarters (Decision 1), with the issuer configs of Decision 2. PQ3 must ingest under `aparinds-fy27-q1-pg.yaml`. Its production
  sequence adds `--alignment-rules v2` to `compare run`.
- Its Task 2 owns `evidence ingest --dictionary/--mapping-set` (and the issuer-config choice); this plan
  does not touch `api/evidence_cli.py`. Its Task 1 edits `test_admission.py`, so this plan uses a new
  test file. Its Task 3 harness should reuse Task 2's per-quarter ingest → compare → admit steps.

## Not verified

- Any comparison, stored proof or admission outcome. These need PostgreSQL and are proven only by
  Task 2 (A1's tolerance step, A2).
- That `retained_intake_from_manifest` accepts each quarter's config pin against the manifest sha.
  The probe matched the config pins against the files only.
- Whether any existing test enumerates mapping sets, alignment versions or issuer configs and needs
  the new ones added.

## r1 findings → resolution

| # | Finding | Resolution |
|---|---|---|
| 1 P1 | PQ3 unit unresolved | Decision 2: new `aparinds-fy27-q1-pg.yaml`, exact marker `Ra.in crones` evidenced by tokens and words on page 3 of c0c2b2fa (Finding 2); no existing config edited; prescribed for ingest and acceptance. |
| 2 P1 | Helpers cannot ingest PQ1–PQ3 | Task 2 calls `apar_intake(…, issuer_config=cfg_path)` with a per-quarter catalog and `pdf_specs` (Finding 3). |
| 3 P2 | PAT nil premise unverified | Route: premise-free identities. PAT = TCI − OCI (config-only; every operand readable and filed). The nil-earlier-years rule is dropped. The same defect applied to PQ3's exceptional `.`, so the nil-exceptional PBT rule is dropped and v1's TE rule is left out of v2. Replacements: TE = sum of 6(a)–(g) and PBT = PBT incl. associates − associates (Findings 5–7). Negatives: PQ3's `.` cells are `UNREADABLE_CELL`, and v1's rules over them yield no proof. The `.`-as-nil code route was checked against the pins and rejected (Open question 1). |
| 4 P2 | Dropped tax section broadens selection | `section_equals: "Expenses"` for PQ1–PQ3 in pdf/v2. PQ0 keeps v1's context through separate pins (superseded by r2 #1: PQ0 tax rows unmapped under v6). The mutation negative is in Task 2 (Finding 8). |
| 5 P2 | Arithmetic without code provenance | The by-hand sums and A2's inference are removed. Every number comes from the recorded probe output (Probe table); PQ1 XBRL exceptional −249900000 is read directly (Finding 10). |
| 6 P3 | Full copy not mandatory | The full copy is kept; the subset alternative is noted (Decision 3). |
| 7 P3 | Evidence corrections | The r0 count corrected to 26 (PQ3 eight) is superseded: the revised pdf/v2 gains 12/13/13 (Finding 9). A1 is narrowed; `current_tax` differs in PQ1–PQ2 because the XBRL folds earlier-years tax (Finding 10). |
| other | EPS labels; PQ0 negative; rule evidence | EPS exact variants kept. PQ0 negative kept, now v5/alignment v1 (r2: v6/alignment v1). Rule ids are asserted through `list_alignment_proofs`. |

## r2 findings → resolution

| # | Finding | Resolution |
|---|---|---|
| 1 P1 | PQ0 on v5 contradicts the admission plan's single `PILOT_VERSIONS` | Decision 1: v6 for all four quarters; admission plan unchanged. Narrower coverage recorded: PQ0's three PDF tax mappings and its tax-based PAT proof dropped, PAT proved by TCI − OCI (Findings 8–9). No duplicate-checker or section-guard change. Other consumers checked: none needs PQ0's PDF tax mappings (Finding 16). Task 2 runs v6 throughout. |
| 2 P2 | PBT identity circular on the XBRL side | Dropped. Decision 4: `LAYOUT_POSITION` `profit_before_tax.before_associates_position`, anchors `capmkt.profit_before_tax` / `pdf.profit_before_tax`. Finding 14 records the filed elements, per-quarter PDF lines and the associates/subtotal evidence, all from `probe7.out`. Production `_prove` holds in PQ0–PQ3; anchor and position negatives fail (Task 2). |
| 3 P2 | Expense proof not section-bound | Decision 3: `section_equals: "Expenses"` on the seven 6(a)–(g) entries and `pdf.total_expenses`. Finding 15: each selects its row and refuses `Discontinued operations` in every quarter. The negatives are in Task 2. |
