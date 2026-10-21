"""D8 shareholding comparison: Task 3 config loading and Task 5 run family (stage D8.2/D8.3).

The D8 configuration is fixed before any ingest: dictionary v3 and mapping set v7 must load
through the run loader, every vendor percentage must carry its owner-sanctioned assumption,
and a basket that double counts a member with its own descendant must be refused. The
``family`` tests run ``fundamentals compare`` over Apar's retained gen-2 SHP and Q1 FY27 results
XBRL into ``eqos_test_*`` databases with the socket guard on.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import shutil
import socket
from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml
from lxml import html  # type: ignore[import-untyped]
from onboarding_support import count
from pg_support import PgTestDatabase, cloned_database
from pydantic import ValidationError
from test_shareholding_filing import (
    COMPANIES,
    EVIDENCE_TABLES,
    GEN,
    INSTANT,
    OFF_QUARTER,
    RAW,
    SEBI_ROWS,
    TS,
    _fail,
    _filed,
    _ingest,
    _marked,
    _refuse_socket,
    _rewrite,
    _seed,
)
from test_shareholding_filing import guarded as guarded  # the fixture, re-exported
from test_shareholding_filing import ingested as ingested  # the fixture, re-exported

from fundamentals.api.cli import main
from fundamentals.canon.dictionary import (
    FORMULA_SET_FILE,
    CanonicalDictionary,
    DictionaryDefect,
    DictionaryLoadError,
    load_dictionary,
)
from fundamentals.canon.formula import CurrencyMismatchError, resolve_operand_keys
from fundamentals.compare import run_config
from fundamentals.compare.run import (
    DatabaseIdentity,
    RunExitStatus,
    RunManifest,
    RunRequest,
    RunScope,
    RunStatus,
    load_results,
    replay_run,
    request_for,
)
from fundamentals.compare.run_config import LoadedConfig, load_run_config, vendor_extractor_pin
from fundamentals.compare.run_store import RunStore
from fundamentals.contracts.acquisition_outcome import ExtractionOutcome
from fundamentals.contracts.canonical import (
    Basis,
    Representation,
    StatementFamily,
    ValueIdentity,
    ValueKind,
)
from fundamentals.contracts.comparison import (
    CalculationState,
    CorroborationStatus,
    ExtractionStatus,
    ReasonCode,
    SourceRole,
    SourceState,
)
from fundamentals.contracts.config_versions import ConfigVersions
from fundamentals.contracts.evidence import (
    AcquisitionAttempt,
    AttemptStage,
    FilingFamily,
    Interpretation,
    InterpretationStatus,
    MissingValueState,
    Occurrence,
    VersionPin,
)
from fundamentals.contracts.measurement_key import DimensionSet, MeasurementKey, PeriodInterval
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.contracts.source_catalog import (
    SCREENER_INVESTORS,
    SCREENER_SHAREHOLDING,
    SHP_LISTING,
    SHP_XBRL,
    TIJORI_SHAREHOLDING,
    UPSTOX_SHAREHOLDING,
)
from fundamentals.entity.discovery import MANIFEST_NAME
from fundamentals.evidence.interpret import input_digest
from fundamentals.evidence.mapping import matches_dimensions
from fundamentals.evidence.mapping_models import MappingAssumption, selector_matches
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.evidence.shareholding_filing import SHP_EXTRACTOR_VERSION

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = REPO_ROOT / "config"
SHP_NS = "http://www.bseindia.com/xbrl/shp/2025-10-31/in-bse-shp"
VENDOR_SURFACES = {"SCREENER_SHAREHOLDING", "shareholding", "share-holdings"}
BOTH = (MappingAssumption.DENOMINATOR_ASSUMED, MappingAssumption.BOUNDARY_ASSUMED)


@pytest.fixture(scope="module")
def v7() -> LoadedConfig:
    """Dictionary v3, mapping set v7 and the policy v7 pins, through the run loader."""
    versions = ConfigVersions(dictionary="v3", mapping_set="v7", normalisation_policy="v2")
    return load_run_config(CONFIG_ROOT, versions)


@pytest.mark.parametrize(
    ("entry_id", "raw_unit"),
    [("shp.sebi_promoter_group.total_shares", "xbrli:pure"), ("screener.shp.promoters", "percent")],
)
def test_config_shareholding_units_are_percentages(
    v7: LoadedConfig, entry_id: str, raw_unit: str
) -> None:
    """The unit each side emits means its key's value kind, so neither reads as UNIT_MISMATCH."""
    policy = v7.normalisation_policy
    assert v7.mapping_set.normalisation_policy_version == policy.version == "v2"
    row = v7.dictionary.row(v7.mapping_set.entry(entry_id).canonical_id)
    assert policy.units[raw_unit].value_kind is row.value_kind is ValueKind.PERCENTAGE


