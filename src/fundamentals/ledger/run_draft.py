"""A run's earnings update as a validated ``DRAFT`` version (PREP-2b Task 6).

``preflight`` pins the predecessor quarter's ``APPROVED`` head (none for the bootstrap period)
and refuses before the pipeline writes anything. ``write_run_draft`` binds the computed values
(:mod:`run_traces`), then in one READ COMMITTED transaction locks WATCHLIST then the prior,
re-reads both heads, checks every capture behind every claim against the source cutoff, writes
the version and checks it ``AS_KNOWN`` in place; anything not passing rolls it all back.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Any, LiteralString

from psycopg import Cursor
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, ConfigDict

from fundamentals.canon.role_translation import LEGACY_CONCEPTS
from fundamentals.contracts.canonical import ValueKind
from fundamentals.contracts.comparative import RUN_PERCENT_PLACES
from fundamentals.contracts.evidence import RunMode
from fundamentals.contracts.guidance_claim import EpistemicClass, GuidanceClaim
from fundamentals.contracts.ledger import (
    Citation,
    CitationKind,
    NumericClaim,
    ReportKind,
    ReportSection,
    Rounding,
    SubjectKind,
    VersionDraft,
    VersionStatus,
)
from fundamentals.contracts.measurement_key import PeriodInterval
from fundamentals.contracts.retention import OriginalExpiredError
from fundamentals.contracts.role import FactRole
from fundamentals.contracts.snapshot import SnapshotError
from fundamentals.contracts.source_catalog import SourceCatalog
from fundamentals.evidence.capture_retention import retained_capture
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.evidence.repository_rows import capture_of
from fundamentals.ledger import store
from fundamentals.ledger.citations import _FILE_CAPTURES, _first_party
from fundamentals.ledger.claim_check import CRORE, PERCENT, UNITS, quote_qualifiers
from fundamentals.ledger.display import content_hash
from fundamentals.ledger.import_mapping import (
    ABS,
    BOUNDS_STYLE,
    CONTRACT_FIELDS,
    PCT,
    QUOTE_STYLE,
    _places,
    _slot,
    _valued,
    change_key,
    measurement_key,
)
from fundamentals.ledger.importer import _ENTITY
from fundamentals.ledger.lifecycle import (
    _LOCK,
    _NOW,
    OPEN,
    PASSING,
    check_version,
    version_status,
)
from fundamentals.ledger.run_traces import TAX, Computed, RunDraftError, bind_computed
from fundamentals.output.earnings_update import _ROLE_LABELS, REQUIRED_ROLES, EarningsUpdate
from fundamentals.output.management_ledger import LedgerStatus
from fundamentals.output.pnl_lines import OPERAND_MISSING
from fundamentals.store.fact_store import FactRef
from fundamentals.store.snapshot_store import SnapshotStore

RUN_AUTHOR = "fundamentals-run"
GUIDANCE_KEY = "ledger.{metric}.{horizon}.{scope}"  # as import_mapping keys a ledger entry
HEADING, RESULTS, CHANGES, CALCS = "heading", "results", "changes", "calculations"
GUIDANCE = "management_ledger"
CRORE_STYLE = "group-intl,trim"
CRORE_UNIT = f"{CRORE_STYLE},unit"
CARRIED = LedgerStatus.CARRIED
NONE = "- none"
INTROS = {
    RESULTS: "{{e:observed}} Reported consolidated figures:",
    CHANGES: "{{e:observed}} {{e:computed}} Prior figures and changes (current − prior; "
    "(current − prior) / prior × 100):",
    CALCS: "{{e:computed}} {{e:observed}} Derived values (the filed tax is observed):",
    GUIDANCE: "{{e:forecast}} Management guidance, each quote-anchored in its transcript:",
}
_REPORT: LiteralString = (
    "SELECT id FROM eqos.reports WHERE entity_id = %s AND period = %s AND kind = %s"
)
_HEAD: LiteralString = """SELECT max(v.id) FROM eqos.report_versions v
JOIN eqos.reports r ON r.id = v.report_id
WHERE r.entity_id = %s AND r.period = %s AND r.kind = 'EARNINGS_UPDATE'"""
_MAPPED: LiteralString = (
    "SELECT 1 FROM eqos.interpretations WHERE capture_ref_id = ANY(%s) AND status = 'MAPPED'"
)
_OPERAND_BLOBS: LiteralString = """SELECT DISTINCT c.blob_sha256
FROM eqos.calculation_trace_operands o
JOIN eqos.interpretations i ON i.id = o.interpretation_id
JOIN eqos.capture_refs c ON c.id = i.capture_ref_id
WHERE o.calculation_trace_id = ANY(%s)"""
_READ_COMMITTED: LiteralString = "SET TRANSACTION ISOLATION LEVEL READ COMMITTED"


class Prior(BaseModel):
    """The run's entity, the pinned predecessor head (``None`` for the bootstrap period) with
    its guidance claims, and the first-seen time of each required original."""

    model_config = ConfigDict(frozen=True)

    entity_id: int
    first_seen: Mapping[str, datetime]
    version_id: int | None = None
    sealed_digest: str | None = None
    entries: tuple[NumericClaim, ...] = ()


class Retrospective(BaseModel):
    """The ``--retrospective`` designation: the pinned retrieval manifest's digest and each of
    its originals' earliest NSE publication."""

    model_config = ConfigDict(frozen=True)

    manifest_sha256: str
    published: Mapping[str, datetime]


