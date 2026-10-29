"""Finite market breadth and append-only traversal checkpoints."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, date, datetime
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, ConfigDict

from fundamentals.evidence.repository_rows import capture_of
from fundamentals.ingest.vendor_surface_capture import Request, RunReport, capture
from fundamentals.ingest.vendor_surface_expand import MARKET_PARENTS, advertised
from fundamentals.ingest.vendor_surface_fetch import (
    SITE_AUTHORITY,
    Site,
    SiteBusy,
    SiteStopped,
    VendorFetcher,
    normalise,
    request_key,
)
from fundamentals.ingest.vendor_surface_parse import Body, parser_sha256
from fundamentals.ingest.vendor_surface_specs import SITE_NAME, Scope, SurfaceSpec
from fundamentals.ingest.vendor_surface_tables import feed_rows
from fundamentals.store.snapshot_store import SnapshotStore
from fundamentals.store.vendor_values_store import (
    USABLE,
    Outcome,
    OutcomeStatus,
    VendorValue,
    VendorValuesStore,
)

MAX_FEED_PAGES = 20
TRAVERSAL_VERSION = "traversal.v3"
# Index pages are advertised only by company pages: route through verified retained ones.
COMPANY_PAGES = """SELECT DISTINCT ON (a.url) c.*, a.url FROM eqos.capture_refs c
JOIN eqos.capture_addresses a ON a.capture_ref_id = c.id
JOIN eqos.vendor_outcomes o ON o.capture_ref_id = c.id AND o.surface = 'company-page'
WHERE c.surface = 'vs.company-page' AND o.status = ANY(%s) ORDER BY a.url, c.capture_id DESC"""
MOVING = frozenset(
    "p page cursor timestamp daterange date_from date_to ts same_ts_offset_count".split()
)


class Boundary(BaseModel):
    """The newest stable identity from a completed traversal's first page."""

    model_config = ConfigDict(frozen=True)
    row_id: str | None = None
    date_to: date | None = None
    cursor: str | None = None


class Progress(BaseModel):
    """Only retained outcomes and addresses determine continuation."""

    model_config = ConfigDict(frozen=True)
    boundary: Boundary | None
    resume_page: int | None
    resume_url: str | None


def named(spec: SurfaceSpec) -> str:
    """The site and surface naming a report entry, never a vendor address."""
    return f"{SITE_NAME[spec.site]}:{spec.id}"


def address(request: Request) -> str:
    """A report entry for one request: its surface and address key, never the address."""
    return f"{named(request.spec)}:{request_key(normalise(request.url))}"


def traversal_key(request: Request) -> str:
    """Keep path/filter identity while excluding moving pagination parameters."""
    parts = urlsplit(normalise(request.url))
    stable = sorted(
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key not in MOVING
    )
    return hashlib.sha256(
        json.dumps([request.spec.site, request.spec.id, parts.path, stable]).encode()
    ).hexdigest()


def progress(pool: ConnectionPool, key: str) -> Progress:
    """Recover the last completed boundary and the unfinished page from retained outcomes."""
    with pool.connection() as conn:
        rows = conn.execute(
            "SELECT o.id,o.traversal_page,o.traversal_done,a.url FROM eqos.vendor_outcomes o "
            "JOIN eqos.capture_addresses a ON a.capture_ref_id=o.capture_ref_id "
            "WHERE o.traversal_key=%s ORDER BY o.id",
            (key,),
        ).fetchall()
        done = [index for index, row in enumerate(rows) if row[2]]
        boundary = None
        if done:
            # The boundary is the first page of the last completed traversal.
            first = rows[done[-2] + 1 if len(done) > 1 else 0]
            marks: dict[str, str] = dict(
                conn.execute(
                    "SELECT column_label,raw_text FROM eqos.vendor_values WHERE outcome_id=%s",
                    (first[0],),
                ).fetchall()
            )
            window = dict(parse_qsl(urlsplit(first[3]).query)).get("daterange")
            boundary = Boundary(
                row_id=marks.get("row_id"),
                cursor=marks.get("cursor"),
                date_to=datetime.strptime(window.split(",")[1], "%m/%d/%Y").date()
                if window
                else None,
            )
    pending = rows[done[-1] + 1 :] if done else rows
    last = max(pending, key=lambda row: row[1], default=None)
    return Progress(
        boundary=boundary,
        resume_page=last[1] if last else None,
        resume_url=last[3] if last else None,
    )


def mark(name: str, text: str | None) -> tuple[VendorValue, ...]:
    """Keep one traversal mark as a value, so outcome detail never holds vendor text."""
    if text is None:
        return ()
    return (
        VendorValue(
            table_key="traversal",
            row_index=0,
            column_index=0 if name == "row_id" else 1,
            locator=f"traversal:{name}",
            row_label="",
            column_label=name,
            raw_text=text,
            value=None,
        ),
    )


