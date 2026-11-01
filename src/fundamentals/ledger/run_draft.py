"""A run's earnings update as a validated ``DRAFT`` version (PREP-2b Task 6).

``preflight`` pins the predecessor quarter's ``APPROVED`` head (none for the bootstrap period:
the one period with a bootstrap thesis version) and refuses before the pipeline writes
anything; the pipeline binds the computed values (:mod:`run_traces`) before it stores a fact.
``write_run_draft`` then, in one READ COMMITTED transaction, locks WATCHLIST then the prior,
re-reads both heads (or the bootstrap period), checks every capture behind every claim against
the source cutoff, writes the version and checks it ``AS_KNOWN`` in place; anything not passing
rolls it all back. A rework of a version with claim rejections (``Prior.rework``, PREP-5)
carries that version's claims on every line it does not rerun; ``--full-successor``
(``Prior.full_successor``) reruns it whole. Either way the period's head must still be the
reworked version, before the run's first write and again under the lock. ``recall`` retrieves
the stock's promoted memory at a store-clock boundary before the pipeline starts; its line is
sealed in the heading and nothing else reads it (PILOT-GAP memory). A QoQ prior cites the
predecessor run version's admitted ``fact.<role>`` when its key, value and file are the fact's
(``predecessor``, PILOT-4), checked before the run's first write and swapped in at the write;
that version's comparison runs join the draft's pins. The derived falsifier sections and
their threshold claims follow, bound to the thesis approved at the derivation cutoff
(:mod:`falsifier_status`), then the risk probe (:mod:`risk_probe`).
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping, Sequence, Set
from datetime import date, datetime
from typing import Any, LiteralString

from psycopg import Cursor
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, ConfigDict

from fundamentals.canon.role_translation import LEGACY_CONCEPTS
from fundamentals.compare.queue import lock_queue
from fundamentals.contracts.canonical import ValueKind
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
from fundamentals.contracts.retention import OriginalExpiredError
from fundamentals.contracts.snapshot import SnapshotError
from fundamentals.contracts.source_catalog import SourceCatalog
from fundamentals.evidence.capture_retention import retained_capture
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.evidence.repository_rows import capture_of
from fundamentals.ledger import store
from fundamentals.ledger.citations import _FILE_CAPTURES, TRACES, _first_party
from fundamentals.ledger.claim_check import UNITS, quote_qualifiers
from fundamentals.ledger.display import FILED, content_hash
from fundamentals.ledger.falsifier_status import approved_thesis, derived, evaluate
from fundamentals.ledger.import_mapping import (
    BOUNDS_STYLE,
    CONTRACT_FIELDS,
    QUOTE_STYLE,
    _places,
    _slot,
    _valued,
    measurement_key,
    refs,
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
from fundamentals.ledger.rework import Rework, plan, rejected
from fundamentals.ledger.risk_probe import Probe, probe_section
from fundamentals.ledger.run_traces import (
    CALCS,
    CHANGES,
    CRORE_UNIT,
    DISCLOSED,
    NOT_PERFORMED,
    OPEN_QUESTIONS,
    Carry,
    Line,
    RunDraftError,
    _shown,
    cite,
)
from fundamentals.memory.pg_store import PgMemoryStore
from fundamentals.output.earnings_update import _ROLE_LABELS, REQUIRED_ROLES, EarningsUpdate
from fundamentals.output.management_ledger import LedgerStatus
from fundamentals.store.fact_store import FactRef
from fundamentals.store.snapshot_store import SnapshotStore

RUN_AUTHOR = "fundamentals-run"
GUIDANCE_KEY = "ledger.{metric}.{horizon}.{scope}"  # as import_mapping keys a ledger entry
HEADING, RESULTS = "heading", "results"
FACT_PREFIX, QOQ_PRIOR = "fact.", ".qoq.prior"
GUIDANCE = "management_ledger"
CARRIED = LedgerStatus.CARRIED
NONE = "- none"
FISCAL_PERIOD = re.compile(r"FY\d{2,4}(?:_Q[1-4])?")
UNSPECIFIED = " (target period not specified by the extracted guidance)"
UNCOMPARED = " (comparability not established)"
INTROS = {
    RESULTS: "{{e:observed}} Reported consolidated figures:",
    CHANGES: "{{e:observed}} {{e:computed}} Prior figures and changes (current − prior; "
    "(current − prior) / prior × 100):",
    CALCS: "{{e:computed}} {{e:observed}} Derived values (the filed tax is observed):",
    GUIDANCE: "{{e:forecast}} Management guidance, each quote-anchored in its transcript:",
    OPEN_QUESTIONS: "{{e:computed}} Questions the extracted data leaves open (this pipeline "
    "drafts no analyst questions, so the list does not show that no others exist):",
    NOT_PERFORMED: "{{e:computed}} This version does not contain:",
}
NOT_DONE = (
    "- forward scenarios",
    "- forensic checks beyond the risk probe's ratio checks (see `risk_probe` for the sources "
    "it does not assess)",
    "- a management-credibility assessment",
    "- a narrative thesis-impact assessment",
    "- materiality decisions: no claim carries a materiality decision, because the pipeline "
    "produces no materiality policy, candidate inventory or per-claim decision",
)
QUESTION = (
    "- Which fiscal year or window applies to {label}? Why it matters: the "
    "guidance cannot be checked against an outcome period without it. Evidence required: the "
    "transcript context around the quoted guidance {ref}, or a later management statement "
    "naming the period. Status: open; owner not assigned."
)
_REPORT: LiteralString = (
    "SELECT id FROM eqos.reports WHERE entity_id = %s AND period = %s AND kind = %s"
)
_HEAD: LiteralString = """SELECT max(v.id) FROM eqos.report_versions v
JOIN eqos.reports r ON r.id = v.report_id
WHERE r.entity_id = %s AND r.period = %s AND r.kind = 'EARNINGS_UPDATE'"""
_BOOTSTRAPS: LiteralString = """SELECT DISTINCT r.period FROM eqos.reports r
JOIN eqos.report_versions v ON v.report_id = r.id
WHERE r.entity_id = %s AND r.kind = 'BOOTSTRAP_THESIS'"""
# The captures behind every operand of the given traces and of the traces they reach.
_OPERAND_BLOBS: LiteralString = (
    "WITH RECURSIVE "
    + TRACES
    + """ SELECT DISTINCT c.blob_sha256
