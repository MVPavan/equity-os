-- D1a evidence schema (plan docs/workstreams/data-foundation/plans/D1a.md, Task 2).
-- Run as eqos_migrator, which owns schema eqos and every object in it. Every table is
-- append-only: eqos.reject_mutation() refuses UPDATE, DELETE and TRUNCATE, and the runtime
-- role is granted SELECT and INSERT only. Enum CHECK lists copy the plan's Python enums
-- verbatim; a drift between the two is a defect.

CREATE SCHEMA eqos;
REVOKE ALL ON SCHEMA eqos FROM PUBLIC;

-- ---------------------------------------------------------------------------
-- Captures, identity and settings
-- ---------------------------------------------------------------------------

CREATE TABLE eqos.capture_refs (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_id       text NOT NULL,
    surface         text NOT NULL,
    request_key     text NOT NULL,
    capture_id      text NOT NULL,
    blob_sha256     text NOT NULL,
    record_sha256   text NOT NULL,
    registered_at   timestamptz NOT NULL,
    first_seen_at   timestamptz NOT NULL,
    UNIQUE (source_id, surface, request_key, capture_id)
);

CREATE TABLE eqos.evidence_inputs (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kind            text NOT NULL CHECK (kind IN ('ENTITY_MAP', 'ISSUER_IDENTITY', 'ISSUER_CONFIG')),
    label           text NOT NULL,
    content_sha256  text NOT NULL,
    recorded_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (kind, content_sha256)
);

CREATE TABLE eqos.evidence_input_captures (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    evidence_input_id   bigint NOT NULL REFERENCES eqos.evidence_inputs (id),
    capture_ref_id      bigint NOT NULL REFERENCES eqos.capture_refs (id),
    UNIQUE (evidence_input_id, capture_ref_id)
);

CREATE TABLE eqos.reporting_entities (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_key          text NOT NULL,
    market              text NOT NULL,
    display_name        text NOT NULL,
    evidence_input_id   bigint NOT NULL REFERENCES eqos.evidence_inputs (id),
    created_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (entity_key)
);

CREATE TABLE eqos.securities (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_id           bigint NOT NULL REFERENCES eqos.reporting_entities (id),
    isin                text,
    share_class         text NOT NULL,
    evidence_input_id   bigint NOT NULL REFERENCES eqos.evidence_inputs (id),
    UNIQUE NULLS NOT DISTINCT (entity_id, share_class, isin)
);
CREATE UNIQUE INDEX securities_isin_key ON eqos.securities (isin) WHERE isin IS NOT NULL;

CREATE TABLE eqos.listings (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    security_id         bigint NOT NULL REFERENCES eqos.securities (id),
    venue               text NOT NULL CHECK (venue IN ('NSE', 'BSE')),
    symbol              text NOT NULL,
    evidence_input_id   bigint NOT NULL REFERENCES eqos.evidence_inputs (id),
    UNIQUE (venue, symbol, security_id)
);

CREATE TABLE eqos.entity_basis_status (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_id           bigint NOT NULL REFERENCES eqos.reporting_entities (id),
    basis_status        text NOT NULL
        CHECK (basis_status IN ('CONSOLIDATED_AND_STANDALONE', 'STANDALONE_ONLY')),
    evidence_input_id   bigint NOT NULL REFERENCES eqos.evidence_inputs (id),
    recorded_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (entity_id, basis_status, evidence_input_id)
);

CREATE TABLE eqos.settings_records (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_id           bigint NOT NULL REFERENCES eqos.reporting_entities (id),
    setting_key         text NOT NULL
        CHECK (setting_key IN ('FISCAL_YEAR_END_MONTH', 'PDF_PRINTED_UNIT', 'PDF_LAYOUT')),
    value_text          text NOT NULL,
    evidence_input_id   bigint NOT NULL REFERENCES eqos.evidence_inputs (id),
    recorded_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (entity_id, setting_key, value_text, evidence_input_id)
);

-- ---------------------------------------------------------------------------
-- Packages
-- ---------------------------------------------------------------------------

CREATE TABLE eqos.filing_packages (
    id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_id               bigint NOT NULL REFERENCES eqos.reporting_entities (id),
    family                  text NOT NULL CHECK (family IN ('FINANCIAL_RESULTS', 'SHAREHOLDING')),
    reporting_period_end    date NOT NULL,
    basis                   text NOT NULL CHECK (basis IN ('CONSOLIDATED', 'STANDALONE')),
    framework               text NOT NULL
        CHECK (framework IN ('IND_AS', 'IFRS', 'US_GAAP', 'UNKNOWN')),
    reporting_kind          text NOT NULL CHECK (reporting_kind IN (
        'QUARTER', 'HALF_YEAR', 'NINE_MONTH', 'YEAR', 'TTM', 'INSTANT', 'OTHER')),
    knowledge_time          timestamptz NOT NULL,
    supersedes_package_id   bigint REFERENCES eqos.filing_packages (id),
    evidence_sha256         text NOT NULL,
    UNIQUE (entity_id, family, reporting_period_end, basis, framework, evidence_sha256)
);

