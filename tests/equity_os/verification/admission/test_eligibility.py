"""Check class, the eligibility artifact and three-way coverage (VENDOR-1 spec §6.6, §6.11 #3
and #8; plan Task 7), through ``eqos compare run`` and ``eqos vendor measure``.

LAURUSLABS Q3 FY25 under mapping set v9 (values in ``test_compare_vendor_runs``): revenue and
depreciation are ``VENDORS_AGREE`` with an agreeing filing; ``finance_costs`` is
``VENDORS_IMPRECISE`` (Screener "58" ± 0.5 crore is wider than 0.5% of it) although the filing,
57.8, agrees with both vendors. POLYCAB's Q3 FY25 filing enumerates its segment members.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml
from test_compare_vendor_runs import CONFIG, LAURUS, POLYCAB, Q3_END, Company, Issuer

from equity_os.companies.identity.identity_seed import EvidenceInputKind, SettingKey
from equity_os.contracts.measurement.canonical import Basis, PeriodKind
from equity_os.contracts.measurement.evidence import Interpretation, VendorExtractorPin
from equity_os.contracts.measurement.measurement_key import MeasurementKey
from equity_os.contracts.measurement.observation import AccountingFramework
from equity_os.contracts.sourcing.source_catalog import SCREENER_PAGE, TIJORI_PAGE
from equity_os.contracts.verification.comparison import SourceRole, SourceState
from equity_os.contracts.verification.vendor_first import FilingState, VendorOutcome
from equity_os.interface.entry.cli import main
from equity_os.normalisation.mapping.mapping import MappingSet
from equity_os.verification.admission.eligibility import (
    EligibilityArtifact,
    coverage,
    load_eligibility,
)
from equity_os.verification.admission.vendor_first import (
    NON_FINANCIAL,
    check_class,
    filing_state,
    vendor_outcome,
)
from equity_os.verification.comparison.run import load_results, replay_inputs
from equity_os.verification.comparison.run_config import ConfigVersions, load_run_config
from equity_os.verification.comparison.run_models import ResultRow, SourceValue

V9 = ("--dictionary", "v2", "--mapping-set", "v9", "--alignment-rules", "v2")
VERSIONS = ConfigVersions(dictionary="v2", mapping_set="v9", alignment_rules="v2")
ENCLOSED, NOT_FILED = "a_wires_and_cables", "z_not_filed"
# Two quarterly lines per vendor repointed to a dimensioned instant row: one member POLYCAB's
# filing enumerates, one it does not.
PROBES = {
    "screener/v4": {"Profit before tax": ENCLOSED, "Other Income": NOT_FILED},
    "tijori/v5": {"PBDT": ENCLOSED, "Other Income": NOT_FILED},
}


@pytest.fixture
def pool(pg_db: Any, monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    """A runtime pool on the test database; the CLI points at it too."""
    for name, value in pg_db.cli_env().items():
        monkeypatch.setenv(name, value)
    with pg_db.runtime_pool() as opened:
        yield opened


@pytest.mark.pg
@pytest.mark.retained
def test_measure_counts_agreeing_cells_with_provenance_and_is_byte_identical(
    pg_db: Any, pool: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """With onboarding provenance known at the run's cutoff, only ``VENDORS_AGREE`` cells with a
    filing state count; imprecise ones add nothing even when the filing agrees. Reruns give
    identical bytes; an early ``available_from`` refuses."""
    issuer = _issuer(LAURUS, pg_db, pool, tmp_path, CONFIG)
    repository = issuer.repository
    discovery = repository.put_evidence_input(EvidenceInputKind.DISCOVERY, "LAURUS", "d" * 64)
    repository.put_settings_record(
        issuer.entity_id, SettingKey.REPORTING_FRAMEWORK, "IND_AS", discovery
    )
    with pool.connection() as conn:
        conn.execute(
            "INSERT INTO eqos.onboarding_records (identifier, identifier_namespace, outcome, "
            "entity_id, evidence_input_id) VALUES ('LAURUSLABS', 'NSE', 'PARTIAL', %s, %s)",
            (issuer.entity_id, discovery),
        )
    run_id = _compare(issuer, capsys)
    available = repository.store_clock()
    first = _measure(available, tmp_path / "first.yaml", capsys)
    second = _measure(available, tmp_path / "second.yaml", capsys)
    assert (tmp_path / "first.yaml").read_bytes() == (tmp_path / "second.yaml").read_bytes()
    assert first == second

    rows = {row.key.canonical_id: row for row in load_results(run_id, pool=pool)}
    classes = {item.class_digest: item for item in first.classes}
    inputs, request, config = replay_inputs(run_id, pool=pool, config_root=CONFIG)
    pins = request.pinned.vendor_extractors
    interpretations = {item.interpretation_id: item for item in inputs.interpretations}
    policy = config.vendor_first_policy
    assert policy is not None
    finance = rows["finance_costs"]
    assert vendor_outcome(finance, interpretations, config.mapping_set, policy)[0] is (
        VendorOutcome.VENDORS_IMPRECISE
    )
    assert filing_state(finance, True) is FilingState.FILING_AGREES
    digests = {
        name: check_class(
            rows[name],
            interpretations,
            mapping=config.mapping_set,
            extractor_pins=pins,
            dictionary_version="v2",
            policy_version="v1",
            issuer_class=NON_FINANCIAL,
            period_kind=PeriodKind.QUARTER,
        )
        for name in ("revenue_from_operations", "depreciation_amortisation", "finance_costs")
    }
    assert digests["finance_costs"] not in classes
    for name in ("revenue_from_operations", "depreciation_amortisation"):
        evidence = classes.pop(digests[name])
        assert (evidence.agrees, evidence.differs, evidence.run_ids) == (1, 0, (run_id,))
        assert not evidence.eligible  # one clean key-period of the policy's four
    assert classes == {}

    early = available - timedelta(days=1)
    out = tmp_path / "early.yaml"
    assert main(_measure_command(early, out)) == 2
    assert "measure refused" in capsys.readouterr().err
    assert not out.exists()


@pytest.mark.pg
@pytest.mark.retained
def test_fresh_run_covers_every_expected_key(
    pg_db: Any, pool: Any, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A fresh run has a three-way comparison for every key both vendors map, the dimensioned
    one included where the filing enumerates its member; the member it does not enumerate
    refuses with Task 5's reason, so nothing is missing (acceptance 3). An Ind AS setting with
    no onboarding provenance gives the entity no class, so its agreeing cells count nowhere."""
    root = tmp_path / "config"
    shutil.copytree(CONFIG, root)
    for files, probes in PROBES.items():
        path = root / "normalisation/mappings" / files / "financials.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        for entry in data["entries"]:
            (label,) = entry["selector"]["labels"]
            if entry["selector"].get("section_equals") in ("quarters", "qt_c") and label in probes:
                entry["canonical_id"] = "segment_liabilities"
                entry["period_rule"] = "COLUMN_CLOSING_INSTANT"
                entry["period_kinds"] = ["QUARTER", "INSTANT"]
                entry["dimension_members"] = {
                    "segment": probes[label],
                    "elimination_basis": "POST_ELIMINATION",
                }
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    issuer = _issuer(POLYCAB, pg_db, pool, tmp_path, root)
    repository = issuer.repository
    month = repository.settings_as_of(
        issuer.entity_id, SettingKey.FISCAL_YEAR_END_MONTH, repository.store_clock()
    )
    assert month is not None
    repository.put_settings_record(
        issuer.entity_id, SettingKey.REPORTING_FRAMEWORK, "IND_AS", month.evidence_input_id
    )
    run_id = _compare(issuer, capsys, "--config-root", str(root))
    out = tmp_path / "unclassed.yaml"
    assert _measure(repository.store_clock(), out, capsys, "--config-root", str(root)).classes == ()
    inputs, _, config = replay_inputs(run_id, pool=pool, config_root=root)
    interpretations = {item.interpretation_id: item for item in inputs.interpretations}
    assert config.vendor_first_policy is not None
    revenue = next(
        row
        for row in load_results(run_id, pool=pool)
        if row.row_id.startswith("revenue_from_operations|2024-10-01..")
    )
    outcome = vendor_outcome(
        revenue, interpretations, config.mapping_set, config.vendor_first_policy
    )
    assert (outcome[0], filing_state(revenue, True)) == (
        VendorOutcome.VENDORS_AGREE,
        FilingState.FILING_AGREES,
    )  # a clean observation, had the entity a class

    found = coverage(pool, run_id, config_root=root)
    assert found.missing == 0 and found.expected == found.three_way + len(found.refused)
    (reason,) = found.refused.values()
    assert "members of dimensioned rows ['segment_liabilities'] cannot be enumerated" in reason
    rows = load_results(run_id, pool=pool)
    enclosed = [
        row
        for row in rows
        if row.key.canonical_id == "segment_liabilities"
        and ("segment", ENCLOSED) in row.key.dimensions.pairs
    ]
    assert [_values(row) for row in enclosed] == [{"XBRL", "screener", "tijori"}]
    assert not [row for row in rows if ("segment", NOT_FILED) in row.key.dimensions.pairs]
    assert _values(revenue) == {"XBRL", "screener", "tijori"}


