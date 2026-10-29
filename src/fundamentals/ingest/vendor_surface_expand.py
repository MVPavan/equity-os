"""Finite company children advertised by registered parent responses."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import quote, urljoin

from fundamentals.ingest.screener_company_models import InvestorHook, Periodicity, SegmentHook
from fundamentals.ingest.screener_financials_models import Section
from fundamentals.ingest.screener_financials_schedules import parse_sub_rows
from fundamentals.ingest.screener_financials_tables import read_section
from fundamentals.ingest.screener_session_models import Basis
from fundamentals.ingest.screener_shareholding import read_shareholding_table
from fundamentals.ingest.vendor_surface_capture import Request
from fundamentals.ingest.vendor_surface_fetch import SITE_AUTHORITY, Site
from fundamentals.ingest.vendor_surface_parse import Body, ParseContext
from fundamentals.ingest.vendor_surface_specs import SurfaceSpec


def expansion_name(spec: SurfaceSpec, parent: str) -> str | None:
    """The declared parent relation, shared by acquisition and retained replay."""
    if parent == spec.id == "schedules-api":
        return "screener_nested_schedules"
    expected = {
        "screener_schedules": "company-page",
        "screener_investors": "company-page",
        "screener_segments": "company-page",
        "screener_compare_peers": "company-page",
        "tijori_op_metrics": "company-overview",
        "tijori_revenue_mix_items": "company-overview",
        "tijori_popup_fields": "company-financials",
        "tijori_compare_selector": "company-financials",
    }.get(spec.expand or "")
    if spec.expand == "advertised_links":
        expected = {
            "quarter-source-pdf": "company-page",
            "shareholding-detail-chart-api": "company-shareholding",
            "market-share-peer-companies-api": "company-overview",
        }[spec.id]
    return spec.expand if expected == parent else None


def child(
    spec: SurfaceSpec,
    context: ParseContext,
    *,
    reader_inputs: Mapping[str, Any] | None = None,
    **params: Any,
) -> Request:
    """Carry verified identity and reader inputs into one concrete child address."""
    assert context.ids is not None
    parameters = {
        "symbol": context.ids.nse_symbol,
        "ticker": context.ids.nse_symbol,
        "slug": context.ids.tijori_slug,
        "company_id": context.ids.screener_company_id
        if spec.site is Site.SCREENER
        else context.ids.tijori_company_id,
        "id": context.ids.tijori_company_id,
        "cursor": 0,
        "n": 10000,
        **params,
    }
    path = spec.path.replace("[?onlygraph=True]", "").replace(
        "[?consolidated=true]",
        "?consolidated=true" if context.basis is Basis.CONSOLIDATED else "",
    )
    path = path.replace(
        "[consolidated/]",
        "consolidated/" if context.basis is Basis.CONSOLIDATED else "",
    )
    for key, value in parameters.items():
        if "{" + key + "}" in path:
            path = path.replace("{" + key + "}", quote(str(value), safe=""))
    if spec.id == "segments-api" and context.basis is Basis.CONSOLIDATED:
        path = path.replace("consolidated=", "consolidated=true")
    if spec.site is Site.SCREENER and context.basis is Basis.STANDALONE:
        path = path.replace("&consolidated=", "").replace("?consolidated=", "")
    return Request(
        spec=spec,
        url=urljoin(f"https://{SITE_AUTHORITY[spec.site]}", path),
        ids=context.ids,
        basis=context.basis,
        parent=reader_inputs,
        due_since=None,
    )


def handlers(body: Body, context: ParseContext, name: str) -> tuple[Request, ...]:
    """Expand the page's handler arguments, including whitespace before the opening bracket."""
    assert context.parent is not None
    spec = SurfaceSpec.model_validate(context.parent["spec"])
    calls = re.findall(
        name + r"\s*\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]", body.raw.decode()
    )
    result = []
    tables: dict[str, Any] = {}
    for first, second in dict.fromkeys(calls):
        url_params = {"row": first, "section": second}
        params = {**context.parent, **url_params, "depth": context.parent.get("depth", 1) + 1}
        params.pop("spec", None)
        params.pop("peers", None)
        if name == "showShareholders":
            url_params = {"class": first, "quarterly|yearly": second}
            params = {}
        elif name == "showSegment":
            url_params = {"quarters|profit-loss": first, "segment_type": second}
            params = {}
        if context.parent.get("depth", 1) == 1:
            key = (
                second
                if name == "showShareholders"
                else (first if name == "showSegment" else second)
            )
            if key not in tables:
                provenance: dict[str, Any] = {
                    "source_id": Site.SCREENER.value,
                    "file_sha256": context.body_sha256,
                    "retrieved_at": context.retrieved_at,
                }
                tables[key] = (
                    read_shareholding_table(body.tree(), Periodicity(key), **provenance)
                    if name == "showShareholders"
                    else read_section(body.tree(), Section(key), **provenance)
                )
            table = tables[key]
            if name == "showShareholders":
                params.update(
                    hook=InvestorHook(
                        bucket=first,
                        periodicity=Periodicity(second),
                        row_label=next(row.label for row in table.rows if row.bucket == first),
                    ),
                    table=table,
                )
            else:
                params.update(
                    page_section=table,
                    periods=table.periods,
                    page_row=next(
                        (row for row in table.rows if row.schedule_parent == first), None
                    ),
                )
                if name == "showSegment":
                    params["hook"] = SegmentHook(section=first, segment_type=second)
        result.append(child(spec, context, reader_inputs=params, **url_params))
    if name == "showShareholders":
        result = [request.model_copy(update={"basis": None}) for request in result]
    return tuple(result)


