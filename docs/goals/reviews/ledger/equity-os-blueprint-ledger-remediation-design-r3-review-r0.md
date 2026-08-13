# Independent exact-byte review: ledger remediation design r3

## Review binding

- Reviewed design: `docs/goals/reviews/ledger/equity-os-blueprint-ledger-remediation-design-r3.md`
- Required and observed SHA-256: `ff269d9ed19909b252902ef427bca4ad420a6efa7b8ed019c205b05676a591d0`
- Reviewer lane: independent `gpt-5.6-sol`, `xhigh`
- Scope: load-bearing Critical/Important defects only; no fix or canonical mutation was performed.

The exact design bytes are not safe to present for approval. Three Important defects remain.

## Material findings

### 1. Important — The exact approval question does not bind the independent review evidence

**Design location:** `docs/goals/reviews/ledger/equity-os-blueprint-ledger-remediation-design-r3.md:366-379`, especially `:372-379`, and the exact question at `:386-388`.

**Corroborating evidence:** The pre-approval package says it will show the independent review artifact path, SHA-256, reviewer/session identity, model, effort, timestamp, and verdict (`:372-373`), then says the exact question will have the review-evidence fields filled (`:377-379`). The literal question at `:388` has only `<R3_SHA256>` and contains no review path, review SHA-256, reviewer/session identifier, timestamp, or review-verdict field. `rg -n '<[^>]+>|review artifact|review-evidence|review digest|review SHA' docs/goals/reviews/ledger/equity-os-blueprint-ledger-remediation-design-r3.md` confirmed that `<R3_SHA256>` is the only placeholder in the question. The active goal requires explicit current-user approval for reconciled authority at `docs/goals/equity-os-blueprint-completion.md:119-125`, and its resolution model makes the recorded entry authority projection the immutable authority binding at `docs/goals/equity-os-blueprint-completion.md:939-947`.

**Consequence:** Showing review evidence adjacent to the question is not the same as binding the user's affirmative response to that evidence. The post-answer goal record proposed at design `:396-404` may contain a review digest, but those bytes are agent-produced after the response; the response/question pair does not prove which review artifact or review digest the user approved. A different review artifact could therefore be substituted in the transaction record while preserving the literal approved question and response. That violates the design's own requirement that authority be bound to the stable reviewed design *and* its review evidence.

**Required correction:** Put the exact independent-review artifact path and full SHA-256 in the literal user-facing question, with the clean verdict and reviewed-input SHA explicitly bound as immutable values. Either bind the complete presented package by its own digest or record and validate the exact package bytes, not only the question and response. The structural reconciliation check must compare those bound values with the immutable review artifact and reject substitution before any canonical write.

### 2. Important — In-place stale-evidence refresh can preserve a false “current no-implementation proof” for `DISP-R-1`

**Design location:** `docs/goals/reviews/ledger/equity-os-blueprint-ledger-remediation-design-r3.md:505-517`, `:550-573`, and `:696-698`.

**Corroborating source:** The live `DISP-R-1` object at `docs/goals/equity-os-blueprint-component-ledger.jsonl:135` has:

- stale `EV-DISP-R-1-SPEC-DRAFT` recorded as SHA-256 `87b8755b236d1bd0d377b52bfdb8be491dfc0b22e7cd0f93aed40a06466efb50`;
- `REQ-DISP-R-1-NO-IMPLEMENTATION.status="SATISFIED"`; and
- an immutable `rejection_record.no_implementation_evidence_ref_ids=["EV-DISP-R-1-SPEC-DRAFT"]`.

Fresh command evidence returned current S20 SHA-256 `4948d0f84240cd58b107da1272ed2b90a386bc3fb9ebb6228faac8b98be9c483`, proving that this satisfied proof's declared bytes are stale. The current structural validator requires only that a rejection record's no-implementation IDs resolve to its evidence IDs at `scripts/equity_os_blueprint/validate_ledger_structural.py:1476-1492`; it does not require that those bytes have a fresh semantic review. The current terminal validator likewise accepts a rejected non-register row from its rejection record without running complete-proof validation at `docs/goals/equity-os-blueprint-completion.md:3916-3922`.

**Consequence:** The design orders the migrator to change the existing evidence object's digest and capture time in place (`:505-512`) and to reset stale proof (`:512-517`), while also prohibiting any rejection-record change (`:567-573`). Because the rejection record continues to name the same evidence-ref ID, the validator can treat the newly retargeted bytes as its current no-implementation evidence even after the corresponding requirement is reset. That is exactly the fake-proof outcome prohibited by the approval question and postconditions: digest maintenance is silently promoted into substantive proof.

**Required correction:** Close the proof-consumer rule explicitly. The migration must reset `REQ-DISP-R-1-NO-IMPLEMENTATION` to its exact unresolved form, and structural/terminal reporting must not treat `rejection_record.no_implementation_evidence_ref_ids` as current proof unless those refs are covered by a current, satisfied no-implementation requirement and fresh content-bound review. If the rejection-record schema cannot represent that separation, amend it under HR-0004 and authorize the necessary controlled-field transition instead of declaring every rejection record immutable. Post-transaction reporting must list this proof as unmet; current-digest replacement alone must never satisfy it.

