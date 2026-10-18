-- D7 screen export Task 4 (plan D7-screen-export S3, S4; amendment 2026-10-18-screen-export).
-- 0001--0033 are immutable. A screen run is now one vendor's automated export of a saved screen:
-- its vendor, provenance and definition capture (Screener page / Tijori listing) beside the
-- results capture. Runs before this migration are owner-exported Screener CSVs. Members keep the
-- row's ISIN and Tijori slug. A pair links the Screener and Tijori runs of one export.

ALTER TABLE eqos.screen_runs
    ADD COLUMN vendor text NOT NULL DEFAULT 'SCREENER' CHECK (vendor IN ('SCREENER', 'TIJORI')),
    ADD COLUMN provenance text NOT NULL DEFAULT 'OWNER_EXPORT'
        CHECK (provenance IN ('OWNER_EXPORT', 'AUTOMATED_EXPORT')),
    ADD COLUMN definition_capture_ref_id bigint REFERENCES eqos.capture_refs (id),
    ADD CHECK (provenance = 'OWNER_EXPORT' OR definition_capture_ref_id IS NOT NULL);
ALTER TABLE eqos.screen_runs ALTER COLUMN vendor DROP DEFAULT,
    ALTER COLUMN provenance DROP DEFAULT;

ALTER TABLE eqos.screen_members ADD COLUMN isin text, ADD COLUMN slug text;
ALTER TABLE eqos.screen_members DROP CONSTRAINT screen_members_reason_check;
ALTER TABLE eqos.screen_members ADD CHECK (reason IN ('UNKNOWN_NSE_CODE', 'UNKNOWN_BSE_CODE',
    'CONFLICTING_CODES', 'AMBIGUOUS_CODE', 'NO_CODE', 'UNKNOWN_ISIN'));

CREATE TABLE eqos.screen_run_pairs (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    screener_run_id     bigint NOT NULL UNIQUE REFERENCES eqos.screen_runs (id),
    tijori_run_id       bigint NOT NULL UNIQUE REFERENCES eqos.screen_runs (id),
    run_by              text NOT NULL DEFAULT current_user,
    recorded_at         timestamptz NOT NULL DEFAULT eqos.store_now()
);

CREATE FUNCTION eqos.check_screen_run_pair() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM eqos.screen_runs WHERE id = NEW.screener_run_id
                   AND vendor = 'SCREENER' AND provenance = 'AUTOMATED_EXPORT')
       OR NOT EXISTS (SELECT 1 FROM eqos.screen_runs WHERE id = NEW.tijori_run_id
                      AND vendor = 'TIJORI' AND provenance = 'AUTOMATED_EXPORT') THEN
        RAISE EXCEPTION 'a pair links one automated Screener run and one automated Tijori run'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER check_screen_run_pair BEFORE INSERT ON eqos.screen_run_pairs
    FOR EACH ROW EXECUTE FUNCTION eqos.check_screen_run_pair();
CREATE TRIGGER reject_row_mutation BEFORE UPDATE OR DELETE ON eqos.screen_run_pairs
    FOR EACH ROW EXECUTE FUNCTION eqos.reject_mutation();
CREATE TRIGGER reject_truncate BEFORE TRUNCATE ON eqos.screen_run_pairs
    FOR EACH STATEMENT EXECUTE FUNCTION eqos.reject_mutation();
GRANT SELECT ON eqos.screen_run_pairs TO eqos_runtime, eqos_panel, eqos_owner, eqos_purge;
GRANT INSERT ON eqos.screen_run_pairs TO eqos_owner;
GRANT USAGE ON SEQUENCE eqos.screen_run_pairs_id_seq TO eqos_owner;
