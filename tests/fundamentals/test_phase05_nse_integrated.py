"""Slice phase05-s1 acceptance tests: NSE Integrated Filing + in-capmkt versions.

Since Mar-2025 NSE serves quarterly results as SEBI "Integrated Filings". Three
things change versus the shipped in-bse-fin path: the listing row lives at
``/integrated-filing-results`` (not ``financial_results``), the instance is
written in a *versioned* ``in-capmkt`` taxonomy, and the context entity is
identified by BSE scrip under SEBI's ``ScripCode`` scheme.

Every fixture here is synthetic — symbol ``SYNTH``, scrip ``999001``, quarters in
2027, invented amounts and URLs. Only the public taxonomy/scheme URIs are real.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from fundamentals.api.config import load_config
from fundamentals.extract.xbrl_parser import parse_instance
from fundamentals.extract.xbrl_taxonomies import (
    _ALL_TAXONOMIES,
    IN_CAPMKT_NAMESPACE,
    IN_CAPMKT_REGISTRY_VERSION,
)
from fundamentals.ingest.xbrl_identity import (
    NseEntityIdentityError,
    validate_nse_entity_identities,
)
from fundamentals.ingest.xbrl_source import (
    NseXbrlSource,
    XbrlFetchError,
    XbrlHardBlockError,
)

# --- Synthetic issuer / quarter ----------------------------------------------

SYMBOL = "SYNTH"
SCRIP = "999001"
Q_START = date(2027, 4, 1)
Q_END = date(2027, 6, 30)
QE_DATE = "30-JUN-2027"
BROADCAST_RAW = "24-Jul-2027 18:33:13"
BROADCAST_AT = datetime(2027, 7, 24, 18, 33, 13, tzinfo=UTC)

PRIOR_Q_START = date(2027, 1, 1)
PRIOR_Q_END = date(2027, 3, 31)

# --- Public taxonomy / scheme identifiers ------------------------------------

IN_CAPMKT_PREFIX = "in-capmkt"
IN_CAPMKT_2025 = "http://www.sebi.gov.in/xbrl/2025-01-31/in-capmkt"
IN_CAPMKT_2026 = "http://www.sebi.gov.in/xbrl/2026-01-31/in-capmkt"
SEBI_SCRIP_SCHEME = "http://www.sebi.gov.in/in-capmkt/ScripCode"
UNKNOWN_SCHEME = "http://www.example.invalid/SomeOtherScheme"

REVENUE_CONCEPT = "in-capmkt:RevenueFromOperations"
CONSOLIDATED_TEXT = "Consolidated"
STANDALONE_TEXT = "Standalone"

# --- Synthetic listing values -------------------------------------------------

FAKE_BASE_URL = "https://nse.example/api"
INTEGRATED_PATH = "/integrated-filing-results"
INDAS_XBRL_URL = "https://archives.example/INTEGRATED_FILING_INDAS_999001_A.xml"
INDAS_XBRL_URL_B = "https://archives.example/INTEGRATED_FILING_INDAS_999001_B.xml"
GOVERNANCE_XBRL_URL = "https://archives.example/INTEGRATED_FILING_GOVERNANCE_999001.xml"
LEGACY_XBRL_URL = "https://archives.example/legacy_indas_999001.xml"

_SOURCE_ID = "synthetic-integrated"
_SHA = "0" * 64
_RETRIEVED_AT = datetime(2027, 7, 25, tzinfo=UTC)

Row = dict[str, str | None]


# --- Synthetic instance / listing builders ------------------------------------


def _in_capmkt_instance(
    *,
    namespace: str = IN_CAPMKT_2026,
    scope_text: str = CONSOLIDATED_TEXT,
    entity_scheme: str = SEBI_SCRIP_SCHEME,
    entity_id: str = SCRIP,
    start: date = Q_START,
    end: date = Q_END,
) -> bytes:
    """A minimal Integrated-Filing instance: scope, scrip identity, one revenue fact."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"\n'
        f'    xmlns:in-capmkt="{namespace}">\n'
        '  <xbrli:context id="OneD">\n'
        f'    <xbrli:entity><xbrli:identifier scheme="{entity_scheme}">{entity_id}'
        "</xbrli:identifier></xbrli:entity>\n"
        f"    <xbrli:period><xbrli:startDate>{start.isoformat()}</xbrli:startDate>"
        f"<xbrli:endDate>{end.isoformat()}</xbrli:endDate></xbrli:period>\n"
        "  </xbrli:context>\n"
        '  <xbrli:unit id="INR"><xbrli:measure>iso4217:INR</xbrli:measure></xbrli:unit>\n'
        f'  <in-capmkt:NatureOfReportStandaloneConsolidated contextRef="OneD">{scope_text}'
        "</in-capmkt:NatureOfReportStandaloneConsolidated>\n"
        '  <in-capmkt:RevenueFromOperations contextRef="OneD" unitRef="INR" decimals="0">'
        "1234500000</in-capmkt:RevenueFromOperations>\n"
        "</xbrli:xbrl>\n"
    ).encode()


