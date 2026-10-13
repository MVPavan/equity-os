-- D1b Task 13: persist the exact joined vendor-publication digest in every v2 run.
-- Migrations 0001-0006 are immutable; this migration only widens the run pin vocabulary.

ALTER TABLE eqos.run_versions DROP CONSTRAINT run_versions_pin_check;
ALTER TABLE eqos.run_versions ADD CONSTRAINT run_versions_pin_check CHECK (pin IN (
    'dictionary','formula_set','mapping_set','normalisation_policy','extractor_xbrl','extractor_pdf',
    'rounding_policy','definition_set','comparison_policy','alignment_rules','vendor_extractor',
    'source_authority','vendor_publication'));