def test_config_v3_and_v7_load_with_assumed_vendor_denominators(v7: LoadedConfig) -> None:
    """Every vendor pairing rests on the assumed SCRR denominator (R10); none is evidence-stated."""
    mapping_set = v7.mapping_set
    assert v7.dictionary.version == "v3"
    vendor = [entry for entry in mapping_set.entries if entry.surface in VENDOR_SURFACES]
    vendor = [entry for entry in vendor if entry.canonical_id.startswith("shp_")]
    assert len(vendor) == 17  # §13.5: 17 nodes ruled to a key
    assert all(
        MappingAssumption.DENOMINATOR_ASSUMED in entry.assumptions
        and entry.dimension_members["denominator"] == "TOTAL_SHARES"
        for entry in vendor
    )
    institutions = mapping_set.entry("tijori.shp.institutions")
    assert institutions.assumptions == BOTH
    assert institutions.canonical_id == "shp_institutions_domestic_plus_foreign_pct"
    # A boundary fixed by structure (Tijori Public Shareholding = B + C2, §7) is not assumed.
    assert mapping_set.entry("tijori.shp.public_shareholding").assumptions == BOTH[:1]


def test_config_first_party_selector_takes_only_its_member() -> None:
    """B and B1 share element and axis; only the member decides, else B1 would land on B."""
    axis = f"{{{SHP_NS}}}CategoryOfShareholdersAxis"
    context = {
        "dimension_axes": [axis],
        "dimension_qnames": [[axis, f"{{{SHP_NS}}}InstitutionsDomesticMember"]],
        "dimensions": {"in-bse-shp:CategoryOfShareholdersAxis": "InstitutionsDomesticMember"},
    }
    axis_name = "CategoryOfShareholdersAxis"
    assert matches_dimensions(context, SHP_NS, axis_name, "InstitutionsDomesticMember")
    assert not matches_dimensions(context, SHP_NS, axis_name, "PublicShareholdingMember")


def test_config_vendor_selector_matches_path_and_quarterly(v7: LoadedConfig) -> None:
    """A vendor node maps by its full label path at quarterly periodicity, never its bare label."""
    selector = v7.mapping_set.entry("tijori.shp.institutions").selector
    node = {
        "statement_family": "SHAREHOLDING",
        "label": "Institutions",
        "path": ["Public Shareholding", "Institutions"],
        "periodicity": "quarterly",
    }
    assert selector_matches(selector, node)
    assert not selector_matches(selector, {**node, "path": ["Institutions"]})
    assert not selector_matches(selector, {**node, "periodicity": "yearly"})


def test_config_basket_with_member_and_descendant_is_refused(tmp_path: Path) -> None:
    """B already contains B4, so a B + B4 basket would double count B4."""
    shutil.copytree(CONFIG_ROOT / "dictionary" / "v3", tmp_path / "v3")
    path = tmp_path / "v3" / FORMULA_SET_FILE
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    row = next(
        row
        for row in doc["rows"]
        if row["canonical_id"] == "shp_public_shareholding_plus_employee_trust_pct"
    )
    row["formula"]["operands"][0]["aggregation"]["input_members"] = [
        "public_shareholding",
        "non_institutions",
    ]
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    with pytest.raises(DictionaryLoadError) as raised:
        load_dictionary(tmp_path, "v3")
    assert raised.value.defect is DictionaryDefect.MEMBER_OF_MEMBER


# --- Task 5: the shareholding run family and family isolation (selected by ``-k family``) ---

APAR = "APARINDS"
RESULTS_MANIFEST = REPO_ROOT / "data" / "raw" / "watchlist" / "aparinds" / "retrieval-manifest.json"
RESULTS_XBRL = "INTEGRATED_FILING_INDAS_1701114_24072026063426_WEB.xml"  # Q1 FY27, 2026-06-30
SHP_ARGS: tuple[str, ...] = ("--family", "shareholding", "--dictionary", "v3")
SHP_ARGS += ("--mapping-set", "v7", "--normalisation-policy", "v2")
# The results set that reads the in-capmkt 2026-01-31 taxonomy Apar's Q1 FY27 XBRL files.
RESULTS_ARGS = ("--dictionary", "v2", "--mapping-set", "v6")
# ``request_for``'s default-family JSON digest and run identity at HEAD 70647c0 (plan D8 Task 5),
# computed there with the request built in ``_default_request``.
HEAD_REQUEST_SHA256 = "23bd185448fb55ed48f3c17efda00b37bc93c6b594ed6e8d841df842df4ddd9c"
HEAD_IDENTITY_HASH = "e77ecf35d57faf48becb1273713ce22cb62aa599c8873c4ac24129ad41a59fca"


def _default_request() -> RunRequest:
    """A default-family request with fixed extractor pins, so no source bytes enter it."""
    pins = {
        Representation.XBRL: VersionPin(version="x", content_sha256="a" * 64),
        Representation.PDF: VersionPin(version="p", content_sha256="b" * 64),
    }
    return request_for(
        7,
        INSTANT,
        Basis.CONSOLIDATED,
        cutoff=datetime(2026, 7, 31, tzinfo=UTC),
        config_root=CONFIG_ROOT,
        code_version="c",
        database_identity=DatabaseIdentity(host="h", port=1, name="n"),
        extractor_pins=pins,
    )


def test_family_default_identity_is_unchanged() -> None:
    """A results request serialises and hashes exactly as before ``RunScope.family`` existed."""
    request = _default_request()
    manifest = RunManifest(**dict(request), inputs=(), status=RunStatus.COMPLETE)
    assert hashlib.sha256(request.model_dump_json().encode()).hexdigest() == HEAD_REQUEST_SHA256
    assert manifest.identity_hash() == HEAD_IDENTITY_HASH
    assert "family" not in request.scope.model_dump(mode="json")


