-- D4 Task 1: long-term memory items and supports, sealed and staged with at least one support,
-- and their decisions in the D3 chain by the panel or the owner (ledger spec §2; plan D4, M1,
-- M2). 0001--0015 are immutable. Status is derived from PROMOTE, REJECT_CANDIDATE and RETIRE
-- rows in eqos.decisions, never stored (P1).

CREATE TABLE eqos.memory_items (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_id           bigint REFERENCES eqos.reporting_entities (id),
    kind                text NOT NULL CHECK (kind IN ('COMPANY_UNDERSTANDING',
        'MANAGEMENT_TRACK_RECORD', 'THESIS_AND_WARNING', 'SOURCE_QUIRK', 'OWNER_RULING', 'LESSON')),
    statement           text NOT NULL CHECK (char_length(statement) BETWEEN 1 AND 500),
    epistemic_class     text NOT NULL CHECK (epistemic_class IN (
        'observed', 'computed', 'inferred', 'forecast', 'opinion')),
    valid_from          date NOT NULL,
    valid_to            date,
    supersedes_item_id  bigint REFERENCES eqos.memory_items (id),
    recorded_at         timestamptz NOT NULL,
    created_xid         bigint NOT NULL,
    -- Stored: PostgreSQL 18 generated columns are virtual by default and cannot be indexed.
    statement_search    tsvector GENERATED ALWAYS AS (to_tsvector('english', statement)) STORED,
    CHECK (valid_to >= valid_from),
    CHECK (supersedes_item_id < id),
    CHECK (entity_id IS NOT NULL OR kind IN ('SOURCE_QUIRK', 'OWNER_RULING', 'LESSON'))
);
CREATE INDEX memory_items_statement_search ON eqos.memory_items USING gin (statement_search);

CREATE TABLE eqos.memory_supports (
    id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    item_id                 bigint NOT NULL REFERENCES eqos.memory_items (id),
    claim_id                bigint REFERENCES eqos.numeric_claims (id),
    version_id              bigint REFERENCES eqos.report_versions (id),
    definition_record_id    bigint REFERENCES eqos.definition_records (id),
    disposition_id          bigint REFERENCES eqos.queue_dispositions (id),
    decision_id             bigint REFERENCES eqos.decisions (id),
    capture_ref_id          bigint REFERENCES eqos.capture_refs (id),
    CHECK (num_nonnulls(claim_id, version_id, definition_record_id, disposition_id, decision_id,
                        capture_ref_id) = 1),
    UNIQUE NULLS NOT DISTINCT (item_id, claim_id, version_id, definition_record_id,
                               disposition_id, decision_id, capture_ref_id)
);

-- D1 digest of an item: its row (the generated column aside), then the support count and each
-- support's targets in id order. NULL for a missing item.
CREATE FUNCTION eqos.memory_sealed_digest(item bigint) RETURNS text LANGUAGE sql STABLE AS $$
    SELECT encode(sha256(convert_to(
        eqos.enc(i.id::text) || eqos.enc(i.entity_id::text) || eqos.enc(i.kind)
        || eqos.enc(i.statement) || eqos.enc(i.epistemic_class) || eqos.enc(i.valid_from)
        || eqos.enc(i.valid_to) || eqos.enc(i.supersedes_item_id::text)
        || eqos.enc(i.recorded_at) || eqos.enc(i.created_xid::text)
        || (SELECT eqos.enc(count(*)::text) || coalesce(string_agg(
                eqos.enc(s.claim_id::text) || eqos.enc(s.version_id::text)
                || eqos.enc(s.definition_record_id::text) || eqos.enc(s.disposition_id::text)
                || eqos.enc(s.decision_id::text) || eqos.enc(s.capture_ref_id::text),
                '' ORDER BY s.id), '')
            FROM eqos.memory_supports s WHERE s.item_id = i.id),
        'UTF8')), 'hex')
    FROM eqos.memory_items i WHERE i.id = item
$$;

