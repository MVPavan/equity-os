"""Tests for the multi-model, cross-verified thesis layer.

The model clients are faked so the whole pipeline is exercised deterministically:
the number-checker flags an invented number, the divergence detector builds the
adjudication queue, the pipeline fails closed when a client raises, and the prompt
carries only validated facts. Real CLI clients are covered by asserting the exact
command they build via an injected runner (no process is spawned).
"""

from __future__ import annotations

import subprocess
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from fundamentals.contracts.observation import (
    AccountingFramework,
    PeriodType,
    Scope,
)
from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.reconcile.agreement import AgreementStatus, SourceClass, SourceValue
from fundamentals.reconcile.gold_file import GoldFact, GoldFile
from fundamentals.thesis import (
    ClaudeClientConfig,
    ClaudeOpusClient,
    CodexClientConfig,
    CodexSolClient,
    DiscrepancyKind,
    DraftSection,
    DraftStatus,
    FactAnchor,
    JudgmentSection,
    ModelResponse,
    SubprocessResult,
    ThesisClientError,
    ThesisClientTimeoutError,
    ThesisDocumentStatus,
    ThesisDraft,
    Unknown,
    UnknownReason,
    ValidatedFact,
    ValidatedFactSet,
    apply_adjudications_to_markdown,
    build_prompt,
    build_thesis,
    cross_verify,
    extract_numbers,
    from_gold_file,
    from_stock_report,
    known_numbers,
    render_thesis_document,
)
from fundamentals.thesis.adjudication import (
    AdjudicationStatus,
    resolve_adjudication,
    upsert_discrepancies,
)
from fundamentals.thesis.subprocess_runner import run_with_watchdog
from fundamentals.verify.comparison_key import ComparisonKey

# --- shared fixtures / helpers ------------------------------------------------

_REVENUE = "in-bse-fin:RevenueFromOperations"
_EPS = "in-bse-fin:BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations"
_GOOD_JSON = (
    '{"stance":"constructive",'
    '"drivers":["order book expansion continues"],'
    '"key_risks":["customer concentration in defence orders"]}'
)


def _fact_set() -> ValidatedFactSet:
    """A small MTAR-like validated fact set (Revenue + EPS), no unknowns."""
    revenue = ValidatedFact(
        concept_qname=_REVENUE,
        label="Revenue from operations",
        value="174.455",
        unit="INR crore",
        status="agree",
        agreed_sources=("bse-results-pdf", "nse-indas-xbrl-consolidated"),
        corroborating_sources=("screener",),
        first_party_source_count=2,
        single_sourced=False,
        period_start="2024-10-01",
        period_end="2024-12-31",
        scope="consolidated",
        currency="INR",
        anchors=(
            FactAnchor(
                source_id="bse-results-pdf",
                source_class="first_party",
                value="174.455",
                description="page 6, block 10, span x (sha ed8099172e25…)",
            ),
            FactAnchor(
                source_id="screener",
                source_class="derived",
                value="174",
                description="context screener (sha 1f4af5dea4ff…)",
            ),
        ),
    )
    eps = ValidatedFact(
        concept_qname=_EPS,
        label="Basic EPS",
        value="5.19",
        unit="INR per share",
        status="agree",
        agreed_sources=("bse-results-pdf", "nse-indas-xbrl-consolidated"),
        corroborating_sources=("screener",),
        first_party_source_count=2,
        single_sourced=False,
        period_start="2024-10-01",
        period_end="2024-12-31",
        scope="consolidated",
        currency="INR",
        anchors=(
            FactAnchor(
                source_id="nse-indas-xbrl-consolidated",
                source_class="first_party",
                value="5.19",
                description="context OneD (sha 2f42635a245b…)",
            ),
        ),
    )
    return ValidatedFactSet(
        symbol="MTARTECH",
        name="MTAR Technologies",
        domain="Precision engineering",
        quarter="Q3FY25",
        period_start="2024-10-01",
        period_end="2024-12-31",
        scope="consolidated",
        basis="IND_AS",
        currency="INR",
        facts=(revenue, eps),
        unknowns=(),
    )


