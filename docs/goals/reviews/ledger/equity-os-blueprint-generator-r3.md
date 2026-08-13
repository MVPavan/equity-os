# Equity-OS initial-ledger bootstrap generator r3 review

## Review binding

- Review base: `6d6d8361454fadfde990ae8d65ef3f78a3841b19`.
- Base generator blob (Git SHA-1): `c4b5a5a4e78d249700b790a78bd3ebf58f34adb2`.
- Reviewed worktree generator blob (Git SHA-1): `25142d6b80d63b82289cbd921789dbd7421c1f15`.
- Reviewed generator SHA-256: `54f8bc1f23c304bef41218bd249b8310f3ca15026daa3ee685b241279d38bfe7`.
- Binary patch SHA-256: `2c4b5dc297a6423e2ff5d343c61f850900804022aaa3d7c647c77ed935ec2fa4`, from `git diff --no-ext-diff --binary 6d6d8361454fadfde990ae8d65ef3f78a3841b19 -- scripts/equity_os_blueprint/generate_initial_ledger.py | sha256sum`.
- Patch size: 382 insertions, 72 deletions in `scripts/equity_os_blueprint/generate_initial_ledger.py`.
- Active goal SHA-256: `dabad7bfe3d2765a5ac9687376029d8587b4b2ac95bc03494155a974e5ddc67f`.
- Pinned register SHA-256: `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`.
- Pinned disposition SHA-256: `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738`.
- Current structural-validator SHA-256: `f880f507d82ac20145ac73d422a01bae38abf88a23e1ed0f240c62ebdd9554e9`.
- Current preimplementation-validator SHA-256: `ed73ffe1bd0388ed55e6d2d368058599aaa5b346f6c583fb76086a636cd5b39c`.
- Canonical live ledger and human-review SHA-256 values remained `51091042dae87d2f41fbbf02d77ab1619c6a1008a022baec4233c44a0e295e13` and `54c1e183def8e0b1b91504effbf20c233b3d1352fd65d4910e89c2b913ee5702` during this read-only review.

## Blocking defects

1. **Important — Paired-publication rollback can still delete a pre-existing or unowned replacement file.** `scripts/equity_os_blueprint/generate_initial_ledger.py:870-882` creates a hard link and then obtains ownership metadata by resolving the destination pathname again. On rollback, `scripts/equity_os_blueprint/generate_initial_ledger.py:885-898` performs `lstat`, `read_bytes`, and `unlink` as three separate pathname operations, invoked after a later publication error by `scripts/equity_os_blueprint/generate_initial_ledger.py:901-913`. A concurrent process can rename or replace the first published destination after either ownership check and before `unlink`; `unlink()` then resolves the pathname afresh and may delete the replacement. The inode and content checks reduce accidental deletion but do not make check-and-unlink atomic. This directly violates the requirement that cleanup never delete a pre-existing/unowned output. The safety currently depends on an unstated stable-parent-directory/no-concurrent-namespace-mutation assumption. Preserve an already-published partial output and report it rather than attempting unsafe rollback, or use a publication design whose ownership and deletion are atomic under an explicitly enforced filesystem model.

2. **Important — The disposition/register semantic crosswalk remains padded and dropped to mimic spec applicability, so r1 finding 5 is not fully fixed.** The serialized mappings at `scripts/equity_os_blueprint/generate_initial_ledger.py:97-108` disagree with the instructed exact semantic manifest at `docs/goals/reviews/ledger/equity-os-blueprint-ledger-remediation-design-r2.md:115-148`: `G-4` omits `B-02` and `B-13`; `M-9` adds unrelated `C-02`; `T-4` adds unrelated `A-05`; `R-1` adds dependency `D-01`; and `6.8` omits `B-02`. The source supports the missing/direct distinctions: `G-4` requires three later assisted updates and reviewer-bias controls at `docs/blueprint/funda-third-order-review-disposition-report.md:88-100` with `B-02`/`B-13` defined at `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md:52` and `:63`; `M-9` is the golden-set/failure-taxonomy control at `funda-third-order-review-disposition-report.md:252-262`, while `C-02` is only the document registry at `funda-blueprint-implementation-decision-register-v2.md:73`; `T-4` concerns `A-01` plus the external/distribution and execution gates at `funda-third-order-review-disposition-report.md:299-304`, not the `A-05` data-rights row at `funda-blueprint-implementation-decision-register-v2.md:35`; `R-1` retains the `D-02` benchmark at `funda-third-order-review-disposition-report.md:309-323`; and `6.8` explicitly depends on the three `B-02` assisted updates at `funda-third-order-review-disposition-report.md:383-394`. The check at `generate_initial_ledger.py:220-239` validates rows against the same generator-authored constants and hard-codes only three examples, so it cannot detect these five source-manifest errors before `generate_initial_ledger.py:575-580` serializes them. These errors are outside the three authority blockers the current review permits to remain unresolved, and the generated disclosure does not name them.

