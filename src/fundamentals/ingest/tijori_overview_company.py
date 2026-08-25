"""Builder for the overview page's company-details header and forensic flags.

Split out of :mod:`fundamentals.ingest.tijori_overview_sections` because the
``quick_look`` checklist is the one overview island whose shape had to be learned
from the live page rather than the structure capture, and it carries its own
retention rules.

LIVE FACT (TITAN, 2026-08-25): ``quick_look`` is an object, not a list —
``{"count": {...tallies...}, "data": [{"name": ..., "factories": [flag, ...]}],
"table_data": ...}``. Flags therefore live one level deeper than the capture
suggested, under a named category.

Because this subtree's shape was already wrong once, it is modeled
retention-first: anything unexpected is recorded as a note plus verbatim JSON and
never raises. The header identity around it keeps the ordinary fail-closed rules.
"""

from __future__ import annotations

from typing import Any

import structlog

from fundamentals.ingest.tijori_overview_common import (
    DATA_FIELD,
    NAME_FIELD,
    PATH_SEPARATOR,
    SLUG_FIELD,
    SYMBOL_FIELD,
    SectionContext,
    anchor,
    as_object,
    invalid_values_json,
    number,
    optional_bool,
    optional_int,
    optional_string,
    unmodeled,
)
from fundamentals.ingest.tijori_overview_models import (
    TijoriCompanyDetailsSection,
    TijoriOverviewSchemaError,
    TijoriQuickLook,
    TijoriQuickLookCategory,
    TijoriQuickLookCounts,
    TijoriQuickLookFlag,
)
from fundamentals.ingest.tijori_tables import raw_json

_LOGGER = structlog.get_logger(__name__)

_COMPANY_FIELD = "company"
_COMPANY_ID_FIELD = "company_id"
_SHORTNAME_FIELD = "shortname"
_IND_CODE_FIELD = "ind_code"
_IS_BANKING_FIELD = "is_banking"
_MCAP_FIELD = "mcap"
_MCAP_RAW_FIELD = "mcap_raw"
_PE_FIELD = "pe"
_HAS_PEG_FIELD = "has_peg"
_PEG_FIELD = "peg"
_QUICK_LOOK_FIELD = "quick_look"
_COMPANY_DETAILS_FIELDS = frozenset(
    {
        _COMPANY_FIELD,
        _COMPANY_ID_FIELD,
        SYMBOL_FIELD,
        _SHORTNAME_FIELD,
        SLUG_FIELD,
        _IND_CODE_FIELD,
        _IS_BANKING_FIELD,
        _MCAP_FIELD,
        _MCAP_RAW_FIELD,
        _PE_FIELD,
        _HAS_PEG_FIELD,
        _PEG_FIELD,
        _QUICK_LOOK_FIELD,
    }
)

_SENTENCE_FIELD = "sentence"
_EXPLANATION_FIELD = "explanation"
_FLAG_FIELD = "flag"
_COUNT_FIELD = "count"
_TABLE_DATA_FIELD = "table_data"
_FACTORIES_FIELD = "factories"
_QUICK_LOOK_FIELDS = frozenset({_COUNT_FIELD, DATA_FIELD, _TABLE_DATA_FIELD})
_CATEGORY_FIELDS = frozenset({NAME_FIELD, _FACTORIES_FIELD})
_COUNT_FIELDS = ("green", "red", "neutral", "gray", "total")

_ABSENT_NOTE = "island published no quick_look"
_NULL_NOTE = "quick_look published as JSON null"
_UNMODELED_SHAPE_NOTE = "quick_look was not an object; preserved verbatim"
_UNMODELED_DATA_NOTE = "quick_look.data was not a list; preserved verbatim"
_UNMODELED_FACTORIES_NOTE = "one category published no factories list; preserved verbatim"


