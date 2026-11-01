# RESEARCH-3 S1 — Risk probe with explanation and typed limits — Implementation Plan

**Origin:** `docs/specs/2026-10-27-research-3-thesis-analysis.md` §5 "S1" (approved r4,
gpt-6.1-sol `APPROVE`), with §0–§2, §6 and the owner rulings (OD-2: raw filed amounts beside the
ratios; invariant 7 extension). Bead `eqos-bnx`, slice 3 → S1. LIVE-RUN-1 (`eqos-dna`) is done:
the four live Apar run drafts FY26_Q2..FY27_Q1 are `APPROVED` (versions 8, 10, 11, 12), so live
regeneration is not blocked.
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
- **P2, flow window.** On the selected capture, the flow window is the longest `MAPPED`
  `revenue_from_operations` duration ending at the balance date. That is the half-year or annual
  window on Apar; it needs no fiscal-calendar config. `D` is that window's inclusive day count,
  taken from the flow operand's key period inside `run.days`.
- **P3, child sums.**
  - M is `run.sum(run.sum(cost_of_materials_consumed, purchases_of_stock_in_trade),
    changes_in_inventories)`: two child traces, as the spec says.
  - R6's numerator `borrowings_current + borrowings_noncurrent` is also a child `run.sum`, which
    the spec implies but does not name.
  - Child traces are stored as soon as they are computed (F-2). A later refusal leaves an
    unreferenced, content-addressed trace, which is harmless.
- **P4, missing versus ambiguous at run time.** Zero `MAPPED` interpretations of an operand →
  the row is `NOT_ASSESSED`, naming the canonical id. More than one → `RunDraftError` (a store
  fault, as `_Binder.operand` treats it today; Task 0 shows none on Apar).
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
- **P7, one sentence per flagged row.** A row whose rules fire carries one sentence. Its rule
  phrase is chosen by the first fired rule in the order guard, S, L, T, and its business
  meaning by the check. Six check meanings and four rule phrases replace a 6 × 4 sentence table.
- **P8, adverse cases are pure unit tests.** The spec suggests synthetic test-DB interpretations
  for the adverse cases (loss, negative equity, cfo below PAT, zero denominator, sign anomaly,
  mismatched priors). The guards, rules and statuses are a pure function of operand values and
  windows (Task 3), so they are tested without a database. The database path (traces, unitless
  claims, raw figures, `MATCH`) is proven on the retained pilot (Task 4). This is cheaper and
  covers the same logic (`.claude/rules/python/testing.md`).
- **P9, `not_performed` unchanged.** Its "- forensic checks" line stays. The probe is a ratio
  screen, and it names every forensic source it does not assess.

## File map

| File | Change | Responsibility |
|---|---|---|
| `src/fundamentals/verify/thesis_predicates.py` | modify | `Disposition.NOT_ASSESSED` (P5) |
| `src/fundamentals/ledger/import_mapping.py` | modify | typed `_falsifier` (`METRIC_KINDS`), the `map_q0` registered-kind check, unitless `measurement_key`/`_valued` |
| `src/fundamentals/ledger/importer.py` | modify | pass the registered metric kinds to `map_q0` |
| `src/fundamentals/ledger/falsifier_status.py` | modify | typed `METRICS` plus the six probe metrics, `RISK_PROBE` in `DERIVED`, value-kind check, stale → `NOT_ASSESSED` |
| `src/fundamentals/ledger/run_traces.py` | modify | `_Binder`: interpretation-read operands, closing and window keys, `CLOSING` role, formulas `run.days`/`run.ratio`/`run.outflow_pct`, child sums |
| `src/fundamentals/ledger/citations.py` | modify | `_filed_key` admits `probe.R<n>.<canonical_id>` |
| `src/fundamentals/ledger/risk_probe.py` | create | the probe: check table, guards, rules S/T/L, statuses, statement selection and prior matching, binding to traces and claims, section body, explanation, non-evaluated sources |
| `src/fundamentals/ledger/run_draft.py` | modify | `RunDraft.probe`, probe claims in the version, stale keys into `evaluate`, `risk_probe` section after `observable_falsifiers`, recursive `_OPERAND_BLOBS` |
| `src/fundamentals/api/cli.py` | modify | call `bind_probe` in `before_commit` after `bind_computed` and pass it to `RunDraft` |
| `tests/fundamentals/test_falsifier_status.py` | modify | typed-limit import refusals, `DAYS` limits flag on breach, evaluator kind mismatch, stale `NOT_ASSESSED` |
| `tests/fundamentals/test_risk_probe.py` | create | pure guards, rules, statuses, prior matching, explanation and section text |
| `tests/fundamentals/test_prep2b_traces.py` | modify | `run.days` (inclusive `D`, leap year), `run.outflow_pct` and `CLOSING` role on a stored trace, if the pure tests cannot reach them |
| `tests/fundamentals/test_pilot_e2e.py` | modify | PILOT-4: probe keys, R1–R6 values, raw amounts cite filed facts, windows, stale, T on FY26_Q2 and FY26_Q4 |
| `docs/evidence/phase-0.5/q0-thesis-successor-2.{md,yaml}` | create (Task 5) | successor thesis 1.2.0 with typed probe limits |
| `config/ledger_import.yaml` | modify (Task 5) | `thesis_successor` → successor-2 |

