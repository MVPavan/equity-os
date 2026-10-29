"""Code controls proposals; the provider is always fake in these tests."""

import io
import json
from unittest.mock import Mock
from urllib.error import URLError
from urllib.request import OpenerDirector

import pytest
from pydantic import SecretStr
from test_vendor_values_store import outcome, setup_store

from fundamentals.contracts.canonical import ValueKind
from fundamentals.ingest.vendor_surface_cells import LabelSample
from fundamentals.ingest.vendor_surface_fetch import Site
from fundamentals.ingest.vendor_surface_labels import accept, map_labels
from fundamentals.ingest.vendor_surface_model import ChatCompletionsModel, ModelReply, ModelSettings


@pytest.mark.parametrize(
    "label,units,per_share,reply,reason",
    [
        ("Sales", {"₹ Cr"}, False, '{"label":"Sales","field":"sales"}', "MAPPED"),
        ("Sales", {"₹ Cr"}, False, '{"label":"sales","field":"sales"}', "LABEL_ALTERED"),
        ("Sales", {"₹ Cr"}, False, '{"label":"Sales","field":"unknown"}', "NOT_IN_DICTIONARY"),
        ("Margin", {"%"}, False, '{"label":"Margin","field":"sales"}', "UNIT_INCOMPATIBLE"),
        ("EPS (₹)", {"₹"}, True, '{"label":"EPS (₹)","field":"eps"}', "MAPPED"),
        (
            "Sales (₹ Cr)",
            {"Cr"},
            False,
            '{"label":"Sales (₹ Cr)","field":"eps"}',
            "UNIT_INCOMPATIBLE",
        ),
        ("Sales", {"Cr"}, False, "not JSON", "MALFORMED_REPLY"),
        ("Sales", {"Cr"}, False, '{"label":"Sales","field":null}', "MODEL_UNMAPPED"),
        ("Sales", {"Cr", "%"}, False, '{"label":"Sales","field":"sales"}', "UNIT_INCOMPATIBLE"),
        ("EPS", {"%"}, True, '{"label":"EPS","field":"eps"}', "UNIT_INCOMPATIBLE"),
        ("Sales", {""}, False, '{"label":"Sales","field":"sales"}', "UNIT_INCOMPATIBLE"),
        ("Sales", {"Cr"}, False, '{"label":"Sales","field":"sales","value":9}', "MALFORMED_REPLY"),
        *(
            ("Sales", {unit}, False, '{"label":"Sales","field":"sales"}', "MAPPED")
            for unit in ("INR Crore", "Rs crore", "Crs", "₹ crores")
        ),
        ("Sales", {"Crs", "MW"}, False, '{"label":"Sales","field":"sales"}', "UNIT_INCOMPATIBLE"),
        ("Sales", {"MW"}, False, '{"label":"Sales","field":"sales"}', "UNIT_INCOMPATIBLE"),
    ],
)
def test_code_acceptance(label, units, per_share, reply, reason):
    field, actual = accept(
        LabelSample(label=label, units=frozenset(units), per_share=per_share),
        reply,
        {"sales": ValueKind.CURRENCY_AMOUNT, "eps": ValueKind.PER_SHARE_AMOUNT},
    )
    assert actual == reason
    assert field == (json.loads(reply)["field"] if reason == "MAPPED" else None)


@pytest.mark.pg
def test_fake_mapping_persistence_and_corrections(pg_db, tmp_path):
    reply = '{"label":"Sales","field":"sales"}'
    model = Mock(model_id="fake")
    model.complete.return_value = ModelReply(text=reply, input_tokens=1, output_tokens=1)
    settings = ModelSettings(
        model_id="fake",
        base_url="https://unused.example/v1",
        key_file="unused",
        prompt_version="v1",
        dictionary_version="v3",
    )
    _, pool, ref, values = setup_store(pg_db, tmp_path)
    cell = outcome().values[0]
    cell = cell.model_copy(
        update={"row_label": "Sales", "unit": "Cr", "column_index": 1, "expected_numeric": True}
    )
    fields = {"sales": ValueKind.CURRENCY_AMOUNT}
    mapping = (pool, model, settings, Site.TIJORI, "chart-api", fields)
    correction = (
        "INSERT INTO eqos.vendor_label_proposals (source_id,surface,label,units,reason,"
        "model_id,prompt_version,dictionary_version,prompt,raw_response) VALUES "
        "('tijori','chart-api','Sales','{Cr}','MODEL_UNMAPPED','correction:owner','v1','v3','','')"
    )
    with pool:
        values.record(ref, outcome(values=(cell,)), row_count=1)
        assert map_labels(*mapping) == 1 and map_labels(*mapping) == 0
        assert model.complete.call_count == 1
        sent = json.loads(model.complete.call_args.args[1])
        assert set(sent) == {"label", "units", "per_share", "fields"}
        with pool.connection() as conn:
            row = conn.execute(
                "SELECT field,reason,epistemic_class,model_id,prompt_version,"
                "dictionary_version,prompt,raw_response FROM eqos.vendor_label_proposals"
            ).fetchone()
            assert row[:6] == ("sales", "MAPPED", "inferred", "fake", "v1", "v3")
            assert json.loads(row[6])["system"] and row[7] == reply
            conn.execute(correction)
            assert conn.execute(
                "SELECT field,model_id FROM eqos.vendor_label_proposals ORDER BY id DESC LIMIT 1"
            ).fetchone() == (None, "correction:owner")


