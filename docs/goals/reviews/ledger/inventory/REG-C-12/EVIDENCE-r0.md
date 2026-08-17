# Inventory review — REG-C-12 — EVIDENCE — r0

**Verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| Component ID | `REG-C-12` |
| Review type | `EVIDENCE` |
| Round | `r0` |
| Reviewer | Reviewer role (CONTEXT.md "Agent roles (harness-wide)"), Claude Code session `8958a695-f635-4f4e-8747-5433095fbc1a` |
| Role | `REVIEWER` |
| Role binding path | `CONTEXT.md` |
| Role binding SHA-256 at review time | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| Model actually invoked | `claude-opus-5` |
| Effort actually invoked | `high` |
| Review UTC | `2026-08-16T13:45:24Z` |
| Batch | 17 (`register_row`, owning specs S15–S18) per recording design r2 §5.2 |

## Input hashes read at review time

| Input | Path | SHA-256 |
|---|---|---|
| Active goal | `docs/goals/equity-os-blueprint-completion.md` | `f15f7ab5a4e425dec3877ab7f1f7594687979060e4dbcd49390a8a8d5fedb85f` |
| Canonical ledger | `docs/goals/equity-os-blueprint-component-ledger.jsonl` | `de236d7e8dcf02e307ec58797f5722ae2f85d1d8cdba57d4ecc07df5383c9c97` |
| Pinned decision register v2 | `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` | `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164` |
| Third-order disposition report | `docs/blueprint/funda-third-order-review-disposition-report.md` | `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738` |
| Structural validator | `scripts/equity_os_blueprint/validate_ledger_structural.py` | `731d0d8b208b577967c92e3992e7ec1a4333cdecbf89f6951c32d2ec469436f9` |
| Preimplementation validator | `scripts/equity_os_blueprint/validate_ledger_preimplementation.py` | `f7a225a1f99cb85c92cde3094505a92a746552280eb45dae0253a71ab9048013` |
| Human-review artifact | `docs/goals/equity-os-blueprint-human-review-needed.md` | `094fcdfab74a3f4c6fdb82b1520fc4d13b636ac0e9ed10194e5d607aed2ce9af` |
| Role binding | `CONTEXT.md` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |

Fresh at these bytes: `extract_goal_validators.py --check` exit `0`;
`validate_ledger_structural.py --repo-root .` exit `0`.

## Applicability

`REG-C-12.kind == "register_row"`; `scope_derivation.semantic_review` is `null`
(verified on the row; goal L208-211). `EVIDENCE` and `APPROVAL` only; no
`SCOPE` artifact.

