# Stage 1 retained-source inventory — 2026-10-13

Status: source-checked working inventory; not a frozen manifest or Stage 1 approval.
Scope: the existing `data/raw/watchlist/` bytes only. No source acquisition, raw edits,
credentials, database registration or owner financial decisions were performed for this inventory.

Authority: [current D1b plan](../../workstreams/data-foundation/plans/D1b.md), Task 1;
[approved data specification](../2026-10-11-canonical-financial-data-and-cross-source-comparison.md),
§2–§5 and Stage 1; [dictionary manifest](dictionary-v1-manifest.md), Deferred to D1b;
[original coverage inventory](../../research/canonical-field-coverage-inventory.md), §2f and conflicts.
The original inventory is a research pointer, never proof that its old measurements are
reproduced by the presently authorized bytes. The current dictionary baseline is 259 rows.

## Acquisition, authority and clocks

[A05-DECISION-004](../../evidence/phase-0a/a-05-rights-decision-004-private-use.md)
permits first-party exchange collection/retention/internal processing within its private personal
boundary; [A05-DECISION-005](../../evidence/phase-0a/a-05-rights-decision-005-subscriber-scraping.md)
permits the owner's subscriber Screener/Tijori surfaces under the same boundary. Neither
permission establishes capture authenticity, source independence or a specific mapping's equivalence.
Upstox has no retained capture here; the data specification treats its statements as diagnostic
because of shared Screener lineage. This inventory does not grant a new source/surface authority.

Apar's `data/raw/watchlist/aparinds/retrieval-manifest.json` records named URLs, hashes,
publication claims and retrieval timestamps. All 23 XML/PDF files match their manifest hashes;
there are no unmanifested XML/PDF files in that directory. The manifest cites A-02 v2 and
[A02-ATTEST-002](../../evidence/phase-0a/a-02-analyst-attestation-v2.md), whose analyst-suitability
scope is Apar Q2 FY26–Q1 FY27. That attestation is not a general ten-company analyst approval.

For the ten-company filings, file contents establish the declarations below, but no per-file
retrieval manifest was found under their authorized directories. Filename dates, PDF letter dates,
filesystem mtimes and source publication are not capture/first-seen or registration receipts.
The Screener `fetched_at` timestamps below are retained metadata claims, not protected receipts.
**Store first-seen is unknown in this inventory.** Any new registration must use the real
`eqos.store_now()`; never backdate to those September timestamps. Publication time is unknown
where no trusted publication record exists; absence of local bytes is `UNAVAILABLE`, never
`NOT_PUBLISHED`. Missing approved authority is `NOT_AUTHORISED`, separately from acquisition failure.

## Screener financials

Exactly ten basis directories exist: nine consolidated, NETWEB standalone. Each contains one
raw HTML page, six derived section JSON files, fifteen raw schedule JSON files and one metadata
JSON file: 10 HTML + 220 JSON overall. All ten raw HTML SHA-256 digests equal their metadata pins.
Every quarterly section retains a `Dec 2024` column. This proves retained columns, not fiscal
period start, issuer equivalence or qualified agreement. Annual labels and TTM remain distinct.
Each source surface is independently mapped and checked; a package-wide flag cannot override
an unverified schedule. JSON sections are derived from HTML; raw schedules are separately retained
responses and need their own content pins.

| Symbol | Retained basis | Raw HTML SHA-256 | Metadata capture claim | Metadata verified; unverified surface |
|---|---|---|---|---|
| CGPOWER | consolidated | `933d7c5f1e51a70ba810885c6a783bb8974b8c4382aaf4c8900e039402415230` | `2026-09-04T11:05:38.592975Z` | false; cash-flow/Cash from Operating Activity |
| ETERNAL | consolidated | `afba050b92f56b433cad50b58f2937d44fa135b30dbc7fdd5c0536e6b36adf33` | `2026-09-04T11:06:02.119034Z` | true; None recorded |
| HFCL | consolidated | `4fefad29dfb80061be461597fd6b1bd1150c87ce8d2c59820cfaed4b4291e236` | `2026-09-04T11:04:51.069606Z` | true; None recorded |
| LAURUSLABS | consolidated | `eadb8cbf417fce6e7b7af5eb4643fba2b5fac0cf2c41cc03b363d46340b22411` | `2026-09-04T11:02:46.326660Z` | false; quarters/Net Profit |
| MTARTECH | consolidated | `41dbe14ecf1757f88d516e7875b763bcd6e7eb034d390779ce4874f78993b2c2` | `2026-09-04T11:03:23.027017Z` | true; None recorded |
| NETWEB | standalone | `6199e844cdc0d1d242e412c266154a0b22dc1cdab0cbb2477da85044507f2546` | `2026-09-04T11:07:01.302232Z` | true; None recorded |
| POLYCAB | consolidated | `02daa3131765d6d2bb89a66668379615ac60702ac9b4ccb6f347490859bedea3` | `2026-09-04T11:05:15.009575Z` | false; balance-sheet/Fixed Assets |
| SONACOMS | consolidated | `44347bbbd29a191760059564cd21bed2a7ce53f9091762d5b86125178b68b0a2` | `2026-09-04T11:03:46.633374Z` | false; cash-flow/Cash from Operating Activity |
| THERMAX | consolidated | `6894f0979643755a618a6e8f572dc63ee3efb61abb6495ddf4766d5ec678f0ad` | `2026-09-04T11:04:27.393490Z` | true; None recorded |
| TITAN | consolidated | `98e499bd097bcef85e7a4994d6ad79a3af8b18c4e3f455734349f7368d362a83` | `2026-09-04T11:06:37.769575Z` | true; None recorded |

