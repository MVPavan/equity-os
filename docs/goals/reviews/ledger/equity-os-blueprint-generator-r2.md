ISSUES_FOUND

## Reviewed generator

- HEAD: `6d6d8361454fadfde990ae8d65ef3f78a3841b19`
- Base blob: `c4b5a5a4e78d249700b790a78bd3ebf58f34adb2`
- Worktree blob: `b3513537269819361a5aefe292aa9a249d7e2ded`
- Patch SHA-256: `4c88c8f5327a4fa2ba3732f3cd4dbeeae7d4127164ea58209163fbbc93f6cb08`
- Patch command: `git diff --no-ext-diff --binary -- scripts/equity_os_blueprint/generate_initial_ledger.py | sha256sum`
- Diff: 279 insertions, 61 deletions
- Goal SHA-256: `dabad7bfe3d2765a5ac9687376029d8587b4b2ac95bc03494155a974e5ddc67f`
- Both pinned authority hashes match the goal.

## Commands and results

| Check | Result |
|---|---|
| `git diff --check -- scripts/equity_os_blueprint/generate_initial_ledger.py` | Exit 0 |
| In-memory Python `compile(...)` | PASS |
| Missing either output argument | `SystemExit(2)`; zero writes |
| Canonical, existing, or identical targets | Refused; zero writes in all five probes |
| Explicit alternate-path generation with intercepted writer | Exit 0; no filesystem output |
| Generated ledger | SHA-256 `0834ec235da5384ea4f6c93481a9f165e22ff5c9aa26cebab548f66d4b4b320b`; 213 unique rows, 178 canonical, 35 aliases |
| Generated proof inventory | 183 approvals, 395 evidence requirements, 25 command requirements, 325/325 unique evidence references |
| Active structural validator with memfd path injection | Exit 0 |
| `extract_goal_validators.py --check` | Exit 0 |
| Final worktree | Only pre-existing `.beads/issues.jsonl`, generator diff, and untracked r1 report shown; live ledger/human-review files untouched |

## Per-finding verdict

| # | Severity | Verdict | Exact evidence |
|---:|---|---|---|
| 1 | Critical | **FIXED** | Both CLI paths are required at `generate_initial_ledger.py:833` and `:834`. Canonical/existing targets are rejected at `:814-822`; both targets are resolved before generation or writing at `:836-840`; exclusive creation occurs at `:825-828`. All failure probes produced zero write calls. |
| 2 | Important | **FIXED** | Sequence rows use `PROGRAM_WIDE_ACTIVE_CONTROL` at `generate_initial_ledger.py:600-604`; the explicit closed-schema assertion requires null ownership, empty related registers, and `REQUIRED_NOW` at `:716-724`. All 11 generated rows passed the active validator. |
| 3 | Important | **OPEN — schema-authority blocker** | `PG-1-11` now truthfully relates only to D-02, D-05, E-03, E-05, and E-09 at `generate_initial_ledger.py:71`, but `:490-496` consequently derives it dormant. The source requires an active Phase-1 exclusion at `funda-blueprint-implementation-decision-register-v2.md:160`; the goal’s closed rules at `equity-os-blueprint-completion.md:227-245` provide no active-negative-control representation over dormant capabilities. |
| 4 | Important | **OPEN — schema-authority blocker** | Nine multi-target summaries remain independent `authority_clause` rows at `generate_initial_ledger.py:579-595` and are skipped as aliases at `:630-638`. The goal requires such summaries to remain aliases at `equity-os-blueprint-completion.md:153-164`, but permits only one direct canonical target. A compound-alias schema must be approved first. |
| 5 | Important | **FIXED** | Spec ownership and semantic registers are separate constants at `generate_initial_ledger.py:78-104`, independently asserted at `:203-222`, and independently applied at `:560-562`. G-1 is A-04/C-09/C-08/C-16 (`:211`), T-4 is A-01/A-05/E-08/E-09 (`:212`), and 6.4 is D-02/D-05 (`:213`). These match the disposition semantics at `funda-third-order-review-disposition-report.md:47-59`, `:299-304`, and `:367-369`, plus the controlling register rows at `funda-blueprint-implementation-decision-register-v2.md:31`, `:34-35`, `:79-80`, `:87`, `:98`, `:101`, and `:116-117`. |
| 6 | Important | **OPEN — schema-authority blocker** | Phase-2 predicates still consume copied conclusion booleans such as `current_scale_outcomes_improved` and `operational_burden_acceptable` at `generate_initial_ledger.py:265-279`; `PG-1-11` still falls back to `activation_ready` at `:279`. This violates the stable-measurement requirement at `equity-os-blueprint-completion.md:267-268`. Observable inputs, thresholds, test identities, and comparisons require an approved schema amendment. |
| 7 | Important | **FIXED** | Six source-required nondelegated approvals are declared at `generate_initial_ledger.py:156-163` and attached with ordinary component-review evidence at `:498-503`. Delegated approval is added only to rows with an owned spec at `:647-656`; the phase-gate assertion rejects delegated approval/spec-review evidence at `:692-713`. Generated result: six correctly typed human approvals and zero delegated artifact approvals across all 35 phase gates. |

## r0 regression safety

PASS: deferral polarity, scale-trigger enforcement, `PG-2-04` D-01/D-03 scope, predicate-related human authorities, register/gate/disposition approval omissions, distinct D-05 activation/adoption scopes, 25 command requirements, disposition review proof, line-9 alias coverage, and null ownership for `DEF-12`.

The remaining r0 failures correspond to open r1 findings 3, 4, and 6. The active validator passes the generated candidate but still cannot independently prove exhaustive authority/alias semantics or the exact disposition/spec/register crosswalk; its hard-coded output paths remain at `validate_ledger_structural.py:15` and `:705`.

## Authority-gated remainder

No code-only generator fix may resolve findings 3, 4, or 6 under the current closed goal schema. The goal and generated validator require explicit amendment and approval first.

Applying any corrected inventory to the activated canonical ledger separately requires an active human `RECONCILE_AUTHORITY` resolution, explicit user approval, and append-only `AUTHORITY_RECONCILIATION` transitions under `equity-os-blueprint-completion.md:120-126` and `:622-634`. No such authority exists: `equity-os-blueprint-human-review-needed.md:237` records an empty resolutions list.

The canonical ledger remains SHA-256 `51091042dae87d2f41fbbf02d77ab1619c6a1008a022baec4233c44a0e295e13`; it must not be replaced by bootstrap generation.