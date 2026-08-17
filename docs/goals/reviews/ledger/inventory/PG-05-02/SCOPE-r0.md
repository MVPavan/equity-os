# Inventory review — PG-05-02 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `PG-05-02` |
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
{"activation_predicate":null,"disposition_refs":[],"gate_refs":[],"related_register_ids":["A-03","B-02"],"scope_derivation":{"authority_effect":null,"derived_program_disposition":"REQUIRED_NOW","related_register_ids":["A-03","B-02"],"rule":"RELATED_REGISTER_SCOPE"}}
```

Digests observed at review time, **pre-record** (the recorder must recompute both after
its Phase A evidence append, per recording design r2 §3.4 — appending review evidence
mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `01397898b043b2ff2d7f71ed45a485a13eddc2d6c7f0e25da069aff439bc71bc`
- `reviewed_inventory_sha256` (pre-record): `1bae1e2ea9b1bd976852cfa2330635af69e8ead7af1eb3edb76c15a6a9aa3a4a`

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` line 138,
anchor `F-0.5-02`, the 2nd bullet under the
`### Phase 0.5 may exit only when` heading at line 135, inside
`## F. Phase-gate scorecard` (line 122):

> - Quarter 0 manual baseline/bootstrap and three real assisted updates for Quarters 1–3 have been produced and reviewed;

- `source_hash` recomputed over the whole register file →
  `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`, matching the row.
- `text_digest` recomputed over the normalized L138 span (CRLF→LF, surrounding ASCII
  whitespace trimmed) → `875ce63c5716f3ab38aba4c8373bf647a1de8d69dd929916e5b87ccffc97a64f`, matching the row.
- `required_acceptance_text` is that span with the `- ` list marker and the trailing
  `;` removed — compared programmatically, not by eye.
- `EV-PG-05-02-SOURCE` is a `UTF8_LINE_SPAN` reference over exactly that one line
  (`start_line == end_line == 138`); its `content_sha256` recomputes to the same digest,
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

**Related register IDs — `["A-03", "B-02"]`.** The clause is a conjunction of two
distinct products with two distinct register owners, and the split is exact:

- "Quarter 0 manual baseline/bootstrap … produced and reviewed" → A-03 (register L33),
  "Define and perform the manual baseline workflow", whose acceptance is "Quarter 0 is
  completed manually with time-stamped reading, source location, verification,
  calculation, drafting, and approval".
- "three real assisted updates for Quarters 1–3 … produced and reviewed" → B-02
  (register L52), "Produce three real incremental earnings updates", whose acceptance is
  "Quarters 1–3 each consume the approved preceding thesis and include … approval
  record".

A-02 ("Select one discovery company and four consecutive quarters", register L32) is the
obvious near-miss: it is the row that reserves "Quarter 0 … for the manual baseline" and
"Quarters 1–3 … for three assisted incremental updates". But A-02's obligation is the
*selection*, which is gated separately at `PG-0A-03`; this clause requires the quarters
to have been *produced and reviewed*. Including A-02 would pad source semantics with a
prerequisite.

Backlinks confirm the pairing from the register side: `REG-A-03.gate_refs ==
["PG-05-02", "PG-05-03"]` and `REG-B-02.gate_refs == ["PG-05-02"]`.

**Aggregated disposition.** Both related rows are `REQUIRED_NOW`, so the aggregation's
first branch fires (goal L248-250, "`REQUIRED_NOW` if any related row is
`REQUIRED_NOW`") and yields `REQUIRED_NOW`, matching the stored value. Note the
aggregation is a disjunction, so this derivation would survive one of the two going
dormant — a fact worth recording because it means the stored disposition is not evidence
that *both* rows are active; each was checked directly.

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

**Two-register clause, one scope object.** The array is sorted and duplicate-free
(`:1520`) and both IDs are in the register ID set (`:1548`). The clause's conjunction
lives in `required_acceptance_text`, not in the scope object, which is correct: the scope
object records *which authoritative rows this occurrence draws from*, not the logical
shape of the condition.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records only
that this component's scope derivation is correct at the input bytes pinned above.
