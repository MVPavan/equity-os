---
status: approved
scope: a05-derived-amounts
spec: docs/specs/2026-10-12-report-ledger-memory-and-data-lifecycle.md
register: docs/blueprint/funda-blueprint-implementation-decision-register-v2.md
subject_sha256: ab255a2a7c2cf3881b88b27759003035aaed7148fcadf9e0bc053799017d07a6
amendments:
- id: derived-amounts-kept
  scope: a05-derived-amounts
  register_clause: A-05:derived-outputs
  change: 'Keep derived amounts as outcomes, not payload, after vendor material expires and after
    a vendor licence end: pair_outcomes (status, reason, triage, difference, interval_gap),
    pair_adjustments, definition_records explained amounts, queue items and dispositions, results
    and COMPARISON claims. Conditions: private, personal, non-commercial use under the owner''s own
    subscriber accounts, no redistribution; a licence end purges that vendor''s captures and
    payload (tombstoned per redaction-inventory), never outcomes. Residual risk accepted: Screener
    Medium-High, Tijori High (derivative-works clause), Upstox open (terms unassessed).'
- id: redaction-inventory
  scope: a05-derived-amounts
  register_clause: A-05:retention
  change: 'Tombstoning a VENDOR capture updates in place exactly the rows selected below: it sets
    every clear column to NULL, reset columns to the stated value, reduces each json_keep column to
    its listed keys and changes nothing else. No row is deleted; every table and column not listed
    is kept unchanged.'
  tombstone:
    occurrences:
      rows: capture_ref_id is the capture
      clear: [raw_value_text, raw_sign]
      json_keep:
        native_context: [schema_identity, basis, statement_family, label, section, section_parent,
          field_id, header_months, header_kind, native_period_kind, native_period_label,
          identity_evidence_ref]
        disclosure: [identity_strength, quarantined, reason, supporting_page_capture_id,
          supporting_page_sha256, reconciliation, metadata_sha256, metadata_verification_unknown,
          claimed_fetched_at, surface_unverified, capture_complete_claim, capture_verified_claim,
          alignment, skipped_column]
      json_dropped_known: [native_context.island_value, disclosure.anomalies]
      keep: [id, capture_ref_id, representation, extractor_version, native_field, raw_unit,
        raw_scale, precision_kind, declared_precision, period_start, period_end, period_instant,
        missing_state, anchor, anchor_key, valid_time, knowledge_time, knowledge_time_status,
        first_seen_at, revision_cause]
    interpretations:
      rows: capture_ref_id is the capture (DIRECT and CONSTRUCTED)
      clear: [value, lower, upper]
      reset: {transform_trace: '{}'}
      keep: [id, origin, occurrence_id, capture_ref_id, representation, construction_rule_id,
        input_digest, status, entity_id, canonical_id, dictionary_version, period_start,
        period_end, period_instant, basis, framework, currency, value_kind, dimension_set,
        dimension_hash, key_digest, tier, qualification_ref, mapping_set_version,
        mapping_entry_id, normalisation_policy_version, extractor_version, reason, revision_cause,
        supersedes_interpretation_id, recorded_at]
    calculation_traces:
      rows: vendor-derived, i.e. linked by construction_traces to an interpretation of the
        capture, or with an operand row whose interpretation_id is an interpretation of the
        capture or whose operand_trace_id is a vendor-derived trace (transitively)
      clear: [value, lower, upper, exact_value, exact_lower, exact_upper]
      keep: [id, content_sha256, trace_kind, formula_id, formula_version, formula_tier,
        formula_qualification_ref, rounding_policy_id, key_digest, value_identity, state,
        effective_tier]
    calculation_trace_operands:
      rows: operands of a vendor-derived trace whose interpretation_id is an interpretation of the
        capture or whose operand_trace_id is a vendor-derived trace
      clear: [value, lower, upper, exact_value, exact_lower, exact_upper]
      keep: [id, calculation_trace_id, ordinal, operand_name, key_digest, temporal_role,
        interpretation_id, operand_trace_id, alignment_proof_id, mapping_entry_id,
        qualification_ref, scoped_tier, selection_source, source_state]
    result_source_values:
      rows: source_role INDEPENDENT_VENDOR or DIAGNOSTIC, and interpretation_id is an
        interpretation of the capture or calculation_trace_id a vendor-derived trace
      clear: [value, lower, upper]
      keep: [id, result_id, source_role, representation, source_state, reason, interpretation_id,
        calculation_trace_id, attempt_id, calculation_state, source_id, surface]
    acquisition_attempts:
      rows: stage EXTRACTION and capture_ref_id is the capture
      clear: [reason]
      keep: [id, stage, source_id, surface, entity_id, period_end, basis, framework,
        representation, statement_family, package_id, capture_ref_id, input_sha256,
        extractor_version, outcome, attempted_at, extraction_context_sha256]
  kept_value_derived:
    calculation_traces.content_sha256: SHA-256 over every trace field including values; the
      UNIQUE constraint and the content-hash lookup keep it, so a guessed value can be confirmed
    occurrences.missing_state: ZERO_PRINTED reveals a printed zero
    occurrences.declared_precision: Tijori's displayed decimals reveal whether the magnitude is
      above its rounding threshold; a CHECK ties it to precision_kind
    interpretation_condition_evidence.holds: a held zero condition reveals a zero operand
    pair_outcomes.difference and interval_gap: with the retained first-party value they reveal
      the vendor figure (the derived-amounts-kept decision)
