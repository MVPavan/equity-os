"""The evidence a narrated version's model and panel both read (RESEARCH-3 S3 P5, spec §4)."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from psycopg import Cursor
from pydantic import BaseModel, ConfigDict, Field, PositiveInt

from fundamentals.contracts.ledger import NumericClaim, VersionDraft
from fundamentals.contracts.retention import OriginalExpiredError
from fundamentals.evidence.repository import _RETENTION_SHARED, _TRACES_EXPIRED, _read_traces, _rows
from fundamentals.evidence.repository_calc import StoredTrace
from fundamentals.evidence.repository_rows import INTERPRETATIONS_BY_ID, interpretation_of
from fundamentals.ledger import store
from fundamentals.ledger.display import narrative, parse_style, render_claim
from fundamentals.ledger.falsifier_status import NARRATIVE, THESIS_IMPACT, no_thesis_section
from fundamentals.ledger.lifecycle import DecisionRefusedError

ARGV_ITEM_CAP = 131_071  # Linux's limit on one argv item, less its NUL; the prompt is one
_BOUND = re.compile(r"approved thesis version:(\d+) \(sealed digest ([0-9a-f]{64})\)")
_REF, _UNIT = parse_style("ref"), parse_style("unit")


class BundleLimits(BaseModel):
    """The bundle's and the model call's size limits."""

    model_config = ConfigDict(frozen=True)

    max_span_chars: PositiveInt
    max_total_bytes: PositiveInt
    max_prompt_bytes: int = Field(gt=0, le=ARGV_ITEM_CAP)
    max_response_bytes: PositiveInt


class Bundle(BaseModel):
    """The bundle's text, its citable (capture id, anchor) pairs and the claims it left out."""

    model_config = ConfigDict(frozen=True)

    text: str
    citable: frozenset[tuple[str, str]]
    excluded: frozenset[str]

    @property
    def sha256(self) -> str:
        """The digest narrate seals in the author and the panel gate rechecks."""
        return hashlib.sha256(self.text.encode()).hexdigest()


def build_bundle(cursor: Cursor[Any], draft: VersionDraft, limits: BundleLimits) -> Bundle:
    """The version's evidence, deterministic from its claims and thesis binding, or a refusal."""
    quoted = {c.claim_key: c.citation for c in draft.claims if c.citation.quote is not None}
    excluded = {k for k, c in quoted.items() if len(c.quote or "") > limits.max_span_chars}
    spans = {
        (str(c.capture_ref_id), c.anchor or ""): c.quote or ""
        for key, c in quoted.items()
        if key not in excluded
    }
    lines = ["EVIDENCE BUNDLE", "Claims:"]
    lines += [_claim_line(claim, claim.claim_key in excluded) for claim in draft.claims]
    lines += ["Trace operands:", *_trace_lines(cursor, draft.claims)]
    lines.append("Citable spans, each marker then its full text:")
    lines += [f"{{{{s:{capture}|{anchor}}}}}\n{q}" for (capture, anchor), q in spans.items()]
    thesis = _thesis(cursor, draft)
    if repeated := sorted(key for key in excluded if (quoted[key].quote or "") in thesis):
        raise DecisionRefusedError(f"the bound thesis repeats a withheld quote: {repeated}")
    text = "\n".join((*lines, "Bound thesis:", thesis)) + "\n"
    if len(text.encode()) > limits.max_total_bytes:
        raise DecisionRefusedError(f"the bundle is over max_total_bytes: {len(text.encode())}")
    return Bundle(text=text, citable=frozenset(spans), excluded=frozenset(excluded))


def panel_text(cursor: Cursor[Any], draft: VersionDraft, limits: BundleLimits | None) -> str:
    """What the panel reads: the narrative, and a narrated version's bundle sealed in its author."""
    text = narrative(draft.sections, draft.claims).decode()
    if NARRATIVE.isdisjoint(s.section_key for s in draft.sections):
        return text
    if limits is None:
        raise DecisionRefusedError("a narrated version's panel text needs the bundle limits")
    bundle = build_bundle(cursor, draft, limits)
    if not draft.author.endswith(f":bundle:{bundle.sha256}"):
        raise DecisionRefusedError(f"the rebuilt bundle {bundle.sha256} is not the author's")
    return f"{text}\n{bundle.text}"


