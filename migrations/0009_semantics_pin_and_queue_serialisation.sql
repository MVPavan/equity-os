-- D1b review C2: a run records the engine's comparison semantics as a run_versions pin.
ALTER TABLE eqos.run_versions DROP CONSTRAINT run_versions_pin_check;
ALTER TABLE eqos.run_versions ADD CHECK (pin IN (
    'dictionary','formula_set','mapping_set','normalisation_policy','extractor_xbrl','extractor_pdf',
    'rounding_policy','definition_set','comparison_policy','alignment_rules','vendor_extractor',
    'comparison_semantics'));

-- D1b review C5: queue writes serialize at the database boundary, not only in Python. A
-- transaction may take the queue lock only before its first store-clock read (the clock
-- caches its time per transaction), so a queue time is always issued under the lock and an
-- overlay boundary never moves. The marker records that this transaction took it that way;
-- only the function's owner can write it.
CREATE TABLE eqos_clock.queue_locks (
    backend_pid integer PRIMARY KEY,
    xact_id     xid8    NOT NULL
);
REVOKE ALL ON eqos_clock.queue_locks FROM PUBLIC;

CREATE FUNCTION eqos.lock_queue() RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    xact xid8 := pg_current_xact_id();
BEGIN
    IF EXISTS (SELECT 1 FROM eqos_clock.queue_locks
               WHERE backend_pid = pg_backend_pid() AND xact_id = xact) THEN
        RETURN;
    END IF;
    IF EXISTS (SELECT 1 FROM eqos_clock.transaction_times
               WHERE backend_pid = pg_backend_pid() AND xact_id = xact) THEN
        RAISE EXCEPTION 'the queue lock must precede the transaction''s first store-clock read'
            USING ERRCODE = '55000';
    END IF;
    PERFORM pg_advisory_xact_lock(349322958149);
    INSERT INTO eqos_clock.queue_locks (backend_pid, xact_id) VALUES (pg_backend_pid(), xact)
        ON CONFLICT (backend_pid) DO UPDATE SET xact_id = EXCLUDED.xact_id;
END;
$$;
REVOKE ALL ON FUNCTION eqos.lock_queue() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION eqos.lock_queue() TO eqos_runtime;

CREATE OR REPLACE FUNCTION eqos.record_queue_time() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog,eqos AS $$
BEGIN
    PERFORM eqos.lock_queue();
    NEW.recorded_at := eqos.store_now();
    IF TG_TABLE_NAME='queue_items' THEN NEW.created_xid := txid_current(); END IF;
    RETURN NEW;
END $$;
