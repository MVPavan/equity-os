# Inventory review — REG-C-07 — APPROVAL — r0

**Verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| Component ID | `REG-C-07` |
| Review type | `APPROVAL` |
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

`REG-C-07.kind == "register_row"`; `scope_derivation.semantic_review` is `null`
(verified on the row). `EVIDENCE` and `APPROVAL` only; no `SCOPE` artifact.

## Live source occurrence (pinned authority)

`funda-blueprint-implementation-decision-register-v2.md:78` — `C-07`, "Put
factual entity relationships in bitemporal SQL", acceptance
"Parent/subsidiary, management roles, ownership, cross-holdings, and
validity/knowledge intervals are represented", dependency `C-17`, status
`Open`, priority `High`. Line digest recomputed and equal to `text_digest`.

## Reviewed inventory, exactly as read

`required_approvals` (1 item):

| `approval_id` | `approval_type` | `required_authority` | `scope` | `status` | `actor`/`timestamp`/`matched_record_id` | `evidence_ref_ids` |
|---|---|---|---|---|---|---|
| `APR-REG-C-07-01` | `DELEGATED_ARTIFACT_APPROVAL` | `Delegated fresh Sol xhigh specification reviewer` | `C-07 under S17: Put factual entity relationships in bitemporal SQL` | `UNRESOLVED` | all `null` | `[]` |

`approval_records` = `[]`. `human_review_id` = `"HR-0004"`.
`security_exception_ids` = `[]`.

## Reasoning

1. **The clause names no authority.** Its subject is what the relationship store
   represents; its predicate is "are represented". There is no approval,
   acceptance, agreement, or authorization verb anywhere in the acceptance cell,
   and no role is named.

2. **The word "factual" is a scope qualifier, not an authority trigger.** The
   title distinguishes *factual* relationships (parent/subsidiary, roles,
   ownership) from inferred or analytical ones, which is a data-classification
   statement. It does not summon a domain expert to attest the data.

3. **Candidates tested and rejected.**
   - `DOMAIN_EXPERT_ACCEPTANCE` / "Entity-data authority": this is the
     strongest candidate, since `C-17` — C-07's sole dependency, same spec S17,
     same disposition refs — does carry it. It stays on `C-17` because C-17's
     clause is an act of deciding the entity/security-master authority, and
     disposition M-7 (report L226-238) frames its bullets as things "**the
     decision** must name". C-07 consumes that decision to shape a schema. A
     second, independent sign-off here would be the inferred coverage goal
     L611-614 explicitly forbids ("record two explicit human resolutions …
     rather than infer coverage" applies only where two real decisions exist;
     here there is one).
   - `LEGAL_REVIEW`: cross-holdings and ownership are financial-structure facts
     drawn from disclosures, not a legal opinion the register asks for.
     Trademark/legal review is `A-09`'s clause.
   - `DATA_RIGHTS_APPROVAL` / `PROVIDER_AUTHORIZATION`: sourcing rights for
     shareholding and relationship data are `A-05`'s clause.
   - `ANALYST_ACCEPTANCE`: no analyst judgement is accepted by this clause.

4. **Dependencies.** `C-17`'s approvals remain on `C-17` (goal L188).

5. **Gates.** `gate_refs` = `[]` — no phase-gate clause names `C-07` in its
   `related_register_ids`. I checked the Phase 1 gate list (register v2
   L148-160) for a clause that would implicitly require an authority over entity
   relationships and found none; the bitemporal-correctness gate clause
   (`PG-1-05`, post-cutoff exclusion) relates to `C-15`, not to this row.

6. **Fail-closed boundaries.** `blocked_scope = []`,
   `security_exception_ids = []`, `rejection_record = null`,
   `activation_predicate = null`; `program_disposition = REQUIRED_NOW` derived
   from `Open`/`Open`. No exception or activation authority applies.

7. **Delegated approval well-formed.** `APR-REG-C-07-01` uses the single
   program-wide delegated-reviewer literal (goal L577-583), scoped to C-07 under
   S17, paired with `REQ-REG-C-07-SPEC-REVIEW`.

The empty typed-approval set is a correct positive determination (goal L188).
No omission.

## Verdict

verdict: CLEAN
