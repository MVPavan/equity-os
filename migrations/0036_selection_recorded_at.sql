-- PREP-2/2b phase review r1 #2: a selection's recording time, from the store clock and not
-- the caller's ``selected_at``; a native fact's AS_KNOWN eligibility reads it (legacy-imported
-- selections keep their legacy times). Existing rows get this migration's time. 0001--0035
-- are immutable.
ALTER TABLE eqos.fact_selections
    ADD COLUMN recorded_at timestamptz NOT NULL DEFAULT eqos.store_now();
