# Product completion legacy-check fixture repair

Work: `eqos-xa1`. Standard, test-first; user-authorized project completion. No product or approval-policy behavior changes.

The six existing reconciliation tests treat a superseded production goal as the prestate of an older transaction. The old manifest correctly refuses its changed bytes; refreshing real hashes cannot make the newer short goal satisfy the old protected line range. Preserve that refusal and all genuine approval records.

Own only `tests/equity_os_blueprint/test_reconcile_ledger_approval_contracts.py` and `tests/phase_0a/test_validate_phase_0a_evidence.py`. Production scripts, goal documents, real manifests/approval/ledger files and immutable inputs are forbidden writes. Preserve other agents' work. No commits, network, dependencies or cloud.

Implementation packet: `scratchpad/execution/product-gold-second-batch/legacy-check-diagnosis-report.md`, including exact source pointers and existing failure proof. Use a disposable clearly labeled synthetic goal/manifest/prestate satisfying the real builder's fences/protected span. Bind exact synthetic bytes and modes in the fixture-local manifest; pin only its digest on the freshly loaded test-module instance. Reuse public structural/extractor code and exact copied public immutable input bytes without changing their originals. Route the six tests through the synthetic root; keep all existing positive and rejection assertions. Add a behavioral red isolation oracle that delegates to real preflight, and a one-byte synthetic target tamper rejection. No current production hash may be presented as approval of that old transaction.

Remove only diagnosed unused imports/variables, sort imports, wrap lines and format these two test files. Do not add skips or weaken assertions. Characterize the live real-manifest drift read-only; it must continue to refuse.

Verification: installed pytest for the two exact files, Ruff lint/format for them, scoped diff check, and before/after hashes of reconciliation source, real manifest, its four targets and four immutable inputs. Then coordinator verification of wider `tests/equity_os_blueprint tests/phase_0a`. Passing proves synthetic behavior and corrected project test independence; it supplies no new real approval or executability of a real old reconciliation package.

Coordinator document review: APPROVE this bounded standard packet; the diagnosis establishes a test-only obsolete-fixture cause, with every genuine authority check and artifact preserved. No owner decision is required for the reversible test repair. Independent code review applies at the batch's final integration gate.
