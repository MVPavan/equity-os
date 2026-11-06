# ICICIBANK grounding record

VENDOR-1 Phase 3 Task 2 (`docs/plans/VENDOR-1-P3.md`), bead eqos-awnc. This record is the
evidence for branches B1–B8 and B10. It proposes the arm each branch's evidence supports. Task 3
fixes the arms by citing these lines; nothing here is a ruling. B9 is pending until Task 12.

## Provenance

- **Issuer and evidence.** Every claim and locator below cites an ICICIBANK capture from grounding
  generation 1 (`data/raw/five-company/ICICIBANK/gen-1`). No claim rests on earlier HDFCBANK
  fixtures. HDFCBANK enters Phase 3 in two places only: the plan's B4b example (`NameOfBank`),
  and Task 1's replay test, which uses the retained HDFCBANK dev fixtures as a stand-in bank. This
  record observes `NameOfBank` in ICICIBANK's own instances (B4). Where a claim compares
  ICICIBANK with "Ind AS filers", the comparison cites repository code, not a capture.
- **Generation.** `gen-1`, as of 2026-11-06, authorization `VENDOR-1 §8 step 1 grounding`. It
  holds 11 requests, all `OK`. The manifest `discovery-manifest.json` has sha256
  `520efe09d5ab2b744add134cf6f6de62b1ba43a5a3a8e90926b4959d70683c92`. The folder digest (sorted
  path and sha256 list) is `93f2019267029aefecced59689b348cece4b9fc078fe30904690eb827762c9cd`.
- **Runs.** Code revision `9aef44d4`. Acquisition ran once, 2026-11-06 11:55:41Z–11:56:16Z UTC
  (the capture ids' retrieval times), against a throwaway restore. The rehearsal replay ran on a
  fresh restore (12:02:26Z–12:03:02Z). The live replay ran 12:04:08Z–12:04:44Z, exit 0.
  **Grounding completed on live at 2026-11-06T12:04:44Z**; the last capture was registered at
  12:04:43.654808Z. The live delta equals the rehearsal's: 11 rows each in `capture_refs`,
  `capture_addresses` and `retention_classes`, and nothing else. The logs are in
  `scratchpad/vendor-first/live-p3-1/`, which is not committed.
- **Structure JSON.** sha256 `568044728a220584a29300eee1a4ed490d5080302a6261c77263ebb053889f85`.
  The rehearsal and live replays produced byte-identical JSON, equal to the acquisition's.
- **Live captures.** Ids 2532–2542 under snapshot root `data/raw/snapshots/v1`. No
  `reporting_entities`, `securities` or `listings` row names ICICIBANK or ISIN `INE090A01021`.

| Live id | Source / surface | Capture sha256 | Request |
|---|---|---|---|
| 2532 | `nse` / `EQUITY_L` | `da7eb83cf21156cca3a8bcc5b94ea55f825ff7348e02c89abc51658788361fa5` | equity master |
| 2533 | `nse` / `FINANCIAL_RESULTS_LISTING` | `4e1df093c60fc8fef4a8ed0f1f3e1bf1940586c937a4920e77b10a13b00a17fe` | legacy listing |
| 2534 | `nse` / `INTEGRATED_FILING_LISTING` | `aa9d084a9a6c65bd3df091f20f14ee23a26a67dd61ca407be0c497b0eaab2d71` | integrated listing |
| 2535 | `nse-grounding` / `NSE_XBRL_INSTANCE` | `615348fca1872145ef64f390d725bc196359c61dec88ddf49f8ab8deb920dc5d` | 2026-09-30 consolidated |
| 2536 | `nse-grounding` / `NSE_XBRL_INSTANCE` | `a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3` | 2026-09-30 standalone |
| 2537 | `nse` / `ANNOUNCEMENTS_LISTING` | `f5a17c905a2d09146fb4b333f877cb18803f485b0b4ee090c5a50357f3c1c025` | 2026-09-30 → 2026-10-24 |
| 2538 | `nse-grounding` / `NSE_RESULTS_DOCUMENT` | `b28a719174d31592413f317e9baf527e4dd127f18b2468179d9cc0bfa74fabd1` | 2026-09-30 results PDF |
| 2539 | `nse-grounding` / `NSE_XBRL_INSTANCE` | `ded5800004dd276f7b81110c4be9ed449eb2c7281ee3bb3e67519cf6448a4cb4` | 2026-06-30 consolidated |
| 2540 | `nse-grounding` / `NSE_XBRL_INSTANCE` | `39677b484f433a34be77c8a1bd241a0d9b66bf17cfd4eedc54ce0dfbaefc62d5` | 2026-06-30 standalone |
| 2541 | `nse` / `ANNOUNCEMENTS_LISTING` | `5009c79950c4fc32884018bb15017393dda14c88167d6aefb44df0648869e477` | 2026-06-30 → 2026-07-25 |
| 2542 | `nse-grounding` / `NSE_RESULTS_DOCUMENT` | `1b3599e2a01fc9b77f913fef7a3068bca6ec43c722010a1c1bc4c01c55033c03` | 2026-06-30 results PDF |

## Data extraction rules

The record cites no amount. Every value it does cite carries a locator: an identifier, a date, a
label, a namespace or a quote. A locator names the capture sha256, the basis, the period, and
either the QName with its `contextRef` or the page with a quote. The locator check confirms each
one in the retained bytes. The check also confirms stated absences: a concept, a phrase or a
marker that does not occur. A page without a text layer would read `NOT_ASSESSED`; neither PDF
has such a page. Nothing is derived, estimated or filled.

## Unresolved and missing items

- **Candidates `UNRESOLVED`:** none. Each (period, basis) has one latest listed row with a
  broadcast time and an instance URL, and no tie.
- **Missing PDFs:** none. Each period has exactly one results-category PDF in its window, and
  both PDFs were retained.
- **Recorded as found:** neither PDF carries the `Scrip Symbol :` marker (B7). No instance
  declares an accounting framework; only the PDFs do (B1, B1′). The June instances use the
  context identifier scheme `http://www.sebi.gov.in/in-capmkt/Symbol` (B4).

## Reading

Locator ids such as `[B4.06]` refer to the Locators section. "Q2" means the period ending
2026-09-30 and "Q1" the period ending 2026-06-30. "C" is the consolidated basis and "S" the
standalone basis.

### B1: framework declaration and its meaning

- No grounded instance states an accounting framework in any fact. A search of every fact's text
  for `accounting standard`, `in accordance with`, `GAAP`, `Ind AS` and `AS 25` finds nothing in
  Q2 C, Q2 S, Q1 C or Q1 S `[B1.01–B1.04]`. The instances' IntegratedFinance form is `Banking`,
  not `IndAS` (B2). The existing structural declaration, the `IntegratedFinance_IndAS` form read
  by `integrated_ind_as` in `member_identity.py`, is therefore absent.
- Each results PDF states the bank's basis of preparation, for both bases. The Q2 standalone
  notes (p7) read: "The standalone financial results hove been prepared in accordance with the
  recognition and measurement principles laid down in Accounting Standard 25 "Interim Financial
  Reporting" ('AS 25'). prescribed under Section 133 of the Companies Act, 2013, the relevant
  provisions of the Banking Regulation Act, 1949, the circulars, guidelines and directions issued
  by the Reserve Bank of India ("RBI") from time to time and other accounting principles generally
  accepted in Indio" `[B1.05]`. The consolidated notes (p16) are to the same effect `[B1.06]`.
  The Q1 standalone notes (p6) name "Accounting Standards prescribed under Section 133 of the
  Companies Act, 2013" without naming AS 25 `[B1.09]`; the Q1 consolidated notes (p13) name AS 25
  `[B1.10]`. Each news release headed its summary "Summary Profit and Loss Statement (as per
  standalone Indian GAAP accounts)" (Q2 p30, Q1 p26) `[B1.07, B1.11]`.
- None of the three `IND_AS` phrases in `FRAMEWORK_DECLARATIONS` occurs in either PDF
  `[B1.13–B1.18]`. "Ind AS" appears in two places only. One is subsidiaries' results: "The profit
  after tax of ICICI Securities, on a consolidated basis, as per Ind AS" (Q2 p29) `[B1.08]`. The
  other is the title of the SEBI format circular: "Revised Formats for Financial Results and
  Implementation of Ind AS by Listed Entities" (Q1 p10) `[B1.12]`. Neither declares the bank's
  own framework.
- **Arm.** The declared framework is accounting standards under Section 133 together with the
  Banking Regulation Act, RBI directions and generally accepted accounting principles in India.
  The releases call this "Indian GAAP". It fits no existing `AccountingFramework` value (`IND_AS`,
  `IFRS`, `US_GAAP`, `UNKNOWN`). By content, therefore, it is B1b. All four notes agree, so it is
  neither ambiguous nor conflicting. The table makes B1 depend on B1′ and B7, however: B1′ is
  **P**, and B7 is **B7b** (below). B7b reads "with B1′ P → B1c". **Under the table as written,
  the supported arm is B1c (stop)**, although the declaration's content is B1b. Task 3 rules on
  this.

