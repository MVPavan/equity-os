"""Exercise privacy rails through the public gate in an isolated synthetic repo."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]


def _git(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=root, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


@pytest.fixture
def gate(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    shutil.copy2(REPO_ROOT / "scripts/verify.sh", scripts / "verify.sh")
    (tmp_path / "tests/equity_os").mkdir(parents=True)
    (tmp_path / "scratchpad/gate").mkdir(parents=True)
    (tmp_path / ".gitignore").write_text("scratchpad/\nbin/\ndata/\n")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.name", "Privacy gate test")
    _git(tmp_path, "config", "user.email", "privacy@example.invalid")
    _git(tmp_path, "add", ".gitignore")
    _git(tmp_path, "commit", "-qm", "synthetic baseline")
    (tmp_path / "scratchpad/gate/privacy-baseline.json").write_text(
        json.dumps(
            {
                "passed": 1,
                "taken_at": "synthetic",
                "tests": ["tests/equity_os/test_synthetic.py::test_pass"],
            }
        )
    )
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    uv = bin_dir / "uv"
    uv.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "with open(os.environ['PRIVACY_TEST_CALLS'], 'a') as output:\n"
        "    output.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "if sys.argv[1:3] == ['run', 'pytest']:\n"
        "    print('PASSED tests/equity_os/test_synthetic.py::test_pass')\n"
    )
    uv.chmod(0o755)
    environment = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "PRIVACY_TEST_CALLS": str(tmp_path / "bin/calls.jsonl"),
    }
    environment.pop("VERIFY_SCOPE_BASE", None)
    return tmp_path, environment


def _run(gate: tuple[Path, dict[str, str]]) -> subprocess.CompletedProcess[str]:
    root, environment = gate
    return subprocess.run(
        ["bash", str(root / "scripts/verify.sh"), "gate", "privacy"],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def _capture(root: Path, text: str) -> None:
    captures = root / "scratchpad/synthetic_capture"
    captures.mkdir(parents=True, exist_ok=True)
    (captures / "page.html").write_text(text)


def test_indented_short_generic_metadata_is_not_a_pasted_capture(gate) -> None:
    root, _ = gate
    label = '"identity_strength": "configured_url_only",'
    (root / "tests/equity_os/test_synthetic.py").write_text(" " * 28 + label + "\n")
    _capture(root, label)

    result = _run(gate)

    assert result.returncode == 0, result.stdout
    assert "rails            OK" in result.stdout


def test_historical_scope_replays_committed_identifiers_with_head_default(gate) -> None:
    root, environment = gate
    base = _git(root, "rev-parse", "HEAD")
    token = str(900_000 + 73)
    path = "tests/equity_os/test_synthetic.py"
    (root / path).write_text(f'company_id = "{token}"\n')
    _git(root, "add", path)
    _git(root, "commit", "-qm", "synthetic copied ID")
    _capture(root, f'<tr data-row-company-id="{token}">')

    assert _run(gate).returncode == 0
    environment["VERIFY_SCOPE_BASE"] = base
    result = _run(gate)

    assert result.returncode == 3, result.stdout
    assert "real captured identifier" in result.stdout


def test_branch_default_scope_is_the_merge_base_with_main(gate) -> None:
    root, _ = gate
    _git(root, "branch", "-M", "main")
    _git(root, "switch", "-qc", "feature")
    token = str(900_000 + 73)
    path = "tests/equity_os/test_synthetic.py"
    (root / path).write_text(f'company_id = "{token}"\n')
    _git(root, "add", path)
    _git(root, "commit", "-qm", "synthetic copied ID")
    _capture(root, f'<tr data-row-company-id="{token}">')

    result = _run(gate)

    assert result.returncode == 3, result.stdout
    assert "real captured identifier" in result.stdout


@pytest.mark.parametrize(
    "template",
    (
        'company_id = "{}"',
        "row_id = {}",
        'url = "/company/id/{}/"',
        '<tr data-row-company-id="{}">',
        "# unknown captured numeric token {}",
    ),
)
def test_unknown_numeric_issuer_and_row_ids_still_stop(gate, template) -> None:
    root, environment = gate
    token = str(900_000 + 73)
    (root / "tests/equity_os/test_synthetic.py").write_text(template.format(token))
    environment["VERIFY_PRIVACY_ALLOW_IDS"] = token  # No runtime bypass is supported.
    _capture(root, f'<tr data-row-company-id="{token}">')

    result = _run(gate)

    assert result.returncode == 3
    assert "real captured identifier" in result.stdout


def test_digit_run_inside_a_digest_is_not_an_identifier(gate) -> None:
    """A sha256 digest can hold a captured id's digits by chance; it names content, not issuers."""
    root, _ = gate
    token = str(900_000 + 73)
    digest = "a" * 29 + token + "b" * 29
    (root / "tests/equity_os/test_synthetic.py").write_text(f'EXPECTED = "{digest}"\n')
    _capture(root, f'<tr data-row-company-id="{token}">')

    result = _run(gate)

    assert result.returncode != 3, result.stdout
    assert "real captured identifier" not in result.stdout


