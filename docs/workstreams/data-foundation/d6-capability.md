# D6 Task 0b — Capability

Status: complete, **no HALT** (2026-10-16). Plan: [`plans/D6.md`](plans/D6.md) Task 0b, D1.2, D1.4,
D2, D4.3. Live requests 2026-10-16 02:20–02:27 UTC, no credentials, 3 s spacing, 30 s timeout;
43/43 returned 200 (`requests.json`). No draw was made or simulated; no non-financial frame row
was read beyond aggregate `Industry` counts.

Retained root `R = data/raw/onboarding-dev/` (gitignored, private). Every claim cites `path`
(relative to `R` unless it starts with `data/`, `config/`, `src/` or `docs/`) and its SHA-256.
Request log: `requests.json` `2f42e5ffccbe0e795c1ff9e3a032da9c828a90d55fb905492299e88c638203f4`
(URL, params, status, bytes, SHA-256, `retrieved_at` per file). Fetch scripts: `scripts/fetch.py`,
`fetch2.py`, `fetch3.py`.

## 1. Frame (D1.2)

| Item | Value | Evidence |
|---|---|---|
| URL | `https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv` (public, `User-Agent` only) | `requests.json` |
| Retained bytes | 32,785 B, `retrieved_at` 2026-10-16T02:20:18Z | `frame/ind_nifty500list.csv` `2959bf206239284e145f7aecc65095b18d11556d2642323a70f2d26efe0f5cb3` |
| Columns | `Company Name, Industry, Symbol, Series, ISIN Code` | same |
| `Industry` column | **present** | same |
| Rows | 501 data rows; 20 distinct `Industry` values | same |
| Financial value(s) | **`excluded_values: [Financial Services]`** (98 rows) — the only finance value in the column | same |

Every financial test company below has `Industry = Financial Services` in this file. The selector
re-fetches the frame for the draw; its own `sha256`/`retrieved_at` go into the attempt record, not
these.

## 2. Financial-sector signal (D4.3 `financial_rule`) — pinned

**Pinned positive non-financial signal:** the XBRL instance declares the `in-capmkt-ent` entry-point
namespace `http://www.sebi.gov.in/xbrl/IntegratedFinance_IndAS/<YYYY-MM-DD>/in-capmkt/in-capmkt-ent`
(matched by namespace URI, not by prefix). Any other or missing entry-point namespace →
`UNSUPPORTED (FINANCIAL_OR_UNKNOWN_SECTOR)`. One signal, filing-borne, read from the two instances
discovery already holds; every instance must carry it.

| Role | Issuer (frame `Industry`) | Instance (period end) | `in-capmkt-ent` namespace segment | `schemaRef` href | SHA-256 |
|---|---|---|---|---|---|
| bank | HDFCBANK, INE040A01034 | `bank-HDFCBANK/nse/INTEGRATED_FILING_BANKING_1696123_18072026040126_WEB.xml` (2026-06-30) | `IntegratedFinance_Banking/2026-01-31` | `in-capmkt-ent-2026-01-31.xsd` | `7c5f4cfae145b0ac20dcbb7081c6a76488fb1ffea1b42e49ddd4a6f46d6cf38b` |
| bank | 〃 | `bank-HDFCBANK/nse/INTEGRATED_FILING_BANKING_1654391_18042026073048_WEB.xml` (2026-03-31) | `IntegratedFinance_Banking/2026-01-31` | 〃 | `de471a6c3e9af6fa4b93c229f53ce77244eaf664db91b9f0039b6d93472ee3f1` |
| NBFC | BAJFINANCE, INE296A01032 | `nbfc-BAJFINANCE/nse/INTEGRATED_FILING_NBFC_INDAS_1705543_30072026070233_WEB.xml` (2026-06-30) | `IntegratedFinance_NBFC/2026-01-31` | `in-capmkt-ent-2026-01-31.xsd` | `6673a4352cbba97633148e64caa8cd803eafc2fefb118e9318ceaf02cae248ba` |
| NBFC | 〃 | `nbfc-BAJFINANCE/nse/INTEGRATED_FILING_NBFC_INDAS_1661603_29042026104724_WEB.xml` (2026-03-31) | `IntegratedFinance_NBFC/2026-01-31` | 〃 | `88a56b7b0ff07e0dd596e8760eddc24d19389ba1a0db205e14ea7e3228b8c7f5` |
| insurer | HDFCLIFE, INE795G01014 | `insurer-HDFCLIFE/nse/INTEGRATED_FILING_LI_1739360_15102026072721_WEB.xml` (2026-09-30) | `IntegratedFinance_LI/2025-01-31` | `in-capmkt-ent-2025-01-31.xsd` | `d6058876141b32251fdc2d557b2987ca31fffc89ffaddeb472d7ad6288897b54` |
| insurer | 〃 | `insurer-HDFCLIFE/nse/INTEGRATED_FILING_LI_1693455_15072026055112_WEB.xml` (2026-06-30) | `IntegratedFinance_LI/2025-01-31` | 〃 | `5108d044540e7ec29c99d16effc4524cec669117cf424a9577904df1cf292903` |
| insurer (extra, standalone-only) | SBILIFE, INE123W01016 | `insurer-SBILIFE/nse/INTEGRATED_FILING_LI_1700867_24072026045312_WEB.xml` | `IntegratedFinance_LI/2025-01-31` | `in-capmkt-ent-2025-01-31.xsd` | `d9ea87b911f4a39c02486374c98d3f63ed6227e1be26edc7fb20f56561762557` |

