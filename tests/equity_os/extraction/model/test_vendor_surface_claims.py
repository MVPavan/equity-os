"""Models select offsets; code alone extracts and persists retained text."""

import hashlib
import inspect
from pathlib import Path
from unittest.mock import Mock

import pytest
from retention_support import record_of
from test_vendor_values_store import outcome

from equity_os.extraction.model.vendor_surface_model import ModelReply, ModelSettings
from equity_os.sourcing.surfaces.vendor_surface_fetch import Fetched, Site
from equity_os.storage.raw_files.snapshot_store import SnapshotStore
from equity_os.storage.records.vendor_values_store import (
    ParserVersionDrift,
    VendorValuesStore,
    register,
)


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
    from equity_os.extraction.model.vendor_surface_claims import validate_spans

    spans, count = validate_spans("Acme grows", reply)
    assert [(s.kind, s.start, s.end) for s in spans] == expected
    assert count == rejected


SCREENER = "https://www.screener.in"
PAGE = '<div id="company-info" data-company-id="7" class="company-info">{}</div>'


@pytest.mark.parametrize(
    "surface,url,markup,expected,items",
    [
        (
            "company-page",
            "/company/X/consolidated/",
            PAGE.format(
                '<div class="about"><p>Acme  grows</p></div>'
                '<div class="commentary"><p>Builds cables</p></div><p>Ignore ratios</p>'
            ),
            "Acme grows Builds cables",
            [(0, 24, "SCREENER_COMPANY_ID", "7")],
        ),
        (
            "company-announcements",
            "/announcements/recent/9/",
            '<ul class="list-links"><li><a href="/doc">New plant'
            "<div><time>Yesterday</time></div></a></li></ul>",
            "New plant",
            [(0, 9, "SCREENER_COMPANY_ID", "9")],
        ),
        (
            "announcements-feed",
            "/announcements/",
            '<div class="announcement-item"><a href="/company/X/">Acme</a>'
            '<a href="https://exchange.example/doc">New  plant<time>Today</time></a></div>'
            '<div class="announcement-item"><a href="/doc">No company link</a></div>'
            '<div class="announcement-item"><a href="/company/Y/consolidated/">Bolt</a>'
            '<a href="/doc">Order win</a></div>',
            "New plant No company link Order win",
            [(0, 9, "SCREENER_SLUG", "X"), (26, 35, "SCREENER_SLUG", "Y")],
        ),
        (
            "concall-summary",
            "/concalls/summary/5/",
            '<html><body><main><div><ul><li><a href="/concalls/">C</a></li>'
            '<li><a href="/company/X/">X</a></li></ul></div><div class="card card-medium">'
            "<article><ul><li>Margins  held</li><li><p>Capex done</p></li></ul></article>"
            "</div><p>Outside region</p></main></body></html>",
            "Margins held Capex done",
            [(0, 23, "SCREENER_SLUG", "X")],
        ),
        (
            "concall-summary",
            "/concalls/summary/5/",
            '<html><body><main><div><ul><li><a href="/company/X/">X</a></li></ul></div>'
            '<div class="card"><div class="callout success"><p>Notice</p></div></div>'
            "</main></body></html>",
            "",
            [],
        ),
    ],
)
def test_readers_select_only_their_region_and_bind_each_item(surface, url, markup, expected, items):
    from equity_os.extraction.surfaces.vendor_text_readers import read_text

    read = read_text(Site.SCREENER, surface, markup.encode(), SCREENER + url)
    assert read.text == expected
    assert [(i.start, i.end, i.company.namespace, i.company.value) for i in read.items] == items


@pytest.mark.parametrize(
    "site,surface,url",
    [
        (Site.TIJORI, "company-page", SCREENER + "/company/X/"),
        (Site.SCREENER, "company-page", "https://evil.example/company/X/"),
        (Site.SCREENER, "company-announcements", SCREENER + "/announcements/recent/X/"),
        (Site.SCREENER, "concall-summary", SCREENER + "/company/X/"),
    ],
)
def test_unsupported_pairs_and_foreign_addresses_are_refused(site, surface, url):
    from equity_os.extraction.surfaces.vendor_text_readers import read_text

    with pytest.raises(ValueError):
        read_text(site, surface, PAGE.encode(), url)


@pytest.mark.retained
def test_retained_aparinds_about_is_selected_without_other_page_sections():
    from equity_os.extraction.surfaces.vendor_text_readers import read_text
    from equity_os.extraction.vendors.screener.screener_session_page import parse_document

    raw = Path("data/raw/vendor-surface/2026-10-28/screener/company-page.html").read_bytes()
    source = read_text(Site.SCREENER, "company-page", raw, SCREENER + "/company/APARINDS/").text
    tree = parse_document(raw.decode())
    about = tree.xpath('//div[contains(concat(" ",@class," ")," about ")]')[0]
    about_text = " ".join(about.text_content().split())
    selected = source.startswith(about_text) and len(source) > len(about_text)
    assert selected, "the About text is not the start of a longer reader text"


