# D1b native construction preparation

> **Superseded 2026-10-14** by [D1b-cleanup.md](D1b-cleanup.md): the design this plan describes was deleted or simplified; kept as history.

Status: approved-for-implementation, r3, 2026-10-13. Independent Codex session (handoff run) re-review APPROVE; all original/r2 Important findings addressed. Formal historical gate prerequisite passed before dispatch.

**Origin:** approved `docs/workstreams/data-foundation/plans/D1b.md` Tasks 3/13 and data spec §2 known Screener traps. Code-read finding: existing constructions require mapped canonical operands, but required source-native Borrowings and Other Liabilities are deliberately not canonical standalone mappings.
**Goal:** retained Screener native operands produce the specified `liabilities_incl_nci` aggregate with exact arithmetic and durable source provenance, completing this draft prerequisite for Task 13 without inventing canonical operand rows.
**Out of scope:** shared v2 publication, new dictionary rows, live vendor capture, real missing Tijori/Upstox proofs or Stage 1 closure.
**Out of scope:** first-party NCI adjustment of the vendor amount or invented borrowing/equity definitions.
**Constraints:** “Financial logic: exact `Fraction` arithmetic, fail closed, never zero-fill, never backdate.”
**Constraints:** “Expected values come from source documents, never from code output.”
**Constraints:** “Tests use `eqos_test_*` databases only.”
**Constraints:** migrations `0001`–`0006` and published v1 configurations are immutable; no raw mutation, new credentials or pushes.

## File map and producer handoff

- Shared evidence owner: `src/fundamentals/evidence/mapping.py`, `interpret.py`, `capture_interpretation.py`; new `native_construction.py` for typed native reading/arithmetic; new `mapping_models.py` only for the necessary mechanical model split under the 800-line ceiling, with existing mapping imports re-exported and v1 behavior retained. New `tests/fundamentals/test_native_construction.py`, `test_native_construction_store.py` own proving cases. Root coordinates any repository change; current SQL storage is sufficient.
- Screener draft owner: `config/mappings/screener/v2/constructions.yaml` and new `tests/fundamentals/test_screener_native_construction.py`. It consumes the reviewed shared contract after Task 14, then returns the completed draft to Task 13's sole release owner.
- Neither owner edits shared v2 index/source authority, published v1, other workers' tests, existing red contracts or raw captures.

### Task 14: Add source-native operands to reported constructions

Goal: a construction can read actual native occurrences without converting their direct UNMAPPED interpretations into invented MAPPED canonical facts; only the evidenced canonical aggregate is emitted.

Stage: `eqos-u0u.1`.

Files:
- Create: `src/fundamentals/evidence/native_construction.py`, `tests/fundamentals/test_native_construction.py`, `tests/fundamentals/test_native_construction_store.py`.
- Modify: the shared evidence paths above; only a minimal mapping-model split if necessary, preserving existing import APIs.
- Test: the new seams plus existing mapping/interpretation/generation and repository regressions.

Interfaces:
- Consumes: actual `Occurrence`, its stored/reserved direct `Interpretation`, `CaptureScope`, `ConstructionRule`, `NormalisationPolicy`, dictionary target and immutable mapping-member content.
- Produces: a mutually exclusive native-selector alternative to `ConstructionOperand`; proposed `NativeOperandReading` and `read_native_operand` in the new module; proposed `construct_native` orchestration, returned `Interpretation` with existing `CONSTRUCTED` result shape and real relational `operand_interpretation_ids`.

Approach: keep mapped-operand constructions and v1 serialization/results unchanged. Loader validates native selector scope, operand uniqueness, expression references and actual canonical target without requiring fabricated operand canonical IDs. Group by exact period/dimensions within one requested source/surface/schema/capture/representation/entity/basis/framework and interpretation pin tuple. Raw normalization uses declared sign/scale/unit/precision and existing policy. Preserve raw missing/null/dash/invalid meanings, invalid precedence, duplicate ambiguity and incompatible-group refusal; no implicit zero rule. Build only the result's legitimate dictionary key from evidenced group/unit/scope. Keep direct rows UNMAPPED, retain actual operand interpretation/occurrence/capture identities, and pin normalized amounts, intervals, arithmetic and selectors in deterministic JSON-safe transform traces/digests. Exact fractions serialize as p/q or terminating decimal strings, never float. Native inputs do not become qualified canonical operands: construction tier stays EQUIVALENCE_UNPROVEN unless a separately demonstrated whole-construction scope proves otherwise. Existing SQL operand FKs/capture trigger and repository JSONB/link readback are the persistence boundary; no new migration or CalculationTrace operand category is needed.

