# Wave-2 Multi-Stock Validation — Roll-up

**Date:** 2026-08-22 · **Quarter:** Q3FY25 (2024-10-01 … 2024-12-31), consolidated, Ind AS ·
**Sources:** NSE Ind AS XBRL (first-party) · BSE issuer results PDF (first-party) ·
Screener (derived cross-check). Values in ₹ crore (EPS in ₹/share).

Wave 2 adds one stock per remaining domain (`docs/research/watchlist.md`): Netweb (GPUs),
HFCL (electrical connectivity), Polycab (cables), CG Power (power infra), Eternal / fmr Zomato
(others). All identifiers were resolved and confirmed live (NSE `financial_results` + BSE
`getScripName`/`announcements`) on 2026-08-22 before being written to `config/watchlist.yaml`.

Machine reports (`*-Q3FY25.json`, `Wave-2-rollup.json`; full provenance) are gitignored (large,
regeneratable; kept on disk under this directory). The watchlist config carries a single
top-level `wave` label and no per-stock wave field, so Wave 2 is regenerated **per symbol**
(`--watchlist` would run all ten stocks under the "Wave-1" label). Point `--report-dir` at a
scratch dir: a per-symbol run also writes a single-stock `Wave-1-rollup.json` named from the
config's `wave`, which would otherwise clobber the Wave-1 machine roll-up.

```
for S in NETWEB HFCL POLYCAB CGPOWER ETERNAL; do
  uv run fundamentals validate --symbol "$S" --quarter Q3FY25 --sources nse,pdf,screener --live \
    --report-dir "$SCRATCH/reports" --gold-dir data/gold
done
```

## Why this quarter, why these sources

