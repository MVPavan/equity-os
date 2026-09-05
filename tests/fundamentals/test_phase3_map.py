"""Acceptance tests for the three-source line registry and spine precision (Phase 3, S4).

The seam under test is ``fundamentals.verify.three_source_map``: ONE declared
registry of vendor lines (Screener and Tijori) carrying what each row *means*,
its evidence tier and its XBRL concept candidates — plus ``alias_roles()``,
which must reproduce the pre-S4 alias table in ``reconcile/fact_view.py`` byte
for byte so no consumer of ``derived_concept_map`` changes behaviour. The rest
of the slice is precision on the spine: ``SourceValue`` gains the observation's
``decimals`` so gold records what each source stated a value to.

The registry module does not exist yet, so each test imports it at call time:
that keeps collection green and puts the failure inside the test that names the
behaviour. Every figure here is synthetic — a made-up symbol, made-up amounts,
and periods in 2027.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError
from test_upstox_scope_guards import _imported_modules

from fundamentals.contracts.observation import (
    AccountingFramework,
    Observation,
    PeriodType,
    Scope,
)
from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.contracts.role import FactRole
from fundamentals.ingest.screener_crosscheck import EvidenceTier
from fundamentals.reconcile.agreement import AgreementResult, classify_agreement
from fundamentals.reconcile.fact_view import derived_concept_map
from fundamentals.reconcile.gold_file import (
    DriftKind,
    build_gold_file,
    canonical_json,
    read_gold_file,
    regress,
)

_SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src" / "fundamentals"
REGISTRY_MODULE_NAME = "fundamentals.verify.three_source_map"
REGISTRY_MODULE_PATH = _SOURCE_ROOT / "verify" / "three_source_map.py"

# Packages the registry must not reach: it is a declaration the reconciler
# reads, never a participant in reconciliation, orchestration, or storage.
BARRED_PACKAGES = ("fundamentals.reconcile", "fundamentals.api", "fundamentals.store")

REVENUE_CONCEPT = "in-bse-fin:RevenueFromOperations"
PROFIT_BEFORE_TAX_CONCEPT = "in-bse-fin:ProfitBeforeTax"
PROFIT_FOR_PERIOD_CONCEPT = "in-bse-fin:ProfitLossForPeriod"
PROFIT_ATTRIBUTABLE_CONCEPT = "in-bse-fin:ProfitOrLossAttributableToOwnersOfParent"
BASIC_EPS_CONCEPT = "in-bse-fin:BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations"

# The pre-S4 literal, copied verbatim from ``reconcile/fact_view.py`` lines 29-34.
# This IS the pin: ``alias_roles()`` must reproduce it, keys and tuples in order.
PRE_S4_DERIVED_ROLE_ALIASES: dict[FactRole, tuple[str, ...]] = {
    FactRole.REVENUE: ("screener:Sales", "tijori:sales"),
    FactRole.PROFIT_BEFORE_TAX: ("tijori:pbt",),
    FactRole.PROFIT_FOR_PERIOD: ("screener:NetProfit", "tijori:net_profit"),
    FactRole.BASIC_EPS: ("screener:EPS", "tijori:eps"),
}

SYNTHETIC_SYMBOL = "SYNTH"
SYNTHETIC_QUARTER = "Q3FY28"
XBRL_SOURCE_ID = "nse-indas-xbrl-consolidated"
TIJORI_SOURCE_ID = "tijori"
XBRL_DECIMALS = -5
XBRL_SCALE = 100_000
TIJORI_DECIMALS = -7
TIJORI_SCALE = 10**7
_RETRIEVED_AT = datetime(2028, 2, 14, tzinfo=UTC)


def _registry_module() -> ModuleType:
    """Import the registry module at call time (it does not exist before S4).

    A plain import, not a skip: before the seam is built this raises
    ``ModuleNotFoundError`` inside the test that names the behaviour.
    """
    return import_module(REGISTRY_MODULE_NAME)


class _SyntheticRole(BaseModel):
    """A configured role/concept pair, matching the ``RoleConceptView`` shape."""

    model_config = ConfigDict(frozen=True)

    role: FactRole
    concept_qname: str


def _synthetic_roles() -> list[_SyntheticRole]:
    """The four roles the derived aliases bind to, with synthetic canonical concepts."""
    return [
        _SyntheticRole(role=FactRole.REVENUE, concept_qname=REVENUE_CONCEPT),
        _SyntheticRole(role=FactRole.PROFIT_BEFORE_TAX, concept_qname=PROFIT_BEFORE_TAX_CONCEPT),
        _SyntheticRole(role=FactRole.PROFIT_FOR_PERIOD, concept_qname=PROFIT_FOR_PERIOD_CONCEPT),
        _SyntheticRole(role=FactRole.BASIC_EPS, concept_qname=BASIC_EPS_CONCEPT),
    ]


def _entry_by_id(module: ModuleType, mapping_id: str) -> Any:
    """Fetch one seeded registry entry by ``mapping_id``, failing loudly if absent."""
    found = [entry for entry in module.REGISTRY if entry.mapping_id == mapping_id]
    assert found, f"registry has no entry {mapping_id!r}"
    return found[0]


def _valid_entry_fields(module: ModuleType) -> dict[str, Any]:
    """Field values for a well-formed mapping, used as the base of negative cases."""
    return {
        "mapping_id": "synthetic.quarters.sales",
        "source": module.MappedSource.SCREENER,
        "section": module.SCREENER_QUARTERS,
        "row_selector": "Sales",
        "alias_qname": "screener:Sales",
        "role": FactRole.REVENUE,
        "means": "Synthetic quarterly revenue row used only by this test.",
        "tier": EvidenceTier.EQUIVALENCE_UNPROVEN,
        "concept_qnames": (REVENUE_CONCEPT,),
    }


def _xbrl_observation() -> Observation:
    """A synthetic XBRL-like observation stated in lakh to five-digit precision."""
    return Observation(
        concept_qname=REVENUE_CONCEPT,
        raw_value="123400000",
        normalized_value=Decimal("1234"),
        normalized_unit="INR lakh",
        context_ref="SyntheticQuarterContext",
        entity_scheme="nse-symbol",
        entity_id=SYNTHETIC_SYMBOL,
        scope=Scope.CONSOLIDATED,
        accounting_basis=AccountingFramework.IND_AS,
        period_type=PeriodType.DURATION,
        period_start=date(2027, 10, 1),
        period_end=date(2027, 12, 31),
        currency="INR",
        scale=XBRL_SCALE,
        decimals=XBRL_DECIMALS,
        provenance=Provenance(
            source_id=XBRL_SOURCE_ID,
            file_sha256="0" * 64,
            anchor_type=SourceAnchorType.XBRL_CONTEXT,
            context_ref="SyntheticQuarterContext",
            retrieved_at=_RETRIEVED_AT,
        ),
    )


def _tijori_observation() -> Observation:
    """A synthetic Tijori-like observation stated in crore to seven-digit precision."""
    return Observation(
        concept_qname=PROFIT_BEFORE_TAX_CONCEPT,
        raw_value="4560000000",
        normalized_value=Decimal("456"),
        normalized_unit="INR crore",
        entity_scheme="nse-symbol",
        entity_id=SYNTHETIC_SYMBOL,
        scope=Scope.CONSOLIDATED,
        accounting_basis=AccountingFramework.UNKNOWN,
        period_type=PeriodType.DURATION,
        period_start=date(2027, 10, 1),
        period_end=date(2027, 12, 31),
        currency="INR",
        scale=TIJORI_SCALE,
        decimals=TIJORI_DECIMALS,
        provenance=Provenance(
            source_id=TIJORI_SOURCE_ID,
            file_sha256="b" * 64,
            anchor_type=SourceAnchorType.JSON_ISLAND,
            island_id="synthetic-island",
            table_key="qt_c",
            row_label="Profit Before Tax",
            column_label="Q3FY28",
            retrieved_at=_RETRIEVED_AT,
        ),
    )


def _agreement_results() -> list[AgreementResult]:
    """Classify each synthetic observation as its own comparison column.

    They state different scales, so they are different comparison keys: one call
    would make one an *incompatible* source, dropped from the result.
    """
    return [
        classify_agreement([_xbrl_observation()]),
        classify_agreement([_tijori_observation()]),
    ]


def test_unmapped_row_refuses() -> None:
    """A vendor row nobody declared must raise, never be guessed into a mapping.

    Guessing is how a false comparison is born: an undeclared row bound to the
    nearest-looking concept reports a mismatch on a line no one ever verified.
    """
    module = _registry_module()

    with pytest.raises(module.UnmappedRowError, match="refusing to guess"):
        module.mapping_for(module.MappedSource.SCREENER, module.SCREENER_QUARTERS, "Other Income")


def test_tier1_entry_cannot_drop_its_exclusion() -> None:
    """A demonstrated-equivalence line without its named exclusion must not construct.

    Lane B's tier 1 held on most companies and failed on a named part of the
    population, so the tier is only honest while that exclusion travels with it.
    Empty ``exclusions`` claims an identity no measurement supports.
    """
    module = _registry_module()
    tier_one = {
        **_valid_entry_fields(module),
        "tier": EvidenceTier.EQUIVALENCE_DEMONSTRATED,
    }
    exclusion = ("companies with material exceptional items",)

    with pytest.raises(ValidationError):
        module.SourceLineMapping(**tier_one)

    accepted = module.SourceLineMapping(**{**tier_one, "exclusions": exclusion})
    assert accepted.exclusions == exclusion


def test_alias_roles_matches_the_pre_s4_table() -> None:
    """Moving the alias table into the registry must not change one byte of it.

    ``derived_concept_map`` feeds the comparatives, goal runner and report
    builder, and alias order decides which derived value is canonicalised first,
    so a reordered tuple is a behaviour change disguised as a refactor. The
    literal above is the pre-S4 table verbatim; equality plus item order is the pin.
    """
    module = _registry_module()

    produced = module.alias_roles()

    assert produced == PRE_S4_DERIVED_ROLE_ALIASES
    assert list(produced.items()) == list(PRE_S4_DERIVED_ROLE_ALIASES.items())

    assert derived_concept_map(_synthetic_roles()) == {
        "screener:Sales": REVENUE_CONCEPT,
        "tijori:sales": REVENUE_CONCEPT,
        "tijori:pbt": PROFIT_BEFORE_TAX_CONCEPT,
        "screener:NetProfit": PROFIT_FOR_PERIOD_CONCEPT,
        "tijori:net_profit": PROFIT_FOR_PERIOD_CONCEPT,
        "screener:EPS": BASIC_EPS_CONCEPT,
        "tijori:eps": BASIC_EPS_CONCEPT,
    }


def test_net_profit_is_section_qualified() -> None:
    """The same label on two Screener sections is two different facts.

    "Net Profit" on the quarters table is quarterly; the same label on the
    profit-loss table is annual. A registry keyed on the label alone would let an
    annual number satisfy a quarterly comparison — fact-identity collapse.
    """
    module = _registry_module()

    quarterly = module.mapping_for(
        module.MappedSource.SCREENER, module.SCREENER_QUARTERS, "Net Profit"
    )
    annual = module.mapping_for(
        module.MappedSource.SCREENER, module.SCREENER_PROFIT_LOSS, "Net Profit"
    )

    assert quarterly.mapping_id != annual.mapping_id
    assert quarterly.alias_qname == "screener:NetProfit"
    assert annual.alias_qname is None
    assert annual.role is None
    assert "annual" in annual.means.lower()


def test_net_profit_carries_two_candidates_with_one_tier_each() -> None:
    """Both net-profit rows list the same two candidates, each holding its own tier.

    Which concept a vendor's "Net Profit" is stays undecided until the S6 replay,
    so both candidates are named in preference order. The tier is per entry: were
    it shared, grading one line up would silently promote the other.
    """
    module = _registry_module()
    expected_candidates = (PROFIT_FOR_PERIOD_CONCEPT, PROFIT_ATTRIBUTABLE_CONCEPT)

    screener_entry = _entry_by_id(module, "screener.quarters.net_profit")
    tijori_entry = _entry_by_id(module, "tijori.qt_c.net_profit")

    assert screener_entry.concept_qnames == expected_candidates
    assert tijori_entry.concept_qnames == expected_candidates
    assert screener_entry.tier is EvidenceTier.EQUIVALENCE_UNPROVEN
    assert tijori_entry.tier is EvidenceTier.EQUIVALENCE_UNPROVEN

    regraded = screener_entry.model_copy(update={"tier": EvidenceTier.RELATED_NOT_EQUIVALENT})
    assert regraded.tier is EvidenceTier.RELATED_NOT_EQUIVALENT
    assert tijori_entry.tier is EvidenceTier.EQUIVALENCE_UNPROVEN
    assert _entry_by_id(module, "screener.quarters.net_profit").tier is (
        EvidenceTier.EQUIVALENCE_UNPROVEN
    )


@pytest.mark.parametrize(
    "duplicate_kind", ["mapping_id", "selector_triple", "alias_qname"], ids=str
)
def test_registry_refuses_duplicates(duplicate_kind: str) -> None:
    """Two entries claiming the same identity make lookup order decide the answer.

    A duplicate id, selector triple or alias means a lookup returns whichever
    entry happens to be first — a mapping chosen by list position, not by
    declaration. Building the registry is the cheapest moment to catch it.
    """
    module = _registry_module()
    first = module.SourceLineMapping(**_valid_entry_fields(module))
    second = module.SourceLineMapping(
        **{
            **_valid_entry_fields(module),
            "mapping_id": "synthetic.qt_c.net_sales",
            "source": module.MappedSource.TIJORI,
            "section": module.TIJORI_QT_C,
            "row_selector": "Net Sales",
            "alias_qname": "tijori:sales",
        }
    )
    assert module.build_registry([first, second]) == (first, second)

    updates: dict[str, dict[str, Any]] = {
        "mapping_id": {"mapping_id": first.mapping_id},
        "selector_triple": {
            "source": first.source,
            "section": first.section,
            "row_selector": first.row_selector,
        },
        "alias_qname": {"alias_qname": first.alias_qname},
    }
    colliding = second.model_copy(update=updates[duplicate_kind])

    with pytest.raises(ValueError):
        module.build_registry([first, colliding])


def test_alias_only_entry_binds_role_but_never_matches_a_row() -> None:
    """``tijori:eps`` keeps its role binding while admitting no row is parsed.

    No Tijori EPS row is parsed today; the alias survives only so the role table
    is unchanged, and the registry says so instead of implying a vendor row.
    A selector-less entry is reachable by alias and unreachable by row lookup.
    """
    module = _registry_module()

    alias_only = module.mappings_for_alias("tijori:eps")
    assert alias_only.row_selector is None
    assert alias_only.role is FactRole.BASIC_EPS
    assert alias_only.source is module.MappedSource.TIJORI

    tijori_selectors = [
        entry.row_selector
        for entry in module.REGISTRY
        if entry.source is module.MappedSource.TIJORI and entry.row_selector is not None
    ]
    resolved_aliases = {
        module.mapping_for(module.MappedSource.TIJORI, module.TIJORI_QT_C, selector).alias_qname
        for selector in tijori_selectors
    }
    assert "tijori:eps" not in resolved_aliases

    with pytest.raises(module.UnmappedRowError):
        module.mapping_for(module.MappedSource.TIJORI, module.TIJORI_QT_C, "EPS in Rs")


def test_source_values_carry_observation_decimals() -> None:
    """Each retained source value must keep the precision its source stated.

    The reconciliation tolerance is derived from ``decimals``, so a reader of a
    gold file without it cannot tell a rounded crore figure from an exact one,
    nor re-derive the tolerance the original match was judged under.
    """
    results = _agreement_results()

    decimals_by_source = {
        value.source_id: value.decimals for result in results for value in result.source_values
    }
    assert decimals_by_source == {
        XBRL_SOURCE_ID: XBRL_DECIMALS,
        TIJORI_SOURCE_ID: TIJORI_DECIMALS,
    }


def test_old_gold_loads_with_decimals_none_and_new_gold_round_trips(tmp_path: Path) -> None:
    """Adding precision must not invalidate the gold files already on disk.

    ``decimals`` is optional and the schema version does not bump, so a pre-S4
    file (no such key) must still load — reading ``None`` — and must not register
    as drift on the next run. The pre-S4 file here is produced deterministically:
    dump a fresh gold file and delete the key from every source value.
    """
    results = _agreement_results()
    fresh_gold = build_gold_file(SYNTHETIC_SYMBOL, SYNTHETIC_QUARTER, results)
    fresh_json = canonical_json(fresh_gold)

    assert '"decimals":-7' in fresh_json

    fresh_path = tmp_path / "fresh-gold.json"
    fresh_path.write_text(fresh_json, encoding="utf-8")
    assert read_gold_file(fresh_path) == fresh_gold

    old_payload = json.loads(fresh_json)
    for fact in old_payload["facts"]:
        for source_value in fact["source_values"]:
            del source_value["decimals"]
    old_path = tmp_path / "old-gold.json"
    old_path.write_text(
        json.dumps(old_payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8"
    )

    old_gold = read_gold_file(old_path)
    assert old_gold.facts
    assert all(value.decimals is None for fact in old_gold.facts for value in fact.source_values)

    report = regress(old_gold, results)
    assert [drift for drift in report.drifts if drift.kind is DriftKind.VALUE_DRIFT] == []
    assert report.has_drift is False


def test_registry_imports_stay_in_lane() -> None:
    """The registry is a declaration the reconciler reads, not a reconciler itself.

    ``reconcile.fact_view`` imports this module, so an import back would close a
    cycle; reaching ``api`` or ``store`` would make a name-mapping table a second
    place where reconciliation decisions live.
    """
    assert REGISTRY_MODULE_PATH.exists(), f"{REGISTRY_MODULE_PATH} does not exist yet"

    imported = _imported_modules(REGISTRY_MODULE_PATH)
    for barred in BARRED_PACKAGES:
        assert not any(name.startswith(barred) for name in imported), (
            f"three_source_map.py imports {barred}"
        )
