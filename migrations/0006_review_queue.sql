-- D1b: source-qualified vendor evidence and append-only local review governance.
-- 0001--0005 are immutable. Existing immutable rows are backfilled only here,
-- from their actual capture/attempt/trace provenance, without synthetic source ids.
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
-- Package membership and alignment participants retain their original XBRL/PDF CHECKs.

CREATE FUNCTION eqos.trace_capture_ids(root_id bigint) RETURNS TABLE(capture_ref_id bigint)
LANGUAGE sql STABLE SET search_path = pg_catalog, eqos AS $$
    WITH RECURSIVE traces(id) AS (
        SELECT root_id
        UNION
        SELECT o.operand_trace_id FROM eqos.calculation_trace_operands o
        JOIN traces t ON o.calculation_trace_id = t.id WHERE o.operand_trace_id IS NOT NULL
    )
    SELECT DISTINCT i.capture_ref_id FROM traces t
    JOIN eqos.calculation_trace_operands o ON o.calculation_trace_id = t.id
    JOIN eqos.interpretations i ON i.id = o.interpretation_id
$$;

CREATE FUNCTION eqos.trace_leaf_representations(root_id bigint) RETURNS TABLE(representation text)
LANGUAGE sql STABLE SET search_path=pg_catalog,eqos AS $$
    WITH RECURSIVE traces(id) AS (
        SELECT root_id UNION
        SELECT o.operand_trace_id FROM eqos.calculation_trace_operands o
        JOIN traces t ON o.calculation_trace_id=t.id WHERE o.operand_trace_id IS NOT NULL
    )
    SELECT DISTINCT i.representation FROM traces t
    JOIN eqos.calculation_trace_operands o ON o.calculation_trace_id=t.id
    JOIN eqos.interpretations i ON i.id=o.interpretation_id
$$;

CREATE FUNCTION eqos.check_vendor_operand_source() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog,eqos AS $$
DECLARE valid boolean;
BEGIN
    IF NEW.selection_source IS DISTINCT FROM 'VENDOR_CAPTURE' OR NEW.source_state<>'VALUE' THEN
        RETURN NEW;
    END IF;
    IF NEW.interpretation_id IS NOT NULL THEN
        SELECT representation IN ('HTML','JSON') INTO valid FROM eqos.interpretations
        WHERE id=NEW.interpretation_id;
    ELSE
        WITH RECURSIVE traces(id) AS (
            SELECT NEW.operand_trace_id UNION
            SELECT o.operand_trace_id FROM eqos.calculation_trace_operands o
            JOIN traces t ON o.calculation_trace_id=t.id WHERE o.operand_trace_id IS NOT NULL
        )
        SELECT count(DISTINCT i.capture_ref_id)=1 AND bool_and(i.representation IN ('HTML','JSON'))
        INTO valid FROM traces t JOIN eqos.calculation_trace_operands o ON o.calculation_trace_id=t.id
        JOIN eqos.interpretations i ON i.id=o.interpretation_id;
    END IF;
    IF NOT coalesce(valid,false) THEN
        RAISE EXCEPTION 'vendor operand must name a selected vendor capture or its computed child'
            USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER check_vendor_operand_source BEFORE INSERT ON eqos.calculation_trace_operands
FOR EACH ROW EXECUTE FUNCTION eqos.check_vendor_operand_source();

ALTER TABLE eqos.result_source_values ADD COLUMN source_id text;
ALTER TABLE eqos.result_source_values ADD COLUMN surface text;
ALTER TABLE eqos.result_source_values DISABLE TRIGGER reject_row_mutation;
UPDATE eqos.result_source_values v SET source_id=c.source_id, surface=c.surface
FROM eqos.interpretations i JOIN eqos.capture_refs c ON c.id=i.capture_ref_id
WHERE v.interpretation_id=i.id;
UPDATE eqos.result_source_values v SET source_id=a.source_id, surface=a.surface
FROM eqos.acquisition_attempts a WHERE v.attempt_id=a.id AND v.source_id IS NULL;
WITH identities AS (
    SELECT v.id, min(c.source_id) AS source_id, min(c.surface) AS surface
    FROM eqos.result_source_values v
    CROSS JOIN LATERAL eqos.trace_capture_ids(v.calculation_trace_id) t
    JOIN eqos.capture_refs c ON c.id=t.capture_ref_id
    WHERE v.source_id IS NULL AND v.calculation_trace_id IS NOT NULL
    GROUP BY v.id HAVING count(DISTINCT (c.source_id,c.surface))=1
)
UPDATE eqos.result_source_values v SET source_id=s.source_id, surface=s.surface
FROM identities s WHERE v.id=s.id;
ALTER TABLE eqos.result_source_values ENABLE TRIGGER reject_row_mutation;
ALTER TABLE eqos.result_source_values DROP CONSTRAINT result_source_values_result_id_source_role_representation_key;
ALTER TABLE eqos.result_source_values ADD UNIQUE NULLS NOT DISTINCT
    (result_id,source_role,representation,source_id,surface);
