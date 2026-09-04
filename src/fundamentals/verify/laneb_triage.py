"""Lane B step 5(c): which disagreements are worth a reviewer, and which are not.

Two measurements decide every rule here, and nothing else does. The Part 2 sweep
read 344 live lines and found 68 of 69 non-agreeing lines at or under 20%
relative difference, with agreeing lines at a median 0.008%. The Part 3
sensitivity harness seeded parser defects into the same comparison and found
every scale, sign or truncation defect at 90% or more, while a dropped row and a
stale period both landed as ``MISSING_SCREENER``. A magnitude floor plus a
structural class is therefore the only separation those two measurements
support. Persistence across periods separates nothing — definitional
disagreements persist exactly as a parser defect would — so no rule reads period
counts.

**This is an annotation, not a decision.** :func:`triage_run` returns a copy of
the report with two fields set per row and every other field untouched, so the
queue and the evidence can never disagree about what was compared. The exit code
stays the comparison's own (decision A, log-only); only the command may turn a
warn into a non-zero exit, and only when the operator asks with ``--warn-exit``.

**Nothing here is a fact.** Upstox shares upstream lineage with Screener, so a
disagreement gives a triage direction and never a diagnosis, and no value on
this path may reach the fact store or the reconciler.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from fundamentals.ingest.screener_crosscheck import (
    LISTED_CLASSES as LISTED_CLASSES,
)
from fundamentals.ingest.screener_crosscheck import (
    WARN_CLASSES as WARN_CLASSES,
)
from fundamentals.ingest.screener_crosscheck import (
    CrosscheckOutcome,
    CrosscheckReport,
    CrosscheckRow,
    EvidenceTier,
    UnmappedCategoryError,
    mapping_for,
)
from fundamentals.ingest.screener_crosscheck import (
    TriageClass as TriageClass,
)
from fundamentals.ingest.upstox_crosscheck import (
    CompanyCrosscheck,
    CrosscheckRunReport,
    is_valid_isin,
)
from fundamentals.ingest.upstox_statements import parse_identity_note

WARNINGS_FILENAME = "warnings.tsv"
WARNINGS_HEADER = (
    "isin\tsymbol\tbasis\tperiod\tupstox_category\ttier\toutcome\tupstox_amount\t"
    "screener_amount\trelative_difference\ttriage"
)
# What a column holds when the row states nothing there. A missing side is not a
# difference of zero, and rendering it as one would invent a comparison.
UNSTATED = "-"
# Four decimals is one order finer than the bar the classes are decided on, so a
# reviewer can see how close to it a line sat without reading the raw amounts.
RATIO_DECIMALS = 4

FIELD_SEPARATOR = "\t"
LINE_SEPARATOR = "\n"

# The two sections breadth is observed over. A section is a set of mapped
# categories that a single column shift or rescale would move together; the
# cash-flow categories are tier 3 and are never triaged, so they form none.
PROFIT_AND_LOSS_CATEGORIES: tuple[str, ...] = ("revenue", "operating_profit", "net_profit")
BALANCE_SHEET_CATEGORIES: tuple[str, ...] = ("total_asset", "total_liability")
BREADTH_SECTIONS: tuple[tuple[str, ...], ...] = (
    PROFIT_AND_LOSS_CATEGORIES,
    BALANCE_SHEET_CATEGORIES,
)
# One category is not a breadth observation, so a section that published only
# one mapped line in a period can never fire.
MINIMUM_SECTION_WIDTH = 2

# Outcomes a per-cell class is decided from. ``AGREE`` and ``MISSING_UPSTOX``
# say nothing about this repo's extraction and fall through to ``NONE``.
DISAGREEING_OUTCOMES: frozenset[CrosscheckOutcome] = frozenset(
    {CrosscheckOutcome.MISMATCH, CrosscheckOutcome.ANOMALY}
)
# What every line of a section must be for breadth to be observable at all.
BREADTH_OUTCOMES: frozenset[CrosscheckOutcome] = DISAGREEING_OUTCOMES | {
    CrosscheckOutcome.MISSING_SCREENER
}
# Tier 3 is excluded from triage entirely: equivalence there was never
# demonstrated, so a difference is as consistent with the mapping being wrong as
# with the parse being wrong, and ``unmet_tier3_count`` already counts it.
TRIAGED_TIERS: frozenset[EvidenceTier] = frozenset(
    {EvidenceTier.EQUIVALENCE_DEMONSTRATED, EvidenceTier.RELATED_NOT_EQUIVALENT}
)
# Classes whose own verdict is "large" or "small" and nothing more, so a
# table-wide hypothesis may re-read them; and the classes that make one.
REDUCIBLE_CLASSES: frozenset[TriageClass] = frozenset({TriageClass.MAGNITUDE, TriageClass.NOISE})
BREADTH_TRIGGERS: frozenset[TriageClass] = frozenset(
    {TriageClass.MAGNITUDE, TriageClass.STRUCTURAL}
)

# Reporting order for the queue: the strongest class first, exactly as the enum
# declares them.
_CLASS_ORDER: dict[TriageClass, int] = {
    triage_class: order for order, triage_class in enumerate(TriageClass)
}

_UNREADABLE_CONFIG = "{path} is not readable as a triage config: {reason}"
_INVALID_CONFIG = "{path} is not a valid triage config: {reason}"
_BAD_ISIN = "isin {isin!r} does not carry a valid ISO 6166 check digit"
_DUPLICATE = "two acknowledgements name the same (isin, upstox_category): {key}"


class TriageConfigError(ValueError):
    """Raised for a triage config this repo cannot read or cannot justify.

    Every number here is a measurement and every acknowledgement silences a warn
    for a named company and field, which is the one mechanism in this design
    that can hide a real finding. An entry that cannot state its evidence is
    refused rather than applied.
    """


def relative_difference(upstox: Decimal | None, screener: Decimal | None) -> Decimal | None:
    """Both sides' gap as a share of the larger, or ``None`` when there is no scale.

    ``|U - S| / max(|U|, |S|)`` is the statistic both Lane B measurements were
    reported in, so it is the only one under which the sweep's "68 of 69 at or
    under 20%" and the harness's "90% or more" are comparable. Absolute values
    because expense and cash-flow lines are legitimately negative and a signed
    ratio would rank a sign flip below a rounding difference.
    """
    if upstox is None or screener is None:
        return None
    scale = max(abs(upstox), abs(screener))
    if scale == 0:
        return None
    return abs(upstox - screener) / scale


class Acknowledgement(BaseModel):
    """One (company, field) exclusion, with the evidence that justifies it.

    Listed, never suppressed: an acknowledged line still reaches the review
    queue, so the six known definitional lines stay visible while none of them
    pages anyone.
    """

    # A key nobody modelled is refused rather than ignored: a misspelt field is
    # an exclusion the owner believes is in force and is not.
    model_config = ConfigDict(frozen=True, extra="forbid")

    isin: str
    symbol: str = Field(min_length=1)
    upstox_category: str
    reason: str = Field(min_length=1)
    # The document the exclusion was measured in. An acknowledgement without one
    # is an assertion, and an assertion cannot be re-checked when the vendor
    # restates.
    measured_in: str = Field(min_length=1)

    @field_validator("isin")
    @classmethod
    def _isin_verifies(cls, value: str) -> str:
        """Refuse an ISIN that cannot be the company it claims to be."""
        if not is_valid_isin(value):
            raise ValueError(_BAD_ISIN.format(isin=value))
        return value

    @field_validator("upstox_category")
    @classmethod
    def _category_is_mapped(cls, value: str) -> str:
        """Refuse a category the name map does not declare.

        An unmapped category silences nothing while reading as if it did, which
        is worse than an absent entry: the reviewer believes a line is covered.
        """
        try:
            mapping_for(value)
        except UnmappedCategoryError as error:
            raise ValueError(str(error)) from error
        return value


class TriageConfig(BaseModel):
    """The bar, the owner and the exclusions one run triages against.

    Unknown keys are refused. A plural typo — ``acknowledgements:`` for
    ``acknowledged:`` — otherwise loads as a config with no exclusions at all,
    and the first thing that happens is the documented 32% definitional line
    warning at the review owner every run.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    # A ratio of 0 warns on every disagreeing line and one above 1 is
    # unreachable, so both are refused rather than accepted as a no-op.
    magnitude_warn_ratio: Decimal = Field(gt=0, le=1)
    # A warn with no owner is a log line.
    review_owner: str = Field(min_length=1)
    acknowledged: tuple[Acknowledgement, ...] = ()

    @model_validator(mode="after")
    def _acknowledgements_are_distinct(self) -> TriageConfig:
        """Refuse two entries for one cell: one of them is unread."""
        keys = [(entry.isin, entry.upstox_category) for entry in self.acknowledged]
        for key in keys:
            if keys.count(key) > 1:
                raise ValueError(_DUPLICATE.format(key=key))
        return self


