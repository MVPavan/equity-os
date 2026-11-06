"""FIVE-1 Task 3: ``eqos vendor reingest --captures-of`` records vendor evidence at a named period
from the retained captures cited at a source period, in two passes.

Each test ingests the retained Apar Screener page (first) and Tijori financials capture (second)
at the source period ``PE0`` on its own ``eqos_test_*`` database, as onboarding does. The entity
is read back by key, so no symbol is written here. A refusal must leave every attempt,
occurrence and interpretation count unchanged at every period.
"""

from __future__ import annotations

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
from tests.equity_os.extraction.vendors.test_vendor_retained import SCREENER, TIJORI

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
PERIODS = "SELECT period_end, count(*) FROM eqos.acquisition_attempts GROUP BY 1 ORDER BY 1"


class Fixture:
    """The seeded entity with both vendors ingested at ``PE0``."""

    def __init__(
        self, db: PgTestDatabase, monkeypatch: pytest.MonkeyPatch, store: Path = RETAINED
    ) -> None:
        self.db, self.entity_id, self.store = db, seed_apar(db), store
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

    def ingest(self, capture: tuple[str, ...], extract: Any, vendor: str) -> None:
        """One adapter's ingest at ``PE0``, as onboarding does."""
        version = vendor_screener.EXTRACTOR_VERSION if vendor else vendor_tijori.EXTRACTOR_VERSION
        config = load_run_config(CONFIG, VERSIONS)
        with self.db.runtime_pool() as pool:
            ingest_vendor(
                VendorIngestRequest(
                    source_id=capture[0],
                    surface=capture[1],
                    request_key=capture[2],
                    capture_id=capture[3],
                    representation=Representation.HTML,
                    entity_id=self.entity_id,
                    period_end=PE0,
                    basis=Basis.CONSOLIDATED,
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

    def read(self, query: str) -> list[Any]:
        """One query's rows."""
        with self.db.runtime_pool() as pool, pool.connection() as conn:
            return conn.execute(query).fetchall()


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


@pytest.mark.parametrize(
    ("edit", "target", "source", "basis", "gap"),
    [
        (None, SCREENER_ONLY, PE0, Basis.CONSOLIDATED, "no tijori occurrence ends at 2023-09-30"),
        (None, NOWHERE, PE0, Basis.CONSOLIDATED, "no screener-subscriber occurrence ends"),
        (_later_month, YEAR_END, PE0, Basis.CONSOLIDATED, "differs from its stored occurrence"),
        (None, YEAR_END, YEAR_END, Basis.CONSOLIDATED, "capture is cited at 2026-03-31"),
        (None, YEAR_END, PE0, Basis.STANDALONE, "capture is cited at 2026-06-30"),
    ],
    ids=["tijori-lacks", "no-section", "stored-disagrees", "no-capture", "basis"],
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
    period, and a basis no attempt holds: each refuses naming the gap, with every count
    unchanged."""
    if edit is not None:
        edit(apar)
    before = apar.read(COUNTS), apar.read(PERIODS)
    with pytest.raises(ReingestIncompleteError, match=gap):
        apar.reingest(target, source, basis)
    assert (apar.read(COUNTS), apar.read(PERIODS)) == before


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
    before = apar.read(COUNTS), apar.read(PERIODS)
    with pytest.raises(ReingestIncompleteError, match=f"{record.capture_id} is rejected: .*{why}"):
        apar.reingest(YEAR_END)
    assert (apar.read(COUNTS), apar.read(PERIODS)) == before


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