Verification: focused new tests prove exact sum/precision intervals and status failures; actual isolated-PG insertion/reload preserves UNMAPPED direct rows, constructed target, all relational operand refs and trace content, and refuses another capture's operand. Existing v1 mapping and capture interpretation cases remain green. Root runs the combined full quality/red-proof gate after source freeze.

Test seams: `load_mapping_set`, `interpret_generation` and `EvidenceRepository` read/write round-trip; explicit pre-implementation RED proof `d1b-native-construction`. Synthetic arithmetic/failure tests prove the mechanism; retained source literals are reserved for Task 15 and never inferred from implementation output.

Dependencies: stable Task 2 contract, independent approval of this supplemental plan, and prior recorded gate findings investigated with a fresh formal gate. No Task 13 release dependency.

Risks: test-first; source identity, precision, missingness and generation provenance cross trust/financial boundaries. Transform JSON alone cannot substitute for relational operand links. No weakening first-party package membership or v1 pins.

#### Normative native configuration and API contract

All names below are proposed new interfaces; they do not already exist. `ConstructionOperand` keeps its original `name`, `mapping_entry_id` and `dash_rule_id` mapped form. Add `native: NativeOperandSpec | None`; exactly one of `mapping_entry_id` or `native` must be present. A construction-level validator requires all operands to use the same branch, so mixed mapped/native is invalid. For legacy mapped operands, omit the new default field in every model dump; preserve the old field keys, values and import API exactly. Native operands serialize their explicit native branch and do not invent a mapping entry id.

`NativeOperandSpec` is frozen/extra-forbid and contains `selector: Selector`, `sign: Literal[-1,1]`, `unit_transform: UnitTransform`, `precision_rule: PrecisionRule`, `value_kind: ValueKind`, `currency: str | None`, `period_nature: PeriodNature`, `dimension_members: Mapping[str,str]`, nonempty `bases: frozenset[Basis]`, nonempty `period_kinds: frozenset[PeriodKind]` and nonempty `evidence_ref: str`. Native selection requires each occurrence to match this evidence-scoped basis set and actual period kind as well as `CaptureScope`; an inapplicable native rule emits no aggregate, never broadens a consolidated rule to standalone. The native branch has no dash-to-zero rule in this supplement. Native rules require a named source, known surface/schema, nonempty selector evidence, distinct operand names, complete/exact expression-name coverage, no overlapping selectors and unit-algebra-compatible target. Invalid/mixed/missing branch, empty selector evidence, duplicate names or overlap fails load before generation. Existing mapped dash behavior is unchanged.

For the Screener liability rule, every selector is the existing label form with `statement_family=BALANCE_SHEET`, its exact source label and `section_equals=balance-sheet`; its spec declares `CURRENCY_AMOUNT`, `currency=INR`, `period_nature=INSTANT`, `dimension_members={}`, declared precision and scale-to-base-unit. The retained liability member explicitly declares `bases={CONSOLIDATED}` and `period_kinds={INSTANT}`; no standalone evidence is inferred. The source label aliases must come from the actual retained parser output and independent raw rows. Empty dimensions are permitted only for the evidenced scalar BS context; unexpected axes/members are refused, not discarded. Different legitimate balance-sheet dates form separate groups; no adjacent-column or cross-date pairing. The existing dictionary target must have compatible monetary unit algebra, instant period nature and dimensions.

Proposed `NativeOperandReading` fields: `operand_name: str`, `occurrence: Occurrence`, `direct_interpretation: Interpretation`, `state: NativeReadingState` (VALUE/MISSING/INVALID), `amount: Fraction | None`, `interval: Interval | None`, `value_kind: ValueKind | None`, `currency: str | None`, `period: PeriodInterval | None`, `dimensions: DimensionSet | None`, `reason: InterpretationReason | None`, `trace: ReadOnlyJson`. VALUE requires amount/interval and a complete typed group; MISSING has no amount/interval; INVALID retains every evidenced part without fabricating a complete key. The original raw occurrence and relational direct interpretation remain separate; this reading is never a stored pretend canonical fact.

