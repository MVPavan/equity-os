# Judge's Consolidation — Screener.in + Tijori Acquisition Tooling

**Judge:** Fable 5 (high) · **Date:** 2026-08-24
**Members:** Opus 5 medium (`opus-5-stage2.md`) · GPT-5.6 Sol high (`gpt-5.6-sol-stage2.md`)
· OpenCode x-alpha (`opencode-x-alpha-stage2.md`) · Stage 1 matrices in the same directory.

## Verdict: UNANIMOUS — Option 2, build our own

All three members independently chose **build our own HTTP-first Python acquisition
layer**, keeping the existing uncommitted Tijori json_script adapter as the foundation,
reusing *knowledge* (not runtime code) from all three candidate repos, and rejecting
Crawl4AI as the engine. No judge override is needed on the headline; my rulings below
resolve the secondary disagreements.

## Where the members converge (adopted as decided)

1. **The existing Tijori island adapter is the foundation** — the only code in play that
   already satisfies every house invariant (fail-closed identity via `company_details`,
   `is_auth` gate, redirect-refusal, label-keyed column selection, Decimal, provenance,
   SecretStr at composition root), live-verified digit-for-digit against XBRL gold.
   Commit it; generalize it; do not replace it.
2. **Knowledge over code.** tijori-finance-mcp → its `ARCHITECTURE.md` endpoint
   inventory, the five API traps (esp. silently-ignored unknown params → echo the
   interpreted query back in provenance), and the agent-ergonomics patterns
   (cache-then-slice pagination; empty-with-note, never error, for legitimately-empty
   data; field catalogs behind a search handle). screener-scraper-pro → **GPL-3.0
   clean-room: markup facts only, never open its source while writing our parser.**
3. **Crawl4AI rejected as engine** — both sites server-render the target data; a 6GB
   container + LLM extraction is dead weight and the LLM layer is hostile to
   deterministic provenance. Retained only as a bounded discovery/diagnostic tool; if a
   surface is ever proven browser-gated, all members prefer thin Playwright over
   Crawl4AI.
4. **Subscriber-surface route discovery is a gate, not an assumption.** Screener custom
   metrics / core watchlist / saved screens have unknown routes; a live owner-session
   network capture decides HTTP-reachable vs JS-gated before anything is promised.
5. **The named shared enemies:** positional column zipping (all four external parsers)
   → label-bound selection with ambiguity rejection, everywhere; identity fail-open
   (all three repos) → per-response assertion; float money → Decimal from the wire.

## Conflicts and rulings

| Question | Positions | Ruling |
|---|---|---|
| CLI vs MCP | Opus: CLI only, MCP deferred until an external consumer exists. Sol: CLI canonical + thin MCP facade. x-alpha: CLI now, MCP at Phase 5 | **CLI now, single core; MCP as a thin facade later** (earliest when ≥2 sources are stable). Opus's context-budget argument (30+ always-resident tool schemas taxing every agent turn) is decisive for now; Sol/x-alpha's handle-based MCP design is the blueprint for when it comes. |
| HTTP client | x-alpha: add httpx. Opus: stay urllib (house pattern, AK rule 11). Sol: neutral | **urllib via one shared fetcher.** Zero new dependencies; the existing adapter proves sufficiency; conformance beats taste. Revisit only when connection pooling is a measured need. |
| openscreener reuse | Sol: selectively absorb code+tests. Opus: label map only (retracts its own Stage 1 seam enthusiasm — `parse_number` destroys raw text and units before our contract can see them). x-alpha: knowledge only | **Label map only, with MIT attribution.** Opus's retraction is the best-evidenced position: the library's value funnel is structurally lossy for our Observation contract, and its transport/fail-open behaviors are the parts we must not inherit. |
| First-phase order | Opus: discovery first, then Screener auth slice. Sol: combined 5–8-day slice. x-alpha: widen Tijori first (pure mapping on a green adapter) | **Both tracks, discovery-gated:** commit + harden the Tijori adapter and widen it across the island (no discovery needed — same GET); in parallel, run the owner-session capture for both sites, which gates the Screener subscriber slice. |