def _integrated_row(
    *,
    consolidated: str | None = CONSOLIDATED_TEXT,
    xbrl: str | None = INDAS_XBRL_URL,
    qe_date: str = QE_DATE,
) -> Row:
    """An ``/integrated-filing-results`` row shaped like NSE's (no fromDate/isin)."""
    return {
        "symbol": SYMBOL,
        "qe_Date": qe_date,
        "consolidated": consolidated,
        "xbrl": xbrl,
        "broadcast_Date": BROADCAST_RAW,
        "audited": "Un-Audited",
        "seq_Id": "1",
    }


def _financial_results_row(
    *, from_date: str = "01-Jan-2027", to_date: str = "31-Mar-2027", xbrl: str = LEGACY_XBRL_URL
) -> Row:
    """A legacy ``financial_results`` row for the same synthetic issuer."""
    return {
        "fromDate": from_date,
        "toDate": to_date,
        "consolidated": CONSOLIDATED_TEXT,
        "indAs": "Ind-AS New",
        "xbrl": xbrl,
        "isin": None,
        "relatingTo": "First Quarter",
        "broadCastDate": BROADCAST_RAW,
    }


class _FakeResponse:
    """Stand-in for the response object ``nse``'s private ``_req`` helper returns."""

    def __init__(self, payload: dict[str, list[Row]]) -> None:
        self._payload = payload

    def json(self) -> dict[str, list[Row]]:
        return self._payload


class _FakeIntegratedClient:
    """NSE stand-in exposing ``financial_results``, ``base_url`` and ``_req``."""

    def __init__(
        self,
        *,
        results_rows: list[Row],
        integrated_rows: list[Row] | None = None,
        file_bytes: bytes = b"",
        req_error: Exception | None = None,
    ) -> None:
        self.base_url = FAKE_BASE_URL
        self._results_rows = results_rows
        self._integrated_rows = integrated_rows or []
        self._file_bytes = file_bytes
        self._req_error = req_error
        self.requests: list[tuple[str, dict[str, str] | None]] = []
        self.downloaded: list[str] = []

    def __enter__(self) -> _FakeIntegratedClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def financial_results(self, **_kwargs: object) -> list[Row]:
        return self._results_rows

    def _req(self, url: str, params: dict[str, str] | None = None) -> _FakeResponse:
        self.requests.append((url, params))
        if self._req_error is not None:
            raise self._req_error
        return _FakeResponse({"data": self._integrated_rows})

    def download_document(self, url: str, folder: Path) -> str:
        self.downloaded.append(url)
        path = Path(folder) / "filing.xml"
        path.write_bytes(self._file_bytes)
        return str(path)


