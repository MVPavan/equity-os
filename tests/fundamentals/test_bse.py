"""BSE source adapter tests: deterministic parse + offline fetch pipeline.

The deterministic suites run against hand-built synthetic BSE fixtures (real BSE
bytes are never committed):

* an ``in-bse-fin`` Q2 FY25 consolidated instance, and
* an ``in-capmkt`` Q4 FY25 consolidated instance,

proving :meth:`BseSource.parse` reuses the shared context-aware XBRL parser,
handles *both* BSE taxonomies, and stamps every observation with
``source_id="bse-xbrl"``.

The fetch pipeline is exercised offline by monkeypatching ``urllib.request.urlopen``
so download -> verify -> stamp runs with no network: it pins the success path, the
fail-closed scope mismatch, the URL guard, and the M10 terminal-block / retry
classification. A separate opt-in live test (``RUN_BSE_LIVE=1``) fetches the real
Infosys scrip 500209 filing.
"""

from __future__ import annotations

import hashlib
import os
import urllib.error
import urllib.request
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from fundamentals.contracts.observation import PeriodType, Scope
from fundamentals.contracts.provenance import SourceAnchorType
from fundamentals.extract.xbrl_parser import select_observation
from fundamentals.ingest.bse_source import (
    SOURCE_ID,
    BseFetchError,
    BseHardBlockError,
    BseSource,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
BSE_FIN_Q2 = FIXTURES / "synthetic_bse_q2_fy25_consolidated.xml"
BSE_CAPMKT_Q4 = FIXTURES / "synthetic_bse_q4_fy25_consolidated_capmkt.xml"

SCRIP_INFY = "500209"
VALID_XBRL_URL = (
    "https://www.bseindia.com/XBRLFILES/FourOneUploadDocument/Main_Ind_As_500209_test.xml"
)

_RETRIEVED_AT = datetime(2024, 10, 20, tzinfo=UTC)

FIN_REVENUE = "in-bse-fin:RevenueFromOperations"
FIN_PBT = "in-bse-fin:ProfitBeforeTax"
FIN_PROFIT = "in-bse-fin:ProfitLossForPeriod"
CAPMKT_REVENUE = "in-capmkt:RevenueFromOperations"
CAPMKT_PROFIT = "in-capmkt:ProfitLossForPeriod"

Q2_START = date(2024, 7, 1)
Q2_END = date(2024, 9, 30)
Q4_START = date(2025, 1, 1)
Q4_END = date(2025, 3, 31)
FY25_START = date(2024, 4, 1)
FY25_END = date(2025, 3, 31)


class _FakeResponse:
    """Minimal context-manager stand-in for an ``http.client.HTTPResponse``."""

    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *_: object) -> bool:
        return False

    def read(self) -> bytes:
        return self._body


def _parse(path: Path) -> tuple[Any, ...]:
    xml_bytes = path.read_bytes()
    return BseSource.parse(
        xml_bytes,
        file_sha256=hashlib.sha256(xml_bytes).hexdigest(),
        retrieved_at=_RETRIEVED_AT,
    )


def _select_quarter(observations: tuple[Any, ...], concept: str, start: date, end: date) -> Any:
    return select_observation(
        observations,
        concept_qname=concept,
        scope=Scope.CONSOLIDATED,
        period_type=PeriodType.DURATION,
        period_start=start,
        period_end=end,
    )


# --------------------------------------------------------------------------- #
# Deterministic parse — in-bse-fin taxonomy                                    #
# --------------------------------------------------------------------------- #


def test_parse_in_bse_fin_stamps_bse_source_id() -> None:
    observations = _parse(BSE_FIN_Q2)
    assert observations
    assert all(obs.provenance.source_id == SOURCE_ID for obs in observations)
    revenue = _select_quarter(observations, FIN_REVENUE, Q2_START, Q2_END)
    assert revenue.provenance.anchor_type is SourceAnchorType.XBRL_CONTEXT
    assert revenue.provenance.context_ref == "OneD"
    assert revenue.provenance.file_sha256


