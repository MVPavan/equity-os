"""Promoted memory as Markdown (ledger spec §2 export, §3; plan D5, D3).

Engine-neutral: it formats what any ``MemoryStore.retrieve`` returns, so export needs no store
method and no database code.
"""

from __future__ import annotations

from collections.abc import Sequence

from fundamentals.contracts.memory import RetrievedItem, SupportRef

_TITLE = "# Promoted memory"
_NONE = "none"
_OPEN = "open"
_YES, _NO = "yes", "no"
_ITEM = """## Memory item {id}: {kind}

{statement}

- epistemic class: {epistemic_class}
- valid: {valid_from} to {valid_to}
- recorded: {recorded_at}
- needs revalidation: {flag}
- supports:
{supports}"""
_SUPPORT = "  - {}"
_TARGET = "{target} {target_id}"


def format_memory(items: Sequence[RetrievedItem]) -> str:
    """One Markdown section per item in id order: kind, statement verbatim, epistemic class,
    valid range, recorded time, revalidation flag and supports."""
    sections = [
        _ITEM.format(
            id=item.id,
            kind=item.kind,
            statement=item.statement,
            epistemic_class=item.epistemic_class,
            valid_from=item.valid_from,
            valid_to=item.valid_to or _OPEN,
            recorded_at=item.recorded_at,
            flag=_YES if item.needs_revalidation else _NO,
            supports="\n".join(_SUPPORT.format(_support(ref)) for ref in item.supports),
        )
        for item in sorted(items, key=lambda item: item.id)
    ]
    return "\n\n".join([_TITLE, *(sections or [_NONE])]) + "\n"


def _support(ref: SupportRef) -> str:
    """A support as ``period kind claim_key`` (a version: ``period kind``), else its target
    kind and id."""
    if ref.version_id is None:
        return _TARGET.format(target=ref.target, target_id=ref.target_id)
    return " ".join(part for part in (ref.period, ref.report_kind, ref.claim_key) if part)
