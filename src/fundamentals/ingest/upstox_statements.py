"""The four Lane B fundamentals responses, parsed under the traps that hide in them.

Verified live on 2026-09-04 against 29 authenticated responses over three
issuers and both bases. Every refusal and every anomaly below traces to
something those responses actually did; the vendor's documentation describes
none of it. The full record is in
``docs/research/upstox-api-schemas/fundamentals.md``.

**An empty response is not proof of an empty company.** An unknown ISIN returns
``{"status":"success","data":[]}`` with HTTP 200 — byte-identical to a real
company that has nothing to report. Nothing in this module can tell those apart,
and no envelope check can: the caller must only ask about ISINs it already found
in the instrument catalog. ``OK_EMPTY`` here means "the payload was empty",
never "the company published nothing".

**``full_statement`` is annual whatever the response claims.** Asking
``income-statement`` for ``time_period=quarterly`` returns a payload whose own
``time_period`` field says ``quarterly``, whose summary block *is* quarterly,
and whose ``full_statement`` block is still the last four financial years. So
the two blocks carry different periodicities and the document names them
separately —:attr:`IncomeStatementDocument.summary_periodicity` and
:attr:`~IncomeStatementDocument.full_statement_periodicity` — because a single
``periodicity`` attribute would be a lie half the time.

``balance-sheet`` and ``cash-flow`` ignore ``time_period`` outright, returning
byte-identical annual bodies that echo ``"yearly"``. Their readers therefore
take no periodicity argument at all: the safest guard against a silently
discarded request is not offering it.

**One payload can contradict itself.** On NETWEB Mar-2025 the summary
``operating_profit`` reads 153.0 while the ``full_statement`` particular it is
identical to, ``Profit Before Tax``, reads 153.97 — in the same HTTP response,
far beyond rounding. 48 of the 51 observed identities held; these are the other
three. The disagreement is recorded as an anomaly and neither side is preferred,
because "Upstox says X" is not well defined for that issuer and period.

**``key-ratios`` is the odd one.** ``data`` is a bare array, not an object; its
row set varies by company (one live issuer omits ``Quick Ratio`` entirely); its
values are strings, sometimes ``%``-suffixed and sometimes negative; and it
echoes no ``type``, no ``units_in`` and no period — while still honouring
``?type=``. The basis is real but unstated, so the caller's request is what the
document records.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from fundamentals.ingest.upstox_source import (
    AcquisitionOutcome,
    UpstoxFetch,
    UpstoxSurface,
)
from fundamentals.verify.crossfoot import half_ulp

# Every one of the 22 live envelopes carrying a unit said crore, so a change is
# a silent rescaling of every number downstream and is refused rather than read.
EXPECTED_UNITS = "crore"
EXPECTED_STATUS = "success"
PERCENT_SUFFIX = "%"

# Values on both sides are already stated in crore.
CRORE_SCALE = 1

FULL_STATEMENT_IS_ALWAYS_ANNUAL = (
    "full_statement is annual although time_period echoes quarterly; only the "
    "summary block carries quarterly data"
)
_FULL_STATEMENT_WAS_NULL = "full_statement was null rather than a list; read as empty"
_UNREADABLE_JSON = "response body is not valid JSON: {reason}"
_NOT_AN_OBJECT = "response body is not a JSON object"
_BAD_STATUS = "status was {status!r}, not {expected!r}"
_BAD_UNITS = "units_in was {units!r}, not {expected!r}"
_BAD_BASIS = "response echoed type {echoed!r} for a {requested!r} request"
_BAD_PERIODICITY = "response echoed time_period {echoed!r} for a {requested!r} request"
_BAD_SHAPE = "{field} is not in the verified shape: {reason}"
_NOT_AN_ARRAY = "data is not a JSON array; key-ratios carries a bare list"
_SUMMARY_DISAGREES = (
    "summary {category} {period} = {summary} but full_statement {particular} "
    "= {full}; the same response states both"
)
_WRONG_SURFACE = "capture is from surface {actual}, not {expected}"

# What each field of the note above looks like when the note is read back. The
# period carries a space, so it is the one field that cannot be a run of
# non-space characters. Both numbers are captured: the triage rule needs the
# ``full_statement`` figure to decide whether Screener agrees with it.
_NOTE_FIELD_PATTERNS: dict[str, str] = {
    "category": r"(?P<category>\S+)",
    "period": r"(?P<period>.+?)",
    "summary": r"(?P<summary>\S+)",
    "particular": r".+?",
    "full": r"(?P<full>\S+)",
}
_NOTE_FIELD_MARKER = "\x00{field}\x00"
# ``compare_company`` stores every parse note prefixed with the surface it came
# from, so the reader has to accept both the bare note and the stored form.
_NOTE_SURFACE_PREFIX = "(?:(?:{surfaces}): )?"


def _identity_note_pattern() -> re.Pattern[str]:
    """Derive the note's reader from the note's own format string.

    Written this way so the two cannot drift: a change to
    ``_SUMMARY_DISAGREES`` changes the pattern with it, and the triage rule that
    consumes the note keeps firing. A second, hand-written regex would go stale
    silently — the queue would fill with lines the vendor had already admitted
    were self-contradictory, and no test would fail.
    """
    marked = _SUMMARY_DISAGREES.format(
        **{field: _NOTE_FIELD_MARKER.format(field=field) for field in _NOTE_FIELD_PATTERNS}
    )
    body = re.escape(marked)
    for field, pattern in _NOTE_FIELD_PATTERNS.items():
        body = body.replace(re.escape(_NOTE_FIELD_MARKER.format(field=field)), pattern)
    prefix = _NOTE_SURFACE_PREFIX.format(
        surfaces="|".join(re.escape(surface.value) for surface in UpstoxSurface)
    )
    return re.compile(prefix + body)


_IDENTITY_NOTE_PATTERN = _identity_note_pattern()


class IdentityNote(BaseModel):
    """One cell the response contradicted itself about, and both figures it gave.

    The category and period say which cell, and nothing wider. Both numbers
    travel with them because "the vendor disagrees with itself" is not on its own
    an alibi for a Screener disagreement: only a Screener value that matches the
    ``full_statement`` figure places the fault on the vendor's summary block
    rather than on this repo's parse.
    """

    model_config = ConfigDict(frozen=True)

    category: str = Field(min_length=1)
    period: str = Field(min_length=1)
    summary: Decimal
    full: Decimal


def parse_identity_note(note: str) -> IdentityNote | None:
    """Read one stored anomaly back, or ``None`` when it is not an identity note.

    ``None`` is the answer for every note about the envelope, the status or the
    response's shape: those carry no cell and no figures, and guessing one would
    exonerate a line nothing was ever said about.
    """
    match = _IDENTITY_NOTE_PATTERN.fullmatch(note)
    if match is None:
        return None
    try:
        summary, full = Decimal(match["summary"]), Decimal(match["full"])
    except InvalidOperation:
        return None
    return IdentityNote(
        category=match["category"], period=match["period"], summary=summary, full=full
    )


class StatementBasis(StrEnum):
    """Which set of books a request asked for."""

    STANDALONE = "standalone"
    CONSOLIDATED = "consolidated"


class StatementPeriodicity(StrEnum):
    """The reporting frequency a block of a response carries."""

    YEARLY = "yearly"
    QUARTERLY = "quarterly"


# What each summary category is identical to in the same payload's
# ``full_statement``. ``operating_profit`` is the one that matters: it is not
# operating profit, it is profit before tax, and a comparator built on the label
# would report a false mismatch on every company.
INCOME_SUMMARY_IDENTITIES: tuple[tuple[str, str], ...] = (
    ("revenue", "Total Revenue"),
    ("operating_profit", "Profit Before Tax"),
    ("net_profit", "Profit After Tax"),
)


class UpstoxStatementError(ValueError):
    """Raised when a capture is handed to a reader that cannot honestly read it."""


class PeriodPoint(BaseModel):
    """One period's value, with the vendor's own percentage change if it gave one.

    ``change`` is a string like ``"+44.62%"`` and is absent on the oldest period
    of every series observed. It is retained verbatim and never parsed: it is
    the vendor's arithmetic over the vendor's own numbers, not an input.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    period: str = Field(min_length=1)
    value: Decimal
    change: str | None = None


