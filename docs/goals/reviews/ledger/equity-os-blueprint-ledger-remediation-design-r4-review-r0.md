# Independent exact-byte review: ledger remediation design r4

## Review binding

- Reviewed design: `docs/goals/reviews/ledger/equity-os-blueprint-ledger-remediation-design-r4.md`
- Reviewed-input SHA-256: `c1ab125880ec1895a344b57f7aaef8d372836fa0ded9c900a1aae9284b295e00`
- Reviewer model: `gpt-5.6-sol`
- Reviewer effort: `xhigh`
- Codex session ID: `019ffa0b-0f01-7d81-b3d2-fb06c917e919`
- Review timestamp: `2026-08-13T07:40:33Z` UTC
- Scope: the three Important r3 findings and new load-bearing breakage introduced by r4; no broad blueprint remapping.

## Focused checks

1. **Important r3 finding 1 — closed.** The literal question in r4 §5.2 binds the exact r4 path and externally substituted r4 digest, the predetermined review path and externally substituted review digest, the required clean verdict, reviewed-input digest equality, and the required reviewer lane. Sections 5.3 and 6.2 require the completed question and response bytes to be recorded after approval and require structural reconciliation to hash and compare every bound field against the immutable review artifact before any canonical write.
2. **Important r3 finding 2 — closed.** R4 §3.6 specifies the exact `REQ-DISP-R-1-NO-IMPLEMENTATION` `UNRESOLVED` object with empty `evidence_ref_ids`. Sections 3.2, 7.2, 8.1, and 8.3 consistently preserve the rejection record as historical metadata, require a current satisfied requirement plus fresh content-bound review before current proof can exist, permit structural reconciliation while proof is false, and require preimplementation and terminal reporting to emit the unmet-proof blocker. Mechanical comparison confirmed the declared object equals the live requirement with only `status` and `evidence_ref_ids` reset; the existing controlled-state history contains the unchanged rejection record and contains neither mutable proof field.
3. **Important r3 finding 3 — closed.** All three candidate and all three post-replacement structural, preimplementation, and terminal invocations explicitly pass required `--repo-root .`; the post-replacement terminal command is explicit and uses the protected candidate-extracted terminal bytes.
4. **Preserved invariants — pass.** Fresh hashes matched the five immutable baselines: active goal `dabad7bfe3d2765a5ac9687376029d8587b4b2ac95bc03494155a974e5ddc67f`, ledger `51091042dae87d2f41fbbf02d77ab1619c6a1008a022baec4233c44a0e295e13`, human review `54c1e183def8e0b1b91504effbf20c233b3d1352fd65d4910e89c2b913ee5702`, v2 register `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164`, and disposition report `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738`. The target remains exactly 213/169/44. Independent range expansion produced 144 unique IDs and digest `bf6fee00d0f4510316b42b50ec13f74148df9ed44e472f2ad8be114ee3add894`. The live 454-transition prefix projection reproduced digest `d4ce9646438d388bf26c8faa82d689209296726af2c29d1e56942218c613d9b1`; HR-0001..3 remain `OPEN_BLOCKING` with zero resolutions.
5. **Authority and failure boundaries — pass.** R4 retains exactly six allowed canonical paths, prohibits canonical mutation before bound approval, preserves the Git index and unrelated paths, requires candidate-only validation before replacement, and retains journaled compare-and-swap rollback with `RECOVERY_REQUIRED` fail-closure. Digest refresh is explicitly barred from becoming delivery, approval, or no-implementation proof.

## Material findings

None. No Critical or Important defect was found in the r4 delta.

Verdict: CLEAN
