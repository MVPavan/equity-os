# Inventory review — DISP-R-4 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-R-4` |
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
{"activation_predicate":null,"disposition_refs":["R-4"],"gate_refs":[],"related_register_ids":["A-04"],"scope_derivation":{"applicable_spec_ids":["S06"],"authority_effect":"ACTIVE_CONTROL","derived_program_disposition":"REQUIRED_NOW","related_register_ids":["A-04"],"rule":"AUTHORITATIVE_OCCURRENCE"}}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 — appending
review evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `9ee3c78b356b9d624a71ea6dd1bfff1fcb32909f858f14538bf067ea9b456788`
- `reviewed_inventory_sha256` (pre-record): `0d191cdacfd4e4a033bc94be2fd556984df92a61acb362e2f2a2da474968a145`

## Live source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` lines 337-341, anchor `R-4`, title "Add observable falsifiers":

> ### R-4 — Add observable falsifiers
>
> **Disposition: Accept.**
>
> The output contract should state what observable event, metric, management outcome, or evidence would materially weaken or reverse the current thesis. This is distinct from listing generic risks.

- `source_hash` recomputed over the whole file → `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738`, matching the row.
- `text_digest` recomputed over the normalized L337-341 span (`\n`-joined,
  surrounding ASCII whitespace trimmed) → `5b47fb8bb6e04161603fe15b37b17c534201e957fc53f6d8212dbb83180cee07`, matching the row.
- `required_acceptance_text` equals that normalized span byte for byte
  (checked by comparison, not by eye).
- The crosswalk for this row is pinned by the structural validator at
  `validate_ledger_structural.py:2427-2479` (`EXPECTED_DISPOSITION_CROSSWALK`),
  which fixes `applicable_spec_ids` and `related_register_ids` and derives the
  `primary_spec` shape from the spec count.

## Reasoning

**Kind.** Numbered §5 amendment finding, ordinal `R-4`, explicit
`**Disposition: Accept.**` — `disposition_item`.

**Derivation rule.** `AUTHORITATIVE_OCCURRENCE` (goal L237-245;
`validate_ledger_structural.py:1510`), with `applicable_spec_ids` as the only
kind-specific key (`:1502`).

**Authority effect.** `ACTIVE_CONTROL`; derives `REQUIRED_NOW` directly, and both
stored disposition fields read `REQUIRED_NOW`.

**Related register IDs.** `["A-04"]`, and the pinned register proves the fold-in
directly: A-04 ("Freeze the first output contract", register L34) lists the
contract's contents as "event/cutoff, facts, changes, driver analysis, management
ledger, thesis impact, **observable falsifiers**, open questions, calculations,
memory draft, and approval record". The clause's demand appears there verbatim
as a named contract element, and in no other register row. A-03 (the manual
baseline A-04 depends on for its final freeze) is not controlled by this clause
and is correctly absent.

**Applicable spec IDs and `primary_spec`.** `["S06"]`, matching REG-A-04's owning
spec (output contract, materiality, falsifiers). Single spec, so `primary_spec`
is the object form (`:2474-2476`): S06,
`docs/specs/equity-os-s06-output-materiality-falsifiers.md`. HR-0004 left it in
place; this row's `AUTHORITY_RECONCILIATION` entry touches `human_review_id`
only.

**Distinctness from the sequence inventory.** `SEQ-07` (report L457, "A-04 final:
freeze the first-release contract, **including falsifiers** and artifact-hash
approval") also names falsifiers. It is a separate occurrence inventoried as a
`sequence_clause` with `source_register_ids ["A-04"]`, and it carries sequencing
semantics — when the freeze happens — where `DISP-R-4` carries the content demand.
Two occurrences, two rows, no duplication.

**Blocked state does not touch scope.** The row is `REVIEW_BLOCKED` at
`review_round` 4 with the open load-bearing finding `S06-I7`. Those fields are in
the input projection, not the `SCOPE` inventory projection, and blocking is
delivery state rather than disposition; `activation_predicate` stays `null` as
`REQUIRED_NOW` requires (goal L288-290). This review does not touch the blocker.

**Refs and slot.** `disposition_refs == ["R-4"]`; `gate_refs == []` (register-only,
`:2660-2664`); `scope_derivation.semantic_review` is the applicable slot, present
and `PENDING`.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `DISP-R-4`'s scope derivation is correct at the input bytes pinned above.