class RunDraft(BaseModel):
    """What the draft is written from: the emitted update, its guidance claims, each required
    role's selected fact, the run's originals (XBRLs incl. comparators; PDFs) and designation."""

    model_config = ConfigDict(frozen=True)

    period: str
    update: EarningsUpdate
    guidance: tuple[GuidanceClaim, ...]
    facts: Mapping[str, FactRef]
    xbrl: tuple[str, ...]
    pdfs: tuple[str, ...]
    retrospective: Retrospective | None = None


def preflight(
    pool: ConnectionPool,
    *,
    stock: str,
    period: str,
    xbrl: tuple[str, ...],
    pdfs: tuple[str, ...],
    catalog: SourceCatalog,
    snapshots: SnapshotStore,
) -> Prior:
    """The pinned prior; refuses when the period's head is open, the prior is not ``APPROVED``
    or a required original is not a retained first-party capture (an XBRL also mapped)."""
    with pool.connection() as conn, conn.cursor() as cursor:
        row = cursor.execute(_ENTITY, (stock,)).fetchone()
        if row is None:
            raise RunDraftError(f"no reporting entity {stock}")
        entity_id = int(row[0])
        _require_closed(cursor, entity_id, period)
        first_seen = {
            sha256: _original(cursor, sha256, sha256 in xbrl, catalog, snapshots)
            for sha256 in (*xbrl, *pdfs)
        }
        prior = Prior(entity_id=entity_id, first_seen=first_seen)
        bootstrap = (entity_id, period, ReportKind.BOOTSTRAP_THESIS.value)
        if cursor.execute(_REPORT, bootstrap).fetchone() is not None:
            return prior
        previous = _predecessor(period)
        head = _head(cursor, entity_id, previous)
        status = None if head is None else version_status(cursor, head)
        if head is None or status is not VersionStatus.APPROVED:
            raise RunDraftError(f"{previous} has no APPROVED head (head {head}: {status})")
        claims = store.read_version(cursor, head).claims
        quotes = tuple(c for c in claims if c.citation.kind is CitationKind.SOURCE_QUOTE)
        digest = store.sealed_digest(cursor, head)
        return prior.model_copy(
            update={"version_id": head, "sealed_digest": digest, "entries": quotes}
        )


