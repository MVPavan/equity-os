-- D5 generated views (ledger spec O5, §3; plan D5, D1, D2). 0001--0020 are immutable.

-- Status derives at read time from the decision log, as lifecycle.version_status does. A
-- report's versions form one chain in id order (0012, D4), so a version's descendants are its
-- report's later versions.
CREATE VIEW eqos.report_status_view AS
SELECT v.id AS version_id, v.predecessor_id, e.entity_key AS stock, r.period,
    r.kind AS report_kind, v.knowledge_cutoff, v.content_hash,
    CASE
        WHEN h.kind IN ('APPROVE', 'IMPORTED_APPROVAL', 'IMPORT_SEAL') AND EXISTS (
            SELECT 1 FROM eqos.report_versions s JOIN eqos.decisions d
                ON d.subject_kind = 'REPORT_VERSION' AND d.subject_id = s.id
            WHERE s.report_id = v.report_id AND s.id > v.id
              AND d.kind IN ('APPROVE', 'IMPORTED_APPROVAL')) THEN 'SUPERSEDED'
        WHEN h.kind IS NULL THEN 'DRAFT'
        WHEN h.kind = 'SUBMIT' THEN 'IN_REVIEW'
        WHEN h.kind = 'IMPORT_SEAL' THEN 'HISTORICAL'
        WHEN h.kind IN ('APPROVE', 'IMPORTED_APPROVAL') THEN 'APPROVED'
        WHEN h.kind = 'REQUEST_CHANGES' THEN 'CHANGES_REQUESTED'
        WHEN h.kind = 'REJECT' THEN 'REJECTED'
        WHEN h.kind = 'WITHDRAW' THEN 'WITHDRAWN'
    END AS status,
    lv.id AS latest_validation_id, lv.mode AS latest_validation_mode,
    lv.untrusted AS untrusted_claims
FROM eqos.report_versions v
JOIN eqos.reports r ON r.id = v.report_id
JOIN eqos.reporting_entities e ON e.id = r.entity_id
LEFT JOIN LATERAL (SELECT kind FROM eqos.decisions
    WHERE subject_kind = 'REPORT_VERSION' AND subject_id = v.id
    ORDER BY sequence DESC LIMIT 1) h ON true
LEFT JOIN LATERAL (SELECT l.id, l.mode,
        (SELECT count(*) FROM eqos.validation_claim_states s
         WHERE s.validation_id = l.id AND s.claim_id IS NOT NULL AND s.state <> 'MATCH')
        AS untrusted
    FROM eqos.validations l WHERE l.version_id = v.id ORDER BY l.id DESC LIMIT 1) lv ON true;

-- PROMOTED as memory.status.derive_status: head PROMOTE and no promoted successor.
CREATE VIEW eqos.promoted_memory_view AS
SELECT i.id AS item_id, e.entity_key AS stock, i.kind, i.statement, i.epistemic_class,
    i.valid_from, i.valid_to, i.recorded_at
FROM eqos.memory_items i
LEFT JOIN eqos.reporting_entities e ON e.id = i.entity_id
WHERE (SELECT d.kind FROM eqos.decisions d
       WHERE d.subject_kind = 'MEMORY_ITEM' AND d.subject_id = i.id
       ORDER BY d.sequence DESC LIMIT 1) = 'PROMOTE'
  AND NOT EXISTS (SELECT 1 FROM eqos.memory_items s JOIN eqos.decisions d
                  ON d.subject_kind = 'MEMORY_ITEM' AND d.subject_id = s.id AND d.kind = 'PROMOTE'
                  WHERE s.supersedes_item_id = i.id);

-- The reader sees the two views only; they run with the migrator's privileges.
GRANT USAGE ON SCHEMA eqos TO eqos_reader;
GRANT SELECT ON eqos.report_status_view, eqos.promoted_memory_view TO eqos_reader;
