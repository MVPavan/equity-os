-- VENDOR-1 Phase 2 Task 4 (eqos-awnc). 0001--0049 are immutable. A version's source cutoff S:
-- vendor captures registered after S are not citable by it. Written only in the version's creating
-- transaction, never later than its knowledge cutoff, and never changed.
CREATE TABLE eqos.version_source_cutoffs (
    version_id bigint PRIMARY KEY REFERENCES eqos.report_versions (id),
    source_cutoff timestamptz NOT NULL
);

CREATE FUNCTION eqos.check_version_source_cutoff() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, eqos AS $$
BEGIN
    PERFORM eqos.lock_subject('REPORT_VERSION', NEW.version_id);
    IF NOT EXISTS (SELECT 1 FROM eqos.report_versions
                   WHERE id = NEW.version_id AND created_xid = txid_current()
                     AND NEW.source_cutoff <= knowledge_cutoff) THEN
        RAISE EXCEPTION 'source cutoff must be set with version % and not after its knowledge cutoff',
            NEW.version_id USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER a_check_version_source_cutoff BEFORE INSERT ON eqos.version_source_cutoffs
    FOR EACH ROW EXECUTE FUNCTION eqos.check_version_source_cutoff();
CREATE TRIGGER check_version_seal BEFORE INSERT ON eqos.version_source_cutoffs
    FOR EACH ROW EXECUTE FUNCTION eqos.check_version_seal();
CREATE TRIGGER reject_row_mutation BEFORE UPDATE OR DELETE ON eqos.version_source_cutoffs
    FOR EACH ROW EXECUTE FUNCTION eqos.reject_mutation();
CREATE TRIGGER reject_truncate BEFORE TRUNCATE ON eqos.version_source_cutoffs
    FOR EACH STATEMENT EXECUTE FUNCTION eqos.reject_mutation();

GRANT SELECT, INSERT ON eqos.version_source_cutoffs TO eqos_runtime, eqos_panel;
GRANT SELECT ON eqos.version_source_cutoffs TO eqos_owner, eqos_purge;
