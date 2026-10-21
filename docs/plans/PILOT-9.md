# PILOT-9 Implementation Plan — four-quarter shareholding in the pilot

**Origin:** Sol's D8 phase re-review r3, finding R3-1 (`scratchpad/execution/d8/phase-r3-sol.md`):
the `_pilot9` tripwire (`tests/fundamentals/test_pilot_e2e.py:419`, `assert not D8_EXIT.exists()`)
blocks D8's full-suite phase gate (`docs/workstreams/data-foundation/plans/D8.md:1052`) and must be
replaced by real PILOT-9 coverage before D8's phase approval. Acceptance: `docs/backend-roadmap.md:109`
(PILOT-9), verdict rules `:115–126`; pilot exit plan `docs/plans/PILOT-E2E.md` (PILOT-9 row `:126`,
bead rulings `:139–146`, owner decisions `:150`, Task 4 `:219–226`). Beads: `eqos-4j2.32` (PILOT-9),
`eqos-4j2.8` (pilot), `eqos-17r` (D8).
Status: draft r3 (Sol plan review r1 and r2 findings incorporated; `scratchpad/execution/d8/pilot9-plan-r1-sol.md`,
`pilot9-plan-r2-sol.md`).

**Goal:** for each of PQ0–PQ3, the pilot exit test ingests Apar's quarter-matched SHP filing and
vendor captures through the CLI, runs `compare run --family shareholding` at the quarter's instant
and asserts the frozen aggregate/vendor inventory, outcomes, point checks, assumption labels and the
identity of the selected filing and vendor evidence. The tripwire is gone, the vacuity check stays,
and the pilot plan, report and roadmap record PILOT-9 as MET on that evidence, with the verdict still
CONDITIONAL on the remaining named gates.

**Out of scope:**
- Shareholding claims, sections or citations in pilot updates (§ Decision 3).
- Any D8 code, config, mapping or extractor change. D8 runs as built, under its pins.
- New acquisition code. The existing `shareholding acquire` is used unchanged.
- Holder lists, full tree inventories and keyless diagnostics per quarter. The D8 Stage 3 exit
  covers them.
- ETERNAL and TITAN at any instant other than 2026-06-30.
- The pilot verdict PASS, `PILOT_PROVEN: YES`, Phase 0.5 closure and closing `eqos-4j2.8`.
- Any retention extension, retention subsystem or change to `holds.yaml`.

**Constraints:**
- Versions are never mutated (D8 R1). Runs use dictionary `v3`, mapping set `v7`, normalisation
  policy `v2` and extractors `nse-shp-v2`, `screener-shp-v2`, `tijori-shp-v2` and `upstox-shp-v2`.
  If a new filing needs any change, stop and re-plan. Expectations are never changed to make a
  refusal pass.
- Models never compute numbers. Expected values come only from a frozen, Sol-approved manifest
  authored from hashed bytes. They never come from code output.
- Vendor readings never enter git (D8 Task 7 amendment, `plans/D8.md:1013`). They live in a private,
  hash-bound companion.
- An approved manifest payload is committed before the e2e commit that uses it
  (`test_frozen_manifests.py:755` `test_approved_payload_preceded_its_e2e`, unchanged).
- Formal outcomes are unchanged (D8 R10, R12). Formed pairs stay
  `NOT_COMPARABLE / PRECISION_UNSUPPORTED`. A point check never becomes a status, tier, fact or
  corroboration. Upstox stays diagnostic.
- Retention: raw generations, the companion and their backups inherit the strictest retention and
  licence deadline of every contributing capture (`plans/D8.md:1013–1023`, `d8-probe.md:1110–1117`).
  Registering a file as a manifest source is a hash binding, not a retention extension: for
  vendor-bounded captures only an open queue item or screen review holds
  (`src/fundamentals/retention/eligibility.py:20–23`), and licence end wins. On expiry the mixed
  artifact is deleted or regenerated without the expired material; reproduction then stops
  (`ORIGINAL_EXPIRED` semantics), with no recapture and no fabricated hold.
- PostgreSQL only on `eqos_test_*`. Nothing under `data/` is written by tests. The test never opens
  `stage4_*`, `data/holdout/`, `data/raw/onboarding/` or `~/.secrets`, and fixture files are named
  explicitly (no glob).
- 800-line cap per module and the File map caps below. Owner minimal-code rule (2026-10-14).

## Grounding (read-only; no vendor values)

1. **First-party SHP: only PQ3 is retained.** `data/raw/shareholding/APARINDS/gen-1` and `gen-2`
   each hold one SHP instance, the 2026-06-30 one (`02.bin`, `d8-probe.md` §1, §13.2). `acquire`
   fetches only the instances the listing dates at `--instant` (`ingest/shareholding_filing.py:95–98`).
2. **The retained NSE listing (`gen-2/01.bin`) has one unrevised row per PQ instant.** Knowledge
   time is the listing `broadcastDate` (IST, R4):

   | Quarter | Instant | Listing `recordId` / instance | Broadcast (IST) | Pilot source cutoff (UTC) |
   |---|---|---|---|---|
   | PQ0 FY26_Q2 | 2025-09-30 | 202526 / `SHP_1548120_14102025071519_WEB.xml` | 14-OCT-2025 19:15:27 | 2025-11-06T06:35:34Z |
   | PQ1 FY26_Q3 | 2025-12-31 | 205812 / `SHP_1602404_16012026043631_WEB.xml` | 16-JAN-2026 16:36:40 | 2026-02-04T09:18:22Z |
   | PQ2 FY26_Q4 | 2026-03-31 | 207887 / `SHP_1648747_10042026040326_WEB.xml` | 10-APR-2026 16:03:37 | 2026-06-04T10:43:48Z |
   | PQ3 FY27_Q1 | 2026-06-30 | 211105 / `SHP_1692435_14072026053431_WEB.xml` (retained, gen-2) | 14-JUL-2026 17:34:40 | 2026-07-31T10:14:41Z |

   This is the retained listing only; it does not establish what a fresh acquisition returns. A
   fresh listing that shows more than one submission at a quarter's instant stops this plan for a
   re-plan (Task 2, single-submission rule).
3. **Vendor period coverage (column headers of the gen-2 bytes only):** Screener `quarterly-shp`
   and its quarterly drill-downs and Tijori `company_detailed` cover all four PQ instants; Screener's
   yearly table stays diagnostic (R11). Upstox `history` covers PQ2 and PQ3 only. Vendor sides are
   selected by attempt `period_end == instant` and capture `registered_at <= cutoff`
   (`compare/vendor_sides.py:340–378`); a complete capture with no interpretation at the key gives
   `NO_VALUE` (`:401–410`), so Upstox at PQ0/PQ1 has no failed attempt, leaves run status unchanged
   and has no point-check candidate.
