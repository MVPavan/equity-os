# Tijori Finance MCP — Evaluation

**Date:** 2026-08-21. **Rights:** bounded personal-use eval, owner's own free Tijori
account, authenticated automated login approved by the product owner (bd memory
`rights-tijori-autologin-approved-2026-08-21`). **Tijori data is DERIVED** (aggregator
restatement) — a cross-check/convenience layer, never source-of-record. First-party
Ind AS XBRL remains the spine.

**Credential handling:** login credentials were passed only as transient inline env
vars; no `.env` or password was written to disk. The Playwright session cookie lives in
gitignored external scratchpad (`scratchpad/tijori-eval/.../output/session.json`) and is
NOT committed. That session token is sensitive — treat scratchpad as disposable.

## Setup findings

- Repo: `LaZZy0v0/tijori-finance-mcp` (MIT, Node 18+, Playwright/Chromium). 20+ MCP tools.
- **Auth is via the owner's account, and the account is Zerodha-Kite-linked** — login
  submits email/password on `tijorifinance.com/account/signin/` (fields `#email` /
  `#pwd-field` / "SIGN IN"), which redirects through `kite.zerodha.com` OAuth and lands on
  the Tijori dashboard with a valid `sessionid` cookie.
- The MCP's bundled `discover.js` login is **manual** (waits for a human in a visible
  browser); its README's "automatic login" claim is inaccurate. An automated headless login
  (fill + submit + return to the Tijori origin for same-origin fetch) works.
- The tools mostly **render Tijori company pages** and scrape tables (not a clean public
  API); only company-search hits `/api/v1/ind/company_search/`. So the MCP *is itself* a
  browser-scraper of Tijori — a separate crawl4AI pass would use the same mechanism and is
  redundant given the MCP already returns full data.

## What it returns for Infosys (`infosys-limited`, verified live)

| Tool | Result | Notes |
|---|---|---|
| search | HCL Infosystems / **Infosys Ltd.** / Slone — pick by name | fuzzy; must disambiguate (naive first-match = wrong company) |
| financials `pl` | 16 rows × **9 annual periods (Mar'18–Mar'26) + latest quarter (Jun'26)** | Sales Mar'25 = ₹1,62,990 Cr — matches first-party XBRL |
| financials `bs` | 21 rows × Mar'17–Mar'26 | full balance sheet history |
| financials `cf` | 28 rows × Mar'17–Mar'26 | full cash-flow history |
| shareholding | quarter-by-quarter, **down to individual holders** | promoters (Nilekani, Murty…) + institutions (LIC, SBI MF…) with % |
| overview | mcap ₹4,58,642 Cr, PE 15.14, symbol INFY, company_id 149 | plus ratios, market_share, revenue_mix pointers |
| overview `quick_look` | **17 proprietary quality flags** (12 green / 3 red / 2 neutral) | e.g. Contingent Liabilities, Depreciation Effect — Tijori's own analysis + explanations |
| revenue_mix | **product-wise breakdown with history** (Software services 95.16% / products 4.84%, back to 2018) | segment/mix data XBRL & PDFs don't cleanly give |

## Where Tijori adds value over first-party sources

1. **Long history in one call** — 9–10 years of P&L/BS/CF (XBRL is per-filing).
2. **Revenue mix / product & segment breakdown with history** — not in XBRL, buried in PDFs.
3. **Shareholding down to named individual holders** across quarters — richer than exchange XBRL.
4. **Proprietary quality flags & ratios** (`quick_look`) — Tijori's analytical layer.

## Caveats

- **Derived, not primary.** Labels differ ("Sales" vs "Revenue from operations"); numbers are
  Tijori's restatement. Use for convenience/cross-check; verify against first-party XBRL/PDF
  for anything load-bearing. No filing-level provenance (no page anchor, no auditor sign-off).
- **Login-gated & Kite-dependent.** Needs the owner's account + Kite OAuth; session expires and
  must be refreshed. A production dependency on this is fragile and personal-account-bound.
- **Rights:** Tijori's own ToS governs; this is authenticated personal-account use only, no
  redistribution. Separate ToS surface from NSE/BSE (A05-DECISION-001/004).
- **crawl4AI alternative is redundant:** the MCP already scrapes Tijori via an authenticated
  headless browser and returns full data; a parallel crawl4AI pass would duplicate it. Only
  worth doing for independent verification, not coverage.

## Verdict

Tijori MCP works end-to-end on the owner's free account and is a **strong optional cross-check
and enrichment layer** — especially for revenue mix, long-history financials, individual-holder
shareholding, and quality flags. It is **not** a source-of-record (derived, login-gated,
personal-account-bound). Recommended role: wire it as an *optional enrichment/cross-check
adapter* behind the first-party spine, refreshed on demand — not a core pipeline dependency.
