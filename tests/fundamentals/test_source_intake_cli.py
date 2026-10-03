"""Registration-backed public composition using synthetic originals only."""

import hashlib
import json
import sqlite3
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml
from tests.fundamentals.test_cli_temporal_admission import cli_fixture
from tests.fundamentals.test_pipeline_temporal_admission import (
    CUTOFF,
    RUN_TIME,
    inputs,
    synthetic_evidence,
)

from fundamentals.api.cli import main
from fundamentals.api.source_admission import (
    NativeSourceEvidenceResolver,
    PipelineSourceRefs,
    RetainedSourceRef,
    SourceAdmissionError,
    prepare_pipeline_sources,
)
from fundamentals.api.source_intake import ApprovedIntakeBinding, ApprovedIntakeContext
from fundamentals.contracts.acquisition_outcome import OutcomeCode, OutcomeRecord
from fundamentals.contracts.snapshot import (
    BlobRef,
    BodyCompleteness,
    CaptureRecord,
    RequestIdentity,
    SnapshotRights,
)
from fundamentals.contracts.source_registration import SourceRegistrationError, SourceRole
from fundamentals.store.snapshot_store import DirectoryAnchor, SnapshotStore


def test_retained_preparation_consumes_resolver_bytes_without_old_paths(tmp_path: Path) -> None:
    args = inputs(tmp_path)
    config = args["config"]
    evidence = synthetic_evidence(args)
    Path(args["results_pdf_path"]).unlink()
    Path(args["transcript_pdf_path"]).unlink()
    with prepare_pipeline_sources(
        xbrl_bytes=args["xbrl_input"].xml_bytes,
        xbrl_source_id=config.xbrl.source_id,
        xbrl_sha256=args["xbrl_input"].file_sha256,
        results_pdf_path=args["results_pdf_path"],
        results_pdf_sha256=args["results_pdf_sha256"],
        results_source_id=config.results_pdf.source_id,
        transcript_pdf_path=args["transcript_pdf_path"],
        transcript_pdf_sha256=args["transcript_pdf_sha256"],
        transcript_source_id=config.transcript_pdf.source_id,
        cutoff=CUTOFF,
        run_started_at=RUN_TIME,
        **evidence,
    ) as admitted:
        assert admitted.xbrl_bytes == args["xbrl_input"].xml_bytes
        assert admitted._results_path.read_bytes().startswith(b"%PDF")
        assert admitted._transcript_path.read_bytes().startswith(b"%PDF")


INTAKE_TIME = datetime(2026, 1, 2, tzinfo=UTC)
EVALUATION_TIME = INTAKE_TIME + timedelta(hours=1)


