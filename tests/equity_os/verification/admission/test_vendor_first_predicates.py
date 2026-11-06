"""T1, the filing state and the vendor-first pins (VENDOR-1 spec §6.4, acceptance 7; plan Task 6).

Unit cases build only what the predicates read: a row's source values, each vendor side's
interpretation and its mapping entry's tier. The ``pg`` case round-trips both new pins through
``run_versions`` and proves an old manifest serialises exactly as before.
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from evidence_support import CONFIG

from equity_os.contracts.measurement.canonical import Basis, Representation
from equity_os.contracts.measurement.evidence import (
    Interpretation,
    InterpretationOrigin,
    PinnedVersions,
    RunMode,
)
from equity_os.contracts.measurement.evidence_tier import EvidenceTier
from equity_os.contracts.sourcing.source_catalog import SCREENER_PAGE, TIJORI_PAGE
from equity_os.contracts.verification.comparison import SourceRole, SourceState
from equity_os.contracts.verification.vendor_first import FilingState, VendorOutcome
from equity_os.contracts.verification.versioning import VersionContentDriftError
from equity_os.normalisation.mapping.mapping import MappingSet
from equity_os.normalisation.mapping.mapping_models import MappingEntry
from equity_os.storage.records.repository import EvidenceRepository
from equity_os.verification.admission.vendor_first import (
    VendorFirstPolicy,
    filing_state,
    load_vendor_first_policy,
    vendor_outcome,
)
from equity_os.verification.comparison.run_config import (
    ConfigVersions,
    load_run_config,
    pin_config,
    require_pins,
)
from equity_os.verification.comparison.run_models import (
    DatabaseIdentity,
    ResultRow,
    RunManifest,
    RunScope,
    RunStatus,
    SourceValue,
)
from equity_os.verification.comparison.run_store import RunStore

POLICY = load_vendor_first_policy(CONFIG / "verification/vendor_first/policy/v1.yaml")
_ENTRY_TIER = {"s": EvidenceTier.EQUIVALENCE_UNPROVEN, "t": EvidenceTier.EQUIVALENCE_UNPROVEN}
# Omitted from an old manifest without vendors: no vendor pins, and neither Task 6 pin.
_NEW_PINS = ("vendor_extractors", "vendor_first_policy", "eligibility")
_ELIGIBILITY_FIXTURE = "# eligibility fixture (Task 7 defines the artifact)\nclasses: []\n"


def _vendor(page: tuple[str, str], value: str, half: str = "0", *, interpretation: int) -> Any:
    """A vendor ``VALUE`` side ``value ± half``."""
    centre, width = Decimal(value), Decimal(half)
    return SourceValue(
        source_role=SourceRole.INDEPENDENT_VENDOR,
        representation=Representation.HTML,
        source_id=page[0],
        surface=page[1],
        state=SourceState.VALUE,
        reason=None,
        value=centre,
        lower=centre - width,
        upper=centre + width,
        interpretation_id=interpretation,
        calculation_trace_id=None,
        attempt_id=None,
        calculation_state=None,
    )


def _filed(
    value: str | None, half: str = "0", *, state: SourceState = SourceState.VALUE
) -> SourceValue:
    """A first-party XBRL side."""
    centre = None if value is None else Decimal(value)
    width = Decimal(half)
    return SourceValue(
        source_role=SourceRole.FIRST_PARTY,
        representation=Representation.XBRL,
        state=state,
        reason=None,
        value=centre,
        lower=None if centre is None else centre - width,
        upper=None if centre is None else centre + width,
        interpretation_id=None,
        calculation_trace_id=None,
        attempt_id=None,
        calculation_state=None,
    )


def _row(*values: SourceValue) -> ResultRow:
    """A row holding only the source values the predicates read."""
    return ResultRow.model_construct(source_values=values)


def _outcome(
    screener: tuple[str, str], tijori: tuple[str, str], tiers: dict[str, EvidenceTier] | None = None
) -> tuple[VendorOutcome, SourceValue | None]:
    """T1 for a Screener and a Tijori side, both DIRECT under entries of ``tiers``."""
    tier = {**_ENTRY_TIER, **(tiers or {})}
    mapping = MappingSet.model_construct(
        entries=tuple(
            MappingEntry.model_construct(entry_id=entry_id, tier=tier[entry_id])
            for entry_id in tier
        )
    )
    interpretations = {
        1: Interpretation.model_construct(origin=InterpretationOrigin.DIRECT, mapping_entry_id="s"),
        2: Interpretation.model_construct(origin=InterpretationOrigin.DIRECT, mapping_entry_id="t"),
    }
    row = _row(
        _vendor(SCREENER_PAGE, *screener, interpretation=1),
        _vendor(TIJORI_PAGE, *tijori, interpretation=2),
    )
    return vendor_outcome(row, interpretations, mapping, POLICY)


def test_policy_file_holds_the_spec_thresholds() -> None:
    """§6.4: a 0.5% half-width limit and four clean key-periods, quoted so no float sets them."""
    assert POLICY == VendorFirstPolicy(
        version="v1",
        content_sha256=POLICY.content_sha256,
        precision_limit=Decimal("0.005"),
        min_clean_key_periods=4,
    )


@pytest.mark.parametrize(
    ("screener", "tijori", "expected"),
    [
        # Disjoint precise intervals: the vendors disagree, nothing is chosen.
        (("100.00", "0.005"), ("100.10", "0.005"), VendorOutcome.VENDORS_DISAGREE),
        # Intersecting but coarse: 100 ± 1 has half-width 1 > 0.005 × 100.5.
        (("100.5", "0.05"), ("100", "1"), VendorOutcome.VENDORS_IMPRECISE),
        # Half-width exactly at the limit (0.5 = 0.005 × 100) still agrees.
        (("100", "0.5"), ("100", "0"), VendorOutcome.VENDORS_AGREE),
        # m = 0: both exact agree; any width is imprecise.
        (("0", "0"), ("0", "0"), VendorOutcome.VENDORS_AGREE),
        (("0", "0"), ("0", "0.005"), VendorOutcome.VENDORS_IMPRECISE),
    ],
)
def test_vendor_outcome(
    screener: tuple[str, str], tijori: tuple[str, str], expected: VendorOutcome
) -> None:
    """T1 rules 2-4, first match wins."""
    assert _outcome(screener, tijori)[0] is expected


def test_agreeing_vendors_choose_the_narrower_side_screener_on_a_tie() -> None:
    """The admitted vendor value is the narrower interval; equal widths take Screener."""
    outcome, chosen = _outcome(("100.0", "0.05"), ("100.00", "0.005"))
    assert outcome is VendorOutcome.VENDORS_AGREE
    assert chosen is not None and chosen.source_id == TIJORI_PAGE[0]
    _, tie = _outcome(("100", "0.1"), ("100", "0.1"))
    assert tie is not None and tie.source_id == SCREENER_PAGE[0]


def test_related_entry_or_missing_vendor_is_unmapped() -> None:
    """Rule 1 reads the entry tier through the mapping set, and needs both vendors' values."""
    related = _outcome(("100", "0"), ("100", "0"), {"t": EvidenceTier.RELATED_NOT_EQUIVALENT})
    assert related == (VendorOutcome.VENDOR_UNMAPPED, None)
    lone = _row(_vendor(SCREENER_PAGE, "100", interpretation=1))
    assert vendor_outcome(lone, {}, MappingSet.model_construct(entries=()), POLICY) == (
        VendorOutcome.VENDOR_UNMAPPED,
        None,
    )


