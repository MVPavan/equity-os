-- PREP-5 Task 1. 0001--0038 are immutable.
-- A REQUEST_CHANGES on a version may name the claims it rejects: each a claim key of that
-- version, once. The keys are written in the decision's own INSERT, so they share its head
-- check, immutability, promote guard and grants.
ALTER TABLE eqos.decisions ADD COLUMN rejected_claims text[],
    ADD CHECK (rejected_claims IS NULL OR (subject_kind = 'REPORT_VERSION'
        AND kind = 'REQUEST_CHANGES' AND cardinality(rejected_claims) > 0));

CREATE FUNCTION eqos.check_rejected_claims() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, eqos AS $$
BEGIN
    IF NEW.rejected_claims IS NOT NULL AND (
        cardinality(NEW.rejected_claims)
            <> (SELECT count(DISTINCT key) FROM unnest(NEW.rejected_claims) key)
        OR EXISTS (SELECT 1 FROM unnest(NEW.rejected_claims) key WHERE NOT EXISTS (
            SELECT 1 FROM eqos.numeric_claims c
            WHERE c.version_id = NEW.subject_id AND c.claim_key = key))) THEN
        RAISE EXCEPTION 'rejected claims % are not distinct claims of version %',
            NEW.rejected_claims, NEW.subject_id USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER check_rejected_claims BEFORE INSERT ON eqos.decisions
    FOR EACH ROW EXECUTE FUNCTION eqos.check_rejected_claims();

-- A stored trace's operand set is closed: its writer records how many operands it stores, in
-- the trace's own transaction at ordinals 0..n-1, so every ordinal is taken. NULL (rows before
-- this migration) admits none. The 0029 mutation trigger keeps the count fixed.
ALTER TABLE eqos.calculation_traces ADD COLUMN operand_count integer CHECK (operand_count >= 0);

CREATE FUNCTION eqos.check_operand_ordinal() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, eqos AS $$
BEGIN
    IF NOT coalesce(NEW.ordinal >= 0 AND NEW.ordinal < (SELECT operand_count
            FROM eqos.calculation_traces WHERE id = NEW.calculation_trace_id), false) THEN
        RAISE EXCEPTION 'trace % has no operand slot %', NEW.calculation_trace_id, NEW.ordinal
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER check_operand_ordinal BEFORE INSERT ON eqos.calculation_trace_operands
    FOR EACH ROW EXECUTE FUNCTION eqos.check_operand_ordinal();