def intake_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, cutoff: datetime = INTAKE_TIME
) -> dict[str, Any]:
    import fundamentals.api.cli as cli
    import fundamentals.api.source_admission as admission
    import fundamentals.store.source_intake_store as producer

    config_path, db, argv = cli_fixture(tmp_path)
    data = yaml.safe_load(config_path.read_bytes())
    data["quarter"]["knowledge_cutoff"] = cutoff.isoformat()
    config_path.write_text(yaml.safe_dump(data))
    root = tmp_path / "retained"
    root.mkdir(mode=0o700)
    rights = SnapshotRights(authority_refs=("synthetic-test-only",))
    refs, bindings = {}, []
    store = SnapshotStore(root)
    for role, filename in (
        (SourceRole.XBRL, "source.xml"),
        (SourceRole.RESULTS_PDF, "results.pdf"),
        (SourceRole.TRANSCRIPT_PDF, "transcript.pdf"),
    ):
        source = data[role.value]["source_id"]
        body = (tmp_path / filename).read_bytes()
        digest = hashlib.sha256(body).hexdigest()
        record = CaptureRecord.make(
            request=RequestIdentity(source_id=source, surface="synthetic", request_key="fixture"),
            retrieved_at=datetime(2024, 7, 17, tzinfo=UTC),
            http_status=200,
            media_type="application/octet-stream",
            content_encoding=None,
            body=BlobRef(source_id=source, content_sha256=digest, byte_count=len(body)),
            outcome=OutcomeRecord(code=OutcomeCode.OK, native_kind="synthetic", native_value="ok"),
            rights=rights,
            schema_version=2,
            body_completeness=BodyCompleteness.COMPLETE,
        )
        store.put_capture(record, body)
        refs[role.value] = RetainedSourceRef(
            source_id=source,
            surface="synthetic",
            request_key="fixture",
            capture_id=record.capture_id,
            source_sha256=digest,
            record_sha256=record.record_sha256,
        )
        bindings.append(ApprovedIntakeBinding(role, source, digest, rights))
    context = ApprovedIntakeContext(
        tuple(bindings),
        hashlib.sha256(config_path.read_bytes()).hexdigest(),
        DirectoryAnchor(root),
        DirectoryAnchor(tmp_path),
    )
    manifest = tmp_path / "input-refs.json"
    manifest.write_text(PipelineSourceRefs(**refs).model_dump_json())
    locator = tmp_path / "registered.json"
    monkeypatch.setattr(producer, "_utc_now", lambda: INTAKE_TIME)
    monkeypatch.setattr(admission, "actual_clock", lambda: EVALUATION_TIME)

    class ModuleClock(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> datetime:
            return EVALUATION_TIME

    monkeypatch.setattr(cli, "datetime", ModuleClock)
    register = [
        "register-sources",
        "--config",
        str(config_path),
        "--source-admission-manifest",
        str(manifest),
        "--source-admission-store",
        str(root),
        "--out-manifest",
        str(locator),
    ]
    retained_run = argv + [
        "--source-admission-manifest",
        str(locator),
        "--source-admission-store",
        str(root),
        "--xbrl-mode",
        "live",
        "--out-json",
        str(tmp_path / "report.json"),
    ]
    return dict(
        context=context,
        manifest=manifest,
        locator=locator,
        root=root,
        db=db,
        config=config_path,
        register=register,
        run=retained_run,
        refs=refs,
    )


def forbid_acquisition(monkeypatch: pytest.MonkeyPatch) -> None:
    import fundamentals.api.cli as cli

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("source/credential/acquisition boundary was called")

    monkeypatch.setattr(cli.NseXbrlSource, "fetch_consolidated_quarter", forbidden)
    for name in (
        "_screener_credentials_from_env",
        "_tijori_credentials_from_env",
        "_upstox_credentials_from_env",
    ):
        monkeypatch.setattr(cli, name, forbidden)


@pytest.mark.parametrize("cutoff", [INTAKE_TIME, INTAKE_TIME + timedelta(minutes=1)])
def test_public_main_register_restart_and_parsed_retained_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cutoff: datetime,
) -> None:
    fixture = intake_fixture(tmp_path, monkeypatch, cutoff=cutoff)
    forbid_acquisition(monkeypatch)
    assert main(fixture["register"], intake_context=fixture["context"]) == 0
    assert not fixture["db"].parent.exists()
    refs = json.loads(fixture["locator"].read_bytes())
    assert set(refs) == {"xbrl", "results_pdf", "transcript_pdf"}
    assert all(len(ref) == 6 for ref in refs.values())
    first = NativeSourceEvidenceResolver(
        fixture["root"], approved_intake=fixture["context"]
    ).resolve(fixture["refs"]["xbrl"])
    assert first.registration.registered_at == INTAKE_TIME
    assert first.claimed_retrieved_at == datetime(2024, 7, 17, tzinfo=UTC)
    # A fresh operator reconstruction observes the same directories after restart.
    context = replace(fixture["context"], store_anchor=DirectoryAnchor(fixture["root"]))
    second = NativeSourceEvidenceResolver(fixture["root"], approved_intake=context).resolve(
        fixture["refs"]["xbrl"]
    )
    assert second.registration == first.registration
    for name in ("source.xml", "results.pdf", "transcript.pdf"):
        (tmp_path / name).unlink()
    (tmp_path / "output").mkdir()
    assert main(fixture["run"], intake_context=context) == 0
    report = json.loads((tmp_path / "report.json").read_bytes())
    values = {fact["concept_qname"].split(":")[-1]: fact["value"] for fact in report["facts"]}
    assert Decimal(values["RevenueFromOperations"]) == Decimal("1000")
    assert Decimal(values["ProfitBeforeTax"]) == Decimal("300")
    assert Decimal(values["ProfitLossForPeriod"]) == Decimal("220")
    assert "1,000" in (tmp_path / "output" / "report.md").read_text()


