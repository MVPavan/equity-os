"""A rejected version's evidence package and rerun set, derived from its verified rows (PREP-5).

A claim's package is its input atoms: ``(blob, key digest)`` for a ``FIGURE`` (the fact row's
file or the interpretation's capture blob) and for each operand of a ``CALCULATION`` (the
operand interpretation's capture blob), ``(blob, anchor)`` for a ``SOURCE_QUOTE``. Affected
claims are the rejected ones and every claim sharing an atom with them (one hop); the rerun set
is every claim on a line holding an affected claim, since a line is re-rendered whole. Anything
else is carried. Traces are read through the repository, so each hash is re-checked.

A rework run passes every line it would write through a ``Gate`` before its first write. A
line's keys are its text's placeholders, which must be its claims' and new to the run: a line
of carried keys must equal the version's and takes its claims; a line of rerun keys only is
rerun; any other refuses, as does a carried line missing or out of the version's order, or a
changed section scaffold.

The derived falsifier sections and their threshold claims are re-derived on every write, so a
rework neither carries nor reruns them; a rejection naming one, or of a version written before
them, refuses (plan RESEARCH-1 D7): a threshold's route is superseding the thesis, a probe figure
or calculation's is diagnosis, then ``--full-successor``, and a credibility claim's is diagnosis, a
mapping correction if the mapping is wrong, then ``--full-successor``. The disclosed open-questions
and not-performed sections are likewise regenerated from the run's guidance on every write, outside
the rework contract. A narrative section owns no claim and is dropped: a reworked successor is
narrated again once approved (RESEARCH-3 S3).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from typing import Any, LiteralString

from psycopg import Cursor
from pydantic import BaseModel, ConfigDict

from equity_os.analysis.calculations.run_traces import DISCLOSED, RunDraftError
from equity_os.analysis.lenses.thesis_tests.falsifier_status import (
    CREDIBILITY,
    DERIVED,
    NARRATIVE,
    RISK_PROBE,
    THESIS_IMPACT,
)
from equity_os.contracts.publication.ledger import (
    CitationKind,
    DecisionKind,
    NumericClaim,
    SubjectKind,
)
from equity_os.contracts.verification.vendor_first import AdmissionLabel
from equity_os.publication.drafting.display import FILED, PLACEHOLDER, DisplayError, render_section
from equity_os.storage.records import store
from equity_os.storage.records.repository import EvidenceRepository
from equity_os.storage.records.repository_calc import StoredTrace

Atom = tuple[str, str]
FactOrigin = tuple[str, int]
# A run binds these, so a carried claim takes the version's (a quote's text and anchor included).
_BINDING = {"citation", "unresolved"}
_BOUND = {FILED, *AdmissionLabel}  # qualifiers binding gives a claim, not the run
_FACT_FILES: LiteralString = """SELECT origin, origin_id, file_sha256 FROM eqos.fact_rows
WHERE (origin, origin_id) IN (SELECT * FROM unnest(%s::text[], %s::bigint[]))"""


class Rework(BaseModel):
    """Version ``head``'s claims by key with their input atoms, its claim lines per section (text
    and keys), the rerun and carried keys, the blobs the carried claims rest on, and each
    section's scaffold."""

    model_config = ConfigDict(frozen=True)

    head: int
    claims: Mapping[str, NumericClaim]
    atoms: Mapping[str, frozenset[Atom]]
    lines: Mapping[str, tuple[tuple[str, frozenset[str]], ...]]
    rerun: frozenset[str]
    carried: frozenset[str]
    blobs: frozenset[str]
    scaffolds: Mapping[str, str]

    def gate(
        self, body: Callable[[str, Sequence[str]], str], admit: Callable[[frozenset[str]], None]
    ) -> Gate:
        """A gate over a rework run's lines; ``body`` renders a section from its lines and
        ``admit`` checks the run's sources."""
        return Gate(self, body, admit)