def _draft(
    label: str,
    *,
    stance: str = "constructive",
    sections: dict[JudgmentSection, list[str]] | None = None,
    raw_text: str = "{}",
    parsed: bool = True,
    status: DraftStatus = DraftStatus.OK,
) -> ThesisDraft:
    """Build a ThesisDraft directly for verifier tests."""
    built = tuple(
        DraftSection(section=section, points=tuple(points))
        for section, points in (sections or {}).items()
    )
    return ThesisDraft(
        model_label=label,
        client_name=label,
        status=status,
        stance=stance,
        sections=built,
        raw_text=raw_text,
        parsed=parsed,
        duration_seconds=0.0,
    )


class _FakeClient:
    """A ThesisModelClient returning canned text or raising a canned error."""

    def __init__(
        self, label: str, name: str, *, text: str | None = None, error: Exception | None = None
    ) -> None:
        self._label = label
        self._name = name
        self._text = text
        self._error = error

    @property
    def label(self) -> str:
        return self._label

    @property
    def name(self) -> str:
        return self._name

    def generate(self, prompt: str) -> ModelResponse:
        if self._error is not None:
            raise self._error
        return ModelResponse(text=self._text or "", duration_seconds=0.01)


class _RecordingRunner:
    """A CommandRunner that records calls and returns canned stdout."""

    def __init__(self, stdout: str = "{}") -> None:
        self.calls: list[dict[str, object]] = []
        self._stdout = stdout

    def __call__(
        self,
        cmd,  # noqa: ANN001 - matches the CommandRunner protocol positional arg
        *,
        timeout_seconds: int,
        retries: int,
        stdin_devnull: bool,
    ) -> SubprocessResult:
        self.calls.append(
            {
                "cmd": list(cmd),
                "timeout_seconds": timeout_seconds,
                "retries": retries,
                "stdin_devnull": stdin_devnull,
            }
        )
        return SubprocessResult(stdout=self._stdout, stderr="", returncode=0, duration_seconds=0.02)


# --- prompt: only validated facts ---------------------------------------------


def test_prompt_contains_only_validated_facts() -> None:
    fact_set = _fact_set()
    prompt = build_prompt(fact_set)

    assert "Revenue from operations" in prompt
    assert "174.455" in prompt
    assert "5.19" in prompt
    assert "- none" in prompt  # no unknowns

    known = known_numbers(fact_set)
    stray = [hit.raw for hit in extract_numbers(prompt) if hit.value not in known]
    assert stray == [], f"prompt leaked non-validated numbers: {stray}"


def test_prompt_lists_unknowns_without_leaking_numbers() -> None:
    fact_set = _fact_set().model_copy(
        update={
            "unknowns": (
                Unknown(
                    concept_qname="in-bse-fin:Expenses",
                    label="Total expenses",
                    reason=UnknownReason.CONFLICT,
                    detail="agreement status conflict; no retained value",
                ),
            )
        }
    )
    prompt = build_prompt(fact_set)
    assert "Total expenses" in prompt
    assert "withheld" in prompt
    known = known_numbers(fact_set)
    assert all(hit.value in known for hit in extract_numbers(prompt))


# --- number extraction / known set --------------------------------------------


def test_extract_numbers_parses_currency_grouping_and_percent() -> None:
    hits = {hit.raw: hit.is_percent for hit in extract_numbers("₹1,234.5 and 12.5% and 174.455")}
    assert "1,234.5" in hits
    assert hits["12.5"] is True
    assert "174.455" in hits


def test_known_numbers_includes_fact_and_anchor_values() -> None:
    from decimal import Decimal

    known = known_numbers(_fact_set())
    assert Decimal("174.455") in known
    assert Decimal("5.19") in known
    assert Decimal("174") in known  # anchor (screener) value
    assert Decimal("250") not in known


# --- number-checker flags invented numbers ------------------------------------


