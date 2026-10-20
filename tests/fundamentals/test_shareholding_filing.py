"""Shareholding-pattern acquisition (plan D8): the transport boundary (Task 1), and stage D8.2
acceptance (Task 4) over the retained gen-2 generations of APARINDS, ETERNAL and TITAN.

Ingest runs through ``fundamentals shareholding ingest`` into ``eqos_test_*`` databases with the
socket guard on. Spot values are read from the retained XBRL with lxml here, never written down.
Marked generations are copies under ``tmp_path`` with one named edit and a rehashed manifest.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import socket
from collections.abc import Callable, Iterator
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from lxml import etree  # type: ignore[import-untyped]
from onboarding_support import count, rows, seed
from pg_support import PgTestDatabase, cloned_database
from pydantic import SecretStr

from fundamentals.api import onboard_cli
from fundamentals.api.cli import main
from fundamentals.api.shareholding_cli import SHAREHOLDING_VERSIONS, _replayed
from fundamentals.api.watchlist_config import load_watchlist_config
from fundamentals.compare import run_config
from fundamentals.compare.run_config import extractor_pin, load_run_config
from fundamentals.contracts.acquisition_outcome import ExtractionOutcome
from fundamentals.contracts.canonical import Basis, Representation, StatementFamily
from fundamentals.contracts.evidence import (
    AttemptStage,
    EligibilityBoundary,
    FilingFamily,
    InterpretationReason,
    InterpretationStatus,
    MissingValueState,
)
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.contracts.onboarding import VerificationUnit
from fundamentals.contracts.source_catalog import (
    NSE_MASTER,
    SCREENER_SHAREHOLDING,
    SHP_LISTING,
    SHP_XBRL,
    UPSTOX_INSTRUMENTS,
    UPSTOX_SHAREHOLDING,
    UPSTOX_STATEMENT,
    VENDOR_SURFACES,
    surface_authority,
)
from fundamentals.contracts.versioning import VersionContentDriftError
from fundamentals.entity import discovery
from fundamentals.entity.discovery import MANIFEST_NAME, Request, replay_fetch, store_captures
from fundamentals.evidence.capture_intake import parse_filed_at
from fundamentals.evidence.interpret import input_digest
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.evidence.selection import select_package
from fundamentals.evidence.shareholding_ingest import shareholding_pins
from fundamentals.ingest.shareholding_filing import acquire, authorised, listing_date
from fundamentals.store.snapshot_store import SnapshotStore

_API = "https://api.upstox.com/v2/x"
_TOKEN = "test-token"
REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / "config"
RAW = REPO / "data" / "raw" / "shareholding"
INSTANT = date(2026, 6, 30)
OFF_QUARTER = date(2026, 8, 13)
GEN = "gen-2"
# Public identifiers from the probe record (d8-probe.md §1, §3): ISIN, BSE scrip.
COMPANIES = {
    "APARINDS": ("INE372A01015", "532259"),
    "ETERNAL": ("INE758T01015", "543320"),
    "TITAN": ("INE280A01028", "500114"),
}
X = "{http://www.xbrl.org/2003/instance}"
XBRLDI = "{http://xbrl.org/2006/xbrldi}"
SHP_NS = "http://www.bseindia.com/xbrl/shp/2025-10-31/in-bse-shp"
TS, VR = "ShareholdingAsAPercentageOfTotalNumberOfShares", "PercentageOfTotalVotingRights"
# A, B, B1-B4 and C (plan Task 4 Verification, Interpretations).
SEBI_ROWS = {
    "ShareholdingOfPromoterAndPromoterGroupMember": "sebi_promoter_group",
    "PublicShareholdingMember": "public_shareholding",
    "InstitutionsDomesticMember": "institutions_domestic",
    "InstitutionsForeignMember": "institutions_foreign",
    "GovernmentsMember": "central_state_government",
    "NonInstitutionsMember": "non_institutions",
    "SharesHeldByNonPromoterNonPublicShareholdersMember": "non_promoter_non_public",
}
SEED_STATE = "INSERT INTO eqos.capture_states (capture_ref_id, state) VALUES (%s, %s)"
EVIDENCE_TABLES = (
    "capture_refs",
    "capture_addresses",
    "acquisition_attempts",
    "occurrences",
    "interpretations",
    "filing_packages",
    "package_members",
)


class _Response:
    status = 200

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self, *_: object) -> bytes:
        """An empty body."""
        return b""


class _RecordingOpener:
    """Records the headers of each request it is asked to open."""

    def __init__(self) -> None:
        self.headers: list[dict[str, str]] = []

    def open(self, request: Any, timeout: float) -> Any:
        """Record the request headers and return an empty 200 response."""
        del timeout
        self.headers.append(dict(request.header_items()))
        return _Response()


@pytest.mark.parametrize(
    ("pair", "url", "bearer"),
    [
        (UPSTOX_STATEMENT, _API, True),
        (UPSTOX_SHAREHOLDING, _API, True),
        (UPSTOX_INSTRUMENTS, "https://assets.upstox.com/m/complete.json.gz", False),
        (UPSTOX_SHAREHOLDING, "https://other.example.com/v2/x", False),
        (UPSTOX_SHAREHOLDING, "http://api.upstox.com/v2/x", False),
        (SCREENER_SHAREHOLDING, "https://www.screener.in/company/X/", False),
    ],
)
def test_transport_sends_the_bearer_only_for_routed_surfaces_on_the_api_origin(
    monkeypatch: pytest.MonkeyPatch, pair: tuple[str, str], url: str, bearer: bool
) -> None:
    """The Upstox token goes only to ``UPSTOX_ROUTED`` on ``api.upstox.com``."""
    opener = _RecordingOpener()
    monkeypatch.setattr(onboard_cli.urllib.request, "build_opener", lambda *_: opener)
    monkeypatch.setattr(onboard_cli, "_screener_credentials_from_env", lambda: None)
    monkeypatch.setattr(onboard_cli, "_tijori_credentials_from_env", lambda: None)
    monkeypatch.setattr(
        onboard_cli,
        "_upstox_credentials_from_env",
        lambda: SimpleNamespace(access_token=SecretStr(_TOKEN)),
    )
    request = Request(unit=VerificationUnit.UPSTOX, source_id=pair[0], surface=pair[1], url=url)
    assert onboard_cli.live_transport()(request) == (200, b"")
    assert ("Authorization" in opener.headers[0]) is bearer


# --- stage D8.2 (Task 4) ------------------------------------------------------------------


def _refuse_socket(*_: object) -> None:
    raise OSError("socket guard: no network in replay")


def _ingest(raw: Path, snapshots: Path, symbol: str, instant: date = INSTANT) -> int:
    """``fundamentals shareholding ingest`` over one generation."""
    return main(
        [
            *("shareholding", "ingest", "--symbol", symbol, "--instant", instant.isoformat()),
            *("--raw-root", str(raw), "--snapshot-root", str(snapshots), "--generation", "2"),
        ]
    )


def _seed(db: PgTestDatabase, symbol: str) -> int:
    isin, scrip = COMPANIES[symbol]
    return seed(db, symbol, isin, symbol, scrip)


def _counts(db: PgTestDatabase) -> dict[str, int]:
    return {table: count(db, table) for table in EVIDENCE_TABLES}


@pytest.fixture
def guarded(pg_db: PgTestDatabase, monkeypatch: pytest.MonkeyPatch) -> Iterator[PgTestDatabase]:
    """A fresh database the CLI reaches, with no socket allowed."""
    for name, value in pg_db.cli_env().items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(socket.socket, "connect", _refuse_socket)
    yield pg_db


@pytest.fixture(scope="module")
def ingested(
    pg_template: PgTestDatabase, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[tuple[PgTestDatabase, Path, dict[str, int]]]:
    """All three gen-2 generations ingested once (entity ids by symbol)."""
    snapshots = tmp_path_factory.mktemp("shp") / "snapshots"
    with cloned_database(pg_template) as db, pytest.MonkeyPatch.context() as patch:
        for name, value in db.cli_env().items():
            patch.setenv(name, value)
        patch.setattr(socket.socket, "connect", _refuse_socket)
        entities = {symbol: _seed(db, symbol) for symbol in COMPANIES}
        for symbol in COMPANIES:
            assert _ingest(RAW, snapshots, symbol) == 0
        yield db, snapshots, entities


def _listing(symbol: str) -> list[dict[str, Any]]:
    return list(json.loads((RAW / symbol / GEN / "01.bin").read_bytes()))


def _filed(symbol: str) -> dict[tuple[str, str], str]:
    """``(category member, percentage element) -> lexeme`` of each filed SEBI row, by lxml."""
    root = etree.fromstring((RAW / symbol / GEN / "02.bin").read_bytes())
    contexts = {}
    for context in root.iter(f"{X}context"):
        members = context.findall(f".//{XBRLDI}explicitMember")
        instant = context.findtext(f"{X}period/{X}instant")
        typed = context.findall(f".//{XBRLDI}typedMember")
        if len(members) == 1 and not typed and instant == INSTANT.isoformat():
            contexts[context.get("id")] = members[0].text.split(":")[1]
    return {
        (contexts[element.get("contextRef")], etree.QName(element).localname): element.text
        for element in root.iter(f"{{{SHP_NS}}}{TS}", f"{{{SHP_NS}}}{VR}")
        if element.get("contextRef") in contexts
    }


def _evidence(db: PgTestDatabase, entity_id: int) -> tuple[Any, ...]:
    """The SHP capture's occurrences and interpretations, keyed by occurrence id."""
    with db.runtime_pool() as pool:
        repository = EvidenceRepository(pool)
        packages = repository.list_packages(entity_id, FilingFamily.SHAREHOLDING, INSTANT)
        capture = packages[0].members[Representation.XBRL].capture
        assert capture.capture_ref_id is not None
        occurrences = repository.list_capture_occurrences(capture.capture_ref_id)
        interpretations = repository.list_capture_interpretations(capture.capture_ref_id)
    return packages, occurrences, {row.occurrence_id: row for row in interpretations}


