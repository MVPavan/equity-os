"""Behavior tests for the persistent thesis adjudication queue."""

from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import pytest
from structlog.testing import capture_logs

import fundamentals.api.cli as cli_module
import fundamentals.api.thesis_cli as thesis_cli_module
import fundamentals.thesis.adjudication as adjudication_module
from fundamentals.api.adjudication_cli import (
    adjudication_apply_command,
    adjudication_list_command,
    adjudication_resolve_command,
)
from fundamentals.api.cli import _build_parser
from fundamentals.thesis import (
    AdjudicationStatus,
    Discrepancy,
    DiscrepancyKind,
    discrepancy_id,
    load_adjudication_queue,
    render_persisted_adjudication_sections,
    resolve_adjudication,
    upsert_discrepancies,
)


def _discrepancy() -> Discrepancy:
    """Return one fixed model divergence for queue tests."""
    return Discrepancy(
        section="drivers",
        kind=DiscrepancyKind.DIVERGENT_POINTS,
        model_a_label="model-a",
        model_b_label="model-b",
        model_a_points=("demand is durable",),
        model_b_points=("demand is fragile",),
        detail="models disagree on demand",
    )


def test_queue_appends_once_and_deduplicates_by_stable_content_id(tmp_path: Path) -> None:
    """Rebuilding an identical discrepancy must retain one stable queue entry."""
    queue_path = tmp_path / "adjudication-queue.json"
    created_at = datetime(2026, 8, 23, 12, tzinfo=UTC)

    first = upsert_discrepancies(
        queue_path,
        stock="MTARTECH",
        quarter="Q3FY25",
        discrepancies=(_discrepancy(),),
        now=created_at,
    )
    second = upsert_discrepancies(
        queue_path,
        stock="MTARTECH",
        quarter="Q3FY25",
        discrepancies=(_discrepancy(),),
        now=datetime(2026, 8, 23, 13, tzinfo=UTC),
    )

    assert len(first.entries) == 1
    assert second == load_adjudication_queue(queue_path)
    assert len(second.entries) == 1
    assert second.entries[0].id == (
        "17df0d4966b15b4ae994cd77b55cbea2182db53c29630dadd7a8ba727ac64817"
    )
    assert second.entries[0].created_at == created_at
    assert second.entries[0].updated_at == created_at


def test_discrepancy_id_normalizes_point_order_case_and_whitespace() -> None:
    """All text variance and set-like point ordering must not mint a new ID."""
    first = _discrepancy().model_copy(
        update={
            "section": "Drivers",
            "model_a_label": "Model-A",
            "model_a_points": ("Demand is durable", "  Orders   expand "),
            "detail": "Models DISAGREE on demand",
        }
    )
    second = _discrepancy().model_copy(
        update={
            "section": "  drivers ",
            "model_a_label": " model-a ",
            "model_a_points": ("orders expand", "demand IS durable"),
            "detail": "  models   disagree ON demand ",
        }
    )

    assert discrepancy_id("MTARTECH", "Q3FY25", first) == discrepancy_id(
        "mtartech", "Q3 FY25", second
    )


