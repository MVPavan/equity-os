-- D1b: a queue item's calculation traces are part of its input hash, so they are stored with
-- its other evidence: sealed with the item, append-only, each a real trace. 0001--0007 are
-- immutable.
CREATE TABLE eqos.queue_item_traces (
    id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    item_id                 bigint NOT NULL REFERENCES eqos.queue_items (id),
    calculation_trace_id    bigint NOT NULL REFERENCES eqos.calculation_traces (id),
    UNIQUE (item_id, calculation_trace_id)
);
CREATE TRIGGER check_queue_input_seal BEFORE INSERT ON eqos.queue_item_traces
    FOR EACH ROW EXECUTE FUNCTION eqos.check_queue_input_seal();
CREATE TRIGGER reject_row_mutation BEFORE UPDATE OR DELETE ON eqos.queue_item_traces
    FOR EACH ROW EXECUTE FUNCTION eqos.reject_mutation();
CREATE TRIGGER reject_truncate BEFORE TRUNCATE ON eqos.queue_item_traces
    FOR EACH STATEMENT EXECUTE FUNCTION eqos.reject_mutation();
GRANT SELECT, INSERT ON eqos.queue_item_traces TO eqos_runtime;
GRANT USAGE ON SEQUENCE eqos.queue_item_traces_id_seq TO eqos_runtime;
