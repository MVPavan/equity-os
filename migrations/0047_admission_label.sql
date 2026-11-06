-- VENDOR-1 Phase 1 (spec §6.5, §6.8, §6.9). 0001--0045 are immutable; 0046 is reserved for
-- research-4. Every existing admission is a first-party filed value, so the label default covers
-- it and no UPDATE runs against the append-only table.
ALTER TABLE eqos.fact_admissions
    ADD COLUMN label text NOT NULL DEFAULT 'CHECKED_AGAINST_FILING'
        CHECK (label IN ('CHECKED_AGAINST_FILING', 'VENDORS_AGREE_NOT_CHECKED')),
    ADD COLUMN witness_interpretation_id bigint REFERENCES eqos.interpretations (id),
    ADD COLUMN eligibility_version text,
    ADD CONSTRAINT fact_admissions_unchecked_witness CHECK (
        label <> 'VENDORS_AGREE_NOT_CHECKED'
        OR (witness_interpretation_id IS NOT NULL AND eligibility_version IS NOT NULL));
ALTER TABLE eqos.fact_admissions ALTER COLUMN label DROP DEFAULT;

-- A filing contradicted vendor agreement for a check class; it stores no vendor value.
CREATE TABLE eqos.vendor_counterexamples (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    class_digest text NOT NULL CHECK (class_digest ~ '^[0-9a-f]{64}$'),
    result_id   bigint NOT NULL REFERENCES eqos.results (id),
    run_id      bigint NOT NULL REFERENCES eqos.runs (id),
    recorded_at timestamptz NOT NULL DEFAULT eqos.store_now(),
    UNIQUE (class_digest, result_id)
);

-- The fallback workflow's terminal outcome per company-period, with the run it consumed.
CREATE TABLE eqos.vendor_fallback_outcomes (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id      bigint NOT NULL REFERENCES eqos.runs (id),
    entity_id   bigint NOT NULL REFERENCES eqos.reporting_entities (id),
    period_end  date NOT NULL,
    basis       text NOT NULL CHECK (basis IN ('CONSOLIDATED', 'STANDALONE')),
    outcome     text NOT NULL CHECK (outcome IN ('ADMITTED', 'FILING_UNAVAILABLE',
        'FILING_UNRESOLVED', 'STILL_REFUSED')),
    rerun_id    bigint REFERENCES eqos.runs (id),
    cells       jsonb NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT eqos.store_now()
);

DO $$
DECLARE
    name text;
BEGIN
    FOREACH name IN ARRAY ARRAY['vendor_counterexamples', 'vendor_fallback_outcomes'] LOOP
        EXECUTE format('CREATE TRIGGER reject_row_mutation BEFORE UPDATE OR DELETE ON eqos.%I '
            'FOR EACH ROW EXECUTE FUNCTION eqos.reject_mutation()', name);
        EXECUTE format('CREATE TRIGGER reject_truncate BEFORE TRUNCATE ON eqos.%I '
            'FOR EACH STATEMENT EXECUTE FUNCTION eqos.reject_mutation()', name);
        EXECUTE format('GRANT INSERT ON eqos.%I TO eqos_runtime', name);
        EXECUTE format('GRANT USAGE ON SEQUENCE eqos.%I TO eqos_runtime', name || '_id_seq');
        EXECUTE format('GRANT SELECT ON eqos.%I TO eqos_runtime, eqos_panel, eqos_owner, eqos_purge',
            name);
    END LOOP;
END;
$$;

ALTER TABLE eqos.run_versions DROP CONSTRAINT run_versions_pin_check;
ALTER TABLE eqos.run_versions ADD CHECK (pin IN (
    'dictionary','formula_set','mapping_set','normalisation_policy','extractor_xbrl','extractor_pdf',
    'rounding_policy','definition_set','comparison_policy','alignment_rules','vendor_extractor',
    'comparison_semantics','vendor_first_policy','eligibility'));

-- The 0028 body, with the admission's second witness added to the fact_admissions branch.
CREATE OR REPLACE FUNCTION eqos.row_captures(tbl text, r jsonb) RETURNS bigint[]
LANGUAGE plpgsql STABLE AS $$
DECLARE
    found   bigint[];
    item    bigint := (SELECT item_id FROM eqos.queue_dispositions
                       WHERE id = (r ->> 'disposition_id')::bigint);
