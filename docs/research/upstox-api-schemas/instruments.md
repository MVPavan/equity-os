# Upstox instrument schemas

Documentation: [Instrument files](https://upstox.com/developer/api-documentation/instruments?utm_source=equity-os)

These are static HTTPS JSON/gzip files; the documentation states no token is
needed on this page and says the files refresh around 06:00 IST. JSON is the
recommended format; CSV is deprecated. `instrument_key` is the durable
identifier; `exchange_token` may be reused after expiry.

## Static file URLs

| File | URL | Documented content |
|---|---|---|
| Complete | `https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz` | Complete BOD instruments |
| NSE | `https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz` | NSE BOD instruments |
| BSE | `https://assets.upstox.com/market-quote/instruments/exchange/BSE.json.gz` | BSE BOD instruments |
| MCX | `https://assets.upstox.com/market-quote/instruments/exchange/MCX.json.gz` | MCX BOD instruments |
| Mutual funds | `https://assets.upstox.com/market-quote/instruments/exchange/mf-instruments.json.gz` | Mutual-fund schemes |
| Suspended | `https://assets.upstox.com/market-quote/instruments/exchange/suspended-instrument.json.gz` | Suspended instruments |
| MTF | `https://assets.upstox.com/market-quote/instruments/exchange/MTF.json.gz` | MTF instruments |
| NSE MIS | `https://assets.upstox.com/market-quote/instruments/exchange/NSE_MIS.json.gz` | NSE MIS instruments |
| BSE MIS | `https://assets.upstox.com/market-quote/instruments/exchange/BSE_MIS.json.gz` | BSE MIS instruments |
| Global | `https://assets.upstox.com/market-quote/instruments/exchange/global.json.gz` | Global indices and indicators |

Each file is a JSON array of records; the docs do not explicitly state the
top-level JSON type or record requiredness beyond the examples below. For every
field in the following tables, presence and nullability are `UNDOCUMENTED`.
An omitted field in a variant's example is not evidence that it is optional.

**VERIFIED against the live files, 2026-09-03.** Downloaded and fully
decompressed both `complete.json.gz` (117,344 records, 54.6 MB decompressed)
and `suspended-instrument.json.gz` (33,930 records, 9.7 MB decompressed) and
scanned **every record** — not a sample — to compute exact field-presence
counts per segment/instrument_type combination. `NSE.json.gz`, `BSE.json.gz`,
`MCX.json.gz`, `mf-instruments.json.gz`, `MTF.json.gz`, `NSE_MIS.json.gz`,
`BSE_MIS.json.gz`, and `global.json.gz` were **NOT** separately downloaded —
`complete.json.gz` already contains NSE/BSE/MCX/global/MTF-shaped records, but
the dedicated `mf-instruments.json.gz` file itself was not fetched, so the
mutual-fund record section below remains **NOT OBSERVED**.

## BOD equity record (`EQ`)

Example from docs:

```json
{
  "segment": "NSE_EQ",
  "name": "JOCIL LIMITED",
  "exchange": "NSE",
  "isin": "INE839G01010",
  "instrument_type": "EQ",
  "instrument_key": "NSE_EQ|INE839G01010",
  "lot_size": 1,
  "freeze_quantity": 100000.0,
  "exchange_token": "16927",
  "tick_size": 5.0,
  "trading_symbol": "JOCIL",
  "short_name": "JOCIL",
  "security_type": "NORMAL",
  "cas_eligible": true
}
```

**VERIFIED — full scan of `complete.json.gz`.** `NSE_EQ`/`EQ` records:
2,639; `BSE_EQ`/`A` records: 699. Exact field presence:

| Field | JSON/type | Presence / nullability | Documented meaning / enum |
|---|---|---|---|
| `segment` | string | **VERIFIED**, all segment values in the enum were observed, plus `GLOBAL_INDEX`/`GLOBAL_INDICATOR` which are documented separately | `NSE_EQ`, `NSE_INDEX`, `NSE_FO`, `NCD_FO`, `BSE_EQ`, `BSE_INDEX`, `BSE_FO`, `BCD_FO`, `MCX_FO`, `NSE_COM`. |
| `name` | string | **VERIFIED** 100% present | Equity name. |
| `exchange` | string | **VERIFIED** 100% present | `NSE`, `BSE`, `MCX`. |
| `isin` | string | **VERIFIED** 100% present | ISIN. |
| `instrument_type` | string | **VERIFIED** 100% present | Exchange-defined instrument type; docs delegate NSE/BSE values to those exchanges. |
| `instrument_key` | string | **VERIFIED** 100% present | Unique Upstox identifier. |
| `lot_size` | number | **VERIFIED** 100% present, always `int` | Lot size. |
| `freeze_quantity` | number | **VERIFIED** 100% present, always `float` | Maximum freezable quantity. |
| `exchange_token` | string | **VERIFIED** 100% present | Exchange token. |
| `tick_size` | number | **VERIFIED** 100% present, always `float` | Minimum price movement. |
| `trading_symbol` | string | **VERIFIED** 100% present | Trading symbol. |
| `short_name` | string | **CORRECTED: genuinely optional, not just "example omits it."** Present in 1,753/2,639 (66%) `NSE_EQ` records and 520/699 (74%) `BSE_EQ` records — missing in roughly a third of real records. A schema that marks this required will reject valid rows. | Short name. |
| `security_type` | string | **VERIFIED** 100% present on `NSE_EQ`; **CORRECTED: entirely absent on `BSE_EQ`** (0/699) — this field does not exist on BSE equity records at all in the live file | Security classification; enum delegated to Security Type Appendix. |
| `cas_eligible` | boolean | **CORRECTED — major finding: present only when `true`, never present-and-`false`.** Present in 210/2,639 `NSE_EQ` and 208/699 `BSE_EQ` records, and in every one of those it is `true`. A schema modeling this as a required or nullable boolean is wrong either way: model it as "optional, defaults to `false` when absent." | Participates in Closing Auction Session. |

**UNDOCUMENTED FIELDS on plain `EQ` records: `mtf_enabled`, `mtf_bracket`.**
These are documented only as belonging to the separate "MTF record" file
variant (`MTF.json.gz`), but they appear directly embedded in 1,361/2,639
(52%) of ordinary `NSE_EQ`/`EQ` records inside `complete.json.gz` — e.g.
Maruti Suzuki's record in the complete file carries `"mtf_enabled": true,
"mtf_bracket": 23.37` alongside the fields documented above. Not observed on
any `BSE_EQ` record. A strict schema for the base EQ record needs these two
fields as optional (`bool`, `float`), not just in a separate MTF-only model.

## CORRECTIONS from the 2026-09-04 live run

Full scan of `complete.json.gz` as served 2026-09-04 (118,334 records, up from
117,344 the day before). Three findings, all of which contradict the section
above and two of which were live correctness bugs.

**1. `qty_multiplier` is on every equity record.** The BOD-equity table above
omits it and lists it only under the suspended record. It was present on
**3,337/3,337** retained equity rows, always `float`, and every observed value
was `1.0`. Found by the unknown-key census on the adapter's first live run.
Modelled required; the constant value is deliberately *not* modelled.

**2. `instrument_type` does not separate equity from non-equity, and must never
be used as the equity filter.** The two cash segments hold 22,458 rows:

| Fact | Count |
|---|---|
| Rows in `NSE_EQ` + `BSE_EQ` | 22,458 |
| Of those, company equity (`INE…` with ISIN issue-type `01`) | **7,845** |
| `NSE_EQ`/`EQ` rows that are **ETFs**, not companies (`INF…` issuers) | 176 |
| Distinct `instrument_type` values inside the two segments | 137 |

`NSE_EQ` also carries government securities (`SG` 4,311, `GS` 131, `TB` 84),
NCD series (`N0`–`N9`, `NA`–`NZ`, `Y*`, `Z*`) and SME/startup boards (`SM` 450,
`ST` 117). `BSE_EQ` carries the fixed-income group `F` (6,559). Six
segment/type combinations — including `NSE_EQ`/`EQ` itself — **mix** equity and
non-equity.

**3. The equity discriminator is the ISIN.** An Indian ISIN is
`IN | issuer-type | 4-char issuer | 2-char issue-type | 2-char serial | check`.
`INE` is a company and issue-type `01` is equity shares. Both conditions are
required: issue-type `01` alone admits 328 `INF` mutual-fund rows and 12 `IN9`;
`INE` alone admits 7,936 debentures (issue-types `07`, `08`, `14`, `15`).
Together they give 7,845 rows over 5,409 distinct ISINs and cover all ten pinned
watchlist stocks.

The cost of getting this wrong was measured, not hypothetical. Filtering on
`NSE_EQ`/`EQ` and `BSE_EQ`/`A` **silently dropped HFCL and MTARTECH**, which
trade in NSE series `BE` and BSE group `T`. A company moved to trade-to-trade is
still that company. Two of ten pinned stocks were invisible to the entity map,
with no anomaly and no drift recorded — just absence.

## Futures record (`FUT`)

**VERIFIED — full scan.** `NSE_FO`/`FUT`: 647 records; `NSE_FO`/`CE`: 15,804
records (sampled as a proxy for the options table below since it shares the
same fields). Every documented field was 100% present with the documented
type across all 647 `FUT` records — no missing fields found.

| Field | JSON/type | Presence / nullability | Meaning / enum |
|---|---|---|---|
| `weekly` | boolean | **VERIFIED** 100% present | Weekly future flag. |
| `segment` | string | **VERIFIED** 100% present | Same segment enum as BOD equity. |
| `name` | string | **VERIFIED** 100% present | Future name. |
| `exchange` | string | **VERIFIED** 100% present | `NSE`, `BSE`, `MCX`. |
| `expiry` | **CORRECTED: docs type `date`, actual is always integer epoch ms** | **VERIFIED** 100% present, always `int` | Future expiry. |
| `instrument_type` | string | **VERIFIED** 100% present, always `FUT` | `FUT`. |
| `underlying_symbol` | string | **VERIFIED** 100% present | Underlying symbol. |
| `instrument_key` | string | **VERIFIED** 100% present | Unique identifier. |
| `lot_size` | number | **VERIFIED** 100% present, always `int` | Lot size. |
| `freeze_quantity` | number | **VERIFIED** 100% present, always `float` | Maximum freezable quantity. |
| `exchange_token` | string | **VERIFIED** 100% present | Exchange token. |
| `minimum_lot` | number | **VERIFIED** 100% present, always `int` | Minimum lot. |
| `underlying_key` | string | **VERIFIED** 100% present | Underlying instrument key. |
| `tick_size` | number | **VERIFIED** 100% present, always `float` | Minimum movement. |
| `underlying_type` | string | **VERIFIED** 100% present | `COM`, `INDEX`, `EQUITY`, `CUR`, `IRD`. |
| `trading_symbol` | string | **VERIFIED** 100% present | `<underlying_symbol> FUT <expiry in dd MMM yy>`. |

**UNDOCUMENTED FIELDS on `FUT`/`CE`/`PE` records: `asset_key`, `asset_symbol`,
`asset_type`.** Not in the docs' futures/options field tables at all, but
present in 100% of both the 647 `FUT` and 15,804 `CE` records scanned — e.g.
`"asset_key": "NSE_INDEX|Nifty Bank", "asset_symbol": "BANKNIFTY",
"asset_type": "INDEX"` alongside the (identical-valued, for index
derivatives) `underlying_key`/`underlying_symbol`/`underlying_type` triplet.
`qty_multiplier` (float, always `1.0`) is likewise present on every record
but absent from the docs' field table.

Example from docs:

```json
{
  "weekly": false,
  "segment": "NSE_FO",
  "name": "071NSETEST",
  "exchange": "NSE",
  "expiry": 2111423399000,
  "instrument_type": "FUT",
  "underlying_symbol": "071NSETEST",
  "instrument_key": "NSE_FO|36702",
  "lot_size": 50,
  "freeze_quantity": 100000.0,
  "exchange_token": "36702",
  "minimum_lot": 50,
  "underlying_key": "NSE_EQ|DUMMYSAN011",
  "tick_size": 5.0,
  "underlying_type": "EQUITY",
  "trading_symbol": "071NSETEST FUT 27 NOV 36",
  "strike_price": 0.0
}
```

`strike_price` is present in the example but is not included in the futures
field-description table; its type/presence/meaning are therefore
`UNDOCUMENTED`. **CORRECTED: VERIFIED present in 100% of 647 `FUT` records,
always `float`, and always exactly `0.0`** — futures never carry a real
strike; the field exists purely for shape-uniformity with options records.

## Options record (`CE` / `PE`)

The docs use the same fields as futures, plus `strike_price`, and document:

**VERIFIED — full scan of 15,804 `NSE_FO`/`CE` records** (proxy for the
shared FUT/CE/PE field set; `PE` count was 15,775, not separately scanned
field-by-field but sharing the same record shape by construction). All
documented fields 100% present.

| Field | JSON/type | Presence / nullability | Meaning / enum |
|---|---|---|---|
| `weekly` | boolean | **VERIFIED** 100% present | Weekly option flag. |
| `segment`, `name`, `exchange` | string | **VERIFIED** 100% present | Segment, name, and `NSE`/`BSE`/`MCX`. |
| `expiry` | **CORRECTED: always integer epoch ms in the static file**, same as futures | **VERIFIED** 100% present | Option expiry; exact wire representation is not defined. |
| `instrument_type` | string | **VERIFIED** 100% present | `CE` or `PE`. |
| `underlying_symbol` | string | **VERIFIED** 100% present | Underlying symbol. |
| `instrument_key` | string | **VERIFIED** 100% present | Unique identifier. |
| `strike_price` | number | **VERIFIED** 100% present, always `float`, non-zero for real option strikes (unlike `FUT`, where it's always `0.0`) | Strike. |
| `lot_size`, `freeze_quantity`, `minimum_lot`, `tick_size` | number | **VERIFIED** 100% present | Size, freeze cap, minimum lot, tick. |
| `exchange_token` | string | **VERIFIED** 100% present | Exchange token. |
| `underlying_key` | string | **VERIFIED** 100% present | Underlying instrument key. |
| `underlying_type` | string | **VERIFIED** 100% present | `COM`, `INDEX`, `EQUITY`, `CUR`, `IRD`. |
| `trading_symbol` | string | **VERIFIED** 100% present | `<underlying_symbol> <strike_price> <CE/PE> <expiry in dd MMM yy>`. |

Same undocumented-field caveat as `FUT` above: `asset_key`, `asset_symbol`,
`asset_type`, and `qty_multiplier` are present in 100% of the 15,804 `CE`
records scanned but absent from the docs' table.

Example from docs:

```json
{
  "weekly": false,
  "segment": "NSE_FO",
  "name": "VODAFONE IDEA LIMITED",
  "exchange": "NSE",
  "expiry": 1706207399000,
  "instrument_type": "CE",
  "underlying_symbol": "IDEA",
  "instrument_key": "NSE_FO|36708",
  "lot_size": 80000,
  "freeze_quantity": 1600000.0,
  "exchange_token": "36708",
  "minimum_lot": 80000,
  "underlying_key": "NSE_EQ|INE669E01016",
  "tick_size": 5.0,
  "underlying_type": "EQUITY",
  "trading_symbol": "IDEA 22 CE 25 JAN 24",
  "strike_price": 22.0
}
```

## Index record (`INDEX`)

**VERIFIED — full scan.** `NSE_INDEX`: 139 records; `BSE_INDEX`: 77 records.

| Field | JSON/type | Presence / nullability | Meaning / enum |
|---|---|---|---|
| `segment` | string | **VERIFIED** 100% present | Same segment enum as above. |
| `name` | string | **VERIFIED** 100% present | Index name. |
| `exchange` | string | **VERIFIED** 100% present | `NSE`, `BSE`, `MCX`. |
| `instrument_type` | string | **VERIFIED** 100% present, always `INDEX` | `INDEX`. |
| `instrument_key` | string | **VERIFIED** 100% present | Unique identifier. |
| `exchange_token` | **CORRECTED: docs type number, actual is always string** | **VERIFIED** 100% present, always string in both `NSE_INDEX` and `BSE_INDEX` | Exchange token. |
| `trading_symbol` | string | **VERIFIED** 100% present | Index trading symbol. |

**UNDOCUMENTED FIELD, optional-when-true: `cas_eligible`** also appears on
index records (6/139 `NSE_INDEX`, 4/77 `BSE_INDEX`, e.g. `Nifty 50`, `Nifty
Bank`) — same present-only-if-`true` pattern as the EQ record above, and also
visible in `/v2/instruments/search` results for these same indexes
(`search-nifty-index.json`).

Example: `{ "segment": "BSE_INDEX", "name": "AUTO", "exchange": "BSE", "instrument_type": "INDEX", "instrument_key": "BSE_INDEX|AUTO", "exchange_token": "13", "trading_symbol": "AUTO" }`.

## Suspended record

**VERIFIED — full scan of `suspended-instrument.json.gz`, 33,930 records.**
Every one of the 12 documented fields was present in **100% of all 33,930
records** with the documented type — the cleanest result in this whole
verification pass; nothing optional, nothing undocumented, no type
surprises. (One data-quality curiosity, not a schema issue: a handful of
records carry a sentinel `lot_size`/`freeze_quantity` of `999999999`.)

| Field | JSON/type | Presence / nullability | Meaning / enum |
|---|---|---|---|
| `segment`, `name`, `exchange`, `isin`, `instrument_type`, `instrument_key`, `trading_symbol` | string | **VERIFIED** 100% present, no exceptions | Segment/name/exchange, ISIN, exchange-defined type, key, symbol. Segment and exchange use the enums above. |
| `lot_size`, `freeze_quantity`, `tick_size`, `qty_multiplier` | number | **VERIFIED** 100% present, no exceptions (`lot_size` int, others float) | Size, freeze cap, tick, quantity multiplier. |
| `exchange_token` | string | **VERIFIED** 100% present, no exceptions | Exchange token. |

Notably **absent from every suspended record**: `short_name`, `mtf_enabled`,
`mtf_bracket`, `cas_eligible`, `security_type` — none of these ever appear
here, unlike the live `EQ` record above where several of them show up
unpredictably.

Example from docs:

```json
{"segment":"NSE_EQ","name":"JOCIL LIMITED","exchange":"NSE","isin":"INE839G01010","instrument_type":"BE","instrument_key":"NSE_EQ|INE839G01010","lot_size":1,"freeze_quantity":100000.0,"exchange_token":"16931","tick_size":1.0,"trading_symbol":"JOCIL","qty_multiplier":1.0}
```

## MTF record

**`MTF.json.gz` itself was NOT fetched separately in this pass — NOT
OBSERVED as a standalone file.** However, `mtf_enabled`/`mtf_bracket` appear
directly on 1,361 ordinary `NSE_EQ`/`EQ` records inside `complete.json.gz`
(see the BOD equity record section above), and that gives a partial,
indirect verification of this shape: **CORRECTED — `mtf_bracket` is always
`float` in every one of those 1,361 live occurrences, never a string.** The
docs' own internal contradiction ("string in the docs table but number in
the example") is resolved in favor of number.

The MTF equity record fields are `segment`, `name`, `exchange`, `isin`,
`instrument_type`, `instrument_key`, `lot_size`, `freeze_quantity`,
`exchange_token`, `tick_size`, `trading_symbol`, `short_name`, `mtf_enabled`,
`mtf_bracket`, and `security_type`. Types are respectively string, string,
string, string, string, string, number, number, string, number, string, string,
boolean, **string in the docs table but number in the example — VERIFIED number**, and string.
Presence and nullability for every field are UNDOCUMENTED except
`mtf_enabled`/`mtf_bracket`, which (per the BOD equity record findings above)
are themselves optional — present only on a subset of EQ records, not a
fixed always-present pair. `segment` is documented as `NSE_EQ`; `exchange` as
`NSE`; security type is delegated to the appendix.

Example: `{ "segment":"NSE_EQ", "name":"RELIANCE INDUSTRIES LTD", "exchange":"NSE", "isin":"INE002A01018", "instrument_type":"EQ", "instrument_key":"NSE_EQ|INE002A01018", "lot_size":1, "freeze_quantity":100000.0, "exchange_token":"2885", "tick_size":5.0, "trading_symbol":"RELIANCE", "short_name":"Reliance Industries", "mtf_enabled":true, "mtf_bracket":26.5, "security_type":"NORMAL" }`.

## MIS record

**NOT OBSERVED — `NSE_MIS.json.gz`/`BSE_MIS.json.gz` were not fetched in this
pass.** Everything below is still doc-derived only.

The MIS equity record fields are `segment`, `name`, `exchange`, `isin`,
`instrument_type`, `instrument_key`, `lot_size`, `freeze_quantity`,
`exchange_token`, `tick_size`, `trading_symbol`, `short_name`, `security_type`,
`qty_multiplier`, `intraday_margin`, and `intraday_leverage`. Types are string
for the first six string fields listed, number for `lot_size`,
`freeze_quantity`, `tick_size`, `qty_multiplier`, `intraday_margin`, and
`intraday_leverage`, string for `exchange_token`, `trading_symbol`,
`short_name`, and `security_type`. Presence/nullability is UNDOCUMENTED. The
example omits `qty_multiplier`, so omission is not proof of optionality.

## Mutual-fund record

**NOT OBSERVED — `mf-instruments.json.gz` was not fetched in this pass.**
Everything below is still doc-derived only.

| Field | JSON/type | Presence / nullability | Meaning / values |
|---|---|---|---|
| `instrument_key`, `amc`, `name` | string | UNDOCUMENTED / UNDOCUMENTED | Scheme identifier, AMC code, display name. |
| `purchase_allowed`, `redemption_allowed` | boolean | UNDOCUMENTED / UNDOCUMENTED | Whether operation is allowed. |
| `minimum_purchase_amount`, `maximum_purchase_amount`, `purchase_amount_multiplier`, `additional_purchase_amount` | number | UNDOCUMENTED / UNDOCUMENTED | Purchase constraints. |
| `minimum_redemption_quantity`, `maximum_redemption_quantity`, `redemption_quantity_multiplier` | number | UNDOCUMENTED / UNDOCUMENTED | Redemption quantity constraints. |
| `minimum_redemption_amount`, `maximum_redemption_amount`, `redemption_amount_multiplier` | number | UNDOCUMENTED / UNDOCUMENTED | Redemption amount constraints. |
| `dividend_type`, `scheme_type`, `plan`, `settlement_type` | string | UNDOCUMENTED / UNDOCUMENTED | Dividend option; category such as equity/debt/ELSS; direct/regular; e.g. T1/T2. |
| `last_price`, `hair_cut` | number | UNDOCUMENTED / UNDOCUMENTED | NAV and haircut. |
| `last_price_date` | string | UNDOCUMENTED / UNDOCUMENTED | Date for NAV. |

Example from docs:

```json
{"instrument_key":"INF846K016M6","name":"AXIS LONG DURATION FUND REGULAR ANNUAL IDCW PAYOUT","purchase_allowed":true,"redemption_allowed":false,"minimum_purchase_amount":200000.0,"maximum_purchase_amount":0.0,"purchase_amount_multiplier":1.0,"additional_purchase_amount":200000.0,"minimum_redemption_quantity":0.001,"maximum_redemption_quantity":0.0,"redemption_quantity_multiplier":0.001,"minimum_redemption_amount":1.0,"maximum_redemption_amount":0.0,"redemption_amount_multiplier":0.001,"scheme_type":"DEBT","plan":"NORMAL","settlement_type":"L1","hair_cut":1.0}
```

The field table includes `amc`, `dividend_type`, `last_price`, and
`last_price_date`, but the sample omits them; their presence is therefore not
documented.

## Global index and indicator records

The docs list the following fields for both variants:

**VERIFIED — full scan.** `GLOBAL_INDEX`: 10 records (e.g. Hang Seng, Dow
Jones, FTSE 100); `GLOBAL_INDICATOR`: 3 records — inside `complete.json.gz`,
not a dedicated `global.json.gz` fetch. All 13 records carry every field
below.

| Field | JSON/type | Presence / nullability | Meaning / values |
|---|---|---|---|
| `weekly` | boolean | **VERIFIED** 100% present, always `false` in this sample | Weekly flag. |
| `segment` | string | **VERIFIED** 100% present | `GLOBAL_INDEX` or `GLOBAL_INDICATOR`. |
| `name`, `exchange`, `isin`, `country`, `latency`, `instrument_type`, `asset_symbol`, `underlying_symbol`, `instrument_key`, `exchange_token`, `asset_key`, `underlying_key`, `asset_type`, `underlying_type`, `trading_symbol`, `price_quote_unit`, `start_time`, `end_time`, `week_days` | string | **VERIFIED** 100% present (as keys — see empty-string note below) | Display/identity and market metadata. `exchange` is `GLOBAL`; latency values: `20 Seconds`, `120 Seconds`, `900 Seconds`; instrument-key format `<segment>|<trading_symbol>`. |
| `lot_size`, `freeze_quantity`, `minimum_lot`, `tick_size`, `strike_price`, `qty_multiplier`, `mtf_bracket` | number | **VERIFIED** 100% present, all `0`/`0.0` in this sample | Numeric contract/quote fields; global docs say `mtf_bracket` is always `0.0`. |
| `mtf_enabled` | boolean | **VERIFIED** 100% present, always `false` in all 13 records | Always `false` for global instruments. |

`country` is documented as empty for indicators. The live samples also contain
empty strings for `isin`, `instrument_type`, asset/underlying fields, and
`exchange_token`; these are literal empty strings, not documented `null`s.
**VERIFIED** — e.g. Hang Seng's record has `"isin": "", "instrument_type":
"", "asset_symbol": "", "underlying_symbol": "", "exchange_token": "",
"asset_key": "", "underlying_key": "", "asset_type": ""`, confirmed as
present-but-empty-string keys, never absent and never `null`.

## `GET /v2/instruments/search`

Documentation: [Instrument Search](https://upstox.com/developer/api-documentation/instrument-search?utm_source=equity-os)

**VERIFIED (Tier 2 — envelope and fields checked)** with 4 live calls:
`query=RELIANCE` (EQ, original probe), `query=NIFTY&segments=FUT`,
`query=NIFTY&segments=INDEX`, `query=RELIANCE&instrument_types=CE`
(`p5-instrument-search.json`, `search-nifty-fut.json`,
`search-nifty-index.json`, `search-reliance-ce.json`).

### Request

| Name | Type | Presence | Format / values / default |
|---|---|---|---|
| `query` | string | required | Free text, maximum 50 characters. |
| `exchanges` | string | optional; nullability UNDOCUMENTED | Comma-separated `ALL`, `NSE`, `BSE`, `MCX`; default `ALL`. |
| `segments` | string | optional; nullability UNDOCUMENTED | Comma-separated `ALL`, `EQ`, `FO`, `CURR`, `COMM`, `INDEX`, `OPT`, `FUT`; default `ALL`. |
| `instrument_types` | string | optional; nullability UNDOCUMENTED | Comma-separated types; options `CE`, `PE`, series such as `A`, `X`, etc. |
| `expiry` | string | optional; nullability UNDOCUMENTED | Comma-separated keywords `current_week`, `this_week`, `near_week`, `weekly`, `next_week`, `far_week`, `current_month`, `this_month`, `near_month`, `monthly`, `next_month`, `far_month`, or dates `yyyy-MM-dd`. |
| `atm_offset` | integer | optional; nullability UNDOCUMENTED | 0 ATM, positive above, negative below; if `expiry` is omitted, defaults to current-week options. |
| `page_number` | integer | optional; nullability UNDOCUMENTED | Starts at 1; default 1. |
| `records` | integer | optional; nullability UNDOCUMENTED | Default 10; maximum 30; minimum 1. |

### Response fields

Envelope: `status` string; `data` array; `meta_data.page` object. For
`meta_data.page`, every field is an integer: `page_number`, `total_pages`,
`records`, `total_records`; presence/nullability is UNDOCUMENTED.
**VERIFIED** envelope shape and all 4 `meta_data.page` fields in all 4 live
calls.

The `data` item fields depend on segment and match the static variants above.
The search page explicitly documents EQ fields `name`, `segment`, `exchange`,
`isin`, `instrument_key`, `exchange_token`, `trading_symbol`, `short_name`,
`tick_size`, `lot_size`, `instrument_type`, `freeze_quantity`,
`qty_multiplier`, `security_type` (optional), and `cas_eligible`; futures add
`expiry` string (`YYYY-MM-DD`), `weekly`, `underlying_key`, `underlying_type`,
`underlying_symbol`, `strike_price` (always `0.0`), and `minimum_lot`; options
use the same derivative fields with `CE|PE`; indexes use `name`, `segment`,
`exchange`, `instrument_key`, `exchange_token`, `trading_symbol`, and
`instrument_type=INDEX`. Item-field presence is otherwise UNDOCUMENTED.

**VERIFIED — `expiry` is `YYYY-MM-DD` string in search results**, confirmed
on both the `NIFTY` `FUT` search (`"expiry": "2026-09-29"`) and the
`RELIANCE` `CE` search (`"expiry": "2026-09-29"`), in clean contrast to the
static-file `expiry` (always integer epoch ms) — this is the strict-parser
hazard the docs already flag, now backed by live evidence on both sides.

**VERIFIED — `strike_price` is always `0.0` for futures**, `"expiry":
"2026-09-29"`, `"strike_price": 0.0` on the `NIFTY` `FUT` search result, and
non-zero (e.g. `1320.0`) on the `RELIANCE` `CE` result, exactly as documented.

**UNDOCUMENTED FIELD on the `INDEX` search-result shape: `cas_eligible`.**
The docs' INDEX field list for search omits it, but `Nifty 50`, `Nifty Next
50`, `Nifty Bank`, and `NIFTY MID SELECT` in `search-nifty-index.json` all
carry `"cas_eligible": true`; other indexes in the same response (e.g. `Nifty
REITs Realty`, `Nifty Smallcap 500`) omit the key entirely — the same
present-only-if-`true` pattern found in the static index-file records.

**CORRECTED — `qty_multiplier` observed as an integer (`1`), not a float
(`1.0`), in both the `FUT` and `CE` search results**, contrasting with the
static complete-file records where the same field is always `1.0` (float).
JSON does not distinguish `1` from `1.0` at the wire level, but a strict
`int`-only or `float`-only Pydantic field could reject one representation
depending on which endpoint supplied the value — model this field loosely
(`float`, which accepts both) rather than `int`.

### Documentation example response (copied)

```json
{
  "status": "success",
  "data": [
    {
      "name": "RELIANCE INDUSTRIES LTD",
      "segment": "NSE_EQ",
      "exchange": "NSE",
      "isin": "INE002A01018",
      "instrument_key": "NSE_EQ|INE002A01018",
      "exchange_token": "2885",
      "trading_symbol": "RELIANCE",
      "short_name": "Reliance",
      "tick_size": 10.0,
      "lot_size": 1,
      "instrument_type": "EQ",
      "freeze_quantity": 100000.0,
      "qty_multiplier": 1,
      "security_type": "NORMAL",
      "cas_eligible": true
    },
    {
      "name": "RELIANCE INDUSTRIES LTD.",
      "segment": "BSE_EQ",
      "exchange": "BSE",
      "isin": "INE002A01018",
      "instrument_key": "BSE_EQ|INE002A01018",
      "exchange_token": "500325",
      "trading_symbol": "RELIANCE",
      "short_name": "RELIANCE",
      "tick_size": 5.0,
      "lot_size": 1,
      "instrument_type": "A",
      "freeze_quantity": 100000.0,
      "qty_multiplier": 1
    }
  ],
  "meta_data": { "page": { "page_number": 1, "total_pages": 1, "records": 20, "total_records": 2 } }
}
```

### Errors

`UDAPI1169` empty query; `UDAPI1170` query over 50 characters;
`UDAPI1171` invalid exchange; `UDAPI1172` invalid segment; `UDAPI1173`
`records` over 30; `UDAPI1174` `page_number` below 1; `UDAPI1175` invalid
expiry; `UDAPI1196` `records` below 1.

### Strict-parser hazards

Static futures/options samples use epoch integers for `expiry`, while search
responses use `YYYY-MM-DD` strings. Static index documentation calls
`exchange_token` a number while its sample is a string. MTF documentation calls
`mtf_bracket` a string while its sample is numeric. Missing EQ fields such as
`security_type` and `cas_eligible` are shown as genuinely omitted in the BSE
example; the search page explicitly marks only `security_type` optional.
