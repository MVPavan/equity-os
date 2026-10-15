"""D3.2 acceptance: the claim check row by row, citation authority and legacy first-seen times.

``check_claim`` is a pure function over a claim and what its citation resolved to, tested per
spec row in both modes (ledger spec §1). ``resolve_citation`` and ``resolve_location`` run on
an ``eqos_test_*`` database holding the D2 legacy import, acquisitions and cited runs (plan
D8, D9).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from functools import partial
from typing import Any

import psycopg
import pytest
from ledger_cited_support import Cited, cited
from ledger_support import SELF_CITED, Ledger, ledger
from pg_evidence_schema_support import runtime, seeded
from selection_support import key

from fundamentals.contracts.canonical import ValueKind
from fundamentals.contracts.evidence import RunMode
from fundamentals.contracts.guidance_claim import EpistemicClass
from fundamentals.contracts.ledger import (
    Citation,
    CitationKind,
    ClaimState,
    GuidanceContract,
    InputTime,
    NumericClaim,
    ResolvedCitation,
    Rounding,
    VersionState,
)
from fundamentals.ledger import store
from fundamentals.ledger.citations import resolve_location
from fundamentals.ledger.claim_check import check_claim, cutoff_instant, quote_qualifiers
from fundamentals.ledger.numeral_scan import scan_section

__all__ = ["cited", "ledger", "runtime", "seeded"]

CUTOFF = datetime(2026, 7, 31, 18, 30, tzinfo=UTC)
BEFORE, AFTER = CUTOFF - timedelta(days=1), CUTOFF + timedelta(microseconds=1)
QUOTE = "guiding about 9.5%, 10%"
CONTRACT = GuidanceContract(
    metric="ebitda_margin", scope="company", horizon="FY27", unit="%", constant_currency=False
)

FIGURE = NumericClaim(
    claim_key="fact.revenue",
    section_key="results",
    citation=Citation(kind=CitationKind.FIGURE, fact_origin="sqlite-x", fact_origin_id=11),
    measurement_key=key(),
    value_kind=ValueKind.CURRENCY_AMOUNT,
    unit="INR crore",
    currency="INR",
    scale=10_000_000,
    value=Decimal("6591.06"),
    precision=2,
    rounding=Rounding.ROUND_HALF_UP,
    epistemic_class=EpistemicClass.OBSERVED,
)
FIGURE_CITED = ResolvedCitation(
    value=Decimal("6591.06"),
    key_digest=key().digest(),
    value_kind=ValueKind.CURRENCY_AMOUNT,
    unit="INR crore",
    currency="INR",
    scale=10_000_000,
    times=((InputTime.KNOWLEDGE, BEFORE), (InputTime.FIRST_SEEN, BEFORE)),
    trusted=True,
)
QUOTED = NumericClaim(
    claim_key="ledger.ebitda_margin.FY27.company",
    section_key="ledger",
    citation=Citation(
        kind=CitationKind.SOURCE_QUOTE, capture_ref_id=1, anchor="p1.b0.0:23", quote=QUOTE
    ),
    value_kind=ValueKind.PERCENTAGE,
    unit="%",
    lower_bound=Decimal("9.5"),
    upper_bound=Decimal("10"),
    horizon="FY27",
    qualifiers=("about",),
    precision=1,
    rounding=Rounding.ROUND_HALF_UP,
    epistemic_class=EpistemicClass.FORECAST,
    metric="ebitda_margin",
    scope="company",
    constant_currency=False,
)
QUOTE_CITED = ResolvedCitation(
    times=((InputTime.FIRST_SEEN, BEFORE),), quote_text=QUOTE, guidance=CONTRACT
)
PLUS = "20%-plus"
PLUS_QUOTED = QUOTED.model_copy(
    update={
        "citation": QUOTED.citation.model_copy(update={"quote": PLUS}),
        "lower_bound": Decimal("20"),
        "upper_bound": Decimal("20"),
        "qualifiers": ("plus",),
    }
)


def _times(**times: datetime | None) -> dict[str, Any]:
    return {"times": tuple((InputTime[name], at) for name, at in times.items())}


def case(
    name: str,
    expected: ClaimState,
    claim: NumericClaim = FIGURE,
    cited_record: ResolvedCitation | None = FIGURE_CITED,
    **updates: dict[str, Any],
) -> Any:
    """One table case: ``claim`` and ``cited_record`` with ``mine``/``theirs`` field updates."""
    record = cited_record and cited_record.model_copy(update=updates.get("theirs", {}))
    return pytest.param(claim.model_copy(update=updates.get("mine", {})), record, expected, id=name)


UNIT, MEANING = ClaimState.UNIT_MISMATCH, ClaimState.QUOTE_MEANING_MISMATCH
HALF_EVEN_29 = {"precision": 1, "rounding": Rounding.ROUND_HALF_EVEN, "value": Decimal("29.0")}
ROWS = [
    case("1-unresolved", ClaimState.UNRESOLVED, cited_record=None),
    case("1-resolved", ClaimState.MATCH),
    case("2-first-seen-after", ClaimState.POST_CUTOFF, theirs=_times(FIRST_SEEN=AFTER)),
    case("2-missing", ClaimState.POST_CUTOFF, theirs=_times(KNOWLEDGE=None, FIRST_SEEN=BEFORE)),
    case("2-run-after", ClaimState.POST_CUTOFF, theirs=_times(RUN=AFTER)),
    case("2-at-cutoff", ClaimState.MATCH, theirs=_times(KNOWLEDGE=CUTOFF, FIRST_SEEN=CUTOFF)),
    case(
        "2-before-5", ClaimState.POST_CUTOFF, mine={"value": Decimal(1)}, theirs=_times(RUN=AFTER)
    ),
    case("3-unit", UNIT, mine={"unit": "INR lakh"}),
    case("3-scale", UNIT, mine={"scale": 100_000}),
    case("3-currency", UNIT, mine={"currency": "USD"}),
    case("3-value-kind", UNIT, mine={"value_kind": ValueKind.COUNT}),
    case("3-not-carried", ClaimState.MATCH, mine={"unit": "%"}, theirs={"unit": None}),
    case("4-key", ClaimState.KEY_MISMATCH, mine={"measurement_key": key("profit_before_tax")}),
    case("5-value", ClaimState.VALUE_MISMATCH, mine={"value": Decimal("6591.07")}),
    case("5-at-precision", ClaimState.MATCH, theirs={"value": Decimal("6591.0649")}),
    case("5-half-even", ClaimState.MATCH, mine=HALF_EVEN_29, theirs={"value": Decimal("29.05")}),
    case(
        "5-half-up",
        ClaimState.VALUE_MISMATCH,
        mine={"precision": 1, "value": Decimal("29.0")},
        theirs={"value": Decimal("29.05")},
    ),
    case(
        "6-other-text", ClaimState.QUOTE_NOT_FOUND, QUOTED, QUOTE_CITED, theirs={"quote_text": "x"}
    ),
    case("6-no-span", ClaimState.QUOTE_NOT_FOUND, QUOTED, QUOTE_CITED, theirs={"quote_text": None}),
    case("6-verbatim", ClaimState.MATCH, QUOTED, QUOTE_CITED),
    case("7-bounds", MEANING, QUOTED, QUOTE_CITED, mine={"upper_bound": Decimal("11")}),
    case("7-qualifiers", MEANING, QUOTED, QUOTE_CITED, mine={"qualifiers": ()}),
    case(
        "7-plus-dropped",
        MEANING,
        PLUS_QUOTED,
        QUOTE_CITED,
        mine={"qualifiers": ()},
        theirs={"quote_text": PLUS},
    ),
    case("7-plus-kept", ClaimState.MATCH, PLUS_QUOTED, QUOTE_CITED, theirs={"quote_text": PLUS}),
    case("7-metric", MEANING, QUOTED, QUOTE_CITED, mine={"metric": "revenue_growth"}),
    case("7-scope", MEANING, QUOTED, QUOTE_CITED, mine={"scope": "cables"}),
    case("7-constant-currency", MEANING, QUOTED, QUOTE_CITED, mine={"constant_currency": True}),
    case("7-horizon", MEANING, QUOTED, QUOTE_CITED, mine={"horizon": "FY28"}),
    case("8-untrusted", ClaimState.MATCH_UNTRUSTED, theirs={"trusted": False}),
    case("8-no-run-cell", ClaimState.MATCH, theirs={"trusted": None}),
]


@pytest.mark.parametrize("mode", list(RunMode))
@pytest.mark.parametrize(("claim", "resolved", "expected"), ROWS)
def test_claim_check_rows(
    mode: RunMode, claim: NumericClaim, resolved: ResolvedCitation | None, expected: ClaimState
) -> None:
    """The first matching spec row wins, identically in both modes for these inputs."""
    state = check_claim(claim, resolved, mode=mode, cutoff=CUTOFF, imported=False)
    assert state is expected


@pytest.mark.parametrize("name", ["RECORDED", "SELECTED", "POLICY"])
def test_as_known_only_times(name: str) -> None:
    """Interpretation recorded-at, selection time and policy recorded-at count only as known."""
    resolved = FIGURE_CITED.model_copy(update=_times(KNOWLEDGE=BEFORE, **{name: AFTER}))
    states = {
        mode: check_claim(FIGURE, resolved, mode=mode, cutoff=CUTOFF, imported=False)
        for mode in RunMode
    }
    assert states == {
        RunMode.AS_KNOWN: ClaimState.POST_CUTOFF,
        RunMode.RETROSPECTIVE: ClaimState.MATCH,
    }


def test_only_an_import_may_self_cite_policy() -> None:
    """A self-cited ``POLICY`` claim has no owner decision behind it: an import's own record
    holds its value, a draft's holds nothing."""
    resolved = ResolvedCitation(value=SELF_CITED.value)
    check = {"resolved": resolved, "mode": RunMode.AS_KNOWN, "cutoff": CUTOFF}
    assert check_claim(SELF_CITED, imported=False, **check) is ClaimState.UNRESOLVED
    assert check_claim(SELF_CITED, imported=True, **check) is ClaimState.MATCH
    wrong = ResolvedCitation(value=Decimal("11.56"))
    assert check_claim(SELF_CITED, wrong, mode=RunMode.AS_KNOWN, cutoff=CUTOFF, imported=True) is (
        ClaimState.VALUE_MISMATCH
    )