## Disclosed authority blockers, not generator defects in this bounded mode

- `PG-1-11` remains a dormant related-scope row because the approved schema has no active-negative-control form: `scripts/equity_os_blueprint/generate_initial_ledger.py:73-79` and `:494-520`. The source still requires the active Phase-1 exclusion at `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md:148-160`.
- Nine compound summaries remain canonical authority rows and the candidate remains 178 canonical plus 35 aliases at `scripts/equity_os_blueprint/generate_initial_ledger.py:589-612`, `:628-660`, and `:817-827`; the approved schema still permits only one direct alias target.
- Phase-2 predicates still consume conclusion booleans at `scripts/equity_os_blueprint/generate_initial_ledger.py:282-300`; approved threshold-to-measurement predicate authority does not yet exist.
- The paired human-review candidate accurately says these three items require approved schema reconciliation and that neither generated artifact is canonical or migration authority at `scripts/equity_os_blueprint/generate_initial_ledger.py:934-945`. The generator itself refuses canonical targets at `:842-850` and requires both alternate targets at `:919-927`.

These three items may remain unresolved only for a non-canonical bootstrap candidate. They continue to block authority completeness, preimplementation acceptance, and any migration of activated state.

## Re-review and quality checks

- **Timestamps:** invocation time is captured once at `scripts/equity_os_blueprint/generate_initial_ledger.py:188-197` and used for evidence and bootstrap transitions at `:251-262` and `:435-449`; the separate pinned-source cutoff is used only for the authoritative rejection at `:744-757`. A fixed `2026-08-13T01:06:48Z` in-memory fixture produced that time for all 325 evidence references and all bootstrap transitions, while the rejection retained `2026-08-13T01:06:47Z`.
- **Canonical/existing-target refusal:** canonical, existing regular-file, and existing symlink probes were refused by `scripts/equity_os_blueprint/generate_initial_ledger.py:842-850`; two lexically different arguments resolved to the same path and are rejected by the equality guard at `:924-927`. Exclusive `os.link` publication at `:870-875` cannot replace an existing final entry. Finding 1 remains the rollback exception.
- **Temporary files and ordinary errors:** each temporary file is created in the destination directory, file-flushed/fsynced, removed on preparation failure, and removed in the outer `finally` at `scripts/equity_os_blueprint/generate_initial_ledger.py:853-867` and `:901-916`. No filesystem-writing fault injection was run because this review was restricted to focused read-only checks. The static error path is sound absent concurrent namespace mutation; Finding 1 covers the unsafe concurrency case.
- **213-row invariant:** fixed-time in-memory generation produced 213 unique rows, 178 canonical and 35 aliases, with kind counts `60/35/13/8/32/13/11/6/35`; 183 approvals; 395 evidence requirements; 25 command requirements; and 325/325 unique evidence references. Its deterministic fixture ledger SHA-256 was `667362af364ebbff3efd9c35e762b37b8d474d0996d4e2da62e54e8911209fbb`. The current structural validator passed against paired anonymous memfd artifacts; its count-only checks at `scripts/equity_os_blueprint/validate_ledger_structural.py:279-289` do not clear Finding 2.
- **Other r1/r2 fixed findings:** sequence rows remain null-owned program-wide active controls at `scripts/equity_os_blueprint/generate_initial_ledger.py:613-621` and `:733-741`; null-owned phase gates cannot receive delegated artifact approvals at `:709-730`; `DEF-12` remains null-owned at `:528-550`; command-proof inventory and the corrected scale-workflow disposition are enforced at `:176-180` and `:773-791`. No regression was found in the remaining previously fixed approval, evidence, deferral, scale-trigger, or `PG-2-04` items.

## Commands and results

- `git diff --check 6d6d8361454fadfde990ae8d65ef3f78a3841b19 -- scripts/equity_os_blueprint/generate_initial_ledger.py` — exit 0.
- In-memory `compile(...)` of `scripts/equity_os_blueprint/generate_initial_ledger.py` — PASS.
- Fixed-time in-memory generation plus current structural validator redirected only to paired anonymous memfd artifacts — PASS with the inventory and fixture hash above.
- `python3 -B scripts/equity_os_blueprint/extract_goal_validators.py --check` — exit 0; the checked-in structural and preimplementation validators are byte-synchronized with the active goal under `scripts/equity_os_blueprint/extract_goal_validators.py:31-60`.
- Read-only resolver probes — canonical ledger, existing regular file, and existing symlink all refused; same resolved path detected by the main equality guard at `scripts/equity_os_blueprint/generate_initial_ledger.py:924-927`.
- Exact crosswalk comparison — five mismatches listed in Finding 2.
- Scope check — the reviewed implementation diff changes only `scripts/equity_os_blueprint/generate_initial_ledger.py`; this reviewer wrote only this r3 report. Pre-existing `.beads`, scratchpad, generator, and other review-file changes were neither modified nor claimed.

Verdict: ISSUES_FOUND
