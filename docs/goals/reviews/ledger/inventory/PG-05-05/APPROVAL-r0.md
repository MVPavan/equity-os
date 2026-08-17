# Inventory review — PG-05-05 / APPROVAL / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `PG-05-05` |
| `review_type` | `APPROVAL` |
| `review_round` | `r0` |
| `role` | `REVIEWER` |
| `reviewer` | Reviewer-role subagent, session `3c844df3-fdab-4e89-929b-89fcbc8223d4` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `model` (actually invoked) | `claude-opus-5` |
| `effort` (actually invoked) | `high` |
| `timestamp` (UTC) | `2026-08-16T03:50:06Z` |

Role binding: `CONTEXT.md` "Agent roles (harness-wide)" L137-139 binds `REVIEWER` to
Claude Opus 5 at high effort, in an agent and context independent of any `IMPLEMENTER`
that produced the reviewed content. The digest above is the `CONTEXT.md` bytes at review
time and is an immutable historical capture, never re-verified against later bytes
(`validate_ledger_structural.py:250-262`).

## Input hashes read for this review

| Input | SHA-256 |
|---|---|
| `docs/goals/equity-os-blueprint-completion.md` (active goal contract) | `f15f7ab5a4e425dec3877ab7f1f7594687979060e4dbcd49390a8a8d5fedb85f` |
| `docs/goals/equity-os-blueprint-component-ledger.jsonl` (canonical ledger) | `de236d7e8dcf02e307ec58797f5722ae2f85d1d8cdba57d4ecc07df5383c9c97` |
| `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` (pinned v2 decision register) | `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164` |
| `docs/blueprint/funda-third-order-review-disposition-report.md` (pinned third-order disposition report) | `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738` |
| `scripts/equity_os_blueprint/validate_ledger_structural.py` (structural validator) | `731d0d8b208b577967c92e3992e7ec1a4333cdecbf89f6951c32d2ec469436f9` |
| `scripts/equity_os_blueprint/validate_ledger_preimplementation.py` (preimplementation validator) | `f7a225a1f99cb85c92cde3094505a92a746552280eb45dae0253a71ab9048013` |
| `scripts/equity_os_blueprint/extract_goal_validators.py` (extractor) | `5d20d796666d1154fb3c84ba4fa7407ee82819510a5ac06254f7f4a3126c6f2a` |
| `docs/goals/equity-os-blueprint-human-review-needed.md` (canonical human-review artifact) | `094fcdfab74a3f4c6fdb82b1520fc4d13b636ac0e9ed10194e5d607aed2ce9af` |
| `CONTEXT.md` (role binding) | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `docs/goals/reviews/ledger/equity-os-blueprint-inventory-review-recording-design-r2.md` (artifact format, design r2 §2.2) | `adf908ac8cec01a55a53438624c6a8913f673f5b7cecd3e955fc4919f73803fb` |

Fresh validation at these exact bytes, run this round:
`python3 scripts/equity_os_blueprint/validate_ledger_structural.py --repo-root .` → exit `0`;
`python3 scripts/equity_os_blueprint/extract_goal_validators.py --check` → exit `0`, so the
structural validator's pinned manifests are the goal's own bytes, not a downstream
paraphrase of them.

## Reviewed inventory, exactly as read

`review_inventory_projection(row, "APPROVAL")` — canonical JSON
(`validate_ledger_structural.py:292-318`, extracted by `ast` and executed in an isolated
namespace this round rather than transcribed):

```json
{"approval_records":[],"human_review_id":["HR-0004"],"required_approvals":[{"actor":null,"approval_id":"APR-PG-05-05-01","approval_type":"DOMAIN_EXPERT_ACCEPTANCE","evidence_ref_ids":[],"matched_record_id":null,"required_authority":"Data-domain authority","scope":"PG-05-05 domain acceptance","status":"UNRESOLVED","timestamp":null}],"security_exception_ids":[]}
```

