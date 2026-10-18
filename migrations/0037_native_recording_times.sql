-- PREP-2/2b phase review r2 #2: a native fact row's ``created_at`` and every selection's
-- ``recorded_at`` come from the store clock, whatever the INSERT supplies. The one exception is
-- the legacy import's own rows (origin = its ``sqlite-`` LEGACY_SQLITE store), which keep their
-- legacy times. Readers exempt the same rows (eqos.legacy_time_exempt). 0001--0036 are
-- immutable.
CREATE FUNCTION eqos.legacy_time_exempt(store text, origin text) RETURNS boolean
LANGUAGE sql STABLE SET search_path = pg_catalog, eqos AS $$
    SELECT origin = store AND origin LIKE 'sqlite-%'
        AND EXISTS (SELECT 1 FROM eqos.fact_stores WHERE store_id = store AND kind = 'LEGACY_SQLITE')
$$;

CREATE FUNCTION eqos.stamp_native_recording() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, eqos AS $$ BEGIN
    IF eqos.legacy_time_exempt(NEW.target_store, NEW.origin) THEN
        NULL;
    ELSIF TG_TABLE_NAME = 'fact_rows' THEN
        NEW.created_at := to_char(eqos.store_now() AT TIME ZONE 'UTC',
            'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"');
    ELSE
        NEW.recorded_at := eqos.store_now();
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER stamp_native_recording BEFORE INSERT ON eqos.fact_rows
    FOR EACH ROW EXECUTE FUNCTION eqos.stamp_native_recording();
CREATE TRIGGER stamp_native_recording BEFORE INSERT ON eqos.fact_selections
    FOR EACH ROW EXECUTE FUNCTION eqos.stamp_native_recording();
