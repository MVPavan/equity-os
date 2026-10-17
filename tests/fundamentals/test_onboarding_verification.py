"""D6 Task 3 (T3): discovery — verification predicates, the filing window and outcome paths.

Predicates are unit-tested over development values; outcome paths run ``main(["onboard", …])``
in replay over ``tmp_path`` roots built by ``onboarding_support``. No socket is opened.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import date
from functools import partial
from pathlib import Path
from typing import Any

import pytest
import stage4_filings
from onboarding_support import (
    APAR,
    APAR_ISIN,
    APAR_SCRIP,
    AS_OF,
    DEV,
    FAILURE,
    INCOMPLETE,
    JUN,
    MAR,
    OC,
    VERIFIED_FIVE,
    R,
    S,
    U,
    cli,
    count,
    edit,
    evidence_counts,
    recorded,
    requested,
    rows,
    synthetic_isin,
    world,
    write_root,
)
from pg_support import PgTestDatabase
from stage4_filings import (
    historical_framework,
    historical_sector_rule,
    onboarding_mapping_set,
    xbrl_admitted,
)

from fundamentals.contracts.entity_identity import IdentifierNamespace
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.contracts.onboarding import OnboardingOutcome, VerificationState, VerificationUnit
from fundamentals.entity import verification
from fundamentals.entity.identity_layers import latest_slice
from fundamentals.entity.verification import (
    VERIFIED,
    financial_rule,
    framework_state,
    normalise_name,
    outcome,
)
from fundamentals.evidence import member_identity
from fundamentals.evidence.member_identity import IdentityVerdict, verify_xbrl_framework
from fundamentals.evidence.xbrl_adapter import XBRL_EXTRACTOR_VERSION, parse_instance
from fundamentals.extract.xbrl_parser import RawXbrlInstance
from fundamentals.ingest.nse_filings import filing_window, listing_rows
from fundamentals.pg.identity_seed import EvidenceInputKind

__all__ = ["cli", "requested"]
HDFCBANK_JUN = DEV / "bank-HDFCBANK/nse/INTEGRATED_FILING_BANKING_1696123_18072026040126_WEB.xml"
IND_AS_ROOT_NAMESPACE = (
    b'xmlns:zz="http://www.sebi.gov.in/xbrl/IntegratedFinance_IndAS/2026-01-31/in-capmkt/'
    b'in-capmkt-ent" '
)
FOREIGN = "https://example.invalid/foreign"


def _dev_filings() -> list[tuple[str, Path]]:
    return [
        (path.parts[-3], path) for path in sorted((DEV / "dev-entry-points").glob("*/nse/*.xml"))
    ]


@pytest.mark.retained
def test_name_normalisation_matches_every_development_master_row_and_filing() -> None:
    """D4.3: the pinned normalisation equates each development company's NSE master name
    with the name its own filing declares (case, punctuation, Ltd/Limited)."""
    master = (DEV / "master" / "EQUITY_L.csv").read_text().splitlines()
    names = {line.split(",")[0]: line.split(",")[1] for line in master[1:]}
    filings = _dev_filings()
    assert len(filings) == 11
    for symbol, path in filings:
        body = path.read_text()
        filed = body.split("NameOfTheCompany", 1)[1].split(">", 1)[1].split("<", 1)[0]
        assert normalise_name(filed) == normalise_name(names[symbol]), symbol
    assert normalise_name("Apar  Industries Ltd.") == normalise_name("APAR INDUSTRIES LIMITED")
    assert normalise_name("Apar Industries Limited") != normalise_name("Apar Industrie Limited")


@pytest.mark.retained
@pytest.mark.parametrize("symbol", ["HDFCBANK", "BAJFINANCE", "HDFCLIFE"])
def test_financial_rule_refuses_bank_nbfc_and_insurer_filings(symbol: str) -> None:
    """Task 0b pin: banks and NBFCs share the in-capmkt-ent xsd name with Ind AS issuers, so
    only the IntegratedFinance_IndAS entry-point namespace separates them."""
    instances = [item for item in world(symbol) if item["surface"] == "NSE_XBRL_INSTANCE"]
    assert len(instances) == 2
    assert not any(financial_rule(item["body"]) for item in instances)


@pytest.mark.retained
def test_financial_rule_admits_every_development_filing() -> None:
    """Every development Ind AS instance (and both Apar instances) carries the signal."""
    bodies = [path.read_bytes() for _, path in _dev_filings()]
    bodies += [item["body"] for item in world(APAR) if item["surface"] == "NSE_XBRL_INSTANCE"]
    assert all(financial_rule(body) for body in bodies)
    ind_as = b"IntegratedFinance_IndAS"
    unknown = bodies[0].replace(ind_as, b"IntegratedFinance_ZZ")
    assert not financial_rule(unknown)  # unknown entry point fails closed


def _retained() -> list[tuple[str, bytes, RawXbrlInstance, date]]:
    """Every distinct (by sha256 of bytes) retained NSE instance: symbol or folder, bytes, the
    instance under the onboarding mapping set, and its declared reporting-period end."""
    paths = sorted(DEV.glob("**/nse/*.xml"))
    paths += sorted((DEV.parent / "watchlist/aparinds/nse").glob("*.xml"))
    distinct = {hashlib.sha256(path.read_bytes()).hexdigest(): path for path in reversed(paths)}
    found = []
    for path in distinct.values():
        body = path.read_bytes()
        instance = parse_instance(body, mapping_set=onboarding_mapping_set())
        spec = instance.taxonomy
        (end,) = {
            date.fromisoformat((fact.raw_text or "").strip())
            for fact in instance.facts
            if fact.namespace_uri == spec.namespace
            and fact.concept_qname.endswith(f":{spec.reporting_period_end_concept}")
        }
        label = path.parts[-3] if "onboarding-dev" in path.parts else APAR
        found.append((label, body, instance, end))
    assert len(found) == 25
    return found


def _marked_bank() -> bytes:
    """R1 (MARKED): a bank filing with an unused IndAS root namespace added, its Banking
    namespaces and content kept."""
    body = HDFCBANK_JUN.read_bytes()
    marked = body.replace(b"<xbrli:xbrl ", b"<xbrli:xbrl " + IND_AS_ROOT_NAMESPACE, 1)
    assert marked != body
    return marked


@pytest.mark.retained
def test_discovery_admits_exactly_the_instances_first_party_ingest_accepts() -> None:
    """eqos-h4h.10: attempt 2 was burned because discovery admitted an Ind AS filing whose XBRL
    ingest then rejected for declaring no framework. Over every distinct retained instance,
    discovery's framework verdict is ingest's own (``first_party_extract._read_xbrl``), and its
    sector and framework gates admit an instance iff the financial rule holds and ingest
    accepts the framework: under extractor v2, the 16 IndAS-form instances of all 11 symbols.
    A bank filing carrying a competing IndAS namespace is refused by both."""
    admitted: list[str] = []
    for label, body, instance, _ in _retained():
        ingest = verify_xbrl_framework(instance, AccountingFramework.IND_AS, body=body).verified
        assert (framework_state(instance, body) == VERIFIED) is ingest, label
        if financial_rule(body) and framework_state(instance, body) == VERIFIED:
            admitted.append(label)
    assert len(admitted) == 16
    assert set(admitted) == {symbol for symbol, _ in _dev_filings()}
    marked = _marked_bank()
    instance = parse_instance(marked, mapping_set=onboarding_mapping_set())
    assert historical_sector_rule(marked)  # the counterexample the conflict clause closes
    assert not financial_rule(marked)
    assert framework_state(instance, marked) != VERIFIED


def _dev_instance(symbol: str, body_edit: tuple[bytes, bytes] = (b"", b"")) -> RawXbrlInstance:
    """A development filing's instance (``body_edit``: SYNTHETIC bytes replaced first)."""
    (path,) = [path for name, path in _dev_filings() if name == symbol]
    body = path.read_bytes().replace(*body_edit) if body_edit[0] else path.read_bytes()
    return parse_instance(body, mapping_set=onboarding_mapping_set())


