# Upstox integration plan (v2)

**Owner:** `eqos-rdb`. **Hands persistence off to:** `eqos-f2m`.
**Supersedes** `scratchpad/upstox/PLAN-sol.md` (v1). Every blocking item and
every should-fix in `scratchpad/upstox/REVIEW-opus.md` is dispositioned in
[§14](#14-disposition-of-the-review), including the ones this plan declines.

**API authority:** `docs/research/upstox-api-surface-inventory.md` (rows graded
**A** are verified by live request and are treated as settled) and
`docs/research/upstox-api-schemas/*.md`, verified against 129 live responses and
a full census of two static files. Where this plan states a fact, it states its
grade. Where the evidence is silent, it says so and recommends rather than
asserts.

---

## 1. What this builds

A **read-only vendor-evidence acquisition lane**. It fetches, retains, and types
ten Upstox GET surfaces across two lanes. It produces artifacts and typed
records. It produces no facts, no canonical corporate actions, and no security
lifecycle state.

**Lane A — acquisition.** Six surfaces with no XBRL or Screener counterpart.

| Surface | Host | Auth |
|---|---|---|
| Daily adjusted candles, backfill to 2000 + incremental tail | `api.upstox.com` | Bearer |
| `complete.json.gz` and `suspended-instrument.json.gz` | `assets.upstox.com` | none |
| Corporate actions (per ISIN) | `api.upstox.com` | Bearer |
| Shareholding (per ISIN) | `api.upstox.com` | Bearer |
| Market holidays | `api.upstox.com` | Bearer |
| FII / DII activity | `api.upstox.com` | Bearer |

**Lane B — Screener parse-check (added 2026-09-03, owner decision).** Four
statement/ratio surfaces, plus a comparator over the shareholding already
fetched in Lane A.

| Surface | Compared against | Basis |
|---|---|---|
| `income-statement` (`fs=true`, yearly + quarterly) | Screener P&L and quarters | consolidated + standalone |
| `balance-sheet` (`fs=true`, yearly only) | Screener balance sheet | consolidated + standalone |
| `cash-flow` (`fs=true`, yearly only) | Screener cash flow | consolidated + standalone |
| `key-ratios` (current snapshot) | Screener quick ratios | consolidated + standalone |
| `share-holdings` (already fetched in Lane A) | Screener shareholding | n/a |

**Lane B exists to detect Screener *scraping* error, not to adjudicate truth.**
The independence test (`scratchpad/upstox/probes/independence-test/`) proved
these endpoints share lineage with Screener — `operating_profit` is Screener's
profit-before-tax, 12/12 across three companies and both bases, and Upstox
reproduces Screener's divergence from the BSE filing on TITAN Jun-2026 net
profit (1777 vs the filed 1699.00).

Shared lineage disqualifies Lane B as a third opinion and makes it usable as a
**differential anomaly check**.

**Corrected 2026-09-03 after external critique (Codex GPT-5.6 Sol).** An earlier
version of this section said a disagreement "isolates to one cause — our HTML
parse read the page wrong." That does not follow and is withdrawn. A
disagreement means only that two representations differ. Alternative causes,
none of which the check can distinguish on its own:

1. Refresh or restatement timing. Upstox exposes no as-of or version field and
   only a rolling four-period window.
2. Different aggregation, classification, or formula.
3. Different precision or rounding (Upstox returns decimals; Screener displays
   integer crore — see §6.9).
4. An Upstox-side transformation or schema defect.
5. Period, basis, or issuer misalignment inside our own comparator.
6. Screener rendering a genuine vendor-side error that our parser extracts
   correctly.

So the two outcomes are weaker than first stated, and both are *triage
directions*, not diagnoses:

- **Upstox ≠ Screener** → inspect the retained Screener artifact for this cell
  before classifying anything. It may be our parser; it may be any of the six
  above.
- **Upstox = Screener ≠ XBRL** → the two renderings agree, so a parser defect is
  less likely and a vendor-versus-filing disagreement is more likely.

Today `needs_human_review` gives no directional signal at all. Lane B gives one.
That is the honest claim, and it is smaller than the claim this section
originally made.

**Lane B is barred from voting.** Its values never become facts, never enter
`FactStore`, never enter reconciliation, and never change whether a fact ships.
**Corrected 2026-09-03.** An earlier version justified this bar by saying a
leak would manufacture "a false 2-vs-1 majority — TITAN Jun-2026 would ship
1777." That mechanism does not match the code and is withdrawn.
`src/fundamentals/reconcile/agreement.py:43` marks a source derived only if its
id contains `screener` or `tijori`; derived sources corroborate but never
satisfy the two-first-party requirement. So Screener does not vote today, and no
majority forms.

The real hazard is worse and runs the other way: **`upstox` matches neither
marker, so a leaked Upstox value would be classified `first_party`** — the
highest authority the system has, granted by string default to the one source
proven non-independent. Verified locally: both `upstox` and `upstox-fundamentals`
resolve to `first_party` under the current markers.

Enforcement must therefore be a typed, fail-closed evidence role checked at the
reconciliation entry point, not an import scan (§10).

**Out of scope, and why**

- **`profile` and `competitors`.** Neither has a Screener counterpart to check,
  so neither serves Lane B's purpose. **No URL builder in this codebase may
  construct these paths**, enforced by a scope test (§10). (`competitors` also
  carries an integration hazard: its path takes `NSE_EQ|<isin>`, not a bare
  ISIN.)
- Quotes, `prev_ohlc`, market status, market timings, intraday candles, expired
  instruments, option chain, news, IPOs.
- Orders, portfolios, funds, accounts, OAuth login, money movement — barred
  outright by product invariant 12 (`.claude/project/invariants.md`): no order
  APIs, broker credentials, or portfolio state in the research system.
- `FactStore` promotion, authoritative corporate actions, S17 lifecycle state.
- Cron/scheduler deployment. This work ships deterministic commands; scheduling
  them is somebody else's decision.

## 2. Why none of this may enter `FactStore`

`src/fundamentals/store/fact_store.py:117` bars `API_DOCUMENT` (alongside
`CONFIG_PIN`) from the store, and its module docstring gives the reason: an API
response *"carries no identity field of its own, so the only binding to an issuer
is the id in the request URL. That is enough to acquire and retain a document,
but not to let a value join the canonical revision chain, where content identity
is assumed to be corroborated by the source."*

Every Upstox response in scope is anchored `API_DOCUMENT`. So:

- **No module in this plan imports `FactStore`.** Asserted by a test (§10).
- Corporate actions and shareholding are **vendor observations**, not events.
- A changed adjusted candle is **a new source-series version**, not
  automatically a corporate-action restatement (§7.4). Upstox's own
  corporate-action endpoint is not independent evidence explaining a change in
  Upstox's own candles.

**The one asymmetry that survives, and it is the sharpest idea in v1:** a bulk
instrument file is **self-describing** — it publishes ISIN, trading symbol and
exchange token side by side for 117,344 records nobody asked about by name — so
it *may* assert identity into `EntityMap`. A per-ISIN response is
**request-bound** — the only thing tying the payload to the issuer is the ISIN we
put in the URL — so it *may not*. The instrument file is the only Upstox surface
that emits `SourceRecord`s.

## 3. Gate 0 — preconditions before live code runs

1. **Rights.** Record the exact Upstox authorization for automated access,
   caching, retention, transformation, and private/internal output. Fixture-only
   implementation may proceed without it; live capture and any scheduled refresh
   stay disabled until it exists.
   **Drafted 2026-09-04: `docs/research/upstox-rights-record.md`, state
   `PROPOSED`. It authorizes nothing** — several dimensions are `UNKNOWN`, and
   under S02 §6.3 an `UNKNOWN` denies its operation. Two findings change this
   section's assumptions. First, the personal-use / internal-use carve-out this
   plan's evaluation doc relied on **does not exist** in the terms; the phrase
   was checked and is absent. Second, the **unauthenticated instrument files are
   the least covered surface, not the most**: the terms' prohibition is scoped to
   "materials on our website", which is plainly what they are, while the staff
   permission that does exist is explicitly about endpoints "requiring an Upstox
   API access token" — which the assets host does not. Slice 1 was ordered first
   because it was operationally cheapest; that ordering does not carry over to
   which live run should be authorized first.
2. **Ownership.** `eqos-rdb` owns this adapter. `eqos-kx4.4` owns the snapshot
   store and the outcome taxonomy; this plan deliberately builds neither (§8).
3. **S17 G02/G03** block authoritative entity/action promotion. They do not
   block raw acquisition.
4. **One live error-envelope probe** for `/v2/fundamentals/*` — a Slice 3
   precondition, not a Gate 0 one (§9.3, review S5).

---

## 4. The verified facts that drive the design

These are not background. Each one silently corrupts data if missed — which is
exactly what happened to v1, where four of them appear zero times in 626 lines.
Every row here has a named test in §9.

| # | Fact | Grade | What breaks without it |
|---|---|---|---|
| F1 | **Path order is `to_date` BEFORE `from_date`**: `/v3/historical-candle/{instrument_key}/{unit}/{interval}/{to_date}/{from_date}` | A | Reversing returns a **wrong window with HTTP 200**, no error. A 2000–2010 backfill written the natural way asks for to=2000, from=2010, and wrong history is content-hashed and stored as evidence. |
| F2 | **Candle rows arrive most-recent-first** | A | v1's only ordering sentence said the opposite ("ascending canonical order"), so read as validation it rejects 100% of live responses; read as an assumption it hashes a reversed series. |
| F3 | **`instrument_key` is `SEGMENT\|ISIN`** (e.g. `NSE_EQ\|INE009A01021`); the pipe **must be percent-encoded** in a path segment (`%7C`) | A | An unencoded pipe is a malformed path segment; behaviour is not ours to rely on either way. |
| F4 | **Corporate-action `expiry_date` is `"14 Aug 2025"`** (`dd Mon yyyy`), 108/108 observed | A | Pydantic v2 parses ISO-8601 and raises on this in **both** lax and strict mode. A `date`-typed field rejects every real event — total Slice 3 outage. |
| F5 | **Shareholding `period` is `"Mon yyyy"`**, a **rolling 4-quarter window** | A | Same parse failure; and treating the window as a static snapshot silently loses every quarter older than four, which exists only in our own captures. |
| F6 | **Instrument-file fields are omitted, not defaulted** — `cas_eligible` is present only when true; `short_name` and `security_type` are absent on real records; `security_type` does not exist at all on `BSE_EQ` | A (full census) | A required field drops a large share of the universe. The rule is **"optional and omission-preserving"**. **No prevalence percentage enters code** — the brief and the schema report quote different numbers because they used different denominators, and neither denominator is a fact about an instrument. |
| F7 | **Holiday openness is per-exchange, read from `open_exchanges`/`closed_exchanges` — never from `holiday_type`** | A | `2024-01-01` is `TRADING_HOLIDAY` with `closed_exchanges: []` and NSE in `open_exchanges`. NSE traded. Reading the type marks a live session closed. |
| F8 | **A `days` range over 10 years returns HTTP 400 `UDAPI1148`**; exactly ten years returns HTTP 200 with a full untruncated series | A | A naive 2000→today request fails, so the backfill must be windowed — into exactly three ten-year windows, not a guessed safety margin. |
| F9 | **The candle error envelope has no `data` key**, wraps errors in an array, and duplicates every field in camelCase *and* snake_case: `{"status":"error","errors":[{...}]}` | A | Success-shaped error handling breaks on the first 4xx; picking one casing breaks on the other. |
| F10 | **Candle timestamps are ISO-8601 strings** with the `+05:30` offset, despite the docs table saying "number" | A | Type-column trust produces a parser that never runs. |
| F11 | **The default `Python-urllib` User-Agent is blocked at Cloudflare** with 403 / error 1010 | A | It is **not retryable** and never clears on backoff. Retrying it burns the budget and reports the wrong cause. |
| F12 | **A successful empty array is real**: 28/83 ISINs have no corporate-action history; holidays and timings return `data: []` for a non-holiday date | A | Reading empty as failure marks real companies as unacquirable. |

Two more that are *not* graded A and are handled as assumptions, not facts:

- **`UDAPI1149` → plan-locked.** Its HTTP status is grade **D**; this account has
  Plus, so it cannot be exercised and no fixture exists (review S11).
- **OHLC relationships** (`high >= max(open, close)`) are **not established** by
  any of the 129 responses. They are recorded as anomalies, never enforced
  (review S13).

---

## 5. Module layout

Ten source modules, **three** CLI commands — eight modules and two commands for Lane A (§1), plus two modules and one command for Lane B (Slice 6). v1 proposed eighteen modules, six
commands and a bespoke SQLite database for six read-only GETs; house rule is the
minimum code that solves the problem (`.claude/rules/core/03-ak-guidelines.md`
§2). The accounting for what was cut is in §14 (S10).

| File | Responsibility | Slice |
|---|---|---|
| `src/fundamentals/ingest/http_session.py` | **Extracted, not new.** `NoRedirectHandler`, `RequestPacer` (monotonic spacing), `read_bounded`. Zero source semantics. | 1 |
| `src/fundamentals/ingest/upstox_source.py` | Config, credentials, typed errors, pinned hosts, path templates and URL builders, GET transport, hashing, byte caps, retry, outcome classification, `redact`. | 1 |
| `src/fundamentals/ingest/upstox_instruments.py` | Bounded gzip decode, equity-row filter, instrument models, `UpstoxInstrumentCatalog`. | 1 |
| `src/fundamentals/entity/upstox_entity_source.py` | Reads a retained catalog artifact **from disk** and emits `SourceRecord`s. Opens no socket. | 1 |
| `src/fundamentals/ingest/upstox_candles.py` | Window planning, wire parsing, canonicalisation, series versions, version comparison. | 2 |
| `src/fundamentals/ingest/upstox_company.py` | Corporate-action and shareholding wire models, typed records, wire-date parsing. | 3 |
| `src/fundamentals/ingest/upstox_market.py` | Holidays + `TradingCalendar` (Slice 4); FII/DII (Slice 5). | 4, 5 |
| `src/fundamentals/ingest/upstox_sync.py` | **Pure planner.** Deterministic plan from `as_of_date` + on-disk state. No I/O. | 4 |
| `src/fundamentals/api/upstox_cli.py` | Both commands, their dispatch, artifact writing, exit codes. | 1–5 |

**Modified:** `api/cli_parser.py` (register two commands), `api/cli.py` (read
`UPSTOX_ANALYTICS_TOKEN` at the composition root, wrap in `SecretStr`),
`api/entity_map_cli.py` (one optional `--upstox-catalog` flag, Slice 1),
`ingest/screener_session.py` (import the three extracted helpers, delete its
private copies), and the three `__init__.py` export lists.

**Commands**

```
fundamentals upstox --surface {instruments|candles|corporate-actions|share-holdings|holidays|fii-dii} ...
fundamentals upstox-sync --as-of-date YYYY-MM-DD ...
fundamentals upstox-crosscheck --isin-file <path> --screener-root <dir> ...   (Slice 6, Lane B)
```

Not ten commands. The repo's per-family dispatch module (`screener_cli_dispatch.py`,
`tijori_cli_dispatch.py`) is a convention this deliberately does not follow while
there are only three commands — a stated deviation, not an oversight. Extract one
if a fourth command arrives.

