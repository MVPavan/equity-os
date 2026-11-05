"""PREP-5 helpers shared by the rework, corrected-filing and PREP-6 tests: a FY26_Q2 rerun and
a corrected FY26_Q1 comparator filing."""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Callable
from datetime import date
from functools import partial
from pathlib import Path
from typing import Any

import yaml
from evidence_support import Ingest
from prep2b_support import COMPARATOR_KIND, STOCK, Pilot
from retained_support import (
    APAR_MANIFEST,
    INPUTS_DIR,
    STORE_DIR,
    XBRL_DIR,
    apar_original,
    manifest_entry,
)

from equity_os.contracts.measurement.canonical import Representation
from equity_os.extraction.packages.capture_intake import retained_intake_from_manifest
from equity_os.extraction.xbrl.xbrl_adapter import parse_instance
from equity_os.extraction.xbrl.xbrl_parser import RawXbrlFact
from equity_os.interface.commands.publication.ledger_cli import DEFAULT_IMPORT_CONFIG
from equity_os.interface.entry.cli import _build_parser, run_command
from equity_os.interface.workflows.pipeline import PipelineResult

Q1 = "FY26_Q1"
CORRECTED_KIND = "xbrl-consolidated-comparator-corrected"
# FY26_Q1's consolidated revenue from operations as its comparator filing states it, in ₹.
Q1_REVENUE = 51_041_600_000
REVENUE_FACT = b'<in-capmkt:RevenueFromOperations contextRef="OneD" decimals="-5" unitRef="INR">%d<'
CRORE = 10**7
LATE = "01-Dec-2025 10:00:00"  # after FY26_Q2's source cutoff


def _rerun(
    pilot: Pilot,
    *flags: str,
    edit: Callable[[dict[str, Any]], None] | None = None,
    manifest: Path = APAR_MANIFEST,
) -> PipelineResult:
    """FY26_Q2 run again on ``manifest``; ``edit`` corrects its config first (a new approved
    config, A3)."""
    context, argv = pilot.registered("FY26_Q2")
    if edit is not None:
        path = Path(argv[argv.index("--config") + 1])
        body = yaml.safe_load(path.read_text(encoding="utf-8"))
        edit(body)
        path.write_text(yaml.safe_dump(body, allow_unicode=True), encoding="utf-8")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        context = dataclasses.replace(context, approved_config_sha256=digest)
    args = _build_parser().parse_args([*argv, "--retrospective", str(manifest), *flags])
    return run_command(args, intake_context=context)


def _facts(body: bytes, ingest: Ingest) -> tuple[RawXbrlFact, ...]:
    """Every fact of an instance as evidence ingest reads it."""
    return parse_instance(body, mapping_set=ingest.mapping_set).facts


def _correct(
    pilot: Pilot, ingest: Ingest, *, filed_at: str | None = None, original: bool = True
) -> tuple[str, Callable[[], PipelineResult]]:
    """FY26_Q1's comparator restated with revenue ₹100 crore higher, published (by default) when
    the original was, entered in a copy of the retrieval manifest the run is pinned to and
    evidence-ingested; returns its digest and the FY26_Q2 rerun pointing ``comparators.qoq`` at
    it. ``original=False`` drops the original filing from the manifest copy."""
    entry = manifest_entry(Q1, COMPARATOR_KIND)
    body = apar_original(Q1, COMPARATOR_KIND).read_bytes()
    assert body.count(REVENUE_FACT % Q1_REVENUE) == 1
    corrected = body.replace(REVENUE_FACT % Q1_REVENUE, REVENUE_FACT % (Q1_REVENUE + 100 * CRORE))
    pairs = zip(_facts(body, ingest), _facts(corrected, ingest), strict=True)
    changed = [new for old, new in pairs if old != new]
    assert [fact.raw_text for fact in changed] == [str(Q1_REVENUE + 100 * CRORE)]
    path = pilot.tmp_path / INPUTS_DIR / XBRL_DIR / f"corrected-{entry['filename']}"
    path.write_bytes(corrected)
    sha = hashlib.sha256(corrected).hexdigest()
    manifest = json.loads(APAR_MANIFEST.read_text(encoding="utf-8"))
    if not original:
        manifest["entries"] = [e for e in manifest["entries"] if e["sha256"] != entry["sha256"]]
    manifest["entries"].append(
        entry
        | {"kind": CORRECTED_KIND, "filename": path.name, "sha256": sha, "bytes": len(corrected)}
        | {"filed_at_nse": filed_at or entry["filed_at_nse"]}
    )
    copy = pilot.tmp_path / "retrieval-manifest-corrected.json"
    copy.write_text(json.dumps(manifest), encoding="utf-8")
    pin = pilot.tmp_path / DEFAULT_IMPORT_CONFIG
    text = pin.read_text(encoding="utf-8")
    pinned = hashlib.sha256(APAR_MANIFEST.read_bytes()).hexdigest()
    assert text.count(pinned) == 1
    pin.write_text(text.replace(pinned, hashlib.sha256(copy.read_bytes()).hexdigest()))
    intake = retained_intake_from_manifest(
        copy,
        issuer=STOCK,
        quarter=Q1,
        kinds={Representation.XBRL: CORRECTED_KIND},
        store_root=(pilot.tmp_path / STORE_DIR).absolute(),
        input_root=(pilot.tmp_path / INPUTS_DIR).absolute(),
        issuer_config=None,
    )
    ingest.run(intake, date(2025, 6, 30))

    def point(config: dict[str, Any]) -> None:
        config["comparators"]["qoq"] |= {"local_path": str(path), "sha256": sha}

    return sha, partial(_rerun, pilot, edit=point, manifest=copy)