4. **Each instant needs its own generation.** `shareholding ingest --instant` replays one whole
   generation whose SHP dates at that instant, with vendor attempts at `period_end = instant`
   (`api/shareholding_cli.py:139–206, 235–247`). Gen-2 vendor captures cannot serve PQ0–PQ2 through
   the CLI. Gen-2 made 15 requests; that is observed behaviour, not a fixed count.
5. **The pilot never uses shareholding** (`PILOT-E2E.md` Evidence 4; D8 Out of scope; R12). No
   admitted fact or trace exists for an update to cite.
6. **Pilot entity identity.** `seed_apar` loads `config/identity/aparinds.yaml`; base identifiers
   without temporal relationships are unbounded (`entity/identity_layers.py:4–8, 416–435`;
   `pg/identity_seed.py:146–165`). No earlier identity history is indicated; Task 3 Step 0 asserts it.
7. **Reuse inventory:**
   - `test_data_stage3_e2e.py`: `_recorded`-style templating, `_key`, `_labels`, `_printed`,
     `_point`, `_want_point`, `_package`, and `stage1_e2e_support.expected/actual/diff`.
   - Stage 3 manifest schema: `packages.<SYM>.{stored[{instance, lineage, links, at: [{src, path,
     lex}]}], selected}` for filing identity; the run row and point-check schemas.
   - `manifest_locators` readers (`shp_table`, `shp_bucket`, `tijori_html`, `upstox_shp`) for
     vendor cells; `stage3_data_support.facts/number/row_key`.
   - `restore_check.replay` → `replay_run` is family-agnostic (`pg/restore_check.py:167`).

## Decisions and rulings

1. **Acquire PQ0–PQ2 with the existing CLI.** Three live `shareholding acquire` runs. PQ3 reuses the
   retained gen-2, whose Stage 3 expectations are already approved. The CLI's fixed authorisation
   string ("plan D8 Task 4") is preserved and is not presented as new authority; the acquisition
   record states the PILOT-9 purpose and the actual generation numbers, under the existing
   registered-source authority and this plan's bounded scope (Sol r1 ruling Q6).
2. **Extend the frozen `pilot_manifest.yaml` with a `shareholding` section and a private vendor
   companion.** A separate manifest would need an `E2E` entry and edits to `test_frozen_manifests.py`
   (798/800) and `holds.yaml`; extending reuses registration, preflight and the order rule unchanged.
   Sol re-approves the whole payload. This supersedes `PILOT-E2E.md`'s out-of-scope line "any edit to
   `pilot_manifest.yaml`". PQ3 is not duplicated: the section pins `stage3_manifest.yaml` by SHA-256
   and points at its `APARINDS-SHP-2026-06-30` run, package and point checks.
3. **Citations (Sol r1 ruling Q2).** Update-citation coverage is vacuous: no pilot update uses
   shareholding, and the existing vacuity check (no version carries a shareholding key or section)
   stays as the proof. Separately, the `compare report` point lines' assumption labels are asserted
   directly. Report labels are not update citations; no sealing, export or citation-survival path is
   claimed as exercised. Any later update use activates the real citation requirement.
4. **Vendor timing (Sol r1 ruling Q3).** "Each quarter" fixes the valid-time instant. Comparisons are
   separate store-clock `as_known` runs (PILOT-2 route, `pilot_e2e_support.py:296–336`); every vendor
   capture is registered after all four source cutoffs. The report calls them later-acquired
   historical-period comparisons, records actual capture and run times, and excludes them from
   historical update evidence. This does not establish point-in-time vendor knowledge. The
   first-party side is cutoff-clean.
5. **Upstox (Sol r1 ruling Q5).** Diagnostic (`contracts/source_catalog.py:310`). PQ0/PQ1:
   `NO_VALUE`, no point line, completeness unchanged. PQ2/PQ3: its expected sides are asserted like
   any other. This does not relax Screener/Tijori coverage.
6. **Earlier taxonomy (Sol r1 ruling Q7).** A first-party schema or identity refusal makes `_ingest`
   exit non-zero (`api/shareholding_cli.py:217–226`); namespace support is pinned
   (`evidence/shareholding_filing.py:190–196`). Refusal → stop and re-plan.
7. **Verdict label (orchestrator ruling, accepted by Sol r1 ruling Q1).** The verdict stays
   CONDITIONAL, its conditions restated as the remaining gates (Task 4). The governing definition at
   `backend-roadmap.md:121–123` is amended to match. PASS, Phase 0.5 closure and
   `PILOT_PROVEN: YES` stay reserved. No owner confirmation is awaited.
8. **Placement: one block after the quarter loop**, after `_pilot5`/`_pilot12` and before `_pilot6`,
   looping PQ0→PQ3. The four run ids join `runs` for PILOT-13 and PILOT-10; captures go to
   `pilot.rig.snapshots`.

## File map

| File | Task | Responsibility | Lines (now → max) |
|---|---|---|---|
| `data/raw/shareholding/APARINDS/gen-N` ×3 (private, gitignored) | 1 | PQ0, PQ1, PQ2 generations written by `shareholding acquire` | — |
| `tests/fundamentals/fixtures/data_foundation/pilot_manifest.yaml` | 2 | `shareholding` section; new `header.sources`; re-approval | 748 → — |
| `data/raw/shareholding/pilot-manifest/pilot_vendor.yaml` (private, gitignored) | 2 | per quarter: vendor side and point-check readings plus the aggregate-only node locator map | — |
| `tests/fundamentals/pilot_manifest_check.py` | 2 | `check_shareholding(m)` called from `check_pilot`; sources derivation; `PILOT_MUTATIONS` entries | 417 → ≤ 520 |
| `tests/fundamentals/pilot_e2e_support.py` | 3 | `pilot9(pilot, quarter) -> int` | 457 → ≤ 580 |
| `tests/fundamentals/test_pilot_e2e.py` | 3 | `D8_EXIT` and its assertion removed; `_pilot9` reduced to the vacuity check; block wired; docstrings | 600 → ≤ 610 |
| `tests/fundamentals/test_data_stage3_e2e.py` | 3 | `_want_point` takes the quarter instant (keyword, default `HEADER['instant']`); `_package` takes a hash→label map (keyword, default `LABELS`) | 300 → ≤ 306 |
| `docs/plans/PILOT-E2E.md` | 4 | PILOT-9 row, `eqos-4j2.32` ruling, Task 4 verdict line, pointer to this plan | — |
| `docs/evidence/pilot/report.md` | 4 | PILOT-9 row and evidence, acquisition record, verdict text, conditions | — |
| `docs/backend-roadmap.md` | 4 | Pilot row (`:47`), CONDITIONAL definition (`:121–123`), report-link parenthetical (`:128`) | — |
| `docs/status/dashboard.html`, `docs/status/activity.json` | 4 | status refresh after each committed task | — |

