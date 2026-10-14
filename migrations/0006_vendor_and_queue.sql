-- D1b: source-qualified vendor evidence and the append-only review queue.
-- 0001--0005 are immutable. No stored row is rewritten: existing first-party values keep a
-- NULL source_id/surface.
ALTER TABLE eqos.occurrences DROP CONSTRAINT occurrences_representation_check;
ALTER TABLE eqos.occurrences ADD CHECK (representation IN ('XBRL','PDF','HTML','JSON'));
ALTER TABLE eqos.interpretations DROP CONSTRAINT interpretations_representation_check;
ALTER TABLE eqos.interpretations ADD CHECK (representation IN ('XBRL','PDF','HTML','JSON'));
ALTER TABLE eqos.acquisition_attempts DROP CONSTRAINT acquisition_attempts_representation_check;
ALTER TABLE eqos.acquisition_attempts ADD CHECK (representation IN ('XBRL','PDF','HTML','JSON'));
ALTER TABLE eqos.acquisition_attempts ADD CHECK (representation IN ('XBRL','PDF') OR package_id IS NULL);
ALTER TABLE eqos.result_source_values DROP CONSTRAINT result_source_values_representation_check;
ALTER TABLE eqos.result_source_values ADD CHECK (representation IN ('XBRL','PDF','HTML','JSON'));
ALTER TABLE eqos.pair_adjustments DROP CONSTRAINT pair_adjustments_representation_check;
ALTER TABLE eqos.pair_adjustments ADD CHECK (representation IN ('XBRL','PDF','HTML','JSON'));
ALTER TABLE eqos.pair_outcomes DROP CONSTRAINT pair_outcomes_pair_kind_check;
ALTER TABLE eqos.pair_outcomes ADD CHECK (pair_kind IN (
    'EXTRACTION','REPORTED_VS_DERIVED','CORROBORATION','DIAGNOSTIC'));
ALTER TABLE eqos.calculation_trace_operands DROP CONSTRAINT calculation_trace_operands_selection_source_check;
ALTER TABLE eqos.calculation_trace_operands ADD CHECK (selection_source IN (
    'PACKAGE_AS_REPORTED','PACKAGE_OPENING_DISCLOSURE','INSTANT_OWN_SELECTION',
    'HISTORICAL_PACKAGE','VENDOR_CAPTURE'));
ALTER TABLE eqos.calculation_trace_operands ADD CHECK (
    selection_source <> 'VENDOR_CAPTURE' OR source_state <> 'VALUE'
    OR num_nonnulls(interpretation_id,operand_trace_id)=1);

ALTER TABLE eqos.result_source_values ADD COLUMN source_id text;
ALTER TABLE eqos.result_source_values ADD COLUMN surface text;
ALTER TABLE eqos.result_source_values DROP CONSTRAINT result_source_values_result_id_source_role_representation_key;
ALTER TABLE eqos.result_source_values ADD UNIQUE NULLS NOT DISTINCT
    (result_id,source_role,source_id,surface,representation);
ALTER TABLE eqos.result_source_values ADD CHECK ((source_id IS NULL)=(surface IS NULL));
ALTER TABLE eqos.result_source_values ADD CHECK (source_role IN (
    'FIRST_PARTY','REPORTED_COUNTERPART','INDEPENDENT_VENDOR','DIAGNOSTIC'));
ALTER TABLE eqos.result_source_values ADD CHECK (CASE
    WHEN source_role IN ('INDEPENDENT_VENDOR','DIAGNOSTIC')
    THEN source_id IS NOT NULL AND representation IN ('HTML','JSON')
    ELSE representation IN ('XBRL','PDF') END);
ALTER TABLE eqos.result_source_values ADD CHECK (
    source_role NOT IN ('INDEPENDENT_VENDOR','DIAGNOSTIC') OR source_state <> 'VALUE'
    OR num_nonnulls(interpretation_id,calculation_trace_id)=1);

ALTER TABLE eqos.run_versions DROP CONSTRAINT run_versions_pin_check;
ALTER TABLE eqos.run_versions ADD CHECK (pin IN (
    'dictionary','formula_set','mapping_set','normalisation_policy','extractor_xbrl','extractor_pdf',
    'rounding_policy','definition_set','comparison_policy','alignment_rules','vendor_extractor'));
ALTER TABLE eqos.run_versions ADD COLUMN source_id text;
ALTER TABLE eqos.run_versions ADD COLUMN surface text;
ALTER TABLE eqos.run_versions DROP CONSTRAINT run_versions_run_id_pin_key;
ALTER TABLE eqos.run_versions ADD UNIQUE NULLS NOT DISTINCT (run_id,pin,source_id,surface);
ALTER TABLE eqos.run_versions ADD CHECK (
    (pin='vendor_extractor') = (source_id IS NOT NULL AND surface IS NOT NULL)
    AND (source_id IS NULL)=(surface IS NULL));