Lane B adds two source modules, both new files, neither importing `fact_store`:

```
ingest/upstox_statements.py     Pydantic models, four Lane B responses          Slice 6
ingest/screener_crosscheck.py   frozen name map, comparator, outcome enum       Slice 6
```

### 5.1 The `http_session.py` extraction

`ingest/screener_session.py` already contains `_NoRedirectHandler`,
`assert_pinned_origin`, `_redact_private_query`, `_wait_for_slot` on a monotonic
clock, bounded exponential backoff, `SecretStr` injection, `DEFAULT_USER_AGENT`,
and `TERMINAL_BLOCK_STATUSES = {403, 451}`. A seventh reimplementation of the
polite fetcher is a real cost (review S1), and 403-already-terminal *is* the
Cloudflare-1010 case.

**Extract exactly three things, all semantics-free:**

1. `NoRedirectHandler` — verbatim.
2. `RequestPacer` — `_wait_for_slot`'s monotonic spacing, as a tiny class.
3. `read_bounded(response, max_bytes) -> bytes` — the read-one-extra-byte cap.

**Leave per-adapter:** origin pinning (different hosts), terminal statuses
(different meanings), auth header shape (cookie vs Bearer), error taxonomy,
redaction. These genuinely differ; unifying them would invent a shared
abstraction over two things that disagree.

`tests/fundamentals/test_screener_session.py` runs **unchanged** as the
characterization harness for the refactor. If the coordinator judges the
in-flight risk too high — `eqos-kx4.3.5` (Screener Slice 3) is open and touches
this file — the fallback is to copy the three helpers into `upstox_source.py`
with a comment naming their origin, and file a bead. Recommendation: extract; it
is ~40 lines with an existing red-proof harness. See §12 D1.

---

## 6. Contracts

All models: `from __future__ import annotations`, frozen Pydantic v2
(`model_config = ConfigDict(frozen=True)`), `arbitrary_types_allowed=False`, no
`float` on any monetary or price field, collections as `tuple[...]` in an
explicitly stated order.

### 6.1 Transport and outcome

```python
UPSTOX_API_ORIGIN    = "https://api.upstox.com"      # Bearer token goes ONLY here
UPSTOX_ASSETS_ORIGIN = "https://assets.upstox.com"   # never receives the token
DEFAULT_USER_AGENT   = "EquityOS Research"           # honest, required (F11)
```

`UpstoxCredentials(access_token: SecretStr)` — constructed only in `api/cli.py`
from `UPSTOX_ANALYTICS_TOKEN`. No business-logic module reads the environment
(`.claude/rules/python/safety.md`).

The Analytics Token materially de-risks this work and its properties are grade A:
**one year of validity, read-only GET only, one per account, no authorization
redirect and no daily login**, and **every surface in scope is on Upstox's
no-static-IP-required list** — proven end-to-end by a live v3 candle request. The
static-IP list is almost exactly our EXCLUDE list (User, Payments, Orders, GTT,
Portfolio, Mutual Fund, Trade P&L), which is a pleasant coincidence rather than a
control we rely on.

**Rate limits** (documented, "Other Standard APIs" bucket, which covers
everything we call): **50 req/s, 500/min, 2,000 per 30 minutes**. The 30-minute
bucket binds at **~1.1 req/s sustained**; the 50/s is burst headroom only. No 429
was ever observed, so this is documented rather than grade A. Default
`min_request_spacing_seconds` is **1.1**, matching the spacing both probe runs
used (~175 GETs, no throttling). `assets.upstox.com` is not described as subject
to this bucket.

`UpstoxConfig` — frozen, injected at construction, bounding every knob the
Screener config bounds plus two of its own:
`credentials`, `user_agent`, `request_timeout_seconds`,
`min_request_spacing_seconds`, `max_rate_limit_retries`,
`rate_limit_backoff_seconds`, `max_compressed_bytes`, `max_decompressed_bytes`,
`max_requests_per_run`, `retrieved_at` supplier.

Two validators that are not decoration:

- **Refuse a dishonest User-Agent** at construction: empty, or beginning
  `Python-urllib`. F11 makes this a correctness rule, not politeness.
- **Bound the total retry budget**, copying `ScreenerSessionConfig`'s
  `_check_retry_budget_is_bounded`.

`AcquisitionOutcome` — a **local** enum in `upstox_source.py`, explicitly *not* a
shared contract. `eqos-kx4.4` owns the shared taxonomy; publishing a competing
one under `contracts/` is precisely the mistake B3 exists to prevent. Members:

| Member | Trigger | `retryable` |
|---|---|---|
| `OK` | success with rows | — |
| `OK_EMPTY` | `status == "success"` and `data == []` (F12) | — |
| `CLIENT_BLOCKED` | 403 / Cloudflare 1010 (F11) | **False** |
| `AUTH_EXPIRED` | 401 | False |
| `RATE_LIMITED` | 429 | True, bounded |
| `REQUEST_REJECTED` | parsed non-retryable 400, incl. `UDAPI1148` (F8) | False |
| `PLAN_LOCKED` | `UDAPI1149` — **unverified assumption**, no fixture (S11) | False |
| `SCHEMA_DRIFT` | envelope or row shape not recognised | False |
| `TRANSPORT_ERROR` | timeout, DNS, connection reset | True, bounded |

Missing local credentials raise `UpstoxCredentialsError` **before any request** —
that is a configuration defect, not `AUTH_EXPIRED`.

`UpstoxErrorEnvelope` models F9 exactly: no `data` key, `errors` as an array,
and both casings read. **If the camelCase and snake_case values of one field
disagree, that is `SCHEMA_DRIFT`** — not a coin flip.

### 6.2 Raw capture

```python
class UpstoxCapture(BaseModel):        # frozen
    surface: UpstoxSurface
    request_url: str                   # token is a header; never in a URL
    http_status: int
    media_type: str | None
    byte_count: int
    content_sha256: str
    outcome: AcquisitionOutcome
    retrieved_at: datetime             # from the injected supplier
```

