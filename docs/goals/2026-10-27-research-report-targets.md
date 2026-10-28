# Research report targets (owner direction, 2026-10-27)

The owner supplied three Tijori Stack sample reports (`docs/goals/sample-reports/`, kept out of git:
vendor output). Equity-OS theses must carry **this kind of information**. It is **one requirement among others**:
the three kinds below are neither complete nor exhaustive. They are a floor the research output
must cover, not the whole product vision (`docs/goals/equity-os-product-completion-gold.md`) and
not a template to copy. Concalls are a required input.

## The three kinds of analysis

| Kind | Sample | What it contains |
|---|---|---|
| Forward view (5-year estimates) | Kalyani Cast-Tech | Thesis, key driver, critical dependency and watch items. Competitive position. Bear, base and bull scenarios with probabilities and triggers. A revenue/EBITDA/PAT table across scenarios. Growth split by driver (capacity × utilisation × price). Margin path. Funding gap. Unit economics. Working capital. A credibility adjustment to management's timeline. A dated analyst watchlist. |
| Risk probe (forensic) | Kaynes Technology | A scorecard of named checks (passed, flagged, not applicable), each rated by category (accounting, governance, business, liquidity, solvency) with evidence. Examples: receivable and payable days, OCF against profit, capitalised intangibles, off-balance-sheet exposure, disclosure lapses, credit-rating remarks, capex intensity. |
| Management credibility | OLA Electric | A guidance-adherence table: each promise, the actual result, the verdict (achieved, unmet, revised down, on track) and the reason. It shows where credibility is rising or falling and what that means for the thesis. |

## How Equity-OS differs (doctrine, `.claude/project/invariants.md`)

- **Numbers.** The samples are AI-generated and "may contain inaccuracies". Ours must not be: every
  number comes from a fact or a deterministic calculation trace.
- **Estimates.** Projections are computed by code from explicit assumptions such as capacity,
  utilisation, price and margin. Each assumption is cited to a disclosure, or labelled as the
  analyst's or model's judgement. A model proposes an assumption; it never states the resulting
  figure.
- **Scenario probabilities** are labelled opinion, with stated triggers that become falsifiers.
- **Forensic checks** are deterministic tests over filed statements. A model only explains a flag.
- **Credibility** is the management ledger: guidance claims from transcripts and presentations,
  matched to later filed results by code.

## Source coverage

| Need | Source | Status |
|---|---|---|
| Quarterly P&L, segments | NSE/BSE XBRL and results PDFs; Screener/Tijori | Have (PDF extraction bugs open) |
| Multi-year P&L, balance sheet, cash flow | Screener/Tijori (10-year); half-year and annual XBRL | Vendor have; first-party balance sheet and cash flow not extracted |
| Concall transcripts, PPTs, recordings | Exchange filings (SEBI LODR, Reg. 30/46); Screener `#documents .concalls` (BSE links back to 2016); Tijori `#companyFilings` (own copies back to 2010) | Retained for Apar only; **no production intake** (`eqos-dna`, `eqos-msq`). Only Tijori's market-wide concall monitor is non-static |
| Investor presentations | Exchange filings; Screener concall PPT links; Tijori `#companyFilings` | **Missing** (`eqos-msq`) |
| Annual reports (notes, related parties, contingent liabilities, auditor remarks, capacity, capex plan) | Exchange filings; Screener links | **Missing** |
| Credit-rating rationales | Exchange filings; rating-agency sites; Screener links | **Missing** |
| Corporate announcements and events (capex, orders, approvals, fund raises, penalties) | NSE/BSE announcements; BSE/NSE/ET news; Tijori events | Partial |
| Upcoming results and board meetings (daily trigger) | NSE `boardMeetings`; Screener `/upcoming-results/`; Tijori upcoming results | NSE and Screener unparsed; Tijori parsed; no scheduler |
| Shareholding and pledges | Exchange shareholding filings; Screener/Tijori | Have |
| Prices and valuation | Upstox | Have |
| Peers (competitive position) | Screener peers; registry | Partial |
| Industry, capacity and market-share context | Industry bodies; disclosures | **Missing**; mostly narrative, labelled |

**Owner requirement (2026-10-28):** capture and retain everything Screener and Tijori show to the
owner's subscriber accounts, whether used today or not (A05-DECISION-005, private use). Audit and
gap plan: `docs/plans/2026-10-28-parallel-sol-lanes.md` lane 0.
