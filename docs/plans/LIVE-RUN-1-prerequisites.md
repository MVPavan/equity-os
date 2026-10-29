# LIVE-RUN-1 — Live run prerequisites for regenerating the Apar updates — Implementation Plan

**Origin:** bead `eqos-dna` (RESEARCH-1 Task 7). Scope = "Task 7 prerequisites" in
[RESEARCH-1 Amendment A1](RESEARCH-1-falsifier-status.md#amendment-a1-2026-10-27-live-ledger-is-empty)
(Sol APPROVE r3, 2026-10-27). Related: `eqos-0eu` (quote contracts no sealed import covers),
`eqos-hdz` (intermittent clock/PG flakes), `eqos-4j2.21` (no `ledger submit` CLI), `eqos-tqf`
(F1: reviewer adapter and panel CLI). Specs: data spec
`docs/specs/2026-10-11-canonical-financial-data-and-cross-source-comparison.md`, ledger spec
`docs/specs/2026-10-12-report-ledger-memory-and-data-lifecycle.md`.
**Goal:** an ordinary `fundamentals run` for APARINDS FY26_Q2 on live writes a draft that the
approval panel approves, then FY26_Q3, FY26_Q4 and FY27_Q1 do the same in order, with guidance
`SOURCE_QUOTE` claims bound through the imported versions' contracts.
**Out of scope:**
- A real model-calling reviewer adapter (rest of `eqos-tqf`); this plan records a verdict the
  orchestrator obtained from Sol out of band (decision OD-3).
- Contracts for quotes no sealed import covers (`eqos-0eu`); a quarter whose quote does not bind
  stops the sequence.
- The rework path after `REQUEST_CHANGES`/`REJECT` (PREP-5 flow; the orchestrator rules).
- Changing the retrospective designation text (`run_draft.py:642-648`).
- Disposing the open `HIGH` queue items of comparison runs 1–3 (finding F9: none is a required
  role).
- Any migration. Any edit under `data/`, `stage4_*`, `data/holdout/`, `data/raw/onboarding/`.
**Constraints:**
- Missing inputs fail closed; no fabricated numbers (invariant 10). The LLM never calculates
  (invariant 6).
- Facts append-only, nothing backdated; "Actual acquisition, registration, extraction, selection,
  approval and promotion times are kept" (PREP-2b contract b, `docs/plans/PREP-2b.md:56-59`).
- Neither a model nor the host clock may supply a knowledge time; historical eligibility comes
  only from the hash-pinned retrieval manifest's `filed_at_nse` (PREP-2b contract a).
- "No argv option, environment variable, JSON context file, dynamic plugin or manifest field
  selects/creates this object" for the ordinary `fundamentals` entry point
  (`docs/plans/product-completion-source-intake.md:41`); the context is built only by an
  installed operator launcher (same line).
- `WATCHLIST` `ADD`/`REMOVE` are owner-only decisions with verbatim reason (ledger spec §4,
  lines 367-371).
- Tests on `eqos_test_*` only, markers `pg`/`retained`; integration-weighted
  (`.claude/rules/python/testing.md`). Gate: `.claude/project/verification.md`.
- Crisp minimal code (owner 2026-10-14). Never open `stage4_holdout.yaml`, `stage4_manifest.yaml`,
  `data/holdout/`, `data/raw/onboarding/`; never print secrets or vendor readings.

## Investigation findings

Read-only, 2026-10-27. Live facts from `scratchpad/live-run-1/probe.py` and `high2.py`
(migrator role, read-only transaction, no values printed).

- **F1. The production refusal is the missing context, not the cutoff rule.** `run_command`
  refuses `--source-admission-*` without an `ApprovedIntakeContext` (`api/cli.py:219-226,
  252-257`), and `main` accepts one only through its keyword seam (`api/cli.py:588-602, 712`);
  no caller in `src/` passes it. Without the flags, local inputs take now as acquisition
  (`api/source_admission.py:338-345`) and refuse against every historical cutoff.
- **F2. The retrospective rule already exists and is the right one.** With a registered
  original and `--retrospective <manifest>`, admission switches to `retrospective_registered`
  and only then waives `bound > cutoff`, keeping identity, hash, rights and future-time checks
  (`source_admission.py:312-345`). The package comes from the manifest whose SHA-256 must equal
  `config/ledger_import.yaml`'s pin (`cli.py:567-585`, `published_package`
  `source_admission.py:390-404`); `check_blobs` applies the same publication time to every
  cited capture (`ledger/run_draft.py:606-629`). Registration times stay real.
- **F3. Retrieval does not predate the cutoffs.** Every retained original was retrieved
  2026-09-06T15:31Z–2026-09-07T04:05Z (`retrieval-manifest-v2.json` `retrieved_at`), after all
  four cutoffs (latest FY27_Q1 2026-07-31T10:14:41Z, `config/aparinds-fy27-q1.yaml:22`). So an
  ordinary (non-retrospective) live run is impossible for these quarters; each live draft
  carries the "Retrospective workflow demonstration" designation (`run_draft.py:642-648`). That
  label is honest and stays.
- **F4. The test-only analogue shows the full composition.** `Pilot.prepared` builds three
  `ApprovedIntakeBinding`s, an `ApprovedIntakeContext` and a locator, then runs with
  `--retrospective` (`tests/fundamentals/prep2b_support.py:207-282`). Production already has
  `stage_local_source` (capture + register, `api/source_intake.py:102-138`) and the
  descriptor-safe resolver (`source_admission.py:127-178`). The approved-context origin is
  specified: source ids and PDF pins from the quarter config, the XBRL pin from the accepted
  retrieval-manifest entry, rights from existing source-use authority
  (`docs/plans/product-completion-source-intake.md:39`). Live `evidence ingest` captures use
  `SnapshotRights(authority_refs=(manifest["authorization"],))`
  (`evidence/capture_intake.py:183, 238`).
- **F5. Transcript route is a thin wrapper.** `admit_transcript` (capture only, diagnostic
  first-party) is called only from tests (`evidence/first_party_ingest.py:388-407`;
  `prep2b_support.py:188-192`). `retained_intake_from_manifest(..., pdf_declaration=
  "transcript_pdf")` already binds a transcript (`capture_intake.py:143-185`), and
  `with_issuer_pdfs` declares it diagnostic-only (`api/watchlist_config.py:326-341`). The
  manifest has a `transcript` entry per run quarter; FY26_Q2's is filed at the cutoff instant
  (06-Nov-2025 12:05:34 IST = `2025-11-06T06:35:34Z`).
- **F6. No production route reaches `APPROVED` for a runtime draft.** `APPROVE` needs a
  `SUBMIT` head; `SUBMIT` is runtime-only (`ledger/lifecycle.py:58-87`). `lifecycle.submit`
  (`lifecycle.py:152-173`) has no caller in `src/` (`eqos-4j2.21`). The panel's
  `panel.review` (`ledger/panel.py:105-157`) has no CLI and no real adapter (`eqos-tqf`).
  `ledger decide` runs as the owner login (`api/ledger_cli.py:194`); an owner `APPROVE` would
  record a model's verdict as the owner's and lock the panel out of that chain (ledger spec
  §1, lines 196-197).
