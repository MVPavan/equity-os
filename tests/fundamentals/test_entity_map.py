"""The entity identity map's frozen contract, rule by rule (EM-01 .. EM-12).

Each test pins exactly one rule of ``scratchpad/phase3/entity-map-contract.md``
and is built so that deleting that one rule from the implementation — and
nothing else — turns it red. Two habits do that work and are used throughout:

*   **The accepting shape is asserted first.** A refusal test that only asserts
    "this raised" stays green under an implementation that refuses everything,
    so every refusal test first proves the near-identical accepting fixture
    builds.
*   **A control entity sits beside the excluded one.** A test that only asserts
    ``lookup(...) is None`` or ``entity not in universe`` stays green under an
    implementation that returns nothing at all, so every exclusion test also
    proves a neighbouring entity *is* returned.

Where a fixture would otherwise trip two rules at once it has been split so the
rule under test is the only one that can fire. Nothing here opens a socket,
reads a captured page, or names a real listed company; the synthetic corpus
lives in :mod:`entity_map_fixtures`.
"""

from __future__ import annotations

import json
import re
from typing import Any

import entity_map_fixtures as fx
import pytest
from pydantic import ValidationError

_TEMPORAL_FIELDS = frozenset(
    {
        "as_of",
        "as_of_date",
        "valid_from",
        "valid_to",
        "effective_from",
        "effective_to",
        "superseded_at",
        "superseded_by",
        "version",
        "revision",
        "history",
        "previous",
        "previous_values",
    }
)


def _strings(node: Any) -> list[str]:
    """Every string leaf of a parsed JSON document, in document order."""
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [leaf for value in node.values() for leaf in _strings(value)]
    if isinstance(node, list):
        return [leaf for value in node for leaf in _strings(value)]
    return []


# ---------------------------------------------------------------------------
# EM-01 — ISIN is the primary key
# ---------------------------------------------------------------------------


def test_an_isin_of_the_wrong_shape_is_refused_even_with_a_valid_check_digit() -> None:
    """EM-01: the shape half of the rule is load-bearing on its own.

    ``WRONG_SHAPE_ISIN`` fails ``^IN[EF9]...`` (its third character is ``A``)
    but carries a correctly computed ISO 6166 check digit, so the Luhn half
    accepts it. Delete the shape check and only this test notices: the value
    would be stored as a live primary key. The accepting fixture is built first
    so an implementation that refuses every ISIN cannot pass, and both records
    carry an NSE symbol so A4's unkeyable-record refusal cannot pre-empt the
    ISIN rule whichever order the implementation checks them in.
    """
    assert fx.isin_check_digit(fx.WRONG_SHAPE_BODY) == fx.WRONG_SHAPE_ISIN[-1]
    assert re.fullmatch(fx.ISIN_SHAPE, fx.WRONG_SHAPE_ISIN) is None
    assert fx.build(fx.record(isin_code=fx.ALPHA_ISIN, nse=fx.ALPHA_NSE)).entities

    with pytest.raises(fx.contracts.IsinFormatError):
        fx.build(fx.record(isin_code=fx.WRONG_SHAPE_ISIN, nse=fx.ALPHA_NSE))


def test_an_isin_with_a_wrong_check_digit_is_refused_despite_a_valid_shape() -> None:
    """EM-01: the ISO 6166 check digit half of the rule is load-bearing on its own.

    ``WRONG_DIGIT_ISIN`` matches the shape exactly and differs from a valid ISIN
    by one character in the check position — the single-digit mutation EM-01
    says must fail. An implementation that validates only the regex stores it,
    and only this test goes red. Both records carry an NSE symbol so A4 cannot
    refuse them first for having no key at all.
    """
    assert re.fullmatch(fx.ISIN_SHAPE, fx.WRONG_DIGIT_ISIN) is not None
    assert fx.WRONG_DIGIT_ISIN[:-1] == fx.isin(fx.WRONG_DIGIT_BODY)[:-1]
    assert fx.build(fx.record(isin_code=fx.isin(fx.WRONG_DIGIT_BODY), nse=fx.ALPHA_NSE)).entities

    with pytest.raises(fx.contracts.IsinFormatError):
        fx.build(fx.record(isin_code=fx.WRONG_DIGIT_ISIN, nse=fx.ALPHA_NSE))


