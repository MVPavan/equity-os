"""Rendered-HTML collection for the overview page's revenue-mix break-ups.

Every other overview section reads a ``json_script`` island. This one does not:
the revenue mix is server-rendered markup that carries its data in an element
attribute::

    <section id="revenuemix">
      <div class="rmix_graph_block" company-id="4280">
        <h4>Product Wise Break-Up</h4>
        <div chart-id="4280"
             chart-data="[[&quot;Jewelry&quot;, 88.37], [&quot;Watches&quot;, 8.12]]"></div>
      </div>
      ...
    </section>

That is attribute-embedded tabular data, so the slices anchor as
``SourceAnchorType.HTML_TABLE`` against ``table_id="rmix:<chart-id>"`` — they
are re-found by fetching the page and reading a named attribute of a named
element, which is a markup retrieval procedure, not an island one.

LIVE FACT — ``company-id`` IS NOT AN IDENTITY (TITAN, company 81, verified
2026-08-25): the ``company-id`` attribute on ``rmix_graph_block`` duplicates the
block's ``chart-id`` — on TITAN's Product Wise block both read ``4280``, and
neither is the page's company id (81). It is a misnamed chart identifier, so it
must NEVER be checked against, or read as, the issuer. This module previously
refused every live block on exactly that mistake. Identity is established once,
by the island gate in :mod:`fundamentals.ingest.tijori_overview`, before any
section is built; nothing in this markup can strengthen or contradict it. The
attribute is still source data and is retained verbatim under a name that
records the misnomer rather than repeating it.

Selection follows the same doctrine as the shareholding table: the DOM id
``revenuemix`` finds the section, and the structural expectations then prove
that what the id pointed at really is the revenue mix. A block that does not
satisfy them is retained with its reason rather than dropped, and never fails
the page around it — the section is one of ten, and the other nine do not
depend on it.

The typed contracts live in :mod:`fundamentals.ingest.tijori_overview_models`;
page-level orchestration lives in :mod:`fundamentals.ingest.tijori_overview`.
"""

from __future__ import annotations

import json
from decimal import Decimal
from html.parser import HTMLParser
from typing import Any

import structlog
from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.ingest.tijori_common import (
    TIJORI_SOURCE_ID,
    TijoriIslandStatus,
    label_number_pairs,
    raw_json,
)
from fundamentals.ingest.tijori_overview_common import PATH_SEPARATOR, SectionContext
from fundamentals.ingest.tijori_overview_models import (
    REVENUE_MIX_ELEMENT_ID,
    TijoriRevenueMixBreakUp,
    TijoriRevenueMixEntry,
    TijoriRevenueMixSection,
)

_LOGGER = structlog.get_logger(__name__)

BREAK_UP_TABLE_ID_PREFIX = "rmix"
BREAK_UP_VALUE_LABEL = "value"
BREAK_UP_BLOCK_CLASS = "rmix_graph_block"

_SECTION_TAG = "section"
_DIV_TAG = "div"
_TITLE_TAG = "h4"
_ID_ATTRIBUTE = "id"
_CLASS_ATTRIBUTE = "class"
_COMPANY_ID_ATTRIBUTE = "company-id"
_CHART_ID_ATTRIBUTE = "chart-id"
_CHART_DATA_ATTRIBUTE = "chart-data"

_NO_TITLE = f"the block renders no <{_TITLE_TAG}> break-up title"
_NO_CHART_DATA = f"the block carries no {_CHART_DATA_ATTRIBUTE} attribute"
_NO_CHART_ID = (
    f"the block carries {_CHART_DATA_ATTRIBUTE} but no {_CHART_ID_ATTRIBUTE} to address it by"
)
_AMBIGUOUS = "the block carries {count} chart-data attributes; none of them is addressable"
_UNDECODABLE = "the chart-data attribute is not decodable JSON: {error}"
_WRONG_SHAPE = "the chart-data attribute is not a list of [label, number] pairs: {detail}"


class _RawBlock(BaseModel):
    """One ``rmix_graph_block`` reduced to the parts that carry meaning.

    ``company_id_attribute`` is the block's ``company-id`` attribute, retained
    under a name that says it is an ATTRIBUTE and not an identity: live it
    duplicates ``chart-id`` and does not match the page's company id at all.
    Nothing reads it; it is kept because it is source data.
    """

    model_config = ConfigDict(frozen=True)

    title: str | None
    chart_id: str | None
    observed_chart_id: str | None
    chart_data: str | None
    company_id_attribute: str | None
    chart_data_count: int


