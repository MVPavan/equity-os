-- D2 Task 4: admission records (data spec §4; plan D2 Task 4). One row per admitted run cell
-- and interpretation in a store; it names the fact row and the run, result, interpretation,
-- occurrence and overlay position that authorized it. Append-only. 0001--0010 are immutable.
CREATE TABLE eqos.fact_admissions (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    store_id            text NOT NULL,
    row_handle          bigint NOT NULL,
    fact_origin         text NOT NULL,
    fact_origin_id      bigint NOT NULL,
    run_id              bigint NOT NULL REFERENCES eqos.runs (id),
    result_id           bigint NOT NULL REFERENCES eqos.results (id),
    interpretation_id   bigint NOT NULL REFERENCES eqos.interpretations (id),
    occurrence_id       bigint NOT NULL REFERENCES eqos.occurrences (id),
    overlay_position    timestamptz NOT NULL,
    bridge_version      text NOT NULL,
    UNIQUE (store_id, result_id, interpretation_id),
    FOREIGN KEY (store_id, row_handle) REFERENCES eqos.fact_rows (target_store, handle),
    FOREIGN KEY (fact_origin, fact_origin_id) REFERENCES eqos.fact_rows (origin, origin_id)
);

CREATE TRIGGER reject_row_mutation BEFORE UPDATE OR DELETE ON eqos.fact_admissions
    FOR EACH ROW EXECUTE FUNCTION eqos.reject_mutation();
CREATE TRIGGER reject_truncate BEFORE TRUNCATE ON eqos.fact_admissions
    FOR EACH STATEMENT EXECUTE FUNCTION eqos.reject_mutation();
GRANT SELECT, INSERT ON eqos.fact_admissions TO eqos_runtime;
GRANT USAGE ON SEQUENCE eqos.fact_admissions_id_seq TO eqos_runtime;
