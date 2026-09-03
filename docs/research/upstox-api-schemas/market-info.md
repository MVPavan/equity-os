# Upstox market-information schemas

`status` is documented as a string, typically `success`; presence and
nullability of response fields are `UNDOCUMENTED` unless stated otherwise.
All timestamps below are Unix milliseconds. The documentation does not state a
timezone for those epoch values.

**VERIFIED against live responses (2026-09-03)** — all five endpoints in this
file were live-called. See `scratchpad/upstox/probes/sanity-market-holidays.json`
(earlier run) and `scratchpad/upstox/probes/verify2/{fii,dii,holidays,timings,status}-*.json`
(this pass). `VERIFICATION.md` has the full call list.

## `GET /v2/market/fii`

Documentation: [FII Activity Data](https://upstox.com/developer/api-documentation/get-fii-data?utm_source=equity-os)

### Request

| Name | Type | Presence | Format / values / limits |
|---|---|---|---|
| `data_type` | string | required | One value or a comma-separated list of: `NSE_FO|INDEX_FUTURES`, `NSE_FO|STOCK_FUTURES`, `NSE_FO|INDEX_OPTIONS`, `NSE_FO|STOCK_OPTIONS`, `NSE_EQ|CASH`. The curl example repeats the query key; Python uses repeated pairs. |
| `interval` | string | required | `1D` daily or `1M` monthly. |
| `from` | string | optional; nullability UNDOCUMENTED | Start date, `YYYY-MM-DD`. |

Availability starts 1 April 2026. `1D` returns up to 30 trading days per
request; `1M` returns up to 12 months per request.

### Response fields

**VERIFIED** with 3 live calls: `NSE_EQ|CASH`/`1D`, a comma-separated
multi-value `data_type` (`NSE_FO|INDEX_FUTURES,NSE_FO|STOCK_FUTURES`), and
`NSE_FO|INDEX_OPTIONS`/`1M` (`fii-nse_eq_cash-1D.json`, `fii-multi-1D.json`,
`fii-index_options-1M.json`). Every field below matched the documented type
in all 3 responses, with zero deviation.

| Field | Type | Presence / nullability | Meaning |
|---|---|---|---|
| `status` | string | **VERIFIED** `success` | Outcome. |
| `data` | object/map | **VERIFIED**; a multi-value request returns one key per requested `data_type`, each with its own array (confirmed: both requested segments present in the multi-value response, 30 rows apiece) | Dynamic key is each requested `data_type`. |
| `data[<data_type>]` | array | **VERIFIED** | FII records for that segment. |
| `data[<data_type>][].time_stamp` | integer | **VERIFIED** always present, always int | Unix milliseconds. |
| `...buy_amount`, `...sell_amount` | number | **VERIFIED** always present, always float | Buy/sell value in INR. |
| `...buy_contracts`, `...sell_contracts` | integer | **VERIFIED** always present, always int | Contracts bought/sold. |
| `...oi_contracts` | integer | **VERIFIED** always present, always int | Open interest contracts. |
| `...oi_amount` | number | **VERIFIED** always present, always float | Open-interest value in INR. |
| `...total_long_contracts`, `...total_short_contracts` | integer | **VERIFIED** always present, always int | Total long/short contracts. |
| `...total_call_long_contracts`, `...total_put_long_contracts` | integer | **VERIFIED** always present, always int | Long call/put contracts. |
| `...total_call_short_contracts`, `...total_put_short_contracts` | integer | **VERIFIED** always present, always int | Short call/put contracts. |

`NSE_EQ|CASH` — listed by the docs as one of FII's own `data_type` options —
**VERIFIED working** for `/v2/market/fii` too (not just `/v2/market/dii`).

### Documentation example response (copied)

```json
{
  "status": "success",
  "data": {
    "NSE_FO|STOCK_FUTURES": [
      { "time_stamp": 1777487400000, "buy_amount": 23109.75, "sell_amount": 24642.52, "buy_contracts": 353981, "sell_contracts": 384079, "oi_contracts": 7245154, "oi_amount": 452650.0, "total_long_contracts": 4021980, "total_short_contracts": 3223174, "total_call_long_contracts": 0, "total_put_long_contracts": 0, "total_call_short_contracts": 0, "total_put_short_contracts": 0 },
      { "time_stamp": 1777401000000, "buy_amount": 21593.35, "sell_amount": 21252.58, "buy_contracts": 327164, "sell_contracts": 318686, "oi_contracts": 7237618, "oi_amount": 456065.1, "total_long_contracts": 4033261, "total_short_contracts": 3204357, "total_call_long_contracts": 0, "total_put_long_contracts": 0, "total_call_short_contracts": 0, "total_put_short_contracts": 0 }
    ],
    "NSE_FO|INDEX_OPTIONS": [
      { "time_stamp": 1777487400000, "buy_amount": 797967.36, "sell_amount": 794438.53, "buy_contracts": 5094129, "sell_contracts": 5072195, "oi_contracts": 1995796, "oi_amount": 313760.14, "total_long_contracts": 0, "total_short_contracts": 0, "total_call_long_contracts": 351772, "total_put_long_contracts": 715640, "total_call_short_contracts": 572110, "total_put_short_contracts": 356275 },
      { "time_stamp": 1777401000000, "buy_amount": 579943.55, "sell_amount": 583822.61, "buy_contracts": 3659192, "sell_contracts": 3683793, "oi_contracts": 1776287, "oi_amount": 281482.39, "total_long_contracts": 0, "total_short_contracts": 0, "total_call_long_contracts": 293574, "total_put_long_contracts": 653116, "total_call_short_contracts": 509632, "total_put_short_contracts": 319965 }
    ]
  }
}
```

### Errors

`UDAPI1198` invalid `data_type`; `UDAPI1199` invalid `interval`;
`UDAPI1200` invalid `from` date format.

## `GET /v2/market/dii`

Documentation: [DII Activity Data](https://upstox.com/developer/api-documentation/get-dii-data?utm_source=equity-os)

### Request

| Name | Type | Presence | Format / values / limits |
|---|---|---|---|
| `data_type` | string | required | Only `NSE_EQ|CASH`. |
| `interval` | string | required | `1D` or `1M`. |
| `from` | string | optional; nullability UNDOCUMENTED | `YYYY-MM-DD`. |

Availability starts 1 April 2026. Limits are up to 30 trading days for `1D`
and up to 12 months for `1M`.

### Response fields

The response is the same dynamic-key envelope and record schema as FII above;
the only accepted map key is `data["NSE_EQ|CASH"]`. All twelve record fields
are documented with the same types and units.

**VERIFIED** with 2 live calls, `NSE_EQ|CASH`/`1D` and `NSE_EQ|CASH`/`1M`
(`dii-nse_eq_cash-1D.json`, `dii-nse_eq_cash-1M.json`). All twelve fields
matched documented types exactly, same as FII above — no deviation found.

### Documentation example response (copied)

```json
{
  "status": "success",
  "data": {
    "NSE_EQ|CASH": [
      {
        "time_stamp": 1746633600000,
        "buy_amount": 8523456789.0,
        "sell_amount": 7234567890.5,
        "buy_contracts": 0,
        "sell_contracts": 0,
        "oi_contracts": 0,
        "oi_amount": 0.0,
        "total_long_contracts": 0,
        "total_short_contracts": 0,
        "total_call_long_contracts": 0,
        "total_put_long_contracts": 0,
        "total_call_short_contracts": 0,
        "total_put_short_contracts": 0
      }
    ]
  }
}
```

### Errors

`UDAPI1198` invalid `data_type`; `UDAPI1199` invalid `interval`;
`UDAPI1200` invalid `from` date format.

## `GET /v2/market/holidays[/{date}]`

Documentation: [Market Holidays](https://upstox.com/developer/api-documentation/get-market-holidays?utm_source=equity-os)

### Request

| Name | Type | Presence | Format / values |
|---|---|---|---|
| `date` (path) | string | optional; nullability UNDOCUMENTED | `YYYY-MM-DD`; omit it for the current-year list. |

No query parameter or maximum list size is documented.

**VERIFIED** with 3 live calls: no `date` (`holidays-no-date.json`, 22
records for the current year), `date` = an actual holiday
(`holidays-with-date-holiday.json`, `2026-01-26` Republic Day), and `date` =
an ordinary trading day (`holidays-with-date-trading-day.json`,
`2026-09-03`).

### Response fields

| Field | Type | Presence / nullability | Meaning |
|---|---|---|---|
| `status` | string | **VERIFIED** `success` | Outcome. |
| `data` | array | **VERIFIED**; **CONFIRMED UNDOCUMENTED BEHAVIOR**: `data: []` (empty array, not an error) when `date` names a day that is not a holiday — observed for `2026-09-03` | Holiday records. |
| `data[].date` | string | **VERIFIED** `YYYY-MM-DD` | `YYYY-MM-DD`. |
| `data[].description` | string | **VERIFIED** always present | Holiday description. |
| `data[].holiday_type` | string | **VERIFIED enum, all 3 values and no more**, across 22 current-year holidays: `TRADING_HOLIDAY` (16), `SETTLEMENT_HOLIDAY` (4), `SPECIAL_TIMING` (2) | `SETTLEMENT_HOLIDAY`, `TRADING_HOLIDAY`, `SPECIAL_TIMING`. |
| `data[].closed_exchanges` | array of strings | **VERIFIED** always present, sometimes `[]` (e.g. `SPECIAL_TIMING` days, where nothing is fully closed) | Closed exchange codes. |
| `data[].open_exchanges` | array of objects | **VERIFIED** always present, sometimes `[]` (e.g. Republic Day, when every exchange is fully closed) | Open exchanges and times. |
| `data[].open_exchanges[].exchange` | string | **VERIFIED** | Exchange code. |
| `data[].open_exchanges[].start_time` | number | **VERIFIED** epoch ms | Epoch milliseconds. |
| `data[].open_exchanges[].end_time` | number | **VERIFIED** epoch ms | Epoch milliseconds. |

### Documentation example response (copied)

```json
{
  "status": "success",
  "data": [
    { "date": "2024-01-01", "description": "New Year Day", "holiday_type": "TRADING_HOLIDAY", "closed_exchanges": [], "open_exchanges": [
      { "exchange": "MCX", "start_time": 1704079800000, "end_time": 1704108600000 }, { "exchange": "NSE", "start_time": 1704080700000, "end_time": 1704103200000 }, { "exchange": "NFO", "start_time": 1704080700000, "end_time": 1704103200000 }, { "exchange": "CDS", "start_time": 1704079800000, "end_time": 1704108600000 }, { "exchange": "BSE", "start_time": 1704080700000, "end_time": 1704103200000 }, { "exchange": "BCD", "start_time": 1704079800000, "end_time": 1704108600000 }, { "exchange": "BFO", "start_time": 1704080700000, "end_time": 1704103200000 }
    ] },
    { "date": "2024-01-20", "description": "Special DR Trading", "holiday_type": "TRADING_HOLIDAY", "closed_exchanges": ["MCX", "CDS", "BCD"], "open_exchanges": [
      { "exchange": "NSE", "start_time": 1705722300000, "end_time": 1705734000000 }, { "exchange": "NFO", "start_time": 1705722300000, "end_time": 1705734000000 }, { "exchange": "BSE", "start_time": 1705722300000, "end_time": 1705734000000 }, { "exchange": "BFO", "start_time": 1705722300000, "end_time": 1705734000000 }
    ] },
    { "date": "2024-01-26", "description": "Republic Day", "holiday_type": "TRADING_HOLIDAY", "closed_exchanges": ["NFO", "CDS", "BSE", "BCD", "MCX", "NSE", "BFO"], "open_exchanges": [] }
  ]
}
```

The docs list no error-code table for this endpoint.

## `GET /v2/market/timings/{date}`

Documentation: [Market Timings](https://upstox.com/developer/api-documentation/get-market-timings?utm_source=equity-os)

### Request

`date` is a required string path parameter in `YYYY-MM-DD` format. No query
parameter or list limit is documented.

**VERIFIED** with 2 live calls: a trading day (`timings-trading-day.json`,
`2026-09-03`, 7 exchange rows) and a full-closure holiday
(`timings-holiday.json`, `2026-01-26` Republic Day).

### Response fields

| Field | Type | Presence / nullability | Meaning |
|---|---|---|---|
| `status` | string | **VERIFIED** `success` | Outcome. |
| `data` | array (page incorrectly says object) | **CORRECTED (now VERIFIED, not just inferred)**: confirmed a JSON array in both live calls, matching the existing "page incorrectly says object" note. **UNDOCUMENTED BEHAVIOR**: `data: []` on a day with no exchange open at all (Republic Day) — same empty-array-on-holiday pattern as `/v2/market/holidays/{date}`. | Timing record list. |
| `data[].exchange` | string | **VERIFIED** | Exchange code. |
| `data[].start_time` | number | **VERIFIED** epoch ms | Epoch milliseconds. |
| `data[].end_time` | number | **VERIFIED** epoch ms | Epoch milliseconds. |

### Documentation example response (copied)

```json
{
  "status": "success",
  "data": [
    { "exchange": "MCX", "start_time": 1704079800000, "end_time": 1704108600000 },
    { "exchange": "NSE", "start_time": 1704080700000, "end_time": 1704103200000 },
    { "exchange": "NFO", "start_time": 1704080700000, "end_time": 1704103200000 },
    { "exchange": "CDS", "start_time": 1704079800000, "end_time": 1704108600000 },
    { "exchange": "BSE", "start_time": 1704080700000, "end_time": 1704103200000 },
    { "exchange": "BCD", "start_time": 1704079800000, "end_time": 1704108600000 },
    { "exchange": "BFO", "start_time": 1704080700000, "end_time": 1704103200000 }
  ]
}
```

### Errors

`UDAPI1088` — Invalid date.

## `GET /v2/market/status/{exchange}`

Documentation: [Exchange Status](https://upstox.com/developer/api-documentation/get-market-status?utm_source=equity-os)

### Request

`exchange` is a required string path parameter. Valid exchange values are
delegated to the Exchange Appendix; the page does not enumerate them.

**VERIFIED** with 3 live calls: `NSE`, `BSE`, `MCX`
(`status-NSE.json`, `status-BSE.json`, `status-MCX.json`).

### Response fields

| Field | Type | Presence / nullability | Meaning |
|---|---|---|---|
| `status` | string | **VERIFIED** `success` | Outcome. |
| `data` | object | **VERIFIED** | Exchange status. |
| `data.exchange` | string | **VERIFIED** | Exchange code. |
| `data.status` | string | **CORRECTED: a new, undocumented enum value was observed.** Both `NSE` and `BSE` returned `"CLOSING_END"` at call time (19:33 IST) — not `NORMAL_OPEN` as in the docs' only example, and not in any status vocabulary the docs enumerate (they explicitly delegate the full list to an appendix, so this isn't a contradiction, but it is proof the real value space is wider than the one example shown). `MCX` returned `"NORMAL_OPEN"` at the same instant, since MCX trades later into the evening. | Current status; valid members are delegated to the Market Status Appendix. |
| `data.last_updated` | number | **VERIFIED** epoch ms | Epoch milliseconds. |
| `data.cas_eligible_status` | object | **VERIFIED optional, exactly as documented**: present for `NSE` and `BSE` (both CAS-eligible), **absent** for `MCX` (not CAS-eligible) — clean confirmation of "present only for CAS-eligible segments." | Present only for CAS-eligible segments. |
| `data.cas_eligible_status.status` | string | **VERIFIED**; observed `"CLOSING_END"` for both NSE and BSE at call time — again a value outside the docs' one example (`CTS_CLOSE`) | CAS status; members delegated to appendix. |
| `data.cas_eligible_status.last_updated` | number | **VERIFIED** epoch ms | Epoch milliseconds. |

### Documentation example response (copied)

```json
{
  "status": "success",
  "data": {
    "exchange": "NSE",
    "status": "NORMAL_OPEN",
    "last_updated": 1705549500000,
    "cas_eligible_status": { "status": "CTS_CLOSE", "last_updated": 1705570500000 }
  }
}
```

### Errors

`UDAPI1089` — Invalid exchange.

### Strict-parser hazards

Holiday/timing `data` is an array even though the timings description calls it
an object. Status values and CAS values are not enumerated on the endpoint
page; do not invent enum members from a single example.
