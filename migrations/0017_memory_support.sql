-- D4 Task 2: the memory support predicate, checked at staging, by PROMOTE and again at its
-- commit, and the one queue lock every write that can falsify a support holds (ledger spec §2,
-- amendment A1; plan D4, M3, M4). 0001--0016 are immutable.

-- M3 L: a quote's location, its blob and the anchor's parsed coordinates (citations.ANCHOR), so
-- duplicate capture rows of one blob and equivalent spellings meet. NULL when it does not parse.
CREATE FUNCTION eqos.quote_location(blob text, anchor text) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT blob || ':' || array_to_string(
        (regexp_match(anchor, '^p(\d+)\.b(\d+)\.(\d+):(\d+)$'))::int[], '.')
$$;

CREATE FUNCTION eqos.quote_location(capture bigint, anchor text) RETURNS text
LANGUAGE sql STABLE AS $$
    SELECT eqos.quote_location(blob_sha256, anchor) FROM eqos.capture_refs WHERE id = capture
$$;

-- M3 P: an AS_KNOWN validation of the version as sealed, MATCH for every claim and nothing else.
CREATE FUNCTION eqos.memory_validation_passes(checked eqos.validations) RETURNS boolean
LANGUAGE sql STABLE AS $$
    SELECT checked.mode = 'AS_KNOWN'
        AND checked.sealed_digest = eqos.version_sealed_digest(checked.version_id)
        AND NOT EXISTS (SELECT 1 FROM eqos.validation_claim_states s
                        WHERE s.validation_id = checked.id
                          AND (s.claim_id IS NULL OR s.state <> 'MATCH'))
        AND NOT EXISTS (SELECT 1 FROM eqos.numeric_claims c
                        WHERE c.version_id = checked.version_id AND NOT EXISTS (
                            SELECT 1 FROM eqos.validation_claim_states s
                            WHERE s.validation_id = checked.id AND s.claim_id = c.id))
$$;

-- The version's head decision as of a time (NULL: everything committed).
CREATE FUNCTION eqos.memory_version_head(version bigint, as_of timestamptz) RETURNS text
LANGUAGE sql STABLE AS $$
    SELECT kind FROM eqos.decisions
    WHERE subject_kind = 'REPORT_VERSION' AND subject_id = version
      AND (as_of IS NULL OR recorded_at <= as_of)
    ORDER BY sequence DESC LIMIT 1
$$;

-- M3 V: approved and not superseded, with a trusted AS_KNOWN validation T, and every
-- validation from T on (store time, then id) passing P.
CREATE FUNCTION eqos.memory_version_valid(version bigint, as_of timestamptz) RETURNS boolean
LANGUAGE sql STABLE AS $$
    WITH RECURSIVE descendants (id) AS (
        SELECT id FROM eqos.report_versions WHERE predecessor_id = version
        UNION ALL
        SELECT v.id FROM eqos.report_versions v JOIN descendants d ON v.predecessor_id = d.id
    ), checks AS (
        SELECT * FROM eqos.validations
        WHERE version_id = version AND (as_of IS NULL OR recorded_at <= as_of)
    ), trusted AS (
        SELECT recorded_at, id FROM checks
        WHERE creator IN ('PANEL', 'OWNER') AND mode = 'AS_KNOWN'
        ORDER BY recorded_at DESC, id DESC LIMIT 1
    )
    SELECT coalesce(eqos.memory_version_head(version, as_of) IN ('APPROVE', 'IMPORTED_APPROVAL'),
                    false)
        AND NOT EXISTS (SELECT 1 FROM eqos.decisions
                        WHERE subject_kind = 'REPORT_VERSION'
                          AND kind IN ('APPROVE', 'IMPORTED_APPROVAL')
                          AND subject_id IN (SELECT id FROM descendants)
                          AND (as_of IS NULL OR recorded_at <= as_of))
        AND EXISTS (SELECT 1 FROM trusted)
        AND NOT EXISTS (SELECT 1 FROM checks c, trusted t
                        WHERE (c.recorded_at, c.id) >= (t.recorded_at, t.id)
                          AND NOT eqos.memory_validation_passes(c))
$$;

