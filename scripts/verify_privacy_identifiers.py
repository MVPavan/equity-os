#!/usr/bin/env python3
"""Catch captured IDs; exact, reviewed monetary contexts can resolve collisions."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


def git(root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def main() -> None:
    root = Path(sys.argv[1])
    scope_base = sys.argv[2]
    tokens = set(Path(sys.argv[3]).read_text().splitlines())
    if not tokens or any(re.fullmatch(r"[0-9]{4,}", token) is None for token in tokens):
        raise ValueError("invalid captured identifier set")
    # Fixed-path policy, no custom registry, environment allowlist or value bypass.
    registry = json.loads(Path(__file__).with_name("verify_privacy_proofs.json").read_text())
    proofs = set()
    for proof in registry["contexts"]:
        path = Path(proof["path"])
        if path.is_absolute() or ".." in path.parts or not str(path).startswith("tests/"):
            raise ValueError("invalid proof path")
        if (
            any(
                re.fullmatch(r"[0-9a-f]{64}", proof[field]) is None
                for field in ("file_sha256", "line_sha256")
            )
            or not proof["reason"]
            or not proof["source_proof"]
        ):
            raise ValueError("invalid collision proof")
        proofs.add((proof["path"], proof["file_sha256"], proof["line_sha256"], proof["token"]))
    changed = set(git(root, "diff", "--name-only", scope_base, "--", "tests").splitlines())
    untracked = set(
        git(root, "ls-files", "--others", "--exclude-standard", "--", "tests").splitlines()
    )
    pattern = re.compile(r"(?<!\w)(?:" + "|".join(sorted(tokens)) + r")(?!\w)")
    leaked = set()
    for name in sorted(changed | untracked):
        path = root / name
        if not path.is_file():
            continue
        content = path.read_bytes()
        if b"\0" in content:
            continue
        digest = hashlib.sha256(content).hexdigest()
        if name in untracked:
            lines = content.decode(errors="replace").splitlines()
        else:
            lines = [
                line[1:]
                for line in git(root, "diff", "-U0", scope_base, "--", name).splitlines()
                if line.startswith("+") and not line.startswith("+++ ")
            ]
        for line in lines:
            line_digest = hashlib.sha256(line.encode()).hexdigest()
            for token in pattern.findall(line):
                if (name, digest, line_digest, token) not in proofs:
                    leaked.add(token)
    print(",".join(sorted(leaked)[:3]))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError):
        print("identifier scan failed closed", file=sys.stderr)
        raise SystemExit(1) from None