def load_triage_config(path: Path) -> TriageConfig:
    """Read one triage config, refusing anything it cannot fully justify."""
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise TriageConfigError(_UNREADABLE_CONFIG.format(path=path, reason=error)) from error
    try:
        return TriageConfig.model_validate(payload)
    except ValidationError as error:
        raise TriageConfigError(
            _INVALID_CONFIG.format(path=path, reason=error.errors()[0]["msg"])
        ) from error


def triage_run(report: CrosscheckRunReport, config: TriageConfig) -> CrosscheckRunReport:
    """Classify every compared row of a run, changing nothing else about it.

    Pure and idempotent. Purity is what lets a changed threshold be evaluated
    against a stored report rather than a fresh sweep; idempotence is what lets
    that happen without the second pass reclassifying what the first one wrote.
    """
    companies = tuple(_triage_company(company, config) for company in report.companies)
    return report.model_copy(update={"companies": companies})


def render_warnings(report: CrosscheckRunReport) -> str:
    """Render the review queue as TSV: one line per listed row, warnings first.

    The whole product of a warn in a log-only lane is a file the review owner
    can work through, so both stated amounts and the measure the class was
    decided on travel with the class itself.

    Warning classes come first, and within one company and basis the periods run
    **oldest first** — the reverse of the order the comparison lists them in.
    That is the queue contract the command's acceptance test pins, and it is
    expressed as a reversed report index rather than a sort on the period label:
    labels are month-year strings, so sorting them would put "Jun 2026" before
    "Mar 2026" the moment a quarterly comparison is offered.
    """
    lines = sorted(_queue_lines(report), key=lambda entry: entry[0])
    return LINE_SEPARATOR.join([WARNINGS_HEADER, *(line for _, line in lines)])


