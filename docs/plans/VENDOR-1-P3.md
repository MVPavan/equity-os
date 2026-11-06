# VENDOR-1 Phase 3 Implementation Plan: banks

## Task 3 review 2 dispositions

Sol re-reviewed fix round 1 (main `2a70a09b`): CHANGES REQUIRED, two findings; B1c correctly
stands. Fix round 2 is below. Record: `docs/evidence/vendor-first/icicibank-grounding.md`
(Meaning audit, Alias audit, Segments, Counts, locators T3.82–T3.85).

| Item | Disposition |
|---|---|
| 1 (P2) segment-asset basis | `POST_ELIMINATION` for L393–L396 is withdrawn. The reconciliation [T3.68–T3.70] does not show where inter-segment adjustments sit, and no retained statement defines the treatment; the segment notes define only the segments and "Unallocated" [T3.84, T3.85]. The basis is unresolved, and the members are withheld: `no key` `R-BASIS`. Segment capital employed (L443–L446) has no interpreted operand member and is `no key` `R-OP`. The undimensioned asset rows (L397–L399) keep their values. Task 8: the isolation amendment must also cover Apar's `capmkt.segment_assets.2026` (`in_capmkt.yaml:496–501`), and the bank basis is never chosen because that entry supplies one. |
| 2 (P2) A7 comparatives | A7's period rule is rewritten (Resolved branches): the requested current intervals bind uniquely to the instance's; evidenced, labelled comparative columns are allowed; missing, ambiguous or conflicting current periods reject. The contradiction check is never waived after a positive match. Tests are listed. |
| Release routes | Replaced by Sol's rulings on routes (a), (b) and (c), with conditions. None releases the Task 8 isolation stop. Route (a)'s current evidence is the period-reader probe: on current main the reader refuses both PDFs, so (a) needs a reviewed reader change first. |
| Notes | PPE refusals (L103, L258, L260) read "scope not established". The segment-liability equity is demonstrated in the treasury member [T3.47, T3.82, T3.83] and so in its aggregate and net, not claimed of every member. L406 keeps its value. The record's v4 baseline is branch `fix-dictionary-v4-on-v3` (tip `aa1a7cb3`). |
| Counts | 457 lines: `VALUE` 103 (98 reported, 5 computed); `NOT_APPLICABLE` 128; `REFUSED` 200 (`R-NF` 77, `R-QCF` 76, `R-PDF` 18, `R-SCOPE` 15, `R-MEAN` 6, `R-OP` 3, `R-SIGN` 2, `R-CON` 2, `R-TIME` 1); `no key` 26. Admissible on rehearsal: the 98 reported lines. Locator check: 246 of 246 `OK`. |

## Task 3 review 1 dispositions

Sol reviewed the Task 3 amendment (main `95ad553c`) and found CHANGES REQUIRED, with seven
findings. Fix round 1 is below. Record: `docs/evidence/vendor-first/icicibank-grounding.md`
(Meaning audit, Alias audit, Segments, Counts, locators T3.49–T3.81).

