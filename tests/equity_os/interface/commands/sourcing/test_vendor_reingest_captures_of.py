"""FIVE-1 Task 3: ``eqos vendor reingest --captures-of`` records vendor evidence at a named period
from the retained captures cited at a source period, in two passes.

Each test ingests the retained Apar Screener page (first) and Tijori financials capture (second)
at the source period ``PE0`` on its own ``eqos_test_*`` database, as onboarding does. The entity
is read back by key, so no symbol is written here. A refusal must leave every attempt,
occurrence and interpretation count unchanged at every period, and the version pins' rows and
sequence unchanged (closing review 5: pins are registered only after the check pass).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date
from functools import partial
from pathlib import Path
from typing import Any

import pytest
from pg_support import PgTestDatabase
from retained_support import seed_apar
from retention_support import record_of
from test_evidence_vendor import screener, tijori
from test_evidence_vendor_screener import binding as screener_binding

from equity_os.companies.identity.identity_seed import EvidenceInputKind, SettingKey
from equity_os.contracts.measurement.canonical import Basis, Representation
from equity_os.contracts.measurement.evidence import KnowledgeTimeStatus
from equity_os.contracts.measurement.observation import AccountingFramework
from equity_os.contracts.sourcing.acquisition_outcome import ExtractionOutcome
from equity_os.contracts.verification.config_versions import ConfigVersions
from equity_os.extraction.surfaces.vendor_ingest import (
    VendorExtractionError,
    VendorIngestRequest,
    ingest_vendor,
)
from equity_os.extraction.vendors.screener import vendor_screener
from equity_os.extraction.vendors.screener.screener_session_models import BasisTopology
from equity_os.extraction.vendors.screener.screener_session_page import (
    parse_document,
    read_identity,
)
from equity_os.extraction.vendors.tijori import vendor_tijori
from equity_os.interface.commands.companies.onboard_cli import SCREENER_SECTIONS
from equity_os.interface.commands.sourcing import vendor_reingest
from equity_os.interface.commands.sourcing.vendor_reingest import (
    ReingestIncompleteError,
    reingest,
)
from equity_os.interface.entry.cli import main
from equity_os.storage.raw_files.snapshot_store import SnapshotStore
from equity_os.storage.records.repository import EvidenceRepository
from equity_os.verification.comparison.run_config import load_run_config
from tests.equity_os.extraction.vendors.test_vendor_retained import OLDER, SCREENER, TIJORI

pytestmark = [pytest.mark.pg, pytest.mark.retained]

REPO = Path(__file__).resolve().parents[5]
CONFIG = REPO / "config"
RETAINED = REPO / "data/raw/snapshots/v1"
VERSIONS = ConfigVersions(dictionary="v2", mapping_set="v9")
PE0 = date(2026, 6, 30)  # the source period whose attempts cite the captures
YEAR_END = date(2026, 3, 31)  # every section of both vendors
JUNE = date(2025, 6, 30)  # Screener quarters and Tijori qt_c only, on a March year-end
SCREENER_ONLY = date(2023, 9, 30)  # before Tijori's first quarter
NOWHERE = date(2010, 3, 31)
ADAPTERS = len(SCREENER_SECTIONS) + 1
COUNTS = (
    "SELECT (SELECT count(*) FROM eqos.acquisition_attempts), "
    "(SELECT count(*) FROM eqos.occurrences), (SELECT count(*) FROM eqos.interpretations)"
)
# Pin rows and the identity sequence, which even a conflicting pin insert advances.
PINS = (
    "SELECT (SELECT count(*) FROM eqos.version_pins), "
    "pg_sequence_last_value('eqos.version_pins_id_seq')"
)
PERIODS = "SELECT period_end, count(*) FROM eqos.acquisition_attempts GROUP BY 1 ORDER BY 1"
RECORDED = "SELECT recorded_at FROM eqos.interpretations WHERE mapping_set_version = %s"


class Fixture:
    """The seeded entity with both vendors ingested at ``PE0``."""

    def __init__(
        self,
        db: PgTestDatabase,
        monkeypatch: pytest.MonkeyPatch,
        store: Path = RETAINED,
        versions: ConfigVersions = VERSIONS,
    ) -> None:
        self.db, self.entity_id, self.store, self.versions = db, seed_apar(db), store, versions
        for name, value in db.cli_env().items():
            monkeypatch.setenv(name, value)
        with db.runtime_pool() as pool:
            self.ids = EvidenceRepository(pool).issuer_identifiers(self.entity_id)
        self.key = self.ids.nse_symbol
        sections = [
            (SCREENER, screener(self.key, Basis.CONSOLIDATED, section), "screener")
            for section in SCREENER_SECTIONS
        ]
        for capture, extract, vendor in [*sections, (TIJORI, tijori(TIJORI[2], self.key), "")]:
            self.ingest(capture, extract, vendor)

    def ingest(
        self,
        capture: tuple[str, ...],
        extract: Any,
        vendor: str,
        basis: Basis = Basis.CONSOLIDATED,
        period: date = PE0,
    ) -> None:
        """One adapter's ingest at ``period``, as onboarding does."""
        version = vendor_screener.EXTRACTOR_VERSION if vendor else vendor_tijori.EXTRACTOR_VERSION
        config = load_run_config(CONFIG, self.versions)
        with self.db.runtime_pool() as pool:
            ingest_vendor(
                VendorIngestRequest(
                    source_id=capture[0],
                    surface=capture[1],
                    request_key=capture[2],
                    capture_id=capture[3],
                    representation=Representation.HTML,
                    entity_id=self.entity_id,
                    period_end=period,
                    basis=basis,
                    framework=AccountingFramework.IND_AS,
                ),
                extract=extract,
                extractor_version=version,
                snapshot_store=SnapshotStore(self.store),
                repository=EvidenceRepository(pool),
                dictionary=config.dictionary,
                mapping_set=config.mapping_set,
                policy=config.normalisation_policy,
                rounding_policy=config.rounding,
                fiscal_year_end_month=3,
            )

    def reingest(self, target: date, source: date = PE0, basis: Basis = Basis.CONSOLIDATED) -> Any:
        """``reingest`` of ``target`` from the captures cited at ``source``."""
        with self.db.runtime_pool() as pool:
            return reingest(
                pool,
                SnapshotStore(self.store),
                CONFIG,
                VERSIONS,
                entity=self.key,
                period_end=target,
                basis=basis,
                captures_of=source,
            )

    def read(self, query: Any, params: tuple[Any, ...] = ()) -> list[Any]:
        """One query's rows."""
        with self.db.runtime_pool() as pool, pool.connection() as conn:
            return conn.execute(query, params).fetchall()


