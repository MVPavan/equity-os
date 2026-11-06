"""VENDOR-1 Phase 1 (spec §6.1): Tijori display rules and ``eqos vendor reingest``.

The module fixture extracts and interprets the retained Apar Screener and Tijori financials
captures (gitignored ``data/raw/snapshots/v1``) on one ``eqos_test_*`` database; Task 3 adds its
inventory tests to this module. This file records no vendor value: the characterization is a
digest, and the precision case reads the SYNTHETIC ``synthetic_tijori_financials.html``.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, NamedTuple

import pytest
from pg_support import PgTestDatabase, cloned_database
from retained_support import seed_apar
from test_evidence_vendor import screener, tijori

from equity_os.contracts.measurement.canonical import Basis, Representation
from equity_os.contracts.measurement.evidence import (
    CaptureReference,
    InterpretationReason,
    InterpretationStatus,
)
from equity_os.contracts.measurement.observation import AccountingFramework
from equity_os.contracts.sourcing.acquisition_outcome import ExtractionOutcome
from equity_os.contracts.verification.config_versions import ConfigVersions
from equity_os.extraction.surfaces.vendor_ingest import (
    VendorIngestReport,
    VendorIngestRequest,
    ingest_vendor,
)
from equity_os.extraction.vendors.tijori import vendor_tijori
from equity_os.interface.commands.companies.onboard_cli import SCREENER_SECTIONS
from equity_os.interface.entry.cli import main
from equity_os.sourcing.vendors.tijori.tijori_source import TijoriSource
from equity_os.storage.raw_files.snapshot_store import SnapshotStore
from equity_os.storage.records.repository import EvidenceRepository
from equity_os.verification.comparison.run_config import load_run_config

REPO = Path(__file__).resolve().parents[4]
CONFIG = REPO / "config"
RETAINED = REPO / "data/raw/snapshots/v1"
TIJORI = ("tijori", "financials", "apar-industries-limited", "20261014T092203.484096Z-ea59098cc0df")
SCREENER = (
    "screener-subscriber",
    "SCREENER_FINANCIALS",
    "b881ee29efca68f7cfd2f1dac2dc53f023b4d4c18d0f6ebfd750330b6698bac7",
    "20261029T063416.958531Z-aafca20d157e",  # Apar's onboarding capture
)
PERIOD_END = date(2026, 6, 30)
VERSIONS = ConfigVersions(dictionary="v2", mapping_set="v6")
OLDER = ConfigVersions(dictionary="v2", mapping_set="v5")  # onboarding's, as live holds Apar
DISPLAY = vendor_tijori.load_tijori_display(
    CONFIG / "normalisation/mappings/tijori/v5/display.yaml"
)
# The retained Apar qt_c occurrences under tijori-v4 (v1's one rule), recorded before tijori-v5.
QT_C = (230, "2724155f97b0525dbd100229de893c5df1f766722d209d10e811e1f2d62fd95d")
_FIELDS = {
    *("native_field", "raw_value_text", "raw_unit", "raw_scale", "raw_sign", "precision_kind"),
    *("declared_precision", "native_context", "period", "missing_state", "disclosure", "anchor"),
}


class Ingested(NamedTuple):
    """The fixture database, Apar's entity id and each capture's ingest report."""

    db: PgTestDatabase
    entity_id: int
    reports: tuple[VendorIngestReport, ...]


def ingest(
    db: PgTestDatabase, entity_id: int, versions: ConfigVersions, tijori_version: str
) -> tuple[VendorIngestReport, ...]:
    """Ingest the retained Tijori capture and the Screener page (once per section)."""
    config = load_run_config(CONFIG, versions)
    adapters = [(TIJORI, tijori(TIJORI[2], "APARINDS"), tijori_version)]
    adapters += [
        (SCREENER, screener("APARINDS", Basis.CONSOLIDATED, section), "screener-v1")
        for section in SCREENER_SECTIONS
    ]
    with db.runtime_pool() as pool:
        return tuple(
            ingest_vendor(
                VendorIngestRequest(
                    source_id=capture[0],
                    surface=capture[1],
                    request_key=capture[2],
                    capture_id=capture[3],
                    representation=Representation.HTML,
                    entity_id=entity_id,
                    period_end=PERIOD_END,
                    basis=Basis.CONSOLIDATED,
                    framework=AccountingFramework.IND_AS,
                ),
                extract=extract,
                extractor_version=version,
                snapshot_store=SnapshotStore(RETAINED),
                repository=EvidenceRepository(pool),
                dictionary=config.dictionary,
                mapping_set=config.mapping_set,
                policy=config.normalisation_policy,
                rounding_policy=config.rounding,
                fiscal_year_end_month=3,
            )
            for capture, extract, version in adapters
        )


@pytest.fixture(scope="module")
def apar(pg_template: PgTestDatabase) -> Iterator[Ingested]:
    """The retained Apar financials captures, extracted and interpreted under the current
    extractors and ``VERSIONS``."""
    with cloned_database(pg_template) as db:
        entity_id = seed_apar(db)
        reports = ingest(db, entity_id, VERSIONS, vendor_tijori.EXTRACTOR_VERSION)
        assert {r.attempt.outcome for r in reports} == {ExtractionOutcome.COMPLETE}
        yield Ingested(db, entity_id, reports)


def ruled(occurrence: Any) -> bool:
    """The occurrence's own (section, basis) has a rule that scopes its row."""
    context = occurrence.native_context
    labels = (occurrence.native_field, *filter(None, context["section_parent"].split("/")))
    return DISPLAY.rule_for(context["section"], Basis(context["basis"]), labels) is not None


