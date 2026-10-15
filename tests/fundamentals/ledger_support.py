"""Ledger test support: the ledger's tables and a driver over the runtime, panel and owner pools.

Every write goes through ``fundamentals.ledger.store`` inside one transaction of the named
role's real login pool, so the triggers and grants under test are the ones a command meets.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from pg_support import PgTestDatabase
from psycopg import Cursor
from psycopg_pool import ConnectionPool
from selection_support import key

from fundamentals.contracts.canonical import ValueKind
from fundamentals.contracts.evidence import RunMode
from fundamentals.contracts.guidance_claim import EpistemicClass
from fundamentals.contracts.ledger import (
    Citation,
    CitationKind,
    ClaimState,
    DecisionKind,
    DecisionRecord,
    NumericClaim,
    ReportKind,
    ReportSection,
    Rounding,
    SubjectKind,
    Validation,
    VersionDraft,
    VersionState,
)
from fundamentals.ledger import store
from fundamentals.pg.settings import PgRole

# The tables 0012 and 0013 create.
LEDGER_TABLES = frozenset(
    {
        "panel_reviews",
        "disposition_proposals",
        "reports",
        "report_versions",
        "import_sources",
        "report_sections",
        "numeric_claims",
        "validations",
        "validation_claim_states",
        "qa_records",
        "decisions",
        "legacy_acquisitions",
    }
)
CUTOFF = datetime(2026, 7, 31, 18, 30, tzinfo=UTC)
CONTENT_HASH = "0" * 64
PINNED_INPUTS = "1" * 64
RULING = "fixture ruling"
SECTION = ReportSection(ordinal=0, section_key="preamble", body="{{e:computed}} {{c:calc.1|}}")


def claim(trace_id: int, claim_key: str = "calc.1") -> NumericClaim:
    """A resolved ``CALCULATION`` claim on one stored trace."""
    return NumericClaim(
        claim_key=claim_key,
        section_key=SECTION.section_key,
        citation=Citation(kind=CitationKind.CALCULATION, calculation_trace_id=trace_id),
        measurement_key=key(),
        value_kind=ValueKind.PERCENTAGE,
        unit="%",
        value=Decimal("12.34"),
        precision=2,
        rounding=Rounding.ROUND_HALF_UP,
        epistemic_class=EpistemicClass.COMPUTED,
    )


SELF_CITED = NumericClaim(
    claim_key="falsifier.F1",
    section_key=SECTION.section_key,
    citation=Citation(kind=CitationKind.POLICY),
    value_kind=ValueKind.PERCENTAGE,
    unit="%",
    value=Decimal("11.55"),
    precision=2,
    rounding=Rounding.ROUND_HALF_UP,
    epistemic_class=EpistemicClass.OPINION,
)


class Ledger:
    """One seeded test database's ledger, driven through the three role pools."""

    def __init__(self, pools: dict[PgRole, ConnectionPool], seeded: dict[str, int]) -> None:
        self.pools = pools
        self.entity_id = seeded["_entity"]
        self.trace_id = seeded["calculation_traces"]
        self._periods = 0

    def report(self) -> int:
        """A new report (runtime) for a fresh period."""
        self._periods += 1
        with self._cursor(PgRole.RUNTIME) as cursor:
            return store.create_report(
                cursor,
                entity_id=self.entity_id,
                period=f"FY27_Q{self._periods}",
                kind=ReportKind.EARNINGS_UPDATE,
            )

    def draft(self, report_id: int, predecessor_id: int | None = None, **update: Any) -> int:
        """A runtime draft version with one section and one claim."""
        with self._cursor(PgRole.RUNTIME) as cursor:
            return store.create_version(
                cursor, self.version_draft(report_id, predecessor_id, **update)
            )

    def version_draft(
        self, report_id: int, predecessor_id: int | None = None, **update: Any
    ) -> VersionDraft:
        """The draft :meth:`draft` inserts, with any field replaced."""
        return VersionDraft(
            report_id=report_id,
            predecessor_id=predecessor_id,
            author="fixture-author",
            knowledge_cutoff=CUTOFF,
            content_hash=CONTENT_HASH,
            sections=(SECTION,),
            claims=(claim(self.trace_id),),
        ).model_copy(update=update)

    def imported(
        self,
        report_id: int,
        predecessor_id: int | None = None,
        *,
        approve: bool = False,
        digest: str | None = None,
    ) -> int:
        """An imported version sealed by ``IMPORT_SEAL`` (with ``digest``, else its own) and
        optionally approved, in one panel transaction."""
        draft = self.version_draft(
            report_id,
            predecessor_id,
            claims=(SELF_CITED,),
            import_sources=(("q0-approved-thesis.md", b"# Q0\n"),),
        )
        with self._cursor(PgRole.PANEL) as cursor:
            version_id = store.create_version(cursor, draft)
            seal = store.insert_decision(
                cursor,
                subject_kind=SubjectKind.REPORT_VERSION,
                subject_id=version_id,
                kind=DecisionKind.IMPORT_SEAL,
                predecessor_id=None,
                sealed_digest=digest or store.sealed_digest(cursor, version_id),
            )
            if approve:
                store.insert_decision(
                    cursor,
                    subject_kind=SubjectKind.REPORT_VERSION,
                    subject_id=version_id,
                    kind=DecisionKind.IMPORTED_APPROVAL,
                    predecessor_id=seal.id,
                    sealed_digest=seal.sealed_digest,
                    original_approval_sha256="2" * 64,
                    ruling="accept all",
                    decided_on=CUTOFF.date(),
                )
        return version_id

    def decide(
        self, role: PgRole, subject_id: int, kind: DecisionKind, **fields: Any
    ) -> DecisionRecord:
        """A decision on a version naming its current head and digest, unless ``fields`` say
        otherwise; owner decisions carry a ruling."""
        subject_kind = fields.pop("subject_kind", SubjectKind.REPORT_VERSION)
        with self._cursor(role) as cursor:
            head = store.chain_head(cursor, subject_kind, subject_id)
            defaults: dict[str, Any] = {
                "predecessor_id": None if head is None else head.id,
                "ruling": RULING if role is PgRole.OWNER else None,
            }
            if subject_kind is SubjectKind.REPORT_VERSION:
                defaults["sealed_digest"] = store.sealed_digest(cursor, subject_id)
            return store.insert_decision(
                cursor,
                subject_kind=subject_kind,
                subject_id=subject_id,
                kind=kind,
                **(defaults | fields),
            )

    def head(self, version_id: int) -> DecisionRecord:
        """The version's latest decision."""
        with self._cursor(PgRole.RUNTIME) as cursor:
            head = store.chain_head(cursor, SubjectKind.REPORT_VERSION, version_id)
        assert head is not None
        return head

    def submit(self, version_id: int) -> DecisionRecord:
        """The runtime's ``SUBMIT``."""
        return self.decide(PgRole.RUNTIME, version_id, DecisionKind.SUBMIT)

    def validate(
        self,
        version_id: int,
        *,
        mode: RunMode = RunMode.AS_KNOWN,
        state: ClaimState | None = ClaimState.MATCH,
        version_states: tuple[VersionState, ...] = (),
    ) -> int:
        """A runtime validation giving every claim ``state`` (none when ``None``)."""
        with self._cursor(PgRole.RUNTIME) as cursor:
            keys = cursor.execute(
                "SELECT claim_key FROM eqos.numeric_claims WHERE version_id = %s", (version_id,)
            ).fetchall()
            return store.insert_validation(
                cursor,
                Validation(
                    version_id=version_id,
                    checker_version="fixture-checker",
                    mode=mode,
                    overlay_position=CUTOFF,
                    pinned_input_sha256=PINNED_INPUTS,
                    sealed_digest=store.sealed_digest(cursor, version_id),
                    claim_states=() if state is None else tuple((k, state) for (k,) in keys),
                    version_states=version_states,
                ),
            )

    def approve(self, version_id: int, validation_id: int) -> DecisionRecord:
        """The owner's ``APPROVE`` binding ``validation_id``."""
        return self.decide(
            PgRole.OWNER, version_id, DecisionKind.APPROVE, validation_id=validation_id
        )

    @contextmanager
    def _cursor(self, role: PgRole) -> Iterator[Cursor[Any]]:
        """A cursor in one committed transaction of the role's pool."""
        with self.pools[role].connection() as conn, conn.transaction(), conn.cursor() as cursor:
            yield cursor


@pytest.fixture
def ledger(pg_db: PgTestDatabase, seeded: dict[str, int]) -> Iterator[Ledger]:
    """The ledger of a seeded test database with its runtime, panel and owner pools open."""
    with ExitStack() as stack:
        pools = {
            role: stack.enter_context(pg_db.role_pool(role))
            for role in (PgRole.RUNTIME, PgRole.PANEL, PgRole.OWNER)
        }
        yield Ledger(pools, seeded)
