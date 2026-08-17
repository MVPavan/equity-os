# Inventory review — `REG-A-06` — `APPROVAL` — `r0`

**verdict: CLEAN**

## 1. Review identity and role binding

| Field | Value |
|---|---|
| Component ID | `REG-A-06` |
| Component kind | `register_row` |
| Review type | `APPROVAL` |
| Review round | `r0` |
| Reviewer identity / session | Reviewer-role dispatch (independent agent and context), Claude Code session dac10266-7ecd-43c9-8e3d-203459a7c509 |
| Role | `REVIEWER` |
| Role binding path | `CONTEXT.md` |
| Role binding SHA-256 (CONTEXT.md bytes at review time) | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| Model actually invoked | `claude-opus-5` |
| Effort actually invoked | `high` |
| Review UTC timestamp | `2026-08-16T13:46:18Z` |

This dispatch is an independent `REVIEWER`-role agent and context, separate from
any `IMPLEMENTER` that produced the reviewed ledger content (goal L947-949;
`CONTEXT.md` "Agent roles (harness-wide)", whose current `REVIEWER` binding is
Claude Opus 5 at high effort — the model and effort recorded above are what was
actually invoked, not a copy of that table).

## 2. Input hashes read at review time

Recomputed by `sha256sum` from repo root `/data/codes/equity-os` during this
review; every file below was read, not assumed.

| Input | Path | SHA-256 |
|---|---|---|
| Active goal contract | `docs/goals/equity-os-blueprint-completion.md` | `f15f7ab5a4e425dec3877ab7f1f7594687979060e4dbcd49390a8a8d5fedb85f` |
| Canonical component ledger | `docs/goals/equity-os-blueprint-component-ledger.jsonl` | `de236d7e8dcf02e307ec58797f5722ae2f85d1d8cdba57d4ecc07df5383c9c97` |
| Pinned decision register v2 (authority for this row) | `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` | `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164` |
| Third-order review disposition report | `docs/blueprint/funda-third-order-review-disposition-report.md` | `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738` |
| Structural validator | `scripts/equity_os_blueprint/validate_ledger_structural.py` | `731d0d8b208b577967c92e3992e7ec1a4333cdecbf89f6951c32d2ec469436f9` |
| Preimplementation validator | `scripts/equity_os_blueprint/validate_ledger_preimplementation.py` | `f7a225a1f99cb85c92cde3094505a92a746552280eb45dae0253a71ab9048013` |
| Canonical human-review artifact | `docs/goals/equity-os-blueprint-human-review-needed.md` | `094fcdfab74a3f4c6fdb82b1520fc4d13b636ac0e9ed10194e5d607aed2ce9af` |
| Role binding table | `CONTEXT.md` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |

Baseline gate state observed at these bytes:
`python3 scripts/equity_os_blueprint/validate_ledger_structural.py --repo-root .`
exits `0`.

## 3. Applicable review slots for this row

`REG-A-06` is a `register_row`. `validate_ledger_preimplementation.py:199-204`
builds the applicable check list as `APPROVAL` + `EVIDENCE` always, and appends
`SCOPE` only when `row["kind"] != "register_row"`. I verified on this row
directly, from the canonical ledger bytes, that
`scope_derivation.semantic_review` is `null`:

```json
{
  "authority_effect": null,
  "derived_program_disposition": "REQUIRED_NOW",
  "related_register_ids": [],
  "rule": "REGISTER_STATUS",
  "semantic_review": null
}
```

So this row has exactly **two** applicable review slots, `EVIDENCE` and
`APPROVAL`, and no `SCOPE` review exists or may be created for it. Its scope
derivation comes from the pinned v2 register itself under rule `REGISTER_STATUS`
(goal L208-211).

The `APPROVAL` slot as read, `PENDING` with the exact 10-key `PENDING` key
set and no role-binding keys (`validate_ledger_structural.py:238-243`,
`:320-356`):

```json
{
  "effort": null,
  "evidence_ref_ids": [],
  "model": null,
  "review_type": "APPROVAL",
  "reviewed_input_sha256": null,
  "reviewed_inventory_sha256": null,
  "reviewer": null,
  "status": "PENDING",
  "timestamp": null,
  "verdict": null
}
```

## 4. Source clause, as read in the pinned authority

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line 36
(file SHA-256 `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`), read verbatim:

```
| A-06 | Critical | Run filing-channel-aware XBRL-versus-PDF spike | Coverage matrix by company, quarter, filing channel, taxonomy/version, statement, segment, note, ownership/share count, restatement behavior, mapping stability, and reconciliation effort | A-02 | Open |
```

| Binding | Ledger value | Recomputed from the pinned bytes | Match |
|---|---|---|---|
| `text_digest` | `fe4ab447a3f815971ef8182e3b94e602e80a85be61b283c53042992e2cde128e` | `fe4ab447a3f815971ef8182e3b94e602e80a85be61b283c53042992e2cde128e` | yes |
| `source_title` | `Run filing-channel-aware XBRL-versus-PDF spike` | cell 3 of the row | yes |
| `required_acceptance_text` | (cell 4, reproduced below) | cell 4 of the row | yes |
| `source_status` | `Open` | cell 6 of the row | yes |
| `priority` | `Critical` | cell 2 of the row | yes |

