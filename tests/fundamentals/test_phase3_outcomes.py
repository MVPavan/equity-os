"""Acceptance tests for the shared capture-level outcome code (Phase 3, S1).

The seam under test is ``fundamentals.contracts.acquisition_outcome``: one
capture-level ``OutcomeCode``, an ``OutcomeRecord`` that keeps each source's
native wire value verbatim, and two ``to_outcome_record`` translators beside the
enums that already exist. Nothing here runs an acquisition; every value is
synthetic or read off an enum member.

The module under test does not exist yet, so each test imports it at call time.
That keeps collection green and puts the failure inside the test that names the
behaviour, rather than losing the whole file to one import error.
"""

from __future__ import annotations

import ast
import inspect
from importlib import import_module
from pathlib import Path
from typing import get_type_hints

import pytest
from pydantic import ValidationError
from test_upstox_scope_guards import (
    _imported_modules,
    declares_acquisition_outcome_class,
)

from fundamentals.ingest.screener_financials_models import SectionOutcome
from fundamentals.ingest.screener_screen_models import ScreenOutcome
from fundamentals.ingest.screener_session_models import PageOutcome
from fundamentals.ingest.screener_watchlist_models import WatchlistOutcome
from fundamentals.ingest.tijori_common import TijoriIslandStatus
from fundamentals.ingest.tijori_events_models import TijoriEventsOutcome
from fundamentals.ingest.upstox_source import RETRYABLE_OUTCOMES, AcquisitionOutcome

UPSTOX_ENUM_QUALIFIED_NAME = "fundamentals.ingest.upstox_source.AcquisitionOutcome"

EXPECTED_WIRE_VALUES = {
    "OK": "ok",
    "OK_EMPTY": "ok_empty",
    "NOT_OFFERED": "not_offered",
    "PLAN_LOCKED": "plan_locked",
    "AUTH_EXPIRED": "auth_expired",
    "IDENTITY_MISMATCH": "identity_mismatch",
    "SCHEMA_DRIFT": "schema_drift",
    "RATE_LIMITED": "rate_limited",
    "TRANSPORT_ERROR": "transport_error",
    "CLIENT_BLOCKED": "client_blocked",
    "REQUEST_REJECTED": "request_rejected",
}

PARSE_LEVEL_ENUMS = (
    SectionOutcome,
    ScreenOutcome,
    WatchlistOutcome,
    TijoriIslandStatus,
    TijoriEventsOutcome,
)

LANE_PACKAGES = (
    "fundamentals.ingest",
    "fundamentals.store",
    "fundamentals.reconcile",
    "fundamentals.api",
)


def test_outcome_code_pins_exactly_the_eleven_capture_level_states() -> None:
    """These eleven strings become persisted capture records and cross releases.

    A member added or a wire value edited silently rewrites the vocabulary every
    stored capture was written in, and a reader of last month's records has no
    way to tell a renamed state from a missing one. Pinning the whole map — not
    a subset — also refuses the drift the other direction: a twelfth member
    smuggling a parse-level state into a capture-level enum.
    """
    from fundamentals.contracts import acquisition_outcome

    actual = {member.name: member.value for member in acquisition_outcome.OutcomeCode}
    assert actual == EXPECTED_WIRE_VALUES


@pytest.mark.parametrize("member", list(AcquisitionOutcome), ids=lambda member: member.name)
def test_every_upstox_outcome_maps_and_keeps_its_native_wire_value(
    member: AcquisitionOutcome,
) -> None:
    """The Upstox enum stays the wire vocabulary; the shared code is the view.

    Exhaustiveness is the point: a member with no branch would either raise at
    the moment a capture is being recorded — losing the evidence of the failure
    that produced it — or fall through to a default that reports a block as a
    success. ``native_value`` is asserted verbatim because the record is the
    only place the source's own distinction survives the translation.
    """
    from fundamentals.contracts import acquisition_outcome
    from fundamentals.ingest.upstox_source import to_outcome_record

    record = to_outcome_record(member)
    assert record.code == acquisition_outcome.OutcomeCode[member.name]
    assert record.native_value == member.value
    assert record.native_kind == UPSTOX_ENUM_QUALIFIED_NAME


def test_retryability_agrees_with_the_upstox_retry_set() -> None:
    """Retry policy must not change meaning when a capture crosses the seam.

    ``RETRYABLE_OUTCOMES`` is what the adapter's bounded retry already obeys. If
    the shared code disagreed for any member, a caller reading records instead
    of the native enum would either hammer a terminal block — an auth expiry no
    backoff can clear — or abandon a rate limit that one wait would have cleared.
    """
    from fundamentals.contracts import acquisition_outcome
    from fundamentals.ingest.upstox_source import to_outcome_record

    code = acquisition_outcome.OutcomeCode
    expected = frozenset({code.RATE_LIMITED, code.TRANSPORT_ERROR})
    assert acquisition_outcome.RETRYABLE_CODES == expected
    for member in AcquisitionOutcome:
        record = to_outcome_record(member)
        assert record.retryable == (member in RETRYABLE_OUTCOMES), member.name


