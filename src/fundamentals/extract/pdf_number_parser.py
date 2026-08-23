"""Deterministic PDF number extraction of a consolidated quarterly P&L.

Reads the consolidated results statement printed in a held Indian filer's
quarterly results PDF and emits typed :class:`Observation`s with exact
page/block/span provenance. Extraction is by **word geometry** — words are
grouped into horizontal row bands and, for each configured target row, the
current-quarter value is the numeric cell aligned under the current-quarter
column. Naive ``get_text('text')`` reading order is unsafe here: a nil (``-``)
cell breaks label/value line pairing (see docs/research/pdf-extraction-bakeoff.md
§3a).

This module is the **extraction layer**: it turns located rows and the located
current-quarter column into typed observations, reconstructs a split revenue total
by validated summation, and derives a missing revenue total from the statement's
own ``Income = Revenue + Other income`` identity. The "where is the statement /
header / unit / current-quarter column" machinery — banding, tolerant label
matching, date/scope/column geometry — and the parse spec itself live one layer
down in :mod:`fundamentals.extract.pdf_column_geometry`; the public spec, target,
error, and entry-point names are re-exported here so importers are unaffected by
the split. The design is **SEBI-format-general**, validated against five
structurally different Wave-1 issuers plus Infosys (see the geometry module for
the label/column/date/scope tolerance notes).

Fail-closed contract: if the consolidated statement page is absent a distinct
:class:`ConsolidatedStatementNotFoundError` is raised (the caller may treat that as a
skip); any other missing page, column, unit marker, or line item raises
:class:`NumberParseError`. A partial extraction never silently drops a fact, and a
value is never fabricated: a summed or derived total is emitted only when the
statement's own arithmetic supports it from clean inputs.

The primary (text-layer) lane makes no model calls and no network I/O: values are
reproducible byte-for-byte. An optional **OCR recovery lane** — for a statement
whose text layer is glyph-garbled or has a corrupt cell — lives in
:mod:`fundamentals.extract.pdf_ocr_recovery`: it renders the page, runs an injected
LOCAL OCR engine (nothing is transmitted), rebuilds word geometry from the
recognized tokens, and re-runs :func:`_extract_lines` (and thus the same summation
and derivation logic) with OCR-tolerant matching, failing closed against the
statement's own cross-foot identities. Both lanes share one fail-closed contract.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fundamentals.contracts.observation import Observation, PeriodType
from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.extract.pdf_column_geometry import (
    DEFAULT_COLUMN_X_TOLERANCE_PT,
    DEFAULT_MONTH_NAMES,
    DEFAULT_ROW_BAND_TOLERANCE_PT,
    ConditionalLabel,
    ConsolidatedStatementNotFoundError,
    LabelMatch,
    NumberParseError,
    PdfLineUnit,
    PdfParseSpec,
    PdfTargetLine,
    SubcomponentSummation,
    _anchor_row_top,
    _band_rows,
    _column_value,
    _current_column_center,
    _detect_unit_factor,
    _find_statement_page,
    _first_index,
    _label_has_any,
    _label_matches,
    _labelled_value_word,
    _parse_number,
    _parse_number_or_none,
    _row_label,
)
from fundamentals.ingest.pdf_source import LoadedPdf, PageWord, PdfPage

# Re-exported so importers of the public parse-spec / target / error surface are
# unaffected by the extraction/geometry split (grep-verified: config, goal_runner,
# pipeline, and the pdf tests import these names from this module).
__all__ = [
    "DEFAULT_COLUMN_X_TOLERANCE_PT",
    "DEFAULT_MONTH_NAMES",
    "DEFAULT_ROW_BAND_TOLERANCE_PT",
    "ConditionalLabel",
    "ConsolidatedStatementNotFoundError",
    "NumberParseError",
    "PdfLineUnit",
    "PdfParseSpec",
    "PdfTargetLine",
    "SubcomponentSummation",
    "extract_consolidated_pl",
]


def _build_observation(
    target: PdfTargetLine,
    *,
    raw_value: str,
    normalized_value: Decimal,
    provenance: Provenance,
    spec: PdfParseSpec,
) -> Observation:
    """Assemble a typed Observation from a target's typing and the run's identity.

    Shared by the single-cell (:func:`_observation_for`), summed
    (:func:`_summed_observation`), and derived (:func:`_derived_observation`)
    builders so the comparison-key fields stay in one place; each caller supplies
    only the value, its lexical form, and the anchor.
    """
    return Observation(
        concept_qname=target.concept_qname,
        raw_value=raw_value,
        normalized_value=normalized_value,
        normalized_unit=target.normalized_unit,
        entity_scheme=spec.entity_scheme,
        entity_id=spec.entity_id,
        scope=spec.scope,
        accounting_basis=spec.accounting_basis,
        period_type=PeriodType.DURATION,
        period_start=spec.period_start,
        period_end=spec.period_end,
        unit_ref=target.unit_ref,
        currency=spec.currency,
        scale=target.scale,
        decimals=target.decimals,
        provenance=provenance,
    )


def _observation_for(
    target: PdfTargetLine,
    value_word: PageWord,
    *,
    unit_factor: Decimal,
    page: PdfPage,
    pdf: LoadedPdf,
    spec: PdfParseSpec,
    retrieved_at: datetime,
) -> Observation:
    """Build a typed Observation for one matched line, with exact provenance.

    A monetary value is rescaled to crore by ``unit_factor`` so it reconciles with
    the crore-normalized XBRL side; a per-share value is left as printed.
    """
    provenance = Provenance(
        source_id=pdf.source_id,
        file_sha256=pdf.file_sha256,
        anchor_type=SourceAnchorType.PDF_SPAN,
        page=page.page_number,
        block=value_word.block,
        span=f"{value_word.x0:.1f},{value_word.y0:.1f},{value_word.x1:.1f},{value_word.y1:.1f}",
        retrieved_at=retrieved_at,
    )
    factor = unit_factor if target.line_unit is PdfLineUnit.MONETARY else Decimal(1)
    return _build_observation(
        target,
        raw_value=value_word.text,
        normalized_value=_parse_number(value_word.text) * factor,
        provenance=provenance,
        spec=spec,
    )


def extract_consolidated_pl(
    pdf: LoadedPdf,
    *,
    spec: PdfParseSpec,
    retrieved_at: datetime,
    require_all: bool = True,
) -> list[Observation]:
    """Extract the consolidated quarterly P&L line items as typed Observations.

    Always raises :class:`ConsolidatedStatementNotFoundError` when the consolidated
    statement is absent, and :class:`NumberParseError` when the current-quarter
    column or the printed-unit marker is missing — those are document-level
    failures from which no fact can be trusted.

    A missing *line item* is governed by ``require_all``. With the default
    ``True`` the whole extraction fails closed (the single-issuer pipeline needs
    every headline line). With ``False`` a line item that cannot be located with a
    clean current-quarter value is skipped (never fabricated) and the lines that
    are present are still emitted — so a filer that splits revenue into
    sub-components, or whose EPS cell is OCR-corrupted, still contributes its
    other material facts as a cross-check source.

    A target carrying :class:`SubcomponentSummation` that matched only a value-less
    header is not failed in the first pass: after the direct lines are read, its
    total is reconstructed by validated summation (a split revenue with no printed
    total) or, failing that, derived from the statement's own
    ``Income = Revenue + Other income`` identity, and only then does ``require_all``
    decide whether an irrecoverable line fails the extraction.
    """
    page = _find_statement_page(pdf, spec)
    rows = _band_rows(page.words, spec.row_band_tolerance_pt)
    anchor_top = _anchor_row_top(rows, spec)
    header_words = tuple(word for word in page.words if word.y0 < anchor_top)
    unit_factor = _detect_unit_factor(header_words)
    center = _current_column_center(header_words, spec)
    return _extract_lines(
        rows,
        center=center,
        unit_factor=unit_factor,
        page=page,
        pdf=pdf,
        spec=spec,
        retrieved_at=retrieved_at,
        require_all=require_all,
        match_mode=LabelMatch.SUBSEQUENCE,
    )


def _extract_lines(
    rows: list[list[PageWord]],
    *,
    center: float,
    unit_factor: Decimal,
    page: PdfPage,
    pdf: LoadedPdf,
    spec: PdfParseSpec,
    retrieved_at: datetime,
    require_all: bool,
    match_mode: LabelMatch,
) -> list[Observation]:
    """Read every target line from pre-banded rows, then reconstruct split totals.

    Shared by the deterministic text-layer path (``SUBSEQUENCE`` matching) and the
    OCR lane (``CONCATENATED`` matching), so both honour the same fail-closed
    contract, summation, and derivation logic over the geometry they each produced.
    """
    observations: list[Observation] = []
    extracted_values: dict[str, Decimal] = {}
    for target in spec.target_lines:
        value_word = _match_target_value(rows, target, center, spec, match_mode)
        if value_word is None:
            if target.subcomponent_summation is None and require_all:
                raise NumberParseError(
                    f"line item {target.labels!r} not found with a current-quarter value "
                    f"on page {page.page_number}"
                )
            continue
        observation = _observation_for(
            target,
            value_word,
            unit_factor=unit_factor,
            page=page,
            pdf=pdf,
            spec=spec,
            retrieved_at=retrieved_at,
        )
        observations.append(observation)
        extracted_values[target.concept_qname] = observation.normalized_value

    _append_recovered_lines(
        observations,
        extracted_values,
        rows=rows,
        spec=spec,
        center=center,
        unit_factor=unit_factor,
        page=page,
        pdf=pdf,
        retrieved_at=retrieved_at,
        require_all=require_all,
        match_mode=match_mode,
    )
    return observations


def _append_recovered_lines(
    observations: list[Observation],
    extracted_values: dict[str, Decimal],
    *,
    rows: list[list[PageWord]],
    spec: PdfParseSpec,
    center: float,
    unit_factor: Decimal,
    page: PdfPage,
    pdf: LoadedPdf,
    retrieved_at: datetime,
    require_all: bool,
    match_mode: LabelMatch,
) -> None:
    """Recover a split/garbled total by validated summation, then by identity derivation.

    Runs after the direct pass so the reconciliation total (already read as a
    normal line) is available. For each summable target still missing, the printed
    sub-components are summed first (a filer that splits revenue with no printed
    total); failing that, the total is derived from the statement's own
    ``reconciliation_total − other block line`` identity (a filer whose revenue
    label/cell is garbled but whose income and other-income read cleanly). A target
    recoverable by neither fails closed under ``require_all``.
    """
    total_target = next((t for t in spec.target_lines if t.is_reconciliation_total), None)
    for target in spec.target_lines:
        if target.subcomponent_summation is None or target.concept_qname in extracted_values:
            continue
        recovered = _summed_line(
            rows,
            target,
            total_target=total_target,
            extracted_values=extracted_values,
            center=center,
            unit_factor=unit_factor,
            spec=spec,
            page=page,
            pdf=pdf,
            retrieved_at=retrieved_at,
            match_mode=match_mode,
        ) or _derived_line(
            rows,
            target,
            total_target=total_target,
            extracted_values=extracted_values,
            center=center,
            unit_factor=unit_factor,
            spec=spec,
            page=page,
            pdf=pdf,
            retrieved_at=retrieved_at,
            match_mode=match_mode,
        )
        if recovered is not None:
            observations.append(recovered)
        elif require_all:
            raise NumberParseError(
                f"line item {target.labels!r} has no printed total and could not be "
                f"reconstructed from self-consistent sub-components or the statement's "
                f"income identity on page {page.page_number}"
            )


def _starts_with_marker(row_label: str, markers: tuple[str, ...]) -> bool:
    """Whether a printed label begins with a sub-component bullet/dash marker."""
    stripped = row_label.strip()
    return any(stripped.startswith(marker) for marker in markers)


def _summed_line(
    rows: list[list[PageWord]],
    target: PdfTargetLine,
    *,
    total_target: PdfTargetLine | None,
    extracted_values: dict[str, Decimal],
    center: float,
    unit_factor: Decimal,
    spec: PdfParseSpec,
    page: PdfPage,
    pdf: LoadedPdf,
    retrieved_at: datetime,
    match_mode: LabelMatch,
) -> Observation | None:
    """Reconstruct a split total by summing its sub-components, or fail closed.

    The sub-components are the marker-led valued rows between the target's
    value-less header and the reconciliation-total row; the reconstruction is
    accepted only when ``sum(sub-components) + sum(other block lines)`` equals the
    already-read reconciliation total within tolerance. Any unexpected valued line
    in the block, a missing other-line, or a residual beyond tolerance returns
    ``None`` (never a guessed total).
    """
    cfg = target.subcomponent_summation
    if cfg is None or total_target is None:
        return None
    total_value = extracted_values.get(total_target.concept_qname)
    if total_value is None:
        return None
    header_idx = _first_index(rows, lambda row: _label_matches(_row_label(row), target, match_mode))
    total_idx = _first_index(
        rows,
        lambda row: (
            _label_matches(_row_label(row), total_target, match_mode)
            and _column_value(row, center, spec.column_x_tolerance_pt) is not None
        ),
    )
    if header_idx is None or total_idx is None or total_idx <= header_idx:
        return None

    factor = unit_factor if target.line_unit is PdfLineUnit.MONETARY else Decimal(1)
    components: list[PageWord] = []
    other_total = Decimal(0)
    other_found = False
    for row in rows[header_idx + 1 : total_idx]:
        value_word = _column_value(row, center, spec.column_x_tolerance_pt)
        if value_word is None or _parse_number_or_none(value_word.text) is None:
            continue
        label = _row_label(row)
        if _starts_with_marker(label, cfg.markers):
            components.append(value_word)
        elif _label_has_any(label, cfg.other_labels, match_mode):
            other_total += _parse_number(value_word.text) * factor
            other_found = True
        else:
            return None
    if not components or not other_found:
        return None
    subtotal = Decimal(0)
    for value_word in components:
        subtotal += _parse_number(value_word.text) * factor
    if abs(subtotal + other_total - total_value) > cfg.tolerance:
        return None
    return _summed_observation(
        target, components, subtotal, page=page, pdf=pdf, spec=spec, retrieved_at=retrieved_at
    )


def _summed_observation(
    target: PdfTargetLine,
    components: list[PageWord],
    subtotal: Decimal,
    *,
    page: PdfPage,
    pdf: LoadedPdf,
    spec: PdfParseSpec,
    retrieved_at: datetime,
) -> Observation:
    """Build a typed Observation for a summed total, tracing each summed component.

    ``raw_value`` is the printed components joined by ``+`` (the computed trace);
    the provenance span lists every component cell's box so each summed input is
    independently anchored. ``subtotal`` is already unit-scaled.
    """
    first = min(components, key=lambda word: (word.y0, word.x0))
    raw_value = " + ".join(word.text for word in components)
    trace = "; ".join(
        f"{word.text}@{word.x0:.1f},{word.y0:.1f},{word.x1:.1f},{word.y1:.1f}"
        for word in components
    )
    provenance = Provenance(
        source_id=pdf.source_id,
        file_sha256=pdf.file_sha256,
        anchor_type=SourceAnchorType.PDF_SPAN,
        page=page.page_number,
        block=first.block,
        span=f"sum({trace})",
        retrieved_at=retrieved_at,
    )
    return _build_observation(
        target,
        raw_value=raw_value,
        normalized_value=subtotal,
        provenance=provenance,
        spec=spec,
    )


def _derived_line(
    rows: list[list[PageWord]],
    target: PdfTargetLine,
    *,
    total_target: PdfTargetLine | None,
    extracted_values: dict[str, Decimal],
    center: float,
    unit_factor: Decimal,
    spec: PdfParseSpec,
    page: PdfPage,
    pdf: LoadedPdf,
    retrieved_at: datetime,
    match_mode: LabelMatch,
) -> Observation | None:
    """Derive a missing revenue-style total from the statement's income identity.

    The algebraic dual of :func:`_summed_line`, for the case its reconciliation
    cannot even be attempted. When the target's own line is **entirely unreadable**
    — its label matches no row, as when a garbled glyph layer turns
    ``"Revenue from operations"`` into ``"Revenuc from operations"`` — but the
    reconciliation total (``Income``) was cleanly extracted AND the other block line
    (``Other income``, taken from the target's own :class:`SubcomponentSummation`)
    reads cleanly on the current-quarter column, the target total is recovered as
    ``reconciliation_total − other`` — the rearrangement of the statement's own
    ``Income = Revenue + Other income`` identity.

    Fails closed (``None``) unless every condition holds: the target line is absent
    (a *present* split whose components did not reconcile is a fail-closed signal,
    not a licence to derive from a total that row's own arithmetic just contradicted
    — the summation reconciliation stays authoritative there); the total is already
    in ``extracted_values``; and both the total and the other cells resolve to a
    clean current-quarter number. A single-source guess is never emitted, and the
    derived value is still a first-party PDF fact (its provenance references both
    contributing cells and is tagged ``derive(...)``).
    """
    cfg = target.subcomponent_summation
    if cfg is None or total_target is None:
        return None
    if total_target.concept_qname not in extracted_values:
        return None
    # Derive only when the target line is entirely unreadable. If its label matches
    # any row — a value-less split header whose components failed to reconcile, or a
    # header whose value cell is unreadable — the summation reconciliation is
    # authoritative, and its failure means fail closed rather than trust the total.
    if any(_label_matches(_row_label(row), target, match_mode) for row in rows):
        return None
    total_word = _labelled_value_word(rows, total_target.labels, center, spec, match_mode)
    other_word = _labelled_value_word(rows, cfg.other_labels, center, spec, match_mode)
    if total_word is None or other_word is None:
        return None
    factor = unit_factor if target.line_unit is PdfLineUnit.MONETARY else Decimal(1)
    derived_value = (
        _parse_number(total_word.text) * factor - _parse_number(other_word.text) * factor
    )
    return _derived_observation(
        target,
        total_word,
        other_word,
        derived_value,
        page=page,
        pdf=pdf,
        spec=spec,
        retrieved_at=retrieved_at,
    )


def _derived_observation(
    target: PdfTargetLine,
    total_word: PageWord,
    other_word: PageWord,
    derived_value: Decimal,
    *,
    page: PdfPage,
    pdf: LoadedPdf,
    spec: PdfParseSpec,
    retrieved_at: datetime,
) -> Observation:
    """Build a typed Observation for a value derived as ``total − other block line``.

    ``raw_value`` is the computed trace of the two printed inputs
    (``"2539.27 - 31.51"``); the provenance span references BOTH contributing cells'
    boxes and is tagged ``derive(...)`` so downstream can see the value was
    recovered from the statement's income identity rather than read from a single
    printed cell — while remaining a first-party PDF fact (``PDF_SPAN`` anchor).
    ``derived_value`` is already unit-scaled.
    """
    raw_value = f"{total_word.text} - {other_word.text}"
    trace = "; ".join(
        f"{word.text}@{word.x0:.1f},{word.y0:.1f},{word.x1:.1f},{word.y1:.1f}"
        for word in (total_word, other_word)
    )
    provenance = Provenance(
        source_id=pdf.source_id,
        file_sha256=pdf.file_sha256,
        anchor_type=SourceAnchorType.PDF_SPAN,
        page=page.page_number,
        block=total_word.block,
        span=f"derive({trace})",
        retrieved_at=retrieved_at,
    )
    return _build_observation(
        target,
        raw_value=raw_value,
        normalized_value=derived_value,
        provenance=provenance,
        spec=spec,
    )


def _match_target_value(
    rows: list[list[PageWord]],
    target: PdfTargetLine,
    center: float,
    spec: PdfParseSpec,
    match_mode: LabelMatch = LabelMatch.SUBSEQUENCE,
) -> PageWord | None:
    """Return the current-quarter value cell for a target, skipping value-less rows.

    A label may appear first as a section header carrying no value cell (e.g.
    ``"Revenue from operations"`` above its sub-components, or the ``"(a) Revenue
    from operations"`` sub-header above a ``"Total revenue from operations"``
    total). Such matches are skipped so only rows that both match and carry a
    current-quarter value are candidates; if none do, the caller fails closed.

    A :class:`ConditionalLabel` match takes precedence over the plain ``labels`` —
    it binds the associate-inclusive profit-for-the-period and, crucially, the
    pre-associate line (which lacks the ``also_contains`` token) can never match any
    label, so it is never emitted. Among plain-label matches the first (top-to-
    bottom) valued row wins.
    """
    conditional = _conditional_value(rows, target, center, spec, match_mode)
    if conditional is not None:
        return conditional
    return _labelled_value_word(rows, target.labels, center, spec, match_mode)


def _conditional_value(
    rows: list[list[PageWord]],
    target: PdfTargetLine,
    center: float,
    spec: PdfParseSpec,
    match_mode: LabelMatch,
) -> PageWord | None:
    """First valued row matching a conditional label (head AND co-token), else None."""
    for conditional in target.conditional_labels:
        for row in rows:
            label = _row_label(row)
            if not _label_has_any(label, conditional.heads, match_mode):
                continue
            if not _label_has_any(label, conditional.also_contains, match_mode):
                continue
            value_word = _column_value(row, center, spec.column_x_tolerance_pt)
            if value_word is not None and _parse_number_or_none(value_word.text) is not None:
                return value_word
    return None
