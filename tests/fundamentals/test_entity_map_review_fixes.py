"""Build-side and adapter defects the review round found (A18, A21-A26, A30).

Each of these shipped past a green gate, which is the point: the frozen suite
only ever exercised the paths the contract's worked examples named, so a rule
that was right for two-ISIN records and wrong for ISIN-less ones was invisible.
Every test below is written so that reverting its one fix turns it red.

Nothing here opens a socket or names a real listed company; the synthetic corpus
lives in :mod:`entity_map_fixtures`.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import entity_map_fixtures as fx
import pytest

from fundamentals.contracts.provenance import SourceAnchorType
from fundamentals.entity.entity_map_sources import UNRECORDED_RETRIEVAL
from fundamentals.ingest.screener_watchlist_models import (
    WatchlistArtifact,
    WatchlistFailure,
    WatchlistOutcome,
)

# ---------------------------------------------------------------------------
# A18 — two companies joined by an alternate key must never merge
# ---------------------------------------------------------------------------


def test_two_isin_less_records_sharing_a_scrip_but_not_a_symbol_refuse_the_build() -> None:
    """A18: the EM-02 refusal must not depend on an ISIN being present.

    Before the fix the collision check returned early unless the group held two
    distinct ISINs, so this pair published ONE entity keyed ``nse:ALPHAFX``,
    holding both symbols as a conflict — and BRAVOFX's key simply vanished from
    the map with nothing reporting that a company had disappeared. The live
    trigger is two stocks in a hand-edited config sharing one ``bse_scrip``
    through a copy-paste, which is exactly what this deliverable exists to catch.

    The same pair with distinct scrips is built first, so an implementation that
    refused every ISIN-less pair could not pass.
    """
    assert len(fx.build(*_scrip_pair(fx.ALPHA_BSE, fx.BRAVO_BSE)).entities) == 2

    with pytest.raises(fx.contracts.AlternateKeyCollisionError):
        fx.build(*_scrip_pair(fx.SHARED_BSE, fx.SHARED_BSE))


def _scrip_pair(first: str, second: str) -> tuple[object, ...]:
    """Two ISIN-less companies with different symbols and the given scrips."""
    return (
        fx.record(source_id=fx.S2_SOURCE_ID, nse=fx.ALPHA_NSE, bse=first, screener_company_id=1),
        fx.record(source_id=fx.S2_SOURCE_ID, nse=fx.BRAVO_NSE, bse=second, screener_company_id=2),
    )


def test_two_records_sharing_one_isin_still_record_a_symbol_conflict_rather_than_refuse() -> None:
    """A18's boundary: the ISIN is the primary key, so a disagreement under it is EM-06.

    The refusal must fire only on records pulled together by an alternate key
    ALONE. Two sources naming one ISIN and two symbols are one security about
    which the sources disagree, which EM-06 says to record and never resolve. An
    over-broad fix that refused any symbol disagreement would take this build
    down and delete a rule the frozen suite depends on.
    """
    built = fx.build(
        fx.record(isin_code=fx.ALPHA_ISIN, nse=fx.ALPHA_NSE),
        fx.record(source_id=fx.S2_SOURCE_ID, isin_code=fx.ALPHA_ISIN, nse=fx.ZULU_NSE),
    )

    entity = fx.by_key(built)[fx.ALPHA_ISIN]
    assert entity.conflicted is True
    assert sorted(fx.values_of(entity, fx.NSE_NS)) == sorted([fx.ALPHA_NSE, fx.ZULU_NSE])


def test_an_unconfirmed_scrip_contradicting_the_evidence_conflicts_rather_than_refuses() -> None:
    """A18 + EM-07: a mistyped hand pin must not be able to take a build down.

    ``bse_scrip`` is flagged ``needs_verification`` for two live stocks, so a
    refusal driven by unconfirmed values would fail the real build over a value
    the map never trusted. EM-07 is explicit that a contradicted unconfirmed
    value is an ordinary conflict, so only CONFIRMED values may drive the A18
    refusal — and the two records here still join on their shared symbol.
    """
    built = fx.build(
        fx.record(isin_code=fx.ALPHA_ISIN, nse=fx.ALPHA_NSE, bse=fx.ALPHA_BSE),
        fx.record(
            source_id=fx.S2_SOURCE_ID,
            nse=fx.ALPHA_NSE,
            bse=fx.SHARED_BSE,
            unverified=(fx.BSE_NS,),
        ),
    )

    assert [entity.key for entity in built.entities] == [fx.ALPHA_ISIN]
    assert (
        fx.coverage(built.entities[0], fx.BSE_NS).status is fx.contracts.CoverageStatus.CONFLICTED
    )


# ---------------------------------------------------------------------------
# A24 — one entity per published key
# ---------------------------------------------------------------------------


def test_two_pins_claiming_one_symbol_cannot_be_published_under_one_key() -> None:
    """A24: EM-01b's one-entity-per-key must hold on the published artifact.

    Nothing joins these two — the second symbol is unconfirmed, so it is no
    lookup path — yet both derive the surrogate key ``nse:SHAREDFX``. Publishing
    both makes every reference to that key ambiguous, the A17 advisory included,
    which degenerated to naming the same key twice. ``WatchlistConfig`` does not
    constrain ``nse_symbol``, so nothing upstream catches it.
    """
    confirmed = fx.record(source_id=fx.S2_SOURCE_ID, nse=fx.SHARED_NSE, bse=fx.ALPHA_BSE)
    unconfirmed = fx.record(
        source_id=fx.S2_SOURCE_ID,
        nse=fx.SHARED_NSE,
        bse=fx.BRAVO_BSE,
        unverified=(fx.NSE_NS,),
    )
    assert len(fx.build(confirmed).entities) == 1

    with pytest.raises(fx.contracts.DuplicateEntityKeyError):
        fx.build(confirmed, unconfirmed)


# ---------------------------------------------------------------------------
# A23 — the share-class tripwire is scoped to two distinct ISINs
# ---------------------------------------------------------------------------


def test_a_missed_join_sharing_a_company_id_does_not_kill_the_build() -> None:
    """A23: EM-08 calls a missed join recoverable, so it must not be fatal.

    This is the live ICICI Securities shape: a watchlist row carrying an ISIN
    and neither exchange code, beside a config pin carrying both. No rung of the
    ladder matches, so they stay two entities that share one Screener company
    id — and the unscoped tripwire killed the whole build on it. EM-04 words the
    refusal as two distinct ISINs, and only one ISIN is present here.
    """
    built = fx.build(
        fx.record(isin_code=fx.ALPHA_ISIN, screener_company_id=9100001),
        fx.record(source_id=fx.S2_SOURCE_ID, nse=fx.ALPHA_NSE, screener_company_id=9100001),
    )

    assert sorted(fx.by_key(built)) == sorted([fx.ALPHA_ISIN, f"nse:{fx.ALPHA_NSE}"])


def test_two_distinct_isins_sharing_a_company_id_still_refuse_the_build() -> None:
    """A23's boundary: scoping the tripwire must not disarm it.

    The dual-class shape EM-04 exists for is two ISINs under one Screener
    company, and narrowing the rule to match EM-04's wording must leave that
    refusal firing. Without this test the A23 fix could be "delete the check".
    """
    with pytest.raises(fx.contracts.ShareClassCollisionError):
        fx.build(
            fx.record(isin_code=fx.ALPHA_ISIN, nse=fx.ALPHA_NSE, screener_company_id=9100001),
            fx.record(isin_code=fx.BRAVO_ISIN, nse=fx.BRAVO_NSE, screener_company_id=9100001),
        )


# ---------------------------------------------------------------------------
# A22 — a reported absence contradicts an asserted value
# ---------------------------------------------------------------------------


def test_a_source_reporting_a_namespace_absent_conflicts_with_a_source_asserting_it() -> None:
    """A22: "there is no NSE listing" and "the symbol is BRAVOFX" disagree.

    Before the fix ``reported_absent`` was consulted only when the namespace
    held no values at all, so a hand-typed ``CONFIG_PIN`` overwrote the
    evidence's own statement, published KNOWN, and resolved through ``lookup``.
    EM-03's delisting signal — the one transition the map exists to make
    visible — vanished silently. The control entity is asserted reachable first,
    so the excluded lookup cannot be explained by a dead ``lookup``.
    """
    built = fx.build(
        fx.record(isin_code=fx.ALPHA_ISIN, bse=fx.ALPHA_BSE, reported_absent=(fx.NSE_NS,)),
        fx.record(source_id=fx.S2_SOURCE_ID, bse=fx.ALPHA_BSE, nse=fx.BRAVO_NSE),
        fx.record(isin_code=fx.CHARLIE_ISIN, nse=fx.CHARLIE_NSE),
    )

    assert built.lookup(fx.namespace(fx.NSE_NS), fx.CHARLIE_NSE) is not None
    entity = fx.by_key(built)[fx.ALPHA_ISIN]
    assert fx.coverage(entity, fx.NSE_NS).status is fx.contracts.CoverageStatus.CONFLICTED
    assert entity.conflicted is True
    assert built.lookup(fx.namespace(fx.NSE_NS), fx.BRAVO_NSE) is None


def test_a_namespace_no_source_carried_still_reads_as_not_supplied() -> None:
    """A22's boundary: only a REPORTED absence conflicts, silence does not.

    S1 carries no Tijori column at all, so an S1 row beside a pin asserting a
    Tijori slug must publish that slug as KNOWN. A fix that treated every
    unstated namespace as a contradiction would mark almost every live entity
    conflicted and empty the analysis universe.
    """
    built = fx.build(
        fx.record(isin_code=fx.ALPHA_ISIN, nse=fx.ALPHA_NSE),
        fx.record(source_id=fx.S2_SOURCE_ID, nse=fx.ALPHA_NSE, tijori_slug="fixture-alpha"),
    )

    entity = fx.by_key(built)[fx.ALPHA_ISIN]
    assert fx.coverage(entity, fx.TIJORI_SLUG_NS).status is fx.contracts.CoverageStatus.KNOWN
    assert entity.conflicted is False


# ---------------------------------------------------------------------------
# A21 — a failed acquisition is not evidence
# ---------------------------------------------------------------------------


def test_an_incomplete_watchlist_artifact_is_refused_rather_than_read_for_its_rows(
    tmp_path: Path,
) -> None:
    """A21: an artifact that stopped short records no membership.

    Iterating its empty rows yields zero evidence, which makes ``verify`` report
    every pin NOT_COVERED and exit zero — a failed acquisition reading as a
    clean map. ``INCOMPLETE`` was made a first-class outcome precisely so a
    capped or stale fetch could not pass as complete. A complete artifact is
    loaded first, so a loader that refused everything could not pass.
    """
    complete = fx.write_s1_artifact(tmp_path, [fx.ALPHA_LISTING])
    assert fx.sources.load_s1_records(complete)

    incomplete = tmp_path / "incomplete.json"
    incomplete.write_text(_incomplete_artifact().model_dump_json(indent=2), encoding="utf-8")

    with pytest.raises(fx.contracts.IncompleteEvidenceError, match=WatchlistOutcome.INCOMPLETE):
        fx.sources.load_s1_records(incomplete)


def _incomplete_artifact() -> WatchlistArtifact:
    """A published-shape artifact for a run that stopped short."""
    return WatchlistArtifact(
        outcome=WatchlistOutcome.INCOMPLETE,
        incomplete_reason="the fixture run stopped short",
        failure=WatchlistFailure(
            source_url="https://fixture.invalid/watchlist/",
            refusal="WatchlistStructureError",
            detail="the fixture table had no admitted shape",
        ),
    )


# ---------------------------------------------------------------------------
# A25 — EM-11: no filesystem metadata in the artifact
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("source", ["s1", "s2"])
def test_touching_a_source_file_without_changing_a_byte_changes_no_provenance(
    tmp_path: Path, source: str
) -> None:
    """A25: EM-11 promises two builds over identical bytes agree.

    ``retrieved_at`` was derived from mtime, which any clone or checkout
    restamps, so CI could never byte-match a developer's build over the very
    same sources — destroying the diff EM-11 exists to make meaningful. The
    frozen CLI test could not see it because it rebuilds inside one tmpdir.
    The file's digest is asserted unchanged first, so the comparison is provably
    over identical bytes.
    """
    path = (
        fx.write_s1_artifact(tmp_path, [fx.ALPHA_LISTING])
        if source == "s1"
        else fx.write_s2_config(tmp_path, [fx.ALPHA_PIN])
    )
    load = fx.sources.load_s1_records if source == "s1" else fx.sources.load_s2_records
    before = load(path)
    digest = fx.sha256_of(path)

    os.utime(path, (1_000_000_000, 1_000_000_000))

    assert fx.sha256_of(path) == digest
    assert load(path) == before


def test_a_source_recording_no_retrieval_time_says_so_rather_than_inventing_one(
    tmp_path: Path,
) -> None:
    """A25: the sentinel is explicit, and a caller's stamp still wins.

    A YAML config records no retrieval time by nature. Publishing a plausible
    wall-clock or mtime value there would be a fabricated claim about when the
    value was seen; the sentinel says "unrecorded" in one recognisable way. The
    caller-supplied stamp is asserted in the same test so the sentinel cannot be
    a hardcoded constant that ignores its input.
    """
    config = fx.write_s2_config(tmp_path, [fx.ALPHA_PIN])
    stamp = datetime(2026, 9, 3, 6, 0, tzinfo=UTC)

    unstamped = fx.sources.load_s2_records(config)[0]
    stamped = fx.sources.load_s2_records(config, retrieved_at=stamp)[0]

    assert unstamped.assertions[0].provenance.retrieved_at == UNRECORDED_RETRIEVAL
    assert stamped.assertions[0].provenance.retrieved_at == stamp


# ---------------------------------------------------------------------------
# A26 — the S1 anchor must address a position the file actually has
# ---------------------------------------------------------------------------


def test_the_s1_anchor_addresses_a_json_location_not_a_csv_column(tmp_path: Path) -> None:
    """A26: the file named by the sha256 is JSON, and JSON has no columns.

    The anchor previously claimed ``CSV_RECORD`` with a ``column_index`` that
    was a position in a Python tuple, not a column of any file — SL4-27 in
    reverse, an anchor addressing a position it does not have. ``JSON_ISLAND``
    fits honestly and BARS ``column_index``, so no ordinal can be fabricated;
    that bar is asserted here rather than assumed.
    """
    artifact = fx.write_s1_artifact(tmp_path, [fx.ALPHA_LISTING])

    marks = [
        assertion.provenance
        for record in fx.sources.load_s1_records(artifact)
        for assertion in record.assertions
    ]
    assert marks

    for mark in marks:
        assert mark.anchor_type is SourceAnchorType.JSON_ISLAND
        assert mark.column_index is None
        assert mark.table_id is None
        assert mark.island_id and mark.table_key
        assert mark.row_label == "1"
    assert {mark.column_label for mark in marks} == {
        "isin_code",
        "nse_code",
        "bse_code",
        "slug",
        "data_row_company_id",
    }


# ---------------------------------------------------------------------------
# A30 — A4's typed refusal must precede provenance construction
# ---------------------------------------------------------------------------


def test_a_pin_with_no_symbol_raises_the_typed_refusal_not_a_provenance_error(
    tmp_path: Path,
) -> None:
    """A30: a refusal a reader sees as protection must actually be the one raised.

    The config addresses every stock by NSE symbol, and the CONFIG_PIN anchor
    uses it as ``row_label``. Building the provenance first meant the anchor
    validator rejected the empty ``row_label`` before the map's own typed
    refusal could fire, so the error a maintainer saw pointed at the anchor
    rather than at the unidentifiable config row. A normal pin is loaded first,
    so the refusal is provably about the missing symbol.
    """
    assert fx.sources.load_s2_records(fx.write_s2_config(tmp_path, [fx.ALPHA_PIN]))

    elsewhere = tmp_path / "nameless"
    elsewhere.mkdir()
    blank = fx.write_s2_config(elsewhere, [fx.ALPHA_PIN.model_copy(update={"nse_symbol": ""})])

    with pytest.raises(fx.contracts.UnkeyableRecordError):
        fx.sources.load_s2_records(blank)
