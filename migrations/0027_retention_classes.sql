-- D9 Task 2: retention classes, capture addresses, licence ends and the retention guard v1
-- (plan docs/workstreams/data-foundation/plans/D9.md R2, R3, RP3c-d, R14). 0001--0026 are
-- immutable. Every table here is append-only; a capture has at most one class row.

GRANT USAGE ON SCHEMA eqos TO eqos_purge;
GRANT SELECT ON eqos.capture_refs TO eqos_purge;

-- R3: the vendor-bounded sources (four quarters, never past a licence end).
CREATE FUNCTION eqos.is_vendor_source(source text) RETURNS boolean LANGUAGE sql IMMUTABLE AS $$
    SELECT source IN ('screener', 'screener-subscriber', 'tijori', 'upstox')
$$;

-- R2: a capture's class from its source and surface alone.
CREATE FUNCTION eqos.base_class(source text, surface text) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN eqos.is_vendor_source(source) AND (source, surface) = ('upstox', 'instruments')
            THEN 'IDENTITY'
        WHEN eqos.is_vendor_source(source) THEN 'VENDOR'
        WHEN (source, surface) IN (('nse', 'EQUITY_L'), ('nse', 'FINANCIAL_RESULTS_LISTING'),
                                   ('nse', 'INTEGRATED_FILING_LISTING'),
                                   ('nse', 'SHAREHOLDING_LISTING'), ('bse', 'PEER_SMART_SEARCH'))
            THEN 'IDENTITY'
        WHEN surface IN ('NSE_XBRL_INSTANCE', 'NSE_RESULTS_PDF', 'NSE_TRANSCRIPT_PDF',
                         'NSE_SHP_XBRL') THEN 'EXCHANGE_REFETCHABLE'
        WHEN NOT eqos.is_vendor_source(source) THEN 'COVERED'
        ELSE 'UNCLASSIFIED' END
$$;

CREATE TABLE eqos.retention_classes (
    capture_ref_id  bigint PRIMARY KEY REFERENCES eqos.capture_refs (id),
    retention_class text NOT NULL
        CHECK (retention_class IN ('VENDOR', 'IDENTITY', 'EXCHANGE_REFETCHABLE', 'COVERED')),
    cause           text NOT NULL CHECK (cause IN ('INTAKE', 'ONE_OFF'))
);

-- R14: the address a capture was fetched from, recorded once at intake.
CREATE TABLE eqos.capture_addresses (
    capture_ref_id  bigint PRIMARY KEY REFERENCES eqos.capture_refs (id),
    url             text NOT NULL CHECK (url <> '')
);

-- R11: a vendor licence end; from it on, nothing new may rest on that source.
CREATE TABLE eqos.licence_ends (
    source_id   text PRIMARY KEY CHECK (eqos.is_vendor_source(source_id)),
    ended_at    timestamptz NOT NULL DEFAULT eqos.store_now()
);

DO $$
DECLARE
    table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY['retention_classes', 'capture_addresses', 'licence_ends'] LOOP
        EXECUTE format('CREATE TRIGGER reject_row_mutation BEFORE UPDATE OR DELETE ON eqos.%I '
            'FOR EACH ROW EXECUTE FUNCTION eqos.reject_mutation()', table_name);
        EXECUTE format('CREATE TRIGGER reject_truncate BEFORE TRUNCATE ON eqos.%I '
            'FOR EACH STATEMENT EXECUTE FUNCTION eqos.reject_mutation()', table_name);
        EXECUTE format('GRANT SELECT ON eqos.%I TO eqos_runtime, eqos_panel, eqos_owner, '
            'eqos_purge', table_name);
    END LOOP;
END;
$$;
GRANT INSERT ON eqos.capture_addresses TO eqos_runtime, eqos_owner;
GRANT INSERT ON eqos.licence_ends TO eqos_owner, eqos_purge;

-- R2: intake classifies; a capture whose class is unknown stays unclassified.
CREATE FUNCTION eqos.classify_capture() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, eqos AS $$
BEGIN
    INSERT INTO eqos.retention_classes (capture_ref_id, retention_class, cause)
        SELECT NEW.id, c, 'INTAKE' FROM eqos.base_class(NEW.source_id, NEW.surface) c
        WHERE c <> 'UNCLASSIFIED';
    RETURN NULL;
