# Inventory review — DISP-M-8 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-M-8` |
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
{"activation_predicate":null,"disposition_refs":["M-8"],"gate_refs":[],"related_register_ids":["A-13","C-18"],"scope_derivation":{"applicable_spec_ids":["S08","S18"],"authority_effect":"ACTIVE_CONTROL","derived_program_disposition":"REQUIRED_NOW","related_register_ids":["A-13","C-18"],"rule":"AUTHORITATIVE_OCCURRENCE"}}
```

Digests observed at review time, **pre-record** (the recorder must recompute
both after its Phase A evidence append, per recording design r2 §3.4 — appending
review evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `283ce39d9a0b4ce4f556385dd417db966e5c66b95329d868352cd6a1d4db2065`
- `reviewed_inventory_sha256` (pre-record): `541bb3fa523944929828f15756b1a4b4dec1f527a4c034115766c531e1c3c4c7`

## Live source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` lines 240-250, anchor `M-8`, title "Results-season throughput":

> ### M-8 — Results-season throughput
>
> **Disposition: Accept and fold into the success-metric contract.**
>
> Coverage capacity during clustered reporting periods is a product constraint. It need not become a separate architecture subsystem, but the register should track:
>
> - reports reviewable per analyst per week;
> - peak-week document and claim volume;
> - backlog age;
> - percent of updates completed before the next material event;
> - capacity at the selected Phase 1 company count.

- `source_hash` recomputed over the whole file → `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738`, matching the row.
- `text_digest` recomputed over the normalized L240-250 span (`\n`-joined,
  surrounding ASCII whitespace trimmed) → `671b7ce1b3059934ba4fda735adb70538afeb9c33015d328b6bb70beccfd69bb`, matching the row.
- `required_acceptance_text` equals that normalized span byte for byte
  (checked by comparison, not by eye).
- The crosswalk for this row is pinned by the structural validator at
  `validate_ledger_structural.py:2427-2479` (`EXPECTED_DISPOSITION_CROSSWALK`),
  which fixes `applicable_spec_ids` and `related_register_ids` and derives the
  `primary_spec` shape from the spec count.

## Reasoning

**Kind.** The occurrence is a numbered finding of the disposition report's §3
merits audit, carrying its own heading ordinal `M-8` and an explicit
`**Disposition:**` line. That is exactly what `disposition_item` inventories.
It is not an `authority_clause` (it allocates no authority between documents),
not a `document_strategy_clause` (§9 owns those, L468-475), and not a
`sequence_clause` (§8 owns those, L451-462).

**Derivation rule.** `AUTHORITATIVE_OCCURRENCE` is forced by kind — goal L237-245
kind→rule table, mechanized at `validate_ledger_structural.py:1510`
(`required_rule_by_kind`) — and the kind-specific extra key `applicable_spec_ids`
is likewise forced (`:1502`). Both are present and no other key is.

**Authority effect.** `ACTIVE_CONTROL` is right. The disposition line reads
"Accept and fold into the success-metric contract": an accepted finding that
imposes a live obligation. The contrasting values are exercised elsewhere in the
same closed set — `DISP-R-1` (report L309-323, "Disposition: Reject") is the
program's only `REJECTED_PROPOSAL`. `ACTIVE_CONTROL` derives `REQUIRED_NOW`
directly (goal L~255-259) without aggregating related rows, and the stored
`derived_program_disposition` and `program_disposition` both read `REQUIRED_NOW`.

**Related register IDs.** `["A-13","C-18"]` are the two rows this occurrence
controls, and I checked both against the pinned v2 register bytes. A-13 ("Freeze
success-metric contract", register L43) is literally the contract the clause
folds into. C-18 ("Validate results-season throughput", register L89) states the
register-side restatement of the clause's five bullets — "Peak-week reviews per
analyst, claim/document volume, backlog age, and completion capacity for the
Phase 1 universe". No third row belongs: the clause explicitly declines to create
architecture scope ("It need not become a separate architecture subsystem"), so
no B-series implementation row is in its cone.

**Applicable spec IDs and `primary_spec`.** `["S08","S18"]` pair one-to-one with
the owning specs of the two related rows (REG-A-13 → S08, REG-C-18 → S18);
neither array is padded from the other. Because two spec IDs are present,
`primary_spec` must be `null` (`validate_ledger_structural.py:2474-2479`). The
transition history shows the HR-0004 migration doing exactly that:
`TR-DISP-M-8-002` cleared the earlier S08 `primary_spec` object under
`HRD-0004-001`. The current value is `null`, as required.

**Disposition and gate refs.** `disposition_refs == ["M-8"]` is the row's
self-identification with its own finding ordinal. `gate_refs == []` is correct:
`gate_refs` is populated only on register rows through the `gate_map` equality at
`validate_ledger_structural.py:2660-2664`, and all 109 non-register canonical
rows carry `[]`.

**Activation predicate.** `null`, required for a `REQUIRED_NOW` component
(goal L288-290).

**Applicable review slot.** `DISP-M-8` is a non-register canonical row, so
`validate_ledger_preimplementation.py:200-204` appends `SCOPE` to its checks and
`scope_derivation.semantic_review` is the slot this review fills. It is present,
non-`null`, `PENDING`, and carries exactly the 10-key `PENDING` set.

**Occurrence-versus-restatement check.** `ALIAS-001` (L16-18), `ALIAS-012` (L35)
and `ALIAS-033` (L430) all resolve to `DISP-M-8`. They are derivative
restatements at other spans; the authoritative occurrence remains L240-250, which
is what this row anchors. That separation is correct and not a duplicate
inventory.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records
only that `DISP-M-8`'s scope derivation is correct at the input bytes pinned above.