## Live source occurrence (pinned authority)

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md:83`,
section **C. Phase 1 — Evidence-grounded MVP**, register ID `C-12`, status
`Open`, priority `High`:

> | C-12 | High | Set Phase 1 analyst-economics gate | Pre-agreed improvement is evaluated against per-company or matched-quarter baselines; workload-normalized metrics and total report time are reported; remaining confounds are disclosed | A-13, B-04 | Open |

Recomputed `UTF8_LINE_SPAN` digest of line 83:
`892bf688c0376013d3d9dc95e7a85e826874fa9c52757dae72b4a25faaa42e09` — equals
`text_digest` and `EV-REG-C-12-SOURCE.content_sha256`. `required_acceptance_text`
is byte-identical to the acceptance cell.

## Reviewed inventory, exactly as read

`required_evidence` (3 items):

| `evidence_id` | `evidence_type` | `proof_mode` | `status` | `approval_ids` |
|---|---|---|---|---|
| `REQ-REG-C-12-ACCEPTANCE` | `ARTIFACT` | `CONTENT_HASH` | `UNRESOLVED` | `[]` |
| `REQ-REG-C-12-SPEC-REVIEW` | `REVIEW` | `CONTENT_HASH` | `UNRESOLVED` | `[]` |
| `REQ-REG-C-12-ANALYST_ACCEPTANCE` | `ANALYST` | `TYPED_APPROVAL` | `UNRESOLVED` | `["APR-REG-C-12-02"]` |

- `…-ACCEPTANCE.description` = "Current proof satisfying: Pre-agreed improvement
  is evaluated against per-company or matched-quarter baselines;
  workload-normalized metrics and total report time are reported; remaining
  confounds are disclosed".
- `…-SPEC-REVIEW` scope = "C-12 under S18: Set Phase 1 analyst-economics gate".
- `…-ANALYST_ACCEPTANCE.description` = "Current ANALYST_ACCEPTANCE evidence from
  Responsible analyst".

`evidence_refs` (2): `EV-REG-C-12-SOURCE` (`UTF8_LINE_SPAN`, register v2:83,
`2026-08-13T02:49:11Z`) and `EV-REG-C-12-SPEC-DRAFT` (`FILE_BYTES`,
`docs/specs/equity-os-s18-universe-review-economics-throughput.md`,
`6b59d6ef082ccca047ec119bc60331894ab1b752fd50e810634da317b0a78631`,
`2026-08-15T07:13:28Z`). Both recomputed: current.

`verification_command` = `{"mode": "UNRESOLVED", "commands": [],
"not_applicable_review": null}`.

## Reasoning

1. **Clause decomposition — three obligations.** (a) A **pre-agreed**
   improvement threshold, evaluated against per-company or matched-quarter
   baselines; (b) workload-normalized metrics and total report time are
   reported; (c) remaining confounds are disclosed. All three are carried
   verbatim in `REQ-REG-C-12-ACCEPTANCE.description`.

2. **"Pre-agreed" is the conjunct that must not collapse into the artifact.**
   A threshold the program sets after seeing the results is not a gate. The
   agreement is enumerated as `REQ-REG-C-12-ANALYST_ACCEPTANCE`,
   `ANALYST`/`TYPED_APPROVAL`, naming the component-local requirement
   `APR-REG-C-12-02` (verified in this row's `required_approvals`) — the typed
   approval/human-review path the goal mandates for analyst evidence
   (L487-490), with the linkage rule at L484-487 satisfied. Had this been left
   as a self-authored `ARTIFACT` item, the "pre-agreed" property would have
   been unprovable.

3. **Conjuncts (b) and (c) are reporting and disclosure obligations.** Their
   proof is the economics report itself — the normalized metrics, the total
   report time, and an explicit confounds section — bound by content hash.
   `ARTIFACT`/`CONTENT_HASH` is correct.

4. **Is executable proof demanded?** No. The clause's verbs are "evaluated",
   "reported", "disclosed" — analytical and documentary acts, not machine
   behaviour. The measurement *instrumentation* that produces the numbers is
   `B-04`, one of C-12's two dependencies, and neither row is a member of the
   goal's closed `EXPECTED_COMMAND_PROOF_COMPONENTS` set (goal L3989-3996;
   validator `:2635`, asserted `:2649`). My reading agrees with the pin.

5. **Disposition cross-check — unusually load-bearing here.** `disposition_refs`
   are `G-2`, `G-3`, `G-4`, `M-8`, `6.1`, and three of them are the direct
   source of this clause's wording: G-3 (report L75-86) requires per-company or
   matched-quarter baselines and normalized operational measures with total
   report time retained "but not treated as a portable causal measure by
   itself"; G-4 (L88-100) requires the practice-effect confound to be preserved
   in the experiment log when it cannot be removed — the origin of "remaining
   confounds are disclosed"; G-2 (L61-73) forbids significance claims from the
   three-report pilot; §6.1 (L355-357) repeats the clustering caveat. Because
   the register cell already encodes all three requirements, the disposition
   adds no unenumerated proof demand to this row. Each is additionally ledgered
   in its own right — `DISP-G-2`, `DISP-G-3`, `DISP-G-4`, `DISP-M-8`,
   `DISP-6-1`, each with its own `ACCEPTANCE` item (verified) — and register v2's
   Authority rule (L23) governs precedence.

6. **Gate cross-check.** `gate_refs` = `["PG-1-08"]` — "analyst effort improves
   against matched or per-company baselines by the agreed threshold, with
   confounds disclosed", `related_register_ids = ["B-04","C-12"]`. I read it:
   one `ARTIFACT`/`CONTENT_HASH` item and no approvals. The gate restates this
   row's obligation at gate level and carries the same proof shape; the
   "agreed threshold" authority is enumerated here on C-12, which is the correct
   placement — the gate evaluates against a threshold the register row is
   responsible for having agreed.

7. **`verification_command` = `UNRESOLVED`** — valid during initial ledger
   construction (goal L500-502).

No omission. The three items cover all three conjuncts with the pre-agreement
correctly escalated to a typed approval.

## Verdict

verdict: CLEAN
