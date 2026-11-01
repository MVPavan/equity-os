# RESEARCH-3 S1 — Risk probe with explanation and typed limits — Implementation Plan

**Origin:** `docs/specs/2026-10-27-research-3-thesis-analysis.md` §5 "S1" (approved r4,
gpt-6.1-sol `APPROVE`), with §0–§2, §6 and the owner rulings (OD-2: raw filed amounts beside the
ratios; invariant 7 extension). Bead `eqos-bnx`, slice 3 → S1. LIVE-RUN-1 (`eqos-dna`) is done:
the four live Apar run drafts FY26_Q2..FY27_Q1 are `APPROVED` (versions 8, 10, 11, 12), so live
regeneration is not blocked.
**Revision:** r2 (2026-11-01) fixes the 12 findings of Sol's r1 plan review (`REQUEST_CHANGES`);
the changed parts are marked "r2" with the finding number. r3 (2026-11-01) fixes Sol's r2
residuals #7 and #8 and its two notes, marked "r3". r4 resolves foreign test captures by pinned
SHA (Sol r3 #8). r5 (2026-11-01) fixes Sol's closing review (four P1), marked "r5": every
`map_q0` caller, a new test module under the 800-line ceiling, PILOT-11's trace closure, and the
probe's rework semantics (P11).
**Status:** approved r5 (2026-11-01) — approver gpt-6.1-sol, `APPROVE` on the re-review of the
closing critical review's fixes (plan rounds r1–r3, closing review, re-review).
**Goal:** every Apar run draft carries a `risk_probe` section after `observable_falsifiers`.
For R1–R6 it shows the traced ratio, the cited raw filed amounts, the balance date and flow
window, and a code-computed status with its reason (guards, rules S/T/L, staleness). It ends with
the template explanation and the non-evaluated sources. Probe limits are typed thesis falsifiers
(`_days`, `_ratio`, `_pct`). The draft still validates `AS_KNOWN` with every claim `MATCH`.
**Out of scope:**
- S2 (management credibility) and S3 (`ledger narrate`, `risk_notes`, narrative-mode scan).
- Average balances (OD-8), full-COGS days, any probe check beyond R1–R6.
- Extracting related parties, pledges, contingent liabilities, auditor remarks or ratings. They
  render `NOT_ASSESSED` only.
- The legacy renderer `output/earnings_update.py` (frozen; RESEARCH-1 D1).
- Any migration: the schema already admits `DAYS`/`RATIO` claims, `CLOSING` operands and
  free-text formula ids (spec §0).
**Constraints:**
- The LLM is never the authoritative calculator. Every material number links to a fact,
  interpretation or calculation trace (invariants 6, 7). Raw probe amounts cite their filed
  facts, labelled single-source (invariant 7 extension, OD-2).
- Missing inputs fail closed per row, not per report. A structural fault raises
  `RunDraftError` (spec §1 rule 2).
- Every row and paragraph carries `{{e:…}}`. Labels and reasons hold no digits; dates and period
  labels are structural (spec §1 rules 1 and 5; `ledger/numeral_scan.py:23-40`).
- Migrations `0001`–`0045` are immutable. No migration in S1.
- Frozen manifests change only via the approved re-seal flow. The pilot manifest is not edited.
- Never open `stage4_holdout.yaml`, `stage4_manifest.yaml`, `data/holdout/` or
  `data/raw/onboarding/`. Never print vendor readings.
- Crisp minimal code (owner 2026-10-14; `.claude/rules/core/04-agent-stack.md` "Code size").
  Python rules: `.claude/rules/python/`.

## Task 0 record (read-only, 2026-11-01)

Run under `scratchpad/research3-s1/t0_*.py` (migrator role, `read_only = True`, asserts
`current_database() == 'equity_os'`). They printed ids, periods, counts and signs only.

**Pins.** Comparison runs 1–4 (the pinned runs of live versions 8, 10, 11, 12) all pin
dictionary `v2`, mapping set `v6`, normalisation policy `v1` and extractor
`xbrl-occurrences/3`. `config/mappings/v6.yaml` includes `xbrl/v5/in_capmkt.yaml`, the entry
file the spec cites. Store interpretations under these pins: 1052 `MAPPED`, 979 `UNMAPPED` and
16 `PERIOD_AMBIGUOUS` (none of the ambiguous ones is a probe operand).

**Captures** (first registration of each blob, the one `find_capture_ref` returns):
- FY26_Q2 `90baae…` → capture 1
- FY26_Q4 `be8ef651…` → capture 5
- FY25_Q4 `94387374…` → capture 15
- FY25_Q2 `c44ac376…` → capture 13 (extra; see finding T0-2)

Captures 25 and 26 re-register blobs `f76a…` and `be8e…` and hold no interpretations under the
pins. Capture 5 is the one that binds.

**Result: Task 0 passes.** Every operand has exactly one `MAPPED` interpretation under the pins:
consolidated, Ind AS, INR, `CURRENCY_AMOUNT`, no dimensions, key digest present.
- I = instant at the capture's period end.
- H = half-year 2025-04-01..2025-09-30 (FY25_Q2: 2024-04-01..2024-09-30).
- A = annual 2025-04-01..2026-03-31 (FY25_Q4: 2024-04-01..2025-03-31).

| Canonical id | Context | FY26_Q2 (cap 1) | FY26_Q4 (cap 5) | FY25_Q4 (cap 15) | FY25_Q2 (cap 13) |
|---|---|---|---|---|---|
| `trade_receivables_current` | I | present (1) | present (1) | present (1) | present (1) |
| `inventories` | I | present (1) | present (1) | present (1) | present (1) |
| `trade_payables_current` | I | present (1) | present (1) | present (1) | present (1) |
| `borrowings_current` | I | present (1) | present (1) | present (1) | present (1) |
| `borrowings_noncurrent` | I | present (1) | present (1) | present (1) | present (1) |
| `total_equity` | I | present (1) | present (1) | present (1) | present (1) |
| `revenue_from_operations` | H / A | present (1) | present (1) | present (1) | present (1) |
| `cost_of_materials_consumed` | H / A | present (1) | present (1) | present (1) | present (1) |
| `purchases_of_stock_in_trade` | H / A | present (1) | present (1) | present (1) | present (1) |
| `changes_in_inventories` | H / A | present (1) | present (1) | present (1) | present (1) |
| `cfo` | H / A | present (1) | present (1) | present (1) | present (1) |
| `profit_for_period` | H / A | present (1) | present (1) | present (1) | present (1) |
| `cf_capex_ppe` | H / A | present (1) | present (1) | present (1) | present (1) |

Missing: none. Ambiguous: none.

**Rounding policy** (`config/rounding_policy/v1.yaml`): `DAYS: 2`, `RATIO: 6` and
`PERCENTAGE: 2` are all covered.

**Findings for the plan:**
- **T0-1, sign.** `cf_capex_ppe` is negative on all three captures, as spec §0 states, so R5
  negates it. `changes_in_inventories` is negative on all three. It is a signed P&L line and
  no guard applies to it; only M ≤ 0 is guarded.
- **T0-2, spec fact (FY26_Q2 trend).** Spec §0/§2 says "Only Q4 has a same-basis prior year …
  On Apar this is the Q4 case only". But FY26_Q2's YoY comparator FY25_Q2 (`c44a…`,
  `config/aparinds-fy26-q2.yaml:106-108`) carries the full H1 statement under the pins (column
  above). It matches T's criteria: balance date 2024-09-30, half-year, April start, consolidated,
  same ids, no dimensions. The plan implements T's rule as written, so **T is evaluated on
  FY26_Q2 as well as FY26_Q4**. FY26_Q3 and FY27_Q1 have no matching prior. Their YoY
  comparators FY25_Q3 and FY26_Q1 carry no instant. This is a fact correction, not a scope change;
  the phase-end review should confirm it.
- **T0-3, staleness.** FY26_Q3's own XBRL (capture 3) and FY27_Q1's (capture 7) hold no instant.
  So FY26_Q3 selects FY26_Q2 (its QoQ comparator) and FY27_Q1 selects FY26_Q4, both stale, as
  spec §0 expects.

No remediation task is needed.

## Investigation findings

**F-1. The binder is tied to run values.**
- `_Binder.operand` (`ledger/run_traces.py:150-197`) takes the single `MAPPED` interpretation
  of a key and refuses unless it equals the run's value. Its keys are this quarter's duration
  (`:146-148`, via `import_mapping.measurement_key`).
- `_compute` (`:261-303`) has two operands, both recorded `DURATION`. It knows `DIFFERENCE`,
  `SUM`, `CHANGE_PCT` and `ETR`/`RATIO_PCT` (`RATIO_PCT = "run.ratio_pct"`, `:79`), and it checks
  the result against a run value.
- Traces are held in `pending` and stored only once every line binds (`:463`).
- Probe operands have no run value: they are read straight from the interpretation.

**F-2. Child traces must be stored before their parent.**
- `put_calculation_trace` (`evidence/repository.py:636-647`) requires stored children: the
  parent's operand row holds `operand_trace_id = operand.calculation_trace_id`
  (`canon/formula.py:744-770`).
- `operand_from_result` (`canon/formula.py:459-488`) attaches `child_trace` but leaves
  `calculation_trace_id` unset.