-- M3: whether one support meets its item kind's rule as of a time (the table in the plan), with
-- E (a stock's item cites only its own stock's claims and versions) and D (a disposition is
-- not superseded) and the LESSON exception R (a rejected version as evidence of a mistake).
CREATE FUNCTION eqos.memory_support_holds(item_kind text, support eqos.memory_supports,
                                          as_of timestamptz) RETURNS boolean
LANGUAGE sql STABLE AS $$
    SELECT coalesce(CASE
        WHEN support.claim_id IS NOT NULL THEN
            item_kind IN ('COMPANY_UNDERSTANDING', 'MANAGEMENT_TRACK_RECORD')
            AND eqos.memory_version_valid(
                (SELECT version_id FROM eqos.numeric_claims WHERE id = support.claim_id), as_of)
        WHEN support.version_id IS NOT NULL THEN CASE
            WHEN item_kind = 'LESSON' THEN
                eqos.memory_version_head(support.version_id, as_of) = 'REJECT'
            ELSE item_kind IN ('COMPANY_UNDERSTANDING', 'THESIS_AND_WARNING')
                AND eqos.memory_version_valid(support.version_id, as_of) END
        WHEN support.definition_record_id IS NOT NULL OR support.capture_ref_id IS NOT NULL THEN
            item_kind = 'SOURCE_QUIRK'
        WHEN support.disposition_id IS NOT NULL THEN
            item_kind IN ('SOURCE_QUIRK', 'LESSON') AND NOT EXISTS (
                SELECT 1 FROM eqos.queue_dispositions d JOIN eqos.queue_dispositions later
                    ON later.item_id = d.item_id
                    AND (later.recorded_at, later.id) > (d.recorded_at, d.id)
                WHERE d.id = support.disposition_id
                  AND (as_of IS NULL OR later.recorded_at <= as_of))
        WHEN support.decision_id IS NOT NULL THEN CASE item_kind
            WHEN 'LESSON' THEN true
            WHEN 'OWNER_RULING' THEN EXISTS (SELECT 1 FROM eqos.decisions
                WHERE id = support.decision_id AND decider = 'OWNER' AND ruling <> '')
            ELSE false END
    END, false)
    AND NOT EXISTS (
        SELECT 1 FROM eqos.memory_items i
        JOIN eqos.report_versions v ON v.id = coalesce(support.version_id,
            (SELECT version_id FROM eqos.numeric_claims WHERE id = support.claim_id))
        JOIN eqos.reports r ON r.id = v.report_id
        WHERE i.id = support.item_id AND i.entity_id IS NOT NULL AND r.entity_id <> i.entity_id)
$$;

-- Every support holds and, for a track record, at least two claims, one a quote, and no two
-- quotes at one location (an unparsed or missing location counts as shared). NULL item: false.
CREATE FUNCTION eqos.memory_item_supported(item bigint, as_of timestamptz) RETURNS boolean
LANGUAGE sql STABLE AS $$
    SELECT coalesce((
        SELECT EXISTS (SELECT 1 FROM eqos.memory_supports WHERE item_id = i.id)
            AND NOT EXISTS (SELECT 1 FROM eqos.memory_supports s
                            WHERE s.item_id = i.id
                              AND NOT eqos.memory_support_holds(i.kind, s, as_of))
            AND (i.kind <> 'MANAGEMENT_TRACK_RECORD' OR (
                (SELECT count(*) FROM eqos.memory_supports WHERE item_id = i.id) >= 2
                AND EXISTS (SELECT 1 FROM eqos.memory_supports s
                            JOIN eqos.numeric_claims c ON c.id = s.claim_id
                            WHERE s.item_id = i.id AND c.citation_kind = 'SOURCE_QUOTE')
                AND NOT EXISTS (
                    SELECT 1 FROM eqos.memory_supports s1
                    JOIN eqos.numeric_claims c1 ON c1.id = s1.claim_id
                    JOIN eqos.memory_supports s2 ON s2.item_id = s1.item_id AND s2.id > s1.id
                    JOIN eqos.numeric_claims c2 ON c2.id = s2.claim_id
                    WHERE s1.item_id = i.id AND c1.citation_kind = 'SOURCE_QUOTE'
                      AND c2.citation_kind = 'SOURCE_QUOTE'
                      AND coalesce(eqos.quote_location(c1.capture_ref_id, c1.anchor)
                                   = eqos.quote_location(c2.capture_ref_id, c2.anchor), true))))
        FROM eqos.memory_items i WHERE i.id = item), false)