@pytest.mark.retained
def test_acquisition_reproduces_each_probe_request_in_order() -> None:
    """``acquire`` over the replayed gen-2 asks for exactly the recorded requests, Screener
    drill-downs included, and every request it makes is authorised."""
    watchlist = load_watchlist_config(CONFIG / "watchlist.yaml")
    for symbol in COMPANIES:
        folder = RAW / symbol / GEN
        manifest = json.loads((folder / MANIFEST_NAME).read_bytes())
        allowed: list[bool] = []
        served = replay_fetch(folder)

        def spy(request: Request, ok: bool, served: Any = served, seen: Any = allowed) -> Any:
            seen.append(ok)
            return served(request, ok)

        slug = watchlist.stock(symbol).identifiers.tijori_slug
        captures = acquire(symbol, INSTANT, spy, tijori_slug=slug)
        made = [(c.request.key, c.request.surface, c.request.url) for c in captures]
        recorded = [(e["request_key"], e["surface"], e["url"]) for e in manifest["entries"]]
        assert made == recorded
        assert allowed and all(allowed)
        for capture in captures:
            check = discovery.authorised if capture.request.surface == NSE_MASTER[1] else authorised
            assert check(capture.request, VENDOR_SURFACES)


@pytest.mark.pg
@pytest.mark.retained
def test_authority_retention_and_addresses(
    ingested: tuple[PgTestDatabase, Path, dict[str, int]],
) -> None:
    """Every capture is on a registered surface, its record carries that surface's retention
    authority, and it has its migration-0027 class and its retained source address."""
    db, snapshots, _ = ingested
    entries = [
        entry
        for symbol in COMPANIES
        for entry in json.loads((RAW / symbol / GEN / MANIFEST_NAME).read_bytes())["entries"]
    ]
    urls = {entry["url"] for entry in entries}
    store = SnapshotStore(snapshots)
    found = rows(
        db,
        "SELECT r.source_id, r.surface, r.request_key, r.capture_id, c.retention_class, "
        "eqos.base_class(r.source_id, r.surface), a.url FROM eqos.capture_refs r "
        "LEFT JOIN eqos.retention_classes c ON c.capture_ref_id = r.id "
        "LEFT JOIN eqos.capture_addresses a ON a.capture_ref_id = r.id",
    )
    assert len(found) == len(entries)
    for source, surface, key, capture_id, kept, base, url in found:
        authority = surface_authority(source, surface)
        assert authority.role is not None
        record = store.get_capture(source, surface, key, capture_id)
        assert record.rights.authority_refs == (authority.retention_authority,)
        assert kept == base and url in urls


