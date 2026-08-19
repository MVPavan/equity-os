# Spec closure audit — r0

- **Role:** `REVIEWER` (CONTEXT.md "Agent roles"), read-only audit. No repository, Beads, or Git mutation was performed.
- **UTC of evidence capture:** 2026-08-15 (session date). All hashes below are current worktree bytes at capture time.
- **Scope:** S01–S25 (`docs/specs/equity-os-s*.md`) against the active goal contract.
- **Excluded by instruction (concurrent lanes):** `docs/goals/reviews/ledger/inventory/`, `scratchpad/inventory-reviews/`, `scratchpad/disp-r1/`, `scripts/equity_os_blueprint/`.

## 0. Authority bytes at audit time

| Artifact | Current SHA-256 |
|---|---|
| `docs/goals/equity-os-blueprint-completion.md` | `f15f7ab5a4e425dec3877ab7f1f7594687979060e4dbcd49390a8a8d5fedb85f` |
| `docs/blueprint/funda-blueprint-implementation-decision-register-v2.md` | `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164` |
| `docs/blueprint/funda-third-order-review-disposition-report.md` | `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738` |
| `docs/goals/equity-os-blueprint-component-ledger.jsonl` | `de236d7e8dcf02e307ec58797f5722ae2f85d1d8cdba57d4ecc07df5383c9c97` |
| `docs/goals/equity-os-blueprint-human-review-needed.md` | `094fcdfab74a3f4c6fdb82b1520fc4d13b636ac0e9ed10194e5d607aed2ce9af` |
| `CONTEXT.md` | `8f2795af93ba6bf5303cf13227b8ce9e96295269887673a3a8b97d920b3198ce` |

**Every one of the 39 spec review artifacts binds goal-contract hash `dabad7bfe3d2765a5ac9687376029d8587b4b2ac95bc03494155a974e5ddc67f`** — the pre-HR-0004 contract (4,146 lines, commit `7254ff83`). Verified by extracting `git show 7254ff83:docs/goals/equity-os-blueprint-completion.md`, which hashes exactly to `dabad7bf…`, and whose lines 129–870 hash exactly to the `1650313c…` span every review binds. The current contract is 5,894 lines. See §5.

## 1. What "clean delegated approval" means, exactly

Assembled from the goal contract; citations are to `docs/goals/equity-os-blueprint-completion.md` at its **current** bytes.

### 1.1 The three things the contract actually requires per spec

**(a) A persisted clean review artifact bound to the exact spec bytes.**

- §"Autonomous lifecycle" step 2 (`:895–902`): "An `IMPLEMENTER`-role dispatch authors each spec; a fresh `REVIEWER`-role dispatch reviews it… **Close each child only with persisted clean-review evidence and delegated approval.**"
- §"Review, fix, and adjudication policy" (`:977–1000`): review rounds `r0`–`r4` (five is a ceiling); every finding, severity, load-bearing classification, evidence, fix, verdict, and round must be persisted in review artifacts **and the ledger**; "Conversation text is not evidence."
- §"Agent routing and delegated authority" (`:932–955`): "the role, model, and effort actually invoked are recorded explicitly for every dispatch"; a `REVIEWER` dispatch "is always a separate agent and context from the `IMPLEMENTER`-role dispatch whose output it reviews."

**(b) A delegated-approval statement in that artifact.**

§"Delegated artifact approval" (`:957–975`): after user activation, "a clean, fresh-context `REVIEWER`-role review may approve a spec, roadmap, or JIT plan under delegated goal authority. **The artifact records `approved under delegated goal authority`, reviewer identity/session, source hashes, review round, timestamp, and evidence path.** It never records or implies personal user approval." Delegation covers no analyst/domain/legal/rights/budget/regulatory/production authority.

**(c) A typed, one-to-one ledger approval record.**

Same section: "The owned components record this event as distinct `DELEGATED_ARTIFACT_APPROVAL` requirements and one-to-one approval records." Per §"Typed approval proof" (`:533–627`):