-- An item is keyed by measurement key, pair, outcome and input hash (data spec §5).
CREATE TABLE eqos.queue_items (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id bigint NOT NULL REFERENCES eqos.runs(id),
    key_digest text, measurement_key jsonb,
    pair_identity text NOT NULL, outcome text NOT NULL, input_sha256 text NOT NULL,
    severity text NOT NULL CHECK (severity IN ('HIGH','MEDIUM','LOW')),
    diagnostic boolean NOT NULL,
    routing_reason text NOT NULL, reason_code text,
    source_refs jsonb NOT NULL,
    predecessor_item_id bigint REFERENCES eqos.queue_items(id),
    recorded_at timestamptz NOT NULL,
    created_xid bigint NOT NULL,
    UNIQUE NULLS NOT DISTINCT (key_digest,pair_identity,outcome,input_sha256),
    CHECK ((measurement_key IS NULL)=(key_digest IS NULL)),
    CHECK (key_digest IS NOT NULL OR outcome='UNMAPPED')
);
CREATE TABLE eqos.queue_item_inputs (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    item_id bigint NOT NULL REFERENCES eqos.queue_items(id),
    occurrence_id bigint REFERENCES eqos.occurrences(id),
    interpretation_id bigint REFERENCES eqos.interpretations(id),
    attempt_id bigint REFERENCES eqos.acquisition_attempts(id),
    CHECK (num_nonnulls(occurrence_id,interpretation_id,attempt_id)=1),
    UNIQUE NULLS NOT DISTINCT (item_id,occurrence_id,interpretation_id,attempt_id)
);
CREATE TABLE eqos.queue_run_items (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id bigint NOT NULL REFERENCES eqos.runs(id),
    item_id bigint NOT NULL REFERENCES eqos.queue_items(id),
    recorded_at timestamptz NOT NULL,
    UNIQUE (run_id,item_id)
);
CREATE TABLE eqos.queue_dispositions (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    item_id bigint NOT NULL REFERENCES eqos.queue_items(id),
    kind text NOT NULL CHECK (kind IN ('ACCEPTED_AS_DEFINITION','MAPPING_FIX','PARSER_DEFECT',
        'FILER_INCONSISTENCY','ALTERNATE_READ_REQUIRED','DISMISSED')),
    reason text NOT NULL CHECK (reason <> ''),
    decider text NOT NULL CHECK (decider <> ''),
    evidence_ref text NOT NULL CHECK (evidence_ref <> ''),
    explained_amount numeric,
    recorded_at timestamptz NOT NULL
);

-- Recorded times are the store clock's, never the caller's.
CREATE FUNCTION eqos.record_queue_time() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog,eqos AS $$
BEGIN
    NEW.recorded_at := eqos.store_now();
    IF TG_TABLE_NAME='queue_items' THEN NEW.created_xid := txid_current(); END IF;
    RETURN NEW;
END $$;

-- An item's evidence is sealed with the item: inputs only in the creating transaction.
CREATE FUNCTION eqos.check_queue_input_seal() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog,eqos AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM eqos.queue_items
                   WHERE id=NEW.item_id AND created_xid=txid_current()) THEN
        RAISE EXCEPTION 'queue item evidence is sealed with the item transaction'
            USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER check_queue_input_seal BEFORE INSERT ON eqos.queue_item_inputs
FOR EACH ROW EXECUTE FUNCTION eqos.check_queue_input_seal();

DO $$
DECLARE name text;
BEGIN
    FOREACH name IN ARRAY ARRAY['queue_items','queue_item_inputs','queue_run_items',
                                'queue_dispositions'] LOOP
        EXECUTE format('CREATE TRIGGER reject_row_mutation BEFORE UPDATE OR DELETE ON eqos.%I '
            'FOR EACH ROW EXECUTE FUNCTION eqos.reject_mutation()', name);
        EXECUTE format('CREATE TRIGGER reject_truncate BEFORE TRUNCATE ON eqos.%I '
            'FOR EACH STATEMENT EXECUTE FUNCTION eqos.reject_mutation()', name);
        IF name <> 'queue_item_inputs' THEN
            EXECUTE format('CREATE TRIGGER record_queue_time BEFORE INSERT ON eqos.%I '
                'FOR EACH ROW EXECUTE FUNCTION eqos.record_queue_time()', name);
        END IF;
    END LOOP;
END $$;
GRANT SELECT, INSERT ON eqos.queue_items, eqos.queue_item_inputs, eqos.queue_run_items,
    eqos.queue_dispositions TO eqos_runtime;
GRANT USAGE ON SEQUENCE eqos.queue_items_id_seq, eqos.queue_item_inputs_id_seq,
    eqos.queue_run_items_id_seq, eqos.queue_dispositions_id_seq TO eqos_runtime;
