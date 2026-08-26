"""The ``screener-company`` acquisition contract and its refusals.

Everything here is about what reaches disk and what exit code the caller sees:
retained evidence, no-clobber, a sweep cut short, and the difference between a
document that failed a check and one that never had a check to fail.

The transport seam and the synthetic bodies live in
:mod:`screener_company_support`, shared with :mod:`test_screener_company`.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import screener_company_support as support

from fundamentals.api.cli import main
from fundamentals.api.screener_cli_dispatch import (
    EXIT_BASIS_UNAVAILABLE,
    EXIT_OK,
    EXIT_REFUSED,
)
from fundamentals.api.screener_company_cli import (
    DOCUMENTS_DIRNAME,
    FAILURES_FILENAME,
    META_FILENAME,
    PAGE_RAW_FILENAME,
    render_screener_company_summary,
    run_screener_company_command,
)
from fundamentals.api.watchlist_config import SCREENER_COMPANY_ID_FIELD

BARE_PAGE = support.FIXTURES / "synthetic_screener_company_bare.html"


def _argv(tmp_path: Path, config: Path, *extra: str) -> list[str]:
    """The argv for one full consolidated acquisition into ``tmp_path``."""
    return [
        "screener-company",
        "--stock",
        support.SYMBOL,
        "--out",
        str(tmp_path / "out"),
        "--config",
        str(config),
        *extra,
    ]


def _run_cli(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *extra: str, **kwargs: object
) -> tuple[int, Path]:
    """Run the command end to end against the pinned seam."""
    support.serve(monkeypatch, **kwargs)  # type: ignore[arg-type]
    config = support.watchlist(tmp_path)
    exit_code = main(_argv(tmp_path, config, *extra))
    return exit_code, tmp_path / "out"


# --------------------------------------------------------------------------
# What reaches disk
# --------------------------------------------------------------------------


def test_a_clean_run_publishes_every_body_a_part_file_and_the_metadata_last(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The metadata is the completion marker, so it must be the last thing written.

    An artifact whose source documents are gone cannot be re-derived or audited,
    and for the ``URL_ONLY`` parts the retained body is the *only* evidence there
    will ever be. Publishing the metadata first would leave a durable claim
    pointing at files that do not exist — and, because writes are no-clobber,
    would block the retry that would fix it.
    """
    exit_code, out_dir = _run_cli(monkeypatch, tmp_path)
    assert exit_code == EXIT_OK
    assert (out_dir / PAGE_RAW_FILENAME).exists()
    assert (out_dir / META_FILENAME).exists()
    assert not (out_dir / FAILURES_FILENAME).exists()
    documents = sorted(path.name for path in (out_dir / DOCUMENTS_DIRNAME).iterdir())
    assert documents == [
        "corporate-actions__corporate-actions.raw.html",
        "investors__foreign-institutions-quarterly.raw.json",
        "investors__foreign-institutions-yearly.raw.json",
        "investors__government-quarterly.raw.json",
        "investors__government-yearly.raw.json",
        "investors__promoters-quarterly.raw.json",
        "investors__promoters-yearly.raw.json",
        "investors__public-quarterly.raw.json",
        "investors__public-yearly.raw.json",
        "peers__peers.raw.html",
        "quick-ratios__quick-ratios.raw.html",
        "related-party__related-party.raw.html",
        "segments__profit-loss-1.raw.html",
        "segments__quarters-1.raw.html",
    ]
    assert sorted(path.name for path in out_dir.glob("part_*.json")) == [
        "part_corporate-actions.json",
        "part_investors.json",
        "part_peers.json",
        "part_quick-ratios.json",
        "part_related-party.json",
        "part_segments.json",
    ]


