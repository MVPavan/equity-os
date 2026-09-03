# Upstox historical-candle schemas

Scope: the two v3 historical-data endpoints in the acquisition surface. Types
and presence below are documentation claims; `UNDOCUMENTED` means Upstox does
not state the fact. Authentication headers are omitted from the field tables.

**VERIFIED against live responses** (2026-09-03): ~15 live calls against
`NSE_EQ|INE002A01018` (Reliance) plus the 4 split/bonus-adjustment probes and
the decade-boundary probes already on disk in `scratchpad/upstox/probes/`
(`p9a-inclusive-check.json`, `p9c-decade-span.json`,
`p9c-exactly-decade.json`, `candle-*.json`) and new probes in
`scratchpad/upstox/probes/verify2/` (`historical-*.json`, `intraday-*.json`).
See `VERIFICATION.md` for the full list.

## `GET /v3/historical-candle/{instrument_key}/{unit}/{interval}/{to_date}[/{from_date}]`

Documentation: [Historical Candle Data V3](https://upstox.com/developer/api-documentation/v3/get-historical-candle-data?utm_source=equity-os)

### Request

Path parameters:

| Name | JSON/type | Presence | Format / allowed values / limits |
|---|---|---|---|
| `instrument_key` | string | required | Financial-instrument identifier; URL-encode `|` in a path segment. Exact regex is delegated to the Field Pattern Appendix. |
| `unit` | string | required | `minutes`, `hours`, `days`, `weeks`, `months`. |
| `interval` | string | required | Minutes: `1`–`300`; hours: `1`–`5`; days/weeks/months: `1`. |
| `to_date` | string | required | Inclusive ending date, `YYYY-MM-DD`. |
| `from_date` | string | optional; nullability UNDOCUMENTED | Starting date, `YYYY-MM-DD`; must not be after `to_date`. |

Documented retrieval limits:

| Unit | Availability | Maximum retrieval window |
|---|---|---|
| `minutes` | January 2022 onward | 1 month for intervals 1–15; 1 quarter for intervals greater than 15, up to `to_date` |
| `hours` | January 2022 onward | 1 quarter leading up to `to_date` |
| `days` | January 2000 onward | 1 decade leading up to `to_date` |
| `weeks` | January 2000 onward | no limit documented |
| `months` | January 2000 onward | no limit documented |

**CORRECTED — `from_date` omitted has different live behavior per unit, and
the docs' "no limit" claim for weeks/months is misleading.** Verified against
`NSE_EQ|INE002A01018` on 2026-09-03 (`historical-days-nofrom.json`,
`historical-minutes-nofrom.json`, `historical-weeks-nofrom.json`,
`historical-months-nofrom.json` in `scratchpad/upstox/probes/verify2/`):

- `days`, `from_date` omitted → **silently clipped to exactly the documented
  decade cap**: 2478 rows, `2016-09-01` .. `2026-09-01`. Same row count as the
  explicit `days/1/2026-09-01/2016-09-01` call — omission is not an error and
  is not unlimited, it silently applies the max window.
- `minutes/1`, `from_date` omitted → clipped to **exactly one month**: 8250
  rows, `2026-08-03` .. `2026-09-01`.
- `weeks/1`, `from_date` omitted → returned **the entire available history**,
  1392 rows back to `2000-01-03`. Not clipped to any window — "no limit
  documented" is accurate here, but only because omitting `from_date` reaches
  all the way to the January 2000 availability floor.
- `months/1`, `from_date` omitted → same pattern, 321 rows back to
  `2000-01-01`.

A strict client that treats "no limit documented" as "no need to think about
`from_date`" will silently fetch a company's entire 25-year history on every
`weeks`/`months` call with no `from_date` — worth flagging as a footgun even
though it is not a schema-shape defect.

The docs do not document a maximum number of returned rows for `weeks`/`months`.

### Response

Envelope:

| Field | JSON/type | Presence / nullability | Meaning |
|---|---|---|---|
| `status` | string | **VERIFIED**: always `success` in ~15 live calls; error responses use a different top-level shape entirely (see Documented errors below) | Typically `success`; the page's response table says possible outcome values are `success` and `error`. |
| `data` | object | **VERIFIED** present in every successful response | Candle container. |
| `data.candles` | array of arrays | **VERIFIED**; observed empty `[]` never occurred in this sample (all probed ranges had trading days), so an empty result is **NOT OBSERVED** | Each candle is a positional array. |
| `data.candles[i][0]` | **CORRECTED: docs table says number, actual is always string** | **VERIFIED** always present, always ISO-8601 with `+05:30` offset (e.g. `"2026-09-03T15:29:00+05:30"`) across `days`/`weeks`/`months`/`minutes`/`hours` and both endpoints | Candle-start timestamp. |
| `data.candles[i][1]` | number | **VERIFIED** always present | Open price. |
| `data.candles[i][2]` | number | **VERIFIED** always present | High price. |
| `data.candles[i][3]` | number | **VERIFIED** always present | Low price. |
| `data.candles[i][4]` | number | **VERIFIED** always present | Close price. |
| `data.candles[i][5]` | integer in every observed row | **VERIFIED** always present; observed `0` for a same-minute intraday candle with no trades (`intraday-minutes-1.json`, last minute of the day) — zero is a valid value, not evidence of nullability | Volume. |
| `data.candles[i][6]` | integer, **always `0` in every equity candle observed** | **VERIFIED** always present, but only ever `0` — this dataset is all `NSE_EQ` equities, which have no open interest; a non-`EQ`/F&O instrument's OI value is **NOT OBSERVED** | Open interest. |

The website's prose labels these as `data.candle[0]` through `data.candle[6]`
(singular), while the envelope uses `data.candles`. The actual shape is the
7-element positional array shown below. The docs do not state row ordering;
the verified integration fact is most-recent-first. Do not model candles as
objects. The timestamp type is a direct documentation disagreement: the
example is a string, while the field table calls index 0 a number. The verified
contract is the ISO-8601 string shown in the example.

### Documentation example response (copied)

```json
{
  "status": "success",
  "data": {
    "candles": [
      [
        "2025-01-01T00:00:00+05:30",
        53.1,
        53.95,
        51.6,
        52.05,
        235519861,
        0
      ],
      [
        "2025-02-01T00:00:00+05:30",
        50.35,
        56.85,
        49.35,
        52.8,
        1004998611,
        0
      ]
    ]
  }
}
```

### Documented errors

The page documents a generic `4XX` response and these error codes:

| Code | Documentation description |
|---|---|
| `UDAPI1021` | Instrument key is of invalid format. |
| `UDAPI1022` | `to_date` is required. |
| `UDAPI100011` | Invalid instrument key. **VERIFIED** — a bad instrument key on `/days/1/2026-08-31` → HTTP 400, `errorCode: "UDAPI100011"`, message `"Invalid Instrument key"` (`historical-badkey.json`). |
| `UDAPI1015` | `to_date` must be greater than or equal to `from_date`; date must be valid `yyyy-mm-dd`. |
| `UDAPI1146` | Invalid unit. |
| `UDAPI1147` | Invalid interval. |
| `UDAPI1148` | Invalid date range. **VERIFIED** twice: (1) `days/1` over ~16.7 years → HTTP 400 `UDAPI1148` (`p9c-decade-span.json`); (2) `minutes/1` over ~8 months, `2025-01-01`..`2026-08-31` → HTTP 400 `UDAPI1148` (`historical-minutes1-toolong.json`). Exactly 10 years on `days/1` → HTTP 200, full untruncated 2478-row series, not an error (`p9c-exactly-decade.json`). |

**UNDOCUMENTED FIELD — error envelope shape.** The docs list error *codes* but
never show the error response body. The live shape (identical in both error
probes above) is:

```json
{
  "status": "error",
  "errors": [
    {
      "errorCode": "UDAPI1148",
      "message": "Invalid date range",
      "propertyPath": null,
      "invalidValue": null,
      "error_code": "UDAPI1148",
      "property_path": null,
      "invalid_value": null
    }
  ]
}
```

Three things a strict parser must know and the docs state none of them:
there is **no `data` key at all** on an error response (only `status` and
`errors`); errors arrive as an **array**, not a single object; and every
field is duplicated under **both camelCase and snake_case** keys carrying
the same value (`errorCode`/`error_code`, `propertyPath`/`property_path`,
`invalidValue`/`invalid_value`). This was observed on `/v3/historical-candle`
only — treat it as likely but **NOT OBSERVED** for other endpoints in this
inventory (fundamentals, market, quotes, instruments, news, ipos) since no
error response was captured from any of them in this pass.

### Strict-parser hazards

- Seven positional values, with no named fields or documented arity declaration.
- **CORRECTED**: timestamp is *always* a string in live data (docs table says
  number) — verified across every unit tested (`days`, `weeks`, `months`,
  `minutes`, `hours`), not just the doc's own example.
- Timestamp carries the `+05:30` offset.
- `to_date` precedes `from_date` in the path and is inclusive (**VERIFIED**,
  `p9a-inclusive-check.json`).
- `UDAPI1148` covers the unit-specific range caps; the exact server rule is not
  further specified beyond the table above.
- **CORRECTED**: omitting `from_date` is not "unbounded" for every unit — see
  the from_date-omitted findings above. `days`/`minutes` silently clip to the
  documented cap; `weeks`/`months` return the full ~2000-onward history.
- **UNDOCUMENTED**: the error envelope (see above) has no `data` key, wraps
  errors in an array, and double-encodes every error field in both
  camelCase and snake_case.

## `GET /v3/historical-candle/intraday/{instrument_key}/{unit}/{interval}`

Documentation: [Intraday Candle Data V3](https://upstox.com/developer/api-documentation/v3/get-intra-day-candle-data?utm_source=equity-os)

### Request

| Name | JSON/type | Presence | Format / allowed values / limits |
|---|---|---|---|
| `instrument_key` | string | required | Financial-instrument identifier; URL-encode `|` in a path segment. Exact regex is delegated to the Field Pattern Appendix. |
| `unit` | string | required | `minutes`, `hours`, `days` according to the endpoint's request table. |
| `interval` | string | required | Minutes: `1`–`300`; hours: `1`–`5`; days: `1`. |

The endpoint returns current-trading-day data. No query parameters, default,
date-range limit, or maximum row count is documented.

**VERIFIED live** against `NSE_EQ|INE002A01018` on a trading day
(2026-09-03, Thursday) for `minutes/1` (375 rows, full trading session),
`minutes/30` (13 rows), and `hours/1` (7 rows) — `intraday-minutes-1.json`,
`intraday-minutes-30.json`, `intraday-hours-1.json` in
`scratchpad/upstox/probes/verify2/`.

### Response

The envelope and positional candle members are the same as the historical
endpoint:

| Field | JSON/type | Presence / nullability | Meaning |
|---|---|---|---|
| `status` | string | **VERIFIED** `success` in all 3 live calls | Typically `success`; the page lists `success` and `error` as response outcomes. |
| `data` | object | **VERIFIED** present | Candle container. |
| `data.candles` | array of arrays | **VERIFIED** present, non-empty on a trading day | Positional candles. |
| `data.candles[i][0]` | **CORRECTED: docs table says number, actual is always string** | **VERIFIED** ISO-8601 with `+05:30`, e.g. `"2026-09-03T09:15:00+05:30"` | Candle-start timestamp. |
| `data.candles[i][1]` | number | **VERIFIED** | Open. |
| `data.candles[i][2]` | number | **VERIFIED** | High. |
| `data.candles[i][3]` | number | **VERIFIED** | Low. |
| `data.candles[i][4]` | number | **VERIFIED** | Close. |
| `data.candles[i][5]` | integer in every observed row | **VERIFIED**; observed `0` for the final minute-candle of the day (no trades in that minute) | Volume. |
| `data.candles[i][6]` | integer, always `0` observed | **VERIFIED** present, but this is an all-`NSE_EQ` sample so a genuinely non-zero OI is **NOT OBSERVED** | Open interest. |

Row ordering is not stated on the page; the verified integration fact is
most-recent-first (confirmed again in all 3 live calls above).

### Documentation example response (copied)

```json
{
  "status": "success",
  "data": {
    "candles": [
      [
        "2025-01-12T15:15:00+05:30",
        2305.3,
        2307.05,
        2301,
        2304.65,
        559982,
        0
      ],
      [
        "2025-01-12T14:45:00+05:30",
        2309.1,
        2310.75,
        2305.25,
        2305.3,
        740124,
        0
      ]
    ]
  }
}
```

### Documented errors

The page documents a generic `4XX` response and:

| Code | Documentation description |
|---|---|
| `UDAPI1021` | Instrument key is of invalid format. |
| `UDAPI100011` | Invalid instrument key. |
| `UDAPI1146` | Invalid unit. The prose includes `weeks` and `months`, although the request table allows only `minutes`, `hours`, and `days`. |
| `UDAPI1147` | Invalid interval. |

### Strict-parser hazards

- **VERIFIED**: `data.candles[i][0]` is always a string in live data, not a
  number, on every unit tested (`minutes`, `hours`).
- The positional seven-element array and timestamp type contradiction are the
  same as above.
- The error text lists `weeks` and `months` although the request table excludes
  them. This is an intra-page disagreement; accept only the request-table
  values until separately verified.
