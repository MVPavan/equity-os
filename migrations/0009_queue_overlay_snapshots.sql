-- Durable queue-overlay visibility seals. Existing queue rows remain append-only and unchanged.

CREATE FUNCTION eqos.queue_ids_are_sorted_unique(ids bigint[]) RETURNS boolean
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE
SET search_path=pg_catalog AS $$
    SELECT array_position(ids, NULL) IS NULL AND NOT EXISTS (
        SELECT 1
        FROM (
            SELECT value, lag(value) OVER (ORDER BY ordinal) AS previous
            FROM unnest(ids) WITH ORDINALITY AS entries(value, ordinal)
        ) AS ordered
        WHERE previous IS NOT NULL AND value <= previous
    )
$$;

CREATE TABLE eqos.queue_overlay_snapshots (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id bigint NOT NULL REFERENCES eqos.runs(id),
    as_of timestamptz NOT NULL,
    recorded_position bigint NOT NULL CHECK(recorded_position >= 0),
    membership_ids bigint[] NOT NULL,
    item_ids bigint[] NOT NULL,
    disposition_candidate_ids bigint[] NOT NULL,
    UNIQUE(run_id, as_of, recorded_position),
    CHECK(as_of = timestamptz 'epoch' + recorded_position * interval '1 microsecond'),
    CHECK(cardinality(membership_ids) = cardinality(item_ids)),
    CHECK(eqos.queue_ids_are_sorted_unique(membership_ids)),
    CHECK(eqos.queue_ids_are_sorted_unique(item_ids)),
    CHECK(eqos.queue_ids_are_sorted_unique(disposition_candidate_ids))
);

CREATE FUNCTION eqos.check_queue_overlay_snapshot() RETURNS trigger
LANGUAGE plpgsql
SET search_path=pg_catalog AS $$
DECLARE
    expected_memberships bigint[];
    expected_items bigint[];
    expected_dispositions bigint[];
BEGIN
    IF current_setting('transaction_isolation') NOT IN ('repeatable read', 'serializable') THEN
        RAISE EXCEPTION 'queue overlay capture requires repeatable read or serializable isolation'
            USING ERRCODE='25001';
    END IF;

    SELECT
        coalesce(array_agg(membership.id ORDER BY membership.id), ARRAY[]::bigint[]),
        coalesce(array_agg(membership.item_id ORDER BY membership.item_id), ARRAY[]::bigint[])
    INTO expected_memberships, expected_items
    FROM eqos.queue_run_items AS membership
    JOIN eqos.queue_items AS item ON item.id=membership.item_id
    WHERE membership.run_id=NEW.run_id
      AND membership.recorded_at<=NEW.as_of
      AND item.recorded_at<=NEW.as_of;

    SELECT coalesce(array_agg(disposition.id ORDER BY disposition.id), ARRAY[]::bigint[])
    INTO expected_dispositions
    FROM eqos.queue_dispositions AS disposition
    WHERE disposition.item_id=ANY(expected_items)
      AND disposition.recorded_at<=NEW.as_of;

    IF NEW.membership_ids IS DISTINCT FROM expected_memberships
       OR NEW.item_ids IS DISTINCT FROM expected_items
       OR NEW.disposition_candidate_ids IS DISTINCT FROM expected_dispositions THEN
        RAISE EXCEPTION 'queue overlay snapshot differs from its transaction-visible row set'
            USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER check_queue_overlay_snapshot
BEFORE INSERT ON eqos.queue_overlay_snapshots
FOR EACH ROW EXECUTE FUNCTION eqos.check_queue_overlay_snapshot();

CREATE TRIGGER reject_queue_overlay_snapshot_mutation
BEFORE UPDATE OR DELETE ON eqos.queue_overlay_snapshots
FOR EACH ROW EXECUTE FUNCTION eqos.reject_mutation();

CREATE TRIGGER reject_queue_overlay_snapshot_truncate
BEFORE TRUNCATE ON eqos.queue_overlay_snapshots
FOR EACH STATEMENT EXECUTE FUNCTION eqos.reject_mutation();