### B1′: where the declaration is

- The declaration is in the results PDFs only `[B1.05, B1.06, B1.09, B1.10]`; no instance fact
  states it `[B1.01–B1.04]`. **Arm: P.** P needs B7's identity, period and basis association,
  which B7b does not give (see B7).

### B2: IntegratedFinance form

- Every grounded instance declares the in-capmkt-ent namespace
  `http://www.sebi.gov.in/xbrl/IntegratedFinance_Banking/2026-01-31/in-capmkt/in-capmkt-ent`
  `[B2.02, B2.04, B2.06, B2.08]`. Across all of each instance's namespace declarations, the set of
  IntegratedFinance segments is exactly `{Banking}` `[B2.01, B2.03, B2.05, B2.07]`.
- **Arm: B2a.** All four instances are uncontested `Banking`.

### B3: fact namespace, scope and period concepts

- Every instance's facts are in `http://www.sebi.gov.in/xbrl/2026-01-31/in-capmkt`
  `[B3.01, B3.06, B3.11, B3.16]`. That namespace is registered as
  `IN_CAPMKT_2026_NAMESPACE` in `equity_os/extraction/xbrl/xbrl_taxonomies.py`.
- The registered scope concept `NatureOfReportStandaloneConsolidated` and the period concepts
  `DateOfStartOfReportingPeriod` and `DateOfEndOfReportingPeriod` are used. Each instance carries
  them at `OneD` with its basis and period: Q2 C `Consolidated`, 2026-07-01 to 2026-09-30
  `[B3.02–B3.05]`; Q2 S `Standalone`, the same dates `[B3.07–B3.10]`; Q1 C `Consolidated`,
  2026-04-01 to 2026-06-30 `[B3.12–B3.15]`; Q1 S `Standalone`, the same dates `[B3.17–B3.20]`.
  The Q2 instances repeat the three concepts at `FourD` (2026-04-01 to 2026-09-30); see Facts.
- **Arm: B3a.** The namespace is registered and its scope and period concepts are used.

### B4: identity concepts and identity scheme

- `ISIN` `INE090A01021`, `Symbol` `ICICIBANK` and `ScripCode` `532174` are at `OneD` in every
  instance `[B4.01–B4.03, B4.07–B4.09, B4.13–B4.15, B4.19–B4.21]`. The ISIN equals the equity
  master's row for ICICIBANK `[B4.25]`. All of these are the concepts `filing_identity` reads
  (`equity_os/companies/onboarding/verification.py`).
- **Name concept.** Every instance names the issuer through `NameOfBank` ("ICICI BANK LIMITED"
  at `OneD`) `[B4.04, B4.10, B4.16, B4.22]` and carries no `NameOfTheCompany` fact
  `[B4.05, B4.11, B4.17, B4.23]`. Ind AS filers' name concept is `NameOfTheCompany`, the only
  name that `filing_identity` reads.
- **Context identifier scheme.** Q2 contexts use `http://www.sebi.gov.in/in-capmkt/ScripCode`
  with `532174` `[B4.06, B4.12]`, a seeded scheme (`SEBI_SCRIP_ENTITY_SCHEME`,
  `equity_os/extraction/xbrl/xbrl_identity.py`). Q1 contexts use
  `http://www.sebi.gov.in/in-capmkt/Symbol` with `ICICIBANK` `[B4.18, B4.24]`. That scheme is not
  seeded: the seeded schemes are `http://www.nseindia.com/NSESymbol` and the SEBI and BSE
  `ScripCode` schemes. The Q1 value equals the instances' own `Symbol` fact and the master
  symbol, so the identity does not conflict.
- **Arm: B4b.** Two concepts differ from Ind AS filers: the name concept (`NameOfBank`) and the
  Q1 context scheme (`.../in-capmkt/Symbol`). Every identity value agrees, so this is not B4c.
  For Task 3: the unseeded Q1 scheme is "other concepts", not an unknown identity. If Task 3
  reads an unseeded scheme as "unknown identity", the arm is B4c.

### B5: bases on the listings

- The integrated listing has a `Consolidated` and a `Standalone` `Integrated Filing- Financials`
  row for 30-SEP-2026 `[B5.01, B5.02]` and for 30-JUN-2026 `[B5.03, B5.04]`. Each row's instance
  URL is the instance grounded for that basis.
- **Arm: B5a.** Both bases are listed for both periods.

### B6: collapsed integrated rows' type

- Each (period, basis) collapses to one latest row, with a broadcast time and no tie (Facts). Its
  `type` is `Integrated Filing- Financials` in all four cases `[B5.01–B5.04]`. The listing also
  has `Integrated Filing- Governance` rows for the same periods with no `consolidated` value.
  `listing_rows` keeps only rows with a basis, so these never reach the collapse. They are recorded
  here as found.
- **Arm: B6a.**

### B7: results PDF against the intake contract

- **Text layer.** Every page has one: 32 of 32 pages (Q2) and 29 of 29 (Q1); see Facts. Some
  pages read as OCR output, for example "hove been" and "Indio" in `[B1.05]`.
- **Period and basis headings, statement lines.** Present. Q2: "Unaudited financial results of
  the Bank (standalone and consolidated) for the quarter and six months ended September 30, 2026."
  (p1) `[B7.01]`; "STANDALONE FINANCIAL RESULTS", "Interest earned", "Three months ended" and "Six
  months ended" (p3) `[B7.02–B7.05]`; "SUMMARISED STANDALONE BALANCE SHEET" (p5) `[B7.06]`;
  "STANDALONE CASH FLOW STATEMENTS" (p6) `[B7.07]`; "CONSOLIDATED FINANCIAL RESULTS" (p13)
  `[B7.08]`. Q1: the p1 heading for the quarter ended June 30, 2026 `[B7.09]`; "STANDALONE
  FINANCIAL RESULTS", "1. Interest earned (a)+(b)+(c)+(d)" and "Three months ended" (p3)
  `[B7.10–B7.12]`; "SUMMARISED STANDALONE BALANCE SHEET" (p5) `[B7.13]`; "CONSOLIDATED FINANCIAL
  RESULTS" (p11) `[B7.14]`. Each PDF covers both bases in one document.
- **`Scrip Symbol :` marker** (`PDF_SYMBOL_MARKER`, `member_identity.py`). The contract's identity
  check needs it on page 1. It occurs on no page of either PDF `[B7.15, B7.16]`.
- **Arm: B7b.** The identity part of the contract fails on both retained PDFs. Under B7b the
  package is XBRL-only, each PDF is retained with an explicit limitation, and PDF claims read
  `NOT_ASSESSED`. Combined with B1′ P, the table gives B1c (see B1).

### B8: statements per period kind and basis, and anchor fit

Presence is by the bank concepts the instances carry. The check lists them `[B8.*]`; no amount is
read.

| Statement | Q2 C and Q2 S (2026-09-30) | Q1 C and Q1 S (2026-06-30) | `statement_anchors/v2` fit |
|---|---|---|---|
| P&L | quarter `OneD` and six months `FourD`: `ProfitLossForThePeriod`, `InterestEarned`, `ProfitLossFromOrdinaryActivitiesBeforeTax` `[B8.01–B8.03, B8.11, B8.17–B8.19, B8.27, B8.08, B8.24]` | quarter `OneD`: same concepts `[B8.33–B8.35, B8.44–B8.46, B3.15, B3.20]` | **no match.** The anchor fields `RevenueFromOperations` and `ProfitBeforeTax` are absent from all four instances `[B8.05, B8.06, B8.21, B8.22, B8.37, B8.38, B8.48, B8.49]` |
| Balance sheet | instant at period end `OneI`: `Assets`, `CapitalAndLiabilities` `[B8.09, B8.13, B8.14, B8.25, B8.29, B8.30]` | **absent**: no `Assets` or `CapitalAndLiabilities` `[B8.40, B8.41, B8.51, B8.52]`. The Q1 PDF carries a summarised balance sheet `[B7.13]` | fits through `Assets` (`OneI`); the anchor's other field `EquityAndLiabilities` is absent `[B8.07, B8.23]`, and the anchor needs any one field |
| Cash flow | six months `FourD`: `CashFlowsFromUsedInOperatingActivities`; instant `OneI`: `CashAndCashEquivalentsCashFlowStatement` `[B8.15, B8.16, B8.31, B8.32]`; also at prior year end `PY_I` 2026-03-31 `[B8.10, B8.26]` (Facts) | **absent** `[B8.42, B8.43, B8.53, B8.54]` | fits (both v2 cash-flow anchors) |
| Segment | `SegmentRevenue` at `OneD` and `FourD` `[B8.04, B8.12, B8.20, B8.28]` | `SegmentRevenue` at `OneD` `[B8.36, B8.47]` | fits |

