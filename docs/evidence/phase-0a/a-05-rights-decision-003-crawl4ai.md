# A-05 Rights Decision Record — A05-DECISION-003 (crawl4AI Evaluation Extension)

Extends `A05-DECISION-002`: a one-time, bounded, evaluation-only authorization
to test crawl4AI as a general web-crawler against the NSE and BSE public
websites, given verbatim by the source-rights authority on 2026-08-20.

## Decision

| Field | Value |
| --- | --- |
| Record ID | `A05-DECISION-003` |
| Decision | **EXTEND_BOUNDED_EVALUATION** |
| Date | 2026-08-20 |
| Decider | PavanMV (`mvpavan42@gmail.com`), source-rights authority per `A05-DECISION-001` (D-6) |
| Scope | One-time bounded evaluation of crawl4AI against NSE/BSE public sites, to characterize whether Infosys FY25 quarter-grain financials/filings are obtainable, for comparison with the wrapper libraries |
| Boundary | Containerized/isolated install; low-volume polite crawling; small internal samples only; private/internal only |

Verbatim instruction (2026-08-20, in-session, voice-transcribed):

> "Explore crawl4AI. It's a free github repo for web crawling, scraping. Maybe
> we can use this to scrape NSE and BSE websites themselves. Install crawl4AI
> via container and use it to scrape NSE and BSE websites for the same task so
> that we can compare."

## Limits and risk statement

Evaluation-only. Does **not** lift the `CHN-01` (NSE) / `CHN-02` (BSE)
decided-DENY dispositions of `A05-DECISION-001` for production, standing,
scheduled, or bulk use. **No anti-bot evasion tooling** — no proxy rotation,
CAPTCHA-solving, or fingerprint spoofing beyond a normal browser user-agent;
the evaluation stops on a hard block and records it as a finding. No bulk
retention, redistribution, public output, or production adoption. NSE's terms
of use expressly prohibit systematic/automated data collection including
scraping; the decider is informed and accepts the risk for this bounded
private evaluation only. Not legal advice or a legal review.

## Record digest convention and payload

Same convention as A-01: `sha256:<hex>` of the UTF-8 canonical JSON payload
(recursively sorted keys, compact separators, no digest field in the input).

```json
{"artifact_id":"A-05-DECISION-003","decider":"PavanMV (mvpavan42@gmail.com), source-rights authority per A05-DECISION-001 (D-6)","decision":"EXTEND_BOUNDED_EVALUATION","decision_date":"2026-08-20","decision_record_id":"A05-DECISION-003","explicit_limits":"Evaluation-only; extends A05-DECISION-002, does NOT lift the CHN-01/CHN-02 decided-DENY for production, standing, scheduled, or bulk use. No anti-bot evasion tooling (no proxy rotation, CAPTCHA-solving, or fingerprint spoofing beyond a normal browser user-agent); stop on hard block and record it. No bulk retention, redistribution, public output, or production adoption. NSE terms prohibit systematic/automated collection; decider is informed and accepts the risk for this bounded private evaluation only.","relationship_to_prior":"Extends A05-DECISION-002 (evaluation carve-out); both subordinate to A05-DECISION-001 (record digest sha256:3f71a7c0dee75f33d5f9fb132803795b3a88cb2a0873dc9e69b7a38f57deb816). All production dispositions unchanged.","scope":"One-time bounded evaluation of crawl4AI (unclabs/crawl4ai) as a general web-crawler against the NSE and BSE public websites, for the same objective as A05-DECISION-002: characterize whether quarter-grain structured financials / filings for Infosys FY25 are obtainable, to compare against the wrapper-library results. Permitted: containerized/isolated install; low-volume polite crawling; retention of small internal evaluation samples only.","verbatim_instruction":"Explore crawl4AI. It's a free github repo for web crawling, scraping. Maybe we can use this to scrape NSE and BSE websites themselves. Install crawl4AI via container and use it to scrape NSE and BSE websites for the same task so that we can compare. (2026-08-20, in-session, voice-transcribed)"}
```

**Record digest:** `sha256:756c4efbf2cab3dac0606d99f3f402793ee5d64dc972d7eedc5ac5e15ca10d1a`
