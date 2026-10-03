"""Public temporal boundary proofs using generated documents only."""

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from fundamentals.api.pipeline import PipelineResult, XbrlInput, run_pipeline
from fundamentals.store.fact_store import FactStore

SOURCE_TIME = datetime(2024, 7, 17, tzinfo=UTC)
CUTOFF = datetime(2024, 7, 18, tzinfo=UTC)
RUN_TIME = datetime(2026, 10, 2, tzinfo=UTC)


def inputs(tmp_path: Path, *, future: bool = False) -> dict[str, Any]:
    from tests.fundamentals.test_generalization import (
        _genfiler_config,
        _genfiler_xbrl,
        _write_results_pdf,
        _write_transcript_pdf,
    )

    config = _genfiler_config()
    if future:
        config = config.model_copy(
            update={
                "quarter": config.quarter.model_copy(
                    update={"knowledge_cutoff": datetime(2099, 1, 1, tzinfo=UTC)}
                )
            }
        )
    results = tmp_path / "results.pdf"
    transcript = tmp_path / "transcript.pdf"
    rh = _write_results_pdf(results)
    th = _write_transcript_pdf(transcript)
    config = config.model_copy(
        update={
            "results_pdf": config.results_pdf.model_copy(update={"sha256": rh}),
            "transcript_pdf": config.transcript_pdf.model_copy(update={"sha256": th}),
        }
    )
    xml = _genfiler_xbrl()
    return dict(
        config=config,
        xbrl_input=XbrlInput(
            xml_bytes=xml,
            file_sha256=hashlib.sha256(xml).hexdigest(),
            source_id=config.xbrl.source_id,
            retrieved_at=SOURCE_TIME,
        ),
        results_pdf_path=str(results),
        results_pdf_sha256=rh,
        transcript_pdf_path=str(transcript),
        transcript_pdf_sha256=th,
    )


def test_old_unproved_sources_refuse_through_existing_public_arguments(tmp_path: Path) -> None:
    args = inputs(tmp_path)
    store = FactStore(":memory:")
    try:
        with pytest.raises(ValueError, match="cutoff|proof"):
            run_pipeline(**args, store=store)
        assert store.query_canonical() == ()
    finally:
        store.close()


def test_new_fact_clock_is_actual_derivation_not_evaluation_cutoff(tmp_path: Path) -> None:
    args = inputs(tmp_path, future=True)
    before = datetime.now(UTC)
    store = FactStore(":memory:")
    try:
        result = run_pipeline(**args, store=store)
        after = datetime.now(UTC)
        assert all(before <= r.fact.knowledge_time <= after for r in result.stored_revisions)
    finally:
        store.close()


def test_unchanged_effective_selection_does_not_append_decision(tmp_path: Path) -> None:
    args = inputs(tmp_path, future=True)
    store = FactStore(":memory:")
    try:
        first = run_pipeline(**args, store=store)
        identity = first.stored_revisions[0].content_identity
        history = store.get_selection_history(identity)
        run_pipeline(**args, store=store)
        assert store.get_selection_history(identity) == history
    finally:
        store.close()


class SyntheticResolver:
    """Trusted test composition; deliberately unavailable to CLI."""

    def __init__(self, evidence: dict[str, Any]) -> None:
        self.evidence = evidence

    def resolve(self, ref: Any) -> Any:
        return self.evidence[ref.source_id]


class Tick:
    def __init__(self, start: datetime = RUN_TIME) -> None:
        self.value = start

    def __call__(self) -> datetime:
        from datetime import timedelta

        value = self.value
        self.value += timedelta(microseconds=1)
        return value


def synthetic_evidence(args: dict[str, Any]) -> dict[str, Any]:
    """Explicit immutable document bindings and independent synthetic source clocks."""
    from fundamentals.api.source_admission import (
        PipelineSourceRefs,
        RetainedSourceRef,
        SourceCaptureEvidence,
    )
    from fundamentals.contracts.acquisition_outcome import OutcomeCode

    config = args["config"]
    xml = args["xbrl_input"]
    refs = {}
    evidence = {}
    for purpose, source, digest, body in (
        ("xbrl", xml.source_id, xml.file_sha256, xml.xml_bytes),
        (
            "results_pdf",
            config.results_pdf.source_id,
            args["results_pdf_sha256"],
            Path(args["results_pdf_path"]).read_bytes(),
        ),
        (
            "transcript_pdf",
            config.transcript_pdf.source_id,
            args["transcript_pdf_sha256"],
            Path(args["transcript_pdf_path"]).read_bytes(),
        ),
    ):
        ref = RetainedSourceRef(
            source_id=source,
            surface="synthetic",
            request_key="test",
            capture_id=f"20240717T000000.000000Z-{digest[:12]}",
            source_sha256=digest,
            record_sha256="ab" * 32,
        )
        refs[purpose] = ref
        evidence[source] = SourceCaptureEvidence(
            reference=ref,
            source_id=source,
            source_sha256=digest,
            body=body,
            acquired_at=SOURCE_TIME,
            first_seen_at=CUTOFF,
            complete=True,
            outcome=OutcomeCode.OK,
            private_internal=True,
        )
    return dict(
        source_refs=PipelineSourceRefs(**refs), evidence_resolver=SyntheticResolver(evidence)
    )