- each owned component carries a `required_approvals` entry with `approval_type=DELEGATED_ARTIFACT_APPROVAL`, a `required_authority` string identical across all such requirements, `scope`, `status`, `actor`, `timestamp`, `evidence_ref_ids`, `matched_record_id`;
- "Missing actor, timestamp, evidence, authorization proof, or matching record leaves the requirement `UNRESOLVED`; **only `SATISFIED` passes**";
- a matching `approval_records` entry with `decision=APPROVED`, `authority_source=DELEGATED_AUTOMATED` (the only type allowed to use it), null human-resolution fields, and which "carries the persisted clean `REVIEWER`-role review";
- "A `SATISFIED` requirement matches one `APPROVED` record with identical type, authority, scope, actor, timestamp, evidence, and authority source. Record IDs … are globally unique … and may not satisfy two requirements."
- Evidence objects (§"Typed evidence and verification proof", `:449–465`): the review artifact must be an `evidence_refs` object with `evidence_ref_id`, repo-relative `path`, `scope`, `digest_mode`, `content_sha256`, `captured_at`. "A changed or missing target invalidates the reference."

**(d) Closure of the typed tracked work.**

§"Typed tracked-work closure" (`:628–664`): exactly one `SPEC_EPIC` and "exactly 25 required `SPEC_TASK` records carrying S01…S25 once each"; a `BEAD` record's live state is read with `bd --readonly show --json <id>` and its typed `status` must equal `closed`. "A ledger-authored word such as `closed` is never accepted as source state."

### 1.2 What it binds

The binding is **path + exact file-byte SHA-256 + role + verdict + round + reviewer identity/session + timestamp + evidence path**. Every clean review artifact in this repo states the exact-hash limit itself, e.g. `equity-os-s22-s25-r4.md:60`: "Any byte change invalidates the corresponding approval and requires fresh review."

### 1.3 Where the artifacts must live

The contract does not pin a directory for spec review artifacts (it pins only the single human-review document path and the ledger path). In practice all spec reviews live in `docs/goals/reviews/specs/`, and the ledger/human-review evidence objects reference them by that repo-relative path. That convention is what the evidence refs bind, so it is effectively normative now.

### 1.4 Program-level gates that consume the per-spec result

- §"Preimplementation coverage gate" (`:810`): "**all 25 initial specs and the cross-spec audit are clean under delegated goal authority**."
- §"Nine mechanical conditions for `SUCCESS`" #3 (`:5750`): "The specification epic has exactly 25 direct child tasks, all closed with saved clean-review evidence." The terminal validator "queries the epic's actual children from Beads and requires them to be exactly the 25 typed spec tasks."

## 2. Review artifacts that exist on disk

39 files in `docs/goals/reviews/specs/` — eight batch chains plus three post-`r4` adjudications. No spec review artifact exists anywhere else in the repo (checked `docs/`, `scratchpad/`, `scripts/`).

| Batch | Rounds present | Terminal verdict | Adjudication |
|---|---|---|---|
| S01–S03 | r0, r1, r2, r3, r4 | **r4 CLEAN** | — |
| S04–S06 | r0, r1, r2, r3, r4 | r4 ISSUES_FOUND (S04 CLEAN, S05 CLEAN, S06 blocked) | `equity-os-s04-s06-adjudication.md` — **UPHOLD S06-I7** |
| S07–S09 | r0, r1, r2, r3, r4 | r4 ISSUES_FOUND (S07 CLEAN, S08 CLEAN, S09 blocked) | `equity-os-s07-s09-adjudication.md` — **UPHOLD S09-r3-N1** |
| S10–S12 | r0, r1, r2, r3, r4 | r4 ISSUES_FOUND (S10 blocked, S11 CLEAN, S12 CLEAN) | `equity-os-s10-s12-adjudication.md` — **UPHOLD R3-F-01** |
| S13–S15 | r0, r1, r2, r3 | **r3 CLEAN** (stopped early, permitted) | — |
| S16–S18 | r0, r1, r2, r3 | **r3 CLEAN** | — |
| S19–S21 | r0, r1, r2 | **r2 CLEAN** | — |
| S22–S25 | r0, r1, r2, r3, r4 | **r4 CLEAN — delegated artifact approval granted** | — |

**No cross-spec audit artifact exists.** Lifecycle step 3 (`:903–907`) has not been performed, and the preimplementation gate names it explicitly alongside the 25 specs.

## 3. The 25-row table

`STALE/CURRENT` = does a clean review bind the spec's **exact current bytes**? Bead state from `bd --readonly show --json eqos-0xb.N`. Ledger DAC = `DELEGATED_ARTIFACT_APPROVAL` requirements SATISFIED / total across that spec's owned components.

