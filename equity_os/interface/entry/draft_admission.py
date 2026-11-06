"""The report path's first four steps before drafting (VENDOR-1 plan Task 9): static run
validation, admission, witness and package validation, then selection.

A ``fundamentals run --compare-run <id>`` admits its required facts before the pipeline, so the
draft renders and computes from the admitted values. Admissions and selections persist even when
a later step fails; a rerun finds them in place and selects nothing twice.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import structlog
from psycopg_pool import ConnectionPool

from equity_os.analysis.calculations.run_traces import RunDraftError
from equity_os.contracts.measurement.canonical import Basis, Representation, ValueIdentity
from equity_os.contracts.measurement.evidence import KnowledgeTimeStatus, RunMode
from equity_os.contracts.measurement.measurement_key import MeasurementKey
from equity_os.contracts.measurement.role import FactRole
from equity_os.contracts.verification.config_versions import ConfigVersions
from equity_os.contracts.verification.vendor_first import AdmissionLabel
from equity_os.contracts.verification.versioning import VersionContentDriftError
from equity_os.interface.entry.config import FundamentalsConfig
from equity_os.normalisation.dictionary.role_translation import LEGACY_CONCEPTS
from equity_os.publication.checking.citations import witnesses
from equity_os.publication.checking.claim_check import CRORE, PER_SHARE
from equity_os.publication.drafting.earnings_update import REQUIRED_ROLES, AdmittedFact
from equity_os.publication.revision.import_mapping import measurement_key
from equity_os.storage.facts.pg_fact_store import PgFactStore
from equity_os.storage.records.repository import EvidenceRepository
from equity_os.verification.admission.admission import (
    AdmissionRecord,
    admit_run,
    key_identity,
    select_admitted,
)
from equity_os.verification.comparison.run_config import (
    ComparisonSemanticsError,
    load_run_config,
    require_pins,
)
from equity_os.verification.comparison.run_models import (
    RunInputDisposition,
    RunInputKind,
    RunManifest,
    RunStatus,
    row_id,
)
from equity_os.verification.comparison.run_store import RunReadError, RunStore

# The pins a pilot run's comparison run must name, by content (PILOT-GAP admission Decision 8);
# the vendor-first policy and eligibility are the run's own.
PILOT_VERSIONS = ConfigVersions(dictionary="v2", mapping_set="v9", alignment_rules="v2")
CONFIG_ROOT = Path("config")  # as ``compare run``'s default config root
_OWN_PINS = {"vendor_first_policy": None, "eligibility": None}
Chosen = dict[FactRole, tuple[MeasurementKey, AdmissionRecord]]


def run_versions(
    pool: ConnectionPool, run_id: int, entity_id: int, config: FundamentalsConfig
) -> tuple[RunManifest, ConfigVersions]:
    """Comparison run ``run_id``'s manifest and versions, once it is a complete ``AS_KNOWN`` run
    of this entity and quarter under ``PILOT_VERSIONS`` whose current files, vendor extractors,
    policy and eligibility match its own pins."""
    try:
        manifest = RunStore(pool).read_manifest(run_id)
    except (LookupError, RunReadError) as error:
        raise RunDraftError(f"comparison run {run_id}: {error}") from error
    period_end = config.quarter.period_end
    if (
        manifest.status is not RunStatus.COMPLETE
        or manifest.mode is not RunMode.AS_KNOWN
        or manifest.scope.entity_ids != (entity_id,)
        or period_end not in manifest.scope.period_ends
    ):
        raise RunDraftError(
            f"comparison run {run_id} is not a complete AS_KNOWN run of {period_end}"
        )
    versions = ConfigVersions.of(manifest.pinned)
    pilot = PILOT_VERSIONS.model_copy(update=_OWN_PINS)
    if drift := [n for n, v in versions.model_copy(update=_OWN_PINS) if getattr(pilot, n) != v]:
        raise RunDraftError(f"comparison run {run_id}: {', '.join(drift)} not the pilot's pins")
    try:
        current = load_run_config(CONFIG_ROOT, versions, vendors=manifest.scope.vendors)
        require_pins(current, manifest.pinned)
    except (VersionContentDriftError, ComparisonSemanticsError) as error:
        raise RunDraftError(f"comparison run {run_id}: {error}") from error
    return manifest, versions


def admit_roles(
    pool: ConnectionPool,
    store_id: str,
    run_id: int,
    config: FundamentalsConfig,
    entity_id: int,
    carried: frozenset[str],
) -> Chosen:
    """Admit comparison run ``run_id``, then each non-carried required role's record, keyed in
    its role's own unit from the issuer's concepts and the quarter; a refused role refuses."""
    outcome = admit_run(run_id, pool=pool, store_id=store_id, config_root=CONFIG_ROOT)
    others = Counter(refusal.value for _, refusal in outcome.refusals)
    structlog.get_logger("fundamentals.cli").info("admission_refusals", run_id=run_id, **others)
    refusals = dict(outcome.refusals)
    concepts = {item.role: item.concept_qname for item in config.concepts.roles}
    start, end = config.quarter.period_start, config.quarter.period_end
    chosen = {}
    for role in REQUIRED_ROLES:
        if f"fact.{role.value}" in carried:
            continue
        unit = PER_SHARE if role is FactRole.BASIC_EPS else CRORE
        key = measurement_key(LEGACY_CONCEPTS[concepts[role]], unit, entity_id, start, end)
        found = [record for record in outcome.records if record.key_digest == key.digest()]
        if len(found) != 1:
            refusal = refusals.get(row_id(key, ValueIdentity.REPORTED), "not in run")
            raise RunDraftError(
                f"{role.value} not admitted from comparison run {run_id}: {refusal}"
            )
        chosen[role] = (key, found[0])
    return chosen


def check_sources(
    pool: ConnectionPool,
    manifest: RunManifest,
    chosen: Chosen,
    config: FundamentalsConfig,
    xbrl: tuple[str, ...],
    pdfs: tuple[str, ...],
    versions: ConfigVersions,
) -> None:
    """A filed value comes from the run's one selected package of the quarter, published by the
    cutoff and holding the run's own XBRL and results PDF; a vendor value's two witnesses are
    held captures of both vendor-primary sources registered by the run's cutoff, an unchecked
    one under the run's eligibility pin. Only an all-unchecked run may select no package."""
    records = {role: record for role, (_, record) in chosen.items()}
    unchecked = AdmissionLabel.VENDORS_AGREE_NOT_CHECKED
    with pool.connection() as conn, conn.cursor() as cursor:
        for role, record in records.items():
            if record.witness_interpretation_id is None:
                continue
            times = witnesses(cursor, record.interpretation_id, record.witness_interpretation_id)
            if times is None or max(times) > manifest.cutoff:
                raise RunDraftError(f"{role.value}'s vendor witnesses are not held by the run")
            if record.label is unchecked and record.eligibility_version != versions.eligibility:
                raise RunDraftError(f"{role.value} is not under the run's eligibility pin")
    if all(record.label is unchecked for record in records.values()):
        return
    members = _members(pool, manifest, config, xbrl, pdfs)
    filed = {r for r, record in records.items() if record.witness_interpretation_id is None}
    occurrences = {
        item.occurrence_id: item
        for item in EvidenceRepository(pool).get_occurrences(
            [records[role].occurrence_id for role in filed]
        )
    }
    for role in filed:
        capture = occurrences[records[role].occurrence_id].capture
        if (capture.source_id, capture.blob_sha256) not in members:
            raise RunDraftError(
                f"{role.value} was admitted from {capture.blob_sha256}, not the package"
            )