def _queue_lines(
    report: CrosscheckRunReport,
) -> Iterable[tuple[tuple[int, str, str, int, str], str]]:
    """Every listed row as a sort key and its rendered line.

    The key sorts by class first, so a reviewer reads the warning classes before
    the two that are merely listed. Periods are ordered by their position in the
    company's own reports rather than by their label — a label sort would put
    "Jun 2026" before "Mar 2026" — and reversed, so one company's lines run
    oldest first.
    """
    for company in report.companies:
        for index, crosscheck in enumerate(company.reports):
            for row in crosscheck.rows:
                if row.triage not in LISTED_CLASSES:
                    continue
                key = (
                    _CLASS_ORDER[row.triage],
                    company.isin,
                    company.basis,
                    -index,
                    row.upstox_category,
                )
                yield key, _queue_line(company, crosscheck, row)


def _queue_line(
    company: CompanyCrosscheck, crosscheck: CrosscheckReport, row: CrosscheckRow
) -> str:
    """One queue line, stating each amount exactly as its source stated it."""
    return FIELD_SEPARATOR.join(
        (
            company.isin,
            company.symbol,
            company.basis,
            crosscheck.period,
            row.upstox_category,
            row.tier.value,
            row.outcome.value,
            _amount(row.upstox_amount),
            _amount(row.screener_amount),
            _ratio(row.relative_difference),
            row.triage.value,
        )
    )


def _amount(value: Decimal | None) -> str:
    """One stated amount, or the unstated marker."""
    return UNSTATED if value is None else str(value)


def _ratio(value: Decimal | None) -> str:
    """One relative difference at a fixed width, or the unstated marker."""
    return UNSTATED if value is None else f"{value:.{RATIO_DECIMALS}f}"


def _triage_company(company: CompanyCrosscheck, config: TriageConfig) -> CompanyCrosscheck:
    """Classify one company's reports against the notes and exclusions it carries."""
    noted = _identity_notes(company.upstox_anomalies)
    acknowledged = frozenset(
        entry.upstox_category for entry in config.acknowledged if entry.isin == company.isin
    )
    reports = tuple(
        _triage_report(
            crosscheck,
            noted=noted,
            acknowledged=acknowledged,
            ratio=config.magnitude_warn_ratio,
        )
        for crosscheck in company.reports
    )
    return company.model_copy(update={"reports": reports})


def _identity_notes(anomalies: tuple[str, ...]) -> dict[tuple[str, str], Decimal]:
    """Each contradicted cell mapped to the ``full_statement`` figure it stated.

    Read through the statement reader's own parser, so the note's format has one
    owner. A note about the envelope or the response's shape names no cell and
    contributes nothing.
    """
    parsed = (parse_identity_note(note) for note in anomalies)
    return {(note.category, note.period): note.full for note in parsed if note is not None}


def _triage_report(
    crosscheck: CrosscheckReport,
    *,
    noted: Mapping[tuple[str, str], Decimal],
    acknowledged: frozenset[str],
    ratio: Decimal,
) -> CrosscheckReport:
    """Classify one period: every row on its own, then the breadth pass over it."""
    rows = tuple(
        _triage_row(
            row, period=crosscheck.period, noted=noted, acknowledged=acknowledged, ratio=ratio
        )
        for row in crosscheck.rows
    )
    return crosscheck.model_copy(update={"rows": _apply_breadth(rows)})