| Spec | Path (`docs/specs/`) | Current SHA-256 | Clean review bound to this hash | Verdict | Status | Open load-bearing findings | Ledger DAC | Bead |
|---|---|---|---|---|---|---|---|---|
| S01 | `equity-os-s01-product-identity-operating-distribution-boundary.md` | `1ad276cfa854b760a627b067be5aabe3b36019998a9ad5d1b52194c2dbd4af49` | `s01-s03-r4.md:31` | CLEAN | CURRENT | none | 0/3 | `eqos-0xb.1` closed |
| S02 | `equity-os-s02-source-rights-providers-consensus-policy.md` | `284d496f4b173c2489b1214e5662af0d6d7454db2558f106bbb649878c57ac14` | `s01-s03-r4.md:32` | CLEAN | CURRENT | none | 0/4 | `eqos-0xb.2` closed |
| S03 | `equity-os-s03-external-tool-due-diligence.md` | `998c4a66023689fddd7f25785ed1fee8af533356f8fc329421cb6e60c2cc155c` | `s01-s03-r4.md:33` | CLEAN | CURRENT | none | 0/2 | `eqos-0xb.3` closed |
| S04 | `equity-os-s04-execution-trust-domain.md` | `0ceab71267d96f40a7b40bd1af36d83f04a5b068370d558106d0fdbbb79f4523` | `s04-s06-r4.md` per-spec table | CLEAN | CURRENT | none | 0/3 | `eqos-0xb.4` closed |
| S05 | `equity-os-s05-discovery-company-vertical-slice.md` | `3f3e371f7a71683c3befed5e6f0d6daff4bd2a5f630ad4aa9b62c31b1070885e` | `s04-s06-r2/r3/r4.md` | CLEAN (byte-identical since r2) | CURRENT | none | 0/6 | `eqos-0xb.5` closed |
| S06 | `equity-os-s06-output-materiality-falsifiers.md` | `9b14f5f327a9ff623cb41c823ab3eeec2d14f2f3ee05b8506313fbb28e83f458` | **none** | ISSUES_FOUND at this exact hash; UPHELD post-cap | n/a — never clean | **S06-I7** (Important, load-bearing): cyclic digest dependency `transition → decision → inventory → transition`. `s04-s06-r4.md`, `s04-s06-adjudication.md` | 0/3 | `eqos-0xb.6` **blocked** |
| S07 | `equity-os-s07-golden-set-failure-reviewer-controls.md` | `5da8bf5f31e29833885d7e0bf74ecfc2a550fb9c24415ef5123fa47c938e2957` | `s07-s09-r4.md` per-spec table | CLEAN | CURRENT | none | 0/3 | `eqos-0xb.7` closed |
| S08 | `equity-os-s08-success-metrics-budgets-capacity.md` | `96add3840a6ff8c6280a70a75242b20a1615e50e9a49236d1bd3636f7e22d9ba` | `s07-s09-r4.md` per-spec table | CLEAN | CURRENT | none | 0/5 | `eqos-0xb.8` closed |
| S09 | `equity-os-s09-filing-ingestion-point-in-time-capture.md` | `a1f7477881ac2fb0497b02bcf1bce897219565d6fc521fdd3589a9006fae1c4c` | **none** | ISSUES_FOUND at this exact hash; UPHELD post-cap | n/a — never clean | **S09-r3-N1** (Important, load-bearing, plan-mandated): approval record does not require `human_review_id`/actor/timestamp equality with the canonical resolution. `s07-s09-r4.md`, `s07-s09-adjudication.md` | 0/5 | `eqos-0xb.9` **blocked** |
| S10 | `equity-os-s10-source-of-truth-evidence-retention.md` | `22c0c777ab8fa7f6ebdb311bd8cfc04d2f45af692cf7990b8be81bb71ccb2c6e` | **none** | ISSUES_FOUND at this exact hash; UPHELD post-cap | n/a — never clean | **R3-F-01 residue** (Important, load-bearing): imported S08 approval projection omits full one-to-one equality semantics; correction-ancestry import omits root/scope/acyclicity/fork/current-leaf validation. `s10-s12-r4.md`, `s10-s12-adjudication.md` | 0/8 | `eqos-0xb.10` **blocked** |
| S11 | `equity-os-s11-run-manifest-cutoff-reproducibility.md` | `f6158ce7d04109cbb954a4113bd43046428028abd30c34f0652ca3aae52ccf8e` | `s10-s12-r4.md` verdict table | CLEAN | CURRENT | none | 0/3 | `eqos-0xb.11` closed |
| S12 | `equity-os-s12-observation-fact-identity-schema.md` | `61094a92688a7393eeedf99cd1a8759be874b5f9fd775374984d748c73d3376d` | `s10-s12-r4.md` verdict table | CLEAN | CURRENT | none | 0/5 | `eqos-0xb.12` closed |
| S13 | `equity-os-s13-claim-schema-vocabulary-evidence.md` | `f1a60a20e24a0d2a457aa71f8d9006316ea461d237ea1faa054fc24176ba3dc4` | `s13-s15-r3.md:21` | CLEAN | CURRENT | none | 0/4 | `eqos-0xb.13` closed |
| S14 | `equity-os-s14-earnings-review-workflow-rework.md` | `b9515d9b6fe92fb735f9ab8121dec2c7d2ba8566828896f1dc5386d6fb801912` | `s13-s15-r3.md:22` | CLEAN | CURRENT | none | 0/8 | `eqos-0xb.14` closed |
| S15 | `equity-os-s15-human-review-correction-promotion.md` | `3dfc8cac1fa57df3b2cbe2cef8b1d6bf5f274cbeee12527d301cfef580020e44` | `s13-s15-r3.md:23` | CLEAN | CURRENT | none | 0/2 | `eqos-0xb.15` closed |
| S16 | `equity-os-s16-minimum-deterministic-compute.md` | `b3d436e95b874445cb9000a7ee89c69c5a9bcdee03433865b83280e09842b3d6` | `s16-s18-r3.md` | CLEAN | CURRENT | none | 0/2 | `eqos-0xb.16` closed |
| S17 | `equity-os-s17-entity-security-master-actions.md` | `dbb6b8600de771e9ae668208a9893394321ce67fb366c706c2d9c98985ee85aa` | `s16-s18-r3.md` | CLEAN | CURRENT | none | 0/5 | `eqos-0xb.17` closed |
| S18 | `equity-os-s18-universe-review-economics-throughput.md` | `6b59d6ef082ccca047ec119bc60331894ab1b752fd50e810634da317b0a78631` | `s16-s18-r3.md` | CLEAN | CURRENT | none | 0/7 | `eqos-0xb.18` closed |
| S19 | `equity-os-s19-memory-store-promotion.md` | `17c50829c062dadf4a8b2edb6c0eb403c246d4966d5498a99f106fc4620e5da7` | `s19-s21-r2.md:53` | CLEAN — "approved under delegated goal authority" | CURRENT | none | 0/2 | `eqos-0xb.19` closed |
| S20 | `equity-os-s20-memory-benchmark-gbrain.md` | `4948d0f84240cd58b107da1272ed2b90a386bc3fb9ebb6228faac8b98be9c483` | `s19-s21-r2.md:54` | CLEAN — same | CURRENT | none | 0/4 | `eqos-0xb.20` closed |
| S21 | `equity-os-s21-conditional-model-grade-compute.md` | `85d3f7fd2b6cc48b415772d11db84ce6b4ed8845b8a5104a7503f16dbd14ab75` | `s19-s21-r2.md:55` | CLEAN — same | CURRENT | none | 0/2 | `eqos-0xb.21` closed |
| S22 | `equity-os-s22-conditional-stress-test-companies.md` | `c465652e7a6bcfde8a486fe59e28c287e8511bfdf097326ebc04ca4d8bb8f9ef` | `s22-s25-r4.md:55` | CLEAN — DAC **granted** | CURRENT | none | 0/1 | `eqos-0xb.22` closed |
| S23 | `equity-os-s23-conditional-bull-bear-forensic-review.md` | `2be2555baf432cd0830d08e7a256fa6cefd9962ea70e7355f419abbf84812936` | `s22-s25-r4.md:56` | CLEAN — DAC granted | CURRENT | none | 0/2 | `eqos-0xb.23` closed |
| S24 | `equity-os-s24-conditional-event-monitoring.md` | `6218383aff0cfb42d0f9acae0b280cd703e97a6b27d80941aeeb3877b057b449` | `s22-s25-r4.md:57` | CLEAN — DAC granted | CURRENT | none | 0/2 | `eqos-0xb.24` closed |
| S25 | `equity-os-s25-quant-validation-historical-leakage.md` | `3b66cb90a76ab8f62eef203de2beabff5171c556146071974cc48e926374bbd2` | `s22-s25-r4.md:58` | CLEAN — DAC granted | CURRENT | none | 0/5 | `eqos-0xb.25` closed |

