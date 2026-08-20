# A-05 Rights Decision Record — A05-DECISION-002 (Bounded Evaluation Carve-Out)

Narrow amendment to `A05-DECISION-001`: a one-time, bounded, evaluation-only
authorization for the data-gathering candidate tools, given verbatim by the
source-rights authority on 2026-08-20.

## Decision

| Field | Value |
| --- | --- |
| Record ID | `A05-DECISION-002` |
| Decision | **AUTHORIZE_BOUNDED_EVALUATION** |
| Date | 2026-08-20 |
| Decider | PavanMV (`mvpavan42@gmail.com`), source-rights authority per `A05-DECISION-001` (D-6) |
| Scope | One-time bounded evaluation of the data-gathering candidate repositories in `docs/research/external-tools-and-repos-inventory.md` §6 (NSE/BSE wrappers, Screener/Tijori/FII-DII tools, MCP servers): isolated-environment installation, low-volume polite test calls characterizing available data for the Infosys FY25 slice, small internal evaluation samples only |
| Boundary | Private/internal only; no bulk retention; no redistribution; no public output; no production adoption |

Verbatim instruction (2026-08-20, in-session, voice-transcribed):

> "Use NSE BSE libraries I just gave you. Install them in a container somewhere
> or in a separate virtual environment somewhere, and check what they give for
> all of these. Verify. This is also a kind of review on all the tools I have
> given at the end, especially for NSE/BSE, screener, or Tijori finance. …
> Don't get into all the other tools like databases, memories, agents, and all
> those. I'm talking about data gathering tools. So do this thoroughly, and let
> me know."

## Limits and risk statement

This record does **not** lift the HELD/DENY dispositions of `A05-DECISION-001`
for production, standing, scheduled, or bulk use — those require a further
decision informed by this evaluation's findings. NSE's terms of use expressly
prohibit systematic/automated data collection including scraping; BSE's terms
are unretrievable; Screener.in and Tijori have their own unreviewed terms. The
decider is informed of these facts and accepts the risk for this bounded
private evaluation. Not legal advice or a legal review.

## Record digest convention and payload

Same convention as A-01: `sha256:<hex>` of the UTF-8 canonical JSON payload
(recursively sorted keys, compact separators, no digest field in the input).

```json
{"artifact_id":"A-05-DECISION-002","decider":"PavanMV (mvpavan42@gmail.com), current user/product-owner principal, acting as source-rights authority per A05-DECISION-001 (D-6)","decision":"AUTHORIZE_BOUNDED_EVALUATION","decision_date":"2026-08-20","decision_record_id":"A05-DECISION-002","explicit_limits":"Evaluation-only. Does NOT lift the HELD/DENY dispositions of A05-DECISION-001 for production, standing, scheduled, or bulk use. No bulk data retention, no redistribution, no public output, no production adoption. NSE terms prohibit systematic/automated collection; the decider is informed and accepts the risk for this bounded private evaluation.","relationship_to_prior":"Narrow carve-out amending A05-DECISION-001 (record digest sha256:4762d1976d36f2263247dbd41bff2f1a3c416bae9c141ee98a68ac484a3ec36b); all other dispositions unchanged.","scope":"One-time bounded evaluation of the data-gathering candidate repositories in docs/research/external-tools-and-repos-inventory.md section 6 (NSE/BSE wrapper libraries, Screener/Tijori/FII-DII tools and MCP servers). Permitted operations: installation in isolated environments; low-volume polite test calls to their endpoints to characterize available data for the Infosys FY25 slice; retention of small internal evaluation samples only. Private/internal boundary only.","verbatim_instruction":"Use NSE BSE libraries I just gave you. Install them in a container somewhere or in a separate virtual environment somewhere, and check what they give for all of these. Verify. This is also a kind of review on all the tools I have given at the end, especially for NSE/BSE, screener, or Tijori finance. Don't get into all the other tools like databases, memories, agents, and all those. I'm talking about data gathering tools. So do this thoroughly, and let me know. (2026-08-20, in-session, voice-transcribed)"}
```

**Record digest:** `sha256:d426cfaaa2d6711451fab9de67d857a90428dc63778952050645010a0d0fb1c7`
