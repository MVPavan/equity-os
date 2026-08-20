# A-06 Filing-Channel Coverage Spike — Infosys Q1–Q4 FY25

**Record version:** 1.1.0
**Status:** RECORDED — factual channel research; every cell is a cited fact, `UNKNOWN`, `ABSENT`, or `NOT_APPLICABLE`. **Not a coverage-acceptance decision, not a source-rights decision, not a provider or parser selection.**
**Recorded at:** 2026-08-20 (v1.0.0); amended 2026-08-20 (v1.1.0 — conformed to the approved plan file map; matrix extracted to CSV)
**Author:** bounded implementer (recording agent, not the decision maker)
**Stage / bead:** S2 `eqos-3ps.2`, plan Task 3 (`docs/plans/2026-08-19-phase-0a-evidence-program.md`)

## Artifact pair

This document is the `FilingCoverageSpike` narrative required by the plan's file map: method, source
references, observed mapping stability, reconciliation observations, conflicts, and per-quarter
gaps. The machine-readable `FilingCoverageMatrix` is
**`docs/evidence/phase-0a/a-06-filing-coverage-matrix.csv`**, one row per
(channel × program quarter × dimension).

The CSV is **derived mechanically from the four quarter tables in this document**, so the two
cannot drift: every CSV row's `state` and `cell_text` come from the corresponding markdown cell.
The CSV file digest is bound into this record's digest payload below.

## Scope

| Program quarter | Issuer quarter | Quarter ended | Role (A-02) |
|---|---|---|---|
| Q0 | Infosys Q1 FY25 | 2024-06-30 | Manual baseline / bootstrap thesis |
| Q1 | Infosys Q2 FY25 | 2024-09-30 | Assisted incremental update |
| Q2 | Infosys Q3 FY25 | 2024-12-31 | Assisted incremental update |
| Q3 | Infosys Q4 FY25 | 2025-03-31 | Assisted incremental update |

Company: **Infosys Ltd**. Indian listings NSE `INFY` / BSE scrip code `500209`; U.S. listing of
American Depositary Shares under `INFY`, SEC registrant CIK `0001067491`, Exchange Act file number
`001-35754`, fiscal year end `0331` (EDGAR company header, accessed 2026-08-20).

## Method, and why so many cells are `UNKNOWN`

This record was produced **under a fail-closed rights posture**. `docs/evidence/phase-0a/a-05-source-rights-package.md`
records **132 source×operation disposition cells, all `UNKNOWN (denied by default)`**, and no
source-rights authority record exists. Plan Task 3 permits consuming only operations marked
`ALLOWED`; there are none.

Consequently:

- **No source-package content was retrieved, opened, parsed, or hashed** — no quarterly results
  PDF, transcript, press release, or XBRL instance. Every dimension whose answer lives *inside* a
  filing document is therefore `UNKNOWN`, not guessed.
- **No automated retrieval of NSE or BSE filing/results/XBRL data was attempted.** The NSE Terms of
  Use retrieved 2026-08-20 state that a user "is prohibited to conduct any systematic or automated
  data collection activities (including scraping, data mining, data extraction and data
  harvesting)"; with no rights disposition in place, no such retrieval was performed. Cells that
  would have required it are `UNKNOWN` with the attempt recorded.
- **No stable per-quarter XBRL deep link is invented.** Where the shortlist recorded a data gap, it
  stays a data gap.
- Facts sourced from `docs/research/phase-0a-discovery-company-shortlist.md` carry that record's
  retrieval date of **2026-08-19** and are marked `[repo-recorded]`. Facts obtained during this
  task carry **2026-08-20** and are marked `[verified 2026-08-20]`.
- Live re-verification of `www.infosys.com` was attempted on 2026-08-20 and returned **HTTP 403**
  from an Akamai bot-management layer for both `/robots.txt` and `/terms-of-use.html`. Issuer-site
  facts are therefore `[repo-recorded]` and **were not re-verified live**.

## State vocabulary (kept distinct)

