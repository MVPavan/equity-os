"""One bounded document-intake pass; durable revisions drive retries and bead reconciliation."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from contextlib import ExitStack
from datetime import datetime, timedelta
from typing import cast
from urllib.parse import urlsplit

import psycopg
from pydantic import TypeAdapter

from fundamentals.api.shareholding_cli import PAUSE_SECONDS
from fundamentals.api.watchlist_config import load_watchlist_config
from fundamentals.compare.run_models import RunExitStatus
from fundamentals.contracts.entity_identity import IdentifierNamespace
from fundamentals.contracts.onboarding import VerificationUnit
from fundamentals.contracts.snapshot import SnapshotError
from fundamentals.contracts.source_catalog import (
    DOCUMENT_LISTINGS,
    NSE_MASTER,
    SCREENER_PAGE,
    VENDOR_SURFACES,
    DocumentKind,
)
from fundamentals.entity.discovery import (
    OK,
    Capture,
    Request,
    Response,
    Send,
    acquiring_fetch,
    authorised,
    register_capture,
)
from fundamentals.entity.identity_layers import latest_slice
from fundamentals.entity.verification import master_rows
from fundamentals.evidence.capture_retention import Registration
from fundamentals.ingest.first_party_documents import (
    IST,
    AnnouncementClass,
    DocumentLink,
    announcement_link,
    classify_announcement,
    document_request,
    listing_rows,
    meeting_date,
    nse_listing_url,
)
from fundamentals.ingest.nse_filings import EQUITY_MASTER_URL
from fundamentals.ingest.screener_documents import read_screener_documents
from fundamentals.pg.document_intake import (
    COVERED,
    FAILED_START,
    INTAKE_ISSUERS,
    REGISTERED,
    RETENTION_SHARED,
    TERMINAL,
    DocumentIntake,
    refusal,
)
from fundamentals.pg.pool import DatabaseUnavailableError, open_pool
from fundamentals.pg.settings import PgRole, PgSettings
from fundamentals.store.snapshot_store import SnapshotStore

BdRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]
BD_LOOKUP = ("list", "--all", "--external-contains", "docs-", "--limit", "0", "--json", "--brief")
BACKFILL = "backfill"
ANNOUNCEMENTS, MEETINGS, REPORTS = DOCUMENT_LISTINGS
SCREENER_SURFACE = SCREENER_PAGE[1]
ALL_SURFACES = (*DOCUMENT_LISTINGS, SCREENER_SURFACE)
UNCOVERED_LINE = "UNCOVERED\t{}\t{}\t{}\t{}\n"
GAP_LINE = "GAP\t{}\t{}\t{}\t{}\n"
TRIGGER_LINE = "{}\t{}\t{}\t{}\t{}\t{}\n"
TRIGGERS = {DocumentKind.RESULTS, DocumentKind.TRANSCRIPT, DocumentKind.PRESENTATION}
LOCK_NAME = "documents.lock"
BD_ROWS = TypeAdapter(list[dict[str, object]])


def run_documents(
    args: argparse.Namespace, *, send: Send, clock: Callable[[], datetime], bd: BdRunner
) -> int:
    """Serialize one pass, atomically retain listings/documents, then reconcile durable triggers."""
    write, refuse = sys.stdout.write, sys.stderr.write
    today = clock().astimezone(IST).date()
    backfill = args.documents_command == BACKFILL
    if backfill and (args.from_date > args.to_date or args.annual_reports < 1):
        refuse("refused document backfill arguments\n")
        return RunExitStatus.FAILURE
    resources = ExitStack()
    try:
        args.lock_root.mkdir(parents=True, exist_ok=True)
        lock = resources.enter_context((args.lock_root / LOCK_NAME).open("a"))
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        store = SnapshotStore(args.snapshot_root)
        resources.enter_context(store.prepare_ordinary_output())
        pool = resources.enter_context(open_pool(PgSettings(), PgRole.RUNTIME))
        conn = resources.enter_context(pool.connection())
        incomplete = False
        fetch = acquiring_fetch(send, clock, [])
        conn.autocommit = True
        intake = DocumentIntake(conn)
        registration = Registration(conn)
        held = latest_slice(conn, today)
        issuers: list[tuple[int, str, str]] = []
        for (entity,) in conn.execute(COVERED).fetchall():
            symbols = {
                h.value
                for h in held
                if h.entity_id == entity and h.namespace is IdentifierNamespace.NSE_SYMBOL
            }
            isins = {
                h.value
                for h in held
                if h.entity_id == entity and h.namespace is IdentifierNamespace.ISIN
            }
            if len(symbols) != 1 or len(isins) != 1:
                write(f"UNCOVERED_ISSUER\t{entity}\n")
                incomplete = True
            elif not backfill or args.symbol in symbols:
                issuers.append((entity, symbols.pop(), isins.pop()))
        if backfill and not issuers:
            write(f"UNCOVERED_ISSUER\t{args.symbol}\n")
            return RunExitStatus.INCOMPLETE
        master = b""
        if issuers:
            time.sleep(PAUSE_SECONDS)
            request = Request(
                unit=VerificationUnit.EXCHANGE,
                source_id=NSE_MASTER[0],
                surface=NSE_MASTER[1],
                url=EQUITY_MASTER_URL,
            )
            response = fetch(request, authorised(request, VENDOR_SURFACES))
            master = response.body or b""
            incomplete |= response.outcome != OK
        for entity, symbol, isin in issuers:
            verified = master_rows(master, symbol)
            identity_ok = len(verified) == 1 and verified[0][1] == isin
            surfaces = (
                ALL_SURFACES
                if backfill and args.screener
                else (DOCUMENT_LISTINGS if backfill else DOCUMENT_LISTINGS[:2])
            )
            for surface in surfaces:
                covered = intake.coverage(entity, surface)
                start = (
                    covered - timedelta(days=3)
                    if covered
                    else (args.from_date if backfill else today - timedelta(days=3))
                )
                failed = conn.execute(FAILED_START, (entity, surface)).fetchone()
                if failed is not None and failed[0] is not None:
                    start = min(start, failed[0])
                end = (
                    args.to_date
                    if backfill
                    else today + timedelta(days=90 if surface == MEETINGS else 0)
                )
                windows = []
                if surface in DOCUMENT_LISTINGS[:2]:
                    while start <= end:
                        stop = min(start + timedelta(days=30), end)
                        windows.append((start, stop))
                        start = stop + timedelta(days=1)
                else:
                    windows = [(None, None)]
                stopped = False
                for index, (span_from, span_to) in enumerate(windows):
                    if stopped or index >= 12:
                        write(UNCOVERED_LINE.format(symbol, surface, span_from, span_to))
                        incomplete = True
                        continue
                    url = (
                        nse_listing_url(surface, symbol, span_from or today, span_to or today)
                        if surface in DOCUMENT_LISTINGS
                        else f"https://www.screener.in/company/{symbol}/consolidated/"
                    )
                    source = "nse" if surface in DOCUMENT_LISTINGS else SCREENER_PAGE[0]
                    request = Request(
                        unit=VerificationUnit.EXCHANGE,
                        source_id=source,
                        surface=surface,
                        url=url,
                    )
                    time.sleep(PAUSE_SECONDS)
                    response = fetch(request, authorised(request, VENDOR_SURFACES))
                    outcome = response.outcome
                    observations = []
                    if outcome == OK:
                        try:
                            if not identity_ok:
                                raise ValueError("refused master identity")
                            body = cast(bytes, response.body)
                            if surface == SCREENER_SURFACE:
                                config = load_watchlist_config(args.config_root / "watchlist.yaml")
                                expected = config.stock(symbol).identifiers.screener_company_id
                                documents = read_screener_documents(
                                    body, expected_company_id=expected
                                )
                                observations = [
                                    (link.url, link.model_dump(mode="json"))
                                    for link in documents.links
                                ]
                            else:
                                observations = listing_rows(surface, body)
                                if surface == ANNOUNCEMENTS and len(observations) != len(
                                    json.loads(body)
                                ):
                                    incomplete = True
                                if surface != REPORTS:
                                    accepted = [
                                        (key, row)
                                        for key, row in observations
                                        if row.get("sm_isin") == isin
                                    ]
                                    if len(accepted) != len(observations):
                                        refuse(f"refused listing ISIN\t{symbol}\t{surface}\n")
                                        incomplete = True
                                    observations = accepted
                                else:
                                    observations = sorted(
                                        observations,
                                        key=lambda item: int(item[1]["toYr"]),
                                        reverse=True,
                                    )[: args.annual_reports]
                        except (ValueError, KeyError, TypeError):
                            refuse(
                                "refused screener identity\n"
                                if surface == SCREENER_SURFACE
                                else f"refused listing\t{symbol}\t{surface}\n"
                            )
                            outcome, observations = "PARSE_ERROR", []
                    with conn.transaction():
                        conn.execute(RETENTION_SHARED)
                        ref_id = None
                        if outcome == OK:
                            item = Capture(request=request, response=response)
                            ref_id = register_capture(store, registration, item)[1].capture_ref_id
                        intake.record_listing(
                            dict(
                                entity_id=entity,
                                symbol=symbol,
                                surface=surface,
                                span_from=span_from,
                                span_to=span_to,
                                retrieved_at=response.retrieved_at,
                                outcome=outcome,
                                capture_ref_id=ref_id,
                            ),
                            observations,
                        )
                    if outcome != OK:
                        write(UNCOVERED_LINE.format(symbol, surface, span_from, span_to))
                        stopped = incomplete = True
            for surface in ALL_SURFACES:
                for observation in intake.latest(entity, surface):
                    payload, key = observation.payload, observation.occurrence_key
                    if surface == ANNOUNCEMENTS:
                        link = announcement_link(payload)
                    elif surface == REPORTS:
                        link = DocumentLink(
                            kind=DocumentKind.ANNUAL_REPORT,
                            period=str(payload["toYr"]),
                            url=payload["fileName"],
                            host=urlsplit(payload["fileName"]).netloc,
                            found_on=surface,
                        )
                    elif surface == SCREENER_SURFACE:
                        link = DocumentLink.model_validate(payload)
                    else:
                        continue
                    if link is None:
                        continue
                    pending_request = document_request(link)
                    if pending_request is None:
                        continue
                    request = pending_request
                    gap = symbol, link.kind, key
                    attempts = intake.attempts(observation.id, request.url)
                    if any(attempt.outcome == OK for attempt in attempts):
                        continue
                    terminal = next((a.outcome for a in attempts if a.outcome in TERMINAL), None)
                    if terminal or len(attempts) >= 5:
                        write(GAP_LINE.format(*gap, terminal or attempts[-1].outcome))
                        incomplete = True
                        continue
                    route = hashlib.sha256(request.key.encode()).hexdigest()
                    remnants = [
                        r
                        for r in store.list_captures(request.source_id, request.surface, route)
                        if r.retrieved_at >= observation.observed_at
                        and conn.execute(
                            REGISTERED,
                            (request.source_id, request.surface, route, r.capture_id),
                        ).fetchone()
                        is None
                    ]
                    if remnants:
                        remnant = max(remnants, key=lambda record: record.retrieved_at)
                        response = Response(
                            outcome=OK,
                            body=store.read_body(remnant),
                            retrieved_at=remnant.retrieved_at,
                        )
                    else:
                        time.sleep(PAUSE_SECONDS)
                        response = fetch(request, authorised(request, VENDOR_SURFACES))
                    outcome = (
                        refusal(link.kind, cast(bytes, response.body))
                        if response.outcome == OK
                        else response.outcome
                    )
                    with conn.transaction():
                        conn.execute(RETENTION_SHARED)
                        ref_id = None
                        if outcome == OK:
                            item = Capture(request=request, response=response)
                            ref_id = register_capture(store, registration, item)[1].capture_ref_id
                        intake.record_attempt(
                            observation.id,
                            request.url,
                            response.retrieved_at,
                            outcome,
                            hashlib.sha256(response.body).hexdigest()
                            if response.body is not None
                            else None,
                            ref_id,
                        )
                    if outcome in TERMINAL or (outcome != OK and len(attempts) + 1 >= 5):
                        write(GAP_LINE.format(*gap, outcome))
                    incomplete |= outcome != OK
        try:
            lookup = bd(BD_LOOKUP)
            if lookup.returncode:
                raise ValueError("bd lookup failed")
            refs = {row.get("external_ref") for row in BD_ROWS.validate_json(lookup.stdout)}
        except (OSError, subprocess.SubprocessError, ValueError, TypeError):
            write("BD_LOOKUP_FAILED\n")
            return RunExitStatus.FAILURE
        for entity, symbol in conn.execute(INTAKE_ISSUERS).fetchall():
            for surface in ALL_SURFACES:
                for observation in intake.latest(entity, surface):
                    row, key = observation.payload, observation.occurrence_key
                    if surface == MEETINGS:
                        meeting = meeting_date(row)
                        if (
                            row["bm_purpose"] == "Financial Results"
                            and meeting is not None
                            and meeting >= today
                        ):
                            write(f"RESULTS_SCHEDULED\t{symbol}\t{meeting}\t{key}\n")
                        continue
                    kind = (
                        classify_announcement(row)
                        if surface == ANNOUNCEMENTS
                        else row.get("kind", "ANNUAL_REPORT")
                    )
                    candidate = kind == AnnouncementClass.CONCALL_UNRESOLVED
                    if kind not in TRIGGERS and not candidate:
                        continue
                    prefix, label = (
                        ("docs-candidate", "doc-classification")
                        if candidate
                        else ("docs-trigger", "update-run")
                    )
                    ref = f"{prefix}:{symbol}:{key}"
                    filed = row.get("an_dt", row.get("period", ""))
                    filename = row.get("attchmntFile", row.get("url", ""))
                    action = "exists" if ref in refs else "created"
                    if ref not in refs:
                        title = f"{symbol} {kind} {filed}"
                        description = f"{kind} filed {filed}; attachment {filename}"
                        command = ("create", title, "-t", "task", "-l", label)
                        result = bd((*command, "--external-ref", ref, "-d", description))
                        if result.returncode:
                            return RunExitStatus.FAILURE
                        refs.add(ref)
                    tag = "CANDIDATE" if candidate else "TRIGGER"
                    write(TRIGGER_LINE.format(tag, symbol, kind, filed, key, action))
        return RunExitStatus.INCOMPLETE if incomplete else RunExitStatus.SUCCESS
    except (
        OSError,
        LookupError,
        ValueError,
        psycopg.Error,
        DatabaseUnavailableError,
        SnapshotError,
        subprocess.SubprocessError,
    ) as error:
        refuse(f"documents failed: {type(error).__name__}\n")
        return RunExitStatus.FAILURE
    finally:
        resources.close()
