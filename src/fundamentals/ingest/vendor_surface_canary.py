"""Capture-yield drift: compare like parser versions and expose missing outcomes."""

from datetime import datetime
from typing import LiteralString

from psycopg_pool import ConnectionPool
from pydantic import BaseModel, ConfigDict

from fundamentals.ingest.vendor_surface_fetch import Site
from fundamentals.store.vendor_values_store import USABLE

# A loss of more than half a request's rows is a strong signal of silent drift.
DROP_FACTOR = 2
NO_BASELINE = "NO_BASELINE"
ROW_COUNT_DROP = "ROW_COUNT_DROP"
MISSING_OUTCOME = "MISSING_OUTCOME"
_YIELD: LiteralString = """
WITH history AS (
    SELECT c.source_id, o.surface, c.request_key, o.row_count, o.recorded_at,
        lag(o.row_count) OVER (PARTITION BY c.source_id,c.request_key,o.surface,o.parser_version
            ORDER BY o.recorded_at,o.id) AS previous,
        lag(o.parser_version) OVER (PARTITION BY c.source_id,c.request_key,o.surface
            ORDER BY o.recorded_at,o.id) AS prior_version,
        row_number() OVER (PARTITION BY c.source_id,c.request_key,o.surface
            ORDER BY o.recorded_at DESC,o.id DESC) AS latest
    FROM eqos.vendor_outcomes o JOIN eqos.capture_refs c ON c.id=o.capture_ref_id
    WHERE o.status=ANY(%s) AND c.source_id=ANY(%s)
)
SELECT source_id,surface,request_key,row_count,previous FROM history
WHERE latest=1 AND recorded_at >= %s
    AND ((previous IS NULL AND prior_version IS NOT NULL) OR row_count * %s < previous)
ORDER BY source_id,surface,request_key
"""
_MISSING: LiteralString = """
SELECT c.source_id, substr(c.surface,4), c.request_key, c.id
FROM eqos.capture_refs c WHERE starts_with(c.surface,'vs.') AND c.source_id=ANY(%s)
    AND c.registered_at >= %s AND NOT EXISTS (
        SELECT 1 FROM eqos.vendor_outcomes o WHERE o.capture_ref_id=c.id)
ORDER BY c.source_id,c.surface,c.request_key,c.id
"""


class Drift(BaseModel):
    """A named check with enough request identity to diagnose its evidence."""

    model_config = ConfigDict(frozen=True)
    site: Site
    surface: str
    request_key: str
    check: str
    detail: str


def yield_drift(pool: ConnectionPool, since: datetime) -> tuple[Drift, ...]:
    """Compare the latest usable yield against its own version's previous yield."""
    found = []
    sites = [site.value for site in Site]
    with pool.connection() as conn:
        rows = conn.execute(
            _YIELD, ([status.value for status in USABLE], sites, since, DROP_FACTOR)
        ).fetchall()
        for site, surface, key, count, previous in rows:
            found.append(
                Drift(
                    site=site,
                    surface=surface,
                    request_key=key,
                    check=NO_BASELINE if previous is None else ROW_COUNT_DROP,
                    detail="first outcome under this parser version"
                    if previous is None
                    else f"{previous} -> {count} rows",
                )
            )
        for site, surface, key, capture in conn.execute(_MISSING, (sites, since)).fetchall():
            found.append(
                Drift(
                    site=site,
                    surface=surface,
                    request_key=key,
                    check=MISSING_OUTCOME,
                    detail=f"capture {capture} has no outcome",
                )
            )
    return tuple(found)
