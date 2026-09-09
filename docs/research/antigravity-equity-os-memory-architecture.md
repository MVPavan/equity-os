# Multi-Modal Memory & Storage Architecture for Fundamental Equity Research

**Author:** Antigravity  
**Date:** 2026-09-08  
**Status:** Architecture Recommendation / Research Report  
**Target Systems:** Equity-OS (Indian Equities Phase 0.5–1, Global Multi-Market Phase 2)  
**References:**  
- `CONTEXT.md`
- `docs/blueprint/funda-blueprint-final-consolidated-review.md`
- `docs/blueprint/org/funda-agentic-stock-research-blueprint.md`
- `docs/specs/equity-os-s19-memory-store-promotion.md`
- `docs/specs/equity-os-s20-memory-benchmark-gbrain.md`
- `docs/specs/2026-08-25-tijori-stack-ai-analyst-requirements.md`
- `src/fundamentals/store/fact_store.py`
- `src/fundamentals/store/snapshot_store.py`
- `src/fundamentals/contracts/entity_identity.py`
- `src/fundamentals/contracts/fact.py`
- `src/fundamentals/contracts/news.py`
- `src/fundamentals/contracts/guidance_claim.py`
- `src/fundamentals/news/events.py`
- `src/fundamentals/thesis/contracts.py`

---

## 1. Executive Summary: The Architectural Dilemma

A state-of-the-art fundamental equity research system (Equity-OS) must store and retrieve seven distinct modalities of data across thousands of listed companies:
1. **Financial Numbers & Metrics:** Multi-quarter/multi-year financial statements, ratios, and restatements sourced from Screener.in, Tijori Finance, Upstox APIs, and official XBRL exchange filings.
2. **Primary Corporate Documents:** Raw PDF annual reports, investor presentations, earnings concall audio and transcripts, regulatory announcements.
3. **Corporate News & Regulatory Intimations:** BSE/NSE corporate announcements, press releases, financial media coverage.
4. **Supply Chain & Technological Bottlenecks:** Vendor/customer dependency trees, raw material cost drivers, and global technology choke points (e.g., semiconductor foundry packaging, EUV lithography, specialty chemical import dependencies).
5. **Investor Tracking & Capital Flows:** FII/DII shareholding distributions, quarterly institutional shifts, daily bulk/block deals, insider trading (SEBI PIT), and promoter pledge ratios.
6. **Investment Theses & Hypotheses:** Variant perceptions, bull/bear cases, active hypotheses, and observable falsifier conditions.
7. **Management Guidance & Track Record:** Forward-looking commentary, revenue/margin guidance bands, and longitudinal verification ledgers.

### Can One System Achieve It?

#### At the Query Engine Level: YES
A single multi-model database engine—specifically **PostgreSQL** with the **`pgvector`** extension (or **SQLite** in local development/MVP)—can natively store and query all relational tables, JSON observation anchors, bitemporal restatement chains, graph relationships (via recursive CTEs), dense vector embeddings, and full-text search indexes. There is **no operational need** to deploy five separate database engines (PostgreSQL + Neo4j + Pinecone + Elasticsearch + MongoDB).

#### At the Physical Storage Level: NO
No single database engine should store raw 50MB PDF annual reports, concall audio recordings, or multi-megabyte scraped HTML dumps directly inside database table columns (`BYTEA` or `BLOB`). Doing so causes buffer cache thrashing, massive index bloat, slow replication, and unwieldy database backups.

### The Recommended Architecture: The Pragmatic Dual-Engine Core
Equity-OS presents a **single unified data access interface** in Python backed by two complementary physical layers:
1. **Content-Addressed Blob Lake (Filesystem / S3 / MinIO):** Stores immutable raw files and vendor payloads addressed by their SHA-256 cryptographic digest (already implemented in `src/fundamentals/store/snapshot_store.py`).
2. **Multi-Model Relational Core (PostgreSQL + pgvector / SQLite for MVP):** Stores structured bitemporal facts, entity resolution mappings, investor flows, supply chain graph edges, and document chunk embeddings.
3. **Versioned Narrative Brain (Git-backed Markdown with SQL Dual-Registration):** Stores human-curated company notes, theses, and management credibility profiles, promoted strictly via analyst validation gates (as specified in `docs/specs/equity-os-s19-memory-store-promotion.md`).

