"""What each filing family's comparison run reads (plan D8 R6, R8).

``FINANCIAL_RESULTS`` keeps exactly the D1a sources, framework and document type. A
``SHAREHOLDING`` run reads the SHP XBRL surface under framework ``UNKNOWN`` and declares the
listing as the XBRL side's prerequisite surface: its failed acquisition makes that side
``UNAVAILABLE``, but it never supplies a member. The XBRL extractor pin by family is
``run_config.extractor_pin``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.canonical import Basis, DocumentType, Representation
from fundamentals.contracts.evidence import FilingFamily
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.contracts.source_catalog import SHP_LISTING, SHP_XBRL
from fundamentals.evidence.capture_intake import FirstPartySurface

ANY_FISCAL_MONTH = 3  # an instant's period kind ignores the fiscal calendar (plan D8 R6)


class RunFamily(BaseModel):
    """One family's run boundary: framework, document type, sources and prerequisites."""

    model_config = ConfigDict(frozen=True)

    framework: AccountingFramework
    document_type: DocumentType
    sources: tuple[str, ...]
    prerequisites: tuple[tuple[Representation, str], ...] = ()
    bases: tuple[Basis, ...] | None = None
    fiscal_calendar: bool = True


RUN_FAMILIES: dict[FilingFamily, RunFamily] = {
    FilingFamily.FINANCIAL_RESULTS: RunFamily(
        framework=AccountingFramework.IND_AS,
        document_type=DocumentType.FINANCIAL_RESULTS,
        sources=tuple(sorted(surface.value for surface in FirstPartySurface)),
    ),
    FilingFamily.SHAREHOLDING: RunFamily(
        framework=AccountingFramework.UNKNOWN,
        document_type=DocumentType.SHAREHOLDING_PATTERN,
        sources=(SHP_XBRL[1],),
        prerequisites=((Representation.XBRL, SHP_LISTING[1]),),
        bases=(Basis.STANDALONE,),  # R4: the filing declares no basis
        fiscal_calendar=False,  # R6: every period is an instant
    ),
}