def _counts(raw_counts: Any, context: SectionContext) -> tuple[TijoriQuickLookCounts | None, bool]:
    """Read the flag tallies, recording any colour Tijori added since.

    Returns the tallies and whether the raw value had a shape this cannot read,
    so the caller can preserve that value verbatim instead of losing it.
    """
    if raw_counts is None:
        return None, False
    if not isinstance(raw_counts, dict):
        return None, True
    extra = {key: value for key, value in raw_counts.items() if key not in _COUNT_FIELDS}
    if extra:
        _LOGGER.warning(
            "tijori_overview_quick_look_count_drift",
            island=context.island_id,
            unmodeled_counts=sorted(str(key) for key in extra),
        )
    return (
        TijoriQuickLookCounts(
            green=optional_int(raw_counts, "green"),
            red=optional_int(raw_counts, "red"),
            neutral=optional_int(raw_counts, "neutral"),
            gray=optional_int(raw_counts, "gray"),
            total=optional_int(raw_counts, "total"),
            unmodeled_counts_json=raw_json(extra) if extra else None,
        ),
        False,
    )


def _flag(raw_flag: Any, context: SectionContext, *, element_path: str) -> TijoriQuickLookFlag:
    """Build one forensic flag, always keeping its verbatim source JSON."""
    entry = raw_flag if isinstance(raw_flag, dict) else {}
    return TijoriQuickLookFlag(
        name=optional_string(entry, NAME_FIELD),
        sentence=optional_string(entry, _SENTENCE_FIELD),
        explanation=optional_string(entry, _EXPLANATION_FIELD),
        flag=optional_string(entry, _FLAG_FIELD),
        raw_json=raw_json(raw_flag),
        provenance=anchor(context, element_path=element_path, field_label=_FLAG_FIELD),
    )


def _category(
    raw_category: dict[str, Any], context: SectionContext, *, index: int
) -> tuple[TijoriQuickLookCategory, bool]:
    """Build one flag category, addressing its flags by position then category.

    Nothing guarantees category names are unique, so the published position leads
    the address; the name follows it for readability.
    """
    name = optional_string(raw_category, NAME_FIELD) or ""
    element_root = (
        f"{_QUICK_LOOK_FIELD}{PATH_SEPARATOR}{index}{PATH_SEPARATOR}{name.strip() or DATA_FIELD}"
    )
    raw_flags = raw_category.get(_FACTORIES_FIELD)
    unreadable_flags = raw_flags is not None and not isinstance(raw_flags, list)
    flags = (
        tuple(
            _flag(
                raw_flag,
                context,
                element_path=f"{element_root}{PATH_SEPARATOR}{flag_index}",
            )
            for flag_index, raw_flag in enumerate(raw_flags)
        )
        if isinstance(raw_flags, list)
        else ()
    )
    return (
        TijoriQuickLookCategory(
            name=name,
            flags=flags,
            unmodeled_fields_json=unmodeled(
                raw_category, _CATEGORY_FIELDS, context=context, element=element_root
            ),
            # ``factories`` is a modeled key, so ``unmodeled`` excludes it: an
            # unreadable one is retained here or it would vanish with only a note.
            invalid_fields_json=invalid_values_json(
                raw_category,
                context=context,
                element=element_root,
                strings=(NAME_FIELD,),
                lists=(_FACTORIES_FIELD,),
            ),
        ),
        unreadable_flags,
    )


