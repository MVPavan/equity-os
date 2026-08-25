"""Composition-root configuration for the multi-stock validation watchlist.

The Wave-1 validation universe (``docs/goals/fundamentals-multistock-validation-goal.md``)
is a set of structurally-different stocks, each cross-checked across every source
that carries it. This module loads the non-secret watchlist YAML into frozen
pydantic models at the composition root only — no business-logic module reads the
environment or filesystem for configuration (repo rule ``python/safety.md``).

Per stock it pins the resolvable source identifiers (NSE symbol, BSE scrip,
Screener slug, Tijori slug), the reviewed quarter, and the concept map (defaulting
to the shared Ind-AS ``in-bse-fin`` concepts from :mod:`fundamentals.api.config`).
Identifiers that could not be confirmed against a live filing are listed in
``needs_verification`` so the runner surfaces them instead of trusting a guess;
the runner still fails closed per stock rather than fabricating a value.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from fundamentals.api.config import ConceptsConfig, SourceFileConfig

DEFAULT_ENTITY_SCHEME = "nse-symbol"
TIJORI_SLUG_FIELD = "tijori_slug"
TIJORI_COMPANY_ID_FIELD = "tijori_company_id"
TIJORI_IDENTIFIER_FIELDS = (TIJORI_SLUG_FIELD, TIJORI_COMPANY_ID_FIELD)


class Wave(StrEnum):
    """The validation wave a stock belongs to.

    Waves partition the watchlist into independently-run cohorts. Each stock carries
    its own wave so ``validate --watchlist`` rolls each wave up under its own
    (per-wave) roll-up file: a run of one wave never clobbers another wave's roll-up,
    and a run can be scoped to a single wave via ``--wave``.
    """

    WAVE_1 = "Wave-1"
    WAVE_2 = "Wave-2"


class FilingTaxonomy(StrEnum):
    """The XBRL taxonomy a stock's reviewed quarter was filed under.

    BSE (and NSE) served results XBRL under ``in-bse-fin`` through FY25 Q3 and
    under the SEBI ``in-capmkt`` Integrated Filing format from Mar-2025 (FY25 Q4)
    onward. The runner parses with the superset of both taxonomies, so this field
    is a recorded expectation, not a dispatch switch.
    """

    IN_BSE_FIN = "in-bse-fin"
    IN_CAPMKT = "in-capmkt"


class SourceIdentifiers(BaseModel):
    """Resolvable per-stock source identifiers across every host.

    ``needs_verification`` names any identifier (e.g. ``"tijori_slug"``) whose
    value is a best-known guess not yet confirmed against a live filing, so the
    runner surfaces it rather than silently trusting it.

    ``accepted_entity_ids`` names as-filed XBRL context entity identifiers (e.g. a
    pre-rename NSE symbol such as ``"ZOMATO"``) that legitimately belong to this
    issuer. A filing made before a symbol rename still carries the OLD symbol, so
    this lets the NSE issuer guard accept it without weakening its rejection of a
    genuinely different company. Empty for the common (never-renamed) case.

    ``tijori_company_id`` is Tijori's numeric company id for the slug. It is
    required because Tijori's shareholding page publishes no identity island —
    its only deterministic marker is the ``comp_id`` attribute on the page
    heading, which is meaningless without a configured id to match it against.
    """

    model_config = ConfigDict(frozen=True)

    nse_symbol: str
    bse_scrip: str
    isin: str | None = None
    screener_slug: str
    tijori_slug: str
    tijori_company_id: int = Field(gt=0)
    us_listed: bool = False
    needs_verification: tuple[str, ...] = ()
    accepted_entity_ids: tuple[str, ...] = ()
    news_aliases: tuple[str, ...] = ()

    def unverified_tijori_fields(self) -> tuple[str, ...]:
        """Tijori identifiers flagged as unconfirmed, in declaration order.

        Every Tijori acquisition path binds a response to the issuer through
        both the slug and the company id, so an unconfirmed value in either one
        must stop the run rather than be trusted.
        """
        flagged = set(self.needs_verification)
        return tuple(field for field in TIJORI_IDENTIFIER_FIELDS if field in flagged)


class StockQuarter(BaseModel):
    """The reviewed quarter for one stock and its period anchors."""

    model_config = ConfigDict(frozen=True)

    label: str
    period_start: date
    period_end: date
    knowledge_cutoff: datetime
    filing_taxonomy: FilingTaxonomy = FilingTaxonomy.IN_BSE_FIN


class FixturePaths(BaseModel):
    """Optional repo-relative fixture instances for deterministic ``--fixture`` runs.

    Real Wave-1 stocks carry no committed fixtures (their source bytes are
    gitignored, private-use only); a missing path means the source is skipped in
    fixture mode. Live mode ignores these and fetches politely.
    """

    model_config = ConfigDict(frozen=True)

    nse: str | None = None
    nse_qoq: str | None = None
    nse_qoq_unavailable_reason: str | None = None
    nse_yoy: str | None = None
    nse_yoy_unavailable_reason: str | None = None
    bse: str | None = None
    screener: str | None = None
    tijori: str | None = None
    results_pdf: str | None = None


class StockConfig(BaseModel):
    """One watchlist stock: identity, reviewed quarter, and its concept map."""

    model_config = ConfigDict(frozen=True)

    name: str
    domain: str
    wave: Wave = Wave.WAVE_1
    identifiers: SourceIdentifiers
    quarter: StockQuarter
    entity_scheme: str = DEFAULT_ENTITY_SCHEME
    results_pdf: SourceFileConfig | None = None
    results_pdf_url: str | None = None
    fixtures: FixturePaths = Field(default_factory=FixturePaths)
    concepts: ConceptsConfig = Field(default_factory=ConceptsConfig)
    notes: tuple[str, ...] = ()

    @property
    def symbol(self) -> str:
        """The canonical NSE symbol used as the gold-file / report key."""
        return self.identifiers.nse_symbol


class WatchlistConfig(BaseModel):
    """The resolved multi-stock validation configuration.

    The wave is a per-stock property (:attr:`StockConfig.wave`), not a single
    top-level label, so a watchlist that spans multiple waves rolls each wave up
    independently rather than mixing them under one label.
    """

    model_config = ConfigDict(frozen=True)

    raw_dir: str
    stocks: tuple[StockConfig, ...]

    @model_validator(mode="after")
    def _check_tijori_company_ids_are_unique(self) -> WatchlistConfig:
        """Reject a config that binds two stocks to one Tijori company.

        The Tijori company id is an identity constraint, so a duplicate would
        silently let one issuer's page satisfy another issuer's request.
        """
        collisions = sorted(
            company_id
            for company_id, count in Counter(
                stock.identifiers.tijori_company_id for stock in self.stocks
            ).items()
            if count > 1
        )
        if collisions:
            shared = ", ".join(str(company_id) for company_id in collisions)
            raise ValueError(f"watchlist reuses {TIJORI_COMPANY_ID_FIELD} across stocks: {shared}")
        return self

    def repo_root(self, config_path: Path) -> Path:
        """Return the repository root given the loaded config file's path."""
        return config_path.resolve().parent.parent

    def waves(self) -> tuple[Wave, ...]:
        """The distinct waves present, in canonical :class:`Wave` order."""
        present = {stock.wave for stock in self.stocks}
        return tuple(wave for wave in Wave if wave in present)

    def stocks_for_wave(self, wave: Wave) -> tuple[StockConfig, ...]:
        """Return the stocks tagged with ``wave`` (empty when none)."""
        return tuple(stock for stock in self.stocks if stock.wave is wave)

    def stock(self, symbol: str) -> StockConfig:
        """Return the stock config for an NSE symbol, or fail closed."""
        wanted = symbol.upper()
        for stock in self.stocks:
            if stock.identifiers.nse_symbol.upper() == wanted:
                return stock
        known = ", ".join(stock.identifiers.nse_symbol for stock in self.stocks)
        raise ValueError(f"symbol {symbol!r} is not in the watchlist (known: {known})")


def load_watchlist_config(config_path: Path) -> WatchlistConfig:
    """Load and validate the non-secret watchlist YAML configuration."""
    data: Any = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return WatchlistConfig.model_validate(data)
