# Project: data-foundation

What this project is, what it is for, and how to tell that it is finished. The plan and progress
live in [`roadmap.md`](roadmap.md); the requirements live in the two specs below. Where this file
and a spec differ, the spec wins.

## What it is

The data foundation of Equity-OS. It replaces per-company SQLite facts and loose report files with
one shared PostgreSQL store that holds:

- **Evidence:** every captured filing and vendor page, its native line items (occurrences) and
  their versioned canonical interpretations, with exact source locations and honest timestamps
  (when a figure applies, and when the system could have known it).
- **A canonical field dictionary:** one versioned list of every figure the product reads, mapped
  once per source surface and schema version, never per company.
- **A comparator:** for every measurement it reports two separate checks:
  - the **extraction check** (exchange XBRL against the results PDF of the same filing);
  - **independent corroboration** (the filing against Screener and Tijori).

  Each pair gets a typed outcome, every untrusted outcome gets a review route, and no figure gets a
  blended score.
- **A report ledger and long-term memory:** report versions whose every number cites a stored
  figure or calculation trace; per-stock memory that is promoted only by a separate approval.
- **Generated views, coverage and retention:** read-only human views; a universe registry →
  screens → watchlist; a retention policy with replay after deletion.

Requirements:
- [Data spec](../../specs/2026-10-11-canonical-financial-data-and-cross-source-comparison.md), Stages 1–4.
- [Ledger spec](../../specs/2026-10-12-report-ledger-memory-and-data-lifecycle.md), Stages 1–5. It
  amends the data spec's retention and replay clauses.

## Goal

The owner can trust, trace and scale every number Equity-OS reports:

1. **Trust:** every figure is checked against a second representation of the same filing and,
   where a vendor exists, against an independent source. The owner can detect and explain gaps
   such as the ~4.5 crore Apar opex difference against Screener.
2. **Trace:** every reported number links to a stored fact or a stored calculation trace, down to
   the page, table cell or XBRL fact. A missing input fails closed and is never filled in.
3. **Scale:**
   - a new Indian listed company is added by identifier alone, with no hand-written configuration;
   - one shared store serves the full market (about 5,000 stocks in the registry and 50–200 on
     the watchlist).
4. **Remember and forget safely:** knowledge persists between quarters through approved memory.
   Expired originals are deleted under hash-checked, crash-safe rules, without losing anything that
   cannot be recreated.

Out of scope: the specs' Out of Scope tables. Main items:
- banks, NBFCs and insurers;
- foreign markets;
- prices;
- scheduled whole-market capture;
- vector search;
- multi-user access;
- off-machine backups.

## How to verify the project is complete

Completion is mechanical. It is never a model's opinion, and it has four parts.

**1. Every phase exit test passes.** The roadmap has ten phases, each ending in one end-to-end test
over real retained filings on the PostgreSQL test database:

| Phase | Exit test | What it proves |
|---|---|---|
| D1a | `tests/fundamentals/test_compare_tracer.py` | One company and quarter from both filings through the extraction check and report |
| D1b | `tests/fundamentals/test_data_stage1_e2e.py` | Vendors, corroboration and the review queue for Apar and ten companies, matching the frozen Stage 1 manifest |
| D2 | data Stage 2 e2e | The legacy fact store is migrated, consumers run on PostgreSQL, and cutover is recorded |
| D3 | ledger Stage 1 e2e and `test_ledger_export.py` | Report ledger; the export reproduces every imported Apar version's hash |
| D4 | ledger Stage 2 e2e | Memory retrieval returns promoted items with supports and provenance |
| D5 | ledger Stage 3 e2e | Generated views |
| D6 | data Stage 4 e2e | A held-out company onboards by identifier alone, with no code or configuration change |
| D7 | ledger Stage 4 e2e | A coverage batch captures and compares only the screened subset |
| D8 | data Stage 3 e2e | Shareholding aggregates are compared against each vendor |
| D9 | ledger Stage 5 e2e | Retention dry-run lists exactly the eligible blobs; purge then restore matches the manifest |

The exact test names for D2–D9 are fixed in each phase plan; the roadmap's Exit lines state what
each must show.

**2. The expected answers were fixed before the code ran.**
- Every phase from D1b on has a frozen manifest. It is checked by hand against named source
  documents, approved by the reviewer, and committed before its e2e test.
- `tests/fundamentals/test_frozen_manifests.py` enforces this, including the commit order, so the
  code under test never writes its own answer key.
- Spec amendments are checked by `tests/fundamentals/test_amendment_records.py`.

**3. The suite is clean.**
- `uv run pytest tests/fundamentals` passes with no unexplained failure.
- `uv run mypy --strict src` passes.
- `uv run ruff check src tests/fundamentals` and `uv run ruff format --check src tests/fundamentals`
  pass.
- Commands and opt-outs are listed in `.claude/project/verification.md`.

**4. Every phase is closed.**
- Every phase epic in bd (label `ws-data-foundation`) is closed with evidence.
- Each phase had its end-of-phase review approved by the reviewer
  (`.claude/rules/core/04-agent-stack.md`).

**Single check (to be built):** `scripts/verify_project.sh` should run parts 1–3 and report
per-phase PASS/FAIL. It does not exist yet; [`roadmap.md`](roadmap.md#project-completion) tracks it.
The project is complete when that check passes and all ten phase epics are closed.
