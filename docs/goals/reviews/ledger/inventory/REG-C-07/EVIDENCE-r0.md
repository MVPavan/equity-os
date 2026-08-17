# Inventory review — REG-C-07 — EVIDENCE — r0

**Verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| Component ID | `REG-C-07` |
| Review type | `EVIDENCE` |
| Round | `r0` |
| Reviewer | Reviewer role (CONTEXT.md "Agent roles (harness-wide)"), Claude Code session `8958a695-f635-4f4e-8747-5433095fbc1a` |
| Role | `REVIEWER` |
| Role binding path | `CONTEXT.md` |
| Role binding SHA-256 at review time | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| Model actually invoked | `claude-opus-5` |
| Effort actually invoked | `high` |
| Review UTC | `2026-08-16T13:45:24Z` |
| Batch | 17 (`register_row`, owning specs S15–S18) per recording design r2 §5.2 |

## Input hashes read at review time

| Input | Path | SHA-256 |
|---|---|---|
| Active goal | `docs/goals/equity-os-blueprint-completion.md` | `f15f7ab5a4e425dec3877ab7f1f7594687979060e4dbcd49390a8a8d5fedb85f` |
| Canonical ledger | `docs/goals/equity-os-blueprint-component-ledger.jsonl` | `de236d7e8dcf02e307ec58797f5722ae2f85d1d8cdba57d4ecc07df5383c9c97` |
| Pinned decision register v2 | `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` | `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164` |
| Third-order disposition report | `docs/blueprint/funda-third-order-review-disposition-report.md` | `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738` |
| Structural validator | `scripts/equity_os_blueprint/validate_ledger_structural.py` | `731d0d8b208b577967c92e3992e7ec1a4333cdecbf89f6951c32d2ec469436f9` |
| Preimplementation validator | `scripts/equity_os_blueprint/validate_ledger_preimplementation.py` | `f7a225a1f99cb85c92cde3094505a92a746552280eb45dae0253a71ab9048013` |
| Human-review artifact | `docs/goals/equity-os-blueprint-human-review-needed.md` | `094fcdfab74a3f4c6fdb82b1520fc4d13b636ac0e9ed10194e5d607aed2ce9af` |
| Role binding | `CONTEXT.md` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |

Fresh at these bytes: `extract_goal_validators.py --check` exit `0`;
`validate_ledger_structural.py --repo-root .` exit `0`.

## Applicability

`REG-C-07.kind == "register_row"`; `scope_derivation.semantic_review` is `null`
(verified on the row; goal L208-211). `EVIDENCE` and `APPROVAL` only; no
`SCOPE` artifact.