**No spec has drifted from its clean review.** Every spec's current bytes are exactly the bytes its terminal review bound; `git status --porcelain docs/specs` is empty and the specs have not been touched since commit `6d6d836`. There is no case of "review exists but binds an older hash."

## 4. Verification of the stale `eqos-0xb` note

The note claims: clean delegated approvals exist for **S01, S05, S07, S08, S11, S13, S19, S20, S21 only**, and S22–S25 "received an additional interrupted-but-file-complete Sol fix pass and still require fresh r2."

**Both claims are false as of today.** The note is a checkpoint from `2026-08-13T03:10Z`, before the r3/r4 rounds and the S22–S25 r4 ran.

- Actually clean at exact current bytes: **22 specs** — S01, S02, S03, S04, S05, S07, S08, S11, S12, S13, S14, S15, S16, S17, S18, S19, S20, S21, S22, S23, S24, S25.
- S22–S25 did not stop at "requires fresh r2": `equity-os-s22-s25-r4.md` is a **CLEAN r4** that explicitly grants `DELEGATED_ARTIFACT_APPROVAL` for all four current hashes.
- Not clean: **S06, S09, S10** only.

The note's vendor-capacity clause ("Every fresh Sol xhigh Codex CLI invocation now fails with usage limit until 2026-08-18T03:21Z; no Luna substitution is allowed") is **stale on two counts**: the goal contract no longer names any vendor model (HR-0004 rebound every occurrence to `REVIEWER`-role, and `CONTEXT.md` "Agent roles" is now the single binding table), and the acceptance criteria on the epic and all 25 children still say "clean delegated **Sol xhigh** review evidence," which contradicts the current contract.

