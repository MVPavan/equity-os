-- D2 Task 2: the fact store in PostgreSQL and the legacy import (plan D2, design decisions 2-7, 9).
-- Stores are namespaces. Imported legacy columns keep the exact SQLite text. Every table is
-- append-only. 0001--0009 are immutable.
CREATE SEQUENCE eqos.fact_native_id AS bigint;

CREATE TABLE eqos.fact_stores (
    store_id    text PRIMARY KEY,
    kind        text NOT NULL CHECK (kind IN ('LEGACY_SQLITE', 'NATIVE')),
    file_label  text,
    file_sha256 text,
    CHECK ((kind = 'LEGACY_SQLITE') = (file_label IS NOT NULL AND file_sha256 IS NOT NULL))
);

CREATE TABLE eqos.fact_rows (
    target_store          text NOT NULL REFERENCES eqos.fact_stores (store_id),
    handle                bigint NOT NULL,
    origin                text NOT NULL,
    origin_id             bigint NOT NULL,
    content_identity      text NOT NULL,
    value_hash            text NOT NULL,
    revision_family       text NOT NULL,
    revision_ordinal      bigint NOT NULL,
    canonical_status      text NOT NULL,
    canonical_selected_at text,
    canonical_reason      text,
    source_id             text NOT NULL,
    file_sha256           text NOT NULL,
    anchor                text NOT NULL,
    valid_time_start      text NOT NULL,
    valid_time_end        text,
    knowledge_time        text NOT NULL,
    first_seen_time       text NOT NULL,
    fact_json             text NOT NULL,
    created_at            text NOT NULL,
    PRIMARY KEY (target_store, handle),
    UNIQUE (origin, origin_id),
    UNIQUE (target_store, content_identity, value_hash),
    UNIQUE (target_store, content_identity, revision_ordinal)
);

CREATE TABLE eqos.fact_selections (
    target_store        text NOT NULL,
    handle              bigint NOT NULL,
    origin              text NOT NULL,
    origin_id           bigint NOT NULL,
    content_identity    text NOT NULL,
    row_handle          bigint NOT NULL,
    sequence            bigint NOT NULL,
    predecessor_handle  bigint,
    selected_at         text NOT NULL,
    reason              text NOT NULL,
    legacy_baseline     boolean NOT NULL,
    synthesized         boolean NOT NULL,
    selection_sha256    text NOT NULL,
    PRIMARY KEY (target_store, handle),
    UNIQUE (origin, origin_id),
    UNIQUE (target_store, content_identity, sequence),
    UNIQUE (target_store, content_identity, selected_at),
    UNIQUE (target_store, predecessor_handle),
    CHECK ((sequence = 1) = (predecessor_handle IS NULL)),
    FOREIGN KEY (target_store, row_handle) REFERENCES eqos.fact_rows (target_store, handle),
    FOREIGN KEY (target_store, predecessor_handle)
        REFERENCES eqos.fact_selections (target_store, handle)
);

CREATE TABLE eqos.fact_store_events (
    id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    store_id                text NOT NULL REFERENCES eqos.fact_stores (store_id),
    operation_id            uuid NOT NULL,
    state                   text NOT NULL
        CHECK (state IN ('IMPORTED', 'CUTOVER_FROZEN', 'OPEN', 'ROLLED_BACK')),
    approval_sha256         text,
    owner_record_sha256     text,
    last_row_handle         bigint,
    last_selection_handle   bigint,
    recorded_at             timestamptz NOT NULL,
    UNIQUE (store_id, operation_id)
);

CREATE TABLE eqos.legacy_fact_translations (
    target_store        text NOT NULL,
    row_handle          bigint NOT NULL,
    translation_version text NOT NULL,
    entity_id           bigint NOT NULL REFERENCES eqos.reporting_entities (id),
    canonical_id        text NOT NULL,
    period_start        date,
    period_end          date,
    period_instant      date,
    basis               text NOT NULL,
    framework           text NOT NULL,
    currency            text,
    value_kind          text NOT NULL,
    dimension_set       jsonb NOT NULL,
    PRIMARY KEY (target_store, row_handle),
    FOREIGN KEY (target_store, row_handle) REFERENCES eqos.fact_rows (target_store, handle)
);

CREATE TABLE eqos.legacy_evidence_bindings (
    target_store    text NOT NULL,
    row_handle      bigint NOT NULL,
    capture_ref_id  bigint NOT NULL REFERENCES eqos.capture_refs (id),
    file_sha256     text NOT NULL,
    anchor          text NOT NULL,
    PRIMARY KEY (target_store, row_handle),
    FOREIGN KEY (target_store, row_handle) REFERENCES eqos.fact_rows (target_store, handle)
);

CREATE TABLE eqos.legacy_imports (
    store_id            text PRIMARY KEY REFERENCES eqos.fact_stores (store_id),
    manifest_sha256     text NOT NULL,
    preflight_sha256    text NOT NULL,
    file_sha256         text NOT NULL
);

DO $$
DECLARE
    table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY['fact_stores', 'fact_rows', 'fact_selections',
        'fact_store_events', 'legacy_fact_translations', 'legacy_evidence_bindings',
        'legacy_imports'] LOOP
        EXECUTE format('CREATE TRIGGER reject_row_mutation BEFORE UPDATE OR DELETE ON eqos.%I '
            'FOR EACH ROW EXECUTE FUNCTION eqos.reject_mutation()', table_name);
        EXECUTE format('CREATE TRIGGER reject_truncate BEFORE TRUNCATE ON eqos.%I '
            'FOR EACH STATEMENT EXECUTE FUNCTION eqos.reject_mutation()', table_name);
        EXECUTE format('GRANT SELECT, INSERT ON eqos.%I TO eqos_runtime', table_name);
    END LOOP;
END;
$$;
GRANT USAGE ON SEQUENCE eqos.fact_native_id, eqos.fact_store_events_id_seq TO eqos_runtime;