def query_url(url: str, **params: str) -> str:
    """Change moving parameters without discarding stable filters."""
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.update(params)
    return urlunsplit(parts._replace(query=urlencode(query)))


def alternatives(path: str) -> list[str]:
    """Expand catalog optional `[a|b]` and required `{a|b}` notation into concrete paths."""
    match = re.search(r"\[([^\[\]]+)\]|\{([^{}]*\|[^{}]*)\}", path)
    if match is None:
        return [path]
    return [
        concrete
        for item in (match[1] or match[2]).split("|") + ([""] if match[1] else [])
        if item != "..."
        for concrete in alternatives(path[: match.start()] + item + path[match.end() :])
    ]


def market_requests(specs: tuple[SurfaceSpec, ...], pool: ConnectionPool) -> tuple[Request, ...]:
    """Build finite hub requests; parameterized children wait for retained parents."""
    requests = []
    for spec in specs:
        if spec.scope is not Scope.MARKET or spec.expand:
            continue
        for path in alternatives(spec.path):
            path = path.split(" -> ")[0]
            for token in re.findall(r"\{([^{}]+)\}", path):
                path = path.replace("{" + token + "}", "1" if token == "n" else "")
            path = re.sub(r" \(\+ (\S+)\)", r" | \1", path.replace("&...", ""))
            for variant in path.split(" | "):
                requests.append(
                    Request(
                        spec=spec,
                        url=urljoin(f"https://{SITE_AUTHORITY[spec.site]}", variant),
                        ids=None,
                        due_since=None,
                    )
                )
    return tuple(requests)


def company_routes(
    store: SnapshotStore, pool: ConnectionPool, specs: tuple[SurfaceSpec, ...]
) -> tuple[tuple[Request, ...], tuple[str, ...]]:
    """Market children of the latest verified company page per address, or the missing level."""
    page = next((s for s in specs if s.id == "company-page"), None)
    targets = [s for s in specs if "company-page" in MARKET_PARENTS.get(s.expand or "", ())]
    if page is None or not targets:
        return (), ()
    with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
        rows = cursor.execute(COMPANY_PAGES, (list(USABLE),)).fetchall()
    found: list[Request] = []
    gaps: list[str] = []
    for row in rows:
        ref = capture_of(row)
        record = store.get_capture(ref.source_id, ref.surface, ref.request_key, ref.capture_id)
        parent = Request(spec=page, url=row["url"], ids=None, due_since=None)
        body = Body(raw=store.read_body(record))
        children, missing = advertised(
            parent, body, parent.context(record, ref.blob_sha256), targets, ()
        )
        found.extend(children)
        gaps.extend(gap.replace(": ", f":{ref.request_key}: ", 1) for gap in missing)
    if rows:
        return tuple(found), tuple(gaps)
    return (), tuple(f"{named(s)}: no advertised children" for s in targets)


def continuation(request: Request, body: Body, page: int) -> str | None:
    """Read explicit next-page links, show-more continuations, or the timeline cursor."""
    tree = body.tree()
    for onclick in tree.xpath('//div[starts-with(@id,"show-more-")]/button/@onclick'):
        query = re.search(r"Utils\.ajaxLoad\(event, '\?([^']+)'\)", onclick)
        if query:
            return query_url(request.url, **dict(parse_qsl(query[1])))
    if request.spec.id in {
        "screens-list",
        "screen-page",
        "product-prices",
        "filter-popular-queries",
        "filter-public-queries",
        "filter-popular-queries-api",
        "filter-public-queries-api",
    }:
        return None
    if request.spec.id == "company-timeline-api":
        cells = tree.xpath('//tr[contains(@class,"d-none")]/td')
        if cells and cells[-1].text_content().strip() == "True":
            return query_url(request.url, timestamp=cells[0].text_content().strip())
        return None
    key = (
        "page"
        if request.spec.site is Site.TIJORI
        or "page" in dict(parse_qsl(urlsplit(request.url).query, keep_blank_values=True))
        else "p"
    )
    for href in tree.xpath("//a[@href]/@href"):
        target = urljoin(request.url, href)
        number = dict(parse_qsl(urlsplit(target).query)).get(key)
        if (
            urlsplit(target).path == urlsplit(request.url).path
            and number
            and number.isdigit()
            and int(number) == page + 1
        ):
            return query_url(request.url, **{key: str(page + 1)})
    if tree.xpath('//button[contains(@class,"show_more") and not(@disabled)]'):
        return query_url(request.url, **{key: str(page + 1)})
    return None


