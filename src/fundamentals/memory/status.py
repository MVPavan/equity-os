"""An item's status and revalidation flag, derived from its decision log (ledger spec P1, §2;
plan D4, M5)."""

from __future__ import annotations

from fundamentals.contracts.ledger import DecisionKind
from fundamentals.contracts.memory import MemoryStatus

_HEAD_STATUS = {
    None: MemoryStatus.CANDIDATE,
    DecisionKind.PROMOTE: MemoryStatus.PROMOTED,
    DecisionKind.REJECT_CANDIDATE: MemoryStatus.REJECTED,
    DecisionKind.RETIRE: MemoryStatus.RETIRED,
}


def derive_status(
    head: DecisionKind | None, retired_by_successor: bool, supported: bool
) -> tuple[MemoryStatus, bool]:
    """The status from the head decision (a promoted successor retires a promoted item) and
    whether it needs revalidation: only a promoted item whose supports no longer hold."""
    status = _HEAD_STATUS[head]
    if status is MemoryStatus.PROMOTED and retired_by_successor:
        status = MemoryStatus.RETIRED
    return status, status is MemoryStatus.PROMOTED and not supported
