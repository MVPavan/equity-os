# Inventory review verdict — REG-A-01 — EVIDENCE — r0

**verdict: CLEAN**

This artifact is the durable evidence for one content-bound `EVIDENCE`
inventory review of ledger component `REG-A-01`. It records no approval, grants
no authority, and does not satisfy any evidence item (goal L493-495).

## 1. Review identity

| Field | Value |
|---|---|
| Component ID | `REG-A-01` |
| Review type | `EVIDENCE` |
| Round | `r0` |
| Role | `REVIEWER` |
| Reviewer | Independent `REVIEWER` subagent, Claude Code session `6b725e7a-eda6-42e9-be39-2f0d26984eee`, batch-13 dispatch |
| Role binding path | `CONTEXT.md` |
| Role binding SHA-256 (at review time) | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| Model actually invoked | `claude-opus-5` |
| Effort actually invoked | `high` |
| Review UTC | `2026-08-16T13:48:25Z` |
| Batch | 13 (`register_row`, specs S01–S04) per recording design r2 §5.2 |

## 2. Inputs read at review time

| Input | SHA-256 |
|---|---|
| `docs/goals/equity-os-blueprint-completion.md` | `f15f7ab5a4e425dec3877ab7f1f7594687979060e4dbcd49390a8a8d5fedb85f` |
| `docs/goals/equity-os-blueprint-component-ledger.jsonl` | `de236d7e8dcf02e307ec58797f5722ae2f85d1d8cdba57d4ecc07df5383c9c97` |
| `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` | `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164` |
| `docs/blueprint/funda-third-order-review-disposition-report.md` | `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738` |
| `scripts/equity_os_blueprint/validate_ledger_structural.py` | `731d0d8b208b577967c92e3992e7ec1a4333cdecbf89f6951c32d2ec469436f9` |
| `CONTEXT.md` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `docs/specs/equity-os-s01-…-boundary.md` (owning spec, corroboration only) | `1ad276cfa854b760a627b067be5aabe3b36019998a9ad5d1b52194c2dbd4af49` |

The S01 digest equals this row's own `EV-REG-A-01-SPEC-DRAFT.content_sha256`,
so the owning-spec bytes I read are the bytes the ledger binds.

## 3. Applicable review slots — verified on this row, not assumed

`REG-A-01` has `kind = "register_row"` and `scope_derivation.semantic_review`
is `null` in its own ledger bytes (quoted in §4 of the APPROVAL artifact and
verified directly here). Per goal L208-211 a register row's `semantic_review`
is contractually `null`, and `validate_ledger_preimplementation.py:200-204`
builds `checks` as `APPROVAL` + `EVIDENCE` and appends `SCOPE` only
`if row["kind"] != "register_row"`. The applicable slots are therefore
**`EVIDENCE` and `APPROVAL` only**; no `SCOPE` artifact exists or should exist
for this component. Both applicable slots were `PENDING` at the pinned ledger
bytes.

## 4. Reviewed inventory, exactly as seen

The `EVIDENCE` reviewed inventory is `required_evidence`, `evidence_refs`, and
`verification_command` (goal L433-434). Reproduced verbatim from the pinned
ledger bytes via the structural validator's own
`review_inventory_projection`, extracted read-only by `ast` per recording
design r2 §3.3:

```json
{
  "evidence_refs": [
    {
      "captured_at": "2026-08-13T02:49:11Z",
      "content_sha256": "c467848b177c03cee840f261d39afd6a81af902b8c3c892e6d92021617ab5de8",
      "digest_mode": "UTF8_LINE_SPAN",
      "end_line": 31,
      "evidence_ref_id": "EV-REG-A-01-SOURCE",
      "path": "docs/blueprint/funda-blueprint-implementation-decision-register-v2.md",
      "scope": "Exact authoritative source occurrence for REG-A-01",
      "start_line": 31
    },
    {
      "captured_at": "2026-08-15T07:13:28Z",
      "content_sha256": "1ad276cfa854b760a627b067be5aabe3b36019998a9ad5d1b52194c2dbd4af49",
      "digest_mode": "FILE_BYTES",
      "end_line": null,
      "evidence_ref_id": "EV-REG-A-01-SPEC-DRAFT",
      "path": "docs/specs/equity-os-s01-product-identity-operating-distribution-boundary.md",
      "scope": "Current draft specification bytes for REG-A-01",
      "start_line": null
    }
  ],
  "required_evidence": [
    {
      "approval_ids": [],
      "description": "Current proof satisfying: Written statement covering private/internal use, public or paid distribution, personalization, execution linkage, and intended future boundary; document does not claim legal sufficiency",
      "evidence_id": "REQ-REG-A-01-ACCEPTANCE",
      "evidence_ref_ids": [],
      "evidence_type": "ARTIFACT",
      "proof_mode": "CONTENT_HASH",
      "scope": "REG-A-01 acceptance and delivery scope",
      "status": "UNRESOLVED"
    },
    {
      "approval_ids": [],
      "description": "Persisted clean fresh Sol xhigh review of the current specification bytes",
      "evidence_id": "REQ-REG-A-01-SPEC-REVIEW",
      "evidence_ref_ids": [],
      "evidence_type": "REVIEW",
      "proof_mode": "CONTENT_HASH",
      "scope": "A-01 under S01: Freeze initial user and distribution boundary",
      "status": "UNRESOLVED"
    }
  ],
  "verification_command": {
    "commands": [],
    "mode": "UNRESOLVED",
    "not_applicable_review": null
  }
}
```

