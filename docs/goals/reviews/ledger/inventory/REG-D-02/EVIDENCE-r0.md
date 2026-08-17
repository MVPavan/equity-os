# Inventory review — REG-D-02 / EVIDENCE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `REG-D-02` |
| `review_type` | `EVIDENCE` |
| `review_round` | `r0` |
| `role` | `REVIEWER` |
| `reviewer` | Reviewer-role subagent, session `c625bbd5-cbd8-40b2-823c-20422d619435` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `model` (actually invoked) | `claude-opus-5` |
| `effort` (actually invoked) | `high` |
| `timestamp` (UTC) | `2026-08-16T13:58:44Z` |

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

Fresh structural validation at these exact bytes → exit `0`
(`python3 scripts/equity_os_blueprint/validate_ledger_structural.py --repo-root .`).

## Applicable review slots for this component

This component is a `register_row`, so it has exactly **two** applicable review
slots. `scope_derivation.semantic_review` is contractually `null` (goal
L208-211, mechanized at `validate_ledger_structural.py:1532`), and
`validate_ledger_preimplementation.py:199-204` builds `checks` as `APPROVAL` +
`EVIDENCE` and appends `SCOPE` only when `row["kind"] != "register_row"`. I
confirmed on this row's live bytes that `scope_derivation` is
`{"authority_effect": null, "derived_program_disposition": "CONDITIONAL_UNACTIVATED",
"related_register_ids": [], "rule": "REGISTER_STATUS", "semantic_review": null}`.
No `SCOPE` artifact exists or may exist for this component.

## Row facts, re-read this round

| Field | Value as read |
|---|---|
| `kind` | `register_row` |
| `register_id` / `source_anchor` | `D-02` / `D-02` |
| `source_path` L98-98 | `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` |
| `source_status` / `activation_source_status` | `Deferred` / `Deferred` |
| `program_disposition` / `delivery_status` | `CONDITIONAL_UNACTIVATED` / `SPEC_DRAFT` |
| `priority` / `blueprint_phase` | `Critical` / `2` |
| `primary_spec` | `S20` — docs/specs/equity-os-s20-memory-benchmark-gbrain.md |
| `dependencies` / `gate_refs` | `["C-05", "D-01", "D-04"]` / `["PG-1-11", "PG-2-01", "PG-2-02", "PG-2-06"]` |
| `disposition_refs` / `human_review_id` | `["R-1", "6.4"]` / `"HR-0004"` |
| `text_digest` (recomputed this round) | `f6fcaf28d67d26fe22a49525fb9e268e883377555cf30bdf423f7b62a077f0f5` |

## Reviewed inventory, exactly as read

`review_inventory_projection(row, "EVIDENCE")` — canonical JSON:

```json
{"evidence_refs":[{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"f6fcaf28d67d26fe22a49525fb9e268e883377555cf30bdf423f7b62a077f0f5","digest_mode":"UTF8_LINE_SPAN","end_line":98,"evidence_ref_id":"EV-REG-D-02-SOURCE","path":"docs/blueprint/funda-blueprint-implementation-decision-register-v2.md","scope":"Exact authoritative source occurrence for REG-D-02","start_line":98},{"captured_at":"2026-08-15T07:13:28Z","content_sha256":"4948d0f84240cd58b107da1272ed2b90a386bc3fb9ebb6228faac8b98be9c483","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-REG-D-02-SPEC-DRAFT","path":"docs/specs/equity-os-s20-memory-benchmark-gbrain.md","scope":"Current draft specification bytes for REG-D-02","start_line":null}],"required_evidence":[{"approval_ids":[],"description":"Current proof satisfying: All arms receive the same authoritative prior artifacts; compare no persistent memory/manual context assembly, Git/Markdown/SQL retrieval, and GBrain on longitudinal tasks, retrieval misses, contradiction/staleness detection, analyst time, unsupported claims, latency, cost, and operations; result governs current adoption only; re-evaluation triggers are precommitted","evidence_id":"REQ-REG-D-02-ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"REG-D-02 acceptance and delivery scope","status":"UNRESOLVED"},{"approval_ids":[],"description":"Persisted clean fresh Sol xhigh review of the current specification bytes","evidence_id":"REQ-REG-D-02-SPEC-REVIEW","evidence_ref_ids":[],"evidence_type":"REVIEW","proof_mode":"CONTENT_HASH","scope":"D-02 under S20: Run current-scale three-arm memory benchmark","status":"UNRESOLVED"}],"verification_command":{"commands":[],"mode":"UNRESOLVED","not_applicable_review":null}}
```

