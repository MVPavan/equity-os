# RESEARCH-1 — Deterministic falsifier status in every run draft — Implementation Plan

**Origin:** bead eqos-bnx, recommended slice (1), with the owner's OK on slices 1→2→3 recorded
2026-10-23 in the bead notes. Binding gap: eqos-4j2.26. Register A-04 and B-02 (sections 6/7
in every update). No separate spec: this plan records the assumptions and design decisions
D1–D8 for Sol's plan review. Revisions r2 and r3 answer Sol's r1 and r2 findings (tables at the
end).
**Goal:** every Apar run-draft ledger version (FY26_Q3, FY26_Q4 and FY27_Q1 updates, plus the
FY26_Q2 bootstrap-period run as the baseline check) carries a `thesis_impact` section and an
`observable_falsifiers` section. For each falsifier of the thesis version that was `APPROVED`
at the run's derivation cutoff, they show what is tested (a short label), the measured traced
claim, the operator, the threshold as a claim citing that thesis version, and a code-computed
status (`WEAKENED` / `HELD` / `UNRESOLVED`). The draft must still validate `AS_KNOWN` with every
claim `MATCH`.
**Out of scope:**
- Narrative thesis impact, drivers, open questions, memory draft (slice 3).
- Segment lines (slice 2; eqos-ghv, eqos-djv).
- The legacy markdown renderer `output/earnings_update.py` sections 6/7 (D1).
- Changing a falsifier threshold through owner `SET_POLICY` decisions (none are made here).
- Band (`OUTSIDE_BAND`) thresholds: an imported thesis cannot carry one (F-5), so none reach
  the binder.
- Breach aggregation across quarters (thesis open question; each quarter stands alone).
**Constraints:**
- The LLM is never the authoritative calculator; every material number links to a fact ID,
  calculation trace or cited thesis claim (invariants 6, 7). No model computes anything here.
- Missing inputs fail closed: no fabricated numbers or filled gaps (invariant 10).
- Output is labelled by epistemic class (invariant 8). Every paragraph carries an `{{e:…}}`
  marker.
- Narrative numbers come only from claim placeholders. Any other numeral raises
  `UNREGISTERED_NUMBER` unless it is structural (`ledger/numeral_scan.py:23-38`). The scanner is
  not changed.
- Tax is never derived as PBT − PAT: approved data spec
  `docs/specs/2026-10-11-canonical-financial-data-and-cross-source-comparison.md:177-179` (§1,
  owner-approved 2026-10-11) and `output/pnl_lines.py:3`.
- Migrations `0001`–`0041` are immutable; schema changes go in a new migration.
- Frozen manifests change only via the approved re-seal flow.
  `tests/fundamentals/fixtures/data_foundation/pilot_manifest.yaml` is not edited by this plan.
- Never open `stage4_holdout.yaml`, `stage4_manifest.yaml`, `data/holdout/` or
  `data/raw/onboarding/`. Never print vendor readings.
- Crisp minimal code (owner 2026-10-14). Python rules: `.claude/rules/python/`.

## Investigation findings

**F-1. The ledger run draft is the authoritative report path.**
- A PostgreSQL `fundamentals run` ends in `write_run_draft` (`api/cli.py:429`), which writes a
  `DRAFT` version and checks it `AS_KNOWN` in the same transaction
  (`ledger/run_draft.py:274-353`). The check's cutoff is the version's `knowledge_cutoff`
  (`lifecycle.py:297`), which is the run's derivation cutoff, stamped from the store clock at
  `api/cli.py:411-413`.
- The pilot asserts on that version: claims, citations, export hash and claim check
  (`tests/fundamentals/test_pilot_e2e.py:222-272`), and on the stock export (PILOT-6).
- The legacy `render_earnings_update` (`output/earnings_update.py:380-559`) only feeds the side-file
  markdown. It is not reviewed, sealed or claim-checked.

**F-2. Today the run draft has no sections 6/7.** `_sections` emits `heading` plus `results`,
`changes`, `calculations` and `management_ledger` (`run_draft.py:96-103,624-660`).

**F-3. The legacy renderer must not change.** `ledger import` requires
`render_earnings_update(twin) == md` (`ledger/import_mapping.py:140-141`), so any text change to
its sections 6/7 breaks the import of the four retained reports (D1).

**F-4. The existing evaluator is retired, not reused.**
- `verify/thesis_impact.py` resolves metrics through `verify/metric_registry.py`, outside any
  stored trace, and prints raw numerals.
- `api/thesis_impact_cli.py:26,43-46` evaluates any YAML as an "approved" thesis with no ledger
  identity. That is eqos-4j2.26.
- Its only dependents are `api/cli.py:79`, `api/cli_parser.py:34` and
  `tests/fundamentals/test_phase05_thesis_impact.py` (grep over `src` and `tests`). Nothing else
  imports `metric_registry` or `thesis_impact`.
- Kept: `FalsifierPredicate`/`ApprovedThesis` (`verify/thesis_predicates.py:27-82`), the predicate
  rule (`thesis_impact.py:65-81`) and `Disposition` (`:26-31`), both moved next to the predicate
  model.

**F-5. How the approved thesis is stored.**
- `config/ledger_import.yaml:12-19` imports Q0 as the `BOOTSTRAP_THESIS` report of FY26_Q2.
  The md and YAML twin are stored byte-for-byte as `eqos.import_sources` and covered by the
  sealed digest (`0012_report_ledger.sql:231-265`).
- Each threshold becomes a self-cited `POLICY` claim `falsifier.F<n>`
  (`import_mapping.py:573-596`); a predicate must have exactly `metric_id`, `op`, `threshold`
  (`:86`), so no band reaches the ledger.
- The version is sealed `IMPORT_SEAL`, then `IMPORTED_APPROVAL` (status `APPROVED`) when the
  evidence rule holds (`importer.py:169-171,195-209,237-256`).
- When the evidence rule fails, `_persist` still commits the version with `IMPORT_SEAL` alone
  (`importer.py:237-245`). Approval cannot be added later: `IMPORTED_APPROVAL` must follow a
  seal from the same transaction, and `SUBMIT` refuses imported versions (`0014:104-114`).

**F-6. Supersession and knowledge time.**
- `eqos.version_superseded` counts both `APPROVE` and `IMPORTED_APPROVAL` on a descendant
  (`0014_ledger_review_fixes.sql:9-18`, replacing `0012:268`).
- `version_status(cursor, id, as_of=t)` reads only decisions recorded at or before `t`,
  supersession included (`lifecycle.py:119-149`).

