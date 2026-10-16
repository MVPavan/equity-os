"""The Stage 4 manifest and held-out record checks, behind one opaque boundary (plan D6 D1.7).

The frozen-manifest checks of ``test_frozen_manifests`` assert with whole locators and value
nodes, so Stage 4 is outside their parametrisation (nothing private is read at collection) and
each runs here, every failure a ``pytest.fail`` naming the check and its step only.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import test_frozen_manifests as frozen
from stage4_cases import STAGE4_CASES, stage4_case
from stage4_support import CHECKS as HOLDOUT_CHECKS
from stage4_support import need, opaque, refused

from fundamentals.api.cli import main

SECRET = "SYNTHETIC-LEXEME-0x5eed"  # a stand-in private lexeme, never a recorded value


def check_runs(path: Path) -> None:
    """The manifest's runs expand from the manifest alone (``test_runs_expand_...``)."""
    manifest = frozen.load(path)
    frozen.check_inventory(manifest)
    for run in manifest["runs"]:
        frozen.check_run(run)


MANIFEST_CHECKS: dict[str, Callable[[Path], None]] = {
    "hand verification": frozen.test_header_records_hand_verification,
    "source hashes": frozen.test_sources_match_their_hashes,
    "lexemes": frozen.test_every_lexeme_is_at_its_locator,
    "arithmetic": frozen.test_recorded_arithmetic_is_exact,
    "values": frozen.test_values_follow_from_their_lexemes,
    "runs": check_runs,
    "approved before e2e": frozen.test_approved_payload_preceded_its_e2e,
    "approved": frozen.test_manifest_is_approved,
}


@pytest.mark.retained
@pytest.mark.parametrize("check", MANIFEST_CHECKS)
def test_stage4_manifest(check: str) -> None:
    """Each frozen-manifest check holds for the Stage 4 manifest."""
    with opaque(f"stage4_manifest {check}"):
        MANIFEST_CHECKS[check](frozen.STAGE4)


@pytest.mark.parametrize("check", HOLDOUT_CHECKS)
def test_stage4_holdout(check: str) -> None:
    """The held-out record passes each D1 check; a failure names only the check (plan D6 D1.7)."""
    HOLDOUT_CHECKS[check](frozen.REPO)


@pytest.mark.parametrize("name", STAGE4_CASES)
def test_stage4_check(name: str, tmp_path: Path) -> None:
    """Each exclusion case passes; each mutation, locators intact, fails just its checks (T5a)."""
    stage1 = frozen.load(frozen.STAGE1)
    case = stage4_case(name, tmp_path, frozen.run_of(stage1, "APARINDS-Q2FY26"))
    manifest = case["manifest"]
    for loc in [node for node in frozen.walk(manifest["onboarding"]) if "src" in node]:
        frozen.check_locator(manifest, loc)
    checks = {"run": lambda: frozen.check_run(manifest["runs"][0]), "stage4": case["check"]}
    assert {key for key, check in checks.items() if refused(check)} == case["fails"]


def misplaced(tmp_path: Path) -> None:
    """The genuine locator check over a synthetic source whose line lacks the lexeme."""
    text = tmp_path / "source.txt"
    text.write_text("another line\n")
    manifest = {"header": {"sources": [{"label": "s", "path": str(text), "kind": "text"}]}}
    frozen.check_locator(manifest, {"src": "s", "line": 1, "lex": SECRET})


RAISES: dict[str, tuple[Callable[[Path], Any], str]] = {
    "locator": (misplaced, "AssertionError"),
    "value error": (lambda _: int(SECRET), "ValueError"),
    "cli exit": (lambda _: main(["onboard", SECRET]), "SystemExit"),
    "skip": (lambda _: pytest.skip(SECRET), "Skipped"),
    "xfail": (lambda _: pytest.xfail(SECRET), "XFailed"),
    "fail": (lambda _: pytest.fail(SECRET), "Failed"),
    "refused": (lambda _: need(False, "step"), "step"),
}


@pytest.mark.parametrize("name", RAISES)
def test_failure_output_names_only_the_check(
    name: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Any non-success outcome, ``SystemExit`` and pytest skip/xfail included, becomes one
    traceback-free failure naming the check and step; no lexeme reaches the report or the
    output streams."""
    raise_, step = RAISES[name]
    with pytest.raises(pytest.fail.Exception) as failed, opaque("stage4_manifest synthetic"):
        raise_(tmp_path)
    assert str(failed.value) == f"stage4_manifest synthetic: {step}"
    assert not failed.value.pytrace
    assert SECRET not in "".join(capsys.readouterr())


def test_user_interrupt_still_interrupts() -> None:
    """The boundary does not swallow a user interrupt."""
    with pytest.raises(KeyboardInterrupt), opaque("stage4_manifest synthetic"):
        raise KeyboardInterrupt