def test_identifier_rail_ignores_bare_four_digit_values_and_reports_every_match(gate) -> None:
    """Bare four digits look like a year or round amount; a truncated report hides leaks."""
    root, _ = gate
    tokens = [str(90_001 + at) for at in range(4)]
    (root / "tests/equity_os/test_synthetic.py").write_text(f"values = {[2023, *tokens]}\n")
    rows = "".join(f'<tr data-row-company-id="{token}">' for token in ["2023", *tokens])
    _capture(root, rows)

    result = _run(gate)

    assert result.returncode == 3
    assert f"real captured identifier in a fixture: {','.join(tokens)}" in result.stdout
    assert "2023" not in result.stdout.split("real captured identifier")[1].split("\n")[0]


@pytest.mark.parametrize("line", ["ratio = 0.90073", "price = 90073.25", "pe = 12.90073"])
def test_identifier_rail_ignores_the_digits_of_a_decimal(gate, line: str) -> None:
    """A decimal is an amount: its digits matching a captured id is coincidence, not a leak."""
    root, _ = gate
    (root / "tests/equity_os/test_synthetic.py").write_text(f"{line}\n")
    _capture(root, '<tr data-row-company-id="90073">')

    result = _run(gate)

    assert result.returncode == 0, result.stdout
    assert "rails            OK" in result.stdout


@pytest.mark.parametrize(
    "line",
    [
        'url = "/company/1234/"',
        'url = "/company/id/1234/"',
        '<tr data-row-company-id="1234">',
        'company_id = "1234"',
        "row_id = 1234",
        '{"company_id": 1234}',
        "rowId: '1234'",
    ],
)
def test_identifier_rail_still_catches_a_four_digit_id_in_id_context(gate, line: str) -> None:
    """A real short id written as an id is a leak, even though a bare number is not judged."""
    root, _ = gate
    (root / "tests/equity_os/test_synthetic.py").write_text(f"{line!r}\n")
    _capture(root, '<tr data-row-company-id="1234">')

    result = _run(gate)

    assert result.returncode == 3
    assert "real captured identifier in a fixture: 1234" in result.stdout


@pytest.mark.parametrize("indent", (0, 24))
def test_real_long_pasted_body_still_stops_after_trimming(gate, indent) -> None:
    root, _ = gate
    copied = "Synthetic private capture body with a distinctive long literal " + "X" * 32
    (root / "tests/equity_os/test_synthetic.py").write_text(" " * indent + copied)
    _capture(root, copied)

    result = _run(gate)

    assert result.returncode == 3
    assert "fixture text matches private capture" in result.stdout


DIGEST = "ab" * 32
NSE_CAPTURE = "data/raw/snapshots/v1/nse/announcement.html"
VENDOR_CAPTURE = "data/raw/snapshots/v1/vendor/page.html"
EVIDENCE = "docs/evidence/quote.md"
TEST_FILE = "tests/equity_os/test_synthetic.py"
QUOTE = "Synthetic exchange filing sentence quoted as evidence for a reviewed figure."


def _write(root: Path, path: str, text: str) -> None:
    (root / path).parent.mkdir(parents=True, exist_ok=True)
    (root / path).write_text(text)