def test_number_checker_flags_model_invented_number() -> None:
    fact_set = _fact_set()
    draft = _draft(
        "gpt-5.6-sol",
        sections={
            JudgmentSection.DRIVERS: [
                "PAT of 250 crore would signal a step-change",  # invented number
                "revenue of 174.455 crore held up",  # validated fact — must not flag
            ],
            JudgmentSection.KEY_RISKS: ["margin pressure persists"],
        },
        raw_text=_GOOD_JSON,
    )
    cross = cross_verify(fact_set, [draft])

    flagged = {claim.number for claim in cross.unsourced_claims}
    assert "250" in flagged
    assert "174.455" not in flagged
    assert all(claim.model_label == "gpt-5.6-sol" for claim in cross.unsourced_claims)


def test_number_checker_flags_computed_percentage() -> None:
    fact_set = _fact_set()
    draft = _draft(
        "m1",
        sections={JudgmentSection.THESIS_IMPACT: ["PBT margin near 12.1% is healthy"]},
        raw_text=_GOOD_JSON,
    )
    cross = cross_verify(fact_set, [draft])
    assert any(claim.number == "12.1%" for claim in cross.unsourced_claims)


def test_clean_draft_produces_no_unsourced_flags() -> None:
    fact_set = _fact_set()
    draft = _draft(
        "m1",
        sections={JudgmentSection.DRIVERS: ["revenue of 174.455 crore and EPS of 5.19 held"]},
        raw_text=_GOOD_JSON,
    )
    cross = cross_verify(fact_set, [draft])
    assert cross.unsourced_claims == ()


# --- divergence detection -----------------------------------------------------


def test_discrepancy_list_captures_point_divergence() -> None:
    fact_set = _fact_set()
    draft_a = _draft(
        "m1",
        sections={
            JudgmentSection.KEY_RISKS: ["customer concentration in defence orders"],
            JudgmentSection.DRIVERS: ["order book expansion continues"],
        },
    )
    draft_b = _draft(
        "m2",
        sections={
            JudgmentSection.KEY_RISKS: ["foreign exchange volatility on exports"],
            JudgmentSection.DRIVERS: ["order book expansion continues"],
        },
    )
    cross = cross_verify(fact_set, [draft_a, draft_b])

    risk_divergences = [
        d
        for d in cross.discrepancies
        if d.section == "key_risks" and d.kind is DiscrepancyKind.DIVERGENT_POINTS
    ]
    assert risk_divergences, cross.discrepancies
    # the shared driver point must not be flagged as divergent
    assert not any(d.section == "drivers" for d in cross.discrepancies)


def test_discrepancy_list_captures_stance_divergence() -> None:
    fact_set = _fact_set()
    shared = {JudgmentSection.DRIVERS: ["shared abc"]}
    draft_a = _draft("m1", stance="constructive", sections=shared)
    draft_b = _draft("m2", stance="cautious", sections=shared)
    cross = cross_verify(fact_set, [draft_a, draft_b])
    assert any(d.kind is DiscrepancyKind.STANCE_DIVERGENCE for d in cross.discrepancies)


def test_discrepancy_list_captures_coverage_gap() -> None:
    fact_set = _fact_set()
    draft_a = _draft(
        "m1", sections={JudgmentSection.OBSERVABLE_FALSIFIERS: ["order inflow stalls"]}
    )
    draft_b = _draft("m2", sections={JudgmentSection.DRIVERS: ["order inflow stalls"]})
    cross = cross_verify(fact_set, [draft_a, draft_b])
    assert any(d.kind is DiscrepancyKind.COVERAGE_GAP for d in cross.discrepancies)


def test_agreeing_drafts_produce_no_divergence() -> None:
    fact_set = _fact_set()
    sections = {
        JudgmentSection.KEY_RISKS: ["customer concentration risk in defence"],
        JudgmentSection.DRIVERS: ["order book expansion continues"],
    }
    draft_a = _draft("m1", stance="neutral", sections=sections)
    draft_b = _draft("m2", stance="neutral", sections=sections)
    cross = cross_verify(fact_set, [draft_a, draft_b])
    assert cross.discrepancies == ()


