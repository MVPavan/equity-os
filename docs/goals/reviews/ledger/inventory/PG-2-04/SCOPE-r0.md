# Inventory review — PG-2-04 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `PG-2-04` |
| `review_type` | `SCOPE` |
| `review_round` | `r0` |
| `role` | `REVIEWER` |
| `reviewer` | Reviewer-role subagent, session `c43733f6-8986-4487-8aa6-2f7b5b723107` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `model` (actually invoked) | `claude-opus-5` |
| `effort` (actually invoked) | `high` |
| `timestamp` (UTC) | `2026-08-16T03:52:19Z` |

Role binding: `CONTEXT.md` "Agent roles (harness-wide)" L137-139 and L147 bind
`REVIEWER` to Claude Opus 5 at high effort, in an agent and context independent
of any `IMPLEMENTER` that produced the reviewed content. The digest above is the
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

`review_inventory_projection(row, "SCOPE")` — canonical JSON:

```json
{"activation_predicate":null,"disposition_refs":[],"gate_refs":[],"related_register_ids":["D-01","D-03"],"scope_derivation":{"authority_effect":null,"derived_program_disposition":"REQUIRED_NOW","related_register_ids":["D-01","D-03"],"rule":"RELATED_REGISTER_SCOPE"}}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 —
appending review evidence mutates `evidence_refs` and therefore the input
projection):

- `reviewed_input_sha256` (pre-record): `f3f1519162d9b8739291051b9b299245a90eeffdf7fe90b84a5379644433ecff`
- `reviewed_inventory_sha256` (pre-record): `dcb3eba7a55aeb5d8504d24e36d1d9f765375d730dce5bdc10aa54f518f06efc`

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md`
L167, the fourth bullet under `### Phase 2 may exit only when`
(L162), inside `## F. Phase-gate scorecard` (L122):

> - correction, deletion, backup, and export have been tested;

- `source_hash` recomputed over the whole register file → `26d51b31…`, matches
  the stored value.
- `text_digest` recomputed over the normalized L167 span →
  `2fbfb2e54fe8c6907cb49dbd0b01ea8bb08a994a80cfee40eb7a37af474375d6`, equal to
  the stored `text_digest` and to `EV-PG-2-04-SOURCE.content_sha256`.
- `required_acceptance_text` equals that bullet with the list marker and the
  terminal punctuation stripped, byte for byte.

## Reasoning