Same frontier as Wave 1: NSE's API serves consolidated Ind AS XBRL through **Q3FY25 (Dec-24)**;
BSE `resultsSnapshot` exposes only the **latest ~2 quarters** (no Q3FY25 overlap), so the second
independent first-party source is the **issuer results PDF** fetched from BSE announcements
(structured XBRL cross-checked against the company's own signed statement). Screener is a derived
aggregator — cross-check only, never source-of-record; it can corroborate an already-agreed value
but never counts toward the two first-party sources a fact needs to be confirmed. Tijori and SEC
are out of scope here (no credentials injected; none of the five is US-listed).

## Outcome per stock

| Stock | Domain | AGREE (2 first-party) | Outcome | Note |
|---|---|---|---|---|
| **CGPOWER** | Power Infra | **4 / 5** | needs_adjudication | Revenue/Income/PBT/EPS all NSE=PDF exact; ProfitForPeriod single (discontinued-ops split); profit-attribution cross-foot residual (258.38) |
| **POLYCAB** | Cables | 0 / 5 | needs_adjudication | NSE clean (cross-foot residual 0.000); PDF **skipped** (consolidated P&L page not found — OCR/encoding-corrupt text layer, unit in ₹ million); every fact single first-party |
| **HFCL** | Electrical Conn. | 0 / 5 | needs_adjudication | all 3 sources returned, but the PDF read the **standalone** column of a combined table and conflicts with NSE consolidated (see gap #1) |
| **NETWEB** | GPUs / Supercomp. | 0 / 5 | **BLOCKED** | NSE lists **no consolidated quarterly** filing (standalone-only filer); PDF has no consolidated statement; Screener has no consolidated quarter columns → no first-party source reachable |
| **ETERNAL** | Others (fmr Zomato) | 0 / 5 | **BLOCKED** | NSE fail-closed on issuer-rename entity mismatch (`['ZOMATO'] ≠ 'ETERNAL'`, see gap #2); PDF **skipped** (consolidated P&L page not found); Screener-only (derived, fp=0) |

**4 / 25 material concepts** reached two-first-party AGREE (all CGPOWER). Every non-AGREE is a
*reported* fail-closed — a conflict surfaced for review, a skipped source with a structured note,
or a blocked stock — never a fabricated or silently-dropped number. The core guarantee held on
every stress case: **no wrong or unsourced value was ever confirmed** (HFCL's mis-scoped PDF
values conflicted rather than agreeing; ETERNAL's Screener-only values stayed unconfirmed).

The PDF second-first-party source was the bottleneck: it produced usable consolidated facts for
only **1 of 5** Wave-2 issuers (CGPOWER). Without a working PDF, NSE alone is a single first-party
source, so a fact cannot reach two-first-party AGREE even when NSE is clean and Screener
corroborates it (POLYCAB is the clearest case).

## Per-concept matrix (NSE-XBRL vs BSE-PDF vs Screener)

| Stock | Concept | Status | NSE | BSE-PDF | Screener |
|---|---|---|---:|---:|---:|
| CGPOWER | RevenueFromOperations | AGREE | 2515.68 | 2515.68 | 2516 |
| CGPOWER | Income | AGREE | 2549.28 | 2549.28 | — |
| CGPOWER | ProfitBeforeTax | AGREE | 334.86 | 334.86 | — |
| CGPOWER | ProfitLossForPeriod | single | 237.85 | — | 238 |
| CGPOWER | BasicEPS | AGREE | 1.57 | 1.57 | 1.57 |
| POLYCAB | RevenueFromOperations | single | 5226.062 | — | 5226 |
| POLYCAB | Income | single | 5251.067 | — | — |
| POLYCAB | ProfitBeforeTax | single | 616.573 | — | — |
| POLYCAB | ProfitLossForPeriod | single | 464.348 | — | 464 |
| POLYCAB | BasicEPS | single | 30.42 | — | 30.42 |
| HFCL | RevenueFromOperations | conflict | 1011.95 | 960.94 ⚠SA | 1012 |
| HFCL | Income | conflict | 1031.99 | 981.95 ⚠SA | — |
| HFCL | ProfitBeforeTax | conflict | 99.61 | 106.87 ⚠SA | — |
| HFCL | ProfitLossForPeriod | single | 72.58 | — | 73 |
| HFCL | BasicEPS | conflict | 0.51 | 0.54 ⚠SA | 0.51 |
| NETWEB | RevenueFromOperations | missing | — | — | — |
| NETWEB | Income | missing | — | — | — |
| NETWEB | ProfitBeforeTax | missing | — | — | — |
| NETWEB | ProfitLossForPeriod | missing | — | — | — |
| NETWEB | BasicEPS | missing | — | — | — |
| ETERNAL | RevenueFromOperations | single (fp=0) | ✗ blocked | ✗ skip | 5405 |
| ETERNAL | Income | missing | ✗ blocked | ✗ skip | — |
| ETERNAL | ProfitBeforeTax | missing | ✗ blocked | ✗ skip | — |
| ETERNAL | ProfitLossForPeriod | single (fp=0) | ✗ blocked | ✗ skip | 59 |
| ETERNAL | BasicEPS | single (fp=0) | ✗ blocked | ✗ skip | 0.06 |

`⚠SA` = the BSE-PDF value is the issuer's **standalone** current-quarter figure that the parser
mis-read from a combined statement and stamped `scope=CONSOLIDATED` (gap #1); it is not the
consolidated figure. Income and ProfitBeforeTax carry no Screener column because Screener does not
publish those lines. `single (fp=0)` = only a *derived* source (Screener) returned the concept, so
it has zero first-party backing and can never be confirmed (correct fail-closed for a BLOCKED
stock).

Cross-foot (first-party identity checks, NSE side): POLYCAB and CGPOWER both hold the
`PBT = Total income − Total expenses` identity to 0.00. CGPOWER's
`Profit for the period = owners + non-controlling interests` identity fails with residual
**258.38** — the discontinued-operations analogue of Wave-1's SONACOMS associate/exceptional
residual (the selected profit line is continuing-operations profit; the attribution terms are on
total profit). HFCL both identities hold on its NSE consolidated numbers.

## Generalization gaps found by the multi-stock run (the point of the exercise)

Four NEW gaps surfaced beyond Wave 1. Gaps #1 and #2 are code defects to route; #3 and #4 are
coverage realities to decide on. **None was fixed here** (this lane owns only `config/watchlist.yaml`
and reports).

1. **PDF column selector reads the standalone column of a combined "Standalone AND Consolidated"
   single-table statement (HFCL) — a silent wrong-scope extraction.** HFCL files one table titled
   *"Statement of Un-audited Standalone and Consolidated Financial Results…"* with the standalone
   scope block printed left of the consolidated block; both blocks carry a 31-Dec-2024
   current-quarter column. `_find_statement_page` accepts the page (it contains "Consolidated"),
   but `_current_column_center` picks `min(x)` among columns whose header date == `period_end`
   (the quarter-vs-YTD disambiguator) — which is the **leftmost = standalone** quarter column.
   The parser then emits the standalone value stamped `scope=CONSOLIDATED`.
   *Evidence:* PDF page 5 prints Revenue standalone **960.94** / consolidated **1,011.95**; the
   PDF observation is 960.94 while NSE (and Screener) are 1011.95/1012. Same standalone/consolidated
   split on Income (981.95 / 1031.99), PBT (106.87 / 99.61), EPS (0.54 / 0.51). Cross-foot passes
   on the PDF's own (internally consistent standalone) numbers, so nothing internal flags it — only
   the NSE disagreement catches it. Contained by the two-first-party AGREE gate (it showed as
   `conflict`, not a confirmed fact), but it pollutes the observation/gold provenance with a
   wrong-scope value. *Fix direction (route, do not implement here):* confine current-quarter
   column selection to the consolidated column group (e.g. anchor to the "Consolidated" header's
   x-span), or reject/relabel a page that carries both scope markers in one table.

2. **Issuer rename between filing time and retrieval time breaks NSE issuer verification
   (ETERNAL / fmr ZOMATO).** The Q3FY25 XBRL was filed (Jan-2025) as *Zomato Limited* and carries
   `NSESymbol/Symbol = "ZOMATO"`; the company renamed to *Eternal* (symbol ZOMATO→ETERNAL,
   effective 2025-04-09). Today `financial_results(symbol="ETERNAL")` returns the Dec-2024 row
   (NSE keys history under the current symbol), the download succeeds, but
   `NseXbrlSource._verify_issuer` rejects it: `downloaded XBRL entity ['ZOMATO'] does not match
   requested issuer 'ETERNAL'`. The old symbol is no escape hatch: `financial_results(symbol=
   "ZOMATO")` now returns **0 rows** (verified live). So **no single `nse_symbol` satisfies both**
   the listing lookup (needs ETERNAL) and issuer verification (needs ZOMATO); NSE ingestion is
   unavoidably fail-closed for any renamed issuer whose filing predates the rename.
   *Fix direction:* verify issuer by a stable key (ISIN, or an accepted alias set in config) rather
   than the point-in-time NSE symbol, and/or let a stock declare `nse_symbol_aliases`.

3. **PDF consolidated-page finder misses valid consolidated P&L layouts (POLYCAB, ETERNAL) →
   fail-closed SKIP, loss of the second first-party source.** POLYCAB's PDF text layer is
   OCR/encoding-corrupt (Latin letters substituted with Greek glyphs — "ΤΗΕ", "ΝΙΝΕ",
   "RESUL TS") and prints amounts in ₹ million; the consolidated page's markers don't match.
   ETERNAL's PDF exposes only a consolidated *segment-notes* page and a *standalone* P&L page to
   the finder — the main consolidated P&L statement page is not matched. Both correctly SKIP (no
   fabrication), but the cross-check collapses to NSE-only. This is the Wave-1 "PDF extractor
   overfit" theme recurring on new layouts; closing it needs a scanned-page/vision lane or more
   layout-robust page detection, not looser matching.

4. **Recent / single-entity issuers may file no consolidated quarterly at all (NETWEB) →
   structurally un-validatable by a consolidated-only pipeline.** NSE lists only **Non-Consolidated
   (standalone)** Ind AS quarterly filings for NETWEB (zero consolidated quarterly rows anywhere,
   verified live); the results PDF likewise has no consolidated statement, and Screener's
   consolidated view has no quarter columns. NETWEB is therefore correctly BLOCKED — but this is a
   watchlist-selection / product-scope decision, not a bug: either add a standalone validation lane
   or exclude standalone-only filers from the consolidated gold loop.

## Residual (not defects in this lane)

- **Config models a single top-level `wave`** with no per-stock wave field, so Wave 2 was appended
  to the same file and run per-symbol; `--watchlist` would run all ten under the "Wave-1" label and
  `_write_reports` would name the roll-up `Wave-1-rollup.json`. Reports here were routed to scratch
  and the five per-stock JSONs + a hand-assembled `Wave-2-rollup.json` copied in, so no Wave-1
  artifact was overwritten. Recommend a per-stock `wave` field or per-wave config files.
- **CGPOWER ProfitForPeriod single-source** (PDF did not isolate a clean total-profit line under
  the continuing/discontinued split) and the **258.38 attribution cross-foot residual** are the
  same class as Wave-1's LAURUS PFP / SONACOMS residual — a discontinued-operations structure, not
  a parser defect.
- **A BLOCKED stock with a derived-only source still writes a gold file** (ETERNAL: Screener-only,
  all facts fp=0). Minor: consider not writing a gold reference when a stock has zero first-party
  facts.

---

## Re-validation update (2026-08-22, after the OCR + scope + rename fixes)

Re-ran all 5 Wave-2 stocks live once the consolidated-column confinement, local-OCR
lane, and ISIN-anchored issuer-rename verification landed on main.

**Wave-2 AGREE: 4/25 → 8/25.** Whole net gain is HFCL.

| Stock | Before | After | What changed |
|---|---|---|---|
| CGPOWER | 4/5 | 4/5 | control — reproduced exactly |
| HFCL | 0/5 (PDF read standalone → all conflict) | **4/5** | PDF now reads the CONSOLIDATED column (Rev 1011.95, Income 1031.99, EPS 0.51) — matches NSE |
| ETERNAL | 0/5 · **BLOCKED** | 0/5 · needs_adjudication | rename fix unblocked NSE (entity ZOMATO via ISIN); PDF still skipped |
| NETWEB | 0/5 · BLOCKED | 0/5 · needs_adjudication | standalone-only filer; NSE has no consolidated filing |
| POLYCAB | 0/5 | 0/5 | OCR reached the page, stalled at current-quarter-column resolver |

No stock is BLOCKED anymore (was 2). No wrong/unsourced value was ever confirmed.

### Open OCR follow-ups (recorded, not yet fixed)

1. **NETWEB standalone-as-consolidated (contained bug):** NETWEB filed standalone only; the OCR
   fallback picked its standalone P&L and stamped `scope=consolidated` because the spec forces
   consolidated scope. Values stayed single-first-party (never confirmed), so nothing false was
   published, but the provenance is wrong. Fix: page-scope check before OCR extraction; fail-closed
   for standalone-only filers.
2. **OCR current-quarter-column resolver (highest leverage):** fails when a statement has both a
   3-month and a 9-month column sharing the same period-end and/or multi-line date headers
   (`Quarter ended` / `December 31,` / `2024`). This alone blocks ETERNAL (clean consolidated page
   already located) and POLYCAB (plus a Greek-glyph header). Multi-line-date assembly + 3-vs-9-month
   disambiguation would unblock both.
