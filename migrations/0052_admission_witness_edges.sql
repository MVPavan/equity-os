-- VENDOR-1 Phase 1 review finding 4 (eqos-awnc). 0001--0051 are immutable. A calculation's
-- capture walk follows each admitted operand to its second witness, as a fact claim already does
-- (0047). Only row_captures changes: 0047's body plus that one branch.
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
            UNION ALL SELECT 'I', a.witness_interpretation_id
                FROM eqos.calculation_trace_operands o
                JOIN eqos.fact_admissions a ON a.interpretation_id = o.interpretation_id
                WHERE n.kind = 'T' AND o.calculation_trace_id = n.id
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
