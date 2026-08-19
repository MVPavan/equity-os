# Phase 0A discovery: Indian listed company shortlist

**Status:** Non-authoritative A-02 discovery evidence; nonbinding shortlist
**Retrieval date:** 2026-08-19
**Slice:** One discovery-company slice; product-owner selection is not made here.

## Scope and method

This pass screened Indian listed, non-financial issuers with a complete four-quarter FY25 window (Q1 ended June 30, 2024 through Q4 ended March 31, 2025). I checked issuer-hosted result/IR packages and official issuer management commentary, then checked the official NSE/BSE structured-filing entry points. No vendor, broker, data-reseller, or secondary-media evidence was used.

Source hierarchy used:

1. Issuer financial-results PDF or IR presentation, then issuer result page.
2. Issuer-hosted management transcript/press release for commitments and guidance.
3. NSE/BSE filing/search pages and SEBI/NSE filing-format notices for structured-channel evidence.

Labels in this note: **FACT** = directly stated in an official source; **INFERENCE** = reasoned workflow assessment; **DATA GAP** = not established by this pass.

**Workflow assumption (INFERENCE):** for the selected FY25 window, program Quarter 0 maps to issuer Q1 FY25 and is the manual baseline/bootstrap thesis; program Quarter 1 maps to issuer Q2 FY25, program Quarter 2 to issuer Q3 FY25, and program Quarter 3 to issuer Q4 FY25. Each of program Quarters 1–3 is a full assisted quarterly update. The exact internal phase definitions and analyst rubric still require confirmation.

## Candidate comparison

| Rank | Candidate | Four-quarter evidence | Program Q0-Q3 suitability | Principal complexity / gap |
|---|---|---|---|---|
| 1 | Infosys Ltd (INFY) | **FACT:** issuer has a dedicated FY25 quarterly-results series and direct result PDFs for all four quarters. | **INFERENCE:** High suitability. Program Quarter 0 is straightforward for the issuer Q1 FY25 manual baseline/bootstrap thesis; each full assisted update in program Quarters 1–3 is well supported by the issuer Q2–Q4 FY25 packages, including explicit guidance revisions and actuals. | Medium: IFRS plus Ind AS, segment disclosures, and guidance mainly in transcripts. XBRL per-quarter direct link not established. |
| 2 | Larsen & Toubro Ltd (LT) | **FACT:** issuer-hosted Q1-Q4 FY25 earnings-call/IR presentations are available as direct PDFs. | **INFERENCE:** Good fallback. Program Quarter 0 must separate group, projects/manufacturing, IT/services, and financial-services data; each full assisted update in program Quarters 1–3 is supported by repeated order-inflow, order-book, revenue, margin, NWC, and ROE fields. | Medium-high: conglomerate, many segments, non-GAAP/operating KPIs, and IR presentation is not a substitute for final statutory-result verification. |
| 3 | Tata Motors Ltd (TATAMOTORS) | **FACT:** issuer-hosted Q1-Q4 FY25 group investor presentations are direct PDFs; issuer also has quarter press-release pages. | **INFERENCE:** Useful but hardest. Program Quarter 0 must lock scope across TML, JLR, CV, PV, currencies, and Ind AS/IFRS; each full assisted update in program Quarters 1–3 remains materially complex because of the multiple reporting bases, segment definitions, bespoke KPIs, and dynamic package links. | High: multiple reporting bases, segment definitions, bespoke KPIs, and dynamic package links. XBRL mapping for Auto FCF, PBT (bei), order/volume measures is a DATA GAP. |

## Official structured/XBRL channels

