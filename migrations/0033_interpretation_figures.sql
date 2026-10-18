-- PREP-2b ruling 2 (plan docs/plans/PREP-2b.md): a FIGURE may cite an interpretation with no
-- run (a comparator's prior figure, the filed tax expense); a run still needs an
-- interpretation. 0001--0032 are immutable.
ALTER TABLE eqos.numeric_claims DROP CONSTRAINT numeric_claims_check6,
    ADD CONSTRAINT numeric_claims_check6 CHECK (citation_kind <> 'FIGURE' OR (
        num_nonnulls(calculation_trace_id, capture_ref_id, anchor, quote, pair_outcome_id,
                     policy_decision_id) = 0
        AND (fact_origin IS NULL) = (fact_origin_id IS NULL)
        AND (run_id IS NULL OR interpretation_id IS NOT NULL)
        AND num_nonnulls(fact_origin_id, interpretation_id) = (NOT unresolved)::int));
