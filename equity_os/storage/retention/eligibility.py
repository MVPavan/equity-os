"""Eligibility of captures and blobs for purge (plan D9 R5); pure, no I/O."""

from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import datetime

from equity_os.contracts.storage.retention import (
    CaptureFacts,
    Eligibility,
    EligibilityKind,
    EligibleBlob,
    EligibleReason,
    HoldRoot,
    RetentionClass,
)

EXCHANGE_WINDOW_MONTHS = 3  # P4: three calendar months after verification
VENDOR_WINDOW_MONTHS = 12  # four quarters from registration (vendor and identity)
_KEEP = Eligibility(kind=EligibilityKind.KEEP)
# R3: for a vendor-bounded source only an open queue item or screen review extends the window.
_VENDOR_HOLDS = frozenset(
    {HoldRoot.OPEN_QUEUE_ITEM, HoldRoot.OPEN_SCREEN_REVIEW, HoldRoot.VENDOR_SURFACE_KEEP}
)


def add_months(at: datetime, months: int) -> datetime:
    """``at`` moved by calendar months, its day clamped to the target month's end."""
    year, month = divmod(at.year * 12 + at.month - 1 + months, 12)
    day = min(at.day, calendar.monthrange(year, month + 1)[1])
    return at.replace(year=year, month=month + 1, day=day)


def eligibility(facts: CaptureFacts, now: datetime) -> Eligibility:
    """R5 in order: licence end, effective coverage, relevant holds, then the class window."""
    ended = facts.licence_ended_at
    if ended is not None and ended <= now:
        return Eligibility(
            kind=EligibilityKind.ELIGIBLE, since=ended, reason=EligibleReason.LICENCE_END
        )
    if facts.covered:
        return _KEEP
    relevant = facts.holds & _VENDOR_HOLDS if facts.vendor_bounded else facts.holds
    if relevant:
        return Eligibility(kind=EligibilityKind.HELD, held_by=relevant)
    anchor, months = _anchor(facts)
    if anchor is None or now < (since := add_months(anchor, months)):
        return _KEEP
    reason = EligibleReason.CATALOG_CEILING if facts.holds else EligibleReason.WINDOW
    return Eligibility(kind=EligibilityKind.ELIGIBLE, since=since, reason=reason)


def _anchor(facts: CaptureFacts) -> tuple[datetime | None, int]:
    """The time a class's window runs from, and its length; no anchor keeps the bytes."""
    if facts.base_class is RetentionClass.EXCHANGE_REFETCHABLE:
        return (facts.verified_at if facts.url else None), EXCHANGE_WINDOW_MONTHS
    if facts.base_class in (RetentionClass.VENDOR, RetentionClass.IDENTITY):
        return facts.registered_at, VENDOR_WINDOW_MONTHS
    return None, 0


def eligible_blobs(facts: tuple[CaptureFacts, ...], now: datetime) -> tuple[EligibleBlob, ...]:
    """The ``(source, blob)`` pairs every user of which is eligible, since the latest."""
    users: defaultdict[tuple[str, str], list[CaptureFacts]] = defaultdict(list)
    for fact in facts:
        users[fact.source_id, fact.blob_sha256].append(fact)
    blobs = []
    for (source_id, blob_sha256), group in sorted(users.items()):
        verdicts = [eligibility(fact, now) for fact in group]
        if all(v.kind is EligibilityKind.ELIGIBLE for v in verdicts):
            blobs.append(
                EligibleBlob(
                    source_id=source_id,
                    blob_sha256=blob_sha256,
                    since=max(v.since for v in verdicts if v.since is not None),
                    capture_ref_ids=tuple(sorted(fact.capture_ref_id for fact in group)),
                )
            )
    return tuple(blobs)
