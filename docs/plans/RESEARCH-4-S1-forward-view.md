# RESEARCH-4 S1 — Base-case forward view — Implementation Plan

**Origin:** `docs/specs/2026-11-03-research-4-forward-view.md` (r6, approved with this plan by gpt-6.1-sol), §8 S1 and §10, with §0-§7. Bead `eqos-3v3w`. Format: `.claude/skills/planning/references/plan-format.md`.
**Status:** approved r3 (2026-11-03): approver gpt-6.1-sol, `APPROVE` after two fix rounds. Task 0 passed (below). The owner granted permissions A and B on 2026-11-04.
**Goal:** on `eqos_test_r4`, the FY27_Q1 run writes a `forward_view` section with a base-case five-year path by driver and division, recomputed by code on every check, all claims `MATCH`, with a real Sol `APPROVE` and a readable export.
**Out of scope:**
- Any live write: 0046, the thesis and the report stay off the live database until the live close.
- S2's `WORKING_CAPITAL` and `FUNDING` blocks and the days and cash anchors.
- S3's bear and bull computation, scenario section, trigger evaluator and watch rows.
- Parity (`--parity`) and the §7.6 rehearsals, both live close.
- The merge to `main` and the live cutover, which belong to the live-close plan; S1 only records what that plan must do (Left ready). The scheduled intake is not paused or changed.
- A runtime model call, a generic extractor, OCR, DCF, target price or recommendation.
**Constraints:**
- Committed migrations 0001 to 0045 are frozen; 0046 is new.
- Models never compute or invent numbers. Later evidence never enters an earlier report.
- Every verdict before a live write is a real Sol round on a real rendered artefact, never written by the orchestrator (spec §6.3).
- Crisp minimal code: every module traces to a spec requirement (`.claude/rules/core/04-agent-stack.md`).
- Never open `stage4_holdout.yaml`, `stage4_manifest.yaml`, `data/holdout/` or `data/raw/onboarding/`; no recursive grep over `tests/` or `data/`; do not print secrets or vendor readings; no machine-local absolute paths.
- One gate across the machine, no concurrent test runs, and no `claude` launches until it exits; a worktree does not relax this. Outside a gate, focused runs use `-n 0` and at most 8 test workers run across the machine.
- After three rounds an orchestrator ruling decides a finding's disposition; it never stands in for Sol's approval.

## Permissions gate

**The owner granted permissions A and B on 2026-11-04 (spec §7.1), so the declined routes below do not apply.**
- **Task 0 is read-only and may run first.**
- **No task after Task 0 starts before both rulings exist.** Task 1, creating the worktree and applying the invariant text, is the first task after them.
- **B declined:** S1 stops. The estimates start from division volumes and margins, so they cannot be built as designed.
- **A declined:** only A's last sentence goes into the invariant. Tasks 5 and 6 are replaced by the trace route (spec §7.1: about 200-350 more lines), through a plan revision and a fresh Sol round.

## Spec against code at `64d4e559`

Marks: **V** read in code or through read-only queries and the code's PDF loader, with digits masked, at this commit. **I** inference. Rows C-1 to C-5 are where the spec could not be built as written. Rows C-6 to C-11 are gaps or placements. Each resolution below is the one Sol's r1 ruling leaves standing; spec r6 carries the amendments it named.

| # | Spec says | Code or data says | Resolution |
|---|---|---|---|
| C-1 | r5 §10, OD-9: `narrate` refuses a version holding `forward_view` | **V** Every new run holds that section, `NOT_ASSESSED` included (§5.6). A literal refusal stops narrate on every future version and breaks `test_narrate_flow.py` and `test_narrate_refusals.py`. | **Accepted; spec amended.** Refuse a version holding any `fcst.` claim, before any model call. A `NOT_ASSESSED` section holds none, so it narrates as today. Both are tested. |
| C-2 | r5 §6.2 rule 3 `TABLE`: "the `PERIOD` span holds each of `columns`" | **V** The header of the pp. 3-5 tables sits across six blocks (`p3.b6` to `p3.b11`). No single span holds it. Book-order joining would let the author reorder spans and `columns` together. | **Spec amended.** New `HEADER` role with several spans. Code sorts them by retained position, never book order; their anchors must equal the closed list's; their joined text must equal `columns` joined. A permutation of both refuses. |
| C-3 | r5 §6.2 rule 3: `column` equals the required period | **V** The p6 table's columns are divisions (Conductor, Oil, Cable, Others, Total); the period is only in its heading `p6.b4`. Rule 4 needs that table's total PAT. | **Accepted; spec amended.** The closed list fixes each id's required `column` and required period separately. For a period-column table they are the same label. For `division_total_pat_fy26` the column is `Total`, its division header is verified as C-2, and a `PERIOD` span at the listed anchor must hold FY26. Case 4's wrong-year pair still refuses. |
| C-4 | r5 §6.2 rule 3: `SUBJECT` holds the division name; `numbers(quote)[columns.index(column)]` | **V** Oil and cable rows put the label in another block (`p4.b12`, `p4.b13`). One block can hold two rows (`p3.b13`). `(Note 1)` in a p6 label would shift the index. p6's PAT row holds a negative cell. The `numbers` regex drops minus signs (`quote_anchor.py:149`), so a quoted `-25` reads as `25`. | **Spec amended.** Row binding: `DisclosureSpec` holds `row_text`, `row_anchor` and `cells_anchor`, reviewed metadata from Task 0. The quote's anchor equals `cells_anchor`, and a `SUBJECT` span at `row_anchor` holds `row_text`. Scalar check: the quote splits on whitespace into exactly `len(columns)` cells, each read by a new sign-preserving grammar in `forward_validate.py`, any other token refusing; the selected signed cell equals `value`. `PROSE` refuses a signed or parenthesised number. `quote_anchor.py` and guidance parsing do not change. |
| C-5 | r5 S1 case 1: `P^c_0` reproduces the disclosure | **V** p3 has revenue, volume, EBITDA, EBITDA per MT and margin rows, and no realisation row. | **Accepted conditionally; spec amended.** Task 0 records whether an admitted source states a realisation. If none does, the exact `P^c_0 × V^c_0 / C = R^c_0` check tests only the implementation of the definition and says so; `EBITDA per MT` stays the independent comparison, within tolerance. If one does, it is compared as well. |
| C-6 | §1 and §6.2: an NSE capture, pinned by `observation_id` | **V** Blob `1deb9bd637c1` has three captures: 1766 `bse-documents`, 1924 `tijori` (derived), 2015 `nse-documents`. `importer._cited` takes the lowest id, so 1766. Observation 867 (attempt 302, `OK`, capture 2015, `an_dt` present) pins the NSE one. | **Accepted conditionally; §7.3 wording amended.** Keep `_cited`, with no refactor; the drafted `fcst.d.*` uses the same selection. Two identities stay explicit: the selected capture must be first-party, hold the exact pinned blob and supply the verified span; the pinned NSE observation stays the publication and issuer evidence. Task 0 checks each. A derived lowest id fails closed. |
| C-7 | Not stated | **V** `preflight` makes every non-credibility `SOURCE_QUOTE` of the previous head a guidance entry (`run_draft.py:316,331`). A future FY27_Q2 run would read `fcst.d.*` as management guidance, against invariant text "never an input". | `entries` also excludes `forward_view`, in the same line count, with a test. |
| C-8 | §8: the book is written once, complete, in S1; S3 lists its guards as acceptance | Thesis claims cannot be added after sealing, and an S3 guard could refuse a sealed book. | S1's import parses and seals all of `forward`, including `scenario.*`, `trigger.*`, `ScenarioFalsifier` and watch items, and enforces every §6.2 guard. S3 cases 1 and 2 become table rows in S1's book-guard test. S3 keeps computation, rendering and evaluation. |
| C-9 | §10 touch point: narrow `NOT_DONE`'s "forward scenarios" | **V** The line "This version does not contain: forward scenarios" (`run_draft.py:123`) would be false of an eligible S1 report, which holds a base case. | **Fixed in S1.** The line now names bear and bull scenarios, and a base case only where `forward_view` reads `NOT_ASSESSED`. C-10's extraction frees the room. S3 removes bear and bull from it. |
| C-10 | §10, non-contractual: `resolve_projections` in `citations.py`; §6.2 rule 6 at import | `citations.py` is 703 lines. `run_draft.py` and `api/cli.py` are 798, and a source file over 800 fails the gate's lint (`scripts/verify.sh:470-476`). Import has no run, so no manifest times. | New `forward_binding.py`. Task 8 moves `_check_sources`, `_operand_blobs`, `allowed_captures` and `check_blobs` to `ledger/run_sources.py` unchanged. `api/cli.py` changes only its import. `ledger_cli` passes `published_package` times to the importer. Existing source-check behaviour is preserved. |
| C-11 | §8: nothing live until the live close | **V** `_claim_row` inserts every `Citation` field (`store.py`), so once `projection_model` exists in code, any claim insert on a database without 0046 fails. `db check-live` (the `Live DB` row of `scripts/verify_project.sh`) requires every migration file recorded (`verification.md`), so it fails too. Both last from Task 5's commit until the live close. The 16:00 UTC scheduled DOCS-1 intake runs from the shared checkout against live, so a branch checked out there would run migration-dependent code against an unmigrated database. | **All RESEARCH-4 commits stay on branch `research-4`, in a dedicated worktree, until the live close;** the shared checkout stays on `main`. Merges keep history: no squash or rebase, because `evidence_holds` reads the book's exact commit. See Worktree, Left ready and Backup. |

