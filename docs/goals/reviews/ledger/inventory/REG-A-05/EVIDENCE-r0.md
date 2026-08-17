# Inventory review verdict — REG-A-05 — EVIDENCE — r0

**verdict: CLEAN**

Durable evidence for one content-bound `EVIDENCE` inventory review of ledger
component `REG-A-05`. It records no approval and does not satisfy any evidence
item (goal L493-495).

## 1. Review identity

| Field | Value |
|---|---|
| Component ID | `REG-A-05` |
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
| `docs/specs/equity-os-s02-source-rights-providers-consensus-policy.md` (owning spec, corroboration only) | `284d496f4b173c2489b1214e5662af0d6d7454db2558f106bbb649878c57ac14` |

## 3. Applicable review slots — verified on this row, not assumed

`REG-A-05.kind` is `register_row` and its `scope_derivation.semantic_review` is
`null` in the pinned ledger bytes. Goal L208-211 requires that; goal L2886
asserts it; `validate_ledger_preimplementation.py:200-204` appends the `SCOPE`
check only for non-register kinds. Applicable slots: `EVIDENCE` and `APPROVAL`
only. **No `SCOPE` artifact for this component.** Both were `PENDING`.

## 4. Reviewed inventory, exactly as seen

`required_evidence`, `evidence_refs`, `verification_command` (goal L433-434),
reproduced verbatim via the structural validator's own
`review_inventory_projection`, extracted read-only by `ast` (design r2 §3.3):

