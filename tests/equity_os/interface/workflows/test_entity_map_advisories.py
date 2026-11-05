"""A17: a duplicate alternate-key value nothing has confirmed must be reported.

EM-02 refuses two entities that claim one non-null NSE symbol or BSE scrip. That
refusal cannot apply to a value a source flagged as unconfirmed: EM-07 says such
a value never satisfies a lookup on its own, so it joins nothing and collides
with nothing, and a frozen fixture requires exactly that build to succeed.

The consequence is the blind spot this file closes. Two entities may hold one
byte-identical scrip with nothing said about it, and in a hand-edited config
that is far more likely a copy-paste than two securities sharing a code. The
build still succeeds — refusing would fail a run over a value the map never
trusted — but the map publishes the duplicate as an advisory of its own. It is
NOT recorded in ``conflicts``: that field means EM-06, two sources disagreeing,
and nothing disagrees here.

Every fixture is synthetic and comes from :mod:`entity_map_fixtures`.
"""

from __future__ import annotations

from typing import Any

import entity_map_fixtures as fx
import pytest

_NAMESPACE_FIELDS = {fx.NSE_NS: "nse", fx.BSE_NS: "bse"}


def _pair(namespace: str, first: str, second: str) -> tuple[Any, ...]:
    """Two securities whose only possible clash is one unconfirmed alternate key.

    Both carry a distinct valid ISIN and a distinct value in the *other*
    alternate-key namespace, so neither the EM-01 rule, the EM-02 refusal nor
    the EM-04 tripwire can fire on them, and the namespace under test is flagged
    unconfirmed on both sides so no join can pull them together either.
    """
    field = _NAMESPACE_FIELDS[namespace]
    other = "bse" if field == "nse" else "nse"
    return (
        fx.record(
            source_id=fx.S2_SOURCE_ID,
            isin_code=fx.ALPHA_ISIN,
            unverified=(namespace,),
            **{field: first, other: fx.ALPHA_NSE if other == "nse" else fx.ALPHA_BSE},
        ),
        fx.record(
            source_id=fx.S2_SOURCE_ID,
            isin_code=fx.BRAVO_ISIN,
            unverified=(namespace,),
            **{field: second, other: fx.BRAVO_NSE if other == "nse" else fx.BRAVO_BSE},
        ),
    )


@pytest.mark.parametrize(
    ("namespace", "shared"),
    [(fx.NSE_NS, fx.SHARED_NSE), (fx.BSE_NS, fx.SHARED_BSE)],
)
def test_two_entities_holding_one_unconfirmed_alternate_key_are_reported(
    namespace: str, shared: str
) -> None:
    """A17: the duplicate is published, naming the namespace, the value and both keys.

    Asserting only "an advisory exists" would pass an implementation that
    reported a bare count, which tells a human nothing about which file to open.
    Both entity keys are asserted so the reader can find both pins. Both
    alternate-key namespaces are exercised because an implementation guarding
    only one of them passes the other case unchanged.
    """
    built = fx.build(*_pair(namespace, shared, shared))

    assert sorted(fx.by_key(built)) == sorted([fx.ALPHA_ISIN, fx.BRAVO_ISIN])
    advisories = built.duplicate_alternate_keys
    assert len(advisories) == 1
    assert advisories[0].namespace is fx.namespace(namespace)
    assert advisories[0].value == shared
    assert sorted(advisories[0].entity_keys) == sorted([fx.ALPHA_ISIN, fx.BRAVO_ISIN])


@pytest.mark.parametrize(
    ("namespace", "first", "second"),
    [
        (fx.NSE_NS, fx.CHARLIE_NSE, fx.DELTA_NSE),
        (fx.BSE_NS, fx.CHARLIE_BSE, fx.DELTA_BSE),
    ],
)
def test_two_entities_holding_different_unconfirmed_values_raise_no_advisory(
    namespace: str, first: str, second: str
) -> None:
    """A17: the control — an unconfirmed value is not itself a defect.

    Nine of the ten pinned stocks carry values no second source has confirmed,
    so an implementation that flagged every unconfirmed value would emit an
    advisory per pin and be ignored within a week. The two entities are asserted
    present, so an implementation that built nothing at all cannot pass by
    reporting nothing.
    """
    built = fx.build(*_pair(namespace, first, second))

    assert sorted(fx.by_key(built)) == sorted([fx.ALPHA_ISIN, fx.BRAVO_ISIN])
    assert built.duplicate_alternate_keys == ()


def test_a_duplicate_alternate_key_is_not_recorded_as_an_em_06_conflict() -> None:
    """A17: the advisory is additive, and ``conflicts`` keeps its EM-06 meaning.

    Folding this into ``conflicts`` would be the tempting shortcut and would
    corrupt two things at once: the duplicate is not a disagreement — no source
    contradicts another — and a key named in ``conflicts`` is excluded from
    lookup and from the analysis universe. Both entities here are legitimately
    usable on their confirmed identifiers, so both lookups are asserted to still
    resolve.
    """
    built = fx.build(*_pair(fx.BSE_NS, fx.SHARED_BSE, fx.SHARED_BSE))

    assert built.duplicate_alternate_keys
    assert built.conflicts == ()
    assert all(entity.conflicted is False for entity in built.entities)
    assert built.lookup(fx.namespace(fx.ISIN_NS), fx.ALPHA_ISIN) is not None
    assert built.lookup(fx.namespace(fx.ISIN_NS), fx.BRAVO_ISIN) is not None
    assert [entity.key for entity in built.analysis_universe()] == [
        fx.ALPHA_ISIN,
        fx.BRAVO_ISIN,
    ]