CREATE TABLE eqos.package_members (
    id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    package_id              bigint NOT NULL REFERENCES eqos.filing_packages (id),
    capture_ref_id          bigint NOT NULL REFERENCES eqos.capture_refs (id),
    representation          text NOT NULL CHECK (representation IN ('XBRL', 'PDF')),
    knowledge_time          timestamptz NOT NULL,
    knowledge_time_raw      text NOT NULL,
    knowledge_time_status   text NOT NULL CHECK (knowledge_time_status IN ('KNOWN', 'UNKNOWN')),
    UNIQUE (package_id, representation)
);

CREATE TABLE eqos.package_statements (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    package_id          bigint NOT NULL REFERENCES eqos.filing_packages (id),
    statement_family    text NOT NULL CHECK (statement_family IN (
        'PL', 'BALANCE_SHEET', 'CASH_FLOW', 'SEGMENT', 'SHAREHOLDING', 'DERIVED')),
    role                text NOT NULL CHECK (role IN ('PRESENT', 'REPLACED')),
    UNIQUE (package_id, statement_family, role)
);

-- ---------------------------------------------------------------------------
-- Occurrences, attempts and interpretations (owned by a capture, never a package)
-- ---------------------------------------------------------------------------

CREATE TABLE eqos.occurrences (
    id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    capture_ref_id          bigint NOT NULL REFERENCES eqos.capture_refs (id),
    representation          text NOT NULL CHECK (representation IN ('XBRL', 'PDF')),
    extractor_version       text NOT NULL,
    native_field            text NOT NULL,
    raw_value_text          text,
    raw_unit                text NOT NULL,
    raw_scale               integer NOT NULL,
    raw_sign                integer NOT NULL,
    precision_kind          text NOT NULL CHECK (precision_kind IN ('EXACT', 'FINITE', 'UNSUPPORTED')),
    declared_precision      integer,
    native_context          jsonb NOT NULL,
    period_start            date,
    period_end              date,
    period_instant          date,
    missing_state           text NOT NULL CHECK (missing_state IN (
        'VALUE', 'ZERO_PRINTED', 'NIL', 'DASH', 'BLANK', 'NOT_PRESENTED', 'SOURCE_NULL')),
    disclosure              jsonb NOT NULL,
    anchor                  jsonb NOT NULL,
    anchor_key              text NOT NULL,
    -- The fact store's valid time: the period end, or the instant.
    valid_time              date,
    knowledge_time          timestamptz,
    knowledge_time_status   text NOT NULL CHECK (knowledge_time_status IN ('KNOWN', 'UNKNOWN')),
    first_seen_at           timestamptz NOT NULL,
    revision_cause          text NOT NULL CHECK (revision_cause IN (
        'ORIGINAL', 'ISSUER_RESTATEMENT', 'ISSUER_CORRECTION', 'COMPARATIVE_RESTATEMENT',
        'VENDOR_UPDATE', 'PARSER_REEXTRACTION', 'MANUAL_CORRECTION',
        'NORMALISATION_POLICY_CHANGE')),
    UNIQUE (capture_ref_id, extractor_version, anchor_key),
    UNIQUE (id, capture_ref_id),
    CHECK ((declared_precision IS NOT NULL) = (precision_kind = 'FINITE')),
    CHECK (
        num_nonnulls(period_start, period_end, period_instant) = 0
        OR (period_start IS NOT NULL AND period_end IS NOT NULL AND period_instant IS NULL)
        OR (period_start IS NULL AND period_end IS NULL AND period_instant IS NOT NULL)
    )
);

CREATE TABLE eqos.package_statement_evidence (
    id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    package_statement_id    bigint NOT NULL REFERENCES eqos.package_statements (id),
    occurrence_id           bigint NOT NULL REFERENCES eqos.occurrences (id),
    UNIQUE (package_statement_id, occurrence_id)
);

CREATE TABLE eqos.segment_members (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_id       bigint NOT NULL REFERENCES eqos.reporting_entities (id),
    axis            text NOT NULL,
    member          text NOT NULL,
    display_name    text NOT NULL,
    valid_from      date NOT NULL,
    valid_to        date,
    recorded_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE NULLS NOT DISTINCT (entity_id, axis, member, valid_from)
);