def run_synthetic_pipeline(**kwargs: Any) -> PipelineResult:
    """Existing synthetic caller fixtures opt into trusted evidence explicitly."""
    config = kwargs["config"]
    kwargs["config"] = config.model_copy(
        update={
            "results_pdf": config.results_pdf.model_copy(
                update={"sha256": kwargs["results_pdf_sha256"]}
            ),
            "transcript_pdf": config.transcript_pdf.model_copy(
                update={"sha256": kwargs["transcript_pdf_sha256"]}
            ),
        }
    )
    return run_pipeline(**kwargs, **synthetic_evidence(kwargs))


@pytest.mark.parametrize("purpose", ["xbrl", "results_pdf", "transcript_pdf"])
@pytest.mark.parametrize(
    "failure",
    [
        "late",
        "naive",
        "offset",
        "hash",
        "reference",
        "source",
        "missing",
        "partial",
        "failed",
        "rights",
    ],
)
def test_each_bad_source_refuses_before_any_parser_or_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    purpose: str,
    failure: str,
) -> None:
    from datetime import timedelta, timezone

    import fundamentals.api.pipeline as pipeline
    from fundamentals.api.source_admission import SourceAdmissionError
    from fundamentals.contracts.acquisition_outcome import OutcomeCode

    args = inputs(tmp_path)
    proof = synthetic_evidence(args)
    ref = getattr(proof["source_refs"], purpose)
    resolver = proof["evidence_resolver"]
    changes = {
        "late": {"acquired_at": CUTOFF + timedelta(seconds=1)},
        "naive": {"first_seen_at": SOURCE_TIME.replace(tzinfo=None)},
        "offset": {"first_seen_at": SOURCE_TIME.astimezone(timezone(timedelta(hours=1)))},
        "hash": {"source_sha256": "cd" * 32},
        "reference": {"reference": ref.model_copy(update={"record_sha256": "cd" * 32})},
        "source": {"source_id": "wrong"},
        "missing": {"body": b""},
        "partial": {"complete": False},
        "failed": {"outcome": OutcomeCode.TRANSPORT_ERROR},
        "rights": {"private_internal": False},
    }
    resolver.evidence[ref.source_id] = resolver.evidence[ref.source_id].model_copy(
        update=changes[failure]
    )

    def never_parse(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("parsing ran before all-source admission")

    monkeypatch.setattr(pipeline, "load_pdf", never_parse)
    monkeypatch.setattr(pipeline, "parse_observations", never_parse)
    ledger = tmp_path / "ledger.json"
    ledger.write_bytes(b"preserve-ledger")
    args["config"] = args["config"].model_copy(update={"ledger_path": str(ledger)})
    store = FactStore(":memory:")
    try:
        with pytest.raises(SourceAdmissionError):
            run_pipeline(**args, **proof, store=store, clock=Tick())
        assert store.query_canonical() == ()
        assert ledger.read_bytes() == b"preserve-ledger"
    finally:
        store.close()


@pytest.mark.parametrize("purpose", ["results_pdf", "transcript_pdf"])
@pytest.mark.parametrize("restore", [False, True])
def test_original_a_b_a_swap_never_reaches_parsed_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    purpose: str,
    restore: bool,
) -> None:
    import pymupdf

    import fundamentals.ingest.pdf_source as pdf_module
    from fundamentals.api.config import GuidanceConfig, GuidanceRuleConfig
    from fundamentals.output.earnings_update import FactRole

    args = inputs(tmp_path)
    original = Path(args[f"{purpose}_path"])
    if purpose == "transcript_pdf":
        original.unlink()
        doc: Any = pymupdf.open()  # type: ignore[no-untyped-call]
        doc.new_page().insert_text((60, 90), "We expect margin guidance 10% to 12%.")
        doc.save(original)
        doc.close()
        args["transcript_pdf_sha256"] = hashlib.sha256(original.read_bytes()).hexdigest()
        args["config"] = args["config"].model_copy(
            update={
                "transcript_pdf": args["config"].transcript_pdf.model_copy(
                    update={"sha256": args["transcript_pdf_sha256"]}
                ),
                "guidance": GuidanceConfig(
                    rules=(
                        GuidanceRuleConfig(
                            metric="margin",
                            label="Margin",
                            pattern=r"margin guidance (\d+)% to (\d+)%",
                            horizon="FY25",
                        ),
                    )
                ),
            }
        )
    original_bytes = original.read_bytes()
    proof = synthetic_evidence(args)
    bdoc: Any = pymupdf.open()  # type: ignore[no-untyped-call]
    bdoc.new_page().insert_text((60, 90), "We expect margin guidance 80% to 90%.")
    replacement = bdoc.tobytes()
    bdoc.close()
    real_hash = pdf_module.compute_file_sha256
    real_open: Any = pymupdf.open
    paths = []
    swapped = False

    def hash_then_swap(path: Path) -> str:
        nonlocal swapped
        paths.append(path)
        digest = real_hash(path)
        if len(paths) == (1 if purpose == "results_pdf" else 2):
            original.write_bytes(replacement)
            swapped = True
        return digest

    def open_then_restore(*a: Any, **kw: Any) -> Any:
        document = real_open(*a, **kw)
        if swapped and restore:
            original.write_bytes(original_bytes)
        return document

    monkeypatch.setattr(pdf_module, "compute_file_sha256", hash_then_swap)
    monkeypatch.setattr(pymupdf, "open", open_then_restore)
    store = FactStore(":memory:")
    try:
        result = run_pipeline(**args, **proof, store=store, clock=Tick())
        assert all(path.parent != tmp_path for path in paths)
        revenue = next(f for f in result.update.facts if f.role is FactRole.REVENUE)
        assert revenue.value == 1000
        if purpose == "transcript_pdf":
            assert result.update.guidance[0].lower_bound == 10
            assert "10% to 12%" in result.update.guidance[0].quote
            assert result.update.guidance[0].source.file_sha256 == args["transcript_pdf_sha256"]
        assert all(not path.exists() for path in paths)
    finally:
        store.close()


