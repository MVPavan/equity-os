#!/usr/bin/env bash
#
# verify.sh — the deterministic gate of the v2 build pipeline.
#
#   docs/graph-loops/v2-build-pipeline.md — step 5, and the red-proof stand-in
#   for mutation testing described under "Mutation and its stand-in".
#
# It is the ONLY loop in the pipeline: the implementer runs against this script
# until it is green, and no model reviews anything before it passes. It costs
# zero model tokens, so the loop is free.
#
# Two modes:
#
#   scripts/verify.sh red  <slice> <pytest-target>...   capture the red proof
#   scripts/verify.sh gate <slice>                      the gate itself
#
# Contract: prints at most 8 status lines plus one ROUTE line. Tracebacks NEVER
# reach stdout — they go to the log file, because a red gate is the one path
# that can put 2,000 tokens of traceback into the orchestrator's context, where
# every later call in the session re-sends it.
#
# Exit codes double as the route, so a caller branches without parsing text:
#
#   0  PASS
#   1  IMPL      -> implementer     gate failure, or a changed line no test runs
#   2  CONTRACT  -> orchestrator    vacuous test, or a red proof that does not match
#   3  STOP      -> orchestrator    a security rail tripped; never work around
#   4  DIAGNOSE  -> diagnostician   too many failures to route by name

set -uo pipefail

readonly EXIT_PASS=0
readonly EXIT_IMPL=1
readonly EXIT_CONTRACT=2
readonly EXIT_STOP=3
readonly EXIT_DIAGNOSE=4

# Measured 2026-09-02 on a clean tree: 958 passed, 7 skipped. The skips are all
# opt-in live fetches or the absent optional OCR wheel. Going green by adding a
# skip is the cheapest way to defeat this gate, so the count is pinned.
readonly BASELINE_SKIPS="${VERIFY_BASELINE_SKIPS:-7}"

# A verbatim run of this many characters shared between a fixture and a real
# captured page means the capture was pasted in rather than synthesised.
readonly PASTE_MIN_LEN=60
readonly PASTE_MAX_PATTERNS=500

readonly REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly GATE_DIR="${REPO_ROOT}/scratchpad/gate"
readonly CAPTURE_DIR="${REPO_ROOT}/scratchpad/screener_discovery"

# Authoritative commands: .claude/project/verification.md. Keep them identical
# there and here — a gate that lints a different scope than the project claims
# is a gate that lies.
readonly SRC_SCOPE="src"
readonly TEST_SCOPE="tests/fundamentals"
readonly COV_SCOPE="src/fundamentals"

# The whole point of this script is that its output is bounded. A list of 37
# failing node IDs is the same context poisoning as a traceback, so names are
# capped here and the full set stays in the log.
readonly NAME_CAP=4
cap_names() {
  local -a names; local n
  IFS=$'\n' read -r -d '' -a names < <(printf '%s\n' "$@" | grep -v '^$'; printf '\0')
  n="${#names[@]}"
  [ "${n}" -eq 0 ] && return 0
  if [ "${n}" -le "${NAME_CAP}" ]; then
    printf '%s' "$(IFS=,; echo "${names[*]}")"
  else
    printf '%s (+%d more, see log)' \
      "$(IFS=,; echo "${names[*]:0:${NAME_CAP}}")" "$(( n - NAME_CAP ))"
  fi
}

usage() {
  cat >&2 <<'USAGE'
usage:
  scripts/verify.sh red  <slice> <pytest-target>...   capture the red proof
  scripts/verify.sh gate <slice>                      run the gate
USAGE
  exit 64
}

