-- eqos-ya8. 0001--0048 are immutable. A paired run is sealed: its members are what the pair's
-- review items, dispositions and holds were computed over, so no member is appended after the
-- pair. A run and its pair are recorded in one transaction, members first.
CREATE FUNCTION eqos.check_screen_member_unpaired() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM eqos.screen_run_pairs
               WHERE NEW.screen_run_id IN (screener_run_id, tijori_run_id)) THEN
        RAISE EXCEPTION 'screen run % is paired and sealed', NEW.screen_run_id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER check_screen_member_unpaired BEFORE INSERT ON eqos.screen_members
    FOR EACH ROW EXECUTE FUNCTION eqos.check_screen_member_unpaired();
