"""The ``screener-financials`` acquisition contract and its refusals.

Everything here is about what reaches disk and what exit code the caller sees:
retained evidence, no-clobber, a sweep cut short, and the structural
ambiguities this adapter refuses rather than resolving by document order.

The transport seam and the synthetic bodies live in
:mod:`screener_financials_support`, shared with
:mod:`test_screener_financials`.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from screener_financials_support import (
    _DUPLICATE_COLUMN_SECTION,
    _DUPLICATE_EXPANDER_SECTION,
    _DUPLICATE_PARENT_ROW_SECTION,
    _PAGE,
    _SCHEDULES,
    _SESSION_ENV,
    _SESSION_TOKEN,
    _balance_sheet_table,
    _family,
    _page_with,
    _run,
    _schedule_kwargs,
    _serve,
    _watchlist,
)

from fundamentals.api.cli import main
from fundamentals.api.screener_cli_dispatch import EXIT_BASIS_UNAVAILABLE, EXIT_REFUSED
from fundamentals.api.screener_financials_cli import (
    FAILURES_FILENAME,
    META_FILENAME,
    PAGE_RAW_FILENAME,
    SCHEDULES_DIRNAME,
)
from fundamentals.ingest.screener_financials import (
    ALL_SECTIONS,
    _page_row,
)
from fundamentals.ingest.screener_financials_models import (
    AmbiguousStructureError,
    ReconciliationStatus,
    ScheduleBodyError,
    ScheduleReconciliationError,
    ScheduleStrategy,
    Section,
    reconciliation_is_proven,
)
from fundamentals.ingest.screener_financials_schedules import (
    read_schedule,
    reconciliation_tolerance,
)
from fundamentals.ingest.screener_financials_tables import read_section, schedule_parents
from fundamentals.ingest.screener_session import ScreenerSessionSource
from fundamentals.ingest.screener_session_page import parse_document

# --------------------------------------------------------------------------
# The acquisition contract.
# --------------------------------------------------------------------------


def test_the_command_retains_the_page_and_every_schedule_body_beside_its_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An artifact is only trustworthy with the documents it was derived from beside it.

    Every schedule body is retained, not just the page: a family that fails the
    reconciliation gate is exactly the body someone will need to look at.
    """
    _serve(monkeypatch)
    out_dir = tmp_path / "out"
    exit_code = main(
        [
            "screener-financials",
            "--stock",
            "FIXTURECO",
            "--out",
            str(out_dir),
            "--config",
            str(_watchlist(tmp_path)),
        ]
    )
    assert exit_code == 0
    metadata = json.loads((out_dir / META_FILENAME).read_text(encoding="utf-8"))
    assert metadata["complete"] is True
    assert metadata["basis"] == "consolidated"
    assert (out_dir / PAGE_RAW_FILENAME).read_bytes() == _PAGE.read_bytes()
    retained = sorted(path.name for path in (out_dir / SCHEDULES_DIRNAME).iterdir())
    assert retained == [
        "balance-sheet__borrowings.raw.json",
        "balance-sheet__fixed-assets.raw.json",
        "balance-sheet__other-liabilities.raw.json",
        "cash-flow__cash-from-investing-activity.raw.json",
        "profit-loss__sales.raw.json",
        "quarters__expenses.raw.json",
        "quarters__net-profit.raw.json",
        "quarters__other-income.raw.json",
        "quarters__sales.raw.json",
    ]
    for section in ALL_SECTIONS:
        assert (out_dir / f"section_{section.value}.json").exists()
    summary = capsys.readouterr().out
    assert "balance-sheet/Borrowings\tflat_sum\treconciled" in summary
    assert "quarters/Sales\tall_percent\tnot_applicable" in summary