def test_filing_state() -> None:
    """F disjoint from one vendor only differs; any unavailable first-party side failed."""
    screener = _vendor(SCREENER_PAGE, "100", "0.5", interpretation=1)
    tijori = _vendor(TIJORI_PAGE, "100.4", "0.05", interpretation=2)
    # F = 99.6 ± 0.05 meets Screener's [99.5, 100.5] but not Tijori's [100.35, 100.45].
    assert filing_state(_row(screener, tijori, _filed("99.6", "0.05")), True) is (
        FilingState.FILING_DIFFERS
    )
    assert filing_state(_row(screener, tijori, _filed("100.4")), True) is FilingState.FILING_AGREES
    unavailable = _filed(None, state=SourceState.UNAVAILABLE)
    assert filing_state(_row(screener, tijori, unavailable), False) is FilingState.FILING_FAILED
    absent = _filed(None, state=SourceState.NO_VALUE)
    assert filing_state(_row(screener, tijori, absent), False) is FilingState.FILING_ABSENT
    assert filing_state(_row(screener, tijori, _filed("100.4")), False) is (
        FilingState.FILING_FAILED
    )


@pytest.mark.pg
def test_vendor_first_pins_round_trip(pg_db: Any, tmp_path: Path) -> None:
    """Both pins publish into ``run_versions``, read back, name their versions, and refuse a
    policy edited under the same version; an old manifest omits both, byte for byte."""
    root = tmp_path / "config"
    shutil.copytree(CONFIG, root)
    eligibility = root / "verification/vendor_first/eligibility/v1.yaml"
    eligibility.parent.mkdir(parents=True)
    eligibility.write_text(_ELIGIBILITY_FIXTURE, encoding="utf-8")
    versions = ConfigVersions(dictionary="v2", mapping_set="v9", eligibility="v1")
    config = load_run_config(root, versions)
    assert config.vendor_first_policy == POLICY
    old = config.pinned.model_copy(update={"vendor_first_policy": None, "eligibility": None})
    with pg_db.runtime_pool() as pool:
        definition_set_id = pin_config(config, repository=EvidenceRepository(pool), pool=pool)
        store = RunStore(pool)

        def publish(pinned: PinnedVersions, day: int) -> RunManifest:
            manifest = RunManifest(
                scope=RunScope(
                    entity_ids=(1,),
                    period_ends=(date(2025, 9, day),),
                    bases=(Basis.CONSOLIDATED,),
                    sources=("NSE_XBRL_INSTANCE",),
                ),
                cutoff=datetime(2026, 1, 1, tzinfo=UTC),
                mode=RunMode.AS_KNOWN,
                pinned=pinned,
                code_version="pins-fixture",
                database_identity=DatabaseIdentity(host="fixture", port=1, name="fixture"),
                inputs=(),
                status=RunStatus.COMPLETE,
            )
            run_id, _ = store.publish(manifest, (), definition_set_id=definition_set_id)
            return store.read_manifest(run_id)

        stored = publish(config.pinned, 1)
        legacy = publish(old, 2)
    assert stored.pinned == config.pinned
    assert ConfigVersions.of(stored.pinned) == versions
    require_pins(load_run_config(root, ConfigVersions.of(stored.pinned)), stored.pinned)
    policy = root / "verification/vendor_first/policy/v1.yaml"
    policy.write_text(policy.read_text(encoding="utf-8") + "# edited\n", encoding="utf-8")
    with pytest.raises(VersionContentDriftError, match="vendor_first_policy"):
        require_pins(load_run_config(root, ConfigVersions.of(stored.pinned)), stored.pinned)

    # The pre-Task-6 document: every earlier pin in field order, and nothing else.
    earlier = [name for name in PinnedVersions.model_fields if name not in _NEW_PINS]
    expected = {name: getattr(old, name).model_dump(mode="json") for name in earlier}
    assert json.dumps(legacy.pinned.model_dump(mode="json")) == json.dumps(expected)
    assert (ConfigVersions.of(legacy.pinned).vendor_first_policy, legacy.pinned.eligibility) == (
        None,
        None,
    )