def test_unstructured_draft_flagged_for_review() -> None:
    fact_set = _fact_set()
    structured = _draft("m1", sections={JudgmentSection.DRIVERS: ["order book expansion"]})
    prose = _draft("m2", parsed=False, raw_text="This is prose, not JSON.", sections={})
    cross = cross_verify(fact_set, [structured, prose])
    assert any(d.kind is DiscrepancyKind.UNSTRUCTURED_OUTPUT for d in cross.discrepancies)


# --- pipeline: fail-closed ----------------------------------------------------


def test_pipeline_two_models_ok_status_and_queue() -> None:
    fact_set = _fact_set()
    json_a = '{"stance":"constructive","key_risks":["customer concentration in defence"]}'
    json_b = '{"stance":"constructive","key_risks":["currency swings on export revenue"]}'
    doc = build_thesis(
        fact_set,
        [_FakeClient("m1", "c1", text=json_a), _FakeClient("m2", "c2", text=json_b)],
    )
    assert doc.status is ThesisDocumentStatus.OK
    assert doc.usable_draft_count == 2
    assert doc.cross_verification.discrepancies  # divergent risks queued


def test_pipeline_fail_closed_when_one_client_raises() -> None:
    fact_set = _fact_set()
    doc = build_thesis(
        fact_set,
        [
            _FakeClient("m1", "c1", text=_GOOD_JSON),
            _FakeClient("m2", "c2", error=ThesisClientError("capacity")),
        ],
    )
    assert doc.status is ThesisDocumentStatus.PARTIAL
    assert doc.usable_draft_count == 1
    failed = [d for d in doc.drafts if d.status is DraftStatus.FAILED]
    assert len(failed) == 1
    # no fabrication: the failed side carries no content
    assert failed[0].raw_text == ""
    assert failed[0].sections == ()


def test_pipeline_timeout_recorded_not_fabricated() -> None:
    fact_set = _fact_set()
    doc = build_thesis(
        fact_set,
        [
            _FakeClient("m1", "c1", text=_GOOD_JSON),
            _FakeClient("m2", "c2", error=ThesisClientTimeoutError("hung")),
        ],
    )
    timed_out = [d for d in doc.drafts if d.status is DraftStatus.TIMED_OUT]
    assert len(timed_out) == 1
    assert timed_out[0].raw_text == ""


def test_pipeline_both_fail_is_blocked() -> None:
    fact_set = _fact_set()
    doc = build_thesis(
        fact_set,
        [
            _FakeClient("m1", "c1", error=ThesisClientError("down")),
            _FakeClient("m2", "c2", error=ThesisClientTimeoutError("hung")),
        ],
    )
    assert doc.status is ThesisDocumentStatus.BLOCKED
    assert doc.usable_draft_count == 0


def test_pipeline_no_clients_is_blocked() -> None:
    doc = build_thesis(_fact_set(), [])
    assert doc.status is ThesisDocumentStatus.BLOCKED
    assert doc.drafts == ()


# --- clients: exact command construction --------------------------------------


def test_codex_client_builds_exact_command_with_closed_stdin() -> None:
    runner = _RecordingRunner(stdout="RESPONSE")
    client = CodexSolClient(CodexClientConfig(), runner=runner)
    response = client.generate("PROMPT-TEXT")

    assert response.text == "RESPONSE"
    assert client.label == "gpt-5.6-sol"
    assert client.name == "codex-sol"
    call = runner.calls[0]
    assert call["cmd"] == [
        "codex",
        "exec",
        "-m",
        "gpt-5.6-sol",
        "-c",
        "model_reasoning_effort=high",
        "-c",
        "tools.web_search=true",
        "-s",
        "read-only",
        "PROMPT-TEXT",
    ]
    assert call["stdin_devnull"] is True


