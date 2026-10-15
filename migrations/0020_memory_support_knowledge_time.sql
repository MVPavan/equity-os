-- D4 critical review r2 (ledger spec §2, amendment A1; plan D4, M3). 0001--0019 are immutable.

-- 0016's sealing check, and no support target known after its item. A claim or version is known
-- from its version's first SUBMIT or IMPORT_SEAL (content is sealed then, 0012); an unsealed
-- version is refused. A capture is known from the later of registration and first sight, as the
-- evidence layer selects it.
CREATE OR REPLACE FUNCTION eqos.check_memory_support() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, eqos AS $$
DECLARE
    known   timestamptz;
    version bigint := coalesce(NEW.version_id,
        (SELECT version_id FROM eqos.numeric_claims WHERE id = NEW.claim_id));
    target  timestamptz;
BEGIN
    SELECT recorded_at INTO known FROM eqos.memory_items
        WHERE id = NEW.item_id AND created_xid = txid_current();
    IF NOT FOUND THEN
        RAISE EXCEPTION 'memory supports are sealed with the item transaction'
            USING ERRCODE = '23514';
    END IF;
    IF version IS NOT NULL THEN
        SELECT min(recorded_at) INTO target FROM eqos.decisions
            WHERE subject_kind = 'REPORT_VERSION' AND subject_id = version
              AND kind IN ('SUBMIT', 'IMPORT_SEAL');
        IF target IS NULL THEN
            RAISE EXCEPTION 'memory item % cites unsealed version %', NEW.item_id, version
                USING ERRCODE = '23514';
        END IF;
    ELSE
        target := coalesce(
            (SELECT s.published_at FROM eqos.definition_records r
             JOIN eqos.definition_sets s ON s.id = r.definition_set_id
             WHERE r.id = NEW.definition_record_id),
            (SELECT recorded_at FROM eqos.queue_dispositions WHERE id = NEW.disposition_id),
            (SELECT recorded_at FROM eqos.decisions WHERE id = NEW.decision_id),
            (SELECT greatest(registered_at, first_seen_at) FROM eqos.capture_refs
             WHERE id = NEW.capture_ref_id));
    END IF;
    IF target > known THEN
        RAISE EXCEPTION 'memory item % predates its support target', NEW.item_id
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;
