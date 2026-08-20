# A-05 Source Rights Package

**Record version:** 1.2.0
**Status:** PARTIALLY_DECIDED_REMAINDER_PENDING — the product owner's source-rights decision `A05-DECISION-001` (2026-08-20) is **transcribed** here; every cell it does not cover remains `UNKNOWN (denied by default)`
**Recorded at:** 2026-08-20 (v1.0.0); amended 2026-08-20 (v1.1.0 — conformed to the approved plan file map; machine form added); amended 2026-08-20 (v1.2.0 — `A05-DECISION-001` recorded)
**Author:** bounded implementer (recording agent, not the decision maker)
**Stage / bead:** S2 `eqos-3ps.2`, plan Task 2 (`docs/plans/2026-08-19-phase-0a-evidence-program.md`)
**Decision record:** `docs/evidence/phase-0a/a-05-rights-decision-record.md` — `A05-DECISION-001`

## Artifact pair

The machine-readable `SourceRightsPackage` required by the plan's file map is
**`docs/evidence/phase-0a/a-05-source-rights-package.json`**. This document is its human-readable
companion; the two carry the same sources, the same operation vocabulary, and the same 132
dispositions.

The JSON additionally carries the **24 exact S1 inventory source/use pairs** in the inventory's own
prose operation vocabulary, so that a set comparison against
`docs/evidence/phase-0a/source-package-inventory.json` is exact, together with a mapping from each
prose operation to the normalized `OP-01 … OP-12` identifiers used below. Every publisher quotation
in the JSON is **extracted mechanically from this document**, so the two cannot drift. The JSON file
digest is bound into this record's digest payload below.

## What this record is and is not

This record collects **published terms, policy, and access observations** for every source in the
S1 metadata-only inventory (`docs/evidence/phase-0a/source-package-inventory.json`) and for the
official filing channels recorded alongside it, and **transcribes** the source-rights decision the
competent authority made against that evidence.

It is **not itself** a rights decision, a legal review, a legal opinion, an interpretation of any
quoted term, or a finding of legal sufficiency. It **grants** nothing. Every `ALLOWED` cell below
is a transcription of `A05-DECISION-001`
(`docs/evidence/phase-0a/a-05-rights-decision-record.md`), made by the product owner on 2026-08-20
on a self-assumed mandate **with no legal credential claimed and no legal review performed**;
permission flows from that decision, never from this file. Public reachability of a URL, the
presence of a document in the S1 inventory, the A-01 boundary decision, and the A-02 slice
selection each still establish **no** right.

Per the approved plan, unknown or unapproved operations are **denied**: acquisition,
transformation, and use remain denied except for operations the authority independently marked
`ALLOWED`, which are exactly the cells cited to `A05-DECISION-001` below. A source-level decision
may never widen an operation that is independently denied or unknown; no source-level access
decision exists, so none does.

The A-01 boundary (`docs/evidence/phase-0a/a-01-initial-boundary-decision.md`) independently
prohibits public, paid, personalized, and execution-linked modes. That prohibition is **separate
from and additional to** the rights dispositions below; it does not make any other operation
permitted.

## Method and limits of the evidence

- During evidence collection (versions 1.0.0 and 1.1.0) only terms of use, website policy,
  disclaimer, `robots.txt`, and regulator/legal pages were requested; **no source-package content
  was fetched, downloaded, parsed, or hashed** at that stage.
- **Subsequently, under `A05-DECISION-001` (2026-08-20), the eight enumerated Infosys IR documents
  were retrieved** in a one-time, human-directed, agent-assisted fetch — 8 URLs requested, 8/8
  `OK`, per-file SHA-256 recorded in
  `docs/evidence/phase-0a/a-05-retrieval-manifest-infy-fy25.json`. The retrieved PDFs live under a
  gitignored path and **must never be committed**; the manifest carries URLs, byte counts, and
  digests only. The per-source `source_content_digest_state` fields in the companion JSON continue
  to mirror the S1 inventory, which this record does not amend.
- Access date for every observation in this record: **2026-08-20**.
- Where a live publisher page could not be retrieved, the failure is recorded as a fact and the
  terms content is marked `NOT_RETRIEVED`; where an Internet Archive snapshot was used instead,
  the snapshot timestamp is stated and the evidence is scoped to that snapshot, **not** to the
  current live page.
- Quotations are reproduced verbatim from the retrieved page text. Emphasis is never added.
- No provider, procurement route, account, credential, parser, automation mechanism, or vendor is
  selected, recommended, or evaluated in this record.

## Source register

Sources `SRC-01` through `SRC-08` are the exact eight `source_id` values in the S1 inventory.
`CHN-01` and `CHN-02` are the official exchange filing channels recorded in
`docs/evidence/phase-0a/a-02-discovery-slice-selection.md` and
`docs/research/phase-0a-discovery-company-shortlist.md`; they carry no S1 `source_id`.
`CHN-03` is **not** in the S1 inventory and appears only because A-06 examines it as a filing
channel; listing it here does not add it to the selected source package.