def _claim_line(claim: NumericClaim, excluded: bool) -> str:
    """A claim's key, citation and rendered value; a quote's text is held only in its span."""
    bounded = claim.lower_bound is not None and claim.upper_bound is not None
    shown = render_claim(claim, _UNIT) if claim.value is not None or bounded else "no value"
    withheld = " (withheld: over the span limit, not citable)" if excluded else ""
    return f"- {render_claim(claim, _REF)} value {shown}{withheld}"


def _flattened(traces: Iterable[StoredTrace]) -> dict[int, StoredTrace]:
    """The traces and every trace they reach, by id."""
    found: dict[int, StoredTrace] = {}
    for stored in traces:
        found |= {stored.trace_id: stored, **_flattened(stored.children)}
    return found


def _trace_lines(cursor: Cursor[Any], claims: tuple[NumericClaim, ...]) -> list[str]:
    """Every operand the cited traces reach, with the claims citing it; R13's guard runs first."""
    citing: defaultdict[str, list[str]] = defaultdict(list)
    for claim in claims:
        citing[f"interpretation {claim.citation.interpretation_id}"].append(claim.claim_key)
        citing[f"trace {claim.citation.calculation_trace_id}"].append(claim.claim_key)
    cited = sorted(
        c.citation.calculation_trace_id for c in claims if c.citation.calculation_trace_id
    )
    if not cited:
        return []
    conn = cursor.connection
    conn.execute(_RETENTION_SHARED)
    if expired := _rows(conn, _TRACES_EXPIRED, (cited,))[0]["expired"]:
        raise OriginalExpiredError(f"ORIGINAL_EXPIRED: traces {cited} rest on {expired}")
    traces = _flattened(_read_traces(conn, cited))
    operands = [(i, o) for i, stored in sorted(traces.items()) for o in stored.trace.operands]
    ids = sorted({o.interpretation_id for _, o in operands if o.interpretation_id is not None})
    read = map(interpretation_of, _rows(conn, INTERPRETATIONS_BY_ID, (ids,)))
    keys = {i.interpretation_id: i.key for i in read}
    lines = []
    for trace_id, operand in operands:
        record = (
            f"trace {operand.operand_trace_id}"
            if operand.operand_trace_id is not None
            else f"interpretation {operand.interpretation_id}"
        )
        value = operand.value if operand.value is not None else f"{operand.lower}..{operand.upper}"
        text = f"- in trace {trace_id}: {operand.name} {operand.temporal_role.value} {record}"
        text += f", {operand.source_state.value}, value {value}"
        if key := keys.get(operand.interpretation_id):
            kind = f"{key.value_kind.value}, {key.currency}, {key.basis.value}"
            text += f", {kind}, {key.period.canonical()}"
        named = citing[record] if operand.interpretation_id or operand.operand_trace_id else []
        lines.append(f"{text}; claims {', '.join(named)}" if named else text)
    return lines


def _thesis(cursor: Cursor[Any], draft: VersionDraft) -> str:
    """The rendered thesis ``thesis_impact`` binds, or a fixed line for the no-thesis section."""
    body = next((s.body for s in draft.sections if s.section_key == THESIS_IMPACT), "")
    if body == no_thesis_section(THESIS_IMPACT):
        return "No approved thesis is bound to this version."
    bound = _BOUND.search(body)
    if bound is None or store.sealed_digest(cursor, int(bound[1])) != bound[2]:
        raise DecisionRefusedError(f"{THESIS_IMPACT} binds no thesis whose digest holds")
    thesis = store.read_version(cursor, int(bound[1]))
    return narrative(thesis.sections, thesis.claims).decode()
