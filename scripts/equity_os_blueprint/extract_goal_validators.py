#!/usr/bin/env python3
"""Extract the canonical embedded ledger validators from the active goal."""

from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GOAL = ROOT / "docs/goals/equity-os-blueprint-completion.md"
OUTPUTS = (
    ROOT / "scripts/equity_os_blueprint/validate_ledger_structural.py",
    ROOT / "scripts/equity_os_blueprint/validate_ledger_preimplementation.py",
)


def embedded_programs() -> list[str]:
    text = GOAL.read_text(encoding="utf-8")
    programs: list[str] = []
    cursor = 0
    opener = "```bash\npython3 - <<'PY'\n"
    closer = "\nPY\n```"
    while True:
        start = text.find(opener, cursor)
        if start == -1:
            break
        body_start = start + len(opener)
        end = text.find(closer, body_start)
        if end == -1:
            raise ValueError("unterminated embedded Python validator")
        programs.append(text[body_start:end] + "\n")
        cursor = end + len(closer)
    if len(programs) != 3:
        raise ValueError(f"expected 3 embedded validators, found {len(programs)}")
    return programs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if checked-in validators differ from the active goal",
    )
    args = parser.parse_args()
    programs = embedded_programs()
    stale: list[str] = []
    for output, program in zip(OUTPUTS, programs[: len(OUTPUTS)], strict=True):
        generated = (
            "#!/usr/bin/env python3\n"
            '"""Generated verbatim from docs/goals/equity-os-blueprint-completion.md."""\n\n'
            + program
        )
        if args.check:
            if not output.exists() or output.read_text(encoding="utf-8") != generated:
                stale.append(output.relative_to(ROOT).as_posix())
        else:
            output.write_text(generated, encoding="utf-8")
    if stale:
        raise SystemExit("stale generated validators: " + ", ".join(stale))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