CREATE TABLE eqos.segment_member_evidence (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    segment_member_id   bigint NOT NULL REFERENCES eqos.segment_members (id),
    occurrence_id       bigint NOT NULL REFERENCES eqos.occurrences (id),
    UNIQUE (segment_member_id, occurrence_id)
);

CREATE TABLE eqos.acquisition_attempts (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    stage               text NOT NULL CHECK (stage IN ('ACQUISITION', 'EXTRACTION')),
    source_id           text NOT NULL,
    surface             text NOT NULL,
    entity_id           bigint NOT NULL REFERENCES eqos.reporting_entities (id),
    period_end          date NOT NULL,
    basis               text NOT NULL CHECK (basis IN ('CONSOLIDATED', 'STANDALONE')),
    framework           text NOT NULL
        CHECK (framework IN ('IND_AS', 'IFRS', 'US_GAAP', 'UNKNOWN')),
    representation      text NOT NULL CHECK (representation IN ('XBRL', 'PDF')),
    statement_family    text CHECK (statement_family IN (
        'PL', 'BALANCE_SHEET', 'CASH_FLOW', 'SEGMENT', 'SHAREHOLDING', 'DERIVED')),
    package_id          bigint REFERENCES eqos.filing_packages (id),
    capture_ref_id      bigint REFERENCES eqos.capture_refs (id),
    input_sha256        text NOT NULL,
    extractor_version   text NOT NULL,
    outcome             text NOT NULL CHECK (outcome IN (
        'COMPLETE', 'NOT_PUBLISHED', 'PARTIAL', 'FAILED', 'NOT_AUTHORISED',
        'IDENTITY_REJECTED', 'UNSUPPORTED_SCHEMA', 'PARSE_FAILED')),
    reason              text,
    attempted_at        timestamptz NOT NULL DEFAULT now(),
    UNIQUE NULLS NOT DISTINCT (
        stage, source_id, surface, entity_id, period_end, basis, framework, representation,
        statement_family, package_id, capture_ref_id, input_sha256, extractor_version, outcome),
    CHECK (stage <> 'EXTRACTION' OR (capture_ref_id IS NOT NULL AND extractor_version <> '')),
    CHECK (stage <> 'ACQUISITION' OR extractor_version = '')
);

CREATE TABLE eqos.interpretations (
    id                              bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    origin                          text NOT NULL CHECK (origin IN ('DIRECT', 'CONSTRUCTED')),
    occurrence_id                   bigint,
    capture_ref_id                  bigint NOT NULL REFERENCES eqos.capture_refs (id),
    representation                  text NOT NULL CHECK (representation IN ('XBRL', 'PDF')),
    construction_rule_id            text,
    input_digest                    text NOT NULL,
    status                          text NOT NULL CHECK (status IN (
        'MAPPED', 'UNMAPPED', 'PERIOD_AMBIGUOUS', 'INVALID')),
    entity_id                       bigint NOT NULL REFERENCES eqos.reporting_entities (id),
    canonical_id                    text,
    dictionary_version              text NOT NULL,
    period_start                    date,
    period_end                      date,
    period_instant                  date,
    basis                           text NOT NULL CHECK (basis IN ('CONSOLIDATED', 'STANDALONE')),
    framework                       text NOT NULL
        CHECK (framework IN ('IND_AS', 'IFRS', 'US_GAAP', 'UNKNOWN')),
    currency                        text,
    value_kind                      text CHECK (value_kind IN (
        'CURRENCY_AMOUNT', 'PER_SHARE_AMOUNT', 'COUNT', 'PERCENTAGE', 'RATIO', 'DAYS')),
    dimension_set                   jsonb NOT NULL,
    dimension_hash                  text NOT NULL,
    key_digest                      text,
    value                           numeric,
    lower                           numeric,
    upper                           numeric,
    tier                            text NOT NULL CHECK (tier IN (
        'EQUIVALENCE_DEMONSTRATED', 'RELATED_NOT_EQUIVALENT', 'EQUIVALENCE_UNPROVEN')),
    qualification_ref               text,
    mapping_set_version             text NOT NULL,
    mapping_entry_id                text,
    normalisation_policy_version    text NOT NULL,
    extractor_version               text NOT NULL,
    transform_trace                 jsonb NOT NULL,
    reason                          text CHECK (reason IN (
        'UNREADABLE_CELL', 'PRECISION_UNSUPPORTED', 'UNIT_MISMATCH')),
    revision_cause                  text NOT NULL CHECK (revision_cause IN (
        'ORIGINAL', 'ISSUER_RESTATEMENT', 'ISSUER_CORRECTION', 'COMPARATIVE_RESTATEMENT',
        'VENDOR_UPDATE', 'PARSER_REEXTRACTION', 'MANUAL_CORRECTION',
        'NORMALISATION_POLICY_CHANGE')),
    supersedes_interpretation_id    bigint REFERENCES eqos.interpretations (id),
    recorded_at                     timestamptz NOT NULL DEFAULT now(),
    -- revision_cause is deliberately outside the key: a repeat ingest returns the stored row.
    UNIQUE NULLS NOT DISTINCT (
        input_digest, mapping_entry_id, construction_rule_id, mapping_set_version,
        normalisation_policy_version, extractor_version, supersedes_interpretation_id),
    FOREIGN KEY (occurrence_id, capture_ref_id) REFERENCES eqos.occurrences (id, capture_ref_id),
    CHECK ((origin = 'DIRECT') = (occurrence_id IS NOT NULL)),
    CHECK ((origin = 'CONSTRUCTED') = (construction_rule_id IS NOT NULL)),
    CHECK (revision_cause <> 'ORIGINAL' OR supersedes_interpretation_id IS NULL),
    CHECK (
        num_nonnulls(period_start, period_end, period_instant) = 0
        OR (period_start IS NOT NULL AND period_end IS NOT NULL AND period_instant IS NULL)
        OR (period_start IS NULL AND period_end IS NULL AND period_instant IS NOT NULL)
    )
);