@pytest.mark.pg
@pytest.mark.parametrize("valid", [True, False])
def test_fake_model_claims_and_zero_span_outcomes_are_atomic_and_idempotent(
    pg_db, tmp_path, valid, monkeypatch
):
    from equity_os.extraction.model import vendor_surface_claims
    from equity_os.extraction.model.vendor_surface_claims import extract_text

    raw = PAGE.format('<div class="about">Acme grows 12%</div>').encode()
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
        monkeypatch.setattr(vendor_surface_claims, "PROMPT_VERSION", "rollback")
        with pytest.raises(ParserVersionDrift):
            extract_text(pool, store, model, settings)
        monkeypatch.undo()
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
                "SELECT parser_sha256 FROM eqos.vendor_parser_versions WHERE parser_version=%s",
                ("claims:fake:spans.v3",),
            ).fetchone() == (hashlib.sha256(inspect.getsource(extract_text).encode()).hexdigest(),)
            assert conn.execute(
                "SELECT row_count,rejected_count FROM eqos.vendor_outcomes "
                "WHERE parser_version='claims:fake:spans.v3'"
            ).fetchone() == (int(valid), int(not valid))


@pytest.mark.pg
def test_changed_span_prompt_reprocesses_captures_done_under_the_old_identity(pg_db, tmp_path):
    from equity_os.extraction.model.vendor_surface_claims import extract_text

    raw = PAGE.format('<div class="about">Acme grows</div>').encode()
    store = SnapshotStore(tmp_path / "store")
    record = record_of(raw, "screener-subscriber", "vs.company-page")
    store.put_capture(record, raw)
    settings = ModelSettings(
        model_id="fake",
        base_url="https://unused.example",
        key_file="unused",
        prompt_version="labels.v1",
        dictionary_version="v3",
    )
    model = Mock(model_id="fake")
    model.complete.return_value = ModelReply(
        text='[{"kind":"CLAIM","start":0,"end":10}]', input_tokens=1, output_tokens=1
    )
    with pg_db.runtime_pool() as pool:
        ref = register(
            pool, Fetched(record=record, url="https://www.screener.in/company/X/", location=None)
        )
        values = VendorValuesStore(pool)
        for version in ("screener:company-page.v1", "claims:fake:labels.v1"):
            values.record(
                ref, outcome(version=version, surface="company-page", values=()), row_count=0
            )
        assert extract_text(pool, store, model, settings) == 1
        with pool.connection() as conn:
            assert conn.execute(
                "SELECT count(*) FROM eqos.vendor_outcomes "
                "WHERE parser_version='claims:fake:spans.v3'"
            ).fetchone() == (1,)
            assert conn.execute(
                "SELECT prompt_version FROM eqos.vendor_text_claims"
            ).fetchall() == [("spans.v3",)]


@pytest.mark.pg
def test_extraction_outcome_cannot_mask_a_cell_yield_drop(pg_db, tmp_path):
    from datetime import UTC, datetime, timedelta

    from equity_os.contracts.sourcing.snapshot import CaptureRecord
    from equity_os.extraction.model.vendor_surface_claims import extract_text
    from equity_os.sourcing.surfaces.vendor_surface_canary import yield_drift

    raw = PAGE.format('<div class="about">Acme grows</div>').encode()
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
    assert [(d.surface, d.check, d.detail) for d in drift if d.check != "MISSING_OUTCOME"] == [
        ("company-page", "ROW_COUNT_DROP", "10 -> 4 rows")
    ]