- **Arms.** P&L is present for both periods and bases, but the anchors do not match bank
  statements: Task 8 adds `statement_anchors/v3.yaml` from the evidenced elements. The balance
  sheet and cash flow are present with fitting anchors at Q2, and absent at Q1 in both bases
  (capability `UNSUPPORTED` with reason; required-period rules unchanged). The segment statement
  is present with a fitting anchor at Q2 and Q1.

### B10: rounding, currency, fiscal-year end

- Every instance carries `LevelOfRounding` `Crores`, `DescriptionOfPresentationCurrency` `INR`,
  `DateOfStartOfFinancialYear` `2026-04-01` and `DateOfEndOfFinancialYear` `2027-03-31` at `OneD`
  `[B10.01–B10.16]`. `OneD` is a context that declares `DateOfEndOfReportingPeriod`
  `[B3.04, B3.09, B3.14, B3.19]`, the context `derived_settings._declared` reads them in. These are
  the concepts `_declared` uses (`FISCAL_YEAR_END`, `ROUNDING_LEVEL`, `PRESENTATION_CURRENCY`).
- **Arm: B10a.** The concepts and contexts are those of Ind AS filers. Whether `_declared` accepts
  a `Banking` instance is the form question (`financial_rule`), which belongs to B2 and Task 5,
  not B10.

### Summary for Task 3

| Branch | Supported arm | Basis |
|---|---|---|
| B1 | B1c by the table (content B1b: Indian GAAP, accounting standards under s.133 with the Banking Regulation Act and RBI directions) | B1′ P with B7b |
| B1′ | P | PDF only |
| B2 | B2a | `Banking` on all four |
| B3 | B3a | registered 2026-01-31 `in-capmkt` with its scope and period concepts |
| B4 | B4b (B4c if an unseeded scheme counts as unknown) | `NameOfBank`; Q1 scheme `.../in-capmkt/Symbol` |
| B5 | B5a | both bases listed for both periods |
| B6 | B6a | `Integrated Filing- Financials` |
| B7 | B7b | no `Scrip Symbol :` in either PDF |
| B8 | P&L present, anchors do not match (v3); BS and CF present at Q2, absent at Q1; segment present | see table |
| B10 | B10a | Ind AS filers' concepts in the period-declaring context |

B1c is a stop arm. Under "Conditional branches", it halts the phase at Task 3 for an amendment.

## Facts