`test_frozen_manifests.py` (798), `stage3_data_support.py`, `config/retention/holds.yaml`,
`scripts/verify_project.sh` and every `src/` file stay unedited.

## Tasks

### Task 1: Acquire PQ0–PQ2 first-party filings (orchestrator)

Goal: Apar SHP generations exist for 2025-09-30, 2025-12-31 and 2026-03-31, each complete with every
request `OK`, and each ingests without refusal.

Files:
- Create: three `data/raw/shareholding/APARINDS/gen-N` directories (numbers as the CLI writes them).

Interfaces:
- Consumes: the registered D8 surfaces and origins, `config/watchlist.yaml` (Tijori slug), and
  credentials through `scripts/credentials.sh` only.
- Produces: one generation per instant (`discovery-manifest.json` plus `NN.bin` bodies). Generation
  numbers, request counts, manifest SHA-256s, registration times and the PILOT-9 purpose go into
  `report.md` § Acquisition.

Approach:
- One at a time, each after `source scripts/credentials.sh`, nothing printed:
  `fundamentals shareholding acquire --symbol APARINDS --instant 2025-09-30 --raw-root data/raw/shareholding`,
  then `--instant 2025-12-31`, then `--instant 2026-03-31`.
- A non-zero exit keeps the failed generation for diagnosis; retry once (next number); a second
  failure stops and reports.
- Smoke ingest: on a disposable `eqos_test_*` database seeded as `test_shareholding_filing._seed`,
  `shareholding ingest --generation N --instant <PQ>` per new generation. Read only exit code and
  outcome words.

Verification:
- Each acquire exits 0; every entry outcome is `OK`.
- Each generation's `NSE_SHP_XBRL` request names an instance listed at that instant. If the fresh
  listing shows more than one submission at the instant, stop and re-plan (Task 2 rule).
- Each smoke ingest exits 0.
- `uv run pytest tests/fundamentals/test_shareholding_filing.py tests/fundamentals/test_shareholding_vendor.py tests/fundamentals/test_shareholding_compare.py tests/fundamentals/test_data_stage3_e2e.py`
  stays green (they pin `--generation 2`).
- `git status` is unchanged (`data/` is ignored).

Dependencies: Sol APPROVE on this plan.

Risks: a refusal (Decision 6) stops the plan.

### Task 2: Frozen `shareholding` section and its check (Opus, fresh, independent author)

Goal: `pilot_manifest.yaml` carries a hand-verified, Sol-approved `shareholding` section binding each
quarter's expected run, point checks, selected filing and vendor cells to hashed bytes, with vendor
readings only in the private companion. `check_pilot` validates it and rejects its mutations. The
approved manifest is committed; the pilot order check is recorded as pending until Task 3's commit.

Files:
- Modify: `pilot_manifest.yaml`, `pilot_manifest_check.py`.
- Create: `data/raw/shareholding/pilot-manifest/pilot_vendor.yaml` (private).
- Test (unedited): `test_pilot_manifest_check.py` (driven by `PILOT_MUTATIONS`),
  `test_frozen_manifests.py`.

Interfaces:
- Consumes: Task 1's generations; gen-2 bytes; the Stage 3 manifest header (rulings, members,
  baskets, notation, `cli`), its `APARINDS-SHP-2026-06-30` run and `packages.APARINDS`; D8 R10–R12
  and `d8-probe.md` §13.5.
- Produces:
  - `shareholding.hand_verification`; `shareholding.companion: {path, sha256, rows}`;
    `shareholding.stage3`: the label of the pinned `stage3_manifest.yaml` source.
  - `shareholding.cli`: the Stage 3 `ingest` / `run` / `report` commands with `APARINDS` written
    literally for `<SYM>` and `<KEY>`, slots `<INSTANT>`, `<GEN>`, `<tmp>` only, every other flag as
    Stage 3 records it.
  - `shareholding.quarters.<FY26_Q2|FY26_Q3|FY26_Q4>`:
    - `instant`, `generation`;
    - `package`: the Stage 3 `packages.<SYM>` shape — `stored: [{instance, lineage, links, at:
      [{src, path, lex}, …]}]` (listing `recordId`, `date`, `broadcastDate`, `submissionDate`,
      `xbrl`, `revisedData`, as `{src, path, lex}` locators into that generation's listing) and
      `selected: <index>`. `instance` is a source label, never a `src` key, so the generic walker
      sees only registered locator shapes;
    - `run`: the Stage 3 run schema (run, entity, instant, keys, source_vector, defaults,
      default_rows, rows, status, exit), each vendor side carrying `at: {node: <id>}` and `labels`;
    - `point_checks`: the Stage 3 point-check schema including `formal` (key, vendor, at, members,
      zero, expr, v, verdict, formal, labels).
  - `shareholding.quarters.FY27_Q1: {instant: '2026-06-30', generation: 2, run:
    APARINDS-SHP-2026-06-30}`, resolved in the pinned Stage 3 manifest (run, `packages.APARINDS`,
    point checks).
  - Companion, per run: `sides[<row key>][<vendor>]`, `point_checks[]` (Stage 3 shape), and `nodes`:
    an aggregate-only locator map `{<node id>: {file, periodicity, path, source_node_id, column}}`
    for exactly the nodes referenced by sides and point checks. `file` is a header source label of
    that quarter's generation (not `src`: an injected companion must not look like a generic
    locator); `column` is the native period header for the instant. No holder or
    tree inventory. `FY27_Q1` uses the Stage 3 companion unchanged.
  - `pilot_manifest_check.check_shareholding(m: Node) -> None`; its companion reader takes
    `shareholding.companion` (the Stage 3 helper reads `header.companion`), with the same
    injected-copy rule for mutations.