def test_true_clocks_unchanged_reopen_and_a_b_a_history(tmp_path: Path) -> None:
    from datetime import timedelta

    from tests.fundamentals.test_generalization import _genfiler_xbrl

    from fundamentals.output.earnings_update import FactRole

    args = inputs(tmp_path)
    config = args["config"]
    eps = "in-bse-fin:BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations"
    args["config"] = config.model_copy(
        update={
            "concepts": config.concepts.model_copy(
                update={"cross_check": tuple(c for c in config.concepts.cross_check if c != eps)}
            )
        }
    )
    db = tmp_path / "facts.sqlite"
    results = []
    for index, value in enumerate(["5.50", "5.50", "6.50", "5.50"]):
        xml = _genfiler_xbrl().replace(b"5.50", value.encode())
        args["xbrl_input"] = args["xbrl_input"].model_copy(
            update={"xml_bytes": xml, "file_sha256": hashlib.sha256(xml).hexdigest()}
        )
        with_store = FactStore(str(db))
        try:
            result = run_pipeline(
                **args,
                **synthetic_evidence(args),
                store=with_store,
                clock=Tick(RUN_TIME + timedelta(minutes=index)),
            )
            results.append(result)
        finally:
            with_store.close()
    revisions = [
        next(r for r in result.stored_revisions if r.fact.observation.concept_qname == eps)
        for result in results
    ]
    assert revisions[0].row_id == revisions[1].row_id == revisions[3].row_id
    assert revisions[3].fact.knowledge_time == revisions[0].fact.knowledge_time
    store = FactStore(str(db))
    try:
        history = store.get_selection_history(revisions[0].content_identity)
        assert [d.row_id for d in history] == [
            revisions[0].row_id,
            revisions[2].row_id,
            revisions[0].row_id,
        ]
        assert store.query_canonical(cutoff=CUTOFF) == ()
        for at, expected in [
            (RUN_TIME + timedelta(seconds=1), "5.50"),
            (RUN_TIME + timedelta(minutes=2, seconds=1), "6.50"),
            (RUN_TIME + timedelta(minutes=3, seconds=1), "5.50"),
        ]:
            selected = store.get_canonical(revisions[0].content_identity, cutoff=at)
            assert (
                selected is not None and str(selected.fact.observation.normalized_value) == expected
            )
        temporal = results[0].temporal_evidence
        assert temporal.run_started_at == RUN_TIME
        assert temporal.sources[0].acquired_at == SOURCE_TIME
        assert temporal.sources[0].first_seen_at == CUTOFF
        assert RUN_TIME < temporal.xbrl_extracted_at < temporal.results_extracted_at
        assert (
            temporal.results_extracted_at
            < temporal.transcript_extracted_at
            < temporal.reconciled_at
        )
        assert revisions[0].fact.knowledge_time == temporal.reconciled_at
        assert history[0].selected_at > temporal.reconciled_at
        assert all(
            a.persisted_basis == "unproved_producer" and not a.historical_certification
            for a in results[3].temporal_evidence.facts
        )
        assert (
            next(f for f in results[3].update.facts if f.role is FactRole.BASIC_EPS).value == 5.50
        )
    finally:
        store.close()