**The hash is taken over the raw bytes before anything else touches them** —
before decompression, before decoding, before `json.loads`, before validation.
The model is never the entry point. A corrupt gzip or an unparseable body still
produces a capture with a hash and a `SCHEMA_DRIFT` outcome; the bytes are
retained so a reviewed parser upgrade can re-read them later.

`raw_body` is deliberately **not** a model field. It is passed alongside as
`bytes` and written by `write_bytes_no_clobber`, so the bytes on disk are
byte-identical to the ones whose sha256 the metadata records — the property
`artifact_writer.write_bytes_no_clobber` was written to preserve.

**Decimal rule.** Every JSON body is read with
`json.loads(text, parse_float=Decimal)` in one shared helper. No monetary,
price, ratio or holding-percentage field is ever `float`. Pydantic v2 serialises
`Decimal` to a JSON *string*, so `model_dump_json` round-trips losslessly. Note
that `parse_float` covers JSON *numbers* only: `event_details[].value` arrives as
a **string** in 748/748 observed values, so any number read from there is
`Decimal(text)`, parsed explicitly (§6.5).

**Why the raw bytes are the only restatement detector.** **No response on any
surface carries a server-side as-of, version, or last-updated field** — confirmed
across all eight fundamentals response schemas. A silent restatement is therefore
undetectable from the payload's own content. Detection must be our own hash of
the **raw bytes**, never of a re-serialised structure, and a `float` round-trip
anywhere in that path would break it. This is also why the `upstox-python-sdk` is
rejected in favour of direct `urllib`: it hands back parsed objects, types
candles as `list[list[object]]`, and never exposes the bytes provenance needs.

### 6.3 Provenance

Reuse `Provenance` with `anchor_type=API_DOCUMENT`. No Upstox-specific
provenance type. `API_DOCUMENT` requires `document_id`, `context_ref`,
`table_key`, `row_label`, `column_label`, and **bars** `island_id`, `table_id`,
`row_path`, `column_index` (`contracts/provenance.py:60`, `_FOREIGN_ANCHOR_FIELDS`).

| Field | Value |
|---|---|
| `source_id` | `upstox` |
| `file_sha256` | the raw-body sha256 |
| `document_id` | `upstox:<surface>:<content_sha256>` |
| `context_ref` | the request URL (token is a header, so nothing to redact) |
| `table_key` | the surface name |
| `row_label` | `instrument_key`, ISO date, `"Mon yyyy"` period, or holiday date |
| `column_label` | the exact wire field name |
| `retrieved_at` | from the injected supplier, or the artifact's recorded time when reading from disk |

**`retrieved_at` and determinism (review S2).** `Provenance.retrieved_at` is
required wall-clock, so two runs over identical bytes cannot produce
byte-identical artifacts. v1 injected a **monotonic** clock — the wrong clock for
a wall-clock field. This plan:

- injects a `retrieved_at` supplier (`Callable[[], datetime]`, default
  `lambda: datetime.now(tz=UTC)`); the monotonic clock stays for pacing only;
