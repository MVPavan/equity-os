# Upstox API — full surface inventory

Compiled 2026-09-03 for the equity-os acquisition layer. **Organized by Upstox's
own documentation navigation tree**, so any row can be checked against the site
without translation.

Sources: four independent researcher passes (Context7, a web crawl, Codex/Luna,
Codex/Sol) plus live orchestrator probes. Sol counted **99 endpoint-reference
pages** on the live site. Cross-referenced against Upstox's machine-readable
index at `/developer/api-documentation/llms.txt`.

**This system does not trade.** No orders, no positions, no funds. Every
judgement below follows from that.

---

## How to test anything in this document

Host `https://api.upstox.com` (a few order endpoints use `https://api-hft.upstox.com`).
Static instrument files come from `https://assets.upstox.com` and need no credential.

```
Authorization: Bearer <analytics token>
Accept:        application/json
User-Agent:    <any honest client name>
```

> ### The User-Agent is not optional
> Requests sent with Python's default `Python-urllib/3.x` are rejected at the CDN
> with **HTTP 403, Cloudflare `error_code 1010`, `browser_signature_banned`,
> `retryable: false`** — before the token is ever evaluated. A tester who omits
> it will conclude the whole API is dead.
>
> Verified by us live, and corroborated by an Upstox staff reply in the
> [community thread on Cloudflare 1010](https://community.upstox.com/t/upstox-api-historical-candle-request-blocked-by-cloudflare-error-1010/16758):
> the API does not enforce a particular UA, but Cloudflare may block particular
> request signatures. It is **not** part of the documented API contract — it is
> CDN hardening. Send a truthful client name; do not impersonate a browser.

`instrument_key` contains a pipe and **must be URL-encoded** in a path segment:
`NSE_EQ|INE758T01015` → `NSE_EQ%7CINE758T01015`.

Rate limits for everything we use ("Other Standard APIs"): **50/sec, 500/min,
2000 per 30 min.** The 30-minute bucket binds — ~1.1 req/s sustained; the 50/s is
burst headroom only.

## Legends

**Our category** — our decision, not Upstox's:

| | |
|---|---|
| **CORE** | Build against it now. |
| **MAYBE** | Plausible later; the row states the trigger. |
| **EXCLUDE** | Never call. Trading, account, or money-movement surface. |

**Access tier** — Upstox's own badge. `Plus` means a paid plan; `Unmarked` does
**not** imply entitlement, only that no badge is shown.

**Confidence:**

| | |
|---|---|
| **A** | Verified live by us on 2026-09-03 — request issued, response inspected. |
| **B** | Documented and independently cited by all four researcher passes. |
| **C** | Documented; one or two passes. Believed, not cross-checked. |
| **D** | Contradictory, undocumented, or inferred. **Probe before use.** |

---

# Developer API › Getting Started

Subsections below follow Upstox's own order: API Structure, Rate Limits,
Instruments, Authentication, Login, Sandbox, SDK, MCP Integration, Agent
Quickstart.

## Getting Started › API Structure

REST URLs follow `https://api.upstox.com/[VERSION]/[ENDPOINT]`; selected order
operations use `https://api-hft.upstox.com`. Authenticated calls send
`Authorization: Bearer` + `Accept: application/json`; JSON bodies add
`Content-Type: application/json`; token exchange uses
`application/x-www-form-urlencoded`. Special and non-ASCII URL values must be
URL-encoded. **No User-Agent requirement is documented** — see the CDN warning
at the top of this file.

## Getting Started › Rate Limits

"Other Standard APIs" — which covers everything we call — allow **50/sec,
500/min, 2000 per 30 min**. Order placement and payout buckets differ and are
irrelevant here. The 30-minute bucket binds.

## Getting Started › Instruments › Instrument files

Static gzipped JSON at `https://assets.upstox.com/market-quote/instruments/exchange/`.
Refreshed daily ~06:00 IST. **No token required.** CSV equivalents exist but are
deprecated in favour of JSON.

| Upstox name | URL suffix | Ours | Notes | Conf |
|---|---|---|---|---|
| Complete | `complete.json.gz` | **CORE** | 117,344 records, 3.2 MB gz. ISIN on **100% of equity rows** (22,433/22,433), none elsewhere. `instrument_key` is literally `SEGMENT\|ISIN`. | **A** |
| NSE | `NSE.json.gz` | **CORE** | 1.9 MB. | **A** |
| BSE | `BSE.json.gz` | **CORE** | 754 KB. | **A** |
| MCX | `MCX.json.gz` | EXCLUDE | Commodities, out of scope. | **C** |
| Mutual funds | `mf-instruments.json.gz` | MAYBE | The MF scheme universe. Kept because it is the only MF resource that is **not** account-scoped; costs nothing to retain. Supplies no flows, only the scheme list. | **C** |
| Suspended instruments | `suspended-instrument.json.gz` | **CORE** | 33,930 records, all equity, all with ISIN. **Singular "instrument"** — the plural form fails. Multiple rows per ISIN (one per series) — dedupe. Our only delisting/suspension signal. | **A** |
| MTF | `MTF.json.gz` | MAYBE | 60 KB; margin-eligible list. | **A** |
| NSE MIS | `NSE_MIS.json.gz` | EXCLUDE | Intraday-eligible list. | **C** |
| BSE MIS | `BSE_MIS.json.gz` | EXCLUDE | Intraday-eligible list. | **C** |
| Global | `global.json.gz` | MAYBE | 771 bytes; indices/indicators. | **A** |

> `exchange_token` is documented as reusable by the exchange for a different
> instrument after expiry. **Never use it as a long-term key.** Use
> `instrument_key` or ISIN.

## Getting Started › Instruments › Instrument Search

| Upstox name | Method | Path | Params | Tier | Ours | Conf |
|---|---|---|---|---|---|---|
| Instrument Search | GET | `/v2/instruments/search` | req `query`; opt `exchanges`, `segments`, `instrument_types`, `expiry`, `atm_offset`, `page_number`, `records` (max 30) | New / Beta | MAYBE | **D** |

> **Likely unavailable on an Analytics Token.** The Analytics Token page does not
> list Instruments or Instrument Search among its supported categories, and a
> [community report](https://community.upstox.com/t/upstox-analytics-token-works-for-historical-candles-but-returns-udapi100050-on-instrument-search/16604)
> describes `UDAPI100050 Invalid token` on Instrument Search while historical
> candles worked on the same token. No Upstox resolution in the thread.
> **This corrects an earlier row that rated it merely "undocumented".** Low
> stakes — the static file covers our need.

## Getting Started › Authentication

OAuth 2.0 authorization-code flow: Upstox hosts the login/consent screen,
requires the registered redirect URL, and returns a single-use authorization
code. Standard access tokens expire at 3:30 AM the following day. **We use none
of this** — the Analytics Token is issued from the Developer Apps page with no
redirect and no daily login.

## Getting Started › Login — **EXCLUDE (all)**

| Upstox name | Method | Path | Why excluded | Conf |
|---|---|---|---|---|
| Authorize | GET | `/v2/login/authorization/dialog` | OAuth dance; we hold a pre-issued Analytics Token. | **B** |
| Get Token | POST | `/v2/login/authorization/token` | Token expires 3:30 AM next day; auth code single-use. | **B** |
| Access Token Request | POST | `/v3/login/auth/token/request/:client_id` | Beta webhook flow. | **C** |
| Logout | DELETE | `/v2/logout` | **Could invalidate a year-long credential.** | **B** |

---

## Getting Started › Sandbox

A parallel simulated environment; sandbox tokens last 30 days and cannot touch
live data. **EXCLUDE** — it cannot produce real observations, so it has no place
in a provenance-anchored pipeline.

## Getting Started › SDK

`upstox-python-sdk`, v2.29.0 (released 2026-08-19), swagger-codegen output.
**Decision: do not adopt — call the API directly.** Reasons, in weight order for
this repo:

1. **Provenance needs raw bytes.** We sha256 the response body before parsing;
   the SDK deserializes internally.
2. **The types are empty where it counts** — every generated field is
   `[optional]`, and candles are typed `list[list[object]]`. No `py.typed`, so
   `mypy --strict` would need `ignore_missing_imports`.
3. **Double re-wrap** — JSON → generated mutable class → frozen Pydantic.
4. **Surface hygiene** — importing `upstox_client` puts `place_order` and
   `exit_positions` one attribute away in a system that must never trade.

Dependencies pull `six` (Python-2 shim), `uuid` (an abandoned PyPI backport that
shadows the stdlib module), and `websocket-client` + `protobuf` for a streaming
surface we exclude. Counter-argument on record: the SDK tracks v2/v3 URL churn
that hand-built paths will get wrong — mitigated by one module of versioned path
constants.

## Getting Started › MCP Integration — real, and irrelevant to us

| | |
|---|---|
| Server | `https://mcp.upstox.com/mcp` |
| Auth | OAuth; **"re-authorize your account connection daily"** |
| Cost | Free |
| Exposes | holdings, orders, positions, mutual funds, funds, profile |

**Read-only, but account-scoped only.** It exposes our entire EXCLUDE bucket and
nothing else — no market data, no candles, no fundamentals — and it requires the
daily re-auth the Analytics Token exists to avoid. **EXCLUDE**, with the reason
recorded so the question does not get re-asked.

## Getting Started › Agent Quickstart

The same MCP server plus a setup guide (`upstox-skill` package, `npx` bridge).
Same daily-OAuth assumption. Useful byproduct: Upstox publishes a
machine-readable endpoint index at `/developer/api-documentation/llms.txt`.

# Developer API › Account & Funds — **EXCLUDE (all)**

Account state, money movement, and hypothetical costs. No research value, and
leaks identity into logs.

| Group | Endpoints | Note | Conf |
|---|---|---|---|
| User | `/v2/user/profile`, `/v2/user/get-funds-and-margin`, `/v3/user/get-funds-and-margin`, `GET+PUT /v2/user/ip`, `GET+POST /v2/user/kill-switch` | **`PUT /v2/user/ip` invalidates existing access tokens** — calling it would break our credential. 1 change/week. | **C** |
| Payments | `/v2/user/payments/payin`, `/payout` (GET/POST/PUT/DELETE), `/payout/modes` | Money movement. | **C** |
| Charges | `/v2/charges/brokerage`, `/v2/charges/historical-trades` | Hypothetical transaction costs — not a fact about a company. | **C** |
| Margins | `POST /v2/charges/margin` | Up to 20 instruments/request. | **C** |

---

# Developer API › Orders & Trading

Orders and GTT are EXCLUDE outright — mutating trade surface, violating the
no-trade invariant. **IPO is split**: the two discovery GETs are read-only
market information and are kept; only the application path is a trading action.

| Group | Endpoints | Conf |
|---|---|---|
| Orders | `/v2\|v3/order/place`, `/modify`, `/cancel` (v2 forms **deprecated**; v2/v3 place-modify-cancel use the `api-hft` host), `/v2/order/multi/place`, `/multi/cancel`, `/retrieve-all`, `/details`, `/history`, `/trades`, `/trades/get-trades-for-day`, `/positions/exit` | **B** |
| GTT Orders | `/v3/order/gtt` place / modify / cancel / get | **B** |
| IPO — application | `POST /ipos/orders`, `GET /ipos/orders`, `GET /ipos/orders/:id`, `DELETE /ipos/orders/:id` | **C** |

## Orders & Trading › IPO — discovery only (**MAYBE**)

| Upstox name | Method | Path | Params | Ours | Conf |
|---|---|---|---|---|---|
| Get IPOs | GET | `/v2/ipos` | `status`, `issue_type` | MAYBE | **C** |
| Get IPO Details | GET | `/v2/ipos/:id` | path `id` | MAYBE | **C** |

Kept by owner decision, 2026-09-03: knowing which IPOs are open or upcoming is
research, not trading. These are read-only and touch no account state.

Applying is a different matter — `POST /ipos/orders` requires bidding capital and
a UPI mandate, and the order GETs/DELETE only describe applications we never
make. Those stay EXCLUDE.

**Trigger to promote to CORE:** a primary-market workstream that tracks new
listings into the universe. Note the instrument master already gains a new
listing on its own once it trades, so this is early warning, not a gap.

---

# Developer API › Portfolio — **EXCLUDE (all)**

*(Its own top-level branch — not under Account & Funds. Absent from the
screenshots because it was collapsed.)*

| Group | Endpoints | Note | Conf |
|---|---|---|---|
| Portfolio | `/v2/portfolio/long-term-holdings`, `/short-term-positions`, `/v3/portfolio/mtf-positions`, `PUT /v2/portfolio/convert-position` | The GETs are side-effect-free but meaningless — we custody nothing through Upstox. Trigger if that changes: reconciling real holdings against XBRL-derived ones. | **B** |
| Mutual Fund | `/v2/mf/holdings`, `/orders`, `/orders/:id`, `/sips` | **Account-scoped, not market data.** Considered 2026-09-03 as a fund-flow indicator and rejected on evidence: Upstox's index describes holdings as "units, last NAV, unrealized P/L, folio… in a single **portfolio** response", and the launch note frames the group as "orders, SIPs, holdings… for **portfolio and wealth integrations**". No scheme AUM, no industry flows, no NAV history. For a non-trading account these return an empty list. The fund-flow signal lives in FII/DII Activity and Share Holdings instead. | **C** |
| Trade Profit And Loss | `/v2/trade/profit-loss/{data,metadata,charges}` | Realized P&L presupposes trades we never made. Uses `dd-mm-yyyy` dates, unlike everything else. | **B** |

---

# Developer API › Market Data

**This branch is our entire integration.** Note that Fundamentals and News live
*under* Market Data, not at the root.

## Market Data › Historical Data — the price lane

| Upstox name | Method | Path | Tier | Ours | Conf |
|---|---|---|---|---|---|
| Historical Candle Data **V3** | GET | `/v3/historical-candle/:instrument_key/:unit/:interval/:to_date[/:from_date]` | Unmarked | **CORE** | **A** |
| Intraday Candle Data **V3** | GET | `/v3/historical-candle/intraday/:instrument_key/:unit/:interval` | Unmarked | **CORE** | **C** |
| Historical Candle Data | GET | `/v2/historical-candle/:instrument_key/:interval/:to_date[/:from_date]` | Unmarked | EXCLUDE — **badge: Deprecated** | **B** |
| Intraday Candle Data | GET | `/v2/historical-candle/intraday/:instrument_key/:interval` | Unmarked | EXCLUDE — **badge: Deprecated** | **B** |

### Response shape — verified live, and it contradicts Upstox's own examples

The website renders candles as named objects. They are not. Seven-element
positional arrays:

```json
["2026-08-28T00:00:00+05:30", 329.1, 330.0, 324.3, 328.0, 31385139, 0]
```

| idx | 0 | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|---|
| field | timestamp | open | high | low | close | volume | open interest |

Independently confirmed by the Backtesting guide, which states the same tuple.
Timestamps carry `+05:30`, not UTC. Rows return **most-recent-first** (observed,
not documented — sort explicitly). Envelope `{"status":"success","data":{"candles":[…]}}`.

**Path order is `to_date` before `from_date`** — verified live, against one of two
contradictory doc pages. Reversing it returns a wrong window silently, not an
error.

Verified live 2026-09-03: `to_date` **is inclusive**; rows return
**most-recent-first**; a `days` request spanning **more than a decade fails
loudly** with `400 UDAPI1148` rather than truncating silently, and a request of
exactly ten years returns the full 2,478-row series untruncated. The chunker can
therefore rely on a hard error rather than having to detect short reads.

### Chunking caps

| Unit | Intervals | History from | Max per request |
|---|---|---|---|
| minutes | 1–300 | ~Jan 2022 | 1 month (1–15); 1 quarter (>15) |
| hours | 1–5 | ~Jan 2022 | 1 quarter |
| days | 1 | **~Jan 2000** | **1 decade** |
| weeks | 1 | ~Jan 2000 | no limit |
| months | 1 | ~Jan 2000 | no limit |

Full daily backfill 2000→today = **3 requests per instrument**. Our 92 entities
≈ 276 requests, comfortably inside one 30-minute bucket.

> ### SETTLED (A) — candles ARE split/bonus adjusted
> Probed live 2026-09-03. Four corporate actions were derived from the
> corporate-actions endpoint itself (not from memory) and candles pulled across
> each ex-date: E2E Networks **1:10 split** (2026-06-05), Authum Invest **4:1
> bonus** (2026-01-13), Ram Ratna Wires **1:1 bonus** (2025-12-26), Anand Rathi
> Wealth **1:1 bonus** (2026-06-03). All four series are smooth across the
> ex-date.
>
> Orchestrator re-check on the strongest case: over a 3-month window spanning
> the 1:10 split, the largest single-day close drop is **5.0%** (430.3 → 408.8)
> against the ~90% cliff an unadjusted series would show; the whole window
> ranges 259.2–452.9 with no discontinuity.
>
> **Consequence:** the price series is directly usable for returns, drawdown and
> volatility without our own adjustment layer.
>
> It also means Upstox **rewrites history**: a candle fetched before a corporate
> action will not byte-match the same candle fetched after it. Content-hash every
> fetch, and retain every version.
>
> **Correction (2026-09-03).** An earlier draft of this note said to "treat a hash
> change over an unchanged window as a corporate-action restatement, not
> corruption." That overstated the evidence and is withdrawn. The *adjustment* is
> grade A — observed. The causal reading is an inference, and a weak one: Upstox's
> own corporate-action endpoint is not independent evidence about Upstox's own
> candles, and a feed glitch co-occurring with an unrelated split would earn the
> same reassuring label. A revision may be called action-driven only when the
> observed cross-ex-date price ratio matches the declared ratio within tolerance;
> otherwise it is an unexplained revision and must be surfaced, never blessed.

## Market Data › Expired Instruments — `Plus` **(paid)**

| Upstox name | Method | Path | Ours | Conf |
|---|---|---|---|---|
| Get Expiries | GET | `/v2/expired-instruments/expiries?instrument_key=` | MAYBE | **C** |
| Get Expired Option Contracts | GET | `/v2/expired-instruments/option/contract?instrument_key=&expiry_date=` | MAYBE | **C** |
| Get Expired Future Contracts | GET | `/v2/expired-instruments/future/contract?instrument_key=&expiry_date=` | MAYBE | **C** |
| Get Expired Historical Candle Data | GET | `/v2/expired-instruments/historical-candle/:key/:interval/:to_date/:from_date` | MAYBE | **C** |

**This account HAS Upstox Plus — verified live 2026-09-03.**
`GET /v2/expired-instruments/expiries?instrument_key=NSE_INDEX|Nifty 50` returns
HTTP 200 with a real expiry list running from 2024-10-03. So the `Plus` badge is
**not** a barrier here, and the trigger reduces to one thing: **scope extending
to derivatives.**

Documented gating, for the record: *"The [Expired Instruments APIs] are available
on the Upstox Plus plan. Instrument Search and Historical Candle Data V3 are
available on all plans."* A non-entitled call is documented to return
`UDAPI1149`; we could not observe that path, because this token is entitled.
The exact HTTP status for it remains **D**.

Consequence: **Backtesting is also available to us**, since its only gated
inputs are these endpoints.

## Market Data › Backtesting — `Plus`

Not an endpoint group — a **workflow guide** composing Instrument Search, Get
Expiries, expired contracts, and Historical Candle Data V3. No new endpoints.

## Market Data › Market Quote — snapshots

| Upstox name | Method | Path | Ours | Conf |
|---|---|---|---|---|
| Full Market Quotes | GET | `/v2/market-quote/quotes?instrument_key=` (≤500 keys) | MAYBE | **B** |
| OHLC Quotes **V3** | GET | `/v3/market-quote/ohlc?instrument_key=&interval=` | MAYBE | **C** |
| LTP Quotes **V3** | GET | `/v3/market-quote/ltp?instrument_key=` | MAYBE | **C** |
| Option Greeks | GET | `/v3/market-quote/option-greek?instrument_key=` (≤50 keys) | MAYBE | **C** |
| OHLC Quotes | GET | `/v2/market-quote/ohlc` | EXCLUDE — **Deprecated** | **B** |
| LTP Quotes | GET | `/v2/market-quote/ltp` | EXCLUDE — **Deprecated** | **B** |

Trigger: needing a same-day snapshot before the candle closes. **Full Market
Quotes has no v3 replacement — it stays v2 and is NOT deprecated.** All quote
endpoints mutate continuously during a session: point-in-time observations,
never settled facts.

## Market Data › Option Chain — MAYBE (derivatives only)

| Upstox name | Method | Path | Conf |
|---|---|---|---|
| Option Contracts | GET | `/v2/option/contract?instrument_key=` (opt `expiry_date`) | **C** |
| Put/Call Option Chain | GET | `/v2/option/chain?instrument_key=&expiry_date=` | **C** |

> `expiry_date` accepts **relative keywords** (`current_week`, `next_month`, …).
> A determinism hazard: the same request returns different data on different
> days. If ever used, resolve to an explicit date and store the resolved value.

## Market Data › Market Information

| Upstox name | Method | Path | Params | Ours | Conf |
|---|---|---|---|---|---|
| Get Options Smartlist | GET | `/v2/market/smartlist/options` | `asset_type`, `category`; opt paging | MAYBE | **C** |
| Get Futures Smartlist | GET | `/v2/market/smartlist/futures` | `asset_type`, `category`; opt paging | MAYBE | **C** |
| Get MTF Smartlist | GET | `/v2/market/smartlist/mtf` | opt paging, max 50 | MAYBE | **C** |
| Get FII Data | GET | `/v2/market/fii` | req `data_type`, `interval`; opt `from` | **CORE** | **C** |
| Get DII Data | GET | `/v2/market/dii` | req `data_type`, `interval`; opt `from` | **CORE** | **C** |
| Get OI | GET | `/v2/market/oi` | `instrument_key`, `expiry`, `date` | MAYBE | **C** |
| Get Change in OI | GET | `/v2/market/change-oi` | + `interval` | MAYBE | **C** |
| Get Max Pain | GET | `/v2/market/max-pain` | + `bucket_interval` | MAYBE | **C** |
| Get PCR | GET | `/v2/market/pcr` | + `bucket_interval` | MAYBE | **C** |
| Market Holidays | GET | `/v2/market/holidays[/:date]` | `date` is a **path** segment, not a query param | **CORE** | **B** |
| Market Timings | GET | `/v2/market/timings/:date` | | **CORE** | **C** |
| Exchange Status | GET | `/v2/market/status/:exchange` | | MAYBE | **C** |

**FII/DII adopted by owner decision, 2026-09-03.** Institutional flows; data from
1 Apr 2026; 30 trading days per request at 1D, 12 months at 1M. The start date is
documented text taken at face value, unverified against market history.

Market Holidays is needed to compute the last completed trading day, so a
missing candle is distinguishable from a closed market. **Never use
`datetime.now()` for that.** Exchange Status is scheduler gating only — never
store its output as a fact.

OI / Max Pain / PCR / Smartlists: derivatives. Trigger is scope extension.

## Market Data › Fundamentals — all keyed by ISIN, all v2, all GET

| Upstox name | Path | Params | Ours | Conf |
|---|---|---|---|---|
| Get Company Profile | `/v2/fundamentals/:isin/profile` | — | EXCLUDE | **C** |
| Get Balance Sheet | `/v2/fundamentals/:isin/balance-sheet` | `type`, `fs` | **CHECK-ONLY** | **C** |
| Get Cash Flow | `/v2/fundamentals/:isin/cash-flow` | `type`, `fs` | **CHECK-ONLY** | **C** |
| Get Income Statement | `/v2/fundamentals/:isin/income-statement` | `type`, `time_period`, `fs` | **CHECK-ONLY** | **C** |
| Get Share Holdings | `/v2/fundamentals/:isin/share-holdings` | — | **CORE** | **C** |
| Get Key Ratios | `/v2/fundamentals/:isin/key-ratios` | — | **CHECK-ONLY** | **C** |
| Get Corporate Actions | `/v2/fundamentals/:isin/corporate-actions` | — | **CORE** | **C** |
| Get Competitors | `/v2/fundamentals/:isin/competitors` | **takes an `instrument_key`, not a bare ISIN** | EXCLUDE | **A** |

**A fourth category, added 2026-09-03: CHECK-ONLY.**

Four statement/ratio endpoints are neither CORE (they produce no fact) nor
EXCLUDE (they are built and run). They are **Lane B**: a parse-check on
Screener's HTML scraping, log-only, barred from reconciliation. The independence
test that disqualified them as a third opinion is exactly what qualifies them
here — shared lineage means a disagreement isolates to our parser rather than to
the data. Design in `docs/research/upstox-integration-plan.md` §1, §6.9, §9.6.

`profile` and `competitors` move to EXCLUDE: neither has a Screener counterpart,
so neither can check anything.

**Two are CORE.**

*Corporate Actions* — splits, bonuses and dividends are required to interpret any
price series, and give an independent cross-check against XBRL. No stable event
id; synthesize `(isin, name, ex_date, amount, ratio)`.

*Share Holdings* — promoted 2026-09-03. Upstox's own index describes it as
"promoter, FII, DII, and public holding percentages **over time**", i.e. a time
series, not the flat snapshot an earlier draft of this file assumed. That makes
it a per-company money-flow indicator, complementing the market-wide FII/DII
activity endpoints. It is also the closest thing Upstox offers to the fund-flow
signal the mutual-fund endpoints cannot supply (those are account-scoped —
see Portfolio). Caveat stands: percentages only, **no pledge data**, which
Screener does provide.

### The remaining six are REFUSED FOR RECONCILIATION. Independence test FAILED, 2026-09-03.

Refused as a *source of facts*. Four of the six return as CHECK-ONLY (Lane B,
above); `profile` and `competitors` are refused outright. Nothing below
licenses any of the six to produce a fact, and the evidence below is what
disqualifies them from doing so.

**Upstox fundamentals share lineage with Screener.** Verified by the orchestrator
against our own captured Screener data and our own XBRL-anchored gold facts.

**Fingerprint 1 — the mislabel (conclusive).** Upstox's `operating_profit` is not
operating profit. It is Screener's *Profit before tax* row, to the crore, in
every quarter checked — TITAN consolidated below, and reproduced across HFCL
(consolidated) and NETWEB (standalone), 12/12 data points with no exceptions:

| TITAN consolidated | Sep-25 | Dec-25 | Mar-26 | Jun-26 |
|---|---|---|---|---|
| Screener "Operating Profit" | 1875 | 2713 | 1938 | 2890 |
| Screener "Profit before tax" | **1522** | **2223** | **1577** | **2429** |
| Upstox `operating_profit` | **1522** | **2223** | **1577** | **2429** |
| Screener "Net Profit" | 1120 | 1684 | 1179 | 1777 |
| Upstox `net_profit` | 1120 | 1684 | 1179 | 1777 |

Two independent pipelines do not both derive the identical PBT *and* mislabel it
identically.

**Fingerprint 2 — the shared error.** For TITAN's quarter ended 2026-06-30 our
gold facts already carried `needs_human_review: True` on a first-party/derived
disagreement:

| | BSE filing (first party) | Screener (derived) | Upstox |
|---|---|---|---|
| net profit | **1699.00** | **1777** | **1777.0** |
| revenue | 18101.00 | 21356 | 21502.0 |

Upstox reproduces Screener's divergent net profit exactly and departs from the
audited filing by the same ₹78 crore. (Revenue is *not* an exact match — Upstox
runs ~0.6–0.7% above Screener's "Sales" in all four quarters, so that line is a
different derived definition rather than a fingerprint. Reported here because an
earlier draft of the finding overstated it.)

**Consequences, and they are binding:**

1. **Upstox fundamentals must never corroborate Screener.** Agreement between
   them is one opinion counted twice. Feeding both into a fail-closed reconciler
   would manufacture false confidence — the precise failure the reconciler
   exists to prevent.
2. **`operating_profit` is actively wrong.** Any consumer reading it as operating
   profit gets profit before tax. This is a trap independent of lineage, and it
   is reason enough to refuse the field even for exploratory use.
3. The **three-source** reconciliation design collapses to **two** sources for
   fundamentals: XBRL (first party) and Screener/Upstox (one derived opinion).
4. This does **not** touch the CORE lanes. Price history, the instrument
   universe, suspensions, corporate actions and FII/DII have no XBRL or Screener
   counterpart — they are additive, not confirmatory, so lineage is irrelevant
   to them.

Known limits regardless: only **4 periods** of history; `full_statement` is
annual-only; values in **INR crore, rounded**, against our rupee-exact XBRL;
cash-flow `history[].change` is vendor-derived, not source. Key Ratios covers
P/E, P/B, ROA, ROE, ROCE and EV/EBITDA **benchmarked against peers** — richer
than the bare snapshot an earlier draft described, though still no time series.

`type` = `consolidated`|`standalone` (default consolidated). `fs=true` adds a
line-item breakdown. Errors `UDAPI1206` invalid ISIN, `UDAPI1207` invalid type.

**Verified live 2026-09-03:** every endpoint returns exactly **4 periods**;
`fs=true` adds line-item detail but no extra periods; `standalone` genuinely
differs from `consolidated`; `units_in` is `"crore"` throughout.

**Gotcha (A):** `competitors` is the one endpoint that does **not** accept a bare
ISIN in the `:isin` slot — it requires the `NSE_EQ|<isin>` instrument_key form
and returns `400 UDAPI100011` otherwise. The other seven take the bare ISIN. A
single adapter that formats the path uniformly will fail on exactly this one.

> **OPEN (D), low probability.** One researcher reported an overview page
> rendering these as `/company/x?isin=`. That form appears **nowhere** in
> Upstox's `llms.txt`, where every fundamentals entry resolves to the
> `/v2/fundamentals/:isin/x` path form. Most likely a misread of an overview
> page. Retained only so a probe can close it.
>
> **SETTLED (A) — `time_period` does NOT work on Balance Sheet or Cash Flow.**
> Probed live 2026-09-03: passing `time_period=quarterly` to those two returns a
> **byte-identical** body to the parameter-free call. Silently ignored — no
> error, no different data. Only Income Statement honours it.
>
> This **refutes** the reading recorded here earlier (owner's and mine both):
> the index calling all three "annual or quarterly", and the responses carrying
> `time_period: yearly`, describe the *response* shape, not an accepted request
> parameter. The parameter tables were right and the prose misled us.
>
> **Consequence:** Upstox gives quarterly data for the income statement only.
> Quarterly balance sheet and cash flow remain Screener/XBRL-only.

## Market Data › News

| Upstox name | Method | Path | Ours | Conf |
|---|---|---|---|---|
| Get News | GET | `/v2/news?category=&instrument_keys=&page_number=&page_size=` | MAYBE | **C** |

`category=instrument_keys` (≤30 keys) is the usable form. **Serves only the
preceding 7 days** — a hard ceiling on any news lane. `category=positions` and
`holdings` read live account state; not applicable and not to be called.

---

# Developer API › Realtime & Streaming

*(Own top-level branch. Absent from the screenshots — collapsed.)*

| Upstox name | Path | Ours | Conf |
|---|---|---|---|
| Market Data Feed **V3** | `wss://api.upstox.com/v3/feed/market-data-feed` | MAYBE | **C** |
| Market Data Feed Authorize V3 | `GET /v3/feed/market-data-feed/authorize` | MAYBE | **C** |
| Market Data Feed | `wss://api.upstox.com/v2/feed/market-data-feed` | EXCLUDE — **DISCONTINUED** | **B** |
| Market Data Feed Authorize | `GET /v2/feed/market-data-feed/authorize` | EXCLUDE — **DISCONTINUED** | **B** |
| Portfolio Stream Feed | `wss://api.upstox.com/v2/feed/portfolio-stream-feed` | EXCLUDE | **B** |
| Portfolio Stream Feed Authorize | `GET /v2/feed/portfolio-stream-feed/authorize` | EXCLUDE | **B** |

The v2 feed is **fully discontinued after 2025-08-22** — not merely deprecated.
Calling it fails outright rather than degrading. The v3 feed is Protobuf-encoded
and its `full_d30` mode is `Plus`-gated.

Streaming cannot be content-hashed, so it sits outside our provenance model by
construction. Trigger: an intraday-monitoring use case that explicitly accepts
non-deterministic, unarchived data.

**Websocket Implementation** and **Webhook** are guides, not callable endpoints.
Webhook is an inbound order/GTT push surface — EXCLUDE regardless.

---

# Developer API › Appendix

Reference material only; no endpoint pages.

---

# Auth model (verified live)

| | |
|---|---|
| **Analytics Token** | 1-year validity, **read-only GET only**, one per account, **no authorization redirect, no daily login**. |
| **Static IP required** | User, Payments, Orders, GTT Orders, Portfolio, Mutual Fund, Trade P&L |
| **Static IP NOT required** | Charges, Margins, Market Quote, Historical Data, Option Chain, Market Information, Fundamentals, News, IPO, Websocket |
| **Full OAuth token** | Expires 3:30 AM next day; auth code single-use. Not needed for anything we do. |

**Every CORE endpoint is on the no-Static-IP list** — proven end to end by a live
v3 candle request returning HTTP 200.

Note the structural check: Upstox's Static-IP-required list is almost exactly our
EXCLUDE list. What we must never call is largely what our token cannot reach.

Instruments and Instrument Search are **not named** in the Analytics Token's
supported categories. The static files need no token; Instrument Search appears
to reject it.

# Cross-cutting hazards

1. **No server-side as-of / version / last-updated field on any response.** A
   silent restatement is undetectable from the payload. Detection must be our own
   content hash. (Confirmed across all 8 fundamentals response schemas.)
2. **Ordering is not guaranteed** anywhere except cash-flow history. Hash raw
   bytes, never a re-serialized structure.
3. **All fundamentals money is INR crore, rounded** — a ±₹5,000,000 quantum
   against rupee-exact XBRL. A sanity band, not a fine-grained cross-check.
4. **Parse numerics as `Decimal`, never float.** A float round-trip breaks
   byte-identical rebuilds.
5. **Error envelope:** `{"status":"error","errors":[{"error_code","message",
   "property_path","invalid_value"}]}`. The camelCase variants are themselves
   deprecated — their presence signals an old route.
6. **Cloudflare 1010 is neither a rate limit nor an auth failure.** It needs its
   own outcome type; backoff will never clear it.
7. **Relative expiry keywords** on option endpoints make the same request return
   different data on different days.

# Open questions — status after live probing (2026-09-03)

Nine questions were probed live with ~140 GET requests. Six are settled, two
partly, one untestable from this account.

| # | Question | Status | Answer |
|---|---|---|---|
| 1 | Candles adjusted for splits/bonuses? | **SETTLED (A)** | **Yes, adjusted.** Four events across three ratios, all smooth. Largest drop near a 1:10 split was 5.0% vs the ~90% an unadjusted series needs. |
| 2 | Is Upstox fundamentals independent of Screener's upstream? | **SETTLED (A)** | **No — shared lineage.** Upstox's `operating_profit` is Screener's Profit-before-tax to the crore (12/12 across 3 companies, 2 bases), and Upstox reproduces Screener's divergence from the BSE filing on TITAN Jun-26. The six non-corporate-action fundamentals endpoints are refused. |
| 3 | `time_period=quarterly` on Balance Sheet / Cash Flow? | **SETTLED (A)** | **No.** Byte-identical response; silently ignored. Income Statement only. Quarterly BS/CF stays Screener/XBRL-only. |
| 4 | Period count per fundamentals endpoint? | **SETTLED (A)** | Exactly 4 everywhere. `fs=true` adds detail, not periods. `standalone` ≠ `consolidated`. `units_in="crore"`. |
| 5 | Which fundamentals path form is live? | **SETTLED (A) / partial** | `/v2/fundamentals/{isin}/x` returns 200. The `/company/...` variants were **not** called — they fall outside the probe allowlist. Given they appear nowhere in `llms.txt`, treat as non-existent. |
| 6 | Does Instrument Search accept the Analytics Token? | **SETTLED (A)** | **Yes.** HTTP 200 with real data. The community-reported `UDAPI100050` did not reproduce. |
| 7 | HTTP status for `UDAPI1149` on a non-Plus account? | **UNTESTABLE** | **This account has Plus** — the gated endpoint returned 200. The non-entitled path cannot be observed from here. |
| 8 | Is the Postman collection current? | **SETTLED (A)** | **Stale.** Dated 2023-10-23; contains no `fundamentals`, no `cash-flow`, no `historical-candle`, no v3 anything. Do not use it. |
| 9 | Candle edge cases | **SETTLED (A)** | `to_date` inclusive; most-recent-first; >10y → `400 UDAPI1148`; exactly 10y → 200, 2,478 rows, no truncation. |

## Predictions this file got wrong

Recorded so the same reasoning is not trusted again:

- **Question 3** — this file rated `time_period=quarterly` "likely yes" on the
  strength of Upstox's prose calling all three statements "annual or quarterly".
  Wrong. The prose described the response, not an accepted parameter.
- **Question 6** — this file rated Instrument Search "probably not" on a single
  community report. Wrong. It works.
- **Question 7** — the `Plus` badge was treated as a limitation on our access.
  It is not; this account is entitled, which also makes **Backtesting**
  available.

Raw probe evidence: `scratchpad/upstox/probes/` (110 response files and
`RESULTS.md`).

## Reference material for a tester

- Machine-readable endpoint index: `/developer/api-documentation/llms.txt` (249 lines).
- `Appendix › Field Pattern` — regexes for `instrument_key`, order id, and date formats.
- `Appendix › Equity Security Type` — SME, IPO, RELIST, PCA, NORMAL classifications.
- `Appendix › Exchange`, `Appendix › Market Status`, `Appendix › Order Status` — enum references.
- `Appendix › Postman collection` — see question 8 before trusting it.

# Sources

- Researcher reports and probes: `scratchpad/upstox/` —
  `report-context7.md`, `report-web.md`, `report-codex-luna.md`,
  `report-sol-navtree.md`, `probe-instrument-master.md`, `CONSOLIDATION.md`.
- Prior evaluation: `docs/research/upstox-api-evaluation.md` (2026-08-24).
- Upstox documentation `https://upstox.com/developer/api-documentation/` and its
  `llms.txt` index.