def test_one_entity_is_published_per_isin_and_it_is_keyed_by_that_isin() -> None:
    """EM-01: the ISIN is the primary key, not merely a stored attribute.

    Two records naming the same ISIN and different everything else must publish
    one entity whose key *is* the ISIN. An implementation keying by source row,
    by slug or by company id publishes two entities, or one under another key.
    """
    built = fx.build(
        fx.record(isin_code=fx.ALPHA_ISIN, screener_slug=fx.ALPHA_NSE),
        fx.record(source_id=fx.S2_SOURCE_ID, isin_code=fx.ALPHA_ISIN, nse=fx.ALPHA_NSE),
    )

    assert [entity.key for entity in built.entities] == [fx.ALPHA_ISIN]


# ---------------------------------------------------------------------------
# EM-01b — surrogate keys for entities with no ISIN
# ---------------------------------------------------------------------------


def test_a_record_with_no_isin_is_kept_under_an_nse_surrogate_key() -> None:
    """EM-01b: an ISIN-less record is retained, keyed ``nse:<symbol>``, ISIN_MISSING.

    S2 supplies no ISIN at all, so dropping such a record would make all ten
    pinned stocks unrepresentable. Asserting only "the build did not raise"
    would pass an implementation that discards them, so this asserts the key,
    the state, and that the ISIN namespace is reported missing rather than
    filled with the surrogate.
    """
    built = fx.build(fx.record(source_id=fx.S2_SOURCE_ID, nse=fx.ZULU_NSE, bse=fx.ORPHAN_BSE))

    entity = fx.by_key(built)[f"nse:{fx.ZULU_NSE}"]
    assert entity.state is fx.contracts.EntityState.ISIN_MISSING
    assert fx.values_of(entity, fx.ISIN_NS) == ()
    assert built.lookup(fx.namespace(fx.NSE_NS), fx.ZULU_NSE) is entity


def test_a_record_with_neither_isin_nor_nse_falls_back_to_a_bse_surrogate_key() -> None:
    """EM-01b: ``bse:<scrip>`` is used only when no NSE symbol exists.

    The fallback order is part of the rule. An implementation that always uses
    the BSE scrip, or that refuses a record with no NSE symbol, goes red here;
    the sibling test above proves NSE wins when both are present.
    """
    built = fx.build(fx.record(source_id=fx.S2_SOURCE_ID, bse=fx.ORPHAN_BSE))

    entity = fx.by_key(built)[f"bse:{fx.ORPHAN_BSE}"]
    assert entity.state is fx.contracts.EntityState.ISIN_MISSING


def test_a_surrogate_keyed_entity_merges_into_the_isin_entity_when_an_isin_arrives() -> None:
    """EM-01b: a later ISIN for the same NSE symbol collapses the two into one.

    Without the merge the map carries the same security twice — once under
    ``nse:ZULUFX`` and once under its ISIN — and every downstream join silently
    sees two companies. The surrogate key must not survive publication.
    """
    built = fx.build(
        fx.record(source_id=fx.S2_SOURCE_ID, nse=fx.ZULU_NSE),
        fx.record(isin_code=fx.CHARLIE_ISIN, nse=fx.ZULU_NSE),
    )

    assert [entity.key for entity in built.entities] == [fx.CHARLIE_ISIN]
    entity = built.entities[0]
    assert entity.state is not fx.contracts.EntityState.ISIN_MISSING
    assert fx.values_of(entity, fx.NSE_NS) == (fx.ZULU_NSE,)


def test_a_record_with_no_isin_no_nse_and_no_bse_is_refused_at_ingest() -> None:
    """A4: a record with no key of any kind cannot be identified, so it is refused.

    A Screener slug and a company id are attributes, not keys — nothing joins
    them to a security, and EM-08 forbids falling back to the display name. The
    same record with a BSE scrip added is built first, so the refusal is
    provably about the missing key and not about the rest of the shape.

    This is not the EM-03 delisting case: ICICI Securities has an ISIN, keys
    fine, and is merely ``NOT_LISTED``.
    """
    keyed = fx.record(screener_slug=fx.ALPHA_NSE, screener_company_id=9100001, bse=fx.ALPHA_BSE)
    assert fx.build(keyed).entities

    with pytest.raises(fx.contracts.UnkeyableRecordError):
        fx.build(fx.record(screener_slug=fx.ALPHA_NSE, screener_company_id=9100001))


