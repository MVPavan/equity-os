# RESEARCH-3 — Risk probe, management credibility and narrative — Spec

**Status:** approved r4 (2026-10-28) — approver gpt-6.1-sol, `APPROVE` on the fresh critical
review's re-review. History: Sol r1–r3 review loop (r3 residual `same_as` applied by orchestrator
ruling after three rounds); fresh critical review (6 findings) fixed in r4. Owner rulings
OD-1/OD-2 integrated; scope ruled by the orchestrator. Plan notes from the approval: year-specific
guidance rules need matching sealed guidance-contract bindings for end-to-end `AS_KNOWN`; transcript
filing-time coverage and non-retrospective manifest supply are unverified (`AMBIGUOUS` fallback).
**Origin:** bead `eqos-bnx`, slice 3 (owner OK on slices 1→2→3, bead notes 2026-10-23). Owner
direction 2026-10-27: `docs/goals/2026-10-27-research-report-targets.md`. Register A-04 and B-02
(`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md:34,52`; v2 is the
operational register, invariant 5).
**Implementer:** Opus. **Scope:** three slices — the risk probe with a short explanation (the first
reader-facing slice), management credibility, and `ledger narrate`. The forward view is
RESEARCH-4 (§7). The sample reports are used only for their section structure; nothing here is
copied from their text or values.

## 0. Ground truth this spec rests on

- **The run draft is the authoritative report.** It is written by `write_run_draft`
  (`ledger/run_draft.py:277-362`) and checked `AS_KNOWN` in the same transaction. The legacy
  renderer (`output/earnings_update.py:442-530`) stays frozen because `ledger import`
  byte-compares it (RESEARCH-1 F-3, D1). Everything below goes into the run draft only.
- **The pattern to follow (RESEARCH-1).** `run_draft._sections` (`run_draft.py:632-672`) appends
  derived sections after the code-built ones. `falsifier_status` selects the thesis `APPROVED` at
  the derivation cutoff (`falsifier_status.py:97`), evaluates it with a pure function (`:139`) and
  cites thresholds as `THESIS_CLAIM` (`:188-241`). Rework skips `DERIVED` sections and claims
  (`falsifier_status.py:43`; `rework.py:221,227`).
- **Schema already admits everything here.** Section keys are free strings
  (`contracts/ledger.py:196-203`). Claim value kinds include `RATIO` and `DAYS`
  (`migrations/0012_report_ledger.sql:64-65`), citation kinds include `FIGURE`, `CALCULATION`,
  `SOURCE_QUOTE`, `POLICY` and (since `0042`) `THESIS_CLAIM`, trace operand roles include
  `CLOSING` (`0001_evidence.sql:369-370`), and `formula_id` is free text (`:339`).
  **RESEARCH-3 needs no migration** (the only migration in r1 was OD-3's projection citation,
  now RESEARCH-4).
- **Numbers in prose.** `scan_section` (`ledger/numeral_scan.py:44-64`) blocks any digit outside
  placeholders, location and class markers, after removing structural patterns (`:23-40`). Gaps
  it does not close: number words ("forty"), the id exemption (`amount:123` passes as an id,
  `:35`), list numbering, decorations adjacent to a placeholder (`-{{c:…|}}`), and the
  placeholder style field. §5 closes these for model-written sections.
- **Locations.** `resolve_location` (`citations.py:320-334`) checks only that a first-party
  capture has a non-empty span. It does not check issuer, package or cutoff (§5).
- **Traces.** `_Binder.operand` takes the single `MAPPED` interpretation of a key under the run's
  pins and requires it to equal the run's value (`run_traces.py:150-197`). Keys are this
  quarter's duration (`:146-148`). `_compute` has two operands, both recorded `DURATION`, and
  formulas `DIFFERENCE`, `SUM`, `CHANGE_PCT`, `ETR`/`RATIO_PCT` (`:261-303`). There is no plain
  ratio, no constant operand and no instant role in use.
- **Unitless claims.** `DAYS`, `RATIO` and `COUNT` are `UNITLESS` in the claim check
  (`claim_check.py:140`), but the keyed-claim builders cover only the unit table (`:43-50`;
  `import_mapping.py:351-406`), so a unitless claim has no constructor today.
- **Falsifier import is percent-only.** `_falsifier` requires a `_pct` metric and builds a
  `PERCENTAGE` threshold (`import_mapping.py:573-593`).
- **Cash-flow sign.** The canonical cash flow is inflow-positive
  (`config/dictionary/v3/cash_flow.yaml:1-14`), and the mapping applies sign −1 to PPE purchases
  (`config/mappings/xbrl/v5/in_capmkt.yaml:401-404`). So `cf_capex_ppe` is **negative** for an
  outflow; the dictionary's "positive = outflow" (`cash_flow.yaml:108`) describes the XBRL
  element, not the canonical value.