ALTER TABLE eqos.result_source_values ADD CHECK ((source_id IS NULL)=(surface IS NULL));
ALTER TABLE eqos.result_source_values ADD CHECK (source_role IN (
    'FIRST_PARTY','REPORTED_COUNTERPART','INDEPENDENT_VENDOR','DIAGNOSTIC'));
ALTER TABLE eqos.result_source_values ADD CHECK (
    source_role NOT IN ('INDEPENDENT_VENDOR','DIAGNOSTIC') OR
    (source_id IS NOT NULL AND surface IS NOT NULL AND representation IN ('HTML','JSON')));

ALTER TABLE eqos.result_source_values ADD CHECK (
    source_role NOT IN ('INDEPENDENT_VENDOR','DIAGNOSTIC') OR source_state <> 'VALUE'
    OR num_nonnulls(interpretation_id,calculation_trace_id)=1);

ALTER TABLE eqos.result_source_values ADD CHECK (
    source_role NOT IN ('FIRST_PARTY','REPORTED_COUNTERPART') OR representation IN ('XBRL','PDF'));

CREATE FUNCTION eqos.check_vendor_value_source() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog,eqos AS $$
DECLARE matching boolean; captures bigint[];
BEGIN
    IF NEW.source_role NOT IN ('INDEPENDENT_VENDOR','DIAGNOSTIC') THEN RETURN NEW; END IF;
    IF NEW.interpretation_id IS NOT NULL THEN
        SELECT c.source_id=NEW.source_id AND c.surface=NEW.surface
            AND i.representation=NEW.representation INTO matching
        FROM eqos.interpretations i JOIN eqos.capture_refs c ON c.id=i.capture_ref_id
        WHERE i.id=NEW.interpretation_id;
    ELSIF NEW.calculation_trace_id IS NOT NULL THEN
        SELECT array_agg(t.capture_ref_id) INTO captures
        FROM eqos.trace_capture_ids(NEW.calculation_trace_id) t;
        SELECT count(*)=1 AND bool_and(c.source_id=NEW.source_id AND c.surface=NEW.surface)
            AND (SELECT count(*)=1 AND bool_and(r.representation=NEW.representation
                    AND r.representation IN ('HTML','JSON'))
                FROM eqos.trace_leaf_representations(NEW.calculation_trace_id) r)
            INTO matching FROM eqos.capture_refs c WHERE c.id=ANY(captures);
    ELSIF NEW.attempt_id IS NOT NULL THEN
        SELECT a.source_id=NEW.source_id AND a.surface=NEW.surface
            AND a.representation=NEW.representation INTO matching
        FROM eqos.acquisition_attempts a WHERE a.id=NEW.attempt_id;
    ELSE matching := NEW.source_state <> 'VALUE';
    END IF;
    IF NOT coalesce(matching,false) THEN
        RAISE EXCEPTION 'vendor value source/surface differs from selected evidence' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER check_vendor_value_source BEFORE INSERT ON eqos.result_source_values
FOR EACH ROW EXECUTE FUNCTION eqos.check_vendor_value_source();

ALTER TABLE eqos.run_versions DROP CONSTRAINT run_versions_pin_check;
ALTER TABLE eqos.run_versions ADD CHECK (pin IN (
    'dictionary','formula_set','mapping_set','normalisation_policy','extractor_xbrl','extractor_pdf',
    'rounding_policy','definition_set','comparison_policy','alignment_rules','vendor_extractor',
    'source_authority'));