Approach:
- **Authoring** (D8 R9): a fresh Opus worker with a `scratchpad/` aid that never imports
  `fundamentals`, never runs D8 code and never reads run output. It reads only the pinned generation
  bytes, the Stage 3 header and the approved rulings.
  - Upstox at PQ0/PQ1: side `NO_VALUE`, no point line.
  - Screener and Tijori: a point line for each of promoter, public and institution (R12 Apar table).
    Labels exactly D, plus Bd or Z as that quarter's filing dictates; zero only where that
    quarter's filing has no context for the member.
  - Header sources gain every file of each new generation (labels `P0-…`, `P1-…`, `P2-…`) and
    `stage3_manifest.yaml`.
  - **Single-submission rule** (r2 R2-2): each quarter's listing must hold exactly one submission
    at its instant (the Stage 3 `package()` filter and assertion, `stage3_data_support.py:140–146`),
    so `stored` has one entry with `lineage: null` and `selected: 0`, and its `broadcastDate` must be
    at or before that quarter's `source_cutoff`. Otherwise stop and re-plan: production stores a
    revision's lineage as the predecessor's database `package_id`
    (`src/fundamentals/evidence/shareholding_ingest.py:320–325`, `:342`), which a byte-only author
    cannot freeze. Grounding 2 is not inherited.
- **Check.** `check_shareholding`:
  - Sources equal the derivation (generation files; Stage 3 manifest by hash); companion hash
    matches.
  - Each quarter's `package` has one `stored` entry, `lineage: null`, `selected: 0`; its `at`
    locators resolve in its listing (generic walker); its knowledge time is at or before the
    quarter's `source_cutoff` (existing `admitted`).
  - Every first-party lexeme is at its XBRL locator in that quarter's selected SHP.
  - Every companion `nodes` entry resolves through `manifest_locators` in its pinned file to the
    companion lexeme at its `column`, and every side's and point check's node id is in `nodes`.
  - Each point check's `expr` sums its listed first-party lexemes (zero only for a member absent
    from that filing) and equals `v`; every point line carries "denominator assumed, not
    vendor-stated"; no row pairs differing denominators.
  - `FY27_Q1` resolves to the pinned Stage 3 run.
  - Reuses `facts`, `number`, `row_key` and `manifest_locators`; no parallel locator code.
- **Mutations** (each must fail): a quarter's run removed; a paired denominator; a point-check label
  dropped; a zero taken for a filed member; a companion value changed by one unit in its last
  printed decimal; a node locator pointed at another column; the selected package's broadcast moved
  past the cutoff; the Stage 3 pin hash changed.
- **Approval.** Sol payload-bound review of the new manifest bytes (diff-focused, whole payload
  hashed), loop per `04-agent-stack.md`; `header.approval` updated. The orchestrator commits manifest
  and check.

Verification:
- `uv run pytest tests/fundamentals/test_pilot_manifest_check.py tests/fundamentals/test_frozen_manifests.py`
  passes except `test_approved_payload_preceded_its_e2e[pilot]`, which is expected to fail now: it
  compares the current payload with the parent of the latest committed e2e change, which is still
  the old one. Record it as pending; it is not edited or weakened. `test_manifest_is_approved[pilot]`
  and the new mutations pass.
- `test_pilot_e2e.py`'s `preflight` (manifest equals HEAD) passes after the commit.

Dependencies: Task 1.

Risks:
- An author ruling that differs from D8 code behaviour is settled by evidence (R9); a code defect
  stops this plan.
- `check_pilot`'s sources check (`:255–258`) is exact-set; the derivation adds exactly the named
  files.

### Task 3: Real PILOT-9 coverage in the pilot exit test (Opus). Starts after Task 2 is committed

Goal: each PQ quarter's shareholding comparison runs through the CLI on the pilot database and
matches the frozen section, including the selected filing and vendor evidence identities. The
tripwire is gone and the vacuity check remains. Any drift fails with `PILOT-9: <quarter>`.

Files:
- Modify: `pilot_e2e_support.py`, `test_pilot_e2e.py`, `test_data_stage3_e2e.py` (`_want_point`
  `instant` parameter and `_package` `labels` keyword; cap 306).

Interfaces:
- Consumes: Task 2's section and companion; `Pilot` (`entity_id`, `rig.snapshots`, `pg_db`);
  `stage1_e2e_support.expected/actual/diff`; `test_data_stage3_e2e._key/_labels/_printed/_point/
  _want_point/_package`; `EvidenceRepository`; `fundamentals.api.cli.main`. `_package`
  (`test_data_stage3_e2e.py:81–86`) resolves the XBRL hash through module-global `LABELS`, built
  from the Stage 3 header only (`:50`), so a new-quarter hash would raise `KeyError`.
- Produces: `pilot_e2e_support.pilot9(pilot: Pilot, quarter: str) -> int` (the run id, appended to
  `runs`); `_want_point(check, reading, package, instant=HEADER['instant'])` and
  `_package(package, labels=LABELS)`, Stage 3 calls and behaviour unchanged. No module global is
  patched and the Stage 3 manifest is not extended.

Approach:
- **Step 0, identity.** At each PQ instant, `APARINDS` and the issuer identifiers/ISIN resolve to
  `pilot.entity_id` (the `_entity` rule). Failure stops and re-plans (test-side identity history).
- **`pilot9`, per quarter:**
  - `shareholding ingest` (`cli.ingest`, snapshot root `pilot.rig.snapshots`) → exit 0.
  - `compare run` (`cli.run`) → exit equals `run.exit`; parse the new run id.
  - Rows: `diff(expected(rich, pilot.entity_id, STAGE3), actual(run, rows, items)) == []`, `rich`
    = frozen run plus companion vendor values, `STAGE3` = the pinned `stage3_manifest.yaml`. Covers
    keys, values, side states, pairs, outcomes, statuses and queue items.
  - Every formed vendor pair is `NOT_COMPARABLE / PRECISION_UNSUPPORTED`; Upstox state as recorded
    (`NO_VALUE` at PQ0/PQ1, its frozen sides at PQ2/PQ3).
  - **Filing identity:** `[_package(p, labels=…) for p in list_packages(...)]` equals the frozen
    `package.stored` (instance hash label, `null` lineage, links, knowledge time), `labels` being
    the pilot header's `{sha256: label}` for PQ0–PQ2 and the default for `FY27_Q1`; the selected
    package id comes from the frozen `selected` index, not from the run.
  - **Vendor identity:** for each VALUE side, its interpretation's occurrence
    (`Occurrence.capture`, `.native_context`: `src/fundamentals/contracts/evidence.py:262–278`) has
    `capture.blob_sha256` (`:191–204`) equal to the pinned file of its node's `file`, and
    `native_context` `periodicity`, `path`, `source_node_id` and `period_label` equal the node's
    `periodicity`, `path`, `source_node_id` and `column` (written by
    `src/fundamentals/evidence/vendor_shareholding.py:415–443`); labels (`_labels`) equal the frozen
    ones. Pins are those of the Constraints. For `FY27_Q1` the nodes are the pinned Stage 3
    companion's `tree[APARINDS][<vendor>]` entries (`id`, `file` basename, `periodicity`, `path`,
    `source_node_id`: `tests/fundamentals/stage3_data_support.py:87–90`), `file` resolved to the
    Stage 3 header source at `data/raw/shareholding/APARINDS/gen-2/<file>` and `column` the instant's
    period header; read only, no tree inventory, no companion or `stage3_data_support.py` change.
  - `compare report` (`cli.report`) → exit 0, `run\t<new run id>` and the frozen status printed;
    `point` lines equal `_want_point(check, reading, selected, instant=…)` for the frozen checks,
    each carrying "denominator assumed, not vendor-stated"; Screener and Tijori each print promoter,
    public and institution lines; no outcome other than the formal one.
