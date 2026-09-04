"""The nested ``showSchedule`` call, read as the whole address it is.

The acceptance suite covers the calls that name the wrong row or the wrong
section. This pins the other refusal on the same path: a value under
``isExpandable`` that is not a ``showSchedule`` call at all. The pattern is
anchored at both ends on purpose — a call this contract cannot read whole is a
call it cannot turn into a request, and guessing at the readable part would
spend a rate-limited fetch on an address the site never named.
"""

from __future__ import annotations

import pytest

from fundamentals.ingest.screener_financials_models import Section
from fundamentals.ingest.screener_financials_nested import nested_call_defect

_LABEL = "Trade receivables"


@pytest.mark.parametrize(
    "call",
    [
        "",
        "Company.showSchedule('Trade receivables', 'balance-sheet', this)",
        'Company.showSchedule("Trade receivables", "balance-sheet")',
        'window.open("Trade receivables", "balance-sheet", this)',
        'Company.showSchedule("Trade receivables", "balance-sheet", this); steal()',
    ],
)
def test_a_value_that_is_not_a_show_schedule_call_is_refused_not_guessed_at(call: str) -> None:
    """Every one of these carries the right label somewhere and is still refused."""
    defect = nested_call_defect(call, label=_LABEL, section=Section.BALANCE_SHEET)
    assert defect is not None
    assert repr(call) in defect


def test_the_call_that_names_this_row_and_this_section_is_followed() -> None:
    """The one shape a live capture recorded is the only one that passes."""
    call = f'Company.showSchedule("{_LABEL}", "balance-sheet", this)'
    assert nested_call_defect(call, label=_LABEL, section=Section.BALANCE_SHEET) is None
