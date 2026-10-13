"""D1a.2 acceptance: applicability from context alone, and scoped tiers per measurement.

Applicability decides ``NOT_APPLICABLE`` versus a later ``NO_SOURCE``: a Q1 or Q3
package without a balance sheet must never report balance-sheet rows as missing,
a standalone-only issuer must never have consolidated rows at all, and segment
rows are owed only on a basis where the entity's segments are evidenced.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from fundamentals.canon.applicability import (
    REPORTING_KINDS,
    ROW_BASIS_RULE_ID,
    STANDALONE_ONLY_RULE_ID,
    ApplicabilityContext,
    decide_applicability,
)
from fundamentals.canon.dictionary import CanonicalDictionary, DictionaryRow, load_dictionary
from fundamentals.contracts.basis_status import BasisStatus
from fundamentals.contracts.canonical import (
    ApplicabilityStatus,
    Basis,
    DocumentType,
    PeriodKind,
    ReportingRegime,
    StatementFamily,
    ValueKind,
)
from fundamentals.contracts.evidence_tier import EvidenceTier
from fundamentals.contracts.measurement_key import DimensionSet, MeasurementKey, PeriodInterval
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.contracts.qualification import (
    ConditionPredicate,
    ProvenCondition,
    QualificationCondition,
    QualificationContext,
    QualificationFixture,
    QualificationScope,
    qualification_context,
    scoped_tier,
)

DICTIONARY_ROOT = Path(__file__).resolve().parents[2] / "config" / "dictionary"
VERSION = "v1"
APPLICABLE = ApplicabilityStatus.APPLICABLE
NOT_APPLICABLE = ApplicabilityStatus.NOT_APPLICABLE
MARCH = 3
BS_ROW = "total_assets"
CF_ROW = "cfo"
STATEMENT_ROWS = {StatementFamily.BALANCE_SHEET: BS_ROW, StatementFamily.CASH_FLOW: CF_ROW}
SEGMENT_ROWS = ("segment_revenue", "segment_assets", "segment_revenue_members_total")
RESERVES = "reserves_excl_revaluation"
CONSOLIDATED_ONLY = frozenset({Basis.CONSOLIDATED})


@pytest.fixture(scope="module")
def dictionary() -> CanonicalDictionary:
    """Dictionary v1 as committed."""
    return load_dictionary(DICTIONARY_ROOT, VERSION)


def _context(
    kind: PeriodKind,
    present: frozenset[StatementFamily] = frozenset({StatementFamily.PL}),
    *,
    basis: Basis = Basis.CONSOLIDATED,
    status: BasisStatus = BasisStatus.CONSOLIDATED_AND_STANDALONE,
    document: DocumentType = DocumentType.FINANCIAL_RESULTS,
    segment_bases: frozenset[Basis] = CONSOLIDATED_ONLY,
    disclosed: frozenset[str] = frozenset(),
) -> ApplicabilityContext:
    """A results context under the listing regulations; segments evidenced as Apar's are."""
    return ApplicabilityContext(
        regime=ReportingRegime.IN_LODR,
        document_type=document,
        statements_present=present,
        period_kind=kind,
        requested_basis=basis,
        entity_basis_status=status,
        evidenced_segment_bases=segment_bases,
        disclosed_rows=disclosed,
    )


def test_context_carries_no_value_fields() -> None:
    """Applicability is decided before any value exists: the context cannot hold one."""
    assert set(ApplicabilityContext.model_fields) == {
        "regime",
        "document_type",
        "statements_present",
        "period_kind",
        "requested_basis",
        "entity_basis_status",
        "evidenced_segment_bases",
        "disclosed_rows",
    }


@pytest.mark.parametrize("family", list(STATEMENT_ROWS))
@pytest.mark.parametrize("kind", [PeriodKind.QUARTER, PeriodKind.NINE_MONTH])
def test_q1_q3_statement_rows_need_the_statement_in_the_package(
    dictionary: CanonicalDictionary, family: StatementFamily, kind: PeriodKind
) -> None:
    """Q1/Q3 without the statement: NOT_APPLICABLE (not NO_SOURCE); with it: APPLICABLE."""
    row = dictionary.row(STATEMENT_ROWS[family])

    without = decide_applicability(row, _context(kind))
    with_it = decide_applicability(row, _context(kind, frozenset({StatementFamily.PL, family})))

    assert without.status is NOT_APPLICABLE
    assert without.rule_id == row.applicability_rule_id
    assert with_it.status is APPLICABLE


