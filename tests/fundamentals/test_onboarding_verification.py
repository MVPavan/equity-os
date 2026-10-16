"""D6 Task 3 (T3): discovery, verification and the insertion-boundary gate.

Predicates are unit-tested over development values; outcome paths run ``main(["onboard", …])``
in replay over ``tmp_path`` roots built from ``fixtures/onboarding`` (retained originals pinned
by SHA-256, committed rows, labelled synthetic edits). Synthetic identifiers are ``ZZ``-prefixed.
No socket is opened: the only transport is a fake serving the same fixtures.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import shutil
import subprocess
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any

import pytest
import yaml
from evidence_support import CONFIG
from pg_support import PgTestDatabase, create_database, drop_database, mint_name
from retained_support import REPO_ROOT, apar_catalog, seed_apar
from test_evidence_vendor_screener import binding as screener_binding

from fundamentals.api import onboard_cli
from fundamentals.api.cli import main
from fundamentals.canon.dictionary import load_dictionary
from fundamentals.canon.interval import load_rounding_policy
from fundamentals.contracts.basis_status import BasisStatus
from fundamentals.contracts.canonical import Basis, Representation
from fundamentals.contracts.entity_identity import IdentifierNamespace
from fundamentals.contracts.evidence import FilingFamily
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.contracts.onboarding import (
    OnboardingOutcome,
    OnboardingReason,
    VerificationState,
    VerificationUnit,
)
from fundamentals.contracts.source_catalog import VENDOR_SURFACES
from fundamentals.entity.discovery import (
    MANIFEST_NAME,
    DiscoveryManifest,
    ManifestEntry,
    request_key,
)
from fundamentals.entity.entity_map import isin_check_digit
from fundamentals.entity.identity_layers import (
    IdentifierRef,
    IdentityEventKind,
    latest_slice,
    record_event,
)
from fundamentals.entity.verification import financial_rule, normalise_name, outcome
from fundamentals.evidence import vendor_screener
from fundamentals.evidence.capture_intake import RetainedCaptureBinding, RetainedIntake
from fundamentals.evidence.discovery_gate import IneligibleCaptureError
from fundamentals.evidence.first_party_ingest import ingest_first_party
from fundamentals.evidence.mapping import load_mapping_set, load_normalisation_policy
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.evidence.vendor_ingest import VendorIngestRequest, ingest_vendor
from fundamentals.ingest.nse_filings import filing_window, listing_rows
from fundamentals.ingest.screener_financials_models import Section
from fundamentals.pg.identity_seed import (
    EvidenceInputKind,
    IssuerIdentityInput,
    seed_issuer_identity,
)
from fundamentals.store.snapshot_store import DirectoryAnchor, SnapshotStore

FIXTURES = Path(__file__).parent / "fixtures" / "onboarding"
SPEC = yaml.safe_load((FIXTURES / "fixtures.yaml").read_text())
DEV = REPO_ROOT / "data" / "raw" / "onboarding-dev"
U, S, R, OC = VerificationUnit, VerificationState, OnboardingReason, OnboardingOutcome
APAR, APAR_ISIN, APAR_SCRIP = "APARINDS", "INE372A01015", "532259"
JUN, MAR = "1701114", "1675395"  # the two latest consolidated Apar instances (FY27 Q1, FY26 Q4)
AS_OF = date(2026, 10, 16)
FAILURE, INCOMPLETE = 5, 4
VERIFIED_FIVE = {U.EXCHANGE, U.XBRL_ENTITY, U.SCREENER, U.TIJORI, U.UPSTOX}
SENTINEL = "zzSENTINELcredential0123456789"
SYNTHETIC_NOTICE = b"SYNTHETIC identity notice for tests; no exchange published this."


def _isin(body: str) -> str:
    """A synthetic ISIN with a valid check digit."""
    return body + isin_check_digit(body)


ZZ_ISIN = _isin("INZZ0000001")


# --- fixtures: worlds and replay roots -------------------------------------------------------


def world(symbol: str) -> list[dict[str, Any]]:
    """The company's fixture responses with their bytes, retained ones pinned."""
    served = []
    for item in SPEC["companies"][symbol]:
        if "retained" in item:
            path = REPO_ROOT / item["retained"]["path"]
            if not path.is_file():
                pytest.fail(f"retained original missing: {path}", pytrace=False)
            body = path.read_bytes()
            if hashlib.sha256(body).hexdigest() != item["retained"]["sha256"]:
                pytest.fail(f"retained original {path} differs from its pin", pytrace=False)
        else:
            body = (FIXTURES / item["file"]).read_bytes()
            if item.get("gzip"):
                body = gzip.compress(body, mtime=0)
        served.append({**item, "body": body, "outcome": "OK"})
    return served


