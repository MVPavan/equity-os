# D1b vendor input and first-party handoff review

Status: R1 ISSUES_FOUND / quality-security BLOCK, 2026-10-13. Fresh independent spec and
quality reviewers report all findings before the fix round. This ledger covers the isolated
producer/consumer mechanism; the actual reviewed release is separately accepted at `a4002bb`.

| ID | Severity | Concrete defect and required fix | Owner / status |
|---|---|---|---|
| V01 | Important | Pinned capture-free vendor ACQUISITION violates the existing empty-extractor SQL CHECK. Add reviewed narrow 0008 branch; preserve the pin, logical hash and real failure stage. | Root migration / OPEN |
| V02 | Important | Captured failed peers outside successful package members are rejected, and their deciding captures escape returned closure. Reprove their exact source/scope/context and include their captures and attempts. | Handoff owner / OPEN |
| V03 | Important | First-party ACQUISITION correctly has an empty extractor; stage-insensitive checks reject it and let a joint omission evade package completeness. Use stage-aware complete closure and prove positive/omission cases. | Handoff owner / OPEN |
| V04 | Important | Existing same-key vendor attempts can retain a wrong reason because repository reuse omits reason comparison. Compare full fixed recomposition before writes and after exact reload, excluding only assigned IDs/clocks. | Producer owner / OPEN |
| V05 | Important | Package-attempt completeness ignores semantic PDF context and is contaminated by other spec-context generations. Compare the exact source-derived context and complete scoped set. | Handoff owner / OPEN |
| V06 | Important | Whole-capture equality rejects valid additional sections/families/period scopes; interpretation selection is also too broad. Close the actual semantic request while preserving legitimate shared physical captures. | Producer owner / OPEN |
| V07 | Important | Vendor fiscal-setting evidence is checked only by ID; wrong kind/label/hash is accepted. Descriptor-read the actual source artifact and prove its kind, label, content, entity and setting value before qualification/write. | Producer owner / OPEN |

Root's original producer persistence plus publication compatibility is **1 failed / 14 passed**;
the failure is the real V01 SQL constraint. The consumer's eleven original guarded-PG cases
pass but omit the material negative-source variants. Three independent read-only probes
confirm the shared-capture, setting-source and acquisition-omission branches. The missing
gitignored raw fixture in the first consumer run was infrastructure-only; read-only primary
input binding resolved it, and it is not behavioral RED. The remaining anyio assertion-rewrite
warning belongs to that invocation, not product behavior.

Every owner must capture relevant regressions against the existing frozen callable helpers
before fixing them; new API/import failures do not count. Root owns migrations and guarded
PostgreSQL execution. No source rights, raw input, existing migration or financial oracle is
changed. Full Task 6 dispatch/resolution/run/replay and Stage 1 acceptance remain open.

The fixture-only post-release failure is separate: copying the now-real publication into an
unpublished private draft changes its refusal message. Root may omit only `vendor_publication`
from the private `_draft_root` copy, retaining every original assertion and actual release byte.

## R2 checkpoint and scoped producer acceptance

Fresh independent [spec R2](D1b-vendor-inputs-handoff-spec-r2.md) and
[quality R2](D1b-vendor-inputs-handoff-quality-r2.md) address V01/V03/V04/V05/V06/V07 in code.
V01's separately reviewed additive migration is accepted at `2d15c1d`: all twelve constraint/
retained-v1-upgrade cases pass. All thirty-eight producer cases pass, including the two genuine
existing-helper PG regressions and the concurrent shared-page section case. Root's integrated
producer/publication/legacy-run/actual-release matrix is **85 passed in 165.88s**; scoped Ruff
lint/format and strict mypy pass on all four changed producer/model modules. No adapter byte or
selected actual-release artifact changed. Root accepts only the guarded vendor-generation
producer scope (`eqos-u0u.19`), separately from the consumer and full Task 6 run writer/dispatch.

The two real R1 producer RED outcomes remain unchanged. Root authorizes resealing its test file
from `50bc416a446e9dd51fa5c8567934c3b6fa3731f2265cbc30ad8dd10759ea3cbd` to
`fd58cdb687a1f8c86c2ae063683669e5b35f5136f4a7bc353dc030bcbc1ab46f` for disclosed additional
source-artifact and concurrent shared-capture characterization. Neither original failed node
body or assertion is changed. The separate permanent existing-public-dispatch refusal test
remains unchanged and RED; it is not integrated as a passing mechanism test or silently waived.

V02/N01 remains Important: with no successful XBRL package member, the current handoff has no
independent failed-XBRL physical input witness. An unset hash must not match arbitrary captured
inputs. Root's fail-closed ruling requires an explicit refusal for that unsupported variant,
never a candidate attempt's own hash, wildcard, newest-row choice or omitted failure. Future
positive support is tracked as `eqos-u0u.24`, requiring a separately approved durable retained-
intake witness. Successful XBRL plus failed PDF retains its exact configured PDF input proof.

Root's first two R2 tests stopped at a private mapping fixture's dangling capmkt construction;
that proof is invalid and archived outside `scratchpad/gate`, never claimed as behavioral RED.
After removing the dependent construction consistently from that private, explicitly published
test mapping, both tests reach the actual consumer and fail **DID NOT RAISE**. The corrected
two genuine RED outcomes prove the null-binding and caller-expanded foreign-body cases before
guard implementation. This creates no source equivalence, actual approval or full-stage waiver.

## R3 consumer guard checkpoint

Fresh independent [consumer R3](D1b-vendor-inputs-handoff-spec-r3.md) approves V02/V03/V05 and
N01 under the fail-closed ruling. Missing successful-XBRL input authority now raises the typed
binding/witness refusal; an unset physical hash cannot match any attempt. Both corrected new
RED test bodies remain unchanged. The isolated twenty-case matrix passes in 55.46s; main's
consumer/first-party-generation/actual-release matrix is **29 passed in 79.01s**. Scoped Ruff
lint/format and strict mypy pass. This accepts a bounded checkpoint; positive missing-XBRL
support (`eqos-u0u.24`), the broader consumer task and full Task 6 stay open.

Root authorizes the R1 acceptance-file reseal from
`f72955c4c463493f80f2f886ccc72372d919ed002e7023b05331c5508cb7598e` to
`c33a7ef131b3c550c12b8482b4514b63fcb6f5b8cb7a279c21a0e848e046aaed` for disclosed added
foreign-context, omission and reverse-XBRL coverage and its corrected private mapping fixture.
All five original R1 failed-node outcomes remain; the already-green captured-peer joint
omission case remains characterization. The separate R2 proof contains exactly two genuine
post-fixture-correction consumer failures; no initial fixture failure is counted as RED.