CREATE TABLE eqos.interpretation_operands (
    id                          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    interpretation_id           bigint NOT NULL REFERENCES eqos.interpretations (id),
    ordinal                     integer NOT NULL,
    operand_interpretation_id   bigint NOT NULL REFERENCES eqos.interpretations (id),
    UNIQUE (interpretation_id, ordinal)
);

CREATE TABLE eqos.interpretation_condition_evidence (
    id                          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    interpretation_id           bigint NOT NULL REFERENCES eqos.interpretations (id),
    condition_id                text NOT NULL,
    holds                       boolean NOT NULL,
    evidence_interpretation_id  bigint NOT NULL REFERENCES eqos.interpretations (id),
    UNIQUE (interpretation_id, condition_id, evidence_interpretation_id)
);

-- ---------------------------------------------------------------------------
-- Alignment proofs and calculation traces
-- ---------------------------------------------------------------------------

CREATE TABLE eqos.alignment_proofs (
    id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    package_id              bigint NOT NULL REFERENCES eqos.filing_packages (id),
    key_digest              text NOT NULL,
    canonical_id            text NOT NULL,
    rule_id                 text NOT NULL,
    rule_set_version        text NOT NULL,
    xbrl_interpretation_id  bigint NOT NULL REFERENCES eqos.interpretations (id),
    pdf_interpretation_id   bigint NOT NULL REFERENCES eqos.interpretations (id),
    participants_digest     text NOT NULL,
    holds                   boolean NOT NULL,
    UNIQUE (package_id, key_digest, rule_id, rule_set_version, participants_digest)
);

CREATE TABLE eqos.alignment_proof_participants (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    alignment_proof_id  bigint NOT NULL REFERENCES eqos.alignment_proofs (id),
    interpretation_id   bigint NOT NULL REFERENCES eqos.interpretations (id),
    representation      text NOT NULL CHECK (representation IN ('XBRL', 'PDF')),
    UNIQUE (alignment_proof_id, interpretation_id)
);

CREATE TABLE eqos.calculation_traces (
    id                          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    content_sha256              text NOT NULL,
    trace_kind                  text NOT NULL CHECK (trace_kind IN (
        'FORMULA', 'DIMENSIONAL_AGGREGATE', 'AVERAGE', 'PERIOD_DERIVATION')),
    formula_id                  text,
    formula_version             text,
    formula_tier                text CHECK (formula_tier IN (
        'EQUIVALENCE_DEMONSTRATED', 'RELATED_NOT_EQUIVALENT', 'EQUIVALENCE_UNPROVEN')),
    formula_qualification_ref   text,
    rounding_policy_id          text NOT NULL,
    key_digest                  text NOT NULL,
    value_identity              text NOT NULL CHECK (value_identity IN ('REPORTED', 'DERIVED')),
    state                       text NOT NULL CHECK (state IN (
        'OPERAND_UNAVAILABLE', 'OPERAND_INVALID', 'OPERAND_MISSING', 'REVISION_INCOMPATIBLE',
        'UNDEFINED', 'COMPUTED')),
    value                       numeric,
    lower                       numeric,
    upper                       numeric,
    exact_value                 text,
    exact_lower                 text,
    exact_upper                 text,
    effective_tier              text NOT NULL CHECK (effective_tier IN (
        'EQUIVALENCE_DEMONSTRATED', 'RELATED_NOT_EQUIVALENT', 'EQUIVALENCE_UNPROVEN')),
    UNIQUE (content_sha256),
    CHECK (trace_kind <> 'FORMULA' OR (
        formula_id IS NOT NULL AND formula_version IS NOT NULL AND formula_tier IS NOT NULL))
);