| State | Meaning |
|---|---|
| *cited fact* | Established by a named source with a retrieval date, stated inline. |
| `UNKNOWN` | Not established by this pass. Each occurrence carries a note of what was attempted or what is blocking. Never a synonym for "none". |
| `ABSENT` | The channel **was** examined and the item is observably not present there. |
| `NOT_APPLICABLE` | The dimension does not apply to this channel/quarter by construction (e.g. a taxonomy version where no structured artifact exists, or quarter-level reporting from an annual-only form). |

## Channel register

| Channel | Description | Channel-level facts |
|---|---|---|
| `CH-ISSUER` | Infosys investor-relations site, `www.infosys.com/investors/reports-filings/quarterly-results/2024-2025/` | `[repo-recorded]` A per-quarter results-and-auditors'-reports PDF exists for all four FY25 quarters, plus management transcripts and an IFRS USD press release; exact URLs and document dates are in `docs/evidence/phase-0a/source-package-inventory.json`. `[verified 2026-08-20]` Non-browser HTTPS requests to this host return HTTP 403 (Akamai `Access Denied`). |
| `CH-NSE` | NSE Financial Results and Integrated Filing–Financial channels | `[repo-recorded]` The NSE Financial Results search page exposes company/period filters, CSV download, an XBRL column, and "Convert XBRL into Excel"; the Integrated Filing–Financial page exposes quarter-ending filters, CSV download, and XBRL-to-Excel conversion. `[repo-recorded]` NSE circular dated 2025-04-02 states that listed entities submit Integrated Filing–Financial in XBRL and separately submit the board-meeting financial-results PDF. |
| `CH-BSE` | BSE company results endpoint, scrip code `500209` | `[repo-recorded]` The BSE company financial-results endpoint exposes filing date/time plus standalone and consolidated XBRL columns; the Infosys search page is `https://www.bseindia.com/corporates/Comp_Results.aspx?Code=500209`. |
| `CH-SEC-6K` | SEC EDGAR Form 6-K (foreign private issuer report) | `[verified 2026-08-20]` EDGAR company-browse listing for CIK `0001067491` shows 6-K submissions on 2024-07-18, 2024-10-17, 2025-01-16 and 2025-04-17 — the same dates as the four issuer results releases. Every 6-K row shows only `Documents` in the Format column. |
| `CH-SEC-20F` | SEC EDGAR Form 20-F (annual report of foreign private issuer) | `[verified 2026-08-20]` The FY25 annual report (fiscal year ended 2025-03-31) was filed 2025-07-01, accession `0000950170-25-091925`; its Format column shows `Documents` **and** `Interactive Data`. The prior-year 20-F was filed 2024-06-24, accession `0000950170-24-076649`, also with `Interactive Data`. |

**`CH-SEC-6K` and `CH-SEC-20F` are not in the S1 source-package inventory.** They appear here as
channel research only. A-05 decision item `D-5` asks the rights authority to decide explicitly
whether SEC EDGAR enters the source package.

## Regulatory framework facts bearing on this window