@pytest.fixture
def apar(pg_db: PgTestDatabase, monkeypatch: pytest.MonkeyPatch) -> Fixture:
    """Both vendors ingested at ``PE0``."""
    return Fixture(pg_db, monkeypatch)


def test_targets_reuse_the_stored_occurrences(apar: Fixture) -> None:
    """A year end, then a June quarter only the quarterly sections hold, each add exactly one
    attempt per adapter at the target and none elsewhere; their reports cite the occurrence ids
    stored at ``PE0`` (own source periods, ``UNKNOWN`` knowledge time, the capture's first-seen
    time), and occurrence and interpretation counts stay unchanged: stored once."""
    (_, occurrences, interpretations) = apar.read(COUNTS)[0]
    cited: list[set[int | None]] = []
    for target in (YEAR_END, JUNE):
        reports = apar.reingest(target)
        assert len(reports) == ADAPTERS
        assert {r.attempt.period_end for r in reports} == {target}
        assert {r.attempt.outcome for r in reports} == {ExtractionOutcome.COMPLETE}
        found = [o for r in reports for o in r.occurrences]
        assert {o.knowledge_time_status for o in found} == {KnowledgeTimeStatus.UNKNOWN}
        assert all(o.first_seen_at == o.capture.first_seen_at for o in found)
        assert len({o.period for o in found}) > 1
        cited.append({o.occurrence_id for o in found})
    assert cited[0] == cited[1]
    assert apar.read(COUNTS)[0][1:] == (occurrences, interpretations)
    assert apar.read(PERIODS) == [(JUNE, ADAPTERS), (YEAR_END, ADAPTERS), (PE0, ADAPTERS)]


