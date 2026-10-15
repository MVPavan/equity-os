---
status: approved
scope: report-ledger-and-memory
spec: docs/specs/2026-10-12-report-ledger-memory-and-data-lifecycle.md
register: docs/blueprint/funda-blueprint-implementation-decision-register-v2.md
subject_sha256: ff12604ccf46da80fa5550b06130d1abee29809709cd4afb78d278a51ead792b
amendments:
- id: narrative-authority-postgresql
  scope: report-ledger-and-memory
  register_clause: B-03:narrative-row
  change: Move the approved narrative's authority from versioned Markdown files to PostgreSQL
    report-ledger rows; Markdown becomes a generated view.
- id: postgresql-ledger-memory
  scope: report-ledger-and-memory
  register_clause: G:last-bullet
  change: Extend the data spec's financial-data-layer override of the PostgreSQL deferral to the
    report ledger and long-term memory.
- id: memory-deletion-retirement
  scope: report-ledger-and-memory
  register_clause: D-01:deletion
  change: In the MemoryStore contract, deletion means retirement; memory rows are never physically
    removed.
- id: promotion-approval-roles
  scope: report-ledger-and-memory
  register_clause: invariant-11
  change: Memory promotion stays a separate decision, made by the approval panel or the owner role
    (override kept), replacing human-only promotion in invariant 11 and CONTEXT.md; roles are named,
    never models.
approvals:
  narrative-authority-postgresql:
    reviewer: gpt-6.1-sol
    date: '2026-10-15'
    verdict: APPROVE
    subject_sha256: ff12604ccf46da80fa5550b06130d1abee29809709cd4afb78d278a51ead792b
    report: docs/workstreams/data-foundation/reviews/D3-ledger-amendment-review.md
  postgresql-ledger-memory:
    reviewer: gpt-6.1-sol
    date: '2026-10-15'
    verdict: APPROVE
    subject_sha256: ff12604ccf46da80fa5550b06130d1abee29809709cd4afb78d278a51ead792b
    report: docs/workstreams/data-foundation/reviews/D3-ledger-amendment-review.md
  memory-deletion-retirement:
    reviewer: gpt-6.1-sol
    date: '2026-10-15'
    verdict: APPROVE
    subject_sha256: ff12604ccf46da80fa5550b06130d1abee29809709cd4afb78d278a51ead792b
    report: docs/workstreams/data-foundation/reviews/D3-ledger-amendment-review.md
  promotion-approval-roles:
    reviewer: gpt-6.1-sol
    date: '2026-10-15'
    verdict: APPROVE
    subject_sha256: ff12604ccf46da80fa5550b06130d1abee29809709cd4afb78d278a51ead792b
    report: docs/workstreams/data-foundation/reviews/D3-ledger-amendment-review.md
---

# Report ledger and memory: narrative authority, PostgreSQL, retirement, promotion roles

Recorded 2026-10-15 for the approved 2026-10-12 report-ledger spec, Stage 1.

This record changes exactly items 3, 5, 7 and 8 of the [report-ledger spec's decision-register amendments](../../specs/2026-10-12-report-ledger-memory-and-data-lifecycle.md#decision-register-amendments-scope-stated-exactly).
The original [decision register](../funda-blueprint-implementation-decision-register-v2.md) remains the baseline.

1. **B-03**, narrative row only: the approved narrative's authority moves from versioned
   Markdown files to PostgreSQL rows; Markdown is a generated view. The other B-03 rows are
   unchanged.
2. **§G last bullet**: the data spec's PostgreSQL override for the financial data layer extends
   to the report ledger and long-term memory. The distributed workflow engine deferral remains.
3. **D-01**: "deletion" means retirement; memory rows are never physically removed.
4. **Invariant 11** and CONTEXT.md: promotion stays a separate decision, by the approval panel or
   the owner role, who may override (owner autonomy directive 2026-10-12). Docs name roles; panel
   models are configuration, never named here.

Items 1, 2 and 6 of the spec (initiation, C-16, C-02) belong to Stages 4 and 5 and are not part
of this record. The data spec's market-wide capture deferral, §H triggers and GBrain deferrals
remain in force.

Fresh independent review approved each exact amendment on 2026-10-15. The header records the
per-item approval-panel verdict, date, subject digest and
[approval report](../../workstreams/data-foundation/reviews/D3-ledger-amendment-review.md).
Any substantive change to these four items requires a new digest and fresh review.