@pytest.mark.parametrize(
    ("added_path", "added", "capture", "stops"),
    [
        # A lone quoted digest names a capture by hash; it is not its text.
        (TEST_FILE, f'    "{DIGEST}",\n', VENDOR_CAPTURE, False),
        # Only the lone digest is exempt: a longer line carrying one is still checked.
        (TEST_FILE, f'sha = "{DIGEST}"\n', VENDOR_CAPTURE, True),
        # Evidence may quote public NSE/BSE filings ...
        (EVIDENCE, QUOTE + "\n", NSE_CAPTURE, False),
        # ... but never any other capture,
        (EVIDENCE, QUOTE + "\n", VENDOR_CAPTURE, True),
        # and the exchange exception belongs to evidence files alone.
        (TEST_FILE, QUOTE + "\n", NSE_CAPTURE, True),
    ],
)
def test_pasted_capture_owner_exceptions(gate, added_path, added, capture, stops) -> None:
    root, _ = gate
    _write(root, added_path, added)
    _write(root, capture, f"<p>{added.strip()}</p>")

    result = _run(gate)

    assert (result.returncode == 3) is stops, result.stdout
    assert ("fixture text matches private capture" in result.stdout) is stops


def test_pasted_capture_rail_checks_every_candidate_line(gate) -> None:
    """A pasted line sorting after the 500th candidate still stops: no cap hides it."""
    root, _ = gate
    copied = "zz synthetic pasted capture line sorting after every other candidate"
    filler = [
        f"aa synthetic candidate line number {n:04d} written by hand for padding"
        for n in range(600)
    ]
    _write(root, TEST_FILE, "\n".join([*filler, copied]) + "\n")
    _capture(root, copied)

    result = _run(gate)

    assert result.returncode == 3, result.stdout
    assert "fixture text matches private capture" in result.stdout


@pytest.mark.parametrize("kind", ("cookie", "machine_path", "raw_path", "scratch_path"))
def test_cookie_machine_local_and_tracked_private_paths_still_stop(gate, kind) -> None:
    root, _ = gate
    path = "tests/equity_os/test_synthetic.py"
    if kind == "cookie":
        text = "sessionid=" + "SyntheticToken" * 3
    elif kind == "machine_path":
        text = "/" + "home/private-user/capture.json"
    else:
        path = ("data/raw/" if kind == "raw_path" else "scratchpad/") + "copied.txt"
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        text = "Synthetic private content"
    (root / path).write_text(text)
    if kind.endswith("path") and kind != "machine_path":
        _git(root, "add", "-f", path)

    result = _run(gate)

    assert result.returncode == 3
    assert "rails            STOP" in result.stdout


@pytest.mark.parametrize("base", ("does-not-exist", "--help", "HEAD;false", "HEAD^{tree}"))
def test_invalid_historical_scope_is_rejected_before_quality_commands(gate, base) -> None:
    root, environment = gate
    environment["VERIFY_SCOPE_BASE"] = base

    result = _run(gate)

    assert result.returncode == 3
    assert "invalid verification scope base" in result.stdout
    assert not (root / "bin/calls.jsonl").exists()


def test_default_gate_command_registry_and_bounded_output_are_preserved(gate) -> None:
    root, _ = gate

    result = _run(gate)

    assert result.returncode == 0
    assert len(result.stdout.splitlines()) == 9
    assert sum(line.startswith("ROUTE:") for line in result.stdout.splitlines()) == 1
    calls = [json.loads(line) for line in (root / "bin/calls.jsonl").read_text().splitlines()]
    assert calls[0][:11] == [
        "run",
        "pytest",
        "tests/equity_os",
        "-n",
        "24",
        "--dist",
        "loadfile",
        "-q",
        "--tb=short",
        "-rA",
        "--cov=equity_os",
    ]
    assert calls[0][-1] == "--cov-report="
    assert calls[0][11].startswith(f"--cov-report=json:{root}/scratchpad/gate/privacy-")
    assert calls[0][11].endswith("-cov.json")
    assert calls[1:] == [
        ["run", "ruff", "check", "equity_os", "tests/equity_os"],
        ["run", "ruff", "format", "--check", "equity_os", "tests/equity_os"],
        ["run", "mypy", "--strict", "equity_os"],
    ]
