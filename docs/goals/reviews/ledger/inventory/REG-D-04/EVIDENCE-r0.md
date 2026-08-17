# Inventory review — REG-D-04 / EVIDENCE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `REG-D-04` |
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
| `register_id` / `source_anchor` | `D-04` / `D-04` |
| `source_path` L100-100 | `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` |
| `source_status` / `activation_source_status` | `Deferred` / `Deferred` |
| `program_disposition` / `delivery_status` | `CONDITIONAL_UNACTIVATED` / `SPEC_DRAFT` |
| `priority` / `blueprint_phase` | `High` / `2` |
| `primary_spec` | `S20` — docs/specs/equity-os-s20-memory-benchmark-gbrain.md |
| `dependencies` / `gate_refs` | `[]` / `[]` |
| `disposition_refs` / `human_review_id` | `["R-1", "6.4"]` / `"HR-0004"` |
| `text_digest` (recomputed this round) | `f7eb7eadf35a05fa44a2528cde96094b88415335663240992362cedc3f7bbda8` |

## Reviewed inventory, exactly as read

`review_inventory_projection(row, "EVIDENCE")` — canonical JSON:

```json
{"evidence_refs":[{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"f7eb7eadf35a05fa44a2528cde96094b88415335663240992362cedc3f7bbda8","digest_mode":"UTF8_LINE_SPAN","end_line":100,"evidence_ref_id":"EV-REG-D-04-SOURCE","path":"docs/blueprint/funda-blueprint-implementation-decision-register-v2.md","scope":"Exact authoritative source occurrence for REG-D-04","start_line":100},{"captured_at":"2026-08-15T07:13:28Z","content_sha256":"4948d0f84240cd58b107da1272ed2b90a386bc3fb9ebb6228faac8b98be9c483","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-REG-D-04-SPEC-DRAFT","path":"docs/specs/equity-os-s20-memory-benchmark-gbrain.md","scope":"Current draft specification bytes for REG-D-04","start_line":null}],"required_evidence":[{"approval_ids":[],"description":"Current proof satisfying: Repository, license, maintainers, activity, tests, security, export path, and pinned version recorded","evidence_id":"REQ-REG-D-04-ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"REG-D-04 acceptance and delivery scope","status":"UNRESOLVED"},{"approval_ids":[],"description":"Persisted clean fresh Sol xhigh review of the current specification bytes","evidence_id":"REQ-REG-D-04-SPEC-REVIEW","evidence_ref_ids":[],"evidence_type":"REVIEW","proof_mode":"CONTENT_HASH","scope":"D-04 under S20: Verify GBrain repository and dependency posture","status":"UNRESOLVED"},{"approval_ids":["APR-REG-D-04-03"],"description":"Current LEGAL_REVIEW evidence from Competent dependency-license reviewer","evidence_id":"REQ-REG-D-04-LEGAL_REVIEW","evidence_ref_ids":[],"evidence_type":"LEGAL","proof_mode":"TYPED_APPROVAL","scope":"D-04 under S20: Verify GBrain repository and dependency posture","status":"UNRESOLVED"}],"verification_command":{"commands":[],"mode":"UNRESOLVED","not_applicable_review":null}}
```

Digests observed at review time, **pre-record**:

- `reviewed_input_sha256` (pre-record): `a090df009c8a03bb1ad79dc317afd2826422bf7de12fb97e69bc443ce6f223d2`
- `reviewed_inventory_sha256` (pre-record): `f4d86e799de35a830648772cb64916ecb3880ea1a045d268566399756e2b317f`

Both were recomputed this round with `canonical_sha256` /
`review_input_projection` / `review_inventory_projection` extracted from the
checked-in structural validator by `ast` (never imported), per design r2 §3.3.

## Scope of this decision

Completeness of `required_evidence` only (goal L492-495): does this row's
source clause demand a proof that is not enumerated and classified by proof mode?
Whether any proof has been obtained is out of scope; `UNRESOLVED` with empty
`evidence_ref_ids` is the correct current state on every item (goal L483-484).

## The source clause, re-read this round

Register L100, table `## D. Phase 2 — Memory evaluation` (header L95-96), the single table row for `D-04`:

> | D-04 | High | Verify GBrain repository and dependency posture | Repository, license, maintainers, activity, tests, security, export path, and pinned version recorded | — | Deferred |

Column 4 ("Required evidence / acceptance") is the acceptance text:

