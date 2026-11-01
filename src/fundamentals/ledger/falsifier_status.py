"""Deterministic falsifier status in a run draft, bound to the thesis approved at its cutoff.

``approved_thesis`` selects the newest version of the stock's ``BOOTSTRAP_THESIS`` report that
was ``APPROVED`` as of the run's derivation cutoff (the claim check's cutoff too) and parses its
YAML twin. ``evaluate`` tests each falsifier's predicate on the run's own traced claim, at its
stored precision; ``derived`` renders the ``thesis_impact`` and ``observable_falsifiers``
sections and cites each evaluated threshold as a ``THESIS_CLAIM`` on the thesis's
``falsifier.<id>`` claim and sealed digest (plan RESEARCH-1 D2-D6). Labels and reasons hold no
digits, so nothing outside a placeholder reads as a number. Q0's effective tax rate was
registered as (PBT − PAT) / PBT, which the ledger never derives, so it stays ``UNRESOLVED``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, LiteralString

from psycopg import Cursor
from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.canonical import ValueKind
from fundamentals.contracts.guidance_claim import EpistemicClass
from fundamentals.contracts.ledger import (
    Citation,
    CitationKind,
    NumericClaim,
    SubjectKind,
    VersionStatus,
)
from fundamentals.ledger import store
from fundamentals.ledger.import_mapping import _slot, refs
from fundamentals.ledger.lifecycle import _LOCK, version_status
from fundamentals.ledger.run_traces import CALCS, MARGIN_KEY, Line, RunDraftError
from fundamentals.output.pnl_lines import ETR_LABEL
from fundamentals.verify.thesis_predicates import (
    ApprovedThesis,
    Disposition,
    PredicateOp,
    parse_thesis,
)

THESIS_IMPACT, FALSIFIER_STATUS = "thesis_impact", "observable_falsifiers"
DERIVED = frozenset({THESIS_IMPACT, FALSIFIER_STATUS})
# The risk probe's section: re-derived on every run like ``DERIVED``, rendered by ``risk_probe``.
RISK_PROBE = "risk_probe"
_PCT, _DAYS, _RATIO = ValueKind.PERCENTAGE, ValueKind.DAYS, ValueKind.RATIO
# A metric id: its label, the run claim measuring it (``None``: the ETR line's claim) and its
# value kind.
METRICS: Mapping[str, tuple[str, str | None, ValueKind]] = {
    "revenue_yoy_pct": ("Revenue YoY growth (%)", "cmp.revenue.yoy.pct", _PCT),
    "pbt_margin_pct": ("PBT margin, PBT before associates over revenue (%)", MARGIN_KEY, _PCT),
    "pat_yoy_pct": ("PAT YoY growth (%)", "cmp.profit_for_period.yoy.pct", _PCT),
    "eps_yoy_pct": ("Basic EPS YoY growth (%)", "cmp.basic_eps.yoy.pct", _PCT),
    "filed_effective_tax_rate_pct": ("Effective tax rate, filed tax over PBT (%)", None, _PCT),
    "probe_receivable_days": ("Receivable days", "probe.R1", _DAYS),
    "probe_inventory_materials_days": ("Inventory days on materials", "probe.R2", _DAYS),
    "probe_payable_materials_days": ("Payable days on materials", "probe.R3", _DAYS),
    "probe_cash_conversion_pct": ("Cash conversion, CFO over PAT (%)", "probe.R4", _PCT),
    "probe_capex_intensity_pct": ("Capex intensity, capex over revenue (%)", "probe.R5", _PCT),
    "probe_borrowings_to_equity_ratio": ("Borrowings to equity", "probe.R6", _RATIO),
}
KINDS: Mapping[str, ValueKind] = {metric: kind for metric, (*_, kind) in METRICS.items()}
SUPERSEDED_METRICS = frozenset({"effective_tax_rate_pct"})
SUPERSEDED_LABEL, UNREGISTERED_LABEL = "Effective tax rate (%)", "Unregistered metric"
SUPERSEDED = "definition superseded, pending approval"
UNREGISTERED = "metric not registered"
NO_VALUE = "measured value not available"
NO_THRESHOLD = "threshold claim not found"
STALE = "latest statement predates the period"
OPERATORS = {
    PredicateOp.LT: "below",
    PredicateOp.LTE: "at or below",
    PredicateOp.GT: "above",
    PredicateOp.GTE: "at or above",
}
FALSIFIER_PREFIX, THRESHOLD_PREFIX = "falsifier.", "thesis."
NO_THESIS = "{{e:computed}} UNRESOLVED: no approved thesis."
_VERSIONS: LiteralString = """SELECT v.id FROM eqos.report_versions v
JOIN eqos.reports r ON r.id = v.report_id
WHERE r.entity_id = %s AND r.kind = 'BOOTSTRAP_THESIS' ORDER BY v.id DESC"""
_CLAIM_IDS: LiteralString = "SELECT claim_key, id FROM eqos.numeric_claims WHERE version_id = %s"


class BoundThesis(BaseModel):
    """The approved thesis version, its sealed digest, its parsed twin and each falsifier's
    threshold claim with its row id."""

    model_config = ConfigDict(frozen=True)

    version_id: int
    sealed_digest: str
    thesis: ApprovedThesis
    thresholds: Mapping[str, tuple[int, NumericClaim]]


class FalsifierRow(BaseModel):
    """One falsifier's status: its label, operator, measuring claim and why it is unresolved."""

    model_config = ConfigDict(frozen=True)

    falsifier_id: str
    label: str
    op: PredicateOp
    claim_key: str | None
    disposition: Disposition
    reason: str | None