FROM traces t JOIN eqos.calculation_trace_operands o ON o.calculation_trace_id = t.id
JOIN eqos.interpretations i ON i.id = o.interpretation_id
JOIN eqos.capture_refs c ON c.id = i.capture_ref_id"""
)
_READ_COMMITTED: LiteralString = "SET TRANSACTION ISOLATION LEVEL READ COMMITTED"
MEMORY_LINE = "Memory retrieved at store time {boundary}: {items}."
_MEMORY_ITEM = "memory:{id} (needs revalidation: {flag}; supports {supports})"


class Successor(BaseModel):
    """A ``--full-successor`` run: the version it reruns whole and the claims rejected there."""

    model_config = ConfigDict(frozen=True)

    head: int
    rejected: tuple[str, ...]


class Prior(BaseModel):
    """The run's entity, the pinned predecessor head (``None`` for the bootstrap period) with
    its guidance claims and, for a run-generated head, its ``fact.*`` claims and pinned runs,
    the first-seen time of each required original, and the period's head this run reworks,
    selectively or whole."""

    model_config = ConfigDict(frozen=True)

    entity_id: int
    first_seen: Mapping[str, datetime]
    version_id: int | None = None
    sealed_digest: str | None = None
    entries: tuple[NumericClaim, ...] = ()
    facts: tuple[NumericClaim, ...] = ()
    pinned_run_ids: tuple[int, ...] = ()
    rework: Rework | None = None
    full_successor: Successor | None = None


class Retrospective(BaseModel):
    """The ``--retrospective`` designation: the pinned retrieval manifest's digest and each of
    its originals' earliest NSE publication."""

    model_config = ConfigDict(frozen=True)

    manifest_sha256: str
    published: Mapping[str, datetime]


