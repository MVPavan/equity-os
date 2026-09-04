# Upstox fundamentals schemas

All endpoints below use a bare ISIN in the path except the noted competitors
integration hazard. Monetary statement values are in crore. Every response
field's presence is `UNDOCUMENTED` unless the docs explicitly say optional or
present only under a condition; nullability is likewise `UNDOCUMENTED` unless
the docs explicitly say `null`.

**Scope note (2026-09-03 verification pass):** only `corporate-actions` and
`share-holdings` are Tier 1 in this pass — these two are what we will build
against, and are verified exhaustively below. `profile`, `balance-sheet`,
`cash-flow`, `income-statement`, `key-ratios`, and `competitors` were
**explicitly SKIPPED** per the verification brief: an independence test
(`scratchpad/upstox/probes/independence-test/`) showed these six endpoints
share lineage with Screener (`operating_profit` is actually Screener's
profit-before-tax), so no live-verification effort was spent on them here.
Everything in those six sections below is still doc-derived and unverified;
do not read the absence of `VERIFIED`/`CORRECTED` markers there as a gap in
this pass — it is intentional.

**Scope reopened (2026-09-03, later the same day).** The owner reframed these
endpoints from *third opinion* to *parse-check on Screener's HTML scraping*.
Shared lineage disqualifies them from adjudicating truth and qualifies them for
detecting scrape error, because a disagreement then isolates to one cause. Four
of the six — `income-statement`, `balance-sheet`, `cash-flow`, `key-ratios` —
are back in scope as **Lane B** of `docs/research/upstox-integration-plan.md`
(§1, §6.9, §9.6), barred from voting in reconciliation. `profile` and
`competitors` stay out: neither has a Screener counterpart to check.

**Those four sections below are therefore a verification debt, not a closed
decision.** They must be live-verified before Slice 6 implements against them.
Nothing in them below this line carries a `VERIFIED` marker yet.

One doc-derived finding worth promoting out of the tables, because it is
self-proving from Upstox's own example response: `income_statement.operating_profit`
Mar-2025 = 106017 and `full_statement` "Profit Before Tax" Mar-2025 = 106017 —
identical. The mislabel is in Upstox's own data model, not in our reading of it.
Likewise `income_statement.revenue` 982671 equals `full_statement` **"Total
Revenue"**, not "Revenue" (964693), so `revenue` includes other income.

## Shared fundamentals conventions

`status` is a string; the docs list `success` and `error`. All endpoint pages
document `UDAPI1206` for an invalid ISIN. The statement endpoints also document
`UDAPI1207` for invalid `type`; income statement documents `UDAPI1208` for
invalid `time_period`.

The statement pages return four periods. `period` is a string such as
`Mar 2025`; values are numbers in crore. Percentage changes are strings such as
`+12.54%`, and the oldest history item omits `change` rather than returning
`null`. The docs state this omission for the change field. `full_statement` is
present only when `fs=true` and is always annual; `time_period=quarterly` is
documented for income statement only. Verified behavior: the quarterly value is
silently ignored by balance-sheet and cash-flow.

## `GET /v2/fundamentals/{isin}/corporate-actions`