# --------------------------------------------------------------------------
# red — run the acceptance tests BEFORE the implementer exists and record that
# every one of them failed. A test that passes here asserts nothing the code
# controls, which is a gap in the contract, not a bug in the implementation.
# --------------------------------------------------------------------------
mode_red() {
  local slice="$1"; shift
  [ "$#" -ge 1 ] || usage

  mkdir -p "${GATE_DIR}"
  local proof="${GATE_DIR}/${slice}-red.json"
  local log="${GATE_DIR}/${slice}-red-$(date -u +%Y%m%dT%H%M%SZ).log"

  echo "verify.sh red ${slice} · $(date -u +%Y-%m-%dT%H:%MZ)"

  ( cd "${REPO_ROOT}" && uv run pytest "$@" -q --tb=no -rA ) >"${log}" 2>&1
  local outcomes
  outcomes="$(grep -E '^(PASSED|FAILED|ERROR) ' "${log}" || true)"

  if [ -z "${outcomes}" ]; then
    echo "collect        FAIL  no tests collected from: $*"
    echo "log            ${log#"${REPO_ROOT}/"}"
    echo "ROUTE: CONTRACT  the acceptance tests do not exist or do not collect"
    exit "${EXIT_CONTRACT}"
  fi

  local passed
  passed="$(cap_names "$(awk '/^PASSED /{print $2}' <<<"${outcomes}")")"
  local total red
  total="$(wc -l <<<"${outcomes}")"
  red="$(grep -cE '^(FAILED|ERROR) ' <<<"${outcomes}" || true)"

  VERIFY_ROOT="${REPO_ROOT}" VERIFY_SLICE="${slice}" VERIFY_TARGETS="$*" VERIFY_OUTCOMES="${outcomes}" \
    python3 - "${proof}" <<'PYEOF'
import hashlib, json, os, sys, datetime, pathlib

root = pathlib.Path(os.environ["VERIFY_ROOT"])
tests = []
for line in os.environ["VERIFY_OUTCOMES"].splitlines():
    # `pytest -rA` appends " - <error summary>" to a failing line; the node id
    # is the first whitespace-delimited field after the outcome.
    parts = line.split()
    if len(parts) < 2:
        continue
    tests.append({"nodeid": parts[1], "outcome": parts[0].lower()})

# Hash the acceptance files themselves. The gate later re-hashes them, which
# catches an implementer editing the contract even when the file is untracked
# and `git diff` would show nothing.
files = []
for nodeid in {t["nodeid"] for t in tests}:
    path = root / nodeid.split("::", 1)[0]
    if path.is_file():
        files.append({
            "path": str(path.relative_to(root)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
files = sorted({f["path"]: f for f in files}.values(), key=lambda f: f["path"])

pathlib.Path(sys.argv[1]).write_text(json.dumps({
    "slice": os.environ["VERIFY_SLICE"],
    "captured_at": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
    "targets": os.environ["VERIFY_TARGETS"].split(),
    "files": files,
    "tests": sorted(tests, key=lambda t: t["nodeid"]),
}, indent=2) + "\n")
PYEOF

  echo "collected      OK    ${total} acceptance tests"
  echo "proof          ${proof#"${REPO_ROOT}/"}"
  if [ -n "${passed}" ]; then
    echo "red-proof      FAIL  ${red}/${total} red; already passing: ${passed}"
    echo "log            ${log#"${REPO_ROOT}/"}"
    echo "ROUTE: CONTRACT  ${passed}"
    exit "${EXIT_CONTRACT}"
  fi
  echo "red-proof      OK    ${red}/${total} acceptance tests were red"
  echo "ROUTE: PASS      dispatch the implementer"
  exit "${EXIT_PASS}"
}

# --------------------------------------------------------------------------
# gate
# --------------------------------------------------------------------------
mode_gate() {
  local slice="$1"
  cd "${REPO_ROOT}" || exit "${EXIT_STOP}"

  mkdir -p "${GATE_DIR}"
  local ts log proof
  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  log="${GATE_DIR}/${slice}-${ts}.log"
  proof="${GATE_DIR}/${slice}-red.json"
  : >"${log}"

  local route="${EXIT_PASS}" reason=""
  local l_untouched l_red l_gate l_skips l_cov l_rails

  note() { printf '%s\n' "$1" >>"${log}"; }
  # Worse routes win. STOP is never downgraded by a later check.
  escalate() {
    local code="$1" why="$2"
    local rank_new rank_cur
    rank_new=$(rank "${code}"); rank_cur=$(rank "${route}")
    if [ "${rank_new}" -gt "${rank_cur}" ]; then route="${code}"; reason="${why}"; fi
  }
  rank() { case "$1" in 0) echo 0;; 1) echo 1;; 4) echo 2;; 2) echo 3;; 3) echo 4;; esac; }

  # 1 — the acceptance tests must be byte-identical to the red proof.
  if [ ! -f "${proof}" ]; then
    l_untouched="tests-untouched  SKIP  no red proof for slice '${slice}'"
    l_red="red-proof        FAIL  ${proof#"${REPO_ROOT}/"} missing"
    escalate "${EXIT_CONTRACT}" "run 'scripts/verify.sh red ${slice} <targets>' before the implementer"
  else
    local drift
    drift="$(python3 - "${proof}" <<'PYEOF'
import hashlib, json, pathlib, sys
proof = json.loads(pathlib.Path(sys.argv[1]).read_text())
for entry in proof["files"]:
    path = pathlib.Path(entry["path"])
    if not path.is_file():
        print(f"{entry['path']}:deleted")
    elif hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
        print(f"{entry['path']}:modified")