- **Balance sheet and cash flow are filed and mapped, but no report reads them** (verified by
  element names and contexts in the retained XBRL the Apar configs point to):
  - FY26_Q2 integrated filing: half-year contexts (from 2025-04-01), period-end and prior-year-end
    instants. It carries `TradeReceivablesCurrent`, `Inventories`, `TradePayablesCurrent`,
    `Borrowings*`, `Equity`, `CashFlowsFromUsedInOperatingActivities`,
    `PurchaseOfPropertyPlantAndEquipment…`.
  - FY26_Q4 and FY25_Q4 filings: the same elements for the full year. FY26_Q3: none.
  - Mapping set v5 maps all of them (`in_capmkt.yaml:36,40,44,116,216,224,272,276,300,312,398,402`).
  - **Not verified (no DB read here):** that the store holds the `MAPPED` interpretations. Task 0.
- **Each run's latest half-year or annual statements.** Q3 uses its QoQ comparator, FY26_Q2
  (`config/aparinds-fy26-q3.yaml:100-101`); Q1 FY27 uses FY26_Q4 (`aparinds-fy27-q1-pg.yaml:100-101`);
  Q4 has its own and FY25_Q4 as YoY comparator (`aparinds-fy26-q4-pg.yaml:106-107`). Only Q4 has a
  same-basis prior year.
- **Apar guidance.** Rules extract `cables_revenue_growth`, `cables_ebitda_margin`,
  `conductor_ebitda_per_mt`, `conductor_volume_growth` (`aparinds-fy26-q*.yaml:114`).
  - Horizons are free strings and part of the ledger key (`run_draft.py:96`). Some are wrong as
    windows: a "CAGR" quote is stored `annual` (`aparinds-fy26-q3.yaml:116-119`; `-q4-pg.yaml:125-128`).
  - `_guidance` keys prior entries by claim key and replaces a restated entry
    (`run_draft.py:502-519`); `Prior` holds only the predecessor head's guidance entries
    (`:137-153`). So a commitment's first statement is lost once restated.
  - Filings report segment revenue and PBIT, not segment EBITDA or volumes. Only cables revenue
    growth has a filed actual, and it needs segment lines not yet in run drafts (bnx slice 2;
    `eqos-djv`, `eqos-ghv`).
- **Rework.** Rework carries lines whose claims are unchanged and refuses when a carried line or a
  section scaffold moved (`rework.py:112-122`); it reads the head's non-`DERIVED` sections
  (`:227-267`).
- **Panel.** The panel gives the reviewer only the rendered narrative and validation result
  (`panel.py:194-196`), no source evidence.
- **Pledges, related parties, contingent liabilities, auditor remarks, ratings.** Not in a run's
  package or not extracted (`run_draft.py:598-603`; `shareholding.yaml:18-20`; DOCS-1 registers
  documents but extracts nothing, `docs/plans/DOCS-1-first-party-document-intake.md:8-17`).

## 1. Shared rules

1. **Epistemic labels.** Every row and paragraph carries `{{e:…}}`: *observed* (a filed figure or
   a transcript quote), *computed* (a code result over cited claims), *inferred* (a code
   extrapolation such as `ON_TRACK`, or a model explanation tied to cited claims), *opinion* (an
   approved limit).
2. **Fail closed per row, not per report.** A missing input renders the row's reason
   (`NOT_ASSESSED: …` / `UNRESOLVED: …`). A section with no evaluable row renders one such
   paragraph. A structural fault (unparseable thesis block, unknown formula, unit mismatch) raises
   `RunDraftError`, as RESEARCH-1 D4.
3. **Order.** `risk_probe` then `management_credibility`, after `observable_falsifiers`. Both join
   `DERIVED`.
4. **Limits are opinions in the approved thesis**, imported through the thesis-successor path and
   approved by the panel (RESEARCH-1 D6), cited into runs as `THESIS_CLAIM`. A run never invents
   one.
5. **No number reaches prose except through a claim.** Labels and reasons carry no digits
   (`falsifier_status.py:1-10`). Dates and period labels are structural.

## 2. Risk probe

**Questions served.** What happened (computed checks), why (S1 template explanation; S3 model
note), evidence against the thesis (a breached limit is a falsifier), what to monitor (each
`NOT_ASSESSED` names its missing source).

**Statement selection.** The run's own XBRL if it has a `MAPPED` balance-sheet interpretation at
its period end, else its QoQ comparator's, else none ("NOT_ASSESSED: no filed balance sheet in the
run's package"). Every row renders its **balance date** and **flow window** (start–end). A
selection from the comparator is **stale**: its balance date precedes the run's period end.

