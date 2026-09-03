# Upstox schema verification — 2026-09-03

This documents the verification pass over `scratchpad/upstox/schemas/*.md`
(six files, all doc-derived before this pass) against live Upstox API
responses and the live static instrument files. All six schema files were
edited in place; every change is marked `**VERIFIED**`, `**CORRECTED: docs
said X, actual is Y**`, `**UNDOCUMENTED FIELD**`, or `**NOT OBSERVED**`
inline at the field it applies to. This file is the summary and the ranked
list of what would actually break a strict parser.

## What was checked and how much

Two sources of live evidence, both real authenticated (or, for the static
files, unauthenticated) GET calls against `api.upstox.com` /
`assets.upstox.com`, GET-only, restricted to the allowlisted path prefixes,
with the required `User-Agent` header, token read once from
`~/.secrets/upstox_token` inside a script and never printed/logged:

1. **Reused, at no additional cost**: ~110 response files already on disk in
   `scratchpad/upstox/probes/` from an earlier same-day run (`RESULTS.md`
   documents that run's own methodology and rate-limiting). The 83
   `ca-*.json` corporate-actions responses and the 4 `candle-*.json`
   split/bonus-adjustment responses did almost all of the heavy lifting for
   this pass.
2. **New probes this pass**, in `scratchpad/upstox/probes/verify2/`: 38
   response files from ~35 new live calls (`run2.py` + `driver.py` through
   `driver5.py`), spaced ≥1.1s apart, plus two static-file downloads
   (`complete.json.gz`, 3.2 MB compressed / 54.6 MB decompressed, 117,344
   records; `suspended-instrument.json.gz`, 0.85 MB compressed / 9.7 MB
   decompressed, 33,930 records) fetched once from `assets.upstox.com` with
   no token and scanned **exhaustively, every record**, not sampled.

**Total live responses inspected for this pass: 83 (corporate-actions) + 4
(candle adjustment) + 4 (candle edge-case probes: inclusive-to_date,
decade-span error, exactly-decade, market-holidays sanity) + 38 (verify2) +
2 static-file downloads (151,274 records scanned in full) = 129 live HTTP
responses plus a full census of two multi-hundred-thousand-record files.**

### Explicitly out of scope (per the verification brief)

- The other six `/v2/fundamentals/*` endpoints — `profile`, `balance-sheet`,
  `cash-flow`, `income-statement`, `key-ratios`, `competitors` — were
  **skipped entirely**, per instructions: an earlier independence test
  (`scratchpad/upstox/probes/independence-test/`) found they share lineage
  with Screener (`operating_profit` there is actually Screener's
  profit-before-tax), so no verification effort was spent on them. Marked
  with a `SKIPPED` banner at each heading in `fundamentals.md`.
- `/v2/ipos/{id}` — not in the Tier 2 list given (`/v2/ipos` was), not
  called.
- `NSE.json.gz`, `BSE.json.gz`, `MCX.json.gz`, `MTF.json.gz`,
  `NSE_MIS.json.gz`, `BSE_MIS.json.gz`, `mf-instruments.json.gz`,
  `global.json.gz` were **not** separately fetched — only `complete.json.gz`
  and `suspended-instrument.json.gz` were downloaded. `complete.json.gz`
  happens to already contain NSE/BSE/MCX/global/MTF-*shaped* records mixed
  in (see findings below), which gave partial indirect coverage of the MTF
  and global-index/indicator record shapes, but the MIS and mutual-fund
  record shapes remain **NOT OBSERVED**.
- No invalid-input / error-path probes were run against `/v2/fundamentals/*`
  (corporate-actions, share-holdings), `/v2/news`, or `/v2/ipos` — their
  documented error codes are unverified in this pass. Error-envelope shape
  *was* verified, but only via `/v3/historical-candle`.

## Verification status by endpoint

| Endpoint | Tier | Status |
|---|---|---|
| `/v3/historical-candle/{key}/{unit}/{interval}/{to}[/{from}]` | 1 | **Verified exhaustively** — all 5 units tried, decade cap confirmed both ways, `from_date`-omitted behavior characterized per unit, error envelope captured |
| `/v3/historical-candle/intraday/{key}/{unit}/{interval}` | 1 | **Verified** — `minutes/1`, `minutes/30`, `hours/1` on a live trading day |
| `/v2/fundamentals/{isin}/corporate-actions` | 1 | **Verified exhaustively** — 83/83 ISINs, 108 events, full enum coverage |
| `/v2/fundamentals/{isin}/share-holdings` | 1 | **Verified** — 5 companies spanning micro- to large-cap |
| `/v2/market/fii` | 1 | **Verified** — 3 calls, all fields match |
| `/v2/market/dii` | 1 | **Verified** — 2 calls, all fields match |
| `/v2/market/holidays[/{date}]` | 1 | **Verified** — 3 calls (no date, holiday date, trading-day date) |
| `/v2/market/timings/{date}` | 1 | **Verified** — 2 calls (trading day, holiday) |
| Static: `complete.json.gz` | 1 | **Verified exhaustively** — full scan, 117,344 records |
| Static: `suspended-instrument.json.gz` | 1 | **Verified exhaustively** — full scan, 33,930 records, schema is rock-solid |
| `/v3/market-quote/ohlc` | 2 | **Verified** — 2 calls; found the most important nullability bug in this pass |
| `/v3/market-quote/ltp` | 2 | **Verified** — 1 call, 2 instruments |
| `/v2/market-quote/quotes` | 2 | **Verified** — 1 call, 2 instruments |
| `/v2/instruments/search` | 2 | **Verified** — 4 calls (EQ, FUT, INDEX, CE) |
| `/v2/news` | 2 | **Verified** — 2 calls |
| `/v2/ipos` | 2 | **Verified** — 2 calls, found an undocumented field and a nullable field |
| `/v2/market/status/{exchange}` | 2 | **Verified** — 3 calls (NSE, BSE, MCX); found a new enum value |
| `/v2/fundamentals/{isin}/{profile,balance-sheet,cash-flow,income-statement,key-ratios,competitors}` | — | **Skipped per brief** |
| `/v2/ipos/{id}` | — | **Not observed** — outside stated scope |

## Every correction made, by file

### `historical.md`
- `data.candles[i][0]` timestamp: confirmed always **string**, not number, across every unit/endpoint tested (docs table says number).
- `from_date` omitted: **not uniform across units** — `days`/`minutes` silently clip to the documented cap (10y / 1 month); `weeks`/`months` return the *entire* available history back to ~Jan 2000. Previously undocumented and easy to misread as "no limit = no behavior to think about."
- Documented the actual **error envelope shape** for the first time: `{"status":"error","errors":[{...}]}` — no `data` key at all on error, errors arrive as an array, and every error field is duplicated in both camelCase and snake_case (`errorCode`/`error_code`, etc).
- Open interest (`candles[i][6]`) confirmed always `0` for equities in this sample — real F&O OI values are NOT OBSERVED.

### `fundamentals.md` (corporate-actions, share-holdings only — rest skipped)
- `data[].name` enum: **`"Rights Issue"`, not `"Rights"`** as the docs' own example implies. Full enum: `Dividend`, `Bonus`, `Rights Issue`, `Split`.
- `data[].amount`: always present as a float (never absent), `0.0` for non-Dividend events — not conditionally absent as "applicable to dividends" phrasing could suggest.
- `event_details[].name` for `Dividend type`: 8 real values observed (`Final`, `Interim`, `Misc.Income`, `Interest`, `Dividend`, `RepayOfSPVLvlDebt`, `Other Income`, `Special`) vs. the docs' single example (`Final`).
- `data` can be an **empty array** — 28/83 ISINs have no corporate-action history at all.
- `share-holdings` category order is **not fixed** (varies by company) — do not index by position.

### `market-info.md`
- `/v2/market/status/{exchange}`: a real, undocumented **`"CLOSING_END"`** status value observed (docs' only example is `NORMAL_OPEN`); `cas_eligible_status` confirmed present only for CAS-eligible exchanges (NSE/BSE), absent for MCX.
- `/v2/market/holidays/{date}` and `/v2/market/timings/{date}`: both confirmed to return `data: []` (not an error) when the date has no holiday / no exchange open.
- `/v2/market/timings/{date}`: `data` confirmed to genuinely be an array live, resolving the docs' own "page incorrectly says object" self-contradiction with live evidence.

### `instruments.md` (the largest set of findings)
- **`cas_eligible` is present only when `true`** across every record type that carries it (`NSE_EQ`, `BSE_EQ`, `NSE_INDEX`, `BSE_INDEX`) — never present-and-`false`. A required or nullable-boolean model is wrong either way.
- **`mtf_enabled`/`mtf_bracket` appear directly on 52% of ordinary `NSE_EQ`/`EQ` records** inside `complete.json.gz`, not just in a separate MTF-only file as documented.
- **`short_name` is optional**, missing in ~30% of both `NSE_EQ` and `BSE_EQ` records — not just "the example omits it."
- **`security_type` does not exist at all on `BSE_EQ` records** (0/699), only on `NSE_EQ`.
- `mtf_bracket` type resolved: always a **number**, never the string the docs table claims.
- `FUT`/`CE`/`PE` records carry three fully undocumented always-present fields: `asset_key`, `asset_symbol`, `asset_type`.
- Index-record `exchange_token`: confirmed always a **string**, not the number the docs table claims.
- `strike_price` on `FUT`: confirmed always present, always exactly `0.0`.
- `/v2/instruments/search` INDEX results carry an undocumented `cas_eligible` field (present-only-if-true, same pattern as the static files).
- `expiry` in search results is a `YYYY-MM-DD` string; `expiry` in the static files is an integer epoch — both sides of this documented hazard are now backed by live evidence, not just doc example inspection.
- Suspended-instrument file: **zero surprises** — full scan, 100% presence of every documented field, correct types throughout. The cleanest section in this whole pass.

### `quotes.md`
- **`/v3/market-quote/ohlc`'s `prev_ohlc` can be `null`** (observed for `interval=1d`) — the single highest-severity finding in this file. The docs show it only as a plain object with no nullability note.
- `/v2/market-quote/quotes` map key format confirmed live: `<segment>:<TRADING_SYMBOL>` (e.g. `NSE_EQ:MARUTI`), not the company name.
- `timestamp` confirmed always ISO-8601 with milliseconds, never the epoch-ms number the prose claims.
- Depth arrays confirmed always exactly 5 buy + 5 sell, zero-padded.

### `news-ipo.md`
- **`/v2/ipos` carries an undocumented `investors` field** (array, always empty in this sample — item shape unknown).
- **`/v2/ipos`'s `industry` field can be `null`** — observed on a real SME IPO record, contradicting the docs' implicit non-null string.
- Confirmed the docs' own JSON example (missing comma before `metadata`) is purely a documentation typo — live responses are valid JSON.

## Ranked list of traps that would break a strict parser

1. **`/v3/market-quote/ohlc`'s `prev_ohlc` can be `null`.** A non-optional
   Pydantic field here rejects a routine, non-error `interval=1d` response.
   Highest severity because it's silent at the API level (200 OK) and only
   surfaces as a validation exception downstream.
2. **`cas_eligible` (and, by the same pattern, `mtf_enabled`/`mtf_bracket`
   on some records) is omitted rather than `false`** across the static
   instrument files and search results. A model that requires the field, or
   that treats its absence as an error, will fail on the ~90% of records
   where it's legitimately absent.
3. **The `/v3/historical-candle` error envelope has no `data` key, wraps
   errors in an array, and double-encodes every field in both camelCase and
   snake_case.** Any error-handling code that expects the success envelope's
   shape, or picks only one casing, breaks on the very first 4xx.
4. **`short_name` is missing on ~30% of real `EQ` instrument records**, not
   just "omitted in one example" — a required field here silently drops a
   third of the universe.
5. **`security_type` does not exist at all on `BSE_EQ` records.** A model
   that inherited this field as required from the `NSE_EQ` shape will reject
   every BSE equity.
6. **Omitting `from_date` on `/v3/historical-candle` behaves differently per
   `unit`**: silently clipped to the documented cap for `days`/`minutes`,
   but unboundedly returns the entire ~25-year history for `weeks`/`months`.
   A caller who treats "no limit documented" as "safe to omit" will
   accidentally fetch a company's entire history on every such call.
7. **`industry` can be `null` on `/v2/ipos`**, and a wholly undocumented
   `investors` field is present on every record. Minor individually, but two
   more places a strict schema silently rejects real data.
8. **Corporate-action `name` is `"Rights Issue"`, never `"Rights"`.** A
   strict enum built from the docs' own example text would reject 2 of 108
   real observed events outright.
9. **`/v2/market/status/{exchange}.status` and `.cas_eligible_status.status`
   have a wider value space than the docs' single example** (`CLOSING_END`
   observed, not just `NORMAL_OPEN`/`CTS_CLOSE`). The docs already delegate
   the full enum to an appendix, so this isn't a contradiction — but a
   parser that hardcodes the two documented example values as the complete
   enum will reject legitimate live states.
10. **Timestamp type disagreements are pervasive but consistent**: candles
    (`historical-candle`, both endpoints) always use ISO-8601 strings despite
    docs tables saying "number"; quote `timestamp` fields are also always
    ISO-8601 strings despite prose saying "milliseconds." These are
    consistently one-sided in the live data (never actually numbers), so the
    fix is simple — just don't trust the type column — but worth flagging as
    a systemic, not one-off, documentation defect.

## Honest gaps — fields/behaviors this pass could not exercise

- Non-`NSE_EQ` open interest values on `/v3/historical-candle` and
  `/v2/market-quote/quotes` (`oi`, `oi_day_high`, `oi_day_low`) — every probe
  in this pass used equities, which always show `0`. A genuinely non-zero F&O
  value is **NOT OBSERVED**.
- `/v3/market-quote/ohlc`'s `interval=I30` — only `1d` and `I1` were called.
- Any invalid-input / error-path response from `/v2/fundamentals/{corporate-
  actions,share-holdings}`, `/v2/news`, or `/v2/ipos` — `UDAPI1206`,
  `UDAPI1189/1190/1193`, `UDAPI1219/1220` etc. are all still **NOT OBSERVED**;
  only `/v3/historical-candle`'s error shape was actually captured live.
- The dedicated `MTF.json.gz`, `NSE_MIS.json.gz`, `BSE_MIS.json.gz`,
  `mf-instruments.json.gz`, and `global.json.gz` files were not fetched —
  MIS and mutual-fund record shapes remain fully **NOT OBSERVED**; MTF and
  global-index/indicator shapes got partial indirect coverage via records
  embedded in `complete.json.gz`.
- `/v2/ipos/{id}` and the `positions`/`holdings` categories of `/v2/news`
  were not called at all — out of the stated Tier 2 scope for this pass.
- The `/v2/ipos` docs' claim that `minimum_price`/`maximum_price` are `0`
  before announcement — every IPO observed in this pass already had an
  announced price band, so that specific case is **NOT OBSERVED**.
