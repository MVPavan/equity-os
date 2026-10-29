"""Screener document discovery over the retained identity-bound probe."""

from collections import Counter

import pytest
from test_nse_documents import read_probe


@pytest.mark.retained
def test_screener_document_links_missing_chips_and_identity() -> None:
    """Source links remain visible across hosts; summaries and an unrelated issuer do not."""
    from fundamentals.ingest.screener_documents import read_screener_documents

    page = read_probe("company_APARINDS_consolidated.html")
    result = read_screener_documents(page, expected_company_id=211)
    assert Counter(str(link.kind) for link in result.links) == {
        "ANNUAL_REPORT": 15,
        "CREDIT_RATING": 6,
        "TRANSCRIPT": 54,
        "PRESENTATION": 50,
    }
    assert Counter(link.host for link in result.links if link.kind == "ANNUAL_REPORT") == {
        "www.bseindia.com": 14,
        "archives.nseindia.com": 1,
    }
    assert Counter(link.host for link in result.links if link.kind == "CREDIT_RATING") == {
        "www.careratings.com": 4,
        "www.icra.in": 2,
    }
    assert result.absent == {"TRANSCRIPT": 9, "PRESENTATION": 13}
    assert result.recordings == 13
    assert all(
        link.host != "www.screener.in" and "/concalls/summary/" not in link.url
        for link in result.links
    )
    assert all(link.period.isdigit() for link in result.links if link.kind == "ANNUAL_REPORT")
    with pytest.raises(ValueError):
        read_screener_documents(page, expected_company_id=212)
