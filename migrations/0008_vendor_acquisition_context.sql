-- Admit only the pinned, capture-free vendor acquisition shape required for
-- logical availability. Existing acquisition/extraction, row and role protections stay.
ALTER TABLE eqos.acquisition_attempts
    DROP CONSTRAINT acquisition_attempts_check1;
ALTER TABLE eqos.acquisition_attempts
    ADD CONSTRAINT acquisition_attempts_check1 CHECK (
        stage <> 'ACQUISITION'
        OR extractor_version = ''
        OR (
            representation IN ('HTML', 'JSON')
            AND package_id IS NULL
            AND capture_ref_id IS NULL
            AND extractor_version <> ''
            AND extraction_context_sha256 IS NOT NULL
            AND extraction_context_sha256 ~ '^[0-9a-f]{64}$'
        )
    );
