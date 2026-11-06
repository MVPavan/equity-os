"""Vendor-only applicability from table structure, never values (VENDOR-1 spec §6.3).

LAURUSLABS Q3 FY25 consolidated from its retained Tijori capture plus synthetic rows (value 123,
never a vendor value) under a test mapping set: a balance-sheet instant at the period end makes
the conditional balance sheet present in a quarter, and an excise-duty line with an unreadable
unit is still a disclosure, so its cell applies and reads ``INVALID`` rather than
``NOT_APPLICABLE``. The same line in a column of unknown period cannot be placed and refuses.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml
from test_compare_vendor_runs import CONFIG, CRORE, LAURUS, Q3, Q3_END, Issuer, _value
from test_evidence_vendor import tijori
from test_vendor_only_run import OPTIONS, RUN, TIJORI, _refused, _results
from test_vendor_only_run import laurus as laurus  # the fixture

from equity_os.contracts.measurement.canonical import ApplicabilityStatus
from equity_os.contracts.measurement.evidence import Occurrence
from equity_os.contracts.measurement.measurement_key import PeriodInterval
from equity_os.contracts.verification.comparison import SourceState
from equity_os.extraction.surfaces.vendor_ingest import VendorExtraction, json_occurrence
from equity_os.extraction.vendors.tijori import vendor_tijori
from equity_os.interface.entry.cli import main
from equity_os.verification.comparison.run import RunExitStatus
from equity_os.verification.comparison.run_config import ConfigVersions, load_run_config

pytestmark = [pytest.mark.pg, pytest.mark.retained]

ASSETS, EXCISE = "Synthetic Assets", "Synthetic Excise"


def _config(tmp_path: Path) -> Path:
    """A config root whose mapping set v99 maps the two synthetic Tijori labels."""
    root = tmp_path / "config-structure"
    shutil.copytree(CONFIG, root)
    mappings = root / "normalisation/mappings"
    index = yaml.safe_load((mappings / "v2.yaml").read_text(encoding="utf-8"))
    (mappings / "v99.yaml").write_text(yaml.safe_dump(index | {"version": "v99"}), "utf-8")
    entries = mappings / "tijori/v1/financials.yaml"
    data = yaml.safe_load(entries.read_text(encoding="utf-8"))
    base = data["entries"][0]
    data["entries"] += [
        base
        | {
            "entry_id": "tijori.qt_c.synthetic_total_assets",
            "canonical_id": "total_assets",
            "selector": base["selector"]
            | {"statement_family": "BALANCE_SHEET", "labels": [ASSETS]},
            "period_kinds": ["INSTANT"],
            "period_rule": "COLUMN_INSTANT",
        },
        base
        | {
            "entry_id": "tijori.qt_c.synthetic_excise_duty",
            "canonical_id": "excise_duty",
            "selector": base["selector"] | {"labels": [EXCISE]},
        },
    ]
    entries.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return root


def _synthetic(
    template: Occurrence, label: str, family: str, period: PeriodInterval | None, unit: str
) -> Occurrence:
    """A Tijori qt_c cell under another label, family, period and unit, valued 123."""
    return json_occurrence(
        template.capture,
        extractor_version=template.extractor_version,
        label=label,
        lexeme="123",
        value=Decimal(123),
        raw_unit=unit,
        raw_scale=template.raw_scale,
        declared_precision=0,
        period=period,
        native_context=dict(template.native_context)
        | {"label": label, "statement_family": family, "island_value": "123"},
        anchor=dict(template.anchor) | {"row_key": label},
        disclosure=template.disclosure,
    )


def _ingest(laurus: Issuer, root: Path, rows: Callable[[Occurrence], list[Occurrence]]) -> None:
    """Ingest the retained Tijori capture under v99 with ``rows`` added beside its Q3 sales."""
    laurus.config = load_run_config(root, ConfigVersions(dictionary="v2", mapping_set="v99"))
    adapter = tijori(LAURUS.tijori[2], LAURUS.symbol)

    def extract(body: bytes, **kwargs: Any) -> VendorExtraction:
        found: VendorExtraction = adapter(body, **kwargs)
        (sales,) = [
            item
            for item in found.occurrences
            if item.native_context["section"] == "qt_c"
            and item.native_context["label"] == "Net Sales"
            and item.period == Q3
        ]
        return found.model_copy(update={"occurrences": (*found.occurrences, *rows(sales))})

    laurus.vendor(LAURUS.tijori, extract, vendor_tijori.EXTRACTOR_VERSION, Q3_END)


def test_present_instant_and_invalid_disclosure_apply(
    laurus: Issuer, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A balance-sheet instant at the period end makes every balance-sheet row applicable in a
    quarter; an invalid excise-duty cell is a disclosure, applicable and ``INVALID``."""
    root = _config(tmp_path)
    _ingest(
        laurus,
        root,
        lambda sales: [
            _synthetic(sales, ASSETS, "BALANCE_SHEET", PeriodInterval.at(Q3_END), sales.raw_unit),
            _synthetic(sales, EXCISE, "PL", Q3, "SYNTHETIC_UNIT"),
        ],
    )
    args = ("--config-root", str(root), "--mapping-set", "v99")
    assert main([*RUN, *OPTIONS, *args]) == RunExitStatus.SUCCESS
    (run_id,) = [
        int(line.split("\t")[1])
        for line in capsys.readouterr().out.splitlines()
        if line.startswith("run\t")
    ]
    rows = {
        (row.key.canonical_id, row.key.period): row
        for row in _results(laurus, run_id)
        if row.value_identity.value == "REPORTED"
    }
    instant = PeriodInterval.at(Q3_END)
    assets, ppe, excise = (
        rows["total_assets", instant],
        rows["ppe", instant],
        rows["excise_duty", Q3],
    )
    for row in (assets, ppe, excise):
        assert row.applicability is ApplicabilityStatus.APPLICABLE
    assert _value(assets, TIJORI).state is SourceState.VALUE
    assert _value(assets, TIJORI).value == 123 * CRORE
    assert _value(excise, TIJORI).state is SourceState.INVALID


def test_row_of_unknown_period_refuses(
    laurus: Issuer, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A mapped excise-duty cell with no column period cannot be placed: its presence cannot be
    assessed, so the group refuses rather than calling the row inapplicable."""
    root = _config(tmp_path)
    _ingest(laurus, root, lambda sales: [_synthetic(sales, EXCISE, "PL", None, sales.raw_unit)])
    reason = "vendor rows ['excise_duty'] cannot be placed"
    _refused(laurus, capsys, reason, "--config-root", str(root), "--mapping-set", "v99")