def _phrase_in_foreign_block() -> RawXbrlInstance:
    """SYNTHETIC: Apar's phrase-bearing facts moved to a foreign-namespace text block."""
    instance = _dev_instance(APAR)
    moved = tuple(
        fact.model_copy(update={"namespace_uri": FOREIGN, "concept_qname": "zz:NotesTextBlock"})
        if "Indian Accounting Standard" in (fact.raw_text or "")
        else fact
        for fact in instance.facts
    )
    return instance.model_copy(update={"facts": moved})


HISTORICAL_FRAMEWORK_CASES: dict[str, tuple[Callable[[], RawXbrlInstance], bool]] = {
    "schema_ref_only": (  # SYNTHETIC: THERMAX (no phrase) under the Ind AS entry point
        lambda: _dev_instance("THERMAX").model_copy(
            update={"schema_refs": ("Ind-AS_entry_point_2020-03-31.xsd",)}
        ),
        True,
    ),
    "phrase_only": (lambda: _dev_instance(APAR), True),
    "structural_only": (lambda: _dev_instance("THERMAX"), False),
    "absent": (
        lambda: _dev_instance("THERMAX", (b"IntegratedFinance_IndAS", b"IntegratedFinance_ZZ")),
        False,
    ),
    "phrase_in_foreign_block": (_phrase_in_foreign_block, False),
}


