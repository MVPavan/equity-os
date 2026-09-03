# Upstox news and IPO schemas

**VERIFIED (Tier 2) against live responses (2026-09-03)** for `/v2/news` and
`/v2/ipos` — `scratchpad/upstox/probes/p8-news.json`,
`scratchpad/upstox/probes/verify2/news-maruti.json`,
`scratchpad/upstox/probes/verify2/ipos-{open,listed}.json`. `/v2/ipos/{id}`
was **not called** in this pass (out of the stated Tier 2 scope, which lists
only `/v2/ipos`) — that section remains unverified doc-derived content.

## `GET /v2/news`

Documentation: [News API](https://upstox.com/developer/api-documentation/get-news?utm_source=equity-os)

### Request

| Name | Type | Presence | Format / values / default / limit |
|---|---|---|---|
| `category` | string | required | `instrument_keys`, `positions`, or `holdings`. |
| `instrument_keys` | string | optional; nullability UNDOCUMENTED | Comma-separated instrument keys; required when `category=instrument_keys`; maximum 30 keys. |
| `page_number` | integer | optional; nullability UNDOCUMENTED | 1–100; default 1. |
| `page_size` | integer | optional; nullability UNDOCUMENTED | 1–100; default 100. |

The API returns news published in the preceding seven days. No other date
filter is documented.

### Response fields

| Field | Type | Presence / nullability | Meaning |
|---|---|---|---|
| `status` | string | **VERIFIED** `success` in both live calls | `success` or `error`. |
| `data` | object/map | **VERIFIED**; only `category=instrument_keys` was tested — `positions`/`holdings` key behavior is **NOT OBSERVED** | Dynamic key is an instrument key; value is a news-item array. For positions/holdings, exact key behavior is not documented. |
| `data[<instrument>][].heading` | string | **VERIFIED** always present | Headline. |
| `data[<instrument>][].summary` | string | **VERIFIED** always present | Summary. |
| `data[<instrument>][].thumbnail` | string | **VERIFIED** always present in both calls (5+6 items, 0 missing) | Thumbnail URL. |
| `data[<instrument>][].article_link` | string | **VERIFIED** always present | Article URL. |
| `data[<instrument>][].published_time` | number | **VERIFIED** always present, always integer epoch ms | Unix milliseconds. |
| `metadata` | object | **VERIFIED** present, and correctly comma-separated from `data` on the wire (see below) | Pagination metadata. |
| `metadata.page` | object | **VERIFIED** present | Page details. |
| `metadata.page.page_number`, `page_size`, `total_records`, `total_pages` | integer | **VERIFIED** all 4 present; on a denser-news instrument (MARUTI, `page_size=5`), returned exactly 5 items with `total_records=6, total_pages=2` — the pagination fields are real and consistent, not placeholders | Current page, returned-page size, total matches, and total pages. |

The response field table incorrectly calls `data` an array; the envelope and
example show a dynamic-key object. The docs do not state response-field
nullability. **VERIFIED — `data` is genuinely a dynamic-key object in both
live calls, never an array.**

### Documentation example response (copied)

```text
{
  "status": "success",
  "data": {
    "NSE_EQ|INE040H01021": [
      {
        "heading": "SMIDs outperform: Nifty Smallcap 100, Nifty Midcap 100 rise over 2%; Suzlon Energy, Afcons Infra top gainers",
        "summary": "On a year-on-year basis, the Nifty Midcap 100 index has gained 13%, while the Nifty Smallcap 100 gauge rose 6%",
        "thumbnail": "https://assets.upstox.com/content/assets/images/news/traders-assemble-hero.webp",
        "article_link": "https://upstox.com/news/market-news/latest-updates/smids-outperform/article-181757/",
        "published_time": 1776251261821
      }
    ]
  }
  "metadata": {
    "page": { "page_number": 1, "page_size": 10, "total_records": 1, "total_pages": 1 }
  }
}
```

The live documentation example omits the comma between the closing `data`
object and `metadata`; the block above preserves that source defect and is not
valid JSON. A parser-facing implementation must add the comma after validating
the wire response. **CONFIRMED this is purely a docs-page typo, not a real
wire defect**: both live responses (`p8-news.json`, `news-maruti.json`) are
valid, correctly-comma-separated JSON.

### Errors

`UDAPI1189` invalid category; `UDAPI1190` `instrument_keys` required for the
instrument-key category; `UDAPI1193` more than 30 instrument keys. **NOT
OBSERVED** (no error-path probe run against this endpoint).

### Strict-parser hazards

Dynamic-key object, not an array — **VERIFIED**; `published_time` is epoch
milliseconds while other URLs are strings — **VERIFIED**. Category controls
whether the key can be predicted.

## `GET /v2/ipos`

Documentation: [Get IPOs](https://upstox.com/developer/api-documentation/get-ipos?utm_source=equity-os)

**VERIFIED** with 2 live calls: `status=open` (1 result) and
`status=listed&records=5` (5 of 101 total results) — `ipos-open.json`,
`ipos-listed.json`.

### Request

| Name | Type | Presence | Format / values / default / limit |
|---|---|---|---|
| `status` | string | optional; nullability UNDOCUMENTED | `open`, `closed`, `listed`, `upcoming`; default `open`. `open` and `listed` **VERIFIED**. |
| `issue_type` | string | optional; nullability UNDOCUMENTED | `regular` or `sme`; default returns both. **VERIFIED both values occur** (`sme` and `regular` both present in `ipos-listed.json`'s 5 results) without setting this param, confirming the "default returns both" claim. |
| `page_number` | integer | optional; nullability UNDOCUMENTED | Default 1; minimum is not separately stated. |
| `records` | integer | optional; nullability UNDOCUMENTED | Default 20; maximum 30. **VERIFIED** `records=5` returns exactly 5. |

### Response fields

| Field | Type | Presence / nullability | Meaning |
|---|---|---|---|
| `status` | string | **VERIFIED** `success` | `success` or `error`. |
| `data` | array | **VERIFIED** | IPO listings. |
| `data[].id`, `symbol`, `name`, `isin` | string | **VERIFIED** always present | Slug, ticker, name, ISIN. |
| `data[].industry` | string | **CORRECTED: nullable, not documented as such.** Observed `"industry": null` for one of 6 live IPO records ("Kwick Forensic Solutions IPO", an SME issue) while every other field on that same record was populated normally. A required non-null `industry: str` field will reject this real record. | Industry. |
| `data[].status` | string | **VERIFIED**; both `open` and `listed` observed | `open`, `closed`, `listed`, `upcoming`. |
| `data[].issue_type` | string | **VERIFIED**; both `regular` and `sme` observed | `regular` or `sme`. |
| `data[].issue_size` | number | **VERIFIED** always present, always float | INR crore. |
| `data[].minimum_price`, `maximum_price` | number | **VERIFIED** always present, always float, non-zero (already-announced issues) in this sample; the docs' `0`-if-unannounced case is **NOT OBSERVED** | INR price band; docs say `0` if not announced. |
| `data[].bidding_start_date`, `bidding_end_date` | string | **VERIFIED** always present, `YYYY-MM-DD` | `YYYY-MM-DD`. |
| `data[].total_subscription` | string | **VERIFIED** always present, decimal string (e.g. `"200.08"`, `"0.0"`) | Decimal subscription multiple, e.g. `"10.0"`. |
| `data[].investors` | array | **UNDOCUMENTED FIELD.** Present on every one of the 6 live IPO records seen, always `[]` in this sample — a subscribing-investor list not mentioned anywhere in the docs. Item shape is **NOT OBSERVED** (always empty here); do not model its element type without further evidence. | Not documented. |
| `meta_data.page.page_number`, `total_pages`, `records`, `total_records` | integer | **VERIFIED** all 4 present and internally consistent (e.g. `records=5, total_records=101, total_pages=21` for the `listed` call) | Pagination. |

### Documentation example response (copied)

```json
{
  "status": "success",
  "data": [
    { "id": "yaashvi-jewellers-limited-ipo", "symbol": "YAASHVI", "name": "Yaashvi Jewellers IPO", "status": "open", "isin": "INE1T6L01010", "issue_type": "sme", "issue_size": 44, "industry": "Diamond & Jewellery", "minimum_price": 83, "maximum_price": 83, "bidding_start_date": "2026-05-25", "bidding_end_date": "2026-05-27", "total_subscription": "0.0" },
    { "id": "m-r-maniveni-foods-limited-ipo", "symbol": "MANIVENI", "name": "M R Maniveni Foods IPO", "status": "open", "isin": "INE0YD301010", "issue_type": "sme", "issue_size": 27, "industry": "Consumer Food", "minimum_price": 51, "maximum_price": 52, "bidding_start_date": "2026-05-22", "bidding_end_date": "2026-05-26", "total_subscription": "1.27" }
  ],
  "meta_data": { "page": { "page_number": 1, "total_pages": 1, "records": 2, "total_records": 2 } }
}
```

### Errors

`UDAPI1219` invalid IPO status; `UDAPI1220` invalid issue type. **NOT
OBSERVED** (no error-path probe run against this endpoint).

## `GET /v2/ipos/{id}`

**NOT OBSERVED in this pass** — `/v2/ipos/{id}` was out of the stated Tier 2
scope (only `/v2/ipos` was listed). Everything below is still doc-derived,
unverified content.

Documentation: [Get IPO Details](https://upstox.com/developer/api-documentation/get-ipo-details?utm_source=equity-os)

### Request

`id` is a required string path parameter, an IPO slug obtained from the list
endpoint. No query parameter or size limit is documented.

### Response fields

| Field | Type | Presence / nullability | Meaning |
|---|---|---|---|
| `status` | string | UNDOCUMENTED / UNDOCUMENTED | `success` or `error`. |
| `data.id`, `symbol`, `name`, `isin`, `industry` | string | UNDOCUMENTED / UNDOCUMENTED | Identity and industry. |
| `data.status` | string | UNDOCUMENTED / UNDOCUMENTED | `open`, `closed`, `listed`, `upcoming`. |
| `data.issue_type` | string | UNDOCUMENTED / UNDOCUMENTED | `regular` or `sme`. |
| `data.issue_size`, `minimum_price`, `maximum_price`, `face_value`, `tick_size`, `cut_off_price`, `listing_price` | number | UNDOCUMENTED / docs explicitly say `tick_size` and `listing_price` can be `null` | Crore/INR fields as described by the endpoint. |
| `data.bidding_start_date`, `bidding_end_date` | string | UNDOCUMENTED / UNDOCUMENTED | `YYYY-MM-DD`. |
| `data.daily_start_time`, `daily_end_time` | string | UNDOCUMENTED / UNDOCUMENTED | `HH:MM:SS` IST. |
| `data.lot_size`, `minimum_quantity` | integer | UNDOCUMENTED / UNDOCUMENTED | Shares per lot and minimum application quantity. |
| `data.listing_exchange` | string | UNDOCUMENTED / UNDOCUMENTED | `BSE`, `NSE,BSE`, etc. |
| `data.rhp_url`, `drhp_url` | string | UNDOCUMENTED / docs say each can be `null` when unavailable | Prospectus URLs. |
| `data.timeline` | object | UNDOCUMENTED / UNDOCUMENTED | Eight timeline date strings: `pre_apply_start_date`, `application_start_date`, `application_end_date`, `allotment_start_date`, `allotment_date`, `refund_initiation_date`, `listing_date`, `mandate_end_date`. |
| `data.registrar_info` | object | UNDOCUMENTED / UNDOCUMENTED | Six strings: `name`, `email`, `contact_name`, `contact_number`, `website`, `registrar`. |
| `data.total_subscription` | string | UNDOCUMENTED / UNDOCUMENTED | Decimal subscription multiple. |

`minimum_price` and `maximum_price` are numbers and may be `0` before
announcement. `tick_size`, `listing_price`, `rhp_url`, and `drhp_url` are
explicitly documented as nullable in the stated conditions; no other response
nullability is documented.

### Documentation example response (copied)

```json
{
  "status": "success",
  "data": {
    "id": "autofurnish-limited-ipo",
    "symbol": "AFLTD",
    "name": "Autofurnish IPO",
    "status": "open",
    "isin": "INE18HI01019",
    "issue_type": "sme",
    "issue_size": 15,
    "industry": "Automobile Two & Three Wheelers",
    "minimum_price": 41,
    "maximum_price": 41,
    "bidding_start_date": "2026-05-21",
    "bidding_end_date": "2026-05-25",
    "daily_start_time": "10:00:00",
    "daily_end_time": "17:00:00",
    "face_value": 10,
    "tick_size": null,
    "lot_size": 3000,
    "minimum_quantity": 6000,
    "cut_off_price": 41,
    "listing_price": null,
    "listing_exchange": "BSE",
    "rhp_url": null,
    "drhp_url": "https://www.bsesme.com/download/325882/SME_IPO%20InPrinciple/DP_Autofurnish_Final_20250930195434.pdf",
    "timeline": {
      "pre_apply_start_date": "2026-05-20",
      "application_start_date": "2026-05-21",
      "application_end_date": "2026-05-25",
      "allotment_start_date": "2026-05-26",
      "allotment_date": "2026-05-27",
      "refund_initiation_date": "2026-05-27",
      "listing_date": "2026-05-29",
      "mandate_end_date": "2026-07-06"
    },
    "registrar_info": {
      "name": "SKYLINE FINANCIAL SERVICES PRIVATE LIMITED",
      "email": "virenr@skylinerta.com",
      "contact_name": "Mr. Anuj Rana",
      "contact_number": "+91-11-40450193-97",
      "website": "https://www.skylinerta.com/",
      "registrar": "SKYLINE"
    },
    "total_subscription": "0.68"
  }
}
```

### Errors

`UDAPI100500` — IPO data not found for Id.

### Strict-parser hazards

Dates are ISO strings, daily times are `HH:MM:SS`, URLs and subscription
multiples are strings, and several numeric/URL fields are explicitly `null` in
the documented example. IPO list and detail responses use `meta_data` only on
the list endpoint.
