"""VENDOR-1 Task 9 support: the Apar pilot with both vendors' FY26_Q2 captures, for report runs
whose required roles are admitted from the vendors.

``vendor_pilot`` ingests Screener's and Tijori's retained Apar pages into a pilot database.
``withheld`` makes the row-3 world of acceptance 9: no FY26_Q2 package at the comparison run's
cutoff (it is ingested after, as the report path's other sections read it), onboarding
provenance for the issuer class, and an eligibility fixture pinning every required role's
class. Both retained pages map only revenue among the required roles, so the other sides are
test-private marked copies of each vendor's revenue interpretation (``stage1_e2e_support.mark``)
on the role's key; they are fixtures, not source readings.
"""

from __future__ import annotations

import shutil
from datetime import UTC, date, datetime
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any

import prep2b_support
import pytest
import yaml
from evidence_support import CONFIG, XBRL_KIND
from prep2b_support import PINS, STOCK, XBRLS, Pilot
from retained_support import APAR_MANIFEST
from stage1_e2e_support import RUNS, Stage, mark

from equity_os.companies.identity.identity_seed import EvidenceInputKind, SettingKey
from equity_os.contracts.measurement.interval import Interval
from equity_os.contracts.measurement.measurement_key import MeasurementKey
from equity_os.contracts.measurement.role import FactRole
from equity_os.contracts.sourcing.source_catalog import SCREENER_PAGE, TIJORI_PAGE
from equity_os.contracts.verification.config_versions import ConfigVersions
from equity_os.contracts.verification.vendor_first import VendorOutcome
from equity_os.interface.commands.verification.compare_cli import run_compare
from equity_os.interface.entry import draft_admission
from equity_os.interface.entry.cli import _build_parser, main
from equity_os.interface.entry.config import load_config
from equity_os.normalisation.dictionary.role_translation import LEGACY_CONCEPTS
from equity_os.publication.checking.claim_check import CRORE, PER_SHARE
from equity_os.publication.drafting.earnings_update import REQUIRED_ROLES
from equity_os.publication.revision.import_mapping import measurement_key
from equity_os.storage.records.repository import EvidenceRepository
from equity_os.verification.admission.eligibility import (
    ClassEvidence,
    EligibilityArtifact,
    row_class,
)
from equity_os.verification.admission.vendor_first import NON_FINANCIAL, vendor_outcome
from equity_os.verification.comparison.run import load_results, replay_inputs
from equity_os.verification.comparison.run_config import ELIGIBILITY_DIR, load_run_config

QUARTER, END = "FY26_Q2", date(2025, 9, 30)
V9 = ConfigVersions(dictionary="v2", mapping_set="v9", alignment_rules="v2")
VENDORS = ("screener-subscriber/SCREENER_FINANCIALS", "tijori/financials")
ELIGIBILITY = "fixture"
# A vendor side the retained pages lack, in crore (per share for EPS): the quarter's filed
# figure at the vendors' precision (test-private).
MARKED = {
    FactRole.TOTAL_INCOME: Decimal("5743"),
    FactRole.TOTAL_EXPENSES: Decimal("5402"),
    FactRole.PROFIT_BEFORE_TAX: Decimal("341"),
    FactRole.PROFIT_FOR_PERIOD: Decimal("252"),
    FactRole.BASIC_EPS: Decimal("62.66"),
}
CANONICAL = {
    FactRole.TOTAL_INCOME: "total_income",
    FactRole.TOTAL_EXPENSES: "total_expenses",
    FactRole.PROFIT_BEFORE_TAX: "profit_before_tax",
    FactRole.PROFIT_FOR_PERIOD: "profit_for_period",
    FactRole.BASIC_EPS: "eps_basic",
}
# The required roles each retained page has no mapped quarterly line for.
LACKING = {
    SCREENER_PAGE: (FactRole.TOTAL_INCOME, FactRole.TOTAL_EXPENSES),
    TIJORI_PAGE: tuple(MARKED),
}
MAPPINGS = {
    SCREENER_PAGE: "normalisation/mappings/screener/v4/financials.yaml",
    TIJORI_PAGE: "normalisation/mappings/tijori/v5/financials.yaml",
}
ONBOARDED = (
    "INSERT INTO eqos.onboarding_records (identifier, identifier_namespace, outcome, "
    "entity_id, evidence_input_id) VALUES (%s, 'NSE', 'PARTIAL', %s, %s)"
)
WITNESSES = (
    "SELECT c.id, c.source_id FROM eqos.interpretations i "
    "JOIN eqos.capture_refs c ON c.id = i.capture_ref_id WHERE i.id IN (%s, %s) ORDER BY c.id"
)