**F-7. Existing citation kinds cannot cite an approved thesis claim.**
- Kinds are `FIGURE`, `CALCULATION`, `SOURCE_QUOTE`, `COMPARISON` and `POLICY`
  (`contracts/ledger.py:58-63`, schema `0012:61-62`).
- A `POLICY` citation needs an owner `SET_POLICY` decision (`citations.py:132-135,553-565`). A
  self-cited one resolves only on an import (`claim_check.py:82-86`) and blocks `SUBMIT`
  (`0014:107-110`).
- Rework refuses any kind a run draft does not emit (`rework.py:166-177`).
- `_check_sources` treats every `source_sha256` as a capture blob (`run_draft.py:578`), so a new
  kind must not reuse that column.

**F-8. Metric coverage and definitions.**
- `bind_computed` stores `cmp.<role>.yoy.pct` traces: F1 `revenue_yoy_pct` →
  `cmp.revenue.yoy.pct`, F3 `pat_yoy_pct` → `cmp.profit_for_period.yoy.pct`, F4 `eps_yoy_pct` →
  `cmp.basic_eps.yoy.pct`.
- F2 `pbt_margin_pct` has no claim. The thesis registered it as `PROFIT_BEFORE_TAX ÷ REVENUE × 100`
  (`metric_registry.py:202-210`) with a zero-denominator guard (`:308-309`).
- **F5 has a different meaning in the ledger.** The thesis registered `effective_tax_rate_pct` as
  (PBT − PAT) ÷ PBT (`metric_registry.py:220-228,311-317`; the thesis states every metric id is a
  registry id, `q0-approved-thesis.md:45`, F5 row `:92`). The ledger's ETR line is filed tax ÷
  PBT (`pnl_lines.py:3`; branch `run_traces.py:389-393`). Evaluating Q0's F5 against it would
  silently change the falsifier, and reintroducing PBT − PAT is forbidden (Constraints).
- `render_section` resolves a placeholder against all of the version's claims
  (`display.py:85-95`), so falsifier lines re-show existing claims without duplicating them.

**F-9. No path exists today for a successor thesis version.**
- The import is one-shot and roots only: `_persist` always calls `create_report`
  (`importer.py:223`), which is `UNIQUE (entity_id, period, kind)` (`0012:11`), with no
  predecessor.
- A non-imported version can be approved only after `SUBMIT`, which refuses import sources and
  self-cited `POLICY` claims (`0014:104-110`). It therefore cannot carry a predicate twin, and its
  thresholds would need owner `SET_POLICY` decisions.
- The `ledger` CLI has `decide`, `check`, `import`, `stage` and `export` and no verb for writing
  a thesis version (`api/ledger_cli.py:123-158`).

**F-10. What the pilot asserts.**
- PILOT-4 requires the non-quote claim keys to equal exactly the 46 `KEYS`
  (`test_pilot_e2e.py:236-237`) and each value to equal its frozen value (`:238-240`).
- Each non-guidance claim must route to a fact, trace or labelled filed value (`:241-251`).
- It also checks `FILED_COUNTS`, the export hash against the version's own `content_hash`, and
  an all-`MATCH` claim check.
- New sections and claims keep every frozen value valid, so **no re-seal is needed**. The
  key-set equality and the routing check are updated deliberately in test code (Tasks 1 and 3).

**F-11. Rework and the new lines.**
- `rework.plan` records placeholder lines and scaffolds for every section with `ordinal > 0`
  (`rework.py:229-252`). `Gate.close` refuses unless each comes back through the gate
  (`:107-119`).
- `Gate.line` raises "moved" for a line whose keys the reworked version never had (`:89-105`).
  So selectively reworking a version written before this slice refuses on the new margin line.
- Adding the margin claim changes the rerun closure when revenue or PBT is rejected, because it
  shares their input atoms (`test_prep5_rework.py:339-366`, `rework.py:230-239`).

**F-12. The data spec assigns "PBT margin" to headline PBT.** Spec `:171` lists
`profit_before_tax_incl_associates` as used for "Headline PBT; PBT margin", while the thesis
registry's `pbt_margin_pct` uses `PROFIT_BEFORE_TAX` (before associates). The thesis does not say
which PBT its F2 basis (`q0-approved-thesis.md:89`) is. See D8.

## Design (smallest that meets the goal)

- **One new citation kind, `THESIS_CLAIM`**, so a run draft can cite an approved thesis
  threshold. It pins the cited claim (its row id fixes version and claim) and that version's
  sealed digest. It resolves only when an `APPROVE`/`IMPORTED_APPROVAL` decision recorded that
  digest on that version, and the decision's time is an input time held against the cutoff.
  Nothing else in the claim check, scanner or `SUBMIT` rule changes.
- **One new trace:** the PBT margin.
- **One new module** that selects the thesis and renders two derived sections. It selects the
  newest version on the stock's `BOOTSTRAP_THESIS` chain that was `APPROVED` as of the run's
  derivation cutoff, so the selection and the claim check share one boundary.
- **Q0's F5 is not evaluated.** Its metric id is marked superseded and renders `UNRESOLVED`. A
  successor thesis that re-registers F5 on filed tax ÷ PBT is imported through a minimal
  extension of the existing import path, and the run picks it up once it is approved (D6).
- **The legacy thesis-impact evaluator and its CLI are deleted** (D3).

Rendered shape (every token outside placeholders is non-numeric or structural):

```
## thesis_impact

{{e:computed}} Deterministic falsifier status against approved thesis version:<id> (sealed digest <sha256>): WEAKENED F2; HELD F1, F3, F4; UNRESOLVED F5. The narrative impact is not drafted by this pipeline.

## observable_falsifiers

{{e:computed}} {{e:opinion}} Each falsifier of thesis version:<id>, tested in code: what is measured, its traced value, the operator, the thesis threshold, and the status.
- F1 Revenue YoY growth (%): {{c:cmp.revenue.yoy.pct|plus,unit}} below {{c:thesis.F1|}}: HELD (not triggered)
- F2 PBT margin, PBT before associates over revenue (%): {{c:calc.pbt_margin|}} below {{c:thesis.F2|}}: WEAKENED (triggered)
- F5 Effective tax rate (%): UNRESOLVED (definition superseded, pending approval)
```

The statuses illustrate the layout only. With no approved thesis, each section is the single
paragraph `{{e:computed}} UNRESOLVED: no approved thesis.` (D4).

## Design decisions (for Sol's plan review)

- **D1 — legacy markdown.** Leave `earnings_update.py` sections 6/7 unchanged (F-3). The goal is
  met on the authoritative path. Flag this to the owner in the summary.
