"""Guidance lines and claims of a run draft: each extracted statement as a ``SOURCE_QUOTE`` claim
on its transcript's first-party capture, its ledger status against the prior, and the outstanding
question for a horizon that names no fiscal period (split from :mod:`run_draft`)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from psycopg import Cursor
from psycopg.rows import dict_row

from equity_os.analysis.lenses.credibility.guidance_targets import GUIDANCE_KEY
from equity_os.contracts.measurement.canonical import ValueKind
from equity_os.contracts.measurement.guidance_claim import EpistemicClass, GuidanceClaim
from equity_os.contracts.publication.ledger import (
    Citation,
    CitationKind,
    NumericClaim,
    Rounding,
)
from equity_os.contracts.sourcing.source_catalog import SourceCatalog
from equity_os.publication.checking.citations import _FILE_CAPTURES, _first_party
from equity_os.publication.checking.claim_check import UNITS, quote_qualifiers
from equity_os.publication.drafting.earnings_update import EarningsUpdate
from equity_os.publication.drafting.management_ledger import LedgerStatus
from equity_os.publication.revision.import_mapping import (
    BOUNDS_STYLE,
    CONTRACT_FIELDS,
    QUOTE_STYLE,
    _places,
    _slot,
    refs,
)

if TYPE_CHECKING:
    from equity_os.publication.drafting.run_draft import Prior

GUIDANCE = "management_ledger"
CARRIED = LedgerStatus.CARRIED
FISCAL_PERIOD = re.compile(r"FY\d{2,4}(?:_Q[1-4])?")
UNSPECIFIED = " (target period not specified by the extracted guidance)"
UNCOMPARED = " (comparability not established)"
QUESTION = (
    "- Which fiscal year or window applies to {label}? Why it matters: the "
    "guidance cannot be checked against an outcome period without it. Evidence required: the "
    "transcript context around the quoted guidance {ref}, or a later management statement "
    "naming the period. Status: open; owner not assigned."
)


def _captures(cursor: Cursor[Any], sha256: str, catalog: SourceCatalog) -> list[dict[str, Any]]:
    """The file's first-party captures, earliest first-seen first."""
    with cursor.connection.cursor(row_factory=dict_row) as own:
        rows = own.execute(_FILE_CAPTURES, (sha256,)).fetchall()
    return [row for row in rows if _first_party(row["source_id"], catalog)]


def _guidance(
    cursor: Cursor[Any],
    guidance: tuple[GuidanceClaim, ...],
    update: EarningsUpdate,
    prior: Prior,
    catalog: SourceCatalog,
) -> list[tuple[str, NumericClaim]]:
    """Each guidance line and claim, then the prior's entries the run did not restate."""
    entries = {entry.claim_key: entry for entry in prior.entries}
    found = []
    for claim_source, rendered in zip(guidance, update.guidance, strict=True):
        claim = _quote(cursor, claim_source, rendered.metric_label, rendered.quote, catalog)
        found.append((_guided(claim, _status(claim, entries.get(claim.claim_key))), claim))
    stated = {claim.claim_key for _, claim in found}
    for key, entry in entries.items():
        if key not in stated:
            carried = entry.model_copy(update={"section_key": GUIDANCE})
            found.append((_guided(carried, CARRIED), carried))
    return found


def _guided(claim: NumericClaim, status: LedgerStatus) -> str:
    """A guidance line; a status against a predecessor (same key, so same horizon) is not a
    comparison when the horizon names no fiscal period."""
    key, note = claim.claim_key, "" if _specified(claim.horizon) else UNSPECIFIED
    uncompared = note and status in (LedgerStatus.MODIFIED, LedgerStatus.REAFFIRMED)
    return (
        f"- {claim.metric_label or claim.metric}: {_slot(key, f'{BOUNDS_STYLE},qual')} for "
        f"{claim.horizon}{note} — {status.value}{UNCOMPARED if uncompared else ''}: "
        f'"{_slot(key, QUOTE_STYLE)}" {refs([key])}'
    )


def _question(claim: NumericClaim) -> str:
    """The outstanding question of a guidance claim whose horizon names no fiscal period."""
    return QUESTION.format(label=claim.metric_label or claim.metric, ref=refs([claim.claim_key]))


def _specified(horizon: str | None) -> bool:
    """Whether ``horizon`` names a fiscal year or fiscal quarter, never an inferred one."""
    return horizon is not None and FISCAL_PERIOD.fullmatch(horizon) is not None


def _quote(
    cursor: Cursor[Any],
    guidance: GuidanceClaim,
    metric_label: str,
    quote: str,
    catalog: SourceCatalog,
) -> NumericClaim:
    """A guidance claim as a ``SOURCE_QUOTE`` on its transcript's first-party capture (its
    contract binds through the sealed imports, M9)."""
    source = guidance.provenance
    captures = _captures(cursor, source.file_sha256, catalog)
    return NumericClaim(
        claim_key=GUIDANCE_KEY.format(
            metric=guidance.metric, horizon=guidance.horizon, scope=guidance.scope.value
        ),
        section_key=GUIDANCE,
        citation=Citation(
            kind=CitationKind.SOURCE_QUOTE,
            source_sha256=source.file_sha256,
            capture_ref_id=captures[0]["id"] if captures else None,
            anchor=f"p{source.page}.b{source.block}.{source.span}",
            quote=quote,
        ),
        value_kind=UNITS.get(guidance.unit, (ValueKind.CURRENCY_AMOUNT,))[0],
        qualifiers=tuple(sorted(quote_qualifiers(quote))),
        precision=max(_places(guidance.lower_bound), _places(guidance.upper_bound)),
        rounding=Rounding.ROUND_HALF_EVEN,
        epistemic_class=EpistemicClass.FORECAST,
        metric_label=metric_label,
        **guidance.model_dump(include=CONTRACT_FIELDS) | {"scope": guidance.scope.value},
    )


def _status(claim: NumericClaim, entry: NumericClaim | None) -> LedgerStatus:
    """``NEW`` with no prior entry; ``REAFFIRMED`` only when bounds, unit, constant currency
    and qualifiers all equal the prior's (F11); else ``MODIFIED``."""
    if entry is None:
        return LedgerStatus.NEW
    fields = ("lower_bound", "upper_bound", "unit", "constant_currency", "qualifiers")
    same = all(getattr(claim, name) == getattr(entry, name) for name in fields)
    return LedgerStatus.REAFFIRMED if same else LedgerStatus.MODIFIED