def test_legacy_backdated_duplicate_retains_bytes_times_and_unproved_audit(tmp_path: Path) -> None:
    import sqlite3

    args = inputs(tmp_path)
    db = tmp_path / "facts.sqlite"
    store = FactStore(":memory:")
    try:
        template = run_pipeline(**args, **synthetic_evidence(args), store=store, clock=Tick())
    finally:
        store.close()
    store = FactStore(str(db))
    for revision in template.stored_revisions:
        legacy = revision.fact.model_copy(
            update={"knowledge_time": CUTOFF, "first_seen_time": CUTOFF}
        )
        row = store.put(legacy)
        if revision.canonical_selected_at is not None:
            store.select_canonical(row.row_id, "synthetic legacy", selected_at=CUTOFF)
    store.close()
    with sqlite3.connect(db) as conn:
        before = conn.execute("SELECT row_id, fact_json FROM facts ORDER BY row_id").fetchall()
    store = FactStore(str(db))
    try:
        rerun = run_pipeline(**args, **synthetic_evidence(args), store=store, clock=Tick())
    finally:
        store.close()
    with sqlite3.connect(db) as conn:
        assert (
            conn.execute("SELECT row_id, fact_json FROM facts ORDER BY row_id").fetchall() == before
        )
    assert all(r.fact.knowledge_time == CUTOFF for r in rerun.stored_revisions)
    assert all(
        a.persisted_basis == "unproved_producer"
        and not a.historical_certification
        and a.derivation_completed_at > RUN_TIME
        and a.persisted_knowledge_time == CUTOFF
        for a in rerun.temporal_evidence.facts
    )


@pytest.mark.parametrize("purpose_index", [0, 1, 2])
def test_local_capture_finishing_after_cutoff_refuses_before_load(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    purpose_index: int,
) -> None:
    from datetime import timedelta

    import fundamentals.api.pipeline as pipeline
    from fundamentals.api.source_admission import SourceAdmissionError

    args = inputs(tmp_path)
    times = [SOURCE_TIME, SOURCE_TIME, SOURCE_TIME, SOURCE_TIME]
    times[purpose_index + 1] = CUTOFF + timedelta(seconds=1)
    clock = iter(times)

    def never_load(*a: Any, **kw: Any) -> Any:
        pytest.fail("local capture rejection happened after parsing")

    monkeypatch.setattr(pipeline, "load_pdf", never_load)
    store = FactStore(":memory:")
    try:
        with pytest.raises(SourceAdmissionError, match="cutoff"):
            run_pipeline(**args, store=store, clock=lambda: next(clock))
        assert store.query_canonical() == ()
    finally:
        store.close()


def test_clock_reversal_after_admission_refuses_without_fact_writes(tmp_path: Path) -> None:
    from datetime import timedelta

    from fundamentals.api.source_admission import SourceAdmissionError

    args = inputs(tmp_path)
    times = iter(
        [
            RUN_TIME,
            RUN_TIME + timedelta(seconds=1),
            RUN_TIME + timedelta(seconds=2),
            RUN_TIME + timedelta(seconds=3),
            RUN_TIME,
        ]
    )
    store = FactStore(":memory:")
    try:
        with pytest.raises(SourceAdmissionError, match="backwards"):
            run_pipeline(**args, **synthetic_evidence(args), store=store, clock=lambda: next(times))
        assert store.query_canonical() == ()
    finally:
        store.close()


