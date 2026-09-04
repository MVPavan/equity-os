"""Lane B step 5(c): what a threshold or an exclusion has to arrive with.

Acceptance tests T13 and T19 of ``scratchpad/laneb-5c/plan.md``, covering C-05
and C-09. The per-row rules are in ``test_laneb_triage`` and the command-level
half in ``test_laneb_triage_cli``.

Held apart from the rules they govern because these two are the only tests here
that read a file: every other behaviour is decided in memory, while these decide
what the repository is allowed to ship as a decision record. ``_triage`` is
restated rather than imported, as it is in the command-level half — a
three-line, call-time import is cheaper than a dependency between test modules.

Every value is synthetic apart from the shipped config the last test loads.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from types import ModuleType

import pytest
from tests.fundamentals.upstox_fixtures import NSE_ISIN, NSE_SYMBOL

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = _REPO_ROOT / "config" / "laneb_triage.yaml"
DEFAULT_REVIEW_OWNER = "PavanMV"
DEFAULT_WARN_RATIO = Decimal("0.20")


def _triage() -> ModuleType:
    """Import the module under test at call time, not at collection time."""
    from fundamentals.verify import laneb_triage

    return laneb_triage


def test_a_threshold_or_exclusion_the_config_cannot_justify_is_refused(tmp_path: Path) -> None:
    """T13/C-05: every number and every exclusion has to arrive with its evidence.

    The 20% bar is a measurement, not a preference, and an acknowledgement
    silences a warn for a named company and field — the one mechanism here that
    can hide a real finding. So each entry carries the reason and the document it
    was measured in, a category the name map actually declares (an unmapped one
    would silence nothing while reading as if it did), a checkable ISIN, and no
    duplicates, since two entries for one cell means one of them is unread. A
    ratio of 0 would warn on every disagreeing line and one above 1 is
    unreachable, so both are refused rather than accepted as a no-op.
    """
    module = _triage()
    assert issubclass(module.TriageConfigError, ValueError)
    valid = (
        "magnitude_warn_ratio: '0.20'\n"
        f"review_owner: {DEFAULT_REVIEW_OWNER}\n"
        "acknowledged:\n"
        f"  - isin: {NSE_ISIN}\n"
        f"    symbol: {NSE_SYMBOL}\n"
        "    upstox_category: operating_profit\n"
        "    reason: definitional, exceptional items sit differently\n"
        "    measured_in: docs/research/laneb/part-2.md\n"
    )
    path = tmp_path / "valid.yaml"
    path.write_text(valid, encoding="utf-8")
    config = module.load_triage_config(path)
    assert config.magnitude_warn_ratio == DEFAULT_WARN_RATIO
    assert config.review_owner == DEFAULT_REVIEW_OWNER
    assert len(config.acknowledged) == 1

    malformed = {
        "missing-reason": valid.replace(
            "    reason: definitional, exceptional items sit differently\n", ""
        ),
        "ratio-zero": valid.replace("'0.20'", "'0'"),
        "ratio-above-one": valid.replace("'0.20'", "'1.5'"),
        "unknown-category": valid.replace("operating_profit", "ebitda"),
        "bad-isin": valid.replace(NSE_ISIN, "INE999Z01013"),
        "duplicate-entry": valid + valid.split("acknowledged:\n")[1],
        # The plural reads as correct and loads as a config with no exclusions
        # at all, so the documented 32% definitional line warns every run.
        "unknown-key": valid.replace("acknowledged:", "acknowledgements:"),
    }
    for name, text in malformed.items():
        bad = tmp_path / f"{name}.yaml"
        bad.write_text(text, encoding="utf-8")
        with pytest.raises(module.TriageConfigError, match=r".*"):
            module.load_triage_config(bad)


def test_the_default_config_ships_the_thresholds_the_measurements_support() -> None:
    """T19/C-09: the shipped file is the decision record, and it has to load.

    A threshold in a YAML nobody validates is a magic number with extra steps.
    This asserts the file the command reads by default is the one the owner
    approved: the 20% bar, the two documented tier-1 exclusions and no others,
    each carrying the reason and the measurement it came from, and a named review
    owner — because a warn with no owner is a log line.
    """
    module = _triage()
    config = module.load_triage_config(DEFAULT_CONFIG_PATH)
    assert config.magnitude_warn_ratio == DEFAULT_WARN_RATIO
    assert config.review_owner == DEFAULT_REVIEW_OWNER
    assert len(config.acknowledged) == 2
    for entry in config.acknowledged:
        assert entry.reason.strip()
        assert entry.measured_in.strip()
