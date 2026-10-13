# D1b native implementation review

Status: R3 APPROVE, 2026-10-13. Codex session (handoff run): separate fresh
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

## Final R3 closure

Fresh independent spec and code-quality re-reviews both return APPROVE. Every N01–N12
finding is ADDRESSED; the original R1 and intermediate R2 refusals above remain historical
evidence. R2 left N08 open because callers could forge a reading's derived fields. The final
constructor re-reads each actual occurrence/direct pair under the current operand, rule and
scope, compares the complete reading, and constructs only from the re-derived object.

| ID | Final resolution |
|---|---|
| N01 | Common generation provenance applies to every pair; native UNMAPPED checks apply only to selected operands. Mapped neighbors remain valid; wrong-capture neighbors refuse. |
| N02 | Every operand must share a nonempty basis/period scope; partial eligibility cannot form a sum. |
| N03 | Mixed representations refuse before grouping or arithmetic. |
| N04 | Related tier refuses; unqualified output stays unproven; demonstrated tier requires evidenced whole-rule scope. |
| N05 | Blank fields, normalized labels and evidence predicates refuse at load. |
| N06 | Known currency/kind/target mismatch, both signs and fixed-ID permutation stability are proved. |
| N07 | Load-time decimal closure and defensive exact point/bounds conversion refuse unsupported arithmetic without rounding. |
| N08 | Public selector/name/key checks and full current-rule re-derivation reject forged values, intervals, periods, dimensions, sign reuse and false collisions. Genuine overlapping selectors remain ambiguous. |
| N09 | Exact target axes and permitted members are enforced at load and runtime. |
| N10 | Copied dimension mappings are immutable and serialize stably. |
| N11 | Non-value readings reject either populated numeric field; values require both. |
| N12 | Both first-party bridge rules explicitly require consolidated basis; standalone emits no bridge. Default legacy serialization stays unchanged. |

Root's final guarded integration reports **131 passed in 8.26s**, including retained source,
native persistence, actual by-ID reload, mapped-neighbor, dictionary/bridge, and legacy mapping,
interpretation-key and config-pin cases. Scoped Ruff lint/format and strict mypy also pass.
The actual count supersedes the earlier 132-case forecast. No new review findings remain.
This accepts the bounded drafts and native mechanism. The combined formal gate, joined release,
publication-bound generations, vendor runs and full D1b source acceptance remain separate gates.

## Orchestrator test reopening and reseal proof

Original RED outcomes are preserved, never retaken or relabelled. The original native feature
proof is one genuine unsupported-native load failure; the mixed-neighbor proof is one genuine
generation failure. The R1 fixes have 25 genuine failures and the final reading-binding repair
has six genuine `DID NOT RAISE` failures. Seven already-green R1 characterization cases and the
already-green real-overlap control do not acquire retrospective RED status. The first invalid
reading-binding setup attempt had four fixture-validation errors; it was discarded before code,
then corrected and captured as six genuine failures.

The original native test was changed only by mechanical import sorting/formatting. The R1
regression and consolidated-scope files received mechanical formatting plus disclosed later
characterization. The original store collision fixture incorrectly renamed a reading to a
nonmatching selector. Under the repaired API it fails with `PROVENANCE_MISMATCH`; root saved its
pre-reopening bytes (SHA-256 `b8414fc8c045a84f6424ecfb7424001e92c0d1eefe34b01e8c2901e08eb28c95`)
and observed that refusal. The corrected fixture loads two selectors that actually match the
same occurrence and derives both readings through the public reader. Its three assertions stay
unchanged: INVALID, INTERPRETATION_AMBIGUOUS, and the one real direct ID exactly once. The new
binding plus corrected collision tests pass **8/8**. The full store file is explicitly protected
by the native feature reseal.

The retained dictionary test's source fixture was corrected from an unsigned exceptional
contribution to the raw signed value: 467,906,000 + (-56,992,000) = **410,914,000**. Integer-crore
display precision is read from source, not from implementation output. The independent source
review agrees. Root replayed all four corrected dictionary tests against the pre-draft config;
all four still fail because v2 is absent. The Screener feature test retains its hand-read sums,
intervals, basis and date. Its extractor pin now uses the actual production bundle helper with
nine actual code members, including schedule shapes and interpretation digest semantics.
Replay against the pre-draft config still fails at the missing aggregate assertion. Thus the
corrected configuration-feature replay is **5/5 genuine RED**, not an API/import failure.

The source-oracle draft remains unchanged at SHA-256
`75e2493d535ca6444f4f0c2b18b5aae61971fa63db6b8c791dd3db73032e5a8d`.
Root explicitly authorizes the disclosed test-hash reseals using this proof, preserving every
recorded outcome and protecting the added store, mixed-neighbor and binding test files. Retained
numeric proofs establish these drafts only; missing vendor bodies and excluded additions remain
open and unproven.

VERDICT: APPROVE