def test_repeated_local_guidance_keeps_ledger_and_advances_acquisition(tmp_path: Path) -> None:
    """A fresh admission of identical bytes must not rewrite retained guidance."""
    from datetime import timedelta

    import pymupdf

    from fundamentals.api.config import GuidanceConfig, GuidanceRuleConfig

    args = inputs(tmp_path, future=True)
    transcript = Path(args["transcript_pdf_path"])
    transcript.unlink()
    document: Any = pymupdf.open()
    document.new_page().insert_text((60, 90), "We expect margin guidance 10% to 12%.")
    document.save(transcript)
    document.close()
    digest = hashlib.sha256(transcript.read_bytes()).hexdigest()
    ledger_path = tmp_path / "ledger.json"
    args["transcript_pdf_sha256"] = digest
    config = args["config"]
    args["config"] = config.model_copy(
        update={
            "transcript_pdf": config.transcript_pdf.model_copy(update={"sha256": digest}),
            "ledger_path": str(ledger_path),
            "guidance": GuidanceConfig(
                rules=(
                    GuidanceRuleConfig(
                        metric="margin",
                        label="Margin",
                        pattern=r"margin guidance (\d+)% to (\d+)%",
                        horizon="FY25",
                    ),
                )
            ),
        }
    )
    db = tmp_path / "facts.sqlite"
    store = FactStore(str(db))
    try:
        first = run_pipeline(**args, store=store, clock=Tick())
    finally:
        store.close()
    before = {p: p.read_bytes() for p in [ledger_path, *tmp_path.glob("ledger.quarters/*.json")]}
    store = FactStore(str(db))
    try:
        second = run_pipeline(**args, store=store, clock=Tick(RUN_TIME + timedelta(minutes=1)))
        assert first.update.guidance and second.update.guidance
        assert second.update.ledger == first.update.ledger
        assert all(p.read_bytes() == body for p, body in before.items())
        assert all(s.mode == "new_local_capture" for s in second.temporal_evidence.sources)
        assert (
            second.temporal_evidence.sources[2].acquired_at
            > first.temporal_evidence.sources[2].acquired_at
        )
        assert (
            second.update.guidance[0].source.retrieved_at
            == second.temporal_evidence.sources[2].acquired_at
        )
        assert second.update.ledger is not None
        assert second.update.ledger.quarter_claims is not None
        assert (
            second.update.ledger.quarter_claims[0].provenance.retrieved_at
            == first.temporal_evidence.sources[2].acquired_at
        )
    finally:
        store.close()


def test_cross_run_a_t0_b_t2_a_t1_refuses_rollback(tmp_path: Path) -> None:
    """An earlier as-of A cannot hide the actual effective B selection head."""
    from datetime import timedelta

    from tests.fundamentals.test_generalization import _genfiler_xbrl

    from fundamentals.store.fact_store import CanonicalSelectionError

    args = inputs(tmp_path)
    config = args["config"]
    eps = "in-bse-fin:BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations"
    args["config"] = config.model_copy(
        update={
            "concepts": config.concepts.model_copy(
                update={"cross_check": tuple(c for c in config.concepts.cross_check if c != eps)}
            )
        }
    )
    db = tmp_path / "facts.sqlite"
    for minute, value in [(0, "5.50"), (2, "6.50")]:
        xml = _genfiler_xbrl().replace(b"5.50", value.encode())
        args["xbrl_input"] = args["xbrl_input"].model_copy(
            update={
                "xml_bytes": xml,
                "file_sha256": hashlib.sha256(xml).hexdigest(),
            }
        )
        store = FactStore(str(db))
        try:
            run_pipeline(
                **args,
                **synthetic_evidence(args),
                store=store,
                clock=Tick(RUN_TIME + timedelta(minutes=minute)),
            )
        finally:
            store.close()
    xml = _genfiler_xbrl()
    args["xbrl_input"] = args["xbrl_input"].model_copy(
        update={
            "xml_bytes": xml,
            "file_sha256": hashlib.sha256(xml).hexdigest(),
        }
    )
    store = FactStore(str(db))
    try:
        heads = store.query_canonical(cutoff=RUN_TIME + timedelta(minutes=3))
        history = {
            r.content_identity: store.get_selection_history(r.content_identity) for r in heads
        }
        with pytest.raises(CanonicalSelectionError, match="predecessor"):
            run_pipeline(
                **args,
                **synthetic_evidence(args),
                store=store,
                clock=Tick(RUN_TIME + timedelta(minutes=1)),
            )
        assert all(
            store.get_selection_history(identity) == decisions
            for identity, decisions in history.items()
        )
        assert store.query_canonical(cutoff=RUN_TIME + timedelta(minutes=3)) == heads
    finally:
        store.close()