Acceptance text bound by the ledger:

> Coverage matrix by company, quarter, filing channel, taxonomy/version, statement, segment, note, ownership/share count, restatement behavior, mapping stability, and reconciliation effort

Owning spec: `S09` — Filing ingestion, immutable documents, point-in-time capture, and conditional audio
(`docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md`). Blueprint phase `0A`,
program disposition `REQUIRED_NOW`, delivery status
`REVIEW_BLOCKED`. `disposition_refs` = `["M-9", "R-2"]`,
`gate_refs` = `["PG-0A-04"]`,
`dependencies` = `["A-02"]`.

## 5. Reviewed inventory, exactly as read

The `APPROVAL` inventory is defined by goal L435-436: the `APPROVAL` reviewed inventory is the complete `required_approvals`, `approval_records`, `human_review_id`, and `security_exception_ids` collections.
Transcribed here directly from the canonical ledger bytes whose SHA-256 is
recorded in §2:

```json
{
  "approval_records": [],
  "human_review_id": [
    "HR-0002",
    "HR-0004"
  ],
  "required_approvals": [
    {
      "actor": null,
      "approval_id": "APR-REG-A-06-01",
      "approval_type": "DELEGATED_ARTIFACT_APPROVAL",
      "evidence_ref_ids": [],
      "matched_record_id": null,
      "required_authority": "Delegated fresh Sol xhigh specification reviewer",
      "scope": "A-06 under S09: Run filing-channel-aware XBRL-versus-PDF spike",
      "status": "UNRESOLVED",
      "timestamp": null
    }
  ],
  "security_exception_ids": []
}
```

## 6. The question this review decides

Is `required_approvals` **complete** — does the source clause demand any authority whose sign-off is not enumerated? This audits the completeness of the obligation list, not whether any approval has been obtained.

## 7. Reasoning

**What the source clause demands.** `A-06`'s acceptance cell is a coverage
matrix over eleven measurement axes. It contains no approval verb — no
"approved", "accepted", "authorized", "signed off" — and names no business
authority. Structurally it asks for a measurement to be *performed and
reported*, and the only judgement it invites is whether the spike is complete.

**Against the enumerated inventory.** One requirement is declared:
`APR-REG-A-06-01`, `DELEGATED_ARTIFACT_APPROVAL`, authority
"Delegated fresh Sol xhigh specification reviewer", scope
"A-06 under S09: Run filing-channel-aware XBRL-versus-PDF spike". That is the
contract-universal specification-review obligation carried by every canonical
row; its literal is the single ledger-wide `DELEGATED_ARTIFACT_APPROVAL`
authority string that `validate_ledger_structural.py:2618-2633` requires to be
unique, so it is the pinned current authority and not a per-row invention.

**Derivation sources checked one by one** (goal L535: acceptance text,
dependencies, phase gates, transitions, fail-closed boundaries, security
exceptions).

- *Acceptance text*: no authority named, per above.
- *Phase gates*: `gate_refs` is `["PG-0A-04"]`, and I confirmed by reverse scan
  that `PG-0A-04` is the only gate clause whose `related_register_ids` contains
  `A-06`. `PG-0A-04` carries `required_approvals == []`. This is a real
  discriminator rather than a formality: its sibling `PG-05-05` does carry a
  `DOMAIN_EXPERT_ACCEPTANCE`, and that obligation *is* mirrored onto its
  related row `B-03`. Here there is nothing to mirror.
- *Dependencies*: `A-06` depends on `A-02`, which holds a
  `PRODUCT_OWNER_DECISION` / "Product owner" requirement for selecting the
  discovery company and four quarters. That decision is exercised on `A-02`.
  Copying it onto `A-06` would create a second requirement for one and the same
  determination, and the contract forbids satisfying two requirements from one
  record ("One record satisfies at most one requirement; one approval never
  implies another", goal L188) — so the copy would demand a second, duplicate
  product-owner decision. Dependency ordering, not requirement duplication, is
  the contract's mechanism here.
- *Transitions / fail-closed boundaries / security exceptions*:
  `security_exception_ids` is empty; `approval_records` is empty; nothing in the
  row's controlled state asserts a fail-closed authority boundary.

**Human-review links.** `human_review_id` is `["HR-0002","HR-0004"]`. Both
resolve through the one canonical human-review artifact, and the forward and
reverse link checks are machine-enforced. `HR-0002`'s decision authority is
`GOAL_OR_PROCESS_AUTHORIZATION` / rank-1 current-user authority — a
human-resolution decision type that appears zero times in `required_approvals`
anywhere in the ledger, because it is exercised as a resolution, not carried as
a component inventory obligation.

`required_approvals` is complete for the clause as written.

## 8. Verdict

No omission found. The obligation list is complete against the source clause as
written, against the phase-gate and disposition authorities that reach this row,
and against the contract's closed vocabularies.

verdict: CLEAN