def test_an_unverified_identifier_refuses_before_any_request_is_made(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unverified id would attach the owner's cookie to the wrong company's URL."""
    requested: list[str] = []

    def unexpected(*args: object, **kwargs: object) -> tuple[int, bytes]:
        requested.append(repr(args))
        raise AssertionError("no request may be made for an unverified identifier")

    monkeypatch.setenv(_SESSION_ENV, _SESSION_TOKEN)
    monkeypatch.setattr(ScreenerSessionSource, "_fetch_bytes", unexpected)
    with pytest.raises(SystemExit) as raised:
        main(
            [
                "screener-financials",
                "--stock",
                "FIXTURECO",
                "--out",
                str(tmp_path / "out"),
                "--config",
                str(_watchlist(tmp_path, flagged='"screener_company_id"')),
            ]
        )
    assert "not verified" in str(raised.value)
    assert requested == []


def test_the_command_refuses_to_overwrite_an_existing_artifact_before_fetching(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Refusing after the sweep would spend sixteen rate-limited requests to discard them."""
    requested = _serve(monkeypatch)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / META_FILENAME).write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit) as raised:
        main(
            [
                "screener-financials",
                "--stock",
                "FIXTURECO",
                "--out",
                str(out_dir),
                "--config",
                str(_watchlist(tmp_path)),
            ]
        )
    assert "refusing to overwrite" in str(raised.value)
    assert requested == []


def test_a_rate_limit_mid_sweep_keeps_what_was_read_and_marks_the_artifact_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A partial sweep must never read as a complete acquisition.

    Screener rate-limits at around forty requests and one company costs sixteen,
    so this is an expected outcome. The sections already read stay, the bodies
    already retained stay, and what is missing is named rather than implied — and
    the exit code is non-zero so a watchlist loop does not treat it as done.
    """
    _serve(monkeypatch, rate_limit_after=3)
    out_dir = tmp_path / "out"
    exit_code = main(
        [
            "screener-financials",
            "--stock",
            "FIXTURECO",
            "--out",
            str(out_dir),
            "--config",
            str(_watchlist(tmp_path)),
        ]
    )
    assert exit_code == EXIT_REFUSED
    metadata = json.loads((out_dir / META_FILENAME).read_text(encoding="utf-8"))
    assert metadata["complete"] is False
    assert "rate-limited after 3 of 9 schedules" in metadata["incomplete_reason"]
    assert len(metadata["schedule_families_fetched"]) == 3
    assert len(metadata["schedule_families_requested"]) == 9
    assert (out_dir / PAGE_RAW_FILENAME).exists()
    assert len(list((out_dir / SCHEDULES_DIRNAME).iterdir())) == 3
    for section in ALL_SECTIONS:
        assert (out_dir / f"section_{section.value}.json").exists()
    assert "INCOMPLETE" in capsys.readouterr().out


def test_a_basis_the_company_does_not_publish_writes_nothing_and_exits_three(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Parsing must not proceed on a page that never carried the requested basis.

    The degenerate consolidated shell of a standalone-only company is HTTP 200
    with empty tables; reading it would publish an empty artifact as a fact
    about the issuer.
    """
    _serve(monkeypatch)
    out_dir = tmp_path / "out"
    exit_code = main(
        [
            "screener-financials",
            "--stock",
            "SOLOCO",
            "--out",
            str(out_dir),
            "--config",
            str(_watchlist(tmp_path)),
        ]
    )
    assert exit_code == EXIT_BASIS_UNAVAILABLE
    assert not (out_dir / META_FILENAME).exists()


def test_a_flat_sum_family_with_no_readable_page_value_is_not_comparable() -> None:
    """Aligned periods but nothing on the page to compare against is not agreement.

    Distinct from an unrecognised shape: the family is summable and its periods
    line up, there is simply no page number. Calling that reconciled would let
    the basis gate be satisfied by a row the page never published.
    """
    table = _balance_sheet_table()
    family = read_schedule(
        json.dumps({"Long term Borrowings": {"Mar 2025": "400"}}).encode("utf-8"),
        page_row=None,
        **_schedule_kwargs(table),
    )
    assert family.strategy is ScheduleStrategy.FLAT_SUM
    assert family.unaligned_periods == ()
    assert family.reconciliation is ReconciliationStatus.NOT_COMPARABLE