def test_trusted_caller_fixture_composes_generated_documents_without_config_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from temporal_fixture_support import (
        FIXTURE_ACQUIRED_AT,
        install_trusted_fixture_cli,
        run_trusted_fixture_pipeline,
    )

    import fundamentals.api.cli as cli

    args = inputs(tmp_path)
    config = args["config"]
    original_config = config.model_dump_json()
    store = FactStore(":memory:")
    try:
        result = run_trusted_fixture_pipeline(**args, store=store)
        assert result.cross_check_results and all(c.matched for c in result.cross_check_results)
        assert result.update.facts[0].value == 1000
        assert config.model_dump_json() == original_config
        assert all(s.mode == "trusted_direct" for s in result.temporal_evidence.sources)
    finally:
        store.close()

    # The monkeypatch belongs to caller-report fixtures, not production CLI proof.
    install_trusted_fixture_cli(monkeypatch)
    xbrl = args["xbrl_input"]
    with cli.prepare_pipeline_sources(
        xbrl_bytes=xbrl.xml_bytes,
        xbrl_source_id=xbrl.source_id,
        xbrl_sha256=xbrl.file_sha256,
        results_pdf_path=args["results_pdf_path"],
        results_pdf_sha256=args["results_pdf_sha256"],
        results_source_id=config.results_pdf.source_id,
        transcript_pdf_path=args["transcript_pdf_path"],
        transcript_pdf_sha256=args["transcript_pdf_sha256"],
        transcript_source_id=config.transcript_pdf.source_id,
        cutoff=config.quarter.knowledge_cutoff,
        run_started_at=datetime.now(UTC),
    ) as prepared:
        assert prepared.transcript_pdf.acquired_at == FIXTURE_ACQUIRED_AT
        assert prepared.transcript_pdf.mode == "trusted_direct"
        assert prepared.xbrl_bytes == xbrl.xml_bytes


def local_guidance_inputs(tmp_path: Path) -> dict[str, Any]:
    import pymupdf

    from fundamentals.api.config import GuidanceConfig, GuidanceRuleConfig

    args = inputs(tmp_path, future=True)
    transcript = Path(args["transcript_pdf_path"])
    transcript.unlink()
    document: Any = pymupdf.open()
    document.new_page().insert_text((60, 90), "We expect margin guidance 10% to 12%.")
    document.save(transcript)
    document.close()
    digest = hashlib.sha256(transcript.read_bytes()).hexdigest()
    ledger_path = tmp_path / "ledger.json"
    args["transcript_pdf_sha256"] = digest
    config = args["config"]
    args["config"] = config.model_copy(
        update={
            "transcript_pdf": config.transcript_pdf.model_copy(update={"sha256": digest}),
            "ledger_path": str(ledger_path),
            "guidance": GuidanceConfig(
                rules=(
                    GuidanceRuleConfig(
                        metric="margin",
                        label="Margin",
                        pattern=r"margin guidance (\d+)% to (\d+)%",
                        horizon="FY25",
                    ),
                )
            ),
        }
    )
    return args


@pytest.mark.parametrize("equivalent_pattern", [False, True])
def test_local_guidance_replay_retains_exact_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, equivalent_pattern: bool
) -> None:
    from datetime import timedelta

    import fundamentals.api.pipeline as pipeline

    args = local_guidance_inputs(tmp_path)
    store = FactStore(":memory:")
    try:
        first = run_pipeline(**args, store=store, clock=Tick())
        assert first.update.ledger is not None
        prior = first.update.ledger
        before = Path(args["config"].ledger_path).read_bytes()
        if equivalent_pattern:
            config = args["config"]
            rule = config.guidance.rules[0].model_copy(
                update={"pattern": r"margin guidance ([0-9]+)% to ([0-9]+)%"}
            )
            args["config"] = config.model_copy(
                update={"guidance": config.guidance.model_copy(update={"rules": (rule,)})}
            )
        loaded = []
        original_load = pipeline.load_ledger

        def observe_loaded(*a: Any, **kw: Any) -> Any:
            ledger = original_load(*a, **kw)
            loaded.append(ledger)
            return ledger

        monkeypatch.setattr(pipeline, "load_ledger", observe_loaded)
        second = run_pipeline(**args, store=store, clock=Tick(RUN_TIME + timedelta(minutes=1)))
        assert second.update.ledger is loaded[0]
        assert second.update.ledger == prior
        assert Path(args["config"].ledger_path).read_bytes() == before
        assert (
            second.update.guidance[0].source.retrieved_at
            > first.update.guidance[0].source.retrieved_at
        )
        assert second.temporal_evidence.facts[0].historical_certification is False
    finally:
        store.close()


