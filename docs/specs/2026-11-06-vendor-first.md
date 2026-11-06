# VENDOR-1: vendor-first numbers and text, filings as the fallback

**Status:** draft. Sol (`gpt-6.1-sol`) reviews next. **Bead:** filed by the orchestrator.
**Date:** 2026-11-06.

Statements are marked **verified** (read or queried read-only on 2026-11-06 at `80a55405`),
**inferred**, or **not established**. Measurement figures come from
`scratchpad/vendor-first/measure-1/` (`measure.out`, `measure2.out`), Apar only (entity 1, the
only entity with interpretations; verified).

## 1. Owner order (2026-11-05)

1. Screener and Tijori are the main sources, for numbers and for processed text such as concall
   summaries.
2. NSE/BSE filings are the fallback only: when the vendors disagree, or a vendor does not map a
   concept.
3. Every mechanism is built.

Defaults already stated to the owner, kept here: every number carries a label (`vendors agree,
not checked against filing` or `checked against filing`); summaries guide, filings prove
numbers; first measure on Apar how often the filing differs when the vendors agree.

## 2. Goal

Any covered company gets an admitted value for every concept both vendors map and agree on,
without first fetching or extracting its filing. A filing check runs when a trigger (§5.4) fires
and always when a retained filing is already there. Every admitted number shows which of the
three labels (§5.3) applies. Vendor text is stored and cited as vendor text, never as a number
source. The Apar measurement is re-run after mapping and decides which concept classes may rely
on vendor agreement alone.

## 3. Non-goals

- The next phase: the five-company test (APARINDS, ICICIBANK, LAURUSLABS, MTARTECH, NETWEB),
  ICICIBANK onboarding, and the bank vendor and XBRL mapping entries written from its captures.
  This spec only makes that phase possible (§9).
- Feeding `eqos.vendor_values` (the raw-first cell store) into comparison. The occurrence path
  already holds the same statement tables (§5.1).
- Promoting mapping tiers to `EQUIVALENCE_DEMONSTRATED`. D3 needs ≥5 companies; the next phase
  supplies them.
- Upstox. It stays diagnostic-only.
- Operating KPIs, divisions, volumes and capacity. Per the Data Extraction rule these are model
  work from documents and belong elsewhere.
- Changes to the review queue, its severities or the trust overlay.

## 4. What the measurement found (verified)

| Finding | Number |
|---|---|
| Concept-periods with a Screener, a Tijori and a filed value | 8, all quarterly revenue, all agree |
| Vendor disagreements in the sample | 0 |
| Tijori interpretations | 20 `MAPPED`, 2,030 `UNMAPPED`, 10 `INVALID` (`UNIT_MISMATCH`, `pl_c_s` Sales) |
| Tijori unmapped native fields (occurrence path) | 196 across `qt_c`, `pl_c_d`, `pl_c_s`, `bs_c_d`, `bs_c_s`, `cf_c`, `fr_c` (43 of them ratios) |
| Screener interpretations | 297 `MAPPED`, 210 `UNMAPPED` (17 native fields per section), 9 `PERIOD_AMBIGUOUS`; 15 concepts mapped, 4 of them vendor aggregates |
| Screener FY `finance_costs` vs filing | 7.70–7.78% off in all 7 pairs; quarterly matches. Inferred: a definition difference |
| Standalone values stored | none |
| Compare runs with vendor sides in scope | run 5 only |
| `vendor_label_proposals`, `vendor_text_claims` rows | 0, 0 |

The sample cannot answer the owner's question yet: 8 points of one concept. The mapping work in
§5.1 exists mainly to make the re-measurement mean something.

## 5. Decisions

### 5.1 Vendor row-label mapping is standard data: a reviewed code dictionary

**Decision.** Extend the existing per-surface YAML mapping files
(`config/normalisation/mappings/screener/…/financials.yaml`, `…/tijori/…/financials.yaml`). Each
entry is a fixed vendor label in a fixed section mapped to a canonical id, with sign, scale, unit
and tier, as today. No per-company entries, no new mapping mechanism. Comparison reads only these
files.

**Reason.** The labels are the vendor's template. "Net Sales" in Tijori `qt_c` is the same row
for every non-financial company, so the same code works unchanged on a second company. That is
the owner's test for standard data. The comparison spec already says mappings are "once per
source surface and schema version, never per company" (§2 there). About 170 statement labels
(153 Tijori outside the `fr_c` ratios, 17 Screener per section; verified counts) is a dictionary someone writes once, not a job for a
model on every run.

