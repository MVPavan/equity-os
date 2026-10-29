"""Models select offsets; code alone extracts and persists retained text."""

from pathlib import Path
from unittest.mock import Mock

import pytest
from retention_support import record_of
from test_vendor_values_store import outcome

from fundamentals.ingest.vendor_surface_fetch import Fetched, Site
from fundamentals.ingest.vendor_surface_model import ModelReply, ModelSettings
from fundamentals.store.snapshot_store import SnapshotStore
from fundamentals.store.vendor_values_store import ParserVersionDrift, VendorValuesStore, register


@pytest.mark.parametrize(
    "reply,expected,rejected",
    [
        ('[{"kind":"NAME","start":0,"end":4}]', [("NAME", 0, 4)], 0),
        ('[{"kind":"CLAIM","start":-1,"end":4}]', [], 1),
        ('[{"kind":"NAME","start":0,"end":99}]', [], 1),
        ('[{"kind":"NAME","start":2,"end":2}]', [], 1),
        ('[{"kind":"NAME","start":0,"end":4,"text":"invented 99"}]', [], 1),
        ('[{"kind":"NAME","start":true,"end":4}]', [], 1),
        ("not JSON", [], 1),
        ("[]", [], 0),
        (
            '[{"kind":"NAME","start":0,"end":4},{"kind":"NAME","start":2,"end":5},'
            '{"kind":"CLAIM","start":0,"end":4},{"kind":"NAME","start":4,"end":5}]',
            [("NAME", 0, 4), ("CLAIM", 0, 4), ("NAME", 4, 5)],
            1,
        ),
    ],
)
def test_only_valid_nonoverlapping_source_offsets_survive(reply, expected, rejected):
    from fundamentals.ingest.vendor_surface_claims import validate_spans

    spans, count = validate_spans("Acme grows", reply)
    assert [(s.kind, s.start, s.end) for s in spans] == expected
    assert count == rejected


@pytest.mark.parametrize(
    "surface,markup,expected",
    [
        (
            "company-page",
            '<div class="company-info"><div class="about"><p>Acme  grows</p></div>'
            '<div class="commentary"><p>Builds cables</p></div><p>Ignore ratios</p></div>',
            "Acme grows Builds cables",
        ),
        (
            "company-announcements",
            '<ul class="list-links"><li><a href="/doc">New plant'
            "<div><time>Yesterday</time></div></a></li></ul>",
            "New plant",
        ),
        (
            "announcements-feed",
            '<div class="announcement-item"><a href="/company/X/">Acme</a>'
            '<a href="https://exchange.example/doc">New plant<time>Today</time></a></div>',
            "New plant",
        ),
    ],
)
def test_source_regions_exclude_controls_dates_and_other_cells(surface, markup, expected):
    from fundamentals.ingest.vendor_surface_claims import source_text

    assert source_text(Site.SCREENER, surface, markup.encode()) == expected


@pytest.mark.retained
def test_retained_aparinds_about_is_selected_without_other_page_sections():
    from fundamentals.ingest.screener_session_page import parse_document
    from fundamentals.ingest.vendor_surface_claims import source_text

    raw = Path("data/raw/vendor-surface/2026-10-28/screener/company-page.html").read_bytes()
    source = source_text(Site.SCREENER, "company-page", raw)
    tree = parse_document(raw.decode())
    about = tree.xpath('//div[contains(concat(" ",@class," ")," about ")]')[0]
    assert source.startswith(" ".join(about.text_content().split()))
    assert len(source) > len(" ".join(about.text_content().split()))


