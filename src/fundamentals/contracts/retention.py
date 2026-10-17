"""Retention vocabulary shared by SQL, the store and the CLI (plan D9 R2, R3, R6)."""

from __future__ import annotations

from enum import StrEnum


class RetentionClass(StrEnum):
    """A capture's retention class, as ``eqos.base_class`` assigns it (R2)."""

    VENDOR = "VENDOR"
    IDENTITY = "IDENTITY"
    EXCHANGE_REFETCHABLE = "EXCHANGE_REFETCHABLE"
    COVERED = "COVERED"
    UNCLASSIFIED = "UNCLASSIFIED"


class RefusalCode(StrEnum):
    """The prefix of a retention refusal raised by the database (RP3)."""

    BEYOND_AUTHORITY = "BEYOND_AUTHORITY"
