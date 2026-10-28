"""One bounded document-intake pass; durable revisions drive retries and bead reconciliation."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import subprocess
import sys
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import ExitStack, contextmanager
from datetime import date, datetime, timedelta
from typing import Any, cast

import psycopg
from pydantic import TypeAdapter

from fundamentals.api.shareholding_cli import PAUSE_SECONDS
from fundamentals.api.watchlist_config import load_watchlist_config
from fundamentals.compare.run_models import RunExitStatus
from fundamentals.contracts.entity_identity import IdentifierNamespace
from fundamentals.contracts.onboarding import VerificationUnit
from fundamentals.contracts.snapshot import SnapshotError
from fundamentals.contracts.source_catalog import (
    NSE_MASTER,
    SCREENER_PAGE,
    VENDOR_SURFACES,
    DocumentKind,
)
from fundamentals.entity.discovery import (
    OK,
    Capture,
    Fetch,
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
    ANNOUNCEMENTS,
    IST,
    MEETINGS,
    REPORTS,
    AnnouncementClass,
    classify_announcement,
    document_request,
    listing_rows,
    meeting_date,
    nse_listing_url,
    observed_link,
)
from fundamentals.ingest.nse_filings import EQUITY_MASTER_URL
from fundamentals.ingest.screener_documents import read_screener_documents
from fundamentals.pg.document_intake import (
    COVERED,
    INTAKE_ISSUERS,
    REGISTERED,
    RETENTION_SHARED,
    TERMINAL,
    DocumentIntake,
    Observation,
    refusal,
)
from fundamentals.pg.pool import DatabaseUnavailableError, open_pool
from fundamentals.pg.settings import PgRole, PgSettings
from fundamentals.store.snapshot_store import SnapshotStore

BdRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]
BD_LOOKUP = ("list", "--all", "--external-contains", "docs-", "--limit", "0", "--json", "--brief")
BD_ROWS = TypeAdapter(list[dict[str, object]])
BACKFILL = "backfill"
LOCK_NAME = "documents.lock"
SCREENER = SCREENER_PAGE[1]
SCREENER_URL = "https://www.screener.in/company/{}/consolidated/"
PARSE_ERROR = "PARSE_ERROR"
TRIGGERS = {AnnouncementClass.RESULTS, AnnouncementClass.TRANSCRIPT, AnnouncementClass.PRESENTATION}
OVERLAP = timedelta(days=3)
MEETING_HORIZON = timedelta(days=90)
SPAN = timedelta(days=30)
MAX_SPANS = 12
MAX_ATTEMPTS = 5
Span = tuple[date | None, date | None]


def run_documents(
    args: argparse.Namespace, *, send: Send, clock: Callable[[], datetime], bd: BdRunner
) -> int:
    """Serialize one pass, atomically retain listings/documents, then reconcile durable triggers."""
    try:
        with ExitStack() as stack:
            args.lock_root.mkdir(parents=True, exist_ok=True)
            lock = stack.enter_context((args.lock_root / LOCK_NAME).open("a"))
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            store = SnapshotStore(args.snapshot_root)
            stack.enter_context(store.prepare_ordinary_output())
            pool = stack.enter_context(open_pool(PgSettings(), PgRole.RUNTIME))
            conn = stack.enter_context(pool.connection())
            conn.autocommit = True
            today = clock().astimezone(IST).date()
            return _Pass(args, conn, store, acquiring_fetch(send, clock, []), today).run(bd)
    except (
        OSError,
        LookupError,
        ValueError,
        psycopg.Error,
        DatabaseUnavailableError,
        SnapshotError,
        subprocess.SubprocessError,
    ) as error:
        sys.stderr.write(f"documents failed: {type(error).__name__}\n")
        return RunExitStatus.FAILURE


class _Pass:
    """One pass's connection, store and running INCOMPLETE flag, shared by its steps."""

    def __init__(
        self,
        args: argparse.Namespace,
        conn: psycopg.Connection[Any],
        store: SnapshotStore,
        fetch: Fetch,
        today: date,
    ) -> None:
        self.args, self.conn, self.store, self.fetch, self.today = args, conn, store, fetch, today
        self.intake = DocumentIntake(conn)
        self.backfill = args.documents_command == BACKFILL
        self.incomplete = False

    def run(self, bd: BdRunner) -> int:
        """Steps 1-6 of the plan in order; bd reconciliation reads every retained issuer."""
        issuers = self._issuers()
        if self.backfill and not issuers:
            sys.stdout.write(f"UNCOVERED_ISSUER\t{self.args.symbol}\n")
            return RunExitStatus.INCOMPLETE
        master = b""
        if issuers:
            master = self._get(_exchange(*NSE_MASTER, EQUITY_MASTER_URL)).body or b""
        surfaces: tuple[str, ...] = (ANNOUNCEMENTS, MEETINGS)
        if self.backfill:
            surfaces += (REPORTS, SCREENER) if self.args.screener else (REPORTS,)
        for entity, symbol, isin in issuers:
            verified = [found for _, found in master_rows(master, symbol)] == [isin]
            for surface in surfaces:
                self._listing(entity, symbol, isin if verified else None, surface)
            self._documents(entity, symbol)
        if not self._beads(bd):
            return RunExitStatus.FAILURE
        return RunExitStatus.INCOMPLETE if self.incomplete else RunExitStatus.SUCCESS

    def _issuers(self) -> list[tuple[int, str, str]]:
        """Covered issuers with one NSE symbol and ISIN; others print UNCOVERED_ISSUER."""
        held = latest_slice(self.conn, self.today)
        found = []
        for (entity,) in self.conn.execute(COVERED).fetchall():
            symbols, isins = (
                {h.value for h in held if h.entity_id == entity and h.namespace is namespace}
                for namespace in (IdentifierNamespace.NSE_SYMBOL, IdentifierNamespace.ISIN)
            )
            if len(symbols) != 1 or len(isins) != 1:
                sys.stdout.write(f"UNCOVERED_ISSUER\t{entity}\n")
                self.incomplete = True
            elif not self.backfill or self.args.symbol in symbols:
                found.append((entity, symbols.pop(), isins.pop()))
        return found

    def _get(self, request: Request) -> Response:
        """One polite fetch on the request's pinned surface."""
        time.sleep(PAUSE_SECONDS)
        response = self.fetch(request, authorised(request, VENDOR_SURFACES))
        self.incomplete |= response.outcome != OK
        return response

    @contextmanager
    def _registered(self, request: Request, response: Response, ok: bool) -> Iterator[int | None]:
        """One transaction: register an OK body, then the caller records its row."""
        with self.conn.transaction():
            self.conn.execute(RETENTION_SHARED)
            item = Capture(request=request, response=response)
            ref = register_capture(self.store, Registration(self.conn), item)[1] if ok else None
            yield ref.capture_ref_id if ref else None

    def _listing(self, entity: int, symbol: str, isin: str | None, surface: str) -> None:
        """Read a listing's spans from its coverage; the first failure stops the advance."""
        covered = self.intake.coverage(entity, surface)
        default = self.args.from_date if self.backfill else self.today - OVERLAP
        first = self.intake.first_span(entity, surface)
        start = covered - OVERLAP if covered else min(default, first or default)
        horizon = MEETING_HORIZON if surface == MEETINGS else timedelta()
        end = self.args.to_date if self.backfill else self.today + horizon
        spans: list[Span] = [(None, None)]
        if surface in (ANNOUNCEMENTS, MEETINGS):
            spans = []
            while start <= end:
                stop = min(start + SPAN, end)
                spans.append((start, stop))
                start = stop + timedelta(days=1)
        for index, span in enumerate(spans):
            if index >= MAX_SPANS or not self._span(entity, symbol, isin, surface, span):
                for span_from, span_to in spans[index:]:
                    sys.stdout.write(f"UNCOVERED\t{symbol}\t{surface}\t{span_from}\t{span_to}\n")
                self.incomplete = True
                return

    def _span(self, entity: int, symbol: str, isin: str | None, surface: str, span: Span) -> bool:
        """Fetch one listing span and commit its body, listing row and revisions together."""
        span_from, span_to = span
        if surface == SCREENER:
            request = _exchange(SCREENER_PAGE[0], surface, SCREENER_URL.format(symbol))
        else:
            url = nse_listing_url(surface, symbol, span_from or self.today, span_to or self.today)
            request = _exchange("nse", surface, url)
        response = self._get(request)
        outcome, observations = response.outcome, []
        if outcome == OK:
            try:
                observations = self._parse(symbol, isin, surface, cast(bytes, response.body))
            except (ValueError, KeyError, TypeError):
                refused = "screener identity" if surface == SCREENER else f"listing\t{symbol}"
                sys.stderr.write(f"refused {refused}\t{surface}\n")
                outcome, self.incomplete = PARSE_ERROR, True
        with self._registered(request, response, outcome == OK) as ref_id:
            listing = dict(
                entity_id=entity,
                symbol=symbol,
                surface=surface,
                span_from=span_from,
                span_to=span_to,
                retrieved_at=response.retrieved_at,
                outcome=outcome,
                capture_ref_id=ref_id,
            )
            self.intake.record_listing(listing, observations)
        return outcome == OK

    def _parse(
        self, symbol: str, isin: str | None, surface: str, body: bytes
    ) -> list[tuple[str, dict[str, Any]]]:
        """Observations of one listing body; rows for another ISIN are refused."""
        if isin is None:
            raise ValueError("refused master identity")
        if surface == SCREENER:
            config = load_watchlist_config(self.args.config_root / "watchlist.yaml")
            expected = config.stock(symbol).identifiers.screener_company_id
            documents = read_screener_documents(body, expected_company_id=expected)
            return [(link.url, link.model_dump(mode="json")) for link in documents.links]
        rows = listing_rows(surface, body)
        if surface == REPORTS:
            rows.sort(key=lambda item: int(item[1]["toYr"]), reverse=True)
            return rows[: self.args.annual_reports]
        accepted = [(key, row) for key, row in rows if row.get("sm_isin") == isin]
        if len(accepted) != len(json.loads(body)):
            sys.stderr.write(f"refused listing rows\t{symbol}\t{surface}\n")
            self.incomplete = True
        return accepted

    def _documents(self, entity: int, symbol: str) -> None:
        """Complete each latest revision's pending document within its attempt bound."""
        for surface in (ANNOUNCEMENTS, REPORTS, SCREENER):
            for observation in self.intake.latest(entity, surface):
                link = observed_link(surface, observation.payload)
                request = document_request(link) if link else None
                if link is None or request is None:
                    continue
                outcomes = self.intake.attempts(observation.id, request.url)
                if OK in outcomes:
                    continue
                if not _closed(outcomes):
                    outcomes.append(self._attempt(observation, link.kind, request))
                if outcomes[-1] != OK:
                    self.incomplete = True
                    if _closed(outcomes):
                        gap = f"{symbol}\t{link.kind}\t{observation.occurrence_key}\t{outcomes[-1]}"
                        sys.stdout.write(f"GAP\t{gap}\n")

    def _attempt(self, observation: Observation, kind: DocumentKind, request: Request) -> str:
        """Register a crash remnant without a request, else fetch; record one attempt."""
        route = hashlib.sha256(request.key.encode()).hexdigest()
        identity = request.source_id, request.surface, route
        remnants = [
            record
            for record in self.store.list_captures(*identity)
            if record.retrieved_at >= observation.observed_at
            and self.conn.execute(REGISTERED, (*identity, record.capture_id)).fetchone() is None
        ]
        if remnants:
            remnant = max(remnants, key=lambda record: record.retrieved_at)
            response = Response(
                outcome=OK, body=self.store.read_body(remnant), retrieved_at=remnant.retrieved_at
            )
        else:
            response = self._get(request)
        outcome = response.outcome
        if outcome == OK:
            outcome = refusal(kind, cast(bytes, response.body))
        digest = hashlib.sha256(response.body).hexdigest() if response.body is not None else None
        with self._registered(request, response, outcome == OK) as ref_id:
            attempt = (observation.id, request.url, response.retrieved_at, outcome, digest, ref_id)
            self.intake.record_attempt(*attempt)
        return outcome

    def _beads(self, bd: BdRunner) -> bool:
        """Print scheduled results; create each missing trigger or candidate bead exactly once."""
        try:
            lookup = bd(BD_LOOKUP)
            if lookup.returncode:
                raise ValueError("bd lookup failed")
            refs = {row.get("external_ref") for row in BD_ROWS.validate_json(lookup.stdout)}
        except (OSError, subprocess.SubprocessError, ValueError):
            sys.stdout.write("BD_LOOKUP_FAILED\n")
            return False
        for entity, symbol in self.conn.execute(INTAKE_ISSUERS).fetchall():
            for observation in self.intake.latest(entity, ANNOUNCEMENTS):
                row, key = observation.payload, observation.occurrence_key
                kind = classify_announcement(row)
                candidate = kind == AnnouncementClass.CONCALL_UNRESOLVED
                if kind not in TRIGGERS and not candidate:
                    continue
                tag, prefix, label = (
                    ("CANDIDATE", "docs-candidate", "doc-classification")
                    if candidate
                    else ("TRIGGER", "docs-trigger", "update-run")
                )
                ref, filed = f"{prefix}:{symbol}:{key}", row.get("an_dt", "")
                action = "exists"
                if ref not in refs:
                    description = f"{kind} filed {filed}; attachment {row.get('attchmntFile', '')}"
                    create = ("create", f"{symbol} {kind} {filed}", "-t", "task", "-l", label)
                    if bd((*create, "--external-ref", ref, "-d", description)).returncode:
                        return False
                    refs.add(ref)
                    action = "created"
                sys.stdout.write(f"{tag}\t{symbol}\t{kind}\t{filed}\t{key}\t{action}\n")
            for observation in self.intake.latest(entity, MEETINGS):
                meeting = meeting_date(observation.payload)
                purpose = observation.payload["bm_purpose"]
                if purpose == "Financial Results" and meeting and meeting >= self.today:
                    key = observation.occurrence_key
                    sys.stdout.write(f"RESULTS_SCHEDULED\t{symbol}\t{meeting}\t{key}\n")
        return True


def _exchange(source: str, surface: str, url: str) -> Request:
    """An exchange-unit request on a pinned surface."""
    return Request(unit=VerificationUnit.EXCHANGE, source_id=source, surface=surface, url=url)


def _closed(outcomes: list[str]) -> bool:
    """A terminal outcome or the retry bound ends a revision's attempts."""
    return bool(TERMINAL.intersection(outcomes)) or len(outcomes) >= MAX_ATTEMPTS
