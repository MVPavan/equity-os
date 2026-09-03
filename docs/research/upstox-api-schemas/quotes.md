# Upstox quote schemas

All quote maps are keyed by a dynamic instrument label. The endpoint pages do
not document response-field nullability; every field below is therefore
`UNDOCUMENTED` for presence and nullability unless explicitly noted.

**VERIFIED (Tier 2) against live responses (2026-09-03, ~19:33 IST, market
in closing auction)**, two instruments (`RELIANCE`, `MARUTI`), all three
endpoints — `scratchpad/upstox/probes/verify2/{quotes-v2-two,ohlc-v3-1d,
ohlc-v3-I1,ltp-v3-two}.json`. The single most important finding of this
section: **`prev_ohlc` on the v3 OHLC endpoint can be `null`** — see below.

## `GET /v2/market-quote/quotes`

Documentation: [Full Market Quotes](https://upstox.com/developer/api-documentation/get-full-market-quote?utm_source=equity-os)

### Request

| Name | Type | Presence | Format / limit |
|---|---|---|---|
| `instrument_key` | string | required | Comma-separated instrument keys; maximum 500 instruments per call. The field-pattern regex is delegated to the appendix. |

### Response fields

| Field | Type | Presence / nullability | Meaning |
|---|---|---|---|
| `status` | string | **VERIFIED** `success` | Typically `success`. |
| `data` | object/map | **VERIFIED**; **CORRECTED — the map key is `<segment>:<TRADING_SYMBOL>`, not the company name** (e.g. `NSE_EQ:MARUTI`, `NSE_EQ:RELIANCE`), matching the doc's `NSE_EQ:NHPC` example exactly | Dynamic key is the returned instrument label (the example uses `NSE_EQ:NHPC`, with a colon). |
| `data[<instrument>]` | object | **VERIFIED** | Full quote. |
| `data[<instrument>].ohlc` | object | **VERIFIED** always present, all 4 sub-fields present as numbers | `open`, `high`, `low`, `close`: numbers, session prices. |
| `data[<instrument>].depth` | object | **VERIFIED** always present | Top-five depth. |
| `...depth.buy`, `...depth.sell` | array of objects | **VERIFIED — exactly 5 entries each, always**, zero-padded with `{quantity:0, price:0.0, orders:0}` rows when fewer than 5 real price levels exist (both live quotes had only 1 real level on one side) | Bids and asks. |
| `...depth.{buy,sell}[].quantity` | integer | **VERIFIED** always present | Quantity. |
| `...depth.{buy,sell}[].price` | number | **VERIFIED** always present, always float | Price. |
| `...depth.{buy,sell}[].orders` | integer | **VERIFIED** always present | Order count. |
| `data[<instrument>].timestamp` | string | **CORRECTED (now backed by live evidence, not just the doc's own example): always ISO-8601 with milliseconds and `+05:30` offset** (e.g. `"2026-09-03T19:33:24.324+05:30"`), never a millisecond epoch number despite the prose | Feed-update time, documented as milliseconds despite the example being ISO-8601. |
| `...instrument_token` | string | **VERIFIED** always present, pipe-separated | Instrument key. |
| `...symbol` | string | **VERIFIED** always present, matches the trading symbol half of the map key | Trading symbol. |
| `...last_price` | number | **VERIFIED** always present | Last traded price. |
| `...volume` | integer | **VERIFIED** always present | Today's volume. |
| `...average_price` | number | **VERIFIED** always present | Average price. |
| `...oi` | number | **VERIFIED** always present; `0.0` for both equities tested (no F&O instrument tested here) | Outstanding contracts, only F&O. |
| `...net_change` | number | **VERIFIED** always present, can be negative | Absolute change from prior close. |
| `...total_buy_quantity`, `...total_sell_quantity` | number | **VERIFIED** always present, always float (e.g. `0.0`, `121.0`) even though the values are conceptually integer share counts | Bid/ask quantity. |
| `...lower_circuit_limit`, `...upper_circuit_limit` | number | **VERIFIED** always present, float | Circuit limits. |
| `...last_trade_time` | string | **VERIFIED** always present, a numeric string of epoch milliseconds (e.g. `"1788431263000"`) | Milliseconds at last trade. |
| `...oi_day_high`, `...oi_day_low` | number | **VERIFIED** always present; `0.0` for both equities tested | OI day high/low. |

### Documentation example response (copied)

```json
{
  "status": "success",
  "data": {
    "NSE_EQ:NHPC": {
      "ohlc": { "open": 53.4, "high": 53.8, "low": 51.75, "close": 52.05 },
      "depth": {
        "buy": [
          { "quantity": 6917, "price": 52.05, "orders": 20 },
          { "quantity": 0, "price": 0, "orders": 0 }, { "quantity": 0, "price": 0, "orders": 0 },
          { "quantity": 0, "price": 0, "orders": 0 }, { "quantity": 0, "price": 0, "orders": 0 }
        ],
        "sell": [
          { "quantity": 0, "price": 0, "orders": 0 }, { "quantity": 0, "price": 0, "orders": 0 },
          { "quantity": 0, "price": 0, "orders": 0 }, { "quantity": 0, "price": 0, "orders": 0 },
          { "quantity": 0, "price": 0, "orders": 0 }
        ]
      },
      "timestamp": "2023-10-19T05:21:51.099+05:30",
      "instrument_token": "NSE_EQ|INE848E01016",
      "symbol": "NHPC",
      "last_price": 52.04999923706055,
      "volume": 24123697,
      "average_price": 52.56,
      "oi": 0,
      "net_change": -1.0500000000000043,
      "total_buy_quantity": 6917,
      "total_sell_quantity": 0,
      "lower_circuit_limit": 42.5,
      "upper_circuit_limit": 63.7,
      "last_trade_time": "1697624972130",
      "oi_day_high": 0,
      "oi_day_low": 0
    }
  }
}
```

### Errors

`UDAPI1087` — one of `symbol` or `instrument_key` is invalid;
`UDAPI100042` — maximum 500 instrument keys exceeded.

### Strict-parser hazards

The returned map key uses `:` in the example while `instrument_token` uses
`|` — **VERIFIED live**, both symbols observed. `timestamp` is a string in
ISO format although its description says milliseconds — **VERIFIED live**;
`last_trade_time` is a numeric string — **VERIFIED live**. Depth has fixed
five-item examples, but a five-item maximum rather than exact arity is not
stated — **VERIFIED: always exactly 5**, zero-padded, in both live quotes.

## `GET /v3/market-quote/ohlc`

Documentation: [OHLC Quotes V3](https://upstox.com/developer/api-documentation/get-market-quote-ohlc-v3?utm_source=equity-os)

**VERIFIED** with 2 live calls against `NSE_EQ|INE002A01018` (RELIANCE):
`interval=1d` and `interval=I1` (`ohlc-v3-1d.json`, `ohlc-v3-I1.json`).

### Request

| Name | Type | Presence | Format / values / limit |
|---|---|---|---|
| `instrument_key` | string | required | Comma-separated instrument keys; maximum is documented by the error as a limit-exceeded condition, but the numeric limit is not stated on this page. |
| `interval` | string | required | `1d`, `I1`, or `I30` (`1d` daily, `I1` one-minute, `I30` 30-minute). `1d` and `I1` **VERIFIED**; `I30` **NOT OBSERVED** (not called). |

### Response fields

| Field | Type | Presence / nullability | Meaning |
|---|---|---|---|
| `status` | string | **VERIFIED** `success` | Typically `success`. |
| `data` | object/map | **VERIFIED**, keyed `<segment>:<TRADING_SYMBOL>` (`NSE_EQ:RELIANCE`), same colon convention as v2 quotes | Dynamic instrument key. |
| `data[<instrument>].last_price` | number | **VERIFIED** always present | Last traded price. |
| `data[<instrument>].instrument_token` | string | **VERIFIED** always present | Instrument key. |
| `data[<instrument>].prev_ohlc` | object | **CORRECTED — MAJOR FINDING: this field can be `null`.** With `interval=1d`, `prev_ohlc` was `null` (not an object) while `live_ohlc` was a normal populated object. With `interval=I1`, `prev_ohlc` was a normal object. The docs give no nullability note at all — a Pydantic model that requires `prev_ohlc: OhlcCandle` (non-optional) will reject a real, common `1d` response. | Prior candle. |
| `data[<instrument>].live_ohlc` | object | **VERIFIED** present as a populated object in both calls tested | Current candle. |
| `...{prev_ohlc,live_ohlc}.{open,high,low,close,volume}` | number | **VERIFIED** when the parent object is present; `volume` observed as `int` (including `0` for a single-minute window with no trades in `prev_ohlc` under `I1`) | Prices and volume. |
| `...{prev_ohlc,live_ohlc}.ts` | number | **VERIFIED** epoch ms, when the parent object is present | Candle start epoch milliseconds. |

### Documentation example response (copied)

```json
{
  "status": "success",
  "data": {
    "NSE_FO:NIFTY2543021600PE": {
      "last_price": 303.9,
      "instrument_token": "NSE_FO|51834",
      "prev_ohlc": { "open": 303.9, "high": 304.3, "low": 303.85, "close": 304.3, "volume": 300, "ts": 1744019880000 },
      "live_ohlc": { "open": 304.45, "high": 304.45, "low": 302.75, "close": 303.9, "volume": 2250, "ts": 1744019940000 }
    }
  }
}
```

### Errors

`UDAPI1009` symbol is required; `UDAPI1011` symbol has invalid format;
`UDAPI1028` invalid interval; `UDAPI1027` interval is required;
`UDAPI1087` invalid instrument key; `UDAPI100043` maximum instrument-key limit
exceeded.

The error table says `symbol` for the first two codes although the request
parameter is `instrument_key`; this is an intra-page legacy-name conflict.

## `GET /v3/market-quote/ltp`

Documentation: [LTP Quotes V3](https://upstox.com/developer/api-documentation/ltp-v3?utm_source=equity-os)

**VERIFIED** with 1 live call, two instruments in a single comma-separated
request (`NSE_EQ|INE002A01018`, `NSE_EQ|INE585B01010` → `ltp-v3-two.json`).

### Request

`instrument_key` is a required string query parameter containing a
comma-separated list of instrument keys. The endpoint page documents no
numeric maximum; the error table names a maximum-limit error without a number.
**VERIFIED** a 2-key comma-separated request returns both instruments as
separate map entries.

### Response fields

| Field | Type | Presence / nullability | Meaning |
|---|---|---|---|
| `status` | string | **VERIFIED** `success` | Typically `success`. |
| `data` | object/map | **VERIFIED**, keyed `<segment>:<TRADING_SYMBOL>`, one entry per requested instrument | Dynamic instrument key. |
| `data[<instrument>].last_price` | number | **VERIFIED** always present | Last traded price. |
| `data[<instrument>].instrument_token` | string | **VERIFIED** always present | Instrument key. |
| `data[<instrument>].ltq` | number | **VERIFIED** always present, always `int` in both records tested | Last traded quantity. |
| `data[<instrument>].volume` | number | **VERIFIED** always present, always `int` | Current-day volume. |
| `data[<instrument>].cp` | number | **VERIFIED** always present, always `float` | Previous-day closing price. |

### Documentation example response (copied)

```json
{
  "status": "success",
  "data": {
    "NSE_FO:NIFTY2543021600PE": {
      "last_price": 303.9,
      "instrument_token": "NSE_FO|51834",
      "ltq": 75,
      "volume": 170325,
      "cp": 29.0
    }
  }
}
```

### Errors

`UDAPI1009` instrument_key is required; `UDAPI1011` instrument_key has invalid
format; `UDAPI1087` invalid instrument key; `UDAPI100043` maximum instrument-key
limit exceeded.

### Strict-parser hazards

All three quote endpoints use dynamic-key maps. Quote map keys shown in the
examples use `:` while instrument tokens use `|`; do not assume the map key is
the canonical instrument key without retaining the token field. **VERIFIED**
across all three endpoints in this pass.

**Ranked, cross-endpoint: the single biggest hazard found in this file is
`/v3/market-quote/ohlc`'s `prev_ohlc` going `null` on `interval=1d`** (see
above) — every other field in all three quote endpoints was present and
typed exactly as documented in every live call made.