@pytest.mark.parametrize(
    "field,value",
    [
        ("metric", "changed"),
        ("lower_bound", "11"),
        ("upper_bound", "13"),
        ("unit", "INR"),
        ("constant_currency", True),
        ("horizon", "FY26"),
        ("scope", "standalone"),
        ("qualifiers", ["changed"]),
        ("epistemic_class", "opinion"),
        ("source_quote", "different quote"),
        ("provenance.source_id", "changed"),
        ("provenance.file_sha256", "ab" * 32),
        ("provenance.page", 2),
        ("provenance.block", 2),
        ("provenance.span", "changed-span"),
        ("provenance.filed_at", "2024-07-17T00:00:00Z"),
        ("provenance.published_at", "2024-07-17T00:00:00Z"),
        ("provenance.context_ref", "changed"),
    ],
)
def test_local_guidance_changed_nonclock_field_conflicts(
    tmp_path: Path, field: str, value: Any
) -> None:
    import json
    from datetime import timedelta

    args = local_guidance_inputs(tmp_path)
    store = FactStore(":memory:")
    try:
        run_pipeline(**args, store=store, clock=Tick())
        path = Path(args["config"].ledger_path)
        payload = json.loads(path.read_bytes())
        target = payload["quarter_claims"][0]
        if field.startswith("provenance."):
            target = target["provenance"]
        target[field.split(".")[-1]] = value
        retained = [path, *tmp_path.glob("ledger.quarters/*.json")]
        for artifact in retained:
            artifact.write_text(json.dumps(payload))
        before = {artifact: artifact.read_bytes() for artifact in retained}
        with pytest.raises(ValueError, match="conflicting same-quarter guidance"):
            run_pipeline(**args, store=store, clock=Tick(RUN_TIME + timedelta(minutes=1)))
        assert all(artifact.read_bytes() == body for artifact, body in before.items())
    finally:
        store.close()


@pytest.mark.parametrize(
    "oldclock", ["missing", "naive", "nonutc", "after_derivation", "after_cutoff"]
)
@pytest.mark.parametrize("field", ["retrieved_at", "first_seen_at"])
def test_local_guidance_invalid_retained_clock_refuses(
    tmp_path: Path, oldclock: str, field: str
) -> None:
    import json
    from datetime import timedelta

    args = local_guidance_inputs(tmp_path)
    store = FactStore(":memory:")
    try:
        run_pipeline(**args, store=store, clock=Tick())
        path = Path(args["config"].ledger_path)
        payload = json.loads(path.read_bytes())
        provenance = payload["quarter_claims"][0]["provenance"]
        values = {
            "missing": None,
            "naive": "2026-10-02T00:00:00",
            "nonutc": "2026-10-02T01:00:00+01:00",
            "after_derivation": "2026-10-02T00:02:00Z",
            "after_cutoff": "2100-01-01T00:00:00Z",
        }
        provenance[field] = values[oldclock]
        retained = [path, *tmp_path.glob("ledger.quarters/*.json")]
        for artifact in retained:
            artifact.write_text(json.dumps(payload))
        before = {artifact: artifact.read_bytes() for artifact in retained}
        from pydantic import ValidationError

        from fundamentals.api.source_admission import SourceAdmissionError

        if oldclock == "missing" and field == "retrieved_at":
            refusal = ValidationError
            message = "Input should be a valid datetime"
        else:
            refusal = SourceAdmissionError
            message = {
                "missing": "retained guidance clocks require present UTC time",
                "naive": "temporal evidence requires aware UTC time",
                "nonutc": "temporal evidence requires aware UTC time",
                "after_derivation": (
                    "retained guidance clocks exceed cutoff or current derivation completion"
                ),
                "after_cutoff": (
                    "retained guidance clocks exceed cutoff or current derivation completion"
                ),
            }[oldclock]
        with pytest.raises(refusal, match=message):
            run_pipeline(**args, store=store, clock=Tick(RUN_TIME + timedelta(minutes=1)))
        assert all(artifact.read_bytes() == body for artifact, body in before.items())
    finally:
        store.close()


