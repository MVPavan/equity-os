-- D9 Task 5: purge records, probes, the vendor tombstone and the purge role's grants (plan
-- docs/workstreams/data-foundation/plans/D9.md R7, R8, R9). 0001--0028 are immutable. Purge
-- records and probes are append-only; the tombstone is the one in-place change to evidence
-- rows (ledger §6 item 4), limited to the A-05 redaction inventory
-- (docs/blueprint/amendments/2026-10-12-a05-derived-amounts.md).

-- R9: a per-source sample probe before exchange deletions; a non-match is a HIGH incident.
CREATE TABLE eqos.retention_probes (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_id       text NOT NULL,
    capture_ref_id  bigint NOT NULL REFERENCES eqos.capture_refs (id),
    url             text NOT NULL,
    outcome         text NOT NULL CHECK (outcome IN ('MATCH', 'MISMATCH', 'FAILED')),
    category        text CHECK (category IN ('INCOMPLETE', 'HTTP_STATUS', 'TIMEOUT', 'CONNECTION')),
    http_status     integer,
    fetched_sha256  text,
    severity        text CHECK (severity = 'HIGH'),
    recorded_at     timestamptz NOT NULL DEFAULT eqos.store_now(),
    CHECK ((outcome = 'MATCH') = (severity IS NULL)),
    CHECK ((outcome = 'FAILED') = (category IS NOT NULL))
);

-- R8 step 4: what was purged, why, from where, and the probe that cleared it (NULL: not
-- required). A capture restored and expired again gets a second record.
CREATE TABLE eqos.purge_records (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    purge_run_id    bigint NOT NULL REFERENCES eqos.purge_runs (id),
    capture_ref_id  bigint NOT NULL REFERENCES eqos.capture_refs (id),
    retention_class text NOT NULL,
    reason          text NOT NULL,
    url             text,
    blob_sha256     text NOT NULL,
    probe_id        bigint REFERENCES eqos.retention_probes (id),
    purged_at       timestamptz NOT NULL DEFAULT eqos.store_now()
);

DO $$
DECLARE
    table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY['retention_probes', 'purge_records'] LOOP
        EXECUTE format('CREATE TRIGGER reject_row_mutation BEFORE UPDATE OR DELETE ON eqos.%I '
            'FOR EACH ROW EXECUTE FUNCTION eqos.reject_mutation()', table_name);
        EXECUTE format('CREATE TRIGGER reject_truncate BEFORE TRUNCATE ON eqos.%I '
            'FOR EACH STATEMENT EXECUTE FUNCTION eqos.reject_mutation()', table_name);
        EXECUTE format('GRANT SELECT ON eqos.%I TO eqos_runtime, eqos_panel, eqos_owner',
            table_name);
    END LOOP;
END;
$$;

-- R9: an open probe incident closes on a later matching probe of its source. Task 6 (0030)
-- adds re-fetch mismatches to this view.
CREATE VIEW eqos.retention_incidents AS
    SELECT 'PROBE' AS kind, p.id, p.source_id, p.capture_ref_id, p.outcome, p.recorded_at
    FROM eqos.retention_probes p
    WHERE p.severity = 'HIGH' AND NOT EXISTS (
        SELECT 1 FROM eqos.retention_probes m
        WHERE m.source_id = p.source_id AND m.outcome = 'MATCH' AND m.id > p.id);
GRANT SELECT ON eqos.retention_incidents TO eqos_runtime, eqos_panel, eqos_owner;

-- R13: a tombstoned vendor occurrence keeps no sign.
ALTER TABLE eqos.occurrences ALTER COLUMN raw_sign DROP NOT NULL;

-- R7: a JSON object reduced to the listed keys.
CREATE FUNCTION eqos.jsonb_keep(document jsonb, keys text[]) RETURNS jsonb
LANGUAGE sql IMMUTABLE AS $$
    SELECT coalesce((SELECT jsonb_object_agg(key, value) FROM jsonb_each(document)
                     WHERE key = ANY (keys)), '{}'::jsonb)
