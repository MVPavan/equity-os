"""The two entity-map source adapters, and the read-only verification report.

S1 is a ``screener-watchlist`` artifact JSON and S2 is ``config/watchlist.yaml``;
both are read from disk and nothing here opens a socket. Every fixture is
synthetic and is written into ``tmp_path`` by :mod:`entity_map_fixtures`, so no
test in this file can be satisfied — or corrupted — by a captured page or by the
repository's own pinned config.

The rules pinned here are the ones that only exist once a real source shape is
involved: provenance survival across the adapter boundary (EM-05) under the
``CONFIG_PIN`` anchor A5 added, S2's ISIN being absent today but read when
pinned (A1 / EM-01b), ``needs_verification`` arriving unverified (EM-07), the
two ``MissingReason`` members A6 fixed, ``verify`` never writing to what it read
(EM-09), and ``verify`` refusing two pins that claim one NSE symbol (A7).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import entity_map_fixtures as fx
import pytest

from fundamentals.contracts.provenance import SourceAnchorType

CHARLIE_LISTING = fx.Listing(
    company_id=9100003,
    slug=fx.CHARLIE_NSE,
    display_name="Fixture Charlie Foods Limited",
    isin_code=fx.CHARLIE_ISIN,
    nse_code=fx.CHARLIE_NSE,
    bse_code=fx.CHARLIE_BSE,
)

# Pinned against a stock S1 also carries, but disagreeing on the BSE scrip.
CHARLIE_PIN = fx.Pin(
    name="Fixture Charlie Foods Limited",
    nse_symbol=fx.CHARLIE_NSE,
    bse_scrip=fx.DELTA_BSE,
    screener_slug=fx.CHARLIE_NSE,
    screener_company_id=9100003,
    screener_warehouse_id_standalone=9200003,
    tijori_slug="fixture-charlie-foods",
    tijori_company_id=9300003,
)


# No NSE code and no BSE code, but an ISIN: the shape EM-03 keeps as NOT_LISTED
# and A6 calls SOURCE_REPORTED_ABSENT, because the export carried both columns
# and published nothing in either.
DELISTED_LISTING = fx.Listing(
    company_id=9100005,
    slug=None,
    display_name="Fixture Echo Securities Limited",
    isin_code=fx.DELTA_ISIN,
    nse_code=None,
    bse_code=None,
)

ISIN_PINNED = fx.Pin(
    name="Fixture Bravo Chemicals Limited",
    nse_symbol=fx.BRAVO_NSE,
    bse_scrip=fx.BRAVO_BSE,
    isin=fx.BRAVO_ISIN,
    screener_slug=fx.BRAVO_NSE,
    screener_company_id=9100002,
    screener_warehouse_id_standalone=9200002,
    tijori_slug="fixture-bravo-chemicals",
    tijori_company_id=9300002,
)


def _sources(tmp_path: Path) -> tuple[Path, Path]:
    """An S1 artifact and an S2 config on disk: one shared stock, one of each alone."""
    artifact = fx.write_s1_artifact(tmp_path, [fx.ALPHA_LISTING, CHARLIE_LISTING])
    config = fx.write_s2_config(tmp_path, [fx.ALPHA_PIN, CHARLIE_PIN, fx.DELTA_PIN])
    return artifact, config


def _namespaces(record: Any) -> set[Any]:
    """The namespaces one source record asserts."""
    return {assertion.namespace for assertion in record.assertions}


def _pin_record(records: tuple[Any, ...], symbol: str) -> Any:
    """The one loaded S2 record whose NSE symbol is ``symbol``."""
    return next(
        record
        for record in records
        if any(assertion.value == symbol for assertion in record.assertions)
    )


def test_the_s1_adapter_binds_every_value_to_the_artifact_file_it_read(tmp_path: Path) -> None:
    """EM-05: provenance survives the adapter, bound to the file by sha256.

    A model that merely *requires* a provenance is satisfied by an adapter that
    invents one, so this asserts the recorded ``file_sha256`` is the digest of
    the artifact actually read. The record and assertion counts are asserted
    first: an adapter returning nothing would otherwise pass a loop-only test.
    """
    artifact, _ = _sources(tmp_path)

    records = fx.sources.load_s1_records(artifact)
    assert len(records) == 2

    digest = fx.sha256_of(artifact)
    for record in records:
        assert record.assertions
        for assertion in record.assertions:
            assert assertion.provenance.file_sha256 == digest
            assert assertion.provenance.source_id


def test_the_s1_adapter_supplies_the_five_namespaces_the_artifact_carries(
    tmp_path: Path,
) -> None:
    """EM-12: coverage is stated, so what S1 does and does not supply is explicit.

    S1 supplies ISIN, NSE, BSE, the Screener slug and the Screener company id,
    and carries no Tijori namespace whatsoever. Asserting the set is exact
    catches both an adapter that drops a column and one that invents a Tijori
    value out of the slug.
    """
    artifact, _ = _sources(tmp_path)

    supplied = _namespaces(fx.sources.load_s1_records(artifact)[0])

    assert supplied == {
        fx.namespace(fx.ISIN_NS),
        fx.namespace(fx.NSE_NS),
        fx.namespace(fx.BSE_NS),
        fx.namespace(fx.SCREENER_SLUG_NS),
        fx.namespace(fx.SCREENER_COMPANY_ID_NS),
    }


def test_the_s2_adapter_supplies_no_isin_so_its_stocks_are_surrogate_keyed(
    tmp_path: Path,
) -> None:
    """EM-01b: S2 carries no ISIN, so every S2-only stock is keyed ``nse:<symbol>``.

    This is the rule's reason for existing: without the surrogate, all ten
    pinned stocks are unrepresentable and an implementation would be tempted to
    drop them. The ISIN namespace must be reported missing rather than filled
    with the surrogate key, which would publish it as if it were an ISIN.
    """
    _, config = _sources(tmp_path)

    records = fx.sources.load_s2_records(config)
    assert len(records) == 3
    assert all(fx.namespace(fx.ISIN_NS) not in _namespaces(record) for record in records)

    built = fx.entity_map.build_entity_map(records)
    entity = fx.by_key(built)[f"nse:{fx.DELTA_NSE}"]
    assert entity.state is fx.contracts.EntityState.ISIN_MISSING
    assert fx.coverage(entity, fx.ISIN_NS).status is fx.contracts.CoverageStatus.MISSING
    assert fx.coverage(entity, fx.ISIN_NS).missing_reason is (
        fx.contracts.MissingReason.NOT_SUPPLIED
    )


def test_a_needs_verification_field_arrives_unverified_and_its_siblings_do_not(
    tmp_path: Path,
) -> None:
    """EM-07: only the fields a stock names in ``needs_verification`` are unverified.

    ``DELTA_PIN`` flags ``bse_scrip`` and nothing else. Asserting the flagged
    field alone would pass an adapter that marks every S2 value unverified —
    which would make every S2 pin unusable for lookup — so the unflagged NSE
    symbol is asserted verified in the same breath.
    """
    _, config = _sources(tmp_path)

    delta = _pin_record(fx.sources.load_s2_records(config), fx.DELTA_NSE)
    verified = {assertion.namespace: assertion.verified for assertion in delta.assertions}

    assert verified[fx.namespace(fx.BSE_NS)] is False
    assert verified[fx.namespace(fx.NSE_NS)] is True
    assert verified[fx.namespace(fx.TIJORI_SLUG_NS)] is True


def test_the_s2_adapter_anchors_every_pin_as_config_pin_by_symbol_and_field(
    tmp_path: Path,
) -> None:
    """A5 / EM-05: a hand-edited YAML pin gets its own anchor type, not a borrowed one.

    No pre-existing anchor kind honestly describes a config pin, and forcing one
    would make the retrieval procedure a lie — the point of the typed anchor.
    ``row_label`` addresses the stock by the NSE symbol as the config spells it
    and ``column_label`` names the identifier field, so a reader can go back to
    the exact line. Asserting the anchor type alone would pass an adapter that
    stamped ``CONFIG_PIN`` on an otherwise unaddressed provenance, so the two
    location fields are asserted for a specific, named assertion.
    """
    _, config = _sources(tmp_path)

    delta = _pin_record(fx.sources.load_s2_records(config), fx.DELTA_NSE)
    marks = {assertion.namespace: assertion.provenance for assertion in delta.assertions}
    assert len(marks) == len(delta.assertions)

    for mark in marks.values():
        assert mark.anchor_type is SourceAnchorType.CONFIG_PIN
        assert mark.row_label == fx.DELTA_NSE
    assert marks[fx.namespace(fx.BSE_NS)].column_label == "bse_scrip"
    assert marks[fx.namespace(fx.TIJORI_SLUG_NS)].column_label == "tijori_slug"


def test_a_pinned_isin_makes_an_s2_stock_isin_keyed_rather_than_surrogate_keyed(
    tmp_path: Path,
) -> None:
    """A1: the adapter reads ``identifiers.isin`` when a stock populates it.

    ``SourceIdentifiers`` declares the field and no stock populates it today, so
    an adapter that ignored it would be invisible until the day someone pinned
    one — and would then silently publish that stock under a surrogate key
    beside its own ISIN-keyed self. A stock with no pinned ISIN is loaded in the
    same config and asserted still surrogate-keyed, so an adapter that invents
    an ISIN for everything cannot pass either.
    """
    config = fx.write_s2_config(tmp_path, [ISIN_PINNED, fx.DELTA_PIN])

    built = fx.entity_map.build_entity_map(fx.sources.load_s2_records(config))

    assert sorted(fx.by_key(built)) == sorted([fx.BRAVO_ISIN, f"nse:{fx.DELTA_NSE}"])
    pinned = fx.by_key(built)[fx.BRAVO_ISIN]
    assert pinned.state is fx.contracts.EntityState.RESOLVED
    assert fx.values_of(pinned, fx.ISIN_NS) == (fx.BRAVO_ISIN,)


def test_a_source_that_carried_a_namespace_and_published_nothing_says_so(
    tmp_path: Path,
) -> None:
    """A6: ``SOURCE_REPORTED_ABSENT`` is not the same claim as ``NOT_SUPPLIED``.

    The S1 export carries an ``NSE Code`` column for every member, so an empty
    cell is the source stating there is no NSE listing — the live ICICI
    Securities shape. It carries no Tijori column at all, which is a statement
    about our coverage, not about the company. Both are asserted on one entity
    so an adapter that emits a single reason for everything goes red.
    """
    artifact = fx.write_s1_artifact(tmp_path, [DELISTED_LISTING])

    built = fx.entity_map.build_entity_map(fx.sources.load_s1_records(artifact))
    entity = fx.by_key(built)[fx.DELTA_ISIN]

    assert entity.state is fx.contracts.EntityState.NOT_LISTED
    for name in (fx.NSE_NS, fx.BSE_NS):
        assert fx.coverage(entity, name).missing_reason is (
            fx.contracts.MissingReason.SOURCE_REPORTED_ABSENT
        )
    assert fx.coverage(entity, fx.TIJORI_SLUG_NS).missing_reason is (
        fx.contracts.MissingReason.NOT_SUPPLIED
    )


def test_verify_rewrites_neither_source_file(tmp_path: Path) -> None:
    """EM-09: the map is read-only toward its sources.

    ``verify`` exists to tell a human that a pin is wrong; correcting the pin is
    that human's edit. An implementation that "helpfully" repaired the YAML
    would destroy the hand-pinned evidence and make the next run's report
    meaningless. The report is asserted non-empty first, so a ``verify`` that
    did nothing at all cannot pass by leaving the files alone.
    """
    artifact, config = _sources(tmp_path)
    before = (fx.sha256_of(artifact), fx.sha256_of(config))

    report = fx.entity_map.verify_pins(artifact, config)
    assert len(report.entries) == 3

    assert (fx.sha256_of(artifact), fx.sha256_of(config)) == before


def test_verify_separates_a_confirmed_pin_from_a_conflicted_and_an_uncovered_one(
    tmp_path: Path,
) -> None:
    """The verify report: CONFIRMED / CONFLICTED / NOT_COVERED, per pinned stock.

    All three outcomes are asserted in one build because the distinctions are
    what the report is for: an implementation that collapses NOT_COVERED into
    CONFLICTED would fail the run on a watchlist that simply does not overlap,
    and one that collapses CONFLICTED into CONFIRMED would pass a genuinely
    wrong pin. ``CHARLIE_PIN`` disagrees with S1 on the BSE scrip only, so no
    other rule can explain its outcome.
    """
    artifact, config = _sources(tmp_path)

    outcomes = {
        entry.symbol: entry.outcome for entry in fx.entity_map.verify_pins(artifact, config).entries
    }

    assert outcomes == {
        fx.ALPHA_NSE: fx.contracts.VerificationOutcome.CONFIRMED,
        fx.CHARLIE_NSE: fx.contracts.VerificationOutcome.CONFLICTED,
        fx.DELTA_NSE: fx.contracts.VerificationOutcome.NOT_COVERED,
    }


def test_verify_refuses_two_pinned_stocks_that_claim_one_nse_symbol(tmp_path: Path) -> None:
    """A7: the report is keyed by NSE symbol, so a duplicate symbol has no answer.

    ``WatchlistConfig`` enforces uniqueness on the Screener and Tijori ids but
    not on the symbol, so nothing upstream catches this. Nor does EM-02: two
    ISIN-less pins sharing a symbol *join* under EM-08's second rung rather than
    colliding, so without this guard ``verify`` would quietly emit one merged,
    conflicted row for two different pinned stocks. The non-colliding config is
    verified first, proving the refusal is about the duplicate and not about the
    fixture.
    """
    artifact, config = _sources(tmp_path)
    assert fx.entity_map.verify_pins(artifact, config).entries

    twin = CHARLIE_PIN.model_copy(
        update={
            "nse_symbol": fx.ALPHA_NSE,
            "screener_company_id": 9100006,
            "screener_warehouse_id_standalone": 9200006,
            "tijori_company_id": 9300006,
        }
    )
    elsewhere = tmp_path / "colliding"
    elsewhere.mkdir()
    colliding = fx.write_s2_config(elsewhere, [fx.ALPHA_PIN, twin])

    with pytest.raises(fx.contracts.AlternateKeyCollisionError):
        fx.entity_map.verify_pins(artifact, colliding)
