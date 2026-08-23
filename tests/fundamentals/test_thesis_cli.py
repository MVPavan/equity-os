"""CLI acceptance tests for the ``fundamentals thesis`` subcommand.

The two model clients are faked (no process spawned, no network) and injected at
the command's seam, so the whole CLI path is exercised deterministically:

* two usable drafts -> OK, the sourced markdown is written;
* one model unreachable -> PARTIAL, the doc still emits with the recorded gap;
* both unreachable -> BLOCKED, the doc emits (facts only) but the exit code is
  non-zero (fail closed);
* a missing gold file fails closed telling the user to run ``validate`` first.

The default (non-test) path constructs the two REAL clients from config; that
construction is asserted without invoking a model.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from structlog.testing import capture_logs

from fundamentals.api.cli import (
    _build_parser,
    _build_thesis_clients,
    _thesis_exit_code,
    main,
    thesis_command,
)
from fundamentals.contracts.observation import AccountingFramework, PeriodType, Scope
from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.reconcile.agreement import AgreementStatus, SourceClass, SourceValue
from fundamentals.reconcile.gold_file import GoldFact, GoldFile
from fundamentals.thesis import (
    ClaudeOpusClient,
    CodexSolClient,
    ModelResponse,
    ThesisClientError,
    ThesisConfig,
    ThesisDocumentStatus,
)
from fundamentals.thesis.adjudication import (
    AdjudicationStatus,
    load_adjudication_queue,
    resolve_adjudication,
)
from fundamentals.verify.comparison_key import ComparisonKey

_REVENUE = "in-bse-fin:RevenueFromOperations"
_SYMBOL = "MTARTECH"
_QUARTER = "Q3FY25"
_GOOD_JSON = (
    '{"stance":"constructive",'
    '"drivers":["order book expansion continues"],'
    '"key_risks":["customer concentration in defence orders"]}'
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
        self.call_count = 0

    @property
    def label(self) -> str:
        return self._label

    @property
    def name(self) -> str:
        return self._name

    def generate(self, prompt: str) -> ModelResponse:
        self.call_count += 1
        if self._error is not None:
            raise self._error
        return ModelResponse(text=self._text or "", duration_seconds=0.01)


def _write_gold(gold_dir: Path) -> Path:
    """Write a minimal one-AGREE-fact gold file for MTARTECH-Q3FY25."""
    key = ComparisonKey(
        entity_scheme="nse-symbol",
        entity_id=_SYMBOL,
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
    fact = GoldFact(
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
    gold = GoldFile(schema_version=1, symbol=_SYMBOL, quarter=_QUARTER, facts=(fact,))
    gold_dir.mkdir(parents=True, exist_ok=True)
    path = gold_dir / f"{_SYMBOL}-{_QUARTER}.json"
    path.write_text(gold.model_dump_json(), encoding="utf-8")
    return path


def _args(
    gold_dir: Path,
    out_dir: Path,
    *,
    symbol: str | None = _SYMBOL,
    done_only: bool = False,
) -> object:
    """Parse a ``thesis`` argv through the real CLI parser."""
    argv = ["thesis", "--quarter", _QUARTER, "--gold-dir", str(gold_dir), "--out-dir", str(out_dir)]
    if symbol is not None:
        argv += ["--symbol", symbol]
    else:
        argv.append("--watchlist")
    if done_only:
        argv.append("--done-only")
    return _build_parser().parse_args(argv)


def test_thesis_cli_writes_sourced_markdown_with_fake_clients(tmp_path: Path) -> None:
    gold_dir, out_dir = tmp_path / "gold", tmp_path / "thesis"
    _write_gold(gold_dir)
    clients = (
        _FakeClient("gpt-5.6-sol", "codex-sol", text=_GOOD_JSON),
        _FakeClient("claude-opus", "claude-opus", text=_GOOD_JSON),
    )
    docs = thesis_command(
        _args(gold_dir, out_dir),
        clients=clients,
        queue_path=out_dir / "adjudication-queue.json",
    )

    assert len(docs) == 1
    assert docs[0].status is ThesisDocumentStatus.OK
    assert _thesis_exit_code(docs) == 0

    out_path = out_dir / f"{_SYMBOL}-{_QUARTER}.md"
    assert out_path.is_file()
    text = out_path.read_text(encoding="utf-8")
    # Heading uses the watchlist display name resolved from the real config.
    assert f"MTAR Technologies Limited ({_SYMBOL})" in text
    assert "NON-AUTHORITATIVE DRAFT" in text  # invariant 11 banner
    assert "174.455" in text  # the validated (OBSERVED) fact value


def test_thesis_cli_partial_when_one_model_unreachable(tmp_path: Path) -> None:
    gold_dir, out_dir = tmp_path / "gold", tmp_path / "thesis"
    _write_gold(gold_dir)
    clients = (
        _FakeClient("gpt-5.6-sol", "codex-sol", error=ThesisClientError("codex unreachable")),
        _FakeClient("claude-opus", "claude-opus", text=_GOOD_JSON),
    )
    docs = thesis_command(
        _args(gold_dir, out_dir),
        clients=clients,
        queue_path=out_dir / "adjudication-queue.json",
    )

    assert docs[0].status is ThesisDocumentStatus.PARTIAL
    assert _thesis_exit_code(docs) == 0  # a partial thesis is still emitted
    text = (out_dir / f"{_SYMBOL}-{_QUARTER}.md").read_text(encoding="utf-8")
    assert "PARTIAL" in text.upper()  # the recorded gap is surfaced


def test_thesis_cli_blocked_when_both_fail_exits_nonzero(tmp_path: Path) -> None:
    gold_dir, out_dir = tmp_path / "gold", tmp_path / "thesis"
    _write_gold(gold_dir)
    clients = (
        _FakeClient("gpt-5.6-sol", "codex-sol", error=ThesisClientError("codex down")),
        _FakeClient("claude-opus", "claude-opus", error=ThesisClientError("claude down")),
    )
    docs = thesis_command(
        _args(gold_dir, out_dir),
        clients=clients,
        queue_path=out_dir / "adjudication-queue.json",
    )

    assert docs[0].status is ThesisDocumentStatus.BLOCKED
    assert _thesis_exit_code(docs) == 1  # fail closed
    # The doc still emits (validated facts + recorded gaps), never fabricated judgment.
    assert (out_dir / f"{_SYMBOL}-{_QUARTER}.md").is_file()


def test_thesis_cli_fails_closed_on_missing_gold(tmp_path: Path) -> None:
    gold_dir, out_dir = tmp_path / "gold", tmp_path / "thesis"
    gold_dir.mkdir(parents=True, exist_ok=True)  # present but empty
    clients = (
        _FakeClient("gpt-5.6-sol", "codex-sol", text=_GOOD_JSON),
        _FakeClient("claude-opus", "claude-opus", text=_GOOD_JSON),
    )
    with pytest.raises(SystemExit, match="validate"):
        thesis_command(
            _args(gold_dir, out_dir),
            clients=clients,
            queue_path=out_dir / "adjudication-queue.json",
        )


def test_build_thesis_clients_constructs_the_two_real_clients() -> None:
    # The default (non-test) path builds the two independent real clients from
    # config, without invoking any model.
    clients = _build_thesis_clients(ThesisConfig())
    assert [client.name for client in clients] == ["codex-sol", "claude-opus"]
    assert isinstance(clients[0], CodexSolClient)
    assert isinstance(clients[1], ClaudeOpusClient)


def test_thesis_main_dispatch_fails_closed_on_missing_gold(tmp_path: Path) -> None:
    # main() wires the subcommand end-to-end; a missing gold file fails closed
    # before any model client is ever invoked.
    with pytest.raises(SystemExit):
        main(["thesis", "--symbol", _SYMBOL, "--quarter", _QUARTER, "--gold-dir", str(tmp_path)])


def test_rebuilt_thesis_carries_resolution_forward_without_reopening(tmp_path: Path) -> None:
    """A matching durable decision must survive a fresh two-model thesis build."""
    gold_dir, out_dir = tmp_path / "gold", tmp_path / "thesis"
    _write_gold(gold_dir)
    clients = (
        _FakeClient(
            "model-a",
            "client-a",
            text='{"stance":"constructive","drivers":["demand remains durable"]}',
        ),
        _FakeClient(
            "model-b",
            "client-b",
            text='{"stance":"cautious","drivers":["demand remains fragile"]}',
        ),
    )
    args = _args(gold_dir, out_dir)
    queue_path = out_dir / "adjudication-queue.json"
    thesis_command(args, clients=clients, queue_path=queue_path)
    queue = load_adjudication_queue(queue_path)
    assert queue.entries
    for entry in queue.entries:
        resolve_adjudication(
            queue_path,
            entry_id=entry.id,
            status=AdjudicationStatus.ACCEPTED_A,
            note="Analyst accepted model A.",
            now=datetime(2026, 8, 23, 14, tzinfo=UTC),
        )

    thesis_command(args, clients=clients, queue_path=queue_path)

    rebuilt = load_adjudication_queue(queue_path)
    assert {entry.status for entry in rebuilt.entries} == {AdjudicationStatus.ACCEPTED_A}
    markdown = (out_dir / f"{_SYMBOL}-{_QUARTER}.md").read_text(encoding="utf-8")
    assert "### 4c. Adjudicated" in markdown
    assert "Analyst accepted model A." in markdown
    assert "Human adjudication required: **NO**" in markdown


def test_partial_rebuild_preserves_existing_supersession_state(tmp_path: Path) -> None:
    """A transient model outage must not supersede previously resolved divergences."""
    gold_dir, out_dir = tmp_path / "gold", tmp_path / "thesis"
    _write_gold(gold_dir)
    queue_path = out_dir / "adjudication-queue.json"
    args = _args(gold_dir, out_dir)
    complete_clients = (
        _FakeClient(
            "model-a",
            "client-a",
            text='{"stance":"constructive","drivers":["demand remains durable"]}',
        ),
        _FakeClient(
            "model-b",
            "client-b",
            text='{"stance":"cautious","drivers":["demand remains fragile"]}',
        ),
    )
    thesis_command(args, clients=complete_clients, queue_path=queue_path)
    queue = load_adjudication_queue(queue_path)
    for entry in queue.entries:
        resolve_adjudication(
            queue_path,
            entry_id=entry.id,
            status=AdjudicationStatus.ACCEPTED_A,
            note="Analyst accepted model A.",
        )

    partial = thesis_command(
        args,
        clients=(
            _FakeClient("model-a", "client-a", error=ThesisClientError("transient outage")),
            complete_clients[1],
        ),
        queue_path=queue_path,
    )

    assert partial[0].status is ThesisDocumentStatus.PARTIAL
    assert all(not entry.superseded for entry in load_adjudication_queue(queue_path).entries)


def test_done_only_watchlist_skips_missing_gold_with_logged_reason(tmp_path: Path) -> None:
    """Batch thesis mode must call models only for stocks with a local gold file."""
    gold_dir, out_dir = tmp_path / "gold", tmp_path / "thesis"
    _write_gold(gold_dir)
    clients = (
        _FakeClient("model-a", "client-a", text=_GOOD_JSON),
        _FakeClient("model-b", "client-b", text=_GOOD_JSON),
    )

    with capture_logs() as logs:
        docs = thesis_command(
            _args(gold_dir, out_dir, symbol=None, done_only=True),
            clients=clients,
            queue_path=out_dir / "adjudication-queue.json",
        )

    assert [doc.fact_set.symbol for doc in docs] == [_SYMBOL]
    skipped = [event for event in logs if event["event"] == "thesis_skipped_no_gold"]
    assert skipped
    assert {event["reason"] for event in skipped} == {"gold file does not exist"}


def test_watchlist_without_done_only_fails_closed_listing_missing_gold(tmp_path: Path) -> None:
    """A normal batch may not silently produce a partial watchlist."""
    gold_dir, out_dir = tmp_path / "gold", tmp_path / "thesis"
    _write_gold(gold_dir)
    clients = (
        _FakeClient("model-a", "client-a", text=_GOOD_JSON),
        _FakeClient("model-b", "client-b", text=_GOOD_JSON),
    )

    with pytest.raises(SystemExit, match="missing.*LAURUSLABS"):
        thesis_command(
            _args(gold_dir, out_dir, symbol=None),
            clients=clients,
            queue_path=out_dir / "adjudication-queue.json",
        )

    assert [client.call_count for client in clients] == [0, 0]


def test_thesis_queue_defaults_to_custom_output_directory(tmp_path: Path) -> None:
    """A scratch output directory must carry its own adjudication queue."""
    gold_dir = tmp_path / "gold"
    custom_out_dir = tmp_path / "custom-thesis"
    _write_gold(gold_dir)
    clients = (
        _FakeClient(
            "model-a",
            "client-a",
            text='{"stance":"constructive","drivers":["demand remains durable"]}',
        ),
        _FakeClient(
            "model-b",
            "client-b",
            text='{"stance":"cautious","drivers":["demand remains fragile"]}',
        ),
    )

    thesis_command(_args(gold_dir, custom_out_dir), clients=clients)

    assert (custom_out_dir / "adjudication-queue.json").is_file()


@pytest.mark.parametrize(
    ("symbol", "quarter"),
    (("../escape", _QUARTER), (_SYMBOL, "../escape")),
)
def test_thesis_rejects_path_tokens_before_model_calls(
    tmp_path: Path, symbol: str, quarter: str
) -> None:
    """Untrusted CLI tokens must never escape the configured gold/output roots."""
    gold_dir, out_dir = tmp_path / "gold", tmp_path / "thesis"
    clients = (
        _FakeClient("model-a", "client-a", text=_GOOD_JSON),
        _FakeClient("model-b", "client-b", text=_GOOD_JSON),
    )
    args = _build_parser().parse_args(
        [
            "thesis",
            "--symbol",
            symbol,
            "--quarter",
            quarter,
            "--gold-dir",
            str(gold_dir),
            "--out-dir",
            str(out_dir),
        ]
    )

    with pytest.raises(SystemExit, match="invalid symbol or quarter"):
        thesis_command(args, clients=clients)

    assert [client.call_count for client in clients] == [0, 0]


def test_thesis_normalizes_gold_identity_for_queue_and_document_key(tmp_path: Path) -> None:
    """Gold metadata spacing must not diverge the filename key from the queue key."""
    gold_dir, out_dir = tmp_path / "gold", tmp_path / "thesis"
    gold_path = _write_gold(gold_dir)
    payload = gold_path.read_text(encoding="utf-8").replace(
        '"quarter":"Q3FY25"', '"quarter":"Q3 FY25"'
    )
    gold_path.write_text(payload, encoding="utf-8")
    clients = (
        _FakeClient(
            "model-a",
            "client-a",
            text='{"stance":"constructive","drivers":["demand remains durable"]}',
        ),
        _FakeClient(
            "model-b",
            "client-b",
            text='{"stance":"cautious","drivers":["demand remains fragile"]}',
        ),
    )

    thesis_command(_args(gold_dir, out_dir), clients=clients)

    queue = load_adjudication_queue(out_dir / "adjudication-queue.json")
    assert {entry.quarter for entry in queue.entries} == {_QUARTER}
    assert (out_dir / f"{_SYMBOL}-{_QUARTER}.md").is_file()


def test_corrupt_queue_fails_before_any_batch_model_call(tmp_path: Path) -> None:
    """Batch mode must validate durable state before invoking an external model."""
    gold_dir, out_dir = tmp_path / "gold", tmp_path / "thesis"
    _write_gold(gold_dir)
    queue_path = out_dir / "adjudication-queue.json"
    queue_path.parent.mkdir(parents=True)
    queue_path.write_text("{not-json", encoding="utf-8")
    clients = (
        _FakeClient("model-a", "client-a", text=_GOOD_JSON),
        _FakeClient("model-b", "client-b", text=_GOOD_JSON),
    )

    with pytest.raises(SystemExit, match="invalid adjudication queue"):
        thesis_command(
            _args(gold_dir, out_dir, symbol=None, done_only=True),
            clients=clients,
            queue_path=queue_path,
        )

    assert [client.call_count for client in clients] == [0, 0]
