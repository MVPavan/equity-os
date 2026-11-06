"""VENDOR-1 Phase 3 Task 1: grounding retains candidate bank evidence and nothing else.

HDFCBANK's retained development fixtures stand in for a bank (they are not ICICIBANK evidence):
the master, both listings and the two latest consolidated instances. The fake transport serves
those by URL and answers anything else 404, so the standalone instances and the earlier period's
announcements listing are unavailable. SYNTHETIC additions, made in memory: a second standalone
row for the latest period with the same broadcast and another URL, which ties that group; and
for that period an announcements listing naming one results PDF, a one-page PDF made here.
No socket opens.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any, NoReturn

import pymupdf
import pytest
from onboarding_support import count, rows, world
from pg_support import PgTestDatabase

from equity_os.contracts.measurement.canonical import Representation
from equity_os.contracts.sourcing.source_catalog import BUILTIN_SOURCES, NSE_GROUNDING_XBRL
from equity_os.extraction.packages import member_identity
from equity_os.extraction.packages.capture_intake import RetainedCaptureBinding, authorise
from equity_os.interface.commands.companies import onboard_cli
from equity_os.interface.entry.cli import main
from equity_os.sourcing.documents.first_party_documents import ANNOUNCEMENTS, nse_listing_url
from equity_os.sourcing.exchange import results_filing

pytestmark = [pytest.mark.retained, pytest.mark.pg]

_UNWRITTEN = (
    "reporting_entities",
    "onboarding_records",
    "settings_records",
    "evidence_inputs",
    "document_observations",
    "filing_packages",
    "interpretations",
)
_TIED = "https://nsearchives.nseindia.com/corporate/xbrl/SYNTHETIC_TIE_WEB.xml"
_PDF = "https://nsearchives.nseindia.com/corporate/SYNTHETIC_RESULTS.pdf"
_PDF_TEXT = "Scrip Symbol : HDFCBANK\nStandalone results for the quarter ended June 30, 2026"


def _refuse(*_: object, **__: object) -> NoReturn:
    raise AssertionError("grounding called a validation step")


def _served() -> dict[str, bytes]:
    """HDFCBANK's fixture bodies by URL, the integrated listing carrying the SYNTHETIC tie."""
    served = {item["url"]: item["body"] for item in world("HDFCBANK")}
    (url,) = [u for u in served if "integrated-filing-results" in u]
    listing = json.loads(served[url])
    rows_ = listing["data"] if isinstance(listing, dict) else listing
    (row,) = [
        r for r in rows_ if r["qe_Date"] == "30-JUN-2026" and r["consolidated"] == "Standalone"
    ]
    rows_.append({**row, "xbrl": _TIED})
    served[url] = json.dumps(listing).encode()
    span = (date(2026, 6, 30), date(2026, 7, 25))  # period end to broadcast plus seven days
    announcement = {
        "seq_id": "1",
        "desc": "Financial Result Updates",
        "attchmntText": "Financial Results for the quarter ended June 30, 2026",
        "attchmntFile": _PDF,
        "an_dt": "18-Jul-2026 16:30:00",
    }
    served[nse_listing_url(ANNOUNCEMENTS, "HDFCBANK", *span)] = json.dumps([announcement]).encode()
    document = pymupdf.open()  # type: ignore[no-untyped-call]
    document.new_page().insert_text((72, 72), _PDF_TEXT)
    served[_PDF] = document.tobytes()
    return served


def test_grounding_retains_candidates_without_validation(
    pg_db: PgTestDatabase, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Acquire then replay: captures only, the Banking form named, a tie and missing evidence
    recorded, never defaulted, and no validation step called (F25)."""
    for name, value in pg_db.cli_env().items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(results_filing, "PAUSE_SECONDS", 0)
    for module, names in (
        (onboard_cli, ("discover",)),
        (member_identity, [n for n in dir(member_identity) if n.startswith("verify_")]),
    ):
        for name in names:
            monkeypatch.setattr(module, name, _refuse)
    served, sent = _served(), []

    def send(request: Any) -> tuple[int, bytes]:
        sent.append(request.url)
        return (200, served[request.url]) if request.url in served else (404, b"")

    monkeypatch.setattr(onboard_cli, "live_transport", lambda: send)
    base = ["onboard", "HDFCBANK", "--ground", "--raw-root", str(tmp_path / "raw")]
    base += ["--snapshot-root", str(tmp_path / "snapshots")]

    assert main([*base, "--structure", str(tmp_path / "acquired.json"), "--acquire"]) == 0
    assert main([*base, "--structure", str(tmp_path / "replayed.json"), "--generation", "1"]) == 0

    acquired = json.loads((tmp_path / "acquired.json").read_text())
    assert acquired == json.loads((tmp_path / "replayed.json").read_text())
    assert acquired["isins"] == ["INE040A01034"]
    periods = {p["period_end"]: p for p in acquired["periods"]}
    assert list(periods) == ["2026-06-30", "2026-03-31"]
    by_basis = {(end, i["basis"]): i for end, p in periods.items() for i in p["instances"]}
    assert by_basis["2026-06-30", "Standalone"]["status"] == "UNRESOLVED"
    assert _TIED not in sent
    assert by_basis["2026-03-31", "Standalone"]["status"] == "FETCH_FAILED"
    grounded = []
    for end in periods:
        instance = by_basis[end, "Consolidated"]
        assert instance["forms"] == ["Banking"]
        assert instance["type"] == "Integrated Filing- Financials"
        assert instance["non_numeric"] and instance["facts"] and instance["contexts"]
        grounded.append(instance["sha256"])
    (pdf,) = periods["2026-06-30"]["pdfs"]
    assert pdf["sha256"] == hashlib.sha256(served[_PDF]).hexdigest()
    assert pdf["pages"] == [{"page": 1, "text_layer": True}]
    assert [line["line"] for line in pdf["lines"]] == _PDF_TEXT.splitlines()
    assert periods["2026-03-31"]["pdfs"] == []  # the PDF is absent, the XBRL kept

    stored = rows(
        pg_db,
        "SELECT DISTINCT blob_sha256 FROM eqos.capture_refs WHERE source_id = %s AND surface = %s",
        *NSE_GROUNDING_XBRL,
    )
    assert sorted(sha for (sha,) in stored) == sorted(grounded)
    bodies = {hashlib.sha256(body).hexdigest() for body in served.values()}
    assert set(grounded) <= bodies
    assert all(count(pg_db, table) == 0 for table in _UNWRITTEN)

    binding = RetainedCaptureBinding(
        representation=Representation.XBRL,
        source_id=NSE_GROUNDING_XBRL[0],
        relative_path=Path("xbrl/grounded.xml"),
        expected_sha256=grounded[0],
        filed_at_raw="18-Jul-2026 16:01:12",
    )
    assert authorise(binding, catalog=BUILTIN_SOURCES) is None
