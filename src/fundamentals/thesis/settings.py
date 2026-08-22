"""Composition-root configuration for the thesis model clients.

Following the repository convention (``fundamentals.api.config``), configuration
is a set of frozen pydantic models constructed at the composition root and
injected into the clients; no business-logic module reads the environment. The
one secret — an optional Anthropic API key used only by the API fallback — is a
:class:`~pydantic.SecretStr` so it never renders in a repr, log, or file, and is
supplied by the caller at construction time (never read here from ``os.environ``).

The repository's Python rules mention ``pydantic-settings`` + YAML; that package
is not a dependency of this project and the shipped code (``config.py``) actually
standardises on frozen ``BaseModel`` + explicit injection, so this module
conforms to the code, not the aspirational wording. ``load_thesis_config`` mirrors
``config.load_config`` for the YAML path when a file is supplied.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, SecretStr

# Task-specified Codex invocation defaults (see .claude/commands/use-codex.md and
# the build brief): read-only, high reasoning effort, web search on.
DEFAULT_CODEX_MODEL = "gpt-5.6-sol"
DEFAULT_CODEX_EFFORT = "high"
DEFAULT_CODEX_SANDBOX = "read-only"
DEFAULT_CODEX_EXECUTABLE = "codex"

# Opus is the second, independent model (methodology memory: Claude Opus + GPT
# Sol). ``None`` lets the ``claude`` CLI pick its configured default; set a model
# id to pin Opus explicitly.
DEFAULT_CLAUDE_MODEL: str | None = "claude-opus-4-1"
DEFAULT_CLAUDE_OUTPUT_FORMAT = "text"
DEFAULT_CLAUDE_EXECUTABLE = "claude"

# A single model call is bounded by the watchdog; on timeout it is killed and
# reissued exactly once before the layer proceeds fail-closed without that side.
DEFAULT_TIMEOUT_SECONDS = 600
DEFAULT_RETRIES = 1

# Exactly two independent models run concurrently; concurrency is bounded, never
# an unbounded fan-out (repo safety rule).
DEFAULT_MAX_WORKERS = 2


class CodexClientConfig(BaseModel):
    """Parameters for the Codex (GPT-5.x Sol) thesis client."""

    model_config = ConfigDict(frozen=True)

    model: str = DEFAULT_CODEX_MODEL
    reasoning_effort: str = DEFAULT_CODEX_EFFORT
    web_search: bool = True
    sandbox: str = DEFAULT_CODEX_SANDBOX
    executable: str = DEFAULT_CODEX_EXECUTABLE
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    retries: int = DEFAULT_RETRIES


class ClaudeClientConfig(BaseModel):
    """Parameters for the Claude Opus thesis client (CLI-first, API fallback)."""

    model_config = ConfigDict(frozen=True)

    model: str | None = DEFAULT_CLAUDE_MODEL
    output_format: str = DEFAULT_CLAUDE_OUTPUT_FORMAT
    executable: str = DEFAULT_CLAUDE_EXECUTABLE
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    retries: int = DEFAULT_RETRIES
    use_api: bool = False
    api_key: SecretStr | None = None
    api_max_tokens: int = 4096


class ThesisConfig(BaseModel):
    """The full thesis-layer configuration assembled at the composition root."""

    model_config = ConfigDict(frozen=True)

    codex: CodexClientConfig = CodexClientConfig()
    claude: ClaudeClientConfig = ClaudeClientConfig()
    max_workers: int = DEFAULT_MAX_WORKERS


def load_thesis_config(config_path: Path) -> ThesisConfig:
    """Load and validate non-secret thesis configuration from a YAML file.

    Secrets are never loaded from YAML; inject an ``api_key`` on the returned
    config's ``claude`` sub-config at the composition root if the API fallback is
    used.
    """
    data: Any = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return ThesisConfig.model_validate(data or {})
