"""Context for a results group with no filing package, from evidenced metadata (spec §6.3).

Currency comes from the requested vendors' current interpretations of the group's periods
(their evidenced units), framework, fiscal year and basis status from identity settings,
``disclosed_rows`` from the vendor rows present (never their values) and the period kind from
the longest vendor column of the group. Nothing is defaulted: a missing input raises
``RunResolutionError`` and the group refuses. A dimensioned row a requested vendor maps
refuses too, since its members are enumerated from a filing package (§6.1). A consolidated
request of a standalone-only entity reads nothing: every row is ``NOT_APPLICABLE`` first.
"""

from __future__ import annotations

from datetime import date

from equity_os.companies.identity.identity_seed import SettingKey
from equity_os.contracts.measurement.canonical import Basis, ReportingRegime
from equity_os.contracts.measurement.evidence import InterpretationStatus
from equity_os.contracts.measurement.measurement_key import PeriodInterval
from equity_os.normalisation.dictionary.applicability import ApplicabilityContext
from equity_os.verification.comparison.engine_attempts import RunResolutionError
from equity_os.verification.comparison.engine_context import (
    basis_status,
    reporting_currency,
    segment_bases,
    segment_members,
    setting_as_of,
)
from equity_os.verification.comparison.resolve_models import ResolvedInputs
from equity_os.verification.comparison.run_config import LoadedConfig
from equity_os.verification.comparison.run_family import RUN_FAMILIES
from equity_os.verification.comparison.run_models import RunRequest
from equity_os.verification.comparison.vendor_sides import VendorSides

VendorContext = tuple[str | None, ApplicabilityContext]
_FRAMEWORK = "entity {entity_id} has no {framework} reporting framework recorded by the cutoff"
_NO_COLUMN = "entity {entity_id} period {period_end}: no vendor column evidences the period"
_DIMENSIONED = (
    "entity {entity_id} period {period_end}: members of dimensioned rows {rows} cannot be "
    "enumerated without a filing package"
)


def vendor_group_context(
    vendors: VendorSides,
    inputs: ResolvedInputs,
    request: RunRequest,
    config: LoadedConfig,
    group: tuple[int, Basis, date],
    periods: tuple[PeriodInterval, ...],
    fiscal_month: int,
) -> VendorContext:
    """The reporting currency and applicability context of one package-less results group."""
    (entity_id, basis, end), cutoff = group, request.cutoff
    family = RUN_FAMILIES[request.scope.family]
    status = basis_status(inputs.basis_statuses, entity_id, cutoff)
    items = [
        item
        for item in vendors.group_interpretations(entity_id, basis, end)
        if item.status is InterpretationStatus.MAPPED
        and item.entity_id == entity_id
        and item.basis is basis
        and item.period in periods
    ]
    currency = reporting_currency(items, inputs.basis_statuses, entity_id, basis, end, cutoff)
    columns = [period for period in periods if any(item.period == period for item in items)]
    if currency is not None:
        framework = setting_as_of(
            inputs.settings, entity_id, SettingKey.REPORTING_FRAMEWORK, cutoff, end
        )
        if framework != family.framework.value:
            raise RunResolutionError(
                _FRAMEWORK.format(entity_id=entity_id, framework=family.framework.value)
            )
        if not columns:
            raise RunResolutionError(_NO_COLUMN.format(entity_id=entity_id, period_end=end))
        if dimensioned := _vendor_dimensioned(config, request):
            raise RunResolutionError(
                _DIMENSIONED.format(entity_id=entity_id, period_end=end, rows=dimensioned)
            )
    occurrences = {item.occurrence_id or 0: item for item in inputs.occurrences}
    return currency, ApplicabilityContext(
        regime=ReportingRegime.IN_LODR,
        document_type=family.document_type,
        statements_present=frozenset(),
        period_kind=(columns or periods)[-1].kind(fiscal_month),
        requested_basis=basis,
        entity_basis_status=status,
        evidenced_segment_bases=segment_bases(
            segment_members(inputs.segment_members, entity_id, cutoff), occurrences
        ),
        disclosed_rows=frozenset(item.canonical_id for item in items if item.canonical_id),
    )


def _vendor_dimensioned(config: LoadedConfig, request: RunRequest) -> list[str]:
    """Current dimensioned rows a requested vendor table maps."""
    vendors = set(request.scope.vendors)
    mapping = config.mapping_set
    mapped = {
        rule.canonical_id for rule in mapping.entries if (rule.source, rule.surface) in vendors
    }
    mapped |= {
        rule.canonical_id
        for rule in mapping.constructions
        if (rule.source, rule.surface) in vendors
    }
    return sorted(
        row.canonical_id
        for row in config.dictionary.rows
        if row.dimension_template is not None
        and row.deprecated_by is None
        and row.canonical_id in mapped
    )


class VendorGroups:
    """One run's package-less results groups, each context resolved once."""

    def __init__(
        self,
        vendors: VendorSides,
        inputs: ResolvedInputs,
        request: RunRequest,
        config: LoadedConfig,
    ) -> None:
        self._args = (vendors, inputs, request, config)
        self._found: dict[tuple[int, Basis, date], VendorContext] = {}

    def context(
        self, group: tuple[int, Basis, date], periods: tuple[PeriodInterval, ...], month: int
    ) -> VendorContext:
        """A package-less group's currency and context (refused when an input is missing)."""
        if group not in self._found:
            self._found[group] = vendor_group_context(*self._args, group, periods, month)
        return self._found[group]

    def known(self, group: tuple[int, Basis, date]) -> ApplicabilityContext | None:
        """The context of a group already resolved as package-less, else ``None``."""
        found = self._found.get(group)
        return None if found is None else found[1]