@pytest.mark.parametrize(
    ("family", "sources", "bases"),
    [
        (FilingFamily.FINANCIAL_RESULTS, (SHP_XBRL[1],), (Basis.STANDALONE,)),
        (FilingFamily.SHAREHOLDING, ("NSE_XBRL_INSTANCE",), (Basis.STANDALONE,)),
        (FilingFamily.SHAREHOLDING, (SHP_XBRL[1],), (Basis.CONSOLIDATED,)),
    ],
    ids=["results-names-shp", "shareholding-names-results", "shareholding-consolidated"],
)
def test_family_scope_refuses_another_familys_source_or_basis(
    family: FilingFamily, sources: tuple[str, ...], bases: tuple[Basis, ...]
) -> None:
    """Each family reads only its own first-party surfaces; shareholding is standalone only."""
    with pytest.raises(ValidationError):
        RunScope(
            entity_ids=(1,), period_ends=(INSTANT,), bases=bases, sources=sources, family=family
        )


def test_family_no_currency_is_invented() -> None:
    """A monetary operand with no reporting currency is refused, never keyed in a guessed one."""
    dictionary = load_dictionary(CONFIG_ROOT / "dictionary", "v3")
    row, operand = next(
        (row, operand)
        for row in dictionary.rows
        if row.formula is not None
        for operand in row.formula.operands
        if dictionary.row(operand.canonical_id).value_kind is ValueKind.CURRENCY_AMOUNT
    )
    output = MeasurementKey(
        entity_id=1,
        canonical_id=row.canonical_id,
        period=PeriodInterval.duration(date(2026, 4, 1), INSTANT),
        basis=Basis.CONSOLIDATED,
        framework=AccountingFramework.IND_AS,
        currency="INR" if row.value_kind is ValueKind.CURRENCY_AMOUNT else None,
        value_kind=row.value_kind,
        dimensions=DimensionSet(),
    )
    with pytest.raises(CurrencyMismatchError):
        resolve_operand_keys(output, operand, dictionary=dictionary, reporting_currency=None)


def _compare(*args: str) -> tuple[int, str]:
    """``fundamentals compare <args>`` in process; its exit code and stdout."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = main(["compare", *args])
    return code, out.getvalue()


def _run(end: date = INSTANT, *, shareholding: bool = True) -> tuple[int, int]:
    """``compare run`` over Apar: the shareholding family (standalone) or results; its exit
    code and run id."""
    scope = ("--entity", APAR, "--period-end", end.isoformat())
    basis = ("--basis", "standalone" if shareholding else "consolidated")
    family = SHP_ARGS if shareholding else RESULTS_ARGS
    code, out = _compare("run", *scope, *basis, *family)
    assert code != RunExitStatus.FAILURE, out
    return code, int(out.split("\n")[0].split("\t")[1])


def _ingest_results(snapshots: Path) -> None:
    """Apar's Q1 FY27 results XBRL through ``evidence ingest`` (consolidated, XBRL only)."""
    inputs = snapshots.parent / "results-inputs" / "nse"
    for folder in (inputs, snapshots):
        folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    shutil.copyfile(RESULTS_MANIFEST.parent / "nse" / RESULTS_XBRL, inputs / RESULTS_XBRL)
    argv = [
        *("evidence", "ingest", "--retrieval-manifest", str(RESULTS_MANIFEST)),
        *("--issuer", APAR, "--quarter", "FY27_Q1", "--period-end", INSTANT.isoformat()),
        *("--basis", "consolidated", "--raw-root", str(inputs.parent)),
        *("--snapshot-root", str(snapshots), "--member", "xbrl=xbrl-consolidated"),
        *RESULTS_ARGS,
    ]
    assert main(argv) == 0


def _states(db: PgTestDatabase, run_id: int) -> list[tuple[Any, ...]]:
    """A run's rows as id-free tuples: row, statuses and each source's state, reason, value."""
    with db.runtime_pool() as pool:
        rows = load_results(run_id, pool=pool)
    return [
        (
            row.row_id,
            row.extraction_status,
            row.corroboration_status,
            [
                (v.source_role, v.representation, v.state, v.reason, v.value)
                for v in row.source_values
            ],
        )
        for row in rows
    ]


def _replays(db: PgTestDatabase, run_id: int) -> None:
    """``replay_run`` recomputes the stored rows exactly."""
    with db.runtime_pool() as pool:
        assert replay_run(run_id, pool=pool, config_root=CONFIG_ROOT) == load_results(
            run_id, pool=pool
        )