The two instances per test company are the latest two distinct consolidated period ends after
collapsing to the latest broadcast per period (filing-window rule). Use HDFCLIFE, not SBILIFE, as
the T3 insurer: SBILIFE has only standalone rows (`insurer-SBILIFE/nse-listing/integrated-filing-quarterly.json`
`6ca211cc74152e681e5f6f97afc1e06d3ee46f53e97a910a2226e039ace201a4`), so D4.2 step 2 refuses it
(`STANDALONE_BASIS`) before the financial rule runs.

**Development set — all admitted.** The latest integrated Financials instance of each of the 11
development companies declares `IntegratedFinance_IndAS/2026-01-31` with `schemaRef`
`in-capmkt-ent-2026-01-31.xsd`:

| Dev | Instance | SHA-256 |
|---|---|---|
| APARINDS | `dev-entry-points/APARINDS/nse/INTEGRATED_FILING_INDAS_1701114_24072026063426_WEB.xml` | `f76a131abb5fdb796a8e579848c6036f04181c38f88b05e3a5317f4820124a85` |
| CGPOWER | `dev-entry-points/CGPOWER/nse/INTEGRATED_FILING_INDAS_1701362_25072026090516_WEB.xml` | `75e8d7e56974895f45cd3b4f9bc8ccf3a18f18a5d219ed9b2a17017036f7251f` |
| ETERNAL | `dev-entry-points/ETERNAL/nse/INTEGRATED_FILING_INDAS_1699577_22072026071843_WEB.xml` | `6d66975e1a64fec63e05437b73205e5bf9c80127ef010d9625a118a583b880c0` |
| HFCL | `dev-entry-points/HFCL/nse/INTEGRATED_FILING_INDAS_1699607_22072026075408_WEB.xml` | `a62209bbe99a04d6b115f6c983c71d9fd02e05055e19d4cc5f405cfde149d87a` |
| LAURUSLABS | `dev-entry-points/LAURUSLABS/nse/INTEGRATED_FILING_INDAS_1701038_24072026060410_WEB.xml` | `7bcd878a5eb61d3fb330e16ebd3e04cbae0f10969110f28a874bd9d29ee0faa2` |
| MTARTECH | `dev-entry-points/MTARTECH/nse/INTEGRATED_FILING_INDAS_1704359_29072026063925_WEB.xml` | `784c2adb054cac7c6467dc39002f28d1a625d07db3f714922304c4de706f7489` |
| NETWEB (standalone) | `dev-entry-points/NETWEB/nse/INTEGRATED_FILING_INDAS_1702930_28072026033426_WEB.xml` | `1fa9d17547e46c3f51b386789ee406e5de85f2f1b354b0efd82f7ea9de4f3936` |
| POLYCAB | `dev-entry-points/POLYCAB/nse/INTEGRATED_FILING_INDAS_1738868_15102026035523_WEB.xml` | `6476acf173e1896cf17159a578999aa455a3f25b9d22de9ba502097c8f3df47e` |
| SONACOMS | `dev-entry-points/SONACOMS/nse/INTEGRATED_FILING_INDAS_1700197_23072026055607_WEB.xml` | `7403473de0977b08820dd9672dbc6df28f64ed73bf68263a823d9449f3fc17c2` |
| THERMAX | `dev-entry-points/THERMAX/nse/INTEGRATED_FILING_INDAS_1705307_30072026053358_WEB.xml` | `b42c4c7e2e0d20ecb300e587f469fc2aa0ba6e50163fa303ba23f39a8cd84690` |
| TITAN | `dev-entry-points/TITAN/nse/INTEGRATED_FILING_INDAS_1710081_07082026064307_WEB.xml` | `a1d9eb5bdded074ba0c780fc92b58a3661ba7e3410b758588a5f4bb677801a85` |