Proposed signature: `read_native_operand(occurrence: Occurrence, direct: Interpretation, *, operand: ConstructionOperand, rule: ConstructionRule, scope: CaptureScope) -> NativeOperandReading`. Proposed signature: `construct_native(rule: ConstructionRule, readings: Mapping[str, tuple[NativeOperandReading,...]], *, scope: CaptureScope, qualification_for: Callable[[PeriodInterval, DimensionSet], QualificationContext], recorded_at: datetime) -> tuple[Interpretation,...]`. `interpret_generation` supplies the actual occurrence→direct-row pairing and routes only an all-native rule to this path. Its trusted per-group `qualification_for` derives schema, surface, group period kind, actual basis and proven conditions; first pass uses no proofs, second uses `_proofs` keyed by period/basis from the same capture, preserving the existing two-pass discipline. Only demonstrated whole-construction qualification can overcome unproven native inputs. Initial Screener rules have tier EQUIVALENCE_UNPROVEN and no qualifying sample claims; numerical validity alone never promotes. The callback is internal composition, not an external authorization claim. Extend `CaptureScope` with an optional current `expected_extractor_pin: VendorExtractorPin | None`, required for native rules, default absent for legacy mapped rules. The adapter/caller derives it from its actual content-pinned extractor bundle, never a fabricated historical hash. Record its version/hash in native input digests/traces; compare stored occurrence/direct extractor versions to it. Existing direct interpretation columns carry versions, not content hashes: dictionary/mapping/policy content hashes come from their loaded pinned scope objects, and extractor content authentication remains the common intake/version-pin boundary. Do not claim a nonexistent direct-row hash field was checked.

#### Provenance, key and outcome matrix

Before reading any amount, require a stored/reserved non-null interpretation id and occurrence id, `DIRECT` + `UNMAPPED`, no mapping entry/canonical id/key/value/interval, and that exact occurrence id. Match direct/capture representation and capture id, source/surface/schema, context basis, entity/basis/framework and current dictionary/mapping/policy/extractor versions against `CaptureScope`. The direct-row digest remains exactly the current `input_digest({"occurrence_id": occurrence.occurrence_id})`; compare that unchanged formula for the occurrence linkage. Check dictionary/mapping/policy/extractor versions and the actual expected extractor pin separately; loaded config/version-pin boundaries establish their content hashes. Put content hashes only in the NEW native construction digest/trace, never rewrite legacy direct digests or pretend those digests authenticate all pins. A direct row with any scope/version mismatch is refused; an older stored row with identical immutable occurrence, input digest and exact current pins may be reused without a latest lookup. Generation requires a one-to-one current occurrence/direct-row pairing; never select an old or duplicate direct row by latest lookup. Any identity, linkage, basis/framework, source, representation or pin mismatch raises proposed `NativeConstructionError` with defect PROVENANCE_MISMATCH before any new generation is committed. Applied SQL capture guard is supplementary to these Python guards.

Resolve raw units via the pinned `NormalisationPolicy.units` `UnitRule`; reuse/factor the existing exact number/interval normalizer, never fork its arithmetic. Validate raw sign is ±1, scale is an integer supplied by the evidenced source extraction, and numeric precision is EXACT or supported FINITE with its declared precision. The spec sign and raw sign/scale all participate exactly once in normalization. Unit rule, each operand spec and dictionary target must agree on value kind, currency, period nature and dimensions. Only then build the result's `MeasurementKey` with actual entity/basis/framework, target id, currency, kind, exact date/dimensions. There is no operand canonical key.

| Condition | Native aggregate result / refusal | Required proving case |
|---|---|---|
| No operand selector matches anywhere | Emit no construction; direct UNMAPPED rows remain | Empty/nonmatching group |
| VALUE: readable exact number with supported metadata | MAPPED/CONSTRUCTED amount + interval when all operands VALUE | Exact signed/scaled sum and interval |
| ZERO_PRINTED with actual printed zero | Same VALUE path, zero from source only | Printed zero contributes exactly zero |
| NIL, DASH, BLANK, NOT_PRESENTED, SOURCE_NULL or absent required row | Value-less MAPPED/CONSTRUCTED for an otherwise typed group; trace state MISSING and missing operand names; no fabricated absent-row id | Each marker and absent-row case; no zero fill |
| Unreadable VALUE text or contradictory ZERO_PRINTED lexeme | INVALID/UNREADABLE_CELL; no amount | Bad lexeme with a missing other operand still INVALID |
| Numeric VALUE/ZERO with unsupported precision | INVALID/PRECISION_UNSUPPORTED; no amount | Unsupported precision, including mixed missing |
| Unknown raw unit, wrong value kind/currency or incompatible operand/target unit algebra | INVALID/UNIT_MISMATCH; preserve only known key parts and trace defect | Unknown unit, count-vs-money, INR-vs-USD, wrong target |
| Unknown/unsupported period, duration for this instant rule, unexpected dimensions, malformed sign/scale | Raise NativeConstructionError with PERIOD_UNRESOLVED/PERIOD_MISMATCH/DIMENSION_MISMATCH/NATIVE_METADATA_INVALID; no new interpretation generation committed | Each metadata mismatch; retained raw evidence stays untouched |
| Different legitimate instant dates | Separate groups; never combine; incomplete groups are value-less | Borrowings at one date and liabilities at another |
| Duplicate native candidates for one operand/group or one occurrence matching multiple operand selectors | INVALID/INTERPRETATION_AMBIGUOUS, no amount; attach every real matched candidate id exactly once | Duplicate row and runtime selector collision |
| Any wrong occurrence/direct link, current pin, source/capture/representation, entity/basis/framework | Refuse generation with PROVENANCE_MISMATCH | One negative per provenance dimension, including old direct row |

