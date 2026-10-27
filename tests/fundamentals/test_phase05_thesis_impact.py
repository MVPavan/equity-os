"""Slice phase05-sD: the approved-thesis twin parser and its predicate validation.

The metric registry, the free-standing evaluator and its CLI were retired (plan RESEARCH-1 D3):
an approved thesis is evaluated only inside a run draft (``ledger.falsifier_status``). All data
is synthetic: symbol ``SYNTH`` and a made-up thesis twin.
"""

from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal

import pytest

from fundamentals.verify.thesis_predicates import PredicateOp, parse_thesis

_SYMBOL = "SYNTH"


_MARGIN_HOLDS_BLOCK = """  - falsifier_id: f_margin_collapse
    statement: "PBT margin prints below 12% in any FY28 quarter"
    predicate:
      metric_id: pbt_margin_pct
      op: LT
      threshold: "12"
"""
_TAX_BAND_BLOCK = """  - falsifier_id: f_tax_band
    statement: "Effective tax rate leaves the 20-30% band"
    predicate:
      metric_id: effective_tax_rate_pct
      op: OUTSIDE_BAND
      band: ["20", "30"]
"""
_UNKNOWN_OP_BLOCK = """  - falsifier_id: f_unknown_op
    statement: "PBT margin sits between two numbers"
    predicate:
      metric_id: pbt_margin_pct
      op: BETWEEN
      threshold: "12"
"""
_DUPLICATE_ID_BLOCK = (
    _MARGIN_HOLDS_BLOCK
    + """  - falsifier_id: f_margin_collapse
    statement: "PAT margin prints below 5% in any FY28 quarter"
    predicate:
      metric_id: pat_margin_pct
      op: LT
      threshold: "5"
"""
)


def _thesis(falsifier_blocks: str) -> bytes:
    """A made-up approved-thesis YAML twin."""
    return (
        "symbol: " + _SYMBOL + "\n"
        'version: "2027.1"\n'
        "approved_by: synthetic-analyst\n"
        "approved_at: 2027-07-25\n"
        "stance: constructive on synthetic order book\n"
        "assumptions:\n"
        '  - "synthetic assumption: PBT margin stays above 12%"\n'
        "falsifiers:\n" + falsifier_blocks + "open_questions:\n"
        '  - "synthetic open question: does the order book convert?"\n'
    ).encode()


def test_thesis_parser_rejects_unknown_op_and_duplicate_ids() -> None:
    """WHY: an unregistered op or an ambiguous falsifier id must never reach the evaluator."""
    good = _thesis(_MARGIN_HOLDS_BLOCK + _TAX_BAND_BLOCK)
    thesis = parse_thesis(good)

    assert thesis.symbol == _SYMBOL
    assert thesis.version == "2027.1"
    assert thesis.approved_at == date(2027, 7, 25)
    assert [falsifier.falsifier_id for falsifier in thesis.falsifiers] == [
        "f_margin_collapse",
        "f_tax_band",
    ]
    assert thesis.falsifiers[0].predicate.op is PredicateOp.LT
    assert thesis.falsifiers[0].predicate.threshold == Decimal("12")
    assert thesis.falsifiers[1].predicate.band == (Decimal("20"), Decimal("30"))
    assert thesis.content_sha256 == hashlib.sha256(good).hexdigest()

    for blocks in (_UNKNOWN_OP_BLOCK, _DUPLICATE_ID_BLOCK):
        with pytest.raises(ValueError):
            parse_thesis(_thesis(blocks))
