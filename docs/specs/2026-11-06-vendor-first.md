# VENDOR-1: vendor-first sourcing with filing checks

**Status:** draft. Revised after Sol (`gpt-6.1-sol`) spec review 1 (REQUEST_CHANGES, 22 findings);
Sol re-reviews next. **Bead:** filed by the orchestrator. **Date:** 2026-11-06.

Statements are marked **verified** (code read or store queried read-only on 2026-11-06 at
`a66962e7`), **inferred**, or **not established**. Measurement figures come from
`scratchpad/vendor-first/measure-1/`, Apar only (entity 1; the store holds one reporting entity,
verified).

## 1. Owner order (2026-11-05) and how it is read

1. Screener and Tijori are the main sources for numbers and processed text.
2. NSE/BSE filings are the fallback, used when the vendors disagree or don't map.
3. Every mechanism is built.
4. Next step after this spec: a test on APARINDS, ICICIBANK (a bank), LAURUSLABS, MTARTECH, NETWEB.

**Reading (adopted from review 1, finding 1):** vendor-first sourcing with filing checks. The
vendor candidate is chosen first. A filing's presence alone never changes the source. The filed
value is used only when vendor sourcing fails, or when a filing comparison establishes a
difference. "Filings prove numbers" governs checking and fallback; it does not make filings
primary.

## 2. Owner decisions (defaults in force)

The spec proceeds on these. Each stands until the owner changes it.

1. **Numeric retention.** Admitted vendor numeric cells (both witnesses of a vendor-sourced fact)
   are kept privately, never committed to the public repo, for as long as a sealed report cites
   them, within each vendor's licence and terms. Expiry or licence end for either witness
   withdraws the admission for new reports; existing sealed reports keep their stored values with
   a visible note. This is a separate exception from DOCS-1 (`CONTEXT.md`, Evidence package),
   which covers labelled Tijori copies of documents with no exchange original and is unchanged.
2. **ICICIBANK analysis basis: standalone.** Recorded as the analysis basis, separately from the
   bases the issuer actually reports.
3. **Headline lines** (revenue, PAT, EPS) get no special case; the label is always shown.
4. **Scope of eligibility:** the five-company pilot and the owner's private reports. Admitting a
   vendor value without a filing check anywhere wider needs a new owner decision.

## 3. Phases

Each phase ships on its own, closes with its own Sol review, and leaves the system consistent.

| Phase | Scope | Findings |
|---|---|---|
| 1. Core | Numbers on non-bank issuers: mapping and extraction fixes, vendor-first selection and admission, eligibility, citation, fallback workflow, retention | 1–9, 12–20, 22 |
| 2. Vendor text | Tijori and Screener summaries as cited vendor text; numeral-scanner rule | 11, note |
| 3. Banks | Bank route grounded in a retained ICICIBANK filing | 10, 21 |

All three land before the five-company test (§9).

## 4. Non-goals

- Feeding `eqos.vendor_values` (the raw-first cell store) into comparison; the occurrence path
  holds the same tables.
- Operating KPIs, divisions, volumes, capacity (model work from documents, Data Extraction rule).
- Upstox (stays diagnostic). Review-queue severities and the trust overlay.
- A mutable eligibility system. Eligibility is one pinned artifact plus counterexample blocking.
- NBFCs and insurers (stay `UNSUPPORTED`).

## 5. What the measurement found (verified)

| Finding | Number |
|---|---|
| Concept-periods with a Screener, a Tijori and a filed value | 8, all quarterly revenue, all agree |
| Tijori interpretations | 20 `MAPPED`, 2,030 `UNMAPPED`, 10 `INVALID` (`UNIT_MISMATCH`, `pl_c_s`) |
| Screener interpretations | 297 `MAPPED`, 210 `UNMAPPED`, 9 `PERIOD_AMBIGUOUS` |
| Screener FY `finance_costs` vs filing | 7.70–7.78% off in all 7 pairs; quarterly matches. Inferred: a definition difference |
| Standalone values stored | none |