### Beads reality vs the premise in the audit request

The premise that "only 3 child beads exist (S06, S09, S10) and all are BLOCKED" is an artifact of `bd list` defaulting to open issues. **The epic has all 25 direct children** (`eqos-0xb.1` … `eqos-0xb.25`), of which **22 are `closed`** and 3 are `blocked`. `bd show eqos-0xb` reports "22/25 complete (88%)". The ledger likewise carries exactly one `SPEC_EPIC` and 25 `SPEC_TASK` records, S01–S25 once each.

### Are the three blockers real or stale?

**Real, and they are not the vendor-capacity blocker.** `bd blocked` returns "No blocked issues" — none of the three has a dependency edge; their only dependency is the parent-child link to the epic. They carry `status=blocked` set by hand, and their notes cite the actual cause: a fresh post-`r4` adjudication **UPHELD** a load-bearing Important finding in each case, with the exact spec hash and report path recorded. Those adjudications are on disk, are source-grounded, and rule out both `REJECT` and `PARK/DEFER` with reasoning. Under §"Review, fix, and adjudication policy" clause 5, an unresolved load-bearing Important finding blocks the component and every dependent cone and "may not be waived to manufacture completion."

What **is** stale in those blockers is the remediation *route*: each note (and each HR entry) asks for authority to run "a future Sol xhigh session" and "a separate fresh Sol xhigh exact-byte review." Under the current contract and `CONTEXT.md`, that work is an `IMPLEMENTER`-role fix plus a fresh independent `REVIEWER`-role review. The vendor lane named in the request is prohibited by standing project policy; the *process* need (post-cap authority + fix + fresh review) is unchanged and still real.

### Human-review entries

`docs/goals/equity-os-blueprint-human-review-needed.md` carries **HR-0001 (S06-I7), HR-0002 (S09-r3-N1), HR-0003 (R3-F-01)** — all `blocking: true`, `resolution_decision_ids: []`, decision authority `GOAL_OR_PROCESS_AUTHORIZATION` / `CURRENT_USER`. HR-0004 (the executed `RECONCILE_AUTHORITY` transaction) explicitly "preserves HR-0001, HR-0002, and HR-0003 open, blocking, and unresolved." So the three spec blockers are correctly filed and awaiting exactly one user decision each.

