-- D1a stage 4a review (plan docs/workstreams/data-foundation/plans/D1a.md, Task 5; findings 3,
-- 6 and 9). 0001 and 0002 are applied and checksum-pinned, so the changes are a new migration.
--
-- 1. eqos.version_pins: the first content hash seen for a versioned artifact (mapping set,
--    normalisation policy; Task 9 adds the comparison policy). A version string reused with
--    other content is drift, refused before any reuse or write. Mirrors eqos.definition_sets.
-- 2. interpretations.reason gains INTERPRETATION_AMBIGUOUS: two mapping entries match one
--    native field, or one construction operand is matched twice in one group. Both fail closed
--    as INVALID with this reason instead of a silent first-match or skip.

CREATE TABLE eqos.version_pins (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    artifact        text NOT NULL,
    version         text NOT NULL,
    content_sha256  text NOT NULL,
    pinned_at       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (artifact, version)
);

CREATE TRIGGER reject_row_mutation BEFORE UPDATE OR DELETE ON eqos.version_pins
    FOR EACH ROW EXECUTE FUNCTION eqos.reject_mutation();
CREATE TRIGGER reject_truncate BEFORE TRUNCATE ON eqos.version_pins
    FOR EACH STATEMENT EXECUTE FUNCTION eqos.reject_mutation();

GRANT SELECT, INSERT ON eqos.version_pins TO eqos_runtime;

ALTER TABLE eqos.interpretations DROP CONSTRAINT interpretations_reason_check;
ALTER TABLE eqos.interpretations ADD CONSTRAINT interpretations_reason_check CHECK (
    reason IN (
        'UNREADABLE_CELL', 'PRECISION_UNSUPPORTED', 'UNIT_MISMATCH', 'INTERPRETATION_AMBIGUOUS')
);
