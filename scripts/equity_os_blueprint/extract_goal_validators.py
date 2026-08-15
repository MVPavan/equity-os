#!/usr/bin/env python3
"""Extract the canonical embedded ledger validators from the active goal."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GOAL = ROOT / "docs/goals/equity-os-blueprint-completion.md"
OUTPUTS = (
    ROOT / "scripts/equity_os_blueprint/validate_ledger_structural.py",
    ROOT / "scripts/equity_os_blueprint/validate_ledger_preimplementation.py",
)
HEADER = (
    "#!/usr/bin/env python3\n"
    '"""Generated verbatim from docs/goals/equity-os-blueprint-completion.md."""'
    "\n\n"
)


def embedded_programs(goal_path: Path) -> list[str]:
    text = goal_path.read_text(encoding="utf-8")
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


# r7 §7.3 D.1: one exact required marker substring per amendment item A1-A11.
# Each must appear at least once outside the three embedded program spans, so a
# future prose/validator divergence fails loudly instead of silently.
REQUIRED_MARKERS = {
    "A1": "`disposition_item` adds `applicable_spec_ids`",
    "A2": "`RELATED_REGISTER_SCOPE` or `ACTIVE_NEGATIVE_CONTROL`",
    "A3": "`ACTIVE_NEGATIVE_CONTROL` is allowed only for `phase_gate_clause`",
    "A4": "including one that became `REQUIRED_NOW` by related-register",
    "A5": '{"op":"COMPARE_METRICS"',
    "A6": "has current no-implementation proof only when",
    "A7": "may begin at sequence zero only with",
    "A8": "aggregated `REQUIRED_NOW` phase-gate clause carries no activation",
    "A9": "Closed required-authority vocabulary",
    "A10": "213 rows: 169 canonical and 44 aliases",
    "A11": "exact whole-object projections",
}

# r7 §7.3 D.2: closed lane-token list, matched case-insensitively at word
# boundaries. D.1 is a presence check and cannot catch an omitted rewrite.
LANE_TOKENS = ("Sol", "Terra", "Luna", "xhigh", "gpt-5.6", "Codex",
               "Agent Matrix")
LANE_TOKEN_PATTERN = re.compile(
    "|".join(rf"\b{re.escape(token)}\b" for token in LANE_TOKENS),
    re.IGNORECASE,
)
ACTIVATION_RECORD_HEADING = "## Activation record"
PROGRAM_OPENER = "```bash\npython3 - <<'PY'\n"
PROGRAM_CLOSER = "\nPY\n```"


def _program_spans(text: str) -> list[tuple[int, int]]:
    """Character spans of the three embedded programs, located by their fences."""
    spans: list[tuple[int, int]] = []
    cursor = 0
    while True:
        start = text.find(PROGRAM_OPENER, cursor)
        if start == -1:
            break
        body_start = start + len(PROGRAM_OPENER)
        end = text.find(PROGRAM_CLOSER, body_start)
        if end == -1:
            raise ValueError("unterminated embedded Python validator")
        spans.append((start, end + len(PROGRAM_CLOSER)))
        cursor = end + len(PROGRAM_CLOSER)
    if len(spans) != 3:
        raise ValueError(f"expected 3 embedded validators, found {len(spans)}")
    return spans


def _activation_record_span(text: str) -> tuple[int, int]:
    matches = [
        match.start() for match in
        re.finditer("^" + re.escape(ACTIVATION_RECORD_HEADING) + "$", text,
                    flags=re.MULTILINE)
    ]
    if len(matches) != 1:
        raise ValueError(
            f"expected one {ACTIVATION_RECORD_HEADING!r} heading, "
            f"found {len(matches)}"
        )
    return (matches[0], len(text))


def check_required_markers(text: str) -> list[str]:
    """r7 §7.3 D.1. Markers inside the program spans do not count."""
    spans = _program_spans(text)
    outside = []
    cursor = 0
    for start, end in spans:
        outside.append(text[cursor:start])
        cursor = end
    outside.append(text[cursor:])
    prose = "\n".join(outside)
    return [
        f"{item}: {marker!r}"
        for item, marker in sorted(REQUIRED_MARKERS.items())
        if marker not in prose
    ]


def check_lane_tokens(text: str) -> list[str]:
    """r7 §7.3 D.2. Zero occurrences outside the three closed exempt regions."""
    exempt = _program_spans(text) + [_activation_record_span(text)]
    line_starts = [0]
    for index, character in enumerate(text):
        if character == "\n":
            line_starts.append(index + 1)
    offenders = []
    for match in LANE_TOKEN_PATTERN.finditer(text):
        start, end = match.start(), match.end()
        if any(low <= start < high for low, high in exempt):
            continue
        # Exemption 3: path-literal contexts only, e.g. `.codex/…`.
        preceded = text[start - 1] if start else ""
        following = text[end] if end < len(text) else ""
        if preceded == "." and following == "/":
            continue
        line_number = sum(1 for position in line_starts if position <= start)
        offenders.append(f"line {line_number}: {match.group(0)!r}")
    return offenders


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if generated validators differ from the selected outputs",
    )
    parser.add_argument(
        "--goal-path",
        help="alternate goal document; defaults to the canonical active goal",
    )
    parser.add_argument("--structural-output")
    parser.add_argument("--preimplementation-output")
    parser.add_argument("--terminal-output")
    args = parser.parse_args()

    goal_path = Path(args.goal_path) if args.goal_path else GOAL
    if not goal_path.is_absolute():
        goal_path = ROOT / goal_path
    goal_text = goal_path.read_text(encoding="utf-8")
    programs = embedded_programs(goal_path)

    # r7 §7.3 D / §8.1: both anti-drift closures live here and both exit
    # nonzero on failure.
    missing_markers = check_required_markers(goal_text)
    lane_offenders = check_lane_tokens(goal_text)
    if missing_markers or lane_offenders:
        problems = []
        if missing_markers:
            problems.append(
                "missing required goal markers: " + "; ".join(missing_markers)
            )
        if lane_offenders:
            problems.append(
                "lane tokens outside the exempt regions: "
                + "; ".join(lane_offenders)
            )
        raise SystemExit(" | ".join(problems))

    explicit = (
        args.structural_output,
        args.preimplementation_output,
        args.terminal_output,
    )
    if any(explicit):
        targets = [
            None if value is None else Path(value) for value in explicit
        ]
    else:
        targets = [*OUTPUTS, None]

    # The terminal program is never a checked-in script; whenever it is
    # extracted it is syntax checked so a candidate goal cannot ship a program
    # that cannot even compile.
    compile(programs[2], "<terminal-validator>", "exec")

    stale: list[str] = []
    for target, program in zip(targets, programs, strict=True):
        if target is None:
            continue
        generated = HEADER + program
        compile(program, str(target), "exec")
        if args.check:
            if not target.exists() or target.read_text(encoding="utf-8") != generated:
                stale.append(str(target))
        else:
            target.write_text(generated, encoding="utf-8")
    if stale:
        raise SystemExit("stale generated validators: " + ", ".join(stale))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