def select_roles(
    pool: ConnectionPool, store_id: str, run_id: int, chosen: Chosen
) -> dict[FactRole, AdmittedFact]:
    """Select each chosen record's fact unless it is already its key's head, and the admitted
    facts as selected."""
    store = PgFactStore(pool, store_id)
    reason = f"admitted from comparison run {run_id}"
    admitted = {}
    for role, (key, record) in chosen.items():
        identity = key_identity(key)
        history = store.get_selection_history(identity)
        if not history or history[-1].row_id != record.handle:
            head = history[-1].selection_id if history else 0
            select_admitted(
                pool,
                store_id=store_id,
                admission_id=record.admission_id,
                reason=reason,
                expected_selection_id=head,
            )
        (revision,) = [r for r in store.get_revisions(identity) if r.row_id == record.handle]
        observation = revision.fact.observation
        admitted[role] = AdmittedFact(
            ref=record.ref,
            value=observation.normalized_value,
            decimals=observation.decimals,
            provenance=observation.provenance,
            label=record.label,
            interpretation_id=record.interpretation_id,
            witness_interpretation_id=record.witness_interpretation_id,
        )
    return admitted


def _members(
    pool: ConnectionPool,
    manifest: RunManifest,
    config: FundamentalsConfig,
    xbrl: tuple[str, ...],
    pdfs: tuple[str, ...],
) -> frozenset[tuple[str, str]]:
    """The run's one selected package of the quarter, published by the cutoff, as its XBRL and
    results PDF members, which must be the run's own."""
    period_end, cutoff = config.quarter.period_end, config.quarter.knowledge_cutoff
    selected = [
        item.ref_id
        for item in manifest.inputs
        if item.kind is RunInputKind.PACKAGE and item.disposition is RunInputDisposition.SELECTED
    ]
    packages = [
        package
        for package in EvidenceRepository(pool).get_packages(selected)
        if (package.entity_id, package.reporting_period_end, package.basis)
        == (manifest.scope.entity_ids[0], period_end, Basis.CONSOLIDATED)
    ]
    if len(packages) != 1 or packages[0].knowledge_time > cutoff:
        raise RunDraftError(f"the comparison run has no single package published by {cutoff}")
    expected = {
        Representation.XBRL: (config.xbrl.source_id, xbrl[0]),
        Representation.PDF: (config.results_pdf.source_id, pdfs[0]),
    }
    for representation, capture in expected.items():
        member = packages[0].members.get(representation)
        if (
            member is None
            or (member.capture.source_id, member.capture.blob_sha256) != capture
            or member.knowledge_time_status is not KnowledgeTimeStatus.KNOWN
            or member.knowledge_time > cutoff
        ):
            raise RunDraftError(
                f"the comparison run's {representation.value} member is not the run's own "
                f"{capture[1]} published by {cutoff}"
            )
    return frozenset(expected.values())