Within a typed group, semantic INVALID beats missing; unsupported numeric precision is not inferred for a missing marker. No explicit period is invented for a refused group. All actually matched current operand interpretation IDs are included in invalid/value-less results; absent operands have no invented IDs. Operand links use existing FK-backed `interpretation_operands`; raw-occurrence IDs are additional trace detail. Result tier remains unproven unless real whole-construction qualification evidence supports promotion; numerical validity never supplies equivalence proof.

#### Explicit compatibility, pin and replay verification

Before model changes, characterize committed v1 construction dumps/loads, complete mapping content pin and a fixed pure interpretation result (status/value/interval/tier/trace/operand ids). The new tests require byte-for-byte legacy model serialization/pins and field-for-field legacy results after extension, without editing v1 YAML or old assertions. This characterization is GREEN baseline, not invented RED. Native feature RED uses the existing `load_mapping_set`→`interpret_generation` seam with a valid proposed native config; rejection of its unsupported branch is a missing-feature failure, not a missing-import or infrastructure proof.

Prove native selector/expression member bytes join the draft mapping-set content hash: changing one operand/member changes that hash, while published v1 hash stays unchanged and no shared v2 index is written. Under identical actual pins and input rows, repeated generation has the same sorted group order, rule operand order, candidate ordering, input digest, JSON-safe trace and status/value/interval/tier. Reserved database IDs remain explicit provenance; content digest uses stable occurrence/direct context consistently and must not depend on dictionary iteration order. An isolated PG by-id read/reload reproduces the complete constructed row, relational UNMAPPED operand rows and trace; no latest/as-of operand recovery is permitted. Task 15 separately seals hand-read raw literal/date/precision/body-hash evidence before draft implementation. Root broad gate includes all existing first-party and modern/legacy run/replay tests.


### Task 15: Complete the retained Screener liabilities draft

Goal: same-page, same-period native Borrowings plus Other Liabilities produce `liabilities_incl_nci`; Total Liabilities remains unmapped and no first-party NCI enters the vendor sum.

Stage: `eqos-u0u.1`.

Files:
- Create: `tests/fundamentals/test_screener_native_construction.py`.
- Modify: `config/mappings/screener/v2/constructions.yaml` only, before final publication.
- Test: the new retained extraction→interpretation→store seam; existing Screener adapter cases unchanged.

Interfaces:
- Consumes: Task 14 reviewed native operands and normalization, Task 3 page extraction/common authorization, real source-bound `Occurrence` and existing dictionary `liabilities_incl_nci` target.
- Produces: completed unpublished Screener construction member and evidence report handed to Task 13; no final shared pin or release.

Approach: independently read literal Borrowings and Other Liabilities plus printed balance-sheet date/precision from authorized retained pages. Select only that page's direct source rows, sum exact signed amounts/intervals under declared normalization, and store linked constructed interpretations. Assert source-native row IDs are not canonical targets, direct rows remain UNMAPPED, and Total Liabilities is excluded. Use actual local registration/store clocks for retained persistence and refuse unsupported/missing/duplicate/opposite-basis/cross-capture operands. No per-company correction or borrowed first-party amount. Result remains unproven without real qualifying sample evidence. Record scope/table/column/body hashes and independent operands before implementation; keep the draft unpublished.

Verification: retained literal sum and propagated precision agree with hand-read source inputs; actual isolated PostgreSQL readback preserves both direct UNMAPPED inputs, constructed aggregate and honest clocks. Focused source/negative cases and scoped quality checks pass; Task 13 combined review/publication remains separate.

Test seams: `extract_screener_page` → `interpret_generation` → `EvidenceRepository` using genuine retained body hashes, not generated sections/comparator output. Capture `d1b-screener-native` RED before writing the construction draft.

Dependencies: Task 14 reviewed handoff and existing Task 3 retained adapter. Task 13 consumes the completed draft only after this proof.

Risks: test-first dynamic financial behavior; native operands and dates cannot be assumed from another source, page or period. Missing capture proof does not waive this available-source engineering prerequisite.
