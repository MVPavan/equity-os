"""``CONFIG_PIN`` must be structurally constrained like every other anchor (A16).

Amendment A5 stated what a config pin addresses — ``row_label`` is the stock's
NSE symbol as the config spells it, ``column_label`` is the identifier field —
and for one round nothing enforced it. A pin could be constructed with neither,
or carrying a page number, an island id or a CSV row position it had never read.
That is the SL4-27 defect class: an anchor whose typed fields claim a retrieval
procedure the value did not come from, which is precisely the difference the
typed-anchor design exists to preserve.

The accepting construction is asserted first in every test below, so a validator
that simply refused every ``CONFIG_PIN`` could not pass any of them.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from fundamentals.contracts.provenance import Provenance, SourceAnchorType

_SOURCE_ID = "watchlist-config"
_SHA256 = "0" * 64
_SYMBOL = "FIXTUREFX"
_FIELD = "bse_scrip"
_RETRIEVED_AT = datetime(2026, 9, 3, 6, 0, tzinfo=UTC)

# One value per locator that belongs to some other retrieval procedure. Zero is
# used for the two integer positions deliberately: it is falsy, and a guard
# written with ``if getattr(...)`` rather than ``is not None`` would let it
# through while passing every other row.
_FOREIGN_LOCATORS: tuple[tuple[str, object], ...] = (
    ("page", 3),
    ("block", 0),
    ("span", "1-4"),
    ("context_ref", "ctx-Q3FY25"),
    ("island_id", "company-info"),
    ("document_id", "api:cash_flow"),
    ("table_key", "1yr"),
    ("table_id", "watchlist-export"),
    ("row_path", "0"),
    ("column_index", 0),
)


def _config_pin(**overrides: Any) -> Provenance:
    """A well-formed config pin, with the named fields overridden."""
    fields: dict[str, Any] = {
        "source_id": _SOURCE_ID,
        "file_sha256": _SHA256,
        "anchor_type": SourceAnchorType.CONFIG_PIN,
        "row_label": _SYMBOL,
        "column_label": _FIELD,
        "retrieved_at": _RETRIEVED_AT,
    }
    fields.update(overrides)
    return Provenance(**fields)


def test_a_well_formed_config_pin_addresses_the_symbol_and_the_field() -> None:
    """A5: the pin a reader follows back to one line of the committed YAML.

    This is the control for every refusal below. Without it, a validator that
    rejected ``CONFIG_PIN`` outright — or that had quietly been dropped from the
    enum — would satisfy all three refusal tests and leave the S2 adapter unable
    to record provenance at all.
    """
    pin = _config_pin()

    assert pin.anchor_type is SourceAnchorType.CONFIG_PIN
    assert pin.row_label == _SYMBOL
    assert pin.column_label == _FIELD


@pytest.mark.parametrize("field", ["row_label", "column_label"])
@pytest.mark.parametrize("value", [None, "", "   "])
def test_a_config_pin_missing_either_location_field_is_refused(
    field: str, value: str | None
) -> None:
    """A16: both location fields are required, and blank is not "set".

    Either one alone is useless: a symbol without a field name does not say
    which identifier was pinned, and a field name without a symbol does not say
    for which stock. Whitespace is included because a config edit that blanked a
    value would otherwise produce an anchor that passes a null check and still
    addresses nothing.
    """
    assert _config_pin(**{field: "kept"}).anchor_type is SourceAnchorType.CONFIG_PIN

    with pytest.raises(ValidationError, match="CONFIG_PIN"):
        _config_pin(**{field: value})


@pytest.mark.parametrize(("field", "value"), _FOREIGN_LOCATORS)
def test_a_config_pin_carrying_a_foreign_locator_is_refused(field: str, value: object) -> None:
    """A16: a config pin names no fetched document, so it may address none.

    A hand-typed YAML value has no page, no island, no request URL and no export
    row. An anchor carrying one of those reads as a different retrieval
    procedure to anything that switches on the typed fields rather than on the
    discriminant — the exact ambiguity ``_reject_foreign_fields`` was written to
    stop for the other anchor kinds. Each locator is asserted separately because
    a table listing nine of the ten would pass a test that checked only one.
    """
    assert getattr(_config_pin(), field) is None

    with pytest.raises(ValidationError, match=field):
        _config_pin(**{field: value})