```json
{
  "evidence_refs": [
    {
      "captured_at": "2026-08-13T02:49:11Z",
      "content_sha256": "bf474f998b557fbc4ded60e208b0692e96976fb02f4a932e24e488a2b92f6aae",
      "digest_mode": "UTF8_LINE_SPAN",
      "end_line": 35,
      "evidence_ref_id": "EV-REG-A-05-SOURCE",
      "path": "docs/blueprint/funda-blueprint-implementation-decision-register-v2.md",
      "scope": "Exact authoritative source occurrence for REG-A-05",
      "start_line": 35
    },
    {
      "captured_at": "2026-08-15T07:13:28Z",
      "content_sha256": "284d496f4b173c2489b1214e5662af0d6d7454db2558f106bbb649878c57ac14",
      "digest_mode": "FILE_BYTES",
      "end_line": null,
      "evidence_ref_id": "EV-REG-A-05-SPEC-DRAFT",
      "path": "docs/specs/equity-os-s02-source-rights-providers-consensus-policy.md",
      "scope": "Current draft specification bytes for REG-A-05",
      "start_line": null
    }
  ],
  "required_evidence": [
    {
      "approval_ids": [],
      "description": "Current proof satisfying: For every source: access method, automation, caching, retention, commercial use, derived outputs, redistribution, account limits, point-in-time availability, and replacement path",
      "evidence_id": "REQ-REG-A-05-ACCEPTANCE",
      "evidence_ref_ids": [],
      "evidence_type": "ARTIFACT",
      "proof_mode": "CONTENT_HASH",
      "scope": "REG-A-05 acceptance and delivery scope",
      "status": "UNRESOLVED"
    },
    {
      "approval_ids": [],
      "description": "Persisted clean fresh Sol xhigh review of the current specification bytes",
      "evidence_id": "REQ-REG-A-05-SPEC-REVIEW",
      "evidence_ref_ids": [],
      "evidence_type": "REVIEW",
      "proof_mode": "CONTENT_HASH",
      "scope": "A-05 under S02: Create provider and data-rights register scoped to the declared boundary",
      "status": "UNRESOLVED"
    },
    {
      "approval_ids": [
        "APR-REG-A-05-02"
      ],
      "description": "Current DATA_RIGHTS_APPROVAL evidence from Data-rights authority",
      "evidence_id": "REQ-REG-A-05-DATA_RIGHTS_APPROVAL",
      "evidence_ref_ids": [],
      "evidence_type": "DATA_RIGHTS",
      "proof_mode": "TYPED_APPROVAL",
      "scope": "A-05 under S02: Create provider and data-rights register scoped to the declared boundary",
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
| `reviewed_inventory_sha256` (`EVIDENCE`) | `2aafd55af763c72e759e59e1ec33acfcb98a77c954097fc7f2ef058a6a4f2ee6` |
| `reviewed_input_sha256` (shared by both review types on this row) | `67c24fc3137611892ef97fbdfe0f325fe388431eddaefe408ab85bb918fdd427` |

These are informational: the recorder recomputes both from the ledger at record
time and must not copy them from this artifact.

## 5. Source clause, read in the pinned authority

`EV-REG-A-05-SOURCE` binds register line 35 (`UTF8_LINE_SPAN` 35–35):

```
| A-05 | Critical | Create provider and data-rights register scoped to the declared boundary | For every source: access method, automation, caching, retention, commercial use, derived outputs, redistribution, account limits, point-in-time availability, and replacement path | A-01 | Open |
```

Dependencies cell: `A-01`. Status cell: `Open`.

Also read: disposition report §R-3 ("Make A-05 depend on A-01" — **Accept**),
this row's second `disposition_ref` alongside `T-4`; `gate_refs = ["PG-0A-02"]`.

## 6. Completeness reasoning

**1. The acceptance obligation, and the one real question on this row.** The
clause enumerates ten dimensions, quantified over every source: access method,
automation, caching, retention, commercial use, derived outputs, redistribution,
account limits, point-in-time availability, replacement path.
`REQ-REG-A-05-ACCEPTANCE` (`ARTIFACT` / `CONTENT_HASH`) reproduces all ten
verbatim — I compared its `description`, minus the `Current proof satisfying: `
prefix, byte-for-byte against register L35 column 4; it matches exactly.

The question worth asking is whether one item is enough for a clause quantified
over *every source* — should the inventory carry one obligation per source, or
per dimension? I concluded no, for two reasons. First, the source set does not
exist yet: S02 §7 defines register completeness against a `SourceUsageInventory`
with `U == R`, and that inventory is precisely what A-05 is chartered to
produce. Enumerating per-source obligations now would fabricate an inventory the
authority has not defined — the opposite of what a completeness review should
force. Second, the goal's evidence schema (L476-483) requires a globally unique
`evidence_id`, nonempty `description`, and exact `scope`; it nowhere requires one
item per clause noun. The per-source, per-dimension granularity S02 §7 describes
is a *satisfaction* requirement discharged through separate
`DATA_RIGHTS_APPROVAL` records at delivery, not an inventory-shape requirement
at these bytes. The verbatim ten-dimension description is what keeps any
dimension from being dropped later, and it is present.

**2. The delegated review obligation.** `REQ-REG-A-05-SPEC-REVIEW`
(`REVIEW` / `CONTENT_HASH`), consumed by `APR-REG-A-05-01`. Present.

**3. Typed-approval evidence.** The row's non-delegated approval is
`APR-REG-A-05-02`, `DATA_RIGHTS_APPROVAL`. It is paired by
`REQ-REG-A-05-DATA_RIGHTS_APPROVAL`, `evidence_type` `DATA_RIGHTS`,
`proof_mode` `TYPED_APPROVAL`, `approval_ids` `["APR-REG-A-05-02"]` — the exact
type correspondence goal L486-489 requires, and the exact back-link goal
L485-486 requires. Ledger-wide, every one of the 46 approval requirements whose
type has a matching `evidence_type` is paired this way with no exceptions, so
this row conforms.

**4. No `COMMAND` obligation.** The clause's operative verb is "Create … 
register"; the ten dimensions are recorded facts about third-party sources, not
behaviour of Funda code. There is no test, replay, or demonstration verb.
`verification_command.mode` `UNRESOLVED` is the valid initial state (goal L187).

**5. `R-3` adds no evidence item.** It constrains A-05's *scope* ("A-05 should
be scoped to the initial boundary while retaining fields for future
commercial/public modes"). Scope derivation is not in the `EVIDENCE` inventory —
and for a register row there is no `SCOPE` review at all, because scope comes
from the pinned register itself. The A-01 dependency is carried structurally in
`dependencies`, which is outside this projection. Neither creates an
unenumerated proof obligation.

Nothing the clause demands is unenumerated.

## 7. Verdict

verdict: CLEAN
