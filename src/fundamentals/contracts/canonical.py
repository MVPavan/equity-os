"""Shared enums of the canonical dictionary, measurement keys and applicability (spec §1, §4)."""

from __future__ import annotations

from enum import StrEnum


class StatementFamily(StrEnum):
    """Which statement a canonical row belongs to; ``DERIVED`` rows carry a formula."""

    PL = "PL"
    BALANCE_SHEET = "BALANCE_SHEET"
    CASH_FLOW = "CASH_FLOW"
    SEGMENT = "SEGMENT"
    SHAREHOLDING = "SHAREHOLDING"
    DERIVED = "DERIVED"


class ValueKind(StrEnum):
    """Canonical unit family of a value; kinds are never interconverted implicitly."""

    CURRENCY_AMOUNT = "CURRENCY_AMOUNT"
    PER_SHARE_AMOUNT = "PER_SHARE_AMOUNT"
    COUNT = "COUNT"
    PERCENTAGE = "PERCENTAGE"
    RATIO = "RATIO"
    DAYS = "DAYS"


class PeriodNature(StrEnum):
    """Whether a row measures over an interval or at an instant."""

    DURATION = "DURATION"
    INSTANT = "INSTANT"


class Basis(StrEnum):
    """Statement basis of a measurement; standalone is never compared as consolidated."""

    CONSOLIDATED = "CONSOLIDATED"
    STANDALONE = "STANDALONE"


class PeriodKind(StrEnum):
    """Period kind, always derived from the interval and never from a label."""

    QUARTER = "QUARTER"
    HALF_YEAR = "HALF_YEAR"
    NINE_MONTH = "NINE_MONTH"
    YEAR = "YEAR"
    TTM = "TTM"
    INSTANT = "INSTANT"
    OTHER = "OTHER"


class TemporalRole(StrEnum):
    """How a formula operand's period relates to the output period."""

    DURATION = "DURATION"
    CLOSING = "CLOSING"
    OPENING = "OPENING"
    AVERAGE = "AVERAGE"


class ApplicabilityStatus(StrEnum):
    """Whether a row applies to a context, decided before any value is examined."""

    APPLICABLE = "APPLICABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ValueIdentity(StrEnum):
    """Whether a value was reported by a source or derived by a registered formula."""

    REPORTED = "REPORTED"
    DERIVED = "DERIVED"


class DocumentType(StrEnum):
    """Which kind of exchange filing a package is."""

    FINANCIAL_RESULTS = "FINANCIAL_RESULTS"
    SHAREHOLDING_PATTERN = "SHAREHOLDING_PATTERN"


class ReportingRegime(StrEnum):
    """Regulation the filing is made under."""

    IN_LODR = "IN_LODR"


class Representation(StrEnum):
    """First-party representation of one filing."""

    XBRL = "XBRL"
    PDF = "PDF"
    HTML = "HTML"
    JSON = "JSON"


FIRST_PARTY_REPRESENTATIONS = (Representation.XBRL, Representation.PDF)
