-- D3 Task 4: the approval panel, disposition proposals and queue gating (plan D3, D4, D10,
-- D11). 0001--0012 are immutable: 0012's check_decision keeps report and version subjects,
-- check_subject_decision takes proposals and interpretations, check_panel_review holds D10.
-- D11: the comparison writer stores routing.pair_identity with each outcome; outcomes stored
-- before 0013 keep a null, so no proposal can bind them.
ALTER TABLE eqos.pair_outcomes ADD COLUMN pair_identity text;

CREATE TABLE eqos.panel_reviews (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    subject_kind        text NOT NULL
        CHECK (subject_kind IN ('REPORT_VERSION', 'DISPOSITION_PROPOSAL')),
    subject_id          bigint NOT NULL,
    sealed_digest       text NOT NULL,
    provider            text NOT NULL CHECK (provider <> ''),
    model               text NOT NULL CHECK (model <> ''),
    effort              text NOT NULL CHECK (effort <> ''),
    brief_version       text NOT NULL CHECK (brief_version <> ''),
    verdict             text NOT NULL
        CHECK (verdict IN ('APPROVE', 'REQUEST_CHANGES', 'REJECT')),
    rationale           text NOT NULL CHECK (rationale <> ''),
    rationale_sha256    text NOT NULL,
    created_xid         bigint NOT NULL,
    recorded_at         timestamptz NOT NULL
);
ALTER TABLE eqos.decisions ADD FOREIGN KEY (panel_review_id) REFERENCES eqos.panel_reviews (id);
CREATE UNIQUE INDEX decisions_one_per_review ON eqos.decisions (panel_review_id);

-- A runtime proposal; ACCEPTED_AS_DEFINITION binds the pair outcome its amount comes from.
CREATE TABLE eqos.disposition_proposals (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    item_id         bigint NOT NULL REFERENCES eqos.queue_items (id),
    kind            text NOT NULL CHECK (kind IN ('ACCEPTED_AS_DEFINITION', 'MAPPING_FIX',
        'PARSER_DEFECT', 'FILER_INCONSISTENCY', 'ALTERNATE_READ_REQUIRED', 'DISMISSED')),
    reason          text NOT NULL CHECK (reason <> ''),
    evidence_ref    text NOT NULL CHECK (evidence_ref <> ''),
    pair_outcome_id bigint REFERENCES eqos.pair_outcomes (id),
    recorded_at     timestamptz NOT NULL,
    CHECK ((pair_outcome_id IS NOT NULL) = (kind = 'ACCEPTED_AS_DEFINITION'))
);
CREATE UNIQUE INDEX queue_dispositions_one_per_decision ON eqos.queue_dispositions (evidence_ref)
    WHERE evidence_ref LIKE 'decision:%';

-- D1 digest of a decision subject; rows are walked as JSON under UTC (session-independent).
CREATE FUNCTION eqos.subject_digest(kind text, subject bigint) RETURNS text
LANGUAGE sql STABLE SET TimeZone = 'UTC' AS $$
    SELECT CASE kind
        WHEN 'REPORT_VERSION' THEN eqos.version_sealed_digest(subject)
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

-- The stored deterministic difference a proposal accepts; never a caller's number.
CREATE FUNCTION eqos.proposal_amount(proposal bigint) RETURNS numeric LANGUAGE sql STABLE AS $$
    SELECT abs(o.difference) FROM eqos.disposition_proposals p
    JOIN eqos.pair_outcomes o ON o.id = p.pair_outcome_id WHERE p.id = proposal
$$;

CREATE FUNCTION eqos.record_panel_review() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, eqos AS $$ BEGIN
    NEW.rationale_sha256 := encode(sha256(convert_to(NEW.rationale, 'UTF8')), 'hex');
    NEW.created_xid := txid_current();
    NEW.recorded_at := eqos.store_now();
    RETURN NEW;
END $$;