**FACT:** NSE's [Financial Results search page](https://www.nseindia.com/companies-listing/corporate-filings-financial-results) exposes company/period filters, CSV download, an XBRL column in the result table, and “Convert XBRL into Excel.” NSE's [Integrated Filing–Financial page](https://www.nseindia.com/companies-listing/corporate-integrated-filing?integratedType=integratedfilingfinancials&symbol=null) exposes quarter-ending filters, CSV download, and XBRL-to-Excel conversion. NSE's [April 2, 2025 circular](https://nsearchives.nseindia.com/web/sites/default/files/inline-files/NSE_Circular_02042025_0.pdf) states that listed entities submit Integrated Filing–Financial in XBRL and separately submit the board-meeting financial-results PDF.

**FACT:** BSE's official company financial-results endpoint exposes filing date/time plus standalone and consolidated XBRL columns. Candidate search pages: [Infosys, code 500209](https://www.bseindia.com/corporates/Comp_Results.aspx?Code=500209), [Tata Motors, code 500570](https://www.bseindia.com/corporates/Comp_Results.aspx?Code=500570), and [L&T, code 500510](https://www.bseindia.com/corporates/Comp_Results.aspx?Code=500510).

**Direct-link gap (DATA GAP):** this pass did not establish a stable, per-company, per-quarter public XBRL file URL for any candidate. The NSE/BSE search pages above are the exact official discovery pages to use; the presence of a search page or XBRL column does not establish a stable downloadable file, API, historical retention, or automated retrieval path.

## Candidate 1 — Infosys Ltd

### Quarter/source matrix

| Quarter | Official issuer package | Document date / period |
|---|---|---|
| Q1 FY25 | [Financial results and auditors' reports PDF](https://www.infosys.com/investors/reports-filings/quarterly-results/2024-2025/q1/documents/q1-fy25-financial-results-auditorsreports.pdf) | July 18, 2024 / quarter ended June 30, 2024 |
| Q2 FY25 | [Financial results and auditors' reports PDF](https://www.infosys.com/investors/reports-filings/quarterly-results/2024-2025/q2/documents/q2-and-h1-fy25-financial-results-auditorsreports.pdf) | October 17, 2024 / quarter and half-year ended September 30, 2024 |
| Q3 FY25 | [Financial results and auditors' reports PDF](https://www.infosys.com/investors/reports-filings/quarterly-results/2024-2025/q3/documents/q3-and-9m-fy25-financial-results-auditorsreports.pdf) | January 16, 2025 / quarter and nine months ended December 31, 2024 |
| Q4 FY25 | [Financial results and auditors' reports PDF](https://www.infosys.com/investors/reports-filings/quarterly-results/2024-2025/q4/documents/q4-and-12m-fy25-financial-results-auditorsreports.pdf) | April 17, 2025 / quarter and year ended March 31, 2025 |

Structured channel: NSE [Financial Results](https://www.nseindia.com/companies-listing/corporate-filings-financial-results) and [Integrated Filing–Financial](https://www.nseindia.com/companies-listing/corporate-integrated-filing?integratedType=integratedfilingfinancials&symbol=INFY); BSE [code 500209 results search](https://www.bseindia.com/corporates/Comp_Results.aspx?Code=500209). **DATA GAP:** direct XBRL file link not captured.

### Commitment evidence and suitability

- **FACT:** management's Q1 transcript set FY25 constant-currency revenue-growth guidance at 3%–4% and operating-margin guidance at 20%–22% ([official Q1 transcript](https://www.infosys.com/investors/reports-filings/quarterly-results/2024-2025/q1/documents/transcripts/press-conference.pdf)).
- **FACT:** Q2 revised revenue guidance to 3.75%–4.5% while retaining 20%–22% operating margin ([official Q2 transcript](https://www.infosys.com/investors/reports-filings/quarterly-results/2024-2025/q2/documents/transcripts/press-conference.pdf)). Q3 revised it again to 4.5%–5%, with margin guidance unchanged ([official Q3 earnings-call transcript](https://www.infosys.com/investors/reports-filings/quarterly-results/2024-2025/q3/documents/transcripts/earningscall.pdf)).
- **FACT:** Q4 reported FY25 constant-currency growth of 4.2% and set FY26 guidance at 0%–3% revenue growth and 20%–22% operating margin ([official Q4 IFRS press release](https://www.infosys.com/investors/reports-filings/quarterly-results/2024-2025/q4/documents/ifrs-usd-press-release.pdf)). This creates a clear commitment-revision-and-outcome chain for Q3 tracking.
- **INFERENCE:** strongest discovery candidate for a manual baseline: consistent source naming, explicit document dates, statutory result PDFs, management transcripts, and a guidance-vs-actual trail.
- **DATA GAP:** structured data availability for the exact INFY FY25 quarters, field coverage for guidance, and exchange-file retention were not proven.

## Candidate 3 — Tata Motors Ltd

### Quarter/source matrix

| Quarter | Official issuer package | Document date / period |
|---|---|---|
| Q1 FY25 | [Group investor presentation](https://www.tatamotors.com/wp-content/uploads/2024/08/Tata-Motors-Investor-presentation-Q1FY25.pdf) | August 1, 2024 / quarter ended June 30, 2024 |
| Q2 FY25 | [Group investor presentation](https://www.tatamotors.com/wp-content/uploads/2024/11/Tata-Motors-Investor-presentation-Q2-FY25-1.pdf) | November 8, 2024 / quarter ended September 30, 2024 |
| Q3 FY25 | [Group investor presentation](https://www.tatamotors.com/wp-content/uploads/2025/01/Tata-Motors-Investor-presentation-Q3FY25.pdf) | January 29, 2025 / quarter ended December 31, 2024 |
| Q4 FY25 | [Group investor presentation](https://www.tatamotors.com/wp-content/uploads/2025/05/Q4-FY25-Investor-presentation.pdf) | May 13, 2025 / quarter and year ended March 31, 2025 |

Issuer result index: [quarterly-results archive](https://www.tatamotors.com/quarterly-results/). Official quarter result pages include Q2 [November 8](https://www.tatamotors.com/press-releases/tata-motors-consolidated-q2-fy25-results/), Q3 [January 29](https://www.tatamotors.com/press-releases/tata-motors-consolidated-q3-fy25-results/), and Q4 [May 13](https://www.tatamotors.com/press-releases/tata-motors-consolidated-q4-fy25-results/). Structured channel: NSE [Financial Results](https://www.nseindia.com/companies-listing/corporate-filings-financial-results) / [Integrated Filing–Financial](https://www.nseindia.com/companies-listing/corporate-integrated-filing?integratedType=integratedfilingfinancials&symbol=TATAMOTORS); BSE [code 500570 results search](https://www.bseindia.com/corporates/Comp_Results.aspx?Code=500570). **DATA GAP:** direct XBRL file link not captured.

### Commitment evidence and suitability

- **FACT:** Q1 JLR commentary held full-year deliverables of EBIT above 8.5% and achieving net cash ([official Q1 results PDF](https://www.tatamotors.com/wp-content/uploads/2024/08/q1fy25-results-press-release.pdf)).
- **FACT:** Q2 kept full-year guidance at approximately £30bn revenue, EBIT at least 8.5%, and positive net cash ([official Q2 result page](https://www.tatamotors.com/press-releases/tata-motors-consolidated-q2-fy25-results/)); Q3 said JLR was on track for those profitability and cash-flow targets ([official Q3 result page](https://www.tatamotors.com/press-releases/tata-motors-consolidated-q3-fy25-results/)).
- **FACT:** Q4 reported that the TML group turned net-auto-cash positive in FY25 with ₹1.0K Cr net cash ([official Q4 result page](https://www.tatamotors.com/press-releases/tata-motors-consolidated-q4-fy25-results/)). The Q4 presentation also states “deleveraging commitment fulfilled.”
- **INFERENCE:** useful as a complex reconciliation case: management target, JLR operational metrics, TML consolidated Ind AS, and cash/debt measures can be tracked, but they require explicit scope and currency controls.
- **DATA GAP:** exact exchange XBRL coverage for JLR/TML segment measures, stable links to every statutory standalone/consolidated PDF, and whether bespoke KPIs map cleanly to structured facts.

## Candidate 2 — Larsen & Toubro Ltd

### Quarter/source matrix

| Quarter | Official issuer package | Document date / period |
|---|---|---|
| Q1 FY25 | [Earnings-call presentation](https://investors.larsentoubro.com/upload/AnalystPres/FY2025AnalystPresL%26T%20Q1FY25%20Analyst%20Presentation%20.pdf) | July 24, 2024 / quarter ended June 30, 2024 |
| Q2 FY25 | [Earnings-call presentation](https://investors.larsentoubro.com/upload/AnalystPres/FY2025AnalystPresL%26T%20Q2FY25%20Analyst%20Presentation.pdf) | October 30, 2024 / quarter and half-year ended September 30, 2024 |
| Q3 FY25 | [Earnings-call presentation](https://investors.larsentoubro.com/upload/AnalystPres/FY2025AnalystPresL%26T%20Q3FY25%20Analyst%20Presentation%20.pdf) | January 30, 2025 / quarter and nine months ended December 31, 2024 |
| Q4 FY25 | [Earnings-call presentation](https://investors.larsentoubro.com/upload/AnalystPres/FY2025AnalystPresL%26T%20Q4FY25%20Analyst%20Presentation.pdf) | May 8, 2025 / quarter and year ended March 31, 2025 |

Issuer archive: [L&T analyst-presentation archive](https://investors.larsentoubro.com/Analyst-Presentation-Archives.aspx) and [events calendar](https://investors.larsentoubro.com/Events.aspx). Structured channel: NSE [Financial Results](https://www.nseindia.com/companies-listing/corporate-filings-financial-results) / [Integrated Filing–Financial](https://www.nseindia.com/companies-listing/corporate-integrated-filing?integratedType=integratedfilingfinancials&symbol=LT); BSE [code 500510 results search](https://www.bseindia.com/corporates/Comp_Results.aspx?Code=500510). **DATA GAP:** direct XBRL file link not captured.

### Commitment evidence and suitability

- **FACT:** Q1-Q4 presentations repeat order inflow, order book, revenue, EBITDA/margin, NWC, ROE, and segment measures; see the four official PDFs above.
- **FACT:** Q4 reports the FY21–FY26 strategic-plan target/current-status table: order inflow target ₹3.4 trillion, revenue target ₹2.7 trillion, and ROE target 18%, alongside FY25 status ([official Q4 presentation](https://investors.larsentoubro.com/upload/AnalystPres/FY2025AnalystPresL%26T%20Q4FY25%20Analyst%20Presentation.pdf)).
- **INFERENCE:** this is a good fallback for tracking a multi-period operating target against repeated quarterly KPIs; Q0 must define whether L&T Finance and other subsidiaries are in or out of the discovery slice.
- **DATA GAP:** the presentations are IR evidence, not final proof that every statutory result/XBRL fact has identical definitions; exact quarter-level XBRL files and a complete stable statutory-PDF inventory remain unverified.

## Ranking, boundaries, and required decisions

**Nonbinding research-suitability recommendation:**

1. **Preferred: Infosys** — cleanest repeatable manual discovery path and clearest guidance trail.
2. **Fallback: Larsen & Toubro** — strongest operating-KPI/target challenge with manageable source continuity.
3. **Tata Motors** — valuable high-complexity stress case, but least suitable as the first slice.

This ranking is research-suitability only. It is not a valuation, price, expected-return, buy/sell, provider, or investment recommendation.

For every candidate, public access is observed but **source rights are unknown**: public access does not establish permission for automation, caching, retention, derived outputs, or redistribution. Rights, terms, exchange access constraints, and any issuer-specific restrictions require a separate review; no rights conclusion is made here.

**Required before any downstream selection:** product-owner selection and an analyst suitability attestation remain required. This artifact does not authorize product code, provider selection, or Phase 0.5 start.
