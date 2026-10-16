"""Settings an onboarded issuer derives from its verified discovery evidence (plan D6 D5).

``derive`` reads only the anchors discovery verified: the filing window of the two NSE listings
(basis status, D4.2 step 2) and the two qualifying consolidated XBRL instances (fiscal year end,
rounding level, presentation currency, framework, document location). Each value becomes one
row citing its unit's ``DISCOVERY`` input, valid from the earliest period end among the filings
declaring it (C4), so a later change of value governs only the periods it was declared for.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import date, datetime
from typing import Any, LiteralString

import psycopg
from lxml import etree  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.basis_status import BasisStatus
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.contracts.onboarding import ANCHOR_UNITS, VerificationState, VerificationUnit
from fundamentals.contracts.source_catalog import (
    NSE_INTEGRATED_LISTING,
    NSE_MASTER,
    NSE_RESULTS_LISTING,
    NSE_XBRL_INSTANCE,
)
from fundamentals.entity.discovery import FILINGS_CHECKED, Discovery, as_of_for
from fundamentals.entity.verification import financial_rule
from fundamentals.evidence import repository_rows as rows_sql
from fundamentals.ingest.nse_filings import filing_window, listing_rows
from fundamentals.pg.identity_seed import SettingKey

FISCAL_YEAR_END = "DateOfEndOfFinancialYear"
ROUNDING_LEVEL = "LevelOfRounding"
PRESENTATION_CURRENCY = "DescriptionOfPresentationCurrency"
_NOT_VERIFIED = "settings derive only from verified anchors; {unit} is {state}"
_NOT_ONE = "{name}: {count} distinct values in {url}"
_NOT_IND_AS = "{url} is not an Ind AS in-capmkt filing"


class DerivedSettingsError(ValueError):
    """The verified evidence does not determine a setting: nothing is derived."""


class Filing(BaseModel):
    """One verified consolidated filing: its period, NSE filed-at time and instance."""

    model_config = ConfigDict(frozen=True)

    period_end: date
    filed_at: datetime
    url: str
    body: bytes
    retrieved_at: datetime


class DerivedSetting(BaseModel):
    """One derived value and the unit whose ``DISCOVERY`` input it cites."""

    model_config = ConfigDict(frozen=True)

    key: SettingKey
    value: str
    valid_from: date
    unit: VerificationUnit


class DerivedSettings(BaseModel):
    """Basis status and settings, with the verified filings (latest period first)."""

    model_config = ConfigDict(frozen=True)

    basis_status: BasisStatus
    filings: tuple[Filing, ...]
    settings: tuple[DerivedSetting, ...]

    def value(self, key: SettingKey, period_end: date) -> str:
        """The value governing ``period_end`` (latest ``valid_from`` on or before it)."""
        rows = [s for s in self.settings if s.key is key and s.valid_from <= period_end]
        return max(rows, key=lambda s: s.valid_from).value


def derive(found: Discovery) -> DerivedSettings:
    """Every D5 setting of a discovery whose anchors verified."""
    for unit in ANCHOR_UNITS:
        state = found.states[unit][0]
        if state is not VerificationState.VERIFIED:
            raise DerivedSettingsError(_NOT_VERIFIED.format(unit=unit.value, state=state.value))
    bodies = {(c.request.source_id, c.request.surface): c for c in found.captures}
    window = filing_window(
        listing_rows(
            bodies[NSE_RESULTS_LISTING].response.body or b"",
            bodies[NSE_INTEGRATED_LISTING].response.body or b"",
        ),
        as_of_for(bodies[NSE_MASTER].response.retrieved_at),
    )
    instances = {
        c.request.url: c
        for c in found.captures
        if (c.request.source_id, c.request.surface) == NSE_XBRL_INSTANCE
    }
    filings = []
    for row in window.filings[:FILINGS_CHECKED]:
        capture = instances[row.xbrl_url or ""]
        assert row.broadcast is not None and capture.response.body is not None
        filings.append(
            Filing(
                period_end=row.period_end,
                filed_at=row.broadcast,
                url=capture.request.url,
                body=capture.response.body,
                retrieved_at=capture.response.retrieved_at,
            )
        )
    declared: dict[tuple[SettingKey, str], date] = {}
    for filing in filings:
        for key, value in _declared(filing).items():
            start = declared.get((key, value), filing.period_end)
            declared[key, value] = min(start, filing.period_end)
    latest = filings[0]
    location = json.dumps(
        {"url": latest.url, "sha256": hashlib.sha256(latest.body).hexdigest()}, sort_keys=True
    )
    declared[SettingKey.DOCUMENT_LOCATION, location] = latest.period_end
    return DerivedSettings(
        basis_status=BasisStatus.CONSOLIDATED_AND_STANDALONE,  # discovery refused any other
        filings=tuple(filings),
        settings=tuple(
            DerivedSetting(
                key=key, value=value, valid_from=start, unit=VerificationUnit.XBRL_ENTITY
            )
            for (key, value), start in sorted(declared.items(), key=lambda item: item[0])
        ),
    )


def write(
    conn: psycopg.Connection[Any],
    entity_id: int,
    derived: DerivedSettings,
    inputs: Mapping[VerificationUnit, int],
) -> None:
    """Record the basis status and every setting, each citing its unit's input (idempotent)."""
    with conn.transaction():
        conn.execute(
            _INSERT_BASIS,
            (entity_id, derived.basis_status.value, inputs[VerificationUnit.EXCHANGE]),
        )
        for item in derived.settings:
            conn.execute(
                rows_sql.INSERT_SETTING,
                (entity_id, item.key.value, item.value, inputs[item.unit], item.valid_from),
            )


def _declared(filing: Filing) -> dict[SettingKey, str]:
    """The values one instance declares; a missing or ambiguous fact fails closed."""
    if not financial_rule(filing.body):
        raise DerivedSettingsError(_NOT_IND_AS.format(url=filing.url))
    root = etree.fromstring(filing.body)

    def fact(name: str) -> str:
        values = {
            (element.text or "").strip()
            for element in root.iter()
            if isinstance(element.tag, str) and etree.QName(element).localname == name
        }
        if len(values) != 1:
            raise DerivedSettingsError(
                _NOT_ONE.format(name=name, count=len(values), url=filing.url)
            )
        return values.pop()

    return {
        SettingKey.FISCAL_YEAR_END_MONTH: str(date.fromisoformat(fact(FISCAL_YEAR_END)).month),
        SettingKey.FILING_ROUNDING_LEVEL: fact(ROUNDING_LEVEL),
        SettingKey.PRESENTATION_CURRENCY: fact(PRESENTATION_CURRENCY),
        SettingKey.REPORTING_FRAMEWORK: AccountingFramework.IND_AS.value,
    }


_INSERT_BASIS: LiteralString = (
    "INSERT INTO eqos.entity_basis_status (entity_id, basis_status, evidence_input_id) "
    "VALUES (%s, %s, %s) ON CONFLICT DO NOTHING"
)