def approved_thesis(
    cursor: Cursor[Any], entity_id: int, symbol: str, as_of: datetime
) -> BoundThesis | None:
    """The newest bootstrap thesis version ``APPROVED`` as of ``as_of``, or ``None``; one with
    no single parseable YAML twin of ``symbol`` refuses."""
    for (version_id,) in cursor.execute(_VERSIONS, (entity_id,)).fetchall():
        cursor.execute(_LOCK, (SubjectKind.REPORT_VERSION.value, version_id))
        if version_status(cursor, version_id, as_of=as_of) is VersionStatus.APPROVED:
            break
    else:
        return None
    version = store.read_version(cursor, version_id)
    try:
        thesis = bindable_thesis(version.import_sources, symbol)
    except ValueError as error:
        raise RunDraftError(f"approved thesis version {version_id}: {error}") from error
    ids = dict(cursor.execute(_CLAIM_IDS, (version_id,)).fetchall())
    thresholds = {
        claim.claim_key.removeprefix(FALSIFIER_PREFIX): (int(ids[claim.claim_key]), claim)
        for claim in version.claims
        if claim.claim_key.startswith(FALSIFIER_PREFIX)
    }
    return BoundThesis(
        version_id=version_id,
        sealed_digest=store.sealed_digest(cursor, version_id),
        thesis=thesis,
        thresholds=thresholds,
    )


def bindable_thesis(sources: Sequence[tuple[str, bytes]], symbol: str) -> ApprovedThesis:
    """The single YAML twin among a thesis version's import ``sources``, parsed; one that is
    missing, ambiguous, unparseable or not of ``symbol`` raises ``ValueError``."""
    twins = [body for path, body in sources if path.endswith(".yaml")]
    if len(twins) != 1:
        raise ValueError(f"{len(twins)} YAML twins")
    thesis = parse_thesis(twins[0])
    if thesis.symbol != symbol:
        raise ValueError(f"thesis is of {thesis.symbol}")
    return thesis


