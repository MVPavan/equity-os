# Inventory review — PG-05-05 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `PG-05-05` |
| `review_type` | `SCOPE` |
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

`review_inventory_projection(row, "SCOPE")` — canonical JSON
(`validate_ledger_structural.py:292-318`, extracted by `ast` and executed in an isolated
namespace this round rather than transcribed):

```json
{"activation_predicate":null,"disposition_refs":[],"gate_refs":[],"related_register_ids":["B-03"],"scope_derivation":{"authority_effect":null,"derived_program_disposition":"REQUIRED_NOW","related_register_ids":["B-03"],"rule":"RELATED_REGISTER_SCOPE"}}
```

Digests observed at review time, **pre-record** (the recorder must recompute both after
its Phase A evidence append, per recording design r2 §3.4 — appending review evidence
mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `51180ee5b1f1e644ac5e306fde5edcb3d9f8aba2feef565763af2345a6eef882`
- `reviewed_inventory_sha256` (pre-record): `725daffe74b2b9171f06a5b293d749330c94ebe04d209e9b6ce37861325711a6`

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

**Kind.** A bullet inside the `## F. Phase-gate scorecard` exit list — the clause is a
condition on a phase exit, not a register decision, a disposition finding, or a
deferral. `phase_gate_clause` is the only kind that fits, and it is the kind stored.

**Derivation rule.** `RELATED_REGISTER_SCOPE`. Kind fixes the rule to that or
`ACTIVE_NEGATIVE_CONTROL` (goal L237-239); `validate_ledger_structural.py:1507` carries
`phase_gate_clause -> RELATED_REGISTER_SCOPE` as the default and `:1535-1536` admits
`ACTIVE_NEGATIVE_CONTROL` only for this kind. `:2520-2523` then pins the negative-control
set to `{"PG-1-11"}` exactly, so no other phase-gate row — including this one — may carry
it. `authority_effect` is `null`, required for this rule (`:1551`), and the
`AUTHORITATIVE_OCCURRENCE`-only key `applicable_spec_ids` and the `sequence_clause`-only
key `source_register_ids` are both absent, which is what `extra_scope_keys_by_kind`
(`:1501-1504`) requires for `phase_gate_clause`: the exact five-key scope object and
nothing else.

**Related register IDs — `["B-03"]`, and only B-03.** "the source-of-truth matrix" is
a proper noun in this program: B-03 (register L53) is "Establish source-of-truth matrix",
and its acceptance is "Approved authority table for raw documents, SQL facts, claims,
calculations, narrative memory, derivative indices, evidence packages, and reports". The
term appears in no other register row — I searched the pinned register for it. The
clause's second word, "approved", is likewise B-03's own first acceptance word.

Backlink: `REG-B-03.gate_refs == ["PG-05-05"]`, a singleton, so B-03 is coupled to this
clause and no other. The pairing is one-to-one in both directions, which is the tightest
form this check can return.

**Aggregated disposition.** `REG-B-03.program_disposition == "REQUIRED_NOW"`, so the
one-element aggregation yields `REQUIRED_NOW`, matching both derivation and stored
value.

**Disposition refs, gate refs, predicate.** `disposition_refs == []`. That field records
anchors in the third-order disposition report, and it is populated on exactly three kinds
— measured across the ledger this round: 56 `register_row`, 32 `disposition_item`, 8
`scale_trigger`, and **zero of the 35 `phase_gate_clause` rows**. This component's
authoritative occurrence is in the register file, which is its `source_path`; the
disposition report contains no phase-gate scorecard clause and no `F-0A-*` or `F-0.5-*`
anchor (checked by search), and where it touches this subject matter it does so through
the register rows, which is why those rows and not gate clauses carry the field. `gate_refs == []` — verified to be a register-side field only: the validator
builds `gate_map` *from* phase-gate `related_register_ids` and asserts it against the
register rows' `gate_refs` (`:2659-2666`), so a phase-gate row is the source of that
backlink and never a holder of it. `activation_predicate == null`, required of every
`REQUIRED_NOW` component including one that reached it by related-register aggregation
(goal L288-290).

**Applicable review slot.** A non-register canonical row, so all three review types
apply and `SCOPE` is the `scope_derivation.semantic_review` slot
(`validate_ledger_preimplementation.py:200-204` appends `SCOPE` exactly when
`kind != "register_row"`). The slot is `PENDING` and carries exactly the 10-key
`PENDING` set with all seven value fields `null` and `evidence_ref_ids` empty
(`validate_ledger_structural.py:238-242`), checked programmatically.

**Prior human-review lineage checked.** B-03 is listed under `HR-0003` in
`EXPECTED_PRIOR_HR_LINKS` (`validate_ledger_structural.py:2776-2787`) — but as
`REG-B-03`, the register row, not as this gate. `PG-05-05` correctly does not inherit
that link; its own `human_review_id` is `HR-0004`, from `TR-PG-05-05-001`. Scope
derivation is unaffected either way, but I checked it because a mis-propagated
human-review link is the kind of error that would show up first as a scope anomaly.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records only
that this component's scope derivation is correct at the input bytes pinned above.
