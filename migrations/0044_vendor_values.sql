-- VENDOR-SURFACE Phase 1. 0001--0043 are immutable; 0043 belongs to DOCS-1.
ALTER TABLE eqos.capture_addresses ADD COLUMN location text;
CREATE TABLE eqos.vendor_parser_versions (
    parser_version text PRIMARY KEY,
    parser_sha256 text NOT NULL CHECK (parser_sha256 ~ '^[0-9a-f]{64}$')
);
CREATE TABLE eqos.vendor_outcomes (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    capture_ref_id bigint NOT NULL REFERENCES eqos.capture_refs (id),
    surface text NOT NULL,
    parser_version text NOT NULL REFERENCES eqos.vendor_parser_versions (parser_version),
    symbol text,
    status text NOT NULL CHECK (status IN ('OK','PARTIAL','EMPTY','FAILED','UNUSABLE','KEPT')),
    row_count integer NOT NULL CHECK (row_count >= 0),
    rejected_count integer CHECK (rejected_count >= 0),
    detail text,
    traversal_key text,
    traversal_page integer,
    traversal_done boolean NOT NULL DEFAULT false,
    recorded_at timestamptz NOT NULL DEFAULT eqos.store_now(),
    UNIQUE (capture_ref_id, surface, parser_version),
    UNIQUE (id, capture_ref_id)
);
CREATE TABLE eqos.vendor_values (
    outcome_id bigint NOT NULL,
    capture_ref_id bigint NOT NULL REFERENCES eqos.capture_refs (id),
    table_key text NOT NULL,
    row_index integer NOT NULL CHECK (row_index >= 0),
    column_index integer NOT NULL CHECK (column_index >= 0),
    locator text NOT NULL,
    row_label text,
    column_label text,
    raw_text text,
    value numeric,
    unit text,
    basis text,
    link text,
    padded boolean NOT NULL DEFAULT false,
    expected_numeric boolean NOT NULL DEFAULT false,
    FOREIGN KEY (outcome_id, capture_ref_id)
        REFERENCES eqos.vendor_outcomes (id, capture_ref_id),
    UNIQUE (outcome_id, table_key, row_index, column_index)
);
CREATE TABLE eqos.vendor_basis_bindings (
    entity_id bigint NOT NULL REFERENCES eqos.reporting_entities (id),
    basis text NOT NULL CHECK (basis IN ('CONSOLIDATED','STANDALONE')),
    screener_company_id bigint NOT NULL,
    warehouse_id bigint NOT NULL,
    capture_ref_id bigint NOT NULL REFERENCES eqos.capture_refs (id),
    evidence text NOT NULL CHECK (evidence IN ('ONBOARDING','FIRST_CAPTURE')),
    recorded_at timestamptz NOT NULL DEFAULT eqos.store_now(),
    UNIQUE (entity_id, basis)
);
-- The 0028 guard also refuses vendor payloads on captures that are no longer retained.
CREATE OR REPLACE FUNCTION eqos.retention_guard() RETURNS trigger LANGUAGE plpgsql
SECURITY DEFINER SET search_path = pg_catalog, eqos AS $$
DECLARE
    rec         jsonb := to_jsonb(NEW);
    captures    bigint[];
    ended       text;
    expired     bigint;
BEGIN
    PERFORM eqos.retention_shared();
    captures := eqos.row_captures(TG_TABLE_NAME, rec);
    SELECT l.source_id INTO ended FROM eqos.licence_ends l
        WHERE l.source_id = rec ->> 'source_id'
           OR l.source_id IN (SELECT source_id FROM eqos.capture_refs WHERE id = ANY (captures))
        LIMIT 1;
    IF ended IS NOT NULL THEN
        RAISE EXCEPTION 'BEYOND_AUTHORITY: the % licence has ended; % refused', ended,
            TG_TABLE_NAME USING ERRCODE = '42501';
    END IF;
    IF rec ->> 'citation_kind' = 'SOURCE_QUOTE'
       AND EXISTS (SELECT 1 FROM eqos.capture_refs WHERE id = ANY (captures)
                   AND eqos.is_vendor_source(source_id)) THEN
        RAISE EXCEPTION 'BEYOND_AUTHORITY: a vendor capture cannot be quoted'
            USING ERRCODE = '42501';
    END IF;
    IF rec ->> 'citation_kind' = 'SOURCE_QUOTE' OR TG_TABLE_NAME IN ('report_sections',
        'legacy_evidence_bindings', 'occurrences', 'interpretations', 'interpretation_operands',
        'interpretation_condition_evidence', 'construction_traces', 'calculation_trace_operands',
        'result_source_values', 'run_inputs', 'acquisition_attempts', 'package_members',
        'vendor_outcomes', 'vendor_values', 'vendor_basis_bindings') THEN
        SELECT c INTO expired FROM unnest(captures) c
            WHERE eqos.capture_state(c) NOT IN ('RETAINED', 'RESTORED') LIMIT 1;
        IF expired IS NOT NULL THEN
            RAISE EXCEPTION 'ORIGINAL_EXPIRED: capture % is not retained; % refused', expired,
                TG_TABLE_NAME USING ERRCODE = '55000';
        END IF;
    END IF;
    RETURN NEW;
END $$;