@pytest.mark.parametrize("row_id", [BS_ROW, CF_ROW, "receivable_days", "cf_wc_total"])
@pytest.mark.parametrize("kind", [PeriodKind.HALF_YEAR, PeriodKind.YEAR])
def test_half_year_and_year_require_statements_even_if_none_detected(
    dictionary: CanonicalDictionary, row_id: str, kind: PeriodKind
) -> None:
    """The September half-year balance sheet applies even with an empty statements set."""
    decision = decide_applicability(dictionary.row(row_id), _context(kind, frozenset()))

    assert decision.status is APPLICABLE


@pytest.mark.parametrize("kind", sorted(REPORTING_KINDS))
def test_pl_rows_apply_in_every_reporting_kind(
    dictionary: CanonicalDictionary, kind: PeriodKind
) -> None:
    """P&L rows and formulas over them are filed in every results package."""
    for row_id in ("revenue_from_operations", "opm_pct", "shares_outstanding"):
        assert decide_applicability(dictionary.row(row_id), _context(kind)).status is APPLICABLE


@pytest.mark.parametrize("kind", sorted(REPORTING_KINDS))
def test_segment_rows_are_owed_only_on_an_evidenced_segment_basis(
    dictionary: CanonicalDictionary, kind: PeriodKind
) -> None:
    """Apar's segments are evidenced consolidated only: owed there even in a Q1 package with
    no segment statement detected (missing is later NO_SOURCE); on the standalone basis they
    apply only when the package carries a segment statement; a single-segment entity has none."""
    no_segment_statement = frozenset({StatementFamily.PL})
    with_segment_statement = frozenset({StatementFamily.PL, StatementFamily.SEGMENT})
    for row_id in SEGMENT_ROWS:
        row = dictionary.row(row_id)

        consolidated = decide_applicability(row, _context(kind, no_segment_statement))
        standalone = decide_applicability(
            row, _context(kind, no_segment_statement, basis=Basis.STANDALONE)
        )
        standalone_present = decide_applicability(
            row, _context(kind, with_segment_statement, basis=Basis.STANDALONE)
        )
        no_segments = decide_applicability(
            row, _context(kind, no_segment_statement, segment_bases=frozenset())
        )

        assert consolidated.status is APPLICABLE
        assert (standalone.status, standalone.rule_id) == (NOT_APPLICABLE, "results.segment")
        assert standalone_present.status is APPLICABLE
        assert no_segments.status is NOT_APPLICABLE


@pytest.mark.parametrize(
    ("kind", "disclosed", "expected"),
    [
        (PeriodKind.YEAR, frozenset(), APPLICABLE),
        (PeriodKind.QUARTER, frozenset(), NOT_APPLICABLE),
        (PeriodKind.HALF_YEAR, frozenset(), NOT_APPLICABLE),
        (PeriodKind.QUARTER, frozenset({RESERVES}), APPLICABLE),
    ],
)
def test_annual_reserves_are_owed_only_annually_or_when_disclosed(
    dictionary: CanonicalDictionary,
    kind: PeriodKind,
    disclosed: frozenset[str],
    expected: ApplicabilityStatus,
) -> None:
    """Apar files reserves in its annual filings only: a quarter without the line is not NO_SOURCE,
    and a quarter that does print it keeps the value."""
    decision = decide_applicability(dictionary.row(RESERVES), _context(kind, disclosed=disclosed))

    assert decision.status is expected


def test_standalone_only_issuer_has_no_consolidated_rows(dictionary: CanonicalDictionary) -> None:
    """Every row of every family is NOT_APPLICABLE for a consolidated request, standalone-only;
    a standalone request is never refused by that rule."""
    assert {row.family for row in dictionary.rows} == set(StatementFamily)
    for row in dictionary.rows:
        document = row.applicability_rule.document_type
        all_present = frozenset(StatementFamily)
        consolidated = _context(
            PeriodKind.YEAR, all_present, status=BasisStatus.STANDALONE_ONLY, document=document
        )
        standalone = consolidated.model_copy(update={"requested_basis": Basis.STANDALONE})

        refused = decide_applicability(row, consolidated)

        assert (refused.status, refused.rule_id) == (NOT_APPLICABLE, STANDALONE_ONLY_RULE_ID)
        assert decide_applicability(row, standalone).rule_id != STANDALONE_ONLY_RULE_ID


