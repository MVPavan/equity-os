-- D9 Task 4: the retention protocol (plan docs/workstreams/data-foundation/plans/D9.md R6 RP1-RP3).
-- 0001--0027 are immutable. Capture states, purge runs and their closures are append-only; the
-- retention guard v2 replaces 0027's v1 and adds the lock, the stale-snapshot check and the
-- expired-original refusals. Purge-role grants arrive with the purge (0029).

-- RP1: the one advisory key purge (exclusive), backup (session shared) and writers share.
CREATE FUNCTION eqos.retention_lock_key() RETURNS bigint LANGUAGE sql IMMUTABLE AS $$
    SELECT 2026101709::bigint
$$;

-- RP2: each purge run takes the next epoch in its first transaction.
CREATE SEQUENCE eqos.retention_epoch CACHE 1 NO CYCLE;

CREATE TABLE eqos.purge_runs (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    epoch       bigint NOT NULL UNIQUE DEFAULT nextval('eqos.retention_epoch'),
    started_at  timestamptz NOT NULL DEFAULT eqos.store_now()
);

CREATE TABLE eqos.purge_run_closures (
    run_id      bigint PRIMARY KEY REFERENCES eqos.purge_runs (id),
    closed_at   timestamptz NOT NULL DEFAULT eqos.store_now()
);

-- A capture's latest row is its state; a capture with none is RETAINED.
CREATE TABLE eqos.capture_states (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    capture_ref_id  bigint NOT NULL REFERENCES eqos.capture_refs (id),
    state           text NOT NULL
        CHECK (state IN ('RETAINED', 'PURGE_PENDING', 'EXPIRED', 'RESTORED')),
    purge_run_id    bigint REFERENCES eqos.purge_runs (id),
    recorded_at     timestamptz NOT NULL DEFAULT eqos.store_now()
);
CREATE INDEX capture_states_latest ON eqos.capture_states (capture_ref_id, id);

DO $$
DECLARE
    table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY['purge_runs', 'purge_run_closures', 'capture_states'] LOOP
        EXECUTE format('CREATE TRIGGER reject_row_mutation BEFORE UPDATE OR DELETE ON eqos.%I '
            'FOR EACH ROW EXECUTE FUNCTION eqos.reject_mutation()', table_name);
        EXECUTE format('CREATE TRIGGER reject_truncate BEFORE TRUNCATE ON eqos.%I '
            'FOR EACH STATEMENT EXECUTE FUNCTION eqos.reject_mutation()', table_name);
        EXECUTE format('GRANT SELECT ON eqos.%I TO eqos_runtime, eqos_panel, eqos_owner, '
            'eqos_purge', table_name);
    END LOOP;
END;
$$;

CREATE FUNCTION eqos.capture_state(capture bigint) RETURNS text LANGUAGE sql STABLE AS $$
    SELECT coalesce((SELECT state FROM eqos.capture_states WHERE capture_ref_id = capture
                     ORDER BY id DESC LIMIT 1), 'RETAINED')
$$;

-- RP1: what blocks writers and backups until a purge rerun converges.
CREATE VIEW eqos.retention_pending AS
    SELECT 'RUN' AS kind, r.id FROM eqos.purge_runs r
    WHERE NOT EXISTS (SELECT 1 FROM eqos.purge_run_closures c WHERE c.run_id = r.id)
    UNION ALL
    SELECT 'INTENT', s.capture_ref_id FROM eqos.capture_states s
    WHERE s.state = 'PURGE_PENDING' AND NOT EXISTS (
        SELECT 1 FROM eqos.capture_states n
        WHERE n.capture_ref_id = s.capture_ref_id AND n.id > s.id);
GRANT SELECT ON eqos.retention_pending TO eqos_runtime, eqos_panel, eqos_owner, eqos_purge;

-- RP1, RP2: the shared transaction lock every retention-relevant write takes first. After the
-- lock, fresh statements compare the sequence (not MVCC) with the epochs this snapshot sees.
CREATE FUNCTION eqos.retention_shared() RETURNS void LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, eqos AS $$
BEGIN
    PERFORM pg_advisory_xact_lock_shared(eqos.retention_lock_key());
    IF EXISTS (SELECT 1 FROM eqos.retention_pending) THEN
        RAISE EXCEPTION 'PURGE_PENDING: a purge run is unfinished; run fundamentals retention purge'
            USING ERRCODE = '55000';
    END IF;
    IF pg_sequence_last_value('eqos.retention_epoch')
       IS DISTINCT FROM (SELECT max(epoch) FROM eqos.purge_runs) THEN
        RAISE EXCEPTION 'STALE_SNAPSHOT: a purge committed after this snapshot; retry'
            USING ERRCODE = '40001';
    END IF;