- So a child sum (M, and R6's borrowings) is stored first, and its id goes into the operand.

**F-3. Claim construction is unit-table only.**
- `measurement_key` and `_valued` (`ledger/import_mapping.py:356-413`) index `UNITS[unit]`, so
  they cannot build a unitless `DAYS`/`RATIO` key or claim.
- `_typed` (`ledger/claim_check.py:142-150`) already accepts a unitless claim: unit, currency
  and scale all `None`, and value kind in `UNITLESS`.
- A `CALCULATION` claim resolves through its trace's value and key digest
  (`ledger/citations.py:542-555`, recursing child traces via `_INPUTS`, `:174-193`).
- The value check compares both values rounded at the claim's precision
  (`claim_check.py:108-113`).

**F-4. Filed figures.**
- A `FIGURE` cited to an interpretation must carry `FILED` and pass `_filed_key`
  (`citations.py:251-257,372-376`). Today that is only `cmp.*.prior` and the filed tax.
- `FILED_SUFFIX` renders "(filed value, single source, not cross-checked)"
  (`ledger/display.py:42`), which is the invariant-7 label.

**F-5. Falsifiers.**
- `_falsifier` requires `_pct` and builds a `PERCENTAGE` threshold (`import_mapping.py:578-601`).
- `METRICS` maps a metric to (label, claim key) (`ledger/falsifier_status.py:45-51`).
- `evaluate` (`:139-185`) has no value-kind check. `Disposition` is
  `WEAKENED`/`HELD`/`UNRESOLVED` (`verify/thesis_predicates.py:25-30`).
- `falsifier_status` imports `import_mapping`, so `import_mapping` cannot import `METRICS`.
  `importer.py` already imports `falsifier_status` (`:45`).

**F-6. Package captures.** The run's own XBRL provenance is `update.facts[...].sources[0]`, and
each comparator's is `comparative.qoq/yoy.prior_source` (as `bind_computed` uses them,
`run_traces.py:328-356`). `allowed_captures` already admits the comparators
(`run_draft.py:640-645`).

**F-7. The operand-blob check does not recurse.** `_OPERAND_BLOBS` (`run_draft.py:143-147`)
reads only the direct operands' captures, so a child sum's operands are not cutoff- or
package-checked through it.

**F-8. Rework.**
- `rework.plan` skips `DERIVED` sections and claims (`rework.py:221-227`). A claim in a
  `DERIVED` section therefore never needs reworkable atoms, and its child-trace operands carry
  no interpretation.
- `DISCLOSED` sections are not scaffolds (`:227`).
- r5: `DERIVED` means *re-derived on every run*, rework included. `write_run_draft` calls
  `evaluate` and `derived` on every run (`run_draft.py:347-349`), and `before_commit` calls
  `bind_computed` with the rework's `carry` gate (`api/cli.py:378-394`).
- r5: the PREP-5 `calls` fixture (`tests/fundamentals/test_prep5_rework.py:410-432`) spies
  `_Binder.operand`, `run_traces.conclude` and `EvidenceRepository.put_calculation_trace`. These
  assertions read its `conclude`/`put_calculation_trace` lists:
  - `test_prep5_rework.py:511-512, 539-540, 591-592, 644, 732-736`;
  - `test_prep5_corrected_filing.py:122-123, 151, 189`;
  - `test_pilot_citations.py:154`;
  - `test_pilot_e2e.py:533`.
  They encode "a rework computes and stores only its rejected lines' traces".