# ---------------------------------------------------------------------------
# EM-02 — nullable unique alternate keys
# ---------------------------------------------------------------------------


def test_two_entities_sharing_one_nse_symbol_refuse_the_build() -> None:
    """EM-02: a duplicate non-null NSE symbol across two entities is a refusal.

    Both records carry a valid, distinct ISIN and no Screener company id, so
    neither EM-01 nor the EM-04 tripwire can fire — only the NSE uniqueness
    rule can refuse this pair. The same two records with distinct symbols are
    built first, so an implementation refusing any two-entity map cannot pass.
    """
    assert len(fx.build(*_two_entities(fx.ALPHA_NSE, fx.BRAVO_NSE, key=fx.NSE_NS)).entities) == 2

    with pytest.raises(fx.contracts.AlternateKeyCollisionError):
        fx.build(*_two_entities(fx.SHARED_NSE, fx.SHARED_NSE, key=fx.NSE_NS))


def test_two_entities_sharing_one_bse_scrip_refuse_the_build() -> None:
    """EM-02: the same uniqueness rule holds for the BSE namespace.

    Written separately from the NSE case because an implementation that guards
    only one namespace passes the other test unchanged.
    """
    assert len(fx.build(*_two_entities(fx.ALPHA_BSE, fx.BRAVO_BSE, key=fx.BSE_NS)).entities) == 2

    with pytest.raises(fx.contracts.AlternateKeyCollisionError):
        fx.build(*_two_entities(fx.SHARED_BSE, fx.SHARED_BSE, key=fx.BSE_NS))


def test_two_entities_that_both_lack_an_exchange_code_are_not_a_collision() -> None:
    """EM-02: null is permitted and common, so two nulls must never collide.

    Measured on the live 83, fifteen members carry no NSE symbol. An
    implementation that groups on the raw value would fold every one of them
    into a single ``None`` bucket and refuse the build; this is the test that
    catches that, and it asserts both entities survive rather than merely that
    nothing raised.
    """
    built = fx.build(fx.record(isin_code=fx.ALPHA_ISIN), fx.record(isin_code=fx.BRAVO_ISIN))

    assert sorted(fx.by_key(built)) == sorted([fx.ALPHA_ISIN, fx.BRAVO_ISIN])


def _two_entities(first: str, second: str, *, key: str) -> tuple[Any, ...]:
    """Two records with distinct valid ISINs and the given values in one namespace."""
    field = {fx.NSE_NS: "nse", fx.BSE_NS: "bse"}[key]
    return (
        fx.record(isin_code=fx.ALPHA_ISIN, **{field: first}),
        fx.record(isin_code=fx.BRAVO_ISIN, **{field: second}),
    )


# ---------------------------------------------------------------------------
# EM-03 — neither exchange code is NOT_LISTED, not an error
# ---------------------------------------------------------------------------


def test_an_entity_with_no_exchange_code_is_retained_as_not_listed_and_left_out() -> None:
    """EM-03: retained with state ``NOT_LISTED``, excluded from the default universe.

    "No exception was raised" is worthless here — an implementation that
    silently drops the record passes it. So this asserts the entity is PRESENT
    under its ISIN, asserts its state, and asserts it is absent from the
    analysis universe *while a listed neighbour is present in it*, which an
    implementation returning an empty universe cannot fake.
    """
    built = fx.build(
        fx.record(isin_code=fx.ALPHA_ISIN),
        fx.record(isin_code=fx.BRAVO_ISIN, nse=fx.BRAVO_NSE, bse=fx.BRAVO_BSE),
    )

    delisted = fx.by_key(built)[fx.ALPHA_ISIN]
    assert delisted.state is fx.contracts.EntityState.NOT_LISTED

    universe = built.analysis_universe()
    assert [entity.key for entity in universe] == [fx.BRAVO_ISIN]


