"""D3.2 acceptance: placeholder display, the deterministic narrative and the prose scans.

Displays must be byte-identical to the retained earnings-update renderings (plan D5, D7), and
the scans enforce ledger spec §1's numeric-coverage and prose-label rules at ``SUBMIT``.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal
from typing import Any

import pytest

from fundamentals.contracts.canonical import ValueKind
from fundamentals.contracts.guidance_claim import EpistemicClass
from fundamentals.contracts.ledger import (
    Citation,
    CitationKind,
    NumericClaim,
    ReportSection,
    Rounding,
    VersionState,
)
from fundamentals.ledger.display import (
    DisplayError,
    content_hash,
    narrative,
    parse_style,
    render_claim,
    render_section,
)
from fundamentals.ledger.numeral_scan import scan_section

QUOTE = "guiding about 9.5%, 10%"


def numeric(
    value: str | None = None, bounds: tuple[str, str] | None = None, **update: Any
) -> NumericClaim:
    """A claim with ``value`` or ``bounds``; quote claims cite :data:`QUOTE`."""
    quoted = bounds is not None
    citation = (
        Citation(kind=CitationKind.SOURCE_QUOTE, capture_ref_id=1, anchor="p1.b0.0:23", quote=QUOTE)
        if quoted
        else Citation(kind=CitationKind.CALCULATION, calculation_trace_id=1)
    )
    fields: dict[str, Any] = {
        "claim_key": "c",
        "section_key": "preamble",
        "citation": citation,
        "value_kind": ValueKind.PERCENTAGE,
        "unit": "%",
        "value": None if value is None else Decimal(value),
        "lower_bound": None if bounds is None else Decimal(bounds[0]),
        "upper_bound": None if bounds is None else Decimal(bounds[1]),
        "precision": 2,
        "rounding": Rounding.ROUND_HALF_UP,
        "epistemic_class": EpistemicClass.FORECAST if quoted else EpistemicClass.COMPUTED,
    }
    return NumericClaim.model_validate(fields | update)


CRORE = {"unit": "INR crore", "value_kind": ValueKind.CURRENCY_AMOUNT, "currency": "INR"}
HALF_EVEN = {"precision": 1, "rounding": Rounding.ROUND_HALF_EVEN}


@pytest.mark.parametrize(
    ("claim", "style", "expected"),
    [
        (numeric("6591.06", **CRORE), "group-intl", "6,591.06"),
        (numeric("6591.06", **CRORE), "", "6591.06"),
        (numeric("256.70", **CRORE), "", "256.70"),
        (numeric("256.70", **CRORE), "trim", "256.7"),
        (numeric("6591.06", **CRORE), "group-intl,unit", "6,591.06 INR crore"),
        (numeric("12345678.9", **CRORE), "group-indian", "1,23,45,678.90"),
        (numeric("29.05", **HALF_EVEN), "plus,unit", "+29.0%"),
        (numeric("29.1", **HALF_EVEN), "plus,unit", "+29.1%"),
        (numeric("0.04", precision=1), "plus", "0.0"),
        (numeric("-12.5", precision=1), "plus,unit", "-12.5%"),
        (numeric(bounds=("9.5", "10"), precision=1), "range-dash,unit,trim", "9.5–10%"),
        (numeric(bounds=("9.5", "10"), precision=1), "range-dash,unit", "9.5–10.0%"),
        (numeric(bounds=("9.5", "10"), precision=1), "range-comma,unit,trim", "9.5%, 10%"),
        (numeric(bounds=("20", "20"), precision=0), "range-dash,unit,trim", "20%"),
        (numeric(bounds=("20", "20"), precision=0, qualifiers=("plus",)), "unit", "20%"),
        (numeric(bounds=("20", "20"), precision=0, qualifiers=("plus",)), "unit,qual", "20%-plus"),
        (
            numeric(bounds=("9.5", "10"), precision=1, qualifiers=("about",)),
            "unit,trim,qual",
            "about 9.5–10%",
        ),
        (numeric(bounds=("9.5", "10"), precision=1), "quote", QUOTE),
    ],
)
def test_render_claim_is_byte_identical(claim: NumericClaim, style: str, expected: str) -> None:
    """Each style renders the claim's typed value exactly as the retained artifact prints it:
    the same value shows "6,591.06" in a table and "6591.06" in a trace (D7)."""
    assert render_claim(claim, parse_style(style)).encode() == expected.encode()


@pytest.mark.parametrize(
    "style", ["bogus", "group-intl,group-indian", "range-dash,range-comma", "trim,trim"]
)
def test_unknown_or_conflicting_style_is_invalid(style: str) -> None:
    """The style enum is closed: an unknown, repeated or conflicting token invalidates it."""
    with pytest.raises(DisplayError):
        parse_style(style)


def test_quote_style_needs_a_source_quote() -> None:
    """``quote`` renders a verified verbatim quote, so only a ``SOURCE_QUOTE`` claim has one."""
    with pytest.raises(DisplayError):
        render_claim(numeric("6591.06"), parse_style("quote"))


SHA = "ab" * 32


@pytest.mark.parametrize(
    ("citation", "expected"),
    [
        (
            Citation(
                kind=CitationKind.FIGURE, source_sha256=SHA, fact_origin="pilot", fact_origin_id=4
            ),
            f"[c: FIGURE source_sha256={SHA}, fact_origin=pilot, fact_origin_id=4]",
        ),
        (
            Citation(kind=CitationKind.CALCULATION, run_id=3, calculation_trace_id=9),
            "[c: CALCULATION run_id=3, calculation_trace_id=9]",
        ),
        (
            Citation(
                kind=CitationKind.SOURCE_QUOTE,
                source_sha256=SHA,
                capture_ref_id=1,
                anchor="p1.b0.0:23",
                quote=QUOTE,
            ),
            f"[c: SOURCE_QUOTE source_sha256={SHA}, capture_ref_id=1, anchor=p1.b0.0:23]",
        ),
        (
            Citation(kind=CitationKind.THESIS_CLAIM, cited_claim_id=12, cited_sealed_digest=SHA),
            f"[c: THESIS_CLAIM cited_claim_id=12, cited_sealed_digest={SHA}]",
        ),
    ],
    ids=["figure", "calculation", "source-quote", "thesis-claim"],
)
def test_ref_renders_the_claim_key_and_its_stored_citation(
    citation: Citation, expected: str
) -> None:
    """eqos-dna.1 finding 2: ``ref`` shows the claim's key, citation kind and every locator it
    stores (never the quote text), so a reader resolves the number from the narrative alone."""
    assert render_claim(numeric("6591.06", citation=citation), parse_style("ref")) == expected


def test_sections_render_into_the_narrative_and_its_hash() -> None:
    """Placeholders fill in place, sections join in ordinal order with no separator (D7) and
    the content hash is the narrative's SHA-256 (P2)."""
    claims = (numeric("6591.06", claim_key="fact.revenue", **CRORE),)
    first = ReportSection(ordinal=0, section_key="preamble", body="# Apar\n\n")
    second = ReportSection(
        ordinal=1, section_key="results", body="Revenue {{c:fact.revenue|group-intl}} crore.\n"
    )
    assert render_section(second.body, claims) == "Revenue 6,591.06 crore.\n"
    body = narrative((second, first), claims)
    assert body == b"# Apar\n\nRevenue 6,591.06 crore.\n"
    assert content_hash((second, first), claims) == hashlib.sha256(body).hexdigest()