@pytest.mark.pg
@pytest.mark.parametrize("failure", ["source", "model"])
def test_extraction_failures_are_recorded_continue_and_retry(pg_db, tmp_path, monkeypatch, failure):
    from equity_os.extraction.model.vendor_surface_claims import extract_text

    store = SnapshotStore(tmp_path / "store")
    settings = ModelSettings(
        model_id="fake",
        base_url="https://unused.example",
        key_file="unused",
        prompt_version="v1",
        dictionary_version="v3",
    )
    failing = True
    reads = store.read_body

    def read(record):
        if failing and failure == "source" and reads(record).endswith(b"first</div></div>"):
            raise OSError("PRIVATE_FAILURE_SENTINEL")
        return reads(record)

    def complete(system, source):
        if failing and failure == "model" and source == "first":
            raise ValueError("PRIVATE_FAILURE_SENTINEL")
        return ModelReply(text="[]", input_tokens=1, output_tokens=1)

    monkeypatch.setattr(store, "read_body", read)
    model = Mock(model_id="fake", complete=Mock(side_effect=complete))
    with pg_db.runtime_pool() as pool:
        for name in ("first", "second"):
            raw = PAGE.format(f'<div class="about">{name}</div>').encode()
            record = record_of(raw, "screener-subscriber", "vs.company-page")
            store.put_capture(record, raw)
            ref = register(
                pool,
                Fetched(
                    record=record, url=f"https://www.screener.in/company/{name}/", location=None
                ),
            )
            VendorValuesStore(pool).record(
                ref,
                outcome(version="screener:company-page.v1", surface="company-page", values=()),
                row_count=0,
            )
        assert extract_text(pool, store, model, settings) == 1
        assert extract_text(pool, store, model, settings) == 0
        with pool.connection() as conn:
            assert conn.execute(
                "SELECT status,detail,row_count FROM eqos.vendor_outcomes "
                "WHERE starts_with(parser_version,'claims:') ORDER BY id"
            ).fetchall() == [
                ("FAILED", "OSError" if failure == "source" else "ValueError", 0),
                ("OK", None, 0),
                ("FAILED", "OSError" if failure == "source" else "ValueError", 0),
            ]
        failing = False
        assert extract_text(pool, store, model, settings) == 1
        calls = model.complete.call_count
        assert extract_text(pool, store, model, settings) == 0
        assert model.complete.call_count == calls


RETAINED = Path("data/raw/snapshots/v1/screener-subscriber")
# Recorded from ``source_text`` before the (site, surface) readers replaced it: per surface, the
# sha256 over each retained capture's coordinates and its text's sha256 (no text is recorded).
TEXT_DIGESTS = {
    "company-page": (14, "a9846820398a50e3fb04ead701b7f56197c094dd34bc7296f26e861b98f12911"),
    "company-announcements": (
        9,
        "b41e6dd1f923d938ca3247e4451cc50dda52467097741130f9c9316b55146118",
    ),
    "announcements-feed": (122, "55a7d49d10f3e2430619e43ff0cc77eba2ce9f0165d2cc351356e84a084cd239"),
}
CAPTURED_BY = "20261106T170000"  # captures registered after the digests were recorded are excluded


def retained_bodies(surface):
    """Each retained Apar capture of one surface by coordinates, oldest first, up to the pin."""
    for path in sorted((RETAINED / f"vs.{surface}").glob("*/*/body.bin")):
        if path.parent.name < CAPTURED_BY:
            yield path.parent.parent.name, path.parent.name, path.read_bytes()


def registered_addresses():
    """Apar's registered addresses by request key, rebuilt from its retained company page."""
    from equity_os.extraction.vendors.screener.screener_session_page import (
        parse_document,
        read_identity,
    )
    from equity_os.sourcing.surfaces.vendor_surface_fetch import request_key

    *_, (_, _, page) = retained_bodies("company-page")
    tree = parse_document(page.decode())
    company_id, _ = read_identity(tree)
    paths = ["/company/APARINDS/", "/company/APARINDS/consolidated/"]
    paths += [f"/announcements/{kind}/{company_id}/" for kind in ("recent", "important", "search")]
    paths += tree.xpath('//*[@id="documents"]//*/@data-url')
    return {request_key(SCREENER + path): SCREENER + path for path in paths}


def retained_texts(surface):
    """Each retained capture's coordinates and reader text; feed pages share one route."""
    from equity_os.extraction.surfaces.vendor_text_readers import read_text

    urls = registered_addresses()
    for key, capture, body in retained_bodies(surface):
        url = SCREENER + "/announcements/" if surface == "announcements-feed" else urls[key]
        yield key, capture, read_text(Site.SCREENER, surface, body, url)


@pytest.mark.retained
@pytest.mark.parametrize("surface", TEXT_DIGESTS)
def test_existing_readers_text_is_unchanged_on_retained_captures(surface):
    digest, count = hashlib.sha256(), 0
    for key, capture, read in retained_texts(surface):
        digest.update(
            f"{key}/{capture}:{hashlib.sha256(read.text.encode()).hexdigest()}\n".encode()
        )
        count += 1
    assert (count, digest.hexdigest()) == TEXT_DIGESTS[surface]


@pytest.mark.retained
def test_retained_concall_summaries_are_one_item_bound_to_the_breadcrumb_company():
    reads = [read for *_, read in retained_texts("concall-summary")]
    count = len(reads)
    assert count == 56
    # One page shows a notice and has no summary region: it reads as nothing (Task 2 record).
    assert sum(not read.text and not read.items for read in reads) == 1
    for read in filter(lambda read: read.text, reads):
        [item] = read.items
        whole = (item.start, item.end) == (0, len(read.text))
        assert whole, "a concall summary item does not span the whole text"
        assert (item.company.namespace, item.company.value) == ("SCREENER_SLUG", "APARINDS")


