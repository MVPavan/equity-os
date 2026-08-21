# Fundamentals — Infosys Pilot Build Plan

**Status:** DRAFT for review (build contract for the first product code).
**Scope class:** deep (first product code; introduces the product package).
**Product name:** Fundamentals (A-09 SELECTED).
**Date:** 2026-08-21.

## 1. Goal (one sentence)

Produce **one source-backed Infosys earnings update for Q1 FY25**, end-to-end, from
first-party data through typed verified facts to a cited markdown output — the smallest
vertical slice that proves the product works.

Success = a runnable command that emits a markdown earnings update in which **every number
traces to a stored fact with provenance** (source, file hash, page/context anchor), and the
core figures pass cross-checks against an independent source.

## 2. Non-goals (explicitly deferred)

- Multiple companies or quarters (pilot is INFY, Q1 FY25 only).
- News ingestion (later increment: RSS + Marketaux + GDELT — see `docs/research/india-news-sourcing.md`).
- Tijori enrichment (optional adapter, later — see `docs/research/tijori-mcp-evaluation.md`).
- BSE path (NSE + PDF + SEC cover the pilot; BSE via crawl4AI is a later source adapter).
- Any public/commercial output (private/personal boundary per A05-DECISION-004).

## 3. Proven architecture (from the evaluations)

```
INGEST            EXTRACT                 VERIFY                 STORE          OUTPUT
NSE XBRL (libs) → context-aware parse  → cross-foot            → SQLite      → sourced
Infosys PDF     → Luna extract+Opus     → quote-anchor         (provenance-    earnings
(lawfully held)   review (narrative)    → XBRL↔PDF↔SEC cross-    bound)          update
SEC XBRL        → arelle/edgartools       check                                (markdown)
```

Sources for the pilot, all rights-cleared:
- **Infosys Q1 FY25 PDF** — already lawfully retrieved (`data/raw/infy-fy25/`, A05-DECISION-001).
- **NSE Ind AS XBRL** — via `nselib` / `NseIndiaApi` (A05-DECISION-004, private use).
- **SEC XBRL** — annual FY25 20-F, automated access allowed (A05-DECISION-001). Used as
  independent cross-check (USD; guard the currency).

## 4. The three gotchas (baked into the plan, from the evaluations)

1. **XBRL context-aware parsing** — each fact appears under multiple `xbrli:context` refs
   (quarter / YTD / prior-year). Naive first-value extraction returned a WRONG PAT
   (₹6,822 Cr vs correct per-quarter ₹6,358 Cr). The parser MUST bind each fact to the
   intended period context. This is an explicit acceptance test (see Slice 1).
2. **BSE taxonomy split** — `in-bse-fin` through Dec-2024, `in-capmkt` from Mar-2025.
   Not in the pilot (NSE-only), but the XBRL parser design must not hard-code one taxonomy.
3. **Currency guard** — SEC 20-F is USD; Ind-AS filings are INR. Cross-checks must compare
   like-for-like (SEC ↔ Infosys IFRS press release, not the ₹-crore PDF). A hard currency
   assertion prevents fake discrepancies.

## 5. Package structure (Python, per repo rules)

New product package under `src/fundamentals/` (uv project; `pyproject.toml` at repo root).
Follows `.claude/rules/python/*`: pydantic frozen models, `contracts/` for shared types,
downward dependency flow, one core class per file, ruff + mypy --strict, structlog, uv.

```
pyproject.toml                     # uv project, ruff/mypy config
src/fundamentals/
  contracts/                       # shared frozen pydantic types (no deps)
    fact.py                        # FinancialFact, NarrativeFact, GuidanceFact
    provenance.py                  # Provenance (source_id, file_sha256, anchor, retrieved_at)
    period.py                      # ProgramQuarter/IssuerQuarter enums
  ingest/
    xbrl_source.py                 # fetch + hold NSE XBRL (via libs), provenance-stamped
    pdf_source.py                  # load lawfully-held PDF, page text + hashes
    sec_source.py                  # SEC XBRL facts (cross-check only)
  extract/
    xbrl_parser.py                 # context-aware XBRL -> FinancialFact  (GOTCHA 1)
    narrative_extractor.py         # Luna extract from PDF -> GuidanceFact (Opus reviews)
  verify/
    crossfoot.py                   # accounting identities (±0.5 tolerance)
    cross_check.py                 # XBRL <-> PDF <-> SEC, with currency guard (GOTCHA 3)
    quote_anchor.py                # every extracted narrative fact must quote its source
  store/
    fact_store.py                  # SQLite (WAL), provenance-bound, idempotent upsert
  output/
    earnings_update.py             # render markdown; every number cites a stored fact
  api/
    pipeline.py                    # orchestrates the slice; CLI entrypoint
tests/fundamentals/                # pytest; unit for parsers/verify, integration for store
```

