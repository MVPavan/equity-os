# Inventory review — DISP-M-7 / SCOPE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-M-7` |
| `review_type` | `SCOPE` |
| `review_round` | `r0` |
| `role` | `REVIEWER` |
| `reviewer` | Reviewer-role subagent, session `a88da077-0dfc-49ab-bb1a-df4e8266291b` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `model` (actually invoked) | `claude-opus-5` |
| `effort` (actually invoked) | `high` |
| `timestamp` (UTC) | `2026-08-15T13:16:03Z` |

Role binding: `CONTEXT.md` "Agent roles (harness-wide)" binds `REVIEWER` to
Claude Opus 5 at high effort, in an agent and context independent of any
`IMPLEMENTER` that produced the reviewed content. The digest above is the
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
{"activation_predicate":null,"disposition_refs":["M-7"],"gate_refs":[],"related_register_ids":["C-17"],"scope_derivation":{"applicable_spec_ids":["S17"],"authority_effect":"ACTIVE_CONTROL","derived_program_disposition":"REQUIRED_NOW","related_register_ids":["C-17"],"rule":"AUTHORITATIVE_OCCURRENCE"}}
```

Digests observed at review time, **pre-record** (the recorder must recompute both
after its Phase A evidence append, per recording design r2 §3.4 — appending review
evidence mutates `evidence_refs` and therefore the input projection):

- `reviewed_input_sha256` (pre-record): `31c56cb44e4cb1629014a9eee921b62f4fd7992881457a9ed71d9abc2e50d023`
- `reviewed_inventory_sha256` (pre-record): `7c01745534c1af97189de1da212b73e9bf67046b48fa8b8839ac4f38c87b3516`

## Live source occurrence, re-read this round

`docs/blueprint/funda-third-order-review-disposition-report.md` lines 226-238, anchor
`M-7`, `source_title` "Entity and security master authority":

> ### M-7 — Entity and security master authority
>
> **Disposition: Accept, but do not use ISIN as the internal primary key.**
>
> Funda should use stable internal `company_id` and `security_id` values. ISIN, exchange symbol, CIN, LEI, and other identifiers are versioned external mappings with valid-time and knowledge-time intervals.
>
> The decision must name:
>
> - source hierarchy for each identifier type;
> - conflict-resolution rule;
> - symbol and listing changes;
> - corporate-action handling;
> - one real test case involving an identifier change.


Recomputed this round against current bytes:

- `source_hash` over the whole file → `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738`, equal to the stored value.
- `text_digest` over the normalized L226-238 span
  (CRLF-to-LF normalized, surrounding ASCII whitespace trimmed) →
  `90270f7df30c0860334933a72cf82cdc3e45ee2a28fe87cd601fad6114a486aa`, equal to the stored value.
- `required_acceptance_text` equals that normalized span byte for byte.
- Every `evidence_refs` object on this row was re-hashed against current bytes and
  matches its stored `content_sha256`.

## Reasoning

**Kind.** `### M-7 — Entity and security master authority`, ordinal `M-7`,
opening `**Disposition: Accept, but do not use ISIN as the internal primary
key.**`. `disposition_item`.

**Derivation rule.** `AUTHORITATIVE_OCCURRENCE` forced by kind (goal L242,
`validate_ledger_structural.py:1510`); `authority_effect` `ACTIVE_CONTROL` derives
`REQUIRED_NOW` (`:1558-1559`); `activation_predicate` `null` (goal L288-290).

**Applicable spec IDs.** `["S17"]`. The goal's 25-spec table lists S17's
disposition references as `M-7, 6.3`; no other spec lists `M-7`. Single spec, so
`primary_spec` is forced non-null (`:2473-2476`) and carries S17 ("Entity/security
master, relationships, and corporate actions") with the exact title and path.

**Related register IDs.** `["C-17"]` — a singleton whose register title, "Decide
entity/security master authority", is this component's `source_title` almost word
for word. `C-17`'s acceptance is "Stable internal company/security IDs; versioned
ISIN/symbol/CIN/LEI mappings; source hierarchy, conflicts, valid/knowledge time,
and one real identifier-change case tested" — which restates the clause's opening
decision and three of its five "must name" items.

**The candidate rejections here are load-bearing and are set out in full.** The
clause's "must name" list includes **"symbol and listing changes"** and
**"corporate-action handling"**, which are `C-06`'s subject ("Put authoritative
corporate actions in SQL — Splits, bonuses, rights, demergers, dividends, ticker
changes, and delistings are versioned events"), and it opens by treating external
identifiers as "versioned external mappings with valid-time and knowledge-time
intervals", which is `C-07`'s subject ("Put factual entity relationships in
bitemporal SQL … validity/knowledge intervals are represented"). Neither is
related. I examined whether that is an omission and concluded it is not, for three
reasons:

1. **The clause's grammatical subject is singular.** "**The decision** must name:
   …" — one decision, and that decision is `C-17`, the entity/security master
   authority decision. The clause constrains what `C-17` must contain; it does not
   constrain `C-06`'s or `C-07`'s own acceptance criteria.
2. **The register already routes the dependency.** In the pinned v2 register, both
   `C-06` and `C-07` name `C-17` as their sole Dependency. The clause therefore
   reaches corporate actions and bitemporal relationships *through* `C-17`'s
   authority, which is how the register itself models it — not as separate related
   scope.
3. **The two axes are contractually separate.** Goal L233-235: "`applicable_spec_ids`
   is artifact applicability and `related_register_ids` is source semantics;
   neither may be padded or inferred from the other." The corporate-action content
   does land in the applicable spec S17, which owns `C-06`, `C-07`, and `C-17`.
   Importing `C-06`/`C-07` into `related_register_ids` would be exactly the
   inference from artifact applicability that this sentence forbids.

Sibling check: `DISP-6-3` ("ISIN is an external identifier") carries the identical
`(["S17"], ["C-17"])` derivation and is the narrower ISIN-only occurrence, while
`M-7` is the broader "must name" occurrence. Two occurrences at two spans are
separately inventoried by design, and their sharing one related register is
consistent with the clause-subject reading above.

**Disposition and gate refs.** `disposition_refs == ["M-7"]`; `gate_refs == []`.

**Applicable review slot.** Non-register canonical row; `SCOPE` applies; the
`semantic_review` slot is present, `PENDING`, 10 keys, no role-binding keys.

**Residuals.** None.

---

**verdict: CLEAN**

This review authorizes no delivery, gate, approval, or transition. It records only
that `DISP-M-7`'s scope derivation is correct at the input bytes pinned above.
