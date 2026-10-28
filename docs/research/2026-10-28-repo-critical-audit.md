# Lane 3 critical audit — 2026-10-28

Lane 3 audit by gpt-6.1-sol (2026-10-28), read-only. The orchestrator spot-checked two findings in the code: F01 (`numeral_scan.py:35` treats `word:500` as an identifier) and F06 (`gold_file.py:172` overwrites the gold file without comparing first). F01 and F03 overlap RESEARCH-3 spec findings 1–2 (strict numeral scan, location eligibility); fold them into its S3 plan.

**VERDICT: REQUEST_CHANGES**

23 findings: **6 P1, 11 P2, 6 P3**. Primary categories (each finding counted once): **7 invariant violations, 2 spec-drift findings, 8 correctness bugs, 2 dead-code/reachability findings, 4 size findings**. Findings may also implicate another category; those cross-references do not increase the count.

**Estimated net removable code: 300 lines**, before implementation measurement: 70 unused helpers/declarations + 140 duplicated blueprint projection/equivalence plumbing + 60 repetitive CLI dispatch + 30 duplicated transport classification. Moving code between modules is counted as **zero deletion**. A further **205-line** dormant candle-replay module is an owner scope decision, excluded from 300. There is no evidence here that half of the approximately 99k scoped lines can safely be deleted.

## Boundaries and evidence

- Read AGENTS.md, CONTEXT.md, the lane plan, and the requested `.claude/project/{invariants,repo-map,verification}.md` first; also consulted the Codex project overlay and applicable review/minimal-code guidance. The requested Claude invariants include the October 20/28 filed-figure exceptions; these are respected below.
- Source inventory: 404 Python/SQL/YAML/shell/JSON files, 99,314 lines, excluding the named ingest/API filename patterns and the two forbidden manifests. Inventory is a size census, **not a claim that every line received equivalent manual review**. Manual inspection concentrated on report production, citations, numeric checks, reconciliation, temporal selection, persistence, memory, identity/news, migration execution, and scripts. Targeted AST/import/name scans covered `src/` and `scripts/`; **no recursive tests/ or data/ search**.
- Did not open `stage4_holdout.yaml`, `stage4_manifest.yaml`, `data/holdout/`, or `data/raw/onboarding/`. No DB access (including SQLite), network, model calls, permission changes, Beads commands/writes, Git writes, installs, or test-suite runs. Pure probes used the existing `.venv/bin/python -B` and synthetic in-memory inputs only.
- **Observed** means directly inspected source, a targeted search result, or the pure probe output recorded below. **Inference** means the stated end-to-end failure follows from that source; no live incident or DB rehearsal is claimed. All source references are repo-relative and refer to this checkout.
- Initial and final Git status are clean. Only this ignored report was written. No production acceptance conclusion follows from this audit.

## Ranked findings

### F01 — P1 — Invariant: ordinary analytical numerals evade ledger numeric coverage

**Evidence:** `src/fundamentals/ledger/numeral_scan.py:35` removes arbitrary lowercase words followed by `-`, `:` or `#` and digits, treating them as identifiers. `:49-50` then searches only the remainder. This check is used at submission (`ledger/lifecycle.py:168-173`) and approval validation (`:275-279`).

**Observed probe:** `scan_section('{{e:opinion}} Expected revenue:500 crore.', resolves=...)` returns `()`. Writing the same number as `Expected revenue is 500 crore.` returns `UNREGISTERED_NUMBER`. `Expected return is × 100 percent.` also returns `()` because the formula-literal exemption is context-free (`numeral_scan.py:36`).

**Failure inference:** drafted `revenue:500 crore` reaches the narrative without a NumericClaim, fact, or trace. Labelling it opinion does not make an invented amount lawful. Violates invariants 6–7 and the explicit numeric-coverage rule in `docs/specs/2026-10-12-report-ledger-memory-and-data-lifecycle.md:163-167`, which exempts **parsed identifier/provenance fields** and **registered formula literals**, not arbitrary analytical text.

**Smallest fix:** restrict exemptions to the actual structural fields/forms emitted by the renderer. Do not strip an arbitrary `word:number` or `× 100` from ordinary prose. No new validation subsystem is needed.