def test_the_reader_itself_raises_a_typed_error_on_a_failed_reconciliation() -> None:
    """The recorded failure and the typed refusal are the same event, not alternatives.

    The sweep catches this so the response reaches disk; the exception is still
    the contract, so anything calling the reader directly fails closed.
    """
    table = _balance_sheet_table()
    page = next(row for row in table.rows if row.label == "Borrowings")
    with pytest.raises(ScheduleReconciliationError):
        read_schedule(
            (_SCHEDULES / "balance-sheet__borrowings.wrong-basis.json").read_bytes(),
            page_row=page,
            **_schedule_kwargs(table),
        )


# --------------------------------------------------------------------------
# Fix round: shape registry, ambiguity, tolerance, evidence.
# --------------------------------------------------------------------------


def test_a_flat_sum_family_that_gains_one_percent_row_is_refused_not_exempted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """This is the escape hatch the shape guess left open.

    Under a rule that reads "any percent row means analysis", a wrong-basis
    amount breakdown carrying one informational rate would be reclassified as
    exempt, skip the reconciliation gate entirely, and exit zero — the numbers
    silently wrong. An unregistered mixed shape must instead fail closed.
    """
    run = _run(monkeypatch, swap=("balance-sheet__borrowings", ".gains-percent"))
    family = _family(run, Section.BALANCE_SHEET, "Borrowings")
    assert family.strategy is ScheduleStrategy.UNVERIFIED
    assert family.reconciliation is ReconciliationStatus.UNVERIFIED
    assert family.reconciliation is not ReconciliationStatus.NOT_APPLICABLE
    assert "no registered signature" in family.reconciliation_note
    assert run.artifact.metadata.verified is False
    assert "balance-sheet/Borrowings" in run.artifact.metadata.schedule_families_unverified


