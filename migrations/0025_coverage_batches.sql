-- D7 Task 2: screens, screen runs and capture batches (plan D7 R1-R3). 0001--0024 are immutable.
-- A screen is stored once by its text's hash; a screen run is one owner-exported CSV (a
-- SCREEN_EXPORT capture) with its members resolved against the registry's current attributes.
-- A capture batch declares the chosen member ids once; each member gets one terminal result
-- pinning its onboarding record and, when admitted, the same-entity comparison run it consumed.
-- A completion is appended only when every declared member has a result. Append-only; INSERT to
-- the owner role only, SELECT to all three.

CREATE TABLE eqos.screens (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    text_sha256         text NOT NULL UNIQUE,
    screen_text         text NOT NULL,
    CHECK (text_sha256 = encode(sha256(convert_to(screen_text, 'UTF8')), 'hex'))
);

CREATE TABLE eqos.screen_runs (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    screen_id           bigint NOT NULL REFERENCES eqos.screens (id),
    capture_ref_id      bigint NOT NULL REFERENCES eqos.capture_refs (id),
    run_by              text NOT NULL DEFAULT current_user,
    recorded_at         timestamptz NOT NULL DEFAULT eqos.store_now()
);

CREATE TABLE eqos.screen_members (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    screen_run_id       bigint NOT NULL REFERENCES eqos.screen_runs (id),
    row_number          integer NOT NULL,
    name                text NOT NULL,
    nse_code            text,
    bse_code            text,
    listing_id          bigint REFERENCES eqos.registry_listings (id),
    reason              text CHECK (reason IN ('UNKNOWN_NSE_CODE', 'UNKNOWN_BSE_CODE',
        'CONFLICTING_CODES', 'AMBIGUOUS_CODE', 'NO_CODE')),
    CHECK ((listing_id IS NULL) <> (reason IS NULL)),
    UNIQUE (screen_run_id, row_number)
);

CREATE TABLE eqos.capture_batches (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    screen_run_id       bigint NOT NULL REFERENCES eqos.screen_runs (id),
    member_ids          bigint[] NOT NULL CHECK (cardinality(member_ids) > 0),
    run_by              text NOT NULL DEFAULT current_user,
    recorded_at         timestamptz NOT NULL DEFAULT eqos.store_now()
);

CREATE TABLE eqos.batch_member_results (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    batch_id            bigint NOT NULL REFERENCES eqos.capture_batches (id),
    member_id           bigint NOT NULL REFERENCES eqos.screen_members (id),
    outcome             text NOT NULL CHECK (outcome IN (
        'ONBOARDED', 'PARTIAL', 'UNSUPPORTED', 'IDENTITY_CONFLICT')),
    entity_id           bigint REFERENCES eqos.reporting_entities (id),
    onboarding_record_id bigint NOT NULL REFERENCES eqos.onboarding_records (id),
    run_id              bigint REFERENCES eqos.runs (id),
    exit_code           integer NOT NULL,
    run_by              text NOT NULL DEFAULT current_user,
    recorded_at         timestamptz NOT NULL DEFAULT eqos.store_now(),
    CHECK ((outcome IN ('ONBOARDED', 'PARTIAL')) = (entity_id IS NOT NULL)),
    CHECK ((entity_id IS NULL) = (run_id IS NULL)),
    UNIQUE (batch_id, member_id)
);

CREATE TABLE eqos.batch_completions (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    batch_id            bigint NOT NULL UNIQUE REFERENCES eqos.capture_batches (id),
    run_by              text NOT NULL DEFAULT current_user,
    recorded_at         timestamptz NOT NULL DEFAULT eqos.store_now()
);