END $$;
CREATE TRIGGER classify_capture AFTER INSERT ON eqos.capture_refs
    FOR EACH ROW EXECUTE FUNCTION eqos.classify_capture();

-- R2: the one-off classification of captures registered before 0027; returns rows written.
CREATE FUNCTION eqos.classify_existing() RETURNS integer LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, eqos AS $$
DECLARE
    written integer;
BEGIN
    INSERT INTO eqos.retention_classes (capture_ref_id, retention_class, cause)
        SELECT r.id, eqos.base_class(r.source_id, r.surface), 'ONE_OFF'
        FROM eqos.capture_refs r
        WHERE eqos.base_class(r.source_id, r.surface) <> 'UNCLASSIFIED'
          AND NOT EXISTS (SELECT 1 FROM eqos.retention_classes c WHERE c.capture_ref_id = r.id);
    GET DIAGNOSTICS written = ROW_COUNT;
    RETURN written;
END $$;
REVOKE ALL ON FUNCTION eqos.classify_existing() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION eqos.classify_existing() TO eqos_purge;

-- R2: the entities a capture is evidence of (packages, attempts, onboarding inputs).
CREATE VIEW eqos.capture_entities AS
    SELECT m.capture_ref_id, p.entity_id
    FROM eqos.package_members m JOIN eqos.filing_packages p ON p.id = m.package_id
    UNION
    SELECT capture_ref_id, entity_id FROM eqos.acquisition_attempts
    WHERE capture_ref_id IS NOT NULL
    UNION
    SELECT c.capture_ref_id, o.entity_id
    FROM eqos.onboarding_records o
    LEFT JOIN eqos.namespace_verifications v ON v.onboarding_record_id = o.id
    JOIN eqos.evidence_input_captures c
        ON c.evidence_input_id IN (o.evidence_input_id, v.evidence_input_id)
    WHERE o.entity_id IS NOT NULL;