## 5. The gap nobody has recorded: ledger-side approval proof is empty

Parsing all 213 ledger rows:

- `DELEGATED_ARTIFACT_APPROVAL` **requirements**: 123 total (96 on spec-owned components, 27 on components with `primary_spec=null`). **All 123 are `UNRESOLVED`.**
- `DELEGATED_ARTIFACT_APPROVAL` **records**: **zero**. There is not one `approval_records` entry of that type anywhere in the ledger.

Per §1.1(c), "only `SATISFIED` passes." So by the contract's own typed-approval test, **no spec currently has a delegated approval at all** — including the 22 whose review artifacts say in prose that approval is granted. The prose grant in the review artifact is a necessary input; the ledger record is the machine-checkable proof, and it has never been written. This affects every one of the 22 otherwise-clean specs and is invisible from Beads (which shows 22/25 closed) and from the review artifacts (which read as approved).

Corollary: the 22 spec beads were closed on review evidence alone, without the delegated-approval half of the step-2 closure rule ("persisted clean-review evidence **and** delegated approval").

## 6. Authority drift since the reviews (open interpretive question)

All 39 spec reviews bind goal hash `dabad7bf…`. The current goal is `f15f7ab5…`. Diffing the exact reviewed span (old lines 129–870 = "Canonical blueprint component ledger" through "Review, fix, and adjudication policy") against the corresponding current text gives **289 changed lines** across 14 of 19 subsections:

| Subsection | Changed lines | Character of change |
|---|---|---|
| Required normalized inventory | 22 | Exhaustive counts pinned (213 rows: 169 canonical / 44 aliases) |
| Required JSONL fields | 4 | Sol → `REVIEWER`; `human_review_id` may be an array |
| Disposition derivation and authority records | 28 | Compound aliases; append-only HR-link growth |
| Typed activation predicates | 19 | `REQUIRED_NOW` components carry `activation_predicate=null` |
| Content-bound inventory reviews | 22 | Sol → `REVIEWER`-role + role-binding digest fields |
| Typed evidence and verification proof | 26 | Sol → `REVIEWER`; no-implementation-proof predicate tightened |
| **Typed approval proof** | **42** | **New closed required-authority vocabulary table** (`ANALYST_ACCEPTANCE` → `Responsible analyst`, etc.); Sol → `REVIEWER` |
| State transitions | 32 | Transaction-mode reconciliation |
| Preimplementation coverage gate | 2 | Sol → `REVIEWER` |
| Autonomous lifecycle | 31 | Role rebinding throughout |
| Agent routing and delegated authority | 52 | Whole section rewritten to the three-role model |
| Delegated artifact approval | 3 | "fresh-context Sol xhigh review" → "fresh-context `REVIEWER`-role review" |
| Review, fix, and adjudication policy | 2 | "fresh Sol xhigh adjudicator" → "fresh `REVIEWER`-role adjudicator" |

