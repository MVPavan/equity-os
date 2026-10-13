-- The store clock's per-transaction cache moves to server-owned state. 0001–0004 are applied
-- and checksum-pinned, so the change is a new migration.
--
-- 0004 cached a transaction's issued time in the custom setting eqos.store_now_us. Any
-- session may set a custom setting, so the runtime role could SET LOCAL it and move or freeze
-- the clock for its own writes. The cache now lives in a table only the function's owner can
-- read or write: one row per backend, valid only for the top-level transaction that wrote it
-- (pg_current_xact_id() is never reused). A row from an earlier transaction, or from an
-- earlier backend that held the same pid, never matches, so the next call issues a new time.
--
-- The cache is working state, not evidence, so it lives outside the eqos schema and is
-- updated in place. The runtime role gets no privilege on the schema or the table.

CREATE SCHEMA eqos_clock;
REVOKE ALL ON SCHEMA eqos_clock FROM PUBLIC;

CREATE TABLE eqos_clock.transaction_times (
    backend_pid integer PRIMARY KEY,
    xact_id     xid8    NOT NULL,
    issued_us   bigint  NOT NULL
);
REVOKE ALL ON eqos_clock.transaction_times FROM PUBLIC;

CREATE OR REPLACE FUNCTION eqos.store_now() RETURNS timestamptz
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    -- Arbitrary fixed key, distinct from the migration runner's.
    lock_key    constant bigint := 4215031004;
    xact        xid8 := pg_current_xact_id();
    issued      bigint;
    last_issued bigint;
BEGIN
    SELECT issued_us INTO issued FROM eqos_clock.transaction_times
        WHERE backend_pid = pg_backend_pid() AND xact_id = xact;
    IF issued IS NOT NULL THEN
        RETURN timestamptz 'epoch' + issued * interval '1 microsecond';
    END IF;
    PERFORM pg_advisory_lock(lock_key);
    BEGIN
        SELECT CASE WHEN is_called THEN last_value ELSE 0 END INTO last_issued
            FROM eqos.store_clock_us;
        issued := GREATEST(
            floor(extract(epoch FROM clock_timestamp()) * 1000000)::bigint, last_issued + 1);
        PERFORM setval('eqos.store_clock_us', issued, true);
    EXCEPTION WHEN query_canceled OR OTHERS THEN
        PERFORM pg_advisory_unlock(lock_key);
        RAISE;
    END;
    PERFORM pg_advisory_unlock(lock_key);
    INSERT INTO eqos_clock.transaction_times (backend_pid, xact_id, issued_us)
        VALUES (pg_backend_pid(), xact, issued)
        ON CONFLICT (backend_pid) DO UPDATE
            SET xact_id = EXCLUDED.xact_id, issued_us = EXCLUDED.issued_us;
    RETURN timestamptz 'epoch' + issued * interval '1 microsecond';
END;
$$;

REVOKE ALL ON FUNCTION eqos.store_now() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION eqos.store_now() TO eqos_runtime;

-- An interpretation without a key keeps the dimension set only when its evidence establishes
-- one (an INVALID unit on a mapped, dimensioned fact); NULL means not established, never the
-- empty set. A keyed row always has its key's dimension set. Rows stored before this
-- migration carry the empty set whether established or not.
ALTER TABLE eqos.interpretations ALTER COLUMN dimension_set DROP NOT NULL;
ALTER TABLE eqos.interpretations ALTER COLUMN dimension_hash DROP NOT NULL;
ALTER TABLE eqos.interpretations ADD CONSTRAINT interpretations_dimensions_check CHECK (
    (dimension_set IS NULL) = (dimension_hash IS NULL)
    AND (key_digest IS NULL OR dimension_set IS NOT NULL));

-- Capture-only extraction may be reused, but mapping/layout-dependent decisions have distinct
-- identities. NULL retains the identity of old capture-only and acquisition attempts.
ALTER TABLE eqos.acquisition_attempts ADD COLUMN extraction_context_sha256 text
    CHECK (extraction_context_sha256 IS NULL
        OR extraction_context_sha256 ~ '^[0-9a-f]{64}$');
DO $$
DECLARE
    original_unique text;
BEGIN
    SELECT conname INTO STRICT original_unique FROM pg_constraint
        WHERE conrelid = 'eqos.acquisition_attempts'::regclass AND contype = 'u';
    EXECUTE format('ALTER TABLE eqos.acquisition_attempts DROP CONSTRAINT %I', original_unique);
END;
$$;
ALTER TABLE eqos.acquisition_attempts ADD CONSTRAINT acquisition_attempts_identity_key
    UNIQUE NULLS NOT DISTINCT (
        stage, source_id, surface, entity_id, period_end, basis, framework, representation,
        statement_family, package_id, capture_ref_id, input_sha256, extractor_version, outcome,
        extraction_context_sha256);
