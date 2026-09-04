# Learnings

Durable, verified, likely-to-recur patterns for **this** repo. Capture only
after a verified fix or a repeated pattern — not speculation. Keep each entry
short: what was observed, why it matters, how to apply it.

Format per entry:

```
## <short title>  (<YYYY-MM-DD>)
- Observed: <what happened / the pattern>
- Why it matters: <consequence>
- Apply: <concrete guidance>
```

## Stale `sync.remote` in `.beads/config.yaml` breaks `bd init`  (2026-08-12)

- Observed: at adoption the working-tree `.beads/config.yaml` carried another
  repo's `sync.remote` (`agent-os.git`, nonexistent); `bd init` tried to clone
  it and failed with "Repository not found". Corrected the remote, init
  succeeded. (Why the earlier init commit f881e51 was reverted is not
  recorded — its committed config already had the correct remote.)
- Why it matters: `bd init` fails closed on a wrong/unreachable `sync.remote`.
- Apply: when adopting into a new repo, set `sync.remote` to the repo's own
  git remote **before** running `bd init`.

## A `time.sleep` default argument defeats every `monkeypatch` of it  (2026-09-03)

- Observed: extracting `RequestPacer` (eqos-zfu) gave `wait_for_slot` the
  signature `sleep: Callable[[float], None] = time.sleep`. Python evaluates a
  default at function-definition time, so the real `time.sleep` was captured at
  import. `tests/fundamentals/test_screener_session.py` patches
  `fundamentals.ingest.screener_session.time.sleep` — that patch mutates the
  shared `time` module and had worked for years, but it could not reach an
  already-bound default. The suite really slept 1.5 s and the spacing assertion
  failed (2.28 s run, down to 0.74 s after the fix).
- Why it matters: the failure mode is a *slow, flaky* test, not a clear error.
  Had the assertion been looser it would have passed while silently sleeping —
  the same trap hides in any injected clock, sleeper, or `now()`.
- Apply: never bind a patchable callable as a default argument. Default to
  `None` and resolve inside the body (`wait = time.sleep if sleep is None else
  sleep`). Applies equally to `datetime.now`, `uuid4`, and `random`.

## `mypy --strict` catches `config or Default()` aliasing bugs  (2026-09-03)

- Observed: in the same extraction, `__init__` read
  `RequestPacer(config.min_request_spacing_seconds)` one line after
  `self._config = config or ScreenerSessionConfig()`. Every test passes a
  config, so 1,284 tests stayed green; the default-constructed path would have
  raised `AttributeError`. mypy flagged it as `union-attr`.
- Why it matters: the `x or Default()` idiom leaves the narrower parameter in
  scope, and reading the parameter instead of the attribute is invisible to a
  test suite that never exercises the default.
- Apply: after `self._x = x or Default()`, read `self._x` for the rest of the
  constructor. Run `mypy --strict` before trusting a green suite on any
  constructor change.

## A filtered source may not report a namespace absent  (2026-09-04)

- Observed: the Upstox entity adapter (Slice 1, eqos-rdb) emitted
  `reported_absent=(BSE_SCRIP,)` whenever its rows carried no BSE listing.
  `entity_map.py:303` derives `Entity.conflicted` from any `CONFLICTED`
  namespace, and `_coverage` treats "source reported absent" as an assertion
  that conflicts with any stated value — so a correctly pinned stock became
  conflicted and `EntityMap.lookup` returned `None` for it. The slice's own
  headline acceptance test caught it: the entity re-keyed to its ISIN exactly
  as designed and was then unreachable.
- Why it matters: the adapter reads a *filtered* catalog (only `NSE_EQ`/`EQ`
  and `BSE_EQ`/`A` rows are retained). Absence in our rows is our filter, not
  the vendor's silence. Reporting it as vendor silence states our own
  processing as a source claim, and the map is built to trust exactly that
  distinction — so the lie propagates into an unreachable entity rather than
  into a visible error. Slice 1 would have removed a lookup path while
  claiming to add one.
- Apply: only a source that carried the whole namespace and published nothing
  may set `reported_absent`. If any of your own filtering, sampling or
  projection could have emptied it, emit nothing — that is
  `MissingReason.NOT_SUPPLIED`, which is the truth. Check this whenever a new
  `SourceRecord` producer is written.

## A trading series is not a security type  (2026-09-04)

- Observed: the Upstox instrument filter retained `NSE_EQ`/`EQ` and
  `BSE_EQ`/`A`, the two combinations the schema census had counted. On the
  first live entity-map build, 2 of 10 pinned watchlist stocks (HFCL,
  MTARTECH) were missing. Both trade in NSE series `BE` and BSE group `T` —
  trade-to-trade. A full scan then showed the filter was wrong in both
  directions: it dropped real companies, and `NSE_EQ`/`EQ` itself carries 176
  ETFs (`INF` issuers) that it was admitting as listed companies.
