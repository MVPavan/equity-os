# D7 Task 4 coverage-initiation amendment review

VERDICT: APPROVE

Reviewer: gpt-6.1-sol  
Review date: 2026-10-17  
Subject: `docs/blueprint/amendments/2026-10-17-coverage-initiation.md:7–12`, the associated glossary entry, and the `ledger_stage4` governance-test entry.  
Subject SHA-256: `df3161a1f50bcb3fcafd36bc5fd78a22ae47239e6b96bffcbae1d1c6b1291f51`

## Item approvals

| Amendment id | Verdict | Reviewer | Date | Subject SHA-256 |
|---|---|---|---|---|
| `initiation-clarified` | APPROVE | gpt-6.1-sol | 2026-10-17 | `df3161a1f50bcb3fcafd36bc5fd78a22ae47239e6b96bffcbae1d1c6b1291f51` |

## Authority and exact scope

- **Verbatim quotations:** record lines 25–27 reproduce the register’s heading and first bullet at `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md:173–175`. Record lines 31–36 reproduce amendment 1 at `docs/specs/2026-10-12-report-ledger-memory-and-data-lifecycle.md:102–107`, including its line wrapping.
- **Exact scope:** record lines 3 and 7–12 contain one amendment, `initiation-clarified`, scoped to `coverage-initiation` and `G:first-bullet`. It clarifies the deferral without lifting it. Stage 4 attribution at record line 17 matches the ledger spec’s allocation at lines 99–100 and 135.
- **Permitted and deferred behavior:** record lines 38–51 faithfully preserve owner-chosen coverage, assisted initiation, a bootstrap first report, panel approval and owner override. System-chosen coverage, unapproved initiation and full-universe daily research remain deferred. No other amendment or §G item is changed.
- **Implementation consistency:** `migrations/0026_watchlist.sql:46–79` enforces owner-only decisions, a nonempty ruling, legal ADD/REMOVE transitions and a coverage digest from a completed batch. Lines 8–14 bind that digest to an admitted result and its onboarding record and run. Lines 85–112 gate runtime versions and content on current watchlist membership and require an existing bootstrap version before drafting a non-bootstrap version.
- **Q4 ruling:** the SQL checks bootstrap-version existence, without requiring bootstrap approval. This matches `docs/workstreams/data-foundation/plans/D7.md:82–89`. The record requires initiation approval without introducing an approval prerequisite for later drafting.
- **Plan and glossary:** the changes satisfy Task 4 at `docs/workstreams/data-foundation/plans/D7.md:244–257` and introduce no member selection contrary to R8 at lines 95–98. `CONTEXT.md:72–74` accurately distinguishes owner-chosen report coverage from universe membership, capture and the comparison configuration. The entry contains no model names.
- **Test entry:** `tests/fundamentals/test_amendment_records.py:37–42` names the correct file, scope, spec and singleton amendment ID.

## Independent digest and link checks

- Independently parsed the YAML `amendments` list and computed SHA-256 over UTF-8 `json.dumps(items, sort_keys=True, separators=(",",":"))`. The result matches `subject_sha256` at record line 6 exactly.
- Both front-matter authority paths at record lines 4–5 resolve. Both Markdown links at lines 20–21 resolve, including the spec heading fragment.
- The changed Python file compiled successfully in memory without writing bytecode.
- Direct execution of `test_amendment_records` for `ledger_stage4`, without pytest collection, reached and failed the expected `status == "approved"` assertion at `tests/fundamentals/test_amendment_records.py:73`. Record lines 2 and 17–18 truthfully remain pending. Approval-metadata assertions after that point were not executed.
- Scoped `git diff --check` passed. Final scoped status showed the two modified tracked files and the untracked amendment record; the review file is awaiting integration.

## Severity-ranked issues

- P1: none.
- P2: none.
- P3: none.

## Acceptance limits

This approves the exact governance amendment above. It does not establish D7 implementation acceptance, Stage 4 acceptance or runtime database verification.

No files, Git state, databases or Beads state were changed. Prohibited files and directories were not accessed; no recursive search over tests or data was performed. PostgreSQL tests and the full suite were not run.

After saving this report, the orchestrator must record the per-item approval metadata, mark the amendment approved, update its pending narrative, and run:

```bash
uv run pytest tests/fundamentals/test_amendment_records.py -k ledger_stage4
```

Substantive changes to the structured amendment require a new digest and fresh review.

VERDICT: APPROVE
