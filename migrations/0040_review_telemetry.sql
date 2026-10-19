-- PREP-6 Task 1. 0001--0039 are immutable.
-- The owner's review of a version: one session per owner review decision on that version, and
-- every claim event of the session. Written by the owner in the decision's own transaction.
-- started_at, finished_at and the durations are client measurements; recorded_at is the store's.
CREATE TABLE eqos.review_sessions (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    version_id          bigint NOT NULL REFERENCES eqos.report_versions (id),
    decision_id         bigint NOT NULL UNIQUE REFERENCES eqos.decisions (id),
    instrument_version  text NOT NULL CHECK (instrument_version <> ''),
    started_at          timestamptz NOT NULL,
    finished_at         timestamptz NOT NULL,
    command_handling_ms bigint NOT NULL CHECK (command_handling_ms >= 0),
    recorded_at         timestamptz NOT NULL,
    CHECK (finished_at >= started_at)
);

CREATE TABLE eqos.claim_reviews (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id      bigint NOT NULL REFERENCES eqos.review_sessions (id),
    ordinal         integer NOT NULL CHECK (ordinal >= 0),
    claim_key       text NOT NULL,
    disposition     text NOT NULL CHECK (disposition IN ('accepted', 'edited', 'rejected',
                        'deferred')),
    category        text NOT NULL CHECK (category IN ('none', 'wrong_value', 'wrong_source',
                        'missing_context', 'calculation', 'wording', 'other')),
    elapsed_ms      bigint NOT NULL CHECK (elapsed_ms >= 0),
    locate_seconds  integer NOT NULL CHECK (locate_seconds >= 0),
    check_seconds   integer NOT NULL CHECK (check_seconds >= 0),
    note            text,
    UNIQUE (session_id, ordinal),
    CONSTRAINT category_rule
        CHECK (disposition = 'deferred' OR (disposition = 'accepted') = (category = 'none'))
);

-- A session binds an owner review decision on its version; a claim review names a claim of its
-- session's version.
CREATE FUNCTION eqos.check_review_telemetry() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, eqos AS $$
BEGIN
    IF TG_TABLE_NAME = 'review_sessions' THEN
        IF NOT EXISTS (SELECT 1 FROM eqos.decisions d WHERE d.id = NEW.decision_id
                AND d.subject_kind = 'REPORT_VERSION' AND d.subject_id = NEW.version_id
                AND d.decider = 'OWNER' AND d.kind IN ('APPROVE', 'REQUEST_CHANGES', 'REJECT'))
        THEN
            RAISE EXCEPTION 'decision % is not an owner review decision on version %',
                NEW.decision_id, NEW.version_id USING ERRCODE = '23514';
        END IF;
        NEW.recorded_at := eqos.store_now();
    ELSIF NOT EXISTS (SELECT 1 FROM eqos.review_sessions s JOIN eqos.numeric_claims c
            ON c.version_id = s.version_id
            WHERE s.id = NEW.session_id AND c.claim_key = NEW.claim_key) THEN
        RAISE EXCEPTION 'claim % is not a claim of session %''s version', NEW.claim_key,
            NEW.session_id USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;

DO $$
DECLARE
    name text;
BEGIN
    FOREACH name IN ARRAY ARRAY['review_sessions', 'claim_reviews'] LOOP
        EXECUTE format('CREATE TRIGGER check_review_telemetry BEFORE INSERT ON eqos.%I '
            'FOR EACH ROW EXECUTE FUNCTION eqos.check_review_telemetry()', name);
        EXECUTE format('CREATE TRIGGER refuse_after_promote BEFORE INSERT ON eqos.%I '
            'FOR EACH ROW EXECUTE FUNCTION eqos.refuse_after_promote()', name);
        EXECUTE format('CREATE TRIGGER reject_row_mutation BEFORE UPDATE OR DELETE ON eqos.%I '
            'FOR EACH ROW EXECUTE FUNCTION eqos.reject_mutation()', name);
        EXECUTE format('CREATE TRIGGER reject_truncate BEFORE TRUNCATE ON eqos.%I '
            'FOR EACH STATEMENT EXECUTE FUNCTION eqos.reject_mutation()', name);
        EXECUTE format('GRANT INSERT ON eqos.%I TO eqos_owner', name);
        EXECUTE format('GRANT USAGE ON SEQUENCE eqos.%I TO eqos_owner', name || '_id_seq');
    END LOOP;
END $$;
GRANT SELECT ON eqos.review_sessions, eqos.claim_reviews
    TO eqos_runtime, eqos_panel, eqos_owner, eqos_purge;
