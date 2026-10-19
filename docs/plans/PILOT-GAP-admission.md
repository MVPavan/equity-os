# PILOT-GAP-admission Implementation Plan — fact admission on the pilot run path

**Origin:** bead `eqos-4j2.24` (P1, parent `eqos-4j2`), raised by the PREP-4 matrix review r1
(Sol, 2026-10-18) as a pilot blocker. Source-of-truth matrix
(`docs/blueprint/source-of-truth-matrix.md`) Gap 2 and the "Facts and canonical selections" row
(writer: "`fundamentals run` (`CANDIDATE`, then `select_canonical`)"). Data spec
(`docs/specs/2026-10-11-canonical-financial-data-and-cross-source-comparison.md`) §4 "Boundary
with the fact store" (:432–440), §5 queue overlay (:600), Stage 2 criteria (:894–901).
Status: **approved — gpt-6.1-sol APPROVE, 2026-10-19** (r1 REQUEST_CHANGES 3 P1/5 P2/1 P3 → r2 REQUEST_CHANGES
→ r3 APPROVE; fresh closing REQUEST_CHANGES 2 P1/4 P2 → REQUEST_CHANGES 2 P2 → APPROVE). Tasks 2–3 blocked on
`eqos-4j2.33`; lands after PILOT-GAP-memory.
**Goal:** on the PostgreSQL run path, the facts a ledger draft cites enter the fact store only
through `admit_run` over a named comparison run of the quarter's frozen package, are then
selected, and the pipeline itself writes and selects no fact. A refused required cell fails the
run closed.
**Out of scope:**
- The SQLite/diagnostic path (`run_command` non-`PgFactStore` branch, matrix Gap 5/6): unchanged.
- Producing the pilot quarters' comparison runs inside `fundamentals run` (Decision 2).
- Qualification evidence for the six required roles: bead `eqos-4j2.33`, plan
  `docs/plans/PILOT-GAP-alignment.md` (Prerequisite below).
- Vendor corroboration (PILOT-2), citation-kind contract (`eqos-4j2.27`), clock bug (`eqos-4j2.23`).
- Register or matrix edits (matrix Gap 2 is updated by the orchestrator at closure, not here).
**Constraints:** every task leaves `uv run pytest tests/fundamentals`, `uv run mypy --strict src`,
`uv run ruff check src tests/fundamentals` and `uv run ruff format --check src tests/fundamentals`
green; PG tests only on `eqos_test_*` databases; no new migration (0011 `fact_admissions` exists;
`key_digest` is a query projection, Decision 6); migrations 0001–0040 immutable; admission's §4
rule (`_decide`) is not weakened; owner 2026-10-14 minimal-code rule.

## Findings (verified in code)

1. **`admit_run` has no production caller.** Only references outside `evidence/admission.py`
   are the retention hold join (`retention/holds.py:42`), migrations 0011/0027/0028 and
   `tests/fundamentals/test_admission.py` (`src/`, `migrations/`, `scripts/` searched).
2. **The run writes and selects facts itself.** `api/pipeline.py:428–475` plans one XBRL write
   per role (`make_canonical=True`) and a PDF confirm write; step 10 (`:540–575`) calls
   `store.put` (:546) and `store.select_canonical` (:558) with the process-clock `decision_time`.
   `api/cli.py:344–353` takes `result.stored_revisions` that are `CANONICAL` as the draft's
   `facts`, keyed by `revision_family.split(":")[1]` (the role value).
3. **`skip_roles` already renders without storing.** `pipeline.py:447`: a role in `skip_roles`
   is rendered, never stored or selected (built for PREP-5 carried roles, `cli.py:342`). Passing
   every role stops all pipeline fact writes with no pipeline change.
4. **`admit_run` needs a stored comparison run.** `admission.py:127` reads `RunStore.read_results
   (run_id)` and the run's first-party interpretations/occurrences; the decision is `_decide`
   (:314): `REPORTED` only, `AGREE` or single-representation `NOT_APPLICABLE` (anything else,
   incl. `AGREE_UNQUALIFIED`, is `EXTRACTION_NOT_AGREE`, :327–328), no open non-diagnostic HIGH
   (:329–330), DIRECT interpretation (XBRL preferred, :336), known knowledge time (:340–341). It writes
   `CANDIDATE` rows and `fact_admissions` atomically and idempotently (:181, `ON CONFLICT … DO
   NOTHING`, :62; `insert_revision` reuses an identical row, `store/pg_fact_store.py:138–151`).
   It never selects; `select_admitted` (:249) is separate and needs `expected_selection_id`.
   Refusals are `(row_id, AdmissionRefusal)` pairs (:157).
5. **`fundamentals run` has no comparison-run input.** Its PG branch (`cli.py:285–360`) never
   touches `compare/`; `compare run` is a separate command (`api/compare_cli.py:136–145`). A run
   manifest carries `scope` (entity ids, period ends, bases), `cutoff`, `mode`, `pinned`,
   `status` (`compare/run_models.py:112–126`, :196–209); `RunStore.read_manifest`
   (`compare/run_store.py:360`).
6. **`AdmissionRecord` does not carry its key.** It has `result_id`, `ref`, `handle`
   (`admission.py:90–102`); `_RECORD` (:64) reads only `fact_admissions`.