### F02 — P1 — Invariant: thesis verification launders dates, signs and units into sourced analytical amounts

**Evidence:** `src/fundamentals/thesis/verifier.py:133-160` creates a flat set of allowed Decimal values containing fact values, source counts, date components and adjacent years. `:183-189` accepts a number solely by membership in that set. The numeric regex at `:36-39` does not preserve a minus sign, and acceptance ignores `NumberHit.is_percent`. `thesis/render.py:190-191` reports a clean result as no number introduced outside the validated fact set.

**Observed probe:** with **no financial facts**, period April 1–June 30, 2025 and label FY26_Q1, two identical drafts saying `ROCE is 30% and leverage is 1%. The company has 2025 stores.` produce zero unsourced claims and zero discrepancies. `Profit is -30 crore.` also produces zero unsourced claims. The allowed 30 and 1 came from dates/quarter text, not financial evidence.

**Failure inference:** a model-created ratio, unit substitution, sign reversal, or amount coinciding with an unrelated fact is not put in the exception queue. This affects the reachable `fundamentals thesis` path (`api/thesis_cli.py:252`), not the newer ledger NumericClaim checker. The draft remains labelled OPINION; **no claim of automatic approved-ledger promotion is made**. It nevertheless violates the numerical provenance doctrine and the task rule forbidding new ratios/estimates (`thesis/prompt.py:42-46`).

**Smallest fix:** reuse typed claim references for echoed amounts, or prohibit analytical numerals in these free-text judgment fields. Remove date/source-count value membership as evidence of an analytical number. Preserve sign and unit when checking an actual numeric reference.

### F03 — P1 — Invariant: a prose source marker can cite a future or different issuer's capture

**Evidence:** `src/fundamentals/ledger/citations.py:320-334` resolves a marker by capture ID, first-party source class, and nonempty span only. It receives **no report entity, cutoff, or pinned runs/package**. Both submission (`ledger/lifecycle.py:168`) and approval validation (`:275`) bind exactly this unrestricted resolver. Numeric citations separately pass report entity and pinned runs (`:260-267`) and check input times (`ledger/claim_check.py:95-100`).

**Failure inference:** a historical report's `{{e:observed}}` paragraph can cite an existing PDF captured after its cutoff, or another issuer's PDF, and pass the prose citation gate. The future fact need not have a numeric placeholder. This violates temporal doctrine and `docs/specs/equity-os-s11-run-manifest-cutoff-reproducibility.md:148-159`. The ledger spec's presence-only prose rule (`2026-10-12-report-ledger-memory-and-data-lifecycle.md:175-178`) leaves semantic fit to reviewers; that is not proof that future evidence is cutoff-eligible.

**Smallest fix:** pass the report's existing entity/cutoff/evidence bindings into location resolution and reuse existing capture eligibility checks. Retain human judgment of whether the cited passage supports the wording.

### F04 — P1 — Invariant: legacy validate/report paths bypass cutoff admission and backdate cached reads

**Evidence:** `src/fundamentals/api/goal_runner.py:464` uses the configured historical cutoff as a fixture retrieval timestamp; NSE fixture parsing stamps it at `:513-519`, and PDF fixture parsing uses it at `:813-815`. Live NSE parsing uses the actual retrieval time (`:539-544`), but `reconcile_stock` / `reconcile/fact_view.py:129-168` never apply the stock's knowledge cutoff. `api/report_builder.py:248` prints that configured cutoff; `output/earnings_update.py:398-402` explicitly says later information is out of scope. `config/watchlist.yaml:67` actually pins a February 15, 2025 cutoff.

**Failure inference:** `validate --live` today can accept a later restatement while reporting the old cutoff. `report` reparses cached raw bytes as FIXTURE (`api/report_cli.py:147-152`) and stamps them as known at that old cutoff, without retained acquisition proof or a retrospective label. This bypasses the source-admission mechanism already used by `run` (`api/pipeline.py:220-235`).

**Smallest fix:** route cached/live report inputs through existing source-admission proof, or explicitly render this old command as a retrospective current-data diagnostic with actual acquisition time. Do not use the cutoff as invented retrieval provenance. Invariants 9–10/13 and S11's cutoff contract apply.