- **F7. Watchlist `ADD` is owner-only in spec and code.** Spec: lines 367-371 and O10 (line
  85). Code: `TRANSITIONS` `(W, ADD)` owner only (`lifecycle.py:84-86`); trigger
  `check_owner_watchlist` refuses any other role and needs a verbatim ruling and a coverage
  digest (`migrations/0026_watchlist.sql:44-79`). The digest needs an `ONBOARDED`/`PARTIAL`
  result in a completed batch (`0026:7-14`); every runtime draft needs `watchlisted`
  (`0026:81-105`).
- **F8. Coverage chain: two retained inputs, one network step.** All `coverage` actions run as
  the owner login (`api/coverage_cli.py:180-183`).
  - Registry: a retained Upstox instrument capture exists
    (`data/raw/upstox/instruments/complete/20260904T082313Z-459ec0544e40/`, the one the D7
    tests load, `tests/fundamentals/coverage_support.py:34-38`).
  - Onboarding: `batch` replays `<raw-root>/<SYMBOL>/gen-<n>` with no socket
    (`coverage_cli.py:316-339`; `api/onboard_cli.py:6-8`). Retained APARINDS generations exist
    under `data/raw/onboarding-dev/live-smoke/APARINDS/gen-{1,2,3}`; the D6 smoke onboarded
    APARINDS `PARTIAL` with every unit `VERIFIED` (`docs/workstreams/data-foundation/plans/D6.md:621-625`).
    `--acquire` is bound to the Stage 4 freeze protocol (`onboard_cli.py:8-14`) and is not used.
  - Screen run: only `coverage export` writes one, and it always fetches both vendors with
    session cookies from the environment (`coverage_cli.py:198-219`); there is no replay or
    owner-CSV route (`migrations/0034_screen_export.sql:9-12` keeps `OWNER_EXPORT` only for old
    rows). `declare_batch` needs an `NSE_EQ` `APARINDS` listing among the run's members
    (`coverage/screens.py:85-89, 287-299`). **Network acquisition is needed for this one step.**
- **F9. Live comparison runs fit; their `HIGH` items do not block.** Runs 1–4 are `COMPLETE`,
  `AS_KNOWN`, period ends 2025-09-30 / 2025-12-31 / 2026-03-31 / 2026-06-30, pinned dictionary
  v2, mapping set v6, alignment v2 = `PILOT_VERSIONS` (`cli.py:139`). Open `HIGH` items: run 1 ×6
  (cash-flow and balance-sheet keys), run 2 ×2 and run 3 ×4 (`current_tax`,
  `employee_benefits_expense`, `employee_cost_pct`), all `EXTRACTION_DISAGREE`, none disposed.
  `_admit` needs only `REQUIRED_ROLES` (revenue, total income, total expenses, PBT, PAT, basic EPS;
  `output/earnings_update.py:52-59`), so `OPEN_HIGH` (`evidence/admission.py:86`) cannot refuse
  a run. Exit 3 in the cutover log is `SUCCESS_WITH_OPEN_HIGH` (`compare/run_models.py:67-73`).
- **F10. Live holds:** captures = 4 run-quarter XBRLs + 4 results PDFs; 0 transcript captures; 0
  comparator captures; 0 rows in `registry_loads`, `registry_listings`, `screens`, `screen_runs`,
  `capture_batches`, `onboarding_records`, `batch_completions`.
- **F11. Quarter configs.** The pilot runs FY26_Q4 from `config/aparinds-fy26-q4-pg.yaml` (the
  frozen `-fy26-q4.yaml` has the uncorrected cutoff `16:13:48Z`) and the other quarters from
  their committed configs (`prep2b_support.py:65-70`); the catalog adds each quarter's PDFs
  (`prep2b_support.py:271`, `ledger_cli.py:230-235`).
- **F12. The pin check trusts the caller's root.** `_retrospective` reads
  `config/ledger_import.yaml` from `config.repo_root(config_path)`, the supplied config's
  grandparent (`api/config.py:581-583`, `cli.py:567-585`). A copied directory holding a
  self-consistent config, manifest and pin passes it. The launcher therefore needs its own anchor.
- **F13. Export reads are already gated by the watchlist; vendor formulas cannot name one company.**
  - `_read_missing` reads the other vendor only for an item whose NSE code is a stock in
    `--watchlist`. Any other item records `ReadGap.NOT_VERIFIED` with no request
    (`coverage_cli.py:251-266`, `screen_review.py:172-186`).
  - Open review items do not block `declare_batch`, which needs only APARINDS as a resolved
    `NSE_EQ` member (`screens.py:287-299`). They add only an `OPEN_SCREEN_REVIEW` retention hold
    (`retention/holds.py:76`).
  - Both exports are fetched before anything is recorded. A vendor refusal (no echo, a
    mismatched echo, no count, non-200) writes nothing (`coverage_cli.py:200-214`; D7 revision
    S3).
  - Screener's query fields are the 374 names in `docs/research/screener/ratio-library.md`, all
    metrics with no name, code or ISIN. `Number of equity shares` and `Face value` are among them
    (`:45, :75`).
  - The only Tijori fields shown working in retained evidence are `Market Capitalization`,
    `capex` and `Net Block` (Cr columns), joined with `AND` and `>`
    (`docs/research/screen-export-probe.md:101-108`; D7 revision S3).
  - No retained document shows `<` at either vendor.
- **F14. The draft commits before its artifacts are written.** `run_command` returns after the
  draft transaction; only then does `write_bytes_no_clobber(--out-json)` run, and `--out` is a
  plain overwrite (`cli.py:712-723`). An existing `--out-json` path therefore fails after a
  permanent draft.
- **F15. Rights authority.** The source-use authority is A05-DECISION-004 (private, personal,
  non-commercial; no redistribution:
  `docs/evidence/phase-0a/a-05-rights-decision-004-private-use.md`). Its runtime form is
  `SnapshotRights(use=PRIVATE_INTERNAL, redistribution=PROHIBITED,
  authority_refs=("A05-DECISION-004",))` (`contracts/snapshot.py:226-252`;
  `docs/evidence/product-completion/apar-current-source-intake-proof.json`
  `source_use_authority`). The manifest's `authorization` (A-02 v2 + A02-ATTEST-002) is the
  retrieval and suitability attestation (`product-completion-source-intake.md:39`).
  Manifest v2 (`c47866ce…`, `supersedes: retrieval-manifest.json`, with the 2026-10-14
  comparator `filed_at_nse` correction) is the accepted successor of the phase-0.5 manifest that
  line names, and it is the one `config/ledger_import.yaml` pins.

## Design (smallest that meets the goal)