@pytest.mark.pg
def test_submit_refuses_a_draft_self_citing_policy(ledger: Ledger) -> None:
    """The 0012 SUBMIT trigger refuses a draft whose ``POLICY`` claim cites no owner decision."""
    version_id = ledger.draft(ledger.report(), claims=(SELF_CITED,))
    with pytest.raises(psycopg.errors.CheckViolation, match="illegal decision"):
        ledger.submit(version_id)


def test_cutoff_instant_is_midnight_ist() -> None:
    """A date-only cutoff ends at 24:00 IST that day."""
    assert cutoff_instant(date(2026, 7, 31)) == CUTOFF


@pytest.mark.parametrize(
    ("quote", "expected"),
    [
        (PLUS, {"plus"}),
        ("revenue growth of 20% plus", {"plus"}),
        (QUOTE, {"about"}),
        ("a surplus, roundabout", set()),
    ],
)
def test_quote_qualifiers(quote: str, expected: set[str]) -> None:
    """Qualifiers come from the quote's own whole words, from a closed lexicon."""
    assert quote_qualifiers(quote) == frozenset(expected)


# --- resolution on a seeded database (D8, D9)


@pytest.mark.pg
@pytest.mark.retained
def test_legacy_first_seen_comes_from_the_retrieval_manifest(cited: Cited) -> None:
    """D8: the FY27_Q1 revenue fact's capture was registered today, but its blob was retrieved
    on 2026-09-06; the claim check sees the manifest time and the registration is untouched."""
    resolved = cited.resolve(cited.legacy_revenue())
    assert resolved is not None
    assert (InputTime.FIRST_SEEN, datetime(2026, 9, 6, 15, 31, 30, 984308, tzinfo=UTC)) in (
        resolved.times
    )
    assert (resolved.value, resolved.unit, resolved.scale) == (
        Decimal("6591.06"),
        "INR crore",
        10_000_000,
    )
    registered = cited.query(
        "SELECT c.registered_at FROM eqos.capture_refs c "
        "JOIN eqos.legacy_evidence_bindings b ON b.capture_ref_id = c.id "
        "WHERE b.file_sha256 = %s",
        cited.revenue_file_sha256,
    )
    assert registered == cited.revenue_registered_at
    assert registered and all(at > cited.started for (at,) in registered)