Paths are `data/raw/watchlist/screener-financials/<SYMBOL>/<basis>/screener_financials_page.raw.html`
and sibling `screener_financials_meta.json`. All metadata says `complete=true`, all fifteen schedule
families fetched, none refused. Four packages nevertheless say `verified=false` with the exact
surface above. These flags are retained parser claims; preserving them is not requalification.
Financial table headings declare crore scale and consolidated/standalone context. Ratio/EPS rows
retain their own percent/day/per-share units; do not apply crore scale or inferred precision to them.

Identity anchors include the raw HTML exchange-profile links. In particular, ETERNAL's HTML
links BSE code **543320** while its Q3 filing XML declares **ZOMATO**. The retained Zomato PDF
p1 independently states BSE543320 and ISIN INE758T01015, providing an explicit exchange-code
bridge to record with its evidence. Never join by directory name or silently replace the
historical XML's NSE symbol. Per-surface identity/basis still needs the runtime admission checks.

## Ten-company first-party anchors

Each of the nine primary XMLs declares its listed symbol, `Consolidated`, start dates
2024-10-01 and 2024-04-01, and end 2024-12-31. The quarter and nine-month contexts are distinct.
The PDF cover/result context p1–2 states the December 2024 reporting window; nine cover letters
or statements mention standalone and consolidated, while NETWEB explicitly states standalone.
These are package anchors, not a claim that every numeric line or every later PDF page was qualified.
NETWEB's approved standalone-only refusal is source/spec scoped; its retained standalone filing
alone does not prove that every absent consolidated vendor response says not published.

