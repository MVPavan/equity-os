"""Closed vendor producer mechanics over marked synthetic source bodies and publications.

These are characterization tests for the new producer API, not a claimed pre-existing RED.
The permanent existing-API behavioral RED lives in test_compare_vendor_runs.py.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import yaml
from screener_financials_support import _watchlist
from test_vendor_config_publication import _draft_root, _publish_synthetic

from fundamentals.compare.run_config import ConfigVersions, LoadedConfig, load_run_config
from fundamentals.compare.run_models import VendorSurfaceRequest
from fundamentals.compare.vendor_inputs import (
    compose_vendor_generation,
)
from fundamentals.compare.vendor_request import (
    ScreenerComposerContext,
    logical_scope_sha256,
)
from fundamentals.contracts.canonical import Basis, Representation, StatementFamily
from fundamentals.contracts.evidence import CaptureReference
from fundamentals.contracts.measurement_key import PeriodInterval
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.evidence.member_identity import IssuerIdentifiers
from fundamentals.evidence.repository import EvidenceInputRecord, SettingsRecord
from fundamentals.evidence.vendor_common import VendorRequest, VendorRetainedBinding
from fundamentals.evidence.vendor_screener import ScreenerIssuerBinding
from fundamentals.ingest.screener_financials_models import Section
from fundamentals.ingest.screener_session_models import BasisTopology
from fundamentals.pg.identity_seed import (
    CITED_FIELDS,
    EvidenceInputKind,
    IssuerIdentityInput,
    SettingKey,
)
from fundamentals.store.snapshot_store import DirectoryAnchor

SOURCE = "screener-subscriber"
SURFACE = "SCREENER_FINANCIALS"
SCHEMA = "screener-financials-html-v1"
QUARTER = PeriodInterval.duration(date(2025, 7, 1), date(2025, 9, 30))
YEAR = PeriodInterval.duration(date(2025, 4, 1), date(2026, 3, 31))
NOW = datetime(2026, 10, 13, 7, 0, tzinfo=UTC)
TABLES = ("capture_refs", "occurrences", "interpretations", "acquisition_attempts", "runs")


def fixture_identity() -> tuple[IssuerIdentityInput, bytes]:
    document = {
        "entity_key": "FIXTURECO",
        "display_name": "Synthetic fixture company",
        "isin": "INEFIXTURE001",
        "share_class": "EQUITY",
        "nse_symbol": "FIXTURECO",
        "bse_scrip": "500999",
        "basis_status": "CONSOLIDATED_AND_STANDALONE",
        "fiscal_year_end_month": 3,
        "citations": [
            {"field": field, "capture_sha256": "a" * 64, "native_field": field}
            for field in sorted(CITED_FIELDS)
        ],
    }
    body = yaml.safe_dump(document, sort_keys=True).encode()
    return IssuerIdentityInput.model_validate(
        {**document, "content_sha256": hashlib.sha256(body).hexdigest()}
    ), body


class RecordingRepository:
    """Read-only protocol fixture: every producer write is a test failure."""

    def __init__(self) -> None:
        self.capture: CaptureReference | None = None
        self.captures: dict[int, CaptureReference] = {}
        self.extra_evidence: tuple[EvidenceInputRecord, ...] = ()
        self.setting = SettingsRecord(
            id=1,
            entity_id=1,
            setting_key=SettingKey.FISCAL_YEAR_END_MONTH,
            value_text="3",
            evidence_input_id=1,
            recorded_at=NOW,
        )
        self.evidence = EvidenceInputRecord(
            id=1,
            kind=EvidenceInputKind.ISSUER_IDENTITY,
            label="FIXTURECO",
            content_sha256=fixture_identity()[0].content_sha256,
            recorded_at=NOW,
        )

    def entity_id(self, entity_key: str) -> int | None:
        return 1 if entity_key == "FIXTURECO" else None

    def list_attempts(self, *args: object) -> tuple[()]:
        return ()

    def store_clock(self) -> datetime:
        return NOW

    def issuer_identifiers(self, entity_id: int) -> IssuerIdentifiers:
        return IssuerIdentifiers(
            entity_id=entity_id,
            isin="INEFIXTURE001",
            nse_symbol="FIXTURECO",
            bse_scrip="500999",
            evidence_input_id=1,
        )

    def settings_as_of(self, *args: object) -> SettingsRecord:
        return self.setting

    def get_settings_records(self, ids: object) -> tuple[SettingsRecord, ...]:
        return (self.setting,)

    def get_evidence_inputs(self, ids: object) -> tuple[EvidenceInputRecord, ...]:
        return (self.evidence, *self.extra_evidence)

    def get_capture_refs(self, ids: list[int]) -> tuple[CaptureReference, ...]:
        captures = dict(self.captures)
        if self.capture is not None:
            captures[self.capture.capture_ref_id or 0] = self.capture
        return tuple(captures[ref] for ref in ids if ref in captures)

    def get_occurrences(self, ids: object) -> tuple[()]:
        return ()

    def list_capture_occurrences(self, *args: object) -> tuple[()]:
        return ()

    def list_capture_interpretations(self, *args: object) -> tuple[()]:
        return ()

    def pin_versions_guarded(self, *args: object, **kwargs: object) -> None:
        raise AssertionError("refused vendor generation reached a write")

    def put_generation(self, *args: object) -> None:
        raise AssertionError("refused vendor generation reached a write")


def fixture(
    tmp_path: Path,
    *,
    repository: Any | None = None,
    entity_id: int = 1,
    section: Section = Section.QUARTERS,
    period: PeriodInterval = QUARTER,
) -> tuple[Path, Path, LoadedConfig, VendorSurfaceRequest, ScreenerComposerContext, Any]:
    root = _draft_root(tmp_path)
    identity_path = _watchlist(root)
    (root / "identity").mkdir(exist_ok=True)
    (root / "identity/fixtureco.yaml").write_bytes(fixture_identity()[1])
    _publish_synthetic(root)
    config = load_run_config(
        root, ConfigVersions(mapping_set="v2"), allow_synthetic_vendor_config=True
    )
    body = (Path(__file__).parent / "fixtures/synthetic_screener_financials.html").read_bytes()
    # Marked synthetic fixture: this independent listing assertion is deliberately added.
    body = body.replace(
        b"</body>", b'<a href="https://www.bseindia.com/stock-share-price/500999">BSE</a></body>'
    )
    inputs = tmp_path / "marked-synthetic-inputs"
    inputs.mkdir()
    (inputs / "synthetic.html").write_bytes(body)
    request = VendorRequest(
        source_id=SOURCE,
        surface=SURFACE,
        representation=Representation.HTML,
        schema_identity=SCHEMA,
        entity_id=entity_id,
        period=period,
        basis=Basis.CONSOLIDATED,
        framework=AccountingFramework.IND_AS,
        statement_family=StatementFamily.PL,
        retained=VendorRetainedBinding(
            relative_path=Path("synthetic.html"), expected_sha256=hashlib.sha256(body).hexdigest()
        ),
    )
    context = ScreenerComposerContext(
        binding=ScreenerIssuerBinding(
            symbol="FIXTURECO",
            company_id=991001,
            bse_code="500999",
            topology=BasisTopology(
                consolidated_warehouse_id=992001, standalone_warehouse_id=992002
            ),
            identity_evidence_ref="config/watchlist.yaml",
        ),
        section=section,
        identity_config_sha256=hashlib.sha256(identity_path.read_bytes()).hexdigest(),
    )
    repository = repository or RecordingRepository()
    if isinstance(repository, RecordingRepository):
        capture = CaptureReference(
            capture_ref_id=1,
            source_id=SOURCE,
            surface=SURFACE,
            request_key=request.identity_sha256(),
            capture_id="marked-synthetic-page",
            blob_sha256=hashlib.sha256(body).hexdigest(),
            record_sha256="b" * 64,
            registered_at=NOW,
            first_seen_at=NOW,
        )
        repository.capture = capture
    else:
        registration_time = repository.store_clock()
        capture = repository.put_capture_ref(
            CaptureReference(
                capture_ref_id=None,
                source_id=SOURCE,
                surface=SURFACE,
                request_key=request.identity_sha256(),
                capture_id="marked-synthetic-page",
                blob_sha256=hashlib.sha256(body).hexdigest(),
                record_sha256="b" * 64,
                registered_at=registration_time,
                first_seen_at=registration_time,
            )
        )
    assert config.vendor_config is not None
    pin = next(p for p in config.vendor_config.extractor_pins if p.surface == SURFACE)
    declaration = VendorSurfaceRequest(
        **request.model_dump(mode="python"),
        capture_ref_id=capture.capture_ref_id,
        composer_context=context,
        expected_logical_scope_sha256=logical_scope_sha256(
            request, extractor_pin=pin, composer_context=context
        ),
    )
    return root, inputs, config, declaration, context, repository


def arguments(
    case: tuple[Path, Path, LoadedConfig, VendorSurfaceRequest, ScreenerComposerContext, Any],
) -> dict[str, Any]:
    root, inputs, config, declaration, context, repository = case
    return {
        "declaration": declaration,
        "loaded_config": config,
        "config_root": root,
        "input_anchor": DirectoryAnchor(inputs),
        "composer_context": context,
        "repository": repository,
    }


def schedule_fixture(tmp_path: Path) -> tuple[Any, ...]:
    case = fixture(tmp_path)
    root, inputs, config, page_declaration, page_context, repository = case
    page_generation = compose_vendor_generation(**arguments(case))
    page_request = page_generation.request
    body = (
        Path(__file__).parent / "fixtures/screener_schedules/quarters__other-income.json"
    ).read_bytes()
    (inputs / "synthetic-schedule.json").write_bytes(body)
    request = page_request.model_copy(
        update={
            "surface": "SCREENER_SCHEDULE",
            "schema_identity": "screener-financials-schedule-v1",
            "representation": Representation.JSON,
            "retained": VendorRetainedBinding(
                relative_path=Path("synthetic-schedule.json"),
                expected_sha256=hashlib.sha256(body).hexdigest(),
            ),
        }
    )
    capture = CaptureReference(
        capture_ref_id=2,
        source_id=SOURCE,
        surface=request.surface,
        request_key=request.identity_sha256(),
        capture_id="marked-synthetic-schedule",
        blob_sha256=hashlib.sha256(body).hexdigest(),
        record_sha256="c" * 64,
        registered_at=NOW,
        first_seen_at=NOW,
    )
    repository.captures[2] = capture
    context = page_context.model_copy(
        update={
            "parent": "Other Income",
            "supporting_page_request": page_request,
            "supporting_page_capture_ref_id": page_declaration.capture_ref_id,
        }
    )
    assert config.vendor_config is not None
    pin = next(row for row in config.vendor_config.extractor_pins if row.surface == request.surface)
    declaration = VendorSurfaceRequest(
        **request.model_dump(mode="python"),
        capture_ref_id=2,
        composer_context=context,
        expected_logical_scope_sha256=logical_scope_sha256(
            request, extractor_pin=pin, composer_context=context
        ),
    )
    return root, inputs, config, declaration, context, repository
