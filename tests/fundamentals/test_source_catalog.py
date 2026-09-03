"""Source classification must be declared, never inferred, and must fail closed.

Regression cover for eqos-pyr. ``classify_source`` previously marked a source
DERIVED only when its ``source_id`` contained ``screener`` or ``tijori``; every
other id — including one never registered anywhere — fell through to
FIRST_PARTY, the highest authority the system has. Authority granted by a
substring default is the defect these tests encode.

The invariant: a source's class is a property the source *declares*, and an
undeclared source is refused rather than promoted.
"""

from __future__ import annotations

import pytest

from fundamentals.contracts.source_catalog import (
    BUILTIN_SOURCES,
    EvidenceRole,
    SourceCatalog,
    SourceClass,
    SourceDescriptor,
    UnknownSourceError,
)

# The source proven non-independent of Screener (see eqos-0j6). It matches no
# builtin marker, which is precisely why the old substring rule promoted it.
UPSTOX = "upstox"
UPSTOX_FUNDAMENTALS = "upstox-fundamentals"


def test_unknown_source_id_fails_closed_rather_than_defaulting_to_first_party() -> None:
    """An id nobody declared must raise, not inherit first-party authority."""
    with pytest.raises(UnknownSourceError):
        BUILTIN_SOURCES.describe("a-source-nobody-declared")


@pytest.mark.parametrize("source_id", [UPSTOX, UPSTOX_FUNDAMENTALS])
def test_upstox_source_ids_are_never_classified_first_party(source_id: str) -> None:
    """Upstox is the one source proven non-independent; it may never outrank a filing.

    Either it is undeclared (refused) or declared derived. It is never first-party.
    """
    try:
        descriptor = BUILTIN_SOURCES.describe(source_id)
    except UnknownSourceError:
        return
    assert descriptor.source_class is SourceClass.DERIVED


def test_a_declared_source_resolves_to_its_declared_class() -> None:
    """Classification comes from the declaration, not from the shape of the id."""
    catalog = SourceCatalog.of(
        SourceDescriptor(
            source_id="infy-q1-fy25-results-pdf",
            source_class=SourceClass.FIRST_PARTY,
            evidence_role=EvidenceRole.RECONCILABLE,
        )
    )
    assert catalog.describe("infy-q1-fy25-results-pdf").source_class is SourceClass.FIRST_PARTY


def test_classification_is_not_inferred_from_the_id_text() -> None:
    """A source may be declared derived without its id containing any marker word.

    The old rule could not express this: 'moneycontrol' has no marker substring,
    so it was first-party no matter what it actually is.
    """
    catalog = SourceCatalog.of(
        SourceDescriptor(
            source_id="moneycontrol",
            source_class=SourceClass.DERIVED,
            evidence_role=EvidenceRole.RECONCILABLE,
        )
    )
    assert catalog.describe("moneycontrol").source_class is SourceClass.DERIVED


def test_a_diagnostic_only_source_is_never_reconcilable() -> None:
    """DIAGNOSTIC_ONLY is the typed bar for Lane B; it must be expressible."""
    descriptor = SourceDescriptor(
        source_id="upstox-crosscheck",
        source_class=SourceClass.DERIVED,
        evidence_role=EvidenceRole.DIAGNOSTIC_ONLY,
    )
    assert descriptor.evidence_role is EvidenceRole.DIAGNOSTIC_ONLY
    assert not descriptor.may_reconcile


def test_builtin_first_party_sources_are_filings_only() -> None:
    """Only genuine filings and issuer documents carry first-party authority."""
    first_party = {
        d.source_id for d in BUILTIN_SOURCES.entries if d.source_class is SourceClass.FIRST_PARTY
    }
    assert "screener" not in first_party
    assert "tijori" not in first_party
    assert "bse-xbrl" in first_party
