# RESEARCH-4 — Forward view — Spec

**Status:** approved r6 (2026-11-03): approver gpt-6.1-sol, `APPROVE` on r5's re-review after its fresh closing review, and on r6's amendments with the S1 plan. Amendment: OD-9, §6.2 rule 3, §7.3's capture identity, S1 cases 1 and 4, §10 and the total estimate (§9, last row). The owner granted permissions A and B in §7.1 on 2026-11-04. No implementation, rehearsal or live result is established.
**Origin:** bead `eqos-3v3w`; binding requirements `docs/specs/2026-10-27-research-3-thesis-analysis.md` §7; owner
direction `docs/goals/2026-10-27-research-report-targets.md`.
**Implementer:** Opus. **Boundaries:** E-01 stays deferred
(`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md:111`; RESEARCH-3 §7 cites `:109`, now stale).
No DCF, target price or recommendation. The sample report is used for section structure only; nothing here comes from
its text or values.

Marks: **V** verified on 2026-11-03 at `c5c9649b` by reading code, or by read-only queries of the live database and
retained files. **I** inference. `ledger/` means `src/fundamentals/ledger/`.

## 0. Ground truth

**The ledger**
- **V** Live heads: FY26_Q2 v29, FY26_Q3 v21, FY26_Q4 v22, FY27_Q1 v23, all `APPROVED`. None has a narrative section;
  each has `risk_probe` and `management_credibility`.
- **V** Every run draft is written by `write_run_draft` (`ledger/run_draft.py:342-436`). Derived sections join at
  `:397`; `DERIVED` is `ledger/falsifier_status.py:46`. `_check_sources` runs at `:396`, and only over claims
  assembled by then. An `APPROVED` head with no claim rejections is rerun whole with the head as predecessor
  (`run_draft.py:293-296`, `ledger/rework.py:222-226`). That is how v19 became v23, and it is this spec's write path.
  Any emitted claim not passing refuses the whole version (`run_draft.py:430-435`).
- **V** A version's `knowledge_cutoff` is its derivation cutoff, the store clock at run completion
  (`run_draft.py:413`; `api/cli.py:457`). The source cutoff is the config's: FY27_Q1 is 2026-07-31T10:14:41Z
  (`config/aparinds-fy27-q1-pg.yaml:22`). The temporal gate is `check_blobs` (`run_draft.py:722-745`) and the run's
  allowed set (`:713-719`). A retrospective run reads `Retrospective.published`, not first-seen.
- **V** `check_claim` row 2 applies `FIRST_SEEN` in both modes (`ledger/claim_check.py:95-100`). A thesis citing a
  capture first seen in October 2026 therefore needs a knowledge cutoff after that date, whatever its evidence date.
- **V** The checker reads a trace's stored value; it does not recompute (`ledger/citations.py:556-572`).
- **V** `calculation_trace_operands` allows a row with neither interpretation nor trace
  (`migrations/0001_evidence.sql:390`), and `_input_times` proves first-party status only for the interpretations it
  finds (`citations.py:641-661`).
- **V** A drafted `SOURCE_QUOTE` must have a guidance contract bound by a panel-sealed import, or it fails row 7
  (`claim_check.py:116-121`; `citations.py:319-352`). `contract_bindings` parses each non-update source as a
  `ManagementLedger` (`citations.py:335-343`), so a thesis version holding a quote would raise on its Markdown today.
  Several distinct contracts at one quote bind nothing (`citations.py:351-352`). `_IMPORTED_QUOTES` reads every sealed
  import of the entity, not the citing version's (`citations.py:205-217`). Existing guidance quotes must keep that
  behaviour.
- **V** A `ledger check` supplies no `bound` (`api/ledger_cli.py:281`). An imported version then binds no contract
  (`lifecycle.py:278`), so its quote asserting a contract field fails row 7 (`claim_check.py:158-165`). A contract an
  imported thesis needs on every recheck must therefore come from its own sealed sources.
- **V** `check_claim` compares only metadata resolution supplies, and `_typed` passes any unkeyed claim
  (`claim_check.py:101-105,127-131,134-142`). Horizon, class and precision are not compared at all. A keyless claim
  therefore needs its shape checked elsewhere (§7.3).
- **V** The sealed digest covers each import source's path and SHA-256 (`0042_thesis_claim_citation.sql:58-60`), so
  anything in the twin is sealed.
- **V** `THESIS_CLAIM` resolves only `falsifier.*` claims and does not match the cited key to the citing claim's
  (`citations.py:167-174`). `map_q0` admits only lists of strings plus `falsifiers`
  (`ledger/import_mapping.py:286-291`).
- **V** `evaluate` tests every falsifier in the bound thesis, whatever the period (`falsifier_status.py:159-215`); the
  probe flags each fired row on its metric as a breached limit (`ledger/risk_probe.py:303-308`).
- **V** `import_thesis_successor`'s `_persist` commits seal and approval before `validate`
  (`ledger/importer.py:235-248,324-343`). The version's cutoff is the configured one (`importer.py:315`).
- **V** The filed-figure exception admits comparator priors, the filed tax total and the probe's operands
  (`citations.py:380-390`; `ledger/probe_operands.py:38-42`). The migration precedent is
  `0042_thesis_claim_citation.sql`.

**Later evidence is already in the store**
- **V** Apar filed Q2 FY27 results and a presentation on 2026-10-29, and intake holds both. No FY27_Q2 run config
  exists (`config/aparinds-*.yaml` stop at FY27_Q1). Temporal validity is a live risk (§2, S1 case 5).

**The model part measured so far**
- **V** Real panel on live, code-built drafts: 19 submitted, 4 `REQUEST_CHANGES`. On narrated drafts: v24, v26, v28
  and trial v32 not approved; trial v30, v31 approved (`docs/plans/RESEARCH-3-S3-ledger-narrate.md:776-820`). So
  code-built text is rejected too, and test-database rounds are required for all of this spec's text.

## 1. Extraction: settled

DOCS-1 delivered intake only: `docs/plans/DOCS-1-first-party-document-intake.md:20-24` puts extraction out of scope,
and `eqos-msq.3`, `eqos-msq.4` are open with no content. §7's premise did not hold.

**Decision: start without an extraction pipeline.** `eqos-msq.3` stays open and is not a dependency. Build one narrow
piece of `eqos-msq.4` in S1: **named disclosures** — a short list of exact spans, sealed in the assumption book (§6),
each verified by code against the retained PDF and cross-footed against filed figures where a filed figure exists. No
rule engine, OCR or generic table parser. This is not completion of the general pipeline, and the spec does not claim
it.

**Why this is enough. V, all read through retained captures; Task 0 proves mapping and uniqueness:**

| Need | Where it is | State today |
|---|---|---|
| FY26 annual P&L, balance sheet, cash flow, segment revenue | FY26_Q4 XBRL, the FY27_Q1 run's QoQ comparator (`config/aparinds-fy27-q1-pg.yaml:100-102`) | 181 `MAPPED` interpretations under the run's pins, including all lines in §4; Task 0 reconciles the count |
| FY26 volume, EBITDA, EBITDA per unit by division | NSE investor update filed 2026-05-28 (blob `1deb9bd637c1`), pp. 3-5 | Text layer present. Row labels and cells mostly share a block (`Volume (MT) …` p3); some labels sit in another block and one block can hold two rows; headers span several blocks and units sit in others (§6.2 rule 3). Not in any run package |
| FY26 division EBITDA to PAT | Same document p6 (`FY26 DIVISION WISE EBITDA TO PAT`) | Text layer, one block per row |
| Capex plan, utilisation, volume and growth statements | FY26_Q4 transcript pp. 7, 10, 11, 15, 16 (blob `69aba177cad6`) | In the FY27_Q1 package through prior quotes (`run_draft.py:716`) |
| Working-capital days statement | FY27_Q1 transcript p. 11 (blob `78a312c86f58`) | In the package |
| Guidance quotes | `ledger.conductor_volume_growth.annual.consolidated`, `ledger.cables_revenue_growth.annual.consolidated`, `ledger.conductor_ebitda_per_mt.medium_term.consolidated`, `ledger.cables_ebitda_margin.annual.consolidated` | Claims in v23, already `MATCH` |
| Absolute capacity | Amended 2026-11-05 after a wider search, quotes confirmed by code, meaning not yet reviewed. **V** Before the cutoff: the QIP placement document filed 29 Nov 2023 states capacity, production and utilisation by division to H1 FY24. FY24 and FY25 conductor and oil figures conflict across CARE and company statements. Nothing states an FY26 year-end figure | **Not established at the FY26 base date** |
| Cable volumes | **V** The placement document states cable production in km to H1 FY24; nothing later found. The company said on its Q1 FY26 call that it does not report volume sold | **Missing** |
| Unrestricted cash | **V** The FY25 notes state bank balance restrictions, with no restricted total. The FY26 annual report was filed 25 Aug 2026, after the cutoff | **Not established at the FY26 base date** (§5.5) |

**V** A presentation capture is first-party (`contracts/source_catalog.py:208-214`; `citations.py:393-398`) but not
admissible to a run today: not in `allowed_captures`, not in `Retrospective.published`. **I** Twelve to twenty spans
suffice for Apar; a second issuer is the real test of whether extraction is needed, which is `eqos-msq.3`'s purpose.