# ---------------------------------------------------------------------------
# EM-04 — share-class tripwire
# ---------------------------------------------------------------------------


def test_two_isins_resolving_to_one_screener_company_id_refuse_the_build() -> None:
    """EM-04: a dual-class issuer or a parse error must stop the build, never merge.

    Both records carry distinct valid ISINs and *distinct* NSE symbols, so the
    EM-02 uniqueness rule cannot fire and this pair can only be refused by the
    share-class tripwire. The same pair with distinct company ids is built
    first, proving the refusal is about the collision and not about the shape.
    """
    assert len(fx.build(*_share_class_pair(9100001, 9100002)).entities) == 2

    with pytest.raises(fx.contracts.ShareClassCollisionError):
        fx.build(*_share_class_pair(9100001, 9100001))


def _share_class_pair(first_id: int, second_id: int) -> tuple[Any, ...]:
    """Two distinct securities whose only possible clash is the company id."""
    return (
        fx.record(isin_code=fx.ALPHA_ISIN, nse=fx.ALPHA_NSE, screener_company_id=first_id),
        fx.record(isin_code=fx.BRAVO_ISIN, nse=fx.BRAVO_NSE, screener_company_id=second_id),
    )


# ---------------------------------------------------------------------------
# EM-05 — every identifier value carries provenance
# ---------------------------------------------------------------------------


def test_an_identifier_value_cannot_be_constructed_without_a_recorded_source() -> None:
    """EM-05: an identifier with no recorded source cannot be stored, structurally.

    The accepting construction is asserted first; the refusal then proves the
    empty-provenance case is rejected by the model rather than left to whichever
    caller happens to remember. Drop the minimum-length constraint and only this
    test notices.
    """
    marks = (fx.provenance(fx.S1_SOURCE_ID),)
    assert (
        fx.contracts.IdentifierValue(
            value=fx.ALPHA_NSE, provenances=marks, verified=True
        ).provenances
        == marks
    )

    with pytest.raises(ValidationError):
        fx.contracts.IdentifierValue(value=fx.ALPHA_NSE, provenances=(), verified=True)


def test_every_value_a_built_entity_publishes_names_the_source_that_asserted_it() -> None:
    """EM-05: the build carries provenance through rather than discarding it.

    The model constraint above is satisfied by an implementation that invents a
    placeholder provenance during the merge. This asserts the source ids that
    come out are exactly the two that went in, per value.
    """
    built = fx.build(
        fx.record(isin_code=fx.ALPHA_ISIN, nse=fx.ALPHA_NSE),
        fx.record(source_id=fx.S2_SOURCE_ID, isin_code=fx.ALPHA_ISIN, bse=fx.ALPHA_BSE),
    )

    entity = fx.by_key(built)[fx.ALPHA_ISIN]
    assert fx.source_ids_of(entity, fx.NSE_NS) == (frozenset({fx.S1_SOURCE_ID}),)
    assert fx.source_ids_of(entity, fx.BSE_NS) == (frozenset({fx.S2_SOURCE_ID}),)


# ---------------------------------------------------------------------------
# EM-06 — a conflict is recorded, never resolved
# ---------------------------------------------------------------------------


def test_two_sources_disagreeing_on_one_namespace_retain_both_values_and_both_sources() -> None:
    """EM-06: both values survive, both provenances survive, the build does not fail.

    Asserting only ``conflicted is True`` would pass an implementation that
    marks the entity and then keeps whichever value it saw last — the exact
    silent corruption the rule forbids. So this asserts the pair of values and
    the pair of asserting sources, and that no winner was picked. Per A3 the
    state stays ``RESOLVED``: this entity is ISIN-keyed and listed, and conflict
    is a separate, derived fact about it.
    """
    built = fx.build(*_conflicting_pair())

    entity = fx.by_key(built)[fx.ALPHA_ISIN]
    assert entity.conflicted is True
    assert entity.state is fx.contracts.EntityState.RESOLVED
    assert sorted(fx.values_of(entity, fx.NSE_NS)) == sorted([fx.ALPHA_NSE, fx.ZULU_NSE])
    assert sorted(frozenset().union(*fx.source_ids_of(entity, fx.NSE_NS))) == sorted(
        [fx.S1_SOURCE_ID, fx.S2_SOURCE_ID]
    )
    assert fx.coverage(entity, fx.NSE_NS).status is fx.contracts.CoverageStatus.CONFLICTED


