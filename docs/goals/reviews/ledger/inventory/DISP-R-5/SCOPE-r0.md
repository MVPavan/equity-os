# Inventory review — DISP-R-5 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-R-5` |
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
{"activation_predicate":null,"disposition_refs":["R-5"],"gate_refs":[],"related_register_ids":["B-01","B-03"],"scope_derivation":{"applicable_spec_ids":["S10","S14"],"authority_effect":"ACTIVE_CONTROL","derived_program_disposition":"REQUIRED_NOW","related_register_ids":["B-01","B-03"],"rule":"AUTHORITATIVE_OCCURRENCE"}}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 — appending
review evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `eead4a15af67e3d9339bd4a64c9a007355a040d6e665516f1a6e58a46b19b212`
- `reviewed_inventory_sha256` (pre-record): `33fd8b518c380a07bc94acb6f4f85ec1ca59c9e7af87f06249d5e6fd7744c8cd`

## Live source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` lines 343-347, anchor `R-5`, title "Predefine the SQLite migration trigger":

> ### R-5 — Predefine the SQLite migration trigger
>
> **Disposition: Retain as an operational note, not a new critical decision.**
>
> SQLite remains appropriate for the vertical slice and small pilot. Record migration triggers in the storage ADR, such as persistent writer contention, multi-user remote access, reliability requirements, or operational complexity that exceeds a single-writer design.

- `source_hash` recomputed over the whole file → `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738`, matching the row.
- `text_digest` recomputed over the normalized L343-347 span (`\n`-joined,
  surrounding ASCII whitespace trimmed) → `6daaa2ec9c49ca7a3d30edc5de92911e214dce90c2d4b6d0128d1543be7426c1`, matching the row.
- `required_acceptance_text` equals that normalized span byte for byte
  (checked by comparison, not by eye).
- The crosswalk for this row is pinned by the structural validator at
  `validate_ledger_structural.py:2427-2479` (`EXPECTED_DISPOSITION_CROSSWALK`),
  which fixes `applicable_spec_ids` and `related_register_ids` and derives the
  `primary_spec` shape from the spec count.

## Reasoning

**Kind.** Numbered §5 amendment finding, ordinal `R-5`, with an explicit
`**Disposition:**` line — `disposition_item`.

**Derivation rule.** `AUTHORITATIVE_OCCURRENCE` forced by kind (goal L237-245;
`validate_ledger_structural.py:1510`); `applicable_spec_ids` present as the only
extra key (`:1502`).

**Authority effect — the judgment this row turns on.** The disposition line is
"Retain as an operational note, **not a new critical decision**", which reads at
first like a refusal. `ACTIVE_CONTROL` is nevertheless correct, and
`REJECTED_PROPOSAL` would be wrong. What is refused is the *form* the reviewer
asked for — a new critical register decision — not the substance: the clause then
issues a live imperative, "Record migration triggers in the storage ADR", and
names four of them. A `REJECTED_PROPOSAL` disposition derives
`REJECTED_ACCOUNTED` and requires a `rejection_record`; this row has
`rejection_record == null` and is `REQUIRED_NOW`, which is the coherent reading.
The program's only genuine `REJECTED_PROPOSAL` is `DISP-R-1`, whose disposition
line is a bare "Reject".

**Related register IDs.** `["B-01","B-03"]`, checked against the pinned register.
B-03 ("Establish source-of-truth matrix … Approved authority table for raw
documents, SQL facts, claims, calculations, narrative memory, derivative indices,
evidence packages, and reports", register L53) is the row that owns storage
authority, hence the storage ADR the clause writes into. B-01 ("Implement fixed,
resumable earnings-review workflow", register L51) is the single-writer design
the triggers are about — the clause's own words are "persistent writer
contention" and "operational complexity that exceeds a **single-writer design**".
Both are genuinely controlled; neither is padding.

**Applicable spec IDs and `primary_spec`.** `["S10","S14"]` pair one-to-one with
the owning specs of those two rows (REG-B-03 → S10, REG-B-01 → S14). Two spec
IDs, so `primary_spec` must be `null` (`:2474-2479`), and `TR-DISP-R-5-005`
cleared the earlier S10 object under `HRD-0004-001`. The same migration also
re-sorted `related_register_ids` from `["B-03","B-01"]` to `["B-01","B-03"]`
(`TR-DISP-R-5-006`) to satisfy the goal's sorted-and-unique array rule; the
current stored value is sorted and unique.

**Fold-in cross-check.** The four triggers this clause demands are present in the
pinned v2 register under "### Reconsider SQLite when" (register L196-200) and are
separately inventoried as `SCALE-SQLITE-01`…`04`, each a `scale_trigger` carrying
`disposition_refs ["R-5"]` — a pairing the structural validator pins directly
(`:2506`). Those rows inventory the register-side trigger clauses;
`DISP-R-5` inventories the disposition-report occurrence that ordered them. Four
`scale_trigger` rows plus one `disposition_item` is the correct decomposition,
not a five-fold duplicate.

**Blocked state.** `REVIEW_BLOCKED`, `review_round` 4, open load-bearing finding
`R3-F-01`. Those fields are outside the `SCOPE` projection and do not alter the
derivation; `activation_predicate` remains `null` as `REQUIRED_NOW` requires.

**Refs and slot.** `disposition_refs == ["R-5"]`; `gate_refs == []`
(register-only, `:2660-2664`); `scope_derivation.semantic_review` is the
applicable slot, present and `PENDING`.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `DISP-R-5`'s scope derivation is correct at the input bytes pinned above.
