"""Bank grounding (spec 2026-11-06-vendor-first §8 step 1): retain the latest two listed
integrated periods' candidate instances and results PDFs on the retention-only ``nse-grounding``
surfaces and read their branch evidence from the bytes. Entity-free: no eligibility, framework or
schema filter decides what is retained, and nothing but captures is written."""

from __future__ import annotations

import hashlib
import re
from itertools import chain
from typing import Any, cast

import psycopg
import pymupdf
from lxml import etree  # type: ignore[import-untyped]

from equity_os.companies.onboarding.discovery import Fetch, Response
from equity_os.companies.onboarding.verification import master_rows
from equity_os.contracts.companies.onboarding import VerificationUnit
from equity_os.contracts.sourcing.source_catalog import (
    NSE_GROUNDING_PDF,
    NSE_GROUNDING_XBRL,
    NSE_INTEGRATED_LISTING,
    NSE_MASTER,
    NSE_RESULTS_LISTING,
)
from equity_os.extraction.packages.member_identity import (
    FRAMEWORK_DECLARATIONS,
    INTEGRATED_FORM,
    PDF_SYMBOL_MARKER,
)
from equity_os.extraction.xbrl.xbrl_parser import (
    REPORTING_PERIOD_END_CONCEPT,
    REPORTING_PERIOD_START_CONCEPT,
    SCOPE_CONCEPT,
)
from equity_os.sourcing.documents.first_party_documents import DocumentLink
from equity_os.sourcing.exchange.nse_filings import (
    EQUITY_MASTER_URL,
    INTEGRATED_LISTING,
    LEGACY_LISTING,
    collapse,
    listing_rows,
    listing_url,
)
from equity_os.sourcing.exchange.results_filing import PDF_DAYS, results_pdfs, retain
from equity_os.storage.raw_files.snapshot_store import SnapshotStore

UNRESOLVED = "UNRESOLVED"
FETCH_FAILED = "FETCH_FAILED"
PERIODS = 2
_XBRLI = "{http://www.xbrl.org/2003/instance}"
_XBRLDI = "{http://xbrl.org/2006/xbrldi}"
_SCHEMA_REF = "{http://www.xbrl.org/2003/linkbase}schemaRef"
_HREF = "{http://www.w3.org/1999/xlink}href"
_PDF_MARKERS = tuple(
    marker.lower()
    for marker in (
        *chain.from_iterable(FRAMEWORK_DECLARATIONS.values()),
        "prepared in accordance with",
        PDF_SYMBOL_MARKER,
    )
)
_HEADING = re.compile(r"(quarter|year|months|period) ended|standalone|consolidated", re.I)
_TAXONOMY_CONCEPTS = (SCOPE_CONCEPT, REPORTING_PERIOD_START_CONCEPT, REPORTING_PERIOD_END_CONCEPT)


