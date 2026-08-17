# Inventory review — REG-C-17 — APPROVAL — r0

**Verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| Component ID | `REG-C-17` |
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

`REG-C-17.kind == "register_row"`; `scope_derivation.semantic_review` is `null`
(verified on the row). `EVIDENCE` and `APPROVAL` only; no `SCOPE` artifact.

## Live source occurrence (pinned authority)

`funda-blueprint-implementation-decision-register-v2.md:88` — `C-17`, "Decide
entity/security master authority", acceptance "Stable internal
company/security IDs; versioned ISIN/symbol/CIN/LEI mappings; source hierarchy,
conflicts, valid/knowledge time, and one real identifier-change case tested",
dependencies `A-05, A-06`, status `Open`, priority `High`. Line digest
recomputed and equal to `text_digest`.

## Reviewed inventory, exactly as read

`required_approvals` (2 items):

| `approval_id` | `approval_type` | `required_authority` | `scope` | `status` | `actor`/`timestamp`/`matched_record_id` | `evidence_ref_ids` |
|---|---|---|---|---|---|---|
| `APR-REG-C-17-01` | `DELEGATED_ARTIFACT_APPROVAL` | `Delegated fresh Sol xhigh specification reviewer` | `C-17 under S17: Decide entity/security master authority` | `UNRESOLVED` | all `null` | `[]` |
| `APR-REG-C-17-02` | `DOMAIN_EXPERT_ACCEPTANCE` | `Entity-data authority` | `C-17 under S17: Decide entity/security master authority` | `UNRESOLVED` | all `null` | `[]` |

`approval_records` = `[]`. `human_review_id` = `"HR-0004"`.
`security_exception_ids` = `[]`.

## Reasoning

1. **The clause's verb is "Decide", and the object of the decision is a data
   authority.** This is the one row in this batch whose title itself names an
   authority question. The competent sign-off is therefore an entity-data domain
   expert, and `APR-REG-C-17-02` enumerates exactly that:
   `DOMAIN_EXPERT_ACCEPTANCE` with `required_authority = "Entity-data
   authority"`, one of the five literals the goal's closed table permits for
   that type (goal L563-575; validator `REQUIRED_AUTHORITY_VOCABULARY` at
   `:2586`, goal L3946-3952).

2. **Beware the word "authority" in the title — it is the object, not the
   approver.** "Entity/security master **authority**" means "which store and
   which identifier are authoritative", a systems-of-record question. The row
   would still need a human sign-off, but for a different reason: the decision
   fixes identity semantics for the whole entity model and cannot be validated
   by test alone. The type chosen reflects that correctly.

3. **Disposition M-7 corroborates and does not add a further authority.** M-7
   (report L226-238) is dispositioned "Accept, but do not use ISIN as the
   internal primary key" and enumerates what "the decision must name". It
   describes the *content* of the decision, not a second approving role. I read
   `DISP-M-7` in the ledger: its `required_approvals` contains only the standard
   `DELEGATED_ARTIFACT_APPROVAL` — no additional business authority anywhere in
   that family. §6.3 likewise (`DISP-6-3`, delegated approval only, verified).

4. **Candidates tested and rejected.**
   - `DATA_RIGHTS_APPROVAL` / "Data-rights authority": the clause is about
     identifier semantics, not about the right to use a data source. Rights are
     `A-05`'s clause — a declared dependency of this row, whose approvals stay
     on `A-05` (goal L188). Note also that `Data-rights authority` belongs to
     `DATA_RIGHTS_APPROVAL` in the closed table, so borrowing it here would
     violate the type/authority pairing the validator enforces.
   - `LEGAL_REVIEW`: ISIN/CIN/LEI are regulatory identifiers, but the clause
     asks how to map them, not whether their use is lawful.
   - `PRODUCT_OWNER_DECISION`: no scope or boundary activation is implicated.
   - A *second* `DOMAIN_EXPERT_ACCEPTANCE` under a different literal (e.g.
     "Data-domain authority"): the goal warns that a second string for an
     authority that already has one is "a permanent trap" (L557-559). One
     entity-data authority is the right and only enumeration.

5. **Dependencies.** `A-05` (provider and data-rights register) and `A-06`
   (filing-channel XBRL/PDF spike) each own their obligations; goal L188
   forbids inferring coverage across rows.

6. **Gates.** `gate_refs` = `[]` — no phase-gate clause names `C-17` in its
   `related_register_ids`, so no gate imposes an authority here. Its dependents
   `C-06` and `C-07` also carry none.

7. **Fail-closed boundaries and state.** `blocked_scope = []`,
   `security_exception_ids = []`, `rejection_record = null`,
   `activation_predicate = null`; `program_disposition = REQUIRED_NOW` derived
   from `Open`/`Open`. The "one real identifier-change case tested" conjunct is
   a proof obligation (enumerated as a `COMMAND_RESULT` item on the evidence
   side), not an approval obligation.

8. **Delegated approval well-formed.** `APR-REG-C-17-01` uses the single
   program-wide delegated-reviewer literal (goal L577-583), scoped to C-17 under
   S17, paired with `REQ-REG-C-17-SPEC-REVIEW`.

Both demanded authorities are enumerated; no omission.

## Verdict

verdict: CLEAN