Estimate: about **450 production lines** (Task 1 ≈ 40, Task 2 ≈ 70, Task 3 ≈ 170, Task 4 ≈ 170)
and **≈ 400 test lines**. That is below the spec's 600–900 because guards and rules are one
table-driven pure function, and no new module wraps the binder.

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
- Test: `tests/fundamentals/test_falsifier_status.py`

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
  - `falsifier_status.RISK_PROBE = "risk_probe"`, a member of `DERIVED`.
  - `falsifier_status.STALE = "latest statement predates the period"`.
  - `evaluate(bound, claims, lines, stale: frozenset[str] = frozenset()) ->
    tuple[FalsifierRow, ...]`. The new parameter holds the stale measuring claim keys.
  - `Disposition.NOT_ASSESSED`.

Approach:
- `_falsifier` looks up the suffix in `METRIC_KINDS` (`_require` on a miss) and builds the
  threshold with that kind and unit. Unitless thresholds have unit, currency and scale `None`.
- `map_q0` refuses when a falsifier's metric is in `metrics` with a kind other than its suffix's.
- `importer` passes the kinds from `METRICS` at both `map_q0` calls.
- `evaluate` reads the kind from `METRICS`:
  - A stale key gives `NOT_ASSESSED` with `STALE`, before any value test.
  - A measured claim whose `value_kind` differs from the threshold claim's raises.
- `derived` needs no change: it already copies the threshold's kind and unit into the
  `THESIS_CLAIM`, and the `thesis_impact` count by status picks up `NOT_ASSESSED`.

Verification: `uv run pytest tests/fundamentals/test_falsifier_status.py tests/fundamentals/test_ledger_import.py -n 0` passes. The new cases are:
- (a) `_days` limits on `probe_receivable_days`, `probe_inventory_materials_days` and
  `probe_payable_materials_days` import as `DAYS`, unitless.
- (b) an unknown suffix is refused;
- (c) with `METRICS` patched so a `_days` metric is `PERCENTAGE`, import is refused;
- (d) with `METRICS` pointing a `_days` metric at a `PERCENTAGE` claim, `evaluate` raises
  `RunDraftError`;
- (e) a `_days` limit flags `WEAKENED` on breach, for each of the three days metrics;
- (f) a stale key gives `NOT_ASSESSED` with `STALE`.

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

Approach:
- Refactor `_compute` into `evaluate` plus the run-value check, so every existing trace keeps
  its content hash. That makes this characterization-first: `test_prep2b_traces.py` and the
  pilot must stay green before any new formula lands.
- Add the three formulas to `evaluate`. `run.days` reads D from operand b's key period.
- Instant keys are `key.model_copy(update={"period": PeriodInterval.at(day)})`, as `bind_computed`
  already builds prior keys.
- An undefined division still raises `RunDraftError`. The probe never reaches one, because its
  guards run first (Task 3).

Verification:
- `uv run pytest tests/fundamentals/test_prep2b_traces.py -n 0` passes unchanged.
- One added case: a stored `run.days` trace over a `CLOSING` instant and a 366-day leap-year
  window carries D = 366 inside its exact value and records the `CLOSING` role.
- One added case: `run.outflow_pct` on a negative outflow is positive.
- `uv run mypy --strict src` is clean.

Test seams: `_Binder` over a test-DB evidence repository, as `test_prep2b_traces.py` already uses.

Dependencies: None.