@pytest.mark.retained
def test_print_item_and_numeral_free_item_counts_per_surface():
    from equity_os.publication.checking.numeral_scan import has_numeral

    for surface in (*TEXT_DIGESTS, "concall-summary"):
        items = [
            read.text[i.start : i.end] for *_, read in retained_texts(surface) for i in read.items
        ]
        free = sum(not has_numeral(t) for t in items)
        print(f"{surface}: items={len(items)} numeral_free={free}")  # counts only, never text
        assert items


@pytest.mark.pg
@pytest.mark.retained
def test_concall_spans_upgrade_from_v2_without_touching_earlier_rows_or_numbers(pg_db):
    from equity_os.extraction.model.vendor_surface_claims import extract_text

    store = SnapshotStore(RETAINED.parent)
    urls = registered_addresses()
    texts = {capture: read for _, capture, read in retained_texts("concall-summary")}
    notice = next(capture for capture, read in texts.items() if not read.text)
    summary = next(capture for capture, read in texts.items() if read.text)
    settings = ModelSettings(
        model_id="fake",
        base_url="https://unused.example",
        key_file="unused",
        prompt_version="spans.v1",
        dictionary_version="v3",
    )
    model = Mock(model_id="fake")
    model.complete.return_value = ModelReply(
        text='[{"kind":"CLAIM","start":0,"end":10}]', input_tokens=1, output_tokens=1
    )
    tables = ("vendor_text_claims", "vendor_outcomes", "vendor_parser_versions")
    with pg_db.runtime_pool() as pool:
        values, refs = VendorValuesStore(pool), {}
        for key, capture, _ in retained_bodies("concall-summary"):
            if capture in (notice, summary):
                record = store.get_capture(
                    "screener-subscriber", "vs.concall-summary", key, capture
                )
                refs[capture] = ref = register(
                    pool, Fetched(record=record, url=urls[key], location=None)
                )
                values.record(
                    ref,
                    outcome(version="kept.v1", surface="concall-summary", values=()),
                    row_count=0,
                )
        ref = refs[summary]
        with pool.connection() as conn:
            conn.execute(
                "INSERT INTO eqos.vendor_parser_versions VALUES ('claims:fake:spans.v2',%s)",
                ("a" * 64,),
            )
            conn.execute(
                "INSERT INTO eqos.vendor_text_claims (capture_ref_id,surface,kind,span_start,"
                "span_end,text,model_id,prompt_version,epistemic_class) "
                "VALUES (%s,'concall-summary','CLAIM',0,10,%s,'fake','spans.v2','inferred')",
                (ref.capture_ref_id, texts[summary].text[:10]),
            )
        values.record(
            ref,
            outcome(version="claims:fake:spans.v2", surface="concall-summary", values=()),
            row_count=1,
        )
        with pool.connection() as conn:
            before = {t: conn.execute(f"SELECT * FROM eqos.{t}").fetchall() for t in tables}
            occurrences = conn.execute("SELECT count(*) FROM eqos.occurrences").fetchone()
        assert extract_text(pool, store, model, settings) == 2
        assert model.complete.call_count == 1  # the notice page never reaches the model
        with pool.connection() as conn:
            for table, rows in before.items():
                after = conn.execute(f"SELECT * FROM eqos.{table}").fetchall()
                kept = set(rows) <= set(after)
                assert kept, f"{table}: an earlier row changed"
            assert conn.execute(
                "SELECT capture_ref_id,status FROM eqos.vendor_outcomes "
                "WHERE parser_version='claims:fake:spans.v3' ORDER BY capture_ref_id"
            ).fetchall() == sorted(
                [(refs[notice].capture_ref_id, "EMPTY"), (ref.capture_ref_id, "OK")]
            )
            stored = conn.execute(
                "SELECT capture_ref_id,span_start,span_end,text FROM eqos.vendor_text_claims "
                "WHERE prompt_version='spans.v3'"
            ).fetchall()
            expected = [(ref.capture_ref_id, 0, 10, texts[summary].text[:10])]
            matches = stored == expected
            assert matches, "the stored v3 claim rows differ from the expected rows"
            assert conn.execute(
                "SELECT count(*) FROM eqos.interpretations WHERE capture_ref_id IN "
                "(SELECT capture_ref_id FROM eqos.vendor_text_claims)"
            ).fetchone() == (0,)
            assert conn.execute("SELECT count(*) FROM eqos.occurrences").fetchone() == occurrences
