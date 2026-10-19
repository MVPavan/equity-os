-- PILOT-GAP memory Task 1 (eqos-4j2.20): an item's natural key is its columns, so a retried or
-- concurrent identical stage converges on one row whoever the writer is. 0001--0040 are
-- immutable. Existing duplicates are refused with their ids for an owner disposition, never
-- deleted.

DO $$
DECLARE
    groups text;
BEGIN
    SELECT string_agg(ids, '; ') INTO groups FROM (
        SELECT string_agg(id::text, ', ' ORDER BY id) AS ids FROM eqos.memory_items
        GROUP BY entity_id, kind, statement, epistemic_class, valid_from, valid_to,
                 supersedes_item_id
        HAVING count(*) > 1) duplicates;
    IF groups IS NOT NULL THEN
        RAISE EXCEPTION 'duplicate memory items need an owner disposition: %', groups
            USING ERRCODE = '23505';
    END IF;
END $$;

CREATE UNIQUE INDEX memory_items_natural_key ON eqos.memory_items (entity_id, kind, statement,
    epistemic_class, valid_from, valid_to, supersedes_item_id) NULLS NOT DISTINCT;
