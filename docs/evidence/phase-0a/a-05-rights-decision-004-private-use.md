# A-05 Rights Decision Record — A05-DECISION-004 (Private/Personal-Use Authorization)

Amends `A05-DECISION-001` **for private personal use only**: authorizes
automated collection of NSE/BSE public data via the evaluated wrapper
libraries and crawl4AI, given by the source-rights authority on 2026-08-21.
This is an informed risk-acceptance, not a determination that the exchanges'
terms permit the activity.

## Decision

| Field | Value |
| --- | --- |
| Record ID | `A05-DECISION-004` |
| Decision | **AUTHORIZE_PRIVATE_PERSONAL_USE** |
| Date | 2026-08-21 |
| Decider | PavanMV (`mvpavan42@gmail.com`), source-rights authority per `A05-DECISION-001` (D-6) |
| Scope | Automated collection of NSE/BSE public listed-company data (results, Ind AS XBRL, announcements, shareholding, corporate actions, prices) via nselib / NseIndiaApi (`nse`) / nsepython / jugaad-data / bsedata / `bse` and crawl4AI, for this personal non-commercial project; retention + internal processing + internal derived facts |
| Boundary | **PRIVATE / PERSONAL / NON-COMMERCIAL ONLY** — no redistribution, no public output of raw/substantial source data, no commercial use, no public product |

Verbatim instruction (2026-08-21, in-session):

> "2, I approve for scraping" (electing the "central and cheap" scraping path
> over the "proper" paid licensed feeds, for a stated personal project).

## Boundary — private use only

PRIVATE / PERSONAL / NON-COMMERCIAL use ONLY. If the project becomes public,
commercial, multi-user, or redistributed, **this decision is void** and
`CHN-01`/`CHN-02` revert to the `A05-DECISION-001` DENY pending a fresh
decision.

## Risk statement (accepted by the authority)

NSE's terms of use expressly prohibit systematic/automated data collection
including scraping; BSE's terms are unretrievable; the wrapper libraries and
crawl4AI collect from these first-party endpoints without the publishers'
permission. The decider is the product-owner/source-rights authority, is
informed of these facts, and **accepts the ToS-conflict risk for private
personal non-commercial use only.** This is not legal advice and not a
determination that the terms permit this — it is an informed risk-acceptance.

## Evasion boundary (unchanged)

This decision does **not** authorize dedicated anti-bot-detection evasion —
fingerprint/navigator spoofing, stealth/undetected browser plugins,
sensor-data forgery, CAPTCHA-solving, or proxy/IP rotation. The evaluated
libraries and crawl4AI's normal browser rendering do not require these; a
source reachable only by defeating an active security control remains a
separate, unmade decision.

## Operational limits

Polite, low-volume, pilot-scoped (Infosys) to start; scale only as the
personal project genuinely needs it. Prefer first-party structured data
(XBRL) over derived aggregators (Screener/Tijori), which carry their own
terms and lack provenance.

## Relationship to prior decisions

Amends `A05-DECISION-001` for **private use only**: `CHN-01` (NSE) and
`CHN-02` (BSE) automated-collection operations move from decided-DENY to
ALLOWED-FOR-PRIVATE-PERSONAL-USE within the boundary above. Supersedes the
production-HELD status of the evaluated libraries in
`docs/research/external-tools-and-repos-inventory.md` for private use, and the
evaluation-only framing of `A05-DECISION-002`/`003` for these libraries in the
private-use context. Infosys IR (`SRC-*`) and SEC EDGAR dispositions are
unchanged. Not legal advice.

## Record status note

This record uses a prose form rather than the embedded canonical-JSON + SHA-256
digest convention of `A05-DECISION-001/002/003`. The decision is additionally
captured in the `bd` memory key `rights-private-scraping-approved-2026-08-21`.
A digest-bound machine payload may be regenerated later; the binding facts are
the decision, boundary, and risk-acceptance stated above.