Digests observed at review time, **pre-record**:

- `reviewed_input_sha256` (pre-record): `bc7b99611c754550cbabcd76317b671cb00418aeb194d61ccf79868b035983ab`
- `reviewed_inventory_sha256` (pre-record): `ad8a60e0f7601aff0a879a51ac2f249e3e2a0fe089dc91ad07e936b93b499577`

Both were recomputed this round with `canonical_sha256` /
`review_input_projection` / `review_inventory_projection` extracted from the
checked-in structural validator by `ast` (never imported), per design r2 §3.3.

## Scope of this decision

Completeness of `required_evidence` only (goal L492-495): does this row's
source clause demand a proof that is not enumerated and classified by proof mode?
Whether any proof has been obtained is out of scope; `UNRESOLVED` with empty
`evidence_ref_ids` is the correct current state on every item (goal L483-484).

## The source clause, re-read this round

Register L98, table `## D. Phase 2 — Memory evaluation` (header L95-96), the single table row for `D-02`:

> | D-02 | Critical | Run current-scale three-arm memory benchmark | All arms receive the same authoritative prior artifacts; compare no persistent memory/manual context assembly, Git/Markdown/SQL retrieval, and GBrain on longitudinal tasks, retrieval misses, contradiction/staleness detection, analyst time, unsupported claims, latency, cost, and operations; result governs current adoption only; re-evaluation triggers are precommitted | C-05, D-01, D-04 | Deferred |

Column 4 ("Required evidence / acceptance") is the acceptance text:

> All arms receive the same authoritative prior artifacts; compare no persistent memory/manual context assembly, Git/Markdown/SQL retrieval, and GBrain on longitudinal tasks, retrieval misses, contradiction/staleness detection, analyst time, unsupported claims, latency, cost, and operations; result governs current adoption only; re-evaluation triggers are precommitted

`text_digest` and `EV-REG-D-02-SOURCE.content_sha256` were both recomputed
this round over the normalized L98-98 span → `f6fcaf28d67d26fe22a49525fb9e268e883377555cf30bdf423f7b62a077f0f5`,
matching the stored values. The register's ID, priority, title, acceptance text,
dependencies, and status cells were each byte-compared against the corresponding
ledger fields; all six match.

## Reasoning

**Program-wide facts recomputed this round** (not transcribed from any peer
artifact), used in the sweeps below:

- The `evidence_type` vocabulary is closed at 17 values
  (`validate_ledger_structural.py:2095-2100`) and 13 of them are
  `human_evidence_types` (`:2101-2105`), which the validator forces to
  `proof_mode: TYPED_APPROVAL` (`:2132-2133`); a `TYPED_APPROVAL` item must name
  at least one component-local `required_approvals` entry (`:2134-2135`), and a
  non-`TYPED_APPROVAL` item must name none (`:2136-2137`). So a typed evidence
  item cannot exist on a row that carries no matching approval requirement.
- Mirroring is exact ledger-wide: of the 194 `required_approvals` entries across
  all 213 rows, every entry whose `approval_type` has a counterpart in
  `human_evidence_types` is mirrored 1:1 by a `TYPED_APPROVAL` evidence item
  (47 of 47), and the only unmirrored types are the three with **no**
  representable evidence type — `DELEGATED_ARTIFACT_APPROVAL` (123),
  `PRODUCT_OWNER_DECISION` (23) and `EXECUTION_TRUST_DOMAIN_APPROVAL` (1). The
  delegated obligation is instead carried by the `REVIEW`/`CONTENT_HASH`
  `-SPEC-REVIEW` item present on every row with a non-null `primary_spec`
  (verified: 1:1 across all 60 register rows).
- The command-proof population is a goal-owned constant of 25 component IDs
  (`EXPECTED_COMMAND_PROOF_COMPONENTS`, `:2635-2648`) and the validator asserts
  the ledger's actual `COMMAND_RESULT` holders equal it exactly (`:2649`).
- The negative "no-implementation" proof machinery is mapped to exactly one
  component (`NO_IMPLEMENTATION_REQUIREMENT_MAP`, `:2671-2673` → `DISP-R-1`), and
  `DISP-R-1` is the only row in the ledger carrying a `SOURCE`-typed evidence
  item.