**Checks.** `D` is the flow window's calendar days, inclusive, taken from the flow operand's own
period interval. The `run.days` formula derives it from that interval, so replay recomputes it from
the trace; it is never an operand and never rendered as digits.

| Id | Metric id | Check | Formula (trace) | Rules |
|---|---|---|---|---|
| R1 | `probe_receivable_days` | Receivable days | `run.days`: `trade_receivables_current` (CLOSING) ÷ `revenue_from_operations` × D | T↑, L |
| R2 | `probe_inventory_materials_days` | Inventory days, materials-cost basis | `run.days`: `inventories` (CLOSING) ÷ M × D | T↑, L |
| R3 | `probe_payable_materials_days` | Payable days, materials-cost basis | `run.days`: `trade_payables_current` (CLOSING) ÷ M × D | L |
| R4 | `probe_cash_conversion_pct` | Cash conversion | `run.ratio_pct`: `cfo` ÷ `profit_for_period` × 100 | S, T↓, L |
| R5 | `probe_capex_intensity_pct` | Capex intensity | `run.outflow_pct`: −`cf_capex_ppe` ÷ `revenue_from_operations` × 100 | L |
| R6 | `probe_borrowings_to_equity_ratio` | Borrowings to equity | `run.ratio`: (`borrowings_current` + `borrowings_noncurrent`) ÷ `total_equity` | T↑, L |

- **M is a materials-cost proxy, not COGS:** `cost_of_materials_consumed` +
  `purchases_of_stock_in_trade` + `changes_in_inventories` (two child `run.sum` traces). It omits
  conversion costs, so R2/R3 overstate days against full COGS. Rows and metric ids say
  "materials-cost basis"; a limit can only target that metric id, so it uses the same definition.
- **Closing balances (OD-8).** All balance operands are `CLOSING` and labelled "closing".
- **R5 sign.** Capex is negated because the canonical outflow is negative (§0); R5 is positive
  for spend.

**Domain guards (evaluated before rules).**

