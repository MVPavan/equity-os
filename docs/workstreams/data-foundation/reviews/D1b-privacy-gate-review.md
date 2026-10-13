# D1b verification privacy-rail correction — independent review

Final verdict: APPROVE — r1's sole Important fixture-isolation issue is addressed; no new Critical/Important issues. The seven exact financial-context records retain their individual r1 APPROVE verdicts.

Reviewer: Codex session (handoff run), `/root/review_privacy_gate`.
Date: 2026-10-13.
Scope: `scripts/verify.sh`, `verify_privacy_identifiers.py`, `verify_privacy_proofs.json`, `tests/fundamentals/test_verify_privacy.py`. This review approves the bounded technical scanner correction and privacy classification, not financial qualification, owner judgment or full project acceptance. The coordinator separately runs the actual full historical-scope gate before closing the issue.

The original financial oracles/fixtures are unchanged. Exceptions bind exact path, whole-file hash, line hash and token; other contexts still fail closed. Registry and scanner remain trusted repository policy assets, not authentication against a malicious repository writer.

## Final scoped re-review

# eqos-490 privacy-rail scoped re-review r2 — Codex session (handoff run)

Finding verdicts:

1. **ADDRESSED — `tests/fundamentals/test_verify_privacy.py:61-67`.** The fixture now copies the process environment, removes only the outer repository's `VERIFY_SCOPE_BASE`, and passes the isolated environment to each temporary repository. The dedicated historical-scope case still resolves its own temporary repository base and adds it only after proving default-HEAD behavior (`tests/fundamentals/test_verify_privacy.py:118-133`). This removes the exact parent-to-temporary-repository commit leak without weakening the production scope-base validation or the test's historical replay assertion.

Verification evidence: the fix report records the exact pre-fix command under outer `VERIFY_SCOPE_BASE=05b2634` as exit 1 with 16 failed / 8 passed and invalid-scope STOPs (`scratchpad/execution/data-foundation-resume-2026-10-13/privacy-isolation-fix.md:30-38`). The identical command after the one-line isolation fix reports exit 0 with 24 passed (`privacy-isolation-fix.md:40-43`). Scoped Ruff lint/format, Python compilation, and `git diff --check` are also reported green (`privacy-isolation-fix.md:44-49`). The mutation check removes the pop and restores the exact RED (`privacy-isolation-fix.md:51`).

New breakage in fix diff: **none.** Removing a commit name that belongs to the outer checkout is correct isolation for newly initialized temporary Git repositories; the only test that needs a historical base explicitly supplies a base belonging to its own repository (`tests/fundamentals/test_verify_privacy.py:118-130`).

Out-of-scope observations: **none.** The seven registry/context approvals and the helper/scanner implementation were unchanged and retain the r1 verdicts.

Verdict: **all addressed, no new Critical/Important**.

## Preserved first pass and every exact context

# eqos-490 privacy-rail quality/security review — Codex session (handoff run)

Strengths: The correction is narrow. `scripts/verify.sh:281-289` resolves `VERIFY_SCOPE_BASE` to a commit and rejects option-like, malformed, non-commit, and non-ancestor values before running quality commands. The resolved hash is used consistently for candidate discovery, added-line extraction, diff coverage, and identifier adjudication (`scripts/verify.sh:370-387`, `:536-545`, `:640`). The helper has no environment allowlist or caller-selected registry, uses argv rather than a shell, restricts proof paths to `tests/`, validates both SHA-256 fields, and converts registry/Git/read failures into a nonzero result (`scripts/verify_privacy_identifiers.py:14-21`, `:24-46`, `:77-82`). Exact runtime authorization is `(path, whole-file SHA-256, exact-line SHA-256, token)` (`scripts/verify_privacy_identifiers.py:46`, `:60-73`); `reason`, `source_proof`, `authority`, and `line_number_at_review` are review metadata, not runtime identity. Unknown captured numeric IDs remain terminal (`scripts/verify.sh:632-645`; `tests/fundamentals/test_verify_privacy.py:134-166`). Trim-before-length removes the generic-indentation false positive while preserving indented and unindented long-body refusal (`scripts/verify.sh:648-660`; `tests/fundamentals/test_verify_privacy.py:86-95`, `:190-200`). Cookie, machine-local path, tracked raw/scratch path, missing-registry, bounded-output, and `--tb=short` behavior have direct public-gate tests (`tests/fundamentals/test_verify_privacy.py:203-275`). AuthN/AuthZ, network input, persistence, supply-chain, and LLM-output boundaries are absent from this diff.

## Exact context adjudications

All seven current whole-file and exact-line hashes match the registry. The five corroboration records and one diagnostic record are typed-input, pure decision/routing fixtures permitted by the D1b Task 5 plan, not vendor qualification (`docs/workstreams/data-foundation/plans/D1b.md:368-400`); the independent batch review approved those pure rules and their routing/trust semantics (`docs/workstreams/data-foundation/reviews/D1b-batch-review.md:23-28`). The HFCL record is an existing retained-page Sales oracle: the inventory pins the HFCL consolidated HTML and its retained Dec-2024 column (`docs/specs/artifacts/stage1-source-inventory.md:39-55`), the retained test reads that body and checks the `quarters:data-table` / `Dec 2024` anchor (`tests/fundamentals/test_evidence_vendor_screener.py:38-60`), and the batch review approved the retained extraction path within its bounded scope (`docs/workstreams/data-foundation/reviews/D1b-batch-review.md:27-34`). These are privacy-collision verdicts. They do not create owner financial approval; the inventory expressly says it performed no owner financial decisions (`docs/specs/artifacts/stage1-source-inventory.md:3-5`).

