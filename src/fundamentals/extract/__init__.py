"""Fundamentals extract layer — deterministic parsers (XBRL, PDF, guidance)."""

from fundamentals.extract.guidance_extractor import (
    GuidanceExtractionError,
    anchor_matches,
    extract_guidance_claims,
    resolve_span,
)
from fundamentals.extract.pdf_number_parser import (
    NumberParseError,
    extract_consolidated_pl,
)
from fundamentals.extract.xbrl_parser import (
    FactSelectionError,
    XbrlParseError,
    parse_observations,
    select_observation,
)

__all__ = [
    "FactSelectionError",
    "GuidanceExtractionError",
    "NumberParseError",
    "XbrlParseError",
    "anchor_matches",
    "extract_consolidated_pl",
    "extract_guidance_claims",
    "parse_observations",
    "resolve_span",
    "select_observation",
]
