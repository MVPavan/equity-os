"""Finite company children advertised by registered parent responses."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable, Mapping
from typing import Any
from urllib.parse import quote, urljoin

from equity_os.extraction.surfaces.vendor_surface_parse import Body, ParseContext
from equity_os.extraction.vendors.screener.screener_company_models import (
    InvestorHook,
    Periodicity,
    SegmentHook,
)
from equity_os.extraction.vendors.screener.screener_financials_models import (
    MAX_SCHEDULE_DEPTH,
    Section,
)
from equity_os.extraction.vendors.screener.screener_financials_schedules import parse_sub_rows
from equity_os.extraction.vendors.screener.screener_financials_tables import read_section
from equity_os.extraction.vendors.screener.screener_session_models import (
    Basis,
    ScreenerSessionError,
)
from equity_os.extraction.vendors.screener.screener_session_page import read_identity
from equity_os.extraction.vendors.screener.screener_shareholding import read_shareholding_table
from equity_os.sourcing.surfaces.vendor_surface_capture import Request
from equity_os.sourcing.surfaces.vendor_surface_fetch import SITE_AUTHORITY, Site
from equity_os.sourcing.surfaces.vendor_surface_specs import SITE_NAME, SurfaceSpec


def parent_surface(spec: SurfaceSpec) -> str | None:
    """The surface whose retained response advertises this surface's requests, if any."""
    if spec.id == "chart-api" or "{warehouse_id}" in spec.path:
        return "company-page"
    if spec.expand == "advertised_links":
        return {
            "shareholding-detail-chart-api": "company-shareholding",
            "market-share-peer-companies-api": "company-overview",
        }[spec.id]
    return {
        "screener_schedules": "company-page",
        "screener_investors": "company-page",
        "screener_segments": "company-page",
        "screener_concall_summaries": "company-page",
        "screener_compare_peers": "company-page",
        "tijori_op_metrics": "company-overview",
        "tijori_revenue_mix_items": "company-overview",
        "tijori_popup_fields": "company-financials",
        "tijori_compare_selector": "company-financials",
    }.get(spec.expand or "")


def expansion_name(spec: SurfaceSpec, parent: str) -> str | None:
    """The declared parent relation, shared by acquisition and retained replay."""
    if parent == spec.id == "schedules-api":
        return "screener_nested_schedules"
    return spec.expand if spec.expand and parent_surface(spec) == parent else None


def lineage(spec: SurfaceSpec, specs: Iterable[SurfaceSpec]) -> tuple[SurfaceSpec, ...]:
    """The spec and every same-site surface it transitively needs: section owner or parent."""
    by_id = {s.id: s for s in specs if s.site is spec.site}
    by_path = {s.path: s for s in by_id.values()}
    chain = [spec]
    for current in chain:
        parents = (
            (by_path.get(current.path.split("#")[0]),)
            if "#" in current.path
            else tuple(
                by_id.get(name or "")
                for name in (parent_surface(current), *MARKET_PARENTS.get(current.expand or "", ()))
            )
        )
        chain.extend(parent for parent in parents if parent is not None and parent not in chain)
    return tuple(chain)


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


def screener_concall_summaries(body: Body, context: ParseContext) -> tuple[Request, ...]:
    """Follow the Notes button of each concalls row in the verified page's documents section."""
    assert context.parent is not None
    spec = SurfaceSpec.model_validate(context.parent["spec"])
    urls = body.tree().xpath('//*[@id="documents"]//*/@data-url')
    ids = dict.fromkeys(
        m[1] for u in urls if (m := re.fullmatch(r"/concalls/summary/([0-9]+)/", u))
    )
    return tuple(child(spec, context, concall_id=concall_id) for concall_id in ids)


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
    """Follow the two remaining finite company endpoint advertisements."""
    assert context.parent is not None and context.ids is not None
    spec = SurfaceSpec.model_validate(context.parent["spec"])
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
        screener_concall_summaries,
        tijori_op_metrics,
        tijori_revenue_mix_items,
        tijori_popup_fields,
        tijori_compare_selector,
        screener_compare_peers,
        advertised_links,
    )
}