### F05 — P1 — Invariant: SEC fact provenance hashes different bytes from the facts being parsed

**Evidence:** `src/fundamentals/ingest/sec_source.py:171-172` first hashes one direct HTTP response, then separately loads facts through edgartools (`:230-239`). The first response body is discarded (`:186-197`); it is not the parser input. Every selected fact receives that hash (`:272-279`). The code also sets `first_seen_at=filed_at` (`:279`), even though retrieval occurred now (`:277`). Reachable when SEC is enabled through `api/pipeline_steps.py:142-151` / `api/pipeline.py:491-492`.

**Failure inference:** an edgartools cache or an update between reads yields facts that cannot be reconstructed from their claimed hash. Even without a race, this application retains no hashed body for replay and reports publication as first sight. Invariants 7/9/13 are not satisfied by a hash obtained independently of the parsed bytes.

**Smallest fix:** fetch and retain one companyfacts response and parse/select from those exact bytes. Record actual first sight separately from filing date. This can remove the duplicate acquisition path; no extra provenance layer is needed. SEC values are currently diagnostic/excluded from the quarterly report, limiting direct report impact.

### F06 — P1 — Spec drift: validation overwrites the gold baseline instead of regressing it

**Spec:** `docs/goals/fundamentals-multistock-validation-goal.md:53` requires reruns to compare fresh extraction against the stored reference and flag drift.

**Code:** `src/fundamentals/api/goal_runner.py:367-370` always calls `write_gold_file`. `reconcile/gold_file.py:169-172` unconditionally replaces the existing reference. The implemented regression function is at `reconcile/gold_file.py:188`; targeted `rg -n '\bregress\b|read_gold_file\(' src scripts` finds its definition, docstrings and package export, **no runtime invocation**.

**Failure inference:** a parser regression, changed status, or restatement replaces the human-reviewed expected value before comparison. The run can report DONE and the old reference is lost. This is also an append-only/auditability problem for this reference artifact; the SQL FactStore's immutable history does not preserve the overwritten gold file.

**Smallest fix:** read the existing baseline before writing; use the existing `regress` function and report its drift. Publish a replacement only through the intended reference-update decision. Do not add another comparator implementation.

### F07 — P2 — Correctness: public pipeline persistence is only atomic per individual write

**Evidence:** `src/fundamentals/api/pipeline.py:545-563` performs `put`, history reads and `select_canonical` in a loop. SQLite `FactStore.put` commits independently (`store/fact_store.py:644-663`); `select_canonical` has another transaction (`:698-706`). PostgreSQL methods likewise each call `_write` (`store/pg_fact_store.py:228,284,317-319`). A stale selection at pipeline line 552 raises after preceding writes have committed.

**Failure inference:** a second-identity write failure, store failure, or concurrent selection leaves earlier identities newly canonical although `run_pipeline` raises and yields no result. This is a concrete failure path in the public/SQLite pipeline; the current PostgreSQL CLI passes `skip_roles=frozenset(FactRole)` (`api/cli.py:403-407`), so **this finding does not claim those particular native pipeline writes occur on that CLI route**. Its separate admissions have their own transactions.

**Smallest fix:** perform the planned revision/selection batch in one store transaction, keeping the existing predecessor checks inside that transaction. Do not describe the current per-write loop as a whole-run transaction. DB failure/concurrency behavior was inferred, not exercised.

### F08 — P2 — Spec drift: DONE does not cover every required report role

**Spec:** `docs/goals/fundamentals-multistock-validation-goal.md:47-50,57-62` requires every material line in the cross-check/reference and no missing material concepts.

**Code:** `src/fundamentals/api/goal_runner.py:329` builds `facts`, `missing`, and the gold results solely from `concepts.cross_check`. The default required roles contain total expenses (`api/config.py:377`), but the cross-check set at `:403-410` omits it. The existing union helper `reconcile/fact_view.py:47-54` is not used here.

**Observed probe:** both default ConceptsConfig and configured LAURUSLABS/MTARTECH have required `total_expenses` outside this completion set.

**Failure inference:** five headline facts can agree and the stock can be DONE while expenses are missing or conflicting; its gold file does not even contain the omitted required role. The report renderer later needs that role. **Smallest fix:** build material results from the existing union of required roles and cross-check concepts; keep the narrower cross-check selection only where that distinction is intended.