class SummarySeries(BaseModel):
    """One summary category and its history, most-recent-first as the wire states it."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    category: str = Field(min_length=1)
    history: tuple[PeriodPoint, ...] = ()


class StatementLine(BaseModel):
    """One ``full_statement`` particular and its history."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    particular: str = Field(min_length=1)
    history: tuple[PeriodPoint, ...] = ()


class BalanceSheetPoint(BaseModel):
    """One period of the balance-sheet summary.

    The keys are singular on the wire — ``total_asset``, ``total_liability`` —
    and the summary is a flat list rather than the ``{category, history}`` shape
    the other two statements use.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    period: str = Field(min_length=1)
    total_asset: Decimal
    total_liability: Decimal


class KeyRatio(BaseModel):
    """One ratio, kept as stated and parsed alongside.

    The wire values are strings because some carry a trailing ``%``. Both the
    string and the number are held: the string is what the vendor said, the
    number is what can be compared.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    name: str = Field(min_length=1)
    company_value: str = Field(min_length=1)
    sector_value: str = Field(min_length=1)

    @property
    def is_percentage(self) -> bool:
        """Whether this ratio is stated as a percentage rather than a multiple."""
        return self.company_value.endswith(PERCENT_SUFFIX)

    @property
    def company_number(self) -> Decimal:
        """The company figure with any percent sign removed."""
        return _ratio_number(self.company_value)

    @property
    def sector_number(self) -> Decimal:
        """The sector figure with any percent sign removed. Can be negative."""
        return _ratio_number(self.sector_value)

    @model_validator(mode="after")
    def _check_both_sides_are_the_same_kind_of_number(self) -> KeyRatio:
        """A percentage against a multiple is two different quantities under one name."""
        if self.company_value.endswith(PERCENT_SUFFIX) != self.sector_value.endswith(
            PERCENT_SUFFIX
        ):
            raise ValueError(
                f"ratio {self.name!r} mixes a percentage and a multiple: "
                f"{self.company_value!r} vs {self.sector_value!r}"
            )
        _ratio_number(self.company_value)
        _ratio_number(self.sector_value)
        return self


