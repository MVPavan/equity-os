# Stock Watchlist — Product-Owner Recommendations

**Source:** product owner (PavanMV), 2026-08-21. Raw recommendation list, organized by domain.
**Status:** watchlist only — NOT analyzed, NOT investment advice, NOT vetted. Company names
are as supplied; exact NSE/BSE tickers are resolved at analysis time (some names are
approximate; a few are recent listings or SME-board / BSE-heavy).

**Use:** validation universe for the Fundamentals pipeline. To avoid single-stock (Infosys)
bias, the pipeline is validated on ≥5 structurally-different businesses (see "Validation
selection" below), then expanded toward one-per-domain.

---

## Domains

### GPUs / Supercomputers
E2E (E2E Networks) · Netweb (Netweb Technologies)

### Electrical Connectivity
Sterlite Technologies · HFCL

### Cooling
KRN Heat Exchanger · Aeroflex (Aeroflex Industries) · ABB · Blue Star · Voltas · Thermax

### Cables
V-Marc (Vmarc India) · Finolex · RR Kabel · Universal Cable · Polycab · Prime Cable ·
KSH International · Dynamic Cables

### Precision Engineering
MTAR Technologies · Sansera Engineering · Azad Engineering · Omnitech · Dynamatic Technologies ·
Shivalik Bimetal (Shivalik Biometal)

### Power Infrastructure
TD Power Systems · Yash High Voltage · Pitti Engineering · Kirloskar Oil Engines · ABB India ·
Siemens India · Siemens Energy · Schneider Electric · Hitachi Energy India · Cummins India ·
CG Power · Quality Power · Emmvee Photovoltaic (Emmvee Photovol)

### Auto & Auto Ancillary
Ather Energy · Lumax Auto Tech · Sedemac Mechatronics · SJS (SJS Enterprises) ·
Divgi TorqTransfer (Divgi Torq) · Craftsman Automation · Uno Minda · Sona BLW · Bosch ·
Gabriel India · TVS Motor · Bajaj Auto · Rolex Rings · OBSC Perfection · Pricol · Steel Strips (Wheels)

### CDMO / Pharma
Laurus Labs · Gland Pharma · Shilpa Medicare · Aarti Pharma (Aarti Pharmalabs / Aarti Drugs) ·
Kwality Pharma · Sudeep Pharma · Sai Life Sciences · Acutaas · Divi's Labs · Sakar Healthcare ·
Beta Drugs · Neuland (Neuland Labs)

### Jewellery
Sky Gold · Titan · Kalyan (Kalyan Jewellers) · PN Gadgil (Jewellers) · PNGS Reva

### Others
Shadowfax Technology · Timex · Ethos · Cupid · Eternal (fmr Zomato) · Paytm · Sona BLW ·
Ramkrishna Forgings

---

## Validation selection (Wave 1 — 5 maximally-different domains)

Chosen for maximum structural diversity (different accounting, filing style, size, XBRL
concepts) so the pipeline is stress-tested for generalization, not tuned to one company:

| # | Stock | Domain | Why it stresses the pipeline differently |
|---|---|---|---|
| 1 | **Laurus Labs** | CDMO/Pharma | R&D capitalization, complex inventory, segment mix |
| 2 | **MTAR Technologies** | Precision Engineering | Small-cap, order-book / project-linked revenue |
| 3 | **Sona BLW** | Auto Ancillary | EV components, export mix, margin structure |
| 4 | **Thermax** | Power Infrastructure | Long-cycle project + product mix, order backlog |
| 5 | **Titan** | Jewellery | Retail, inventory-heavy, gold-hedging, non-banking financials |

**Wave 2 (expand toward one-per-domain):** add one from each remaining domain — e.g. Netweb
(GPUs), HFCL (electrical), Polycab (cables), CG Power (power), Eternal (others) — after Wave 1
validates.

## Data-source plan per stock (cross-validation)

Numbers are cross-checked across every source that has the stock, for robustness:

| Source | Access | Role |
|---|---|---|
| NSE (lib + XBRL) | nselib / NseIndiaApi (A05-DECISION-004) | first-party primary |
| BSE (crawl + XBRL) | crawl4AI / `bse` lib | first-party second host |
| Issuer PDF | deterministic parse (PyMuPDF) | first-party document |
| Screener | screener-scraper-pro / openscreener | derived cross-check (own ToS) |
| Tijori | tijori-finance-mcp (owner account) | derived cross-check (own ToS) |
| SEC | edgartools | ONLY if the stock has a US listing (most here do NOT) |

Rights: NSE/BSE private-use per A05-DECISION-004; Screener/Tijori are derived aggregators
with their own terms, used as private cross-check only, never source-of-record. Per-stock the
available sources will differ (small-caps have thinner coverage; SEC usually absent).

## Gold file / gold loop (validation harness — to build in the pipeline validation phase)

A per-stock **gold file** records the cross-validated expected values (each fact + which
sources agreed + provenance). The **gold loop** runs the full pipeline over the watchlist and
regresses each stock's extraction against its gold file — surfacing only discrepancies for
human adjudication. First run builds the gold file from source agreement; later runs regress
against it. This is the multi-stock analogue of the A-08 golden set (which covered decisions);
this one covers facts.
