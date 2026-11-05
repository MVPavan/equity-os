"""0006 keeps the store clock protected and first-party sides on filing representations."""

import psycopg
import pytest
from pg_evidence_schema_support import _insert, migrator, runtime, seeded
from psycopg import errors

__all__ = ["runtime", "migrator", "seeded"]
pytestmark = pytest.mark.pg


def test_runtime_cannot_advance_the_protected_store_clock_sequence(
    runtime: psycopg.Connection,
) -> None:
    with pytest.raises(errors.InsufficientPrivilege):
        runtime.execute("SELECT nextval('eqos.store_clock_us')")


@pytest.mark.parametrize("role", ["FIRST_PARTY", "REPORTED_COUNTERPART"])
def test_first_party_sql_side_cannot_use_a_vendor_representation(
    role: str,
    seeded: dict[str, int],
    runtime: psycopg.Connection,
) -> None:
    with pytest.raises(errors.CheckViolation):
        _insert(
            runtime,
            "result_source_values",
            {
                "result_id": seeded["results"],
                "source_role": role,
                "representation": "HTML",
                "source_state": "NO_VALUE",
            },
        )