- **D2 — thresholds are cited claims (r2, replaces "by reference").** Each evaluated falsifier
  emits a run claim `thesis.F<n>` (section `observable_falsifiers`) with kind `THESIS_CLAIM`.
  It copies value, precision, rounding, unit and value kind from the thesis's `falsifier.F<n>`
  claim. `SET_POLICY` is not used, and no owner decision is manufactured.
- **D3 — eqos-4j2.26 (r2).** Delete `api/thesis_impact_cli.py`, `verify/thesis_impact.py` and
  `verify/metric_registry.py` and their registration in this slice (F-4). The run draft is then
  the only consumer of an approved thesis, bound to the ledger by construction.
- **D4 — no approved thesis (r2).** One contract, at section level: both sections read
  `UNRESOLVED: no approved thesis.` with no rows, and the draft still validates.
  - An approved thesis with no YAML twin, a twin that does not parse, or a symbol other than
    the run's raises `RunDraftError`. Silently dropping an approved thesis is worse than no
    report.
- **D5 — live regeneration.** Regenerate the live Apar drafts only after Sol's phase-end APPROVE
  of Tasks 1–5 and after the successor thesis is imported (Task 6), so they are regenerated
  once. Ledger versions are append-only.
- **D6 — F5 (orchestrator ruling, r2).**
  - Q0's `effective_tax_rate_pct` is in `SUPERSEDED_METRICS` and always renders `UNRESOLVED`
    with reason "definition superseded, pending approval", without a threshold claim.
  - A successor thesis re-registers F5 as `filed_effective_tax_rate_pct` (filed tax ÷ PBT, the
    ledger ETR line). It keeps the same threshold unless the Task 6 comparison shows that is
    inappropriate, and the reason is recorded in the successor's text.
  - The successor is imported onto the existing chain (`ledger import --thesis-successor`,
    Task 4). Approval is the existing `IMPORTED_APPROVAL` panel decision under the evidence rule,
    and the evidence commit records Sol's APPROVE (`.claude/rules/core/04-agent-stack.md`
    autonomous approval). Q0 then becomes `SUPERSEDED` (F-6).
- **D7 — rework of a pre-slice version.** `rework.plan` refuses a version with claim rejections
  that has no `thesis_impact` section: "version N predates the falsifier sections; rerun with
  --full-successor". `--full-successor` is the supported upgrade (`run_draft.py:237-243`). No
  new-line special case is added to the gate.
- **D8 — F2 basis (ruled 2026-10-23: keep; Sol plan review r2 accepted).** Keep the thesis registry's definition (PBT before
  associates ÷ revenue): it is what F2's threshold was set against, and the spec does not forbid
  that ratio. Label the line so it does not read as the spec's headline margin.
  - Sol's review of the successor thesis (Task 6) rules whether F2 moves to headline PBT too. If
    it does, Task 6 re-registers F2 the same way as F5 (a new metric id plus a margin trace on the
    `HEADLINE_LABEL` claim). Nothing in Tasks 1–5 changes.

## File map

| File | Responsibility (one) |
|---|---|
| `migrations/0042_thesis_claim_citation.sql` (create) | `THESIS_CLAIM` kind: columns, checks, digest extension |
| `src/fundamentals/contracts/ledger.py` (modify) | `CitationKind.THESIS_CLAIM`; `Citation.cited_claim_id`, `cited_sealed_digest` |
| `src/fundamentals/ledger/store.py` (modify) | Write/read the two new citation columns |
| `src/fundamentals/ledger/citations.py` (modify) | Resolve a `THESIS_CLAIM` citation |
| `src/fundamentals/ledger/claim_check.py` (modify) | `THESIS_CLAIM` in `VALUED` |
| `src/fundamentals/verify/thesis_predicates.py` (modify) | `Disposition`, `FalsifierPredicate.holds`, `parse_thesis(bytes)` (replaces `load_thesis`) |
| `src/fundamentals/ledger/run_traces.py` (modify) | PBT-margin line in `calculations` |
| `src/fundamentals/ledger/falsifier_status.py` (create) | Select the approved thesis as of a cutoff; evaluate; build the derived sections and threshold claims |
| `src/fundamentals/ledger/run_draft.py` (modify) | Append the derived sections and claims |
| `src/fundamentals/ledger/rework.py` (modify) | Skip derived sections and claims; refuse derived-claim rejections and pre-slice heads |
| `src/fundamentals/ledger/importer.py`, `api/ledger_cli.py` (modify) | Import a thesis successor onto the chain |
| `src/fundamentals/api/thesis_impact_cli.py`, `verify/thesis_impact.py`, `verify/metric_registry.py` (delete) | Retired (D3); registrations removed from `api/cli.py`, `api/cli_parser.py` |
| `tests/fundamentals/test_phase05_thesis_impact.py` (modify) | Keep predicate/parse tests only |
| `tests/fundamentals/test_falsifier_status.py` (create) | Binder, citation and evaluate tests |
| `tests/fundamentals/test_pilot_e2e.py` (modify) | Margin, threshold claims, statuses, sections per quarter |
| `tests/fundamentals/test_prep5_rework.py` (modify) | Rerun closures with the margin; derived skip; pre-slice refusal |
| `tests/fundamentals/test_ledger_import.py` (modify) | Successor import |

## Tasks

### Task 1: Traced PBT margin claim in every run draft

Goal: every run draft's `calculations` section has the line `MARGIN_LABEL`. When PBT and a
non-zero revenue are present, its claim `calc.pbt_margin` cites a stored `COMPUTED` trace with
value fact `profit_before_tax` ÷ fact `revenue` × 100, at 2 places `ROUND_HALF_EVEN`, and it
resolves `MATCH`. Otherwise the line has no claim and renders `OPERAND_MISSING`. PILOT-4's 46
frozen values hold unchanged.

Files:
- Modify: `src/fundamentals/ledger/run_traces.py`, `tests/fundamentals/test_pilot_e2e.py`,
  `tests/fundamentals/test_prep5_rework.py`
- Test: the same two test files.

Interfaces:
- Consumes: `_Binder.trace`, `reported(name, role)`, `RUN_PERCENT_PLACES` (`run_traces.py`).
- Produces: `RATIO_PCT = "run.ratio_pct"`; `MARGIN_KEY = "calc.pbt_margin"`;
  `MARGIN_LABEL = "PBT margin, PBT before associates over revenue (PBT / revenue × 100, %)"`
  (D8), all exported from `run_traces.py`.