def test_claude_client_builds_command_with_and_without_model() -> None:
    runner = _RecordingRunner(stdout="A")
    client = ClaudeOpusClient(ClaudeClientConfig(model="claude-opus-4-1"), runner=runner)
    client.generate("P")
    assert runner.calls[0]["cmd"] == [
        "claude",
        "-p",
        "P",
        "--output-format",
        "text",
        "--model",
        "claude-opus-4-1",
    ]

    runner2 = _RecordingRunner()
    client2 = ClaudeOpusClient(ClaudeClientConfig(model=None), runner=runner2)
    client2.generate("Q")
    assert runner2.calls[0]["cmd"] == ["claude", "-p", "Q", "--output-format", "text"]
    assert client2.label == "claude-opus"


# --- watchdog -----------------------------------------------------------------


def _completed(
    returncode: int = 0, stdout: str = "ok", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["x"], returncode=returncode, stdout=stdout, stderr=stderr
    )


class _TimeoutRun:
    def __init__(self, fail_times: int) -> None:
        self.calls = 0
        self._fail_times = fail_times

    def __call__(self, cmd, *, timeout: float, stdin_devnull: bool):  # noqa: ANN001, ANN204
        self.calls += 1
        if self.calls <= self._fail_times:
            raise subprocess.TimeoutExpired(cmd=list(cmd), timeout=timeout)
        return _completed()


def test_watchdog_retries_once_then_raises_timeout() -> None:
    run = _TimeoutRun(fail_times=99)
    with pytest.raises(ThesisClientTimeoutError):
        run_with_watchdog(["x"], timeout_seconds=1, retries=1, run=run)
    assert run.calls == 2  # first attempt + one reissue


def test_watchdog_recovers_after_single_timeout() -> None:
    run = _TimeoutRun(fail_times=1)
    result = run_with_watchdog(["x"], timeout_seconds=1, retries=1, run=run)
    assert result.stdout == "ok"
    assert run.calls == 2


def test_watchdog_raises_on_nonzero_exit() -> None:
    def run(cmd, *, timeout: float, stdin_devnull: bool):  # noqa: ANN001, ANN202
        return _completed(returncode=2, stderr="boom")

    with pytest.raises(ThesisClientError):
        run_with_watchdog(["x"], timeout_seconds=1, retries=0, run=run)


def test_watchdog_raises_on_launch_error() -> None:
    def run(cmd, *, timeout: float, stdin_devnull: bool):  # noqa: ANN001, ANN202
        raise OSError("executable not found")

    with pytest.raises(ThesisClientError):
        run_with_watchdog(["x"], timeout_seconds=1, retries=1, run=run)


# --- adapters -----------------------------------------------------------------


def _write_gold(tmp_path: Path) -> Path:
    """Write a minimal 1-AGREE + 1-CONFLICT gold file and return its path."""
    key = ComparisonKey(
        entity_scheme="nse-symbol",
        entity_id="MTARTECH",
        concept_qname=_REVENUE,
        period_type=PeriodType.DURATION,
        period_start=date(2024, 10, 1),
        period_end=date(2024, 12, 31),
        scope=Scope.CONSOLIDATED,
        accounting_basis=AccountingFramework.IND_AS,
        currency="INR",
        unit="INR crore",
        scale=10_000_000,
    )
    provenance = Provenance(
        source_id="nse-indas-xbrl-consolidated",
        file_sha256="2f42635a245b1e2ef9e05ad9cc6f21bbf7b77d9c8b77d59b74673503eba0e822",
        anchor_type=SourceAnchorType.XBRL_CONTEXT,
        context_ref="OneD",
        retrieved_at=datetime(2026, 8, 22, tzinfo=UTC),
    )
    from decimal import Decimal

    agree = GoldFact(
        concept_qname=_REVENUE,
        comparison_key=key,
        value="174.455",
        normalized_unit="INR crore",
        agreement_status=AgreementStatus.AGREE,
        agreed_sources=("bse-results-pdf", "nse-indas-xbrl-consolidated"),
        corroborating_sources=("screener",),
        incompatible_sources=(),
        first_party_source_count=2,
        needs_human_review=False,
        source_values=(
            SourceValue(
                source_id="nse-indas-xbrl-consolidated",
                source_class=SourceClass.FIRST_PARTY,
                normalized_value=Decimal("174.455"),
                normalized_unit="INR crore",
                provenance=provenance,
            ),
        ),
    )
    conflict = agree.model_copy(
        update={
            "concept_qname": "in-bse-fin:Expenses",
            "value": None,
            "agreement_status": AgreementStatus.CONFLICT,
            "agreed_sources": (),
        }
    )
    gold = GoldFile(schema_version=1, symbol="MTARTECH", quarter="Q3FY25", facts=(agree, conflict))
    path = tmp_path / "MTARTECH-Q3FY25.json"
    path.write_text(gold.model_dump_json(), encoding="utf-8")
    return path


