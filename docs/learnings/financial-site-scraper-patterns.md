# Financial-Site Scraper Patterns — Learnings from the Tijori Breadth Build

Earned 2026-08-24/25 across the Tijori acquisition slices (commits `fc10a0e`,
`5677e30`, `2bb90d1`, `bde0b3e`, `e486209`): ~15 implementation rounds, 4
independent critiques (18 findings), ~12 live-taught contract facts. Written
for the Screener build (Phase 2) and any future source adapter.

## The five load-bearing patterns

### 1. Fixtures always pass; live data writes the contract

Every slice went gates-green on synthetic fixtures, then live data broke it
with facts no fixture author could invent: `field: "NA"` as a no-id sentinel,
`sub_section: ""` on leaf rows, JSON-null tables for standalone-only
companies, byte-identical duplicate islands, the same shareholder under two
category buckets, nesting hidden below a depth-capped probe.

Process fixes that worked:

- **Capture real pages before implementing.** The one slice given real HTML
  up front (events) needed zero structural fix rounds from its live smoke.
- **Smoke across structurally different companies, not just the flagship.**
  TITAN alone validates nothing; NETWEB (standalone-only), ETERNAL (fresh
  listing), HFCL (reclassified shareholders) each taught a contract fact
  TITAN could not.

### 2. The severity inversion is the default bug

Parsers naturally come out fatal about things the source is entitled to do
(extra keys, repeated labels, missing sub-rows) and silent about what
actually loses data (a lock flag discarding present content, wrong-typed
fields becoming blank-but-counted entries, empty-success). Every review
round found this inversion somewhere. Review lens: for each fatal check ask
"is the source entitled to do this?"; for each tolerant path ask "what data
can vanish here without a trace?".

### 3. Wrong-but-plausible is the threat model, not crashes

The dangerous failures were valid-looking artifacts, never exceptions: an
expired cookie yielding a valid anonymous page, error statuses inside
HTTP-200 bodies, decoy tables that parse cleanly, empty artifacts reading as
"no data", a filter taxonomy that looks like an event feed. Countermeasures
that stuck:

- Typed outcome enums where an artifact is either OK or **provably** empty
  (`element_count == 0` with no quarantined rows); everything else raises.
- Positive evidence markers — never absence-of-bad as proof of good.
- Selection by stable id **plus** shape proof; either alone is spoofable.
- Validate body-level status fields even under HTTP 200.

### 4. Identity is per-surface and never guessable

Four Tijori surfaces used four identity mechanisms (`company_details`
island, `company_details_data` island, `<h1 comp_id>` attribute, URL-only).
Slugs are historical-name fossils (`zomato-ltd` for Eternal,
`crompton-greaves-limited` for CG Power) — resolve via the site's own search
API, then verify on the fetched page. Body-wide grep is provably unsafe:
peer widgets carry other companies' symbols earlier in the page. Anchor
everything to a numeric source-native company id, live-verified once,
stored in config with uniqueness validation, and refuse identifiers flagged
`needs_verification`. Where a response carries no identity at all (bare
JSON APIs), record the weaker basis explicitly (`CONFIGURED_URL_ONLY`) and
bar such data from fact promotion by type.

### 5. Retention beats rejection for drift

The shape that survived three critiques: unknown keys → recorded verbatim
(`unmodeled_fields_json`); known-but-unreadable → recorded verbatim in a
**distinct** slot (`invalid_fields_json`); unalignable rows → quarantined
with their lexemes, never position-guessed; raw response bytes retained
beside artifacts, hash-verified. Fail loud only where addressing is
genuinely ambiguous (duplicate final paths under one parent).

## Secondary patterns

- **Indian financial sites are server-rendered.** No JS wall found anywhere
  on Tijori or Screener subscriber surfaces. Embedded JSON islands beat DOM
  parsing wherever they exist; the headless browser is for discovery,
  capture, and verification — never acquisition.
- **Markup carries more machine structure than it advertises**: nesting
  attributes (`rowN`/`myid`/`data-parent`), stable element ids
  (`company_detailed`), field ids on rows. Inspect the real markup before
  writing any heuristic.
- **Provenance discipline compounds.** Honest anchor types per retrieval
  procedure (page island / HTML table / API document) caught a latent
  value-hash collision in already-committed code; positional path segments
  wherever the source lacks unique keys; a duplicate-anchor backstop turns
  future collisions into loud failures.
- **Templates repeat content**: identical islands rendered twice per page
  (collapse iff byte-identical, differing stays fatal), sample-report modals
  embedded in every page (select by id + shape, never index), full HTML
  documents embedded inside data cells (structural checks must inspect only
  root children).
- **Scope rulings belong in the tracker, not chat.** Both "unimplemented
  scope" review findings were actually undocumented rescopes; record
  exclusions on the bead and as a code comment at the registry.
- **Process**: implementer/critic separation across model vendors caught 18
  real findings; the orchestrator's live smoke between rounds was the
  single highest-value verification step; per-surface plans with a
  structure-only evidence file beat prose descriptions.

## Screener-specific carryover (Phase 2)

- The expired-cookie trap: Screener serves a **valid anonymous page** to a
  dead session. Pin a per-response logged-in assertion derived from an
  anonymous-vs-authenticated diff of the same URL; never silently downgrade.
- Screener's support APIs use **two distinct numeric company-id
  namespaces** (observed in the owner HAR); map both before trusting either.
- Record consolidated-vs-standalone as an observed fact per response, not
  an assumption.
- Capture real HTML for every subscriber surface (headless, owner session)
  **before** writing any parser; base synthetic fixtures on those captures;
  never commit captures (rights boundary A05-DECISION-005).
