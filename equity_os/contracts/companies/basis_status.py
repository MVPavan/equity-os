"""Which statement bases an entity files, as evidenced identity input states it."""

from __future__ import annotations

from enum import StrEnum


class BasisStatus(StrEnum):
    """Whether an entity files consolidated statements at all.

    Always read from evidenced identity input, never from a filing's own basis
    declaration: applicability uses it to tell ``NOT_APPLICABLE`` from a missing
    source.
    """

    CONSOLIDATED_AND_STANDALONE = "CONSOLIDATED_AND_STANDALONE"
    STANDALONE_ONLY = "STANDALONE_ONLY"
