# D9 Task 1 governance amendments review

VERDICT: APPROVE

Reviewer: gpt-6.1-sol  
Review date: 2026-10-17

Subjects:

- `docs/blueprint/amendments/2026-10-12-retention-replay.md` — SHA-256: `e7028b7f60e24f5c47fdc29b5f7fa002defc98188ef190d75ecae8d62bca12d8`
- `docs/blueprint/amendments/2026-10-12-a05-derived-amounts.md` — SHA-256: `ab255a2a7c2cf3881b88b27759003035aaed7148fcadf9e0bc053799017d07a6`

Approval covers these exact structured subjects and the associated governance-test and glossary changes.

## Item approvals

| Amendment id | Verdict | Reviewer | Date | Subject SHA-256 |
|---|---|---|---|---|
| `c16-qualified` | APPROVE | gpt-6.1-sol | 2026-10-17 | `e7028b7f60e24f5c47fdc29b5f7fa002defc98188ef190d75ecae8d62bca12d8` |
| `c02-qualified` | APPROVE | gpt-6.1-sol | 2026-10-17 | `e7028b7f60e24f5c47fdc29b5f7fa002defc98188ef190d75ecae8d62bca12d8` |
| `data-spec-us12` | APPROVE | gpt-6.1-sol | 2026-10-17 | `e7028b7f60e24f5c47fdc29b5f7fa002defc98188ef190d75ecae8d62bca12d8` |
| `data-spec-4-capture-store` | APPROVE | gpt-6.1-sol | 2026-10-17 | `e7028b7f60e24f5c47fdc29b5f7fa002defc98188ef190d75ecae8d62bca12d8` |
| `data-spec-5-replay` | APPROVE | gpt-6.1-sol | 2026-10-17 | `e7028b7f60e24f5c47fdc29b5f7fa002defc98188ef190d75ecae8d62bca12d8` |
| `data-spec-6-integrity` | APPROVE | gpt-6.1-sol | 2026-10-17 | `e7028b7f60e24f5c47fdc29b5f7fa002defc98188ef190d75ecae8d62bca12d8` |
| `data-spec-6-backup` | APPROVE | gpt-6.1-sol | 2026-10-17 | `e7028b7f60e24f5c47fdc29b5f7fa002defc98188ef190d75ecae8d62bca12d8` |
| `data-spec-6-restore-test` | APPROVE | gpt-6.1-sol | 2026-10-17 | `e7028b7f60e24f5c47fdc29b5f7fa002defc98188ef190d75ecae8d62bca12d8` |
| `data-spec-7-shareholding` | APPROVE | gpt-6.1-sol | 2026-10-17 | `e7028b7f60e24f5c47fdc29b5f7fa002defc98188ef190d75ecae8d62bca12d8` |
| `data-spec-8-discovery` | APPROVE | gpt-6.1-sol | 2026-10-17 | `e7028b7f60e24f5c47fdc29b5f7fa002defc98188ef190d75ecae8d62bca12d8` |
| `data-spec-stage2-restore` | APPROVE | gpt-6.1-sol | 2026-10-17 | `e7028b7f60e24f5c47fdc29b5f7fa002defc98188ef190d75ecae8d62bca12d8` |
| `data-spec-0-cross-spec` | APPROVE | gpt-6.1-sol | 2026-10-17 | `e7028b7f60e24f5c47fdc29b5f7fa002defc98188ef190d75ecae8d62bca12d8` |
| `data-spec-5-queue-panel` | APPROVE | gpt-6.1-sol | 2026-10-17 | `e7028b7f60e24f5c47fdc29b5f7fa002defc98188ef190d75ecae8d62bca12d8` |
| `data-spec-2-qualification` | APPROVE | gpt-6.1-sol | 2026-10-17 | `e7028b7f60e24f5c47fdc29b5f7fa002defc98188ef190d75ecae8d62bca12d8` |
| `ledger-5-high-incident` | APPROVE | gpt-6.1-sol | 2026-10-17 | `e7028b7f60e24f5c47fdc29b5f7fa002defc98188ef190d75ecae8d62bca12d8` |
| `derived-amounts-kept` | APPROVE | gpt-6.1-sol | 2026-10-17 | `ab255a2a7c2cf3881b88b27759003035aaed7148fcadf9e0bc053799017d07a6` |
| `redaction-inventory` | APPROVE | gpt-6.1-sol | 2026-10-17 | `ab255a2a7c2cf3881b88b27759003035aaed7148fcadf9e0bc053799017d07a6` |

## Scope, quotations and authority

- The 15 retention/replay ids and two A-05 ids match D9 Task 1 exactly (`docs/workstreams/data-foundation/plans/D9.md:396`). No additional amendment ids are introduced.
- Independently parsed each YAML amendment list and computed SHA-256 over UTF-8 `json.dumps(items, sort_keys=True, separators=(",",":"))`. Both results match their headers. The A-05 digest includes both the structured `tombstone` inventory and `kept_value_derived` map.
- All 37 block quotations match the cited authorities after normalizing Markdown quote markers and line wrapping. Inline quoted source wording also matches. C-02/C-16 are complete table rows; the replay and qualification excerpts are contiguous, verbatim portions of their source paragraphs (`docs/blueprint/amendments/2026-10-12-retention-replay.md:103`).
- Item 11 preserves the dated F2 qualification: interpretations needing approval remain owner-decided until the specified panel-acceptance mechanism exists (`docs/blueprint/amendments/2026-10-12-retention-replay.md:229`).
- The HIGH amendment correctly cites ledger §5 and Stage 5. Its incident rows, closure rules, visibility and exit status implement D9 R9 without inventing a data-spec HIGH-item clause (`docs/blueprint/amendments/2026-10-12-retention-replay.md:256`; `docs/workstreams/data-foundation/plans/D9.md:240`).
- All Markdown file links in both records resolve.