def write_run_draft(
    pool: ConnectionPool,
    repo: EvidenceRepository,
    prior: Prior,
    run: RunDraft,
    *,
    catalog: SourceCatalog,
    snapshots: SnapshotStore,
) -> int:
    """Write the run's ``DRAFT`` version on its quarter's report; returns its id."""
    update, entity_id = run.update, prior.entity_id
    computed = bind_computed(repo, update, entity_id=entity_id)
    with pool.connection() as conn, conn.transaction(), conn.cursor() as cursor:
        cursor.execute(_READ_COMMITTED)
        cursor.execute(_LOCK, (SubjectKind.WATCHLIST.value, entity_id))
        if prior.version_id is not None:
            cursor.execute(_LOCK, (SubjectKind.REPORT_VERSION.value, prior.version_id))
            head = _head(cursor, entity_id, _predecessor(run.period))
            if (
                head != prior.version_id
                or version_status(cursor, head) is not VersionStatus.APPROVED
                or store.sealed_digest(cursor, head) != prior.sealed_digest
            ):
                raise RunDraftError(f"the pinned prior version {prior.version_id} changed")
        current = _require_closed(cursor, entity_id, run.period)
        body = _Body(computed, entity_id)
        _figures(body, update, run.facts)
        entries = {entry.claim_key: entry for entry in prior.entries}
        for guidance, rendered in zip(run.guidance, update.guidance, strict=True):
            claim = _quote(cursor, guidance, rendered.metric_label, rendered.quote, catalog)
            body.guidance(claim, _status(claim, entries.get(claim.claim_key)))
        for key, entry in entries.items():
            if key not in body.claims:
                body.guidance(entry.model_copy(update={"section_key": GUIDANCE}), CARRIED)
        claims = tuple(body.claims.values())
        _check_sources(cursor, claims, run, prior, catalog)
        sections = _sections(run, prior, body.lines)
        kind = ReportKind.EARNINGS_UPDATE
        row = cursor.execute(_REPORT, (entity_id, run.period, kind.value)).fetchone()
        report_id = (
            int(row[0])
            if row is not None
            else store.create_report(cursor, entity_id=entity_id, period=run.period, kind=kind)
        )
        assert update.derivation_cutoff is not None
        version_id = store.create_version(
            cursor,
            VersionDraft(
                report_id=report_id,
                predecessor_id=current,
                author=RUN_AUTHOR,
                knowledge_cutoff=update.derivation_cutoff,
                content_hash=content_hash(sections, claims),
                sections=sections,
                claims=claims,
            ),
        )
        boundary = cursor.execute(_NOW).fetchone()
        assert boundary is not None
        validation = check_version(
            cursor,
            version_id,
            mode=RunMode.AS_KNOWN,
            boundary=boundary[0],
            catalog=catalog,
            snapshots=snapshots,
        )
        found = [
            f"{key}: {state}" for key, state in validation.claim_states if state not in PASSING
        ]
        if found or validation.version_states:
            found += validation.version_states
            raise RunDraftError(f"the draft does not validate AS_KNOWN: {', '.join(found)}")
    return version_id


def _head(cursor: Cursor[Any], entity_id: int, period: str) -> int | None:
    """The latest version of the period's earnings update, if any."""
    row = cursor.execute(_HEAD, (entity_id, period)).fetchone()
    return None if row is None or row[0] is None else int(row[0])


def _require_closed(cursor: Cursor[Any], entity_id: int, period: str) -> int | None:
    """The period's head, refused while it is open."""
    head = _head(cursor, entity_id, period)
    if head is not None and version_status(cursor, head) in OPEN:
        raise RunDraftError(f"{period}'s head version {head} is open")
    return head


def _predecessor(period: str) -> str:
    """The previous issuer quarter: ``FY27_Q1`` → ``FY26_Q4``."""
    fiscal, quarter = period.split("_Q")
    if quarter == "1":
        return f"FY{int(fiscal[2:]) - 1:02d}_Q4"
    return f"{fiscal}_Q{int(quarter) - 1}"