Approach:
- After the calculations loop: if `FactRole.REVENUE` is absent from `facts` or its value is
  zero, append `Line(section=CALCS, label=MARGIN_LABEL)` with no claim. Otherwise compute
  `(pbt / revenue * 100).quantize(Decimal("0.01"), ROUND_HALF_EVEN)` and bind it with
  `binder.trace(MARGIN_KEY, CALCS, RATIO_PCT, binder.key(MARGIN_LABEL, PERCENT),
  (reported("pbt", PBT), reported("revenue", REVENUE)), value, PERCENT,
  precision=RUN_PERCENT_PLACES, rounding=Rounding.ROUND_HALF_EVEN)`. PBT is already required
  (`run_traces.py:371`).
- Make `_compute`'s ratio branch explicit (`formula in (ETR, RATIO_PCT)`), and raise
  `RunDraftError` for an unknown formula id instead of the catch-all `else`. Document
  `run.ratio_pct` in the module docstring.
- `test_pilot_e2e.py::_pilot4`: compare `figures` to `CLAIM_KEYS | {MARGIN_KEY} | thresholds`.
  Here `thresholds` is the set of `thesis.F<n>` keys from Task 3; until Task 3 lands it is empty.
  - Assert `claims[MARGIN_KEY].value == round_half_even(frozen fact.profit_before_tax / frozen
    fact.revenue × 100, 2)` (as `Fraction` over `frozen_value`), and that it cites
    `CALCULATION` with a trace id.
- `test_prep5_rework.py:339-347` (F-11, deliberate):
  - Add `MARGIN_KEY` to the `fact.revenue` rerun set.
  - Add a case rejecting `MARGIN_KEY` itself. Its expected rerun set is written out literally:
    the margin and every claim sharing its revenue or PBT inputs, closed over their lines. The
    docstring states that one-hop rule.
- Focused test (medium, in `test_prep5_rework.py` or `test_prep2b_run_draft.py`, whichever already
  builds a `bind_computed` input): a zero revenue and a missing revenue each give a claimless
  margin line rendering `OPERAND_MISSING`, with no `MARGIN_KEY` claim and no trace stored.

Verification:
- `uv run pytest tests/fundamentals/test_pilot_e2e.py tests/fundamentals/test_prep2b_run_draft.py tests/fundamentals/test_prep5_rework.py -q`
  is green. This needs the compose postgres and the retained originals.
- `uv run mypy --strict src`.

Dependencies: None.

Risks:
- The run value and the trace must agree at the stored scale (`_compute` compares
  `store_value`). Use the ETR line's quantization.
- `FILED_COUNTS` is unaffected (the claim is a trace).

### Task 2: `THESIS_CLAIM` citation kind

Goal: a run-draft claim can cite an approved thesis claim, pinned to that claim and its version's
sealed digest. It resolves `MATCH` only while that digest carries an approval recorded at or
before the check's cutoff. Every existing version's sealed digest is unchanged.

Files:
- Create: `migrations/0042_thesis_claim_citation.sql`
- Modify: `contracts/ledger.py`, `ledger/store.py`, `ledger/citations.py`, `ledger/claim_check.py`
- Test: `tests/fundamentals/test_falsifier_status.py`

Interfaces:
- Produces: `CitationKind.THESIS_CLAIM`, `Citation.cited_claim_id: int | None` and
  `Citation.cited_sealed_digest: str | None`.

Approach:
- Migration, following the pattern of `0033`:
  - Add `cited_claim_id bigint REFERENCES eqos.numeric_claims (id)` and `cited_sealed_digest text`.
  - Replace the `citation_kind` IN-list check and the `measurement_key` check (`0012:61-62,88`) so
    they include `THESIS_CLAIM`. Read the constraint names from `\d eqos.numeric_claims`.
  - Add one check: `citation_kind <> 'THESIS_CLAIM' OR (num_nonnulls(<every other citation
    column>) = 0 AND cited_claim_id IS NOT NULL AND cited_sealed_digest IS NOT NULL AND NOT
    unresolved AND value IS NOT NULL)`.
  - Add a second: `citation_kind = 'THESIS_CLAIM' OR num_nonnulls(cited_claim_id,
    cited_sealed_digest) = 0`.
  - `CREATE OR REPLACE eqos.version_sealed_digest` with one addition per claim, after
    `policy_decision_id`: `CASE WHEN c.cited_claim_id IS NULL THEN '' ELSE
    eqos.enc(c.cited_claim_id::text) || eqos.enc(c.cited_sealed_digest) END`. Because it adds
    nothing for existing claims, existing digests are unchanged.
- `citations.py`: add a `THESIS_CLAIM` branch and query. The cited claim's version must belong to
  the entity's `BOOTSTRAP_THESIS` report, and its key must start `falsifier.`. Take the earliest
  decision on that version with kind `APPROVE` or `IMPORTED_APPROVAL` whose `sealed_digest`
  equals both `cited_sealed_digest` and `eqos.version_sealed_digest(version)`.
  - Return the cited value, unit and value kind, with `times=((InputTime.POLICY,
    recorded_at),)`. No row gives `None`, which is `UNRESOLVED`.
- `claim_check.py`: add `THESIS_CLAIM` to `VALUED`. Nothing else changes. `SUBMIT` legality is
  untouched, because the kind is not a self-cited `POLICY`.
- Tests (medium, `ledger_support.Ledger` on a disposable DB):
  - A run claim citing an approved thesis claim is `MATCH`.
  - A wrong digest, a cited version with no approval, or a cited claim that is not
    `falsifier.*` gives `UNRESOLVED`.
  - An approval recorded after the citing version's cutoff gives `POST_CUTOFF`.
  - The sealed digest changes when `cited_claim_id` changes.
  - The schema refuses a `THESIS_CLAIM` row with a `source_sha256`, and a `FIGURE` row with a
    `cited_claim_id`.

Verification: `uv run pytest tests/fundamentals/test_falsifier_status.py tests/fundamentals/test_ledger_integrity.py tests/fundamentals/test_ledger_claim_check.py -q`; `uv run mypy --strict src`.

Dependencies: None.

Risks:
- Retention triggers (`0027:189`, `0028:182-188`) key on `SOURCE_QUOTE` and are unaffected. Run
  the retention tests in the full suite.
- Read views (`0021`) list columns explicitly. The new columns are not needed there.

### Task 3: Falsifier status sections bound to the thesis approved at the cutoff

