# External Tools, Services, and Data-Source Inventory

**Version:** 1.0.0
**Date:** 2026-08-20
**Status:** NON-AUTHORITATIVE research inventory. The binding authority remains
`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md`.
Listing an item here is **not** adoption, permission, or a rights decision.
**Sources of this inventory:**
1. Original blueprint enumeration — `docs/blueprint/org/funda-agentic-stock-research-blueprint.md` (~76 named items), as extracted by the independent drift review `scratchpad/blueprint-drift/original-blueprint-drift-review-r0.md` §4.
2. User-supplied candidate repository list, 2026-08-20 (20 repos; 6 were duplicates of existing entries and are merged in place, 14 added as new entries in §6).

**Standing rights rule (applies to every row):** all source-rights dispositions
are fail-closed (`docs/evidence/phase-0a/a-05-source-rights-package.json`:
132/132 cells `UNKNOWN (denied by default)`). A library, MCP server, or scraper
that accesses NSE, BSE, Screener.in, Tijori, or issuer sites **does not confer
rights** — it hits the same endpoints the publishers' terms govern. NSE's live
terms expressly prohibit systematic/automated data collection including
scraping. Using any wrapper below against those endpoints is denied until an
A-05 disposition says otherwise.

**Status vocabulary**

| Status | Meaning |
|---|---|
| ADOPTED | Named and selected in a current binding document. |
| DEFERRED-RECORDED | Name appears in a current binding document with a deferral/exclusion decision ID. |
| EXCLUDED-RECORDED | Explicitly excluded by a recorded disposition. |
| CAPABILITY-DEFERRED, NAME-DROPPED | The function is deferred by a register/DEF row but the named tool is absent from current docs. |
| IN-EVIDENCE-ONLY | Appears only in Phase 0A evidence artifacts; not in any binding contract. |
| NEVER-DECIDED | Absent from every current authority document; no decision of any kind exists. |
| CANDIDATE-UNDECIDED | Added to this inventory (user-supplied or new); awaiting triage; no decision exists. |
| CONFLICTED | Contradictory statements across current documents. |

---

## 1. Adopted (1)

| # | Item | Where adopted |
|---:|---|---|
| 1 | **SQLite (WAL)** | Register v2 §H; `architecture-brief-v2.md` §13 (with SCALE-SQLITE-01…04 migration triggers) |

## 2. Deferred / excluded with a recorded decision (9)

| # | Item | Blueprint role | Recorded decision |
|---:|---|---|---|
| 1 | **GBrain** | Memory engine, Phase 2 | D-02/D-04/D-05 Deferred; DEF-02; S19/S20 benchmark candidate behind neutral `MemoryStore` |
| 2 | **OpenBB ODP** (`OpenBB-finance/OpenBB`) | Data platform, Phase 1 | E-06 Deferred; if adopted, out-of-process behind an Equity-OS adapter; needs A-05 Accepted + ACTIVATE_DEFERRED |
| 3 | **FinanceHarness** | Pattern reference, Phase 0 | E-07, S03 dormant due-diligence gate |
| 4 | **Vibe-Trading** (`HKUDS/Vibe-Trading`) | Benchmark reference, Phase 0 | E-07, S03 dormant due-diligence gate |
| 5 | **PostgreSQL** | Scale relational store | DEF-13 — migrate only on measured trigger |
| 6 | **Durable queue / workflow engine** | Introduce only when required | DEF-13 + SCALE-WORKFLOW-01…04; simple state tables default |
| 7 | **Earnings-call audio / transcription** | Tier 1/2 source | C-14, S09 conditional |
| 8 | **Consensus estimates / licensed institutional feeds** | Tier 2, likely needed if commercial | C-13 excluded by default; DEF-07; Tier-3 vendor feed PROPOSED only (`architecture-brief-v2.md` §432) |
| 9 | **Temporal-class infra** (Temporal / homelab / Bodha / pre-existing PostgreSQL) | Not in the blueprint; crept in via reviews | EXCLUDED-RECORDED — third-order disposition 6.7: "must not be treated as architecture facts" |