| Ref | S1 `source_id` / channel | Publisher / host | Program quarter | Recorded reference |
|---|---|---|---|---|
| SRC-01 | `INFY-FY25-Q1-results-auditors` | Infosys Limited — `www.infosys.com` | Q0 | `.../2024-2025/q1/documents/q1-fy25-financial-results-auditorsreports.pdf` |
| SRC-02 | `INFY-FY25-Q1-management-transcript` | Infosys Limited — `www.infosys.com` | Q0 | `.../2024-2025/q1/documents/transcripts/press-conference.pdf` |
| SRC-03 | `INFY-FY25-Q2-results-auditors` | Infosys Limited — `www.infosys.com` | Q1 | `.../2024-2025/q2/documents/q2-and-h1-fy25-financial-results-auditorsreports.pdf` |
| SRC-04 | `INFY-FY25-Q2-management-transcript` | Infosys Limited — `www.infosys.com` | Q1 | `.../2024-2025/q2/documents/transcripts/press-conference.pdf` |
| SRC-05 | `INFY-FY25-Q3-results-auditors` | Infosys Limited — `www.infosys.com` | Q2 | `.../2024-2025/q3/documents/q3-and-9m-fy25-financial-results-auditorsreports.pdf` |
| SRC-06 | `INFY-FY25-Q3-management-transcript` | Infosys Limited — `www.infosys.com` | Q2 | `.../2024-2025/q3/documents/transcripts/earningscall.pdf` |
| SRC-07 | `INFY-FY25-Q4-results-auditors` | Infosys Limited — `www.infosys.com` | Q3 | `.../2024-2025/q4/documents/q4-and-12m-fy25-financial-results-auditorsreports.pdf` |
| SRC-08 | `INFY-FY25-Q4-ifrs-press-release` | Infosys Limited — `www.infosys.com` | Q3 | `.../2024-2025/q4/documents/ifrs-usd-press-release.pdf` |
| CHN-01 | NSE financial-results / Integrated Filing–Financial channel (no S1 `source_id`) | National Stock Exchange of India Ltd — `www.nseindia.com` | Q0–Q3 | `https://www.nseindia.com/companies-listing/corporate-filings-financial-results` |
| CHN-02 | BSE company results channel, scrip code 500209 (no S1 `source_id`) | BSE Limited — `www.bseindia.com` | Q0–Q3 | `https://www.bseindia.com/corporates/Comp_Results.aspx?Code=500209` |
| CHN-03 | SEC EDGAR filings for Infosys Ltd, CIK `0001067491` (**not in S1 inventory**) | U.S. Securities and Exchange Commission — `www.sec.gov` | Q0–Q3 | `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001067491` |

## Intended-operation vocabulary

The S1 inventory records intended operations in prose per source. This record normalizes them into
twelve operations so that each can carry an independently scoped disposition. Every one of the
nine distinct prose operations recorded in S1 (`manual reading`, `source-location capture`,
`manual baseline observation extraction`, `assisted update input`, `reconciliation against Q0`,
`reconciliation against prior quarters`, `management-guidance ledger extraction`,
`management-guidance revision extraction`, `guidance-outcome comparison`) maps onto one or more
of `OP-01`, `OP-05`, `OP-06`, `OP-07`, and `OP-08`; the exact mapping is the
`s1_prose_operation_mapping` field of the companion JSON. No prose operation is dropped and none
is invented.

| Op | Operation | Scope |
|---|---|---|
| OP-01 | Human interactive access and reading | A person opening the document in a browser and reading it. |
| OP-02 | Programmatic / automated retrieval | Any scripted, batched, scheduled, crawled, or tool-driven fetch. |
| OP-03 | Retention of source bytes | Keeping the retrieved file beyond transient display, in any store. |
| OP-04 | Caching | Any *additional* intermediate, proxy, CDN, or shared reuse cache of live-fetched source content. Clarification, not a new permission: a single retained local copy already covered by `OP-03`, re-read by the same principal, is `OP-03` and not `OP-04`. |
| OP-05 | Source-location capture | Recording URL, document identity, page/section anchors as citations. |
| OP-06 | Fact and figure extraction into internal records | Copying values, statements, or guidance text into program artifacts. |
| OP-07 | Transformation and derived outputs | Computations, reconciliations, summaries, memos derived from the source. |
| OP-08 | Machine processing (parser, LLM, or other automated reader) | Submitting source content to any automated processing system. |
| OP-09 | Internal redistribution inside the A-01 private/internal boundary | Sharing source content or close derivatives with internal recipients. |
| OP-10 | External redistribution or publication | Any distribution outside the internal boundary. |
| OP-11 | Commercial use | Any revenue-linked, paid, or commercial application. |
| OP-12 | Hashing / content digesting of source bytes | Computing a content digest, which requires holding the bytes. |

`OP-10` and `OP-11` are **additionally prohibited by A-01** irrespective of rights. That
prohibition is separate from the rights dispositions below: `OP-10` is now `DENIED` on rights
grounds for every source as well, while `OP-11` is `DENIED` for CHN-01 and CHN-02 and remains
`UNKNOWN` for the other nine sources because `A05-DECISION-001` did not address commercial use
there — and stays denied either way.

## Disposition table — as decided by `A05-DECISION-001`

**Legend:** `A` = `ALLOWED`, `D` = `DENIED`, `U/D` = `UNKNOWN (denied by default)`.
**11 sources × 12 operations = 132 disposition cells: 66 `ALLOWED`, 41 `DENIED`, 25
`UNKNOWN (denied by default)`.** Every `A` and every `D` cell cites `decision_ref`
`A05-DECISION-001` and carries `authority_envelope` `A05-DECISION-001` in the companion JSON;
every `U/D` cell carries `NOT_COVERED_BY_A05-DECISION-001` and remains denied.

| Ref | OP-01 | OP-02 | OP-03 | OP-04 | OP-05 | OP-06 | OP-07 | OP-08 | OP-09 | OP-10 | OP-11 | OP-12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SRC-01 | A | A | A | U/D | A | A | A | A | D | D | U/D | A |
| SRC-02 | A | A | A | U/D | A | A | A | A | D | D | U/D | A |
| SRC-03 | A | A | A | U/D | A | A | A | A | D | D | U/D | A |
| SRC-04 | A | A | A | U/D | A | A | A | A | D | D | U/D | A |
| SRC-05 | A | A | A | U/D | A | A | A | A | D | D | U/D | A |
| SRC-06 | A | A | A | U/D | A | A | A | A | D | D | U/D | A |
| SRC-07 | A | A | A | U/D | A | A | A | A | D | D | U/D | A |
| SRC-08 | A | A | A | U/D | A | A | A | A | D | D | U/D | A |
| CHN-01 | U/D | D | D | D | D | D | D | D | D | D | D | D |
| CHN-02 | D | D | D | D | D | D | D | D | D | D | D | D |
| CHN-03 | A | A | U/D | U/D | U/D | U/D | U/D | U/D | D | D | U/D | U/D |