NO_SECTOR = "/sector/None"
# Parent ids are finite; only these retained advertisements may create requests.
MARKET_PARENTS = {
    "screener_market_levels": ("market-overview", "market-level"),
    "screener_indices": ("company-page",),
    "screener_people": ("people-search",),
    "screener_hs": ("hs-search-api",),
    "screener_commodities": ("hs-search-api",),
    "screener_screens": ("screens-list",),
    "screener_authors": ("screen-page",),
    "screener_capsules": ("explore",),
    "screener_insiders": ("trades-feed",),
    "tijori_sectors": ("company-overview",),
    "tijori_indices": ("markets",),
    "tijori_widgets": ("markets",),
    "tijori_sector_charts": ("sector-page",),
    "tijori_macro": ("macro",),
}


def child_spec(context: ParseContext) -> SurfaceSpec:
    """The child surface whose expansion runs over this retained parent."""
    assert context.parent is not None
    return SurfaceSpec.model_validate(context.parent["spec"])


def market_children(context: ParseContext, paths: Iterable[str]) -> tuple[Request, ...]:
    """Deduplicate concrete market addresses advertised by one retained parent."""
    spec = child_spec(context)
    return tuple(
        Request(spec=spec, url=urljoin(context.url, path), ids=None, due_since=None)
        for path in dict.fromkeys(paths)
    )


def market_links(body: Body, context: ParseContext) -> tuple[Request, ...]:
    """Match this finite endpoint template against retained URL advertisements."""
    spec = child_spec(context)
    path = spec.path.split("?")[0]
    pattern = re.escape(path)
    for token in re.findall(r"\{([^{}]+)\}", path):
        replacement = r"[0-9]+" if token in {"id", "screen_id", "hs_code"} else r"[A-Za-z0-9_-]+"
        pattern = pattern.replace(re.escape("{" + token + "}"), replacement)
    urls = re.findall(pattern, body.raw.decode())
    return market_children(context, urls)


def screener_market_levels(body: Body, context: ParseContext) -> tuple[Request, ...]:
    """Visit every advertised industry path and all four ancestor levels."""
    paths = dict.fromkeys(
        "/market/" + "/".join(parts[:depth]) + "/"
        for path in body.tree().xpath("//a/@href")
        if re.fullmatch(
            r"/market/IN[0-9]{2}/(?:IN[0-9]{4}/)?(?:IN[0-9]{6}/)?(?:IN[0-9]{9}/)?", path
        )
        for parts in [path.strip("/").split("/")[1:]]
        for depth in range(1, len(parts) + 1)
    )
    return market_children(context, paths)


def tijori_market_tree(body: Body) -> dict[str, Any]:
    """Read the retained market tree's explicitly declared groups."""
    return dict(json.loads(body.tree().xpath('//script[@id="data"]/text()')[0]))


def screener_indices(body: Body, context: ParseContext) -> tuple[Request, ...]:
    """Index pages are advertised only as a company page's benchmark tags."""
    return market_children(
        context, body.tree().xpath('//a[contains(@class,"Click+Benchmark")]/@href')
    )


def screener_hs(body: Body, context: ParseContext) -> tuple[Request, ...]:
    """HS codes come from the search API's commodity links."""
    spec = child_spec(context)
    codes = re.findall(r"/commodity/([0-9]+)/", body.raw.decode())
    return market_children(context, (spec.path.replace("{hs_code}", code) for code in codes))


def tijori_sectors(body: Body, context: ParseContext) -> tuple[Request, ...]:
    """A covered company page links its one sector, or `/sector/None` when it has none."""
    links = re.findall(r'"url": "(/sector/[^"]+)"', body.raw.decode())
    return market_children(context, (link for link in links if link != NO_SECTOR))