@pytest.mark.pg
@pytest.mark.parametrize("valid", [True, False])
def test_fake_model_claims_and_zero_span_outcomes_are_atomic_and_idempotent(pg_db, tmp_path, valid):
    from fundamentals.ingest.vendor_surface_claims import extract_text

    raw = b'<div class="company-info"><div class="about">Acme grows 12%</div></div>'
    store = SnapshotStore(tmp_path / "store")
    record = record_of(raw, "screener-subscriber", "vs.company-page")
    store.put_capture(record, raw)
    settings = ModelSettings(
        model_id="fake",
        base_url="https://unused.example",
        key_file="unused",
        prompt_version="spans.v1",
        dictionary_version="v3",
    )
    model = Mock(model_id="fake")
    model.complete.return_value = ModelReply(
        text='[{"kind":"CLAIM","start":0,"end":%s}]' % (14 if valid else 99),
        input_tokens=1,
        output_tokens=1,
    )
    with pg_db.runtime_pool() as pool:
        ref = register(
            pool, Fetched(record=record, url="https://www.screener.in/company/X/", location=None)
        )
        values = VendorValuesStore(pool)
        values.record(
            ref,
            outcome(version="screener:company-page.v1", surface="company-page", values=()),
            row_count=0,
        )
        with pool.connection() as conn:
            conn.execute(
                "INSERT INTO eqos.vendor_parser_versions VALUES (%s,%s)",
                ("claims:fake:rollback", "b" * 64),
            )
        with pytest.raises(ParserVersionDrift):
            extract_text(
                pool, store, model, settings.model_copy(update={"prompt_version": "rollback"})
            )
        with pool.connection() as conn:
            assert conn.execute("SELECT count(*) FROM eqos.vendor_text_claims").fetchone() == (0,)
            assert conn.execute(
                "SELECT count(*) FROM eqos.vendor_outcomes WHERE parser_version=%s",
                ("claims:fake:rollback",),
            ).fetchone() == (0,)
        model.complete.reset_mock()
        assert extract_text(pool, store, model, settings) == 1
        assert extract_text(pool, store, model, settings) == 0
        assert model.complete.call_count == 1
        with pool.connection() as conn:
            assert conn.execute(
                "SELECT text,epistemic_class,span_start,span_end FROM eqos.vendor_text_claims"
            ).fetchall() == ([("Acme grows 12%", "inferred", 0, 14)] if valid else [])
            assert conn.execute(
                "SELECT row_count,rejected_count FROM eqos.vendor_outcomes "
                "WHERE parser_version='claims:fake:spans.v1'"
            ).fetchone() == (int(valid), int(not valid))


def test_extract_cli_refuses_unselected_model_before_io():
    from fundamentals.api.cli_parser import build_parser
    from fundamentals.api.vendor_surface_cli import dispatch_vendor_command

    refused = Mock(side_effect=AssertionError("no I/O before owner selection"))
    args = build_parser().parse_args(["vendor", "extract-text"])
    assert dispatch_vendor_command(args, pool_factory=refused, opener_factory=refused) == 2


@pytest.mark.pg
def test_extraction_outcome_cannot_mask_a_cell_yield_drop(pg_db, tmp_path):
    from datetime import UTC, datetime, timedelta

    from fundamentals.contracts.snapshot import CaptureRecord
    from fundamentals.ingest.vendor_surface_canary import yield_drift
    from fundamentals.ingest.vendor_surface_claims import extract_text

    raw = b'<div class="company-info"><div class="about">Acme grows</div></div>'
    store = SnapshotStore(tmp_path / "store")
    base = record_of(raw, "screener-subscriber", "vs.company-page")
    settings = ModelSettings(
        model_id="fake",
        base_url="https://unused.example",
        key_file="unused",
        prompt_version="spans.v1",
        dictionary_version="v3",
    )
    model = Mock(model_id="fake")
    model.complete.return_value = ModelReply(text="[]", input_tokens=1, output_tokens=1)
    with pg_db.runtime_pool() as pool:
        values = VendorValuesStore(pool)
        for seconds, count in ((0, 10), (1, 4)):
            record = CaptureRecord.make(
                base.request,
                base.retrieved_at + timedelta(seconds=seconds),
                200,
                "text/html",
                None,
                base.body,
                base.outcome,
                base.rights,
            )
            store.put_capture(record, raw)
            ref = register(
                pool,
                Fetched(record=record, url="https://www.screener.in/company/X/", location=None),
            )
            cell = outcome(version="screener:company-page.v1", surface="company-page", values=())
            values.record(ref, cell, row_count=count)
        assert extract_text(pool, store, model, settings) == 2
        drift = yield_drift(pool, datetime(2000, 1, 1, tzinfo=UTC))
    assert [(d.surface, d.check, d.detail) for d in drift] == [
        ("company-page", "ROW_COUNT_DROP", "10 -> 4 rows")
    ]