---

## 2. Technical Evaluation of GBrain

GBrain (`garrytan/gbrain`) is an open-source, local-first personal memory engine created by Garry Tan. Because it implements people- and company-level segregation, it provides valuable design patterns as well as notable limitations for fundamental equity research.

### How GBrain Operates
- **Markdown Notes as Ground Truth:** Notes are stored on disk as `.md` files with YAML frontmatter.
- **Embedded Database:** PGLite (PostgreSQL compiled to WASM) running `pgvector`.
- **Directory-Level Entity Segregation:** 
  - Notes in `people/<slug>.md` adhere to the `person` schema.
  - Notes in `companies/<slug>.md` adhere to the `company` schema.
  - Internal links such as `[[companies/infosys]]` inside `people/salil-parekh.md` automatically register bidirectional graph edges in the embedded database.
- **Hybrid Search:** Combines BM25 lexical search (`tsvector`) and vector search (`pgvector`) using Reciprocal Rank Fusion (RRF).

### Architectural Strengths to Adopt
1. **Human-Readable Dossiers:** Storing synthesized company theses and executive background profiles in Markdown allows human equity analysts to review, audit, diff, and edit research using standard tools (Git, Obsidian, VS Code).
2. **Wikilink Auto-Wiring:** Bi-directional relationships between management profiles, companies, competitors, and institutional funds can be expressed intuitively using `[[entity/slug]]` syntax.

### Fatal Limitations if Used as the Sole Engine
1. **Quantitative Storage Collapse:** Indian equities alone (4,000+ companies × 80 quarters × 100 metrics) generate tens of millions of quantitative data points. Markdown tables cannot maintain fixed-point decimal precision (`Decimal(28, 6)`), support B-tree indexing, or execute cross-sectional financial screens (`SELECT symbol WHERE roe > 20% AND pe < 15`).
2. **No Bitemporal Awareness (Look-Ahead Bias Risk):** Fundamental research and quantitative backtesting require strict distinction between **valid time** (the fiscal quarter represented) and **knowledge time** (when the financial statement or restatement became public). GBrain lacks bitemporal point-in-time boundaries.
3. **Memory Poisoning Vulnerability:** If an autonomous agent writes an unverified inference into a persistent Markdown note, subsequent agent runs retrieve that note as established truth, amplifying ungrounded claims into permanent thesis distortion.

### Governance Status in Equity-OS
Under project specifications `docs/specs/equity-os-s19-memory-store-promotion.md` and `docs/specs/equity-os-s20-memory-benchmark-gbrain.md`, GBrain is an unactivated benchmark candidate (Deferred items D-02, D-04, and D-05 in the decision register). Equity-OS implements the **ergonomic patterns of GBrain** through an engine-neutral `MemoryStore` interface, while enforcing strict promotion gates on all persistent writes.

---

## 3. Detailed Storage Schemas for the 7 Modalities