def tijori_indices(body: Body, context: ParseContext) -> tuple[Request, ...]:
    """Index ids belong to groups; niche ids identify sectors."""
    spec = child_spec(context)
    nodes = tijori_market_tree(body)["groups"]["children"]
    return market_children(
        context,
        (spec.path.replace("{index_id}", str(node["id"])) for node in nodes if "id" in node),
    )


def tijori_widgets(body: Body, context: ParseContext) -> tuple[Request, ...]:
    """Follow the hub script: each expanding metric reads its own table, row and cell."""
    spec = child_spec(context)
    parts = (
        {
            "table": metric.xpath("string(ancestor::table[1]/@data-widget)"),
            "activeIndex": metric.xpath("string(ancestor::tr[1]/@tjiid)"),
            "field": metric.xpath("string(ancestor::td[1]/@field)"),
        }
        for metric in body.tree().xpath(
            '//*[contains(concat(" ",@class," ")," expanding_metric ")]'
        )
    )
    return market_children(
        context, (spec.path.format(**part) for part in parts if all(part.values()))
    )


MARKET_EXPANSIONS = dict.fromkeys(MARKET_PARENTS, market_links)
MARKET_EXPANSIONS.update(
    {
        function.__name__: function
        for function in (
            screener_market_levels,
            screener_indices,
            screener_hs,
            tijori_sectors,
            tijori_indices,
            tijori_widgets,
        )
    }
)
EXPANSIONS = {**EXPANSIONS, **MARKET_EXPANSIONS}


def advertised(
    request: Request,
    body: Body,
    context: ParseContext,
    specs: Iterable[SurfaceSpec],
    peers: tuple[int, ...],
) -> tuple[tuple[Request, ...], tuple[str, ...]]:
    """One parent's advertised children, and every missing or failed expansion by fixed name."""
    found: list[Request] = []
    gaps: list[str] = []
    for spec in specs:
        name = expansion_name(spec, request.spec.id) or (
            spec.expand if request.spec.id in MARKET_PARENTS.get(spec.expand or "", ()) else None
        )
        if name is None or spec.site is not request.spec.site:
            continue
        prefix = f"{SITE_NAME[spec.site]}:{spec.id}"
        parent = {**(request.parent or {}), "spec": spec.model_dump(), "peers": peers}
        try:
            children = EXPANSIONS[name](body, context.model_copy(update={"parent": parent}))
        except (
            ValueError,
            KeyError,
            IndexError,
            TypeError,
            StopIteration,
            ScreenerSessionError,
        ) as error:
            gaps.append(f"{prefix}: expansion failed: {type(error).__name__}")
            continue
        if name == "screener_nested_schedules":
            if children and (request.parent or {}).get("depth", 2) >= MAX_SCHEDULE_DEPTH:
                gaps.append(f"{prefix}: schedule depth limit")
                continue
        elif (
            not children
            and spec.id != "company-compare"
            and not (spec.id == "segments-api" and b"Product Segments" not in body.raw)
            and not (spec.id == "sector-page" and f'"{NO_SECTOR}"'.encode() in body.raw)
        ):
            gaps.append(f"{prefix}: no advertised children")
        found.extend(children)
    if request.spec.id == "company-page":
        warehouse = read_identity(body.tree())[1]
        for spec in specs:
            if spec.id == "chart-api":
                metrics = dict.fromkeys(
                    body.tree().xpath('//*[@id="chart"]//*[@name="metrics"]/@value')
                )
                if not any(metrics):
                    gaps.append("screener:chart-api: no advertised metrics")
                plain = context.model_copy(update={"basis": None})
                found.extend(child(spec, plain, **{"metric-set": m}) for m in metrics if m)
            elif "{warehouse_id}" in spec.path and warehouse is not None:
                found.append(child(spec, context, warehouse_id=warehouse))
    return tuple(found), tuple(gaps)
