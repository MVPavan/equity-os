-- D3 Task 1: the report ledger (ledger spec §1; plan D3, decisions D1-D4, D8, D11). Every table
-- is append-only. Digests, decider and recorded times are set here, never by callers.
-- 0001--0011 are immutable. Group roles eqos_panel and eqos_owner exist before this runs
-- (ensure_group_roles).

CREATE TABLE eqos.reports (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_id   bigint NOT NULL REFERENCES eqos.reporting_entities (id),
    period      text NOT NULL CHECK (period <> ''),
    kind        text NOT NULL CHECK (kind IN ('BOOTSTRAP_THESIS', 'EARNINGS_UPDATE')),
    UNIQUE (entity_id, period, kind)
);

-- D4: each report's versions form one linear chain (one root, one successor, an earlier
-- version of the same report as predecessor).
CREATE TABLE eqos.report_versions (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    report_id           bigint NOT NULL REFERENCES eqos.reports (id),
    predecessor_id      bigint UNIQUE,
    author              text NOT NULL CHECK (author <> ''),
    knowledge_cutoff    timestamptz NOT NULL,
    pinned_run_ids      bigint[] NOT NULL,
    content_hash        text NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    created_at          timestamptz NOT NULL,
    created_xid         bigint NOT NULL,
    UNIQUE (id, report_id),
    CHECK (predecessor_id < id),
    FOREIGN KEY (predecessor_id, report_id) REFERENCES eqos.report_versions (id, report_id)
);
CREATE UNIQUE INDEX report_versions_one_root ON eqos.report_versions (report_id)
    WHERE predecessor_id IS NULL;

CREATE TABLE eqos.import_sources (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    version_id  bigint NOT NULL REFERENCES eqos.report_versions (id),
    source_path text NOT NULL CHECK (source_path <> ''),
    body        bytea NOT NULL,
    sha256      text NOT NULL GENERATED ALWAYS AS (encode(sha256(body), 'hex')) STORED,
    UNIQUE (version_id, source_path)
);

CREATE TABLE eqos.report_sections (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    version_id  bigint NOT NULL REFERENCES eqos.report_versions (id),
    ordinal     integer NOT NULL CHECK (ordinal >= 0),
    section_key text NOT NULL CHECK (section_key <> ''),
    body        text NOT NULL,
    sha256      text NOT NULL CHECK (sha256 = encode(sha256(convert_to(body, 'UTF8')), 'hex')),
    UNIQUE (version_id, ordinal),
    UNIQUE (version_id, section_key),
    UNIQUE (id, version_id)
);