@pytest.mark.parametrize(
    "cutoff", [INTAKE_TIME - timedelta(seconds=1), EVALUATION_TIME + timedelta(seconds=1)]
)
@pytest.mark.parametrize("legacy", [False, True])
def test_refused_retained_cutoff_preserves_database_and_existing_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cutoff: datetime,
    legacy: bool,
) -> None:
    fixture = intake_fixture(tmp_path, monkeypatch, cutoff=cutoff)
    assert main(fixture["register"], intake_context=fixture["context"]) == 0
    if legacy:
        fixture["db"].parent.mkdir()
        with sqlite3.connect(fixture["db"]) as connection:
            connection.execute("CREATE TABLE legacy_marker (value TEXT)")
            connection.execute("INSERT INTO legacy_marker VALUES ('preserve')")
    before = fixture["db"].read_bytes() if legacy else None
    (tmp_path / "output").mkdir()
    report = tmp_path / "output" / "report.md"
    report.write_bytes(b"preserve-report")
    with pytest.raises(SourceAdmissionError, match="cutoff|future"):
        main(fixture["run"], intake_context=fixture["context"])
    assert report.read_bytes() == b"preserve-report"
    assert fixture["db"].read_bytes() == before if legacy else not fixture["db"].parent.exists()
    assert not (tmp_path / "report.json").exists()


@pytest.mark.parametrize("fault", ["absent", "digest", "source", "content", "rights", "store"])
def test_registration_context_mismatch_issues_no_locator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
) -> None:
    fixture = intake_fixture(tmp_path, monkeypatch)
    context = fixture["context"]
    if fault == "absent":
        context = None
    elif fault == "digest":
        context = replace(context, approved_config_sha256="ab" * 32)
    elif fault == "store":
        wrong = tmp_path / "wrong-store"
        wrong.mkdir(mode=0o700)
        context = replace(context, store_anchor=DirectoryAnchor(wrong))
    else:
        binding = context.bindings[0]
        changes = {
            "source": {"source_id": "wrong"},
            "content": {"expected_sha256": "ab" * 32},
            "rights": {"rights": SnapshotRights(authority_refs=("invented",))},
        }[fault]
        context = replace(context, bindings=(replace(binding, **changes), *context.bindings[1:]))
    with pytest.raises((SourceRegistrationError, SourceAdmissionError)):
        main(fixture["register"], intake_context=context)
    assert not fixture["locator"].exists()
    assert not fixture["db"].parent.exists()
    assert not (fixture["root"] / ".source-intake").exists()


def test_unregistered_self_consistent_old_capture_is_not_proof_and_receipt_is_current(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = intake_fixture(tmp_path, monkeypatch)
    resolver = NativeSourceEvidenceResolver(fixture["root"], approved_intake=fixture["context"])
    with pytest.raises(SourceAdmissionError):
        resolver.resolve(fixture["refs"]["xbrl"])
    assert main(fixture["register"], intake_context=fixture["context"]) == 0
    proof = resolver.resolve(fixture["refs"]["xbrl"])
    assert (
        proof.acquired_at == proof.first_seen_at == proof.registration.registered_at == INTAKE_TIME
    )
    with pytest.raises(SourceAdmissionError):
        main(fixture["run"])
    assert not fixture["db"].parent.exists()


@pytest.mark.parametrize(
    "field", ["retrieved_at", "first_seen_at", "registration", "registered_at"]
)
def test_manifest_cannot_import_dates_or_registration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
) -> None:
    fixture = intake_fixture(tmp_path, monkeypatch)
    refs = json.loads(fixture["manifest"].read_bytes())
    refs["xbrl"][field] = "2020-01-01T00:00:00Z"
    fixture["manifest"].write_text(json.dumps(refs))
    with pytest.raises(ValueError):
        main(fixture["register"], intake_context=fixture["context"])
    assert not fixture["locator"].exists()
    assert not (fixture["root"] / ".source-intake").exists()