def test_check_class_changes_with_every_component() -> None:
    """§6.6: each listed component, changed alone, makes a new class."""
    interpretations = {
        1: Interpretation.model_construct(mapping_entry_id="screener.entry"),
        2: Interpretation.model_construct(mapping_entry_id="tijori.entry"),
        3: Interpretation.model_construct(mapping_entry_id="screener.other"),
        4: Interpretation.model_construct(mapping_entry_id="tijori.other"),
    }
    base: dict[str, Any] = {
        "canonical_id": "revenue_from_operations",
        "basis": Basis.CONSOLIDATED,
        "framework": AccountingFramework.IND_AS,
        "sides": (1, 2),
        "mapping": "v9",
        "pins": ("screener-v1", "tijori-v5"),
        "dictionary_version": "v2",
        "policy_version": "v1",
        "issuer_class": NON_FINANCIAL,
        "period_kind": PeriodKind.QUARTER,
    }
    changes: list[dict[str, Any]] = [
        {"canonical_id": "finance_costs"},
        {"basis": Basis.STANDALONE},
        {"framework": AccountingFramework.US_GAAP},
        {"sides": (3, 2)},
        {"sides": (1, 4)},
        {"mapping": "v10"},
        {"pins": ("screener-v2", "tijori-v5")},
        {"pins": ("screener-v1", "tijori-v6")},
        {"dictionary_version": "v3"},
        {"policy_version": "v2"},
        {"issuer_class": "BANK"},
        {"period_kind": PeriodKind.YEAR},
    ]
    digests = [_digest(base | change, interpretations) for change in ({}, *changes)]
    assert len(set(digests)) == len(digests)
    assert _digest(base, interpretations) == digests[0]


