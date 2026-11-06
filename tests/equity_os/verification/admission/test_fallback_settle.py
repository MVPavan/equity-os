"""How the fallback settles one original trigger cell against its rerun row (spec §6.8 step 5).

Unit cases at the classification boundary: a row holding only what ``settle`` reads, and the
rerun's admission outcome. ``NOT_DISCLOSED`` needs a read filing and no value on any side; a
failed, invalid, zero or constructed vendor value, an unread vendor or a missing package is not
absence, and an open review or failed filing is never replaced.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from equity_os.contracts.measurement.canonical import (
    ApplicabilityStatus,
    Basis,
    Representation,
    ValueKind,
)
from equity_os.contracts.measurement.measurement_key import (
    DimensionSet,
    MeasurementKey,
    PeriodInterval,
)
from equity_os.contracts.measurement.observation import AccountingFramework
from equity_os.contracts.sourcing.source_catalog import SCREENER_PAGE, TIJORI_PAGE
from equity_os.contracts.verification.comparison import SourceRole, SourceState
from equity_os.contracts.verification.vendor_first import FilingFailure
from equity_os.verification.admission.admission import (
    TRIGGERS,
    AdmissionOutcome,
    AdmissionRecord,
    AdmissionRefusal,
)
from equity_os.verification.admission.fallback import settle
from equity_os.verification.comparison.run_models import ResultRow, SourceValue
from equity_os.verification.comparison.selection import NO_ELIGIBLE_PACKAGE

ROW_ID = "r1"
KEY = MeasurementKey(
    entity_id=1,
    canonical_id="biological_assets",
    period=PeriodInterval(instant=date(2025, 9, 30)),
    basis=Basis.CONSOLIDATED,
    framework=AccountingFramework.IND_AS,
    currency="INR",
    value_kind=ValueKind.CURRENCY_AMOUNT,
    dimensions=DimensionSet(),
)
RULE = "results.annual_disclosure"


def _side(
    page: tuple[str, str] | None,
    state: SourceState = SourceState.NO_VALUE,
    value: str | None = None,
    *,
    reason: str | None = None,
    trace: int | None = None,
) -> SourceValue:
    """A first-party XBRL side (``page`` ``None``) or a vendor page's side."""
    number = None if value is None else Decimal(value)
    vendor = page is not None and state is SourceState.VALUE
    return SourceValue(
        source_role=SourceRole.FIRST_PARTY if page is None else SourceRole.INDEPENDENT_VENDOR,
        representation=Representation.XBRL if page is None else Representation.HTML,
        source_id=None if page is None else page[0],
        surface=None if page is None else page[1],
        state=state,
        reason=reason,
        value=number,
        lower=number,
        upper=number,
        interpretation_id=1 if vendor and trace is None else None,
        calculation_trace_id=trace,
        attempt_id=None,
        calculation_state=None,
    )


def _row(*values: SourceValue, applicable: bool = True) -> ResultRow:
    """A rerun row of ``KEY`` holding only what ``settle`` reads."""
    status = ApplicabilityStatus.APPLICABLE if applicable else ApplicabilityStatus.NOT_APPLICABLE
    return ResultRow.model_construct(
        row_id=ROW_ID,
        key=KEY,
        applicability=status,
        applicability_rule_id=RULE,
        source_values=values,
    )


def _admitted(
    refusal: AdmissionRefusal | None,
    failure: FilingFailure | None = None,
    admission: int | None = None,
) -> AdmissionOutcome:
    """The rerun's admission outcome for the one row: refused, or admitted as ``admission``."""
    records = ()
    if admission is not None:
        records = (
            AdmissionRecord.model_construct(admission_id=admission, key_digest=KEY.digest()),
        )
    return AdmissionOutcome(
        records=records,
        refusals=() if refusal is None else ((ROW_ID, refusal),),
        filing_failures=() if failure is None else ((ROW_ID, failure),),
        triggers=(),
        created=0,
    )


ABSENT = (_side(None), _side(SCREENER_PAGE))
UNMAPPED = _admitted(AdmissionRefusal.VENDOR_UNMAPPED)


