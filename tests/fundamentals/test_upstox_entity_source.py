"""Coverage for the Upstox entity adapter: a disk read that emits identity records.

This adapter is the reason Slice 1 exists. Nine of the ten pinned stocks are
keyed ``nse:<symbol>`` because no source has ever supplied their ISIN, and
supplying one **re-keys** the entity — a transition ``build_entity_map`` has
several refusal paths that could fire on. The last test in this file is that
transition, run end to end.

The adapter opens no socket, exactly as the two existing entity adapters do not,
so an entity-map build stays offline and reproducible.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import entity_map_fixtures as emf
import pytest
from upstox_fixtures import (
    BSE_ISIN,
    BSE_SCRIP,
    NSE_ISIN,
    NSE_SYMBOL,
    bse_equity_row,
    derivative_row,
    instruments_fetch,
    nse_equity_row,
    suspended_fetch,
    suspended_row,
)

from fundamentals.contracts.entity_identity import IdentifierNamespace
from fundamentals.contracts.provenance import SourceAnchorType
from fundamentals.entity.entity_map import build_entity_map
from fundamentals.entity.entity_map_sources import load_s2_records
from fundamentals.entity.upstox_entity_source import (
    UPSTOX_SOURCE_ID,
    load_upstox_records,
)
from fundamentals.ingest.upstox_instruments import (
    read_instrument_catalog,
    read_suspended_catalog,
)

_CAP = 4 * 1024 * 1024


def _write_catalog(tmp_path: Path, *rows: dict[str, object]) -> Path:
    """Write a parsed instrument catalog artifact and return its path."""
    catalog = read_instrument_catalog(instruments_fetch(list(rows)), max_decompressed_bytes=_CAP)
    path = tmp_path / "upstox_instruments.parsed.json"
    path.write_text(catalog.model_dump_json(), encoding="utf-8")
    return path


def test_a_listed_row_asserts_its_isin_and_its_exchange_code(tmp_path: Path) -> None:
    """The three join namespaces come from the file, never from a name."""
    records = load_upstox_records(_write_catalog(tmp_path, nse_equity_row(), bse_equity_row()))
    stated = {
        (record.assertions[index].namespace, record.assertions[index].value)
        for record in records
        for index in range(len(record.assertions))
    }
    assert (IdentifierNamespace.ISIN, NSE_ISIN) in stated
    assert (IdentifierNamespace.NSE_SYMBOL, NSE_SYMBOL) in stated
    assert (IdentifierNamespace.BSE_SCRIP, BSE_SCRIP) in stated


def test_listed_rows_join_by_identifier_and_never_by_name(tmp_path: Path) -> None:
    """A company name is not an identifier; no assertion may be built from one."""
    records = load_upstox_records(_write_catalog(tmp_path, nse_equity_row()))
    name = nse_equity_row()["name"]
    assert all(assertion.value != name for record in records for assertion in record.assertions)
    assert records[0].display_name == name


def test_one_record_is_emitted_per_isin_not_per_row(tmp_path: Path) -> None:
    """A dual-listed issuer is one security stated twice, not two securities."""
    dual = bse_equity_row(isin=NSE_ISIN, instrument_key=f"BSE_EQ|{NSE_ISIN}")
    records = load_upstox_records(_write_catalog(tmp_path, nse_equity_row(), dual))
    assert len(records) == 1
    namespaces = {assertion.namespace for assertion in records[0].assertions}
    assert namespaces == {
        IdentifierNamespace.ISIN,
        IdentifierNamespace.NSE_SYMBOL,
        IdentifierNamespace.BSE_SCRIP,
    }


def test_nothing_is_ever_reported_absent_because_our_own_filter_may_have_emptied_it(
    tmp_path: Path,
) -> None:
    """A filtered view cannot honestly assert what the vendor did not publish.

    The map treats ``reported_absent`` as a claim about the company, conflicting
    with any source that does assert a value and making the entity unreachable.
    We retain only ``NSE_EQ``/``EQ`` and ``BSE_EQ``/``A`` rows, so a security in
    another BSE group is missing from our rows because we dropped it. Reporting
    that as vendor silence would state our filter as the vendor's claim.
    """
    records = load_upstox_records(_write_catalog(tmp_path, nse_equity_row()))
    assert records[0].reported_absent == ()


def test_a_pin_the_catalog_holds_no_row_for_is_not_made_unreachable(tmp_path: Path) -> None:
    """The regression this adapter's absence rule exists to prevent.

    A stock pinned with a BSE scrip that our filtered catalog holds no BSE row
    for must stay reachable. Under a ``reported_absent`` claim the two sources
    would disagree, the entity would be marked conflicted, and Slice 1 would
    have removed a lookup path while claiming to add one.
    """
    symbol = "NSEONLYCO"
    pinned = emf.Pin(
        name="NSE Only Company Limited",
        nse_symbol=symbol,
        bse_scrip="590996",
        screener_slug=symbol,
        screener_company_id=9100097,
        screener_warehouse_id_standalone=9200097,
        tijori_slug=symbol,
        tijori_company_id=9300097,
    )
    config_path = emf.write_s2_config(tmp_path, [pinned])
    catalog_path = _write_catalog(
        tmp_path,
        nse_equity_row(trading_symbol=symbol, isin=NSE_ISIN, instrument_key=f"NSE_EQ|{NSE_ISIN}"),
    )
    built = build_entity_map(load_s2_records(config_path) + load_upstox_records(catalog_path))
    assert built.conflicts == ()
    assert built.lookup(IdentifierNamespace.BSE_SCRIP, "590996") is not None


def test_every_assertion_is_marked_verified(tmp_path: Path) -> None:
    """A load-bearing choice, stated rather than defaulted into.

    ``EntityMap.lookup`` gates on ``verified``. Marking these true is justified
    by what the file is: a self-describing current-state bulk export publishing
    the ISIN and the exchange code side by side on one row *is* the
    confirmation, within the snapshot it describes.
    """
    records = load_upstox_records(_write_catalog(tmp_path, nse_equity_row()))
    assert all(assertion.verified for assertion in records[0].assertions)


def test_every_assertion_is_anchored_to_the_api_document_it_was_read_from(
    tmp_path: Path,
) -> None:
    """An API value is re-found by issuing the GET, so the anchor names it."""
    records = load_upstox_records(_write_catalog(tmp_path, nse_equity_row()))
    provenance = records[0].assertions[0].provenance
    assert provenance.source_id == UPSTOX_SOURCE_ID
    assert provenance.anchor_type is SourceAnchorType.API_DOCUMENT
    assert provenance.document_id is not None
    assert provenance.context_ref is not None
    assert provenance.row_label == f"NSE_EQ|{NSE_ISIN}"
    assert provenance.column_label == "isin"
    assert provenance.island_id is None


def test_the_retrieval_time_comes_from_the_artifact_content_not_the_filesystem(
    tmp_path: Path,
) -> None:
    """An mtime is restamped by any clone, so CI could never match a local build."""
    path = _write_catalog(tmp_path, nse_equity_row())
    records = load_upstox_records(path)
    recorded = json.loads(path.read_text(encoding="utf-8"))["retrieved_at"]
    assert records[0].assertions[0].provenance.retrieved_at == datetime.fromisoformat(recorded)


def test_a_caller_supplied_stamp_overrides_the_recorded_one(tmp_path: Path) -> None:
    """The caller's stamp wins where one is given, matching the other adapters."""
    stamp = datetime(2027, 3, 1, tzinfo=UTC)
    records = load_upstox_records(_write_catalog(tmp_path, nse_equity_row()), retrieved_at=stamp)
    assert records[0].assertions[0].provenance.retrieved_at == stamp


