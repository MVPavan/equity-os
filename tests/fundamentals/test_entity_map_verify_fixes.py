"""``verify`` defects the review round found (A19, A20, A27, A28).

Both reviewers independently found A19: the build joined only through confirmed
values while ``verify`` joined through any value, so a pin flagged
``needs_verification`` could be dragged onto another company's row and produce
fabricated disagreements and a non-zero exit. The structural fix for A20 —
resolving pins against the BUILT map rather than raw records — is what makes
A19 unreachable by construction, since ``lookup`` matches confirmed values only.

Every fixture is synthetic and written into ``tmp_path``; nothing here opens a
socket or reads a captured page.
"""

from __future__ import annotations

from pathlib import Path

import entity_map_fixtures as fx
import pytest
import test_entity_map_sources as source_tests

from fundamentals.api.cli import main
from fundamentals.api.cli_parser import build_parser
from fundamentals.api.screener_cli_dispatch import EXIT_OK, EXIT_REFUSED

COMMAND = "entity-map"

# Pinned against a company S1 does NOT carry, but whose scrip is another
# company's. Nothing else about it overlaps the evidence.
_STRAY_SCRIP_PIN = fx.Pin(
    name="Fixture Zulu Holdings Limited",
    nse_symbol=fx.ZULU_NSE,
    bse_scrip=fx.ALPHA_BSE,
    screener_slug=fx.ZULU_NSE,
    screener_company_id=9100007,
    screener_warehouse_id_standalone=9200007,
    tijori_slug="fixture-zulu-holdings",
    tijori_company_id=9300007,
    needs_verification=("bse_scrip",),
)


def _evidence(tmp_path: Path) -> Path:
    """Two unrelated watchlist members on disk."""
    return fx.write_s1_artifact(tmp_path, [fx.ALPHA_LISTING, source_tests.CHARLIE_LISTING])


def _outcomes(artifact: Path, config: Path) -> dict[str, object]:
    """The verify report as a symbol -> outcome mapping."""
    return {
        entry.symbol: entry.outcome for entry in fx.entity_map.verify_pins(artifact, config).entries
    }


# ---------------------------------------------------------------------------
# A19 — verify must join only through confirmed values
# ---------------------------------------------------------------------------


def test_an_unconfirmed_scrip_does_not_join_a_pin_to_another_companys_row(
    tmp_path: Path,
) -> None:
    """A19: a pin nothing has confirmed is no lookup path, so it joins nothing.

    ``bse_scrip`` is flagged ``needs_verification`` for two stocks in the
    committed config, so this is live-reachable today. Before the fix the stray
    scrip matched ALPHA's row and the report claimed CONFLICTED with three
    fabricated disagreements — symbol, slug and company id — none of which is a
    disagreement about anything, because the two records describe different
    companies. Under EM-07 plus EM-08 the truthful answer is NOT_COVERED.
    """
    artifact = _evidence(tmp_path)
    config = fx.write_s2_config(tmp_path, [_STRAY_SCRIP_PIN])

    assert _outcomes(artifact, config) == {
        fx.ZULU_NSE: fx.contracts.VerificationOutcome.NOT_COVERED
    }


def test_the_same_scrip_confirmed_does_join_and_reports_the_real_disagreement(
    tmp_path: Path,
) -> None:
    """A19's control: the join path itself still works, so NOT_COVERED means something.

    The only difference from the test above is that the scrip is no longer
    flagged unconfirmed. It now joins ALPHA's row and the pin genuinely
    disagrees with it, so an implementation that simply stopped joining on the
    BSE rung — which would also make the sibling test pass — goes red here.
    """
    artifact = _evidence(tmp_path)
    confirmed = _STRAY_SCRIP_PIN.model_copy(update={"needs_verification": ()})
    config = fx.write_s2_config(tmp_path, [confirmed])

    assert _outcomes(artifact, config) == {fx.ZULU_NSE: fx.contracts.VerificationOutcome.CONFLICTED}


# ---------------------------------------------------------------------------
# A20 — resolution goes through the built map, never through row position
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("reversed_rows", [False, True])
def test_a_pin_resolving_to_two_securities_is_refused_in_either_row_order(
    tmp_path: Path, reversed_rows: bool
) -> None:
    """A20: an ambiguous match is refused, never settled by which row came first.

    This pin carries ALPHA's symbol and CHARLIE's scrip, so two rungs of the
    ladder point at two different securities. The old ``_match`` returned the
    first record whose values intersected, so reversing the export's row order
    flipped the very same input between CONFIRMED and CONFLICTED — attribution
    decided by position. Both orders are exercised here, and the refusal must be
    identical for each.
    """
    listings = [fx.ALPHA_LISTING, source_tests.CHARLIE_LISTING]
    artifact = fx.write_s1_artifact(
        tmp_path, list(reversed(listings)) if reversed_rows else listings
    )
    straddling = _STRAY_SCRIP_PIN.model_copy(
        update={"nse_symbol": fx.ALPHA_NSE, "bse_scrip": fx.CHARLIE_BSE, "needs_verification": ()}
    )
    config = fx.write_s2_config(tmp_path, [straddling])

    with pytest.raises(fx.contracts.AmbiguousPinError):
        fx.entity_map.verify_pins(artifact, config)


