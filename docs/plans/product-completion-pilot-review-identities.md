# Pilot review identities implementation plan

**Status:** PLAN_READY; candidate for plan review before implementation.
**Origin:** Explicit bounded request; existing export packets `eqos-4j2.12` and `eqos-dii`. No new specification or tracking record needed.
**Goal:** Stable guidance review identities and deterministic figure assertions, preserving legacy review binding.
**Mode:** standard; two independently reviewable defect tasks.

## Concerns and boundaries

Legacy reports contain only `metric_label`; recovering a canonical metric from that label would fabricate identity. Existing sessions persist claims and bind `report_json_sha256` to original report bytes. Relabeling those claims or hashing reserialized models would silently change approval meaning.

This planning pass owns only this new document. All implementation paths below are proposed future assignments, not current source ownership. `pipeline.py` and `test_generalization.py` already have concurrent edits: coordinator must allocate their narrow hunks after temporal/intake workers settle. Preserve their changes.

**Forbidden:** `src/fundamentals/api/source_admission.py`; `src/fundamentals/store/snapshot_store.py` (SnapshotStore); `src/fundamentals/store/fact_store.py` (FactStore); `config/**`; approved artifacts under `docs/goals/architecture/**` and `docs/evidence/**`; old Apar reports/sessions. No source/test edits in this pass, Beads/git writes, network, private originals, credentials, cloud, dependencies, further agents, architecture changes, PDF-content changes or golden-company figure changes.

## Task 1: Carry canonical guidance identity end to end

Goal: New claims use `guidance:<metric>:<horizon>` independently of presentation; legacy records remain readable and auditable.

Files:
- Create/Test: `tests/fundamentals/test_guidance_review_identity.py`.
- Modify: `src/fundamentals/output/earnings_update.py` (`RenderedGuidance` field only), `src/fundamentals/api/pipeline.py` (guidance construction only), `src/fundamentals/output/review_session.py` (`enumerate_claims` guidance ID only).
- Test/Modify: `tests/fundamentals/test_phase05_review_session.py` (new-format fixture and legacy characterization).

Interfaces:
- Consumes: `GuidanceClaim.metric: str`, `horizon: str`; `RenderedGuidance`; `EarningsUpdate`; original report bytes through `review_cli._start`.
- Produces: `RenderedGuidance.metric: str | None = None`; stable guidance `ReviewClaim.claim_id`; unchanged `ReviewSession` schema/hash binding.

Approach: Copy `claim.metric` verbatim into every newly pipeline-produced rendered claim. Keep labels for Markdown and review text. Missing/null metric means unavailable legacy identity; enumerate exactly the previous label/horizon ID, explicitly documented as legacy. Reject present empty/whitespace metric rather than falling back. Never infer from labels, source quotes or current config. Existing session load/list/claim/finish consumes persisted IDs without reenumeration or migration. Existing report files stay untouched; CLI continues hashing raw input bytes. Canonicalizing an old report requires a separately produced artifact and fresh review; no approval transfer. No new schema-version machinery.

Verification: characterization first, then RED/GREEN through public model, renderer, synthetic pipeline, enumeration and review CLI seams. Test differing label/metric, label rename preserving ID, distinct metrics sharing a label, horizon change changing ID, and invalid metric rejection. A generated synthetic guidance pipeline run must carry metric through JSON into review. Literal pre-field JSON must deserialize, enumerate legacy IDs, and retain its exact byte hash through approval. Saved unfinished/finished legacy sessions preserve claims, reviews, superseded lineage, decision and hash after round-trip; canonical replacement IDs are refused. Markdown labels/ranges/sources remain unchanged.

Dependencies: None. Risk: test-first compatibility change; duplicate canonical metric/horizon inputs would still be ambiguous—surface any admitted example during review rather than inventing suffixes.

## Task 2: Scope figure assertions

Goal: Provenance hash digits cannot invalidate correct current-quarter figures.

Files:
- Create: None.
- Modify/Test: `tests/fundamentals/test_generalization.py` only.

Interfaces:
- Consumes: `PipelineResult.update`, rendered §2 facts table; existing `_facts_table_values` pattern in `tests/fundamentals/test_pipeline_e2e.py`.
- Produces: Figure-specific parsed value assertions and deterministic collision regression.

Approach: Parse only §2 value cells; assert current values and exclude exact prior values 900/950. In a separate renderer-only synthetic model, replace provenance hash with `900950abcdef` followed by 52 zeroes. Preserve all figures and PDFs. Prove Markdown contains both substrings while parsed values remain correct; a wrong-column 900/950 value must fail the figure check.

Verification: RED demonstrates whole-Markdown negatives fail on the fixed hash; GREEN parsed assertions pass, and wrong-column controls fail. No random retries or PDF determinism workaround.

Dependencies: None. Risk: pre-existing edits require coordinated hunk ownership.

## Review and verification gate

Self-review scope, compatibility and test seams now; independent plan review precedes implementation. Further agents and Beads updates are excluded from this pass by request.

After implementation, using installed tools only:

- `.venv/bin/python -m pytest -q tests/fundamentals/test_guidance_review_identity.py tests/fundamentals/test_phase05_review_session.py tests/fundamentals/test_generalization.py tests/fundamentals/test_pipeline_e2e.py`
- `.venv/bin/ruff check src/fundamentals/output/earnings_update.py src/fundamentals/output/review_session.py src/fundamentals/api/pipeline.py tests/fundamentals/test_guidance_review_identity.py tests/fundamentals/test_phase05_review_session.py tests/fundamentals/test_generalization.py`
- `.venv/bin/ruff format --check src/fundamentals/output/earnings_update.py src/fundamentals/output/review_session.py src/fundamentals/api/pipeline.py tests/fundamentals/test_guidance_review_identity.py tests/fundamentals/test_phase05_review_session.py tests/fundamentals/test_generalization.py`
- `.venv/bin/mypy --strict src/fundamentals/output/earnings_update.py src/fundamentals/output/review_session.py src/fundamentals/api/pipeline.py`

Record failures attributable to concurrent work. Finish with `git --no-optional-locks status --short`; stage/commit nothing.