def edit(served: list[dict[str, Any]], url_part: str, old: bytes, new: bytes) -> None:
    """SYNTHETIC: replace bytes in every response whose URL contains ``url_part``."""
    hits = [item for item in served if url_part in item["url"]]
    assert hits and all(old in item["body"] for item in hits), url_part
    for item in hits:
        item["body"] = item["body"].replace(old, new)


def gunzipped(served: list[dict[str, Any]], url_part: str, change: Callable[[Any], Any]) -> None:
    """SYNTHETIC: rewrite a gzipped JSON response."""
    (item,) = [item for item in served if url_part in item["url"]]
    item["body"] = gzip.compress(
        json.dumps(change(json.loads(gzip.decompress(item["body"])))).encode()
    )


def rename(served: list[dict[str, Any]], old: str, new: str, keep: tuple[str, ...] = ()) -> None:
    """SYNTHETIC: carry ``new`` instead of ``old`` everywhere (URLs too) except ``keep``."""
    for item in served:
        item["url"] = item["url"].replace(old, new)
        if not any(part in item["url"] for part in keep):
            body = item["body"]
            if item.get("gzip"):
                body = gzip.decompress(body).replace(old.encode(), new.encode())
                item["body"] = gzip.compress(body, mtime=0)
            else:
                item["body"] = body.replace(old.encode(), new.encode())


def write_root(root: Path, served: list[dict[str, Any]], symbol: str, generation: int = 1) -> Path:
    """A replay generation in the discovery-manifest format."""
    folder = root / f"gen-{generation}"
    folder.mkdir(parents=True)
    retrieved_at = datetime.fromisoformat(SPEC["retrieved_at"])
    entries = []
    for index, item in enumerate(served):
        name = None
        if item["body"] is not None and item["outcome"] == "OK":
            name = f"{index:02d}.bin"
            (folder / name).write_bytes(item["body"])
        entries.append(
            ManifestEntry(
                request_key=request_key(item["surface"], item["url"]),
                source_id=item["source_id"],
                surface=item["surface"],
                unit=item["unit"],
                url=item["url"],
                filename=name,
                sha256=hashlib.sha256(item["body"]).hexdigest() if name else None,
                bytes=len(item["body"]) if name else None,
                retrieved_at=retrieved_at,
                outcome=item["outcome"],
            )
        )
    manifest = DiscoveryManifest(
        issuer=symbol,
        authorization="test fixtures",
        generation=generation,
        as_of=AS_OF,
        entries=tuple(entries),
    )
    (folder / MANIFEST_NAME).write_text(manifest.model_dump_json(indent=1))
    return root


