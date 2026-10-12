-- Monotonic, server-owned store clock. 0001–0003 are applied and checksum-pinned, so the
-- change is a new migration.
--
-- The host clock can step backwards (observed: WSL2 shares a kernel clock that jumps back
-- by up to ~1 s), and now()/clock_timestamp() follow it. Every knowledge-time column and
-- every as-of read therefore takes its time from eqos.store_now():
--
-- * strictly increasing across transactions: max(clock_timestamp(), last issued + 1 µs);
-- * stable inside one transaction (like now()), so rows written together share one time;
-- * lock-free for writers: the high-water mark is a sequence (non-transactional), updated
--   under a session advisory lock released before the function returns, so no lock is held
--   until commit and concurrent writers never deadlock on the clock.
--
-- The runtime role gets EXECUTE on the function only; the function runs as its owner.

CREATE SEQUENCE eqos.store_clock_us AS bigint MINVALUE 0 START 0;
REVOKE ALL ON SEQUENCE eqos.store_clock_us FROM PUBLIC;
REVOKE ALL ON SEQUENCE eqos.store_clock_us FROM eqos_runtime;

CREATE FUNCTION eqos.store_now() RETURNS timestamptz
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    -- Arbitrary fixed key, distinct from the migration runner's.
    lock_key    constant bigint := 4215031004;
    issued      bigint := NULLIF(current_setting('eqos.store_now_us', true), '')::bigint;
    last_issued bigint;
BEGIN
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
    PERFORM set_config('eqos.store_now_us', issued::text, true);
    RETURN timestamptz 'epoch' + issued * interval '1 microsecond';
END;
$$;

REVOKE ALL ON FUNCTION eqos.store_now() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION eqos.store_now() TO eqos_runtime;

ALTER TABLE eqos.evidence_inputs ALTER COLUMN recorded_at SET DEFAULT eqos.store_now();
ALTER TABLE eqos.reporting_entities ALTER COLUMN created_at SET DEFAULT eqos.store_now();
ALTER TABLE eqos.entity_basis_status ALTER COLUMN recorded_at SET DEFAULT eqos.store_now();
ALTER TABLE eqos.settings_records ALTER COLUMN recorded_at SET DEFAULT eqos.store_now();
ALTER TABLE eqos.segment_members ALTER COLUMN recorded_at SET DEFAULT eqos.store_now();
ALTER TABLE eqos.acquisition_attempts ALTER COLUMN attempted_at SET DEFAULT eqos.store_now();
ALTER TABLE eqos.interpretations ALTER COLUMN recorded_at SET DEFAULT eqos.store_now();
ALTER TABLE eqos.definition_sets ALTER COLUMN published_at SET DEFAULT eqos.store_now();
ALTER TABLE eqos.runs ALTER COLUMN created_at SET DEFAULT eqos.store_now();
ALTER TABLE eqos.version_pins ALTER COLUMN pinned_at SET DEFAULT eqos.store_now();
