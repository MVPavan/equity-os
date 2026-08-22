"""The injectable thesis-model client contract shared by every implementation.

A :class:`ThesisModelClient` takes one deterministic prompt and returns text.
Nothing about *how* the text is produced (a CLI subprocess, an HTTP API, or a
fake in a test) leaks past this seam, so the pipeline can run two real models
concurrently in production and two fakes deterministically under test.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict


class ThesisClientError(RuntimeError):
    """A model call failed (non-zero exit, unreachable tool, or API error)."""


class ThesisClientTimeoutError(ThesisClientError):
    """A model call exceeded its watchdog budget after the permitted retries."""


class ModelResponse(BaseModel):
    """One model's raw text answer plus how long the call took."""

    model_config = ConfigDict(frozen=True)

    text: str
    duration_seconds: float


@runtime_checkable
class ThesisModelClient(Protocol):
    """A source of model *judgment*: one prompt in, one text answer out."""

    @property
    def label(self) -> str:
        """Stable model label recorded on the produced draft (e.g. ``gpt-5.6-sol``)."""
        ...

    @property
    def name(self) -> str:
        """Short client name recorded on the produced draft (e.g. ``codex-sol``)."""
        ...

    def generate(self, prompt: str) -> ModelResponse:
        """Return the model's text answer for ``prompt`` or raise a client error."""
        ...