@pytest.mark.pg
@pytest.mark.retained
def test_acquisitions_refuse_a_tampered_manifest(cited: Cited) -> None:
    """Acquisition times come only from the hash-pinned manifest; re-runs add nothing."""
    body = cited.manifest_bytes
    with cited.panel() as cursor:
        assert store.insert_acquisitions(cursor, body, expected_sha256=cited.manifest_sha256) == 0
        with pytest.raises(ValueError, match="SHA-256"):
            store.insert_acquisitions(
                cursor,
                body.replace(b"15:31:30", b"15:31:31"),
                expected_sha256=cited.manifest_sha256,
            )


@pytest.mark.pg
@pytest.mark.retained
def test_capture_without_acquisition_keeps_its_own_first_seen(cited: Cited) -> None:
    """A capture absent from the manifest is first seen at its own registration."""
    resolved = cited.resolve(cited.interpretation_figure())
    assert resolved is not None
    assert (InputTime.FIRST_SEEN, cited.fixture_first_seen) in resolved.times


@pytest.mark.pg
@pytest.mark.retained
def test_interpretation_figure_resolves_only_through_its_run_cell(cited: Cited) -> None:
    """D9: a ``FIGURE`` on an interpretation resolves only through the named run's ``VALUE``
    source value under the claim's key, with that row's value."""
    resolved = cited.resolve(cited.interpretation_figure())
    assert resolved is not None
    assert (resolved.value, resolved.key_digest, resolved.trusted) == (
        cited.cell_value,
        cited.cell_key.digest(),
        False,
    )
    assert any(name is InputTime.RECORDED for name, _ in resolved.times)
    assert cited.resolve(cited.interpretation_figure(not_selected=True)) is None
    assert cited.resolve(cited.interpretation_figure(other_key=True)) is None


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize("case", ["vendor_fact", "vendor_operand_trace", "vendor_quote"])
def test_vendor_records_do_not_resolve(cited: Cited, case: str) -> None:
    """D9: ``FIGURE``/``CALCULATION`` cite first-party values only, and a quote never cites a
    vendor capture; each is ``UNRESOLVED``."""
    assert cited.resolve(getattr(cited, case)()) is None


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize(
    ("case", "value", "time"),
    [
        ("first_party_trace", Decimal("12.34"), InputTime.KNOWLEDGE),
        ("comparison", -200, InputTime.RUN),
    ],
)
def test_first_party_trace_and_comparison_resolve(
    cited: Cited, case: str, value: Decimal, time: InputTime
) -> None:
    """A trace over first-party operands resolves with every operand's times; a comparison to
    its stored pair difference with its run time."""
    resolved = cited.resolve(getattr(cited, case)())
    assert resolved is not None
    assert resolved.value == value
    assert time in {name for name, _ in resolved.times}


@pytest.mark.pg
@pytest.mark.retained
@pytest.mark.parametrize(
    ("which", "anchor", "holds"),
    [
        ("pdf", "valid", True),
        ("missing", "valid", False),
        ("pdf", "p1.b0.0:100000", False),
        ("pdf", "zero", False),
        ("pdf", "whitespace", False),
        ("pdf", "p1.b0", False),
        ("vendor", "valid", False),
    ],
)
def test_location_markers(cited: Cited, which: str, anchor: str, holds: bool) -> None:
    """D9: ``{{s:…}}`` resolves only to a non-empty span inside a non-vendor capture's bytes;
    a failing one leaves the observed paragraph ``UNCITED_PROSE``."""
    capture_id, span = cited.location(which, anchor)
    with cited.runtime() as cursor:
        resolves = partial(
            resolve_location, cursor, catalog=cited.catalog, snapshots=cited.snapshots
        )
        states = scan_section(
            f"{{{{e:observed}}}} Said so {{{{s:{capture_id}|{span}}}}}.", resolves=resolves
        )
    assert states == (() if holds else (VersionState.UNCITED_PROSE,))
