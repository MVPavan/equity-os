# PREP-7 Implementation Plan — frozen pilot manifest

**Origin:** `docs/backend-roadmap.md:73`, row PREP-7. Title: "Frozen pilot manifest". Done when: "Expected values
hand-verified from the four quarters' filings, reviewer-approved, committed before the pilot test;
per quarter the IST-correct source cutoff, the reviewed package (ids + sha256) and the
retrospective designation". Other sources:
- §4 "Expected values come from the frozen pilot manifest (PREP-7), never from code output"
  (`docs/backend-roadmap.md:96-97`).
- PILOT-1 and PILOT-2 (`:101-102`).
- The retrospective contract in `docs/plans/PREP-2b.md:48-67`.
- The source-of-truth matrix, Gap 1: "Frozen inputs remain PREP-7" (`docs/blueprint/source-of-truth-matrix.md:33,50`).

Status: **approved — gpt-6.1-sol APPROVE, 2026-10-19** (plan r1 REVISE 12 → r2 REQUEST_CHANGES 2+2 notes → r3 APPROVE; fresh closing r1 REQUEST_CHANGES 7 → r2 REQUEST_CHANGES 2 → r3 APPROVE; resolutions below).

**Goal:** one Sol-approved, hash-pinned YAML,
`tests/fundamentals/fixtures/data_foundation/pilot_manifest.yaml`, produced by an audited authoring
process. For each pilot quarter (PQ0–PQ3) it freezes:
- the IST-correct source cutoff, located at its NSE filing lexeme;
- the reviewed source package: the config-pinned originals and comparators, as ids plus sha256;
- the retrospective designation, with the facts that make it true;
- the expected numerical claims, located in the filings and bound to the meaning each claim key requires.

The existing frozen-manifest suite validates it from the retained bytes, and `holds.yaml` holds its
inputs. The pilot test that will consume it can only be committed after it is approved, and both
the test suite and the pilot test's own preflight enforce that order.

**Out of scope:**
- Building the pilot test itself (`eqos-4j2.8` / PREP-8). This plan fixes the test's path and how it consumes the manifest.
- Guidance quote claims (open question 3).
- Shareholding values (open question 4).
- Owner review time (PILOT-12).
- Any `src/` change or migration.

**Constraints:**
- `config/aparinds-fy26-q4.yaml` stays byte-identical.
- Migrations 0001–0040 are immutable. There is no new migration.
- Never open `stage4_manifest.yaml`, `stage4_holdout.yaml`, `data/holdout/` or `data/raw/onboarding/`.
- Never print bodies from `data/raw/screen-exports/`.
- Never touch `.env`, `~/.secrets` or `equity_os`.
- No value may come from code output. That excludes `data/reports/**`, the earnings updates, the ledger and any `fundamentals` run.
- `tests/fundamentals/test_frozen_manifests.py` stays within the mandatory 800-line cap (`coding-style.md`, `scripts/verify.sh:431`).
- Owner, 2026-10-14: build the smallest thing that meets the acceptance.

## Findings (verified in code)

1. **The frozen-manifest machinery already does almost everything.**
   - `tests/fundamentals/test_frozen_manifests.py:46` globs every `*_manifest.yaml` in the fixtures
     directory, and `:55` excludes only the opaque stage4 file. A new manifest there is therefore
     validated automatically:
     - the header records `hand_verification` and reviewer `gpt-6.1-sol` (`:531-535`);
     - every header source matches its sha256 (`:540-543`);
     - every lexeme is at its locator (`:548-555`, `check_locator` `:296`);
     - every `expr` is exact (`:659-681`);
     - every `v` follows from its lexemes (`:684-689`, `check_values` `:503`);
     - it carries a dated APPROVE over its own payload (`:775-777`, using `manifest_support.py:259-272`).
   - The locator shapes it needs already exist (`:72-88`):
     - `xbrl` (concept, context, unit, decimals, lexeme, period, optional dims);
     - `pdf` (page, label row, header-verified column);
     - `field` (a JSON/YAML value at a path, read by `field_at`, `:338-343`).
   - These checks prove a lexeme is *somewhere*; nothing binds a claim key to the concept, period
     or package member it must come from. That binding is new (Decision 3).
2. **Ordering is enforced from history only.** `test_approved_payload_preceded_its_e2e`
   (`test_frozen_manifests.py:759-772`) finds the commit that first added the e2e named in `E2E`
   (`:56-65`) and asserts that its parent holds the manifest with its own APPROVE over the
   current payload (`manifest_support.py:268-272`). It returns early while the e2e file does not
   exist, so it cannot stop an uncommitted pilot run that precedes the manifest commit. Today
   `E2E[...]` raises `KeyError` for an unlisted manifest name, so a `pilot` entry is required.
3. **The holds list.**
   - `config/retention/holds.yaml:6-12` lists the public manifests.
   - `test_retention_holds.py:474-483` (H7) requires it to equal the public glob minus the opaque file.
   - `retention/holds.py:138-167` turns every 64-hex string in a listed manifest into a
     `MANIFEST_INPUT` hold root, so the manifest's package hashes hold those captures.
   - The ledger Stage 5 e2e runs with a temporary `holds.yaml` that has `manifests: []`
     (`ledger_stage5_manifest.yaml:38`), so new roots do not disturb its frozen hold sets.
4. **IST cutoffs.**
   - `evidence/capture_intake.py:128-140` (`parse_filed_at`) reads `DD-Mon-YYYY HH:MM:SS` as Asia/Kolkata wall time and converts it to UTC.
   - The cutoff is the quarter's transcript `filed_at_nse` (`test_prep2b_cutoffs.py:18-35`).
   - Configs record it as `quarter.knowledge_cutoff` (line 22):
     - Q2 `2025-11-06T06:35:34Z` (IST 12:05:34);
     - Q3 `2026-02-04T09:18:22Z` (IST 14:48:22);
     - Q4 `2026-06-04T10:43:48Z` in the `-pg` copy (IST 16:13:48);
     - Q1 FY27 `2026-07-31T10:14:41Z` (IST 15:44:41).
   - The frozen `aparinds-fy26-q4.yaml` keeps the old UTC misreading, `16:13:48Z`. That is why the pilot runs Q4 from `-pg` (`prep2b_support.py:55-60`).
5. **The retrospective designation.**
   - The designation is `--retrospective <retrieval manifest>`, which must hash to `config/ledger_import.yaml:6` (`c47866ce…`) (`api/cli.py:363-385`).
   - `published_package` (`api/source_admission.py:390-404`) maps each original's sha256 to its earliest IST-parsed NSE publication.
   - Admission accepts a registered original published by the cutoff (`source_admission.py:326-331`).
   - The draft records `Retrospective(manifest_sha256, published)` (`ledger/run_draft.py:140-147`), and the heading prints both cutoffs (`:544-567`).
   - Every retrieval-manifest entry carries `filename`, `kind`, `quarter`, `filed_at_nse`, `retrieved_at` and `sha256`; the top level has `retrieved_at_utc_date: 2026-09-06`.