```
+----------------------------------------------------------------------------------------------------+
|                                   EQUITY-OS UNIFIED DATA INTERFACE                                 |
|               (FactStore | SnapshotStore | EntityMap | NewsEvents | MemoryStore | Graph)                |
+----------------------------------------------------------------------------------------------------+
                                                   |
         +-----------------------------------------+----------------------------------------+
         |                                         |                                        |
         v                                         v                                        v
+------------------------------+  +-----------------------------------+  +----------------------------------+
|    LAYER 1: BLOB LAKE        |  |    LAYER 2: MULTI-MODEL CORE      |  |     LAYER 3: NARRATIVE BRAIN     |
| (SnapshotStore: Local / S3)  |  |    (PostgreSQL + pgvector /       |  |  (Git Markdown + SQL Dual-Reg)   |
|                              |  |     SQLite WAL for MVP)           |  |                                  |
+------------------------------+  +-----------------------------------+  +----------------------------------+
| - Immutable raw source files |  | - Bitemporal financial facts      |  | - Human-curated company notes    |
| - PDFs (Annual Reports)      |  | - Point-in-time restatements      |  | - Active investment theses       |
| - Concall audio & HTML dumps |  | - Entity cross-source mapping     |  | - Management credibility ledger  |
| - Vendor JSON API payloads   |  | - FII/DII flows & bulk deals      |  | - Variant perceptions            |
| - Content-addressed (SHA256) |  | - Supply chain & bottleneck graph |  | - Observable falsifiers          |
| - Atomic staging & links     |  | - Vector chunks for dense search  |  | - Human promotion gate           |
+------------------------------+  +-----------------------------------+  +----------------------------------+
```

### Modality 1: Structured Financial Numbers & Bitemporal Restatements
- **Engine:** PostgreSQL / SQLite relational tables.
- **Reference Code:** `src/fundamentals/store/fact_store.py`
- **Core Principle:** Facts are immutable records. Restatements generate a new `revision_ordinal` under the same `revision_family`. Unanchored API endpoints (e.g. Tijori API endpoints lacking self-identity) are barred from the canonical revision chain until reconciled with primary filings.

```sql
CREATE TABLE facts (
    row_id BIGSERIAL PRIMARY KEY,
    content_identity VARCHAR(64) NOT NULL,            -- SHA-256 of concept, period, scope, dimensions, currency, scale, entity
    value_hash VARCHAR(64) NOT NULL,                  -- SHA-256 of raw/normalized values, decimals, source_id, file_sha256, anchor
    revision_family VARCHAR(64) NOT NULL,             -- Stable identifier across restatements
    revision_ordinal INTEGER NOT NULL,                -- Increments on restatement (1, 2, 3...)
    canonical_status VARCHAR(16) NOT NULL,            -- 'CANDIDATE', 'CANONICAL', 'SUPERSEDED'
    canonical_selected_at TIMESTAMP WITH TIME ZONE,
    canonical_reason TEXT,
    
    source_id VARCHAR(64) NOT NULL,                   -- 'bse', 'nse', 'screener', 'tijori'
    file_sha256 VARCHAR(64) NOT NULL,                 -- Hash of the raw held source blob
    anchor JSONB NOT NULL,                            -- Exact table/cell coordinate or XBRL context
    
    valid_time_start DATE NOT NULL,                   -- Period start / instant
    valid_time_end DATE,                              -- Period end (null for instant)
    knowledge_time TIMESTAMP WITH TIME ZONE NOT NULL, -- Point in time when fact became public
    first_seen_time TIMESTAMP WITH TIME ZONE NOT NULL,
    
    fact_json JSONB NOT NULL,                         -- Normalized Pydantic Fact model
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX ux_facts_identity_value ON facts (content_identity, value_hash);
CREATE INDEX ix_facts_pit_lookup ON facts (content_identity, canonical_status, knowledge_time);
```

---

### Modality 2: Primary Documents & Content-Addressed Snapshots
- **Engine:** Filesystem / Object Storage (MinIO / AWS S3).
- **Reference Code:** `src/fundamentals/store/snapshot_store.py`
- **Directory Layout:**
  ```text
  data/snapshots/
    blobs/
      <source_id>/
        <sha256[:2]>/
          <sha256>                        # Immutable raw bytes
    <source_id>/
      <surface>/
        <request_key>/
          <capture_id>/
            record.json                   # Headers, timestamp, source URL, payload hash
            body.pdf                      # Hardlinked directly to blobs/ via os.link
    .staging/                             # Atomic staging directory
  ```
- **Integrity Guarantee:** Reads recalculate SHA-256 against `record.json` and fail closed on checksum mismatches.

---