**Kind.** The occurrence is one bullet of the register's own §F phase-gate
scorecard. `phase_gate_clause` is the kind that inventories exactly those
bullets: all 35 `PG-*` rows carry `source_path` = the pinned v2 register,
`register_id: null`, and a `source_anchor` of the form `F-<phase>-<ordinal>`.
It is not a `register_row` (those are the §A–§E decision table rows and carry a
`register_id`), not a `disposition_item` (those inventory the third-order
disposition report's numbered findings), and not a `first_release_deferral`
(those are §G).

**Derivation rule.** Goal L239 admits exactly two rules for this kind,
`RELATED_REGISTER_SCOPE` or `ACTIVE_NEGATIVE_CONTROL`, and
`validate_ledger_structural.py:1535-1538` enforces that pair. The choice is
further closed from the other side: `:2520-2523` asserts that the set of
canonical rows using `ACTIVE_NEGATIVE_CONTROL` is exactly `{"PG-1-11"}`. So for
this row `RELATED_REGISTER_SCOPE` is the only representable rule, and the
stored value matches. It is also right on the merits — see below — rather than
right only by elimination. `validate_ledger_structural.py:2563-2573` additionally pins this
row by name: rule `RELATED_REGISTER_SCOPE`, `related_register_ids ==
["D-01","D-03"]`, null `authority_effect`, `REQUIRED_NOW` on both disposition
fields, null `primary_spec`, null `activation_predicate`, null
`activation_record`, and `gate_result == "NOT_EVALUATED"`. Every one of those
matches the row as read. `:2655-2657` pins the register pair a second time.

**Related register IDs — `["D-01", "D-03"]`.** Four operations are named —
correction, deletion, backup, export — and the pair covers them without overlap:

- `D-01` (register v2 L97), "Implement `MemoryStore` interface before choosing
  engine": "Retrieval, staged write, promotion, **correction**, **deletion**,
  **export**, cutoff filtering, and provenance contracts are engine-neutral."
  Three of the four appear verbatim; `D-01` is the row that defines them as
  contracts capable of being tested.
- `D-03` (L99), "Define canonical memory promotion transaction": "Narrative
  content hash/commit is registered in SQL; partial writes cannot create
  split-brain state." This is what makes correction and deletion testable
  *against durable state*, and it supplies the transactional half that `D-01`'s
  interface contract does not.

"Backup" is named by neither row verbatim, which I checked rather than glossed:
no §D row uses the word. It falls to `D-01` as the row owning the durable-store
contracts, since backup and export are the same class of obligation over the
same store, and the ledger records the observable conjunction for all four
operations explicitly in this row's command-proof scope (below) rather than by
adding a register ID that does not exist.

**Candidates examined and rejected.** `D-02` (the benchmark) measures outcomes,
not data-management operations, and is claimed by `PG-1-11`, `PG-2-01`,
`PG-2-02`, `PG-2-06`. `D-05` (adoption) decides an engine, not the operations,
and is claimed by four other clauses. `C-10`, the Phase 1 correction workflow,
is a different phase and is claimed by `PG-1-07`; including it — or `D-04`, or
any other `Open` row — would not change this row's already-`REQUIRED_NOW`
disposition, so the exclusion here rests purely on subject matter and on goal
L233-235's no-padding rule rather than on a mechanical consequence.

**Derived disposition — recomputed, and this row is the batch's only mixed
aggregation.** `REG-D-01`: activation `Open`, current `Open` → `REQUIRED_NOW`.
`REG-D-03`: activation `Deferred`, current `Deferred` →
`CONDITIONAL_UNACTIVATED`. Goal L248-250's first branch — "`REQUIRED_NOW` if any
related row is `REQUIRED_NOW`" — fires on `D-01`. Stored fields are
`REQUIRED_NOW`, matching.

I verified this is not an accident of one row: across all 34
`RELATED_REGISTER_SCOPE` phase-gate clauses, **`PG-2-04` is the only one whose
related set mixes an active and a dormant register row**. That makes it the
unique referent of goal L266-272, and everything below follows from it.

**`authority_effect` — `null`, and not a choice.**
`validate_ledger_structural.py:1551` asserts `authority_effect is None` for
every `RELATED_REGISTER_SCOPE` row, and goal L252-254 confines the three
`authority_effect` values to `AUTHORITATIVE_OCCURRENCE`. There is no open
judgment here, unlike a `disposition_item`.

**`activation_predicate: null` — and this is the interesting field on this
row.** Its five Phase 2 siblings (`PG-2-01`, `PG-2-02`, `PG-2-03`, `PG-2-05`,
`PG-2-06`) all carry predicates and are all in `PHASE2_CONDITIONAL_GATE_IDS`
(`validate_ledger_structural.py:411-413`); `PG-2-04` is deliberately excluded
from that set. The reason is goal L288-290: a component derived `REQUIRED_NOW`,
"including one that became `REQUIRED_NOW` by related-register aggregation", has
a null predicate. `D-01` being `Open` is what pulls this clause out of dormancy,
and goal L266-268 states the consequence in terms: "A phase-gate clause whose
related register rows aggregate to `REQUIRED_NOW` is a now-required obligation,
not a dormant one." The null is mandatory, and `:2571` asserts it.

Goal L268-272 then says where the lost conjunction goes: "the observable
conjunction that a predicate would have carried lives instead in the exact
`scope` of that component's command-proof obligation". That is visible on this
row and nowhere else in the ledger — `REQ-PG-2-04-COMMAND-PROOF`'s scope carries
a twelve-term conjunction over correction, deletion, backup, and export, pinned
verbatim as `PG_2_04_COMMAND_PROOF_SCOPE` at `:2553-2562` and re-asserted at
`:2574-2578`. The `EVIDENCE` review of this component treats that scope as an
evidence obligation; from the scope side, what matters is that the derivation's
`REQUIRED_NOW` and the null predicate are consistent with it.

**`gate_refs: []`, reverse link closed.** `REG-D-01.gate_refs == ['PG-2-04']`
and `REG-D-03.gate_refs == ['PG-2-03', 'PG-2-04']`; both contain this row and
`:2659-2666` closes the map. `disposition_refs: []`.

**`primary_spec: null`** — pinned at `:2570`. `D-01` and `D-03` are both
S19-owned, so a single owning spec exists in practice, but goal L185 is explicit
that `primary_spec` "never determines whether a component is active".

**Applicable review slot.** This is a non-register canonical row, so
`validate_ledger_preimplementation.py:199-204` appends `SCOPE` to its checks and
`scope_derivation.semantic_review` is the slot this review fills. It is present,
non-`null`, `PENDING`, and carries exactly the 10-key `PENDING` set with no
role-binding keys.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `PG-2-04`'s scope derivation is correct at the input bytes pinned
above.
