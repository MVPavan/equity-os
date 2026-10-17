-- D9 Task 6: re-fetch, RESTORED admission and expired vendor inputs (plan
-- docs/workstreams/data-foundation/plans/D9.md R9, R10, R13). 0001--0029 are immutable.
-- Re-fetch attempts are append-only; a mismatch is a HIGH incident.

-- R10: every re-fetch of an expired capture, recorded before any store write.
CREATE TABLE eqos.refetch_attempts (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    capture_ref_id  bigint NOT NULL REFERENCES eqos.capture_refs (id),
    url             text NOT NULL,
    outcome         text NOT NULL CHECK (outcome IN ('MATCH', 'MISMATCH', 'FAILED')),
    category        text CHECK (category IN ('INCOMPLETE', 'HTTP_STATUS', 'TIMEOUT', 'CONNECTION')),
    http_status     integer,
    fetched_sha256  text,
    severity        text CHECK (severity = 'HIGH'),
    recorded_at     timestamptz NOT NULL DEFAULT eqos.store_now(),
    CHECK ((outcome = 'MISMATCH') = (severity IS NOT NULL)),
    CHECK ((outcome = 'FAILED') = (category IS NOT NULL)),
    CHECK ((outcome = 'FAILED') = (fetched_sha256 IS NULL))
);
CREATE TRIGGER reject_row_mutation BEFORE UPDATE OR DELETE ON eqos.refetch_attempts
    FOR EACH ROW EXECUTE FUNCTION eqos.reject_mutation();
CREATE TRIGGER reject_truncate BEFORE TRUNCATE ON eqos.refetch_attempts
    FOR EACH STATEMENT EXECUTE FUNCTION eqos.reject_mutation();
GRANT SELECT ON eqos.refetch_attempts TO eqos_runtime, eqos_panel, eqos_owner, eqos_purge;
GRANT INSERT ON eqos.refetch_attempts TO eqos_runtime;

-- R10: RESTORED only for an expired capture of a non-vendor-bounded source whose bytes a
-- MATCH attempt fetched, whoever inserts it.
CREATE FUNCTION eqos.admit_restored() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF eqos.capture_state(NEW.capture_ref_id) <> 'EXPIRED' OR NOT EXISTS (
        SELECT 1 FROM eqos.capture_refs r JOIN eqos.refetch_attempts a ON a.capture_ref_id = r.id
        WHERE r.id = NEW.capture_ref_id AND NOT eqos.is_vendor_source(r.source_id)
          AND a.outcome = 'MATCH' AND a.fetched_sha256 = r.blob_sha256) THEN
        RAISE EXCEPTION 'NOT_REFETCHABLE: capture % has no matching re-fetch to restore',
            NEW.capture_ref_id USING ERRCODE = '55000';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER admit_restored BEFORE INSERT ON eqos.capture_states
    FOR EACH ROW WHEN (NEW.state = 'RESTORED') EXECUTE FUNCTION eqos.admit_restored();

-- The runtime role restores through this alone; it never inserts other states.
CREATE FUNCTION eqos.restore_capture(capture bigint) RETURNS void LANGUAGE sql
SECURITY DEFINER SET search_path = pg_catalog, eqos AS $$
    INSERT INTO eqos.capture_states (capture_ref_id, state) VALUES (capture, 'RESTORED')
$$;
REVOKE ALL ON FUNCTION eqos.restore_capture(bigint) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION eqos.restore_capture(bigint) TO eqos_runtime;

-- R13: the vendor captures among a run's inputs that are not retained.
CREATE FUNCTION eqos.expired_vendor_captures(captures bigint[]) RETURNS bigint[]
LANGUAGE sql STABLE AS $$
    SELECT coalesce(array_agg(id ORDER BY id), '{}') FROM eqos.capture_refs
    WHERE id = ANY (captures) AND eqos.is_vendor_source(source_id)
      AND eqos.capture_state(id) NOT IN ('RETAINED', 'RESTORED')
$$;

-- R9: a mismatch incident closes when its capture is later RESTORED.
CREATE OR REPLACE VIEW eqos.retention_incidents AS
    SELECT 'PROBE' AS kind, p.id, p.source_id, p.capture_ref_id, p.outcome, p.recorded_at
    FROM eqos.retention_probes p
    WHERE p.severity = 'HIGH' AND NOT EXISTS (
        SELECT 1 FROM eqos.retention_probes m
        WHERE m.source_id = p.source_id AND m.outcome = 'MATCH' AND m.id > p.id)
    UNION ALL
    SELECT 'REFETCH', a.id, r.source_id, a.capture_ref_id, a.outcome, a.recorded_at
    FROM eqos.refetch_attempts a JOIN eqos.capture_refs r ON r.id = a.capture_ref_id
    WHERE a.severity = 'HIGH' AND NOT EXISTS (
        SELECT 1 FROM eqos.capture_states s
        WHERE s.capture_ref_id = a.capture_ref_id AND s.state = 'RESTORED'
          AND s.recorded_at > a.recorded_at);