def test_a_registered_mixed_family_carrying_an_unknown_row_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A registered exemption covers a recorded shape, not a family name forever.

    Companies legitimately carry different subsets of a family's rows, so the
    body must be a subset of the signature — but a label nobody has seen means
    the family may have changed what it decomposes into, and inheriting the old
    exemption would hide that.
    """
    run = _run(monkeypatch, swap=("balance-sheet__fixed-assets", ".extra-row"))
    family = _family(run, Section.BALANCE_SHEET, "Fixed Assets")
    assert family.strategy is ScheduleStrategy.UNVERIFIED
    assert family.reconciliation is ReconciliationStatus.UNVERIFIED
    assert "Right of Use Assets" in family.reconciliation_note


def test_a_single_whole_crore_addend_must_match_its_parent_exactly() -> None:
    """With one sub-row, the sub-row and the parent are the same underlying number.

    Two roundings of one number are equal, so when that single addend is itself
    shown as a whole crore the two must agree exactly. The general ``(n + 1)/2``
    band would admit 1,001 against 1,000 — the size of error this gate exists to
    catch on a small company, and single-row families are real (NETWEB and HFCL
    quarterly Other Income).
    """
    assert reconciliation_tolerance(("400",)) == Decimal("0")
    table = _balance_sheet_table()
    page = next(row for row in table.rows if row.label == "Borrowings")
    with pytest.raises(ScheduleReconciliationError):
        read_schedule(
            json.dumps({"Long term Borrowings": {"Mar 2025": "1,001", "Mar 2026": "1,200"}}).encode(
                "utf-8"
            ),
            page_row=page,
            **_schedule_kwargs(table),
        )


def test_a_single_full_precision_addend_may_differ_by_the_pages_own_rounding() -> None:
    """The API publishes some sub-rows at full precision while the page rounds.

    NETWEB's quarterly Other Income returns ``0.42`` where the page shows ``0``,
    and HFCL's returns ``46.95`` where the page shows ``47``. Only the page value
    is rounded there, so the band is its half-unit — demanding exact equality
    would refuse two live companies' correct data.
    """
    assert reconciliation_tolerance(("0.42",)) == Decimal("0.5")
    table = _balance_sheet_table()
    page = next(row for row in table.rows if row.label == "Borrowings")
    family = read_schedule(
        json.dumps({"Long term Borrowings": {"Mar 2025": "1000.49", "Mar 2026": "1200.00"}}).encode(
            "utf-8"
        ),
        page_row=page,
        **_schedule_kwargs(table),
    )
    assert family.reconciliation is ReconciliationStatus.RECONCILED


def test_a_sub_row_that_is_itself_expandable_is_not_read_as_a_period() -> None:
    """``isExpandable`` carries a nested ``showSchedule`` call, and its value is a string.

    That makes it read exactly like a period labelled "isExpandable" — which is
    what happened until the alignment check began refusing sub-row periods the
    page does not carry, on TITAN and HFCL ``Trade receivables``. The nested call
    is recorded rather than discarded.
    """
    table = _balance_sheet_table()
    page = next(row for row in table.rows if row.label == "Borrowings")
    family = read_schedule(
        json.dumps(
            {
                "Long term Borrowings": {
                    "Mar 2025": "1,000",
                    "Mar 2026": "1,200",
                    "isExpandable": 'Company.showSchedule("Long term Borrowings", "x", this)',
                }
            }
        ).encode("utf-8"),
        page_row=page,
        **_schedule_kwargs(table),
    )
    assert family.unaligned_periods == ()
    assert family.reconciliation is ReconciliationStatus.RECONCILED
    assert "showSchedule" in (family.sub_rows[0].nested_schedule_call or "")


@pytest.mark.parametrize(
    ("addends", "expected"),
    [(2, Decimal("1.5")), (5, Decimal("3"))],
)
def test_the_rounding_band_is_the_arithmetic_of_independent_rounding(
    addends: int, expected: Decimal
) -> None:
    """``(n + 1) / 2``: each of n addends and the total is rounded to a whole crore."""
    assert reconciliation_tolerance(("100",) * addends) == expected


@pytest.mark.parametrize(
    ("addends", "offset", "admitted"),
    [(2, "1.5", True), (2, "2", False), (5, "3", True), (5, "3.5", False)],
)
def test_the_rounding_band_holds_exactly_at_its_boundary(
    addends: int, offset: str, admitted: bool
) -> None:
    """A boundary that drifts is a gate that drifts; pin both sides of it."""
    table = _balance_sheet_table()
    page = next(row for row in table.rows if row.label == "Borrowings")
    share = (Decimal("1000") + Decimal(offset)) / addends
    body = {f"Part {index}": {"Mar 2025": str(share)} for index in range(addends)}
    call = lambda: read_schedule(  # noqa: E731
        json.dumps(body).encode("utf-8"), page_row=page, **_schedule_kwargs(table)
    )
    if admitted:
        assert call().reconciliation is ReconciliationStatus.RECONCILED
    else:
        with pytest.raises(ScheduleReconciliationError):
            call()


def test_two_columns_with_the_same_label_are_refused_not_collapsed() -> None:
    """A schedule addresses its values by period label, so a repeat is a wrong binding.

    Keeping the last column silently would let a sub-row reconcile against a
    column it never described — and the duplicate is exactly where a stale or
    injected value would sit.
    """
    with pytest.raises(AmbiguousStructureError) as raised:
        read_section(
            parse_document(_page_with(_DUPLICATE_COLUMN_SECTION)),
            Section.BALANCE_SHEET,
            source_id="screener-subscriber",
            file_sha256="0" * 64,
            retrieved_at=datetime(2026, 8, 26, tzinfo=UTC),
        )
    assert "Mar 2026" in str(raised.value)


def test_two_expanders_for_one_family_are_refused_not_deduplicated() -> None:
    """Nothing says two buttons naming one family describe the same row.

    Deduplicating picks one by document order and drops the other without a
    word, which is indistinguishable from the page having changed underneath.
    """
    with pytest.raises(AmbiguousStructureError) as raised:
        schedule_parents(parse_document(_page_with(_DUPLICATE_EXPANDER_SECTION)))
    assert "balance-sheet/Borrowings" in str(raised.value)


def test_two_rows_claiming_one_family_are_refused_not_resolved_by_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reconciliation's reference row must not be chosen by document order.

    Taking the first match would compare the schedule against whichever row the
    parser reached first, while the other — carrying different numbers — sits
    unmentioned in the same artifact.
    """
    del monkeypatch
    table = read_section(
        parse_document(_page_with(_DUPLICATE_PARENT_ROW_SECTION)),
        Section.BALANCE_SHEET,
        source_id="screener-subscriber",
        file_sha256="0" * 64,
        retrieved_at=datetime(2026, 8, 26, tzinfo=UTC),
    )
    with pytest.raises(AmbiguousStructureError) as raised:
        _page_row(table, "Borrowings")
    assert "Borrowings" in str(raised.value)