CREATE TABLE eqos.calculation_trace_operands (
    id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    calculation_trace_id    bigint NOT NULL REFERENCES eqos.calculation_traces (id),
    ordinal                 integer NOT NULL,
    operand_name            text NOT NULL,
    key_digest              text NOT NULL,
    temporal_role           text NOT NULL CHECK (temporal_role IN (
        'DURATION', 'CLOSING', 'OPENING', 'AVERAGE')),
    interpretation_id       bigint REFERENCES eqos.interpretations (id),
    operand_trace_id        bigint REFERENCES eqos.calculation_traces (id),
    alignment_proof_id      bigint REFERENCES eqos.alignment_proofs (id),
    mapping_entry_id        text,
    qualification_ref       text,
    scoped_tier             text NOT NULL CHECK (scoped_tier IN (
        'EQUIVALENCE_DEMONSTRATED', 'RELATED_NOT_EQUIVALENT', 'EQUIVALENCE_UNPROVEN')),
    selection_source        text NOT NULL CHECK (selection_source IN (
        'PACKAGE_AS_REPORTED', 'PACKAGE_OPENING_DISCLOSURE', 'INSTANT_OWN_SELECTION',
        'HISTORICAL_PACKAGE')),
    source_state            text NOT NULL CHECK (source_state IN (
        'VALUE', 'NO_VALUE', 'UNAVAILABLE', 'INVALID')),
    value                   numeric,
    lower                   numeric,
    upper                   numeric,
    exact_value             text,
    exact_lower             text,
    exact_upper             text,
    UNIQUE (calculation_trace_id, ordinal),
    CHECK (num_nonnulls(interpretation_id, operand_trace_id) <= 1)
);

-- ---------------------------------------------------------------------------
-- Definition sets
-- ---------------------------------------------------------------------------

CREATE TABLE eqos.definition_sets (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    version         text NOT NULL,
    content_sha256  text NOT NULL,
    published_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (version)
);

CREATE TABLE eqos.definition_records (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    definition_set_id   bigint NOT NULL REFERENCES eqos.definition_sets (id),
    record_id           text NOT NULL,
    scope               text NOT NULL CHECK (scope IN ('MAPPING', 'MEASUREMENT', 'FILING')),
    mapping_entry_id    text,
    key_digest          text,
    package_id          bigint REFERENCES eqos.filing_packages (id),
    canonical_id        text NOT NULL,
    operand_name        text,
    evidence_ref        text NOT NULL,
    explained_amount    numeric NOT NULL,
    unit                text NOT NULL CHECK (unit IN (
        'CURRENCY_AMOUNT', 'PER_SHARE_AMOUNT', 'COUNT', 'PERCENTAGE', 'RATIO', 'DAYS')),
    UNIQUE (definition_set_id, record_id),
    CHECK (num_nonnulls(mapping_entry_id, key_digest, package_id) = 1),
    CHECK (
        (scope = 'MAPPING' AND mapping_entry_id IS NOT NULL)
        OR (scope = 'MEASUREMENT' AND key_digest IS NOT NULL)
        OR (scope = 'FILING' AND package_id IS NOT NULL)
    )
);

-- ---------------------------------------------------------------------------
-- Runs (written only inside the publication transaction)
-- ---------------------------------------------------------------------------

CREATE TABLE eqos.runs (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    identity_hash   text NOT NULL,
    cutoff          timestamptz NOT NULL,
    mode            text NOT NULL CHECK (mode IN ('AS_KNOWN', 'RETROSPECTIVE')),
    status          text NOT NULL CHECK (status IN ('COMPLETE', 'INCOMPLETE')),
    code_version    text NOT NULL,
    manifest        jsonb NOT NULL,
    manifest_sha256 text NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (identity_hash)
);

CREATE TABLE eqos.run_versions (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id          bigint NOT NULL REFERENCES eqos.runs (id),
    pin             text NOT NULL CHECK (pin IN (
        'dictionary', 'formula_set', 'mapping_set', 'normalisation_policy', 'extractor_xbrl',
        'extractor_pdf', 'rounding_policy', 'definition_set', 'comparison_policy',
        'alignment_rules')),
    version         text NOT NULL,
    content_sha256  text NOT NULL,
    UNIQUE (run_id, pin)
);

