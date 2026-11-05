"""Bounded, owner-selected chat completion boundary shared by labels and spans."""

import json
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener

from pydantic import BaseModel, ConfigDict, SecretStr

from equity_os.sourcing.transport.http_session import NoRedirectHandler


class ModelNotSelected(Exception):  # noqa: N818 - plan interface
    """Runtime use is refused until the owner selects a model."""


class ModelSettings(BaseModel):
    """Non-secret settings injected by the composition root."""

    model_config = ConfigDict(frozen=True)
    model_id: str | None
    base_url: str
    key_file: str
    prompt_version: str
    dictionary_version: str


class ModelReply(BaseModel):
    """Raw completion and provider-reported token usage."""

    model_config = ConfigDict(frozen=True)
    text: str
    input_tokens: int
    output_tokens: int


class LabelModel(Protocol):
    """The only model capability exposed to proposal code."""

    model_id: str

    def complete(self, system: str, user: str) -> ModelReply:
        """Propose text without acquiring or calculating vendor values."""
        ...


class ChatCompletionsModel:
    """One OpenAI-compatible POST with bounded bytes, tokens, retries and timeout."""

    def __init__(
        self,
        model_id: str,
        base_url: str,
        api_key: SecretStr,
        *,
        timeout_seconds: float = 60.0,
        max_response_bytes: int = 200_000,
        max_output_tokens: int = 512,
        max_retries: int = 2,
    ) -> None:
        endpoint = urlsplit(base_url)
        loopback = endpoint.scheme == "http" and endpoint.hostname in {"localhost", "127.0.0.1"}
        if endpoint.scheme != "https" and not loopback:
            raise ValueError("model endpoint requires HTTPS, or plain HTTP on this machine")
        self.model_id, self.base_url, self.api_key = model_id, base_url, api_key
        self.timeout_seconds, self.max_response_bytes = timeout_seconds, max_response_bytes
        self.max_output_tokens, self.max_retries = max_output_tokens, max_retries

    def complete(self, system: str, user: str) -> ModelReply:
        """Return raw text, refusing oversized or truncated completions."""
        messages = [dict(role="system", content=system), dict(role="user", content=user)]
        payload = dict(model=self.model_id, messages=messages, max_tokens=self.max_output_tokens)
        request = Request(
            self.base_url.rstrip("/") + "/chat/completions",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": "Bearer " + self.api_key.get_secret_value(),
                "Content-Type": "application/json",
            },
            method="POST",
        )
        opener = build_opener(NoRedirectHandler())
        for attempt in range(self.max_retries + 1):
            try:
                with opener.open(request, timeout=self.timeout_seconds) as response:
                    raw = response.read(self.max_response_bytes + 1)
                break
            except (URLError, TimeoutError) as error:
                if (
                    isinstance(error, HTTPError) and error.code != 429 and error.code < 500
                ) or attempt == self.max_retries:
                    raise
        if len(raw) > self.max_response_bytes:
            raise ValueError("model response exceeds byte bound")
        payload = json.loads(raw)
        choice, usage = payload["choices"][0], payload["usage"]
        if choice["finish_reason"] != "stop" or usage["completion_tokens"] > self.max_output_tokens:
            raise ValueError("model response exceeds token bound or is incomplete")
        return ModelReply(
            text=choice["message"]["content"],
            input_tokens=usage["prompt_tokens"],
            output_tokens=usage["completion_tokens"],
        )