-- True when an item superseding this one has been promoted, which retires this one.
CREATE FUNCTION eqos.memory_promoted_successor(item bigint) RETURNS boolean
LANGUAGE sql STABLE AS $$
    SELECT EXISTS (SELECT 1 FROM eqos.memory_items s JOIN eqos.decisions d
                   ON d.subject_kind = 'MEMORY_ITEM' AND d.subject_id = s.id AND d.kind = 'PROMOTE'
                   WHERE s.supersedes_item_id = item)
$$;

-- 0013's digest dispatch plus the memory branch.
CREATE OR REPLACE FUNCTION eqos.subject_digest(kind text, subject bigint) RETURNS text
LANGUAGE sql STABLE SET TimeZone = 'UTC' AS $$
    SELECT CASE kind
        WHEN 'REPORT_VERSION' THEN eqos.version_sealed_digest(subject)
        WHEN 'MEMORY_ITEM' THEN eqos.memory_sealed_digest(subject)
        WHEN 'DISPOSITION_PROPOSAL' THEN (
            SELECT encode(sha256(convert_to(eqos.enc(to_jsonb(p)) || eqos.enc(to_jsonb(q))
                || eqos.enc(to_jsonb(o)), 'UTF8')), 'hex')
            FROM eqos.disposition_proposals p JOIN eqos.queue_items q ON q.id = p.item_id
            LEFT JOIN eqos.pair_outcomes o ON o.id = p.pair_outcome_id WHERE p.id = subject)
        WHEN 'INTERPRETATION' THEN (
            SELECT encode(sha256(convert_to(eqos.enc(to_jsonb(i)) || eqos.enc(coalesce(
                (SELECT jsonb_agg(to_jsonb(o) ORDER BY o.ordinal)
                 FROM eqos.interpretation_operands o WHERE o.interpretation_id = i.id),
                '[]'::jsonb)), 'UTF8')), 'hex')
            FROM eqos.interpretations i WHERE i.id = subject) END
$$;

-- An item's store time; a correction supersedes an item of the same stock and kind only.
CREATE FUNCTION eqos.record_memory_item() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, eqos AS $$ BEGIN
    IF NEW.supersedes_item_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM eqos.memory_items WHERE id = NEW.supersedes_item_id
          AND entity_id IS NOT DISTINCT FROM NEW.entity_id AND kind = NEW.kind) THEN
        RAISE EXCEPTION 'item supersedes % across stock or kind', NEW.supersedes_item_id
            USING ERRCODE = '23514';
    END IF;
    NEW.recorded_at := eqos.store_now();
    NEW.created_xid := txid_current();
    RETURN NEW;
END $$;

-- Supports are sealed with their item: inserts only in its creating transaction, so none
-- follows a decision (always a later transaction by another role).
CREATE FUNCTION eqos.check_memory_support() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, eqos AS $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM eqos.memory_items
                   WHERE id = NEW.item_id AND created_xid = txid_current()) THEN
        RAISE EXCEPTION 'memory supports are sealed with the item transaction'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;

CREATE FUNCTION eqos.check_memory_item_supported() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, eqos AS $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM eqos.memory_supports WHERE item_id = NEW.id) THEN
        RAISE EXCEPTION 'memory item % has no support', NEW.id USING ERRCODE = '23514';
    END IF;
    RETURN NULL;
END $$;

-- M2: PROMOTE and REJECT_CANDIDATE on an empty chain by the panel or owner; RETIRE by the owner
-- after PROMOTE unless a promoted successor already retired the item. A correction promotes
-- only over a predecessor that is still PROMOTED. The queue lock comes before the subject lock
-- (M4 lock order); PROMOTE runs at READ COMMITTED only (amendment A1). stamp_decision follows.
CREATE FUNCTION eqos.check_memory_decision() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, eqos AS $$
DECLARE
    head        eqos.decisions;
    item        eqos.memory_items;
    legal       boolean;