Generated by `scratchpad/vendor-first/live-p3-1/facts.py` from the structure JSON alone (not committed; the JSON's sha256 is below). Amounts are never in the JSON.

Structure JSON sha256 `568044728a220584a29300eee1a4ed490d5080302a6261c77263ebb053889f85`; generation 1; symbol ICICIBANK; master ISINs INE090A01021; listings fetched.

### Period ending 2026-09-30

#### Consolidated instance `615348fca1872145ef64f390d725bc196359c61dec88ddf49f8ab8deb920dc5d`

- Listing row: type `Integrated Filing- Financials`, broadcast 2026-10-17 17:28:43, url `https://nsearchives.nseindia.com/corporate/xbrl/INTEGRATED_FILING_BANKING_1740887_17102026052842_WEB.xml`
- schemaRefs: `in-capmkt-ent-2026-01-31.xsd`
- IntegratedFinance forms: Banking
- Root namespaces: `in-capmkt`=`http://www.sebi.gov.in/xbrl/2026-01-31/in-capmkt`, `in-capmkt-ent`=`http://www.sebi.gov.in/xbrl/IntegratedFinance_Banking/2026-01-31/in-capmkt/in-capmkt-ent`, `in-capmkt-roles`=`http://www.sebi.gov.in/xbrl/IntegratedFinance_Banking/2026-01-31/in-capmkt-roles`, `in-capmkt-types`=`http://www.sebi.gov.in/xbrl/2026-01-31/in-capmkt-types`, `iso4217`=`http://www.xbrl.org/2003/iso4217`, `link`=`http://www.xbrl.org/2003/linkbase`, `negated`=`http://www.xbrl.org/2009/role/negated`, `net`=`http://www.xbrl.org/2009/role/net`, `nonnum`=`http://www.xbrl.org/dtr/type/non-numeric`, `num`=`http://www.xbrl.org/dtr/type/numeric`, `xbrldi`=`http://xbrl.org/2006/xbrldi`, `xbrldt`=`http://xbrl.org/2005/xbrldt`, `xbrli`=`http://www.xbrl.org/2003/instance`, `xl`=`http://www.xbrl.org/2003/XLink`, `xlink`=`http://www.w3.org/1999/xlink`
- Fact namespaces: `http://www.sebi.gov.in/xbrl/2026-01-31/in-capmkt`
- Taxonomy scope and period concepts used: `DateOfEndOfReportingPeriod`, `DateOfStartOfReportingPeriod`, `NatureOfReportStandaloneConsolidated`
- Contexts: 74; facts' concepts: 164; non-numeric facts: 84
- Text blocks: none

| Concept | contextRef | Context period | Value |
|---|---|---|---|
| `ScripCode` | `OneD` | 2026-07-01..2026-09-30 | 532174 |
| `Symbol` | `OneD` | 2026-07-01..2026-09-30 | ICICIBANK |
| `MSEISymbol` | `OneD` | 2026-07-01..2026-09-30 | NOTLISTED |
| `ISIN` | `OneD` | 2026-07-01..2026-09-30 | INE090A01021 |
| `NameOfBank` | `OneD` | 2026-07-01..2026-09-30 | ICICI BANK LIMITED |
| `DateOfStartOfFinancialYear` | `OneD` | 2026-07-01..2026-09-30 | 2026-04-01 |
| `DateOfEndOfFinancialYear` | `OneD` | 2026-07-01..2026-09-30 | 2027-03-31 |
| `DescriptionOfPresentationCurrency` | `OneD` | 2026-07-01..2026-09-30 | INR |
| `LevelOfRounding` | `OneD` | 2026-07-01..2026-09-30 | Crores |
| `TypeOfReportingPeriod` | `OneD` | 2026-07-01..2026-09-30 | Quarterly |
| `DateOfStartOfReportingPeriod` | `OneD` | 2026-07-01..2026-09-30 | 2026-07-01 |
| `DateOfEndOfReportingPeriod` | `OneD` | 2026-07-01..2026-09-30 | 2026-09-30 |
| `WhetherResultsAreAuditedOrUnaudited` | `OneD` | 2026-07-01..2026-09-30 | Unaudited |
| `NatureOfReportStandaloneConsolidated` | `OneD` | 2026-07-01..2026-09-30 | Consolidated |
| `DateOfStartOfReportingPeriod` | `FourD` | 2026-04-01..2026-09-30 | 2026-04-01 |
| `DateOfEndOfReportingPeriod` | `FourD` | 2026-04-01..2026-09-30 | 2026-09-30 |
| `WhetherResultsAreAuditedOrUnaudited` | `FourD` | 2026-04-01..2026-09-30 | Unaudited |
| `NatureOfReportStandaloneConsolidated` | `FourD` | 2026-04-01..2026-09-30 | Consolidated |

- Not present: `NameOfTheCompany`
- Undimensioned contexts: `OneD` 2026-07-01..2026-09-30, `OneI` 2026-09-30, `PY_I` 2026-03-31, `FourD` 2026-04-01..2026-09-30

#### Standalone instance `a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3`

- Listing row: type `Integrated Filing- Financials`, broadcast 2026-10-17 17:27:59, url `https://nsearchives.nseindia.com/corporate/xbrl/INTEGRATED_FILING_BANKING_1740886_17102026052751_WEB.xml`
- schemaRefs: `in-capmkt-ent-2026-01-31.xsd`
- IntegratedFinance forms: Banking
- Root namespaces: `in-capmkt`=`http://www.sebi.gov.in/xbrl/2026-01-31/in-capmkt`, `in-capmkt-ent`=`http://www.sebi.gov.in/xbrl/IntegratedFinance_Banking/2026-01-31/in-capmkt/in-capmkt-ent`, `in-capmkt-roles`=`http://www.sebi.gov.in/xbrl/IntegratedFinance_Banking/2026-01-31/in-capmkt-roles`, `in-capmkt-types`=`http://www.sebi.gov.in/xbrl/2026-01-31/in-capmkt-types`, `iso4217`=`http://www.xbrl.org/2003/iso4217`, `link`=`http://www.xbrl.org/2003/linkbase`, `negated`=`http://www.xbrl.org/2009/role/negated`, `net`=`http://www.xbrl.org/2009/role/net`, `nonnum`=`http://www.xbrl.org/dtr/type/non-numeric`, `num`=`http://www.xbrl.org/dtr/type/numeric`, `xbrldi`=`http://xbrl.org/2006/xbrldi`, `xbrldt`=`http://xbrl.org/2005/xbrldt`, `xbrli`=`http://www.xbrl.org/2003/instance`, `xl`=`http://www.xbrl.org/2003/XLink`, `xlink`=`http://www.w3.org/1999/xlink`
- Fact namespaces: `http://www.sebi.gov.in/xbrl/2026-01-31/in-capmkt`
- Taxonomy scope and period concepts used: `DateOfEndOfReportingPeriod`, `DateOfStartOfReportingPeriod`, `NatureOfReportStandaloneConsolidated`
- Contexts: 4675; facts' concepts: 187; non-numeric facts: 12449
- Text blocks: `DisclosureOfNotesOnFinancialResultsExplanatoryTextBlock@OneD`, `DisclosureOfNotesOnSegmentsExplanatoryTextBlock@OneD`

| Concept | contextRef | Context period | Value |
|---|---|---|---|
| `ScripCode` | `OneD` | 2026-07-01..2026-09-30 | 532174 |
| `Symbol` | `OneD` | 2026-07-01..2026-09-30 | ICICIBANK |
| `MSEISymbol` | `OneD` | 2026-07-01..2026-09-30 | NOTLISTED |
| `ISIN` | `OneD` | 2026-07-01..2026-09-30 | INE090A01021 |
| `NameOfBank` | `OneD` | 2026-07-01..2026-09-30 | ICICI BANK LIMITED |
| `DateOfStartOfFinancialYear` | `OneD` | 2026-07-01..2026-09-30 | 2026-04-01 |
| `DateOfEndOfFinancialYear` | `OneD` | 2026-07-01..2026-09-30 | 2027-03-31 |
| `DescriptionOfPresentationCurrency` | `OneD` | 2026-07-01..2026-09-30 | INR |
| `LevelOfRounding` | `OneD` | 2026-07-01..2026-09-30 | Crores |
| `TypeOfReportingPeriod` | `OneD` | 2026-07-01..2026-09-30 | Quarterly |
| `DateOfStartOfReportingPeriod` | `OneD` | 2026-07-01..2026-09-30 | 2026-07-01 |
| `DateOfEndOfReportingPeriod` | `OneD` | 2026-07-01..2026-09-30 | 2026-09-30 |
| `WhetherResultsAreAuditedOrUnaudited` | `OneD` | 2026-07-01..2026-09-30 | Unaudited |
| `NatureOfReportStandaloneConsolidated` | `OneD` | 2026-07-01..2026-09-30 | Standalone |
| `DateOfStartOfReportingPeriod` | `FourD` | 2026-04-01..2026-09-30 | 2026-04-01 |
| `DateOfEndOfReportingPeriod` | `FourD` | 2026-04-01..2026-09-30 | 2026-09-30 |
| `WhetherResultsAreAuditedOrUnaudited` | `FourD` | 2026-04-01..2026-09-30 | Unaudited |
| `NatureOfReportStandaloneConsolidated` | `FourD` | 2026-04-01..2026-09-30 | Standalone |

- Not present: `NameOfTheCompany`
- Undimensioned contexts: `OneD` 2026-07-01..2026-09-30, `OneI` 2026-09-30, `PY_I` 2026-03-31, `FourD` 2026-04-01..2026-09-30

#### Results PDF `b28a719174d31592413f317e9baf527e4dd127f18b2468179d9cc0bfa74fabd1`

- url `https://nsearchives.nseindia.com/corporate/ICICI2022_17102026152039_NSEBSE17102026.pdf`, filed 2026-10-17 15:21:44+05:30
- pages 32; pages without a text layer: none
- marker/heading lines captured: 85; lines naming `Scrip Symbol :`: 0; lines naming `prepared in accordance with`: 8

### Period ending 2026-06-30

#### Consolidated instance `ded5800004dd276f7b81110c4be9ed449eb2c7281ee3bb3e67519cf6448a4cb4`

- Listing row: type `Integrated Filing- Financials`, broadcast 2026-07-18 17:06:43, url `https://nsearchives.nseindia.com/corporate/xbrl/INTEGRATED_FILING_BANKING_1696196_18072026050643_WEB.xml`
- schemaRefs: `in-capmkt-ent-2026-01-31.xsd`
- IntegratedFinance forms: Banking
- Root namespaces: `in-capmkt`=`http://www.sebi.gov.in/xbrl/2026-01-31/in-capmkt`, `in-capmkt-ent`=`http://www.sebi.gov.in/xbrl/IntegratedFinance_Banking/2026-01-31/in-capmkt/in-capmkt-ent`, `in-capmkt-roles`=`http://www.sebi.gov.in/xbrl/IntegratedFinance_Banking/2026-01-31/in-capmkt-roles`, `in-capmkt-types`=`http://www.sebi.gov.in/xbrl/2026-01-31/in-capmkt-types`, `iso4217`=`http://www.xbrl.org/2003/iso4217`, `link`=`http://www.xbrl.org/2003/linkbase`, `negated`=`http://www.xbrl.org/2009/role/negated`, `net`=`http://www.xbrl.org/2009/role/net`, `nonnum`=`http://www.xbrl.org/dtr/type/non-numeric`, `num`=`http://www.xbrl.org/dtr/type/numeric`, `xbrldi`=`http://xbrl.org/2006/xbrldi`, `xbrldt`=`http://xbrl.org/2005/xbrldt`, `xbrli`=`http://www.xbrl.org/2003/instance`, `xl`=`http://www.xbrl.org/2003/XLink`, `xlink`=`http://www.w3.org/1999/xlink`
- Fact namespaces: `http://www.sebi.gov.in/xbrl/2026-01-31/in-capmkt`
- Taxonomy scope and period concepts used: `DateOfEndOfReportingPeriod`, `DateOfStartOfReportingPeriod`, `NatureOfReportStandaloneConsolidated`
- Contexts: 52; facts' concepts: 76; non-numeric facts: 58
- Text blocks: none

| Concept | contextRef | Context period | Value |
|---|---|---|---|
| `ScripCode` | `OneD` | 2026-04-01..2026-06-30 | 532174 |
| `Symbol` | `OneD` | 2026-04-01..2026-06-30 | ICICIBANK |
| `MSEISymbol` | `OneD` | 2026-04-01..2026-06-30 | NOTLISTED |
| `ISIN` | `OneD` | 2026-04-01..2026-06-30 | INE090A01021 |
| `NameOfBank` | `OneD` | 2026-04-01..2026-06-30 | ICICI BANK LIMITED |
| `DateOfStartOfFinancialYear` | `OneD` | 2026-04-01..2026-06-30 | 2026-04-01 |
| `DateOfEndOfFinancialYear` | `OneD` | 2026-04-01..2026-06-30 | 2027-03-31 |
| `DescriptionOfPresentationCurrency` | `OneD` | 2026-04-01..2026-06-30 | INR |
| `LevelOfRounding` | `OneD` | 2026-04-01..2026-06-30 | Crores |
| `TypeOfReportingPeriod` | `OneD` | 2026-04-01..2026-06-30 | Quarterly |
| `DateOfStartOfReportingPeriod` | `OneD` | 2026-04-01..2026-06-30 | 2026-04-01 |
| `DateOfEndOfReportingPeriod` | `OneD` | 2026-04-01..2026-06-30 | 2026-06-30 |
| `WhetherResultsAreAuditedOrUnaudited` | `OneD` | 2026-04-01..2026-06-30 | Unaudited |
| `NatureOfReportStandaloneConsolidated` | `OneD` | 2026-04-01..2026-06-30 | Consolidated |

- Not present: `NameOfTheCompany`
- Undimensioned contexts: `OneD` 2026-04-01..2026-06-30, `OneI` 2026-06-30

#### Standalone instance `39677b484f433a34be77c8a1bd241a0d9b66bf17cfd4eedc54ce0dfbaefc62d5`

- Listing row: type `Integrated Filing- Financials`, broadcast 2026-07-18 17:06:10, url `https://nsearchives.nseindia.com/corporate/xbrl/INTEGRATED_FILING_BANKING_1696194_18072026050610_WEB.xml`
- schemaRefs: `in-capmkt-ent-2026-01-31.xsd`
- IntegratedFinance forms: Banking
- Root namespaces: `in-capmkt`=`http://www.sebi.gov.in/xbrl/2026-01-31/in-capmkt`, `in-capmkt-ent`=`http://www.sebi.gov.in/xbrl/IntegratedFinance_Banking/2026-01-31/in-capmkt/in-capmkt-ent`, `in-capmkt-roles`=`http://www.sebi.gov.in/xbrl/IntegratedFinance_Banking/2026-01-31/in-capmkt-roles`, `in-capmkt-types`=`http://www.sebi.gov.in/xbrl/2026-01-31/in-capmkt-types`, `iso4217`=`http://www.xbrl.org/2003/iso4217`, `link`=`http://www.xbrl.org/2003/linkbase`, `negated`=`http://www.xbrl.org/2009/role/negated`, `net`=`http://www.xbrl.org/2009/role/net`, `nonnum`=`http://www.xbrl.org/dtr/type/non-numeric`, `num`=`http://www.xbrl.org/dtr/type/numeric`, `xbrldi`=`http://xbrl.org/2006/xbrldi`, `xbrldt`=`http://xbrl.org/2005/xbrldt`, `xbrli`=`http://www.xbrl.org/2003/instance`, `xl`=`http://www.xbrl.org/2003/XLink`, `xlink`=`http://www.w3.org/1999/xlink`
- Fact namespaces: `http://www.sebi.gov.in/xbrl/2026-01-31/in-capmkt`
- Taxonomy scope and period concepts used: `DateOfEndOfReportingPeriod`, `DateOfStartOfReportingPeriod`, `NatureOfReportStandaloneConsolidated`
- Contexts: 27; facts' concepts: 77; non-numeric facts: 46
- Text blocks: `DisclosureOfNotesOnFinancialResultsExplanatoryTextBlock@OneD`, `DisclosureOfNotesOnSegmentsExplanatoryTextBlock@OneD`

| Concept | contextRef | Context period | Value |
|---|---|---|---|
| `ScripCode` | `OneD` | 2026-04-01..2026-06-30 | 532174 |
| `Symbol` | `OneD` | 2026-04-01..2026-06-30 | ICICIBANK |
| `MSEISymbol` | `OneD` | 2026-04-01..2026-06-30 | NOTLISTED |
| `ISIN` | `OneD` | 2026-04-01..2026-06-30 | INE090A01021 |
| `NameOfBank` | `OneD` | 2026-04-01..2026-06-30 | ICICI BANK LIMITED |
| `DateOfStartOfFinancialYear` | `OneD` | 2026-04-01..2026-06-30 | 2026-04-01 |
| `DateOfEndOfFinancialYear` | `OneD` | 2026-04-01..2026-06-30 | 2027-03-31 |
| `DescriptionOfPresentationCurrency` | `OneD` | 2026-04-01..2026-06-30 | INR |
| `LevelOfRounding` | `OneD` | 2026-04-01..2026-06-30 | Crores |
| `TypeOfReportingPeriod` | `OneD` | 2026-04-01..2026-06-30 | Quarterly |
| `DateOfStartOfReportingPeriod` | `OneD` | 2026-04-01..2026-06-30 | 2026-04-01 |
| `DateOfEndOfReportingPeriod` | `OneD` | 2026-04-01..2026-06-30 | 2026-06-30 |
| `WhetherResultsAreAuditedOrUnaudited` | `OneD` | 2026-04-01..2026-06-30 | Unaudited |
| `NatureOfReportStandaloneConsolidated` | `OneD` | 2026-04-01..2026-06-30 | Standalone |

- Not present: `NameOfTheCompany`
- Undimensioned contexts: `OneD` 2026-04-01..2026-06-30, `OneI` 2026-06-30

#### Results PDF `1b3599e2a01fc9b77f913fef7a3068bca6ec43c722010a1c1bc4c01c55033c03`

- url `https://nsearchives.nseindia.com/corporate/ICICI2022_18072026142245_NSEBSE_18072026_.pdf`, filed 2026-07-18 14:23:53+05:30
- pages 29; pages without a text layer: none
- marker/heading lines captured: 80; lines naming `Scrip Symbol :`: 0; lines naming `prepared in accordance with`: 8

## Locators

One row per locator, tab-separated: id, kind, capture sha256, basis, period, where (QName@contextRef, page, namespace, listing key or search pattern), expected (value, quote, or `*` for presence without a value). `scratchpad/vendor-first/live-p3-1/locators.py` resolves every row in the retained blob under `data/raw/snapshots/v1` after checking the blob's sha256; `*-absent` rows assert that the concept, pattern or phrase does not occur. Result on 2026-11-06: 161 of 161 `OK`, none `NOT_ASSESSED`, exit 0.

```locators
B1.01	xbrl-text-absent	615348fca1872145ef64f390d725bc196359c61dec88ddf49f8ab8deb920dc5d	Consolidated	2026-09-30	accounting standard|in accordance with|GAAP|\bInd ?AS\b|AS 25	-
B1.02	xbrl-text-absent	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	accounting standard|in accordance with|GAAP|\bInd ?AS\b|AS 25	-
B1.03	xbrl-text-absent	ded5800004dd276f7b81110c4be9ed449eb2c7281ee3bb3e67519cf6448a4cb4	Consolidated	2026-06-30	accounting standard|in accordance with|GAAP|\bInd ?AS\b|AS 25	-
B1.04	xbrl-text-absent	39677b484f433a34be77c8a1bd241a0d9b66bf17cfd4eedc54ce0dfbaefc62d5	Standalone	2026-06-30	accounting standard|in accordance with|GAAP|\bInd ?AS\b|AS 25	-
B1.05	pdf	b28a719174d31592413f317e9baf527e4dd127f18b2468179d9cc0bfa74fabd1	Standalone	2026-09-30	7	The standalone financial results hove been prepared in accordance with the recognition and measurement principles laid down in Accounting Standard 25 "Interim Financial Reporting" ('AS 25'). prescribed under Section 133 of the Companies Act, 2013, the relevant provisions of the Banking Regulation Act, 1949, the circulars, guidelines and directions issued by the Reserve Bank of India ("RBI") from time to time and other accounting principles generally accepted in Indio
B1.06	pdf	b28a719174d31592413f317e9baf527e4dd127f18b2468179d9cc0bfa74fabd1	Consolidated	2026-09-30	16	The consolidated financial results have been prepared in accordance w ith the recognition and measurement principles laid down in Accounting Standards 25 "Interim Financial Reporting"('AS 25'),prescribed under Section 133 of the Companies Act. 2013, the relevant provisions of the Banking Regulation Act, 1949
B1.07	pdf	b28a719174d31592413f317e9baf527e4dd127f18b2468179d9cc0bfa74fabd1	Standalone	2026-09-30	30	Summary Profit and Loss Statement (as per standalone Indian GAAP accounts)
B1.08	pdf	b28a719174d31592413f317e9baf527e4dd127f18b2468179d9cc0bfa74fabd1	Consolidated	2026-09-30	29	The profit after tax of ICICI Securities, on a consolidated basis, as per Ind AS
B1.09	pdf	1b3599e2a01fc9b77f913fef7a3068bca6ec43c722010a1c1bc4c01c55033c03	Standalone	2026-06-30	6	The standalone financial results have been prepared in accordance with the recognition and measurement principles laid down in Accounting Standards prescribed under Section 133 of the Companies Act, 2013, the relevant provisions of the Banking Regulation Act, 1949, the circulars, guidelines and directions issued by the Reserve Bank of India ("RBI") from time to time and other accounting principles generally accepted in India
B1.10	pdf	1b3599e2a01fc9b77f913fef7a3068bca6ec43c722010a1c1bc4c01c55033c03	Consolidated	2026-06-30	13	The consolidated financial results have been prepared in accordance with the recognition and measurement principles laid down in Accounting Standards 25 "Interim Financial Reporting"('AS 25'), prescribed under Section 133 of the Companies Act, 2013, the relevant provisions of the Banking Regulation Act, 1949
B1.11	pdf	1b3599e2a01fc9b77f913fef7a3068bca6ec43c722010a1c1bc4c01c55033c03	Standalone	2026-06-30	26	Summary Profit and Loss Statement (as per standalone Indian GAAP accounts)
B1.12	pdf	1b3599e2a01fc9b77f913fef7a3068bca6ec43c722010a1c1bc4c01c55033c03	Standalone	2026-06-30	10	Revised Formats for Financial Results and Implementation of Ind AS by Listed Entities
B1.13	pdf-absent	b28a719174d31592413f317e9baf527e4dd127f18b2468179d9cc0bfa74fabd1	both	2026-09-30	*	prepared in accordance with Indian Accounting Standard
B1.14	pdf-absent	b28a719174d31592413f317e9baf527e4dd127f18b2468179d9cc0bfa74fabd1	both	2026-09-30	*	prepared in accordance with the Indian Accounting Standards
B1.15	pdf-absent	b28a719174d31592413f317e9baf527e4dd127f18b2468179d9cc0bfa74fabd1	both	2026-09-30	*	prepared in accordance with applicable Indian Accounting Standards
B1.16	pdf-absent	1b3599e2a01fc9b77f913fef7a3068bca6ec43c722010a1c1bc4c01c55033c03	both	2026-06-30	*	prepared in accordance with Indian Accounting Standard
B1.17	pdf-absent	1b3599e2a01fc9b77f913fef7a3068bca6ec43c722010a1c1bc4c01c55033c03	both	2026-06-30	*	prepared in accordance with the Indian Accounting Standards
B1.18	pdf-absent	1b3599e2a01fc9b77f913fef7a3068bca6ec43c722010a1c1bc4c01c55033c03	both	2026-06-30	*	prepared in accordance with applicable Indian Accounting Standards
B2.01	xbrl-forms	615348fca1872145ef64f390d725bc196359c61dec88ddf49f8ab8deb920dc5d	Consolidated	2026-09-30	-	Banking
B2.02	xbrl-ns	615348fca1872145ef64f390d725bc196359c61dec88ddf49f8ab8deb920dc5d	Consolidated	2026-09-30	http://www.sebi.gov.in/xbrl/IntegratedFinance_Banking/2026-01-31/in-capmkt/in-capmkt-ent	-
B2.03	xbrl-forms	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	-	Banking
B2.04	xbrl-ns	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	http://www.sebi.gov.in/xbrl/IntegratedFinance_Banking/2026-01-31/in-capmkt/in-capmkt-ent	-
B2.05	xbrl-forms	ded5800004dd276f7b81110c4be9ed449eb2c7281ee3bb3e67519cf6448a4cb4	Consolidated	2026-06-30	-	Banking
B2.06	xbrl-ns	ded5800004dd276f7b81110c4be9ed449eb2c7281ee3bb3e67519cf6448a4cb4	Consolidated	2026-06-30	http://www.sebi.gov.in/xbrl/IntegratedFinance_Banking/2026-01-31/in-capmkt/in-capmkt-ent	-
B2.07	xbrl-forms	39677b484f433a34be77c8a1bd241a0d9b66bf17cfd4eedc54ce0dfbaefc62d5	Standalone	2026-06-30	-	Banking
B2.08	xbrl-ns	39677b484f433a34be77c8a1bd241a0d9b66bf17cfd4eedc54ce0dfbaefc62d5	Standalone	2026-06-30	http://www.sebi.gov.in/xbrl/IntegratedFinance_Banking/2026-01-31/in-capmkt/in-capmkt-ent	-
B3.01	xbrl-ns	615348fca1872145ef64f390d725bc196359c61dec88ddf49f8ab8deb920dc5d	Consolidated	2026-09-30	http://www.sebi.gov.in/xbrl/2026-01-31/in-capmkt	-
B3.02	xbrl-fact	615348fca1872145ef64f390d725bc196359c61dec88ddf49f8ab8deb920dc5d	Consolidated	2026-09-30	NatureOfReportStandaloneConsolidated@OneD	Consolidated
B3.03	xbrl-fact	615348fca1872145ef64f390d725bc196359c61dec88ddf49f8ab8deb920dc5d	Consolidated	2026-09-30	DateOfStartOfReportingPeriod@OneD	2026-07-01
B3.04	xbrl-fact	615348fca1872145ef64f390d725bc196359c61dec88ddf49f8ab8deb920dc5d	Consolidated	2026-09-30	DateOfEndOfReportingPeriod@OneD	2026-09-30
B3.05	xbrl-context	615348fca1872145ef64f390d725bc196359c61dec88ddf49f8ab8deb920dc5d	Consolidated	2026-09-30	OneD	2026-07-01..2026-09-30
B3.06	xbrl-ns	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	http://www.sebi.gov.in/xbrl/2026-01-31/in-capmkt	-
B3.07	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	NatureOfReportStandaloneConsolidated@OneD	Standalone
B3.08	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	DateOfStartOfReportingPeriod@OneD	2026-07-01
B3.09	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	DateOfEndOfReportingPeriod@OneD	2026-09-30
B3.10	xbrl-context	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	OneD	2026-07-01..2026-09-30
B3.11	xbrl-ns	ded5800004dd276f7b81110c4be9ed449eb2c7281ee3bb3e67519cf6448a4cb4	Consolidated	2026-06-30	http://www.sebi.gov.in/xbrl/2026-01-31/in-capmkt	-
B3.12	xbrl-fact	ded5800004dd276f7b81110c4be9ed449eb2c7281ee3bb3e67519cf6448a4cb4	Consolidated	2026-06-30	NatureOfReportStandaloneConsolidated@OneD	Consolidated
B3.13	xbrl-fact	ded5800004dd276f7b81110c4be9ed449eb2c7281ee3bb3e67519cf6448a4cb4	Consolidated	2026-06-30	DateOfStartOfReportingPeriod@OneD	2026-04-01
B3.14	xbrl-fact	ded5800004dd276f7b81110c4be9ed449eb2c7281ee3bb3e67519cf6448a4cb4	Consolidated	2026-06-30	DateOfEndOfReportingPeriod@OneD	2026-06-30
B3.15	xbrl-context	ded5800004dd276f7b81110c4be9ed449eb2c7281ee3bb3e67519cf6448a4cb4	Consolidated	2026-06-30	OneD	2026-04-01..2026-06-30
B3.16	xbrl-ns	39677b484f433a34be77c8a1bd241a0d9b66bf17cfd4eedc54ce0dfbaefc62d5	Standalone	2026-06-30	http://www.sebi.gov.in/xbrl/2026-01-31/in-capmkt	-
B3.17	xbrl-fact	39677b484f433a34be77c8a1bd241a0d9b66bf17cfd4eedc54ce0dfbaefc62d5	Standalone	2026-06-30	NatureOfReportStandaloneConsolidated@OneD	Standalone
B3.18	xbrl-fact	39677b484f433a34be77c8a1bd241a0d9b66bf17cfd4eedc54ce0dfbaefc62d5	Standalone	2026-06-30	DateOfStartOfReportingPeriod@OneD	2026-04-01
B3.19	xbrl-fact	39677b484f433a34be77c8a1bd241a0d9b66bf17cfd4eedc54ce0dfbaefc62d5	Standalone	2026-06-30	DateOfEndOfReportingPeriod@OneD	2026-06-30
B3.20	xbrl-context	39677b484f433a34be77c8a1bd241a0d9b66bf17cfd4eedc54ce0dfbaefc62d5	Standalone	2026-06-30	OneD	2026-04-01..2026-06-30
B4.01	xbrl-fact	615348fca1872145ef64f390d725bc196359c61dec88ddf49f8ab8deb920dc5d	Consolidated	2026-09-30	ISIN@OneD	INE090A01021
B4.02	xbrl-fact	615348fca1872145ef64f390d725bc196359c61dec88ddf49f8ab8deb920dc5d	Consolidated	2026-09-30	Symbol@OneD	ICICIBANK
B4.03	xbrl-fact	615348fca1872145ef64f390d725bc196359c61dec88ddf49f8ab8deb920dc5d	Consolidated	2026-09-30	ScripCode@OneD	532174
B4.04	xbrl-fact	615348fca1872145ef64f390d725bc196359c61dec88ddf49f8ab8deb920dc5d	Consolidated	2026-09-30	NameOfBank@OneD	ICICI BANK LIMITED
B4.05	xbrl-absent	615348fca1872145ef64f390d725bc196359c61dec88ddf49f8ab8deb920dc5d	Consolidated	2026-09-30	NameOfTheCompany	-
B4.06	xbrl-entity	615348fca1872145ef64f390d725bc196359c61dec88ddf49f8ab8deb920dc5d	Consolidated	2026-09-30	-	http://www.sebi.gov.in/in-capmkt/ScripCode|532174
B4.07	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	ISIN@OneD	INE090A01021
B4.08	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	Symbol@OneD	ICICIBANK
B4.09	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	ScripCode@OneD	532174
B4.10	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	NameOfBank@OneD	ICICI BANK LIMITED
B4.11	xbrl-absent	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	NameOfTheCompany	-
B4.12	xbrl-entity	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	-	http://www.sebi.gov.in/in-capmkt/ScripCode|532174
B4.13	xbrl-fact	ded5800004dd276f7b81110c4be9ed449eb2c7281ee3bb3e67519cf6448a4cb4	Consolidated	2026-06-30	ISIN@OneD	INE090A01021
B4.14	xbrl-fact	ded5800004dd276f7b81110c4be9ed449eb2c7281ee3bb3e67519cf6448a4cb4	Consolidated	2026-06-30	Symbol@OneD	ICICIBANK
B4.15	xbrl-fact	ded5800004dd276f7b81110c4be9ed449eb2c7281ee3bb3e67519cf6448a4cb4	Consolidated	2026-06-30	ScripCode@OneD	532174
B4.16	xbrl-fact	ded5800004dd276f7b81110c4be9ed449eb2c7281ee3bb3e67519cf6448a4cb4	Consolidated	2026-06-30	NameOfBank@OneD	ICICI BANK LIMITED
B4.17	xbrl-absent	ded5800004dd276f7b81110c4be9ed449eb2c7281ee3bb3e67519cf6448a4cb4	Consolidated	2026-06-30	NameOfTheCompany	-
B4.18	xbrl-entity	ded5800004dd276f7b81110c4be9ed449eb2c7281ee3bb3e67519cf6448a4cb4	Consolidated	2026-06-30	-	http://www.sebi.gov.in/in-capmkt/Symbol|ICICIBANK
B4.19	xbrl-fact	39677b484f433a34be77c8a1bd241a0d9b66bf17cfd4eedc54ce0dfbaefc62d5	Standalone	2026-06-30	ISIN@OneD	INE090A01021
B4.20	xbrl-fact	39677b484f433a34be77c8a1bd241a0d9b66bf17cfd4eedc54ce0dfbaefc62d5	Standalone	2026-06-30	Symbol@OneD	ICICIBANK
B4.21	xbrl-fact	39677b484f433a34be77c8a1bd241a0d9b66bf17cfd4eedc54ce0dfbaefc62d5	Standalone	2026-06-30	ScripCode@OneD	532174
B4.22	xbrl-fact	39677b484f433a34be77c8a1bd241a0d9b66bf17cfd4eedc54ce0dfbaefc62d5	Standalone	2026-06-30	NameOfBank@OneD	ICICI BANK LIMITED
B4.23	xbrl-absent	39677b484f433a34be77c8a1bd241a0d9b66bf17cfd4eedc54ce0dfbaefc62d5	Standalone	2026-06-30	NameOfTheCompany	-
B4.24	xbrl-entity	39677b484f433a34be77c8a1bd241a0d9b66bf17cfd4eedc54ce0dfbaefc62d5	Standalone	2026-06-30	-	http://www.sebi.gov.in/in-capmkt/Symbol|ICICIBANK
B4.25	master	da7eb83cf21156cca3a8bcc5b94ea55f825ff7348e02c89abc51658788361fa5	-	-	ICICIBANK	INE090A01021
B5.01	listing	aa9d084a9a6c65bd3df091f20f14ee23a26a67dd61ca407be0c497b0eaab2d71	Consolidated	2026-09-30	30-SEP-2026|Consolidated|Integrated Filing- Financials	https://nsearchives.nseindia.com/corporate/xbrl/INTEGRATED_FILING_BANKING_1740887_17102026052842_WEB.xml
B5.02	listing	aa9d084a9a6c65bd3df091f20f14ee23a26a67dd61ca407be0c497b0eaab2d71	Standalone	2026-09-30	30-SEP-2026|Standalone|Integrated Filing- Financials	https://nsearchives.nseindia.com/corporate/xbrl/INTEGRATED_FILING_BANKING_1740886_17102026052751_WEB.xml
B5.03	listing	aa9d084a9a6c65bd3df091f20f14ee23a26a67dd61ca407be0c497b0eaab2d71	Consolidated	2026-06-30	30-JUN-2026|Consolidated|Integrated Filing- Financials	https://nsearchives.nseindia.com/corporate/xbrl/INTEGRATED_FILING_BANKING_1696196_18072026050643_WEB.xml
B5.04	listing	aa9d084a9a6c65bd3df091f20f14ee23a26a67dd61ca407be0c497b0eaab2d71	Standalone	2026-06-30	30-JUN-2026|Standalone|Integrated Filing- Financials	https://nsearchives.nseindia.com/corporate/xbrl/INTEGRATED_FILING_BANKING_1696194_18072026050610_WEB.xml
B7.01	pdf	b28a719174d31592413f317e9baf527e4dd127f18b2468179d9cc0bfa74fabd1	both	2026-09-30	1	Unaudited financial results of the Bank (standalone and consolidated) for the quarter and six months ended September 30, 2026.
B7.02	pdf	b28a719174d31592413f317e9baf527e4dd127f18b2468179d9cc0bfa74fabd1	Standalone	2026-09-30	3	STANDALONE FINANCIAL RESULTS
B7.03	pdf	b28a719174d31592413f317e9baf527e4dd127f18b2468179d9cc0bfa74fabd1	Standalone	2026-09-30	3	Interest earned
B7.04	pdf	b28a719174d31592413f317e9baf527e4dd127f18b2468179d9cc0bfa74fabd1	Standalone	2026-09-30	3	Three months ended
B7.05	pdf	b28a719174d31592413f317e9baf527e4dd127f18b2468179d9cc0bfa74fabd1	Standalone	2026-09-30	3	Six months ended
B7.06	pdf	b28a719174d31592413f317e9baf527e4dd127f18b2468179d9cc0bfa74fabd1	Standalone	2026-09-30	5	SUMMARISED STANDALONE BALANCE SHEET
B7.07	pdf	b28a719174d31592413f317e9baf527e4dd127f18b2468179d9cc0bfa74fabd1	Standalone	2026-09-30	6	STANDALONE CASH FLOW STATEMENTS
B7.08	pdf	b28a719174d31592413f317e9baf527e4dd127f18b2468179d9cc0bfa74fabd1	Consolidated	2026-09-30	13	CONSOLIDATED FINANCIAL RESULTS
B7.09	pdf	1b3599e2a01fc9b77f913fef7a3068bca6ec43c722010a1c1bc4c01c55033c03	both	2026-06-30	1	Unaudited financial results of the Bank (standalone and consolidated) for the quarter ended June 30, 2026.
B7.10	pdf	1b3599e2a01fc9b77f913fef7a3068bca6ec43c722010a1c1bc4c01c55033c03	Standalone	2026-06-30	3	STANDALONE FINANCIAL RESULTS
B7.11	pdf	1b3599e2a01fc9b77f913fef7a3068bca6ec43c722010a1c1bc4c01c55033c03	Standalone	2026-06-30	3	1. Interest earned (a)+(b)+(c)+(d)
B7.12	pdf	1b3599e2a01fc9b77f913fef7a3068bca6ec43c722010a1c1bc4c01c55033c03	Standalone	2026-06-30	3	Three months ended
B7.13	pdf	1b3599e2a01fc9b77f913fef7a3068bca6ec43c722010a1c1bc4c01c55033c03	Standalone	2026-06-30	5	SUMMARISED STANDALONE BALANCE SHEET
B7.14	pdf	1b3599e2a01fc9b77f913fef7a3068bca6ec43c722010a1c1bc4c01c55033c03	Consolidated	2026-06-30	11	CONSOLIDATED FINANCIAL RESULTS
B7.15	pdf-absent	b28a719174d31592413f317e9baf527e4dd127f18b2468179d9cc0bfa74fabd1	both	2026-09-30	*	Scrip Symbol :
B7.16	pdf-absent	1b3599e2a01fc9b77f913fef7a3068bca6ec43c722010a1c1bc4c01c55033c03	both	2026-06-30	*	Scrip Symbol :
B8.01	xbrl-fact	615348fca1872145ef64f390d725bc196359c61dec88ddf49f8ab8deb920dc5d	Consolidated	2026-09-30	ProfitLossForThePeriod@OneD	*
B8.02	xbrl-fact	615348fca1872145ef64f390d725bc196359c61dec88ddf49f8ab8deb920dc5d	Consolidated	2026-09-30	InterestEarned@OneD	*
B8.03	xbrl-fact	615348fca1872145ef64f390d725bc196359c61dec88ddf49f8ab8deb920dc5d	Consolidated	2026-09-30	ProfitLossFromOrdinaryActivitiesBeforeTax@OneD	*
B8.04	xbrl-fact	615348fca1872145ef64f390d725bc196359c61dec88ddf49f8ab8deb920dc5d	Consolidated	2026-09-30	SegmentRevenue@OneD	*
B8.05	xbrl-absent	615348fca1872145ef64f390d725bc196359c61dec88ddf49f8ab8deb920dc5d	Consolidated	2026-09-30	RevenueFromOperations	-
B8.06	xbrl-absent	615348fca1872145ef64f390d725bc196359c61dec88ddf49f8ab8deb920dc5d	Consolidated	2026-09-30	ProfitBeforeTax	-
B8.07	xbrl-absent	615348fca1872145ef64f390d725bc196359c61dec88ddf49f8ab8deb920dc5d	Consolidated	2026-09-30	EquityAndLiabilities	-
B8.08	xbrl-context	615348fca1872145ef64f390d725bc196359c61dec88ddf49f8ab8deb920dc5d	Consolidated	2026-09-30	FourD	2026-04-01..2026-09-30
B8.09	xbrl-context	615348fca1872145ef64f390d725bc196359c61dec88ddf49f8ab8deb920dc5d	Consolidated	2026-09-30	OneI	2026-09-30
B8.10	xbrl-context	615348fca1872145ef64f390d725bc196359c61dec88ddf49f8ab8deb920dc5d	Consolidated	2026-09-30	PY_I	2026-03-31
B8.11	xbrl-fact	615348fca1872145ef64f390d725bc196359c61dec88ddf49f8ab8deb920dc5d	Consolidated	2026-09-30	ProfitLossForThePeriod@FourD	*
B8.12	xbrl-fact	615348fca1872145ef64f390d725bc196359c61dec88ddf49f8ab8deb920dc5d	Consolidated	2026-09-30	SegmentRevenue@FourD	*
B8.13	xbrl-fact	615348fca1872145ef64f390d725bc196359c61dec88ddf49f8ab8deb920dc5d	Consolidated	2026-09-30	Assets@OneI	*
B8.14	xbrl-fact	615348fca1872145ef64f390d725bc196359c61dec88ddf49f8ab8deb920dc5d	Consolidated	2026-09-30	CapitalAndLiabilities@OneI	*
B8.15	xbrl-fact	615348fca1872145ef64f390d725bc196359c61dec88ddf49f8ab8deb920dc5d	Consolidated	2026-09-30	CashFlowsFromUsedInOperatingActivities@FourD	*
B8.16	xbrl-fact	615348fca1872145ef64f390d725bc196359c61dec88ddf49f8ab8deb920dc5d	Consolidated	2026-09-30	CashAndCashEquivalentsCashFlowStatement@OneI	*
B8.17	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	ProfitLossForThePeriod@OneD	*
B8.18	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	InterestEarned@OneD	*
B8.19	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	ProfitLossFromOrdinaryActivitiesBeforeTax@OneD	*
B8.20	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	SegmentRevenue@OneD	*
B8.21	xbrl-absent	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	RevenueFromOperations	-
B8.22	xbrl-absent	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	ProfitBeforeTax	-
B8.23	xbrl-absent	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	EquityAndLiabilities	-
B8.24	xbrl-context	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	FourD	2026-04-01..2026-09-30
B8.25	xbrl-context	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	OneI	2026-09-30
B8.26	xbrl-context	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	PY_I	2026-03-31
B8.27	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	ProfitLossForThePeriod@FourD	*
B8.28	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	SegmentRevenue@FourD	*
B8.29	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	Assets@OneI	*
B8.30	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	CapitalAndLiabilities@OneI	*
B8.31	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	CashFlowsFromUsedInOperatingActivities@FourD	*
B8.32	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	CashAndCashEquivalentsCashFlowStatement@OneI	*
B8.33	xbrl-fact	ded5800004dd276f7b81110c4be9ed449eb2c7281ee3bb3e67519cf6448a4cb4	Consolidated	2026-06-30	ProfitLossForThePeriod@OneD	*
B8.34	xbrl-fact	ded5800004dd276f7b81110c4be9ed449eb2c7281ee3bb3e67519cf6448a4cb4	Consolidated	2026-06-30	InterestEarned@OneD	*
B8.35	xbrl-fact	ded5800004dd276f7b81110c4be9ed449eb2c7281ee3bb3e67519cf6448a4cb4	Consolidated	2026-06-30	ProfitLossFromOrdinaryActivitiesBeforeTax@OneD	*
B8.36	xbrl-fact	ded5800004dd276f7b81110c4be9ed449eb2c7281ee3bb3e67519cf6448a4cb4	Consolidated	2026-06-30	SegmentRevenue@OneD	*
B8.37	xbrl-absent	ded5800004dd276f7b81110c4be9ed449eb2c7281ee3bb3e67519cf6448a4cb4	Consolidated	2026-06-30	RevenueFromOperations	-
B8.38	xbrl-absent	ded5800004dd276f7b81110c4be9ed449eb2c7281ee3bb3e67519cf6448a4cb4	Consolidated	2026-06-30	ProfitBeforeTax	-
B8.39	xbrl-absent	ded5800004dd276f7b81110c4be9ed449eb2c7281ee3bb3e67519cf6448a4cb4	Consolidated	2026-06-30	EquityAndLiabilities	-
B8.40	xbrl-absent	ded5800004dd276f7b81110c4be9ed449eb2c7281ee3bb3e67519cf6448a4cb4	Consolidated	2026-06-30	Assets	-
B8.41	xbrl-absent	ded5800004dd276f7b81110c4be9ed449eb2c7281ee3bb3e67519cf6448a4cb4	Consolidated	2026-06-30	CapitalAndLiabilities	-
B8.42	xbrl-absent	ded5800004dd276f7b81110c4be9ed449eb2c7281ee3bb3e67519cf6448a4cb4	Consolidated	2026-06-30	CashFlowsFromUsedInOperatingActivities	-
B8.43	xbrl-absent	ded5800004dd276f7b81110c4be9ed449eb2c7281ee3bb3e67519cf6448a4cb4	Consolidated	2026-06-30	CashAndCashEquivalentsCashFlowStatement	-
B8.44	xbrl-fact	39677b484f433a34be77c8a1bd241a0d9b66bf17cfd4eedc54ce0dfbaefc62d5	Standalone	2026-06-30	ProfitLossForThePeriod@OneD	*
B8.45	xbrl-fact	39677b484f433a34be77c8a1bd241a0d9b66bf17cfd4eedc54ce0dfbaefc62d5	Standalone	2026-06-30	InterestEarned@OneD	*
B8.46	xbrl-fact	39677b484f433a34be77c8a1bd241a0d9b66bf17cfd4eedc54ce0dfbaefc62d5	Standalone	2026-06-30	ProfitLossFromOrdinaryActivitiesBeforeTax@OneD	*
B8.47	xbrl-fact	39677b484f433a34be77c8a1bd241a0d9b66bf17cfd4eedc54ce0dfbaefc62d5	Standalone	2026-06-30	SegmentRevenue@OneD	*
B8.48	xbrl-absent	39677b484f433a34be77c8a1bd241a0d9b66bf17cfd4eedc54ce0dfbaefc62d5	Standalone	2026-06-30	RevenueFromOperations	-
B8.49	xbrl-absent	39677b484f433a34be77c8a1bd241a0d9b66bf17cfd4eedc54ce0dfbaefc62d5	Standalone	2026-06-30	ProfitBeforeTax	-
B8.50	xbrl-absent	39677b484f433a34be77c8a1bd241a0d9b66bf17cfd4eedc54ce0dfbaefc62d5	Standalone	2026-06-30	EquityAndLiabilities	-
B8.51	xbrl-absent	39677b484f433a34be77c8a1bd241a0d9b66bf17cfd4eedc54ce0dfbaefc62d5	Standalone	2026-06-30	Assets	-
B8.52	xbrl-absent	39677b484f433a34be77c8a1bd241a0d9b66bf17cfd4eedc54ce0dfbaefc62d5	Standalone	2026-06-30	CapitalAndLiabilities	-
B8.53	xbrl-absent	39677b484f433a34be77c8a1bd241a0d9b66bf17cfd4eedc54ce0dfbaefc62d5	Standalone	2026-06-30	CashFlowsFromUsedInOperatingActivities	-
B8.54	xbrl-absent	39677b484f433a34be77c8a1bd241a0d9b66bf17cfd4eedc54ce0dfbaefc62d5	Standalone	2026-06-30	CashAndCashEquivalentsCashFlowStatement	-
B10.01	xbrl-fact	615348fca1872145ef64f390d725bc196359c61dec88ddf49f8ab8deb920dc5d	Consolidated	2026-09-30	LevelOfRounding@OneD	Crores
B10.02	xbrl-fact	615348fca1872145ef64f390d725bc196359c61dec88ddf49f8ab8deb920dc5d	Consolidated	2026-09-30	DescriptionOfPresentationCurrency@OneD	INR
B10.03	xbrl-fact	615348fca1872145ef64f390d725bc196359c61dec88ddf49f8ab8deb920dc5d	Consolidated	2026-09-30	DateOfStartOfFinancialYear@OneD	2026-04-01
B10.04	xbrl-fact	615348fca1872145ef64f390d725bc196359c61dec88ddf49f8ab8deb920dc5d	Consolidated	2026-09-30	DateOfEndOfFinancialYear@OneD	2027-03-31
B10.05	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	LevelOfRounding@OneD	Crores
B10.06	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	DescriptionOfPresentationCurrency@OneD	INR
B10.07	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	DateOfStartOfFinancialYear@OneD	2026-04-01
B10.08	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	DateOfEndOfFinancialYear@OneD	2027-03-31
B10.09	xbrl-fact	ded5800004dd276f7b81110c4be9ed449eb2c7281ee3bb3e67519cf6448a4cb4	Consolidated	2026-06-30	LevelOfRounding@OneD	Crores
B10.10	xbrl-fact	ded5800004dd276f7b81110c4be9ed449eb2c7281ee3bb3e67519cf6448a4cb4	Consolidated	2026-06-30	DescriptionOfPresentationCurrency@OneD	INR
B10.11	xbrl-fact	ded5800004dd276f7b81110c4be9ed449eb2c7281ee3bb3e67519cf6448a4cb4	Consolidated	2026-06-30	DateOfStartOfFinancialYear@OneD	2026-04-01
B10.12	xbrl-fact	ded5800004dd276f7b81110c4be9ed449eb2c7281ee3bb3e67519cf6448a4cb4	Consolidated	2026-06-30	DateOfEndOfFinancialYear@OneD	2027-03-31
B10.13	xbrl-fact	39677b484f433a34be77c8a1bd241a0d9b66bf17cfd4eedc54ce0dfbaefc62d5	Standalone	2026-06-30	LevelOfRounding@OneD	Crores
B10.14	xbrl-fact	39677b484f433a34be77c8a1bd241a0d9b66bf17cfd4eedc54ce0dfbaefc62d5	Standalone	2026-06-30	DescriptionOfPresentationCurrency@OneD	INR
B10.15	xbrl-fact	39677b484f433a34be77c8a1bd241a0d9b66bf17cfd4eedc54ce0dfbaefc62d5	Standalone	2026-06-30	DateOfStartOfFinancialYear@OneD	2026-04-01
B10.16	xbrl-fact	39677b484f433a34be77c8a1bd241a0d9b66bf17cfd4eedc54ce0dfbaefc62d5	Standalone	2026-06-30	DateOfEndOfFinancialYear@OneD	2027-03-31
```
