"""Shared Tijori page seams: JSON-island collection and decoding.

Every Tijori company surface (financials, shareholding, ...) is one Django
template carrying ``json_script`` islands. This module owns the island-level
plumbing so each surface adapter only models its own payload. Transport lives in
``tijori_source`` because only that adapter fetches.
"""

from __future__ import annotations

import json
from collections import Counter
from decimal import Decimal
from html.parser import HTMLParser
from typing import Any

import structlog

from fundamentals.ingest.tijori_tables import (
    TijoriParseError,
    TijoriUnparseableIsland,
)

_LOGGER = structlog.get_logger(__name__)

_SCRIPT_TAG = "script"
_ISLAND_ID_ATTRIBUTE = "id"
_ISLAND_TYPE_ATTRIBUTE = "type"
_ISLAND_CONTENT_TYPE = "application/json"


class JsonScriptCollector(HTMLParser):
    """Collect named Django JSON islands without interpreting their payloads.

    Entity conversion stays off: an island body is JSON source text, so decoding
    character references inside it would corrupt the payload.

    Every occurrence of a requested id is collected, not just the first, because
    whether a repeated island is safe depends on what the repeats say.
    ``duplicates`` names ids the page rendered more than once;
    ``divergent_duplicates`` names the subset whose bodies actually disagree.
    """

    def __init__(self, island_ids: tuple[str, ...]) -> None:
        super().__init__(convert_charrefs=False)
        self._island_ids = frozenset(island_ids)
        self.islands: dict[str, str] = {}
        self.duplicates: set[str] = set()
        self.divergent_duplicates: set[str] = set()
        self.occurrences: Counter[str] = Counter()
        self._active_island: str | None = None
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Start collecting a requested application/json script body."""
        if tag != _SCRIPT_TAG:
            return
        attributes = dict(attrs)
        island_id = attributes.get(_ISLAND_ID_ATTRIBUTE)
        content_type = attributes.get(_ISLAND_TYPE_ATTRIBUTE)
        if island_id not in self._island_ids or content_type is None:
            return
        if content_type.strip().lower() != _ISLAND_CONTENT_TYPE:
            return
        self._active_island = island_id
        self._chunks = []

    def handle_data(self, data: str) -> None:
        """Append a script body fragment for the active JSON island."""
        if self._active_island is not None:
            self._chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        """Finish the active JSON island, classifying a repeat by its content."""
        if tag != _SCRIPT_TAG or self._active_island is None:
            return
        island_id = self._active_island
        body = "".join(self._chunks)
        self.occurrences[island_id] += 1
        first_body = self.islands.get(island_id)
        if first_body is None:
            self.islands[island_id] = body
        else:
            self.duplicates.add(island_id)
            if first_body.strip() != body.strip():
                self.divergent_duplicates.add(island_id)
        self._active_island = None
        self._chunks = []


def decode_document(raw: bytes, *, page_label: str) -> str:
    """Decode one Tijori page as UTF-8 HTML, naming the surface when it is not."""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise TijoriParseError(f"tijori {page_label} page is not UTF-8 HTML") from error


def collect_islands(
    document: str,
    *,
    required_islands: tuple[str, ...],
    optional_islands: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Collect and deserialize the named islands of one already-decoded page."""
    collector = JsonScriptCollector(required_islands + optional_islands)
    collector.feed(document)
    collector.close()
    return load_islands(collector, required_islands, optional_islands)


def load_islands(
    collector: JsonScriptCollector,
    required_islands: tuple[str, ...],
    optional_islands: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Deserialize named JSON islands with isolated failure reasons."""
    decoded: dict[str, Any] = {}
    for island_id in required_islands + optional_islands:
        optional = island_id in optional_islands
        if island_id in collector.divergent_duplicates:
            raise TijoriParseError(
                f"tijori JSON island {island_id!r} appears multiple times with differing content"
            )
        if island_id in collector.duplicates:
            # FACT (live overview page, 2026-08-25): the template renders both
            # ``is_auth`` and ``plan_details`` in two layout contexts with
            # byte-identical bodies. Identical repeats carry no ambiguity, so
            # they collapse to one; only disagreeing repeats are unresolvable.
            _LOGGER.info(
                "tijori_identical_island_duplicate_collapsed",
                island=island_id,
                occurrences=collector.occurrences[island_id],
            )
        raw_island = collector.islands.get(island_id)
        if raw_island is None:
            if optional:
                _LOGGER.warning("tijori_optional_island_missing", island=island_id)
                continue
            raise TijoriParseError(f"tijori JSON island {island_id!r} is missing")
        try:
            decoded[island_id] = json.loads(raw_island, parse_float=Decimal)
        except json.JSONDecodeError as error:
            if optional:
                _LOGGER.warning(
                    "tijori_optional_island_unparseable",
                    island=island_id,
                    error=error.msg,
                    pos=error.pos,
                    lineno=error.lineno,
                    colno=error.colno,
                )
                decoded[island_id] = TijoriUnparseableIsland(island_id=island_id, error=str(error))
                continue
            raise TijoriParseError(f"tijori JSON island {island_id!r} is unparseable") from error
    return decoded
