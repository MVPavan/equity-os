# D1b native implementation review

Status: R1 REQUEST_CHANGES, 2026-10-13. Codex session (handoff run): separate fresh
spec, code-quality and retained-source/config reviewers inspected the frozen batch.
This technical review grants no financial, publication or owner-decision authority.

The retained PostgreSQL integration reached product code and reported 53 passed / 6 failed.
All six required retained Screener cases failed because the native-only UNMAPPED guard ran
before selector filtering and rejected an unrelated legitimate mapped row. The existing
guarded PostgreSQL service is reachable with authorized sandbox escalation; no database
configuration or Docker change is needed. An isolated generic native storage case passed,
but this does not establish the retained mixed-generation acceptance.

## Exhaustive R1 finding ledger

| ID | Severity | Finding | Required resolution |
|---|---|---|---|
| N01 | Important | All rows receive the native-only UNMAPPED guard before selection | Preserve generic current-generation identity/pin guards for all pairs; apply native-only checks to matched inputs; mixed mapped/native retained and synthetic tests |
| N02 | Important | Native applicability is checked one operand at a time | Whole-rule/group basis and period eligibility intersection; disjoint scopes produce no partial aggregate |
| N03 | Important | Mixed representations can enter one period/dimension group | Refuse or segregate representation before arithmetic; prove no HTML/JSON sum |
| N04 | Important | Native configuration can grant RELATED_NOT_EQUIVALENT without whole-rule proof | Native result remains unproven; demonstrated promotion requires actual valid whole-construction scope |
| N05 | Important | Empty/whitespace selector evidence passes load | Refuse blank native fields, labels and evidence predicates |
| N06 | Important | Required known-unit/target/sign/permuted-order cases are absent | Prove known currency/kind/target mismatch, both signs exactly once, stable order and provenance under permutation |
| N07 | Important | Accepted division can produce nonterminating values or bounds unsupported by Decimal/SQL | Fail closed at load where decimal closure cannot be established; typed defensive refusal, no migration or rounding |
| N08 | Important | Public native read/construct accepts wrong selector or operand-name binding | Validate selector inside read and exact rule/name/key binding inside construction |
| N09 | Important | Target dimension compatibility is only a boolean check | Validate exact template axes and permitted closed-list members at load/runtime |
| N10 | Important | Frozen native dimension mapping is mutable under an unchanged content pin | Copy into immutable mapping with stable serialization; prove mutation refusal |
| N11 | Minor | MISSING/INVALID readings permit amount-only or interval-only states | Require both absent for non-VALUE; require both present for VALUE |
| N12 | Important | First-party bridge basis is inferred only from a source name/upstream path | Explicit enforceable consolidated eligibility and standalone negative at the public generation seam |

The source/config reviewer independently confirmed all 259 original dictionary rows are retained,
the one new row is correctly DERIVED and unproven, the SONACOMS signed exceptional contribution
and comparison interval are correct, and both Mar-2025 retained liabilities sums and intervals
match their raw date/basis/precision evidence. Total Liabilities, first-party NCI, and all seventeen
excluded additions remain outside the native sum/addition scope. These findings require no
financial definition change.

Root recorded a genuine mixed mapped-neighbor RED before the fix. The supplemental fix round
adds proving cases before code and preserves the original recorded acceptance assertions.
Mechanical formatting, source-correct fixture amendments and added characterization cases need
an explicit orchestrator reseal with disclosed before/after evidence; original RED outcomes must
remain intact. Task 13 alone joins accepted drafts and actual reviewed release content.

## Authority ruling

Fail closed for N12: add explicit consolidated scope to the evidenced first-party bridge rather
than broadening its applicability based on a source identifier. Preserve default legacy rule
serialization and v1 pins. Fail closed for N07: reject arithmetic whose exact point or uncertainty
bounds cannot fit the existing Decimal/SQL persistence contract; never round an exact Fraction
or change immutable migrations. These are technical contract enforcements of the approved scope,
not owner financial judgments.

R1 verdict: REQUEST_CHANGES. Re-review and stable integrated verification remain pending.