**Also read, no change needed.**
- All 182 live `THESIS_CLAIM` rows already meet the exact-key rule (`thesis.X` → `falsifier.X`).
- `content_hash` covers the narrative only (`display.py:118-120`), so a new `Citation` field moves no stored hash.
- All document captures share one root, `data/raw/snapshots/v1`, so a run's `--snapshot-root` reads them.
- `first_party_documents.py:115` already parses `an_dt` as IST.
- The panel role can read the document tables (`0043:45`). Whether it can read the fiscal setting is checked in Task 7's risk.

## Design decisions

- **D1, write path.** `bind_probe` already holds the binder and selected statement outside the transaction, so it also builds `Probe.annual`. Inside the transaction, `write_run_draft` calls `forward_view` after `bound` is known and before `_check_sources`. `evaluate`'s `by_key` is built before the new claims join, so no shared consumer sees them.
- **D2, selection.** `Probe.annual` is `None` unless the selected statement's window is `YEAR` and its balance date is on or before the run's period end. `None`, or no bound book, or any of `applies_to`, `as_of`, `filed` differing, gives a `NOT_ASSESSED` section with no claim.
- **D3, S1's emitted claims.** Base projections for `REVENUE` and `PROFIT` only. Assumption endpoints for all 20 registry ids at `base` or `all`, so the reader sees every sealed base assumption, and S2 adds results rather than rows. A row states that working-capital and funding assumptions produce no result in this version. Bear and bull endpoints are sealed in the thesis and not cited until S3.
- **D4, layering.** The book schema and closed lists go in `contracts/`, because `verify/thesis_predicates.py` and `ledger/import_mapping.py` both read them. `forward_model.py` is pure. The checks in `forward_binding.py` sit below `lifecycle`; the writer in `forward.py` sits above it. `forward.py` never imports `risk_probe`.
- **D5, book text guards** run in `map_q0`'s `forward` branch, so a refusal is a `LosslessError` before anything persists. Schema faults raise through `bindable_thesis`. Span, cross-foot, issuer and time checks need the database, so they run in `_persist`.
- **D6, book corrections inside S1.** Until the report round closes, nothing is imported anywhere lasting, so a book fix edits the files, repeats the book round and restarts from a fresh restore. Once S1 closes, §7.6's new-successor route applies.

Cut for size: a data-driven line graph; storing each subexpression; a disclosure table parser; `fcst.base.cash` and `other_bank` (S2); any operator wrapper committed to the repo.

## File map

Line counts include imports and fixed text, which S3's estimate left out.

| File | Change | Responsibility | Lines |
|---|---|---|---|
| `migrations/0046_projection_citation.sql` | create | `PROJECTION` kind, `projection_model`, constraints, digest `CASE` | ≈ 45 SQL |
| `src/fundamentals/contracts/forward_book.py` | create | `ForwardBook` schema with exact fields and structural guards; `ASSUMPTIONS`, `DISCLOSURES`, `COMPARABLE` closed tables, row and header metadata | ≈ 180 |
| `src/fundamentals/ledger/forward_model.py` | create | Pure `compute`, `MODELS`, `OUTPUTS` with allowed scenarios, `block_inputs`, key helpers | ≈ 180 |
| `src/fundamentals/ledger/forward_validate.py` | create | `validate_book`: span, contract, header order, row binding, signed cells, period, cross-foot, issuer, time, calendar | ≈ 160 |
| `src/fundamentals/ledger/forward_binding.py` | create | `ROLES`, `resolve_projections`, `disclosure_contract`, wrong-book rule | ≈ 150 |
| `src/fundamentals/ledger/forward.py` | create | `annual_base` traces and anchors; `forward_view` claims and code-built section | ≈ 250 |
| `src/fundamentals/ledger/run_sources.py` | create | Moved source checks, unchanged, plus the two forward parameters | ≈ 75 moved |
| `src/fundamentals/ledger/import_mapping.py` | modify | `map_q0` branch for `forward`: self-cited claims, section lines, text guards | +65 |
| `src/fundamentals/ledger/importer.py` | modify | Pre-approval check in `_persist`; `published` parameter | +18 |
| `src/fundamentals/ledger/citations.py` | modify | Exact-key `_THESIS_CLAIM`; `_IMPORTED_QUOTES` excludes `BOOTSTRAP_THESIS` | +8 |
| `src/fundamentals/ledger/claim_check.py` | modify | `PROJECTION` joins `VALUED`; row 5 exact | +6 |
| `src/fundamentals/ledger/lifecycle.py`, `memory/retrieval.py` | modify | Call `disclosure_contract` and `resolve_projections` | +11 |
| `src/fundamentals/contracts/ledger.py`, `ledger/store.py` | modify | Enum member, `Citation.projection_model`, its column | +6 |
| `src/fundamentals/ledger/falsifier_status.py` | modify | `FORWARD_VIEW` in `DERIVED`; `BoundThesis.forward_claims` | +8 |
| `src/fundamentals/ledger/risk_probe.py` | modify | `Probe.annual`, built in `bind_probe` | +8 |
| `src/fundamentals/ledger/run_draft.py` | modify | Call `forward_view`; `entries` exclusion (C-7); `NOT_DONE` line (C-9); source checks moved out | net ≤ 0 |
| `src/fundamentals/verify/thesis_predicates.py` | modify | `ApprovedThesis.forward` | +3 |
| `src/fundamentals/ledger/rework.py`, `ledger/narrate.py` | modify | `fcst.*` routes (§7.6); C-1 refusal | +10 |
| `src/fundamentals/api/ledger_cli.py`, `api/cli.py` | modify | Pass manifest times; import path only | +6 |
| `docs/evidence/phase-0.5/q0-thesis-successor-3.{md,yaml}`, `config/ledger_import.yaml` | create, modify | Thesis 1.3.0 and its import entry | data |
| `tests/fundamentals/forward_support.py` | create | Synthetic book, invented PDF, pilot helpers | ≈ 120 |
| `tests/fundamentals/test_forward_model.py` | create | Pure model, bridge, rounding | ≈ 90 |
| `tests/fundamentals/test_forward_book.py` | create | Guard table at import, nothing persisted | ≈ 100 |
| `tests/fundamentals/test_forward_meaning.py` | create | `validate_book` refusals and controls, atomicity | ≈ 160 |
| `tests/fundamentals/test_forward_binding.py` | create | §7.4 proofs | ≈ 210 |
| `tests/fundamentals/test_forward_view.py` | create | Write path, fail closed, labels, anchors, C-1, C-7, C-9 | ≈ 175 |

**Size.** About **1,000-1,130 production lines** added, not counting the ≈ 75 moved unchanged, and 45 SQL, against the spec's 780-950 and 50. About **720-880 test lines** including helpers, against 370-480.
- **Why production is over:** C-8 moves about 50-60 lines of book parsing and guards from S3, which shrinks by that much. C-2 to C-4 add about 45. The layering in D4 adds imports and fixed text, which the spec's estimate likely undercounted (**I**).
- **Why tests are over:** S1 carries ten cases, nine §7.4 proofs and S3's cases 1 and 2. S3's suite measured 1,176 lines against an estimate of 695 for fewer proofs, which shows the estimate was low and does not establish that these tests cannot be smaller (**I**).
- **Stop.** After the tests round and the first green round, and again after any fix round, the orchestrator runs `wc -l`. Over **1,150 production or 900 test lines**: name what grew, cut or justify it in the bead before review. Helpers over 150 lines stop the tests round. "Could this be half the code?" stays a valid review finding; Sol found no defensible basis for promising half.

