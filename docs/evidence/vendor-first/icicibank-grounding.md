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

One row per locator, tab-separated: id, kind, capture sha256, basis, period, where (QName@contextRef, page, namespace, listing key or search pattern), expected (value, quote, or `*` for presence without a value). `scratchpad/vendor-first/live-p3-1/locators.py` resolves every row in the retained blob under `data/raw/snapshots/v1` after checking the blob's sha256; `*-absent` rows assert that the concept, pattern or phrase does not occur. Result on 2026-11-06: 161 of 161 `OK`, none `NOT_ASSESSED`, exit 0. Task 3 appended rows `T3.01`–`T3.48` (cited by the Ledger and Evidence pins below and by the plan's Resolved branches). They add four kinds, resolved by `scratchpad/vendor-first/live-p3-1/locators_t3.py`, which runs `locators.py`'s kinds unchanged: `xbrl-concept-set` (the exact set of numeric concepts with an undimensioned fact at a context), `pdf-codes` (the set of every `NSE:`/`BSE:` code citation in a PDF), `announcement` (an announcements-listing row's symbol, ISIN and category, by attachment URL) and `pdf-tokens` (a phrase as a lowercase alphanumeric token run, as `member_identity` matches declarations). Result on 2026-11-06 over all rows: 209 of 209 `OK`, none `NOT_ASSESSED`, exit 0. Task 3 fix round 1 (Sol review 1) appended `T3.49`–`T3.81` and five kinds in the same script: `xbrl-sum` and `xbrl-sum-absent` (the decimal sum of `+`-joined facts or integer literals equals, or equals none of, each `|`-joined term), `xbrl-shape` (a fact's `decimals`, unit measure and sign), `pdf-title` (a whole text line equal to a name, case-insensitive, above a whole line equal to a heading on the page), and `pdf-line-absent`/`pdf-page-absent` (no text line, or no normalised page text, matches a case-insensitive pattern). Each new kind was also run on deliberately false rows, and each of those failed. Result on 2026-11-06 over all rows: 242 of 242 `OK`, none `NOT_ASSESSED`, exit 0.

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
T3.01	xbrl-concept-set	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	OneD	AdditionalTier1Ratio,AmountOfRelatedPartyTransactionDuringTheReportingPeriod,BasicEarningsPerShareAfterExtraordinaryItems,BasicEarningsPerShareBeforeExtraordinaryItems,CET1Ratio,DilutedEarningsPerShareAfterExtraordinaryItems,DilutedEarningsPerShareBeforeExtraordinaryItems,EmployeesCost,ExceptionalItems,ExpenditureExcludingProvisionsAndContingencies,ExtraordinaryItems,FaceValueOfEquityShareCapital,GrossNonPerformingAssets,Income,InterSegmentRevenue,InterestEarned,InterestExpended,InterestOnBalancesWithReserveBankOfIndiaAndOtherInterBankFunds,InterestOrDiscountOnAdvancesOrBills,NonPerformingAssets,OperatingExpenses,OperatingProfitBeforeProvisionAndContingencies,OtherIncome,OtherInterest,OtherOperatingExpenses,PaidUpValueOfEquityShareCapital,PercentageOfGrossNpa,PercentageOfNpa,PercentageOfShareHeldByGovernmentOfIndia,ProfitLossAfterTaxesMinorityInterestAndShareOfProfitLossOfAssociates,ProfitLossForThePeriod,ProfitLossFromOrdinaryActivitiesAfterTax,ProfitLossFromOrdinaryActivitiesBeforeTax,ProvisionsOtherThanTaxAndContingencies,ReturnOnAssets,RevenueOnInvestments,SegmentProfitBeforeTax,SegmentProfitLossBeforeTaxAndFinanceCosts,SegmentRevenue,SegmentRevenueFromOperations,TaxExpense
T3.02	xbrl-concept-set	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	FourD	AdditionalTier1Ratio,AdjustmentsForDecreaseIncreaseInInventories,AdjustmentsForDecreaseIncreaseInOtherCurrentAssets,AdjustmentsForDecreaseIncreaseInTradeReceivables,AdjustmentsForDepreciationAndAmortisationExpense,AdjustmentsForDividendIncome,AdjustmentsForFinanceCosts,AdjustmentsForImpairmentLossReversalOfImpairmentLossRecognisedInProfitOrLoss,AdjustmentsForIncreaseDecreaseInOtherCurrentLiabilities,AdjustmentsForIncreaseDecreaseInTradePayables,AdjustmentsForProvisions,AdjustmentsForReconcileProfitLoss,AdjustmentsForSharebasedPayments,AdjustmentsForUnrealisedForeignExchangeLossesGains,AdjustmentsForWorkingCapital,AdjustmentsToProfitLoss,BasicEarningsPerShareAfterExtraordinaryItems,BasicEarningsPerShareBeforeExtraordinaryItems,CET1Ratio,CashAdvancesAndLoansMadeToOtherPartiesClassifiedAsInvestingActivities,CashFlowsFromLosingControlOfSubsidiariesOrOtherBusinessesClassifiedAsInvestingActivities,CashFlowsFromUsedInFinancingActivities,CashFlowsFromUsedInFinancingActivitiesBeforeExtraordinaryItems,CashFlowsFromUsedInInvestingActivities,CashFlowsFromUsedInInvestingActivitiesBeforeExtraordinaryItems,CashFlowsFromUsedInOperatingActivities,CashFlowsFromUsedInOperatingActivitiesBeforeExtraordinaryItems,CashFlowsFromUsedInOperations,CashFlowsUsedInObtainingControlOfSubsidiariesOrOtherBusinessesClassifiedAsInvestingActivities,CashPaymentForInvestmentInPartnershipFirmOrAssociationOfPersonsOrLimitedLiabilityPartnerships,CashPaymentsForFutureContractsForwardContractsOptionContractsAndSwapContractsClassifiedAsInvestingActivities,CashReceiptsFromFutureContractsForwardContractsOptionContractsAndSwapContractsClassifiedAsInvestingActivities,CashReceiptsFromRepaymentOfAdvancesAndLoansMadeToOtherPartiesClassifiedAsInvestingActivities,CashReceiptsFromShareOfProfitsOfPartnershipFirmOrAssociationOfPersonsOrLimitedLiabilityPartnerships,DilutedEarningsPerShareAfterExtraordinaryItems,DilutedEarningsPerShareBeforeExtraordinaryItems,DividendsPaidClassifiedAsFinancingActivities,DividendsReceivedClassifiedAsInvestingActivities,DividendsReceivedClassifiedAsOperatingActivities,EffectOfExchangeRateChangesOnCashAndCashEquivalents,EmployeesCost,ExceptionalItems,ExpenditureExcludingProvisionsAndContingencies,ExtraordinaryItems,FaceValueOfEquityShareCapital,GrossNonPerformingAssets,Income,IncomeTaxesPaidRefundClassifiedAsFinancingActivities,IncomeTaxesPaidRefundClassifiedAsInvestingActivities,IncomeTaxesPaidRefundClassifiedAsOperatingActivities,IncreaseDecreaseInCashAndCashEquivalents,IncreaseDecreaseInCashAndCashEquivalentsBeforeEffectOfExchangeRateChanges,InterSegmentRevenue,InterestEarned,InterestExpended,InterestOnBalancesWithReserveBankOfIndiaAndOtherInterBankFunds,InterestOrDiscountOnAdvancesOrBills,InterestPaidClassifiedAsFinancingActivities,InterestPaidClassifiedAsOperatingActivities,InterestReceivedClassifiedAsInvestingActivities,InterestReceivedClassifiedAsOperatingActivities,NonPerformingAssets,OperatingExpenses,OperatingProfitBeforeProvisionAndContingencies,OtherAdjustmentsForNoncashItems,OtherAdjustmentsForWhichCashEffectsAreInvestingOrFinancingCashFlow,OtherAdjustmentsToReconcileProfitLoss,OtherCashPaymentsToAcquireEquityOrDebtInstrumentsOfOtherEntitiesClassifiedAsInvestingActivities,OtherCashPaymentsToAcquireInterestsInJointVenturesClassifiedAsInvestingActivities,OtherCashReceiptsFromSalesOfEquityOrDebtInstrumentsOfOtherEntitiesClassifiedAsInvestingActivities,OtherCashReceiptsFromSalesOfInterestsInJointVenturesClassifiedAsInvestingActivities,OtherIncome,OtherInflowsOutflowsOfCashClassifiedAsFinancingActivities,OtherInflowsOutflowsOfCashClassifiedAsInvestingActivities,OtherInflowsOutflowsOfCashClassifiedAsOperatingActivities,OtherInterest,OtherOperatingExpenses,PaidUpValueOfEquityShareCapital,PaymentForExtraordinaryItemsClassifiedAsFinancingActivities,PaymentForExtraordinaryItemsClassifiedAsInvestingActivities,PaymentForExtraordinaryItemsClassifiedAsOperatingActivities,PercentageOfGrossNpa,PercentageOfNpa,PercentageOfShareHeldByGovernmentOfIndia,ProceedsFromBorrowingsClassifiedAsFinancingActivities,ProceedsFromExtraordinaryItemsClassifiedAsFinancingActivities,ProceedsFromExtraordinaryItemsClassifiedAsInvestingActivities,ProceedsFromExtraordinaryItemsClassifiedAsOperatingActivities,ProceedsFromGovernmentGrantsClassifiedAsInvestingActivities,ProceedsFromIssuingDebenturesNotesBondsEtc,ProceedsFromIssuingOtherEquityInstruments,ProceedsFromIssuingShares,ProceedsFromSalesOfIntangibleAssetsClassifiedAsInvestingActivities,ProceedsFromSalesOfTangibleAssetsClassifiedAsInvestingActivities,ProfitBeforeExtraordinaryItemsAndTax,ProfitLossAfterTaxesMinorityInterestAndShareOfProfitLossOfAssociates,ProfitLossForThePeriod,ProfitLossFromOrdinaryActivitiesAfterTax,ProfitLossFromOrdinaryActivitiesBeforeTax,ProvisionsOtherThanTaxAndContingencies,PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities,PurchaseOfTangibleAssetsClassifiedAsInvestingActivities,RepaymentsOfBorrowingsClassifiedAsFinancingActivities,ReturnOnAssets,RevenueOnInvestments,SegmentProfitBeforeTax,SegmentProfitLossBeforeTaxAndFinanceCosts,SegmentRevenue,SegmentRevenueFromOperations,ShareOfProfitAndLossFromPartnershipFirmOrAssociationOfPersonsOrLimitedLiabilityPartnerships,TaxExpense
T3.03	xbrl-concept-set	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	OneI	Advances,Assets,BalancesWithBanksAndMoneyAtCallAndShortNotice,Borrowings,Capital,CapitalAndLiabilities,CashAndBalancesWithReserveBankOfIndia,CashAndCashEquivalentsCashFlowStatement,Deposits,FixedAssets,Investments,NetSegmentAssets,NetSegmentLiabilities,OtherAssets,OtherLiabilitiesAndProvisions,ReservesAndSurplus,SegmentAssets,SegmentLiabilities,UnAllocableAssets,UnAllocableLiabilities
T3.04	xbrl-concept-set	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	PY_I	CashAndCashEquivalentsCashFlowStatement
T3.05	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	DescriptionOfReportableSegment@OneReportable11D	Retail
T3.06	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	DescriptionOfReportableSegment@OneReportable12D	Wholesale
T3.07	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	DescriptionOfReportableSegment@OneReportable13D	Treasury
T3.08	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	DescriptionOfReportableSegment@OneReportable14D	Other Banking
T3.09	pdf	b28a719174d31592413f317e9baf527e4dd127f18b2468179d9cc0bfa74fabd1	both	2026-09-30	26	ICICI Bank Limited (NSE: ICICIBANK, BSE: 532174, NYSE: IBN)
T3.10	pdf	1b3599e2a01fc9b77f913fef7a3068bca6ec43c722010a1c1bc4c01c55033c03	both	2026-06-30	22	ICICI Bank Limited (NSE: ICICIBANK, BSE: 532174, NYSE: IBN)
T3.11	pdf-codes	b28a719174d31592413f317e9baf527e4dd127f18b2468179d9cc0bfa74fabd1	both	2026-09-30	*	NSE:ICICIBANK|BSE:532174
T3.12	pdf-codes	1b3599e2a01fc9b77f913fef7a3068bca6ec43c722010a1c1bc4c01c55033c03	both	2026-06-30	*	NSE:ICICIBANK|BSE:532174
T3.13	announcement	f5a17c905a2d09146fb4b333f877cb18803f485b0b4ee090c5a50357f3c1c025	both	2026-09-30	https://nsearchives.nseindia.com/corporate/ICICI2022_17102026152039_NSEBSE17102026.pdf	ICICIBANK|INE090A01013|Outcome of Board Meeting
T3.14	announcement	5009c79950c4fc32884018bb15017393dda14c88167d6aefb44df0648869e477	both	2026-06-30	https://nsearchives.nseindia.com/corporate/ICICI2022_18072026142245_NSEBSE_18072026_.pdf	ICICIBANK|INE090A01013|Outcome of Board Meeting
T3.15	pdf-tokens	b28a719174d31592413f317e9baf527e4dd127f18b2468179d9cc0bfa74fabd1	Standalone	2026-09-30	7	prescribed under Section 133 of the Companies Act, 2013, the relevant provisions of the Banking Regulation Act, 1949
T3.16	pdf-tokens	b28a719174d31592413f317e9baf527e4dd127f18b2468179d9cc0bfa74fabd1	Consolidated	2026-09-30	16	prescribed under Section 133 of the Companies Act, 2013, the relevant provisions of the Banking Regulation Act, 1949
T3.17	pdf-tokens	1b3599e2a01fc9b77f913fef7a3068bca6ec43c722010a1c1bc4c01c55033c03	Standalone	2026-06-30	6	prescribed under Section 133 of the Companies Act, 2013, the relevant provisions of the Banking Regulation Act, 1949
T3.18	pdf-tokens	1b3599e2a01fc9b77f913fef7a3068bca6ec43c722010a1c1bc4c01c55033c03	Consolidated	2026-06-30	13	prescribed under Section 133 of the Companies Act, 2013, the relevant provisions of the Banking Regulation Act, 1949
T3.19	pdf	b28a719174d31592413f317e9baf527e4dd127f18b2468179d9cc0bfa74fabd1	Standalone	2026-09-30	3	Operotinq expenses le)+(f)
T3.20	pdf	b28a719174d31592413f317e9baf527e4dd127f18b2468179d9cc0bfa74fabd1	Standalone	2026-09-30	3	Tax expense !a)+(h)
T3.21	pdf	1b3599e2a01fc9b77f913fef7a3068bca6ec43c722010a1c1bc4c01c55033c03	Standalone	2026-06-30	3	Operatinq expenses (e)+(f)
T3.22	pdf	b28a719174d31592413f317e9baf527e4dd127f18b2468179d9cc0bfa74fabd1	Standalone	2026-09-30	3	Current tax
T3.23	pdf	b28a719174d31592413f317e9baf527e4dd127f18b2468179d9cc0bfa74fabd1	Standalone	2026-09-30	3	Deferred tax
T3.24	pdf	b28a719174d31592413f317e9baf527e4dd127f18b2468179d9cc0bfa74fabd1	Standalone	2026-09-30	3	ACTIVITIES BEFORE TAX (9)-(10)
T3.25	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	SegmentRevenue@FourReportable11D	*
T3.26	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	SegmentRevenue@FourReportable12D	*
T3.27	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	SegmentRevenue@FourReportable13D	*
T3.28	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	SegmentRevenue@FourReportable14D	*
T3.29	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	SegmentRevenue@OneReportable11D	*
T3.30	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	SegmentRevenue@OneReportable12D	*
T3.31	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	SegmentRevenue@OneReportable13D	*
T3.32	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	SegmentRevenue@OneReportable14D	*
T3.33	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	SegmentProfitLossBeforeTaxAndFinanceCosts@FourReportable21D	*
T3.34	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	SegmentProfitLossBeforeTaxAndFinanceCosts@FourReportable22D	*
T3.35	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	SegmentProfitLossBeforeTaxAndFinanceCosts@FourReportable23D	*
T3.36	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	SegmentProfitLossBeforeTaxAndFinanceCosts@FourReportable24D	*
T3.37	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	SegmentProfitLossBeforeTaxAndFinanceCosts@OneReportable21D	*
T3.38	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	SegmentProfitLossBeforeTaxAndFinanceCosts@OneReportable22D	*
T3.39	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	SegmentProfitLossBeforeTaxAndFinanceCosts@OneReportable23D	*
T3.40	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	SegmentProfitLossBeforeTaxAndFinanceCosts@OneReportable24D	*
T3.41	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	SegmentAssets@OneReportable31I	*
T3.42	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	SegmentAssets@OneReportable32I	*
T3.43	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	SegmentAssets@OneReportable33I	*
T3.44	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	SegmentAssets@OneReportable34I	*
T3.45	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	SegmentLiabilities@OneReportable41I	*
T3.46	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	SegmentLiabilities@OneReportable42I	*
T3.47	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	SegmentLiabilities@OneReportable43I	*
T3.48	xbrl-fact	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	SegmentLiabilities@OneReportable44I	*
T3.49	pdf-title	b28a719174d31592413f317e9baf527e4dd127f18b2468179d9cc0bfa74fabd1	Standalone	2026-09-30	3	ICICI Bank Limited|STANDALONE FINANCIAL RESULTS
T3.50	pdf-title	1b3599e2a01fc9b77f913fef7a3068bca6ec43c722010a1c1bc4c01c55033c03	Standalone	2026-06-30	3	ICICI Bank Limited|STANDALONE FINANCIAL RESULTS
T3.51	pdf-line-absent	b28a719174d31592413f317e9baf527e4dd127f18b2468179d9cc0bfa74fabd1	Standalone	2026-09-30	3	(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2},\s*\d{4}
T3.52	pdf-line-absent	1b3599e2a01fc9b77f913fef7a3068bca6ec43c722010a1c1bc4c01c55033c03	Standalone	2026-06-30	3	(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2},\s*\d{4}
T3.53	pdf	b28a719174d31592413f317e9baf527e4dd127f18b2468179d9cc0bfa74fabd1	Standalone	2026-09-30	8	during six months ended September 30, 2026
T3.54	pdf-title	b28a719174d31592413f317e9baf527e4dd127f18b2468179d9cc0bfa74fabd1	Consolidated	2026-09-30	13	ICICI Bonk Limited|CONSOLIDATED FINANCIAL RESULTS
T3.55	pdf	b28a719174d31592413f317e9baf527e4dd127f18b2468179d9cc0bfa74fabd1	Standalone	2026-09-30	5	Employees stock options/units outstanding
T3.56	xbrl-sum-absent	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	Capital@OneI	PaidUpValueOfEquityShareCapital@OneD
T3.57	pdf	b28a719174d31592413f317e9baf527e4dd127f18b2468179d9cc0bfa74fabd1	Standalone	2026-09-30	11	Segmental Results (i.e.
T3.58	pdf	1b3599e2a01fc9b77f913fef7a3068bca6ec43c722010a1c1bc4c01c55033c03	Standalone	2026-06-30	9	Segmental Results (i.e. Profit before tax)
T3.59	xbrl-sum	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	SegmentProfitLossBeforeTaxAndFinanceCosts@OneD	SegmentProfitBeforeTax@OneD|ProfitLossFromOrdinaryActivitiesBeforeTax@OneD
T3.60	xbrl-sum	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	SegmentProfitLossBeforeTaxAndFinanceCosts@FourD	SegmentProfitBeforeTax@FourD|ProfitLossFromOrdinaryActivitiesBeforeTax@FourD
T3.61	xbrl-sum-absent	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	InterestExpended@OneD	0
T3.62	xbrl-sum-absent	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	InterestExpended@FourD	0
T3.63	xbrl-sum	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	SegmentRevenue@OneReportable11D+SegmentRevenue@OneReportable12D+SegmentRevenue@OneReportable13D+SegmentRevenue@OneReportable14D	SegmentRevenue@OneD
T3.64	xbrl-sum	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	SegmentRevenue@FourReportable11D+SegmentRevenue@FourReportable12D+SegmentRevenue@FourReportable13D+SegmentRevenue@FourReportable14D	SegmentRevenue@FourD
T3.65	xbrl-sum	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	SegmentRevenueFromOperations@OneD+InterSegmentRevenue@OneD	SegmentRevenue@OneD
T3.66	xbrl-sum	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	SegmentRevenueFromOperations@FourD+InterSegmentRevenue@FourD	SegmentRevenue@FourD
T3.67	pdf	b28a719174d31592413f317e9baf527e4dd127f18b2468179d9cc0bfa74fabd1	Standalone	2026-09-30	11	Less: Inter segment
T3.68	xbrl-sum	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	SegmentAssets@OneReportable31I+SegmentAssets@OneReportable32I+SegmentAssets@OneReportable33I+SegmentAssets@OneReportable34I	SegmentAssets@OneI
T3.69	xbrl-sum	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	SegmentAssets@OneI+UnAllocableAssets@OneI	NetSegmentAssets@OneI|Assets@OneI
T3.70	pdf-page-absent	b28a719174d31592413f317e9baf527e4dd127f18b2468179d9cc0bfa74fabd1	Standalone	2026-09-30	11	inter.?segment (assets|liabilities)
T3.71	xbrl-sum	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	SegmentLiabilities@OneReportable41I+SegmentLiabilities@OneReportable42I+SegmentLiabilities@OneReportable43I+SegmentLiabilities@OneReportable44I	SegmentLiabilities@OneI
T3.72	xbrl-sum	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	SegmentLiabilities@OneI+UnAllocableLiabilities@OneI	NetSegmentLiabilities@OneI|CapitalAndLiabilities@OneI
T3.73	pdf	b28a719174d31592413f317e9baf527e4dd127f18b2468179d9cc0bfa74fabd1	Standalone	2026-09-30	11	Caoital Emploved
T3.74	pdf	1b3599e2a01fc9b77f913fef7a3068bca6ec43c722010a1c1bc4c01c55033c03	Standalone	2026-06-30	9	Capital Employed
T3.75	pdf	1b3599e2a01fc9b77f913fef7a3068bca6ec43c722010a1c1bc4c01c55033c03	Standalone	2026-06-30	9	Total (4) + (5)
T3.76	xbrl-shape	a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3	Standalone	2026-09-30	ProceedsFromIssuingShares@FourD	decimals=-5;unit=INR;sign=+
T3.77	pdf	b28a719174d31592413f317e9baf527e4dd127f18b2468179d9cc0bfa74fabd1	Standalone	2026-09-30	6	Proceeds from issue of share capitol (includina ESOPs/ESUSs)
T3.78	pdf	b28a719174d31592413f317e9baf527e4dd127f18b2468179d9cc0bfa74fabd1	Standalone	2026-09-30	6	Cash flow from/(used in) flnancinq activities
T3.79	pdf	b28a719174d31592413f317e9baf527e4dd127f18b2468179d9cc0bfa74fabd1	Standalone	2026-09-30	6	Purchase of fixed assets
T3.80	pdf	b28a719174d31592413f317e9baf527e4dd127f18b2468179d9cc0bfa74fabd1	Standalone	2026-09-30	6	Proceeds from sole of fixed assets
T3.81	pdf	b28a719174d31592413f317e9baf527e4dd127f18b2468179d9cc0bfa74fabd1	Standalone	2026-09-30	6	Cash and cash equivalents include cash in hand
```

## Ledger

VENDOR-1 Phase 3 Task 3 (F12, F13, R2-05). **Draft for Sol review; not frozen.** Its sha256 is
recorded here and in the plan only after `APPROVE`. Written from the evidence above alone: every
line cites a locator, and nothing in it is read from code behaviour. It assumes B1b `INDIAN_GAAP`.
**Revised A7 is not met by the retained PDFs, so B1c stands and the phase halts at Task 3**
(plan, Resolved branches). This ledger is not in force. It is corrected for Sol review 1 so that
a later amendment releasing B1c starts from reviewed expectations. It is never frozen while B1c
stands.

**Scope.** The acceptance run: family `FINANCIAL_RESULTS`, entity ICICIBANK, issuer class `BANK`,
framework `INDIAN_GAAP`, basis `STANDALONE` (owner decision 2), period end 2026-09-30, whose fiscal
periods are the quarter and the half-year; the instance files both (`OneD` [B3.10], `FourD`
2026-04-01 to 2026-09-30 [B8.24]). The first-party side is the XBRL-only package of instance
`a2d49864…` (B7b). Keys are dictionary v4's rows plus the six bank rows below, as v5 will hold them.

**Dictionary v4 baseline.** v4 is v3 plus `current_tax_excl_earlier_years` (plan base ruling).
v4 is not on `main` at this draft: its rows are read from branch `fix-results-pdf-data-quality`
(`f75892e8`) plus v3's three shareholding basket rows (`derived.yaml`), which that branch's v4
(still on v2) lacks. If the landed v4's row set differs, this ledger is amended before Task 6.

**Columns.** *Period*: `Q` the quarter 2026-07-01..2026-09-30 (`OneD`), `H1` the half-year
2026-04-01..2026-09-30 (`FourD`), `I` the instant 2026-09-30 (`OneI`). A dimensioned row has
one line per evidenced member set. Its key names every axis: `segment` and `elimination_basis`
(templates.yaml). *Capability*: the statement's capability for that period kind and basis.
*Expected result*:

- `VALUE <QName@contextRef>`: the first-party side carries that filed fact. `VALUE computed`: a
  formula row whose operands are all `VALUE` lines here. Code computes it and records its trace.
  It is never an observed fact (Task 8 checks it through the formula path).
- `NOT_APPLICABLE <rule>`: `ISSUER_RULE_ID` for a row v5 restricts to `NON_FINANCIAL` (ruled
  below), or the unchanged v4 rule named.
- `REFUSED <reason>`: the row applies and the first-party side has no value, for the reason
  given: `R-NF` the pinned instance files no element with the row's meaning at that context (the
  context's complete numeric concept set is `T3.01`–`T3.04`); `R-PDF` v4 names no XBRL element for
  the row and the package is XBRL-only (B7b); `R-QCF` the filing has no quarter cash-flow column
  (cash-flow concepts are filed at `FourD` only, `T3.01`, `T3.02`); `R-SIGN` the bank element
  `ExceptionalItems` is filed but its sign is not evidenced as v4's "positive is a gain" (the
  statement prints "ACTIVITIES BEFORE TAX (9)-(10)", `T3.24`, the opposite sense), so it is not
  mapped (Sol ruling: the opposite sign is suggested, not proved; the filed Q and H1 values are
  zero and do not discriminate); `R-CON` v4's construction needs `share_of_profit_associates_jv`,
  which is not filed; `R-OP` a formula operand is a `REFUSED` line, or a dimensioned operand has
  no key. The fix round adds three reasons. `R-MEAN`: the bank files an element under v4's name or
  a candidate alias, but its evidenced meaning is not the row's, so it is not mapped (Meaning
  audit). `R-SCOPE`: the bank files a related element whose scope differs from the row's (Alias
  audit). `R-TIME`: the row's element is filed only at another instant, and no mapping moves it.
- `no key`: a dimensioned row with no member the package evidences enumerates no key. This
  includes a dimensioned row whose filed members are `R-MEAN`. The engine enumerates member sets
  only from interpretations (`engine._evidence_dimensions`).

**Issuer applicability (v5), by row.** A row is restricted to `NON_FINANCIAL` when its meaning is
a line of the non-financial layout with no bank meaning (spec §8 step 3: revenue from operations,
materials, inventories, working capital). The bank layout is evidenced by the pinned instance's
concept sets `T3.01`–`T3.03`: the bank P&L (interest earned, other income, interest expended,
operating expenses, provisions and contingencies) and the bank balance sheet (capital, reserves
and surplus, deposits, borrowings, other liabilities and provisions, cash and balances with RBI,
balances with banks, investments, advances, fixed assets, other assets), with no current or
non-current classification.

- `NON_FINANCIAL` only: P&L `sales`, `other_operating_income`, `revenue_from_operations`,
  `excise_duty`, `total_income` (defined as revenue from operations plus other income),
  `cost_of_materials_consumed`, `purchases_of_stock_in_trade`, `changes_in_inventories`,
  `finance_costs` (a bank's interest cost is the bank row `interest_expended`), `other_expenses`,
  `other_expenses_detail` and `total_expenses` (residual and total of that layout); every balance-sheet
  row classified current or non-current, plus `inventories`, the trade receivable and payable rows,
  the MSME dues rows and `other_bank_balances`; every `cf_wc_*` cash-flow row and
  `cf_adj_provisions_current`/`_noncurrent`; and the formulas built on them (`opex_excl_finance_and_da`,
  `ebitda_excl_other_income`, `opm_pct`, `pbdt_vendor`, `pbt_margin_pct`, `material_cost_pct`,
  `employee_cost_pct`, `cfo_to_op_pct`, `receivable_days`, `net_current_assets`, `cf_wc_total`,
  `net_profit_margin_pct`, `gross_margin_pct`).
- Shared (both classes): every other v4 row, including the Ind AS-only lines (OCI, comprehensive
  income, regulatory deferral, discontinued operations): their meaning is not sector-specific, and
  they refuse here because the filing carries none, not by issuer rule.
- `BANK` only: the six rows below.

**Shared rows valued from a bank element** (the bank QName differs from v4's; the meaning holds):
`profit_before_tax` ← `ProfitLossFromOrdinaryActivitiesBeforeTax` (standalone: no associates
line); `profit_for_period` ← `ProfitLossForThePeriod`; `employee_benefits_expense` ←
`EmployeesCost`; `eps_basic`/`eps_diluted` ← `Basic`/`DilutedEarningsPerShareAfterExtraordinaryItems`
(EPS on the period's whole profit: INR per share, separate Q and H1 periods, never summed or
annualised; Sol ruling); `total_equity_and_liabilities` ← `CapitalAndLiabilities`;
`cf_proceeds_shares` ← `ProceedsFromIssuingShares@FourD` (Meaning audit). Every other `VALUE`
line is v4's own element, filed at that context. Task 8 maps nothing a `REFUSED` or `no key`
line names, and none of the other filed bank lines (no row). The equity alias of the first draft
is withdrawn (Meaning audit).

**Meaning audit (Task 3 review 1).** Each item is established from the retained statement. A
locator is not proof of equivalence; the stated relation is.

- **Equity (L137, L138: `R-MEAN`).** v4's `equity_share_capital` is the share-capital line alone,
  and `other_equity` is all equity other than share capital. The bank's balance sheet prints
  "Employees stock options/units outstanding" as its own line, between capital and reserves
  [T3.55]. `Capital@OneI` differs from `PaidUpValueOfEquityShareCapital@OneD` [T3.56], so the
  filed `Capital` combines share capital with that balance (Sol, finding 2, by decimal
  arithmetic). Neither row has a supported standard element. `ReservesAndSurplus` omits the
  option balance, so it is not `other_equity`. Both refuse. Neither is filled from a combination:
  v4 has no formula row for either, and a combination would be a computed key with its trace,
  not a reported value. `paid_up_equity_capital` stays the distinct, correctly scoped row. Its
  duration-filed fact is outside this ledger's balance-sheet lines, as before.
- **Segment result (L375–L384: `R-MEAN`).** v4's `segment_result` is profit before finance
  costs and tax. The bank's measure is "Segmental Results (i.e. Profit before tax)" [T3.57,
  T3.58]. In the instance, `SegmentProfitLossBeforeTaxAndFinanceCosts` equals both
  `SegmentProfitBeforeTax` and the bank's profit before tax, for Q and H1 [T3.59, T3.60]. Interest
  expended is non-zero in both periods [T3.61, T3.62]. The QName does not carry v4's meaning.
  Members enumerate no key, and the total refuses. Mapping isolation is in the plan (Task 8):
  Apar's 2026 entry `capmkt.segment_result_total.2026` selects the same element in the same
  namespace, and no supported selector separates the bank from Apar.
- **Segment liabilities (L401–L405, L407: `R-MEAN`).** The bank's filed segment liabilities, with
  unallocated liabilities, equal `NetSegmentLiabilities` and also total capital *and* liabilities
  [T3.71, T3.72]. The statement presents "Capital Employed" as its own line 5, outside the
  segment liabilities, with "Total (4) + (5)" [T3.73–T3.75]. So the filed member and total
  figures include equity that the statement keeps out of segment liabilities. That is not v4's
  liabilities meaning; Apar's `NetSegmentLiabilities` is its liabilities alone (`xbrl/v5/in_capmkt.yaml`
  evidence ref). Members enumerate no key; the total and net refuse. `segment_unallocable_liabilities`
  (L406) keeps its value. `segment_capital_employed` (L443–L446) refuses `R-OP`: its liabilities
  operand has no key.
- **Opening cash (L359: `R-TIME`).** `CashAndCashEquivalentsCashFlowStatement@PY_I` is the instant
  2026-03-31 [T3.04, B8.26]. The key is the instant 2026-09-30. Interpretation keeps XBRL periods,
  and the existing mapping reads this element as closing cash at each instant. The September
  `cf_cash_opening` key therefore has no first-party value and refuses, as it does for Apar
  today. Nothing is retimestamped. An opening-balance design that relates the March instant to
  H1 would need its own reviewed amendment.
- **Share proceeds (L322: `VALUE`).** `ProceedsFromIssuingShares@FourD` is filed for
  2026-04-01..2026-09-30 [T3.02, B8.24], in INR, with `decimals=-5`, as a positive inflow
  [T3.76]. The statement prints it as "Proceeds from issue of share capital (including
  ESOPs/ESUSs)", directly under the financing-activities heading [T3.77, T3.78]. That is v4's
  "Proceeds from issuing shares (financing)". The combined line is not split:
  `cf_proceeds_stock_options` (L326) refuses `R-SCOPE`.

**Alias audit (every refusal where the bank files a related element).** Each `R-NF` line was
checked by meaning against `T3.01`–`T3.03`. A reason is never "Apar's element name is absent".

| Lines | Row | Bank element(s) | Decision |
|---|---|---|---|
| L030–L031 | `profit_before_exceptional_items_and_tax` | `OperatingProfitBeforeProvisionAndContingencies`; `ProfitBeforeExtraordinaryItemsAndTax` (H1) | `R-SCOPE`. The first is before provisions. The second is before *extraordinary* items, which the bank files apart from `ExceptionalItems` [T3.01]. |
| L050–L051 | `profit_continuing_after_tax` | `ProfitLossFromOrdinaryActivitiesAfterTax` | `R-SCOPE`. Ordinary activities (before extraordinary items) is not continuing operations (before discontinued operations). |
| L062–L063 | `profit_attributable_owners` | `ProfitLossAfterTaxesMinorityInterestAndShareOfProfitLossOfAssociates` | `R-SCOPE`. A consolidation line; the standalone statement attributes nothing to owners or NCI. As for Apar, it is not mapped. |
| L093–L094, L099–L100 | `eps_basic_continuing`, `eps_diluted_continuing` | `Basic`/`DilutedEarningsPerShareBeforeExtraordinaryItems` | `R-SCOPE`. Same distinction: before extraordinary items is not continuing operations. |
| L103 | `ppe` | `FixedAssets` | `R-SCOPE`. The filing does not give the composition of "fixed assets". v4 keeps PPE apart from CWIP and intangibles. |
| L125 | `cash_and_cash_equivalents` | `CashAndBalancesWithReserveBankOfIndia`, `BalancesWithBanksAndMoneyAtCallAndShortNotice` | `R-SCOPE`. The balance sheet has no single cash line. The cash-flow measure "include[s] cash in hand … balances with RBI, balances with other banks and money at call" [T3.81] and is `cf_cash_closing` (L360). A sum would be computed, not reported. |
| L258, L260 | `cf_capex_ppe`, `cf_sale_ppe` | `PurchaseOf`/`ProceedsFromSalesOfTangibleAssetsClassifiedAsInvestingActivities` | `R-SCOPE`. The statement line is "Purchase of fixed assets" / "Proceeds from sale of fixed assets" [T3.79, T3.80], with the same undisclosed composition as L103. The "tangible" tag does not show that CWIP is excluded. |
| L326 | `cf_proceeds_stock_options` | inside `ProceedsFromIssuingShares` | `R-SCOPE`. It is combined in L322 and is not split. |
| L023–L024 | `depreciation_amortisation` | `AdjustmentsForDepreciationAndAmortisationExpense` (cash flow) | `R-NF` confirmed. The P&L files no depreciation line; the adjustment is `cf_adj_depreciation` (L174). |
| L040–L041, L044–L045 | `current_tax`, `deferred_tax` | `TaxExpense` only | `R-NF` confirmed. The split is printed only in the PDF [T3.22, T3.23], which is not a member (B7b). |
| L141, L169 | `total_equity`, `total_liabilities` | `Capital`, `ReservesAndSurplus`; `Deposits`, `Borrowings`, `OtherLiabilitiesAndProvisions` | `R-NF` confirmed. No single element; a sum would be computed. |
| L385–L388 | `segment_finance_costs`, `segment_unallocable_net` | none | `R-NF` confirmed. The bank's segment results are after finance costs (above). |

The remaining `R-NF` lines name rows whose subject the bank files nowhere: associates, discontinued
operations, OCI and comprehensive income, NCI, regulatory deferral, goodwill, intangibles,
investment property, biological assets, deferred tax balances, held-for-sale items, and the
financing and investing rows with no bank element.

**Bank rows Task 6 adds** (spec §8 step 3 list; names from the record): `interest_earned`
(`InterestEarned`, P&L, duration), `interest_expended` (`InterestExpended`), `provisions_and_contingencies`
(`ProvisionsOtherThanTaxAndContingencies`, "Provisions (other than tax) and contingencies"),
`deposits` (`Deposits`, balance sheet, instant), `advances` (`Advances`) and `bank_investments`
(`Investments`, "investments as a bank line"). Each declares `BANK` and the v4 family defaults of
its statement.

**Segments.** Members, from `DescriptionOfReportableSegment` [T3.05–T3.08]: `retail` (member 1),
`wholesale` (2), `treasury` (3), `other_banking` (4). Every `elimination_basis` member is frozen
here from the filing. Task 8 implements it and never chooses it.
- `segment_revenue` (and `segment_revenue_members_total`): `PRE_ELIMINATION`. The members sum to
  `SegmentRevenue` with no dimension, and `SegmentRevenueFromOperations` plus
  `InterSegmentRevenue` equals that total, for Q and H1 [T3.63–T3.66]. The statement prints
  "Less: Inter segment revenue" after the total [T3.67]. The members are before elimination.
- `segment_assets`: `POST_ELIMINATION`. The members sum to `SegmentAssets` with no dimension. That
  total plus unallocated assets equals `NetSegmentAssets` and the balance-sheet `Assets`
  [T3.68, T3.69]. The segment page prints no inter-segment asset or liability line [T3.70]. Figures
  that reconcile to the entity total with no elimination line are after any elimination.
- `segment_liabilities`: no basis is frozen, because the meaning is refused (Meaning audit).
  `segment_capital_employed` (assets less liabilities on one basis) therefore has no common basis
  and refuses `R-OP`.

**Excluded families.** `SHAREHOLDING` (`shareholding.yaml`'s four rows): not enumerated by a
`FINANCIAL_RESULTS` run; no shareholding filing is in Phase 3 scope. The three shareholding
basket formulas in `derived.yaml` enumerate no key here (`no key` lines). No other family exists.

**Admissible cells (rehearsal, §6.5).** The 102 reported `VALUE` lines. Each is expected to admit
with label `CHECKED_AGAINST_FILING` under row 1, 2 or 5; which row depends on Task 12's vendor
sides (B9) and is recorded at Task 13. A row 0a refusal of one of them is a deviation that blocks
Task 13 until reviewed. Not admissible: the 5 `VALUE computed` lines. Derived figures are
calculated by code from admitted facts (§6.4 T1 rule 1), and `admit_run` refuses non-`REPORTED`
rows as `NOT_REPORTED` (`admission.py:277–278`). Their reported operands follow the admission
rules for those lines. Also not admissible: every `REFUSED` line (no row 3 for `BANK`, so row 4
or 6 refuses), and every `NOT_APPLICABLE` and `no key` line.

**Counts.** 457 lines: `VALUE` 107 (102 filed, 5 computed); `NOT_APPLICABLE` 128 (127
`ISSUER_RULE_ID`, 1 `results.annual_disclosure`); `REFUSED` 204 (`R-NF` 77, `R-QCF` 76, `R-PDF`
18, `R-SCOPE` 15, `R-OP` 7, `R-MEAN` 6, `R-SIGN` 2, `R-CON` 2, `R-TIME` 1); `no key` 18 (6 as
before, 12 `R-MEAN` segment members). Capability: 345 `SUPPORTED` lines, 94
`UNSUPPORTED: no quarter cash-flow statement` (76 of them `R-QCF`, 18 `ISSUER_RULE_ID`), 18 `—`
(`no key`); no balance sheet, cash-flow (half-year) or segment capability is unsupported at this
period (B8). Against the first draft, 19 reported values leave (equity 2, segment result 10,
segment liabilities 6, opening cash 1) and 1 is added (share proceeds), a net change of 18. The 4
segment capital-employed computed values also leave.

| # | Key | Period | Capability | Expected result | Locator |
|---|---|---|---|---|---|
| L001 | `sales` | Q 2026-07-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.01 |
| L002 | `sales` | H1 2026-04-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.02 |
| L003 | `other_operating_income` | Q 2026-07-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.01 |
| L004 | `other_operating_income` | H1 2026-04-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.02 |
| L005 | `revenue_from_operations` | Q 2026-07-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.01 |
| L006 | `revenue_from_operations` | H1 2026-04-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.02 |
| L007 | `excise_duty` | Q 2026-07-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.01 |
| L008 | `excise_duty` | H1 2026-04-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.02 |
| L009 | `other_income` | Q 2026-07-01..2026-09-30 | SUPPORTED | VALUE `OtherIncome@OneD` | T3.01 |
| L010 | `other_income` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `OtherIncome@FourD` | T3.02 |
| L011 | `total_income` | Q 2026-07-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.01 |
| L012 | `total_income` | H1 2026-04-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.02 |
| L013 | `cost_of_materials_consumed` | Q 2026-07-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.01 |
| L014 | `cost_of_materials_consumed` | H1 2026-04-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.02 |
| L015 | `purchases_of_stock_in_trade` | Q 2026-07-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.01 |
| L016 | `purchases_of_stock_in_trade` | H1 2026-04-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.02 |
| L017 | `changes_in_inventories` | Q 2026-07-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.01 |
| L018 | `changes_in_inventories` | H1 2026-04-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.02 |
| L019 | `employee_benefits_expense` | Q 2026-07-01..2026-09-30 | SUPPORTED | VALUE `EmployeesCost@OneD` | T3.01 |
| L020 | `employee_benefits_expense` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `EmployeesCost@FourD` | T3.02 |
| L021 | `finance_costs` | Q 2026-07-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.01 |
| L022 | `finance_costs` | H1 2026-04-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.02 |
| L023 | `depreciation_amortisation` | Q 2026-07-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.01 |
| L024 | `depreciation_amortisation` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.02 |
| L025 | `other_expenses` | Q 2026-07-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.01 |
| L026 | `other_expenses` | H1 2026-04-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.02 |
| L027 | `other_expenses_detail` | — | — | no key: no evidenced member | T3.01 |
| L028 | `total_expenses` | Q 2026-07-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.01 |
| L029 | `total_expenses` | H1 2026-04-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.02 |
| L030 | `profit_before_exceptional_items_and_tax` | Q 2026-07-01..2026-09-30 | SUPPORTED | REFUSED R-SCOPE | T3.01 |
| L031 | `profit_before_exceptional_items_and_tax` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-SCOPE | T3.02 |
| L032 | `exceptional_items_before_tax` | Q 2026-07-01..2026-09-30 | SUPPORTED | REFUSED R-SIGN | T3.01 |
| L033 | `exceptional_items_before_tax` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-SIGN | T3.02 |
| L034 | `profit_before_tax` | Q 2026-07-01..2026-09-30 | SUPPORTED | VALUE `ProfitLossFromOrdinaryActivitiesBeforeTax@OneD` | T3.01 |
| L035 | `profit_before_tax` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `ProfitLossFromOrdinaryActivitiesBeforeTax@FourD` | T3.02 |
| L036 | `share_of_profit_associates_jv` | Q 2026-07-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.01 |
| L037 | `share_of_profit_associates_jv` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.02 |
| L038 | `profit_before_tax_incl_associates` | Q 2026-07-01..2026-09-30 | SUPPORTED | REFUSED R-CON | T3.01 |
| L039 | `profit_before_tax_incl_associates` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-CON | T3.02 |
| L040 | `current_tax` | Q 2026-07-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.01 |
| L041 | `current_tax` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.02 |
| L042 | `current_tax_excl_earlier_years` | Q 2026-07-01..2026-09-30 | SUPPORTED | REFUSED R-PDF | — |
| L043 | `current_tax_excl_earlier_years` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-PDF | — |
| L044 | `deferred_tax` | Q 2026-07-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.01 |
| L045 | `deferred_tax` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.02 |
| L046 | `tax_earlier_years` | Q 2026-07-01..2026-09-30 | SUPPORTED | REFUSED R-PDF | — |
| L047 | `tax_earlier_years` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-PDF | — |
| L048 | `tax_expense` | Q 2026-07-01..2026-09-30 | SUPPORTED | VALUE `TaxExpense@OneD` | T3.01 |
| L049 | `tax_expense` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `TaxExpense@FourD` | T3.02 |
| L050 | `profit_continuing_after_tax` | Q 2026-07-01..2026-09-30 | SUPPORTED | REFUSED R-SCOPE | T3.01 |
| L051 | `profit_continuing_after_tax` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-SCOPE | T3.02 |
| L052 | `profit_discontinued_before_tax` | Q 2026-07-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.01 |
| L053 | `profit_discontinued_before_tax` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.02 |
| L054 | `tax_discontinued` | Q 2026-07-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.01 |
| L055 | `tax_discontinued` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.02 |
| L056 | `profit_discontinued_after_tax` | Q 2026-07-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.01 |
| L057 | `profit_discontinued_after_tax` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.02 |
| L058 | `regulatory_deferral_net_movement` | Q 2026-07-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.01 |
| L059 | `regulatory_deferral_net_movement` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.02 |
| L060 | `profit_for_period` | Q 2026-07-01..2026-09-30 | SUPPORTED | VALUE `ProfitLossForThePeriod@OneD` | T3.01 |
| L061 | `profit_for_period` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `ProfitLossForThePeriod@FourD` | T3.02 |
| L062 | `profit_attributable_owners` | Q 2026-07-01..2026-09-30 | SUPPORTED | REFUSED R-SCOPE | T3.01 |
| L063 | `profit_attributable_owners` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-SCOPE | T3.02 |
| L064 | `profit_attributable_nci` | Q 2026-07-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.01 |
| L065 | `profit_attributable_nci` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.02 |
| L066 | `oci_not_reclassified_items` | Q 2026-07-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.01 |
| L067 | `oci_not_reclassified_items` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.02 |
| L068 | `oci_not_reclassified_items_detail` | — | — | no key: no evidenced member | T3.01 |
| L069 | `oci_not_reclassified_tax` | Q 2026-07-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.01 |
| L070 | `oci_not_reclassified_tax` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.02 |
| L071 | `oci_reclassified_items` | Q 2026-07-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.01 |
| L072 | `oci_reclassified_items` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.02 |
| L073 | `oci_reclassified_items_detail` | — | — | no key: no evidenced member | T3.01 |
| L074 | `oci_reclassified_tax` | Q 2026-07-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.01 |
| L075 | `oci_reclassified_tax` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.02 |
| L076 | `oci_net` | Q 2026-07-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.01 |
| L077 | `oci_net` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.02 |
| L078 | `total_comprehensive_income` | Q 2026-07-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.01 |
| L079 | `total_comprehensive_income` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.02 |
| L080 | `tci_attributable_owners` | Q 2026-07-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.01 |
| L081 | `tci_attributable_owners` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.02 |
| L082 | `tci_attributable_nci` | Q 2026-07-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.01 |
| L083 | `tci_attributable_nci` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.02 |
| L084 | `oci_attributable_owners` | Q 2026-07-01..2026-09-30 | SUPPORTED | REFUSED R-PDF | — |
| L085 | `oci_attributable_owners` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-PDF | — |
| L086 | `oci_attributable_nci` | Q 2026-07-01..2026-09-30 | SUPPORTED | REFUSED R-PDF | — |
| L087 | `oci_attributable_nci` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-PDF | — |
| L088 | `paid_up_equity_capital` | I 2026-09-30 | SUPPORTED | VALUE `PaidUpValueOfEquityShareCapital@OneD` | T3.01 |
| L089 | `face_value_per_share` | I 2026-09-30 | SUPPORTED | VALUE `FaceValueOfEquityShareCapital@OneD` | T3.01 |
| L090 | `reserves_excl_revaluation` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `results.annual_disclosure` | T3.03 |
| L091 | `eps_basic` | Q 2026-07-01..2026-09-30 | SUPPORTED | VALUE `BasicEarningsPerShareAfterExtraordinaryItems@OneD` | T3.01 |
| L092 | `eps_basic` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `BasicEarningsPerShareAfterExtraordinaryItems@FourD` | T3.02 |
| L093 | `eps_basic_continuing` | Q 2026-07-01..2026-09-30 | SUPPORTED | REFUSED R-SCOPE | T3.01 |
| L094 | `eps_basic_continuing` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-SCOPE | T3.02 |
| L095 | `eps_basic_discontinued` | Q 2026-07-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.01 |
| L096 | `eps_basic_discontinued` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.02 |
| L097 | `eps_diluted` | Q 2026-07-01..2026-09-30 | SUPPORTED | VALUE `DilutedEarningsPerShareAfterExtraordinaryItems@OneD` | T3.01 |
| L098 | `eps_diluted` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `DilutedEarningsPerShareAfterExtraordinaryItems@FourD` | T3.02 |
| L099 | `eps_diluted_continuing` | Q 2026-07-01..2026-09-30 | SUPPORTED | REFUSED R-SCOPE | T3.01 |
| L100 | `eps_diluted_continuing` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-SCOPE | T3.02 |
| L101 | `eps_diluted_discontinued` | Q 2026-07-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.01 |
| L102 | `eps_diluted_discontinued` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.02 |
| L103 | `ppe` | I 2026-09-30 | SUPPORTED | REFUSED R-SCOPE | T3.03 |
| L104 | `right_of_use_assets` | I 2026-09-30 | SUPPORTED | REFUSED R-PDF | — |
| L105 | `cwip` | I 2026-09-30 | SUPPORTED | REFUSED R-NF | T3.03 |
| L106 | `goodwill` | I 2026-09-30 | SUPPORTED | REFUSED R-NF | T3.03 |
| L107 | `other_intangible_assets` | I 2026-09-30 | SUPPORTED | REFUSED R-NF | T3.03 |
| L108 | `intangibles_under_development` | I 2026-09-30 | SUPPORTED | REFUSED R-NF | T3.03 |
| L109 | `investment_property` | I 2026-09-30 | SUPPORTED | REFUSED R-NF | T3.03 |
| L110 | `biological_assets` | I 2026-09-30 | SUPPORTED | REFUSED R-NF | T3.03 |
| L111 | `investments_equity_method` | I 2026-09-30 | SUPPORTED | REFUSED R-NF | T3.03 |
| L112 | `noncurrent_investments` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L113 | `trade_receivables_noncurrent` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L114 | `loans_noncurrent` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L115 | `other_noncurrent_financial_assets` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L116 | `derivative_financial_assets_noncurrent` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L117 | `noncurrent_financial_assets` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L118 | `deferred_tax_assets_net` | I 2026-09-30 | SUPPORTED | REFUSED R-NF | T3.03 |
| L119 | `noncurrent_tax_assets` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L120 | `other_noncurrent_assets` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L121 | `noncurrent_assets_total` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L122 | `inventories` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L123 | `current_investments` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L124 | `trade_receivables_current` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L125 | `cash_and_cash_equivalents` | I 2026-09-30 | SUPPORTED | REFUSED R-SCOPE | T3.03, T3.81 |
| L126 | `other_bank_balances` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L127 | `loans_current` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L128 | `other_current_financial_assets` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L129 | `derivative_financial_assets_current` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L130 | `current_financial_assets` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L131 | `current_tax_assets` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L132 | `other_current_assets` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L133 | `assets_held_for_sale` | I 2026-09-30 | SUPPORTED | REFUSED R-NF | T3.03 |
| L134 | `regulatory_deferral_debit` | I 2026-09-30 | SUPPORTED | REFUSED R-NF | T3.03 |
| L135 | `current_assets_total` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L136 | `total_assets` | I 2026-09-30 | SUPPORTED | VALUE `Assets@OneI` | T3.03 |
| L137 | `equity_share_capital` | I 2026-09-30 | SUPPORTED | REFUSED R-MEAN | T3.03, T3.55, T3.56 |
| L138 | `other_equity` | I 2026-09-30 | SUPPORTED | REFUSED R-MEAN | T3.03, T3.55 |
| L139 | `equity_attributable_owners` | I 2026-09-30 | SUPPORTED | REFUSED R-NF | T3.03 |
| L140 | `non_controlling_interest_bs` | I 2026-09-30 | SUPPORTED | REFUSED R-NF | T3.03 |
| L141 | `total_equity` | I 2026-09-30 | SUPPORTED | REFUSED R-NF | T3.03 |
| L142 | `borrowings_noncurrent` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L143 | `lease_liabilities_noncurrent` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L144 | `other_noncurrent_financial_liabilities` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L145 | `derivative_financial_liabilities_noncurrent` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L146 | `noncurrent_financial_liabilities` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L147 | `provisions_noncurrent` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L148 | `deferred_tax_liabilities_net` | I 2026-09-30 | SUPPORTED | REFUSED R-NF | T3.03 |
| L149 | `other_noncurrent_liabilities` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L150 | `deferred_government_grants_current` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L151 | `deferred_government_grants_noncurrent` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L152 | `noncurrent_liabilities_total` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L153 | `borrowings_current` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L154 | `lease_liabilities_current` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L155 | `trade_payables_msme` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L156 | `trade_payables_msme_noncurrent` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L157 | `trade_payables_others` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L158 | `trade_payables_current` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L159 | `trade_payables_noncurrent` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L160 | `other_current_financial_liabilities` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L161 | `derivative_financial_liabilities_current` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L162 | `current_financial_liabilities` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L163 | `other_current_liabilities` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L164 | `provisions_current` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L165 | `current_tax_liabilities` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L166 | `liabilities_held_for_sale` | I 2026-09-30 | SUPPORTED | REFUSED R-NF | T3.03 |
| L167 | `regulatory_deferral_credit` | I 2026-09-30 | SUPPORTED | REFUSED R-NF | T3.03 |
| L168 | `current_liabilities_total` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.03 |
| L169 | `total_liabilities` | I 2026-09-30 | SUPPORTED | REFUSED R-NF | T3.03 |
| L170 | `total_equity_and_liabilities` | I 2026-09-30 | SUPPORTED | VALUE `CapitalAndLiabilities@OneI` | T3.03 |
| L171 | `cf_profit_before_tax` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L172 | `cf_profit_before_tax` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-PDF | — |
| L173 | `cf_adj_depreciation` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L174 | `cf_adj_depreciation` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `AdjustmentsForDepreciationAndAmortisationExpense@FourD` | T3.02 |
| L175 | `cf_adj_gain_loss_sale_ppe` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L176 | `cf_adj_gain_loss_sale_ppe` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-PDF | — |
| L177 | `cf_adj_finance_costs` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L178 | `cf_adj_finance_costs` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `AdjustmentsForFinanceCosts@FourD` | T3.02 |
| L179 | `cf_adj_interest_income` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L180 | `cf_adj_interest_income` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.02 |
| L181 | `cf_adj_dividend_income` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L182 | `cf_adj_dividend_income` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `AdjustmentsForDividendIncome@FourD` | T3.02 |
| L183 | `cf_adj_unrealised_fx` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L184 | `cf_adj_unrealised_fx` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `AdjustmentsForUnrealisedForeignExchangeLossesGains@FourD` | T3.02 |
| L185 | `cf_adj_share_based_payments` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L186 | `cf_adj_share_based_payments` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `AdjustmentsForSharebasedPayments@FourD` | T3.02 |
| L187 | `cf_adj_impairment` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L188 | `cf_adj_impairment` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `AdjustmentsForImpairmentLossReversalOfImpairmentLossRecognisedInProfitOrLoss@FourD` | T3.02 |
| L189 | `cf_adj_fair_value` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L190 | `cf_adj_fair_value` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.02 |
| L191 | `cf_adj_profit_sale_investments` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L192 | `cf_adj_profit_sale_investments` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-PDF | — |
| L193 | `cf_adj_provisions_current` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.01 |
| L194 | `cf_adj_provisions_current` | H1 2026-04-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.02 |
| L195 | `cf_adj_provisions_noncurrent` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.01 |
| L196 | `cf_adj_provisions_noncurrent` | H1 2026-04-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.02 |
| L197 | `cf_adj_associates_undistributed` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L198 | `cf_adj_associates_undistributed` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.02 |
| L199 | `cf_adj_other_noncash` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L200 | `cf_adj_other_noncash` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `OtherAdjustmentsForNoncashItems@FourD` | T3.02 |
| L201 | `cf_adj_other_investing_financing` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L202 | `cf_adj_other_investing_financing` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `OtherAdjustmentsForWhichCashEffectsAreInvestingOrFinancingCashFlow@FourD` | T3.02 |
| L203 | `cf_adj_other_reconcile` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L204 | `cf_adj_other_reconcile` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `OtherAdjustmentsToReconcileProfitLoss@FourD` | T3.02 |
| L205 | `cf_wc_trade_receivables_current` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.01 |
| L206 | `cf_wc_trade_receivables_current` | H1 2026-04-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.02 |
| L207 | `cf_wc_trade_receivables_noncurrent` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.01 |
| L208 | `cf_wc_trade_receivables_noncurrent` | H1 2026-04-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.02 |
| L209 | `cf_wc_trade_and_other_receivables` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.01 |
| L210 | `cf_wc_trade_and_other_receivables` | H1 2026-04-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.02 |
| L211 | `cf_wc_inventories` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.01 |
| L212 | `cf_wc_inventories` | H1 2026-04-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.02 |
| L213 | `cf_wc_trade_payables_current` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.01 |
| L214 | `cf_wc_trade_payables_current` | H1 2026-04-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.02 |
| L215 | `cf_wc_trade_payables_noncurrent` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.01 |
| L216 | `cf_wc_trade_payables_noncurrent` | H1 2026-04-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.02 |
| L217 | `cf_wc_trade_and_other_payables` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.01 |
| L218 | `cf_wc_trade_and_other_payables` | H1 2026-04-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.02 |
| L219 | `cf_wc_other_current_assets` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.01 |
| L220 | `cf_wc_other_current_assets` | H1 2026-04-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.02 |
| L221 | `cf_wc_other_noncurrent_assets` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.01 |
| L222 | `cf_wc_other_noncurrent_assets` | H1 2026-04-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.02 |
| L223 | `cf_wc_other_current_liabilities` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.01 |
| L224 | `cf_wc_other_current_liabilities` | H1 2026-04-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.02 |
| L225 | `cf_wc_other_noncurrent_liabilities` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.01 |
| L226 | `cf_wc_other_noncurrent_liabilities` | H1 2026-04-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.02 |
| L227 | `cf_wc_other_financial_assets_current` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.01 |
| L228 | `cf_wc_other_financial_assets_current` | H1 2026-04-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.02 |
| L229 | `cf_wc_other_financial_assets_noncurrent` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.01 |
| L230 | `cf_wc_other_financial_assets_noncurrent` | H1 2026-04-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.02 |
| L231 | `cf_wc_other_financial_liabilities_current` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.01 |
| L232 | `cf_wc_other_financial_liabilities_current` | H1 2026-04-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.02 |
| L233 | `cf_wc_other_financial_liabilities_noncurrent` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.01 |
| L234 | `cf_wc_other_financial_liabilities_noncurrent` | H1 2026-04-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.02 |
| L235 | `cf_wc_other_bank_balances` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.01 |
| L236 | `cf_wc_other_bank_balances` | H1 2026-04-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | T3.02 |
| L237 | `cf_adjustments_total` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L238 | `cf_adjustments_total` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `AdjustmentsForReconcileProfitLoss@FourD` | T3.02 |
| L239 | `cf_cash_generated_from_operations` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L240 | `cf_cash_generated_from_operations` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `CashFlowsFromUsedInOperations@FourD` | T3.02 |
| L241 | `cf_interest_paid_operating` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L242 | `cf_interest_paid_operating` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `InterestPaidClassifiedAsOperatingActivities@FourD` | T3.02 |
| L243 | `cf_interest_received_operating` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L244 | `cf_interest_received_operating` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `InterestReceivedClassifiedAsOperatingActivities@FourD` | T3.02 |
| L245 | `cf_dividends_received_operating` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L246 | `cf_dividends_received_operating` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `DividendsReceivedClassifiedAsOperatingActivities@FourD` | T3.02 |
| L247 | `cf_income_taxes_paid` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L248 | `cf_income_taxes_paid` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `IncomeTaxesPaidRefundClassifiedAsOperatingActivities@FourD` | T3.02 |
| L249 | `cf_income_taxes_paid_investing` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L250 | `cf_income_taxes_paid_investing` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `IncomeTaxesPaidRefundClassifiedAsInvestingActivities@FourD` | T3.02 |
| L251 | `cf_income_taxes_paid_financing` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L252 | `cf_income_taxes_paid_financing` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `IncomeTaxesPaidRefundClassifiedAsFinancingActivities@FourD` | T3.02 |
| L253 | `cf_other_operating` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L254 | `cf_other_operating` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `OtherInflowsOutflowsOfCashClassifiedAsOperatingActivities@FourD` | T3.02 |
| L255 | `cfo` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L256 | `cfo` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `CashFlowsFromUsedInOperatingActivities@FourD` | T3.02 |
| L257 | `cf_capex_ppe` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L258 | `cf_capex_ppe` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-SCOPE | T3.02, T3.79 |
| L259 | `cf_sale_ppe` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L260 | `cf_sale_ppe` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-SCOPE | T3.02, T3.80 |
| L261 | `cf_purchase_intangible_assets` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L262 | `cf_purchase_intangible_assets` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities@FourD` | T3.02 |
| L263 | `cf_sale_intangible_assets` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L264 | `cf_sale_intangible_assets` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `ProceedsFromSalesOfIntangibleAssetsClassifiedAsInvestingActivities@FourD` | T3.02 |
| L265 | `cf_purchase_intangibles_under_development` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L266 | `cf_purchase_intangibles_under_development` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.02 |
| L267 | `cf_sale_intangibles_under_development` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L268 | `cf_sale_intangibles_under_development` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.02 |
| L269 | `cf_purchase_goodwill` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L270 | `cf_purchase_goodwill` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.02 |
| L271 | `cf_sale_goodwill` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L272 | `cf_sale_goodwill` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.02 |
| L273 | `cf_purchase_investment_property` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L274 | `cf_purchase_investment_property` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.02 |
| L275 | `cf_sale_investment_property` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L276 | `cf_sale_investment_property` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.02 |
| L277 | `cf_purchase_biological_assets` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L278 | `cf_purchase_biological_assets` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.02 |
| L279 | `cf_sale_biological_assets` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L280 | `cf_sale_biological_assets` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.02 |
| L281 | `cf_purchase_other_long_term_assets` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L282 | `cf_purchase_other_long_term_assets` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.02 |
| L283 | `cf_sale_other_long_term_assets` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L284 | `cf_sale_other_long_term_assets` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.02 |
| L285 | `cf_purchase_equity_debt_instruments` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L286 | `cf_purchase_equity_debt_instruments` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `OtherCashPaymentsToAcquireEquityOrDebtInstrumentsOfOtherEntitiesClassifiedAsInvestingActivities@FourD` | T3.02 |
| L287 | `cf_sale_equity_debt_instruments` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L288 | `cf_sale_equity_debt_instruments` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `OtherCashReceiptsFromSalesOfEquityOrDebtInstrumentsOfOtherEntitiesClassifiedAsInvestingActivities@FourD` | T3.02 |
| L289 | `cf_purchase_jv_interests` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L290 | `cf_purchase_jv_interests` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `OtherCashPaymentsToAcquireInterestsInJointVenturesClassifiedAsInvestingActivities@FourD` | T3.02 |
| L291 | `cf_sale_jv_interests` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L292 | `cf_sale_jv_interests` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `OtherCashReceiptsFromSalesOfInterestsInJointVenturesClassifiedAsInvestingActivities@FourD` | T3.02 |
| L293 | `cf_investments_net` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L294 | `cf_investments_net` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-PDF | — |
| L295 | `cf_obtaining_control_subsidiaries` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L296 | `cf_obtaining_control_subsidiaries` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `CashFlowsUsedInObtainingControlOfSubsidiariesOrOtherBusinessesClassifiedAsInvestingActivities@FourD` | T3.02 |
| L297 | `cf_losing_control_subsidiaries` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L298 | `cf_losing_control_subsidiaries` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `CashFlowsFromLosingControlOfSubsidiariesOrOtherBusinessesClassifiedAsInvestingActivities@FourD` | T3.02 |
| L299 | `cf_loans_advances_made` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L300 | `cf_loans_advances_made` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `CashAdvancesAndLoansMadeToOtherPartiesClassifiedAsInvestingActivities@FourD` | T3.02 |
| L301 | `cf_loans_advances_repaid` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L302 | `cf_loans_advances_repaid` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `CashReceiptsFromRepaymentOfAdvancesAndLoansMadeToOtherPartiesClassifiedAsInvestingActivities@FourD` | T3.02 |
| L303 | `cf_derivative_payments_investing` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L304 | `cf_derivative_payments_investing` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `CashPaymentsForFutureContractsForwardContractsOptionContractsAndSwapContractsClassifiedAsInvestingActivities@FourD` | T3.02 |
| L305 | `cf_derivative_receipts_investing` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L306 | `cf_derivative_receipts_investing` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `CashReceiptsFromFutureContractsForwardContractsOptionContractsAndSwapContractsClassifiedAsInvestingActivities@FourD` | T3.02 |
| L307 | `cf_interest_received_investing` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L308 | `cf_interest_received_investing` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `InterestReceivedClassifiedAsInvestingActivities@FourD` | T3.02 |
| L309 | `cf_dividends_received_investing` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L310 | `cf_dividends_received_investing` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `DividendsReceivedClassifiedAsInvestingActivities@FourD` | T3.02 |
| L311 | `cf_partnership_investment` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L312 | `cf_partnership_investment` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `CashPaymentForInvestmentInPartnershipFirmOrAssociationOfPersonsOrLimitedLiabilityPartnerships@FourD` | T3.02 |
| L313 | `cf_partnership_profit_share` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L314 | `cf_partnership_profit_share` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `CashReceiptsFromShareOfProfitsOfPartnershipFirmOrAssociationOfPersonsOrLimitedLiabilityPartnerships@FourD` | T3.02 |
| L315 | `cf_government_grants` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L316 | `cf_government_grants` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `ProceedsFromGovernmentGrantsClassifiedAsInvestingActivities@FourD` | T3.02 |
| L317 | `cf_other_investing` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L318 | `cf_other_investing` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `OtherInflowsOutflowsOfCashClassifiedAsInvestingActivities@FourD` | T3.02 |
| L319 | `cfi` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L320 | `cfi` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `CashFlowsFromUsedInInvestingActivities@FourD` | T3.02 |
| L321 | `cf_proceeds_shares` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L322 | `cf_proceeds_shares` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `ProceedsFromIssuingShares@FourD` | T3.02, T3.76–T3.78, B8.24 |
| L323 | `cf_proceeds_other_equity_instruments` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L324 | `cf_proceeds_other_equity_instruments` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `ProceedsFromIssuingOtherEquityInstruments@FourD` | T3.02 |
| L325 | `cf_proceeds_stock_options` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L326 | `cf_proceeds_stock_options` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-SCOPE | T3.02, T3.77 |
| L327 | `cf_payments_redeem_own_shares` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L328 | `cf_payments_redeem_own_shares` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.02 |
| L329 | `cf_payments_other_equity_instruments` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L330 | `cf_payments_other_equity_instruments` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.02 |
| L331 | `cf_proceeds_ownership_changes_subsidiaries` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L332 | `cf_proceeds_ownership_changes_subsidiaries` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.02 |
| L333 | `cf_payments_ownership_changes_subsidiaries` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L334 | `cf_payments_ownership_changes_subsidiaries` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.02 |
| L335 | `cf_proceeds_borrowings` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L336 | `cf_proceeds_borrowings` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `ProceedsFromBorrowingsClassifiedAsFinancingActivities@FourD` | T3.02 |
| L337 | `cf_short_term_borrowings_net` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L338 | `cf_short_term_borrowings_net` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-PDF | — |
| L339 | `cf_proceeds_debentures` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L340 | `cf_proceeds_debentures` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `ProceedsFromIssuingDebenturesNotesBondsEtc@FourD` | T3.02 |
| L341 | `cf_repayment_borrowings` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L342 | `cf_repayment_borrowings` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `RepaymentsOfBorrowingsClassifiedAsFinancingActivities@FourD` | T3.02 |
| L343 | `cf_lease_payments` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L344 | `cf_lease_payments` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.02 |
| L345 | `cf_dividends_paid` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L346 | `cf_dividends_paid` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `DividendsPaidClassifiedAsFinancingActivities@FourD` | T3.02 |
| L347 | `cf_interest_paid_financing` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L348 | `cf_interest_paid_financing` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `InterestPaidClassifiedAsFinancingActivities@FourD` | T3.02 |
| L349 | `cf_other_financing` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L350 | `cf_other_financing` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `OtherInflowsOutflowsOfCashClassifiedAsFinancingActivities@FourD` | T3.02 |
| L351 | `cff` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L352 | `cff` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `CashFlowsFromUsedInFinancingActivities@FourD` | T3.02 |
| L353 | `cf_net_change_before_fx` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L354 | `cf_net_change_before_fx` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `IncreaseDecreaseInCashAndCashEquivalentsBeforeEffectOfExchangeRateChanges@FourD` | T3.02 |
| L355 | `cf_fx_effect` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L356 | `cf_fx_effect` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `EffectOfExchangeRateChangesOnCashAndCashEquivalents@FourD` | T3.02 |
| L357 | `cf_net_change` | Q 2026-07-01..2026-09-30 | UNSUPPORTED: no quarter cash-flow statement | REFUSED R-QCF | T3.01 |
| L358 | `cf_net_change` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `IncreaseDecreaseInCashAndCashEquivalents@FourD` | T3.02 |
| L359 | `cf_cash_opening` | I 2026-09-30 | SUPPORTED | REFUSED R-TIME | T3.04, B8.26 |
| L360 | `cf_cash_closing` | I 2026-09-30 | SUPPORTED | VALUE `CashAndCashEquivalentsCashFlowStatement@OneI` | T3.03 |
| L361 | `segment_revenue` [segment=retail, elimination_basis=PRE_ELIMINATION] | Q 2026-07-01..2026-09-30 | SUPPORTED | VALUE `SegmentRevenue@OneReportable11D` | T3.29, T3.05, T3.63, T3.65, T3.67 |
| L362 | `segment_revenue` [segment=wholesale, elimination_basis=PRE_ELIMINATION] | Q 2026-07-01..2026-09-30 | SUPPORTED | VALUE `SegmentRevenue@OneReportable12D` | T3.30, T3.06, T3.63, T3.65, T3.67 |
| L363 | `segment_revenue` [segment=treasury, elimination_basis=PRE_ELIMINATION] | Q 2026-07-01..2026-09-30 | SUPPORTED | VALUE `SegmentRevenue@OneReportable13D` | T3.31, T3.07, T3.63, T3.65, T3.67 |
| L364 | `segment_revenue` [segment=other_banking, elimination_basis=PRE_ELIMINATION] | Q 2026-07-01..2026-09-30 | SUPPORTED | VALUE `SegmentRevenue@OneReportable14D` | T3.32, T3.08, T3.63, T3.65, T3.67 |
| L365 | `segment_revenue` [segment=retail, elimination_basis=PRE_ELIMINATION] | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `SegmentRevenue@FourReportable11D` | T3.25, T3.05, T3.64, T3.66, T3.67 |
| L366 | `segment_revenue` [segment=wholesale, elimination_basis=PRE_ELIMINATION] | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `SegmentRevenue@FourReportable12D` | T3.26, T3.06, T3.64, T3.66, T3.67 |
| L367 | `segment_revenue` [segment=treasury, elimination_basis=PRE_ELIMINATION] | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `SegmentRevenue@FourReportable13D` | T3.27, T3.07, T3.64, T3.66, T3.67 |
| L368 | `segment_revenue` [segment=other_banking, elimination_basis=PRE_ELIMINATION] | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `SegmentRevenue@FourReportable14D` | T3.28, T3.08, T3.64, T3.66, T3.67 |
| L369 | `segment_revenue_total` | Q 2026-07-01..2026-09-30 | SUPPORTED | VALUE `SegmentRevenue@OneD` | T3.01 |
| L370 | `segment_revenue_total` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `SegmentRevenue@FourD` | T3.02 |
| L371 | `inter_segment_revenue` | Q 2026-07-01..2026-09-30 | SUPPORTED | VALUE `InterSegmentRevenue@OneD` | T3.01 |
| L372 | `inter_segment_revenue` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `InterSegmentRevenue@FourD` | T3.02 |
| L373 | `segment_revenue_from_operations` | Q 2026-07-01..2026-09-30 | SUPPORTED | VALUE `SegmentRevenueFromOperations@OneD` | T3.01 |
| L374 | `segment_revenue_from_operations` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `SegmentRevenueFromOperations@FourD` | T3.02 |
| L375 | `segment_result` [segment=retail] | Q 2026-07-01..2026-09-30 | — | no key: R-MEAN, no member interpreted | T3.37, T3.05, T3.57, T3.58, T3.59 |
| L376 | `segment_result` [segment=wholesale] | Q 2026-07-01..2026-09-30 | — | no key: R-MEAN, no member interpreted | T3.38, T3.06, T3.57, T3.58, T3.59 |
| L377 | `segment_result` [segment=treasury] | Q 2026-07-01..2026-09-30 | — | no key: R-MEAN, no member interpreted | T3.39, T3.07, T3.57, T3.58, T3.59 |
| L378 | `segment_result` [segment=other_banking] | Q 2026-07-01..2026-09-30 | — | no key: R-MEAN, no member interpreted | T3.40, T3.08, T3.57, T3.58, T3.59 |
| L379 | `segment_result` [segment=retail] | H1 2026-04-01..2026-09-30 | — | no key: R-MEAN, no member interpreted | T3.33, T3.05, T3.57, T3.58, T3.60 |
| L380 | `segment_result` [segment=wholesale] | H1 2026-04-01..2026-09-30 | — | no key: R-MEAN, no member interpreted | T3.34, T3.06, T3.57, T3.58, T3.60 |
| L381 | `segment_result` [segment=treasury] | H1 2026-04-01..2026-09-30 | — | no key: R-MEAN, no member interpreted | T3.35, T3.07, T3.57, T3.58, T3.60 |
| L382 | `segment_result` [segment=other_banking] | H1 2026-04-01..2026-09-30 | — | no key: R-MEAN, no member interpreted | T3.36, T3.08, T3.57, T3.58, T3.60 |
| L383 | `segment_result_total` | Q 2026-07-01..2026-09-30 | SUPPORTED | REFUSED R-MEAN | T3.01, T3.57, T3.58, T3.59, T3.61 |
| L384 | `segment_result_total` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-MEAN | T3.02, T3.57, T3.58, T3.60, T3.62 |
| L385 | `segment_finance_costs` | Q 2026-07-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.01 |
| L386 | `segment_finance_costs` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.02 |
| L387 | `segment_unallocable_net` | Q 2026-07-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.01 |
| L388 | `segment_unallocable_net` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-NF | T3.02 |
| L389 | `segment_other_elimination` | Q 2026-07-01..2026-09-30 | SUPPORTED | REFUSED R-PDF | — |
| L390 | `segment_other_elimination` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-PDF | — |
| L391 | `segment_profit_before_tax` | Q 2026-07-01..2026-09-30 | SUPPORTED | VALUE `SegmentProfitBeforeTax@OneD` | T3.01 |
| L392 | `segment_profit_before_tax` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `SegmentProfitBeforeTax@FourD` | T3.02 |
| L393 | `segment_assets` [segment=retail, elimination_basis=POST_ELIMINATION] | I 2026-09-30 | SUPPORTED | VALUE `SegmentAssets@OneReportable31I` | T3.41, T3.05, T3.68–T3.70 |
| L394 | `segment_assets` [segment=wholesale, elimination_basis=POST_ELIMINATION] | I 2026-09-30 | SUPPORTED | VALUE `SegmentAssets@OneReportable32I` | T3.42, T3.06, T3.68–T3.70 |
| L395 | `segment_assets` [segment=treasury, elimination_basis=POST_ELIMINATION] | I 2026-09-30 | SUPPORTED | VALUE `SegmentAssets@OneReportable33I` | T3.43, T3.07, T3.68–T3.70 |
| L396 | `segment_assets` [segment=other_banking, elimination_basis=POST_ELIMINATION] | I 2026-09-30 | SUPPORTED | VALUE `SegmentAssets@OneReportable34I` | T3.44, T3.08, T3.68–T3.70 |
| L397 | `segment_assets_total` | I 2026-09-30 | SUPPORTED | VALUE `SegmentAssets@OneI` | T3.03 |
| L398 | `segment_unallocable_assets` | I 2026-09-30 | SUPPORTED | VALUE `UnAllocableAssets@OneI` | T3.03 |
| L399 | `segment_assets_net` | I 2026-09-30 | SUPPORTED | VALUE `NetSegmentAssets@OneI` | T3.03 |
| L400 | `inter_segment_assets` | I 2026-09-30 | SUPPORTED | REFUSED R-PDF | — |
| L401 | `segment_liabilities` [segment=retail] | I 2026-09-30 | — | no key: R-MEAN, no member interpreted | T3.45, T3.05, T3.71–T3.75 |
| L402 | `segment_liabilities` [segment=wholesale] | I 2026-09-30 | — | no key: R-MEAN, no member interpreted | T3.46, T3.06, T3.71–T3.75 |
| L403 | `segment_liabilities` [segment=treasury] | I 2026-09-30 | — | no key: R-MEAN, no member interpreted | T3.47, T3.07, T3.71–T3.75 |
| L404 | `segment_liabilities` [segment=other_banking] | I 2026-09-30 | — | no key: R-MEAN, no member interpreted | T3.48, T3.08, T3.71–T3.75 |
| L405 | `segment_liabilities_total` | I 2026-09-30 | SUPPORTED | REFUSED R-MEAN | T3.03, T3.72–T3.75 |
| L406 | `segment_unallocable_liabilities` | I 2026-09-30 | SUPPORTED | VALUE `UnAllocableLiabilities@OneI` | T3.03 |
| L407 | `segment_liabilities_net` | I 2026-09-30 | SUPPORTED | REFUSED R-MEAN | T3.03, T3.72–T3.75 |
| L408 | `inter_segment_liabilities` | I 2026-09-30 | SUPPORTED | REFUSED R-PDF | — |
| L409 | `interest_earned` (new, BANK) | Q 2026-07-01..2026-09-30 | SUPPORTED | VALUE `InterestEarned@OneD` | T3.01 |
| L410 | `interest_earned` (new, BANK) | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `InterestEarned@FourD` | T3.02 |
| L411 | `interest_expended` (new, BANK) | Q 2026-07-01..2026-09-30 | SUPPORTED | VALUE `InterestExpended@OneD` | T3.01 |
| L412 | `interest_expended` (new, BANK) | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `InterestExpended@FourD` | T3.02 |
| L413 | `provisions_and_contingencies` (new, BANK) | Q 2026-07-01..2026-09-30 | SUPPORTED | VALUE `ProvisionsOtherThanTaxAndContingencies@OneD` | T3.01 |
| L414 | `provisions_and_contingencies` (new, BANK) | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE `ProvisionsOtherThanTaxAndContingencies@FourD` | T3.02 |
| L415 | `deposits` (new, BANK) | I 2026-09-30 | SUPPORTED | VALUE `Deposits@OneI` | T3.03 |
| L416 | `advances` (new, BANK) | I 2026-09-30 | SUPPORTED | VALUE `Advances@OneI` | T3.03 |
| L417 | `bank_investments` (new, BANK) | I 2026-09-30 | SUPPORTED | VALUE `Investments@OneI` | T3.03 |
| L418 | `opex_excl_finance_and_da` | Q 2026-07-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | — |
| L419 | `opex_excl_finance_and_da` | H1 2026-04-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | — |
| L420 | `ebitda_excl_other_income` | Q 2026-07-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | — |
| L421 | `ebitda_excl_other_income` | H1 2026-04-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | — |
| L422 | `opm_pct` | Q 2026-07-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | — |
| L423 | `opm_pct` | H1 2026-04-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | — |
| L424 | `pbdt_vendor` | Q 2026-07-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | — |
| L425 | `pbdt_vendor` | H1 2026-04-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | — |
| L426 | `pbt_margin_pct` | Q 2026-07-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | — |
| L427 | `pbt_margin_pct` | H1 2026-04-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | — |
| L428 | `effective_tax_rate_pct` | Q 2026-07-01..2026-09-30 | SUPPORTED | VALUE computed | — |
| L429 | `effective_tax_rate_pct` | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE computed | — |
| L430 | `material_cost_pct` | Q 2026-07-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | — |
| L431 | `material_cost_pct` | H1 2026-04-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | — |
| L432 | `employee_cost_pct` | Q 2026-07-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | — |
| L433 | `employee_cost_pct` | H1 2026-04-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | — |
| L434 | `cfo_to_op_pct` | Q 2026-07-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | — |
| L435 | `cfo_to_op_pct` | H1 2026-04-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | — |
| L436 | `receivable_days` | Q 2026-07-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | — |
| L437 | `receivable_days` | H1 2026-04-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | — |
| L438 | `liabilities_incl_nci` | I 2026-09-30 | SUPPORTED | REFUSED R-OP (total_liabilities) | — |
| L439 | `net_current_assets` | I 2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | — |
| L440 | `shares_outstanding` | I 2026-09-30 | SUPPORTED | VALUE computed | — |
| L441 | `cf_wc_total` | Q 2026-07-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | — |
| L442 | `cf_wc_total` | H1 2026-04-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | — |
| L443 | `segment_capital_employed` [segment=retail, elimination_basis=POST_ELIMINATION] | I 2026-09-30 | SUPPORTED | REFUSED R-OP (segment_liabilities) | T3.41, T3.45, T3.68–T3.75 |
| L444 | `segment_capital_employed` [segment=wholesale, elimination_basis=POST_ELIMINATION] | I 2026-09-30 | SUPPORTED | REFUSED R-OP (segment_liabilities) | T3.42, T3.46, T3.68–T3.75 |
| L445 | `segment_capital_employed` [segment=treasury, elimination_basis=POST_ELIMINATION] | I 2026-09-30 | SUPPORTED | REFUSED R-OP (segment_liabilities) | T3.43, T3.47, T3.68–T3.75 |
| L446 | `segment_capital_employed` [segment=other_banking, elimination_basis=POST_ELIMINATION] | I 2026-09-30 | SUPPORTED | REFUSED R-OP (segment_liabilities) | T3.44, T3.48, T3.68–T3.75 |
| L447 | `segment_revenue_members_total` [segment=reportable_segments_total, elimination_basis=PRE_ELIMINATION] | Q 2026-07-01..2026-09-30 | SUPPORTED | VALUE computed | T3.25–T3.32, T3.63–T3.67 |
| L448 | `segment_revenue_members_total` [segment=reportable_segments_total, elimination_basis=PRE_ELIMINATION] | H1 2026-04-01..2026-09-30 | SUPPORTED | VALUE computed | T3.25–T3.32, T3.63–T3.67 |
| L449 | `net_profit_margin_pct` | Q 2026-07-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | — |
| L450 | `net_profit_margin_pct` | H1 2026-04-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | — |
| L451 | `gross_margin_pct` | Q 2026-07-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | — |
| L452 | `gross_margin_pct` | H1 2026-04-01..2026-09-30 | SUPPORTED | NOT_APPLICABLE `ISSUER_RULE_ID` | — |
| L453 | `other_income_incl_exceptional` | Q 2026-07-01..2026-09-30 | SUPPORTED | REFUSED R-OP (exceptional_items_before_tax) | — |
| L454 | `other_income_incl_exceptional` | H1 2026-04-01..2026-09-30 | SUPPORTED | REFUSED R-OP (exceptional_items_before_tax) | — |
| L455 | `shp_public_shareholding_plus_employee_trust_pct` | — | — | no key: no shareholding member in a results package | — |
| L456 | `shp_non_institutions_plus_employee_trust_pct` | — | — | no key: no shareholding member in a results package | — |
| L457 | `shp_institutions_domestic_plus_foreign_pct` | — | — | no key: no shareholding member in a results package | — |

## Evidence pins

VENDOR-1 Phase 3 Task 3 (F16). Task 11 checks that discovery's selected filings equal these
before its rehearsal; any difference stops Task 11 for re-grounding and a Task 3 amendment.

- **Issuer.** ICICIBANK, ISIN `INE090A01021` [B4.25], BSE scrip `532174` [B4.09].
- **Period ends.** 2026-09-30, the acceptance period (Task 13 `<PE>`; a half-year package,
  quarter Q2 of the year ending 2027-03-31 [B10.08]); 2026-06-30, onboarding's second filing.
- **Analysis basis.** `STANDALONE`, owner decision 2 (spec §2). Basis status
  `CONSOLIDATED_AND_STANDALONE` (B5a) [B5.01–B5.04].
- **Framework.** The PDFs declare `INDIAN_GAAP` content (B1b) [B1.05, B1.09]. The PDFs are not
  associated with the issuer, period and basis under revised A7, so B1c stands and no framework is
  pinned. These pins are not used while the phase halts at Task 3.

| Period end | Basis | Instance sha256 | Role |
|---|---|---|---|
| 2026-09-30 | Standalone | `a2d498641dc7516679efeb4fae21bbc0c97a3220ead3fa229d669997fbcb64d3` | acceptance package member; onboarding filing |
| 2026-06-30 | Standalone | `39677b484f433a34be77c8a1bd241a0d9b66bf17cfd4eedc54ce0dfbaefc62d5` | onboarding filing |
| 2026-09-30 | Consolidated | `615348fca1872145ef64f390d725bc196359c61dec88ddf49f8ab8deb920dc5d` | listing evidence for basis status only; never a member |
| 2026-06-30 | Consolidated | `ded5800004dd276f7b81110c4be9ed449eb2c7281ee3bb3e67519cf6448a4cb4` | listing evidence for basis status only; never a member |

| Period end | Results PDF sha256 | Filed | Role |
|---|---|---|---|
| 2026-09-30 | `b28a719174d31592413f317e9baf527e4dd127f18b2468179d9cc0bfa74fabd1` | 2026-10-17 15:21:44+05:30 | candidate framework evidence (B1′ P); A7 not met; not a package member (B7b) |
| 2026-06-30 | `1b3599e2a01fc9b77f913fef7a3068bca6ec43c722010a1c1bc4c01c55033c03` | 2026-07-18 14:23:53+05:30 | candidate framework evidence (B1′ P); A7 not met; not a package member (B7b) |

The grounding captures are retention-only (`nse-grounding`): onboarding acquires its own copies
under first-party sources, and the pins are byte identities those copies must match.
