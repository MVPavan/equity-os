"""VENDOR-1 Phase 1 (spec §6.1): Tijori display rules, ``eqos vendor reingest`` and mapping set
v9's label inventory.

The module fixture extracts and interprets the retained Apar Screener and Tijori financials
captures (gitignored ``data/raw/snapshots/v1``) on one ``eqos_test_*`` database. This file records
no vendor value: the characterization is a digest, the inventory prints cell counts only, and the
precision case reads the SYNTHETIC ``synthetic_tijori_financials.html``.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, NamedTuple

import pytest
from evidence_support import BOTH
from pg_support import PgTestDatabase, cloned_database
from retained_support import APAR_MANIFEST, INPUTS_DIR, STORE_DIR, apar_intake, seed_apar
from test_evidence_vendor import screener, tijori

from equity_os.contracts.measurement.canonical import Basis, PeriodKind, Representation
from equity_os.contracts.measurement.evidence import (
    CaptureReference,
    InterpretationReason,
    InterpretationStatus,
    Occurrence,
)
from equity_os.contracts.measurement.evidence_tier import EvidenceTier
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
from equity_os.normalisation.mapping.mapping import MappingSet
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
VERSIONS = ConfigVersions(dictionary="v2", mapping_set="v9")
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


# Ratio tables are outside the inventory: ratios are computed by code (spec §6.1).
RATIO_SECTIONS = frozenset({"fr_c", "fr_s"})


class Ingested(NamedTuple):
    """The fixture database, Apar's entity id, each capture's ingest report and the pinned
    mapping set."""

    db: PgTestDatabase
    entity_id: int
    reports: tuple[VendorIngestReport, ...]
    mapping_set: MappingSet


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
        yield Ingested(db, entity_id, reports, load_run_config(CONFIG, VERSIONS).mapping_set)


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
    argv += ["--basis", "consolidated", "--mapping-set", "v9", "--dictionary", "v2"]
    assert main([*argv, "--snapshot-root", str(RETAINED), "--config-root", str(CONFIG)]) == 0
    after = stored()
    for kind in ("occurrences", "interpretations"):
        assert all(row in after[kind] for row in before[kind])
    added = [row for row in after["interpretations"] if row not in before["interpretations"]]
    assert {(row["mapping_set_version"], row["extractor_version"]) for row in added} == {
        ("v9", "tijori-v5"),
        ("v9", "screener-v1"),
    }


def inventory(apar: Ingested) -> tuple[Occurrence, ...]:
    """Every native cell of the retained captures: the fixture's consolidated Screener page and
    Tijori tables, plus the Tijori capture's standalone tables read by the same extractor."""
    (report,) = (r for r in apar.reports if r.attempt.source_id == "tijori")
    store = SnapshotStore(RETAINED)
    record = store.get_capture(*TIJORI)
    standalone = tijori(TIJORI[2], "APARINDS")(
        store.read_body(record),
        capture=report.occurrences[0].capture,
        record=record,
        extractor_version=vendor_tijori.EXTRACTOR_VERSION,
        basis=Basis.STANDALONE,
    )
    return (*(o for r in apar.reports for o in r.occurrences), *standalone.occurrences)


def dispositions(
    mapping_set: MappingSet, occurrences: Iterable[Occurrence]
) -> dict[tuple[str, str, str, str], set[tuple[str, ...]]]:
    """Each native label (surface, section, basis, label) outside the ratio tables, with the
    dispositions its cells find: matching entry ids and reviewed ``unmapped`` items."""
    found: dict[tuple[str, str, str, str], set[tuple[str, ...]]] = defaultdict(set)
    for occurrence in occurrences:
        surface, section, basis, label = key = label_key(occurrence)
        if section in RATIO_SECTIONS:
            continue
        unmapped = tuple(
            f"unmapped: {item.reason}"
            for item in mapping_set.unmapped.get(surface, ())
            if (item.section, item.label) == (section, label) and Basis(basis) in item.basis
        )
        entries = tuple(entry.entry_id for entry in mapping_set.matches(occurrence))
        found[key].add(entries + unmapped)
    return found


def label_key(occurrence: Occurrence) -> tuple[str, str, str, str]:
    """A native label's identity: surface, section, basis and label."""
    context = occurrence.native_context
    return (occurrence.capture.surface, context["section"], context["basis"], context["label"])


def kind(disposition: tuple[str, ...]) -> str:
    """``mapped`` for an entry id, ``unmapped`` for a reviewed unmapped item."""
    return "unmapped" if disposition[0].startswith("unmapped:") else "mapped"


def undisposed(found: dict[tuple[str, str, str, str], set[tuple[str, ...]]]) -> list[str]:
    """Labels without exactly one disposition, by name."""
    return sorted(
        f"{key}: {sorted(seen)}"
        for key, seen in found.items()
        if len(seen) != 1 or len(next(iter(seen))) != 1
    )


