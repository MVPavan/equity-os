-- RESEARCH-1 Task 2 (docs/plans/RESEARCH-1-falsifier-status.md): a THESIS_CLAIM citation pins an
-- approved thesis claim (its row fixes version and claim) and that version's sealed digest. The
-- sealed digest gains the two columns only for such claims, so every existing digest is
-- unchanged. 0001--0041 are immutable.
ALTER TABLE eqos.numeric_claims
    ADD COLUMN cited_claim_id bigint REFERENCES eqos.numeric_claims (id),
    ADD COLUMN cited_sealed_digest text,
    DROP CONSTRAINT numeric_claims_citation_kind_check,
    ADD CONSTRAINT numeric_claims_citation_kind_check CHECK (citation_kind IN (
        'FIGURE', 'CALCULATION', 'SOURCE_QUOTE', 'COMPARISON', 'POLICY', 'THESIS_CLAIM')),
    DROP CONSTRAINT numeric_claims_check1,
    ADD CONSTRAINT numeric_claims_check1 CHECK (
        (measurement_key IS NULL) = (citation_kind IN ('SOURCE_QUOTE', 'POLICY', 'THESIS_CLAIM'))),
    ADD CONSTRAINT numeric_claims_thesis_claim_check CHECK (citation_kind <> 'THESIS_CLAIM' OR (
        num_nonnulls(source_sha256, fact_origin, fact_origin_id, interpretation_id, run_id,
                     calculation_trace_id, capture_ref_id, anchor, quote, pair_outcome_id,
                     policy_decision_id) = 0
        AND cited_claim_id IS NOT NULL AND cited_sealed_digest IS NOT NULL
        AND NOT unresolved AND value IS NOT NULL)),
    ADD CONSTRAINT numeric_claims_thesis_columns_check CHECK (citation_kind = 'THESIS_CLAIM'
        OR num_nonnulls(cited_claim_id, cited_sealed_digest) = 0);

-- 0012's digest plus, per claim after policy_decision_id, the cited thesis claim and digest.
CREATE OR REPLACE FUNCTION eqos.version_sealed_digest(version bigint) RETURNS text
LANGUAGE sql STABLE AS $$
    SELECT encode(sha256(convert_to(
        (SELECT eqos.enc(v.id::text) || eqos.enc(v.report_id::text)
             || eqos.enc(v.predecessor_id::text) || eqos.enc(v.author)
             || eqos.enc(v.knowledge_cutoff) || eqos.enc(v.pinned_run_ids::text)
             || eqos.enc(v.content_hash) || eqos.enc(v.created_at)
         FROM eqos.report_versions v WHERE v.id = version)
        || (SELECT eqos.enc(count(*)::text) || coalesce(string_agg(
                eqos.enc(s.ordinal::text) || eqos.enc(s.section_key) || eqos.enc(s.body),
                '' ORDER BY s.ordinal), '')
            FROM eqos.report_sections s WHERE s.version_id = version)
        || (SELECT eqos.enc(count(*)::text) || coalesce(string_agg(
                eqos.enc(c.claim_key) || eqos.enc(c.section_id::text)
                || eqos.enc(c.citation_kind) || eqos.enc(c.key_digest)
                || eqos.enc(c.measurement_key) || eqos.enc(c.value_kind) || eqos.enc(c.unit)
                || eqos.enc(c.currency) || eqos.enc(c.scale::text) || eqos.enc(c.value::text)
                || eqos.enc(c.lower_bound::text) || eqos.enc(c.upper_bound::text)
                || eqos.enc(c.horizon) || eqos.enc(c.qualifiers::text)
                || eqos.enc(c.precision::text) || eqos.enc(c.rounding)
                || eqos.enc(c.epistemic_class) || eqos.enc(c.metric) || eqos.enc(c.metric_label)
                || eqos.enc(c.scope) || eqos.enc(c.constant_currency::text)
                || eqos.enc(c.unresolved::text) || eqos.enc(c.source_sha256)
                || eqos.enc(c.fact_origin) || eqos.enc(c.fact_origin_id::text)
                || eqos.enc(c.interpretation_id::text) || eqos.enc(c.run_id::text)
                || eqos.enc(c.calculation_trace_id::text) || eqos.enc(c.capture_ref_id::text)
                || eqos.enc(c.anchor) || eqos.enc(c.quote) || eqos.enc(c.pair_outcome_id::text)
                || eqos.enc(c.policy_decision_id::text)
                || CASE WHEN c.cited_claim_id IS NULL THEN ''
                        ELSE eqos.enc(c.cited_claim_id::text) || eqos.enc(c.cited_sealed_digest)
                   END,
                '' ORDER BY c.claim_key COLLATE "C"), '')
            FROM eqos.numeric_claims c WHERE c.version_id = version)
        || (SELECT eqos.enc(count(*)::text) || coalesce(string_agg(
                eqos.enc(i.source_path) || eqos.enc(i.sha256),
                '' ORDER BY i.source_path COLLATE "C"), '')
            FROM eqos.import_sources i WHERE i.version_id = version),
        'UTF8')), 'hex')
$$;
