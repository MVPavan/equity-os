"""VENDOR-1 P1 closing review, finding 5: fallback joins the results PDF the issuer config
approves, chosen by digest among the acquired ones (spec 2026-11-06-vendor-first §6.8).

The world is ``test_fallback``'s (Apar's Q2 FY26, filing withheld from the vendor run). SYNTHETIC
here: the announcements listing names an earlier "original" results PDF, whose body is a short
synthetic byte string, before the retained PDF the issuer config pins (the "corrected" one); in
the ambiguous case a second URL serves the pinned bytes again. No socket is opened.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from test_fallback import (
    ANNOUNCEMENTS_URL,
    ISIN,
    ISSUER_CONFIG,
    OUTCOMES,
    PDF_URL,
    Q2,
    SYMBOL,
    _Fallback,
    _served,
)

from equity_os.contracts.measurement.canonical import Basis

pytestmark = [pytest.mark.pg, pytest.mark.retained]

BASE = PDF_URL.rsplit("/", 1)[0]
ORIGINAL_URL = f"{BASE}/{SYMBOL}_29102025120000_Original.pdf"
COPY_URL = f"{BASE}/{SYMBOL}_31102025100000_Copy.pdf"
PDF_MEMBER = (
    "SELECT c.blob_sha256 FROM eqos.package_members m "
    "JOIN eqos.capture_refs c ON c.id = m.capture_ref_id WHERE m.representation = 'PDF'"
)


def _announcement(seq: str, url: str, when: str) -> dict[str, str]:
    return {
        "seq_id": seq,
        "symbol": SYMBOL,
        "sm_isin": ISIN,
        "desc": "Outcome of Board Meeting",
        "attchmntText": "Outcome of Board Meeting - Financial Results for the quarter",
        "attchmntFile": url,
        "an_dt": when,
    }


@pytest.mark.parametrize(
    ("second", "joined"),
    [((PDF_URL, "29-Oct-2025 13:33:43"), True), ((COPY_URL, "31-Oct-2025 10:00:00"), False)],
    ids=["corrected-configured", "ambiguous"],
)
def test_fallback_joins_the_pdf_with_the_approved_digest(
    pg_db: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    second: tuple[str, str],
    joined: bool,
) -> None:
    """With the original announced first and the corrected PDF pinned, the corrected member is
    taken and passes intake (a package holds it and the rerun is made); when two acquired PDFs
    carry the pinned digest, none is chosen and the group ends PDF_UNACQUIRED."""
    served = _served()
    pinned = served[PDF_URL]
    served[ORIGINAL_URL] = b"%PDF-1.4 SYNTHETIC original results"
    served[COPY_URL] = pinned
    listed = [_announcement("1", ORIGINAL_URL, "29-Oct-2025 12:00:00")]
    if not joined:
        listed.append(_announcement("2", PDF_URL, "29-Oct-2025 13:33:43"))
    listed.append(_announcement("3", *second))
    served[ANNOUNCEMENTS_URL] = json.dumps(listed).encode()
    digest = yaml.safe_load(ISSUER_CONFIG.read_bytes())["results_pdf"]["sha256"]
    assert hashlib.sha256(pinned).hexdigest() == digest
    with _Fallback(pg_db, tmp_path, monkeypatch, Basis.CONSOLIDATED) as run:
        run.main(served, ISSUER_CONFIG)
        ((_, period, _, outcome, rerun, cells),) = run.read(OUTCOMES)
        members = run.read(PDF_MEMBER)
    assert (period, outcome) == (Q2, "FILING_UNRESOLVED")
    if joined:
        assert rerun is not None and members == [(digest,)]
    else:
        assert rerun is None and members == []
        assert {failure for _, failure in cells.values()} == {"PDF_UNACQUIRED"}