6. **The package members per quarter** come from the config pins (`config/aparinds-*.yaml`) and the retrieval manifest:
   - results PDF and transcript PDF, each with `source_id` and `sha256` (e.g. `aparinds-fy26-q2.yaml:28-38`);
   - the current XBRL, with `source_id` and a `local_path` but **no `sha256`** (`:40-43`);
   - the `qoq` and `yoy` comparator XBRLs, each with `local_path`, `sha256` and period (`:99-110`).

   | Quarter | XBRL | Results | Transcript | QoQ comparator | YoY comparator |
   |---|---|---|---|---|---|
   | FY26_Q2 | `90baae0b` | `8be1b8de` | `c9ed50d3` | FY26_Q1 `a3c8d9d6` | FY25_Q2 `c44ac376` |
   | FY26_Q3 | `87a5dd95` | `2f9c6d5a` | `66df508c` | FY26_Q2 `90baae0b` | FY25_Q3 `3ba61227` |
   | FY26_Q4 | `be8ef651` | `17f5bc04` | `69aba177` | FY26_Q3 `87a5dd95` | FY25_Q4 `94387374` |
   | FY27_Q1 | `f76a131a` | `c0c2b2fa` | `78a312c8` | FY26_Q4 `be8ef651` | FY26_Q1 `a3c8d9d6` |

   Every member's `filed_at_nse` is at or before its quarter's transcript time. The pilot quarters
   are exactly `config/ledger_import.yaml` `earnings_updates: [FY26_Q2, FY26_Q3, FY26_Q4, FY27_Q1]`.
7. **The numerical claim keys a run emits: exactly 46 per quarter.**
   - 6 `fact.<role>` (`run_draft.py:402`), for the `REQUIRED_ROLES` (`output/earnings_update.py:52-59`, `BASIC_EPS` `:58`):
     `revenue`, `total_income`, `total_expenses`, `profit_before_tax`, `profit_for_period`, `basic_eps`.
   - 36 `cmp.<role>.<qoq|yoy>.<prior|abs|pct>` (`run_traces.py:317-345`): `prior` a figure,
     `abs` `run.difference` (current − prior), `pct` `run.change_pct` ((current − prior) / prior × 100,
     `run_traces.py:9`), rounded to `RUN_PERCENT_PLACES = 2` with `ROUND_HALF_EVEN`
     (`contracts/comparative.py:17`, `run_traces.py:342`).
   - 4 `calc.1..calc.4`, numbered by `update.calculations` order (`run_traces.py:358`), which is
     gap, tax, ETR, headline (`api/pipeline_steps.py:190-197`):
     - `calc.1` other-income gap = total income − revenue (`run.difference`);
     - `calc.2` the filed tax expense, a figure (`run_traces.py:370-373`). No results PDF prints a
       total-tax cell, only its components (current, deferred, earlier-years tax);
     - `calc.3` ETR = tax / PBT × 100, quantized to `0.01` under the default decimal context,
       which rounds `ROUND_HALF_EVEN` (`output/pnl_lines.py:39`);
     - `calc.4` headline PBT = PBT + share of associates (`run.sum`).
   - The share of associates is **an operand, not a claim**: the ledger binds it lazily as
     `headline − PBT` (`run_traces.py:381`). PBT is before associates.
   - Guidance claims are source quotes from the transcript, built by `_quote` (`run_draft.py:439`,
     `CitationKind.SOURCE_QUOTE` `:456`). They join the same claim collection as the 46
     (`run_draft.py:255-257`), so a consumer must filter them out by citation kind.
8. **PILOT-1 and PILOT-2's PQ0 expectations are already frozen and approved** in
   `stage1_manifest.yaml` (approved 2026-10-14):
   - PBT `340.56` (`:1357`) and `340.53` (`:1450`);
   - OPM `C7_OPM.spec_literal_2dp: '8.06'` (`:667-678`);
   - the pre-registered Screener opex gap `pre_registered.H3`, with outcome `{pair: ANOMALY, triage: NOISE, queue: none}` (`:241-271`).
9. **The PDF text layers locate the lexemes in all four quarters.** pymupdf finds the expected
   figure lexemes as whole words on pages 3–4 of each results PDF. This was probed, not
   asserted. `eqos-ghv` (PQ3 PDF identity and statement-block failure) is a parser problem, not
   a missing text layer.
10. **Interval precision differs by representation.** `reading` (`test_frozen_manifests.py:186-198`)
    gives an XBRL fact a half-width of `10^-d / 2` and a PDF lexeme its printed precision, so a
    coarser XBRL `decimals` can make the XBRL interval wider than the PDF's while the displayed
    values agree (PQ0 PAT and PQ2 PBT, per Sol r1). Containment is therefore the wrong predicate.
11. **The citation contract.** `allowed_captures` (`ledger/run_draft.py:505-510`) lets a run cite
    its own originals, the captures cited by the approved prior's `Prior.entries` (`run_draft.py:135`;
    today only its guidance quotes, `:211-217`), and in a rework the blobs its carried claims rest
    on. Nothing else.
12. **The PREP-8 slot.** `scripts/verify_project.sh:10` has `PILOT_TARGET=""`, and `:65` runs it. No pilot test exists.
13. **The 800-line cap is at its limit.** `test_frozen_manifests.py` is 800 lines now. The
    verify gate escalates any hashed test file over 800 (`scripts/verify.sh:431-435`).

## Decisions

1. **"Hand-verified" means an audited, locator-verified transcription. No human read the filings.**
   This follows the precedent of every approved manifest (`stage1`, `stage2`, `ledger_stage1-5` headers):
   - A throwaway authoring aid (in `scratchpad/`, never committed) reads only the retained
     filing bytes and the inputs on its explicit `INPUTS` list (lxml, pymupdf, json, yaml). It
     never imports `fundamentals` or a repo test module, and never reads code output.
   - The aid's complete source and its `INPUTS` list are **review inputs** for Sol. Before
     approval, the orchestrator regenerates the manifest fresh from the reviewed aid and requires
     the result to be byte-identical to the reviewed draft (Task 3). This makes the authoring
     auditable. It does not make copying numbers impossible: `-I` does not restrict file reads,
     and only review shows that the aid computes from bytes rather than embedding values.
   - Every expected figure is a verbatim XBRL lexeme at a complete locator, bound to the concept,
     package member, period, dimensions and unit its claim key requires (Decision 3). Each
     current-quarter figure is also cross-checked against the results-PDF lexeme at a header-verified cell.
   - Every derived value is recomputed by the check from its prescribed operands and formula.
   - The suite re-checks all of this from the raw bytes on every run. Sol approves the payload.
   - No model computes or invents a number: the aid's code computes, and the test re-computes.
   - The owner does not read the filings for PREP-7. The owner already confirmed the PQ0 starting
     figures on 2026-10-12 (`backend-roadmap.md:91`), and their time is reserved for PILOT-12.

   The header's `hand_verification.method` says exactly this, including "no human read the filings".
