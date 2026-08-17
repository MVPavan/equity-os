# Inventory review — DISP-M-3 / APPROVAL / r0

**verdict: ISSUES_FOUND**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-M-3` |
| `review_type` | `APPROVAL` |
| `review_round` | `r0` |
| `role` | `REVIEWER` |
| `reviewer` | Reviewer-role subagent, session `a88da077-0dfc-49ab-bb1a-df4e8266291b` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `model` (actually invoked) | `claude-opus-5` |
| `effort` (actually invoked) | `high` |
| `timestamp` (UTC) | `2026-08-15T13:16:03Z` |

Role binding: `CONTEXT.md` "Agent roles (harness-wide)" binds `REVIEWER` to
Claude Opus 5 at high effort, in an agent and context independent of any
`IMPLEMENTER` that produced the reviewed content. The digest above is the
`CONTEXT.md` bytes at review time and is an immutable historical capture.

## Input hashes read for this review

| Input | SHA-256 |
|---|---|
| `docs/goals/equity-os-blueprint-completion.md` (active goal) | `f15f7ab5a4e425dec3877ab7f1f7594687979060e4dbcd49390a8a8d5fedb85f` |
| `docs/goals/equity-os-blueprint-component-ledger.jsonl` (canonical ledger) | `de236d7e8dcf02e307ec58797f5722ae2f85d1d8cdba57d4ecc07df5383c9c97` |
| `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` (pinned v2 register) | `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164` |
| `docs/blueprint/funda-third-order-review-disposition-report.md` (pinned disposition report) | `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738` |
| `scripts/equity_os_blueprint/validate_ledger_structural.py` (structural validator) | `731d0d8b208b577967c92e3992e7ec1a4333cdecbf89f6951c32d2ec469436f9` |
| `scripts/equity_os_blueprint/validate_ledger_preimplementation.py` | `f7a225a1f99cb85c92cde3094505a92a746552280eb45dae0253a71ab9048013` |
| `scripts/equity_os_blueprint/extract_goal_validators.py` | `5d20d796666d1154fb3c84ba4fa7407ee82819510a5ac06254f7f4a3126c6f2a` |
| `docs/goals/equity-os-blueprint-human-review-needed.md` | `094fcdfab74a3f4c6fdb82b1520fc4d13b636ac0e9ed10194e5d607aed2ce9af` |
| `CONTEXT.md` (role binding) | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `docs/goals/reviews/ledger/equity-os-blueprint-inventory-review-recording-design-r2.md` (artifact format) | `adf908ac8cec01a55a53438624c6a8913f673f5b7cecd3e955fc4919f73803fb` |

Fresh structural validation at these exact bytes:
`python3 scripts/equity_os_blueprint/validate_ledger_structural.py --repo-root .`
→ exit `0` (run at review time).

## Reviewed inventory, exactly as read

`review_inventory_projection(row, "APPROVAL")` — canonical JSON:

```json
{"approval_records":[],"human_review_id":["HR-0004"],"required_approvals":[{"actor":null,"approval_id":"APR-DISP-M-3-01","approval_type":"DELEGATED_ARTIFACT_APPROVAL","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Delegated fresh Sol xhigh specification reviewer","scope":"M-3 under S13","status":"UNRESOLVED","timestamp":null}],"security_exception_ids":[]}
```

Digests observed at review time, **pre-record** (the recorder must recompute both
after its Phase A evidence append, per recording design r2 §3.4 — appending review
evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `2b97105430ea5512995d0895fe860a01a77f56860b0f38676410e6d1a777ebe2`
- `reviewed_inventory_sha256` (pre-record): `0edb3bdf3fe7a87db5d282402689959a1375cc61fd912ac4f8c638aff9409f28`

## Live source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` lines 168-180, anchor
`M-3`, `source_title` "Predicate and metric vocabulary governance":