### Modality 3: Supply Chain, Vendor Exposure & Global Technology Bottlenecks
- **Engine:** Property Graph implemented directly in PostgreSQL via Relational Tables + Recursive Common Table Expressions (CTEs).
- **Rationale:** A 4,000-company market with 5–25 disclosures per company creates 100,000–500,000 graph edges. In PostgreSQL, B-tree indexed 4-hop traversals execute in under 10ms, eliminating the operational complexity of Neo4j.

```sql
CREATE TABLE graph_nodes (
    node_id VARCHAR(64) PRIMARY KEY,                  -- 'COMP:IN:INFY', 'COMM:SODA_ASH', 'TECH:COWOS'
    node_type VARCHAR(32) NOT NULL,                   -- 'COMPANY', 'COMMODITY', 'TECHNOLOGY', 'GEOGRAPHY'
    name VARCHAR(255) NOT NULL,
    country_iso VARCHAR(2),
    attributes JSONB
);

CREATE TABLE graph_edges (
    edge_id BIGSERIAL PRIMARY KEY,
    source_node_id VARCHAR(64) REFERENCES graph_nodes(node_id),
    target_node_id VARCHAR(64) REFERENCES graph_nodes(node_id),
    relationship VARCHAR(32) NOT NULL,                -- 'SUPPLIES_TO', 'CUSTOMER_OF', 'DEPENDS_ON', 'CHOKEPOINT_FOR'
    weight_percentage NUMERIC(5, 2),                  -- Revenue or COGS exposure percentage
    criticality VARCHAR(16) DEFAULT 'HIGH',           -- 'CRITICAL', 'HIGH', 'SUBSTITUTABLE'
    substitute_lead_time_months INT,                  -- Switching lead time
    valid_from DATE NOT NULL,
    valid_to DATE,
    source_file_sha256 VARCHAR(64) NOT NULL,
    CONSTRAINT ux_graph_edges UNIQUE (source_node_id, target_node_id, relationship, valid_from)
);

CREATE INDEX ix_graph_edges_traversal ON graph_edges (source_node_id, relationship);
```

---

### Modality 4: Investor Details & Institutional Capital Flows
- **Engine:** PostgreSQL / SQLite Relational Tables.
- **Coverage:** Quarterly shareholding disclosures, daily BSE/NSE bulk and block deals, SEBI Prohibition of Insider Trading (PIT) disclosures, and promoter share pledges.

```sql
-- Quarterly institutional & promoter holdings
CREATE TABLE shareholding_snapshots (
    snapshot_id BIGSERIAL PRIMARY KEY,
    entity_id VARCHAR(64) NOT NULL,
    period_end DATE NOT NULL,                         -- Quarter end (e.g., 2024-03-31)
    filing_date DATE NOT NULL,                        -- Knowledge time
    category VARCHAR(32) NOT NULL,                    -- 'PROMOTER', 'FII_FPI', 'DII_MF', 'DII_INSURANCE', 'RETAIL'
    holding_percentage NUMERIC(6, 3) NOT NULL,
    shares_count BIGINT NOT NULL,
    pledged_percentage NUMERIC(6, 3) DEFAULT 0,       -- Governance risk indicator
    source_file_sha256 VARCHAR(64) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ux_shareholding UNIQUE (entity_id, period_end, category)
);

-- Daily market trades (Bulk deals, Block deals, Insider trading)
CREATE TABLE market_disclosures (
    disclosure_id BIGSERIAL PRIMARY KEY,
    entity_id VARCHAR(64) NOT NULL,
    disclosure_date DATE NOT NULL,
    disclosure_type VARCHAR(24) NOT NULL,             -- 'BULK_DEAL', 'BLOCK_DEAL', 'PIT_INSIDER_TRADE'
    client_or_promoter_name VARCHAR(255) NOT NULL,
    transaction_type VARCHAR(4) NOT NULL,             -- 'BUY' or 'SELL'
    quantity BIGINT NOT NULL,
    price NUMERIC(14, 2) NOT NULL,
    exchange VARCHAR(8) NOT NULL,                     -- 'NSE', 'BSE'
    source_file_sha256 VARCHAR(64) NOT NULL
);
```