def test_a_conflicted_entity_is_excluded_from_lookup_and_named_in_the_report() -> None:
    """EM-06: excluded from lookup, reported, and the build still succeeds.

    A control entity is built alongside and its lookups asserted first, so an
    implementation whose ``lookup`` always returns ``None`` cannot pass. The
    conflicted entity is looked up both on the disputed namespace and on its
    undisputed ISIN, because "the entity is excluded" is wider than "the
    disputed value is excluded". A3 also routes ``analysis_universe()`` through
    ``conflicted``, so the control entity must be the only member.
    """
    built = fx.build(
        *_conflicting_pair(),
        fx.record(isin_code=fx.BRAVO_ISIN, nse=fx.BRAVO_NSE),
    )

    assert fx.by_key(built)[fx.BRAVO_ISIN].conflicted is False
    assert built.lookup(fx.namespace(fx.NSE_NS), fx.BRAVO_NSE) is not None
    assert built.lookup(fx.namespace(fx.ISIN_NS), fx.BRAVO_ISIN) is not None

    assert built.lookup(fx.namespace(fx.NSE_NS), fx.ALPHA_NSE) is None
    assert built.lookup(fx.namespace(fx.NSE_NS), fx.ZULU_NSE) is None
    assert built.lookup(fx.namespace(fx.ISIN_NS), fx.ALPHA_ISIN) is None
    assert fx.ALPHA_ISIN in built.conflicts
    assert [entity.key for entity in built.analysis_universe()] == [fx.BRAVO_ISIN]


def _conflicting_pair() -> tuple[Any, ...]:
    """One ISIN, two sources, two different NSE symbols."""
    return (
        fx.record(isin_code=fx.ALPHA_ISIN, nse=fx.ALPHA_NSE),
        fx.record(source_id=fx.S2_SOURCE_ID, isin_code=fx.ALPHA_ISIN, nse=fx.ZULU_NSE),
    )


def test_an_entity_can_be_not_listed_and_conflicted_at_the_same_time() -> None:
    """A3 / EM-03 / EM-06: keying-and-listing and conflict are independent facts.

    Under the superseded single-enum design this entity was inexpressible: it
    has no exchange code of either kind (``NOT_LISTED``) *and* two sources
    disagreeing on its Screener slug (``conflicted``), and one field could only
    record one of the two. Collapsing them would either hide the delisting from
    the universe filter or hide the disagreement from the report. The control
    entity is listed and unconflicted, so neither exclusion can be faked by an
    empty universe or a dead ``lookup``.
    """
    built = fx.build(
        fx.record(isin_code=fx.ALPHA_ISIN, screener_slug=fx.ALPHA_NSE),
        fx.record(source_id=fx.S2_SOURCE_ID, isin_code=fx.ALPHA_ISIN, screener_slug=fx.ZULU_NSE),
        fx.record(isin_code=fx.BRAVO_ISIN, nse=fx.BRAVO_NSE),
    )

    entity = fx.by_key(built)[fx.ALPHA_ISIN]
    assert entity.state is fx.contracts.EntityState.NOT_LISTED
    assert entity.conflicted is True
    assert sorted(fx.values_of(entity, fx.SCREENER_SLUG_NS)) == sorted([fx.ALPHA_NSE, fx.ZULU_NSE])

    assert built.lookup(fx.namespace(fx.ISIN_NS), fx.BRAVO_ISIN) is not None
    assert built.lookup(fx.namespace(fx.ISIN_NS), fx.ALPHA_ISIN) is None
    assert [member.key for member in built.analysis_universe()] == [fx.BRAVO_ISIN]


# ---------------------------------------------------------------------------
# EM-07 — needs_verification fields are ingested as unverified
# ---------------------------------------------------------------------------