## 3. Capability deferred, name dropped (7)

The function is covered by a register/DEF row; the blueprint's named tool is absent from all current docs.

| # | Item | Blueprint role | Covering row |
|---:|---|---|---|
| 1 | **FinRobot** (`AI4Finance-Foundation/FinRobot`) | Deterministic operators — direct/likely dependency | First-party S16/E-01 |
| 2 | **TradingAgents** (`TauricResearch/TradingAgents`) | Multi-agent topology, Phase 4 | E-03 + DEF-04 |
| 3 | **VectorBT** | Quant module dependency, Phase 6 | E-05 Deferred |
| 4 | **NautilusTrader** | Preferred serious validation engine | E-05/E-09, DEF-10/11 |
| 5 | **Agentic Trading Lab** (`Open-Finance-Lab/AgenticTrading`) | Optional experiment layer, Phase 6–7 | DEF-10 paper trading |
| 6 | **Local models / Ollama / FinGPT-style** | Optional local NLP | DEF-12 (generic) |
| 7 | **Shareholding / promoter-pledge sources** | §16.2 source | B-09 `SHAREHOLDING_CHANGE` capture kind exists; no source named |

## 4. In evidence only — all operations currently denied (7)

| # | Item | Evidence ref | Note |
|---:|---|---|---|
| 1 | **NSE** (announcements, results, XBRL) | A-05 `CHN-01` | All 12 operations `UNKNOWN (denied)`; ToU prohibits systematic/automated collection incl. scraping |
| 2 | **BSE** | A-05 `CHN-02` | All 12 operations denied; live terms unretrievable (SPA shell) |
| 3 | **Infosys investor-relations pages** | A-05 `SRC-01…08` | Live host 403 (Akamai); terms via 2026-06-06 archive snapshot only |
| 4 | **Issuer annual/quarterly results PDFs** | A-05 `SRC-*` | Same denial |
| 5 | **Earnings-call transcripts (text)** | A-05 `SRC-02/04/06` | Same denial |
| 6 | **SEBI circulars/regulations** | A-06 | Used as regulatory reference; never registered as a product source |
| 7 | **SEC EDGAR** | A-05 `CHN-03`, A-06 | NEW vs. blueprint; explicitly allows automated fair access (10 req/s, declared UA); D-5 asks whether it enters scope |

## 5. Never decided — named in the original blueprint, absent from all current authority docs (52)

### 5.1 Agent / research repositories and frameworks (26)

| # | Item | Blueprint verdict (line ref) |
|---:|---|---|
| 1 | **Dexter** (`virattt/dexter`) | Best orchestration reference; optional fast-prototype fork, Phase 1 (L888, L1026). Function replaced by S14 fixed state machine + DEF-03; the name itself never decided |
| 2 | **FinanceGym** (point-in-time benchmark) | Evaluation reference (L1723) |
| 3 | **Anthropic financial-services skills repo** | "Use as workflow library", Phase 0–1 — the earliest-phase recommendation (L891, L1150). Most under-noticed drop |
| 4 | **Agent Rita** | Optional, only if OpenBB Workspace adopted (L893) |
| 5 | **OpenBB AI SDK / `openbb-ai` / PydanticAI bridges** | Borrow streaming/artifact patterns (L2815) |
| 6 | **AI Hedge Fund** | Reference, later (L896, L1326) |
| 7 | **Qlib** | Optional systematic-research track (L900) |
| 8 | **RD-Agent** | Optional systematic-research track (L900) |
| 9 | **FinGPT** | Optional local NLP component (L901); nearest cover DEF-12 |
| 10 | **FinRL / FinRL-Meta** | Usually defer (L902) |
| 11 | **FinWorld** | Defer (L903) |
| 12 | **FINCON / FAgent** | Reference concepts only (L904) |
| 13 | **FinMem** | Reference concepts only (L905) |
| 14 | **StockAgent** | Not core (L906) |
| 15 | **Backtrader** | Not preferred (L907) |
| 16 | **Zipline / Zipline-Reloaded** | Compatibility only (L2826) |
| 17 | **QuantConnect / Lean** | Optional managed quant engine (L2554–2560) |
| 18 | **Value-Investing-Agent** | Skill/MCP reference (L1670–1676) |
| 19 | **`cc-equity-research` / Claude skill bundles** | Methodology reference (L1678–1684) |
| 20 | **`nse-stock-research-system` / India niche repos** | Adapter/prompt reference, Phase 1 (L908, L1648–1668) |
| 21 | **Market-Rover** | Verify repo before use (L1694–1696) |
| 22 | **FinAgent orchestration** | Reference (L2816) |
| 23 | **LangGraph** (via TradingAgents) | Implicit state-graph reference (L1241) |
| 24 | **Danelfin / Tickeron / Prospero** | "Do not treat scores as evidence" (L2830) — the prohibition itself is unrecorded |
| 25 | **MCP (Model Context Protocol)** as access surface | GBrain/OpenBB/Value-Investing access (L456, L1180) |
| 26 | **CrewAI / Streamlit / Gemini-style regional stacks** | Reference only (L1650) |

