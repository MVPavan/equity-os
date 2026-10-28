"""Imported test support belongs to the acceptance contract's red seal."""

import json
import subprocess
import sys

from test_verify_privacy import _run, gate  # noqa: F401


def test_red_seals_transitive_support_and_conftest_and_detects_drift(gate) -> None:  # noqa: F811
    root, environment = gate
    uv = root / "bin/uv"
    stub = uv.read_text()
    uv.write_text(
        f"#!{sys.executable}\n"
        "import os, sys\n"
        "args = sys.argv[2:]\n"
        "args = ['-m', 'pytest', *args[1:]] if args[0] == 'pytest' else args[1:]\n"
        "os.execv(sys.executable, [sys.executable, *args])\n"
    )
    tests = root / "tests/fundamentals"
    (tests / "test_synthetic.py").write_text(
        "from local_support import value\ndef test_pass():\n    assert value == 2\n"
    )
    (tests / "local_support.py").write_text("from nested_support import value\n")
    (tests / "nested_support.py").write_text("value = 1\n")
    (tests / "conftest.py").write_text("import fixture_support\n")
    (tests / "fixture_support.py").write_text("value = 3\n")
    (tests / "unused_support.py").write_text("value = 4\n")
    (root / "scratchpad/gate/privacy-baseline.json").unlink()
    red = subprocess.run(
        [
            "bash",
            str(root / "scripts/verify.sh"),
            "red",
            "privacy",
            "tests/fundamentals/test_synthetic.py::test_pass",
        ],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert red.returncode == 0, red.stdout
    proof = json.loads((root / "scratchpad/gate/privacy-red.json").read_text())
    assert {entry["path"] for entry in proof["files"]} == {
        f"tests/fundamentals/{name}.py"
        for name in (
            "test_synthetic",
            "local_support",
            "nested_support",
            "conftest",
            "fixture_support",
        )
    }
    assert proof["tests"] == [
        {"nodeid": "tests/fundamentals/test_synthetic.py::test_pass", "outcome": "failed"}
    ]
    (tests / "nested_support.py").write_text("value = 2\n")
    uv.write_text(stub)
    result = _run(gate)
    assert result.returncode == 2, result.stdout
    assert "nested_support.py:modified" in result.stdout