-- P3: an exchange capture is covered when a linked entity has an ADD whose next REMOVE (if
-- any) came after the capture's registration.
CREATE FUNCTION eqos.capture_covered(capture bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
    SELECT EXISTS (
        SELECT 1 FROM eqos.capture_refs r
        JOIN eqos.retention_classes k ON k.capture_ref_id = r.id
        JOIN eqos.capture_entities e ON e.capture_ref_id = r.id
        JOIN eqos.decisions a ON a.subject_kind = 'WATCHLIST' AND a.subject_id = e.entity_id
                              AND a.kind = 'ADD'
        WHERE r.id = capture AND k.retention_class = 'EXCHANGE_REFETCHABLE'
          AND NOT EXISTS (
              SELECT 1 FROM eqos.decisions x
              WHERE x.subject_kind = 'WATCHLIST' AND x.subject_id = a.subject_id
                AND x.kind = 'REMOVE' AND x.sequence > a.sequence
                AND x.recorded_at < r.registered_at))
$$;

-- R3: an ADD does not extend the entity's vendor and identity captures registered before it.
CREATE VIEW eqos.retention_limited AS
    SELECT a.id AS decision_id, e.entity_id, e.capture_ref_id, k.retention_class
    FROM eqos.decisions a
    JOIN eqos.capture_entities e ON e.entity_id = a.subject_id
    JOIN eqos.retention_classes k ON k.capture_ref_id = e.capture_ref_id
    JOIN eqos.capture_refs r ON r.id = e.capture_ref_id
    WHERE a.subject_kind = 'WATCHLIST' AND a.kind = 'ADD'
      AND k.retention_class IN ('VENDOR', 'IDENTITY') AND r.registered_at < a.recorded_at;

GRANT SELECT ON eqos.capture_entities, eqos.retention_limited
    TO eqos_runtime, eqos_panel, eqos_owner, eqos_purge;

-- RP3: the captures a new row rests on, from its capture, interpretation, occurrence,
-- attempt, package, evidence-input and trace columns and its body's location markers.
CREATE FUNCTION eqos.row_captures(tbl text, r jsonb) RETURNS bigint[] LANGUAGE sql STABLE AS $$
    WITH RECURSIVE traces(id) AS (
        SELECT (r ->> k)::bigint FROM unnest(ARRAY['calculation_trace_id', 'operand_trace_id']) k
        UNION
        SELECT o.operand_trace_id FROM eqos.calculation_trace_operands o
        JOIN traces t ON o.calculation_trace_id = t.id
    ), interps(id) AS (
        SELECT (r ->> k)::bigint FROM unnest(ARRAY['interpretation_id',
            'operand_interpretation_id', 'evidence_interpretation_id']) k
        UNION
        SELECT o.interpretation_id FROM eqos.calculation_trace_operands o
        JOIN traces t ON o.calculation_trace_id = t.id
    )
    SELECT coalesce(array_agg(DISTINCT c) FILTER (WHERE c IS NOT NULL), '{}') FROM (
        SELECT (r ->> CASE tbl WHEN 'capture_refs' THEN 'id' ELSE 'capture_ref_id' END)::bigint
        UNION ALL SELECT capture_ref_id FROM eqos.interpretations
            WHERE id IN (SELECT id FROM interps)
        UNION ALL SELECT capture_ref_id FROM eqos.occurrences
            WHERE id = (r ->> 'occurrence_id')::bigint
        UNION ALL SELECT capture_ref_id FROM eqos.acquisition_attempts
            WHERE id = (r ->> 'attempt_id')::bigint
        UNION ALL SELECT capture_ref_id FROM eqos.package_members
            WHERE package_id = (r ->> 'package_id')::bigint
        UNION ALL SELECT capture_ref_id FROM eqos.evidence_input_captures
            WHERE evidence_input_id = (r ->> 'evidence_input_id')::bigint
        UNION ALL SELECT m[1]::bigint
            FROM regexp_matches(coalesce(r ->> 'body', ''), '\{\{s:(\d+)\|', 'g') m
    ) found(c)
$$;

-- RP3 (c, d), guard v1: nothing new rests on a licence-ended source, and a vendor capture is
-- never quoted. Supports, onboarding records and identity events on vendor captures pass.
CREATE FUNCTION eqos.retention_guard() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, eqos AS $$
DECLARE
    rec         jsonb := to_jsonb(NEW);
    captures    bigint[] := eqos.row_captures(TG_TABLE_NAME, rec);
    ended       text;
BEGIN
    SELECT l.source_id INTO ended FROM eqos.licence_ends l
        WHERE l.source_id = rec ->> 'source_id'
           OR l.source_id IN (SELECT source_id FROM eqos.capture_refs WHERE id = ANY (captures))
        LIMIT 1;
    IF ended IS NOT NULL THEN
        RAISE EXCEPTION 'BEYOND_AUTHORITY: the % licence has ended; % refused', ended,
            TG_TABLE_NAME USING ERRCODE = '42501';
    END IF;
    IF TG_TABLE_NAME = 'numeric_claims' AND rec ->> 'citation_kind' = 'SOURCE_QUOTE'
       AND EXISTS (SELECT 1 FROM eqos.capture_refs WHERE id = ANY (captures)
                   AND eqos.is_vendor_source(source_id)) THEN
        RAISE EXCEPTION 'BEYOND_AUTHORITY: a vendor capture cannot be quoted'
            USING ERRCODE = '42501';
    END IF;
    RETURN NEW;
END $$;

DO $$
DECLARE
    table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY['capture_refs', 'numeric_claims', 'report_sections',
        'memory_supports', 'queue_item_inputs', 'queue_item_traces', 'legacy_evidence_bindings',
        'fact_admissions', 'evidence_input_captures', 'identity_events', 'onboarding_records',
        'namespace_verifications', 'occurrences', 'interpretations', 'interpretation_operands',
        'interpretation_condition_evidence', 'construction_traces', 'calculation_trace_operands',
        'result_source_values', 'run_inputs', 'acquisition_attempts', 'package_members'] LOOP
        EXECUTE format('CREATE TRIGGER a0_retention_guard BEFORE INSERT ON eqos.%I '
            'FOR EACH ROW EXECUTE FUNCTION eqos.retention_guard()', table_name);
    END LOOP;
END;
$$;