def screener_schedules(body: Body, context: ParseContext) -> tuple[Request, ...]:
    """Follow advertised first-level schedules."""
    return handlers(body, context, "showSchedule")


def screener_nested_schedules(body: Body, context: ParseContext) -> tuple[Request, ...]:
    """Read raw isExpandable calls and the reader's sub_rows representation."""
    document = json.loads(body.raw)
    rows = document.get("sub_rows", document.values())
    calls = [
        row.get("nested_schedule_call", row.get("isExpandable"))
        for row in rows
        if isinstance(row, dict)
    ]
    advertised = " ".join(call for call in calls if isinstance(call, str))
    nested_context = context.model_copy(
        update={
            "parent": {
                **(context.parent or {}),
                "outer_parent": (context.parent or {}).get("row"),
            }
        }
    )
    children = handlers(Body(raw=advertised.encode()), nested_context, "showSchedule")
    if not children or "sub_rows" in document:
        return children
    assert context.parent is not None
    reference_rows = parse_sub_rows(
        body.raw,
        family=str(context.parent["row"]),
        periods=context.parent["periods"],
        document_id=context.capture_id,
        body_sha256=context.body_sha256,
        source_id=Site.SCREENER.value,
        retrieved_at=context.retrieved_at,
    )
    return tuple(
        request.model_copy(
            update={
                "parent": {
                    **(request.parent or {}),
                    "reference_row": next(
                        row for row in reference_rows if row.label == (request.parent or {})["row"]
                    ),
                    "sales_row": next(
                        (
                            row
                            for row in context.parent["page_section"].rows
                            if row.label == "Sales"
                        ),
                        None,
                    ),
                }
            }
        )
        for request in children
    )


def screener_investors(body: Body, context: ParseContext) -> tuple[Request, ...]:
    """Follow the shareholder classes and periods advertised by the page."""
    return handlers(body, context, "showShareholders")


def screener_segments(body: Body, context: ParseContext) -> tuple[Request, ...]:
    """Follow only advertised segment types."""
    return handlers(body, context, "showSegment")


def tijori_op_metrics(body: Body, context: ParseContext) -> tuple[Request, ...]:
    """Follow the operating metric URLs in the overview."""
    assert context.parent is not None and context.ids is not None
    spec = SurfaceSpec.model_validate(context.parent["spec"])
    paths = dict.fromkeys(
        re.findall(r"/api/v1/ind/company_op_metrics/([0-9]+)/([0-9]+)/", body.raw.decode())
    )
    return tuple(
        child(spec, context, reader_inputs={"metric_id": metric}, metric_id=metric)
        for company, metric in paths
        if int(company) == context.ids.tijori_company_id
    )