class RunDraft(BaseModel):
    """What the draft is written from: the emitted update, its guidance claims, each required
    role's selected fact, its bound changes and calculations lines, its risk probe, the run's
    originals (XBRLs incl. comparators; PDFs), the comparison run its facts were admitted from
    and designation."""

    model_config = ConfigDict(frozen=True)

    period: str
    update: EarningsUpdate
    guidance: tuple[GuidanceClaim, ...]
    facts: Mapping[str, FactRef]
    lines: tuple[Line, ...]
    probe: Probe
    xbrl: tuple[str, ...]
    pdfs: tuple[str, ...]
    memory: str
    run_id: int
    retrospective: Retrospective | None = None


def boundary(cursor: Cursor[Any]) -> datetime:
    """The store time after every memory decision or support-falsifying write stamped before
    it has committed: the queue lock, then the clock."""
    lock_queue(cursor)
    row = cursor.execute(_NOW).fetchone()
    assert row is not None
    at: datetime = row[0]
    return at


def recall(pool: ConnectionPool, entity_id: int, *, at: datetime | None = None) -> str:
    """The heading line of the stock's promoted memory as known at a fresh boundary (or a
    replay at ``at``): each item's id, revalidation flag and support ids."""
    if at is None:
        with pool.connection() as conn, conn.transaction(), conn.cursor() as cursor:
            at = boundary(cursor)
    found = PgMemoryStore(pool).retrieve("", stock=entity_id, cutoff=at)
    items = "; ".join(
        _MEMORY_ITEM.format(
            id=item.id,
            flag="yes" if item.needs_revalidation else "no",
            supports=", ".join(
                f"{ref.target.value.removesuffix('_id')}:{ref.target_id}" for ref in item.supports
            ),
        )
        for item in found
    )
    return MEMORY_LINE.format(boundary=at.isoformat(), items=items or "none")


def preflight(
    pool: ConnectionPool,
    *,
    stock: str,
    period: str,
    xbrl: tuple[str, ...],
    pdfs: tuple[str, ...],
    catalog: SourceCatalog,
    snapshots: SnapshotStore,
    full_successor: bool = False,
) -> Prior:
    """The pinned prior; refuses when the period's head is open, the prior is not ``APPROVED``
    or a required original, or a capture a prior guidance claim cites, is not a retained
    first-party capture. A head with claim rejections is reworked; ``full_successor`` reruns it
    whole and needs one."""
    with pool.connection() as conn, conn.cursor() as cursor:
        row = cursor.execute(_ENTITY, (stock,)).fetchone()
        if row is None:
            raise RunDraftError(f"no reporting entity {stock}")
        entity_id = int(row[0])
        current = _require_closed(cursor, entity_id, period)
        first_seen = {
            sha256: _original(cursor, sha256, catalog, snapshots) for sha256 in (*xbrl, *pdfs)
        }
        prior = Prior(entity_id=entity_id, first_seen=first_seen)
        if full_successor:
            keys = () if current is None else rejected(cursor, current)
            if current is None or not keys:
                raise RunDraftError(f"--full-successor: {period}'s head has no claim rejections")
            prior = prior.model_copy(
                update={"full_successor": Successor(head=current, rejected=keys)}
            )
        elif current is not None:
            prior = prior.model_copy(
                update={"rework": plan(cursor, EvidenceRepository(pool), current)}
            )
        if _bootstrap(cursor, entity_id, period):
            return prior
        previous = _predecessor(period)
        head = _head(cursor, entity_id, previous)
        status = None if head is None else version_status(cursor, head)
        if head is None or status is not VersionStatus.APPROVED:
            raise RunDraftError(f"{previous} has no APPROVED head (head {head}: {status})")
        version = store.read_version(cursor, head)
        claims, pins = version.claims, version.pinned_run_ids
        quotes = tuple(c for c in claims if c.citation.kind is CitationKind.SOURCE_QUOTE)
        facts = tuple(c for c in claims if pins and c.claim_key.startswith(FACT_PREFIX))
        for sha256 in {quote.citation.source_sha256 for quote in quotes}:
            assert sha256 is not None
            _original(cursor, sha256, catalog, snapshots)
        digest = store.sealed_digest(cursor, head)
        return prior.model_copy(
            update={
                "version_id": head,
                "sealed_digest": digest,
                "entries": quotes,
                "facts": facts,
                "pinned_run_ids": pins,
            }
        )