ALTER TABLE eqos.run_versions ADD COLUMN source_id text;
ALTER TABLE eqos.run_versions ADD COLUMN surface text;
ALTER TABLE eqos.run_versions DROP CONSTRAINT run_versions_run_id_pin_key;
ALTER TABLE eqos.run_versions ADD UNIQUE NULLS NOT DISTINCT(run_id,pin,source_id,surface);
ALTER TABLE eqos.run_versions ADD CHECK (
    (pin='vendor_extractor' AND source_id IS NOT NULL AND surface IS NOT NULL)
    OR (pin<>'vendor_extractor' AND source_id IS NULL AND surface IS NULL));

CREATE TABLE eqos.queue_items (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id bigint NOT NULL REFERENCES eqos.runs(id),
    key_digest text, measurement_key jsonb,
    pair_identity text NOT NULL, outcome text NOT NULL, input_sha256 text NOT NULL,
    severity text NOT NULL CHECK(severity IN ('HIGH','MEDIUM','LOW')),
    diagnostic boolean NOT NULL DEFAULT false,
    routing_reason text NOT NULL DEFAULT '', reason_code text,
    source_refs jsonb NOT NULL DEFAULT '[]',
    predecessor_item_id bigint REFERENCES eqos.queue_items(id),
    recorded_at timestamptz NOT NULL DEFAULT eqos.store_now(),
    created_xid bigint NOT NULL DEFAULT txid_current(),
    UNIQUE NULLS NOT DISTINCT(key_digest,pair_identity,outcome,input_sha256),
    CHECK((measurement_key IS NULL)=(key_digest IS NULL)),
    CHECK(key_digest IS NOT NULL OR outcome='UNMAPPED')
);
CREATE TABLE eqos.queue_item_inputs (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    item_id bigint NOT NULL REFERENCES eqos.queue_items(id),
    occurrence_id bigint REFERENCES eqos.occurrences(id),
    interpretation_id bigint REFERENCES eqos.interpretations(id),
    attempt_id bigint REFERENCES eqos.acquisition_attempts(id),
    CHECK(num_nonnulls(occurrence_id,interpretation_id,attempt_id)=1),
    UNIQUE NULLS NOT DISTINCT(item_id,occurrence_id,interpretation_id,attempt_id)
);
CREATE TABLE eqos.queue_run_items (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id bigint NOT NULL REFERENCES eqos.runs(id), item_id bigint NOT NULL REFERENCES eqos.queue_items(id),
    recorded_at timestamptz NOT NULL DEFAULT eqos.store_now(), UNIQUE(run_id,item_id)
);
CREATE TABLE eqos.queue_disposition_proposals (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    item_id bigint NOT NULL REFERENCES eqos.queue_items(id),
    kind text NOT NULL CHECK(kind IN ('ACCEPTED_AS_DEFINITION','MAPPING_FIX','PARSER_DEFECT',
        'FILER_INCONSISTENCY','ALTERNATE_READ_REQUIRED','DISMISSED')),
    reason text NOT NULL, proposer text NOT NULL, evidence_ref text NOT NULL,
    proposal_sha256 text NOT NULL, subject_sha256 text NOT NULL,
    explained_amount numeric, amount_trace_id bigint REFERENCES eqos.calculation_traces(id),
    producer_database_identity text NOT NULL DEFAULT session_user,
    recorded_at timestamptz NOT NULL DEFAULT eqos.store_now(),
    UNIQUE(item_id,proposal_sha256)
);
CREATE TABLE eqos.approval_review_evidence (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    subject_kind text NOT NULL CHECK(subject_kind IN ('QUEUE_DISPOSITION','INTERPRETATION')),
    subject_id bigint NOT NULL,
    proposal_id bigint NOT NULL REFERENCES eqos.queue_disposition_proposals(id),
    proposal_sha256 text NOT NULL, subject_sha256 text NOT NULL,
    evidence_sha256 text NOT NULL, evidence_document jsonb NOT NULL, raw_evidence bytea NOT NULL,
    evidence_origin text NOT NULL CHECK(evidence_origin IN ('INDEPENDENT_REVIEW','OWNER_RULING')),
    decision text NOT NULL CHECK(decision IN ('ACCEPT','REJECT')),
    decider text NOT NULL, owner_amount numeric,
    producer_database_identity text NOT NULL DEFAULT session_user,
    recorded_at timestamptz NOT NULL DEFAULT eqos.store_now(),
    UNIQUE(evidence_sha256,subject_sha256,proposal_sha256),
    CHECK(owner_amount IS NULL OR evidence_origin='OWNER_RULING')
);
CREATE TABLE eqos.approval_receipts (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    subject_kind text NOT NULL CHECK(subject_kind IN ('QUEUE_DISPOSITION','INTERPRETATION')),
    subject_id bigint NOT NULL,
    proposal_id bigint NOT NULL REFERENCES eqos.queue_disposition_proposals(id),
    proposal_sha256 text NOT NULL, subject_sha256 text NOT NULL,
    decision text NOT NULL CHECK(decision IN ('ACCEPT','REJECT')),
    review_evidence_id bigint NOT NULL REFERENCES eqos.approval_review_evidence(id),
    review_evidence_sha256 text NOT NULL, decider text NOT NULL,
    producer_database_identity text NOT NULL DEFAULT session_user,
    recorded_at timestamptz NOT NULL DEFAULT eqos.store_now(),
    UNIQUE(proposal_id,review_evidence_id)
);
CREATE TABLE eqos.queue_dispositions (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    item_id bigint NOT NULL REFERENCES eqos.queue_items(id),
    proposal_id bigint NOT NULL REFERENCES eqos.queue_disposition_proposals(id),
    approval_receipt_id bigint NOT NULL REFERENCES eqos.approval_receipts(id),
    kind text NOT NULL CHECK(kind IN ('ACCEPTED_AS_DEFINITION','MAPPING_FIX','PARSER_DEFECT',
        'FILER_INCONSISTENCY','ALTERNATE_READ_REQUIRED','DISMISSED')),
    reason text NOT NULL, proposer text NOT NULL, decider text NOT NULL, evidence_ref text NOT NULL,
    explained_amount numeric, amount_trace_id bigint REFERENCES eqos.calculation_traces(id),
    producer_database_identity text NOT NULL DEFAULT session_user,
    recorded_at timestamptz NOT NULL DEFAULT eqos.store_now(),
    UNIQUE(proposal_id,approval_receipt_id)
);

