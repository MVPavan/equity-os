"""Durable qualification context for publication-bound first-party interpretations."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from fundamentals.contracts.evidence import Interpretation
from fundamentals.contracts.snapshot import canonical_sha256
from fundamentals.evidence.repository import EvidenceRepository, SettingsRecord
from fundamentals.pg.identity_seed import SettingKey

QUALIFICATION_CONTEXT_TRACE_KEY = "first_party_qualification_context_v1"
_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_MISSING = object()
_NO_SETTING = "published generation requires an evidenced fiscal-year-end setting"
_RECORD_CHANGED = "stored qualification context no longer matches its settings record"
_FRESH_MAPPING = (
    "interpretations predate the current qualification setting or have different context; "
    "fresh mapping version required"
)
_RESERVED_COLLISION = (
    "interpretation transform trace uses conflicting reserved qualification context; "
    "fresh mapping version required"
)


class FirstPartyContextError(ValueError):
    """Qualification context cannot be proven from exact persisted identities."""


class _FrozenJsonObject(dict[str, object]):
    """A JSON-native object whose ordinary mutation operations always refuse."""

    def __setitem__(self, key: str, value: object) -> None:
        raise TypeError("qualification-context trace is immutable")

    def __delitem__(self, key: str) -> None:
        raise TypeError("qualification-context trace is immutable")

    def clear(self) -> None:
        raise TypeError("qualification-context trace is immutable")

    def pop(self, key: str, default: object = _MISSING) -> object:
        raise TypeError("qualification-context trace is immutable")

    def popitem(self) -> tuple[str, object]:
        raise TypeError("qualification-context trace is immutable")

    def setdefault(self, key: str, default: object = None) -> object:
        raise TypeError("qualification-context trace is immutable")

    def update(self, *args: object, **kwargs: object) -> None:
        raise TypeError("qualification-context trace is immutable")

    def __ior__(self, other: object) -> Self:  # type: ignore[override,misc]
        raise TypeError("qualification-context trace is immutable")


class FirstPartyGenerationContext(BaseModel):
    """One complete settings record and the digest of its canonical identity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    settings_record_id: int = Field(gt=0)
    entity_id: int = Field(gt=0)
    setting_key: SettingKey
    value_text: str
    evidence_input_id: int = Field(gt=0)
    recorded_at: datetime
    record_sha256: str = Field(pattern=_SHA256_PATTERN)

    @classmethod
    def from_record(cls, record: SettingsRecord) -> Self:
        """Freeze the complete identity of one already-persisted settings row."""
        payload = _record_payload(record)
        try:
            return cls(
                settings_record_id=record.id,
                entity_id=record.entity_id,
                setting_key=record.setting_key,
                value_text=record.value_text,
                evidence_input_id=record.evidence_input_id,
                recorded_at=record.recorded_at,
                record_sha256=canonical_sha256(payload),
            )
        except ValueError as exc:
            raise FirstPartyContextError("stored qualification setting is invalid") from exc

    @model_validator(mode="after")
    def _valid_identity(self) -> Self:
        """Accept only the intended setting and its derived record digest."""
        if self.setting_key is not SettingKey.FISCAL_YEAR_END_MONTH:
            raise ValueError("first-party generation context must be a fiscal-year-end setting")
        if not 1 <= self.fiscal_year_end_month <= 12:
            raise ValueError("fiscal-year-end month must be between 1 and 12")
        if canonical_sha256(self.record_payload()) != self.record_sha256:
            raise ValueError("qualification-context record digest does not match its fields")
        return self

    @property
    def fiscal_year_end_month(self) -> int:
        """The validated month used by interpretation and package construction."""
        try:
            return int(self.value_text)
        except ValueError as exc:
            raise ValueError("fiscal-year-end setting must be an integer month") from exc

    def record_payload(self) -> dict[str, object]:
        """Canonical JSON-safe fields whose digest identifies the settings row."""
        return {
            "settings_record_id": self.settings_record_id,
            "entity_id": self.entity_id,
            "setting_key": self.setting_key.value,
            "value_text": self.value_text,
            "evidence_input_id": self.evidence_input_id,
            "recorded_at": self.recorded_at.isoformat(),
        }

    def trace_payload(self) -> dict[str, object]:
        """The complete self-verifying object stored in an interpretation trace."""
        return {**self.record_payload(), "record_sha256": self.record_sha256}


def capture_first_party_generation_context(
    repository: EvidenceRepository, entity_id: int
) -> FirstPartyGenerationContext:
    """Capture the current setting and prove its complete row by exact id reload."""
    record = repository.settings_as_of(
        entity_id, SettingKey.FISCAL_YEAR_END_MONTH, repository.store_clock()
    )
    if record is None:
        raise FirstPartyContextError(_NO_SETTING)
    context = FirstPartyGenerationContext.from_record(record)
    reload_first_party_generation_context(repository, context)
    return context


def reload_first_party_generation_context(
    repository: EvidenceRepository, expected: FirstPartyGenerationContext
) -> SettingsRecord:
    """Reload the named settings row and require all persisted fields to match."""
    rows = repository.get_settings_records([expected.settings_record_id])
    if len(rows) != 1 or FirstPartyGenerationContext.from_record(rows[0]) != expected:
        raise FirstPartyContextError(_RECORD_CHANGED)
    return rows[0]


def bind_first_party_generation_context(
    row: Interpretation, context: FirstPartyGenerationContext
) -> Interpretation:
    """Add the reserved context trace without overwriting caller or mapping metadata."""
    trace = dict(row.transform_trace)
    existing = trace.get(QUALIFICATION_CONTEXT_TRACE_KEY, _MISSING)
    if existing is not _MISSING:
        if _context_from_payload(existing) != context:
            raise FirstPartyContextError(_RESERVED_COLLISION)
    trace[QUALIFICATION_CONTEXT_TRACE_KEY] = _FrozenJsonObject(context.trace_payload())
    values = {name: getattr(row, name) for name in type(row).model_fields}
    values["transform_trace"] = trace
    return Interpretation.model_validate(values)


def require_first_party_generation_context(
    rows: Sequence[Interpretation], expected: FirstPartyGenerationContext
) -> None:
    """Require every row to carry exactly the intended complete settings identity."""
    for row in rows:
        payload = row.transform_trace.get(QUALIFICATION_CONTEXT_TRACE_KEY, _MISSING)
        try:
            actual = _context_from_payload(payload)
        except FirstPartyContextError as exc:
            raise FirstPartyContextError(_FRESH_MAPPING) from exc
        if actual != expected:
            raise FirstPartyContextError(_FRESH_MAPPING)


def _context_from_payload(payload: object) -> FirstPartyGenerationContext:
    if payload is _MISSING:
        raise FirstPartyContextError("interpretation has no qualification-context trace")
    try:
        return FirstPartyGenerationContext.model_validate(payload)
    except (TypeError, ValueError) as exc:
        raise FirstPartyContextError("interpretation has malformed qualification context") from exc


def _record_payload(record: SettingsRecord) -> dict[str, object]:
    return {
        "settings_record_id": record.id,
        "entity_id": record.entity_id,
        "setting_key": record.setting_key.value,
        "value_text": record.value_text,
        "evidence_input_id": record.evidence_input_id,
        "recorded_at": record.recorded_at.isoformat(),
    }