### Decision bases

Each cell above cites one of these bases, carried verbatim in the companion JSON's
`decision_bases` object with its rationale, the exact term relied on, conditions and limits, scope
boundary, and the events that invalidate it.

| Basis | Cells | Disposition | Short form |
|---|---|---|---|
| `DB-01-INFY-INTERNAL-ALLOW` | SRC-01 … SRC-08 × OP-01, 02, 03, 05, 06, 07, 08, 12 | `ALLOWED` | Human-directed retrieval — including the one-time agent-assisted Python-requests fetch of the eight enumerated URLs executed 2026-08-20 — plus internal retention, internal AI processing, and internal derived facts and claims for private research. `OP-05` (source-location capture) and `OP-12` (content digesting) are recorded `ALLOWED` as **direct entailments of that instructed retrieval and of the manifest digests the decider was shown, not as separately spoken permissions**. `OP-02` is limited to that one-time fetch; standing, scheduled, recurring, or crawling retrieval stays `UNKNOWN`. |
| `DB-02-INFY-REDIST-DENY` | SRC-01 … SRC-08 × OP-09, OP-10 | `DENIED` | No redistribution, publication, or public output of source bytes or substantial excerpts. The decider did not separately distinguish internal from external redistribution, so the deny is applied to both fail-closed. |
| `DB-04-SEC-FAIR-ACCESS-ALLOW` | CHN-03 × OP-01, OP-02 **only** | `ALLOWED` | Access within the SEC's published fair-access limits — max 10 requests/second, declared descriptive user agent, efficient scripting — and entry into the source list. **Authorizes access only**; nothing may yet be retained, extracted, transformed, machine-processed, captured, or hashed from CHN-03. |
| `DB-05-SEC-REDIST-DENY` | CHN-03 × OP-09, OP-10 | `DENIED` | Same internal-only output boundary as `DB-02`. |
| `DB-06-NSE-DENY` | CHN-01 × OP-02 … OP-12 | `DENIED` | All automated collection denied; the NSE terms expressly prohibit systematic or automated data collection. |
| `DB-08-NSE-HUMAN-BROWSING-OUT-OF-SCOPE` | CHN-01 × OP-01 | `UNKNOWN (denied by default)` | Human browsing was declared **out of scope of the system, not decided**. Out of scope is not denied, so the cell stays `UNKNOWN` and denied by default; no artifact in this program may rest on it. |
| `DB-07-BSE-DENY` | CHN-02 × all twelve operations | `DENIED` | All operations denied; the operative `www.bseindia.com` terms were not retrievable, so there is nothing to rely on. |
| `DB-03-NOT-COVERED-UNKNOWN` | SRC-01 … SRC-08 × OP-04, OP-11; CHN-03 × OP-03, 04, 05, 06, 07, 08, 11, 12 | `UNKNOWN (denied by default)` | The decision is silent on these operations. Silence is `UNKNOWN` and therefore denied; **nothing is inferred from the operations that were decided** — including for CHN-03, where the decider spoke to access only and the remaining operations are deliberately **not** carried over from the Infosys allowance. `OP-11` is additionally prohibited by A-01. |

Supporting per-pair fields required by the plan — access method, automation, caching, retention,
commercial use, transformation/derived output, redistribution, account limits, point-in-time
availability, and replacement path — carry the decided envelope on every **decided** cell, and are
**neutral `UNKNOWN` on all 25 undecided cells**: a source's decided envelope says nothing about an
operation nobody decided, so an undecided cell never displays an `ALLOWED`-looking string next to
its `UNKNOWN` disposition. **Account limits, point-in-time availability, and replacement path
remain `UNKNOWN` on every cell of every source**: they are unanswered facts, not dispositions, and
decision items D-3 and D-4 are still open. `authority_envelope` is `A05-DECISION-001` on decided
cells and `NOT_COVERED_BY_A05-DECISION-001` elsewhere.

### Held, not decided

Screener.in, Tijori, and **exactly the eleven ⛔-marked rows** of
`docs/research/external-tools-and-repos-inventory.md` §6 — rows 3, 4, 5, 6, 7, 8, 9, 11, 12, 13,
and 14 (`nsepython`, `NseIndiaApi`, `BseIndiaApi`, `nselib`, `tijori-finance-mcp`, `jugaad-data`,
`screener-scraper-pro`, `fii-dii-data`, `nse-bse-indian-stock-market-data-mcp`, `NSEDownload`,
`fii-dii-analysis`) — are **HELD — denied for now**, to be revisited after program Q0 (manual
baseline) shows what data is actually missing. §6 rows 1 (`FinceptTerminal`), 2
(`machine-learning-for-trading`), and 10 (`openscreener`) have no source access of their own, are
**not** held, and remain CANDIDATE-UNDECIDED. None of these are sources in this register and none
carries a cell in the grid; the hold is recorded in the companion JSON under
`held_pending_q0_review` so it stays discoverable.

## Publisher terms evidence

### P1 — Infosys Limited (`www.infosys.com`) — governs SRC-01 … SRC-08