-- D11 pair binding: the outcome of the item's own pair (run membership, key, pair identity,
-- outcome) with a stored non-zero difference.
CREATE FUNCTION eqos.check_proposal() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, eqos AS $$ BEGIN
    IF NEW.pair_outcome_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM eqos.queue_items q
        JOIN eqos.queue_run_items m ON m.item_id = q.id
        JOIN eqos.results r ON r.run_id = m.run_id AND r.key_digest = q.key_digest
        JOIN eqos.pair_outcomes o ON o.result_id = r.id
        WHERE q.id = NEW.item_id AND o.id = NEW.pair_outcome_id
          AND o.pair_identity = q.pair_identity AND o.outcome = q.outcome
          AND o.difference <> 0) THEN
        RAISE EXCEPTION 'pair outcome % is not the pair of queue item %', NEW.pair_outcome_id,
            NEW.item_id USING ERRCODE = '23514';
    END IF;
    NEW.recorded_at := eqos.store_now();
    RETURN NEW;
END $$;

-- D3/D4/D11: one ACCEPT or REJECT per proposal (panel or owner) or interpretation (owner). A
-- proposal decision takes the queue lock before the subject lock; the panel yields to any
-- disposition of the item and any owner decision on a proposal of it.
CREATE FUNCTION eqos.check_subject_decision() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, eqos AS $$
DECLARE
    item    bigint;
    legal   boolean;
BEGIN
    NEW.decider := CASE current_user WHEN 'eqos_runtime' THEN 'RUNTIME'
        WHEN 'eqos_panel' THEN 'PANEL' WHEN 'eqos_owner' THEN 'OWNER' END;
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
        || eqos.enc(NEW.decider) || eqos.enc(NEW.recorded_at) || eqos.enc(NULL::text),
        'UTF8')), 'hex');
    RETURN NEW;
END $$;

-- D10: a panel decision (imports aside) names an unused review of its own subject and digest,
-- written in this transaction, whose verdict maps to the decision kind; no one else names one.
CREATE FUNCTION eqos.check_panel_review() RETURNS trigger LANGUAGE plpgsql
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
       OR NEW.kind IS DISTINCT FROM (CASE WHEN NEW.subject_kind = 'REPORT_VERSION'
            THEN review.verdict WHEN review.verdict = 'APPROVE' THEN 'ACCEPT'
            WHEN review.verdict = 'REJECT' THEN 'REJECT' END) THEN
        RAISE EXCEPTION 'panel review % does not bind % on % %', NEW.panel_review_id, NEW.kind,
            NEW.subject_kind, NEW.subject_id USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;

-- D11: a disposition naming decision:<id> follows that same-transaction ACCEPT on a proposal
-- of its item, kind and reason, with the proposal's derived amount; the panel disposes only so.
CREATE FUNCTION eqos.check_disposition() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, eqos AS $$ BEGIN
    IF NEW.evidence_ref LIKE 'decision:%' THEN
        IF NOT EXISTS (
            SELECT 1 FROM eqos.decisions d JOIN eqos.disposition_proposals p ON p.id = d.subject_id
            WHERE NEW.evidence_ref = 'decision:' || d.id AND d.kind = 'ACCEPT'
              AND d.subject_kind = 'DISPOSITION_PROPOSAL' AND d.created_xid = txid_current()
              AND p.item_id = NEW.item_id AND p.kind = NEW.kind AND p.reason = NEW.reason
              AND eqos.proposal_amount(p.id) IS NOT DISTINCT FROM NEW.explained_amount) THEN
            RAISE EXCEPTION 'disposition does not follow its accepted proposal'
                USING ERRCODE = '23514';
        END IF;
    ELSIF current_user = 'eqos_panel' THEN
        RAISE EXCEPTION 'the panel disposes only through an accepted proposal'
            USING ERRCODE = '42501';
    END IF;
    RETURN NEW;
END $$;