Unchanged: **`## Exact 25-spec program`**, `### Evidence-derived provisional contracts`, `### Typed tracked-work closure`, `### Status semantics`, and the ledger section preamble. The register and disposition report bytes are unchanged (HR-0004's scope text asserts this and the hashes confirm it).

**Materiality assessment (my judgment, not settled by the contract):** the bulk of the change is (i) vendor-model → role rebinding and (ii) ledger schema, neither of which is spec-content. The one genuinely new normative surface for specs is the closed required-authority vocabulary. I tested it mechanically: of the 17 pinned authority literals, only `Golden-set owner` appears anywhere in the 25 specs (one file), and it is in the allowed set. No spec hardcodes an authority literal outside the table. So I found **no concrete spec-text violation** introduced by the amendment.

**But the drift itself is unresolved.** §"Source drift and reconciliation" clause 6 (`:122–125`) requires, after a reconciliation, "Re-run the preimplementation coverage gate for affected specs before dependent product work resumes" — and that gate's spec clause is "all 25 initial specs and the cross-spec audit are clean under delegated goal authority." Whether a review bound to `dabad7bf…` still discharges that clause under `f15f7ab5…` is not stated anywhere in the contract. The contract makes staleness explicit for content-bound *inventory* reviews ("A mutation to any covered source… makes all affected complete reviews stale") and silent for spec reviews. Both readings are defensible:

- **Narrow reading:** spec reviews bind the spec bytes; spec bytes are unchanged; the amended sections impose no new spec obligation I could find; the 22 clean reviews stand.
- **Strict reading:** a spec review asserts compliance *against an authority*, that authority's bytes changed inside the exact reviewed span, so all 22 approvals are stale and need a fresh delta review.

I cannot settle this from evidence. See §9.

## 7. Ranked "what must happen to close each spec", batched

### Group A — blocked on one user decision each, then fix + fresh review (3 specs: S06, S09, S10)

Identical shape; can be worked in parallel because their file scopes are disjoint.

1. **Get HR-0001 / HR-0002 / HR-0003 resolved by the current user.** Each authorizes a narrow post-`r4` remediation mechanism outside the forbidden ordinary `r5`. Nothing else in this group can start first — clause 5 of the review policy forbids waiving a load-bearing finding, and clause 2 forbids an `r5`.
2. **Re-word the three HR questions before asking.** As written they request authority for "a future Sol xhigh session" and "a fresh Sol xhigh exact-byte review." That vendor lane is prohibited by standing project policy and is no longer named by the contract. The questions should ask for the same *mechanism* in role terms (`IMPLEMENTER` fix + fresh independent `REVIEWER` exact-byte review).
3. **`IMPLEMENTER`-role fix, one spec per dispatch:**
   - S06 — replace the cyclic digest architecture with an acyclic one. The adjudication's non-binding recommendation: candidate snapshot digest → materiality decision digest → disposition transition digest → final inventory-closure digest → artifact digest → human approval.
   - S09 — require the approval record's `human_review_id`, actor identity, and timestamp to equal the canonical resolution's fields, and add the missing `human_review_id`-mismatch fixture plus explicit record→resolution actor/timestamp fixtures.
   - S10 — specify the full imported approval projection (requirement actor/timestamp/evidence/`matched_record_id`; record `authority_source` and human-resolution fields; global one-to-one matching) and full correction-chain root/scope/acyclicity/fork/current-leaf validation, with a digest-valid-but-semantically-invalid negative fixture.
4. **Fresh `REVIEWER`-role exact-byte review per spec** (separate agent and context from the fixer), producing a clean artifact that records role, model, effort, session, round, timestamp, exact new spec hash, and the delegated-approval statement.
5. **Then Group B steps for those three specs**, and `bd update` from `blocked` to closed.

### Group B — ledger approval records missing (all 25, including the 22 clean)

One batched mechanical pass, cheapest work with the largest effect:

6. **Write the 123 `DELEGATED_ARTIFACT_APPROVAL` approval records** and flip the matching requirements to `SATISFIED`: for each owned component, one `approval_records` entry with `decision=APPROVED`, `authority_source=DELEGATED_AUTOMATED`, null human-resolution fields, globally unique record ID, and `evidence_ref_ids` pointing at `evidence_refs` objects for the governing review artifact (path + `FILE_BYTES` `content_sha256` + `captured_at`), with requirement `actor`, `timestamp`, `scope`, and `matched_record_id` set to match byte-for-byte. Append the field changes to `transition_history` and refresh `transition_history_sha256`.
7. **Pin the single `required_authority` literal** for `DELEGATED_ARTIFACT_APPROVAL`. The contract requires every such requirement to share one identical nonempty value and validates that invariant; confirm the 123 existing requirements already agree before writing records.
8. **Re-run the structural then preimplementation validators** and read their exit codes.

### Group C — program-level items that are not per-spec but gate the same success condition

9. **Run the cross-spec audit** (lifecycle step 3): a fresh `REVIEWER`-role dispatch over all 25 specs for the 60 register owners, 32 dispositions, interface consistency, authority conflicts, omissions, and accidental Deferred activation. It does not exist and the preimplementation gate names it explicitly. It should run *after* Group A, since S06/S09/S10 will change.
10. **Decide the §6 drift question**, and if the strict reading wins, run a bounded `REVIEWER`-role delta review of the goal diff against the 22 clean specs rather than 22 full re-reviews.
11. **Fix the stale acceptance criteria** on `eqos-0xb` and all 25 children ("clean delegated **Sol xhigh** review evidence") and the epic's stale checkpoint note, so the Beads record stops contradicting the contract.

## 8. Counts

Under the contract's full definition (clean current-byte review **+** `SATISFIED` typed delegated approval **+** closed typed bead):

- **Genuinely closed today: 0.** No spec has a `SATISFIED` `DELEGATED_ARTIFACT_APPROVAL`, because zero such records exist in the ledger.

Under the practical decomposition the remaining work actually follows:

- **22 specs need only the ledger approval record written** (review is clean and bound to exact current bytes; bead already closed): S01–S05, S07, S08, S11–S25.
- **0 specs need only a fresh review** because of spec drift. No spec has drifted from its review. (If the strict drift reading in §6 is adopted, this becomes **22 need a fresh delta review**, and the "needs only a ledger record" count becomes 0.)
- **3 specs need fixes first** — S06, S09, S10 — each gated on a user decision (HR-0001/0002/0003) before the fix may begin.
- **1 program-level artifact missing:** the cross-spec audit.

## 9. What I could not determine, and what would settle it

1. **Whether the HR-0004 goal amendment stales the 22 clean spec reviews.** The contract is explicit about staleness for content-bound inventory reviews and silent for spec reviews. *Settled by:* an explicit user or `REVIEWER`-role ruling on whether a `RECONCILE_AUTHORITY` amendment inside the reviewed authority span invalidates prior spec approvals — ideally recorded as a contract clause so it never has to be re-litigated. A cheap intermediate: one `REVIEWER`-role delta review of the 289-line diff asking only "does any changed clause impose a new obligation on spec text?"
2. **Whether the three UPHELD findings survive against the current contract bytes.** S09's finding cites `goal:498` and `goal:2252` and S10's cites `goal:2191/2201/2288` — line numbers in the 4,146-line contract that now point elsewhere in the 5,894-line file. I confirmed the underlying record→resolution equality requirement still exists in the current §"Typed approval proof", so the findings look intact, but I did not re-derive them line by line. *Settled by:* the fresh `REVIEWER` review in Group A step 4, which re-derives against current bytes anyway.
3. **Whether the spec reviews satisfy the "record the role" requirement.** All 39 record model and effort; none records `role: REVIEWER` as a field (some mention the word in prose). Spec reviews are not held to the content-bound review schema that mandates `role`/`role_binding_path`/`role_binding_sha256` — that schema governs the three ledger inventory reviews — so this may be a non-issue. *Settled by:* the same ruling as item 1, or by a validator that states the required field set for spec review artifacts.
4. **Whether `equity-os-s01-s03-r3.md` taints the S01–S03 chain.** That round was performed by the root session acting as both fixer and reviewer under a temporary user fallback, which contradicts "A `REVIEWER`-role dispatch is always a separate agent and context." The subsequent `r4` states it "treated the r3 sequential-fallback verdict as an unverified claim and independently re-derived" it, which I read as curing the defect. *Settled by:* accepting that r4 statement, or re-running one independent review if the user wants the chain clean end to end.
5. **Whether a post-cap fix+review for S06/S09/S10 is contractually available at all.** §"Review, fix, and adjudication policy" caps rounds at `r0`–`r4` and offers the adjudicator only reject / park / uphold — with no described path back to clean after an UPHOLD. The four mandated amendment gates in §"Evidence-derived provisional contracts" show that an amendment restarts the cap, but only S06 has such a gate and it is conditioned on A-03 baseline evidence that does not yet exist. *Settled by:* the user's HR-0001/0002/0003 decisions, which is exactly what those entries are for — this is the contract working as designed, not a defect.

## 10. Evidence commands run

All read-only:

```
sha256sum docs/specs/*.md
sha256sum docs/goals/equity-os-blueprint-completion.md docs/blueprint/*.md \
          docs/goals/equity-os-blueprint-component-ledger.jsonl \
          docs/goals/equity-os-blueprint-human-review-needed.md CONTEXT.md
grep -rl <each-spec-hash> docs/goals/reviews/
git show 7254ff83:docs/goals/equity-os-blueprint-completion.md | sha256sum   # -> dabad7bf…
git status --porcelain docs/specs docs/goals/reviews/specs                   # empty
bd show eqos-0xb ; bd --readonly show --json eqos-0xb.{1..25} ; bd blocked
python3  # parse all 213 ledger rows for DAC requirements/records, tracked_work,
         # open_findings, blocked_scope grouped by primary_spec
```
