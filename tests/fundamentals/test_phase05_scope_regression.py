"""Regression: a legacy filing states its scope once per context, not once per file.

Slice phase05-s1 moved the consolidated-scope check onto the taxonomy registry
and required exactly one scope element. Real ``in-bse-fin`` filings carry
``NatureOfReportStandaloneConsolidated`` in every duration context (quarter and
year-to-date), so a genuine consolidated filing was rejected as "not a
consolidated filing" and every legacy comparator quarter became unfetchable.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from fundamentals.ingest.xbrl_source import NseXbrlSource, XbrlFetchError

FIN_NS = "http://www.bseindia.com/xbrl/fin/2020-03-31/in-bse-fin"
SYMBOL = "SYNTH"
Q_START = date(2027, 7, 1)
Q_END = date(2027, 9, 30)
YTD_START = date(2027, 4, 1)


def _context(context_id: str, start: date, end: date) -> str:
    return (
        f'  <xbrli:context id="{context_id}">\n'
        "    <xbrli:entity><xbrli:identifier "
        f'scheme="http://www.nseindia.com/NSESymbol">{SYMBOL}</xbrli:identifier></xbrli:entity>\n'
        f"    <xbrli:period><xbrli:startDate>{start.isoformat()}</xbrli:startDate>"
        f"<xbrli:endDate>{end.isoformat()}</xbrli:endDate></xbrli:period>\n"
        "  </xbrli:context>\n"
    )


def _instance(scopes: tuple[tuple[str, str], ...]) -> bytes:
    """A legacy instance whose scope concept appears once per (context, text) pair."""
    scope_lines = "".join(
        f'  <in-bse-fin:NatureOfReportStandaloneConsolidated contextRef="{ref}">'
        f"{text}</in-bse-fin:NatureOfReportStandaloneConsolidated>\n"
        for ref, text in scopes
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"\n'
        f'    xmlns:in-bse-fin="{FIN_NS}">\n'
        + _context("OneD", Q_START, Q_END)
        + _context("FourD", YTD_START, Q_END)
        + scope_lines
        + "</xbrli:xbrl>\n"
    ).encode()


def test_verify_accepts_scope_stated_in_every_context(tmp_path: Path) -> None:
    # Legacy filings repeat the scope per duration context; both say Consolidated,
    # so the filing is consolidated and must not be refused. The two negative
    # controls pin that the relaxed rule still fails closed on disagreement and
    # on a missing scope statement.
    source = NseXbrlSource(tmp_path, symbol=SYMBOL, retry_backoff_seconds=0.0)
    source._verify(
        _instance((("OneD", "Consolidated"), ("FourD", "Consolidated"))),
        from_date=Q_START,
        to_date=Q_END,
    )
    with pytest.raises(XbrlFetchError, match="not a consolidated filing"):
        source._verify(
            _instance((("OneD", "Consolidated"), ("FourD", "Standalone"))),
            from_date=Q_START,
            to_date=Q_END,
        )
    with pytest.raises(XbrlFetchError, match="not a consolidated filing"):
        source._verify(_instance(()), from_date=Q_START, to_date=Q_END)


def test_identity_accepts_bse_hosted_scrip_scheme() -> None:
    # Integrated Filings before the SEBI-hosted taxonomy identify the entity under
    # a BSE-hosted ScripCode scheme URI; the same scrip under either host is the
    # same issuer, while any other scheme stays rejected.
    from fundamentals.ingest.xbrl_identity import (
        NseEntityIdentityError,
        validate_nse_entity_identities,
    )

    scrip = "999001"
    validate_nse_entity_identities(
        {("http://www.bseindia.com/in-capmkt/ScripCode", scrip)}, {scrip}
    )
    validate_nse_entity_identities({("http://www.sebi.gov.in/in-capmkt/ScripCode", scrip)}, {scrip})
    with pytest.raises(NseEntityIdentityError, match="not an accepted NSE scheme"):
        validate_nse_entity_identities({("http://example.invalid/ScripCode", scrip)}, {scrip})