def _later_month(apar: Fixture) -> None:
    """A December fiscal-year-end month governing periods from 2026-01-01."""
    with apar.db.runtime_pool() as pool:
        repository = EvidenceRepository(pool)
        evidence = repository.put_evidence_input(EvidenceInputKind.DISCOVERY, apar.key, "f" * 64)
        repository.put_settings_record(
            apar.entity_id, SettingKey.FISCAL_YEAR_END_MONTH, "12", evidence, date(2026, 1, 1)
        )


def test_new_interpretations_stay_invisible_at_an_earlier_cutoff(
    pg_db: PgTestDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With ``PE0`` interpreted under an older mapping set, the target reuses the occurrences but
    writes new interpretations under the run's set, each recorded after a cutoff taken before the
    command: an ``AS_KNOWN`` run at that cutoff (``vendor_sides._pinned``: recorded by the cutoff)
    cannot see them, while the occurrences keep the capture's own first-seen time."""
    apar = Fixture(pg_db, monkeypatch, versions=OLDER)
    assert apar.read(RECORDED, (VERSIONS.mapping_set,)) == []
    (cutoff,) = apar.read("SELECT clock_timestamp()")[0]
    reports = apar.reingest(YEAR_END)
    recorded = apar.read(RECORDED, (VERSIONS.mapping_set,))
    assert recorded and all(at > cutoff for (at,) in recorded)
    found = [o for r in reports for o in r.occurrences]
    assert all(o.first_seen_at == o.capture.first_seen_at < cutoff for o in found)


def _screener_only_cited(apar: Fixture) -> None:
    """Only the Screener page's sections are also ingested at ``YEAR_END``."""
    for section in SCREENER_SECTIONS:
        extract = screener(apar.key, Basis.CONSOLIDATED, section)
        apar.ingest(SCREENER, extract, "screener", period=YEAR_END)


@pytest.mark.parametrize(
    ("edit", "target", "source", "basis", "gap"),
    [
        (None, SCREENER_ONLY, PE0, Basis.CONSOLIDATED, "no tijori occurrence ends at 2023-09-30"),
        (None, NOWHERE, PE0, Basis.CONSOLIDATED, "no screener-subscriber occurrence ends"),
        (_later_month, YEAR_END, PE0, Basis.CONSOLIDATED, "differs from its stored occurrence"),
        (None, YEAR_END, YEAR_END, Basis.CONSOLIDATED, "capture is cited at 2026-03-31"),
        (_screener_only_cited, JUNE, YEAR_END, Basis.CONSOLIDATED, "no tijori capture is cited"),
        (None, YEAR_END, PE0, Basis.STANDALONE, "capture is cited at 2026-06-30"),
    ],
    ids=["tijori-lacks", "no-section", "stored-disagrees", "no-capture", "one-vendor", "basis"],
)
def test_a_gap_refuses_before_any_write(
    apar: Fixture,
    edit: Callable[[Fixture], None] | None,
    target: date,
    source: date,
    basis: Basis,
    gap: str,
) -> None:
    """A target held by Screener but not Tijori (ingested second), one in no section, a stored
    occurrence the current binding would re-parse differently, no capture cited at the source
    period, only one vendor's captures cited there, and a basis no attempt holds: each refuses
    naming the gap, with every count unchanged."""
    if edit is not None:
        edit(apar)
    before = apar.read(COUNTS), apar.read(PERIODS), apar.read(PINS)
    with pytest.raises(ReingestIncompleteError, match=gap):
        apar.reingest(target, source, basis)
    assert (apar.read(COUNTS), apar.read(PERIODS), apar.read(PINS)) == before


@pytest.mark.parametrize(
    ("accepted", "why"),
    [(False, "no stored occurrence carries"), (True, "lacks the pinned exchange-code identity")],
    ids=["never-accepted", "accepted-under-another-code"],
)
def test_an_identity_rejected_capture_is_fatal(
    pg_db: PgTestDatabase, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, accepted: bool, why: str
) -> None:
    """R4-01: beside the valid Screener page, a SYNTHETIC copy carrying BSE code 000000 instead
    of the issuer's is also cited at ``PE0``: identity-rejected there, or ``accepted`` under a
    binding of that code. Both vendors cover the target, yet the command refuses naming that
    capture, with every count unchanged."""
    store = SnapshotStore(tmp_path)
    for capture in (SCREENER, TIJORI):
        store.put_capture(*SnapshotStore(RETAINED).read_capture_verified(*capture))
    apar = Fixture(pg_db, monkeypatch, tmp_path)
    _, page = store.read_capture_verified(*SCREENER)
    body = page.replace(apar.ids.bse_scrip.encode(), b"000000")
    record = store.put_capture(record_of(body, *SCREENER[:2]), body)
    rejected = (*SCREENER[:2], record.request.request_key, record.capture_id)
    extract = screener(apar.key, Basis.CONSOLIDATED, SCREENER_SECTIONS[0])
    if accepted:
        extract = partial(
            vendor_reingest._screener,
            binding=screener_binding(apar.key).model_copy(update={"bse_code": "000000"}),
            basis=Basis.CONSOLIDATED,
            section=SCREENER_SECTIONS[0],
        )
    apar.ingest(rejected, extract, "screener")
    before = apar.read(COUNTS), apar.read(PERIODS), apar.read(PINS)
    with pytest.raises(ReingestIncompleteError, match=f"{record.capture_id} is rejected: .*{why}"):
        apar.reingest(YEAR_END)
    assert (apar.read(COUNTS), apar.read(PERIODS), apar.read(PINS)) == before


def test_a_failed_section_records_its_failure(
    apar: Fixture, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Through the command: a Screener section refusing with a non-identity outcome records its
    failure attempt at the target while the others proceed, and the command exits non-zero; a
    refusal exits INCOMPLETE."""
    adapter = vendor_reingest._screener

    def failing(body: bytes, **options: Any) -> Any:
        if options["section"] is SCREENER_SECTIONS[0]:
            raise VendorExtractionError(ExtractionOutcome.FAILED, "SYNTHETIC section failure")
        return adapter(body, **options)

    monkeypatch.setattr(vendor_reingest, "_screener", failing)
    argv = [
        *("vendor", "reingest", "--entity", apar.key, "--basis", "consolidated"),
        *("--mapping-set", VERSIONS.mapping_set, "--dictionary", VERSIONS.dictionary),
        *("--snapshot-root", str(RETAINED), "--config-root", str(CONFIG)),
        *("--captures-of", str(PE0)),
    ]
    assert main([*argv, "--period-end", str(YEAR_END)]) == 1
    outcomes = [line for line in capsys.readouterr().out.splitlines() if line]
    assert len(outcomes) == ADAPTERS
    assert sum('"FAILED"' in line for line in outcomes) == 1
    assert main([*argv, "--period-end", str(NOWHERE)]) == 4
    assert "INCOMPLETE: no screener-subscriber occurrence ends" in capsys.readouterr().err


def _copy(tmp_path: Path) -> SnapshotStore:
    """A private store holding the retained Screener and Tijori captures."""
    store = SnapshotStore(tmp_path)
    for capture in (SCREENER, TIJORI):
        store.put_capture(*SnapshotStore(RETAINED).read_capture_verified(*capture))
    return store


def _variant(store: SnapshotStore, of: tuple[str, ...], body: bytes) -> tuple[str, ...]:
    """A SYNTHETIC capture of ``body`` on ``of``'s surface."""
    record = store.put_capture(record_of(body, *of[:2]), body)
    return (*of[:2], record.request.request_key, record.capture_id)


def _foreign_tijori(apar: Fixture, store: SnapshotStore) -> tuple[str, ...]:
    """A SYNTHETIC Tijori copy naming another company symbol, failing at ``PE0``."""
    _, page = store.read_capture_verified(*TIJORI)
    foreign = _variant(store, TIJORI, page.replace(apar.key.encode(), b"SYNTHX"))
    apar.ingest(foreign, tijori(TIJORI[2], apar.key), "")
    return foreign


def _standalone_screener(apar: Fixture, store: SnapshotStore) -> tuple[str, ...]:
    """A SYNTHETIC Screener copy declaring standalone figures, accepted at ``PE0`` under an
    earlier gate that read the valid page's basis evidence (its tables are the valid page's)."""
    _, page = store.read_capture_verified(*SCREENER)
    wrong = _variant(
        store, SCREENER, re.sub(rb"Consolidated(\s+)Figures", rb"Standalone\1Figures", page)
    )
    real = vendor_screener.read_page_evidence
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            vendor_screener,
            "read_page_evidence",
            lambda _, **options: real(page.decode(), **options),
        )
        for section in SCREENER_SECTIONS:
            apar.ingest(wrong, screener(apar.key, Basis.CONSOLIDATED, section), "screener")
    return wrong


@pytest.mark.parametrize(
    ("variant", "why"),
    [(_foreign_tijori, "identity_mismatch"), (_standalone_screener, "declares basis standalone")],
    ids=["foreign-tijori", "wrong-basis-screener"],
)
def test_a_capture_failing_issuer_or_basis_is_fatal(
    pg_db: PgTestDatabase,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    variant: Callable[[Fixture, SnapshotStore], tuple[str, ...]],
    why: str,
) -> None:
    """F2: beside the valid captures, a SYNTHETIC Tijori page of another company symbol, or a
    Screener page declaring the other basis, is also cited at ``PE0``. Their adapters raise only
    ``PARSE_FAILED`` and the valid captures cover the target, yet the whole-capture check refuses
    naming that capture, with every attempt, occurrence and interpretation count unchanged."""
    store = _copy(tmp_path)
    apar = Fixture(pg_db, monkeypatch, tmp_path)
    capture = variant(apar, store)
    before = apar.read(COUNTS), apar.read(PERIODS), apar.read(PINS)
    with pytest.raises(ReingestIncompleteError, match=f"{capture[3]} is rejected: .*{why}"):
        apar.reingest(YEAR_END)
    assert (apar.read(COUNTS), apar.read(PERIODS), apar.read(PINS)) == before


def test_a_standalone_only_page_reingests(
    pg_db: PgTestDatabase, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """F1, through the command: for an entity whose stored basis status is ``STANDALONE_ONLY``,
    a SYNTHETIC unmarked standalone page (the shape Screener renders for such an issuer) and the
    Tijori standalone tables ingested at ``PE0`` re-ingest at the year end, every adapter
    ``COMPLETE``; the same page refuses under a basis status that files both bases."""
    store = _copy(tmp_path)
    apar = Fixture(pg_db, monkeypatch, tmp_path)
    _, page = store.read_capture_verified(*SCREENER)
    body = re.sub(rb"Consolidated\s+Figures", b"Figures", page).replace(b"View Standalone", b"View")
    standalone = _variant(store, SCREENER, body)
    _, warehouse = read_identity(parse_document(body.decode()))
    binding = screener_binding(apar.key).model_copy(
        update={"topology": BasisTopology(standalone_warehouse_id=warehouse)}
    )
    for section in SCREENER_SECTIONS:
        extract = partial(
            vendor_reingest._screener, binding=binding, basis=Basis.STANDALONE, section=section
        )
        apar.ingest(standalone, extract, "screener", Basis.STANDALONE)
    tijori_standalone = partial(tijori(TIJORI[2], apar.key), basis=Basis.STANDALONE)
    apar.ingest(TIJORI, tijori_standalone, "", Basis.STANDALONE)
    argv = [
        *("vendor", "reingest", "--entity", apar.key, "--basis", "standalone"),
        *("--mapping-set", VERSIONS.mapping_set, "--dictionary", VERSIONS.dictionary),
        *("--snapshot-root", str(tmp_path), "--config-root", str(CONFIG)),
        *("--captures-of", str(PE0), "--period-end", str(YEAR_END)),
    ]
    before = apar.read(COUNTS), apar.read(PERIODS), apar.read(PINS)
    assert main(argv) == 4  # the seeded status files both bases
    assert (apar.read(COUNTS), apar.read(PERIODS), apar.read(PINS)) == before
    with apar.db.runtime_pool() as pool:
        repository = EvidenceRepository(pool)
        evidence = repository.put_evidence_input(EvidenceInputKind.DISCOVERY, apar.key, "e" * 64)
        with pool.connection() as conn:
            conn.execute(
                "INSERT INTO eqos.entity_basis_status (entity_id, basis_status, evidence_input_id)"
                " VALUES (%s, 'STANDALONE_ONLY', %s)",
                (apar.entity_id, evidence),
            )
    assert main(argv) == 0
    assert (YEAR_END, ADAPTERS) in apar.read(PERIODS)