## Live source occurrence (pinned authority)

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md:78`,
section **C. Phase 1 — Evidence-grounded MVP**, register ID `C-07`, status
`Open`, priority `High`:

> | C-07 | High | Put factual entity relationships in bitemporal SQL | Parent/subsidiary, management roles, ownership, cross-holdings, and validity/knowledge intervals are represented | C-17 | Open |

Recomputed `UTF8_LINE_SPAN` digest of line 78:
`5ec77db809de78a1c4ad17ab753cebda7965bfb3915744d939940abf0e578ceb` — equals
`text_digest` and `EV-REG-C-07-SOURCE.content_sha256`. `required_acceptance_text`
is byte-identical to the acceptance cell.

## Reviewed inventory, exactly as read

`required_evidence` (2 items):

| `evidence_id` | `evidence_type` | `proof_mode` | `status` | `approval_ids` |
|---|---|---|---|---|
| `REQ-REG-C-07-ACCEPTANCE` | `ARTIFACT` | `CONTENT_HASH` | `UNRESOLVED` | `[]` |
| `REQ-REG-C-07-SPEC-REVIEW` | `REVIEW` | `CONTENT_HASH` | `UNRESOLVED` | `[]` |

- `…-ACCEPTANCE.description` = "Current proof satisfying: Parent/subsidiary,
  management roles, ownership, cross-holdings, and validity/knowledge intervals
  are represented".
- `…-SPEC-REVIEW` scope = "C-07 under S17: Put factual entity relationships in
  bitemporal SQL".

`evidence_refs` (2): `EV-REG-C-07-SOURCE` (`UTF8_LINE_SPAN`, register v2:78,
`2026-08-13T02:49:11Z`) and `EV-REG-C-07-SPEC-DRAFT` (`FILE_BYTES`,
`docs/specs/equity-os-s17-entity-security-master-actions.md`,
`dbb6b8600de771e9ae668208a9893394321ce67fb366c706c2d9c98985ee85aa`,
`2026-08-15T07:13:28Z`). Both recomputed: current. (This spec file is shared
with `REG-C-06` and `REG-C-17`; each row holds its own distinct
`evidence_ref_id`, so global uniqueness at goal L476 is preserved.)

`verification_command` = `{"mode": "UNRESOLVED", "commands": [],
"not_applicable_review": null}`.

## Reasoning

1. **Clause decomposition.** Five things must be "represented":
   parent/subsidiary structure, management roles, ownership, cross-holdings,
   and validity/knowledge intervals. All five are carried verbatim in
   `REQ-REG-C-07-ACCEPTANCE.description`.

2. **The fifth conjunct is the substantive one.** "Validity/knowledge intervals"
   is the bitemporality requirement in the row title made explicit in the
   acceptance text — the relationship store must carry both valid time and
   knowledge time. Because the clause names it, it is inside the enumerated
   obligation and cannot be quietly dropped at delivery. That is exactly what
   this review must confirm, and it holds.

3. **Proof mode.** "Are represented" is a schema/representation obligation; the
   proof is the schema and populated store bound by content hash, so
   `ARTIFACT`/`CONTENT_HASH` is correct.

4. **Is executable proof demanded here?** No. The clause has no test,
   demonstration, or replay verb. Two nearby rows show where the program does
   put executable proof for temporal correctness, and both are enumerated:
   - knowledge-time *enforcement* is `C-15` ("SQL/document/memory retrieval
     applies `knowledge_time <= cutoff` … tests insert and reject post-cutoff
     records") with gate `PG-1-05`, and disposition `M-4`; `REG-C-15`,
     `PG-1-05` and `DISP-M-4` are all members of the goal's closed
     `EXPECTED_COMMAND_PROOF_COMPONENTS` set (goal L3989-3996; validator
     `:2635`, asserted `:2649`);
   - the identifier-change test is `C-17`, also a member, which C-07 declares as
     its sole dependency.
   `REG-C-07` is correctly absent from that set: representing intervals is not
   the same obligation as proving retrieval honours them.

5. **Disposition cross-check.** `disposition_refs` are `M-7` and `6.3` — the
   same pair as `C-06`, and for the same reason: M-7 (report L226-238) sets the
   entity-master authority and its bullets are obligations of the *decision*
   (C-17), while §6.3 (L363-365) rules ISIN out as an internal primary key.
   Both are separately ledgered — `DISP-M-7` with `ACCEPTANCE` + `COMMAND-PROOF`,
   `DISP-6-3` with `ACCEPTANCE` (verified) — so nothing they require is
   unenumerated program-wide, and register v2's Authority rule (L23) keeps them
   from adding to C-07's acceptance cell.

6. **Consistency with C-06, checked deliberately rather than assumed.** C-06 and
   C-07 are adjacent register lines with the same two-item inventory. I
   confirmed this is driven by clause grammar — both end in a representation
   predicate ("are versioned events" / "are represented"), neither names an
   authority or a test — and not by copying: their descriptions differ, their
   evidence-ref IDs differ, and their priorities differ (`Critical` vs `High`).

7. **`gate_refs` = `[]`; `verification_command` = `UNRESOLVED`** (valid during
   initial ledger construction, goal L500-502). No gate names C-07, so there is
   no gate-side proof demand to reconcile.

No omission found.

## Verdict

verdict: CLEAN