def test_partial_batch_has_individual_receipt_but_no_complete_locator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = intake_fixture(tmp_path, monkeypatch)
    ref = fixture["refs"]["transcript_pdf"]
    (
        fixture["root"]
        / ref.source_id
        / ref.surface
        / ref.request_key
        / ref.capture_id
        / "record.json"
    ).unlink()
    with pytest.raises(SourceRegistrationError):
        main(fixture["register"], intake_context=fixture["context"])
    assert not fixture["locator"].exists()
    resolver = NativeSourceEvidenceResolver(fixture["root"], approved_intake=fixture["context"])
    assert resolver.resolve(fixture["refs"]["xbrl"]).registration.registered_at == INTAKE_TIME
    with pytest.raises(SourceAdmissionError):
        resolver.resolve(ref)
    assert not fixture["db"].parent.exists()


@pytest.mark.parametrize("collision", ["file", "symlink"])
def test_locator_no_clobber_refuses_existing_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    collision: str,
) -> None:
    fixture = intake_fixture(tmp_path, monkeypatch)
    target = tmp_path / "sentinel"
    target.write_bytes(b"keep")
    if collision == "symlink":
        fixture["locator"].symlink_to(target)
    else:
        fixture["locator"].write_bytes(b"keep")
    with pytest.raises(SourceRegistrationError, match="overwrite"):
        main(fixture["register"], intake_context=fixture["context"])
    assert fixture["locator"].read_bytes() == b"keep"
    assert target.read_bytes() == b"keep"
    assert not (fixture["root"] / ".source-intake").exists()


@pytest.mark.parametrize("role", list(SourceRole))
@pytest.mark.parametrize(
    "field", ["source_id", "surface", "request_key", "capture_id", "source_sha256", "record_sha256"]
)
def test_each_reference_coordinate_is_bound_after_restart(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    role: SourceRole,
    field: str,
) -> None:
    fixture = intake_fixture(tmp_path, monkeypatch)
    assert main(fixture["register"], intake_context=fixture["context"]) == 0
    data = json.loads(fixture["locator"].read_bytes())
    data[role.value][field] = (
        "ab" * 32
        if field.endswith("sha256")
        else "20200101T000000.000000Z-abcdef123456"
        if field == "capture_id"
        else "wrong"
    )
    fixture["locator"].write_text(json.dumps(data))
    with pytest.raises(SourceAdmissionError):
        main(fixture["run"], intake_context=fixture["context"])
    assert not fixture["db"].parent.exists()
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("fault", ["source", "content", "rights", "store"])
def test_native_restart_checks_current_context_against_existing_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
) -> None:
    fixture = intake_fixture(tmp_path, monkeypatch)
    assert main(fixture["register"], intake_context=fixture["context"]) == 0
    context = fixture["context"]
    if fault == "store":
        wrong = tmp_path / "wrong"
        wrong.mkdir(mode=0o700)
        context = replace(context, store_anchor=DirectoryAnchor(wrong))
    else:
        changed = {
            "source": {"source_id": "wrong"},
            "content": {"expected_sha256": "ab" * 32},
            "rights": {"rights": SnapshotRights(authority_refs=("forged",))},
        }[fault]
        context = replace(
            context, bindings=(replace(context.bindings[0], **changed), *context.bindings[1:])
        )
    with pytest.raises(SourceAdmissionError):
        main(fixture["run"], intake_context=context)
    assert not fixture["db"].parent.exists()
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("part", ["record", "body", "receipt", "installed"])
def test_native_tamper_refuses_before_database_and_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    part: str,
) -> None:
    fixture = intake_fixture(tmp_path, monkeypatch)
    assert main(fixture["register"], intake_context=fixture["context"]) == 0
    ref = fixture["refs"]["transcript_pdf"]
    resolver = NativeSourceEvidenceResolver(fixture["root"], approved_intake=fixture["context"])
    proof = resolver.resolve(ref)
    if part in ("receipt", "installed"):
        path = (
            fixture["root"]
            / ".source-intake"
            / proof.registration.binding_id
            / ("registration.json" if part == "receipt" else "installed.json")
        )
    else:
        directory = fixture["root"] / ref.source_id / ref.surface / ref.request_key / ref.capture_id
        path = directory / "record.json" if part == "record" else next(directory.glob("body.*"))
    path.write_bytes(b"tampered")
    with pytest.raises(SourceAdmissionError):
        main(fixture["run"], intake_context=fixture["context"])
    assert not fixture["db"].parent.exists()
    assert not (tmp_path / "output").exists()