@pytest.mark.pg
@pytest.mark.retained
def test_packages_lineage_and_selection(
    ingested: tuple[PgTestDatabase, Path, dict[str, int]],
) -> None:
    """Every submission at the instant is a STANDALONE/UNKNOWN package with its lineage; exactly
    one is eligible at the listing's latest broadcast, at that broadcast's knowledge time."""
    db, _, entities = ingested
    for symbol, entity_id in entities.items():
        dated = [row for row in _listing(symbol) if listing_date(row["date"]) == INSTANT]
        broadcasts = [parse_filed_at(row["broadcastDate"].title()) for row in dated]
        packages, _, _ = _evidence(db, entity_id)
        assert len(packages) == len(dated)
        with db.runtime_pool() as pool:
            repository = EvidenceRepository(pool)
            for package in packages:
                assert package.package_id is not None
                lineage = repository.list_package_lineage(package.package_id)
                assert lineage[-1] == package and len(lineage) >= 1
            selected = select_package(
                packages,
                entity_id=entity_id,
                family=FilingFamily.SHAREHOLDING,
                statement_family=StatementFamily.SHAREHOLDING,
                basis=Basis.STANDALONE,
                framework=AccountingFramework.UNKNOWN,
                period_end=INSTANT,
                boundary=EligibilityBoundary.at(max(broadcasts)).model_copy(
                    update={"first_seen_cutoff": repository.store_clock()}
                ),
            )
        assert selected is not None and selected.knowledge_time == max(broadcasts)
        assert {(p.basis, p.framework) for p in packages} == {
            (Basis.STANDALONE, AccountingFramework.UNKNOWN)
        }


