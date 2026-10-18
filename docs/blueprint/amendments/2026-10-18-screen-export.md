---
status: approved
scope: screen-export
spec: docs/specs/2026-10-12-report-ledger-memory-and-data-lifecycle.md
register: docs/blueprint/funda-blueprint-implementation-decision-register-v2.md
subject_sha256: a5155fbebfd5057a480baeb39286adc0667a2ab82bac0127745d9f33108b42be
amendments:
- id: screens-vendor-export
  scope: screen-export
  ledger_clause: §4:screens
  change: 'Replace the whole §4 Screens paragraph: a screen definition is owner-authored formula
    text in the repository, one formula per vendor, versioned by hash of that text; nothing is
    saved at either vendor; a screen run is the system running that formula directly at the
    vendor on an owner command (Screener raw-query page and its export form CSV, Tijori advanced
    search JSON), from the listed endpoints only, retaining every response and refusing any
    response whose echoed formula or export action differs from the configured formula, plus
    one-page diagnostic reads of a one-sided member at the other vendor; Screener `?q=`,
    `?page=`, `?sort=` and `?limit=` URLs stay prohibited.'
approvals:
  screens-vendor-export:
    reviewer: gpt-6.1-sol
    date: '2026-10-18'
    verdict: APPROVE
    subject_sha256: a5155fbebfd5057a480baeb39286adc0667a2ab82bac0127745d9f33108b42be
    report: docs/workstreams/data-foundation/reviews/D7-amendment-3-review.md
---

# Screen export: the system runs owner-authored formulas at each vendor and keeps the exports

Recorded 2026-10-18 for the approved 2026-10-12 report-ledger spec, §4 (D7 screen-export plan, ruling
S1). Revised 2026-10-18 on owner direction (no screens saved at Screener or Tijori; run the
queries directly, export, keep the files). The revision supersedes the version approved under
digest `78efe8303a41c3599a0beafde420a2e85cd5577d2cec254447f893ca90758098`; that approval does
not carry over. Approved by GPT-6.1 Sol on 2026-10-18 ([review](../../workstreams/data-foundation/reviews/D7-amendment-3-review.md)).

This record replaces exactly the **Screens** paragraph of [ledger spec §4](../../specs/2026-10-12-report-ledger-memory-and-data-lifecycle.md#4-coverage-model),
including its "results CSV the owner exported" and "CSV capture" wording. The rest of §4 and the
[decision register](../funda-blueprint-implementation-decision-register-v2.md) are unchanged.

## Before (spec §4, verbatim)

> **Screens.** A screen definition is owner-authored text (e.g. a Screener custom screen),
> versioned with a hash. Its only input is a results CSV the owner exported from Screener; the
> system never requests `?q=` URLs. A screen run records who ran it, when, the CSV capture
> (`VENDOR`) and its members, each resolved by exchange identifiers to a registry row or `UNRESOLVED`.

## After

> **Screens.** A screen definition is owner-authored formula text kept in the repository, one
> formula per vendor (Screener and Tijori query syntax), versioned with a hash of that text;
> nothing is saved at either vendor. A screen run is the system running that formula directly at
> the vendor on an owner command and retaining the vendor's own responses: Screener's raw-query
> page and its export form (CSV), Tijori's advanced search (JSON). The system requests only the
> endpoints the amendment record lists and never a Screener URL carrying `?q=`, `?page=`,
> `?sort=` or `?limit=`. A screen run records who ran it, when, its definition and its captures
> (`VENDOR`) and its members, each resolved by exchange identifiers to a registry row or
> `UNRESOLVED`. A member found on one side only, or unresolved, is a review item until the owner
> disposes it.

## Permitted endpoints

A screen export requests only these, each on an owner command, never scheduled:

- Screener: `GET /screen/raw/?query=<formula>`, `query` the only parameter (the vendor's echo of
  the formula, its result count and one export form); `POST` to that page's one export form
  action, which must be exactly path `/api/export/screen/` with query keys `query` and `url_name`
  once each, `query` equal to the formula and `url_name` equal to the literal `raw_query`, no fragment
  (CSV of all results). Formulas compare after collapsing whitespace runs and stripping the ends.
- Tijori: `GET /api/filter_queries/advanced_search/?financial=<formula>&is_checked=False&whales=False&is_sme=False`
  (JSON, all results in one response); its echoed `financial_q` must equal the formula and
  `alternate_q` be empty, else the run is refused.
- Diagnostic reads, one page each for a pending one-sided member after the export commits, no
  formula: the Screener company page and the Tijori overview page, through the existing readers.

Still prohibited: any Screener URL carrying `?q=`, `?page=`, `?sort=` or `?limit=` (and the
`sort`, `order`, `page`, `limit` and `source_id` parameters on the raw-query page), saving,
listing or editing a screen at either vendor, and any Screener or Tijori request not
listed above. Evidence: [screen export probe](../../research/screen-export-probe.md) and the
orchestrator's live probe of 2026-10-18 (raw responses kept locally, not committed).

## Vendor terms

Neither vendor's terms address automated access. Screener's robots.txt (fetched 2026-10-18)
disallows `/user/*`, `/*?q=`, `/*?sort=`, `/*?limit=`, `/*?page=` and
`/company/source/quarter/*`; both permitted Screener URLs begin `?query=`, which matches none of
these literal prefixes (`?query=` is not `?q=`). Its export help describes the CSV export for use
in scripts. Tijori's robots.txt allows all; its terms allow storage for personal, non-commercial
use only ([vendor terms research](../../research/vendor-terms-screener-tijori-2026-10.md)).
The §4 catalog basis therefore binds every export: personal, single-owner, non-commercial
research; no redistribution; views stay local.

Any substantive change to this item requires a new digest and fresh review.
