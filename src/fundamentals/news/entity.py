"""Fail-closed issuer matching for NSE and media news occurrences."""

from __future__ import annotations

import re

from fundamentals.contracts.news import NewsEntity

_NON_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")


def _normalized(value: str) -> str:
    """Normalize an identity token for exact and phrase matching."""
    return " ".join(_NON_ALPHANUMERIC.sub(" ", value.casefold()).split())


def _unique(matches: list[NewsEntity]) -> NewsEntity | None:
    """Return the sole distinct match, otherwise fail closed."""
    by_symbol = {entity.symbol.upper(): entity for entity in matches}
    return next(iter(by_symbol.values())) if len(by_symbol) == 1 else None


def resolve_news_entity(
    entities: tuple[NewsEntity, ...],
    *,
    isin: str | None = None,
    scrip: str | None = None,
    symbol: str | None = None,
    title: str = "",
) -> tuple[NewsEntity | None, str | None, bool]:
    """Resolve an entity while preserving unverifiable and contradictory evidence."""
    candidates: list[NewsEntity] = []
    notes: list[str] = []
    wanted_isin = isin.strip().upper() if isin else ""
    wanted_scrip = scrip.strip().upper() if scrip else ""
    wanted_symbol = symbol.strip().upper() if symbol else ""

    if wanted_isin:
        isin_matches = [entity for entity in entities if (entity.isin or "").upper() == wanted_isin]
        if isin_matches:
            candidates.extend(isin_matches)
        else:
            notes.append(f"unverified ISIN {wanted_isin} fell through to lower identifier")
    if wanted_scrip:
        candidates.extend(entity for entity in entities if entity.bse_scrip.upper() == wanted_scrip)
    if wanted_symbol:
        candidates.extend(entity for entity in entities if entity.symbol.upper() == wanted_symbol)

    normalized_title = f" {_normalized(title)} "
    alias_matches: list[NewsEntity] = []
    for candidate_entity in entities:
        if any(
            len(normalized_alias.split()) >= 2 and f" {normalized_alias} " in normalized_title
            for candidate in candidate_entity.aliases
            if (normalized_alias := _normalized(candidate))
        ):
            alias_matches.append(candidate_entity)
    candidates.extend(alias_matches)

    resolved_entity = _unique(candidates)
    candidate_symbols = {candidate.symbol.upper() for candidate in candidates}
    contradictory = len(candidate_symbols) > 1
    if resolved_entity is not None and wanted_isin and resolved_entity.isin is not None:
        contradictory = contradictory or resolved_entity.isin.upper() != wanted_isin
    if resolved_entity is not None and wanted_scrip:
        contradictory = contradictory or resolved_entity.bse_scrip.upper() != wanted_scrip
    if contradictory:
        return None, "contradictory issuer identifiers", True
    return resolved_entity, "; ".join(notes) or None, False


def match_news_entity(
    entities: tuple[NewsEntity, ...],
    *,
    isin: str | None = None,
    scrip: str | None = None,
    symbol: str | None = None,
    title: str = "",
) -> NewsEntity | None:
    """Return the uniquely resolved entity without its matching evidence."""
    entity, _, contradictory = resolve_news_entity(
        entities, isin=isin, scrip=scrip, symbol=symbol, title=title
    )
    return None if contradictory else entity
