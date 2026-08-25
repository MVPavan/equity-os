"""Coverage for the shared Tijori JSON-island loader.

The loader is the one seam every Tijori surface (financials, shareholding,
overview) collects its islands through, so the repeated-island rule is pinned
here rather than in any one surface's tests.
"""

from __future__ import annotations

import pytest

from fundamentals.ingest.tijori_page import collect_islands
from fundamentals.ingest.tijori_tables import TijoriParseError, TijoriUnparseableIsland

_ISLAND = "is_auth"
_OPTIONAL_ISLAND = "plan_details"


def _page(*bodies: tuple[str, str]) -> str:
    """Render a minimal page carrying the given ``(island_id, body)`` scripts."""
    scripts = "\n".join(
        f'<script id="{island_id}" type="application/json">{body}</script>'
        for island_id, body in bodies
    )
    return f"<!doctype html><html><body>{scripts}</body></html>"


def test_single_island_is_loaded() -> None:
    """The ordinary one-occurrence case is unaffected by the repeat rule."""
    islands = collect_islands(_page((_ISLAND, "true")), required_islands=(_ISLAND,))

    assert islands[_ISLAND] is True


def test_identical_repeat_collapses_to_one_value() -> None:
    """A template that renders one island twice with the same body is not ambiguous.

    FACT (live overview page, 2026-08-25): ``is_auth`` and ``plan_details`` are
    each rendered in two layout contexts with byte-identical bodies. Refusing
    that page would reject a well-formed response over a layout detail.
    """
    document = _page((_ISLAND, "true"), (_ISLAND, "true"))

    islands = collect_islands(document, required_islands=(_ISLAND,))

    assert islands[_ISLAND] is True


def test_repeat_that_differs_only_in_surrounding_whitespace_collapses() -> None:
    """Bodies are compared after stripping, because layout indents the script body."""
    document = _page((_ISLAND, "true"), (_ISLAND, "\n      true\n    "))

    islands = collect_islands(document, required_islands=(_ISLAND,))

    assert islands[_ISLAND] is True


def test_repeat_with_differing_content_stays_fatal_and_names_the_island() -> None:
    """Two islands that disagree cannot be resolved to one value by any rule."""
    document = _page((_ISLAND, "true"), (_ISLAND, "false"))

    with pytest.raises(
        TijoriParseError,
        match=r"tijori JSON island 'is_auth' appears multiple times with differing content",
    ):
        collect_islands(document, required_islands=(_ISLAND,))


def test_optional_island_repeat_with_differing_content_is_also_fatal() -> None:
    """Optionality tolerates an absent or undecodable island, never a contradictory one."""
    document = _page(
        (_ISLAND, "true"),
        (_OPTIONAL_ISLAND, '{"plan_tier": "free"}'),
        (_OPTIONAL_ISLAND, '{"plan_tier": "pro"}'),
    )

    with pytest.raises(TijoriParseError, match=r"'plan_details' appears multiple times"):
        collect_islands(document, required_islands=(_ISLAND,), optional_islands=(_OPTIONAL_ISLAND,))


def test_optional_island_repeat_with_identical_content_collapses() -> None:
    """The tolerance applies to optional islands on the same terms as required ones."""
    body = '{"plan_tier": "free"}'
    document = _page((_ISLAND, "true"), (_OPTIONAL_ISLAND, body), (_OPTIONAL_ISLAND, body))

    islands = collect_islands(
        document, required_islands=(_ISLAND,), optional_islands=(_OPTIONAL_ISLAND,)
    )

    assert islands[_OPTIONAL_ISLAND] == {"plan_tier": "free"}


def test_missing_required_island_is_still_fatal() -> None:
    """The repeat rule must not weaken the required-island contract."""
    with pytest.raises(TijoriParseError, match="is missing"):
        collect_islands(_page((_OPTIONAL_ISLAND, "{}")), required_islands=(_ISLAND,))


def test_unparseable_optional_island_is_still_quarantined_not_raised() -> None:
    """An undecodable optional island keeps its existing typed outcome."""
    document = _page((_ISLAND, "true"), (_OPTIONAL_ISLAND, "{not json,}"))

    islands = collect_islands(
        document, required_islands=(_ISLAND,), optional_islands=(_OPTIONAL_ISLAND,)
    )

    assert isinstance(islands[_OPTIONAL_ISLAND], TijoriUnparseableIsland)