## Best-of synthesis (the plan of record)

**Phase 0 — commit + capture (days).** Commit the Tijori adapter with three fixes
(`json.loads(..., parse_float=Decimal)` so raw wire text survives; dedupe
`_SCOPE_ASSUMED_NOTE`; retire/flip the now-verified `live_dom_verified` gate — plus
x-alpha's anchor-honesty fix: stop labeling island anchors as XBRL contexts). Owner
browser session + network capture on both sites exercising: company page, custom
metrics/columns, core watchlist, a saved screen, documents. One time-boxed throwaway
`discover.js` run under the owner's account; delete the clone after. Deliverable:
`docs/research/screener-tijori-endpoint-inventory.md` incl. each site's logged-in
marker.

**Phase 1 — Tijori breadth (days).** Generalize `fetch_pl` → `fetch_table(key)` across
`qt_c/qt_s/pl_*/bs_*/cf_*/fr_*/growth`; read `financials_locks` + `plan_details` into
provenance (distinguishes plan-locked from absent — no external tool can); verify the
other 9 watchlist stocks' full-legal-name slugs live.

**Phase 2 — Screener subscriber core (~1 week).** Shared polite fetcher extracted;
`ScreenerCredentials(SecretStr)` mirroring Tijori; cookie on every GET; **mandatory
logged-in-marker assertion before parsing** (Opus's R1: an expired cookie yields a
valid anonymous page — never silently downgrade, never retry anonymously); clean-room
section parsers against captured-real-HTML fixtures; record standalone-vs-consolidated
as an observed fact per response.

**Phase 3 — reconciliation + snapshots.** Sol's typed outcome taxonomy (OK-empty /
PLAN_LOCKED / NOT_OFFERED / AUTH_EXPIRED / IDENTITY_MISMATCH / SCHEMA_DRIFT /
RATE_LIMITED / TRANSPORT_ERROR); append-only content-hashed snapshot store; stable
entity-ID mapping {NSE symbol, BSE scrip, Screener id, Tijori slug+company_id};
three-source tolerance compare (XBRL spine ⊕ Tijori ⊕ Screener) so a drifted parser
surfaces as a mismatch, not quiet self-agreement.

**Phase 4 — full breadth, registry-driven.** Sol's capability registry (discovered →
captured → parsed → verified → agent-exposed), one surface at a time, demand-driven
from the reconciler; Tijori KPIs/fund-flow/revenue-mix/market-intel/screens; Screener
screens/watchlist/custom metrics/exports.

**Phase 5 — MCP facade + monitoring readiness.** Thin read-only MCP over the same core
(handles + bounded samples, not table dumps); x-alpha's weekly one-slug polite canary;
diff primitives finalized. Alerts remain a separate layer.

**Standing controls:** politeness (sequential, spaced, stop-on-429, daily caps until
safe rates measured); kill switch per site; GPL clean-room policy written into the
Screener parser's docstring; A05-DECISION-005 boundary (private, subscriber, derived
only, no redistribution) bound to every adapter.

## Gaps no member fully covered (judge's additions)

1. The remaining 9 watchlist `tijori_slug`s follow the disproven short scheme — slug
   re-verification is folded into Phase 1, not left implicit.
2. Cookie storage is currently `~/.secrets/` files; acceptable now, but the
   `SessionProvider` should treat storage as pluggable so an OS keyring can slot in
   without adapter changes.
3. Work-state: phases land as beads under a `screener-tijori-acquisition` workstream so
   session hand-offs survive compaction.

## Flip conditions (carried from members, monitored)

- A sanctioned API/bulk export under either subscription → scraping becomes second
  choice immediately (nobody has checked; Phase 0 asks).
- `fin_tables_data` proves non-universal across companies → island becomes fast path,
  documented fallback tier added.
- Screener subscriber surfaces prove JS-walled → thin Playwright service for those
  surfaces only (never Crawl4AI, never anti-bot evasion).