Eight points of one concept cannot answer the owner's question; Phase 1 exists to make the
re-measurement mean something.

## 6. Phase 1: the core

### 6.1 Mapping and the label inventory (findings 3, 16)

Vendor row labels are standard data: the reviewed per-surface mapping files
(`config/normalisation/mappings/screener/…`, `…/tijori/…`) are extended, new versions, no new
mechanism. `map_labels` may draft entries; comparison never reads `vendor_label_proposals`.

- Each mapping file gains an `unmapped:` list. Every native statement label in the retained
  captures (site, section, basis, label; Tijori `fr_c` ratios excluded, since ratios are computed
  by code) has exactly one disposition: an entry, or an `unmapped` item with a reason. This
  **is** the frozen inventory; no separate file.
- Entries default to `EQUIVALENCE_UNPROVEN`. A label whose definition is known to differ is
  `RELATED_NOT_EQUIVALENT` and never votes; Screener annual interest vs `finance_costs` is in this
  class unless the phase explains the 7.7%.
- Standalone tables (Tijori `*_s` sections, the Screener standalone page) get entries; capture
  fetches them when the company's basis is standalone (NETWEB). Standalone never pairs with
  consolidated.

**Units and precision cannot come from a mapping file (verified).** `MappingEntry` has no
raw-unit field; `vendor_tijori.py` (`extract_tijori`, the `scoped_row` branch) sets unit, scale and
declared precision only for the one section named in `config/normalisation/mappings/tijori/v1/display.yaml`
(`qt_c`), and `UNKNOWN_UNIT` elsewhere, which `interpret.py` (`interpret`, the `policy.units` lookup)
rejects as `INVALID`/`UNIT_MISMATCH`. Fix:

- `display.yaml` v2 becomes a list of rules, one per supported (section, basis), each with its own
  `unit_evidence_ref` and `precision_evidence_ref` taken from a retained capture. Sections without
  a rule stay `UNKNOWN_UNIT` and fail closed.
- The extractor applies the rule of the row's own section; its version is bumped
  (`VENDOR_EXTRACTORS` in `run_config.py` pins it), and retained captures are re-ingested.
- Precision is never inferred from serialized digits.

### 6.2 Vendor-only runs (finding 2)

Verified: `engine.py` `_group_periods` takes reporting currency only from filing-package
interpretations, and `ApplicabilityContext.disclosed_rows` comes from the package. A company-period
with vendor captures and no filing package therefore cannot run. Fix: when a group has no filing
package, the engine resolves context from evidenced metadata: currency from the vendor
occurrences' evidenced unit (§6.1 rules), framework and fiscal year from identity settings,
`disclosed_rows` from the vendor tables' structure (rows present, never values), period kind from
the vendor column. Nothing is defaulted; a missing input refuses the group.

### 6.3 Predicates (finding 15)

Policy file `config/verification/vendor_first/policy/v1.yaml`, pinned through `eqos.version_pins`
like every run artifact: `precision_limit: '0.005'`, `min_clean_key_periods: 4`. This is a
separate field from the comparison policy's triage `magnitude_threshold`, which is not reused.

Per cell, each side is an interval: value ± half a unit of its declared precision (zero width when
exact). S = Screener, T = Tijori, F = the run's first-party side.

**T1, vendor outcome.** First match wins:

1. `VENDOR_UNMAPPED`: S or T is absent, not `MAPPED`, not a DIRECT interpretation, not `VALUE`, or
   its entry is `RELATED_NOT_EQUIVALENT`. Constructed values are excluded here; derived figures
   are calculated by code from admitted facts.
2. `VENDORS_DISAGREE`: the S and T intervals are disjoint.
3. `VENDORS_IMPRECISE`: let m = max(|S|, |T|). If m = 0, either side has non-zero width. Else the
   wider half-width exceeds `precision_limit` × m.
4. `VENDORS_AGREE`.

The pair-outcome distinction `AGREE` / `AGREE_UNQUALIFIED` plays no part in T1; mapping tier
enters only through rule 1 and through the check class (§6.5).

