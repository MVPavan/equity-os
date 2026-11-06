"""Re-ingest one entity-period's retained Screener and Tijori financials captures (VENDOR-1 §6.1).

Each capture an earlier extraction attempt of that entity, period end and basis cites is
ingested again under the current extractor and the named mapping set, with the issuer binding
onboarding built (``onboard_cli._vendor_adapters``): read from the stored identifiers and
settings, the capture's own bytes and, for Screener, the identity evidence its earlier
occurrences cite. Earlier rows are never changed; new ones are added beside them.

With ``captures_of`` (FIVE-1 Task 3) the captures are those the attempts at that source period
cite, and the evidence is recorded at ``period_end``, in two passes. The check pass parses every
adapter with no attempt, occurrence or interpretation write: an ``IDENTITY_REJECTED`` refusal is
fatal; each of Screener and Tijori must hold an occurrence ending at ``period_end`` in some
section; each parsed occurrence must equal any stored one under its capture, extractor version
and anchor. Any gap raises ``ReingestIncompleteError`` before the first write. Only then does
today's ingest run at ``period_end``, which reuses the stored occurrences and adds one attempt
per adapter. Nothing is relabelled and nothing is fetched.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from datetime import date
from functools import partial
from pathlib import Path
from typing import Any

from psycopg_pool import ConnectionPool

from equity_os.companies.identity.identity_seed import SettingKey
from equity_os.contracts.measurement.canonical import Basis, Representation
from equity_os.contracts.measurement.evidence import AttemptStage, CaptureReference
from equity_os.contracts.measurement.observation import AccountingFramework
from equity_os.contracts.sourcing.acquisition_outcome import ExtractionOutcome
from equity_os.contracts.sourcing.source_catalog import SCREENER_PAGE, TIJORI_PAGE
from equity_os.contracts.verification.config_versions import ConfigVersions
from equity_os.extraction.packages.member_identity import IssuerIdentifiers
from equity_os.extraction.surfaces.vendor_ingest import (
    VendorExtraction,
    VendorExtractionError,
    VendorIngestReport,
    VendorIngestRequest,
    _bound,
)
from equity_os.extraction.vendors.screener import vendor_screener
from equity_os.extraction.vendors.screener.screener_session_models import BasisTopology
from equity_os.extraction.vendors.screener.screener_session_page import (
    parse_document,
    read_identity,
)
from equity_os.extraction.vendors.tijori import vendor_tijori
from equity_os.extraction.vendors.tijori.tijori_page import JsonScriptCollector, decode_document
from equity_os.interface.commands.companies.onboard_cli import SCREENER_SECTIONS, TIJORI_DISPLAY
from equity_os.sourcing.vendors.tijori.tijori_capture import (
    COMPANY_DETAILS_ISLAND,
    FINANCIALS_PAGE_LABEL,
)
from equity_os.storage.raw_files.capture_retention import ingest_vendor_retained
from equity_os.storage.raw_files.snapshot_store import SnapshotStore
from equity_os.storage.records.repository import EvidenceRepository
from equity_os.verification.comparison.run_config import (
    load_run_config,
    vendor_extractor_pin,
    vendor_version_pin,
)
from equity_os.verification.comparison.selection import period_end as end_of

_NO_ENTITY = "no reporting entity {key!r}"
_NO_FISCAL_MONTH = "entity {key!r} has no fiscal-year-end month for {period}"
_IDENTITY_REF = "identity_evidence_ref"
_TIJORI_COMPANY_ID = "company_id"
_NO_VENDOR = "no {vendor} capture is cited at {source}"
_REJECTED = "capture {capture_id} is rejected: {detail}"
_UNBOUND = "no stored occurrence carries its identity evidence"
_UNCOVERED = "no {vendor} occurrence ends at {target}"
_DISAGREES = "capture {capture_id} anchor {anchor} differs from its stored occurrence"
Adapter = tuple[Any, str]  # the ``ingest_vendor`` adapter and its extractor version


class ReingestIncompleteError(LookupError):
    """The captures cannot record the target period; with ``captures_of``, nothing was written."""


def reingest(
    pool: ConnectionPool,
    store: SnapshotStore,
    config_root: Path,
    versions: ConfigVersions,
    *,
    entity: str,
    period_end: date,
    basis: Basis,
    captures_of: date | None = None,
) -> tuple[VendorIngestReport, ...]:
    """Ingest every retained financials capture of the entity-period again, or with
    ``captures_of`` those of that period at ``period_end`` (module docstring)."""
    repository = EvidenceRepository(pool)
    entity_id = repository.entity_id(entity)
    if entity_id is None:
        raise LookupError(_NO_ENTITY.format(key=entity))
    record = repository.settings_as_of(
        entity_id, SettingKey.FISCAL_YEAR_END_MONTH, repository.store_clock(), period_end
    )
    if record is None:
        raise LookupError(_NO_FISCAL_MONTH.format(key=entity, period=period_end))
    month = int(record.value_text)
    config = load_run_config(config_root, versions)
    ids = repository.issuer_identifiers(entity_id)
    captures = {
        attempt.capture.capture_ref_id: attempt.capture
        for attempt in repository.list_attempts(entity_id, captures_of or period_end)
        if attempt.capture is not None
        and attempt.stage is AttemptStage.EXTRACTION
        and attempt.basis is basis
        and (attempt.source_id, attempt.surface) in (SCREENER_PAGE, TIJORI_PAGE)
    }

    def request(capture: CaptureReference) -> VendorIngestRequest:
        return VendorIngestRequest(
            source_id=capture.source_id,
            surface=capture.surface,
            request_key=capture.request_key,
            capture_id=capture.capture_id,
            representation=Representation.HTML,
            entity_id=entity_id,
            period_end=period_end,
            basis=basis,
            framework=AccountingFramework.IND_AS,
        )

    def parsed(capture: CaptureReference) -> Iterator[tuple[Adapter, Any, bytes]]:
        identity = (capture.source_id, capture.surface, capture.request_key, capture.capture_id)
        record, body = store.read_capture_verified(*identity)
        for adapter in _adapters(repository, capture, body, ids, basis, month, config_root):
            yield adapter, record, body

    ordered = [capture for _, capture in sorted(captures.items())]
    if captures_of is not None:
        _check(repository, ordered, parsed, request, captures_of, period_end)
    reports = []
    for capture in ordered:
        for (extract, version), _, _ in parsed(capture):
            reports.append(
                ingest_vendor_retained(
                    request(capture),
                    extract=extract,
                    extractor_version=version,
                    snapshot_store=store,
                    repository=repository,
                    dictionary=config.dictionary,
                    mapping_set=config.mapping_set,
                    policy=config.normalisation_policy,
                    rounding_policy=config.rounding,
                    fiscal_year_end_month=month,
                )
            )
    return tuple(reports)


def _check(
    repository: EvidenceRepository,
    captures: list[CaptureReference],
    parsed: Callable[[CaptureReference], Iterator[tuple[Adapter, Any, bytes]]],
    request: Callable[[CaptureReference], VendorIngestRequest],
    source: date,
    target: date,
) -> None:
    """The check pass (module docstring): refuse before any write unless every capture parses
    without an identity refusal, both vendors cover the target and stored rows agree."""
    covered = dict.fromkeys((SCREENER_PAGE, TIJORI_PAGE), False)
    cited = {(capture.source_id, capture.surface) for capture in captures}
    if absent := sorted(covered.keys() - cited):
        raise ReingestIncompleteError(_NO_VENDOR.format(vendor=absent[0][0], source=source))
    for capture in captures:
        assert capture.capture_ref_id is not None
        page = (capture.source_id, capture.surface)
        for (extract, version), record, body in parsed(capture):
            pin = vendor_extractor_pin(capture.source_id, capture.surface, version=version)
            repository.pin_versions([vendor_version_pin(pin)])
            try:
                extraction = extract(
                    body, capture=capture, record=record, extractor_version=version
                )
                _bound(extraction, request(capture), repository)
            except VendorExtractionError as error:
                if error.outcome is ExtractionOutcome.IDENTITY_REJECTED:
                    detail = _REJECTED.format(capture_id=capture.capture_id, detail=error)
                    raise ReingestIncompleteError(detail) from error
                continue  # a section failure: the write pass records it as today
            stored = {
                row.anchor_key: row.model_dump(exclude={"occurrence_id"})
                for row in repository.list_capture_occurrences(capture.capture_ref_id, version)
            }
            for occurrence in extraction.occurrences:
                payload = stored.get(occurrence.anchor_key)
                if payload not in (None, occurrence.model_dump(exclude={"occurrence_id"})):
                    raise ReingestIncompleteError(
                        _DISAGREES.format(
                            capture_id=capture.capture_id, anchor=occurrence.anchor_key
                        )
                    )
                if occurrence.period is not None and end_of(occurrence.period) == target:
                    covered[page] = True
    for page, held in covered.items():
        if not held:
            raise ReingestIncompleteError(_UNCOVERED.format(vendor=page[0], target=target))


def _adapters(
    repository: EvidenceRepository,
    capture: CaptureReference,
    body: bytes,
    ids: IssuerIdentifiers,
    basis: Basis,
    month: int,
    config_root: Path,
) -> Iterator[Adapter]:
    """The capture's adapters under the current extractors: Screener once per page section."""
    if (capture.source_id, capture.surface) == TIJORI_PAGE:
        collector = JsonScriptCollector((COMPANY_DETAILS_ISLAND,))
        collector.feed(decode_document(body, page_label=FINANCIALS_PAGE_LABEL))
        collector.close()
        details = json.loads(collector.islands[COMPANY_DETAILS_ISLAND])
        binding = vendor_tijori.TijoriBinding(
            slug=capture.request_key,
            symbol=ids.nse_symbol,
            company_id=details[_TIJORI_COMPANY_ID],
        )
        display = vendor_tijori.load_tijori_display(config_root / TIJORI_DISPLAY)
        extract = partial(
            vendor_tijori.extract_tijori, binding=binding, display=display, basis=basis
        )
        yield extract, vendor_tijori.EXTRACTOR_VERSION
        return
    assert capture.capture_ref_id is not None
    earlier = repository.list_capture_occurrences(capture.capture_ref_id)
    if not earlier:  # never accepted, so no identity evidence binds it
        raise ReingestIncompleteError(
            _REJECTED.format(capture_id=capture.capture_id, detail=_UNBOUND)
        )
    company_id, warehouse_id = read_identity(parse_document(body.decode("utf-8")))
    screener = vendor_screener.ScreenerIssuerBinding(
        symbol=ids.nse_symbol,
        company_id=company_id,
        bse_code=ids.bse_scrip,
        topology=BasisTopology(consolidated_warehouse_id=warehouse_id),
        identity_evidence_ref=str(earlier[0].native_context[_IDENTITY_REF]),
        fiscal_year_end_month=month,
    )
    for section in SCREENER_SECTIONS:
        yield (
            partial(_screener, binding=screener, basis=basis, section=section),
            (vendor_screener.EXTRACTOR_VERSION),
        )


def _screener(body: bytes, *, record: Any, **options: Any) -> VendorExtraction:
    """The Screener page adapter in the ``ingest_vendor`` shape (it reads no record)."""
    del record
    return vendor_screener.extract_screener_page(body, **options)
