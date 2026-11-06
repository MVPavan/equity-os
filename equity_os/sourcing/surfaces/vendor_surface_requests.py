"""The request graph of a company: its fixed requests, the peers it compares with, and the
requests its retained captures admit (split from :mod:`vendor_surface_capture`)."""

from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING, Any

from lxml.etree import ParserError  # type: ignore[import-untyped]
from psycopg_pool import ConnectionPool

from equity_os.contracts.sourcing.acquisition_outcome import OutcomeCode
from equity_os.contracts.sourcing.snapshot import BodyCompleteness, CaptureRecord
from equity_os.extraction.surfaces.vendor_surface_parse import (
    Body,
    CompanyIds,
    ParseContext,
    company_page,
)
from equity_os.extraction.vendors.screener.screener_session_models import (
    Basis,
    ScreenerSessionError,
)
from equity_os.extraction.vendors.screener.screener_session_page import (
    assert_logged_in,
    read_identity,
)
from equity_os.sourcing.surfaces.vendor_surface_fetch import Site
from equity_os.sourcing.surfaces.vendor_surface_specs import Scope, SurfaceSpec
from equity_os.sourcing.vendors.tijori.tijori_capture import classify_financials_body
from equity_os.storage.raw_files.snapshot_store import SnapshotStore

if TYPE_CHECKING:
    from equity_os.sourcing.surfaces.vendor_surface_capture import Request

IDENTITY_PAGES = ("company-page", "company-financials")


def company_requests(specs: tuple[SurfaceSpec, ...], ids: CompanyIds) -> tuple[Request, ...]:
    """Build parents before fixed endpoints; parameterized children await retained parents."""
    from equity_os.sourcing.surfaces.vendor_surface_expand import child

    result: list[Request] = []
    context = ParseContext(
        ids=ids, basis=None, url="", retrieved_at=datetime.min, body_sha256="", capture_id=""
    )
    for spec in sorted(
        specs, key=lambda spec: spec.id not in ("company-page", "company-financials")
    ):
        if (
            spec.scope is not Scope.COMPANY
            or spec.expand
            or spec.id == "chart-api"
            or "#" in spec.path
        ):
            continue
        if any(
            token in spec.path
            for token in ("{warehouse_id}", "{month}", "{chart_company_id}", "{field}")
        ):
            continue
        if spec.site is Site.TIJORI and (
            ids.tijori_slug is None
            or (
                ids.tijori_company_id is None
                and any(token in spec.path for token in ("{company_id}", "{id}"))
            )
        ):
            continue
        bases = (
            tuple(Basis)
            if spec.site is Site.SCREENER
            and ("[consolidated/]" in spec.path or "consolidated=" in spec.path)
            else (None,)
        )
        alternative = re.search(r"\{([^{}]*\|[^{}]*)\}", spec.path)
        variants = (
            [part for part in alternative[1].split("|") if part != "..."] if alternative else [""]
        )
        for basis in bases:
            for variant in variants:
                parameters: dict[str, Any] = {alternative[1]: variant} if alternative else {}
                result.append(
                    child(
                        spec,
                        context.model_copy(update={"basis": basis}),
                        **parameters,
                    )
                )
    return tuple(result)


def identity_refusal(request: Request, body: Body) -> str | None:
    """Why a retained identity page does not prove its request's company, or None."""
    assert request.ids is not None
    try:
        if request.spec.id == "company-page":
            assert_logged_in(body.tree())
            same = read_identity(body.tree())[0] == request.ids.screener_company_id
            return None if same else "company identity mismatch"
        gate = classify_financials_body(
            body.raw,
            expected_symbol=request.ids.nse_symbol,
            expected_company_id=request.ids.tijori_company_id,
        )
        return None if gate.code is OutcomeCode.OK else gate.native_value
    except (ScreenerSessionError, ParserError, UnicodeDecodeError) as error:
        return type(error).__name__


def covered_peers(pool: ConnectionPool, store: SnapshotStore, ids: CompanyIds) -> tuple[int, ...]:
    """Covered NSE peers, using registry evidence with configuration overrides."""
    from equity_os.sourcing.surfaces.vendor_surface_due import covered_universe

    return tuple(
        peer.screener_company_id
        for peer in covered_universe(pool, store)
        if peer.nse_symbol != ids.nse_symbol and peer.screener_company_id is not None
    )


def retained_graph(
    store: SnapshotStore,
    pool: ConnectionPool,
    specs: tuple[SurfaceSpec, ...],
    ids: CompanyIds,
    retained: list[dict[str, Any]],
) -> dict[str, Request]:
    """The company requests its retained captures admit, gated as live capture gates them.

    Identity pages must prove the company (and Screener pages their basis); fixed requests need
    their site and basis proven; children need an admitted, retained parent advertising them.
    """
    from equity_os.sourcing.surfaces.vendor_surface_expand import advertised, expansion_name

    captures: dict[str, list[tuple[CaptureRecord, str]]] = {}
    for row in retained:
        if row["symbol"] != ids.nse_symbol:
            continue
        record = store.get_capture(
            row["source_id"], row["surface"], row["request_key"], row["capture_id"]
        )
        if (
            record.http_status == 200
            and record.effective_body_completeness is BodyCompleteness.COMPLETE
        ):
            captures.setdefault(row["url"], []).append((record, row["blob_sha256"]))
    fixed = company_requests(specs, ids)
    admitted: dict[str, Request] = {}
    proven: set[Site | Basis] = set()
    verified_captures: set[str] = set()
    for request in (r for r in fixed if r.spec.id in IDENTITY_PAGES):
        for record, sha in captures.get(request.url, []):
            body = Body(raw=store.read_body(record))
            if identity_refusal(request, body) is not None:
                continue
            if request.basis is not None:
                try:
                    company_page(body, request.context(record, sha))
                except ScreenerSessionError:
                    continue
                proven.add(request.basis)
            proven.add(request.spec.site)
            verified_captures.add(record.capture_id)
            admitted[request.url] = request
    admitted.update(
        (r.url, r)
        for r in fixed
        if r.spec.site in proven
        and (r.basis is None or r.basis in proven)
        and r.spec.id not in IDENTITY_PAGES
    )
    queue, peers = list(admitted.values()), covered_peers(pool, store, ids)
    while queue:
        request = queue.pop()
        if request.spec.id != "company-page" and not any(
            expansion_name(spec, request.spec.id) for spec in specs
        ):
            continue
        for record, sha in captures.get(request.url, []):
            if request.spec.id in IDENTITY_PAGES and record.capture_id not in verified_captures:
                continue
            body = Body(raw=store.read_body(record))
            children, _ = advertised(request, body, request.context(record, sha), specs, peers)
            fresh = [child for child in children if child.url not in admitted]
            admitted.update((child.url, child) for child in fresh)
            queue.extend(fresh)
    return admitted
