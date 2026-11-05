"""Period and quarter enumerations for the Fundamentals product.

Two distinct notions of "quarter" must never be conflated:

* :class:`ProgramQuarter` — the position within the Phase 0.5 four-quarter
  vertical-slice experiment (Quarter 0 manual baseline plus three assisted
  updates).
* :class:`IssuerQuarter` — the issuer's own fiscal quarter (Infosys reports on
  an April–March fiscal year).
"""

from __future__ import annotations

from enum import StrEnum


class ProgramQuarter(StrEnum):
    """Position within the Phase 0.5 four-quarter vertical-slice experiment."""

    QUARTER_0 = "QUARTER_0"
    QUARTER_1 = "QUARTER_1"
    QUARTER_2 = "QUARTER_2"
    QUARTER_3 = "QUARTER_3"


class IssuerQuarter(StrEnum):
    """Issuer fiscal quarter (April–March fiscal year) for the INFY pilot."""

    FY24_Q1 = "FY24_Q1"
    FY25_Q1 = "FY25_Q1"
    FY25_Q2 = "FY25_Q2"
    FY25_Q3 = "FY25_Q3"
    FY25_Q4 = "FY25_Q4"
