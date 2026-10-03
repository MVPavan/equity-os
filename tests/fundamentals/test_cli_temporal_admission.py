"""Offline CLI admission precedes creation and legacy database migration."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml
from tests.fundamentals.test_pipeline_temporal_admission import inputs

from fundamentals.api.cli import main, run_command
from fundamentals.api.cli_parser import build_parser
from fundamentals.ingest.pdf_source import load_pdf
from fundamentals.store.fact_store import FactStore


def cli_fixture(tmp_path: Path, *, future: bool = False) -> tuple[Path, Path, list[str]]:
    args = inputs(tmp_path, future=future)
    config = args["config"]
    data: dict[str, Any] = config.model_dump(mode="json")
    data["raw_dir"] = str(tmp_path)
    data["store_db"] = str(tmp_path / "store" / "facts.sqlite")
    data["xbrl"]["local_path"] = str(tmp_path / "source.xml")
    (tmp_path / "source.xml").write_bytes(args["xbrl_input"].xml_bytes)
    config_path = tmp_path / "config" / "fundamentals.yaml"
    config_path.parent.mkdir()
    config_path.write_text(yaml.safe_dump(data))
    out = tmp_path / "output" / "report.md"
    return (
        config_path,
        Path(data["store_db"]),
        [
            "run",
            "--issuer",
            "GENFILER",
            "--quarter",
            "Q1-FY25",
            "--config",
            str(config_path),
            "--out",
            str(out),
        ],
    )


@pytest.mark.parametrize("legacy", [False, True])
def test_cli_historical_refusal_leaves_database_bytes_and_output_absent(
    tmp_path: Path,
    legacy: bool,
) -> None:
    _, db, argv = cli_fixture(tmp_path)
    before = None
    if legacy:
        db.parent.mkdir()
        with sqlite3.connect(db) as connection:
            connection.execute("CREATE TABLE legacy_marker (value TEXT)")
            connection.execute("INSERT INTO legacy_marker VALUES ('preserve')")
        before = db.read_bytes()
    with pytest.raises(ValueError, match="cutoff|proof"):
        main(argv)
    assert not (tmp_path / "output").exists()
    if legacy:
        assert db.read_bytes() == before
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as connection:
            assert connection.execute("SELECT value FROM legacy_marker").fetchall() == [
                ("preserve",)
            ]
    else:
        assert not db.parent.exists()


def test_local_cli_uses_actual_time_and_old_namespace_defaults(tmp_path: Path) -> None:
    _, db, argv = cli_fixture(tmp_path, future=True)
    namespace = build_parser().parse_args(argv)
    for key in ("source_admission_manifest", "source_admission_store"):
        if hasattr(namespace, key):
            delattr(namespace, key)
    before = datetime.now(UTC)
    result = run_command(namespace)
    after = datetime.now(UTC)
    assert db.is_file()
    assert all(before <= source.acquired_at <= after for source in result.temporal_evidence.sources)


def native_manifest(tmp_path: Path, config_path: Path) -> tuple[Path, Path]:
    import hashlib

    from fundamentals.api.config import load_config
    from fundamentals.api.source_admission import PipelineSourceRefs, RetainedSourceRef
    from fundamentals.contracts.acquisition_outcome import OutcomeCode, OutcomeRecord
    from fundamentals.contracts.snapshot import (
        BlobRef,
        CaptureRecord,
        RequestIdentity,
        SnapshotRights,
    )
    from fundamentals.store.snapshot_store import SnapshotStore

    config = load_config(config_path)
    root = tmp_path / "retained"
    store = SnapshotStore(root)
    refs = {}
    for purpose, source, body in (
        ("xbrl", config.xbrl.source_id, (tmp_path / "source.xml").read_bytes()),
        ("results_pdf", config.results_pdf.source_id, (tmp_path / "results.pdf").read_bytes()),
        (
            "transcript_pdf",
            config.transcript_pdf.source_id,
            (tmp_path / "transcript.pdf").read_bytes(),
        ),
    ):
        digest = hashlib.sha256(body).hexdigest()
        record = CaptureRecord.make(
            request=RequestIdentity(source_id=source, surface="synthetic", request_key="test"),
            retrieved_at=datetime(2024, 7, 17, tzinfo=UTC),
            http_status=200,
            media_type="application/octet-stream",
            content_encoding=None,
            body=BlobRef(source_id=source, content_sha256=digest, byte_count=len(body)),
            outcome=OutcomeRecord(code=OutcomeCode.OK, native_kind="synthetic", native_value="ok"),
            rights=SnapshotRights(authority_refs=("synthetic-test-only",)),
        )
        store.put_capture(record, body)
        refs[purpose] = RetainedSourceRef(
            source_id=source,
            surface="synthetic",
            request_key="test",
            capture_id=record.capture_id,
            source_sha256=digest,
            record_sha256=record.record_sha256,
        )
    manifest = tmp_path / "refs.json"
    manifest.write_text(PipelineSourceRefs(**refs).model_dump_json())
    return manifest, root


@pytest.mark.parametrize("legacy", [False, True])
def test_public_flags_reach_native_proof_refusal_before_constructor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    legacy: bool,
) -> None:
    import fundamentals.api.cli as cli
    from fundamentals.api.source_admission import SourceAdmissionError

    config_path, db, argv = cli_fixture(tmp_path)
    manifest, root = native_manifest(tmp_path, config_path)
    if legacy:
        db.parent.mkdir()
        with sqlite3.connect(db) as connection:
            connection.execute("CREATE TABLE old_facts (knowledge_time TEXT)")
            connection.execute("INSERT INTO old_facts VALUES ('2024-07-18')")
    before = db.read_bytes() if legacy else None
    constructions = []
    real_store = FactStore

    def observed_store(*a: Any, **kw: Any) -> Any:
        constructions.append(a)
        return real_store(*a, **kw)

    monkeypatch.setattr(cli, "FactStore", observed_store)
    with pytest.raises(SourceAdmissionError, match="completion/first-seen/registration proof"):
        main(
            argv
            + ["--source-admission-manifest", str(manifest), "--source-admission-store", str(root)]
        )
    assert constructions == []
    assert not (tmp_path / "output").exists()
    assert db.read_bytes() == before if legacy else not db.parent.exists()


@pytest.mark.parametrize("purpose", ["xbrl", "results_pdf", "transcript_pdf"])
@pytest.mark.parametrize("legacy", [False, True])
def test_each_ineligible_cli_source_has_no_initialization_side_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    purpose: str,
    legacy: bool,
) -> None:
    import fundamentals.api.cli as cli
    from fundamentals.api.source_admission import SourceAdmissionError

    config_path, db, argv = cli_fixture(tmp_path, future=True)
    if purpose == "xbrl":
        manifest, root = native_manifest(tmp_path, config_path)
        argv += [
            "--source-admission-manifest",
            str(manifest),
            "--source-admission-store",
            str(root),
        ]
    else:
        data = yaml.safe_load(config_path.read_text())
        data[purpose]["sha256"] = "cd" * 32
        config_path.write_text(yaml.safe_dump(data))
    if legacy:
        db.parent.mkdir()
        with sqlite3.connect(db) as conn:
            conn.execute("CREATE TABLE old_facts (knowledge_time TEXT)")
            conn.execute("INSERT INTO old_facts VALUES ('2024-07-18')")
    before = db.read_bytes() if legacy else None
    calls = []
    real_store = FactStore

    def observed(*a: Any, **kw: Any) -> Any:
        calls.append(a)
        return real_store(*a, **kw)

    monkeypatch.setattr(cli, "FactStore", observed)
    with pytest.raises(SourceAdmissionError):
        main(argv)
    assert calls == []
    assert not (tmp_path / "output").exists()
    assert db.read_bytes() == before if legacy else not db.parent.exists()


def test_paired_flags_and_manifest_timestamp_assertions_are_refused(tmp_path: Path) -> None:
    import json

    from fundamentals.api.source_admission import SourceAdmissionError

    config_path, db, argv = cli_fixture(tmp_path)
    manifest, root = native_manifest(tmp_path, config_path)
    with pytest.raises(SourceAdmissionError, match="required together"):
        main(argv + ["--source-admission-manifest", str(manifest)])
    data = json.loads(manifest.read_text())
    data["xbrl"]["first_seen_at"] = "2024-07-17T00:00:00Z"
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        main(
            argv
            + ["--source-admission-manifest", str(manifest), "--source-admission-store", str(root)]
        )
    assert not db.parent.exists()


def test_successful_local_cli_reads_each_original_once_and_only_parses_staged_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import fundamentals.api.pipeline as pipeline

    _, _, argv = cli_fixture(tmp_path, future=True)
    original_read = Path.read_bytes
    original_load = load_pdf
    counts: dict[str, int] = {}
    paths = []

    def read(path: Path) -> bytes:
        if path.parent == tmp_path:
            counts[path.name] = counts.get(path.name, 0) + 1
        return original_read(path)

    def load(**kwargs: Any) -> Any:
        paths.append(kwargs["path"])
        return original_load(**kwargs)

    monkeypatch.setattr(Path, "read_bytes", read)
    monkeypatch.setattr(pipeline, "load_pdf", load)
    # main writes the requested report to an existing directory after admission.
    (tmp_path / "output").mkdir()
    assert main(argv) == 0
    assert counts == {"source.xml": 1, "results.pdf": 1, "transcript.pdf": 1}
    assert len(paths) == 2 and all(path.parent != tmp_path and not path.exists() for path in paths)


@pytest.mark.parametrize(
    "fault", ["missing_body", "partial_body", "failed_outcome", "wrong_record"]
)
def test_native_retained_body_guards_never_certify_historical_metadata(
    tmp_path: Path,
    fault: str,
) -> None:
    import hashlib

    from fundamentals.api.source_admission import (
        NativeSourceEvidenceResolver,
        RetainedSourceRef,
        SourceAdmissionError,
    )
    from fundamentals.contracts.acquisition_outcome import OutcomeCode, OutcomeRecord
    from fundamentals.contracts.snapshot import (
        BlobRef,
        BodyCompleteness,
        BodyReadIssue,
        CaptureRecord,
        RequestIdentity,
        SnapshotRights,
    )
    from fundamentals.store.snapshot_store import SnapshotStore

    body = None if fault == "missing_body" else b"synthetic body"
    blob = (
        None
        if body is None
        else BlobRef(
            source_id="synthetic",
            content_sha256=hashlib.sha256(body).hexdigest(),
            byte_count=len(body),
        )
    )
    partial = fault == "partial_body"
    record = CaptureRecord.make(
        request=RequestIdentity(source_id="synthetic", surface="test", request_key="test"),
        retrieved_at=datetime(2024, 7, 17, tzinfo=UTC),
        http_status=200,
        media_type="application/octet-stream",
        content_encoding=None,
        body=blob,
        outcome=OutcomeRecord(
            code=OutcomeCode.TRANSPORT_ERROR if fault != "wrong_record" else OutcomeCode.OK,
            native_kind="synthetic",
            native_value="test",
        ),
        rights=SnapshotRights(authority_refs=("synthetic-test-only",)),
        schema_version=2,
        body_completeness=BodyCompleteness.PARTIAL
        if partial
        else BodyCompleteness.ABSENT
        if body is None
        else BodyCompleteness.COMPLETE,
        body_read_issue=BodyReadIssue.READ_INTERRUPTED if partial else None,
    )
    root = tmp_path / "retained"
    SnapshotStore(root).put_capture(record, body)
    ref = RetainedSourceRef(
        source_id="synthetic",
        surface="test",
        request_key="test",
        capture_id=record.capture_id,
        source_sha256=hashlib.sha256(body or b"").hexdigest(),
        record_sha256="cd" * 32 if fault == "wrong_record" else record.record_sha256,
    )
    with pytest.raises(SourceAdmissionError):
        NativeSourceEvidenceResolver(root).resolve(ref)


def test_native_retained_parsed_values_survive_replaced_config_originals(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import json
    from decimal import Decimal

    from tests.fundamentals.test_source_intake_cli import forbid_acquisition, intake_fixture

    fixture = intake_fixture(tmp_path, monkeypatch)
    forbid_acquisition(monkeypatch)
    assert main(fixture["register"], intake_context=fixture["context"]) == 0
    # Replacements are valid pathnames, but contain no usable filing or PDF.
    for name in ("source.xml", "results.pdf", "transcript.pdf"):
        (tmp_path / name).write_bytes(b"replaced original")
    (tmp_path / "output").mkdir()
    assert main(fixture["run"], intake_context=fixture["context"]) == 0
    report = json.loads((tmp_path / "report.json").read_bytes())
    revenue = next(
        f for f in report["facts"] if f["concept_qname"].endswith(":RevenueFromOperations")
    )
    assert Decimal(revenue["value"]) == Decimal("1000")
