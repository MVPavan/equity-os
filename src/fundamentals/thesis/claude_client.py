"""Claude Opus thesis client: the second, independent judgment source.

Prefers the headless ``claude -p "<prompt>" --output-format text`` CLI (no extra
dependency, uses the workstation's existing Claude auth). When ``use_api`` is set
it falls back to the Anthropic Messages API, importing the SDK lazily so the CLI
path and the tests never require the package. The API key is a
:class:`~pydantic.SecretStr`, read only via ``get_secret_value`` at call time and
never logged.
"""

from __future__ import annotations

import importlib
import shutil
import time
from typing import Any

import structlog

from fundamentals.thesis.client import ModelResponse, ThesisClientError
from fundamentals.thesis.settings import ClaudeClientConfig
from fundamentals.thesis.subprocess_runner import CommandRunner, run_with_watchdog

_LOGGER = structlog.get_logger("fundamentals.thesis.claude")

_CLIENT_NAME = "claude-opus"
_FALLBACK_LABEL = "claude-opus"
_PRINT_FLAG = "-p"
_OUTPUT_FORMAT_FLAG = "--output-format"
_MODEL_FLAG = "--model"


def claude_cli_available(executable: str = "claude") -> bool:
    """Whether the Claude Code CLI is resolvable on ``PATH``."""
    return shutil.which(executable) is not None


class ClaudeOpusClient:
    """A :class:`ThesisModelClient` backed by the ``claude -p`` CLI or the API."""

    def __init__(
        self, config: ClaudeClientConfig, *, runner: CommandRunner = run_with_watchdog
    ) -> None:
        """Store config and the (injectable) watchdog runner."""
        self._config = config
        self._runner = runner

    @property
    def label(self) -> str:
        """The Opus model id recorded on the draft (or a stable fallback label)."""
        return self._config.model or _FALLBACK_LABEL

    @property
    def name(self) -> str:
        """Short client name recorded on the draft."""
        return _CLIENT_NAME

    def build_command(self, prompt: str) -> list[str]:
        """Build the ``claude -p`` argv for ``prompt`` (prompt is positional)."""
        command = [
            self._config.executable,
            _PRINT_FLAG,
            prompt,
            _OUTPUT_FORMAT_FLAG,
            self._config.output_format,
        ]
        if self._config.model is not None:
            command.extend([_MODEL_FLAG, self._config.model])
        return command

    def generate(self, prompt: str) -> ModelResponse:
        """Return Opus's answer via the API fallback or the headless CLI."""
        if self._config.use_api:
            return self._generate_via_api(prompt)
        command = self.build_command(prompt)
        _LOGGER.info("claude_call_start", model=self.label, prompt_chars=len(prompt))
        result = self._runner(
            command,
            timeout_seconds=self._config.timeout_seconds,
            retries=self._config.retries,
            stdin_devnull=True,
        )
        _LOGGER.info(
            "claude_call_done", model=self.label, duration_s=round(result.duration_seconds, 1)
        )
        return ModelResponse(text=result.stdout, duration_seconds=result.duration_seconds)

    def _generate_via_api(self, prompt: str) -> ModelResponse:
        """Call the Anthropic Messages API (SDK imported lazily; key never logged)."""
        if self._config.api_key is None:
            raise ThesisClientError("Anthropic API fallback requires an injected api_key")
        if self._config.model is None:
            raise ThesisClientError("Anthropic API fallback requires an explicit model id")
        try:
            module = importlib.import_module("anthropic")
        except ImportError as error:
            raise ThesisClientError(
                "Anthropic API fallback needs the 'anthropic' package (not installed); "
                "use the claude CLI path instead"
            ) from error
        start = time.monotonic()
        text = self._call_api(module, prompt, self._config.api_key.get_secret_value())
        return ModelResponse(text=text, duration_seconds=time.monotonic() - start)

    def _call_api(self, module: Any, prompt: str, api_key: str) -> str:
        """Invoke the SDK and concatenate the returned text blocks into one string.

        ``module`` is the dynamically imported, untyped Anthropic SDK, so its
        surface is ``Any``; the returned text is coerced back to ``str`` here so no
        dynamic value escapes this boundary.
        """
        client = module.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=self._config.model,
            max_tokens=self._config.api_max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        parts: list[str] = []
        for block in getattr(message, "content", []):
            block_text = getattr(block, "text", None)
            if isinstance(block_text, str):
                parts.append(block_text)
        return "".join(parts)