def test_local_guidance_legacy_incomplete_claims_receive_no_relaxed_replay(tmp_path: Path) -> None:
    import json
    from datetime import timedelta

    args = local_guidance_inputs(tmp_path)
    store = FactStore(":memory:")
    try:
        run_pipeline(**args, store=store, clock=Tick())
        path = Path(args["config"].ledger_path)
        payload = json.loads(path.read_bytes())
        payload.pop("quarter_claims")
        retained = [path, *tmp_path.glob("ledger.quarters/*.json")]
        for artifact in retained:
            artifact.write_text(json.dumps(payload))
        before = {artifact: artifact.read_bytes() for artifact in retained}
        with pytest.raises(ValueError, match="conflicting same-quarter guidance"):
            run_pipeline(**args, store=store, clock=Tick(RUN_TIME + timedelta(minutes=1)))
        assert all(artifact.read_bytes() == body for artifact, body in before.items())
    finally:
        store.close()


@pytest.mark.parametrize("field", ["retrieved_at", "first_seen_at"])
def test_retained_guidance_clock_after_cutoff_before_derivation_refuses(
    tmp_path: Path, field: str
) -> None:
    import json
    from datetime import timedelta

    from fundamentals.api.source_admission import SourceAdmissionError

    args = local_guidance_inputs(tmp_path)
    config = args["config"]
    args["config"] = config.model_copy(
        update={"quarter": config.quarter.model_copy(update={"knowledge_cutoff": CUTOFF})}
    )
    store = FactStore(":memory:")
    try:
        run_pipeline(**args, **synthetic_evidence(args), store=store, clock=Tick())
        path = Path(args["config"].ledger_path)
        payload = json.loads(path.read_bytes())
        payload["quarter_claims"][0]["provenance"][field] = "2025-01-01T00:00:00Z"
        retained = [path, *tmp_path.glob("ledger.quarters/*.json")]
        for artifact in retained:
            artifact.write_text(json.dumps(payload))
        before = {artifact: artifact.read_bytes() for artifact in retained}
        with pytest.raises(
            SourceAdmissionError,
            match="^retained guidance clocks exceed cutoff or current derivation completion$",
        ):
            run_pipeline(
                **args,
                **synthetic_evidence(args),
                store=store,
                clock=Tick(RUN_TIME + timedelta(minutes=1)),
            )
        assert all(artifact.read_bytes() == body for artifact, body in before.items())
    finally:
        store.close()


def test_native_receipt_role_refuses_even_when_source_and_content_pins_coincide(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dataclasses import replace

    from tests.fundamentals.test_source_intake_cli import intake_fixture

    from fundamentals.api.cli import main
    from fundamentals.api.config import load_config
    from fundamentals.api.source_admission import (
        NativeSourceEvidenceResolver,
        PipelineSourceRefs,
        SourceAdmissionError,
        prepare_pipeline_sources,
    )
    from fundamentals.contracts.source_registration import SourceRole

    fixture = intake_fixture(tmp_path, monkeypatch)
    assert main(fixture["register"], intake_context=fixture["context"]) == 0
    context = fixture["context"]
    xbrl = context.bindings[0]
    context = replace(
        context,
        bindings=(
            xbrl,
            replace(xbrl, role=SourceRole.RESULTS_PDF),
            context.bindings[2],
        ),
    )
    config = load_config(fixture["config"])
    refs = dict(fixture["refs"], results_pdf=fixture["refs"]["xbrl"])
    with pytest.raises(SourceAdmissionError, match="role"):
        with prepare_pipeline_sources(
            xbrl_bytes=b"",
            xbrl_source_id=xbrl.source_id,
            xbrl_sha256=xbrl.expected_sha256,
            results_pdf_path=tmp_path / "absent-results",
            results_pdf_sha256=xbrl.expected_sha256,
            results_source_id=xbrl.source_id,
            transcript_pdf_path=tmp_path / "absent-transcript",
            transcript_pdf_sha256=config.transcript_pdf.sha256,
            transcript_source_id=config.transcript_pdf.source_id,
            cutoff=config.quarter.knowledge_cutoff,
            run_started_at=config.quarter.knowledge_cutoff,
            source_refs=PipelineSourceRefs(**refs),
            evidence_resolver=NativeSourceEvidenceResolver(
                fixture["root"], approved_intake=context
            ),
        ):
            pytest.fail("wrong-purpose receipt was admitted")
    assert not fixture["db"].parent.exists()
