# Inventory review — `REG-B-09` — `EVIDENCE` — `r0`

**verdict: CLEAN**

## 1. Review identity and role binding

| Field | Value |
|---|---|
| Component ID | `REG-B-09` |
| Component kind | `register_row` |
| Review type | `EVIDENCE` |
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

The `EVIDENCE` slot as read, `PENDING` with the exact 10-key `PENDING` key
set and no role-binding keys (`validate_ledger_structural.py:238-243`,
`:320-356`):

```json
{
  "effort": null,
  "evidence_ref_ids": [],
  "model": null,
  "review_type": "EVIDENCE",
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

The `EVIDENCE` inventory is defined by goal L433-434: the `EVIDENCE` reviewed inventory is the complete `required_evidence`, `evidence_refs`, and `verification_command` collections.
Transcribed here directly from the canonical ledger bytes whose SHA-256 is
recorded in §2:

```json
{
  "evidence_refs": [
    {
      "captured_at": "2026-08-13T02:49:11Z",
      "content_sha256": "432d4b996f6762858221e291e985a1b6d294431e55cacdc2a3039b2133c942ca",
      "digest_mode": "UTF8_LINE_SPAN",
      "end_line": 59,
      "evidence_ref_id": "EV-REG-B-09-SOURCE",
      "path": "docs/blueprint/funda-blueprint-implementation-decision-register-v2.md",
      "scope": "Exact authoritative source occurrence for REG-B-09",
      "start_line": 59
    },
    {
      "captured_at": "2026-08-15T07:13:28Z",
      "content_sha256": "a1f7477881ac2fb0497b02bcf1bce897219565d6fc521fdd3589a9006fae1c4c",
      "digest_mode": "FILE_BYTES",
      "end_line": null,
      "evidence_ref_id": "EV-REG-B-09-SPEC-DRAFT",
      "path": "docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md",
      "scope": "Current draft specification bytes for REG-B-09",
      "start_line": null
    },
    {
      "captured_at": "2026-08-13T04:29:50Z",
      "content_sha256": "a1f7477881ac2fb0497b02bcf1bce897219565d6fc521fdd3589a9006fae1c4c",
      "digest_mode": "FILE_BYTES",
      "end_line": null,
      "evidence_ref_id": "EV-REG-B-09-S09-R3-N1-CURRENT-S09",
      "path": "docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md",
      "scope": "Exact current S09 bytes adjudicated for S09-r3-N1 on REG-B-09",
      "start_line": null
    },
    {
      "captured_at": "2026-08-13T04:29:50Z",
      "content_sha256": "496d4874e89f119176f06dde057c8500fd36c45d740d1976c833b890c75abab6",
      "digest_mode": "FILE_BYTES",
      "end_line": null,
      "evidence_ref_id": "EV-REG-B-09-S09-R3-N1-R4",
      "path": "docs/goals/reviews/specs/equity-os-s07-s09-r4.md",
      "scope": "Final ordinary r4 review report retaining S09-r3-N1 for REG-B-09",
      "start_line": null
    },
    {
      "captured_at": "2026-08-13T04:29:50Z",
      "content_sha256": "95f7cbcaa3c4530cf56412b20b563435f0fc2bd2452c12bcff7549e561df1bf3",
      "digest_mode": "FILE_BYTES",
      "end_line": null,
      "evidence_ref_id": "EV-REG-B-09-S09-R3-N1-ADJUDICATION",
      "path": "docs/goals/reviews/specs/equity-os-s07-s09-adjudication.md",
      "scope": "Post-cap adjudication upholding S09-r3-N1 and its exact cone for REG-B-09",
      "start_line": null
    }
  ],
  "required_evidence": [
    {
      "approval_ids": [],
      "description": "Current proof satisfying: Daily/event jobs persist approved membership/security changes, prices, announcements, corporate actions, shareholding changes, hashes, first-seen times, and capture failures",
      "evidence_id": "REQ-REG-B-09-ACCEPTANCE",
      "evidence_ref_ids": [],
      "evidence_type": "ARTIFACT",
      "proof_mode": "CONTENT_HASH",
      "scope": "REG-B-09 acceptance and delivery scope",
      "status": "UNRESOLVED"
    },
    {
      "approval_ids": [],
      "description": "Persisted clean fresh Sol xhigh review of the current specification bytes",
      "evidence_id": "REQ-REG-B-09-SPEC-REVIEW",
      "evidence_ref_ids": [],
      "evidence_type": "REVIEW",
      "proof_mode": "CONTENT_HASH",
      "scope": "B-09 under S09: Start point-in-time capture",
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

## 6. The question this review decides

Is `required_evidence` **complete** — does the source clause demand any proof that is not enumerated? This audits the completeness of the obligation list, not whether any proof has been obtained.

## 7. Reasoning

**What the source clause demands.** `B-09` (v2 line 59) is "Start point-in-time
capture", accepted when "Daily/event jobs persist approved membership/security
changes, prices, announcements, corporate actions, shareholding changes,
hashes, first-seen times, and capture failures". The demand is a *persistence*
claim over eight named record classes, including — importantly — the negative
class, "capture failures". The proof is the captured state itself, plus the job
definition that produced it.

**Against the enumerated inventory.** Two items are declared.
`REQ-REG-B-09-ACCEPTANCE` (`ARTIFACT` / `CONTENT_HASH`) carries the acceptance
cell verbatim, which matters here more than usual: because the description is
byte-identical to the source cell (recomputed and matched), the awkward eighth
class, "capture failures", is inside the obligation and cannot be quietly
dropped by a paraphrase that reads as "capture succeeded".
`REQ-REG-B-09-SPEC-REVIEW` (`REVIEW` / `CONTENT_HASH`) is the persisted-review
proof for the row's single `DELEGATED_ARTIFACT_APPROVAL`.

**Is a command proof missing?** No. "persist … and capture failures" is a state
claim about a store; the clause names no test, no replay, no fail-closed
behaviour. Contrast the sibling S09-family row `C-15`, whose cell says "tests
insert and reject post-cutoff records" and which does carry a `COMMAND_RESULT`
item. `REG-B-09` is absent from `EXPECTED_COMMAND_PROOF_COMPONENTS`; declaring
a command item here would fail `validate_ledger_structural.py:2649`.

**Does "approved" in the clause create an evidence obligation?** No — and this
is the one word on the row that could be misread. "approved membership/security
changes" describes the *input data*: entity- and security-master changes that
have already been accepted upstream. `B-09`'s obligation is to persist them
point-in-time. The authority over entity/security-master content is carried by
`C-17` (`DOMAIN_EXPERT_ACCEPTANCE` / "Entity-data authority"), not by the
capture job. So the word demands no typed-approval evidence item here.

**Linked authorities.** Gate `PG-05-09` ("point-in-time capture has started")
is the only gate clause related to `B-09`; it holds a single
`ARTIFACT`/`CONTENT_HASH` acceptance and no approval, adding no proof kind.
Dispositions `M-9` and `R-2` reach this row only as spec-level S09 tags; their
register scopes are `A-08`/`B-08` and `A-06` respectively.

**Open finding.** `S09-r3-N1` is `OPEN_BLOCKING` and load-bearing, adjudicated
`UPHELD` with fix `NOT_AUTHORIZED`. It is a specification-level approval-proof
defect; it identifies no acceptance proof that `required_evidence` omits.

`required_evidence` is complete for the clause as written.

## 8. Verdict

No omission found. The obligation list is complete against the source clause as
written, against the phase-gate and disposition authorities that reach this row,
and against the contract's closed vocabularies.

verdict: CLEAN