def _install(monkeypatch: pytest.MonkeyPatch, client: _FakeIntegratedClient) -> None:
    """Route ``NseXbrlSource``'s NSE client construction to the fake."""
    monkeypatch.setattr("fundamentals.ingest.xbrl_source.NSE", lambda *_a, **_k: client)


def _source(tmp_path: Path, *, accepted: tuple[str, ...] = (SCRIP,)) -> NseXbrlSource:
    """A fail-fast source for the synthetic issuer (no sleeping between retries)."""
    return NseXbrlSource(
        tmp_path, symbol=SYMBOL, accepted_entity_ids=accepted, retry_backoff_seconds=0.0
    )


# --- A. Taxonomy registry ------------------------------------------------------


def test_registry_has_three_in_capmkt_versions() -> None:
    # An unregistered namespace makes parse_instance fail closed, so every
    # in-capmkt revision NSE actually serves must be registered explicitly.
    in_capmkt = [spec for spec in _ALL_TAXONOMIES if spec.prefix == IN_CAPMKT_PREFIX]
    assert len(in_capmkt) == 3
    assert {spec.namespace for spec in in_capmkt} == {
        IN_CAPMKT_NAMESPACE,
        IN_CAPMKT_2025,
        IN_CAPMKT_2026,
    }
    assert {spec.registry_version for spec in in_capmkt} == {
        IN_CAPMKT_REGISTRY_VERSION,
        "in-capmkt/2025-01-31",
        "in-capmkt/2026-01-31",
    }


@pytest.mark.parametrize("namespace", [IN_CAPMKT_2025, IN_CAPMKT_2026], ids=["2025", "2026"])
def test_parse_instance_accepts_versioned_in_capmkt_namespace(namespace: str) -> None:
    # Facts under a versioned in-capmkt namespace must reach the pipeline; an
    # unsupported namespace yields no observation at all (silent data loss).
    result = parse_instance(
        _in_capmkt_instance(namespace=namespace),
        source_id=_SOURCE_ID,
        file_sha256=_SHA,
        retrieved_at=_RETRIEVED_AT,
        taxonomies=_ALL_TAXONOMIES,
    )
    revenue = [obs for obs in result.observations if obs.concept_qname == REVENUE_CONCEPT]
    assert len(revenue) == 1
    assert revenue[0].taxonomy_namespace == namespace
    assert revenue[0].context_ref == "OneD"


# --- C1. Scope verification under in-capmkt ------------------------------------


def test_verify_accepts_consolidated_in_capmkt_instance(tmp_path: Path) -> None:
    # An Integrated Filing declares its scope under in-capmkt, not in-bse-fin;
    # rejecting it would block every post-Mar-2025 quarter from being ingested.
    _source(tmp_path)._verify(_in_capmkt_instance(), from_date=Q_START, to_date=Q_END, isin=None)


def test_verify_rejects_standalone_in_capmkt_instance(tmp_path: Path) -> None:
    # Widening scope detection to in-capmkt must not weaken it: a standalone
    # instance still fails closed. The consolidated control proves the rejection
    # is caused by the scope text, not by an unrecognised namespace.
    source = _source(tmp_path)
    source._verify(_in_capmkt_instance(), from_date=Q_START, to_date=Q_END, isin=None)
    with pytest.raises(XbrlFetchError, match="not a consolidated filing"):
        source._verify(
            _in_capmkt_instance(scope_text=STANDALONE_TEXT),
            from_date=Q_START,
            to_date=Q_END,
            isin=None,
        )


def test_verify_rejects_unaccepted_scrip(tmp_path: Path) -> None:
    # Nothing is inferred: a BSE scrip is only this issuer if the caller said so,
    # so an unconfigured scrip must not pass issuer verification.
    source = _source(tmp_path, accepted=())
    with pytest.raises(XbrlFetchError, match="does not match requested issuer"):
        source._verify(_in_capmkt_instance(), from_date=Q_START, to_date=Q_END, isin=None)


# --- B. Entity identity policy -------------------------------------------------