**Aggregate budget after the transfer (I, estimates, not ceilings).** It replaces spec r5's 1,085-1,350 production and 670-870 test lines.

| Slice | Production | Tests |
|---|---|---|
| S1 | 1,000-1,130 | 720-880 |
| S2 | 130-160 | 110-140 |
| S3, less C-8's transfer | 75-130 | 80-120 |
| Live close | 40-60 | 70-100 |
| **Total** | **1,245-1,480** | **980-1,240** |

Scratch tooling, never committed, under the shared checkout's `scratchpad/research4/s1/`: Task 0's script and the rehearsal gate, about 200 lines, not counted.

## Worktree

**One dedicated worktree on branch `research-4`, created in Task 1 from the commit holding the approved plan (`S1_BASE`), as a sibling of the shared checkout on the same filesystem.** All RESEARCH-4 implementation, commits, gates and rehearsals happen there. Task 0 is read-only and may run from either.
- **Shared checkout.** It stays on `main` for the scheduled DOCS-1 job and ordinary commits. Bead writes and the dashboard refresh stay there. `.beads/issues.jsonl` is never staged on `research-4`.
- **Verified before Task 1's first commit, and again at each task start:** the shared checkout's branch is `main` and it imports `fundamentals` from its own `src`; the worktree's branch is `research-4` and it imports from its own `src`, through its own `uv sync`. Every worker brief opens with the worktree check and stops on a mismatch, so a worker cannot commit to `main` by accident.
- **Retained inputs.** `git worktree add` writes tracked files, including the `stage4_*` fixtures, which nobody opens. Gitignored inputs arrive as follows (**V** `.claude/project/learnings.md`: symlinked directories fail `O_NOFOLLOW`, and partial copies fail gates). None of the steps prints content.
  - `.env`: copied, not printed. Secrets stay outside the checkouts.
  - `data/`: byte copy with `data/holdout` and `data/raw/onboarding` excluded by name. About 1.4 GB (**V**).
  - `data/holdout`: a symlink, never opened.
  - `data/raw/onboarding`: a hard-link tree, which adds directory entries without opening file bytes. Hard links need the same filesystem; if the sibling is on another, stop. Only the gate's existing stage4 test reads it, as it does on `main` (**I** from the learnings entry; this plan does not open that test's data). No agent opens or lists it, and a change appearing under it stops the task.
  - `scratchpad/`: real copies of the `*discovery*`, `*capture*` and `*smoke*` directories. The paste rail discovers them under its own checkout (`scripts/verify.sh:61-65`), so an empty worktree scratchpad would silently narrow it.
  - **Parity:** the file lists of the two `data/` trees are compared with `holdout` and `onboarding` pruned, and the capture directories' lists likewise.
- **Canonical scratch.** Rounds, rehearsal results and backups live in the shared checkout's `scratchpad/`, so removing the worktree loses nothing. Only `scratchpad/gate` is per checkout.
- **What a worktree does not isolate: the shared PostgreSQL service and the machine.** Test harness databases are minted per session (**V** `pg_support.py`), so a checkout's 0046 template cannot reach another's. A rehearsal has no such protection: each command names `EQOS_PG_DB=eqos_test_r4` explicitly and never relies on the copied `.env`, which names live, and the rehearsal script stops if the connected database is not `eqos_test_*`, or if `db restore --database` names anything else, because that argument selects the restore target independently of `EQOS_PG_DB`. `docker compose` runs only from the shared checkout.
- **The 16:00 UTC job.** This is a conservative rule for shared CPU and PostgreSQL load: no separate `claude` launch by the job is known, and the worktree already isolates code. The schedule is not paused. So a gate starts only when it can exit before 16:00 UTC, or after that day's job has finished; one overlapped is discarded and rerun. `db backup` and `db restore` keep the same window.

## Gate and test order

- **Slice name** `RESEARCH-4-S1`, run from the worktree. `S1_BASE` is recorded in the bead.
- **The one concurrency rule.** One gate across the machine, no concurrent test runs, and no `claude` launches until it exits. A worktree does not relax this. So no Claude worker is dispatched during a gate, and no database rehearsal runs beside one. It needs the compose PostgreSQL service and both markers green.
- **Red capture, orchestrator only.** After Task 2, `scripts/verify.sh red RESEARCH-4-S1` over the five test files. Tests import new production names inside tests and fixtures, so files collect first and fail before implementation. The orchestrator inspects the expected node set and each failure's cause. A collection failure is not behavioural proof, and a node passing before the change is vacuous and is fixed first.
- **Sealed tests.** Imported support files are sealed too. They change only through `scripts/verify.sh reseal RESEARCH-4-S1 <proof-file>`, after a genuine reopening proof.
- **Gate.** `VERIFY_SCOPE_BASE=$S1_BASE scripts/verify.sh gate RESEARCH-4-S1`, and its `ROUTE:` line is read first.
- **New tests in new files.** All five are new and stay under 800 lines. Nothing is added to `test_prep2b_run_draft.py` (763), `test_prep5_rework.py` (760), `test_credibility_binding.py` (734) or `test_ledger_import.py` (711). A changed file over 800 stays in hashed test scope and routes `CONTRACT`: the orchestrator owns the correction, splits or trims the file, and documents the reseal.
- **Fixtures** use invented text and an invented PDF, never pasted capture text; the gate's paste rail compares 60-character runs against private captures. Refusal tests inject an invented closed list through `DISCLOSURES`, since the real list pins real anchors; Task 10 proves the real list against the real spans.

## Backup

`research-4` is not pushed: only `refs/heads/main` may be pushed. A local branch or another worktree shares one object store.
- **What.** A Git bundle of the complete branch history at the shared checkout's `scratchpad/backups/research4/`, beside the database backups, with its SHA-256 and tip commit recorded in a manifest there.
- **Verified by restoring it.** The bundle verifies, a throwaway clone from it has the recorded tip, and from Task 10 on every configured `evidence_commit` is reachable there and `evidence_holds` is true against the clone.
- **When.** After each gate `PASS`, the book commit, Task 11's report `APPROVE` and the closing commit.
- **Also retained there, hashed:** the round briefs and responses, which a bundle does not hold.
- **Limit, stated plainly.** This is the same disk. It protects against branch and object-store damage, not disk loss.

## Tasks

### Task 0: Blocking read-only proof of the data

Goal: every data premise of S1 is proven or S1 stops with the gap named. Nothing is written anywhere but scratch.

Files:
- Create (never committed): `scratchpad/research4/s1/task0/` script, `disclosures.yaml`, `result.md`.
- Modify: none.
- Test: none; the script's checks are the evidence.

Interfaces:
- Consumes: `_Binder.mapped`, `_Binder.filed`, `citations._span`, `citations._first_party_capture`, `load_pdf` beneath them, `EvidenceRepository`, `store.read_version`.
- Produces: `disclosures.yaml`, the candidate closed list with id, blob, form, columns, required column and period, contract, `header_anchors`, `period_anchor`, `row_text`, `row_anchor`, `cells_anchor`, context spans and value, consumed by Tasks 4 and 10. The run's pins for `forward.filed.context`.

Approach: run with `PGOPTIONS` setting `default_transaction_read_only=on`, so a write fails rather than slips. An Opus worker selects the spans from the §1 pages; code checks every one. The checks, exactly spec §8:
1. Under FY27_Q1's pins (`config/aparinds-fy27-q1-pg.yaml`), the `MAPPED` interpretations on the FY26_Q4 capture (`be8ef6514df9`) count exactly 181, reconciled by key, with no key holding two values.
2. One `MAPPED` interpretation for each §4 line, including all five rate-anchor formulas' lines.
3. Each disclosure's span and context resolve through `_span`, which reaches `load_pdf`, on the capture `_cited` would select. That capture is first-party and holds the pinned blob (C-6). Each `TABLE` entry's header anchors, in retained position order, join to exactly its `columns`, its `column` occurs once, its cells parse to `len(columns)` signed cells, and the selected cell equals its value.
4. The pinned observation for each capture outside the package: entity is the report's, an `OK` attempt whose body is the blob, `an_dt` read from exactly that payload and on or before `as_of`.
5. All cross-foots pass on real values, tolerance one crore: each division's revenue against its `segment_revenue` member on the `YEAR` window; the division table's total PAT against filed `profit_for_period`; `EBITDA` against `EBITDA per unit × volume`.
6. The `QUARTER` metrics' claims exist on FY27_Q1 v23: `cmp.revenue.yoy.pct`, the margin key, `cmp.profit_for_period.yoy.pct`, `cmp.basic_eps.yoy.pct`.
7. No version of any `BOOTSTRAP_THESIS` report, approved head or superseded, holds a `SOURCE_QUOTE` claim.
8. Whether any admitted source states a conductor or oil realisation, recorded in `result.md`; this decides C-5's wording in case 1. No failure attaches to the answer.