def tijori_revenue_mix_items(body: Body, context: ParseContext) -> tuple[Request, ...]:
    """Follow historic chart ids declared by the overview."""
    assert context.parent is not None
    spec = SurfaceSpec.model_validate(context.parent["spec"])
    return tuple(
        child(spec, context, item_id=item)
        for item in dict.fromkeys(
            body.tree().xpath('//*[contains(@class,"line-chart-historic")]/@chart-id')
        )
    )


def financials(body: Body) -> dict[str, Any]:
    """Read the retained financial table island for its endpoint selectors."""
    return dict(json.loads(body.tree().xpath('//script[@id="fin_tables_data"]/text()')[0]))


def tijori_popup_fields(body: Body, context: ParseContext) -> tuple[Request, ...]:
    """Follow each distinct financial row's declared field, source and statement."""
    assert context.parent is not None
    spec = SurfaceSpec.model_validate(context.parent["spec"])
    rows = [row for table in financials(body).values() if table for row in table.get("data", [])]
    fields: dict[tuple[str, str, str], None] = {}
    while rows:
        row = rows.pop(0)
        if row.get("field") and row.get("source") and row.get("fs_name"):
            fields[row["field"], row["source"], row["fs_name"]] = None
        rows[0:0] = row.get("sub_section") or []
    return tuple(
        child(spec, context, field=field, source=source, fs_name=name)
        for field, source, name in fields
    )


def tijori_compare_selector(body: Body, context: ParseContext) -> tuple[Request, ...]:
    """Follow every retained financial table selector."""
    assert context.parent is not None
    spec = SurfaceSpec.model_validate(context.parent["spec"])
    return tuple(
        child(spec, context, column_selector=selector)
        for selector, table in financials(body).items()
        if table is not None
    )


def screener_compare_peers(body: Body, context: ParseContext) -> tuple[Request, ...]:
    """Compare only peers supplied by the covered-universe caller."""
    assert context.parent is not None
    spec = SurfaceSpec.model_validate(context.parent["spec"])
    assert context.ids is not None
    return tuple(
        child(spec, context).model_copy(
            update={
                "url": f"https://www.screener.in/company/compare/?codes={context.ids.screener_company_id},{peer}"
            }
        )
        for peer in context.parent.get("peers", ())
    )


def advertised_links(body: Body, context: ParseContext) -> tuple[Request, ...]:
    """Follow the three remaining finite company endpoint advertisements."""
    assert context.parent is not None and context.ids is not None
    spec = SurfaceSpec.model_validate(context.parent["spec"])
    if spec.id == "quarter-source-pdf":
        matches = re.findall(
            r"/company/source/quarter/([0-9]+)/([^/]+)/([0-9]+)/", body.raw.decode()
        )
        return tuple(
            child(spec, context, month=month, year=year)
            for company, month, year in dict.fromkeys(matches)
            if int(company) == context.ids.screener_company_id
        )
    if spec.id == "shareholding-detail-chart-api":
        fields = dict.fromkeys(
            (e.get("field"), e.get("source")) for e in body.tree().xpath("//*[@field and @source]")
        )
        return tuple(child(spec, context, field=field, source=source) for field, source in fields)
    matches = re.findall(
        r"/api/v1/ind/market_share_peer_companies/([0-9]+)/([0-9]+)/", body.raw.decode()
    )
    return tuple(
        child(spec, context, chart_company_id=peer)
        for company, peer in dict.fromkeys(matches)
        if int(company) == context.ids.tijori_company_id
    )


EXPANSIONS: Mapping[str, Callable[[Body, ParseContext], tuple[Request, ...]]] = {
    function.__name__: function
    for function in (
        screener_schedules,
        screener_nested_schedules,
        screener_investors,
        screener_segments,
        tijori_op_metrics,
        tijori_revenue_mix_items,
        tijori_popup_fields,
        tijori_compare_selector,
        screener_compare_peers,
        advertised_links,
    )
}