@pytest.mark.parametrize(
    ("row", "admitted", "read", "expected"),
    [
        (None, UNMAPPED, True, ("RERUN_ROW_MISSING", None)),
        (
            _row(_side(None, SourceState.VALUE, "5")),
            _admitted(None, admission=7),
            True,
            ("ADMITTED", 7),
        ),
        (_row(applicable=False), UNMAPPED, True, ("NOT_APPLICABLE", RULE)),
        (_row(*ABSENT), UNMAPPED, True, ("NOT_DISCLOSED", None)),
        (_row(_side(None)), UNMAPPED, True, ("NOT_DISCLOSED", None)),
        # Review and a failed filing take precedence over every fallback-only disposition.
        (_row(*ABSENT), _admitted(AdmissionRefusal.REVIEW_OPEN), True, ("REVIEW_OPEN", None)),
        (
            _row(applicable=False),
            _admitted(AdmissionRefusal.REVIEW_OPEN),
            True,
            ("REVIEW_OPEN", None),
        ),
        (
            _row(_side(None, SourceState.VALUE, "5")),
            _admitted(AdmissionRefusal.FILING_UNRESOLVED, FilingFailure.EXTRACTION_NOT_AGREE),
            True,
            ("FILING_UNRESOLVED", "EXTRACTION_NOT_AGREE"),
        ),
        # Not absence: an unread vendor, a failed, invalid, zero or constructed vendor value, no
        # package, or no first-party side at all.
        (_row(*ABSENT), UNMAPPED, False, ("VENDOR_UNMAPPED", None)),
        (
            _row(_side(None), _side(TIJORI_PAGE, SourceState.UNAVAILABLE)),
            UNMAPPED,
            True,
            ("VENDOR_UNMAPPED", None),
        ),
        (
            _row(_side(None), _side(TIJORI_PAGE, SourceState.INVALID)),
            UNMAPPED,
            True,
            ("VENDOR_UNMAPPED", None),
        ),
        (
            _row(_side(None), _side(TIJORI_PAGE, SourceState.VALUE, "0")),
            UNMAPPED,
            True,
            ("VENDOR_UNMAPPED", None),
        ),
        (
            _row(_side(None), _side(TIJORI_PAGE, SourceState.VALUE, "9", trace=3)),
            UNMAPPED,
            True,
            ("VENDOR_UNMAPPED", None),
        ),
        (_row(_side(None, reason=NO_ELIGIBLE_PACKAGE)), UNMAPPED, True, ("VENDOR_UNMAPPED", None)),
        (_row(_side(SCREENER_PAGE)), UNMAPPED, True, ("VENDOR_UNMAPPED", None)),
        # A disagreeing or imprecise pair has values; it is never absence.
        (
            _row(*ABSENT),
            _admitted(AdmissionRefusal.VENDORS_DISAGREE),
            True,
            ("VENDORS_DISAGREE", None),
        ),
    ],
    ids=[
        "missing-row",
        "admitted",
        "not-applicable",
        "not-disclosed",
        "not-disclosed-unmapped-vendors",
        "review-over-absent",
        "review-over-not-applicable",
        "filing-unresolved",
        "vendor-unread",
        "vendor-unavailable",
        "vendor-invalid",
        "vendor-zero",
        "vendor-constructed",
        "no-package",
        "no-first-party",
        "disagree",
    ],
)
def test_settle(
    row: ResultRow | None,
    admitted: AdmissionOutcome,
    read: bool,
    expected: tuple[str, str | int | None],
) -> None:
    """Each original trigger is admitted, settled or still refused for its stated reason."""
    assert settle(row, admitted, read) == expected


def test_triggers_are_rows_4_and_6() -> None:
    """The one exported trigger set: rows 4 and 6 of §6.5, without the queue's two refusals."""
    assert TRIGGERS == {
        AdmissionRefusal.CHECK_REQUIRED,
        AdmissionRefusal.VENDOR_UNMAPPED,
        AdmissionRefusal.VENDORS_DISAGREE,
        AdmissionRefusal.VENDORS_IMPRECISE,
    }
