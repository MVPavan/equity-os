-- DOCS-1: listing coverage, occurrence revisions and per-revision document attempts.
CREATE TABLE eqos.document_listings (
    id bigserial PRIMARY KEY,
    entity_id bigint NOT NULL,
    symbol text NOT NULL,
    surface text NOT NULL,
    span_from date, span_to date,
    retrieved_at timestamptz NOT NULL,
    outcome text NOT NULL,
    capture_ref_id bigint REFERENCES eqos.capture_refs (id),
    recorded_at timestamptz NOT NULL DEFAULT eqos.store_now(),
    CHECK ((outcome = 'OK') = (capture_ref_id IS NOT NULL))
);
CREATE TABLE eqos.document_observations (
    id bigserial PRIMARY KEY,
    listing_id bigint NOT NULL REFERENCES eqos.document_listings (id),
    occurrence_key text NOT NULL,
    payload_sha256 text NOT NULL,
    payload jsonb NOT NULL,
    observed_at timestamptz NOT NULL
);
CREATE INDEX ON eqos.document_observations (occurrence_key, observed_at DESC, id DESC);
CREATE TABLE eqos.document_attempts (
    id bigserial PRIMARY KEY,
    observation_id bigint NOT NULL REFERENCES eqos.document_observations (id),
    url text NOT NULL,
    attempted_at timestamptz NOT NULL,
    outcome text NOT NULL,
    body_sha256 text,
    capture_ref_id bigint REFERENCES eqos.capture_refs (id),
    recorded_at timestamptz NOT NULL DEFAULT eqos.store_now(),
    CHECK ((outcome = 'OK') = (capture_ref_id IS NOT NULL))
);
CREATE INDEX ON eqos.document_attempts (observation_id, url);
DO $$
DECLARE name text;
BEGIN
    FOREACH name IN ARRAY ARRAY['document_listings', 'document_observations', 'document_attempts'] LOOP
        EXECUTE format('CREATE TRIGGER reject_row_mutation BEFORE UPDATE OR DELETE ON eqos.%I '
            'FOR EACH ROW EXECUTE FUNCTION eqos.reject_mutation()', name);
        EXECUTE format('CREATE TRIGGER reject_truncate BEFORE TRUNCATE ON eqos.%I '
            'FOR EACH STATEMENT EXECUTE FUNCTION eqos.reject_mutation()', name);
        EXECUTE format('GRANT SELECT, INSERT ON eqos.%I TO eqos_runtime', name);
        EXECUTE format('GRANT USAGE ON SEQUENCE eqos.%I TO eqos_runtime', name || '_id_seq');
        EXECUTE format('GRANT SELECT ON eqos.%I TO eqos_panel, eqos_owner, eqos_purge', name);
    END LOOP;
END $$;