def _digest(parts: dict[str, Any], interpretations: dict[int, Interpretation]) -> str:
    """``check_class`` over a row built from ``parts``."""
    key = MeasurementKey.model_construct(
        canonical_id=parts["canonical_id"], basis=parts["basis"], framework=parts["framework"]
    )
    sides = tuple(
        SourceValue.model_construct(
            source_role=SourceRole.INDEPENDENT_VENDOR,
            source_id=page[0],
            surface=page[1],
            state=SourceState.VALUE,
            interpretation_id=interpretation,
        )
        for page, interpretation in zip((SCREENER_PAGE, TIJORI_PAGE), parts["sides"], strict=True)
    )
    pins = tuple(
        VendorExtractorPin(source_id=page[0], surface=page[1], version=version, content_sha256="")
        for page, version in zip((SCREENER_PAGE, TIJORI_PAGE), parts["pins"], strict=True)
    )
    return check_class(
        ResultRow.model_construct(key=key, source_values=sides),
        interpretations,
        mapping=MappingSet.model_construct(version=parts["mapping"]),
        extractor_pins=pins,
        dictionary_version=parts["dictionary_version"],
        policy_version=parts["policy_version"],
        issuer_class=parts["issuer_class"],
        period_kind=parts["period_kind"],
    )


def _issuer(company: Company, pg_db: Any, pool: Any, tmp_path: Path, root: Path) -> Issuer:
    """A company with its Q3 FY25 filing, Screener page and Tijori capture under v9, read from
    ``root``."""
    issuer = Issuer(company, pg_db, pool, tmp_path, VERSIONS)
    issuer.config = load_run_config(root, VERSIONS)
    issuer.first_party()
    issuer.screener(Q3_END)
    issuer.tijori()
    return issuer


def _compare(issuer: Issuer, capsys: pytest.CaptureFixture[str], *args: str) -> int:
    """A default-vendor ``compare run`` of Q3 FY25; the printed run id."""
    symbol = issuer.company.symbol
    command = ["compare", "run", "--entity", symbol, "--period-end", Q3_END.isoformat()]
    assert main([*command, "--basis", "consolidated", *V9, *args]) == 0
    (run_id,) = [
        int(line.split("\t")[1])
        for line in capsys.readouterr().out.splitlines()
        if line.startswith("run\t")
    ]
    return run_id


def _measure_command(available: datetime, out: Path, *args: str) -> list[str]:
    """``vendor measure`` argv."""
    return [
        "vendor",
        "measure",
        "--available-from",
        available.isoformat(),
        "--out",
        str(out),
        *args,
    ]


def _measure(
    available: datetime, out: Path, capsys: pytest.CaptureFixture[str], *args: str
) -> EligibilityArtifact:
    """``vendor measure``; the written artifact. Every counted run prints a ``COVERAGE`` line
    with nothing missing."""
    assert main(_measure_command(available, out, *args)) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines and all(line.startswith("COVERAGE ") and line.endswith(" 0") for line in lines)
    return load_eligibility(out)


def _values(row: ResultRow) -> set[str]:
    """Which sides of a row hold a value: the first-party representation or the vendor."""
    return {
        value.representation.value if value.source_id is None else value.source_id.split("-")[0]
        for value in row.source_values
        if value.state is SourceState.VALUE
    }