-- One citation kind per claim; each kind's CHECK names the columns it may and must set. An
-- unresolved claim (imports only, refused at SUBMIT) carries no cited record.
CREATE TABLE eqos.numeric_claims (
    id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    version_id              bigint NOT NULL,
    section_id              bigint NOT NULL,
    claim_key               text NOT NULL CHECK (claim_key <> ''),
    citation_kind           text NOT NULL CHECK (citation_kind IN (
        'FIGURE', 'CALCULATION', 'SOURCE_QUOTE', 'COMPARISON', 'POLICY')),
    key_digest text, measurement_key jsonb,
    value_kind              text NOT NULL CHECK (value_kind IN (
        'CURRENCY_AMOUNT', 'PER_SHARE_AMOUNT', 'COUNT', 'PERCENTAGE', 'RATIO', 'DAYS')),
    unit text, currency text, scale integer,
    value numeric, lower_bound numeric, upper_bound numeric, horizon text,
    qualifiers              text[] NOT NULL,
    precision               integer NOT NULL CHECK (precision >= 0),
    rounding                text NOT NULL CHECK (rounding IN ('ROUND_HALF_UP', 'ROUND_HALF_EVEN')),
    epistemic_class         text NOT NULL CHECK (epistemic_class IN (
        'observed', 'computed', 'inferred', 'forecast', 'opinion')),
    metric text, metric_label text, scope text, constant_currency boolean,  -- guidance contract
    unresolved              boolean NOT NULL,
    source_sha256 text, fact_origin text, fact_origin_id bigint,
    interpretation_id       bigint REFERENCES eqos.interpretations (id),
    run_id                  bigint REFERENCES eqos.runs (id),
    calculation_trace_id    bigint REFERENCES eqos.calculation_traces (id),
    capture_ref_id          bigint REFERENCES eqos.capture_refs (id),
    anchor text, quote text,
    pair_outcome_id         bigint REFERENCES eqos.pair_outcomes (id),
    policy_decision_id      bigint,
    UNIQUE (version_id, claim_key),
    UNIQUE (id, version_id),
    FOREIGN KEY (section_id, version_id) REFERENCES eqos.report_sections (id, version_id),
    FOREIGN KEY (fact_origin, fact_origin_id) REFERENCES eqos.fact_rows (origin, origin_id),
    CHECK ((key_digest IS NULL) = (measurement_key IS NULL)),
    CHECK ((measurement_key IS NULL) = (citation_kind IN ('SOURCE_QUOTE', 'POLICY'))),
    CHECK ((lower_bound IS NULL) = (upper_bound IS NULL)),
    CHECK ((value IS NULL) = (lower_bound IS NOT NULL)),
    CHECK (lower_bound <= upper_bound),
    CHECK (citation_kind = 'SOURCE_QUOTE'
        OR num_nonnulls(metric, metric_label, scope, constant_currency) = 0),
    CHECK (citation_kind <> 'FIGURE' OR (
        num_nonnulls(calculation_trace_id, capture_ref_id, anchor, quote, pair_outcome_id,
                     policy_decision_id) = 0
        AND (fact_origin IS NULL) = (fact_origin_id IS NULL)
        AND (interpretation_id IS NULL) = (run_id IS NULL)
        AND num_nonnulls(fact_origin_id, interpretation_id) = (NOT unresolved)::int)),
    CHECK (citation_kind <> 'CALCULATION' OR (
        num_nonnulls(fact_origin, fact_origin_id, interpretation_id, run_id, capture_ref_id,
                     anchor, quote, pair_outcome_id, policy_decision_id) = 0
        AND num_nonnulls(calculation_trace_id) = (NOT unresolved)::int)),
    CHECK (citation_kind <> 'SOURCE_QUOTE' OR (
        num_nonnulls(fact_origin, fact_origin_id, interpretation_id, run_id,
                     calculation_trace_id, pair_outcome_id, policy_decision_id) = 0
        AND anchor IS NOT NULL AND quote IS NOT NULL
        AND num_nonnulls(capture_ref_id) = (NOT unresolved)::int)),
    CHECK (citation_kind <> 'COMPARISON' OR (
        num_nonnulls(fact_origin, fact_origin_id, interpretation_id, calculation_trace_id,
                     capture_ref_id, anchor, quote, policy_decision_id) = 0
        AND num_nonnulls(run_id, pair_outcome_id) = 2 * (NOT unresolved)::int)),
    -- A null policy decision is a self-citation, which only an import may make (D12, G9).
    CHECK (citation_kind <> 'POLICY' OR (
        num_nonnulls(fact_origin, fact_origin_id, interpretation_id, run_id,
                     calculation_trace_id, capture_ref_id, anchor, quote, pair_outcome_id) = 0
        AND NOT unresolved AND value IS NOT NULL))
);

CREATE TABLE eqos.validations (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    version_id          bigint NOT NULL REFERENCES eqos.report_versions (id),
    checker_version     text NOT NULL CHECK (checker_version <> ''),
    mode                text NOT NULL CHECK (mode IN ('AS_KNOWN', 'RETROSPECTIVE')),
    overlay_position    timestamptz NOT NULL,
    pinned_input_sha256 text NOT NULL CHECK (pinned_input_sha256 ~ '^[0-9a-f]{64}$'),
    sealed_digest       text NOT NULL,
    recorded_at         timestamptz NOT NULL,
    created_xid         bigint NOT NULL,
    UNIQUE (id, version_id)
);