### F09 — P2 — Correctness: skipped accounting identities count as passed

**Evidence:** `src/fundamentals/api/goal_runner.py:289-293` silently omits any identity without complete operands. `:414` uses `all(...)` over only returned results. No result records that an identity was not evaluated.

**Observed probe:** `_evaluate_dod([one agreed fact], [], [], gold_written=True)` returns every clause true, including `cross_foot_holds`, and `dod.met == True`.

**Failure inference:** when neither XBRL source covers the accounting operands, all configured identities disappear and DONE can still be awarded. This independently violates the identity clause at `docs/goals/fundamentals-multistock-validation-goal.md:60`; adding expenses to material facts does not establish that accounting identities were evaluated.

**Smallest fix:** distinguish an explicitly inapplicable identity from a required identity with unavailable operands, and require a result for each applicable identity before asserting it holds. Preserve the existing optional-NCI exception; do not ban legitimately inapplicable identities.

### F10 — P2 — Correctness: two empty JSON answers become an OK thesis with no review flags

**Evidence:** `src/fundamentals/thesis/draft_parser.py:81-96` accepts any parsed object, including `{}`, as `DraftStatus.OK`; `thesis/contracts.py:174-176` defines usability by nonempty raw text. `_document_status` counts these (`thesis/pipeline.py:94-101`). Missing sections on both sides are skipped by divergence checking (`thesis/verifier.py:304-305`).

**Observed probe:** two `{}` answers are both usable, the document status is `ok`, and cross-verification has no flags.

**Failure inference:** a provider returning an empty object or an unrelated JSON envelope appears to have produced two usable analyst drafts, although there is no judgment content. **Smallest fix:** derive usability from recognized substantive content; report empty/unusable responses through the existing EMPTY/PARTIAL/BLOCKED paths.

### F11 — P2 — Correctness: opposite judgments are reported as no divergence

**Evidence:** `src/fundamentals/thesis/verifier.py:76` removes `not`; `:201-206` tokenizes both judgments; `_unmatched` (`:220-241`) uses a low Jaccard threshold to decide whether points have counterparts. `thesis/render.py:221-224` then says no material divergences were detected.

**Observed probe:** equal-stance drafts with `Cash conversion is strong.` versus `Cash conversion is not strong.` produce **zero discrepancies**. Negation disappears entirely.

**Failure inference:** exception-only review misses directly opposing analytical conclusions. This is not merely imperfect stylistic similarity. **Smallest fix:** stop treating lexical similarity as evidence of agreement. Keep unequal judgments unresolved unless a supported comparison establishes agreement; at minimum preserve negation and comparators. No additional model council or abstraction is proposed.

### F12 — P2 — Correctness: cached report inputs are selected by filename, not report identity/version

**Evidence:** `src/fundamentals/api/report_cli.py:62,72` selects the lexicographically first XML and first PDF in each issuer cache. It does not bind them to one capture/package. `_collect_nse` in `api/goal_runner.py:513-520` parses the current cached XML without the issuer check used for comparators (`api/comparatives.py:59-67,130`). `reconcile/fact_view.py:75-77,151` overwrites the observation's entity with the requested symbol.

**Failure inference:** once original and revised filings coexist, the report may silently use the older filename rather than the selected package. Files from different quarters can leave a usable single-source report or block an otherwise valid one; an incorrectly placed same-period issuer XML is relabelled as the requested stock. Merely hashing the selected PDF again (`report_cli.py:86`) does not prove it is the intended document.

**Smallest fix:** select the registered capture/package for the requested stock and quarter, using its existing hash/version binding. Reuse the existing current/comparator entity check before cross-host canonicalization. This concerns input selection, separate from F04's timestamp admission.

### F13 — P2 — Correctness: a zero-PBT quarter aborts even when no tax calculation is available

**Evidence:** `src/fundamentals/api/pipeline_steps.py:181-184` aborts on zero PBT **before looking for the optional tax operand**. `output/pnl_lines.py:34-40` would already return OPERAND_MISSING for absent tax, without dividing.

**Observed probe:** `build_calculations` with sourced revenue/income, zero PBT and no filed tax raises PipelineError.