| Condition | Row status |
|---|---|
| An operand missing, or a flow denominator (revenue, M) ≤ 0 | `NOT_ASSESSED` (reason) |
| A balance other than `total_equity`, or negated capex, < 0 (sign anomaly; equity is R6's rule) | `NOT_ASSESSED` ("sign anomaly in filed line") |
| R4: `profit_for_period` ≤ 0 | `FLAGGED` ("non-positive profit"); ratio not shown; S still evaluated |
| R6: `total_equity` ≤ 0 | `FLAGGED` ("non-positive equity"); ratio not shown |

An adverse condition is never an ordinary `PASSED`.

**Rules.**
- **S, same period.** R4 is `FLAGGED` when `cfo` < `profit_for_period` (two cited values, no
  constant).
- **T, trend.** Evaluable only when the package holds a prior statement that matches on all of:
  balance date one fiscal year earlier (same month-day); same duration class (half-year or full
  year) and same flow-window start month; each period's own `D`; same basis (consolidated), same
  mapping-set canonical ids and no dimensions. Then `FLAGGED` if the check moved in the arrow's
  direction. Otherwise "trend not evaluable: no matching prior". On Apar this is the Q4 case only
  (FY26 vs FY25 annual).
- **L, limit.** A thesis falsifier on the probe metric id (OD-4: falsifiers, typed). A `WEAKENED`
  falsifier makes the row `FLAGGED` and the row names the falsifier id.
  - **Staleness.** A stale selection renders its values and states which statement it is, but it
    does not register its metric for falsifier evaluation in that run: the falsifier shows
    `NOT_ASSESSED: latest statement predates the period`. A breach is therefore reported once,
    in the run that owns the statement.

**Status, first match wins.** Guard result; else any evaluated rule fired → `FLAGGED` (rules
named); else a rule was evaluated → `PASSED`; else `COMPUTED` (with a reason naming what was not evaluable (for example limits not assessed on a stale statement)).

Non-evaluated sources (related parties, pledges, contingent liabilities, auditor opinion,
capitalised intangibles, rating remarks, disclosure lapses) each render `NOT_ASSESSED` naming the
missing source.

**Explanation (S1, code-built, no model).** Each `FLAGGED` row gets one fixed sentence chosen by
rule and check, stating what the rule means for the business (for example cash conversion under S:
reported profit was not matched by operating cash in the flow window). One closing sentence
summarises the category mix (which of accounting, business, liquidity, solvency carry flags) and
names the coverage gaps. Labelled *computed*; no digits. S3 adds the model's `risk_notes`.

**Ledger.**
- Claims `probe.<id>` (`CALCULATION`, value kind `DAYS`, `PERCENTAGE` or `RATIO`, unitless where
  kind is unitless).
- **Raw filed amounts (OD-2).** Each operand line the probe uses is shown beside its ratio as
  `probe.<id>.<canonical_id>`: a `FIGURE` claim on its filed fact, labelled *observed*, single
  source. `_filed_key` (`citations.py:337-341`) widens to these keys; that is the invariant-7
  filed-figure extension the owner ruled. No amount is typed or computed by a model.
- `probe.<id>.prior` (`CALCULATION` on the comparator) when T is evaluable.

**Typed limits.** `_falsifier` maps the metric-id suffix to a value kind: `_pct` → `PERCENTAGE`
(`%`), `_days` → `DAYS`, `_ratio` → `RATIO` (both unitless). `METRICS` entries gain the measured
claim's value kind. Import refuses (Q0) a suffix not in the map, or a registered metric whose value
kind disagrees with its own suffix's kind; the evaluator raises `RunDraftError` if the measured
claim's value kind is not the threshold's.

## 3. Management credibility

**Questions served.** Each commitment (quote, observed), its window, the filed actual (computed),
revision events and outcome; what remains unresolved; why (S3 model notes).

**Commitment episode.** One episode = (metric, scope, window key). Its id is
`<metric>.<scope>.<window key>` (for example `cables_revenue_growth.consolidated.FY26`); scope is
the guidance contract's. The window key is the `FY<yy>` label; for `MULTI_YEAR` and `AMBIGUOUS` it
is `<class>.<entry id>`, so each such quote is its own episode and no date is invented, unless
its entry links an earlier one with `same_as`.
- **Window (rule H).** `config/guidance_targets/<symbol>.yaml` has one live entry per stated
  quote, keyed by (guidance claim key, capture, anchor). Each entry gives:
  - `id`: a slug unique in the file;
  - `window_text`: a substring of the quote;
  - `window`: `FY<yy>`, or `MULTI_YEAR`, or `AMBIGUOUS`;
  - `definition`: the measure promised — the metric's registered definition id, or another id when
    the quote qualifies the measure (for example excluding a business);
  - `same_as` (optional): the id of an earlier entry restating the same promise (same metric, scope
    and window class). The entry joins that entry's episode, so revision events apply; it never
    changes the window or outcome. Sol checks each link at the phase review; unlinked quotes stay
    separate;
  - `supersedes` (optional): the id of an entry for the same (claim key, capture, anchor) whose
    mapping this entry corrects (see Pinning);
  - an entry digest over all fields plus the quote.
- **OD-9.** The window must follow from `window_text` alone: an explicit fiscal-year label, or
  "this year" / "current year" / "next year" resolved against the **reference fiscal year**: the
  fiscal year containing the transcript original's NSE filing time in the pinned retrieval
  manifest (A-02 v2; never `retrieved_at` or first-seen). Relative wording stays `AMBIGUOUS` when
  that filing falls in a later fiscal year than the run's period end (a Q4 call held after
  year-end, e.g. FY26_Q4 filed in May 2026, where "this year" could be FY26 or FY27), or when the
  manifest has no filing time. An anchor or surrounding text cannot supply a year the quote does
  not state. If no window is established, the entry is `AMBIGUOUS`. The implementer writes the
  entries; Sol checks them at the phase review.
- **Several annual targets in one transcript.** `_claim_for` takes only the first match per rule
  (`guidance_extractor.py:77`), and the ledger key is `ledger.<metric>.<horizon>.<scope>`
  (`run_draft.py:96`), which `_Body.add` refuses to duplicate (`:479`). So each year's target gets
  its own extraction rule whose pattern includes the year text and whose `horizon` is that
  `FY<yy>` label. Both keys then reach the episode builder with no code change; a duplicate
  horizon for one metric still refuses. The rules go in the new quarter's run config; existing
  run configs, the legacy renderer and import key serialization are untouched.
- **Classification.** A "CAGR", "a year" or multi-period quote is `MULTI_YEAR` even when its
  extraction rule says `annual`. `MULTI_YEAR` and `AMBIGUOUS` episodes render
  `UNRESOLVED` ("window not single-year" / "window not established"). A missing entry renders
  `UNRESOLVED` ("window not mapped"). Existing ledger keys and horizons are unchanged, so the
  carry chain and PILOT-4 stay intact.
- **Carry.** The section holds `episode.<id>.original` and `episode.<id>.latest`, both
  `SOURCE_QUOTE` copies of the guidance claims with their citations. `Prior` gains the
  predecessor head's `episode.*` claims. A new quote opens a new episode. A quote mapping to an
  open episode's id updates `.latest`; `.original` never changes. Successive annual targets
  (FY26, FY27) and different windows are different episodes. Episodes are carried until their
  outcome renders, then kept as history. They are bounded by the run chain.
