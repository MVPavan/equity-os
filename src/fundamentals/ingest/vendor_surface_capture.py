"""Raw-first registration, parse dispatch and replay of registered vendor responses."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, ConfigDict

from fundamentals.api.screener_page_cli import basis_topology
from fundamentals.api.watchlist_config import StockConfig, load_watchlist_config
from fundamentals.contracts.evidence import CaptureReference
from fundamentals.contracts.snapshot import BodyCompleteness, CaptureRecord
from fundamentals.evidence.repository_rows import capture_of
from fundamentals.ingest.screener_session_models import Basis, ScreenerSessionError
from fundamentals.ingest.vendor_surface_fetch import Site, SiteStopped, VendorFetcher
from fundamentals.ingest.vendor_surface_parse import (
    PARSERS,
    Body,
    CompanyIds,
    ParseContext,
    parser_sha256,
)
from fundamentals.ingest.vendor_surface_readers import ReaderError
from fundamentals.ingest.vendor_surface_specs import SITE_NAME, ParseGroup, SurfaceSpec
from fundamentals.store.snapshot_store import SnapshotStore
from fundamentals.store.vendor_values_store import (
    Outcome,
    OutcomeStatus,
    VendorValue,
    VendorValuesStore,
    register,
)

WATCHLIST = Path("config/watchlist.yaml")
TOPOLOGY_UNKNOWN = "topology unknown"


class Request(BaseModel):
    """One expected request, carrying only verified context."""

    model_config = ConfigDict(frozen=True)
    spec: SurfaceSpec
    url: str
    ids: CompanyIds | None
    basis: Basis | None = None
    parent: Mapping[str, Any] | None = None
    due_since: datetime | None


class RunReport(BaseModel):
    """All expected work, including refusals and missing usable outcomes."""

    model_config = ConfigDict(frozen=True)
    expected: int
    completed: int
    refused: tuple[str, ...]
    incomplete: tuple[str, ...]
    stopped_sites: tuple[Site, ...]


def company_ids(stock: StockConfig) -> CompanyIds:
    """Copy configured bindings; unverified fields never become response expectations."""
    ids = stock.identifiers
    return CompanyIds(
        nse_symbol=ids.nse_symbol,
        isin=ids.isin or "",
        tijori_slug=None if ids.unverified_tijori_fields() else ids.tijori_slug,
        tijori_company_id=None if ids.unverified_tijori_fields() else ids.tijori_company_id,
        screener_company_id=None
        if "screener_company_id" in ids.needs_verification
        else ids.screener_company_id,
        topology=None
        if any(field.startswith("screener_warehouse_id_") for field in ids.needs_verification)
        else basis_topology(stock),
    )


def parse_and_record(
    store: SnapshotStore,
    values: VendorValuesStore,
    ref: CaptureReference,
    record: CaptureRecord,
    request: Request,
    body: Body | None = None,
) -> tuple[OutcomeStatus, ...]:
    """Read registered bytes and atomically store each logical surface's parse result."""
    context = ParseContext(
        ids=request.ids,
        basis=request.basis,
        url=request.url,
        retrieved_at=record.retrieved_at,
        body_sha256=ref.blob_sha256,
        capture_id=record.capture_id,
        parent=request.parent,
    )
    states = []
    for surface in (request.spec.id, *request.spec.sections):
        entry = PARSERS[request.spec.site, surface]
        version, digest = entry.version, parser_sha256(entry.parse)
        parsed: tuple[VendorValue, ...] = ()
        status, detail = OutcomeStatus.UNUSABLE, None
        try:
            if record.http_status != 200:
                detail = record.outcome.code.value
            elif record.effective_body_completeness is not BodyCompleteness.COMPLETE:
                detail = record.effective_body_completeness.value
            else:
                if body is None:
                    body = Body(raw=store.read_body(record))
                # A page proves login and identity even when its topology is unknown.
                if surface == "company-page":
                    parsed = entry.parse(body, context)
                if request.basis is not None and (
                    request.ids is None or request.ids.topology is None
                ):
                    version = f"{SITE_NAME[request.spec.site]}:gate.topology.v1"
                    digest = parser_sha256(topology_gate)
                    detail = TOPOLOGY_UNKNOWN
                elif request.spec.group is ParseGroup.NONE and surface == request.spec.id:
                    status = OutcomeStatus.KEPT
                else:
                    parsed = entry.parse(body, context)
                    status = (
                        OutcomeStatus.PARTIAL
                        if any(v.expected_numeric and v.value is None for v in parsed)
                        else (OutcomeStatus.OK if parsed else OutcomeStatus.EMPTY)
                    )
        except ReaderError as error:
            status, detail = OutcomeStatus.FAILED, str(error)
        except ScreenerSessionError as error:
            detail = type(error).__name__
        except Exception as error:
            status, detail = OutcomeStatus.FAILED, type(error).__name__
        assert ref.capture_ref_id is not None
        if not values.has_outcome(ref.capture_ref_id, surface, version):
            values.record(
                ref,
                Outcome(
                    surface=surface,
                    parser_version=version,
                    parser_sha256=digest,
                    status=status,
                    symbol=request.ids.nse_symbol if request.ids else None,
                    detail=detail,
                    values=parsed,
                ),
                row_count=len(parsed),
            )
        states.append(status)
    return tuple(states)


