"""VENDOR-1 P1 closing review, finding 2: a consolidated listing row decides the basis even when
its missing broadcast makes it unusable (spec 2026-11-06-vendor-first §6.2).

The fixture is the standalone-only world of ``test_standalone_onboarding`` (SYNTHETIC edits of
Apar's gitignored retained originals, made in memory), plus one SYNTHETIC consolidated
integrated Financials row for the latest standalone period with no broadcast time. No socket is
opened.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from onboarding_support import APAR, FAILURE, OC, R, cli, recorded, rows, write_root
from pg_support import PgTestDatabase
from test_standalone_onboarding import _standalone_world

__all__ = ["cli"]
pytestmark = [pytest.mark.pg, pytest.mark.retained]


def test_an_unbroadcast_consolidated_row_refuses_rather_than_onboarding_standalone_only(
    cli: Callable[..., int], pg_db: PgTestDatabase, tmp_path: Path
) -> None:
    """The listings show consolidated reporting, so the consolidated path is kept; with no usable
    consolidated filing onboarding refuses for insufficient filings and records no basis status
    (never ``STANDALONE_ONLY``)."""
    served = _standalone_world()
    (item,) = [i for i in served if i["surface"] == "INTEGRATED_FILING_LISTING"]
    payload = json.loads(item["body"])
    latest = next(row for row in payload["data"] if row.get("consolidated") == "Standalone")
    payload["data"].append(dict(latest, consolidated="Consolidated", broadcast_Date=None))
    item["body"] = json.dumps(payload).encode()
    assert cli(APAR, write_root(tmp_path / "raw", served, APAR)) == FAILURE
    record, _ = recorded(pg_db)
    assert record[1:4] == (OC.UNSUPPORTED.value, None, R.INSUFFICIENT_FILINGS.value)
    assert rows(pg_db, "SELECT basis_status FROM eqos.entity_basis_status") == []
