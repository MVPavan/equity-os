# Inventory review verdict — REG-A-09 — EVIDENCE — r0

**verdict: CLEAN**

Durable evidence for one content-bound `EVIDENCE` inventory review of ledger
component `REG-A-09`. It records no approval and does not satisfy any evidence
item (goal L493-495).

> **Read with:** `APPROVAL-r0.md` in this directory returns **ISSUES_FOUND** on
> this same component. §6.5 below explains why that finding does not propagate
> into the evidence inventory, so that a later reader does not mistake this
> `CLEAN` for an oversight.

## 1. Review identity

| Field | Value |
|---|---|
| Component ID | `REG-A-09` |
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

## 3. Applicable review slots — verified on this row, not assumed

`REG-A-09.kind` is `register_row`; its `scope_derivation.semantic_review` is
`null` in the pinned ledger bytes (goal L208-211, asserted at goal L2886).
`validate_ledger_preimplementation.py:200-204` appends `SCOPE` only for
non-register kinds. Applicable slots: `EVIDENCE` and `APPROVAL` only. **No
`SCOPE` artifact for this component.** Both were `PENDING`.

## 4. Reviewed inventory, exactly as seen

`required_evidence`, `evidence_refs`, `verification_command` (goal L433-434),
reproduced verbatim via the structural validator's own
`review_inventory_projection`, extracted read-only by `ast` (design r2 §3.3):

```json
{
  "evidence_refs": [
    {
      "captured_at": "2026-08-13T02:49:11Z",
      "content_sha256": "36946395e9c69d565a922865b2ba14738affc35b20e7afe06e3c77dac85cc59f",
      "digest_mode": "UTF8_LINE_SPAN",
      "end_line": 39,
      "evidence_ref_id": "EV-REG-A-09-SOURCE",
      "path": "docs/blueprint/funda-blueprint-implementation-decision-register-v2.md",
      "scope": "Exact authoritative source occurrence for REG-A-09",
      "start_line": 39
    },
    {
      "captured_at": "2026-08-15T07:13:28Z",
      "content_sha256": "1ad276cfa854b760a627b067be5aabe3b36019998a9ad5d1b52194c2dbd4af49",
      "digest_mode": "FILE_BYTES",
      "end_line": null,
      "evidence_ref_id": "EV-REG-A-09-SPEC-DRAFT",
      "path": "docs/specs/equity-os-s01-product-identity-operating-distribution-boundary.md",
      "scope": "Current draft specification bytes for REG-A-09",
      "start_line": null
    }
  ],
  "required_evidence": [
    {
      "approval_ids": [],
      "description": "Current proof satisfying: Search record and decision on continued use of “Funda”",
      "evidence_id": "REQ-REG-A-09-ACCEPTANCE",
      "evidence_ref_ids": [],
      "evidence_type": "ARTIFACT",
      "proof_mode": "CONTENT_HASH",
      "scope": "REG-A-09 acceptance and delivery scope",
      "status": "UNRESOLVED"
    },
    {
      "approval_ids": [],
      "description": "Persisted clean fresh Sol xhigh review of the current specification bytes",
      "evidence_id": "REQ-REG-A-09-SPEC-REVIEW",
      "evidence_ref_ids": [],
      "evidence_type": "REVIEW",
      "proof_mode": "CONTENT_HASH",
      "scope": "A-09 under S01: Verify project name and trademark risk",
      "status": "UNRESOLVED"
    },
    {
      "approval_ids": [
        "APR-REG-A-09-02"
      ],
      "description": "Current LEGAL_REVIEW evidence from Competent trademark or legal reviewer",
      "evidence_id": "REQ-REG-A-09-LEGAL_REVIEW",
      "evidence_ref_ids": [],
      "evidence_type": "LEGAL",
      "proof_mode": "TYPED_APPROVAL",
      "scope": "A-09 under S01: Verify project name and trademark risk",
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
| `reviewed_inventory_sha256` (`EVIDENCE`) | `a6caa85c9774f676e597142cfd252ccb33c2759b457b25ba808052acae1da5b0` |
| `reviewed_input_sha256` (shared by both review types on this row) | `882fc5b714c0df854cf77a724ab05552de557eccde1dfb83730a467a025bf210` |

These are informational: the recorder recomputes both from the ledger at record
time and must not copy them from this artifact.

## 5. Source clause, read in the pinned authority

`EV-REG-A-09-SOURCE` binds register line 39 (`UTF8_LINE_SPAN` 39–39):

```
| A-09 | Medium | Verify project name and trademark risk | Search record and decision on continued use of “Funda” | — | Open |
```

Dependencies cell: `—`. Status cell: `Open`. Disposition refs: `T-4`.
`gate_refs` is empty.

## 6. Completeness reasoning

**1. The acceptance obligation.** The clause demands two documentary
deliverables: a **search record**, and a **decision** on continued use of the
name. `REQ-REG-A-09-ACCEPTANCE` (`ARTIFACT` / `CONTENT_HASH`) carries both,
verbatim — I compared its `description`, minus the `Current proof satisfying: `
prefix, byte-for-byte against register L39 column 4, including the typographic
quotation marks around “Funda”, and it matches exactly. Both deliverables are
therefore inside the enumerated obligation; neither can be dropped when the
proof is assessed.

**2. Cross-check against the owning spec's evidence column.** S01 §7 states the
A-09 gate's required evidence as "Search record with scope, evidence,
conflicts, explicit decision, and recomputed content digest." Every element of
that list is a component *of* the search record and decision the acceptance item
already demands, and the "recomputed content digest" is the `CONTENT_HASH`
proof mode itself. Nothing there is an unenumerated obligation.

**3. The delegated review obligation.** `REQ-REG-A-09-SPEC-REVIEW`
(`REVIEW` / `CONTENT_HASH`), consumed by `APR-REG-A-09-01`. Present.

**4. Typed-approval evidence.** The row's non-delegated approval is
`APR-REG-A-09-02`, `LEGAL_REVIEW`, and it is paired by
`REQ-REG-A-09-LEGAL_REVIEW`: `evidence_type` `LEGAL`, `proof_mode`
`TYPED_APPROVAL`, `approval_ids` `["APR-REG-A-09-02"]`, and the description
names the exact required authority, "Competent trademark or legal reviewer".
Correct type correspondence per goal L486-489 and correct back-link per goal
L485-486.

**5. Interaction with this component's APPROVAL finding — checked, not
assumed.** In `APPROVAL-r0.md` I find that `PRODUCT_OWNER_DECISION` is omitted
from this row's `required_approvals`. That omission does **not** create an
unenumerated evidence obligation here, for a reason I verified rather than
inferred: the closed `evidence_type` vocabulary (goal L479-483) contains no
product-owner member, and goal L486-489's list of classes that must use
`TYPED_APPROVAL` does not include a product-owner decision. Across the whole
ledger, all 23 `PRODUCT_OWNER_DECISION` requirements carry no paired
`required_evidence` item, without exception. So even after the approval
inventory is corrected, this evidence inventory would be unchanged. The two
reviews are genuinely independent on this row, and this one is complete on its
own terms.

**6. No `COMMAND` obligation.** "Search record" is a documentary artifact
recording a name search; the clause has no test, replay, or demonstration verb.
`verification_command.mode` `UNRESOLVED` is the valid initial state (goal L187).

**7. `T-4`** concerns regulatory verification before boundary crossing and adds
no evidence obligation to a trademark search; `gate_refs` is empty, so no gate
contributes one either.

Nothing the clause demands is unenumerated.

## 7. Verdict

verdict: CLEAN