def test_an_unverified_value_is_stored_but_does_not_satisfy_a_lookup_on_its_own() -> None:
    """EM-07: stored with ``verified=False`` and never a lookup path by itself.

    The entity is reachable on its verified NSE symbol in the same assertion
    block, so the ``None`` on the unverified BSE scrip cannot be explained by a
    missing entity or a dead ``lookup``. A control entity with a *verified* BSE
    scrip proves the BSE lookup path works at all.
    """
    built = fx.build(
        fx.record(
            source_id=fx.S2_SOURCE_ID,
            isin_code=fx.CHARLIE_ISIN,
            nse=fx.CHARLIE_NSE,
            bse=fx.CHARLIE_BSE,
            unverified=(fx.BSE_NS,),
        ),
        fx.record(isin_code=fx.BRAVO_ISIN, nse=fx.BRAVO_NSE, bse=fx.BRAVO_BSE),
    )

    assert built.lookup(fx.namespace(fx.BSE_NS), fx.BRAVO_BSE) is not None
    entity = built.lookup(fx.namespace(fx.NSE_NS), fx.CHARLIE_NSE)
    assert entity is not None

    assert fx.values_of(entity, fx.BSE_NS) == (fx.CHARLIE_BSE,)
    assert fx.coverage(entity, fx.BSE_NS).status is fx.contracts.CoverageStatus.UNVERIFIED
    assert built.lookup(fx.namespace(fx.BSE_NS), fx.CHARLIE_BSE) is None


def test_a_second_source_asserting_the_same_value_promotes_it_to_verified() -> None:
    """EM-07: confirmation by a second source verifies the value.

    Both records name the same ISIN so the join is not in question. The single
    surviving value must carry both provenances — an implementation that
    replaces rather than confirms loses the S2 pin and its evidence trail — and
    the value must now satisfy a BSE lookup, which it did not before.
    """
    built = fx.build(
        fx.record(
            source_id=fx.S2_SOURCE_ID,
            isin_code=fx.CHARLIE_ISIN,
            bse=fx.CHARLIE_BSE,
            unverified=(fx.BSE_NS,),
        ),
        fx.record(isin_code=fx.CHARLIE_ISIN, bse=fx.CHARLIE_BSE),
    )

    entity = fx.by_key(built)[fx.CHARLIE_ISIN]
    assert fx.values_of(entity, fx.BSE_NS) == (fx.CHARLIE_BSE,)
    assert fx.source_ids_of(entity, fx.BSE_NS) == (frozenset({fx.S1_SOURCE_ID, fx.S2_SOURCE_ID}),)
    assert fx.coverage(entity, fx.BSE_NS).status is fx.contracts.CoverageStatus.KNOWN
    assert built.lookup(fx.namespace(fx.BSE_NS), fx.CHARLIE_BSE) is not None


def test_a_second_source_contradicting_an_unverified_value_is_an_ordinary_conflict() -> None:
    """EM-07: an unverified value that is contradicted conflicts under EM-06.

    The tempting shortcut is to let the verified source overwrite the
    unverified pin, which reads as tidy and destroys the disagreement a human
    needs to see. Both values and the CONFLICTED state are asserted, not just
    the state.
    """
    built = fx.build(
        fx.record(
            source_id=fx.S2_SOURCE_ID,
            isin_code=fx.CHARLIE_ISIN,
            bse=fx.CHARLIE_BSE,
            unverified=(fx.BSE_NS,),
        ),
        fx.record(isin_code=fx.CHARLIE_ISIN, bse=fx.DELTA_BSE),
    )

    entity = fx.by_key(built)[fx.CHARLIE_ISIN]
    assert entity.conflicted is True
    assert fx.coverage(entity, fx.BSE_NS).status is fx.contracts.CoverageStatus.CONFLICTED
    assert sorted(fx.values_of(entity, fx.BSE_NS)) == sorted([fx.CHARLIE_BSE, fx.DELTA_BSE])


# ---------------------------------------------------------------------------
# EM-08 — join by ISIN, then NSE, then BSE; never by name
# ---------------------------------------------------------------------------