def test_a_refused_schedule_leaves_its_response_and_a_failure_record_on_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The body that fails the gate is the most valuable thing the run produced.

    It is what a wrong basis actually looks like. Letting the refusal escape
    before publishing would discard exactly that evidence and leave the operator
    with a traceback and nothing to inspect.
    """
    _serve(monkeypatch, swap=("balance-sheet__borrowings", ".wrong-basis"))
    out_dir = tmp_path / "out"
    exit_code = main(
        [
            "screener-financials",
            "--stock",
            "FIXTURECO",
            "--out",
            str(out_dir),
            "--config",
            str(_watchlist(tmp_path)),
        ]
    )
    assert exit_code == EXIT_REFUSED
    retained = out_dir / SCHEDULES_DIRNAME / "balance-sheet__borrowings.raw.json"
    assert retained.exists()
    assert (
        retained.read_bytes()
        == (_SCHEDULES / "balance-sheet__borrowings.wrong-basis.json").read_bytes()
    )
    failures = json.loads((out_dir / FAILURES_FILENAME).read_text(encoding="utf-8"))
    assert [item["parent"] for item in failures] == ["Borrowings"]
    assert failures[0]["refusal"] == "ScheduleReconciliationError"
    assert failures[0]["body_sha256"] == hashlib.sha256(retained.read_bytes()).hexdigest()
    metadata = json.loads((out_dir / META_FILENAME).read_text(encoding="utf-8"))
    assert metadata["verified"] is False
    assert metadata["schedule_families_refused"] == ["balance-sheet/Borrowings"]
    assert "refused_schedule" in capsys.readouterr().out


def test_the_growth_section_summary_counts_what_it_actually_holds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The growth section has ranges-tables, not period rows.

    Counting its (always empty) row list printed a line of zeros that reads as
    "this section came back empty" — the opposite of what it means.
    """
    _serve(monkeypatch)
    main(
        [
            "screener-financials",
            "--stock",
            "FIXTURECO",
            "--out",
            str(tmp_path / "out"),
            "--config",
            str(_watchlist(tmp_path)),
        ]
    )
    growth = next(
        line for line in capsys.readouterr().out.splitlines() if line.startswith("growth\t")
    )
    assert growth.split("\t")[2:4] == ["4", "16"]


# A balance sheet whose own column label collides with a reserved schedule key.
_RESERVED_COLLISION_SECTION = """
  <table class="data-table">
    <thead><tr><th class="text"></th>
      <th data-date-key="2025-03-31">Mar 2025</th>
      <th data-date-key="2026-03-31">isExpandable</th></tr></thead>
    <tbody><tr><td class="text"><button
      onclick="Company.showSchedule('Borrowings', 'balance-sheet', this)"
      >Borrowings&nbsp;+</button></td><td>1,000</td><td>1,200</td></tr></tbody>
  </table>"""