`[verified 2026-08-20]` SEBI circular **`SEBI/HO/CFD/CFD-PoD-2/CIR/P/2024/185`, dated December 31,
2024** ("Implementation of recommendations of the Expert Committee for facilitating ease of doing
business for listed entities"), retrieved from
`https://www.sebi.gov.in/legal/circulars/dec-2024/circular-for-implementation-of-recommendations-of-the-expert-committee-for-facilitating-ease-of-doing-business-for-listed-entities_90406.html`
and its attached PDF, states verbatim:

> "In order to facilitate ease of filing and compliance for listed entities, it has been decided to
> introduce Integrated Filing, in terms of regulation 10(1A) of the LODR Regulations, for the
> following Governance and Financial related periodic filings required under the LODR, which shall
> be applicable for the filings to be done for the quarter ending 31st December 2024 and thereafter"

> "The timeline for quarterly Integrated Filing shall be as follows: a. Integrated Filing
> (Governance): within 30 days from the end of the quarter; b. Integrated Filing (Financial):
> within 45 days from the end of the quarter, other than the last quarter, and 60 days from the end
> of the last quarter and the financial year. In this regard, the first quarterly Integrated Filing
> i.e., Integrated Filing (Governance) and Integrated Filing (Financial) which is applicable for the
> quarter ending December 31, 2024, may be filed within a period of 45 days from the end of the
> quarter."

The circular's table places **"33(3) Financial results"** inside Integrated Filing (Financial).

`[verified 2026-08-20]` A keyword scan of the full extracted circular text found **no occurrence of
"XBRL"**. The XBRL requirement for Integrated Filing–Financial is asserted by the NSE circular of
2025-04-02 as `[repo-recorded]` in the shortlist, **not** by this SEBI circular. This distinction
matters and is preserved.

**Consequence for the selected window:** program Q0 (quarter ended 2024-06-30) and Q1 (quarter
ended 2024-09-30) precede the Integrated Filing regime; program Q2 (quarter ended 2024-12-31) is the
**first** Integrated Filing quarter; program Q3 (quarter ended 2025-03-31) is the **first last-quarter
/ full-year** Integrated Filing, on the 60-day timeline. The exchange filing framework therefore
changes **inside** the four-quarter slice.

## Dimensions

`D1` filing-channel availability · `D2` structured/XBRL availability · `D3` taxonomy and version ·
`D4` statement-level coverage · `D5` segment data · `D6` notes and accompanying disclosures ·
`D7` ownership / share-count data · `D8` restatement and revision behavior · `D9` mapping stability
versus the prior quarter · `D10` point-in-time retention and stable deep link ·
`D11` estimated reconciliation effort.

`D11` is `UNKNOWN` in every cell. An effort estimate requires either rights-permitted access to the
documents or an analyst judgement; neither exists. **The recording agent does not supply an
estimate.** This is the same fail-closed treatment the plan requires for coverage acceptance.

---

## Q0 — Infosys Q1 FY25, quarter ended 2024-06-30

| Dim | `CH-ISSUER` | `CH-NSE` | `CH-BSE` | `CH-SEC-6K` | `CH-SEC-20F` |
|---|---|---|---|---|---|
| D1 | *cited fact* `[repo-recorded]` Results-and-auditors'-reports PDF dated 2024-07-18 and press-conference transcript PDF are recorded at issuer URLs in the S1 inventory. Not re-verified live (HTTP 403). | *cited fact* `[repo-recorded]` Financial Results search channel exists. Presence of the specific INFY Q1 FY25 filing on it: `UNKNOWN` — no automated retrieval attempted. | *cited fact* `[repo-recorded]` Company results endpoint for code 500209 exists. Presence of the specific filing: `UNKNOWN` — no automated retrieval attempted. | *cited fact* `[verified 2026-08-20]` 6-K submitted 2024-07-18, accession `0001067491-24-000024`. | `NOT_APPLICABLE` — annual form; no quarter-level submission exists for this quarter. |
| D2 | `UNKNOWN` — no XBRL artifact on the issuer site was established; the shortlist records this as a data gap and no document was retrieved. | `UNKNOWN` — pre-Integrated-Filing quarter; whether an Ind AS XBRL results file for INFY exists and is retrievable here was **not** verified (no automated retrieval). | `UNKNOWN` — the endpoint exposes standalone/consolidated XBRL columns `[repo-recorded]`, but whether a file exists for this quarter was **not** verified. | `ABSENT` — `[verified 2026-08-20]` the EDGAR listing shows only `Documents` for this 6-K row, with no `Interactive Data`. | `NOT_APPLICABLE` |
| D3 | `UNKNOWN` — dependent on D2. | `UNKNOWN` — taxonomy family and version not established. | `UNKNOWN` — taxonomy family and version not established. | `NOT_APPLICABLE` — no structured artifact present. | `NOT_APPLICABLE` |
| D4 | `UNKNOWN` — document not opened (no rights disposition). | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` — filing documents not retrieved; only the index listing was read. | `NOT_APPLICABLE` |
| D5 | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `NOT_APPLICABLE` |
| D6 | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `NOT_APPLICABLE` |
| D7 | `UNKNOWN` | `UNKNOWN` — shareholding-pattern filings are a separate LODR channel; not examined. | `UNKNOWN` — same. | `UNKNOWN` | `NOT_APPLICABLE` |
| D8 | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `NOT_APPLICABLE` |
| D9 | `NOT_APPLICABLE` — Q0 is the first quarter in the slice; there is no prior quarter inside scope. | `NOT_APPLICABLE` | `NOT_APPLICABLE` | `NOT_APPLICABLE` | `NOT_APPLICABLE` |
| D10 | `UNKNOWN` — no retention or URL-stability commitment established; live access to the host was denied to automated clients on 2026-08-20. | `UNKNOWN` — `[repo-recorded]` no stable per-company per-quarter XBRL file URL was established. | `UNKNOWN` — same. | `UNKNOWN` — EDGAR accession numbers are recorded above, but no retention statement was retrieved. | `NOT_APPLICABLE` |
| D11 | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `NOT_APPLICABLE` |

## Q1 — Infosys Q2 FY25, quarter ended 2024-09-30

| Dim | `CH-ISSUER` | `CH-NSE` | `CH-BSE` | `CH-SEC-6K` | `CH-SEC-20F` |
|---|---|---|---|---|---|
| D1 | *cited fact* `[repo-recorded]` Q2-and-H1 results-and-auditors'-reports PDF dated 2024-10-17 and press-conference transcript PDF recorded at issuer URLs. Not re-verified live. | *cited fact* `[repo-recorded]` channel exists; specific filing presence `UNKNOWN`. | *cited fact* `[repo-recorded]` endpoint exists; specific filing presence `UNKNOWN`. | *cited fact* `[verified 2026-08-20]` 6-K submitted 2024-10-17, accession `0001067491-24-000032`. | `NOT_APPLICABLE` |
| D2 | `UNKNOWN` — as Q0. | `UNKNOWN` — pre-Integrated-Filing quarter; Ind AS XBRL availability for INFY **not confirmed**. | `UNKNOWN` — **not confirmed**. | `ABSENT` — `[verified 2026-08-20]` no `Interactive Data` on this 6-K row. | `NOT_APPLICABLE` |
| D3 | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `NOT_APPLICABLE` | `NOT_APPLICABLE` |
| D4 | `UNKNOWN` — half-year statements are expected in a Q2 filing under LODR 33(3)(f), but this was not verified against the document. | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `NOT_APPLICABLE` |
| D5 | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `NOT_APPLICABLE` |
| D6 | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `NOT_APPLICABLE` |
| D7 | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `NOT_APPLICABLE` |
| D8 | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `NOT_APPLICABLE` |
| D9 | `UNKNOWN` — document-naming continuity across quarters is recorded in the shortlist as an **inference**, not a verified mapping-stability fact. | *cited fact* `[verified 2026-08-20]` No exchange filing-framework change applies to this quarter: the Integrated Filing regime begins with the quarter ending 2024-12-31 (SEBI circular 185). Field-level mapping stability remains `UNKNOWN`. | *cited fact* — same regulatory position as `CH-NSE`; field-level mapping stability `UNKNOWN`. | `UNKNOWN` — 6-K content not examined. | `NOT_APPLICABLE` |
| D10 | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `NOT_APPLICABLE` |
| D11 | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `NOT_APPLICABLE` |

## Q2 — Infosys Q3 FY25, quarter ended 2024-12-31

| Dim | `CH-ISSUER` | `CH-NSE` | `CH-BSE` | `CH-SEC-6K` | `CH-SEC-20F` |
|---|---|---|---|---|---|
| D1 | *cited fact* `[repo-recorded]` Q3-and-9M results-and-auditors'-reports PDF dated 2025-01-16 and earnings-call transcript PDF recorded at issuer URLs. Not re-verified live. | *cited fact* `[repo-recorded]` channel exists; **`[verified 2026-08-20]`** this is the first quarter for which Integrated Filing (Financial) applies. Specific filing presence `UNKNOWN`. | *cited fact* — same as `CH-NSE`; specific filing presence `UNKNOWN`. | *cited fact* `[verified 2026-08-20]` 6-K submitted 2025-01-16, accession `0001067491-25-000002`. | `NOT_APPLICABLE` |
| D2 | `UNKNOWN` | `UNKNOWN` — the Integrated Filing regime applies from this quarter and NSE's 2025-04-02 circular `[repo-recorded]` states Integrated Filing–Financial is submitted in XBRL, but **whether an Ind AS XBRL artifact for INFY for this quarter exists and is retrievable was not verified.** | `UNKNOWN` — same. | `ABSENT` — `[verified 2026-08-20]` no `Interactive Data` on this 6-K row. | `NOT_APPLICABLE` |
| D3 | `UNKNOWN` | `UNKNOWN` — the SEBI circular text contains **no** occurrence of "XBRL" `[verified 2026-08-20]`; taxonomy family and version are established by neither this circular nor any page retrieved in this pass. | `UNKNOWN` | `NOT_APPLICABLE` | `NOT_APPLICABLE` |
| D4 | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `NOT_APPLICABLE` |
| D5 | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `NOT_APPLICABLE` |
| D6 | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `NOT_APPLICABLE` |
| D7 | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `NOT_APPLICABLE` |
| D8 | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `NOT_APPLICABLE` |
| D9 | `UNKNOWN` | *cited fact* `[verified 2026-08-20]` **Framework discontinuity inside the slice.** SEBI circular 185 introduces Integrated Filing "applicable for the filings to be done for the quarter ending 31st December 2024 and thereafter", with LODR 33(3) financial results inside Integrated Filing (Financial) and a 45-day timeline. Field-level mapping impact on INFY's filings is `UNKNOWN`. | *cited fact* — same discontinuity; field-level impact `UNKNOWN`. | `UNKNOWN` | `NOT_APPLICABLE` |
| D10 | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `NOT_APPLICABLE` |
| D11 | `UNKNOWN` | `UNKNOWN` — a regime change mid-slice is a recognized reconciliation risk, but no effort figure is supplied by the recording agent. | `UNKNOWN` | `UNKNOWN` | `NOT_APPLICABLE` |

## Q3 — Infosys Q4 FY25, quarter and year ended 2025-03-31

| Dim | `CH-ISSUER` | `CH-NSE` | `CH-BSE` | `CH-SEC-6K` | `CH-SEC-20F` |
|---|---|---|---|---|---|
| D1 | *cited fact* `[repo-recorded]` Q4-and-12M results-and-auditors'-reports PDF dated 2025-04-17 and IFRS USD press-release PDF recorded at issuer URLs. Not re-verified live. | *cited fact* `[repo-recorded]` channel exists; **`[verified 2026-08-20]`** last-quarter/full-year Integrated Filing (Financial) applies on a 60-day timeline. Specific filing presence `UNKNOWN`. | *cited fact* — same; specific filing presence `UNKNOWN`. | *cited fact* `[verified 2026-08-20]` 6-K submitted 2025-04-17, accession `0001067491-25-000008`. | *cited fact* `[verified 2026-08-20]` Annual report on Form 20-F for the fiscal year ended 2025-03-31 filed 2025-07-01, accession `0000950170-25-091925`. |
| D2 | `UNKNOWN` | `UNKNOWN` — **not confirmed** for this quarter. | `UNKNOWN` — **not confirmed** for this quarter. | `ABSENT` — `[verified 2026-08-20]` no `Interactive Data` on this 6-K row. | *cited fact* `[verified 2026-08-20]` The EDGAR listing shows `Interactive Data` for this 20-F, i.e. a structured XBRL exhibit is present. **Scope caveat:** annual, not quarter-level. |
| D3 | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `NOT_APPLICABLE` | `UNKNOWN` — the presence of Interactive Data was observed from the index listing; the taxonomy family (IFRS vs. other) and version were **not** established, because no filing document or XBRL instance was retrieved. |
| D4 | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` — annual statements are expected in a 20-F but were not verified; quarter-level (Jan–Mar 2025) isolation from an annual filing is `NOT_APPLICABLE` by construction. |
| D5 | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` |
| D6 | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` |
| D7 | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` |
| D8 | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` |
| D9 | `UNKNOWN` | *cited fact* `[verified 2026-08-20]` Second framework transition inside the slice: the last quarter and financial year move to the 60-day Integrated Filing (Financial) timeline. Field-level mapping impact `UNKNOWN`. | *cited fact* — same; field-level impact `UNKNOWN`. | `UNKNOWN` | `UNKNOWN` — comparability between an Indian-GAAP-family quarterly filing and an IFRS annual 20-F is a known reconciliation question and was not examined. |
| D10 | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` |
| D11 | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` |

**Cell count:** 11 dimensions × 5 channels × 4 program quarters = **220 cells**, each exactly one of
cited fact, `UNKNOWN`, `ABSENT`, or `NOT_APPLICABLE`. The same 220 cells are the 220 data rows of
`docs/evidence/phase-0a/a-06-filing-coverage-matrix.csv`.

## Tier framing

- **Tier 1 — official structured/XBRL, evaluated first.** Candidate Tier 1 artifacts are the
  exchange Integrated Filing / financial-results XBRL on `CH-NSE` and `CH-BSE`, and the SEC 20-F
  Interactive Data exhibit on `CH-SEC-20F`. **Tier 1 is currently unproven for every program
  quarter at quarter grain.** The single confirmed structured artifact in this window
  (`CH-SEC-20F`, FY ended 2025-03-31) is annual, so it cannot serve quarter-level Q0–Q2
  measurement at all and covers Q3 only as part of a full year.
- **Tier 2 — official unstructured (issuer PDFs), only for demonstrated Tier 1 gaps.** The S1
  inventory is entirely Tier 2. Because Tier 1 is unproven rather than demonstrated-absent, the
  Tier 1 gap that would justify Tier 2 use is **not yet demonstrated** — it is `UNKNOWN`. Tier 2
  use also remains blocked by A-05.
- **Tier 3 — licensed vendor data.** Out of scope now. Recorded only as a possible future
  reconciliation cross-check. A Tier 3 item may never become primary, fill an official-source gap,
  or win a conflict by origin, and would require its own separate licence and rights disposition.

## Per-quarter gaps (no aggregate score)

**Q0 (quarter ended 2024-06-30).** Structured/XBRL availability on both Indian exchanges is
unconfirmed. SEC structured data is `ABSENT` for the corresponding 6-K. All in-document dimensions
(D4–D8) are unresolved. No prior-quarter mapping comparison is possible inside the slice.

**Q1 (quarter ended 2024-09-30).** Same structured-data position as Q0. Additional unresolved
question: whether the Q2/H1 filing's half-year statements change the statement set relative to Q0.

**Q2 (quarter ended 2024-12-31).** First Integrated Filing quarter — a **verified framework
discontinuity inside the selected slice**. Whether this changes the exchange artifact set, the
XBRL taxonomy, or field mappings for Infosys is unresolved. This is the highest-risk quarter for
mapping stability in the window.

**Q3 (quarter ended 2025-03-31).** Second transition (last-quarter/annual Integrated Filing, 60-day
timeline). The only confirmed structured artifact in the whole window sits here but is annual and
on a different reporting framework and channel from the Indian quarterly filings, so using it
introduces a framework-reconciliation question rather than resolving the quarterly gap.

**Cross-quarter.** No stable, per-company, per-quarter public XBRL file URL has been established
for any quarter on any Indian channel. Point-in-time retention is unestablished everywhere. No
restatement or revision behavior has been observed on any channel.

## What would resolve the principal `UNKNOWN`s

Each item below is listed as a prerequisite, not as an authorization or a recommendation to act.

1. **A-05 dispositions.** Until a competent source-rights authority independently marks specific
   source×operation pairs `ALLOWED`, no document-interior dimension (D4–D8) can move off `UNKNOWN`.
2. **Ind AS XBRL confirmation on `CH-NSE` / `CH-BSE`.** Requires a rights disposition covering
   retrieval from those hosts, given NSE's clause on systematic and automated data collection.
   Until then D2/D3 stay `UNKNOWN` for all four quarters on both channels.
3. **Taxonomy identification for the SEC 20-F Interactive Data exhibit.** Requires retrieving the
   filing's XBRL artifacts, which is `OP-02`/`OP-03` on `CHN-03` and currently `UNKNOWN`; it also
   requires the A-05 `D-5` scope decision on whether SEC EDGAR is in the source package.
4. **Issuer-site re-verification.** `www.infosys.com` denied automated requests on 2026-08-20, so
   even the `[repo-recorded]` URL facts have not been confirmed current.
5. **`D11` reconciliation effort.** Requires items 1–3 plus an analyst judgement. It is not an
   agent output.

## Conflicts and epistemic hygiene

- The NSE circular statement that Integrated Filing–Financial is submitted in XBRL is
  `[repo-recorded]` from the shortlist and was **not** re-verified; the SEBI circular that creates
  Integrated Filing does **not** mention XBRL. These are consistent but are separate instruments at
  different authority levels, and this record does not merge them into a single claim.
- No source disagreement between channels has been observed, because no channel's filing content
  has been read. Absence of observed conflict is **not** evidence of agreement.
- Publicly indexed third-party summaries about Indian XBRL filing history were seen during
  research and are deliberately excluded; only official issuer, exchange, regulator, and SEC
  material is cited above.

## Record digest convention and payload

This record uses the non-self-referential SHA-256 convention stated in A-01: UTF-8 canonical JSON
with recursively sorted object keys, preserved array order, no whitespace or byte-order mark, and
every `record_digest` field excluded from the digest input. No source-content bytes are included or
digested.

The companion machine artifact is bound by its own file digest inside the payload, so a change to
the CSV invalidates this record digest.

```json
{"artifact_id":"A-06","author_role":"bounded implementer (recording agent, not the decision maker)","cell_states_used":["CITED_FACT","UNKNOWN","ABSENT","NOT_APPLICABLE"],"cells_total":220,"channels":["CH-ISSUER","CH-NSE","CH-BSE","CH-SEC-6K","CH-SEC-20F"],"company":"Infosys Ltd (INFY; BSE 500209; SEC CIK 0001067491)","dimensions":["D1","D2","D3","D4","D5","D6","D7","D8","D9","D10","D11"],"document_version":"1.1.0","framework_discontinuity":"SEBI/HO/CFD/CFD-PoD-2/CIR/P/2024/185 Integrated Filing applies from the quarter ending 2024-12-31, inside the selected slice","ind_as_xbrl_confirmed_on_exchanges":false,"matrix_csv_path":"docs/evidence/phase-0a/a-06-filing-coverage-matrix.csv","matrix_csv_sha256":"7a93bb319e64941315ff152993974537f6b1b886f887d661aa39cf1104e14b43","program_quarters":["Q0","Q1","Q2","Q3"],"recorded_at":"2026-08-20","rights_ref":"docs/evidence/phase-0a/a-05-source-rights-package.md","source_content_fetched":false,"status":"RECORDED_FACTUAL","tier1_proven":false}
```

**Record digest:** `sha256:e9de787214bb7906b27522d2e502cdfbe4cec4112d69a48cc4990f94400d3a92`
(v1.0.0 digest, preserved:
`sha256:a86e31e2234f538be14806252ae1b594a3575015d691b97ea1e95b26c9ac6a2b`)

## Authorities and references

- `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` — A-06 clause and Phase 0A gate.
- `docs/plans/2026-08-19-phase-0a-evidence-program.md` — Task 3 scope, tier rules, state vocabulary.
- `docs/evidence/phase-0a/source-package-inventory.json` — issuer document URLs and dates (retrieval date 2026-08-19).
- `docs/evidence/phase-0a/a-02-discovery-slice-selection.md` — selected slice and recorded exchange channels.
- `docs/evidence/phase-0a/a-06-filing-coverage-matrix.csv` — the machine form of the four quarter tables above (220 data rows).
- `docs/evidence/phase-0a/a-05-source-rights-package.json` and `docs/evidence/phase-0a/a-05-source-rights-package.md` — all 132 disposition cells `UNKNOWN (denied by default)`.
- `docs/research/phase-0a-discovery-company-shortlist.md` — non-authoritative `[repo-recorded]` channel facts, retrieval date 2026-08-19.
- `https://www.sebi.gov.in/legal/circulars/dec-2024/circular-for-implementation-of-recommendations-of-the-expert-committee-for-facilitating-ease-of-doing-business-for-listed-entities_90406.html` — accessed 2026-08-20, circular `SEBI/HO/CFD/CFD-PoD-2/CIR/P/2024/185` dated 2024-12-31.
- `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001067491` — EDGAR company-browse listings for Forms 20-F and 6-K, accessed 2026-08-20.
- `https://www.nseindia.com/static/nse-terms-of-use` — accessed 2026-08-20; basis for not attempting automated exchange retrieval.
