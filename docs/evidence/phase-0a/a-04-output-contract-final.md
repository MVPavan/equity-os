# A-04 Output Contract Final (Evidence-Derived)

**Record version:** 1.0.0
**Status:** APPROVED — the frozen v0 11-section shape, populated with the measured Q0 baseline (A-03) facts and the approved Q0 bootstrap thesis (A-11) content; analyst usability acceptance and product-owner scope approval RECORDED (see approval record).
**Prepared at:** 2026-08-21
**Author:** bounded implementer (assembling agent, not a decision maker)

## Purpose and boundary

This is the evidence-derived final output contract required by decision-register
v2 A-04, produced after the measured Quarter 0 baseline. It fills the frozen v0
section shape (`a-04-output-contract-v0.md`, 11 ordered sections) with the
already-approved Q0 content: the confirmed facts come from the measured Q0
baseline (`a-03-measured-baseline.md`) and the thesis sections come from the
approved bootstrap thesis (`a-11-investment-thesis.md`). **No new analysis is
introduced here** — this record only assembles existing, already-approved A-03
and A-11 content into the output format. Every fact number carries its A-03
source anchor; every thesis-derived number carries its A-11 tag.

- Company: Infosys Ltd (INFY); Program Q0 = issuer Q1 FY25 (quarter ended
  2024-06-30); basis consolidated, Ind AS, ₹ crore; knowledge cutoff 2024-07-18.
- Source records: `a-03-measured-baseline.md`
  (`sha256:e5971fa9de5d60b6a86821374e91b400d4e0b1032d520542d7c238378814b940`) and
  `a-11-investment-thesis.md` version 1.0.0
  (`sha256:7529443eed227c6fcad083b2027893ac6e922d40902d23daceb381f5922c7ae9`).

## 1. event_and_cutoff

Event under review: Infosys Q1 FY25 consolidated results (issuer results PDF and
NSE Ind AS XBRL). Information cutoff: **2024-07-18** (filing/announcement date);
anything later is out of scope for Q0. [Anchor: A-03 baseline header.]

## 2. facts

Confirmed consolidated Q1 FY25 facts (₹ crore), each anchored to A-03, which
binds them to two independent first-party extraction paths (issuer results PDF
consolidated P&L page 11, and the NSE Ind AS XBRL consolidated instance read
context-bound to `OneD`, 2024-04-01 → 2024-06-30):

| P&L line | Value | XBRL concept | Anchor |
| --- | ---: | --- | --- |
| Revenue from operations | 39,315 | `RevenueFromOperations` | A-03 confirmed facts |
| Total income | 40,153 | `Income` | A-03 confirmed facts |
| Total expenses | 31,132 | `Expenses` | A-03 confirmed facts |
| Profit before tax | 9,021 | `ProfitBeforeTax` | A-03 confirmed facts |
| Profit for the period (PAT) | 6,374 | `ProfitLossForPeriod` | A-03 confirmed facts |
| EPS basic (₹) | 15.38 | `BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations` | A-03 confirmed facts |

Source anchors (from A-03): issuer results PDF `INFY-FY25-Q1-results-auditors`,
consolidated P&L page 11, file
`sha256:a07c12effe6cbffb6024e8462250e7f5e96b22fb4ec30c163827cc729b372695`,
recorded in `a-05-retrieval-manifest-infy-fy25.json` and inventoried in
`source-package-inventory.json` (source `record_digest`
`sha256:143e96fa18aabc0295473c97bb1f87e4c7dc6cc51bfd7c510af32ae7c75d19f3`); NSE
Ind AS XBRL consolidated context `OneD` scale sample `RevenueFromOperations` raw
`393150000000` INR, `decimals -7` → 39,315 ₹ crore. Cross-source verification:
`docs/research/infy-q1-cross-source-comparison.md` — **19 / 19 agree exactly**,
**0 true value conflicts**, all four cross-foot identities hold at ±0.

## 3. changes

Thesis-derived (A-11 §1); comparatives carry A-11 tags:

- Q1 FY25 revenue ₹39,315 cr vs Q4 FY24 ₹37,923 cr → ~3.7% reported ₹ QoQ **[INFERENCE]**.
- Q1 FY25 revenue ₹39,315 cr vs Q1 FY24 ₹37,933 cr → ~3.7% reported ₹ YoY **[INFERENCE]**.
- Operating margin held at ~20.8%, the low end of the guided 20–22% band **[INFERENCE]**.

## 4. drivers

Analyst driver analysis (A-11 §2 key assumptions):

