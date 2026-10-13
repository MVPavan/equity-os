"""Project-verifier dispatch/control-flow proof, never phase acceptance evidence."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
EXIT_TARGETS = (
    ("D1a", "test_compare_tracer.py"),
    ("D1b", "test_data_stage1_e2e.py"),
    ("D2", "test_data_stage2_e2e.py"),
    ("D3", "test_ledger_stage1_e2e.py"),
    ("D3 export", "test_ledger_export.py"),
    ("D4", "test_ledger_stage2_e2e.py"),
    ("D5", "test_ledger_stage3_e2e.py"),
    ("D6", "test_data_stage4_e2e.py"),
    ("D7", "test_ledger_stage4_e2e.py"),
    ("D8", "test_data_stage3_e2e.py"),
    ("D9", "test_ledger_stage5_e2e.py"),
    ("Frozen manifests", "test_frozen_manifests.py"),
    ("Amendment records", "test_amendment_records.py"),
)


@pytest.fixture
def verifier(tmp_path: Path) -> tuple[Path, dict[str, str], Path]:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    original = REPO_ROOT / "scripts/verify_project.sh"
    assert original.is_file(), "the project verification command has not been built"
    script = scripts / original.name
    script.write_bytes(original.read_bytes())
    script.chmod(original.stat().st_mode)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "calls.jsonl"
    shim = bin_dir / "uv"
    shim.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "with open(os.environ['VERIFIER_TEST_CALLS'], 'a') as output:\n"
        "    output.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "failed = json.loads(os.environ.get('VERIFIER_TEST_FAILURES', '[]'))\n"
        "sys.exit(7 if sys.argv[1:] in failed else 0)\n"
    )
    shim.chmod(0o755)
    environment = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "VERIFIER_TEST_CALLS": str(calls),
    }
    return script, environment, calls


def _build_targets(script: Path) -> None:
    test_dir = script.parent.parent / "tests/fundamentals"
    test_dir.mkdir(parents=True)
    for _, name in EXIT_TARGETS:
        (test_dir / name).touch()


def _run(
    verifier: tuple[Path, dict[str, str], Path],
) -> tuple[subprocess.CompletedProcess[str], list]:
    script, environment, calls = verifier
    result = subprocess.run(
        [str(script)], env=environment, capture_output=True, text=True, check=False
    )
    return result, [json.loads(line) for line in calls.read_text().splitlines()]


def _statuses(result: subprocess.CompletedProcess[str]) -> dict[str, str]:
    return {
        line.split(" | ")[0]: line.split(" | ")[1]
        for line in result.stdout.splitlines()
        if " | " in line
    }


def test_missing_parts_are_named_not_built_and_fail_closed(verifier) -> None:
    result, calls = _run(verifier)

    assert result.returncode == 1
    statuses = _statuses(result)
    for label, _ in EXIT_TARGETS:
        assert statuses[label] == "NOT BUILT"
    assert statuses["Pilot"] == "NOT BUILT"
    assert len(calls) == 4
    assert all(statuses[label] == "PASS" for label in ("Pytest", "Mypy", "Ruff", "Ruff format"))


def test_failed_parts_do_not_stop_remaining_exits_or_quality_gates(verifier) -> None:
    script, environment, _ = verifier
    _build_targets(script)
    environment["VERIFIER_TEST_FAILURES"] = json.dumps(
        [
            ["run", "pytest", "tests/fundamentals/test_compare_tracer.py"],
            ["run", "pytest", "tests/fundamentals"],
        ]
    )

    result, calls = _run(verifier)

    assert result.returncode == 1
    statuses = _statuses(result)
    assert statuses["D1a"] == "FAIL"
    assert statuses["Pytest"] == "FAIL"
    assert statuses["D9"] == "PASS"
    assert statuses["Amendment records"] == "PASS"
    assert statuses["Ruff format"] == "PASS"
    assert calls[-1] == ["run", "ruff", "format", "--check", "src", "tests/fundamentals"]


def test_dispatch_uses_authoritative_targets_without_pg_or_retained_exclusions(verifier) -> None:
    script, _, _ = verifier
    _build_targets(script)

    result, calls = _run(verifier)

    assert calls == [
        ["run", "pytest", f"tests/fundamentals/{name}"] for _, name in EXIT_TARGETS
    ] + [
        ["run", "pytest", "tests/fundamentals"],
        ["run", "mypy", "--strict", "src"],
        ["run", "ruff", "check", "src", "tests/fundamentals"],
        ["run", "ruff", "format", "--check", "src", "tests/fundamentals"],
    ]
    assert result.returncode == 1
    assert _statuses(result)["Pilot"] == "NOT BUILT"


def test_future_registered_pilot_all_passing_control_flow_returns_zero(verifier) -> None:
    script, _, _ = verifier
    _build_targets(script)
    # Only this isolated copy registers a synthetic pilot for the future dispatch seam.
    # The production registry remains unresolved until an approved pilot contract exists.
    script.write_text(
        script.read_text().replace(
            'readonly PILOT_TARGET=""',
            'readonly PILOT_TARGET="tests/fundamentals/test_future_pilot_control_flow.py"',
        )
    )
    pilot = script.parent.parent / "tests/fundamentals/test_future_pilot_control_flow.py"
    pilot.touch()

    result, calls = _run(verifier)

    assert result.returncode == 0
    assert set(_statuses(result).values()) == {"PASS"}
    assert ["run", "pytest", "tests/fundamentals/test_future_pilot_control_flow.py"] in calls


def test_present_phase_does_not_make_required_missing_export_pass(verifier) -> None:
    script, _, _ = verifier
    _build_targets(script)
    (script.parent.parent / "tests/fundamentals/test_ledger_export.py").unlink()

    result, calls = _run(verifier)

    assert result.returncode == 1
    statuses = _statuses(result)
    assert statuses["D3"] == "PASS"
    assert statuses["D3 export"] == "NOT BUILT"
    assert ["run", "pytest", "tests/fundamentals/test_ledger_export.py"] not in calls