- **Wiring.** After `_pilot12`: `runs += [pilot9(pilot, q) for q in QUARTERS]`, then PILOT-6, 13,
  10, 11 (iii) and 8 as today.
- **Tripwire and vacuity.** Delete `D8_EXIT` and its assertion; keep the vacuity check as
  `_pilot9_vacuity` (docstring: proves no update uses shareholding, Decision 3); update the module
  and test docstrings.

Verification:
- `uv run pytest tests/fundamentals/test_pilot_e2e.py tests/fundamentals/test_data_stage3_e2e.py`
  green, with `--durations` (§ Runtime).
- `data/` capture SHA-256s unchanged.
- Three `scratchpad/` probes on in-memory copies (never committed): a companion Screener value moved
  one unit in its last decimal; a label removed from a frozen point check; PQ1's expected `status`
  changed. Each fails `PILOT-9:`.
- Commit the e2e (its parent carries the approved manifest). Then
  `uv run pytest tests/fundamentals/test_frozen_manifests.py -k "preceded_its_e2e and pilot"` passes
  (closes Task 2's pending check).

Dependencies: Task 2 committed.

Risks:
- Runtime (§ Runtime).
- PILOT-10/13 now replay four shareholding runs; a replay mismatch is a D8 defect → stop and report.
- PILOT-10's real-clock dry run now sees the new vendor captures. They are registered at test time,
  so inside their vendor window and not eligible; manifest registration does not hold them
  (Constraints). If a required input is past its authority when the gate runs, reproduction stops
  as `ORIGINAL_EXPIRED`; nothing is recaptured or held to pass.

### Task 4: Reconciliation, verification and landing (orchestrator)

Goal: the pilot plan, report and roadmap state PILOT-9 MET on Task 3's evidence, keep the verdict
CONDITIONAL with its remaining conditions named in one place, and one full gate run is green so D8's
phase re-review can rule on R3-1.

Files:
- Modify: `docs/plans/PILOT-E2E.md`, `docs/evidence/pilot/report.md`, `docs/backend-roadmap.md`
  (`:47`, `:121–123`, `:128`), `docs/status/dashboard.html`, `docs/status/activity.json`.

Interfaces:
- Consumes: Task 3's green e2e, commit hashes, the acquisition record, runtime numbers.
- Produces: the reconciled documents and the gate logs.

Approach:
- **Conditions** (one list, written in `backend-roadmap.md:121–123`; the report and `PILOT-E2E.md`
  link to it): D8's own phase approval (Sol D8 r4); PILOT-11 (iii) blind drill `eqos-4j2.30`
  (owner); PILOT-12 owner review timing (Owner Q1; hand review `eqos-4j2.21`); PILOT-7 via the D6
  exit row; `verify_project.sh` exit 0; reviewer approval of the report. The roadmap definition
  becomes: the verdict is CONDITIONAL while any listed condition is open; PASS, Phase 0.5 closure and
  `PILOT_PROVEN: YES` stay reserved.
- **`PILOT-E2E.md`:** PILOT-9 row (test action = Task 3 block; failure = `PILOT-9:` drift;
  citation clause vacuous, vacuity asserted); `eqos-4j2.32` met by this plan, closing on Sol D8 r4
  APPROVE; Task 4 verdict line; pointer to this plan.
- **`report.md`:** PILOT-9 MET, citing the e2e block, the section and payload hash, the four
  instants, Upstox `NO_VALUE` at PQ0/PQ1, the vacuous citation clause and the label assertion
  (Decision 3), and the later-acquired-comparison wording with capture and run times (Decision 4);
  § Acquisition (Decision 1); the gate log paths; verdict "CONDITIONAL" linking the conditions.
  `eqos-3zl` done (2026-10-20); `eqos-4j2.8` stays open.
- **Gate.** One `scripts/verify_project.sh` run after the Task 3 and Task 4 commits. Its retained
  `scratchpad/project-verification.*` logs (Pytest, Mypy, Ruff, Ruff format, D8, Pilot) are the
  full-suite and quality evidence; read each log's status. Rerun only after a later change or a
  diagnosed failure. If `test_prior_refusals` recurs, keep its traceback (r3 note).
- **Review.** Sol D8 phase re-review r4, fresh round: r3 findings plus this plan's diff, the manifest
  approval and the reconciled report.
- **Commits** (explicit files, in order): manifest + check (Task 2), e2e + `_want_point`/`_package` (Task 3),
  docs (Task 4). Refresh the status files after each.
- **Beads** (orchestrator): `eqos-4j2.32` closes on r4 APPROVE; `eqos-4j2.8` stays open.

Verification:
- The verifier's Pytest log: zero failures, skips no more than the existing 9; Mypy and both Ruff
  logs pass; `D8 | PASS` and `Pilot | PASS`. Overall exit reported as observed.
- `grep -n "D8_EXIT" tests/fundamentals/test_pilot_e2e.py` returns nothing.
- `git status` clean apart from ignored files.

Dependencies: Task 3.

Risks: wording drift between documents — the condition list lives only in the roadmap.

## Runtime

No reliable baseline: the last pilot e2e run (2m14s, `scratchpad/pilot-e2e/e2e-run5.txt`) ended in
the known tripwire failure, and the last full suite (1:44:34, `scratchpad/d8-phase-gate.log`) had 4
failures. Before Task 3, measure `--durations=0` for `test_pilot_e2e.py` (labelled "ends at the
PILOT-9 tripwire") and `test_data_stage3_e2e.py`, and compare after Task 3 at the same boundary.
Budget: the block may add up to Stage 3 e2e time × 4/3 plus four more PILOT-10 replays; more than
twice that is investigated, not accepted. These are investigation bounds, not performance claims.
No test is split or marked slow.

## Verification (plan exit)

1. Task 2 and Task 3 focused checks green, including `test_approved_payload_preceded_its_e2e[pilot]`
   after the Task 3 commit.
2. One `scripts/verify_project.sh` run: Pytest, Mypy, Ruff, Ruff format, `D8 | PASS`, `Pilot | PASS`
   from its logs; overall exit as observed.
3. Sol D8 r4 `APPROVE` on R3-1.
4. `git status` clean.

## Dependencies

Sol APPROVE on this plan → Task 1 → Task 2 (Sol manifest approval, commit; order check pending) →
Task 3 (commit; order check passes) → Task 4 (docs commit, one gate run, Sol D8 r4). No parallel
implementers; Task 3 only reads Task 2's files.

## Risks

- PQ0–PQ2 SHP files fail under `nse-shp-v2` → caught by the Task 1 smoke; stop (Decision 6).
- Live acquisition under subscriber credentials, never printed; a mid-sequence refusal keeps a
  failed generation and the retry takes the next number.
- Retention: new inputs and the companion expire with their strictest contributing deadline; after
  expiry the e2e cannot reproduce, by design, as for Stage 3 (Constraints).
- A fresh clone fails both e2es (no retained bytes or companions), by design.
- WSL clock steps (`eqos-0bp`) may flake ordering; rerun once and note it.

## r1 dispositions

- R1-1 (order check impossible in Task 2): Task 2 records the pilot order check as pending; Task 3
  runs it after the e2e commit; the test is unchanged.
- R1-2 (filing record vs generic walker): the filing record reuses Stage 3 `packages` shape —
  `instance` label plus `{src, path, lex}` listing locators; no bare `src` on non-locators.
- R1-3 (unresolvable vendor nodes): companion `nodes` aggregate-only locator map per quarter,
  resolved through `manifest_locators`; companion read from `shareholding.companion`;
  `stage3_data_support.py` left unedited.
- R1-4 (selected evidence not bound): frozen `package.stored/selected` asserted via `_package`
  with the quarter's label map; vendor sides bound by blob SHA-256 and native locator; report run id
  equals the new run id; single cutoff-eligible submission per quarter, else stop (see r2).
- R1-5 (CONDITIONAL not reconciled): ruling adopted (Decision 7); roadmap `:121–123` in Task 4 scope
  and holds the single condition list.
- R1-6 (retention extension): claim removed; strictest-deadline inheritance, hash binding ≠ hold,
  expiry stops reproduction (Constraints, Task 3 risk).
- R1-7 (schema/CLI slots): `formal` added; `APARINDS` literal for `<SYM>`/`<KEY>`; `_want_point`
  gets a defaulted `instant` keyword.
- R1-8 (labels as citations): Decision 3 separates vacuous update citations from directly asserted
  report labels; no sealing/export claim.
- R1-9 (File map omission): `dashboard.html` and `activity.json` mapped to Task 4.
- R1-10 (duplicate full gate): one `verify_project.sh` run; its retained logs are the suite and
  quality evidence.
- Sol rulings Q1–Q7: incorporated as Decisions 1, 3–7 and Task 3 Step 0 (Q4, plus issuer
  identifiers/ISIN); the open-questions section is removed.

## r2 dispositions

- R2-1 (`_package` bound to Stage 3 `LABELS`): `_package` gains a `labels` keyword defaulting to
  `LABELS`; Task 3 passes the pilot header's hash→label map for PQ0–PQ2; File map and Task 3 edit
  boundary updated; no global patching, Stage 3 manifest unchanged; that file's cap 300 → 306.
- R2-2 (revision lineage is a runtime id): smaller option taken — exactly one submission per quarter,
  `lineage: null`, `selected: 0`; any multi-submission listing stops and re-plans (Grounding 2,
  Task 1, Task 2 rule and check); the cutoff check is kept.
- R1-4 (partial): closed by R2-1 and R2-2.
- Note, vendor fields: binding names `native_context.period_label` against the node `column`, with
  the producing seam cited.
- Note, PQ3 companion adapter: `FY27_Q1` nodes read from the pinned Stage 3 companion tree and
  normalized in Task 3; no tree inventory or `stage3_data_support.py` change.

## Amendment A1: SHP taxonomy 2025-05-31

**Trigger.** Task 1 retained gen-4 (2025-09-30), gen-5 (2025-12-31) and gen-6 (2026-03-31); gen-3 is
kept as the failed attempt. gen-5 and gen-6 smoke-ingest with exit 0. gen-4 refuses
`UNSUPPORTED_SCHEMA`: its facts are in `http://www.bseindia.com/xbrl/shp/2025-05-31/in-bse-shp`.
Decision 6 stops the plan. This amendment is the re-plan, and it bumps D8 versions. Evidence:
`scratchpad/execution/d8/pilot9-taxonomy-note.md` (structural counts corrected below, A1-5).

**Findings** (gen-4 `02.bin` against gen-5, gen-6 and gen-2 `02.bin`; structural, not ingestion):
- Concept local names, units, `decimals`, axes and context shapes are the same. Concept×dimension×
  unit×decimals signatures: gen-4 has 514; gen-5 has 498, all in gen-4; gen-6 has 497, all in gen-4.
  The text block `DisclosureOfNotesOnShareholdingPatternExplanatoryTextBlock` is in gen-4 and gen-5,
  absent from gen-6. The prefix `in-bse-shp` is the same, so concept QName text matches; the
  expanded QNames do not.
- Of the 21 `shareholding_filing/v1/shp.yaml` selectors, by local name and category member, 13
  have exactly one fact in each of gen-4/5/6 and eight have none (`central_state_government` ×2,
  `non_promoter_non_public` ×2, `employee_benefit_trust` ×2, `promoter_foreign`,
  `sovereign_wealth_funds_domestic`); none has more than one (`scratchpad/execution/d8/tools/shp_selectors.py`).
- `DateOfReport`, `ISIN`, `Symbol`, `ScripCode` and the DR declaration (`false`) have the same shapes.
- **Second refusal behind the first.** The context entity scheme is
  `http://www.bseindia.com/bse-shp/ScripCode` (2025-10-31: `…/in-bse-shp/ScripCode`), scrip `532259`
  in all 133 contexts. Under `nse-shp-v2` the identity gate (`shareholding_filing.py:254–280`)
  would reject gen-4.
- Four members appear only in gen-4, each carrying only zero ESOP/diluted facts (zero is filed, not
  absent). Two, `RelativesOfPromotersOtherThanPromoterGroupMember` and
  `TrustsWhereAnyPersonBelongingToPromoterAndPromoterGroupIsTrusteeOrBeneficiaryOrAuthorOfTrustMember`,
  have no `FORMAT_PARENT`, so `point_check._absent` (`point_check.py:202–227`, `:219`) would
  report `UNPLACED` for PQ0. The format places them under B(4): `R/reference/gen-1/02.bin` p. 9
  "(d) Relatives of promoters", p. 10 "(e) Trusts where any person belonging to 'Promoter and
  Promoter Group'…". Neither is filed in the three Stage 3 gen-2 filings.
- **Meaning.** SEBI circular 2025/35 (`02.bin`, in force from the quarter ending 30 June 2025) is the
  one format both taxonomies encode. No BSE or SEBI taxonomy change note is retained, and neither
  `.xsd` is retained: the 2025-10-31 URL is recorded `HTTP_404` (d8-probe §11.1); the 2025-05-31
  URL was never requested, so its availability is untested. The equivalence is an inference by
  identical local name, unit, structure and governing format, the label-binding grade of
  d8-probe §11.2. It is not taxonomy-wide semantic identity, and no owner financial judgment is
  involved (Sol A1 r1 ruling).

**Goal.** Occurrences stay namespace-faithful. `nse-shp-v3` extracts 2025-05-31 and 2025-10-31 SHP
instances, each under its own filed namespace. Mapping set v8 adds 2025-05-31-scoped entries for the
13 evidenced selectors; the v7 files are unchanged. Dictionary v3 and policy v2 are unchanged.
`nse-shp-v1`/`v2` and mapping set v7 are not edited in place (D8 R1); v2 stays a recorded name, like
v1, no longer reproducible from source.

**Files.**

| File | Change | Lines (now → max) |
|---|---|---|
| `src/fundamentals/evidence/shareholding_filing.py` | Changes listed below | 360 → ≤ 372 |
| `config/mappings/shareholding_filing/v2/shp.yaml` | New: 13 entries, `schema_identity` 2025-05-31 | new, ≤ 80 |
| `config/mappings/v8.yaml` | New: v7 plus `shareholding_filing/v2/shp.yaml` | new, ≤ 28 |
| `src/fundamentals/api/shareholding_cli.py` | `:89–90` mapping set `v7` → `v8` | 339 → 339 |
| `tests/fundamentals/test_shareholding_filing.py` | One gen-4 test; three refusal ids; helpers take the generation | 734 → ≤ 800 |
| `tests/fundamentals/test_shareholding_compare.py` | `:197` `--mapping-set v7` → `v8` | 591 → 591 |
| `tests/fundamentals/fixtures/data_foundation/stage3_manifest.yaml` | `:86` `v7` → `v8`; `:87` `nse-shp-v2` → `nse-shp-v3`; `:94` `--mapping-set v7` → `v8`; `:19` Sol re-approval | — |
| `docs/workstreams/data-foundation/plans/D8.md` | `:535` adds "`shareholding_filing/v2/shp.yaml`, `v8.yaml`: PILOT-9 A1"; `:537` adds "`nse-shp-v3`: PILOT-9 A1"; `:546` cap ≤ 740 → ≤ 800 | — |

`shareholding_filing.py` changes:
- `:67–68`: `SHP_EXTRACTOR_VERSION = "nse-shp-v3"`; `SHP_EXTRACTOR_VERSIONS` gains `"nse-shp-v2"`.
- `:70–71`: `SHP_NAMESPACE`/`SHP_FORMAT_VERSION` become one map `SHP_FORMAT_VERSIONS` from each
  accepted filed namespace to its format date: 2025-05-31 → `in-bse-shp/2025-05-31`,
  2025-10-31 → `in-bse-shp/2025-10-31`. No other `src/` module reads either name.
- `:192`: refuse `UNSUPPORTED_SCHEMA` unless the facts' namespaces are exactly one key of that map
  (`len(namespaces) == 1` and a subset of its keys). Mixed or unknown namespaces still refuse.
- `:303`: `CONTEXT_SCHEMA_IDENTITY` is the filed `fact.namespace_uri`. `CONTEXT_NAMESPACE`,
  `CONTEXT_DIMENSION_AXES`, `dimension_qnames`, `concept_qname`, `dimensions`, anchors and raw bytes
  stay as parsed. No `filed_namespace` key.
- `:338`: `format_version` is `SHP_FORMAT_VERSIONS[fact.namespace_uri]`.
- `:260–265`: `by_scheme` gains `http://www.bseindia.com/bse-shp/ScripCode` → the held scrip, as
  another BSE-scrip scheme. Every context (used or not) and every ISIN/Symbol/ScripCode fact is
  still checked against the temporally held issuer.
- `:101–105`: `_FORMAT_CHILDREN["NonInstitutions"]` gains `RelativesOfPromotersOtherThanPromoterGroup`
  and `TrustsWhereAnyPersonBelongingToPromoterAndPromoterGroupIsTrusteeOrBeneficiaryOrAuthorOfTrust`,
  so both map to `NonInstitutionsMember` in `FORMAT_PARENT`.

`shareholding_filing/v2/shp.yaml` (precedent `xbrl/v5/in_capmkt.yaml:1–5`):
- Header and `defaults` as v1 (`source`, `surface`, `tier: EQUIVALENCE_UNPROVEN`, `member_source`,
  `period_kinds`); `schema_identity: http://www.bseindia.com/xbrl/shp/2025-05-31/in-bse-shp`.
- One entry per selector with a gen-4 fact (the 13 above): selector, `canonical_id` and
  `dimension_members` copied from v1; `entry_id` is the v1 id plus `.2025_05` (unique, so
  `mapping.py:407–415` passes). The eight selectors with no fact get no entry.
- `evidence_ref`: the v1 entry's format row and denominator citation, plus "PILOT-9 A1: same local
  name, unit, decimals and context shape filed in APARINDS gen-4/02.bin (sha256 da042398…, instant
  2025-09-30, namespace 2025-05-31); SEBI format 2025/35 in force from the quarter ending
  2025-06-30; equivalence to the 2025-10-31 entry inferred, not proven from definitions (neither
  .xsd retained); scope: these observed shapes only."

**Interfaces.**
- No change to `mapping.py`, `interpret.py`, `point_check.py`, `run_config.py` or the v7 files.
  `matches`/`selects` (`mapping.py:158–173`, `:241–258`, `:208–237`) already scope each entry to
  its own schema; `supported_schemas` (`:383`) gains 2025-05-31 from the entries. `_absent` reads
  local names, so its roots are unchanged.
- A 2025-05-31 occurrence selects only a `.2025_05` entry; a 2025-10-31 occurrence only a v1 entry.

**Ripple.**
- A run cannot pin v2 and v3, or v7 and v8, side by side for SHP. Ingest writes the single module
  constant and the CLI's fixed config (`shareholding_cli.py:90`); interpretations are reused only
  under equal (mapping set, policy, extractor) pins (`shareholding_ingest.py:284–290`);
  `extractor_pin` hashes current source (`run_config.py:207–211`). Stage 3 therefore moves to
  `nse-shp-v3` and v8, and the compare test's run args to v8 (`test_shareholding_compare.py:197`).
- Stage 3's expected measurement rows and outcomes are predicted unchanged (gen-2 is 2025-10-31; the
  new entries and members do not occur in it). That is a prediction pending execution, not byte
  equality of run artifacts or pins.
- The Stage 3 manifest's payload changes at `:86`, `:87` and `:94` (`:13` is authoring history and
  stays). It needs a fresh `payload_sha256` and Sol `APPROVE`, and is committed before Task 3's
  commit to `test_data_stage3_e2e.py`. Task 2 pins that re-approved Stage 3 file by SHA-256 (`:110`).
