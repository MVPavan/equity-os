# Inventory review verdict — REG-A-09 — APPROVAL — r0

**verdict: ISSUES_FOUND**

Durable evidence for one content-bound `APPROVAL` inventory review of ledger
component `REG-A-09`. **This review is not clean.** One Important, load-bearing
omission is recorded in §6.

Because `verdict == "CLEAN"` is asserted for every `COMPLETE` review
(`validate_ledger_structural.py:342`) and a `PENDING` review must carry
`verdict = null` (`:332-338`), a non-clean outcome **has no representation in
the ledger review object**. Per recording design r2 §5.4 the correct handling
is: `REG-A-09.approval_inventory_review` **stays `PENDING`**, this component is
**dropped from the batch-13 recording run**, and this artifact is the durable
record of the finding. No partial or "COMPLETE but not clean" object may be
written.

## 1. Review identity

| Field | Value |
|---|---|
| Component ID | `REG-A-09` |
| Review type | `APPROVAL` |
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
| `docs/specs/equity-os-s01-…-boundary.md` (owning spec) | `1ad276cfa854b760a627b067be5aabe3b36019998a9ad5d1b52194c2dbd4af49` |

The S01 digest equals this row's own `EV-REG-A-09-SPEC-DRAFT.content_sha256`,
so the spec bytes cited below are the bytes the ledger binds — the corroboration
in §6.2 is not read from a stale draft.

## 3. Applicable review slots — verified on this row, not assumed

`scope_derivation` on this row, verbatim from the pinned ledger bytes:

```json
{"authority_effect": null, "derived_program_disposition": "REQUIRED_NOW",
 "related_register_ids": [], "rule": "REGISTER_STATUS", "semantic_review": null}
```

`semantic_review` is `null` (goal L208-211; asserted at goal L2886), so
`validate_ledger_preimplementation.py:200-204` yields `APPROVAL` + `EVIDENCE`
only. **No `SCOPE` artifact for this component.**

## 4. Reviewed inventory, exactly as seen

`required_approvals`, `approval_records`, `human_review_id`,
`security_exception_ids` (goal L435-436), reproduced verbatim via the
structural validator's own `review_inventory_projection`, extracted read-only by
`ast` (design r2 §3.3):

```json
{
  "approval_records": [],
  "human_review_id": [
    "HR-0004"
  ],
  "required_approvals": [
    {
      "actor": null,
      "approval_id": "APR-REG-A-09-01",
      "approval_type": "DELEGATED_ARTIFACT_APPROVAL",
      "evidence_ref_ids": [],
      "matched_record_id": null,
      "required_authority": "Delegated fresh Sol xhigh specification reviewer",
      "scope": "A-09 under S01: Verify project name and trademark risk",
      "status": "UNRESOLVED",
      "timestamp": null
    },
    {
      "actor": null,
      "approval_id": "APR-REG-A-09-02",
      "approval_type": "LEGAL_REVIEW",
      "evidence_ref_ids": [],
      "matched_record_id": null,
      "required_authority": "Competent trademark or legal reviewer",
      "scope": "A-09 under S01: Verify project name and trademark risk",
      "status": "UNRESOLVED",
      "timestamp": null
    }
  ],
  "security_exception_ids": []
}
```

Digests recomputed by me over these exact bytes, using the validator's own
`canonical_sha256`:

| Digest | Value |
|---|---|
| `reviewed_inventory_sha256` (`APPROVAL`) | `bfe58531d9c5ac57762fb96467eefdf09bc9461dfb506f7cb4708f54d8703bc9` |
| `reviewed_input_sha256` (shared by both review types on this row) | `882fc5b714c0df854cf77a724ab05552de557eccde1dfb83730a467a025bf210` |

These are informational: the recorder recomputes both from the ledger at record
time and must not copy them from this artifact.

## 5. Source clause, read in the pinned authority

`EV-REG-A-09-SOURCE` binds register line 39 (`UTF8_LINE_SPAN` 39–39):

```
| A-09 | Medium | Verify project name and trademark risk | Search record and decision on continued use of “Funda” | — | Open |
```

Dependencies cell: `—`. Status cell: `Open`. Disposition refs: `T-4`.
`gate_refs` is empty. Register L23: "The wording in this register is
authoritative for implementation gates."

## 6. Completeness reasoning and finding

Bounds: goal L535 derives `required_approvals` from the exact source acceptance
text, dependencies, phase gates, transitions, and fail-closed boundaries; goal
L583-584 closes the universe to the twelve types in the required-authority
table (L562-575, mechanized as `REQUIRED_AUTHORITY_VOCABULARY` at
`validate_ledger_structural.py:2586-2607`) plus `DELEGATED_ARTIFACT_APPROVAL`.

### 6.1 Enumerated and correct

- `APR-REG-A-09-02`, `LEGAL_REVIEW`, `Competent trademark or legal reviewer`.
  Correct for "trademark risk"; the authority string is an exact member of
  `LEGAL_REVIEW`'s allowed set.
- `APR-REG-A-09-01`, `DELEGATED_ARTIFACT_APPROVAL`, for the specification
  artifact review.