> ### M-3 — Predicate and metric vocabulary governance
>
> **Disposition: Accept with a simpler Phase 0.5 implementation.**
>
> Typed claims are ineffective without controlled predicates and metric definitions. The first version needs:
>
> - a small versioned metric registry;
> - a small versioned claim-predicate registry;
> - aliases and deprecated terms;
> - definition, expected object type, units/dimensions, and scope rules;
> - a human approval rule for additions.
>
> Embedding-assisted duplicate suggestions are optional later. They should not be a Phase 0.5 dependency for a registry containing only dozens of entries.


Recomputed this round against current bytes:

- `source_hash` over the whole file → `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738`, equal to the stored value.
- `text_digest` over the normalized L168-180 span
  (CRLF-to-LF normalized, surrounding ASCII whitespace trimmed) →
  `a7d8a6209c47dcce38693046ce19563c89e4dde47e0d9310d3bc949693c5017e`, equal to the stored value.
- `required_acceptance_text` equals that normalized span byte for byte.
- Every `evidence_refs` object on this row was re-hashed against current bytes and
  matches its stored `content_sha256`.

## Reasoning

**Enumerated.** One requirement:

| `approval_id` | `approval_type` | `required_authority` | `scope` | `status` |
|---|---|---|---|---|
| `APR-DISP-M-3-01` | `DELEGATED_ARTIFACT_APPROVAL` | `Delegated fresh Sol xhigh specification reviewer` | `M-3 under S13` | `UNRESOLVED` |

The enumerated requirement is itself well-formed: the type is in the closed
vocabulary (goal L~538-548) and the authority literal is the one value
`validate_ledger_structural.py:2620-2631` requires every
`DELEGATED_ARTIFACT_APPROVAL` requirement to share. `approval_records` is `[]` and
the requirement is `UNRESOLVED` with null actor, null timestamp, empty evidence and
null `matched_record_id` — internally consistent.
`security_exception_ids` is `[]`, correct: the clause raises no fail-closed
security boundary.

`human_review_id` is `"HR-0004"`, a single `HR-####` string (goal L~192-196),
normalized to `["HR-0004"]` inside this projection, resolving into the one
canonical human-review artifact.

**Source-clause scan for omitted authorities.** Remit per goal L188:
`approval_inventory_review` "records whether a fresh `REVIEWER`-role review has
checked the component's source clauses for **omitted approval types**". Derivation
basis per goal L535-537: "its exact source acceptance text, dependencies, phase
gates, transitions, fail-closed boundaries, and any approved security exception".

Report L168-180 lists what the first version of the vocabulary governance "needs",
and its fifth and final bullet is:

> - a human approval rule for additions.

That is an authority obligation stated in the clause's own words: additions to the
metric and claim-predicate registries must be approved by a human. No requirement
on this row represents it. **The finding below records that.**

## Finding 1 — `required_approvals` omits the human approval the clause names

**Severity:** Important. **Load-bearing:** yes — `required_approvals` is a terminal
gating collection: `validate_ledger_structural.py:2299-2312`
(`assert_complete_proof`) requires every entry to be `SATISFIED` with a
`matched_record_id` before `VERIFIED`, `Accepted`, or gate `PASS`. As inventoried,
`DISP-M-3` can reach those states with no human having approved anything about the
registries, while the clause it enforces requires registry additions to be
human-approved.

**What the clause says.** Report L168-180, fifth bullet: "**a human approval rule
for additions**". The goal makes `required_approvals` the collection that
"exhaustively declares the component's typed approval obligations" (goal L188) and
derives it "from its exact source acceptance text" (goal L535-537). An approval
obligation stated in the acceptance text and absent from the collection is exactly
the "omitted approval type" this review exists to detect.

**The authority exists in the closed vocabulary and is already in use for this
requirement.** `DOMAIN_EXPERT_ACCEPTANCE` carries `Vocabulary authority` among its
allowed `required_authority` values (goal required-authority table;
`validate_ledger_structural.py:2586-2600`, `REQUIRED_AUTHORITY_VOCABULARY`). And
`REG-B-12` — the register decision this clause is an authoritative occurrence over,
whose acceptance text reads "Registry definitions, aliases, object/unit/dimension
rules, **addition approval**, deprecation, and versioning exist" — carries exactly
`("DOMAIN_EXPERT_ACCEPTANCE", "Vocabulary authority")`. So this is **not** the
vocabulary-reconciliation case of goal L~552-556: no new type or authority literal
is needed, and no reconciliation is required. The authority the clause names is
representable, is represented elsewhere for the identical requirement, and is
simply not declared here.