Goal: `write_run_draft` writes `thesis_impact` and `observable_falsifiers`, in that order after
`management_ledger`. They come from the newest `BOOTSTRAP_THESIS` version that was `APPROVED` as
of `update.derivation_cutoff`, and they name its version id and sealed digest. The legacy
evaluator and CLI are gone. Rework skips the derived sections. For Apar, all four quarters'
statuses equal those the test derives independently, and F5 is `UNRESOLVED` (superseded).

Files:
- Create: `src/fundamentals/ledger/falsifier_status.py`
- Modify: `verify/thesis_predicates.py`, `ledger/run_draft.py`, `ledger/rework.py`,
  `api/cli.py`, `api/cli_parser.py`
- Delete: `api/thesis_impact_cli.py`, `verify/thesis_impact.py`, `verify/metric_registry.py`
- Test: `test_falsifier_status.py`, `test_phase05_thesis_impact.py`, `test_pilot_e2e.py`,
  `test_prep5_rework.py`

Interfaces:
- Consumes: `MARGIN_KEY` (Task 1), `ETR_LABEL` (`output/pnl_lines.py:17`), `THESIS_CLAIM`
  (Task 2), `Line`, `store.read_version`, `store.sealed_digest`, `version_status`, `_LOCK`.
- Produces:
  - In `thesis_predicates.py`: `Disposition` (moved verbatim), `FalsifierPredicate.holds(value:
    Decimal) -> bool` (moved verbatim from `_predicate_holds`), and `parse_thesis(content:
    bytes) -> ApprovedThesis` with `content_sha256` the bytes' sha256. `load_thesis` is deleted
    along with its only caller.
  - In `falsifier_status.py`:
    - `THESIS_IMPACT`, `FALSIFIER_STATUS` and `DERIVED = frozenset({THESIS_IMPACT,
      FALSIFIER_STATUS})`.
    - `METRICS: Mapping[str, tuple[str, str | None]]`, mapping a metric id to (label, claim
      key). Entries: F1/F3/F4 → `cmp.*.yoy.pct`, `pbt_margin_pct` → `MARGIN_KEY`, and
      `filed_effective_tax_rate_pct` → `None`, which means the claim of the `calculations` line
      labelled `ETR_LABEL`.
    - `SUPERSEDED_METRICS = frozenset({"effective_tax_rate_pct"})`.
    - `class BoundThesis(BaseModel)` (frozen): `version_id`, `sealed_digest`, `thesis:
      ApprovedThesis` and `thresholds: Mapping[str, tuple[int, NumericClaim]]` (falsifier id →
      thesis claim row id and claim).
    - `approved_thesis(cursor, entity_id: int, symbol: str, as_of: datetime) -> BoundThesis |
      None`.
    - `class FalsifierRow(BaseModel)` (frozen): `falsifier_id`, `label`, `op`, `claim_key: str
      | None`, `disposition: Disposition` and `reason: str | None`.
    - `evaluate(bound: BoundThesis, claims: Mapping[str, NumericClaim], lines: Sequence[Line])
      -> tuple[FalsifierRow, ...]`, which is pure.
    - `derived(bound: BoundThesis | None, rows) -> tuple[tuple[tuple[str, str], ...],
      tuple[NumericClaim, ...]]`: the two (section key, body) pairs and the `thesis.F<n>`
      threshold claims for the evaluated rows.

Approach:
- **`approved_thesis`.**
  1. Select the version ids of the entity's `BOOTSTRAP_THESIS` report, newest first.
  2. For each, take the `REPORT_VERSION` `_LOCK`, then call `version_status(cursor, id,
     as_of=as_of)`. Use the first that is `APPROVED`; if none is, return `None`.
  3. From its import sources, take the single one whose path ends `.yaml`. If there is none, or
     `parse_thesis` fails, or `thesis.symbol != symbol`, raise `RunDraftError` (D4).
  4. Read its `falsifier.F<n>` claims and their row ids.
- **`evaluate`.** Statuses are checked in this order:
  - A metric in `SUPERSEDED_METRICS` → `UNRESOLVED`, reason "definition superseded, pending
    approval".
  - An unmapped metric, a missing claim (including the claimless margin of Task 1) or a missing
    threshold → `UNRESOLVED` with a fixed reason.
  - Otherwise `WEAKENED` if `predicate.holds(claim.value)`, else `HELD`. `claim.value` is the
    stored run value at claim precision: what the reader sees and what the claim check matched.
- **`derived`.**
  - Renders the shape in the Design section, and for `None` the D4 sentence.
  - Operator words are `LT` below, `LTE` at or below, `GT` above, `GTE` at or above.
  - Labels and reasons are digit-free module constants, so a claim key such as `calc.3` is never
    printed outside a placeholder.
  - Measured-claim style: `plus,unit` for `cmp` claims, `""` for calc claims. Threshold claims
    use `""`, the style the import uses (`import_mapping.py:596`).
  - Each threshold claim is `thesis.F<n>` (section `FALSIFIER_STATUS`, epistemic `OPINION`,
    no measurement key), citing `THESIS_CLAIM(cited_claim_id, cited_sealed_digest =
    bound.sealed_digest)`.
- **`run_draft.write_run_draft`.**
  1. After `claims = predecessor(...)`, call `approved_thesis(cursor, entity_id, update.nse_symbol,
     update.derivation_cutoff)`, then `evaluate` and `derived`. The `assert` on
     `derivation_cutoff` moves up to here, so one boundary serves both the selection and the
     claim check (F-1).
  2. `_sections` appends the derived sections after the `INTROS` sections with consecutive
     ordinals. The threshold claims join `claims` before `content_hash` and `create_version`.
- **`rework.plan`.**
  - Drop sections in `DERIVED` from `lines` and `scaffolds`, and their claims from `claims`
    before `inputs`, because they are re-derived on every write.
  - Refuse a rejection naming a derived claim: "thesis.Fn is re-derived from the approved
    thesis; supersede the thesis instead".
  - After the no-rejections early return, refuse a head with no `THESIS_IMPACT` section (D7).
- **Retire (D3).** Delete the three modules and their registration lines. In
  `test_phase05_thesis_impact.py`, delete the tests of the deleted modules and keep the
  predicate-validation and parse tests, rewritten from `load_thesis` to `parse_thesis`.
- **Unit test** (small, the only one): `FalsifierPredicate.holds`, parametrized.
  - `LT`/`GT` at equality are not held; `LTE`/`GTE` at equality are held.
  - `OUTSIDE_BAND` at both edges is not held; just outside is held.