$$;

-- Staging (deferred to commit) and PROMOTE (before insert, and again at its commit, M4).
CREATE FUNCTION eqos.check_memory_supports_hold() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, eqos AS $$
DECLARE
    item    bigint;
BEGIN
    IF TG_TABLE_NAME = 'memory_items' THEN
        item := NEW.id;
    ELSE
        item := NEW.subject_id;
    END IF;
    IF NOT eqos.memory_item_supported(item, NULL) THEN
        RAISE EXCEPTION 'memory item % fails its support predicate', item USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;

-- M4: PROMOTE is the last support-relevant write of its transaction.
CREATE FUNCTION eqos.refuse_after_promote() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, eqos AS $$ BEGIN
    IF EXISTS (SELECT 1 FROM eqos.decisions
               WHERE subject_kind = 'MEMORY_ITEM' AND kind = 'PROMOTE'
                 AND created_xid = txid_current()) THEN
        RAISE EXCEPTION 'no % write may follow a memory PROMOTE in its transaction', TG_TABLE_NAME
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;

-- M4: a write that can falsify a support takes the queue lock before its first store-clock
-- read, so it serializes with PROMOTE. A root version's approval supersedes nothing.
CREATE FUNCTION eqos.lock_support_writer() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, eqos AS $$ BEGIN
    IF TG_TABLE_NAME = 'validations' THEN
        PERFORM eqos.lock_queue();
    ELSIF NEW.kind = 'WITHDRAW' OR EXISTS (SELECT 1 FROM eqos.report_versions
                                           WHERE id = NEW.subject_id AND predecessor_id IS NOT NULL)
    THEN
        PERFORM eqos.lock_queue();
    END IF;
    RETURN NEW;
END $$;

-- Sorts after check_memory_decision, which takes the queue lock and checks the chain.
CREATE TRIGGER check_memory_promotion BEFORE INSERT ON eqos.decisions FOR EACH ROW
    WHEN (NEW.subject_kind = 'MEMORY_ITEM' AND NEW.kind = 'PROMOTE')
    EXECUTE FUNCTION eqos.check_memory_supports_hold();
CREATE CONSTRAINT TRIGGER memory_promotion_at_commit AFTER INSERT ON eqos.decisions
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
    WHEN (NEW.subject_kind = 'MEMORY_ITEM' AND NEW.kind = 'PROMOTE')
    EXECUTE FUNCTION eqos.check_memory_supports_hold();
CREATE CONSTRAINT TRIGGER check_memory_supports_hold AFTER INSERT ON eqos.memory_items
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION eqos.check_memory_supports_hold();
-- The a_ prefix sorts before record_validation and check_decision, the subject locks.
CREATE TRIGGER a_lock_support_writer BEFORE INSERT ON eqos.validations
    FOR EACH ROW EXECUTE FUNCTION eqos.lock_support_writer();
CREATE TRIGGER a_lock_support_writer BEFORE INSERT ON eqos.decisions FOR EACH ROW
    WHEN (NEW.subject_kind = 'REPORT_VERSION'
          AND NEW.kind IN ('APPROVE', 'IMPORTED_APPROVAL', 'WITHDRAW'))
    EXECUTE FUNCTION eqos.lock_support_writer();
CREATE TRIGGER refuse_after_promote BEFORE INSERT ON eqos.decisions FOR EACH ROW
    WHEN (NEW.subject_kind = 'REPORT_VERSION') EXECUTE FUNCTION eqos.refuse_after_promote();

DO $$
DECLARE
    name text;
BEGIN
    -- The ledger's validations and 0006's tables carrying record_queue_time.
    FOREACH name IN ARRAY ARRAY['validations', 'validation_claim_states', 'queue_items',
                                'queue_run_items', 'queue_dispositions'] LOOP
        EXECUTE format('CREATE TRIGGER refuse_after_promote BEFORE INSERT ON eqos.%I '
            'FOR EACH ROW EXECUTE FUNCTION eqos.refuse_after_promote()', name);
    END LOOP;
END $$;