def write_run_draft(
    pool: ConnectionPool,
    prior: Prior,
    run: RunDraft,
    *,
    catalog: SourceCatalog,
    snapshots: SnapshotStore,
) -> int:
    """Write the run's ``DRAFT`` version on its quarter's report; returns its id."""
    update, entity_id = run.update, prior.entity_id
    with pool.connection() as conn, conn.transaction(), conn.cursor() as cursor:
        cursor.execute(_READ_COMMITTED)
        cursor.execute(_LOCK, (SubjectKind.WATCHLIST.value, entity_id))
        if prior.version_id is None:
            if not _bootstrap(cursor, entity_id, run.period):
                raise RunDraftError(f"{run.period} is no longer the bootstrap period")
        else:
            cursor.execute(_LOCK, (SubjectKind.REPORT_VERSION.value, prior.version_id))
            head = _head(cursor, entity_id, _predecessor(run.period))
            if (
                head != prior.version_id
                or version_status(cursor, head) is not VersionStatus.APPROVED
                or store.sealed_digest(cursor, head) != prior.sealed_digest
            ):
                raise RunDraftError(f"the pinned prior version {prior.version_id} changed")
        current = _require_closed(cursor, entity_id, run.period)
        check_head(cursor, prior, run.period)
        reworked = prior.rework
        carried = {} if reworked is None else {k: reworked.claims[k] for k in reworked.carried}
        run_ids = {run.run_id, *prior.pinned_run_ids}
        if reworked is not None:  # carried citations keep their head's comparison runs
            run_ids.update(store.read_version(cursor, reworked.head).pinned_run_ids)
        body = _Body()
        for text, claim in _results(update, run.facts, entity_id):
            body.add(RESULTS, text, carried.get(claim.claim_key, claim))
        for line in run.lines:
            body.add(line.section, _shown(line), *line.claims)
        for text, claim in _guidance(cursor, run.guidance, update, prior, catalog):
            shown = carried.get(claim.claim_key, claim)
            body.add(GUIDANCE, text, shown)
            if not _specified(shown.horizon):
                body.lines[OPEN_QUESTIONS].append(_question(shown))
        claims = predecessor(prior, tuple(body.claims.values())) + run.probe.claims
        assert update.derivation_cutoff is not None
        bound = approved_thesis(cursor, entity_id, update.nse_symbol, update.derivation_cutoff)
        by_key = {claim.claim_key: claim for claim in claims}
        rows = () if bound is None else evaluate(bound, by_key, run.lines, run.probe.stale_keys)
        falsifiers, thresholds = derived(bound, rows)
        _check_sources(cursor, claims, run, prior, catalog)
        derived_sections = (*falsifiers, probe_section(run.probe, rows))
        sections = _sections(run, prior, body.lines, derived_sections)
        claims += thresholds
        kind = ReportKind.EARNINGS_UPDATE
        row = cursor.execute(_REPORT, (entity_id, run.period, kind.value)).fetchone()
        report_id = (
            int(row[0])
            if row is not None
            else store.create_report(cursor, entity_id=entity_id, period=run.period, kind=kind)
        )
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
                pinned_run_ids=tuple(sorted(run_ids)),
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


