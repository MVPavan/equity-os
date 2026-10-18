"""A rejected version's evidence package and rerun set, derived from its verified rows (PREP-5).

A claim's package is its input atoms: ``(blob, key digest)`` for a ``FIGURE`` (the fact row's
file or the interpretation's capture blob) and for each operand of a ``CALCULATION`` (the
operand interpretation's capture blob), ``(blob, anchor)`` for a ``SOURCE_QUOTE``. Affected
claims are the rejected ones and every claim sharing an atom with them (one hop); the rerun set
is every claim on a line holding an affected claim, since a line is re-rendered whole. Anything
else is carried. Traces are read through the repository, so each hash is re-checked.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, LiteralString

from psycopg import Cursor
from pydantic import BaseModel, ConfigDict

from fundamentals.contracts.ledger import CitationKind, DecisionKind, NumericClaim, SubjectKind
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.evidence.repository_calc import StoredTrace
from fundamentals.ledger import store
from fundamentals.ledger.display import PLACEHOLDER
from fundamentals.ledger.run_traces import RunDraftError

Atom = tuple[str, str]
FactOrigin = tuple[str, int]
_FACT_FILES: LiteralString = """SELECT origin, origin_id, file_sha256 FROM eqos.fact_rows
WHERE (origin, origin_id) IN (SELECT * FROM unnest(%s::text[], %s::bigint[]))"""


class Rework(BaseModel):
    """Version ``head``'s claims by key, its claim lines per section (text and keys), the rerun
    and carried keys, the blobs the carried claims rest on, and each section's scaffold."""

    model_config = ConfigDict(frozen=True)

    head: int
    claims: Mapping[str, NumericClaim]
    lines: Mapping[str, tuple[tuple[str, frozenset[str]], ...]]
    rerun: frozenset[str]
    carried: frozenset[str]
    blobs: frozenset[str]
    scaffolds: Mapping[str, str]


def rejected(cursor: Cursor[Any], head: int) -> tuple[str, ...]:
    """The claims the version's latest decision rejects, sorted; empty unless it is a
    ``REQUEST_CHANGES`` naming claims."""
    decision = store.chain_head(cursor, SubjectKind.REPORT_VERSION, head)
    if decision is None or decision.kind is not DecisionKind.REQUEST_CHANGES:
        return ()
    return tuple(sorted(decision.rejected_claims or ()))


def inputs(
    claims: Mapping[str, NumericClaim],
    traces: Mapping[int, StoredTrace],
    blobs: Mapping[int, str],
    facts: Mapping[FactOrigin, str],
) -> dict[str, frozenset[Atom]]:
    """Each claim's input atoms; ``blobs`` maps an interpretation to its capture blob, ``facts``
    a fact row to its file. Refuses an unresolved claim, a citation kind a run draft does not
    emit and an operand that is not one interpretation."""
    found: dict[str, frozenset[Atom]] = {}
    for key, claim in claims.items():
        atoms = None if claim.unresolved else _atoms(claim, traces, blobs, facts)
        if atoms is None:
            raise RunDraftError(f"claim {key} ({claim.citation.kind}) has no reworkable inputs")
        found[key] = atoms
    return found


def _atoms(
    claim: NumericClaim,
    traces: Mapping[int, StoredTrace],
    blobs: Mapping[int, str],
    facts: Mapping[FactOrigin, str],
) -> frozenset[Atom] | None:
    """A resolved claim's atoms; ``None`` when its record or an input is missing or of a shape
    a run draft does not emit."""
    citation, key = claim.citation, claim.measurement_key
    if citation.kind is CitationKind.SOURCE_QUOTE:
        if citation.source_sha256 is None or citation.anchor is None:
            return None
        return frozenset({(citation.source_sha256, citation.anchor)})
    if citation.kind is CitationKind.FIGURE and key is not None:
        if citation.fact_origin is not None and citation.fact_origin_id is not None:
            blob = facts.get((citation.fact_origin, citation.fact_origin_id))
        else:
            blob = _blob(blobs, citation.interpretation_id)
        return None if blob is None else frozenset({(blob, key.digest())})
    if citation.kind is not CitationKind.CALCULATION or citation.calculation_trace_id is None:
        return None
    trace = traces.get(citation.calculation_trace_id)
    if trace is None:
        return None
    atoms = set()
    for operand in trace.trace.operands:
        blob = _blob(blobs, operand.interpretation_id)
        if blob is None:
            return None
        atoms.add((blob, operand.key_digest))
    return frozenset(atoms)


def _blob(blobs: Mapping[int, str], interpretation_id: int | None) -> str | None:
    """The interpretation's capture blob, if it is one known interpretation."""
    return None if interpretation_id is None else blobs.get(interpretation_id)


def scaffold(body: str) -> str:
    """A section body without its claim lines."""
    return "".join(line for line in body.splitlines(True) if not PLACEHOLDER.search(line))


def plan(cursor: Cursor[Any], repository: EvidenceRepository, head: int) -> Rework | None:
    """Version ``head``'s rework when its latest decision rejects claims, else ``None``."""
    keys = rejected(cursor, head)
    if not keys:
        return None
    version = store.read_version(cursor, head)
    claims = {claim.claim_key: claim for claim in version.claims}
    cited = [claim.citation for claim in version.claims]
    trace_ids = [c.calculation_trace_id for c in cited if c.calculation_trace_id is not None]
    traces = {t.trace_id: t for t in repository.get_calculation_traces(trace_ids)}
    operands = (o for t in traces.values() for o in t.trace.operands)
    cited_ids = (*(o.interpretation_id for o in operands), *(c.interpretation_id for c in cited))
    interpretation_ids = sorted({i for i in cited_ids if i is not None})
    interpretations = repository.get_interpretations(interpretation_ids)
    captures = repository.get_capture_refs(sorted({i.capture_ref_id for i in interpretations}))
    capture_blobs = {capture.capture_ref_id: capture.blob_sha256 for capture in captures}
    blobs = {
        i.interpretation_id: capture_blobs[i.capture_ref_id]
        for i in interpretations
        if i.interpretation_id is not None
    }
    origins = [(c.fact_origin, c.fact_origin_id) for c in cited if c.fact_origin_id is not None]
    rows = cursor.execute(_FACT_FILES, ([o for o, _ in origins], [i for _, i in origins]))
    facts = {(origin, origin_id): sha256 for origin, origin_id, sha256 in rows.fetchall()}
    atoms = inputs(claims, traces, blobs, facts)
    hit = frozenset().union(*(atoms[key] for key in keys))
    affected = {key for key, own in atoms.items() if key in keys or own & hit}
    lines = {
        section.section_key: tuple(
            (line, frozenset(match[0] for match in PLACEHOLDER.findall(line)))
            for line in section.body.splitlines()
            if PLACEHOLDER.search(line)
        )
        for section in version.sections
        if section.ordinal  # the heading (ordinal 0) is run metadata
    }
    rerun = frozenset(affected).union(
        *(own for held in lines.values() for _, own in held if own & affected)
    )
    carried = frozenset(claims) - rerun
    return Rework(
        head=head,
        claims=claims,
        lines=lines,
        rerun=rerun,
        carried=carried,
        blobs=frozenset(blob for key in carried for blob, _ in atoms[key]),
        scaffolds={s.section_key: scaffold(s.body) for s in version.sections if s.ordinal},
    )
