Verdict: APPROVE

# D9 phase-end review record

Reviewer: GPT-6.1 Sol (reasoning effort high), fresh session per round. Approver of record per
`.claude/rules/core/04-agent-stack.md`. Date: 2026-10-18. Plan: [D9](../plans/D9.md).

| Round | Basis | Verdict | Findings | Fixed in |
|---|---|---|---|---|
| Phase review r1 | D9 Tasks 1–9 (`8dd1b53`..`b72103a`) | REVISE | F1–F18 | `38077cb` |
| Re-review r2 | `38077cb` | REVISE | F1, F9, F10 partial → G1–G5 | `65bb74d` |
| Re-review r3 | `65bb74d` | REVISE | G1 partial → H1–H2 | `8b41f29` (orchestrator rulings, loop at 3 rounds) |
| Fresh critical review | whole phase at `8b41f29` | REVISE | K1–K8 (5 P1, 3 P2) | `3859728` |
| Re-review | `3859728` | REVISE | K3 partial, two regressions → L1–L3 | `3183817` |
| Re-review 2 | `3183817` | **APPROVE** | none; K1–K8 and L1–L3 fixed | — |

## Orchestrator rulings carried by the approval

- Accepted: unknown non-vendor surfaces are COVERED; queue dispositions stay writable on
  licence-ended sources; seeded-expiry tests; a recovered purge recomputes the eligibility reason
  (vendor WINDOW may report as CATALOG_CEILING); remaining test-to-test imports; store-only byte
  readers outside D9's files rely on the licence-marker check; 0031's RESTORED admission after a
  cancelled intent has no purge-run predicate.
- Parked: the store writer's 5 s lock timeout while a purge holds the store lock (publishers fail
  loudly on long purges).
- Documented exception (H1): every `db restore` names `--live-snapshot-root` or `--unwitnessed`;
  a journal rolled back together with its live witness, or an unwitnessed restore, cannot be
  detected.
- File map caps raised by recorded exceptions in the plan; new modules `pg/restore_check.py`,
  `retention/purge_first.py`; migrations 0031, 0032 (0032's sequence grant is unused after L2).

## Verification at approval

`ruff format --check`, `ruff check`, `mypy --strict src` clean. Full suite at `3183817`:
4102 passed, 8 skipped, 2 failed — both the WSL wall-clock backstep in `test_pipeline_e2e`
("derivation clock moved backwards", `api/source_admission.py`), non-D9, reproduces in isolation
about 2 runs in 5, tracked `eqos-0bp`. The ledger Stage 5 e2e (D9 exit) passes.

Round reports: `scratchpad/execution/d9/` (`phase-r1-sol.md`, `phase-r2-sol.md`,
`phase-r3-sol.md`, `phase-final-sol.md`, `final-rereview-sol.md`), not committed.