**Access observation (fact, 2026-08-20).** Two independent non-browser HTTPS requests, one for
`https://www.infosys.com/robots.txt` and one for `https://www.infosys.com/terms-of-use.html`,
each returned **HTTP 403** with an Akamai-hosted `Access Denied` body
(`errors.edgesuite.net` reference identifiers `18.8ead1cb8.1787222401.388005a` and
`18.44f4d517.1769714547.36d88dad`). The Internet Archive's stored capture of
`https://www.infosys.com/robots.txt` at timestamp `20260201062300` is itself an archived copy of
the same Akamai `Access Denied` page. **The content of `infosys.com/robots.txt` is therefore
`NOT_RETRIEVED` / `UNKNOWN`; no robots directive for this host has been observed.** This is a
technical observation about a bot-management layer, not a legal characterization and not a
disposition.

**Terms text source.** `https://www.infosys.com/terms-of-use.html`, retrieved 2026-08-20 **via the
Internet Archive snapshot `20260606173716`** because live retrieval was denied as above. The
quotations below are scoped to that snapshot; the current live text is `UNKNOWN`.

Verbatim, on scope:

> "Terms of Use for www.infosys.com, blogs.infosys.com, abm.infosys.com, and www.infosysbpm.com"

> "The use of any product, service or feature (the "Materials") available through the internet
> websites accessible at Infosys.com, blogs.ionfosys.com, abm.infosys.com, and infosysbpm.com
> (collectively, the "Website") by any user of the Website ("User" or "You" or "Your" hereafter)
> shall be governed by the following terms of use."

> "This Website is provided by Infosys Limited … and shall be used for informational purposes
> only. By using the Website or downloading Materials from the Website, You hereby agree to abide
> by the terms and conditions set forth in this Terms of Use."

> "This Website, including all Materials present (excluding any applicable third party materials),
> is the property of Infosys and Infosys retains all rights, title or interest, including all
> intellectual property laws in such Materials."

Verbatim, under the heading `LIMITED LICENSE:`:

> "Subject to the terms and conditions set forth in these Terms of Use, Infosys grants You a
> non-exclusive, non-transferable, limited copyright license to access, and display this Website
> and the Materials thereon provided you comply with these Terms of Use, and all copyright,
> trademark, and other proprietary notices remain intact."

> "You shall not modify, copy, distribute, transmit, display, perform, reproduce, publish,
> license, create derivative works from, transfer, or sell any information, software, products or
> services obtained from this Website."

> "Except for the limited permission in the preceding paragraph, Infosys does not grant you any
> express or implied rights or licenses under any patents, trademarks, copyrights, or other
> proprietary or intellectual property rights. You may not mirror any of the content from this
> site on another Web site or in any other media."

> "Any software and other materials that are made available for downloading, access, or other use
> from this site with their own license terms will be governed by such terms, conditions, and
> notices. Your failure to comply with such terms or any of the terms on this site will result in
> automatic termination of any rights granted to you, without prior notice, and you must
> immediately destroy all copies of downloaded materials in your possession, custody or control."

**Observed absence (fact).** A keyword scan of the retrieved snapshot text for `robot`, `spider`,
`scrap`, `crawl`, `automat`, `cache`, `data min`, `harvest`, and `commercial` returned **no clause
addressing automated access, crawling, scraping, caching, retention periods, or commercial use of
the Materials** other than the `LIMITED LICENSE` text quoted above. Absence of an express clause
is recorded here as an evidentiary observation only; it is **not** an inference that any operation
is permitted, and it does not change any disposition.

**Not established for this publisher:** account/registration limits, rate limits, point-in-time
availability or archival retention commitments for the FY25 quarterly documents, any replacement
path if a document URL changes, and whether any separate terms attach to the specific
`investors/reports-filings` area (the terms state that terms posted for a specific area take
precedence — the existence and content of any such area-specific terms is `UNKNOWN`).

### P2 — National Stock Exchange of India Ltd (`www.nseindia.com`) — governs CHN-01

**`robots.txt` (fact, retrieved live 2026-08-20, HTTP 200, verbatim and complete):**

```
User-agent: *
Allow: /
Disallow: /market-data-test
Sitemap: https://www.nseindia.com/sitemap.xml
```

A `robots.txt` directive is a crawler-control convention, not a grant of rights, and is recorded
here only as an observed fact.

**Terms text source.** `https://www.nseindia.com/static/nse-terms-of-use`, retrieved live
2026-08-20 (HTTP 200). The page states `Updated on: 29/10/2025`.

Verbatim:

> "These terms of use ("Terms") governs the access and use of the Website / Mobile Application. By
> accessing or using the Website / Mobile Application, you agree to be bound by these Terms and
> the Policy."

> "All information (including any real time information) or Content on the Website / Mobile
> Application is the exclusive property of NSE except the third-party content or information. …
> The Website / Mobile Application and all its content are protected by copyright, trademark, and
> other Intellectual Property Rights laws."

> "User agrees that any information or content or data on the Website / Mobile Application shall
> not be copied, modified, reverse engineer, reproduced, uploaded, transmitted, posted, stored
> (either in hardcopy or in an electronic retrieval system), adapted, altered, translated,
> disseminated, distributed, displayed, performed, broadcasted, published, hyperlinked, sold,
> marketed, licensed, rented, leased or distributed in any form, without prior written permission
> of NSE."

> "Unless the information or Content is available for download, not to aggregate, copy or
> duplicate in any manner any of the content or information which is available on Website / Mobile
> Application."

> "All rights not expressly granted herein are reserved. Unauthorised use of the data, Content or
> materials appearing on the Website / Mobile Application may violate copyright, trademark and
> other applicable laws, and could result in NSE taking strict actions against such User."

> "User is granted a non-exclusive, non-transferable, limited right to access the Website / Mobile
> Application and avail the services provided by NSE through the Website / Mobile Application."