**The proposal path.** `map_labels` (`equity_os/extraction/model/vendor_surface_labels.py`,
writing `eqos.vendor_label_proposals`) may be used to *draft* entries. It reads the same labels
from `vendor_values`. A proposal never takes effect by itself. The reviewed YAML entry is the
mapping, and comparison never reads `vendor_label_proposals`. No new proposal code.

**Which labels get entries.** Every statement label whose meaning matches exactly one canonical
id, or a dictionary formula row, at tier `EQUIVALENCE_UNPROVEN` unless evidence says otherwise.
A label whose definition is known to differ is `RELATED_NOT_EQUIVALENT`, so it never votes;
Screener annual "Interest" vs `finance_costs` is in this class unless the fix round explains the
7.7%. A label with no canonical counterpart stays `UNMAPPED`, which is a valid answer. Tijori
`fr_c` ratios are not mapped, because ratios are computed by code (invariant 6). The 10 `pl_c_s`
`UNIT_MISMATCH` cases are fixed in the entry's unit declaration, not with an override.

**Basis.** Vendors are captured at the basis the filing declares for the company (consolidated,
or standalone for a standalone-only issuer such as NETWEB). Standalone tables (Tijori `qt_s`,
`pl_s_*`, `bs_s_*`; the Screener standalone page) get mapping entries, and capture fetches them
when the company's basis is standalone. Standalone is never compared as consolidated (comparison
spec §3).

### 5.2 Admission precedence: vendor-first sourcing, filing-proven value

**Decision.** Admission decides each run cell in this order. The first rule that applies wins.

| # | Condition | Admitted value | Label |
|---|---|---|---|
| A | A retained filed value passes today's first-party rule (extraction `AGREE`, or `NOT_APPLICABLE` on one representation; no open non-diagnostic `HIGH`), and ≥1 independent vendor pair for the cell is `AGREE` (qualified or unqualified) | the filed value | `CHECKED_AGAINST_FILING` |
| B | As A, but no vendor pair agrees (vendor unmapped, unavailable, or differs) | the filed value | `FILED_ONLY` |
| C | No admissible filed value. Screener and Tijori both map the cell, both are `VALUE`, the vendor pair agrees under §5.4 T1, and the cell's check class is eligible (§5.4 T2) | the vendor value with the narrower interval (tie: Screener) | `VENDORS_AGREE_NOT_CHECKED` |
| — | Otherwise | none | refusal: `VENDORS_DISAGREE`, `VENDOR_UNMAPPED`, `VENDORS_IMPRECISE` or `CHECK_REQUIRED` |

**Reason.** The vendors are the main source because rule C admits without any filing. That is
the change the owner ordered. When a filing is already retained it is used, because "filings
prove numbers". Where the filing and agreeing vendors differ, the filing wins and the case is
exactly what the measurement counts. Where they match, the filed value is the same number at
better precision, so choosing it costs nothing. Every refusal in the last row is a trigger
(§5.4). The vendors disagreeing, or one of them not mapping the concept, are the owner's two
fallback cases.

`FILED_ONLY` is a third label the owner did not name. A filing used as the fallback has no vendor
check, and calling it either of the two named labels would be false.

A rule-C fact cites both vendor interpretations: the chosen one as its occurrence, and the other
as corroboration. Its epistemic class is `observed`, because both values are code-read table
cells. The labels state source class; they are not confidence.

**Contradiction to amend.** Comparison spec §4 ("Vendor observations … never get fact authority")
and its Stage 2 criterion ("A vendor observation cannot be admitted as a fact") are superseded
for rule C by owner order 2026-11-05. The implementation adds an amendment line to that spec. The
retention exception in `CONTEXT.md` (Evidence package) extends to rule-C facts: after a vendor
licence ends, such a fact keeps its value, label and both capture hashes, and it reconstructs
only by hash-matched re-fetch from the vendor.

### 5.3 Label storage and display

**Decision.** One enum, `AdmissionLabel` (`CHECKED_AGAINST_FILING`, `FILED_ONLY`,
`VENDORS_AGREE_NOT_CHECKED`), in a new non-null column `label` on `eqos.fact_admissions`, plus a
nullable `corroborating_interpretation_id`. `SelectedFact` carries the label. Every renderer that
reads `select_admitted` / `read_selected` prints it beside the number, as:

- `checked against filing`
- `filed, no vendor check`
- `vendors agree, not checked against filing`

The thesis-model adapters pass the label where they pass `single_sourced` today.

**Reason.** The fact store keeps one admission record per fact, and the label is a property of
that admission, not of the value. One column is the smallest store for it. Existing rows are
backfilled by code: first-party admissions are `CHECKED_AGAINST_FILING` if their run had an
agreeing vendor pair, else `FILED_ONLY`.

### 5.4 When the filing is checked: thresholds

The **check class** is (canonical id, period kind, basis, vendor surface pair).

- **T1, vendor-pair agreement.** The two vendor intervals intersect *and* the coarser vendor's
  half-width is ≤ 0.5% of the value's magnitude (the existing `magnitude_threshold: '0.005'`,
  `config/verification/comparison_policy/v1.yaml`). Otherwise the cell is `VENDORS_IMPRECISE`.
  **Reason:** an intersection test at Screener's ₹1 crore precision is loose for small lines.
  For a ₹3 crore line, ±0.5 crore is ~17% (verified: interval width ₹1 crore on every Screener pair).
  Agreement that cannot discriminate cannot vouch.
- **T2, eligibility.** A check class may use rule C only after ≥4 key-periods in which both
  vendors agreed under T1 have been compared with a filed value (any company), with 0
  differences. Until then the cell refuses with `CHECK_REQUIRED`.
- **T3, demotion.** One vendors-agree key-period whose filed value differs makes its class
  ineligible, and it stays so until a changed mapping entry is re-measured.

**Reason.** The sample is tiny, so a single counter-example must count, and ≥4 clean points is
the smallest bar that Apar's quarterly series can meet (8 three-way revenue points today).
Inferred consequence: on Apar alone, annual and balance-sheet classes (≤2 filed periods each)
stay `CHECK_REQUIRED`. That is correct: the five-company test supplies the rest.

**Storage: extract once.** A measurement command computes T2/T3 from stored run results and
writes `config/verification/vendor_first/v1.yaml` (class → eligible, n checked, n differ, run
ids). The file is committed after review. Admission reads only that file, so a run never
re-derives eligibility.

**What a trigger does.** A company-period with any `CHECK_REQUIRED`, `VENDORS_DISAGREE`,
`VENDOR_UNMAPPED` or `VENDORS_IMPRECISE` cell is listed by the run, and its filing (XBRL, then
results PDF) is acquired and extracted through the existing first-party path. A filing covers
the whole period, so the trigger works per period, not per cell. On the next run, rules A and B
apply to every cell of that period.

### 5.5 The filing-first path stays, as the fallback and the check

**Decision.** No first-party extraction, mapping, comparison or admission code is removed. The
comparator still computes the extraction check and corroboration as today. Admission gains rule
C and the label. Every run includes vendor sides by default, not only when a run config asks for
them.

**Reason.** The owner's fallback *is* this path, and the measurement needs it on every run.
Deleting or forking it would lose both.

### 5.6 Vendor processed text: stored as cited vendor text, never a number source

**Decision.** Vendor summaries (Tijori `concall-monitor` AI summaries, the Screener concall
notes on the company page) go through the existing span path
(`equity_os/extraction/model/vendor_surface_claims.py` → `eqos.vendor_text_claims`). A model
selects the `CLAIM` spans, code validates the offsets against the retained capture, and the epistemic class is
`inferred`. Each span cites its `capture_ref_id`, offsets and capture hash. Reading these surfaces
needs one text reader per surface, added to `SURFACES`. Both are fixed vendor page formats, so
the readers are code.

Kept separate from numbers in three ways:

1. `vendor_text_claims` never produce an occurrence or interpretation.
2. The claim check (`equity_os/publication/checking/claim_check.py`, `numeral_scan.py`) refuses a
   vendor text span as the evidence of any claim with a numeric object. That claim must cite a
   fact ID, a calculation trace, or a filing page and quote.
3. Reports render vendor text in its own block, headed with vendor, surface and capture date, and
   marked `vendor summary — guidance, not evidence`.

**"Guide" means** a summary span may point the document-extraction model at the transcript or
presentation to read. What the model extracts there carries its own page and quote, checked by
code (Data Extraction rule). The summary is never the citation.