def _ratio_number(stated: str) -> Decimal:
    """Read one ratio string, refusing anything that is not a number.

    A placeholder such as ``"-"`` must not become zero: zero is a claim and the
    vendor made none.
    """
    try:
        return Decimal(stated.removesuffix(PERCENT_SUFFIX))
    except InvalidOperation as error:
        raise ValueError(f"ratio value {stated!r} is not a number") from error


class _DocumentHeader(BaseModel):
    """What every Lane B document records about the capture it was read from."""

    model_config = ConfigDict(frozen=True)

    surface: UpstoxSurface
    route_key: str
    source_url: str
    content_sha256: str
    byte_count: int
    retrieved_at: datetime
    outcome: AcquisitionOutcome
    # The basis the caller asked for, not one the payload asserted: key-ratios
    # echoes nothing, and the other three are checked against this rather than
    # trusted to define it.
    basis: StatementBasis
    anomalies: tuple[str, ...] = ()


class IncomeStatementDocument(_DocumentHeader):
    """One ``income-statement`` response, with its two blocks named separately."""

    summary_periodicity: StatementPeriodicity = StatementPeriodicity.YEARLY
    # Never the requested periodicity: the block is annual in every observed
    # response, including those the vendor labelled quarterly.
    full_statement_periodicity: StatementPeriodicity = StatementPeriodicity.YEARLY
    summary: tuple[SummarySeries, ...] = ()
    full_statement: tuple[StatementLine, ...] = ()


class BalanceSheetDocument(_DocumentHeader):
    """One ``balance-sheet`` response. Annual only — the surface ignores anything else."""

    history: tuple[BalanceSheetPoint, ...] = ()
    full_statement: tuple[StatementLine, ...] = ()


class CashFlowDocument(_DocumentHeader):
    """One ``cash-flow`` response. Annual only, three signed summary categories."""

    summary: tuple[SummarySeries, ...] = ()
    full_statement: tuple[StatementLine, ...] = ()


class KeyRatiosDocument(_DocumentHeader):
    """One ``key-ratios`` response — a bare array, with no period and no unit."""

    ratios: tuple[KeyRatio, ...] = ()