| Scope | Source declaration / locator | Retained path and SHA-256 |
|---|---|---|
| CGPOWER | CGPOWER | `data/raw/watchlist/cgpower/nse/INDAS_117955_1364192_29012025010421.xml`; `8e42116c743bf1dc2a298c0d133efa26b93f27fa07bc953f88f34baddc0fc16a` |
| CGPOWER PDF | p1–2 cover/result context | `data/raw/watchlist/cgpower/bse_pdf/af476a81-837f-412c-8cca-5f2e583b49a4.pdf`; `68a3caff6d02babbd9c2731d23311a4786cbd296e3677f78d8f7a189cf1a2e7e` |
| ETERNAL | ZOMATO | `data/raw/watchlist/eternal/nse/INDAS_117408_1353522_20012025062858.xml`; `d386a46527d775df1d9dcbc4d324360722ca30baf25d07efa9a23b6d9b8359fd` |
| ETERNAL PDF | p1–2 cover/result context | `data/raw/watchlist/eternal/bse_pdf/189f6577-91c3-4738-abf1-dc3f9c68de6b.pdf`; `bac409da254d2f5b8d8aa6ebcd3a721f12b2352a485f0cdaca24b4b775609c1a` |
| HFCL | HFCL | `data/raw/watchlist/hfcl/nse/INDAS_118544_1369950_04022025012501.xml`; `a390ccfad8d61019d6f1db400ab5d3ab7c1181c38246468d8904a43b5eeec3db` |
| HFCL PDF | p1–2 cover/result context | `data/raw/watchlist/hfcl/bse_pdf/96c4fe56-2f6d-4d2f-b511-718f612e8b05.pdf`; `d7e71dc06e62124cad2288be4d5cf6bcffd7632f71fb72d06df618c692158f4f` |
| LAURUSLABS | LAURUSLABS | `data/raw/watchlist/lauruslabs/nse/INDAS_117690_1360957_24012025084417.xml`; `2d50d29a467b9035f8124f7a9576346b7d36888e9895befc3363e3c5d227cfa6` |
| LAURUSLABS PDF | p1–2 cover/result context | `data/raw/watchlist/lauruslabs/bse_pdf/40f6294a-0346-4a9a-9dc8-baf1790984ae.pdf`; `2b79047e7d2e7c4f46eb3dfe56e1aff03d5871b92df1b24e63ffd0cd89c5b517` |
| MTARTECH | MTARTECH | `data/raw/watchlist/mtartech/nse/INDAS_119445_1377020_10022025065704.xml`; `2f42635a245b1e2ef9e05ad9cc6f21bbf7b77d9c8b77d59b74673503eba0e822` |
| MTARTECH PDF | p1–2 cover/result context | `data/raw/watchlist/mtartech/bse_pdf/901e434d-85df-4ab9-bffb-ce641d973099.pdf`; `ed8099172e25c813c12fc44f1542dce6fe2378288e855b36d5af3b5678503d0c` |
| NETWEB | NETWEB (PDF) | No retained XML |
| NETWEB PDF | p1–2 cover/result context | `data/raw/watchlist/netweb/bse_pdf/b0e5bb4f-ff37-4094-8983-1bbe721a851f.pdf`; `122ca4cc7fafc72f3c96dce0f30d42b618f78b272bac2c64cde1589cc258ab3a` |
| POLYCAB | POLYCAB | `data/raw/watchlist/polycab/nse/INDAS_117488_1357164_22012025051528.xml`; `05ebba47a2a07015f107cc9ca3a616138e4a78b900f43074cbfd489db011518d` |
| POLYCAB PDF | p1–2 cover/result context | `data/raw/watchlist/polycab/bse_pdf/b60596af-4d43-4ef7-8c7b-9c6145b87097.pdf`; `8602f194f97ca8f045f2c878c9c3a7e111bc73f1398a9e2ba5c0bb2a8b10a71c` |
| SONACOMS | SONACOMS | `data/raw/watchlist/sonacoms/nse/INDAS_117581_1359784_23012025083325.xml`; `c2e5b2bde74f631b47ff203a721e1a995bc135692e6b6c23d64bc1a0a75831fc` |
| SONACOMS PDF | p1–2 cover/result context | `data/raw/watchlist/sonacoms/bse_pdf/e23c0bd4-b922-4702-92b1-9fb4ab0a0a45.pdf`; `0ce43a604a1622e3ae28b49a7ed552e756fb80190a830f64df7e5f5e0fa16ee7` |
| THERMAX | THERMAX | `data/raw/watchlist/thermax/nse/INDAS_118568_1370145_04022025030939.xml`; `36d79235f8ab475c3206dd90137bd707e55446e26ba4979dd9f0a039bf33980d` |
| THERMAX PDF | p1–2 cover/result context | `data/raw/watchlist/thermax/bse_pdf/f7a48138-a78e-4666-82fa-2138e2a9d7fa.pdf`; `9554c06ceb43f0f24d4536aeebc8cfecdb6324d3cfea270e403085f490c99c43` |
| TITAN | TITAN | `data/raw/watchlist/titan/nse/INDAS_118668_1371012_04022025105441.xml`; `09dbeb46c6edfe31be0cbbd1c55e5861d247cacba040b855737a51841cd771c1` |
| TITAN PDF | p1–2 cover/result context | `data/raw/watchlist/titan/bse_pdf/d4ddb6ee-2cb7-4dae-b39e-145601dc47b4.pdf`; `7248bdacf5f4b20b07612a370850cb16e5b8f9bffe20c3ddc4f2fb6e6bc983bc` |

ETERNAL and POLYCAB also retain two XML comparative files each under `nse/comparatives/`:
2024-07-01–2024-09-30 (QoQ), 2023-10-01–2023-12-31 (YoY); their XML period declarations were
checked. They are separate captures/packages, never substitutes for the Q3 capture identity.

## Apar package anchors

All eight XMLs declare APARINDS and consolidated reporting. Each quarter end matches the
manifest's named period; half-year/nine-month/annual contexts also survive separately. The four
integrated XMLs for Q2 FY26 through Q1 FY27 carry ISIN INE372A01015. The raw-results PDF hashes
below are manifest-bound; numeric selection remains subject to D1a's basis/layout/ambiguity checks.

