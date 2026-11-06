-- VENDOR-1 Phase 1 (spec §6.6). 0001--0047 are immutable. An unchecked admission records the
-- check class it was admitted under, so a later counterexample of that class withdraws it for
-- later cutoffs without recomputing the class from files that may have changed since.
ALTER TABLE eqos.fact_admissions
    ADD COLUMN class_digest text CHECK (class_digest ~ '^[0-9a-f]{64}$'),
    ADD CONSTRAINT fact_admissions_unchecked_class CHECK (
        (label = 'VENDORS_AGREE_NOT_CHECKED') = (class_digest IS NOT NULL));
