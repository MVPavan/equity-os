# Fundamentals — Infosys Q1 Increment Build Plan

**Status:** DRAFT for review (build contract for the first product code).
**Scope class:** deep (first product code; introduces the product package).
**Product name:** Fundamentals (A-09 SELECTED).
**Date:** 2026-08-21.

## 0. What this increment is (and is not)

This is **the first Q1 implementation increment within the four-quarter Phase 0.5
roadmap** — NOT "the vertical slice." Per `CONTEXT.md`, the *vertical slice* is one
discovery company across four consecutive quarters (Quarter 0 manual baseline + three
assisted updates). This plan delivers only the Q1 assisted-update increment; the
remaining quarters and any decision to collapse the four-quarter experiment into fewer
quarters require a separate explicit phase-gate decision.

## 0a. Prerequisites (binding — approval of this roadmap does NOT authorize product code)

Product code MUST NOT begin until **both** of the following are recorded:

1. **Phase 0A exit gate passed** — the complete Phase 0A exit record per the v2 register
   scorecard (§F) and the goal readiness gate. Phase 0.5 product implementation is blocked
   until then.
2. **Approved build contract** — an explicit build-contract approval for this increment
   (register §F authority). Roadmap approval alone is insufficient.

If either prerequisite is unmet, Slice 0 does not start.

## 1. Goal (one sentence)

Produce **one source-backed Infosys earnings update for Q1 FY25**, end-to-end, from
first-party data through typed verified facts to a cited markdown output — the first
increment that proves the earnings-review workflow works on real filings.

Success = a runnable command that emits a markdown earnings update in which **every number
traces to a stored fact with provenance** (source, file hash, page/block/span anchor), and
the core figures pass a full-comparison-key cross-check against an independent source.

## 2. Non-goals (explicitly deferred)

- Quarters 0, 2, 3 of the Phase 0.5 four-quarter slice (this increment is Q1 FY25 only).
- Multiple companies (pilot is INFY only).
- News ingestion (later increment: RSS + Marketaux + GDELT — see `docs/research/india-news-sourcing.md`).
- Tijori enrichment (optional adapter, later — see `docs/research/tijori-mcp-evaluation.md`).
- BSE `in-capmkt` path and `in-capmkt` taxonomy support (NSE + Q1 `in-bse-fin` cover this
  increment; see Gotcha 2).
- Any external-model document processing (removed by product-owner decision 2026-08-21; see §5).
- Any public/commercial output (private/personal boundary per A05-DECISION-004).

## 3. Rights posture (accurate wording)

All sources are **owner-authorized, private-use risk accepted within the recorded boundary**
(A05-DECISION-004) — NOT "rights-cleared" and NOT a legal clearance. Extraction is
**local and deterministic**; no source bytes are transmitted to any external model or service.
This keeps the whole pipeline inside A05-DECISION-004 (collection + internal processing +
internal derived facts, private/personal/non-commercial only).

- **Infosys Q1 FY25 PDF** — already lawfully retrieved (`data/raw/infy-fy25/`, A05-DECISION-001).
- **NSE Ind AS XBRL** — via `nselib` / `NseIndiaApi` (A05-DECISION-004, private use).
- **SEC XBRL** — annual FY25 20-F, automated fair-access allowed (A05-DECISION-001). Used ONLY
  as retrospective annual-adapter validation, excluded from the Q1 evidence package (see §4, §7).

## 4. Proven architecture (from the evaluations — local deterministic only)

```
INGEST            EXTRACT                       VERIFY                     STORE          OUTPUT
NSE XBRL (libs) → context-aware XBRL parse   → full-comparison-key      → SQLite      → sourced
Infosys PDF     → local PDF number parse       cross-foot (decimals-      (append-      earnings
(lawfully held)   (PyMuPDF word-geometry)      derived tolerance)         only,          update
                → local rule-based guidance   → quote-anchor (page/       revision-      (markdown)
                  range extraction              block/span binding)        aware)
SEC XBRL        → edgartools (annual only,    → cross-source w/ full key
                  retrospective validation)     (currency + scope + …)
```

Design rules baked in:

- **No external-model upload.** All extraction (numbers and narrative/guidance) is local
  deterministic parsing. There is no GPT/Luna PDF-upload lane.
- **The deterministic PDF numbers parser exists BEFORE output**, because the XBRL↔PDF
  cross-check depends on it.
- **SEC FY25 is annual and was filed 2025-07-01.** It is used as retrospective ANNUAL adapter
  validation and is excluded from the Q1 evidence package by `knowledge_time <= update_cutoff`
  to avoid cutoff leakage. Output is built only after the cross-checks it depends on.

## 5. External-model decision (product owner, 2026-08-21, binding)