def test_identity_validator_accepts_sebi_scrip_scheme() -> None:
    # Integrated instances identify the entity by BSE scrip under SEBI's scheme;
    # the identity policy must accept that scheme or no such filing verifies,
    # while the allow-list stays closed: an unknown scheme is still rejected.
    validate_nse_entity_identities({(SEBI_SCRIP_SCHEME, SCRIP)}, {SCRIP})
    with pytest.raises(NseEntityIdentityError, match="not an accepted NSE scheme"):
        validate_nse_entity_identities({(UNKNOWN_SCHEME, SCRIP)}, {SCRIP})


# --- C2/C3. Integrated listing fallback ----------------------------------------


def test_fetch_falls_back_to_integrated_listing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # financial_results carries nothing after Dec-2024 for such issuers; without
    # the fallback the quarter is unfetchable even though NSE publishes it.
    client = _FakeIntegratedClient(
        results_rows=[],
        integrated_rows=[_integrated_row()],
        file_bytes=_in_capmkt_instance(),
    )
    _install(monkeypatch, client)

    retrieval = _source(tmp_path).fetch_consolidated_quarter(from_date=Q_START, to_date=Q_END)

    assert client.requests, "the integrated listing was never requested"
    url, params = client.requests[0]
    assert url.endswith(INTEGRATED_PATH)
    assert params is not None
    assert params["symbol"] == SYMBOL
    assert retrieval.consolidated is True
    assert retrieval.xbrl_url == INDAS_XBRL_URL
    assert retrieval.relating_to == ""
    assert retrieval.filed_at == BROADCAST_AT
    assert (retrieval.from_date, retrieval.to_date) == (Q_START, Q_END)
    assert retrieval.symbol == SYMBOL


def test_fetch_ignores_governance_and_standalone_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # One quarter yields several Integrated rows; picking a governance or
    # standalone attachment would silently ingest the wrong document.
    client = _FakeIntegratedClient(
        results_rows=[],
        integrated_rows=[
            _integrated_row(consolidated=None, xbrl=GOVERNANCE_XBRL_URL),
            _integrated_row(consolidated=STANDALONE_TEXT, xbrl=INDAS_XBRL_URL_B),
            _integrated_row(),
        ],
        file_bytes=_in_capmkt_instance(),
    )
    _install(monkeypatch, client)

    retrieval = _source(tmp_path).fetch_consolidated_quarter(from_date=Q_START, to_date=Q_END)

    assert retrieval.xbrl_url == INDAS_XBRL_URL
    assert client.downloaded == [INDAS_XBRL_URL]


def test_fetch_rejects_ambiguous_integrated_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Two equally plausible consolidated rows must fail closed, never be guessed
    # between; the error has to name the count so the ambiguity is auditable.
    client = _FakeIntegratedClient(
        results_rows=[],
        integrated_rows=[_integrated_row(), _integrated_row(xbrl=INDAS_XBRL_URL_B)],
        file_bytes=_in_capmkt_instance(),
    )
    _install(monkeypatch, client)

    with pytest.raises(XbrlFetchError, match=r"\b2\b"):
        _source(tmp_path).fetch_consolidated_quarter(from_date=Q_START, to_date=Q_END)
    assert client.requests, "the integrated listing was never requested"
    assert client.downloaded == []


def test_fetch_prefers_financial_results_listing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The fallback is strictly additive: when the legacy listing already answers,
    # the extra request must not be made at all (polite, low-volume access).
    client = _FakeIntegratedClient(
        results_rows=[_financial_results_row(from_date="01-Apr-2027", to_date="30-Jun-2027")],
        integrated_rows=[_integrated_row()],
        file_bytes=_in_capmkt_instance(),
        req_error=AssertionError("integrated listing must not be requested"),
    )
    _install(monkeypatch, client)

    retrieval = _source(tmp_path).fetch_consolidated_quarter(from_date=Q_START, to_date=Q_END)

    assert client.requests == []
    assert retrieval.xbrl_url == LEGACY_XBRL_URL


