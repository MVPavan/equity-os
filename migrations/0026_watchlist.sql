-- D7 Task 3: watchlist decisions and the drafting gate (ledger spec O10; plan D7 R3, R6, R7).
-- 0001--0025 are immutable. A WATCHLIST subject is a reporting entity; the owner ADDs a stock
-- that has an admitted result in a completed batch and may REMOVE it. The runtime role drafts a
-- version, or adds content to one, only for a watchlisted stock.

-- R3 digest of a stock's coverage: its latest admitted result in a completed batch (completion,
-- result, onboarding record and run). NULL when there is none.
CREATE FUNCTION eqos.watchlist_digest(entity bigint) RETURNS text LANGUAGE sql STABLE AS $$
    SELECT encode(sha256(convert_to(eqos.enc(c.id::text) || eqos.enc(r.id::text)
        || eqos.enc(r.onboarding_record_id::text) || eqos.enc(r.run_id::text), 'UTF8')), 'hex')
    FROM eqos.batch_member_results r JOIN eqos.batch_completions c ON c.batch_id = r.batch_id
    WHERE r.entity_id = entity AND r.outcome IN ('ONBOARDED', 'PARTIAL')
    ORDER BY r.id DESC LIMIT 1
$$;

-- The stock's latest watchlist decision is an ADD (also D9.2's covered-stock test).
CREATE FUNCTION eqos.watchlisted(entity bigint) RETURNS boolean LANGUAGE sql STABLE AS $$
    SELECT coalesce((SELECT kind = 'ADD' FROM eqos.decisions
                     WHERE subject_kind = 'WATCHLIST' AND subject_id = entity
                     ORDER BY sequence DESC LIMIT 1), false)
$$;

-- 0016's digest dispatch plus the watchlist branch.
CREATE OR REPLACE FUNCTION eqos.subject_digest(kind text, subject bigint) RETURNS text
LANGUAGE sql STABLE SET TimeZone = 'UTC' AS $$
    SELECT CASE kind
        WHEN 'REPORT_VERSION' THEN eqos.version_sealed_digest(subject)
        WHEN 'MEMORY_ITEM' THEN eqos.memory_sealed_digest(subject)
        WHEN 'WATCHLIST' THEN eqos.watchlist_digest(subject)
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

-- O10: ADD (on an empty chain or after REMOVE) and REMOVE (after ADD) by the owner with the
-- verbatim ruling, sealed to the stock's coverage digest. Sorts before check_panel_review, which
-- reads the decider, and stamp_decision.
CREATE FUNCTION eqos.check_owner_watchlist() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, eqos AS $$
DECLARE
    head    eqos.decisions;
BEGIN
    NEW.decider := eqos.decider_role();
    IF NEW.decider IS DISTINCT FROM 'OWNER' THEN
        RAISE EXCEPTION 'role % may not decide the watchlist', current_user
            USING ERRCODE = '42501';
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
    IF coalesce(NEW.ruling, '') = '' THEN
        RAISE EXCEPTION '% needs the verbatim ruling', NEW.kind USING ERRCODE = '23514';
    END IF;
    IF NOT coalesce(CASE NEW.kind WHEN 'ADD' THEN coalesce(head.kind, 'REMOVE') = 'REMOVE'
                                  WHEN 'REMOVE' THEN head.kind = 'ADD' END, false) THEN
        RAISE EXCEPTION 'illegal decision: % on % % after %', NEW.kind, NEW.subject_kind,
            NEW.subject_id, coalesce(head.kind, 'nothing') USING ERRCODE = '23514';
    END IF;
    NEW.sealed_digest := eqos.watchlist_digest(NEW.subject_id);
    IF NEW.sealed_digest IS NULL THEN
        RAISE EXCEPTION 'stock % has no admitted result in a completed batch', NEW.subject_id
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;

-- R6/R7: a runtime version or version content needs its stock on the watchlist, read at READ
-- COMMITTED after the WATCHLIST lock (taken before record_version's and check_version_seal's
-- REPORT_VERSION lock, whose store_now() stamps the version). A version also needs a bootstrap
-- report or an existing bootstrap version of the stock.
CREATE FUNCTION eqos.check_drafting() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, eqos AS $$
DECLARE
    report  eqos.reports;
BEGIN
    IF eqos.decider_role() IS DISTINCT FROM 'RUNTIME' THEN
        RETURN NEW;
    END IF;
    IF current_setting('transaction_isolation') <> 'read committed' THEN
        RAISE EXCEPTION 'drafting runs at READ COMMITTED only' USING ERRCODE = '23514';
    END IF;
    IF TG_TABLE_NAME = 'report_versions' THEN
        SELECT * INTO report FROM eqos.reports WHERE id = NEW.report_id;
    ELSE
        SELECT r.* INTO report FROM eqos.reports r
            JOIN eqos.report_versions v ON v.report_id = r.id WHERE v.id = NEW.version_id;
    END IF;
    PERFORM eqos.lock_subject('WATCHLIST', report.entity_id);
    IF NOT eqos.watchlisted(report.entity_id) THEN
        RAISE EXCEPTION 'stock % is not on the watchlist', report.entity_id
            USING ERRCODE = '23514';
    END IF;
    IF TG_TABLE_NAME = 'report_versions' AND report.kind <> 'BOOTSTRAP_THESIS' AND NOT EXISTS (
        SELECT 1 FROM eqos.report_versions v JOIN eqos.reports b ON b.id = v.report_id
        WHERE b.entity_id = report.entity_id AND b.kind = 'BOOTSTRAP_THESIS') THEN
        RAISE EXCEPTION 'stock % has no bootstrap thesis version', report.entity_id
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;

ALTER TABLE eqos.decisions DROP CONSTRAINT decisions_subject_kind_check,
    ADD CONSTRAINT decisions_subject_kind_check CHECK (subject_kind IN ('REPORT_VERSION',
        'REPORT', 'DISPOSITION_PROPOSAL', 'INTERPRETATION', 'MEMORY_ITEM', 'WATCHLIST'));
ALTER TABLE eqos.decisions DROP CONSTRAINT decisions_kind_check,
    ADD CONSTRAINT decisions_kind_check CHECK (kind IN ('SUBMIT', 'IMPORT_SEAL',
        'IMPORTED_APPROVAL', 'APPROVE', 'REQUEST_CHANGES', 'REJECT', 'WITHDRAW', 'ACCEPT',
        'SET_POLICY', 'PROMOTE', 'REJECT_CANDIDATE', 'RETIRE', 'ADD', 'REMOVE'));

CREATE TRIGGER check_owner_watchlist BEFORE INSERT ON eqos.decisions FOR EACH ROW
    WHEN (NEW.subject_kind = 'WATCHLIST') EXECUTE FUNCTION eqos.check_owner_watchlist();

DO $$
DECLARE
    table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY['report_versions', 'import_sources', 'report_sections',
                                      'numeric_claims'] LOOP
        EXECUTE format('CREATE TRIGGER a_check_drafting BEFORE INSERT ON eqos.%I '
            'FOR EACH ROW EXECUTE FUNCTION eqos.check_drafting()', table_name);
    END LOOP;
END;
$$;