@pytest.fixture
def cli(
    pg_db: PgTestDatabase, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Callable[..., int]:
    """``main(["onboard", …])`` in replay against this test's database."""
    for name, value in pg_db.cli_env().items():
        monkeypatch.setenv(name, value)

    def run(symbol: str, root: Path, *extra: str) -> int:
        return main(
            [
                "onboard",
                symbol,
                "--raw-root",
                str(root),
                "--snapshot-root",
                str(tmp_path / "snapshots"),
                *extra,
            ]
        )

    return run


@pytest.fixture
def requested(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Surfaces the replay fetch was asked for, in order (a fetch spy)."""
    seen: list[str] = []
    real = onboard_cli.replay_fetch

    def spied(folder: Path) -> Any:
        fetch = real(folder)

        def call(request: Any) -> Any:
            seen.append(request.surface)
            return fetch(request)

        return call

    monkeypatch.setattr(onboard_cli, "replay_fetch", spied)
    return seen


@contextmanager
def fresh_db(pg_template: PgTestDatabase) -> Iterator[PgTestDatabase]:
    """A second fresh database cloned from the session template."""
    name = mint_name(pg_template.settings)
    create_database(pg_template.settings, name, template=pg_template.dbname)
    try:
        yield pg_template.model_copy(update={"dbname": name})
    finally:
        drop_database(pg_template.settings, name)


def rows(db: PgTestDatabase, query: str, *params: object) -> list[tuple[Any, ...]]:
    """Rows of one read on the database."""
    with db.runtime_pool() as pool, pool.connection() as conn:
        return conn.execute(query, params).fetchall()  # type: ignore[arg-type]


def count(db: PgTestDatabase, table: str) -> int:
    """Rows in one ``eqos`` table."""
    return int(rows(db, f"SELECT count(*) FROM eqos.{table}")[0][0])


def recorded(db: PgTestDatabase) -> tuple[tuple[Any, ...], dict[str, tuple[str, str | None]]]:
    """The one onboarding record and its unit states."""
    (record,) = rows(
        db, "SELECT id, outcome, severity, reason, entity_id FROM eqos.onboarding_records"
    )
    states = rows(
        db,
        "SELECT unit, state, reason FROM eqos.namespace_verifications "
        "WHERE onboarding_record_id = %s",
        record[0],
    )
    return record, {unit: (state, reason) for unit, state, reason in states}


def evidence_counts(db: PgTestDatabase) -> tuple[int, int]:
    """Occurrences and interpretations stored."""
    return count(db, "occurrences"), count(db, "interpretations")


# --- predicates (unit, development values) ---------------------------------------------------


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
    assert evidence_counts(pg_db) == (0, 0)


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
            edit, url_part="EQUITY_L", old=APAR_ISIN.encode(), new=_isin("INE372A0199").encode()
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
    assert count(pg_db, "reporting_entities") == count(pg_db, "entity_basis_status") == 0


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


def _without(surface: str) -> tuple[Any, ...]:
    return tuple(item for item in VENDOR_SURFACES if item.surface != surface)


@pytest.mark.pg
@pytest.mark.retained
def test_authority_is_checked_before_each_request(
    cli: Callable[..., int],
    pg_db: PgTestDatabase,
    tmp_path: Path,
    requested: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D4.4: an unregistered vendor surface is NOT_AUTHORISED with no request (PARTIAL); an
    unregistered anchor surface aborts before its transport call, exit 5, no record."""
    root = write_root(tmp_path / "raw", world(APAR), APAR)
    monkeypatch.setattr(onboard_cli, "SURFACES", _without("company_search"))
    assert cli(APAR, root) == INCOMPLETE
    _, states = recorded(pg_db)
    assert states[U.TIJORI] == (S.NOT_AUTHORISED.value, R.NOT_AUTHORISED.value)
    assert "company_search" not in requested and "financials" not in requested
    requested.clear()
    monkeypatch.setattr(onboard_cli, "SURFACES", _without("NSE_XBRL_INSTANCE"))
    assert cli(APAR, root) == FAILURE
    assert "NSE_XBRL_INSTANCE" not in requested
    assert count(pg_db, "onboarding_records") == 1


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


# --- stable ids (C6-C8) -----------------------------------------------------------------------


def _seed(db: PgTestDatabase, key: str, isin: str, nse: str, bse: str) -> int:
    identity = IssuerIdentityInput(
        entity_key=key,
        display_name=f"{key} Synthetic Limited",
        isin=isin,
        share_class="EQUITY",
        nse_symbol=nse,
        bse_scrip=bse,
        basis_status=BasisStatus.CONSOLIDATED_AND_STANDALONE,
        fiscal_year_end_month=3,
        citations=(),
        content_sha256=hashlib.sha256(key.encode()).hexdigest(),
    )
    with db.runtime_pool() as pool, pool.connection() as conn:
        return seed_issuer_identity(conn, identity).entity_ids[key]


def _event(
    db: PgTestDatabase,
    kind: IdentityEventKind,
    on: date,
    ref: tuple[IdentifierNamespace, str],
    new: str,
) -> None:
    """Record a synthetic change of the target currently holding ``ref`` to ``new``."""
    with db.runtime_pool() as pool, pool.connection() as conn:
        conn.autocommit = True
        sha = hashlib.sha256(SYNTHETIC_NOTICE + f"{kind}{new}".encode()).hexdigest()
        notice = conn.execute(
            "INSERT INTO eqos.evidence_inputs (kind, label, content_sha256) "
            "VALUES (%s, %s, %s) RETURNING id",
            (EvidenceInputKind.DISCOVERY.value, "synthetic-notice", sha),
        ).fetchone()
        assert notice is not None
        namespace, value = ref
        (target,) = {
            v.security_id if namespace is IdentifierNamespace.ISIN else v.listing_id
            for v in latest_slice(conn)
            if v.namespace is namespace and v.value == value
        }
        assert target is not None
        held = IdentifierRef(namespace=namespace, target_id=target)
        record_event(conn, kind, on, int(notice[0]), ends=[held], starts=[(held, new)])


def _table_counts(db: PgTestDatabase) -> tuple[int, int, int]:
    return count(db, "reporting_entities"), count(db, "securities"), count(db, "listings")


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize("held", ["isin_under_other_symbol", "symbol_on_other_listing"])
def test_identifiers_held_elsewhere_conflict_without_new_rows(
    held: str, cli: Callable[..., int], pg_db: PgTestDatabase, tmp_path: Path
) -> None:
    """D3.4: the master ISIN under another current symbol, or the symbol on another listing,
    is IDENTITY_CONFLICT and writes no identity row."""
    if held == "isin_under_other_symbol":
        _seed(pg_db, "ZZOTHER", APAR_ISIN, "ZZOTHER", "999001")
    else:
        _seed(pg_db, "ZZOTHER", ZZ_ISIN, APAR, "999001")
    before = _table_counts(pg_db)
    assert cli(APAR, write_root(tmp_path / "raw", world(APAR), APAR)) == FAILURE
    record, states = recorded(pg_db)
    assert record[1] == OC.IDENTITY_CONFLICT.value and states[U.EXCHANGE][0] == S.CONFLICT.value
    assert _table_counts(pg_db) == before


@pytest.mark.pg
@pytest.mark.retained
def test_apar_on_a_seeded_database_resolves_to_its_d1a_ids(
    cli: Callable[..., int], pg_db: PgTestDatabase, tmp_path: Path
) -> None:
    """The seeded D1a layers are reused: same entity, no new identity rows."""
    entity_id = seed_apar(pg_db)
    before = _table_counts(pg_db)
    assert cli(APAR, write_root(tmp_path / "raw", world(APAR), APAR)) == INCOMPLETE
    record, _ = recorded(pg_db)
    assert record[4] == entity_id and _table_counts(pg_db) == before


NEW_SYMBOL, CHANGED_ON = (
    "ZZAPAR",
    date(2026, 6, 1),
)  # between the Mar (28-May) and Jun (24-Jul) filings


@pytest.mark.pg
@pytest.mark.retained
def test_reonboarding_after_isin_and_symbol_change_keeps_ids(
    cli: Callable[..., int], pg_db: PgTestDatabase, tmp_path: Path
) -> None:
    """C6-C8: after an ISIN_CHANGE and a SYMBOL_CHANGE between the two filings, fixtures
    carrying the new values (the older filing still the old ones) re-onboard to the same
    entity, security and listing ids; Upstox verifies against the new ISIN's rows."""
    assert cli(APAR, write_root(tmp_path / "raw1", world(APAR), APAR)) == INCOMPLETE
    first, states = recorded(pg_db)
    assert {u for u, (s, _) in states.items() if s == S.VERIFIED} == VERIFIED_FIVE
    before = _table_counts(pg_db)
    new_isin = _isin("INE372A0199")
    _event(
        pg_db,
        IdentityEventKind.ISIN_CHANGE,
        CHANGED_ON,
        (IdentifierNamespace.ISIN, APAR_ISIN),
        new_isin,
    )
    _event(
        pg_db,
        IdentityEventKind.SYMBOL_CHANGE,
        CHANGED_ON,
        (IdentifierNamespace.NSE_SYMBOL, APAR),
        NEW_SYMBOL,
    )
    served = world(APAR)
    rename(served, APAR_ISIN, new_isin, keep=(MAR,))
    rename(served, APAR, NEW_SYMBOL, keep=(MAR,))
    assert cli(NEW_SYMBOL, write_root(tmp_path / "raw2", served, NEW_SYMBOL)) == INCOMPLETE
    records = rows(pg_db, "SELECT outcome, entity_id FROM eqos.onboarding_records ORDER BY id")
    assert records[-1] == (OC.PARTIAL.value, first[4])
    (latest,) = rows(pg_db, "SELECT id FROM eqos.onboarding_records ORDER BY id DESC LIMIT 1")
    upstox = rows(
        pg_db,
        "SELECT state FROM eqos.namespace_verifications "
        "WHERE onboarding_record_id = %s AND unit = 'UPSTOX'",
        latest[0],
    )
    assert upstox == [(S.VERIFIED.value,)]
    assert _table_counts(pg_db) == before
    with pg_db.runtime_pool() as pool, pool.connection() as conn:
        old = {v.value for v in latest_slice(conn, CHANGED_ON - timedelta(days=1))}
        new = {v.value for v in latest_slice(conn)}
    assert {APAR_ISIN, APAR} <= old and {new_isin, NEW_SYMBOL} <= new and APAR not in new


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize("variant", ["no_event", "post_change_filing_with_old_symbol"])
def test_discovery_across_a_change_needs_the_event_and_the_new_value(
    variant: str, cli: Callable[..., int], pg_db: PgTestDatabase, tmp_path: Path
) -> None:
    """C8: without the recorded event the new symbol conflicts; with it, a post-change filing
    still carrying the old symbol conflicts (expected identity at each filing date)."""
    assert cli(APAR, write_root(tmp_path / "raw1", world(APAR), APAR)) == INCOMPLETE
    served = world(APAR)
    if variant == "no_event":
        rename(served, APAR, NEW_SYMBOL, keep=(MAR,))
    else:
        _event(
            pg_db,
            IdentityEventKind.SYMBOL_CHANGE,
            CHANGED_ON,
            (IdentifierNamespace.NSE_SYMBOL, APAR),
            NEW_SYMBOL,
        )
        rename(served, APAR, NEW_SYMBOL, keep=(MAR, JUN))  # the Jun filing keeps the old symbol
    assert cli(NEW_SYMBOL, write_root(tmp_path / "raw2", served, NEW_SYMBOL)) == FAILURE
    (last,) = rows(pg_db, "SELECT outcome FROM eqos.onboarding_records ORDER BY id DESC LIMIT 1")
    assert last == (OC.IDENTITY_CONFLICT.value,)


@pytest.mark.pg
@pytest.mark.retained
def test_symbol_reuse_resolves_to_the_reusing_listing_and_keeps_its_key(
    cli: Callable[..., int], pg_db: PgTestDatabase, tmp_path: Path
) -> None:
    """Entity A changes ZZOLD → ZZNEW; B's listing takes ZZOLD by SYMBOL_REUSE: onboarding
    ZZOLD resolves to B under B's key. Without B, a new issuer on the once-held ZZOLD conflicts."""
    _seed(pg_db, "ZZOLD", ZZ_ISIN, "ZZOLD", "999001")
    _event(
        pg_db,
        IdentityEventKind.SYMBOL_CHANGE,
        date(2026, 7, 1),
        (IdentifierNamespace.NSE_SYMBOL, "ZZOLD"),
        "ZZNEW",
    )
    served = world(APAR)
    rename(served, APAR, "ZZOLD", keep=(MAR, JUN))  # both filings precede the reuse
    root = write_root(tmp_path / "raw", served, "ZZOLD")
    assert cli("ZZOLD", root) == FAILURE  # once held, no reuse event: conflict
    b = _seed(pg_db, "ZZB", APAR_ISIN, APAR, APAR_SCRIP)
    _event(
        pg_db,
        IdentityEventKind.SYMBOL_REUSE,
        date(2026, 8, 1),
        (IdentifierNamespace.NSE_SYMBOL, APAR),
        "ZZOLD",
    )
    assert cli("ZZOLD", root) == INCOMPLETE
    (last,) = rows(
        pg_db,
        "SELECT r.outcome, r.entity_id, e.entity_key FROM eqos.onboarding_records r "
        "JOIN eqos.reporting_entities e ON e.id = r.entity_id ORDER BY r.id DESC LIMIT 1",
    )
    assert last == (OC.PARTIAL.value, b, "ZZB")


@pytest.mark.pg
@pytest.mark.retained
def test_new_issuer_on_an_occupied_key_gets_a_suffixed_key(
    cli: Callable[..., int], pg_db: PgTestDatabase, tmp_path: Path
) -> None:
    """The key is an internal label: an occupied key yields ``<symbol>-2``, never the occupant."""
    occupant = _seed(pg_db, APAR, ZZ_ISIN, "ZZOTHER", "999001")
    assert cli(APAR, write_root(tmp_path / "raw", world(APAR), APAR)) == INCOMPLETE
    record, _ = recorded(pg_db)
    assert record[4] != occupant
    assert rows(
        pg_db, "SELECT entity_key FROM eqos.reporting_entities WHERE id = %s", record[4]
    ) == [(f"{APAR}-2",)]


# --- the insertion-boundary gate through both real writers ------------------------------------


def _writers(db: PgTestDatabase, tmp_path: Path, snapshots: Path) -> dict[str, Callable[[], Any]]:
    """Ingest the Jun XBRL instance and each discovery capture through the real writers."""
    dictionary = load_dictionary(CONFIG / "dictionary", "v2")
    mapping_set = load_mapping_set(CONFIG / "mappings", "v5", dictionary=dictionary)
    policy = load_normalisation_policy(CONFIG / "normalisation_policy" / "v1.yaml")
    rounding = load_rounding_policy(CONFIG / "rounding_policy" / "v1.yaml")
    (entity_id,) = rows(db, "SELECT id FROM eqos.reporting_entities")[0]
    (jun,) = [item for item in world(APAR) if JUN in item["url"]]
    inputs, store = tmp_path / "inputs", tmp_path / "store"
    (inputs / "nse").mkdir(parents=True)
    store.mkdir(mode=0o700)
    (inputs / "nse" / "jun.xml").write_bytes(jun["body"])
    intake = RetainedIntake(
        bindings=(
            RetainedCaptureBinding(
                representation=Representation.XBRL,
                source_id="nse-indas-xbrl-consolidated",
                relative_path=Path("nse") / "jun.xml",
                expected_sha256=hashlib.sha256(jun["body"]).hexdigest(),
                filed_at_raw="24-Jul-2026 18:33:13",
            ),
        ),
        retrieval_manifest_sha256="0" * 64,
        issuer_config_sha256=None,
        authority_ref="A05-DECISION-004",
        store_anchor=DirectoryAnchor(store),
        input_anchor=DirectoryAnchor(inputs),
    )

    def vendor(surface: str) -> Any:
        (key, capture_id) = rows(
            db, "SELECT request_key, capture_id FROM eqos.capture_refs WHERE surface = %s", surface
        )[0]
        source = rows(db, "SELECT source_id FROM eqos.capture_refs WHERE surface = %s", surface)[0][
            0
        ]

        def extract(body: bytes, *, capture: Any, record: Any, extractor_version: str) -> Any:
            return vendor_screener.extract_screener_page(
                body,
                capture=capture,
                binding=screener_binding(APAR),
                basis=Basis.CONSOLIDATED,
                section=Section.QUARTERS,
                extractor_version=extractor_version,
            )

        with db.runtime_pool() as pool:
            return ingest_vendor(
                VendorIngestRequest(
                    source_id=source,
                    surface=surface,
                    request_key=key,
                    capture_id=capture_id,
                    representation=Representation.HTML,
                    entity_id=entity_id,
                    period_end=date(2026, 6, 30),
                    basis=Basis.CONSOLIDATED,
                    framework=AccountingFramework.IND_AS,
                ),
                extract=extract,
                extractor_version=vendor_screener.EXTRACTOR_VERSION,
                snapshot_store=SnapshotStore(snapshots),
                repository=EvidenceRepository(pool),
                dictionary=dictionary,
                mapping_set=mapping_set,
                policy=policy,
                rounding_policy=rounding,
                fiscal_year_end_month=3,
            )

    def first_party() -> Any:
        with db.runtime_pool() as pool:
            return ingest_first_party(
                intake=intake,
                catalog=apar_catalog(),
                snapshot_store=SnapshotStore(store),
                repository=EvidenceRepository(pool),
                dictionary=dictionary,
                mapping_set=mapping_set,
                policy=policy,
                entity_id=entity_id,
                basis=Basis.CONSOLIDATED,
                framework=AccountingFramework.IND_AS,
                family=FilingFamily.FINANCIAL_RESULTS,
                reporting_period_end=date(2026, 6, 30),
                pdf_specs=None,
            )

    return {
        "xbrl": first_party,
        "screener_page": lambda: vendor("SCREENER_FINANCIALS"),
        "screener_search": lambda: vendor("SCREENER_SEARCH"),
        "equity_l": lambda: vendor("EQUITY_L"),
    }


@pytest.mark.pg
@pytest.mark.retained
def test_gate_refuses_conflicted_and_identity_captures_and_admits_partial_ones(
    cli: Callable[..., int],
    pg_db: PgTestDatabase,
    pg_template: PgTestDatabase,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D4.5: EXCHANGE, XBRL_ENTITY and SCREENER verify, then Tijori conflicts: the verified XBRL
    instance and Screener page are refused by both real writers (nothing stored). In a fresh
    database the same bytes under a PARTIAL record are admitted; an IDENTITY capture never is."""
    seed_apar(pg_db)
    served = world(APAR)
    CONFLICTS["tijori_wrong_symbol"][0](served)
    root = write_root(tmp_path / "raw", served, APAR)
    assert cli(APAR, root) == FAILURE
    _, states = recorded(pg_db)
    assert {u for u, (s, _) in states.items() if s == S.VERIFIED} == {
        U.EXCHANGE,
        U.XBRL_ENTITY,
        U.SCREENER,
    }
    writers = _writers(pg_db, tmp_path / "a", tmp_path / "snapshots")
    for name in ("xbrl", "screener_page"):
        with pytest.raises(IneligibleCaptureError):
            writers[name]()
    assert evidence_counts(pg_db) == (0, 0) and count(pg_db, "acquisition_attempts") == 0

    with fresh_db(pg_template) as db:
        for name, value in db.cli_env().items():
            monkeypatch.setenv(name, value)
        seed_apar(db)
        clean = write_root(tmp_path / "clean", world(APAR), APAR)
        assert (
            main(
                [
                    "onboard",
                    APAR,
                    "--raw-root",
                    str(clean),
                    "--snapshot-root",
                    str(tmp_path / "snap2"),
                ]
            )
            == INCOMPLETE
        )
        writers = _writers(db, tmp_path / "b", tmp_path / "snap2")
        assert writers["xbrl"]().package_id is not None
        assert writers["screener_page"]().occurrences
        before = evidence_counts(db)
        with pytest.raises(IneligibleCaptureError):
            writers["screener_search"]()
        with pytest.raises((IneligibleCaptureError, KeyError)):
            writers["equity_l"]()
        assert evidence_counts(db) == before


# --- acquisition composition and the freeze protocol (C5, C13) --------------------------------


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _repo(tmp_path: Path) -> tuple[Path, Path, str]:
    """A git repo with an implementation commit and a committed freeze descriptor."""
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "t")
    (repo / "src" / "impl.py").write_text("x = 1\n")
    _git(repo, "add", "src/impl.py")
    _git(repo, "commit", "-qm", "impl")
    implementation = _git(repo, "rev-parse", "HEAD")
    descriptor = repo / "freeze.yaml"
    descriptor.write_text(
        yaml.safe_dump({"freezes": [{"attempt": 1, "implementation_commit": implementation}]})
    )
    _git(repo, "add", "freeze.yaml")
    _git(repo, "commit", "-qm", "freeze")
    return repo, descriptor, implementation


def _transport(
    served: list[dict[str, Any]], echo: bool = False
) -> Callable[[Any], tuple[int, bytes]]:
    """A fake transport serving the fixtures by URL; ``echo`` leaks a credential on failure."""
    bodies = {request_key(item["surface"], item["url"]): item["body"] for item in served}

    def send(request: Any) -> tuple[int, bytes]:
        if echo and request.surface == "company_search":
            raise OSError(f"refused with cookie {os.environ['TIJORI_SESSION_COOKIE']}")
        if echo and request.surface == "instruments":
            return 302, f"Location: https://x.invalid/?token={SENTINEL}".encode()
        return 200, bodies[request_key(request.surface, request.url)]

    return send


def _raising(request: Any) -> tuple[int, bytes]:
    raise AssertionError("replay must not open a transport")


@pytest.mark.pg
@pytest.mark.retained
def test_acquire_then_replay_is_identical_and_leaks_nothing(
    cli: Callable[..., int],
    pg_db: PgTestDatabase,
    pg_template: PgTestDatabase,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``onboard --acquire`` with only transports faked writes gen-1; replay in a fresh database
    with credentials unset, transports raising and the clock three years on gives the same
    outcome and window; altered retained entries refuse; a second acquisition writes gen-2 and
    leaves gen-1 byte-identical, and an echoed credential lands nowhere."""
    repo, descriptor, _ = _repo(tmp_path)
    raw = tmp_path / "raw"
    clock = datetime(2026, 10, 16, 2, 20, 24, tzinfo=UTC)
    monkeypatch.setattr(onboard_cli, "live_transport", lambda: _transport(world(APAR)))
    monkeypatch.setattr(onboard_cli, "now", lambda: clock)
    acquire = ("--acquire", "--freeze-descriptor", str(descriptor))
    assert cli(APAR, raw, *acquire) == INCOMPLETE
    acquisition = json.loads((raw / "gen-1" / "acquisition.json").read_text())
    assert acquisition["acquisition_head"] == _git(repo, "rev-parse", "HEAD")
    first = recorded(pg_db)[1]
    gen1 = {p.name: p.read_bytes() for p in (raw / "gen-1").iterdir()}

    for name in ("SCREENER_SESSION_COOKIE", "TIJORI_SESSION_COOKIE", "UPSTOX_ANALYTICS_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(onboard_cli, "live_transport", lambda: _raising)
    monkeypatch.setattr(onboard_cli, "now", lambda: clock + timedelta(days=3 * 365))
    with fresh_db(pg_template) as db:
        for name, value in db.cli_env().items():
            monkeypatch.setenv(name, value)
        out = tmp_path / "replay-snapshots"
        assert (
            main(["onboard", APAR, "--raw-root", str(raw), "--snapshot-root", str(out)])
            == INCOMPLETE
        )
        assert recorded(db)[1] == first
        manifest = json.loads((raw / "gen-1" / MANIFEST_NAME).read_text())
        assert manifest["as_of"] == AS_OF.isoformat()
        for damage in ("delete", "alter"):
            copy = tmp_path / damage
            shutil.copytree(raw, copy)
            victim = (
                copy
                / "gen-1"
                / next(
                    e["filename"]
                    for e in manifest["entries"]
                    if e["surface"] == "NSE_XBRL_INSTANCE"
                )
            )
            if damage == "delete":
                victim.unlink()
            else:
                victim.write_bytes(victim.read_bytes() + b" ")
            assert (
                main(["onboard", APAR, "--raw-root", str(copy), "--snapshot-root", str(out)])
                == FAILURE
            )
        assert count(db, "onboarding_records") == 1

    for name, value in pg_db.cli_env().items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("TIJORI_SESSION_COOKIE", SENTINEL)
    monkeypatch.setattr(onboard_cli, "live_transport", lambda: _transport(world(APAR), echo=True))
    monkeypatch.setattr(onboard_cli, "now", lambda: clock)
    capsys.readouterr()
    assert cli(APAR, raw, *acquire) == INCOMPLETE
    assert {p.name: p.read_bytes() for p in (raw / "gen-1").iterdir()} == gen1
    assert (raw / "gen-2" / MANIFEST_NAME).is_file()
    logs = capsys.readouterr()
    assert SENTINEL not in logs.out + logs.err
    assert not any(SENTINEL.encode() in p.read_bytes() for p in raw.rglob("*") if p.is_file())
    assert not any(
        SENTINEL.encode() in p.read_bytes()
        for p in (tmp_path / "snapshots").rglob("*")
        if p.is_file()
    )


@pytest.mark.parametrize(
    "breach", ["dirty_impl", "entry_uncommitted", "impl_after_freeze", "head_at_implementation"]
)
def test_acquire_refuses_outside_the_freeze_protocol(
    breach: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C5: acquisition only on the descriptor commit or a descendant with no IMPL change,
    with the entry committed; each breach refuses (exit 5) before any request."""
    repo, descriptor, implementation = _repo(tmp_path)
    if breach == "dirty_impl":
        (repo / "src" / "impl.py").write_text("x = 2\n")
    elif breach == "entry_uncommitted":
        descriptor.write_text(
            yaml.safe_dump(
                {
                    "freezes": [
                        {"attempt": 1, "implementation_commit": implementation},
                        {"attempt": 2, "implementation_commit": implementation},
                    ]
                }
            )
        )
    elif breach == "impl_after_freeze":
        (repo / "src" / "impl.py").write_text("x = 3\n")
        _git(repo, "commit", "-qam", "late")
    else:
        _git(repo, "checkout", "-q", implementation)
    monkeypatch.setattr(onboard_cli, "live_transport", lambda: _raising)
    args = [
        "onboard",
        APAR,
        "--raw-root",
        str(tmp_path / "raw"),
        "--snapshot-root",
        str(tmp_path / "s"),
        "--acquire",
        "--freeze-descriptor",
        str(descriptor),
    ]
    assert main(args) == FAILURE
    assert not (tmp_path / "raw").exists()
