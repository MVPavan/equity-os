"""Source-health assessment that distinguishes failures from no matching news."""

from __future__ import annotations

from datetime import datetime, timedelta

from fundamentals.contracts.news import (
    NewsFetchResult,
    NewsSourceHealthKind,
    NewsSourceWarning,
)


def assess_source_health(
    *,
    source_id: str,
    raw_count: int,
    resolved_count: int,
    published_times: tuple[datetime, ...],
    previous_had_data: bool,
    observed_at: datetime,
    recency_bound: timedelta,
) -> tuple[NewsSourceWarning, ...]:
    """Assess raw, resolved, and recency health outside pure source parsers."""
    if raw_count == 0:
        kind = NewsSourceHealthKind.EMPTY if previous_had_data else NewsSourceHealthKind.NO_HISTORY
        message = (
            "source returned an empty feed after previously returning data"
            if previous_had_data
            else "source has no prior history and returned no rows"
        )
        return (NewsSourceWarning(source_id=source_id, kind=kind, message=message),)
    if resolved_count == 0:
        return (
            NewsSourceWarning(
                source_id=source_id,
                kind=NewsSourceHealthKind.ZERO_RESOLVED,
                message=f"source returned {raw_count} raw row(s) but resolved none",
            ),
        )
    if published_times:
        latest = max(published_times)
        if latest < observed_at - recency_bound:
            return (
                NewsSourceWarning(
                    source_id=source_id,
                    kind=NewsSourceHealthKind.STALE,
                    message=(
                        f"source latest item {latest.isoformat()} predates observed-at "
                        f"recency bound {(observed_at - recency_bound).isoformat()}"
                    ),
                ),
            )
    return ()


def with_source_health(
    result: NewsFetchResult,
    *,
    published_times: tuple[datetime, ...],
    previous_had_data: bool,
    observed_at: datetime,
    recency_bound: timedelta,
) -> NewsFetchResult:
    """Attach composition-time health policy to a pure parse result."""
    warnings = (
        *result.warnings,
        *assess_source_health(
            source_id=result.source_id,
            raw_count=result.raw_count,
            resolved_count=len(result.observations),
            published_times=published_times,
            previous_had_data=previous_had_data,
            observed_at=observed_at,
            recency_bound=recency_bound,
        ),
    )
    return result.model_copy(update={"warnings": warnings})