## 2. Which quarters

**Decision: FY27_Q1 only, as an explicitly dated retrospective view.** v29, v21 and v22 are not rewritten.

| Run | Latest annual statement admissible | Result |
|---|---|---|
| FY26_Q2 | FY25, filed May 2025, but not in this run's package (own half-year, QoQ, YoY) | `NOT_ASSESSED: no annual statement in the run's package`. FY26 is future evidence and never admitted |
| FY26_Q3 | Same; its QoQ is the FY26_Q2 half-year | Same |
| FY26_Q4 | FY26 own | Would be eligible; not written, smallest first |
| FY27_Q1 | FY26 through QoQ, which the probe already selects (v23 `risk_probe`) | **Base year FY26, forecast FY27-FY31** |

**Selection rule (all runs).** The annual statement is the probe's selected statement
(`ledger/risk_probe.py:465-475`), accepted only when its flow window's `kind` is `YEAR` and its balance date is on or
before the run's period end. Anything else renders the row above. No new statement lookup.

**The assumption book binds one quarter.** The run must equal all of the book's `applies_to` (period), `as_of` (source
cutoff), and `filed` (selected statement's blob, flow window, balance date and measurement context), or `forward_view`
is `NOT_ASSESSED: no assumption book for this period`. Nothing else in the book reaches any report: **scenario
falsifiers are a separate type from thesis falsifiers** (§6.2), so the shared `evaluate`, `thesis_impact`,
`observable_falsifiers` and the probe never read them. Regenerating an earlier quarter therefore cannot pick up later
judgement, even though `approved_thesis` selects by derivation cutoff (`falsifier_status.py:112-122`).

**Disclosed to the reader, at the head of the section:** FY27_Q2 evidence exists and is excluded, so the view is as of
the FY27_Q1 source cutoff. The next quarter's run gets its own book only after testing this book's thresholds (§10).

## 3. Content mapped to the product questions

Gold goal questions (`docs/goals/equity-os-product-completion-gold.md:13-17`), plus the owner floor.

| Content | Question | Class | Claim and citation |
|---|---|---|---|
| FY26 base lines | 1 | observed | `probe.*`, filed; read, not duplicated |
| FY26 anchors: EBITDA, PPE, rates, cash | 1 | computed | `fcst.base.*`, `CALCULATION`: traces via `_Binder.evaluate`, `child`, `_total` (`run_traces.py:320-379`; `risk_probe.py:624-632`); identity traces through `conclude` |
| Named disclosures, with quote | 1, 3 | observed (stated past), forecast (forward statement) | `fcst.d.*`, `SOURCE_QUOTE` |
| Five-year revenue, EBITDA, margin, PAT; revenue by driver and bridge; unit economics; working capital and funding gap | 2, 5 | forecast; FY26 rows computed | `fcst.<scenario>.<line>.<period>`, **`PROJECTION`** |
| Each assumption | 5 | opinion, always; its relation to guidance is a separate computed status | `fcst.a.<scope>.<id>.<y1,y5>`, `THESIS_CLAIM` on `assumption.…`; `scope` is `all` or the scenario |
| Rationale per assumption | 2 | opinion | Book text, verbatim |
| Scenario probabilities | 4, 5 | opinion | `fcst.p.<scenario>`, `THESIS_CLAIM` on `scenario.…` |
| Triggers, scenario falsifiers and their status | 4, 5 | computed status over opinion thresholds | `fcst.t.<id>`, `THESIS_CLAIM` on `trigger.…` |
| Watch items | 5 | computed (listing), status `UNRESOLVED` | Book |

The thesis gains `assumption.*`, `scenario.*`, `trigger.*` (self-cited `POLICY`, as `_falsifier`,
`import_mapping.py:595-623`) and `disclosure.*` (`SOURCE_QUOTE`; `_cited` binds the capture,
`ledger/importer.py:356-358`).

**Not delivered, each rendered as `NOT_ASSESSED` naming its source:** capacity × utilisation (no installed capacity established at
the FY26 base date); cable volume split (volume sold is not reported); usable cash beyond cash and equivalents; competitive position (peers and industry
missing, targets document:44-45); credibility adjustment (Apar's scored outcomes are `UNRESOLVED`, RESEARCH-3 §3);
causes of past moves (RESEARCH-3 S3 closed unmet); prospective falsification (FY27_Q1 was known at sealing; §6.2, §10).

**Stated prominently beside the headline, code-built:** the volume paths depend on capacity delivery that has not been
established, and cable growth has no physical-volume decomposition.

## 4. Inputs

Prefix: `fcst.`. Availability is **V** for name and presence under the run's context; a single `MAPPED` value per key
is confirmed by Task 0. A missing input fails only its block (§5.6).

| Input | Claim | Exists today | When absent |
|---|---|---|---|
| Consolidated revenue, closing receivables, inventories, payables, borrowings, PAT | `probe.R1.revenue_from_operations`, `probe.R1.trade_receivables_current`, `probe.R2.inventories`, `probe.R3.trade_payables_current`, `probe.R6.borrowings_*`, `probe.R4.profit_for_period` | Yes, in v23 | Block `NOT_ASSESSED` |
| FY26 anchors for days | `probe.R1`, `probe.R2`, `probe.R3` | Yes | Shown as not available |
| EBITDA including other income | `fcst.base.ebitda`, trace: `profit_before_exceptional_items_and_tax` + `finance_costs` + `depreciation_amortisation` | Lines mapped; trace new | `PROFIT` block |
| PPE including CWIP | `fcst.base.ppe`, trace `ppe` + `cwip` | Lines mapped | `PROFIT` block |
| Cash and equivalents | `fcst.base.cash`, one-operand identity trace on `cash_and_cash_equivalents` | Line mapped | `FUNDING` block |
| Other bank balances, excluded from funding | `fcst.base.other_bank`, identity trace | Line mapped | Row names it not available; no block fails |
| Rate anchors | `fcst.base.da_rate_pct`, `.finance_rate_pct`, `.etr_pct`, `.payout_pct`, `.materials_pct`; display only, not model inputs (§5.7) | Lines mapped | Anchor shown as not available |
| Division revenue, volume, EBITDA | `fcst.d.*`, `SOURCE_QUOTE` | Spans exist; claims new | Driver rows; `REVENUE` block |
| Forward statements | Existing `ledger.*` claims; new `fcst.d.capex_fy27`, `.conductor_utilisation`, `.working_capital_days` | Mixed | Assumption shows no comparison |
| Assumptions and probabilities | `fcst.a.*`, `fcst.p.*`, `THESIS_CLAIM` | **Missing:** a new thesis successor | Section `NOT_ASSESSED` |

Tijori and Screener are not inputs. Macro charts and index widgets are disabled and unused.

## 5. Deterministic part

`ledger/forward_model.py`: one pure function, no database, no I/O, below `citations.py` in the imports (as
`probe_operands.py`):

```python
compute(model_id: str, inputs: Mapping[str, Fraction], fiscal_year_end_month: int,
        blocks: Set[tuple[str, Block]]) -> ModelResult