class _RevenueMixCollector(HTMLParser):
    """Collect the break-up blocks rendered inside ``<… id="revenuemix">``.

    Character references are converted because this markup IS the data: the
    ``chart-data`` attribute is entity-encoded JSON and the title is rendered
    text. Nesting is tracked by counting only ``section`` and ``div`` tags,
    which are never void, so a stray void element cannot desynchronise the
    depth the way a generic tag counter would.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[_RawBlock] = []
        self.section_found = False
        self._section_depth = 0
        self._block_depth = 0
        self._block: dict[str, Any] | None = None
        self._title_chunks: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Open the revenue-mix section, a break-up block, or a captured title."""
        attributes = dict(attrs)
        if tag == _SECTION_TAG:
            if self._section_depth:
                self._section_depth += 1
            elif attributes.get(_ID_ATTRIBUTE) == REVENUE_MIX_ELEMENT_ID:
                self._section_depth = 1
                self.section_found = True
            return
        if not self._section_depth:
            return
        if tag == _DIV_TAG:
            self._start_div(attributes)
            return
        if tag == _TITLE_TAG and self._block is not None:
            self._title_chunks = []
            return
        if self._block is not None:
            self._read_chart_attributes(attributes)

    def _start_div(self, attributes: dict[str, str | None]) -> None:
        """Open a break-up block, or descend inside the one already open."""
        if self._block_depth:
            self._block_depth += 1
            self._read_chart_attributes(attributes)
            return
        classes = (attributes.get(_CLASS_ATTRIBUTE) or "").split()
        if BREAK_UP_BLOCK_CLASS not in classes:
            return
        self._block_depth = 1
        self._block = {
            "title": None,
            "chart_id": None,
            "observed_chart_id": None,
            "chart_data": None,
            "company_id_attribute": attributes.get(_COMPANY_ID_ATTRIBUTE),
            "chart_data_count": 0,
        }
        self._read_chart_attributes(attributes)

    def _read_chart_attributes(self, attributes: dict[str, str | None]) -> None:
        """Record the first chart payload found in the open block, counting repeats.

        ``chart_id`` is taken from the element that carries the data, because
        that is what addresses the values. Any chart id seen elsewhere in the
        block is kept separately as ``observed_chart_id`` — it addresses
        nothing, but a refused block that names one should say so rather than
        be retained as if the markup had carried no id at all.
        """
        if self._block is None:
            return
        chart_id = attributes.get(_CHART_ID_ATTRIBUTE)
        if chart_id is not None and self._block["observed_chart_id"] is None:
            self._block["observed_chart_id"] = chart_id
        if _CHART_DATA_ATTRIBUTE not in attributes:
            return
        self._block["chart_data_count"] += 1
        if self._block["chart_data"] is not None:
            return
        self._block["chart_data"] = attributes.get(_CHART_DATA_ATTRIBUTE)
        self._block["chart_id"] = chart_id

    def handle_data(self, data: str) -> None:
        """Accumulate the break-up title currently being captured."""
        if self._title_chunks is not None:
            self._title_chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        """Close a captured title, a break-up block, or the section itself."""
        if tag == _TITLE_TAG and self._title_chunks is not None:
            self._finish_title()
            return
        if tag == _DIV_TAG and self._block_depth:
            self._block_depth -= 1
            if self._block_depth == 0:
                self._finish_block()
            return
        if tag == _SECTION_TAG and self._section_depth:
            self._section_depth -= 1

    def _finish_title(self) -> None:
        """Store the first rendered title of the open block."""
        chunks, self._title_chunks = self._title_chunks, None
        if self._block is None or chunks is None or self._block["title"] is not None:
            return
        title = " ".join("".join(chunks).split())
        self._block["title"] = title or None

    def _finish_block(self) -> None:
        """Retain one completed break-up block exactly as it was rendered."""
        block, self._block = self._block, None
        self._title_chunks = None
        if block is None:
            return
        self.blocks.append(
            _RawBlock(
                title=block["title"],
                chart_id=block["chart_id"],
                observed_chart_id=block["observed_chart_id"],
                chart_data=block["chart_data"],
                company_id_attribute=block["company_id_attribute"],
                chart_data_count=block["chart_data_count"],
            )
        )


def collect_revenue_mix_blocks(document: str) -> tuple[_RawBlock, ...] | None:
    """Collect the rendered break-up blocks, or None when the section is absent.

    None and an empty tuple mean different things and must not be collapsed: a
    page with no revenue-mix section did not publish this data at all, while a
    section that rendered no recognizable block is drift worth reporting.
    """
    collector = _RevenueMixCollector()
    collector.feed(document)
    collector.close()
    if not collector.section_found:
        return None
    return tuple(collector.blocks)