END $$;

-- RP3: the captures a new row rests on. Claims follow interpretations, traces (recursively),
-- interpretation operands, condition evidence and construction traces, pair outcomes and fact
-- origins; supports resolve through the claims, versions and disposed items they name. A
-- disposition is an outcome (ledger §6 item 4): it rests on no capture and only takes the lock.
CREATE OR REPLACE FUNCTION eqos.row_captures(tbl text, r jsonb) RETURNS bigint[]
LANGUAGE plpgsql STABLE AS $$
DECLARE
    found   bigint[];
    item    bigint := (SELECT item_id FROM eqos.queue_dispositions
                       WHERE id = (r ->> 'disposition_id')::bigint);
BEGIN
    IF tbl = 'memory_supports' THEN
        SELECT coalesce(array_agg(DISTINCT c) FILTER (WHERE c IS NOT NULL), '{}') INTO found
        FROM (
            SELECT (r ->> 'capture_ref_id')::bigint
            UNION ALL SELECT unnest(eqos.row_captures('numeric_claims', to_jsonb(k)))
                FROM eqos.numeric_claims k
                WHERE k.id = (r ->> 'claim_id')::bigint
                   OR k.version_id = (r ->> 'version_id')::bigint
            UNION ALL SELECT unnest(eqos.row_captures('report_sections', to_jsonb(s)))
                FROM eqos.report_sections s WHERE s.version_id = (r ->> 'version_id')::bigint
            UNION ALL SELECT unnest(eqos.row_captures('queue_item_inputs', to_jsonb(i)))
                FROM eqos.queue_item_inputs i WHERE i.item_id = item
            UNION ALL SELECT unnest(eqos.row_captures('queue_item_traces', to_jsonb(t)))
                FROM eqos.queue_item_traces t WHERE t.item_id = item
        ) x(c);
        RETURN found;
    END IF;
    WITH RECURSIVE nodes(kind, id) AS (
        SELECT v.kind, (r ->> v.col)::bigint FROM (VALUES ('T', 'calculation_trace_id'),
            ('T', 'operand_trace_id'), ('I', 'interpretation_id'),
            ('I', 'operand_interpretation_id'), ('I', 'evidence_interpretation_id')) v(kind, col)
        UNION ALL SELECT s.kind, s.id FROM eqos.pair_outcomes p
            JOIN eqos.result_source_values v ON v.id IN (p.left_value_id, p.right_value_id)
            CROSS JOIN LATERAL (VALUES ('I', v.interpretation_id), ('T', v.calculation_trace_id))
                s(kind, id)
            WHERE p.id = (r ->> 'pair_outcome_id')::bigint
        UNION ALL SELECT 'I', a.interpretation_id FROM eqos.fact_admissions a
            WHERE a.fact_origin = r ->> 'fact_origin'
              AND a.fact_origin_id = (r ->> 'fact_origin_id')::bigint
        UNION
        SELECT e.kind, e.id FROM nodes n CROSS JOIN LATERAL (
            SELECT 'I', operand_interpretation_id FROM eqos.interpretation_operands
                WHERE n.kind = 'I' AND interpretation_id = n.id
            UNION ALL SELECT 'I', evidence_interpretation_id
                FROM eqos.interpretation_condition_evidence
                WHERE n.kind = 'I' AND interpretation_id = n.id
            UNION ALL SELECT 'T', calculation_trace_id FROM eqos.construction_traces
                WHERE n.kind = 'I' AND interpretation_id = n.id
            UNION ALL SELECT 'I', interpretation_id FROM eqos.calculation_trace_operands
                WHERE n.kind = 'T' AND calculation_trace_id = n.id
            UNION ALL SELECT 'T', operand_trace_id FROM eqos.calculation_trace_operands
                WHERE n.kind = 'T' AND calculation_trace_id = n.id
        ) e(kind, id) WHERE e.id IS NOT NULL
    )
    SELECT coalesce(array_agg(DISTINCT c) FILTER (WHERE c IS NOT NULL), '{}') INTO found FROM (
        SELECT (r ->> CASE tbl WHEN 'capture_refs' THEN 'id' ELSE 'capture_ref_id' END)::bigint
        UNION ALL SELECT i.capture_ref_id FROM eqos.interpretations i
            JOIN nodes n ON n.kind = 'I' AND n.id = i.id
        UNION ALL SELECT capture_ref_id FROM eqos.occurrences
            WHERE id = (r ->> 'occurrence_id')::bigint
        UNION ALL SELECT capture_ref_id FROM eqos.acquisition_attempts
            WHERE id = (r ->> 'attempt_id')::bigint
        UNION ALL SELECT capture_ref_id FROM eqos.package_members
            WHERE package_id = (r ->> 'package_id')::bigint
        UNION ALL SELECT capture_ref_id FROM eqos.evidence_input_captures
            WHERE evidence_input_id = (r ->> 'evidence_input_id')::bigint
        UNION ALL SELECT b.capture_ref_id FROM eqos.fact_rows f
            JOIN eqos.legacy_evidence_bindings b
                ON (b.target_store, b.row_handle) = (f.target_store, f.handle)
            WHERE f.origin = r ->> 'fact_origin' AND f.origin_id = (r ->> 'fact_origin_id')::bigint
        UNION ALL SELECT m[1]::bigint
            FROM regexp_matches(coalesce(r ->> 'body', ''), '\{\{s:(\d+)\|', 'g') m
    ) x(c);
    RETURN found;