> "User is prohibited to conduct any systematic or automated data collection activities (including
> scraping, data mining, data extraction and data harvesting) on or in relation to our Website /
> Mobile Application."

> "NSE does not permit any part of the Website / Mobile Application being cached in proxy servers
> and accessed by individuals who have not registered with Website / Mobile Application as Users."

> "The Website / Mobile Application may be used only for lawful and permitted purposes by the
> Users. NSE specifically prohibits any other use of the Website / Mobile Application, and all
> Users agree not to do any of the following: … Take any action that imposes an unreasonable or
> disproportionately large load on the Website / Mobile Application's infrastructure."

**Effect on this task's own method (fact).** Because these terms address automated collection and
caching directly and because no rights disposition existed at the time, **no automated retrieval of
NSE filing, results, or XBRL data was attempted for A-05 or A-06.** Every NSE coverage cell in A-06
that would have required such retrieval is `UNKNOWN`. `A05-DECISION-001` has since made CHN-01 a
**decided deny across `OP-02` … `OP-12`**, so no such retrieval may be attempted at all; `OP-01`
(a person reading a public NSE page) was declared out of scope rather than decided and stays
`UNKNOWN`.

**Not established for this publisher:** whether registration/account status changes any of the
above, rate or volume limits, retention/point-in-time availability of per-quarter filings, and any
replacement path. A separate NSE "Data Sharing & Usage Policy"
(`https://www.nseindia.com/static/market-data/nse-data-policy`) and a "DATA USAGE AND DATA SHARING
POLICY" PDF were surfaced by public web search but were **not retrieved**; their content is
`UNKNOWN` and the rights authority should treat them as required reading.

### P3 — BSE Limited (`www.bseindia.com`) — governs CHN-02

**`robots.txt` (fact, 2026-08-20).** `https://www.bseindia.com/robots.txt` returned **HTTP 200 but
the body is the site's single-page-application HTML shell**, not a robots directive file; the same
13,850-byte shell was returned for `static/about/website_policy.html`,
`static/about/Terms_condition.htm`, and `static/about/disclaimer.htm`. **No current robots
directive for this host has been observed; content is `NOT_RETRIEVED` / `UNKNOWN`.** An Internet
Archive snapshot at timestamp `20220430050932` does contain a directive file, reproduced verbatim
below **as a 2022 historical artifact only**; it is not evidence of the current file:

```
# robots.txt for https://www.bseindia.com/
User-agent: *
Disallow: /dropdowns/
Disallow: /bseplus/StockReach/
Disallow: /stockinfo/
Disallow: /xml-data/
Disallow: /qresann/
Disallow: /sensexview/
Disallow: /SiteCache/
Disallow: /sitecache/
Disallow: /Msource/SNPSensexData.aspx
Disallow: /Msource/IndexMovers.aspx
Sitemap : https://www.bseindia.com/sitemap.xml
```

**Disclaimer text source.** `https://www.bseindia.com/static/about/disclaimer.htm`, retrieved
2026-08-20 **via the Internet Archive snapshot `20260110180623`** because the live path returned
the SPA shell. Quotations are scoped to that snapshot.

Verbatim:

> "This website, www.bseindia.com and any other regional language websites and the Windows Store
> Apps (hereinafter referred to as "the Website") are operated by BSE Limited"

> "Any person who is accessing or has accessed any information or data from the Website
> acknowledges and agrees that all proprietary rights, statutory or otherwise, in the information
> received by such person shall remain the exclusive property of BSE. Any reproduction,
> redistribution or transmission, for consideration or otherwise, of any such information
> contained on the Website is strictly prohibited and would constitute a breach of the laws of
> India."

> "Access to any information on or through the Website is provided only on an "as is where is
> basis" and "with all faults"."

> "The contents of this Disclaimer are also applicable to BSE's regional language websites …and to
> any other facilities/tools as 'view only', 'download' or 'executable' offered through the
> Website that shall be subject to additional specified Terms and Conditions."

**Scoped adjacent terms (different host — read with care).**
`https://bseplus.bseindia.com/Terms_condition_Bseplus.htm` was retrieved live 2026-08-20
(HTTP 200). By its own text it governs **`bseplus.bseindia.com`, not `www.bseindia.com`**, so it is
recorded as adjacent publisher evidence and not as the terms for CHN-02:

> "This Agreement to Use (hereinafter referred to as "User Agreement") shall apply to all
> subscribers … As it governs your use of the site bseplus.bseindia.com, and all other URLs
> forming part thereof"

> "PERSONAL AND NON-COMMERCIAL USE LIMITATION You shall use the Site for the essential purposes
> for which the Site is intended. Unless otherwise specified, the Site is for your personal and
> non-commercial use. You may not modify, copy, distribute, transmit, display, perform, reproduce,
> publish, license, create derivative works from, transfer, or sell any information, software,
> products or services obtained from the Site."

> "However, you may print or download extracts from these pages for your personal / individual,
> non-commercial use only. You must not retain any copies of these pages saved to disk or to any
> other storage medium except for the purposes of using the same for subsequent viewing purposes
> or to print extracts for personal / individual use."

> "You may not (whether directly or through the use of any software program) create a database in
> electronic or structured manual form by regularly or systematically downloading and storing all
> or any part of the pages from this site. No part of the Site may be reproduced or transmitted to
> or stored in any other web site, nor may any of its pages or part thereof be disseminated in any
> electronic or non-electronic form, nor included in any public or private electronic retrieval
> system or service without prior written permission."

**Not established for this publisher:** the current text of `www.bseindia.com`'s own Terms of Usage
and Website Policy pages (`NOT_RETRIEVED`; both returned the SPA shell live and the Internet
Archive availability API returned HTTP 429 on every attempt during this session), current
`robots.txt`, account limits, rate limits, retention/point-in-time availability of per-quarter
filings, and any replacement path. Publicly indexed search snippets purporting to quote the BSE
website policy were seen but are **secondary, unverified against a primary page, and are
deliberately not quoted or relied on here.**