def read_income_statement(
    fetch: UpstoxFetch,
    *,
    requested_basis: StatementBasis,
    requested_periodicity: StatementPeriodicity = StatementPeriodicity.YEARLY,
) -> IncomeStatementDocument:
    """Read one ``income-statement`` capture, naming each block's real periodicity."""
    data, anomalies = _envelope(fetch, UpstoxSurface.INCOME_STATEMENT, requested_basis)
    if data is None:
        return IncomeStatementDocument(
            **_header(fetch, AcquisitionOutcome.SCHEMA_DRIFT, requested_basis, anomalies)
        )
    echoed = data.get("time_period")
    if echoed != requested_periodicity.value:
        anomalies += (
            _BAD_PERIODICITY.format(echoed=echoed, requested=requested_periodicity.value),
        )
        return IncomeStatementDocument(
            **_header(fetch, AcquisitionOutcome.SCHEMA_DRIFT, requested_basis, anomalies)
        )
    summary, summary_fault = _series(data.get("income_statement"), "income_statement")
    lines, line_anomalies = _full_statement(data)
    anomalies += line_anomalies
    if summary is None or lines is None:
        return IncomeStatementDocument(
            **_header(
                fetch,
                AcquisitionOutcome.SCHEMA_DRIFT,
                requested_basis,
                anomalies + summary_fault,
            )
        )
    if requested_periodicity is StatementPeriodicity.QUARTERLY:
        # The two blocks now carry different periodicities, and "Mar 2026"
        # names the quarter in one and the financial year in the other. The
        # identity check keys on that label, so running it here compares a
        # quarter against a year and reports three confident false
        # disagreements per company. Same label, different meaning: not a key.
        anomalies += (FULL_STATEMENT_IS_ALWAYS_ANNUAL,)
    else:
        anomalies += _identity_anomalies(summary, lines)
    empty = not lines and all(not series.history for series in summary)
    return IncomeStatementDocument(
        **_header(
            fetch,
            AcquisitionOutcome.OK_EMPTY if empty else AcquisitionOutcome.OK,
            requested_basis,
            anomalies,
        ),
        summary_periodicity=requested_periodicity,
        summary=summary,
        full_statement=lines,
    )


def read_balance_sheet(
    fetch: UpstoxFetch, *, requested_basis: StatementBasis
) -> BalanceSheetDocument:
    """Read one ``balance-sheet`` capture. No periodicity argument, by design."""
    data, anomalies = _envelope(fetch, UpstoxSurface.BALANCE_SHEET, requested_basis)
    if data is None:
        return BalanceSheetDocument(
            **_header(fetch, AcquisitionOutcome.SCHEMA_DRIFT, requested_basis, anomalies)
        )
    annual_fault = _annual_only(data)
    anomalies += annual_fault
    history, history_fault = _rows(data.get("history"), BalanceSheetPoint, "history")
    lines, line_anomalies = _full_statement(data)
    anomalies += line_anomalies
    if history is None or lines is None or annual_fault:
        return BalanceSheetDocument(
            **_header(
                fetch, AcquisitionOutcome.SCHEMA_DRIFT, requested_basis, anomalies + history_fault
            )
        )
    empty = not history and not lines
    return BalanceSheetDocument(
        **_header(
            fetch,
            AcquisitionOutcome.OK_EMPTY if empty else AcquisitionOutcome.OK,
            requested_basis,
            anomalies,
        ),
        history=history,
        full_statement=lines,
    )


def read_cash_flow(fetch: UpstoxFetch, *, requested_basis: StatementBasis) -> CashFlowDocument:
    """Read one ``cash-flow`` capture. No periodicity argument, by design."""
    data, anomalies = _envelope(fetch, UpstoxSurface.CASH_FLOW, requested_basis)
    if data is None:
        return CashFlowDocument(
            **_header(fetch, AcquisitionOutcome.SCHEMA_DRIFT, requested_basis, anomalies)
        )
    annual_fault = _annual_only(data)
    anomalies += annual_fault
    summary, summary_fault = _series(data.get("cash_flow"), "cash_flow")
    lines, line_anomalies = _full_statement(data)
    anomalies += line_anomalies
    if summary is None or lines is None or annual_fault:
        return CashFlowDocument(
            **_header(
                fetch, AcquisitionOutcome.SCHEMA_DRIFT, requested_basis, anomalies + summary_fault
            )
        )
    empty = not lines and all(not series.history for series in summary)
    return CashFlowDocument(
        **_header(
            fetch,
            AcquisitionOutcome.OK_EMPTY if empty else AcquisitionOutcome.OK,
            requested_basis,
            anomalies,
        ),
        summary=summary,
        full_statement=lines,
    )


