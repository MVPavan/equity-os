"""D8 shareholding comparison: Task 3 config loading (stage D8.2/D8.3).

The D8 configuration is fixed before any ingest: dictionary v3 and mapping set v7 must load
through the run loader, every vendor percentage must carry its owner-sanctioned assumption,
and a basket that double counts a member with its own descendant must be refused.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from fundamentals.canon.dictionary import (
    FORMULA_SET_FILE,
    DictionaryDefect,
    DictionaryLoadError,
    load_dictionary,
)
from fundamentals.compare.run_config import LoadedConfig, load_run_config
from fundamentals.contracts.canonical import ValueKind
from fundamentals.contracts.config_versions import ConfigVersions
from fundamentals.evidence.mapping import matches_dimensions
from fundamentals.evidence.mapping_models import MappingAssumption, selector_matches

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
