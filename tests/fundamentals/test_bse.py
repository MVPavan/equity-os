"""BSE source adapter tests: summary mapping, deterministic XBRL parse, and fetch.

The default first-party path is BSE's own ``resultsSnapshot`` summary. It is tested
deterministically against a committed synthetic snapshot fixture (real BSE bytes
are never committed), proving the summary rows map to observations under the
canonical concepts with ``source_id="bse-summary"``, the requested period column is
selected correctly, and a quarter BSE no longer publishes fails closed (zero
observations plus a structured note) rather than fabricating.

The secondary XBRL path runs against hand-built synthetic BSE fixtures:

* an ``in-bse-fin`` Q2 FY25 consolidated instance, and
* an ``in-capmkt`` Q4 FY25 consolidated instance,

proving :meth:`BseSource.parse` reuses the shared context-aware XBRL parser,
handles *both* BSE taxonomies, and stamps every observation with
``source_id="bse-xbrl"``. Its fetch pipeline is exercised offline by
monkeypatching ``urllib.request.urlopen`` so download -> verify -> stamp runs with
no network: success path, fail-closed scope mismatch, URL guard, and the M10
terminal-block / retry classification. A separate opt-in live test
(``RUN_BSE_LIVE=1``) reads the real Titan scrip 500114 results summary.
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from fundamentals.contracts.observation import AccountingFramework, PeriodType, Scope
from fundamentals.contracts.provenance import SourceAnchorType
from fundamentals.extract.xbrl_parser import select_observation
from fundamentals.ingest.bse_source import (
    CONCEPT_CASH_EPS,
    CONCEPT_EPS,
    CONCEPT_NET_PROFIT,
    CONCEPT_NPM,
    CONCEPT_OPM,
    CONCEPT_REVENUE,
    SOURCE_ID,
    SUMMARY_SOURCE_ID,
    BseFetchError,
    BseHardBlockError,
    BseSource,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
BSE_FIN_Q2 = FIXTURES / "synthetic_bse_q2_fy25_consolidated.xml"
BSE_CAPMKT_Q4 = FIXTURES / "synthetic_bse_q4_fy25_consolidated_capmkt.xml"
BSE_SNAPSHOT = FIXTURES / "synthetic_bse_results_snapshot.json"

SCRIP_INFY = "500209"
SCRIP_TITAN = "500114"
SUMMARY_RESULTS_URL = "https://api.bseindia.example/results?scrip=500209"
_SUMMARY_RETRIEVED_AT = datetime(2026, 8, 20, tzinfo=UTC)
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


def _load_snapshot() -> dict[str, Any]:
    return json.loads(BSE_SNAPSHOT.read_text(encoding="utf-8"))


def _parse_summary(period_label: str) -> Any:
    return BseSource.parse_summary(
        _load_snapshot(),
        period_label=period_label,
        scrip_code=SCRIP_INFY,
        results_url=SUMMARY_RESULTS_URL,
        retrieved_at=_SUMMARY_RETRIEVED_AT,
    )


def _by_concept(result: Any, concept: str) -> Any:
    matches = [obs for obs in result.observations if obs.concept_qname == concept]
    assert len(matches) == 1, f"expected exactly one {concept}, got {len(matches)}"
    return matches[0]


# --------------------------------------------------------------------------- #
# Summary path — resultsSnapshot mapping (default first-party path)            #
# --------------------------------------------------------------------------- #


def test_summary_maps_rows_to_canonical_concepts() -> None:
    result = _parse_summary("Jun-26")
    assert result.note is None
    assert result.source_id == SUMMARY_SOURCE_ID
    assert {obs.concept_qname for obs in result.observations} == {
        CONCEPT_REVENUE,
        CONCEPT_NET_PROFIT,
        CONCEPT_EPS,
        CONCEPT_CASH_EPS,
        CONCEPT_OPM,
        CONCEPT_NPM,
    }
    for obs in result.observations:
        assert obs.provenance.source_id == SUMMARY_SOURCE_ID
        assert obs.provenance.anchor_type is SourceAnchorType.XBRL_CONTEXT
        assert obs.provenance.file_sha256 == result.snapshot_sha256
        assert obs.scope is Scope.CONSOLIDATED
        assert obs.accounting_basis is AccountingFramework.IND_AS
        # Summary figures carry no taxonomy identity, so they cannot contradict
        # the NSE XBRL taxonomy during reconciliation.
        assert obs.taxonomy_namespace is None
        assert obs.registry_version is None


def test_summary_monetary_row_is_crore_comparable() -> None:
    revenue = _by_concept(_parse_summary("Jun-26"), CONCEPT_REVENUE)
    assert revenue.normalized_value == Decimal("18101.00")
    assert revenue.normalized_unit == "INR crore"
    assert revenue.currency == "INR"
    assert revenue.scale == 10_000_000  # matches the NSE XBRL crore scale
    assert revenue.decimals == -7
    assert revenue.period_start == date(2026, 4, 1)
    assert revenue.period_end == date(2026, 6, 30)
    profit = _by_concept(_parse_summary("Jun-26"), CONCEPT_NET_PROFIT)
    assert profit.normalized_value == Decimal("1699.00")
    assert profit.normalized_unit == "INR crore"


def test_summary_per_share_and_percent_units() -> None:
    result = _parse_summary("Jun-26")
    eps = _by_concept(result, CONCEPT_EPS)
    assert eps.normalized_value == Decimal("19.15")
    assert eps.normalized_unit == "INR per share"
    assert eps.currency == "INR"
    assert eps.scale == 1
    cash_eps = _by_concept(result, CONCEPT_CASH_EPS)
    assert cash_eps.normalized_value == Decimal("22.40")
    assert cash_eps.normalized_unit == "INR per share"
    opm = _by_concept(result, CONCEPT_OPM)
    assert opm.normalized_value == Decimal("24.50")
    assert opm.normalized_unit == "percent"
    assert opm.currency is None
    npm = _by_concept(result, CONCEPT_NPM)
    assert npm.normalized_value == Decimal("9.39")


def test_summary_selects_requested_period_column() -> None:
    mar = _by_concept(_parse_summary("Mar-26"), CONCEPT_REVENUE)
    assert mar.normalized_value == Decimal("17000.00")
    assert mar.period_start == date(2026, 1, 1)
    assert mar.period_end == date(2026, 3, 31)

    fy = _by_concept(_parse_summary("FY25-26"), CONCEPT_REVENUE)
    assert fy.normalized_value == Decimal("68000.00")
    assert fy.period_start == date(2025, 4, 1)
    assert fy.period_end == date(2026, 3, 31)


def test_summary_historical_quarter_fails_closed_with_note() -> None:
    result = _parse_summary("Dec-25")  # not among the exposed columns
    assert result.observations == ()
    assert result.note is not None
    assert "only exposes latest quarters" in result.note
    assert "Dec-25" in result.note
    assert result.available_periods == ("Jun-26", "Mar-26", "FY25-26")


def test_summary_snapshot_hash_is_stable() -> None:
    first = _parse_summary("Jun-26").snapshot_sha256
    second = _parse_summary("Jun-26").snapshot_sha256
    assert first == second and len(first) == 64


def test_fetch_summary_uses_resultssnapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    snapshot = _load_snapshot()
    calls: dict[str, Any] = {}

    class _FakeClient:
        def __init__(self, *, download_folder: Path) -> None:
            calls["download_folder"] = download_folder

        def resultsSnapshot(self, scripcode: str) -> dict[str, Any]:  # noqa: N802 - lib API name
            calls["scrip"] = scripcode
            return snapshot

        def exit(self) -> None:
            calls["closed"] = True

    source = BseSource(tmp_path, scrip_code=SCRIP_INFY)
    monkeypatch.setattr(source, "_load_bse_client_class", lambda: _FakeClient)

    result = source.fetch_summary(period_label="Jun-26")

    assert calls["scrip"] == SCRIP_INFY
    assert calls["closed"] is True
    revenue = _by_concept(result, CONCEPT_REVENUE)
    assert revenue.normalized_value == Decimal("18101.00")


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
    monkeypatch.setattr(urllib.request, "urlopen", lambda *_a, **_k: _FakeResponse(body))
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
    monkeypatch.setattr(urllib.request, "urlopen", lambda *_a, **_k: _FakeResponse(body))
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
    monkeypatch.setattr(urllib.request, "urlopen", lambda *_a, **_k: _FakeResponse(body))
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


def test_terminal_block_not_retried(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    def _forbidden(*_a: Any, **_k: Any) -> _FakeResponse:
        calls.append(1)
        raise urllib.error.HTTPError(VALID_XBRL_URL, 403, "Forbidden", hdrs=None, fp=None)  # type: ignore[arg-type]

    monkeypatch.setattr(urllib.request, "urlopen", _forbidden)
    source = BseSource(tmp_path, scrip_code=SCRIP_INFY, max_retries=3, retry_backoff_seconds=0.0)

    with pytest.raises(BseHardBlockError):
        source.fetch_quarter(from_date=Q2_START, to_date=Q2_END, xbrl_url=VALID_XBRL_URL)
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
        source.fetch_quarter(from_date=Q2_START, to_date=Q2_END, xbrl_url=VALID_XBRL_URL)
    assert len(calls) == 3  # exhausted bounded retries


# --------------------------------------------------------------------------- #
# Opt-in live BSE ingestion (skipped by default; polite, single filing)       #
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(
    os.environ.get("RUN_BSE_LIVE") != "1",
    reason="live BSE fetch is opt-in; set RUN_BSE_LIVE=1 to run",
)
def test_live_summary_titan_scrip_500114(tmp_path: Path) -> None:
    # Reads BSE's real resultsSnapshot for Titan; the requested period must be one
    # of the columns BSE currently publishes (override via BSE_SUMMARY_PERIOD).
    source = BseSource(tmp_path, scrip_code=SCRIP_TITAN)
    period = os.environ.get("BSE_SUMMARY_PERIOD")
    if period is None:
        # Discover an exposed period first, then map it.
        probe = source.fetch_summary(period_label="__none__")
        assert probe.available_periods, "resultsSnapshot exposed no periods"
        period = probe.available_periods[0]
    result = source.fetch_summary(period_label=period)
    assert result.source_id == SUMMARY_SOURCE_ID
    assert result.note is None, result.note
    assert result.observations
    revenue = _by_concept(result, CONCEPT_REVENUE)
    assert revenue.normalized_value > Decimal("0")  # plausibility, not audit