def _captures(cursor: Cursor[Any], sha256: str, catalog: SourceCatalog) -> list[dict[str, Any]]:
    """The file's first-party captures, earliest first-seen first."""
    with cursor.connection.cursor(row_factory=dict_row) as own:
        rows = own.execute(_FILE_CAPTURES, (sha256,)).fetchall()
    return [row for row in rows if _first_party(row["source_id"], catalog)]


def _original(
    cursor: Cursor[Any], sha256: str, mapped: bool, catalog: SourceCatalog, snapshots: SnapshotStore
) -> datetime:
    """The first-seen time of an original's earliest first-party capture, which must be
    retained and, for an XBRL, carry a mapped interpretation."""
    captures = _captures(cursor, sha256, catalog)
    if not captures:
        raise RunDraftError(f"original {sha256[:12]} has no first-party capture")
    try:
        retained_capture(cursor.connection, snapshots, capture_of(captures[0]))
    except (SnapshotError, OriginalExpiredError) as error:
        raise RunDraftError(f"original {sha256[:12]} is not retained: {error}") from error
    ids = [row["id"] for row in captures]
    if mapped and cursor.execute(_MAPPED, (ids,)).fetchone() is None:
        raise RunDraftError(f"original {sha256[:12]} has no mapped interpretation")
    first_seen: datetime = captures[0]["first_seen"]
    return first_seen


class _Body:
    """The draft's claims by key and each section's lines, built together."""

    def __init__(self, computed: Computed, entity_id: int) -> None:
        self.computed, self.entity_id = computed, entity_id
        self.claims: dict[str, NumericClaim] = {}
        self.lines: dict[str, list[str]] = {key: [] for key in INTROS}

    def add(self, claim: NumericClaim, **citation: Any) -> str:
        """Add ``claim``, a computed or comparator value cited to its bound record; returns its
        key."""
        name, figures = claim.claim_key, self.computed.figures
        if name in self.claims:
            raise RunDraftError(f"duplicate claim key {name}")
        if claim.citation.kind is not CitationKind.SOURCE_QUOTE:
            if not citation:
                citation = (
                    {"interpretation_id": figures[name]}
                    if name in figures
                    else {"calculation_trace_id": self.computed.traces[name]}
                )
            cited = claim.citation.model_copy(update=citation)
            claim = claim.model_copy(update={"citation": cited, "unresolved": False})
        self.claims[name] = claim
        return name

    def guidance(self, claim: NumericClaim, status: LedgerStatus) -> None:
        """Add a guidance claim and its line."""
        key = self.add(claim)
        self.lines[GUIDANCE].append(
            f"- {claim.metric_label or claim.metric}: {_slot(key, BOUNDS_STYLE)} for "
            f'{claim.horizon} — {status.value}: "{_slot(key, QUOTE_STYLE)}"'
        )