- **Pinning.** Each row renders its entry id and entry digest (`sha256 <hex>`, structural), sealed
  in the version digest. A run that carries an episode refuses (`RunDraftError`) when the
  config entry's digest differs from the one in the predecessor's row: history cannot be
  reinterpreted by a config edit. A new management statement is a new quote entry. A wrong
  mapping is corrected by appending a successor entry with `supersedes: <id>` and its own digest;
  the superseded entry stays in the file unchanged, so its pin still verifies. Each entry has at
  most one successor, chains are acyclic, and a `same_as` naming a superseded id resolves to its
  live successor. The next run builds episodes from live entries and renders a correction line
  per supersession since the predecessor: old and new entry ids, digests and interpretations
  (window, definition). An episode left with no live entry renders once as `UNRESOLVED`
  ("mapping corrected", naming the successor entry) and is then dropped. A previously used entry
  that is missing refuses the same way.

**Revision events** (between consecutive statements of one episode, never across episodes).
1. **Comparability first.** The guidance contract has to be equal: metric, scope, unit, currency,
   constant-currency and `definition`. If any of them differs, the event is `REVISED` ("basis
   changed") with no direction.
2. **Compared value.** A point uses its value. A closed range [L, U] uses its midpoint. An
   open-ended `plus` promise uses its binding bound. If one statement is open-ended and the other
   is not, both compare on the binding bound (L for `HIGHER`, U for `LOWER`). A `plus` promise on
   a `LOWER` metric renders `UNRESOLVED` ("open bound in the wrong direction").
3. **Event.** Higher → `REVISED_UP`; lower → `REVISED_DOWN`. If the midpoint is equal but the
   range changed, the event is `REVISED` ("range widened" or "range narrowed"). Otherwise
   `REAFFIRMED`.

Revision events work on Apar today. They render in their own column and never replace the
outcome.

**Actual registry (rule A).** `ACTUALS: (metric, scope) → (actual claim-key template for the
window, better ∈ {HIGHER, LOWER}, the actual's basis, interim rule | none)`. The basis is unit and
currency, constant-currency (false for a filed figure) and definition id. An unregistered pair
renders `UNRESOLVED` ("no filed measure").

**Endpoint comparability.** Each endpoint (`.original`, `.latest`) is assessed against the actual
only when its scope, unit and currency, constant-currency flag and `definition` equal the actual's.
An incompatible endpoint renders `UNRESOLVED` ("promise basis differs from the filed measure",
naming the field); the other endpoint is still assessed. This applies to steps 2 and 4 below.

**Outcome, first match wins.**
1. Window unresolved (rule H) or no filed measure (rule A): `UNRESOLVED` with the reason.
2. The window has ended and the actual is in the package or the pinned predecessor. The outcome is
   computed twice, once against `.original` and once against `.latest`, each `ACHIEVED` or
   `MISSED`. The actual is rounded `ROUND_HALF_EVEN` to that statement's own precision and then
   compared with its binding bound.
   - **OD-7.** The row discloses the effective tolerance ("rounded to the guidance's stated
     precision") and shows the unrounded actual.
   - `about` adds no extra tolerance.
3. The window has ended with no actual by the cutoff: `UNRESOLVED` ("actual not yet filed").
4. The window is open and the metric has an interim rule. The interim rule declares:
   - the year-to-date numerator window, ending at the run's period end;
   - the comparator window (the same fiscal months one year earlier);
   - the denominator;
   - how the year-to-date value relates to the annual bound (for a growth rate or a margin it is
     compared directly);
   - a fixed limitation label ("seasonality not adjusted; year-to-date assumed representative").

   The interim status is computed twice, against the binding bound of `.original` and of
   `.latest`, and shown side by side as in step 2. `ON_TRACK` means the year-to-date value meets
   that bound. `BEHIND` (OD-6) means it does not. Both are *inferred* and always carry the label.
   If either window is missing, the outcome is `UNRESOLVED`.
5. The window is open with no interim rule: `UNRESOLVED` ("not due" or "no interim rule").

An actual taken from the predecessor head keeps its citation, and its capture joins
`allowed_captures` (`run_draft.py:598-603`), as prior entries do.

**Ledger.** The section is `management_credibility`. Rows cite the `episode.*` claims through
placeholders. The actual is `cred.<metric>.<scope>.<window>`, either a `CALCULATION` or the
predecessor's cited claim. No migration.

**Apar today:** revision events. Cables revenue growth is `MULTI_YEAR` (CAGR and "a year"
quotes), so it stays `UNRESOLVED` until a single-year quote exists, even after the segment lines
land. The other three metrics are unregistered (`UNRESOLVED`, no filed measure).

## 4. `ledger narrate`

- **Flow.** `write_run_draft` writes deterministic version N with no model call, and N goes
  through submit and panel as today. `ledger narrate <version>` runs only on an `APPROVED` N that
  is its period's head and carries no `NARRATIVE`; anything else refuses. Submit needs a terminal
  predecessor (`lifecycle.py:160-167`), `predecessor_id` is unique (`0012_report_ledger.sql:19`) and
  `WITHDRAW` only follows an approval or import (`lifecycle.py:71-74`), so this is the one legal
  order with no lifecycle change. Narrate:
  1. builds the evidence bundle;
  2. calls the configured client outside any transaction;
  3. writes successor DRAFT N+1: N's sections and claims unchanged, plus the narrative sections
     `drivers`, `risk_notes`, `credibility_notes`, `thesis_narrative`, `open_questions`
     (`NARRATIVE`);
  4. checks N+1 `AS_KNOWN`.

  N+1 is then submitted and goes to the panel; its approval supersedes N. If the panel requests
  changes on or rejects N+1, the next `write_run_draft` on the period (rework or full successor)
  drops the narrative, and that version is approved and narrated again.

  Notes are written for `FLAGGED` probe rows and for `MISSED`, `REVISED_*` and `BEHIND`
  credibility rows. The model never assigns or changes a status.
- **Evidence bundle** is deterministic from N, size-bounded by config (maximum span length and
  total size; over the total cap → refuse), and goes to **both** the drafting call and the panel
  reviewer (`panel.py:194-196` gains it). It holds:
  - every claim's key, value as rendered, citation kind, and capture id with anchor;
  - for traces, the operand claim keys;
  - the **full text** of each span N cites (guidance quotes; each `.original`/`.latest` episode
    quote) — never truncated;
  - the citable locations: N's cited spans on eligible captures (below) whose full text is in the
    bundle. A span over the maximum length is left out of the bundle and is not citable.
- **Guardrails.** All deterministic and fail closed; on any failure no version is written.
  - Every section of N is byte-identical in N+1, and only `NARRATIVE` keys are added.
  - Each placeholder names an existing claim, and its style field is empty or a registered style
    with no digit.
  - Every claim is `MATCH`.
  - **Location eligibility.** Each `{{s:capture|anchor}}` must resolve (`citations.py:320-334`).
    Its capture must also be one of N's admitted captures (`allowed_captures`), belong to N's
    entity, and have been first seen at or before N's derivation cutoff. The (capture, anchor)
    must also be a citable location of the bundle, so the panel sees in full every span the
    narrative cites.
  - **Narrative-mode scan** applies to `NARRATIVE` sections, on top of `scan_section`:
    - The only structural exemptions are dates and period labels. Ids, list numbering, footnotes,
      hashes and the `× 100` literal all block.
    - A closed lexicon of number words blocks:
      - cardinals zero to nineteen, the tens, hundred, thousand, lakh, crore, million, billion;
      - dozen, twice, thrice, double(d), triple(d), halve(d), "-fold";
      - percent, per cent, bps, basis point(s).
    - A placeholder may touch only whitespace or `( ) , . ;` on either side. Anything else next
      to it blocks — a sign, digit, `%`, currency symbol, `×`/`x`, letter, `=` or `:`; that
      covers `-{{c:…|}}`, `{{c:…|}}x` and `amount:{{c:…|}}`.
  - **Coverage statement.** Deterministic coverage is: digits; the number-word lexicon; ids and
    other structural smuggling; decorations next to placeholders; style fields; claim existence
    and `MATCH`; location eligibility. **The panel's residual semantic review** covers the rest:
    "half" or "a quarter" used as quantities, comparatives and magnitude words ("most", "sharply"),
    arithmetic implied between claims, direction claims, and whether each sentence follows from
    the evidence it cites and carries an honest label. The panel decides on N+1, and its verdict
    stands.
- **Rework of a narrated version.** Rework treats `NARRATIVE` like `DERIVED`: it skips those
  sections, so a reworked successor carries no narrative. A narrative is therefore invalidated
  whenever any claim changes, and it is redrafted by running `ledger narrate` on the new head
  once it is approved. Narrate refuses a version that already carries `NARRATIVE` sections.
- **Out of scope:** the memory draft (it needs its own spec against invariant 11).

## 5. Build slices

Each slice ends with the four Apar run drafts regenerated, `AS_KNOWN`, every claim `MATCH`, the
slice's acceptance cases passing, and Sol `APPROVE` on the regenerated report. Live regeneration
waits for `eqos-dna` (LIVE-RUN-1). Until then slices are proven on the pilot's retained package,
and on synthetic test-DB interpretations for the adverse cases Apar does not exhibit.

### S1 — Risk probe with explanation and typed limits (first reader-facing slice)

**Task 0, read-only.** Under each run's pins, confirm a single `MAPPED` interpretation exists for
every §2 operand on the FY26_Q2, FY26_Q4 and FY25_Q4 captures, for the instant and the half-year or
annual contexts. Also confirm the rounding policy covers `DAYS` and `RATIO`.
- **Stop.** If any operand is missing or ambiguous, stop S1 and report the gap per capture and
  canonical id.
- **Remediation.** Re-run interpretation under a new pin through the existing admission path
  (`eqos-dna` launcher). A config or mapping fault becomes its own bead. S1 resumes once Task 0
  passes. No probe code is written around a gap.

**Work.**
- `_Binder` changes:
  - keys for closing instants and for the half-year or annual flow window;
  - operand values read from the interpretation rather than from a run value;
  - the `CLOSING` role.
- Unitless claim construction.
- Formulas `run.days` (D derived from the flow interval), `run.ratio`, `run.ratio_pct`
  (reusing `RATIO_PCT`) and `run.outflow_pct`.
- Three-operand M through child sums.
- Guards, rules S/T/L with prior matching, staleness, statuses.
- Raw `FIGURE` lines and the `_filed_key` widening.
- Typed `_falsifier` and typed `METRICS`.
- The template explanation.
- Then, operationally, a model-proposed thesis successor carrying probe limits, approved by the
  panel through the RESEARCH-1 Task 6 path.

**Estimate.** About 600–900 production lines and 400–600 test lines. The binder and claim
construction are the bulk.

**Acceptance cases.**
- R1–R6 values on the pilot package equal hand-computed values from the filed figures, with the
  balance date and flow window shown on each row.
- R5 is positive for a negative canonical capex.
- R4 is `FLAGGED` by S when cfo is below PAT. R4 with a loss is `FLAGGED` ("non-positive profit").
  R6 with negative equity is `FLAGGED` ("non-positive equity"), not `NOT_ASSESSED`.
- A zero or negative revenue or materials denominator gives `NOT_ASSESSED`; a missing operand gives `NOT_ASSESSED`
  naming it.
- T on Q4: FY26 against FY25 is evaluated and flags in the arrow direction. A half-year against an
  annual prior is not evaluable. A prior with a different `D` uses its own `D`.
- L: a `_days` limit on `probe_receivable_days` flags on breach. A registered `_days` metric whose
  `METRICS` value kind is `PERCENTAGE` is refused at import. A `_days` limit whose `METRICS` entry
  points at a `PERCENTAGE` claim raises `RunDraftError` in the evaluator. An unknown suffix is
  refused. Limits on
  `probe_inventory_materials_days` and `probe_payable_materials_days` import as `DAYS` and flag on
  breach.
- Stale: the Q3 run shows FY26_Q2 values, and its falsifier on that metric is `NOT_ASSESSED`.
- `COMPUTED` when there is no prior and no limit. Non-evaluated sources each name their source.
- Raw amounts cite their filed facts.
- Regenerated Apar reports show the risk table plus the explanation, and Sol `APPROVE` judges the
  explanation readable as analysis.

### S2 — Management credibility

**Work.**
- The rule-H file for Apar, with entries and digests.
- Episode claims, `Prior` loading them, and the digest pinning check.
- Revision events, rule A with `ACTUALS`, and the outcome logic with interim rules.

**Estimate.** About 400–600 production lines and 300–400 test lines.

**Acceptance cases.**
- Revision events: `REVISED_UP`, `REVISED_DOWN`, `REVISED` for basis changed, range widened or
  narrowed at the same midpoint, `REAFFIRMED`, and the plus-against-range binding-bound comparison.
- An ended episode, `MISSED` against `.original` and `ACHIEVED` against `.latest` (synthetic), with
  the unrounded actual and the tolerance disclosed.
- A CAGR quote under `annual` gives `MULTI_YEAR`, and the outcome is `UNRESOLVED`.
- A quote with no year gives `AMBIGUOUS`, and the outcome is `UNRESOLVED`. An anchor-only year is
  refused.
- FY26 and FY27 targets for one metric are two episodes. One transcript stating both years'
  targets, with one rule per year, yields two guidance claims and two episodes; two rules with
  the same horizon refuse.
- Relative years: "this year" in a Q3 FY26 call filed in January 2026 maps to FY26; "this year"
  in the FY26_Q4 call filed in May 2026 (after year-end) is `AMBIGUOUS`.
- Standalone and consolidated promises for one metric and window are two episodes with two
  actuals; neither's `.latest` changes the other's.
- Two distinct `MULTI_YEAR` promises for one metric and scope are two episodes. Two `MULTI_YEAR`
  restatements linked by `same_as` are one episode with a revision event; the outcome stays
  `UNRESOLVED`.
- A basis-changing revision (`.original` constant-currency, `.latest` reported): the event is
  `REVISED` ("basis changed"); `.latest` is `ACHIEVED` or `MISSED`; `.original` is `UNRESOLVED`
  with the basis reason.
- Editing or deleting a used entry is refused on the next run.
- Correcting a used mapping with no new disclosure: a successor entry with `supersedes` (window
  FY26 → `MULTI_YEAR`) passes the pin check; the next report renders the correction line with
  both ids, digests and windows, the old episode renders "mapping corrected" once, and the quote
  continues in its new episode.
- Interim: `ON_TRACK` and `BEHIND` with the limitation label. The same year-to-date actual is
  `BEHIND` `.original` and `ON_TRACK` `.latest` after a downward revision, side by side. A missing
  comparator window gives `UNRESOLVED`.
- **Plan note.** The plan covers both carried endpoints (`.original`, `.latest`) and a previously
  used mapping entry that has gone missing.
- Ended with no actual gives "actual not yet filed".
- Apar regenerated, with revision events and reasoned `UNRESOLVED` rows.

### S3 — `ledger narrate`

**Work.**
- The CLI, the evidence bundle (also passed to the panel), the client call, the guardrails, the
  narrative-mode scan, location eligibility and the `NARRATIVE` rework skip.

**Estimate.** About 400–600 production lines and 300–400 test lines.

**Acceptance cases. Each of these is refused and no version is written:**
- number words ("forty", "doubled");
- `amount:123`;
- a numbered list item;
- `-{{c:…|}}`, `{{c:…|}}x`, `amount:{{c:…|}}`;
- a digit in a style field;
- an unknown claim key;
- a location in another issuer's document;
- a location in the same issuer's later disclosure (first seen after the cutoff);
- a location in a capture outside the package;
- an otherwise eligible location (admitted capture, same entity, before the cutoff, resolving)
  that is not a citable location of the bundle;
- narrate on a version that is `DRAFT`, `IN_REVIEW` or not its period's head;
- an edited deterministic section;
- an extra section key;
- a bundle over the cap.

Full path: `write_run_draft` gives DRAFT N → submit → panel `APPROVE` → `narrate` gives N+1 →
submit succeeds → panel decides on N+1 with the bundle, and its approval supersedes N. A span over
the maximum length is absent from the bundle and not citable. Rework from an approved narrated
version gives a successor without narrative, `AS_KNOWN`, and `narrate` on it once approved gives
the next narrated version. The panel receives the bundle. The four Apar reports narrated, panel
verdicts recorded, Sol `APPROVE`.

## 6. Decisions

- **OD-1 (owner, closed).** C-12 measures machine effort: review-panel rounds, findings per report,
  open review-queue size and the deterministic checks. No human time is measured, and the gate says
  so. Panel decisions already record rounds and verdicts. The register text is amended
  (`register-v2.md` C-12).
- **OD-2 (owner, closed).** Raw filed balance-sheet and cash-flow amounts are shown beside the
  ratios as cited filed facts (§2 Ledger). This is the invariant-7 extension.
- **OD-4.** Probe limits are typed thesis falsifiers (§2), with no separate list.
- **OD-5.** Multi-year windows are `UNRESOLVED` here. A CAGR evaluation comes with the first
  dated multi-year promise.
- **OD-6.** `BEHIND` is defined only through an interim rule (§3).
- **OD-7.** No extra tolerance. The row discloses the effective tolerance and keeps the unrounded
  actual.
- **OD-8.** Closing balances, labelled. Average balances are not used.
- **OD-9.** The quote's own `window_text` establishes the window. An anchor never supplies a year
  (§3).

## 7. Deferred to RESEARCH-4 (forward view)

A separate spec written after DOCS-1 delivers presentation and concall extraction. Binding
requirements for it:
- Sol r1 findings 5, 18, 19, 20, 21 and 22, each answered explicitly.
- The owner floor: five-year estimates; revenue split by driver; unit economics; working-capital
  assumptions; the funding gap.
- r1 OD-3, the projection citation: option (a), a `PROJECTION` citation kind that recomputes from
  the version's own claims, against (b), an assumption operand in the trace store. Either one
  needs a migration. Decide it in that spec.
- E-01 stays deferred (`register-v2.md:109`). No DCF, target price or recommendation.

## Owner rulings (PavanMV, 2026-10-28)

- **OD-1:** C-12 is amended to measure machine effort: review-panel rounds, findings per report and
  open review-queue size, plus the deterministic checks. No human time is measured, and the gate
  says so. *Integrated in §6.*
- **OD-2:** the risk probe shows the filed raw amounts alongside the ratios. Invariant 7's
  filed-figure exception extends to the balance-sheet and cash-flow lines the probe uses. Each
  amount is cited to its filed fact and never typed or computed by a model. *Integrated in §2
  and §6.*