| Record | Token and exact context | Whole-file SHA-256 | Exact-line SHA-256 | Verdict |
|---|---|---|---|---|
| 1 | `1200`, `tests/fundamentals/test_compare_corroboration.py:120`, synthetic conflict operands | `a5fda23716bb56942dd409ae6eaff718df17a15c4e7db4eb10dc549e78eab34a` | `ebbadd46a25b7174b3a16ef343e574bd19765c7f9795ee479407d9b4b042a92d` | **APPROVE** |
| 2 | `1200`, `tests/fundamentals/test_compare_corroboration.py:140`, synthetic anomaly operand | `a5fda23716bb56942dd409ae6eaff718df17a15c4e7db4eb10dc549e78eab34a` | `9f281036ba9042b028c8d316b6a6148e50e423e40495bef576c9e84bcc18031d` | **APPROVE** |
| 3 | `1010`, `tests/fundamentals/test_compare_corroboration.py:141`, synthetic definition-difference operand | `a5fda23716bb56942dd409ae6eaff718df17a15c4e7db4eb10dc549e78eab34a` | `d2d108ace804e6f1bf02ff8877e3d0282d8c8322743ea3961f6eec98ff95a120` | **APPROVE** |
| 4 | `1200`, `tests/fundamentals/test_compare_corroboration.py:200`, synthetic mismatch/agree operands | `a5fda23716bb56942dd409ae6eaff718df17a15c4e7db4eb10dc549e78eab34a` | `441fcc3ba38bda4137ff0e6efa2bd83e3e3c2b56b82369900a05bbaa9280e4f3` | **APPROVE** |
| 5 | `1200`, `tests/fundamentals/test_compare_corroboration.py:278`, synthetic anomaly-triage operand | `a5fda23716bb56942dd409ae6eaff718df17a15c4e7db4eb10dc549e78eab34a` | `0841d2c7634884aa0022717d3d7d2925f35988b4212efd0394c8b9f938c44e50` | **APPROVE** |
| 6 | `1200`, `tests/fundamentals/test_compare_diagnostic.py:148`, synthetic independent diagnostic operand | `8279b888574703406eb896b79ac12d3bef46a930a3a63296b93174341e471ef6` | `d7bda0c1898caafde2086282f277eeaacaa2b8374bafb75660981c65155aa83f` | **APPROVE** |
| 7 | `1012`, `tests/fundamentals/vendor_retained_support.py:29`, hand-read HFCL consolidated Sales, Dec 2024, crore | `5ab9697b0ae64f919d2da5202c3096e6b91de5d9676e9b77bd3a744e03e0af6a` | `1a35ebbcb227cf2345a31dc6bcab2ca1656e3d78742fdcec5fd9fe2465336c70` | **APPROVE** for the privacy-collision context; no new owner financial approval asserted |

Issues — Critical (must fix): none.

Issues — Important (should fix):

1. **[Important] `tests/fundamentals/test_verify_privacy.py:61-65` — the new historical-scope variable leaks into every isolated gate, so the required formal `VERIFY_SCOPE_BASE=05b2634` run cannot pass.** The fixture copies all of `os.environ`; the outer real gate necessarily exports `VERIFY_SCOPE_BASE=05b2634`, but that commit does not exist in each temporary Git repository. Every inner `verify.sh` therefore stops at `scripts/verify.sh:281-289` before exercising the intended rail. The reported 24-pass run (`scratchpad/execution/data-foundation-resume-2026-10-13/privacy-final-focused.log:1`) used the default environment and does not cover this invocation. A focused reproduction, `VERIFY_SCOPE_BASE=05b2634 ... pytest ...::test_indented_short_generic_metadata_is_not_a_pasted_capture`, failed at `tests/fundamentals/test_verify_privacy.py:94`: expected PASS, received `STOP invalid verification scope base`. Remove `VERIFY_SCOPE_BASE` from the fixture's copied environment, then set the temporary repository's own base only inside `test_historical_scope_replays_committed_identifiers_with_head_default` (`tests/fundamentals/test_verify_privacy.py:116-130`). Add a regression that runs at least one ordinary inner-gate case while the parent environment contains an unrelated historical commit string.

Issues — Minor (nice to have): none.

Evidence checked: the supplied focused log reports 24 passed with no skips or warnings (`scratchpad/execution/data-foundation-resume-2026-10-13/privacy-final-focused.log:1-2`). The six mutation declarations cover disabling the numeric rail, historical scope, cookie rail, paste rail, whole-file digest, and corrected trim order (`scratchpad/execution/data-foundation-resume-2026-10-13/privacy-mutations.log:1-6`), and the corresponding assertions exist at `tests/fundamentals/test_verify_privacy.py:116-247`. The parent-supplied historical helper replay reported 317 harvested identifiers, base `05b2634`, exit 0, and zero unresolved collisions; the helper path that produces that result is `scripts/verify_privacy_identifiers.py:47-74`. That helper replay does not cure the formal-gate test-environment failure above.

Code contract verdict: **ISSUES**.

Verdict: **BLOCK** — all seven exact financial-context adjudications are technically acceptable and the privacy rails remain narrowly fail-closed, but the historical scope required to prove the original STOP resolved makes the newly added privacy test suite fail before it tests those rails. Fix the fixture environment leak and rerun the focused 24 tests plus the formal historical gate.