- Why it matters: the failure was **silent**. No anomaly, no schema drift, no
  count that looked wrong — the rows simply were not there, and the entity map
  reported 0 conflicts while being blind to two of the ten stocks the whole
  system exists to track. A filter that drops rows can only be checked against
  something you already know should be present.
- Root cause: a census enumerates the categories that *happened to be counted*.
  Turning that enumeration into a filter encodes the sample as the population.
  `instrument_type` is a trading-restriction series (137 distinct values inside
  the two cash segments); it says how a security may be traded, not what it is.
- Apply: filter on what the data *declares itself to be*, not on a category
  list. Here the ISIN carries it — `INE` (company) plus issue-type `01` (equity
  shares), both required. When you must filter, write a test that asserts a
  known member of the population survives it, and prefer a known-awkward member
  (a suspended stock, a trade-to-trade stock) over a typical one.

## An empty success payload can mean "no such entity"  (2026-09-04)

- Observed: the Upstox Lane B verification asked `/v2/fundamentals/{isin}/
  corporate-actions` for a fabricated ISIN. It answered HTTP 200 with
  `{"status":"success","data":[]}` — byte-identical to a real company that has
  no corporate actions. The integration plan had proposed exactly the guard this
  defeats: *"`OK_EMPTY` requires `status == "success"` and `data == []`"*.
- Why it matters: a typo'd or stale identifier reads as a true negative. The
  sweep completes, the report is clean, and the company is simply missing —
  which is the same silent-drop failure shape as the instrument filter.
- Apply: when a lookup's not-found case is indistinguishable from its empty
  case, no response check can recover it. Move the guard **before** the request:
  validate the identifier structurally (an ISIN check digit is deterministic and
  free) and only ask about identifiers already present in a catalog or artifact
  you hold. Check this for every new per-entity endpoint.

## A period label is only a key within one periodicity  (2026-09-04)

- Observed: `income-statement?time_period=quarterly` returns a payload whose
  `time_period` says `quarterly`, whose summary block is quarterly, and whose
  `full_statement` block is still annual. Both label their columns `Mar 2026`.
  The summary↔`full_statement` identity check joins on that label, so on the
  live TITAN response it compared one quarter's revenue (27,104 cr) against the
  financial year's (88,136 cr) and reported three confident disagreements — one
  per identity, all false.
- Why it matters: the two blocks arrive in one HTTP response, so nothing about
  the transport hints that they are on different clocks. The check looked like
  a working drift detector; it was manufacturing findings.
- Apply: before joining two series on a period label, assert both carry the same
  periodicity, and skip rather than compare when they do not. Never derive one
  block's periodicity from the response envelope — measure each block's own.

## Name similarity between two vendors is not evidence of a mapping  (2026-09-04)

- Observed: Lane B mapped Upstox's `total_liability` onto Screener's
  `Total Liabilities` row. Screener's row is the *balancing total* — it equals
  Screener's own `Total Assets` on every period of every company checked — while
  Upstox's field is liabilities excluding equity. The comparator reported a
  five-figure ANOMALY on all four TITAN periods (15,703 / 11,622 / 9,390 /
  11,901 crore) while the underlying numbers agreed to the crore. The correct
  mapping is `Borrowings + Other Liabilities`, which is exact on Mar-2026.
- Why it matters: this is precisely the failure `screener_crosscheck`'s own
  docstring warns about, committed by the module that warns about it. A false
  anomaly on every company and period reads as a catastrophic parser defect that
  does not exist, and it is the fastest way to get a log-only check switched off.
- Apply: every entry in a cross-vendor name map must be demonstrated on live
  data from both sides before it ships — matching labels are a hypothesis, not
  evidence. Prefer a reconstruction from rows whose sum you have checked over a
  single row whose name matches. See
  [`docs/research/upstox-lane-b-first-measurement.md`](../../docs/research/upstox-lane-b-first-measurement.md).

## Validate only the part of an artifact you read  (2026-09-04)

- Observed: `upstox-crosscheck` loaded Screener sections through the full
  `SectionTable` model. A retained capture written before `ScheduleStrategy` and
  `SubRowKind` gained required fields then failed with 16 validation errors —
  none in a field any comparison touches — and the whole run refused before
  comparing anything.
- Why it matters: it couples a consumer to parts of a producer's schema it has
  no interest in, and turns unrelated schema evolution into a hard failure of a
  log-only lane. Retained artifacts outlive the models that wrote them.
- Apply: when reading someone else's artifact, declare a narrow model of exactly
  the fields you use, `extra="ignore"`, and keep those fields strict. Reuse the
  producer's full model only when you actually depend on all of it.