**Reason.** Code reuse: the span table, its retention guard and its tombstone already exist
(migration 0045; verified). The owner's default "summaries guide; filings prove numbers" is
enforced at the one place a number enters a report.

### 5.7 Banks (ICICIBANK)

**Decision.** This spec builds the switch; the next phase writes the bank entries.

- Dictionary v4 adds a bank row set, taken from the statutory Third Schedule format (Banking
  Regulation Act): interest earned, interest expended, other income, operating expenses,
  provisions and contingencies, PBT, tax, PAT; capital, reserves, deposits, borrowings, advances,
  investments, total assets. Applicability is by a new issuer class (`NON_FINANCIAL`, `BANK`),
  recorded in company identity settings and derived from evidence (comparison spec §3).
- Onboarding stops returning `UNSUPPORTED` for a bank. NBFCs and insurers stay `UNSUPPORTED`.
- A bank issuer selects the bank rows. Non-financial rows are `NOT_APPLICABLE` for it, and the
  reverse holds for non-financial issuers.

**Reason.** The bank format is statutory and the same for every bank, so it is standard data. The
row set can be written from the statute. The vendor and XBRL entries cannot: by the comparison
spec's evidence rule, each needs a retained capture, and no ICICIBANK capture exists (verified:
one entity in interpretations). Until they exist, every ICICIBANK cell refuses
`VENDOR_UNMAPPED`, and its filing check reads `NOT_ASSESSED`. Nothing is guessed.

**Not established:** whether NSE's banking XBRL carries all these rows; whether Tijori publishes
bank statement tables in the same `qt_*`/`pl_*` layout.

## 6. Data and flow

```
vendor capture (Screener, Tijori; at the filing-declared basis)
  → occurrences → interpretations   (reviewed YAML mappings, §5.1)
  → comparison run (vendor sides always in scope; Screener–Tijori pair added, T1)
  → admission  A/B: filed value if retained and admissible  (label by vendor pair)
               C:   vendor value if T1 agree and class eligible (vendor_first/v1.yaml)
               else refusal → trigger list per company-period
  → trigger list → existing first-party acquisition + extraction → next run hits A/B
  → measurement command over stored runs → vendor_first/vN.yaml (reviewed, committed)

vendor text surfaces → span selection (model) → offset check (code) → vendor_text_claims
  → report "vendor summary" block; never evidence for a numeric claim
```

## 7. What changes

| Area | Change | Files (inferred where new) |
|---|---|---|
| Mappings | New versions with the §5.1 entries, the `pl_c_s` unit fix and standalone tables; new mapping-set manifest | `config/normalisation/mappings/screener/v4/financials.yaml`, `…/tijori/v5/financials.yaml`, `…/mappings/v9.yaml` |
| Capture basis | Fetch the standalone surfaces when the company's basis is standalone | `equity_os/sourcing/vendors/screener/`, `…/tijori/` |
| Comparison | Screener–Tijori pair and T1; vendor sides in every run's scope | `equity_os/verification/comparison/vendor_sides.py`, `policy.py`, `run_config.py`; `config/verification/comparison_policy/v2.yaml` |
| Admission | Rule C, `AdmissionLabel`, refusal reasons, trigger list | `equity_os/verification/admission/admission.py`; `migrations/0046_admission_label.sql` |
| Measurement | Product command replacing the scratch `measure.py`/`measure2.py`; writes eligibility | `equity_os/verification/comparison/vendor_measure.py`; `config/verification/vendor_first/v1.yaml` |
| Display | Label beside each admitted number | renderers reading `read_selected` (today `equity_os/interface/entry/cli.py`); `equity_os/analysis/thesis_models/adapters.py` |
| Text | Two surface readers; numeric-claim refusal; vendor-summary block | `equity_os/extraction/model/vendor_surface_claims.py`; `equity_os/publication/checking/claim_check.py` |
| Banks | Dictionary v4 bank rows and issuer class; onboarding switch | `config/normalisation/dictionary/v4/`; `config/companies/identity/`; `equity_os/companies/onboarding/` |
| Docs | Amendment line in the comparison spec (§5.2); `CONTEXT.md` gets **Admission label** | `docs/specs/2026-10-11-…comparison.md`, `CONTEXT.md` |

## 8. Acceptance (all checked by code on retained Apar captures unless noted)

