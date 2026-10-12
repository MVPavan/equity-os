-- D1a Task 4 ruling R3 (plan docs/workstreams/data-foundation/plans/D1a.md): a trace operand
-- never records a selection that did not happen. selection_source may be NULL only for a
-- missing operand (source_state other than 'VALUE') or for a computed aggregate or average
-- whose constituents, each with its own source, are in a child trace (operand_trace_id set).
-- 0001 is applied and checksum-pinned, so the change is a new migration.

ALTER TABLE eqos.calculation_trace_operands
    ALTER COLUMN selection_source DROP NOT NULL;

ALTER TABLE eqos.calculation_trace_operands
    ADD CONSTRAINT calculation_trace_operands_selection_provenance CHECK (
        selection_source IS NOT NULL
        OR source_state <> 'VALUE'
        OR operand_trace_id IS NOT NULL
    );