Verification: the script exits 0, with each check's count and outcome in `result.md`; `git status` is unchanged. Digits read from spans stay in scratch. Sol does not review this task; its output goes to the book round.

Dependencies: None; may run before the rulings.

Risks: **any failure stops S1 with the gap named.** No fallback, no substitute span chosen silently. A check needing a schema change is a plan revision. The worker opens only the §1 pages; the 2026-10-29 filing is opened by nobody.

**Task 0 result (2026-11-03, at `ec44e6ce`).** Checks 1 to 7 pass and stop nothing; check 8: no admitted page in the §1 set states a conductor or oil realisation, so C-5's wording applies. The candidate list holds 12 entries, 11 `TABLE` and 1 `PROSE`; its ids and contract names are drafts for Tasks 4 and 10. Figures stay in scratch. Corrections for the tasks below:
- `PGOPTIONS` alone does not make a session read-only, because the code's `conninfo` sets libpq `options`, which overrides it. A read-only script sets the option in the connection or `conn.read_only = True`, and checks `transaction_read_only`.
- Spec §1's "not in `Retrospective.published`" is wrong for the investor update: it is in the pinned manifest. A retrospective run takes the manifest's time, so Task 7 checks S1 case 5's `published.at` refusal independently of that lookup.
- `conductor_utilisation` and `working_capital_days` each state a range, so under §6.2 rule 3 they are not disclosures and their assumptions show no comparison. Spec §4 lists them as `fcst.d.*`, and S2 case 2 expects one. S1 omits them; the S2 plan resolves case 2.

### Task 1: Worktree, retained inputs and the invariant text

Goal: the dedicated `research-4` worktree exists with its retained inputs and isolation checks passing, and its `.claude/project/invariants.md` holds extensions A and B verbatim from spec §7.1, after invariant 7's 2026-10-28 extension, naming the owner's ruling date.

Files:
- Modify: `.claude/project/invariants.md`
- Test: none.

Interfaces:
- Consumes: the owner's rulings; spec §7.1 text; the Worktree section.
- Produces: the worktree every later task runs in; `S1_BASE`; the invariant every later task's claims rest on.

Approach: the orchestrator creates the worktree and brings in inputs as the Worktree section states, excluded paths included. Then a tiny edit there, exact text, no rewording, committed on `research-4`.

Verification: branch and import location checks in both checkouts; the two parity comparisons empty; one `retained` and one `pg` test green from the worktree; a diff of the file against the spec's two quoted blocks shows only the addition; structural gate items 1 and 5.

Dependencies: Task 0 passed; both rulings.

Risks: wording drift, so it is copied, not retyped. A worker starting in the wrong checkout, so each brief's first check stops it. Any step that would open an excluded path stops the task.

### Task 2: Acceptance tests and red proof

Goal: the five test files and the support module exist in final form and every node fails against unchanged source.

Files:
- Create: `tests/fundamentals/forward_support.py`, `test_forward_model.py`, `test_forward_book.py`, `test_forward_meaning.py`, `test_forward_binding.py`, `test_forward_view.py`.
- Modify: none.
- Test: the files themselves.

Interfaces:
- Consumes: every name in the Produces blocks of Tasks 3-8; `pilot`, `dictionary`, `mapping_set` from `test_prep2b_run_draft.py`; `_rerun`, `_request_changes` from their modules; the git-backed evidence setup in `test_ledger_import.py`.
- Produces: `forward_support.synthetic_book(**overrides) -> dict[str, Any]`, a round-number book; `invented_pdf(path: Path) -> str`, returning its SHA-256; `imported_thesis(pilot, book, tmp_path) -> int`.

Approach: production names are imported inside tests and fixtures, so each file collects before the change. One Opus round writes helpers first and reports their `wc -l`. Refusals are table rows over one prepared state, each row naming its reason and asserting no delta, not one test function per row. The cases are the map under Acceptance. Tests encode why: each hand-computed value is stated in the test, from the spec's formula, never from `compute`.

Verification: `scripts/verify.sh red RESEARCH-4-S1 tests/fundamentals/test_forward_model.py tests/fundamentals/test_forward_book.py tests/fundamentals/test_forward_meaning.py tests/fundamentals/test_forward_binding.py tests/fundamentals/test_forward_view.py` reports all nodes red, none missing; the orchestrator has read the node set and each failure's cause.

Test seams: `compute`, `import_thesis_successor`, `validate_book`, `check_version`, `write_run_draft`, `ledger check`, database constraints. No private helper.

Dependencies: Task 1.

Risks: **test-first; this is the plan's main behaviour risk control.** The integration file may outgrow its estimate; the stop above applies.

**Orchestrator rulings during Task 2 (2026-11-04).**
- **Helper stop.** Raised from 150 to 220 lines: the first draft reached 181, mostly the data the acceptance map requires (12 disclosures, layout controls, a complete book). The 900-line test total is unchanged. Sol may still judge the size at phase end.
- **Schema faults (corrects D5).** `import_thesis_successor` calls `map_q0` before `bindable_thesis` (`importer.py`), so the `forward` branch parses the book inside `_parsing` and every guard and schema row refuses with `LosslessError`, as Task 4 states. `bindable_thesis` is not the refusal path.
- **One patch point for `DISCLOSURES`.** Production reads `forward_book.DISCLOSURES` through the module at call time, never `from ... import DISCLOSURES`, so tests patch one attribute and need no module that a later task creates.
- **Names the plan left open.** The tests fix the `OUTPUTS` lines, bridge keys, `BookFault` members and `DisclosureSpec` fields, following the spec's terms. Implementers follow the tests.
- **Digest proof.** The frozen pre-0046 `version_sealed_digest` body from `migrations/0042_thesis_claim_citation.sql` is loaded under another name and compared with the current function on one database, for claims with a null `projection_model`. Task 11 keeps the real before-and-after proof.
- **Real filed figures in `test_forward_view.py`.** The invented PDF is generated at run time under `tmp_path` so it can cross-foot against the retained statement; only the generator is committed. Rate anchors are hand-checked on a seeded statement.
- **FY26 computed rows are exactly nine, not "about fifteen"** (Task 3, spec §7.2): `conductor_realisation`, `oil_realisation`, `others_revenue`, `others_share`, `residual_ebitda_share`, `margin`, `conductor_margin`, `oil_margin`, `cable_margin`. Filed FY26 lines stay on `probe.*` and disclosed ones on `fcst.d.*`. Division margins rest on spec §5.3's "Rows" sentence and S1's FY26-FY31 table. `E^i_0` is the disclosed figure, and `E^c_t = V^c_t eC_t / C` applies for `t >= 1`.

**Task 2 result (2026-11-04, `02de561e` on `research-4`).** Red proof 26/26. **Over the stops:** 1,567 test lines including a 411-line helper, against 900 and 220, after a real 17% reduction from 1,880 unformatted lines, with no acceptance row dropped. What holds it up is listed in the bead. Ruled: proceed, and Sol judges necessity and size at phase end. The aggregate test estimate moves from 980-1,240 to about 1,830-1,930 (**I**), assuming the later slices' estimates hold.

### Task 3: The pure model

Goal: `compute` gives each `REVENUE` and `PROFIT` line exactly as spec §5.1-§5.3, with failures per block and no exception but an unknown model.

Files:
- Create: `src/fundamentals/ledger/forward_model.py`
- Test: `tests/fundamentals/test_forward_model.py`