DO $$
DECLARE name text;
BEGIN
    FOREACH name IN ARRAY ARRAY['vendor_parser_versions','vendor_outcomes','vendor_values',
                                'vendor_basis_bindings'] LOOP
        EXECUTE format('CREATE TRIGGER a0_retention_guard BEFORE INSERT ON eqos.%I '
            'FOR EACH ROW EXECUTE FUNCTION eqos.retention_guard()', name);
        IF name = 'vendor_values' THEN
            EXECUTE format('CREATE TRIGGER reject_row_mutation BEFORE UPDATE OR DELETE ON eqos.%I '
                'FOR EACH ROW EXECUTE FUNCTION eqos.reject_mutation_except_tombstone('
                '''value'',''raw_text'',''row_label'',''column_label'',''link'',''unit'')', name);
        ELSE
            EXECUTE format('CREATE TRIGGER reject_row_mutation BEFORE UPDATE OR DELETE ON eqos.%I '
                'FOR EACH ROW EXECUTE FUNCTION eqos.reject_mutation()', name);
        END IF;
        EXECUTE format('CREATE TRIGGER reject_truncate BEFORE TRUNCATE ON eqos.%I '
            'FOR EACH STATEMENT EXECUTE FUNCTION eqos.reject_mutation()', name);
        EXECUTE format('GRANT INSERT ON eqos.%I TO eqos_runtime', name);
        EXECUTE format('GRANT SELECT ON eqos.%I TO eqos_runtime, eqos_panel, eqos_owner, eqos_purge',
            name);
    END LOOP;
END $$;
GRANT USAGE ON SEQUENCE eqos.vendor_outcomes_id_seq TO eqos_runtime;

-- The 0029 tombstone body is unchanged except the vendor_values content inventory.
CREATE OR REPLACE FUNCTION eqos.tombstone_vendor_capture(capture bigint) RETURNS void LANGUAGE plpgsql
SECURITY DEFINER SET search_path = pg_catalog, eqos AS $$
DECLARE
    interps bigint[];
    traces  bigint[];
BEGIN
    IF eqos.capture_state(capture) <> 'PURGE_PENDING' OR NOT EXISTS (
        SELECT 1 FROM eqos.retention_classes
        WHERE capture_ref_id = capture AND retention_class = 'VENDOR') THEN
        RAISE EXCEPTION 'tombstone refused: capture % is not a PURGE_PENDING VENDOR capture',
            capture USING ERRCODE = '55000';
    END IF;
    PERFORM set_config('eqos.tombstone', capture::text, true);
    SELECT coalesce(array_agg(id), '{}') INTO interps
        FROM eqos.interpretations WHERE capture_ref_id = capture;
    WITH RECURSIVE vendor_traces(id) AS (
        SELECT calculation_trace_id FROM eqos.construction_traces
            WHERE interpretation_id = ANY (interps)
        UNION SELECT calculation_trace_id FROM eqos.calculation_trace_operands
            WHERE interpretation_id = ANY (interps)
        UNION SELECT o.calculation_trace_id FROM eqos.calculation_trace_operands o
            JOIN vendor_traces t ON o.operand_trace_id = t.id
    )
    SELECT coalesce(array_agg(id), '{}') INTO traces FROM vendor_traces;

    UPDATE eqos.occurrences SET raw_value_text = NULL, raw_sign = NULL,
        native_context = eqos.jsonb_keep(native_context, ARRAY['schema_identity', 'basis',
            'statement_family', 'label', 'section', 'section_parent', 'field_id',
            'header_months', 'header_kind', 'native_period_kind', 'native_period_label',
            'identity_evidence_ref']),
        disclosure = eqos.jsonb_keep(disclosure, ARRAY['identity_strength', 'quarantined',
            'reason', 'supporting_page_capture_id', 'supporting_page_sha256', 'reconciliation',
            'metadata_sha256', 'metadata_verification_unknown', 'claimed_fetched_at',
            'surface_unverified', 'capture_complete_claim', 'capture_verified_claim',
            'alignment', 'skipped_column'])
        WHERE capture_ref_id = capture;
    UPDATE eqos.interpretations SET value = NULL, lower = NULL, upper = NULL,
        transform_trace = '{}' WHERE id = ANY (interps);
    UPDATE eqos.calculation_traces SET value = NULL, lower = NULL, upper = NULL,
        exact_value = NULL, exact_lower = NULL, exact_upper = NULL WHERE id = ANY (traces);
    UPDATE eqos.calculation_trace_operands SET value = NULL, lower = NULL, upper = NULL,
        exact_value = NULL, exact_lower = NULL, exact_upper = NULL
        WHERE calculation_trace_id = ANY (traces)
          AND (interpretation_id = ANY (interps) OR operand_trace_id = ANY (traces));
    UPDATE eqos.result_source_values SET value = NULL, lower = NULL, upper = NULL
        WHERE source_role IN ('INDEPENDENT_VENDOR', 'DIAGNOSTIC')
          AND (interpretation_id = ANY (interps) OR calculation_trace_id = ANY (traces));
    UPDATE eqos.acquisition_attempts SET reason = NULL
        WHERE stage = 'EXTRACTION' AND capture_ref_id = capture;
    UPDATE eqos.vendor_values SET value = NULL, raw_text = NULL, row_label = NULL,
        column_label = NULL, link = NULL, unit = NULL WHERE capture_ref_id = capture;
    PERFORM set_config('eqos.tombstone', '', true);
END $$;