7. **The ledger cannot resolve an admitted fact today.** `ledger/citations.py:310` `_fact`
   handles legacy and native facts; `_native_key` (:361–370) requires the observation's entity
   to be `(nse-symbol, <symbol>)` and maps the concept through `LEGACY_CONCEPTS`. An admitted fact
   has concept `eqos:<canonical_id>`, scheme `eqos-reporting-entity`, entity id `str(entity_id)`
   (`admission.py:47–49`, :345–361), so the claim is unresolved and `check_version` fails the
   draft (`ledger/run_draft.py:282–295`; `PASSING` is `MATCH`/`MATCH_UNTRUSTED`,
   `ledger/lifecycle.py:104`).
8. **Claim keys already use canonical ids.** `run_draft._results` (:392–407) keys each required
   role's claim with `measurement_key(LEGACY_CONCEPTS[concept], unit, entity_id, start, end)`
   (`ledger/import_mapping.py:351`) — the key an admitted row of the quarter's comparison run
   carries for `REQUIRED_ROLES` (`output/earnings_update.py:52–58`).
9. **Selection time must precede the derivation cutoff.** The draft is checked `AS_KNOWN` at
   `update.derivation_cutoff` (`run_draft.py:274`, :282–295), set after step 10
   (`pipeline.py:575`); the citation's times include `SELECTED` (`citations.py:338`).
   `before_commit` runs before step 10 (`pipeline.py:538`).
10. **`before_commit` today:** `check_head` + rework gate (`cli.py:327–334`), then
    `bind_computed` (:335), which closes the rework carry (`ledger/run_traces.py:393`) and stores
    calculation traces. `test_prep2b_run_draft.py:208` pins that an unbindable comparator refuses
    before any fact or selection is stored.
11. **(r1 F1) Comparison eligibility binds capture time, not only publication.**
    `FilingPackage.eligible` (`contracts/evidence.py:252–259`) needs every member's
    `capture.first_seen_at <= boundary.first_seen_cutoff`; the engine builds the boundary from the
    request cutoff (`compare/engine.py:144–145`; data spec :400–407). `RETROSPECTIVE` relaxes
    only interpretation recording time. The pilot's four packages were captured after their
    source cutoffs (pilot manifest `quarters.*.source_cutoff`), so a comparison run at a source
    cutoff sees no package in either mode.
12. **(r1 F2) Six-role admission fails today — prerequisite `eqos-4j2.33`.** Qualification (`compare/tables.py:603–607`)
    is `AGREE` only when both sides are `EQUIVALENCE_DEMONSTRATED` in scope or both are aligned by
    a holding filing-specific proof (`evidence/derived.py:101–117`, :358–370; `evidence/alignment.py:155–233`).
    PDF layout entries default to `EQUIVALENCE_UNPROVEN` (`config/mappings/pdf/v1/results_layout.yaml:12`)
    and D3 scope evidence needs five companies (`contracts/qualification.py:188–200`), so for Apar
    only an alignment proof qualifies a reported cell.
13. **(r1 F3) Units.** An admitted observation is base INR, scale 1 (`admission.py:345–361`, `"scale": 1` at :360;
    PAT `2517000000`, `test_admission.py:159`); the claim is INR crore, scale 10^7
    (`ledger/claim_check.py:37–41`, `ledger/import_mapping.py:390`). `_fact` returns the
    observation's value, unit and scale unchanged (`citations.py:325–334`); `_claim_scaled`
    (:456) is used only by the run-store branches (:389, :409, :447). `check_claim` compares
    `(value_kind, unit, currency, scale)` skipping `None` fields (`claim_check.py:95–98`, :124–128).
14. **(r1 F8) Pins.** `compare run` defaults dictionary/mapping set to `v1`
    (`api/compare_cli.py:143–144`, `contracts/config_versions.py:10`) and passes only those two
    (`compare_cli.py:260`); `alignment_rules` is a `ConfigVersions` field (:24) with no flag.
    `evidence ingest` hard-pins dictionary and mapping set `v1` (`api/evidence_cli.py:54–55`,
    :132–134). The pilot needs dictionary `v2`, mapping set `v5` (`test_prep2b_run_draft.py:82–90`;
    v5 maps the 2026 in-capmkt taxonomy for Q4 FY26/Q1 FY27, `config/mappings/v5.yaml:1–2`).
    Selection reads only interpretations under the run's pins (`evidence/selection.py:145–149`).
    The test `Ingest.run` defaults PDF specs to the Q2 layout (`tests/fundamentals/evidence_support.py:151`);
    Q4 FY26 needs the `-pg` config's unit-marker override (`config/aparinds-fy26-q4-pg.yaml:64–70`).
15. **The run already knows its frozen inputs.** `cli.py:297–300` builds `xbrl` (own XBRL sha +
    comparators) and `pdfs` (results, transcript sha) from the prepared, hash-checked inputs;
    a `CaptureReference` carries `source_id` and `blob_sha256` (`contracts/evidence.py:195–204`);
    the declared sources are `config.xbrl.source_id` and `config.results_pdf.source_id`
    (`cli.py:235`, :244).
16. **(r2 F5) The PDF member is otherwise unbound.** `_decide` admits the XBRL interpretation when
    both are DIRECT (`admission.py:336`), so a check on the admitted occurrence alone never sees
    the PDF that corroborated it. The run records each package it read as a `PACKAGE` input,
    `SELECTED` when chosen (`compare/resolve.py:233–246`; `RunInputKind.PACKAGE`,
    `RunInputDisposition`, `compare/run_models.py:75–98`), returned by `read_manifest().inputs`
    (`run_store.py:366–375`). `EvidenceRepository.get_packages` (`evidence/repository.py:554`)
    returns `FilingPackage`s whose `members` map `Representation` → `PackageMember` with
    `capture` (`source_id`, `blob_sha256`), `knowledge_time` and `knowledge_time_status`
    (`contracts/evidence.py:207–259`).