- **Binder and evaluate tests** (medium, `test_falsifier_status.py`, `ledger_support.Ledger`
  seeding imported versions with test-owned twin bytes):
  - an approved successor is selected over Q0;
  - an imported successor without `IMPORTED_APPROVAL` is not selected (Q0 is);
  - a withdrawn or never-approved chain gives `None`, and `derived` gives the D4 sections;
  - a symbol mismatch, a missing `.yaml` source and a malformed twin each raise `RunDraftError`;
  - an approval recorded after `as_of` but before the call is not selected;
  - `evaluate` gives `UNRESOLVED` for a superseded metric, a missing claim and a claimless
    margin.
- **Pilot integration** (`test_pilot_e2e.py`, every quarter including FY26_Q2):
  - The two sections follow `management_ledger` in order, and `thesis_impact` names the imported
    Q0 version id and its sealed digest.
  - Each F1–F4 status equals one computed in the test. The test reads `op` and `threshold` from
    `docs/evidence/phase-0.5/q0-approved-thesis.yaml` with `yaml.safe_load` and compares them as
    `Fraction` against `frozen_value(quarter, key)`, with the margin derived as in Task 1. The
    expectation never comes from the code under test.
  - F5 is `UNRESOLVED` with the superseded reason, and has no threshold claim.
  - PILOT-4 routing gains one branch: a `thesis.F<n>` claim cites `THESIS_CLAIM`, its
    `cited_claim_id` is the Q0 version's `falsifier.F<n>` row, and `cited_sealed_digest` equals
    that version's sealed digest. `citations_allowed` is unaffected because the kind cites no
    blob.
  - The export hashes to `content_hash`, the claim check is all `MATCH`, and PILOT-11's rework
    still succeeds.
- **Rework tests** (`test_prep5_rework.py`):
  - `:363` compares `found.carried` with the non-derived claim keys minus `rerun` (derived =
    claims in `DERIVED` sections), and asserts no `thesis.F<n>` key is in `carried` or `rerun`.
  - The line-count loop at `:364-366` iterates non-derived sections only.
  - Rejecting `thesis.F1` refuses.
  - Pre-slice head: write the submitted Q2 version's sections and claims, minus the two derived
    sections, the margin line and the margin and threshold claims, as a successor of a closed
    head via `store.create_version` (runtime role), with its `content_hash` recomputed. Submit
    it and request changes on `fact.revenue`.
    - An ordinary rerun refuses with the D7 message.
    - `--full-successor` succeeds, and the new version has `MARGIN_KEY` and both sections.

Verification:
- `uv run pytest tests/fundamentals/test_phase05_thesis_impact.py tests/fundamentals/test_falsifier_status.py tests/fundamentals/test_pilot_e2e.py tests/fundamentals/test_prep2b_run_draft.py tests/fundamentals/test_prep5_rework.py -q`
  is green.
- `uv run fundamentals thesis-impact --help` exits non-zero (unknown command).
- `scripts/verify.sh gate RESEARCH-1`: all gate commands green plus the red-proof.

Test seams: `ledger export <version>`, `pilot.version(id).sections`,
`pilot.validate(id).claim_states`, `falsifier_status.evaluate` (pure) and `approved_thesis`.

Dependencies: Tasks 1 and 2.

Risks:
- **Test-first:** write the pilot status assertion first and watch it fail red with no derived
  sections. The red-proof gate requires this.
- **Numeral leakage** fails the draft as `UNREGISTERED_NUMBER`. Statements and claim keys are
  never printed outside placeholders.
- **The pilot's Q0 may not be `APPROVED`** if the evidence rule fails in the test checkout. Then
  every section reads the D4 sentence and the status assertion fails loudly. Check this first;
  do not weaken the assertion.
- **Other shape tests may break.** Run the full `tests/fundamentals` suite.
- **Boundary semantics.** Statuses compare the 2-place stored value; at exact equality the op's
  strictness applies (pinned by the unit test).

### Task 4: Import a thesis successor onto the existing chain

Goal: `fundamentals ledger import --thesis-successor` imports the configured successor thesis as
the next version of the stock's `BOOTSTRAP_THESIS` report. It uses the same lossless mapping,
the same `IMPORT_SEAL`, and `IMPORTED_APPROVAL` under the same evidence rule. Its predecessor
then becomes `SUPERSEDED`, and `approved_thesis` selects the successor.

Files:
- Modify: `src/fundamentals/ledger/importer.py`, `src/fundamentals/api/ledger_cli.py`
- Test: `tests/fundamentals/test_ledger_import.py`

Interfaces:
- Produces:
  - `ImportConfig.thesis_successor: Q0Import | None = None`, with the same fields as `q0`.
  - `import_thesis_successor(pool, config, *, repo, catalog, snapshots) -> ImportedVersion`.

Approach:
- Map with `map_q0`, then compute `evidence_holds(repo, entry.evidence_commit, files,
  entry.decided_on)` **before** any write. `None` refuses: return `ImportedVersion(failure=…)`
  (CLI exit `EXIT_REFUSED`, as for a lossless refusal) and persist nothing. A failed successor
  must never reach `_persist`, because a sealed but unapproved head would strand the chain
  (F-5): it blocks every later successor and can never be approved.
- Give `_persist` two optional arguments, `report_id` and `predecessor_id`. When `report_id` is
  given it does not call `create_report`. Inside its transaction, before `create_version`:
  - take `_LOCK` on the `REPORT_VERSION` `predecessor_id`, and refuse unless it is the report's
    head and `APPROVED`;
  - refuse if any version of the report already holds an import source with the successor
    twin's sha256 ("already imported"). This makes a repeat import refuse even though the first
    successor is now the approved head. The `predecessor_id UNIQUE` chain constraint
    (`0012:19`) already blocks a concurrent fork.
- Validate `RETROSPECTIVE` as `import_versions` does.
- The CLI flag `--thesis-successor` on `ledger import` runs only this function. Without the
  flag, the action is unchanged.
- Test (medium):
  - Copy the Q0 md and twin into a temp git repo and commit them today, then import Q0 and the
    successor from that repo.
  - The successor's predecessor is Q0, its status is `APPROVED`, Q0's is `SUPERSEDED`, and
    `approved_thesis` returns the successor.
  - Invalid evidence (the successor pair committed on a date other than `decided_on`) refuses,
    and the report's version, decision and import-source row counts are unchanged; Q0 stays the
    `APPROVED` head. Re-running with corrected evidence (`decided_on` set to the commit date)
    succeeds.
  - Importing the same successor again refuses "already imported", and the row counts are
    unchanged.
  - Successor F5 (integration): the test-owned successor twin registers F5 as
    `filed_effective_tax_rate_pct`. Given a `calculations` line labelled `ETR_LABEL` with a
    claim, `evaluate(approved_thesis(...), …)` gives F5 `WEAKENED` or `HELD` (not `UNRESOLVED`)
    on that claim, and `derived` emits `thesis.F5` citing `THESIS_CLAIM` on the successor's
    `falsifier.F5` row and the successor's sealed digest.