### P4 — U.S. Securities and Exchange Commission (`www.sec.gov`) — governs CHN-03

**Terms text source.**
`https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data`, retrieved live
2026-08-20 (HTTP 200). The page is dated `March 23, 2021`.

Verbatim:

> "All companies, foreign and domestic, are required to file registration statements, periodic
> reports, and other forms electronically through the U.S. Securities and Exchange Commission's
> EDGAR (Electronic Data Gathering, Analysis, and Retrieval) system. Anyone can access and download
> this information for free or query it through a variety of EDGAR public searches."

> "Fair access — Current max request rate: 10 requests/second."

> "To ensure everyone has equitable access to SEC EDGAR content, please use efficient scripting.
> Download only what you need and please moderate requests to minimize server load."

> "SEC reserves the right to limit request rates to preserve fair access for all users."

> "The SEC does not allow botnets or automated tools to crawl the site. Any request that has been
> identified as part of a botnet or an automated tool outside of the acceptable policy will be
> managed to ensure fair access for all users."

> "Please declare your user agent in request headers: Sample Declared Bot Request Headers:
> User-Agent: Sample Company Name AdminContact@<sample company domain>.com; Accept-Encoding: gzip,
> deflate; Host: www.sec.gov"

> "We do not offer technical support for developing or debugging scripted processes."

**Access observation (fact, 2026-08-20).** `https://www.sec.gov/robots.txt` returned **HTTP 403**
to a request without a declared user agent; its content is `NOT_RETRIEVED` / `UNKNOWN`. The
EDGAR company-browse index pages used for A-06 channel research were retrieved with a declared
descriptive user-agent header, at single-request rate, and returned HTTP 200. Only filing-index
metadata was read; **no filing document, exhibit, or XBRL instance was retrieved.**

**Not established for this publisher:** whether any separate terms attach to the underlying filing
documents or to third-party content within them, retention guarantees, and the treatment of
derived works. `https://www.sec.gov/about/developer-resources`, the SEC "Internet Security Policy"
referenced by the fair-access text, and the EDGAR API terms were **not retrieved**; their content
is `UNKNOWN`.

## Decision form for the source-rights authority

The Implementer may not answer any of this form. Each answer must be made by the competent
source-rights authority (with legal review where that authority requires it), must be
independently scoped per operation, must name the decider and decision date, and must cite the
exact evidence version it was made against. A missing, ambiguous, stale, wrong-authority, or
broader-than-evidence answer is recorded as `UNKNOWN` and stays denied.

**Status after `A05-DECISION-001`** (product owner, 2026-08-20, decided against
`a-05-source-rights-package.json@1.0.0`
`sha256:b6881bca7167b7ff4a5ffdcaf31a3a7871f2baa0997289ca3ac55a70844579e2` and
`a-05-source-rights-package.md@1.1.0` record digest
`sha256:161196a3c4258b0311fad97320a903365bad7159a3e6d83b184afca7d55e483d`):

| Item | Status | What was decided |
|---|---|---|
| D-1 | **partially answered** | 107 of 132 cells carry `ALLOWED` or `DENIED` with rationale, term relied on, conditions, scope boundary, and invalidating events via `decision_bases`. The remaining 25 stay `UNKNOWN`: `OP-04` and `OP-11` for SRC-01 … SRC-08; `OP-03 … OP-08`, `OP-11`, and `OP-12` for CHN-03, where the decider spoke to access only; and `OP-01` for CHN-01, declared out of scope rather than decided. |
| D-2 | **partially answered** | Answered: terms currency — the decider expressly accepted the 2026-06-06 Wayback snapshot of the Infosys terms as the decision basis with the risk stated; automated access for every publisher; and, **for P1 Infosys only**, retention, derived outputs, and machine and LLM processing; redistribution for P1 and P4. Not answered: retention, derived outputs, and machine processing for **P4 SEC**, where the decider spoke to access only; caching; commercial use; accounts and credentials; and whether the unretrieved instruments must be obtained before any wider disposition. |
| D-3 | **not answered** | No point-in-time availability commitment, archival-copy designation, or replacement path. A local retained copy with SHA-256 digests now exists per the authorized retrieval manifest, but that is a fact, not a commitment. |
| D-4 | **not answered** | The content-digest gate was neither confirmed nor rejected. Its precondition is now satisfied for SRC-01 … SRC-08, since `OP-01`, `OP-02`, and `OP-03` are `ALLOWED` there and digests are recorded in the manifest. |
| D-5 | **answered** | CHN-03 (SEC EDGAR) is **added** to the source list, with automated access allowed inside SEC fair-access limits and the same internal-only output boundary. **Access only (`OP-01`/`OP-02`)**: retention, processing, and the other operations (`OP-03 … OP-08`, `OP-11`, `OP-12`) remain `UNKNOWN`, and redistribution (`OP-09`, `OP-10`) is `DENIED`. |
| D-6 | **answered** | The source-rights authority is the product owner, **PavanMV (mvpavan42@gmail.com), self-assumed**. No legal credential is claimed and **no legal review was performed or obtained**. No review cadence was set; each basis states the events that invalidate it. |

### D-1 — Per source, per operation (132 decisions) — *partially answered*

For **each** of `SRC-01 … SRC-08`, `CHN-01`, `CHN-02`, `CHN-03` and **each** of `OP-01 … OP-12`,
supply exactly one of `ALLOWED`, `DENIED`, or `UNKNOWN`, plus:

1. The rationale and the exact term, licence, or instrument relied on.
2. Any condition, volume limit, rate limit, or attribution requirement attached.
3. The scope boundary: does the answer cover only the A-01 private/internal mode?
4. Expiry or review date, and what event invalidates it.

