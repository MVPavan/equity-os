# Inventory review — `REG-B-09` — `APPROVAL` — `r0`

**verdict: CLEAN**

## 1. Review identity and role binding

| Field | Value |
|---|---|
| Component ID | `REG-B-09` |
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

`REG-B-09` is a `register_row`. `validate_ledger_preimplementation.py:199-204`
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

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line 59
(file SHA-256 `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`), read verbatim:

```
| B-09 | High | Start point-in-time capture | Daily/event jobs persist approved membership/security changes, prices, announcements, corporate actions, shareholding changes, hashes, first-seen times, and capture failures | A-05 | Open |
```

| Binding | Ledger value | Recomputed from the pinned bytes | Match |
|---|---|---|---|
| `text_digest` | `432d4b996f6762858221e291e985a1b6d294431e55cacdc2a3039b2133c942ca` | `432d4b996f6762858221e291e985a1b6d294431e55cacdc2a3039b2133c942ca` | yes |
| `source_title` | `Start point-in-time capture` | cell 3 of the row | yes |
| `required_acceptance_text` | (cell 4, reproduced below) | cell 4 of the row | yes |
| `source_status` | `Open` | cell 6 of the row | yes |
| `priority` | `High` | cell 2 of the row | yes |

Acceptance text bound by the ledger:

> Daily/event jobs persist approved membership/security changes, prices, announcements, corporate actions, shareholding changes, hashes, first-seen times, and capture failures

Owning spec: `S09` — Filing ingestion, immutable documents, point-in-time capture, and conditional audio
(`docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md`). Blueprint phase `0.5`,
program disposition `REQUIRED_NOW`, delivery status
`REVIEW_BLOCKED`. `disposition_refs` = `["M-9", "R-2"]`,
`gate_refs` = `["PG-05-09"]`,
`dependencies` = `["A-05"]`.

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
      "approval_id": "APR-REG-B-09-01",
      "approval_type": "DELEGATED_ARTIFACT_APPROVAL",
      "evidence_ref_ids": [],
      "matched_record_id": null,
      "required_authority": "Delegated fresh Sol xhigh specification reviewer",
      "scope": "B-09 under S09: Start point-in-time capture",
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

**What the source clause demands.** "Daily/event jobs persist approved
membership/security changes, prices, announcements, corporate actions,
shareholding changes, hashes, first-seen times, and capture failures". The
clause contains the token "approved", so it must be read carefully before
concluding that no business authority is demanded.

**Against the enumerated inventory.** One requirement is declared:
`APR-REG-B-09-01`, `DELEGATED_ARTIFACT_APPROVAL`, the universal
specification-review obligation, scope "B-09 under S09: Start point-in-time
capture".

**Reading "approved".** Grammatically and substantively, "approved" modifies
"membership/security changes" — the data flowing *into* the capture job — not
the delivery of `B-09` itself. The component's obligation is persistence, and
the authority that approves membership and security-master content sits on
`C-17`, which carries `DOMAIN_EXPERT_ACCEPTANCE` / "Entity-data authority". If
`B-09` also carried that requirement, the same entity-data determination would
need two separate records to be satisfied twice (goal L188). So no approval
obligation is created by that word.

**Derivation sources checked one by one.**

- *Phase gates*: `gate_refs` is `["PG-05-09"]`, confirmed by reverse scan to be
  the only gate clause relating to `B-09`. `PG-05-09` — "point-in-time capture
  has started" — carries `required_approvals == []`. Note this gate is
  deliberately phrased as an event, not an acceptance; its Phase 0.5 sibling
  `PG-05-05` ("… is approved") does carry an approval, and that one is mirrored
  onto its related row. The contrast is evidence the distinction is drawn on
  purpose.
- *Dependencies*: `B-09` depends on `A-05`, which holds
  `DATA_RIGHTS_APPROVAL` / "Data-rights authority". This is the one dependency
  in the batch that genuinely deserves scrutiny, because `B-09` runs
  *automated daily/event jobs against external providers* — exactly the surface
  a rights determination governs. But `A-05`'s own acceptance cell is precisely
  that determination: "For every source: access method, **automation**,
  **caching**, retention, commercial use, derived outputs, redistribution,
  account limits, **point-in-time availability**, and replacement path". The
  rights question `B-09` raises is answered on `A-05`, and `B-09` cannot advance
  until it is; a second `DATA_RIGHTS_APPROVAL` here would be a second rights
  decision over the same declared sources.
- *Fail-closed boundaries / security exceptions*: `security_exception_ids` is
  empty; `approval_records` is empty.

**Human-review links.** `["HR-0002","HR-0004"]`, both machine-verified as
bidirectional links to `DECISION` entries. `HR-0002`'s authority is
`GOAL_OR_PROCESS_AUTHORIZATION`, which is a human-resolution decision type and
appears zero times in `required_approvals` ledger-wide.

`required_approvals` is complete for the clause as written.

## 8. Verdict

No omission found. The obligation list is complete against the source clause as
written, against the phase-gate and disposition authorities that reach this row,
and against the contract's closed vocabularies.

verdict: CLEAN
