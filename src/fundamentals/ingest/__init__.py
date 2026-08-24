"""Fundamentals ingest layer — first-party and derived source adapters.

Exports the held/live source loaders wired together by the goal runner: the two
first-party XBRL hosts (NSE, BSE), the deterministic issuer-PDF loader, the SEC
retrospective annual adapter, and the two DERIVED aggregators (Screener, Tijori)
that are cross-check only, never a source of record.
"""

from fundamentals.ingest.bse_source import (
    BseFetchError,
    BseHardBlockError,
    BseRetrieval,
    BseSource,
)
from fundamentals.ingest.pdf_source import (
    LoadedPdf,
    PageWord,
    PdfBlock,
    PdfIntegrityError,
    PdfPage,
    compute_file_sha256,
    load_pdf,
)
from fundamentals.ingest.screener_source import (
    ScreenerBlockError,
    ScreenerFetchError,
    ScreenerResult,
    ScreenerSource,
    ScreenerSourceConfig,
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
from fundamentals.ingest.tijori_source import (
    TijoriCredentials,
    TijoriCredentialsError,
    TijoriError,
    TijoriFetchError,
    TijoriParseError,
    TijoriSource,
    TijoriSourceConfig,
)
from fundamentals.ingest.tijori_tables import (
    TijoriCapabilityFlag,
    TijoriFeatureLock,
    TijoriIslandStatus,
    TijoriRowSelectionError,
    TijoriTable,
    TijoriTableAbsentError,
    TijoriTableAccessMetadata,
    TijoriTableCell,
    TijoriTableDepthError,
    TijoriTableKey,
    TijoriTableKeyError,
    TijoriTableMetadata,
    TijoriTableRow,
    TijoriTablesAbsentError,
    TijoriTableSchemaError,
    TijoriTableScope,
)
from fundamentals.ingest.xbrl_source import (
    NseXbrlSource,
    XbrlFetchError,
    XbrlHardBlockError,
    XbrlRetrieval,
)

__all__ = [
    "Q1_UPDATE_CUTOFF",
    "BseFetchError",
    "BseHardBlockError",
    "BseRetrieval",
    "BseSource",
    "LoadedPdf",
    "NseXbrlSource",
    "PageWord",
    "PdfBlock",
    "PdfIntegrityError",
    "PdfPage",
    "ScreenerBlockError",
    "ScreenerFetchError",
    "ScreenerResult",
    "ScreenerSource",
    "ScreenerSourceConfig",
    "SecAnnualResult",
    "SecAnnualSource",
    "SecFetchError",
    "SecSourceConfig",
    "TijoriCredentials",
    "TijoriCredentialsError",
    "TijoriError",
    "TijoriFetchError",
    "TijoriParseError",
    "TijoriSource",
    "TijoriSourceConfig",
    "TijoriCapabilityFlag",
    "TijoriFeatureLock",
    "TijoriIslandStatus",
    "TijoriRowSelectionError",
    "TijoriTable",
    "TijoriTableAbsentError",
    "TijoriTableAccessMetadata",
    "TijoriTableCell",
    "TijoriTableDepthError",
    "TijoriTableKey",
    "TijoriTableKeyError",
    "TijoriTableMetadata",
    "TijoriTableRow",
    "TijoriTableSchemaError",
    "TijoriTableScope",
    "TijoriTablesAbsentError",
    "XbrlFetchError",
    "XbrlHardBlockError",
    "XbrlRetrieval",
    "compute_file_sha256",
    "is_annual",
    "is_excluded_from_q1",
    "knowledge_time_of",
    "load_pdf",
]