@pytest.mark.retained
@pytest.mark.parametrize("case", HISTORICAL_FRAMEWORK_CASES)
def test_historical_framework_rule_is_the_attempt_3_rule(case: str) -> None:
    """The frozen D6 attempt-3 framework rule accepts a schemaRef or an own text-block phrase,
    never the IndAS form namespace extractor v2 added."""
    build, accepted = HISTORICAL_FRAMEWORK_CASES[case]
    assert historical_framework(build()) is accepted


@pytest.mark.retained
def test_the_draw_checker_is_independent_of_the_production_rule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D6's recorded attempt-3 draw stays reproducible: the historical prefilter admits the 7
    Apar and LAURUSLABS instances (its framework rule alone 9, adding the two legacy Apar
    ``Ind-AS_entry_point`` instances the sector rule refuses), and production predicates made
    to accept everything change none of its results."""
    retained = _retained()

    def results() -> list[bool]:
        return [xbrl_admitted([(body, end)]) for _, body, _, end in retained]

    before = results()
    admitted = [label for (label, *_), held in zip(retained, before, strict=True) if held]
    framework = [label for label, _, instance, _ in retained if historical_framework(instance)]
    assert len(admitted) == 7 and set(admitted) == {APAR, "LAURUSLABS"}
    assert len(framework) == 9 and set(framework) == {APAR, "LAURUSLABS"}
    accept = IdentityVerdict(verified=True, reason=None, evidence=())
    monkeypatch.setattr(member_identity, "verify_xbrl_framework", lambda *_, **__: accept)
    for module in (verification, stage4_filings):  # also any rebinding inside the checker
        monkeypatch.setattr(module, "financial_rule", lambda _: True, raising=False)
        monkeypatch.setattr(module, "framework_state", lambda *_: VERIFIED, raising=False)
    assert results() == before


def _row(
    end: str, basis: str | None, at: str | None, kind: str = "Integrated Filing- Financials"
) -> dict[str, Any]:
    return {
        "qe_Date": end,
        "consolidated": basis,
        "broadcast_Date": at,
        "type": kind,
        "xbrl": f"x/{end}-{at}.xml",
    }


def _window(*integrated: dict[str, Any], legacy: list[dict[str, Any]] | None = None) -> Any:
    body = json.dumps({"data": list(integrated)}).encode()
    return filing_window(listing_rows(json.dumps(legacy or []).encode(), body), AS_OF)


def test_filing_window_counts_distinct_periods_after_collapse() -> None:
    """D1.3: revisions collapse to the latest broadcast; only consolidated integrated
    Financials rows qualify, counted by distinct period end inside six quarter-ends."""
    jun_a = _row("30-JUN-2026", "Consolidated", "24-Jul-2026 18:33:13")
    jun_b = _row("30-JUN-2026", "Consolidated", "30-Jul-2026 10:00:00")
    mar = _row("31-MAR-2026", "Consolidated", "28-May-2026 20:51:11")
    old = _row("31-MAR-2025", "Consolidated", "14-May-2025 21:31:25")  # outside the window
    two_revisions = _window(jun_a, jun_b)
    assert [f.period_end for f in two_revisions.filings] == [date(2026, 6, 30)]
    assert two_revisions.filings[0].xbrl_url == jun_b["xbrl"]
    assert [f.period_end for f in _window(jun_a, mar, old).filings] == [
        date(2026, 6, 30),
        date(2026, 3, 31),
    ]
    assert _window(jun_a, dict(jun_a, xbrl="other")).tied
    governance = _row("30-JUN-2026", None, "27-Jul-2026 16:14:10", "Integrated Filing- Governance")
    assert not _window(governance).consolidated
    no_time = _window(_row("30-JUN-2026", "Consolidated", None), mar)
    assert [f.period_end for f in no_time.filings] == [date(2026, 3, 31)]
    legacy = {
        "toDate": "31-Mar-2026",
        "consolidated": "Consolidated",
        "broadCastDate": "29-May-2026 10:00:00",
        "xbrl": "l.xml",
    }
    superseded = _window(mar, legacy=[legacy])
    assert superseded.consolidated and not superseded.filings  # a legacy row never qualifies
    standalone = _window(_row("30-JUN-2026", "Standalone", "28-Jul-2026 03:34:26"))
    assert standalone.standalone and not standalone.consolidated


def test_filing_window_counts_a_listed_twice_row_once_and_drops_empty_broadcasts() -> None:
    """D1.3 clarification, one reading with the holdout oracle: rows identical but for an
    ignored field (``seq_Id``) are one filing (no tie), and a missing, empty or blank broadcast
    time leaves its period out."""
    jun = _row("30-JUN-2026", "Consolidated", "24-Jul-2026 18:33:13")
    mar = _row("31-MAR-2026", "Consolidated", "28-May-2026 20:51:11")
    for twice in (_window(jun, dict(jun), mar), _window(jun, jun | {"seq_Id": "2"}, mar)):
        assert not twice.tied
        assert [f.period_end for f in twice.filings] == [date(2026, 6, 30), date(2026, 3, 31)]
    for empty in (None, "", "  "):
        dropped = _window(_row("30-JUN-2026", "Consolidated", empty), mar)
        assert [f.period_end for f in dropped.filings] == [date(2026, 3, 31)], empty


@pytest.mark.parametrize(
    ("states", "expected"),
    [
        ({U.EXCHANGE: S.VERIFIED, U.XBRL_ENTITY: S.VERIFIED}, OC.ONBOARDED),
        (
            {U.EXCHANGE: S.VERIFIED, U.XBRL_ENTITY: S.VERIFIED, U.RESULTS_PDF: S.UNAVAILABLE},
            OC.PARTIAL,
        ),
        (
            {U.EXCHANGE: S.VERIFIED, U.XBRL_ENTITY: S.UNVERIFIED, U.TIJORI: S.UNAVAILABLE},
            OC.UNSUPPORTED,
        ),
        (
            {U.EXCHANGE: S.VERIFIED, U.XBRL_ENTITY: S.VERIFIED, U.TIJORI: S.CONFLICT},
            OC.IDENTITY_CONFLICT,
        ),
        (
            {U.EXCHANGE: S.VERIFIED, U.XBRL_ENTITY: S.UNVERIFIED, U.SCREENER: S.CONFLICT},
            OC.IDENTITY_CONFLICT,
        ),
    ],
)
def test_outcome_rule(
    states: dict[VerificationUnit, VerificationState], expected: OnboardingOutcome
) -> None:
    """D4.3 ``outcome``: conflict beats everything; an unverified anchor is unsupported."""
    assert (
        outcome(
            {unit: (state, None if state is S.VERIFIED else "r") for unit, state in states.items()}
        )[0]
        is expected
    )


# --- outcome paths through main(["onboard", …]) ------------------------------------------------


@pytest.mark.pg
@pytest.mark.retained
def test_apar_onboards_partial_with_only_the_pdf_excluded(
    cli: Callable[..., int], pg_db: PgTestDatabase, tmp_path: Path, requested: list[str]
) -> None:
    """Every identity unit verifies; RESULTS_PDF is excluded by rule, so the outcome is PARTIAL
    (exit 4) and a new entity is keyed by the verified symbol. RESULTS_PDF is never fetched."""
    assert cli(APAR, write_root(tmp_path / "raw", world(APAR), APAR)) == INCOMPLETE
    record, states = recorded(pg_db)
    assert record[1:3] == (OC.PARTIAL.value, None)
    assert {unit for unit, (state, _) in states.items() if state == S.VERIFIED} == VERIFIED_FIVE
    assert states[U.RESULTS_PDF] == (S.UNAVAILABLE.value, R.EXCLUDED_BY_RULE.value)
    (key,) = rows(pg_db, "SELECT entity_key FROM eqos.reporting_entities WHERE id = %s", record[4])
    assert key == (APAR,)
    with pg_db.runtime_pool() as pool, pool.connection() as conn:
        held = {(v.namespace, v.value) for v in latest_slice(conn) if v.entity_id == record[4]}
    assert held == {
        (IdentifierNamespace.ISIN, APAR_ISIN),
        (IdentifierNamespace.NSE_SYMBOL, APAR),
        (IdentifierNamespace.BSE_SCRIP, APAR_SCRIP),
    }
    assert len(requested) == len(world(APAR))
    unlinked = rows(
        pg_db,
        "SELECT count(*) FROM eqos.capture_refs c WHERE NOT EXISTS ("
        "SELECT 1 FROM eqos.evidence_input_captures l WHERE l.capture_ref_id = c.id)",
    )
    assert unlinked == [(0,)]
    kinds = rows(pg_db, "SELECT DISTINCT kind FROM eqos.evidence_inputs")
    assert kinds == [(EvidenceInputKind.DISCOVERY.value,)]


def _two_bse(served: list[dict[str, Any]]) -> None:
    edit(
        served,
        "PeerSmartSearch",
        b'</li>"',
        b'</li><li><a>ZZ<span>ZZ<strong>INE372A01015</strong>&nbsp;532259</span></a></li>"',
    )


def _two_screener(served: list[dict[str, Any]]) -> None:
    edit(
        served,
        "company/search",
        b'}, {"id": null',
        b'}, {"id": 999, "name": "ZZ", "url": "/company/APARINDS/"}, {"id": null',
    )


CONFLICTS = {
    # name: (synthetic edit, conflicting unit, surfaces requested last)
    "two_bse_candidates": (_two_bse, U.EXCHANGE, "PEER_SMART_SEARCH"),
    "master_isin_differs_from_filings": (
        partial(
            edit,
            url_part="EQUITY_L",
            old=APAR_ISIN.encode(),
            new=synthetic_isin("INE372A0199").encode(),
        ),
        U.XBRL_ENTITY,
        "NSE_XBRL_INSTANCE",
    ),
    "wrong_filing_name": (
        partial(edit, url_part=JUN, old=b"APAR INDUSTRIES LIMITED", new=b"ZZ INDUSTRIES LIMITED"),
        U.XBRL_ENTITY,
        "NSE_XBRL_INSTANCE",
    ),
    "scrip_under_nse_scheme": (
        partial(
            edit,
            url_part=MAR,
            old=b"http://www.sebi.gov.in/in-capmkt/ScripCode",
            new=b"http://www.nseindia.com/NSESymbol",
        ),
        U.XBRL_ENTITY,
        "NSE_XBRL_INSTANCE",
    ),
    "two_screener_candidates": (_two_screener, U.SCREENER, "SCREENER_SEARCH"),
    "tijori_wrong_symbol": (
        partial(
            edit, url_part="financials/", old=b'"symbol": "APARINDS"', new=b'"symbol": "ZZAPAR"'
        ),
        U.TIJORI,
        "financials",
    ),
}


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize("case", CONFLICTS)
def test_identity_conflicts_record_high_and_stop(
    case: str,
    cli: Callable[..., int],
    pg_db: PgTestDatabase,
    tmp_path: Path,
    requested: list[str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Contradicting evidence → IDENTITY_CONFLICT (HIGH, exit 5): captures kept under DISCOVERY
    inputs, no entity, no occurrence or interpretation, and no request after the conflict."""
    change, unit, last = CONFLICTS[case]
    served = world(APAR)
    change(served)
    assert cli(APAR, write_root(tmp_path / "raw", served, APAR)) == FAILURE
    record, states = recorded(pg_db)
    assert record[1:3] == (OC.IDENTITY_CONFLICT.value, "HIGH") and record[4] is None
    assert states[unit][0] == S.CONFLICT.value
    later = [
        u
        for u in (U.EXCHANGE, U.SCREENER, U.TIJORI, U.UPSTOX)
        if states[u][0] not in (S.VERIFIED.value, S.CONFLICT.value)
    ]
    assert all(states[u] == (S.UNVERIFIED.value, R.STOPPED_ON_CONFLICT.value) for u in later)
    assert requested[-1] == last
    assert count(pg_db, "reporting_entities") == 0
    assert count(pg_db, "evidence_input_captures") == count(pg_db, "capture_refs") > 0
    assert evidence_counts(pg_db) == (0, 0)
    assert "HIGH" in capsys.readouterr().out