**Failure inference:** a valid break-even quarter cannot produce its sourced report although the unavailable ETR should not suppress facts and other valid calculations. **Smallest fix:** handle the zero denominator at the ETR calculation, emitting its existing nonnumeric unavailable outcome; remove the unconditional whole-report guard. The calculation must not emit a numeric rate for zero PBT.

### F14 — P2 — Correctness: news issuer matching ignores a conflicting unregistered symbol

**Evidence:** `src/fundamentals/news/entity.py:63-66` checks the resolved entity against supplied ISIN and scrip, but never against supplied symbol. NSE rows pass all those fields into the resolver (`ingest/news_nse.py:137-142`).

**Observed probe:** with only APARINDS registered and alias `Apar Industries`, supplying `symbol='OTHER'` and title `Apar Industries signs contract` resolves to APARINDS with no note and `contradictory=False`.

**Failure inference:** an announcement for an uncovered issuer that mentions a covered company is attached to the covered company's news feed despite the explicit different NSE symbol. **Smallest fix:** apply the existing contradiction comparison to the supplied symbol too. Keep genuine unknown-identity fallthrough explicitly unresolved or noted according to existing policy.

### F15 — P2 — Correctness: migration execution silently accepts a missing applied migration

**Evidence:** `src/fundamentals/pg/migrations.py:163-168` checks a recorded checksum only when the filename still exists (`actual is not None`). The CLI calls this function and prints success (`api/db_cli.py:178-179,196-199`). The separate live check is stricter (`pg/live_check.py:46-49`), but is not part of `apply_migrations`.

**Failure inference:** a checkout/package accidentally missing an already-applied migration passes `db migrate`, even though it cannot reproduce the installed schema. A later fresh restore/recreation cannot replay the advertised migration set. **Smallest fix:** treat missing recorded files as checksum/set drift in the existing loop (remove the `actual is not None` exemption). No new migration framework or DB change is required. Not reproduced against a database.

### F16 — P2 — Invariant: the reachable Markdown earnings facts table has no epistemic labels

**Evidence:** `src/fundamentals/output/earnings_update.py:417-425` emits numeric fact rows with value, concept, reconciliation and source only. Guidance has `[FORECAST]` at `:461,485`; calculations have an explicit computed label (`:520`). Reconciliation status is a separate dimension, not one of observed/computed/inferred/forecast/opinion. `api/report_cli.py:158-164` directly writes this renderer's Markdown.

**Failure inference:** consumers of `fundamentals report` receive unlabelled numerical facts even though the same output distinguishes guidance and calculations epistemically. Violates invariant 8 and `docs/specs/equity-os-s06-output-materiality-falsifiers.md:133-137`. The newer ledger sections carrying `{{e:...}}` do not repair this separate exported Markdown path.

**Smallest fix:** label the observed fact table/rows explicitly in the existing rendering. Do not change pinned historical import bytes or historical expected reports in place.

### F17 — P2 — Invariant: a committed recording script switches to one machine's main checkout

**Evidence:** tracked `scripts/equity_os_blueprint/record_inventory_batch_by_kind.sh:4` runs `cd` to a hard-coded machine-local repo path; `:16-18` stages and commits there. The script has only `set -u` (`:3`), so a failed `cd` does not stop execution. Its first generator pipeline (`:6`) also lacks pipefail, letting a successful `cut` hide generator failure.

**Failure inference:** invocation in an isolated worktree operates on the main checkout; on another host a failed `cd` permits the mutating workflow to continue in the caller's unrelated directory. Violates invariant 1 and defeats checkout isolation. **Smallest fix:** derive the repository root from the script location and make changing directory/generation fail the command immediately. No Git command was executed by this script during the review.

### F18 — P3 — Size: oversized files have concrete responsibility boundaries, not a case for wholesale deletion

**Observed sizes and proposed smallest splits:**