def test_row_basis_and_document_type_bound_applicability(dictionary: CanonicalDictionary) -> None:
    """A row outside its basis or document type does not apply."""
    revenue = dictionary.row("revenue_from_operations")
    consolidated_only = DictionaryRow.model_validate(
        {**revenue.model_dump(), "basis_applicability": frozenset({Basis.CONSOLIDATED})}
    )

    standalone = decide_applicability(
        consolidated_only, _context(PeriodKind.YEAR, basis=Basis.STANDALONE)
    )
    shareholding_doc = _context(PeriodKind.QUARTER, document=DocumentType.SHAREHOLDING_PATTERN)

    assert (standalone.status, standalone.rule_id) == (NOT_APPLICABLE, ROW_BASIS_RULE_ID)
    assert decide_applicability(revenue, shareholding_doc).status is NOT_APPLICABLE
    assert (
        decide_applicability(dictionary.row("shp_holding_pct"), shareholding_doc).status
        is APPLICABLE
    )
    assert (
        decide_applicability(dictionary.row("shp_holding_pct"), _context(PeriodKind.QUARTER)).status
        is NOT_APPLICABLE
    )


@pytest.mark.parametrize("kind", [PeriodKind.TTM, PeriodKind.INSTANT, PeriodKind.OTHER])
def test_context_refuses_non_reporting_kinds(kind: PeriodKind) -> None:
    """A package reports as a quarter, half-year, nine months or year, nothing else."""
    with pytest.raises(ValidationError):
        _context(kind)


@pytest.mark.parametrize(
    ("period", "expected"),
    [
        (PeriodInterval.duration(date(2025, 7, 1), date(2025, 9, 30)), PeriodKind.QUARTER),
        (PeriodInterval.duration(date(2025, 4, 1), date(2025, 9, 30)), PeriodKind.HALF_YEAR),
        (PeriodInterval.duration(date(2025, 10, 1), date(2026, 3, 31)), PeriodKind.HALF_YEAR),
        (PeriodInterval.duration(date(2025, 4, 1), date(2025, 12, 31)), PeriodKind.NINE_MONTH),
        (PeriodInterval.duration(date(2025, 4, 1), date(2026, 3, 31)), PeriodKind.YEAR),
        (PeriodInterval.duration(date(2025, 1, 1), date(2025, 12, 31)), PeriodKind.TTM),
        (PeriodInterval.duration(date(2025, 5, 1), date(2025, 7, 31)), PeriodKind.OTHER),
        (PeriodInterval.duration(date(2025, 7, 1), date(2025, 9, 29)), PeriodKind.OTHER),
        (PeriodInterval.duration(date(2025, 7, 1), date(2025, 12, 31)), PeriodKind.OTHER),
        (PeriodInterval.at(date(2025, 9, 30)), PeriodKind.INSTANT),
    ],
)
def test_period_kind_comes_from_the_interval(period: PeriodInterval, expected: PeriodKind) -> None:
    """Kinds are derived from exact intervals against a March fiscal year end, never labels."""
    assert period.kind(MARCH) is expected


# --- scoped tiers --------------------------------------------------------------------------

SCHEMA = "http://www.sebi.gov.in/xbrl/2025-01-31/in-capmkt"
SURFACE = "NSE_XBRL_INSTANCE"
DISCONTINUED_ZERO = QualificationCondition(
    condition_id="discontinued_zero",
    canonical_id="profit_discontinued_after_tax",
    predicate=ConditionPredicate.EQUALS_ZERO,
)
EXCEPTIONAL_NONZERO = QualificationCondition(
    condition_id="exceptional_nonzero",
    canonical_id="exceptional_items_before_tax",
    predicate=ConditionPredicate.NOT_EQUALS_ZERO,
)
DEMONSTRATED = EvidenceTier.EQUIVALENCE_DEMONSTRATED
UNPROVEN = EvidenceTier.EQUIVALENCE_UNPROVEN


