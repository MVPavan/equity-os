# D1b first-party generation review

Status: R2 COMPLIANT; code-quality and security APPROVE, 2026-10-13. This covers Task 11,
not the actual joined release or the Task 6 closed-ID consumer.

Root's frozen integration reports **8 passed in 15.70s**, including exact v1/v2 identity,
unchanged v1 by-ID payloads, repeated reuse, cutoff modes, extractor changes, partial attempts,
publication refusal and qualification-setting refusal. Earlier guard plus exact-ID/legacy cases
report **6 passed**. These are scoped mechanism results; acceptance awaits independent review.

## Orchestrator mechanical reopening proof

The original public-ingest refusal test reached existing code before the fix, did not raise,
and wrote 902 occurrences plus 910 interpretations. Its one genuine failed outcome remains
unchanged in the formal RED record. New producer API cases are disclosed characterization;
no missing API/import or infrastructure error is relabelled behavioral RED.

Root's fresh format check identified only a three-line `load_mapping_set` call that Ruff requires
on one line. Root saved the sealed original bytes, folded that call, and compared the complete
parsed Python ASTs with location attributes omitted: **identical**. Every test, helper, financial
expectation and assertion is preserved. Original SHA-256:
`c51ba560581f9941018f0b97ad6e23270b7719e8ca8772b423fb4a6744fbc19f`.
Formatted SHA-256:
`9f72d30560727cd2816ad94430d6e6f63cd347fb42d4f7ab50d277be00d688d6`.

This document explicitly authorizes the root-owned format-only reseal and protection of the new
producer test file; it grants no code-review, release, qualification or full-phase approval.

## R1 finding and repair

R1 found one Important defect: S1 may supply interpretation context while a concurrent S2 is
stored before those rows. The initial handoff refuses, but a later retry under S2 previously
reused S1 rows because their timestamps were later than S2. Timestamps cannot establish context.
The corrected public-producer RED reaches that retry and fails with `DID NOT RAISE`; its one
genuine outcome is preserved. The earlier missing-fixture ERROR never reached product behavior
and is preserved separately outside valid gate proofs, not counted as behavioral RED.

The bounded repair captures and reloads one actual settings record, uses its exact month during
ingest, and stores its complete identity/hash under reserved immutable context trace metadata in
every new v2 interpretation. Reuse validates that context before returning rows; the handoff
reloads the record by ID and verifies all traces. A different setting requires a fresh mapping
version. Existing SQL schema, numeric values, input digests and legacy v1 trace/serialization stay
unchanged. Trace metadata is stored; a settings foreign key is not invented.

Root's integrated run after the repair reports **13 passed / 1 failed**: the failure expected
`VersionContentDriftError`, while the publication layer's earlier model-consistency check now
raises `VendorConfigPublicationError`. Root explicitly reopened only this typed-refusal
expectation to accept those two named errors with specific messages; the forged object and
finally-block table-count equality remain unchanged. The amended refusal and the actual race
then pass **2/2**. The corrected setting-context RED and original ingest-guard RED remain intact.
Final combined verification and independent spec/quality acceptance are still pending.

## Additional authorized test amendments

The producer test's pre-context sealed SHA-256 is
`9771c36d28210187979b354ca10a2f9a948873781e4ad3e08cd5376344ae8688`; no byte snapshot was saved,
so no complete before/after AST claim is made for that amendment. Root authorized replacing the
old unstored-context flag assertion with explicit trace-stored/foreign-key-absent assertions and
adding actual record/hash/per-row trace checks. Financial, ID, clock and closure assertions stay.

The subsequent narrow typed-error amendment changes producer-test SHA-256 from
`7157284a7e0398cdd09f9e23d6a274aba3eae8b722ba944a967ac8f6242c9bfc` to
`39e8c017d099563851fe4a5a4bec796d6eb4b1d94fb4206a93ed6dd0ec7bc5ad`.
Its AST delta is the named exception import and the explicit exception tuple/message expression;
it does not accept generic `ValueError` or weaken zero-write checks. Root authorizes the disclosed
reseals and protection of the corrected concurrency test using this proof. This is mechanism
evidence; real committed publication and Task 6 by-ID consumption remain required.

## R2 acceptance and minor repair

Fresh independent R2 spec review finds the Task 11 producer mechanism COMPLIANT: the exact
persisted settings identity is used during ingest, stored in every v2 interpretation trace and
checked on reuse and handoff. All R1 findings are addressed; no new Critical or Important
specification, quality or security finding remains. Code-quality and security verdicts are
APPROVE. The actual released configuration, Task 6 consumer and full D1b remain outside that
mechanism acceptance.

R2 identified one Minor in-memory issue: `model_copy(update=...)` bypassed the immutable trace
validator. Before its fix, the new mutation regression genuinely failed with
`DID NOT RAISE TypeError`. The bounded repair revalidates an `Interpretation` from its actual
typed Python field values and freezes the nested JSON-native context. It preserves the input
row, identity, numerical values, digests and clocks. Both direct mutation/serialization cases
pass; root's fresh final producer/context/guard suite is **11 passed in 17.72s**. Root also
verified Ruff lint, format and strict mypy on the frozen source/test scope.

Root authorizes protection of `test_first_party_context_immutability.py` in the existing guard
proof, preserving all original RED outcomes and the corrected race proof. This authorization
records the added regression; it grants no actual publication, Task 6 or complete phase approval.