---

### Modality 5: Corporate News & Regulatory Intimations
- **Engine:** Clustered Event Store with Vector Embeddings.
- **Reference Code:** `src/fundamentals/contracts/news.py` and `src/fundamentals/news/events.py`
- **Processing Logic:** Raw news observations are collected across first-party exchange filings and third-party media. A deterministic clustering engine (`_DEDUPE_WINDOW = 3 days`, `_TITLE_SIMILARITY_THRESHOLD = 0.86`) aggregates observations into unified events, giving priority to first-party filings over media rumors.

```sql
CREATE TABLE news_observations (
    observation_id VARCHAR(64) PRIMARY KEY,           -- Deterministic SHA-256
    issuer_id VARCHAR(64),                            -- Normalized entity ID
    symbol VARCHAR(32),
    resolved BOOLEAN NOT NULL,
    source_family VARCHAR(16) NOT NULL,               -- 'FIRST_PARTY', 'REGULATORY', 'MEDIA'
    source_id VARCHAR(64) NOT NULL,                   -- 'bse_news', 'nse_news', 'et_news'
    source_url TEXT NOT NULL,
    published_at TIMESTAMP WITH TIME ZONE NOT NULL,
    raw_title TEXT NOT NULL,
    raw_category VARCHAR(64) NOT NULL,
    payload_sha256 VARCHAR(64) NOT NULL
);

CREATE TABLE news_events (
    event_id VARCHAR(64) PRIMARY KEY,                 -- SHA-256 of primary occurrence
    event_type VARCHAR(32) NOT NULL,                  -- 'RESULTS', 'BOARD_MEETING', 'CORP_ACTION', 'MATERIAL_EVENT'
    symbol VARCHAR(32) NOT NULL,
    title TEXT NOT NULL,
    published_at TIMESTAMP WITH TIME ZONE NOT NULL,
    observation_ids JSONB NOT NULL,                   -- Clustered observation IDs
    confirmed BOOLEAN NOT NULL,                       -- True if verified by FIRST_PARTY filing
    embedding vector(1536)                            -- Dense vector for semantic search
);
```

---

### Modality 6: Investment Theses, Variant Perceptions & Falsifiers
- **Engine:** Git-Versioned Markdown Files bound to SQL via `CanonicalMemoryPointer`.
- **Reference Code:** `src/fundamentals/thesis/contracts.py` and `docs/specs/equity-os-s19-memory-store-promotion.md`
- **File Structure:**
  ```markdown
  ---
  type: thesis
  thesis_id: THESIS-IN-INFY-MARGIN-FY26
  company_id: IN-COMP-000128
  symbol: INFY
  horizon: 2-3-years
  as_of: 2026-08-15
  status: active
  confidence: medium
  ---

  # Thesis: Margin Expansion via Project Maximus & Automation

  ## Current Thesis Summary
  Infosys will expand operating margins from 21.1% to 22.5% by FY26 through pyramid rationalization and automation.

  ## Key Assumptions & Observable Falsifiers
  | Metric / Hypothesis | Target / Range | Falsifier Condition (Thesis Broken If) | Current Status |
  |---|---|---|---|
  | Operating Margin | 21.5% - 22.5% | Drops below 20.5% for two consecutive quarters | ON_TRACK (21.1%) |
  | Subcontractor Costs | < 7.0% of revenue | Remains above 8.5% of revenue | ON_TRACK (7.2%) |
  | Large Deal TCV | > $3.0B / quarter | Net new TCV drops below $1.5B | ON_TRACK ($3.4B) |
  ```

---

### Modality 7: Management Guidance & Credibility Ledger
- **Engine:** Relational Tracking Ledger with Longitudinal Outcome States.
- **Reference Code:** `src/fundamentals/contracts/guidance_claim.py`
- **Verification Cycle:** Concall quotes and targets are extracted as claims. Following quarter/year financial results, claims are evaluated deterministically as `MET`, `MISSED`, or `DELAYED`.