Interfaces:
- Consumes: only the standard library and `contracts`; no database, no ledger imports above it.
- Produces:
  - `class Block(StrEnum)`: `REVENUE`, `PROFIT`.
  - `class ModelResult` (frozen): `values: Mapping[str, Fraction]`, `failed: Mapping[tuple[str, Block], str]`.
  - `compute(model_id: str, inputs: Mapping[str, Fraction], fiscal_year_end_month: int, blocks: Set[tuple[str, Block]]) -> ModelResult`, keyed by claim key. An assumption is looked up under its scenario, then `all`.
  - `MODELS: Mapping[str, Callable[..., ModelResult]]`, holding `forward.1`.
  - `class OutputSpec` (frozen): block, scenarios, periods, value kind, unit, currency, scale, precision, class. `OUTPUTS: Mapping[str, Mapping[str, OutputSpec]]`, by model then line. S1 registers `base` only; S3 adds bear and bull to the lines it computes, leaving `forward.1`'s existing values unchanged.
  - `block_inputs(scenario: str, block: Block, scopes: Mapping[str, str]) -> tuple[str, ...]`; `projection_key(scenario: str, line: str, period: str) -> str`; `parse_projection_key(key: str) -> tuple[str, str, str] | None`; `stated(value: Fraction, precision: int) -> Decimal`, `ROUND_HALF_EVEN` on the exact fraction, never chained.

Approach: straight-line code in the spec's fixed order. Twenty-five lines for FY27-FY31, about fifteen FY26 computed rows, six bridge terms and their shares. A share is absent when `Rev_5 <= Rev_0`. `fiscal_year_end_month` is in the signature from S1, but no S1 line uses days; `days_t` arrives in S2. A growth at or below -100, or a zero or negative `V_0` or `Rev_0`, fails the block and those after it.

Verification: `uv run pytest tests/fundamentals/test_forward_model.py -n 0` green. Named cases: round-number book, each line FY27-FY31 exact; bridge sum exact, and with a shrinking path no shares; negative `s_0`; missing input fails its block and later ones; a domain fault likewise; unknown model raises; `stated` halves to even.

Dependencies: Task 2.

Risks: financial logic. Opus, test-first. Hand values live in the test, not derived from the code.

### Task 4: Book schema, mapping and text guards

Goal: a twin with `forward` parses to a frozen, exact-field book, maps to self-cited and quote claims in the thesis, and every §6.2 guard refuses at import with nothing persisted.

Files:
- Create: `src/fundamentals/contracts/forward_book.py`
- Modify: `src/fundamentals/verify/thesis_predicates.py`, `src/fundamentals/ledger/import_mapping.py`
- Test: `tests/fundamentals/test_forward_book.py`

Interfaces:
- Consumes: `scan_narrative`; `_slot`, `_require`, `LosslessError`; `disclosures.yaml` from Task 0 for `DISCLOSURES`.
- Produces:
  - Models with `extra="forbid"`: `ForwardBook`, `Disclosure`, `DisclosureContext`, `Published`, `FiledPin`, `Assumption`, `Scenario`, `Trigger`, `ScenarioFalsifier`, `WatchItem`, `ModelCorrection`; `class ContextRole(StrEnum)`: `HEADER`, `PERIOD`, `SUBJECT`, `UNIT`, `DEFINITION`.
  - `ASSUMPTIONS: Mapping[str, AssumptionSpec]`, the 20 ids with unit, value kind, bounds and direction. `DISCLOSURES: Mapping[str, DisclosureSpec]`, with form, contract, required period and column, subject and unit text; for `TABLE`, `header_anchors`, `period_anchor` (only where the column is not the period), `row_text`, `row_anchor` and `cells_anchor`. `COMPARABLE: Mapping[str, frozenset[str]]`.
  - `ApprovedThesis.forward: ForwardBook | None = None`.
  - Thesis claim keys: `assumption.<scope>.<id>.<y1|y5>`, `scenario.<id>`, `trigger.<id>`, each self-cited `POLICY`, labelled opinion; `disclosure.<id>`, `SOURCE_QUOTE` with sealed contract fields and code-derived `quote_qualifiers`.

Approach: `map_q0` gets one `forward` branch; lists elsewhere keep today's path. Every statement and rationale must be in the Markdown, and each trigger states its predicate there as `_falsifier` requires. Numbers become claims with slots in a code-built `forward` section, so `narrative(...).startswith(md)` still holds. Nothing in `forward` joins `falsifiers`. Guards as spec §6.2: no `{` or `}`, `scan_narrative`, closed lexicon, registry bounds, scenario order, probabilities exactly 100, exact horizon, trigger, falsifier and watch coverage (C-8).

Verification: `uv run pytest tests/fundamentals/test_forward_book.py -k map_q0 -n 0`. This task's checkpoint is schema and mapping only: a valid synthetic book maps; each guard row of case 7 and S3 cases 1 and 2 refuses with `LosslessError`, for its named reason; F1-F11 thresholds and `falsifiers` are unchanged from successor 2's. Successful import does not exist yet. The same rows through `import_thesis_successor`, asserting no version, seal or approval, go green in Task 7, after the valid control imports.

Test seams: `map_q0`; `import_thesis_successor` from Task 7.

Dependencies: Task 3.

Risks: two parsers read the twin, `yaml.safe_load` and `_lexemes`. A test holds that the parsed book and the mapped claims agree on every value. A number word in ordinary rationale refuses; accepted, the drafter gets the lexicon.

### Task 5: The projection record and citation rules

Goal: 0046 exists, every prior digest is unchanged, a `PROJECTION` claim stores and reads back, and the two citation changes alter no existing outcome.

Files:
- Create: `migrations/0046_projection_citation.sql`
- Modify: `src/fundamentals/contracts/ledger.py`, `src/fundamentals/ledger/store.py`, `src/fundamentals/ledger/claim_check.py`, `src/fundamentals/ledger/citations.py`
- Test: `tests/fundamentals/test_forward_binding.py`, the constraint and digest nodes.

Interfaces:
- Consumes: 0042's shape.
- Produces: `CitationKind.PROJECTION`; `Citation.projection_model: str | None`; column `numeric_claims.projection_model`; `check_claim` row 5 comparing a `PROJECTION`'s stored value with `resolved.value` exactly; `_THESIS_CLAIM` taking the expected cited key from `cited_key(claim_key: str) -> str | None` (`thesis.X` → `falsifier.X`, `fcst.a.X` → `assumption.X`, `fcst.p.X` → `scenario.X`, `fcst.t.X` → `trigger.X`, else `None`).

Approach: as 0042. Add the kind to the kind check and the null-key set. A `PROJECTION` sets no other citation column, has a value and a model, and is not unresolved. Every other kind has a null model. `version_sealed_digest` gains one `CASE` after the thesis columns, empty when the column is null. `_IMPORTED_QUOTES` gains `r.kind <> 'BOOTSTRAP_THESIS'`.

Verification: `uv run pytest tests/fundamentals/test_forward_binding.py -k "constraint or digest" -n 0`, and `test_prep2b_citations.py`, `test_pilot_citations.py`, `test_phase05_thesis_impact.py`, `test_ledger_import.py` green unchanged.

Test seams: database constraints; `eqos.version_sealed_digest`; `check_claim`.

Dependencies: Task 2.

Risks: **characterization first:** a digest captured before 0046 in the test must equal the one after, on a version holding each citation kind. Task 11 repeats it on the restored live data. The real proof of `_IMPORTED_QUOTES`' safety is Task 0's check 7.

### Task 6: Binding and recomputation on check

Goal: `check_version` recomputes every `PROJECTION` from the version's own bound inputs, a tampered value, input, shape or binding fails exactly its block onward, and contracts replay version-bound with no `bound` supplied.

Files:
- Create: `src/fundamentals/ledger/forward_binding.py`
- Modify: `src/fundamentals/ledger/lifecycle.py`, `src/fundamentals/memory/retrieval.py`
- Test: `tests/fundamentals/test_forward_binding.py`

Interfaces:
- Consumes: `compute`, `OUTPUTS`, `block_inputs`, `parse_projection_key` (Task 3); `check_claim`; `bindable_thesis`; the thesis's sealed twin.
- Produces:
  - `disclosure_contract(cursor: Cursor[Any], draft: VersionDraft, claim: NumericClaim, entity_id: int) -> GuidanceContract | None`.
  - `is_book_quote(claim_key: str) -> bool`, true for `disclosure.*` and `fcst.d.*`.
  - `resolve_projections(cursor: Cursor[Any], draft: VersionDraft, resolved: Mapping[str, ResolvedCitation | None], *, mode: RunMode, cutoff: datetime) -> dict[str, ResolvedCitation | None]`.

Approach: spec §7.3's five steps and role table, unchanged. Step 2 refuses a scenario the line's `OutputSpec` does not register. Held blocks are read from the version's projection keys, never from current code. The sealed `fiscal_year_end_month` is read from the cited twin. The twin is read once per check, not per claim. Each resolved value is `stated(exact, registered precision)`, with `times` the union of its block's inputs' resolved times. `lifecycle` first resolves as today, using `disclosure_contract` for book quotes, then merges `resolve_projections`.