**Extraction is LOCAL/DETERMINISTIC — NO external model upload.** The prior "Luna extract +
Opus review" narrative lane is removed. Management guidance is extracted by local rule-based
parsing of PyMuPDF word-geometry output (guidance ranges, units, horizons, constant-currency
basis), and validated by a deterministic quote-anchor check that binds each claim to an exact
page/block/span in the held PDF. A05-DECISION-004 does not authorize third-party upload; the
pipeline fails closed before any external transmission.

## 6. The gotchas (baked into the plan, from the evaluations)

1. **XBRL context-aware parsing (fact-identity collapse — the dominant risk).** Each concept
   appears under multiple `xbrli:context` refs (quarter / YTD / prior-year / comparative /
   standalone). A fact is only identified when concept QName, period, scope, unit, dimensions
   and knowledge cutoff are all proven — a matching label and plausible value are not enough.
   The Q1 acceptance test pins the exact measurement; a separate Q3 fixture test exercises the
   real quarter-vs-YTD-vs-prior-year selection (see Slice 1).
2. **BSE taxonomy split** — `in-bse-fin` through Q3, `in-capmkt` from Q4 (both namespaces
   demonstrated in the crawl4AI evaluation). Honest scope for this increment: **Slice 1 targets
   Q1 `in-bse-fin` only and does NOT claim taxonomy independence.** Concept resolution goes
   through a versioned concept registry so a later `in-capmkt` adapter is additive, but no
   `in-capmkt` support is built or claimed here.
3. **Currency + scope guard** — SEC 20-F is USD/annual; Ind-AS filings are INR/quarterly.
   Cross-checks require the full comparison key (see §12), not a currency-only guard.

## 7. Data model — layered contracts (one core class per file)

Generic `FinancialFact` + thin `Provenance` cannot represent XBRL identity or revisions. Define
these provisional contracts **before the parser** (each in its own file under `contracts/`):

- **`Observation`** (`contracts/observation.py`) — a single measured occurrence:
  concept QName + taxonomy/registry version, raw lexical value, normalized decimal,
  `context_ref`, entity, consolidated/standalone scope, period start/end or instant,
  period_type, `unit_ref`, currency/scale, decimals, dimensions, source occurrence and typed
  source anchor.
- **`Fact`** (`contracts/fact.py`) — a reconciled identity over observations:
  reconciled observation identity, quality/reconciliation status, valid time,
  knowledge/first-seen time, revision family, canonical-selection status.
- **`GuidanceClaim`** (`contracts/guidance_claim.py`) — management guidance as a claim:
  range bounds, unit, constant-currency basis, horizon, scope, qualifiers, `forecast`
  epistemic class. (Replaces the undifferentiated `GuidanceFact`.)
- **`Provenance`** (`contracts/provenance.py`) — source_id, file_sha256, typed anchor
  (page/block/span), retrieved/filed/published/first-seen times.

This matches the required append-only, revision-aware B-05/B-11 semantics; field lists remain
provisional until frozen through their register items.

## 8. Store — append-only, revision-aware (NOT upsert)

Corrections and restatements must never be silently overwritten (product-doctrine invariant).

- **Identical content identity → return the existing row.** Anything else → **append** a new
  extraction/revision under the same revision family.
- **Canonical selection is a separate, auditable step**, not a side effect of writing.
- No idempotent upsert. Defer SQLite WAL until a measured concurrency need justifies it.

## 9. Package structure (Python, per repo rules)

New product package under `src/fundamentals/` (uv project; `pyproject.toml` at repo root).
Follows `.claude/rules/python/*`: frozen pydantic models, `contracts/` for shared types,
downward dependency flow, **one core class per file**, ruff + mypy --strict, structlog, uv.

```
pyproject.toml                     # uv project, ruff/mypy config
config/fundamentals.yaml           # non-secret settings (endpoints, paths, SEC UA, CIK)
src/fundamentals/
  contracts/                       # shared frozen pydantic types (no deps)
    observation.py                 # Observation
    fact.py                        # Fact
    guidance_claim.py              # GuidanceClaim
    provenance.py                  # Provenance
    period.py                      # ProgramQuarter / IssuerQuarter enums
    comparison_key.py              # ComparisonKey (issuer, concept, period, scope, dims, basis, currency, unit, scale)
  ingest/
    xbrl_source.py                 # fetch + hold NSE XBRL; timeout + bounded retry; retrieval manifest
    pdf_source.py                  # load lawfully-held PDF, page words + hashes
    sec_source.py                  # SEC XBRL facts via edgartools (annual validation only)
  extract/
    xbrl_parser.py                 # context-aware XBRL -> Observation  (GOTCHA 1)
    pdf_number_parser.py           # PyMuPDF word-geometry -> Observation (deterministic, pre-output)
    guidance_extractor.py          # local rule-based guidance ranges -> GuidanceClaim
  verify/
    comparison_key.py              # build/require full comparison key before any compare
    crossfoot.py                   # accounting identities; tolerance derived from XBRL decimals
    cross_check.py                 # cross-source w/ full comparison key (GOTCHA 3)
    quote_anchor.py                # bind each GuidanceClaim to an exact page/block/span
  store/
    fact_store.py                  # SQLite, append-only + revision-aware; canonical selection separate
  reconcile/
    canonical_selection.py         # auditable canonical-fact selection over revision families
  output/
    earnings_update.py             # render markdown; missing required fact FAILS CLOSED
  api/
    cli.py                         # composition root: load YAML config, inject config/secrets into adapters
    pipeline.py                    # orchestrates the increment
tests/fundamentals/                # pytest; unit for parsers/verify, integration for store
data/fixtures/fundamentals/        # measurement manifest + synthetic multi-context XBRL fixtures
```