@pytest.mark.pg
@pytest.mark.retained
def test_interpretations_carry_category_denominator_and_share_class(
    ingested: tuple[PgTestDatabase, Path, dict[str, int]],
) -> None:
    """Each filed SEBI row's percentage is keyed at its category, its filed denominator and the
    filing's ISIN; its lexeme is the filed one, x100 once (raw scale 2), and its INF precision
    is unsupported (R5), so the side refuses rather than invent a value."""
    db, _, entities = ingested
    for symbol, entity_id in entities.items():
        _, occurrences, by_occurrence = _evidence(db, entity_id)
        by_anchor = {
            (o.native_context["context_ref"], o.native_context["local_name"]): o
            for o in occurrences
        }
        filed = _filed(symbol)
        keyed = set()
        for occurrence in occurrences:
            row = by_occurrence[occurrence.occurrence_id]
            if row.key is None or row.canonical_id != "shp_holding_pct":
                continue
            members = dict(row.key.dimensions.pairs)
            assert members["share_class"] == COMPANIES[symbol][0]
            keyed.add((members["shareholding_category"], members["denominator"]))
            assert occurrence.raw_scale == 2 and occurrence.raw_unit == "xbrli:pure"
            assert row.reason is InterpretationReason.PRECISION_UNSUPPORTED
        for (member, element), lexeme in filed.items():
            if member not in SEBI_ROWS:
                continue
            denominator = "TOTAL_SHARES" if element == TS else "VOTING_RIGHTS"
            assert (SEBI_ROWS[member], denominator) in keyed
            contexts = [c for (c, local) in by_anchor if local == element]
            assert any(by_anchor[(c, element)].raw_value_text == lexeme for c in contexts)
        assert {category for category, _ in keyed} >= {
            SEBI_ROWS[member] for member, _ in filed if member in SEBI_ROWS
        }


def _list_axis(occurrence: Any) -> str | None:
    typed = [a for a, v in occurrence.native_context["dimensions"] if v.startswith("typed:")]
    return typed[0].rsplit(":", 1)[-1] if typed else None