Verification: `uv run pytest tests/fundamentals/test_forward_binding.py -n 0 -k "not differing_book"`, the §7.4 rows in the acceptance map. The recorded recomputation-argument proof runs here. The differing-book refusals need `validate_book`, so they run at Tasks 7 and 8, and the complete file runs after Task 8.

Test seams: `check_version` and `ledger check` on versions written by the test, with one stored field changed through the admin connection in a throwaway database. The fixture imports the book through `map_q0` and today's post-seal `validate`, which pass once this task lands; Task 7 adds the pre-approval check and these nodes must stay green. The calendar node wraps the recomputation call to record its argument.

Dependencies: Tasks 3, 4, 5.

Risks: **test-first.** This is the plan's most uncertain part (spec §8 says so). `forward.2` is registered in `MODELS` by the test only. Replay stability in S1 is an analogue: a version holding only `REVENUE` keeps `MATCH` under code that also registers `PROFIT`. The real proof is S2 case 9.

### Task 7: Meaning validation and the pre-approval check

Goal: `validate_book` proves each disclosure's meaning, and a failing book leaves no version, seal or approval, with the prior thesis still the bound head.

Files:
- Create: `src/fundamentals/ledger/forward_validate.py`
- Modify: `src/fundamentals/ledger/importer.py`, `src/fundamentals/api/ledger_cli.py`
- Test: `tests/fundamentals/test_forward_meaning.py`

Interfaces:
- Consumes: `ForwardBook`, `DISCLOSURES` (Task 4); the citation rules (Task 5); `disclosure_contract`, `resolve_projections` (Task 6); `citations._span`, `_first_party_capture`; `check_version`; `published_package`; `first_party_documents` `an_dt` parse; `EvidenceRepository.settings_as_of`.
- Produces:
  - `class BookRefusedError(ValueError)`, carrying `reason`, a stable code from a closed `BookFault` enum.
  - `validate_book(cursor: Cursor[Any], book: ForwardBook, *, entity_id: int, published: Mapping[str, datetime], catalog: SourceCatalog, snapshots: SnapshotStore) -> None`.
  - `import_thesis_successor(..., published: Mapping[str, datetime] | None = None)`. A book with no publication time for a disclosure refuses.

Approach: rules 1-6 of spec §6.2 as amended in r6. `BookFault` names each cause, so a refusal row asserts it reached the intended check: a quoted negative cell asserts the signed-cell fault, not an earlier prerequisite. Filed values read under `forward.filed`, including `segment_revenue` by its dimension members `conductor`, `transformer_and_speciality_oils`, `power_telecom_cables` (**V** live members, `PRE_ELIMINATION`). A row says "single-source" where no filed figure exists. The book's `fiscal_year_end_month` must equal the entity's setting. `_persist` runs `validate_book` and `check_version` after `create_version` and before the seal, only for a twin with `forward`, and raises `ImportRefusedError` so the transaction rolls back.

Verification: `uv run pytest tests/fundamentals/test_forward_meaning.py -n 0`, and `test_forward_book.py -k import -n 0`. **The valid control imports to `APPROVED` first; if it fails, no refusal result counts.** Rows are case 4's and case 5's time refusals plus §7.4 Import atomicity for each of validation, citation, issuer, publication and cross-foot. Also `test_forward_binding.py -k differing_book_import -n 0`: an import whose book's fiscal month differs from the entity's setting refuses.

Test seams: `import_thesis_successor` on a pilot database, an invented PDF retained through the snapshot store, seeded document observations.

Dependencies: Tasks 4, 5, 6.

Risks: **the panel role's read of the fiscal setting is unverified**; if refused, the setting's value is passed in from the runtime role at the composition root, with no new grant. `_persist` is shared: the branch must leave the Q0 and successor 2 paths byte-identical, proven by `test_ledger_import.py` staying green unchanged.

### Task 8: The writer and the section

Goal: an FY27_Q1-shaped run writes `forward_view` per spec §3, §5.6, §5.7 and §8's "Reader sees", and every other run writes a `NOT_ASSESSED` section with no claim.

Files:
- Create: `src/fundamentals/ledger/forward.py`, `src/fundamentals/ledger/run_sources.py`
- Modify: `src/fundamentals/ledger/risk_probe.py`, `src/fundamentals/ledger/run_draft.py`, `src/fundamentals/ledger/falsifier_status.py`, `src/fundamentals/ledger/rework.py`, `src/fundamentals/ledger/narrate.py`, `src/fundamentals/api/cli.py` (import line only)
- Test: `tests/fundamentals/test_forward_view.py`

Interfaces:
- Consumes: `compute`, `OUTPUTS` (Task 3); `ForwardBook`, `COMPARABLE` (Task 4); `validate_book` (Task 7); `_Binder.evaluate`, `child`, `filed`, `conclude`, `_total`.
- Produces:
  - `FORWARD_VIEW = "forward_view"`, in `DERIVED`. `BoundThesis.forward_claims: Mapping[str, tuple[int, NumericClaim]]`, every `assumption.`, `scenario.`, `trigger.` and `disclosure.` claim with its row id.
  - `class AnnualBase` (frozen): `claims: tuple[NumericClaim, ...]`, `pin: FiledPin`. `annual_base(binder: _Binder, source: Provenance, statement_balance: date, window: PeriodInterval | None, selection: SelectionSource, fiscal_year_end_month: int) -> AnnualBase | None`. `Probe.annual: AnnualBase | None`, and `Probe.fiscal_year_end_month: int`.
  - `class ForwardBuilt` (frozen): `section: tuple[str, str]`, `claims: tuple[NumericClaim, ...]`, `blobs: frozenset[str]`, `published: Mapping[str, datetime]`.
  - `forward_view(cursor: Cursor[Any], bound: BoundThesis | None, run: RunDraft, by_key: Mapping[str, NumericClaim], catalog: SourceCatalog, snapshots: SnapshotStore) -> ForwardBuilt`.
  - `_check_sources(..., extra: frozenset[str], published: Mapping[str, datetime])` in `run_sources.py`. `check_blobs` keeps its signature for `api/cli.py`.

Approach:
- `annual_base` builds `fcst.base.ebitda`, `.ppe` and five rate anchors as `CALCULATION` traces per spec §4 and §5.7, each guard failure leaving that claim absent.
- `forward_view` compares the book with the run (D2), runs `validate_book`, resolves the fail-closed blocks of §5.6, calls `compute`, and builds claims from `OUTPUTS`. Disclosures become `fcst.d.*` on the capture selected as C-6. Assumptions, probabilities and thresholds become `THESIS_CLAIM`, labelled opinion. The comparison renders `INSIDE`, `BELOW`, `ABOVE` per reference year and `NOT_COMPARABLE` otherwise.
- All text is code-built except each rationale, copied verbatim. Every number is a placeholder, including the headline's. "Largest driver" and volume against price are picked by code from exact values. Section order: FY27_Q2 exclusion and as-of statement; headline; capacity and cable limits; base table FY26-FY31; driver rows and bridge; unit economics by division; assumption table with quote and anchor; `NOT_ASSESSED` list per spec §3; retrospective limit.
- A structural fault raises `RunDraftError`: unknown model, mismatched unit, cross-foot failure.
- `run_draft` moves its source checks out, calls `forward_view`, appends claims before `_check_sources`, appends the section after credibility, and excludes `forward_view` from `entries` (C-7). The `NOT_DONE` line changes as C-9 states. `rework.plan` refuses `fcst.*` rejections naming spec §7.6's routes. `narrate` refuses any `fcst.` claim before any model call (C-1).

Verification: `uv run pytest tests/fundamentals/test_forward_view.py tests/fundamentals/test_forward_binding.py -n 0`, the complete binding file with `differing_book_write`, then the targeted existing suites `test_prep2b_run_draft.py`, `test_prep5_rework.py`, `test_credibility_binding.py`, `test_narrate_flow.py`, `test_narrate_refusals.py`, each with `-n 0`. An existing assertion of a section count changes by that one line only, with no file passing 800. `wc -l src/fundamentals/ledger/run_draft.py src/fundamentals/api/cli.py` at or under 800.

Test seams: `write_run_draft` through the pilot; `scan_section`; `ledger check`.

Dependencies: Tasks 3, 4, 5, 6, 7.

