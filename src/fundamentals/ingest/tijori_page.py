"""Shared Tijori page seams: JSON-island collection and decoding.

Every Tijori company surface (financials, shareholding, ...) is one Django
template carrying ``json_script`` islands. This module owns the island-level
plumbing so each surface adapter only models its own payload. Transport lives in
``tijori_source`` because only that adapter fetches.
"""

from __future__ import annotations

import json
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
    """

    def __init__(self, island_ids: tuple[str, ...]) -> None:
        super().__init__(convert_charrefs=False)
        self._island_ids = frozenset(island_ids)
        self.islands: dict[str, str] = {}
        self.duplicates: set[str] = set()
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
        if island_id in self.islands:
            self.duplicates.add(island_id)
            return
        self._active_island = island_id
        self._chunks = []

    def handle_data(self, data: str) -> None:
        """Append a script body fragment for the active JSON island."""
        if self._active_island is not None:
            self._chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        """Finish collecting the active JSON island."""
        if tag == _SCRIPT_TAG and self._active_island is not None:
            self.islands[self._active_island] = "".join(self._chunks)
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
        if island_id in collector.duplicates:
            raise TijoriParseError(f"tijori JSON island {island_id!r} appears multiple times")
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