def topology_gate(body: Body, context: ParseContext) -> tuple[VendorValue, ...]:
    """The versioned refusal when the request has no bound basis topology."""
    return ()


def identity_gate(body: Body, context: ParseContext) -> tuple[VendorValue, ...]:
    """The versioned refusal when retained chart bytes have no matching company binding."""
    return ()


def capture(
    fetcher: VendorFetcher,
    store: SnapshotStore,
    pool: ConnectionPool,
    values: VendorValuesStore,
    request: Request,
) -> tuple[CaptureReference, Body | None]:
    """Register before parsing, including the response that durably stops a site."""
    try:
        fetched = fetcher.get(request.spec.site, request.spec.id, request.url, xhr=request.spec.xhr)
    except SiteStopped as error:
        if error.fetched is not None:
            try:
                ref = register(pool, error.fetched)
                entry = PARSERS[request.spec.site, request.spec.id]
                values.record(
                    ref,
                    Outcome(
                        surface=request.spec.id,
                        parser_version=entry.version,
                        parser_sha256=parser_sha256(entry.parse),
                        status=OutcomeStatus.UNUSABLE,
                        symbol=request.ids.nse_symbol if request.ids else None,
                        detail=type(error).__name__,
                    ),
                    row_count=0,
                )
            finally:
                fetcher.stop_dir.mkdir(parents=True, exist_ok=True)
                (fetcher.stop_dir / f"STOP-{error.site}").write_text(
                    f"{error.fetched.record.capture_id} {error.fetched.record.http_status}\n"
                )
        raise
    ref = register(pool, fetched)
    body = (
        Body(raw=store.read_body(fetched.record))
        if fetched.record.http_status == 200
        and fetched.record.effective_body_completeness is BodyCompleteness.COMPLETE
        else None
    )
    parse_and_record(store, values, ref, fetched.record, request, body)
    return ref, body


def reparse(
    store: SnapshotStore, pool: ConnectionPool, values: VendorValuesStore, spec: SurfaceSpec
) -> int:
    """Append outcomes under the current version using registered addresses and retained bytes."""
    entry = PARSERS[spec.site, spec.id]
    with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cursor:
        rows = cursor.execute(
            """SELECT c.*, a.url, (SELECT o.symbol FROM eqos.vendor_outcomes o
                WHERE o.capture_ref_id=c.id AND o.symbol IS NOT NULL ORDER BY o.id LIMIT 1)
                AS symbol FROM eqos.capture_refs c
            JOIN eqos.capture_addresses a ON a.capture_ref_id=c.id
            WHERE c.source_id=%s AND c.surface=%s
            AND eqos.capture_state(c.id) IN ('RETAINED','RESTORED')
            AND NOT EXISTS (SELECT 1 FROM eqos.vendor_outcomes o WHERE o.capture_ref_id=c.id
                AND o.surface=%s AND o.parser_version=%s) ORDER BY c.id""",
            (spec.site, "vs." + spec.id, spec.id, entry.version),
        ).fetchall()
    bindings = [company_ids(stock) for stock in load_watchlist_config(WATCHLIST).stocks]
    for row in rows:
        ref = capture_of(row)
        ids = next(
            (
                binding
                for binding in bindings
                if binding.nse_symbol == row["symbol"]
                or f"/company/{binding.nse_symbol}/" in row["url"]
            ),
            None,
        )
        if ids is None and row["symbol"] is None and spec.id == "chart-api":
            matches = [
                binding
                for binding in bindings
                if binding.screener_company_id is not None
                and urlsplit(row["url"]).path
                == f"/api/company/{binding.screener_company_id}/chart/"
            ]
            ids = matches[0] if len(matches) == 1 else None
        if spec.id == "chart-api" and (
            ids is None
            or ids.screener_company_id is None
            or urlsplit(row["url"]).path != f"/api/company/{ids.screener_company_id}/chart/"
        ):
            version = f"{SITE_NAME[spec.site]}:gate.identity.v1"
            assert ref.capture_ref_id is not None
            if not values.has_outcome(ref.capture_ref_id, spec.id, version):
                values.record(
                    ref,
                    Outcome(
                        surface=spec.id,
                        parser_version=version,
                        parser_sha256=parser_sha256(identity_gate),
                        status=OutcomeStatus.UNUSABLE,
                        symbol=None,
                        detail="verified company binding unavailable",
                    ),
                    row_count=0,
                )
            continue
        basis = (
            (Basis.CONSOLIDATED if "/consolidated/" in row["url"] else Basis.STANDALONE)
            if spec.id == "company-page"
            else None
        )
        record = store.get_capture(ref.source_id, ref.surface, ref.request_key, ref.capture_id)
        parse_and_record(
            store,
            values,
            ref,
            record,
            Request(spec=spec, url=row["url"], ids=ids, basis=basis, due_since=None),
        )
    return len(rows)