CREATE TABLE eqos.run_inputs (
    id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id                  bigint NOT NULL REFERENCES eqos.runs (id),
    input_kind              text NOT NULL CHECK (input_kind IN (
        'CAPTURE_REF', 'PACKAGE', 'OCCURRENCE', 'INTERPRETATION', 'ATTEMPT', 'ALIGNMENT_PROOF',
        'CALCULATION_TRACE', 'EVIDENCE_INPUT', 'SETTINGS_RECORD', 'BASIS_STATUS',
        'SEGMENT_MEMBER', 'PACKAGE_STATEMENT', 'DEFINITION_SET')),
    disposition             text NOT NULL CHECK (disposition IN (
        'SELECTED', 'SURFACED', 'NOT_SELECTED', 'FAILED_ATTEMPT')),
    capture_ref_id          bigint REFERENCES eqos.capture_refs (id),
    package_id              bigint REFERENCES eqos.filing_packages (id),
    occurrence_id           bigint REFERENCES eqos.occurrences (id),
    interpretation_id       bigint REFERENCES eqos.interpretations (id),
    attempt_id              bigint REFERENCES eqos.acquisition_attempts (id),
    alignment_proof_id      bigint REFERENCES eqos.alignment_proofs (id),
    calculation_trace_id    bigint REFERENCES eqos.calculation_traces (id),
    evidence_input_id       bigint REFERENCES eqos.evidence_inputs (id),
    settings_record_id      bigint REFERENCES eqos.settings_records (id),
    basis_status_id         bigint REFERENCES eqos.entity_basis_status (id),
    segment_member_id       bigint REFERENCES eqos.segment_members (id),
    package_statement_id    bigint REFERENCES eqos.package_statements (id),
    definition_set_id       bigint REFERENCES eqos.definition_sets (id),
    UNIQUE NULLS NOT DISTINCT (
        run_id, capture_ref_id, package_id, occurrence_id, interpretation_id, attempt_id,
        alignment_proof_id, calculation_trace_id, evidence_input_id, settings_record_id,
        basis_status_id, segment_member_id, package_statement_id, definition_set_id),
    CHECK (num_nonnulls(
        capture_ref_id, package_id, occurrence_id, interpretation_id, attempt_id,
        alignment_proof_id, calculation_trace_id, evidence_input_id, settings_record_id,
        basis_status_id, segment_member_id, package_statement_id, definition_set_id) = 1),
    CHECK (CASE input_kind
        WHEN 'CAPTURE_REF' THEN capture_ref_id IS NOT NULL
        WHEN 'PACKAGE' THEN package_id IS NOT NULL
        WHEN 'OCCURRENCE' THEN occurrence_id IS NOT NULL
        WHEN 'INTERPRETATION' THEN interpretation_id IS NOT NULL
        WHEN 'ATTEMPT' THEN attempt_id IS NOT NULL
        WHEN 'ALIGNMENT_PROOF' THEN alignment_proof_id IS NOT NULL
        WHEN 'CALCULATION_TRACE' THEN calculation_trace_id IS NOT NULL
        WHEN 'EVIDENCE_INPUT' THEN evidence_input_id IS NOT NULL
        WHEN 'SETTINGS_RECORD' THEN settings_record_id IS NOT NULL
        WHEN 'BASIS_STATUS' THEN basis_status_id IS NOT NULL
        WHEN 'SEGMENT_MEMBER' THEN segment_member_id IS NOT NULL
        WHEN 'PACKAGE_STATEMENT' THEN package_statement_id IS NOT NULL
        WHEN 'DEFINITION_SET' THEN definition_set_id IS NOT NULL
        ELSE false
    END)
);