| Quarter | Retained path | SHA-256 | Manifest retrieval claim |
|---|---|---|---|
| FY26_Q2 | `data/raw/watchlist/aparinds/nse/INTEGRATED_FILING_INDAS_1560713_29102025085858_WEB.xml` | `90baae0babfa7724e652def20f613efbf33bdadbbbe545e97ff77617d467d799` | `2026-09-06T15:31:21.335436+00:00` |
| FY26_Q3 | `data/raw/watchlist/aparinds/nse/INTEGRATED_FILING_INDAS_1613642_29012026072210_WEB.xml` | `87a5dd9583b582132c7c42c9cb6edcbc799372e3772efab19a0ba440f4fcc548` | `2026-09-06T15:31:24.906896+00:00` |
| FY26_Q4 | `data/raw/watchlist/aparinds/nse/INTEGRATED_FILING_INDAS_1675395_28052026085114_WEB.xml` | `be8ef6514df9d4ba25265ace74b85eb476d1f0a7891356a8319458d99f73bf01` | `2026-09-06T15:31:27.933204+00:00` |
| FY27_Q1 | `data/raw/watchlist/aparinds/nse/INTEGRATED_FILING_INDAS_1701114_24072026063426_WEB.xml` | `f76a131abb5fdb796a8e579848c6036f04181c38f88b05e3a5317f4820124a85` | `2026-09-06T15:31:30.984308+00:00` |
| FY27_Q1 | `data/raw/watchlist/aparinds/nse_pdf/APARINDS-FY27_Q1-results.pdf` | `c0c2b2fa5510a776331c2092f03301c65dbea5a98ee42ecbc31f768513278612` | `2026-09-06T15:31:44.167872+00:00` |
| FY26_Q4 | `data/raw/watchlist/aparinds/nse_pdf/APARINDS-FY26_Q4-results.pdf` | `17f5bc047416a795ecdf8c9be5c09ff1699d00cb2feed885bf2a2e43a2d4a377` | `2026-09-06T15:31:50.624486+00:00` |
| FY26_Q3 | `data/raw/watchlist/aparinds/nse_pdf/APARINDS-FY26_Q3-results.pdf` | `2f9c6d5a0c1d6394276602c97a08bd1624ea5e61197a57a1d95d260db6383699` | `2026-09-06T15:32:00.494360+00:00` |
| FY26_Q2 | `data/raw/watchlist/aparinds/nse_pdf/APARINDS-FY26_Q2-results.pdf` | `8be1b8de71997d30f2dccd78cfc42d87c5564e2ab16357ca611763c1f3784ae5` | `2026-09-06T15:32:12.221708+00:00` |
| FY25_Q2 | `data/raw/watchlist/aparinds/nse/INDAS_113920_1293440_30102024104705.xml` | `c44ac3766fedbf697bb91551d55c59015a3253bac99ec95ff03f1bc7795b9d60` | `2026-09-07T04:05:40.301807+00:00` |
| FY25_Q3 | `data/raw/watchlist/aparinds/nse/INDAS_117941_1363971_29012025110018.xml` | `3ba61227e3341d1540504070c663eafe754f8b38fe918345a288fc4417337e5f` | `2026-09-07T04:05:42.404899+00:00` |
| FY25_Q4 | `data/raw/watchlist/aparinds/nse/INTEGRATED_FILING_INDAS_1439170_14052025093124_WEB.xml` | `943873742981759927022eb5963d1ed0a4e1d2fe2aac8d9feda0fcf3c64f4cc2` | `2026-09-07T04:05:41.708750+00:00` |
| FY26_Q1 | `data/raw/watchlist/aparinds/nse/INTEGRATED_FILING_INDAS_1496866_29072025062446_WEB.xml` | `a3c8d9d60e82ac1a0a8eaec0fdbb894155c7ff69db00eed91e454b8f153f2de1` | `2026-09-07T04:05:42.301527+00:00` |

The other eleven PDFs are four presentations, four transcripts and three press releases.
Each of the three press releases is byte-identical to the corresponding FY26 results PDF;
retained filename/kind/URL provenance survives, but equal content is not independent corroboration.
Manifest publication strings must be normalized with their evidenced timezone, never inferred
from a filename or confused with retrieval time. The older comparator quarters retain their own
manifest entries and are not covered by the newer-period analyst attestation by implication.

## Deferred construction dispositions

Evidence aliases below bind the exact retained artifacts. THERMAX is a locator example, not a
five-company qualification. Raw JSON schedules preserve labels and values; the six section JSONs
are parser-derived and are corroborated against the pinned HTML page above.

