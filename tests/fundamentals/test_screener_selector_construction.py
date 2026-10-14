"""Screener Borrowings + Other Liabilities -> ``liabilities_incl_nci`` on the retained THERMAX page.

Oracle, hand-read from the retained consolidated page's balance-sheet table, column Mar 2025
(Rs. crore, printed as integers): Borrowings 1,718; Other Liabilities 4,728; Total Liabilities
11,382 (never an operand). 1,718 + 4,728 = 6,446 crore; each cell is exact to +/-0.5 crore,
so the sum is exact to +/-1 crore. Every expected value below comes from those cells.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

import pytest
import yaml
from pg_evidence_schema_support import _insert
from vendor_retained_support import (
    REPO_ROOT,
    draft_config,
    identifiers,
    retained_page,
    stage_registered,
)

from fundamentals.canon.interval import load_rounding_policy
from fundamentals.contracts.canonical import Basis, StatementFamily, ValueIdentity, ValueKind
from fundamentals.contracts.comparison import CalculationState, SourceState
from fundamentals.contracts.evidence import (
    InterpretationOrigin,
    InterpretationReason,
    InterpretationStatus,
    Occurrence,
)
from fundamentals.contracts.evidence_tier import EvidenceTier
from fundamentals.contracts.interval import Interval
from fundamentals.contracts.measurement_key import PeriodInterval
from fundamentals.evidence.capture_interpretation import CaptureScope, interpret_generation
from fundamentals.evidence.mapping import (
    MappingLoadError,
    NormalisationPolicy,
    UnitRule,
    load_mapping_set,
)
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.evidence.repository_calc import CONSTRUCTION_TRACE, trace_from_json
from fundamentals.evidence.vendor_screener import ScreenerIssuerBinding, extract_screener_page
from fundamentals.ingest.screener_financials_models import Section
from fundamentals.ingest.screener_session_models import BasisTopology
from fundamentals.store.snapshot_store import SnapshotStore

pytestmark = pytest.mark.pg

THERMAX_SHA256 = "6894f0979643755a618a6e8f572dc63ee3efb61abb6495ddf4766d5ec678f0ad"
TARGET = PeriodInterval.at(date(2025, 3, 31))
CRORE = 10**7
BORROWINGS = Fraction(1_718 * CRORE)
OTHER_LIABILITIES = Fraction(4_728 * CRORE)
ORACLE = Fraction(6_446 * CRORE)
HALF_CRORE = Fraction(CRORE, 2)
RULE_ID = "screener.balance-sheet.liabilities_incl_nci"
QUALIFIED = "reviewed-selector-scope"

Rows = tuple[Occurrence, ...]
Result = tuple[Rows, NormalisationPolicy]
Edit = Callable[[Rows, dict[str, Any], NormalisationPolicy], Result]


def _at_target(row: Occurrence, label: str) -> bool:
    return row.native_field == label and row.period == TARGET


def _drop(label: str) -> Edit:
    def edit(rows: Rows, rule: dict[str, Any], policy: NormalisationPolicy) -> Result:
        return tuple(row for row in rows if not _at_target(row, label)), policy

    return edit


def _set(label: str, **fields: object) -> Edit:
    def edit(rows: Rows, rule: dict[str, Any], policy: NormalisationPolicy) -> Result:
        return tuple(
            row.model_copy(update=fields) if _at_target(row, label) else row for row in rows
        ), policy

    return edit


def _both(*edits: Edit) -> Edit:
    def edit(rows: Rows, rule: dict[str, Any], policy: NormalisationPolicy) -> Result:
        for each in edits:
            rows, policy = each(rows, rule, policy)
        return rows, policy

    return edit


def _duplicate_borrowings(rows: Rows, rule: dict[str, Any], policy: NormalisationPolicy) -> Result:
    (borrowings,) = [row for row in rows if _at_target(row, "Borrowings")]
    twin = borrowings.model_copy(update={"anchor_key": f"{borrowings.anchor_key}:twin"})
    return (*rows, twin), policy


def _usd_unit(rows: Rows, rule: dict[str, Any], policy: NormalisationPolicy) -> Result:
    usd = UnitRule(
        raw_unit="USD", value_kind=ValueKind.CURRENCY_AMOUNT, currency="USD", evidence_ref="test"
    )
    return rows, policy.model_copy(update={"units": {**policy.units, "USD": usd}})


def _rule(**fields: object) -> Edit:
    def edit(rows: Rows, rule: dict[str, Any], policy: NormalisationPolicy) -> Result:
        rule.update(fields)
        return rows, policy

    return edit


def _no_edit(rows: Rows, rule: dict[str, Any], policy: NormalisationPolicy) -> Result:
    return rows, policy


QUALIFICATION = {
    "scope_id": QUALIFIED,
    "schema_identities": ["screener-financials-html-v1"],
    "surfaces": ["SCREENER_FINANCIALS"],
    "bases": ["CONSOLIDATED"],
    "period_kinds": ["INSTANT"],
    "fixture_evidence": [
        {
            "capture_id": f"capture-{index}",
            "capture_sha256": f"{index:x}" * 64,
            "entity_id": index,
            "discriminating": index == 1,
        }
        for index in range(1, 6)
    ],
    "sample_rule": "five independent companies including one discriminating case",
}
COMPUTED = {
    "status": InterpretationStatus.MAPPED,
    "value": ORACLE,
    "interval": Interval(lower=ORACLE - 2 * HALF_CRORE, upper=ORACLE + 2 * HALF_CRORE),
    "operands": ["Borrowings", "Other Liabilities"],
    "trace": CalculationState.COMPUTED,
    "tier": EvidenceTier.EQUIVALENCE_UNPROVEN,
}
INVALID = {"status": InterpretationStatus.INVALID, "value": None, "interval": None}

CASES = [
    pytest.param(_no_edit, False, COMPUTED, id="oracle-exact-value-and-interval"),
    pytest.param(
        _drop("Other Liabilities"),
        False,
        {
            "status": InterpretationStatus.MAPPED,
            "value": None,
            "interval": None,
            "operands": ["Borrowings"],
            "trace": CalculationState.OPERAND_MISSING,
        },
        id="missing-operand-is-missing-never-zero",
    ),
    pytest.param(
        _both(_drop("Other Liabilities"), _set("Borrowings", raw_value_text="1,7l8")),
        False,
        {
            **INVALID,
            "reason": InterpretationReason.UNREADABLE_CELL,
            "operands": ["Borrowings"],
            "trace": CalculationState.OPERAND_INVALID,
        },
        id="invalid-beats-missing",
    ),
    pytest.param(
        _duplicate_borrowings,
        False,
        {
            **INVALID,
            "reason": InterpretationReason.INTERPRETATION_AMBIGUOUS,
            "operands": ["Borrowings", "Borrowings", "Other Liabilities"],
            "trace": CalculationState.OPERAND_INVALID,
        },
        id="duplicate-operand-is-ambiguous",
    ),
    pytest.param(_no_edit, True, ValueError, id="other-capture-operand-refused"),
    pytest.param(
        _set("Borrowings", raw_unit="PERCENT"),
        False,
        {
            **INVALID,
            "reason": InterpretationReason.UNIT_MISMATCH,
            "operands": ["Borrowings", "Other Liabilities"],
            "trace": CalculationState.OPERAND_INVALID,
        },
        id="unit-outside-target-value-kind",
    ),
    pytest.param(
        _both(_usd_unit, _set("Borrowings", raw_unit="USD")),
        False,
        {
            **INVALID,
            "reason": InterpretationReason.UNIT_MISMATCH,
            "operands": ["Borrowings", "Other Liabilities"],
            "trace": CalculationState.OPERAND_INVALID,
        },
        id="operand-currencies-disagree",
    ),
    pytest.param(_rule(bases=["STANDALONE"]), False, None, id="basis-outside-rule-scope"),
    pytest.param(
        _rule(tier="RELATED_NOT_EQUIVALENT"), False, MappingLoadError, id="related-tier-refused"
    ),
    pytest.param(
        _rule(tier="EQUIVALENCE_DEMONSTRATED"),
        False,
        MappingLoadError,
        id="unqualified-demonstrated-tier-refused",
    ),
    pytest.param(
        _rule(tier="EQUIVALENCE_DEMONSTRATED", qualification=QUALIFICATION),
        False,
        {
            **COMPUTED,
            "tier": EvidenceTier.EQUIVALENCE_DEMONSTRATED,
            "qualification_ref": QUALIFIED,
        },
        id="qualified-rule-is-demonstrated",
    ),
]


@pytest.mark.parametrize(("edit", "other_capture", "expected"), CASES)
def test_thermax_selector_construction(
    pg_db: Any, tmp_path: Path, edit: Edit, other_capture: bool, expected: Any
) -> None:
    """One rule, one capture: computed from the printed cells, traced, and fail-closed."""
    dictionary, _, policy = draft_config(tmp_path)
    constructions = tmp_path / "mappings" / "constructions.yaml"
    config = yaml.safe_load(constructions.read_text())
    (rule,) = config["constructions"]
    request, _, body = retained_page("THERMAX")
    assert hashlib.sha256(body).hexdigest() == THERMAX_SHA256

    with pg_db.runtime_pool() as pool:
        repository = EvidenceRepository(pool)
        request = request.model_copy(
            update={"entity_id": _entity(pg_db), "statement_family": StatementFamily.BALANCE_SHEET}
        )
        snapshots = tmp_path / "snapshots"
        snapshots.mkdir(mode=0o700)
        capture = stage_registered(request, repository, SnapshotStore(snapshots))
        extracted = extract_screener_page(
            body,
            basis=request.basis,
            capture=capture,
            binding=_binding(),
            section=Section.BALANCE_SHEET,
            extractor_version="screener-v1",
        ).occurrences
        rows, policy = edit(tuple(extracted), rule, policy)
        constructions.write_text(yaml.safe_dump(config))
        if expected is MappingLoadError:
            with pytest.raises(MappingLoadError):
                load_mapping_set(tmp_path / "mappings", "screener-draft", dictionary=dictionary)
            return
        mappings = load_mapping_set(tmp_path / "mappings", "screener-draft", dictionary=dictionary)
        stored_rows = repository.put_occurrences(rows)
        if other_capture:
            foreign = capture.model_copy(
                update={"capture_ref_id": cast(int, capture.capture_ref_id) + 1}
            )
            stored_rows = tuple(
                row.model_copy(update={"capture": foreign})
                if _at_target(row, "Other Liabilities")
                else row
                for row in stored_rows
            )
        recorded_at = repository.store_clock()

        def generate() -> Any:
            return interpret_generation(
                stored_rows,
                scope=CaptureScope(
                    capture=capture,
                    entity_id=request.entity_id,
                    basis=Basis.CONSOLIDATED,
                    framework=request.framework,
                    mapping_set=mappings,
                    policy=policy,
                    dictionary=dictionary,
                    fiscal_year_end_month=3,
                    rounding_policy=load_rounding_policy(
                        REPO_ROOT / "config/rounding_policy/v1.yaml"
                    ),
                ),
                prior=(),
                prior_anchor_keys={},
                reserve_ids=repository.reserve_interpretation_ids,
                recorded_at=recorded_at,
            )

        if expected is ValueError:
            with pytest.raises(ValueError, match="more than one capture"):
                generate()
            return
        generated = generate()
        repository.put_interpretations(generated)
        stored = repository.get_interpretations(
            [cast(int, row.interpretation_id) for row in generated]
        )
        found = [
            row
            for row in stored
            if row.origin is InterpretationOrigin.CONSTRUCTED and row.period == TARGET
        ]
        if expected is None:
            assert found == []
            return
        (constructed,) = found
        labels = {
            row.interpretation_id: next(
                occurrence.native_field
                for occurrence in stored_rows
                if occurrence.occurrence_id == row.occurrence_id
            )
            for row in stored
            if row.origin is InterpretationOrigin.DIRECT
        }
        assert constructed.recorded_at == recorded_at
        assert constructed.status is expected["status"]
        assert constructed.reason is expected.get("reason")
        assert constructed.value == expected["value"]
        assert constructed.interval == expected["interval"]
        assert constructed.tier is expected.get("tier", EvidenceTier.EQUIVALENCE_UNPROVEN)
        assert constructed.qualification_ref == expected.get("qualification_ref")
        if "operands" in expected:
            assert (
                sorted(labels[item] for item in constructed.operand_interpretation_ids)
                == expected["operands"]
            )
        _check_trace(repository, constructed, expected.get("trace"))


def _check_trace(repository: EvidenceRepository, constructed: Any, state: Any) -> None:
    """The stored trace replays the construction: operands, values, bounds, tier and state."""
    links = repository.get_construction_traces([constructed.interpretation_id])
    (stored,) = repository.get_calculation_traces([links[constructed.interpretation_id]])
    trace = stored.trace
    assert trace == trace_from_json(constructed.transform_trace[CONSTRUCTION_TRACE])
    assert trace.state is state
    assert trace.value_identity is ValueIdentity.DERIVED
    assert (trace.formula_id, trace.formula_version) == (RULE_ID, "screener-draft")
    assert trace.rounding_policy_id == "v1"
    assert trace.key_digest == constructed.key.digest()
    assert trace.effective_tier is constructed.tier
    assert [operand.name for operand in trace.operands] == ["borrowings", "other_liabilities"]
    assert all(operand.scoped_tier is constructed.tier for operand in trace.operands)
    if state is not CalculationState.COMPUTED:
        assert trace.value is None and trace.exact_value is None
        return
    assert [operand.interpretation_id for operand in trace.operands] == list(
        constructed.operand_interpretation_ids
    )
    assert [operand.source_state for operand in trace.operands] == [SourceState.VALUE] * 2
    assert [operand.exact_value for operand in trace.operands] == [BORROWINGS, OTHER_LIABILITIES]
    assert [operand.exact_interval for operand in trace.operands] == [
        Interval(lower=BORROWINGS - HALF_CRORE, upper=BORROWINGS + HALF_CRORE),
        Interval(lower=OTHER_LIABILITIES - HALF_CRORE, upper=OTHER_LIABILITIES + HALF_CRORE),
    ]
    assert sum(operand.exact_value or 0 for operand in trace.operands) == trace.exact_value
    assert trace.exact_value == ORACLE and trace.value == Decimal(6_446 * CRORE)
    assert (trace.lower, trace.upper) == (Decimal(6_445 * CRORE), Decimal(6_447 * CRORE))


def _binding() -> ScreenerIssuerBinding:
    identity = identifiers("THERMAX")
    return ScreenerIssuerBinding(
        symbol="THERMAX",
        company_id=identity["screener_company_id"],
        bse_code=identity["bse_scrip"],
        topology=BasisTopology(
            consolidated_warehouse_id=identity["screener_warehouse_id_consolidated"],
            standalone_warehouse_id=identity["screener_warehouse_id_standalone"],
        ),
        identity_evidence_ref="config/watchlist.yaml",
    )


def _entity(pg_db: Any) -> int:
    with pg_db.migrator_connection() as connection:
        evidence = _insert(
            connection,
            "evidence_inputs",
            {
                "kind": "ISSUER_IDENTITY",
                "label": "retained Screener selector construction test scope: THERMAX",
                "content_sha256": "a" * 64,
            },
        )
        return _insert(
            connection,
            "reporting_entities",
            {
                "entity_key": "SCREENER-SELECTOR-THERMAX",
                "market": "IN",
                "display_name": "THERMAX retained test entity",
                "evidence_input_id": evidence,
            },
        )