**Filing state of a cell.** First match wins:

1. `FILING_ABSENT`: no first-party occurrence for the cell in the run.
2. `FILING_FAILED`: a first-party occurrence exists but the cell fails today's first-party rule
   (`admission.py`: extraction `AGREE`, or `NOT_APPLICABLE` on one representation).
3. `FILING_DIFFERS`: admissible, and F is disjoint from the S interval or from the T interval.
4. `FILING_AGREES`: admissible, and F intersects both.

"Differs" therefore means either vendor, not only the chosen one: a counterexample to "the vendors
agree, so the filing matches".

### 6.4 One admission path (findings 1, 4, 8, 13, 14)

`admit_run` keeps one path. Per cell, first match wins:

| # | Condition | Admitted value | Label |
|---|---|---|---|
| 0a | An open non-diagnostic `HIGH` item names the cell | none | refusal `REVIEW_OPEN` |
| 0b | `FILING_FAILED` | none | refusal `FILING_UNRESOLVED` |
| 1 | `VENDORS_AGREE`, `FILING_AGREES` | vendor value | `CHECKED_AGAINST_FILING` |
| 2 | `VENDORS_AGREE`, `FILING_DIFFERS` | filed value; a counterexample is stored (§6.5) | `CHECKED_AGAINST_FILING` |
| 3 | `VENDORS_AGREE`, `FILING_ABSENT`, class eligible (§6.5) | vendor value | `VENDORS_AGREE_NOT_CHECKED` |
| 4 | `VENDORS_AGREE`, `FILING_ABSENT`, class not eligible | none | refusal `CHECK_REQUIRED` |
| 5 | T1 is `VENDOR_UNMAPPED`, `VENDORS_DISAGREE` or `VENDORS_IMPRECISE`; filing admissible | filed value | `CHECKED_AGAINST_FILING` |
| 6 | As 5, `FILING_ABSENT` | none | refusal with the T1 outcome |

The vendor value is the narrower interval's (tie: Screener). Rows 0a–0b run before any source is
chosen, so vendor agreement never bypasses a failed or contested filing. Refusals in rows 4 and 6
are **triggers** (§6.7); 0a and 0b go to the review queue as today.

