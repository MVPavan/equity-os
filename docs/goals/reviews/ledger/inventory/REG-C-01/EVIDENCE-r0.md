# Inventory review — REG-C-01 — EVIDENCE — r0

**Verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| Component ID | `REG-C-01` |
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

`REG-C-01.kind == "register_row"`; `scope_derivation.semantic_review` is `null`
(verified on the row; goal L208-211). `EVIDENCE` and `APPROVAL` only; no
`SCOPE` artifact.

## Live source occurrence (pinned authority)

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md:72`,
section **C. Phase 1 — Evidence-grounded MVP**, register ID `C-01`, status
`Open`, priority `Critical`:

> | C-01 | Critical | Expand to two or three core non-financial companies | Companies selected for disclosure quality, history, differing but manageable structures, and feasible peak-season review capacity | A-12 | Open |

Recomputed `UTF8_LINE_SPAN` digest of line 72:
`2858ae14dd014fcc767cb1e54e51a3c715761920a3c93cdfb8cf647a17924cb9` — equals
`text_digest` and `EV-REG-C-01-SOURCE.content_sha256`. `required_acceptance_text`
is byte-identical to the acceptance cell.

## Reviewed inventory, exactly as read

`required_evidence` (3 items):

| `evidence_id` | `evidence_type` | `proof_mode` | `status` | `approval_ids` |
|---|---|---|---|---|
| `REQ-REG-C-01-ACCEPTANCE` | `ARTIFACT` | `CONTENT_HASH` | `UNRESOLVED` | `[]` |
| `REQ-REG-C-01-SPEC-REVIEW` | `REVIEW` | `CONTENT_HASH` | `UNRESOLVED` | `[]` |
| `REQ-REG-C-01-CAPACITY_COMMITMENT` | `CAPACITY` | `TYPED_APPROVAL` | `UNRESOLVED` | `["APR-REG-C-01-02"]` |

- `…-ACCEPTANCE.description` = "Current proof satisfying: Companies selected for
  disclosure quality, history, differing but manageable structures, and feasible
  peak-season review capacity".
- `…-SPEC-REVIEW` scope = "C-01 under S18: Expand to two or three core
  non-financial companies".
- `…-CAPACITY_COMMITMENT.description` = "Current CAPACITY_COMMITMENT evidence
  from Capacity owner".

`evidence_refs` (2): `EV-REG-C-01-SOURCE` (`UTF8_LINE_SPAN`, register v2:72,
`2026-08-13T02:49:11Z`) and `EV-REG-C-01-SPEC-DRAFT` (`FILE_BYTES`,
`docs/specs/equity-os-s18-universe-review-economics-throughput.md`,
`6b59d6ef082ccca047ec119bc60331894ab1b752fd50e810634da317b0a78631`,
`2026-08-15T07:13:28Z`). Both recomputed: current.

`verification_command` = `{"mode": "UNRESOLVED", "commands": [],
"not_applicable_review": null}`.

## Reasoning

1. **Clause decomposition.** C-01 is a selection decision with four stated
   criteria: disclosure quality, history, "differing but manageable structures",
   and "feasible peak-season review capacity". The first three are judgements
   recorded in a selection rationale; the fourth is a feasibility commitment
   about a scarce human resource.

2. **The fourth criterion is separately typed, and that is the load-bearing
   point.** If `required_evidence` held only the blanket `ARTIFACT` item, the
   capacity feasibility would be provable by a self-authored document — which
   the goal forbids for capacity evidence: capacity evidence "always uses
   `TYPED_APPROVAL` and the typed approval/human-review path, never a fabricated
   shell command" (goal L487-490). `REQ-REG-C-01-CAPACITY_COMMITMENT` is present,
   is `CAPACITY`/`TYPED_APPROVAL`, and names the component-local requirement
   `APR-REG-C-01-02` (verified present in this row's `required_approvals`), so
   the goal's `TYPED_APPROVAL` linkage rule (L484-487) is satisfied.

3. **The first three criteria.** All are carried verbatim in
   `REQ-REG-C-01-ACCEPTANCE.description` and are correctly `ARTIFACT` /
   `CONTENT_HASH`: the proof is the selection record naming the companies and
   the reasoning against each criterion.

4. **Is executable proof demanded?** No. The clause contains no test,
   demonstration, or replay verb — the deliverable is a selection decision, not
   a behaviour. `REG-C-01` is correspondingly absent from the goal's closed
   `EXPECTED_COMMAND_PROOF_COMPONENTS` set (goal L3989-3996; validator `:2635`,
   asserted `:2649`), which matches my independent reading.

5. **Gate cross-check.** `gate_refs` = `["PG-1-09"]`. I read `PG-1-09` ("peak
   results-season capacity is accepted for the selected universe",
   `related_register_ids = ["C-01","C-18"]`): it carries
   `REQ-PG-1-09-ACCEPTANCE` (`ARTIFACT`/`CONTENT_HASH`) **and**
   `REQ-PG-1-09-CAPACITY_COMMITMENT-01` (`CAPACITY`/`TYPED_APPROVAL`). The gate
   and this row demand the same two proof shapes, so the gate imposes nothing
   C-01 lacks. The gate's own copy is a separate obligation on the gate row, not
   a substitute for this one.

6. **Disposition cross-check.** `disposition_refs` are `G-2`, `G-3`, `G-4`,
   `M-8`, `6.1`. M-8 (report L240-250) is the throughput fold-in and lists the
   measures to track; G-3/G-4 govern how cross-company economics may be compared;
   6.1 caveats claim-level sampling. These bear on measurement design (C-12,
   C-18) rather than on which companies are selected, and each is separately
   ledgered (`DISP-G-2`, `DISP-G-3`, `DISP-G-4`, `DISP-M-8`, `DISP-6-1`, all
   verified present with their own `ACCEPTANCE` items). Register v2's Authority
   rule (L23) keeps them off this row.

7. **Dependency.** `A-12` (operating calendar, standing budget, capacity) supplies
   the capacity baseline against which "feasible" is judged, but its evidence is
   A-12's own; goal L188 forbids importing it.

8. **`verification_command` = `UNRESOLVED`** — valid during initial ledger
   construction (goal L500-502); not an inventory gap.

No omission. The three items cover all four criteria plus the standing
spec-review obligation.

## Verdict

verdict: CLEAN
