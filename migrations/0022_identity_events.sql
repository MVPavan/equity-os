-- D6 Task 2: temporal identity layers, onboarding records and settings valid_from (plan D6
-- D3.1). 0001--0021 are immutable. New tables are append-only like 0001: the runtime role
-- gets SELECT and INSERT (panel and owner SELECT, as 0012), eqos.reject_mutation() refuses
-- UPDATE, DELETE and TRUNCATE.

-- An identifier a security (ISIN) or a listing (NSE symbol, BSE scrip) holds from valid_from
-- (null = from first evidence) until an event's ENDS edge names it.
CREATE TABLE eqos.identifier_relationships (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    security_id         bigint REFERENCES eqos.securities (id),
    listing_id          bigint REFERENCES eqos.listings (id),
    namespace           text NOT NULL CHECK (namespace IN ('ISIN', 'NSE_SYMBOL', 'BSE_SCRIP')),
    value               text NOT NULL,
    valid_from          date,
    evidence_input_id   bigint NOT NULL REFERENCES eqos.evidence_inputs (id),
    recorded_at         timestamptz NOT NULL DEFAULT eqos.store_now(),
    CHECK (num_nonnulls(security_id, listing_id) = 1),
    CHECK ((namespace = 'ISIN') = (security_id IS NOT NULL))
);

CREATE TABLE eqos.identity_events (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kind                text NOT NULL CHECK (kind IN (
        'ISIN_CHANGE', 'SYMBOL_CHANGE', 'SYMBOL_REUSE', 'MERGER', 'DEMERGER', 'DELISTING')),
    effective_date      date NOT NULL,
    evidence_input_id   bigint NOT NULL REFERENCES eqos.evidence_inputs (id),
    recorded_at         timestamptz NOT NULL DEFAULT eqos.store_now()
);

CREATE TABLE eqos.identity_event_edges (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_id            bigint NOT NULL REFERENCES eqos.identity_events (id),
    role                text NOT NULL CHECK (role IN ('ENDS', 'STARTS', 'PREDECESSOR', 'SUCCESSOR')),
    relationship_id     bigint REFERENCES eqos.identifier_relationships (id),
    entity_id           bigint REFERENCES eqos.reporting_entities (id),
    CHECK (num_nonnulls(relationship_id, entity_id) = 1),
    CHECK ((role IN ('ENDS', 'STARTS')) = (relationship_id IS NOT NULL)),
    UNIQUE (event_id, entity_id)
);
CREATE UNIQUE INDEX identity_event_edges_one_end
    ON eqos.identity_event_edges (relationship_id) WHERE role = 'ENDS';

CREATE TABLE eqos.onboarding_records (
    id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    identifier              text NOT NULL,
    identifier_namespace    text NOT NULL,
    outcome                 text NOT NULL CHECK (outcome IN (
        'ONBOARDED', 'PARTIAL', 'UNSUPPORTED', 'IDENTITY_CONFLICT')),
    severity                text CHECK (severity = 'HIGH'),
    reason                  text,
    entity_id               bigint REFERENCES eqos.reporting_entities (id),
    evidence_input_id       bigint REFERENCES eqos.evidence_inputs (id),
    recorded_at             timestamptz NOT NULL DEFAULT eqos.store_now(),
    CHECK ((severity IS NOT NULL) = (outcome = 'IDENTITY_CONFLICT')),
    CHECK ((entity_id IS NOT NULL) = (outcome IN ('ONBOARDED', 'PARTIAL')))
);

CREATE TABLE eqos.namespace_verifications (
    id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    onboarding_record_id    bigint NOT NULL REFERENCES eqos.onboarding_records (id),
    unit                    text NOT NULL CHECK (unit IN (
        'EXCHANGE', 'XBRL_ENTITY', 'SCREENER', 'TIJORI', 'UPSTOX', 'RESULTS_PDF')),
    state                   text NOT NULL CHECK (state IN (
        'VERIFIED', 'UNVERIFIED', 'CONFLICT', 'NOT_AUTHORISED', 'UNAVAILABLE')),
    reason                  text,
    evidence_input_id       bigint REFERENCES eqos.evidence_inputs (id),
    CHECK (state = 'VERIFIED' OR char_length(reason) > 0),
    UNIQUE (onboarding_record_id, unit)
);

-- Null valid_from (every existing row) governs every period.
ALTER TABLE eqos.settings_records ADD COLUMN valid_from date;

ALTER TABLE eqos.evidence_inputs DROP CONSTRAINT evidence_inputs_kind_check;
ALTER TABLE eqos.evidence_inputs ADD CHECK (kind IN (
    'ENTITY_MAP', 'ISSUER_IDENTITY', 'ISSUER_CONFIG', 'DISCOVERY'));
ALTER TABLE eqos.settings_records DROP CONSTRAINT settings_records_setting_key_check;
ALTER TABLE eqos.settings_records ADD CHECK (setting_key IN (
    'FISCAL_YEAR_END_MONTH', 'PDF_PRINTED_UNIT', 'PDF_LAYOUT', 'DOCUMENT_LOCATION',
    'PRESENTATION_CURRENCY', 'REPORTING_FRAMEWORK', 'FILING_ROUNDING_LEVEL'));
ALTER TABLE eqos.acquisition_attempts DROP CONSTRAINT acquisition_attempts_outcome_check;
ALTER TABLE eqos.acquisition_attempts ADD CHECK (outcome IN (
    'COMPLETE', 'NOT_PUBLISHED', 'PARTIAL', 'FAILED', 'NOT_AUTHORISED',
    'IDENTITY_REJECTED', 'UNSUPPORTED_SCHEMA', 'PARSE_FAILED', 'EXCLUDED_BY_RULE'));

DO $$
DECLARE
    table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY['identifier_relationships', 'identity_events',
        'identity_event_edges', 'onboarding_records', 'namespace_verifications'] LOOP
        EXECUTE format('CREATE TRIGGER reject_row_mutation BEFORE UPDATE OR DELETE ON eqos.%I '
            'FOR EACH ROW EXECUTE FUNCTION eqos.reject_mutation()', table_name);
        EXECUTE format('CREATE TRIGGER reject_truncate BEFORE TRUNCATE ON eqos.%I '
            'FOR EACH STATEMENT EXECUTE FUNCTION eqos.reject_mutation()', table_name);
        EXECUTE format('GRANT SELECT ON eqos.%I TO eqos_runtime, eqos_panel, eqos_owner', table_name);
        EXECUTE format('GRANT INSERT ON eqos.%I TO eqos_runtime', table_name);
        EXECUTE format('GRANT USAGE ON SEQUENCE eqos.%I TO eqos_runtime', table_name || '_id_seq');
    END LOOP;
END;
$$;