@pytest.mark.pg
@pytest.mark.retained
def test_holders_are_unmapped_with_their_list_completeness(
    ingested: tuple[PgTestDatabase, Path, dict[str, int]],
) -> None:
    """Holder occurrences are keyless and UNMAPPED with R4 completeness: public and C2 trust lists
    THRESHOLDED (1, TOTAL_SHARES); promoter-group and PAC lists UNKNOWN with null threshold and a
    reason. No interpretation holds a zero that was not printed."""
    db, _, entities = ingested
    expected = {
        ("APARINDS", "DetailsOfSharesHeldByMutualFundsOrUTIAxis"): "THRESHOLDED",
        ("ETERNAL", "DetailsOfSharesHeldByEmployeeBenefitsTrustsAxis"): "THRESHOLDED",
        ("APARINDS", "DetailsSharesHeldByIndividualsOrHUFAxis"): "UNKNOWN",
        ("ETERNAL", "DetailsOfTheShareholdersActingAsPersonsInConcertForPublicAxis"): "UNKNOWN",
    }
    seen = set()
    for symbol, entity_id in entities.items():
        _, occurrences, by_occurrence = _evidence(db, entity_id)
        for occurrence in occurrences:
            row = by_occurrence[occurrence.occurrence_id]
            if row.value == 0:
                assert occurrence.missing_state is MissingValueState.ZERO_PRINTED
            axis = _list_axis(occurrence)
            if axis is None:
                continue
            assert row.status is InterpretationStatus.UNMAPPED and row.key is None
            disclosure = occurrence.disclosure
            want = expected.get((symbol, axis))
            if want is None:
                continue
            seen.add((symbol, axis))
            assert disclosure["completeness"] == want
            if want == "THRESHOLDED":
                assert (disclosure["threshold_pct"], disclosure["threshold_denominator"]) == (
                    1,
                    "TOTAL_SHARES",
                )
            else:
                assert disclosure["threshold_pct"] is disclosure["threshold_denominator"] is None
                assert disclosure["completeness_reason"]
    assert seen == set(expected)


@pytest.mark.pg
@pytest.mark.retained
def test_reingest_adds_nothing(
    ingested: tuple[PgTestDatabase, Path, dict[str, int]],
) -> None:
    """Unchanged inputs reuse every registration, attempt, occurrence, interpretation and
    package."""
    db, snapshots, _ = ingested
    before = _counts(db)
    with pytest.MonkeyPatch.context() as patch:
        for name, value in db.cli_env().items():
            patch.setenv(name, value)
        patch.setattr(socket.socket, "connect", _refuse_socket)
        for symbol in COMPANIES:
            assert _ingest(RAW, snapshots, symbol) == 0
    assert _counts(db) == before


def _marked(root: Path, symbol: str, edit: Callable[[Path, list[dict[str, Any]]], None]) -> Path:
    """A copy of the symbol's gen-2 with one edit, its manifest rehashed; returns the raw root."""
    folder = root / symbol / GEN
    shutil.copytree(RAW / symbol / GEN, folder)
    manifest = json.loads((folder / MANIFEST_NAME).read_bytes())
    edit(folder, manifest["entries"])
    for entry in manifest["entries"]:
        if entry["filename"] is not None:
            body = (folder / entry["filename"]).read_bytes()
            entry["sha256"], entry["bytes"] = hashlib.sha256(body).hexdigest(), len(body)
    (folder / MANIFEST_NAME).write_text(json.dumps(manifest))
    return root


def _rewrite(
    pair: tuple[str, str], old: bytes, new: bytes, times: int = -1
) -> Callable[[Path, list[dict[str, Any]]], None]:
    def edit(folder: Path, entries: list[dict[str, Any]]) -> None:
        (entry,) = [e for e in entries if (e["source_id"], e["surface"]) == pair]
        path = folder / entry["filename"]
        body = path.read_bytes()
        assert old in body
        path.write_bytes(body.replace(old, new, times))

    return edit


def _fail(pair: tuple[str, str], outcome: str) -> Callable[[Path, list[dict[str, Any]]], None]:
    """The request answered ``outcome`` with no body; a failed listing names no instance."""

    def edit(folder: Path, entries: list[dict[str, Any]]) -> None:
        if pair == SHP_LISTING:
            entries[:] = [e for e in entries if (e["source_id"], e["surface"]) != SHP_XBRL]
        (entry,) = [e for e in entries if (e["source_id"], e["surface"]) == pair]
        (folder / entry["filename"]).unlink()
        entry.update(outcome=outcome, filename=None, sha256=None, bytes=None)

    return edit


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize(
    ("edit", "outcome"),
    [
        (_rewrite(SHP_LISTING, b'"date":"30-JUN-2026"', b'"date":"29-JUN-2026"'), "PARSE_FAILED"),
        (_rewrite(SHP_XBRL, b"2025-10-31/in-bse", b"2099-01-01/in-bse"), "UNSUPPORTED_SCHEMA"),
        (_rewrite(SHP_XBRL, b'ScripCode">532259<', b'ScripCode">500114<', 1), "IDENTITY_REJECTED"),
        (_rewrite(SHP_XBRL, b">INE372A01015<", b">INE280A01028<"), "IDENTITY_REJECTED"),
    ],
    ids=["listing-date", "namespace", "context-entity", "isin-fact"],
)
def test_refusals_write_nothing_but_their_attempt(
    guarded: PgTestDatabase, tmp_path: Path, edit: Any, outcome: str
) -> None:
    """A marked Apar submission gives its status and writes no occurrence, interpretation or
    package."""
    entity_id = _seed(guarded, "APARINDS")
    raw = _marked(tmp_path / "raw", "APARINDS", edit)
    assert _ingest(raw, tmp_path / "snapshots", "APARINDS") != 0
    with guarded.runtime_pool() as pool:
        attempts = EvidenceRepository(pool).list_attempts(entity_id, INSTANT)
    assert [(a.surface, a.outcome.value) for a in attempts] == [(SHP_XBRL[1], outcome)]
    counts = _counts(guarded)
    assert counts["occurrences"] == counts["interpretations"] == counts["filing_packages"] == 0


