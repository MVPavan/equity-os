-- D9 final-review fixes (plan docs/workstreams/data-foundation/plans/D9.md R8, R12).
-- 0001--0031 are immutable.

-- R8: a run's id continues past every run the expiry journal names, which a restored target's
-- own ids lag; the purge role advances the run id sequence before committing a run.
DO $$
BEGIN
    EXECUTE format('GRANT UPDATE ON SEQUENCE %s TO eqos_purge',
        pg_get_serial_sequence('eqos.purge_runs', 'id'));
END;
$$;
