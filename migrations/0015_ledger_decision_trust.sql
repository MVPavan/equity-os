-- D3 critical review fixes (plan D3, D4). 0001--0014 are immutable.
-- * An approval binds only a validation its decider computed in the deciding transaction, so a
--   runtime check never makes a version eligible; the owner may now write one.
-- * A validation's states close once a decision binds it.
-- * SUBMIT needs a terminal predecessor, as lifecycle.submit checks.

ALTER TABLE eqos.validations ADD COLUMN creator text;

CREATE OR REPLACE FUNCTION eqos.record_validation() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, eqos AS $$
BEGIN
    PERFORM eqos.lock_subject('REPORT_VERSION', NEW.version_id);
    IF NEW.sealed_digest IS DISTINCT FROM eqos.version_sealed_digest(NEW.version_id) THEN
        RAISE EXCEPTION 'validation digest does not match version %', NEW.version_id
            USING ERRCODE = '23514';
    END IF;
    NEW.creator := eqos.decider_role();
    NEW.recorded_at := eqos.store_now();
    NEW.created_xid := txid_current();
    RETURN NEW;
END $$;

CREATE OR REPLACE FUNCTION eqos.check_validation_state() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, eqos AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM eqos.validations
                   WHERE id = NEW.validation_id AND created_xid = txid_current()) THEN
        RAISE EXCEPTION 'validation states are sealed with the validation transaction'
            USING ERRCODE = '23514';
    END IF;
    IF EXISTS (SELECT 1 FROM eqos.decisions WHERE validation_id = NEW.validation_id) THEN
        RAISE EXCEPTION 'validation % is bound by a decision', NEW.validation_id
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;

-- Runs after check_decision has set the decider (trigger names sort).
CREATE FUNCTION eqos.check_version_trust() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, eqos AS $$
DECLARE
    bound   eqos.validations;
BEGIN
    IF NEW.kind = 'SUBMIT' THEN
        IF EXISTS (SELECT 1 FROM eqos.report_versions v
                   WHERE v.id = NEW.subject_id AND v.predecessor_id IS NOT NULL
                     AND coalesce((SELECT d.kind FROM eqos.decisions d
                                   WHERE d.subject_kind = 'REPORT_VERSION'
                                     AND d.subject_id = v.predecessor_id
                                   ORDER BY d.sequence DESC LIMIT 1), 'SUBMIT') = 'SUBMIT') THEN
            RAISE EXCEPTION 'version %: its predecessor is not terminal', NEW.subject_id
                USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
    END IF;
    SELECT * INTO bound FROM eqos.validations WHERE id = NEW.validation_id;
    IF bound.created_xid IS DISTINCT FROM txid_current()
       OR bound.creator IS DISTINCT FROM NEW.decider THEN
        RAISE EXCEPTION 'approval of % must bind a validation its decider wrote in this transaction',
            NEW.subject_id USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER check_version_trust BEFORE INSERT ON eqos.decisions FOR EACH ROW
    WHEN (NEW.subject_kind = 'REPORT_VERSION' AND NEW.kind IN ('SUBMIT', 'APPROVE'))
    EXECUTE FUNCTION eqos.check_version_trust();

GRANT INSERT ON eqos.validations, eqos.validation_claim_states TO eqos_owner;
GRANT USAGE ON SEQUENCE eqos.validations_id_seq, eqos.validation_claim_states_id_seq
    TO eqos_owner;