def test_parse_in_bse_fin_values_bound_to_quarter() -> None:
    observations = _parse(BSE_FIN_Q2)
    revenue = _select_quarter(observations, FIN_REVENUE, Q2_START, Q2_END)
    pbt = _select_quarter(observations, FIN_PBT, Q2_START, Q2_END)
    profit = _select_quarter(observations, FIN_PROFIT, Q2_START, Q2_END)

    assert revenue.normalized_value == Decimal("40986")
    assert revenue.normalized_unit == "INR crore"
    assert revenue.scope is Scope.CONSOLIDATED
    assert revenue.period_start == Q2_START
    assert revenue.period_end == Q2_END
    assert pbt.normalized_value == Decimal("9253")
    assert profit.normalized_value == Decimal("6516")


# --------------------------------------------------------------------------- #
# Deterministic parse — in-capmkt taxonomy (second BSE namespace)             #
# --------------------------------------------------------------------------- #


def test_parse_in_capmkt_handled_by_registry() -> None:
    observations = _parse(BSE_CAPMKT_Q4)
    assert observations
    assert all(obs.provenance.source_id == SOURCE_ID for obs in observations)
    assert all(obs.registry_version == "in-capmkt/2023-03-31" for obs in observations)

    quarter_revenue = _select_quarter(observations, CAPMKT_REVENUE, Q4_START, Q4_END)
    profit = _select_quarter(observations, CAPMKT_PROFIT, Q4_START, Q4_END)
    assert quarter_revenue.normalized_value == Decimal("40925")
    assert profit.normalized_value == Decimal("7038")


def test_parse_in_capmkt_full_year_distractor_not_selected_as_quarter() -> None:
    observations = _parse(BSE_CAPMKT_Q4)
    # RevenueFromOperations appears under both the Q4 (OneD) and FY25 (FourD)
    # contexts; the quarter key must return 40,925, never the 1,62,990 full year.
    quarter = _select_quarter(observations, CAPMKT_REVENUE, Q4_START, Q4_END)
    full_year = select_observation(
        observations,
        concept_qname=CAPMKT_REVENUE,
        scope=Scope.CONSOLIDATED,
        period_type=PeriodType.DURATION,
        period_start=FY25_START,
        period_end=FY25_END,
    )
    assert quarter.normalized_value == Decimal("40925")
    assert full_year.normalized_value == Decimal("162990")


# --------------------------------------------------------------------------- #
# Offline fetch pipeline (monkeypatched urlopen)                              #
# --------------------------------------------------------------------------- #


def test_fetch_quarter_success_returns_stamped_retrieval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = BSE_FIN_Q2.read_bytes()
    monkeypatch.setattr(
        urllib.request, "urlopen", lambda *_a, **_k: _FakeResponse(body)
    )
    source = BseSource(tmp_path, scrip_code=SCRIP_INFY)

    retrieval = source.fetch_quarter(
        from_date=Q2_START, to_date=Q2_END, consolidated=True, xbrl_url=VALID_XBRL_URL
    )

    assert retrieval.source_id == SOURCE_ID
    assert retrieval.scrip_code == SCRIP_INFY
    assert retrieval.file_sha256 == hashlib.sha256(body).hexdigest()
    assert retrieval.local_path.is_file()
    prov = retrieval.provenance()
    assert prov.source_id == SOURCE_ID
    assert prov.anchor_type is SourceAnchorType.XBRL_CONTEXT

    observations = source.parse(
        retrieval.local_path.read_bytes(),
        file_sha256=retrieval.file_sha256,
        retrieved_at=retrieval.retrieved_at,
    )
    revenue = _select_quarter(observations, FIN_REVENUE, Q2_START, Q2_END)
    assert revenue.normalized_value == Decimal("40986")


