# Extractor v2 (structural Ind AS signal) Implementation Plan

Status: approved — Sol plan review r1 REJECT (6) → r2 REJECT (2) → r3 APPROVE 2026-10-17.

**Origin:** bead `eqos-71x`; D6 [Amendment 2026-10-16 (attempt 2 burn)](D6.md#amendment-2026-10-16-attempt-2-burn-eqos-h410)
option A ("a new bead, its own version advance"), the owner's B-now-A-later choice; D6 Freeze step 6
(later phases may change `IMPL`; the Stage 4 e2e keeps replaying attempt 3 at `HEAD`). It must land
before D7, whose exit onboards a three-member batch through D6 (roadmap D7 stage 2, edge `D7 → D6`).
**Amendment to D6 D3.6:** this phase supersedes D3.6's "no pinned file changes" expectation by taking
its "amendment that advances the version" branch; D3.6 stays as written for D6 itself.
**Goal:** first-party XBRL ingest accepts an explicit, uncontested `IntegratedFinance_IndAS` form
declaration as Ind AS evidence, through one predicate shared by discovery and ingest, under advanced
extractor versions.
**Out of scope:** bulk re-extraction or migration; any edit to a frozen manifest, the holdout record,
`d6-capability.md` or a committed migration; new frameworks; a general taxonomy validator; the Stage 4
manifest oracle (`tests/fundamentals/manifest_support.py:36–40`); `VENDOR_EXTRACTORS` files.
**Constraints:**
- A pinned-source edit advances the version; same version with other content is refused
  (`compare/run_config.py:1–8`, `evidence/repository.py:257–276`).
- Fail closed: no positive, uncontested declaration → rejected, as today.
- `discovery.py` is at 800 lines (cap): no net line added there.
- Migrations 0001–0023 immutable; frozen manifests and `stage4_*.yaml` never edited or opened.
- `mypy --strict`, ruff, frozen Pydantic, structlog; owner code-size rule.

## Findings

**Versions.** A pin hashes its version string with its source files' bytes (`run_config.py:159–191`).
`member_identity.py` and `first_party_extract.py` are in **both** `EXTRACTOR_SOURCES` lists
(`:55–74`), and every run pins both first-party extractors (`load_run_config`, `:224–238`), so both
`XBRL_EXTRACTOR_VERSION` (`xbrl_adapter.py:42`, `xbrl-occurrences/1`) and `PDF_EXTRACTOR_VERSION`
(`pdf_adapter.py:52`, `pdf-occurrences/2`) must advance although PDF behaviour is unchanged. Ingest
defaults follow the constants (`first_party_ingest.py:104–107`). No schema migration: versions are
text, pins are keyed by `(artifact, version)`, generations are versioned.

**Stored generations and replay.** Generations are keyed `(capture, extractor_version)`
(`first_party_extract.py:228–235`); a v2 ingest of a stored capture appends a `PARSER_REEXTRACTION`
generation and never rewrites v1 rows (`test_evidence_reprocessing.py:60–131`). New runs select only
the pinned extractor's interpretations (`selection.py:415–421`), so an existing entity needs a v2
ingest before a new run sees first-party values (lazy re-extraction). Replay uses the stored pins and
by-id reads (`compare/run.py:160–197`). v1 cannot be re-run after the bump (its name would hash
current bytes and drift).

**Frozen headers (ruling, Sol r1).** Approved manifests stay unchanged; their extractor names record
the original authoring context. A fresh run under advanced versions compared with their unchanged
expected evidence/results is **regression equivalence, not reproduction** of the original run
identity or pins. Each fresh stored run retains its actual new pins (Stage 4 checks current pins,
`test_data_stage4_e2e.py:175–176`); historical stored-run replay retains old pins and by-id reads.

**Historical draw dependency.** `stage4_filings.xbrl_admitted` (`:98–116`) recomputes attempt-3 skips
through production `financial_rule` and `framework_state`; this phase changes both, which would break
the recorded draw. Both are frozen test-side (Task 2). Boundary: the parser (`parse_instance`) and
`instance_state` stay production imports; this phase leaves them unchanged.

**The signal (measured).** Inventory: `data/raw/onboarding-dev/**/nse/*.xml` plus
`data/raw/watchlist/aparinds/nse/*.xml` — **26 files, 25 distinct by sha256 of bytes** (dedup rule);
lxml over every element's `nsmap`:

| Group | Distinct | schemaRef | `IntegratedFinance_<form>` forms declared | v1 framework accepts |
|---|---|---|---|---|
| Non-financial integrated (Apar ×6, 10 dev cos) | 16 | `in-capmkt-ent-2025/2026-01-31.xsd` | exactly `{IndAS}` 16/16 | 7 (Apar ×6, LAURUSLABS) |
| HDFCBANK | 2 | `in-capmkt-ent-2026-01-31.xsd` | exactly `{Banking}` | 0 |
| BAJFINANCE | 2 | same | exactly `{NBFC}` | 0 |
| HDFCLIFE, SBILIFE | 3 | `in-capmkt-ent-2025-01-31.xsd` | exactly `{LI}` | 0 |
| Apar legacy `in-bse-fin` | 2 | `Ind-AS_entry_point_2020-03-31.xsd` | none | 2 (schemaRef) |

Phrase absent in 9 dev companies: CGPOWER, ETERNAL, HFCL, MTARTECH, NETWEB, POLYCAB, SONACOMS,
THERMAX, TITAN. **Characterisation:** the IndAS form namespace is an explicit, filer-chosen Ind AS
form declaration — the same kind of structural declaration v1 accepts from `Ind-AS_entry_point`
(`member_identity.py:48–52,184–186`). It is not a measured classifier separating every Ind AS from
non-Ind AS filer; no universal claim is made. **Verified counterexample (Sol r1):** adding an unused
IndAS root namespace to a retained HDFCBANK filing turns today's `financial_rule` true; R1's
conflict clause below closes it.

## Design

`integrated_ind_as(body: bytes) -> bool` in `member_identity.py` (lowest common layer; `evidence`
must not import `entity`), with the moved `IND_AS_ENTRY_POINT` regex and `in-capmkt-ent-` prefix.
True iff all hold (unparseable bytes → false):
1. at least one `link:schemaRef`, every basename starting `in-capmkt-ent-`;
2. some declared namespace matches `IND_AS_ENTRY_POINT` (today's `financial_rule` clause);
3. **no competing form (R1):** the set of `<form>` values over every namespace declared anywhere in
   the document (each element's `nsmap`) matching
   `^http://www\.sebi\.gov\.in/xbrl/IntegratedFinance_([^/]+)/` is exactly `{"IndAS"}`. Any other
   form (Banking, NBFC, LI, or unknown) alongside IndAS → false.

Uses:
- ingest: `verify_xbrl_framework(instance, framework, *, body: bytes)` adds Ind AS evidence
  "IntegratedFinance_IndAS form declaration" when `integrated_ind_as(body)`. The v1 schemaRef and
  text-block branches are unchanged, so v2 = v1 ∪ structural: it rejects nothing v1 accepted. (A
  conflicted filing with a notes phrase is still accepted by the phrase, as in v1.) `_read_xbrl`
  passes the `body` it holds (`first_party_extract.py:393,402`).
- discovery: `financial_rule(body)` returns `integrated_ind_as(body)`; `framework_state(instance,
  body)` calls `verify_xbrl_framework` as ingest does; `discovery.py:538` passes `zip(instances,
  bodies)` on the same line (≤100 columns).
Passing `body` avoids extending the 799-line parser. Versions: `xbrl-occurrences/2`,
`pdf-occurrences/3`; pinned files touched: `member_identity.py`, `first_party_extract.py`,
`xbrl_adapter.py`, `pdf_adapter.py`.

## File map

| File | Change |
|---|---|
| `src/fundamentals/evidence/member_identity.py` (pinned) | `integrated_ind_as`; `verify_xbrl_framework(..., body=)` |
| `src/fundamentals/evidence/first_party_extract.py` (pinned) | pass `body=` at `:402` |
| `src/fundamentals/evidence/xbrl_adapter.py`, `pdf_adapter.py` (pinned) | version constants |
| `src/fundamentals/entity/verification.py` | `financial_rule` delegates; `framework_state(instance, body)`; drop moved constants |
| `src/fundamentals/entity/discovery.py` | 1 line: pass bodies |
| `tests/fundamentals/test_identity_namespace.py` | signal cases incl. R1 conflict negative; `body=` |
| `tests/fundamentals/test_evidence_refusals.py` | phrase-only removal ingests; no-declaration case renames the form |
| `tests/fundamentals/test_xbrl_dimension_identity.py` | `body=` the mutated bytes (`:60–69`) |
| `tests/fundamentals/test_derived_settings.py` | upgrade proof (R4) |
| `tests/fundamentals/stage4_filings.py` | frozen historical admission rule (R2) |
| `tests/fundamentals/test_onboarding_verification.py` | parity; historical rule; R1 through discovery; phrase-removed Apar onboards |
| `docs/workstreams/data-foundation/roadmap.md`, `plans/D6.md` | phase row, D7 edge, D3.6 amendment pointer |

## Tasks

### Task 1: Predicate v2, version advance, upgrade proof

Goal: a phrase-free IndAS-form instance ingests `COMPLETE` under `xbrl-occurrences/2`; Banking/NBFC/LI,
unknown and conflicting forms without another declaration stay `IDENTITY_REJECTED`; a pre-upgrade
database keeps its pins, rows and results and replays them.
Interfaces (produces): `integrated_ind_as(body: bytes) -> bool`;
`verify_xbrl_framework(instance: RawXbrlInstance, framework: AccountingFramework, *, body: bytes) -> IdentityVerdict`;
`framework_state(instance: RawXbrlInstance, body: bytes) -> Verdict`; the two version constants.
Approach (test-first; record the red run):
- `test_evidence_refusals.py`: replacing only `XBRL_DECLARATION` gives XBRL `COMPLETE` whose evidence
  names the form declaration (today `IDENTITY_REJECTED`); the no-declaration case also rewrites
  `IntegratedFinance_IndAS` → `IntegratedFinance_ZZ` and stays rejected.
- `test_identity_namespace.py`: parametrise one retained instance per form with its own bytes
  (phrase-free dev IndAS accepted; HDFCBANK, BAJFINANCE, HDFCLIFE rejected "declares no accounting
  framework"). **R1 marked negative:** an in-memory copy of a retained HDFCBANK filing with the
  root namespace `http://www.sebi.gov.in/xbrl/IntegratedFinance_IndAS/2026-01-31/in-capmkt/in-capmkt-ent`
  added (Banking namespaces and content kept) → `integrated_ind_as` false and
  `verify_xbrl_framework(..., body=marked)` rejected. Foreign-text test passes its own bytes.
- `test_xbrl_dimension_identity.py:69`: pass `body=etree.tostring(root)`, the bytes parsed at `:60`
  (bind once, reuse) — never unrelated bytes.
- **Upgrade proof (R4)**, extending `test_onboarding_on_a_seed_commit_database_…` (`:475`) with the
  existing helpers (`_seed_bytes`, `_onboard`, `_compare`, `replay_run`, `load_results`):
  1. `_seed_pins` hashes with `run_config.extractor_pin(representation, version=seed_version)` where
     `SEED_VERSIONS = {XBRL: "xbrl-occurrences/1", PDF: "pdf-occurrences/2"}`; assert the pins
     equal literal `(version, sha256-hex)` pairs recorded in the test (the seed bytes are fixed by
     `SEED_COMMIT`).
  2. Pre-upgrade state, under `run_config._SOURCE_ROOT` = seed root and `EXTRACTOR_VERSIONS` =
     `SEED_VERSIONS` (monkeypatched): pin the seed pins, ingest Apar XBRL **and** PDF with
     `extractor_versions=SEED_VERSIONS` (old-version generations), and store one comparison run.
     (The rows come from current code; for Apar, whose notes carry the phrase, v1 and v2 extract
     identically — stated in the test docstring.)
  3. Snapshot tables, run results and the stored run's pins; leave the seed patches, explicitly
     restoring the current source root and default-version map; re-ingest the same retained
     two-member Apar intake (XBRL + PDF) under current defaults via the existing `Ingest.run`
     helper (`tests/fundamentals/evidence_support.py`); then also onboard Apar. Onboarding alone is
     insufficient: it builds an XBRL-only intake and records a capture-less PDF `EXCLUDED_BY_RULE`
     attempt (`onboard_cli.py` ~:425–466), so it cannot exercise PDF re-extraction.
  4. Assert: exit as today; every pre-existing row unchanged; the stored run's manifest pins still
     name the seed versions/hashes; `replay_run` uses them and returns identical `load_results`;
     the same XBRL and PDF captures carry both old (`xbrl-occurrences/1`, `pdf-occurrences/2`) and
     new (`xbrl-occurrences/2`, `pdf-occurrences/3`) generations, new attempts `COMPLETE`; no
     `VersionContentDriftError`. Limitation: seed rows come from current code under historical
     pins — a compatibility fixture, not historical execution. No production API, migration or bulk tool.
Verification: `uv run pytest tests/fundamentals/test_identity_namespace.py tests/fundamentals/test_evidence_refusals.py tests/fundamentals/test_xbrl_dimension_identity.py tests/fundamentals/test_derived_settings.py tests/fundamentals/test_compare_config_pins.py tests/fundamentals/test_evidence_reprocessing.py`
green; `wc -l src/fundamentals/entity/discovery.py` ≤ 800; mypy, ruff.
Dependencies: none. Risk: a missed PDF bump passes in fresh DBs but drifts on real ones — the
upgrade proof guards it. Implementer: Opus.

### Task 2: Discovery parity and the frozen historical rule

Goal: discovery's framework verdict equals v2 ingest's, and discovery admits exactly the
sector-eligible inputs v2 ingest accepts; the D6 draw checker evaluates the historical
v1 rule independently of production.
Approach:
- **Historical rule (R2)** in `stage4_filings.py`, one small helper, docstring "frozen D6 attempt-3
  admission rule, restated from `4351e2c` (`src/fundamentals/evidence/member_identity.py:35–52,179–196,245–281`,
  `entity/verification.py:74–81,153–166`, `extract/pdf_header_text.py:55–57`); never the production
  rule". Frozen literals: phrases `"prepared in accordance with Indian Accounting Standard"`,
  `"prepared in accordance with the Indian Accounting Standards"`; schemaRef basename prefix
  `"Ind-AS_entry_point"`; text-block suffix `"TextBlock"`; tokenisation `re.sub(r"[^a-z0-9]+", " ",
  text.lower()).split()` with contiguous-token-run matching; framework = Ind AS iff a schemaRef or
  an own-taxonomy non-numeric text-block fact declares it (single framework only). The historical
  sector rule (today's `financial_rule` body: in-capmkt-ent schemaRefs + IndAS namespace, no
  conflict clause) is restated alongside. `xbrl_admitted` uses both instead of production
  `financial_rule`/`framework_state`; parser and `instance_state` stay production (unchanged here).
- Historical-rule tests (`test_onboarding_verification.py`): schemaRef-only → the historical
  framework helper accepts (full `xbrl_admitted` still applies the historical sector rule); phrase-only →
  accepted; structural-only (IndAS form, no phrase) → **not** accepted; absent → not; phrase only in
  a foreign-namespace text block → not. Independence: monkeypatch
  `member_identity.verify_xbrl_framework`/`verification.framework_state`/`financial_rule` to
  always-accept and assert `xbrl_admitted` results are unchanged over the 25 retained instances.
  Historical combined admission = 7 (`{APARINDS, LAURUSLABS}`); the historical framework helper
  alone accepts 9 — those 7 plus the two legacy Apar `Ind-AS_entry_point` schemaRef instances,
  which discovery's sector rule rejects.
- Parity (`test_discovery_admits_exactly_the_instances_first_party_ingest_accepts`, `:104–131`),
  over all 25 inputs: (a) `framework_state(instance, body)` equals the ingest framework verdict;
  (b) discovery admission equals `financial_rule(body) AND ingest_framework_verified` (plus the
  unchanged instance gates where applicable). Admitted == 16 integrated positives, symbols = the
  11; the R1 marked HDFCBANK copy is refused by `financial_rule` and by `framework_state`.
- REFUSALS `no_framework_declaration` (`:380–389`) becomes a success case: exit `INCOMPLETE`
  (`PARTIAL`), XBRL attempt `COMPLETE`, occurrences under `XBRL_EXTRACTOR_VERSION`. Combined-defect
  cases using `_NO_PHRASE` (`:530,564–574`) drop it; delete a resulting duplicate.
  `test_stage4_holdout_git.py` needs no edit.
Verification: `uv run pytest tests/fundamentals/test_onboarding_verification.py tests/fundamentals/test_stage4_holdout_git.py tests/fundamentals/test_data_stage4_e2e.py`
green, then the phase gate.
Dependencies: Task 1. Risk: the opaque Stage 4 e2e is predicted green (plausible, not verified). If
red: stop, do not patch, never alter expected outputs; a Sol-reviewed amendment records the cause.
Implementers never open opaque files. Implementer: Opus.

### Task 3: Acceptance smoke and records

Goal: a live full-onboard smoke over the 11 development symbols meets the pass rule; records updated.
Files: `roadmap.md` (Progress row "D6b Extractor v2 (`eqos-71x`)", edge `D7 → D6b`); `D6.md` one-line
D3.6 amendment pointer (no history rewritten); this plan's status and observed table.
Approach: orchestrator runs `scratchpad/execution/d6/live_onboard_smoke.py` at a committed `HEAD`
(credentials sourced by the orchestrator, scratch `eqos_test_*` DB); fresh generations are required.

| Symbol | v1 baseline | v2 expected | Kind |
|---|---|---|---|
| APARINDS, LAURUSLABS | `PARTIAL` (observed 2026-10-16) | `PARTIAL` | enforced |
| NETWEB | `UNSUPPORTED (STANDALONE_BASIS)` | unchanged, framework gate not reached | enforced |
| THERMAX, SONACOMS | `NO_FRAMEWORK_DECLARATION` observed after identity and period passed | `PARTIAL`, XBRL `COMPLETE` | enforced |
| CGPOWER, ETERNAL, HFCL, MTARTECH, POLYCAB, TITAN | `NO_FRAMEWORK_DECLARATION` predicted from retained instances | `PARTIAL` | provisional |

Pass rule (all required):
1. every enforced row holds;
2. ≥1 formerly phrase-free company is `PARTIAL`/`ONBOARDED` with all XBRL attempts `COMPLETE` under
   `xbrl-occurrences/2` (THERMAX/SONACOMS satisfy it if row 3 holds);
3. ≥3 companies `PARTIAL`/`ONBOARDED` (D7's batch);
4. zero `NO_FRAMEWORK_DECLARATION` outcomes and zero first-party attempts rejected "declares no
   accounting framework";
5. per company the record states whether the framework gate was reached (an earlier refusal is not
   a passed framework check);
6. every unexpected outcome (enforced or provisional) is diagnosed against the retained inputs and
   the v1 baseline before disposition; only a diagnosed live-data change (e.g. a new filing) may be
   recorded as unrelated, explicitly, with a bead — never waived automatically. A failed request is
   re-run (R-ACQ).
Verification: smoke output saved under `scratchpad/execution/extractor-v2/`; table filled here.
Dependencies: Tasks 1–2, phase-end Sol review. Implementer: Sonnet (doc edits).

## Verification (phase gate)

- `uv run ruff check src tests/fundamentals`; `uv run ruff format --check src tests/fundamentals`;
  `uv run mypy --strict src`; `uv run pytest tests/fundamentals` (pg + retained up; no `-m`
  opt-outs), or `scripts/verify.sh gate <slice>`.
- Explicitly green within it: `test_data_stage{1,2,4}_e2e.py` (Stage 4: attempt-3 replay at `HEAD`,
  incl. `test_stage4_freeze_held_to_closure`), `test_ledger_stage{1,2,3}_e2e.py`,
  `test_frozen_manifests.py`, `test_stage4_holdout_git.py`, `test_compare_config_pins.py`,
  `test_evidence_reprocessing.py`.
- `git status` shows only the mapped files.

## Risks

- **Signal scope:** an explicit form declaration, not a classifier; conflicting or unknown forms fail
  closed (R1 clause); all other cases fall to v1 branches.
- **Existing databases:** entities show no first-party values in new runs until re-ingested under v2
  (lazy, by design); stored runs replay unchanged.

## Process notes

- Opaque-path searches use explicit permitted file lists or Python inputs over permitted roots —
  never recursive grep/rg over `tests/` or `data/`. Two r1 incidents (draft: a filename-only
  `grep -l`; review: one extractor-version header line of the held-out manifest) printed no
  identifier; D6 is closed; recorded, no burn.

## Open questions

- O1 (orchestrator): re-extract the live database's Apar generations now or lazily? Recommended:
  lazily; nothing in D7 reads them.
- Owner: none (option A was the owner's choice, 2026-10-16; no financial judgment).