@pytest.mark.pg
@pytest.mark.retained
def test_a_withheld_public_holder_has_no_occurrence(
    guarded: PgTestDatabase, tmp_path: Path
) -> None:
    """A public-list holder the filing does not name is absent, never a zero."""
    path = RAW / "ETERNAL" / GEN / "02.bin"
    tree = etree.parse(str(path))
    axis = "in-bse-shp:DetailsOfSharesHeldByMutualFundsOrUTIAxis"
    holder = next(t for t in tree.iter(f"{XBRLDI}typedMember") if t.get("dimension") == axis)
    value = "".join(holder.itertext()).strip()
    withheld = {
        context.get("id")
        for context in tree.iter(f"{X}context")
        for typed in context.iter(f"{XBRLDI}typedMember")
        if typed.get("dimension") == axis and "".join(typed.itertext()).strip() == value
    }
    name = next(
        element.text
        for element in tree.iter(f"{{{SHP_NS}}}NameOfTheShareholder")
        if element.get("contextRef") in withheld
    )
    for element in list(tree.iter()):
        if element.get("contextRef") in withheld or (
            element.tag == f"{X}context" and element.get("id") in withheld
        ):
            element.getparent().remove(element)
    body = etree.tostring(tree, xml_declaration=True, encoding="UTF-8")

    def edit(folder: Path, entries: list[dict[str, Any]]) -> None:
        (entry,) = [e for e in entries if (e["source_id"], e["surface"]) == SHP_XBRL]
        (folder / entry["filename"]).write_bytes(body)

    entity_id = _seed(guarded, "ETERNAL")
    raw = _marked(tmp_path / "raw", "ETERNAL", edit)
    assert _ingest(raw, tmp_path / "snapshots", "ETERNAL") == 0
    _, occurrences, by_occurrence = _evidence(guarded, entity_id)
    assert all(o.raw_value_text != name for o in occurrences)
    assert all(o.native_context["context_ref"] not in withheld for o in occurrences)
    for occurrence in occurrences:
        if by_occurrence[occurrence.occurrence_id].value == 0:
            assert occurrence.missing_state is MissingValueState.ZERO_PRINTED