Verification: `uv run pytest tests/fundamentals/test_ledger_import.py -q`; `uv run mypy --strict src`.

Dependencies: Task 3 (`approved_thesis`).

Risks: no migration, since the chain constraint (`0012:14-28`) already allows a successor.

### Task 5: Close the binding gap and record the decisions

Goal: the D1–D8 outcomes are recorded, and `CONTEXT.md` names the two derived sections.

Files: this plan (Sol's rulings) and `CONTEXT.md` (at most one line under Thesis). Bead work is
done by the orchestrator:
- close eqos-4j2.26 with "bound via ledger/falsifier_status.py; thesis-impact CLI retired";
- file a bead for the successor-thesis content (Task 6);
- add a note on eqos-bnx.

Verification: the structural gate; `git status` shows only the intended files.

Dependencies: Tasks 1–4 and Sol's phase-end APPROVE.

### Task 6: Successor thesis for F5 (operational, orchestrator)

Goal: an approved successor thesis whose F5 is `filed_effective_tax_rate_pct`, imported into the
live ledger.

Approach:
1. A scratchpad script computes, from the retained Q0-window facts only (the thesis's derivation
   window; no later quarter), the filed tax ÷ PBT rate per quarter and reapplies F5's stated
   threshold recipe ("Q2 FY26 rate plus the observed quarter-on-quarter spread",
   `q0-approved-thesis.md:92`) to it, at the threshold's 2 places. It never derives tax as
   PBT − PAT (Constraints). The numbers come only from this script.
2. Copy Q0's md and twin to `docs/evidence/phase-0.5/q0-thesis-successor-1.{md,yaml}`.
   - F5's predicate becomes `filed_effective_tax_rate_pct GT <threshold>`, using the same value
     unless the script's recomputation differs; the script output decides.
   - Add a reason paragraph citing data spec §1 and this plan.
   - `approved_by` is Sol (the autonomous-approval directive).
   - The successor must map losslessly (`map_q0`).
3. Run a fresh Sol review of the pair together with the script output, including the D8 ruling
   on F2. On APPROVE, commit the pair and the ruling in one commit; that commit is the evidence
   commit.
4. Add the `thesis_successor` block to `config/ledger_import.yaml` and commit.
5. Migrate with a drift-aware preflight (no new product code). `check-live` requires the
   recorded migrations to equal the on-disk set exactly (`pg/live_check.py:46-49`), so it fails
   while `0042` is pending.
   - Preflight: copy `migrations/` minus `0042_thesis_claim_citation.sql` to
     `scratchpad/pre-0042-migrations/` and run `uv run fundamentals db check-live
     --migrations-dir scratchpad/pre-0042-migrations`. It passes only when the live DB's
     recorded migrations are exactly `0001`–`0041` with matching sha256s, plus the identity and
     legacy-store checks.
   - Record `eqos.version_sealed_digest(id)` for every version with a read-only query into a
     scratchpad file.
   - `uv run fundamentals db migrate` (applies `0042`; it already refuses checksum drift on
     recorded files).
   - Re-run the digest query; the two lists must be identical.
   - `uv run fundamentals db check-live` (default migrations dir) exits 0.
6. Run `uv run fundamentals ledger import --thesis-successor --snapshot-root <live snapshot
   root>`, then `db check-live`.

Dependencies: Task 5. The script output and Sol's verdict go in the bead notes.

### Task 7: Regenerate the live Apar updates (operational, orchestrator, D5)

Goal: the live DB's FY26_Q3, FY26_Q4 and FY27_Q1 Apar updates have new versions carrying both
sections, with F5 evaluated against the successor. Each passes the review lifecycle in
issuer-quarter order.

Approach:
1. `uv run fundamentals db check-live` exits 0 (eqos-89z).
2. For each quarter in order, use an **ordinary** `fundamentals run` (no `--full-successor`,
   which refuses an approved head: `run_draft.py:237-240`). On an `APPROVED`, unrejected head,
   preflight plans no rework (`:244-246`) and writes a new version whose predecessor is that
   head.
   - The argv has the flag set the pilot uses (`prep2b_support.py:269-275`): `run --issuer
     APARINDS --quarter Q3-FY26 --config <config> --source-admission-manifest <locator>
     --source-admission-store <retained store> --snapshot-root <snapshot root> --watchlist
     <watchlist> --issuer-config <each quarter's> --compare-run <run id>`. Add `--retrospective
     <retrieval manifest>` when the superseded head's heading carries the designation.
   - Every value comes from the live records of the head being superseded: its run's config file
     (`config/aparinds-fy26-q3.yaml`, `-fy26-q4-pg.yaml`, `-fy27-q1.yaml` for the pilot mapping;
     confirm against the head's run), the live locator manifest written by `register-sources`,
     and the comparison run in its `pinned_run_ids`. The pilot's tmp paths are a disposable DB's
     and are never used.
3. Take each new version through the panel lifecycle before the next quarter. The next quarter's
   preflight pins the predecessor's `APPROVED` head.
4. FY26_Q2 is regenerated only if Sol's D5 ruling asks for the baseline row in the live ledger.

Verification: `ledger export <version> --out <scratchpad file>` shows both sections, with F5
evaluated, for each new version; `db check-live` still passes.

Dependencies: Task 6 and Sol's phase-end APPROVE.

Risks: writes are append-only and permanent. A panel `REQUEST_CHANGES` goes through the normal
rework flow; post-slice versions rework selectively.

## Verification summary

- `uv run ruff check src tests/fundamentals` and `uv run ruff format --check src tests/fundamentals`
- `uv run mypy --strict src`
- `uv run pytest tests/fundamentals` (compose postgres plus retained originals; no `not pg` /
  `not retained` opt-outs, because the pilot e2e is the acceptance test)
- `scripts/verify.sh gate RESEARCH-1`
- `git status` shows only the files in the file map.

## Self-review

- **Coverage:**
  - label, measured claim, operator, cited threshold and status → Tasks 2 and 3;
  - margin → Task 1;
  - knowledge-time selection → Task 3;
  - F5 meaning preserved → D6, Tasks 3, 4 and 6;
  - eqos-4j2.26 → D3, Task 3;
  - rework → Tasks 1 and 3 (D7);
  - pilot validity with no re-seal → Tasks 1 and 3;
  - live reports → Task 7.
- **Placeholders.** The operational argv values in Task 7 and the threshold in Task 6 are read
  from live records and script output at execution time. Nowhere else.
- **Names.** `MARGIN_KEY`, `RATIO_PCT`, `THESIS_CLAIM`, `DERIVED`, `SUPERSEDED_METRICS`,
  `BoundThesis`, `FalsifierRow`, `approved_thesis`, `evaluate`, `derived`, `parse_thesis`,
  `FalsifierPredicate.holds` and `import_thesis_successor` are each produced before use.
- **Gaps named:** legacy md stays a placeholder (D1); F2 basis ruled: keep before-associates, labelled (D8); breach
  aggregation is out of scope. `docs/evidence/pilot/report.md` stays historical.

## Review response (r2)

| # | Finding (gpt-6.1-sol r1) | Change | Plan section |
|---|---|---|---|
| 1 | P1 D2 omits what a falsifier tests; thresholds uncitable | Rows print label, measured claim, operator word, threshold claim `thesis.F<n>` and status. New `THESIS_CLAIM` kind pinned to the cited claim row and sealed digest, resolved only through a recorded approval of that digest; schema checks and digest extended (existing digests unchanged); scanner untouched; no `SET_POLICY`. Rework excludes derived claims and refuses their rejection. PILOT-4 key set and routing reassessed. | Design; D2; F-7; Task 2; Task 3 (`derived`, `rework.plan`, pilot) |
| 2 | P1 F5 changes meaning | Q0 F5 renders `UNRESOLVED` ("definition superseded, pending approval"), tested in pilot and unit. Successor thesis re-registers F5 as filed tax ÷ PBT with the same threshold unless the script shows otherwise, imported with Sol's APPROVE as evidence. Spec line cited (`…cross-source-comparison.md:177-179`). No existing successor path existed (F-9), so Task 4 adds the smallest one. | F-8; F-9; D6; Tasks 3, 4, 6 |
| 3 | P1 `--full-successor` refuses approved heads | Ordinary run; argv flag set from `prep2b_support.py:269-275` with every value taken from the live head's records, never the pilot's tmp paths. | Task 7 |
| 4 | P2 selection not pinned to knowledge time | `approved_thesis(..., as_of=update.derivation_cutoff)`, the same boundary as the claim check's cutoff. `THESIS_CLAIM` approval time is a `POLICY` input time. Test: approval after `as_of` is not selected. | F-1; Design; Task 3 |
| 5 | P2 selective rework of pre-slice versions | Refuse with a pointer to `--full-successor` (supported). Test: a pre-slice head lacking the margin and both sections refuses ordinary rework and succeeds with `--full-successor`. | F-11; D7; Task 3 |
| 6 | P2 rerun closure changes with the margin | `fact.revenue` case gains `MARGIN_KEY` deliberately. New case rejects the margin itself, with the set written out literally. | Task 1 |
| 7 | P2 unconditional margin division | Missing or zero revenue gives a claimless `OPERAND_MISSING` line and F2 `UNRESOLVED`. Focused test. | Task 1; Task 3 (`evaluate`) |
| 8 | P2 binder tests missing | Approved successor, unapproved successor, withdrawn/none, symbol mismatch, missing/malformed twin, post-`as_of` approval. | Task 3 |
| 9 | P2 `thesis-impact` still evaluates arbitrary YAML | CLI, evaluator and registry deleted in this slice. Only dependents are the CLI registration and their own tests (F-4). | D3; Task 3 |
| 10 | P3 no-thesis contract | One section-level contract: `UNRESOLVED: no approved thesis.` | Design; D4 |
| 11 | P3 citations | ETR branch `run_traces.py:389-393`; supersession `0014_ledger_review_fixes.sql:9-18`. | F-6; F-8 |
| note | Disposition beside the predicate model | Moved to `thesis_predicates.py`. | Task 3 |

**Partial disagreement on #2's mechanism:** the ruling asks for the "existing ledger path (draft →
claim check → panel approval)". No such path can carry a thesis.
- A submitted version may not hold import sources or self-cited `POLICY` claims
  (`0014:104-110`), so it can carry neither a predicate twin nor a threshold without an owner
  `SET_POLICY`.
- The import is one-shot and creates only root versions (`importer.py:223`, `0012:11`).
- Task 4 is therefore the smallest compliant path: it reuses the import mapping, `IMPORT_SEAL`,
  the panel `IMPORTED_APPROVAL` and the evidence rule.

**New finding not raised by r1 (D8):** the approved data spec assigns "PBT margin" to headline PBT
(`:171`), while the thesis's F2 used PBT before associates. This is surfaced for Sol to rule in
Task 6. The recommendation is to keep the thesis definition, labelled explicitly.

## Review response (r3)

| # | Finding (gpt-6.1-sol r2) | Change | Plan section |
|---|---|---|---|
| 1 | P1 failed successor evidence strands the chain | Confirmed (`importer.py:187,237-245`; `0014:104-114`). Evidence is computed before any write; `None` refuses with nothing persisted. Test: invalid evidence → no rows, Q0 still head; corrected evidence → success. | F-5; Task 4 |
| 2 | P2 duplicate successor import not refused | Confirmed. Inside the persistence transaction, under `_LOCK` on the pinned predecessor: refuse unless it is the `APPROVED` head, and refuse a twin sha256 already imported on the report. Test: retry refuses, row counts unchanged. | Task 4 |
| 3 | P2 `test_prep5_rework.py:363` carried set includes `thesis.F*` | Confirmed. Expected carried = non-derived claim keys − rerun; derived keys in neither set. | Task 3 (rework tests) |
| 4 | P2 `check-live` before `0042` fails | Confirmed (`live_check.py:46-49`, exact equality). Preflight runs `check-live --migrations-dir` on a scratchpad copy without `0042` (exactly `0001`–`0041` with matching digests), then digests, migrate, digests compare, normal `check-live`. No product code. | Task 6 step 5 |
| note | Stale Task 5 reference | D6 now points to Task 4 for the successor importer. | D6 |
| note | Task 6 computes only filed-tax rate | Step 1 computes filed tax ÷ PBT and the threshold recipe only; no PBT − PAT. | Task 6 |
| note | Successor-F5 integration assertion | Task 4 test: successor's `filed_effective_tax_rate_pct` evaluates on the `ETR_LABEL` claim (not `UNRESOLVED`) and `thesis.F5` cites the successor's row and digest. | Task 4 |

No disagreements.