def predecessor(prior: Prior, claims: tuple[NumericClaim, ...]) -> tuple[NumericClaim, ...]:
    """``claims`` with each QoQ prior cited, unlabelled, to the prior head's admitted
    ``fact.<role>``; refuses one whose key, value or file is not that fact's."""
    facts = {c.claim_key: c for c in prior.facts if c.citation.fact_origin_id is not None}
    found = []
    for claim in claims:
        role = claim.claim_key.removeprefix("cmp.").removesuffix(QOQ_PRIOR)
        fact = facts.get(FACT_PREFIX + role) if claim.claim_key.endswith(QOQ_PRIOR) else None
        if fact is not None:
            assert claim.measurement_key is not None and fact.measurement_key is not None
            if (
                claim.measurement_key.digest() != fact.measurement_key.digest()
                or claim.value != fact.value
                or claim.citation.source_sha256 != fact.citation.source_sha256
            ):
                raise RunDraftError(f"{claim.claim_key} is not version {prior.version_id}'s fact")
            cited = cite(
                claim,
                fact_origin=fact.citation.fact_origin,
                fact_origin_id=fact.citation.fact_origin_id,
                interpretation_id=None,
            )
            labels = tuple(q for q in claim.qualifiers if q != FILED)
            claim = cited.model_copy(update={"qualifiers": labels})
        found.append(claim)
    return tuple(found)


def gate_lines(
    cursor: Cursor[Any],
    gate: Carry,
    update: EarningsUpdate,
    guidance: tuple[GuidanceClaim, ...],
    prior: Prior,
    catalog: SourceCatalog,
) -> None:
    """The run's results and guidance lines through a rework's gate, before any fact is
    stored."""
    for text, claim in _results(update, {}, prior.entity_id):
        gate.line(RESULTS, text, (claim,))
    for text, claim in _guidance(cursor, guidance, update, prior, catalog):
        gate.line(GUIDANCE, text, (claim,))


def check_head(cursor: Cursor[Any], prior: Prior, period: str) -> None:
    """Refuse unless the period's head is still the version this run reworks, if any."""
    reworked = prior.rework or prior.full_successor
    if reworked is not None and (head := _head(cursor, prior.entity_id, period)) != reworked.head:
        raise RunDraftError(f"{period}'s head is version {head}, not the reworked {reworked.head}")


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


def _bootstrap(cursor: Cursor[Any], entity_id: int, period: str) -> bool:
    """Whether ``period`` is the stock's bootstrap period: the one period with a bootstrap
    thesis version (several refuse)."""
    periods = sorted(row[0] for row in cursor.execute(_BOOTSTRAPS, (entity_id,)).fetchall())
    if len(periods) > 1:
        raise RunDraftError(f"ambiguous bootstrap period: {', '.join(periods)}")
    return periods == [period]


def _original(
    cursor: Cursor[Any], sha256: str, catalog: SourceCatalog, snapshots: SnapshotStore
) -> datetime:
    """The first-seen time of an original's earliest first-party capture, which must be
    retained."""
    captures = _captures(cursor, sha256, catalog)
    if not captures:
        raise RunDraftError(f"original {sha256[:12]} has no first-party capture")
    try:
        retained_capture(cursor.connection, snapshots, capture_of(captures[0]))
    except (SnapshotError, OriginalExpiredError) as error:
        raise RunDraftError(f"original {sha256[:12]} is not retained: {error}") from error
    first_seen: datetime = captures[0]["first_seen"]
    return first_seen