CREATE FUNCTION eqos.record_queue_time() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog,eqos AS $$
BEGIN
    NEW.recorded_at := eqos.store_now();
    IF TG_TABLE_NAME='queue_items' THEN NEW.created_xid := txid_current(); END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER record_queue_time BEFORE INSERT ON eqos.queue_items
FOR EACH ROW EXECUTE FUNCTION eqos.record_queue_time();
CREATE TRIGGER record_queue_time BEFORE INSERT ON eqos.queue_run_items
FOR EACH ROW EXECUTE FUNCTION eqos.record_queue_time();
CREATE FUNCTION eqos.check_queue_input_seal() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog,eqos AS $$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM eqos.queue_items WHERE id=NEW.item_id AND created_xid=txid_current()) THEN
        RAISE EXCEPTION 'queue input associations are sealed with the item transaction'
            USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER check_queue_input_seal BEFORE INSERT ON eqos.queue_item_inputs
FOR EACH ROW EXECUTE FUNCTION eqos.check_queue_input_seal();

CREATE FUNCTION eqos.record_review_producer() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog,eqos AS $$
BEGIN
    NEW.producer_database_identity := session_user;
    NEW.recorded_at := eqos.store_now();
    IF TG_TABLE_NAME IN ('approval_review_evidence','approval_receipts','queue_dispositions')
        AND session_user <> 'eqos_migrator' THEN
        RAISE EXCEPTION 'protected review decision requires authenticated migrator'
            USING ERRCODE='42501';
    END IF;
    IF TG_TABLE_NAME='queue_disposition_proposals' THEN
        IF session_user='eqos_runtime'
            AND (NEW.explained_amount IS NOT NULL OR NEW.amount_trace_id IS NOT NULL) THEN
            RAISE EXCEPTION 'runtime proposals cannot supply amounts' USING ERRCODE='42501';
        END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE FUNCTION eqos.check_approval_binding() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog,eqos AS $$