| Alias | Retained artifact | SHA-256 |
|---|---|---|
| S-BOR | `data/raw/watchlist/screener-financials/THERMAX/consolidated/schedules/balance-sheet__borrowings.raw.json` | `2071fbca448cd6c4e43c765c6b3905982edfcb0baa866e2d22f856ccf56bf685` |
| S-NP | `data/raw/watchlist/screener-financials/THERMAX/consolidated/schedules/profit-loss__net-profit.raw.json` | `ccde10e1c27103c85ee06b91ebff6ff926f5bb3e7a38488cd5829fb34d124472` |
| S-CFI | `data/raw/watchlist/screener-financials/THERMAX/consolidated/schedules/cash-flow__cash-from-investing-activity.raw.json` | `b05cb0dd276de5342a113f0948a7d75e034a28eff79bf9e616cb819e322572f0` |
| S-RAT | `data/raw/watchlist/screener-financials/THERMAX/consolidated/section_ratios.json` | `95be8323b1deb79a78a95818823077969d187ef3a41549797aaf5c3a5714dbe8` |
| S-PL | `data/raw/watchlist/screener-financials/THERMAX/consolidated/section_profit-loss.json` | `71923a25f63c412a19b47e018ce19a9ff870344e1ce50d3fe672e7565fe2fea5` |
| S-OI | `data/raw/watchlist/screener-financials/THERMAX/consolidated/schedules/quarters__other-income.raw.json` | `0c1e9a845f10676637d9a01d8dd864a0839e41da4a625e350d5cb3210f98530a` |

All seventeen ids are explicitly `EXCLUDED_UNPROVEN` **from the next dictionary's additions**.
Their native occurrences/labels remain retainable and reportable as unmapped or unproven evidence;
this disposition does not erase source rows, redefine a formula or reduce Stage 1's acceptance scope.
No construction here has a source-bound five-distinct-company qualification with at least one
discriminating case, resolved operands and explicit fiscal/stock roles. Old research measurements
or a numeric coincidence do not satisfy that gate.

| Deferred canonical id | Disposition | Source locator | Exact unresolved construction |
|---|---|---|---|
| `borrowings_total` | `EXCLUDED_UNPROVEN` | S-BOR; Long term Borrowings / Short term Borrowings / Lease Liabilities / Other Borrowings | All ten schedules retain these labels; ETERNAL, HFCL and LAURUSLABS also retain Preference Capital. No evidenced canonical definition settles other borrowing/preference composition and lease treatment; a schedule sum alone does not identify the first-party aggregate. |
| `ebit_vendor` | `EXCLUDED_UNPROVEN` | S-PL row2 Operating Profit and row6 Depreciation; inventory §2f EBIT | Retained Screener labels do not publish an EBIT construction. The cited Tijori formula requires its unresolved Operating_profit operand; no authorized Tijori bytes are present. |
| `profit_excl_exceptional` | `EXCLUDED_UNPROVEN` | S-NP keys Exceptional items AT and Profit excl Excep | Vendor labels and values survive; after-tax exceptional-items construction and its relationship to filed pre-tax exceptionals are unevidenced. Never substitute pre-tax amount. |
| `profit_for_pe` | `EXCLUDED_UNPROVEN` | S-NP key Profit for PE | No published construction resolves owners profit, exceptional adjustment and other vendor adjustments. Numerical similarity is insufficient. |
| `free_cash_flow` | `EXCLUDED_UNPROVEN` | S-CFI keys Fixed assets purchased / Fixed assets sold / Other investing items; inventory §2f FCF | Gross versus net capex and its asset scope remain unresolved; the retained schedules do not publish the formula. Tijori Net Capex (est) bytes are unavailable. |
| `roce_pct` | `EXCLUDED_UNPROVEN` | S-RAT row5 ROCE %; S-PL row2 Operating Profit | A printed annual percentage does not establish the numerator, other-income treatment or closing versus average capital-employed role; Tijori formula proof is unavailable. |
| `roe_pct` | `EXCLUDED_UNPROVEN` | Retained page top ROE; inventory §2f ROE/ROA | No source-declared profit attribution, equity composition or average/closing role. A displayed percentage is native vendor evidence only. |
| `roa_pct` | `EXCLUDED_UNPROVEN` | Inventory §2f Return on Assets (%); authorized vendor roots | No retained Tijori or Upstox response; no ROA construction found in the six retained Screener financial sections/schedules. This is local unavailable evidence, not publication absence. |
| `debt_to_equity` | `EXCLUDED_UNPROVEN` | S-BOR; inventory §2f Debt to Equity Ratio | Debt definition depends on unresolved borrowings_total; equity/NCI/preference treatment and stock role are unstated. No retained Tijori response establishes the construction. |
| `interest_coverage` | `EXCLUDED_UNPROVEN` | S-PL row5 Interest; inventory §2f Interest Coverage Ratio | Interest label does not resolve finance-cost scope, and EBIT numerator remains unresolved. No executable canonical construction is justified. |
| `current_ratio` | `EXCLUDED_UNPROVEN` | Inventory §2f Current Ratio; authorized vendor roots | No retained financial-section formula; named Tijori ratio is unsupported by authorized bytes. Current-asset/liability definitions and stock role remain unproven. |
| `quick_ratio` | `EXCLUDED_UNPROVEN` | Inventory §2f Quick Ratio; authorized vendor roots | No retained Tijori/Upstox response or explicit quick-assets exclusions/stock role. A conventional textbook definition cannot be substituted. |
| `dividend_payout_pct` | `EXCLUDED_UNPROVEN` | S-PL row11 Dividend Payout % | Native annual percentage exists across retained pages, but dividend timing, earnings attribution and denominator construction are unstated. |
| `inventory_days` | `EXCLUDED_UNPROVEN` | S-RAT row1 Inventory Days | Native annual days exist; average versus closing inventory, cost denominator and day-count convention are unspecified. |
| `payable_days` | `EXCLUDED_UNPROVEN` | S-RAT row2 Days Payable | Native annual days exist; payable scope, denominator and stock role/day count are unspecified. |
| `cash_conversion_cycle_days` | `EXCLUDED_UNPROVEN` | S-RAT row3 Cash Conversion Cycle | Native annual days exist; displayed components do not publish the construction or settle their own unresolved definitions. |
| `working_capital_days` | `EXCLUDED_UNPROVEN` | S-RAT row4 Working Capital Days | Native annual days exist; working-capital composition, numerator temporal role and revenue denominator/day count are unspecified. |