CREATE FUNCTION eqos.capture_queue_overlay_snapshot(requested_run_id bigint)
RETURNS SETOF eqos.queue_overlay_snapshots
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog AS $$
DECLARE
    captured_as_of timestamptz;
    captured_position bigint;
    captured_memberships bigint[];
    captured_items bigint[];
    captured_dispositions bigint[];
    stored eqos.queue_overlay_snapshots%ROWTYPE;
BEGIN
    IF current_setting('transaction_isolation') NOT IN ('repeatable read', 'serializable') THEN
        RAISE EXCEPTION 'queue overlay capture requires repeatable read or serializable isolation'
            USING ERRCODE='25001';
    END IF;
    IF requested_run_id IS NULL OR requested_run_id <= 0
       OR NOT EXISTS(SELECT 1 FROM eqos.runs WHERE id=requested_run_id) THEN
        RAISE EXCEPTION 'queue overlay run is not stored' USING ERRCODE='23503';
    END IF;

    WITH clock AS MATERIALIZED (SELECT eqos.store_now() AS as_of)
    SELECT as_of, floor(extract(epoch FROM as_of)*1000000)::bigint
    INTO captured_as_of, captured_position
    FROM clock;

    SELECT
        coalesce(array_agg(membership.id ORDER BY membership.id), ARRAY[]::bigint[]),
        coalesce(array_agg(membership.item_id ORDER BY membership.item_id), ARRAY[]::bigint[])
    INTO captured_memberships, captured_items
    FROM eqos.queue_run_items AS membership
    JOIN eqos.queue_items AS item ON item.id=membership.item_id
    WHERE membership.run_id=requested_run_id
      AND membership.recorded_at<=captured_as_of
      AND item.recorded_at<=captured_as_of;

    SELECT coalesce(array_agg(disposition.id ORDER BY disposition.id), ARRAY[]::bigint[])
    INTO captured_dispositions
    FROM eqos.queue_dispositions AS disposition
    WHERE disposition.item_id=ANY(captured_items)
      AND disposition.recorded_at<=captured_as_of;

    INSERT INTO eqos.queue_overlay_snapshots (
        run_id, as_of, recorded_position, membership_ids, item_ids,
        disposition_candidate_ids
    ) VALUES (
        requested_run_id, captured_as_of, captured_position, captured_memberships,
        captured_items, captured_dispositions
    )
    ON CONFLICT (run_id, as_of, recorded_position) DO NOTHING
    RETURNING * INTO stored;

    IF NOT FOUND THEN
        SELECT * INTO stored
        FROM eqos.queue_overlay_snapshots AS snapshot
        WHERE snapshot.run_id=requested_run_id
          AND snapshot.as_of=captured_as_of
          AND snapshot.recorded_position=captured_position;
        IF NOT FOUND
           OR stored.membership_ids IS DISTINCT FROM captured_memberships
           OR stored.item_ids IS DISTINCT FROM captured_items
           OR stored.disposition_candidate_ids IS DISTINCT FROM captured_dispositions THEN
            RAISE EXCEPTION 'queue overlay snapshot triple has a different visible row set'
                USING ERRCODE='23514';
        END IF;
    END IF;

    RETURN NEXT stored;
END $$;

REVOKE ALL ON TABLE eqos.queue_overlay_snapshots FROM PUBLIC, eqos_runtime;
REVOKE ALL ON SEQUENCE eqos.queue_overlay_snapshots_id_seq FROM PUBLIC, eqos_runtime;
REVOKE ALL ON FUNCTION eqos.queue_ids_are_sorted_unique(bigint[]) FROM PUBLIC, eqos_runtime;
REVOKE ALL ON FUNCTION eqos.check_queue_overlay_snapshot() FROM PUBLIC, eqos_runtime;
REVOKE ALL ON FUNCTION eqos.capture_queue_overlay_snapshot(bigint) FROM PUBLIC;
GRANT SELECT ON TABLE eqos.queue_overlay_snapshots TO eqos_runtime;
GRANT EXECUTE ON FUNCTION eqos.capture_queue_overlay_snapshot(bigint) TO eqos_runtime;