def ground(
    conn: psycopg.Connection[Any], store: SnapshotStore, fetch: Fetch, symbol: str
) -> dict[str, Any]:
    """The structure JSON: the master's ISINs and, per latest listed integrated period, each
    basis's candidate instance and every results PDF, each read from its retained bytes."""
    exchange = VerificationUnit.EXCHANGE
    master = retain(conn, store, fetch, exchange, NSE_MASTER, EQUITY_MASTER_URL)
    isins = [isin for _, isin in master_rows(cast(bytes, master.body), symbol)] if master else []
    legacy, integrated = (
        retain(conn, store, fetch, exchange, pair, listing_url(path, symbol, period))
        for pair, (path, period) in (
            (NSE_RESULTS_LISTING, LEGACY_LISTING),
            (NSE_INTEGRATED_LISTING, INTEGRATED_LISTING),
        )
    )
    structure: dict[str, Any] = {"symbol": symbol, "isins": isins, "periods": []}
    if legacy is None or integrated is None:
        structure["listings"] = FETCH_FAILED
        return structure
    rows = [
        row
        for row in listing_rows(cast(bytes, legacy.body), cast(bytes, integrated.body))
        if row.integrated
    ]
    for end in sorted({row.period_end for row in rows}, reverse=True)[:PERIODS]:
        listed = [row for row in rows if row.period_end == end]
        instances = []
        for basis in sorted({row.basis for row in listed}):
            latest, tied = collapse([row for row in listed if row.basis == basis])
            entry: dict[str, Any] = {"basis": basis}
            url = latest[0].xbrl_url if latest and not tied else None
            if url is None:
                instances.append({**entry, "status": UNRESOLVED})
                continue
            row = latest[0]
            entry |= {"type": row.kind, "url": url, "broadcast": str(row.broadcast)}
            unit = VerificationUnit.XBRL_ENTITY
            response = retain(conn, store, fetch, unit, NSE_GROUNDING_XBRL, url)
            body = response.body if response else None
            instances.append({**entry, **(_instance(body) if body else {"status": FETCH_FAILED})})
        broadcasts = [row.broadcast for row in listed if row.broadcast]
        pdfs = []
        if broadcasts:
            span = (end, max(broadcasts).date() + PDF_DAYS)
            found = results_pdfs(conn, store, fetch, symbol, span, NSE_GROUNDING_PDF)
            pdfs = [_pdf(link, response) for link, response in found]
        structure["periods"].append({"period_end": str(end), "instances": instances, "pdfs": pdfs})
    return structure


def _instance(body: bytes) -> dict[str, Any]:
    """An instance's branch evidence: references, namespaces, forms, every fact's context
    (amounts left out) and every non-numeric fact's value."""
    root = etree.fromstring(body)
    contexts = {
        context.get("id"): {
            "period": [node.text for node in context.iterfind(f"{_XBRLI}period/*")],
            "dimensions": {
                member.get("dimension"): (member.text or "").strip()
                for member in context.iter(f"{_XBRLDI}explicitMember", f"{_XBRLDI}typedMember")
            },
        }
        for context in root.iter(f"{_XBRLI}context")
    }
    facts = [node for node in root if node.get("contextRef") is not None]
    qnames = [etree.QName(node).text for node in facts]
    concepts: dict[str, list[str]] = {}
    for qname, node in zip(qnames, facts, strict=True):
        concepts.setdefault(qname, []).append(cast(str, node.get("contextRef")))
    return {
        "sha256": hashlib.sha256(body).hexdigest(),
        "schema_refs": [ref.get(_HREF) for ref in root.iter(_SCHEMA_REF)],
        "root_namespaces": dict(sorted((k or "", v) for k, v in root.nsmap.items())),
        "fact_namespaces": sorted({etree.QName(node).namespace or "" for node in facts}),
        "forms": sorted(
            {
                found.group(1)
                for element in root.iter(etree.Element)
                for uri in element.nsmap.values()
                if uri and (found := INTEGRATED_FORM.match(uri))
            }
        ),
        "taxonomy_concepts": sorted(
            {q for q in qnames if q.rsplit("}", 1)[-1] in _TAXONOMY_CONCEPTS}
        ),
        "contexts": contexts,
        "facts": concepts,
        "non_numeric": [
            {"qname": qname, "context": node.get("contextRef"), "value": node.text}
            for qname, node in zip(qnames, facts, strict=True)
            if node.get("unitRef") is None
        ],
    }


def _pdf(link: DocumentLink, response: Response) -> dict[str, Any]:
    """A results PDF's text layer per page and its declaration, marker and heading lines."""
    body = cast(bytes, response.body)
    pages, lines = [], []
    with pymupdf.open(stream=body, filetype="pdf") as document:  # type: ignore[no-untyped-call]
        for number, page in enumerate(document, start=1):
            text = page.get_text()
            pages.append({"page": number, "text_layer": bool(text.strip())})
            lines += [
                {"page": number, "line": line.strip()}
                for line in text.splitlines()
                if any(m in line.lower() for m in _PDF_MARKERS) or _HEADING.search(line)
            ]
    return {
        "sha256": hashlib.sha256(body).hexdigest(),
        "url": link.url,
        "filed_at": str(link.filed_at),
        "pages": pages,
        "lines": lines,
    }