The approved specification's separate Screener Other Income bridge is **not** one of these
seventeen unresolved definitions: §2 explicitly states `other_income + exceptional_items`.
The actual v1 operand id is `exceptional_items_before_tax`. A v2 derived row
`other_income_incl_exceptional` can declare that exact signed construction, while its vendor
mapping tier remains source/scoped and unproven until measured. Preserve the two original
first-party rows; do not equate vendor Other Income with `other_income` alone.

## Supportable work and parked acceptance

Available now: source-qualified Screener retained intake, separate raw schedule/page pins,
unknown-publication and actual-registration clocks, scope-specific validation of the four unverified surfaces,
source-derived construction drafts explicitly unproven, queue/corroboration/diagnostic rule
fixtures and append-only generation/replay integration. Synthetic fixtures may prove dynamic
rules but never supply missing real vendor qualification, frozen-oracle values or approvals.

| Stage 1 obligation | Current disposition and reason |
|---|---|
| Apar first-party tracer across retained package periods | Supported by original bytes; D1a verification/review remains required |
| Apar Screener opex qualification | Parked: no APARINDS Screener financial capture in the authorized root |
| Nine-company Tijori qt_c PAT remeasurement at displayed precision | Parked: no retained Tijori response; old research numbers cannot be promoted |
| THERMAX revenue anomaly against both independent vendors | Screener candidate retained; complete pair of vendor measurement proofs parked without Tijori |
| Real Upstox diagnostic agreement/disagreement and conflicting surfaces | Parked: no retained Upstox response; shared-lineage diagnostic routing can be implemented/tested separately |
| NETWEB degenerate consolidated Screener and empty consolidated Upstox response | Parked: neither negative response is retained; standalone scope refusal remains implementable |
| Shareholding exchange/Screener/Tijori happy-path evidence | Parked for this inventory: the retained financials directories are not source-bound exchange/Tijori shareholding captures |
| Fully sourced eleven-company frozen manifest and approval | Parked: missing vendor obligations and actual independent approval; no reduced manifest substitutes |
| INCOMPLETE/diagnostic trust/queue lifecycle fixtures | Dynamic behavior can be built now; retained-source acceptance and final decisions still require their stated evidence/approval boundaries |

This inventory may support the prerequisite's cited-exclusion alternative once independently
reviewed. It does not close vendor mappings, the frozen-manifest stage, D1b or the full project.