def test_from_gold_file_projects_facts_and_unknowns(tmp_path: Path) -> None:
    fact_set = from_gold_file(_write_gold(tmp_path), name="MTAR Technologies", domain="Defence")
    assert fact_set.symbol == "MTARTECH"
    assert fact_set.name == "MTAR Technologies"
    labels = {fact.label: fact.value for fact in fact_set.facts}
    assert labels == {"Revenue from operations": "174.455"}
    assert fact_set.facts[0].anchors[0].description.startswith("context OneD")
    assert [u.reason for u in fact_set.unknowns] == [UnknownReason.CONFLICT]


def test_from_stock_report_projects_facts_and_missing() -> None:
    reading = SimpleNamespace(
        source_id="bse-results-pdf",
        source_class=SourceClass.FIRST_PARTY,
        value="174.455",
        normalized_unit="INR crore",
    )
    fact = SimpleNamespace(
        concept_qname=_REVENUE,
        status=AgreementStatus.AGREE,
        agreed_value="174.455",
        agreed_sources=("bse-results-pdf", "nse-indas-xbrl-consolidated"),
        corroborating_sources=("screener",),
        first_party_source_count=2,
        readings=(reading,),
    )
    report = SimpleNamespace(
        symbol="MTARTECH",
        name="MTAR Technologies",
        domain="Defence",
        quarter="Q3FY25",
        facts=(fact,),
        discrepancies=(),
        missing_material_concepts=("in-bse-fin:Expenses",),
    )
    fact_set = from_stock_report(report)  # type: ignore[arg-type]
    assert [f.value for f in fact_set.facts] == ["174.455"]
    assert fact_set.facts[0].unit == "INR crore"
    assert [u.reason for u in fact_set.unknowns] == [UnknownReason.MISSING]


# --- rendering ----------------------------------------------------------------


def test_render_includes_facts_drafts_and_queue() -> None:
    fact_set = _fact_set()
    json_a = '{"stance":"constructive","key_risks":["customer concentration in defence"]}'
    json_b = '{"stance":"cautious","key_risks":["currency swings on export revenue"]}'
    doc = build_thesis(
        fact_set,
        [
            _FakeClient("gpt-5.6-sol", "codex-sol", text=json_a),
            _FakeClient("claude-opus", "claude-opus", text=json_b),
        ],
    )
    markdown = render_thesis_document(doc, generated_at=datetime(2026, 8, 22, tzinfo=UTC))

    assert "NON-AUTHORITATIVE" in markdown
    assert "Revenue from operations" in markdown
    assert "174.455" in markdown
    assert "[OBSERVED" in markdown
    assert "[OPINION]" in markdown
    assert "gpt-5.6-sol" in markdown
    assert "claude-opus" in markdown
    assert "adjudication queue" in markdown
    assert "Unsourced-number flags" in markdown
    assert "Human adjudication required: **YES**" in markdown


def test_render_blocked_document() -> None:
    doc = build_thesis(
        _fact_set(),
        [_FakeClient("m1", "c1", error=ThesisClientError("down"))],
    )
    # one client, it fails -> zero usable -> blocked
    markdown = render_thesis_document(doc)
    assert doc.status is ThesisDocumentStatus.BLOCKED
    assert "BLOCKED" in markdown