**F-11. Trace reachability (r5, Sol closing #3).**
- PILOT-11's resume check `retried["calculation_traces"] <= cited`
  (`tests/fundamentals/test_pilot_e2e.py:510-514`) admits only traces that a claim cites
  directly.
- A probe child sum is reached through its parent's `operand_trace_id` (F-2), so it would read as
  an orphan.
- The recursive `traces(id)` CTE inside `citations._INPUTS` (`ledger/citations.py:174-178`)
  already walks `operand_trace_id`.

**F-9. Pilot.**
- PILOT-4 asserts the exact non-quote key set (`tests/fundamentals/test_pilot_e2e.py:258-260`),
  each claim's route (`:262-280`) and an all-`MATCH` check.
- The pilot imports Q0 only, with no successor, so the probe's L rule is not exercised on the
  pilot.

**F-10. Successor import** (`importer.py:205-240,290-310`).
- It succeeds the newest version of the FY26_Q2 `BOOTSTRAP_THESIS` report, which must be its
  `APPROVED` head. A successor-2 therefore chains onto live version 6 (1.1.0) with no code
  change.
- `config/ledger_import.yaml` holds one `thesis_successor` block.
- `tests/fundamentals/test_ledger_import.py:573-574` pins the successor-1 files by its own
  constants, not through the config.

## Design decisions (for the phase-end review)

- **P1, claim keys.** `<id>` in spec §2 "Ledger" is the table's Id column:
  - `probe.R1` … `probe.R6` (ratio, `CALCULATION`);
  - `probe.R<n>.<canonical_id>` (raw filed amount, `FIGURE`, `FILED`);
  - `probe.R<n>.prior` (`CALCULATION` on the matching prior).
  The `R<n>` ids pass the numeral scan as rendered identifiers (`numeral_scan.py:37`). A shared
  operand (revenue in R1 and R5) gets one raw claim per row, shown beside each ratio.
- **P2, flow window (r2, Sol r1 #1).** The window does not depend on any one operand.
  - On the selected capture, the candidates are the periods of every `MAPPED` interpretation
    under the pins and the run's context that end at the balance date and whose
    `PeriodInterval.kind(fiscal_year_end_month)` (`contracts/measurement_key.py:57-85`) is
    `HALF_YEAR` or `YEAR`. The month is the entity's `FISCAL_YEAR_END_MONTH` setting
    (`pg/identity_seed.py:66`), read as `api/onboard_cli.py:479` does.
  - The window is the longest candidate (`YEAR` over `HALF_YEAR`). Quarters, nine-month, TTM
    and `OTHER` periods are never windows.
  - No candidate → `Statement.window` is `None`: R1–R5 are `NOT_ASSESSED` ("no half-year or
    annual flow window in the statement"); R6 (instants only) is still assessed.
  - Each flow operand is then read at that window. A missing one (revenue included) affects
    only the checks that use it: missing revenue makes R1 and R5 `NOT_ASSESSED`; R2–R4 and R6
    are unaffected.
  - `D` is the window's inclusive day count, taken from the flow operand's key period inside
    `run.days`.
  - Binding test: Task 4 (q), missing revenue on the pilot.
- **P3, child sums.**
  - M is `run.sum(run.sum(cost_of_materials_consumed, purchases_of_stock_in_trade),
    changes_in_inventories)`: two child traces, as the spec says.
  - R6's numerator `borrowings_current + borrowings_noncurrent` is also a child `run.sum`, which
    the spec implies but does not name.
  - Child traces are stored as soon as they are computed (F-2). A later refusal leaves an
    unreferenced, content-addressed trace, which is harmless.
- **P4, missing versus ambiguous at run time.** Zero `MAPPED` interpretations of an operand →
  the row is `NOT_ASSESSED`, naming the canonical id. More than one → `RunDraftError` (a store
  fault, as `_Binder.operand` treats it today, `run_traces.py:172-185`; Task 0 shows none on
  Apar). Both are proven at the database boundary by Task 4 (q).
- **P5, stale falsifier status.** Spec §2 says the falsifier "shows `NOT_ASSESSED: latest
  statement predates the period`". `Disposition` gains `NOT_ASSESSED`, used only for that case.
  Every other unevaluable falsifier stays `UNRESOLVED`, as in RESEARCH-1.
- **P6, categories for the closing sentence.** Spec §2 names four categories without a mapping.
  - R1 receivable days → accounting (revenue-recognition quality).
  - R2 inventory days → business.
  - R3 payable days → liquidity.
  - R4 cash conversion → accounting.
  - R5 capex intensity → business.
  - R6 borrowings to equity → solvency.
- **P7, one sentence per flagged row.** A row whose rules fire carries one sentence. A guard's
  reason stands alone; otherwise it names every fired rule's phrase, joined with "and" in the
  order S, L, T, and its business meaning comes from the check. Six check meanings and the rule
  phrases replace a 6 × 4 sentence table.
- **P8, adverse cases are pure unit tests.** The spec suggests synthetic test-DB interpretations
  for the adverse cases (loss, negative equity, cfo below PAT, zero denominator, sign anomaly,
  mismatched priors). The guards, rules and statuses are a pure function of operand values and
  windows (Task 3), so they are tested without a database. The database path (traces, unitless
  claims, raw figures, `MATCH`) is proven on the retained pilot (Task 4). This is cheaper and
  covers the same logic (`.claude/rules/python/testing.md`). The pure tests do not replace the
  two database-boundary tests: lookup failures (Task 4 (q)) and the recursive cutoff and
  package check (Task 4 (r)).
- **P9, `not_performed` qualified (r2, Sol r1 #11).** The owner counts receivable and payable
  days, OCF against profit and capex intensity as forensic checks
  (`docs/goals/2026-10-27-research-report-targets.md:14`), so the bare "- forensic checks" line
  (`run_draft.py:118-123`) would contradict the probe. It becomes "- forensic checks beyond the
  risk probe's ratio checks (see `risk_probe` for the sources it does not assess)". Wording
  only; PILOT-4 asserts the new line.
- **P10, non-evaluated sources (r2, Sol r1 #10).** S1 does not check whether a source is in the
  package or merely not extracted (spec lines 86-88 distinguish the two). Each renders the fixed
  "NOT_ASSESSED: <source> not assessed by this probe", which is true either way.
- **P11, rework re-derives the probe (r5, Sol closing #4).** Option (b): every run, selective
  rework included, recomputes the probe. Option (a), carrying the head's probe through an
  unrejected rework, is rejected:
  - Spec §1 rule 3 puts `risk_probe` in `DERIVED`, and every `DERIVED` section is re-derived on
    every run today (F-8). Carrying would make the probe the one `DERIVED` section that is not.
  - The probe's operands are half-year, annual and instant interpretations, which rework atoms
    do not track. Carrying would need probe atoms in `rework.plan`, or it would carry a stale
    probe after a corrected filing. It would also need to rebuild the section from stored claims,
    because L reads the current falsifier rows. That is new production code; (b) needs none.
  - (b) costs one test-fixture change and one assertion change, and every PREP-5 guarantee on
    run lines keeps its text and its meaning:
    - **Probe output keys.** Every probe trace's output key has a canonical id starting
      `probe.`: `probe.R<n>` for a ratio (its prior at the prior's period), `probe.R<n>.<sum>`
      for a child sum. Free canonical ids are the existing pattern for computed outputs:
      `bind_computed` keys calculations by their label (`run_traces.py:396-437`).
    - **Probe calls are counted apart.** The `calls` fixture records a `conclude` call whose
      output canonical id starts `probe.` under `calls["probe"]`, not `"conclude"`. It records
      a `put_calculation_trace` call whose trace's `key_digest` is one of those under
      `calls["probe_put"]`, not `"put_calculation_trace"`. Before the change no output id starts
      `probe.`, so the fixture behaves exactly as today. Every assertion listed in F-8 is
      unchanged and still proves that a rework computes and stores only its rejected run lines.
    - `bind_probe` reads operands only through `_Binder.filed`, never `_Binder.operand`, so the
      `operand` spy is unaffected.
    - **One changed assertion:** `test_prep5_rework.py:643-644`
      (`test_a_refused_rework_recovers_as_a_full_successor`). `len(calls["conclude"]) ==
      len(computed)` counts every `CALCULATION` claim, and the probe adds those claims. `computed`
      therefore excludes claim keys starting `probe.`. Before the change it is the same list.
    - **New assertion:**
      `test_risk_probe_binding.py::test_a_selective_rework_rederives_the_probe_on_the_heads_traces`
      (Task 4 (s)) proves the probe is regenerated and reuses the head's traces.
  - Rejecting a probe claim still refuses selective rework (`rework.py:222-227`); its route is
    `--full-successor` (Task 6).
- **P12, one trace closure (r5, Sol closing #3).** The recursive `traces(id)` CTE in `_INPUTS`
  (F-11) becomes the public `citations.TRACES: LiteralString`. It has one parameter,
  `%(traces)s`. Three users compose it with `"WITH RECURSIVE " + TRACES + ...`:
  - `_INPUTS`, with the same query text it runs today;
  - the recursive `_OPERAND_BLOBS` (F-7), instead of writing a second recursion;
  - the test helper `trace_closure(pilot, trace_ids) -> frozenset[int]`, which runs
    `TRACES + " SELECT id FROM traces"`. PILOT-11 and Task 4 (s) use it.

## File map

| File | Change | Responsibility |
|---|---|---|
| `src/fundamentals/verify/thesis_predicates.py` | modify | `Disposition.NOT_ASSESSED` (P5) |
| `src/fundamentals/ledger/import_mapping.py` | modify | typed `_falsifier` (`METRIC_KINDS`), the `map_q0` registered-kind check, unitless `measurement_key`/`_valued` |
| `src/fundamentals/ledger/importer.py` | modify | pass `falsifier_status.KINDS` to `map_q0` at both calls (`:172`, `:218`) |
| `src/fundamentals/ledger/falsifier_status.py` | modify | typed `METRICS` plus the six probe metrics, `KINDS` (metric → value kind), `RISK_PROBE` in `DERIVED`, value-kind check, stale → `NOT_ASSESSED` |
| `src/fundamentals/ledger/run_traces.py` | modify | `_Binder`: interpretation-read operands, closing and window keys, `CLOSING` role, formulas `run.days`/`run.ratio`/`run.outflow_pct`, child sums |
| `src/fundamentals/ledger/citations.py` | modify | `_filed_key` admits `probe.R<n>.<canonical_id>`; public `TRACES` CTE shared by `_INPUTS` (P12) |
| `src/fundamentals/ledger/risk_probe.py` | create | the probe: check table, guards, rules S/T/L, statuses, statement selection and prior matching, binding to traces and claims, section body, explanation, non-evaluated sources |
| `src/fundamentals/ledger/run_draft.py` | modify | `RunDraft.probe`, probe claims in the version, stale keys into `evaluate`, `risk_probe` section after `observable_falsifiers`, `_OPERAND_BLOBS` recursive over `TRACES`, qualified `NOT_DONE` line (P9) |
| `src/fundamentals/api/cli.py` | modify | call `bind_probe` in `before_commit` after `bind_computed` and pass it to `RunDraft` |
| `tests/fundamentals/test_falsifier_status.py` | modify | typed-limit import refusals, `DAYS` limits flag on breach, evaluator kind mismatch, stale `NOT_ASSESSED`; `metrics=KINDS` at the existing `map_q0` calls `:108`, `:196` (r5) |
| `tests/fundamentals/test_ledger_import.py` | modify (r5) | `metrics=KINDS` at the existing `map_q0` calls `:201`, `:293`, `:367`; assertions unchanged |
| `tests/fundamentals/test_risk_probe.py` | create | pure guards, rules, statuses, prior matching, explanation and section text |
| `tests/fundamentals/test_prep2b_traces.py` | modify | trace-digest characterization (Task 2); `run.days` (inclusive `D`, leap year, `CLOSING` role) and `run.outflow_pct` on stored traces |
| `tests/fundamentals/test_risk_probe_binding.py` | create (r5) | binding-boundary tests (q) lookup failures, (r) nested-source refusal with its isolation spy, (s) rework re-derivation; the helpers `trace_closure` and `check_probe` (PILOT-4's probe constants and assertions) |
| `tests/fundamentals/test_prep5_rework.py` | modify (r5) | `calls` fixture routes probe `conclude`/`put_calculation_trace` calls to `"probe"`/`"probe_put"`; `:643` `computed` excludes `probe.*` keys (P11) |
| `tests/fundamentals/test_pilot_e2e.py` | modify | PILOT-4: probe keys and routes, then `check_probe` (values, raw amounts, windows, stale, T, qualified `not_performed` line); PILOT-11 orphan check against `trace_closure` (r5) |
| `docs/evidence/phase-0.5/q0-thesis-successor-2.{md,yaml}` | create (Task 5) | successor thesis 1.2.0 with typed probe limits |
| `config/ledger_import.yaml` | modify (Task 5) | `thesis_successor` → successor-2 |

Scratch helpers (never committed) are listed in the Files blocks of Tasks 5 and 6.

Unchanged on purpose (r5): `test_prep2b_run_draft.py` (the new boundary tests moved out),
`test_prep5_corrected_filing.py` and `test_pilot_citations.py`. Their spy assertions keep their
text and meaning (P11).

Estimate (r5): about **475 production lines**: Task 1 ≈ 42, Task 2 ≈ 74 (including the `TRACES`
extraction), Task 3 ≈ 170, Task 4 ≈ 190 (including P2's window discovery). The recursive
`_OPERAND_BLOBS` reuses `TRACES`, so it adds no second recursion.

About **745 test lines**:
- Task 1 ≈ 100, including the five existing `map_q0` call sites;
- Task 2 ≈ 60;
- Task 3 ≈ 200;
- Task 4 ≈ 385: `test_risk_probe_binding.py` ≈ 310 for (q), (r), (s), `trace_closure` and
  `check_probe`; PILOT-4 and PILOT-11 edits ≈ 25; the `calls` fixture ≈ 10.

Expected sizes after the tests round, against the 800-line ceiling:
- `test_pilot_e2e.py` ≈ 700 (675 today);
- `test_prep5_rework.py` ≈ 750 (737);
- `test_ledger_import.py` ≈ 712 (705);
- `test_falsifier_status.py` ≈ 495 (400);
- `test_prep2b_traces.py` ≈ 330 (269);
- `test_risk_probe.py` ≈ 200 (new);
- `test_risk_probe_binding.py` ≈ 310 (new).

Scratch helpers for Tasks 5–6: ≈ 250 lines, not committed. Production stays below the spec's
600–900 because guards and rules are one table-driven pure function, and no new module wraps
the binder.

## Test-first order and the red proof (r2, Sol r1 #6)

`scripts/verify.sh gate RESEARCH-3-S1` needs a red proof (`scripts/verify.sh:343-395`). The red
run seals every acceptance file, plus each local module it imports, by SHA-256
(`:197-217`). The gate then fails `tests-untouched` if any of them changes. S1 adds behaviour, so
the refactor `baseline` route does not apply. The sequence is:
1. **Tests round (one Opus round, before any production change).** Write every test-contract
   change in its final form: every test named in Tasks 1–4, and every edit below, in the test
   files of the file map. Shared helpers (`tests/fundamentals/prep2b_support.py`, conftests) are
   changed in this round or not at all. Every file must still collect on the pre-change source,
   because one collection error interrupts the whole red session. A production name that does
   not exist yet (`KINDS`, `TRACES`, `risk_probe.*`) is imported inside the test, helper or
   fixture, never at module level. Each node then fails on its own. The round also does:
   - **Every changed caller (r5, Sol closing #1).** Run `git grep -n "map_q0(" -- src tests
     scripts`, plus the same grep for every other function whose signature this plan changes
     (`evaluate(`, `measurement_key(`, `_valued(`). Today the only test calls of `map_q0` are
     `test_falsifier_status.py:108, :196` and `test_ledger_import.py:201, :293, :367`. Each gets
     `metrics=KINDS`, imported inside the test, with its assertions unchanged. These five fail
     pre-change with `TypeError` (they are not red nodes) and pass after Task 1. `evaluate`'s
     new `stale` parameter and the `ValueKind` arm of `measurement_key`/`_valued` have defaults
     or widen a type, so their callers do not change. The round reports the grep output.
   - **The rework fixture and PILOT-11 (r5, P11, P12).** Make the `calls` routing and the `:643`
     filter in `test_prep5_rework.py`. Replace `cited` in PILOT-11's orphan check with
     `trace_closure(pilot, cited)`.
   - **Size check (r5, Sol closing #2).** Run `wc -l` on every changed or created test file. Each
     must be ≤ 800 lines (`scripts/verify.sh:455-474` routes an oversized changed test file to
     CONTRACT). If one is over, move its new helpers into `test_risk_probe_binding.py` before
     red capture.
2. **Characterization check.** On the pre-change source, `uv run pytest
   tests/fundamentals/test_prep2b_traces.py::test_trace_digests_are_unchanged -n 0` passes. It is
   not an acceptance node (the red proof requires every recorded node to fail).
3. **Red capture** on the pre-change source (`HEAD` = this plan's commit plus the tests), the
   orchestrator only:
   `scripts/verify.sh red RESEARCH-3-S1 tests/fundamentals/test_risk_probe.py
   tests/fundamentals/test_falsifier_status.py::test_a_probe_limit_imports_typed_by_its_suffix
   tests/fundamentals/test_falsifier_status.py::test_an_unknown_or_mismatched_probe_limit_refuses
   tests/fundamentals/test_falsifier_status.py::test_a_probe_measure_of_another_kind_refuses
   tests/fundamentals/test_falsifier_status.py::test_a_days_limit_weakens_on_breach
   tests/fundamentals/test_falsifier_status.py::test_a_stale_measure_is_not_assessed
   tests/fundamentals/test_prep2b_traces.py::test_probe_formulas_store_closing_and_outflow_traces
   tests/fundamentals/test_risk_probe_binding.py
   tests/fundamentals/test_pilot_e2e.py::test_pilot_end_to_end`.
   The whole of `test_risk_probe_binding.py` is a target: (q), (r) and (s) (r5). The red run
   also seals the unchanged modules the targets import (`test_prep5_rework.py`,
   `test_prep2b_run_draft.py`, the support modules), so the `calls` fixture edit is frozen too.
   It must report every node `FAILED` or `ERROR`, with none missing. A node that passes
   pre-change is vacuous: fix the test, then re-capture, still before production code.
4. **Implement** Tasks 1–4 without touching the sealed files.
5. **Reseal only if a contract is wrong.** If an implementer shows a sealed test is wrong, the
   orchestrator stops, has the test amended, and runs `scripts/verify.sh reseal RESEARCH-3-S1
   <proof-file>` with a proof file naming the amendment and showing the amended assertion
   failing against the implementation it was wrong about
   (`docs/graph-loops/v2-build-pipeline.md:243-250`). No other test edit is allowed.
6. **Gate:** `scripts/verify.sh gate RESEARCH-3-S1` → `ROUTE PASS`.

The node names above are binding; the tests round uses exactly these names.

## Tasks

### Task 1: Typed probe limits

Goal:
- A thesis twin's falsifier imports with a threshold typed by its metric-id suffix: `_pct` →
  `PERCENTAGE` `%`; `_days` → `DAYS`, unitless; `_ratio` → `RATIO`, unitless.
- Import refuses an unknown suffix, and a registered metric whose `METRICS` value kind is not
  its suffix's kind.
- `evaluate` raises `RunDraftError` when the measured claim's value kind is not the
  threshold's.
- A measured claim named stale is `NOT_ASSESSED` with "latest statement predates the period".
- The six probe metrics are registered.

Files:
- Modify: `src/fundamentals/verify/thesis_predicates.py`, `src/fundamentals/ledger/import_mapping.py`, `src/fundamentals/ledger/importer.py`, `src/fundamentals/ledger/falsifier_status.py`
- Test: `tests/fundamentals/test_falsifier_status.py`, `tests/fundamentals/test_ledger_import.py`
  (the existing `map_q0` calls only, r5)

Interfaces:
- Consumes: existing `PredicateOp`, `FalsifierRow`, `BoundThesis`, `LosslessError`, `ValueKind`, `PERCENT`.
- Produces:
  - `import_mapping.METRIC_KINDS: Mapping[str, tuple[ValueKind, str | None]]`, keyed by suffix
    (`"_pct"`, `"_days"`, `"_ratio"`).
  - `map_q0(md: bytes, twin: bytes, *, cutoff: date, metrics: Mapping[str, ValueKind]) ->
    MappedVersion`. `metrics` holds the registered metric kinds; every caller passes it.
  - `falsifier_status.METRICS: Mapping[str, tuple[str, str | None, ValueKind]]`, as (label,
    measuring claim key, value kind). The new entries:
    - `probe_receivable_days` → `probe.R1`, `DAYS`
    - `probe_inventory_materials_days` → `probe.R2`, `DAYS`
    - `probe_payable_materials_days` → `probe.R3`, `DAYS`
    - `probe_cash_conversion_pct` → `probe.R4`, `PERCENTAGE`
    - `probe_capex_intensity_pct` → `probe.R5`, `PERCENTAGE`
    - `probe_borrowings_to_equity_ratio` → `probe.R6`, `RATIO`
    - The existing five entries get `PERCENTAGE`.
  - `falsifier_status.KINDS: Mapping[str, ValueKind]`, metric → value kind, derived from
    `METRICS` in one line. It is what every `map_q0` caller passes (r5).
  - `falsifier_status.RISK_PROBE = "risk_probe"`, a member of `DERIVED`.
  - `falsifier_status.STALE = "latest statement predates the period"`.
  - `evaluate(bound, claims, lines, stale: frozenset[str] = frozenset()) ->
    tuple[FalsifierRow, ...]`. The new parameter holds the stale measuring claim keys.
  - `Disposition.NOT_ASSESSED`.

Approach:
- `_falsifier` looks up the suffix in `METRIC_KINDS` (`_require` on a miss) and builds the
  threshold with that kind and unit. Unitless thresholds have unit, currency and scale `None`.
- `map_q0` refuses when a falsifier's metric is in `metrics` with a kind other than its suffix's.
- `importer` passes `KINDS` at both `map_q0` calls (`importer.py:172, :218`). The tests pass it
  at their five calls (tests round).
- `evaluate` reads the kind from `METRICS`:
  - A stale key gives `NOT_ASSESSED` with `STALE`, before any value test.
  - A measured claim whose `value_kind` differs from the threshold claim's raises.
- `derived` needs no change: it already copies the threshold's kind and unit into the
  `THESIS_CLAIM`, and the `thesis_impact` count by status picks up `NOT_ASSESSED`.

Verification: `uv run pytest tests/fundamentals/test_falsifier_status.py tests/fundamentals/test_ledger_import.py -n 0` passes. The new cases (written in the tests round, sealed by the red proof):
- (a) `test_a_probe_limit_imports_typed_by_its_suffix`: `_days` limits on
  `probe_receivable_days`, `probe_inventory_materials_days` and `probe_payable_materials_days`
  import as `DAYS`, unitless; a `_ratio` limit imports as `RATIO`.
- (b)(c) `test_an_unknown_or_mismatched_probe_limit_refuses`, parametrized: an unknown suffix is
  refused; `map_q0` with `metrics=KINDS | {<a _days metric>: PERCENTAGE}` is refused (`KINDS`
  is built at import time, so the test passes the bad kind instead of patching `METRICS`, r5).
- (d) `test_a_probe_measure_of_another_kind_refuses`: with `METRICS` pointing a `_days` metric
  at a `PERCENTAGE` claim, `evaluate` raises `RunDraftError`.
- (e) `test_a_days_limit_weakens_on_breach`, parametrized over the three days metrics.
- (f) `test_a_stale_measure_is_not_assessed`: a stale key gives `NOT_ASSESSED` with `STALE`.

Dependencies: None.

Risks: low. The Q0 and successor-1 twins are all `_pct`, so their import is unchanged (the
existing import tests prove it).

### Task 2: Binder primitives for interpretation-read, unitless and closing-balance traces

Goal:
- The binder can read an operand straight from its single `MAPPED` interpretation under the
  run's pins, at an instant (`CLOSING`) or any duration key: `None` when there is none,
  `RunDraftError` when there are several.
- It computes and stores traces for `run.days` (a ÷ b × D, D the flow operand's inclusive days),
  `run.ratio` (a ÷ b), `run.ratio_pct` (existing `RATIO_PCT`) and `run.outflow_pct`
  (−a ÷ b × 100), plus child `run.sum` traces usable as operands.
- It builds unitless `DAYS`/`RATIO` keys and claims, and `FILED` raw-figure claims under
  `probe.R<n>.<canonical_id>` that resolve.
- Existing traces are byte-identical.

Files:
- Modify: `src/fundamentals/ledger/run_traces.py`, `src/fundamentals/ledger/import_mapping.py`, `src/fundamentals/ledger/citations.py`
- Test: `tests/fundamentals/test_prep2b_traces.py`

Interfaces:
- Consumes: `conclude`, `operand_from_result`, `TemporalRole.CLOSING`, `store_value`, `UNITS`, `UNITLESS`.
- Produces:
  - `measurement_key(canonical_id: str, unit: str | ValueKind, entity_id, start, end)` and
    `_valued(name, section, value, unit: str | ValueKind, key, source=None, *, precision,
    rounding)`. A `ValueKind` argument means a unitless claim of that kind: unit, currency and
    scale are all `None`.
  - `run_traces.DAYS = "run.days"`, `run_traces.RATIO = "run.ratio"`,
    `run_traces.OUTFLOW_PCT = "run.outflow_pct"`. `SUM` and `RATIO_PCT` are reused.
  - `_Binder.filed(source: Provenance, key: MeasurementKey, selection: SelectionSource) ->
    _Operand | None`. This is the single-interpretation lookup shared with `operand`, which
    keeps its run-value check.
  - `_Binder.evaluate(name: str, formula: str, output: MeasurementKey, operands:
    tuple[_Operand, _Operand]) -> CalculationResult`, the pure compute. Each operand's role is
    `CLOSING` when its key period is an instant, else `DURATION`. `_compute` calls it and keeps
    its run-value check and `pending`.
  - `_Binder.child(name, formula, output, operands) -> _Operand`. It evaluates, stores the trace
    and returns the operand with its `calculation_trace_id`.
  - `_Binder.store(name, result) -> int`, which stores a parent trace.
  - `citations._filed_key` accepts `probe.R<n>.<canonical_id>` but not `probe.R<n>.prior`.
  - `citations.TRACES: LiteralString`, the recursive `traces(id)` CTE taken out of `_INPUTS`
    unchanged (P12, r5). `_INPUTS` becomes `"WITH RECURSIVE " + TRACES + ", interps(id) AS
    ..."` with the same text as today.

Approach:
- Refactor `_compute` into `evaluate` plus the run-value check, so every existing trace keeps
  its content hash. The existing trace tests check values, citations and write counts, not
  trace content (`test_prep2b_traces.py:149-196,262-269`), so they cannot catch a changed hash
  (`canon/formula.py:149-152` hashes every field). The tests round therefore adds one
  characterization test, `test_trace_digests_are_unchanged`. It binds one quarter with
  `bind_computed` and asserts the sorted content digests of the traces it stores equal a
  literal tuple. That tuple is printed by running the test body once on the pre-change source,
  never typed by a model. It passes before and after the refactor and is not a red-proof node.
- Add the three formulas to `evaluate`. `run.days` reads D from operand b's key period.
- Instant keys are `key.model_copy(update={"period": PeriodInterval.at(day)})`, as `bind_computed`
  already builds prior keys.
- An undefined division still raises `RunDraftError`. The probe never reaches one, because its
  guards run first (Task 3).

Verification:
- `uv run pytest tests/fundamentals/test_prep2b_traces.py -n 0` passes, including
  `test_trace_digests_are_unchanged` (green on the pre-change source and after).
- `test_probe_formulas_store_closing_and_outflow_traces` (red-proof node), parametrized:
  - a stored `run.days` trace over a `CLOSING` instant and a 366-day leap-year window carries
    D = 366 inside its exact value and records the `CLOSING` role;
  - `run.outflow_pct` on a negative outflow is positive.
- `uv run mypy --strict src` is clean.

Test seams: `_Binder` over a test-DB evidence repository, as `test_prep2b_traces.py` already uses.

Dependencies: None.

Risks: characterization-first. A changed hash on any existing trace breaks the four live
approved versions' replay; `test_trace_digests_are_unchanged` is the guard.

### Task 3: Probe assessment and section text (pure)

Goal: given each check's operand values, window and balance date, any matching prior's values,
and the falsifier rows, the probe produces each row's status, reason, fired rules and named
falsifier ids. It also produces the section body (rows with balance date and flow window,
epistemic markers, the explanation and the non-evaluated sources). The body holds no digit
outside placeholders and structural dates. It must hold exactly as spec §2:
- **Guards, before rules.**
  - A missing operand → `NOT_ASSESSED` naming it.
  - Revenue or M ≤ 0 → `NOT_ASSESSED`.
  - A balance other than `total_equity`, or negated capex, < 0 → `NOT_ASSESSED`, "sign anomaly
    in filed line".
  - R4 profit ≤ 0 → `FLAGGED`, "non-positive profit". The ratio is not shown, and S is still
    evaluated.
  - R6 equity ≤ 0 → `FLAGGED`, "non-positive equity". The ratio is not shown.
- **S.** R4 is flagged when cfo < profit.
- **T.** It is evaluated only for a prior whose balance date is one year earlier (same
  month-day), whose window is in the same duration class with the same start month, and which
  uses its own D. It flags a strict move in the arrow's direction (R1 ↑, R2 ↑, R4 ↓, R6 ↑).
  Otherwise the reason is "trend not evaluable: no matching prior". A prior that fails a guard
  is also not evaluable.
- **L.** A `WEAKENED` falsifier flags the row and names the falsifier id.
- **Status, first match wins.** Guard; else a fired rule → `FLAGGED`; else an evaluated rule →
  `PASSED`; else `COMPUTED` ("no rule evaluable: no prior, no limit").
- **Stale.** Values render with a statement note, and the metric goes to `stale`.
- **No flow window.** `Statement.window` `None` → R1–R5 `NOT_ASSESSED`, "no half-year or annual
  flow window in the statement"; R6 is assessed (P2).
- **No balance sheet.** One paragraph: "NOT_ASSESSED: no filed balance sheet in the run's
  package".
- **No evaluable row (r3, Sol r2 #7; spec §1 rule 2).** A statement is selected but all six rows
  are `NOT_ASSESSED`: `body` renders one `{{e:computed}}` paragraph instead of the rows and the
  explanation: "NOT_ASSESSED: no check is evaluable on the statement of <balance date>", then
  each check id with its reason, in check order. Raw amounts are not shown.

Files:
- Create: `src/fundamentals/ledger/risk_probe.py` (assessment and rendering half)
- Test: `tests/fundamentals/test_risk_probe.py`

Interfaces:
- Consumes: `FalsifierRow`, `Disposition` (Task 1), `_slot`, `refs`, `PeriodInterval`.
- Produces:
  - `ProbeStatus(StrEnum)`: `NOT_ASSESSED`, `FLAGGED`, `PASSED`, `COMPUTED`.
  - `CHECKS: Mapping[str, Check]`, keyed by `"R1"` … `"R6"`. `Check` is a frozen model: `metric_id`,
    `label` (no digits), `formula`, the numerator and denominator canonical ids (M expands to
    its three ids), `arrow: int | None` (+1 ↑, −1 ↓, None), `category` (P6) and `meaning` (P7
    sentence).
  - `Statement` (frozen): `capture_sha256: str`, `balance_date: date`, `window: PeriodInterval |
    None` (P2),
    `stale: bool`, `values: Mapping[str, Decimal]`. The values are exact base-unit amounts of
    the operands found; an absent id is missing.
  - `guard(check_id: str, statement: Statement) -> tuple[ProbeStatus, str] | None`. It returns
    the guard outcome, or `None` when the ratio may be computed.
  - `matches(current: Statement, prior: Statement) -> bool`, the T criteria.
  - `ProbeRow` (frozen): `check_id`, `status: ProbeStatus`, `reason: str | None`,
    `rules: tuple[str, ...]` (fired), `falsifier_ids: tuple[str, ...]`, `shown: bool`,
    `prior_shown: bool`.
  - `assess(check_id: str, statement: Statement, value: Decimal | None, prior: Decimal | None,
    prior_note: str | None, falsifiers: Sequence[FalsifierRow]) -> ProbeRow`. `value` and
    `prior` are the stored claim values, `None` when not computed.
  - `body(statement: Statement | None, rows: Sequence[ProbeRow], claim_keys: Mapping[str,
    tuple[str, ...]]) -> str`. The `## risk_probe` body; `claim_keys` maps each check to the
    raw-figure keys it shows.

Approach:
- The tests come from the spec §5 S1 acceptance list and are written in the tests round
  (above). Build one table-driven module: no per-check classes, no strategy objects.
- Each row line carries its own `{{e:computed}}` marker. Raw amounts carry `{{e:observed}}`
  (and render `FILED_SUFFIX` through their claim). A limit carries `{{e:opinion}}`.
- The explanation paragraph is `{{e:computed}}`. It has one sentence per `FLAGGED` row (P7),
  then one closing sentence naming the categories that carry flags (P6) and the coverage gaps:
  the `NOT_ASSESSED` rows and the non-evaluated sources.
- The non-evaluated sources are a constant tuple, each rendered "NOT_ASSESSED: <source> not
  assessed by this probe" (P10): related parties, pledges, contingent liabilities, auditor
  opinion, capitalised intangibles, rating remarks, disclosure lapses.

Verification: `uv run pytest tests/fundamentals/test_risk_probe.py -n 0` passes. The whole file
is a red-proof target. One case per acceptance item, parametrized where cases share a shape:
- (a) R4 is `FLAGGED` by S when cfo < PAT;
- (b) R4 with a loss is `FLAGGED` ("non-positive profit"), and the ratio is not shown;
- (c) R6 with negative equity is `FLAGGED` ("non-positive equity"), not `NOT_ASSESSED`;
- (d) zero or negative revenue, and zero or negative M, give `NOT_ASSESSED`;
- (e) a missing operand gives `NOT_ASSESSED` naming its canonical id;
- (f) a negative receivable gives the sign anomaly;
- (g) `matches`: an annual against an annual one year earlier is true; a half-year against an
  annual prior is false; a prior with a different D (leap year) is true and its own value is
  used;
- (h) T flags in the arrow direction and passes against it;
- (i) a `WEAKENED` limit flags and names the falsifier id;
- (j) `COMPUTED` when there is no prior and no limit;
- (k) a stale statement renders its note;
- (l) every non-evaluated source is named with "not assessed by this probe";
- (m) `scan_section` on a rendered body (all statuses) returns no state;
- (n) a statement with no window: R1–R5 `NOT_ASSESSED` with the window reason, R6 assessed.

Test seams: `guard`, `matches`, `assess`, `body`. Pure, no I/O.

Dependencies: Task 1 (`Disposition.NOT_ASSESSED`, `FalsifierRow`).

Risks: test-first. This is the financial logic of the slice; a wrong comparison direction or
guard order is a wrong verdict in a reader-facing report.

### Task 4: Probe binding and run-draft wiring

Goal:
- Every run draft written by `fundamentals run` carries `risk_probe` after
  `observable_falsifiers`, built from the selected statement:
  - The run's own XBRL if it has a `MAPPED` balance-sheet instant at the run's period end.
  - Else the QoQ comparator's at the comparator's period end, stale.
  - Else none.
- For each guarded-in check there is a stored trace and a `probe.R<n>` claim; a raw `FIGURE`
  claim per operand; and `probe.R<n>.prior` when a matching prior from the package is found.
- Falsifiers on stale metrics are `NOT_ASSESSED`.
- On the retained pilot, every claim is `MATCH` and R1–R6 equal the hand-computed values.

Files:
- Modify: `src/fundamentals/ledger/risk_probe.py` (binding half), `src/fundamentals/ledger/run_draft.py`, `src/fundamentals/api/cli.py`
- Test: `tests/fundamentals/test_pilot_e2e.py`, `tests/fundamentals/test_prep5_rework.py` (r5,
  P11), create `tests/fundamentals/test_risk_probe_binding.py` (r5)

Interfaces:
- Consumes:
  - Task 2: `_Binder.filed`, `evaluate`, `child`, `store`; the formula constants; unitless
    `measurement_key`/`_valued`.
  - Task 3: `CHECKS`, `Statement`, `guard`, `matches`, `assess`, `body`.
  - Task 1: `evaluate(..., stale=)`, `RISK_PROBE`.
- Produces:
  - `Probe` (frozen): `statement: Statement | None`, `prior: Statement | None`,
    `claims: tuple[NumericClaim, ...]` (cited), `values: Mapping[str, Decimal]` and
    `priors: Mapping[str, Decimal]` (per check id), `notes: Mapping[str, str]` (guard or T
    reasons), `stale_keys: frozenset[str]`.
  - `bind_probe(repo: EvidenceRepository, update: EarningsUpdate, *, entity_id: int, versions:
    ConfigVersions, fiscal_year_end_month: int) -> Probe`. The CLI passes the entity's
    `FISCAL_YEAR_END_MONTH` setting (P2).
  - `probe_section(probe: Probe, rows: Sequence[FalsifierRow]) -> tuple[str, str]`, the
    `(RISK_PROBE, body)` pair.
  - `RunDraft.probe: Probe`.

Approach:
- **Candidates.** `bind_probe` collects the package's XBRL provenances: own, QoQ and YoY prior
  sources, from `update` (F-6).
- **Statement.** It reads the balance-sheet instants with `_Binder.filed`. It discovers the
  window from all eligible `MAPPED` periods of the run's measurement context (entity, basis,
  framework, currency, no dimensions) on the capture (P2), never from revenue alone, then
  reads each flow operand at that window. A missing operand is absent from `values`; only the
  checks that use it are affected.
- **Prior.** It finds the prior among the candidates by `matches`.
- **Per check.**
  - If `guard` passes, it builds the child sums and the parent trace and stores them. The claim
    value is the stored trace value at the rounding policy's scale for its kind (`RATIO` 6,
    `DAYS` and `PERCENTAGE` 2), half-even, shown at that precision, so L, T and the claim check
    read the same value (F-3; Sol closing review). A move or breach smaller than that scale can
    still be hidden or triggered at a rounding boundary, notably sub-0.01 for `DAYS` and
    `PERCENTAGE`; the rounding policy accepts this.
  - `guard` also refuses a denominator whose uncertainty interval reaches zero: `NOT_ASSESSED`
    for the current statement, an unevaluable T for a prior; nothing is stored for it. R4's
    current statement is the exception, because S compares two filed amounts and needs no
    quotient: S is evaluated as usual (`FLAGGED` or `PASSED`) and the raw figures are stored and
    cited, but no ratio is stored or shown, T and L are not evaluated, and the reason says so.
  - It builds the raw figure claims from the operands (value = interpretation value ÷ crore
    scale, `FILED`).
  - It does the same for the prior when one matches and the prior passes its own guard.
- **Fail closed.** No balance sheet → `Probe` with `statement=None`.
- **Raw figures are read once.** The raw `FIGURE` claims and the parent traces' top-level
  operands come from the `Statement` reads; a child sum receives its leaves as arguments to
  `_Binder.child`. Test (r) relies on this seam.
- **CLI.** It calls `bind_probe` right after `bind_computed` in `before_commit` and passes the
  result to `RunDraft`.
- **`write_run_draft`.**
  - It adds the probe claims before `by_key`.
  - It passes `probe.stale_keys` to `evaluate`.
  - It appends `probe_section(probe, rows)` after the falsifier sections and before
    `open_questions`.
  - `NOT_DONE`'s forensic line is qualified (P9).
- **Operand blobs.** `_OPERAND_BLOBS` becomes `"WITH RECURSIVE " + TRACES + ...`, with its
  operand join over every trace in the closure (F-7, P12). Child-sum operands are then package-
  and cutoff-checked. Its parameter becomes `%(traces)s`.
- **Output keys.** Every probe trace's output canonical id starts with `probe.` (P11).
- **Rework.** Nothing special: `risk_probe` is `DERIVED`, so a rework re-derives it like the
  falsifier sections (P11).
- **PILOT-4** in `test_pilot_e2e.py`:
  - The `want_keys` set gains each quarter's probe keys, and the route check accepts probe
    `CALCULATION` and `FILED` `FIGURE` routes.
  - New assertions, in `check_probe(pilot, version_ids)`. It lives in
    `test_risk_probe_binding.py` with its constants, so `test_pilot_e2e.py` stays well under 800
    lines (r5). PILOT-4 calls it:
    - R1–R6 and every raw amount equal literal constants. They are computed once by an
      independent scratch computation from the filed figures in `Fraction`, quantised half-even at
      the rounding policy's scale; the probe code is not used.
    - Each row shows its balance date and flow window.
    - FY26_Q3 shows FY26_Q2's statement and FY27_Q1 shows FY26_Q4's, both stale.
    - FY26_Q2 and FY26_Q4 carry `probe.R1/R2/R4/R6.prior`, and their T outcome equals the
      constants' direction.
    - Raw amounts are `FIGURE` on the interpretation of the selected capture, with `FILED`.
    - R5 is positive.
    - The `not_performed` section carries the qualified forensic line (P9).
    - Every claim is `MATCH`.
- **PILOT-11 (r5, Sol closing #3).** In `_pilot11_resume`, `assert retried["calculation_traces"]
  <= cited` becomes `<= trace_closure(pilot, cited)`. A child sum reached only through a parent
  operand then passes. A trace that no cited trace reaches still fails "an orphan trace". Its
  other assertions and `_pilot11_rework` are unchanged: `:533` reads `calls["conclude"]`, which
  no longer holds probe calls (P11).
- **Binding-boundary tests** in the new `test_risk_probe_binding.py` (r5, Sol closing #2;
  `test_prep2b_run_draft.py` is at 763 lines). It imports `dictionary`, `mapping_set` and `pilot`
  from `test_prep2b_run_draft`, and `submitted_q2`, `calls`, `_request_changes` and `_rerun` from
  `test_prep5_rework`, as existing modules do. On the `pilot` fixture's FY26_Q2
  run, patching only `_Binder._interpretations` (the store read) or `_Binder.filed`'s source:
  - (q) `test_probe_lookup_failures`, parametrized (Sol r1 #1, #7):
    - `revenue_from_operations` has no `MAPPED` interpretation at the half-year window (r3, Sol
      r2 note): the filter hides only that key's 2025-04-01..2025-09-30 interpretation. Its
      quarterly interpretation stays, so the mandatory run binder (`run_traces.py:172-187`) does
      not refuse first. → the draft is written; R1 and R5 are `NOT_ASSESSED` naming it; R2, R3,
      R4 and R6 carry claims, with the window still the half-year (proves P2 does not depend on
      revenue);
    - `cfo` has two `MAPPED` interpretations → `RunDraftError`, no version written;
    - no balance-sheet instant on the run's or the QoQ capture → the section is the single
      "no filed balance sheet" paragraph, and the rest of the draft is written;
    - every row unevaluable with a statement selected (r3, Sol r2 #7): hide every half-year
      interpretation on the run's capture (no window, so R1–R5 are `NOT_ASSESSED`) and the
      `total_equity` instant (R6 missing). The run binder reads only quarter keys
      (`run_traces.py:146-148`), and the receivables, inventories, payables and borrowings
      instants stay, so the run's own capture is still selected, not stale. → the section is
      exactly one paragraph: it names the balance date, the window reason for R1–R5 and
      `total_equity` for R6. There are no `probe.*` claims. The version persists with every other
      section and all its claims `MATCH`.
  - (r) `test_a_nested_probe_operand_outside_the_package_or_cutoff_refuses`, parametrized
    (Sol r1 #8; redesigned r3, Sol r2 #8). The offending blob reaches the draft only through a
    nested child-sum leaf:
    - **Interception.** Wrap `_Binder.child`. For R6's borrowings sum only, replace the
      `borrowings_current` leaf with `binder.filed(foreign, key)`, where `foreign` is another
      registered XBRL capture's provenance and `key` is that capture's period-end instant. Every
      raw `FIGURE` claim, including `probe.R6.borrowings_current`, and every top-level operand
      keeps its in-package capture: each comes from the `Statement` read, not from `child`'s
      arguments. Citations stay valid (`citations.py:260-261`), and `run.sum` checks no period
      (`run_traces.py:284-285`).
    - **Foreign captures by content, not id.** Resolve each `foreign` with
      `Repository.find_capture_ref(source_id, surface, sha)` (`evidence/repository.py:258`) from
      the pilot's pinned XBRL SHA for that quarter; never carry live-DB capture ids (Task 0's
      ids are live; the test fixture registers in a different order, Sol r3 #8).
    - **Cases.** (a) `foreign` = FY25_Q4: outside FY26_Q2's package, published
      before the cutoff → "captures not in the run's package". (b) `foreign` = FY26_Q4,
      admitted with `allowed_captures` patched to include it, its
      `Retrospective.published` time after the source cutoff (the pilot runs
      `--retrospective`, `prep2b_support.py:278-282`) → "captures past the source cutoff"
      (`run_draft.py:658-670`). The test first asserts these preconditions (the capture is
      registered, outside or admitted to the package, published before or after the cutoff), so
      a fixture gap fails loud.
    - **Isolation spy.** Wrap `run_draft._check_sources`. Before delegating, it records on the
      same cursor the direct citation SHAs (`run_draft.py:626-627`) and the result of the pre-change
      non-recursive query (copied as a test literal from `run_draft.py:143-147`) over the claims'
      trace ids. The test asserts the foreign SHA is in neither set, so today's check would let
      the draft through. It also asserts the real call raises the case's message and no report
      version persists.
    - Run kind: ordinary (`prior.rework` is `None`), so the binder's `blobs` never reach
      `allowed_captures` (`run_draft.py:643`).
  - (s) `test_a_selective_rework_rederives_the_probe_on_the_heads_traces` (r5, P11),
    parametrized over two rejections of FY26_Q2's submitted draft (`submitted_q2`): `fact.revenue`
    (run lines rerun) and the cables guidance claim (guidance only). The spies are installed
    after the head's run, by fixture order, as at `test_prep5_rework.py:490`. After the rework:
    - The head carries `probe.*` claims; this fails pre-change.
    - The successor's `probe.*` claims equal the head's, the same trace ids included
      (content-addressed reuse).
    - `sorted(calls["probe"])` equals the sorted `key_digest`s of the traces in
      `trace_closure(pilot, <head's probe trace ids>)`: each probe trace is computed exactly
      once.
    - `set(calls["probe_put"])` equals that closure.
    - `calls["conclude"]` and `calls["put_calculation_trace"]` are left to the existing PREP-5
      tests, which still assert the run-line guarantee.

Verification:
- `uv run pytest tests/fundamentals/test_pilot_e2e.py tests/fundamentals/test_risk_probe_binding.py tests/fundamentals/test_prep5_rework.py tests/fundamentals/test_prep5_corrected_filing.py tests/fundamentals/test_pilot_citations.py tests/fundamentals/test_prep2b_run_draft.py tests/fundamentals/test_falsifier_status.py tests/fundamentals/test_ledger_import.py -n 0`
  passes. This needs the compose postgres plus the retained originals.
- Then the full gate: `scripts/verify.sh gate RESEARCH-3-S1` → `ROUTE PASS`, against the red
  proof captured before Task 1 (see "Test-first order and the red proof").

Test seams: the pilot's four-quarter run on its own `eqos_test_*` database and the version it
writes.

Dependencies: Tasks 1, 2, 3.

Risks:
- Medium. The pilot's comparator interpretations must include the instants and the H/A
  contexts, as live's do (Task 0). If the pilot's do not, the fixture's comparator intake is the
  gap: fix it there, not around it.
- Rework: probe claims sit in a `DERIVED` section, so `rework.plan` neither carries nor needs
  atoms for them (F-8). Every run, rework included, re-derives them (P11); (s) proves it.

### Task 5: Successor thesis with probe limits (operational, orchestrator)

Goal: an approved thesis successor 1.2.0, imported into the live ledger as the head of the
FY26_Q2 `BOOTSTRAP_THESIS` chain. It keeps F1–F5 of 1.1.0 unchanged and adds one typed
falsifier per probe metric, each an opinion with a stated recipe.

Files (r2, Sol r1 #12):
- Create: `docs/evidence/phase-0.5/q0-thesis-successor-2.{md,yaml}` (Opus round writes, script
  fills thresholds); `scratchpad/research3-s1/q0_probe.py`, `thresholds.py` (orchestrator,
  never committed).
- Modify: `config/ledger_import.yaml` (orchestrator).
- Scratch outputs under `scratchpad/research3-s1/task5/`: `q0_probe.json`, `recipes.yaml`,
  `thresholds.json`, `counts/`, `digests/`, `logs/`.

Interfaces:
- Consumes: Tasks 1–4 at the phase-approved commit (`map_q0(..., metrics=)`, `METRICS`,
  `CHECKS`, `guard`, the formula constants); the pinned retrieval manifest `RM` and its
  `published_package` (`api/source_admission.py`); A1's `counts.py` and `digests.py`.
- Produces:
  - `q0_probe.py` → `q0_probe.json`: for each Q0-window statement (capture, balance date,
    window, publication time, acquisition time) and each check, the exact value and its value
    quantised at the claim precision, or the guard reason. Read-only, migrator role, asserts
    `current_database()`.
  - `recipes.yaml` (Opus round): per probe metric, `metric_id`, operator, direction rationale
    and a numeral-free recipe over named `q0_probe.json` values (below).
  - `thresholds.py` → `thresholds.json` and the threshold lexemes in the pair. It reconciles
    the pair against the recipes and exits non-zero on any difference.
  - Successor-2 pair: 1.1.0's F1–F5 unchanged plus six typed probe falsifiers.

Approach (the RESEARCH-1 Task 6 and Amendment A1 path):
1. **Inputs (Sol r1 #2).** The Q0-window statements are the hash-pinned filings in the retrieval
   manifest whose publication time is at or before the thesis cutoff 2025-11-06: FY26_Q2 H1
   (capture 1), FY25_Q2 H1 (capture 13) and FY25 annual (capture 15). This is the existing
   retrospective contract (`api/cli.py:572-590`; `run_draft.py:662-668` uses publication, not
   first-seen, under `--retrospective`). The originals were acquired in September 2026
   (`docs/plans/LIVE-RUN-1-prerequisites.md:51-63`); `q0_probe.json` records both times and
   the md repeats 1.1.0's retrospective disclosure. No later quarter is read.
2. **Observed values.** `q0_probe.py` computes R1–R6 on those statements with the Task 4 code
   (`CHECKS`, `guard`, the formulas), in `Decimal`, quantised as Task 4. Its output is the only
   source of observed numbers.
3. **Recipes, not numbers (Sol r1 #3).** A fresh Opus round reads `q0_probe.json` and writes
   `recipes.yaml` and the pair.
   - The model chooses only the metric, the operator, the direction and the recipe. A recipe is
     numeral-free: a base (one named observation, or the max or min of named observations)
     plus, optionally, a spread (the absolute difference of two named observations). It holds
     no numeric literal.
   - The falsifier itself is an opinion (`{{e:opinion}}`): the choice of recipe and direction.
     The threshold is a calculation from that recipe; the md states each recipe in words and
     marks its threshold "calculated by `thresholds.py`". S1 admits no chosen opinion
     constant. A limit that would need one is dropped from successor-2 and recorded for the
     owner.
   - The pair is a copy of 1.1.0 plus the new falsifiers, a reason paragraph citing this plan
     and spec §2 L, and `approved_by` Sol. Each threshold is the placeholder
     `{{threshold:<metric_id>}}` until step 4.
4. **Thresholds by code.** `thresholds.py` evaluates each recipe over `q0_probe.json` in
   `Decimal` and quantises at the threshold kind's precision (`config/rounding_policy/v1.yaml`:
   `DAYS` 2, `PERCENTAGE` 2, `RATIO` 6). It writes the exact lexemes into both files of the
   pair, then re-reads the pair, maps it with `map_q0(metrics=KINDS)`, and asserts each mapped
   threshold equals its recomputation. Any difference → exit non-zero, no review.
5. **Review.** A fresh Sol round reads the pair, `recipes.yaml`, `q0_probe.json` and
   `thresholds.json`, and judges recipes, directions and the reconciliation. On `APPROVE`,
   commit the pair: that commit is the evidence commit. Then replace the `thesis_successor`
   block in `config/ledger_import.yaml` with successor-2 (evidence commit, `decided_on`,
   ruling) and commit. A Sol change to a recipe goes back through steps 3–5; no threshold is
   ever edited by hand.
6. Rehearse on a restored copy (`db backup` → `db restore --database eqos_test_s1`, A1's form):
   - `ledger import --thesis-successor` → one line, `FY26_Q2 BOOTSTRAP_THESIS <id> APPROVED`;
   - counts deltas: one version, two decisions, two import sources, one validation, and the
     sections and claims of the mapped pair;
   - version 6 becomes `SUPERSEDED`;
   - `approved_thesis` binds the new version.
7. Live: `db check-live` → counts → digests (all prior versions) → `ledger import
   --thesis-successor --snapshot-root data/raw/snapshots/v1`. Then `db check-live`, counts
   (deltas equal the rehearsal's) and digests (prior versions unchanged).

Verification: `thresholds.py` exits 0 (reconciled); the import line shows `APPROVED`;
`db check-live` exits 0; deltas match the rehearsal's; every earlier sealed digest is unchanged.

Dependencies: Tasks 1–4 committed and Sol's phase-end `APPROVE`; the live code is that commit.

Risks: permanent and append-only. Failure branch as A1: stop, preserve output, counts and
digests; the orchestrator rules. Never re-run a partly committed import.

### Task 6: Regenerate the four live Apar drafts and close S1 (operational, orchestrator)

Goal:
- Live FY26_Q2, FY26_Q3, FY26_Q4 and FY27_Q1 each have a new `APPROVED` version carrying
  `risk_probe`, with the stale rows and T as Task 0 predicts and falsifiers against
  successor-2.
- Each is `AS_KNOWN` with every claim `MATCH`/`MATCH_UNTRUSTED`.
- Sol's `APPROVE` on each, through `ledger panel`, judges the explanation readable as analysis.

Files (r2, Sol r1 #12):
- Create: `scratchpad/research3-s1/probe_gate.py` (orchestrator, never committed). No repo
  file changes.
- Scratch outputs: the `OUT` tree below.

Interfaces:
- Consumes: successor-2 (Task 5) and its sealed digest `THESIS_S2` (recorded after Task 5's live import); the LIVE-RUN-1 per-quarter
  table (configs, `--compare-run` 1–4, `$CFGS`, `RM`); the existing locators `$LOC/<Q>.json`
  and intake store `$INTAKE` (inputs only, reused); A1's `counts.py`, `digests.py` and
  LIVE-RUN-1's `check_rehearsal.py`.
- Produces: per quarter `$OUT/out/<Q>.json`, `$OUT/out/<Q>.md`, `$OUT/out/<Q>-v<v>.md`,
  `$OUT/responses/<Q>.{md,task}`, `$OUT/verdicts/<Q>.json`, `$OUT/gate/<Q>.txt`
  (`probe_gate.py`: pass/fail per check and status labels only), `$OUT/counts/<n>.tsv`,
  `$OUT/logs/<step>-<Q>.log`; at close `$OUT/export/`. Four new `APPROVED` versions.

**Paths (Sol r1 #4).** A fresh S1 namespace; no output path is shared with LIVE-RUN-1 or between
rehearsal and live.
- `OUT=scratchpad/research3-s1/task6/$ENV`, `ENV` = `rehearsal` or `live`, holding `out/`,
  `responses/`, `verdicts/`, `gate/`, `counts/`, `logs/` and (at close) `export/`.
- Rehearsal: DB `eqos_test_s1_runs`, restored from a `db backup` taken after Task 5's live
  import. Roots are copies (`cp -a`) of the live roots under `$OUT/roots/{snap,intake,locators}`,
  so no rehearsal write lands in a live root.
- Live: `SNAP=data/raw/snapshots/v1`, `INTAKE=data/raw/source-intake/store`,
  `LOC=data/raw/source-intake/locators` (LIVE-RUN-1's; read as inputs).
- **Preflight, before the environment's first write** (read-only; any failure stops before
  any write):
  - `$OUT` does not exist; it is then created with `mkdir -m 700` and each subdirectory
    likewise. A write-and-delete probe file proves each is writable.
  - For each quarter, none of `$OUT/out/<Q>.json`, `$OUT/out/<Q>.md`, `$OUT/out/<Q>-v*.md`,
    `$OUT/responses/<Q>.md` or `$OUT/verdicts/<Q>.json` exists (the run's JSON write refuses
    to clobber only after the draft commits, `api/cli.py:730-747`,
    `api/artifact_writer.py:42-52`).
  - For each quarter, the reused inputs `$LOC/<Q>.json` and `$INTAKE` exist and are readable.

Approach: LIVE-RUN-1 Task 5 step R, per quarter in order FY26_Q2 → FY27_Q1, each approved
before the next, with the paths above in place of LIVE-RUN-1's.
1. Rehearsal first, for all four quarters. Record every exit code, printed id, counts delta,
   claim state and probe-gate result.
   - **Recovery rehearsal (Sol r1 #5).** After FY26_Q2's rehearsal draft is submitted, record
     `ledger decide REPORT_VERSION <v> REQUEST_CHANGES --claim probe.R1` (rehearsal DB only).
     An ordinary `run` must refuse (`rework.py:222-227`: a `DERIVED` claim is not reworkable).
     `run … --full-successor` (`run_draft.py:265-274`) must then write a new draft, which
     passes `ledger check` and the probe gate, and is taken through submit and panel, on the
     attempt-specific paths under Risks (`<Q>-r1`). Record
     its deltas; the remaining quarters continue from it.
2. Live, per quarter:
   - Reuse the quarter's existing locator `$LOC/<Q>.json`: no `stage`, as the LIVE-RUN-1
     rework mode does.
   - `fundamentals-operator run … --out-json $OUT/out/<Q>.json --out $OUT/out/<Q>.md` →
     `run_draft_written version=<v>`.
   - `ledger check` → all `MATCH`/`MATCH_UNTRUSTED`.
   - **Probe gate** (`probe_gate.py --version <v> --thesis-digest $THESIS_S2`, read-only, output to
     `$OUT/gate/<Q>.txt`). Every check must pass:
     - (a) the draft binds successor-2 by its sealed digest;
     - (b) the `risk_probe` section follows `observable_falsifiers`;
     - (c) the selected capture and staleness are as Task 0: FY26_Q2 own, FY26_Q3 ← FY26_Q2
       stale, FY26_Q4 own, FY27_Q1 ← FY26_Q4 stale;
     - (d) R1–R6 recomputed in `Decimal` from the version's own raw figure claims equal the
       probe claims;
     - (e) priors exist exactly on FY26_Q2 and FY26_Q4;
     - (f) each falsifier on a stale metric is `NOT_ASSESSED`;
     - (g) the statuses equal the rehearsal's.
   - `ledger submit` → `ledger export <v> --out $OUT/out/<Q>-v<v>.md` → a fresh Sol round on
     the export, with the A-04/B-02 brief plus: "judge whether the risk explanation reads as
     analysis a reader can act on; list every issue". The reply ends with the `EQOS-BINDING`
     line and is saved to `$OUT/responses/<Q>.md`; the verdict to `$OUT/verdicts/<Q>.json`.
   - `ledger panel <v> --verdict $OUT/verdicts/<Q>.json --response $OUT/responses/<Q>.md …` →
     `APPROVED`.
3. Close: `ledger export --stock APARINDS --out $OUT/export --status-notes`; post-run `db
   backup`; bead notes record every id, the backup set id and Sol's verdicts.

Verification: four new `APPROVED` versions; the probe gate passes on each; the recovery rehearsal
passed; `db check-live` exits 0 after every write step; counts deltas equal the rehearsal's
(the recovery steps excepted, which run only in rehearsal).

Dependencies: Task 5.

Risks:
- Permanent writes. Failure branch as LIVE-RUN-1 step R: stop at the first deviation; never
  re-run a write step that partly committed.
- A Sol `REQUEST_CHANGES` on readability goes to a fresh Opus round on the Task 3 templates,
  then a re-review. A code change re-enters the phase-end loop before any further live write.
- A rejected probe claim (Sol r1 #5): ordinary rework refuses it (`rework.py:222-227`). After
  diagnosis, any code fix verified and Sol-reviewed, the quarter is rerun with
  `--full-successor` (`run_draft.py:265-274`), the route the recovery rehearsal proved; new
  output paths pass the same preflight (r3, Sol r2 note). Attempt `<n>` (1 for the first
  recovery, in rehearsal and live alike) uses `$OUT/out/<Q>-r<n>.{json,md}`,
  `$OUT/out/<Q>-r<n>-v<v>.md` (export), `$OUT/responses/<Q>-r<n>.md`,
  `$OUT/verdicts/<Q>-r<n>.json`, `$OUT/gate/<Q>-r<n>.txt` and `$OUT/logs/<step>-<Q>-r<n>.log`.
  No attempt reuses another's path.

## Acceptance map (spec §5 S1)

| Acceptance case | Proven by |
|---|---|
| R1–R6 equal hand-computed values; balance date and flow window on each row | Task 4 PILOT-4 constants; Task 6 gate (d) |
| R5 positive for negative canonical capex | Task 2 `run.outflow_pct` case; Task 4 PILOT-4 |
| R4 `FLAGGED` by S; R4 loss `FLAGGED` "non-positive profit"; R6 negative equity `FLAGGED` "non-positive equity" | Task 3 (a)(b)(c) |
| Zero or negative revenue or M → `NOT_ASSESSED`; missing operand named | Task 3 (d)(e); Task 4 (q) at the binding boundary |
| Missing revenue leaves the other checks assessed; ambiguous interpretation → `RunDraftError`; no balance sheet, or a statement with no evaluable row → one paragraph (spec §1 rule 2) | Task 3 (n); Task 4 (q) |
| Child-sum operands are package- and cutoff-checked | Task 4 (r) |
| Selective rework keeps its run-line guarantees and re-derives the probe on the head's traces (r5) | existing PREP-5/PILOT-11 assertions (P11); Task 4 (s) |
| Existing traces keep their content hash | Task 2 `test_trace_digests_are_unchanged` |
| T on Q4 evaluated and flags in the arrow direction; half-year vs annual not evaluable; different D uses its own D | Task 3 (g)(h); Task 4 PILOT-4 T on FY26_Q4 (and FY26_Q2, T0-2) |
| L: `_days` limit on R1 flags on breach | Task 1 (e); Task 3 (i) |
| Registered `_days` metric with `PERCENTAGE` kind refused at import | Task 1 (c) |
| `_days` limit whose `METRICS` entry points at a `PERCENTAGE` claim → `RunDraftError` | Task 1 (d) |
| Unknown suffix refused | Task 1 (b) |
| R2/R3 limits import as `DAYS` and flag on breach | Task 1 (a)(e) |
| Stale: Q3 shows FY26_Q2 values; its falsifier `NOT_ASSESSED` | Task 1 (f); Task 3 (k); Task 4 PILOT-4; Task 6 gate (c)(f) |
| `COMPUTED` with no prior and no limit; non-evaluated sources named | Task 3 (j)(l) |
| Limit thresholds are calculated, not model-written | Task 5 `thresholds.py` reconciliation; Sol review |
| Raw amounts cite their filed facts | Task 4 PILOT-4 routes; all `MATCH` |
| Regenerated Apar reports show the table and explanation; Sol `APPROVE` judges it readable | Task 6 |

## Verification summary

- `uv run ruff check src tests/fundamentals` and `uv run ruff format --check src tests/fundamentals`
- `uv run mypy --strict src`
- `uv run pytest tests/fundamentals` (compose postgres plus retained originals; the pilot e2e is
  the acceptance test)
- Before Task 1: the tests round, then `scripts/verify.sh red RESEARCH-3-S1 <nodes>` on the
  pre-change source, every node red (nodes listed under "Test-first order and the red proof")
- `scripts/verify.sh gate RESEARCH-3-S1` → `ROUTE PASS`
- `wc -l` of every changed test file ≤ 800 (tests round, r5)
- `git status` shows only the files in the file map.

## Self-review

- **Spec coverage.** Every item in §5 S1 "Work" maps to a task:
  - binder keys, interpretation-read values and `CLOSING` → Task 2;
  - unitless claims → Task 2;
  - the four formulas → Task 2;
  - three-operand M → Tasks 2 and 4;
  - guards, rules, staleness and statuses → Task 3;
  - raw `FIGURE` lines and `_filed_key` → Tasks 2 and 4;
  - typed `_falsifier` and `METRICS` → Task 1;
  - the template explanation → Task 3;
  - the successor thesis → Task 5.
  Every acceptance case is in the map above. Spec §1 rule 3 (order after
  `observable_falsifiers`, joins `DERIVED`) → Tasks 1 and 4.
- **Placeholders.** None. The successor's thresholds are deliberately not in this plan: Opus
  proposes numeral-free recipes, `thresholds.py` calculates the thresholds, and Sol reviews
  (Task 5). As in RESEARCH-1 Task 6, no number comes from a model.
- **Name/type consistency.** `METRICS` (3-tuple), `RISK_PROBE`, `STALE`, `evaluate(stale=)`,
  `Disposition.NOT_ASSESSED`, `_Binder.filed/evaluate/child/store`, `CHECKS`, `Statement`,
  `guard`, `matches`, `assess`, `body`, `Probe`, `bind_probe`, `probe_section`,
  `RunDraft.probe`, `KINDS`, `TRACES`, `trace_closure` and `check_probe` are each produced once
  and consumed by name.
- **What has nobody named?**
  - Child-sum operand blobs escaping the package and cutoff check → Task 4 (recursive
    `_OPERAND_BLOBS`).
  - FY26_Q2 trend evaluability, contrary to the spec text → T0-2, implemented as the rule says.
  - R6's numerator sum → P3.
  - Ambiguous interpretation at run time → P4.
  - The successor import chaining onto 1.1.0 → F-10; no code needed.
  - `not_performed` wording → P9, qualified.
  - Window discovery when revenue is missing → P2, Task 4 (q).
  - Recovering a rejected probe claim → Task 6, `--full-successor`, rehearsed.
  - Fresh output paths for the live writes → Task 6 preflight.
  - The probe in a selective rework → P11, re-derived; the spies count it apart.
  - Child sums under PILOT-11's orphan check → P12, `trace_closure`.
  - `rework.plan` refuses a rejected probe claim naming its route (diagnose, then
    `--full-successor`); a rejected thesis threshold keeps "supersede the thesis" (Sol closing
    review).
  - The status dashboard (`docs/status/dashboard.html`) is refreshed by the orchestrator after
    each committed task (routine, not a plan task).
  - Docs: none. The spec and this plan are the record.
