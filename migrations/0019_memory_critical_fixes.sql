-- D4 critical review fixes (ledger spec §2, amendment A1; plan D4, M2, M3). 0001--0018 are
-- immutable.

-- M3 at staging: every support insert schedules its own predicate check, so a support added
-- after the item's check has run (SET CONSTRAINTS ALL IMMEDIATE) is checked too.
CREATE OR REPLACE FUNCTION eqos.check_memory_supports_hold() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, eqos AS $$
DECLARE
    item    bigint;
BEGIN
    IF TG_TABLE_NAME = 'memory_items' THEN
        item := NEW.id;
    ELSIF TG_TABLE_NAME = 'memory_supports' THEN
        item := NEW.item_id;
    ELSE
        item := NEW.subject_id;
    END IF;
    IF NOT eqos.memory_item_supported(item, NULL) THEN
        RAISE EXCEPTION 'memory item % fails its support predicate', item USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;

CREATE CONSTRAINT TRIGGER check_memory_supports_hold AFTER INSERT ON eqos.memory_supports
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION eqos.check_memory_supports_hold();

-- 0016's sealing check, and no support target recorded after its item: an item known at a
-- cutoff rests only on targets known by then (M3). A claim takes its version's time.
CREATE OR REPLACE FUNCTION eqos.check_memory_support() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, eqos AS $$
DECLARE
    known   timestamptz;
BEGIN
    SELECT recorded_at INTO known FROM eqos.memory_items
        WHERE id = NEW.item_id AND created_xid = txid_current();
    IF NOT FOUND THEN
        RAISE EXCEPTION 'memory supports are sealed with the item transaction'
            USING ERRCODE = '23514';
    END IF;
    IF coalesce(
        (SELECT v.created_at FROM eqos.numeric_claims c
         JOIN eqos.report_versions v ON v.id = c.version_id WHERE c.id = NEW.claim_id),
        (SELECT created_at FROM eqos.report_versions WHERE id = NEW.version_id),
        (SELECT s.published_at FROM eqos.definition_records r
         JOIN eqos.definition_sets s ON s.id = r.definition_set_id
         WHERE r.id = NEW.definition_record_id),
        (SELECT recorded_at FROM eqos.queue_dispositions WHERE id = NEW.disposition_id),
        (SELECT recorded_at FROM eqos.decisions WHERE id = NEW.decision_id),
        (SELECT registered_at FROM eqos.capture_refs WHERE id = NEW.capture_ref_id)) > known THEN
        RAISE EXCEPTION 'memory item % predates its support target', NEW.item_id
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;

-- M2: every memory decision reads current state (successor, chain head), so each runs at READ
-- COMMITTED; a stale REPEATABLE READ snapshot could RETIRE an already retired item. The a_
-- prefix sorts before check_memory_decision.
CREATE FUNCTION eqos.memory_decision_read_committed() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, eqos AS $$ BEGIN
    IF current_setting('transaction_isolation') <> 'read committed' THEN
        RAISE EXCEPTION '% runs at READ COMMITTED only', NEW.kind USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER a_memory_read_committed BEFORE INSERT ON eqos.decisions FOR EACH ROW
    WHEN (NEW.subject_kind = 'MEMORY_ITEM')
    EXECUTE FUNCTION eqos.memory_decision_read_committed();