@pytest.fixture(scope="module")
def stored(
    pg_template: PgTestDatabase, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[tuple[PgTestDatabase, int]]:
    """Apar's results package and gen-2 SHP package, and the shareholding run's id."""
    snapshots = tmp_path_factory.mktemp("family") / "snapshots"
    with cloned_database(pg_template) as db, pytest.MonkeyPatch.context() as patch:
        for name, value in db.cli_env().items():
            patch.setenv(name, value)
        patch.setattr(socket.socket, "connect", _refuse_socket)
        _seed(db, APAR)
        _ingest_results(snapshots)
        assert _ingest(RAW, snapshots, APAR) == 0
        yield db, _run()[1]


def _leaf_families(dictionary: CanonicalDictionary, key: MeasurementKey) -> set[StatementFamily]:
    """A row's own family, or a formula row's operand families."""
    row = dictionary.row(key.canonical_id)
    if row.formula is None:
        return {row.family}
    return {dictionary.row(operand.canonical_id).family for operand in row.formula.operands}


@pytest.mark.pg
@pytest.mark.retained
def test_family_shareholding_run_through_the_cli(stored: tuple[PgTestDatabase, int]) -> None:
    """Only shareholding rows, filing-only with extraction NOT_APPLICABLE, no currency, under
    ``nse-shp-v1``; the replay reproduces them. (The plan's ``FILING_ONLY`` predates R10: an
    unsupported-precision percentage is ``NOT_COMPARABLE``, an unfiled line ``NO_SOURCE``.)"""
    db, run_id = stored
    dictionary = load_dictionary(CONFIG_ROOT / "dictionary", "v3")
    with db.runtime_pool() as pool:
        manifest = RunStore(pool).read_manifest(run_id)
        rows = load_results(run_id, pool=pool)
    assert manifest.scope.family is FilingFamily.SHAREHOLDING
    assert manifest.pinned.extractor_xbrl.version == SHP_EXTRACTOR_VERSION
    leaves = {family for row in rows for family in _leaf_families(dictionary, row.key)}
    assert rows and leaves == {StatementFamily.SHAREHOLDING}
    # Filing only (no vendor side); R10: a percentage side is NOT_COMPARABLE, never a value.
    assert {v.source_role for r in rows for v in r.source_values} == {SourceRole.FIRST_PARTY}
    assert {(r.corroboration_status, r.corroboration_reason) for r in rows} == {
        (CorroborationStatus.NOT_COMPARABLE, ReasonCode.PRECISION_UNSUPPORTED),
        (CorroborationStatus.NO_SOURCE, None),
    }
    assert {r.extraction_status for r in rows} == {ExtractionStatus.NOT_APPLICABLE}
    assert {(r.key.currency, r.key.framework) for r in rows} == {
        (None, AccountingFramework.UNKNOWN)
    }
    _replays(db, run_id)


@pytest.mark.pg
@pytest.mark.retained
def test_family_direct_sides_keep_the_filed_value_and_residuals_refuse(
    stored: tuple[PgTestDatabase, int],
) -> None:
    """Each direct percentage side stores the filed lexeme x100 with no interval and stays
    ``INVALID / PRECISION_UNSUPPORTED``; each v3 residual row's first-party side refuses, naming
    every operand, with no value (R10: the formal outcome is unchanged)."""
    db, run_id = stored
    dictionary = load_dictionary(CONFIG_ROOT / "dictionary", "v3")
    filed = _filed(APAR)
    with db.runtime_pool() as pool:
        rows = load_results(run_id, pool=pool)
        repository = EvidenceRepository(pool)
        xbrl = {(r, v.representation): v for r in rows for v in r.source_values}
        direct = [
            (row, value)
            for (row, rep), value in xbrl.items()
            if rep is Representation.XBRL
            and row.value_identity is ValueIdentity.REPORTED
            and row.key.canonical_id == "shp_holding_pct"
        ]
        assert direct
        lexemes = {
            (SEBI_ROWS[member], "TOTAL_SHARES" if element == TS else "VOTING_RIGHTS"): text
            for (member, element), text in filed.items()
            if member in SEBI_ROWS
        }
        for row, value in direct:
            members = dict(row.key.dimensions.pairs)
            assert (value.state, value.reason) == (SourceState.INVALID, "PRECISION_UNSUPPORTED")
            assert value.lower is value.upper is None and value.interpretation_id is not None
            lexeme = lexemes.get((members["shareholding_category"], members["denominator"]))
            if lexeme is not None:
                assert value.value == Decimal(lexeme) * 100
        residuals = [row for row in rows if row.value_identity is ValueIdentity.DERIVED]
        derived = {
            r.canonical_id
            for r in dictionary.rows
            if r.formula and r.canonical_id.startswith("shp_")
        }
        assert {row.key.canonical_id for row in residuals} == derived
        for row in residuals:
            side = xbrl[(row, Representation.XBRL)]
            assert side.calculation_state in (
                CalculationState.OPERAND_INVALID,
                CalculationState.OPERAND_MISSING,
            )
            assert side.value is None and row.key.currency is None
            assert side.calculation_trace_id is not None
            (trace,) = repository.get_calculation_traces([side.calculation_trace_id])
            formula = dictionary.row(row.key.canonical_id).formula
            assert formula is not None
            named = {operand.name for operand in trace.trace.operands}
            assert {operand.name for operand in formula.operands} <= named


@pytest.mark.pg
@pytest.mark.retained
def test_family_non_quarter_end_instant_runs(guarded: PgTestDatabase, tmp_path: Path) -> None:
    """The Task 4 off-quarter generation runs at its own instant (no fiscal periods read)."""
    _seed(guarded, APAR)

    def edit(folder: Path, entries: list[dict[str, Any]]) -> None:
        _rewrite(SHP_LISTING, b'"date":"30-JUN-2026"', b'"date":"13-AUG-2026"')(folder, entries)
        _rewrite(SHP_XBRL, b"2026-06-30", b"2026-08-13")(folder, entries)

    raw = _marked(tmp_path / "raw", APAR, edit)
    assert _ingest(raw, tmp_path / "snapshots", APAR, OFF_QUARTER) == 0
    _, run_id = _run(OFF_QUARTER)
    with guarded.runtime_pool() as pool:
        rows = load_results(run_id, pool=pool)
    assert rows and {row.key.period for row in rows} == {PeriodInterval.at(OFF_QUARTER)}
    _replays(guarded, run_id)


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize("pair", [SHP_LISTING, SHP_XBRL], ids=["listing", "filing"])
def test_family_failed_first_party_acquisition_is_unavailable(
    guarded: PgTestDatabase, tmp_path: Path, pair: tuple[str, str]
) -> None:
    """After a failed listing (or SHP instance) request the shareholding run's filing sides are
    ``UNAVAILABLE`` citing that attempt and the run is ``INCOMPLETE``; a results run of the
    same entity is unchanged by the failed listing attempt."""
    entity_id = _seed(guarded, APAR)
    snapshots = tmp_path / "snapshots"
    _ingest_results(snapshots)
    _, results = _run(shareholding=False)
    raw = _marked(tmp_path / "raw", APAR, _fail(pair, "HTTP_503"))
    assert _ingest(raw, snapshots, APAR) != 0
    with guarded.runtime_pool() as pool:
        attempts = EvidenceRepository(pool).list_attempts(entity_id, INSTANT)
    (attempt,) = [item for item in attempts if item.surface == pair[1]]
    code, run_id = _run()
    assert code == RunExitStatus.INCOMPLETE
    with guarded.runtime_pool() as pool:
        manifest = RunStore(pool).read_manifest(run_id)
        rows = load_results(run_id, pool=pool)
    assert manifest.status is RunStatus.INCOMPLETE and rows
    for row in rows:
        (side,) = [
            v
            for v in row.source_values
            if v.source_role is SourceRole.FIRST_PARTY and v.representation is Representation.XBRL
        ]
        assert (side.state, side.attempt_id) == (SourceState.UNAVAILABLE, attempt.attempt_id)
    _replays(guarded, run_id)
    again = _run(shareholding=False)[1]
    assert again == results  # same identity: the listing attempt is not a results input


def _ingest_family(snapshots: Path, *, shareholding: bool) -> None:
    """Ingest Apar's gen-2 SHP or its Q1 FY27 results XBRL."""
    if shareholding:
        assert _ingest(RAW, snapshots, APAR) == 0
    else:
        _ingest_results(snapshots)


def _reported(*args: str) -> int | None:
    """The run id ``compare report`` prints for a lookup, or ``None`` when it finds none."""
    code, out = _compare("report", "--entity", APAR, "--period-end", INSTANT.isoformat(), *args)
    return int(out.split("\n")[0].split("\t")[1]) if code == RunExitStatus.SUCCESS else None


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize("results_first", [True, False], ids=["results-first", "shp-first"])
def test_family_isolation_and_report_lookup(
    guarded: PgTestDatabase, tmp_path: Path, results_first: bool
) -> None:
    """``compare report`` finds each family's run in either creation order (a results lookup
    never returns the shareholding run, even on its basis), and the family run first stored
    has the same rows and states once the other family's package exists."""
    _seed(guarded, APAR)
    snapshots = tmp_path / "snapshots"
    first = not results_first
    _ingest_family(snapshots, shareholding=first)
    runs = {first: _run(shareholding=first)[1]}
    alone = _states(guarded, runs[first])
    _ingest_family(snapshots, shareholding=not first)
    runs[not first] = _run(shareholding=not first)[1]
    assert _reported("--basis", "consolidated") == runs[False]
    assert _reported("--basis", "standalone", "--family", "shareholding") == runs[True]
    assert _reported("--basis", "standalone") is None
    assert _states(guarded, _run(shareholding=first)[1]) == alone


@pytest.mark.pg
@pytest.mark.retained
def test_family_later_revision_supersedes_within_its_family(
    guarded: PgTestDatabase, tmp_path: Path
) -> None:
    """A later SHP broadcast supersedes the first within the shareholding family: the new run
    reads only the revision's interpretations, and the results run's keys and rows do not move."""
    entity_id = _seed(guarded, APAR)
    snapshots = tmp_path / "snapshots"
    _ingest_family(snapshots, shareholding=False)
    _ingest_family(snapshots, shareholding=True)
    before = _states(guarded, _run(shareholding=False)[1])
    first = _run()[1]

    def revise(folder: Path, entries: list[dict[str, Any]]) -> None:
        _rewrite(SHP_LISTING, b'"broadcastDate":"14-JUL-2026', b'"broadcastDate":"15-JUL-2026')(
            folder, entries
        )
        (entry,) = [e for e in entries if (e["source_id"], e["surface"]) == SHP_XBRL]
        path = folder / entry["filename"]
        path.write_bytes(path.read_bytes() + b"<!-- marked revision -->\n")

    assert _ingest(_marked(tmp_path / "raw", APAR, revise), snapshots, APAR) == 0
    with guarded.runtime_pool() as pool:
        packages = EvidenceRepository(pool).list_packages(
            entity_id, FilingFamily.SHAREHOLDING, INSTANT
        )
    (revision,) = [package for package in packages if package.supersedes_package_id is not None]
    capture = revision.members[Representation.XBRL].capture.capture_ref_id
    assert capture is not None
    _, second = _run()
    assert second != first
    with guarded.runtime_pool() as pool:
        rows = load_results(second, pool=pool)
        revised = EvidenceRepository(pool).list_capture_interpretations(capture)
    read = {v.interpretation_id for r in rows for v in r.source_values} - {None}
    assert read and read <= {item.interpretation_id for item in revised}
    assert _states(guarded, _run(shareholding=False)[1]) == before


# --- stage D8.3 (Task 6): vendor trees, pins and vendor request failures ---------------------

VENDOR = (SCREENER_SHAREHOLDING, SCREENER_INVESTORS, TIJORI_SHAREHOLDING, UPSTOX_SHAREHOLDING)
# d8-probe.md §13.4 node counts per company; Screener as (nodes, drill-down holders).
SCREENER_TREE = {"APARINDS": (120, 109), "ETERNAL": (109, 97), "TITAN": (865, 851)}
TIJORI_TREE = {"APARINDS": 29, "ETERNAL": 21, "TITAN": 35}
CUSTODIANS_DR = "SharesheldbyCustodians-DR"  # Tijori myid; a dash in every column (§13.4)
# The existing vendor extractor pins, computed at HEAD 2e22dec before Task 6.
EXISTING_PINS = {
    ("screener-subscriber", "SCREENER_FINANCIALS"): (
        "screener-v1",
        "9ffad9ac400ba8913edf7bdc69151ce24448ed53311ee4d9c7e82f64d90b15a0",
    ),
    ("tijori", "financials"): (
        "tijori-v4",
        "f7f3689c338667cae8a99adcc2ba4bf0fade9294a3ccea690c3b63c57f099901",
    ),
    ("upstox", "income-statement"): (
        "upstox-v2",
        "351b2aed43565d6191d1afb5ffeeb568f9d03ede9cd55a41ba96b06611249478",
    ),
}
Evidence = list[tuple[AcquisitionAttempt, tuple[Occurrence, ...], dict[int | None, Interpretation]]]


def _vendor(db: PgTestDatabase, entity_id: int) -> Evidence:
    """Each vendor attempt at the instant, with its capture's occurrences and interpretations."""
    found: Evidence = []
    with db.runtime_pool() as pool:
        repository = EvidenceRepository(pool)
        for attempt in repository.list_attempts(entity_id, INSTANT):
            if (attempt.source_id, attempt.surface) not in VENDOR or attempt.capture is None:
                continue
            ref = attempt.capture.capture_ref_id
            assert ref is not None
            rows = {row.occurrence_id: row for row in repository.list_capture_interpretations(ref)}
            found.append((attempt, repository.list_capture_occurrences(ref), rows))
    return found


def _entries(root: Path, symbol: str) -> list[dict[str, Any]]:
    return list(json.loads((root / symbol / GEN / MANIFEST_NAME).read_bytes())["entries"])


def _node(occurrence: Occurrence) -> tuple[Any, ...]:
    context = occurrence.native_context
    return tuple(context["path"]), context["source_node_id"], context["periodicity"]


def _offered(raw: dict[str, Any]) -> list[str]:
    return [key for key in raw if key != "setAttributes"]


@pytest.mark.pg
@pytest.mark.retained
def test_tree_every_node_and_printed_cell_is_one_occurrence(
    ingested: tuple[PgTestDatabase, Path, dict[str, int]],
) -> None:
    """Owner amendment (R11): over gen-2 every vendor node has one node occurrence and one cell
    occurrence per printed cell, with label, parent, path, depth and periodicity. The inventory
    equals §13.4 and the retained bodies: Tijori's custodians row keeps its dashes, a holder
    lacking a period has no cell for it, Apar's empty bucket has no holder, and no value is a
    zero that was not printed."""
    db, _, entities = ingested
    late_holder = False
    for symbol, entity_id in entities.items():
        bodies = {e["sha256"]: e for e in _entries(RAW, symbol) if e["filename"]}
        nodes: dict[str, list[dict[str, Any]]] = {"screener-subscriber": [], "tijori": []}
        empty = 0
        for attempt, occurrences, rows in _vendor(db, entity_id):
            assert attempt.outcome is ExtractionOutcome.COMPLETE and attempt.capture is not None
            entry = bodies[attempt.capture.blob_sha256]
            body = (RAW / symbol / GEN / entry["filename"]).read_bytes()
            heads: dict[tuple[Any, ...], dict[str, Any]] = {}
            cells: dict[tuple[Any, ...], list[str]] = {}
            for occurrence in occurrences:
                row, context = rows[occurrence.occurrence_id], occurrence.native_context
                path = context["path"]
                assert context["label"] == path[-1] and context["depth"] == len(path)
                assert context["parent"] == (path[-2] if len(path) > 1 else None)
                if context["kind"] == "NODE":
                    assert occurrence.raw_value_text is None and row.key is None
                    assert row.status is InterpretationStatus.UNMAPPED
                    assert _node(occurrence) not in heads
                    heads[_node(occurrence)] = context
                else:
                    cells.setdefault(_node(occurrence), []).append(context["period_label"])
                if row.value == 0:
                    assert occurrence.missing_state is MissingValueState.ZERO_PRINTED
                    assert Decimal(str(occurrence.raw_value_text).rstrip("%")) == 0
                if occurrence.missing_state is not MissingValueState.VALUE:
                    assert row.value in (None, 0)
            assert set(cells) <= set(heads)
            assert all(cells.get(key, []) == head["periods"] for key, head in heads.items())
            if attempt.source_id == "upstox":
                assert {h["label"]: h["periods"] for h in heads.values()} == {
                    item["category"]: [point["period"] for point in item["history"]]
                    for item in json.loads(body)["data"]
                }
                continue
            nodes[attempt.source_id].extend(heads.values())
            if attempt.surface == SCREENER_INVESTORS[1]:
                holders = json.loads(body)
                assert {h["label"]: h["periods"] for h in heads.values()} == {
                    name: _offered(values) for name, values in holders.items()
                }
                empty += not holders
                late_holder |= any(
                    h["periodicity"] == "quarterly" and "Jun 2026" not in h["periods"]
                    for h in heads.values()
                )
            elif attempt.surface == SCREENER_SHAREHOLDING[1]:
                root = html.fromstring(body)
                for periodicity in ("quarterly", "yearly"):
                    table = root.xpath(f"//div[@id='{periodicity}-shp']//table")[0]
                    labels = [th.text_content().strip() for th in table.xpath(".//thead//th")[1:]]
                    page = [h for h in heads.values() if h["periodicity"] == periodicity]
                    assert len(page) == len(table.xpath(".//tbody/tr[td]"))
                    assert all(h["periods"] == labels for h in page)
            else:
                rows_html = html.fromstring(body).xpath(
                    "//table[@id='company_detailed']//tr[@myid]"
                )
                assert len(heads) == len(rows_html) == TIJORI_TREE[symbol]
                (dr,) = [key for key in heads if key[1] == CUSTODIANS_DR]
                dashes = [
                    o for o in occurrences if _node(o) == dr and o.native_context["kind"] == "CELL"
                ]
                assert dashes and all(o.missing_state is MissingValueState.DASH for o in dashes)
                assert {o.raw_value_text for o in dashes} == {"—"}
        screener = nodes["screener-subscriber"]
        holders = [node for node in screener if node["depth"] == 2]
        assert (len(screener), len(holders)) == SCREENER_TREE[symbol]
        if symbol == APAR:  # quarterly ``public`` and yearly ``government`` are ``{}`` (§13.4)
            assert empty == 2
            quarterly = [n for n in screener if n["periodicity"] == "quarterly"]
            assert any(n["path"] == ["Public"] for n in quarterly)
            assert not any(n["parent"] == "Public" for n in quarterly)
    assert late_holder


@pytest.mark.pg
@pytest.mark.retained
def test_tree_cells_land_at_v7_keys_and_off_quarter_months_are_ambiguous(
    ingested: tuple[PgTestDatabase, Path, dict[str, int]],
) -> None:
    """A ruled quarterly cell is keyed at its v7 category, the assumed denominator and the share
    class, with the assumption traced; the yearly row is a diagnostic; Apar's ``Aug 2026``
    column (Upstox, d8-probe.md §6) is ``PERIOD_AMBIGUOUS`` and keyless."""
    db, _, entities = ingested
    cells = {
        (attempt.surface, *_node(o)[0::2], o.native_context["period_label"]): rows[o.occurrence_id]
        for attempt, occurrences, rows in _vendor(db, entities[APAR])
        for o in occurrences
        if o.native_context["kind"] == "CELL"
    }
    members = {
        "shareholding_category": "sebi_promoter_group",
        "denominator": "TOTAL_SHARES",
        "share_class": COMPANIES[APAR][0],
    }
    for surface, label in (("SCREENER_SHAREHOLDING", "Promoters"), ("share-holdings", "promoters")):
        june = cells[(surface, (label,), "quarterly", "Jun 2026")]
        assert june.key is not None and june.period == PeriodInterval.at(INSTANT)
        assert dict(june.key.dimensions.pairs) == members
        assert june.transform_trace["assumptions"] == ["DENOMINATOR_ASSUMED"]
    yearly = cells[("SCREENER_SHAREHOLDING", ("Promoters",), "yearly", "Mar 2026")]
    assert yearly.status is InterpretationStatus.UNMAPPED and yearly.key is None
    august = cells[("share-holdings", ("promoters",), "quarterly", "Aug 2026")]
    assert august.status is InterpretationStatus.PERIOD_AMBIGUOUS and august.key is None
    assert august.canonical_id == "shp_holding_pct"


@pytest.mark.pg
@pytest.mark.retained
def test_tree_a_deeper_drilldown_level_is_unsupported_schema(
    guarded: PgTestDatabase, tmp_path: Path
) -> None:
    """A drill-down holder carrying ``isExpandable`` is an unread level: the body is refused
    ``UNSUPPORTED_SCHEMA`` with no occurrence, never read short (R11 Depth)."""
    entity_id = _seed(guarded, APAR)
    (bucket,) = [e for e in _entries(RAW, APAR) if e["url"].endswith("/promoters/quarterly/")]

    def edit(folder: Path, entries: list[dict[str, Any]]) -> None:
        path = folder / bucket["filename"]
        path.write_bytes(path.read_bytes().replace(b'": {"', b'": {"isExpandable": true, "', 1))

    assert _ingest(_marked(tmp_path / "raw", APAR, edit), tmp_path / "snapshots", APAR) == 0
    evidence = _vendor(guarded, entity_id)
    refused = [(a, o) for a, o, _ in evidence if a.outcome is not ExtractionOutcome.COMPLETE]
    ((attempt, occurrences),) = refused
    assert (attempt.source_id, attempt.surface) == SCREENER_INVESTORS
    assert attempt.outcome is ExtractionOutcome.UNSUPPORTED_SCHEMA
    assert attempt.reason is not None and "isExpandable" in attempt.reason
    assert occurrences == ()


@pytest.mark.pg
@pytest.mark.retained
def test_pins_existing_vendor_extractors_are_unchanged_and_tree_sources_are_pinned(
    guarded: PgTestDatabase, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The ``screener-v1``, ``tijori-v4`` and ``upstox-v2`` pins equal HEAD's. The tree surfaces
    pin their own versions, and one changed byte in the tree extractor under its pinned version
    is drift, refused before any vendor evidence is written."""
    for pair, pinned in EXISTING_PINS.items():
        pin = vendor_extractor_pin(*pair)
        assert (pin.version, pin.content_sha256) == pinned
    versions = {pair: vendor_extractor_pin(*pair).version for pair in VENDOR}
    assert set(versions.values()) == {"screener-shp-v1", "tijori-shp-v1", "upstox-shp-v1"}
    _seed(guarded, APAR)
    snapshots = tmp_path / "snapshots"
    assert _ingest(RAW, snapshots, APAR) == 0
    source = tmp_path / "src"
    shutil.copytree(run_config._SOURCE_ROOT, source, ignore=shutil.ignore_patterns("__pycache__"))
    extractor = source / "evidence" / "vendor_shareholding.py"
    extractor.write_bytes(extractor.read_bytes() + b"\n")
    monkeypatch.setattr(run_config, "_SOURCE_ROOT", source)
    before = {table: count(guarded, table) for table in EVIDENCE_TABLES}
    assert _ingest(RAW, snapshots, APAR) != 0
    assert {table: count(guarded, table) for table in EVIDENCE_TABLES} == before
    for pair, pinned in EXISTING_PINS.items():
        pin = vendor_extractor_pin(*pair)
        assert (pin.version, pin.content_sha256) == pinned


def _fail_first(pair: tuple[str, str]) -> Any:
    """The first request on ``pair`` answered HTTP 503 with no body; a failed Screener page
    offers no drill-down, so its bucket requests are not made."""

    def edit(folder: Path, entries: list[dict[str, Any]]) -> None:
        entry = next(e for e in entries if (e["source_id"], e["surface"]) == pair)
        (folder / entry["filename"]).unlink()
        entry.update(outcome="HTTP_503", filename=None, sha256=None, bytes=None)
        if pair == SCREENER_SHAREHOLDING:
            entries[:] = [
                e for e in entries if (e["source_id"], e["surface"]) != SCREENER_INVESTORS
            ]

    return edit


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize(
    "pair", [SCREENER_SHAREHOLDING, SCREENER_INVESTORS, UPSTOX_SHAREHOLDING], ids=lambda p: p[1]
)
def test_vendor_failed_request_is_its_attempt(
    guarded: PgTestDatabase, tmp_path: Path, pair: tuple[str, str]
) -> None:
    """R8: after a complete generation, a later one whose Screener page, drill-down or Upstox
    request failed records that request as one capture-less attempt; ingest still succeeds and
    the earlier evidence is untouched (its run consequences are Task 6's run half)."""
    entity_id = _seed(guarded, APAR)
    snapshots = tmp_path / "snapshots"
    assert _ingest(RAW, snapshots, APAR) == 0
    before = _vendor(guarded, entity_id)
    raw = _marked(tmp_path / "raw", APAR, _fail_first(pair))
    (entry,) = [e for e in _entries(raw, APAR) if e["outcome"] != "OK"]
    assert _ingest(raw, snapshots, APAR) == 0
    with guarded.runtime_pool() as pool:
        attempts = EvidenceRepository(pool).list_attempts(entity_id, INSTANT)
    (failed,) = [a for a in attempts if a.capture is None]
    identity = {"source_id": pair[0], "surface": pair[1], "request_key": entry["request_key"]}
    assert (failed.stage, failed.source_id, failed.surface) == (AttemptStage.ACQUISITION, *pair)
    assert failed.outcome is ExtractionOutcome.FAILED and failed.period_end == INSTANT
    assert failed.reason is not None and entry["request_key"] in failed.reason
    assert failed.input_sha256 == input_digest({**identity, "capture_id": None})
    assert _vendor(guarded, entity_id) == before