The four retained Apar 2025-taxonomy instances also declare `IntegratedFinance_IndAS/2025-01-31`
(e.g. `data/raw/watchlist/aparinds/nse/INTEGRATED_FILING_INDAS_1613642_29012026072210_WEB.xml`).

**Candidates rejected as signals (evidence):**
- `schemaRef` href: **does not separate** — bank, NBFC and Apar all use `in-capmkt-ent-2026-01-31.xsd` (rows above).
- NSE legacy `financial_results` `bank` flag: HDFCBANK all `B`; BAJFINANCE mixes `F` and `N`
  (`N` on 2023 rows); the listing ends at 2024-12-31, so no row falls in a current filing window;
  insurers have no legacy rows (`[]`). `bank-HDFCBANK/nse-listing/financial-results-quarterly.json`
  `6eb918bdac37aba23950b11b34352a0b2266f6637533851bc98dd73a1a1c0531`;
  `nbfc-BAJFINANCE/nse-listing/financial-results-quarterly.json`
  `6b23ff2c2b8790351aec1a6fde1cf160292b574082e39fa53224953c321d0f8e`;
  `insurer-HDFCLIFE/nse-listing/financial-results-quarterly.json`
  `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`.
- Integrated listing: no sector/bank field (keys in the three `integrated-filing-quarterly.json`).
- Instance URL prefix (`INTEGRATED_FILING_INDAS_` vs `_BANKING_`, `_NBFC_INDAS_`, `_LI_`):
  separates on this sample, but is a URL convention, and a substring test on `INDAS` would admit
  NBFCs. Not pinned.

## 3. Ind AS entry point (D5 `REPORTING_FRAMEWORK`, T5a `framework_of_entry_point`)

Pinned: `IND_AS` iff the `schemaRef` href file name starts with `in-capmkt-ent-` **and** the
instance's `in-capmkt-ent` namespace is the `IntegratedFinance_IndAS` one (§2). The file-name prefix
alone also matches bank instances (§2), which are not Ind AS. Financial issuers are refused before
settings are derived, so for any admitted issuer both conditions hold.

## 4. Anchor reachability (D2, D4.2)

| Surface | Result | Evidence |
|---|---|---|
| NSE `EQUITY_L.csv` | 200; 183,984 B; columns as probe Q1; EQ rows for all four test issuers | `master/EQUITY_L.csv` `474ad748f65c9ffa4cf9aa2e483117dfd0f68ccafd6c4c8a0cca02583556f765` |
| NSE `corporates-financial-results` (legacy) | 200 for HDFCBANK, BAJFINANCE, SBILIFE, HDFCLIFE | files cited in §2; `requests.json` |
| NSE `integrated-filing-results` | 200 for 4 test + 11 dev issuers | e.g. `bank-HDFCBANK/nse-listing/integrated-filing-quarterly.json` `af7184cdd549d802978f824fad8685bbd949eaf19f744eca568c76f677beb845`; `nbfc-BAJFINANCE/…` `f7be96764b43c335486d5de5b847fb327ad4aaf027f29ca18827f4422b0515a5`; `insurer-HDFCLIFE/…` `8b016fac431f8ba1d50641f666d2b24ad9ad64c5eaaeeb205d01bc2cd8837d9e` |
| NSE XBRL instance (`nsearchives…/corporate/xbrl/`) | 200 for all 18 instances | §2 |
| BSE `PeerSmartSearch` by ISIN | 200; exactly one `<li>`, ISIN and scrip equal the filing's `ScripCode` | `bank-HDFCBANK/bse/PeerSmartSearch-INE040A01034.html` `9375eb21c854c0c23c20f3aa38d37c378060633fa7e11cc876e09c34c4979f88` (500180); `nbfc-BAJFINANCE/bse/PeerSmartSearch-INE296A01032.html` `61dbae2030795e8d906f3018cd64b72f0d5098d9b42854a10c25a3225742581b` (500034); `insurer-HDFCLIFE/bse/PeerSmartSearch-INE795G01014.html` `2641573518b255772dcc972fc1cd155556a45640c5b3daa2829d3121dde1b5ce` (540777); `insurer-SBILIFE/bse/PeerSmartSearch-INE123W01016.html` `183538b2b93cbdebcbf3a37ca4d612c1778cdc83189c9091acdd44398461d3da` (540719) |

## 5. Unit table and prediction (D1.4)