def _pairs(chart_data: str) -> tuple[tuple[str, Decimal], ...] | str:
    """Decode the chart attribute as JSON pairs, or name why it is not that.

    HTMLParser has already undone the attribute's entity encoding, so what
    arrives here is JSON text. Decoding is this surface's concern; the pair
    shape is checked by the gate the shareholding charts share.
    """
    try:
        parsed: Any = json.loads(chart_data, parse_float=Decimal)
    except json.JSONDecodeError as error:
        return _UNDECODABLE.format(error=error.msg)
    read = label_number_pairs(parsed)
    return _WRONG_SHAPE.format(detail=read) if isinstance(read, str) else read


def _anchor(
    context: SectionContext, *, table_id: str, row_path: str, column_index: int
) -> Provenance:
    """Anchor one slice to the chart element its value was rendered in."""
    return Provenance(
        source_id=TIJORI_SOURCE_ID,
        file_sha256=context.content_sha256,
        anchor_type=SourceAnchorType.HTML_TABLE,
        context_ref=f"{context.source_url}#{table_id}{PATH_SEPARATOR}{row_path}",
        table_id=table_id,
        row_path=row_path,
        row_label=row_path,
        column_index=column_index,
        column_label=BREAK_UP_VALUE_LABEL,
        retrieved_at=context.retrieved_at,
        first_seen_at=context.retrieved_at,
    )


def _refusal(block: _RawBlock, context: SectionContext, detail: str) -> TijoriRevenueMixBreakUp:
    """Record one block that could not be read, retaining it verbatim."""
    _LOGGER.warning(
        "tijori_overview_revenue_mix_block_unreadable",
        section=context.section.value,
        title=block.title,
        chart_id=block.chart_id,
        detail=detail,
    )
    return TijoriRevenueMixBreakUp(
        title=block.title,
        chart_id=block.chart_id,
        table_id=(
            None if block.chart_id is None else f"{BREAK_UP_TABLE_ID_PREFIX}:{block.chart_id}"
        ),
        status=TijoriIslandStatus.UNPARSEABLE,
        detail=detail,
        company_id_attribute=block.company_id_attribute,
        raw_block_json=raw_json(block.model_dump()),
    )


def _break_up(
    block: _RawBlock, context: SectionContext, *, block_index: int
) -> TijoriRevenueMixBreakUp:
    """Build one break-up, recording the reason when it could not be read."""
    chart_id, chart_data = block.chart_id, block.chart_data
    if block.title is None:
        return _refusal(block, context, _NO_TITLE)
    if chart_data is None:
        return _refusal(block, context, _NO_CHART_DATA)
    if block.chart_data_count > 1:
        return _refusal(block, context, _AMBIGUOUS.format(count=block.chart_data_count))
    if chart_id is None or not chart_id.strip():
        return _refusal(block, context, _NO_CHART_ID)
    read = _pairs(chart_data)
    if isinstance(read, str):
        return _refusal(block, context, read)
    table_id = f"{BREAK_UP_TABLE_ID_PREFIX}:{chart_id}"
    return TijoriRevenueMixBreakUp(
        title=block.title,
        chart_id=block.chart_id,
        table_id=table_id,
        status=TijoriIslandStatus.PRESENT,
        company_id_attribute=block.company_id_attribute,
        entries=tuple(
            TijoriRevenueMixEntry(
                label=label,
                value=value,
                raw_text=str(value),
                provenance=_anchor(
                    context,
                    table_id=table_id,
                    # Two break-ups may share a slice label — a segment appears
                    # in both the product and the profit split — so the block
                    # and slice positions lead the address and the label follows.
                    row_path=(f"{block_index}{PATH_SEPARATOR}{index}{PATH_SEPARATOR}{label}"),
                    column_index=index,
                ),
            )
            for index, (label, value) in enumerate(read)
        ),
    )


def build_revenue_mix(payload: Any, context: SectionContext) -> TijoriRevenueMixSection:
    """Build the revenue-mix break-ups from the blocks collected off the page."""
    blocks: tuple[_RawBlock, ...] = payload
    break_ups = tuple(
        _break_up(block, context, block_index=index) for index, block in enumerate(blocks)
    )
    return TijoriRevenueMixSection(
        section=context.section,
        island_id=context.island_id,
        source_kind=context.source_kind,
        metadata=context.metadata,
        break_ups=break_ups,
    )