### 6.2 Finding — Important, load-bearing: YES

**`PRODUCT_OWNER_DECISION` (`Product owner`) is demanded by the source clause
and is not enumerated in `required_approvals`.**

The clause demands two things, and the ledger enumerates an authority for only
one of them. "Verify project name and trademark risk" produces a risk
assessment — that is the legal reviewer's, and it is enumerated. But the
acceptance text also demands, in its own words, a **"decision on continued use
of ‘Funda’"**. A decision to keep or abandon the product's name is a
product-scope determination, not a legal conclusion: a competent trademark
reviewer establishes what the risk *is*, and has no authority to decide whether
the program accepts that risk and keeps the name. The authority that does is
`PRODUCT_OWNER_DECISION` with the exact vocabulary literal `Product owner` —
an admissible type, present in the closed table, already used on this very row's
sibling `REG-A-01` and on four other register rows.

Three independent lines of evidence support this, none of them from the row
itself:

1. **The authoritative clause's own verb.** "decision on continued use" is an
   explicit decision demanded by the register wording, which L23 makes
   authoritative. Under goal L535 the approval inventory derives from that exact
   text.
2. **The register's closest structural analogue, in this same batch.**
   `REG-C-13` — "Licensed and necessary, or explicitly excluded from the MVP" —
   is a clause that couples an external-authority determination with a product
   decision. Its `required_approvals` enumerates **both**:
   `DATA_RIGHTS_APPROVAL` for the rights half and `PRODUCT_OWNER_DECISION`
   (`Product owner`) for the decision half. A-09 has the same two-part shape and
   enumerates only the external-authority half.
3. **The owning spec says so three times, and inverts the ledger's priority.**
   S01 §7's "A-09 name decision" gate requires "`PRODUCT_OWNER_DECISION`
   approval record for the exact identity-decision ID and digest, bound to an
   active canonical `SATISFY_APPROVAL` human resolution; **`LEGAL_REVIEW` when
   legal/trademark clearance is represented**." The product-owner approval is
   unconditional; the legal review is conditional. S01 §5.2 repeats it: a
   missing "matching `PRODUCT_OWNER_DECISION` approval record leaves A-09
   unresolved." S01 §4 repeats it again: `approved_product_name` "Must be null
   unless the bound identity decision is current, its exact
   `PRODUCT_OWNER_DECISION` is satisfied, and A-09 is `Accepted`." The ledger
   enumerates the *conditional* authority and omits the *unconditional* one.

**Why this is load-bearing rather than cosmetic.** Goal L188 requires
`required_approvals` to *exhaustively* declare the component's typed approval
obligations, and states that an empty or short inventory is read as "a
completed, evidenced determination that no approval is required, not an unknown
inventory." As the row stands, A-09 can be driven to satisfied with a trademark
reviewer's sign-off plus a delegated artifact review and **no product owner ever
approving the name** — while S01 §4 simultaneously forbids representing an
approved product name without exactly that satisfied approval. That is a
fail-open in the approval inventory against a fail-closed rule in the owning
spec.

**Scope check — this is an omission, not a scoping quibble.** I checked whether
any other ledger component carries the product-name decision authority: scanning
all 213 rows for name/trademark obligations, `REG-A-09` is the only component
that mentions the continued use of the name at all. The authority is
unenumerated program-wide, not merely relocated.

**Suggested remediation (outside this review's remit).** Add one
`required_approvals` entry to `REG-A-09`: next free `approval_id`
(`APR-REG-A-09-03`), `approval_type` `PRODUCT_OWNER_DECISION`,
`required_authority` `Product owner` (exact literal), `scope` matching the row's
existing entries — "A-09 under S01: Verify project name and trademark risk" —
`status` `UNRESOLVED`, `actor`/`timestamp`/`matched_record_id` `null`,
`evidence_ref_ids` `[]`. No paired `required_evidence` item is needed or
possible: the closed `evidence_type` vocabulary has no product-owner member, and
all 23 existing `PRODUCT_OWNER_DECISION` requirements are likewise unpaired.
That is a ledger content change requiring its own bounded task; recording a
`blocked_scope`/`delivery_status` blocker is likewise a separate,
transition-writing tool per design r2 §5.4 item 4 and is **not** performed here.

### 6.3 Types considered and rejected

- `REGULATORY_REVIEW`: a name/trademark question is not a regulatory posture;
  `T-4`'s regulatory obligation lands on `REG-E-08`.
- `DISTRIBUTION_APPROVAL`: the clause does not authorize any distribution mode.
- `EXTERNAL_COORDINATION_APPROVAL` / `PURCHASE_AUTHORIZATION` (a name search or
  registration could involve either): both are absent from the closed
  required-authority table, so goal L583-584 gives them no obligation in this
  inventory and the structural validator would reject them.

## 7. Verdict

verdict: ISSUES_FOUND

Not recordable as a `COMPLETE` ledger review by design.
`REG-A-09.approval_inventory_review` must remain `PENDING` and this component
must be dropped from the batch-13 recording run.