### D-2 — Per publisher (P1 Infosys, P2 NSE, P3 BSE, P4 SEC) — *partially answered*

1. **Terms currency.** Is the terms text quoted above the operative version? For P1 and P3 the
   quotations come from Internet Archive snapshots because live retrieval failed — does the
   authority accept snapshot-sourced terms as its decision basis, or must the live text be obtained
   by another means first?
2. **Unretrieved instruments.** Are the following required before any disposition, and who obtains
   them: `infosys.com/robots.txt` (denied to automated clients); any Infosys area-specific terms
   for `investors/reports-filings`; NSE's Data Sharing & Usage Policy and Data Usage and Sharing
   Policy; BSE's current Terms of Usage, Website Policy, and `robots.txt`; SEC's Internet Security
   Policy, Developer Resources, and EDGAR API terms?
3. **Automated access.** Given the observed Akamai denial on `infosys.com`, NSE's clause on
   systematic and automated data collection, the 2022-only BSE robots snapshot, and SEC's declared
   user-agent and 10 requests/second fair-access statements — is `OP-02` permitted for this
   publisher, and under what exact constraints?
4. **Caching and retention.** Is `OP-03`/`OP-04` permitted, for how long, in which store, and does
   it extend to a program archive used for reconstructing Q0 evidence?
5. **Derived outputs.** Is `OP-07` permitted, and does the permission extend to quantitative
   values extracted from the source, to close paraphrase, and to reproduction of quoted management
   language in an internal memo?
6. **Machine processing.** Is `OP-08` permitted, including submission of source content to an
   LLM or third-party processor, and does any restriction on third-party transmission apply?
7. **Internal redistribution.** Is `OP-09` permitted, to which internal recipient classes, and does
   a "personal / individual use" limitation (where present) preclude organizational internal use?
8. **Accounts and credentials.** Do any of these channels require registration, and does registered
   status change any answer? (No account, credential, or provider is selected by this record.)

### D-3 — Point-in-time availability and replacement path — *not answered*

For each of `SRC-01 … SRC-08`: is the exact document URL committed to remain available, is there
an authoritative archival copy, and what is the replacement path if it moves or is withdrawn?
All currently `UNKNOWN`.

### D-4 — Content digest gate — *not answered*

`OP-12` requires holding source bytes. Until `OP-01`/`OP-02` **and** `OP-03` are independently
`ALLOWED` for a given source, the S1 `source_content_digest_state` for that source stays `UNKNOWN`.
Confirm or reject this gate.

### D-5 — CHN-03 scope question — *answered*

`CHN-03` (SEC EDGAR) is **not** in the S1 inventory. Decide explicitly whether it is added to the
selected source package, kept out of scope, or deferred.

**Answered by `A05-DECISION-001` (2026-08-20):** CHN-03 is **added** to the source list, with
access allowed inside the SEC's published fair-access limits (`OP-01`, `OP-02`) and the same
internal-only output boundary. The decider spoke to **access only**, so `OP-03`, `OP-04`, `OP-05`,
`OP-06`, `OP-07`, `OP-08`, `OP-11`, and `OP-12` are **not** inferred and stay `UNKNOWN`.

### D-6 — Authority identification — *answered*

Name the source-rights authority (role and identifiable individual), state whether legal review is
required for these decisions, and state the review cadence.

**Answered by `A05-DECISION-001` (2026-08-20):** the source-rights authority is **the product
owner, PavanMV (mvpavan42@gmail.com), self-assumed**. **No legal credential is claimed or recorded
and no legal review was performed or obtained.** No review cadence was set; each entry in
`decision_bases` states the events that invalidate it.

## Downstream effect while this record stands

- A-06 (`docs/evidence/phase-0a/a-06-filing-coverage-spike.md` and
  `docs/evidence/phase-0a/a-06-filing-coverage-matrix.csv`) was produced **before**
  `A05-DECISION-001`, when no operation was `ALLOWED`. It is therefore built from publicly
  retrievable **channel metadata and regulatory documents only**, and every coverage cell that
  would have required a source-package operation is `UNKNOWN`. This record does not amend it.
- Plan Task 5 (Q0 manual baseline) **may now proceed against SRC-01 … SRC-08**, within
  `DB-01-INFY-INTERNAL-ALLOW` and its limits. Re-reading the already-retained local copies under
  `data/raw/infy-fy25/` is `OP-03` retention plus internal processing, **not** `OP-04` caching.
  CHN-03 is **access-only** under `DB-04-SEC-FAIR-ACCESS-ALLOW`: nothing retrieved from SEC EDGAR
  may yet be retained, extracted, transformed, machine-processed, captured, or hashed. Nothing may
  be produced for public output.
- Nothing here authorizes Phase 0.5 execution, external modes, paid modes, personalized modes, or
  execution-linked modes; A-01 independently prohibits those.
- S1 source-content digests in `source-package-inventory.json` remain `UNKNOWN`, unchanged by this
  record; the digests of the retrieved bytes are recorded separately in
  `docs/evidence/phase-0a/a-05-retrieval-manifest-infy-fy25.json`.

## Record digest convention and payload

This record uses the non-self-referential SHA-256 convention stated in A-01: UTF-8 canonical JSON
with recursively sorted object keys, preserved array order, no whitespace or byte-order mark, and
every `record_digest` field excluded from the digest input. No source-content bytes are included.

The companion machine artifact is bound by its own file digest inside the payload, so a change to
the JSON invalidates this record digest.

