---
status: approved
scope: screen-export
spec: docs/specs/2026-10-12-report-ledger-memory-and-data-lifecycle.md
register: docs/blueprint/funda-blueprint-implementation-decision-register-v2.md
subject_sha256: 78efe8303a41c3599a0beafde420a2e85cd5577d2cec254447f893ca90758098
amendments:
- id: screens-vendor-export
  scope: screen-export
  ledger_clause: §4:screens
  change: 'Replace the whole §4 Screens paragraph: a screen run is the vendor''s own export of an
    owner-saved screen (Screener export form CSV, Tijori saved-query results JSON), fetched by the
    system on an owner command from the listed endpoints only; definitions stay versioned by hash
    of the definition as fetched; Screener `?q=` and other Screener query-string screen URLs stay
    prohibited.'
approvals:
  screens-vendor-export:
    reviewer: gpt-6.1-sol
    date: '2026-10-18'
    verdict: APPROVE
    subject_sha256: 78efe8303a41c3599a0beafde420a2e85cd5577d2cec254447f893ca90758098
    report: docs/workstreams/data-foundation/reviews/D7-amendment-2-review.md
---

# Screen export: the system fetches the vendors' own exports of owner-saved screens

Recorded 2026-10-18 for the approved 2026-10-12 report-ledger spec, §4 (D7 screen-export plan, ruling
S1). Approved by GPT-6.1 Sol on 2026-10-18 ([review](../../workstreams/data-foundation/reviews/D7-amendment-2-review.md)).

This record replaces exactly the **Screens** paragraph of [ledger spec §4](../../specs/2026-10-12-report-ledger-memory-and-data-lifecycle.md#4-coverage-model),
including its "results CSV the owner exported" and "CSV capture" wording. The rest of §4 and the
[decision register](../funda-blueprint-implementation-decision-register-v2.md) are unchanged.

## Before (spec §4, verbatim)

> **Screens.** A screen definition is owner-authored text (e.g. a Screener custom screen),
> versioned with a hash. Its only input is a results CSV the owner exported from Screener; the
> system never requests `?q=` URLs. A screen run records who ran it, when, the CSV capture
> (`VENDOR`) and its members, each resolved by exchange identifiers to a registry row or `UNRESOLVED`.

## After

> **Screens.** A screen definition is owner-authored text saved at a vendor (a Screener saved
> screen or a Tijori saved query), versioned with a hash of the definition as fetched. A screen
> run is the vendor's own export of that saved screen, fetched by the system on an owner command:
> Screener's export form (CSV) and Tijori's saved-query results endpoint (JSON). The system
> never requests Screener `?q=` or other Screener query-string screen URLs and requests only the
> endpoints the amendment record lists. A screen run records who ran it, when, its definition and results
> captures (`VENDOR`) and its members, each resolved by exchange identifiers to a registry row
> or `UNRESOLVED`. A member found on one side only, or unresolved, is a review item until the
> owner disposes it.

## Permitted endpoints

A screen export requests only these, each on an owner command, never scheduled:

- Screener: `GET /explore/` (the owner's saved screens); `GET /screens/<id>/<slug>/` (the saved
  screen page, definition and result count); `POST` to that page's one export form action (CSV).
- Tijori: `GET /api/filter_queries/search/?owner=true&limit=100&offset=0` (the owner's saved
  queries); `GET /api/filter_queries/advanced_search/` with the saved query's stored parameters (JSON).

Still prohibited: any Screener URL carrying `?q=`, `?page=`, `?sort=` or `?limit=`, and any
Screener or Tijori screen request not listed above. Evidence: [screen export probe](../../research/screen-export-probe.md).

## Vendor terms

Neither vendor's terms address automated access; Screener's robots.txt disallows `?q=`, `?page=`,
`?sort=` and `?limit=`, and its export help describes the CSV export for use in scripts; Tijori's
terms allow storage for personal, non-commercial use only ([vendor terms research](../../research/vendor-terms-screener-tijori-2026-10.md)).
The §4 catalog basis therefore binds every export: personal, single-owner, non-commercial
research; no redistribution; views stay local.

Any substantive change to this item requires a new digest and fresh review.
