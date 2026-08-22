"""Parse a model's raw answer into a structured :class:`ThesisDraft`.

Real models wrap JSON in prose or code fences; parsing is therefore lenient — it
recovers the first well-formed JSON object it can find. If nothing parses, the
draft is still returned with its raw text (``parsed=False``) so the number-checker
can inspect it and the divergence check can flag it as unstructured, rather than
the pipeline crashing on a malformed answer (fail-closed).
"""

from __future__ import annotations

import json
from typing import Any

from fundamentals.thesis.contracts import (
    DraftSection,
    DraftStatus,
    JudgmentSection,
    ThesisDraft,
)

_STANCE_KEY = "stance"


def _string_list(value: Any) -> tuple[str, ...]:
    """Coerce a JSON value (dynamic) into a tuple of non-empty strings."""
    if isinstance(value, list):
        return tuple(str(item).strip() for item in value if str(item).strip())
    if isinstance(value, str) and value.strip():
        return (value.strip(),)
    return ()


def _extract_json_object(text: str) -> dict[str, Any] | None:
    """Recover the first well-formed JSON object from possibly-noisy text."""
    stripped = text.strip()
    candidates = [stripped]
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidates.append(stripped[start : end + 1])
    for candidate in candidates:
        try:
            parsed: Any = json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def parse_draft(
    raw_text: str, *, model_label: str, client_name: str, duration_seconds: float
) -> ThesisDraft:
    """Structure a model's raw answer; degrade gracefully when it is not JSON."""
    if not raw_text.strip():
        return ThesisDraft(
            model_label=model_label,
            client_name=client_name,
            status=DraftStatus.EMPTY,
            stance="",
            sections=(),
            raw_text=raw_text,
            parsed=False,
            duration_seconds=duration_seconds,
            error="model returned empty output",
        )

    data = _extract_json_object(raw_text)
    if data is None:
        return ThesisDraft(
            model_label=model_label,
            client_name=client_name,
            status=DraftStatus.OK,
            stance="",
            sections=(),
            raw_text=raw_text,
            parsed=False,
            duration_seconds=duration_seconds,
            error="output was not valid JSON",
        )

    sections = tuple(
        DraftSection(section=section, points=points)
        for section in JudgmentSection
        if (points := _string_list(data.get(section.value)))
    )
    stance = str(data.get(_STANCE_KEY, "")).strip()
    return ThesisDraft(
        model_label=model_label,
        client_name=client_name,
        status=DraftStatus.OK,
        stance=stance,
        sections=sections,
        raw_text=raw_text,
        parsed=True,
        duration_seconds=duration_seconds,
    )


def failed_draft(
    *,
    model_label: str,
    client_name: str,
    status: DraftStatus,
    error: str,
    duration_seconds: float,
) -> ThesisDraft:
    """Build a draft recording a failed or timed-out model call (no fabrication)."""
    return ThesisDraft(
        model_label=model_label,
        client_name=client_name,
        status=status,
        stance="",
        sections=(),
        raw_text="",
        parsed=False,
        duration_seconds=duration_seconds,
        error=error,
    )