BEGIN
    IF tbl = 'memory_supports' THEN
        SELECT coalesce(array_agg(DISTINCT c) FILTER (WHERE c IS NOT NULL), '{}') INTO found
        FROM (
            SELECT (r ->> 'capture_ref_id')::bigint
            UNION ALL SELECT unnest(eqos.row_captures('numeric_claims', to_jsonb(k)))
                FROM eqos.numeric_claims k
                WHERE k.id = (r ->> 'claim_id')::bigint
                   OR k.version_id = (r ->> 'version_id')::bigint
            UNION ALL SELECT unnest(eqos.row_captures('report_sections', to_jsonb(s)))
                FROM eqos.report_sections s WHERE s.version_id = (r ->> 'version_id')::bigint
            UNION ALL SELECT unnest(eqos.row_captures('queue_item_inputs', to_jsonb(i)))
                FROM eqos.queue_item_inputs i WHERE i.item_id = item
            UNION ALL SELECT unnest(eqos.row_captures('queue_item_traces', to_jsonb(t)))
                FROM eqos.queue_item_traces t WHERE t.item_id = item
        ) x(c);
        RETURN found;
    END IF;
    WITH RECURSIVE nodes(kind, id) AS (
        SELECT v.kind, (r ->> v.col)::bigint FROM (VALUES ('T', 'calculation_trace_id'),
            ('T', 'operand_trace_id'), ('I', 'interpretation_id'),
            ('I', 'operand_interpretation_id'), ('I', 'evidence_interpretation_id')) v(kind, col)
        UNION ALL SELECT s.kind, s.id FROM eqos.pair_outcomes p
            JOIN eqos.result_source_values v ON v.id IN (p.left_value_id, p.right_value_id)
            CROSS JOIN LATERAL (VALUES ('I', v.interpretation_id), ('T', v.calculation_trace_id))
                s(kind, id)
            WHERE p.id = (r ->> 'pair_outcome_id')::bigint
        UNION ALL SELECT 'I', a.interpretation_id FROM eqos.fact_admissions a
            WHERE a.fact_origin = r ->> 'fact_origin'
              AND a.fact_origin_id = (r ->> 'fact_origin_id')::bigint
        UNION ALL SELECT 'I', a.witness_interpretation_id FROM eqos.fact_admissions a
            WHERE a.fact_origin = r ->> 'fact_origin'
              AND a.fact_origin_id = (r ->> 'fact_origin_id')::bigint
        UNION
        SELECT e.kind, e.id FROM nodes n CROSS JOIN LATERAL (
            SELECT 'I', operand_interpretation_id FROM eqos.interpretation_operands
                WHERE n.kind = 'I' AND interpretation_id = n.id
            UNION ALL SELECT 'I', evidence_interpretation_id
                FROM eqos.interpretation_condition_evidence
                WHERE n.kind = 'I' AND interpretation_id = n.id
            UNION ALL SELECT 'T', calculation_trace_id FROM eqos.construction_traces
                WHERE n.kind = 'I' AND interpretation_id = n.id
            UNION ALL SELECT 'I', interpretation_id FROM eqos.calculation_trace_operands
                WHERE n.kind = 'T' AND calculation_trace_id = n.id
            UNION ALL SELECT 'T', operand_trace_id FROM eqos.calculation_trace_operands
                WHERE n.kind = 'T' AND calculation_trace_id = n.id
        ) e(kind, id) WHERE e.id IS NOT NULL
    )
    SELECT coalesce(array_agg(DISTINCT c) FILTER (WHERE c IS NOT NULL), '{}') INTO found FROM (
        SELECT (r ->> CASE tbl WHEN 'capture_refs' THEN 'id' ELSE 'capture_ref_id' END)::bigint
        UNION ALL SELECT i.capture_ref_id FROM eqos.interpretations i
            JOIN nodes n ON n.kind = 'I' AND n.id = i.id
        UNION ALL SELECT capture_ref_id FROM eqos.occurrences
            WHERE id = (r ->> 'occurrence_id')::bigint
        UNION ALL SELECT capture_ref_id FROM eqos.acquisition_attempts
            WHERE id = (r ->> 'attempt_id')::bigint
        UNION ALL SELECT capture_ref_id FROM eqos.package_members
            WHERE package_id = (r ->> 'package_id')::bigint
        UNION ALL SELECT capture_ref_id FROM eqos.evidence_input_captures
            WHERE evidence_input_id = (r ->> 'evidence_input_id')::bigint
        UNION ALL SELECT b.capture_ref_id FROM eqos.fact_rows f
            JOIN eqos.legacy_evidence_bindings b
                ON (b.target_store, b.row_handle) = (f.target_store, f.handle)
            WHERE f.origin = r ->> 'fact_origin' AND f.origin_id = (r ->> 'fact_origin_id')::bigint
        UNION ALL SELECT m[1]::bigint
            FROM regexp_matches(coalesce(r ->> 'body', ''), '\{\{s:(\d+)\|', 'g') m
    ) x(c);
    RETURN found;
END $$;
