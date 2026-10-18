-- D9 phase-end fixes (plan docs/workstreams/data-foundation/plans/D9.md RP1, RP2, R10).
-- 0001--0030 are immutable.

-- RP1, RP2: restoration takes the retention lock shared and refuses while a purge is unfinished
-- or after a purge the caller's snapshot predates, before the RESTORED admission trigger runs.
CREATE OR REPLACE FUNCTION eqos.restore_capture(capture bigint) RETURNS void LANGUAGE plpgsql
SECURITY DEFINER SET search_path = pg_catalog, eqos AS $$
BEGIN
    PERFORM eqos.retention_shared();
    INSERT INTO eqos.capture_states (capture_ref_id, state) VALUES (capture, 'RESTORED');
END $$;

-- R10: an address outside the approved exchange hosts is refused before any request.
ALTER TABLE eqos.refetch_attempts DROP CONSTRAINT refetch_attempts_category_check,
    ADD CONSTRAINT refetch_attempts_category_check CHECK (category IN
        ('INCOMPLETE', 'HTTP_STATUS', 'TIMEOUT', 'CONNECTION', 'REFUSED_ADDRESS'));
ALTER TABLE eqos.retention_probes DROP CONSTRAINT retention_probes_category_check,
    ADD CONSTRAINT retention_probes_category_check CHECK (category IN
        ('INCOMPLETE', 'HTTP_STATUS', 'TIMEOUT', 'CONNECTION', 'REFUSED_ADDRESS'));

-- R8 cancellation of a restored capture's intent returns it to RESTORED: admitted when the
-- intent's PURGE_PENDING follows a RESTORED state; otherwise the re-fetch admission of 0030.
CREATE OR REPLACE FUNCTION eqos.admit_restored() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF (SELECT array_agg(state ORDER BY id DESC) FROM (SELECT id, state FROM eqos.capture_states
        WHERE capture_ref_id = NEW.capture_ref_id ORDER BY id DESC LIMIT 2) latest)
       = ARRAY['PURGE_PENDING', 'RESTORED'] THEN
        RETURN NEW;
    END IF;
    IF eqos.capture_state(NEW.capture_ref_id) <> 'EXPIRED' OR NOT EXISTS (
        SELECT 1 FROM eqos.capture_refs r JOIN eqos.refetch_attempts a ON a.capture_ref_id = r.id
        WHERE r.id = NEW.capture_ref_id AND NOT eqos.is_vendor_source(r.source_id)
          AND a.outcome = 'MATCH' AND a.fetched_sha256 = r.blob_sha256) THEN
        RAISE EXCEPTION 'NOT_REFETCHABLE: capture % has no matching re-fetch to restore',
            NEW.capture_ref_id USING ERRCODE = '55000';
    END IF;
    RETURN NEW;
END $$;