def _two_revisions(served: list[dict[str, Any]]) -> None:
    """SYNTHETIC: an integrated listing holding only two revisions of one period."""
    (item,) = [i for i in served if i["surface"] == "INTEGRATED_FILING_LISTING"]
    item["body"] = json.dumps(
        {
            "data": [
                _row("30-JUN-2026", "Consolidated", "24-Jul-2026 18:33:13"),
                _row("30-JUN-2026", "Consolidated", "30-Jul-2026 10:00:00"),
            ]
        }
    ).encode()


REFUSALS = {
    "HDFCBANK": ("HDFCBANK", None, R.FINANCIAL_OR_UNKNOWN_SECTOR),
    "BAJFINANCE": ("BAJFINANCE", None, R.FINANCIAL_OR_UNKNOWN_SECTOR),
    "HDFCLIFE": ("HDFCLIFE", None, R.FINANCIAL_OR_UNKNOWN_SECTOR),
    "NETWEB": ("NETWEB", None, R.STANDALONE_BASIS),
    "foreign_isin": (
        APAR,
        partial(edit, url_part="EQUITY_L", old=b",INE372A01015,", new=b",USZZ00000001,"),
        R.FOREIGN_ISIN,
    ),
    "two_revisions_one_period": (APAR, _two_revisions, R.INSUFFICIENT_FILINGS),
}


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize("case", REFUSALS)
def test_unsupported_issuers_get_a_reason_and_no_entity(
    case: str, cli: Callable[..., int], pg_db: PgTestDatabase, tmp_path: Path
) -> None:
    """Financial filings fail closed on the entry-point signal (bank filings name the issuer
    in NameOfBank, so the sector rule must refuse them before any name check); standalone-only,
    non-IN and single-period issuers are refused with the reason recorded and nothing else."""
    symbol, change, reason = REFUSALS[case]
    served = world(symbol)
    if change:
        change(served)
    assert cli(symbol, write_root(tmp_path / "raw", served, symbol)) == FAILURE
    record, states = recorded(pg_db)
    assert record[1:5] == (OC.UNSUPPORTED.value, None, reason.value, None)
    assert S.CONFLICT.value not in {state for state, _ in states.values()}
    _nothing_admitted(pg_db)