| Item | Disposition |
|---|---|
| 1 (P1) A7 accepts another issuer's document | A7 is rewritten (Resolved branches). The PDF must carry one statement block whose title-block line equals the name of the package's identity-verified instance, case-insensitive and whole-line, above the basis heading, with a period heading and the framework declaration in the block. Contradiction checks and the no-authentication limit are stated. The tests cover a third-party mention, an appended release, conflicting issuers and identifier boundaries. The `NYSE: IBN` wording mismatch is withdrawn. **Checked against the retained PDFs: not met.** Issuer, basis and framework bind, but no period heading is bound to the statement page or block [T3.51, T3.52]. **B1c stands; the phase halts at Task 3.** |
| 2 (P1) equity keys | `equity_share_capital ← Capital` and `other_equity ← ReservesAndSurplus` are withdrawn. L137 and L138 are `REFUSED R-MEAN`: `Capital` includes the separately printed employee-option balance [T3.55, T3.56], and neither row has a supported element. Nothing is combined into a reported row. `paid_up_equity_capital` stays distinct. |
| 3 (P1) segment result | The bank's measure is segment PBT [T3.57–T3.62]. The members (L375–L382) enumerate no key, and the total (L383–L384) is `REFUSED R-MEAN`. Isolation: Apar's `capmkt.segment_result_total.2026` would map the bank total, and no supported selector separates them, so Task 8's stop rule applies (Task 8). Apar's meaning is unchanged. |
| 4 (P1) opening cash | L359 is `REFUSED R-TIME`, the existing no-value refusal for the September key. The filed instant is 2026-03-31 [T3.04, B8.26]. Nothing is retimestamped. |
| 5 (P2) share proceeds | L322 is `VALUE ProceedsFromIssuingShares@FourD`: H1, INR, `decimals=-5`, positive inflow, statement line "Proceeds from issue of share capital (including ESOPs/ESUSs)" under financing [T3.76–T3.78]. The line is not split; L326 is `R-SCOPE`. Every alias-based refusal was audited by meaning (record, Alias audit). 15 lines move from `R-NF` to `R-SCOPE` with a stated distinction, among them tangible-asset purchase and sale (L258, L260), whose "fixed assets" composition is undisclosed. The rest are confirmed `R-NF` with reasons. |
| 6 (P2) elimination basis | Frozen in the record. `segment_revenue` is `PRE_ELIMINATION` [T3.63–T3.67], and `segment_assets` is `POST_ELIMINATION` [T3.68–T3.70] (*withdrawn in review 2: basis unresolved*). Segment liabilities include capital [T3.71–T3.75], so their meaning is refused (members no key; total and net `R-MEAN`; Apar's entries would map them, so the Task 8 stop rule applies). `segment_capital_employed` has no common basis and is `REFUSED R-OP`. |
| 7 (P2) Task 8 computed rows | Task 8's `MAPPED` check covers reported `VALUE` lines only. Computed lines go through the formula path (operands, complete key, trace) and stay `NOT_REPORTED` for admission. |
| Rulings | EPS after extraordinary items is accepted (INR per share; Q and H1 separate). Exceptional items stay `R-SIGN`; the opposite sign is described as suggested, not proved. The computed-admission exclusion stands. |
| Counts (*superseded by review 2*) | 457 lines: `VALUE` 107 (102 reported, 5 computed); `NOT_APPLICABLE` 128; `REFUSED` 204 (`R-NF` 77, `R-QCF` 76, `R-PDF` 18, `R-SCOPE` 15, `R-OP` 7, `R-MEAN` 6, `R-SIGN` 2, `R-CON` 2, `R-TIME` 1); `no key` 18. Admissible on rehearsal: the 102 reported lines. Locator check: 242 of 242 `OK`. |

## Review 4 dispositions

| Item | Disposition |
|---|---|
| R2-04 (P1) Screener markerless exception | Exchange basis status no longer grants it. The standalone-only topology comes only from the issuer's reviewed Screener topology evidence. This is the existing NETWEB mechanism: the committed `config/coverage/watchlist.yaml` entry with `screener_warehouse_id_consolidated: null`, read through `screener_page_cli.basis_topology` and matched on company and warehouse id. Onboarding (`discover` → `screener_page_state`, `_vendor_adapters`) and reingest read that entry through the new `watchlist_topology`. Without it a standalone page must carry its marker, or it refuses. The `basis_status` argument and reingest's `basis_status_as_of` lookup are removed. Case (5) is new: exchange `STANDALONE_ONLY` without the entry must not authorise an unmarked page. Case (4) keeps the NETWEB exception (Tasks 5, 7). |
| R4-01 (P1) intake-command order | Before Task 10, Task 8 runs the full Task 13 command 1 with `--mapping-set v11`, the set Task 8 produces. After Task 12 publishes v12, Task 12's gate rerun runs the literal sealed v12 command, before Task 13's rehearsal and live run. Arguments, staged-member equality and the frozen live inventory are unchanged (Tasks 8, 12, 13). |
| R4-02 (P2) shared shareholding file | The bumps stay: no smaller valid design exists (see the note under the inventory). `tijori-shp-v2` → `v3` and `upstox-shp-v2` → `v3` are added to the inventory and to Task 5's files, pin verification and Apar follow-up. The no-alias and durable-pin rules are unchanged. |
| Notes | Fixed the formula-set parenthetical. Task 9 now reconciles §8's old dictionary, control and baseline numbers. Reingest case (1) uses a synthetic financial table and seeded occurrence provenance. The trigger reconciliation is scoped to `eqos` business tables. |

## Review 3 dispositions

| Item | Disposition |
|---|---|
| R2-04 (P1) Screener basis binding (superseded by Review 4) | Selecting standalone no longer implies standalone-only topology. `verification.screener_topology(warehouse_id, basis, basis_status)` builds a standalone-only topology only when the entity's exchange-evidenced basis status is `STANDALONE_ONLY`; otherwise a standalone page must carry its `Standalone Figures` marker, through a new `BasisTopology.consolidated_published` flag (Task 5). Applied to onboarding (`screener_page_state`, `_vendor_adapters`) and reingest (Task 7). The four cases are tests before Task 10. The two edited files are content-pinned, so `screener-v1` → `screener-v2` and `screener-shp-v2` → `screener-shp-v3` (Version and pin inventory). |
| R2-03 (P1) allowlist | `retention_classes` (0027 `classify_capture`, `AFTER INSERT ON capture_refs`) is added to every row that can register a new capture: grounding, onboarding, evidence ingest. Conditional `calculation_traces`, `calculation_trace_operands` and `construction_traces` (`put_interpretations`) are added to onboarding and evidence ingest. Reingest stays sequence-only for existing captures. `capture_states` is dropped, because registration writes none. A trigger reconciliation over migrations 0001–0049 is stated under the table. |
| R3-01 (P2) ledger check | Task 3 freezes and reviews the evidence-backed ledger, recording its sha256. Task 6 runs the mechanical comparison against the implemented v5 rules and must pass before Task 10. Expected outcomes are read from the frozen ledger, never regenerated. A mismatch stops work until a reviewed ledger or branch amendment. |
| Notes | The Interactions line now says FIVE-1 never edits this plan. Task 13's commands carry every argument, filled into `commands.txt` before Task 8's exact-command test and before sealing. The frozen ledger stays independent of the implementation (Task 6). |
| PDF-fix renumbering (orchestrator, binding) | The base is `main` after `eqos-djv`, `eqos-ghv`, `eqos-dol` and `eqos-n21` (`f75892e8`): dictionary v4, mapping set v10, `pdf/v3`, `constructions/v3`, `pdf-occurrences/5`. Phase 3 now creates dictionary **v5** (v4 plus issuer applicability and bank rows), first-party set **v11**, vendor set **v12**, **`pdf/v4/results_layout_banking.yaml`** (alone; v11 keeps listing `pdf/v3/results_layout.yaml`) and PDF extractor **`pdf-occurrences/6`**. Phase 3 creates no constructions version; one, if needed, would be `constructions/v4`. Unchanged: `xbrl/v6`, `statement_anchors/v3`, `screener/v5`, `tijori/v6`, formula set label: v4 declares formula set v3 after the rebase (v4 adds rows, not formula-set changes, unless the rebase worker finds one is needed). |

**Status:** fix round 4 (final) after Sol plan review 4 (`CHANGES REQUIRED`: R2-04, R4-01,
R4-02, notes), over round 3 (R2-03, R2-04, R3-01), renumbered after the results-PDF fixes, over round 2's R2-01–R2-05 and round 1's F01–F26 and
A1–A6. **Approved 2026-11-06 by orchestrator ruling** under the agent-stack rule for a loop that has not
converged after 3 rounds. There were four gpt-6.1-sol rounds. Fix round 4 applied Sol's stated smallest fix to each
residual, and the orchestrator checked those fixes against review 4's findings. Two residual rulings:
- The committed and reviewed watchlist topology entry, the existing NETWEB mechanism, counts as the
  independent Screener topology evidence.
- A standalone-only bank with no such entry ends with Screener `UNVERIFIED`. That fails closed and is accepted.

The phase-end Sol review covers the implementation. **Bead:** `eqos-awnc`. **Prerequisite:** FIVE-1 Tasks 1–2
(`docs/plans/FIVE-1-enablement.md`) gate Task 11 and phase completion; Tasks 1–10 proceed.
**Origin:** `docs/specs/2026-11-06-vendor-first.md` §8 (authoritative, amended per A1–A5), §6.1
(A6), §6.6 (A3), §1–§4 (owner order; decision 2: ICICIBANK's analysis basis is standalone) and §6.8
step 1. Code facts read at `517198f6`, rechecked for round 3 at `f19d2d54`.
**Base (orchestrator ruling):** `main` after the results-PDF fixes land (branch tip `f75892e8`):
dictionary v4 (v3 plus `current_tax_excl_earlier_years`; orchestrator ruling 2026-11-06: the PDF fixes rebase v4 on v3 before landing, so the lineage drops nothing), mapping set v10 (v9 with
`pdf/v3` and `constructions/v3`), `PDF_EXTRACTOR_VERSION = "pdf-occurrences/5"`, and
`PILOT_VERSIONS` at dictionary v4 and mapping set v10. Task 4 starts from that tip and Task 10
confirms these values there; any other value stops work for an amendment. Phase 1 Task 10
(`results_filing.py`, `fallback.py`,
`nse_filings.filing_for`, `compare fallback`) is on `main`; this plan uses its real interfaces.
Phase 1 Task 9 is in flight; Phase 1 live Tasks 13–14 apply migrations 0047, 0048 and 0049.
**Goal:** ICICIBANK onboards as `BANK` under the framework its own filing evidences, and a
comparison run on its retained filing period gives `VALUE` for every shared and bank key the
frozen ledger expects, `NOT_APPLICABLE` for non-financial-only rows, the ledger's stated refusals
for unsupported capabilities, and positive admissions on a rehearsal copy; Apar's numeric results
are unchanged under dictionary v5.

**Out of scope:** NBFCs and insurers (stay `UNSUPPORTED`); any bank other than ICICIBANK; bank
eligibility evidence (§6.5 row 3 stays unavailable for `BANK`); report drafting, thesis models and
the Stage 2 report path for a bank; vendor text (Phase 2); moving Apar's pilot pins
(`PILOT_VERSIONS`, `interface/entry/cli.py`); admitting facts on live; the five-company test (§9);
bank KPIs, segments or divisions beyond the filed statements (Data Extraction rule); re-ingesting
Apar on live under the bumped extractors (a follow-up that gates Apar's next live run; see
Interactions); the acquisition route itself (FIVE-1).

**Constraints:**
- Grounding comes first, and nothing later presumes a bank filing format. Content that depends on
  the grounding record is a branch below, fixed at Task 3 (B9 at Task 12).
- Standard filed statements and XBRL lines are code; nothing is derived, estimated or filled. A
  capability the filing does not carry keeps its rows and refuses with a stated reason (§8 step 5).
- Phase 3's migration is `0050_issuer_class.sql` (0047–0049 are taken; 0049 is
  `seal_paired_screen_runs`). Recheck at landing; if another phase took 0050, use the next free
  number. Committed migrations, dictionary versions and mapping sets are never edited.
- Every byte change to a content-pinned source bumps its version (Version and pin inventory).
- Live writes are permanent. Tasks 2, 11 and 13 follow the live protocol below.
- No vendor body, vendor value or embedded mapping example in committed text, logs or reports; the
  grounding record holds no financial amount.
- Never open `stage4_holdout.yaml`, `stage4_manifest.yaml`, `data/holdout/` or `data/raw/onboarding/`.
- Files stay under 800 lines. `engine.py` (787) and `onboard_cli.py` (785): new logic goes into new
  modules beside them.
- Tests follow `.claude/rules/python/testing.md`: integration through public commands first; unit
  tests only for form classification, issuer-class resolution, issuer applicability and the
  framework predicate.

**Shape:** Task 1 is code; Task 2 grounds live; Task 3 resolves the branches, freezes the
expected-key ledger and pins the accepted evidence (Sol reviews the amendment as a plan review).
Tasks 4–9 are code, one commit each after the orchestrator verifies them. Task 10 gates. Task 11
migrates and onboards live; Task 12 resolves B9 and writes the vendor bank mappings from Task 11's
captures, then reruns the gate; Task 13 ingests, re-ingests and compares live, with admissions and
the Apar regression on the rehearsal copy only. **Sol reviews this plan, the Task 3 amendment, then
once at phase end**, closed by one fresh critical review.

**Estimate:** about 70 summed hours (author's estimate, not measured). The F26 reductions (reused
acquisition, smaller grounding record) are offset by required work the first draft omitted (PDF
framework evidence, pins, fallback, regression materialisation).

| Task | Implementer | Hours |
|---|---|---|
| 1. Grounding command | Opus | 3 |
| 2. Live grounding and the grounding record | orchestrator, Opus drafts the reading | 3 |
| 3. Branch resolution, ledger, evidence pins (plan amendment) | orchestrator | 3 |
| 4. Contracts and migration | Opus | 2 |
| 5. Bank onboarding | Opus | 9 |
| 6. Dictionary v5 and issuer applicability | Opus | 6 |
| 7. Engine context, run framework, fallback | Opus | 7 |
| 8. First-party bank mappings, mapping set v11 | Opus | 6 |
| 9. Document amendments | Sonnet | 1.5 |
| 10. Pre-live gate | orchestrator | 2 |
| 11. Live: migrate, onboard ICICIBANK | orchestrator | 4 |
| 12. B9, vendor bank mappings, mapping set v12 | Opus | 5 |
| 13. Live: ingest, compare; rehearsal admission and Apar regression | orchestrator | 6 |
| Sol loops (Task 3 amendment, phase end), closing review | — | 12 |

## Readings (Sol plan review 1 ruled; conditions folded in)

1. **Grounding is entity-free and filter-free (A1, F02, F26).** Grounding uses the raw listing and
   fetch primitives only: `nse_filings.listing_url`, `listing_rows`, `collapse`; the extracted
   retain step of `results_filing` (made public as `retain`, below) for every body; and a small
   entity-free `results_pdfs` helper (announcements listing, `observed_link`, `document_request`,
   results-category filter, each body through `retain`). It never calls `filing_for`,
   `ListingRow.qualifies` or any form, schema or framework predicate. The entity-bound
   `announcement_documents` (intake rows) stays as Phase 1 built it, for the fallback.
2. **Grounding bodies are retention-only (A1).** Two identity-role surfaces under one source,
   `nse-grounding`: `NSE_XBRL_INSTANCE` (`Representation.XBRL`) and `NSE_RESULTS_DOCUMENT`
   (`Representation.PDF`), `SourceRole.IDENTITY`, exchange rights. Listings and the master use their
   existing surfaces. Intake and package code refuse an `nse-grounding` capture as a member.
   Onboarding fetches its own instances and PDFs under first-party sources (Task 5).
3. **Analysis basis is a setting with a reviewed decision binding (A3, F19).** Task 4 adds
   `SettingKey.ANALYSIS_BASIS` and `EvidenceInputKind.OWNER_DECISION`. The evidence is a committed
   binding file `config/companies/basis_decisions/icicibank.yaml`: ISIN, symbol, value
   `STANDALONE`, the decision's section (`§2 decision 2`), its exact text, `effective_from`.
   Onboarding refuses before any settings write when the binding's ISIN differs from the
   discovered issuer, its value differs from `--analysis-basis`, its quote is not in the committed
   spec, or the path is not under `config/companies/basis_decisions/`. The binding's bytes are the
   retained `OWNER_DECISION` input. Basis status still means "bases the issuer reports", from the
   listing.
4. **Issuer class is a form-backed setting with a bounded legacy rule (A3, F20).** Task 5 writes
   `SettingKey.ISSUER_CLASS` with `DISCOVERY` evidence only when every onboarding filing carries
   the same uncontested supported form (`IndAS` → `NON_FINANCIAL`, `Banking` → `BANK`; the
   existing checks at `member_identity.py:200–212` stay). `issuer_class(conn, entity_id,
   period_end, cutoff)` resolves the setting by `setting_as_of` semantics (recorded by the cutoff,
   `valid_from <= period_end`, latest supersedes). Phase 1's provenance rule applies only to an
   entity for which no `ISSUER_CLASS` setting has ever been recorded (the legacy non-financial
   cohort; Apar); an entity with any such setting never falls back. Unknown, mixed, NBFC, insurer
   or unusable evidence yields no class.
5. **Issuer applicability is consulted only where declared.** Dictionary v1–v4 rows declare none
   and decide as today; a v5 row declares its classes; a v5 run whose group has no resolved class
   refuses the group.
6. **"Apar unchanged under v5" is numeric regression, not eligibility (A4, F17, F24).** On the
   rehearsal copy, three runs share the same captures, cutoff and scope: Apar's v4/v10 baseline at
   the pre-Phase-3 code (the base's pilot pins), a v4/v10 control at the Phase 3 tip, and the
   v5/v12 candidate, with the candidate's interpretations materialised. Every baseline row keeps
   canonical key, state, value, interval and normalised
   reason; added rows have a family/applicability disposition. Eligibility is separate: any changed
   dictionary, mapping or extractor version is a new check class with no evidence.
7. **Admission evidence is from the rehearsal copy (A5).** Positive admissions for the ledger's
   admissible cells, expected refusals for the rest; nothing on live; no `BANK` eligibility.

## Conditional branches (fixed at Task 3 from the grounding record)

Each branch names the evidence that decides it. Any observation outside the table, and any stop
arm, halts the phase at Task 3 for an amendment; nothing is defaulted. Every bank plumbing step
(form predicate, per-entity framework in every ingest, reingest and fallback path, versioned pins)
is unconditional; only the cells below vary.

| # | Decided by | Arm | Changes |
|---|---|---|---|
| B1 | framework declaration for the issuer, basis and period, and its meaning | **B1a** fits an existing `AccountingFramework` value | no enum change; Task 5 verifies that value |
| | | **B1b** another framework | Task 4 adds one value named from the declaration; Task 5 adds its phrases with the cited locator |
| | | **B1c** none, ambiguous or conflicting | stop |
| B1′ | where the declaration is | **X** the instance (text block, QName and context) | existing `verify_xbrl_framework` path |
| | | **P** the results PDF only | Task 5's PDF framework evidence path, carried into every ingest, reuse and fallback (Tasks 5, 7); needs B7 identity, period and basis association, else B1c |
| B2 | IntegratedFinance form namespace segment, every grounded instance | **B2a** uncontested `Banking` on all | Task 5 maps `Banking` → `BANK` |
| | | **B2b** another, mixed or contested form | stop |
| B3 | fact namespace, scope concept, reporting-period concept | **B3a** a registered `in-capmkt` `TaxonomySpec` whose scope and period concepts the instance uses | no parser change; reuse entries per Task 8's inventory |
| | | **B3b** registered namespace with other concepts, or unregistered | Task 8 registers the evidenced `TaxonomySpec` (no invented namespace) |
| B4 | identity concepts and identity scheme (name, ISIN, symbol, scrip, scope) | **B4a** as for Ind AS filers | no identity change |
| | | **B4b** other concepts (e.g. HDFCBANK's `NameOfBank`, a possibility, not an ICICIBANK fact) | Task 5 reads the evidenced concepts for the `BANK` form, in discovery and ingest verification |
| | | **B4c** unknown or conflicting identity | stop |
| B5 | bases on the evidenced listings | **B5a** both | discovery selects standalone; basis status `CONSOLIDATED_AND_STANDALONE` |
| | | **B5b** standalone only | §6.2 path; `STANDALONE_ONLY` |
| | | **B5c** consolidated only, or missing/tied listings | stop (B5c consolidated-only is an owner question) |
| B6 | raw collapsed integrated rows' `type` | **B6a** `Integrated Filing- Financials` | no change |
| | | **B6b** one other value on every bank integrated row | Task 5 lets `qualifies` accept that value; the instance's form check then admits only `Banking` |
| | | **B6c** tie, missing broadcast or no instance | stop |
| B7 | results PDF against the full intake contract: `Scrip Symbol :` marker (`member_identity.py:181`), text layer, period and basis heading, statement lines | **B7a** contract passes on the retained PDF | Task 5's staged inputs carry the PDF member; Task 8 writes PDF entries and `config/runs/icicibank-<period>.yaml` (`pdf_parse`, sha256); Task 13 ingests the XBRL+PDF package from the staged inputs |
| | | **B7b** any part fails or no PDF | XBRL-only package and staged inputs, PDF retained with an explicit limitation, PDF claims `NOT_ASSESSED`; with B1′ P → B1c |
| B8 | per statement, period kind and basis: presence in the XBRL; statement anchor fit (`statement_anchors/v1`, `v2`) | present | mapped in Task 8; capability `SUPPORTED` |
| | | absent | rows and required-period rules unchanged; capability `UNSUPPORTED` with reason; each key's expected result follows the unchanged rules (ledger, Task 3) |
| | | anchors do not match bank statements | Task 8 adds `statement_anchors/v3.yaml` from the evidenced elements, in v11 |
| B9 | vendor tables in Task 11's captures: sections, unit and precision evidence (pending until Task 12) | **B9a** a section's unit and precision are evidenced and its layout is distinct | Task 12 adds a rule to `tijori/v6/display.yaml` |
| | | **B9b** no evidence, or an incompatible layout shares a section key without an evidenced distinction | section stays `UNKNOWN_UNIT`, fails closed; no global rule overwritten |
| B10 | rounding, currency and fiscal-year-end facts and contexts (`derived_settings._declared`) | **B10a** as for Ind AS filers | no change |
| | | **B10b** other concepts | Task 5 reads the evidenced concepts for the `BANK` form |
| | | **B10c** absent | stop: onboarding would be blocked, not accepted |

## Resolved branches (Task 3; draft for Sol review, eqos-awnc)

Fixed from `docs/evidence/vendor-first/icicibank-grounding.md` (gen-1). `[Bx.yy]` are its Task 2
locators; `[T3.nn]` are the rows Task 3 added. The locator check
(`scratchpad/vendor-first/live-p3-1/locators_t3.py`) passes 246 of 246, none `NOT_ASSESSED`
(fix round 2; 242 of 242 at fix round 1, 209 of 209 before).

**B1c stands. The phase halts at Task 3** (fix round 1, after Sol review 1 rejected the first
A7). The framework is declared only in the results PDFs (B1′ P). B7 fails on both PDFs, because
neither prints `Scrip Symbol :` [B7.15, B7.16], so "with B1′ P → B1c" applies. Revised A7 (below)
states the evidenced issuer declaration that would release the stop. The retained PDFs do not
satisfy it. Each names the bank in the title block of its standalone statement page, but no
period heading is bound to that page or its block [T3.51, T3.52]. The arms below other than B1
stay as evidenced. They and the ledger are not in force until an amendment releases B1c.

| Branch | Arm | Evidence | Consequence |
|---|---|---|---|
| B1 | **B1c** (stop). Content would be **B1b `INDIAN_GAAP`** once the PDF is associated | No instance declares a framework [B1.01–B1.04]. All four PDF basis declarations agree [B1.05, B1.06, B1.09, B1.10]: "Accounting Standards prescribed under Section 133 of the Companies Act, 2013, the relevant provisions of the Banking Regulation Act, 1949, the circulars, guidelines and directions issued by the Reserve Bank of India … and other accounting principles generally accepted in India". The releases call this "Indian GAAP" [B1.07, B1.11]. No `IND_AS` phrase occurs [B1.13–B1.18]. The new phrase matches all four as a token run [T3.15–T3.18]. | Task 4: `AccountingFramework.INDIAN_GAAP = "INDIAN_GAAP"`. 0050 also widens the four `framework` CHECKs (0001: `filing_packages`, `acquisition_attempts`, `interpretations`, `results`); without that, no bank package, attempt, interpretation or result row can be written. Task 5: `FRAMEWORK_DECLARATIONS[INDIAN_GAAP] = ("prescribed under Section 133 of the Companies Act, 2013, the relevant provisions of the Banking Regulation Act, 1949",)`. The comment cites T3.15–T3.18. Task 9 applies A7's spec wording. *All of this waits for the B1c release.* |
| B1′ | **P** | The declaration is in the PDFs only [B1.05, B1.09; B1.01–B1.04]. The basis association is the declaration's own subject, "The standalone financial results have been prepared" [B1.05, B1.09]. Page 1, the covering letter, prints the period [B7.01, B7.09]. It sits outside the statement block, and no period heading is bound to the issuer-titled statement page [T3.51, T3.52]. | Task 5's P arm and Task 7's P paths, once released. Identity, period and basis association is revised A7, which is not met. |
| B2 | **B2a** | Each of the four instances' namespace forms is exactly `{Banking}` [B2.01–B2.08]. | Task 5 maps `Banking` → `BANK`. |
| B3 | **B3a** | Facts are in the registered `http://www.sebi.gov.in/xbrl/2026-01-31/in-capmkt` [B3.01, B3.06, B3.11, B3.16]. Its scope and period concepts are used at `OneD` [B3.02–B3.20]. | **Parser:** no change; no `TaxonomySpec` and no `xbrl_taxonomies.py` edit (B3b struck). |
| B4 | **B4b** | The name is `NameOfBank` [B4.04, B4.10, B4.16, B4.22], not `NameOfTheCompany` [B4.05, B4.11, B4.17, B4.23]. Q1 contexts use scheme `http://www.sebi.gov.in/in-capmkt/Symbol` with `ICICIBANK` [B4.18, B4.24]. That equals the instance's own `Symbol` fact [B4.14, B4.20] and the master symbol [B4.25]. The Q2 contexts use the seeded ScripCode scheme [B4.06, B4.12]. | Ruling below. Task 5: `filing_identity` reads `NameOfBank` for the `BANK` form. `xbrl_identity.py` gains `SEBI_SYMBOL_ENTITY_SCHEME = "http://www.sebi.gov.in/in-capmkt/Symbol"`. `verify_xbrl_identity` and `xbrl_entity_state` map it to the NSE symbol set, as they map `NSE_ENTITY_SCHEME`. |
| B5 | **B5a** | Both bases are listed for both periods [B5.01–B5.04]. | Discovery selects standalone. The basis status is `CONSOLIDATED_AND_STANDALONE`. |
| B6 | **B6a** | Every collapsed row is `Integrated Filing- Financials` [B5.01–B5.04]. | No change; B6b struck. |
| B7 | **B7b** for the package; revised A7 not met | Neither PDF prints the marker [B7.15, B7.16]. The release's exchange-code citation [T3.09–T3.12] is no longer an identity rule (Sol review 1, finding 1). The statement page's text layer is OCR-corrupted: "Operotinq expenses le)+(f)", "Tax expense !a)+(h)" [T3.19, T3.20]; "Operatinq expenses (e)+(f)" [T3.21]. Statement-line parsing on it is not evidenced. | XBRL-only package and staged inputs. The PDF is retained as the `REPORTING_FRAMEWORK` setting's evidence input. Its statement claims read `NOT_ASSESSED`; it is not a member. No `config/runs/icicibank-<period>.yaml`, no `pdf/v4/`, no `--member pdf`. The PDF extractor still bumps in Task 5, because `member_identity.py` changes. |
| B8 | P&L present, **anchors do not match**; BS and CF present at the acceptance period, absent at Q1; segment present | P&L concepts at `OneD` and `FourD` [B8.17–B8.19, B8.27; T3.01, T3.02]. The v2 PL fields are absent [B8.21, B8.22]. BS fits v2 through `Assets` [B8.29]; CF fits [B8.31, B8.32]; segment fits [B8.20]. Q1 has no BS or CF [B8.40–B8.43, B8.51–B8.54]. | **Anchor:** Task 8 creates `statement_anchors/v3.yaml` with one PL anchor: `schema_identity` of the 2026-01-31 in-capmkt namespace, `native_fields: [InterestEarned, ProfitLossFromOrdinaryActivitiesBeforeTax]`, `DURATION_ENDING_AT_PERIOD_END` [B8.18, B8.19]. v11 lists it beside v2, and it joins the XBRL extractor pin. Q1's absent BS and CF are capability `UNSUPPORTED`, with rules unchanged. The acceptance period is 2026-09-30 (Evidence pins), where all four statements are present. |
| B10 | **B10a** | `LevelOfRounding`, `DescriptionOfPresentationCurrency`, `DateOfStartOfFinancialYear` and `DateOfEndOfFinancialYear` are at `OneD` in all four instances [B10.01–B10.16]. `OneD` declares the reporting-period end [B3.04, B3.09, B3.14, B3.19]. | **B10:** no change; B10b struck. That `_declared` reads a `Banking` instance at all is Task 5's form change, not B10. |
| B9 | pending | — | Task 12. |

**B4 ruling: B4b, not B4c.** Two places decide identity schemes, both from the seeded constants
of `extraction/xbrl/xbrl_identity.py:7–13`:
- `member_identity.verify_xbrl_identity`, which maps scheme to expected ids through
  `expected_by_scheme` at `:129–133` and rejects any other scheme as `_UNKNOWN_SCHEME`;
- `onboarding/verification.xbrl_entity_state`, whose `by_scheme` at `:227–230` does the same.

Today both would refuse the Q1 instances. The scheme is not an unknown identity. Every identifier
under it is the instance's own `Symbol` value and the master's symbol [B4.20, B4.24, B4.25]. It
sits under the SEBI `in-capmkt` identifier host whose `ScripCode` scheme is already seeded. So it
is an evidenced alias of the NSE-symbol identity, not a new identifier. B4c would apply if any
identifier under it differed from the seed.
`ACCEPTED_NSE_ENTITY_SCHEMES` and `validate_nse_entity_identities` are left unchanged. They are
used only by `sourcing/exchange/xbrl_source.py` and `interface/workflows/comparatives.py`, which
are off the onboarding and ingest paths.
**Pins:** `xbrl_identity.py` is hashed by `SHP_EXTRACTOR_SOURCES` (`run_config.py`), and
`member_identity.py` by the XBRL, PDF and SHP extractors. All three bump once in Task 5, so B4b
adds no bump.

### Amendment A7 (revised, fix rounds 1 and 2): PDF identity by a bound issuer declaration — not met

Sol review 1 (finding 1) rejected the first A7, under which both exchange codes could appear
anywhere in the PDF. That rule accepted another company's PDF that mentions the bank, an
appended unrelated release, and code prefixes such as `NSE: ICICIBANK.X`. The revised rule
below states what would associate a results PDF with the issuer. **The retained PDFs do not
satisfy it, so B1c stands.** The rule is recorded so that a later amendment can be checked
against it. It is not to be weakened to fit these PDFs.

**Rule.** Page 1's `Scrip Symbol :` line decides as today when it is present. Otherwise, a
results PDF is associated with the issuer for a requested basis and period end only when one
*statement block* of the PDF carries all four of the following. A statement block runs from a
page whose title block carries that basis's results heading up to the page before the next page
that carries a results heading for any basis, or to the end of the document.
1. **Issuer.** On the block's first page, a whole text line above the basis heading (by
   `PdfPage` line geometry) equals the issuer's name. Comparison ignores case and collapses
   whitespace. Equality is whole-line, so a line that merely contains the name never matches,
   for example "ICICI Bank Limited (NSE: …)", "ICICI Bank Limited Employees Trust", or the name
   inside another issuer's sentence. *Supporting source association:* the name never comes from
   the PDF or the announcement listing. It is the name concept (`NameOfTheCompany`, or
   `NameOfBank` under B4b) of the same package's instance, for the same basis and period end, and
   that instance must already have passed `verify_xbrl_identity` against the seeded ISIN, symbol
   and scrip. The seeded identifiers alone carry no name.
2. **Basis.** The basis heading (e.g. `STANDALONE FINANCIAL RESULTS`) is a whole line on that same
   page.
3. **Period** (rewritten in fix round 2, Sol review 2 finding 2). Each requested *current*
   reporting interval binds to exactly one column of the block's statement page. The current
   intervals are the instance's current-period contexts: for the 2026-09-30 package, Q
   2026-07-01..2026-09-30 and H1 2026-04-01..2026-09-30; for the 2026-06-30 package, Q
   2026-04-01..2026-06-30. A column binds when its printed heading, read by the generic reader
   from page and column geometry, yields that interval: start and end, or a duration phrase and
   end that fix both. An end date alone does not bind. The heading may be one line or a header the
   reader assembles from stacked lines and a duration group shared over several columns. No date
   comes from the expected answer, covering-letter prose or note sentences. Current Q and H1
   share an end date; their durations tell them apart, and that is not a conflict. Other columns
   are allowed as *comparatives* when their heading is read and labels a different period (prior
   quarter, prior-year quarter or half-year, prior year). Comparatives bind nothing.
4. **Framework.** The framework declaration (B1's phrase) occurs inside the block, with that basis
   as its subject.

**Contradiction checks (each rejects).** Another title block for the same basis names a
different entity, or names none. A requested current interval is missing (no column binds
it), ambiguous (more than one column binds it, or a column that could be current has a heading
the reader cannot resolve to one interval, such as an end date with no duration), or conflicting
(two current headings disagree, or a current heading disagrees with the instance's interval). A
comparative column whose heading cannot be read is ambiguous. These checks run in full after a
positive match; a matching current column never waives them. Another block declares a framework for the same basis. A page-1 marker names another symbol.
Title blocks of other bases are not compared. In the Q2 PDF, the consolidated title block reads
"ICICI Bonk Limited" (OCR) [T3.54]. A document-wide name check would reject on that OCR error, and
fuzzy matching would weaken the rule.

**Limit.** The rule associates text inside one document with an identity-verified instance. It
does not authenticate the document. A forged PDF that copies the issuer's title block and
headings passes. Provenance would be the defence; its ISIN route is not proved (route (b),
below).

**Evidence against the retained PDFs.**

| Requirement | Q2 PDF `b28a7191…` | Q1 PDF `1b3599e2…` |
|---|---|---|
| 1 Issuer | met: p3 "ICICI Bank Limited" above "STANDALONE FINANCIAL RESULTS" [T3.49]; instance name "ICICI BANK LIMITED" [B4.10] | met: p3 [T3.50] |
| 2 Basis | met [B7.02, T3.49] | met [B7.10, T3.50] |
| 3 Period | **not bound.** No line on p3 prints a date [T3.51]. The column headers split the month from "30, 2026" across lines, and the current reader binds no column (route (a) probe, below). The block's other dates occur only in note sentences, e.g. p8 "during six months ended September 30, 2026" [T3.53] | **not bound.** No line on p3 prints a date [T3.52]; the reader binds no column (probe) |
| 4 Framework | met: p7, "Notes on standalone financial results" [B1.05, T3.15]; block p3–p12, next heading p13 [B7.08] | met: p6 [B1.09, T3.17]; block p3–p10, next heading p11 [B7.14] |
| Contradictions | none in the standalone block | none in the standalone block |

**Exactly what is missing:** the current Q and H1 intervals (Q only at 2026-06-30), each bound to
one column of the issuer-titled statement page by the generic reader. The only full period
heading is page 1 [B7.01, B7.09], in the covering letter, outside the block. Each of the
following would weaken the rule, so none is taken: binding the covering letter to the block
through its "Annexure I" enclosure outside route (b)'s reviewed association, matching a date
anywhere in the block (the note sentences above), or feeding a hand-assembled header to
`header_period` (that proves no column association). B7 found statement-line parsing unevidenced
on these OCR pages [T3.19–T3.21].

**Release routes (Sol review 2 rulings).** Each route needs its own reviewed amendment. **None
releases the Task 8 mapping-isolation stop**, which binds separately (Task 8).

- **(a) Generic statement-header binding.** Acceptable in principle; not proved. It needs the
  actual reader, with reviewed generic configuration, to bind the issuer-titled standalone
  statement page to the framework notes in the same unambiguous block, and to recover the
  requested current intervals (Q2: Q 2026-07-01..2026-09-30, H1 2026-04-01..2026-09-30; Q1: Q
  2026-04-01..2026-06-30). An end-date substring alone is insufficient. The proof retains page and
  column geometry and the assembled header text, distinguishes duration groups from comparatives,
  rejects missing, ambiguous and conflicting current headers, and keeps the issuer, basis and
  contradiction checks. A generic reconstruction of a printed header can meet item 3. No date
  comes from the expected answer, covering-letter prose or note sentences. Header-only success
  does not promote PDF statement amounts from `NOT_ASSESSED` or add a PDF package member.
  **Current evidence: the reader refuses both PDFs on current main**
  (`scratchpad/vendor-first/live-p3-1/period-probe/probe.py`; output `probe-output.txt`, sha256
  `9beead81e3702a3687d198158fa4daa2f16655d22eba25dcb5d1aad327ddafbb`). With Apar's settings,
  `locate_statement` finds no page. With bank settings built in memory, `_bind_columns` finds 0
  basis super-headers at `pdf_statement_pages.py:626` (Q2 p3 column group 210–259; Q1 p3 group
  328–378). Past that refusal, the shared "Three months ended" heading attaches only to the column
  it overlaps: the current-quarter and prior-year-quarter columns read as instants ("September 30,
  2026" and "September 30, 2025" on Q2 p3; "June 30, 2026" and "June 30, 2025" on Q1 p3). Route (a)
  therefore needs a reviewed reader change before any binding. A later reader revision is
  reviewed and pinned with its complete probe; success is never attributed to current main.
- **(b) Provenance with ISIN reconciliation.** Acceptable in principle; not proved. Each results
  PDF's announcement-listing row reads ISIN `INE090A01013` [T3.13, T3.14], not the master's and
  instances' `INE090A01021` [B4.25, B4.01]. It needs retained authoritative evidence of the
  relationship between the two ISINs for the same issuer, with validity dates and identifier
  roles, recorded explicitly; an unexplained mismatch is never whitelisted. It also needs the
  exact announcement-to-attachment URL and hash chain, and the attachment's period, basis and
  framework association. ISIN reconciliation settles identity only: "Outcome of Board Meeting",
  retrieval or broadcast time, or the symbol-filtered query establish no reporting period. Both
  covering letters enclose the standalone and consolidated results for the named periods as
  Annexure I (p1); a provenance amendment may use a reviewed generic association between that
  enclosure and its results and notes, amending item 3 explicitly rather than bypassing it.
  Unrelated or appended attachments, stale-period results and contradictory declarations reject.
  The chain is kept as evidence through ingest, reuse and fallback. The CIN on page 1 and page 3
  is not a seeded identifier.
- **(c) Replacement filing.** Acceptable in principle if the retained replacement passes the
  issuer, basis, current-period, framework and contradiction rules above. Changed capture pins
  need re-grounding and review; a printable date alone is insufficient.

**Implementation, if released.** Task 5, in `member_identity.verify_pdf_identity`. It takes the
verified instance's name as an argument, and its constants sit beside `PDF_SYMBOL_MARKER`.
Discovery's P-arm check and `_read_xbrl`'s ingest re-check pass the name. **Tests** (Task 5; unit,
matching logic; synthetic pages unless marked):
- a third-party mention rejects: another issuer's title block, whose notes read "Our lender is
  ICICI Bank Limited (NSE: ICICIBANK, BSE: 532174)";
- an appended unrelated release rejects: another issuer's statement block, followed by the bank's
  news release;
- conflicting issuer declarations reject: two standalone title blocks that name different
  entities;
- identifier boundaries: a title line "ICICI Bank Limited Employees Trust" rejects; a title line
  "icici bank limited" in another case verifies;
- current Q and H1 sharing an end date: "Three months ended" and "Six months ended" over
  September 30, 2026 bind Q 2026-07-01..2026-09-30 and H1 2026-04-01..2026-09-30, one column each;
- comparative columns: prior-quarter, prior-year quarter and half-year, and prior-year columns
  beside the current ones verify and bind nothing;
- a missing current header rejects: the H1 column is absent, or its heading is unreadable. The
  retained PDFs (`retained`), whose columns the current reader binds to no heading, reject today;
- genuinely conflicting current headings reject: two columns both read as the current quarter
  with different starts, or a current heading whose interval differs from the instance's;
- an ambiguous current column rejects: a column that could be current reads as an end date with
  no duration;
- a page-1 marker naming another symbol rejects; Apar's retained PDFs verify through the marker as
  before (existing suite).

**Pins.** `member_identity.py` is content-pinned by the XBRL, PDF and SHP extractors. They already
bump once in Task 5, so a released A7 adds no version. Landing it after Task 10 would bump again
(F08 rule).
**Spec wording for Task 9** (`docs/specs/2026-11-06-vendor-first.md` §8), only once released. The
first A7 sentence, "with no other exchange code cited", is withdrawn. It contradicted the
`NYSE: IBN` code that the documents cite.
- intro, after "`UNKNOWN`": "; Phase 3 adds `INDIAN_GAAP`".
- step 2, first sentence: as in the first draft (the `INDIAN_GAAP` declaration quote).
- steps 2 and 4 paragraph, after "a Banking form alone is not a substitute for that declaration.":
  "A results PDF is associated with the issuer by its page-1 `Scrip Symbol :` line or, absent that
  line, by one statement block whose title block names the issuer, as the package's
  identity-verified instance names it, above the basis heading, and which carries the period
  heading and the framework declaration. Text matching does not authenticate the document."

## Version and pin inventory (F08, F09, F11)

| Pin | Bytes changed by | Consequence |
|---|---|---|
| `XBRL_EXTRACTOR_VERSION` (hashes `member_identity.py`, `first_party_extract.py`, `xbrl_taxonomies.py`) | Task 5; ~~Task 8 on B3b~~ | bumped once in Task 5 (F08 rule below) |
| `PDF_EXTRACTOR_VERSION` (hashes `member_identity.py`, `first_party_extract.py`) | Task 5 | `pdf-occurrences/5` (the base) → `/6` once, in Task 5 (F08 rule below) |
| `SHP_EXTRACTOR_VERSION` (hashes `member_identity.py`, `xbrl_identity.py`) | Task 5 (B4b edits both) | bumped in Task 5 |
| Screener financials extractor (`vendor_screener.EXTRACTOR_VERSION`; hashes `screener_session_models.py`, `screener_session_page.py`) | Task 5 (`BasisTopology.consolidated_published`, R2-04) | `screener-v1` → `screener-v2` in Task 5 |
| Screener shareholding extractor (`vendor_shareholding.SCREENER_VERSION`; hashes the same two files and `vendor_shareholding.py`) | Task 5 (same edit; the constant's bump edits `vendor_shareholding.py`) | `screener-shp-v2` → `screener-shp-v3` in Task 5; stored Screener SHP pins stay; a later SHP run re-ingests (Apar follow-up, Interactions) |
| Tijori shareholding extractor (`vendor_shareholding.TIJORI_VERSION`; hashes `vendor_shareholding.py`; `run_config.py:132–139`) | Task 5 (the `SCREENER_VERSION` edit changes this file's bytes, R4-02) | `tijori-shp-v2` → `tijori-shp-v3` in Task 5; stored pins stay; a later Tijori SHP run re-ingests (Apar follow-up) |
| Upstox shareholding extractor (`vendor_shareholding.UPSTOX_VERSION`; hashes `vendor_shareholding.py`; `run_config.py:140–146`) | Task 5 (same, R4-02) | `upstox-shp-v2` → `upstox-shp-v3` in Task 5; stored pins stay; a later Upstox SHP run re-ingests (Apar follow-up) |
| Tijori vendor extractor (`VENDOR_EXTRACTORS`) | Task 12 (display loaded from the mapping set) | bumped in Task 12 |
| `formula_set_version` | Task 6 (`derived.yaml` applicability) | v5 `metadata.yaml` declares `formula_set_version: v4` (dictionary v3 and the rebased v4 declare v3; formula set v4 is new) |

No smaller design avoids the shareholding bumps (R4-02). The flag must live in
`screener_session_models.py`, because a standalone-only topology rejects a correctly marked page
(`screener_session_page.py:220–226`) and no consolidated warehouse id is known at onboarding.
`screener-shp` hashes that file (`run_config.py:104–127`), so it must bump. `SCREENER_VERSION` is
read only by `run_config.py`, but declaring it there would leave a stale v2 constant in
`vendor_shareholding.py`. Removing that constant would change the same hashed bytes anyway.
| `_SEMANTICS_VERSION` (`run_config.py:195`) | Task 7 (framework and issuer applicability change how inputs become results) | bumped; `require_pins` refuses an earlier semantics pin |
| mapping set content | Task 8 (v11; B7a `pdf/v4/`), Task 12 (v12, names `tijori/v6/display.yaml`) | the display file joins the set's content hash via the new `display_file` key; no constructions file changes (a needed one would be `constructions/v4`) |

**F08 rule (Sol confirmed).** One development version per extractor may span Tasks 5–8 while its
bytes are unfinalised and pinned only in disposable `eqos_test_*` databases (recreated when bytes
change). Any durable pin of it (live, a retained rehearsal copy, another phase's use) before its
bytes are final forces a new version; "Task 11 has not run" is not proof that none exists — Task 10
queries for it. Any edit after Task 10's gate bumps again.

No compatibility hash alias. Old stored evidence keeps its pins; replaying a pre-Phase-3 run at the
new code is refused by version, never recomputed (historical replay needs the old checkout).

## File map

| Path | Change | Task | Responsibility |
|---|---|---|---|
| `equity_os/sourcing/exchange/results_filing.py` | modify | 1, 7 | public `retain`, entity-free `results_pdfs` (1); `acquire_results(..., source)` (7) |
| `equity_os/companies/onboarding/grounding.py` | create | 1 | candidate rows, retained bodies, structure JSON |
| `equity_os/interface/commands/companies/ground_cli.py` | create | 1 | `--ground` handler, generation write and replay |
| `onboard_cli.py` | modify | 1, 5, 7, 12 | route `--ground` (1); bank pins, flags, one call into `bank_onboarding` (5); entity framework (7); display from the set (12) |
| `equity_os/contracts/sourcing/source_catalog.py` | modify | 1, 5 | `nse-grounding` surfaces (1); bank first-party XBRL sources and PDF surface (5) |
| `docs/evidence/vendor-first/icicibank-grounding.md` | create | 2, 3 | record, reading, ledger, evidence pins |
| `docs/plans/VENDOR-1-P3.md` | modify | 3, 12 | branch resolution; B9 addendum |
| `equity_os/contracts/companies/issuer_class.py` | create | 4 | `IssuerClass` |
| `equity_os/companies/identity/identity_seed.py` | modify | 4 | two setting keys, `OWNER_DECISION` |
| `equity_os/contracts/measurement/observation.py` | modify | 4 (B1b) | one `AccountingFramework` value |
| `migrations/0050_issuer_class.sql` | create | 4 | settings-key and evidence-kind CHECKs |
| `equity_os/companies/onboarding/{verification,discovery,derived_settings}.py`, `nse_filings.py` | modify | 5 | form, framework, identity, bank PDF acquisition, analysis-basis selection, basis status, B6b, B10b; `derived_settings.framework_evidence` reader (R2-01); `screener_topology(..., configured)` and `discover`'s configured topology (R2-04) |
| `equity_os/interface/commands/sourcing/screener_page_cli.py` | modify | 5 | `watchlist_topology(config_root, symbol)` (R2-04) |
| `equity_os/extraction/vendors/screener/screener_session_models.py`, `vendor_screener.py`, `extraction/surfaces/vendor_shareholding.py` | modify | 5 | `BasisTopology.consolidated_published` (R2-04); the two Screener extractor bumps; the Tijori and Upstox shareholding bumps (R4-02) |
| `equity_os/extraction/packages/{member_identity,capture_intake}.py` | modify | 5 | bank form predicate, PDF framework evidence, B1b phrases; `xbrl_source_id(issuer_class, basis)`; refuse `nse-grounding` members |
| `equity_os/extraction/packages/{first_party_extract,first_party_ingest}.py` | modify | 5 | `IngestRequest.framework_evidence`; `_read_xbrl` verifies with it on fresh extraction and reuse; its sha256 joins the extraction context (R2-01) |
| `equity_os/companies/onboarding/bank_onboarding.py` | create | 5 | decision binding, issuer-class inputs, pin choice, `stage_inputs` (R2-02) |
| `equity_os/contracts/companies/onboarding.py` | modify | 5 | `BANK_ONBOARDING_VERSIONS` |
| `config/companies/basis_decisions/icicibank.yaml` | create | 5 | the decision binding |
| `equity_os/verification/admission/vendor_first.py` | modify | 4, 5 | `IssuerClass.NON_FINANCIAL` (4); `issuer_class` per reading 4 (5) |
| `equity_os/verification/comparison/run_config.py` | modify | 5, 7, 12 | extractor bumps (5); semantics (7); Tijori extractor (12) |
| `config/normalisation/dictionary/v5/*` | create | 6 | v4 plus issuer applicability and bank rows |
| `equity_os/normalisation/dictionary/{dictionary,applicability}.py` | modify | 6 | `issuer_applicability`, context `issuer_class` |
| `equity_os/verification/comparison/engine_issuer_context.py` | create | 7 | `issuer_context(settings, entity_id, period_end, cutoff)` |
| `equity_os/verification/comparison/{engine,engine_vendor_context,run_family,fact_view}.py` | modify | 7 | pass the context where keys, packages and lookups are chosen (engine net ≤ +10) |
| `evidence_cli.py`, `vendor_reingest.py`, `verification/admission/fallback.py` | modify | 7 (+12 `vendor_reingest`) | entity framework, framework evidence and source; reingest's Screener binding via `verification.screener_topology` with the issuer's watchlist topology (R2-04); display from the set (12) |
| `config/normalisation/mappings/xbrl/v6/*`, `statement_anchors/v3.yaml` (B8), `pdf/v4/results_layout_banking.yaml` (v11 also lists the unchanged `pdf/v3/results_layout.yaml`) and `config/runs/icicibank-<period>.yaml` (B7a), `mappings/v11.yaml` | create | 8 | bank first-party entries and set |
| `equity_os/extraction/xbrl/xbrl_taxonomies.py` | modify | 8 (B3b) | evidenced `TaxonomySpec` |
| `equity_os/normalisation/mapping/mapping.py` | modify | 12 | optional `display_file` set key |
| `config/normalisation/mappings/{screener/v5,tijori/v6}/financials_banking.yaml`, `tijori/v6/display.yaml`, `mappings/v12.yaml` | create | 12 | bank vendor supplements and set |
| `docs/specs/2026-11-06-vendor-first.md`, `docs/specs/2026-10-11-canonical-financial-data-and-cross-source-comparison.md`, `CONTEXT.md` | modify | 9 | contract changes Task 3 makes; §10 Phase 3 lines; glossary |
| `docs/evidence/vendor-first/phase-3-report.md` | create (after `APPROVE`) | 13 | measured counts, no vendor value |

`interface/entry/cli.py` is not touched (Phase 1 Task 9 owns it): grounding routes through the
`onboard` parser. Tests live under `tests/equity_os/<bucket>/<sub-bucket>/` beside their modules.

## Task 1: Grounding command

Goal: `eqos onboard ICICIBANK --ground --structure <path> --raw-root R --snapshot-root S
{--acquire | --generation N}` retains, for the latest two listed integrated periods, every basis's
candidate instance and each period's results PDFs under the `nse-grounding` surfaces, and writes a
structure JSON, with no validation call and no entity, onboarding, settings, intake, package or
interpretation row.

Files:
- Create: `grounding.py`, `ground_cli.py`
- Modify: `results_filing.py` (`_retained` → public `retain`; add `results_pdfs`; `acquire_results`
  calls `retain` unchanged), `source_catalog.py`, `onboard_cli.py` (`--ground` and `--structure`
  on `add_onboard_parser`; `dispatch_onboard_command` hands off before `onboard()`)
- Test: `tests/equity_os/companies/onboarding/test_grounding.py` (`pg`, replay of the retained
  HDFCBANK dev fixtures as a stand-in bank)

Interfaces:
- Consumes: `listing_url`, `listing_rows`, `collapse`, `LEGACY_LISTING`, `INTEGRATED_LISTING`;
  `acquiring_fetch`, `replay_fetch`, `write_generation`, `EQUITY_MASTER_URL`, `master_rows`;
  `first_party_documents.nse_listing_url`, `observed_link`, `document_request`.
- Produces: `retain(conn, store, fetch, unit, pair, url) -> Response | None`;
  `results_pdfs(conn, store, fetch, symbol, span, pair) -> list[tuple[str, Response]]`;
  `ground(conn, store, fetch, symbol) -> dict` (the structure JSON).

Approach: master row → ISIN; both listings; the latest two period ends with any integrated row;
per (period, basis) `collapse` over integrated rows of every `type`. A unique latest row with an
instance URL is fetched; a tie, missing broadcast or missing URL is recorded `UNRESOLVED` and not
fetched. PDFs: `results_pdfs` from each period end to seven days after its latest broadcast, every
results-category PDF retained and listed, none chosen. Acquisition writes a generation folder
(authorization "VENDOR-1 §8 step 1 grounding"); `--generation N` replays it. The structure JSON,
read by code from the retained bytes, holds only branch evidence (F21):
- per instance: capture sha256, basis, period end, collapsed row `type`, schemaRefs, root and fact
  namespaces, IntegratedFinance form segments, per fact QName its `contextRef`, period and
  dimension members (no amounts), text-block QNames with their text, identity, rounding, currency
  and fiscal-year-end facts with values and contexts, the taxonomy's scope and period concepts;
- per PDF: capture sha256, filed time, text-layer flag per page, lines carrying a
  `FRAMEWORK_DECLARATIONS` phrase, "prepared in accordance with", `Scrip Symbol :`, or a period or
  basis heading.

Verification: replay test asserts the capture rows; no row in `reporting_entities`,
`onboarding_records`, `settings_records`, `evidence_inputs`, `document_observations`,
`filing_packages` or `interpretations`; the JSON names the `Banking` form; a run with `discover`,
`verify_xbrl_*` and `verify_pdf_*` patched to raise still passes (no validation call, F25); a tied
row is `UNRESOLVED` and unfetched; a replay missing the PDF retains the XBRL and reports the PDF
absent; an `nse-grounding` capture offered as a package member is refused by intake. Ruff, mypy
strict on the touched modules.

Dependencies: none beyond `main`.

## Live protocol (Tasks 2, 11 and 13)

Phase 1's live protocol (`VENDOR-1-P1.md`, steps 1–6) applies, with three additions.

**Acquisition boundary (F15).** A fetching command (Task 2 `--ground --acquire`, Task 11
`onboard --acquire`) runs once, as an acquisition, against a throwaway `eqos_test_*` restored from
the baseline backup with scratch copies of the snapshot and raw roots. Its generation folder (every
request and response with sha256) is the retained response manifest. The rehearsal (fresh restore,
fresh root copies) and live run the same command in replay mode (`--generation N`), so inputs are
identical by construction; the generation manifest's sha256 is in `commands.txt`. A drift restart
replays the same generation. Delta normalisation stays ids and timestamps only. After each command,
the new files under the snapshot and raw roots (path, sha256), including Task 11's staged inputs
under `<raw-root>/inputs/`, are listed; live's must equal the rehearsal's.

**Allowlists (F14).** Fixed in `commands.txt` before the rehearsal from this table, never widened
from rehearsal output; each listed table's own sequence may advance, no other.

| Command | Tables allowed to change |
|---|---|
| `db migrate` (0050) | migration ledger; the `settings_records` and `evidence_inputs` CHECKs; the `framework` CHECKs of `filing_packages`, `acquisition_attempts`, `interpretations` and `results` (B1b) |
| `onboard --ground` replay | captures: `capture_refs`, `capture_addresses`, `retention_classes` (trigger; `nse-grounding` `NSE_XBRL_INSTANCE` → `EXCHANGE_REFETCHABLE`, `NSE_RESULTS_DOCUMENT` → `COVERED` by `base_class`) |
| `onboard` replay | identity: `reporting_entities`, `securities`, `listings`, `identifier_relationships`, `identity_events`, `identity_event_edges`, `namespace_verifications`; onboarding: `onboarding_records`, `settings_records`, `evidence_inputs`, `evidence_input_captures`, `entity_basis_status`; captures as above (new exchange and vendor captures); package: `filing_packages`, `package_members`, `package_statements`, `package_statement_evidence`, `segment_members`, `segment_member_evidence`; extraction: `occurrences`, `interpretations`, `interpretation_operands`, `interpretation_condition_evidence`, `acquisition_attempts`; vendor: `vendor_values`, `vendor_outcomes`, `vendor_parser_versions`, `vendor_basis_bindings`; `version_pins`; conditional: `calculation_traces`, `calculation_trace_operands`, `construction_traces` (`put_interpretations`, when a v11/v12 construction or Screener construction fires at ingest) |
| `evidence ingest` | package and extraction tables as above; `version_pins`; conditional: captures as above (a staged member not yet registered; a registered one advances only the `capture_refs` sequence), `calculation_traces`, `calculation_trace_operands`, `construction_traces` (`put_interpretations`) |
| `vendor reingest` (`ingest_vendor_retained`) | `acquisition_attempts`, `occurrences` (`put_generation`; a new generation under Task 12's Tijori bump), `interpretations`, `interpretation_operands`, `interpretation_condition_evidence`, `version_pins`; conditional: `calculation_traces`, `calculation_trace_operands`, `construction_traces` (constructions); `capture_refs` sequence only (`put_capture_ref` re-registers an existing capture, `ON CONFLICT DO NOTHING`, no row) |
| `compare run` | `runs`, `run_versions`, `run_inputs`, `results`, `result_source_values`, `result_surfaced_restatements`, `calculation_traces`, `calculation_trace_operands`, `construction_traces`, `pair_outcomes`, `alignment_proofs`, `alignment_proof_participants` (`resolve.py`), `queue_items`, `queue_item_inputs`, `queue_item_traces`, `queue_run_items`, `version_pins`; conditional: `pair_adjustments` (`run_store.py`, applicable adjustments), `definition_sets`, `definition_records` (`run_config.pin_config`; rows or sequence effects when v5/v12 definitions are first published) |

`evidence ingest` writes no `vendor_*` table; `vendor reingest` writes none either (those belong to
the vendor-surface path). No command here writes `capture_states`: a registered capture is
`RETAINED` with no state row (0028); only purge and refetch write it. Conditional rows may be
absent; a listed table's sequence may advance without a row.

**Trigger reconciliation (R2-03).** This is an inventory of `eqos` business tables, the scope of
the inherited allowlist (`VENDOR-1-P1.md`). Queue and clock helpers also write
`eqos_clock.queue_locks` and `eqos_clock.transaction_times` (0009, 0005). The read-only
`check_operand_decision` guard (0013) locks and checks only. Neither changes the allowlists. Across
migrations 0001–0049, one trigger writes another `eqos` business table on these commands' paths: `classify_capture` (0027, `AFTER INSERT ON capture_refs`) inserts the
`retention_classes` row, hence that table wherever a new capture can register. It does not fire
on reingest's `ON CONFLICT DO NOTHING` re-registration, which inserts no row. The other triggers on
written tables check or stamp the inserted row and write nothing else: `check_operand_capture`,
`check_operand_ordinal`, `check_queue_input_seal`, `record_queue_time`, `a0_retention_guard` and the
`reject_*` mutation guards. `tombstone_vendor_labels` fires only on `licence_ends`, which none of
these commands writes. Before each rehearsal (Tasks 2, 11, 13) the orchestrator repeats this check
over any migration landed after 0049.

Before its rehearsal, Task 11 confirms the onboarding row against onboarding's final
write paths (`record`, `store_captures`, `derive`, `_ingest`, the PDF member and binding paths,
vendor capture), and Task 13 re-derives its three rows from the final call paths (ruling 3). A
missing legitimate table is a reviewed plan amendment before the rehearsal; a rehearsal never
widens a list.

**Rehearsal-only segment.** Admissions and the Apar regression run on the rehearsal copy only after
every live-equivalent command's delta is recorded, with their own inventory; their writes never
enter a live expected delta.

**Windows.** No Phase 3 live task runs between a Phase 1 Task 13 or 14 (or any other phase's)
baseline and its last live command, or the reverse; each Task 2, 11 and 13 takes its own backup and
rehearsal and restarts on drift. Task 11 requires Phase 1 Task 13 done (0047, 0048 and 0049 live).
Logs in `scratchpad/vendor-first/live-p3-<n>/`.

## Task 2: Live grounding and the grounding record

Goal: ICICIBANK's latest two integrated periods (every listed basis) and their results PDFs are
retained in live under `nse-grounding`, and `docs/evidence/vendor-first/icicibank-grounding.md`
records the evidence for B1–B8 and B10, before any onboarding check runs.

Files: create the record. Not committed: logs, generation folder sha, structure JSON in
`scratchpad/vendor-first/live-p3-1/`.

Commands: acquisition `eqos onboard ICICIBANK --ground --acquire ...` on the throwaway copy; then,
rehearsal and live, `eqos onboard ICICIBANK --ground --generation N ...`. Allowlist: the grounding
row above.

Approach: the facts section is generated by code from the structure JSON. The reading section
(Opus drafts) states, per branch B1–B8 and B10, the supported arm, each claim with its locator:
capture sha256, basis, period, and QName with `contextRef` or page with quote. A code check
confirms every locator resolves in the retained capture; a page without a text layer reads
`NOT_ASSESSED`. The record states which evidence is prior HDFCBANK fixture evidence and which is
ICICIBANK's, the generation sha, and the time grounding completed.

Verification: protocol passes; locator check exits 0; a read-only query shows the captures and no
ICICIBANK entity; capture sha256s match the retained blobs; the log shows grounding completed.

Dependencies: Task 1; windows rule.

Risks: an `UNRESOLVED` candidate or missing PDF is recorded, never resolved by choice; it decides
B6c, B7b or a stop at Task 3.

## Task 3: Branch resolution, ledger and evidence pins (plan amendment)

Goal: B1–B8 and B10 are fixed by cited record lines (B9 stays pending for Task 12); the record
carries the frozen expected-key ledger and the pinned acceptance evidence; this plan says which arm
each later task implements.

Files: modify this plan ("Resolved branches"; arms not taken struck from Tasks 4–8) and the record
(two appended sections):
- **Ledger** (F12, F13, R2-05): for every key the acceptance run will enumerate in its family and
  scope (dictionary v4's keys plus each bank row Task 6 is to add, named from the record; each
  excluded family named with its disposition), per period kind and basis, two separate columns:
  *capability* (`SUPPORTED`, or `UNSUPPORTED` with reason) and *expected result*: `VALUE`;
  `NOT_APPLICABLE` with its rule (`ISSUER_RULE_ID` for issuer-excluded rows; the unchanged
  period, disclosure or basis rule otherwise, e.g. `total_assets` in a Q1/Q3 filing with no
  balance sheet under `results.balance_sheet`); or refusal with its stated reason (an applicable
  key the filing cannot supply). Plus the admissible cells expected to admit on the rehearsal
  (§6.5 rows 1, 2 or 5).
- **Evidence pins** (F16): the two period ends, analysis basis, instance sha256 per period and
  basis, and the PDF sha256 (B7a or B1′ P).

Approach: the orchestrator maps each record line to an arm and decides the parser, anchor and
B10 consequences explicitly. Stop arms halt the phase; only B5c consolidated-only is an owner
question. Sol reviews the amendment as a plan review, checking each claim's meaning (unit, scope,
basis, period), not only that its quote exists. If the contract text changes (e.g. the B1b
framework name), the amendment carries the spec wording and Task 9 applies it.

Verification: every arm and ledger line cites a record locator; every `NOT_APPLICABLE` line names
the rule that returns it (a v4 rule id, or `ISSUER_RULE_ID` for an issuer exclusion this
amendment fixes); Sol `APPROVE`. The approved ledger is then frozen: its sha256 is recorded in the
record and this plan. It is written from the evidence alone. No code reads it before Task 6, and
nothing derived from the implementation ever changes it (R3-01).

Dependencies: Task 2.

## Task 4: Contracts and migration

Goal: the store and contracts can hold an issuer class, an analysis basis with owner-decision
evidence and (B1b) the bank framework.

Files:
- Create: `issuer_class.py`, `migrations/0050_issuer_class.sql`
- Modify: `identity_seed.py`, B1b `observation.py`, `vendor_first.py` (`IssuerClass.NON_FINANCIAL`)
- Test: the migration suite (upgrade from 0049; the CHECKs reject an unknown key and kind)

Approach: 0050 replaces the two CHECKs with their lists plus the new values (as 0022 did), and
(B1b, Task 3) the four 0001 `framework` CHECKs (`filing_packages`, `acquisition_attempts`,
`interpretations`, `results`) with their list plus `INDIAN_GAAP`; no table, no backfill. Existing
0049 untouched. The migration test also shows each widened CHECK accepts `INDIAN_GAAP` and still
rejects an unknown framework.

Verification: `scripts/verify.sh` migration tests on `eqos_test_*`; mypy, ruff.

Dependencies: Task 3.

## Task 5: Bank onboarding

Goal: `eqos onboard ICICIBANK --analysis-basis standalone --basis-decision
config/companies/basis_decisions/icicibank.yaml` onboards as `BANK` with the evidenced framework,
standalone filings verified, the evidenced basis status, under the bank pins; BAJFINANCE (NBFC) and
HDFCLIFE (insurer) still end `UNSUPPORTED`; Apar onboards as before under `ONBOARDING_VERSIONS`.

Files:
- Create: `bank_onboarding.py`, `config/companies/basis_decisions/icicibank.yaml`
- Modify: `verification.py` (`financial_rule` → `issuer_form`; B4b: `NameOfBank` for `BANK`, the
  `in-capmkt/Symbol` scheme in `xbrl_entity_state`), `xbrl_identity.py` (B4b:
  `SEBI_SYMBOL_ENTITY_SCHEME`), `member_identity.py` (bank form in `verify_xbrl_framework`; PDF
  framework evidence; B1b `INDIAN_GAAP` phrase; B4b scheme in `verify_xbrl_identity`; A7 in
  `verify_pdf_identity`), `discovery.py` (classification
  across filings, analysis-basis selection, bank sources, bank PDF acquisition via `results_pdfs`
  under the first-party documents surface), `nse_filings.py` (`filing_window(rows, as_of,
  basis=None)`; ~~B6b~~), `derived_settings.py` (framework and `ISSUER_CLASS` from the forms;
  `ANALYSIS_BASIS`; basis status from listed bases; ~~B10b~~), `source_catalog.py` and
  `capture_intake.py` (`XBRL_SOURCES[(IssuerClass, Basis)]`, `xbrl_source_id(issuer_class,
  basis)`, `nse-grounding` refused), `contracts/companies/onboarding.py`
  (`BANK_ONBOARDING_VERSIONS = ConfigVersions(dictionary="v5", mapping_set="v11")`),
  `onboard_cli.py` (two flags; pins from `bank_onboarding.versions(args)` for config load, printed
  compare command and the descriptor's `onboarding_versions` check; the staging block and
  `package_manifest` call replaced by one `bank_onboarding.stage_inputs` call),
  `first_party_extract.py` and `first_party_ingest.py` (framework evidence), `vendor_first.py`
  (`issuer_class` per reading 4), `screener_session_models.py` (`consolidated_published`),
  `screener_page_cli.py` (`watchlist_topology`), `vendor_screener.py` and `vendor_shareholding.py`
  (Screener bumps; `tijori-shp-v3`, `upstox-shp-v3`, R4-02), `run_config.py` (three first-party
  extractor bumps)
- Test: `test_onboarding_verification.py` (HDFCBANK moves to the bank route; BAJFINANCE, HDFCLIFE
  unchanged; the five Screener basis cases); `test_bank_onboarding.py` (`pg`, `retained`);
  `test_issuer_class.py` (unit)

Interfaces:
- Produces: `issuer_form(body) -> IssuerClass | None`; `issuer_class(conn, entity_id, period_end,
  cutoff) -> IssuerClass | None`; `verify_xbrl_framework(body, framework, pdf=None)`;
  `IngestRequest.framework_evidence: FrameworkEvidence | None` (PDF capture id, sha256, filed time);
  `derived_settings.framework_evidence(conn, entity_id, period_end, cutoff) -> FrameworkEvidence |
  None` (the framework setting's retained PDF input for that filing); `bank_onboarding.versions(args)
  -> ConfigVersions`; `bank_onboarding.binding(path, isin, basis)`; `screener_topology(warehouse_id,
  basis, configured: BasisTopology | None) -> BasisTopology`;
  `watchlist_topology(config_root, symbol) -> BasisTopology | None`;
  `bank_onboarding.stage_inputs(raw_root, symbol, filings, pdf, issuer_config) -> Path`.

Approach (F04, F05, F19, F20):
- Pins: `--analysis-basis` selects `BANK_ONBOARDING_VERSIONS`; without it `ONBOARDING_VERSIONS`.
  Discovery's class must match (bank pins ↔ `BANK`), else refused before any settings write. The
  same pins drive ingest, the printed command and acquisition descriptor validation. Apar and other
  non-bank pins are unchanged.
- Form: read per instance from the namespace (never URL prefix, schema filename or framework); all
  onboarding filings must agree on one uncontested form, else refused.
- Framework: X arm as today with the evidenced value. P arm: when the instance declares none, the
  filing's results PDF acquired by discovery supplies the evidence if `verify_pdf_identity` passes,
  its period and basis headings match the filing (code-checked phrases from the record), and its
  declarations name exactly the evidenced value; the PDF capture is retained as framework evidence.
  Contradiction between instance and PDF, or several frameworks, refuses. A `Banking` form alone is
  never framework evidence.
- Framework evidence at ingest (R2-01): every first-party ingest caller passes
  `IngestRequest.framework_evidence` (onboarding here; `evidence_cli` and fallback in Task 7, read
  by `derived_settings.framework_evidence`). `_read_xbrl` loads the PDF's bytes from the snapshot
  store by capture and sha256 and calls `verify_xbrl_framework(instance, framework, body, pdf)`
  with the same issuer, period, basis and declaration checks as discovery, on fresh extraction and
  on the reuse check alike; a contradiction stays fatal. The evidence sha256 joins the XBRL
  extraction context, so a generation made under other evidence is not reused. X-arm filings pass
  `None` and behave as today.
- Staged inputs (R2-02): `stage_inputs` replaces onboarding's temporary staging for every issuer.
  It writes, deterministically from retained bytes, `<raw-root>/inputs/<SYMBOL>/<period-end>/`:
  `xbrl/` originals, ~~on B7a `pdf/` original,~~ and `retrieval-manifest.json` from
  `package_manifest` ~~extended with the PDF kind, sha256 and filed time~~ (B7b, taken: XBRL only).
  ~~On B7a it requires `config/runs/<symbol>-<period>.yaml` (refused if absent) and passes it with
  both member kinds to `retained_intake_from_manifest`.~~ Acquisition and replay write identical files; Task 13 ingests
  from this directory. Grounding captures are never staged.
- Binding: reading 3; checked before any settings write.
- Screener basis binding (R2-04). Today a standalone topology carries only
  `standalone_warehouse_id`, so `BasisTopology.standalone_only` is true and `read_page_evidence`
  passes `marker_optional=True` (`screener_session_page.py:177–182`). In that branch
  `_require_basis_evidence` rejects any declared marker, the correct one included (`:220–226`), and
  accepts an unmarked page. The fix: `BasisTopology` gains `consolidated_published: bool = False`
  ("the vendor publishes a consolidated page whose warehouse id this binding does not hold").
  `standalone_only` and `single_basis` treat it as a published consolidated basis. Existing callers
  never set it and behave as today.
  The markerless exception comes only from reviewed Screener topology evidence for the issuer
  (R2-04, review 4). This is the mechanism NETWEB already uses. Its committed watchlist entry in
  `config/coverage/watchlist.yaml` records `screener_warehouse_id_consolidated: null`, live-verified
  against the retained subscriber page (surface-map.md §10; the file's header). The entry is read
  as a `BasisTopology` by `screener_page_cli.basis_topology(stock)`.
  A new `screener_page_cli.watchlist_topology(config_root, symbol) -> BasisTopology | None` returns
  that topology for the issuer's entry under `<config-root>/coverage/watchlist.yaml` (`None` when
  there is no entry).
  `screener_topology(warehouse_id, basis, configured)` then returns the standalone-only topology
  only when three things hold: `configured.standalone_only` is true, the page's company id equals
  the entry's `screener_company_id`, and the page's warehouse id equals the entry's standalone id.
  In every other case a standalone request gets
  `BasisTopology(standalone_warehouse_id=..., consolidated_published=True)`, so the page's
  `Standalone Figures` marker is required. Consolidated is unchanged.
  Exchange basis status is not consulted. `STANDALONE_ONLY` describes the issuer's exchange filings,
  not the vendor's pages, so it can never grant the exception. Choosing standalone never implies
  standalone-only.
  The same entry is carried through onboarding and reingest. `onboard_cli` loads it once, then
  passes it into `discover` → `_vendors` → `screener_page_state` (`verification.py:315–316`) and
  into `_vendor_adapters`. Task 7's reingest reads the same entry. The interface layer loads the
  watchlist, so the `companies` layer imports nothing from it.
  Both directions fail closed. An unmarked page with no reviewed standalone-only entry refuses. A
  marked page whose entry says standalone-only refuses, as today. ICICIBANK has no watchlist entry,
  so its standalone page must carry its marker.
- Settings: framework and `ISSUER_CLASS` (`DISCOVERY`), `ANALYSIS_BASIS` (`OWNER_DECISION`), basis
  status from the listed bases (`_BASIS_STATUS` no longer keys on the selected basis).

Verification (F03): replay integration over the Task 2 retained ICICIBANK bodies, the test building
an onboarding replay folder from them (same URLs), every vendor request answered with an explicit
unavailable response: ICICIBANK → `PARTIAL`, settings with their evidence kinds, a standalone
package whose instance sha256s equal the evidence pins, both filings verified. Refusals before any
write: bank form without `--analysis-basis`; binding for another ISIN; binding value `STANDALONE`
with `--analysis-basis consolidated`; a path outside `basis_decisions/`; a quote absent from the
spec. Apar replay unchanged (existing onboarding suite); BAJFINANCE, HDFCLIFE `UNSUPPORTED`.
Screener basis (R2-04, must pass before Task 10). Each case is an in-memory page shell. It carries
the authentication, identity and code elements, plus one minimal synthetic financial table: one
section, one row, made-up label and number, no vendor body or value. Each case runs through
`screener_page_state` and through `extract_screener_page`'s gate, using the binding that
`screener_topology` builds from the case's watchlist entry:
(1) an issuer with no watchlist entry: a page marked standalone verifies and extracts;
(2) the same issuer's unmarked page refuses (`BASIS_UNVERIFIED`; `BasisEvidenceMissingError`);
(3) a page marked consolidated, requested as standalone, refuses (`BasisMismatchError`);
(4) the NETWEB-style exception, using the committed NETWEB entry (consolidated null) and a shell
carrying its company and standalone warehouse ids: the unmarked page verifies, and the marked page
refuses;
(5) the discriminating case: an entity whose exchange basis status is `STANDALONE_ONLY`, with no
watchlist entry or an entry whose ids differ from the page. Its unmarked page refuses, and its
marked page verifies.
The existing Screener session suites pass unchanged.
Pins: the version-pin suite passes with `screener-v2`, `screener-shp-v3`, `tijori-shp-v3` and
`upstox-shp-v3`. Each of these hashes its listed files at the tip. On an `eqos_test_*` store that
holds a pre-Phase-3 pin of each, the old pin stays and the new version records its own pin. No
alias.
Staged inputs: the replay's `inputs/` files equal a second replay's on a fresh database (path,
sha256); Apar's staged XBRL-only layout ingests as before. P arm (taken), through package
ingest: onboarding ingests the PDF-only-declared instance; the reuse check passes with the same
evidence; a contradictory PDF refuses at ingest; other evidence yields a new context, not reuse;
an existing-enum framework case. B4b: the Q1 standalone instance (`in-capmkt/Symbol` scheme)
verifies in discovery and at ingest; the same scheme with another identifier refuses. A7: the
unit cases under amendment A7. Unit (`issuer_form`, `issuer_class`): the four retained forms; NBFC under Ind AS → `None`;
mixed forms → `None`; Apar's legacy provenance → `NON_FINANCIAL`; a cutoff before a new entity's
setting → `None` (no fallback); a superseding setting wins from its `valid_from`.

Dependencies: Task 4. Code and unit tests need only Task 4; the ICICIBANK replay integration
(v5/v11 pins) runs after Tasks 6 and 8 land, and Task 5 is not verified until it passes — never
against missing config, never counted as passed while deferred.

Risks: characterize first (current onboarding suite). HDFCBANK pin tests change meaning; stated in
the commit.

## Task 6: Dictionary v5 and issuer applicability

Goal: under dictionary v5, shared rows apply to both classes, bank-only rows to `BANK`,
non-financial-only rows and formulas to `NON_FINANCIAL`, decided before any value; v1–v4 decide as
today; the frozen ledger agrees with the implemented rules.

Files:
- Create: `config/normalisation/dictionary/v5/*` (v4's nine files; `metadata.yaml` version,
  `formula_set_version: v4` and `scope` line rewritten; bank rows; `issuer_applicability` on family
  defaults and differing rows)
- Modify: `dictionary.py` (`DictionaryRow.issuer_applicability: frozenset[IssuerClass] | None`),
  `applicability.py` (`ApplicabilityContext.issuer_class`; `ISSUER_RULE_ID`; checked after the
  basis checks)
- Test: `test_issuer_applicability.py` (unit); v5 load tests; `test_bank_ledger.py` (the ledger
  check)

Interfaces: produces `issuer_applicability`, `ApplicabilityContext.issuer_class`, `ISSUER_RULE_ID`,
`IssuerContextMissingError`.

Approach: §8 step 3. Shared rows (PBT, tax, PAT, EPS, share capital, reserves, total assets, and
any row whose v4 `meaning` holds for a bank per the record) declare both classes. Bank-only rows
only for lines the retained filing carries, each `meaning` citing the record. Non-financial-only
rows and their formulas declare `NON_FINANCIAL`. Nothing is deleted or weakened for absence (F12):
period requirements and `when_statement_present` rules stay as in v4; an absent statement is a
capability `UNSUPPORTED` line whose expected result the unchanged rule decides, not a removed row;
no Apar rule changes. No unevidenced bank concept is added. v5 follows v4's lineage, which includes
v3's shareholding rows (orchestrator ruling: v4 = v3 plus the PDF current-tax row).

Verification: unit: shared × both → rule decides; bank × `NON_FINANCIAL` → `NOT_APPLICABLE` by
`ISSUER_RULE_ID`; v4 × `BANK` → unchanged; v5 × `None` → `IssuerContextMissingError`. Tree diff:
v5 equals v4 except the stated changes.

Ledger check (R3-01, must pass before Task 10). Code reads the frozen ledger and first checks its
sha256 against the value Task 3 recorded. For every line it then evaluates the implemented v5
applicability: issuer class `BANK`, the line's period kind and basis, and the statements present
per the record. It compares the decision with the line's expected result: `VALUE`-eligible, or
`NOT_APPLICABLE` by the named rule. Every line must agree. Expected outcomes come only from the
ledger and are never regenerated from the implementation. The check cannot pass by refusal: a
`VALUE` line that v5 makes inapplicable, or one whose rule differs, fails it. A mismatch stops
work. Either the implementation is corrected to the ledger, or a reviewed ledger or branch
amendment (a Sol plan review, as at Task 3) changes the ledger and its recorded sha256.

Dependencies: Task 4; Task 3 (B8, frozen ledger).

## Task 7: Engine context, run framework, fallback

Goal: a financial-results group resolves framework and issuer class from the entity's settings for
its period at the cutoff, everywhere keys, packages and lookups are chosen; every ingest, reingest
and fallback path uses the entity's framework and source; Apar resolves `IND_AS` and
`NON_FINANCIAL`.

Files:
- Create: `engine_issuer_context.py`
- Modify: `engine.py`, `engine_vendor_context.py`, `run_family.py` (`FINANCIAL_RESULTS.framework`
  per entity), `fact_view.py`, `evidence_cli.py`, `onboard_cli.py`, `vendor_reingest.py`,
  `results_filing.py` (`acquire_results(..., source: tuple[str, str])`), `fallback.py` (`_acquire`
  passes `XBRL_SOURCES[(issuer_class, basis)]`; `_ingest` the entity's framework and
  `framework_evidence`), `evidence_cli.py` (same two), `run_config.py` (`_SEMANTICS_VERSION`)
- Test: `test_bank_run.py` (`pg`, `retained`); `test_bank_fallback.py` (`pg`, replay through
  `eqos compare fallback`); `test_bank_reingest.py` (`pg`, `retained`, public `vendor reingest`)

Interfaces: `issuer_context(settings, entity_id, period_end, cutoff) -> IssuerContext` (frozen:
`framework`, `issuer_class`), a pure function over loaded settings via `setting_as_of`.

Approach (F18): no ambient `self._framework`; the context is passed to reported-key enumeration,
package selection and comparative/formula lookups (`engine.py:223–255`, `:465–499`). A package
whose framework differs from the context refuses. `SHAREHOLDING` keeps its `UNKNOWN` framework.
`xbrl_parser.py:538` (legacy parser, off the results path) is not touched.

Reingest basis binding (R2-04). `vendor_reingest._adapters` (`:149–157`) drops the fixed
consolidated topology. It uses `verification.screener_topology(warehouse_id, basis,
watchlist_topology(config_root, ids.nse_symbol))` instead, the same reviewed entry onboarding used
(Task 5). No basis-status lookup is added. The warehouse id and identity evidence still come from
the retained page and its first occurrence. A standalone page must carry its own marker. It may be
unmarked only when the issuer's reviewed watchlist entry records standalone-only with matching ids
(Task 5's rule). A page of the other basis refuses.

Verification: Apar comparison suites pass; bank run: ledger `VALUE` keys valued, non-financial-only
rows `NOT_APPLICABLE` by `ISSUER_RULE_ID`, a v5 group without class refused; results equal whether
bank or non-bank groups run first; an entity whose framework setting changes at a `valid_from`
between two periods gets each period's framework; a run pinned at the old semantics version is
refused by `require_pins`. Bank fallback: a triggered ICICIBANK cell acquires under the bank source
and ingests with the bank framework; a listing without the period ends `FILING_UNAVAILABLE`; ~~B7a: the
PDF member joins with the issuer config;~~ P arm (taken): fallback and `evidence ingest` verify the instance
with the setting's PDF evidence, and refuse when that evidence contradicts it. Reingest (before
Task 10), through public `eqos vendor reingest --basis standalone`. It runs over registered
captures of Task 5's five page shells, each with the entity and watchlist entry its case names.
Each capture is seeded with a first occurrence whose native context carries the identity evidence
ref that reingest reads (`earlier[0].native_context`). Case (1) stores interpretations under
`screener-v2` with standalone keys, from its synthetic financial table: extraction enumerates
financial-table cells (`vendor_screener.py:115–135`), so the identity shell alone proves only the
gate. Cases (2) and (3) refuse. Case (4) passes unmarked and refuses marked. Case (5) refuses
unmarked. Apar's consolidated reingest is unchanged. Task 12 reruns case (1) over ICICIBANK's
retained bank page; no bank page is retained before Task 11. If that page is unmarked, Screener
stays unverified for ICICIBANK. A standalone-only exception would need a reviewed topology entry,
added only by a Sol-reviewed amendment.

Dependencies: Tasks 5, 6.

Risks: fixture entities lacking `REPORTING_FRAMEWORK` now refuse; characterize first and add the
setting, never a default.

## Task 8: First-party bank mappings, mapping set v11

Goal: ICICIBANK's retained XBRL ~~(and, B7a, PDF)~~ interprets every ledger *reported* `VALUE`
line (`VALUE <QName@contextRef>`) `MAPPED` under v11 with verified meaning. Every key that a
ledger `REFUSED` or `no key` line names stays unmapped, and other lines are `UNMAPPED`. Ledger
`VALUE computed` lines have no filed fact and no mapping entry. They are checked through the
comparison and formula path, never as interpretations, and are never admitted as observed facts
(`admit_run` refuses non-`REPORTED` rows as `NOT_REPORTED`). Apar interprets identically under
v10 and v11.

**Isolation (Task 3 reviews 1 and 2; stop rule applies).** Apar's 2026 in-capmkt entries
(`xbrl/v5/in_capmkt.yaml`, listed by v10) select by namespace, element, period shape and
dimension axis. The bank files in the same namespace, so `schema_identity` does not separate the
two (B3a). Without a new scope, these entries would map bank facts that the ledger refuses or
withholds:
- `capmkt.segment_assets.2026` (`in_capmkt.yaml:496–501`; members, `POST_ELIMINATION`): the bank's
  asset members, against L393–L396 `no key` `R-BASIS` (review 2). The bank basis is unresolved
  and is never chosen because this entry already supplies one;
- `capmkt.segment_result_total.2026` (`SegmentProfitLossBeforeTaxAndFinanceCosts`, no dimension):
  the bank's segment PBT, against L383–L384 `R-MEAN`;
- `capmkt.segment_liabilities.2026` (members, `POST_ELIMINATION`) and
  `capmkt.segment_liabilities_total.2026`: liabilities that include capital, against L401–L405;
- `capmkt.segment_liabilities_net.2026` (`NetSegmentLiabilities`): against L407.

The loader's selectors (`Selector`: native field, period shape, dimension axis and member;
entry: `schema_identity`, `basis`, `period_kinds`) have no issuer-class or form scope. **No
supported selector keeps Apar's meaning while refusing the bank's, so Task 8's stop rule applies
to these entries.** The stop needs an amendment, for example an evidenced IntegratedFinance-form
scope on mapping entries. Apar's canonical meaning is never changed to make the bank fit. The
bank's per-member segment results (`ReportableSegmentsFinanceCostsAxis`) match no existing entry
and stay unmapped. `SegmentRevenue` members (`PRE_ELIMINATION`) match Apar's entry with the
basis the record evidences for the bank; the undimensioned `SegmentAssets` total, unallocated and
net assets (L397–L399) carry no basis and match Apar's entries. The stop is deferred, not
discharged, while B1c halts the phase. It binds any amendment that releases B1c, and releasing
B1c by any route does not release it.

Files:
- Create: `config/normalisation/mappings/xbrl/v6/*`, `mappings/v11.yaml` (v10's files and keys
  plus the changes below); B8 `statement_anchors/v3.yaml` (the PL anchor in Resolved branches);
  ~~B7a `pdf/v4/results_layout_banking.yaml` only (v11 lists `pdf/v3/results_layout.yaml` unchanged
  plus this file; no copy), `config/runs/icicibank-<period>.yaml`~~
- Modify: ~~B3b `xbrl_taxonomies.py`~~ (none: B3a)
- Test: `test_bank_mapping.py` (`retained`)

Approach (F10, F22):
1. Inventory by code: every fact QName in the retained instances × the v10 entries matching it.
2. A matched QName whose v10 meaning holds for the bank line is reused, no new entry. A different
   meaning gets a replacement entry in a v6 file under a selector scope the loader supports (e.g.
   the evidenced `schema_identity`), and v11 lists the v6 file in place of the v5 file it
   supersedes; if no supported scope separates them, stop for an amendment. No invented namespace.
3. Unmatched QNames get bank entries with `evidence_ref` (capture sha256, QName, context; PDF page
   and label). Elements whose meaning the filing does not evidence stay unmapped, reason in the
   header.
4. ~~B3b~~/B8: ~~the evidenced `TaxonomySpec` and~~ the v3 anchors, included in v11 and the XBRL
   extractor pin.
5. ~~B7a: the issuer config's `pdf_parse` with the PDF sha256; the PDF's identity, period, basis and
   framework gates pass on the actual layout.~~

Verification: per ledger reported `VALUE` line, code compares the interpretation's canonical
key, value, sign, period, interval and provenance with the retained fact. Per `VALUE computed`
line, the comparison engine's formula path yields the value, with each operand a ledger reported
`VALUE` key, the complete output key (every axis, including `elimination_basis`) and a stored
calculation trace; its admission disposition stays `NOT_REPORTED`; `statements_present`, reporting kind
and period shape as the record states; Apar's retained packages give equal interpretations per
canonical key, value and status under v10 and v11; ~~B7a: a PDF ingest of the retained PDF yields
`MAPPED` occurrences, not only a text layer.~~ Task 13's intake (R2-02, R4-01, before Task 10):
onboarding replay over the Task 2 bodies (Task 5's test folder) stages `inputs/`. Then Task 13
command 1 runs as the string from `commands.txt` with every argument filled (Task 13). The one
change is `--mapping-set v11`, the set this task produces, in place of `v12`, which does not exist
until Task 12. It runs over that directory, on the same database and on a fresh one after a second
replay. It must build the package with the XBRL ~~and (B7a) PDF members and the issuer config~~ member, with
every member `COMPLETE` and the staged members equal across both runs. Task 12's gate rerun later
runs the literal v12 string.

Dependencies: Task 6; Task 3; the intake test also needs Tasks 5 and 7.

## Task 9: Document amendments

Goal: the specs and glossary say what Phase 3 built.

Files: `docs/specs/2026-11-06-vendor-first.md` (any contract wording Task 3 approved, e.g. the B1b
framework name; A1–A6 are already in); the canonical data spec (§8 outcome table, Stage 4, Out of
Scope, §10 verbatim); `CONTEXT.md` (**Issuer class**: `NON_FINANCIAL` or `BANK`, from the filing's
IntegratedFinance form; **Analysis basis**: the basis a bound owner decision fixes for analysis,
apart from reported bases). The vendor-first spec's §8 still uses the old numbers for the
dictionary, control and baseline (`:472`, `:505–510`). Task 9 reconciles them with the binding
renumbering: dictionary v5, sets v11/v12, the v4/v10 baseline and control.

Verification: every linked path exists; `test_source_list.py` passes. Reviewed at phase end.

Dependencies: Task 5.

## Task 10: Pre-live gate

Goal: the tip holding Tasks 1 and 4–9 passes `scripts/verify.sh gate vendor-1-p3` (a
`systemd-run --user` unit; log and revision in `scratchpad/vendor-first/gate-3/`), including Task
5's five Screener basis cases, Task 7's reingest cases and Task 6's ledger check; mypy strict and
ruff clean. The tip's base carries the stated PDF-fix versions (dictionary v4, mapping set v10,
`PILOT_VERSIONS` v4/v10; Phase 3's `pdf-occurrences/6`). Task 12 reruns the gate before Task 13. A
passed gate is code evidence, not live
acceptance. The gate fixes the final extractor bytes (F08 rule): a read-only query of live and every
retained rehearsal copy shows no `version_pins` row for a Phase 3 development extractor version
whose bytes differ from the gated ones; one found forces a new version and a rerun.

Dependencies: Tasks 4–9 committed. Task 2 needs only Task 1's affected suites, mypy, ruff and the
authority-negative tests (capture writes only); no schema, settings or package write precedes this
gate.

## Task 11: Live: migrate, onboard ICICIBANK

Goal: live has 0050 and ICICIBANK onboarded as `BANK` on the pinned evidence, with its standalone
package and vendor captures retained.

Commands (main checkout on the Task 10 tip):
1. `eqos db migrate` (0050).
2. Acquisition on the throwaway copy: `eqos onboard ICICIBANK --acquire --analysis-basis standalone
   --basis-decision config/companies/basis_decisions/icicibank.yaml --raw-root R --snapshot-root S
   --config-root config --sanction config/acquisition/sanctions/five-company.yaml` (FIVE-1 Task 1's
   route; flags as FIVE-1 lands them). Before the rehearsal, code checks that discovery's
   selected filings' sha256 equal the Task 3 evidence pins; any difference stops the task for
   re-grounding (Task 2) and a Task 3 amendment review.
3. Rehearsal and live: the same command with `--generation N` in place of `--acquire` and
   `--sanction`.

Verification: protocol passes; read-only queries show `ISSUER_CLASS = BANK` and the framework with
`DISCOVERY` evidence, `ANALYSIS_BASIS = STANDALONE` with the binding as `OWNER_DECISION` input, the
B5 basis status, the pinned instances in the package, and the staged `inputs/` files (path,
sha256) equal the rehearsal's; the Task 2 log's grounding completion precedes this task's first
onboarding invocation.

Dependencies: Task 10; Phase 1 Task 13 done; windows rule; **FIVE-1 Tasks 1–2 (tracked
prerequisite, ruling 1)**, evidenced before Task 11 starts by: FIVE-1's plan `APPROVE` and its
reviewed sanction route for an already-known issuer; Tasks 1–2 committed and inside a gated tip
this task runs on; the committed, `APPROVE`-stamped sanction listing ICICIBANK; the bank pins
(v5/v11) accepted by that route; and a sanctioned generation replaying under `--generation N` as
this protocol requires. The held-out freeze is never repurposed or weakened for ICICIBANK. Until
all hold, Task 11, and so the phase, is blocked; this plan supplies no acquisition authority.

Risks: permanent; a wrong setting is superseded, never edited.

## Task 12: B9, vendor bank mappings, mapping set v12

Goal: B9 is resolved by an evidence addendum; ICICIBANK's retained standalone Screener and Tijori
captures map their shared and bank rows under v12; every native statement label has one
disposition (§6.1).

Files:
- Create: `{screener/v5,tijori/v6}/financials_banking.yaml`, `tijori/v6/display.yaml`,
  `mappings/v12.yaml`
- Modify: `mapping.py` (optional `display_file`; absent → `tijori/v5/display.yaml`, today's
  constant), `onboard_cli.py` and `vendor_reingest.py` (load the display named by the set in use),
  `run_config.py` (Tijori extractor bump); this plan (B9 addendum)
- Test: the Phase 1 inventory test over the ICICIBANK captures (`retained`); Apar's inventory and
  Tijori interpretations unchanged under v12

Approach (F10, F11): the B9 addendum cites, per Tijori bank section, the unit and precision
evidence (capture, section, locator) and whether existing section/basis rules fit the bank layout;
a stop arm takes a Sol round. v12 = v11's files plus the two `financials_banking.yaml` files, which
hold only disjoint bank supplements (labels and sections not matched by screener/v4 or tijori/v5);
a label already matched is reused only after its meaning is validated for the bank, else a scoped
replacement under the Task 8 rule. Bank labels whose definition differs from the filed line are
`RELATED_NOT_EQUIVALENT`; the rest `EQUIVALENCE_UNPROVEN`.

Verification: inventory complete for ICICIBANK and unchanged for Apar; mapped vendor facts' keys,
units, scale, precision and periods checked by code; Tijori `INVALID`/`UNIT_MISMATCH` = 0 in
sections with a rule; v10/v11 still load `tijori/v5/display.yaml`; Task 7's standalone reingest
case passes over ICICIBANK's page under Task 5's watchlist rule; gate rerun. The gate rerun
includes the literal, sealed Task 13 command 1 from `commands.txt`, with `--mapping-set v12` (R4-01).
It runs over Task 8's staged test inputs, on the same database and on a fresh one after a second
replay. It must build the package with every member `COMPLETE` and the staged members equal. This
check passes before Task 13's rehearsal and live run.

Dependencies: Task 11 (captures), Task 8.

## Task 13: Live: ingest, compare; rehearsal admission and Apar regression

Goal: live has ICICIBANK's acceptance package interpreted under v12 (XBRL+PDF on B7a), its vendor
captures under v12, and one comparison run on the pinned period matching the ledger; on the
rehearsal copy, positive admissions and the Apar regression pass.

Commands, under the live protocol (no acquisition). `<R>` and `<S>` are the live raw and snapshot
roots, `<PE>` and `<Q>` the pinned period end and its quarter (Task 3 evidence pins), and `<D>` is
`<R>/inputs/ICICIBANK/<PE>`. `<xbrl-kind>` and `<pdf-kind>` are the member kinds in Task 11's
staged manifest:
1. `eqos evidence ingest --retrieval-manifest <D>/retrieval-manifest.json --issuer ICICIBANK
   --quarter <Q> --period-end <PE> --basis standalone --raw-root <D> --snapshot-root <S> --member
   xbrl=<xbrl-kind> --config-root config --dictionary v5 --mapping-set v12`, and on B7a also
   `--member pdf=<pdf-kind> --issuer-config config/runs/icicibank-<PE>.yaml`. The raw root is the
   staged period directory, and the manifest's sha256 equals Task 11's.
2. `eqos vendor reingest --entity ICICIBANK --period-end <PE> --basis standalone --mapping-set v12
   --dictionary v5 --snapshot-root <S> --config-root config`.
3. `eqos compare run --entity ICICIBANK --period-end <PE> --basis standalone --cutoff <cutoff>
   --dictionary v5 --mapping-set v12 --config-root config` (vendor sides by default).
Every placeholder is replaced by its literal value in `commands.txt` before Task 8's intake test
runs command 1 and before `commands.txt` is sealed. Task 8 runs command 1 with only `--mapping-set
v11` changed. Task 12's gate rerun, the rehearsal and live run the exact strings, and the live
command inventory stays frozen (R4-01).
Rehearsal-only segment, after the three deltas are recorded:
4. `admit_run` on the run.
5. Apar: run `compare run --mapping-set v10 --dictionary v4` per retained Apar period from a scratch
   worktree at the pre-Phase-3 base SHA recorded in `commands.txt`, with that checkout's code,
   config and environment (baseline); at the Phase 3 tip, `evidence ingest` and
   `vendor reingest` of Apar's packages and captures under v10/v4 and v12/v5, then a v4/v10 control
   and a v5/v12 candidate run; same explicit cutoff and scope throughout.

Verification (F13, F17, F24, F25), by code over stored results:
- ICICIBANK: every result equals its ledger line's expected result: `VALUE` keys valued;
  `NOT_APPLICABLE` keys by the rule the ledger names (`ISSUER_RULE_ID` only for issuer-excluded
  rows); expected refusals with their stated reason; every capability `UNSUPPORTED` line listed in
  the report. Vendor sides carry v12 Screener standalone interpretations. The run's `run_inputs`
  name the acceptance package. An unexpected refusal of a `VALUE` key blocks completion.
- Admissions: each ledger-admissible cell admits under §6.5 with its selected source, label and
  witnesses checked; expected refusals refuse; no row 3.
- Apar: per baseline row, canonical key, state, value, interval and normalised reason equal under
  the candidate (normalisation strips row ids and version strings only, by an explicit list);
  added rows carry a family/applicability disposition; the control separates Phase 3 code effects
  from v5/v12 effects.
  Eligibility: no candidate class digest matches an artifact class; the eligibility artifact and
  pilot pins are byte-unchanged; the report states any Apar cell that would lose vendor-only
  admission under the candidate pins.
- Grounding order: capture-only Task 1 test, Task 2/11 logs and the query that every grounding
  capture precedes ICICIBANK's first `onboarding_records` row.

The phase report is generated by code from these outputs (counts and ids only).

Dependencies: Task 12 and its gate rerun; FIVE-1 Tasks 1–2 (as Task 11).

**Then: Sol phase-end review** of the phase diff (Tasks 1, 4–9, 12), the grounding record, the
Task 3 amendment and B9 addendum, the gate logs, the Task 2, 11 and 13 logs and the drafted report,
by the loop in `.claude/rules/core/04-agent-stack.md`, then one fresh closing review. After
`APPROVE`: commit the report, refresh `docs/status/dashboard.html`, record the verdict on
`eqos-awnc`, file beads for anything parked. Phase close requires FIVE-1 Tasks 1–2 done and the
Apar re-ingest follow-up filed and linked (Interactions).

## Dependency order and file ownership

1 → 2 → 3 → 4 → {5, 6} → 7 (after 5, 6); 8 after 6; 9 after 5; 10 after 4–9; 11 after 10 and FIVE-1
Tasks 1–2; 12 after 11 and 8; 13 after 12's gate rerun. Task 5's replay integration and Task 8's
intake test run after Tasks 6 and 8 (and 7 for the intake test) land.

Parallel: 5 and 6; 8 and 9 alongside 7 (disjoint files). One writer at a time, in this order, for
shared files: `results_filing.py` (1, 7), `source_catalog.py` (1, 5), `onboard_cli.py` (1, 5, 7,
12), `vendor_first.py` (4, 5), `run_config.py` (5, 7, 12), `vendor_reingest.py` (7, 12),
`evidence_cli.py` (7), `first_party_extract.py` and `first_party_ingest.py` (5), `nse_filings.py`
(5); FIVE-1's edits to `onboard_cli.py`, `discovery.py`, `fallback.py` come first. Other phases' edits to these files are preserved; a worker rebases its reading
on the current tip at task start.

## Interactions

- **Phase 1 Task 10** (on `main`): Task 1 makes `results_filing._retained` public without changing
  behaviour; Task 7 adds the `source` argument to `acquire_results` and updates `fallback._acquire`
  and `_ingest`. Phase 1's Apar fallback test stays green; the bank path has its own test.
- **Phase 1 Task 9** (in flight): owns `interface/entry/cli.py`; Phase 3 does not touch it.
- **Phase 1 Tasks 13–14** (live, pending): windows rule; Task 11 needs 0047–0049 live. They run on
  their own gated tip.
- **Apar live re-ingest (ruling 2; bead to be filed: Apar re-ingest under Phase 3 extractors).**
  After Phase 3's extractor bumps land (first-party, Screener financials and shareholding, Tijori
  and Upstox shareholding (`tijori-shp-v3`, `upstox-shp-v3`, R4-02), Tijori),
  Apar's stored interpretations keep their pins. The bead is a
  prerequisite of Apar's next live run on Phase 3 code: that run first re-ingests the first-party
  and vendor inputs it needs on its own gated, rehearsed tip. Historical rows, the old replay
  checkout, dictionary/mapping pilot pins and eligibility authority stay separate; no vendor-only
  admission is promised under changed classes. Not Phase 3 live scope; filed and linked before
  phase close.
- **FIVE-1** (plan in review): Tasks 1–2 are this phase's tracked acquisition prerequisite (Task
  11, phase close). FIVE-1 never edits this plan (binding ruling); Task 11's command takes FIVE-1's
  flags as FIVE-1 lands them, and the file-level ordering under Dependency order controls.
- **Results-PDF fixes** (`eqos-djv`, `eqos-ghv`, `eqos-dol`, `eqos-n21`): land before Phase 3
  code and own dictionary v4, mapping set v10, `pdf/v3`, `constructions/v3` and
  `pdf-occurrences/5`; Phase 3 numbers start after them (Review 3 dispositions).
- **Eligibility:** Phase 1's artifact holds `NON_FINANCIAL` classes under the pilot pins; every
  changed version is a new class, so Apar's pins do not move and no `BANK` eligibility exists.
- **Phase 2:** no shared code files expected; `CONTEXT.md` edits serialised; migration numbers
  rechecked at landing.

## Spec amendments

Round 1: A1 (§8 step 1), A2 (after §8 step 4, governing steps 2 and 4), A3 (§8 step 2; §6.6
issuer-class paragraph), A4 and A5 (§8 acceptance), A6 (§6.1 standalone bullet), worded as Sol
drafted them. Round 2 (R2-05): §8 step 5 refuses an unsupported capability wherever its row applies
and keeps a row the unchanged period, disclosure or basis rules make inapplicable `NOT_APPLICABLE`.

## Self-review

- **Spec coverage:** §8 step 1 → T1, T2 (A1); step 2 → T4, T5 (A2, A3); step 3 → T6; step 4 → T5,
  T7, T8, T12 (A2); step 5 → T3 ledger, T6, T13. Acceptance: grounding order → T1, T2, T11, T13;
  `BANK` with evidenced framework → T5, T11; NBFC/insurer `UNSUPPORTED` → T5; ledger values and
  `NOT_APPLICABLE` → T3 (frozen), T6 (ledger check), T7, T13; admissions → T13 rehearsal (A5); Apar
  numeric regression → T6, T8,
  T13 (A4); gate → T10, T12.
- **Names:** `retain`, `results_pdfs` (T1) → T5, T7; `issuer_form`, `issuer_class`,
  `XBRL_SOURCES[(IssuerClass, Basis)]`, `BANK_ONBOARDING_VERSIONS` (T5) → T7, T11; `IssuerClass`,
  keys (T4) → T5–T7; `issuer_applicability`, `ISSUER_RULE_ID`, `IssuerContextMissingError` (T6) →
  T7, T13; `issuer_context` (T7); `screener_topology(..., configured)`, `watchlist_topology`,
  `BasisTopology.consolidated_published` (T5) → T7, T12.
- **Versions:** dictionary v5, mapping sets v11 (T8) and v12 (T12), `pdf/v4/` (T8 B7a),
  `pdf-occurrences/6`, `screener-v2`, `screener-shp-v3`, `tijori-shp-v3`, `upstox-shp-v3` (T5); none collides with the PDF fixes'
  v4, v10, `pdf/v3`, `constructions/v3`, `pdf-occurrences/5`.
- **Placeholders:** branch-dependent content is named by branch and arm; B9 is pending by design
  until Task 12's addendum.
