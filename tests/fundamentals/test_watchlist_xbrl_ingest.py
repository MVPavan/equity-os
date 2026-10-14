"""XBRL-only first-party ingest of the eight non-Apar Stage 1 issuers (D1b.5 prep, Sol D2/D6).

Each issuer's retained Q3 FY25 consolidated XBRL goes through the real ``evidence ingest`` CLI
with its ``retrieval-manifest.json``, whose ``filed_at_nse`` is the ``broadCastDate`` of the
matching row in the retained NSE ``corporates-financial-results`` listing (``nse-listing/``,
retrieved 2026-10-14). The ISIN and NSE symbol are cited to that listing row; the BSE scrip to
the XBRL ``ScripCode``. ETERNAL's XBRL predates the rename and carries ``ZOMATO`` (same ISIN).
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
from vendor_retained_support import RAW_ROOT

from fundamentals.api.cli import main
from fundamentals.contracts.basis_status import BasisStatus
from fundamentals.contracts.canonical import Representation
from fundamentals.contracts.evidence import EligibilityBoundary, FilingFamily
from fundamentals.evidence.capture_intake import parse_filed_at
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.pg.identity_seed import (
    IdentityCitation,
    IssuerIdentityInput,
    seed_issuer_identity,
)

# symbol -> (ISIN from the listing row, BSE scrip from the XBRL ScripCode)
ISSUERS = {
    "LAURUSLABS": ("INE947Q01010", "540222"),
    "MTARTECH": ("INE864I01014", "543270"),
    "THERMAX": ("INE152A01029", "500411"),
    "TITAN": ("INE280A01010", "500114"),
    "HFCL": ("INE548A01028", "500183"),
    "POLYCAB": ("INE455K01017", "542652"),
    "CGPOWER": ("INE067A01029", "500093"),
    "ETERNAL": ("INE758T01015", "543320"),
}
Q3_END = date(2024, 12, 31)
SECOND = timedelta(seconds=1)


def _seed(pool: Any, symbol: str, entry: dict[str, str]) -> int:
    """The issuer identity, cited to its retained listing row and Q3 FY25 XBRL."""
    isin, scrip = ISSUERS[symbol]
    listing = {
        "capture_sha256": entry["listing_sha256"],
        "context_ref": f"seqNumber={entry['listing_seq_number']}",
    }
    xbrl = {"capture_sha256": entry["sha256"], "context_ref": "OneD"}
    identity = IssuerIdentityInput(
        entity_key=symbol,
        display_name=symbol,
        isin=isin,
        share_class="EQUITY",
        nse_symbol=symbol,
        bse_scrip=scrip,
        basis_status=BasisStatus.CONSOLIDATED_AND_STANDALONE,
        fiscal_year_end_month=3,
        citations=(
            IdentityCitation(field="display_name", native_field="symbol", **listing),
            IdentityCitation(field="isin", native_field="isin", **listing),
            IdentityCitation(field="nse_symbol", native_field="symbol", **listing),
            IdentityCitation(field="bse_scrip", native_field="ScripCode", **xbrl),
            IdentityCitation(field="basis_status", native_field="consolidated", **listing),
            IdentityCitation(
                field="fiscal_year_end_month", native_field="DateOfEndOfFinancialYear", **xbrl
            ),
        ),
        content_sha256=hashlib.sha256(f"D1b.5 {symbol} test identity".encode()).hexdigest(),
    )
    with pool.connection() as conn:
        return seed_issuer_identity(conn, identity).entity_ids[symbol]


@pytest.mark.pg
@pytest.mark.retained
def test_xbrl_only_packages_are_eligible_from_their_nse_broadcast(
    pg_db: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every package is stored and eligible one second after its broadcast, not one before."""
    for name, value in pg_db.cli_env().items():
        monkeypatch.setenv(name, value)
    with pg_db.runtime_pool() as pool:
        repository = EvidenceRepository(pool)
        for symbol in ISSUERS:
            manifest = RAW_ROOT / symbol.lower() / "retrieval-manifest.json"
            (entry,) = json.loads(manifest.read_bytes())["entries"]
            entity_id = _seed(pool, symbol, entry)
            inputs, store = tmp_path / symbol / "inputs", tmp_path / symbol / "store"
            for folder in (inputs / "nse", store):
                folder.mkdir(mode=0o700, parents=True)
            shutil.copyfile(
                manifest.parent / "nse" / entry["filename"], inputs / "nse" / entry["filename"]
            )
            argv = [
                *("evidence", "ingest", "--retrieval-manifest", str(manifest)),
                *("--issuer", symbol, "--quarter", "FY25_Q3"),
                *("--period-end", Q3_END.isoformat(), "--basis", "consolidated"),
                *("--raw-root", str(inputs), "--snapshot-root", str(store)),
                *("--member", "xbrl=xbrl-consolidated"),
            ]
            assert main(argv) == 0, symbol

            (package,) = repository.list_packages(entity_id, FilingFamily.FINANCIAL_RESULTS, Q3_END)
            filed = parse_filed_at(entry["filed_at_nse"])
            assert package.knowledge_time == filed, symbol
            assert set(package.members) == {Representation.XBRL}, symbol
            seen = repository.store_clock()
            assert package.eligible(
                EligibilityBoundary(knowledge_cutoff=filed, first_seen_cutoff=seen)
            )
            assert not package.eligible(
                EligibilityBoundary(knowledge_cutoff=filed - SECOND, first_seen_cutoff=seen)
            ), symbol
