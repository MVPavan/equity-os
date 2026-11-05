"""Several slice contracts share one gate run and one overall route."""

import hashlib
import json
import subprocess

import pytest
from test_verify_privacy import _git, _run, gate  # noqa: F401


@pytest.mark.parametrize("second", ("baseline", "red", "drift", "missing"))
def test_slices_share_checks_and_keep_each_contract(gate, second) -> None:  # noqa: F811
    root, environment = gate
    single = _run(gate)
    assert single.returncode == 0, single.stdout
    calls = root / "bin/calls.jsonl"
    calls.write_text("")
    acceptance = root / "tests/fundamentals/test_synthetic.py"
    acceptance.write_text("# synthetic acceptance\n")
    if second == "baseline":
        (root / "scratchpad/gate/second-baseline.json").write_bytes(
            (root / "scratchpad/gate/privacy-baseline.json").read_bytes()
        )
    elif second != "missing":
        (root / "scratchpad/gate/second-red.json").write_text(
            json.dumps(
                {
                    "files": [
                        {
                            "path": str(acceptance.relative_to(root)),
                            "sha256": hashlib.sha256(acceptance.read_bytes()).hexdigest(),
                        }
                    ],
                    "tests": [
                        {
                            "nodeid": "tests/fundamentals/test_synthetic.py::test_pass",
                            "outcome": "failed",
                        }
                    ],
                }
            )
        )
        if second == "drift":
            acceptance.write_text("# weakened contract\n")
    result = subprocess.run(
        ["bash", str(root / "scripts/verify.sh"), "gate", "privacy", "second"],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == (2 if second in ("drift", "missing") else 0), result.stdout
    assert result.stdout.count("ROUTE:") == 1
    assert "verify.sh gate second" in result.stdout
    # The first slice retains the single-slice report byte for byte, except time.
    first = result.stdout.split("verify.sh gate second")[0].splitlines()
    expected = single.stdout.splitlines()[:-1]
    assert first[1:-1] == expected[1:-1]
    invocations = [json.loads(line) for line in calls.read_text().splitlines()]
    assert invocations == [
        [
            "run",
            "pytest",
            "tests/fundamentals",
            "-n",
            "24",
            "--dist",
            "loadfile",
            "-q",
            "--tb=short",
            "-rA",
            next(arg for arg in invocations[0] if arg.startswith("--cov=")),
            next(arg for arg in invocations[0] if arg.startswith("--cov-report=json:")),
            "--cov-report=",
        ],
        ["run", "ruff", "check", "src", "tests/fundamentals"],
        ["run", "ruff", "format", "--check", "src", "tests/fundamentals"],
        ["run", "mypy", "--strict", "src"],
    ]