def test_two_records_sharing_only_a_display_name_stay_two_entities() -> None:
    """EM-08: a name is not an identifier, so it must never join two records.

    The two records carry the identical display name and no key in common. A
    missed join is recoverable; joining on the name attributes one company's
    financials to another. An implementation that falls back to the name when
    no key matches publishes one entity here.
    """
    built = fx.build(
        fx.record(source_id=fx.S2_SOURCE_ID, display_name=fx.SHARED_NAME, nse=fx.ZULU_NSE),
        fx.record(source_id=fx.S2_SOURCE_ID, display_name=fx.SHARED_NAME, bse=fx.ORPHAN_BSE),
    )

    assert sorted(fx.by_key(built)) == sorted([f"bse:{fx.ORPHAN_BSE}", f"nse:{fx.ZULU_NSE}"])


def test_two_records_with_different_names_but_one_isin_are_one_entity() -> None:
    """EM-08: the ISIN wins over a name mismatch, including a truncated export name.

    The S1 export truncates display names, so an implementation that requires
    the names to agree before joining on the ISIN would split almost every
    live member in two. Both names are retained on the single entity.
    """
    truncated = fx.ALPHA_NAME[:16]
    built = fx.build(
        fx.record(display_name=fx.ALPHA_NAME, isin_code=fx.ALPHA_ISIN),
        fx.record(source_id=fx.S2_SOURCE_ID, display_name=truncated, isin_code=fx.ALPHA_ISIN),
    )

    assert [entity.key for entity in built.entities] == [fx.ALPHA_ISIN]
    assert sorted(built.entities[0].display_names) == sorted([fx.ALPHA_NAME, truncated])


def test_records_with_no_isin_join_on_the_nse_symbol() -> None:
    """EM-08: the second rung of the ladder.

    Neither record has an ISIN, so the NSE symbol is the only available join
    key. An implementation that joins on ISIN alone publishes two entities and
    duplicates the security.
    """
    built = fx.build(
        fx.record(source_id=fx.S2_SOURCE_ID, nse=fx.ZULU_NSE, screener_slug=fx.ZULU_NSE),
        fx.record(source_id=fx.S1_SOURCE_ID, nse=fx.ZULU_NSE, bse=fx.ORPHAN_BSE),
    )

    assert [entity.key for entity in built.entities] == [f"nse:{fx.ZULU_NSE}"]


def test_records_with_neither_isin_nor_nse_join_on_the_bse_scrip() -> None:
    """EM-08: the third rung of the ladder.

    Written separately from the NSE case because an implementation that stops
    the ladder after two rungs passes that test and fails only this one.
    """
    built = fx.build(
        fx.record(source_id=fx.S2_SOURCE_ID, bse=fx.ORPHAN_BSE, screener_slug="fixture-orphan"),
        fx.record(source_id=fx.S1_SOURCE_ID, bse=fx.ORPHAN_BSE),
    )

    assert [entity.key for entity in built.entities] == [f"bse:{fx.ORPHAN_BSE}"]


# ---------------------------------------------------------------------------
# EM-10 — current-state only
# ---------------------------------------------------------------------------


def test_no_published_model_carries_an_as_of_or_versioning_dimension() -> None:
    """EM-10: current state only — history belongs to the snapshot store.

    Anticipating the snapshot store here would fork bitemporal modelling across
    two deliverables. The identity fields are asserted present first, so an
    empty or renamed model cannot pass this by having no fields at all.
    """
    entity_fields = set(fx.contracts.Entity.model_fields)
    assert {"key", "state"} <= entity_fields

    for model in (fx.contracts.Entity, fx.contracts.IdentifierValue, fx.contracts.EntityMap):
        assert _TEMPORAL_FIELDS.isdisjoint(set(model.model_fields))


# ---------------------------------------------------------------------------
# EM-11 — deterministic output
# ---------------------------------------------------------------------------


def test_entities_are_sorted_isin_first_then_surrogate_each_group_lexicographic() -> None:
    """EM-11: the published order is the contract's order, not the input's.

    Feeding the records in a deliberately wrong order is what makes this
    non-vacuous: an implementation that emits insertion order passes an
    identical-input comparison and fails here.
    """
    built = fx.build(*_mixed_records())

    assert [entity.key for entity in built.entities] == [
        fx.ALPHA_ISIN,
        fx.BRAVO_ISIN,
        f"bse:{fx.ORPHAN_BSE}",
        f"nse:{fx.ZULU_NSE}",
    ]