| File | Lines | Concrete split/cut |
|---|---:|---|
| `src/fundamentals/api/goal_runner.py:444` | 1,068 | Move source collection `:444-860` to one collection module; move latest-quarter alignment `:866-969` to its own existing-concern module if still needed. Keep reconciliation `:234-438` and `run_stock`/`run_wave` orchestration together. Reduce alias re-exports only after caller checks. Resolves eqos-4ff's monolith without a strategy/factory hierarchy. |
| `src/fundamentals/ingest/upstox_source.py:280` | 941 | Separate the closed route inventory/path construction `:280-498` from transport/config/read handling. Preserve the explicit approved route allowlist and terminal outcomes. |
| `scripts/equity_os_blueprint/validate_ledger_structural.py:264` | 3,244 | Extract pure review projections (F21), then split review/evidence validation, activation/transition rules, and whole-ledger traversal. Put traversal/argument handling behind main so imports have no execution side effect. Do not remove acceptance checks. |
| `scripts/equity_os_blueprint/record_inventory_review.py:249` | 1,857 | Share pure projection code (F21); separate filesystem publish/rollback from batch selection/review validation. Keep the transaction-like record operation in one orchestrator function. |
| `scripts/equity_os_blueprint/reconcile_ledger_approval_contracts.py:344` | 1,429 | Separate source-candidate transformation (`build_goal_and_structural_candidates`), authorization-response binding (`:587`), and validate/publish/rollback (`:938` onward). |
| `scripts/equity_os_blueprint/generate_initial_ledger.py:467` | 945 | Separate row generation/augmentation (`:467-839`) from no-clobber output publication (`:850-905`) and CLI (`:908`). |
| `scripts/validate_phase_0a_evidence.py:856` | 884 | Keep evidence validator implementation separate from beads-file loading, summary rendering and CLI. |

**Impact:** these files exceed the 800-line limit (`.claude/rules/python/coding-style.md:38`) and combine independently changing concerns. **Estimated deletion from the pure moves: 0.** The cuts counted below are specific; moving functions does not make the repo half as large. This is maintenance work, not a production acceptance blocker.

### F19 — P3 — Dead code: unused wrappers, declarations and their private-only scaffolding

**Evidence method:** targeted `rg` across **all `src/` and `scripts/`, including shell scripts**, for each symbol; the following public names have no callers/importers there beyond their definitions. AST/name census corroborated the Python results. Tests were deliberately not searched; this is production reachability evidence, not proof of no external Python consumers.

| Definition | Lines potentially removed | Existing reached alternative / evidence |
|---|---:|---|
| `canon/applicability.py:111` `load_applicability_rules` | 3 | Dictionary loads captured bytes through `parse_applicability_rules` (`canon/dictionary.py:455`). |
| `news/entity.py:72` `match_news_entity` | 13 | Both news adapters use `resolve_news_entity` and preserve its evidence. |
| `extract/pdf_statement_pages.py:290` `locate_statement_pages` | 11 | Production uses singular `locate_statement`; wrapper only converts exceptions to None. |
| `verify/three_source_map.py:278` `mappings_for_alias` | 10 | Six-line unused function plus `_ALIAS_INDEX` (`:257-259`) and its private error message (`:48`). `alias_roles` remains reached. |
| `store/pg_fact_store.py:154` `create_native_store` | 12 | Seven-line unused function plus its private-only INSERT_STORE/OPEN_EVENT SQL at `:106-110`. |
| `store/no_clobber.py:44` `preflight_paths` | 5 | CLI already calls `existing_paths` (`api/artifact_writer.py:32`). |
| `store/no_clobber.py:77` `fsync_directory` | 7 | No callers; do not confuse existence of this helper with a durability operation having run. |
| `ingest/upstox_instruments.py:103` `UpstoxInstrumentError` | 2 | No subclass, raise, except, importer, or caller uses it. |
| `contracts/retention.py:23` `RefusalCode` | 7 | Runtime uses the actual retention exception/outcome types; this enum is not referenced. |

Paths in this table are under `src/fundamentals/`. **Estimated cut: 70 lines**, subject to preserving any explicitly supported external API/fixture requirement; no claim that these deletions have already passed tests. Remove the unused public helpers rather than introducing a generic replacement interface.

### F20 — P3 — Dead-code/reachability debt: substantial approved APIs have no production consumer

