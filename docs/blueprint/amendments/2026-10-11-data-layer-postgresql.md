---
status: approved
scope: financial-data-layer
spec: docs/specs/2026-10-11-canonical-financial-data-and-cross-source-comparison.md
register: docs/blueprint/funda-blueprint-implementation-decision-register-v2.md
subject_sha256: dcd9a4bedb7ecd8022f85c5fab71e94ba3d95e0e35a35685d594269c6877fb15
amendments:
- id: postgresql-financial-data
  scope: financial-data-layer
  register_clause: G:last-bullet
  change: Override the PostgreSQL deferral for the financial data layer by the approved owner decision,
    without requiring a section H trigger.
- id: indian-market-data-target
  scope: financial-data-layer
  register_clause: first-release-target
  change: Set the first-release financial data layer target (dictionary, mappings, observation store
    and comparator) to the full Indian listed market.
approvals:
  postgresql-financial-data:
    reviewer: Codex /root/review_verifier_and_amendment
    date: '2026-10-13'
    verdict: APPROVE
    subject_sha256: dcd9a4bedb7ecd8022f85c5fab71e94ba3d95e0e35a35685d594269c6877fb15
    report: docs/workstreams/data-foundation/reviews/D1b-data-layer-amendment-review.md
  indian-market-data-target:
    reviewer: Codex /root/review_verifier_and_amendment
    date: '2026-10-13'
    verdict: APPROVE
    subject_sha256: dcd9a4bedb7ecd8022f85c5fab71e94ba3d95e0e35a35685d594269c6877fb15
    report: docs/workstreams/data-foundation/reviews/D1b-data-layer-amendment-review.md
---

# Financial data layer: PostgreSQL and Indian-market target

Recorded 2026-10-13, Codex session (handoff run), for the approved 2026-10-11 data spec.

This record changes exactly the two items in the [data spec's decision-register amendment](../../specs/2026-10-11-canonical-financial-data-and-cross-source-comparison.md#decision-register-amendment-scope-stated-exactly).
The original [decision register](../funda-blueprint-implementation-decision-register-v2.md#g-explicitly-deferred-from-the-first-release) remains the baseline.

1. The section G last-bullet PostgreSQL deferral is overridden for the financial data layer by
   the approved owner decision. A section H observed-need trigger is not a prerequisite for
   this specific override. The distributed workflow engine deferral remains in force.
2. The first-release target for the financial data layer—dictionary, mappings, observation
   store and comparator—is the full Indian listed market. It does not make full-universe
   daily research or company initiation a first-release product requirement.

The other section G deferrals and section H triggers remain in force, including automated
initiation, unattended capture, generalized autonomous planning, financial-sector and foreign
adapters. The [data-foundation roadmap's dated review ruling](../../workstreams/data-foundation/roadmap.md)
uses one fresh independent reviewer. This record carries no vendor-rights approval, new
credentials, live capture, operational database cutover or owner-time measurement authorization.

Fresh independent review approved each exact amendment on 2026-10-13. The header records
the actual reviewer, per-item verdict, date, subject digest and
[approval report](../../workstreams/data-foundation/reviews/D1b-data-layer-amendment-review.md).
Any substantive change to these two amendment items requires a new digest and fresh review.
