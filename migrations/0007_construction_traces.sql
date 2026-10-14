-- D1b: a selector-operand construction's calculation trace (data spec section 2; D1b cleanup
-- plan design point 7). An interpretation row carries no trace id, so the link is its own
-- append-only table. 0001--0006 are immutable.
CREATE TABLE eqos.construction_traces (
    id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    interpretation_id       bigint NOT NULL UNIQUE REFERENCES eqos.interpretations (id),
    calculation_trace_id    bigint NOT NULL REFERENCES eqos.calculation_traces (id)
);
CREATE TRIGGER reject_row_mutation BEFORE UPDATE OR DELETE ON eqos.construction_traces
    FOR EACH ROW EXECUTE FUNCTION eqos.reject_mutation();
CREATE TRIGGER reject_truncate BEFORE TRUNCATE ON eqos.construction_traces
    FOR EACH STATEMENT EXECUTE FUNCTION eqos.reject_mutation();
GRANT SELECT, INSERT ON eqos.construction_traces TO eqos_runtime;
GRANT USAGE ON SEQUENCE eqos.construction_traces_id_seq TO eqos_runtime;