Config injection: `api/cli.py` is the composition root. It loads non-secret YAML from
`config/fundamentals.yaml` and injects config + secrets into adapters. **No `os.environ` reads
in business logic.** SEC uses **pinned `edgartools` (5.51.0) + raw companyfacts JSON** — Arelle
is NOT used (the bake-off rejected it for this use).

## 10. Pre-Slice-0 step — freeze the Q1 measurement manifest (the ORACLE)

**This is the single biggest de-risk and it happens BEFORE Slice 0.** Fact-identity collapse is
the dominant failure mode; a frozen oracle is the guard.

Freeze `data/fixtures/fundamentals/q1-measurement-manifest.json` containing, for each pinned Q1
measurement: exact source file **sha256 hashes**, concept **QNames** (+ taxonomy/registry
version), **contexts** (`context_ref`), **periods** (start/end/instant), **scopes**
(consolidated/standalone), **units** (`unit_ref`, currency, scale), **decimals**, and the
**expected raw + normalized values** — PLUS **adversarial distractor contexts** (wrong-period,
YTD, prior-year comparative, standalone) that MUST NOT be selected.

Pinned Q1 FY25 consolidated values (Apr–Jun 2024, ₹ crore, from PDF bake-off §3a, cross-foot
4/4 pass): Revenue from operations **39,315**; **`ProfitLossForPeriod` = 6,374**; PBT 9,021;
EPS basic 15.38.

This manifest is the oracle for the parser, store, and rendering tests. No Slice 0 until it is
frozen.

## 11. Phased slices (each independently verifiable)

Routing per session policy: an **Implementer** subagent implements each slice (fresh session per
slice); an independent **Reviewer** session reviews. Trivial slices may skip independent review.
No named model lanes.

**Slice 0 — Scaffold.** (Gated on §0a prerequisites + §10 manifest.) `pyproject.toml` (uv),
package skeleton, `contracts/` types (one class per file), `config/fundamentals.yaml`, the
`api/cli.py` composition root, a trivial passing test, ruff + mypy + pytest wired.
→ verify: `uv run ruff check`, `uv run mypy --strict src`, `uv run pytest` all green.

**Slice 1 — XBRL → verified P&L facts (core loop).** `xbrl_parser` parses the INFY Q1 FY25 Ind
AS XBRL **context-aware** into typed `Observation`s; `crossfoot` checks identities with a
tolerance **derived from XBRL `decimals`** (not fixed ±0.5). Deterministic parser tests run
against the frozen manifest fixtures; live NSE fetch is a separate opt-in integration test
(with requested-quarter presence check, timeout, bounded retry — see §12).

→ verify (Q1 acceptance, from the manifest oracle):
- assert **`ProfitLossForPeriod` == ₹6,374 Cr**, bound to the **Apr–Jun 2024 duration context**
  and the concept QName; cross-checked against the PDF (Revenue 39,315 / profit 6,374).
- the wrong-period / YTD / prior-year / standalone distractor contexts are **rejected**.
- **Note:** Q1 cannot exercise the quarter-vs-YTD gotcha (in Q1 the YTD period equals the
  quarter, so the context ambiguity cannot manifest). The old 6,358/6,822 "oracle" was a
  CONCEPT mismatch (attributable-to-owners vs `ProfitLossForPeriod`), not a Q1 context issue.

→ verify (SEPARATE Q3 fixture test — the real Gotcha 1): against a pinned Q3 XBRL fixture, the
parser selects the **quarter-duration context** (Oct–Dec 2024) for `ProfitLossForPeriod`
(**₹6,822 Cr**, matching the printed Q3 statement) and **rejects** the YTD (nine-month) and
prior-year contexts; and it disambiguates `ProfitLossForPeriod` from the distinct
attributable-to-owners concept (the ₹6,358 Cr value) as a different QName, not a relabelling.