def test_fetch_fails_closed_on_integrated_listing_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A failing listing must produce a typed failure and no retrieval record; a
    # terminal block must stop immediately rather than be retried politely.
    transient = _FakeIntegratedClient(
        results_rows=[],
        integrated_rows=[_integrated_row()],
        file_bytes=_in_capmkt_instance(),
        req_error=TimeoutError("connection timed out"),
    )
    _install(monkeypatch, transient)
    with pytest.raises(XbrlFetchError, match="(?i)integrated") as transient_error:
        _source(tmp_path).fetch_consolidated_quarter(from_date=Q_START, to_date=Q_END)
    assert not isinstance(transient_error.value, XbrlHardBlockError)
    assert transient.downloaded == []

    blocked = _FakeIntegratedClient(
        results_rows=[],
        integrated_rows=[_integrated_row()],
        file_bytes=_in_capmkt_instance(),
        req_error=RuntimeError("403 Forbidden"),
    )
    _install(monkeypatch, blocked)
    with pytest.raises(XbrlHardBlockError):
        _source(tmp_path).fetch_consolidated_quarter(from_date=Q_START, to_date=Q_END)
    assert len(blocked.requests) == 1, "a terminal block must not be retried"


def test_available_quarters_unions_both_listings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Latest-quarter resolution intersects NSE's quarters with BSE's; dropping
    # the Integrated quarters would hide every quarter NSE only serves that way.
    client = _FakeIntegratedClient(
        results_rows=[_financial_results_row()],
        integrated_rows=[_integrated_row()],
        file_bytes=_in_capmkt_instance(),
    )
    _install(monkeypatch, client)

    quarters = _source(tmp_path).available_consolidated_quarters()

    assert (PRIOR_Q_START, PRIOR_Q_END) in quarters
    assert (Q_START, Q_END) in quarters


# --- D. Config ------------------------------------------------------------------

_CONFIG_YAML = """
issuer:
  name: "Synth Industries Limited"
  nse_symbol: "SYNTH"
  entity_scheme: "nse-symbol"

quarter:
  issuer_quarter: "FY28_Q1"
  program_quarter: "QUARTER_1"
  label: "Q1 FY28 (quarter ended 2027-06-30)"
  period_start: "2027-04-01"
  period_end: "2027-06-30"
  knowledge_cutoff: "2027-07-25T00:00:00Z"

raw_dir: "data/raw/synth"
store_db: ":memory:"

results_pdf:
  source_id: "synth-results-pdf"
  source_class: "first_party"
  filename: "synth-results.pdf"
  sha256: "{sha}"

transcript_pdf:
  source_id: "synth-transcript-pdf"
  source_class: "first_party"
  filename: "synth-transcript.pdf"
  sha256: "{sha}"

xbrl:
  source_id: "synth-xbrl"
  mode: "local"
  local_path: "tests/fundamentals/fixtures/synth.xml"
  symbol: "SYNTH"
{accepted}"""


def _write_config(tmp_path: Path, accepted: str) -> Path:
    """Write a synthetic composition-root YAML, optionally with accepted ids."""
    path = tmp_path / "fundamentals.yaml"
    path.write_text(_CONFIG_YAML.format(sha=_SHA, accepted=accepted), encoding="utf-8")
    return path


def test_config_accepted_entity_ids_loads_from_yaml(tmp_path: Path) -> None:
    # The scrip that authorises an Integrated Filing is operator-declared config;
    # it must survive YAML loading, and absent config must stay empty (no default
    # issuer is ever assumed).
    configured = load_config(_write_config(tmp_path, '  accepted_entity_ids: ["999001"]\n'))
    assert configured.xbrl.accepted_entity_ids == (SCRIP,)

    absent = load_config(_write_config(tmp_path, ""))
    assert absent.xbrl.accepted_entity_ids == ()