END $$;

-- RP3, guard v2: the shared lock first; then (a) no payload row and (b) no byte-needing edge
-- on a capture that is not retained, (c) nothing new on a licence-ended source, (d) no quote of
-- a vendor capture. Other edges to expired captures proceed (ledger §5).
CREATE OR REPLACE FUNCTION eqos.retention_guard() RETURNS trigger LANGUAGE plpgsql
SECURITY DEFINER SET search_path = pg_catalog, eqos AS $$
DECLARE
    rec         jsonb := to_jsonb(NEW);
    captures    bigint[];
    ended       text;
    expired     bigint;
BEGIN
    PERFORM eqos.retention_shared();
    captures := eqos.row_captures(TG_TABLE_NAME, rec);
    SELECT l.source_id INTO ended FROM eqos.licence_ends l
        WHERE l.source_id = rec ->> 'source_id'
           OR l.source_id IN (SELECT source_id FROM eqos.capture_refs WHERE id = ANY (captures))
        LIMIT 1;
    IF ended IS NOT NULL THEN
        RAISE EXCEPTION 'BEYOND_AUTHORITY: the % licence has ended; % refused', ended,
            TG_TABLE_NAME USING ERRCODE = '42501';
    END IF;
    IF rec ->> 'citation_kind' = 'SOURCE_QUOTE'
       AND EXISTS (SELECT 1 FROM eqos.capture_refs WHERE id = ANY (captures)
                   AND eqos.is_vendor_source(source_id)) THEN
        RAISE EXCEPTION 'BEYOND_AUTHORITY: a vendor capture cannot be quoted'
            USING ERRCODE = '42501';
    END IF;
    IF rec ->> 'citation_kind' = 'SOURCE_QUOTE' OR TG_TABLE_NAME IN ('report_sections',
        'legacy_evidence_bindings', 'occurrences', 'interpretations', 'interpretation_operands',
        'interpretation_condition_evidence', 'construction_traces', 'calculation_trace_operands',
        'result_source_values', 'run_inputs', 'acquisition_attempts', 'package_members') THEN
        SELECT c INTO expired FROM unnest(captures) c
            WHERE eqos.capture_state(c) NOT IN ('RETAINED', 'RESTORED') LIMIT 1;
        IF expired IS NOT NULL THEN
            RAISE EXCEPTION 'ORIGINAL_EXPIRED: capture % is not retained; % refused', expired,
                TG_TABLE_NAME USING ERRCODE = '55000';
        END IF;
    END IF;
    RETURN NEW;
END $$;

-- v1 left dispositions and watchlist ADDs unguarded; v2 takes the lock on both.
CREATE TRIGGER a0_retention_guard BEFORE INSERT ON eqos.queue_dispositions
    FOR EACH ROW EXECUTE FUNCTION eqos.retention_guard();
CREATE TRIGGER a0_retention_guard BEFORE INSERT ON eqos.decisions
    FOR EACH ROW WHEN (NEW.subject_kind = 'WATCHLIST' AND NEW.kind = 'ADD')
    EXECUTE FUNCTION eqos.retention_guard();