Risks: an existing assertion may name the old `NOT_DONE` line; `test_prep2b_run_draft.py` holds none (**V**), and any found elsewhere changes by that line only. **A new section in every run** touches every run path. Characterize first: on a pilot run with no book, every other section and claim equals the pre-change run's. Mutating `DERIVED` must not change `rework` for a version with no `fcst.` claim; `test_prep5_rework.py` proves it. `annual_base` stores traces outside the transaction, as the probe does, so a later refusal leaves unused traces, which is existing behaviour.

### Task 9: Gate and phase-end code review

Goal: the gate routes `PASS`, and Sol's review loop over the S1 diff closes before any real book or rehearsal cost is spent.

Files:
- Modify: whatever a fix round requires, only within the file map.
- Test: existing.

Interfaces:
- Consumes: Tasks 1-8 committed in reviewable steps.
- Produces: a code commit the book and rehearsal run against, recorded in the bead.

Approach: orchestrator runs the gate. A fresh Sol round (`gpt-6.1-sol`, `high`) reports all issues in one pass against this plan and spec, including "could this be half the code?". A fresh Opus round fixes them, and a fresh Sol round checks the fixes, per `.claude/rules/core/04-agent-stack.md`. Three rounds without convergence: the orchestrator rules on each residual.

Verification: `VERIFY_SCOPE_BASE=$S1_BASE scripts/verify.sh gate RESEARCH-4-S1` prints `ROUTE: PASS`; Sol's `APPROVE` is on file; `wc -l` within the stop; a verified bundle of the tip exists (Backup).

Dependencies: Task 8.

Risks: a later book or rehearsal defect may change code. That change gets its own gate, a Sol check of the fix, and a fresh restore.

### Task 10: The assumption book

Goal: thesis successor 1.3.0 exists, its bytes committed, with Sol's real `APPROVE` as its ruling.

Files:
- Create: `docs/evidence/phase-0.5/q0-thesis-successor-3.md`, `docs/evidence/phase-0.5/q0-thesis-successor-3.yaml`
- Modify: `config/ledger_import.yaml` (`thesis_successor`, with `cutoff` equal to `decided_on`)
- Test: `validate_book` with the real closed list against the real spans, and the import, on a throwaway `eqos_test_*` database; Task 11.

Interfaces:
- Consumes: `disclosures.yaml` and pins (Task 0); `ASSUMPTIONS`, `DISCLOSURES`; guards and `validate_book`.
- Produces: `forward:` per spec §6.2, complete: all 20 assumptions with three paths where they vary, three scenarios with probabilities, triggers, falsifiers and watch items. F1-F11 unchanged. `applies_to: FY27_Q1`, `as_of: 2026-07-31T10:14:41Z`, `model: forward.1`, `fiscal_year_end_month: 3`.

Approach:
1. **Draft.** A fresh Opus worker drafts offline. Its brief holds only the admitted captures, the code-rendered FY26 anchors and the FY27_Q1 quarter from v23's claims. It is told the lexicon and that FY27_Q2 evidence exists and must not be opened. It writes values and rationale only, and never states a result (spec §6.1, §6.3 rule 7).
2. **Mechanical checks first:** guards and `validate_book` on a throwaway test database. Model faults go back to the drafter.
3. **Book round, real Sol:** Markdown, twin and complete cited pages against spec §6.3 rule 2's list. Each round's brief and response are kept under `scratchpad/research4/s1/rounds/book-<n>/` with SHA-256s. At most three rounds, then the orchestrator rules on each finding (§6.3 rule 4); that never writes Sol's approval.
4. **Seal.** On `APPROVE`, the orchestrator commits the two evidence files on `research-4`, then the config entry naming that commit, with `decided_on` the commit's UTC date and `ruling: gpt-6.1-sol APPROVE`.

Verification: `evidence_holds` true for the entry; the import succeeds on a throwaway test database; the round files exist with hashes; a verified bundle holds the book commit; `git status` clean of scratch. The orchestrator writes no verdict and edits no response.

Dependencies: Task 9.

Risks: the core judgement risk. Assumption values are opinion, and Sol can only test defensibility, not truth. Hindsight cannot be disproved (§6.3 rule 7) and is disclosed. `config/ledger_import.yaml` names one successor, so a later live `ledger import --thesis-successor` imports this one; nothing runs it before the live close.

### Task 11: Rehearsal and report round on `eqos_test_r4`

Goal: S1's acceptance cases that need real data pass, and the regenerated FY27_Q1 report gets a real Sol `APPROVE` with its export handed to the owner.

Files:
- Create (never committed): `scratchpad/research4/s1/rehearsal/` gate script, digests, deltas, exports, `rounds/report-<n>/`.
- Test: the gate script imports production checks, reimplementing none.

Interfaces:
- Consumes: the code commit (Task 9); the book commit (Task 10); `db backup`, `db restore`, `db migrate`, `ledger import --thesis-successor`, the operator run, `ledger check`, `submit`, `export`, `panel`.
- Produces: `record` of S1's sealed version for S2's replay check: version id, section and claim dump, book SHA-256, code commit. The reader-facing export.

Approach, from the worktree, on one faithful restore with copied snapshot, intake and locator roots, each command naming `eqos_test_r4` explicitly:
1. Capture every `version_sealed_digest` before 0046.
2. Apply 0046 and import the book; its status reads `APPROVED`.
3. Run FY27_Q1 with its config, retrospective manifest and compare run, as the earlier rehearsals did. It reruns whole on v23.
4. `ledger check`: every claim `MATCH`, `scan_section` clean. Then digests again: every prior version equal, including v29, v21, v22, v23 and thesis v13.
5. Regenerate FY26_Q3, then FY26_Q2, in that order, because a DRAFT FY26_Q2 head would refuse the FY26_Q3 run (`run_draft.py:312-313`). Each gives `NOT_ASSESSED`, no `fcst.*` or FY26 annual claim, and `thesis_impact`, `observable_falsifiers` and `risk_probe` equal their heads' under §7.5's identity replacement.
6. Gate script: real-input cases (case 1); the rendered section's sources exclude FY27_Q2 (case 5); each statement in the "Reader sees" list present.
7. `submit`, `export`. A **real Sol report round** on the export with spec §6.3 rule 3's brief; `ledger panel` records its verdict with its response bound to the export's hash. `REQUEST_CHANGES` routes per §7.6 and repeats from a fresh restore, at most three rounds per artefact.

Verification: the gate script exits 0 with each case named; `ledger check` output all `MATCH`; digest comparison empty; panel decision `APPROVE` on `eqos_test_r4`. `db check-live` refuses a test database by design, so it is not the health signal here. No gate runs beside this, and it keeps the 16:00 UTC window. A verified bundle follows the report `APPROVE`.

Dependencies: Tasks 9, 10.

Risks: **live is untouched:** every command's database is checked to be `eqos_test_r4` before it runs, and a live name stops the script. A worktree gives no protection here, since the PostgreSQL service is shared. S3's real-panel history (spec §0: code-built text is rejected too) means a rejection is likely on the first round; that is what the round is for. A rejected report writes nothing live.

### Task 12: Close

Goal: S1's closing review is done, docs are current, and the owner has the artefact.

Files:
- Modify on `research-4`: `CONTEXT.md` (Thesis entry adds `forward_view`), `docs/goals/2026-10-27-research-report-targets.md:35` (first-party balance sheet and cash flow are extracted for half-year and annual filings).
- Modify on `main`, from the shared checkout: `docs/status/dashboard.html`.
- Test: none.

Interfaces:
- Consumes: Task 11's results and export.
- Produces: the bead's record, follow-up beads under "Left ready".

Approach: a fresh Sol session with no prior context reviews everything S1 built, per step 6 of the review loop. Real findings go to a fresh Opus round and a re-review; a code change re-runs Tasks 9 and 11's affected steps from a fresh restore. Docs by Sonnet. The orchestrator commits, refreshes the dashboard after each committed task, and sends the owner the export.

Verification: gate `PASS` at the closing commit; structural gate; `git status` in both checkouts shows only intended files; a verified bundle of the closing commit and the hashed rounds are in `scratchpad/backups/research4/`. The live database is unchanged: a read-only query shows migrations still ending at 0045, the same heads and the digests captured in Task 11. `db check-live` from the shared checkout on `main` still passes; from the worktree it fails by design (C-11). The worktree stays until the live close.

Dependencies: Task 11.

Risks: reporting more than was done. The close states plainly that nothing is live, FY27_Q2 is excluded, and prospective falsification is not delivered.