BEGIN
    IF NEW.kind = 'PROMOTE' AND current_setting('transaction_isolation') <> 'read committed' THEN
        RAISE EXCEPTION 'PROMOTE runs at READ COMMITTED only' USING ERRCODE = '23514';
    END IF;
    NEW.decider := eqos.decider_role();
    IF NOT coalesce(NEW.decider IN ('PANEL', 'OWNER'), false) THEN
        RAISE EXCEPTION 'role % may not decide memory items', current_user
            USING ERRCODE = '42501';
    END IF;
    PERFORM eqos.lock_queue();
    PERFORM eqos.lock_subject(NEW.subject_kind, NEW.subject_id);
    SELECT * INTO head FROM eqos.decisions
        WHERE subject_kind = NEW.subject_kind AND subject_id = NEW.subject_id
        ORDER BY sequence DESC LIMIT 1;
    IF NEW.predecessor_id IS DISTINCT FROM head.id THEN
        RAISE EXCEPTION 'stale head: % % is at decision %', NEW.subject_kind, NEW.subject_id,
            head.id USING ERRCODE = '23514';
    END IF;
    NEW.sequence := coalesce(head.sequence, 0) + 1;
    IF NEW.decider = 'OWNER' AND coalesce(NEW.ruling, '') = '' THEN
        RAISE EXCEPTION '% needs the verbatim ruling', NEW.kind USING ERRCODE = '23514';
    END IF;
    SELECT * INTO item FROM eqos.memory_items WHERE id = NEW.subject_id;
    legal := item.id IS NOT NULL AND CASE NEW.kind
        WHEN 'PROMOTE' THEN head.id IS NULL AND (item.supersedes_item_id IS NULL OR (
            (SELECT kind FROM eqos.decisions
             WHERE subject_kind = 'MEMORY_ITEM' AND subject_id = item.supersedes_item_id
             ORDER BY sequence DESC LIMIT 1) = 'PROMOTE'
            AND NOT eqos.memory_promoted_successor(item.supersedes_item_id)))
        WHEN 'REJECT_CANDIDATE' THEN head.id IS NULL
        WHEN 'RETIRE' THEN NEW.decider = 'OWNER' AND head.kind = 'PROMOTE'
            AND NOT eqos.memory_promoted_successor(NEW.subject_id)
        ELSE false END;
    IF NOT coalesce(legal, false) THEN
        RAISE EXCEPTION 'illegal decision: % by % on % % after %', NEW.kind, NEW.decider,
            NEW.subject_kind, NEW.subject_id, coalesce(head.kind, 'nothing')
            USING ERRCODE = '23514';
    END IF;
    IF NOT coalesce(NEW.sealed_digest = eqos.memory_sealed_digest(NEW.subject_id), false) THEN
        RAISE EXCEPTION 'sealed digest does not match memory item %', NEW.subject_id
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;

-- 0013's D10 check with the memory verdicts: APPROVE → PROMOTE, REJECT → REJECT_CANDIDATE.
CREATE OR REPLACE FUNCTION eqos.check_panel_review() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, eqos AS $$
DECLARE
    review  eqos.panel_reviews;
BEGIN
    IF (NEW.decider = 'PANEL' AND NEW.kind NOT IN ('IMPORT_SEAL', 'IMPORTED_APPROVAL'))
       IS DISTINCT FROM (NEW.panel_review_id IS NOT NULL) THEN
        RAISE EXCEPTION '% by % needs a panel review exactly when the panel decides', NEW.kind,
            NEW.decider USING ERRCODE = '23514';
    END IF;
    IF NEW.panel_review_id IS NULL THEN
        RETURN NEW;
    END IF;
    SELECT * INTO review FROM eqos.panel_reviews WHERE id = NEW.panel_review_id;
    IF review.id IS NULL OR review.subject_kind <> NEW.subject_kind
       OR review.subject_id <> NEW.subject_id OR review.sealed_digest <> NEW.sealed_digest
       OR review.created_xid <> txid_current()
       OR EXISTS (SELECT 1 FROM eqos.decisions WHERE panel_review_id = review.id)
       OR NEW.kind IS DISTINCT FROM (CASE
            WHEN NEW.subject_kind = 'REPORT_VERSION' THEN review.verdict
            WHEN NEW.subject_kind = 'MEMORY_ITEM' THEN CASE review.verdict
                WHEN 'APPROVE' THEN 'PROMOTE' WHEN 'REJECT' THEN 'REJECT_CANDIDATE' END
            WHEN review.verdict = 'APPROVE' THEN 'ACCEPT'
            WHEN review.verdict = 'REJECT' THEN 'REJECT' END) THEN
        RAISE EXCEPTION 'panel review % does not bind % on % %', NEW.panel_review_id, NEW.kind,
            NEW.subject_kind, NEW.subject_id USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;

