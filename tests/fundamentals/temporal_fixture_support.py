"""Trusted test composition for parsing/report fixtures, never historical proof.

The source clocks here are synthetic assertions supplied by the test, including
when report fixtures compose lawfully held PDFs. Production CLI keeps refusing
such historical possession. Only root runs caller fixtures needing private PDFs.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from fundamentals.api.pipeline import PipelineResult, run_pipeline
from fundamentals.api.source_admission import (
    PipelineSourceRefs,
    RetainedSourceRef,
    SourceCaptureEvidence,
)
from fundamentals.contracts.acquisition_outcome import OutcomeCode

FIXTURE_ACQUIRED_AT = datetime(2024, 7, 17, tzinfo=UTC)
FIXTURE_FIRST_SEEN_AT = datetime(2024, 7, 18, tzinfo=UTC)


class _FixtureResolver:
    def __init__(self, evidence: dict[str, SourceCaptureEvidence]) -> None:
        self.evidence = evidence

    def resolve(self, reference: RetainedSourceRef) -> SourceCaptureEvidence:
        return self.evidence[reference.source_id]


def _fixture_proof(kwargs: dict[str, Any]) -> dict[str, Any]:
    refs = {}
    evidence = {}
    for purpose in ("xbrl", "results_pdf", "transcript_pdf"):
        source = (
            kwargs[f"{purpose}_source_id"]
            if purpose == "xbrl"
            else kwargs[f"{purpose.removesuffix('_pdf')}_source_id"]
        )
        digest = kwargs["xbrl_sha256"] if purpose == "xbrl" else kwargs[f"{purpose}_sha256"]
        body = (
            kwargs["xbrl_bytes"]
            if purpose == "xbrl"
            else Path(kwargs[f"{purpose}_path"]).read_bytes()
        )
        ref = RetainedSourceRef(
            source_id=source,
            surface="synthetic-fixture",
            request_key="fixture",
            capture_id=f"20240717T000000.000000Z-{digest[:12]}",
            source_sha256=digest,
            record_sha256="ab" * 32,
        )
        refs[purpose] = ref
        evidence[source] = SourceCaptureEvidence(
            reference=ref,
            source_id=source,
            source_sha256=digest,
            body=body,
            acquired_at=FIXTURE_ACQUIRED_AT,
            first_seen_at=FIXTURE_FIRST_SEEN_AT,
            complete=True,
            outcome=OutcomeCode.OK,
            private_internal=True,
        )
    return dict(
        source_refs=PipelineSourceRefs(**refs), evidence_resolver=_FixtureResolver(evidence)
    )


def run_trusted_fixture_pipeline(**kwargs: Any) -> PipelineResult:
    """Admit asserted fixture evidence without editing config or source hashes."""
    config = kwargs["config"]
    xbrl = kwargs["xbrl_input"]
    proof = _fixture_proof(
        dict(
            xbrl_bytes=xbrl.xml_bytes,
            xbrl_source_id=xbrl.source_id,
            xbrl_sha256=xbrl.file_sha256,
            results_source_id=config.results_pdf.source_id,
            transcript_source_id=config.transcript_pdf.source_id,
            results_pdf_path=kwargs["results_pdf_path"],
            results_pdf_sha256=kwargs["results_pdf_sha256"],
            transcript_pdf_path=kwargs["transcript_pdf_path"],
            transcript_pdf_sha256=kwargs["transcript_pdf_sha256"],
        )
    )
    return run_pipeline(**kwargs, **proof)


def install_trusted_fixture_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch only a caller test's CLI composition; proves report behavior, not admission."""
    import fundamentals.api.cli as cli

    prepare: Callable[..., Any] = cli.prepare_pipeline_sources

    def trusted_fixture_preparation(**kwargs: Any) -> Any:
        if kwargs.get("source_refs") is not None or kwargs.get("evidence_resolver") is not None:
            raise AssertionError("fixture composition must not override native retained references")
        return prepare(**{**kwargs, **_fixture_proof(kwargs)})

    monkeypatch.setattr(cli, "prepare_pipeline_sources", trusted_fixture_preparation)