- PILOT-9 Constraints (`:31–32`) read mapping set `v8` and extractor `nse-shp-v3`. The Out-of-scope
  line "Any D8 code, config, mapping or extractor change" (`:22`) and the File-map line "every `src/`
  file stays unedited" (`:153–154`) are superseded for the files above only. Vendor mappings,
  dictionary v3, policy v2, outcome rules, assumption labels, retention, acquisition, and the
  settled verdict/citation rulings are unchanged. Task 1 resumes at the gen-4 smoke ingest.

**Verification.**
1. New test `test_a_2025_05_31_filing_stays_in_its_taxonomy` (medium, `pg`, `retained`):
   `_seed` APARINDS, ingest `APARINDS/gen-4` (`da042398…`) at 2025-09-30 (`_ingest`/`_evidence`
   take the generation and instant), exit 0. It asserts:
   - every occurrence has `extractor_version` `nse-shp-v3`, `CONTEXT_NAMESPACE` and
     `schema_identity` 2025-05-31, every `dimension_qnames` axis and explicit member in
     `{2025-05-31}`, and `disclosure.format_version` `in-bse-shp/2025-05-31`;
   - the interpretations' `mapping_entry_id`s with a value are exactly the 13 `.2025_05` ids, one
     occurrence each; no v1 id is used;
   - `FORMAT_PARENT` of both new members is `NonInstitutionsMember`;
   - ancestry: `point_check._absent(v8, "non_institutions", filed)`, with `filed` = gen-4's
     occurrences minus those on `NonInstitutionsMember`, returns the `_FILED` reason, not `None`
     (a filed new member keeps B(4) from becoming an absent zero). `_absent` is called directly
     because `point_checks` needs a full run; this is the boundary Sol named.
