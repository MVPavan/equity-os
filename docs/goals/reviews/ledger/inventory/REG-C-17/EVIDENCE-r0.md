# Inventory review — REG-C-17 — EVIDENCE — r0

**Verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| Component ID | `REG-C-17` |
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

`REG-C-17.kind == "register_row"`; `scope_derivation.semantic_review` is `null`
(verified on the row; goal L208-211). `EVIDENCE` and `APPROVAL` only; no
`SCOPE` artifact.

## Live source occurrence (pinned authority)

`docs/blueprint/funda-blueprint-implementation-decision-register-v2.md:88`,
section **C. Phase 1 — Evidence-grounded MVP**, register ID `C-17`, status
`Open`, priority `High`:

> | C-17 | High | Decide entity/security master authority | Stable internal company/security IDs; versioned ISIN/symbol/CIN/LEI mappings; source hierarchy, conflicts, valid/knowledge time, and one real identifier-change case tested | A-05, A-06 | Open |

Recomputed `UTF8_LINE_SPAN` digest of line 88:
`f67d3ec8671dfec9073d33fee4c0f79f1780138bb60f8a42f1546f4fe30aaa01` — equals
`text_digest` and `EV-REG-C-17-SOURCE.content_sha256`. `required_acceptance_text`
is byte-identical to the acceptance cell.

## Reviewed inventory, exactly as read

`required_evidence` (4 items — the largest in this batch):

| `evidence_id` | `evidence_type` | `proof_mode` | `status` | `approval_ids` |
|---|---|---|---|---|
| `REQ-REG-C-17-ACCEPTANCE` | `ARTIFACT` | `CONTENT_HASH` | `UNRESOLVED` | `[]` |
| `REQ-REG-C-17-SPEC-REVIEW` | `REVIEW` | `CONTENT_HASH` | `UNRESOLVED` | `[]` |
| `REQ-REG-C-17-DOMAIN_EXPERT_ACCEPTANCE` | `DOMAIN` | `TYPED_APPROVAL` | `UNRESOLVED` | `["APR-REG-C-17-02"]` |
| `REQ-REG-C-17-COMMAND-PROOF` | `COMMAND_RESULT` | `COMMAND` | `UNRESOLVED` | `[]` |

- `…-ACCEPTANCE.description` = "Current proof satisfying: Stable internal
  company/security IDs; versioned ISIN/symbol/CIN/LEI mappings; source
  hierarchy, conflicts, valid/knowledge time, and one real identifier-change
  case tested".
- `…-SPEC-REVIEW` scope = "C-17 under S17: Decide entity/security master
  authority".
- `…-DOMAIN_EXPERT_ACCEPTANCE.description` = "Current DOMAIN_EXPERT_ACCEPTANCE
  evidence from Entity-data authority".
- `…-COMMAND-PROOF.description` = "Reproducible command result proving the
  current REG-C-17 acceptance obligation", scope "REG-C-17 command proof".

`evidence_refs` (2): `EV-REG-C-17-SOURCE` (`UTF8_LINE_SPAN`, register v2:88,
`2026-08-13T02:49:11Z`) and `EV-REG-C-17-SPEC-DRAFT` (`FILE_BYTES`,
`docs/specs/equity-os-s17-entity-security-master-actions.md`,
`dbb6b8600de771e9ae668208a9893394321ce67fb366c706c2d9c98985ee85aa`,
`2026-08-15T07:13:28Z`). Both recomputed: current.

`verification_command` = `{"mode": "UNRESOLVED", "commands": [],
"not_applicable_review": null}`.

## Reasoning

1. **Clause decomposition — three proof kinds in one cell.** (a) A *decision*
   about which identifiers are authoritative, with stable internal IDs,
   versioned external mappings, source hierarchy, conflict handling, and
   valid/knowledge time; (b) that decision is an act of data-domain authority;
   (c) "one real identifier-change case **tested**" — an execution.

