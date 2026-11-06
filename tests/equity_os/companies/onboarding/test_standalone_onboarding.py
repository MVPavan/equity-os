"""VENDOR-1 Task 4: a standalone-only issuer onboards on its standalone filings (spec §6.2).

The fixture is Apar's development world with SYNTHETIC edits, all made here in memory from the
gitignored retained originals (nothing vendor- or exchange-published is committed):
- both NSE listings keep only their non-consolidated rows, so the window holds no consolidated
  row;
- each of the two latest standalone listing rows is served a copy of Apar's consolidated
  instance for that period whose ``NatureOfReportStandaloneConsolidated`` facts read
  ``Standalone``, under the standalone source and the row's own URL;
- the Screener page is served at the standalone URL with its ``Consolidated Figures`` marker
  removed (a standalone-only company's page carries no basis marker);
- the Upstox statement is requested with ``type=standalone``; the Tijori page is unchanged (it
  carries both bases' tables).
No socket is opened.
"""

from __future__ import annotations

import json
import re
import shlex
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any

import pytest
from onboarding_support import (
    APAR,
    AS_OF,
    INCOMPLETE,
    OC,
    R,
    S,
    U,
    cli,
    recorded,
    rows,
    world,
    write_root,
)
from pg_support import PgTestDatabase

from equity_os.contracts.measurement.canonical import Basis
from equity_os.interface.entry.cli import main
from equity_os.normalisation.dictionary.applicability import STANDALONE_ONLY_RULE_ID
from equity_os.sourcing.exchange.nse_filings import filing_window, listing_rows

__all__ = ["cli"]
pytestmark = pytest.mark.retained

_NATURE = rb'(NatureOfReportStandaloneConsolidated contextRef="[^"]+">)Consolidated'
_MARKER = rb"Consolidated(\s+)Figures"


def _standalone_world() -> list[dict[str, Any]]:
    """SYNTHETIC: Apar's world as a standalone-only issuer's (module docstring)."""
    served = world(APAR)
    (listing,) = [item for item in served if item["surface"] == "INTEGRATED_FILING_LISTING"]
    integrated = json.loads(listing["body"])["data"]
    standalone_url = {
        row["xbrl"]: other["xbrl"]
        for row in integrated
        for other in integrated
        if row.get("consolidated") == "Consolidated"
        and other.get("consolidated") == "Standalone"
        and (row["qe_Date"], row["type"]) == (other["qe_Date"], other["type"])
    }
    for item in served:
        if item["surface"].endswith("_LISTING"):
            payload = json.loads(item["body"])
            listed = payload["data"] if isinstance(payload, dict) else payload
            kept = [row for row in listed if row.get("consolidated") != "Consolidated"]
            item["body"] = json.dumps(
                {"data": kept} if isinstance(payload, dict) else kept
            ).encode()
        elif item["surface"] == "NSE_XBRL_INSTANCE":
            item["source_id"] = "nse-indas-xbrl-standalone"
            item["url"] = standalone_url[item["url"]]
            item["body"] = re.sub(_NATURE, rb"\1Standalone", item["body"])
        elif item["surface"] == "SCREENER_FINANCIALS":
            item["url"] = item["url"].removesuffix("consolidated/")
            item["body"] = re.sub(_MARKER, rb"\1Figures", item["body"])
        elif item["surface"] == "income-statement":
            item["url"] = item["url"].replace("type=consolidated", "type=standalone")
    return served


def _onboarded(
    served: list[dict[str, Any]], cli: Callable[..., int], tmp_path: Path, capsys: Any
) -> str:
    """Onboard ``served`` (PARTIAL: the PDF is excluded by rule); returns the printed command."""
    capsys.readouterr()
    assert cli(APAR, write_root(tmp_path / "raw", served, APAR)) == INCOMPLETE
    return capsys.readouterr().out.split("compare: ", 1)[1].strip()


