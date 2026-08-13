# S01–S03 Independent Specification Review — r0

- **Reviewer:** `gpt-5.6-sol` / `xhigh`
- **UTC time:** `2026-08-13T02:35:17Z`
- **Baseline commit:** `fa4cd53605914bf10376ad9b6264971711ff1f07`
- **Scope state:** All reviewed files match the committed baseline; no scoped working-tree differences were present.

## SHA-256 binding

| Artifact | SHA-256 |
|---|---|
| Goal authority, complete file | `dabad7bfe3d2765a5ac9687376029d8587b4b2ac95bc03494155a974e5ddc67f` |
| Goal authority, reviewed lines 129–870 | `1650313cacaf9a6ae26eac637639f5783dfec967a7189751540a9c27469f3a0e` |
| Decision register v2 | `26d51b313688cb340ec57ef5e952f5497b7ca212add610b803a0033d5fad7164` |
| Disposition report | `a9021c154c3e84bd70b64a9dae99c29f760c2b3356b522f089a7b1a314322738` |
| S01 target | `d5c3e77c8cb14761d5bebbcb2d2ef5cd600eb21ef30371413363975e0db4ea9f` |
| S02 target | `0a4ed24d61feadb9b909c39612d0ce74812510da8423c5aaa7cf292608dda9f6` |
| S03 target | `a3cf78ad060ce7f713f6a3f042f2fc8b495f27812d079ccf1028f05779299c2b` |

## S01 — ISSUES_FOUND

Authority ownership, quoted register text, statuses, dependencies, T-4 disposition coverage, mixed activation classification, E-08 dormancy, typed external approvals, and amendment classification are otherwise consistent.

### Critical

None.

### Important

1. **The operating boundary can be read as authorizing private/internal use before A-01 receives its required decision.**
   **Location:** `docs/specs/equity-os-s01-product-identity-operating-distribution-boundary.md:33`
   **Load-bearing:** Yes
   The specification declares private/internal research as the initial posture unless a human approves something different. That conflicts with the draft’s statement that it approves no boundary and with the A-01 gate requiring an exact `PRODUCT_OWNER_DECISION` at line 96. The fail-closed outcome for a missing A-01 decision is therefore ambiguous: “private/internal allowed” versus “all use blocked.” Add an explicit invariant and fixture stating whether any product operation is permitted before A-01 is accepted.

2. **`OperatingBoundary.product_name` bypasses the unresolved A-09 identity decision.**
   **Location:** `docs/specs/equity-os-s01-product-identity-operating-distribution-boundary.md:60`
   **Load-bearing:** Yes
   The field hardcodes `Equity-OS` unless a later human rename occurs, while A-09 remains `Open` and `ProductIdentityDecision` is supposed to contain the approved name. `OperatingBoundary` has no identity-decision ID or digest binding, so it can represent an unapproved name as current. Require a content-bound reference to the applicable `ProductIdentityDecision`, and distinguish an unapproved working label from an approved product name.

### Minor

None.

## S02 — ISSUES_FOUND

A-05/C-13 ownership, exact register text and status, A-01/A-05 dependencies, T-4/R-3 coverage, active-only classification, consensus exclusion default, typed authority separation, and amendment guards are otherwise consistent.

### Critical

None.

### Important

1. **The S01 boundary dependency is declared content-bound but the interface provides no content binding.**
   **Location:** `docs/specs/equity-os-s02-source-rights-providers-consensus-policy.md:49`
   **Load-bearing:** Yes
   `ProviderRightsRegister` is said to be invalid unless its S01 reference is content-hash bound, but its listed fields contain only `boundary_id` and `boundary_version`; there is no boundary digest or typed evidence-reference field. A boundary could change without changing those identifiers, and the stale-reference fixture at line 117 would have no specified value to recompute. Add an exact boundary content digest or typed current-evidence reference.

2. **“Every used source” completeness is circular because no authoritative source-usage inventory is defined.**
   **Locations:** `docs/specs/equity-os-s02-source-rights-providers-consensus-policy.md:89`, `docs/specs/equity-os-s02-source-rights-providers-consensus-policy.md:116`
   **Load-bearing:** Yes
   The contract requires exactly one current rights record for every used source, but it does not identify the independently authoritative, content-bound inventory against which `records` is compared. Testing a supplied missing-source fixture does not prove real program completeness. Define the source-usage inventory/reference and require exact set equality between used source IDs and current rights records.

### Minor

1. **The operational approval row does not enumerate all A-05 dimensions.**
   **Location:** `docs/specs/equity-os-s02-source-rights-providers-consensus-policy.md:107`
   **Load-bearing:** No
   The row explicitly names automation, caching, retention, derived outputs, and redistribution, but omits commercial use, account limits, point-in-time availability, and replacement-path use. Other invariants partly cover these dimensions, but the approval and acceptance-test matrix should enumerate every applicable A-05 dimension so none relies on implication.

## S03 — ISSUES_FOUND

E-06/E-07 ownership, exact register text and status, disposition 6.7 coverage, dormant-only classification, tool isolation, due-diligence/adoption distinction, typed external approvals, fail-closed tests, and amendment guards are otherwise consistent.

### Critical

None.

### Important

1. **E-06 activation does not mechanically bind or enforce its A-05 dependency.**
   **Locations:** `docs/specs/equity-os-s03-external-tool-due-diligence.md:50`, `docs/specs/equity-os-s03-external-tool-due-diligence.md:54`, `docs/specs/equity-os-s03-external-tool-due-diligence.md:133`
   **Load-bearing:** Yes
   The request contains only `boundary_version` and generic evidence references. The predicate requires merely that an A-05/S02 scope “exists,” not that the exact content-bound rights record is current and that A-05 has satisfied the dependency state required for E-06. Consequently, a proposed request plus human activation resolution could transition E-06 while A-05 remains unresolved. Add typed A-05/S02 record IDs and digests and require the exact prerequisite state before E-06 activation.

### Minor

None.

## Batch verdict

**ISSUES_FOUND — batch is not internally approvable at r0.**

The principal batch defect is the unclosed boundary-reference chain:

`S01 OperatingBoundary → S02 ProviderRightsRegister → S03 E-06 activation`

The documents require content-bound, stale-detectable dependencies, but the interfaces do not carry sufficient typed IDs and digests to enforce that requirement mechanically. S01 also leaves pre-A-01 operating authorization and pre-A-09 product naming ambiguous.

## Overall verdict

**ISSUES_FOUND. No S01–S03 delegated artifact approval should be recorded from r0.**

No Critical findings were found, but the unresolved Important findings are load-bearing and block a clean delegated-goal verdict. A future `CLEAN` verdict would constitute approval only under delegated goal authority; it would not represent or imply the user’s personal approval.