17. **(r2 F7) `admit_run` is one transaction and admits every eligible row.** Its loop, including
    each `insert_revision` (`admission.py:173`), runs inside `run_serializable`
    (`admission.py:186`; `store/pg_fact_store.py:163–176`), so an interruption anywhere inside it
    rolls everything back. It admits every eligible result row, not only the six required roles.
18. **(closing r1 F1) The binder reads only onboarding-pinned interpretations.** `RUN_CONTEXT`
    (`ledger/run_traces.py:87–92`) is `ONBOARDING_VERSIONS` (dictionary `v2`, mapping set `v5`,
    `contracts/onboarding.py:80`) plus the normalisation policy and XBRL extractor; `_Binder.operand`
    keeps only interpretations with `_context(item) == RUN_CONTEXT` (:155) and raises "no single
    mapped interpretation" otherwise (:160–161). `bind_computed` (:288) has one caller,
    `cli.py:335`. The pilot fixture ingests every run and comparator XBRL (`prep2b_support.py:63–72`,
    :117–118) under mapping set `v5` (`test_prep2b_run_draft.py:86–89`, imported by
    `test_prep3_resume.py:30` and `test_prep5_rework.py:46`). Under `v6` ingestion it would refuse.
19. **(closing r1 F2) A rework carries the head's fact citations verbatim.** `write_run_draft`
    replaces each carried key's claim with the head's (`run_draft.py:248–252`), and `cli.py:338–342`
    skips carried roles. A head written before this bead cites run-written native rows, which the
    kept native branch (Decision 7, OQ4) still resolves `MATCH`.
20. **(closing r1 F3) No version names its comparison run today.** `VersionDraft.pinned_run_ids`
    (`contracts/ledger.py:210`) is sealed (`0012_report_ledger.sql:22`, digest :235) and
    round-tripped (`ledger/store.py:99`, :140), but `write_run_draft` leaves it empty
    (`run_draft.py:268–278`). `fact_admissions` is unique per `(store_id, result_id,
    interpretation_id)` (`0011`:16) and `insert_revision` reuses an identical row
    (`pg_fact_store.py:145–147`), so two comparison runs can admit the same fact row. A citation
    cannot carry a run id for a fact (`0033_*.sql:9`: `run_id` needs `interpretation_id`).
    `check_version` reads the version (`ledger/lifecycle.py:251`) and is the only caller of
    `resolve_citation` (:260).
21. **(closing r1 F4) The admission's store-clock time.** `fact_admissions.overlay_position`
    (`0011`:14) is `eqos.store_now()` at admission (`admission.py:149`). `check_claim` holds every
    resolved time against the cutoff; `RECORDED`/`SELECTED` count in `AS_KNOWN` only
    (`claim_check.py:30`, :89–94). A row first written and selected at T1 and admitted at T2
    would otherwise pass at a cutoff between them.
22. **(closing r1 F5) PREP-5 spies the old writer.** `test_prep5_rework.py:389`, :404–424 spy
    `PgFactStore.put`/`select_canonical`; :524–525 and :868 assert on them; the table counts
    (:390–397, :485) omit `fact_admissions`.
23. **(closing r1 F6) A content-checked pin helper exists.** `require_pins`
    (`compare/run_config.py:262–289`) compares every pin in `_PIN_FIELDS` (:127–137: dictionary,
    formula set, mapping set, normalisation, both extractors, rounding, comparison policy,
    alignment rules) plus the definition set and comparison semantics, by content hash, against a
    `load_run_config(config_root, versions)` (:194); `compare/run.py:287–295` uses the pair the same
    way. The `compare run` config root defaults to `config` (`compare_cli.py:94`, :142).

## Decisions

1. **`fundamentals run` gains `--compare-run <id>`, required on the PostgreSQL path.** Missing →
   `RunDraftError` before any write. The SQLite path ignores it.
2. **The run does not create the comparison run.** The pilot runs `evidence ingest` and
   `compare run` per quarter first (production sequence in Task 3).
3. **The pipeline writes no fact on the PG path:** `cli.py` passes `skip_roles=frozenset(FactRole)`.
4. **(r1 F6) Order inside `before_commit`:** `check_head` + rework gate, then `bind_computed`
   (carry closed), **then** admission and selection — still before step 10 and the derivation
   cutoff (Finding 9). Admission steps: (a) **(closing r1 F1)** the manifest and its selected
   package are read and checked (Decision 8) read-only before `run(...)`, so their pins reach
   `bind_computed` (Decision 10);
   (b) `admit_run(run_id, pool=pool, store_id=config.fact_store_id)`; (c) validate the **complete**
   outcome for every non-carried `REQUIRED_ROLES` role — one record whose `key_digest` equals the
   role's claim key, its occurrence's capture a member of the checked package — and
   raise before selecting anything; (d) select each (`select_admitted`, `expected_selection_id`
   = chain head; skipped when the head already targets the row). Reason: `"admitted from
   comparison run {run_id}"`. A refusal at (c) leaves only idempotent `CANDIDATE` rows and
   admissions (never selected; a later admission reuses them) and no version.
5. **A refused required role fails the run:** `RunDraftError` naming the role and its
   `AdmissionRefusal` (or "not in run"). Other rows' refusals are logged once with counts.
6. **`AdmissionRecord` gains `key_digest`**: `_RECORD` joins `eqos.results` on `result_id` and
   projects `results.key_digest`. No migration.