### 5.2 Managed / commercial research services (10)

| # | Item | Blueprint verdict |
|---:|---|---|
| 27 | **Fiscal.ai** | Verification/temporary provider (L2498–2516) |
| 28 | **Perplexity Finance** | Discovery, not system of record (L2518–2524) |
| 29 | **Screener.in** | Licensed source/validation layer (L2526–2544) |
| 30 | **Tijori** | Licensed source/validation layer (L2526–2544) |
| 31 | **Trendlyne** | Licensed source/validation layer (L2526–2544) |
| 32 | **Fintool** | Enterprise benchmark/provider (L2562–2568) |
| 33 | **AlphaSense** | Benchmark; expensive (L2562) |
| 34 | **Hebbia** | Benchmark; expensive (L2562) |
| 35 | **Broker APIs** (unnamed vendor) | Read-only market-data adapter first (L2546–2552); B-09 `PRICE` capture has no source today |
| 36 | **yfinance** | Named as insufficient for India (L1047); correctly irrelevant |

### 5.3 Infrastructure, storage, libraries (11)

| # | Item | Blueprint verdict / note |
|---:|---|---|
| 37 | **pgvector** | GBrain scale path (L281, L2648); dependent on GBrain, itself deferred |
| 38 | **PGLite** | GBrain local pilot (L272, L2648) |
| 39 | **Parquet** | Time-series/analytical files (L270, L2646). CONFLICT: absent from binding docs but asserted in `.claude/project/brief.md:44` |
| 40 | **DuckDB** | Query engine over Parquet (L270, L2646) |
| 41 | **S3-compatible object storage** | Raw documents at scale (L271, L2647); capability required (S09/S10), choice explicitly TBD |
| 42 | **FastAPI** | API layer (L2643) |
| 43 | **TypeScript / Bun** | Only if Dexter fork chosen (L1006, L2642); moot if Dexter stays dropped |
| 44 | **NumPy / Numba** | Via VectorBT (L1506) |
| 45 | **Rust** | Nautilus core (L1526) |
| 46 | **Docker (for the product)** | Vibe-Trading local benchmark (L1204); currently exists only as an *agent* permission in the goal contract |
| 47 | **OS keychain / secret manager** | Shared deployments (L2450); capability required, choice TBD |

Related but tracked as CONFLICTED / DE-FACTO rather than never-decided:
**Pydantic** (mandated by `.claude/rules/python/coding-style.md` and `brief.md`, but `architecture-brief-v2.md` §13 says no such binding is an architecture fact) and **Python** (used by governance validators; not an architecture fact).

### 5.4 Data sources (5)