**Observed:** the complete `src/fundamentals/ingest/upstox_candle_retention.py` (205 lines) has no importer in `src/` or `scripts/`; searches for `candle_version`, `replay_candle_versions`, `CandleReplayResult` and `compose_series` find only that module. The package has no dynamic loader for it in the inspected roots. `memory/store.py`'s Protocol is similarly not imported, but is an explicitly required interface and is **not recommended for deletion**.

`ingest/upstox_instruments.py:273` `canonical_parsed_digest` is also production-unreferenced, but `docs/research/upstox-integration-plan.md:1117` explicitly requires a determinism check using it. Its 10 lines are **not included in deletion savings**.

Other definition-only production APIs: `pg/identity_seed.py:188` `seed_identity` (and its private `_verified` at `:228`); `entity/identity_layers.py:193,223` `record_relationship` / `record_event`; `evidence/selection.py:116,238` `as_reported_periods` / `select_opening_operand`; `evidence/admission.py:269` `read_selected`; `ingest/upstox_statements.py:472` `read_key_ratios`; `evidence/vendor_screener.py:162` `extract_screener_schedule` (144-line function). `pg/test_databases.py:102` `drop_test_database` is definition-only in these roots but is a test-harness API, not a production deletion recommendation. `seed_issuer_identity` was initially a Python-only candidate but is **reached from `scripts/stage2_recreation_check.sh:164-167`** and is not dead.

**Disposition:** these are proven production-orphan surfaces in this checkout, **not proof that their contracts can be retired**. Candle replay is explicitly named in `docs/plans/product-completion-incomplete-capture-retention.md:90,103`, and temporal/identity APIs have domain contracts. Either name their actual intended consumer or retire that feature/contract before deleting its implementation. Do not add speculative callers just to make a reachability scan green. **Optional cut if candle replay is retired: 205 lines; excluded from the 300-line total.** No allegation that SQL identity history is unused or disposable follows from these Python caller searches.

### F21 — P3 — Size: copied blueprint projections require an entire equivalence mechanism

**Evidence:** `scripts/equity_os_blueprint/record_inventory_review.py:237-246` expressly says four functions were copied because importing the structural validator executes argument parsing and validation. AST comparison confirms duplicate implementations at recorder `:249-324` and structural validator `:72-76,264-318,427-437`. Recorder `:327-412` dynamically extracts/evaluates the validator's functions and samples rows just to establish those copies agree.

**Smallest simplification:** make those pure projection/hash functions importable once, use them from recorder and validator, and remove copy-equivalence machinery and its sample selection. Keep the actual independently required evidence/approval checks. This changes the old copy-specific implementation contract, so update its pointed-to description together; do not silently remove checks while leaving the contract claiming they ran.

**Estimated net saving: 140 lines**, allowing for imports and retained call sites. This simultaneously removes a reason the 3,244-line validator cannot be reused normally. Independent acceptance must still compare resulting ledger bytes/hashes; no new abstraction is required.

### F22 — P3 — Size: composition root repeats the same None-dispatch branch for every command

**Evidence:** `src/fundamentals/api/cli.py:608-703` repeatedly calls each dispatcher, tests `is not None`, and returns. These handlers already return the same `int | None` protocol. Credential-taking handlers differ only by an existing factory argument.

**Smallest simplification:** retain the handlers and registration, but iterate an ordered tuple of bound handlers (use `partial` for the few injected factories). Keep the direct special commands whose dispatch genuinely differs. This removes copy/paste branch maintenance without adding a command framework or decorator registry. **Estimated net saving: 60 lines.** No claim that the reachable CLI commands themselves are dead.

### F23 — P3 — Size: terminal provider-block classification is duplicated verbatim three times

**Evidence:** `_is_terminal_error` at `src/fundamentals/ingest/xbrl_source.py:94-100`, `ingest/bse_pdf_source.py:116-122`, and `ingest/bse_source.py:229-235` is AST-identical. Its HTTP-code and message-marker tables are identical too (`xbrl_source.py:72-83`, `bse_pdf_source.py:94-105`, `bse_source.py:207-218`).

**Smallest simplification:** put this one shared classification function and the common constants in the existing `ingest/http_session.py`; import it at the three callers. Preserve all source-specific exception types and pacing. **Estimated net saving: 30 lines** after imports. This is a small removal of real duplication, not a proposal for a new transport hierarchy.

## Numbered-invariant disposition