def read_key_ratios(fetch: UpstoxFetch, *, requested_basis: StatementBasis) -> KeyRatiosDocument:
    """Read one ``key-ratios`` capture, recording the basis the payload will not state."""
    _check_surface(fetch, UpstoxSurface.KEY_RATIOS)
    payload, anomalies = _payload(fetch)
    if payload is None:
        return KeyRatiosDocument(
            **_header(fetch, AcquisitionOutcome.SCHEMA_DRIFT, requested_basis, anomalies)
        )
    anomalies += _status_anomaly(payload)
    data = payload.get("data")
    if not isinstance(data, list):
        anomalies += (_NOT_AN_ARRAY,)
        return KeyRatiosDocument(
            **_header(fetch, AcquisitionOutcome.SCHEMA_DRIFT, requested_basis, anomalies)
        )
    ratios, ratio_fault = _rows(data, KeyRatio, "data")
    if ratios is None or anomalies:
        return KeyRatiosDocument(
            **_header(
                fetch, AcquisitionOutcome.SCHEMA_DRIFT, requested_basis, anomalies + ratio_fault
            )
        )
    return KeyRatiosDocument(
        **_header(
            fetch,
            AcquisitionOutcome.OK_EMPTY if not ratios else AcquisitionOutcome.OK,
            requested_basis,
            anomalies,
        ),
        ratios=ratios,
    )


def _header(
    fetch: UpstoxFetch,
    outcome: AcquisitionOutcome,
    basis: StatementBasis,
    anomalies: tuple[str, ...],
) -> dict[str, Any]:
    """The metadata every document carries, bound to the capture it was read from."""
    capture = fetch.capture
    return {
        "surface": capture.surface,
        "route_key": capture.route_key,
        "source_url": capture.request_url,
        "content_sha256": capture.content_sha256,
        "byte_count": capture.byte_count,
        "retrieved_at": capture.retrieved_at,
        "outcome": outcome,
        "basis": basis,
        "anomalies": anomalies,
    }


def _check_surface(fetch: UpstoxFetch, expected: UpstoxSurface) -> None:
    """Refuse a capture from another surface.

    The four bodies share an envelope and half-parse each other, so a mixed-up
    capture would otherwise produce a plausible empty document rather than an
    error.
    """
    actual = fetch.capture.surface
    if actual is not expected:
        raise UpstoxStatementError(
            _WRONG_SURFACE.format(actual=actual.value, expected=expected.value)
        )


def _payload(fetch: UpstoxFetch) -> tuple[dict[str, Any] | None, tuple[str, ...]]:
    """Decode the response body, reading every number as a ``Decimal``.

    A float round-trip here would perturb the last digit and so the half-ULP
    tolerance Lane B derives from it.
    """
    try:
        decoded = json.loads(fetch.raw_body.decode("utf-8"), parse_float=Decimal)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        return None, (_UNREADABLE_JSON.format(reason=type(error).__name__),)
    if not isinstance(decoded, dict):
        return None, (_NOT_AN_OBJECT,)
    return decoded, ()


def _status_anomaly(payload: Mapping[str, Any]) -> tuple[str, ...]:
    """Whether the envelope claimed success."""
    status = payload.get("status")
    if status != EXPECTED_STATUS:
        return (_BAD_STATUS.format(status=status, expected=EXPECTED_STATUS),)
    return ()


def _envelope(
    fetch: UpstoxFetch, expected: UpstoxSurface, requested_basis: StatementBasis
) -> tuple[dict[str, Any] | None, tuple[str, ...]]:
    """Decode and check everything the three statement surfaces share.

    Returns ``None`` for ``data`` when the response cannot be trusted, so the
    caller still records a document carrying the capture's hash and can re-read
    the retained bytes after a reviewed parser change.
    """
    _check_surface(fetch, expected)
    payload, anomalies = _payload(fetch)
    if payload is None:
        return None, anomalies
    anomalies += _status_anomaly(payload)
    data = payload.get("data")
    if not isinstance(data, dict):
        return None, anomalies + (_NOT_AN_OBJECT,)
    units = data.get("units_in")
    if units != EXPECTED_UNITS:
        anomalies += (_BAD_UNITS.format(units=units, expected=EXPECTED_UNITS),)
    echoed = data.get("type")
    if echoed != requested_basis.value:
        anomalies += (_BAD_BASIS.format(echoed=echoed, requested=requested_basis.value),)
    if anomalies:
        return None, anomalies
    return data, ()