-- O3: the column checks' generated names, as created by 0012 and 0013.
ALTER TABLE eqos.decisions DROP CONSTRAINT decisions_subject_kind_check,
    ADD CONSTRAINT decisions_subject_kind_check CHECK (subject_kind IN (
        'REPORT_VERSION', 'REPORT', 'DISPOSITION_PROPOSAL', 'INTERPRETATION', 'MEMORY_ITEM'));
ALTER TABLE eqos.decisions DROP CONSTRAINT decisions_kind_check,
    ADD CONSTRAINT decisions_kind_check CHECK (kind IN ('SUBMIT', 'IMPORT_SEAL',
        'IMPORTED_APPROVAL', 'APPROVE', 'REQUEST_CHANGES', 'REJECT', 'WITHDRAW', 'ACCEPT',
        'SET_POLICY', 'PROMOTE', 'REJECT_CANDIDATE', 'RETIRE'));
ALTER TABLE eqos.panel_reviews DROP CONSTRAINT panel_reviews_subject_kind_check,
    ADD CONSTRAINT panel_reviews_subject_kind_check
        CHECK (subject_kind IN ('REPORT_VERSION', 'DISPOSITION_PROPOSAL', 'MEMORY_ITEM'));

-- Sorts after check_decision_subject and before check_panel_review, which reads the decider.
CREATE TRIGGER check_memory_decision BEFORE INSERT ON eqos.decisions FOR EACH ROW
    WHEN (NEW.subject_kind = 'MEMORY_ITEM') EXECUTE FUNCTION eqos.check_memory_decision();
CREATE TRIGGER record_memory_item BEFORE INSERT ON eqos.memory_items
    FOR EACH ROW EXECUTE FUNCTION eqos.record_memory_item();
CREATE CONSTRAINT TRIGGER check_memory_item_supported AFTER INSERT ON eqos.memory_items
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
    EXECUTE FUNCTION eqos.check_memory_item_supported();
CREATE TRIGGER check_memory_support BEFORE INSERT ON eqos.memory_supports
    FOR EACH ROW EXECUTE FUNCTION eqos.check_memory_support();

DO $$
DECLARE
    name text;
BEGIN
    FOREACH name IN ARRAY ARRAY['memory_items', 'memory_supports'] LOOP
        EXECUTE format('CREATE TRIGGER reject_row_mutation BEFORE UPDATE OR DELETE ON eqos.%I '
            'FOR EACH ROW EXECUTE FUNCTION eqos.reject_mutation()', name);
        EXECUTE format('CREATE TRIGGER reject_truncate BEFORE TRUNCATE ON eqos.%I '
            'FOR EACH STATEMENT EXECUTE FUNCTION eqos.reject_mutation()', name);
    END LOOP;
END $$;

-- The D2 matrix's default row: everyone reads, only the runtime stages.
GRANT SELECT ON eqos.memory_items, eqos.memory_supports TO eqos_runtime, eqos_panel, eqos_owner;
GRANT INSERT ON eqos.memory_items, eqos.memory_supports TO eqos_runtime;
GRANT USAGE ON SEQUENCE eqos.memory_items_id_seq, eqos.memory_supports_id_seq TO eqos_runtime;
