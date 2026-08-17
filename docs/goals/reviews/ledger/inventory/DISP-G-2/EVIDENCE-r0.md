# Inventory review — DISP-G-2 / EVIDENCE / r0

**verdict: CLEAN**

## Review identity

| Field | Value |
|---|---|
| `component_id` | `DISP-G-2` |
| `review_type` | `EVIDENCE` |
| `review_round` | `r0` |
| `role` | `REVIEWER` |
| `reviewer` | Reviewer-role subagent, session `13edf3cc-a5b0-4217-8730-759de344e6db` |
| `role_binding_path` | `CONTEXT.md` |
| `role_binding_sha256` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |
| `model` (actually invoked) | `claude-opus-5` |
| `effort` (actually invoked) | `high` |
| `timestamp` (UTC) | `2026-08-15T13:10:41Z` |

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

Fresh structural validation at these exact bytes → exit `0`.

## Reviewed inventory, exactly as read

`review_inventory_projection(row, "EVIDENCE")` — canonical JSON:

```json
{"evidence_refs":[{"captured_at":"2026-08-13T02:49:11Z","content_sha256":"d5035c658cea9b446ca8e42e590d955b0627a3a900a49ce261b37c2677da676f","digest_mode":"UTF8_LINE_SPAN","end_line":73,"evidence_ref_id":"EV-DISP-G-2-SOURCE","path":"docs/blueprint/funda-third-order-review-disposition-report.md","scope":"Exact authoritative source occurrence for DISP-G-2","start_line":61},{"captured_at":"2026-08-15T07:13:28Z","content_sha256":"6b59d6ef082ccca047ec119bc60331894ab1b752fd50e810634da317b0a78631","digest_mode":"FILE_BYTES","end_line":null,"evidence_ref_id":"EV-DISP-G-2-SPEC-DRAFT","path":"docs/specs/equity-os-s18-universe-review-economics-throughput.md","scope":"Current draft specification bytes for DISP-G-2","start_line":null}],"required_evidence":[{"approval_ids":[],"description":"Current proof satisfying: ### G-2 — P90 from three reports\n\n**Disposition: Accept.**\n\nA report-level 90th percentile from three updates is not useful. Phase 0.5 should report the three observed totals directly rather than manufacture a percentile.\n\nClaim-level timing is useful, but it is operational telemetry rather than a statistically independent sample. Claims within one report share the same company, sources, model run, and reviewer. Therefore:\n\n- record total analyst minutes for each report;\n- record median and distribution summaries for claim dispositions;\n- stratify by claim type and correction category;\n- do not make statistical-significance claims from the three-report pilot;\n- introduce report-level percentiles only after a materially larger run history exists.","evidence_id":"REQ-DISP-G-2-ACCEPTANCE","evidence_ref_ids":[],"evidence_type":"ARTIFACT","proof_mode":"CONTENT_HASH","scope":"DISP-G-2 acceptance and delivery scope","status":"UNRESOLVED"}],"verification_command":{"commands":[],"mode":"UNRESOLVED","not_applicable_review":null}}
```

Digests observed at review time, **pre-record** (recorder recomputes after
Phase A, recording design r2 §3.4):

- `reviewed_input_sha256` (pre-record): `8ace6288b1724a3700b9e5b18ddb844eafe2feb9e7cd74e42eaf41da0d8d2083`
- `reviewed_inventory_sha256` (pre-record): `255171160c088be06b5ab2159f2d1b5bd039e12a2351111a81e0df1386032f77`

## Scope of this decision

Completeness of `required_evidence` only (goal L492-494). The single item is
legitimately `UNRESOLVED` with empty `evidence_ref_ids` (goal L484).

## The source clause, re-read this round

Disposition report L61-73 — `### G-2 — P90 from three reports`, disposition
"Accept", with five bullets: record total analyst minutes per report; record
median and distribution summaries for claim dispositions; stratify by claim type
and correction category; make no statistical-significance claims from the
three-report pilot; introduce report-level percentiles only after a materially
larger run history exists.

`text_digest` and `EV-DISP-G-2-SOURCE.content_sha256` both recomputed over the
normalized span → `d5035c65…`, matching.

## Reasoning