def evaluate(
    bound: BoundThesis,
    claims: Mapping[str, NumericClaim],
    lines: Sequence[Line],
    stale: frozenset[str] = frozenset(),
) -> tuple[FalsifierRow, ...]:
    """Each falsifier's status on the run's claims: ``WEAKENED`` when its predicate holds on
    the stored value, else ``HELD``; ``NOT_ASSESSED`` when its measuring claim is in ``stale``;
    ``UNRESOLVED`` for a superseded or unregistered metric, a missing value or a missing
    threshold. A measure of another value kind than its threshold raises."""
    etr = next(
        (
            c
            for line in lines
            if line.section == CALCS and line.label == ETR_LABEL
            for c in line.claims
        ),
        None,
    )
    rows = []
    for falsifier in bound.thesis.falsifiers:
        metric, fid = falsifier.predicate.metric_id, falsifier.falsifier_id
        label, key, _ = METRICS.get(metric, (UNREGISTERED_LABEL, None, _PCT))
        measured = etr if key is None else claims.get(key)
        threshold = bound.thresholds.get(fid)
        reason = (
            STALE
            if key in stale
            else SUPERSEDED
            if metric in SUPERSEDED_METRICS
            else UNREGISTERED
            if metric not in METRICS
            else NO_VALUE
            if measured is None or measured.value is None
            else NO_THRESHOLD
            if threshold is None
            else None
        )
        disposition = Disposition.NOT_ASSESSED if reason == STALE else Disposition.UNRESOLVED
        claim_key = None
        if reason is None and measured is not None and measured.value is not None:
            if threshold is None or measured.value_kind is not threshold[1].value_kind:
                raise RunDraftError(f"{fid}: {measured.claim_key} is not a {metric} measure")
            weakened = falsifier.predicate.holds(measured.value)
            disposition = Disposition.WEAKENED if weakened else Disposition.HELD
            claim_key = measured.claim_key
        rows.append(
            FalsifierRow(
                falsifier_id=fid,
                label=SUPERSEDED_LABEL if reason == SUPERSEDED else label,
                op=falsifier.predicate.op,
                claim_key=claim_key,
                disposition=disposition,
                reason=reason,
            )
        )
    return tuple(rows)


def derived(
    bound: BoundThesis | None, rows: Sequence[FalsifierRow]
) -> tuple[tuple[tuple[str, str], ...], tuple[NumericClaim, ...]]:
    """The two derived sections as (key, body) and each evaluated row's threshold claim."""
    if bound is None:
        return tuple(
            (key, f"## {key}\n\n{NO_THESIS}\n\n") for key in (THESIS_IMPACT, FALSIFIER_STATUS)
        ), ()
    pinned = f"version:{bound.version_id}"
    by_status = [
        f"{status.value} {', '.join(r.falsifier_id for r in rows if r.disposition is status)}"
        for status in Disposition
        if any(r.disposition is status for r in rows)
    ]
    impact = (
        f"{{{{e:computed}}}} Deterministic falsifier status against approved thesis {pinned} "
        f"(sealed digest {bound.sealed_digest}): {'; '.join(by_status) or 'no falsifiers'}. "
        "The narrative impact is not drafted by this pipeline."
    )
    lines = [
        f"{{{{e:computed}}}} {{{{e:opinion}}}} Each falsifier of thesis {pinned}, tested in code: "
        "what is measured: observed traced value, trigger condition (operator and thesis "
        "threshold), status."
    ]
    thresholds = []
    for row in rows:
        head = f"- {row.falsifier_id} {row.label}: "
        if row.claim_key is None:
            lines.append(f"{head}{row.disposition.value} ({row.reason})")
            continue
        name = THRESHOLD_PREFIX + row.falsifier_id
        row_id, cited = bound.thresholds[row.falsifier_id]
        citation = Citation(
            kind=CitationKind.THESIS_CLAIM,
            cited_claim_id=row_id,
            cited_sealed_digest=bound.sealed_digest,
        )
        thresholds.append(
            cited.model_copy(
                update={
                    "claim_key": name,
                    "section_key": FALSIFIER_STATUS,
                    "citation": citation,
                    "epistemic_class": EpistemicClass.OPINION,
                }
            )
        )
        style = "plus,unit" if row.claim_key.startswith("cmp.") else ""
        triggered = "triggered" if row.disposition is Disposition.WEAKENED else "not triggered"
        lines.append(
            f"{head}observed {_slot(row.claim_key, style)}; triggers when {OPERATORS[row.op]} "
            f"{_slot(name, '')} {refs([row.claim_key, name])}: "
            f"{row.disposition.value} ({triggered})"
        )
    bodies = ((THESIS_IMPACT, f"{impact}\n"), (FALSIFIER_STATUS, "\n".join(lines) + "\n"))
    return tuple((key, f"## {key}\n\n{body}\n") for key, body in bodies), tuple(thresholds)