Vendor reachability is from the capability probe, retained under `probe-evidence/`:
`vendor_search.json` `78d2e1104a91af51a4dc336b95631ba54c141a6b29c8520608ab4069c88baa25`
(Screener and Tijori search 200), `vendor_search_cardinality.json`
`3a6b570996d475b6a3512ba4fb91b2ffc55180dbf7cb7b57c8a983b2966cedfd`, `q4_upstox_instruments.json`
`2c0c5e54a12b5090bffecc314d907c024549d005bc062c0ec0b8be50a99e961c`, `REPORT.md`
`941d1fde0b1785fefb99239a2ecaca09a5acc96fa851d9199cbcfb81bd07ae0f`; plus retained Apar captures:
Screener consolidated page `data/raw/watchlist/screener-financials/APARINDS/consolidated/screener_financials_page.raw.html`
`34f46c0ea9e37d58a5c23c5fd4fd6f2d3bee93cd37a819e79a41d14b2a4768bc`; Tijori financials page
`data/raw/snapshots/v1/tijori/financials/apar-industries-limited/20261014T092203.484096Z-ea59098cc0df/body.bin`
`ea59098cc0df17eea9ce408f319e84332176c2f84479649357bd026f8c992a08` (HTTP 200); Upstox instrument file
`data/raw/upstox/instruments/complete/20260904T082842Z-459ec0544e40/upstox_instruments.raw.json.gz`
`459ec0544e40c4289fd1fdb007612f4db59f46604504988569a48a262ea087dd`; Upstox consolidated quarterly
statement (`status success`, `type consolidated`, non-empty `full_statement`)
`data/raw/snapshots/v1/upstox/income-statement/default-3acbf55d982a3ba6440218b0/20261014T092123.626790Z-c83a9f0b1b07/body.json`
`c83a9f0b1b072f6168e40a53555e8759e683585136763365432bf50a29c21e62`. `RESULTS_PDF` is excluded by
ruling R-PDF (generic PDF parse 0/10, `probe-evidence/q6_generic_pdf.json`
`6b867108d91057e1e14da095d9a4d2a97984fe4d81c25a0acf4ed09451aff80b`).

The capability table (the only YAML block in this file; a unit maps to `reachable` or to
`{excluded: <ruling|evidence>}`):

```yaml
units:
  EXCHANGE: reachable
  XBRL_ENTITY: reachable
  SCREENER: reachable
  TIJORI: reachable
  UPSTOX: reachable
  RESULTS_PDF: {excluded: R-PDF}
```

D1.4 applied: `excluded = [RESULTS_PDF]`; `diagnostic_excluded = []`; `outcome = PARTIAL`;
`run_status = INCOMPLETE`. Identical for every candidate; matches the plan's R-OUTCOME.

## 6. Configuration pin

`ONBOARDING_VERSIONS = ConfigVersions(dictionary="v2", mapping_set="v5")`. `config/mappings/v5.yaml`
`8666d58a1a151ad8493f5a9727bb278f6ea93aadb6802a9f2e7c2dd61987d459` = v4 + the SEBI in-capmkt
2026-01-31 taxonomy; `config/dictionary/v2` exists. Every development instance in §2 uses the
2026-01-31 taxonomy.

## 7. Request shapes and rights per surface

Rights files: A05-DECISION-004 `docs/evidence/phase-0a/a-05-rights-decision-004-private-use.md`
`1327a4bd594f82b768c0816e1ac4937148c67d30d60bb887b0d7d2ce6518573b`; A05-DECISION-005
`docs/evidence/phase-0a/a-05-rights-decision-005-subscriber-scraping.md`
`a5dff320d825b5ffd3994db42020d74b47876e5bf2029ac4f9020c7971ea68eb`; Upstox rights record §7
`docs/research/upstox-rights-record.md` `2034f0a25fbd848fd170f2a3341dae224158933cc96ba8314ba757854ae3b777`;
current vendor table `src/fundamentals/contracts/source_catalog.py:196–239`
`02d9306ca2f4d037f3375f067e891e7d3adfc0bf8c27138958141927b998ce76`.