def test_fetch_quarter_scope_mismatch_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = BSE_FIN_Q2.read_bytes()  # a CONSOLIDATED instance
    monkeypatch.setattr(
        urllib.request, "urlopen", lambda *_a, **_k: _FakeResponse(body)
    )
    source = BseSource(tmp_path, scrip_code=SCRIP_INFY)
    with pytest.raises(BseFetchError, match="scope"):
        source.fetch_quarter(
            from_date=Q2_START,
            to_date=Q2_END,
            consolidated=False,  # request standalone; download is consolidated
            xbrl_url=VALID_XBRL_URL,
        )


def test_fetch_quarter_wrong_scrip_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = BSE_FIN_Q2.read_bytes()
    monkeypatch.setattr(
        urllib.request, "urlopen", lambda *_a, **_k: _FakeResponse(body)
    )
    source = BseSource(tmp_path, scrip_code="999999")
    with pytest.raises(BseFetchError, match="scrip"):
        source.fetch_quarter(
            from_date=Q2_START, to_date=Q2_END, consolidated=True, xbrl_url=VALID_XBRL_URL
        )


def test_fetch_quarter_rejects_non_bse_url(tmp_path: Path) -> None:
    source = BseSource(tmp_path, scrip_code=SCRIP_INFY)
    with pytest.raises(BseFetchError, match="first-party host"):
        source.fetch_quarter(
            from_date=Q2_START,
            to_date=Q2_END,
            xbrl_url="https://evil.example.com/XBRLFILES/x.xml",
        )


def test_fetch_quarter_rejects_non_https_url(tmp_path: Path) -> None:
    source = BseSource(tmp_path, scrip_code=SCRIP_INFY)
    with pytest.raises(BseFetchError, match="https"):
        source.fetch_quarter(
            from_date=Q2_START,
            to_date=Q2_END,
            xbrl_url="http://www.bseindia.com/XBRLFILES/x.xml",
        )


def test_terminal_block_not_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[int] = []

    def _forbidden(*_a: Any, **_k: Any) -> _FakeResponse:
        calls.append(1)
        raise urllib.error.HTTPError(VALID_XBRL_URL, 403, "Forbidden", hdrs=None, fp=None)  # type: ignore[arg-type]

    monkeypatch.setattr(urllib.request, "urlopen", _forbidden)
    source = BseSource(tmp_path, scrip_code=SCRIP_INFY, max_retries=3, retry_backoff_seconds=0.0)

    with pytest.raises(BseHardBlockError):
        source.fetch_quarter(
            from_date=Q2_START, to_date=Q2_END, xbrl_url=VALID_XBRL_URL
        )
    assert calls == [1]  # hard block surfaced on first attempt, never retried


def test_transient_error_retries_then_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[int] = []

    def _timeout(*_a: Any, **_k: Any) -> _FakeResponse:
        calls.append(1)
        raise urllib.error.URLError("temporary network glitch")

    monkeypatch.setattr(urllib.request, "urlopen", _timeout)
    source = BseSource(tmp_path, scrip_code=SCRIP_INFY, max_retries=3, retry_backoff_seconds=0.0)

    with pytest.raises(BseFetchError):
        source.fetch_quarter(
            from_date=Q2_START, to_date=Q2_END, xbrl_url=VALID_XBRL_URL
        )
    assert len(calls) == 3  # exhausted bounded retries


# --------------------------------------------------------------------------- #
# Opt-in live BSE ingestion (skipped by default; polite, single filing)       #
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(
    os.environ.get("RUN_BSE_LIVE") != "1",
    reason="live BSE fetch is opt-in; set RUN_BSE_LIVE=1 to run",
)
def test_live_fetch_infy_scrip_500209(tmp_path: Path) -> None:
    live_url = os.environ.get("BSE_XBRL_URL")  # optional explicit static link
    source = BseSource(tmp_path, scrip_code=SCRIP_INFY)
    observations = source.fetch_observations(
        from_date=Q2_START, to_date=Q2_END, consolidated=True, xbrl_url=live_url
    )
    assert observations
    assert all(obs.provenance.source_id == SOURCE_ID for obs in observations)
    revenue = _select_quarter(observations, FIN_REVENUE, Q2_START, Q2_END)
    assert revenue.normalized_value > Decimal("30000")  # plausibility, not audit