def test_unsourced_only_thesis_requires_adjudication_with_or_without_queue(
    tmp_path: Path,
) -> None:
    """Supplying a durable queue must not hide an unsourced model number."""
    doc = build_thesis(
        _fact_set(),
        [
            _FakeClient(
                "model-a",
                "client-a",
                text='{"stance":"constructive","drivers":["margin reaches 12.1%"]}',
            ),
            _FakeClient(
                "model-b",
                "client-b",
                text='{"stance":"constructive","drivers":["margin reaches 12.1%"]}',
            ),
        ],
    )
    assert doc.cross_verification.unsourced_claims
    assert not doc.cross_verification.discrepancies

    historical_doc = build_thesis(
        _fact_set(),
        [
            _FakeClient(
                "model-a",
                "client-a",
                text='{"stance":"constructive","drivers":["demand is durable"]}',
            ),
            _FakeClient(
                "model-b",
                "client-b",
                text='{"stance":"cautious","drivers":["demand is fragile"]}',
            ),
        ],
    )
    queue_path = tmp_path / "adjudication-queue.json"
    queue = upsert_discrepancies(
        queue_path,
        stock="MTARTECH",
        quarter="Q3FY25",
        discrepancies=historical_doc.cross_verification.discrepancies,
    )
    for entry in queue.entries:
        queue = resolve_adjudication(
            queue_path,
            entry_id=entry.id,
            status=AdjudicationStatus.REJECTED,
        )

    assert "Human adjudication required: **YES**" in render_thesis_document(doc)
    rendered = render_thesis_document(doc, adjudications=queue.entries)
    assert "Human adjudication required: **YES**" in rendered
    assert "Human adjudication required: **YES**" in apply_adjudications_to_markdown(
        rendered, queue.entries
    )


def test_render_folds_resolutions_and_requires_adjudication_until_zero_open(
    tmp_path: Path,
) -> None:
    """Resolved positions render separately while any remaining OPEN item keeps the flag on."""
    doc = build_thesis(
        _fact_set(),
        [
            _FakeClient(
                "model-a",
                "client-a",
                text=(
                    '{"stance":"constructive","key_risks":["customer concentration in defence"]}'
                ),
            ),
            _FakeClient(
                "model-b",
                "client-b",
                text='{"stance":"cautious","key_risks":["currency swings on exports"]}',
            ),
        ],
    )
    queue_path = tmp_path / "adjudication-queue.json"
    queue = upsert_discrepancies(
        queue_path,
        stock="MTARTECH",
        quarter="Q3FY25",
        discrepancies=doc.cross_verification.discrepancies,
        now=datetime(2026, 8, 23, 12, tzinfo=UTC),
    )
    queue = resolve_adjudication(
        queue_path,
        entry_id=queue.entries[0].id,
        status=AdjudicationStatus.ACCEPTED_A,
        note="Primary evidence supports this position.",
        now=datetime(2026, 8, 23, 13, tzinfo=UTC),
    )

    with_one_open = render_thesis_document(doc, adjudications=queue.entries)

    assert "Human adjudication required: **YES**" in with_one_open
    assert "### 4c. Adjudicated" in with_one_open
    assert "Accepted model-a" in with_one_open
    assert "Primary evidence supports this position." in with_one_open
    assert queue.entries[1].id in with_one_open

    queue = resolve_adjudication(
        queue_path,
        entry_id=queue.entries[1].id,
        status=AdjudicationStatus.REJECTED,
        note="Neither position is supported strongly enough.",
        now=datetime(2026, 8, 23, 14, tzinfo=UTC),
    )
    with_zero_open = render_thesis_document(doc, adjudications=queue.entries)

    assert "Human adjudication required: **NO**" in with_zero_open
    assert "Status: REJECTED" in with_zero_open
    assert "Rejected positions retained for audit" in with_zero_open
    assert "customer concentration in defence" in with_zero_open
    assert "currency swings on exports" in with_zero_open
    assert "Neither position is supported strongly enough." in with_zero_open
    assert "includes recorded human adjudications" in with_zero_open
    assert "un-adjudicated model opinion" not in with_zero_open