@pytest.mark.parametrize(
    "command",
    [
        ["map-labels", "--site", "tijori", "--surface", "company-benchmarking"],
        ["extract-text"],
    ],
)
def test_cli_refuses_unselected_model_without_opening_boundaries(command):
    from fundamentals.api.cli_parser import build_parser
    from fundamentals.api.vendor_surface_cli import dispatch_vendor_command

    args = build_parser().parse_args(["vendor", *command])
    refused = Mock(side_effect=AssertionError("unselected model must refuse before I/O"))
    assert dispatch_vendor_command(args, pool_factory=refused, opener_factory=refused) == 2


@pytest.mark.parametrize("failure", [None, "bytes", "tokens", "retry"])
def test_adapter_bounds_with_fake_transport(monkeypatch, failure):
    payload = (
        b'{"choices":[{"finish_reason":"stop","message":{"content":"reply"}}],'
        b'"usage":{"prompt_tokens":2,"completion_tokens":1}}'
    )
    opened = (
        Mock(side_effect=URLError("synthetic"))
        if failure == "retry"
        else Mock(return_value=io.BytesIO(payload))
    )
    monkeypatch.setattr(OpenerDirector, "open", opened)
    model = ChatCompletionsModel(
        "fake",
        "https://unused.example/v1",
        SecretStr("synthetic"),
        max_response_bytes=1 if failure == "bytes" else 200_000,
        max_output_tokens=0 if failure == "tokens" else 512,
    )
    if failure:
        with pytest.raises(URLError if failure == "retry" else ValueError):
            model.complete("system", "user")
    else:
        assert model.complete("system", "user") == ModelReply(
            text="reply", input_tokens=2, output_tokens=1
        )
    assert opened.call_count == (3 if failure == "retry" else 1)


@pytest.mark.pg
@pytest.mark.parametrize(
    "site,surface",
    [
        (Site.SCREENER, "section-insights"),
        (Site.TIJORI, "benchmarking-benchmarking-financial"),
        (Site.TIJORI, "benchmarking-benchmarking-business"),
        (Site.SCREENER, "company-compare"),
        (Site.TIJORI, "company-benchmarking"),
    ],
)
def test_cli_maps_logical_g3_labels(pg_db, tmp_path, monkeypatch, site, surface):
    from types import SimpleNamespace
    from retention_support import record_of
    from fundamentals.api import vendor_surface_cli as cli
    from fundamentals.api.cli_parser import build_parser
    from fundamentals.ingest.vendor_surface_fetch import Fetched
    from fundamentals.ingest.vendor_surface_specs import SITE_NAME
    from fundamentals.store.snapshot_store import SnapshotStore
    from fundamentals.store.vendor_values_store import VendorValuesStore, register

    settings = tmp_path / "model.yaml"
    settings.write_text(
        "model_id: fake\nbase_url: https://unused.example\nkey_file: fake.key\nprompt_version: v1\ndictionary_version: v3\n"
    )
    (tmp_path / "fake.key").write_text("synthetic")
    monkeypatch.setattr(cli, "MODEL_CONFIG", settings)
    monkeypatch.setenv("EQOS_SECRETS_DIR", str(tmp_path))
    model = Mock(model_id="fake")
    model.complete.return_value = ModelReply(
        text='{"label":"Sales","field":"sales"}', input_tokens=1, output_tokens=1
    )
    monkeypatch.setattr(cli, "ChatCompletionsModel", lambda *a: model)
    monkeypatch.setattr(
        cli,
        "load_dictionary",
        lambda *a: SimpleNamespace(
            rows=[SimpleNamespace(canonical_id="sales", value_kind=ValueKind.CURRENCY_AMOUNT)]
        ),
    )
    store = SnapshotStore(tmp_path / "store")
    record = record_of(b"fixture", site, "vs.company-benchmarking")
    store.put_capture(record, b"fixture")
    with pg_db.runtime_pool() as pool:
        ref = register(pool, Fetched(record=record, url="https://unused.example/", location=None))
        cell = (
            outcome()
            .values[0]
            .model_copy(update={"row_label": "Sales", "unit": "Cr", "expected_numeric": True})
        )
        VendorValuesStore(pool).record(ref, outcome(surface=surface, values=(cell,)), row_count=1)
    args = build_parser().parse_args(
        ["vendor", "map-labels", "--site", SITE_NAME[site], "--surface", surface]
    )
    assert cli.dispatch_vendor_command(args, pool_factory=pg_db.runtime_pool) == 0
    assert model.complete.call_count == 1
    with pg_db.runtime_pool() as pool, pool.connection() as conn:
        assert conn.execute(
            "SELECT source_id,surface,reason FROM eqos.vendor_label_proposals"
        ).fetchall() == [(site, surface, "MAPPED")]
