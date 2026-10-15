"""Trust is a view over immutable two-check results and one named queue overlay (spec §5)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.comparison import CorroborationStatus, ExtractionStatus, SourceState
from fundamentals.contracts.measurement_key import MeasurementKey
from fundamentals.contracts.review_queue import QueueOverlay, QueueSeverity


class TrustResult(BaseModel):
    """A view at the stated run and overlay time; never a stored result."""

    model_config = ConfigDict(frozen=True)
    run_id: int
    key_digest: str
    overlay_as_of: datetime
    trusted: bool


def trusted(
    *,
    run_id: int,
    key: MeasurementKey,
    extraction: ExtractionStatus,
    corroboration: CorroborationStatus,
    first_party_state: SourceState,
    overlay: QueueOverlay,
) -> TrustResult:
    """Both checks must hold, with no open non-diagnostic HIGH item on this cell.

    The overlay is supplied explicitly by the queue's as-of reader. Dispositions never
    rewrite either immutable status; they affect this view through the open item set.
    """
    if overlay.run_id != run_id:
        raise ValueError("queue overlay belongs to another run")
    extraction_holds = first_party_state is SourceState.VALUE and extraction in (
        ExtractionStatus.AGREE,
        ExtractionStatus.NOT_APPLICABLE,
    )
    return TrustResult(
        run_id=run_id,
        key_digest=key.digest(),
        overlay_as_of=overlay.as_of,
        trusted=extraction_holds
        and corroboration is CorroborationStatus.CORROBORATED
        and not open_high(overlay, key),
    )


def open_high(overlay: QueueOverlay, key: MeasurementKey) -> bool:
    """Whether an open non-diagnostic HIGH item names ``key`` in ``overlay``."""
    return any(
        item.key is not None
        and item.key.digest() == key.digest()
        and item.severity is QueueSeverity.HIGH
        and not item.diagnostic
        for item in overlay.open_items
    )