PYEOF
)"
    if [ -n "${drift}" ]; then
      l_untouched="tests-untouched  FAIL  $(tr '\n' ' ' <<<"${drift}")"
      escalate "${EXIT_CONTRACT}" "the implementer edited an acceptance test"
    else
      l_untouched="tests-untouched  OK    $(python3 -c 'import json,sys;print(len(json.load(open(sys.argv[1]))["files"]))' "${proof}") file(s) unchanged"
    fi
    local n_red n_tot
    n_tot="$(python3 -c 'import json,sys;print(len(json.load(open(sys.argv[1]))["tests"]))' "${proof}")"
    n_red="$(python3 -c 'import json,sys;print(sum(1 for t in json.load(open(sys.argv[1]))["tests"] if t["outcome"] in ("failed","error")))' "${proof}")"
    if [ "${n_red}" -ne "${n_tot}" ]; then
      l_red="red-proof        FAIL  only ${n_red}/${n_tot} were red"
      escalate "${EXIT_CONTRACT}" "a vacuous acceptance test"
    else
      l_red="red-proof        OK    ${n_red}/${n_tot} acceptance tests were red"
    fi
  fi

  # 2 — the gate. One pytest run, with coverage, so the loop stays cheap.
  local covjson="${GATE_DIR}/${slice}-${ts}-cov.json"
  note "=== pytest ==="
  uv run pytest "${TEST_SCOPE}" -q --tb=no -rA \
    "--cov=${COV_SCOPE}" "--cov-report=json:${covjson}" --cov-report= >>"${log}" 2>&1
  local failed n_failed n_skipped
  failed="$(cap_names "$(awk '/^(FAILED|ERROR) /{print $2}' "${log}")")"
  n_failed="$(grep -cE '^(FAILED|ERROR) ' "${log}" || true)"
  n_skipped="$(grep -cE '^SKIPPED ' "${log}" || true)"

  local lint_fail=""
  run_check() {
    local label="$1"; shift
    note "=== $* ==="
    if ! uv run "$@" >>"${log}" 2>&1; then
      lint_fail="${lint_fail}${lint_fail:+,}${label}"
    fi
  }
  run_check "ruff-check"  ruff check "${SRC_SCOPE}" "${TEST_SCOPE}"
  run_check "ruff-format" ruff format --check "${SRC_SCOPE}" "${TEST_SCOPE}"
  run_check "mypy"        mypy --strict "${SRC_SCOPE}"

  if [ "${n_failed}" -gt 0 ] || [ -n "${lint_fail}" ]; then
    local parts=""
    [ "${n_failed}" -gt 0 ] && parts="pytest ${n_failed} failed"
    [ -n "${lint_fail}" ] && parts="${parts}${parts:+; }${lint_fail}"
    l_gate="gate             FAIL  ${parts}"
    if [ "${n_failed}" -gt 3 ]; then
      escalate "${EXIT_DIAGNOSE}" "${n_failed} failures — too many to route by name"
    else
      escalate "${EXIT_IMPL}" "${failed:-${lint_fail}}"
    fi
  else
    l_gate="gate             OK    958-baseline suite, ruff, mypy --strict"
  fi

  # 3 — skips must not grow. Cheapest way to fake a green gate.
  if [ "${n_skipped}" -gt "${BASELINE_SKIPS}" ]; then
    l_skips="skips            FAIL  ${n_skipped} > baseline ${BASELINE_SKIPS}"
    escalate "${EXIT_CONTRACT}" "$(( n_skipped - BASELINE_SKIPS )) new skip(s)"
  else
    l_skips="skips            OK    ${n_skipped} <= baseline ${BASELINE_SKIPS}"
  fi

  # 4 — diff coverage: every line this slice changed must be executed by
  # something. Substitute 2 for mutation; catches the unexercised-path class.
  if [ ! -f "${covjson}" ]; then
    l_cov="diff-coverage    —     skipped, no coverage report (gate red?)"
  else
    local uncovered
    uncovered="$(python3 - "${covjson}" "${COV_SCOPE}" <<'PYEOF'
import json, pathlib, re, subprocess, sys, collections

covfile, scope = sys.argv[1], sys.argv[2]

def changed_lines() -> dict[str, set[int]]:
    out: dict[str, set[int]] = collections.defaultdict(set)
    diff = subprocess.run(
        ["git", "diff", "-U0", "HEAD", "--", scope],
        capture_output=True, text=True, check=False).stdout
    path = None
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
        elif line.startswith("@@") and path:
            m = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if m:
                start, count = int(m.group(1)), int(m.group(2) or 1)
                out[path].update(range(start, start + count))
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "--", scope],
        capture_output=True, text=True, check=False).stdout.split()
    for path in untracked:
        p = pathlib.Path(path)
        if p.suffix == ".py" and p.is_file():
            out[path].update(range(1, len(p.read_text().splitlines()) + 1))
    return out

cov = json.loads(pathlib.Path(covfile).read_text())["files"]
missed_by_file = {k: set(v["missing_lines"]) for k, v in cov.items()}

