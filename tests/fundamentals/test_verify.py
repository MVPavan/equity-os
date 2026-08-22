"""Slice 1 verification-module tests.

Exercises the four integrity gates against the frozen Infosys Q1 FY25 oracle:

* cross-foot passes on the Q1 accounting identities and fails on a broken one;
* cross_check rejects an Ind AS INR/Q1 vs SEC USD/annual comparison (currency +
  basis + period mismatch) and accepts a matching cross-source pair;
* quote_anchor passes for a real page/block/span and fails for a wrong or absent
  span;
* a missing required fact fails closed (raises).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from fundamentals.contracts.guidance_claim import GuidanceClaim
from fundamentals.contracts.observation import (
    AccountingFramework,
    Observation,
    PeriodType,
    Scope,
)
from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.verify.comparison_key import explain_comparability
from fundamentals.verify.cross_check import cross_check
from fundamentals.verify.crossfoot import (
    Identity,
    MissingRequiredFactError,
    SignedTerm,
    check_identity,
    observation_half_ulp,
)
from fundamentals.verify.quote_anchor import (
    SourceBlock,
    SourceDocument,
    verify_quote_anchor,
)

_RETRIEVED_AT = datetime(2024, 7, 18, tzinfo=UTC)

# --- concept QNames (from the frozen oracle plus its cross-foot terms) ---------
REVENUE = "in-bse-fin:RevenueFromOperations"
OTHER_INCOME = "in-bse-fin:OtherIncome"
TOTAL_INCOME = "in-bse-fin:Income"
TOTAL_EXPENSES = "in-bse-fin:Expenses"
PBT = "in-bse-fin:ProfitBeforeTax"
TAX = "in-bse-fin:TaxExpense"
PAT = "in-bse-fin:ProfitLossForPeriod"
ATTRIBUTABLE = "in-bse-fin:ProfitOrLossAttributableToOwnersOfParent"
NCI = "in-bse-fin:ProfitOrLossAttributableToNoncontrollingInterests"

# Q1 FY25 consolidated values in INR crore (docs/research + manifest oracle).
_Q1_VALUES: dict[str, int] = {
    REVENUE: 39315,
    OTHER_INCOME: 838,
    TOTAL_INCOME: 40153,
    TOTAL_EXPENSES: 31132,
    PBT: 9021,
    TAX: 2647,
    PAT: 6374,
    ATTRIBUTABLE: 6368,
    NCI: 6,
}


def _xbrl_provenance() -> Provenance:
    return Provenance(
        source_id="nse-indas-xbrl-consolidated",
        file_sha256="0" * 64,
        anchor_type=SourceAnchorType.XBRL_CONTEXT,
        context_ref="OneD",
        retrieved_at=_RETRIEVED_AT,
    )


def _crore_observation(
    concept: str,
    normalized_value: Decimal,
    *,
    currency: str = "INR",
    basis: AccountingFramework = AccountingFramework.IND_AS,
    scope: Scope = Scope.CONSOLIDATED,
    period_start: date = date(2024, 4, 1),
    period_end: date = date(2024, 6, 30),
    scale: int = 10_000_000,
    decimals: int = -7,
    unit: str = "INR crore",
    provenance: Provenance | None = None,
) -> Observation:
    """Build a consolidated Ind AS INR-crore Q1 observation (overridable)."""
    return Observation(
        concept_qname=concept,
        raw_value=str(int(normalized_value) * scale),
        normalized_value=normalized_value,
        normalized_unit=unit,
        context_ref="OneD",
        entity_scheme="nse-symbol",
        entity_id="INFY",
        scope=scope,
        accounting_basis=basis,
        period_type=PeriodType.DURATION,
        period_start=period_start,
        period_end=period_end,
        currency=currency,
        scale=scale,
        decimals=decimals,
        provenance=provenance or _xbrl_provenance(),
    )


def _q1_observations() -> dict[str, Observation]:
    return {
        concept: _crore_observation(concept, Decimal(value))
        for concept, value in _Q1_VALUES.items()
    }


_IDENTITIES = (
    Identity(
        name="Total income = Revenue + Other income",
        lhs_concept=TOTAL_INCOME,
        terms=(
            SignedTerm(sign=1, concept_qname=REVENUE),
            SignedTerm(sign=1, concept_qname=OTHER_INCOME),
        ),
    ),
    Identity(
        name="PBT = Total income - Total expenses",
        lhs_concept=PBT,
        terms=(
            SignedTerm(sign=1, concept_qname=TOTAL_INCOME),
            SignedTerm(sign=-1, concept_qname=TOTAL_EXPENSES),
        ),
    ),
    Identity(
        name="PAT = PBT - Tax",
        lhs_concept=PAT,
        terms=(
            SignedTerm(sign=1, concept_qname=PBT),
            SignedTerm(sign=-1, concept_qname=TAX),
        ),
    ),
    Identity(
        name="PAT = Attributable + NCI",
        lhs_concept=PAT,
        terms=(
            SignedTerm(sign=1, concept_qname=ATTRIBUTABLE),
            SignedTerm(sign=1, concept_qname=NCI),
        ),
    ),
)


# --- decimals-derived tolerance ------------------------------------------------


def test_tolerance_is_derived_from_decimals_not_a_constant() -> None:
    crore = _crore_observation(REVENUE, Decimal(39315))
    assert observation_half_ulp(crore) == Decimal("0.5")

    eps = _crore_observation(
        "in-bse-fin:BasicEPS",
        Decimal("15.38"),
        scale=1,
        decimals=2,
        unit="INR per share",
    )
    assert observation_half_ulp(eps) == Decimal("0.005")


# --- cross-foot ----------------------------------------------------------------


def test_crossfoot_passes_on_q1_identities() -> None:
    observations = _q1_observations()
    for identity in _IDENTITIES:
        result = check_identity(identity, observations)
        assert result.passed, (identity.name, result.residual, result.tolerance)
        assert result.residual == Decimal(0)


def test_crossfoot_fails_on_a_broken_identity() -> None:
    observations = _q1_observations()
    # Corrupt total expenses so PBT no longer foots.
    observations[TOTAL_EXPENSES] = _crore_observation(TOTAL_EXPENSES, Decimal(31000))

    pbt_identity = _IDENTITIES[1]
    result = check_identity(pbt_identity, observations)
    assert not result.passed
    assert result.residual == Decimal(-132)
    assert abs(result.residual) > result.tolerance


def test_crossfoot_missing_required_fact_fails_closed() -> None:
    observations = _q1_observations()
    del observations[TAX]  # required by the PAT = PBT - Tax identity

    pat_identity = _IDENTITIES[2]
    with pytest.raises(MissingRequiredFactError):
        check_identity(pat_identity, observations)


# --- cross_check (the currency/basis/period guard) -----------------------------


def _sec_annual_usd_pat() -> Observation:
    """SEC 20-F FY25 annual PAT: USD, IFRS, full-year — a category mismatch."""
    return Observation(
        concept_qname=PAT,
        raw_value="3160000000",
        normalized_value=Decimal("3160"),
        normalized_unit="USD million",
        entity_scheme="nse-symbol",
        entity_id="INFY",
        scope=Scope.CONSOLIDATED,
        accounting_basis=AccountingFramework.IFRS,
        period_type=PeriodType.DURATION,
        period_start=date(2024, 4, 1),
        period_end=date(2025, 3, 31),
        currency="USD",
        scale=1_000_000,
        decimals=-6,
        provenance=Provenance(
            source_id="sec-20f-fy25",
            file_sha256="1" * 64,
            anchor_type=SourceAnchorType.XBRL_CONTEXT,
            context_ref="FY25",
            retrieved_at=_RETRIEVED_AT,
        ),
    )


def test_cross_check_rejects_inr_q1_vs_usd_annual() -> None:
    inr_q1 = _crore_observation(PAT, Decimal(6374))
    usd_annual = _sec_annual_usd_pat()

    result = cross_check(inr_q1, usd_annual)

    assert result.keys_compatible is False
    assert result.matched is False
    joined = " | ".join(result.reasons)
    assert "currency" in joined
    assert "accounting_basis" in joined
    assert "period" in joined
    # No numeric comparison is attempted when the keys are incompatible.
    assert result.residual is None

    # The comparison-key explainer surfaces the same reasons.
    explained = explain_comparability(inr_q1, usd_annual)
    assert explained.comparable is False


def test_cross_check_accepts_matching_cross_source_pair() -> None:
    xbrl_pat = _crore_observation(PAT, Decimal(6374))
    pdf_pat = _crore_observation(
        PAT,
        Decimal(6374),
        provenance=Provenance(
            source_id="infy-q1-fy25-results-pdf",
            file_sha256="a" * 64,
            anchor_type=SourceAnchorType.PDF_SPAN,
            page=11,
            block=4,
            span="0:5",
            retrieved_at=_RETRIEVED_AT,
        ),
    )

    result = cross_check(xbrl_pat, pdf_pat)

    assert result.keys_compatible is True
    assert result.matched is True
    assert result.residual == Decimal(0)


def test_cross_check_rejects_value_mismatch_even_with_matching_keys() -> None:
    left = _crore_observation(PAT, Decimal(6374))
    right = _crore_observation(PAT, Decimal(6300))

    result = cross_check(left, right)

    assert result.keys_compatible is True
    assert result.matched is False
    assert result.residual == Decimal(74)


# --- accounting-basis wildcard (a derived source declares no framework) --------


def test_unknown_accounting_basis_is_compatible_with_a_declared_framework() -> None:
    # A derived source (e.g. Screener) declares UNKNOWN basis; it must be able to
    # corroborate a first-party Ind AS value when every other key field matches.
    first_party = _crore_observation(PAT, Decimal(6374), basis=AccountingFramework.IND_AS)
    derived = _crore_observation(PAT, Decimal(6374), basis=AccountingFramework.UNKNOWN)

    result = cross_check(first_party, derived)
    assert result.keys_compatible is True
    assert result.matched is True

    # Wildcard is symmetric and surfaces no basis reason from either direction.
    assert explain_comparability(first_party, derived).comparable is True
    assert explain_comparability(derived, first_party).comparable is True


def test_two_different_declared_frameworks_still_do_not_compare() -> None:
    # The IFRS-vs-IndAS guard must NOT be weakened: two declared frameworks that
    # differ remain a category mismatch even when the numbers coincide.
    ind_as = _crore_observation(PAT, Decimal(6374), basis=AccountingFramework.IND_AS)
    ifrs = _crore_observation(PAT, Decimal(6374), basis=AccountingFramework.IFRS)

    result = explain_comparability(ind_as, ifrs)
    assert result.comparable is False
    assert any("accounting_basis" in reason for reason in result.reasons)


def test_two_unknown_bases_are_compatible() -> None:
    left = _crore_observation(PAT, Decimal(6374), basis=AccountingFramework.UNKNOWN)
    right = _crore_observation(PAT, Decimal(6374), basis=AccountingFramework.UNKNOWN)

    assert explain_comparability(left, right).comparable is True


# --- quote_anchor --------------------------------------------------------------

_GUIDANCE_TEXT = (
    "For fiscal 2025, the company expects revenue growth of 3-4% in constant "
    "currency and an operating margin of 20-22%."
)
_QUOTE = "3-4% in constant currency"


def _source_document() -> SourceDocument:
    return SourceDocument(
        blocks=(
            SourceBlock(page=8, block=0, text="Management outlook"),
            SourceBlock(page=8, block=2, text=_GUIDANCE_TEXT),
        )
    )


def _guidance_claim(page: int, block: int, span: str) -> GuidanceClaim:
    return GuidanceClaim(
        metric="revenue_growth",
        lower_bound=Decimal("3"),
        upper_bound=Decimal("4"),
        unit="percent",
        constant_currency=True,
        horizon="FY25",
        scope=Scope.CONSOLIDATED,
        provenance=Provenance(
            source_id="infy-q1-fy25-results-pdf",
            file_sha256="a" * 64,
            anchor_type=SourceAnchorType.PDF_SPAN,
            page=page,
            block=block,
            span=span,
            retrieved_at=_RETRIEVED_AT,
        ),
    )


def test_quote_anchor_passes_for_real_span() -> None:
    start = _GUIDANCE_TEXT.index(_QUOTE)
    span = f"{start}:{start + len(_QUOTE)}"
    claim = _guidance_claim(page=8, block=2, span=span)

    result = verify_quote_anchor(claim, _QUOTE, _source_document())

    assert result.anchored is True
    assert result.resolved_text == _QUOTE


def test_quote_anchor_fails_for_wrong_span() -> None:
    # Points at the start of the block, where the quote does not live.
    claim = _guidance_claim(page=8, block=2, span="0:17")

    result = verify_quote_anchor(claim, _QUOTE, _source_document())

    assert result.anchored is False
    assert result.reason is not None
    assert _QUOTE not in (result.resolved_text or "")


def test_quote_anchor_fails_for_absent_block() -> None:
    claim = _guidance_claim(page=99, block=0, span="0:5")

    result = verify_quote_anchor(claim, _QUOTE, _source_document())

    assert result.anchored is False
    assert result.reason is not None
    assert "no block" in result.reason


def test_quote_anchor_works_on_an_observation_too() -> None:
    start = _GUIDANCE_TEXT.index(_QUOTE)
    span = f"{start}:{start + len(_QUOTE)}"
    pdf_observation = _crore_observation(
        REVENUE,
        Decimal(39315),
        provenance=Provenance(
            source_id="infy-q1-fy25-results-pdf",
            file_sha256="a" * 64,
            anchor_type=SourceAnchorType.PDF_SPAN,
            page=8,
            block=2,
            span=span,
            retrieved_at=_RETRIEVED_AT,
        ),
    )

    result = verify_quote_anchor(pdf_observation, _QUOTE, _source_document())
    assert result.anchored is True
