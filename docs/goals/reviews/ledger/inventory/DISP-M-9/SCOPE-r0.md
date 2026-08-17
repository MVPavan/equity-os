# Inventory review — DISP-M-9 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-M-9` |
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
{"activation_predicate":null,"disposition_refs":["M-9"],"gate_refs":[],"related_register_ids":["A-08","B-08"],"scope_derivation":{"applicable_spec_ids":["S07","S09"],"authority_effect":"ACTIVE_CONTROL","derived_program_disposition":"REQUIRED_NOW","related_register_ids":["A-08","B-08"],"rule":"AUTHORITATIVE_OCCURRENCE"}}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 — appending
review evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `0859b908b24771e29ddb5013c779c38d7423b89028dbce7b754803e3e399df97`
- `reviewed_inventory_sha256` (pre-record): `ec5cd9173fa87f2f627a63fcdf122c6e4de5085d1f34f7d63c38f98271336800`

## Live source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` lines 252-262, anchor `M-9`, title "Untrusted-document surface":

> ### M-9 — Untrusted-document surface
>
> **Disposition: Accept.**
>
> Add explicit failure and test cases for document text being treated as instructions. The operational controls are:
>
> - source content is data, not control text;
> - retrieved text cannot change tools, permissions, cutoffs, or promotion rules;
> - memory drafts show provenance at promotion time;
> - no document-originated instruction can invoke execution or secrets;
> - prompt-injection and source-confusion cases enter the golden set.

- `source_hash` recomputed over the whole file → `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738`, matching the row.
- `text_digest` recomputed over the normalized L252-262 span (`\n`-joined,
  surrounding ASCII whitespace trimmed) → `4271ab940f3e90d9d2ad320339c64bebbd3ae32ccf82f6b020be9b8bf521ee74`, matching the row.
- `required_acceptance_text` equals that normalized span byte for byte
  (checked by comparison, not by eye).
- The crosswalk for this row is pinned by the structural validator at
  `validate_ledger_structural.py:2427-2479` (`EXPECTED_DISPOSITION_CROSSWALK`),
  which fixes `applicable_spec_ids` and `related_register_ids` and derives the
  `primary_spec` shape from the spec count.

## Reasoning

**Kind.** A numbered §3 merits finding with ordinal `M-9` and an explicit
`**Disposition: Accept.**` line — `disposition_item`, on the same test applied
to its neighbour M-8.

**Derivation rule.** `AUTHORITATIVE_OCCURRENCE`, forced by kind (goal L237-245;
`validate_ledger_structural.py:1510`), with the kind's one extra key
`applicable_spec_ids` present and nothing else (`:1502`).

**Authority effect.** `ACTIVE_CONTROL`: "Disposition: Accept", and the body then
states five operational controls in the imperative. Deriving `REQUIRED_NOW`
directly is right, and it matches both stored disposition fields.

**Related register IDs.** `["A-08","B-08"]`, verified against the pinned v2
register. A-08 ("Appoint golden-test-set owner", register L38) ends its
acceptance text with "first twenty labeled cases, **including
prompt-injection/source-confusion cases**" — that is this clause's fifth bullet
folded into the register. B-08 ("Record failure taxonomy", register L58)
enumerates "cutoff leakage, source-confusion, and **document-as-instruction**
failures categorized" — that is the clause's "explicit failure … cases" demand
folded in. Those are the only two register rows whose text this occurrence
changed; no other row was amended by M-9.

**Applicable spec IDs.** `["S07","S09"]`, and this is the row in the batch where
the two arrays are most visibly independent: both related register rows are owned
by S07 (REG-A-08 → S07, REG-B-08 → S07), so S09 cannot have been derived from
them. S09 is filing ingestion and immutable documents — the artifact where
untrusted documents actually enter the system, hence artifact applicability. That
is precisely the goal's rule that `applicable_spec_ids` is artifact applicability
and `related_register_ids` is source semantics, and that "neither may be padded
or inferred from the other". Both were independently derived here.

**`primary_spec`.** `null`, forced by the two-spec case
(`validate_ledger_structural.py:2474-2479`); `TR-DISP-M-9-002` cleared the
earlier S07 object under `HRD-0004-001`.

**Disposition and gate refs, predicate.** `disposition_refs == ["M-9"]`
self-identifies; `gate_refs == []` (register-only field, `:2660-2664`);
`activation_predicate == null` as required for `REQUIRED_NOW` (goal L288-290).

**Applicable review slot.** Non-register canonical row, so `SCOPE` applies
(`validate_ledger_preimplementation.py:200-204`) and
`scope_derivation.semantic_review` is this review's slot; it is `PENDING` with
the exact 10-key set.

**Consistency cross-check.** `DISP-M-9` is one of the 25 components pinned in
`EXPECTED_COMMAND_PROOF_COMPONENTS` (`:2635-2649`). That is an evidence-side
fact, not a scope field, but it corroborates the derivation: a clause demanding
"explicit failure and test cases" is executable scope, unlike its neighbour M-8.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `DISP-M-9`'s scope derivation is correct at the input bytes pinned above.