approvals:
  derived-amounts-kept:
    reviewer: gpt-6.1-sol
    date: '2026-10-17'
    verdict: APPROVE
    subject_sha256: ab255a2a7c2cf3881b88b27759003035aaed7148fcadf9e0bc053799017d07a6
    report: docs/workstreams/data-foundation/reviews/D9-amendments-review.md
  redaction-inventory:
    reviewer: gpt-6.1-sol
    date: '2026-10-17'
    verdict: APPROVE
    subject_sha256: ab255a2a7c2cf3881b88b27759003035aaed7148fcadf9e0bc053799017d07a6
    report: docs/workstreams/data-foundation/reviews/D9-amendments-review.md
---

# A-05: derived amounts kept as outcomes, and the vendor tombstone inventory

Recorded 2026-10-17 for the approved 2026-10-12 report-ledger spec, Stage 5 (D9 Task 1). Approved by the
independent reviewer on 2026-10-17; see the [approval report](../../workstreams/data-foundation/reviews/D9-amendments-review.md).

This record settles the A-05 open question of the
[report-ledger spec](../../specs/2026-10-12-report-ledger-memory-and-data-lifecycle.md#open-questions)
on kept derived amounts, and fixes the redaction inventory that ledger §5 purge step 4 and §6 item
4 leave to it ([D9 plan](../../workstreams/data-foundation/plans/D9.md) ruling R7). The original
[decision register](../funda-blueprint-implementation-decision-register-v2.md) remains the
baseline; register A-05 stays open for Tijori's derivative-works clause and Upstox's terms. The
companion record is [retention and replay](2026-10-12-retention-replay.md).

## Spec clauses, verbatim

Ledger spec, Open Questions:

> - **Provider rights (A-05):** conservative defaults applied from the vendor-terms research; open:
>   Tijori's derivative-works clause, Upstox terms, and whether kept derived amounts (§5) are allowed.

Ledger spec §5:

> **Derived amounts** (comparison deltas, queue items, dispositions, explained amounts,
> `COMPARISON` claims) are kept as outcomes, not payload; with the first-party value they reveal
> the vendor figure (A-05 open).

> | `VENDOR` | Every vendor page, API response and screen CSV, covered or not, with its payload | Four quarters from registration unless an open queue item holds it; never past licence end | Capture record, hash, first-seen time, payload tombstones (id, capture id, measurement key, first-seen time, purge record), comparison outcomes |

> 4. Commit the purge record (capture id, class, reason, address, hash, probe result, UTC time)
>    and `EXPIRED`; for `VENDOR`, in the same transaction tombstone its payload and remove vendor
>    values from result rows, keeping each outcome (status, reason, delta class, delta).

Ledger spec §6 item 4 is quoted in the [retention and replay](2026-10-12-retention-replay.md) record (`data-spec-6-integrity`).

## `derived-amounts-kept`: decision and basis

**Decision: keep.** Derived amounts are the system's own computed outcomes, not vendor payload.
Rights decision [A05-DECISION-005](../../evidence/phase-0a/a-05-rights-decision-005-subscriber-scraping.md)
scopes subscriber collection to "retention + internal processing + internal derived facts" inside
the boundary "**PRIVATE / PERSONAL / NON-COMMERCIAL ONLY** — no redistribution, no public output of
raw/substantial source data, no commercial use, no account sharing". Deleting the amounts would
rewrite sealed report versions and queue evidence, which the ledger forbids.

**Conditions.** Private, personal, non-commercial use through the owner's own accounts; no
redistribution or public output. A licence end purges that vendor's captures and payload (bytes
deleted, rows tombstoned per `redaction-inventory`), never outcomes.

