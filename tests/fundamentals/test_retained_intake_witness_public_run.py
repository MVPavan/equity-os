"""Joined witness/vendor public run and manifest-only replay, explicitly synthetic."""

import hashlib
import json
from pathlib import Path

import pytest
import vendor_runs_support
from pg_support import PgTestDatabase
from run_support import SpyReader, forbid_current_reads
from vendor_runs_support import build_case

from fundamentals.compare.run import load_results
from fundamentals.contracts.canonical import Basis, Representation
from fundamentals.contracts.evidence import FilingFamily
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.evidence.capture_intake import retained_intake_from_manifest
from fundamentals.evidence.first_party_generation import append_first_party_generation
from fundamentals.store.snapshot_store import SnapshotStore

pytestmark = pytest.mark.pg


def test_synthetic_witness_vendor_public_run_replays_from_only_frozen_ids(
    pg_db: PgTestDatabase, tmp_path: Path, monkeypatch
) -> None:
    """No actual issuer/vendor equivalence, source rights or financial oracle is claimed."""
    original_append = vendor_runs_support.append_first_party_generation
    source_inputs = []

    def observe_original_input(**kwargs):
        source_inputs.append(kwargs["intake"])
        return original_append(**kwargs)

    monkeypatch.setattr(
        vendor_runs_support, "append_first_party_generation", observe_original_input
    )
    with pg_db.runtime_pool() as pool:
        case = build_case(pg_db, pool, tmp_path)
        root, inputs, config = case.producer_case[:3]
        body = (inputs / "synthetic-first-party.xml").read_bytes()
        (inputs / "nse").mkdir()
        (inputs / "nse" / "synthetic-first-party.xml").write_bytes(body)
        manifest = tmp_path / "synthetic-original-intake.json"
        manifest.write_text(
            json.dumps(
                {
                    "issuer": "FIXTURECO",
                    "authorization": "SYNTHETIC witness mechanism only; no actual source authority",
                    "entries": [
                        {
                            "quarter": "FY26_Q2",
                            "kind": "xbrl-consolidated",
                            "filename": "synthetic-first-party.xml",
                            "sha256": hashlib.sha256(body).hexdigest(),
                            "filed_at_nse": source_inputs[0].bindings[0].filed_at_raw,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        store_root = tmp_path / "synthetic-snapshots"
        intake = retained_intake_from_manifest(
            manifest,
            issuer="FIXTURECO",
            quarter="FY26_Q2",
            kinds={Representation.XBRL: "xbrl-consolidated"},
            store_root=store_root,
            input_root=inputs,
            issuer_config=root / "fixtureco-fy26-q2.yaml",
        )
        case.first_party = append_first_party_generation(
            intake=intake,
            snapshot_store=SnapshotStore(store_root),
            pool=pool,
            config=config,
            config_root=root,
            entity_id=case.first_party.entity_id,
            basis=Basis.CONSOLIDATED,
            framework=AccountingFramework.IND_AS,
            family=FilingFamily.FINANCIAL_RESULTS,
            reporting_period_end=case.first_party.reporting_period_end,
            pdf_specs=None,
            retain_intake_witness=True,
        )
        witness_id = case.first_party.retained_intake_witness_id
        assert witness_id is not None
        record = case.execute()
        stored = load_results(record.run_id, pool=pool)
        assert any(
            item.ref_id == witness_id and item.kind.value == "EVIDENCE_INPUT"
            for item in record.manifest.inputs
        )
        assert record.queue_overlay is not None
        assert any(row.pairs for row in stored)
        spy = SpyReader(case.repository)
        before = case.counts()
        forbid_current_reads(monkeypatch)

        def forbidden(*args, **kwargs):
            raise AssertionError("witnessed public replay read original filesystem metadata")

        # Replay still loads its normal version-pinned config. Original intake
        # source preparation is forbidden independently of that legitimate load.
        monkeypatch.setattr(
            "fundamentals.evidence.retained_intake_source.prepare_retained_intake_witness",
            forbidden,
        )
        replayed = case.replay(record.run_id, reader=spy)
        assert replayed == stored
        assert spy.calls
        assert case.counts() == before
