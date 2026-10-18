-- D7 screen export Task 5 (plan D7-screen-export S5; Task 5 holds). 0001--0034 are immutable.
-- A pair's review items: each member of either run that did not bind (UNRESOLVED), or bound with
-- no member of the other run bound to the same ISIN (ABSENT, or NOT_PROVEN while the other run has
-- unresolved members; candidates are those sharing an NSE or BSE code). An item stays pending until
-- the owner's one disposition. Each pending item gets one other-vendor read or a named gap. Pair,
-- disposition and read inserts take the retention lock; holds.py holds the pair's captures while
-- an item is pending.

CREATE TABLE eqos.screen_member_dispositions (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pair_id         bigint NOT NULL REFERENCES eqos.screen_run_pairs (id),
    member_id       bigint NOT NULL REFERENCES eqos.screen_members (id),
    kind            text NOT NULL CHECK (kind IN ('ACCEPTED_AS_DEFINITION', 'MAPPING_FIX',
                        'DISMISSED')),
    reason          text NOT NULL CHECK (reason <> ''),
    evidence_ref    text NOT NULL CHECK (evidence_ref <> ''),
    decided_by      text NOT NULL DEFAULT current_user,
    recorded_at     timestamptz NOT NULL DEFAULT eqos.store_now(),
    UNIQUE (pair_id, member_id)
);

CREATE TABLE eqos.screen_other_vendor_reads (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pair_id         bigint NOT NULL REFERENCES eqos.screen_run_pairs (id),
    member_id       bigint NOT NULL REFERENCES eqos.screen_members (id),
    capture_ref_id  bigint REFERENCES eqos.capture_refs (id),
    gap             text CHECK (gap IN ('MEMBER_UNRESOLVED', 'NOT_VERIFIED', 'READ_REFUSED')),
    recorded_at     timestamptz NOT NULL DEFAULT eqos.store_now(),
    UNIQUE (pair_id, member_id),
    CHECK ((capture_ref_id IS NULL) <> (gap IS NULL))
);

CREATE VIEW eqos.screen_review_items AS
WITH sides AS (
    SELECT p.id AS pair_id, m.id AS member_id, r.vendor, m.listing_id, m.reason, m.nse_code,
        m.bse_code, l.isin,
        CASE r.vendor WHEN 'SCREENER' THEN p.tijori_run_id ELSE p.screener_run_id END AS other
    FROM eqos.screen_run_pairs p
    JOIN eqos.screen_runs r ON r.id IN (p.screener_run_id, p.tijori_run_id)
    JOIN eqos.screen_members m ON m.screen_run_id = r.id
    LEFT JOIN eqos.registry_listings l ON l.id = m.listing_id
)
SELECT s.pair_id, s.member_id, s.vendor,
    CASE WHEN s.listing_id IS NULL THEN 'UNRESOLVED'
         WHEN EXISTS (SELECT 1 FROM eqos.screen_members o
                      WHERE o.screen_run_id = s.other AND o.listing_id IS NULL) THEN 'NOT_PROVEN'
         ELSE 'ABSENT' END AS status,
    s.reason, s.nse_code,
    ARRAY(SELECT o.id FROM eqos.screen_members o
          WHERE s.listing_id IS NOT NULL AND o.screen_run_id = s.other AND o.listing_id IS NULL
            AND (o.nse_code = s.nse_code OR o.bse_code = s.bse_code)
          ORDER BY o.id) AS candidate_member_ids
FROM sides s
WHERE s.listing_id IS NULL OR NOT EXISTS (
    SELECT 1 FROM eqos.screen_members o JOIN eqos.registry_listings l ON l.id = o.listing_id
    WHERE o.screen_run_id = s.other AND l.isin = s.isin);

CREATE VIEW eqos.screen_review_pending AS
SELECT i.* FROM eqos.screen_review_items i
WHERE NOT EXISTS (SELECT 1 FROM eqos.screen_member_dispositions d
                  WHERE (d.pair_id, d.member_id) = (i.pair_id, i.member_id));

-- The retention lock first; a disposition or read names one review item of its pair.
CREATE FUNCTION eqos.check_screen_review() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM eqos.retention_shared();
    IF TG_TABLE_NAME <> 'screen_run_pairs' THEN
        IF NOT EXISTS (SELECT 1 FROM eqos.screen_review_items i
                       WHERE (i.pair_id, i.member_id) = (NEW.pair_id, NEW.member_id)) THEN
            RAISE EXCEPTION 'member % is not a review item of pair %', NEW.member_id,
                NEW.pair_id USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

DO $$
DECLARE
    table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY['screen_run_pairs', 'screen_member_dispositions',
        'screen_other_vendor_reads'] LOOP
        EXECUTE format('CREATE TRIGGER a0_check_screen_review BEFORE INSERT ON eqos.%I '
            'FOR EACH ROW EXECUTE FUNCTION eqos.check_screen_review()', table_name);
    END LOOP;
    FOREACH table_name IN ARRAY ARRAY['screen_member_dispositions',
        'screen_other_vendor_reads'] LOOP
        EXECUTE format('CREATE TRIGGER reject_row_mutation BEFORE UPDATE OR DELETE ON eqos.%I '
            'FOR EACH ROW EXECUTE FUNCTION eqos.reject_mutation()', table_name);
        EXECUTE format('CREATE TRIGGER reject_truncate BEFORE TRUNCATE ON eqos.%I '
            'FOR EACH STATEMENT EXECUTE FUNCTION eqos.reject_mutation()', table_name);
        EXECUTE format('GRANT INSERT ON eqos.%I TO eqos_owner', table_name);
        EXECUTE format('GRANT USAGE ON SEQUENCE eqos.%I TO eqos_owner', table_name || '_id_seq');
    END LOOP;
END;
$$;
GRANT SELECT ON eqos.screen_member_dispositions, eqos.screen_other_vendor_reads,
    eqos.screen_review_items, eqos.screen_review_pending
    TO eqos_runtime, eqos_panel, eqos_owner, eqos_purge;