@pytest.mark.pg
@pytest.mark.retained
def test_pins_refuse_a_changed_shp_source_before_writing(
    guarded: PgTestDatabase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One changed byte in a listed SHP source under ``nse-shp-v1`` is drift, refused before
    any write; the results XBRL pin does not move."""
    _seed(guarded, "APARINDS")
    config = load_run_config(CONFIG, SHAREHOLDING_VERSIONS)
    results = extractor_pin(Representation.XBRL)
    with guarded.runtime_pool() as pool:
        EvidenceRepository(pool).pin_versions(shareholding_pins(config))
    source = tmp_path / "src"
    shutil.copytree(run_config._SOURCE_ROOT, source, ignore=shutil.ignore_patterns("__pycache__"))
    adapter = source / "evidence" / "shareholding_filing.py"
    adapter.write_bytes(adapter.read_bytes() + b"\n")
    monkeypatch.setattr(run_config, "_SOURCE_ROOT", source)
    before = _counts(guarded)
    with guarded.runtime_pool() as pool, pytest.raises(VersionContentDriftError):
        EvidenceRepository(pool).pin_versions(shareholding_pins(config))
    assert _ingest(RAW, tmp_path / "snapshots", "APARINDS") != 0
    assert _counts(guarded) == before
    assert extractor_pin(Representation.XBRL) == results


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize("state", ["EXPIRED", "PURGE_PENDING"])
def test_an_expired_registration_is_refused_before_any_write(
    guarded: PgTestDatabase, tmp_path: Path, state: str
) -> None:
    """D9: an expired or purge-pending SHP capture is ``ORIGINAL_EXPIRED``; no evidence or
    attempt row is added."""
    entity_id = _seed(guarded, "APARINDS")
    snapshots = tmp_path / "snapshots"
    captures = [c for c in _replayed(RAW / "APARINDS", 2) if c.request.surface == SHP_XBRL[1]]
    store = SnapshotStore(snapshots)
    with guarded.runtime_pool() as pool, store.prepare_ordinary_output():
        ((_, ref),) = store_captures(store, EvidenceRepository(pool), captures)
    with guarded.migrator_connection() as conn:
        conn.execute(SEED_STATE, (ref.capture_ref_id, state))
    assert _ingest(RAW, snapshots, "APARINDS") != 0
    with guarded.runtime_pool() as pool:
        assert EvidenceRepository(pool).list_attempts(entity_id, INSTANT) == ()
    counts = _counts(guarded)
    assert counts["occurrences"] == counts["interpretations"] == counts["filing_packages"] == 0


@pytest.mark.pg
@pytest.mark.retained
def test_a_non_quarter_end_instant_ingests(guarded: PgTestDatabase, tmp_path: Path) -> None:
    """A submission dated off a quarter end is its own instant (its run is Task 5)."""
    entity_id = _seed(guarded, "APARINDS")

    def edit(folder: Path, entries: list[dict[str, Any]]) -> None:
        _rewrite(SHP_LISTING, b'"date":"30-JUN-2026"', b'"date":"13-AUG-2026"')(folder, entries)
        _rewrite(SHP_XBRL, b"2026-06-30", b"2026-08-13")(folder, entries)

    raw = _marked(tmp_path / "raw", "APARINDS", edit)
    assert _ingest(raw, tmp_path / "snapshots", "APARINDS", OFF_QUARTER) == 0
    with guarded.runtime_pool() as pool:
        packages = EvidenceRepository(pool).list_packages(
            entity_id, FilingFamily.SHAREHOLDING, OFF_QUARTER
        )
    assert len(packages) == 1


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize("pair", [SHP_LISTING, SHP_XBRL], ids=["listing", "filing"])
def test_a_failed_first_party_request_is_its_attempt_alone(
    guarded: PgTestDatabase, tmp_path: Path, pair: tuple[str, str]
) -> None:
    """R8: on a fresh database a non-OK listing (or SHP instance) response exits non-zero with
    exactly one ACQUISITION attempt on that request and no capture, package or evidence."""
    entity_id = _seed(guarded, "APARINDS")
    raw = _marked(tmp_path / "raw", "APARINDS", _fail(pair, "HTTP_503"))
    (entry,) = [
        e
        for e in json.loads((raw / "APARINDS" / GEN / MANIFEST_NAME).read_bytes())["entries"]
        if (e["source_id"], e["surface"]) == pair
    ]
    assert _ingest(raw, tmp_path / "snapshots", "APARINDS") != 0
    with guarded.runtime_pool() as pool:
        (attempt,) = EvidenceRepository(pool).list_attempts(entity_id, INSTANT)
    representation = Representation.JSON if pair == SHP_LISTING else Representation.XBRL
    identity = {"source_id": pair[0], "surface": pair[1], "request_key": entry["request_key"]}
    assert (attempt.stage, attempt.source_id, attempt.surface) == (AttemptStage.ACQUISITION, *pair)
    assert (attempt.representation, attempt.period_end) == (representation, INSTANT)
    assert attempt.package_id is None and attempt.capture is None
    assert attempt.outcome is ExtractionOutcome.FAILED
    assert attempt.reason is not None and entry["request_key"] in attempt.reason
    assert attempt.input_sha256 == input_digest({**identity, "capture_id": None})
    counts = _counts(guarded)
    assert counts["acquisition_attempts"] == 1
    assert counts["capture_refs"] == counts["filing_packages"] == counts["occurrences"] == 0
    assert counts["interpretations"] == 0