### 3. Important — The declared `--repo-root` interface and mandatory post-replacement commands disagree

**Design location:** `docs/goals/reviews/ledger/equity-os-blueprint-ledger-remediation-design-r3.md:577-606` and `:646-667`.

**Corroborating source/command evidence:** The interface declares `--repo-root` for structural and preimplementation validation at `:579-594`; unlike the ledger path, it is not described as optional. All three candidate commands pass `--repo-root .` at `:624-635`. The mandatory post-replacement structural and preimplementation commands omit it at `:649-655`, and the prose-only post-replacement terminal invocation at `:665-667` does not close the discrepancy. Current extracted scripts have no argument parser and hard-code `Path(".")` / canonical paths (`scripts/equity_os_blueprint/validate_ledger_structural.py:13-18` and `scripts/equity_os_blueprint/validate_ledger_preimplementation.py:8-10`), so no existing interface resolves the intended required-versus-default behavior.

**Consequence:** An executor implementing `--repo-root` as the declared required input will make the mandated post-replacement checks fail after canonical replacement and force rollback. An executor silently giving it a default invents a contract that the exact design never states. This leaves the transaction's commit/rollback gate internally under-specified.

**Required correction:** Choose one closed interface. Prefer declaring `--repo-root` optional with an exact default of `.` and testing both explicit candidate use and canonical default use; otherwise add `--repo-root .` to every post-replacement structural, preimplementation, and terminal invocation. The candidate and canonical commands must exercise the same path-resolution semantics.

## Mechanically verified non-findings

- `sha256sum` matched every stated immutable baseline: active goal `dabad7bfe3d2765a5ac9687376029d8587b4b2ac95bc03494155a974e5ddc67f`; ledger `51091042dae87d2f41fbbf02d77ab1619c6a1008a022baec4233c44a0e295e13`; human review `54c1e183def8e0b1b91504effbf20c233b3d1352fd65d4910e89c2b913ee5702`; v2 register `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`; disposition report `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738`.
- Full JSONL enumeration returned 210 unique rows = 167 canonical + 43 aliases, kind counts `60/35/13/8/32/2/11/6/43`, 454 transition objects, and canonical transition-map digest `d4ce9646438d388bf26c8faa82d689209296726af2c29d1e56942218c613d9b1`. It also returned 45 `Open`, 15 `Deferred`, zero activation records, the stated disposition/delivery/gate counts, and the same exact 23 finding/blocker/HR-linked rows.
- Independent range expansion returned 110 semantic/schema IDs = 107 existing + 3 new. Adding the 34 disjoint evidence-maintenance IDs returned 144 IDs = 141 existing + `ALIAS-044`, `AUTH-REG-002`, and `AUTH-REG-003`; canonical-JSON digest was exactly `bf6fee00d0f4510316b42b50ec13f74148df9ed44e472f2ad8be114ee3add894`. Fresh evidence enumeration found 106 stale `FILE_BYTES` refs on 106 components across 21 spec files, with exactly those 34 components outside the semantic set.
- The 213 target, 169/44 split, exact target kind counts `60/35/13/8/32/4/11/6/44`, four authority occurrences, compound-alias model, disposition/sequence/negative-control/Phase-2 mappings, no-activation/no-advance rules, exact-history-prefix rule, and HR-0001..3 preservation are otherwise internally consistent with the checked authorities and current ledger. The scalar-or-array HR representation can preserve all 23 prior links while adding HR-0004 to the 134 scoped canonical rows; the ten scoped aliases can remain direct resolution-bound members with `human_review_id=null`.
- `python3 scripts/equity_os_blueprint/extract_goal_validators.py --check` exited 0. Current structural validation exited 1 at stale evidence digest assertion `validate_ledger_structural.py:183`; current preimplementation validation exited 1 because inventory reviews remain `PENDING` at `validate_ledger_preimplementation.py:71`. Those are the expected baseline blockers, not new r3 defects. The transaction-only reconciliation baseline is not made a permanent ordinary-validation input by the design.
- Current generator SHA-256 is `0f3ac39fe7db1a46ad9808d1f7db61b33d0f816bcf79d929f82ed3ba723c178d`, exactly the generator-r4 reviewed hash. Its bootstrap-only 213-row schema remains intentionally different from the live 169/44 reconciliation target; r3 correctly forbids using it as the migrator or validator authority.
- The six allowed canonical paths are exact, and the index/no-stage/no-commit/no-push/no-Beads-change boundary is explicit. The evidence-bundle destination rule is authority-coherent: repository placement requires separate pre-transaction approval; otherwise the bundle remains outside canonical paths in the protected recovery area. The executor must preserve the design's durable recovery/discoverability requirement, but choosing the physical protected location is not itself a review failure.

Verdict: ISSUES_FOUND