- Growth is guided, not demonstrated: 3–4% CC FY25 target off a soft Q1 base; reported ₹ ≠ constant-currency **[INFERENCE]**.
- Margin holds inside 20–22%: Q1 ~20.8% at the floor; mid/upper band needs utilization/pyramid/pricing levers **[INFERENCE/SPECULATION]**.
- Non-operating income real but not the engine: total income exceeds revenue by ₹838 cr **[FACT]**; treated as treasury/other income **[INFERENCE]**.
- Tax normalized: PBT ₹9,021 cr → PAT ₹6,374 cr implies ~29.3% effective tax **[INFERENCE]**.
- Base effects flatter optics: flat FY24 quarters make low-single-digit Q1 growth read as a restart **[INFERENCE]**.

## 5. management_ledger

Management commitments to track (A-11 §3):

- FY25 revenue growth **3–4% constant currency** **[FACT — commitment]**.
- FY25 operating margin **20–22%** **[FACT — commitment]**.
- Sequential CC acceleration: later quarters must out-grow Q1 **[INFERENCE]**.
- Margin trajectory off the ~20.8% floor toward 21%+ **[INFERENCE]**.
- Whether reported moves reflect operating vs currency vs non-operating items **[INFERENCE]**.

## 6. thesis_impact

Effect on the bootstrap thesis (A-11 §1): **constructive but conditional** — a
margin-anchored, delivery-consistency hold, not a growth re-rating. The FY25 case
rests on management's 3–4% CC growth and 20–22% margin guidance materializing,
not on a demand inflection this quarter does not yet evidence **[SPECULATION]**.
Central honest caveat: the facts contain reported ₹ revenue but no Q1
constant-currency growth, while guidance is in CC — so this single quarter
cannot, from these facts alone, confirm the guidance is on track.

## 7. observable_falsifiers

Conditions that would falsify the interpretation (A-11 §5):

- FY25 CC growth guidance cut below 3% at any FY25 quarter.
- Operating margin printing below 20% in any FY25 quarter, or the 20–22% band withdrawn.
- Q2 FY25 CC sequential growth flat or negative.
- Reported revenue declining QoQ in Q2 (below ₹39,315 cr) absent a disclosed currency/scope reason.
- Revenue rising while operating profit/PBT deteriorate materially, or a one-off revealed to have flattered Q1 PAT.

## 8. open_questions

Unresolved analytical questions (A-11 §6):

- Q1 FY25 constant-currency growth (QoQ and YoY) vs the ~3.7% reported ₹ figures?
- Segment/vertical/geography mix; discretionary vs cost-takeout split?
- Large-deal TCV and book-to-bill?
- Headcount, utilization, attrition?
- Composition and sustainability of the ₹838 cr non-operating income?
- FY25 capital-return posture (buyback/dividend)?

## 9. calculations

Each computed result carries its trace over A-03 facts; the LLM is never the
authoritative calculator:

- Non-operating/other income gap = **₹838 cr**: Total income 40,153 − Revenue from operations 39,315 = 838. [A-03 facts; A-11 §2 **[FACT]**]
- Cross-foot PBT: Total income 40,153 − Total expenses 31,132 = 9,021 (holds ±0). [A-03 cross-source verification]
- Effective tax rate ~**29.3%**: (PBT 9,021 − PAT 6,374) / PBT 9,021 = 2,647 / 9,021 = 0.2934. [A-11 §2 **[INFERENCE]**]

## 10. non_canonical_memory_draft

**Non-canonical — never a source of truth.** Q0 bootstrap: INFY Q1 FY25
consolidated print is solid on profitability (PAT ₹6,374 cr, EPS ₹15.38) but
margin sits at the ~20.8% floor and Q1 constant-currency growth is undisclosed;
the thesis is a conditional, margin-anchored hold pending Q2 CC and margin
trajectory. This draft is explicitly non-canonical.

## 11. approval_record

| Approval | Authority | State |
| --- | --- | --- |
| Output usability acceptance | Analyst | **APPROVED** |
| Output scope approval | Product owner | **APPROVED** |

- **Decider:** PavanMV (mvpavan42@gmail.com), acting as product owner and
  analyst. For this single-principal private project the evaluation-authority
  role is expressly self-assumed on the same basis already used for the analyst
  attestation (`A02-ATTEST-001`) and the A-08 approval (`A08-APPROVAL-001`).
- **Decision date:** 2026-08-21.
- **Verbatim approval:** "Approved" — the product owner's own attributable
  approval recorded for the measured Q0 baseline (A-03) and the Q0 bootstrap
  thesis (A-11) that this output assembles. No approval is inferred from any
  other decision.
- **Underlying approved records:** A-11 investment thesis version 1.0.0
  (`sha256:7529443eed227c6fcad083b2027893ac6e922d40902d23daceb381f5922c7ae9`) and
  the A-03 measured baseline
  (`sha256:e5971fa9de5d60b6a86821374e91b400d4e0b1032d520542d7c238378814b940`).

