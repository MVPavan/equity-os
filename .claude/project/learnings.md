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