@pytest.mark.pg
@pytest.mark.retained
def test_qt_c_output_is_unchanged(apar: Ingested) -> None:
    """Characterization: qt_c, the one section v1 supported, reads exactly as before v5."""
    (report,) = (r for r in apar.reports if r.attempt.source_id == "tijori")
    rows = sorted(
        json.dumps(o.model_dump(mode="json", include=_FIELDS), sort_keys=True)
        for o in report.occurrences
        if o.native_context["section"] == "qt_c"
    )
    assert (len(rows), hashlib.sha256("\n".join(rows).encode()).hexdigest()) == QT_C


@pytest.mark.pg
@pytest.mark.retained
def test_sections_with_a_rule_have_no_unit_mismatch(apar: Ingested) -> None:
    """Acceptance 1 and 2 on the retained capture: a row its section's rule scopes is in crore
    and is never refused UNIT_MISMATCH; every other row (fr_c, ratios) stays UNKNOWN_UNIT.
    pl_c_s Sales, refused before v5 (spec §5), now maps."""
    (report,) = (r for r in apar.reports if r.attempt.source_id == "tijori")
    occurrences = {o.occurrence_id: o for o in report.occurrences}
    assert {o.raw_unit for o in occurrences.values() if ruled(o)} == {"INR"}
    assert {o.raw_unit for o in occurrences.values() if not ruled(o)} == {"unknown"}
    assert {o.native_context["section"] for o in occurrences.values() if not ruled(o)} >= {"fr_c"}
    unit_refused = [
        i
        for i in report.interpretations
        if (i.status, i.reason)
        == (InterpretationStatus.INVALID, InterpretationReason.UNIT_MISMATCH)
    ]
    assert not [i for i in unit_refused if ruled(occurrences[i.occurrence_id])]
    mapped = {
        occurrences[i.occurrence_id].native_context["section"]
        for i in report.interpretations
        if i.status is InterpretationStatus.MAPPED
    }
    assert {"qt_c", "pl_c_s"} <= mapped


