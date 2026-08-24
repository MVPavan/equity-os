# A-05 Rights Decision Record — A05-DECISION-005 (Subscriber-Mode Screener.in + Tijori)

Amends `A05-DECISION-001` (which HELD Screener.in and Tijori and the repos
wrapping them) **for private personal use only**: authorizes automated,
authenticated, subscription-based collection from Screener.in and Tijori
Finance, given by the source-rights authority on 2026-08-24. This is an
informed risk-acceptance, not a determination that either service's terms
permit the activity.

## Decision

| Field | Value |
| --- | --- |
| Record ID | `A05-DECISION-005` |
| Decision | **AUTHORIZE_PRIVATE_SUBSCRIBER_USE** |
| Date | 2026-08-24 |
| Decider | PavanMV (`mvpavan42@gmail.com`), source-rights authority per `A05-DECISION-001` (D-6) |
| Scope | Automated authenticated collection from Screener.in and Tijori Finance using the owner's own PAID subscriber accounts (session cookies supplied by the owner), covering any surface those accounts can reach — financials, ratios, shareholding, peers, revenue mix, operational KPIs, market intelligence, documents, screens, custom metrics/columns, watchlists — for this personal non-commercial project; retention + internal processing + internal derived facts |
| Boundary | **PRIVATE / PERSONAL / NON-COMMERCIAL ONLY** — no redistribution, no public output of raw/substantial source data, no commercial use, no account sharing; both services remain DERIVED cross-check layers, never source-of-record |
| Supersedes | The "HELD — denied for now" disposition for Screener.in, Tijori, `LaZZy0v0/tijori-finance-mcp` (§6 row 7) and `VishwaGauravIn/screener-scraper-pro` (§6 row 9) in `A05-DECISION-001`; those rows may now be evaluated/used within this boundary |

Verbatim instruction (2026-08-24, in-session):

> "okay, now we are going to use both Screener and Tijori … quite a lot for
> cross-checking many things. I have subscriptions for both of them. I'll
> share necessary session IDs and anything if needed" … "I approve your
> second point as well. … We need subscriber mode screener."

## Boundary — private use only

PRIVATE / PERSONAL / NON-COMMERCIAL use ONLY, through the owner's own paid
accounts. If the project becomes public, commercial, multi-user, or
redistributed, **this decision is void** and the Screener/Tijori rows revert
to the `A05-DECISION-001` HELD disposition pending a fresh decision.

## Operational constraints (carried from house invariants)

- Polite fetching only: explicit timeouts, bounded retries, no parallel
  hammering, **no anti-bot evasion** (no stealth plugins, no fingerprint
  spoofing, no CAPTCHA solving); the client authenticates as the subscriber
  and behaves like a browser.
- Session cookies are secrets: injected at the composition root, never
  committed, never logged, never shared with third-party model providers.
- Both services are DERIVED sources; first-party Ind AS XBRL (NSE/BSE)
  remains the source-of-record spine. Load-bearing numbers must remain
  traceable to first-party evidence.

## Risk statement (accepted by the authority)

Screener.in's and Tijori's terms of service have not been formally reviewed;
aggregator terms commonly restrict automated access even for subscribers.
The prior bounded evaluations (`A05-DECISION-002`, bd memory
`rights-tijori-eval-2026-08-21`) operated under narrower one-time carve-outs.
The decider is the product-owner/source-rights authority, is informed of
these facts, and **accepts the ToS-conflict risk for private personal
non-commercial subscriber use only.** This is not legal advice.
