"""Upstox diagnostic statements: pinned bytes to native documents, never a vote."""

import hashlib

from fundamentals.contracts.source_catalog import surface_authority
from fundamentals.ingest.upstox_source import UpstoxFetch, UpstoxSurface
from fundamentals.ingest.upstox_statements import (
    BalanceSheetDocument,
    CashFlowDocument,
    IncomeStatementDocument,
    KeyRatiosDocument,
    StatementBasis,
    StatementPeriodicity,
    read_balance_sheet,
    read_cash_flow,
    read_income_statement,
    read_key_ratios,
)

SOURCE_ID = "upstox"
StatementDocument = (
    IncomeStatementDocument | BalanceSheetDocument | CashFlowDocument | KeyRatiosDocument
)


def read_statements(
    fetch: UpstoxFetch,
    *,
    requested_basis: StatementBasis,
    requested_periodicity: StatementPeriodicity = StatementPeriodicity.YEARLY,
) -> StatementDocument:
    """Check the captured buffer and dispatch pure readers, preserving both native blocks.

    A quarterly request never relabels the full statement's annual interval. API JSON
    digits never qualify canonical precision, identity or independently verified basis.
    """
    surface_authority(SOURCE_ID, fetch.capture.surface.value)
    if (
        hashlib.sha256(fetch.raw_body).hexdigest() != fetch.capture.content_sha256
        or len(fetch.raw_body) != fetch.capture.byte_count
    ):
        raise ValueError("Upstox body differs from its retained content pin")
    surface = fetch.capture.surface
    if surface is UpstoxSurface.INCOME_STATEMENT:
        return read_income_statement(
            fetch, requested_basis=requested_basis, requested_periodicity=requested_periodicity
        )
    if surface is UpstoxSurface.BALANCE_SHEET:
        return read_balance_sheet(fetch, requested_basis=requested_basis)
    if surface is UpstoxSurface.CASH_FLOW:
        return read_cash_flow(fetch, requested_basis=requested_basis)
    if surface is UpstoxSurface.KEY_RATIOS:
        return read_key_ratios(fetch, requested_basis=requested_basis)
    raise ValueError("Upstox retained response is not a supported financial diagnostic surface")