def _figures(body: _Body, update: EarningsUpdate, facts: Mapping[str, FactRef]) -> None:
    """The draft's reported, comparator and calculated values and their lines."""
    entity_id = body.entity_id
    start, end = date.fromisoformat(update.period_start), date.fromisoformat(update.period_end)
    by_role = {fact.role: fact for fact in update.facts}
    keys = {
        fact.role: measurement_key(
            LEGACY_CONCEPTS[fact.concept_qname], fact.unit, entity_id, start, end
        )
        for fact in update.facts
    }
    for role in REQUIRED_ROLES:
        fact, ref = by_role[role], facts[role.value]
        claim = _valued(
            f"fact.{role.value}", RESULTS, fact.value, fact.unit, keys[role], fact.sources[0]
        )
        name = body.add(claim, fact_origin=ref.origin, fact_origin_id=ref.origin_id)
        body.lines[RESULTS].append(f"- {_ROLE_LABELS[role]}: {_slot(name, CRORE_UNIT)}")
    for comparative in update.comparatives:
        fact = next(f for f in update.facts if f.concept_qname == comparative.concept_qname)
        key, unit = keys[fact.role], fact.unit
        for change in (comparative.qoq, comparative.yoy):
            base = f"{fact.role.value}.{change.kind.value.lower()}"
            line = f"- {_ROLE_LABELS[fact.role]} {change.kind.value} vs "
            line += f"{change.period_start}..{change.period_end}"
            if change.prior_value is None or change.absolute_change is None:
                body.lines[CHANGES].append(f"{line}: not available ({change.unavailable_reason})")
                continue
            period = PeriodInterval.duration(change.period_start, change.period_end)
            held = key.model_copy(update={"period": period})
            prior = _valued(
                f"cmp.{base}.prior", CHANGES, change.prior_value, unit, held, change.prior_source
            )
            delta = change_key(key, change.kind, ABS)
            delta_claim = _valued(f"cmp.{base}.abs", CHANGES, change.absolute_change, unit, delta)
            line += f": prior {_slot(body.add(prior), CRORE_UNIT)}"
            line += f"; change {_slot(body.add(delta_claim), f'plus,{CRORE_UNIT}')}"
            if change.percent_change is None:
                line += f"; percent change not available ({change.percent_unavailable_reason})"
            else:
                percent = _valued(
                    f"cmp.{base}.pct",
                    CHANGES,
                    change.percent_change,
                    PERCENT,
                    change_key(key, change.kind, PCT),
                    precision=RUN_PERCENT_PLACES,
                    rounding=Rounding.ROUND_HALF_EVEN,
                )
                line += f", {_slot(body.add(percent), 'plus,unit')}"
            body.lines[CHANGES].append(line)
    filed = by_role[FactRole.PROFIT_BEFORE_TAX].sources[0]
    for number, calculation in enumerate(update.calculations, start=1):
        name, shown = f"calc.{number}", OPERAND_MISSING
        if calculation.result != OPERAND_MISSING:
            unit = PERCENT if calculation.label.endswith("(%)") else CRORE
            value = Decimal(calculation.result.replace(",", ""))
            observed = name in body.computed.figures  # the filed tax expense
            measured = TAX if observed else calculation.label
            key = measurement_key(measured, unit, entity_id, start, end)
            body.add(_valued(name, CALCS, value, unit, key, filed if observed else None))
            shown = _slot(name, CRORE_STYLE if unit == CRORE else "")
        body.lines[CALCS].append(f"- {calculation.label} = {shown}")


def _quote(
    cursor: Cursor[Any],
    guidance: GuidanceClaim,
    metric_label: str,
    quote: str,
    catalog: SourceCatalog,
) -> NumericClaim:
    """A guidance claim as a ``SOURCE_QUOTE`` on its transcript's first-party capture (its
    contract binds through the sealed imports, M9)."""
    source = guidance.provenance
    captures = _captures(cursor, source.file_sha256, catalog)
    return NumericClaim(
        claim_key=GUIDANCE_KEY.format(
            metric=guidance.metric, horizon=guidance.horizon, scope=guidance.scope.value
        ),
        section_key=GUIDANCE,
        citation=Citation(
            kind=CitationKind.SOURCE_QUOTE,
            source_sha256=source.file_sha256,
            capture_ref_id=captures[0]["id"] if captures else None,
            anchor=f"p{source.page}.b{source.block}.{source.span}",
            quote=quote,
        ),
        value_kind=UNITS.get(guidance.unit, (ValueKind.CURRENCY_AMOUNT,))[0],
        qualifiers=tuple(sorted(quote_qualifiers(quote))),
        precision=max(_places(guidance.lower_bound), _places(guidance.upper_bound)),
        rounding=Rounding.ROUND_HALF_EVEN,
        epistemic_class=EpistemicClass.FORECAST,
        metric_label=metric_label,
        **guidance.model_dump(include=CONTRACT_FIELDS) | {"scope": guidance.scope.value},
    )