**Residual risk** (from the [vendor-terms research](../../research/vendor-terms-screener-tijori-2026-10.md), inference, not legal advice):

> | Indefinite retention of extracted/derived figures | **Medium-High** — destroy downloaded materials on termination; no right to retain; derived-figure retention untouched by text | **High** — "create derivative works from … for any purpose" prohibited; personal-use-only carve-out; internal research tool not covered |

Tijori's terms (research §2d): "You may not reproduce, publish, transmit, distribute, display,
modify, create derivative works from, sell or participate in any sale of or exploit in any way, in
whole or in part any of the contents on this Website for any purpose." Screener's (research §1d):
"personal, non-commercial transitory viewing only". Upstox's terms are not assessed there and stay
open under A-05. If the reviewer rules against keeping, D9 plan Q1 applies (a ledger-spec
amendment; D9 Tasks 5 and 9 wait).

## `redaction-inventory`: audit

Every vendor value reaches PostgreSQL through `ingest_vendor` (`src/fundamentals/evidence/vendor_ingest.py:104-196`),
one transaction for the attempt and its occurrences (`_store`, `:350-388`; attempt reason `:166-174`),
interpretations after (`_interpretations`, `:289-342`). The header's `tombstone` map is binding;
this section gives each producer.

### Occurrences (`0001:137-175`; representation `0006:4-5`)

Insert `src/fundamentals/evidence/repository_rows.py:202-210`, params `:397`. Shared builders:
Screener `src/fundamentals/evidence/vendor_screener.py:438-470` (`_occurrence`); Tijori and Upstox
`src/fundamentals/evidence/vendor_ingest.py:214-236` (`json_occurrence`). `raw_value_text` is the
lexeme; `raw_sign` is derived from the value (`vendor_screener.py:447`, `vendor_ingest.py:223`).

| JSON column | Screener (`vendor_screener.py`) | Tijori (`vendor_tijori.py`) | Upstox (`vendor_upstox.py`) |
|---|---|---|---|
| `native_context` | `:450-460`: schema_identity, basis, statement_family, label, section, header_months, native_period_kind, native_period_label, identity_evidence_ref — all kept | `:162-173`: schema_identity, basis, statement_family, label, section, section_parent, field_id, header_months, header_kind kept; **`island_value` (`:170`, the raw lexeme) dropped** | `:125-132`: schema_identity, basis, statement_family, label, section, header_months — all kept |
| `disclosure` | page `:125` identity_strength; quarantined `:148` quarantined, reason (cell counts, `ingest/screener_financials_tables.py:421`); schedules `:277-283` identity_strength, supporting_page_capture_id, supporting_page_sha256, reconciliation, plus `_metadata_claim` `:492-517` metadata_sha256, metadata_verification_unknown, claimed_fetched_at, surface_unverified, capture_complete_claim, capture_verified_claim — all kept | `:181-185`: alignment, quarantined, skipped_column — all kept | **`anomalies` (`:139`) dropped**: identity notes state both figures (`ingest/upstox_statements.py:86-89,658-690`) |
| `anchor` | `:122` (provenance, times stripped `:424-437`), `:139-145`, `:269-276`: location keys only — kept | `:174-180`: location keys — kept | `:133-138`: location keys — kept |

`json_keep` is an allowlist: any key not listed (present or future) is dropped. `anchor` and
`anchor_key` (digest of the location, `vendor_ingest.py:233`, `vendor_screener.py:465`) carry no value.

### Interpretations (`0001:232-289`; `0003`, `0005:67-71` constraints)

Insert `src/fundamentals/evidence/repository_rows.py:274-283`, params `:497`. Direct rows
`src/fundamentals/evidence/interpret.py:255-273` set value, interval and `transform_trace` (sign,
interval places, reasons); constructed rows `:375-396`; a selector construction embeds its whole
calculation trace, values included, in `transform_trace` (`src/fundamentals/evidence/capture_interpretation.py:395-405`).
Hence `transform_trace` → `{}`. `input_digest` hashes ids only (`interpret.py:153,375`).
`interpretation_operands` (`0001:291-297`, insert `repository_rows.py:284-287`) and
`construction_traces` (`0007`) hold ids only and are kept; `interpretation_condition_evidence`
(`0001:299-306`, `repository_rows.py:288-291`) is kept (see `kept_value_derived`).