# ModelResult: values, claim key -> exact Fraction; failed, (scenario, Block) -> reason
```

Only an unknown `model_id` raises. A missing input or domain fault goes in `failed` for its block and those after it
(§5.6). That is the whole exception contract.

### 5.1 Conventions

- **Index.** `t = 0` is FY26, `t = 1..5` are FY27-FY31. `days_t` is computed by the model from the fiscal label and
  `fiscal_year_end_month`, which is sealed in the book (§6.2) and compared with the entity's setting
  (`run_traces.py:562-570`) at import and at write. A later settings change therefore cannot move a sealed version's
  recomputation. FY28 has 366.
- **Path.** Each assumption states `y1` and `y5`; `a_t = y1 + (y5 - y1)(t - 1)/4` exactly.
- **Arithmetic.** `Fraction` throughout. Inputs enter at their claim's stated value. Percent inputs divide by 100. `C
  = 10^7` converts INR to crore (`run_traces.py:101`). Amounts are crore, volumes MT or KL, unit figures INR per MT or
  KL.
- **Rounding.** Only at the claim, `ROUND_HALF_EVEN` on the exact fraction, never chained. Precision: crore 0, percent
  1, days 0, volume 0, INR per unit 0. The stated value equals the recomputed one.
- **Ordering and cycles.** Lines are computed once, in the fixed order below, in code; there is no data-driven graph.
  A `PROJECTION` claim cannot occupy an input role (§7.3), the only cycle a stored version could state.
- **Domain.** A growth at or below -100, a negative day count, or a zero or negative `V_0` or `Rev_0` fails that
  block.

### 5.2 Revenue and the driver bridge

Assumptions: `gVc`, `gPc`, `gVo`, `gPo`, `gRk`, `s`.

```
V^c_0, R^c_0, V^o_0, R^o_0, R^k_0     disclosed (conductor MT, oil KL, cable)
P^i_0 = R^i_0 C / V^i_0               realisation, INR per unit (i = c, o)
V^i_t = V^i_{t-1} (1 + gV^i_t)
P^i_t = P^i_{t-1} (1 + gP^i_t)
R^i_t = V^i_t P^i_t / C
R^k_t = R^k_{t-1} (1 + gRk_t)
Div_t = R^c_t + R^o_t + R^k_t
s_0   = (Rev_0 - Div_0) / Div_0       others net of eliminations, a share of Div; may be negative
Rev_t = Div_t (1 + s_t)               t >= 1
```

Bridge, FY26 to FY31, for `i = c, o`: `Vol^i = (V^i_5 - V^i_0) P^i_0 / C`; `Price^i = (P^i_5 - P^i_0) V^i_5 / C`. Then
`Cable = R^k_5 - R^k_0` and `Others = (Rev_5 - Div_5) - (Rev_0 - Div_0)`. The six terms sum exactly to `Rev_5 -
Rev_0`; a test holds this. Each term's share is shown only when `Rev_5 > Rev_0`. Cable has one term because no volume
is disclosed.

### 5.3 Unit economics and profit

Assumptions: `eC` (INR per MT), `eO` (INR per KL), `mK`, `q`, `d`, `r`, `tau`, `capex`.

```
E^c_t = V^c_t eC_t / C
E^o_t = V^o_t eO_t / C
E^k_t = R^k_t mK_t
q_0   = (EBITDA_0 - E^c_0 - E^o_0 - E^k_0) / Rev_0     disclosed division EBITDA against filed total
EBITDA_t = E^c_t + E^o_t + E^k_t + Rev_t q_t
Margin_t = EBITDA_t / Rev_t
DA_t  = PPE_{t-1} d_t
PPE_t = PPE_{t-1} + capex_t - DA_t
Fin_t = Debt_0 r_t                  Debt_0 = borrowings_current + borrowings_noncurrent
PBT_t = EBITDA_t - DA_t - Fin_t
Tax_t = max(PBT_t, 0) tau_t
PAT_t = PBT_t - Tax_t
```

**Stated in the section:** EBITDA includes other income. Exceptional items and associates are zero. Debt is held flat,
so the gap's own interest is excluded (OD-4). `d` is a proxy over PPE plus CWIP:
capex enters the base when spent, so depreciation is not timed to commissioning.

**Rows.** For each division: volume, realisation, revenue, EBITDA, EBITDA per unit, margin.

### 5.4 Working capital

Assumptions: `rd`, `id`, `pd` (days), `m` (materials share). The definition is the probe's materials-cost basis
(R1-R3), so the anchors compare.

```
Mat_t  = Rev_t m_t
Rec_t  = Rev_t rd_t / days_t
Inv_t  = Mat_t id_t / days_t
Pay_t  = Mat_t pd_t / days_t
NWC_t  = Rec_t + Inv_t - Pay_t      t >= 1
NWC_0  = filed closing receivables + inventories - payables
dNWC_t = NWC_t - NWC_{t-1}
NWCd_t = NWC_t days_t / Rev_t
```

Only trade balances: other current items are excluded and the row says so. Management's working-capital days statement
is shown beside `NWCd_0` with no assertion that the definitions agree.

### 5.5 Funding gap

Assumptions: `pay`, `c`, and `capex` above.

| Term | Definition |
|---|---|
| `CFO_t` | `PAT_t + DA_t - dNWC_t`. Finance cost stays in CFO, unlike the filed format |
| `FCF_t` | `CFO_t - capex_t` |
| `Dvd_t` | `max(PAT_{t-1}, 0) pay_t`; `PAT_0` is filed. Never negative, so a loss cannot create cash |
| `Cum_t` | `L_0 + sum_{i<=t} (FCF_i - Dvd_i)`; `L_0` is `fcst.base.cash` |
| `Min_t` | `Rev_t c_t`: the operating liquidity floor, an explicit assumption |
| `Gap_t` | `max(Min_t - Cum_t, 0)`: cumulative external funding needed by end of `t` to hold the floor |
| `Surplus_t` | `max(Cum_t - Min_t, 0)` |
| `PeakGap` | `max_t Gap_t`, and its year |

**Opening liquidity is cash and cash equivalents only.** `other_bank_balances` may include margin money (**I**, no
note read) and is excluded; the section shows that amount and states that usable funding beyond this line is
unresolved and that restrictions on the line itself were not verified. A gap of zero reads "no gap on this basis",
never "funded". Existing debt is assumed rolled over. The gap is a size, not a financing plan: no debt-or-equity split
is implied.

### 5.6 Fail closed

Dependencies: `REVENUE` → `PROFIT`; `REVENUE` → `WORKING_CAPITAL`; (`PROFIT`, `WORKING_CAPITAL`) → `FUNDING`, per
scenario. `BLOCK_INPUTS[block]` is a closed table.

- **At write.** A block with a missing or non-passing input emits **no numerical claim**, and renders one
  `NOT_ASSESSED: <input>` row (RESEARCH-3 §1 rule 2); so do those after it. The rest render. `forward_view` itself is
  `NOT_ASSESSED` for §2's cases. Hence no emitted claim can fail for this reason, and `run_draft.py:430-435` keeps its
  meaning.
- **At check.** The blocks a version holds are read from its sealed projection keys, not from current code (§7.3). A
  block's failing input fails only that block's claims and those of later blocks it holds.
- **Structural faults raise `RunDraftError`:** an unknown model id, a mismatched unit, a cross-foot failure (§6.2).

### 5.7 Rate anchors

Shown beside the assumption for the reader; not inputs to `compute`. Each is a `CALCULATION` trace over the selected
annual statement, flows on its `YEAR` window and balances at its close, at the rounding policy's scale and
`ROUND_HALF_EVEN`, as the probe's ratios (`risk_probe.py:612-620`). A guard failing renders it not available.
These five display-only anchors undergo the same independent recomputation on every check and in the write precheck;
the stored trace result alone is insufficient. The writer uses the pinned rounding policy; replay compares the
recomputed rate rounded half-even at the claim's precision.

| Anchor | Formula | Guard |
|---|---|---|
| `da_rate_pct` | `100 × depreciation_amortisation / (ppe + cwip)`, closing | denominator > 0 |
| `finance_rate_pct` | `100 × finance_costs / (borrowings_current + borrowings_noncurrent)`, closing | denominator > 0 |
| `etr_pct` | `100 × tax_expense / profit_before_tax` | denominator > 0 |
| `payout_pct` | `-100 × cf_dividends_paid / profit_for_period`; a canonical outflow is negative (`config/dictionary/v3/cash_flow.yaml:1`), so `OUTFLOW_PCT` | denominator > 0 |
| `materials_pct` | `100 × (cost_of_materials_consumed + purchases_of_stock_in_trade + changes_in_inventories) / revenue_from_operations`, the probe's sum (`probe_operands.py:21`) | both > 0 |

The rows say what differs from the projection: `da_rate_pct` is over the closing base and the model applies `d` to the
opening one; `payout_pct` is FY26 cash over FY26 profit and the model pays out of the prior year's; `finance_rate_pct`
is over closing debt.

## 6. Model part and the assumption book

### 6.1 What a model does

A model proposes values and rationale for a closed list of assumptions, and nothing else. **There is no runtime model
call and no new client:** the Opus implementer drafts the book offline, as thesis successor 2 was. So a test-database
result transfers, because the bytes are fixed. **All report text is code-built except each assumption's rationale**,
copied verbatim from the sealed book.

### 6.2 The book

`forward:` in thesis successor 1.3.0 (`docs/evidence/phase-0.5/q0-thesis-successor-3.{md,yaml}`). **Why the thesis:**
RESEARCH-3 §1 rule 4 already routes opinions there, and sealing, digest, import and `THESIS_CLAIM` exist. F1-F11 are
unchanged, and nothing in `forward` joins `falsifiers`.

```yaml
forward:
  model: forward.1
  # model_correction: {replaces: <model id>, statement: <text>}   only on a §7.6 model route
  applies_to: FY27_Q1
  as_of: 2026-07-31T10:14:41Z
  fiscal_year_end_month: 3
  filed: {source_sha256: <blob>, window: [<start>, <end>], balance_date: <date>, context: <run pins>}
  horizon: [FY27, FY28, FY29, FY30, FY31]
  disclosures:
    - id: conductor_volume_fy26       # closed list
      source_sha256: <blob>
      anchor: p<page>.b<block>.<span>
      quote: <exact span>
      contract: {metric: <m>, scope: <s>, horizon: <h>, unit: <u>, constant_currency: <bool or null>}  # sealed
      context:                        # each an exact span, verified as the quote is
        - {role: HEADER, anchor: <span>, quote: <column label text>}   # TABLE form; one or several
        - {role: PERIOD, anchor: <span>, quote: <period text>}         # where a header does not state it
        - {role: SUBJECT, anchor: <span>, quote: <division heading or row label>}
        - {role: UNIT, anchor: <span>, quote: <unit text>}   # DEFINITION for a footnote, as needed
      columns: [<label>, ...]         # TABLE form only: the header's labels, in order
      column: FY26                    # TABLE form only
      value: <number>                 # one number; a range is not a disclosure in this build
      published: {at: <NSE an_dt>, observation_id: <id>}   # only for a capture outside the package
  assumptions:
    - id: conductor_volume_growth_pct # closed registry; fixes unit and value kind
      reference: {claim: <fcst.d id or ledger.* key>, years: [FY27]}   # optional
      rationale: <text>
      paths: {bear: [y1, y5], base: [y1, y5], bull: [y1, y5]}  # or {all: [y1, y5]}
  scenarios:
    - id: bear
      probability: <n>
      triggers:
        - id: <slug>
          statement: <text>
          predicate: {metric_id: <m>, op: <op>, threshold: <n>}
          falsifier: {id: <slug>, falsifies: [base, bull], statement: <text>}
    - {id: base, probability: <n>, triggers: []}
    - {id: bull, probability: <n>, triggers: [...]}
  watch_items:
    - {id: capacity_delivery, statement: <text>, first_due: FY27_Q2, scenarios: [bear, base, bull]}
