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
