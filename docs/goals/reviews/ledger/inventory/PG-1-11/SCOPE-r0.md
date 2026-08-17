# Inventory review — PG-1-11 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `PG-1-11` |
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
{"activation_predicate":null,"disposition_refs":[],"gate_refs":[],"related_register_ids":["D-02","D-05","E-03","E-05","E-09"],"scope_derivation":{"authority_effect":null,"derived_program_disposition":"REQUIRED_NOW","related_register_ids":["D-02","D-05","E-03","E-05","E-09"],"rule":"ACTIVE_NEGATIVE_CONTROL"}}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 —
appending review evidence mutates `evidence_refs` and therefore the input
projection):

- `reviewed_input_sha256` (pre-record): `74e13f988a87b583e0043d1bf64218031b93ef5fc4443fb2545aa25702d00469`
- `reviewed_inventory_sha256` (pre-record): `78f9172ef2f4d04b4f1cad2757a21497aae2b531f6550a8eafd5c82cf80f840a`

## Live source occurrence, re-read this round

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md`
L160, the eleventh bullet under `### Phase 1 may exit only when`
(L148), inside `## F. Phase-gate scorecard` (L122):

> - GBrain, debate, backtesting, and execution remain outside the release unless separately approved.

- `source_hash` recomputed over the whole register file → `26d51b31…`, matches
  the stored value.
- `text_digest` recomputed over the normalized L160 span →
  `3c35050148bf632247195590dbb7cf4cc783706b090853659ac7abfe5d8e6ea7`, equal to
  the stored `text_digest` and to `EV-PG-1-11-SOURCE.content_sha256`.
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

**Derivation rule — `ACTIVE_NEGATIVE_CONTROL`, and this is the one row entitled
to it.** Goal L259-264 allows the rule only for `phase_gate_clause` and requires
four things of it: nonempty exact `related_register_ids`,
`authority_effect=null`, `derived_program_disposition=REQUIRED_NOW`, and
`activation_predicate=null`. `validate_ledger_structural.py:1541-1546` enforces
all four, and `:2508-2523` pins this row by name — rule, the exact register list
`["D-02","D-05","E-03","E-05","E-09"]`, null authority effect, `REQUIRED_NOW` on
both disposition fields, null `primary_spec`, null predicate,
`source_start_line == 160` — and then asserts that the set of canonical rows
using the rule is exactly `{"PG-1-11"}`. All of that matches the row as read.

The rule is also right on the merits, which is the part the validator cannot
decide. Goal L263-264: "It activates no capability: it proves that named
capabilities stay dormant or rejected." The clause asserts that four capabilities
**remain outside** the release. Under `RELATED_REGISTER_SCOPE` the aggregation of
five `Deferred` rows would derive `CONDITIONAL_UNACTIVATED` (goal L250-252),
which would say this gate obligation is dormant — precisely inverting the
clause, since the obligation to keep those capabilities out is live *now* and is
strongest while they are dormant. `ACTIVE_NEGATIVE_CONTROL` is the rule that
makes a negative obligation over dormant scope a present obligation.

**Related register IDs — `["D-02", "D-05", "E-03", "E-05", "E-09"]`.** The clause
names four capabilities; each maps to the register rows that would place it
inside the release:

- **GBrain** → `D-02` (L98), "Run current-scale three-arm memory benchmark",
  which is where GBrain is first exercised, and `D-05` (L101), "Decide GBrain
  adoption", which is the adoption decision itself.
- **debate** → `E-03` (L111), "Evaluate bull/bear and forensic review" —
  adversarial multi-position review, the blueprint's name for debate.
- **backtesting** → `E-05` (L113), "Begin controlled quant validation".
- **execution** → `E-09` (L117), "Keep execution in a separate trust domain".

All five are `Deferred` at activation and `Deferred` now, so the negative claim
has live subject matter. Sorted and unique; `set(related) <= expected_ids` holds
(`:1543`).

**Candidates examined and rejected.** This is the row where over-inclusion is
most tempting, because several further register rows mention the same nouns:

- `D-04`, "Verify GBrain repository and dependency posture" (L100). It names
  GBrain, but verifying a repository's licence, maintainers, and pinned version
  does not put GBrain *inside the release*; it is due diligence that precedes
  the `D-05` decision. `D-04` carries no gate anywhere in the ledger.
- `E-10`, "Publish historical-replay leakage policy" (L118), which governs how
  historical replay results may be represented. That is a disclosure obligation
  about claims, not the backtesting capability; the capability row is `E-05`,
  and `E-10` carries no gate.
- `E-01` (model-grade financial compute) and `E-02` (stress-test companies) —
  deferred Phase 3 scope the clause does not name.
- `E-08` (gate paid/public/personalized research on legal review) — distribution
  and legal gating, not one of the four named capabilities.

Coverage is complete in the other direction too: each of the four named
capabilities has at least one register row in the set, and every row in the set
is one of the four. Goal L233-235's no-padding rule is satisfied without leaving
a named capability unrepresented.

**Derived disposition.** `REQUIRED_NOW`, fixed by the rule rather than
aggregated (`:1546`, goal L261). Note that this is *not* the aggregation result:
all five related rows are `CONDITIONAL_UNACTIVATED`, so `RELATED_REGISTER_SCOPE`
would have produced `CONDITIONAL_UNACTIVATED`. The divergence is the point of the
rule.

**`authority_effect: null`** — required at `:1544` and goal L260.

**`activation_predicate: null`** — required at `:1545` and goal L261, and
consistent with goal L288-290's rule for `REQUIRED_NOW` components. A predicate
here would be a category error: there is no condition under which this
obligation switches on, because it is already on.

**`gate_refs: []`, reverse link closed.** Each of the five related registers
lists this clause: `REG-D-02.gate_refs == ['PG-1-11','PG-2-01','PG-2-02',
'PG-2-06']`, `REG-D-05.gate_refs == ['PG-1-11','PG-2-01','PG-2-05','PG-2-06']`,
and `REG-E-03`, `REG-E-05`, `REG-E-09` each `== ['PG-1-11']`. So `E-03`, `E-05`,
and `E-09` are reached by the §F scorecard through this clause alone — which is
another reason the five-row set may not be trimmed. `disposition_refs: []`.

**`primary_spec: null`** — pinned at `:2517`; the five related rows span S20,
S23, S25, and S04, so no single owning spec exists and related-register
ownership is the correct basis (goal L184).

**Applicable review slot.** This is a non-register canonical row, so
`validate_ledger_preimplementation.py:199-204` appends `SCOPE` to its checks and
`scope_derivation.semantic_review` is the slot this review fills. It is present,
non-`null`, `PENDING`, and carries exactly the 10-key `PENDING` set with no
role-binding keys.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `PG-1-11`'s scope derivation is correct at the input bytes pinned
above.