2. **All three are enumerated, and this row is the batch's clearest case of a
   clause that would be under-proven by a single artifact item.**
   - (a) → `REQ-REG-C-17-ACCEPTANCE`, `ARTIFACT`/`CONTENT_HASH`, carrying the
     acceptance text verbatim.
   - (b) → `REQ-REG-C-17-DOMAIN_EXPERT_ACCEPTANCE`, `DOMAIN`/`TYPED_APPROVAL`,
     naming component-local `APR-REG-C-17-02` (verified in this row's
     `required_approvals`) — the typed-approval path the goal requires for
     domain evidence (L487-490) with the linkage rule at L484-487 satisfied.
   - (c) → `REQ-REG-C-17-COMMAND-PROOF`, `COMMAND_RESULT`/`COMMAND`, the only
     classification the schema offers for a tested case (goal L476-484;
     `evidence_type == "COMMAND_RESULT"` forces `proof_mode == "COMMAND"` at
     goal L3484-3486).

3. **The `COMMAND` item is a remediated gap, worth recording.** The r0
   program-level evidence-inventory review
   (`equity-os-blueprint-evidence-inventory-r0.md`, Critical finding 2) named
   `REG-C-17` among ten register rows whose explicit test obligation had no
   command evidence, when zero of the ledger's requirements used `COMMAND`. At
   the bytes I read, `REQ-REG-C-17-COMMAND-PROOF` exists, and `REG-C-17` is a
   member of the goal's closed `EXPECTED_COMMAND_PROOF_COMPONENTS` set
   (L3989-3996; validator `:2635`, asserted `:2649`). The finding is closed on
   this row.

4. **Disposition M-7 — checked for an unenumerated obligation, and the closest
   call on this row.** `disposition_refs` are `M-7` and `6.3`. M-7 (report
   L226-238) says "The decision must name: source hierarchy for each identifier
   type; conflict-resolution rule; symbol and listing changes; **corporate-action
   handling**; one real test case involving an identifier change." Four of those
   five appear in C-17's acceptance cell; **corporate-action handling** does
   not. I considered whether that is an omission from this row's
   `required_evidence` and concluded it is not, for two reasons that I verified
   rather than assumed:
   - Register v2's Authority rule (L23) is explicit: "The wording in this
     register is authoritative for implementation gates. Narrative reviews
     explain rationale but do not override this register." The register cell,
     not M-7's bullet list, fixes this row's obligations.
   - The obligation is not lost. `DISP-M-7` is a canonical ledger row whose
     source text *is* that bullet list, and it carries both
     `REQ-DISP-M-7-ACCEPTANCE` and `REQ-DISP-M-7-COMMAND-PROOF` (verified).
     Separately, corporate-action versioning is `C-06`'s own register row, which
     declares `C-17` as its dependency. So the program enumerates
     corporate-action handling twice over, on the rows whose source text states
     it.
   An `EVIDENCE` review of `DISP-M-7` — a different component, in a different
   batch — is where that bullet list is audited for completeness. It is out of
   scope here.

5. **§6.3 cross-check.** "ISIN is an external identifier" (report L363-365)
   requires an internal stable primary key. C-17's acceptance cell already
   opens with "Stable internal company/security IDs" and demotes ISIN to a
   "versioned … mapping", so the correction is honoured in the register text
   itself. `DISP-6-3` is separately ledgered with its own `ACCEPTANCE` item
   (verified).

6. **`gate_refs` = `[]`.** No phase-gate clause names `C-17`, so there is no
   gate-side proof demand to reconcile. Its dependents `C-06` and `C-07` also
   carry no gate refs; the Phase 1 gate reaches this subject area through
   `PG-1-05` (post-cutoff exclusion, related to `C-15`), which is not this row.

7. **Dependencies.** `A-05` (provider and data-rights register) and `A-06`
   (XBRL-versus-PDF spike) supply the identifier sources and coverage evidence;
   their obligations stay on their rows (goal L188).

8. **`verification_command` = `UNRESOLVED`** is valid during initial ledger
   construction (goal L500-502); the enumerated `COMMAND_RESULT` requirement is
   what preserves the execution obligation until then.

No omission found. Four items, three distinct proof kinds, complete against the
clause.

## Verdict

verdict: CLEAN