> Repository, license, maintainers, activity, tests, security, export path, and pinned version recorded

`text_digest` and `EV-REG-D-04-SOURCE.content_sha256` were both recomputed
this round over the normalized L100-100 span → `f7eb7eadf35a05fa44a2528cde96094b88415335663240992362cedc3f7bbda8`,
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

**Eight recordables, one acceptance, plus one separately typed obligation.** The
clause requires that "Repository, license, maintainers, activity, tests,
security, export path, and pinned version" be **recorded**. Seven of the eight
are due-diligence observations whose proof is the recorded artifact itself, and
`REQ-REG-D-04-ACCEPTANCE` carries the acceptance text verbatim (byte-compared
this round). The eighth — licence — is separately inventoried as
`REQ-REG-D-04-LEGAL_REVIEW` (`LEGAL`/`TYPED_APPROVAL` → `APR-REG-D-04-03`), which
is not redundant with the acceptance item: recording *which* licence GBrain uses
is an observation; determining that the licence is acceptable for Funda is an
authority's judgement. Goal L487-490 requires exactly this split — legal evidence
"always uses `TYPED_APPROVAL` and the typed approval/human-review path, never a
fabricated shell command". This row is the only one of the eleven carrying a
typed `LEGAL` item, and it is correctly the `Competent dependency-license
reviewer` variant rather than `Competent legal reviewer` (`REG-E-08`) or
`Competent trademark or legal reviewer` (`REG-A-09`).

**"security" — the most plausible missing item, checked and rejected.** `SECURITY`
is a valid `evidence_type` and a member of `human_evidence_types`. Two independent
reasons it is not demanded here. First, on the merits: the clause asks that
GBrain's **security posture be recorded** — a finding about a third-party
repository, of the same kind as "maintainers" and "activity" — not that a security
authority grant anything. The only approval type that could anchor a `SECURITY`
item is `SECURITY_EXCEPTION`, which authorizes a *deviation from* a control, and
no deviation is proposed. Second, mechanically: a `SECURITY` item is forced to
`TYPED_APPROVAL` (`:2132-2133`) and must name a component-local approval
requirement (`:2134-2135`); this row has none, and `security_exception_ids` is
`[]` here and on all 213 rows (recomputed this round). Recording a posture is
covered by the `ARTIFACT`/`CONTENT_HASH` acceptance item.

**"tests" does not create a `COMMAND_RESULT` obligation — the second-most
plausible miss.** The word "tests" in a command-proof-bearing ledger invites the
inference that this row must run something. It does not: the clause asks that the
**upstream project's** test posture be recorded, and Funda cannot offer a third
party's test suite as its own reproducible proof — a command result here would be
a fabricated shell demonstration of someone else's repository. Consistently,
`REG-D-04` is outside the 25-member pinned command-proof population, and unlike
`REG-D-01`/`REG-D-03` this row has **no gates at all** (`gate_refs: []`) and **no
dependencies** (register column 5 is the em dash "—", ledger `dependencies: []`),
so there is no gate row silently carrying a mechanical obligation on its behalf
either. The proof is documentary, end to end.

**"export path" checked for a `DATA_RIGHTS` obligation.** Export is about getting
Funda's **own** memory data back out of the dependency — an exit-cost item — not
about acquiring third-party data. Contrast `REG-E-04`, whose clause ingests
external event sources and which does carry a `DATA_RIGHTS` item. No
`DATA_RIGHTS_APPROVAL` exists on this row to anchor one to.

**Typed-approval mirror check.** Three approvals: delegated (carried by
`REQ-REG-D-04-SPEC-REVIEW`), activate-deferred `PRODUCT_OWNER_DECISION`
(unmirrorable by type), and `LEGAL_REVIEW` (mirrored 1:1 by
`REQ-REG-D-04-LEGAL_REVIEW`, whose `approval_ids` is exactly
`["APR-REG-D-04-03"]`). The mirror is exact and complete.

**`verification_command`.** `mode: UNRESOLVED`, valid during initial construction.
Terminally this row is a `NOT_APPLICABLE` candidate — due diligence on an external
repository is not argv-provable — which would itself require an evidenced
`REVIEWER`-role attestation. A future obligation on a different field.

**Residuals.** None.

---

**verdict: CLEAN**

`required_evidence` for `REG-D-04` is complete at the input bytes pinned above.
This review satisfies no evidence item and authorizes no delivery, gate,
approval, or transition.