@pytest.mark.pg
@pytest.mark.retained
def test_apar_without_its_notes_phrase_onboards_on_its_form_declaration(
    cli: Callable[..., int], pg_db: PgTestDatabase, tmp_path: Path
) -> None:
    """Extractor v2: with the latest instance's notes phrase removed (SYNTHETIC), its
    IntegratedFinance_IndAS form still declares Ind AS, so Apar onboards PARTIAL (exit 4) and
    the XBRL is ingested COMPLETE under the current extractor version."""
    served = world(APAR)
    edit(served, JUN, b"Indian Accounting Standard", b"Zz Accounting Standard")
    assert cli(APAR, write_root(tmp_path / "raw", served, APAR)) == INCOMPLETE
    record, _ = recorded(pg_db)
    assert record[1:4] == (OC.PARTIAL.value, None, None)
    assert rows(
        pg_db,
        "SELECT outcome, extractor_version FROM eqos.acquisition_attempts "
        "WHERE representation = 'XBRL' AND statement_family IS NULL",
    ) == [("COMPLETE", XBRL_EXTRACTOR_VERSION)]
    versions = {
        v for (v,) in rows(pg_db, "SELECT DISTINCT extractor_version FROM eqos.occurrences")
    }
    assert {v for v in versions if v.startswith("xbrl-")} == {XBRL_EXTRACTOR_VERSION}


