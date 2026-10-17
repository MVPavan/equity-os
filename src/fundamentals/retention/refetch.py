"""Fetching an expired exchange original back from its address (plan D9 R8 step 1, R10).

:func:`live_fetch` is the one network path: no redirects, a timeout, and a body that counts
only when read to EOF at the length the server announced. :func:`probe` hash-checks a sample
of a source's eligible captures before any of that source's exchange originals are deleted.
"""

from __future__ import annotations

import hashlib
import http.client
import urllib.error
import urllib.request
from collections import defaultdict
from collections.abc import Callable
from typing import Any, LiteralString

import psycopg

from fundamentals.contracts.retention import CaptureFacts
from fundamentals.contracts.retention_purge import (
    FetchFailure,
    FetchFailureCategory,
    ProbeOutcome,
)
from fundamentals.contracts.snapshot import BodyCompleteness
from fundamentals.ingest.http_session import NoRedirectHandler, read_bounded_capture
from fundamentals.store.snapshot_store import MAX_BODY_BYTES

Fetch = Callable[[str], bytes]
REFETCH_TIMEOUT_SECONDS = 60.0
PROBE_SAMPLE = 3
_INSERT_PROBE: LiteralString = (
    "INSERT INTO eqos.retention_probes (source_id, capture_ref_id, url, outcome, category, "
    "http_status, fetched_sha256, severity) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id"
)


def live_fetch(url: str) -> bytes:
    """The complete body at ``url``, or :class:`FetchFailure` naming why not."""
    opener = urllib.request.build_opener(NoRedirectHandler)
    try:
        with opener.open(url, timeout=REFETCH_TIMEOUT_SECONDS) as response:
            length = response.headers.get("Content-Length")
            read = read_bounded_capture(
                response,
                MAX_BODY_BYTES,
                timeout_seconds=REFETCH_TIMEOUT_SECONDS,
                expected_bytes=int(length) if length is not None else None,
            )
    except urllib.error.HTTPError as error:
        raise FetchFailure(FetchFailureCategory.HTTP_STATUS, error.code) from error
    except http.client.IncompleteRead as error:
        raise FetchFailure(FetchFailureCategory.INCOMPLETE) from error
    except TimeoutError as error:
        raise FetchFailure(FetchFailureCategory.TIMEOUT) from error
    except urllib.error.URLError as error:
        timed_out = isinstance(error.reason, TimeoutError)
        category = FetchFailureCategory.TIMEOUT if timed_out else FetchFailureCategory.CONNECTION
        raise FetchFailure(category) from error
    except OSError as error:
        raise FetchFailure(FetchFailureCategory.CONNECTION) from error
    if read.completeness is not BodyCompleteness.COMPLETE or read.raw_body is None:
        raise FetchFailure(FetchFailureCategory.INCOMPLETE)
    return read.raw_body


def probe(
    conn: psycopg.Connection[Any], facts: tuple[CaptureFacts, ...], fetch: Fetch
) -> dict[str, ProbeOutcome]:
    """Fetch up to :data:`PROBE_SAMPLE` captures per source (lowest ids) and record each;
    the first mismatch or failure halts that source with a HIGH row (R8 step 1, R9)."""
    samples: defaultdict[str, list[tuple[CaptureFacts, str]]] = defaultdict(list)
    for fact in sorted(facts, key=lambda f: f.capture_ref_id):
        if fact.url is not None and len(samples[fact.source_id]) < PROBE_SAMPLE:
            samples[fact.source_id].append((fact, fact.url))
    outcomes: dict[str, ProbeOutcome] = {}
    for source_id, sample in samples.items():
        for fact, url in sample:
            category, status, fetched = None, None, None
            try:
                fetched = hashlib.sha256(fetch(url)).hexdigest()
            except FetchFailure as failure:
                category, status = failure.category, failure.http_status
            matched = fetched == fact.blob_sha256
            outcome = "MATCH" if matched else "FAILED" if category else "MISMATCH"
            params = (source_id, fact.capture_ref_id, url, outcome, category, status, fetched)
            with conn.transaction():
                row = conn.execute(_INSERT_PROBE, (*params, None if matched else "HIGH"))
                (probe_id,) = row.fetchall()[0]
            outcomes[source_id] = ProbeOutcome(matched=matched, probe_id=probe_id)
            if not matched:
                break
    return outcomes