```json
{"artifact_id":"A-05","author_role":"bounded implementer (recording agent, not the decision maker)","boundary_ref":"docs/evidence/phase-0a/a-01-initial-boundary-decision.md","cells_allowed":66,"cells_denied":41,"cells_unknown_denied_by_default":25,"decision_form_open":true,"decision_items_answered":{"D-1":"partial","D-2":"partial","D-3":"no","D-4":"no","D-5":"yes","D-6":"yes"},"disposition_cells_total":132,"disposition_value_set":["ALLOWED","DENIED","UNKNOWN (denied by default)"],"document_version":"1.2.0","evidence_access_date":"2026-08-20","held_pending_q0_review":["Screener.in","Tijori","aeron7/nsepython","BennyThadikaran/NseIndiaApi","BennyThadikaran/BseIndiaApi","RuchiTanmay/nselib","LaZZy0v0/tijori-finance-mcp","jugaad-py/jugaad-data","VishwaGauravIn/screener-scraper-pro","MrChartist/fii-dii-data","Tapetide-hq/nse-bse-indian-stock-market-data-mcp","NSEDownload/NSEDownload","thisisamu/fii-dii-analysis"],"inventory_ref":"docs/evidence/phase-0a/source-package-inventory.json","inventory_source_use_pairs":24,"not_held_still_candidate_undecided":["Fincept-Corporation/FinceptTerminal","stefan-jansen/machine-learning-for-trading","Na1neeth/openscreener"],"operations":["OP-01","OP-02","OP-03","OP-04","OP-05","OP-06","OP-07","OP-08","OP-09","OP-10","OP-11","OP-12"],"retrieval_manifest_path":"docs/evidence/phase-0a/a-05-retrieval-manifest-infy-fy25.json","retrieval_manifest_sha256":"0394c9ab53b7bde341ad38200ea0cf30565888fe700fcfd84d7840751b966d28","rights_authority_record":"A05-DECISION-001 — docs/evidence/phase-0a/a-05-rights-decision-record.md; source-rights authority is the product owner PavanMV (mvpavan42@gmail.com), self-assumed; no legal credential claimed and no legal review performed","rights_decision_record_digest":"sha256:3f71a7c0dee75f33d5f9fb132803795b3a88cb2a0873dc9e69b7a38f57deb816","rights_decision_record_id":"A05-DECISION-001","rights_decision_record_path":"docs/evidence/phase-0a/a-05-rights-decision-record.md","rights_package_json_path":"docs/evidence/phase-0a/a-05-source-rights-package.json","rights_package_json_sha256":"43f6aca5a35c79fc4bbc3a02c7e997944971fc4d880ac066f26ed95efcd1a246","source_bytes_committed_to_repository":false,"source_bytes_held_SRC-01_to_SRC-08":true,"source_content_digest_state":"UNKNOWN in the unamended S1 inventory; digests of the retrieved bytes are recorded in the authorized retrieval manifest","source_content_fetched":true,"sources":["SRC-01","SRC-02","SRC-03","SRC-04","SRC-05","SRC-06","SRC-07","SRC-08","CHN-01","CHN-02","CHN-03"],"status":"PARTIALLY_DECIDED_REMAINDER_PENDING","terms_retrieval_status":{"bseindia.com":"PARTIAL_ARCHIVE_SNAPSHOT_20260110_DISCLAIMER_ONLY","infosys.com":"ARCHIVE_SNAPSHOT_20260606_LIVE_403","nseindia.com":"LIVE_20260820","sec.gov":"LIVE_20260820"}}
```

**Record digest:** `sha256:9fa1b5b6d6c399f8d8730a0f819510146c6f85ed7006d9461a2d2ecc4076fe63`
(v1.1.0 digest, preserved:
`sha256:161196a3c4258b0311fad97320a903365bad7159a3e6d83b184afca7d55e483d`; v1.0.0 digest, preserved:
`sha256:6880c2a1be13a80390c45567d78eb25707cfc61281f0b76f1e09a556346c975e`)

## Authorities and references

- `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` — A-05 clause and Phase 0A gate.
- `docs/plans/2026-08-19-phase-0a-evidence-program.md` — Task 2 scope, fail-closed semantics.
- `docs/evidence/phase-0a/a-05-source-rights-package.json` — the machine form of this record (24 exact inventory source/use pairs plus the 132-cell normalized grid).
- `docs/evidence/phase-0a/a-05-rights-decision-record.md` — `A05-DECISION-001`, the product-owner source-rights decision transcribed into this record.
- `docs/evidence/phase-0a/a-05-retrieval-manifest-infy-fy25.json` — URLs, byte counts, and SHA-256 digests of the eight documents retrieved under that decision on 2026-08-20.
- `docs/research/external-tools-and-repos-inventory.md` — section 6 lists the candidate wrapper libraries held and denied by that decision.
- `docs/evidence/phase-0a/source-package-inventory.json` — the exact source list bound here.
- `docs/evidence/phase-0a/a-01-initial-boundary-decision.md` — private/internal boundary; not a rights decision.
- `docs/evidence/phase-0a/a-02-discovery-slice-selection.md` — selected slice and recorded exchange channels.
- `https://www.infosys.com/terms-of-use.html` — accessed 2026-08-20 via Internet Archive snapshot `20260606173716` (live: HTTP 403).
- `https://www.nseindia.com/static/nse-terms-of-use` — accessed live 2026-08-20; page states `Updated on: 29/10/2025`.
- `https://www.nseindia.com/robots.txt` — accessed live 2026-08-20.
- `https://www.bseindia.com/static/about/disclaimer.htm` — accessed 2026-08-20 via Internet Archive snapshot `20260110180623` (live: SPA shell).
- `https://bseplus.bseindia.com/Terms_condition_Bseplus.htm` — accessed live 2026-08-20; governs `bseplus.bseindia.com` only.
- `https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data` — accessed live 2026-08-20; page dated March 23, 2021.