**This programme does propagate clause-named approvals onto disposition rows.** Two
rows in this same batch prove the rule:

| Row | Clause phrase | Second requirement carried |
|---|---|---|
| `DISP-M-1` | "Approve and version it before the three later assisted updates" | `ANALYST_ACCEPTANCE` / `Responsible analyst`, scope "M-1 analyst acceptance" |
| `DISP-M-5` | "a clear path from rejected claim to … reapproval" | `ANALYST_ACCEPTANCE` / `Responsible analyst`, scope "M-5 analyst acceptance" |
| `DISP-M-3` | "a human approval rule for additions" | **none** |

Each of those mirrors the approval its related register carries (`REG-A-11` and
`REG-B-14` respectively) with a component-local scope. `DISP-M-3` stands in the
identical relation to `REG-B-12` and carries nothing.

**Contrary reading, stated and answered.** One can read "a human approval rule for
additions" as a *design requirement on the specification* — S13 must define who
approves registry additions — rather than an approval obligation on this ledger
component, in which case the delegated artifact approval of S13's bytes would be
sufficient and this review would be `CLEAN`. I do not adopt it, because
`DISP-M-5`'s clause names reapproval in exactly that design-requirement form ("a
clear path from rejected claim to … reapproval" — a property the path must have,
not an act performed on this component) and the ledger nonetheless attaches
`ANALYST_ACCEPTANCE` there. The two rows cannot both be right under one rule; under
either rule one of them is wrong, and only one of the two failures — the missing
approval — is a completeness defect that this review can act on.

I also considered and rejected the narrower objection that `DISP-M-7`'s clause says
"The decision must name … conflict-resolution rule" and carries no
`DOMAIN_EXPERT_ACCEPTANCE` despite `REG-C-17` carrying one, so `DISP-M-3` need not
either. That distinction is precisely why `DISP-M-7`'s `APPROVAL` review is `CLEAN`
and this one is not: `M-7`'s clause requires the decision to *name* things, and
naming is not approving; `M-3`'s clause requires that additions be *approved*.

**Scope of this finding.** It asserts only that an authority the clause names is
not enumerated. Choosing the exact `approval_type`, `required_authority`, and
`scope` is remediation's job and must be reviewed on its own; the strongest
candidate, on the evidence above, is `DOMAIN_EXPERT_ACCEPTANCE` /
`Vocabulary authority` with a component-local scope such as "M-3 vocabulary
addition approval", plus the mirroring `TYPED_APPROVAL` evidence item recorded as
finding 2 of `docs/goals/reviews/ledger/inventory/DISP-M-3/EVIDENCE-r0.md`. Because
`required_approvals` is inside `review_input_projection`, that edit must happen
before any review on this row is digested (recording design r2 §3.4).

---

**verdict: ISSUES_FOUND**

**This artifact is not recordable as a `COMPLETE` review, and that is correct.**
`validate_ledger_structural.py:342` accepts exactly one `verdict` value on a
`COMPLETE` review, `CLEAN`; there is no schema slot for a negative verdict. Per
recording design r2 §5.4 the `APPROVAL` review on `DISP-M-3` therefore stays
`PENDING`, this artifact is the durable record of the finding, and the finding
belongs in `open_findings` on `DISP-M-3` with severity, load-bearing status, artifact
and disposition — written by a tool with a different safety envelope, not by this
review.

Because a row's applicable reviews must be recorded all-at-once or not at all
(recording design r2 §3.4), no review on `DISP-M-3` is recordable while this finding
stands.

This row carries findings in two of its three review types; see also
`docs/goals/reviews/ledger/inventory/DISP-M-3/EVIDENCE-r0.md`.

This review authorizes no delivery, gate, approval, or transition.