def test_unsupported_section_and_precision_come_from_the_rules() -> None:
    """Acceptance 2 on the SYNTHETIC page: an fr_c row and a Quarterly Ratios row stay
    UNKNOWN_UNIT with no precision; a pl_c_s island number with three decimals is displayed
    and declared at the rule's precision (0 above 100), never its digits'."""
    body = (REPO / "tests/fundamentals/fixtures/synthetic_tijori_financials.html").read_bytes()
    (company_id,) = {
        table.metadata.company_id
        for table in TijoriSource.parse_all_tables_bytes(body, slug="x", expected_symbol="TITAN")
    }
    now = datetime(2026, 11, 6, tzinfo=UTC)
    extraction = vendor_tijori.extract_tijori(
        body,
        capture=CaptureReference(
            capture_ref_id=1,
            source_id="tijori",
            surface="financials",
            request_key="titan-company-limited",
            capture_id="synthetic",
            blob_sha256=hashlib.sha256(body).hexdigest(),
            record_sha256="0" * 64,
            registered_at=now,
            first_seen_at=now,
        ),
        record=SimpleNamespace(retrieved_at=now),  # type: ignore[arg-type]
        extractor_version=vendor_tijori.EXTRACTOR_VERSION,
        binding=vendor_tijori.TijoriBinding(
            slug="titan-company-limited", symbol="TITAN", company_id=company_id
        ),
        display=DISPLAY,
        basis=Basis.CONSOLIDATED,
    )
    cells = {
        (o.native_context["section"], o.native_field, o.anchor["column_label"]): o
        for o in extraction.occurrences
    }
    for key in (("fr_c", "Debt to Equity", "Mar 2024"), ("qt_c", "EPS", "Dec 2024")):
        assert (cells[key].raw_unit, cells[key].declared_precision) == ("unknown", None)
    revenue = cells[("pl_c_s", "Revenue", "Mar 2023")]
    assert revenue.native_context["island_value"] == "40000.125"
    assert (revenue.raw_value_text, revenue.raw_unit, revenue.raw_scale) == ("40000", "INR", 7)
    assert revenue.declared_precision == 0


@pytest.mark.pg
@pytest.mark.retained
def test_reingest_adds_new_versions_and_leaves_older_rows(
    pg_db: PgTestDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``eqos vendor reingest`` over an entity-period ingested under older versions (tijori-v4,
    mapping set v5, as live holds Apar) adds rows under tijori-v5 and the named mapping set;
    every older occurrence and interpretation stays byte-for-byte as it was. The older generation
    is today's extractor recorded under the version label ``tijori-v4``."""
    entity_id = seed_apar(pg_db)
    ingest(pg_db, entity_id, OLDER, "tijori-v4")

    def stored() -> dict[str, list[dict[str, Any]]]:
        with pg_db.runtime_pool() as pool:
            repository = EvidenceRepository(pool)
            refs = {
                a.capture.capture_ref_id for a in repository.list_attempts(entity_id, PERIOD_END)
            }
            rows: dict[str, list[dict[str, Any]]] = {"occurrences": [], "interpretations": []}
            for ref in sorted(refs):
                rows["occurrences"] += [
                    o.model_dump() for o in repository.list_capture_occurrences(ref)
                ]
                rows["interpretations"] += [
                    i.model_dump() for i in repository.list_capture_interpretations(ref)
                ]
            return rows

    before = stored()
    for name, value in pg_db.cli_env().items():
        monkeypatch.setenv(name, value)
    argv = ["vendor", "reingest", "--entity", "APARINDS", "--period-end", PERIOD_END.isoformat()]
    argv += ["--basis", "consolidated", "--mapping-set", "v6", "--dictionary", "v2"]
    assert main([*argv, "--snapshot-root", str(RETAINED), "--config-root", str(CONFIG)]) == 0
    after = stored()
    for kind in ("occurrences", "interpretations"):
        assert all(row in after[kind] for row in before[kind])
    added = [row for row in after["interpretations"] if row not in before["interpretations"]]
    assert {(row["mapping_set_version"], row["extractor_version"]) for row in added} == {
        ("v6", "tijori-v5"),
        ("v6", "screener-v1"),
    }