1. **Operator launcher** (`fundamentals-operator`, new console script). It is the installed
   composition root that `product-completion-source-intake.md:39-41` names. Its trust anchor is
   installed code, not the caller's paths (F12). Module constants fix three things: the
   repository root (the installed package's own checkout), the manifest path and SHA-256, and
   each accepted quarter config with its exact byte SHA-256. Any other root, or changed config
   bytes, refuses before anything is read from the supplied paths. Every role's SHA-256 must be
   that quarter's anchored-manifest entry, so a config can select only accepted originals.
   Rights are A05-DECISION-004 (F15), from one shared constant `INTAKE_RIGHTS` that every
   retained-intake capture this plan writes uses: the launcher's three roles, `evidence
   transcript` and the comparator `evidence ingest`. The manifest's `authorization` stays
   retrieval provenance on the intake (`authority_ref`), never rights. Then it calls the
   existing `main(argv, intake_context=…)`. It has two verbs: `stage` (capture, register and write
   the locator) and `run` (passthrough). Admission code is unchanged; `--retrospective` stays
   mandatory for these quarters (F3). The intake store is a new protected directory, kept
   separate from the live snapshot root so that no unregistered `local_*` capture enters the
   backed-up evidence root. Losing it is harmless: a re-stage gives new real registration
   times, which retrospective admission does not use.
2. **`evidence transcript`**: one CLI action over `admit_transcript`.
3. **`ledger submit`**: runtime-role CLI over `lifecycle.submit`.
4. **`ledger panel`**: panel-login CLI over `panel.review`, with a `RecordedReviewer`. It
   returns Sol's verdict only when Sol's own preserved response carries a binding line naming
   the subject, the sealed digest and the narrative SHA-256 under review.
5. **Everything else is operational:** comparator ingests, the coverage chain (narrowest
   formulas, reads limited to APARINDS by a one-stock watchlist, F13), the owner's `ADD`, then
   the runs. Rehearsal and live write to separate output roots.

## Open decisions

| # | Decision | Recommendation |
|---|---|---|
| OD-1 | **Screen formula and network export.** A screen run needs `coverage export` (F8): live Screener and Tijori requests and a formula. A broad formula would record many members and trigger other-vendor reads. | **Resolved by orchestrator ruling (no owner step).** See "Screen ruling" below. Do not reuse `d7-stage4`. |
| OD-2 | **Who runs the owner-login coverage commands** (`registry`, `export`, `batch`). The spec calls them owner-run or owner-launched (lines 135, 362-365); the code only requires the owner login. | The orchestrator runs them as mechanical setup (autonomy directive). APARINDS is already the owner's chosen pilot company, and the batch names only APARINDS. The owner's single command is `ledger decide WATCHLIST 1 ADD`. |
| OD-3 | **Approval route** (F6). (a) A `ledger panel` recorded-verdict adapter, with Sol run by the orchestrator through T3. (b) Owner `ledger decide APPROVE` with Sol's text as the ruling: no new approval code, but it misattributes the decider and blocks later panel decisions on that chain. (c) The full `eqos-tqf` model-calling adapter. | (a): the smallest change that records the real decider (`PANEL`), provider, model and rationale. `eqos-tqf` stays open for (c). |
| OD-4 | **Rehearsal approvals and `ADD`.** The rehearsal DB needs an `ADD` and four approvals to reach FY27_Q1. | On `eqos_test_live1` only, the orchestrator records `ADD` with the ruling `REHEARSAL: …` and approves with verdict files labelled provider `rehearsal`. The adapter refuses a `rehearsal` record on any database not named `eqos_test_*` (Task 4). The deterministic gates still run. Real Sol verdicts and the owner's `ADD` happen only on live. |

**Screen ruling (OD-1).** This works from code, `config/screens.yaml` and retained docs only,
with no network (F13).
- **Neither vendor's formula language can select one company.** No retained document shows a
  name, code or ISIN field. A single-company formula is therefore unsupported, and the next
  narrowest option is used: bands on fields that are near-unique to APARINDS, with bounds taken
  from official retained filings, never from vendor readings.
- **Screener.** `Number of equity shares > <a> AND Number of equity shares < <b>`, where a and b
  are APARINDS's paid-up equity share count from the FY27_Q1 run XBRL, −0.5% and +0.5%.
  - The field name and `AND` are verified (ratio library; surface map `:247`).
  - Two things are inference: `<` and the field's unit (absolute shares assumed).
  - The expected result is APARINDS alone.
- **Tijori.** `Net Block > <n1> AND Net Block < <n2>`, where n1 and n2 are the consolidated net
  property, plant and equipment in ₹ Cr from the FY26_Q4 run XBRL, −30% and +30%.
  - The field, its Cr unit and `AND` are verified; `<` is inference.
  - `Market Capitalization` is left out because its bound would need a vendor reading.
  - `capex` is left out because its unit is unverified.
  - The result set is expected to hold other companies.
- **Isolation.**
  - Every other Tijori member is recorded in one live results capture: identity, segment and the
    Net Block column at fetch time.
  - No additional company request is made for any of those members. Local rendering still
    hydrates their rows from that retained results capture (`screen_review.py:241-259`), and
    each still records a `screen_other_vendor_reads` gap row. Before any automatic read, the
    permitted request set is fixed as {APARINDS} by passing a one-stock watchlist. A helper writes `$OUT/watchlist-aparinds.yaml`,
    holding config/watchlist.yaml's APARINDS stanza and top-level keys verbatim, and asserts
    that the loader returns exactly that stock. Every other pending item therefore records
    `NOT_VERIFIED` with no request.
  - Whether those other members include held-out companies cannot be checked under this plan's
    rules (the holdout files stay closed). That residual is stated, not resolved.
- **Fail-closed checks.**
  - A vendor that rejects a formula refuses before anything is written.
  - After the export, the Screener run must hold exactly one member, which resolves to the
    `NSE_EQ` APARINDS listing. Anything else is a stop that needs a ruling; re-exporting with
    another formula is a new screen entry and needs a ruling too.
  - The helper that computes the bounds prints only the two formula lines. The export's stdout
    (members and side-by-side values) goes to `$OUT/logs/C2.out` (mode 600) and is never pasted
    into a review brief or report; only ids and member counts are reported.

## Tasks

### Task 1: Operator launcher for historical source admission

Goal:
- `fundamentals-operator stage` registers a quarter's three pinned originals in a protected
  intake store and writes their locator.
- `fundamentals-operator run <run argv>` admits them as `retrospective_registered` and writes
  the draft.
- These refuse before any write and leave the intake store unchanged:
  - a `--config` or `--retrospective` path outside the installed root;
  - a `run` with no `--retrospective`;
  - an accepted config whose bytes changed;
  - a config whose pins are not the anchored manifest's entries.
- Below the launcher, admission still refuses `exceeds cutoff` for a context without
  `--retrospective` (F1, F2).
- Plain `fundamentals` behaviour is unchanged.

Files:
- Create: `src/fundamentals/api/operator_cli.py`
- Modify:
  - `pyproject.toml` (`[project.scripts]` `fundamentals-operator =
    "fundamentals.api.operator_cli:main"`);
  - `src/fundamentals/contracts/snapshot.py`: `A05_DECISION_004 = "A05-DECISION-004"` beside
    `A05_DECISION_005`, and, after `SnapshotRights`, `INTAKE_RIGHTS =
    SnapshotRights(authority_refs=(A05_DECISION_004,))`, the one rights composition (Tasks 1-2);
  - `src/fundamentals/evidence/capture_intake.py`: `retained_intake_from_manifest` takes a
    keyword `rights: SnapshotRights | None = None`. `RetainedIntake` gains a `rights` field,
    set to that argument or, when it is `None`, to today's
    `SnapshotRights(authority_refs=(authority_ref,))`. `stage_retained_member` writes
    `intake.rights`, replacing its inline composition (`:245`). `authority_ref` stays the
    manifest's retrieval provenance, and its docstring says so. The default keeps onboarding's
    `freeze <commit>` packages (`api/onboard_cli.py:358-376, 480`) unchanged. About 5 lines.
- Test: `tests/fundamentals/test_operator_cli.py`

Interfaces:
- Consumes:
  - `ApprovedIntakeBinding`, `ApprovedIntakeContext`, `stage_local_source`
    (`api/source_intake.py`);
  - `retained_intake_from_manifest` (`evidence/capture_intake.py`);
  - `load_config`, `PipelineSourceRefs`, `SnapshotRights`;
  - `write_bytes_no_clobber` (`api/artifact_writer.py`);
  - `cli.main`, `cli._build_parser`.
- Produces:
  - Constants: `INSTALLED_ROOT = Path(__file__).resolve().parents[3]`;
    `RETRIEVAL_MANIFEST = "data/raw/watchlist/aparinds/retrieval-manifest-v2.json"`;
    `RETRIEVAL_MANIFEST_SHA256 = "c47866ce…"` (full value);
    `ACCEPTED_CONFIGS: Mapping[str, str]`, mapping the four repo-relative quarter configs (F11,
    the FY26_Q4 entry `-fy26-q4-pg.yaml`) to their committed byte SHA-256s. `INTAKE_RIGHTS`
    is imported from `contracts/snapshot.py`, not redefined.
  - `approved_intake(config_path: Path, store_root: Path, *, root: Path = INSTALLED_ROOT) ->
    ApprovedIntakeContext`. `main` never passes `root`; the keyword exists only so tests can
    prove the byte checks against a tmp copy (the `intake_context` keyword-seam precedent).
  - `main(argv: list[str] | None = None) -> int`.
  - CLI `fundamentals-operator stage --config <yaml> --source-admission-store <dir>
    --out-manifest <path>` prints one line per role, `role\tsource_id\tcapture_id`.
  - CLI `fundamentals-operator run <the ordinary run argv>` requires both
    `--source-admission-*` flags and `--retrospective`.

Approach: `approved_intake` takes these steps, in order.
1. **Root and config.** Resolve `config_path` and refuse `unsupported root` unless its path
   relative to `root` is a key of `ACCEPTED_CONFIGS`. Refuse `config not accepted`
   unless the file's bytes hash to that entry's value.
2. **Manifest.** Read `root / RETRIEVAL_MANIFEST` and refuse unless it hashes to
   `RETRIEVAL_MANIFEST_SHA256`. Nothing is derived from the caller's directory, and
   `config/ledger_import.yaml` is not consulted (`cli._retrospective` still checks it).
3. **Retained intakes.** Build two with `retained_intake_from_manifest`: XBRL
   `xbrl-consolidated` plus PDF `results`, and PDF `transcript` with
   `pdf_declaration="transcript_pdf"`. These enforce one manifest entry per kind and the
   config-vs-manifest PDF pin. Require the XBRL source id to equal `config.xbrl.source_id`.
4. **Bindings and rights.** Both intakes are built with `rights=INTAKE_RIGHTS`. Bindings take
   the anchored manifest's SHA-256s and their rights from `intake.rights`. The manifest's `authorization` stays in the manifest as retrieval
   provenance, bound through its pinned hash and the draft's retrospective designation; it is
   never rights.
5. **Context.** Use the config bytes' SHA-256, the store anchor, and an input anchor at the
   config's `raw_dir`.

Then the two verbs:
- `stage` calls `stage_local_source` for each role with the binding's manifest-relative path,
  then writes `PipelineSourceRefs` from the three receipts with `write_bytes_no_clobber`.
- `run` parses the argv with the ordinary parser. It refuses `retrospective manifest required`
  unless `--retrospective` is present and resolves to `INSTALLED_ROOT / RETRIEVAL_MANIFEST`. This
  happens before `approved_intake` runs, builds the context from `--config` and
  `--source-admission-store`, and returns `cli.main(argv, intake_context=ctx)`.

No other flag, environment variable or file feeds the context. Target ≤ 100 lines.

Verification (test-first; slice `LIVE-RUN-1-T1`):
1. Write `test_operator_cli.py` before `operator_cli.py` exists.
2. `scripts/verify.sh red LIVE-RUN-1-T1 tests/fundamentals/test_operator_cli.py` must record
   every collected test as FAILED or ERROR. Any test passing at red is a contract gap: fix the
   test before implementing.
3. After implementing, `scripts/verify.sh gate LIVE-RUN-1-T1` must pass.
4. `uv run pytest tests/fundamentals/test_source_intake_cli.py
   tests/fundamentals/test_cli_temporal_admission.py tests/fundamentals/test_prep2b_admission.py`
   must be unchanged and green. That last check is the regression set, not part of the red proof.

Test seams: `operator_cli.main`; the `eqos_test_*` DB through the `Pilot` fixture
(`prep2b_support.py`, `imported=True`). Every refusal test asserts three things: its specific
message, unchanged `report_versions` and fact counts, and an intake store identical to its
state before the refused command. That state is a listing of paths and SHA-256s taken just
before the command. It is empty for refusals that come before any `stage`, and populated for
refusals that need staged captures (XBRL substitution (b), the cutoff regression). A test
therefore cannot pass merely because a module or flag is missing.
- *Stage + run FY26_Q2 (integration, medium):*
  - exit 0;
  - the draft's heading carries the retrospective designation with manifest `c47866ce…`;
  - its `AS_KNOWN` validation is all `MATCH`;
  - the JSON records `mode="retrospective_registered"` for all three roles;
  - every staged capture's rights equal `INTAKE_RIGHTS`, with `authority_refs ==
    ("A05-DECISION-004",)` and not the manifest's `authorization` string;
  - the anchored manifest's `authorization` is unchanged.
- *No `--retrospective` (launcher):* after `stage`, `operator_cli.main(["run", …])` without
  `--retrospective` refuses `retrospective manifest required`.
- *Cutoff regression (below the launcher):* after `stage`, `cli.main(run argv without
  --retrospective, intake_context=approved_intake(...))` refuses `source
  acquisition/first-seen/registration exceeds cutoff`. This proves the launcher's check is not the only guard. At red it fails
  because `operator_cli` (and so `approved_intake`) is absent.
- *Self-consistent replacement directory:* a tmp tree holding `config/` (the accepted config
  bytes), `config/ledger_import.yaml` repinned to a copied manifest, and that manifest with one
  `filed_at_nse` altered. Both `stage` and `run` refuse `unsupported root`; `run` passes the
  installed `--retrospective` path, so the earlier manifest refusal does not fire first.
- *XBRL substitution:*
  - (a) The same replacement tree with the quarter's `xbrl-consolidated` entry swapped for
    another quarter's SHA-256 refuses `unsupported root`.
  - (b) In the installed root, a hand-edited locator citing another quarter's registered XBRL
    capture refuses at admission's binding comparison, with no draft.
- *Changed accepted bytes (keyword seam):* in a tmp copy passed as `root`, (a) an
  accepted-name config with one byte changed refuses `config not accepted`, and (b) a manifest
  with one `filed_at_nse` changed refuses `manifest not accepted`.

Dependencies: None.

Risks:
- This is a trust-boundary change, hence test-first.
- Argv selects only which accepted quarter and which store; bindings and rights never come
  from argv or caller paths.
- Updating an accepted config means updating `ACCEPTED_CONFIGS` in a reviewed commit, which is
  the intended control.
- A WSL2 clock step-back can refuse with `clock moved backwards` (`eqos-hdz`). That refusal
  comes before the draft, so a re-run is safe.

### Task 2: `evidence transcript` action

Goal: `fundamentals evidence transcript …` registers a quarter's transcript PDF as a
diagnostic first-party capture (`NSE_TRANSCRIPT_PDF`) and prints its `capture_ref` id. A
repeat prints the same id and adds no row. A config whose transcript pin disagrees with the
manifest refuses `EXIT_REFUSED`.

Files:
- Modify: `src/fundamentals/api/evidence_cli.py`
- Test: `tests/fundamentals/test_transcript_cli.py` (new; the existing
  `test_transcript_admission.py` already passes and would void a red proof)

Interfaces:
- Consumes: `retained_intake_from_manifest` (with Task 1's `rights` keyword), `INTAKE_RIGHTS`,
  `admit_transcript`, `with_issuer_pdfs`, `BUILTIN_SOURCES`, `load_config`,
  `EvidenceRepository`.
- Produces: CLI `evidence transcript --retrieval-manifest <json> --issuer <symbol> --quarter
  <FYyy_Qn> --raw-root <dir> --snapshot-root <dir> --issuer-config <yaml>`; stdout
  `capture_ref\t<id>`; exit `EXIT_OK` or `EXIT_REFUSED` (same refusal set as `ingest`).

Approach: a second action parser. It builds the intake with `kinds={PDF: "transcript"}`,
`pdf_declaration="transcript_pdf"` and `rights=INTAKE_RIGHTS`, the catalog with `with_issuer_pdfs(BUILTIN_SOURCES,
load_config(issuer_config))`, and the runtime pool as in `_ingest`. It calls `admit_transcript`
and prints the id. The existing `ingest` action's `retained_intake_from_manifest` call also
passes `rights=INTAKE_RIGHTS` (one argument), so step X's comparator captures carry
A05-DECISION-004. This changes `evidence ingest` rights for new captures only; captures already
registered keep their recorded rights (level-1 reuse returns them unchanged), including live's
eight run-quarter captures (F10). Any existing test asserting the old `evidence ingest` rights
is updated in this task and named in its commit. Target ≤ 30 added lines.

Verification (slice `LIVE-RUN-1-T2`): `scripts/verify.sh red LIVE-RUN-1-T2
tests/fundamentals/test_transcript_cli.py` must record every test failed before the action
exists. Then `scripts/verify.sh gate LIVE-RUN-1-T2` must pass, and
`uv run pytest tests/fundamentals/test_transcript_admission.py` must stay green.

Test seams: `cli.main(["evidence", "transcript", …])` on an `eqos_test_*` DB with
`retained_support` inputs. - *Success and repeat:* two runs print the same id and leave one `capture_refs` row with
  surface `NSE_TRANSCRIPT_PDF`. The stored capture's rights equal `INTAKE_RIGHTS`
  (`authority_refs == ("A05-DECISION-004",)`), not the manifest's `authorization`.
- *Comparator rights:* `cli.main(["evidence", "ingest", …, "--member",
  "xbrl=xbrl-consolidated-comparator", …])` for one comparator quarter exits 0, and the stored
  capture's rights equal `INTAKE_RIGHTS`. It fails at red because `ingest` still writes the
  manifest's `authorization`.
- *Refusal:* another quarter's `--issuer-config` gives `EXIT_REFUSED`, its pin-mismatch message,
  and no new row.

Dependencies: Task 1 (`INTAKE_RIGHTS` and the `rights` keyword).

Risks: low. Level-1 reuse (`first_party_ingest.py:368-385`) makes it idempotent.

### Task 3: `ledger submit` action

Goal: `fundamentals ledger submit <version> --stock <s> --snapshot-root <dir> [--issuer-config
…]` moves a `DRAFT` to `IN_REVIEW` as the runtime role and prints `decision\t<id>` and
`sealed_digest\t<digest>`. A repeat, or a draft with version-level findings, exits
`EXIT_REFUSED` with nothing written.

Files:
- Modify: `src/fundamentals/api/ledger_cli.py`
- Test: `tests/fundamentals/test_ledger_submit_cli.py` (new; one file per task, so each red
  proof stays byte-identical through the phase)

Interfaces:
- Consumes: `lifecycle.submit`, `decision_sources`, `store.sealed_digest`.
- Produces: the `submit` action (constant `SUBMIT_ACTION = "submit"`), with the same composition
  root as `check` (runtime pool, no credential file).

Approach: an action parser and a ~15-line handler. Errors go through `LEDGER_FAILURES`, as the
other actions do. Update the module docstring's usage block.

Verification (slice `LIVE-RUN-1-T3`): `scripts/verify.sh red LIVE-RUN-1-T3
tests/fundamentals/test_ledger_submit_cli.py` (all failed: the action does not parse yet), then
`scripts/verify.sh gate LIVE-RUN-1-T3`.

Test seams: `cli.main(["ledger", "submit", …])` on a `Pilot` FY26_Q2 draft written through
Task 1.
- *Success:* status `IN_REVIEW`, and the printed digest equals `eqos.version_sealed_digest`.
- *Refusal:* a second call gives `EXIT_REFUSED` with no new `decisions` row.

Dependencies: Task 1 (the test's draft comes from the launcher).

Risks: low. Closes `eqos-4j2.21`.

### Task 4: `ledger panel` action with a recorded verdict

Goal:
- `fundamentals ledger panel <version> --verdict <json> --response <md> --stock <s>
  --snapshot-root <dir> [--issuer-config …]` decides an `IN_REVIEW` version as the panel
  login, through `panel.review`.
- The verdict comes only from Sol's preserved response (`--response`, the verbatim reply). It
  must contain exactly one binding line:

  ```
  EQOS-BINDING subject=REPORT_VERSION:<id> sealed_digest=<sha256> narrative_sha256=<sha256> verdict=<APPROVE|REQUEST_CHANGES|REJECT>
  ```

  The subject must be the argv version, the digest the version's current sealed digest, and the
  hash the SHA-256 of the exact narrative the panel gates.
- The verdict file carries only who answered (`provider`, `model`, `effort`, `brief_version`).
  It holds no verdict, digest or rationale, so a transcription cannot attach a verdict to a
  response that does not name it.
- `APPROVE` gives `APPROVED`, with a `panel_reviews` row whose rationale is the full response
  text.
- A `provider: rehearsal` file refuses unless `current_database()` starts with `eqos_test_`.
- Any mismatch, or a failing gate, refuses with no row.
- The whole production route FY26_Q2 → approval → FY26_Q3 draft passes end to end.
- No signatures and no model-calling adapter.

Files:
- Modify: `src/fundamentals/api/ledger_cli.py`
- Create: `src/fundamentals/ledger/recorded_reviewer.py`
- Test: `tests/fundamentals/test_ledger_panel_cli.py`

Interfaces:
- Consumes: `panel.review`, `Reviewer`, `ReviewOutput`, `Verdict`, `SubjectKind`,
  `decision_sources`, `load_login(PgRole.PANEL, …)`; Task 3's `submit`; Task 1's
  `operator_cli.main`.
- Produces:
  - `Responder` (frozen Pydantic: `provider`, `model`, `effort`, `brief_version`);
  - `binding(response: str) -> Binding`, which parses the single binding line or raises
    `DecisionRefusedError`;
  - `RecordedReviewer(responder: Responder, response: str)` satisfying `Reviewer`;
  - the `panel` action (`PANEL_ACTION = "panel"`), which prints `decision\t<id>`;
  - `REHEARSAL_PROVIDER = "rehearsal"`.

Approach:
- `RecordedReviewer.review(text, sealed_digest)` raises `DecisionRefusedError` unless the
  binding's `sealed_digest == sealed_digest` and `narrative_sha256 == sha256(text.encode())`.
  Otherwise it returns `ReviewOutput(binding.verdict, response)`.
- Before opening a write, the handler refuses unless:
  - the binding's subject is `REPORT_VERSION:<argv version>`;
  - a `rehearsal` provider runs on an `eqos_test_*` database.
- It then calls `panel.review(..., subject_kind=REPORT_VERSION, reviewer=…,
  **decision_sources(args))`.
- The narrative the orchestrator sends to Sol is `ledger export <id>` (the same bytes,
  `ledger/export.py:70-73`).
- Target ≤ 70 lines in total.

Verification (slice `LIVE-RUN-1-T4`): `scripts/verify.sh red LIVE-RUN-1-T4
tests/fundamentals/test_ledger_panel_cli.py` (all failed: no action, no module), then
`scripts/verify.sh gate LIVE-RUN-1-T4`.

Test seams: `cli.main(["ledger", "panel", …])`; panel and runtime pools of the test DB.
- *Approve:*
  - exit 0, status `APPROVED`, decider `PANEL`;
  - the review row's provider, model, effort and brief version equal the file's;
  - its rationale equals the response bytes;
  - the provider is `rehearsal` on `eqos_test_*`, which proves the label is accepted there.
- *Parametrized integration refusals:* each gives `EXIT_REFUSED` and leaves the `decisions` and
  `panel_reviews` row counts unchanged.
  - The response has no binding line, or two.
  - The binding names another version.
  - The binding names a stale digest.
  - The binding names the wrong narrative hash.
  - The version is not submitted.
- *Rehearsal label (small):* the label predicate refuses `rehearsal` for `eqos_live` and accepts
  it for `eqos_test_x`. Tests may not connect to a non-test database, so this case is not an
  integration test.
- *End to end (large):*
  - Task 1 stage + run FY26_Q2 → `ledger submit` → `ledger export` → a response containing its
    binding line → `ledger panel` `APPROVE` → Task 1 stage + run FY26_Q3.
  - The FY26_Q3 draft's predecessor is the approved FY26_Q2 runtime version.
  - Both quarters' guidance quote claims are `MATCH` (bound).
  - This is the integration proof of the whole live route.

Dependencies: Tasks 1, 3.

Risks:
- The orchestrator still writes the files to disk, so forging a response is operator power,
  like holding the owner login.
- The controls:
  - the verdict must sit in Sol's own text, bound to the subject, digest and narrative;
  - the preserved response is kept with its T3 `taskId`, and its full text is the rationale.
- Narrows `eqos-tqf` (recorded in its notes); does not close it.

### Task 5: Live operational sequence (orchestrator, no code)

Goal: live versions for FY26_Q2, FY26_Q3, FY26_Q4 and FY27_Q1 runtime updates, each `APPROVED`
by the panel in issuer-quarter order, each carrying `thesis_impact` and `observable_falsifiers`
with F5 against thesis 1.1.0. `db check-live` passes after every write step.

Dependencies: Tasks 1–4 committed; Sol phase-end `APPROVE` (`04-agent-stack.md`). The OD-1
ruling's `aparinds-coverage` entry is committed: config only, bounds from the helper below.

Helpers (scratchpad, read-only, migrator role, assert `current_database()`): A1's `counts.py`
and `digests.py`, `scratchpad/live-run-1/probe.py`, and `check_rehearsal.py` for check-live on
the rehearsal DB. Further helpers:
- `screen_bounds.py` reads the two official facts from the retained run XBRLs and prints only
  the two formula lines.
- `watchlist_one.py` writes `$OUT/watchlist-aparinds.yaml` (OD-1 ruling).
- `f5_check.py` is described at step R.

Paths:
- `RM=data/raw/watchlist/aparinds/retrieval-manifest-v2.json`,
  `RAW=data/raw/watchlist/aparinds`.
- Each environment has its own roots, with no path shared between rehearsal and live. `ENV` is
  `rehearsal` or `live`; `OUT=scratchpad/live-run-1/$ENV` holds `out/`, `verdicts/`,
  `responses/`, `counts/` and `logs/`.
  - Rehearsal: `SNAP=<scratch>/root`, `INTAKE=<scratch>/intake`, `LOC=<scratch>/locators`.
  - Live: `SNAP=data/raw/snapshots/v1`, `INTAKE=data/raw/source-intake/store`,
    `LOC=data/raw/source-intake/locators`.
- Every directory is created with `mkdir -m 700`, and the live `OUT` must not exist before
  step 0.
- Every command's stdout and stderr are teed to `$OUT/logs/<step>-<Q>.log`.
- `CFGS=--issuer-config config/aparinds-fy26-q2.yaml --issuer-config
config/aparinds-fy26-q3.yaml --issuer-config config/aparinds-fy26-q4-pg.yaml --issuer-config
config/aparinds-fy27-q1.yaml`.

**Per-quarter values** (configs F11; comparison runs from the 2026-10-27 live probe F9; step 0
re-reads them):

| Quarter | `--quarter` | `--config` | `--compare-run` | QoQ / YoY comparator XBRLs |
|---|---|---|---|---|
| FY26_Q2 | `Q2-FY26` | `config/aparinds-fy26-q2.yaml` | 1 | FY26_Q1 `a3c8…` / FY25_Q2 `c44a…` |
| FY26_Q3 | `Q3-FY26` | `config/aparinds-fy26-q3.yaml` | 2 | FY26_Q2 (run XBRL) / FY25_Q3 `3ba6…` |
| FY26_Q4 | `Q4-FY26` | `config/aparinds-fy26-q4-pg.yaml` | 3 | FY26_Q3 (run XBRL) / FY25_Q4 `9438…` |
| FY27_Q1 | `Q1-FY27` | `config/aparinds-fy27-q1.yaml` | 4 | FY26_Q4 (run XBRL) / FY26_Q1 `a3c8…` |

**Steps.** After every write step: check-live → exit 0, then counts → `$OUT/counts/<n>.tsv`. Deltas
must equal the rehearsal's exactly, except C2's, which is checked against expectations derived
from that environment's own export (below). The export is refetched, so membership can differ
between rehearsal and live.

0. **Preflight (live, read-only).**
   - check-live → 0; counts → `$OUT/counts/0.tsv`.
   - digests → 6 versions. Record thesis version 6's status (`APPROVED`) and sealed digest as
     `THESIS6`.
   - The probe shows runs 1–4 as in the table, 0 transcript/comparator captures and 0 coverage
     rows.
   - The vendor session variables named in `api/env_credentials.py` are present (names only,
     never values).
   - `screen_bounds.py` prints the OD-1 formulas, and the `aparinds-coverage` entry is committed
     before step 1, so rehearsal and live run the same entry.
1. **Rehearsal** (`ENV=rehearsal`).
   - `db backup --out <scratch>/set --snapshot-root data/raw/snapshots/v1`, then `db restore
     --set <scratch>/set/<backup-id> --database eqos_test_live1 --snapshot-root <scratch>/root
     --live-snapshot-root data/raw/snapshots/v1` (A1's form).
   - With `EQOS_PG_DB=eqos_test_live1` and the rehearsal roots, run steps T, X, C1–C4 and R
     exactly. Use the OD-4 rehearsal `ADD`, `provider: rehearsal` verdict files, and
     orchestrator-written responses carrying the binding line.
   - Record every exit code, printed id, count delta, claim state, `f5_check` result and
     guidance quote state.
   - Then drop the rehearsal DB. Nothing under the rehearsal `OUT` is read by a live step,
     except the recorded expectations.
   - Any unexpected result → failure branch.
2. **T — transcripts** (×4; `Q` ∈ FY26_Q2, FY26_Q3, FY26_Q4, FY27_Q1, config as in the table):
   `uv run fundamentals evidence transcript --retrieval-manifest $RM --issuer APARINDS --quarter
   <Q> --raw-root $RAW --snapshot-root $SNAP --issuer-config <config>` → exit 0,
   `capture_ref\t<id>`.
3. **X — comparator XBRLs** (×4; A1 prerequisite 3): `uv run fundamentals evidence ingest
   --retrieval-manifest $RM --issuer APARINDS --quarter <q> --period-end <d> --basis
   consolidated --raw-root $RAW --snapshot-root $SNAP --member
   xbrl=xbrl-consolidated-comparator --dictionary v2 --mapping-set v6` for (FY25_Q2,
   2024-09-30), (FY25_Q3, 2024-12-31), (FY25_Q4, 2025-03-31), (FY26_Q1, 2025-06-30) → exit 0
   each.
   - After T and X, a read-only check: every transcript and comparator capture this sequence
     wrote has rights `authority_refs == ("A05-DECISION-004",)`.
4. **C — coverage** (OD-2; owner login):
   - C1 `uv run fundamentals coverage registry --instruments
     data/raw/upstox/instruments/complete/20260904T082313Z-459ec0544e40/upstox_instruments.raw.json.gz
     --snapshot-root $SNAP` → `load`/`new_listings` lines. Read-only check: `registry_view` has
     `NSE_EQ` `APARINDS`.
   - C2 (OD-1 ruling).
     - `watchlist_one.py --out $OUT/watchlist-aparinds.yaml`, then `uv run fundamentals coverage
       export --screen aparinds-coverage --snapshot-root $SNAP --watchlist
       $OUT/watchlist-aparinds.yaml > $OUT/logs/C2.out` (mode 600; never displayed or pasted).
     - A read-only extract prints only `pair`, `screener_run` and `tijori_run` ids, member
       counts per vendor, and the APARINDS member line's listing id.
     - The Screener run must hold exactly one member, resolving to the `NSE_EQ` APARINDS
       listing. That run is `--screen-run`. Anything else → stop and rule.
     - **C2 expectations.** The same extract also reads, for the new pair only: `S` and `T`,
       the member counts per vendor; `I`, the count of its `screen_review_items` (none is
       disposed, so all are pending); and its `screen_other_vendor_reads` rows. Of C2's counts
       delta:
       - `screen_members` must be +(S + T);
       - `screen_other_vendor_reads` must be +I, one row per review item, gaps included;
       - `capture_refs`, `capture_addresses` and `retention_classes` must each be the
         rehearsal's C2 delta less its `R`, plus this export's `R` (each stored read inserts one
         of each: `capture_retention.py:80`, `0027_retention_classes.sql:70`). `R` is the number
         of read rows with a capture, and it must be 0 or 1; if 1, that row is APARINDS's item,
         which is a review item only when one vendor's run lacks it;
       - every other table's delta must equal the rehearsal's C2 delta (screens, runs, pairs
         and results captures do not depend on membership).
       - Every non-APARINDS read row's gap must be `NOT_VERIFIED` or `MEMBER_UNRESOLVED`.
       Rehearsal records its own `S`, `T`, `I` and `R`; live is checked against live's.
   - C3 `uv run fundamentals coverage batch --screen-run <id> --members APARINDS --raw-root
     data/raw/onboarding-dev/live-smoke --snapshot-root $SNAP` → `batch\t<id>`, `APARINDS\tPARTIAL
     run <id>` (or `ONBOARDED`), `complete\tTrue`.
   - C4 **Owner step (the only one):** the owner runs `uv run fundamentals ledger decide
     WATCHLIST 1 ADD` and types the verbatim reason on stdin → `decision\t<id>`. Read-only
     check: `eqos.watchlisted(1)` is true.
5. **R — runs, in order FY26_Q2 → FY27_Q1, each approved before the next:**
   - **Output preflight.** None of `$LOC/<Q>.json`, `$OUT/out/<Q>.json`, `$OUT/out/<Q>.md` or
     `$OUT/out/<Q>-v*.md` exists, and `$OUT/out` and `$LOC` are writable mode-700 directories
     of this environment. Otherwise stop before any write (F14).
   - `uv run fundamentals-operator stage --config <config> --source-admission-store $INTAKE
     --out-manifest $LOC/<Q>.json` → 3 lines.
   - `uv run fundamentals-operator run --issuer APARINDS --quarter <token> --config <config>
     --source-admission-manifest $LOC/<Q>.json --source-admission-store $INTAKE --retrospective
     $RM --compare-run <n> --snapshot-root $SNAP --watchlist config/watchlist.yaml $CFGS
     --out-json $OUT/out/<Q>.json --out $OUT/out/<Q>.md` → exit 0,
     `run_draft_written version=<v>`.
   - `uv run fundamentals ledger check --version <v> --stock APARINDS --snapshot-root $SNAP
     $CFGS` → every claim `MATCH`/`MATCH_UNTRUSTED`, guidance quotes bound.
   - **F5 gate before submission:** `f5_check.py --version <v> --thesis-digest $THESIS6`
     (read-only; prints only pass/fail per check and the status label). Every check must pass:
     - (a) The draft binds thesis version 6, whose sealed digest is `THESIS6` (recorded at step 0).
     - (b) The `ETR_LABEL` calculation line cites this quarter's run-XBRL filed `tax_expense`
       and `profit_before_tax` facts, and both operands' trust state is `MATCH`.
     - (c) `thesis.F5` cites `THESIS_CLAIM` on version 6's `falsifier.F5` row with digest
       `THESIS6` (RESEARCH-1 plan:550-554).
     - (d) The ETR and F5 lines carry exactly the disclosure qualifiers the rehearsal recorded.
     - (e) The helper recomputes filed tax ÷ PBT × 100 in `Decimal` from the cited facts,
       quantizes it to `Decimal("0.01")` with the default context, as production stores it
       (`output/pnl_lines.py:39`), and applies version 6's predicate as read from version 6 (`filed_effective_tax_rate_pct GT
       26.74`, RESEARCH-1 plan:736-737). The resulting
       status is `WEAKENED` or `HELD` and equals the draft's.
     - F5 `UNRESOLVED`, any other operand trust state, or any failed check is an explicit stop:
       no submit; the orchestrator rules.
   - `uv run fundamentals ledger submit <v> --stock APARINDS --snapshot-root $SNAP $CFGS` →
     `sealed_digest\t<d>`.
   - `uv run fundamentals ledger export <v> --out $OUT/out/<Q>-v<v>.md`; `N=$(sha256sum` of
     that file`)`.
   - Fresh Sol round (T3 `delegate_task`, `reasoningEffort: high`, distinct `clientRequestId`)
     on that narrative, `REPORT_VERSION:<v>`, `<d>`, `N` and the A-04/B-02 brief.
     - The brief requires the reply to end with the Task 4 `EQOS-BINDING` line, restating those
       three values and its verdict.
     - Save the reply verbatim to `$OUT/responses/<Q>.md` and its `taskId` to
       `$OUT/responses/<Q>.task`.
     - Write `$OUT/verdicts/<Q>.json` with the responder fields only (`provider: codex`,
       `model: gpt-6.1-sol`, `effort: high`, brief version).
   - `uv run fundamentals ledger panel <v> --verdict $OUT/verdicts/<Q>.json --response
     $OUT/responses/<Q>.md --stock APARINDS --snapshot-root $SNAP $CFGS` → `decision\t<id>`;
     status `APPROVED`.
     FY26_Q2's imported `HISTORICAL` head is now superseded (A1 "Chain root").
6. **Close.** `ledger export --stock APARINDS --out $OUT/export --status-notes`;
   post-run `db backup`; bead notes record every id and the backup set id.

**Failure branch.** Stop at the first deviation. Do not re-run a write step that partly
committed. Preserve the output, a fresh counts file and the digests. Then:
- A step whose writes are idempotent by design (T, X, C1, the run before its draft commit:
  traces, facts and selections) may be re-run once after the cause is fixed.
- A refused run leaves the period head unchanged (preflight is read-only; the draft write is one
  transaction, PREP-3 S3e).
- **Draft committed, artifact publication failed.** The run exits non-zero after the draft
  transaction (`--out-json` or `--out` write failed, F14), or an artifact is missing. Never
  re-run it.
  - Take `<v>` from the logged `run_draft_written` line. If the line is absent, take it from a
    read-only probe of the quarter's newest runtime `DRAFT`, confirming the counts delta is
    exactly one draft.
  - Publish the narrative with `ledger export <v> --out $OUT/out/<Q>-v<v>.md`, the same bytes
    the panel gates. Record the JSON artifact as not published; it is not regenerated.
  - Continue from `ledger check` for that `<v>`.
- Sol `REQUEST_CHANGES`/`REJECT`, an unbound quote (`eqos-0eu`), an onboarding outcome other
  than `ONBOARDED`/`PARTIAL`, or any unexpected delta: no further writes; the orchestrator
  rules.

Risks: every write is permanent. The screen export depends on vendor availability and
membership at fetch time. The onboarding replay writes 2026-09-04 vendor captures into live
under their real times.

## Verification summary

Proof strategy: one slice per code task, each with a red proof and its own test file. A test
file belongs to exactly one slice, so every red proof stays byte-identical through the phase.
Every target test must fail at red: success tests because the entry point is absent, refusal
tests because they assert their specific message and unchanged rows. No refactor baseline is
used. Regression suites are run beside the gate, never inside a red proof.

| Task | Before implementing | After | Signal |
|---|---|---|---|
| 1 | `scripts/verify.sh red LIVE-RUN-1-T1 tests/fundamentals/test_operator_cli.py` | `scripts/verify.sh gate LIVE-RUN-1-T1`; source-intake/temporal/prep2b suites | all red, then gate pass; suites green |
| 2 | `scripts/verify.sh red LIVE-RUN-1-T2 tests/fundamentals/test_transcript_cli.py` | `scripts/verify.sh gate LIVE-RUN-1-T2`; `test_transcript_admission.py` | all red, then pass; green |
| 3 | `scripts/verify.sh red LIVE-RUN-1-T3 tests/fundamentals/test_ledger_submit_cli.py` | `scripts/verify.sh gate LIVE-RUN-1-T3` | all red, then pass |
| 4 | `scripts/verify.sh red LIVE-RUN-1-T4 tests/fundamentals/test_ledger_panel_cli.py` | `scripts/verify.sh gate LIVE-RUN-1-T4` | all red, then pass; e2e FY26_Q2→Q3 included |
| phase end | — | `VERIFY_SCOPE_BASE=<pre-phase commit> scripts/verify.sh gate LIVE-RUN-1-T<n>` for n = 1..4 at HEAD | four passes |
| 5 | — | check-live after each write; rehearsal-equal deltas; `ledger check` and `f5_check` per version | exit 0; equal; all `MATCH`; F5 checks pass |

## Self-review

- **Coverage.** A1 prerequisite 1 → Task 1. Prerequisite 2 → Task 2 + step T. Prerequisite 3 →
  step X. Prerequisite 4 → steps C1–C4. Prerequisite 5 → step R, which also needs Tasks 3–4:
  the approval gap A1 did not list (F6).
- **Placeholders.**
  - `<id>`, `<v>`, `<d>` and `N` are values printed or computed by the preceding command.
  - The formula bounds `<a>`, `<b>`, `<n1>` and `<n2>` come from `screen_bounds.py`, over
    official XBRL facts (OD-1 ruling).
  - No TBDs.
- **Names.** `approved_intake` and `operator_cli.main` (T1) are consumed by T4's e2e;
  `SUBMIT_ACTION` (T3) by T4; `Responder`, `binding` and `RecordedReviewer` only in T4;
  `A05_DECISION_004` and `INTAKE_RIGHTS` (T1, `contracts/snapshot.py`) are consumed by the
  launcher, `evidence transcript` and `evidence ingest` (T2), through the `rights` keyword on
  `retained_intake_from_manifest` (T1).
- **Gaps named.** No migration. Docs: the T3/T4 usage lines go in `ledger_cli.py`'s docstring,
  and T1's launcher in `.claude/project/verification.md`'s D3 paragraph (one line). Beads:
  close `eqos-4j2.21` at T3; add T4's narrowing to `eqos-tqf`'s notes; close `eqos-dna` after
  step 6. Dashboard refresh after each committed task (owner preference).

## Review record

gpt-6.1-sol: r1 REQUEST_CHANGES (7), r2 REQUEST_CHANGES (3), r3 REQUEST_CHANGES (1 P2: C2 companion
tables; 1 note: copied-root `run` test path). Not converged after 3 rounds, so the orchestrator
ruled (agent-stack rule 5, 2026-10-27): both are applied verbatim as Sol specified them, with no
other change. The plan is approved on that ruling. The phase-end Sol review covers the
implementation.

