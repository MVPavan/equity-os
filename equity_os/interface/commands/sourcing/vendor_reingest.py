"""Re-ingest one entity-period's retained Screener and Tijori financials captures (VENDOR-1 §6.1).

Each capture an earlier extraction attempt of that entity, period end and basis cites is
ingested again under the current extractor and the named mapping set, with the issuer binding
onboarding built (``onboard_cli._vendor_adapters``): read from the stored identifiers and
settings, the capture's own bytes and, for Screener, the identity evidence its earlier
occurrences cite. Earlier rows are never changed; new ones are added beside them.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date
from functools import partial
from pathlib import Path
from typing import Any

from psycopg_pool import ConnectionPool

from equity_os.companies.identity.identity_seed import SettingKey
from equity_os.contracts.measurement.canonical import Basis, Representation
from equity_os.contracts.measurement.evidence import AttemptStage, CaptureReference
from equity_os.contracts.measurement.observation import AccountingFramework
from equity_os.contracts.sourcing.source_catalog import SCREENER_PAGE, TIJORI_PAGE
from equity_os.contracts.verification.config_versions import ConfigVersions
from equity_os.extraction.packages.member_identity import IssuerIdentifiers
from equity_os.extraction.surfaces.vendor_ingest import (
    VendorExtraction,
    VendorIngestReport,
    VendorIngestRequest,
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
from equity_os.verification.comparison.run_config import load_run_config

_NO_ENTITY = "no reporting entity {key!r}"
_NO_FISCAL_MONTH = "entity {key!r} has no fiscal-year-end month for {period}"
_IDENTITY_REF = "identity_evidence_ref"
_TIJORI_COMPANY_ID = "company_id"
Adapter = tuple[Any, str]  # the ``ingest_vendor`` adapter and its extractor version


def reingest(
    pool: ConnectionPool,
    store: SnapshotStore,
    config_root: Path,
    versions: ConfigVersions,
    *,
    entity: str,
    period_end: date,
    basis: Basis,
) -> tuple[VendorIngestReport, ...]:
    """Ingest every retained financials capture of the entity-period again (module docstring)."""
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
        for attempt in repository.list_attempts(entity_id, period_end)
        if attempt.capture is not None
        and attempt.stage is AttemptStage.EXTRACTION
        and attempt.basis is basis
        and (attempt.source_id, attempt.surface) in (SCREENER_PAGE, TIJORI_PAGE)
    }
    reports = []
    for _, capture in sorted(captures.items()):
        identity = (capture.source_id, capture.surface, capture.request_key, capture.capture_id)
        _, body = store.read_capture_verified(*identity)
        adapters = _adapters(repository, capture, body, ids, basis, month, config_root)
        for extract, version in adapters:
            reports.append(
                ingest_vendor_retained(
                    VendorIngestRequest(
                        source_id=capture.source_id,
                        surface=capture.surface,
                        request_key=capture.request_key,
                        capture_id=capture.capture_id,
                        representation=Representation.HTML,
                        entity_id=entity_id,
                        period_end=period_end,
                        basis=basis,
                        framework=AccountingFramework.IND_AS,
                    ),
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