```sql
CREATE TABLE management_guidance_claims (
    claim_id BIGSERIAL PRIMARY KEY,
    entity_id VARCHAR(64) NOT NULL,
    source_file_sha256 VARCHAR(64) NOT NULL,
    source_quote TEXT NOT NULL,                       -- Verbatim transcript quote
    metric VARCHAR(64) NOT NULL,                      -- e.g. 'Constant Currency Revenue Growth'
    lower_bound NUMERIC(10, 4) NOT NULL,              -- e.g. 3.0000 (%)
    upper_bound NUMERIC(10, 4) NOT NULL,              -- e.g. 4.5000 (%)
    unit VARCHAR(16) NOT NULL,                        -- 'PERCENT', 'INR_CRORE'
    horizon VARCHAR(32) NOT NULL,                     -- 'FY26', 'FY25_Q4'
    scope VARCHAR(16) NOT NULL,                       -- 'consolidated', 'standalone'
    epistemic_class VARCHAR(16) NOT NULL DEFAULT 'forecast',
    status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',     -- 'ACTIVE', 'MET', 'MISSED', 'DELAYED'
    actual_realized_value NUMERIC(10, 4),
    evaluated_at TIMESTAMP WITH TIME ZONE
);
```

---

## 4. Cross-Modal Agent Retrieval Patterns

The following SQL queries show how AI agents access cross-modal intelligence using the unified schema:

### Pattern 1: Point-in-Time Financial Screening (Zero Look-Ahead Bias)
*Agent Query:* "Screen listed specialty chemical firms with 3-year revenue CAGR > 15% and Net Debt/EBITDA < 1.0, strictly as known on 2024-08-01."
```sql
SELECT f_rev.fact_json->>'normalized_value' AS revenue,
       f_debt.fact_json->>'normalized_value' AS net_debt
FROM facts f_rev
JOIN facts f_debt ON f_debt.fact_json->>'entity_id' = f_rev.fact_json->>'entity_id'
     AND f_debt.fact_json->>'concept_qname' = 'custom:NetDebt'
     AND f_debt.knowledge_time <= '2024-08-01 23:59:59+00'
     AND f_debt.canonical_status = 'canonical'
WHERE f_rev.fact_json->>'concept_qname' = 'in-gaap:RevenueFromOperations'
  AND f_rev.knowledge_time <= '2024-08-01 23:59:59+00'
  AND f_rev.canonical_status = 'canonical';
```

### Pattern 2: Supply Chain Choke Point Blast Radius
*Agent Query:* "If Taiwanese CoWoS packaging capacity encounters a supply freeze, identify all exposed companies across coverage and calculate the direct/indirect dependency depth."
```sql
WITH RECURSIVE bottleneck_path AS (
    SELECT target_node_id AS affected_node, source_node_id AS supplier_node, 
           relationship, weight_percentage, 1 AS depth
    FROM graph_edges
    WHERE source_node_id = 'TECH:COWOS_PACKAGING'
    
    UNION ALL
    
    SELECT ge.target_node_id, ge.source_node_id, 
           ge.relationship, ge.weight_percentage, bp.depth + 1
    FROM graph_edges ge
    JOIN bottleneck_path bp ON ge.source_node_id = bp.affected_node
    WHERE bp.depth < 5
)
SELECT gn.name AS exposed_company, bp.depth, bp.weight_percentage
FROM bottleneck_path bp
JOIN graph_nodes gn ON gn.node_id = bp.affected_node
WHERE gn.node_type = 'COMPANY'
ORDER BY bp.depth ASC, bp.weight_percentage DESC NULLS LAST;
```