@pytest.mark.pg
@pytest.mark.retained
def test_every_native_label_has_exactly_one_disposition(apar: Ingested) -> None:
    """Acceptance 1: every native statement label of the retained captures (ratio tables aside),
    read from the captures and not from the files, has one entry or one reviewed ``unmapped``
    item; a label dropped from a file fails by name. Prints cell counts per disposition."""
    occurrences = inventory(apar)
    found = dispositions(apar.mapping_set, occurrences)
    assert not undisposed(found)
    assert {(surface, basis) for surface, _, basis, _ in found} == {
        ("SCREENER_FINANCIALS", "CONSOLIDATED"),
        ("financials", "CONSOLIDATED"),
        ("financials", "STANDALONE"),
    }
    kinds = {key: kind(next(iter(seen))) for key, seen in found.items()}
    labels = Counter((key[0], key[2], disposition) for key, disposition in kinds.items())
    cells = Counter(
        (o.capture.surface, o.native_context["basis"], kinds.get(label_key(o), "excluded"))
        for o in occurrences
    )
    print(f"labels per disposition: {dict(sorted(labels.items()))}")
    print(f"cells per disposition: {dict(sorted(cells.items()))}")
    removed, *kept = apar.mapping_set.unmapped["SCREENER_FINANCIALS"]
    trimmed = apar.mapping_set.model_copy(
        update={"unmapped": {**apar.mapping_set.unmapped, "SCREENER_FINANCIALS": tuple(kept)}}
    )
    assert undisposed(dispositions(trimmed, occurrences)) == [
        f"{('SCREENER_FINANCIALS', removed.section, 'CONSOLIDATED', removed.label)}: [()]"
    ]


@pytest.mark.pg
@pytest.mark.retained
def test_no_annual_screener_finance_costs_votes(apar: Ingested) -> None:
    """Acceptance 12, data half: Screener's annual Interest differs from the filed finance costs
    unexplained (spec §5), so every annual or TTM Screener finance_costs value is related, not
    equivalent, and cannot vote; the quarterly row stays a voting candidate. (A refused cell, such
    as the period-ambiguous TTM column, votes in no case.)"""
    tiers: dict[bool, set[EvidenceTier]] = defaultdict(set)
    for report in apar.reports:
        for i in report.interpretations:
            if (i.canonical_id, i.status) == ("finance_costs", InterpretationStatus.MAPPED) and (
                report.attempt.source_id == SCREENER[0]
            ):
                assert i.mapping_entry_id is not None
                kinds = apar.mapping_set.entry(i.mapping_entry_id).period_kinds
                tiers[PeriodKind.QUARTER not in kinds].add(i.tier)
    assert tiers == {
        True: {EvidenceTier.RELATED_NOT_EQUIVALENT},
        False: {EvidenceTier.EQUIVALENCE_UNPROVEN},
    }


@pytest.mark.pg
@pytest.mark.retained
def test_v9_interprets_a_filing_package_as_v6_does(
    pg_db: PgTestDatabase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """v9 changes only vendor files: ``eqos evidence ingest`` of one retained Apar package
    (XBRL and results PDF) under v6 and then v9 gives equal first-party interpretation counts
    per (representation, status), as Task 13's live re-interpretation relies on."""
    seed_apar(pg_db)
    for name, value in pg_db.cli_env().items():
        monkeypatch.setenv(name, value)
    issuer_config = CONFIG / "runs/aparinds-fy27-q1-pg.yaml"
    apar_intake(tmp_path, "FY27_Q1", BOTH, issuer_config=issuer_config)  # stages the originals
    argv = ["evidence", "ingest", "--retrieval-manifest", str(APAR_MANIFEST), "--issuer"]
    argv += ["APARINDS", "--quarter", "FY27_Q1", "--period-end", PERIOD_END.isoformat()]
    argv += ["--basis", "consolidated", "--member", "xbrl=xbrl-consolidated"]
    argv += ["--member", "pdf=results", "--issuer-config", str(issuer_config)]
    argv += ["--raw-root", str(tmp_path / INPUTS_DIR), "--snapshot-root", str(tmp_path / STORE_DIR)]
    argv += ["--config-root", str(CONFIG), "--dictionary", "v2", "--mapping-set"]
    for version in ("v6", "v9"):
        assert main([*argv, version]) == 0
    with pg_db.runtime_pool() as pool, pool.connection() as conn:
        rows = conn.execute(
            "SELECT mapping_set_version, representation, status, count(*)"
            " FROM eqos.interpretations GROUP BY 1, 2, 3"
        ).fetchall()
    counts: dict[str, dict[tuple[str, str], int]] = defaultdict(dict)
    for version, representation, status, count in rows:
        counts[version][(representation, status)] = count
    assert set(counts) == {"v6", "v9"}
    assert counts["v9"] == counts["v6"]
    assert {representation for representation, _ in counts["v6"]} == {"XBRL", "PDF"}