2. `test_refusals_write_nothing_but_their_attempt` (`test_shareholding_filing.py:505–532`) gains a
   quarter parameter (gen-2/2026-06-30 for its five ids; gen-4/2025-09-30 for three new ids), and
   `_marked` (`:455`) takes the generation. New ids, each asserting its attempt outcome and zero
   occurrences, interpretations and packages:
   - `gen4-context-entity`: first `ScripCode">532259<` (a `bse-shp/ScripCode` context identifier)
     → another scrip, `IDENTITY_REJECTED`;
   - `gen4-unused-context`: `_foreign_context` (`:495`) on gen-4, `IDENTITY_REJECTED`;
   - `gen4-mixed-namespace`: a new editor retags one fact into the 2025-10-31 namespace,
     `UNSUPPORTED_SCHEMA`.
3. `uv run pytest tests/fundamentals/test_shareholding_filing.py tests/fundamentals/test_shareholding_vendor.py tests/fundamentals/test_shareholding_compare.py tests/fundamentals/test_data_stage3_e2e.py tests/fundamentals/test_frozen_manifests.py`
   is green except `test_approved_payload_preceded_its_e2e[stage3]`, recorded as pending (A1-4;
   the same handling as the pilot at `:283–288`): it compares the current payload with the parent
   of the latest committed `test_data_stage3_e2e.py` change, which is still the old manifest
   (`test_frozen_manifests.py:755–768`, `manifest_support.py:266–272`). The test is not edited or
   weakened. `test_manifest_is_approved[stage3]` passes. `uv run mypy --strict`, `uv run ruff check`
   and `uv run ruff format --check` are clean on the touched files.