def test_a_page_column_named_like_a_reserved_key_is_refused() -> None:
    """Reserved keys are skipped before period matching, so a collision loses a column.

    A column genuinely labelled ``isExpandable`` would have its values dropped
    as metadata while the family reconciled on the columns that remained —
    reported as RECONCILED with a real period silently unread.
    """
    table = read_section(
        parse_document(_page_with(_RESERVED_COLLISION_SECTION)),
        Section.BALANCE_SHEET,
        source_id="screener-subscriber",
        file_sha256="0" * 64,
        retrieved_at=datetime(2026, 8, 26, tzinfo=UTC),
    )
    page = next(row for row in table.rows if row.label == "Borrowings")
    with pytest.raises(AmbiguousStructureError) as raised:
        read_schedule(
            (_SCHEDULES / "balance-sheet__borrowings.json").read_bytes(),
            page_row=page,
            **_schedule_kwargs(table),
        )
    assert "isExpandable" in str(raised.value)


def test_a_reserved_key_carrying_the_wrong_type_is_refused() -> None:
    """A reserved key is skipped rather than read, so a changed type would vanish.

    ``setAttributes`` carries an attribute map; if it arrives as a bare string
    the row's emphasis marking can no longer be read, and silently treating it
    as unmarked could turn a subtotal row into an addend.
    """
    table = _balance_sheet_table()
    page = next(row for row in table.rows if row.label == "Borrowings")
    with pytest.raises(ScheduleBodyError) as raised:
        read_schedule(
            (_SCHEDULES / "balance-sheet__borrowings.mistyped-reserved.json").read_bytes(),
            page_row=page,
            **_schedule_kwargs(table),
        )
    assert "setAttributes" in str(raised.value)


def test_reconciliation_is_proven_admits_only_the_two_positive_outcomes() -> None:
    """One predicate decides both the artifact flag and the exit code.

    They were computed separately once, and NOT_COMPARABLE was in the exit
    code's set but not the artifact's — so a run the command called a failure
    wrote ``verified: true`` to disk.
    """
    assert reconciliation_is_proven(ReconciliationStatus.RECONCILED)
    assert reconciliation_is_proven(ReconciliationStatus.NOT_APPLICABLE)
    assert not reconciliation_is_proven(ReconciliationStatus.NOT_COMPARABLE)
    assert not reconciliation_is_proven(ReconciliationStatus.UNVERIFIED)
    assert not reconciliation_is_proven(ReconciliationStatus.UNVERIFIED_EMPTY)


@pytest.mark.parametrize(
    ("swap", "expected_exit"),
    [
        (None, 0),
        (("balance-sheet__fixed-assets", ".allowed-subset-only"), EXIT_REFUSED),
        (("profit-loss__sales", ".empty"), EXIT_REFUSED),
        (("balance-sheet__borrowings", ".wrong-basis"), EXIT_REFUSED),
        # NOT_COMPARABLE: this is the status the artifact used to omit from its
        # unverified set while the CLI still exited non-zero for it.
        (("balance-sheet__borrowings", ".unreadable"), EXIT_REFUSED),
    ],
)
def test_the_artifacts_verified_flag_always_agrees_with_the_exit_code(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    swap: tuple[str, str] | None,
    expected_exit: int,
) -> None:
    """The file on disk must never claim more than the command told the caller.

    Anyone reading the artifact later has no access to the exit code, so a
    ``verified: true`` on a run that exited non-zero is the artifact lying about
    itself — and it is the artifact, not the shell, that downstream work reads.
    """
    _serve(monkeypatch, swap=swap)
    out_dir = tmp_path / "out"
    exit_code = main(
        [
            "screener-financials",
            "--stock",
            "FIXTURECO",
            "--out",
            str(out_dir),
            "--config",
            str(_watchlist(tmp_path)),
        ]
    )
    metadata = json.loads((out_dir / META_FILENAME).read_text(encoding="utf-8"))
    assert exit_code == expected_exit
    assert metadata["verified"] is (exit_code == 0)