1. **Mapping coverage.** Tijori `UNMAPPED` statement interpretations (excluding `fr_c`) drop from
   1,530 to ≤ the count of labels the reviewed files list as deliberately unmapped, each with a
   reason. Tijori `INVALID` `UNIT_MISMATCH` = 0. Every Screener `UNMAPPED` label is either mapped
   or listed with a reason.
2. **Expected three-way coverage.** The measurement command first computes, from occurrences
   alone, the expected set: every (concept, period) with a Screener occurrence, a Tijori
   occurrence and a filed occurrence for a concept that both vendor files map. A fresh compare run
   then has a three-way comparison for every member of that set; any gap is a failure. Floor:
   ≥60 concept-periods over ≥15 concepts, covering quarterly P&L, annual P&L, balance sheet and
   cash flow. The floor is inferred from occurrence counts; the computed set governs.
3. **Re-measurement.** The command reports, per check class: vendors-agree count, filing-checked
   count, filing-differs count and the eligibility result. Its output is byte-identical on two
   runs over the same stored results. `vendor_first/v1.yaml` is written from that output.
4. **Known differences.** Screener FY `finance_costs` is `RELATED_NOT_EQUIVALENT` (or explained
   and re-measured), so no FY `finance_costs` cell is admitted under rule C.
5. **Admission rules.** With a pinned eligibility fixture, an integration test admits one cell
   under each of A, B and C, and refuses one per refusal reason. A rule-C fact's label is
   `VENDORS_AGREE_NOT_CHECKED` and its value is the narrower vendor interval's value. The same
   cell with a retained admissible filing is admitted under A with the filed value. The existing
   admission tests still pass (rules A/B equal today's admissions; only the label is added).
6. **Trigger list.** A run over a period with a `CHECK_REQUIRED` cell lists that company-period.
   A run with every class eligible and both vendors agreeing lists nothing.
7. **Labels shown.** The rendered admitted-fact output carries the label text for every number.
   A fact without a label fails the render.
8. **Text separation.** A claim with a numeric object that cites only a `vendor_text_claims` span
   is refused by the claim check; the same claim citing a fact ID passes. No row in
   `interpretations` references a text-claim capture's surface.
9. **Standalone.** A standalone-only fixture issuer gets vendor standalone values and consolidated
   rows `NOT_APPLICABLE`; no standalone value pairs with a consolidated one.
10. **Banks.** Dictionary v4 loads. A fixture issuer of class `BANK` selects bank rows and
    onboarding no longer refuses it as `UNSUPPORTED`. Apar's run results are unchanged under v4.
11. Gate: `scripts/verify.sh gate` passes; mypy strict and ruff clean.

## 9. What the next phase gets

For each of the five companies: onboarding (bank included), basis-correct vendor capture, mapped
vendor values, admission with labels, a trigger list, and the measurement command. Five
companies also meet D3's sample count, so the same run can promote mapping tiers, and it adds
annual and balance-sheet points to T2. ICICIBANK needs its bank mapping entries written from its
first captures; that is next-phase work.

## 10. Risks

- **Shared vendor definitions.** Screener and Tijori may define a line the same wrong way, so
  agreement says nothing about the filing. T2/T3 measure exactly this; the risk remains for
  classes measured only on Apar.
- **Small sample.** ≥4 clean points is a weak bar. It is chosen to be reachable now; the next
  phase should raise the counts before anyone relies on rule C at scale.
- **Vendor retention.** Rule-C facts outlive their originals and can be rebuilt only by
  re-fetch, which a vendor may refuse. This is the accepted DOCS-1 trade-off, extended.
- **Vendor licence for summaries.** Whether showing Tijori AI summaries in reports is within its
  terms is not established. The source catalog's role and retention authority gate capture as
  today.
- **Bank formats.** See §5.7, not established.
- **Template drift.** A vendor relabelling a row turns entries into `UNMAPPED`, which fails
  closed. The existing drift check (VENDOR-SURFACE Task 19) catches it.

## 11. Open questions for the owner

1. **ICICIBANK basis.** Should a bank be analysed on standalone figures (the bank alone, the
   basis of its regulatory ratios) or on consolidated figures (including the insurance and AMC
   subsidiaries)? Default if unanswered: standalone.
2. **Can rule C ever be the published basis of a headline number?** Today a report can show a
   `vendors agree, not checked against filing` number with its label. Should headline lines
   (revenue, PAT, EPS) instead always force a filing check, whatever T2 says? Default if
   unanswered: no special case; the label is shown.