def _quick_look(raw_quick_look: Any, context: SectionContext, *, present: bool) -> TijoriQuickLook:
    """Build the forensic checklist, preserving whatever it does not model.

    ``present`` separates a key the island never published from one it published
    as JSON null, so the two never serialize alike.
    """
    if raw_quick_look is None:
        return TijoriQuickLook(note=_NULL_NOTE if present else _ABSENT_NOTE)
    if not isinstance(raw_quick_look, dict):
        _LOGGER.warning(
            "tijori_overview_quick_look_unmodeled",
            island=context.island_id,
            raw_type=type(raw_quick_look).__name__,
        )
        return TijoriQuickLook(
            note=_UNMODELED_SHAPE_NOTE, unmodeled_fields_json=raw_json(raw_quick_look)
        )
    preserved: dict[str, Any] = {
        key: value for key, value in raw_quick_look.items() if key not in _QUICK_LOOK_FIELDS
    }
    counts, unreadable_counts = _counts(raw_quick_look.get(_COUNT_FIELD), context)
    if unreadable_counts:
        preserved[_COUNT_FIELD] = raw_quick_look[_COUNT_FIELD]
    notes: list[str] = []
    raw_categories = raw_quick_look.get(DATA_FIELD)
    categories: list[TijoriQuickLookCategory] = []
    if isinstance(raw_categories, list):
        for index, raw_category in enumerate(raw_categories):
            if not isinstance(raw_category, dict):
                preserved[f"{DATA_FIELD}{PATH_SEPARATOR}{index}"] = raw_category
                continue
            category, unreadable_flags = _category(raw_category, context, index=index)
            categories.append(category)
            if unreadable_flags:
                notes.append(_UNMODELED_FACTORIES_NOTE)
    elif raw_categories is not None:
        preserved[DATA_FIELD] = raw_categories
        notes.append(_UNMODELED_DATA_NOTE)
    if preserved:
        _LOGGER.warning(
            "tijori_overview_quick_look_field_drift",
            island=context.island_id,
            unmodeled_fields=sorted(str(key) for key in preserved),
        )
    raw_table_data = raw_quick_look.get(_TABLE_DATA_FIELD)
    return TijoriQuickLook(
        counts=counts,
        categories=tuple(categories),
        # Content unknown as of 2026-08-25: retained verbatim, deliberately unmodeled.
        table_data_json=None if raw_table_data is None else raw_json(raw_table_data),
        unmodeled_fields_json=raw_json(preserved) if preserved else None,
        note="; ".join(dict.fromkeys(notes)) or None,
    )


def build_company_details(island: Any, context: SectionContext) -> TijoriCompanyDetailsSection:
    """Build the overview header: identity, headline valuation, forensic flags.

    Identity is not re-derived here — the page-level gate has already bound the
    response to the configured symbol and company id, and this section records
    the same verified values.
    """
    details = as_object(island, context.island_id)
    company_id = optional_int(details, _COMPANY_ID_FIELD)
    symbol = optional_string(details, SYMBOL_FIELD)
    if company_id is None or symbol is None:
        raise TijoriOverviewSchemaError(
            f"tijori overview {context.island_id} must publish company_id and symbol"
        )
    quick_look = _quick_look(
        details.get(_QUICK_LOOK_FIELD), context, present=_QUICK_LOOK_FIELD in details
    )
    if quick_look.note is not None:
        _LOGGER.info(
            "tijori_overview_quick_look_note", island=context.island_id, note=quick_look.note
        )
    return TijoriCompanyDetailsSection(
        section=context.section,
        island_id=context.island_id,
        metadata=context.metadata,
        company=optional_string(details, _COMPANY_FIELD),
        company_id=company_id,
        symbol=symbol,
        short_name=optional_string(details, _SHORTNAME_FIELD),
        slug=optional_string(details, SLUG_FIELD),
        industry_code=optional_int(details, _IND_CODE_FIELD),
        is_banking=optional_bool(details, _IS_BANKING_FIELD),
        market_cap_display=optional_string(details, _MCAP_FIELD),
        market_cap=number(
            details.get(_MCAP_RAW_FIELD),
            context,
            element_path=symbol,
            field_label=_MCAP_RAW_FIELD,
        ),
        price_earnings=number(
            details.get(_PE_FIELD), context, element_path=symbol, field_label=_PE_FIELD
        ),
        price_earnings_growth=number(
            details.get(_PEG_FIELD), context, element_path=symbol, field_label=_PEG_FIELD
        ),
        has_price_earnings_growth=optional_bool(details, _HAS_PEG_FIELD),
        quick_look=quick_look,
        unmodeled_fields_json=unmodeled(
            details, _COMPANY_DETAILS_FIELDS, context=context, element=symbol
        ),
        invalid_fields_json=invalid_values_json(
            details,
            context=context,
            element=symbol,
            strings=(_COMPANY_FIELD, _SHORTNAME_FIELD, SLUG_FIELD, _MCAP_FIELD),
            integers=(_IND_CODE_FIELD,),
            booleans=(_IS_BANKING_FIELD, _HAS_PEG_FIELD),
        ),
    )