-- Declared members are resolved members of the batch's own screen run, each with an NSE listing.
CREATE FUNCTION eqos.check_batch_members() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF cardinality(NEW.member_ids) <> (
        SELECT count(*) FROM eqos.screen_members m
        JOIN eqos.registry_listings l ON l.id = m.listing_id
        WHERE m.id = ANY (NEW.member_ids) AND m.screen_run_id = NEW.screen_run_id
          AND l.segment = 'NSE_EQ') THEN
        RAISE EXCEPTION 'batch members must be distinct resolved NSE members of screen run %',
            NEW.screen_run_id USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;

-- A result is for a declared member; its onboarding record carries the same outcome and entity;
-- an admitted result's run is that entity's, and the entity's verified ISIN is the listing's.
CREATE FUNCTION eqos.check_batch_result() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM eqos.capture_batches b
                   WHERE b.id = NEW.batch_id AND NEW.member_id = ANY (b.member_ids)) THEN
        RAISE EXCEPTION 'member % is not declared in batch %', NEW.member_id, NEW.batch_id
            USING ERRCODE = 'check_violation';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM eqos.onboarding_records r
                   WHERE r.id = NEW.onboarding_record_id AND r.outcome = NEW.outcome
                     AND r.entity_id IS NOT DISTINCT FROM NEW.entity_id) THEN
        RAISE EXCEPTION 'onboarding record % does not match the result',
            NEW.onboarding_record_id USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.run_id IS NOT NULL AND NOT (
        EXISTS (SELECT 1 FROM eqos.runs r WHERE r.id = NEW.run_id
                AND r.manifest -> 'scope' -> 'entity_ids' = jsonb_build_array(NEW.entity_id))
        AND EXISTS (SELECT 1 FROM eqos.screen_members m
                    JOIN eqos.registry_listings l ON l.id = m.listing_id
                    JOIN eqos.securities s ON s.isin = l.isin
                    WHERE m.id = NEW.member_id AND s.entity_id = NEW.entity_id)) THEN
        RAISE EXCEPTION 'run % or the listing''s ISIN is not entity %''s', NEW.run_id,
            NEW.entity_id USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE FUNCTION eqos.check_batch_completion() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM eqos.capture_batches b, unnest(b.member_ids) AS member (id)
               WHERE b.id = NEW.batch_id AND NOT EXISTS (
                   SELECT 1 FROM eqos.batch_member_results r
                   WHERE r.batch_id = b.id AND r.member_id = member.id)) THEN
        RAISE EXCEPTION 'batch % has a declared member without a result', NEW.batch_id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER check_batch_members BEFORE INSERT ON eqos.capture_batches
    FOR EACH ROW EXECUTE FUNCTION eqos.check_batch_members();
CREATE TRIGGER check_batch_result BEFORE INSERT ON eqos.batch_member_results
    FOR EACH ROW EXECUTE FUNCTION eqos.check_batch_result();
CREATE TRIGGER check_batch_completion BEFORE INSERT ON eqos.batch_completions
    FOR EACH ROW EXECUTE FUNCTION eqos.check_batch_completion();

DO $$
DECLARE
    table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY['screens', 'screen_runs', 'screen_members',
        'capture_batches', 'batch_member_results', 'batch_completions'] LOOP
        EXECUTE format('CREATE TRIGGER reject_row_mutation BEFORE UPDATE OR DELETE ON eqos.%I '
            'FOR EACH ROW EXECUTE FUNCTION eqos.reject_mutation()', table_name);
        EXECUTE format('CREATE TRIGGER reject_truncate BEFORE TRUNCATE ON eqos.%I '
            'FOR EACH STATEMENT EXECUTE FUNCTION eqos.reject_mutation()', table_name);
        EXECUTE format('GRANT SELECT ON eqos.%I TO eqos_runtime, eqos_panel, eqos_owner', table_name);
        EXECUTE format('GRANT INSERT ON eqos.%I TO eqos_owner', table_name);
        EXECUTE format('GRANT USAGE ON SEQUENCE eqos.%I TO eqos_owner', table_name || '_id_seq');
    END LOOP;
END;
$$;