7. **(r1 F3, F4) Citations resolve admitted facts** through one new branch in
   `ledger/citations.py`: a native fact whose concept starts with `ADMITTED_CONCEPT_PREFIX` is
   resolved by `_admitted`, which reads its admission joined to `eqos.results`
   **constrained to the report's `entity_id`** and to the cited row (`fact_admissions.fact_origin,
   fact_origin_id`) — zero rows (an `eqos:` fact without admission, or another issuer's) or more
   than one distinct `(key_digest, value_kind, currency)` → unresolved. It returns
   `value=_claim_scaled(normalized_value, claim)`, `key_digest`, `value_kind` and `currency`
   from `eqos.results` (`0001_evidence.sql:505`, columns `entity_id`, `currency`, `value_kind`,
   `key_digest`), `unit=None`, `scale=None` (the claim's own unit/scale is typed by `_typed`,
   `claim_check.py:124–128`; key digest and value kind bind the rest), times as native facts
   (`KNOWLEDGE`, `FIRST_SEEN` from the admitted occurrence's first-party capture via
   `_first_party_capture`, `SELECTED`, `RECORDED`). `_fact` gains the `claim` argument
   (`citations.py:203`). Legacy and run-written native branches are unchanged (OQ4).
   **(closing r1 F3, F4)** The admission must belong to a run in the citing version's sealed
   `pinned_run_ids` (Decision 11): `resolve_citation` gains `run_ids`, passed by `check_version`
   from `draft.pinned_run_ids` (Finding 20); `_fact` passes it to `_admitted`. `_admitted` also
   returns `(RECORDED, min overlay_position)` over those pinned admissions (Finding 21), so a
   selected row admitted after the cutoff is `POST_CUTOFF` in `AS_KNOWN`.
8. **(r1 F1, F5) The comparison run is bound to the quarter's frozen package, not to its cutoff.**
   The comparison run is `AS_KNOWN` at an honest evaluation boundary after ingestion (`compare
   run`'s default store-clock cutoff, `compare_cli.py:252`); its `cutoff` is not compared with the
   report's historical `source_cutoff`, which stays `config.quarter.knowledge_cutoff`, and real
   capture timestamps are kept. The run checks: `status` `COMPLETE`, `mode` `AS_KNOWN`,
   `scope.entity_ids == (prior.entity_id,)`, the quarter's period end in `scope.period_ends`,
   **(closing r1 F6)** `require_pins(load_run_config(Path("config"), PILOT_VERSIONS),
   manifest.pinned)` (Finding 23): every prescribed pin (Task 3), by content, where
   `PILOT_VERSIONS = ConfigVersions(dictionary="v2", mapping_set="v6", alignment_rules="v2")` is a
   `cli.py` constant (other fields `v1`). **(r2 F5)
   Package:** of the manifest's `SELECTED` `PACKAGE` inputs, `get_packages` must yield exactly one
   for the quarter's entity, period end and basis (Finding 16), and it must have both members:
   XBRL `capture.source_id == config.xbrl.source_id` and `blob_sha256 == xbrl[0]`; PDF
   `capture.source_id == config.results_pdf.source_id` and `blob_sha256 == pdfs[0]` (Finding 15;
   the PREP-7 consumer contract, `docs/plans/PREP-7.md:281–285`); each member
   `knowledge_time_status` `KNOWN` and `knowledge_time <= config.quarter.knowledge_cutoff`, and the
   package `knowledge_time` likewise (published before the historical cutoff). Each required
   role's admitted occurrence capture must be one of these two members (Decision 4c). Any failure
   → `RunDraftError` before selection. Comparison eligibility itself is unchanged
   (changing it would be a contract change).
9. **No value cross-check guard in the run:** a rendered value that differs from the admitted
   value fails `check_version` (`run_draft.py:282–295`).
10. **(closing r1 F1) The binder takes the run's pins locally.** `bind_computed` gains a required
    `versions: ConfigVersions`; `_Binder` matches `(versions.dictionary, versions.mapping_set,
    versions.normalisation_policy, XBRL_EXTRACTOR_VERSION)` in place of the `RUN_CONTEXT`
    constant, which is removed. `cli.py` passes `ConfigVersions.of(manifest.pinned)`.
    `ONBOARDING_VERSIONS` is unchanged. Comparator XBRLs are ingested under the same pins (Task 3).
11. **(closing r1 F3) The version seals its comparison run.** `RunDraft` gains `run_id: int`;
    `write_run_draft` sets `VersionDraft.pinned_run_ids` to the sorted union of `run.run_id` and,
    on a selective rework, the head's `pinned_run_ids` (`store.read_version(cursor,
    reworked.head)`, under the existing lock), so carried citations keep their binding.
    `Citation` gains nothing (Finding 20).
12. **(closing r1 F2) Carried facts need admission provenance.** In `before_commit`, after
    `check_head`, each carried `fact.*` claim's cited row must have a `fact_admissions` row whose
    `run_id` is in the head's `pinned_run_ids`; otherwise `RunDraftError("version {head} predates
    fact admission; rerun with --full-successor")` before any write. `--full-successor` carries
    nothing, so it admits all six. Sealed historical versions keep resolving through the
    unchanged native branch.

## Assumptions

- A1. After `eqos-4j2.33`, each pilot quarter's comparison run under the prescribed pins yields
  `AGREE` with no open HIGH for all six `REQUIRED_ROLES` keys. That bead's acceptance proves it.
- A2. Admitted value / `claim.scale` equals the rendered claim at display precision. Proven by
  Task 1's unit tests and Task 3's e2e.
- A3. The pilot store `sqlite-cb02b0f12a1708d0` is `OPEN` and accepts native `insert_revision`
  rows, as the pipeline's `PgFactStore.put` already writes there (`cli.py:271`).
- A4. A rework or rerun re-admits idempotently (Finding 4); re-selection is skipped when the head
  already targets the admitted row.

## Open questions (Sol r1 rulings)

1. Who selects — **the run** (Decision 4, approved).
2. `--compare-run` — **required** on PG (approved).
3. `RETROSPECTIVE` comparison at the source cutoff — **rejected**; replaced by Decision 8.
4. Keep the native run-written branch of `_native_key` — **keep** (approved).
5. Admit the PDF confirm row — **no**; corroboration stays bound to the package (approved).

## File map

| File | Change | Task |
|---|---|---|
| `src/fundamentals/evidence/admission.py` | `AdmissionRecord.key_digest`; `_RECORD` joins `eqos.results` | 1 |
| `src/fundamentals/ledger/citations.py` | `_admitted` branch (pinned runs, `RECORDED` admission time); `_fact(…, claim, run_ids)`; `resolve_citation(…, run_ids)` | 1 |
| `src/fundamentals/ledger/lifecycle.py` (:260) | pass `run_ids=draft.pinned_run_ids` | 1 |
| `tests/fundamentals/test_admission.py` | `key_digest` assert; citation unit tests (currency + EPS positive, wrong value, cross-issuer, `eqos:` fact without admission, admission-time cutoff, two runs sharing a row) | 1 |
| `src/fundamentals/ledger/run_traces.py` | `bind_computed(…, versions)`; `RUN_CONTEXT` removed | 2 |
| `src/fundamentals/ledger/run_draft.py` | `RunDraft.run_id`; `pinned_run_ids` union with the rework head's | 2 |
| `src/fundamentals/api/cli_parser.py` (`run` args, beside `--full-successor` :99) | `--compare-run` (int) | 2 |
| `src/fundamentals/api/cli.py` | PG branch: `PILOT_VERSIONS`; manifest + `require_pins` + selected-package check (both members) before `run`; carried-fact provenance check; `versions` to `bind_computed`; `skip_roles=all`, admit/validate/select after `bind_computed`; `facts` from records; `run_id` | 2 |
| `src/fundamentals/api/evidence_cli.py` | `--dictionary`, `--mapping-set` (default `v1`, as `compare run`) | 2 |
| `tests/fundamentals/prep2b_support.py` | `Pilot`: PDF ingest with per-quarter specs, `compare run` per quarter, `--compare-run` in `run` **and** `registered` argv | 3 |
| `tests/fundamentals/test_prep2b_run_draft.py` | e2e host (Task 3 tests 1–7); :86–89 fixture → mapping set `v6`; :557 `assert revisions` → admitted selections canonical | 3 |
| `tests/fundamentals/test_prep2b_traces.py` | :145, :168, :176, :187, :213 `bind_computed` calls pass the fixture's existing v2/v5 configuration explicitly via the new required `versions`; its v5 fixture stays | 2–3 |
| `tests/fundamentals/test_prep3_resume.py` | :336 boundaries → inner-rollback, after-`admit_run` and selection boundaries; :309 `stored_revisions` → admission records | 3 |
| `tests/fundamentals/test_prep5_rework.py` | :435 via `registered()`; spies and assertions migrated to admission + selection; `fact_admissions` in `TABLES`; transition regression | 3 |

**Overlap with `eqos-4j2.25` (memory) — verified against `docs/plans/PILOT-GAP-memory.md:145–158`:**
the only shared code is the `RunDraft(...)` call at `src/fundamentals/api/cli.py:344` (memory
Task 2 adds `memory=` to it; this plan changes `facts=`). Every other file is disjoint. **Settled
(r2 F9):** the two land in sequence, **memory first** (orchestrator ruling 2026-10-19: admission is blocked on `eqos-4j2.33`); admission adapts to the `RunDraft(...)` call memory leaves.

## Size estimate (inference, not measured)

- **This bead, `src/`:** ~105–130 lines (r3: ~80–100) — admission ~4, citations ~32
  (`_admitted` + SQL, pinned runs, admission time), lifecycle ~1, run_traces ~6 (versions
  replace `RUN_CONTEXT`), run_draft ~8 (`run_id`, pin union), cli ~65 (constant, `require_pins`,
  manifest and two-member package check, carried-provenance check, admit/validate/select,
  facts), parser ~2, evidence_cli ~4.
- **This bead, tests:** ~230–310 lines (r3: ~170–240) — citation unit tests ~70 (+ cutoff,
  two-run), harness (PDF + comparator ingest + compare run per quarter) ~55, e2e ~110 (+ one-pin
  drift, documented sequence), migrated resume/draft tests ~30, PREP-5 migration + transition
  regression ~35.
- Qualification config and `compare run --alignment-rules` are sized in `eqos-4j2.33`'s plan.
- PG suite runtime rises by one PDF ingest + one comparison run per pilot quarter per test.

## Tasks

### Prerequisite — `eqos-4j2.33` (PILOT-GAP-alignment, separate plan)

Qualification evidence for the six required roles moved to `docs/plans/PILOT-GAP-alignment.md`
under bead `eqos-4j2.33` (r2 ruling); it also owns the pins Task 3 uses and
`compare run --alignment-rules`. **Its acceptance, which Tasks 2–3 require:** in all four pilot
quarters PQ0–PQ3, all six `REQUIRED_ROLES` keys are `AGREE` and `admit_run` admits all six. It
never changes `_decide`, `_qualified` or a frozen manifest. Task 1 does not depend on it.

### Task 1 — admitted facts are addressable and citable (Opus)

- **Files:** `evidence/admission.py`, `ledger/citations.py`, `ledger/lifecycle.py`,
  `tests/fundamentals/test_admission.py`.
- **Interfaces.** Produces: `AdmissionRecord.key_digest: str`; `resolve_citation` returns a
  `ResolvedCitation` for a `FIGURE` citing an admitted fact of the report's entity (Decision 7).
- **Tests** (`pg`, on the existing Q2 admission fixture, `test_admission.py:78–86`):
  `key_digest == row.key.digest()` on a record; a claim citing the admitted PAT (INR crore,
  `251.70`) and EPS (INR per share, `62.66`) resolves `MATCH`; the same claim with a wrong value
  is `VALUE_MISMATCH`; the citation under another report entity is `UNRESOLVED`; an `eqos:`
  native row with no admission is `UNRESOLVED`. **(closing r1 F4)** a row inserted and selected
  at T1 (direct selection or an earlier unpinned admission — not `select_admitted`, which requires
  an existing admission, `admission.py:259`) then admitted at T2 (`admit_run` reuses it): the
  claim is `POST_CUTOFF` `AS_KNOWN` at a boundary in (T1, T2) and `MATCH` after T2. **(closing
  r1 F3)** two comparison runs R1, R2 admitting the same row: resolution with `run_ids=(R1,)`
  uses R1's admission time; with `run_ids` naming neither → `UNRESOLVED`; with both pinned, the earliest admission is
  taken only over the cited row and its eligible pinned admissions. Existing citation tests
  stay green (legacy/native).
- **Verify:** `uv run pytest tests/fundamentals/test_admission.py tests/fundamentals/test_prep2b_citations.py -q`;
  `uv run mypy --strict src`; `uv run ruff check src tests/fundamentals`.
- **Risk:** low–medium; `_fact` is shared by every ledger check.

### Task 2 — the PG run admits and selects instead of writing (Opus; blocked by `eqos-4j2.33`)

- **Files:** `api/cli.py`, `api/cli_parser.py`, `api/evidence_cli.py`, `ledger/run_traces.py`,
  `ledger/run_draft.py`.
- **Interfaces.** Consumes: `--compare-run`, `RunStore(pool).read_manifest`, `admit_run`,
  `select_admitted`, `EvidenceRepository.get_packages`/`get_occurrences`, `PgFactStore` chain head, the claim
  key (`measurement_key` + `LEGACY_CONCEPTS`, as `_results`). Produces: `RunDraft.facts =
  {role.value: record.ref}`; `RunDraftError` on missing flag, manifest/pin/package/knowledge-time
  mismatch (Decision 8, all pins via `require_pins`), a carried fact without pinned admission
  (Decision 12) or a refused required role (Decision 5); `bind_computed(…, versions=…)`
  (Decision 10); `pinned_run_ids` sealed (Decision 11); pipeline called with
  `skip_roles=frozenset(FactRole)`; order per Decision 4. `evidence ingest --dictionary
  --mapping-set` (defaults `v1`, unchanged behaviour without the flags).
- **Tests:** in Task 3; lands with Task 3 in one commit (existing PG run tests need the harness).
- **Risk:** medium — rework (`carried` roles neither validated nor selected); store-clock
  selection vs process-clock derivation cutoff (`eqos-4j2.23`).

### Task 3 — pilot harness, migrated tests and e2e (Opus; blocked by `eqos-4j2.33`)

- **Prescribed pins (all four quarters):** the dictionary / mapping set / alignment versions
  `eqos-4j2.33` ships (proposed there: `v2` / `v6` / `v2`; the sequence below uses those);
  normalisation/rounding/definition/comparison policies `v1`.
- **Production sequence per quarter:** `fundamentals evidence ingest --retrieval-manifest …
  --issuer APARINDS --quarter <Q> --period-end <end> --basis consolidated --member xbrl=<kind>
  --member pdf=<kind> --issuer-config config/aparinds-<q>.yaml` (Q4 FY26:
  `aparinds-fy26-q4-pg.yaml`) `--dictionary v2 --mapping-set v6`; each comparator XBRL the run
  reads (`prep2b_support.py:68–71` rows) is ingested once with `--member xbrl=<comparator kind>`
  under the same pins; then `fundamentals compare run
  --entity APARINDS --period-end <end> --basis consolidated --dictionary v2 --mapping-set v6
  --alignment-rules v2` (AS_KNOWN, store-clock cutoff); then `fundamentals run … --compare-run
  <id>`.
- **Harness:** `Pilot` ingests the results PDF per quarter with `specs_from_config` of that
  quarter's `pdf_parse` (`evidence_support.py:56`; not the Q2 default at :151), runs the
  comparison (`Pilot.compare_run(quarter) -> int`) and adds `--compare-run` in the one argv path
  shared by `Pilot.run` and `Pilot.registered`. The shared `mapping_set` fixture
  (`test_prep2b_run_draft.py:86–89`) moves to `v6`, so no `v5` interpretation exists.
- **Tests (`pg`, `retained`):**
  1. Each of the four quarters: the draft's six `fact.*` claims cite admitted facts — each cited
     row has a `fact_admissions` row naming the run's comparison run, is the current selection,
     the draft validates `AS_KNOWN` all `MATCH`; no non-`admitted:` fact family is written by the
     run.
  2. Open non-diagnostic HIGH on PAT → `RunDraftError` naming `profit_for_period` / `OPEN_HIGH`;
     no version, no selection.
  3. **(r2 F5) PDF replaced, XBRL kept:** the quarter's package keeps the run's XBRL capture but
     its results-PDF member is a different capture (another sha, or one published after the
     source cutoff) → `RunDraftError` naming the PDF member before admission; no selection, no
     version.
  4. Same quarter, different XBRL (the package's XBRL is not `xbrl[0]`) → refused likewise.
  5. PG run without `--compare-run` → `RunDraftError`, nothing written.
  6. **(closing r1 F6)** A comparison run whose pins differ from `PILOT_VERSIONS` only in
     `rounding_policy` (a test-local `v2` copy under a temporary config root) → `RunDraftError`
     (`VersionContentDriftError`) before any write.
  7. **(closing r1 F1)** Test 1 runs the documented sequence on a fresh pilot database with
     every XBRL ingested only under `v6`; the draft's computed lines bind.
- **Migrated tests (assertions keep their intent):**
  - **(r2 F7)** `test_prep3_resume.py:333–337` boundaries move from
    `PgFactStore.put`/`select_canonical` to three (Finding 17): (i) **inner rollback** —
    interrupt after `fundamentals.evidence.admission.insert_revision` (inside `admit_run`'s
    transaction): no fact row, admission or selection is committed; (ii) **committed admission**
    — interrupt after `admit_run` returns (the name `cli.py` calls): every committed fact row is
    a candidate named by a `fact_admissions` row of the comparison run, no selection; (iii)
    **selection** — interrupt after the first `select_admitted`. Each retry completes with
    identical counts (idempotence). :309 compares **all** committed candidate rows with the
    retry's admission records (not with the six cited); separately, the version's six required
    citations are admitted rows and their current selections.
  - `test_prep2b_run_draft.py:557–562` checks the cited admitted rows are canonical instead of
    `stored_revisions`; :208 stays green unchanged (bind fails before admission, Decision 4).
  - **(closing r2 F2)** `test_prep2b_run_draft.py:573` passes that version's `pinned_run_ids` as
    `run_ids` to `resolve_citation` (`Pilot.sources()` supplies none, so admitted facts would be
    `UNRESOLVED`); its POST_CUTOFF assertion at :583 stays.
  - `test_prep3_resume.py:377` and `test_prep5_rework.py:435` get `--compare-run` through
    `registered()`.
  - **(closing r1 F5)** `test_prep5_rework.py`: `WRITES` spies `admit_run` and `select_admitted`
    (recording admitted/selected families) in place of `put`/`select_canonical`; `TABLES` adds
    `fact_admissions`. :524–525 → no fact row or admission is new (same comparison run), the
    revenue fact cites an admitted row of a pinned run and no carried fact is reselected; :868
    and the guidance-only test → no new fact rows, admissions or selections. Carried claims
    unchanged (:527–529).
  - **(closing r1 F2) Transition regression** (`test_prep5_rework.py`): a head whose fact
    citations are run-written rows (written with an empty `pinned_run_ids`, as before this
    bead) → selective rework refuses naming `--full-successor`, nothing written; the
    `--full-successor` rerun succeeds with six admitted citations; the old head still validates.
- **Verify:** `uv run pytest tests/fundamentals -m pg -q`; then the full gate (Constraints) and
  `scripts/verify_project.sh` (expect `0 failed`).
- **Risk:** medium — harness runtime; `eqos-4j2.33` must have proven A1 first.

## Interactions with open beads

- `eqos-4j2.33` (PILOT-GAP-alignment) — prerequisite; blocks Tasks 2–3.
- `eqos-4j2.25` (memory writer) — shares only the `RunDraft(...)` call at `cli.py:344`; lands
  before this bead (memory first, 2026-10-19 ruling); admission adapts to its `RunDraft(...)` call.
- `eqos-4j2.8` (pilot test, assisted updates Q1–Q3) — uses this plan's production sequence and
  `Pilot` helper.
- `eqos-4j2.23` (derivation cutoff on process clock, recording on store clock) — admitted
  selections are stamped by the store clock; skew could put `SELECTED` after the derivation
  cutoff. Same class as the bug; not fixed here.
- `eqos-4j2.27` (PILOT-4 citation contract) — results claims now cite fact ids; comparator/tax
  figures stay interpretation-backed.
- `eqos-4j2.22` (legacy-origin impersonation) — unaffected; admitted rows are `pg-native`.
- Matrix Gap 2 and the facts row's writer cell — update at closure (orchestrator).

## Not verified

- Live pilot store state of `sqlite-cb02b0f12a1708d0` (A3).
- `tests/` was not searched recursively; other callers of `Pilot.run`/`registered` may need the
  argv change (the shared path covers them).

## r1 findings → resolution

| # | Sev | Finding | Resolution |
|---|---|---|---|
| 1 | P1 | Comparison cutoff cannot admit post-cutoff captures | Finding 11; Decision 8: AS_KNOWN comparison at an honest post-ingestion cutoff; historical `source_cutoff` stays on the report; admitted knowledge time ≤ source cutoff; eligibility unchanged; OQ3 withdrawn. |
| 2 | P1 | Q2 PBT `AGREE_UNQUALIFIED`; six-role admission per quarter unproven | Finding 12; Task 0 (separate prerequisite bead; since r2 `eqos-4j2.33`) with cause, per-quarter analysis, recommended versioned evidence (pdf/v2, alignment/v2, mapping v6, `--alignment-rules`) and acceptance; Tasks 2–3 blocked by it; `_decide` untouched. |
| 3 | P1 | Admitted-fact citation lacks scale/unit handling | Finding 13; Decision 7: `_claim_scaled`, `value_kind`/`currency` from `eqos.results`, `unit`/`scale` `None`; legacy/native unchanged; Task 1 tests currency + EPS positive, wrong-value negative. |
| 4 | P2 | Digest lookup doesn't bind issuer | Decision 7: admission joined to `eqos.results` constrained to the report entity and the cited row; Task 1 tests cross-issuer and `eqos:` without admission. |
| 5 | P2 | Quarter metadata doesn't bind the frozen package | Finding 15; Decision 8: admitted occurrence capture sha/source must be the run's own XBRL/results PDF; Task 3 test 3. |
| 6 | P2 | Admission before binding/gate closure | Finding 10; Decision 4: gate + `bind_computed` first, then admit, validate all required roles, then select; :208 regression kept. |
| 7 | P2 | Existing tests won't stay meaningful | File map + Task 3 "Migrated tests": resume boundaries moved to admission/selection with before/after-commit interruption and retry idempotence; :309/:557 rewritten; `registered()` argv; missing-flag test. |
| 8 | P2 | No executable pin/config contract | Finding 14; Task 3 prescribed pins, production sequence, per-quarter PDF specs incl. Q4 `-pg`; `evidence ingest` pin flags (Task 2); all four quarters in test 1. |
| 9 | P3 | Sibling overlap claim wrong | Verified against the memory plan's file map: only `api/cli.py` is shared (memory Task 2 also edits the `RunDraft` construction); `prep2b_support.py` is not. `key_digest` is a projection via `fact_admissions.result_id`, no migration (Decision 6). |

## r2 findings → resolution

| # | Sev | Finding | Resolution |
|---|---|---|---|
| 5 | P1 | Corroborating PDF unbound; a different or post-cutoff same-quarter PDF passes | Finding 16; Decision 8: the run's one `SELECTED` package, via `EvidenceRepository.get_packages`, must have both members matching the declared XBRL and results-PDF source ids and hashes, each published (and the package) at or before the historical cutoff; each admitted occurrence must be a member; Task 3 test 3 keeps the XBRL and replaces only the PDF. |
| 2 | P2 | Task 0 understates the refusal set | Moved out by ruling: `eqos-4j2.33`, `docs/plans/PILOT-GAP-alignment.md`; this plan keeps the prerequisite and its acceptance (six roles `AGREE` and admitted, PQ0–PQ3); Tasks 2–3 blocked by it; size estimate updated. |
| 7 | P2 | Resume boundary inside `admit_run`'s transaction; all-eligible admission breaks :309 | Finding 17; Task 3 migrated tests: inner-rollback case kept, committed case interrupts after `admit_run` returns, all committed candidates compared with admission records, six citations/selections checked separately. |
| 9 | P3 | Overlap with memory plan | Closed by Sol; settled: only the `RunDraft(...)` call at `cli.py:344` is shared; memory lands first (admission blocked on `eqos-4j2.33`), admission second. |

## closing r1 findings → resolution

| # | Sev | Finding | Resolution |
|---|---|---|---|
| 1 | P1 | v6 ingestion can't feed `bind_computed` (`RUN_CONTEXT` = onboarding v5) | Finding 18; Decision 10: `bind_computed(…, versions)` from the manifest's pins, read before `run`; `ONBOARDING_VERSIONS` unchanged; comparator XBRLs ingested under v2/v6; fixture → v6; Task 3 test 7. |
| 2 | P1 | Carried facts bypass admission on rework | Finding 19; Decision 12: carried `fact.*` citations need an admission under the head's pinned runs, else refuse naming `--full-successor`; historical reading unchanged; transition regression in Task 3. |
| 3 | P2 | Chosen comparison run never sealed; two runs can admit one row | Finding 20; Decision 11: `RunDraft.run_id` → sealed `pinned_run_ids` (union with the rework head's); Decision 7: `_admitted` resolves only through pinned runs; no `Citation.run_id`; Task 1 two-run test. |
| 4 | P2 | Admission time missing from AS_KNOWN check | Finding 21; Decision 7: `(RECORDED, min overlay_position)` of the pinned admissions; Task 1 before/after-cutoff test. |
| 5 | P2 | PREP-5 assertions spy the old writer | Finding 22; Task 3 migrated tests: spies → `admit_run`/`select_admitted`, `fact_admissions` counted, proofs kept. |
| 6 | P2 | Manifest check misses policy pins | Finding 23; Decision 8: `require_pins` against `load_run_config(config, PILOT_VERSIONS)` (all pins, by content); Task 3 test 6 changes only `rounding_policy`. |

## closing r2 findings → resolution

| # | Sev | Finding | Resolution |
|---|---|---|---|
| 1 | P2 | `test_prep2b_traces.py:145,168,176,187,213` call `bind_computed` without the new `versions` | File map (Tasks 2–3): file added; the five calls pass the fixture's existing v2/v5 configuration explicitly; its v5 fixture stays. |
| 2 | P2 | `test_prep2b_run_draft.py:573` resolves without `run_ids` → `UNRESOLVED`, breaking POST_CUTOFF :583 | Task 3 migrated tests: pass the version's `pinned_run_ids`; :583 assertion kept. |
| n1 | note | Earliest pinned admission: restrict to cited row + eligible pinned admissions; add both-pinned case | Task 1 two-run test gains a both-runs-pinned case. |
| n2 | note | Task 1 fixture uses `select_admitted` before any admission (`admission.py:259`) | Task 1 closing-r1-F4 fixture arranged by direct selection or an earlier unpinned admission. |