DECLARE valid boolean;
BEGIN
    IF TG_TABLE_NAME='approval_receipts' THEN
        SELECT e.proposal_id=NEW.proposal_id AND e.proposal_sha256=NEW.proposal_sha256
            AND e.subject_kind=NEW.subject_kind AND e.subject_id=NEW.subject_id
            AND e.subject_sha256=NEW.subject_sha256 AND e.evidence_sha256=NEW.review_evidence_sha256
            AND e.decision=NEW.decision AND e.decider=NEW.decider
            AND p.proposal_sha256=NEW.proposal_sha256 AND p.subject_sha256=NEW.subject_sha256
            INTO valid FROM eqos.approval_review_evidence e
            JOIN eqos.queue_disposition_proposals p ON p.id=e.proposal_id
            WHERE e.id=NEW.review_evidence_id;
    ELSE
        SELECT r.decision='ACCEPT' AND r.subject_kind='QUEUE_DISPOSITION'
            AND r.subject_id=NEW.item_id AND r.proposal_id=NEW.proposal_id
            AND p.item_id=NEW.item_id AND p.kind=NEW.kind AND p.reason=NEW.reason
            AND p.proposer=NEW.proposer AND p.evidence_ref=NEW.evidence_ref
            AND r.decider=NEW.decider AND r.subject_sha256=p.subject_sha256
            AND NEW.explained_amount IS NOT DISTINCT FROM p.explained_amount
            AND NEW.amount_trace_id IS NOT DISTINCT FROM p.amount_trace_id
            AND r.proposal_sha256=p.proposal_sha256
            AND ((NEW.explained_amount IS NULL AND NEW.amount_trace_id IS NULL)
              OR (NEW.amount_trace_id IS NOT NULL AND NEW.explained_amount=(
                  SELECT value FROM eqos.calculation_traces WHERE id=NEW.amount_trace_id))
              OR (NEW.amount_trace_id IS NULL AND e.evidence_origin='OWNER_RULING'
                  AND NEW.explained_amount=e.owner_amount))
            INTO valid FROM eqos.approval_receipts r
            JOIN eqos.queue_disposition_proposals p ON p.id=r.proposal_id
            JOIN eqos.approval_review_evidence e ON e.id=r.review_evidence_id
            WHERE r.id=NEW.approval_receipt_id;
    END IF;
    IF NOT coalesce(valid,false) THEN
        RAISE EXCEPTION 'review decision does not match its sealed subject/proposal/evidence'
            USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER check_approval_binding BEFORE INSERT ON eqos.approval_receipts
FOR EACH ROW EXECUTE FUNCTION eqos.check_approval_binding();
CREATE TRIGGER check_approval_binding BEFORE INSERT ON eqos.queue_dispositions
FOR EACH ROW EXECUTE FUNCTION eqos.check_approval_binding();

DO $$
DECLARE name text;
BEGIN
    FOREACH name IN ARRAY ARRAY['queue_items','queue_item_inputs','queue_run_items',
      'queue_disposition_proposals','approval_review_evidence','approval_receipts','queue_dispositions'] LOOP
        EXECUTE format('CREATE TRIGGER reject_row_mutation BEFORE UPDATE OR DELETE ON eqos.%I '
            'FOR EACH ROW EXECUTE FUNCTION eqos.reject_mutation()',name);
        EXECUTE format('CREATE TRIGGER reject_truncate BEFORE TRUNCATE ON eqos.%I '
            'FOR EACH STATEMENT EXECUTE FUNCTION eqos.reject_mutation()',name);
        IF name IN ('queue_disposition_proposals','approval_review_evidence','approval_receipts','queue_dispositions') THEN
            EXECUTE format('CREATE TRIGGER record_review_producer BEFORE INSERT ON eqos.%I '
                'FOR EACH ROW EXECUTE FUNCTION eqos.record_review_producer()',name);
        END IF;
    END LOOP;
END $$;
GRANT SELECT,INSERT ON eqos.queue_items,eqos.queue_item_inputs,eqos.queue_run_items,
    eqos.queue_disposition_proposals TO eqos_runtime;
GRANT SELECT ON eqos.approval_review_evidence,eqos.approval_receipts,eqos.queue_dispositions TO eqos_runtime;
GRANT USAGE ON SEQUENCE eqos.queue_items_id_seq,eqos.queue_item_inputs_id_seq,
    eqos.queue_run_items_id_seq,eqos.queue_disposition_proposals_id_seq,
    eqos.approval_review_evidence_id_seq,eqos.approval_receipts_id_seq,
    eqos.queue_dispositions_id_seq TO eqos_runtime;
-- Preserve 0004's explicit runtime refusal on the protected store clock sequence.
REVOKE ALL ON SEQUENCE eqos.store_clock_us FROM eqos_runtime;
