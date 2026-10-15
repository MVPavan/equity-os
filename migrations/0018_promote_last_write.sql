-- D4 phase review fix: a memory PROMOTE is the last ledger or queue write of its transaction
-- (ledger spec §2, amendment A1). 0017 guarded only the support-relevant inserts; this guards
-- every decision subject and the remaining ledger and queue tables. 0001--0017 are immutable.

DROP TRIGGER refuse_after_promote ON eqos.decisions;
CREATE TRIGGER refuse_after_promote BEFORE INSERT ON eqos.decisions
    FOR EACH ROW EXECUTE FUNCTION eqos.refuse_after_promote();

DO $$
DECLARE
    name text;
BEGIN
    FOREACH name IN ARRAY ARRAY['reports', 'report_versions', 'import_sources', 'report_sections',
                                'numeric_claims', 'qa_records', 'legacy_acquisitions',
                                'panel_reviews', 'disposition_proposals', 'memory_items',
                                'memory_supports', 'queue_item_inputs', 'queue_item_traces'] LOOP
        EXECUTE format('CREATE TRIGGER refuse_after_promote BEFORE INSERT ON eqos.%I '
            'FOR EACH ROW EXECUTE FUNCTION eqos.refuse_after_promote()', name);
    END LOOP;
END $$;