@pytest.mark.parametrize("body", ["{{c:missing|}}", "{{c:fact.revenue|bogus}}"])
def test_unknown_claim_or_style_makes_the_section_invalid(body: str) -> None:
    """A placeholder naming no claim of the version, or an unknown style, cannot render."""
    with pytest.raises(DisplayError):
        render_section(body, (numeric("1", claim_key="fact.revenue"),))


# --- numeral and prose scans


def _never(capture_id: str, anchor: str) -> bool:
    return False


def _always(capture_id: str, anchor: str) -> bool:
    return True


STRUCTURAL = (
    "## 2. Results\n\n"
    "{{e:computed}} Run run-12 (hash 3f9a2c1d7e) for FY26_Q3 and Q1 FY27, filed 2026-07-31, "
    "falsifier F1[^1], seen at p3.b2.10:40, taxonomy id in-capmkt:Revenue; margin = PBT / revenue "
    "× 100 is {{c:calc.1|}}.\n\n"
    "{{e:inferred}} Two risks:\n1. pricing\n2. demand\n\n"
    "{{e:observed}} Management said {{c:ledger.margin|quote}}.\n"
)


@pytest.mark.parametrize(
    ("text", "resolves", "expected"),
    [
        (STRUCTURAL, _never, ()),
        (
            "{{e:computed}} Revenue grew 29.1% to {{c:fact.revenue|}}.",
            _never,
            (VersionState.UNREGISTERED_NUMBER,),
        ),
        ("{{e:computed}} Revenue was Rs 6,591 crore.", _never, (VersionState.UNREGISTERED_NUMBER,)),
        ("{{e:computed}} Revenue was INR 100000e3.", _never, (VersionState.UNREGISTERED_NUMBER,)),
        ("{{e:computed}} It was hash 100000e3.", _never, (VersionState.UNREGISTERED_NUMBER,)),
        ("{{e:computed}} Ref 3f9a2c1d7e, unlabelled.", _never, (VersionState.UNREGISTERED_NUMBER,)),
        ("{{e:computed}} Built at commit 4f0afa25cd, sha256 " + "ab12" * 16 + ".", _never, ()),
        (
            "Revenue grew {{c:cmp.revenue.yoy.pct|plus,unit}}.",
            _never,
            (VersionState.UNLABELLED_PROSE,),
        ),
        ("{{e:bogus}} Revenue grew {{c:x|}}.", _never, (VersionState.UNLABELLED_PROSE,)),
        ("{{e:observed}} Management was upbeat.", _always, (VersionState.UNCITED_PROSE,)),
        ("{{e:observed}} Management was upbeat {{s:7|p1.b0.0:10}}.", _always, ()),
        (
            "{{e:observed}} Management was upbeat {{s:7|p1.b0.0:10}}.",
            _never,
            (VersionState.UNCITED_PROSE,),
        ),
        ("{{e:opinion}} The stock looks cheap.", _never, ()),
    ],
)
def test_scan_section(text: str, resolves: Any, expected: tuple[VersionState, ...]) -> None:
    """Narrative numbers come only from claims; ids, labelled provenance hashes, ``× 100``,
    period labels, dates, footnote markers, coordinates, list numbering and quotes are
    structural; a number in scientific notation never passes as a hash. Every paragraph
    carries a class; an observed one is backed by a claim or a resolving location."""
    assert scan_section(text, resolves=resolves) == expected
