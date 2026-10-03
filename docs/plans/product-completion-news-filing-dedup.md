# Exchange filing deduplication implementation plan

**Origin:** Existing `eqos-15h`; current user authorization to complete the product; existing operator-triggered news path. Gold V01/V07 requires equivalent filings to remain one inspectable event without losing evidence.
**Goal:** BSE and NSE titles for the same filing produce one event when the NSE title differs only by the known exchange notification wrapper, while distinct disclosures remain separate.
**Out of scope:** Scheduling, source acquisition, rights changes, media normalization, event materiality policy, lowering similarity thresholds, event identity migration and deferred monitoring activation.
**Constraints:** Preserve raw observations, their original titles and all provenance. Preserve existing issuer, event-type and time-window checks. No network, credentials, private captures, cloud, dependency changes, commits or Beads writes by the worker. Other agents are changing this repository; preserve their edits.

### Task 1: Match the known NSE wrapper at the comparison boundary

Goal: A resolved same-issuer BSE/NSE filing pair with different attachment URLs and the known NSE wording is deduplicated, while unrelated or ambiguous titles are not collapsed.

Files:
- Modify: `src/fundamentals/news/events.py`.
- Test: create `tests/fundamentals/test_news_filing_dedup.py`; existing `tests/fundamentals/test_news.py` is regression-only and read-only.

Interfaces:
- Consumes: `NewsObservation` and public `derive_news_events`; existing `normalize_news_text` and matching predicates.
- Produces: A narrow comparison-title normalization at `_same_event`, preserving public event/observation models and rendered raw titles.

Approach: First reproduce the reported split with synthetic public-shaped BSE and NSE observations. Inspect current NSE source IDs and first-party markers before deciding the wrapper guard. Remove only a recognized leading exchange-notification phrase from a resolved NSE first-party comparison title. Preserve company names or matching context as needed to avoid removing disclosure-specific wording. Keep category classification and generic normalization unchanged. Do not broaden media titles or unrecognized exchange wording. Use the existing similarity threshold after the narrow transformation; do not add a generic title rewrite or a new registry. If the body of the wrapper is empty, retain the original comparison behavior. Preserve every source observation and existing enrichment-stable event ID.

Verification: `.venv/bin/python -m pytest tests/fundamentals/test_news_filing_dedup.py tests/fundamentals/test_news.py -q`; expect the new reproduction to fail before implementation and the full scope to pass after. Run lint/format on the modified and new files and strict mypy for `src/fundamentals/news/events.py`.

Test seams: Public `derive_news_events` with synthetic resolved observations. Prove same filing merges and retains both observation IDs/raw titles, reversed input order remains deterministic, unrelated same-type disclosures stay separate, different issuers/types/outside-window pairs stay separate, a media imitation is not normalized, an unrecognized/empty wrapper is not collapsed, and adding the NSE duplicate preserves the existing BSE-anchored event ID.

Dependencies: None. Source/capture and pipeline workers own separate files; do not edit their files.

Risks: Test-first. Overbroad normalization can hide a distinct material filing. Treat unsupported wrapper variants as separate until there is evidence for a narrower supported rule. This repairs existing event derivation; it supplies no monitoring activation or known-event-population acceptance.

## Review and scope check

The current code applies normalized-title similarity only after a different-URL pair passes issuer/type/window checks. The change belongs at this comparison boundary, because changing generic normalization would affect classification and unrelated consumers. No required downstream model changes are planned. A fresh independent reviewer must check the actual wrapper guard, negative cases and preservation of backing observations before closure.