## A-05 ruling

**Approve keeping derived amounts under the stated private-use conditions. Q1 is not triggered.**

The applicable authority is an informed internal risk acceptance. A05-DECISION-005 expressly includes retention, internal processing and internal derived facts through the owner's own paid subscriber accounts; it preserves the private, personal, non-commercial boundary and rejects redistribution (`docs/evidence/phase-0a/a-05-rights-decision-005-subscriber-scraping.md:18`).

The later research identifies unresolved contractual exposure: neither vendor grants a licence suited to this standing pipeline, Screener requires destruction of downloaded materials on termination, and Tijori's derivative-works prohibition conflicts with the proposed use. Calling a figure an “outcome” does not settle that exposure. The record accurately accepts **Medium-High** Screener risk and **High** Tijori risk rather than claiming vendor permission (`docs/research/vendor-terms-screener-tijori-2026-10.md:82`; `:95`).

Within the existing rights decision, preserving the system's sealed comparison and disposition history justifies this bounded retention choice. Licence end must still purge captures and payload; retained outcomes remain private. The decision does not authorize new access after licence end or resolve Upstox's unassessed terms (`docs/blueprint/amendments/2026-10-12-a05-derived-amounts.md:124`).

## Redaction inventory

The inventory covers the current three vendor adapters, shared ingestion, interpretation/construction writers, calculation traces and result-source writers against the cited migrations. No omitted value-bearing column or JSON path was found in that scope.

- **Occurrences:** clearing raw lexemes and signs, dropping Tijori `native_context.island_value`, and dropping Upstox `disclosure.anomalies` removes the identified payload copies. The JSON allowlists also drop unlisted future keys (`docs/blueprint/amendments/2026-10-12-a05-derived-amounts.md:25`).
- **Interpretations and traces:** clearing numeric bounds and exact-text values, resetting `transform_trace`, and following transitive vendor-derived trace dependencies covers embedded and persisted calculations. The operand selector clears vendor-dependent operands while preserving unrelated first-party operands (`docs/blueprint/amendments/2026-10-12-a05-derived-amounts.md:42`; `src/fundamentals/evidence/repository_calc.py:26`).
- **Result values and attempts:** vendor/diagnostic source values are cleared separately from outcomes. Clearing vendor extraction-attempt `reason` is necessary: `vendor_ingest.py:171` copies extraction reasons, and Upstox's identity anomaly embeds both figures (`src/fundamentals/ingest/upstox_statements.py:86`; `:658`). This addition is approved.
- **Kept outcomes and identity:** the stated result, adjustment, definition, queue, disposition and identity records are explicitly retained. The examined source-reference and operational-failure writers carry identifiers, states and codes rather than additional raw financial values (`docs/blueprint/amendments/2026-10-12-a05-derived-amounts.md:206`).

**Approve the explicitly disclosed residual fields without further clearing:**

| Kept data | Ruling |
|---|---|
| `calculation_traces.content_sha256` | Keep the UNIQUE identity digest. It can confirm guessed values; that residual disclosure is explicitly accepted. |
| `occurrences.missing_state`, including `ZERO_PRINTED` | Keep source-state evidence, accepting that the zero state reveals a figure. |
| Tijori `declared_precision` | Keep precision provenance and its magnitude-band disclosure. |
| `interpretation_condition_evidence.holds` | Keep recorded condition evidence, accepting zero-condition disclosure. |
| Pair deltas with retained first-party values | Keep under `derived-amounts-kept`, accepting reconstruction of vendor figures. |

These exceptions are digest-bound in the A-05 subject (`docs/blueprint/amendments/2026-10-12-a05-derived-amounts.md:79`). Tombstoning therefore must not be represented as making every vendor figure unrecoverable.

## Glossary and tests

The Evidence-package sentence accurately summarizes the qualified reconstruction contract and contains no model names (`CONTEXT.md:57`). The test changes are minimal: exact record scopes/ids, a vendor-terms citation check, and extension of the existing glossary/model-name check (`tests/fundamentals/test_amendment_records.py:43`; `:115`; `:153`).

Fresh read-only verification:

- Direct in-memory execution of `test_a05_record_cites_vendor_terms` and `test_context_glossary`: passed.
- Independent scope, id, digest, link and inventory-action checks: passed.
- Both new `test_amendment_records` cases passed their preceding checks and stopped at the expected pending `status == "approved"` assertion (`tests/fundamentals/test_amendment_records.py:102`).
- Changed test source parsed successfully; scoped `git diff --check` passed.
- Final scoped Git status showed the two modified tracked files and two untracked records.

## Severity-ranked issues

None at P1, P2 or P3.

## Acceptance limits and integration

This approves the exact governance amendments, not D9 implementation, Stage 5 acceptance or a legal interpretation of vendor terms. No files, Git state, Beads state or databases were changed. The prohibited holdout paths were not opened or searched; no recursive tests/data search, pytest collection or full-suite run occurred.

The orchestrator must save this report, integrate per-item approval metadata, and run the focused amendment-record suite. The pending records are not represented here as already passing that gate. Substantive subject changes require a new digest and fresh review.
