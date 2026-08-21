"""Composition-root configuration for the Fundamentals pipeline.

Non-secret settings load from ``config/fundamentals.yaml`` into frozen pydantic
models here, at the composition root only. No business-logic module reads the
environment or the filesystem for configuration — everything is injected at
construction time (repo rule ``python/safety.md``). Repo-relative paths are
resolved against the repository root (the parent of the ``config`` directory).
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

_DEFAULT_XBRL_ALIASES: dict[str, str] = {
    "http://www.nseindia.com/NSESymbol": "nse-symbol",
}


class XbrlMode(StrEnum):
    """How the pipeline obtains the NSE Ind AS XBRL instance."""

    LOCAL = "local"
    LIVE = "live"


class IssuerConfig(BaseModel):
    """Issuer identity and its canonical comparison-key entity scheme."""

    model_config = ConfigDict(frozen=True)

    name: str
    nse_symbol: str
    entity_scheme: str


class QuarterConfig(BaseModel):
    """The issuer quarter under review and its bitemporal anchors."""

    model_config = ConfigDict(frozen=True)

    issuer_quarter: str
    program_quarter: str
    label: str
    period_start: date
    period_end: date
    knowledge_cutoff: datetime


class SourceFileConfig(BaseModel):
    """A held source file: its id, filename under ``raw_dir``, and pinned sha256."""

    model_config = ConfigDict(frozen=True)

    source_id: str
    filename: str
    sha256: str


class XbrlConfig(BaseModel):
    """NSE Ind AS XBRL settings for local (held) or live (polite) retrieval."""

    model_config = ConfigDict(frozen=True)

    source_id: str
    mode: XbrlMode = XbrlMode.LOCAL
    local_path: str
    symbol: str
    timeout_seconds: int = 15
    max_retries: int = 3
    retry_backoff_seconds: float = 2.0
    entity_scheme_aliases: dict[str, str] = Field(
        default_factory=lambda: dict(_DEFAULT_XBRL_ALIASES)
    )


class SecConfig(BaseModel):
    """SEC 20-F retrospective annual cross-check settings (opt-in, network)."""

    model_config = ConfigDict(frozen=True)

    enabled: bool = False
    user_agent: str = "EquityOS Research (mvpavan42@gmail.com)"
    cik: int = 1067491
    request_timeout_seconds: float = 30.0
    max_retries: int = 3


class FundamentalsConfig(BaseModel):
    """The full, resolved composition-root configuration."""

    model_config = ConfigDict(frozen=True)

    issuer: IssuerConfig
    quarter: QuarterConfig
    raw_dir: str
    store_db: str
    results_pdf: SourceFileConfig
    transcript_pdf: SourceFileConfig
    xbrl: XbrlConfig
    sec: SecConfig = Field(default_factory=SecConfig)

    def repo_root(self, config_path: Path) -> Path:
        """Return the repository root given the loaded config file's path."""
        return config_path.resolve().parent.parent

    def results_pdf_path(self, config_path: Path) -> Path:
        """Absolute path to the held results PDF."""
        return self.repo_root(config_path) / self.raw_dir / self.results_pdf.filename

    def transcript_pdf_path(self, config_path: Path) -> Path:
        """Absolute path to the held transcript PDF."""
        return self.repo_root(config_path) / self.raw_dir / self.transcript_pdf.filename

    def xbrl_local_path(self, config_path: Path) -> Path:
        """Absolute path to the held/synthetic XBRL instance."""
        return self.repo_root(config_path) / self.xbrl.local_path

    def store_db_path(self, config_path: Path) -> str:
        """Resolve the store DB path (``:memory:`` passes through)."""
        if self.store_db == ":memory:":
            return self.store_db
        return str(self.repo_root(config_path) / self.store_db)


def load_config(config_path: Path) -> FundamentalsConfig:
    """Load and validate the non-secret YAML configuration."""
    data: Any = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return FundamentalsConfig.model_validate(data)
