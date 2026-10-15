-- D3 phase review fixes (plan D1, D3, D4). 0001--0013 are immutable.
-- * version_superseded counts IMPORTED_APPROVAL, as version_status does: an owner may withdraw
--   an imported version an imported successor approved.
-- * A report-local version number and a validation result digest, both derived from append-only
--   rows (ledger spec §1 entities).
-- * One decider mapping and one stamp (store-clock time, transaction, chain digest) for every
--   decision; the subject triggers keep only their own checks.

CREATE OR REPLACE FUNCTION eqos.version_superseded(version bigint) RETURNS boolean
LANGUAGE sql STABLE AS $$
    WITH RECURSIVE descendants (id) AS (
        SELECT id FROM eqos.report_versions WHERE predecessor_id = version
        UNION ALL
        SELECT v.id FROM eqos.report_versions v JOIN descendants d ON v.predecessor_id = d.id
    )
    SELECT EXISTS (SELECT 1 FROM eqos.decisions
                   WHERE subject_kind = 'REPORT_VERSION' AND kind IN ('APPROVE', 'IMPORTED_APPROVAL')
                     AND subject_id IN (SELECT id FROM descendants))
$$;

-- A report's versions are one chain in id order (D4), so a version's number is its position.
CREATE FUNCTION eqos.version_number(version bigint) RETURNS integer LANGUAGE sql STABLE AS $$
    SELECT (SELECT count(*) FROM eqos.report_versions o
            WHERE o.report_id = v.report_id AND o.id <= v.id)::integer
    FROM eqos.report_versions v WHERE v.id = version
$$;

-- D1 digest of a validation's result: its row, then its states in claim-key order (version-level
-- states last, by state). States are sealed with the validation's transaction.
CREATE FUNCTION eqos.validation_result_digest(validation bigint) RETURNS text
LANGUAGE sql STABLE AS $$
    SELECT encode(sha256(convert_to(
        eqos.enc(v.id::text) || eqos.enc(v.version_id::text) || eqos.enc(v.checker_version)
        || eqos.enc(v.mode) || eqos.enc(v.overlay_position) || eqos.enc(v.pinned_input_sha256)
        || eqos.enc(v.sealed_digest) || eqos.enc(v.recorded_at)
        || (SELECT eqos.enc(count(*)::text) || coalesce(string_agg(
                eqos.enc(c.claim_key) || eqos.enc(s.state),
                '' ORDER BY c.claim_key COLLATE "C" NULLS LAST, s.state COLLATE "C"), '')
            FROM eqos.validation_claim_states s
            LEFT JOIN eqos.numeric_claims c ON c.id = s.claim_id
            WHERE s.validation_id = v.id),
        'UTF8')), 'hex')
    FROM eqos.validations v WHERE v.id = validation
$$;

CREATE FUNCTION eqos.decider_role() RETURNS text LANGUAGE sql STABLE AS $$
    SELECT CASE current_user WHEN 'eqos_runtime' THEN 'RUNTIME' WHEN 'eqos_panel' THEN 'PANEL'
                             WHEN 'eqos_owner' THEN 'OWNER' END
$$;

-- Runs after every subject check (trigger names sort): the chain digest over the row fields in
-- column order, then the predecessor's digest (the checks hold it to the chain head).
CREATE FUNCTION eqos.stamp_decision() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, eqos AS $$ BEGIN
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
        || eqos.enc((SELECT decision_sha256 FROM eqos.decisions WHERE id = NEW.predecessor_id)),
        'UTF8')), 'hex');
    RETURN NEW;
END $$;

-- 0012's check, minus the decider mapping and the stamp.
CREATE OR REPLACE FUNCTION eqos.check_decision() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, eqos AS $$
DECLARE
    head        eqos.decisions;
    version     eqos.report_versions;
    latest      eqos.validations;
    imported    boolean;
    legal       boolean;
BEGIN
    NEW.decider := eqos.decider_role();
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
    RETURN NEW;
END $$;

-- 0013's check, minus the decider mapping and the stamp.
CREATE OR REPLACE FUNCTION eqos.check_subject_decision() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, eqos AS $$
DECLARE
    item    bigint;
    legal   boolean;
BEGIN
    NEW.decider := eqos.decider_role();
    IF NEW.subject_kind = 'DISPOSITION_PROPOSAL' THEN
        PERFORM eqos.lock_queue();
        SELECT item_id INTO item FROM eqos.disposition_proposals WHERE id = NEW.subject_id;
    END IF;
    PERFORM eqos.lock_subject(NEW.subject_kind, NEW.subject_id);
    legal := NEW.kind IN ('ACCEPT', 'REJECT') AND NEW.predecessor_id IS NULL
        AND NOT EXISTS (SELECT 1 FROM eqos.decisions
                        WHERE subject_kind = NEW.subject_kind AND subject_id = NEW.subject_id)
        AND (NEW.decider <> 'OWNER' OR coalesce(NEW.ruling, '') <> '')
        AND CASE NEW.subject_kind
            WHEN 'INTERPRETATION' THEN NEW.decider = 'OWNER'
                AND EXISTS (SELECT 1 FROM eqos.interpretations WHERE id = NEW.subject_id)
            ELSE NEW.decider IN ('PANEL', 'OWNER') AND item IS NOT NULL END;
    IF NOT coalesce(legal, false) THEN
        RAISE EXCEPTION 'illegal decision: % by % on % %', NEW.kind, NEW.decider,
            NEW.subject_kind, NEW.subject_id USING ERRCODE = '23514';
    END IF;
    IF NEW.decider = 'PANEL' AND (
        EXISTS (SELECT 1 FROM eqos.queue_dispositions WHERE item_id = item)
        OR EXISTS (SELECT 1 FROM eqos.decisions d
                   JOIN eqos.disposition_proposals p ON p.id = d.subject_id
                   WHERE d.subject_kind = 'DISPOSITION_PROPOSAL' AND d.decider = 'OWNER'
                     AND p.item_id = item)) THEN
        RAISE EXCEPTION 'queue item % has an owner disposition or decision', item
            USING ERRCODE = '23514';
    END IF;
    IF NEW.sealed_digest
       IS DISTINCT FROM eqos.subject_digest(NEW.subject_kind, NEW.subject_id) THEN
        RAISE EXCEPTION 'sealed digest does not match % %', NEW.subject_kind, NEW.subject_id
            USING ERRCODE = '23514';
    END IF;
    NEW.sequence := 1;
    RETURN NEW;
END $$;

CREATE TRIGGER stamp_decision BEFORE INSERT ON eqos.decisions
    FOR EACH ROW EXECUTE FUNCTION eqos.stamp_decision();
