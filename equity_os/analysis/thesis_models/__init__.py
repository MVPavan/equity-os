"""Multi-model, cross-verified thesis layer over the pipeline's validated facts.

Two strong models independently draft judgment (drivers, thesis impact,
falsifiers, risks, open questions) from the SAME validated, sourced facts; a
deterministic cross-verifier flags any number a model invented and queues the
divergences for human adjudication. Facts are ground truth; models supply only
opinion — never new numbers.
"""

from __future__ import annotations

from equity_os.analysis.thesis_models.adapters import from_gold_file, from_stock_report
from equity_os.analysis.thesis_models.adjudication import (
    AdjudicationEntry,
    AdjudicationQueue,
    AdjudicationStatus,
    discrepancy_id,
    entries_for_stock_quarter,
    load_adjudication_queue,
    resolve_adjudication,
    upsert_discrepancies,
)
from equity_os.analysis.thesis_models.claude_client import ClaudeOpusClient, claude_cli_available
from equity_os.analysis.thesis_models.client import (
    ModelResponse,
    ThesisClientError,
    ThesisClientTimeoutError,
    ThesisModelClient,
)
from equity_os.analysis.thesis_models.codex_client import CodexSolClient, codex_cli_available
from equity_os.analysis.thesis_models.contracts import (
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
from equity_os.analysis.thesis_models.draft_parser import failed_draft, parse_draft
from equity_os.analysis.thesis_models.pipeline import build_thesis
from equity_os.analysis.thesis_models.prompt import build_prompt
from equity_os.analysis.thesis_models.render import (
    apply_adjudications_to_markdown,
    render_persisted_adjudication_sections,
    render_thesis_document,
)
from equity_os.analysis.thesis_models.settings import (
    ClaudeClientConfig,
    CodexClientConfig,
    ThesisConfig,
    load_thesis_config,
)
from equity_os.analysis.thesis_models.subprocess_runner import (
    CommandRunner,
    SubprocessResult,
    run_with_watchdog,
)
from equity_os.analysis.thesis_models.verifier import cross_verify, extract_numbers, known_numbers

__all__ = [
    "AdjudicationEntry",
    "AdjudicationQueue",
    "AdjudicationStatus",
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
    "apply_adjudications_to_markdown",
    "build_prompt",
    "build_thesis",
    "claude_cli_available",
    "codex_cli_available",
    "cross_verify",
    "discrepancy_id",
    "entries_for_stock_quarter",
    "extract_numbers",
    "failed_draft",
    "from_gold_file",
    "from_stock_report",
    "known_numbers",
    "load_thesis_config",
    "load_adjudication_queue",
    "parse_draft",
    "render_thesis_document",
    "render_persisted_adjudication_sections",
    "resolve_adjudication",
    "run_with_watchdog",
    "upsert_discrepancies",
]