def capture_market(
    fetcher: VendorFetcher,
    store: SnapshotStore,
    pool: ConnectionPool,
    values: VendorValuesStore,
    specs: tuple[SurfaceSpec, ...],
    *,
    requests: tuple[Request, ...] | None = None,
    today: date | None = None,
    scheduled: bool = False,
) -> RunReport:
    """Capture finite advertisements and resume each feed from registered evidence.

    A scheduled subset captures only its requests (each traversal to its end or cap); advertised
    children wait for the scheduler, which enqueues the eligible ones.
    """
    pending = list(market_requests(specs, pool) if requests is None else requests)
    routes, gaps = company_routes(store, pool, specs) if requests is None else ((), ())
    pending.extend(routes)
    seen: set[str] = set()
    stopped: list[Site] = []
    incomplete: list[str] = list(gaps)
    refused: list[str] = []
    expected, completed = len(gaps), 0
    today = today or datetime.now(UTC).date()
    while pending:
        initial = pending.pop(0)
        if initial.url in seen:
            continue
        seen.add(initial.url)
        key = traversal_key(initial)
        state = progress(pool, key)
        request = initial.model_copy(update={"url": state.resume_url or initial.url})
        if request.spec.site is Site.TIJORI and request.spec.feed and not state.resume_url:
            start = (
                state.boundary.date_to
                if state.boundary and state.boundary.date_to
                else date(1970, 1, 1)
            )
            request = request.model_copy(
                update={
                    "url": query_url(request.url, daterange=f"{start:%m/%d/%Y},{today:%m/%d/%Y}")
                }
            )
        page = state.resume_page or 1
        for _ in range(MAX_FEED_PAGES + int(state.resume_page is not None)):
            expected += 1
            if request.spec.site in stopped:
                refused.append(address(request))
                break
            try:
                ref, body = capture(fetcher, store, pool, values, request)
            except SiteStopped as error:
                stopped.append(error.site)
                incomplete.append(address(request))
                break
            except (SiteBusy, ValueError):
                (incomplete if fetcher.remaining(request.spec.site) == 0 else refused).append(
                    address(request)
                )
                break
            with pool.connection() as conn:
                usable = all(
                    row[0] in USABLE
                    for row in conn.execute(
                        "SELECT status FROM eqos.vendor_outcomes WHERE capture_ref_id=%s",
                        (ref.capture_ref_id,),
                    )
                )
                with conn.cursor(row_factory=dict_row) as cursor:
                    raw_values = cursor.execute(
                        "SELECT * FROM eqos.vendor_values WHERE capture_ref_id=%s "
                        "ORDER BY row_index,column_index",
                        (ref.capture_ref_id,),
                    ).fetchall()
            completed += int(usable)
            if not usable or body is None:
                incomplete.append(address(request))
                break
            cells = tuple(VendorValue.model_validate(row) for row in raw_values)
            row_ids = (
                [row.row_id for row in feed_rows(request.spec, cells)]
                if request.spec.feed
                else [cell.link for cell in cells if cell.link]
            )
            # An ambiguous feed identity can neither set nor reach a traversal boundary.
            unique = [r for r in row_ids if row_ids.count(r) == 1] if request.spec.feed else row_ids
            ambiguous = len(unique) < len(row_ids)
            if ambiguous:
                incomplete.append(f"{named(request.spec)}: rows without a unique identity")
            next_url = continuation(request, body, page)
            next_cursor = (
                dict(parse_qsl(urlsplit(next_url).query)).get("timestamp") if next_url else None
            )
            boundary = state.boundary
            done = not ambiguous and (
                next_url is None
                or bool(
                    boundary
                    and (
                        (boundary.row_id and boundary.row_id in unique)
                        or (boundary.cursor and boundary.cursor == next_cursor)
                    )
                )
            )
            marks = mark("row_id", unique[0] if unique else None) + mark("cursor", next_cursor)
            values.record(
                ref,
                Outcome(
                    surface=request.spec.id,
                    parser_version=f"{named(request.spec)}.{TRAVERSAL_VERSION}",
                    parser_sha256=parser_sha256(continuation),
                    status=OutcomeStatus.UNUSABLE if ambiguous else OutcomeStatus.KEPT,
                    symbol=request.ids.nse_symbol if request.ids else None,
                    detail="rows without a unique identity" if ambiguous else None,
                    values=marks,
                    traversal_key=key,
                    traversal_page=page,
                    traversal_done=done,
                ),
                row_count=len(marks),
            )
            if page == 1 and not scheduled:
                record = store.get_capture(
                    ref.source_id, ref.surface, ref.request_key, ref.capture_id
                )
                context = request.context(record, ref.blob_sha256)
                children, gaps = advertised(request, body, context, specs, ())
                pending.extend(children)
                incomplete.extend(gaps)
                expected += len(gaps)
            if done or ambiguous:
                break
            if next_url == request.url:
                incomplete.append(address(request) + ": repeated continuation")
                break
            assert next_url is not None
            request = request.model_copy(update={"url": next_url})
            page += 1
        else:
            incomplete.append(address(initial) + ": page cap")
    return RunReport(
        expected=expected,
        completed=completed,
        refused=tuple(refused),
        incomplete=tuple(incomplete),
        stopped_sites=tuple(dict.fromkeys(stopped)),
    )
