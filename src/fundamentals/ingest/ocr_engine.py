"""Local OCR engine port and adapter for the PDF recovery lane.

Defines the engine-agnostic :class:`OcrToken` (one recognized region: text, box in
image pixels, confidence) and the :class:`OcrEngine` protocol that the extract-layer
OCR recovery lane calls, plus :class:`RapidOcrEngine`, a concrete LOCAL adapter over
``rapidocr-onnxruntime`` (ONNX, on-CPU, deterministic, transmits nothing).

The heavy ``rapidocr`` dependency is the optional ``ocr`` extra: it is imported
LAZILY on first use and cached, so importing this module (and running
``mypy --strict``) never requires it, and a default install without the extra can
still import everything. Using :class:`RapidOcrEngine` without the extra raises
:class:`OcrEngineUnavailableError`, which the caller treats as "OCR unavailable"
and falls back to the text lane (fail closed) — it never fabricates a number.

This module intentionally imports nothing from the ``extract`` layer: the OCR token
type lives beside its adapter here (mirroring
:class:`~fundamentals.ingest.pdf_source.PageWord`), so the dependency between the
layers stays one-directional (``extract`` -> ``ingest``) with no import cycle.
"""

from __future__ import annotations

import tempfile
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict

_OCR_MISSING_MESSAGE = "local OCR requires the optional 'ocr' extra (install rapidocr-onnxruntime)"


class OcrEngineUnavailableError(RuntimeError):
    """Raised when a local OCR engine is used without its optional dependency installed."""


class OcrToken(BaseModel):
    """One recognized text region from a local OCR engine: text, box, confidence.

    The box is the axis-aligned bounding box in image pixels; ``confidence`` is the
    engine's per-region score in ``[0, 1]``. Engine-agnostic so Tesseract (word
    boxes) or an ONNX PP-OCR engine (line/cell boxes) both map onto it.
    """

    model_config = ConfigDict(frozen=True)

    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    confidence: float


class OcrEngine(Protocol):
    """A LOCAL, deterministic OCR engine: page-image bytes -> recognized tokens.

    Implementations must run entirely on this machine and transmit nothing — the
    hard constraint of this lane is that a rendered statement image is never sent to
    a hosted/remote model. ``recognize`` takes PNG bytes and returns every detected
    region with its box (image pixels) and confidence.
    """

    def recognize(self, image_png: bytes) -> tuple[OcrToken, ...]:
        """Recognize text regions in a rendered page image (PNG bytes)."""
        ...


class RapidOcrEngine:
    """Local RapidOCR (ONNX, on-CPU) adapter implementing the :class:`OcrEngine` protocol.

    ``rapidocr-onnxruntime`` is the optional ``ocr`` extra, imported lazily on the
    first :meth:`recognize` call and cached thereafter, so constructing the adapter
    is cheap and importing this module never pulls the heavy dependency. When the
    extra is not installed, :meth:`recognize` raises :class:`OcrEngineUnavailableError`
    so the caller can fall back to the text lane rather than fail hard. Nothing is
    transmitted — the image is OCR'd entirely on-CPU in this process.
    """

    def __init__(self) -> None:
        self._engine: Any | None = None

    def _ensure_engine(self) -> Any:
        """Lazily build and cache the RapidOCR engine, or fail closed if the extra is absent."""
        if self._engine is None:
            try:
                from rapidocr_onnxruntime import RapidOCR  # type: ignore[import-untyped]
            except ImportError as error:
                raise OcrEngineUnavailableError(_OCR_MISSING_MESSAGE) from error
            self._engine = RapidOCR()
        return self._engine

    def recognize(self, image_png: bytes) -> tuple[OcrToken, ...]:
        """OCR a rendered page image locally into positioned tokens (never transmitted)."""
        engine = self._ensure_engine()
        with tempfile.NamedTemporaryFile(suffix=".png") as handle:
            handle.write(image_png)
            handle.flush()
            result, _elapsed = engine(handle.name)
        if not result:
            return ()
        tokens: list[OcrToken] = []
        for box, text, score in result:
            xs = [float(point[0]) for point in box]
            ys = [float(point[1]) for point in box]
            tokens.append(
                OcrToken(
                    text=str(text),
                    x0=min(xs),
                    y0=min(ys),
                    x1=max(xs),
                    y1=max(ys),
                    confidence=float(score),
                )
            )
        return tuple(tokens)
