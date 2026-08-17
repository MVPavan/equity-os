# Inventory review — PG-1-08 / APPROVAL / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `PG-1-08` |
| `review_type` | `APPROVAL` |
| `review_round` | `r0` |
| `role` | `REVIEWER` |
| `reviewer` | Reviewer-role subagent, session `c43733f6-8986-4487-8aa6-2f7b5b723107` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `model` (actually invoked) | `claude-opus-5` |
| `effort` (actually invoked) | `high` |
| `timestamp` (UTC) | `2026-08-16T03:52:19Z` |

Role binding: `CONTEXT.md` "Agent roles (harness-wide)" L137-139 and L147 bind
`REVIEWER` to Claude Opus 5 at high effort, independent of any `IMPLEMENTER`
that produced the reviewed content.

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
{"approval_records":[],"human_review_id":[],"required_approvals":[],"security_exception_ids":[]}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 —
appending review evidence mutates `evidence_refs` and therefore the input
projection):

- `reviewed_input_sha256` (pre-record): `30a21cc7444012e779bf57b938faba0ec48366bed6c8c2ddc7355e0e5b48ca02`
- `reviewed_inventory_sha256` (pre-record): `3d8490f952ad11fc316d91ecf8ad98db82eea8653909b7236c8c66569c3d904f`

## Scope of this decision

Goal L188: `required_approvals` "exhaustively declares the component's typed
approval obligations", and "Empty `required_approvals` means a completed,
evidenced determination that no approval is required, not an unknown
inventory." Goal L535-537 fixes the derivation inputs: "Every component derives
`required_approvals` from its exact source acceptance text, dependencies, phase
gates, transitions, fail-closed boundaries, and any approved security
exception." This review decides completeness of that list — whether the source
clause demands an authority whose sign-off is not enumerated — not whether any
approval has been obtained.

## The source clause, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md`
L157, the eighth bullet under `### Phase 1 may exit only when`
(L148), inside `## F. Phase-gate scorecard` (L122):

> - analyst effort improves against matched or per-company baselines by the agreed threshold, with confounds disclosed;

- `source_hash` recomputed over the whole register file → `26d51b31…`, matches
  the stored value.
- `text_digest` recomputed over the normalized L157 span →
  `a30cba48f316e0439924b15b38e4971c3febbb97d99243f69a739ca219c4e2dd`, equal to
  the stored `text_digest` and to `EV-PG-1-08-SOURCE.content_sha256`.
- `required_acceptance_text` equals that bullet with the list marker and the
  terminal punctuation stripped, byte for byte.

## Reasoning

**What has to be affirmed here.** `required_approvals` is `[]`. Goal L188 makes
that a positive claim — "a completed, evidenced determination that no approval
is required, not an unknown inventory" — so the burden of this review is to
affirm the emptiness against the clause's text, not to pass over the row. 40 of
the 169 canonical rows carry an empty list; this is one of them.

**No `DELEGATED_ARTIFACT_APPROVAL`, and that is structural.** All 123
delegated-artifact requirements sit on `register_row` (60), `disposition_item`
(32), `first_release_deferral` (13), `sequence_clause` (10), and `scale_trigger`
(8) rows. **Zero sit on a `phase_gate_clause`** — 0 of 35. That type approves an
artifact (goal L577-582; L957-976), and a §F gate bullet owns none:
`primary_spec` is `null` on every phase-gate row. The artifact approvals for this clause's subject matter are `REG-B-04`'s and `REG-C-12`'s, both under S18.

**The ledger's rule for when a gate clause carries a typed approval —
measured, not assumed.** Six of the 35 gate clauses carry one, and in every case
the clause's *own* acceptance text names an approval or acceptance act as part
of what the gate observes:

| Clause | Text fragment | Approval |
|---|---|---|
| `PG-05-01` | "the bootstrap thesis **is approved**" | `ANALYST_ACCEPTANCE` |
| `PG-05-02` | "…have been produced and **reviewed**" | `ANALYST_ACCEPTANCE` |
| `PG-05-05` | "the source-of-truth matrix **is approved**" | `DOMAIN_EXPERT_ACCEPTANCE` / Data-domain authority |
| `PG-1-06` | "the **approved** narrative is bound to an artifact hash" | `ANALYST_ACCEPTANCE` |
| `PG-1-09` | "peak results-season capacity **is accepted**" | `CAPACITY_COMMITMENT` |
| `PG-2-05` | "operational burden **is acceptable**" | `PRODUCT_OWNER_DECISION` |