def test_a_catalog_that_did_not_publish_a_complete_result_is_refused(tmp_path: Path) -> None:
    """A drifted catalog read as evidence would report every pin uncovered.

    That is the failure mode ``IncompleteEvidenceError`` exists for: a run that
    stopped short records no membership, and iterating its empty rows would turn
    a failed acquisition into a clean map.
    """
    from fundamentals.contracts.entity_identity import IncompleteEvidenceError

    path = _write_catalog(tmp_path, derivative_row())
    with pytest.raises(IncompleteEvidenceError):
        load_upstox_records(path)


def test_suspended_rows_emit_no_entity_assertions(tmp_path: Path) -> None:
    """The suspended file is retained evidence of suspension and nothing more.

    It has no code consumer by design: a matching report whose matches nobody may
    act on is a deliverable in search of a user.
    """
    catalog = read_suspended_catalog(
        suspended_fetch([suspended_row()]), max_decompressed_bytes=_CAP
    )
    path = tmp_path / "upstox_suspended.parsed.json"
    path.write_text(catalog.model_dump_json(), encoding="utf-8")
    with pytest.raises(ValueError, match="suspended"):
        load_upstox_records(path)


def test_the_adapter_opens_no_socket(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An entity-map build must stay offline, exactly as the two other adapters are."""
    import socket

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("the entity adapter opened a socket")

    monkeypatch.setattr(socket, "socket", refuse)
    assert load_upstox_records(_write_catalog(tmp_path, nse_equity_row()))


def test_isin_less_pinned_symbol_gains_its_isin_and_rekeys_without_refusal(
    tmp_path: Path,
) -> None:
    """The whole point of Slice 1, run end to end.

    A stock pinned by NSE symbol with no ISIN is keyed ``nse:<symbol>``. Adding
    the Upstox row supplies the ISIN, which re-keys the entity — and this
    asserts the join survives that transition rather than tripping one of
    ``build_entity_map``'s refusals.
    """
    symbol = "PINNEDCO"
    pinned = emf.Pin(
        name="Pinned Company Limited",
        nse_symbol=symbol,
        bse_scrip="590998",
        screener_slug=symbol,
        screener_company_id=9100099,
        screener_warehouse_id_standalone=9200099,
        tijori_slug=symbol,
        tijori_company_id=9300099,
    )
    config_path = emf.write_s2_config(tmp_path, [pinned])
    before = build_entity_map(load_s2_records(config_path))
    keyed_by_symbol = before.lookup(IdentifierNamespace.NSE_SYMBOL, symbol)
    assert keyed_by_symbol is not None
    assert keyed_by_symbol.key == f"nse:{symbol}"

    catalog_path = _write_catalog(
        tmp_path,
        nse_equity_row(trading_symbol=symbol, isin=NSE_ISIN, instrument_key=f"NSE_EQ|{NSE_ISIN}"),
    )
    after = build_entity_map(load_s2_records(config_path) + load_upstox_records(catalog_path))

    rekeyed = after.lookup(IdentifierNamespace.NSE_SYMBOL, symbol)
    assert rekeyed is not None
    assert rekeyed.key == NSE_ISIN
    assert after.lookup(IdentifierNamespace.ISIN, NSE_ISIN) is rekeyed
    assert not after.conflicts


def test_a_pinned_symbol_the_file_does_not_carry_is_left_alone(tmp_path: Path) -> None:
    """An Upstox catalog adds identity; it never removes or re-keys what it lacks."""
    pinned = emf.Pin(
        name="Unlisted Company Limited",
        nse_symbol="ABSENTCO",
        bse_scrip="590997",
        screener_slug="ABSENTCO",
        screener_company_id=9100098,
        screener_warehouse_id_standalone=9200098,
        tijori_slug="ABSENTCO",
        tijori_company_id=9300098,
    )
    config_path = emf.write_s2_config(tmp_path, [pinned])
    catalog_path = _write_catalog(tmp_path, nse_equity_row())
    built = build_entity_map(load_s2_records(config_path) + load_upstox_records(catalog_path))
    still_pinned = built.lookup(IdentifierNamespace.NSE_SYMBOL, "ABSENTCO")
    assert still_pinned is not None
    assert still_pinned.key == "nse:ABSENTCO"


def test_records_are_ordered_by_isin_so_a_build_is_reproducible(tmp_path: Path) -> None:
    """Two runs over identical bytes must emit identical records in identical order."""
    rows = [bse_equity_row(), nse_equity_row()]
    first = load_upstox_records(_write_catalog(tmp_path, *rows))
    assert [record.assertions[0].value for record in first] == sorted({NSE_ISIN, BSE_ISIN})