Digests observed at review time, **pre-record** (the recorder must recompute both after
its Phase A evidence append, per recording design r2 §3.4 — appending review evidence
mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `51180ee5b1f1e644ac5e306fde5edcb3d9f8aba2feef565763af2345a6eef882`
- `reviewed_inventory_sha256` (pre-record): `c51216d7b3fff873d6e59ab5bda1fdc116f0eb33efd4d22f61199f1300c067b8`

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line 141,
anchor `F-0.5-05`, the 5th bullet under the
`### Phase 0.5 may exit only when` heading at line 135, inside
`## F. Phase-gate scorecard` (line 122):

> - the source-of-truth matrix is approved;

- `source_hash` recomputed over the whole register file →
  `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`, matching the row.
- `text_digest` recomputed over the normalized L141 span (CRLF→LF, surrounding ASCII
  whitespace trimmed) → `25e710bbde88dd8320d0c80b406cf7f74f71426b9426fc07afaa008504b871ea`, matching the row.
- `required_acceptance_text` is that span with the `- ` list marker and the trailing
  `;` removed — compared programmatically, not by eye.
- `EV-PG-05-05-SOURCE` is a `UTF8_LINE_SPAN` reference over exactly that one line
  (`start_line == end_line == 141`); its `content_sha256` recomputes to the same digest,
  so the row's only evidence object resolves against current bytes.

## Reasoning

**What authority the clause demands.** "the source-of-truth matrix is approved" makes
an approval the gate condition. The object is B-03's "Approved authority table for raw
documents, SQL facts, claims, calculations, narrative memory, derivative indices, evidence
packages, and reports" (register L53) — a ruling about which store is authoritative for
which kind of data. That is a data-domain judgment, not an analyst's acceptance of a work
product.

**What is enumerated.** `APR-PG-05-05-01`, `DOMAIN_EXPERT_ACCEPTANCE`, required authority
`Data-domain authority`, scope "PG-05-05 domain acceptance", `UNRESOLVED` with null
actor/timestamp/record and empty evidence.

**Why that exact authority string, checked not assumed.**
`DOMAIN_EXPERT_ACCEPTANCE` admits five authorities in the closed map
(`validate_ledger_structural.py:2592-2596`): `Calculation-domain authority`,
`Data-domain authority`, `Entity-data authority`, `Equity-research domain expert`,
`Vocabulary authority`. The matrix rules on data authority across stores, so
`Data-domain authority` is the fit; `Calculation-domain` and `Entity-data` are narrower
surfaces the clause does not touch, and `Vocabulary authority` belongs to registry
naming (it is what B-12 carries). The goal's warning that a second string for an authority
that already has one "is a permanent trap" makes this a consequential choice, and the
value matches `REG-B-03`'s own `APR-REG-B-03-02` byte for byte.

**Why no analyst acceptance in addition.** The matrix is infrastructure, not an analytical
deliverable; no analyst work product is approved by this clause. B-03 carries no
`ANALYST_ACCEPTANCE` either.

**Why no delegated artifact approval.** No `phase_gate_clause` row carries one;
`primary_spec` is `null` and this clause owns no specification artifact.

**A resolved historical finding.** The program-level approval-inventory review r0 listed
`PG-05-05 — DOMAIN_EXPERT_ACCEPTANCE` among nine rows that "contain explicit approval or
acceptance authority but declare no corresponding non-delegated requirement". At the bytes
reviewed here the requirement exists, with the authority that review named. I confirmed
its presence and its exact `required_authority` value directly.

**Rest of the projection.** `approval_records == []`; `security_exception_ids == []`;
`human_review_id` normalizes to `["HR-0004"]`, and `PG-05-05` appears in the canonical
human-review artifact (2 occurrences, verified by lookup). `REG-B-03` — not this row — is
the component listed under `HR-0003` in `EXPECTED_PRIOR_HR_LINKS`, so no prior link is
missing here.

**Residuals.** None. The approval list is complete against the clause.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition, and grants no
non-delegated authority (goal L624-626). It records only that the component's
`required_approvals` obligation list is complete against its source clause at the input
bytes pinned above.