2. **The PDF is the independent cross-check, for current figures only.** The XBRL and the PDF are
   separate issuer representations. `eqos-6so` shows that an XBRL tag can be wrong, so a
   PDF/XBRL disagreement fails the manifest. Agreement is **precision-aware interval overlap**
   (`xbrl_lo <= pdf_hi and pdf_lo <= xbrl_hi`, both from `reading`), not containment (Finding 10).
   PQ0 PAT and PQ2 PBT, whose XBRL interval is wider than the PDF's, must pass. Tax (`calc.2`) has
   no single PDF cell, so its XBRL interval must overlap the **sum** of its located PDF component
   cells' intervals (as `expected_interval` sums `operands`, `test_frozen_manifests.py:205-207`).
   A component printed as a zero marker (the check module's literal `ZERO_MARKERS = {"-"}`) is
   still located, and `check_pdf` (`:282`) proves the cell holds it; it reads as exact 0. Any other
   non-numeric lexeme fails closed. Prior-period figures are XBRL-only (limitation 2).

   `check_pdf` proves only that a lexeme sits under a declared header, not what the header
   means. Each PDF cell is therefore bound by fixed literal tables in the check module, filled in
   Task 2 from the PDFs and reviewed by Sol:
   - `src` is the label whose header sha256 equals **this quarter's** `results_pdf` member;
   - the page carries the consolidated statement title `PDF_SCOPE[Q]` exactly once (`label_rows`,
     `test_frozen_manifests.py:266`), so a standalone page is refused;
   - `pdf_columns[src][pg].cols[col].header` equals `PDF_CURRENT[Q]`, the current-quarter header,
     which `check_pdf` then authenticates on the page;
   - `label` (and `n`) equal `PDF_ROW[role]` for the six roles and the share of associates;
   - `calc.2` `pdf_parts` labels equal the set `PDF_TAX_ROWS[Q]` exactly, each once.
3. **The claim set per quarter is exactly Finding 7's 46 keys, each bound to its meaning.**
   The check module holds one literal binding table; the manifest cannot declare its own:

   | Key | Kind | Bound to |
   |---|---|---|
   | `fact.<role>` | figure + PDF cell | package member `xbrl`; concept `ROLE_CONCEPT[role]`; period = the quarter config's `period_start..period_end`; no dims; the role's unit |
   | `cmp.<role>.<k>.prior` | figure | package member `<k>` (`qoq`/`yoy`); same concept local name (comparators match by local name, `run_comparatives.py:98-108`); period = config `comparators.<k>.period_start..period_end`; no dims; same unit |
   | `cmp.<role>.<k>.abs` | derived | `fact.<role> − cmp.<role>.<k>.prior` |
   | `cmp.<role>.<k>.pct` | derived | `(fact.<role> − prior) / prior × 100`; expected emitted value = exact `v` quantized to `0.01`, `ROUND_HALF_EVEN` |
   | `calc.1` | derived | `fact.total_income − fact.revenue` |
   | `calc.2` | figure + summed PDF component cells | member `xbrl`; the concept the config maps for `TaxExpense` (`api/config.py:47`); current period; no dims. `pdf_parts`: one or more cells, all on the results-PDF member, one page, and the `col` of the `fact.<role>` PDF cells |
   | `calc.3` | derived | `calc.2 / fact.profit_before_tax × 100`; expected emitted value = exact `v` quantized to `0.01`, `ROUND_HALF_EVEN` (Finding 7) |
   | `calc.4` | derived | `fact.profit_before_tax + aux.share_of_associates` |
   | `aux.share_of_associates` | operand, not a claim, figure + PDF cell | member `xbrl`; the concept the config maps for `ASSOCIATES_SHARE_CONCEPT` (`api/config.py:48`); current period; no dims |

   - "Bound to a member" means the locator's `src` label names the header source whose sha256
     equals that member's sha256.
   - **Value shape.** A figure node's keys are exactly `{v, iv, at}` plus `pdf` or `pdf_parts`
     where its row requires one; a derived node's are exactly `{expr, v}`. `check_values` (`:503`)
     checks only nodes that carry `iv`, so a dropped `iv` must fail the shape check. `v` equals its
     XBRL lexeme directly: `Fraction(lex) / UNIT_SCALE[u]`, with the fixed `UNIT_SCALE =
     {INR: 10**7, INRPerShare: 1}` (crore and per share). No pilot locator may carry `sign`;
     `reading` (`:186`) would apply it silently, and direct transcriptions need none.
   - Derived nodes carry `expr` and the exact `v` only. The check recomputes `v` from the bound
     operands' `v` with the prescribed formula; there is no self-declared `of`/`formula`.
   - The only rounding is the two `0.01 ROUND_HALF_EVEN` rules above. Both are exact-fraction
     quantizations; the run's ETR divides in the 28-digit default context first, which can differ
     only at a 28-digit tie (limitation 7).

   That is 46 claims plus 1 operand per quarter, 188 nodes in total.
4. **The "reviewed package" is the input package, not PREP-5's evidence package.**
   - PREP-5's package is a version's cited records. It exists only after the run, and its
     integrity is `sealed_digest` (matrix row, `:33`). It cannot be frozen before the pilot.
   - PREP-7 freezes the inputs. Per quarter, exactly five members with roles
     `{xbrl, results_pdf, transcript_pdf, qoq, yoy}`, each
     `{role, source_id (run roles), entry: {quarter, kind}, sha256}`.
   - Each member's `source_id` equals its config's: `xbrl`, `qoq` and `yoy` →
     `xbrl.source_id` (comparators parse under it, `api/run_comparatives.py:78`);
     `results_pdf` → `results_pdf.source_id`; `transcript_pdf` → `transcript_pdf.source_id`.
   - Each member's sha256 equals its config pin and its unique retrieval-manifest entry. The
     current XBRL has no config sha256, so its `local_path` resolves to the unique entry with that
     `filename`, and the file's actual hash must equal that entry's sha256 (Finding 6).
   - "ids" are the config `source_id` and the retrieval-manifest `(quarter, kind)`. Capture ids
     are minted at registration time in the test (`prep2b_support.py:166-185`), so they cannot be
     frozen.
   - The link to PREP-5: every capture a quarter's version cites must be in that quarter's
     package, or be inherited through the approved, pinned prior (cited by its `Prior.entries`, today guidance
     quotes, or carried in a rework), exactly `allowed_captures` (Finding 11). An earlier-package capture
     the prior does not cite is refused.
5. **The cutoff is recorded as a UTC instant** with a `field` locator on the transcript entry's
   `filed_at_nse` in the retrieval manifest, which is a hashed header source. The pilot check
   converts IST to UTC with `zoneinfo("Asia/Kolkata")` itself, an independent re-implementation
   that does not import `parse_filed_at`. It asserts:
   - the converted instant equals the recorded cutoff;
   - the recorded cutoff equals the quarter config's `knowledge_cutoff` (Q4 from `-pg`).

   The quarter's config comes from a fixed `CONFIGS` map in the check module, as in
   `test_prep2b_cutoffs.py:19-24` (FY26_Q4 → `aparinds-fy26-q4-pg.yaml`), never from the manifest,
   and the check asserts its `quarter.issuer_quarter` equals Q.

   Configs are read as YAML values, not hash-pinned as sources, so a later `eqos-ghv`
   `pdf_parse` edit does not invalidate the manifest.
6. **The retrospective designation is `{designated: RETROSPECTIVE, retrieval_manifest_sha256}`.**
   The check asserts, per member, through one predicate `admitted(entry, cutoff)`:
   - `filed_at_nse` is at or before the cutoff (contract a, as `source_admission.py:328-329`);
   - `retrieved_at` is after the cutoff (which makes the designation true);

   and separately that the digest equals the `ledger_import.yaml` pin that `--retrospective`
   requires (`cli.py:371-377`). All four quarters, including PQ0, are retrospective.
7. **PILOT-1 and PILOT-2 reuse stage1.** The pilot manifest's `pilot_checks` block points into
   `stage1_manifest.yaml`, a hashed header source, with `field` locators:
   - `C7_OPM.spec_literal_2dp` = `8.06`;
   - `pre_registered.H3.outcome.{pair,triage,queue}`.

   PBT 340.56 is PQ0's `fact.profit_before_tax`, and 340.53 is PQ0's `calc.4`. Nothing is duplicated.
8. **The pilot test path is `tests/fundamentals/test_pilot_e2e.py`.** It is registered now as
   `E2E["pilot"]`, which arms Finding 2's history check. PREP-8 sets `PILOT_TARGET` to the same
   path. The pilot test's own preflight (interface step 0) closes the gap the history check
   leaves before the test is committed.
9. **A pending manifest stays out of `tests/` until approved.** This follows the ledger_stage4
   precedent. Once the file sits in the fixtures directory, H7 and `test_manifest_is_approved`
   apply. The manifest, its check module, its predicate test, the `holds.yaml` line and the `E2E`
   entry therefore land in one commit, after Sol's APPROVE. Before approval the draft is
   validated by one explicit invocation outside normal collection (Task 1).

## How the pilot test consumes the manifest (interface for `eqos-4j2.8` / PREP-8)

The test loads the YAML with `yaml.safe_load`. In order:
- (0) **Preflight, before any pilot operation** (config load, store, run): the working
  `pilot_manifest.yaml` bytes equal `git show HEAD:<path>` bytes, and
  `manifest_support.approved(committed, committed)` holds. An uncommitted or unapproved manifest
  therefore stops the pilot before it produces output that could be used to adapt the expectations.
- For each quarter Q of `quarters`, in order:
  - (a) The version's `source_cutoff` equals `quarters[Q].source_cutoff.v`. The `retrospective`
    label is present, with `manifest_sha256` equal to `quarters[Q].retrospective.retrieval_manifest_sha256`.
  - (b) `pilot_manifest_check.citations_allowed(cited, package, inherited)`: every cited capture's
    blob sha256 is in Q's package or in `inherited`, the blobs cited by the approved prior's
    `Prior.entries` (today its guidance quotes, `run_draft.py:211-217`), plus a rework's carried blobs.
  - (c) The emitted claim keys, **excluding `SOURCE_QUOTE` claims** (guidance, Finding 7), equal
    `quarters[Q].claims` keys exactly (46). The guidance claims keep their separate PILOT-4
    validation (`eqos-4j2.27`). `figure` claims
    compare `Decimal` to `v`; `pct` claims and `calc.3` compare to the exact `v` quantized to
    `0.01` with `ROUND_HALF_EVEN`; `abs`, `calc.1` and `calc.4` compare to the exact `v`.
    `aux` operands are not compared as claims.
- (d) PILOT-1 and PILOT-2 read `pilot_checks`.

The manifest is frozen for good once the pilot test lands. `test_approved_payload_preceded_its_e2e`
compares the current payload with the one in the parent of the e2e's first commit
(`manifest_support.py:272`), so after any edit it fails permanently; a fresh APPROVE cannot repair it.

## Manifest shape (`header.notation` documents it)

```yaml
header: {manifest: pilot, spec, hand_verification: {verifier, date, method}, approval: {...},
         notation, pdf_columns: {<label>: {<pg>: {header_y, cols}}},
         sources: [{label, kind, path, sha256}]}   # exactly: 4 results PDFs, 4 transcript PDFs,
                                                   # 8 distinct XBRLs, retrieval manifest, stage1
quarters:                                          # exactly FY26_Q2, FY26_Q3, FY26_Q4, FY27_Q1
  FY26_Q2:
    source_cutoff: {v: '2025-11-06T06:35:34Z', at: [{src: A-MAN, path: 'entries[i].filed_at_nse', lex: '06-Nov-2025 12:05:34'}]}
    package: [{role: xbrl, source_id, entry: {quarter, kind}, sha256}, ...]   # exactly 5 roles
    retrospective: {designated: RETROSPECTIVE, retrieval_manifest_sha256: c47866ce…}
    claims:                                        # exactly the 46 keys of Decision 3
      fact.revenue: {v, iv, at: [<xbrl loc>], pdf: {<pdf loc>}}   # exact key sets; no `sign`
      cmp.revenue.qoq.prior: {v, iv, at: [<xbrl loc on the qoq member>]}
      cmp.revenue.qoq.abs: {expr, v}
      cmp.revenue.qoq.pct: {expr, v}               # v exact fraction
      calc.1: {expr, v}
      calc.2: {v, iv, at: [<xbrl loc>], pdf_parts: [<pdf loc>, ...]}   # tax components; '-' located, reads 0
      calc.3: {expr, v}
      calc.4: {expr, v}
    aux:
      share_of_associates: {v, iv, at: [<xbrl loc>], pdf: {<pdf loc>}}
pilot_checks:
  PILOT-1: {pbt: FY26_Q2 fact.profit_before_tax, pbt_after_associates: FY26_Q2 calc.4,
            opm: {src: STAGE1, path: pre_registered.C7_OPM.spec_literal_2dp, lex: '8.06'}}
  PILOT-2: {src: STAGE1, path: pre_registered.H3.outcome.pair, lex: ANOMALY}   # + triage, queue
```

The claim keys are the run's keys (Finding 7). The aid takes them from the check module's binding
table, never from run output. Derived nodes avoid `operands`, which `test_recorded_arithmetic_is_exact`
(`:665-675`) reserves.

## Assumptions

1. **The XBRL concepts.** The current files carry each binding-table concept with a unique `(concept, context)` hit:
   `RevenueFromOperations`, `Income`, `Expenses`, `ProfitBeforeTax`, `ProfitLossForPeriod`,
   `BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations`, the tax expense and the share of associates.
   - The pre-2025-taxonomy comparators (`INDAS_*.xml`) may use another prefix; binding is by local name, as the run does.
   - A missing or ambiguous hit fails closed and becomes an open question. It is never guessed.
2. **The PDF columns.** Each results PDF's consolidated P&L page has a header row the aid can bind
   (`pdf_columns`, as in stage1) and a title that tells it from the standalone page. PQ3's garbled
   unit words (`eqos-ghv`) do not matter, because locators bind lexemes and the unit is declared in
   `header.notation`. A page that fails `PDF_SCOPE`/`PDF_CURRENT` fails closed.

## Open questions (orchestrator rules; none is the owner's financial judgment)

1. **Does "hand-verified" require the owner to read the filings?** Recommend **no** (Decision 1).
2. **Should derived claims be frozen?** Recommend **yes**, recomputed from prescribed formulas.
3. **Guidance quote claims.** Recommend **out**.
   - No locator shape addresses a transcript PDF's spoken text.
   - PILOT-4's claim check already binds each quote to its source (`ledger_stage2` precedent).
   - New-transcript contracts are `eqos-0eu`.
4. **PILOT-9 shareholding.** Recommend **out**. Shareholding filings are not in the retrieval
   manifest, and PILOT-9 asserts comparison and citation rather than expected values.
5. **PDF corroboration of priors.** Recommend **no** (limitation 2). The current PDF's Q-1 and
   Q-4 columns may be restated, which would need discrepancy handling the spec does not require.

**Orchestrator rulings (2026-10-19), accepted by Sol r1:** all five as recommended.
- **1:** the PREP-7 report tells the owner plainly that no human read the filings: "hand-verified"
  means audited scripted verbatim transcription from the filed bytes, bound to each claim's
  meaning, cross-checked against the results PDF, re-checked by the suite and approved by Sol.
  The owner may spot-check any figure.
- **2:** with the actual keys and rounding (Decision 3).
- **4:** PILOT-9 has no retained shareholding filings, so a bead is filed to check, before the
  pilot, whether it is satisfiable.
- **5:** priors still require the correct comparator, concept and period (Decision 3).

## Stated limitations

1. **"Hand-verified" is audited, mechanically checked transcription plus Sol review. No human
   read the filings for PREP-7.** The aid's independence rests on Sol's review of its source and
   input list and on the fresh regeneration, not on a sandbox. The PDF cross-check is independent
   of the XBRL, but not of the issuer: an error in both representations would pass.
2. **Prior-period figures rest on one representation**, the comparator XBRL.
3. **Retrospective only.** The manifest cannot prove historical possession or the absence of
   hindsight (contract, `PREP-2b.md:50-51`). It proves only that each member was published by
   the cutoff and acquired after it.
4. **The derivation cutoff, capture ids and PREP-5 evidence-package digests are run-time values.**
   They are not frozen; PILOT-4's export hash covers them.
5. **Validation needs the retained `data/raw/watchlist/aparinds/` bytes** (the `retained` marker).
6. **PILOT-13's "its manifest" is the comparison run manifest** (`runs`/`run_inputs`), not this file.
7. **The ETR expectation is the exact-fraction rounding.** The run divides in the 28-digit default
   decimal context first; the two differ only at a 28-digit tie, which would surface as a pilot failure, not pass silently.
8. **The preflight (interface step 0) is PREP-8's code.** PREP-7 specifies it; `eqos-4j2.8` must implement it.

## File map

| File | Change |
|---|---|
| `tests/fundamentals/fixtures/data_foundation/pilot_manifest.yaml` | Create (generated by the reviewed aid, then approved) |
| `tests/fundamentals/pilot_manifest_check.py` | Create: no `fundamentals` imports; imports its helpers from `test_frozen_manifests` at top level (one-way): the binding table, `generic`, `check_pilot`, `admitted`, `citations_allowed`, `PILOT_MUTATIONS`, `SEMANTIC`, `refuses` |
| `tests/fundamentals/test_pilot_manifest_check.py` | Create: every pilot check and mutation (`retained`) and the synthetic predicate cases (unmarked) (Task 2) |
| `tests/fundamentals/test_frozen_manifests.py` | Modify, measured 800 → 794 lines: only `E2E`, rewritten as a comprehension that adds `"pilot"`. No import, no `STAGE_CHECKS` entry, no parametrization change |
| `config/retention/holds.yaml` | Modify: add one line |
| `docs/backend-roadmap.md` | Modify: the PREP-7 row status |
| `docs/blueprint/source-of-truth-matrix.md` | Modify: Gap 1 "Frozen inputs: PREP-7" gets the manifest path (only if the matrix is not hash-pinned; check `scripts/verify.sh`) |
| `CONTEXT.md` | Modify: one line, "Pilot source package", distinct from the evidence package |
| `scratchpad/prep7/` | The aid, its `INPUTS`, the draft manifest and `validate_draft.py`; never committed |

## Size (estimates, except where measured)

- `pilot_manifest_check.py`: about 200–240 lines (binding table about 25, `CONFIGS`/`UNIT_SCALE`/PDF
  tables about 25, inventories, value shape and bindings about 60, tax-component sum about 10,
  package/cutoff/designation about 45, `generic` and `refuses` about 15, mutations about 40 through
  one `repoint` helper).
- `test_pilot_manifest_check.py`: about 50 lines.
- `test_frozen_manifests.py`: **measured 794 lines (net −6)**. The edit was applied to a scratchpad
  copy of the current 800-line file: the 10 literal `E2E` lines become the 4-line comprehension
  below. It yields the same eight paths plus `"pilot"` (asserted by exec), is `ruff format`-stable
  and passes `ruff check`:
  ```python
  E2E = {
      name: f"tests/fundamentals/test_{'data_' * name.startswith('stage')}{name}_e2e.py"
      for name in ["stage1", "stage2", "stage4", "pilot", *(f"ledger_stage{n}" for n in range(1, 6))]
  }
  ```
- `holds.yaml`: 1 line. Docs: about 6 lines.
- The manifest YAML: about 1,300–1,900 generated lines.
- Scratchpad only: the aid and a ~30-line `validate_draft.py`.
- No `src/` change, migration or new dependency.

## Tasks

### Task 1: Author and validate the draft manifest (Opus, fresh)

Goal: `scratchpad/prep7/pilot_manifest.yaml` in the shape above, with every value derived from
bytes by `scratchpad/prep7/author_pilot_manifest.py`. The aid runs with
`uv run --no-sync python -I`, using lxml, pymupdf, json, yaml, fractions and zoneinfo. It opens
only the paths on its literal `INPUTS` list. It never imports `fundamentals` or tests, and never
reads `data/reports/`, `data/ledger/` or `data/store/`.

Files: create all under `scratchpad/prep7/`. The repo is read-only.

Interfaces:
- Consumes (`INPUTS`): the retained originals and comparators (Finding 6), `retrieval-manifest-v2.json`,
  the four pilot configs (pins, periods, concept mappings and cutoffs, as YAML values),
  `ledger_import.yaml`, `stage1_manifest.yaml` (pointers only), and `header.notation`
  conventions from stage1. Claim keys and bindings come from Decision 3's table.
- Produces: the draft YAML, with `approval: {reviewer: gpt-6.1-sol, verdict: PENDING}` on one line.

Approach:
- Per quarter: the package from the config pins, cross-checked against retrieval-manifest entries
  (the current XBRL via its `local_path` filename).
- The cutoff from the transcript's `filed_at_nse`.
- The figures as XBRL lexemes with full locators per the binding table, plus PDF cells for the
  current figures (the six roles, share of associates), the tax component cells as `calc.2`
  `pdf_parts` (zero markers located verbatim), with `pdf_columns`.
- The derived values as `expr` and `v` (exact `Fraction`).
- Fail closed on any absent or ambiguous hit, and list it.

Draft validation (outside normal collection; the aid itself runs no checks):
`scratchpad/prep7/validate_draft.py <draft>` puts `tests/fundamentals` on `sys.path`, imports
`test_frozen_manifests` and `pilot_manifest_check`, and on the draft runs every deterministic
check: `test_header_records_hand_verification`, `test_sources_match_their_hashes`,
`test_every_lexeme_is_at_its_locator`, `test_recorded_arithmetic_is_exact` (each called with the
draft path), `generic` and `check_pilot`; then `refuses(draft, name)` for every `PILOT_MUTATIONS`
entry; then the synthetic predicate cases; then it prints `payload_sha256(draft_bytes)`.

Tests: none committed in this task.

Verification:
- `uv run --no-sync python -I scratchpad/prep7/author_pilot_manifest.py` exits 0.
- `uv run --no-sync python scratchpad/prep7/validate_draft.py scratchpad/prep7/pilot_manifest.yaml` exits 0 (after Task 2).
- `git status` shows no tracked change.

Dependencies: none. Risk: **high** (financial values). Mitigated by meaning-bound locators, the
PDF/XBRL cross-check, recomputed derivations, the reviewed aid and Sol review.

### Task 2: The pilot check and its wiring (Opus, fresh; a different worker from Task 1)

Goal: `check_pilot(manifest)` asserts Decisions 2–7:
- **inventories:** `quarters` keys equal `ledger_import.yaml` `earnings_updates`; each quarter's
  `claims` keys equal the 46-key set and `aux` keys equal `{share_of_associates}`; each `package`
  has exactly the five roles; header source paths equal the package members' files plus the
  retrieval manifest and stage1;
- **package:** every member `source_id` equals its config's; every member sha256 equals its config pin and its unique retrieval-manifest entry;
  the current XBRL's `local_path` resolves to its unique entry by `filename`, and the file's
  actual sha256 equals that entry's;
- **config:** Q's config from the fixed `CONFIGS` map, `quarter.issuer_quarter == Q`;
- **shape:** exact key sets, `v == Fraction(lex) / UNIT_SCALE[u]`, no `sign` (Decision 3);
- **bindings:** every located claim and operand matches its binding-table row (member via `src`
  sha256, concept local name, `per`, no `dims`, unit); every PDF cell matches Decision 2's tables;
- **derivations:** every derived `v` equals the prescribed formula over the bound operands' `v`;
- **PDF:** each current figure's XBRL and PDF intervals overlap; for `calc.2`, the XBRL interval
  overlaps the summed `pdf_parts` intervals, zero markers read as exact 0 (Decision 2);
- **cutoff:** it equals the IST→UTC conversion of the located lexeme and the config's `knowledge_cutoff`;
- **retrospective:** `admitted(entry, cutoff)` for every member; the digest equals the `ledger_import.yaml` pin;
- `pilot_checks` resolves.

Also `citations_allowed(cited, package, inherited) -> None` (Decision 4; consumed by PREP-8).
Once the pilot is in `fixtures/`, the generic `per_manifest` tests still cover it with no edit:
the already-`retained` source and locator tests, and the in-memory default `check_values`
(`:684-689`) and arithmetic tests.

Files:
- Create `tests/fundamentals/pilot_manifest_check.py`. It imports `walk`, `evaluate`, `reading`,
  `source`, `label_rows`, `check_locator`, `check_values` and `REPO` from `test_frozen_manifests` at
  top level. The dependency is one-way: `test_frozen_manifests` never imports the check module.
- Create `tests/fundamentals/test_pilot_manifest_check.py`: every pilot check and mutation.
- Modify `tests/fundamentals/test_frozen_manifests.py`: only `E2E`, the measured comprehension
  under Size (800 → 794). The pilot is not added to `STAGE_CHECKS`, `per_manifest` or `STAGE_CASES`.
- Modify `config/retention/holds.yaml`.

Interfaces:
- Consumes: the manifest dict, plus `REPO` for the configs, `ledger_import.yaml` and the retrieval manifest.
- Produces: `check_pilot(manifest: dict[str, Any]) -> None`, `admitted(entry: dict[str, Any], cutoff: datetime) -> None`,
  `citations_allowed(cited: set[str], package: set[str], inherited: set[str]) -> None`,
  `PILOT_MUTATIONS: dict[str, Callable[[dict[str, Any]], object]]`,
  `SEMANTIC: dict[str, str]` (binding-probe name → expected refusal message),
  `generic(manifest) -> None`: `check_values`, `check_locator` on every located node, every `expr`
  exact (the predicate of `test_recorded_arithmetic_is_exact`, `:663-664`, which takes a path, not a
  dict), and the PDF/XBRL overlap; and
  `refuses(manifest, name) -> None`: mutates a deep copy; an ordinary entry must make `generic` or
  `check_pilot` raise; a `SEMANTIC` entry must pass `generic`, then make `check_pilot` raise with
  its `SEMANTIC` message.

Tests (dynamic logic only). Mutations share one helper, `repoint(m, q, key, at=…, pdf=…)`: it swaps
the named locators for other genuine ones, resets `v`/`iv` from the new XBRL lexeme and recomputes
every derived node of quarter `q` with the check's own formulas.

| Mutation | Kind | Change |
|---|---|---|
| cutoff +5h30 (old UTC misreading) | ordinary | `source_cutoff.v` |
| package sha256 | ordinary | one swapped for another quarter's |
| digest only | ordinary | retrieval digest changed, label kept |
| designation label | ordinary | label changed |
| derived formula | ordinary | a derived `v` and its `expr` changed consistently |
| PDF outside XBRL | ordinary | one PDF lexeme, no overlap |
| broken tax sum | ordinary | one `calc.2` `pdf_parts` cell re-pointed at another genuine cell in the same page and column; the sum no longer overlaps |
| dropped `iv` / added sign | ordinary | one `cmp.*.prior` loses `iv`; another gains `sign: -1`, `v` and `iv` negated |
| deletions | ordinary | a quarter; one `cmp.*` claim; `calc.3`; one package member |
| wrong quarter | `SEMANTIC` | `repoint` `fact.revenue` to the QoQ member's prior-quarter fact and its `pdf` to the prior-quarter column of the same PDF |
| wrong concept | `SEMANTIC` | `repoint` `fact.total_income` to revenue's XBRL and PDF locators |
| QoQ/YoY swap | `SEMANTIC` | `repoint` `cmp.revenue.qoq.prior` to the YoY member's fact |
| PBT concept swap | `SEMANTIC` | PQ0 `fact.profit_before_tax` to `ProfitBeforeExceptionalItemsAndTax` (same filed `340.56`, `stage1_manifest.yaml:1298-1301`) |
| cross-package PDF cell | `SEMANTIC` | PQ0 `fact.revenue.pdf` to the equal-valued PQ0 cell in the PQ1 results PDF's prior-quarter column (header added to `pdf_columns`) |
| ID only | `SEMANTIC` | one member's `source_id` changed, nothing else |

A binding probe first updates its corroborators and derivations so `generic(m)` passes, then must
fail only on the targeted binding. A binding probe that `generic` rejects is a broken mutation.

`test_pilot_manifest_check.py` holds every pilot check and mutation:
- marked `retained` (they read retained bytes): the real manifest passes `generic` and
  `check_pilot` (the positive case for Decision 2, including PQ0 PAT and PQ2 PBT); `refuses` for
  every `PILOT_MUTATIONS` name, parametrized.
- unmarked synthetic cases (small; every other binding valid; each asserts the intended refusal message):
- `admitted`: a valid entry passes; `retrieved_at` at the cutoff is refused (acquired at or before cutoff);
  `filed_at_nse` one second after the cutoff is refused (published after cutoff);
- `citations_allowed`: own-package and prior-cited captures pass; a capture from an earlier
  quarter's package that the prior does not cite is refused.

Develop against the draft in the scratchpad. The file moves into `fixtures/` only in Task 4.

Verification:
- `uv run --no-sync python scratchpad/prep7/validate_draft.py scratchpad/prep7/pilot_manifest.yaml` exits 0.
- `uv run pytest tests/fundamentals/test_pilot_manifest_check.py -m 'not retained'` (the synthetic
  cases; the `retained` cases run on the draft through `validate_draft.py`, and in Task 4).
- `wc -l tests/fundamentals/test_frozen_manifests.py` = 794, and its diff touches only `E2E`.
- `uv run ruff check tests/fundamentals` and `uv run ruff format --check tests/fundamentals`.

Dependencies: Task 1. Risk: medium.

### Task 3: Phase review loop (Sol high), per `04-agent-stack.md`

Sol reviews, in one exhaustive pass: the draft manifest, the check module and its test, the
`test_frozen_manifests.py` diff, the aid's complete source and its `INPUTS` list, and the
`validate_draft.py` output. Fixes go to a fresh Opus round, then a re-review, until APPROVE. A
fresh closing review follows.

Before the approval line is written, the orchestrator deletes the draft, regenerates it with the
reviewed aid, requires it byte-identical to the reviewed draft, reruns `validate_draft.py`, and
writes the one approval line `{reviewer: gpt-6.1-sol, verdict: APPROVE, date, payload_sha256}`
using the digest it prints, which must equal the digest Sol approved. Sol's APPROVE is the
approval; the owner is not waited on.

Dependencies: Tasks 1–2.

### Task 4: Land it (orchestrator)

Move the manifest into `fixtures/data_foundation/`. Commit, in one commit with explicit staging:
the manifest, `pilot_manifest_check.py`, `test_pilot_manifest_check.py`, the
`test_frozen_manifests.py` edits and `holds.yaml`. Then make the docs commit: the roadmap row
(Done, with the plan link and Sol verdicts), the matrix pointer and the CONTEXT line. The PREP-7
report states that no human read the filings (OQ1 ruling).

Verification:
- `uv run pytest tests/fundamentals/test_frozen_manifests.py tests/fundamentals/test_pilot_manifest_check.py tests/fundamentals/test_retention_holds.py tests/fundamentals/test_ledger_stage5_e2e.py tests/fundamentals/test_prep2b_cutoffs.py`
- `uv run pytest tests/fundamentals`
- `uv run mypy --strict src`
- `uv run ruff check src tests/fundamentals` and `uv run ruff format --check src tests/fundamentals`
- `wc -l tests/fundamentals/test_frozen_manifests.py` = 794 (cap 800)
- `git diff --quiet HEAD~2 -- config/aparinds-fy26-q4.yaml` (byte-identical)
- `git status`

Dependencies: Task 3. Risk: low.

## How each requirement is met

| Clause | Met by |
|---|---|
| Expected values hand-verified from the four quarters' filings | Decisions 1–3: an audited aid (source and inputs reviewed, regenerated fresh); XBRL lexemes bound to each key's concept, member, period, dims and unit; PDF overlap cross-check; derivations recomputed from prescribed formulas; exact inventories; all re-checked from bytes. No human read the filings (limitation 1) |
| Reviewer-approved | Task 3: Sol APPROVE over `payload_sha256` of the regenerated draft, asserted by `test_manifest_is_approved` |
| Committed before the pilot test | Decision 8: `test_approved_payload_preceded_its_e2e` (history) plus the pilot test's preflight (interface step 0) |
| IST-correct source cutoff, per quarter | Decision 5: located lexeme, independent IST→UTC conversion, equals the configs (Q4 from `-pg`) |
| Reviewed package (ids + sha256), per quarter | Decision 4: exactly five members; config `source_id`, retrieval-manifest `(quarter, kind)`, sha256 checked against the pins, the current XBRL against its actual file hash; transcripts as hashed header sources; held via `holds.yaml` |
| Retrospective designation, per quarter | Decision 6: designation, `admitted` per member (each predicate refused separately in tests), and the pinned retrieval digest |
| Frozen and hash-pinned | `approved` payload digest; header sources sha256-checked; inputs held (Finding 3) |
| §4 "never from code output" | The aid reads only its reviewed `INPUTS`, none of them code output (Decision 1, Task 1) |
| PILOT-1 (PQ0 PBT 340.56 / 340.53, OPM 8.06%) | PQ0 `fact.profit_before_tax` and `calc.4`, plus `pilot_checks.PILOT-1` → stage1 (Decision 7) |
| PILOT-2 (opex gap equals its pre-registered outcome) | `pilot_checks.PILOT-2` → stage1 `pre_registered.H3` |
| PILOT-4 (both cutoffs, retrospective label) | The source cutoff and designation are the expected values. The derivation cutoff is run-time (limitation 4) |
| PILOT-9, PILOT-13 | Not served by PREP-7 (open question 4; limitation 6) |
| Source-of-truth Gap 1, "frozen inputs" | Decision 4's package plus `citations_allowed`, which the pilot test asserts |

## Interactions with open beads

- `eqos-4j2.8` (assisted updates): the pilot test consumer; it must implement the interface above,
  preflight first, and commit after this.
- PREP-8 / `eqos-4j2`: sets `PILOT_TARGET` to `tests/fundamentals/test_pilot_e2e.py`.
- `eqos-ghv` (PQ3 PDF parser): independent. The manifest reads the PDF text layer directly. If its
  fix edits `aparinds-fy27-q1.yaml`, the manifest survives, because configs are read as values
  (Decision 5). If a fix ever changed the cutoff or a pin, the check would fail, correctly.
- `eqos-6so` (Q1 FY27 owners-PAT mis-tag): the PAT role uses `ProfitLossForPeriod`, which is unaffected. It motivates Decision 2.
- `eqos-4j2.27` (PILOT-4 citation contract): consumes `citations_allowed`.
- `eqos-0eu` (guidance contracts): open question 3.
- `eqos-4j2.23` (derivation clock): unaffected; not frozen.
- `eqos-1kq`, `eqos-7fa`, `eqos-0bp` (flaky PG and order-dependent tests): may show up in the Task 4 full-suite run. Rerun them, and do not mask them.

## Not verified

- The exact concept names and context ids in the eight XBRL files (Assumption 1).
- Whether `pdf_columns` binds cleanly on each Q4 and Q1 FY27 page (Assumption 2).
- Whether `source-of-truth-matrix.md` is hash-pinned.

## Self-review

- **Size:** one check module (one-way import of `test_frozen_manifests`), one test file holding
  every pilot check, and wiring measured at net −6 lines. Everything else
  is reused: locators, hashing, approval, the history check, holds. No new locator shape, no registry.
- **The biggest risk is value correctness.** It is now mitigated by meaning-bound locators,
  exact inventories, recomputed derivations, the PDF overlap check, an audited and regenerated
  aid, a separate author for the check, and Sol.
- **Could it be half the size?** Dropping derived claims (open question 2) halves the YAML but not
  the code. Every check traces to an r1 finding or an acceptance clause.
- **Ordering:** Decision 9 avoids a red window, because the manifest enters `tests/` already
  approved; the preflight covers the pre-commit pilot run.
- **Honesty:** "hand-verified" is defined plainly and states that no human read the filings
  (Decision 1, limitation 1); the PREP-5 versus PREP-7 package distinction is explicit (Decision 4).

## r1 findings → resolution

| # | Sol r1 finding | Resolution |
|---|---|---|
| 1 | PDF containment rejects valid filings (P1) | Finding 10; Decision 2: precision-aware interval overlap. The real manifest is the positive case (PQ0 PAT, PQ2 PBT); the non-overlap mutation stays |
| 2 | Locators not bound to a claim's meaning (P1) | Decision 3 binding table in the check module (member, concept, period, dims, unit; derived keys recomputed from prescribed operands and formulas, `of`/`formula` dropped). Mutations: wrong quarter, wrong concept, QoQ/YoY swap, each with derived values recomputed |
| 3 | Missing quarter or claim shrinks the oracle silently (P1) | Task 2 inventories: quarters = `earnings_updates`, 46 claim keys, `aux`, five package roles, header sources. Deletion mutations: a quarter, a `cmp.*` claim, `calc.3`, a package member |
| 4 | Interface keys and rounding do not match the run (P2) | Finding 7 and Decision 3: actual keys `calc.1..calc.4` (`run_traces.py:358`, order `pipeline_steps.py:190-197`); share of associates under `aux`; `0.01 ROUND_HALF_EVEN` for every `pct` and `calc.3` (`pnl_lines.py:39`); limitation 7 |
| 5 | Commit precedence does not stop an uncommitted pilot run (P2) | Interface step (0): preflight before any pilot operation, working bytes equal HEAD and approved; history check kept; the "fresh APPROVE" sentence corrected (`manifest_support.py:272`); limitation 8 |
| 6 | Transcripts unhashed; current XBRL has no sha256 (P2) | Manifest shape: 4 transcript PDFs as header sources; Decision 4 and Task 2: `local_path` → unique retrieval entry by `filename`, actual file hash checked |
| 7 | Aid independence asserted, not demonstrated (P2) | Decision 1: explicit `INPUTS`; the complete aid and list are Sol review inputs; Task 3 regenerates fresh and requires byte identity before approval; described as audited authoring, limitation 1 |
| 8 | Retrospective predicates lack independent negative proof (P2) | Decision 6 `admitted`; `test_pilot_manifest_check.py` refuses acquisition at the cutoff and publication after it with synthetic entries; separate digest-only mutation |
| 9 | Earlier-package exception broader than the approved-prior contract (P2) | Finding 11; Decision 4 and interface (b): `citations_allowed` = own package or inherited through the approved prior (`run_draft.py:505`); test refuses an earlier-package capture the prior does not cite |
| 10 | Pending draft's checks never run; aid self-run conflicts with no-import rule (P2) | Task 1 `validate_draft.py`: one explicit invocation outside collection runs every deterministic check and mutation and prints `payload_sha256`; the aid runs no checks |
| 11 | `test_frozen_manifests.py` would exceed the 800-line cap (P2) | Finding 13; only `E2E` changes, as a comprehension, measured at 794 lines (closing r2 #2); `wc -l` in Tasks 2 and 4 |
| 12 | `python3 -I` lacks lxml and pymupdf (P2) | `uv run --no-sync python -I` throughout |

## r2 findings → resolution

Sol r2 confirmed EPS is `INRPerShare` on all eight XBRLs and associates are printed in each
current-quarter PDF table; those "Not verified" items are removed.

| # | Sol r2 finding | Resolution |
|---|---|---|
| 1 | `calc.2` total tax has no single PDF cell (P1) | Finding 7, Decision 2, Decision 3 row, manifest shape, Tasks 1–2: XBRL total tax stays the value; corroborated by overlap with the sum of located PDF component cells (`pdf_parts`), zero markers (`ZERO_MARKERS`) located and read as exact 0; new "broken tax sum" mutation |
| 2 | Interface compares all emitted keys, but guidance claims share the collection (P2, r1 #4 residual) | Finding 7 and interface (c): `SOURCE_QUOTE` claims are excluded from the exact 46-key comparison; their PILOT-4 validation stays separate |
| N1 | `REQUIRED_ROLES` citation | `earnings_update.py:52-59`, `BASIC_EPS` `:58` |
| N2 | Inherited prior captures | Finding 11, Decision 4, interface (b): those cited by `Prior.entries`, today guidance quotes (`run_draft.py:211-217`) |

## closing r1 findings → resolution

| # | Sol closing r1 finding | Resolution |
|---|---|---|
| 1 | A dropped `iv` leaves `v` unchecked; a prior can gain `sign: -1` (P1) | Decision 3 value shape: exact key sets, `v == Fraction(lex) / UNIT_SCALE[u]`, no `sign` on pilot locators. Mutations: dropped `iv`, added sign |
| 2 | PDF corroborators not bound to member, scope, column or row (P1) | Decision 2 fixed tables: own quarter's `results_pdf` member, `PDF_SCOPE[Q]`, `PDF_CURRENT[Q]`, `PDF_ROW[role]`, complete unique `PDF_TAX_ROWS[Q]`. Mutation: PQ1 PDF's prior-quarter PQ0 revenue cell |
| 3 | `quarters[Q].config` self-declared (P2) | Decision 5: fixed `CONFIGS` map (Q4 `-pg`) as `test_prep2b_cutoffs.py:19-24`; `issuer_quarter == Q`; `config` dropped from the manifest shape |
| 4 | Package `source_id`s not checked (P2) | Decision 4: role → config `source_id` equality; comparators use `xbrl.source_id` (`run_comparatives.py:78`); Assumption 2 removed. Mutation: ID only |
| 5 | Pilot cases read retained bytes unmarked (P2) | Superseded by closing r2 #2: the pilot checks and mutations live in `test_pilot_manifest_check.py`, marked `retained` |
| 6 | Semantic mutations may be caught by generic checks first (P2) | Task 2: `generic(m)` must pass, then `check_pilot` raises the `SEMANTIC` message; PBT concept-swap mutation added |
| 7 | Finding 8 PBT citation (P3) | `stage1_manifest.yaml:1357` |

## closing r2 findings → resolution

| # | Sol closing r2 finding | Resolution |
|---|---|---|
| 1 | Mutation acceptance contradicts `generic` (P2) | Task 2 table: broken tax sum is an ordinary overlap-negative case. Binding probes `repoint` their corroborators and recompute derivations so `generic` passes, then assert the `SEMANTIC` refusal, all through `refuses` |
| 2 | Wiring measured 807 lines against the 800 cap (P2) | The pilot is out of `STAGE_CHECKS` and both parametrizations; all its checks run from `test_pilot_manifest_check.py` (`retained` per test, synthetic cases unmarked). `test_frozen_manifests.py` changes only `E2E`, measured at 794 lines on a scratchpad copy (Size) |
| N1 | The call-time import keeps a two-way dependency | Top-level, one-way import from `test_frozen_manifests`; "leaf module" wording dropped |
| N2 | Mutation lines are the main compaction target | Mutation table plus one `repoint` helper; estimate about 70 → 40 lines |