## Acceptance map

Each case must be able to fail. "Fails if" names what would make it fail.

| Spec case | Where | Fails if |
|---|---|---|
| 1 Hand-computed lines | `test_forward_model.py`, round-number book | A formula or order changes; values are written in the test |
| 1 Real FY26 inputs (C-5) | Task 11 step 6 | Per-MT reproduction leaves tolerance, or the `P^c_0` definition identity breaks; if Task 0 found a stated realisation, it differs too |
| 2 Bridge, shares, negative `s_0` | `test_forward_model.py` | A term changes; shares appear on a shrinking path; a negative share refuses |
| 3 Recomputation | `test_forward_binding.py` | State does not follow an in-memory wrong value |
| 3 Tamper | `test_forward_binding.py`: off by the smallest unit; stored `123.49` against `123`; assumption differing; unknown model; `measurement_key` with `PROJECTION` | Rounded comparison returns; earlier block not `MATCH`; constraint missing |
| 3 Output shape | `test_forward_binding.py`: wrong unit, scale, horizon, class, precision; unregistered line or period; a correctly valued line under an unregistered scenario, with shared `all` assumptions; `forward.2` | A correct value passes under a wrong shape or a fabricated scenario |
| 3 Binding | `test_forward_binding.py`: equal-value endpoint; base and bull swapped; other period's operand; disclosure in another's role; another book's citation | Values copied, so only the binding can catch it |
| 3 Calendar | `test_forward_binding.py`: after the entity's setting changes, the recorded recomputation call receives the sealed month; `differing_book_import` (Task 7) and `differing_book_write` (Task 8) refuse a book whose month differs. S2 case 1 adds the numerical day-count proof | The recorded call receives the current setting; a differing book writes |
| 3 Sealed digests | `test_forward_binding.py`; Task 11 steps 1 and 4 | Any prior digest differs after 0046, import or write |
| 3 Contract replay | `test_forward_binding.py`: theses A and B, reports, a `ledger.*` claim at the span, two digests, a twin with no entry | A report takes the other's contract; a guidance claim moves |
| 3 Replay stability (analogue) | `test_forward_binding.py`; real proof S2 case 9 | A held-blocks reader requires an unheld block |
| 3 Import atomicity | `test_forward_meaning.py`, each failure class, after the valid control imports | The control fails; any version, seal or approval remains; bound head moves |
| 4 Meaning refusals | `test_forward_meaning.py`: FY25 column; coherent wrong-year pair; columns out of order; both `HEADER` entries and `columns` permuted, with otherwise coherent values; header anchors of another table; a `column` label occurring twice; p6's FY26 heading replaced by another year; `SUBJECT` of another division; conductor's cells swapped with another row's in one block and across split-label rows, with values copied; a quoted negative cell (`-25`, `(25)`) under a positive value, reaching the signed-cell check; an unsupported cell token; `PROSE` with a signed number; oil labelled conductor; KL under MT; period label; absent number; quote not at anchor; another issuer's presentation; two-number prose; other target period; `lower_bound`; `columns` on a prose id. Passing controls: one prose row; a split label; two rows in one block; a `(Note 1)` label; `Total` beside a negative `Others` cell | A row passes, a control refuses, or a row refuses with another check's fault |
| 5 Time, book binding | `test_forward_meaning.py`: 2026-10-29 presentation; `published.at` differing. `test_forward_view.py`: `applies_to`, `as_of`, `filed` differing | A later document passes; a mismatched book emits a claim |
| 5 No FY27_Q2 in sources | Task 11 step 6 | Any rendered source is a later capture |
| 5 FY26_Q2, FY26_Q3 regenerated | Task 11 step 5 | Any `fcst.*` claim, or a shared section differs |
| 6 Fail closed | `test_forward_view.py`: missing `cwip`; missing disclosure | `PROFIT` emits a number; revenue fails to render; the block is unnamed |
| 7 Book guards | `test_forward_book.py`, every row in each statement field | Any row persists anything |
| 8 Labels | `test_forward_view.py`: `INSIDE`, `NOT_COMPARABLE`, `BELOW`; `test_forward_book.py`: reference outside `COMPARABLE` | A later year is compared; an assumption is not opinion |
| 9 Rate anchors | `test_forward_view.py`: hand-computed; negative outflow positive; zero and negative denominators for each anchor, each rendering not available with no numerical claim while unaffected content still writes | A sign or formula changes; a check of `== 0` alone would pass a negative denominator |
| 10 Regenerated report | Task 11 steps 3, 4, 7 | Any claim not `MATCH`; `scan_section` raises; Sol does not `APPROVE` |
| C-1, C-7, C-9 | `test_forward_view.py`: a claim-bearing version refuses with no model call recorded; a claim-free `NOT_ASSESSED` version narrates successfully | Narrate refuses a `NOT_ASSESSED` version, accepts `fcst.` claims or calls a model first; `fcst.d.*` becomes next quarter's guidance; `NOT_DONE` denies the base case an eligible report holds |
| S3 cases 1, 2 (C-8) | `test_forward_book.py` | A bad scenario, trigger or watch block persists |

## Left ready for later slices

- **S2:** `Block` and `OUTPUTS` extend; S1's lines and `forward.1`'s earlier values do not change. `compute` adds `WORKING_CAPITAL` and `FUNDING`, `days_t` arrives, and all S2 assumptions are already sealed and rendered. Task 11's record feeds S2 case 9.
- **S3:** bear and bull paths, `scenario.*`, `trigger.*` and `ScenarioFalsifier` are sealed; `BoundThesis.forward_claims` exposes their row ids. S3 removes bear and bull from `NOT_DONE` (C-9).
- **Live close:** parity runs inside `write_run_draft`'s transaction after `check_version`, so `run_draft.py` must leave room under 800 lines. S1's digest comparison is reused. Follow-up, not delivered: the FY27_Q2 run's design must test this book's original sealed thresholds (spec §10).
- **Live-close plan obligations.** S1 runs none of this; that plan must, in this order:
  1. Merge advancing `main` into `research-4`, with no history rewrite, and resolve conflicts. Precedent: `40b14c06`.
  2. Freeze the integrated candidate, record its commit, and verify it with the gate. Copy back any retained file added under `data/`, by the find comparison with sides swapped.
  3. Rehearse on that candidate from a fresh restore, with the parity record, and get the real Sol approval on it. **Any later production-code change invalidates the affected rehearsal and parity evidence**, so a `main` that moves in production code returns to step 1.
  4. Choose a window. The scheduled intake is an app-owned schedule at 16:00 UTC and stays unchanged. The window starts after that day's run is verified finished, and its measured rehearsal duration must end well before the next firing. Both are verified at the time, from the job's record and the schedule's next-run time. If it cannot fit, wait.
  5. In the window, take a database backup, then merge `research-4` into `main` with an ordinary merge, no squash or rebase (precedent: `508d1107`), then the spec's live sequence: 0046, thesis import, `ledger run … --parity`, real Sol round, digest comparison, `check-live`.
  6. State in advance what `main` and live hold if a step fails inside the window, so the next firing never runs code against a mismatched schema.
  7. Push `main`. Verify the exact configured `evidence_commit` is reachable from the pushed `main` and still passes `evidence_holds`.
  8. Verify the shared checkout's branch and import location, and observe the next scheduled run on the deployed `main`. Then remove the worktree, after a final verified bundle.

## Self-review

- **Spec coverage:** S1's Work list and all ten cases map to tasks. §7.4's proofs map; the "same comparison at the live close" is left to that slice.
- **Placeholders:** none. Task 0 supplies the disclosure list's contents by design.
- **Names:** Task 3 to 8 Produces match Consumes; `FiledPin` is Task 4's, used by Task 8's `AnnualBase`.
- **Order:** each task's checkpoint needs only earlier tasks. Task 4 stops at mapping; Task 5 is plumbing; Task 6 adds version-bound resolution; Task 7 completes the pre-approval import, whose valid control precedes its refusals.
- **Gaps named:** invariants and worktree (Task 1), migration (Task 5), branch, cutover and live compatibility (C-11, Left ready), backup (Backup), docs and dashboard (Task 12), config (Task 10), fix rounds (Tasks 9, 12).
- **Not verified:** the panel role's read of the fiscal setting (Task 7); that only the stage4 test reads `data/raw/onboarding`, which rests on the learnings entry and is not opened to check; whether an existing test asserts a section count (Task 8); p4's rows below block 13 and whether any page states a realisation (Task 0). Sizes are estimates.