**Labels (finding 13).** Two, the owner's: `CHECKED_AGAINST_FILING` ("checked against filing": the
value equals, or is, an admissible filed value) and `VENDORS_AGREE_NOT_CHECKED` ("vendors agree,
not checked against filing"). The comparison outcome (T1, filing state) is not a label; it stays
in the run's results and pair records, reachable from the admission's `result_id`.

**Vendor bridge (finding 8).** `fact_for` today requires a known occurrence knowledge time and
builds anchors for XBRL and PDF only (verified). For a vendor value it:

- anchors natively: Tijori as `JSON_ISLAND`, Screener as `HTML_TABLE` (both exist in
  `SourceAnchorType`; verified); an occurrence lacking a required anchor field raises `BridgeError`;
- sets the fact's knowledge time to the later of the two witnesses' capture-registration times.
  The occurrences keep `KnowledgeTimeStatus.UNKNOWN`; no publication time is invented;
- records both witnesses: the chosen interpretation as today, the other in
  `witness_interpretation_id`. Epistemic class `observed`; bridge version `admission-bridge/2`.

**Which admission authorises a selected fact (finding 14).** Selection stays per fact row
(`select_admitted` → `select_canonical`). `read_selected` takes the label from the latest admission
of the selected row whose `overlay_position` is at or before the cutoff; the knowledge-time witness
stays the earliest, as in `citations.py`. `SelectedFact` gains `label`. Historical cutoffs return
the same facts as before.

**Migration `migrations/0047_admission_label.sql` (finding 18).** 0046 stays reserved for
research-4; the runner is filename-ordered and gap-tolerant (verified: `migrations.py`).

- `fact_admissions`: `label text NOT NULL DEFAULT 'CHECKED_AGAINST_FILING'`, then `DROP DEFAULT`
  (every existing row is a first-party filed value that passed the first-party rule, so no UPDATE
  is needed and the row-mutation trigger stays untouched); `witness_interpretation_id bigint NULL
  REFERENCES eqos.interpretations`; `eligibility_version text NULL`; a check that a
  `VENDORS_AGREE_NOT_CHECKED` row has both a witness and an eligibility version.
- `eqos.vendor_counterexamples (id, class_digest, result_id → results, run_id → runs,
  recorded_at DEFAULT eqos.store_now())`, `UNIQUE (class_digest, result_id)`, append-only with the
  existing `reject_mutation` triggers. It stores no vendor value.
- `eqos.row_captures`: the `fact_admissions` branch also yields `witness_interpretation_id`, so
  retention guards hold both witnesses' captures (finding 12).

### 6.5 Eligibility: a pinned artifact plus counterexample blocking (findings 5, 6, 7)

**Check class** = digest of (canonical id, period kind, basis, framework, issuer class, the
Screener entry and the Tijori entry with their mapping-set version, both extractor versions,
dictionary version, `vendor_first` policy version). Any version change makes a new class with no
evidence, so incompatible evidence is invalidated by identity, not by a rule. Issuer class is an
identity setting (`NON_FINANCIAL` for every onboarded issuer today, since onboarding refuses
financial issuers; `BANK` in Phase 3).

**Artifact.** `eqos vendor measure` (product code replacing the scratch `measure*.py`) reads stored
run results and writes `config/verification/vendor_first/eligibility/v1.yaml`: per class, the
distinct key-periods (dedup identity: `key_digest`) in `FILING_AGREES` and `FILING_DIFFERS`, their
run ids, `eligible` (≥ `min_clean_key_periods` agrees, 0 differs), the code version of the command,
and `available_from` (the commit time of the reviewed file). It holds counts and ids, no vendor
values, and is committed after review. Runs pin it through `eqos.version_pins`; the admission
records it in `eligibility_version`. In `AS_KNOWN` mode a cutoff before `available_from` sees no
eligibility.

**Pilot evidence only (finding 5).** Eligibility is scoped to the exact mapping entries and
conditions in the class. Four clean key-periods are provisional pilot evidence, valid only within
owner decision 4; they establish no reusable concept class.

**Counterexample blocking (finding 6).** Row 2 of §6.4 inserts a `vendor_counterexamples` row in
the same transaction. From then on:

- a class with any counterexample is not eligible, whatever the artifact says; the artifact is the
  reviewed baseline, the store is the override, and nothing waits for a file edit;
- `read_selected` returns nothing for a selected fact whose authorising label is
  `VENDORS_AGREE_NOT_CHECKED` and whose class has a counterexample recorded at or before the
  cutoff; earlier cutoffs are unchanged. The cell refuses on the next run and becomes a trigger;
- sealed reports keep their stored values; a later render shows "class later contradicted by a
  filing on ‹date›".

### 6.6 Citation (finding 9)

Verified: `citations.py` `_admitted` resolves a fact only when every admission's capture is
first-party; calculation inputs resolve the same way. Change: an admission with a
`witness_interpretation_id` resolves when both witnesses' captures are retained catalog vendor
captures of the two vendor-primary sources, and the admission is not withdrawn (§6.5, §6.8). The
resolved citation carries the label. A calculation shows the weakest label among its inputs.
Nothing else in citation resolution changes.

### 6.7 Fallback workflow (finding 20)

`admit_run`'s outcome already lists refusals; triggers are rows 4 and 6 of §6.4, grouped per
(entity, period end, basis), since a filing covers a whole period. A new subcommand
`eqos compare fallback --run <id>` consumes that list and calls the existing steps in order, per
company-period:

1. acquire the filing (XBRL, then results PDF) through the existing exchange acquisition used by
   `eqos documents backfill` (inferred: that path acquires exchange filings when no vendor flag is
   set; the phase confirms it);
2. stage, extract and interpret it as `eqos evidence ingest` does;
3. a fresh `eqos compare run` for the period;
4. `admit_run` on that run.

Terminal outcome per company-period, printed and stored with the run id: `ADMITTED` (every trigger
cell admitted), `FILING_UNAVAILABLE` (no filing acquirable; cells stay refused), `FILING_UNRESOLVED`
(extraction failed or review opened; review queue owns it), `STILL_REFUSED` (listing the cells and
reasons). No retries beyond those the acquisition layer already has.

### 6.8 Retention (finding 12)

Owner decision 1 applies. Mechanically:

- the vendor captures behind both witnesses stay private (store and retained blobs, never the
  repo), are held by the retention guard through `row_captures` (§6.4) while a sealed report cites
  the fact, and follow each vendor's retention and licence terms in the source catalog;
- when either witness's capture expires or its vendor's licence ends, the admission is withdrawn
  for new reports: `read_selected` and citation resolution refuse it; sealed reports keep their
  stored values and show "vendor source expired ‹date›";
- a backup restore does not resurrect a withdrawn admission; only a hash-matched re-fetch from the
  vendor within licence makes the capture `RESTORED` and the admission usable again.

### 6.9 Display

Every renderer reading `read_selected` prints the label text beside the number (today
`equity_os/interface/entry/cli.py`); thesis-model adapters pass it where they pass
`single_sourced`. A fact without a label fails the render.

### 6.10 Phase 1 acceptance (checked by code on retained Apar captures unless noted)

1. **Inventory.** Every native statement label in the retained Apar Tijori and Screener captures
   (excluding `fr_c`) has exactly one disposition in the pinned mapping files. The phase report
   gives cell counts per disposition, computed by code under the pinned mapping version. Tijori
   `INVALID`/`UNIT_MISMATCH` = 0.
2. **Units and precision.** Every supported Tijori (section, basis) has a display rule with both
   evidence refs; a fixture row in an unsupported section stays `UNKNOWN_UNIT`. A value whose digits
   suggest a different precision than its rule gets the rule's precision.
3. **Three-way coverage.** The command computes the expected set from reviewed mappings with full
   keys (entity, canonical id, period, basis, framework, dimensions); a fresh run has a three-way
   comparison for each member. The phase report states the measured count. The earlier 60
   concept-periods over 15 concepts is an estimate, not a gate.
4. **Vendor-only run.** An integration case with vendor captures and no filing package, occurrence
   or interpretation produces a complete run and a row-3 admission under a pinned eligibility
   fixture.
5. **Admission.** One integration case per row of §6.4, including: failed filing plus agreeing
   vendors refuses `FILING_UNRESOLVED`; an agreeing filing keeps the vendor value. Existing
   admission tests pass, with label `CHECKED_AGAINST_FILING`.
6. **Predicates.** Unit cases: disjoint precise intervals → `VENDORS_DISAGREE`; intersecting
   coarse → `VENDORS_IMPRECISE`; half-width exactly at the limit → agree; m = 0 both exact →
   agree, else imprecise; F disjoint from one vendor only → `FILING_DIFFERS`.
7. **Eligibility.** The command's output is byte-identical on two runs over the same stored
   results. A version mismatch gives `CHECK_REQUIRED`. A counterexample in run N blocks row 3 in
   run N+1 with the artifact unchanged, and `read_selected` drops the earlier unchecked fact for
   later cutoffs only.
8. **Citation.** Seal a report citing a row-3 fact and a calculation using it; both resolve with
   the label, and `row_captures` returns both witnesses' captures.
9. **Retention.** Expiry, and separately licence end, of either witness withdraws the admission for
   a new report; the sealed report keeps its value with the note; a backup restore does not revive
   it; a hash-matched re-fetch does.
10. **Fallback.** End to end on an Apar period whose filing is withheld from the first run:
    trigger → acquisition → extraction → comparison → admission ends `ADMITTED`; an unavailable
    filing ends `FILING_UNAVAILABLE` with cells still refused.
11. **Known difference.** No FY `finance_costs` cell is admitted under row 3.
12. **Labels.** The rendered admitted-fact output carries a label for every number.
13. **Gate.** `scripts/verify.sh gate` passes; mypy strict and ruff clean.

## 7. Phase 2: vendor text (finding 11, numeral-scanner note)

Verified: `vendor_surface_claims.extract_text` queries Screener captures only, through a
Screener-only reader, over `SURFACES` = three Screener surfaces; Tijori `concall-monitor` is a
market-scope surface in `config/sourcing/vendor_surface/surfaces.yaml`.

- **Readers by site.** `SURFACES` becomes keyed by (site, surface); the reader table gains the
  Tijori `concall-monitor` reader and the Screener company-page concall notes reader. Both are
  fixed vendor page formats, so the readers are code.
- **Bound to the report.** A span is usable in a report only if code resolves the span's company
  reference to the report's issuer (a market page carries many issuers) and its capture was
  registered at or before the report's cutoff.
- **Resolvable reference.** A report cites a span as (`capture_ref_id`, offsets, capture hash);
  citation resolution re-reads the offsets from the retained capture and refuses a mismatch.
- **Never a number source.** `vendor_text_claims` never produce occurrences or interpretations.
  The claim check refuses a span as evidence for a claim with a numeric object.
- **Numerals (review note).** A span containing any numeral (per `numeral_scan.py`) is never
  rendered; it stays private as an extraction pointer that directs the document-extraction model
  to the transcript or presentation, whose extractions carry their own page and quote. Spans
  without numerals render in a block headed with vendor, surface and capture date and marked
  `vendor summary — guidance, not evidence`.

**Acceptance.** Both readers produce validated spans from retained captures; a span of another
issuer, or captured after the cutoff, is refused; a citation with altered offsets fails; a numeric
claim citing only a span is refused and passes when it cites a fact ID; a span with a numeral is
absent from the render; no `interpretations` row references a text-claim capture. Gate as Phase 1.

## 8. Phase 3: banks (findings 10, 21)

Verified: onboarding verifies Ind AS (`verification.py`), derived settings write an Ind AS
framework (`derived_settings.py`), discovery refuses a non-Ind AS filing (`discovery.py`), and
results runs assume it; `AccountingFramework` has `IND_AS`, `IFRS`, `US_GAAP`, `UNKNOWN`. Inferred,
not established: Indian banks file in the Banking Regulation Act Third Schedule format, not under
Ind AS. No ICICIBANK entity or capture exists in the store (verified). So the bank route starts
from evidence:

1. **Ground.** Acquire and retain one ICICIBANK results filing (XBRL and PDF) through existing
   discovery, without onboarding it. Record from it: framework, XBRL schema and taxonomy, statement
   layout, bases reported. Every later step cites this record.
2. **Framework and onboarding.** Add the framework value the filing evidences (only if no existing
   value fits). Onboarding verification and derived settings accept it for issuer class `BANK`,
   set from evidence. NBFCs and insurers stay `UNSUPPORTED`. ICICIBANK's analysis basis is
   standalone (owner decision 2), stored apart from its reported bases.
3. **Dictionary v4 (finding 21).** Shared concepts stay shared for banks: PBT, tax, PAT, EPS,
   share capital, reserves, total assets and any other row whose definition holds for both.
   Applicability on issuer class restricts only sector-specific rows, layouts and formulas: bank-only
   rows (interest earned, interest expended, provisions and contingencies, deposits, advances,
   investments as a bank line) and non-financial-only rows and formulas (revenue from operations,
   cost of materials, inventories, working-capital formulas).
4. **Discovery, context, extraction, comparison.** Discovery accepts the evidenced bank filing
   family; the engine context carries issuer class; XBRL and PDF mapping entries for the bank rows
   are written from the retained filing; vendor entries from ICICIBANK's Tijori and Screener
   captures, with §6.1 display rules where Tijori bank tables differ.
5. **Refuse the rest.** Any capability the filing does not support (e.g. a statement or segment
   table absent from it) stays refused with a stated reason; nothing is guessed.

**Acceptance.** The grounding record exists with its capture ids. ICICIBANK onboards as `BANK`
with the evidenced framework; an NBFC fixture stays `UNSUPPORTED`. A compare run on the retained
filing period gives values for shared and bank rows, `NOT_APPLICABLE` for non-financial-only rows,
and admissions under §6.4. Apar's results are unchanged under dictionary v4. Gate as Phase 1.

## 9. What the five-company test gets, and D3 (finding 22)

For each company: onboarding (bank included), basis-correct vendor capture, mapped vendor values,
admission with labels, the fallback command, and `eqos vendor measure`.

The test supplies evidence toward D3; it does not qualify mappings by itself. A mapping is promoted
to `EQUIVALENCE_DEMONSTRATED` only when ≥5 distinct companies inside that mapping's own
qualification scope (surface, schema, basis, period kind, conditions) carry it and a discriminating
case exists. ICICIBANK is outside every non-financial mapping's scope and NETWEB (standalone)
outside every consolidated one, so most mappings will not reach five from this test; only mappings
whose sample and discrimination requirements both pass are promoted.

## 10. Document amendments (finding 19)

Made by Phase 1 (Phase 3 for the bank lines), in
`docs/specs/2026-10-11-canonical-financial-data-and-cross-source-comparison.md`:

- **§4, replace** "Vendor observations, including API-document-anchored ones, never get fact
  authority (the API-document bar stays)." **with** "Vendor observations get no fact authority,
  except under VENDOR-1 (`docs/specs/2026-11-06-vendor-first.md` §6.4, owner order 2026-11-05):
  within that spec's pilot scope, a Screener and a Tijori observation that agree may be admitted
  with their own `JSON_ISLAND` / `HTML_TABLE` anchors and a visible label. API-document-anchored
  observations stay barred."
- **Stage 2, replace** "A vendor observation cannot be admitted as a fact (API-document bar
  holds)." **with** "A vendor observation is admitted only under VENDOR-1 §6.4 (API-document bar
  holds)."