def test_basis_unavailable_maps_to_not_offered_and_never_to_success() -> None:
    """A standalone-only company serves HTTP 200 with an empty consolidated page.

    Read as ``OK`` or ``OK_EMPTY`` that page becomes a legitimate empty capture,
    and a later coverage report cannot distinguish "the vendor does not offer
    this basis" from "the vendor offered it and it was blank" — the second
    invites a retry and a substitution with the standalone figures, which is the
    exact contamination the page outcome was introduced to prevent.
    """
    from fundamentals.contracts import acquisition_outcome
    from fundamentals.ingest.screener_session_models import to_outcome_record

    code = acquisition_outcome.OutcomeCode
    assert to_outcome_record(PageOutcome.OK).code == code.OK

    record = to_outcome_record(PageOutcome.BASIS_UNAVAILABLE)
    assert record.code == code.NOT_OFFERED
    assert record.code not in {code.OK, code.OK_EMPTY}
    assert record.native_value == "basis_unavailable"


def test_outcome_record_is_frozen_and_rejects_extra_or_empty_provenance() -> None:
    """A capture record is evidence, so it must be unable to lose its origin.

    Mutability would let a consumer restate someone else's captured outcome in
    place; an ignored extra field would let a writer believe it attached detail
    that was silently dropped; and an empty ``native_kind`` or ``native_value``
    would leave a record that says what happened but not according to whom —
    unfalsifiable later, when the native vocabulary is the only way to re-check.
    """
    from fundamentals.contracts import acquisition_outcome

    code = acquisition_outcome.OutcomeCode
    record_type = acquisition_outcome.OutcomeRecord
    record = record_type(
        code=code.OK, native_kind="synthetic.module.SyntheticOutcome", native_value="FINE"
    )
    with pytest.raises(ValidationError):
        record.code = code.SCHEMA_DRIFT
    with pytest.raises(ValidationError):
        record_type(
            code=code.OK,
            native_kind="synthetic.module.SyntheticOutcome",
            native_value="FINE",
            note="unexpected",
        )
    for kind, value in (("", "FINE"), ("synthetic.module.SyntheticOutcome", "")):
        with pytest.raises(ValidationError):
            record_type(code=code.OK, native_kind=kind, native_value=value)


def test_parse_level_enums_are_left_unmapped_for_kx4_5() -> None:
    """Capture-level and parse-level answer different questions about a fetch.

    A section that would not parse, a screen with no rows, an island that never
    rendered — these describe what was *in* a response that arrived. Folding
    them into the capture code would make ``SCHEMA_DRIFT`` mean both "the vendor
    changed the payload" and "our parser missed a table", and no reader could
    then tell a source problem from our own. ``eqos-kx4.5`` owns that mapping.
    """
    from fundamentals.contracts import acquisition_outcome

    for enum_type in PARSE_LEVEL_ENUMS:
        module = import_module(enum_type.__module__)
        assert not hasattr(module, "to_outcome_record"), enum_type.__module__

    barred = {enum_type.__name__ for enum_type in PARSE_LEVEL_ENUMS}
    for name, value in vars(acquisition_outcome).items():
        if name.startswith("_") or not inspect.isfunction(value):
            continue
        annotated = {getattr(hint, "__name__", "") for hint in get_type_hints(value).values()}
        assert not annotated & barred, f"{name} accepts {sorted(annotated & barred)}"


def test_the_shared_taxonomy_imports_nothing_from_the_lanes() -> None:
    """Every lane imports this module, so it may import none of them back.

    Both adapters and, later, the snapshot store and the reconciler depend on
    the shared code; a single import pointing the other way makes the dependency
    cyclic and drags a transport module into anything that only wanted to read a
    stored outcome. Parsed, not imported, so an import guarded at runtime cannot
    hide from the check.
    """
    from fundamentals.contracts import acquisition_outcome

    assert acquisition_outcome.__file__ is not None
    imported = _imported_modules(Path(acquisition_outcome.__file__))
    offenders = sorted(name for name in imported if name.startswith(LANE_PACKAGES))
    assert not offenders, offenders


def test_the_narrowed_scope_guard_reads_definitions_not_prose() -> None:
    """The guard has to permit the very module ``eqos-kx4.4`` was told to ship.

    Its old substring scan would fire on ``acquisition_outcome.py``'s docstring
    explaining which native enums map into it — the guard would be satisfied
    only by an undocumented module, which inverts its purpose. Narrowed to a
    ``ClassDef``, it still fails on the one thing it was built to stop: a second
    enum published under the Upstox name in shared contracts.
    """
    from fundamentals.contracts import acquisition_outcome

    prose_only = '"""Maps AcquisitionOutcome members onto OutcomeCode."""\n\nVALUE = 1\n'
    competing = "from enum import StrEnum\n\n\nclass AcquisitionOutcome(StrEnum):\n    OK = 'ok'\n"
    assert not declares_acquisition_outcome_class(prose_only)
    assert declares_acquisition_outcome_class(competing)

    assert acquisition_outcome.__file__ is not None
    shipped = Path(acquisition_outcome.__file__).read_text(encoding="utf-8")
    assert not declares_acquisition_outcome_class(shipped)
    declared = {
        node.name for node in ast.walk(ast.parse(shipped)) if isinstance(node, ast.ClassDef)
    }
    assert "OutcomeCode" in declared