def _status(claim: NumericClaim, entry: NumericClaim | None) -> LedgerStatus:
    """``NEW`` with no prior entry; ``REAFFIRMED`` only when bounds, unit, constant currency
    and qualifiers all equal the prior's (F11); else ``MODIFIED``."""
    if entry is None:
        return LedgerStatus.NEW
    fields = ("lower_bound", "upper_bound", "unit", "constant_currency", "qualifiers")
    same = all(getattr(claim, name) == getattr(entry, name) for name in fields)
    return LedgerStatus.REAFFIRMED if same else LedgerStatus.MODIFIED


def _check_sources(
    cursor: Cursor[Any],
    claims: tuple[NumericClaim, ...],
    run: RunDraft,
    prior: Prior,
    catalog: SourceCatalog,
) -> None:
    """Every capture behind every claim is one of the run's originals or one the prior cites,
    first seen (retrospective: published, contract a) by the source cutoff."""
    cutoff = run.update.source_cutoff
    assert cutoff is not None
    traces = [c.citation.calculation_trace_id for c in claims if c.citation.calculation_trace_id]
    blobs = {c.citation.source_sha256 for c in claims if c.citation.source_sha256 is not None}
    blobs |= {row[0] for row in cursor.execute(_OPERAND_BLOBS, (traces,)).fetchall()}
    allowed = {*run.xbrl, *run.pdfs, *(entry.citation.source_sha256 for entry in prior.entries)}
    if outside := sorted(blob[:12] for blob in blobs - allowed):
        raise RunDraftError(f"captures not in the run's package: {', '.join(outside)}")
    late = []
    for blob in sorted(blobs):
        if run.retrospective is not None:
            at = run.retrospective.published.get(blob)
        else:
            captures = _captures(cursor, blob, catalog)
            at = captures[0]["first_seen"] if captures else None
        if at is None or at > cutoff:
            late.append(f"{blob[:12]} ({at})")
    if late:
        raise RunDraftError(f"captures past the source cutoff {cutoff}: {', '.join(late)}")


def _sections(
    run: RunDraft, prior: Prior, lines: Mapping[str, list[str]]
) -> tuple[ReportSection, ...]:
    """The heading, then each section's lines; every number is a claim placeholder or a
    structural date, id or digest."""
    update, retrospective = run.update, run.retrospective
    assert update.source_cutoff is not None and update.derivation_cutoff is not None
    designation = (
        "Ordinary run: every capture first seen by the source cutoff."
        if retrospective is None
        else "Retrospective workflow demonstration (retrieval manifest sha256 "
        f"{retrospective.manifest_sha256}): originals registered after the source cutoff, "
        "admitted as published by it; it cannot prove historical possession or absence of "
        "hindsight."
    )
    pinned = f"version:{prior.version_id} digest {prior.sealed_digest}"
    seen = "; ".join(f"sha256 {sha} at {at.isoformat()}" for sha, at in prior.first_seen.items())
    heading = (
        f"# {update.issuer_name} ({update.nse_symbol}) — {update.issuer_quarter_label}\n\n"
        f"{{{{e:computed}}}} Run draft of {run.period}. Source cutoff "
        f"{update.source_cutoff.isoformat()}; derivation cutoff "
        f"{update.derivation_cutoff.isoformat()}.\n{designation}\n"
        f"Prior: {'none (bootstrap period)' if prior.version_id is None else pinned}.\n"
        f"Originals first seen: {seen}.\n\n"
    )
    bodies = [(HEADING, heading)] + [
        (
            key,
            f"## {key}\n\n{intro}\n" + "".join(f"{line}\n" for line in lines[key] or [NONE]) + "\n",
        )
        for key, intro in INTROS.items()
    ]
    return tuple(
        ReportSection(ordinal=ordinal, section_key=key, body=body)
        for ordinal, (key, body) in enumerate(bodies)
    )