def test_interrupted_batch_retry_reuses_individual_receipt_times(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import fundamentals.store.source_intake_store as producer

    fixture = intake_fixture(tmp_path, monkeypatch)
    ref = fixture["refs"]["transcript_pdf"]
    path = (
        fixture["root"]
        / ref.source_id
        / ref.surface
        / ref.request_key
        / ref.capture_id
        / "record.json"
    )
    original = path.read_bytes()
    path.unlink()
    with pytest.raises(SourceRegistrationError):
        main(fixture["register"], intake_context=fixture["context"])
    resolver = NativeSourceEvidenceResolver(fixture["root"], approved_intake=fixture["context"])
    before = resolver.resolve(fixture["refs"]["xbrl"]).registration
    path.write_bytes(original)
    monkeypatch.setattr(producer, "_utc_now", lambda: INTAKE_TIME + timedelta(minutes=1))
    assert main(fixture["register"], intake_context=fixture["context"]) == 0
    assert resolver.resolve(fixture["refs"]["xbrl"]).registration == before
    assert resolver.resolve(ref).registration.registered_at == INTAKE_TIME + timedelta(minutes=1)


def test_native_future_receipt_refuses_current_ceiling(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import fundamentals.store.source_intake_store as producer

    fixture = intake_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(producer, "_utc_now", lambda: EVALUATION_TIME + timedelta(days=1))
    assert main(fixture["register"], intake_context=fixture["context"]) == 0
    monkeypatch.setattr(producer, "_utc_now", lambda: EVALUATION_TIME)
    with pytest.raises(SourceAdmissionError, match="future"):
        main(fixture["run"], intake_context=fixture["context"])
    assert not fixture["db"].parent.exists()


@pytest.mark.parametrize(
    "flag", ["--retrieved-at", "--registered-at", "--rights", "--intake-context"]
)
def test_argv_cannot_supply_authority_or_clock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    flag: str,
) -> None:
    fixture = intake_fixture(tmp_path, monkeypatch)
    with pytest.raises(SystemExit):
        main(fixture["register"] + [flag, "forged"])
    assert not fixture["locator"].exists()
    assert not (fixture["root"] / ".source-intake").exists()


def test_registration_bound_is_required_even_when_completion_and_observation_are_earlier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import fundamentals.store.source_intake_store as producer

    fixture = intake_fixture(tmp_path, monkeypatch, cutoff=INTAKE_TIME + timedelta(seconds=1))
    later = INTAKE_TIME + timedelta(seconds=10)
    samples = iter([INTAKE_TIME, INTAKE_TIME, later, later] * 3)
    monkeypatch.setattr(producer, "_utc_now", lambda: next(samples))
    assert main(fixture["register"], intake_context=fixture["context"]) == 0
    monkeypatch.setattr(producer, "_utc_now", lambda: EVALUATION_TIME)
    proof = NativeSourceEvidenceResolver(
        fixture["root"], approved_intake=fixture["context"]
    ).resolve(fixture["refs"]["xbrl"])
    assert proof.registration.capture_completed_at == INTAKE_TIME
    assert proof.registration.first_observed_at == INTAKE_TIME
    assert proof.registration.registered_at == later
    with pytest.raises(SourceAdmissionError, match="registration.*cutoff"):
        main(fixture["run"], intake_context=fixture["context"])
    assert not fixture["db"].parent.exists()


@pytest.mark.parametrize("restore", [False, True])
def test_retained_private_pdf_staging_survives_original_swap_during_parse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    restore: bool,
) -> None:
    import pymupdf

    fixture = intake_fixture(tmp_path, monkeypatch)
    forbid_acquisition(monkeypatch)
    assert main(fixture["register"], intake_context=fixture["context"]) == 0
    (tmp_path / "output").mkdir()
    original_open = pymupdf.open
    seen: list[Path] = []

    def open_pdf(*args: Any, **kwargs: Any) -> Any:
        path = Path(args[0])
        seen.append(path)
        held = tmp_path / "results.pdf"
        before = held.read_bytes()
        held.write_bytes(b"replacement bytes during parser call")
        document = original_open(*args, **kwargs)
        if restore:
            held.write_bytes(before)
        return document

    # This is the external PDF engine boundary. Production admission is unpatched.
    monkeypatch.setattr(pymupdf, "open", open_pdf)
    assert main(fixture["run"], intake_context=fixture["context"]) == 0
    assert len(seen) == 2 and all(path.parent != tmp_path and not path.exists() for path in seen)
    report = json.loads((tmp_path / "report.json").read_bytes())
    revenue = next(
        f for f in report["facts"] if f["concept_qname"].endswith(":RevenueFromOperations")
    )
    assert Decimal(revenue["value"]) == Decimal("1000")


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("change", ["cutoff", "parser", "identity", "database"])
def test_retained_replay_refuses_changed_approved_config_before_any_consumption(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, existing: bool, change: str
) -> None:
    import pymupdf

    fixture = intake_fixture(tmp_path, monkeypatch)
    forbid_acquisition(monkeypatch)
    assert main(fixture["register"], intake_context=fixture["context"]) == 0
    data = yaml.safe_load(fixture["config"].read_bytes())
    if change == "cutoff":
        data["quarter"]["knowledge_cutoff"] = (INTAKE_TIME + timedelta(minutes=1)).isoformat()
    elif change == "parser":
        data["pdf_parse"]["scope_marker"] = "Standalone"
    elif change == "identity":
        data["issuer"]["entity_scheme"] = "changed-identity-scheme"
    else:
        data["store_db"] = str(tmp_path / "redirected" / "facts.sqlite")
    fixture["config"].write_text(yaml.safe_dump(data))
    assert all(
        data[role.value]["source_id"] == fixture["refs"][role.value].source_id
        for role in SourceRole
    )
    assert all(
        data[role.value]["sha256"] == fixture["refs"][role.value].source_sha256
        for role in (SourceRole.RESULTS_PDF, SourceRole.TRANSCRIPT_PDF)
    )
    if existing:
        fixture["db"].parent.mkdir()
        with sqlite3.connect(fixture["db"]) as connection:
            connection.execute("CREATE TABLE legacy_marker (value TEXT)")
            connection.execute("INSERT INTO legacy_marker VALUES ('preserve')")
        (tmp_path / "output").mkdir()
        (tmp_path / "output" / "report.md").write_bytes(b"keep markdown")
        (tmp_path / "report.json").write_bytes(b"keep json")
    artifacts = [fixture["db"], tmp_path / "output" / "report.md", tmp_path / "report.json"]
    before = {path: path.read_bytes() if path.exists() else None for path in artifacts}
    consumed: list[str] = []

    def observe(name: str, real: Any) -> Any:
        def call(*args: Any, **kwargs: Any) -> Any:
            consumed.append(name)
            return real(*args, **kwargs)

        return call

    monkeypatch.setattr(yaml, "safe_load", observe("yaml", yaml.safe_load))
    monkeypatch.setattr(pymupdf, "open", observe("source parser", pymupdf.open))
    monkeypatch.setattr(sqlite3, "connect", observe("database", sqlite3.connect))
    with pytest.raises(SourceAdmissionError, match="configuration.*digest"):
        main(fixture["run"], intake_context=fixture["context"])
    assert consumed == []
    assert {path: path.read_bytes() if path.exists() else None for path in artifacts} == before
    assert not (tmp_path / "redirected").exists()
    if not existing:
        assert not fixture["db"].parent.exists()
        assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("boundary", ["read", "digest", "parse"])
