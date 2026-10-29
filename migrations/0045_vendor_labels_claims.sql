-- VENDOR-SURFACE Task 16: advisory labels and inferred spans, never model numbers.
CREATE TABLE eqos.vendor_label_proposals (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_id text NOT NULL, surface text NOT NULL, label text NOT NULL, units text[] NOT NULL,
    field text, reason text NOT NULL CHECK (reason IN ('MAPPED','NOT_IN_DICTIONARY',
        'LABEL_ALTERED','UNIT_INCOMPATIBLE','MODEL_UNMAPPED','MALFORMED_REPLY')),
    epistemic_class text CHECK (epistemic_class = 'inferred'),
    model_id text NOT NULL, prompt_version text NOT NULL, dictionary_version text NOT NULL,
    prompt text NOT NULL, raw_response text NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT eqos.store_now(),
    CHECK (field IS NULL OR epistemic_class IS NOT DISTINCT FROM 'inferred'),
    CHECK ((field IS NOT NULL) = (reason = 'MAPPED'))
);
CREATE INDEX ON eqos.vendor_label_proposals
    (source_id, surface, label, model_id, prompt_version, dictionary_version);
CREATE TABLE eqos.vendor_text_claims (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    capture_ref_id bigint NOT NULL REFERENCES eqos.capture_refs (id),
    surface text NOT NULL, kind text NOT NULL CHECK (kind IN ('NAME','CLAIM')),
    span_start integer NOT NULL CHECK (span_start >= 0),
    span_end integer NOT NULL CHECK (span_end > span_start), text text,
    model_id text NOT NULL, prompt_version text NOT NULL,
    epistemic_class text NOT NULL CHECK (epistemic_class = 'inferred'),
    recorded_at timestamptz NOT NULL DEFAULT eqos.store_now(),
    UNIQUE (capture_ref_id, surface, model_id, prompt_version, kind, span_start, span_end)
);
DO $$
DECLARE name text;
BEGIN
    FOREACH name IN ARRAY ARRAY['vendor_label_proposals','vendor_text_claims'] LOOP
        EXECUTE format('CREATE TRIGGER a0_retention_guard BEFORE INSERT ON eqos.%I '
            'FOR EACH ROW EXECUTE FUNCTION eqos.retention_guard()', name);
        IF name = 'vendor_text_claims' THEN
            EXECUTE format('CREATE TRIGGER reject_row_mutation BEFORE UPDATE OR DELETE ON eqos.%I '
                'FOR EACH ROW EXECUTE FUNCTION eqos.reject_mutation_except_tombstone(''text'')', name);
        ELSE
            EXECUTE format('CREATE TRIGGER reject_row_mutation BEFORE UPDATE OR DELETE ON eqos.%I '
                'FOR EACH ROW EXECUTE FUNCTION eqos.reject_mutation()', name);
        END IF;
        EXECUTE format('CREATE TRIGGER reject_truncate BEFORE TRUNCATE ON eqos.%I '
            'FOR EACH STATEMENT EXECUTE FUNCTION eqos.reject_mutation()', name);
        EXECUTE format('GRANT INSERT ON eqos.%I TO eqos_runtime', name);
        EXECUTE format('GRANT USAGE ON SEQUENCE eqos.%I TO eqos_runtime', name || '_id_seq');
        EXECUTE format('GRANT SELECT ON eqos.%I TO eqos_runtime, eqos_panel, eqos_owner, eqos_purge', name);
    END LOOP;
END $$;
-- The shared guard already enforces licence end; spans additionally require retained originals.
CREATE FUNCTION eqos.vendor_claim_retained() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF eqos.capture_state(NEW.capture_ref_id) NOT IN ('RETAINED','RESTORED') THEN
        RAISE EXCEPTION 'ORIGINAL_EXPIRED: vendor claim capture is not retained' USING ERRCODE='55000';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER a1_claim_retained BEFORE INSERT ON eqos.vendor_text_claims
    FOR EACH ROW EXECUTE FUNCTION eqos.vendor_claim_retained();

-- Extend the existing tombstone without duplicating or changing its cell/trace inventory.
ALTER FUNCTION eqos.tombstone_vendor_capture(bigint) RENAME TO tombstone_vendor_capture_cells;
CREATE FUNCTION eqos.tombstone_vendor_capture(capture bigint) RETURNS void LANGUAGE plpgsql
SECURITY DEFINER SET search_path = pg_catalog, eqos AS $$
BEGIN
    PERFORM eqos.tombstone_vendor_capture_cells(capture);
    PERFORM set_config('eqos.tombstone', capture::text, true);
    UPDATE eqos.vendor_text_claims SET text = NULL WHERE capture_ref_id = capture;
    PERFORM set_config('eqos.tombstone', '', true);
END $$;
REVOKE ALL ON FUNCTION eqos.tombstone_vendor_capture(bigint) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION eqos.tombstone_vendor_capture(bigint) TO eqos_purge;
