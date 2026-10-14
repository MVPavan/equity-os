"""PREP-1: Apar Q4 FY26 and Q1 FY27 (SEBI in-capmkt 2026-01-31) extract under mapping set v5.

Mapping set v4 refuses both instances as ``UNSUPPORTED_SCHEMA``, and the Q4 FY26 results PDF prints
its P&L unit as "(Rs. in crams)", which left every P&L row unit-less and INVALID. Headline values
must equal the lexemes filed in the retained XBRL bytes; the Q4 PDF revenue must agree with them.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from evidence_support import (
    BOTH,
    CONFIG,
    XBRL_KIND,
    Ingest,
    ingest,
    one,
    policy,
)
from lxml import etree
from retained_support import apar_catalog, apar_intake, apar_original

from fundamentals.api.config import load_config
from fundamentals.canon.dictionary import CanonicalDictionary, load_dictionary
from fundamentals.contracts.acquisition_outcome import ExtractionOutcome
from fundamentals.contracts.canonical import Representation
from fundamentals.contracts.evidence import InterpretationStatus
from fundamentals.contracts.measurement_key import PeriodInterval
from fundamentals.contracts.source_catalog import EvidenceRole, SourceClass, SourceDescriptor
from fundamentals.evidence.mapping import MappingSet, load_mapping_set
from fundamentals.extract.pdf_statement_pages import specs_from_config

__all__ = ["ingest", "policy"]

pytestmark = [pytest.mark.pg, pytest.mark.retained]

CAPMKT_2026 = "http://www.sebi.gov.in/xbrl/2026-01-31/in-capmkt"
HEADLINES = (
    ("revenue_from_operations", "RevenueFromOperations"),
    ("profit_before_tax", "ProfitBeforeTax"),
    ("profit_for_period", "ProfitLossForPeriod"),
    ("eps_basic", "BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations"),
)
# (quarter, quarter start, quarter end, whether the instance files a balance sheet)
QUARTERS = (
    ("FY26_Q4", date(2026, 1, 1), date(2026, 3, 31), True),
    ("FY27_Q1", date(2026, 4, 1), date(2026, 6, 30), False),
)


@pytest.fixture(scope="module")
def dictionary() -> CanonicalDictionary:
    """Canonical dictionary v2."""
    return load_dictionary(CONFIG / "dictionary", "v2")


@pytest.fixture(scope="module")
def mapping_set(dictionary: CanonicalDictionary) -> MappingSet:
    """Mapping set v5."""
    return load_mapping_set(CONFIG / "mappings", "v5", dictionary=dictionary)


def _filed(quarter: str, element: str, context: str) -> Decimal:
    """The lexeme filed for one element in one context, read from the retained bytes."""
    root = etree.parse(str(apar_original(quarter, XBRL_KIND))).getroot()
    tag = f"{{{CAPMKT_2026}}}{element}"
    (text,) = [fact.text for fact in root.iter(tag) if fact.get("contextRef") == context]
    return Decimal(text)


@pytest.mark.parametrize(("quarter", "start", "end", "has_balance_sheet"), QUARTERS)
def test_2026_taxonomy_extracts_filed_values(
    ingest: Ingest, quarter: str, start: date, end: date, has_balance_sheet: bool
) -> None:
    """No UNSUPPORTED_SCHEMA; headline XBRL rows equal the filed lexemes; Q4 PDF revenue agrees."""
    issuer = CONFIG / f"aparinds-{quarter.lower().replace('_', '-')}.yaml"
    loaded = load_config(issuer)
    catalog = apar_catalog().extend(
        SourceDescriptor(
            source_id=loaded.results_pdf.source_id,
            source_class=SourceClass.FIRST_PARTY,
            evidence_role=EvidenceRole.RECONCILABLE,
        )
    )
    intake = apar_intake(ingest.tmp_path, quarter, BOTH, issuer_config=issuer)
    report = ingest.run(intake, end, catalog=catalog, pdf_specs=specs_from_config(loaded.pdf_parse))
    assert report.attempts
    assert all(a.outcome is not ExtractionOutcome.UNSUPPORTED_SCHEMA for a in report.attempts)
    rows = ingest.interpretations(report)
    period = PeriodInterval.duration(start, end)
    expected = [(cid, element, "OneD", period) for cid, element in HEADLINES]
    if has_balance_sheet:
        expected.append(("total_assets", "Assets", "OneI", PeriodInterval.at(end)))
    for canonical_id, element, context, key_period in expected:
        xbrl = one(rows, canonical_id, key_period, Representation.XBRL)
        assert xbrl.status is InterpretationStatus.MAPPED, canonical_id
        assert xbrl.value == _filed(quarter, element, context), canonical_id
    if quarter == "FY26_Q4":
        pdf = one(rows, "revenue_from_operations", period, Representation.PDF)
        assert pdf.status is InterpretationStatus.MAPPED
        assert pdf.value == _filed(quarter, "RevenueFromOperations", "OneD")