| # | Assessment from this audit |
|---|---|
| 1 | **Violation F17.** Concrete tracked machine-local path. Broad targeted scan found no other in-scope machine-local path use beyond the gate's regex intended to detect them. |
| 2 | No prohibited Git action executed by this review; inspected script stages explicit paths. Historical authorization for commits cannot be established by static source inspection. |
| 3 | `git ls-files scratchpad data` returned no tracked files. `.gitignore` covers them; `scripts/verify.sh:604-605` enforces the tracked-private-path rail. |
| 4 | **Not live-verified.** Current `.beads/config.yaml` does not contain the historical remote value described by the invariant. No Dolt/Beads/DB command was run; absence of that old YAML field alone is not proof of a wrong live remote. |
| 5 | No blueprint document was changed. Bootstrap/reconciliation scripts intentionally transform controlled artifacts; their operational authorizations were not replayed. |
| 6 | Registered arithmetic is deterministic in inspected canon/run-trace paths; **F01–F02 permit model-authored analytical numbers to evade output checks**. No claim that an LLM is invoked inside canonical arithmetic. |
| 7 | **F01–F03/F05** expose numerical/citation provenance gaps. Filed comparator/tax and approved risk-probe exceptions are not findings. |
| 8 | **F16.** Newer ledger sections and thesis opinion blocks do carry explicit labels; the older report facts table does not. Memory retrieval carries the stored class and derived status. |
| 9 | SQL row immutability is present (`migrations/0001_evidence.sql:664`, `0010_legacy_fact_store.sql:122`, `0012_report_ledger.sql:467`, `0016_memory.sql:235`). **F04–F06** concern misleading times, unbound hashes and overwritten gold, not an allegation that ordinary SQL fact updates are allowed. Authorized retention redaction is not a defect merely because it mutates/redacts vendor data. |
| 10 | **F08–F10** allow missing material work to appear complete; F01–F02 can admit unsupported numbers. Inspected formula evaluator explicitly propagates missing/undefined operands (`canon/formula.py:346-355`). |
| 11 | Separate promotion/approval exists in `memory/pg_store.py:119-142` and SQL support checks. Unsupported promoted memory is flagged by `memory/status.py:23-25`. No automatic draft-to-canonical-memory promotion found in inspected consumers; DB bypass resistance was not exercised. |
| 12 | No order/portfolio implementation found in the inspected research adapters. Upstox's explicit route catalogue is read-only and bars execution segments (`ingest/upstox_source.py:402-421`); its declared Analytics Token is not evidence of an execution credential. Do not remove the route allowlist on size grounds. |
| 13 | Retained snapshot paths exist and preserve acquisition metadata; **F04–F05** still fabricate/lose time or provenance on legacy paths. No retention replay/restore acceptance was run. |
| 14 | No basis to declare conditional sector packs/GBrain adopted from this audit. **F11** demonstrates a failed simpler lexical-consensus check; F18–F23 identify concrete complexity costs. Prior adoption decisions were not invented from file sizes. |

## Verification and limits

Pure probe commands completed with exit 0. They confirmed: ledger `revenue:500`/formula-literal exemption; thesis date/unit/sign laundering; `{}` usability/status; opposing-judgment silence; empty cross-foot success; required expenses absent from completion sets; conflicting-symbol news attachment; and zero-PBT/missing-tax refusal. These were direct function calls with synthetic values, not test-suite results. Four operator config SHA-256 pins were freshly checked and **all matched**; no stale-pin finding is asserted.

Static checks used targeted `rg`, `rg --files`, AST/function equality/import/name census, numbered source reads and read-only Git commands. Some broad source outputs exceeded display limits; named findings were followed up with focused reads. No finding relies on an unread truncated section. All identified findings are included above; no separate issue round is being withheld. Runtime migration/transaction behavior remains inferred pending authorized focused validation, not claimed proven in production.

**Implementation priorities:** close the numeric/cutoff/provenance gaps first; repair gold regression and completion truthfulness next; make the small deletion pass only against supported contracts. Preserve pinned historical parser/config/migration versions and append new versions when their semantics change. No blanket test expansion, new approval layer, or whole-repo rewrite is proposed.

**VERDICT: REQUEST_CHANGES**