**Slice 2 — Deterministic PDF numbers parser + append-only fact store.** `pdf_number_parser`
extracts the consolidated P&L via PyMuPDF word-geometry into `Observation`s; `fact_store`
persists them **append-only, revision-aware**; `canonical_selection` chooses the canonical fact
separately and auditably.
→ verify: PDF numbers match the manifest (Revenue 39,315 / profit 6,374; cross-foot 4/4);
facts round-trip; **re-running with identical content identity returns the existing row (no new
revision); a changed observation appends a new revision** under the same family; canonical
selection is recorded and auditable; every stored fact has non-null `Provenance` with
`file_sha256` matching `data/raw/`.

**Slice 3 — Local guidance extraction.** `guidance_extractor` parses management guidance from
the PyMuPDF word-geometry of the held Q1 PDF (revenue 3–4% CC, margin 20–22%) into
`GuidanceClaim`s; `quote_anchor` binds each claim to an **exact page/block/span** in the PDF
(not substring presence).
→ verify: guidance figures match the PDF; every `GuidanceClaim` resolves to a real
page/block/span anchor; a claim whose anchor does not exist at that span FAILS the check; no
external transmission occurs.

**Slice 4 — Sourced earnings update.** `earnings_update` renders a markdown Q1 FY25 update from
stored canonical facts + guidance, each figure footnoted to its provenance.
→ verify: every number resolves to a stored fact; a **missing required fact FAILS CLOSED
(aborts the render)** — it does not silently drop a line; output builds via one CLI command.

**Slice 5 — Independent retrospective cross-check (confidence).** `sec_source` + `cross_check`
validate the FY25 **annual** figures against SEC XBRL using the **full comparison key**. This is
retrospective annual-adapter validation, excluded from the Q1 evidence package by
`knowledge_time <= update_cutoff`.
→ verify: SEC ↔ Infosys IFRS annual match under the full comparison key; a comparison whose key
differs (currency, period, scope, basis, unit, scale, or concept) is **rejected**, not silently
compared.

## 12. Verification gates (the product's integrity rules)

Every slice enforces the evidence-first doctrine:

- **Full comparison key before any compare.** Cross-foot and cross-source compares require
  issuer, concept, period, scope, dimensions, accounting basis, currency, unit, and scale to
  match first. Cross-footing alone does not prove column identity (a wrong YTD/comparative
  column can cross-foot perfectly).
- **Decimals-derived tolerance.** Numeric tolerance is derived from the XBRL `decimals`/scale,
  not a fixed ±0.5.
- **Fail closed on missing required facts.** A missing required input aborts the render; it
  never merely removes an output line.
- **Quote-anchoring binds to an exact page/block/span**, not substring presence.
- **No un-sourced number** reaches the store or the output.
- **Provenance** — every fact carries source_id + file_sha256 + typed anchor + timestamps.
- **Fetch safety** — deterministic parser tests are separated from an opt-in live ingestion
  test; live fetch verifies issuer, period, filing type and consolidation scope before parsing,
  uses explicit timeout + bounded retry, records a retrieval manifest (URI, filed/published/
  retrieved/first-seen times, response hash), and on failure/staleness stores **no** facts and
  raises a typed, resumable failure.

## 13. Rights & boundary recap

**Owner-authorized, private-use risk accepted within the recorded boundary** (A05-DECISION-004).
Private/personal/non-commercial only. Source bytes stay in gitignored `data/`. All extraction is
local deterministic — no external-model upload. No redistribution, no public output.

## 14. Estimate

- Pre-Slice-0 manifest: ~half a day (the oracle; source-of-truth for every downstream test).
- Slice 0: ~1 hour (scaffold + composition root + contracts split by class).
- Slice 1: ~1 day (context-aware XBRL parsing + Q1 acceptance + separate Q3 fixture test).
- Slice 2: ~half a day (deterministic PDF parser + append-only store + canonical selection).
- Slice 3: ~half a day (local guidance parsing + exact-span quote-anchor).
- Slice 4: ~2 hours (render + provenance footnotes + fail-closed).
- Slice 5: ~2 hours (SEC annual retrospective cross-check with full comparison key).

Revisit after the manifest and fixtures are frozen. First runnable end-to-end update
(manifest + Slices 0–4): ~2.5–3 focused days of agent work.

## 15. First concrete action on approval

Confirm §0a prerequisites (Phase 0A exit gate + approved build contract) are recorded. Then
freeze the §10 Q1 measurement manifest. Only then start Slice 0 (`pyproject.toml` +
`src/fundamentals/` skeleton + `contracts/` classes + `api/cli.py` composition root + a passing
scaffold test), and run ruff/mypy/pytest green. An Implementer implements; an independent
Reviewer verifies before Slice 1 starts.
