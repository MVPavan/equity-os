"""Shared comparison enums: source states, calculation states and selection sources (spec §5)."""

from __future__ import annotations

from enum import StrEnum


class SourceState(StrEnum):
    """One source's state for a cell (data spec §5 source states)."""

    VALUE = "VALUE"
    NO_VALUE = "NO_VALUE"
    UNAVAILABLE = "UNAVAILABLE"
    INVALID = "INVALID"


class CalculationState(StrEnum):
    """How a derived side's evaluation ended; first matching row of the spec table wins."""

    OPERAND_UNAVAILABLE = "OPERAND_UNAVAILABLE"
    OPERAND_INVALID = "OPERAND_INVALID"
    OPERAND_MISSING = "OPERAND_MISSING"
    REVISION_INCOMPATIBLE = "REVISION_INCOMPATIBLE"
    UNDEFINED = "UNDEFINED"
    COMPUTED = "COMPUTED"


class SelectionSource(StrEnum):
    """Which selection rule supplied an operand value (recorded on every trace operand)."""

    PACKAGE_AS_REPORTED = "PACKAGE_AS_REPORTED"
    PACKAGE_OPENING_DISCLOSURE = "PACKAGE_OPENING_DISCLOSURE"
    INSTANT_OWN_SELECTION = "INSTANT_OWN_SELECTION"
    HISTORICAL_PACKAGE = "HISTORICAL_PACKAGE"