- reads `retrieved_at` **from the artifact's recorded content** when the entity
  adapter loads a catalog from disk — never from filesystem mtime, for exactly
  the reason `entity_map_sources.py:11-17` gives (an mtime is restamped by any
  clone, so CI could never byte-match a developer's build);
- defines `canonical_parsed_digest(artifact)` — sha256 over the parsed artifact
  with `retrieved_at`, `fetched_at` and the capture id removed. **Byte-identity
  tests assert on this digest, not on the file.** The determinism guarantee is
  stated honestly as: *identical bytes in, identical canonical digest out.*

`UNRECORDED_RETRIEVAL` (`entity_map_sources.py:48`) is **not** used here. We do
know the retrieval time; a sentinel would say "unrecorded" about something
recorded.

### 6.4 Instruments (Slice 1)

Files (no token, `assets.upstox.com`):

```
/market-quote/instruments/exchange/complete.json.gz             117,344 records
/market-quote/instruments/exchange/suspended-instrument.json.gz  33,930 records
```

`suspended-instrument` is **singular**; the plural spelling 404s. Both are a
top-level JSON array.

`instrument_key` is **read from the file, never constructed**. For retained
equity rows it is validated to contain exactly one `|`, with the segment before
it matching the record's own `segment` field (F3). Equity keys are `SEGMENT|ISIN`
(`NSE_EQ|INE002A01018`), which is why a dual-listed issuer yields both
`NSE_EQ|<isin>` and `BSE_EQ|<isin>` — two different adjusted series (§6.6).
Non-equity keys use other shapes (`NSE_FO|36708`, `BSE_INDEX|AUTO`); we retain no
such rows.

Always-present fields on both `NSE_EQ`/`EQ` (2,639 rows) and `BSE_EQ`/`A` (699
rows), verified by full census: `segment`, `exchange`, `name`, `isin`,
`instrument_type`, `instrument_key`, `trading_symbol`, `exchange_token`
(**string**, not the number the docs claim), `lot_size` (int), `freeze_quantity`
(float), `tick_size` (float). ISIN is present on 100% of equity rows
(22,433/22,433).

Trap fields, all optional and **omission-preserving** (F6):

```python
short_name:    str | None = None
security_type: str | None = None      # absent on every BSE_EQ record
cas_eligible:  bool | None = None     # present only when true; None means absent
mtf_enabled:   bool | None = None
mtf_bracket:   Decimal | None = None  # a number when present; None means absent
```

`None` means *the file did not carry it* and must stay distinguishable from
`False`. A derived read-only property may present absence-as-false for
`cas_eligible`/`mtf_enabled` where a consumer wants a boolean. `mtf_bracket` gets
no such property: it is numeric, and absence-as-false on a number is a category
error (review NOISE).

**No prevalence percentage appears in code or in a code comment.** The rule is
the sentence above, full stop.

**Unknown keys.** `extra="ignore"` on the model, plus a **non-fatal unknown-key
census** written into the parsed artifact's review section. `extra="forbid"`
would turn a harmless vendor addition into a total failure across a
117,344-record file; ignoring silently would hide drift. Recording it does
neither.

**Discriminated-union routing is cut** (review S10). Only equity rows are
retained, so the routing is a filter on `segment`/`instrument_type` **before**
validation, not a discriminator over record shapes we throw away.

The suspended file is fetched, hashed, parsed with its own model and written as
an artifact. Its schema is the cleanest in the whole verification pass — exactly
**12 fields, 100% present across all 33,930 records**, nothing optional, no type
surprises: the eleven above minus `freeze_quantity`'s companions, plus
`qty_multiplier` (float), and **without** `short_name`, `security_type`,
`cas_eligible`, `mtf_enabled`, `mtf_bracket`. It is all equity, all with an ISIN,
and it is our only delisting/suspension signal.

Rows are **grouped by ISIN, never destructively de-duplicated**: a file carries
multiple rows per ISIN, one per series, and collapsing them discards the series
distinction that is the only thing telling them apart. (A handful of rows carry a
sentinel `lot_size`/`freeze_quantity` of `999999999` — a data-quality curiosity,
not a schema issue; retained as-is, not "corrected".)

It **emits no assertions and has no code consumer**. v1's
`SuspendedInstrumentMatch` "candidate-match report" is cut: it was never
requested, and a matching report whose matches nothing may act on is a
deliverable in search of a user.

### 6.5 Corporate actions and shareholding (Slice 3)

**Two layers**, following the repo's lexeme convention
(`screener_company_artifacts.py:16-20`: *"every number carries the lexeme it was
read from beside it"*):

- `...Wire` models take the field exactly as it arrives — `expiry_date: str`,
  `period: str`, amounts already `Decimal` from `parse_float`.
- Typed records carry **both** the lexeme and this contract's reading of it:
  `expiry_date_text: str` **and** `expiry_date: date`; `period_text: str` **and**
  `period_year: int`, `period_month: int`.

**Wire date parsing (F4, F5).** One module-level constant, one function each:

```python
_MONTH_ABBREVIATIONS: dict[str, int] = {"Jan": 1, "Feb": 2, ..., "Dec": 12}

def parse_wire_date(text: str) -> date:            # "14 Aug 2025"
def parse_wire_period(text: str) -> tuple[int, int]  # "Mar 2025" -> (2025, 3)
```

**Never `strptime("%d %b %Y")`.** `%b` is locale-dependent: it breaks under any
non-C `LC_TIME`, which is a property of the machine running the job, not of the
data. An explicit map cannot drift with an environment variable.

Wire shapes, both `{"status": "success", "data": [...]}`:

```
/v2/fundamentals/{isin}/corporate-actions   # bare ISIN in the path, no query params
  data[] = {name, expiry_date, amount, ratio, event_details[{name, value}]}

/v2/fundamentals/{isin}/share-holdings      # bare ISIN, no query params
  data[] = {category, history[{period, value}]}   # exactly 5 categories x 4 periods
```

The path takes a **bare ISIN**, not an `instrument_key` — the `SEGMENT|ISIN` form
is required only by `competitors`, which is out of scope. So no pipe encoding
applies here; it applies to candle paths (§6.6) and to the FII/DII `data_type`
**query value** (§6.8).

`event_details[].value` is **always a string** — 748/748 values across 108
events, dates, ratios and amounts alike. Any number read from it is
`Decimal(text)`, parsed explicitly; `parse_float` never sees it.

Other decisions:

- `CorporateActionName` is exactly `Dividend`, `Bonus`, `Rights Issue`, `Split`.
  **`"Rights Issue"`, never `"Rights"`** — the docs' own example is wrong and a
  docs-derived enum rejects 2 of 108 real events.
- `amount` is a **required** `Decimal` including `Decimal("0.0")` — it is always
  present, and zero for non-dividend events. Not conditionally absent.
- `ratio` is `str | None` — `null` in all 102 `Dividend` events, non-null in all
  six `Bonus`/`Split`/`Rights Issue` events, zero exceptions. Observed forms:
  `"4:1"`, `"1:10"`, `"7:40"`. This is the input to the §6.6 ratio check.
- `event_details[].name` stays an **open string**. Eight values were observed for
  `Dividend type` (`Final`, `Interim`, `Misc.Income`, `Interest`, `Dividend`,
  `RepayOfSPVLvlDebt`, `Other Income`, `Special`) against the docs' single
  example — a docs-derived enum would reject 57 of 102 real records. Closing it
  is a bet the evidence does not support.
- Only four action types appear in 108 events. **Do not assume the enum is
  exhaustive**; a fifth type fails closed with the bytes retained (§9.3 risk).
- A **vendor event digest** over (requested ISIN, name, date, amount, ratio,
  ordered details) gives a stable local handle. It is explicitly **not** an
  authoritative action id.
- `ShareholderCategory` is exactly `promoters`, `fii`, `other_dii`,
  `mutual_funds`, `retail_and_other` — stable across all five companies observed.
  **Order varies by company** (the docs' own example puts `mutual_funds` fourth;
  four of five live companies put it last), so **never index by position**.
  Require each category exactly once (missing or duplicated is `SCHEMA_DRIFT`);
  ignore the provider's order; serialise in enum order.
- `history[].value` is a percentage, `Decimal`, never null and never omitted —
  **including at literal `0.0`**, which one observed company carries for three
  categories across all four periods. Zero is preserved, not dropped.
- Upstox publishes **percentages only, no pledge data** (Screener does). Recorded
  so nobody later reads the absence as a zero.

**Shareholding is a rolling window, not a snapshot (F5, review S8).** Each
response carries four quarters. Anything older exists only in our own captures.
So: retain every capture, and provide
`compose_shareholding(captures) -> tuple[ShareholdingPeriod, ...]` — the union
across captures, ordered by period, with a `restated: bool` on any period whose
value differs between two captures. Restatements are listed in the run's review
artifact. This is the same *shape* of problem as candle revisions but a different
key space, so it reuses the idea, not the code.

### 6.6 Candles (Slice 2)

**The path template is one pinned constant, sitting directly beside the field
index map, with F1 in a comment at the site:**

```python
# to_date comes BEFORE from_date. Reversing the two returns a WRONG WINDOW
# with HTTP 200 and no error of any kind. Grade A, verified live.
CANDLE_PATH_TEMPLATE = "/v3/historical-candle/{instrument_key}/{unit}/{interval}/{to_date}/{from_date}"
CANDLE_FIELDS_BY_INDEX = ("timestamp", "open", "high", "low", "close", "volume", "open_interest")
CandleWire = tuple[str, Decimal, Decimal, Decimal, Decimal, int, int]
```

`CandleWire` as a **typed positional tuple** parsed through
`TypeAdapter[CandleWire]` is v1's idea and is kept: it pins arity at seven and
types each position, so a six- or eight-element row fails at the boundary rather
than shifting every field by one.

`instrument_key` is percent-encoded per path segment with
`quote(instrument_key, safe="")` → `NSE_EQ%7CINE009A01021` (F3). Never
`quote(whole_url)`.

Only `days`/`1` is exposed. Weekly, monthly, hourly and intraday paths are not
built, partly because F-note 6 of the verification pass shows omitting
`from_date` behaves *differently per unit* — `days`/`minutes` clip to the cap,
`weeks`/`months` silently return the entire 25-year history. Both dates are
always sent, so that trap cannot fire.

**Ordering (F2).** The wire is most-recent-first. Canonicalisation **sorts
ascending by timestamp** rather than reversing blindly — sorting is
order-independent, so it stays correct if the vendor ever changes — and
*separately* asserts the observed wire order was non-ascending, recording
`SCHEMA_DRIFT` if a multi-row response arrives ascending. Blind reversal would
double-reverse on that day and hash a scrambled series. **Hashing happens after
canonicalisation.**

**Window planning (F8).** `plan_daily_candle_windows(instrument_key, start, end)`
builds windows backward from `end`, each spanning at most ten years inclusive,
adjacent windows neither overlapping nor leaving a gap. 2000 → today is **three
requests per instrument**. A caller-supplied window longer than ten years is
refused **locally**, before any network call, as `REQUEST_REJECTED` — never
silently truncated.

The boundary is settled, not guessed: a `days/1` request spanning **exactly ten
years returned HTTP 200 and a full untruncated 2,478-row series**, while ~16.7
years returned 400 `UDAPI1148 "Invalid date range"` (both grade A, probes
retained). So the rule is `from_date = to_date` minus exactly ten calendar years
(Feb 29 clamped to Feb 28), and the precise cutoff somewhere between 10 and 16.7
years never needs to be known because we never ask for it. **`to_date` is
inclusive** — also grade A, verified live.

Two more error codes worth distinguishing rather than lumping into
`SCHEMA_DRIFT`: `UDAPI100011` "Invalid Instrument key" → HTTP 400,
`REQUEST_REJECTED` (verified live), and `UDAPI1015` for a `to_date`/`from_date`
ordering violation (documented, not observed — and if we ever see it, the
template is wrong).

An empty `data.candles` array is **NOT OBSERVED** — every probed range contained
trading days — so `OK_EMPTY` on this surface is a plausible extrapolation from
the other surfaces, not a verified behaviour. Marked as such at the enum member.

**Returned timestamps are validated against the requested window.** This is the
structural defence against F1, and it is the one that matters: the URL-string
test catches a reversed template, but only checking that every returned candle
falls inside `[from_date, to_date]` catches a wrong window however it arose. v1's
invariants were checked against the dates the planner *computed*, never the
timestamps the server *returned*, which is why its fifteen candle tests could
not catch B1.

Fail-closed row validation: exactly seven fields; aware timestamp carrying the
`+05:30` offset (F10); non-negative integer volume and open interest; unique
timestamps; every timestamp inside the requested window. **OHLC relationships are
not enforced** — nothing in the 129 responses establishes that adjusted
two-decimal prices always satisfy `high >= max(open, close)`, and failing closed
on an unverified rounding artifact rejects a legitimate candle. They are recorded
as `CandleAnomaly` entries in the review section (review S13).

**A version records only what it observed (review S3).**

```python
class CoverageSpan(BaseModel):     # frozen
    from_date: date
    to_date: date
    capture_sha256: str

class DailyCandleSeriesVersion(BaseModel):   # frozen
    instrument_key: str
    schema_version: int
    coverage: tuple[CoverageSpan, ...]       # ordered, non-overlapping
    candles: tuple[UpstoxDailyCandle, ...]   # ascending
    version_sha256: str
```

`version_sha256` covers instrument key, schema version, ordered coverage spans,
ordered candles and ordered capture hashes — **never** capture time.

This is the fix for the defect v1 could not see: v1's version 2 was "stored
2000–2026 prefix + 5 new days", so its hash *asserted* 2015 values that run never
re-fetched. Here a version physically cannot contain a date it did not observe,
and the full series is a **read-time composition**,
`compose_series(versions) -> tuple[UpstoxDailyCandle, ...]`, latest observation
winning per date. Nothing asserts unobserved history because nothing stores it.

**Version relations**, computed over the **overlap** between a new version's
coverage and prior coverage:

| Relation | Meaning |
|---|---|
| `FIRST` | no prior observation of any overlapping range |
| `IDENTICAL` | the overlap matches a prior version exactly |
| `EXTENSION` | no overlap; contiguous with prior coverage |
| `REVISED_CONSISTENT_WITH_REPORTED_ACTION` | the overlap differs **and** passes the ratio check below |
| `UNEXPLAINED_REVISION` | the overlap differs and does not |

**The ratio check (review S4).** Co-occurrence is not evidence. A vendor split or
bonus whose ex-date merely falls somewhere in the revised range is not enough —
under v1's rule a feed glitch moving one 2015 close by 3% earns the same
reassuring label as a real 1:10 split, provided any split is on record.
`REVISED_CONSISTENT_WITH_REPORTED_ACTION` requires **all** of:

1. an Upstox split/bonus record whose ex-date lies inside the revised range;
2. a parseable adjustment factor from its `ratio` (if unparseable → fail closed
   to `UNEXPLAINED_REVISION`);
3. for every re-observed date **before** the ex-date, `new_close / old_close`
   equals that factor within tolerance;
4. for every re-observed date **on or after** the ex-date, closes unchanged.

Tolerance is a chosen threshold, not a measured one — see §12 D4.

Even when it passes, the label means *"this vendor's own revision is arithmetically
consistent with this vendor's own declared action."* It is **vendor-relative
evidence, not authoritative causation**, and a comment at the enum member says so.

**What a consumer does on `UNEXPLAINED_REVISION`** — a prohibition is not a
handler (review S4). Three things, all defined:

1. the new version is stored and **wins at read time** for its range (it is the
   most recent observation; the prior version is retained, never overwritten);
2. it is listed in the run's `review.json` artifact with both digests;
3. `fundamentals upstox` and `upstox-sync` exit **3** (`EXIT_UNEXPLAINED_REVISION`),
   mirroring the repo's `EXIT_BASIS_UNAVAILABLE = 3` convention — acquisition
   succeeded, a human owes it a look.

Nothing downstream promotes these prices to facts in any case (§2).

### 6.7 Holidays and the trading calendar (Slice 4)

`GET /v2/market/holidays[/{date}]` — `date` is a **path segment**, not a query
parameter, `YYYY-MM-DD`. Envelope `{"status": "success", "data": [...]}`.

**The two exchange arrays have different element types**, which is the shape most
likely to be modelled symmetrically and wrongly:

```
data[] = {
  date:             "2026-01-26",                    # YYYY-MM-DD
  description:      "Republic Day",
  holiday_type:     "TRADING_HOLIDAY",               # exactly 3 values, verified
  closed_exchanges: ["NSE", "BSE", "NFO", ...],      # array of bare STRINGS
  open_exchanges:   [{"exchange": "NSE",             # array of OBJECTS
                      "start_time": 1704080700000,   # epoch MILLISECONDS
                      "end_time":   1704103200000}]  # timezone undocumented
}
```

`HolidayType` is exactly `TRADING_HOLIDAY`, `SETTLEMENT_HOLIDAY`,
`SPECIAL_TIMING` — verified as the complete set across 22 current-year holidays.
Either array may be `[]`: `closed_exchanges` is empty on a `SPECIAL_TIMING` day
where nothing is fully closed, and `open_exchanges` is empty on a full closure.
The endpoint has **no documented error-code table**.

**Openness is read per exchange from `open_exchanges`/`closed_exchanges`, never
from `holiday_type` (F7).** A date is open for exchange E iff E appears as the
`exchange` of an `open_exchanges` element. `HolidayType` is retained as
*description* and is never consulted for openness — a comment at the field says
so, because the tempting misreading is the whole reason F7 exists. `start_time`
and `end_time` are retained but not interpreted: their timezone is undocumented,
and this plan needs only the boolean.

`TradingCalendar.last_completed_trading_day(as_of_date, exchange)` returns the
most recent date that is open for `exchange` and **strictly before**
`as_of_date`. This is conservatively one session stale after a close, and that is
the deliberate price of not re-admitting `/v2/market/status` or
`/v2/market/timings` into scope. `as_of_date` is always explicit — never
`date.today()` inside a library — which is what makes a plan reproducible.

**The current-year-only problem (review S7).** The no-date call returns **the
current year only**, so an early-January `as_of_date` cannot see the prior
December from a fresh capture: v1's determinism claim passed on fixtures and was
false in production. Resolution:

- the calendar is built from **retained year captures** on disk plus the current
  one, and the capture hashes are explicit inputs to the plan digest;
- if a date the lookback needs is covered by no retained capture, the calendar
  probes `/v2/market/holidays/{date}` for that single date — bounded, at most one
  request per lookback day;
- if probing is disabled and coverage is missing, it raises
  `InsufficientCalendarCoverage` rather than guessing.

Weekends are closed unless a capture explicitly lists the exchange as open for
that date (a special session). Whether a Muhurat session appears in this feed is
**not verified** — recorded as an assumption in §12 D6, and the failure mode is a
skipped session, never a phantom one.

Empty holiday `data` is `OK_EMPTY` — "no holiday record for that date" — not an
acquisition failure (F12).

### 6.8 FII/DII (Slice 5)

```
GET /v2/market/fii?data_type=NSE_EQ|CASH&interval=1D[&from=YYYY-MM-DD]
GET /v2/market/dii?data_type=NSE_EQ|CASH&interval=1D[&from=YYYY-MM-DD]
{"status": "success", "data": {"<data_type>": [ {record}, ... ]}}
```

Cash-only (`NSE_EQ|CASH`) for both actors initially — verified working on `/fii`
too, not just `/dii`, and it is the **only** value `/dii` accepts. Derivative
`data_type`s exist and need an explicit scope expansion. The pipe sits in a
**query value** here, so it is encoded by `urlencode`, not by the path-segment
`quote` used for candles.

`time_stamp` is an integer of **Unix milliseconds** (timezone undocumented);
`buy_amount`, `sell_amount`, `oi_amount` are `Decimal`; the contract counts are
integers. The dynamic `data` map is parsed into a **sorted tuple**, not an output
dictionary, and the returned data-type keys must equal the requested ones
exactly.

**Sizing, not hedging (review S9).** The per-request caps are 30 trading days for
`1D` and 12 months for `1M`; availability begins 2026-04-01. Full history is
therefore roughly **four requests** — a bounded job, not an open research
question, which is what v1 made of it.

Honesty about grade, which the review did not supply: the inventory rates the
FII/DII rows **C** overall. The caps are **documented text**, corroborated only
by `1D` calls that returned exactly 30 rows; the 2026-04-01 start is documented
text the inventory explicitly flags as *"taken at face value, unverified"*. The
sizing above is therefore a plan, not a measurement — but it is a plan bounded by
a handful of requests, so being wrong costs one extra round trip (§12 D5).

The genuinely unverified part is narrow: whether `from` is inclusive. Two
responses: (a) request successive windows that **overlap by one day** and
de-duplicate by timestamp, which makes inclusivity irrelevant; (b) one live probe
to settle it and drop the overlap. Recommend (a) — it needs no probe and cannot
be wrong.

A pre-availability date range is **a coverage gap recorded in the artifact**, not
an outcome. v1 mapped it to `NOT_OFFERED`, contradicting its own rule that a
successful empty array is `OK_EMPTY` and never `NOT_OFFERED`; `NOT_OFFERED` is
dropped from the taxonomy entirely.

---

### 6.9 Lane B — the name-mapping table and the comparator (Slice 6)

Upstox's summary field names are wrong, but wrong **consistently**, and Upstox's
own documentation example proves it self-consistently:

```
income_statement.operating_profit   Mar-2025 = 106017
full_statement "Profit Before Tax"  Mar-2025 = 106017    ← identical
```

The three summary categories therefore map as follows. This is not a workaround;
it is the assertion the comparator tests. Our TITAN/HFCL/NETWEB 12/12 result is
its calibration proof, and a break in it is itself an alarm.

| Upstox `category` | Actually is | Screener row |
|---|---|---|
| `revenue` | Total Revenue (**sales + other income**) | `Sales` **+** `Other Income` — the one derived comparison |
| `operating_profit` | Profit Before Tax | `Profit before tax` |
| `net_profit` | Profit After Tax | `Net Profit` |

`full_statement` particulars (`Revenue`, `Other Income`, `Total Revenue`,
`Total Expenses`, `Profit Before Tax`, `Tax`, `Profit After Tax`, `EPS - Basic`,
`EPS - Diluted`) map to Screener rows directly and need no offset.

The mapping lives in one frozen module-level table. It is data, not branching
logic — a wrong mapping must be visible in one place.

**Comparison rule — decision C, settled 2026-09-03 as evidence-tiered outcomes.**

The history below is retained because the correction is load-bearing: the rule
this section originally carried was chosen on a false premise, and a reader who
sees only the tier table will not know which claims about this data are safe.

An earlier version of this section said "our probe found 12/12 **exact**
equality" and chose exact comparison on that basis. **That claim was false and
the evidence contradicting it was in our own probe file.** The independence test
says "to the crore, **or within ₹1 cr rounding**"
(`scratchpad/upstox/independence-test.md:56`), and Upstox returns decimals where
Screener displays integers:

| Company | Period | Screener PBT | Upstox `operating_profit` |
|---|---|---|---|
| HFCL | Jun 2026 | 332 | **331.52** |
| HFCL | Sep 2025 | 106 | **106.34** |
| NETWEB | Mar 2026 | 95 | **94.82** |

Exact equality is not merely strict here — for these companies it is
**unachievable**, and would report a 100% mismatch rate. TITAN's values happen
to be whole (`1522.0`, `2223.0`), which is what made the sample look exact.

The `revenue` line is worse. The plan claimed "expect ±1 and nowhere else." The
same probe file records TITAN Dec-2025 Screener 25,415 vs Upstox 25,567 — a
**152 crore** gap — and Mar-2026 51 crore
(`scratchpad/upstox/independence-test.md:63`). Those are not rounding; the
`revenue = Sales + Other Income` mapping is approximate, not exact.

**Replacement rule — evidence-tiered outcomes, not one global threshold.** The
repo already has the right machinery: `verify/crossfoot.observation_half_ulp`
for decimals-derived tolerance and `verify/comparison_key`. Use those rather
than invent a threshold.

| Tier | Surfaces | Comparison | On difference |
|---|---|---|---|
| 1 — equivalence demonstrated | income statement PBT, PAT (12/12, 3 companies, both bases) | half-ULP on declared precision | `MISMATCH` |
| 2 — related but not equivalent | income statement `revenue`, balance sheet | interval arithmetic over rounded addends | `ANOMALY` |
| 3 — equivalence unproven | cash flow, key ratios, share holdings | recorded, compared, never adjudicated | `NOT_COMPARABLE` |

Tier 3 is fetched and reported (owner decision B — all surfaces) but its
differences make no claim about our parser. Ratios are derived, point-in-time,
and formula-dependent; shareholding buckets may be defined differently. Cash
flow lineage was never tested at all — the independence test covered income
statement and, weakly, balance sheet.

`MISMATCH` is reserved for a difference outside a *justified* precision interval.
Everything else is `ANOMALY` or `NOT_COMPARABLE`. A measured first run sets
operational policy; it may not retroactively invent semantic equivalence.

D4 (0.5% relative) still governs *candle* revision detection, which is
unrelated. Note that `agreement.py:52` already defines
`DEFAULT_MINOR_DIFF_REL_TOLERANCE = 0.005` — the 0.5% figure was not invented,
it matches an existing repo constant.

**Disagreement report.** One JSON artifact per run: `isin`, `basis`, `period`,
`surface`, `screener_value`, `upstox_value`, `mapped_row`, and a
`ScreenerCheckOutcome` enum: `MATCH`, `MISMATCH` (tier 1 only, outside a
justified precision interval), `ROUNDING_COMPATIBLE`, `ANOMALY` (tier 2),
`NOT_COMPARABLE` (tier 3), `SCREENER_MISSING`, `UPSTOX_MISSING`,
`PERIOD_UNALIGNED`. Missing on either side is its own outcome — never silently a
match, never silently a mismatch. The record also carries the **raw vendor
label** alongside the mapped one, so a mapping drift is visible rather than
absorbed.

## 7. Entity assertions (Slice 1)

`entity/upstox_entity_source.py` reads a **retained catalog artifact from disk**
and emits `SourceRecord`s. It opens no socket — matching
`entity_map_sources.py`'s stated invariant that neither entity adapter does — so
an entity-map build stays offline and reproducible.

From the **listed** file only:

| Namespace | Source field | `verified` |
|---|---|---|
| `ISIN` | `isin` | `True` |
| `NSE_SYMBOL` | `trading_symbol` on `NSE_EQ` rows | `True` |
| `BSE_SCRIP` | `exchange_token` on `BSE_EQ` rows (a string) | `True` — see §12 D2 |

`SourceAssertion.verified` defaults to `True` and `EntityMap.lookup` gates on it,
so this is a load-bearing choice v1 never stated (review S6). The justification is
§2's asymmetry: within a current-state snapshot, a self-describing bulk file that
publishes ISIN and exchange code side by side *is* the confirmation. Joins are by
ISIN / NSE symbol / BSE scrip only — **never by name**.

**Nothing is ever `reported_absent`. Added 2026-09-04 during Slice 1; found by
the slice's own acceptance test, which failed on the first run.** The map treats
`reported_absent` as an assertion about the company: it conflicts with any source
that *does* state a value, and a conflicted entity is unreachable by
`EntityMap.lookup` (`entity_map.py:303`, `entity_identity.py:288`). This adapter
cannot honestly make that assertion, because the catalog it reads is a
**filtered** view retaining only `NSE_EQ`/`EQ` and `BSE_EQ`/`A`. A security in
another BSE group is missing from our rows because *we* dropped it, not because
the vendor was silent — so reporting it absent would state our own filter as the
vendor's claim, and would make a correctly pinned entity unreachable. Slice 1
would then have removed a lookup path while claiming to add one. Regression test:
`test_a_pin_the_catalog_holds_no_row_for_is_not_made_unreachable`.

Suspended rows emit nothing (§6.4).

**The slice's stated purpose gets an acceptance test.** Slice 1 exists to close
the identity gap — 9 of 10 pinned stocks are keyed `nse:<symbol>`, and adding an
ISIN **re-keys** the entity, a transition `build_entity_map` has five refusal
paths that can fire on. v1 claimed this value and tested none of it:

```
test_isin_less_pinned_symbol_gains_its_isin_and_rekeys_without_refusal
```

Wiring is behind an explicit `--upstox-catalog <path>` flag on
`fundamentals entity-map build`, **default off**. The map's inputs change only
when someone asks.

---

## 8. Persistence — the artifact-writer pattern, not a store (B3)

**v1's `store/source_snapshot_store.py` is deleted from this plan.** This is a
restructure, not a patch.

The evidence settles it. `src/fundamentals/store/` contains **only**
`fact_store.py`. The append-only content-hashed snapshot store and the typed
outcome taxonomy are two of `eqos-kx4.4`'s four deliverables, they exist nowhere
in code, and `eqos-kx4.4` is **OPEN and blocked by `eqos-kx4.3`, also OPEN**. The
shared store will not arrive first. v1's module table listed it as fact while its
own line 69 made it conditional — two mutually exclusive designs in one document,
and the conditional branch is the real one.

Building an Upstox-specific ledger instead would create a competing persistence
contract and an expensive migration, which is the objection that started this.

**So Slice 1 uses the pattern already proven in this repo**, from
`api/artifact_writer.py`: `preflight_out_paths(...)` then
`write_bytes_no_clobber(...)` / `write_json_no_clobber(...)`, exactly as
`screener_page_cli.py:168` does. Raw bodies go through `write_bytes_no_clobber`
so the bytes on disk stay identical to the ones the recorded sha256 covers.

**Layout**

```
data/raw/upstox/<surface>/<segment>/<key>/<capture_id>/
    upstox_<surface>.raw.json[.gz]      raw bytes, unmodified
    upstox_<surface>_meta.json          UpstoxCapture
    upstox_<surface>.parsed.json        typed artifact (deterministic)
    review.json                         anomalies, unknown keys, revisions
```

- `capture_id = <YYYYMMDDTHHMMSSZ>-<content_sha256[:12]>`. Unique per run by
  construction, so append-only holds as a filesystem property, no capture ever
  clobbers another, and `preflight_out_paths` never collides spuriously.
- `<key>` is the ISIN or the holiday year — **never** the raw `instrument_key`;
  the segment is its own path component so no `|` reaches a filename.
- **The instrument files address no single security**, so as built they use
  `<surface>/<route key>/<capture id>/` — the `<segment>/<key>` pair would have
  to be invented for them. Recorded 2026-09-04 with Slice 1.
- **Deduplication of identical bytes is deliberately not implemented.** It is the
  shared store's job. Repeated identical captures cost disk and nothing else.
- **The token never appears in a path, a filename, a log line, a `repr`, or an
  error message.** A `redact()` method mirrors `ScreenerSessionSource.redact`.

**Follow-up is already filed.** `eqos-f2m` — *"Upstox: migrate acquisition
persistence to the Phase 3 snapshot store"* — is OPEN and depends on
`eqos-kx4.4`. It already carries the three Upstox-specific requirements the
shared design must absorb: candle series need **versions**; a version must record
**which capture hashes cover which date ranges**; and the outcome taxonomy needs
**`CLIENT_BLOCKED` with `retryable=False`** for Cloudflare 1010, which is neither
`RATE_LIMITED` nor `AUTH_EXPIRED` and never clears on backoff. No new bead is
needed; this plan is its upstream.

---

## 9. Slices

Each is independently shippable and ends green on the §11 gate. The order puts
the price/instrument lane first, matching `eqos-rdb`'s decision rule.

### 9.1 Slice 1 — transport + instruments + entity records  *(the smallest useful slice)*

**Why this is first and genuinely smallest:** it needs **no token** (the assets
host is unauthenticated), so it ships before Gate 0's rights record gates live
authenticated capture; it touches no financial data; and it closes a real gap —
ISIN-less pinned symbols in the entity map.

The review proposed splitting this into 1a (transport + catalog + entity records)
and 1b (persistence). **B3 dissolves that split rather than ignoring it:** with
the bespoke store deleted, persistence is three calls to helpers that already
exist, so 1b has no content left.

**Create:** `ingest/http_session.py` (extracted), `ingest/upstox_source.py`,
`ingest/upstox_instruments.py`, `entity/upstox_entity_source.py`,
`api/upstox_cli.py`.
**Modify:** `ingest/screener_session.py`, `api/cli_parser.py`, `api/cli.py`,
`api/entity_map_cli.py`, three `__init__.py`.
**Tests:** `test_upstox_source.py`, `test_upstox_instruments.py`,
`test_upstox_entity_source.py`, `test_upstox_cli.py`,
`tests/fundamentals/upstox_fixtures.py`; `test_screener_session.py` re-run
unchanged.

**Acceptance tests**

```
test_raw_body_is_hashed_before_gzip_decode
test_corrupt_gzip_is_captured_with_a_hash_and_marked_schema_drift
test_compressed_and_decompressed_byte_caps_are_enforced_separately
test_default_urllib_user_agent_is_refused_at_construction
test_assets_host_request_carries_no_authorization_header
test_redirects_are_never_followed
test_instrument_omissions_stay_none_and_are_not_defaulted_to_false
test_bse_equity_row_without_security_type_is_accepted
test_unknown_wire_key_is_recorded_in_the_review_section_and_is_not_fatal
test_instrument_key_shape_is_segment_pipe_isin
test_suspended_rows_emit_no_entity_assertions
test_listed_rows_join_by_identifier_and_never_by_name
test_isin_less_pinned_symbol_gains_its_isin_and_rekeys_without_refusal   ← the slice's purpose
test_identical_bytes_produce_an_identical_canonical_parsed_digest
```

**Seams:** an injected `UrlOpener`, a `retrieved_at` supplier, a sleeper, a
monotonic clock. Tests use synthetic gzip bytes and open no socket.

**Risk:** the complete file is 3.2 MB compressed / 54.6 MB decompressed. Separate
compressed and decompressed caps, streamed decode — never a bare
`gzip.decompress` — and a terminal, retained failure on breach.

### 9.2 Slice 2 — daily candles

**Depends on:** Slice 1. Needs the token.

**Create:** `ingest/upstox_candles.py` + tests. **Modify:** `api/upstox_cli.py`.

**Acceptance tests**

```
test_candle_path_places_to_date_before_from_date          ← B1, asserts the built URL string
test_returned_timestamps_outside_the_requested_window_fail_closed   ← B1, the structural defence
test_instrument_key_pipe_is_percent_encoded_in_the_path   ← B5
test_descending_wire_rows_are_sorted_before_hashing       ← B2
test_ascending_multi_row_wire_is_recorded_as_schema_drift ← B2, the double-reverse guard
test_six_or_eight_field_candle_row_is_rejected
test_candle_prices_are_decimal_and_never_float
test_candle_timestamp_requires_the_india_offset
test_duplicate_timestamp_with_different_values_fails_closed
test_over_ten_year_window_is_refused_without_a_network_call
test_backfill_to_2000_windows_are_contiguous_and_non_overlapping
test_error_envelope_has_no_data_key_and_an_errors_array
test_disagreeing_camel_and_snake_error_fields_are_schema_drift
test_udapi1148_maps_to_request_rejected
test_ohlc_relationship_breach_is_recorded_as_an_anomaly_not_rejected
test_a_version_records_only_the_ranges_it_observed        ← S3
test_incremental_tail_is_not_classified_identical_over_an_unobserved_range  ← S3
test_refetch_appends_a_version_without_overwriting_prior_bytes
test_identical_bytes_produce_the_same_version_sha256
```

Until Slice 3 lands there is no corporate-action evidence, so every differing
overlap classifies as `UNEXPLAINED_REVISION`. That is the correct fail-closed
default, which is what makes the dependency breakable.

### 9.3 Slice 3 — corporate actions and shareholding

**Precondition (review S5):** one live probe of an invalid ISIN against
`/v2/fundamentals/{isin}/corporate-actions` to capture the error envelope, which
is **NOT OBSERVED** — only `/v3/historical-candle`'s error shape was captured
live. Until then, any fundamentals response that is not exactly
`{"status": "success", "data": [...]}` is `SCHEMA_DRIFT`. `OK_EMPTY` requires
`status == "success"` **and** `data == []`. Without this an invalid ISIN could
read as `OK_EMPTY`, recording a real company as having no corporate actions.

**Create:** `ingest/upstox_company.py` + tests. **Modify:** `api/upstox_cli.py`,
`ingest/upstox_candles.py` (add the ratio-consistency classifier).

**Acceptance tests**

```
test_expiry_date_parses_dd_mon_yyyy_wire_format           ← B4, real captured value
test_expiry_date_parsing_is_locale_independent            ← B4, non-C LC_TIME
test_shareholding_period_parses_mon_yyyy                  ← B4/F5
test_unrecognised_fundamentals_envelope_is_schema_drift_not_ok_empty  ← S5
test_empty_corporate_action_data_is_ok_empty
test_rights_issue_is_the_accepted_wire_enum
test_non_dividend_zero_amount_is_a_required_decimal
test_ratio_is_nullable
test_observed_event_detail_names_are_not_a_closed_enum
test_shareholding_category_order_does_not_change_output
test_missing_or_duplicate_shareholding_category_is_schema_drift
test_zero_shareholding_values_are_retained
test_composed_shareholding_marks_a_restated_prior_quarter ← S8
test_split_ratio_inconsistent_with_the_price_change_stays_unexplained  ← S4
test_matching_ratio_labels_the_revision_without_claiming_causation     ← S4
test_company_records_are_never_written_to_the_fact_store
test_token_absent_from_repr_logs_errors_stdout_and_paths
```

**Risk:** a new legitimate corporate-action type stops parsing. Intentional
fail-closed behaviour; raw bytes are retained for a reviewed schema update.

### 9.4 Slice 4 — holidays, trading calendar, deterministic sync

**Create:** holiday half of `ingest/upstox_market.py`, `ingest/upstox_sync.py` +
tests. **Modify:** `api/upstox_cli.py` (add `upstox-sync`).

`upstox_sync.py` is a **pure planner**: `plan(as_of_date, state) -> UpstoxSyncPlan`,
no I/O, fully testable. Execution is a loop in the CLI. A plan:

1. refresh both instrument files;
2. capture the holiday evidence the lookback needs;
3. refresh corporate actions and shareholding for sorted target ISINs;
4. fetch candles from each series' last **observed** date through the last
   completed trading day.

Rules: a newly observed split or bonus schedules a full three-window re-fetch. A
monthly full audit is an **operational default, not a verified requirement**
(§12 D7). A failed or empty candle acquisition does **not** advance the
watermark. `upstox-sync` runs jobs sequentially on shared spacing, continues past
entity-local failures, and returns a non-zero partial exit code.

**Partial-window failure (review S14), previously undefined.** Because a version
records only what it observed (§6.6), a partial run is representable: it stores a
version containing exactly the windows that succeeded, reports outcome `PARTIAL`
with exit 2, and advances the watermark **only** if the tail window through the
completed trading day succeeded and is contiguous with stored coverage.

**Rate budget (review S12), previously absent.** The binding limit is **2,000
requests per 30 minutes** — ~1.1 req/s sustained; the documented 50 req/s is
burst headroom that the 30-minute bucket immediately reclaims. At that rate the
92-entity watchlist over three surfaces is ~276 requests, about five minutes, and
fits inside a single 30-minute bucket. The full NSE equity-series catalog Slice 1
builds is 2,639 instruments; a three-window backfill is ~7,900 requests, roughly
**two hours across four buckets**, repeated by any monthly audit. So: targets
default to the watchlist, widening is explicit, and the planner enforces
`plan.request_count <= config.max_requests_per_run` **before any I/O** and
refuses otherwise.

**Acceptance tests**

```
test_openness_is_read_from_open_exchanges_not_holiday_type    ← B-adjacent, S7
test_trading_holiday_with_nse_in_open_exchanges_is_an_open_session  ← the 2024-01-01 case
test_last_completed_day_is_strictly_before_as_of_date
test_special_weekend_session_is_open_only_when_explicitly_listed
test_january_as_of_date_without_prior_year_coverage_probes_or_refuses  ← S7
test_calendar_capture_hashes_are_inputs_to_the_plan_digest
test_sync_plan_is_identical_for_identical_state_and_as_of_date
test_first_sync_backfills_from_2000
test_incremental_sync_starts_after_the_last_observed_date
test_failed_or_empty_candle_fetch_does_not_advance_the_watermark
test_partial_window_run_stores_only_covered_spans_and_exits_two  ← S14
test_plan_exceeding_the_request_budget_is_refused_before_any_io  ← S12
test_new_split_or_bonus_schedules_a_full_refetch
test_sync_never_routes_to_status_timings_quotes_or_competitors
```

### 9.5 Slice 5 — FII/DII

**Create:** FII/DII half of `ingest/upstox_market.py` + tests.

**Acceptance tests**

```
test_fii_and_dii_cash_share_the_verified_record_shape
test_activity_amounts_are_decimal
test_returned_data_type_keys_must_equal_the_requested_keys
test_empty_requested_series_is_ok_empty
test_full_history_is_four_bounded_requests_under_the_documented_caps  ← S9
test_overlapping_windows_deduplicate_so_from_inclusivity_does_not_matter  ← S9
test_pre_availability_range_is_a_recorded_coverage_gap_not_an_outcome     ← S9
test_activity_output_is_sorted_by_actor_type_and_timestamp
test_cli_offers_no_derivative_data_types
```

---

### 9.6 Slice 6 — Screener parse-check (Lane B)

Depends on Slice 1 (transport) and on stored Screener artifacts. Independent of
Slices 2–5, so it can run in parallel with them.

**Modules**

```
ingest/upstox_statements.py     Pydantic models for the four Lane B responses
ingest/screener_crosscheck.py   frozen name map, comparator, ScreenerCheckOutcome
```

Both are new files. Neither imports `fact_store`.

**Command**

```
fundamentals upstox-crosscheck --isin-file <path> [--basis consolidated|standalone|both]
                               --screener-root <dir> --out-dir <dir>
```

Writes one disagreement report per run via `write_bytes_no_clobber`. Exit code
is **0 on a completed run regardless of how many mismatches it found** — Lane B
is log-only (decision A), so a mismatch is data, not a build failure. Non-zero
only on transport or parse failure.

**Steps**

1. Pydantic models for `income-statement`, `balance-sheet`, `cash-flow`,
   `key-ratios`, both `fs=true` and summary shapes. Note `time_period=quarterly`
   is **silently ignored** by balance-sheet and cash-flow (verified live) —
   the models must not offer a quarterly variant for those two.
2. Fetch per ISIN per basis over the Slice 1 transport, at the Slice 1 pace.
3. Frozen name map and comparator (§6.9).
4. Sweep the 83-ISIN entity map, both bases; write the report.
5. **Graduation procedure — not a bare rate.** A disagreement rate cannot
   separate a parser defect from vendor timing drift, a bad mapping, a formula
   difference, a precision artefact, or a comparator alignment bug, and a low
   rate does not demonstrate sensitivity to real parser failures. So:
   a. Hand-label a stratified sample of differences by opening the retained
      Screener HTML for that exact cell.
   b. Seed known parser mutations (or replay historical parser defects) and
      measure whether Lane B detects them. This is the sensitivity test; without
      it a quiet report is indistinguishable from a blind one.
   c. Choose warn/block **per field and per root-cause class**, not per endpoint.
   Owner and deadline are recorded on the bead. Log-only without a review owner
   becomes permanent unactioned telemetry.

**Red proof before implementation**, per `docs/graph-loops/v2-build-pipeline.md`:
a test asserting `operating_profit` maps to Screener's `Profit before tax` and
that a naive same-name mapping fails.

**Estimate:** about one day. Roughly 1h models, 1h fetch/persist, 2h comparator,
1h sweep and report, plus run time.

**Not in this slice:** any change to reconciliation, `needs_human_review`
triage, or fact promotion. Those wait on the measured rate from step 5.

## 10. Cross-cutting scope and security acceptance

`tests/fundamentals/test_upstox_scope_guards.py`:

```
test_every_upstox_route_is_get_only
test_route_registry_is_exactly_the_ten_approved_surfaces
test_no_url_builder_can_construct_a_profile_or_competitor_path
test_lane_b_report_schema_carries_no_fact_or_provenance_type
test_crosscheck_exit_code_is_zero_when_mismatches_are_found  ← log-only
test_no_lane_b_module_imports_fact_store_or_the_reconciler   ← secondary only
test_no_url_builder_can_construct_an_account_portfolio_order_or_money_path
test_no_upstox_module_imports_fact_store                  ← §2, by import scan
test_authorization_header_reaches_only_the_pinned_api_host
test_assets_host_never_receives_the_token
test_cloudflare_403_1010_is_terminal_and_never_retried    ← F11
test_rate_limit_retries_and_total_backoff_budget_are_bounded
test_transport_errors_never_contain_the_token
```

**The Lane B voting bar is not an import scan.** External critique (Codex
GPT-5.6 Sol, 2026-09-03) established that an import scan proves only that *these
two modules* do not import the store today. It does not stop a third module
importing both, a report consumer reconstructing an `Observation`, a transitive
or dynamic import, or a future orchestration change adding `upstox` to source
collection. The import scan stays as a secondary architecture check and is
demoted accordingly above.

The enforcing change is at the reconciliation boundary, and it fixes a live
defect that exists whether or not Lane B is ever built:

```
src/fundamentals/reconcile/agreement.py
  DERIVED_SOURCE_MARKERS = ("screener", "tijori")   # anything else → FIRST_PARTY
```

Source classification defaults **open**. Any unrecognised source id — `upstox`
included, verified locally — is granted first-party authority by string default.
Required:

```
test_unknown_source_id_fails_closed_rather_than_defaulting_to_first_party
test_reconciliation_entry_points_reject_a_diagnostic_only_evidence_role
test_upstox_source_ids_are_never_classified_first_party
```

A typed `EvidenceRole` with a `DIAGNOSTIC_ONLY` member, rejected at every
reconciliation entry point, is the actual bar. This is a **prerequisite for
Slice 6**, filed separately — it is a defect in existing code, not new work.

**Future-only decisions**, recorded so a later slice does not rediscover them:
if quotes are ever added, `prev_ohlc` must be **optional** (it is `null` on a
routine `interval=1d` response — the highest-severity trap in the whole
verification pass) and responses must join through the embedded
`instrument_token`, never the `SEGMENT:SYMBOL` map key; a future market-status
enum must include `CLOSING_END`; a future competitor URL builder would take
`NSE_EQ|<isin>`, so route construction stays endpoint-specific.

## 11. Verification

Per `.claude/project/verification.md`:

```bash
uv sync
uv run ruff check src tests/fundamentals
uv run ruff format --check src tests/fundamentals
uv run mypy --strict src
uv run pytest tests/fundamentals
git status --short
```

or `scripts/verify.sh gate <slice>`, which runs those four plus the red-proof,
skip-guard, diff-coverage and security-rail checks. Scope ruff and pytest to
owned paths — a bare invocation also scans out-of-scope trees with a known
pre-existing failure.

**The default suite opens no socket.** After Gate 0's rights record exists, one
opt-in live canary per surface may run, retaining only hashes, counts, outcomes
and authorised raw bodies.

---

## 12. Open decisions

Genuinely open. Each carries a recommendation, not an assertion.

**Settled 2026-09-03 by the owner, recorded here so they are not reopened:**

| # | Decision | Chosen | Note |
|---|---|---|---|
| A | What happens when Lane B finds a mismatch | **Log only.** Record it; nothing downstream changes | Chosen over warn/block because the base disagreement rate is unmeasured. Blocking on an unknown rate either halts the pipeline or gets switched off within a day. Promote to warn or block *after* Slice 6 step 5 reports the number. |
| B | How wide the check goes | **All of it** — income statement, balance sheet, cash flow, key ratios, shareholding | Broader than the recommendation (income statement first). Owner's call. The cost is mostly in the shared machinery, so the marginal surfaces are cheap; the risk is a noisier first report, which log-only absorbs. |
| C | Exact match or a tolerance | **Evidence-tiered outcomes** (§6.9), on the repo's existing `verify/crossfoot.observation_half_ulp` and `verify/comparison_key`. Owner-confirmed 2026-09-03. | Supersedes an earlier *exact* choice made on an orchestrator claim of "12/12 exact" that was false — the probe says "within ₹1 cr rounding", and Upstox returns decimals where Screener shows integers (HFCL 331.52 vs 332), so exact would report ~100% mismatch. The owner's original intent — no invented statistical tolerance — is preserved: tier 1 uses a *derived* half-ULP bound, tier 2 interval arithmetic over rounded addends, tier 3 makes no claim. No threshold is guessed anywhere. |

**Note on B, recorded against the plan's own earlier position.** This plan
originally recommended shareholding be *demoted*, because Screener already
supplies it with pledge data Upstox lacks. Under Lane B that reasoning inverts:
overlap with Screener is the prerequisite for checking Screener. Shareholding
stays, now with a stated purpose.

| # | Decision | Recommendation | Trade-off |
|---|---|---|---|
| D1 | Extract `http_session.py` vs. copy the three helpers | **Extract**, with `test_screener_session.py` as the characterization harness | ~40 lines and real DRY, against touching a working transport while `eqos-kx4.3.5` is open in the same file. Fallback: copy with a comment naming the origin, file a bead. |
| D2 | Is `BSE_EQ.exchange_token` the BSE scrip code, and is the assertion `verified`? | **Spot-check one known scrip** (e.g. Reliance = 500325) against the file before emitting, then **`True`** | Upstox documents `exchange_token` as **reusable by the exchange after expiry**, so it is never a long-term key. `EntityMap` is current-state, so a current snapshot's code is a current fact — but if the spot-check fails, emit no `BSE_SCRIP` at all rather than a wrong one. If reuse is later observed, drop to `False`; the map treats unverified values as no lookup path. |
| D3 | `source_id` granularity | **One `upstox`**, with the surface in `table_key` | Per-surface ids would fragment the map's per-source view for no gain. |
| D4 | Revision ratio tolerance (**candles only** — Lane B statement compare is exact, decision C) | **0.5% relative**, on two-decimal adjusted prices | A guess, stated as one. Too tight relabels real splits `UNEXPLAINED_REVISION` (safe, noisy); too loose blesses a glitch (unsafe). Bias tight. |
| D5 | FII/DII availability start (`2026-04-01`) and cap sizes are **documented text, grade C** | Ship the four-request backfill anyway; treat a short or empty first window as data, not as failure | Verifying costs the same requests the backfill already makes, so a probe buys nothing. The failure mode is one wasted round trip. *(This slot previously held the decade-boundary question; the retained probes settled it — exactly ten years returns HTTP 200 with 2,478 rows. See §6.6.)* |
| D6 | Do special weekend sessions (Muhurat) appear in the holidays feed? | Treat as **unverified**; weekends closed unless explicitly listed | Failure mode is a skipped session, never a phantom one. Confirm on the next October capture. |
| D7 | Full candle audit cadence | **Monthly**, plus action-triggered re-fetch | A reasoned operational default, not a measured optimum. At catalog scale it is a two-hour job (§9.4) — revisit if targets widen. |
| D8 | Wire the Upstox catalog into `entity-map build` | Behind `--upstox-catalog`, **default off** | The map's inputs change only when asked. |
| D9 | Upstox rights for automated access, caching, retention | **Drafted 2026-09-04** — `docs/research/upstox-rights-record.md`, state `PROPOSED`, authorizing nothing. Awaiting a named human decision on the four dimensions that are `UNKNOWN` or informal. | Delays live operation; avoids building an unauthorised retention system. Two findings landed against this plan's assumptions: the personal-use carve-out **does not exist** in the terms, and the unauthenticated instrument files are the **least** rights-covered surface rather than the most. |
| D10 | Authoritative action promotion | A separate future S17 task after G02/G03 | Downstream adjusted-price explanations stay vendor-relative until then. |

## 13. Ranked risks

1. **Silent wrong-window corruption (F1).** Wrong history, HTTP 200, content-hashed
   and stored as evidence. → Pinned path constant with the fact in a comment at
   the site; a URL-string test; **and** validation of returned timestamps against
   the requested window, which catches it however it arose.
2. **Silent series scrambling (F2).** → Sort ascending rather than reverse; assert
   the wire was descending; hash only after canonicalisation.
3. **Total slice outage from a wire date format (F4, F5).** → Explicit month map,
   never locale-dependent `strptime`; lexeme retained beside the parsed value;
   tests use real captured values.
4. **Over-authoritative use.** Vendor observations read as corroborated facts. →
   `API_DOCUMENT` is barred from `FactStore`; an import-scan test; no S17
   promotion in this plan.
5. **Asserting history nobody re-observed (S3).** → A version physically stores
   only its observed spans; the full series is composed at read time.
6. **False causal comfort (S4).** A glitch labelled as a corporate action. → The
   ratio-consistency check, fail-closed to `UNEXPLAINED_REVISION`, plus a defined
   consumer handler and exit code 3.
7. **Competing persistence contracts (B3).** → No bespoke store; the existing
   no-clobber artifact pattern; `eqos-f2m` owns the migration.
8. **Provider drift.** → Strict typed models at the boundary, raw retention, a
   typed `SCHEMA_DRIFT` outcome, non-fatal unknown-key census.
9. **Secret or host leakage.** → Pinned origins, refused redirects,
   construction-time `SecretStr`, `redact()`, host-specific auth tests, token
   never in a URL, log, `repr` or path.
10. **Hostile or oversized payloads.** → Separate compressed/decompressed caps,
    streamed decode, sequential processing.
11. **Rate-budget blowout at catalog scale (S12).** → Watchlist-by-default
    targets, an explicit widening flag, a pre-I/O request-budget refusal.
12. **Refactor collision on `screener_session.py` (D1).** → Existing tests as the
    characterization harness; a stated copy fallback.
13. **False historical completeness.** → Explicit coverage gaps for FII/DII; no
    watermark advance on an empty or failed fetch.

---

## 14. Disposition of the review

Every item, including the ones declined. Nothing dropped silently.

### Blocking

| # | Item | Disposition |
|---|---|---|
| B1 | `to_date` before `from_date` | **Fixed.** F1; pinned constant §6.6; two tests §9.2 — the URL string *and* returned-timestamp validation. |
| B2 | Wire is most-recent-first | **Fixed.** F2; sort-not-reverse plus a drift assertion §6.6; two tests §9.2. |
| B3 | Two mutually exclusive designs for Slice 1 | **Restructured.** The bespoke store is deleted; §8 uses `write_bytes_no_clobber` + `preflight_out_paths`. The migration bead **already exists**: `eqos-f2m`, OPEN, depends on `eqos-kx4.4`, and already carries the three Upstox requirements for the shared design. |
| B4 | `expiry_date` is `"14 Aug 2025"` | **Fixed.** F4/F5; explicit month map §6.5; locale-independence test §9.3. `period` is now modelled too. |
| B5 | `instrument_key` undefined | **Fixed.** F3; format, percent-encoding, and the NSE-preferred/BSE-fallback dual-listing rule §6.6; the series and its watermark are keyed by `instrument_key`, not ISIN. |

### Should-fix

| # | Item | Disposition |
|---|---|---|
| S1 | Seventh polite fetcher | **Fixed, narrowly.** §5.1 extracts three semantics-free helpers; everything that genuinely differs stays per-adapter. Recorded as open decision D1 with a stated fallback. |
| S2 | `retrieved_at` breaks byte-identity; wrong clock | **Fixed.** §6.3: a wall-clock supplier for the field, monotonic for pacing only, `canonical_parsed_digest` excluding time as the determinism assertion. |
| S3 | Tail fetch asserts unobserved history | **Fixed structurally.** §6.6: versions store only observed spans; read-time composition. Two tests. |
| S4 | Co-occurrence labelled as evidence | **Fixed.** §6.6 ratio-consistency check with four conditions, fail-closed; and the consumer handler v1 never defined (store, review artifact, exit 3). |
| S5 | Fundamentals error envelopes NOT OBSERVED | **Fixed.** §9.3 precondition probe; until then non-`success` envelopes are `SCHEMA_DRIFT`, and `OK_EMPTY` requires both `status == "success"` and `data == []`. |
| S6 | Slice 1's purpose untested; `verified` unstated | **Fixed.** §7: the re-keying acceptance test, and `verified` stated per namespace with its justification. |
| S7 | Openness from `holiday_type`; current-year-only | **Fixed.** F7 and §6.7: per-exchange rule with a comment at the field, retained year captures, bounded single-date probes, `InsufficientCalendarCoverage`, capture hashes in the plan digest. |
| S8 | Shareholding rolling window | **Fixed.** F5 and §6.5: `period` modelled, `compose_shareholding` with a `restated` flag. Deliberately not the candle version machinery — different key space, same idea. |
| S9 | FII/DII over-hedged; `NOT_OFFERED` misused | **Fixed.** §6.8: caps stated, backfill sized at ~4 requests, overlapping windows make `from`-inclusivity moot, pre-availability is a coverage gap. `NOT_OFFERED` dropped from the taxonomy. |
| S10 | Materially over-built | **Applied.** 18 modules → 8; 6 commands → 2. Cut: the store and its four tables, `parsed_blobs`, `source_interpretations`, the SQLite UPDATE/DELETE triggers, the `upstox_source_models.py` split, `UpstoxInstrumentDiscriminator` routing, `upstox_cli_dispatch.py` as its own module, `SuspendedInstrumentMatch`. The proposed 1a/1b split is **dissolved rather than ignored** — B3 leaves 1b with no content. |
| S11 | `UDAPI1149` presented as settled | **Fixed.** §4 and §6.1 label `PLAN_LOCKED` an unverified assumption with no fixture available (grade D; this account has Plus). |
| S12 | No rate budget | **Fixed.** §9.4 sizes both cases and adds a pre-I/O budget refusal plus a target cap. |
| S13 | OHLC validation invented | **Fixed.** §6.6: recorded as an anomaly, never rejected, with the reason stated. |
| S14 | Partial-window failure undefined | **Fixed.** §9.4: partial versions are representable, exit 2, watermark advances only on a contiguous tail. |
| — | NOISE: `mtf_bracket` absence-as-false | **Accepted.** §6.4: numeric, `Decimal \| None`, no absence-as-false property. |
| — | NOISE: `test_candle_index_map_is_pinned_once` cannot fail | **Accepted.** Dropped; replaced by tests that can fail (arity rejection, positional typing). |

### Preserved from v1 without change

The scope boundary; the `API_DOCUMENT`/`FactStore` reasoning; the self-describing-file vs.
request-bound-response asymmetry; `CandleWire` as a typed positional tuple;
`CLIENT_BLOCKED` / `retryable=False` for Cloudflare 1010; the refusal to call a
hash change a restatement; and the conservative "most recent open session
strictly before an explicit `as_of_date`" rule that keeps market status and
timings out of scope.

## 15. Beads

- **`eqos-rdb`** — owns this work. Slices 1–5 become its children.
- **`eqos-f2m`** — already OPEN, already scoped: migrate this persistence onto
  the `eqos-kx4.4` snapshot store when it ships. No new bead needed.
- **File one bead** only if D1 resolves to *copy* rather than extract: "de-duplicate
  the polite-fetcher helpers across `screener_session.py` and `upstox_source.py`".

**Confidence:** high on scope, contracts and the trap handling — those rest on
grade-A evidence, most of it from live requests and two full-file censuses.
Medium on the FII/DII surface as a whole (grade C: caps and availability are
documented text, and `from` inclusivity is mitigated by overlapping windows
rather than resolved), on special-session handling (D6) and on the audit cadence
(D7). All three are marked as assumptions rather than facts wherever they appear.
Low-confidence items are confined to Slice 5 and to one scheduling default, so
none of them can silently corrupt stored data.