def test_queue_load_migrates_matching_legacy_id(tmp_path: Path) -> None:
    """A valid pre-normalization ID must migrate once instead of failing integrity."""
    queue_path = tmp_path / "adjudication-queue.json"
    legacy_id = "9b3c96bd270bd058dd4134c8a2d0a60ced5542fe88d8d12fd8a67b673f0d5bb9"
    legacy_discrepancy = _discrepancy().model_copy(
        update={"detail": "  Models   DISAGREE on demand "}
    )
    timestamp = datetime(2026, 8, 23, 12, tzinfo=UTC)
    queue_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "entries": [
                    {
                        "id": legacy_id,
                        "stock": "MTARTECH",
                        "quarter": "Q3FY25",
                        "discrepancy": legacy_discrepancy.model_dump(mode="json"),
                        "status": "OPEN",
                        "note": None,
                        "created_at": timestamp.isoformat(),
                        "updated_at": timestamp.isoformat(),
                        "history": [],
                        "superseded": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with capture_logs() as logs:
        migrated = load_adjudication_queue(queue_path)

    new_id = discrepancy_id("MTARTECH", "Q3FY25", legacy_discrepancy)
    assert new_id != legacy_id
    assert migrated.entries[0].id == new_id
    assert json.loads(queue_path.read_text(encoding="utf-8"))["entries"][0]["id"] == new_id
    assert any(
        event["event"] == "adjudication_id_migrated"
        and event["old_id"] == legacy_id
        and event["new_id"] == new_id
        for event in logs
    )


@pytest.mark.parametrize(
    ("tamper", "message"),
    [
        (lambda payload: payload.update(schema_version=2), "unsupported.*schema_version"),
        (lambda payload: payload.update(schema_version="1"), "schema_version"),
        (
            lambda payload: payload["entries"].append(dict(payload["entries"][0])),
            "duplicate adjudication entry id",
        ),
        (
            lambda payload: payload["entries"][0].update(id="tampered"),
            "entry id mismatch.*tampered",
        ),
        (lambda payload: payload.update(unexpected=True), "extra"),
    ],
    ids=("schema", "schema-type", "duplicate-id", "tampered-id", "unknown-field"),
)
def test_queue_load_rejects_integrity_violations(
    tmp_path: Path,
    tamper,  # noqa: ANN001
    message: str,
) -> None:
    """Persisted queue corruption must fail closed before it can be rewritten."""
    queue_path = tmp_path / "adjudication-queue.json"
    upsert_discrepancies(
        queue_path,
        stock="MTARTECH",
        quarter="Q3FY25",
        discrepancies=(_discrepancy(),),
    )
    payload = json.loads(queue_path.read_text(encoding="utf-8"))
    tamper(payload)
    queue_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_adjudication_queue(queue_path)


def test_queue_directory_path_fails_clearly(tmp_path: Path) -> None:
    """A directory is corrupt queue state, not an absent queue."""
    queue_path = tmp_path / "adjudication-queue.json"
    queue_path.mkdir()

    with pytest.raises(ValueError, match="not a file"):
        load_adjudication_queue(queue_path)


def test_resolve_updates_status_note_and_timestamp(tmp_path: Path) -> None:
    """Resolving an OPEN entry must durably record the chosen side and human note."""
    queue_path = tmp_path / "adjudication-queue.json"
    created_at = datetime(2026, 8, 23, 12, tzinfo=UTC)
    queue = upsert_discrepancies(
        queue_path,
        stock="MTARTECH",
        quarter="Q3FY25",
        discrepancies=(_discrepancy(),),
        now=created_at,
    )
    resolved_at = datetime(2026, 8, 23, 14, tzinfo=UTC)

    resolved = resolve_adjudication(
        queue_path,
        entry_id=queue.entries[0].id,
        status=AdjudicationStatus.ACCEPTED_B,
        note="Near-term order timing is the better-supported view.",
        now=resolved_at,
    )

    entry = resolved.entries[0]
    assert entry.status is AdjudicationStatus.ACCEPTED_B
    assert entry.note == "Near-term order timing is the better-supported view."
    assert entry.created_at == created_at
    assert entry.updated_at == resolved_at
    assert load_adjudication_queue(queue_path) == resolved


def test_reresolve_preserves_note_and_appends_resolution_history(tmp_path: Path) -> None:
    """A later decision must retain the earlier decision and its human rationale."""
    queue_path = tmp_path / "adjudication-queue.json"
    queue = upsert_discrepancies(
        queue_path,
        stock="MTARTECH",
        quarter="Q3FY25",
        discrepancies=(_discrepancy(),),
    )
    first_at = datetime(2026, 8, 23, 13, tzinfo=UTC)
    second_at = datetime(2026, 8, 23, 14, tzinfo=UTC)
    resolve_adjudication(
        queue_path,
        entry_id=queue.entries[0].id,
        status=AdjudicationStatus.ACCEPTED_A,
        note="First review accepted the durable-demand view.",
        now=first_at,
    )

    resolved = resolve_adjudication(
        queue_path,
        entry_id=queue.entries[0].id,
        status=AdjudicationStatus.MERGED,
        now=second_at,
    )

    entry = resolved.entries[0]
    assert entry.note == "First review accepted the durable-demand view."
    assert [(event.status, event.note, event.timestamp) for event in entry.history] == [
        (
            AdjudicationStatus.ACCEPTED_A,
            "First review accepted the durable-demand view.",
            first_at,
        ),
        (AdjudicationStatus.MERGED, "First review accepted the durable-demand view.", second_at),
    ]


def test_reresolve_backfills_legacy_current_resolution_before_new_event(tmp_path: Path) -> None:
    """A resolved legacy row with no history must retain its current decision first."""
    queue_path = tmp_path / "adjudication-queue.json"
    queue = upsert_discrepancies(
        queue_path,
        stock="MTARTECH",
        quarter="Q3FY25",
        discrepancies=(_discrepancy(),),
    )
    first_at = datetime(2026, 8, 23, 13, tzinfo=UTC)
    second_at = datetime(2026, 8, 23, 14, tzinfo=UTC)
    resolve_adjudication(
        queue_path,
        entry_id=queue.entries[0].id,
        status=AdjudicationStatus.ACCEPTED_A,
        note="Legacy analyst decision.",
        now=first_at,
    )
    payload = json.loads(queue_path.read_text(encoding="utf-8"))
    payload["entries"][0].pop("history")
    queue_path.write_text(json.dumps(payload), encoding="utf-8")

    resolved = resolve_adjudication(
        queue_path,
        entry_id=queue.entries[0].id,
        status=AdjudicationStatus.MERGED,
        note="Merged after fresh review.",
        now=second_at,
    )

    history = [(event.status, event.note, event.timestamp) for event in resolved.entries[0].history]
    assert history == [
        (AdjudicationStatus.ACCEPTED_A, "Legacy analyst decision.", first_at),
        (AdjudicationStatus.MERGED, "Merged after fresh review.", second_at),
    ]


def test_queue_mutators_hold_one_lock_across_read_modify_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An interleaved resolve and upsert must both survive in the final queue."""
    queue_path = tmp_path / "adjudication-queue.json"
    original = upsert_discrepancies(
        queue_path,
        stock="MTARTECH",
        quarter="Q3FY25",
        discrepancies=(_discrepancy(),),
    )
    added = _discrepancy().model_copy(
        update={
            "model_a_points": ("exports accelerate",),
            "model_b_points": ("exports slow",),
            "detail": "models disagree on exports",
        }
    )
    write_barrier = threading.Barrier(2)
    original_write = adjudication_module._write_adjudication_queue

    def interleaved_write(path, queue) -> None:  # noqa: ANN001
        try:
            write_barrier.wait(timeout=0.1)
        except threading.BrokenBarrierError:
            pass
        original_write(path, queue)

    monkeypatch.setattr(adjudication_module, "_write_adjudication_queue", interleaved_write)
    with ThreadPoolExecutor(max_workers=2) as executor:
        resolve = executor.submit(
            resolve_adjudication,
            queue_path,
            entry_id=original.entries[0].id,
            status=AdjudicationStatus.ACCEPTED_A,
        )
        upsert = executor.submit(
            upsert_discrepancies,
            queue_path,
            stock="MTARTECH",
            quarter="Q3FY25",
            discrepancies=(_discrepancy(), added),
        )
        resolve.result()
        upsert.result()

    final = load_adjudication_queue(queue_path)
    assert len(final.entries) == 2
    assert next(entry for entry in final.entries if entry.id == original.entries[0].id).status is (
        AdjudicationStatus.ACCEPTED_A
    )


def test_absent_resolved_entry_is_rendered_as_superseded(tmp_path: Path) -> None:
    """A decision over an old divergence must not be presented as current adjudication."""
    queue_path = tmp_path / "adjudication-queue.json"
    queue = upsert_discrepancies(
        queue_path,
        stock="MTARTECH",
        quarter="Q3FY25",
        discrepancies=(_discrepancy(),),
    )
    queue = resolve_adjudication(
        queue_path,
        entry_id=queue.entries[0].id,
        status=AdjudicationStatus.ACCEPTED_A,
    )

    rebuilt = upsert_discrepancies(
        queue_path,
        stock="MTARTECH",
        quarter="Q3FY25",
        discrepancies=(),
    )
    rendered = render_persisted_adjudication_sections(rebuilt.entries)
    adjudicated, superseded = rendered.split("### 4d. Superseded")

    assert rebuilt.entries[0].superseded is True
    assert rebuilt.entries[0].id not in adjudicated
    assert rebuilt.entries[0].id in superseded
    args = _build_parser().parse_args(["adjudicate", "list", "--symbol", "MTARTECH"])
    assert "SUPERSEDED (ACCEPTED_A)" in adjudication_list_command(args, queue_path=queue_path)


def test_adjudicate_list_filters_and_renders_one_line_summary(tmp_path: Path) -> None:
    """The list CLI must expose actionable OPEN queue rows with their stable IDs."""
    queue_path = tmp_path / "adjudication-queue.json"
    queue = upsert_discrepancies(
        queue_path,
        stock="MTARTECH",
        quarter="Q3FY25",
        discrepancies=(_discrepancy(),),
        now=datetime(2026, 8, 23, 12, tzinfo=UTC),
    )
    args = _build_parser().parse_args(
        ["adjudicate", "list", "--symbol", "MTARTECH", "--status", "OPEN"]
    )

    table = adjudication_list_command(args, queue_path=queue_path)

    assert "| ID | Stock | Section | Divergence | Status |" in table
    assert queue.entries[0].id in table
    assert "models disagree on demand" in table
    assert "OPEN" in table


def test_adjudicate_resolve_maps_cli_choice_to_durable_status(tmp_path: Path) -> None:
    """The resolve CLI must translate its short token and persist the note."""
    queue_path = tmp_path / "adjudication-queue.json"
    queue = upsert_discrepancies(
        queue_path,
        stock="MTARTECH",
        quarter="Q3FY25",
        discrepancies=(_discrepancy(),),
        now=datetime(2026, 8, 23, 12, tzinfo=UTC),
    )
    args = _build_parser().parse_args(
        [
            "adjudicate",
            "resolve",
            "--id",
            queue.entries[0].id,
            "--accept",
            "merged",
            "--note",
            "Both capture different time horizons.",
        ]
    )

    entry = adjudication_resolve_command(
        args,
        queue_path=queue_path,
        now=datetime(2026, 8, 23, 13, tzinfo=UTC),
    )

    assert entry.status is AdjudicationStatus.MERGED
    assert entry.note == "Both capture different time horizons."
    assert load_adjudication_queue(queue_path).entries == (entry,)


def test_adjudicate_apply_folds_target_resolutions_without_changing_facts(tmp_path: Path) -> None:
    """Apply must update only the review sections and derive the target's OPEN flag."""
    thesis_dir = tmp_path / "thesis"
    thesis_dir.mkdir()
    queue_path = thesis_dir / "adjudication-queue.json"
    queue = upsert_discrepancies(
        queue_path,
        stock="MTARTECH",
        quarter="Q3FY25",
        discrepancies=(_discrepancy(),),
        now=datetime(2026, 8, 23, 12, tzinfo=UTC),
    )
    upsert_discrepancies(
        queue_path,
        stock="TITAN",
        quarter="Q3FY25",
        discrepancies=(
            _discrepancy().model_copy(update={"detail": "TITAN-only jewellery divergence"}),
        ),
        now=datetime(2026, 8, 23, 12, tzinfo=UTC),
    )
    resolve_adjudication(
        queue_path,
        entry_id=queue.entries[0].id,
        status=AdjudicationStatus.ACCEPTED_B,
        note="Accepted after comparing the source-backed narrative.",
        now=datetime(2026, 8, 23, 13, tzinfo=UTC),
    )
    document_path = thesis_dir / "MTARTECH-Q3FY25.md"
    document_path.write_text(
        "# MTARTECH thesis\n\n"
        "- Human adjudication required: **YES**\n\n"
        '<!-- thesis-adjudication-manifest: {"quarter":"Q3FY25","stock":"MTARTECH",'
        '"unsourced_claims":false} -->\n\n'
        "## 1. Validated sourced facts\n\n"
        "Revenue from operations: 174.455 INR crore\n\n"
        "### 4b. Discrepancy / adjudication queue\n\n"
        "old queue rendering\n\n"
        "## 5. Model-run log\n\n"
        "model-a: ok\n",
        encoding="utf-8",
    )
    args = _build_parser().parse_args(
        ["adjudicate", "apply", "--symbol", "MTARTECH", "--quarter", "Q3FY25"]
    )

    written = adjudication_apply_command(
        args,
        queue_path=queue_path,
        thesis_dir=thesis_dir,
    )

    rendered = written.read_text(encoding="utf-8")
    assert "Revenue from operations: 174.455 INR crore" in rendered
    assert "Human adjudication required: **NO**" in rendered
    assert "### 4c. Adjudicated" in rendered
    assert "Accepted model-b" in rendered
    assert "Accepted after comparing the source-backed narrative." in rendered
    assert "TITAN-only jewellery divergence" not in rendered
    assert "old queue rendering" not in rendered
    assert len(load_adjudication_queue(queue_path).entries) == 2


def test_adjudicate_apply_rejects_symbol_path_traversal(tmp_path: Path) -> None:
    """A symbol must never let apply read or overwrite a file outside the thesis directory."""
    thesis_dir = tmp_path / "thesis"
    thesis_dir.mkdir()
    outside = tmp_path / "ESCAPE-Q3FY25.md"
    original = "outside document must remain unchanged\n"
    outside.write_text(original, encoding="utf-8")
    args = _build_parser().parse_args(
        ["adjudicate", "apply", "--symbol", "../escape", "--quarter", "Q3FY25"]
    )

    with pytest.raises(SystemExit, match="invalid symbol or quarter"):
        adjudication_apply_command(
            args,
            queue_path=thesis_dir / "adjudication-queue.json",
            thesis_dir=thesis_dir,
        )

    assert outside.read_text(encoding="utf-8") == original


def test_adjudicate_apply_fails_closed_when_queue_is_missing(tmp_path: Path) -> None:
    """Apply must not erase visible review work when its durable queue is unavailable."""
    thesis_dir = tmp_path / "thesis"
    thesis_dir.mkdir()
    document_path = thesis_dir / "MTARTECH-Q3FY25.md"
    original = (
        "- Human adjudication required: **YES**\n\n"
        "### 4b. Discrepancy / adjudication queue\n\n"
        "visible unresolved divergence\n\n"
        "## 5. Model-run log\n"
    )
    document_path.write_text(original, encoding="utf-8")
    args = _build_parser().parse_args(
        ["adjudicate", "apply", "--symbol", "MTARTECH", "--quarter", "Q3FY25"]
    )

    with pytest.raises(SystemExit, match="queue not found"):
        adjudication_apply_command(
            args,
            queue_path=thesis_dir / "adjudication-queue.json",
            thesis_dir=thesis_dir,
        )

    assert document_path.read_text(encoding="utf-8") == original


def test_adjudicate_apply_fails_closed_when_queue_has_no_matching_entries(
    tmp_path: Path,
) -> None:
    """A key mismatch must never erase the document's visible divergence section."""
    thesis_dir = tmp_path / "thesis"
    thesis_dir.mkdir()
    queue_path = thesis_dir / "adjudication-queue.json"
    upsert_discrepancies(
        queue_path,
        stock="TITAN",
        quarter="Q3FY25",
        discrepancies=(_discrepancy(),),
        now=datetime(2026, 8, 23, 12, tzinfo=UTC),
    )
    document_path = thesis_dir / "MTARTECH-Q3FY25.md"
    original = (
        "- Human adjudication required: **YES**\n\n"
        "### 4b. Discrepancy / adjudication queue\n\n"
        "visible unresolved divergence\n\n"
        "## 5. Model-run log\n"
    )
    document_path.write_text(original, encoding="utf-8")
    args = _build_parser().parse_args(
        ["adjudicate", "apply", "--symbol", "MTARTECH", "--quarter", "Q3FY25"]
    )

    with pytest.raises(SystemExit, match="no adjudication entries match"):
        adjudication_apply_command(args, queue_path=queue_path, thesis_dir=thesis_dir)

    assert document_path.read_bytes() == original.encode()


def test_adjudicate_apply_requires_unique_splice_anchors(tmp_path: Path) -> None:
    """Duplicated structural headings must abort instead of selecting one by order."""
    thesis_dir = tmp_path / "thesis"
    thesis_dir.mkdir()
    queue_path = thesis_dir / "adjudication-queue.json"
    upsert_discrepancies(
        queue_path,
        stock="MTARTECH",
        quarter="Q3FY25",
        discrepancies=(_discrepancy(),),
    )
    document_path = thesis_dir / "MTARTECH-Q3FY25.md"
    original = (
        "- Human adjudication required: **YES**\n"
        '<!-- thesis-adjudication-manifest: {"quarter":"Q3FY25","stock":"MTARTECH",'
        '"unsourced_claims":false} -->\n'
        "### 4b. Discrepancy / adjudication queue\n"
        "first\n"
        "### 4b. Discrepancy / adjudication queue\n"
        "forged duplicate\n"
        "## 5. Model-run log\n"
    )
    document_path.write_text(original, encoding="utf-8")
    args = _build_parser().parse_args(
        ["adjudicate", "apply", "--symbol", "MTARTECH", "--quarter", "Q3FY25"]
    )

    with pytest.raises(SystemExit, match="exactly one"):
        adjudication_apply_command(args, queue_path=queue_path, thesis_dir=thesis_dir)

    assert document_path.read_text(encoding="utf-8") == original


def test_adjudicate_list_converts_corrupt_queue_to_clean_exit(tmp_path: Path) -> None:
    """CLI users should see a bounded queue error rather than a validation traceback."""
    queue_path = tmp_path / "adjudication-queue.json"
    queue_path.write_text("{not-json", encoding="utf-8")
    args = _build_parser().parse_args(["adjudicate", "list"])

    with pytest.raises(SystemExit, match="invalid adjudication queue"):
        adjudication_list_command(args, queue_path=queue_path)


def test_adjudicate_main_dispatches_list(
    tmp_path: Path,
    monkeypatch,
    capsys,  # noqa: ANN001
) -> None:
    """The public CLI entry point must route the nested adjudication action."""
    thesis_dir = tmp_path / "thesis"
    queue_path = thesis_dir / "adjudication-queue.json"
    queue = upsert_discrepancies(
        queue_path,
        stock="MTARTECH",
        quarter="Q3FY25",
        discrepancies=(_discrepancy(),),
        now=datetime(2026, 8, 23, 12, tzinfo=UTC),
    )
    monkeypatch.setattr(thesis_cli_module, "_DEFAULT_THESIS_DIR", thesis_dir)

    exit_code = cli_module.main(["adjudicate", "list", "--status", "OPEN"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert queue.entries[0].id in captured.out