### Calculation traces and operands (`0001:334-391`; `0002`, `0006:18-24`)

Insert `src/fundamentals/evidence/repository_calc.py:26-48` through `src/fundamentals/evidence/repository.py:712-720`.
Vendor-derived traces come from three producers: the construction trace (`repository.py:410`,
link `repository_calc.py:54-57`); the comparison's vendor side, which stores the construction's
trace from `transform_trace` (`src/fundamentals/compare/vendor_sides.py:296-305`); vendor operands
selected as `VENDOR_CAPTURE` (`src/fundamentals/evidence/interpret.py:470-485`). Values sit in
`value/lower/upper` and the exact `p/q` text columns. `queue_item_traces` (`0008`) links are kept.

### Result source values (`0001:554-574`; `0006:11-40`)

Insert `src/fundamentals/compare/run_store.py:144-150`; vendor and diagnostic sides from
`src/fundamentals/compare/vendor_sides.py:270-305`. `reason` holds codes only (`vendor_sides.py:380-398`,
attempt outcomes) and is kept.

### Acquisition attempts (`0001:203-230`; `0005:75-90`, `0006:8-10`)

Insert `src/fundamentals/evidence/repository_rows.py:236-239`. A vendor extraction attempt's
`reason` is `"; ".join(extraction.reasons)` (`vendor_ingest.py:171`); for Upstox these are the
response anomalies (`vendor_upstox.py:148`), whose identity notes state both figures, so `reason`
is cleared for every vendor extraction attempt. The outcome stays. `input_sha256` (request
identity, `vendor_ingest.py:377-381`) and `extraction_context_sha256` (capture hash, binding and
display, e.g. `vendor_tijori.py:199-211`) carry no value.

### Kept as outcomes or identity (not tombstoned)

- `0001`: `capture_refs` (forever, ledger §6 item 6); `results`, `pair_outcomes`,
  `pair_adjustments`, `definition_records` (outcomes, `derived-amounts-kept`); `runs`
  (`operational_failures` hold reason codes, `src/fundamentals/compare/run.py:210-225`),
  `run_versions`, `run_inputs`, `result_surfaced_restatements` (ids). Identity, package, segment,
  alignment and definition-set tables are never written from a vendor capture.
- `0006`: `queue_items` (`source_refs` name role, representation, source and surface only,
  `src/fundamentals/contracts/comparison.py:53-61`; `input_sha256` hashes the draft's codes and ids,
  `src/fundamentals/compare/queue.py:251-261`), `queue_item_inputs`, `queue_run_items`,
  `queue_dispositions` (outcomes).
- Outside the listed migrations: Upstox instrument captures are `IDENTITY`, not tombstoned, and
  their registry rows are kept (ledger §5); Screener screen members (`0025`) hold names and codes,
  no amounts.

### Counts

| | Cleared or reset | JSON paths dropped | Kept |
|---|---|---|---|
| Shared tables (all three adapters) | 22 columns: occurrences 2, interpretations 3 + `transform_trace`, traces 6, trace operands 6, result source values 3, attempts 1 | — | occurrences 20 (+2 reduced JSON), interpretations 31, traces 12, operands 14, result source values 12, attempts 17 |
| Screener | — | 0 | `native_context` 9 keys, `disclosure` 12 keys, anchor |
| Tijori | — | 1 (`native_context.island_value`) | `native_context` 9 keys, `disclosure` 3 keys, anchor |
| Upstox | attempt `reason` (figures in identity notes) | 1 (`disclosure.anomalies`) | `native_context` 6 keys, `disclosure` 0 keys, anchor |

### Residual risk from kept value-derived data

The header's `kept_value_derived` lists what the tombstone keeps although it is derived from a
vendor value: the trace content hash (a constraint keeps it), `ZERO_PRINTED`, Tijori's displayed
precision band, held zero conditions, and the kept outcome deltas. These are accepted A-05 residual
risk on the same conditions as `derived-amounts-kept`.

Any substantive change to these items requires a new digest and fresh review.