Digests recomputed by me over these exact bytes, using the validator's own
`canonical_sha256`:

| Digest | Value |
|---|---|
| `reviewed_inventory_sha256` (`EVIDENCE`) | `39cfedba6dcfc135352d737ea3635098294fa316d48124895a0a7f64f1e424cd` |
| `reviewed_input_sha256` (shared by both review types on this row) | `4d3d7cceec9f641be74b057c4c4d2426729e69b79ed311c87888faac854eaf78` |

These are informational: the recorder recomputes both from the ledger at record
time and must not copy them from this artifact.

## 5. Source clause, read in the pinned authority

The row's own `EV-REG-A-01-SOURCE` binds
`funda-blueprint-implementation-decision-register-v2.md` line 31 as a
`UTF8_LINE_SPAN` (31–31). Read at those bytes:

```
| A-01 | Critical | Freeze initial user and distribution boundary | Written statement covering private/internal use, public or paid distribution, personalization, execution linkage, and intended future boundary; document does not claim legal sufficiency | — | Open |
```

Register L23 fixes this wording as authoritative: "The wording in this register
is authoritative for implementation gates. Narrative reviews explain rationale
but do not override this register."

Row context also read: `disposition_refs = ["T-4"]` (disposition report
§T-4, "Partially accept"), `gate_refs = ["PG-0A-01"]`, `program_disposition`
`REQUIRED_NOW`, `open_findings = []`.

## 6. Completeness reasoning

The question this review decides is narrow: **does the source clause demand any
proof that `required_evidence` does not enumerate?** Whether the proof has been
obtained is not in scope — every item here is correctly `UNRESOLVED` with empty
`evidence_ref_ids`, which the goal permits (L187, "Initial unresolved values are
valid").

**1. The acceptance obligation.** The clause demands one written statement
covering five dimensions — private/internal use, public or paid distribution,
personalization, execution linkage, intended future boundary — plus one
negative constraint, that the document does not claim legal sufficiency.
`REQ-REG-A-01-ACCEPTANCE` (`ARTIFACT` / `CONTENT_HASH`) carries the clause
**verbatim**: I compared its `description`, minus the `Current proof
satisfying: ` prefix, byte-for-byte against register L31 column 4 and it
matches exactly. That matters more than the item count: because the description
is verbatim, no dimension and not the legal-sufficiency constraint can be
silently dropped when the proof is later assessed. A single content-hashed
artifact obligation is the right shape here — the clause demands one document,
not five separate proofs.

**2. The delegated review obligation.** `REQ-REG-A-01-SPEC-REVIEW`
(`REVIEW` / `CONTENT_HASH`) carries the persisted clean specification review
that `APR-REG-A-01-01` (`DELEGATED_ARTIFACT_APPROVAL`) consumes. Present.

**3. Typed-approval evidence — the one place an omission could hide.** The
row's only other approval requirement is `APR-REG-A-01-02`,
`PRODUCT_OWNER_DECISION`. No paired `TYPED_APPROVAL` evidence item exists for
it, and none is required: the closed `evidence_type` vocabulary (goal
L479-483) has no product-owner member, and goal L486-489's enumeration of the
evidence classes that must use `TYPED_APPROVAL` — analyst, domain, provider,
rights, legal, regulatory, budget, capacity, owner, production, distribution,
security, external — does not include a product-owner decision. I checked this
against the whole ledger rather than trusting the reading: all 23
`PRODUCT_OWNER_DECISION` requirements ledger-wide carry no paired
`required_evidence` item, while every one of the 46 approval requirements whose
type has a matching `evidence_type` does carry one, using exactly the
corresponding type. The pattern has no exceptions, so this absence is
contract-mandated, not an omission.

**4. No `COMMAND` obligation is hidden in this clause.** "Written statement"
is a documentary obligation; the clause contains no test, replay,
demonstration, or measurement verb. `verification_command.mode` is
`UNRESOLVED` with empty `commands`, which is the valid initial state under goal
L187 and is uniform across all 60 register rows.

**5. `T-4` adds no evidence obligation here.** The row's own disposition ref
holds that "A-01 can define the intended product boundary without completing
legal analysis" and pushes current regulatory verification to the point of
external, paid, personalized, or execution-connected use. That downstream
obligation is enumerated on `REG-E-08`, which depends on A-01 — not on this
row. So the absence of legal/regulatory evidence items here is what the
disposition requires.

**6. `PG-0A-01`** is a separate ledger component with its own evidence
inventory; a gate reference does not create a component-local evidence item on
the referencing row.

Nothing the clause demands is unenumerated.

## 7. Verdict

verdict: CLEAN
