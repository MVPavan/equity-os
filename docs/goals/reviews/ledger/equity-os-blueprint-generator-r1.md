ISSUES_FOUND

## Reviewed diff

- HEAD: `6d6d8361454fadfde990ae8d65ef3f78a3841b19`
- Base blob: `c4b5a5a4e78d249700b790a78bd3ebf58f34adb2`
- Worktree blob: `bbe7e0e98833dbc43be950083c398962b5ead815`
- Patch SHA-256: `6e20977edb15121ff8b7aae7313850173bb04337dcc29c603f1458a5242cbc2a`
- Diff: 193 insertions, 59 deletions
- Active goal SHA-256: `dabad7bfe3d2765a5ac9687376029d8587b4b2ac95bc03494155a974e5ddc67f`
- Authority hashes matched their pinned values exactly.

## Commands and results

- `git diff --check -- scripts/equity_os_blueprint/generate_initial_ledger.py` — exit 0.
- Python `compile(...)` of the generator — exit 0.
- Safe memfd generation invoking both `--ledger-path` and `--human-review-path` — exit 0; no repository writes.
- Generated ledger SHA-256: `1c86cf5858ce31b049829a9f0c17e495eedfbffb5a6222da2eee3dfcd3b3b5a7`.
- Generated inventory: 213 unique rows; 178 canonical, 35 aliases. Kinds: 60 register, 35 phase-gate, 13 deferral, 8 trigger, 32 disposition, 13 authority, 11 sequence, 6 document-strategy.
- Generated proof inventory: 189 unique approvals; 395 unique required-evidence items; 25 `COMMAND`; 325/325 unique evidence references.
- Active structural validator redirected in memory only to the temporary artifacts — exit 1 at `validate_ledger_structural.py:1343`.
- Diagnostic run relaxing only that sequence-rule assertion — exit 0. This is diagnostic, not valid acceptance.
- Live structural validator — exit 1 at `validate_ledger_structural.py:183`, stale live evidence.
- `extract_goal_validators.py --check` — exit 0.
- Final status remained: pre-existing `.beads/issues.jsonl` modification plus the reviewed generator diff; reviewer changed neither.

## Findings

1. **Critical — The generator remains an activated-state rewriter, not a legal migration.**
   `scripts/equity_os_blueprint/generate_initial_ledger.py:21`, `:217`, `:399`, `:715`, `:758`, `:762` rebuild and backdate activation snapshots, default to the canonical live paths, and replace the human-review payload with an empty document. The current live state has 454 history entries, 23 findings/blocked rows, 23 human links, and 3 open human-review entries; generation reduces this to 377 histories and zero findings, links, blockers, or entries. This violates the immutable/reconciliation contract at `docs/goals/equity-os-blueprint-completion.md:559` and `:622`.
   **Required fix:** make bootstrap creation refuse existing/canonical activated artifacts and require both alternate paths. Implement any live update as a separate authorized migration that preserves history and appends legal reconciliation transitions with truthful current timestamps. No such migration may run without the authority noted below.

2. **Important — Ten sequence clauses violate the goal’s closed scope rule and fail structural validation.**
   `scripts/equity_os_blueprint/generate_initial_ledger.py:569-578` assigns `RELATED_REGISTER_SCOPE`; the goal requires every `sequence_clause` to use `PROGRAM_WIDE_ACTIVE_CONTROL` at `docs/goals/equity-os-blueprint-completion.md:227-235`. The official validator rejects the temporary ledger at `scripts/equity_os_blueprint/validate_ledger_structural.py:1343`.
   **Required fix:** retain program-wide scope and null primary ownership. If explicit multi-spec ownership is required, amend the goal/schema first rather than overloading `related_register_ids`.

3. **Important — `PG-1-11` is changed from an active negative control into dormant scope.**
   `scripts/equity_os_blueprint/generate_initial_ledger.py:71` truthfully removes unrelated `C-11`, but all remaining related rows are Deferred, so `:463-469` derives `CONDITIONAL_UNACTIVATED`. The authoritative exclusion must remain enforced during Phase 1 at `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md:160`.
   **Required fix:** add an approved derivation form for active negative controls related to dormant capabilities. Do not restore an unrelated active register row merely to force `REQUIRED_NOW`.

4. **Important — Nine defective aliases were converted into independent program-wide obligations.**
   `scripts/equity_os_blueprint/generate_initial_ledger.py:552-568` converts executive verdicts, final summaries, accepted-change recaps, and implementation posture into `authority_clause` rows; `:606-618` removes their aliases. The goal explicitly requires repeated executive summaries and accepted-change recaps to remain aliases at `docs/goals/equity-os-blueprint-completion.md:153-164`. The resulting 178-canonical/35-alias partition is semantically wrong despite unique spans and correct digests.
   **Required fix:** preserve these as aliases. Because several passages summarize multiple canonical targets while the current schema permits only one target, reconcile the goal and validator with an explicit compound-alias representation before regenerating. The evidence-derived target partition is 169 canonical and 44 aliases, subject to that authorized schema repair.