Documentation: [Corporate Actions](https://upstox.com/developer/api-documentation/get-corporate-actions?utm_source=equity-os)

**VERIFIED exhaustively.** Live-called for all 83 ISINs in the entity map
(`scratchpad/upstox/probes/ca-*.json`) — 108 corporate-action events total
across 55 non-empty ISINs (28 of the 83 ISINs returned an empty `data: []`,
i.e. no recorded corporate-action history — a valid, observed response
shape, not an error).

### Request

| Name | JSON/type | Presence | Format / allowed values |
|---|---|---|---|
| `isin` (path) | string | required | ISIN, example `INE002A01018`. |

No query parameters or request limit is documented.

### Response fields

| Field | JSON/type | Presence / nullability | Meaning |
|---|---|---|---|
| `status` | string | **VERIFIED** `success` in all 83 calls | `success` or `error`. |
| `data` | array | **VERIFIED**; **can be empty** (`[]`) — observed in 28/83 ISINs | Corporate-action events. |
| `data[].name` | string | **VERIFIED** always present | **CORRECTED: enum is `Dividend`, `Bonus`, `Rights Issue`, `Split` — the docs' own example lists `Rights`, but the live value is always `"Rights Issue"`, never bare `"Rights"`.** Observed distribution across 108 events: `Dividend` 102, `Bonus` 3, `Rights Issue` 2, `Split` 1. |
| `data[].expiry_date` | string | **VERIFIED** always present | Ex-date or effective date, format `dd Mon yyyy` (e.g. `"14 Aug 2025"`) confirmed on every one of 108 events. |
| `data[].amount` | number | **CORRECTED: always present (108/108), always a float — including for non-dividend events, where it is `0.0`, not absent or null.** The docs' "applicable to dividends" phrasing could be misread as "absent otherwise"; it is not. | Monetary amount; `0.0` for `Bonus`/`Split`/`Rights Issue`. |
| `data[].ratio` | string | **VERIFIED nullable, exactly as documented**: `null` in all 102 `Dividend` events, a non-null ratio string (e.g. `"4:1"`, `"1:10"`, `"7:40"`) in all 6 `Bonus`/`Split`/`Rights Issue` events. Zero exceptions in 108 events. | Bonus/split/rights ratio. |
| `data[].event_details` | array | **VERIFIED** always present, never empty; length 6 (`Dividend`) or 5–7 (others) | Detail objects. |
| `data[].event_details[].name` | string | **VERIFIED**; **UNDOCUMENTED enum** — every `Dividend` event has exactly this 7-key set in this order: `Announcement date`, `Ex dividend date`, `Record date`, `Dividend type`, `Amount`, `Dividend %`, `Details` (uniform across all 102 dividend events, zero variation in key set or order). `Bonus` adds `Ratio`, `Ex Bonus date`; `Rights Issue` adds `Ratio`, `Ex rights date`, `Premium`; `Split` adds `Ratio`, `Ex split date`, `Old face value`, `New face value`. All four types share the base three: `Announcement date`, `Record date`, `Details`. | Detail label. |
| `data[].event_details[].value` | string | **VERIFIED** always a string, in all 748 detail values across 108 events, with zero exceptions (dates, ratios, and amounts all arrive as text) | Detail value. Dates and numeric amounts are strings here. |

**UNDOCUMENTED FIELD (enum expansion): `Dividend type`.** The one detail
value the docs don't enumerate at all. Observed values across 102 dividend
events: `Final` (45), `Interim` (29), `Misc.Income` (9), `Interest` (7),
`Dividend` (4), `RepayOfSPVLvlDebt` (4), `Other Income` (2), `Special` (2).
The docs' only example shows `Final`; a strict enum would have rejected 57 of
102 real dividend records.

### Documentation example response (copied)

```json
{
  "status": "success",
  "data": [
    {
      "name": "Dividend",
      "expiry_date": "14 Aug 2025",
      "amount": 5.5,
      "ratio": null,
      "event_details": [
        { "name": "Announcement date", "value": "25 Apr 2025" },
        { "name": "Ex dividend date", "value": "14 Aug 2025" },
        { "name": "Record date", "value": "14 Aug 2025" },
        { "name": "Dividend type", "value": "Final" },
        { "name": "Amount", "value": "5.5" },
        { "name": "Dividend %", "value": "55.0" },
        { "name": "Details", "value": "Rs.5.5000 per share(55%)Final Dividend" }
      ]
    }
  ]
}
```

### Errors

`UDAPI1206` — Invalid ISIN. Not itself tested (no invalid-ISIN probe run),
but the general error envelope shape documented in `historical.md` (array of
error objects, camelCase+snake_case duplicate keys, no `data` key) is a
reasonable prior for this endpoint too — **NOT OBSERVED** here directly.

### Strict-parser hazards

`ratio` is explicitly nullable; `amount` is numeric while an amount inside
`event_details` is a string — **VERIFIED**, and `amount` is a required
always-present field (see above), not conditionally absent. Event-detail
names and values are dynamic key-value records, not a fixed typed object —
**VERIFIED**, and the per-`name`-type key sets above are the full observed
enum; do not assume they are exhaustive of every action type Upstox might
ever emit (only 4 action types were observed in 108 events).

## `GET /v2/fundamentals/{isin}/share-holdings`

Documentation: [Share Holdings](https://upstox.com/developer/api-documentation/get-share-holdings?utm_source=equity-os)

**VERIFIED across 5 companies** spanning large-cap PSU (IDBI Bank), mid-cap
(Dr Reddy's Labs, KPIT Technologies), small-cap (Standard Engineering
Technology), and micro-cap (Mishtann Foods) — `p4-share-holdings-default.json`
and `scratchpad/upstox/probes/verify2/shareholdings-*.json`.

### Request

| Name | JSON/type | Presence | Format / allowed values |
|---|---|---|---|
| `isin` (path) | string | required | ISIN, example `INE002A01018`. |

No query parameters or limit is documented.

### Response fields

| Field | JSON/type | Presence / nullability | Meaning |
|---|---|---|---|
| `status` | string | **VERIFIED** `success` in all 5 calls | `success` or `error`. |
| `data` | array | **VERIFIED**; always exactly 5 entries in every company observed | One entry per shareholder category. |
| `data[].category` | string | **VERIFIED enum, complete and stable**: `promoters`, `fii`, `other_dii`, `mutual_funds`, `retail_and_other` — the same 5 categories in every one of 5 companies, including the micro-cap with several zero-holding categories. **CORRECTED: category order is not fixed** — `mutual_funds` appears last for IDBI Bank/Mishtann Foods/KPIT/Standard Engineering, but 4th (before `retail_and_other`) in the docs' own example; do not index by position. | `promoters`, `fii`, `other_dii`, `mutual_funds`, `retail_and_other`. |
| `data[].history` | array | **VERIFIED**; exactly 4 entries in every company/category observed (20/20) | Quarterly history. |
| `data[].history[].period` | string | **VERIFIED** always present, format `Mon yyyy` | Quarter label, e.g. `Mar 2026`. |
| `data[].history[].value` | number | **VERIFIED — never null or omitted, including at zero.** Mishtann Foods (micro-cap) has `fii`, `other_dii`, and `mutual_funds` all at literal `0.0` across all 4 periods — the field is still present as a float `0.0`, never `null` and never dropped from `history`. | Percentage of total shares. |

### Documentation example response (copied)

```json
{
  "status": "success",
  "data": [
    { "category": "promoters", "history": [
      { "period": "Mar 2026", "value": 50.0 }, { "period": "Dec 2025", "value": 50.01 },
      { "period": "Sep 2025", "value": 50.01 }, { "period": "Jun 2025", "value": 50.07 }
    ] },
    { "category": "fii", "history": [
      { "period": "Mar 2026", "value": 18.67 }, { "period": "Dec 2025", "value": 19.09 },
      { "period": "Sep 2025", "value": 18.65 }, { "period": "Jun 2025", "value": 19.21 }
    ] },
    { "category": "other_dii", "history": [
      { "period": "Mar 2026", "value": 10.77 }, { "period": "Dec 2025", "value": 10.66 },
      { "period": "Sep 2025", "value": 10.67 }, { "period": "Jun 2025", "value": 10.48 }
    ] },
    { "category": "mutual_funds", "history": [
      { "period": "Mar 2026", "value": 9.78 }, { "period": "Dec 2025", "value": 9.52 },
      { "period": "Sep 2025", "value": 9.66 }, { "period": "Jun 2025", "value": 9.32 }
    ] },
    { "category": "retail_and_other", "history": [
      { "period": "Mar 2026", "value": 10.79 }, { "period": "Dec 2025", "value": 10.73 },
      { "period": "Sep 2025", "value": 11.01 }, { "period": "Jun 2025", "value": 10.92 }
    ] }
  ]
}
```

### Errors

`UDAPI1206` — Invalid ISIN. **NOT OBSERVED** (no invalid-ISIN probe run in
this pass).

## `GET /v2/fundamentals/{isin}/profile`

**SKIPPED — out of scope for this verification pass** (see the scope note at
the top of this file). Everything below is unverified doc-derived content.

Documentation: [Company Profile](https://upstox.com/developer/api-documentation/get-company-profile?utm_source=equity-os)

### Request

`isin` is a required string path parameter. No query parameter or limit is
documented.

### Response fields

| Field | JSON/type | Presence / nullability | Meaning |
|---|---|---|---|
| `status` | string | UNDOCUMENTED / UNDOCUMENTED | `success` or `error`. |
| `data` | object | UNDOCUMENTED / UNDOCUMENTED | Profile. |
| `data.company_profile` | string | UNDOCUMENTED / UNDOCUMENTED | Business description. |
| `data.sector` | string | UNDOCUMENTED / UNDOCUMENTED | Sector. |
| `data.sector_market_cap_inr` | object | UNDOCUMENTED / UNDOCUMENTED | INR sector market cap. |
| `data.sector_market_cap_inr.value` | number | UNDOCUMENTED / UNDOCUMENTED | Crore value. |
| `data.sector_market_cap_inr.unit` | string | UNDOCUMENTED / UNDOCUMENTED | `crore`. |
| `data.sector_market_cap_inr.formatted` | string | UNDOCUMENTED / UNDOCUMENTED | Display value, e.g. `1,942,866.05 Cr`. |
| `data.sector_market_cap_usd` | object | UNDOCUMENTED / UNDOCUMENTED | USD sector market cap. |
| `data.sector_market_cap_usd.value` | number | UNDOCUMENTED / UNDOCUMENTED | Value in the stated unit. |
| `data.sector_market_cap_usd.unit` | string | UNDOCUMENTED / UNDOCUMENTED | `billion` or `million`. |
| `data.sector_market_cap_usd.formatted` | string | UNDOCUMENTED / UNDOCUMENTED | Display value, e.g. `$215.87B`. |

### Documentation example response (copied)

```json
{
  "status": "success",
  "data": {
    "company_profile": "Reliance Industries Limited is engaged in the activities of hydrocarbon exploration and production, petroleum refining and marketing, petrochemicals, advanced materials and composites, renewables, retail and digital services.",
    "sector": "Refineries",
    "sector_market_cap_inr": { "value": 1942866.05, "unit": "crore", "formatted": "1,942,866.05 Cr" },
    "sector_market_cap_usd": { "value": 215.87, "unit": "billion", "formatted": "$215.87B" }
  }
}
```

### Errors

`UDAPI1206` — Invalid ISIN.

## `GET /v2/fundamentals/{isin}/competitors`

**SKIPPED — out of scope for this verification pass** (see the scope note at
the top of this file). Everything below is unverified doc-derived content.


Documentation: [Competitors](https://upstox.com/developer/api-documentation/get-competitors?utm_source=equity-os)

### Request

The documentation declares `isin` as a required string path parameter and
shows a bare ISIN. Verified integration behavior requires the path value in the
`NSE_EQ|<isin>` instrument-key form, not a bare ISIN. URL-encode `|` when used
in a path segment. No query parameter or limit is documented.

### Response fields

| Field | JSON/type | Presence / nullability | Meaning |
|---|---|---|---|
| `status` | string | UNDOCUMENTED / UNDOCUMENTED | `success` or `error`. |
| `data` | array | UNDOCUMENTED / UNDOCUMENTED | Competitor profiles. |
| `data[].instrument_key` | string | UNDOCUMENTED / UNDOCUMENTED | `EXCHANGE|ISIN`, e.g. `NSE_EQ|INE242A01010`. |
| `data[].company_profile` | string | UNDOCUMENTED / UNDOCUMENTED | Business description. |
| `data[].sector` | string | UNDOCUMENTED / UNDOCUMENTED | Sector. |
| `data[].sector_market_cap_inr` | object | UNDOCUMENTED / UNDOCUMENTED | Nested fields: `value` number, `unit` string `crore`, `formatted` string. |
| `data[].sector_market_cap_usd` | object | UNDOCUMENTED / UNDOCUMENTED | Nested fields: `value` number, `unit` string `billion` or `million`, `formatted` string. |

### Documentation example response (copied)

```json
{
  "status": "success",
  "data": [
    {
      "instrument_key": "NSE_EQ|INE242A01010",
      "company_profile": "Indian Oil Corporation Limited is an India-based oil company. The Company's segments include Petroleum Products, Petrochemicals, Gas, and Other Business Activities. Its business interests span the entire hydrocarbon value-chain, ranging from refining, pipeline transportation and marketing to exploration and production of petrochemicals, natural gas and alternative energy.",
      "sector": "Refineries",
      "sector_market_cap_inr": { "value": 204334.32, "unit": "crore", "formatted": "204,334.32 Cr" },
      "sector_market_cap_usd": { "value": 22.7, "unit": "billion", "formatted": "$22.70B" }
    },
    {
      "instrument_key": "NSE_EQ|INE029A01011",
      "company_profile": "Bharat Petroleum Corporation Limited is an India-based company, which is engaged in the refining of crude oil and marketing of petroleum products. Its segments include Downstream Petroleum and Exploration & Production of Hydrocarbons.",
      "sector": "Refineries",
      "sector_market_cap_inr": { "value": 131391.64, "unit": "crore", "formatted": "131,391.64 Cr" },
      "sector_market_cap_usd": { "value": 14.6, "unit": "billion", "formatted": "$14.60B" }
    }
  ]
}
```

### Errors

`UDAPI1206` — Invalid ISIN.

## LANE B LIVE VERIFICATION — 2026-09-04

The four statement/ratio sections below were marked **SKIPPED — doc-derived and
unverified**. They were verified live on 2026-09-04: **29 authenticated GETs**
over three issuers (TITAN, HFCL, NETWEB) × both bases × four surfaces, plus
invalid-ISIN and `time_period` probes. Raw bodies retained. This block is
authoritative where it contradicts the sections below; those sections are left
in place so the correction is visible.

### 1. An invalid ISIN is INDISTINGUISHABLE from an empty company — HTTP 200

The single most dangerous finding, and it defeats the guard the integration plan
proposed for this exact risk.

```
GET /v2/fundamentals/INE000X00000/corporate-actions
200  {"status":"success","data":[]}
```

The plan (§9.3, review S5) said: *"`OK_EMPTY` requires `status == "success"`
**and** `data == []`. Without this an invalid ISIN could read as `OK_EMPTY`."*
An invalid ISIN returns **precisely that shape**. There is no error envelope, no
non-200, and nothing in the body to distinguish "this ISIN does not exist" from
"this company has no corporate actions".

**So the envelope cannot be the guard. The ISIN must be validated before the
call.** Only call ISINs that are check-digit valid *and* present in the retained
instrument catalog; then an empty response means genuinely empty.

On `income-statement` the invalid ISIN differs in one thin way —
`"full_statement": null`, where a valid-but-empty company (NETWEB consolidated)
gives `[]`. That was the only such distinction across all 29 responses, it is
n=1, and it does not exist on `corporate-actions` at all. **Do not rely on it.**

### 2. `full_statement` is ANNUAL-ONLY even when the response says `quarterly`

Silent wrong-period corruption, HTTP 200, no error — the F1 class.

```
GET /v2/fundamentals/{isin}/income-statement?type=consolidated&fs=true&time_period=quarterly
→ "time_period": "quarterly"                                     ← the response says quarterly
→ income_statement[].history periods: Jun 2026, Mar 2026, Dec 2025, Sep 2025   ← quarterly, correct
→ full_statement[].history  periods: Mar 2026, Mar 2025, Mar 2024, Mar 2023    ← STILL ANNUAL
```

A parser reading `full_statement` from a quarterly request gets annual figures
inside a payload whose own `time_period` field claims quarterly. **A quarterly
comparison must read the summary block**, which is the three-line block whose
category names are wrong and need the mapping table.

`time_period=quarterly` is **silently ignored** by `balance-sheet` and
`cash-flow`: both echo `"yearly"` and return byte-identical bodies. Only
`income-statement` honours it.

**The consequence for finding 3: under a quarterly request the period label is
not a key across the two blocks.** The summary's `Mar 2026` is the quarter
ending March 2026; `full_statement`'s `Mar 2026` is the financial year. Joining
on the label compares 27,104 crore of quarterly revenue against 88,136 crore of
annual revenue and calls it a disagreement. Running the identity check on the
live quarterly TITAN response produced exactly three confident false
disagreements — one per identity. The check is therefore only defined when both
blocks are annual.

### 3. The name map is confirmed on live data — 48 of 51 identities hold

Each summary `category` was checked against the `full_statement` particular the
mapping table claims it equals, across every valid response:

| Summary `category` | `full_statement` particular | Holds |
|---|---|---|
| `revenue` | `Total Revenue` | ✔ |
| `operating_profit` | **`Profit Before Tax`** | ✔ |
| `net_profit` | `Profit After Tax` | ✔ |

**48 hold, 3 fail — and all three failures are one company in one response.**

| Response | Period | Summary | `full_statement` | Gap |
|---|---|---|---|---|
| NETWEB standalone | Mar 2024 | `revenue` 735.97 | Total Revenue 735.96 | 0.01 |
| NETWEB standalone | Mar 2025 | `operating_profit` 153.0 | Profit Before Tax 153.97 | **0.97** |
| NETWEB standalone | Mar 2025 | `net_profit` 113.75 | Profit After Tax 114.48 | **0.73** |

The last two are the same company and period, both beyond rounding, and **both
blocks come from the same HTTP response** — Upstox contradicts itself inside one
payload. Lane B must therefore state which block it read and record the other,
because "Upstox says X" is not well defined for this issuer.

### 4. Verified response shapes

Envelope invariants across all 29: `status` is always `"success"`; `units_in` is
always `"crore"`; `time_period` is `"yearly"` or `"quarterly"`.

`full_statement` is a list on every valid response; the only `null` seen was the
invalid-ISIN probe (finding 1). Every `value` is a JSON **float** — never a
string, never `null` — across all 936 observed values.

**`income-statement`** — `data` keys: `type`, `time_period`, `units_in`,
`income_statement`, `full_statement`. Summary is
`income_statement: [{category, history: [{value, period, change?}]}]` with
exactly the three categories above. `change` is a **string** like `"+44.62%"`
and is **absent on the oldest period** of every series. `full_statement`
particulars, 9 in fixed order: `Revenue`, `Other Income`, `Total Revenue`,
`Total Expenses`, `Profit Before Tax`, `Tax`, `Profit After Tax`, `EPS - Basic`,
`EPS - Diluted`.

**`balance-sheet`** — a **different summary shape**: `history:
[{total_asset, total_liability, period}]`, not the `{category, history}` form.
Note `total_asset`/`total_liability` are **singular**. `full_statement`
particulars, 8: `Non-Current Assets`, `Current Assets`, `Total Assets`,
`Current Liabilities`, `Net Current Asset`, `Non-Current Liabilities`,
`Equity Capital`, `Total Equity & Liabilities`. There is no `Total Liabilities`
particular.

**`cash-flow`** — summary key is `cash_flow: [{category, history}]` with
categories `operating`, `investing`, `financing`, always all three and always in
that order. Its `history` entries carry the same optional string `change` as
`income-statement`. Values are signed (`-541.0` observed). `full_statement` particulars, 11: `Profit before tax`,
`Income before WC changes`, `Change in Assets`, `Change in Liabilities`,
`Change in WC`, `Cash flow from Operations`, `Cash flow from Investing`,
`Cash flow from Financing`, `Total Cash Flow`, `Cash (Start of the year)`,
`Cash (End of the year)`.

**`key-ratios`** — `data` is a **bare array**, not an object, and **the row set
is not fixed**: TITAN and NETWEB return 7 rows, HFCL returns 6 — `Quick Ratio`
is simply absent. A parser must key by `name` and treat every ratio as optional;
indexing by position, or asserting a count, breaks on the second company tried.

Observed names: `P/E`, `P/B`, `ROA`, `ROE`, `ROCE`, `Quick Ratio`, `EV/EBITDA`.
Each row is `{name, company_value, sector_value}` and **both values are
STRINGS**. `ROA`, `ROE` and `ROCE` carry a trailing `%`; the others do not.
Either field can be negative (`"-9.01"` observed on TITAN's EV/EBITDA
`sector_value`), so both need signed parsing.

The response has no `status`-sibling metadata at all: no `units_in`, no
`time_period`, no period, and — unlike the other three — **no `type` echo**. It
does honour `?type=`: standalone and consolidated differ for all three issuers.
So the basis is real but unstated, and the caller must record which basis it
requested; the payload cannot tell you afterwards.

### 5. Four periods, and a basis a company may not publish

Every valid response returned exactly 4 periods. NETWEB has **no consolidated
statements**: all three consolidated surfaces return `history: []` /
`full_statement: []` with `status: "success"`. That is a real answer about the
company and must not be read as a failure — but see finding 1 for why it cannot
be distinguished from a bad ISIN by the envelope alone.

---

## `GET /v2/fundamentals/{isin}/key-ratios`

**SKIPPED in the 2026-09-03 pass — but VERIFIED LIVE 2026-09-04; see the LANE B LIVE VERIFICATION block above, which is authoritative where it contradicts what follows.** Everything below is the original doc-derived content.


Documentation: [Key Ratios](https://upstox.com/developer/api-documentation/get-key-ratios?utm_source=equity-os)

### Request

`isin` is a required string path parameter. No query parameter or limit is
documented.

### Response fields

| Field | JSON/type | Presence / nullability | Meaning |
|---|---|---|---|
| `status` | string | UNDOCUMENTED / UNDOCUMENTED | `success` or `error`. |
| `data` | array | UNDOCUMENTED / UNDOCUMENTED | Ratio entries. |
| `data[].name` | string | UNDOCUMENTED / UNDOCUMENTED | `P/E`, `P/B`, `ROA`, `ROE`, `ROCE`, `EV/EBITDA`. |
| `data[].company_value` | string | UNDOCUMENTED / UNDOCUMENTED | Company ratio; may be numeric text or percentage text. |
| `data[].sector_value` | string | UNDOCUMENTED / UNDOCUMENTED | Sector benchmark; same mixed string conventions. |

### Documentation example response (copied)

```json
{
  "status": "success",
  "data": [
    { "name": "P/E", "company_value": "20.15", "sector_value": "12.46" },
    { "name": "P/B", "company_value": "2.13", "sector_value": "1.53" },
    { "name": "ROA", "company_value": "4.39%", "sector_value": "7.54%" },
    { "name": "ROE", "company_value": "8.94%", "sector_value": "16.46%" },
    { "name": "ROCE", "company_value": "10.39%", "sector_value": "16.9%" },
    { "name": "EV/EBITDA", "company_value": "10.25", "sector_value": "6.94" }
  ]
}
```

### Errors

`UDAPI1206` — Invalid ISIN.

## Statement response schemas

The following three endpoints share `data.type` (`consolidated` or
`standalone`), `data.time_period` (`yearly` or `quarterly` in the documented
response table), and `data.units_in` (`crore`). The top-level presence and
nullability are UNDOCUMENTED.

## `GET /v2/fundamentals/{isin}/balance-sheet`

**SKIPPED in the 2026-09-03 pass — but VERIFIED LIVE 2026-09-04; see the LANE B LIVE VERIFICATION block above, which is authoritative where it contradicts what follows.** Everything below is the original doc-derived content.


Documentation: [Balance Sheet](https://upstox.com/developer/api-documentation/get-balance-sheet?utm_source=equity-os)

Request: required path `isin` string. Optional query `type` string,
`consolidated|standalone`, default `consolidated`; optional query `fs`
boolean, which adds `full_statement` when `true`. No page-size or date limit is
documented.

Response fields:

| Field | Type | Presence / nullability | Meaning |
|---|---|---|---|
| `data.type` | string | UNDOCUMENTED / UNDOCUMENTED | `consolidated` or `standalone`. |
| `data.time_period` | string | UNDOCUMENTED / UNDOCUMENTED | `yearly` or `quarterly` in the response table; full statement remains annual. |
| `data.units_in` | string | UNDOCUMENTED / UNDOCUMENTED | `crore`. |
| `data.history` | array | UNDOCUMENTED / UNDOCUMENTED | Summary history, four periods, most recent first per docs. |
| `data.history[].total_asset` | number | UNDOCUMENTED / UNDOCUMENTED | Total assets, crore. |
| `data.history[].total_liability` | number | UNDOCUMENTED / UNDOCUMENTED | Total liabilities, crore. |
| `data.history[].period` | string | UNDOCUMENTED / UNDOCUMENTED | Period label, e.g. `Mar 2025`. |
| `data.full_statement` | array | **optional when `fs` is false/absent; nullability UNDOCUMENTED** | Detailed rows; present only with `fs=true`, annual. |
| `data.full_statement[].particular` | string | UNDOCUMENTED / UNDOCUMENTED | One of the eight documented labels: `Non-Current Assets`, `Current Assets`, `Total Assets`, `Current Liabilities`, `Net Current Asset`, `Non-Current Liabilities`, `Equity Capital`, `Total Equity & Liabilities`. |
| `data.full_statement[].history` | array | UNDOCUMENTED / UNDOCUMENTED | Line-item history. |
| `data.full_statement[].history[].period` | string | UNDOCUMENTED / UNDOCUMENTED | Period label. |
| `data.full_statement[].history[].value` | number | UNDOCUMENTED / UNDOCUMENTED | Crore value. |

### Documentation example response (copied)

```json
{
  "status": "success",
  "data": {
    "type": "consolidated",
    "time_period": "yearly",
    "units_in": "crore",
    "history": [
      { "total_asset": 1950121, "total_liability": 940495, "period": "Mar 2025" },
      { "total_asset": 1755986, "total_liability": 830198, "period": "Mar 2024" },
      { "total_asset": 1607431, "total_liability": 778550, "period": "Mar 2023" },
      { "total_asset": 1499665, "total_liability": 610681, "period": "Mar 2022" }
    ],
    "full_statement": [
      { "particular": "Non-Current Assets", "history": [
        { "period": "Mar 2025", "value": 1450851 }, { "period": "Mar 2024", "value": 1285886 }, { "period": "Mar 2023", "value": 1182135 }, { "period": "Mar 2022", "value": 1152646 }
      ] },
      { "particular": "Current Assets", "history": [
        { "period": "Mar 2025", "value": 499270 }, { "period": "Mar 2024", "value": 470100 }, { "period": "Mar 2023", "value": 425296 }, { "period": "Mar 2022", "value": 347019 }
      ] },
      { "particular": "Total Assets", "history": [
        { "period": "Mar 2025", "value": 1950121 }, { "period": "Mar 2024", "value": 1755986 }, { "period": "Mar 2023", "value": 1607431 }, { "period": "Mar 2022", "value": 1499665 }
      ] },
      { "particular": "Current Liabilities", "history": [
        { "period": "Mar 2025", "value": 453737 }, { "period": "Mar 2024", "value": 397367 }, { "period": "Mar 2023", "value": 395743 }, { "period": "Mar 2022", "value": 308662 }
      ] },
      { "particular": "Net Current Asset", "history": [
        { "period": "Mar 2025", "value": 45533 }, { "period": "Mar 2024", "value": 72733 }, { "period": "Mar 2023", "value": 29553 }, { "period": "Mar 2022", "value": 38357 }
      ] },
      { "particular": "Non-Current Liabilities", "history": [
        { "period": "Mar 2025", "value": 486758 }, { "period": "Mar 2024", "value": 432831 }, { "period": "Mar 2023", "value": 382807 }, { "period": "Mar 2022", "value": 302019 }
      ] },
      { "particular": "Equity Capital", "history": [
        { "period": "Mar 2025", "value": 1009626 }, { "period": "Mar 2024", "value": 925788 }, { "period": "Mar 2023", "value": 828881 }, { "period": "Mar 2022", "value": 888984 }
      ] },
      { "particular": "Total Equity & Liabilities", "history": [
        { "period": "Mar 2025", "value": 1950121 }, { "period": "Mar 2024", "value": 1755986 }, { "period": "Mar 2023", "value": 1607431 }, { "period": "Mar 2022", "value": 1499665 }
      ] }
    ]
  }
}
```

Errors: `UDAPI1206` invalid ISIN; `UDAPI1207` invalid `type`.

## `GET /v2/fundamentals/{isin}/cash-flow`

**SKIPPED in the 2026-09-03 pass — but VERIFIED LIVE 2026-09-04; see the LANE B LIVE VERIFICATION block above, which is authoritative where it contradicts what follows.** Everything below is the original doc-derived content.


Documentation: [Cash Flow](https://upstox.com/developer/api-documentation/get-cash-flow?utm_source=equity-os)

Request: required `isin` string; optional `type` string (`consolidated` or
`standalone`, default `consolidated`); optional `fs` boolean. No other limit is
documented.

Response fields:

| Field | Type | Presence / nullability | Meaning |
|---|---|---|---|
| `data.type`, `data.time_period`, `data.units_in` | string | UNDOCUMENTED / UNDOCUMENTED | Same shared meanings above; units `crore`. |
| `data.cash_flow` | array | UNDOCUMENTED / UNDOCUMENTED | Categories. |
| `data.cash_flow[].category` | string | UNDOCUMENTED / UNDOCUMENTED | `operating`, `investing`, `financing`. |
| `data.cash_flow[].history` | array | UNDOCUMENTED / UNDOCUMENTED | Four history rows. |
| `data.cash_flow[].history[].value` | number | UNDOCUMENTED / UNDOCUMENTED | Crore amount; negative is described as outflow. |
| `data.cash_flow[].history[].period` | string | UNDOCUMENTED / UNDOCUMENTED | Period label. |
| `data.cash_flow[].history[].change` | string | **optional for oldest row; nullability UNDOCUMENTED** | Signed percentage string such as `+12.54%`. |
| `data.full_statement` | array | **optional when `fs` is false/absent; nullability UNDOCUMENTED** | Annual line-item rows. |
| `data.full_statement[].particular` | string | UNDOCUMENTED / UNDOCUMENTED | `Profit before tax`, `Income before WC changes`, `Change in Assets`, `Change in Liabilities`, `Change in WC`, `Cash flow from Operations`, `Cash flow from Investing`, `Cash flow from Financing`, `Total Cash Flow`, `Cash (Start of the year)`, `Cash (End of the year)`. |
| `data.full_statement[].history` | array | UNDOCUMENTED / UNDOCUMENTED | Line-item history. |
| `data.full_statement[].history[].period` | string | UNDOCUMENTED / UNDOCUMENTED | Period label. |
| `data.full_statement[].history[].value` | number | UNDOCUMENTED / UNDOCUMENTED | Crore value. |

### Documentation example response (copied)

```json
{
  "status": "success",
  "data": {
    "type": "consolidated",
    "time_period": "yearly",
    "units_in": "crore",
    "cash_flow": [
      { "category": "operating", "history": [
        { "value": 178703, "period": "Mar 2025", "change": "+12.54%" }, { "value": 158788, "period": "Mar 2024", "change": "+38.04%" }, { "value": 115032, "period": "Mar 2023", "change": "+3.96%" }, { "value": 110654, "period": "Mar 2022" }
      ] },
      { "category": "investing", "history": [
        { "value": -137535, "period": "Mar 2025", "change": "-21.09%" }, { "value": -113581, "period": "Mar 2024", "change": "-24.49%" }, { "value": -91235, "period": "Mar 2023", "change": "+17.14%" }, { "value": -110103, "period": "Mar 2022" }
      ] },
      { "category": "financing", "history": [
        { "value": -31891, "period": "Mar 2025", "change": "-91.58%" }, { "value": -16646, "period": "Mar 2024", "change": "-259.22%" }, { "value": 10455, "period": "Mar 2023", "change": "-39.53%" }, { "value": 17289, "period": "Mar 2022" }
      ] }
    ],
    "full_statement": [
      { "particular": "Profit before tax", "history": [
        { "period": "Mar 2025", "value": 106017 }, { "period": "Mar 2024", "value": 104340 }, { "period": "Mar 2023", "value": 94801 }, { "period": "Mar 2022", "value": 84142 }
      ] },
      { "particular": "Income before WC changes", "history": [
        { "period": "Mar 2025", "value": 166904 }, { "period": "Mar 2024", "value": 164383 }, { "period": "Mar 2023", "value": 140963 }, { "period": "Mar 2022", "value": 113726 }
      ] },
      { "particular": "Change in Assets", "history": [
        { "period": "Mar 2025", "value": -14703 }, { "period": "Mar 2024", "value": -28430 }, { "period": "Mar 2023", "value": -19034 }, { "period": "Mar 2022", "value": -39163 }
      ] },
      { "particular": "Change in Liabilities", "history": [
        { "period": "Mar 2025", "value": 38427 }, { "period": "Mar 2024", "value": 34796 }, { "period": "Mar 2023", "value": -600 }, { "period": "Mar 2022", "value": 39888 }
      ] },
      { "particular": "Change in WC", "history": [
        { "period": "Mar 2025", "value": 23724 }, { "period": "Mar 2024", "value": 6366 }, { "period": "Mar 2023", "value": -19634 }, { "period": "Mar 2022", "value": 725 }
      ] },
      { "particular": "Cash flow from Operations", "history": [
        { "period": "Mar 2025", "value": 178703 }, { "period": "Mar 2024", "value": 158788 }, { "period": "Mar 2023", "value": 115032 }, { "period": "Mar 2022", "value": 110654 }
      ] },
      { "particular": "Cash flow from Investing", "history": [
        { "period": "Mar 2025", "value": -137535 }, { "period": "Mar 2024", "value": -113581 }, { "period": "Mar 2023", "value": -91235 }, { "period": "Mar 2022", "value": -110103 }
      ] },
      { "particular": "Cash flow from Financing", "history": [
        { "period": "Mar 2025", "value": -31891 }, { "period": "Mar 2024", "value": -16646 }, { "period": "Mar 2023", "value": 10455 }, { "period": "Mar 2022", "value": 17289 }
      ] },
      { "particular": "Total Cash Flow", "history": [
        { "period": "Mar 2025", "value": 9277 }, { "period": "Mar 2024", "value": 28561 }, { "period": "Mar 2023", "value": 34252 }, { "period": "Mar 2022", "value": 17840 }
      ] },
      { "particular": "Cash (Start of the year)", "history": [
        { "period": "Mar 2025", "value": 97225 }, { "period": "Mar 2024", "value": 68664 }, { "period": "Mar 2023", "value": 36178 }, { "period": "Mar 2022", "value": 17397 }
      ] },
      { "particular": "Cash (End of the year)", "history": [
        { "period": "Mar 2025", "value": 106502 }, { "period": "Mar 2024", "value": 97225 }, { "period": "Mar 2023", "value": 68664 }, { "period": "Mar 2022", "value": 36178 }
      ] }
    ]
  }
}
```

The live page's example expands `full_statement` when `fs=true`; the 11 rows
above reproduce its labels and values. Errors: `UDAPI1206` invalid ISIN;
`UDAPI1207` invalid `type`.

## `GET /v2/fundamentals/{isin}/income-statement`

**SKIPPED in the 2026-09-03 pass — but VERIFIED LIVE 2026-09-04; see the LANE B LIVE VERIFICATION block above, which is authoritative where it contradicts what follows.** Everything below is the original doc-derived content.


Documentation: [Income Statement](https://upstox.com/developer/api-documentation/get-income-statement?utm_source=equity-os)

Request: required `isin` string; optional `type` string (`consolidated` or
`standalone`, default `consolidated`); optional `time_period` string (`yearly`
or `quarterly`, default `yearly`); optional `fs` boolean. No page-size limit is
documented.

Response fields:

| Field | Type | Presence / nullability | Meaning |
|---|---|---|---|
| `data.type`, `data.time_period`, `data.units_in` | string | UNDOCUMENTED / UNDOCUMENTED | Statement type, reporting frequency, and `crore` units. |
| `data.income_statement` | array | UNDOCUMENTED / UNDOCUMENTED | Summary categories. |
| `data.income_statement[].category` | string | UNDOCUMENTED / UNDOCUMENTED | `revenue`, `operating_profit`, `net_profit`. |
| `data.income_statement[].history` | array | UNDOCUMENTED / UNDOCUMENTED | Four rows, most recent first per docs. |
| `data.income_statement[].history[].value` | number | UNDOCUMENTED / UNDOCUMENTED | Crore value; negative values indicate loss. |
| `data.income_statement[].history[].period` | string | UNDOCUMENTED / UNDOCUMENTED | Period label. |
| `data.income_statement[].history[].change` | string | **optional for oldest row; nullability UNDOCUMENTED** | Percentage string such as `+10.53%`. |
| `data.full_statement` | array | **optional when `fs` is false/absent; nullability UNDOCUMENTED** | Annual detailed rows, irrespective of `time_period`. |
| `data.full_statement[].particular` | string | UNDOCUMENTED / UNDOCUMENTED | `Revenue`, `Other Income`, `Total Revenue`, `Total Expenses`, `Profit Before Tax`, `Tax`, `Profit After Tax`, `EPS - Basic`, `EPS - Diluted`. |
| `data.full_statement[].history` | array | UNDOCUMENTED / UNDOCUMENTED | Four rows. |
| `data.full_statement[].history[].period` | string | UNDOCUMENTED / UNDOCUMENTED | Period label. |
| `data.full_statement[].history[].value` | number | UNDOCUMENTED / UNDOCUMENTED | Documentation calls this monetary value in crore, including EPS rows in the same table. |

### Documentation example response (copied)

```json
{
  "status": "success",
  "data": {
    "type": "consolidated",
    "time_period": "yearly",
    "units_in": "crore",
    "income_statement": [
      { "category": "revenue", "history": [
        { "value": 1086181, "period": "Mar 2026", "change": "+10.53%" }, { "value": 982671, "period": "Mar 2025", "change": "+7.15%" }, { "value": 917121, "period": "Mar 2024", "change": "+3.1%" }, { "value": 889569, "period": "Mar 2023" }
      ] },
      { "category": "operating_profit", "history": [
        { "value": 123162, "period": "Mar 2026", "change": "+16.17%" }, { "value": 106017, "period": "Mar 2025", "change": "+1.61%" }, { "value": 104340, "period": "Mar 2024", "change": "+10.95%" }, { "value": 94046, "period": "Mar 2023" }
      ] },
      { "category": "net_profit", "history": [
        { "value": 95610, "period": "Mar 2026", "change": "+18.35%" }, { "value": 80787, "period": "Mar 2025", "change": "+2.74%" }, { "value": 78633, "period": "Mar 2024", "change": "+6.13%" }, { "value": 74088, "period": "Mar 2023" }
      ] }
    ],
    "full_statement": [
      { "particular": "Revenue", "history": [
        { "period": "Mar 2025", "value": 964693 }, { "period": "Mar 2024", "value": 901064 }, { "period": "Mar 2023", "value": 877835 }, { "period": "Mar 2022", "value": 695963 }
      ] },
      { "particular": "Other Income", "history": [
        { "period": "Mar 2025", "value": 17978 }, { "period": "Mar 2024", "value": 16057 }, { "period": "Mar 2023", "value": 11734 }, { "period": "Mar 2022", "value": 14943 }
      ] },
      { "particular": "Total Revenue", "history": [
        { "period": "Mar 2025", "value": 982671 }, { "period": "Mar 2024", "value": 917121 }, { "period": "Mar 2023", "value": 889569 }, { "period": "Mar 2022", "value": 710906 }
      ] },
      { "particular": "Total Expenses", "history": [
        { "period": "Mar 2025", "value": 876654 }, { "period": "Mar 2024", "value": 812781 }, { "period": "Mar 2023", "value": 795547 }, { "period": "Mar 2022", "value": 631883 }
      ] },
      { "particular": "Profit Before Tax", "history": [
        { "period": "Mar 2025", "value": 106017 }, { "period": "Mar 2024", "value": 104340 }, { "period": "Mar 2023", "value": 94046 }, { "period": "Mar 2022", "value": 82154 }
      ] },
      { "particular": "Tax", "history": [
        { "period": "Mar 2025", "value": 25230 }, { "period": "Mar 2024", "value": 25707 }, { "period": "Mar 2023", "value": 20376 }, { "period": "Mar 2022", "value": 15970 }
      ] },
      { "particular": "Profit After Tax", "history": [
        { "period": "Mar 2025", "value": 80787 }, { "period": "Mar 2024", "value": 78633 }, { "period": "Mar 2023", "value": 73670 }, { "period": "Mar 2022", "value": 66184 }
      ] },
      { "particular": "EPS - Basic", "history": [
        { "period": "Mar 2025", "value": 51.47 }, { "period": "Mar 2024", "value": 51.45 }, { "period": "Mar 2023", "value": 98.59 }, { "period": "Mar 2022", "value": 92 }
      ] },
      { "particular": "EPS - Diluted", "history": [
        { "period": "Mar 2025", "value": 51.47 }, { "period": "Mar 2024", "value": 51.45 }, { "period": "Mar 2023", "value": 98.59 }, { "period": "Mar 2022", "value": 90.86 }
      ] }
    ]
  }
}
```

As with cash flow, the live page expands `full_statement` when `fs=true`; the
nine rows above reproduce its labels and values. Errors:
`UDAPI1206` invalid ISIN; `UDAPI1207` invalid `type`; `UDAPI1208` invalid
`time_period`.

## Cross-endpoint strict-parser notes

- `period` strings are labels such as `Mar 2025`, not ISO dates.
- Corporate-action dates use `dd Mon yyyy` text, while statement periods use
  `Mon yyyy` text.
- Ratio values are strings and may include `%`; cash/income `change` values are
  signed percentage strings.
- `full_statement` is conditional and annual, while summary arrays are the
  four-period result set documented by Upstox.
- The docs do not document response-field nullability beyond corporate-action
  `ratio`; do not convert omission or `null` assumptions into required Pydantic
  fields.