-- An ACCEPT on a proposal commits only with its one disposition.
CREATE FUNCTION eqos.check_accept_disposed() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, eqos AS $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM eqos.queue_dispositions
                   WHERE evidence_ref = 'decision:' || NEW.id) THEN
        RAISE EXCEPTION 'accepted proposal % has no disposition', NEW.subject_id
            USING ERRCODE = '23514';
    END IF;
    RETURN NULL;
END $$;

-- D4: an interpretation's operands are part of its decided payload.
CREATE FUNCTION eqos.check_operand_decision() RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, eqos AS $$ BEGIN
    PERFORM eqos.lock_subject('INTERPRETATION', NEW.interpretation_id);
    IF EXISTS (SELECT 1 FROM eqos.decisions
               WHERE subject_kind = 'INTERPRETATION' AND subject_id = NEW.interpretation_id) THEN
        RAISE EXCEPTION 'interpretation % is decided', NEW.interpretation_id
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER check_decision ON eqos.decisions;
CREATE TRIGGER check_decision BEFORE INSERT ON eqos.decisions FOR EACH ROW
    WHEN (NEW.subject_kind IN ('REPORT', 'REPORT_VERSION'))
    EXECUTE FUNCTION eqos.check_decision();
CREATE TRIGGER check_decision_subject BEFORE INSERT ON eqos.decisions FOR EACH ROW
    WHEN (NEW.subject_kind IN ('DISPOSITION_PROPOSAL', 'INTERPRETATION'))
    EXECUTE FUNCTION eqos.check_subject_decision();
CREATE TRIGGER check_panel_review BEFORE INSERT ON eqos.decisions
    FOR EACH ROW EXECUTE FUNCTION eqos.check_panel_review();
CREATE CONSTRAINT TRIGGER check_accept_disposed AFTER INSERT ON eqos.decisions
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
    WHEN (NEW.subject_kind = 'DISPOSITION_PROPOSAL' AND NEW.kind = 'ACCEPT')
    EXECUTE FUNCTION eqos.check_accept_disposed();
CREATE TRIGGER check_disposition BEFORE INSERT ON eqos.queue_dispositions
    FOR EACH ROW EXECUTE FUNCTION eqos.check_disposition();
CREATE TRIGGER check_operand_decision BEFORE INSERT ON eqos.interpretation_operands
    FOR EACH ROW EXECUTE FUNCTION eqos.check_operand_decision();
CREATE TRIGGER record_panel_review BEFORE INSERT ON eqos.panel_reviews
    FOR EACH ROW EXECUTE FUNCTION eqos.record_panel_review();
CREATE TRIGGER check_proposal BEFORE INSERT ON eqos.disposition_proposals
    FOR EACH ROW EXECUTE FUNCTION eqos.check_proposal();
CREATE TRIGGER reject_row_mutation BEFORE UPDATE OR DELETE ON eqos.panel_reviews
    FOR EACH ROW EXECUTE FUNCTION eqos.reject_mutation();
CREATE TRIGGER reject_truncate BEFORE TRUNCATE ON eqos.panel_reviews
    FOR EACH STATEMENT EXECUTE FUNCTION eqos.reject_mutation();
CREATE TRIGGER reject_row_mutation BEFORE UPDATE OR DELETE ON eqos.disposition_proposals
    FOR EACH ROW EXECUTE FUNCTION eqos.reject_mutation();
CREATE TRIGGER reject_truncate BEFORE TRUNCATE ON eqos.disposition_proposals
    FOR EACH STATEMENT EXECUTE FUNCTION eqos.reject_mutation();

GRANT SELECT ON eqos.panel_reviews, eqos.disposition_proposals
    TO eqos_runtime, eqos_panel, eqos_owner;
GRANT INSERT ON eqos.panel_reviews TO eqos_panel;
GRANT USAGE ON SEQUENCE eqos.panel_reviews_id_seq TO eqos_panel;
GRANT INSERT ON eqos.disposition_proposals TO eqos_runtime;
GRANT USAGE ON SEQUENCE eqos.disposition_proposals_id_seq TO eqos_runtime;