-- A row with no claim is a version-level state.
CREATE TABLE eqos.validation_claim_states (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    validation_id   bigint NOT NULL,
    version_id      bigint NOT NULL,
    claim_id        bigint,
    state           text NOT NULL CHECK (state IN ('UNRESOLVED', 'POST_CUTOFF',
        'UNIT_MISMATCH', 'KEY_MISMATCH', 'VALUE_MISMATCH', 'QUOTE_NOT_FOUND',
        'QUOTE_MEANING_MISMATCH', 'MATCH_UNTRUSTED', 'MATCH',
        'UNREGISTERED_NUMBER', 'UNLABELLED_PROSE', 'UNCITED_PROSE')),
    UNIQUE (validation_id, claim_id),
    CHECK ((claim_id IS NULL)
        = (state IN ('UNREGISTERED_NUMBER', 'UNLABELLED_PROSE', 'UNCITED_PROSE'))),
    FOREIGN KEY (validation_id, version_id) REFERENCES eqos.validations (id, version_id),
    FOREIGN KEY (claim_id, version_id) REFERENCES eqos.numeric_claims (id, version_id)
);

CREATE TABLE eqos.qa_records (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    version_id  bigint NOT NULL REFERENCES eqos.report_versions (id),
    gate        text NOT NULL CHECK (gate <> ''),
    result      jsonb NOT NULL,
    recorded_at timestamptz NOT NULL
);

CREATE TABLE eqos.decisions (
    id                          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    subject_kind                text NOT NULL CHECK (subject_kind IN (
        'REPORT_VERSION', 'REPORT', 'DISPOSITION_PROPOSAL', 'INTERPRETATION')),
    subject_id                  bigint NOT NULL,
    kind                        text NOT NULL CHECK (kind IN ('SUBMIT', 'IMPORT_SEAL',
        'IMPORTED_APPROVAL', 'APPROVE', 'REQUEST_CHANGES', 'REJECT', 'WITHDRAW', 'ACCEPT',
        'SET_POLICY')),
    sequence                    integer NOT NULL,
    predecessor_id              bigint UNIQUE REFERENCES eqos.decisions (id),
    sealed_digest               text,
    validation_id               bigint REFERENCES eqos.validations (id),
    panel_review_id             bigint,
    original_approval_sha256 text, ruling text, decided_on date,
    policy_key text, policy_value numeric, policy_unit text,
    decider                     text NOT NULL CHECK (decider IN ('RUNTIME', 'PANEL', 'OWNER')),
    recorded_at                 timestamptz NOT NULL,
    created_xid                 bigint NOT NULL,
    decision_sha256             text NOT NULL,
    UNIQUE (subject_kind, subject_id, sequence),
    CHECK ((sequence = 1) = (predecessor_id IS NULL)),
    CHECK ((validation_id IS NOT NULL) = (subject_kind = 'REPORT_VERSION' AND kind = 'APPROVE')),
    CHECK ((original_approval_sha256 IS NOT NULL) = (kind = 'IMPORTED_APPROVAL')),
    CHECK ((decided_on IS NOT NULL) = (kind = 'IMPORTED_APPROVAL')),
    CHECK (num_nonnulls(policy_key, policy_value, policy_unit)
        = CASE WHEN kind = 'SET_POLICY' THEN 3 ELSE 0 END)
);
ALTER TABLE eqos.numeric_claims
    ADD FOREIGN KEY (policy_decision_id) REFERENCES eqos.decisions (id);