## 6. Phased slices (each independently verifiable)

Routing per session policy: Opus 5 implements each slice (separate session per slice); a
separate Opus 5 session reviews; narrative extraction uses GPT 5.6 Sol Luna with Opus review.
Trivial slices may skip independent review.

**Slice 0 — Scaffold.** `pyproject.toml` (uv), package skeleton, `contracts/` types, a
trivial passing test, ruff + mypy + pytest wired.
→ verify: `uv run ruff check`, `uv run mypy --strict src`, `uv run pytest` all green.

**Slice 1 — XBRL → verified P&L facts (core loop).** `xbrl_source` fetches the INFY Q1 FY25
Ind AS XBRL (provenance-stamped); `xbrl_parser` parses it **context-aware** into typed
`FinancialFact`s; `crossfoot` checks the identities.
→ verify: parsed **PAT == ₹6,358 Cr** (the correct per-quarter value, NOT ₹6,822 Cr — this
test encodes GOTCHA 1); Revenue == ₹39,315 Cr; cross-foot identities pass at ±0.5.

**Slice 2 — Provenance-bound fact store.** `fact_store` persists facts to SQLite with full
provenance; idempotent upsert.
→ verify: facts round-trip; re-running the pipeline produces zero duplicates; every stored
fact has a non-null `Provenance` with file_sha256 matching `data/raw/`.

**Slice 3 — Narrative / guidance extraction.** `narrative_extractor` runs GPT 5.6 Sol Luna
over the lawfully-held Q1 PDF to extract management guidance (revenue 3–4% CC, margin 20–22%)
as `GuidanceFact`s; Opus reviews the extraction; `quote_anchor` requires each fact to carry a
verbatim source quote that literally exists in the extracted PDF text.
→ verify: guidance figures match the PDF; every `GuidanceFact` passes quote-anchoring; a
planted wrong quote fails the anchor check.

**Slice 4 — Sourced earnings update.** `earnings_update` renders a markdown Q1 FY25 update
from stored facts (numbers + guidance), each figure footnoted to its provenance.
→ verify: every number in the output resolves to a stored fact; removing a fact removes its
line (no un-sourced numbers); output builds via one CLI command.

**Slice 5 — Independent cross-check (confidence).** `sec_source` + `cross_check` validate the
FY25 annual figures against SEC XBRL with the currency guard.
→ verify: SEC ↔ Infosys IFRS annual match to the dollar; an INR-vs-USD comparison is rejected
by the currency guard (GOTCHA 3).

## 7. Verification gates (the product's integrity rules)

Every slice enforces the evidence-first doctrine:
- **No un-sourced number** reaches the store or the output.
- **Quote-anchoring** — extracted narrative facts must quote source text that exists.
- **Cross-footing** — accounting identities hold (±0.5).
- **Cross-source** — headline figures agree across XBRL / PDF / SEC (currency-guarded).
- **Provenance** — every fact carries source_id + file_sha256 + anchor + retrieved_at.

## 8. Rights & boundary recap

Private/personal/non-commercial only (A05-DECISION-004). Source bytes stay in gitignored
`data/`. No redistribution, no public output. The pipeline is a personal research tool.

## 9. Estimate

- Slice 0: ~30 min (scaffold).
- Slice 1: ~half a day (context-aware XBRL parsing is the hard part; the acceptance test guards it).
- Slice 2: ~2 hours (SQLite store + idempotency).
- Slice 3: ~half a day (Luna extraction + Opus review + quote-anchor).
- Slice 4: ~2 hours (render + provenance footnotes).
- Slice 5: ~2 hours (SEC cross-check).

First runnable end-to-end update (Slices 0–4): ~1.5–2 focused days of agent work.

## 10. First concrete action on approval

Slice 0: create `pyproject.toml` + `src/fundamentals/` skeleton + `contracts/` types + a
passing scaffold test, then run ruff/mypy/pytest green. Opus 5 implements; verified before
Slice 1 starts.