@pytest.mark.parametrize("restore", [False, True])
@pytest.mark.parametrize("command", ["run", "register"])
def test_approved_configuration_substitution_refuses_across_read_and_parse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, boundary: str, restore: bool, command: str
) -> None:
    import os

    fixture = intake_fixture(tmp_path, monkeypatch)
    assert main(fixture["register"], intake_context=fixture["context"]) == 0
    path = fixture["config"]
    original = path.read_bytes()
    identity = path.stat().st_ino
    replacement = yaml.safe_load(original)
    replacement["store_db"] = str(tmp_path / "redirected" / "facts.sqlite")
    substituted = yaml.safe_dump(replacement).encode()
    fired = False

    def swap() -> None:
        nonlocal fired
        fired = True
        held = path.with_name("held.yaml")
        path.rename(held)
        path.write_bytes(substituted)
        if restore:
            path.unlink()
            held.rename(path)

    if boundary == "read":
        real_read = os.read

        def read(fd: int, size: int) -> bytes:
            payload = real_read(fd, size)
            if not fired and os.fstat(fd).st_ino == identity:
                swap()
            return payload

        monkeypatch.setattr(os, "read", read)
    elif boundary == "digest":
        real_hash = hashlib.sha256

        def digest(payload: Any = b"", **kwargs: Any) -> Any:
            result = real_hash(payload, **kwargs)
            if not fired and payload == original:
                swap()
            return result

        monkeypatch.setattr(hashlib, "sha256", digest)
    else:
        real_load = yaml.safe_load

        def parse(payload: Any) -> Any:
            assert payload == original  # The parser must consume the verified buffer.
            result = real_load(payload)
            swap()
            return result

        monkeypatch.setattr(yaml, "safe_load", parse)
    argv = fixture[command].copy()
    locator = tmp_path / "retry-locator.json"
    if command == "register":
        argv[argv.index("--out-manifest") + 1] = str(locator)
    with pytest.raises((SourceAdmissionError, SourceRegistrationError), match="configuration"):
        main(argv, intake_context=fixture["context"])
    assert fired
    assert not locator.exists()
    assert not fixture["db"].parent.exists()
    assert not (tmp_path / "redirected").exists()
    assert not (tmp_path / "output").exists()
    assert not (tmp_path / "report.json").exists()