Risks: characterization-first. A changed hash on any existing trace breaks the four live
approved versions' replay; the existing trace tests are the guard.

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
- **No balance sheet.** One paragraph: "NOT_ASSESSED: no filed balance sheet in the run's
  package".

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
  - `Statement` (frozen): `capture_sha256: str`, `balance_date: date`, `window: PeriodInterval`,
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
- Write the tests first, from the spec §5 S1 acceptance list. Then build one table-driven
  module: no per-check classes, no strategy objects.
- Each row line carries its own `{{e:computed}}` marker. Raw amounts carry `{{e:observed}}`
  (and render `FILED_SUFFIX` through their claim). A limit carries `{{e:opinion}}`.
- The explanation paragraph is `{{e:computed}}`. It has one sentence per `FLAGGED` row (P7),
  then one closing sentence naming the categories that carry flags (P6) and the coverage gaps:
  the `NOT_ASSESSED` rows and the non-evaluated sources.
- The non-evaluated sources are a constant tuple, each rendered "NOT_ASSESSED: <source> not in
  the run's package": related parties, pledges, contingent liabilities, auditor opinion,
  capitalised intangibles, rating remarks, disclosure lapses.

Verification: `uv run pytest tests/fundamentals/test_risk_probe.py -n 0` passes. One case per
acceptance item:
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
- (l) every non-evaluated source is named;
- (m) `scan_section` on a rendered body (all statuses) returns no state.

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
- Test: `tests/fundamentals/test_pilot_e2e.py`

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
    ConfigVersions) -> Probe`.
  - `probe_section(probe: Probe, rows: Sequence[FalsifierRow]) -> tuple[str, str]`, the
    `(RISK_PROBE, body)` pair.
  - `RunDraft.probe: Probe`.

Approach:
- **Candidates.** `bind_probe` collects the package's XBRL provenances: own, QoQ and YoY prior
  sources, from `update` (F-6).
- **Statement.** It reads each needed operand with `_Binder.filed` under the window or instant
  keys (P2).
- **Prior.** It finds the prior among the candidates by `matches`.
- **Per check.**
  - If `guard` passes, it builds the child sums and the parent trace and stores them. The claim
    value is the stored trace value at precision 2, half-even, so the claim check's rounding
    agrees (F-3).
  - It builds the raw figure claims from the operands (value = interpretation value ÷ crore
    scale, `FILED`).
  - It does the same for the prior when one matches and the prior passes its own guard.
- **Fail closed.** No balance sheet → `Probe` with `statement=None`.
- **CLI.** It calls `bind_probe` right after `bind_computed` in `before_commit` and passes the
  result to `RunDraft`.
- **`write_run_draft`.**
  - It adds the probe claims before `by_key`.
  - It passes `probe.stale_keys` to `evaluate`.
  - It appends `probe_section(probe, rows)` after the falsifier sections and before
    `open_questions`.
- **Operand blobs.** `_OPERAND_BLOBS` becomes recursive over `operand_trace_id`, in the
  `_INPUTS` form (F-7), so child-sum operands are package- and cutoff-checked.
- **PILOT-4** in `test_pilot_e2e.py`:
  - The `want_keys` set gains each quarter's probe keys, and the route check accepts probe
    `CALCULATION` and `FILED` `FIGURE` routes.
  - New assertions:
    - R1–R6 and every raw amount equal literal constants. They are computed once by an
      independent scratch computation from the filed figures in `Fraction`, quantised at 2,
      half-even; the probe code is not used.
    - Each row shows its balance date and flow window.
    - FY26_Q3 shows FY26_Q2's statement and FY27_Q1 shows FY26_Q4's, both stale.
    - FY26_Q2 and FY26_Q4 carry `probe.R1/R2/R4/R6.prior`, and their T outcome equals the
      constants' direction.
    - Raw amounts are `FIGURE` on the interpretation of the selected capture, with `FILED`.
    - R5 is positive.
    - Every claim is `MATCH`.

Verification:
- `uv run pytest tests/fundamentals/test_pilot_e2e.py tests/fundamentals/test_prep2b_run_draft.py tests/fundamentals/test_falsifier_status.py -n 0`
  passes. This needs the compose postgres plus the retained originals.
- Then the full gate: `scripts/verify.sh gate RESEARCH-3-S1`.

Test seams: the pilot's four-quarter run on its own `eqos_test_*` database and the version it
writes.

Dependencies: Tasks 1, 2, 3.

Risks:
- Medium. The pilot's comparator interpretations must include the instants and the H/A
  contexts, as live's do (Task 0). If the pilot's do not, the fixture's comparator intake is the
  gap: fix it there, not around it.
- Rework: probe claims sit in a `DERIVED` section, so `rework.plan` neither carries nor needs
  atoms for them (F-8).

### Task 5: Successor thesis with probe limits (operational, orchestrator)

Goal: an approved thesis successor 1.2.0, imported into the live ledger as the head of the
FY26_Q2 `BOOTSTRAP_THESIS` chain. It keeps F1–F5 of 1.1.0 unchanged and adds one typed
falsifier per probe metric, each an opinion with a stated recipe.

Approach (the RESEARCH-1 Task 6 and Amendment A1 path):
1. A read-only scratchpad script computes R1–R6 from the Q0-window statements only: those first
   seen by the thesis cutoff 2025-11-06, i.e. FY26_Q2 H1, FY25_Q2 H1 and FY25 annual. It uses
   the same formulas, `Decimal` and quantisation as Task 4. No later quarter is read. The
   numbers come only from this script.
2. A fresh Opus round proposes one limit per probe metric (`metric_id`, operator, threshold,
   recipe). Each is stated as an opinion against the script output. The round writes
   `docs/evidence/phase-0.5/q0-thesis-successor-2.{md,yaml}`:
   - a copy of 1.1.0 plus the new falsifiers;
   - a reason paragraph citing this plan and spec §2 L;
   - `approved_by` Sol.
   The pair must map losslessly (`map_q0` with the registered kinds).
3. A fresh Sol review reads the pair with the script output and judges recipes, directions and
   thresholds. On `APPROVE`, commit the pair: that commit is the evidence commit. Then replace
   the `thesis_successor` block in `config/ledger_import.yaml` with successor-2 (evidence
   commit, `decided_on`, ruling) and commit.
4. Rehearse on a restored copy (`db backup` → `db restore --database eqos_test_s1`, A1's form):
   - `ledger import --thesis-successor` → one line, `FY26_Q2 BOOTSTRAP_THESIS <id> APPROVED`;
   - counts deltas: one version, two decisions, two import sources, one validation, and the
     sections and claims of the mapped pair;
   - version 6 becomes `SUPERSEDED`;
   - `approved_thesis` binds the new version.
5. Live: `db check-live` → counts → digests (all prior versions) → `ledger import
   --thesis-successor --snapshot-root data/raw/snapshots/v1`. Then `db check-live`, counts
   (deltas equal the rehearsal's) and digests (prior versions unchanged).

Verification: the import line shows `APPROVED`; `db check-live` exits 0; deltas match the
rehearsal's; every earlier sealed digest is unchanged.

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

Approach: LIVE-RUN-1 Task 5 step R, per quarter in order FY26_Q2 → FY27_Q1, each approved
before the next. Values are from the LIVE-RUN-1 table: configs, `--compare-run` 1–4, `$CFGS`,
the live roots.
1. Rehearsal first, on a restored copy, for all four quarters. Record every exit code, printed
   id, counts delta, claim state and probe-gate result.
2. Live, per quarter:
   - Reuse the quarter's existing locator `$LOC/<Q>.json`: no `stage`, as the LIVE-RUN-1
     rework mode does.
   - `fundamentals-operator run …` → `run_draft_written version=<v>`.
   - `ledger check` → all `MATCH`/`MATCH_UNTRUSTED`.
   - **Probe gate** (read-only scratch helper; prints pass/fail and status labels only). Every
     check must pass:
     - (a) the draft binds successor-2 by its sealed digest;
     - (b) the `risk_probe` section follows `observable_falsifiers`;
     - (c) the selected capture and staleness are as Task 0: FY26_Q2 own, FY26_Q3 ← FY26_Q2
       stale, FY26_Q4 own, FY27_Q1 ← FY26_Q4 stale;
     - (d) R1–R6 recomputed in `Decimal` from the version's own raw figure claims equal the
       probe claims;
     - (e) priors exist exactly on FY26_Q2 and FY26_Q4;
     - (f) each falsifier on a stale metric is `NOT_ASSESSED`;
     - (g) the statuses equal the rehearsal's.
   - `ledger submit` → `ledger export` → a fresh Sol round on the export, with the A-04/B-02
     brief plus: "judge whether the risk explanation reads as analysis a reader can act on; list
     every issue". The reply ends with the `EQOS-BINDING` line.
   - `ledger panel` → `APPROVED`.
3. Close: `ledger export --stock APARINDS --status-notes`; post-run `db backup`; bead notes
   record every id, the backup set id and Sol's verdicts.

Verification: four new `APPROVED` versions; the probe gate passes on each; `db check-live` exits
0 after every write step; counts deltas equal the rehearsal's.

Dependencies: Task 5.

Risks:
- Permanent writes.
- A Sol `REQUEST_CHANGES` on readability goes to a fresh Opus round on the Task 3 templates,
  then a re-review. A code change re-enters the phase-end loop before any further live write.
  A claim rejection goes through the normal rework; probe claims are re-derived, not carried.

## Acceptance map (spec §5 S1)

| Acceptance case | Proven by |
|---|---|
| R1–R6 equal hand-computed values; balance date and flow window on each row | Task 4 PILOT-4 constants; Task 6 gate (d) |
| R5 positive for negative canonical capex | Task 2 `run.outflow_pct` case; Task 4 PILOT-4 |
| R4 `FLAGGED` by S; R4 loss `FLAGGED` "non-positive profit"; R6 negative equity `FLAGGED` "non-positive equity" | Task 3 (a)(b)(c) |
| Zero or negative revenue or M → `NOT_ASSESSED`; missing operand named | Task 3 (d)(e) |
| T on Q4 evaluated and flags in the arrow direction; half-year vs annual not evaluable; different D uses its own D | Task 3 (g)(h); Task 4 PILOT-4 T on FY26_Q4 (and FY26_Q2, T0-2) |
| L: `_days` limit on R1 flags on breach | Task 1 (e); Task 3 (i) |
| Registered `_days` metric with `PERCENTAGE` kind refused at import | Task 1 (c) |
| `_days` limit whose `METRICS` entry points at a `PERCENTAGE` claim → `RunDraftError` | Task 1 (d) |
| Unknown suffix refused | Task 1 (b) |
| R2/R3 limits import as `DAYS` and flag on breach | Task 1 (a)(e) |
| Stale: Q3 shows FY26_Q2 values; its falsifier `NOT_ASSESSED` | Task 1 (f); Task 3 (k); Task 4 PILOT-4; Task 6 gate (c)(f) |
| `COMPUTED` with no prior and no limit; non-evaluated sources named | Task 3 (j)(l) |
| Raw amounts cite their filed facts | Task 4 PILOT-4 routes; all `MATCH` |
| Regenerated Apar reports show the table and explanation; Sol `APPROVE` judges it readable | Task 6 |

## Verification summary

- `uv run ruff check src tests/fundamentals` and `uv run ruff format --check src tests/fundamentals`
- `uv run mypy --strict src`
- `uv run pytest tests/fundamentals` (compose postgres plus retained originals; the pilot e2e is
  the acceptance test)
- `scripts/verify.sh gate RESEARCH-3-S1`
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
- **Placeholders.** None. The successor's thresholds are deliberately not in this plan:
  Task 5's script and Sol decide them, as in RESEARCH-1 Task 6.
- **Name/type consistency.** `METRICS` (3-tuple), `RISK_PROBE`, `STALE`, `evaluate(stale=)`,
  `Disposition.NOT_ASSESSED`, `_Binder.filed/evaluate/child/store`, `CHECKS`, `Statement`,
  `guard`, `matches`, `assess`, `body`, `Probe`, `bind_probe`, `probe_section` and
  `RunDraft.probe` are each produced once and consumed by name.
- **What has nobody named?**
  - Child-sum operand blobs escaping the package and cutoff check → Task 4 (recursive
    `_OPERAND_BLOBS`).
  - FY26_Q2 trend evaluability, contrary to the spec text → T0-2, implemented as the rule says.
  - R6's numerator sum → P3.
  - Ambiguous interpretation at run time → P4.
  - The successor import chaining onto 1.1.0 → F-10; no code needed.
  - `not_performed` wording → P9, unchanged.
  - `rework.plan`'s refusal message for a rejected derived claim says "re-derived from the
    approved thesis", which is inaccurate for a probe claim. NOTICED BUT NOT TOUCHING: wording
    only; the refusal itself is right.
  - The status dashboard (`docs/status/dashboard.html`) is refreshed by the orchestrator after
    each committed task (routine, not a plan task).
  - Docs: none. The spec and this plan are the record.