def test_retained_bodies_match_the_hash_the_metadata_records(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A hash that does not describe the bytes on disk makes the artifact unauditable.

    The whole point of retaining a ``URL_ONLY`` document is that someone can go
    back to the exact bytes a number came from. The hash is verified after the
    write, from the file, so a truncated or re-encoded write cannot pass.
    """
    _, out_dir = _run_cli(monkeypatch, tmp_path)
    page_sha = json.loads((out_dir / META_FILENAME).read_text(encoding="utf-8"))["page_sha256"]
    assert hashlib.sha256((out_dir / PAGE_RAW_FILENAME).read_bytes()).hexdigest() == page_sha
    body = (out_dir / DOCUMENTS_DIRNAME / "investors__promoters-quarterly.raw.json").read_bytes()
    assert json.loads(body)["Fixture Family Trust"]["Sep 2025"] == "20.00"


def test_a_part_file_records_its_outcome_even_when_nothing_was_offered(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An empty part file must not read as "the run never got there".

    "This company publishes no Product Segments" and "the sweep stopped before
    segments" produce the same empty table but mean opposite things, and only one
    of them is a reason to re-run.
    """
    _, out_dir = _run_cli(monkeypatch, tmp_path, page=BARE_PAGE)
    payload = json.loads((out_dir / "part_segments.json").read_text(encoding="utf-8"))
    assert payload["tables"] == []
    assert payload["outcome"]["offered"] is False
    assert payload["outcome"]["documents"] == []
    assert "positive proof" in payload["outcome"]["note"]


def test_metadata_records_each_document_on_both_axes_separately(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A reader must see, per document, both how it is bound and what checked out.

    Promoters and the threshold buckets sit in one part, share a binding, and
    are held to different relations. Recording one verdict per part would
    promote six unproven documents on the strength of two, and recording one
    axis would hide whichever question the reader actually had.
    """
    _, out_dir = _run_cli(monkeypatch, tmp_path)
    metadata = json.loads((out_dir / META_FILENAME).read_text(encoding="utf-8"))
    by_validation = metadata["documents_by_validation"]
    assert "/api/3/991001/investors/promoters/quarterly/" in by_validation["equality:passed"]
    assert "/api/3/991001/investors/public/quarterly/" in by_validation["upper_bound:passed"]
    assert "/results/rpt/991001/consolidated/" in by_validation["none:not_applicable"]
    by_binding = metadata["documents_by_binding"]
    assert "/api/company/992001/peers/" in by_binding["body_asserted"]
    assert "shareholding:quarterly" in by_binding["page_asserted"]
    assert metadata["proven_documents"] == [
        "shareholding:quarterly",
        "shareholding:yearly",
        "/api/3/991001/investors/promoters/quarterly/",
        "/api/3/991001/investors/promoters/yearly/",
        "page:#top-ratios",
    ]
    assert "/api/3/991001/investors/public/quarterly/" in metadata["weak_documents"]
    assert "/api/company/992001/peers/" in metadata["weak_documents"]
    assert metadata["acquisition"] == "complete"
    assert metadata["all_admitted"] is True
    assert metadata["planned_sub_requests"] == 14
    assert metadata["request_count"] == 15


# --------------------------------------------------------------------------
# Refusals before the network
# --------------------------------------------------------------------------


def test_an_unverified_identifier_stops_the_run_before_any_request(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Every request here binds to the issuer through an identifier and nothing else.

    The investors, segments, peers and quick-ratios endpoints all name the
    company only in their path, so an unconfirmed company id would produce
    documents that parse perfectly and describe someone else.
    """
    requested = support.serve(monkeypatch)
    config = support.watchlist(tmp_path, flagged=f'"{SCREENER_COMPANY_ID_FIELD}"')
    with pytest.raises(SystemExit) as excinfo:
        main(_argv(tmp_path, config))
    assert SCREENER_COMPANY_ID_FIELD in str(excinfo.value)
    assert requested == []


def test_an_existing_artifact_is_refused_before_the_page_is_fetched(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Refusing after the sweep would spend fifteen rate-limited requests to discard it.

    Screener rate-limits at ~40 GETs, so a pre-flight that runs after the fetch
    is not a pre-flight — it is a way to burn a third of the budget on a run
    whose output was never going to be written.
    """
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True)
    (out_dir / META_FILENAME).write_text("{}", encoding="utf-8")
    requested = support.serve(monkeypatch)
    config = support.watchlist(tmp_path)
    with pytest.raises(SystemExit) as excinfo:
        main(_argv(tmp_path, config))
    assert "refusing to overwrite" in str(excinfo.value)
    assert requested == []


def test_a_basis_the_company_does_not_publish_exits_three_and_writes_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A standalone-only company answers its consolidated URL with HTTP 200.

    Parsing that degenerate shell would publish an artifact of empty tables under
    a basis the company does not have. Its own exit code keeps a watchlist loop
    from confusing "no such basis" with "the fetch was refused".
    """
    support.serve(monkeypatch)
    config = support.watchlist(tmp_path)
    exit_code = main(
        [
            "screener-company",
            "--stock",
            "SOLOCO",
            "--out",
            str(tmp_path / "out"),
            "--config",
            str(config),
        ]
    )
    assert exit_code == EXIT_BASIS_UNAVAILABLE
    assert not (tmp_path / "out" / META_FILENAME).exists()


# --------------------------------------------------------------------------
# Exit codes: what fails a run and what does not
# --------------------------------------------------------------------------


def test_weak_evidence_alone_still_exits_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Unprovable is not unproven, and conflating them makes the exit code useless.

    Every run of this command retains ``URL_ONLY`` documents, because the source
    publishes nothing that could prove a related-party modal. If that exited
    non-zero, success would be unreachable for every company and a caller would
    learn to ignore the code — including on the runs that really did fail.
    """
    exit_code, _ = _run_cli(monkeypatch, tmp_path)
    assert exit_code == EXIT_OK
    captured = capsys.readouterr()
    assert "retained without a proof" in captured.err
    assert "/results/rpt/991001/consolidated/" in captured.err


def test_a_refused_document_exits_two_with_its_body_retained(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A check that could run and failed is the one thing that must fail the run.

    The body is kept and named in the failures file because it is the most
    useful artifact the run produced: it is what a wrong company id or a
    wrong-basis request actually looks like on this surface.
    """
    exit_code, out_dir = _run_cli(monkeypatch, tmp_path, swap=("peers", ".missing"))
    assert exit_code == EXIT_REFUSED
    failures = json.loads((out_dir / FAILURES_FILENAME).read_text(encoding="utf-8"))
    assert [failure["refusal"] for failure in failures] == ["PeerIdentityError"]
    assert (out_dir / DOCUMENTS_DIRNAME / "peers__peers.raw.html").exists()
    metadata = json.loads((out_dir / META_FILENAME).read_text(encoding="utf-8"))
    assert metadata["all_admitted"] is False
    assert metadata["acquisition"] == "refused"
    assert "documents refused" in capsys.readouterr().err


def test_a_sweep_cut_short_exits_two_and_says_so(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A partial artifact must never be mistaken for a company that publishes less.

    Everything fetched before the 429 is retained and still true. What is missing
    is named in ``incomplete_reason`` and on stderr, so a shorter documents list
    is never read as a fact about the issuer.
    """
    exit_code, out_dir = _run_cli(monkeypatch, tmp_path, rate_limit_after=2)
    assert exit_code == EXIT_REFUSED
    metadata = json.loads((out_dir / META_FILENAME).read_text(encoding="utf-8"))
    assert metadata["complete"] is False
    assert "rate-limited" in metadata["incomplete_reason"]
    assert len(list((out_dir / DOCUMENTS_DIRNAME).iterdir())) == 2
    assert "did not finish" in capsys.readouterr().err


def test_parts_this_company_does_not_publish_are_reported_but_not_failures(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Absence discovered from the page is a fact about the issuer, not a run failure.

    Four of the ten watchlist companies offer no Product Segments at all.
    Treating that as an error would make those companies permanently red while
    telling a reader nothing they could act on.
    """
    exit_code, _ = _run_cli(monkeypatch, tmp_path, page=BARE_PAGE)
    assert exit_code == EXIT_OK
    assert "parts this company does not publish" in capsys.readouterr().err


# --------------------------------------------------------------------------
# Scope and summary
# --------------------------------------------------------------------------


def test_one_part_can_be_acquired_alone(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A caller re-checking one document should not spend the whole request budget.

    ``--part peers`` is one request against a source that rate-limits at ~40;
    running the full sweep to re-read it would cost fifteen.
    """
    requested = support.serve(monkeypatch)
    config = support.watchlist(tmp_path)
    exit_code = main(_argv(tmp_path, config, "--part", "peers"))
    assert exit_code == EXIT_OK
    assert [url for url in requested if "/peers/" in url]
    assert not any("/investors/" in url for url in requested)
    assert sorted(path.name for path in (tmp_path / "out").glob("part_*.json")) == [
        "part_peers.json"
    ]


def test_the_standalone_basis_builds_a_different_request_for_every_scoped_document(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Three of the six parts are basis-scoped and each expresses it differently.

    Segments carry the basis in a query *value*, peers and quick ratios in the
    warehouse id inside the path, and the related-party modal in a path suffix
    the page itself chose. Getting any one of them wrong returns a body that
    parses cleanly and describes the other basis.
    """
    requested = support.serve(monkeypatch)
    config = support.watchlist(tmp_path)
    exit_code = main(_argv(tmp_path, config, "--basis", "standalone"))
    assert exit_code == EXIT_OK
    paths = [url.replace("https://www.screener.in", "") for url in requested]
    assert "/api/segments/991001/quarters/1/" in paths
    assert "/api/segments/991001/quarters/1/?consolidated=true" not in paths
    assert "/api/company/992002/peers/" in paths
    assert "/api/company/992002/quick_ratios/" in paths
    assert "/api/3/991001/investors/promoters/quarterly/" in paths


def test_the_summary_states_each_parts_class_and_its_key_check(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The summary is where a human sees how much of the run was actually proven.

    Printing only "ok" would hide that most of the fourteen documents carry a
    one-sided bound or no check at all, which is the single most important thing
    about this command's output — and the wording has to match the relation that
    actually ran, so a segments line names its newest-period bound rather than
    borrowing the language of a full reconciliation.
    """
    support.serve(monkeypatch)
    config = support.watchlist(tmp_path)
    parser_args = _argv(tmp_path, config)
    from fundamentals.api.cli_parser import build_parser

    published = run_screener_company_command(
        build_parser().parse_args(parser_args),
        credentials=support.config().credentials,  # type: ignore[arg-type]
    )
    summary = render_screener_company_summary(published)  # type: ignore[arg-type]
    assert "investors\ttrue\t10" in summary
    assert "segments\ttrue\t2" in summary
    assert "peers\ttrue\t1" in summary
    assert (
        "/api/3/991001/investors/promoters/quarterly/\tconfigured_url_only\tequality\tpassed"
        in summary
    )
    assert "investors promoters quarterly\tflat_sum\tsum_matched n=2" in summary
    assert "investors public quarterly\tupper_bound\twithin_bound n=1" in summary
    assert (
        "segments quarters Sales\tlower_bound_newest\tnewest_period_not_below reconciled" in summary
    )
    assert "peers\tself_row_basis\tself_row=3 basis ok" in summary
    assert "weak_document\tbinding\tvalidation" in summary