| # | Item | Blueprint verdict |
|---:|---|---|
| 48 | **MCA / company registry** | Tier 1 where licensed (L2126) |
| 49 | **Credit-rating reports** | §16.2 source, §8.11 monitor (L2127, L2869) |
| 50 | **Shareholding / promoter-pledge disclosure sources** | §16.2 source (L2128); capture kind exists, no source named (also listed in §3) |
| 51 | **News & web search services** | First-class box `NW` in the blueprint architecture diagram (L199, L2132). SILENTLY DROPPED — no component, no source, no register row |
| 52 | **FinanceGym-style point-in-time data controls** | Evaluation-integrity reference (L1723) |

## 6. User-added candidate repositories — 2026-08-20 (14)

Supplied by the product owner as candidates to track. Six additional supplied
repos were duplicates of existing entries and are merged in place above:
`virattt/dexter` (§5.1 #1), `TauricResearch/TradingAgents` (§3 #2),
`AI4Finance-Foundation/FinRobot` (§3 #1), `Open-Finance-Lab/AgenticTrading`
(§3 #5), `OpenBB-finance/OpenBB` (§2 #2), `HKUDS/Vibe-Trading` (§2 #4).

All entries below are **CANDIDATE-UNDECIDED**. Descriptions marked *(unverified)*
are inferred from the repository name and general knowledge; the repos have not
been fetched or audited. **Rows marked ⛔ wrap or scrape NSE, BSE, Screener.in,
or Tijori endpoints — using them is a rights-denied operation under the current
A-05 fail-closed dispositions, regardless of the library's license.**

| # | Repository | What it is | Rights note |
|---:|---|---|---|
| 1 | `Fincept-Corporation/FinceptTerminal` | Open-source financial analysis terminal (Bloomberg-terminal-style app) *(unverified)* | Own data-source mix unknown; audit before any use |
| 2 | `stefan-jansen/machine-learning-for-trading` | Companion code for the ML4T book; educational reference, not a data source | No source access of its own |
| 3 | `aeron7/nsepython` | Python wrapper around NSE website/API endpoints | ⛔ NSE scraping-prohibited endpoints |
| 4 | `BennyThadikaran/NseIndiaApi` | Unofficial Python API for the NSE website | ⛔ NSE |
| 5 | `BennyThadikaran/BseIndiaApi` | Unofficial Python API for the BSE website | ⛔ BSE (terms currently unretrievable → denied) |
| 6 | `RuchiTanmay/nselib` | Python library for NSE market/derivatives data | ⛔ NSE |
| 7 | `LaZZy0v0/tijori-finance-mcp` | MCP server exposing Tijori Finance data *(unverified)* | ⛔ Tijori — aggregator with its own ToS; no rights decision exists |
| 8 | `jugaad-py/jugaad-data` | Python library for NSE (and RBI) live/historical data download | ⛔ NSE |
| 9 | `VishwaGauravIn/screener-scraper-pro` | Scraper for Screener.in *(unverified)* | ⛔ Screener.in — aggregator ToS unreviewed |
| 10 | `Na1neeth/openscreener` | Open-source stock screener, presumably India-focused *(unverified)* | Source mix unknown; audit before any use |
| 11 | `MrChartist/fii-dii-data` | FII/DII flow data collection *(unverified)* | ⛔ likely NSE/exchange endpoints |
| 12 | `Tapetide-hq/nse-bse-indian-stock-market-data-mcp` | MCP server exposing NSE/BSE market data *(unverified)* | ⛔ NSE/BSE |
| 13 | `NSEDownload/NSEDownload` | Python package for downloading NSE stock data | ⛔ NSE |
| 14 | `thisisamu/fii-dii-analysis` | FII/DII data analysis *(unverified)* | ⛔ likely NSE/exchange endpoints |

## 7. Triage state

No item in §5 or §6 has a recorded decision. The original blueprint's Phase 0
deliverable was "a decision log recording license and provider constraints"
(L1733); this inventory is the raw material for that log, not the log itself.
Next step (pending product-owner go-ahead): a bulk-defer register entry that
converts every §5/§6 row from silent to deliberately-deferred, with individual
activation gates for anything later wanted.
