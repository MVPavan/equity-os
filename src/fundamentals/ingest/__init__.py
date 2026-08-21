"""Fundamentals ingest layer — held-source loaders (XBRL, PDF, SEC)."""

from fundamentals.ingest.pdf_source import (
    LoadedPdf,
    PageWord,
    PdfBlock,
    PdfIntegrityError,
    PdfPage,
    compute_file_sha256,
    load_pdf,
)
from fundamentals.ingest.sec_source import (
    Q1_UPDATE_CUTOFF,
    SecAnnualResult,
    SecAnnualSource,
    SecFetchError,
    SecSourceConfig,
    is_annual,
    is_excluded_from_q1,
    knowledge_time_of,
)
from fundamentals.ingest.xbrl_source import (
    NseXbrlSource,
    XbrlFetchError,
    XbrlRetrieval,
)

__all__ = [
    "Q1_UPDATE_CUTOFF",
    "LoadedPdf",
    "NseXbrlSource",
    "PageWord",
    "PdfBlock",
    "PdfIntegrityError",
    "PdfPage",
    "SecAnnualResult",
    "SecAnnualSource",
    "SecFetchError",
    "SecSourceConfig",
    "XbrlFetchError",
    "XbrlRetrieval",
    "compute_file_sha256",
    "is_annual",
    "is_excluded_from_q1",
    "knowledge_time_of",
    "load_pdf",
]
