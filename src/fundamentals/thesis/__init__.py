"""Multi-model, cross-verified thesis layer over the pipeline's validated facts.

Two strong models independently draft judgment (drivers, thesis impact,
falsifiers, risks, open questions) from the SAME validated, sourced facts; a
deterministic cross-verifier flags any number a model invented and queues the
divergences for human adjudication. Facts are ground truth; models supply only
opinion — never new numbers.
"""

from __future__ import annotations

from fundamentals.thesis.adapters import from_gold_file, from_stock_report
from fundamentals.thesis.claude_client import ClaudeOpusClient, claude_cli_available
from fundamentals.thesis.client import (
    ModelResponse,
    ThesisClientError,
    ThesisClientTimeoutError,
    ThesisModelClient,
)
from fundamentals.thesis.codex_client import CodexSolClient, codex_cli_available
from fundamentals.thesis.contracts import (
    CrossVerification,
    Discrepancy,
    DiscrepancyKind,
    DraftSection,
    DraftStatus,
    EpistemicClass,
    FactAnchor,
    JudgmentSection,
    ThesisDocument,
    ThesisDocumentStatus,
    ThesisDraft,
    Unknown,
    UnknownReason,
    UnsourcedClaim,
    ValidatedFact,
    ValidatedFactSet,
)
from fundamentals.thesis.draft_parser import failed_draft, parse_draft
from fundamentals.thesis.pipeline import build_thesis
from fundamentals.thesis.prompt import build_prompt
from fundamentals.thesis.render import render_thesis_document
from fundamentals.thesis.settings import (
    ClaudeClientConfig,
    CodexClientConfig,
    ThesisConfig,
    load_thesis_config,
)
from fundamentals.thesis.subprocess_runner import (
    CommandRunner,
    SubprocessResult,
    run_with_watchdog,
)
from fundamentals.thesis.verifier import cross_verify, extract_numbers, known_numbers

__all__ = [
    "ClaudeClientConfig",
    "ClaudeOpusClient",
    "CodexClientConfig",
    "CodexSolClient",
    "CommandRunner",
    "CrossVerification",
    "Discrepancy",
    "DiscrepancyKind",
    "DraftSection",
    "DraftStatus",
    "EpistemicClass",
    "FactAnchor",
    "JudgmentSection",
    "ModelResponse",
    "SubprocessResult",
    "ThesisClientError",
    "ThesisClientTimeoutError",
    "ThesisConfig",
    "ThesisDocument",
    "ThesisDocumentStatus",
    "ThesisDraft",
    "ThesisModelClient",
    "Unknown",
    "UnknownReason",
    "UnsourcedClaim",
    "ValidatedFact",
    "ValidatedFactSet",
    "build_prompt",
    "build_thesis",
    "claude_cli_available",
    "codex_cli_available",
    "cross_verify",
    "extract_numbers",
    "failed_draft",
    "from_gold_file",
    "from_stock_report",
    "known_numbers",
    "load_thesis_config",
    "parse_draft",
    "render_thesis_document",
    "run_with_watchdog",
]