def role_key(pilot: Pilot, role: FactRole) -> MeasurementKey:
    """A required role's FY26_Q2 key, as the report path keys it."""
    concepts = {
        item.role: item.concept_qname for item in load_config(pilot.config(QUARTER)).concepts.roles
    }
    unit = PER_SHARE if role is FactRole.BASIC_EPS else CRORE
    start = date(2025, 7, 1)
    return measurement_key(LEGACY_CONCEPTS[concepts[role]], unit, pilot.entity_id, start, END)


def vendor_pilot(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch, *, withheld: bool = False
) -> Pilot:
    """The pilot with both vendors' FY26_Q2 pages ingested; ``withheld``: the row-3 world, all
    of it ingested under a config copy (its pins are the database's) that the report path
    reads."""
    root = CONFIG
    if withheld:
        root = request.getfixturevalue("tmp_path") / "vendor-config"
        _config_copy(root)
        monkeypatch.setattr(prep2b_support, "CONFIG", root)
        monkeypatch.setattr(draft_admission, "CONFIG_ROOT", root)
    xbrls = tuple(x for x in XBRLS if not (withheld and x[:2] == (QUARTER, XBRL_KIND)))
    fixtures = ("pg_db", "tmp_path", "monkeypatch", "ingest")
    pilot = Pilot(*(request.getfixturevalue(name) for name in fixtures), xbrls=xbrls)
    pilot.period_ends[QUARTER], pilot.config_root = END, root  # type: ignore[attr-defined]
    with pilot.pg_db.runtime_pool() as pool:
        stage = Stage.__new__(Stage)  # the vendor-ingest half of a Stage, on the pilot's entity
        stage.pg_db, stage.pool, stage.tmp_path = pilot.pg_db, pool, pilot.tmp_path
        stage.run, stage.repository = RUNS["APARINDS-Q2FY26"], EvidenceRepository(pool)
        stage.config, stage.config_root, stage.versions = load_run_config(root, V9), root, V9
        stage.end, stage.entity_id = END, pilot.entity_id
        (pilot.tmp_path / "staged").mkdir(mode=0o700)
        for vendor in VENDORS:
            stage.vendor(vendor, stage.run["vendor_inputs"][vendor].split()[0])
        if withheld:
            _row_three(pilot, stage, root)
    return pilot


def _config_copy(root: Path) -> None:
    """The repo config with a test-private mapping entry per role a vendor page lacks, and
    Screener's quarterly EPS counted equivalent; no native label matches the entries, so every
    capture interprets as under the repo's v9."""
    shutil.copytree(CONFIG, root)
    for page, path in MAPPINGS.items():
        body = yaml.safe_load((root / path).read_text(encoding="utf-8"))
        body["entries"] += [_entry(page, role) for role in LACKING[page]]
        for entry in body["entries"]:
            if entry["entry_id"] == "screener.quarters.eps_basic":
                entry["tier"] = "EQUIVALENCE_UNPROVEN"
        (root / path).write_text(yaml.safe_dump(body), encoding="utf-8")