5. **Important — Disposition/spec validation is satisfied by altering register semantics.**
   `scripts/equity_os_blueprint/generate_initial_ledger.py:87-99` and `:702-704` test only the set of owning specs. This admits incorrect register relations: `G-1` drops `C-16`, `T-4` drops the directly controlling `E-08`, and `6.4` introduces unrelated promotion row `D-03`.
   **Required fix:** represent the disposition-to-spec crosswalk independently from semantic `related_register_ids`; validate both exact sets. Restore all authority-supported register links without inventing links solely to reach a spec owner.

6. **Important — Conditional phase-gate predicates still contain copied answers rather than measurements.**
   `scripts/equity_os_blueprint/generate_initial_ledger.py:238-256` replaces generic readiness fields with booleans such as `current_scale_outcomes_improved` and `operational_burden_acceptable`. These remain conclusions, not stable measurements as required by `docs/goals/equity-os-blueprint-completion.md:265-268`. The default path also leaves `PG-1-11` on `activation_ready`.
   **Required fix:** define observable inputs, thresholds, test-result identities, and comparisons; derive the gate result from them instead of accepting a JSON-authored verdict.

7. **Important — Six phase gates receive unsupported delegated artifact approvals.**
   `scripts/equity_os_blueprint/generate_initial_ledger.py:471-474` adds `DELEGATED_ARTIFACT_APPROVAL` and “specification bytes” review evidence to phase-gate rows with `primary_spec=null` and no owned spec/roadmap/JIT-plan artifact. Delegation is limited to those artifact classes at `docs/goals/equity-os-blueprint-completion.md:826-836`.
   **Required fix:** retain the newly added source-required human approvals, but use ordinary component review evidence for the gate. Add delegated approval only when an exact eligible artifact and its current evidence are identified.

## r0 finding disposition

| r0 finding | Disposition |
|---|---|
| Inventory C1 — deferral polarity | ADDRESSED |
| Inventory C2 — scale-trigger semantics | ADDRESSED |
| Inventory I1 — phase-gate maps | PARTIAL: `PG-2-04` fixed; `PG-1-11` now dormant |
| Inventory I2 — aliases and missing line 9 | NOT ADDRESSED: line 9 added, nine aliases misclassified |
| Inventory I3 — validator completeness | NOT ADDRESSED |
| Approval C1 — stale evidence | TEMPORARY OUTPUT ADDRESSED; LIVE BLOCKED |
| Approval C2 — predicate authority omissions | ADDRESSED |
| Approval I1 — four register approval omissions | ADDRESSED |
| Approval I2 — nine gate/disposition approvals | ADDRESSED; new unsupported delegated approvals remain |
| Approval M1 — D-05 scope collision | ADDRESSED |
| Evidence C1 — stale content binding | TEMPORARY OUTPUT ADDRESSED; LIVE BLOCKED |
| Evidence C2 — missing command proof | ADDRESSED: 25 command requirements |
| Evidence C3 — positive deferral proof | ADDRESSED |
| Evidence I1 — disposition review proof | ADDRESSED |
| Evidence I2 — approval/review gate classification | PARTIAL: typed authority proof added; delegated artifact proof is invalid |
| Evidence I3 — scale-trigger proof | ADDRESSED |
| Scope I1 — stale evidence | TEMPORARY OUTPUT ADDRESSED; LIVE BLOCKED |
| Scope I2 — `PG-1-11` | NOT ADDRESSED |
| Scope I3 — `PG-2-04` | ADDRESSED |
| Scope I4 — Phase 2 predicates | PARTIAL |
| Scope I5 — disposition/spec edges | PARTIAL: owner sets match, register semantics do not |
| Scope I6 — multi-spec sequences | NOT ADDRESSED; now validator-invalid |
| Scope I7 — `DEF-12` ownership | ADDRESSED |

## Residual authority and validator notes

- Live ledger SHA-256 is `51091042dae87d2f41fbbf02d77ab1619c6a1008a022baec4233c44a0e295e13`; it remains the activated canonical state.
- Applying corrected inventory would change immutable IDs, aliases, ownership/scope, and snapshot state. The goal requires current human `RECONCILE_AUTHORITY` authorization and append-only reconciliation evidence. No such authority currently exists. This is an operational blocker separate from the generator defects above.
- The generated validator has no alternate ledger/human-review path interface, so safe temporary validation required in-memory path substitution. Add path injection to the goal-generated validator contract.
- The validator still checks exact counts only for the five numeric inventory kinds and cannot independently prove exhaustive authorities, aliases, semantic alias targets, or exact disposition/register/spec crosswalks.