- `security_exception_ids` is `[]` and `approval_records` is `[]` on all 213
  rows, so no security exception and no recorded decision can create an
  unenumerated obligation anywhere.

**Four obligations in one clause, all preserved.** This is the longest
acceptance text of the eleven and it is semicolon-joined: (i) all arms receive
the same authoritative prior artifacts; (ii) the three-arm comparison across
eleven named dimensions; (iii) "result governs current adoption only";
(iv) "re-evaluation triggers are precommitted". `REQ-REG-D-02-ACCEPTANCE` carries
the whole string **verbatim** — byte-compared this round against register L98
column 4 — so none of the four is lost to paraphrase. They are one acceptance:
each is a property of the *same* benchmark artifact, and the goal's model is one
acceptance item per source acceptance text.

**`COMMAND_RESULT` — checked, and correctly absent for a reason internal to the
clause.** The comparison dimensions include **analyst time** and **operations**,
which are human-measured quantities no argv can produce, and the two
mechanical-sounding dimensions (latency, cost) are *measurements recorded in the
benchmark report*, not pass/fail assertions a command could return. There is no
oracle for "retrieval misses and contradictions caught later by humans" either —
disposition R-1 (re-read this round) explicitly frames that as human-instrumented
telemetry. So the proof mode is a content-addressed benchmark artifact, and
`REG-D-02` is correctly outside the 25-member pinned command-proof population.
Corroborating: none of this row's four gates (`PG-1-11`, `PG-2-01`, `PG-2-02`,
`PG-2-06`) carries a `COMMAND_RESULT` item either — verified on their live bytes,
in contrast to `PG-2-03`/`PG-2-04`, which do, and which belong to `D-03`/`D-01`.

**The negative "dormancy" proof belongs to `DISP-R-1`, not here — the check most
likely to be missed on this row.** `DISP-R-1` is the ledger's single
`REJECTED_ACCOUNTED` component and it exists precisely to record the rejection of
disposition R-1 ("Cancel D-02 memory benchmark"); its pinned requirement asserts
that the current S20 draft "preserves D-02 as dormant and contains no
implementation claim". That is a *negative* proof obligation about this row's
scope, and the tempting conclusion is that `REG-D-02` should mirror it. It must
not: `NO_IMPLEMENTATION_REQUIREMENT_MAP` (`:2671-2673`) names exactly
`DISP-R-1` → `REQ-DISP-R-1-NO-IMPLEMENTATION`, and `DISP-R-1` is also the only
row in the ledger carrying a `SOURCE`-typed evidence item. One determination,
one requirement (goal L188).

**Disposition amendments are already inside the acceptance text.** R-1 and 6.4
(both re-read this round) are the linked `disposition_refs`. R-1's four
amendments — state that the result governs current adoption only, define
minimum query/task coverage, include operational burden, predefine re-evaluation
triggers — appear in the register wording as adopted, and 6.4 adds no obligation
beyond "future triggers should reopen the question", which is (iv). No amendment
survives outside the enumerated acceptance item.

**Typed-approval sweep.** The row's two approvals are the delegated artifact
approval (carried by `REQ-REG-D-02-SPEC-REVIEW`) and the activate-deferred
`PRODUCT_OWNER_DECISION`, which has no counterpart in the closed `evidence_type`
vocabulary and is unmirrored on all 23 of its ledger-wide instances. Note the
asymmetry deliberately: the clause requires **cost** to be *measured and
compared*, which is an obligation on the artifact, not a `BUDGET` evidence item —
and a `BUDGET` item is in any case unrepresentable here, since
`:2134-2135` requires a `TYPED_APPROVAL` item to name a component-local approval
requirement and this row has no `BUDGET_APPROVAL`.

**`verification_command`.** `mode: UNRESOLVED`, valid during initial construction
(goal L501-502). Terminally this row is a candidate for `NOT_APPLICABLE` with an
evidenced reviewer attestation rather than `COMMANDS`, because its acceptance
turns on human-measured quantities. A future obligation on a different field.

**Residuals.** None.

---

**verdict: CLEAN**

`required_evidence` for `REG-D-02` is complete at the input bytes pinned above.
This review satisfies no evidence item and authorizes no delivery, gate,
approval, or transition.
