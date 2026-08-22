"""Codex (GPT-5.x Sol) thesis client: one independent judgment source.

Shells to the Codex CLI exactly as ``.claude/commands/use-codex.md`` prescribes —
read-only sandbox, high reasoning effort, web search on — and, critically, closes
stdin (``</dev/null``) to avoid the known interactive-hang bug. The command is
built from injected config and run under the shared watchdog; the runner is
injectable so command construction is unit-tested without invoking Codex.
"""

from __future__ import annotations

import shutil

import structlog

from fundamentals.thesis.client import ModelResponse
from fundamentals.thesis.settings import CodexClientConfig
from fundamentals.thesis.subprocess_runner import CommandRunner, run_with_watchdog

_LOGGER = structlog.get_logger("fundamentals.thesis.codex")

_CLIENT_NAME = "codex-sol"
_EXEC_SUBCOMMAND = "exec"
_MODEL_FLAG = "-m"
_CONFIG_FLAG = "-c"
_SANDBOX_FLAG = "-s"
_EFFORT_KEY = "model_reasoning_effort"
_WEB_SEARCH_KEY = "tools.web_search"


def codex_cli_available(executable: str = "codex") -> bool:
    """Whether the Codex CLI is resolvable on ``PATH``."""
    return shutil.which(executable) is not None


class CodexSolClient:
    """A :class:`ThesisModelClient` backed by the Codex ``exec`` CLI."""

    def __init__(
        self, config: CodexClientConfig, *, runner: CommandRunner = run_with_watchdog
    ) -> None:
        """Store config and the (injectable) watchdog runner."""
        self._config = config
        self._runner = runner

    @property
    def label(self) -> str:
        """The Codex model id recorded on the draft."""
        return self._config.model

    @property
    def name(self) -> str:
        """Short client name recorded on the draft."""
        return _CLIENT_NAME

    def build_command(self, prompt: str) -> list[str]:
        """Build the exact ``codex exec`` argv for ``prompt`` (prompt is positional)."""
        web_search = "true" if self._config.web_search else "false"
        return [
            self._config.executable,
            _EXEC_SUBCOMMAND,
            _MODEL_FLAG,
            self._config.model,
            _CONFIG_FLAG,
            f"{_EFFORT_KEY}={self._config.reasoning_effort}",
            _CONFIG_FLAG,
            f"{_WEB_SEARCH_KEY}={web_search}",
            _SANDBOX_FLAG,
            self._config.sandbox,
            prompt,
        ]

    def generate(self, prompt: str) -> ModelResponse:
        """Run Codex read-only with stdin closed and return its stdout answer."""
        command = self.build_command(prompt)
        _LOGGER.info("codex_call_start", model=self._config.model, prompt_chars=len(prompt))
        result = self._runner(
            command,
            timeout_seconds=self._config.timeout_seconds,
            retries=self._config.retries,
            stdin_devnull=True,
        )
        _LOGGER.info(
            "codex_call_done",
            model=self._config.model,
            duration_s=round(result.duration_seconds, 1),
        )
        return ModelResponse(text=result.stdout, duration_seconds=result.duration_seconds)
