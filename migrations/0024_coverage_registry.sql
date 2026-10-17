-- D7 Task 1: the universe registry (plan D7 R1, R2). 0001--0023 are immutable.
-- A load is one retained Upstox instrument capture, identified by its capture reference (not its
-- bytes: a later capture of identical bytes is a new load). Listings are stable (segment, ISIN);
-- each load records one sighting per listing with the observed symbol, token and name; a
-- listing's symbol differing from its sighting in the preceding load is a candidate event. The
-- registry never writes the identity layers (0022). Append-only like 0022; INSERT to the owner
-- role only, SELECT to all three.

CREATE TABLE eqos.registry_loads (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    capture_ref_id      bigint NOT NULL UNIQUE REFERENCES eqos.capture_refs (id),
    content_sha256      text NOT NULL,
    run_by              text NOT NULL DEFAULT current_user,
    recorded_at         timestamptz NOT NULL DEFAULT eqos.store_now()
);

CREATE TABLE eqos.registry_listings (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    segment             text NOT NULL CHECK (segment IN ('NSE_EQ', 'BSE_EQ')),
    isin                text NOT NULL,
    UNIQUE (segment, isin)
);

CREATE TABLE eqos.registry_sightings (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    listing_id          bigint NOT NULL REFERENCES eqos.registry_listings (id),
    load_id             bigint NOT NULL REFERENCES eqos.registry_loads (id),
    trading_symbol      text NOT NULL,
    exchange_token      text NOT NULL,
    name                text NOT NULL,
    UNIQUE (listing_id, load_id)
);

CREATE TABLE eqos.registry_candidate_events (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    listing_id          bigint NOT NULL REFERENCES eqos.registry_listings (id),
    load_id             bigint NOT NULL REFERENCES eqos.registry_loads (id),
    previous_symbol     text NOT NULL,
    observed_symbol     text NOT NULL,
    CHECK (previous_symbol <> observed_symbol),
    UNIQUE (listing_id, load_id)
);

-- Current attributes from each listing's latest sighting; LISTED iff seen in the latest load.
CREATE VIEW eqos.registry_view AS
SELECT l.id AS listing_id, l.segment, l.isin, last.trading_symbol, last.exchange_token,
       last.name, first.recorded_at AS first_seen_at, last.recorded_at AS last_seen_at,
       CASE WHEN last.load_id = (SELECT max(id) FROM eqos.registry_loads)
            THEN 'LISTED' ELSE 'NOT_SEEN' END AS status
FROM eqos.registry_listings l
CROSS JOIN LATERAL (
    SELECT s.trading_symbol, s.exchange_token, s.name, s.load_id, d.recorded_at
    FROM eqos.registry_sightings s JOIN eqos.registry_loads d ON d.id = s.load_id
    WHERE s.listing_id = l.id ORDER BY s.load_id DESC LIMIT 1) last
CROSS JOIN LATERAL (
    SELECT d.recorded_at
    FROM eqos.registry_sightings s JOIN eqos.registry_loads d ON d.id = s.load_id
    WHERE s.listing_id = l.id ORDER BY s.load_id LIMIT 1) first;

GRANT SELECT ON eqos.registry_view TO eqos_runtime, eqos_panel, eqos_owner;

DO $$
DECLARE
    table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY['registry_loads', 'registry_listings',
        'registry_sightings', 'registry_candidate_events'] LOOP
        EXECUTE format('CREATE TRIGGER reject_row_mutation BEFORE UPDATE OR DELETE ON eqos.%I '
            'FOR EACH ROW EXECUTE FUNCTION eqos.reject_mutation()', table_name);
        EXECUTE format('CREATE TRIGGER reject_truncate BEFORE TRUNCATE ON eqos.%I '
            'FOR EACH STATEMENT EXECUTE FUNCTION eqos.reject_mutation()', table_name);
        EXECUTE format('GRANT SELECT ON eqos.%I TO eqos_runtime, eqos_panel, eqos_owner', table_name);
        EXECUTE format('GRANT INSERT ON eqos.%I TO eqos_owner', table_name);
        EXECUTE format('GRANT USAGE ON SEQUENCE eqos.%I TO eqos_owner', table_name || '_id_seq');
    END LOOP;
END;
$$;

-- R2: the owner CLI registers its own captures (discovery.store_captures); nothing else in
-- evidence or identity.
GRANT INSERT ON eqos.capture_refs TO eqos_owner;
GRANT USAGE ON SEQUENCE eqos.capture_refs_id_seq TO eqos_owner;