def _scope(**changes: object) -> QualificationScope:
    """A consolidated quarter and half-year scope with one condition and one exclusion."""
    base = QualificationScope(
        scope_id="scope-1",
        schema_identities=frozenset({SCHEMA}),
        surfaces=frozenset({SURFACE}),
        bases=frozenset({Basis.CONSOLIDATED}),
        period_kinds=frozenset({PeriodKind.QUARTER, PeriodKind.HALF_YEAR}),
        conditions=(DISCONTINUED_ZERO,),
        exclusions=(EXCEPTIONAL_NONZERO,),
        fixture_evidence=tuple(
            QualificationFixture(
                capture_id=f"constructed-{index}",
                capture_sha256=f"{index:064x}",
                entity_id=index,
                discriminating=index == 1,
            )
            for index in range(1, 6)
        ),
        sample_rule="D3: five distinct companies including a discriminating case",
    )
    return base.model_copy(update=changes)


def _proven(condition: QualificationCondition, holds: bool) -> ProvenCondition:
    """A proven condition with one evidencing interpretation id."""
    return ProvenCondition(
        condition_id=condition.condition_id, holds=holds, evidence_interpretation_ids=(7,)
    )


def _qualification(
    proven: tuple[ProvenCondition, ...], *, basis: Basis = Basis.CONSOLIDATED
) -> QualificationContext:
    """A quarter context with the given proofs."""
    return QualificationContext(
        schema_identity=SCHEMA,
        surface=SURFACE,
        basis=basis,
        period_kind=PeriodKind.QUARTER,
        proven={item.condition_id: item for item in proven},
    )


BOTH_PROVEN = (_proven(DISCONTINUED_ZERO, True), _proven(EXCEPTIONAL_NONZERO, False))


def test_scope_without_measured_fixtures_cannot_preserve_demonstrated() -> None:
    """Scope labels and holding conditions alone do not satisfy the D3 sample rule."""
    result = scoped_tier(
        DEMONSTRATED, _scope(fixture_evidence=(), sample_rule=None), _qualification(BOTH_PROVEN)
    )
    assert result.tier is UNPROVEN


@pytest.mark.parametrize(
    "changes",
    [
        {
            "fixture_evidence": tuple(
                QualificationFixture(
                    capture_id=f"constructed-{index}",
                    capture_sha256=f"{index:064x}",
                    entity_id=1,
                    discriminating=index == 1,
                )
                for index in range(1, 6)
            )
        },
        {
            "fixture_evidence": tuple(
                QualificationFixture(
                    capture_id=f"constructed-{index}",
                    capture_sha256=f"{index:064x}",
                    entity_id=index,
                    discriminating=False,
                )
                for index in range(1, 6)
            )
        },
        {"sample_rule": " "},
        {"fixture_capture_sha256s": ("f" * 64,)},
    ],
)
def test_unverified_sample_rule_is_unproven(changes: dict[str, object]) -> None:
    assert (
        scoped_tier(DEMONSTRATED, _scope(**changes), _qualification(BOTH_PROVEN)).tier is UNPROVEN
    )


def test_in_scope_with_conditions_proven_stays_demonstrated() -> None:
    """Every scope part matches and every condition and exclusion is proven the right way."""
    result = scoped_tier(DEMONSTRATED, _scope(), _qualification(BOTH_PROVEN))

    assert result.tier is DEMONSTRATED
    assert result.qualification_ref == "scope-1"
    assert result.condition_evidence == BOTH_PROVEN


