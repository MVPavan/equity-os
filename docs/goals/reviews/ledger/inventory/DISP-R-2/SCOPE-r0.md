# Inventory review — DISP-R-2 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-R-2` |
| `review_type` | `SCOPE` |
| `review_round` | `r0` |
| `role` | `REVIEWER` |
| `reviewer` | Reviewer-role subagent, session `4e983789-a352-4ab6-9d42-4e7bdc2941f6` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `model` (actually invoked) | `claude-opus-5` |
| `effort` (actually invoked) | `high` |
| `timestamp` (UTC) | `2026-08-15T13:22:11Z` |

Role binding: `CONTEXT.md` "Agent roles (harness-wide)" L137-139 and L147 bind
`REVIEWER` to Claude Opus 5 at high effort, in an agent and context independent
of any `IMPLEMENTER` that produced the reviewed content. The digest above is the
`CONTEXT.md` bytes at review time and is an immutable historical capture.

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

Fresh structural validation at these exact bytes:
`python3 scripts/equity_os_blueprint/validate_ledger_structural.py --repo-root .`
→ exit `0` (run at review time). Every `evidence_refs` entry on this row was
additionally re-hashed by hand against its current target bytes this round and
matched.

## Reviewed inventory, exactly as read

`review_inventory_projection(row, "SCOPE")` — canonical JSON:

```json
{"activation_predicate":null,"disposition_refs":["R-2"],"gate_refs":[],"related_register_ids":["A-06"],"scope_derivation":{"applicable_spec_ids":["S09"],"authority_effect":"ACTIVE_CONTROL","derived_program_disposition":"REQUIRED_NOW","related_register_ids":["A-06"],"rule":"AUTHORITATIVE_OCCURRENCE"}}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 — appending
review evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `34350b141c63030330e4fb10c6e56407f641d9451a9a888e268428ac3462702e`
- `reviewed_inventory_sha256` (pre-record): `c94c509eb4f311b5a665a6556f5460ff8b976d96b683f732813467ab0aebef73`

## Live source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` lines 325-329, anchor `R-2`, title "Add filing channel and taxonomy version to A-06":

> ### R-2 — Add filing channel and taxonomy version to A-06
>
> **Disposition: Accept.**
>
> The XBRL/PDF spike should explicitly distinguish exchange quarterly-result XBRL, annual channels, issuer documents, and taxonomy/version changes. The spike should measure mapping stability, not merely field coverage.

- `source_hash` recomputed over the whole file → `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738`, matching the row.
- `text_digest` recomputed over the normalized L325-329 span (`\n`-joined,
  surrounding ASCII whitespace trimmed) → `3d0a31e472130586bd54f8bdb7b1ffd37c617d6067cf628d24d982e0125fa0d8`, matching the row.
- `required_acceptance_text` equals that normalized span byte for byte
  (checked by comparison, not by eye).
- The crosswalk for this row is pinned by the structural validator at
  `validate_ledger_structural.py:2427-2479` (`EXPECTED_DISPOSITION_CROSSWALK`),
  which fixes `applicable_spec_ids` and `related_register_ids` and derives the
  `primary_spec` shape from the spec count.

## Reasoning

**Kind.** A numbered finding of §5 "Calls to amend or reverse", ordinal `R-2`,
with an explicit `**Disposition: Accept.**` line. `disposition_item` is correct;
the §5 heading changes the finding's purpose (amendment request) but not its
inventory kind, which is fixed by the shape of the occurrence.

**Derivation rule.** `AUTHORITATIVE_OCCURRENCE` (goal L237-245;
`validate_ledger_structural.py:1510`), `applicable_spec_ids` present as the only
kind-specific key (`:1502`).

**Authority effect.** `ACTIVE_CONTROL`. A call to amend that is accepted is a
live obligation on the amended row; `REJECTED_PROPOSAL` is what the sibling
`DISP-R-1` carries, where the same section's disposition line reads "Reject".

**Related register IDs.** `["A-06"]`, and the single-row answer is the right one.
The clause names A-06 in its own title, and the pinned v2 register's A-06 row
(L36) already carries the amendment: "Coverage matrix by company, quarter,
**filing channel, taxonomy/version**, statement, segment, note, ownership/share
count, restatement behavior, **mapping stability**, and reconciliation effort."
Both of the clause's demands — distinguish the channel classes and the taxonomy
version; measure mapping stability rather than field coverage — are present in
that one row and in no other. Nothing here controls A-02 (the discovery-company
selection that A-06 depends on), so adding it would pad the list.

**Applicable spec IDs and `primary_spec`.** `["S09"]`, matching REG-A-06's own
owning spec. Exactly one spec ID, so `primary_spec` must be the object form
(`validate_ledger_structural.py:2474-2476`), and it is: S09, path
`docs/specs/equity-os-s09-filing-ingestion-point-in-time-capture.md`. The
HR-0004 migration correctly left it alone — this row's only
`AUTHORITY_RECONCILIATION` entry touches `human_review_id`, not `primary_spec`.

**Distinctness from the sequence inventory.** `SEQ-03` (report L453, "A-02 and
A-06: select the discovery company … and run the channel-aware XBRL/PDF spike")
also concerns A-06. It is a different occurrence at a different span, inventoried
as a `sequence_clause` carrying `source_register_ids ["A-02","A-06"]`. Two
occurrences, two rows: correct under a contract that inventories exact
occurrences.

**Blocked state does not touch scope.** This row is `REVIEW_BLOCKED` with the
upheld load-bearing Important finding `S09-r3-N1` open, and `review_round` is 4.
Those fields sit in `review_input_projection`, not in the `SCOPE` inventory
projection, and none of them alters the derivation: blocking is delivery state,
not disposition. `activation_predicate` is still `null`, which is required for a
`REQUIRED_NOW` component regardless of blocking (goal L288-290). This review
neither clears nor weakens that blocker.

**Refs and slot.** `disposition_refs == ["R-2"]`; `gate_refs == []` (register-only
field, `:2660-2664`); the applicable review slot is
`scope_derivation.semantic_review`, present and `PENDING`.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `DISP-R-2`'s scope derivation is correct at the input bytes pinned above.