CREATE TABLE eqos.results (
    id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id                  bigint NOT NULL REFERENCES eqos.runs (id),
    entity_id               bigint NOT NULL REFERENCES eqos.reporting_entities (id),
    canonical_id            text NOT NULL,
    dictionary_version      text NOT NULL,
    period_start            date,
    period_end              date,
    period_instant          date,
    basis                   text NOT NULL CHECK (basis IN ('CONSOLIDATED', 'STANDALONE')),
    framework               text NOT NULL
        CHECK (framework IN ('IND_AS', 'IFRS', 'US_GAAP', 'UNKNOWN')),
    currency                text,
    value_kind              text NOT NULL CHECK (value_kind IN (
        'CURRENCY_AMOUNT', 'PER_SHARE_AMOUNT', 'COUNT', 'PERCENTAGE', 'RATIO', 'DAYS')),
    dimension_set           jsonb NOT NULL,
    dimension_hash          text NOT NULL,
    key_digest              text NOT NULL,
    value_identity          text NOT NULL CHECK (value_identity IN ('REPORTED', 'DERIVED')),
    applicability           text NOT NULL CHECK (applicability IN ('APPLICABLE', 'NOT_APPLICABLE')),
    applicability_rule_id   text NOT NULL,
    extraction_status       text NOT NULL CHECK (extraction_status IN (
        'NOT_APPLICABLE', 'UNAVAILABLE', 'NOT_COMPARABLE', 'NONE', 'ONE_SIDE_XBRL',
        'ONE_SIDE_PDF', 'AGREE', 'AGREE_UNQUALIFIED', 'TAGGING_DIFFERENCE', 'DISAGREE')),
    extraction_reason       text CHECK (extraction_reason IN (
        'CANONICAL_MISMATCH', 'PERIOD_MISMATCH', 'BASIS_MISMATCH', 'FRAMEWORK_MISMATCH',
        'CURRENCY_MISMATCH', 'KIND_MISMATCH', 'DIMENSION_UNRESOLVED', 'PERIOD_AMBIGUOUS',
        'PRECISION_UNSUPPORTED', 'SIDE_INVALID', 'UNREADABLE_CELL', 'INTERPRETATION_AMBIGUOUS',
        'VENDOR_INTERNAL_CONFLICT', 'OPERAND_INVALID', 'UNDEFINED', 'REVISION_INCOMPATIBLE',
        'ADJUSTMENT_OUT_OF_SCOPE', 'ADJUSTMENT_MISMATCH')),
    corroboration_status    text NOT NULL CHECK (corroboration_status IN (
        'NOT_APPLICABLE', 'UNAVAILABLE', 'NOT_COMPARABLE', 'VENDOR_ONLY', 'NO_SOURCE',
        'FILING_ONLY', 'CONFLICT', 'CORROBORATED', 'AGREES_UNQUALIFIED', 'ANOMALY',
        'DEFINITION_DIFFERENCE')),
    corroboration_reason    text CHECK (corroboration_reason IN (
        'CANONICAL_MISMATCH', 'PERIOD_MISMATCH', 'BASIS_MISMATCH', 'FRAMEWORK_MISMATCH',
        'CURRENCY_MISMATCH', 'KIND_MISMATCH', 'DIMENSION_UNRESOLVED', 'PERIOD_AMBIGUOUS',
        'PRECISION_UNSUPPORTED', 'SIDE_INVALID', 'UNREADABLE_CELL', 'INTERPRETATION_AMBIGUOUS',
        'VENDOR_INTERNAL_CONFLICT', 'OPERAND_INVALID', 'UNDEFINED', 'REVISION_INCOMPATIBLE',
        'ADJUSTMENT_OUT_OF_SCOPE', 'ADJUSTMENT_MISMATCH')),
    UNIQUE (run_id, key_digest, value_identity),
    CHECK (
        (period_start IS NOT NULL AND period_end IS NOT NULL AND period_instant IS NULL)
        OR (period_start IS NULL AND period_end IS NULL AND period_instant IS NOT NULL)
    )
);

-- Per-source values live apart from outcomes so a later purge (D9) can delete vendor values
-- without touching any outcome (ledger spec §6 item 4).
CREATE TABLE eqos.result_source_values (
    id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    result_id               bigint NOT NULL REFERENCES eqos.results (id),
    source_role             text NOT NULL,
    representation          text NOT NULL CHECK (representation IN ('XBRL', 'PDF')),
    source_state            text NOT NULL CHECK (source_state IN (
        'VALUE', 'NO_VALUE', 'UNAVAILABLE', 'INVALID')),
    reason                  text,
    value                   numeric,
    lower                   numeric,
    upper                   numeric,
    interpretation_id       bigint REFERENCES eqos.interpretations (id),
    calculation_trace_id    bigint REFERENCES eqos.calculation_traces (id),
    attempt_id              bigint REFERENCES eqos.acquisition_attempts (id),
    calculation_state       text CHECK (calculation_state IN (
        'OPERAND_UNAVAILABLE', 'OPERAND_INVALID', 'OPERAND_MISSING', 'REVISION_INCOMPATIBLE',
        'UNDEFINED', 'COMPUTED')),
    UNIQUE (result_id, source_role, representation),
    UNIQUE (id, result_id),
    CHECK (num_nonnulls(interpretation_id, calculation_trace_id) <= 1)
);

CREATE TABLE eqos.result_surfaced_restatements (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    result_id           bigint NOT NULL REFERENCES eqos.results (id),
    interpretation_id   bigint NOT NULL REFERENCES eqos.interpretations (id),
    UNIQUE (result_id, interpretation_id)
);