**Obligation decomposition — five bullets, one item, checked deliberately.** This
is the most itemized acceptance text in the batch, so the granularity question is
live. The five bullets split into three affirmative recording requirements and two
prohibitions, and all five are requirements on the S18 measurement design. The
single `REQ-DISP-G-2-ACCEPTANCE` item (`ARTIFACT`/`CONTENT_HASH`) quotes all five
verbatim in its `description`, so each is individually recoverable from the
obligation record itself. Splitting into five items would produce five entries
with identical `evidence_type`, `proof_mode`, and `scope`, differing only in
which sentence they quote — and the ledger does this nowhere: verified across all
169 canonical rows, each carries exactly one `REQ-<component_id>-ACCEPTANCE`
quoting the full text, including rows whose text is a bulleted list.

**The affirmative bullets and the absence of a command item — the real question
on this row.** "Record total analyst minutes for each report" and "stratify by
claim type and correction category" describe data that a running system either
produces or does not, which makes a `COMMAND_RESULT` item look plausible. I
checked and it is correctly absent:

- `DISP-G-2` is not in `EXPECTED_COMMAND_PROOF_COMPONENTS`
  (`validate_ledger_structural.py:2635-2649`), and neither is `REG-B-04`, nor the
  gate clause `PG-05-04` that this finding corrects. The entire cone of this
  clause is outside the pinned command-proof population — this is not one row
  being treated differently from its neighbours.
- That is coherent with what the clause actually requires. Its dominant
  obligations are the two prohibitions, and a prohibition on *making a claim in
  prose* ("do not make statistical-significance claims from the three-report
  pilot") has no exit code. The affirmative bullets are satisfied by the pilot's
  own recorded outputs under `B-04`'s acceptance, which is `B-04`'s obligation
  and not something §G-2 independently demands proof of.
- Compare `DISP-6-6` and `DISP-6-9`, the two rows in this batch that *are* in the
  pinned set: each demands an enforced property of code (isolation; declared
  replay classes). §G-2 demands a reporting discipline.

**`TYPED_APPROVAL` — unrepresentable.** The row's only approval requirement is
`APR-DISP-G-2-01`, a `DELEGATED_ARTIFACT_APPROVAL`; ledger-wide, all 123 such
requirements are covered by zero `TYPED_APPROVAL` items, because that record
carries its own persisted clean `REVIEWER`-role review (goal L595-598). Note the
instructive contrast with `DISP-G-1`, the adjacent gate-spec audit finding, which
carries an `ANALYST_ACCEPTANCE` and therefore a matching `TYPED_APPROVAL` item:
`G-1`'s guarantee 3 names approved published bytes, while `G-2` names no approved
artifact at all.

**No negative "no-implementation" proof.** `REQUIRED_NOW` active control,
`rejection_record: null`, not among the 13 `first_release_deferral` rows or
`DISP-R-1`, and not named by the `NO_IMPLEMENTATION_REQUIREMENT_MAP`
(`validate_ledger_structural.py:2671`). Its two prohibitions are negative in
content but they constrain the measurement design's text, which the
`CONTENT_HASH` item covers.

**Framing check.** "Current proof satisfying: ### G-2 — P90 from three reports …"
reads correctly: the proof is that the S18 measurement design reports the three
observed totals and declines the percentile — a present, satisfiable obligation on
active Phase 0.5 scope.

**`evidence_refs`.** Two references, both re-verified against current bytes:
`EV-DISP-G-2-SOURCE` (`UTF8_LINE_SPAN` L61-73, digest `d5035c65…`, captured
`2026-08-13T02:49:11Z`) and `EV-DISP-G-2-SPEC-DRAFT` (`FILE_BYTES` over
`docs/specs/equity-os-s18-universe-review-economics-throughput.md`, digest
`6b59d6ef…`, captured `2026-08-15T07:13:28Z`). Both resolve to live repository
paths and both captures precede this review's timestamp. The S18 draft digest is
shared with `DISP-6-1`'s draft reference, which is expected — both rows are
scoped to the same spec artifact under distinct `evidence_ref_id`s.

**`verification_command` observation, not a finding.** `mode: UNRESOLVED`,
permitted during initial ledger construction (goal L498-500); outside the pinned
command-proof population, so the eventual resolution is `NOT_APPLICABLE` with its
own evidenced reviewer attestation.

**Residuals.** None.

---

**verdict: CLEAN**

`required_evidence` for `DISP-G-2` is complete at the input bytes pinned above.
This review satisfies no evidence item and authorizes no delivery, gate,
approval, or transition.