The other 29 carry none — including every clause whose verb is "documented",
"recorded", "visible", "in use", "started", "versioned", "exist", "tested", or
"surfaced" — **even where the related register row does carry an authority**.
`PG-0A-07` ("operating capacity and standing budget are documented") carries
none although `REG-A-12` carries both `BUDGET_APPROVAL` and
`CAPACITY_COMMITMENT`; `PG-0A-08` ("the golden-set owner and initial cases
exist") carries none although `REG-A-08` carries `NAMED_OWNER_COMMITMENT`;
`PG-05-06` carries none although `REG-B-12` carries `DOMAIN_EXPERT_ACCEPTANCE`;
`PG-1-01` and `PG-1-02` ("classified as material **under A-10**") carry none
although `REG-A-10` carries `DOMAIN_EXPERT_ACCEPTANCE`. A gate that *observes*
or *cites* an approved upstream artifact does not inherit that artifact's
authority. Goal L613-615 is the rule behind this and it cuts both ways: one
real-world decision may not be inferred to cover two obligations, which
prevents the register's approval from being reused on the gate and equally
prevents inventing a duplicate gate-local one the clause never asks for.

**Applying it to this clause — the sharpest call in this batch.** "…by the
agreed threshold" is a past participle attached to an approval-shaped noun, and
`PG-1-06`, which also carries a past participle attached to an approval-shaped
noun ("the **approved** narrative"), *does* carry an `ANALYST_ACCEPTANCE`. So
parity has to be argued, not asserted. The distinction is what the participle
qualifies:

- On `PG-1-06`, "the approved narrative" is the **object the gate observes**.
  The gate cannot be evaluated until some narrative has actually been approved
  and bound to a hash; the approval act is inside the gate's own evaluation.
- On `PG-1-08`, "the agreed threshold" is the **yardstick the gate measures
  against**, fixed before the measurement. The gate's own question is whether
  the observed improvement clears it and whether confounds were disclosed —
  both determinable without any new sign-off.

That distinction is not mine to invent; the ledger already applies it. `PG-1-01`
and `PG-1-02` say "classified as material **under A-10**", referencing a policy
whose own row `REG-A-10` carries `DOMAIN_EXPERT_ACCEPTANCE`, and both gate rows
carry an empty `required_approvals`. Referencing an upstream approved artifact
does not create a gate-local obligation. `PG-1-08` is that same shape.

The threshold's own authority is not lost by this reading — it is recorded where
it belongs. `REG-C-12` ("Set Phase 1 analyst-economics gate", acceptance
"**Pre-agreed** improvement is evaluated…") carries `ANALYST_ACCEPTANCE` /
"Responsible analyst", scoped `"C-12 under S18: Set Phase 1 analyst-economics
gate"` — a scope string that names the gate-setting act itself. Adding a second
`ANALYST_ACCEPTANCE` here would be the duplicate coverage goal L613-615 requires
be avoided by explicit separate obligations rather than manufactured ones.

**Sweep of the closed non-delegated vocabulary.**

| Type | Why it is not demanded here |
|---|---|
| `ANALYST_ACCEPTANCE` | The near-miss, argued above. The analyst's act is agreeing the threshold on `C-12`, not accepting this gate's arithmetic. 3 of the ledger's 13 sit on phase-gate rows (`PG-05-01`, `PG-05-02`, `PG-1-06`), each with an acceptance act inside the gate's own object. |
| `DOMAIN_EXPERT_ACCEPTANCE` | "Confounds disclosed" is a methodological disclosure, not a calculation, data, entity, or vocabulary ruling. The nearest candidate authority, "Equity-research domain expert", is enumerated exactly once in the ledger (`REG-A-10`, claim materiality), and neither `B-04` nor `C-12` carries any domain authority to inherit. |
| `PRODUCT_OWNER_DECISION` | Activates no deferred scope; both related rows are `Open`. No product judgment is named. |
| `BUDGET_APPROVAL`, `CAPACITY_COMMITMENT` | Analyst *effort* is measured here, not committed. Contrast `PG-1-09` in this same batch, whose clause says capacity "is accepted" and which therefore carries `CAPACITY_COMMITMENT`. Measuring minutes is not committing capacity. |
| `NAMED_OWNER_COMMITMENT` | No owner is appointed; all 3 sit on `REG-A-08`, `REG-E-01`, `REG-E-04`. |
| `MEMORY_PROMOTION` | Nothing is promoted to canonical memory. |
| `DATA_RIGHTS_APPROVAL`, `LEGAL_REVIEW`, `REGULATORY_REVIEW` | No acquisition, licence, or regulated activity. |
| `DISTRIBUTION_APPROVAL`, `EXECUTION_TRUST_DOMAIN_APPROVAL` | Nothing distributed; no execution boundary. |

**Remaining projection fields.** `approval_records: []` — consistent with
an empty requirement list and no decision (goal L188: one record satisfies at most one requirement). `human_review_id: null` — this row is one of the 35 canonical rows outside the 144-ID scope recorded for `HR-0004`; goal L189 permits exactly `null`, one `HR-####` string, or a sorted array of at least two. `open_findings` is `[]`
and `blocked_scope` is `[]`, so no finding-driven link is expected.
`security_exception_ids: []` — the clause crosses no trust boundary, and no
security exception exists anywhere in the ledger (0 of 213 rows).

**Residuals.** None. The `ANALYST_ACCEPTANCE` question above is recorded as a
resolved judgment with its ledger-wide corroboration, not as an open doubt.

---

**verdict: CLEAN**

This review grants no authority (goal L624-626) and authorizes no delivery,
gate, or transition.
