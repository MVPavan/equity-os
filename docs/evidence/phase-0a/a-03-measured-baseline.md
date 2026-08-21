# A-03 Measured Q0 Baseline — Infosys Ltd (INFY), Q1 FY25

| Field | Value |
| --- | --- |
| Record type | `MEASURED_Q0_BASELINE` |
| Record status | `CONFIRMED` |
| Program quarter | Q0 |
| Issuer quarter | Q1 FY25 (quarter ended 2024-06-30) |
| Basis | Consolidated, Ind AS, ₹ crore |
| Knowledge cutoff | 2024-07-18 (filing/announcement date; anything later is out of scope for Q0) |
| Content-digest algorithm | SHA-256 |

Content-Digest: e5971fa9de5d60b6a86821374e91b400d4e0b1032d520542d7c238378814b940

## Purpose and boundary

This record fixes the measured Quarter 0 baseline: the confirmed consolidated
Q1 FY25 facts, each bound to its exact source anchor, together with the
cross-source verification reference, the methodology under which the baseline
was produced, and the product-owner confirmation. It records observed facts and
an attributable human confirmation only; it does not author the investment
thesis (that is A-11) and does not itself grant any source-use rights.

## Confirmed facts (consolidated Q1 FY25, ₹ crore)

Every line below was confirmed by the product owner on a **consolidated** basis
and is anchored to two independent first-party extraction paths over the same
issuer regulatory filing: the issuer results PDF (consolidated P&L, page 11) and
the NSE Ind AS XBRL consolidated instance, read context-bound to `OneD`
(period 2024-04-01 → 2024-06-30, segment-free).

| P&L line | Value | XBRL concept (context `OneD`) |
| --- | ---: | --- |
| Revenue from operations | 39,315 | `RevenueFromOperations` |
| Total income | 40,153 | `Income` |
| Total expenses | 31,132 | `Expenses` |
| Profit before tax | 9,021 | `ProfitBeforeTax` |
| Profit for the period (PAT) | 6,374 | `ProfitLossForPeriod` |
| EPS basic (₹) | 15.38 | `BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations` |

Standalone-vs-consolidated adjudication: the standalone statements report PAT
5,768 / basic EPS 13.90; the product owner confirmed the **consolidated** basis
(6,374 / 15.38) recorded above. This is the ~9–10% basis trap flagged in the
cross-source comparison and is resolved here in favour of consolidated.

## Source anchors

- **Issuer results PDF** — `source_id` `INFY-FY25-Q1-results-auditors`,
  consolidated P&L on page 11. File retained at
  `data/raw/infy-fy25/INFY-FY25-Q1-results-auditors.pdf`,
  `sha256:a07c12effe6cbffb6024e8462250e7f5e96b22fb4ec30c163827cc729b372695`.
  Recorded in the retrieval manifest
  `docs/evidence/phase-0a/a-05-retrieval-manifest-infy-fy25.json` (result
  `INFY-FY25-Q1-results-auditors`, status 200, 818,858 bytes) and inventoried in
  `docs/evidence/phase-0a/source-package-inventory.json` (Q0 package, source
  `record_digest` `sha256:143e96fa18aabc0295473c97bb1f87e4c7dc6cc51bfd7c510af32ae7c75d19f3`).
- **NSE Ind AS XBRL (consolidated)** — Q1 FY25 consolidated instance
  (`INDAS_109110…xml`), parsed context-aware and bound to context `OneD`
  (2024-04-01 → 2024-06-30, segment-free); scale sample:
  `RevenueFromOperations` raw `393150000000` INR, `decimals -7` → 39,315 ₹ crore.
  This is the independent second extraction path used for the cross-check below.

## Cross-source verification

Cross-source comparison reference:
`docs/research/infy-q1-cross-source-comparison.md`. Consolidated Q1 FY25 P&L
line items compared across the two on-hand first-party sources (issuer PDF page
11 and NSE Ind AS XBRL): **19 / 19 agree exactly**, with **0 true value
conflicts** requiring adjudication. All four cross-foot identities hold at ±0
(Total income = Revenue + Other income; PBT = Total income − Total expenses;
PAT = PBT − net tax; TCI = PAT + OCI). Residual verification limits recorded in
that reference: both Q1 sources trace to one issuer filing (cross-method, not
yet cross-host — the independent BSE Q1 XBRL was not on hand); the SEC 20-F is
FY25 annual USD and is not comparable to the Q1 INR quarter.

## Methodology

Per the product-owner methodology decision (PavanMV, 2026-08-21; bd memory
`methodology-q0-thesis-multimodel-2026-08-21`), the Q0 baseline is produced
under a multi-model generation plus human-adjudication method: facts are
cross-verified across independent sources (strong, as recorded above), and the
downstream thesis is generated independently by two models with exception-based
human adjudication. This method **supersedes the pure-manual Q0 baseline**: Q0
is no longer an independent human-authored baseline, and the manual-vs-assisted
measurement contemplated in A-13 is superseded by a cross-model-consensus plus
human-exception model. The tradeoff was recorded and accepted by the product
owner. Rights boundary: the baseline is built from publicly disclosed figures
and guidance, not from copyrighted source-document prose, and no external
source-document text was uploaded.

## Product-owner confirmation

The authorized product owner, PavanMV (mvpavan42@gmail.com), confirmed the
Q1 FY25 facts above on a **consolidated** basis (Revenue 39,315 / Total income
40,153 / Total expenses 31,132 / PBT 9,021 / PAT 6,374 / EPS 15.38, ₹ crore) and
approved this measured Q0 baseline on 2026-08-21. Verbatim product-owner
approval: "Approved". No approval is inferred from any other decision; this is
the product owner's own attributable confirmation of the facts and their basis.

## Digest convention

The recorded content digest is the SHA-256 of this file's canonical byte stream:
the exact UTF-8 file bytes with the one line beginning exactly
`Content-Digest: `, including that line's terminating LF, removed. No other
normalization, whitespace conversion, or field substitution is performed. This
non-self-referential convention (as used in A-09) binds every other byte of this
record; verification must also confirm there is exactly one such line.

## Authorities

- `docs/evidence/phase-0a/a-05-retrieval-manifest-infy-fy25.json` — retained PDF source and hash.
- `docs/evidence/phase-0a/source-package-inventory.json` — Q0 source-package inventory record.
- `docs/research/infy-q1-cross-source-comparison.md` — 19/19 cross-source verification.
- bd memory `methodology-q0-thesis-multimodel-2026-08-21` — multi-model + human-adjudication methodology decision.
