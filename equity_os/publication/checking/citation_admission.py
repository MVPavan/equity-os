"""Which pinned admission authorises a cited admitted value (VENDOR-1 §6.6, §6.9, §6.10).

Per fact or calculation operand, the latest of its admissions under the citing version's pinned
runs recorded at or before the cutoff authorises it, as ``read_selected`` does: its label is the
value's, and a vendor one stands only while both witnesses are held and, unchecked, its class has
no counterexample by the cutoff. Its recording and both witnesses' registrations are input times.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, LiteralString

from psycopg import Cursor

from equity_os.contracts.publication.ledger import InputTime
from equity_os.contracts.sourcing.source_catalog import SCREENER_PAGE, TIJORI_PAGE
from equity_os.contracts.verification.vendor_first import AdmissionLabel
from equity_os.verification.admission.eligibility import counterexample_at

# A vendor value's two witness captures: each source, registration and whether it is held
# (retained or restored, its vendor's licence not ended; §6.7, §6.9).
_WITNESSES: LiteralString = """SELECT c.source_id, c.surface, c.registered_at,
    eqos.capture_state(c.id) IN ('RETAINED', 'RESTORED')
        AND NOT EXISTS (SELECT 1 FROM eqos.licence_ends l WHERE l.source_id = c.source_id)
FROM eqos.interpretations i JOIN eqos.capture_refs c ON c.id = i.capture_ref_id
WHERE i.id IN (%s, %s)"""
_VENDOR_PAGES = (SCREENER_PAGE, TIJORI_PAGE)
_CHECKED = AdmissionLabel.CHECKED_AGAINST_FILING

Row = Mapping[str, Any]
Times = tuple[tuple[InputTime, datetime | None], ...]


def witnesses(cursor: Cursor[Any], chosen: int, witness: int) -> tuple[datetime, ...] | None:
    """The registration times of a vendor value's two witness captures, when both are held
    captures of the two vendor-primary sources; else ``None``."""
    with cursor.connection.cursor() as own:
        rows = own.execute(_WITNESSES, (chosen, witness)).fetchall()
    pages = {(source_id, surface) for source_id, surface, _, held in rows if held}
    return tuple(row[2] for row in rows) if pages == set(_VENDOR_PAGES) else None


def latest(admissions: Sequence[Row], cutoff: datetime) -> Row | None:
    """The latest admission recorded at or before ``cutoff``; with none, the latest of all,
    whose recording then falls after the cutoff."""
    known = [a for a in admissions if a["overlay_position"] <= cutoff] or admissions
    return max(known, key=lambda a: (a["overlay_position"], a["id"]), default=None)


def standing(cursor: Cursor[Any], admission: Row, cutoff: datetime) -> Times | None:
    """An authorising admission's input times, its recording and a vendor one's two witness
    registrations, when it stands at ``cutoff``; else ``None``."""
    recorded: Times = ((InputTime.RECORDED, admission["overlay_position"]),)
    chosen, witness = admission["interpretation_id"], admission["witness_interpretation_id"]
    if witness is None:
        return recorded
    registered = witnesses(cursor, chosen, witness)
    if registered is None or (
        admission["label"] != _CHECKED
        and counterexample_at(cursor, admission["class_digest"], cutoff) is not None
    ):
        return None
    return recorded + tuple((InputTime.FIRST_SEEN, at) for at in registered)