class Gate:
    """A rework run's lines, recorded in order and held to the reworked version's."""

    def __init__(
        self,
        rework: Rework,
        body: Callable[[str, Sequence[str]], str],
        admit: Callable[[frozenset[str]], None],
    ) -> None:
        self.rework, self.body, self.admit = rework, body, admit
        self.recorded: dict[str, list[str]] = defaultdict(list)
        self.carried: dict[str, list[tuple[str, frozenset[str]]]] = defaultdict(list)
        self.seen: frozenset[str] = frozenset()
        self.sources: set[str] = set()

    def line(
        self, section: str, text: str, claims: tuple[NumericClaim, ...]
    ) -> tuple[NumericClaim, ...] | None:
        """The version's claims for a carried line, ``None`` for a rerun line, ``()`` for a
        line without claims; refuses any other, and a line whose placeholders are not exactly
        its claims, repeat a key the run already showed or do not render."""
        self.recorded[section].append(text)
        keys, seen, rework = _keys(text), self.seen, self.rework
        self.seen = seen | keys
        if sorted(claim.claim_key for claim in claims) == sorted(keys) and not keys & seen:
            if not keys:
                return ()
            if not keys & rework.carried and keys & rework.rerun:
                try:
                    render_section(text, claims)
                except DisplayError as error:
                    raise RunDraftError(f"rework of version {rework.head}: {error}") from error
                sources = (c.citation.source_sha256 for c in claims)
                self.sources |= {sha256 for sha256 in sources if sha256}
                return None
            if keys <= rework.carried and (text, keys) in rework.lines[section]:
                held = tuple(rework.claims[claim.claim_key] for claim in claims)
                if all(_same(claim, own) for claim, own in zip(claims, held, strict=True)):
                    self.carried[section].append((text, keys))
                    return held
        raise RunDraftError(f"rework of version {rework.head}: {section} line {sorted(keys)} moved")

    def close(self, blobs: frozenset[str]) -> None:
        """Refuse unless every carried line came back in the version's order and every
        section's scaffold is the version's, then admit the run's sources and the carried
        claims' inputs."""
        rework = self.rework
        for section, held in rework.lines.items():
            if [line for line in held if line[1] <= rework.carried] != self.carried[section]:
                raise RunDraftError(f"rework drops or reorders carried {section} lines")
        for section, expected in rework.scaffolds.items():
            if scaffold(self.body(section, self.recorded[section])) != expected:
                raise RunDraftError(f"rework changes the {section} section outside its claims")
        self.admit(blobs | self.sources | rework.blobs)


def _same(claim: NumericClaim, own: NumericClaim) -> bool:
    """Whether a run's unbound claim states what the version's resolved claim does; outside
    guidance the ``FILED`` label is binding (a QoQ prior loses it to its predecessor fact), as
    is an admission label (a carried fact is not admitted again)."""
    stated, held = claim.model_dump(exclude=_BINDING), own.model_dump(exclude=_BINDING)
    if own.citation.kind is not CitationKind.SOURCE_QUOTE:
        for dumped in (stated, held):
            dumped["qualifiers"] = tuple(q for q in dumped["qualifiers"] if q not in _BOUND)
    return not own.unresolved and stated == held


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


def _keys(line: str) -> frozenset[str]:
    """The claim keys a line's placeholders show."""
    return frozenset(match[0] for match in PLACEHOLDER.findall(line))


def scaffold(body: str) -> str:
    """A section body without its claim lines."""
    return "".join(line for line in body.splitlines(True) if not PLACEHOLDER.search(line))


def plan(cursor: Cursor[Any], repository: EvidenceRepository, head: int) -> Rework | None:
    """Version ``head``'s rework when its latest decision rejects claims, else ``None``."""
    keys = rejected(cursor, head)
    if not keys:
        return None
    version = store.read_version(cursor, head)
    if all(section.section_key != THESIS_IMPACT for section in version.sections):
        raise RunDraftError(
            f"version {head} predates the falsifier sections; rerun with --full-successor"
        )
    claims = {c.claim_key: c for c in version.claims if c.section_key not in DERIVED}
    probed = {c.claim_key for c in version.claims if c.section_key == RISK_PROBE}
    if filed := sorted(probed.intersection(keys)):
        raise RunDraftError(
            f"{', '.join(filed)} is computed from the filed statement; diagnose it, then rerun "
            "with --full-successor"
        )
    mapped = {c.claim_key for c in version.claims if c.section_key == CREDIBILITY}
    if held := sorted(mapped.intersection(keys)):
        raise RunDraftError(
            f"{', '.join(held)} comes from the guidance mapping file; diagnose it, append a "
            "supersedes entry if the mapping is wrong, then rerun with --full-successor"
        )
    if derived := sorted(set(keys) - set(claims)):
        raise RunDraftError(
            f"{', '.join(derived)} is re-derived from the approved thesis; supersede the thesis "
            "instead"
        )
    sections = [s for s in version.sections if s.section_key not in DERIVED | DISCLOSED | NARRATIVE]
    cited = [claim.citation for claim in claims.values()]
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
            (line, _keys(line)) for line in section.body.splitlines() if PLACEHOLDER.search(line)
        )
        for section in sections
        if section.ordinal  # the heading (ordinal 0) is run metadata
    }
    rerun = frozenset(affected).union(
        *(own for held in lines.values() for _, own in held if own & affected)
    )
    carried = frozenset(claims) - rerun
    return Rework(
        head=head,
        claims=claims,
        atoms=atoms,
        lines=lines,
        rerun=rerun,
        carried=carried,
        blobs=frozenset(blob for key in carried for blob, _ in atoms[key]),
        scaffolds={s.section_key: scaffold(s.body) for s in sections if s.ordinal},
    )