```

**Closed registry (20):** `conductor_volume_growth_pct`, `conductor_realisation_growth_pct`, `oil_volume_growth_pct`,
`oil_realisation_growth_pct`, `cable_revenue_growth_pct`, `others_share_pct`, `conductor_ebitda_per_mt`,
`oil_ebitda_per_kl`, `cable_ebitda_margin_pct`, `residual_ebitda_pct`, `da_rate_pct`, `finance_rate_pct`,
`tax_rate_pct`, `capex_crore`, `materials_pct`, `receivable_days`, `inventory_days`, `payable_days`, `payout_pct`,
`min_liquidity_pct`.

**An assumption is always *opinion*, even inside guidance:** a point chosen in a range is still a choice. A closed
table `COMPARABLE[assumption id]` lists reference claims of compatible subject and definition. For each year in
`reference.years`, inside the statement's target window, code compares the interpolated base value with the bounds (a
disclosure's one value is both bounds) and renders `INSIDE`, `BELOW` or `ABOVE`; every other year renders
`NOT_COMPARABLE: guidance does not establish this year`. A comparison requires the statement's own target window to name that year and its definition to be the assumption's (Sol, S1 code rounds 2 and 3). The four admitted `ledger.*` keys are undated, so on real data they appear beside the assumption as `NOT_COMPARABLE` and only `capex_fy27` compares; the report states this limitation. A dated key added later must certify both definition and target window, and a CAGR never gets an unqualified yearly label.

**Meaning validation (finding 18), `validate_book`, at import and at every write:**
1. Span: the capture's text at each anchor, quote and context alike, equals its stated text (`QUOTE_NOT_FOUND`, row
   6).
2. Contract: the entry's `contract` equals the closed list's for the id. Only here, at import and write, is the closed
   list read. Every check reads the sealed `contract` (§7.3, row 7), never the closed list or a location across
   history, so a corrected list or book cannot unbind anything.
3. Value and period: the closed list fixes each id's form, required period and, for `TABLE`, required column. The
   period is the one its `contract` states. Each form has an exact field set. A range-only statement is not a disclosure, so its assumption shows no comparison (§4);
   guidance ranges stay `ledger.*` claims, which `reference` already names.
   - `TABLE`, all of:
     - *Header order.* Code orders the `HEADER` spans by retained position (page, block, start), never book order. Their
       anchors must equal the closed list's for that table, and their joined text, whitespace normalised, must equal
       `columns` joined. So permuting context and `columns` together refuses.
     - *Column and period.* `column` equals the required column and occurs once in `columns`. In a table whose columns
       are periods, the required column is the required period. Otherwise a `PERIOD` span at the closed list's anchor
       holds the required period: `division_total_pat_fy26` takes column `Total` under the FY26 heading, with its
       division headers verified as above.
     - *Row.* The closed list holds reviewed `row_text`, `row_anchor` and `cells_anchor`. The quote's anchor equals
       `cells_anchor`, and a `SUBJECT` span at `row_anchor` holds `row_text`. Other `SUBJECT` and `UNIT` spans hold the
       closed list's division name and unit text. So a slice cannot be read as another row's, including where the label
       sits in another block, one block holds two rows, or a label holds `(Note 1)`.
     - *Cells.* The quote splits on whitespace into exactly `len(columns)` cells, each read by a sign-preserving grammar
       for this check (grouped digits, decimals, optional `%`, a leading `-` or enclosing parentheses); any other token
       refuses. The selected signed cell equals `value`. `guidance_quote_holds` alone accepts any number in the quote and
       drops signs, which would pass a wrong column or a negative; it and guidance parsing do not change.

     A column mapping is sealed, so the reviewer and the code judge the same claim.
   - `PROSE`, no `columns` or `column`: the quote, less its period labels, holds exactly one number, with no sign or
     parentheses, attached or separated, and no magnitude word its unit does not name, equal to `value`;
     the quote or a `PERIOD` span holds the required period; the quote or `SUBJECT` and `UNIT` spans hold the closed
     list's subject and unit text.
4. **Cross-foot against filed figures**, tolerance one crore (the presentation rounds to crore): each division's
   revenue against its `segment_revenue` interpretation; the division table's total PAT against filed
   `profit_for_period`. Against each other: `EBITDA` against `EBITDA per unit × volume`. A forward statement and a
   volume have no filed figure: rule 3 and the book round are their proof, and the row says "single-source". Filed
   values are read under `forward.filed`.
5. Issuer and scope: a capture in the run's package is the issuer's already. Otherwise `observation_id`'s listing must
   be the report's entity (`eqos.document_listings.entity_id`), with an `OK` attempt whose body is `source_sha256`.
   Consolidated scope is what rule 4's total against the consolidated filed PAT tests.
6. Time: `publication <= as_of`. Retrospective: the manifest's time, else `published.at`, which must equal the `an_dt`
   of exactly that pinned observation's payload; never reselected from evolving intake, and labelled a source claim as
   the run's heading already states. Ordinary run: first-seen, through `check_blobs` as today.

**Provenance survives citation.** Disclosures reach the run as `SOURCE_QUOTE` claims on the capture, not through
`THESIS_CLAIM`, and the row renders the quote through `{{c:<key>|quote}}`. Assumption rows name their reference.

**Book guards, at import (Q0 refusal):**
- Exact field sets. An unknown assumption id, or any field outside the schema, refuses, so a resulting figure has no
  place to go.
- Each rationale and each trigger, falsifier, watch and `model_correction` statement holds no `{` or `}`:
  `scan_narrative` removes valid markers before it looks for numbers (`ledger/numeral_scan.py:90,102`), and rendering
  would fill them (`ledger/display.py:108`). Each then passes `scan_narrative` (`ledger/numeral_scan.py:93`), and refuses
  a closed lexicon: target price, DCF, fair value, recommend, buy, sell, hold rating, overweight, underweight.
- Registry bounds on every value (for example days 0 to 365; growth above -100 and at most 100).
- Scenario order, where the registry gives a direction: bear ≤ base ≤ bull at both ends.
- Scenarios: unique bear, base and bull; probabilities each 0-100, summing exactly to 100; `horizon` exactly
  FY27-FY31.
- **Trigger coverage.** Bear and bull each hold at least one trigger; base holds none, being the residual view. Every
  trigger's metric is `revenue_yoy_pct`, `pbt_margin_pct`, `pat_yoy_pct` or `eps_yoy_pct`, which measure the run's own
  quarter, not the annual path; the row says so. `probe_*` metrics refuse: stale-statement triggers are deferred,
  because on FY27_Q1 they could only render `NOT_ASSESSED`.
- **Falsifier coverage.** Every trigger holds exactly one falsifier with a unique id. `falsifies` is non-empty, names
  only other scenarios, and every one of bear, base and bull is named by at least one falsifier.
- **Watch coverage.** `capacity_delivery` and `cable_physical_volume` are required: the critical dependencies no
  registered metric measures. Together they name bear, base and bull. The section states this monitoring limitation.

**Scenario falsifiers.** This is the owner's "triggers that become falsifiers"
(`docs/goals/2026-10-27-research-report-targets.md:25`). A trigger is the sealed condition. Its falsifier is the
sealed, separately identified statement of what reaching it refutes.

- **Persisted.** `ScenarioFalsifier` is its own type in the sealed twin, stated line by line in the Markdown as
  `_falsifier` requires. The threshold is the one self-cited `trigger.<id>` claim, cited in the run as `fcst.t.<id>`.
- **What reaching it falsifies, exactly:** the book's sealed position that each scenario in `falsifies` remains a
  tenable path, for this book. It renders `FALSIFIED: <scenario>`.
- **What it does not falsify or change:** any number, any sealed probability, any thesis falsifier F1-F11, or the
  thesis. No probability is reweighted and no other scenario is adopted. Revising the view takes a later book.
- **Evaluator.** One function in `forward.py` over `FalsifierPredicate.holds` and `METRICS`, called only by
  `forward_view`. Each trigger is `REACHED`, `NOT_REACHED`, or `NOT_ASSESSED` when its measuring or threshold claim is
  absent or not passing. Each scenario is then `FALSIFIED` if a reached falsifier names it, else `NOT_ASSESSED` if a
  not-assessed one names it, else `NOT_FALSIFIED`.
- **No active scenario is ever selected.** Base is never established by default: an unknown condition renders
  `NOT_ASSESSED`, and the section states no current view, whatever the statuses.
- **Isolation (r1 findings 2, 3).** Keys avoid the `falsifier.` prefix, so `BoundThesis.thresholds` never holds them;
  nothing joins `ApprovedThesis.falsifiers`; `Disposition` is not reused, so nothing renders `WEAKENED`. `evaluate`,
  `derived`, `assess` and `ThesisFalsifier` do not change.
- **Limit, rendered in the section.** FY27_Q1 is a retrospective demonstration. This run measures each trigger only on
  that quarter, known when the book was sealed, so its statuses show the mechanism and give no prospective falsification
  evidence. The prospective obligation is not delivered here: the first independent test is FY27_Q2, against these
  original sealed thresholds (§10).

### 6.3 Where Sol checks, and how it is measured

Rehearsal verdicts written by the orchestrator measured nothing. **Rules:**

1. **Every verdict before a live write is a real Sol round on a real rendered artefact.** The orchestrator writes
   none. Each round's brief and response are kept with hashes.
2. **Book round.** Sol reviews the Markdown, twin and complete cited pages against: each column mapping and span means
   what its contract says; issuer and scope; each rationale follows from evidence dated by `as_of`; no use of FY27_Q2;
   the base path is defensible beside its FY26 anchor and FY27_Q1 quarter; why each quarterly condition refutes the
   five-year scenario it names, not merely that it is adverse; and no falsifier is already reached on FY27_Q1 unless
   the book says why. Approval is `ruling: gpt-6.1-sol APPROVE`, as
   successor 2 (`config/ledger_import.yaml:20-29`).
3. **Report round on `eqos_test_r4`.** A faithful restore, 0046, the book's import, the FY27_Q1 run, then `ledger
   check`, `submit`, `panel` with a real Sol verdict on the export: readable as analysis; labels honest; assumption
   and result kept apart; no implied valuation or recommendation. Each slice's export also goes to the owner as a
   readable artefact.
4. **Limit.** At most three rounds per artefact per slice, then the orchestrator rules. A rejection writes nothing
   live.
5. **Gate to live.** `APPROVE` on the test database of the complete report, then the same book bytes, the same code
   commit, and §7.5's parity, enforced inside the live write.
6. **Live.** A fresh real Sol round with the same brief. A live `REQUEST_CHANGES` stops and takes a §7.6 route. The
   head stays a rejected closed version, which blocks only a future FY27_Q2 run (`run_draft.py:312-313`); none exists.
7. **Residual, disclosed.** Dates can be checked; hindsight cannot be disproved. The proposer is briefed only on the
   admitted captures, and the run's retrospective designation stands.

## 7. Ledger representation

### 7.1 Two permissions for the owner

**Why you are being asked.** Invariants 6 and 7 say each material numerical claim in a report comes from a filed fact or
a registered calculation trace. A five-year estimate is not a fact, and some operating numbers exist only in company documents.
These are two separate decisions. **Recommendation: grant both.**

**Permission A: keep five-year estimates as a recomputed "projection" record.** Code recomputes every estimate from
its assumptions, disclosures and filed figures on every check, and a stored number that differs fails the report. An
LLM proposes assumptions, labelled opinion, and never states a result. Estimates are labelled forecast and never feed
a fact.
- *Does this meet invariant 6's "registered traces"?* No, not as written: a projection is a registered calculation but
  not a trace record. Its aim, that an LLM never calculates, is kept. So A is an exception to invariants 6 and 7.
- *If you decline A:* the same estimates are stored as traces, with a new kind of input for opinions. The report and
  its checks stay the same, at about 200-350 more lines of code (an implementation estimate, not measured). This is an
  engineering choice, not a content one.

**Permission B: show numbers from company documents as exact quotes.** This covers past figures the filed statements
do not hold, such as division volumes and EBITDA per unit; division figures that agree with filed segment numbers; and
management's forward statements, such as a capex plan, labelled forecast with their target period. Each is checked by
code at its exact place in the document and reviewed before sealing. Each is labelled single-source, and is checked
against a filed figure where one exists. Guidance quotes the reports already carry are unchanged.
- *If you decline B:* traces cannot rescue this. A trace needs a recorded fact beneath it, and these numbers have
  none. One with nothing beneath it would prove nothing. The real choices are to build document extraction first (not
  designed or sized here), or to go without. Without them the estimates, which start from division volumes and
  margins, cannot be built as designed, and revenue by driver and unit economics are not delivered.

**Text for `.claude/project/invariants.md`, added to invariant 7 after the 2026-10-28 extension:**

> extension A (owner, RESEARCH-4; also an exception to invariant 6's "registered traces"): a forward view may carry a
> projection: a future-year output of a registered deterministic model, or a base-year line that model derives from
> its inputs, labelled forecast or computed, never typed by an LLM, recomputed by code from the version's own bound
> inputs on every check, and never a measurement of any period nor an input to anything but that model's own rows. Its
> assumptions, probabilities and trigger thresholds are labelled opinion and cited to their sealed thesis claims;

> extension B (owner, RESEARCH-4): a forward view may cite a first-party document's numerical disclosure as a quote at
> its exact location, sealed in a reviewed assumption book: a stated past operating figure, including a division figure,
> labelled observed and single-source and cross-footed to a filed figure where one exists; or management's forward
> statement, labelled forecast with its target window;

If A is declined, only A's last sentence is still needed. If B is declined, the first build slice (S1) stops.

**Engineering basis (not part of the ruling). I, an implementation estimate, nothing measured:**

| Work | Lines | Applies to |
|---|---|---|
| Model, input roles, block resolution, input times, recomputation on check | About 250-350 | Both: not a difference |
| One kind and column, output registry, one resolver | About 60-100 | Projection only |
| Opinion operand column, `TraceOperand`, `_trace_operand`, repository, `_INPUTS`, a recomputing `_trace`, intervals, formula ids, synthetic measurement keys | About 260-450 | Traces only |

Difference: about 200-350, r2's 250-400 less the output registry that a trace's key would partly replace. Rows are
about 270 either way: a trace need not store each subexpression (`canon/formula.py:127`). A trace today reads its
stored value (`citations.py:563`), its first-party meaning (`citations.py:641-661`) would not hold of an opinion, and
a future year would need a synthetic measurement id (`0012_report_ledger.sql:88`).

### 7.2 Sections and claims

Section `forward_view`, joining `DERIVED`, after `management_credibility` (`run_draft.py:397`). Rework then skips it;
§7.6 gives its rejection route. Claims and citation kinds are in §3.

**The twin's knowledge cutoff** is the new entry's `thesis_successor.cutoff` (`importer.py:315`), set to the book's
`decided_on`, on or after the first-seen of every disclosure's capture. The book's `as_of` stays the bound on
evidence.

**Pre-approval check.** Inside `_persist`'s transaction, after `create_version` and before the seal
(`importer.py:321-324`), a twin with `forward` runs `validate_book` and `check_version` on the same cursor. `map_q0`
emits no `bound`, so this first check takes the same twin path as every later one (§7.3). Any failure raises
`ImportRefusedError` and rolls back, leaving no version, seal or approval.

**Sizes, I.** With 8 scenario-varying assumptions and 12 `all:`: assumptions 72 (120 if none shared); base projections
213 (25 lines × 5 in S1; 15 × 5, peak gap and 12 bridge terms and shares in S2 and S1); bear and bull 40 (revenue,
EBITDA, PAT, gap × 5 × 2); FY26 derived about 15; anchors, disclosures, probabilities, triggers 7 + 20 + 3 + about 6.
**About 375 added, about 425 unshared;** versions grow from 91 claims to about 470-520. Falsifiers add no claim.

### 7.3 Binding, output and replay contracts

**Input binding: closed, by role.** `ROLES` maps each input role to one expected claim, built by code. A stored input
that differs in any field is not lawful in that role. `resolve_projections` compares; the thesis citation rule also
holds at ordinary resolution.

| Role | Input claim | Must equal |
|---|---|---|
| Assumption endpoint | `fcst.a.<scope>.<id>.<end>` | `THESIS_CLAIM` whose cited row's key is exactly `assumption.<scope>.<id>.<end>` (`thesis.X` → `falsifier.X`, `fcst.p.X` → `scenario.X`, `fcst.t.X` → `trigger.X`; else `None`). Scope is the book's for that id. Value kind and unit are the registry's; currency and scale none, or crore for `capex_crore`. Every emitted endpoint, used by the model or not, equals its sealed row in every field, including value, precision, rounding and class |
| Disclosure | `fcst.d.<id>` | `SOURCE_QUOTE`; anchor, quote, value and contract are the cited book's. Its capture is the one selection gives (`_cited`): first-party, holding the book's exact `source_sha256` and supplying the verified span; it need not be the pinned observation's capture, which stays the publication and issuer evidence (§6.2 rules 5, 6) |
| Filed operand | `probe.Rn.<line>` | Filed `FIGURE`; `measurement_key`: canonical id `<line>`, the report's entity, `CONSOLIDATED`, `forward.filed`'s window or balance date, INR, `CURRENCY_AMOUNT`; unit crore, scale 10^7 |
| Base trace | `fcst.base.<x>` | `CALCULATION`; same key fields with canonical id `fcst.base.<x>`; row 4 ties the trace's digest to it. On every check, independently recompute the seven S1 anchors from the sealed filing's lines under its pins. Require one distinct value per required key; missing or conflicting values give `UNRESOLVED`. Compare EBITDA and PPE exactly in crore, and rates after `ROUND_HALF_EVEN` rounding at claim precision. Trace-reference correspondence is also required throughout the closure |
| Any | | Not a `PROJECTION` |

**Times and memory.** An anchor's resolved times include its required readings' first-known times, so a required line
known after the cutoff fails the anchor and its projections. A `PROJECTION` claim supports no memory item, and an item
labelled observed cannot rest on a version holding projections (extension A; invariant 8).

**Wrong book.** Every thesis citation in the version holds one `cited_sealed_digest`, of a thesis version whose twin's
`applies_to` is the report's period. The write path has already compared `as_of` and `filed` (§2); the digest seals
them.

**Disclosure contract: version-bound, in `check_version` on every check.** One function, `disclosure_contract`, is the
second argument to `_bind` for these keys, and needs no `bound`:

| Claim | Book read | Contract |
|---|---|---|
| Imported `disclosure.<id>` | The single YAML twin among the version's own `import_sources` | That twin's `forward.disclosures[<id>].contract` |
| Drafted `fcst.d.<id>` | The version's single `cited_sealed_digest` selects a thesis of the entity, sealed under that digest as `_THESIS_CLAIM` requires; its twin | Same field, same id |
| Any other quote | Unchanged: `bound.get(key)` if imported, else `bound_contract` | Unchanged |

No twin, no entry, or zero or several digests gives no contract and no resolution, so the claim reads `UNRESOLVED` for both paths; row 7 applies only once an entry is established. A later book
correcting the same quote at the same location therefore gives its thesis and later reports the new contract, leaves
each earlier thesis and report the old one, and touches no `ledger.*` claim at that span. Thesis imports stay out of
`_IMPORTED_QUOTES` (`citations.py:205`), so a book never binds or unbinds a guidance quote, and a thesis's Markdown is
never parsed as a ledger.

**Output registry: closed.** `OUTPUTS[model][line]` gives scenarios, periods, value kind, unit, currency, scale,
precision and class; rounding is `ROUND_HALF_EVEN`. The writer builds claims from it, and the check compares against
it.

| Line kind | Value kind | Unit | Currency, scale | Precision | Class |
|---|---|---|---|---|---|
| Amount | `CURRENCY_AMOUNT` | `INR crore` | INR, 10^7 | 0 | forecast; FY26 computed |
| Percent, margin, share | `PERCENTAGE` | `%` | none | 1 | same |
| Days | `DAYS` | none | none | 0 | same |
| Volume | `COUNT` | `MT` or `KL` | none | 0 | same |
| Per unit | `CURRENCY_AMOUNT` | `INR per MT` or `INR per KL` | INR, 1 | 0 | same |

A claim's key is `fcst.<scenario>.<line>.<period>`; `<period>` is its fiscal year, or `FY26-FY31` for a bridge term
and `FY27-FY31` for peak gap, and the horizon equals it. Peak gap's year renders beside it as code-built text.

**`resolve_projections`, the whole check:**
1. Read the version's `(scenario, block)` set from its projection keys. A model not in `MODELS`, or a broken
   wrong-book rule → every projection `None`, so row 1 `UNRESOLVED`.
2. Per claim, `projection_model` must equal the book's `model`, the key must be registered, and value kind, unit,
   currency, scale, precision, rounding, horizon and class must equal `OUTPUTS`. A difference gives that claim `None`.
3. For each held block, the required inputs are `BLOCK_INPUTS` for it and its ancestors. Each must exist, meet `ROLES`
   and pass `check_claim`. A failure gives `None` to that block's claims and later held blocks'.
4. `compute` the rest, with the sealed `fiscal_year_end_month`. A block in `failed` resolves `None`.
5. Each claim resolves to its exact value rounded at its registered precision, with `times` the union of its block's
   inputs' resolved times (the recursive cutoff check; row 2 then applies them). Row 5 requires a `PROJECTION`'s stored
   value to equal this result exactly, not after rounding; so does an assumption endpoint against its sealed row; other
   `VALUED` kinds keep their rounded comparison.

### 7.4 Proofs (S1 acceptance, on the test database)

- **Recomputation.** `check_version` recomputes every `PROJECTION`, with the stored claim value replaced in memory by
  a wrong one and by the right one; state follows.
- **Tamper.** A written version with one projection off by the smallest unit, or by less than one (synthetic: stored
  `123.49` against a resolved `123` at precision 0) → `VALUE_MISMATCH`. With one assumption
  differing from the thesis → that claim `VALUE_MISMATCH`, its block's projections `UNRESOLVED`, earlier blocks still
  `MATCH`. Unknown model → `UNRESOLVED`. A row with `measurement_key` and `PROJECTION` → rejected by constraint.
- **Output shape.** Each with the value recomputing correctly: wrong unit, scale, horizon, class or precision, an
  unregistered line or period, and `forward.2` (a known model, not the book's) → `UNRESOLVED`.
- **Binding.** `fcst.a.base.<growth>.y1` citing another assumption or endpoint of equal value → `UNRESOLVED`. A base
  and a bull endpoint swapped; a filed operand of another period; a disclosure under another's role; a thesis citation
  of another book → each refused or `UNRESOLVED`, with values copied so that only the binding can catch it.
- **Calendar.** Changing the entity's fiscal-month setting does not move a sealed version's recomputation; a new write
  with a book that differs from the setting refuses.
- **Sealed digests.** All live `version_sealed_digest` values captured from a faithful restore before 0046 equal those
  after 0046, the import and the FY27_Q1 write, for every prior version including v29, v21, v22, v23 and thesis v13.
  The same comparison runs at the live close, with `check-live` ok.
- **Contract replay.** With no `bound` supplied at any step, `ledger check` on the imported thesis A and its report:
  every `disclosure.*` and `fcst.d.*` claim `MATCH`. Import thesis B, which corrects one contract at the same quote and
  location, and write its report. Recheck all four: A and its report still `MATCH` on the old contract, B and its report
  on the new one, and each version's stored claim asserting the other's contract → `QUOTE_MEANING_MISMATCH`. A
  `ledger.*` claim at that span keeps its `bound_contract` and its `MATCH` throughout. A report holding two digests, and
  a twin with no entry for the id → `UNRESOLVED`, because resolution cannot establish the sealed entry (Sol, S1 code
  round 3).
- **Replay stability.** S1's sealed version still checks `MATCH` under S2's and S3's code, with no funding input
  required of it. New lines add keys and never change `forward.1`'s earlier lines (§7.6 for a correction).
- **Import atomicity.** A book failing each of validation, citation, issuer, publication and cross-foot leaves no
  thesis version, seal or approval, and the prior thesis still the bound head.

### 7.5 Test-to-live parity

Test and live thesis ids, digests and times differ, and non-heading sections embed them
(`falsifier_status.py:224-232`), so parity is defined, not byte-literal:

- **Sections.** Each but the heading, after replacing that version's thesis id and sealed digest with placeholders, by
  value read from its own database, not by pattern. Any other difference stops.
- **Claims.** Per key: kind, value, bounds, unit, scale, precision, class, horizon, contract, quote, anchor,
  `source_sha256`, `key_digest`, `projection_model`, cited thesis key, each trace's parity form. Not row ids or
  `cited_sealed_digest`. **Bindings.** The book's SHA-256 and code commit.
- **Trace parity form.** The trace's canonical fields with each operand's reference replaced. `interpretation_id`: the
  capture's `blob_sha256` and the row's `key_digest`, `value`, `mapping_entry_id`, `construction_rule_id`,
  `mapping_set_version`, `normalisation_policy_version` and `extractor_version`. `operand_trace_id`: the child's parity
  form, recursively. `alignment_proof_id`: its `key_digest`, `rule_id`, `rule_set_version`, `holds` and its participants'
  identities, sorted. `content_sha256` is not compared, nor are `input_digest` and `participants_digest`, since all three
  hash row ids (`evidence/repository.py:636`, `evidence/interpret.py:156`, `evidence/alignment.py:128`).
- **Enforcement.** `ledger run … --parity <test record>`, inside `write_run_draft`'s transaction after
  `check_version`; a difference raises `RunDraftError` and rolls back. **Rehearsal.** Between two fresh restores:
  equal passes; equivalent traces with child, interpretation and proof ids deliberately offset on one side pass; one
  changed number or one operand's changed source blob refuses.

### 7.6 Correction routes, append-only

| Defect | Route |
|---|---|
| **Code, no computed value changes:** rendering or binding | Fix and commit. Regenerate through §6.3 step 3. Rerun FY27_Q1: `--full-successor` if the rejection names claims, otherwise an ordinary whole rerun. The thesis is untouched; replay stability must still hold |
| **Model:** a formula that changes a computed value | A released model id is never changed. Add `forward.N+1` to `MODELS` and keep the old function, so earlier versions still replay. Import a metadata successor changing only `model` and `model_correction`, with its own book round. Rerun, which renders the correction statement |
| **Book:** a value, rationale, span or mapping, including a contract on the same quote | A new successor (1.3.1) with new evidence files, a new book round and a new `thesis_successor` entry. Import it, then the same rerun. The imported book stays auditable |

**Release and invalidation.** `forward.1` is released at its first live seal. A numerical fix before then changes it
in place and repeats the affected slice from a fresh restore. After release, an earlier version keeps `MATCH` under
its model, which proves it reproduces, not that the formula was right; the rerun supersedes it, and that is the
invalidation.

`plan` refuses `fcst.*` rejections with these routes, as it does for probe and credibility claims
(`rework.py:233-244`), rather than the generic "supersede the thesis" (`:245-249`). The orchestrator classifies from
Sol's finding.

**Rehearsed on the test database before the live close:** a rendering fix; a model correction that changes a computed
result, with the old version still `MATCH` under `forward.1` and the new one under the fixture `forward.2`; a book
value correction; and §7.4's contract replay.

## 8. Build slices

S1, S2 and S3 each end on `eqos_test_r4`: FY27_Q1 regenerated, every claim `MATCH`, the cases below, a reader-facing
export and Sol `APPROVE` per §6.3. **Nothing live until the live close.** The book is written once, complete, in S1. A
book defect found in a later slice takes §7.6 on the test database.

### S1 — Base-case five-year estimates with revenue by driver and unit economics

**Task 0, read-only.** Under FY27_Q1's pins: the `MAPPED` interpretations on the FY26_Q4 capture count exactly 181,
reconciled by key and with no key holding two values (§1); one `MAPPED` interpretation for each §4 line. Each
disclosure's span and context through `load_pdf`, since block numbers are the loader's. The pinned observation for
each capture outside the package. All cross-foots pass on real values. The `QUARTER` metrics' claims exist on FY27_Q1.
No version of any `BOOTSTRAP_THESIS` report anywhere in the live database, approved head or superseded, holds a
`SOURCE_QUOTE` claim, so `_IMPORTED_QUOTES`' new exclusion changes no existing binding. Any failure stops S1 with the
gap named.

**Work.** 0046, `PROJECTION`, the model (revenue and profit blocks), the book path, pre-approval check, named
disclosures, thesis successor 1.3.0, `forward_view` with: headline; base-case table FY26-FY31; driver rows and bridge;
unit economics by division; assumption table; rate anchors; the `NOT_ASSESSED` list.

**Reader sees:** a code-built sentence stating the base-case revenue and PAT path, which driver contributes most and
how much of it is volume against price, the margin path, the capacity and cable limits, then each assumption labelled
opinion, with its comparison to guidance, quote and FY26 anchor beside it.

**Estimate (r5, historical; the current figures are in the total below).** About 780-950 production lines, 50 SQL, 370-480 test lines.

**Acceptance cases.**
1. Hand-computed: a synthetic book with round numbers gives each line FY27-FY31, exact. Real FY26 inputs: `EBITDA per
   MT` reproduces the disclosure inside tolerance, an independent comparison. `P^c_0` reproduces a stated realisation
   only if Task 0 records that an admitted source states one. If none does, its exact identity
   `P^c_0 V^c_0 / C = R^c_0` checks the implementation of the definition and is not reported as independent reproduction.
2. Bridge terms sum exactly to `Rev_5 - Rev_0`. Shares omitted when revenue does not grow. Negative `s_0` works.
3. §7.4's proofs.
4. Meaning refusals, each named: the FY25 column's value (column and cross-foot); **a coherent wrong-year pair: the
   genuine FY25 `column` and value under the FY26 id and contract, whose EBITDA, per-unit and revenue arithmetic all
   still cross-foot** (required period); `columns` out of order against the `HEADER` spans; **`HEADER` entries and
   `columns` permuted together, values otherwise coherent** (retained order); a `SUBJECT` span of another division; **one
   row's numeric slice under another row's id, in one block and across split labels, values copied** (row binding); **a
   negative cell quoted under a positive value** (signed cell, reached with all else valid); oil's row labelled conductor (segment cross-foot); unit KL under an MT metric (contract); a period label
   not matching the contract; a number absent from the quote; a quote not at its anchor; a presentation of another
   issuer (observation). `PROSE`: a quote holding two numbers; a statement of another target period; `lower_bound`, or
   `columns` on a prose id (field set). Valid controls pass: a prose statement of one number and its required period, with
   no column; a label in another block; two rows in one block; a `(Note 1)` label; column `Total` under its FY26 heading.
5. Time: a disclosure of the 2026-10-29 presentation refuses, by publication against `as_of`, and FY27_Q2 appears
   nowhere in the rendered section's sources. `published.at` differing from the pinned observation refuses. A book
   with `applies_to: FY26_Q4`, or a differing `as_of` or `filed`, on the FY27_Q1 run gives `NOT_ASSESSED`.
   **Regenerated FY26_Q2 and FY26_Q3 on the test database, with this book bound:** `NOT_ASSESSED`; no `fcst.*` or FY26
   annual claim; `thesis_impact`, `observable_falsifiers` and `risk_probe` equal their current heads' under §7.5's
   identity replacement.
6. Fail closed: a missing `cwip` fails `PROFIT` and later blocks and emits no number for them, while revenue renders
   and the version writes; a missing disclosure fails its block and names it.
7. Book guards: a digit or number word in a rationale; "target price"; an unknown assumption id; an extra field
   `revenue_fy31`; a bound breach; bear above base; **`FY31 PAT is {{c:fcst.base.revenue.FY31|unit}} .`**, a valid
   `{{e:opinion}}` and a `{{s:…|…}}`, each in a rationale and in every other statement field. Each refuses at import
   with nothing persisted.
8. Labels: a base path inside management's range is *opinion*, `INSIDE`, for the referenced year only, and
   `NOT_COMPARABLE` for later years. A haircut renders `BELOW`. A reference not in `COMPARABLE` refuses.
9. Rate anchors: each formula hand-computed; payout positive from a negative filed outflow; a non-positive denominator
   renders not available.
10. Regenerated report: `AS_KNOWN`, all `MATCH`, `scan_section` clean, real Sol `APPROVE` on the test database.

### S2 — Working capital and the funding gap

**Work.** `WORKING_CAPITAL` and `FUNDING` blocks; rows; the anchor table; a code-built funding sentence.

**Reader sees:** the peak gap on the cash-and-equivalents basis and its year, which of working capital, capex or
dividends absorbs the cash, and what is unresolved about usable funds.

**Estimate.** About 130-160 production lines, 110-140 test lines.

**Acceptance cases.**
1. Hand-computed `NWC`, `dNWC`, `CFO`, `FCF`, `Dvd`, `Cum`, `Gap` on a synthetic book, including FY28's 366 days.
2. `NWC_0` equals filed closings. `NWCd_0` renders beside management's statement.
3. `Gap_t = 0` with a positive `Surplus_t` on this basis; the reverse when not; never both. `PeakGap` names its year.
4. Dividends follow the prior year's PAT. The year after a loss: `Dvd` is zero, and `Cum` is no higher than with a zero
   payout. A loss year after a profit (prior PAT 100, current PAT -10, payout 50%): `Dvd` is 50.
5. `L_0` equals the cash line and excludes other bank balances, whose amount renders separately. Raising other bank
   balances moves no projection. The words "funded" and "internally" appear nowhere.
6. A base FY27 capex equal to the disclosed amount renders *opinion* and `INSIDE`, one lower renders `BELOW`, with FY28
   onward `NOT_COMPARABLE`.
7. A missing `cash_and_cash_equivalents` fails `FUNDING` only. A missing `other_bank_balances` fails nothing.
8. The limitations (flat debt, trade balances only, rolled debt, no financing split, cash basis) appear in the
   section.
9. S1's sealed version still `MATCH`. Regenerated report, real Sol `APPROVE` on the test database.

### S3 — Scenarios, probabilities, triggers and the watchlist

**Work.** Bear and bull computed; the revenue/EBITDA/PAT/gap table across scenarios; scenario section; triggers and
scenario falsifiers; watch items.

**Reader sees:** three paths with labelled-opinion probabilities, each trigger with its measurement window and status,
what reaching it would falsify, each scenario's status, and what to watch next, with the first period it can be
assessed.

**Estimate.** About 135-180 production lines, 120-150 test lines.

**Acceptance cases.**
1. Finding 20: probabilities summing to 99 or 101, a negative value, or above 100; a duplicate scenario id; a missing
   one of bear, base, bull; a differing horizon. Each refuses at import. Exactly 100 passes.
2. Coverage: bear or bull with an empty trigger list; a base trigger; a metric outside the four, including any
   `probe_*`; a trigger with no falsifier; a duplicate falsifier id; `falsifies` empty, naming its own scenario or an
   unknown one; a scenario no falsifier names; a missing required watch item. Each refuses.
3. **Linkage.** After import on the test database, each trigger's `ScenarioFalsifier` reads back from the sealed twin
   with its id, `falsifies` and statement, and its threshold from its one `trigger.<id>` claim. A falsifier statement
   differing from the Markdown refuses at import.
4. **Status from measurement.** On one sealed book, digest and thresholds unchanged, moving only the measuring claim
   across the threshold moves a bear trigger from `NOT_REACHED` to `REACHED`, cited as `THESIS_CLAIM`, and `base` and
   `bull` to `FALSIFIED`, with every number and probability unchanged. With bear naming base and bull, and bull naming
   base and bear, both reached render all three `FALSIFIED`. No case states a current view.
5. **Missing input.** An absent or non-passing measure, and a non-passing threshold, each render `NOT_ASSESSED`, and
   the scenarios it names `NOT_ASSESSED`, never `NOT_FALSIFIED`.
6. **Honesty.** The section states that FY27_Q1 is a retrospective demonstration with no prospective falsification
   evidence, and lists the prospective test as not delivered.
7. **Consumers.** With a bear and a bull trigger on a metric shared with a falsifier both `REACHED`: `evaluate`'s
   rows, `thesis_impact`, `observable_falsifiers` and `risk_probe` are unchanged from the same run with no triggers,
   and no probe row is `FLAGGED` by them.
8. A watch item renders `UNRESOLVED` with `first_due` and no status it cannot compute. The monitoring limitation
   renders.
9. Probabilities render as `{{e:opinion}}`, and no probability-weighted value is computed.
10. S1's and S2's sealed versions still `MATCH`. Regenerated report, real Sol `APPROVE` on the test database.

### Live close — one publication

**Work.** Parity (§7.5), and the §7.6 rehearsals. **Estimate.** About 40-60 production lines, 70-100 test lines.

**Sequence.** A fresh test restore; the complete regeneration; real Sol `APPROVE`; the parity record. Then live: 0046,
thesis import, `ledger run … --parity`, real Sol round, digest comparison, `check-live`.

**Acceptance.** §7.5's rehearsal. Live: all `MATCH`, parity held, digests unchanged, Sol `APPROVE`.

**Total estimate.** r6, after the S1 plan moved S3's book parsing, guards and cases 1-2 into S1: **I** about 1,245-1,480
production lines, 50 SQL and 980-1,240 test lines; S1 about 1,000-1,130 and 720-880, S3 about 75-130 and 80-120, and S2 and
the live close as stated. The r5 estimate follows. About 1,085-1,350 production lines, 50 SQL and 670-870 test lines, about 95-120 production lines
above r2: the output registry, model versioning, version-bound contracts and scenario falsifiers, less stale-statement
triggers and the twin branch of `contract_bindings`. Sol found no basis for halving it. **I** Binding and the import
branch are the uncertain parts. Estimates, not acceptance ceilings.

**Cut to keep it small:** capacity model, sensitivity tables, gap-interest feedback, debt-equity split, credibility
adjustment, EPS, peer comparison, a runtime proposal command, a generic extractor, stale-statement triggers.

## 9. Findings to date

Sources under `scratchpad/research4/`: `research3-spec-r1-sol.txt` (R3), `spec-review-r1.md` (r1), `spec-review-r2.md`
(r2); r3 is Sol's r3 review; r4 is Sol's fresh closing review of r4. "Fixed" means in the contract, not yet proven at runtime. Sol accepted OD-2 and OD-4 as
written (§2, §5.3). No question here is the owner's financial judgement; §7.1 is the owner's ruling.

| Finding | Resolution | Where |
|---|---|---|
| R3-5, r1-2 | FY27_Q1 only; book binds one quarter | §2; S1 case 5 |
| R3-18, r1-11 | Disclosure meaning: sealed contract, columns, spans, cross-foot, issuer | §6.2; S1 case 4 |
| R3-19, r1-4, r2-3 | Closed `ROLES` and `OUTPUTS`; exact-key `_THESIS_CLAIM`; sealed calendar | §5.1, §7.3, §7.4 |
| R3-20 | Probabilities: unique scenarios, sum exactly 100, one horizon | §6.2; S3 case 1 |
| R3-21, r1-3, r1-12, OD-8, r2-1 | Sealed `ScenarioFalsifier`; separate evaluator; coverage; watch items; retrospective limit | §6.2; S3 cases 2-8 |
| R3-22 | Owner floor: five years, bridge, unit economics, working capital, gaps named | §3, §5 |
| r1-1, OD-3, r2-2 | Two permissions; true fallbacks; estimate split | §7.1 |
| r1-5, OD-1 | Checks inside `_persist` before the seal | §7.2; §7.4 |
| r1-6 | Assumption always opinion; comparison per comparable year | §6.2; S1 case 8 |
| r1-7, r1-8, OD-5 | Cash-only `L_0`; "funded" never rendered; `Dvd_t` never negative | §5.5; S2 cases 4-5 |
| r1-9 | Rate anchors: formula, sign, guard, rounding | §5.3, §5.7 |
| r1-10 | No claim for a failed block; held blocks from sealed keys | §5.6, §7.3 |
| r1-13, OD-7 | Parity by value, in the write's transaction; one live publication | §7.5, §8 |
| r1-14, r2-4 | Three correction routes; released model ids immutable | §7.6 |
| r2-5, r3-1 | Contract sealed in the twin; own twin for imported, cited twin for drafted; no `bound` | §6.2, §7.2, §7.3; §7.4 Contract replay |
| r1-15 | Claim counts from the registry; estimates not ceilings | §7.2 |
| OD-6, OD-9 | Pinned publication; `ledger narrate` refuses a version holding any `fcst.` claim, before any model call, and narrates a claim-free `NOT_ASSESSED` version as today (r6; r5 refused any `forward_view` version, which would stop every future narrate) | §6.2 rule 6; §10 |
| r2-6 | Blocking Task 0, including no quoted thesis claim anywhere live | §8 Task 0 |
| r3 notes | Retrospective status plain; §7.1 wording; touch points moved to the plan note | §6.2, §6.3, §7.1, §10 |
| r4-1 | Model-authored free text holds no `{` or `}`, so no marker can relabel a computed number | §6.2 guards; S1 case 7 |
| r4-2 | `column` must equal the id's required period, whatever the arithmetic | §6.2 rule 3; S1 case 4 |
| r4-3 | Trace parity form: references normalised to evidence identity and child content, no row-id hashes | §7.5 |
| r4-4 | `TABLE` and `PROSE` scalar forms, each validated; range form removed; a disclosure's value is both bounds | §6.2 rule 3; S1 case 4; S2 case 6 |
| r4-5 | A `PROJECTION` must equal the canonical rounded result exactly at row 5 | §7.3 step 5; §7.4 Tamper; §10 |
| r4-6 | Loss-year dividend case follows the prior-year formula, both directions | S2 case 4 |
| S1 plan review r1 (C-1 to C-6) | r6: OD-9; retained header order; column separate from period; row binding and signed cells; realisation conditional on Task 0; capture identity explicit | §6.2 rule 3; §7.3; S1 cases 1, 4; §8 total; §10 |

## 10. Notes for the plan

- **Follow-up needed, not delivered here:** the FY27_Q2 run's design must evaluate the FY27_Q1 book's scenario
  falsifiers on that quarter, against the thresholds of the original sealed FY27_Q1 book, cited by its digest. A new
  book must not replace them before that test. This spec adds no such path because no FY27_Q2 run exists to prove it.
  Later judgement must still not enter earlier reports.
- `.claude/project/invariants.md` takes the §7.1 text once the owner rules, before S1 is committed.
- The targets document says first-party balance sheet and cash flow are not extracted
  (`docs/goals/2026-10-27-research-report-targets.md:35`). They are, for half-year and annual filings: correct it.
- `.claude/project/repo-map.md` still says the repo is pre-code. NOTICED BUT NOT TOUCHING: orientation only.
- `CONTEXT.md`'s Thesis entry describes the derived sections; add `forward_view` when S1 lands. Update
  `docs/status/dashboard.html` per the standing rule after each committed task.
- New evidence files under `docs/evidence/phase-0.5/` are committed before import, because `evidence_holds` requires
  the commit (`ledger/importer.py:225`).
- **Implementation touch points**, a starting list and not a contract:

| Where | Change |
|---|---|
| `migrations/0046_projection_citation.sql` | `PROJECTION` kind; `projection_model text`; `numeric_claims_check1` adds the kind to the null-key set; a check that such a claim sets no other citation column and has a value; `version_sealed_digest` gains a `CASE` for the one column, as 0042 |
| `contracts/ledger.py:58-64,138-161` | Enum member, one `Citation` field |
| `ledger/claim_check.py:31-39,110-115` | Kind joins `VALUED`; row 5 compares it without rounding |
| `ledger/lifecycle.py:268-283` | After `resolved`, add `resolve_projections`, in `citations.py`; `disclosure_contract` for `disclosure.*` and `fcst.d.*` keys |
| `memory/retrieval.py:220-222` | The same function for those keys |
| `ledger/citations.py:167-174,306-315` | `_THESIS_CLAIM` matches the exact cited key, which existing `thesis.*` citations meet |
| `ledger/citations.py:205-217` | `_IMPORTED_QUOTES` excludes `BOOTSTRAP_THESIS` reports; `disclosure_contract` beside `bound_contract` |
| `ledger/importer.py:315-324` | Pre-approval check, §7.2 |
| `ledger/run_draft.py:122-133,395-399,685-704,713-719` | The "forward scenarios" `NOT_DONE` line narrowed when the section exists. `forward_view`'s claims join `claims` **before** `_check_sources` at `:396`, so disclosures and base traces pass source admission. Disclosure blobs from the bound book join `allowed_captures`; pinned `published` times join retrospective lookups. Optional parity (§7.5) |
| `ledger/falsifier_status.py:46,129-139` | `DERIVED`; `BoundThesis` exposes the new claims' row ids. `evaluate` and `derived` unchanged |
| `verify/thesis_predicates.py:84-105` | `forward` block with validators; falsifiers untouched |
| `ledger/import_mapping.py:286-291` | `map_q0` branch for `forward`, with no `bound` |
| `ledger/rework.py:233-249` | A branch for `fcst.*` keys (§7.6) |
| `ledger/narrate.py:233` | Refuses a version holding any `fcst.` claim, before any model call (OD-9) |
| `ledger/forward_model.py`, `ledger/forward.py` (new) | Pure model and `MODELS`, `OUTPUTS`; binding, `validate_book`, trigger evaluator, parity and code-built section |