def _nothing_admitted(db: PgTestDatabase) -> None:
    """D4.6: a refused issuer keeps its record and rejection evidence (captures under DISCOVERY
    inputs) but gets no entity, basis status, setting, package, attempt or evidence."""
    assert count(db, "evidence_input_captures") == count(db, "capture_refs") > 0
    admitted = ("reporting_entities", "entity_basis_status", "settings_records", "filing_packages")
    assert [count(db, table) for table in (*admitted, "acquisition_attempts")] == [0] * 5
    assert evidence_counts(db) == (0, 0)


UPSTOX_CASES = {
    "standalone_type": (b'"type":"consolidated"', b'"type":"standalone"', R.BASIS_UNVERIFIED),
    "missing_type": (b'"type":"consolidated",', b"", R.BASIS_UNVERIFIED),
}


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize("case", [*UPSTOX_CASES, "empty_statement"])
def test_upstox_needs_the_consolidated_response_gate(
    case: str, cli: Callable[..., int], pg_db: PgTestDatabase, tmp_path: Path
) -> None:
    """C12: a statement whose echoed type is wrong or missing is BASIS_UNVERIFIED, an empty one
    EMPTY_STATEMENT; Upstox is diagnostic, so the outcome stays PARTIAL."""
    served = world(APAR)
    (item,) = [i for i in served if i["surface"] == "income-statement"]
    if case == "empty_statement":
        payload = json.loads(item["body"])
        payload["data"]["full_statement"] = []
        for series in payload["data"]["income_statement"]:
            for key in series:
                if isinstance(series[key], list):
                    series[key] = []
        item["body"], reason = json.dumps(payload).encode(), R.EMPTY_STATEMENT
    else:
        old, new, reason = UPSTOX_CASES[case]
        compact = json.dumps(json.loads(item["body"]), separators=(",", ":")).encode()
        assert old in compact
        item["body"] = compact.replace(old, new)
    assert cli(APAR, write_root(tmp_path / "raw", served, APAR)) == INCOMPLETE
    record, states = recorded(pg_db)
    assert record[1] == OC.PARTIAL.value
    assert states[U.UPSTOX] == (S.UNVERIFIED.value, reason.value)
    assert {u for u, (s, _) in states.items() if s == S.VERIFIED} == VERIFIED_FIVE - {U.UPSTOX}