class _Body:
    """The draft's claims by key and each section's lines, built together."""

    def __init__(self) -> None:
        self.claims: dict[str, NumericClaim] = {}
        self.lines: dict[str, list[str]] = {key: [] for key in INTROS}

    def add(self, section: str, line: str, *claims: NumericClaim) -> None:
        """Add a line of ``section`` and the claims it shows."""
        for claim in claims:
            if claim.claim_key in self.claims:
                raise RunDraftError(f"duplicate claim key {claim.claim_key}")
            self.claims[claim.claim_key] = claim
        self.lines[section].append(line)


def _results(
    update: EarningsUpdate, facts: Mapping[str, FactRef], entity_id: int
) -> Iterator[tuple[str, NumericClaim]]:
    """Each required role's line and reported value, cited to the run's selected fact (uncited
    for a role with none)."""
    start, end = date.fromisoformat(update.period_start), date.fromisoformat(update.period_end)
    by_role = {fact.role: fact for fact in update.facts}
    for role in REQUIRED_ROLES:
        fact, ref = by_role[role], facts.get(role.value)
        key = measurement_key(LEGACY_CONCEPTS[fact.concept_qname], fact.unit, entity_id, start, end)
        name = f"fact.{role.value}"
        claim = _valued(name, RESULTS, fact.value, fact.unit, key, fact.sources[0])
        if ref is not None:
            claim = cite(claim, fact_origin=ref.origin, fact_origin_id=ref.origin_id)
        yield f"- {_ROLE_LABELS[role]}: {_slot(name, CRORE_UNIT)} {refs([name])}", claim


def _guidance(
    cursor: Cursor[Any],
    guidance: tuple[GuidanceClaim, ...],
    update: EarningsUpdate,
    prior: Prior,
    catalog: SourceCatalog,
) -> list[tuple[str, NumericClaim]]:
    """Each guidance line and claim, then the prior's entries the run did not restate."""
    entries = {entry.claim_key: entry for entry in prior.entries}
    found = []
    for claim_source, rendered in zip(guidance, update.guidance, strict=True):
        claim = _quote(cursor, claim_source, rendered.metric_label, rendered.quote, catalog)
        found.append((_guided(claim, _status(claim, entries.get(claim.claim_key))), claim))
    stated = {claim.claim_key for _, claim in found}
    for key, entry in entries.items():
        if key not in stated:
            carried = entry.model_copy(update={"section_key": GUIDANCE})
            found.append((_guided(carried, CARRIED), carried))
    return found


def _guided(claim: NumericClaim, status: LedgerStatus) -> str:
    """A guidance line; a status against a predecessor (same key, so same horizon) is not a
    comparison when the horizon names no fiscal period."""
    key, note = claim.claim_key, "" if _specified(claim.horizon) else UNSPECIFIED
    uncompared = note and status in (LedgerStatus.MODIFIED, LedgerStatus.REAFFIRMED)
    return (
        f"- {claim.metric_label or claim.metric}: {_slot(key, f'{BOUNDS_STYLE},qual')} for "
        f"{claim.horizon}{note} — {status.value}{UNCOMPARED if uncompared else ''}: "
        f'"{_slot(key, QUOTE_STYLE)}" {refs([key])}'
    )


def _question(claim: NumericClaim) -> str:
    """The outstanding question of a guidance claim whose horizon names no fiscal period."""
    return QUESTION.format(label=claim.metric_label or claim.metric, ref=refs([claim.claim_key]))


def _specified(horizon: str | None) -> bool:
    """Whether ``horizon`` names a fiscal year or fiscal quarter, never an inferred one."""
    return horizon is not None and FISCAL_PERIOD.fullmatch(horizon) is not None


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
    """Every capture behind every claim passes ``check_blobs``."""
    cutoff = run.update.source_cutoff
    assert cutoff is not None
    traces = [c.citation.calculation_trace_id for c in claims if c.citation.calculation_trace_id]
    blobs = {c.citation.source_sha256 for c in claims if c.citation.source_sha256 is not None}
    blobs |= {row[0] for row in cursor.execute(_OPERAND_BLOBS, {"traces": traces}).fetchall()}
    check_blobs(
        cursor,
        blobs,
        allowed=allowed_captures(prior, run.xbrl, run.pdfs),
        cutoff=cutoff,
        retrospective=run.retrospective,
        catalog=catalog,
    )