- **§8 outcome table, replace** "e.g. bank, NBFC or insurer, a foreign listing, or no Ind AS
  filing" **with** "e.g. NBFC or insurer, a foreign listing, or no filing in a supported
  framework; banks per VENDOR-1 §8" (Phase 3).
- **Stage 4, replace** "A financial-sector issuer gives `UNSUPPORTED`" **with** "An NBFC or
  insurer gives `UNSUPPORTED`" (Phase 3).
- **Out of Scope, replace** the row "Bank, NBFC and insurer row sets" **with** "NBFC and insurer
  row sets" (Phase 3).
- `config/sourcing/sources.yaml` header: the `vendor cross-check` role line becomes "derived
  aggregator whose values are compared with first-party values, and, for Screener and Tijori under
  VENDOR-1, the primary number source within its pilot scope". Role values are unchanged, so
  `test_source_list.py` still holds.
- `CONTEXT.md` gains **Admission label** (the two labels) and **Check class**; the Evidence package
  entry gains one sentence for owner decision 1, kept apart from the DOCS-1 sentence.

## 11. Risks

- **Shared vendor definitions.** Both vendors can define a line the same wrong way; agreement then
  says nothing. Counterexample blocking catches it on first contact with a filing; classes measured
  only on Apar remain exposed.
- **Small sample.** Four clean key-periods is a weak bar, accepted only within owner decision 4.
- **Precision.** Row 1 keeps the vendor value even when the filing is exact; admitted numbers carry
  vendor precision (₹1 crore on Screener).
- **Vendor licence for summaries.** Whether showing numeral-free Tijori summary spans is within its
  terms is not established; the source catalog's role and retention authority gate capture.
- **Bank formats.** Not established until Phase 3 step 1.
- **Template drift.** A relabelled vendor row becomes `UNMAPPED` and fails closed; the existing
  drift check catches it.