@pytest.mark.pg
@pytest.mark.parametrize(
    ("served", "basis", "status"),
    [
        (partial(world, APAR), "CONSOLIDATED", "CONSOLIDATED_AND_STANDALONE"),
        (_standalone_world, "STANDALONE", "STANDALONE_ONLY"),
    ],
    ids=["apar-consolidated", "standalone-only"],
)
def test_the_listings_basis_flows_through_verification_settings_and_ingest(
    served: Callable[[], list[dict[str, Any]]],
    basis: str,
    status: str,
    cli: Callable[..., int],
    pg_db: PgTestDatabase,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Acceptance 4. Any consolidated row keeps Apar on the consolidated path; listings with
    only standalone rows verify the standalone filings and pages, write ``STANDALONE_ONLY``
    from that evidence, and ingest a standalone package and standalone vendor tables only (the
    Tijori page's consolidated tables are never read). Only Upstox differs: its standalone
    request is served Apar's consolidated statement, whose echoed basis refuses it."""
    command = _onboarded(served(), cli, tmp_path, capsys)
    (_, outcome, *_), states = recorded(pg_db)
    assert outcome == OC.PARTIAL.value
    upstox = (
        (S.VERIFIED.value, None)
        if basis == "CONSOLIDATED"
        else (S.UNVERIFIED.value, R.BASIS_UNVERIFIED.value)
    )
    assert states[U.UPSTOX] == upstox
    verified = {U.EXCHANGE, U.XBRL_ENTITY, U.SCREENER, U.TIJORI}
    assert {unit for unit in verified if states[unit] == (S.VERIFIED.value, None)} == verified
    assert rows(pg_db, "SELECT basis_status FROM eqos.entity_basis_status") == [(status,)]
    xbrl_source = f"nse-indas-xbrl-{basis.lower()}"
    assert rows(
        pg_db,
        "SELECT p.basis, c.source_id FROM eqos.filing_packages p "
        "JOIN eqos.package_members m ON m.package_id = p.id "
        "JOIN eqos.capture_refs c ON c.id = m.capture_ref_id",
    ) == [(basis, xbrl_source)]
    attempts = rows(pg_db, "SELECT DISTINCT basis FROM eqos.acquisition_attempts")
    contexts = rows(
        pg_db,
        "SELECT DISTINCT o.native_context->>'basis', c.source_id, o.native_context->>'section' "
        "FROM eqos.occurrences o JOIN eqos.capture_refs c ON c.id = o.capture_ref_id",
    )
    assert attempts == [(basis,)] and {found for found, _, _ in contexts} == {basis}
    scope = "_c" if basis == "CONSOLIDATED" else "_s"
    tijori = {section for _, source, section in contexts if source == "tijori"}
    assert tijori and all(scope in section for section in tijori)
    argv = shlex.split(command)
    assert argv[argv.index("--basis") + 1] == basis.lower()


@pytest.mark.pg
def test_a_standalone_only_issuer_has_no_consolidated_cells_and_no_consolidated_pairing(
    cli: Callable[..., int],
    pg_db: PgTestDatabase,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Acceptance 4. The printed standalone run pairs vendor values only with the standalone
    filing (every vendor side interprets a standalone occurrence); the same command on the
    consolidated basis makes every cell NOT_APPLICABLE by the standalone-only rule, with no
    source value at all, so no consolidated vendor table is paired with anything."""
    argv = shlex.split(_onboarded(_standalone_world(), cli, tmp_path, capsys))[1:]
    assert main(argv) == INCOMPLETE  # the PDF side is excluded by rule
    argv[argv.index("--basis") + 1] = "consolidated"
    assert main(argv) == 0
    (standalone_run, consolidated_run) = [
        run for (run,) in rows(pg_db, "SELECT id FROM eqos.runs ORDER BY id")
    ]
    assert rows(
        pg_db,
        "SELECT DISTINCT basis, applicability, applicability_rule_id, corroboration_status "
        "FROM eqos.results WHERE run_id = %s",
        consolidated_run,
    ) == [("CONSOLIDATED", "NOT_APPLICABLE", STANDALONE_ONLY_RULE_ID, "NOT_APPLICABLE")]
    assert rows(
        pg_db,
        "SELECT count(*) FROM eqos.result_source_values v "
        "JOIN eqos.results r ON r.id = v.result_id WHERE r.run_id = %s",
        consolidated_run,
    ) == [(0,)]
    paired = rows(
        pg_db,
        "SELECT DISTINCT r.basis, i.basis FROM eqos.result_source_values v "
        "JOIN eqos.results r ON r.id = v.result_id "
        "JOIN eqos.interpretations i ON i.id = v.interpretation_id "
        "WHERE r.run_id = %s AND v.source_role = 'INDEPENDENT_VENDOR'",
        standalone_run,
    )
    assert paired == [("STANDALONE", "STANDALONE")]


def test_netweb_s_retained_listings_select_its_standalone_filings() -> None:
    """NETWEB's own listings (spec §6.2: its listing decides) hold only standalone rows, so the
    window is on the standalone basis with two qualifying filings to verify."""
    bodies = {item["surface"]: item["body"] for item in world("NETWEB")}
    window = filing_window(
        listing_rows(bodies["FINANCIAL_RESULTS_LISTING"], bodies["INTEGRATED_FILING_LISTING"]),
        AS_OF,
    )
    assert window.basis is Basis.STANDALONE and not window.consolidated
    assert len(window.filings) >= 2