hits = []
for path, lines in sorted(changed_lines().items()):
    missed = missed_by_file.get(path)
    if missed is None:
        continue
    for line in sorted(lines & missed):
        hits.append(f"{path}:{line}")
print(" ".join(hits[:6]))
PYEOF
)"
    if [ -n "${uncovered}" ]; then
      l_cov="diff-coverage    FAIL  changed lines no test executes"
      escalate "${EXIT_IMPL}" "${uncovered}"
    else
      l_cov="diff-coverage    OK    every changed line in ${COV_SCOPE} is executed"
    fi
  fi

  # 5 — security rails. Any hit is terminal: it means private data or a secret
  # is about to be committed. Never routed to the implementer.
  local rails=""
  local tracked_private
  tracked_private="$(git ls-files scratchpad data 2>/dev/null | head -3 | paste -sd, -)"
  [ -n "${tracked_private}" ] && rails="${rails}${rails:+; }private path tracked: ${tracked_private}"

  local changed_files
  # scripts/verify.sh is excluded because it necessarily contains the very
  # patterns it greps for; uv.lock and .coverage are generated artifacts.
  changed_files="$(
    { git diff --name-only HEAD; git ls-files --others --exclude-standard; } \
      | sort -u \
      | grep -vE '^(scratchpad/|scripts/verify\.sh$|uv\.lock$|\.coverage)' || true
  )"

  if [ -n "${changed_files}" ]; then
    local abs
    abs="$(grep -IlE '(/home/[a-z]|/data/codes/)' ${changed_files} 2>/dev/null | head -3 | paste -sd, -)"
    [ -n "${abs}" ] && rails="${rails}${rails:+; }machine-local path in: ${abs}"

    local cookie
    cookie="$(grep -IlEi 'sessionid["'"'"':= ]+[A-Za-z0-9]{20,}' ${changed_files} 2>/dev/null | head -3 | paste -sd, -)"
    [ -n "${cookie}" ] && rails="${rails}${rails:+; }possible session cookie in: ${cookie}"

    local big py_files
    py_files="$(grep -E '\.py$' <<<"${changed_files}" || true)"
    big="$([ -n "${py_files}" ] && wc -l ${py_files} 2>/dev/null | awk '$1 > 800 && $2 != "total" {print $2}' | head -3 | paste -sd, -)"
    [ -n "${big}" ] && rails="${rails}${rails:+; }over 800 lines: ${big}"

    # Verbatim runs shared with a real captured page mean a capture was pasted
    # into a fixture instead of a synthetic value being written.
    if [ -d "${CAPTURE_DIR}" ]; then
      local pat pasted
      pat="$(mktemp)"
      grep -IhoE ".{${PASTE_MIN_LEN},}" ${changed_files} 2>/dev/null \
        | sed 's/^[[:space:]]*//' | sort -u | head -"${PASTE_MAX_PATTERNS}" >"${pat}"
      if [ -s "${pat}" ]; then
        pasted="$(grep -rlFf "${pat}" "${CAPTURE_DIR}" 2>/dev/null | head -2 | paste -sd, -)"
        [ -n "${pasted}" ] && rails="${rails}${rails:+; }fixture text matches private capture: ${pasted}"
      fi
      rm -f "${pat}"
    fi
  fi

  if [ -n "${rails}" ]; then
    l_rails="rails            STOP  ${rails}"
    escalate "${EXIT_STOP}" "${rails}"
  else
    l_rails="rails            OK    no private path, secret, or pasted capture"
  fi

  # ---- report: at most 8 status lines, then exactly one ROUTE line ----
  echo "verify.sh gate ${slice} · $(date -u +%Y-%m-%dT%H:%MZ)"
  echo "${l_untouched}"
  echo "${l_red}"
  echo "${l_gate}"
  echo "${l_skips}"
  echo "${l_cov}"
  echo "${l_rails}"
  echo "log              ${log#"${REPO_ROOT}/"}"
  case "${route}" in
    "${EXIT_PASS}")     echo "ROUTE: PASS      review may begin" ;;
    "${EXIT_IMPL}")     echo "ROUTE: IMPL      ${reason}" ;;
    "${EXIT_CONTRACT}") echo "ROUTE: CONTRACT  ${reason}" ;;
    "${EXIT_STOP}")     echo "ROUTE: STOP      ${reason}" ;;
    "${EXIT_DIAGNOSE}") echo "ROUTE: DIAGNOSE  ${reason}" ;;
  esac
  exit "${route}"
}

[ "$#" -ge 2 ] || usage
case "$1" in
  red)  shift; mode_red "$@" ;;
  gate) shift; mode_gate "$1" ;;
  *)    usage ;;
esac