$$;

-- R7: evidence stays immutable except an UPDATE of the inventory columns (the trigger's
-- arguments) inside the tombstone's transaction. DELETE stays refused. The flag is not the
-- boundary (no reading role holds UPDATE); it keeps the owner's own updates out.
CREATE FUNCTION eqos.reject_mutation_except_tombstone() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND coalesce(current_setting('eqos.tombstone', true), '') <> ''
       AND to_jsonb(OLD) - TG_ARGV = to_jsonb(NEW) - TG_ARGV THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'eqos evidence is immutable: % on %.% refused',
        TG_OP, TG_TABLE_SCHEMA, TG_TABLE_NAME;
END $$;

DROP TRIGGER reject_row_mutation ON eqos.occurrences;
CREATE TRIGGER reject_row_mutation BEFORE UPDATE OR DELETE ON eqos.occurrences FOR EACH ROW
    EXECUTE FUNCTION eqos.reject_mutation_except_tombstone(
        'raw_value_text', 'raw_sign', 'native_context', 'disclosure');
DROP TRIGGER reject_row_mutation ON eqos.interpretations;
CREATE TRIGGER reject_row_mutation BEFORE UPDATE OR DELETE ON eqos.interpretations FOR EACH ROW
    EXECUTE FUNCTION eqos.reject_mutation_except_tombstone(
        'value', 'lower', 'upper', 'transform_trace');
DROP TRIGGER reject_row_mutation ON eqos.calculation_traces;
CREATE TRIGGER reject_row_mutation BEFORE UPDATE OR DELETE ON eqos.calculation_traces
    FOR EACH ROW EXECUTE FUNCTION eqos.reject_mutation_except_tombstone(
        'value', 'lower', 'upper', 'exact_value', 'exact_lower', 'exact_upper');
DROP TRIGGER reject_row_mutation ON eqos.calculation_trace_operands;
CREATE TRIGGER reject_row_mutation BEFORE UPDATE OR DELETE ON eqos.calculation_trace_operands
    FOR EACH ROW EXECUTE FUNCTION eqos.reject_mutation_except_tombstone(
        'value', 'lower', 'upper', 'exact_value', 'exact_lower', 'exact_upper');
DROP TRIGGER reject_row_mutation ON eqos.result_source_values;
CREATE TRIGGER reject_row_mutation BEFORE UPDATE OR DELETE ON eqos.result_source_values
    FOR EACH ROW EXECUTE FUNCTION eqos.reject_mutation_except_tombstone('value', 'lower', 'upper');
DROP TRIGGER reject_row_mutation ON eqos.acquisition_attempts;
CREATE TRIGGER reject_row_mutation BEFORE UPDATE OR DELETE ON eqos.acquisition_attempts
    FOR EACH ROW EXECUTE FUNCTION eqos.reject_mutation_except_tombstone('reason');

-- R7: tombstone a PURGE_PENDING VENDOR capture's payload in place, per the A-05 inventory.
CREATE FUNCTION eqos.tombstone_vendor_capture(capture bigint) RETURNS void LANGUAGE plpgsql
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
    PERFORM set_config('eqos.tombstone', '', true);
END $$;
REVOKE ALL ON FUNCTION eqos.tombstone_vendor_capture(bigint) FROM PUBLIC;

-- The purge role (Task 3 and 4 notes): it reads everything the hold query, coverage and the
-- final backup read, writes the retention tables, takes epochs and tombstones.
GRANT SELECT ON ALL TABLES IN SCHEMA eqos TO eqos_purge;
GRANT INSERT ON eqos.purge_runs, eqos.purge_run_closures, eqos.capture_states,
    eqos.purge_records, eqos.retention_probes TO eqos_purge;
GRANT USAGE ON SEQUENCE eqos.retention_epoch TO eqos_purge;
GRANT EXECUTE ON FUNCTION eqos.store_now(), eqos.tombstone_vendor_capture(bigint)
    TO eqos_purge;