| Unit | Surface | Request | Auth | Role (D4.4) | Rights | Sample |
|---|---|---|---|---|---|---|
| EXCHANGE | NSE `EQUITY_L` | `GET https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv`, `User-Agent` | none | IDENTITY | A05-DECISION-004 | `master/EQUITY_L.csv` |
| EXCHANGE, basis | NSE legacy listing | `nse` client `_req GET https://www.nseindia.com/api/corporates-financial-results?index=equities&period=quarterly&symbol=<SYM>` (as `NseXbrlSource`) | NSE cookies (client) | IDENTITY | A05-DECISION-004 | `*/nse-listing/financial-results-quarterly.json` |
| EXCHANGE, basis | NSE integrated listing | `nse` client `_req GET https://www.nseindia.com/api/integrated-filing-results?index=equities&symbol=<SYM>&period=Quarterly` | NSE cookies (client) | IDENTITY | A05-DECISION-004 | `*/nse-listing/integrated-filing-quarterly.json` |
| XBRL_ENTITY | `nse-indas-xbrl-consolidated` / `NSE_XBRL_INSTANCE` | `GET <row.xbrl>` on `https://nsearchives.nseindia.com/corporate/xbrl/…xml` (row: `type = Integrated Filing- Financials`, `consolidated = Consolidated`) | none | FIRST_PARTY | A05-DECISION-004 | `*/nse/*.xml` |
| EXCHANGE | BSE `PeerSmartSearch` | `GET https://api.bseindia.com/BseIndiaAPI/api/PeerSmartSearch/w?Type=SS&text=<ISIN>`, headers `User-Agent`, `Referer: https://www.bseindia.com/`, `Origin: https://www.bseindia.com`, `Accept: application/json, text/plain, */*`; body is a JSON string of raw `<li>` HTML | none | IDENTITY | A05-DECISION-004 | `*/bse/PeerSmartSearch-*.html` |
| SCREENER | search | `GET https://www.screener.in/api/company/search/?q=<NSE symbol>&v=3&fts=1` → `[{id,name,url}]` | session (optional) | IDENTITY | A05-DECISION-005 | `probe-evidence/vendor_search.json` |
| SCREENER | `screener-subscriber/SCREENER_FINANCIALS` | `GET https://www.screener.in/company/<SYM>/consolidated/` | session | INDEPENDENT_VENDOR (existing) | A05-DECISION-005 | Apar page above |
| TIJORI | search | `GET https://www.tijorifinance.com/api/v1/ind/company_search/?q=<ISIN>` → `[{name,slug,type}]` | session | IDENTITY | A05-DECISION-005 | `probe-evidence/vendor_search.json` |
| TIJORI | `tijori/financials` | `GET https://www.tijorifinance.com/company/<slug>/financials/` (`company_details.symbol`) | session | INDEPENDENT_VENDOR (existing) | A05-DECISION-005 | Apar capture above |
| UPSTOX | instrument file | `GET https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz` | none | IDENTITY | Upstox §7 | instrument file above |
| UPSTOX | `upstox/income-statement` | `GET https://api.upstox.com/v2/fundamentals/<ISIN>/income-statement?type=consolidated&time_period=quarterly&fs=true` | bearer token | DIAGNOSTIC (existing) | Upstox §7 + data spec | Upstox capture above |
| RESULTS_PDF | — | never requested (R-PDF) | — | — | — | — |

## 8. Open issues

1. **Rights wording (not a halt).** A05-DECISION-004's scope names the wrapper libraries
   (`nse`, `bse`, …) and crawl4AI. Plan D2 fetches `EQUITY_L`, the XBRL instance and
   `PeerSmartSearch` with plain urllib, the last with browser `Referer`/`Origin` headers because the
   `bse` library is 403'd (probe Q2). This is not fingerprint spoofing or any evasion the decision
   excludes, but the owner should confirm the scope covers it; this task used the same shapes.
   Orchestrator ruling (2026-10-16): covered — public endpoints, the same-origin headers the
   exchange's own page sends, low volume, no auth or rate-limit bypass; the owner may revoke.
2. **Frame classification is NSE's, not verified per company.** `Financial Services` is the only
   finance value; whether every financial issuer sits under it was not checked (that would mean
   reading non-financial rows). A financial issuer filed under another value would be drawn and
   then refused by §2 at onboarding, so the run would differ from the prediction (Q2 burn). This is
   an inference about NSE's taxonomy, not something observed.
3. **Insurer taxonomy year.** Both life-insurer instances (2026 filings) still use the 2025-01-31
   `IntegratedFinance_LI` namespace. No effect on the rule (any non-`IndAS` namespace refuses).
   General insurers (`GI`?) were not sampled; under fail-closed they are refused either way.
4. **Bank filings name the issuer in `in-capmkt:NameOfBank`, not `NameOfTheCompany`** (§2 bank
   instance). This only matters if the financial rule ran after the name check; D4.2 runs it at
   step 4, before vendor steps, so T3 fixtures should expect `FINANCIAL_OR_UNKNOWN_SECTOR`, not a
   name `CONFLICT`. The implementer should confirm that `xbrl_entity_state` cannot fire first on
   these fixtures.
5. Vendor reachability for an arbitrary held-out company is per-company (probe Q4c); a vendor
   `UNAVAILABLE` at acquisition is a failed attempt under R-OUTCOME, not a revised prediction.