def allowed_captures(prior: Prior, xbrl: tuple[str, ...], pdfs: tuple[str, ...]) -> set[str]:
    """The captures a run may cite: its originals, the prior's and, in a rework, those the
    carried claims rest on (admitted for the reworked version)."""
    cited = {entry.citation.source_sha256 for entry in prior.entries}
    carried = prior.rework.blobs if prior.rework is not None else frozenset()
    return {*xbrl, *pdfs, *(blob for blob in cited if blob is not None), *carried}


def check_blobs(
    cursor: Cursor[Any],
    blobs: Set[str],
    *,
    allowed: Set[str],
    cutoff: datetime,
    retrospective: Retrospective | None,
    catalog: SourceCatalog,
) -> None:
    """Every blob is an allowed capture, first seen (retrospective: published, contract a)
    by the source cutoff."""
    if outside := sorted(blob[:12] for blob in blobs - allowed):
        raise RunDraftError(f"captures not in the run's package: {', '.join(outside)}")
    late = []
    for blob in sorted(blobs):
        if retrospective is not None:
            at = retrospective.published.get(blob)
        else:
            captures = _captures(cursor, blob, catalog)
            at = captures[0]["first_seen"] if captures else None
        if at is None or at > cutoff:
            late.append(f"{blob[:12]} ({at})")
    if late:
        raise RunDraftError(f"captures past the source cutoff {cutoff}: {', '.join(late)}")


def _sections(
    run: RunDraft,
    prior: Prior,
    lines: Mapping[str, list[str]],
    falsifiers: Sequence[tuple[str, str]],
) -> tuple[ReportSection, ...]:
    """The heading, then each section's lines, the derived falsifier and probe sections and the
    disclosures; every number is a claim placeholder or a structural date, id or digest."""
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
    successor = prior.full_successor
    full = (
        ""
        if successor is None
        else f"Full successor of version:{successor.head} (full rework requested; rejected "
        f"{', '.join(successor.rejected)})\n"
    )
    seen = "; ".join(f"sha256 {sha} at {at.isoformat()}" for sha, at in prior.first_seen.items())
    heading = (
        f"# {update.issuer_name} ({update.nse_symbol}) — {update.issuer_quarter_label}\n\n"
        f"{{{{e:computed}}}} Run draft of {run.period}. Source cutoff "
        f"{update.source_cutoff.isoformat()}; derivation cutoff "
        f"{update.derivation_cutoff.isoformat()}.\n{designation}\n"
        f"Prior: {'none (bootstrap period)' if prior.version_id is None else pinned}.\n"
        f"{full}Originals first seen: {seen}.\n{run.memory}\n\n"
    )
    keys = [key for key in INTROS if key not in DISCLOSED]
    bodies = [(HEADING, heading)] + [(key, section_body(key, lines[key])) for key in keys]
    bodies += falsifiers
    bodies += [
        (OPEN_QUESTIONS, section_body(OPEN_QUESTIONS, lines[OPEN_QUESTIONS])),
        (NOT_PERFORMED, section_body(NOT_PERFORMED, NOT_DONE)),
    ]
    return tuple(
        ReportSection(ordinal=ordinal, section_key=key, body=body)
        for ordinal, (key, body) in enumerate(bodies)
    )


def section_body(key: str, lines: Sequence[str]) -> str:
    """A non-heading section: its key, intro and lines (``- none`` when empty)."""
    return f"## {key}\n\n{INTROS[key]}\n" + "".join(f"{line}\n" for line in lines or [NONE]) + "\n"