4. The Task 1 smoke ingest of gen-4, gen-5 and gen-6 under v3/v8 exits 0.
5. Order: commit (a) A1 code, config, tests and D8.md; commit (b) the Stage 3 manifest after Sol
   re-approval; then Task 2 and Task 3 as planned. After Task 3's e2e commits, run
   `test_approved_payload_preceded_its_e2e[pilot]` and `[stage3]`, record both closed, then the
   plan-exit gate.

**Risks.**
- The equivalence is unproven from taxonomy definitions. Task 2 checks extraction, selection and
  arithmetic against independently read bytes; it cannot detect a concept whose definition or
  denominator changed while its name, lexeme, unit and dimensions did not. A contradicting
  definition, if one is retained later, requires re-review of every interpretation under a
  `.2025_05` entry, not a PQ0-only conclusion.
- Any persistent store with `nse-shp-v2`/v7 pinned keeps those rows; new ingests re-extract under
  v3/v8 (the R1 design).

**Sol must review:** that the rewrite implements the r1 rulings (config-side v8, filed namespaces
preserved, scheme alias, both B(4) parents, Stage 3 move and deferral), with the 13-entry subset.

**A1 r1 dispositions** (`scratchpad/execution/d8/pilot9-a1-r1-sol.md`):
- A1-1 (preserve native identities; v8): adopted. No namespace rewrite or `filed_namespace`;
  `schema_identity`/`format_version` from the filed namespace; new `shareholding_filing/v2/shp.yaml`
  (13 entries, `.2025_05` ids, `EQUIVALENCE_UNPROVEN`, A1 evidence) and `v8.yaml`; CLI, compare
  test, Stage 3 pins/command and Constraints move to v8.
- A1-2 (manifest cannot detect a semantic change): Risks restated as the limitation; contradiction
  triggers re-review of all `.2025_05` interpretations; evidence scope stated in each `evidence_ref`.
- A1-3 (verification misses identity and ancestry): gen-4 test asserts filed namespace, expanded
  dimension identities, format date, both B(4) parents and the `_absent` ancestry consequence; three
  gen-4 refusal ids (wrong scrip under the old scheme, unused context, mixed namespace) assert
  nothing persisted.
- A1-4 (Stage 3 order check): `[stage3]` recorded pending during A1, closed with `[pilot]` after
  Task 3's e2e commit; test unchanged.
- A1-5 (counts and wording): signatures 514/498/497, text block in gen-4/gen-5 only; 13 selectors
  with one fact, eight with none; neither `.xsd` retained, 404 vs never requested.