def _triage_row(
    row: CrosscheckRow,
    *,
    period: str,
    noted: Mapping[tuple[str, str], Decimal],
    acknowledged: frozenset[str],
    ratio: Decimal,
) -> CrosscheckRow:
    """Annotate one row with its relative difference and the class it earns.

    The difference is measured even where the class is fixed at ``NONE``: a
    tier-3 line can be the largest disagreement in a run, and the reader of
    ``unmet_tier3_count`` needs the number even though nothing may be concluded
    from it.
    """
    difference = relative_difference(row.upstox_amount, row.screener_amount)
    triage = _class_for(
        row,
        period=period,
        difference=difference,
        noted=noted,
        acknowledged=acknowledged,
        ratio=ratio,
    )
    return row.model_copy(update={"relative_difference": difference, "triage": triage})


def _class_for(
    row: CrosscheckRow,
    *,
    period: str,
    difference: Decimal | None,
    noted: Mapping[tuple[str, str], Decimal],
    acknowledged: frozenset[str],
    ratio: Decimal,
) -> TriageClass:
    """Name one row's class, first match winning.

    The order encodes what each class is worth. Structural first, because it is
    the only class the sensitivity harness caught on every seeded cell and the
    live sweep never produced — and because an acknowledgement is about two
    numbers meaning different things, which says nothing about a Screener row
    that stopped existing. Then the two classes that place the fault somewhere
    other than this repo's parse, each as narrow as its evidence: the Upstox
    note covers one category in one period *and only when Screener agrees with
    the figure the response's own ``full_statement`` gave*, the acknowledgement
    one field of one company. Only then the magnitude bar, inclusive at the
    ratio, because that is where the two measurements stop overlapping.
    """
    if row.tier not in TRIAGED_TIERS:
        return TriageClass.NONE
    if row.outcome is CrosscheckOutcome.MISSING_SCREENER:
        return TriageClass.STRUCTURAL
    if row.outcome not in DISAGREEING_OUTCOMES:
        return TriageClass.NONE
    if _is_upstox_side(row, noted.get((row.upstox_category, period))):
        return TriageClass.UPSTOX_SIDE
    if row.upstox_category in acknowledged:
        return TriageClass.ACKNOWLEDGED
    if difference is not None and difference >= ratio:
        return TriageClass.MAGNITUDE
    return TriageClass.NOISE


def _is_upstox_side(row: CrosscheckRow, stated_in_full: Decimal | None) -> bool:
    """Whether the vendor's own contradiction accounts for this disagreement.

    Coincidence is not enough. The first real replay found a company whose
    response contradicted itself on revenue while Screener sat about 50 crore
    from *both* Upstox figures: the summary block being unreliable there says
    nothing about a third value that matches neither. What exonerates this
    repo's parse is Screener agreeing with the ``full_statement`` figure inside
    the interval the comparison derived for the row — the vendor then disagrees
    with itself and this repo agrees with the half of it that is checkable. A
    row with no derived tolerance was never scored, so it earns no alibi either.
    """
    return (
        stated_in_full is not None
        and row.screener_amount is not None
        and row.tolerance is not None
        and abs(row.screener_amount - stated_in_full) <= row.tolerance
    )


def _apply_breadth(rows: tuple[CrosscheckRow, ...]) -> tuple[CrosscheckRow, ...]:
    """Re-read a section every mapped line of which disagrees, if one line is large.

    Breadth alone is a false alarm — the balance sheet has two mapped categories
    and both disagreed in more than a third of the sweep's periods from ordinary
    rounding — and magnitude alone misses a shift that moved every line a little.
    Together they are the signature of one table-wide rescale or column shift,
    and the sweep produced that pattern in no period at all. Rows whose own class
    already explains them keep it: overwriting a structural, Upstox-side or
    acknowledged row would delete the reason the reviewer needs.
    """
    by_category = {row.upstox_category: row for row in rows}
    relabelled: set[str] = set()
    for section in BREADTH_SECTIONS:
        present = [by_category[category] for category in section if category in by_category]
        if len(present) < MINIMUM_SECTION_WIDTH:
            continue
        if not all(row.outcome in BREADTH_OUTCOMES for row in present):
            continue
        if not any(row.triage in BREADTH_TRIGGERS for row in present):
            continue
        relabelled |= {row.upstox_category for row in present if row.triage in REDUCIBLE_CLASSES}
    if not relabelled:
        return rows
    return tuple(
        row.model_copy(update={"triage": TriageClass.WHOLE_TABLE})
        if row.upstox_category in relabelled
        else row
        for row in rows
    )