def _annual_only(data: Mapping[str, Any]) -> tuple[str, ...]:
    """Refuse a balance-sheet or cash-flow body that is not annual.

    Both surfaces discard ``time_period`` and always answer yearly. Anything
    else means the surface changed under us.
    """
    echoed = data.get("time_period")
    if echoed != StatementPeriodicity.YEARLY.value:
        return (
            _BAD_PERIODICITY.format(echoed=echoed, requested=StatementPeriodicity.YEARLY.value),
        )
    return ()


def _rows[RowT: (BalanceSheetPoint, KeyRatio)](
    raw: Any, model: type[RowT], field: str
) -> tuple[tuple[RowT, ...] | None, tuple[str, ...]]:
    """Type a flat list of wire rows, refusing the whole block if any one fails."""
    if not isinstance(raw, list):
        return None, (_BAD_SHAPE.format(field=field, reason="not a list"),)
    rows: list[RowT] = []
    for entry in raw:
        try:
            rows.append(model.model_validate(entry))
        except ValidationError as error:
            return None, (_BAD_SHAPE.format(field=field, reason=error.errors()[0]["msg"]),)
    return tuple(rows), ()


def _series(raw: Any, field: str) -> tuple[tuple[SummarySeries, ...] | None, tuple[str, ...]]:
    """Type a ``{category, history}`` summary block."""
    if not isinstance(raw, list):
        return None, (_BAD_SHAPE.format(field=field, reason="not a list"),)
    series: list[SummarySeries] = []
    for entry in raw:
        try:
            series.append(SummarySeries.model_validate(entry))
        except ValidationError as error:
            return None, (_BAD_SHAPE.format(field=field, reason=error.errors()[0]["msg"]),)
    return tuple(series), ()


def _full_statement(
    data: Mapping[str, Any],
) -> tuple[tuple[StatementLine, ...] | None, tuple[str, ...]]:
    """Type the ``full_statement`` block, tolerating the ``null`` the vendor can send.

    ``null`` appeared once in the verification pass, on an invalid ISIN. It is
    read as empty and recorded, because a ``TypeError`` here would lose the
    capture that documents it.
    """
    raw = data.get("full_statement")
    if raw is None:
        return (), (_FULL_STATEMENT_WAS_NULL,)
    if not isinstance(raw, list):
        return None, (_BAD_SHAPE.format(field="full_statement", reason="not a list"),)
    lines: list[StatementLine] = []
    for entry in raw:
        try:
            lines.append(StatementLine.model_validate(entry))
        except ValidationError as error:
            return None, (
                _BAD_SHAPE.format(field="full_statement", reason=error.errors()[0]["msg"]),
            )
    return tuple(lines), ()


def _identity_anomalies(
    summary: Sequence[SummarySeries], lines: Sequence[StatementLine]
) -> tuple[str, ...]:
    """Record where the two blocks of one response disagree about the same number.

    48 of 51 live identities held. The tolerance is the sum of both values'
    half-ULP — the same derivation the cross-footing checks use — so a
    last-digit difference is not reported and a 0.97 crore gap is.

    Only ever called when both blocks are annual. The period label is the key,
    and under a quarterly request "Mar 2026" names the quarter on one side and
    the financial year on the other.
    """
    by_particular = {line.particular: line for line in lines}
    found: list[str] = []
    for category, particular in INCOME_SUMMARY_IDENTITIES:
        series = next((s for s in summary if s.category == category), None)
        line = by_particular.get(particular)
        if series is None or line is None:
            continue
        stated = {point.period: point.value for point in line.history}
        for point in series.history:
            other = stated.get(point.period)
            if other is None:
                continue
            tolerance = _half_ulp(point.value) + _half_ulp(other)
            if abs(point.value - other) > tolerance:
                found.append(
                    _SUMMARY_DISAGREES.format(
                        category=category,
                        period=point.period,
                        summary=point.value,
                        particular=particular,
                        full=other,
                    )
                )
    return tuple(found)


def _half_ulp(value: Decimal) -> Decimal:
    """Half the last stated digit of one value, as the wire wrote it."""
    exponent = value.as_tuple().exponent
    decimals = -exponent if isinstance(exponent, int) else 0
    return half_ulp(max(decimals, 0), CRORE_SCALE)
