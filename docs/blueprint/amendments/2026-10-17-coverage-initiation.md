---
status: approved
scope: coverage-initiation
spec: docs/specs/2026-10-12-report-ledger-memory-and-data-lifecycle.md
register: docs/blueprint/funda-blueprint-implementation-decision-register-v2.md
subject_sha256: df3161a1f50bcb3fcafd36bc5fd78a22ae47239e6b96bffcbae1d1c6b1291f51
amendments:
- id: initiation-clarified
  scope: coverage-initiation
  register_clause: G:first-bullet
  change: 'Clarify, not lift, the deferral of full company initiation as an automated product: permit
    assisted, approval-gated initiation for owner-chosen watchlist stocks, whose first report is a BOOTSTRAP_THESIS.'
approvals:
  initiation-clarified:
    reviewer: gpt-6.1-sol
    date: '2026-10-17'
    verdict: APPROVE
    subject_sha256: df3161a1f50bcb3fcafd36bc5fd78a22ae47239e6b96bffcbae1d1c6b1291f51
    report: docs/workstreams/data-foundation/reviews/D7-amendment-1-review.md
---

# Coverage initiation: assisted, approval-gated initiation for watchlist stocks

Recorded 2026-10-17 for the approved 2026-10-12 report-ledger spec, Stage 4. Approved by the independent
reviewer on 2026-10-17; see the [approval report](../../workstreams/data-foundation/reviews/D7-amendment-1-review.md).

This record changes exactly item 1 of the [report-ledger spec's decision-register amendments](../../specs/2026-10-12-report-ledger-memory-and-data-lifecycle.md#decision-register-amendments-scope-stated-exactly).
The original [decision register](../funda-blueprint-implementation-decision-register-v2.md) remains the baseline.

## Register §G, verbatim

> ## G. Explicitly deferred from the first release
>
> - full company initiation as an automated product;

## Spec amendment 1, verbatim

> 1. **§G "full company initiation as an automated product"** — clarified, not lifted. Screen-driven
>    capture is not initiation (the owner chooses the screen and launches each batch; no report is
>    drafted). The amendment permits **assisted, approval-gated initiation for owner-chosen
>    watchlist stocks**: a first report is a bootstrap thesis (as A-11), agent-drafted and
>    panel-approved (§1), owner override kept. Still deferred: system-chosen coverage, unapproved
>    initiation, full-universe daily research.

## Permitted

- Assisted initiation for stocks the owner has put on the watchlist (an owner-only `ADD` decision with
  verbatim reason). Drafting for any other stock is refused.
- The first report for a new watchlist member is a `BOOTSTRAP_THESIS`, agent-drafted and approved by
  the approval panel, owner override kept.

## Still deferred

- System-chosen coverage.
- Unapproved initiation.
- Full-universe daily research.
- Every other §G item (GBrain as a mandatory dependency, generalized autonomous planning,
  multi-agent investment committee, broad sector-pack library) is unchanged.

Any substantive change to this item requires a new digest and fresh review.