@pytest.mark.parametrize(
    ("scope", "context"),
    [
        pytest.param(
            _scope(),
            _qualification((_proven(DISCONTINUED_ZERO, False), BOTH_PROVEN[1])),
            id="condition-false",
        ),
        pytest.param(_scope(), _qualification((BOTH_PROVEN[1],)), id="condition-unproven"),
        pytest.param(_scope(), _qualification((BOTH_PROVEN[0],)), id="exclusion-unproven"),
        pytest.param(
            _scope(),
            _qualification((BOTH_PROVEN[0], _proven(EXCEPTIONAL_NONZERO, True))),
            id="exclusion-holds",
        ),
        pytest.param(
            _scope(), _qualification(BOTH_PROVEN, basis=Basis.STANDALONE), id="basis-out-of-scope"
        ),
        pytest.param(
            _scope(surfaces=frozenset({"NSE_RESULTS_PDF"})),
            _qualification(BOTH_PROVEN),
            id="surface-out-of-scope",
        ),
        pytest.param(None, _qualification(BOTH_PROVEN), id="no-scope"),
    ],
)
def test_demonstrated_outside_its_proven_scope_is_unproven(
    scope: QualificationScope | None, context: QualificationContext
) -> None:
    """No scope, out of scope, or any condition not proven the right way: unproven, no ref."""
    result = scoped_tier(DEMONSTRATED, scope, context)

    assert (result.tier, result.qualification_ref, result.condition_evidence) == (
        UNPROVEN,
        None,
        (),
    )


def test_proofs_must_carry_evidence_and_match_their_condition() -> None:
    """A proof without evidence, or filed under another condition's id, is refused."""
    with pytest.raises(ValidationError):
        ProvenCondition(
            condition_id="discontinued_zero", holds=True, evidence_interpretation_ids=()
        )
    with pytest.raises(ValidationError):
        QualificationContext(
            schema_identity=SCHEMA,
            surface=SURFACE,
            basis=Basis.CONSOLIDATED,
            period_kind=PeriodKind.QUARTER,
            proven={DISCONTINUED_ZERO.condition_id: _proven(EXCEPTIONAL_NONZERO, False)},
        )


def test_proofs_cannot_be_changed_after_validation() -> None:
    """The proof mapping is read-only, so a frozen context cannot gain a proof later."""
    context = _qualification(BOTH_PROVEN)

    with pytest.raises(TypeError):
        context.proven["late"] = BOTH_PROVEN[0]  # type: ignore[index]


@pytest.mark.parametrize(
    "changes",
    [
        pytest.param(
            {
                "exclusions": (
                    DISCONTINUED_ZERO.model_copy(update={"predicate": "NOT_EQUALS_ZERO"}),
                )
            },
            id="same-id-other-predicate",
        ),
        pytest.param(
            {"exclusions": (DISCONTINUED_ZERO.model_copy(update={"canonical_id": "tax_expense"}),)},
            id="same-id-other-row",
        ),
        pytest.param({"exclusions": (DISCONTINUED_ZERO,)}, id="both-condition-and-exclusion"),
    ],
)
def test_scope_refuses_conflicting_condition_ids(changes: dict[str, object]) -> None:
    """One condition id has one meaning, and cannot be both required and excluded."""
    with pytest.raises(ValidationError):
        QualificationScope.model_validate({**_scope().model_dump(), **changes})


def test_weaker_tiers_pass_through_unchanged() -> None:
    """Scope can withhold strength but never add it."""
    result = scoped_tier(EvidenceTier.RELATED_NOT_EQUIVALENT, _scope(), _qualification(BOTH_PROVEN))

    assert result.tier is EvidenceTier.RELATED_NOT_EQUIVALENT
    assert result.qualification_ref is None


def test_quarter_scope_follows_each_keys_own_period_kind() -> None:
    """Same package, two keys: the Q2 quarter key is demonstrated, the H1 key is not."""
    scope = _scope(period_kinds=frozenset({PeriodKind.QUARTER}), conditions=(), exclusions=())

    def key(start: date) -> MeasurementKey:
        return MeasurementKey(
            entity_id=1,
            canonical_id="revenue_from_operations",
            period=PeriodInterval.duration(start, date(2025, 9, 30)),
            basis=Basis.CONSOLIDATED,
            framework=AccountingFramework.IND_AS,
            currency="INR",
            value_kind=ValueKind.CURRENCY_AMOUNT,
            dimensions=DimensionSet(),
        )

    def tier(start: date) -> EvidenceTier:
        context = qualification_context(
            key(start),
            schema_identity=SCHEMA,
            surface=SURFACE,
            fiscal_year_end_month=MARCH,
            proven={},
        )
        return scoped_tier(DEMONSTRATED, scope, context).tier

    assert tier(date(2025, 7, 1)) is DEMONSTRATED
    assert tier(date(2025, 4, 1)) is UNPROVEN