## Record digest convention and payload

This record uses the non-self-referential SHA-256 convention stated in A-01 and
A-04 v0: UTF-8 canonical JSON with recursively sorted keys, preserved array
order, no whitespace/BOM, and every `record_digest` field excluded from its
input. It digests no external source-document content — only the already-approved
A-03 facts and A-11 thesis content it assembles.

```json
{"artifact_id":"A-04","assembled_from":{"a_03_measured_baseline":{"content_digest":"sha256:e5971fa9de5d60b6a86821374e91b400d4e0b1032d520542d7c238378814b940","path":"docs/evidence/phase-0a/a-03-measured-baseline.md"},"a_11_investment_thesis":{"content_digest":"sha256:7529443eed227c6fcad083b2027893ac6e922d40902d23daceb381f5922c7ae9","path":"docs/evidence/phase-0a/a-11-investment-thesis.md","version":"1.0.0"}},"basis":"Consolidated, Ind AS, INR crore","company":"Infosys Ltd (INFY)","contract_kind":"OUTPUT_CONTRACT_FINAL","document_version":"1.0.0","issuer_quarter":"Q1 FY25 (quarter ended 2024-06-30)","knowledge_cutoff":"2024-07-18","no_new_analysis":true,"prepared_at":"2026-08-21","program_quarter":"Q0","sections":{"approval_record":{"decider":"PavanMV (mvpavan42@gmail.com), product owner and analyst; single-principal private project; evaluation-authority role self-assumed on the same basis as A02-ATTEST-001 and A-08 (A08-APPROVAL-001)","decision_date":"2026-08-21","output_scope_approval":{"authority":"Product owner","state":"APPROVED"},"output_usability_acceptance":{"authority":"Analyst","state":"APPROVED"},"underlying_records":{"a_03_measured_baseline":{"content_digest":"sha256:e5971fa9de5d60b6a86821374e91b400d4e0b1032d520542d7c238378814b940"},"a_11_investment_thesis":{"content_digest":"sha256:7529443eed227c6fcad083b2027893ac6e922d40902d23daceb381f5922c7ae9","version":"1.0.0"}},"verbatim_approval":"Approved"},"calculations":[{"anchor":"A-03 facts; A-11 s2 [FACT]","result":"Non-operating/other income gap = 838 INR crore","trace":"Total income 40,153 - Revenue from operations 39,315 = 838"},{"anchor":"A-03 cross-source verification","result":"Cross-foot: PBT = Total income - Total expenses","trace":"40,153 - 31,132 = 9,021 (holds +/-0)"},{"anchor":"A-11 s2 [INFERENCE]","result":"Effective tax rate ~29.3%","trace":"(PBT 9,021 - PAT 6,374) / PBT 9,021 = 2,647 / 9,021 = 0.2934"}],"changes":{"note":"A-11 thesis-derived; comparatives carry A-11 tags.","operating_margin":"held at ~20.8%, low end of the guided 20-22% band [INFERENCE, A-11 s1]","revenue_qoq":"Q1 FY25 revenue 39,315 vs Q4 FY24 37,923 -> ~3.7% reported INR QoQ [INFERENCE, A-11 s1]","revenue_yoy":"Q1 FY25 revenue 39,315 vs Q1 FY24 37,933 -> ~3.7% reported INR YoY [INFERENCE, A-11 s1]"},"drivers":{"items":["Growth is guided not demonstrated: 3-4% CC FY25 target off a soft Q1 base; reported INR != CC [INFERENCE].","Margin holds inside 20-22%: Q1 ~20.8% at the floor; mid/upper band needs utilization/pyramid/pricing levers [INFERENCE/SPECULATION].","Non-operating income real but not the engine: total income exceeds revenue by 838 crore [FACT]; treated as treasury/other income [INFERENCE].","Tax normalized: PBT 9,021 -> PAT 6,374 implies ~29.3% effective tax [INFERENCE].","Base effects flatter optics: flat FY24 quarters make low-single-digit Q1 growth read as a restart [INFERENCE]."],"source":"A-11 s2 key assumptions"},"event_and_cutoff":{"cutoff":"2024-07-18 (filing/announcement date); anything later is out of scope for Q0.","event":"Infosys Q1 FY25 consolidated results (issuer results and NSE Ind AS XBRL).","source":"A-03 measured Q0 baseline header."},"facts":[{"anchor":"A-03 confirmed facts; issuer PDF page 11; NSE Ind AS XBRL context OneD","line":"Revenue from operations","value_inr_crore":39315,"xbrl_concept":"RevenueFromOperations"},{"anchor":"A-03 confirmed facts","line":"Total income","value_inr_crore":40153,"xbrl_concept":"Income"},{"anchor":"A-03 confirmed facts","line":"Total expenses","value_inr_crore":31132,"xbrl_concept":"Expenses"},{"anchor":"A-03 confirmed facts","line":"Profit before tax","value_inr_crore":9021,"xbrl_concept":"ProfitBeforeTax"},{"anchor":"A-03 confirmed facts","line":"Profit for the period (PAT)","value_inr_crore":6374,"xbrl_concept":"ProfitLossForPeriod"},{"anchor":"A-03 confirmed facts","line":"EPS basic (INR)","value":15.38,"xbrl_concept":"BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations"}],"management_ledger":{"commitments":["FY25 revenue growth 3-4% constant currency [FACT - commitment].","FY25 operating margin 20-22% [FACT - commitment].","Sequential CC acceleration: later quarters must out-grow Q1 [INFERENCE].","Margin trajectory off the ~20.8% floor toward 21%+ [INFERENCE].","Whether reported moves reflect operating vs currency vs non-operating items [INFERENCE]."],"source":"A-11 s3 management commitments to track"},"non_canonical_memory_draft":{"canonical":false,"note":"Q0 bootstrap: INFY Q1 FY25 consolidated print is solid on profitability (PAT 6,374, EPS 15.38) but margin sits at the 20.8% floor and CC growth is undisclosed; thesis is a conditional margin-anchored hold pending Q2 CC and margin trajectory. This draft is explicitly non-canonical and never a source of truth."},"observable_falsifiers":{"items":["FY25 CC growth guidance cut below 3% at any FY25 quarter.","Operating margin printing below 20% in any FY25 quarter, or the 20-22% band withdrawn.","Q2 FY25 CC sequential growth flat or negative.","Reported revenue declining QoQ in Q2 (below 39,315 crore) absent a disclosed currency/scope reason.","Revenue rising while operating profit/PBT deteriorate materially, or a one-off revealed to have flattered Q1 PAT."],"source":"A-11 s5"},"open_questions":{"items":["Q1 FY25 constant-currency growth (QoQ and YoY) vs the ~3.7% reported INR figures?","Segment/vertical/geography mix; discretionary vs cost-takeout split?","Large-deal TCV and book-to-bill?","Headcount, utilization, attrition?","Composition and sustainability of the 838 crore non-operating income?","FY25 capital-return posture (buyback/dividend)?"],"source":"A-11 s6"},"source_anchors":{"cross_source_verification":{"reference":"docs/research/infy-q1-cross-source-comparison.md","result":"19/19 agree exactly, 0 true value conflicts; all four cross-foot identities hold at +/-0"},"issuer_results_pdf":{"file_sha256":"sha256:a07c12effe6cbffb6024e8462250e7f5e96b22fb4ec30c163827cc729b372695","inventory_record_digest":"sha256:143e96fa18aabc0295473c97bb1f87e4c7dc6cc51bfd7c510af32ae7c75d19f3","location":"consolidated P&L page 11","retrieval_manifest":"docs/evidence/phase-0a/a-05-retrieval-manifest-infy-fy25.json","source_id":"INFY-FY25-Q1-results-auditors"},"nse_indas_xbrl_consolidated":{"context":"OneD (2024-04-01 to 2024-06-30, segment-free)","scale_sample":"RevenueFromOperations raw 393150000000 INR, decimals -7 -> 39,315 INR crore"}},"thesis_impact":{"central_caveat":"Facts contain reported INR revenue but no Q1 constant-currency growth, while guidance is in CC; this single quarter cannot from these facts alone confirm guidance is on track.","source":"A-11 s1 core view","view":"Constructive but conditional; a margin-anchored, delivery-consistency hold, not a growth re-rating. The FY25 case rests on management's 3-4% CC growth and 20-22% margin guidance materializing, not on a demand inflection this quarter does not yet evidence [SPECULATION]."}},"status":"APPROVED"}
```

**Record digest:** `sha256:c23dd1c301f7110d7349253f1d65e4c3313076f7ce493d2600c87abf763edf20`

## Authorities

- `docs/evidence/phase-0a/a-04-output-contract-v0.md` — frozen 11-section v0 shape this record fills.
- `docs/evidence/phase-0a/a-03-measured-baseline.md` — measured Q0 baseline (facts and anchors).
- `docs/evidence/phase-0a/a-11-investment-thesis.md` — approved Q0 bootstrap thesis (version 1.0.0).
- Analyst (usability) and product owner (scope): decisions **APPROVED** 2026-08-21 by PavanMV (see approval record above).
