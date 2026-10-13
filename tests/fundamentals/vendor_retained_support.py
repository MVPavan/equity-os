"""Read-only Screener fixtures and literal source oracles; no acquisition or clock backdating."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import yaml

from fundamentals.contracts.canonical import Basis, Representation, StatementFamily
from fundamentals.contracts.evidence import CaptureReference
from fundamentals.contracts.measurement_key import PeriodInterval
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.evidence.vendor_common import VendorRequest, VendorRetainedBinding

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_ROOT = REPO_ROOT / "data/raw/watchlist"
SOURCE = "screener-subscriber"
PAGE_SURFACE = "SCREENER_FINANCIALS"
PAGE_SCHEMA = "screener-financials-html-v1"
NOW = datetime(2026, 10, 13, 5, 0, tzinfo=UTC)
QUARTER = PeriodInterval.duration(date(2024, 10, 1), date(2024, 12, 31))
# Hand-read from raw #quarters HTML, tr Sales+, Dec 2024. Values in crore.
SALES_ORACLE = {
    "CGPOWER": 2516,
    "ETERNAL": 5405,
    "HFCL": 1012,
    "LAURUSLABS": 1415,
    "MTARTECH": 174,
    "NETWEB": 334,
    "POLYCAB": 5226,
    "SONACOMS": 868,
    "THERMAX": 2529,
    "TITAN": 17740,
}


def identifiers(symbol: str) -> dict[str, Any]:
    data = yaml.safe_load((REPO_ROOT / "config/watchlist.yaml").read_text())
    return next(
        stock["identifiers"]
        for stock in data["stocks"]
        if stock["identifiers"]["nse_symbol"] == symbol
    )


def retained_page(symbol: str = "THERMAX") -> tuple[VendorRequest, CaptureReference, bytes]:
    """A test-only registered reference; its time is explicitly synthetic, never evidence."""
    basis = Basis.STANDALONE if symbol == "NETWEB" else Basis.CONSOLIDATED
    relative = (
        Path("screener-financials")
        / symbol
        / basis.value.lower()
        / "screener_financials_page.raw.html"
    )
    body = (RAW_ROOT / relative).read_bytes()
    digest = hashlib.sha256(body).hexdigest()
    request = VendorRequest(
        source_id=SOURCE,
        surface=PAGE_SURFACE,
        schema_identity=PAGE_SCHEMA,
        entity_id=1,
        period=QUARTER,
        basis=basis,
        framework=AccountingFramework.IND_AS,
        statement_family=StatementFamily.PL,
        representation=Representation.HTML,
        retained=VendorRetainedBinding(relative_path=relative, expected_sha256=digest),
    )
    capture = CaptureReference(
        capture_ref_id=1,
        source_id=SOURCE,
        surface=PAGE_SURFACE,
        request_key=request.identity_sha256(),
        capture_id="test-screener-page",
        blob_sha256=digest,
        record_sha256="1" * 64,
        registered_at=NOW,
        first_seen_at=NOW,
    )
    return request, capture, body


def retained_schedule(
    symbol: str, section: str, parent: str
) -> tuple[VendorRequest, CaptureReference, bytes]:
    page_request, _, _ = retained_page(symbol)
    name = parent.lower().replace(" ", "-")
    relative = (
        Path("screener-financials")
        / symbol
        / page_request.basis.value.lower()
        / "schedules"
        / f"{section}__{name}.raw.json"
    )
    body = (RAW_ROOT / relative).read_bytes()
    digest = hashlib.sha256(body).hexdigest()
    family = (
        StatementFamily.BALANCE_SHEET
        if section == "balance-sheet"
        else StatementFamily.CASH_FLOW
        if section == "cash-flow"
        else StatementFamily.PL
    )
    request = page_request.model_copy(
        update={
            "surface": "SCREENER_SCHEDULE",
            "schema_identity": "screener-financials-schedule-v1",
            "representation": Representation.JSON,
            "statement_family": family,
            "retained": VendorRetainedBinding(relative_path=relative, expected_sha256=digest),
        }
    )
    capture = CaptureReference(
        capture_ref_id=2,
        source_id=SOURCE,
        surface=request.surface,
        request_key=request.identity_sha256(),
        capture_id="test-screener-schedule",
        blob_sha256=digest,
        record_sha256="2" * 64,
        registered_at=NOW,
        first_seen_at=NOW,
    )
    return request, capture, body


def marked_body(
    request: VendorRequest, capture: CaptureReference, body: bytes
) -> tuple[VendorRequest, CaptureReference]:
    """Explicit test reinterpretation, marked by synthetic capture identity and new content pin."""
    assert request.retained is not None
    digest = hashlib.sha256(body).hexdigest()
    request = request.model_copy(
        update={"retained": request.retained.model_copy(update={"expected_sha256": digest})}
    )
    return request, capture.model_copy(
        update={"capture_id": "marked-screener-body", "blob_sha256": digest}
    )


def draft_config(tmp_path: Path) -> tuple[Any, Any, Any]:
    """Task-isolated draft publication for actual loaders; never publishes the shared v2 index."""
    import copy
    import shutil

    from fundamentals.canon.dictionary import load_dictionary
    from fundamentals.evidence.mapping import load_mapping_set, load_normalisation_policy

    dictionary_root = tmp_path / "dictionary"
    dictionary_dir = dictionary_root / "screener-draft"
    shutil.copytree(REPO_ROOT / "config/dictionary/v1", dictionary_dir)
    metadata_path = dictionary_dir / "metadata.yaml"
    metadata = yaml.safe_load(metadata_path.read_text())
    metadata.update(version="screener-draft", formula_set_version="screener-draft")
    metadata_path.write_text(yaml.safe_dump(metadata))
    path = dictionary_dir / "derived.yaml"
    data = yaml.safe_load(path.read_text())
    row = copy.deepcopy(next(r for r in data["rows"] if r["canonical_id"] == "pbdt_vendor"))
    row["canonical_id"] = "other_income_incl_exceptional"
    row["meaning"] = "Approved spec bridge: other income plus exceptional items before tax."
    row["formula"].update(
        formula_id="other_income_incl_exceptional",
        operands=[
            {"name": "other_income", "canonical_id": "other_income", "temporal_role": "DURATION"},
            {
                "name": "exceptional",
                "canonical_id": "exceptional_items_before_tax",
                "temporal_role": "DURATION",
            },
        ],
        expression={
            "op": "ADD",
            "args": [
                {"op": "OPERAND", "operand": "other_income"},
                {"op": "OPERAND", "operand": "exceptional"},
            ],
        },
        evidence="Approved data specification §2 known traps; source-independent bridge.",
    )
    data["rows"].append(row)
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    dictionary = load_dictionary(dictionary_root, "screener-draft")
    mapping_root = tmp_path / "mappings"
    mapping_root.mkdir()
    shutil.copyfile(
        REPO_ROOT / "config/mappings/screener/v2/financials.yaml", mapping_root / "financials.yaml"
    )
    shutil.copyfile(
        REPO_ROOT / "config/mappings/screener/v2/constructions.yaml",
        mapping_root / "constructions.yaml",
    )
    (mapping_root / "screener-draft.yaml").write_text(
        yaml.safe_dump(
            {
                "version": "screener-draft",
                "normalisation_policy_version": "v1",
                "entry_files": ["financials.yaml"],
                "construction_files": ["constructions.yaml"],
            }
        )
    )
    mappings = load_mapping_set(mapping_root, "screener-draft", dictionary=dictionary)
    policy = load_normalisation_policy(REPO_ROOT / "config/normalisation_policy/v1.yaml")
    return dictionary, mappings, policy


def stage_registered(request: VendorRequest, repository: Any, store: Any) -> CaptureReference:
    """Real local snapshot registration, using the database clock and actual retained bytes."""
    from fundamentals.contracts.snapshot import SnapshotRights
    from fundamentals.store.capture_local import capture_local_original
    from fundamentals.store.snapshot_store import DirectoryAnchor

    assert request.retained is not None
    record = capture_local_original(
        store,
        input_anchor=DirectoryAnchor(RAW_ROOT),
        source_id=request.source_id,
        surface=request.surface,
        request_key=request.identity_sha256(),
        expected_sha256=request.retained.expected_sha256,
        media_type="text/html"
        if request.representation is Representation.HTML
        else "application/json",
        rights=SnapshotRights(authority_refs=("A05-DECISION-005; private test registration",)),
        path=request.retained.relative_path,
        clock=repository.store_clock,
    )
    return repository.put_capture_ref(
        CaptureReference(
            capture_ref_id=None,
            source_id=record.request.source_id,
            surface=record.request.surface,
            request_key=record.request.request_key,
            capture_id=record.capture_id,
            blob_sha256=record.body.content_sha256,
            record_sha256=record.record_sha256,
            registered_at=record.retrieved_at,
            first_seen_at=record.retrieved_at,
        )
    )