@pytest.mark.pg
@pytest.mark.retained
def test_anchor_http_failure_aborts_without_record(
    cli: Callable[..., int], pg_db: PgTestDatabase, tmp_path: Path
) -> None:
    """R-ACQ: an anchor HTTP_403 is unobservable, not absent: abort, exit 5, no record."""
    served = world(APAR)
    served[0]["outcome"] = "HTTP_403"
    assert cli(APAR, write_root(tmp_path / "raw", served, APAR)) == FAILURE
    assert count(pg_db, "onboarding_records") == 0


INSTANCE_SUBSTITUTIONS = {
    # SYNTHETIC: the listing's latest row served another period's or the standalone instance.
    "older_period": lambda served: _serve_as(served, JUN, MAR),
    "standalone": partial(
        edit,
        url_part=JUN,
        old=b'NatureOfReportStandaloneConsolidated contextRef="OneD">Consolidated<',
        new=b'NatureOfReportStandaloneConsolidated contextRef="OneD">Standalone<',
    ),
}


def _serve_as(served: list[dict[str, Any]], url_part: str, other: str) -> None:
    """SYNTHETIC: the response for ``url_part`` carries the ``other`` instance's bytes."""
    (target,) = [item for item in served if url_part in item["url"]]
    (source,) = [item for item in served if other in item["url"]]
    target["body"] = source["body"]


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize("case", INSTANCE_SUBSTITUTIONS)
def test_an_instance_must_declare_its_rows_period_and_consolidated_basis(
    case: str, cli: Callable[..., int], pg_db: PgTestDatabase, tmp_path: Path
) -> None:
    """D2 instance verification: the same company's older-period or standalone instance under
    the latest row contradicts the listing → XBRL_ENTITY CONFLICT before admission (exit 5)."""
    served = world(APAR)
    INSTANCE_SUBSTITUTIONS[case](served)
    assert cli(APAR, write_root(tmp_path / "raw", served, APAR)) == FAILURE
    record, states = recorded(pg_db)
    assert record[1] == OC.IDENTITY_CONFLICT.value and record[4] is None
    assert states[U.XBRL_ENTITY][0] == S.CONFLICT.value
    assert count(pg_db, "reporting_entities") == 0