def test_two_builds_over_identical_input_produce_byte_identical_json() -> None:
    """EM-11: a diff of two artifacts is meaningful, so a re-run must not churn.

    The two builds are given freshly constructed but equal records, and the
    second is given them in a different order, so this catches both an
    unstable serialisation and an order-dependent one. A comparison over one
    shared record list would prove nothing.
    """
    first = fx.build(*_mixed_records()).model_dump_json(indent=2)
    second = fx.build(*reversed(_mixed_records())).model_dump_json(indent=2)

    assert first == second


def _mixed_records() -> tuple[Any, ...]:
    """Two ISIN-keyed and two surrogate-keyed records, in a deliberately wrong order."""
    return (
        fx.record(source_id=fx.S2_SOURCE_ID, nse=fx.ZULU_NSE),
        fx.record(isin_code=fx.BRAVO_ISIN, nse=fx.BRAVO_NSE),
        fx.record(source_id=fx.S2_SOURCE_ID, bse=fx.ORPHAN_BSE),
        fx.record(isin_code=fx.ALPHA_ISIN, nse=fx.ALPHA_NSE),
    )


# ---------------------------------------------------------------------------
# EM-12 — coverage is stated, not implied
# ---------------------------------------------------------------------------


def test_a_namespace_no_source_supplied_is_published_as_null_with_a_reason() -> None:
    """EM-12: absence of a field is never used to mean "unknown".

    The record below supplies no Tijori identifier of any kind, and separately
    *carries* the BSE namespace while reporting it null. Both must publish a
    coverage record, and A6's two reasons must come out different: "we never
    looked" (``NOT_SUPPLIED``) versus "the source says there is no such value"
    (``SOURCE_REPORTED_ABSENT``, the shape of a company with no NSE listing).
    An implementation that collapses the two into one reason goes red on one of
    the two halves. An implementation that simply omits the key passes any test
    that reads with ``.get(...)``, so the coverage lookup here raises
    ``KeyError`` instead, and every namespace of the enum is checked.
    """
    built = fx.build(
        fx.record(isin_code=fx.ALPHA_ISIN, nse=fx.ALPHA_NSE, reported_absent=(fx.BSE_NS,))
    )
    entity = fx.by_key(built)[fx.ALPHA_ISIN]

    published = {covered.namespace for covered in entity.namespaces}
    assert published == set(fx.contracts.IdentifierNamespace)

    for name in (fx.TIJORI_SLUG_NS, fx.TIJORI_COMPANY_ID_NS):
        missing = fx.coverage(entity, name)
        assert missing.status is fx.contracts.CoverageStatus.MISSING
        assert missing.values == ()
        assert missing.missing_reason is fx.contracts.MissingReason.NOT_SUPPLIED

    absent = fx.coverage(entity, fx.BSE_NS)
    assert absent.status is fx.contracts.CoverageStatus.MISSING
    assert absent.values == ()
    assert absent.missing_reason is fx.contracts.MissingReason.SOURCE_REPORTED_ABSENT


def test_no_identifier_is_ever_published_as_an_empty_string() -> None:
    """EM-12: a missing value is explicit null, never ``""``.

    Two halves, because an implementation can fail either one: an empty string
    must be refused at the assertion boundary rather than stored, and the
    serialised artifact of a legitimately sparse entity must contain no empty
    string anywhere. The accepting construction is asserted first.
    """
    marks = (fx.provenance(fx.S1_SOURCE_ID),)
    assert (
        fx.contracts.SourceAssertion(
            namespace=fx.namespace(fx.NSE_NS),
            value=fx.ALPHA_NSE,
            provenance=marks[0],
            verified=True,
        ).value
        == fx.ALPHA_NSE
    )

    with pytest.raises(ValidationError):
        fx.contracts.SourceAssertion(
            namespace=fx.namespace(fx.NSE_NS), value="", provenance=marks[0], verified=True
        )

    built = fx.build(fx.record(isin_code=fx.ALPHA_ISIN))
    assert "" not in _strings(json.loads(built.model_dump_json()))