CREATE TABLE eqos.pair_outcomes (
    id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    result_id               bigint NOT NULL REFERENCES eqos.results (id),
    pair_kind               text NOT NULL CHECK (pair_kind IN ('EXTRACTION', 'REPORTED_VS_DERIVED')),
    left_value_id           bigint NOT NULL,
    right_value_id          bigint NOT NULL,
    outcome                 text NOT NULL CHECK (outcome IN (
        'NOT_COMPARABLE', 'AGREE', 'AGREE_UNQUALIFIED', 'DEFINITION_DIFFERENCE', 'MISMATCH',
        'ANOMALY')),
    reason                  text CHECK (reason IN (
        'CANONICAL_MISMATCH', 'PERIOD_MISMATCH', 'BASIS_MISMATCH', 'FRAMEWORK_MISMATCH',
        'CURRENCY_MISMATCH', 'KIND_MISMATCH', 'DIMENSION_UNRESOLVED', 'PERIOD_AMBIGUOUS',
        'PRECISION_UNSUPPORTED', 'SIDE_INVALID', 'UNREADABLE_CELL', 'INTERPRETATION_AMBIGUOUS',
        'VENDOR_INTERNAL_CONFLICT', 'OPERAND_INVALID', 'UNDEFINED', 'REVISION_INCOMPATIBLE',
        'ADJUSTMENT_OUT_OF_SCOPE', 'ADJUSTMENT_MISMATCH')),
    triage                  text CHECK (triage IN ('STRUCTURAL', 'MAGNITUDE', 'NOISE')),
    difference              numeric,
    interval_gap            numeric,
    definition_record_id    bigint REFERENCES eqos.definition_records (id),
    UNIQUE (result_id, pair_kind, left_value_id, right_value_id),
    -- Both sides must be source values of this same result.
    FOREIGN KEY (left_value_id, result_id) REFERENCES eqos.result_source_values (id, result_id),
    FOREIGN KEY (right_value_id, result_id) REFERENCES eqos.result_source_values (id, result_id)
);

CREATE TABLE eqos.pair_adjustments (
    id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pair_outcome_id         bigint NOT NULL REFERENCES eqos.pair_outcomes (id),
    definition_record_id    bigint NOT NULL REFERENCES eqos.definition_records (id),
    operand_name            text NOT NULL,
    representation          text NOT NULL CHECK (representation IN ('XBRL', 'PDF')),
    direction               integer NOT NULL CHECK (direction IN (-1, 1)),
    amount                  numeric NOT NULL,
    UNIQUE (pair_outcome_id, definition_record_id, operand_name)
);

-- ---------------------------------------------------------------------------
-- Cross-row rules a CHECK cannot express
-- ---------------------------------------------------------------------------

-- A constructed interpretation's operands come from its own capture.
CREATE FUNCTION eqos.check_operand_capture() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM eqos.interpretations parent
        JOIN eqos.interpretations operand ON operand.id = NEW.operand_interpretation_id
        WHERE parent.id = NEW.interpretation_id
          AND parent.capture_ref_id = operand.capture_ref_id
    ) THEN
        RAISE EXCEPTION 'operand % does not share the capture of interpretation %',
            NEW.operand_interpretation_id, NEW.interpretation_id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER check_operand_capture
    BEFORE INSERT ON eqos.interpretation_operands
    FOR EACH ROW EXECUTE FUNCTION eqos.check_operand_capture();

-- ---------------------------------------------------------------------------
-- Immutability and grants
-- ---------------------------------------------------------------------------

CREATE FUNCTION eqos.reject_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'eqos evidence is immutable: % on %.% refused',
        TG_OP, TG_TABLE_SCHEMA, TG_TABLE_NAME;
END;
$$;

DO $$
DECLARE
    table_name text;
BEGIN
    FOR table_name IN SELECT tablename FROM pg_tables WHERE schemaname = 'eqos' LOOP
        EXECUTE format(
            'CREATE TRIGGER reject_row_mutation BEFORE UPDATE OR DELETE ON eqos.%I '
            'FOR EACH ROW EXECUTE FUNCTION eqos.reject_mutation()', table_name);
        EXECUTE format(
            'CREATE TRIGGER reject_truncate BEFORE TRUNCATE ON eqos.%I '
            'FOR EACH STATEMENT EXECUTE FUNCTION eqos.reject_mutation()', table_name);
    END LOOP;
END;
$$;

GRANT USAGE ON SCHEMA eqos TO eqos_runtime;
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA eqos TO eqos_runtime;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA eqos TO eqos_runtime;