NATURE = "NatureOfReportStandaloneConsolidated"
NIL = ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:nil="true"'
Change = Callable[[list[dict[str, Any]]], None]


def _append(url_part: str, concept: str, value: str, extra: str) -> Change:
    """SYNTHETIC: a second context-bound ``concept`` fact (``extra``: its text, or NIL) after
    the instance's ``value`` declaration."""
    old = f"{value}</in-capmkt:{concept}>".encode()
    attrs, text = (NIL, "") if extra == NIL else ("", extra)
    fact = f'<in-capmkt:{concept} contextRef="OneD"{attrs}>{text}</in-capmkt:{concept}>'
    return partial(edit, url_part=url_part, old=old, new=old + fact.encode())


def _both(*changes: Change) -> Change:
    """SYNTHETIC: several changes in order."""

    def change(served: list[dict[str, Any]]) -> None:
        for each in changes:
            each(served)

    return change


def _unbound_nature(url_part: str, *contexts: str) -> Change:
    """SYNTHETIC: the report-nature declarations lose their ``contextRef``: the file scope still
    reads, but no context-bound fact declares the nature."""
    return _both(
        *(
            partial(
                edit,
                url_part=url_part,
                old=f'<in-capmkt:{NATURE} contextRef="{context}">'.encode(),
                new=f"<in-capmkt:{NATURE}>".encode(),
            )
            for context in contexts
        )
    )


IDENTITY = {"ISIN": APAR_ISIN, "Symbol": APAR, "ScripCode": APAR_SCRIP}
DECLARATION_DEFECTS = {  # name: (synthetic change, XBRL_ENTITY state, refusal reason)
    **{
        f"{concept}_{kind}": (_append(JUN, concept, value, extra), S.CONFLICT, None)
        for concept, value in IDENTITY.items()
        for kind, extra in (("blank", " \t"), ("nil", NIL))
    },
    "nature_contradicted": (_append(JUN, NATURE, "Consolidated", "Standalone"), S.CONFLICT, None),
    "nature_blank": (_append(JUN, NATURE, "Consolidated", " "), S.CONFLICT, None),
    "nature_nil": (_append(JUN, NATURE, "Consolidated", NIL), S.CONFLICT, None),
    "nature_unbound": (_unbound_nature(JUN, "OneD"), S.UNVERIFIED, R.BASIS_UNVERIFIED),
    # the older instance is judged as the latest is
    "older_symbol_blank": (_append(MAR, "Symbol", APAR, " "), S.CONFLICT, None),
    "older_nature_unbound": (
        _unbound_nature(MAR, "OneD", "FourD"),
        S.UNVERIFIED,
        R.BASIS_UNVERIFIED,
    ),
}


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize("case", DECLARATION_DEFECTS)
def test_discovery_applies_ingest_identity_check_to_both_instances(
    case: str, cli: Callable[..., int], pg_db: PgTestDatabase, tmp_path: Path
) -> None:
    """eqos-h4h.10 r1: every declaration first-party ingest rejects is refused before admission.
    A blank or nil ISIN/Symbol/ScripCode beside the true one, or a contradicting, blank or nil
    context-bound report nature, contradicts the issuer (IDENTITY_CONFLICT, HIGH); no
    context-bound report nature leaves the basis unproven (UNSUPPORTED BASIS_UNVERIFIED). Both
    instances are judged."""
    change, state, reason = DECLARATION_DEFECTS[case]
    served = world(APAR)
    change(served)
    assert cli(APAR, write_root(tmp_path / "raw", served, APAR)) == FAILURE
    record, states = recorded(pg_db)
    if state is S.CONFLICT:
        assert record[1:3] == (OC.IDENTITY_CONFLICT.value, "HIGH")
        assert states[U.XBRL_ENTITY][0] == S.CONFLICT.value
    else:
        assert reason is not None and record[1:4] == (OC.UNSUPPORTED.value, None, reason.value)
        assert states[U.XBRL_ENTITY] == (state.value, reason.value)
    _nothing_admitted(pg_db)