@pytest.mark.parametrize("ancestor", [False, True])
def test_retained_configuration_symlinks_cannot_bypass_nofollow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ancestor: bool
) -> None:
    fixture = intake_fixture(tmp_path, monkeypatch)
    assert main(fixture["register"], intake_context=fixture["context"]) == 0
    if ancestor:
        alias = tmp_path / "config-alias"
        alias.symlink_to(fixture["config"].parent, target_is_directory=True)
        config_path = alias / fixture["config"].name
    else:
        config_path = fixture["config"].with_name("config-alias.yaml")
        config_path.symlink_to(fixture["config"])
    argv = fixture["run"].copy()
    argv[argv.index("--config") + 1] = str(config_path)
    with pytest.raises(SourceAdmissionError, match="configuration"):
        main(argv, intake_context=fixture["context"])
    assert not fixture["db"].parent.exists()
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("existing", [False, True], ids=["absent", "existing"])
@pytest.mark.parametrize("boundary", ["read", "digest", "parse"])
@pytest.mark.parametrize("restore", [False, True], ids=["A-B", "A-B-A"])
@pytest.mark.parametrize("command", ["run", "register"])
def test_approved_configuration_ancestor_directory_substitution_refuses(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    existing: bool,
    boundary: str,
    restore: bool,
    command: str,
) -> None:
    import os
    import time

    import pymupdf

    fixture = intake_fixture(tmp_path, monkeypatch)
    forbid_acquisition(monkeypatch)
    # All fixture publication precedes the guarded operation. The renamed A is
    # above the config's direct parent, and contains no store or output artifacts.
    ancestor = tmp_path / "A"
    nested = ancestor / "nested"
    nested.mkdir(parents=True)
    path = nested / fixture["config"].name
    fixture["config"].rename(path)
    original = path.read_bytes()
    before_file = path.stat()
    before_ancestor = ancestor.stat()
    for argv in (fixture["register"], fixture["run"]):
        argv[argv.index("--config") + 1] = str(path)
    if command == "run":
        assert main(fixture["register"], intake_context=fixture["context"]) == 0
    locator = tmp_path / "retry-locator.json"
    argv = fixture[command].copy()
    if command == "register":
        argv[argv.index("--out-manifest") + 1] = str(locator)
    (tmp_path / "output").mkdir()
    if existing:
        fixture["db"].parent.mkdir()
        with sqlite3.connect(fixture["db"]) as connection:
            connection.execute("CREATE TABLE legacy_marker (value TEXT)")
            connection.execute("INSERT INTO legacy_marker VALUES ('preserve')")
        (tmp_path / "output" / "report.md").write_bytes(b"keep markdown")
        (tmp_path / "report.json").write_bytes(b"keep json")
    artifacts = [fixture["db"], tmp_path / "output" / "report.md", tmp_path / "report.json"]
    before = {p: p.read_bytes() if p.exists() else None for p in artifacts}
    ledger = fixture["root"] / ".source-intake"
    before_ledger = {p.relative_to(ledger): p.read_bytes() for p in ledger.rglob("*.json")}
    # Establish a later filesystem timestamp tick outside the guarded operation;
    # rapid renames can otherwise share the setup ctime on this filesystem.
    probe = tmp_path / "timestamp-probe"
    probe.touch()
    deadline = time.monotonic() + 1
    while probe.stat().st_ctime_ns <= before_ancestor.st_ctime_ns:
        assert time.monotonic() < deadline, "filesystem ctime tick did not advance"
        os.utime(probe, None)
    probe.unlink()
    consumed: list[str] = []
    fired = False

    def swap() -> None:
        nonlocal fired
        fired = True
        held = tmp_path / "B"
        ancestor.rename(held)
        ancestor.mkdir()
        # No descendant config is modified, recreated, or renamed.
        held_path = held / "nested" / path.name
        assert held_path.read_bytes() == original
        assert (held_path.stat().st_dev, held_path.stat().st_ino) == (
            before_file.st_dev,
            before_file.st_ino,
        )
        assert held_path.stat().st_ctime_ns == before_file.st_ctime_ns
        assert held_path.stat().st_mtime_ns == before_file.st_mtime_ns
        if restore:
            ancestor.rmdir()
            held.rename(ancestor)
            assert ancestor.stat().st_ino == before_ancestor.st_ino
            assert ancestor.stat().st_ctime_ns != before_ancestor.st_ctime_ns
            assert (path.stat().st_dev, path.stat().st_ino) == (
                before_file.st_dev,
                before_file.st_ino,
            )
            assert path.stat().st_ctime_ns == before_file.st_ctime_ns
            assert path.stat().st_mtime_ns == before_file.st_mtime_ns

    if boundary == "read":
        real_read = os.read

        def read(fd: int, size: int) -> bytes:
            payload = real_read(fd, size)
            if not fired and os.fstat(fd).st_ino == before_file.st_ino:
                swap()
            return payload

        monkeypatch.setattr(os, "read", read)
    elif boundary == "digest":
        real_hash = hashlib.sha256

        def digest(payload: Any = b"", **kwargs: Any) -> Any:
            result = real_hash(payload, **kwargs)
            if not fired and payload == original:
                swap()
            return result

        monkeypatch.setattr(hashlib, "sha256", digest)
    else:
        real_load = yaml.safe_load

        def parse(payload: Any) -> Any:
            assert payload == original  # Real YAML consumes the approved same buffer.
            result = real_load(payload)
            swap()
            return result

        monkeypatch.setattr(yaml, "safe_load", parse)

    def observe(name: str, real: Any) -> Any:
        def call(*args: Any, **kwargs: Any) -> Any:
            consumed.append(name)
            return real(*args, **kwargs)

        return call

    monkeypatch.setattr(pymupdf, "open", observe("source parser", pymupdf.open))
    monkeypatch.setattr(sqlite3, "connect", observe("database", sqlite3.connect))
    with pytest.raises((SourceAdmissionError, SourceRegistrationError), match="configuration"):
        main(argv, intake_context=fixture["context"])
    assert fired
    assert consumed == []
    assert {p: p.read_bytes() if p.exists() else None for p in artifacts} == before
    assert {p.relative_to(ledger): p.read_bytes() for p in ledger.rglob("*.json")} == before_ledger
    assert not locator.exists()
    if not existing:
        assert not fixture["db"].parent.exists()
        assert list((tmp_path / "output").iterdir()) == []