def _row_three(pilot: Pilot, stage: Stage, root: Path) -> None:
    """Onboarding provenance, the marked vendor sides and the eligibility fixture."""
    repository, pool = stage.repository, stage.pool
    discovery = repository.put_evidence_input(EvidenceInputKind.DISCOVERY, STOCK, "d" * 64)
    repository.put_settings_record(
        pilot.entity_id, SettingKey.REPORTING_FRAMEWORK, "IND_AS", discovery
    )
    with pool.connection() as conn:
        conn.execute(ONBOARDED, (STOCK, pilot.entity_id, discovery))
    rows = {row.key.digest(): row for row in load_results(compare(pilot), pool=pool)}
    revenue = rows[role_key(pilot, FactRole.REVENUE).digest()]
    for page, roles in LACKING.items():
        (side,) = [v for v in revenue.source_values if (v.source_id, v.surface) == page]
        (original,) = repository.get_interpretations([side.interpretation_id])
        for role in roles:
            key, eps = role_key(pilot, role), role is FactRole.BASIC_EPS
            value, half = MARKED[role], Fraction(1, 200) if eps else Fraction(5 * 10**6)
            base = value if eps else value * 10**7
            mark(
                stage,
                original,
                f"vendor-report {page[0]} {role.value}",
                key=key,
                canonical_id=key.canonical_id,
                period=key.period,
                value=base,
                interval=Interval(lower=Fraction(base) - half, upper=Fraction(base) + half),
                mapping_entry_id=_entry(page, role)["entry_id"],
            )
    run_id = compare(pilot)
    inputs, request, config = replay_inputs(run_id, pool=pool, config_root=root)
    interpretations = {item.interpretation_id: item for item in inputs.interpretations}
    policy = config.vendor_first_policy
    assert policy is not None
    keys = {role_key(pilot, role).digest() for role in REQUIRED_ROLES}
    agreeing = [
        row
        for row in load_results(run_id, pool=pool)
        if row.key.digest() in keys
        and vendor_outcome(row, interpretations, config.mapping_set, policy)[0]
        is VendorOutcome.VENDORS_AGREE
    ]
    assert len(agreeing) == len(REQUIRED_ROLES)
    classes = sorted(
        {row_class(r, interpretations, inputs, request, config, NON_FINANCIAL) for r in agreeing}
    )
    artifact = EligibilityArtifact(
        available_from=datetime(2000, 1, 1, tzinfo=UTC),
        code_version="test",
        classes=tuple(
            ClassEvidence(class_digest=d, agrees=4, differs=0, run_ids=(run_id,), eligible=True)
            for d in classes
        ),
    )
    folder = root / ELIGIBILITY_DIR
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{ELIGIBILITY}.yaml").write_text(yaml.safe_dump(artifact.model_dump(mode="json")))


def _entry(page: tuple[str, str], role: FactRole) -> dict[str, Any]:
    """A test-private mapping entry of the role on a vendor page (no native label matches)."""
    return {
        "entry_id": f"test.{page[0]}.{role.value}",
        "selector": {"statement_family": "PL", "labels": [f"TEST-MARKED {role.value}"]},
        "canonical_id": CANONICAL[role],
        "basis": ["CONSOLIDATED"],
        "period_kinds": ["QUARTER"],
        "period_rule": "COLUMN_DURATION",
        "tier": "EQUIVALENCE_UNPROVEN",
        "evidence_ref": "test-private (VENDOR-1 Task 9 row-3 fixture)",
    }


def compare(pilot: Pilot, eligibility: str | None = None) -> int:
    """``compare run`` of FY26_Q2 with the default vendor sides (under the config copy, pinning
    ``eligibility`` when named)."""
    root: Path = pilot.config_root  # type: ignore[attr-defined]
    command = ["compare", "run", "--entity", STOCK, "--basis", "consolidated", *PINS]
    command += ["--period-end", str(END), "--alignment-rules", "v2", "--config-root", str(root)]
    command += [] if eligibility is None else ["--eligibility", eligibility]
    return run_compare(_build_parser().parse_args(command)).run_id


def report(pilot: Pilot, run_id: int) -> int:
    """The FY26_Q2 ``run --retrospective --compare-run run_id`` through ``main``, its originals
    registered now on the first call; its exit code."""
    if not hasattr(pilot, "report_argv"):
        context, register, argv = pilot.prepared(QUARTER)
        assert main(register, intake_context=context) == 0
        pilot.report_argv = (context, argv)  # type: ignore[attr-defined]
    context, argv = pilot.report_argv  # type: ignore[attr-defined]
    flags = ["--compare-run", str(run_id), "--retrospective", str(APAR_MANIFEST)]
    return main([*argv, *flags], intake_context=context)


def witness_captures(pilot: Pilot, chosen: int, witness: int) -> list[Any]:
    """The capture ids and sources of an admission's two witnesses."""
    return pilot.query(WITNESSES, chosen, witness)