### Pattern 3: Institutional Shift vs. Promoter Pledge Risk
*Agent Query:* "Find companies where FII holdings expanded by >1.5% in the most recent quarter, but promoter pledged shares exceed 15%."
```sql
WITH holdings AS (
    SELECT entity_id, category, holding_percentage, pledged_percentage, period_end,
           LAG(holding_percentage) OVER (PARTITION BY entity_id, category ORDER BY period_end) AS prev_fii_holding
    FROM shareholding_snapshots
    WHERE category IN ('FII_FPI', 'PROMOTER')
)
SELECT h_fii.entity_id, 
       (h_fii.holding_percentage - h_fii.prev_fii_holding) AS fii_increase,
       h_prom.pledged_percentage AS promoter_pledge
FROM holdings h_fii
JOIN holdings h_prom ON h_prom.entity_id = h_fii.entity_id 
     AND h_prom.period_end = h_fii.period_end
     AND h_prom.category = 'PROMOTER'
WHERE h_fii.category = 'FII_FPI'
  AND (h_fii.holding_percentage - h_fii.prev_fii_holding) > 1.5
  AND h_prom.pledged_percentage > 15.0;
```

---

## 5. Preventing Memory Poisoning: The Three-Zone Policy

The primary failure mode in autonomous multi-agent research is **memory poisoning**: an agent saves an unverified inference to memory; subsequent agent passes retrieve it as an established fact; confidence compounds until an erroneous conclusion is presented as definitive truth.

To prevent this, Equity-OS implements the **Three-Zone Promotion Architecture** (`docs/blueprint/org/funda-agentic-stock-research-blueprint.md`):

```
[ ZONE 1: INBOX / DRAFT ]
Agents generate extracted numbers, candidate notes, or thesis hypotheses.
Stored in scratch/staging tables. Completely invisible to production retrieval.
                          |
                          v
[ ZONE 2: DETERMINISTIC VERIFICATION ]
Automated validators check:
1. Exact Provenance: Every number must resolve to a valid FactStore content_identity.
2. Direct Quotes: Guidance claims must match verbatim transcript text.
3. Epistemic Labels: Every claim must be tagged (OBSERVED, COMPUTED, INFERRED, FORECAST).
                          |
                          v
[ ZONE 3: CANONICAL PROMOTION GATE ]
Human analyst reviews the staged diff and approves promotion.
The data is written to Git-backed Markdown and registered in SQL as CANONICAL.
```

---

## 6. Implementation & Migration Roadmap

| Milestone | Scope | Storage Engines | Key Capabilities |
|---|---|---|---|
| **Current Baseline (Phase 0.5)** | 1 Discovery Stock (Apar Industries / Titan) | Local Filesystem + SQLite WAL + Git Markdown | Single-stock ingestion, reconciliation, bitemporal facts, thesis drafting. |
| **Near-Term (Phase 1)** | Watchlist (50–100 Stocks) | Local Disk + SQLite (WAL) + DuckDB (for fast OLAP screening) + Git Markdown | Screener & Tijori multi-quarter parsing, news event clustering, guidance ledger, watchlist screening. |
| **Institutional Scale (Phase 2)** | Full Coverage (~4,000 Indian + Global Equities) | MinIO / AWS S3 Blob Lake + PostgreSQL (`pgvector`, GIN, partitioned) + Git Narrative Brain | Full market coverage, institutional FII/DII tracking, 5-hop recursive supply chain traversal, hybrid semantic/lexical RAG. |

---

## 7. Open Technical Decisions & Next Steps

1. **Reconciliation Ladder for Unanchored API Data:** Establish a deterministic promotion rule allowing high-confidence consensus across secondary sources (e.g. Screener and Tijori reporting identical values) to temporarily admit facts when primary XBRL filings are delayed.
2. **Promoter Group Web Resolution:** Model beneficial ownership graphs to link multi-vehicle family trusts and corporate investment entities to their parent Indian promoter families.
3. **Cross-Border Identifier Normalization:** Extend `IdentifierNamespace` in `src/fundamentals/contracts/entity_identity.py` beyond Indian identifiers (`ISIN`, `NSE_SYMBOL`, `BSE_SCRIP`, `SCREENER_SLUG`, `TIJORI_SLUG`) to support global standards: ISO 17442 Legal Entity Identifiers (LEI) and OpenFIGI.