-- D8: legacy first-seen times, from the hash-pinned retrieval manifest.
CREATE TABLE eqos.legacy_acquisitions (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    blob_sha256     text NOT NULL CHECK (blob_sha256 ~ '^[0-9a-f]{64}$'),
    retrieved_at    timestamptz NOT NULL,
    manifest_sha256 text NOT NULL CHECK (manifest_sha256 ~ '^[0-9a-f]{64}$'),
    entry_sha256    text NOT NULL CHECK (entry_sha256 ~ '^[0-9a-f]{64}$'),
    recorded_at     timestamptz NOT NULL,
    UNIQUE (manifest_sha256, entry_sha256)
);

-- D1 encoding and digests. Each field is 'N' (null) or 'S' || utf8 length || ':' || text, so
-- separators inside a value, null versus empty and multi-byte text cannot collide.
-- Timestamps are UTC ISO-8601 with microseconds and 'Z', dates YYYY-MM-DD, JSON is walked
-- (never jsonb::text); every other field is cast with ::text.

CREATE FUNCTION eqos.enc(value text) RETURNS text LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE WHEN value IS NULL THEN 'N'
                ELSE 'S' || octet_length(convert_to(value, 'UTF8')) || ':' || value END
$$;

CREATE FUNCTION eqos.enc(value timestamptz) RETURNS text LANGUAGE sql STABLE AS $$
    SELECT eqos.enc(to_char(value AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'))
$$;

CREATE FUNCTION eqos.enc(value date) RETURNS text LANGUAGE sql STABLE AS $$
    SELECT eqos.enc(to_char(value, 'YYYY-MM-DD'))
$$;

CREATE FUNCTION eqos.enc(value jsonb) RETURNS text LANGUAGE plpgsql IMMUTABLE AS $$
BEGIN
    RETURN CASE jsonb_typeof(value)
        WHEN 'object' THEN 'O' || (SELECT count(*) || ':' || coalesce(string_agg(
            eqos.enc(key) || eqos.enc(item), '' ORDER BY key COLLATE "C"), '')
            FROM jsonb_each(value) AS member (key, item))
        WHEN 'array' THEN 'A' || (SELECT count(*) || ':' || coalesce(string_agg(
            eqos.enc(item), '' ORDER BY position), '')
            FROM jsonb_array_elements(value) WITH ORDINALITY AS member (item, position))
        ELSE eqos.enc(jsonb_typeof(value)) || eqos.enc(value #>> '{}') END;
END;
$$;

-- The version's content in key order: row, sections, claims with citations, import sources.
CREATE FUNCTION eqos.version_sealed_digest(version bigint) RETURNS text LANGUAGE sql STABLE AS $$
    SELECT encode(sha256(convert_to(
        (SELECT eqos.enc(v.id::text) || eqos.enc(v.report_id::text)
             || eqos.enc(v.predecessor_id::text) || eqos.enc(v.author)
             || eqos.enc(v.knowledge_cutoff) || eqos.enc(v.pinned_run_ids::text)
             || eqos.enc(v.content_hash) || eqos.enc(v.created_at)
         FROM eqos.report_versions v WHERE v.id = version)
        || (SELECT eqos.enc(count(*)::text) || coalesce(string_agg(
                eqos.enc(s.ordinal::text) || eqos.enc(s.section_key) || eqos.enc(s.body),
                '' ORDER BY s.ordinal), '')
            FROM eqos.report_sections s WHERE s.version_id = version)
        || (SELECT eqos.enc(count(*)::text) || coalesce(string_agg(
                eqos.enc(c.claim_key) || eqos.enc(c.section_id::text)
                || eqos.enc(c.citation_kind) || eqos.enc(c.key_digest)
                || eqos.enc(c.measurement_key) || eqos.enc(c.value_kind) || eqos.enc(c.unit)
                || eqos.enc(c.currency) || eqos.enc(c.scale::text) || eqos.enc(c.value::text)
                || eqos.enc(c.lower_bound::text) || eqos.enc(c.upper_bound::text)
                || eqos.enc(c.horizon) || eqos.enc(c.qualifiers::text)
                || eqos.enc(c.precision::text) || eqos.enc(c.rounding)
                || eqos.enc(c.epistemic_class) || eqos.enc(c.metric) || eqos.enc(c.metric_label)
                || eqos.enc(c.scope) || eqos.enc(c.constant_currency::text)
                || eqos.enc(c.unresolved::text) || eqos.enc(c.source_sha256)
                || eqos.enc(c.fact_origin) || eqos.enc(c.fact_origin_id::text)
                || eqos.enc(c.interpretation_id::text) || eqos.enc(c.run_id::text)
                || eqos.enc(c.calculation_trace_id::text) || eqos.enc(c.capture_ref_id::text)
                || eqos.enc(c.anchor) || eqos.enc(c.quote) || eqos.enc(c.pair_outcome_id::text)
                || eqos.enc(c.policy_decision_id::text),
                '' ORDER BY c.claim_key COLLATE "C"), '')
            FROM eqos.numeric_claims c WHERE c.version_id = version)
        || (SELECT eqos.enc(count(*)::text) || coalesce(string_agg(
                eqos.enc(i.source_path) || eqos.enc(i.sha256),
                '' ORDER BY i.source_path COLLATE "C"), '')
            FROM eqos.import_sources i WHERE i.version_id = version),
        'UTF8')), 'hex')
$$;

-- True when a descendant version's chain holds APPROVE.
CREATE FUNCTION eqos.version_superseded(version bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
    WITH RECURSIVE descendants (id) AS (
        SELECT id FROM eqos.report_versions WHERE predecessor_id = version
        UNION ALL
        SELECT v.id FROM eqos.report_versions v JOIN descendants d ON v.predecessor_id = d.id
    )
    SELECT EXISTS (SELECT 1 FROM eqos.decisions
                   WHERE subject_kind = 'REPORT_VERSION' AND kind = 'APPROVE'
                     AND subject_id IN (SELECT id FROM descendants))
$$;

-- D4: one transaction-level lock per subject, taken before the first store_now().
CREATE FUNCTION eqos.lock_subject(subject_kind text, subject_id bigint) RETURNS void
LANGUAGE sql AS $$
    SELECT pg_advisory_xact_lock(hashtextextended(subject_kind || ':' || subject_id, 4215031012))
$$;

-- Triggers. Each takes the subject lock before its first store_now() (D4).
CREATE FUNCTION eqos.record_version() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, eqos AS $$ BEGIN
    PERFORM eqos.lock_subject('REPORT_VERSION', NEW.id);
    NEW.created_at := eqos.store_now();
    NEW.created_xid := txid_current();
    RETURN NEW;
END $$;

-- Content inserts after SUBMIT or IMPORT_SEAL are refused.
CREATE FUNCTION eqos.check_version_seal() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, eqos AS $$
BEGIN
    PERFORM eqos.lock_subject('REPORT_VERSION', NEW.version_id);
    IF EXISTS (SELECT 1 FROM eqos.decisions
               WHERE subject_kind = 'REPORT_VERSION' AND subject_id = NEW.version_id
                 AND kind IN ('SUBMIT', 'IMPORT_SEAL')) THEN
        RAISE EXCEPTION 'report version % is sealed', NEW.version_id USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;

CREATE FUNCTION eqos.record_validation() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, eqos AS $$
BEGIN
    PERFORM eqos.lock_subject('REPORT_VERSION', NEW.version_id);
    IF NEW.sealed_digest IS DISTINCT FROM eqos.version_sealed_digest(NEW.version_id) THEN
        RAISE EXCEPTION 'validation digest does not match version %', NEW.version_id
            USING ERRCODE = '23514';
    END IF;
    NEW.recorded_at := eqos.store_now();
    NEW.created_xid := txid_current();
    RETURN NEW;
END $$;

-- A validation's states are sealed with it: inserts only in its creating transaction.
CREATE FUNCTION eqos.check_validation_state() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, eqos AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM eqos.validations
                   WHERE id = NEW.validation_id AND created_xid = txid_current()) THEN
        RAISE EXCEPTION 'validation states are sealed with the validation transaction'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;

CREATE FUNCTION eqos.record_ledger_time() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, eqos AS $$ BEGIN NEW.recorded_at := eqos.store_now(); RETURN NEW; END $$;

-- The decision chain (D3, D4): decider from the session role, the legal predecessor for each
-- kind and role, the recomputed sealed digest, the approval binding, the store-clock time and
-- the chain digest over the row fields in column order, then the predecessor digest.
CREATE FUNCTION eqos.check_decision() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, eqos AS $$
DECLARE
    head        eqos.decisions;
    version     eqos.report_versions;
    latest      eqos.validations;
    imported    boolean;
    legal       boolean;
BEGIN
    NEW.decider := CASE current_user WHEN 'eqos_runtime' THEN 'RUNTIME'
                                     WHEN 'eqos_panel' THEN 'PANEL'
                                     WHEN 'eqos_owner' THEN 'OWNER' END;
    IF NEW.decider IS NULL THEN
        RAISE EXCEPTION 'role % may not decide', current_user USING ERRCODE = '42501';
    END IF;
    PERFORM eqos.lock_subject(NEW.subject_kind, NEW.subject_id);
    SELECT * INTO head FROM eqos.decisions
        WHERE subject_kind = NEW.subject_kind AND subject_id = NEW.subject_id
        ORDER BY sequence DESC LIMIT 1;
    IF NEW.predecessor_id IS DISTINCT FROM head.id THEN
        RAISE EXCEPTION 'stale head: % % is at decision %', NEW.subject_kind, NEW.subject_id,
            head.id USING ERRCODE = '23514';
    END IF;
    NEW.sequence := coalesce(head.sequence, 0) + 1;
    IF (NEW.decider = 'OWNER' OR NEW.kind = 'IMPORTED_APPROVAL')
       AND coalesce(NEW.ruling, '') = '' THEN
        RAISE EXCEPTION '% needs the verbatim ruling', NEW.kind USING ERRCODE = '23514';
    END IF;

    IF NEW.subject_kind = 'REPORT' THEN
        legal := NEW.kind = 'SET_POLICY' AND NEW.decider = 'OWNER' AND NEW.sealed_digest IS NULL
                 AND EXISTS (SELECT 1 FROM eqos.reports WHERE id = NEW.subject_id);
    ELSIF NEW.subject_kind = 'REPORT_VERSION' THEN
        SELECT * INTO version FROM eqos.report_versions WHERE id = NEW.subject_id;
        imported := EXISTS (SELECT 1 FROM eqos.import_sources WHERE version_id = NEW.subject_id);
        legal := version.id IS NOT NULL AND CASE
            WHEN NEW.kind = 'SUBMIT' THEN
                NEW.decider = 'RUNTIME' AND head.id IS NULL AND NOT imported
                AND NOT EXISTS (SELECT 1 FROM eqos.numeric_claims
                                WHERE version_id = NEW.subject_id AND (unresolved
                                   OR (citation_kind = 'POLICY' AND policy_decision_id IS NULL)))
            WHEN NEW.kind = 'IMPORT_SEAL' THEN
                NEW.decider = 'PANEL' AND head.id IS NULL AND imported
                AND version.created_xid = txid_current()
            WHEN NEW.kind = 'IMPORTED_APPROVAL' THEN
                NEW.decider = 'PANEL' AND head.kind = 'IMPORT_SEAL'
                AND head.created_xid = txid_current()
            WHEN NEW.kind IN ('APPROVE', 'REQUEST_CHANGES', 'REJECT') THEN
                NEW.decider IN ('PANEL', 'OWNER') AND head.kind = 'SUBMIT'
            WHEN NEW.kind = 'WITHDRAW' THEN
                NEW.decider = 'OWNER' AND (head.kind IN ('APPROVE', 'IMPORTED_APPROVAL')
                    OR (head.kind = 'IMPORT_SEAL' AND eqos.version_superseded(NEW.subject_id)))
            ELSE false END;
    END IF;
    IF NOT coalesce(legal, false) THEN
        RAISE EXCEPTION 'illegal decision: % by % on % % after %', NEW.kind, NEW.decider,
            NEW.subject_kind, NEW.subject_id, coalesce(head.kind, 'nothing')
            USING ERRCODE = '23514';
    END IF;

    IF NEW.subject_kind = 'REPORT_VERSION' THEN
        IF NEW.sealed_digest IS DISTINCT FROM eqos.version_sealed_digest(NEW.subject_id) THEN
            RAISE EXCEPTION 'sealed digest does not match version %', NEW.subject_id
                USING ERRCODE = '23514';
        END IF;
        IF NEW.kind = 'APPROVE' THEN
            SELECT * INTO latest FROM eqos.validations
                WHERE version_id = NEW.subject_id ORDER BY id DESC LIMIT 1;
            IF latest.id IS DISTINCT FROM NEW.validation_id OR latest.mode <> 'AS_KNOWN'
               OR latest.sealed_digest <> NEW.sealed_digest
               OR EXISTS (SELECT 1 FROM eqos.validation_claim_states
                          WHERE validation_id = latest.id
                            AND (claim_id IS NULL OR state NOT IN ('MATCH', 'MATCH_UNTRUSTED')))
               OR EXISTS (SELECT 1 FROM eqos.numeric_claims c
                          WHERE c.version_id = NEW.subject_id AND NOT EXISTS (
                              SELECT 1 FROM eqos.validation_claim_states s
                              WHERE s.validation_id = latest.id AND s.claim_id = c.id)) THEN
                RAISE EXCEPTION 'approval must bind the latest passing AS_KNOWN validation of %',
                    NEW.subject_id USING ERRCODE = '23514';
            END IF;
        END IF;
    END IF;

    NEW.recorded_at := eqos.store_now();
    NEW.created_xid := txid_current();
    NEW.decision_sha256 := encode(sha256(convert_to(
        eqos.enc(NEW.id::text) || eqos.enc(NEW.subject_kind) || eqos.enc(NEW.subject_id::text)
        || eqos.enc(NEW.kind) || eqos.enc(NEW.sequence::text)
        || eqos.enc(NEW.predecessor_id::text) || eqos.enc(NEW.sealed_digest)
        || eqos.enc(NEW.validation_id::text) || eqos.enc(NEW.panel_review_id::text)
        || eqos.enc(NEW.original_approval_sha256) || eqos.enc(NEW.ruling)
        || eqos.enc(NEW.decided_on) || eqos.enc(NEW.policy_key)
        || eqos.enc(NEW.policy_value::text) || eqos.enc(NEW.policy_unit)
        || eqos.enc(NEW.decider) || eqos.enc(NEW.recorded_at)
        || eqos.enc(head.decision_sha256), 'UTF8')), 'hex');
    RETURN NEW;
END $$;

-- D11: queue dispositions are owner (or, from 0013, panel) decisions.
CREATE FUNCTION eqos.refuse_runtime_disposition() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
    IF current_user = 'eqos_runtime' THEN
        RAISE EXCEPTION 'the runtime role may not dispose a queue item' USING ERRCODE = '42501';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER refuse_runtime_disposition BEFORE INSERT ON eqos.queue_dispositions
    FOR EACH ROW EXECUTE FUNCTION eqos.refuse_runtime_disposition();

CREATE TRIGGER record_version BEFORE INSERT ON eqos.report_versions
    FOR EACH ROW EXECUTE FUNCTION eqos.record_version();
CREATE TRIGGER record_validation BEFORE INSERT ON eqos.validations
    FOR EACH ROW EXECUTE FUNCTION eqos.record_validation();
CREATE TRIGGER check_validation_state BEFORE INSERT ON eqos.validation_claim_states
    FOR EACH ROW EXECUTE FUNCTION eqos.check_validation_state();
CREATE TRIGGER record_ledger_time BEFORE INSERT ON eqos.qa_records
    FOR EACH ROW EXECUTE FUNCTION eqos.record_ledger_time();
CREATE TRIGGER record_ledger_time BEFORE INSERT ON eqos.legacy_acquisitions
    FOR EACH ROW EXECUTE FUNCTION eqos.record_ledger_time();
CREATE TRIGGER check_decision BEFORE INSERT ON eqos.decisions
    FOR EACH ROW EXECUTE FUNCTION eqos.check_decision();

-- Immutability and the D2 privilege matrix.
DO $$
DECLARE
    name text;
BEGIN
    FOREACH name IN ARRAY ARRAY['reports', 'report_versions', 'import_sources',
        'report_sections', 'numeric_claims', 'validations', 'validation_claim_states',
        'qa_records', 'decisions', 'legacy_acquisitions'] LOOP
        EXECUTE format('CREATE TRIGGER reject_row_mutation BEFORE UPDATE OR DELETE ON eqos.%I '
            'FOR EACH ROW EXECUTE FUNCTION eqos.reject_mutation()', name);
        EXECUTE format('CREATE TRIGGER reject_truncate BEFORE TRUNCATE ON eqos.%I '
            'FOR EACH STATEMENT EXECUTE FUNCTION eqos.reject_mutation()', name);
    END LOOP;
    FOREACH name IN ARRAY ARRAY['import_sources', 'report_sections', 'numeric_claims'] LOOP
        EXECUTE format('CREATE TRIGGER check_version_seal BEFORE INSERT ON eqos.%I '
            'FOR EACH ROW EXECUTE FUNCTION eqos.check_version_seal()', name);
    END LOOP;
END $$;

GRANT USAGE ON SCHEMA eqos TO eqos_panel, eqos_owner;
GRANT EXECUTE ON FUNCTION eqos.store_now(), eqos.lock_queue() TO eqos_panel, eqos_owner;
GRANT SELECT ON ALL TABLES IN SCHEMA eqos TO eqos_panel, eqos_owner;
GRANT SELECT, INSERT ON eqos.reports, eqos.report_versions, eqos.import_sources,
    eqos.report_sections, eqos.numeric_claims, eqos.validations, eqos.validation_claim_states,
    eqos.decisions TO eqos_runtime, eqos_panel;
GRANT SELECT ON eqos.qa_records, eqos.legacy_acquisitions TO eqos_runtime;
GRANT INSERT ON eqos.qa_records, eqos.legacy_acquisitions TO eqos_panel;
GRANT INSERT ON eqos.decisions, eqos.queue_dispositions TO eqos_owner;
GRANT INSERT ON eqos.queue_dispositions TO eqos_panel;
GRANT USAGE ON SEQUENCE eqos.reports_id_seq, eqos.report_versions_id_seq,
    eqos.import_sources_id_seq, eqos.report_sections_id_seq, eqos.numeric_claims_id_seq,
    eqos.validations_id_seq, eqos.validation_claim_states_id_seq, eqos.decisions_id_seq
    TO eqos_runtime, eqos_panel;
GRANT USAGE ON SEQUENCE eqos.qa_records_id_seq, eqos.legacy_acquisitions_id_seq TO eqos_panel;
GRANT USAGE ON SEQUENCE eqos.decisions_id_seq TO eqos_owner;
GRANT USAGE ON SEQUENCE eqos.queue_dispositions_id_seq TO eqos_panel, eqos_owner;