@pytest.mark.parametrize("reversed_rows", [False, True])
def test_an_unambiguous_pin_reports_the_same_outcome_in_either_row_order(
    tmp_path: Path, reversed_rows: bool
) -> None:
    """A20's control: order independence is the property, not blanket refusal.

    A pin that resolves to exactly one security must report the same outcome
    however the export happened to order its rows. Without this, the refusal
    test above would pass an implementation that refused every pin.
    """
    listings = [fx.ALPHA_LISTING, source_tests.CHARLIE_LISTING]
    artifact = fx.write_s1_artifact(
        tmp_path, list(reversed(listings)) if reversed_rows else listings
    )
    config = fx.write_s2_config(tmp_path, [fx.ALPHA_PIN, source_tests.CHARLIE_PIN])

    assert _outcomes(artifact, config) == {
        fx.ALPHA_NSE: fx.contracts.VerificationOutcome.CONFIRMED,
        fx.CHARLIE_NSE: fx.contracts.VerificationOutcome.CONFLICTED,
    }


# ---------------------------------------------------------------------------
# A28 — verify applies EM-01 exactly as build does
# ---------------------------------------------------------------------------


def test_verify_refuses_a_pinned_isin_that_fails_the_check_digit(tmp_path: Path) -> None:
    """A28: the two commands must apply EM-01 identically.

    ``verify`` never validated what it read, so a malformed pinned ISIN passed
    silently and surfaced only later at ``build`` — the command whose whole job
    is to tell a human a pin is wrong staying quiet about the one kind of
    wrongness it can prove locally. A pin carrying a VALID ISIN is verified
    first, so the refusal is provably about the check digit.
    """
    artifact = _evidence(tmp_path)
    valid = fx.write_s2_config(
        tmp_path, [_STRAY_SCRIP_PIN.model_copy(update={"isin": fx.BRAVO_ISIN})]
    )
    assert fx.entity_map.verify_pins(artifact, valid).entries

    elsewhere = tmp_path / "malformed"
    elsewhere.mkdir()
    malformed = fx.write_s2_config(
        elsewhere, [_STRAY_SCRIP_PIN.model_copy(update={"isin": fx.WRONG_DIGIT_ISIN})]
    )

    with pytest.raises(fx.contracts.IsinFormatError):
        fx.entity_map.verify_pins(artifact, malformed)


# ---------------------------------------------------------------------------
# A27 — a designed refusal is a typed exit code, not a traceback
# ---------------------------------------------------------------------------


def test_a_refused_verify_exits_refused_rather_than_crashing(tmp_path: Path) -> None:
    """A27: every refusal this command reaches leaves the sibling commands' code.

    An uncaught ``EntityMapError`` exits 1 with a stack trace, which a caller
    reads as a crash rather than as the designed answer, and which no wrapper
    can tell apart from an interpreter fault. ``main`` returning at all is half
    the assertion: an unhandled exception would propagate out of this call.
    A clean run is asserted first, so the code cannot be explained by a bad path.
    """
    artifact = _evidence(tmp_path)
    clean = fx.write_s2_config(tmp_path, [_STRAY_SCRIP_PIN])
    argv = [COMMAND, "verify", "--artifact", str(artifact), "--config", str(clean)]
    assert build_parser().parse_args(argv).command == COMMAND
    assert main(argv) == EXIT_OK

    elsewhere = tmp_path / "malformed"
    elsewhere.mkdir()
    malformed = fx.write_s2_config(
        elsewhere, [_STRAY_SCRIP_PIN.model_copy(update={"isin": fx.WRONG_DIGIT_ISIN})]
    )
    refused = [COMMAND, "verify", "--artifact", str(artifact), "--config", str(malformed)]

    assert main(refused) == EXIT_REFUSED


def test_a_refused_build_exits_refused_rather_than_crashing(tmp_path: Path) -> None:
    """A27: the build path is wrapped too, and an incomplete artifact proves it.

    ``build`` and ``verify`` are separate branches of the dispatcher, so a
    ``try`` around one of them leaves the other crashing. The refusal used here
    is A21's — an artifact that stopped short — which reaches the CLI through
    the adapter rather than through the graph.
    """
    out = tmp_path / "out"
    incomplete = tmp_path / "incomplete.json"
    incomplete.write_text(
        _INCOMPLETE_ARTIFACT_JSON,
        encoding="utf-8",
    )
    config = fx.write_s2_config(tmp_path, [fx.ALPHA_PIN])
    argv = [
        COMMAND,
        "build",
        "--artifact",
        str(incomplete),
        "--config",
        str(config),
        "--out",
        str(out),
    ]
    assert build_parser().parse_args(argv).command == COMMAND

    assert main(argv) == EXIT_REFUSED
    assert not list(out.glob("*.json"))


_INCOMPLETE_ARTIFACT_JSON = """{
  "outcome": "incomplete",
  "incomplete_reason": "the fixture run stopped short",
  "failure": {
    "source_url": "https://fixture.invalid/watchlist/",
    "refusal": "WatchlistStructureError",
    "detail": "the fixture table had no admitted shape"
  }
}
"""
