#!/usr/bin/env bash
# Run the core exit/governance/quality gates and the approved pilot exit when built.
# Registry authority: docs/workstreams/data-foundation/{core,roadmap}.md,
# docs/backend-roadmap.md and plans/D1b.md Task 12. PASS here does not close Beads
# epics or substitute for their required independent review/approval records.
set -uo pipefail

readonly REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# PREP-8 must register the actual approved pilot exit here. No path is approved yet.
readonly PILOT_TARGET=""

if [ "$#" -ne 0 ]; then
  printf 'usage: scripts/verify_project.sh\n' >&2
  exit 64
fi

mkdir -p "${REPO_ROOT}/scratchpad" || exit 1
LOG_DIR="$(mktemp -d "${REPO_ROOT}/scratchpad/project-verification.XXXXXX")" || exit 1
readonly LOG_DIR
failed=0
not_built=0
part=0

run_command() {
  local label="$1"
  shift
  part=$((part + 1))
  local log="${LOG_DIR}/${part}.log"
  if (cd "${REPO_ROOT}" && "$@") >"${log}" 2>&1; then
    printf '%s | PASS | %s\n' "${label}" "${log#"${REPO_ROOT}/"}"
  else
    local status=$?
    failed=$((failed + 1))
    printf '%s | FAIL | exit %s; %s\n' "${label}" "${status}" "${log#"${REPO_ROOT}/"}"
  fi
}

run_test() {
  local label="$1" target="$2"
  if [ -z "${target}" ]; then
    not_built=$((not_built + 1))
    printf '%s | NOT BUILT | no approved exit test path\n' "${label}"
  elif [ ! -f "${REPO_ROOT}/${target}" ]; then
    not_built=$((not_built + 1))
    printf '%s | NOT BUILT | missing %s\n' "${label}" "${target}"
  else
    run_command "${label}" uv run pytest "${target}"
  fi
}

# Explicit required slots prevent unbuilt phases disappearing through discovery.
run_test "D1a" "tests/fundamentals/test_compare_tracer.py"
run_test "D1b" "tests/fundamentals/test_data_stage1_e2e.py"
run_test "D2" "tests/fundamentals/test_data_stage2_e2e.py"
run_test "D3" "tests/fundamentals/test_ledger_stage1_e2e.py"
run_test "D3 export" "tests/fundamentals/test_ledger_export.py"
run_test "D4" "tests/fundamentals/test_ledger_stage2_e2e.py"
run_test "D5" "tests/fundamentals/test_ledger_stage3_e2e.py"
run_test "D6" "tests/fundamentals/test_data_stage4_e2e.py"
run_test "D7" "tests/fundamentals/test_ledger_stage4_e2e.py"
run_test "D8" "tests/fundamentals/test_data_stage3_e2e.py"
run_test "D9" "tests/fundamentals/test_ledger_stage5_e2e.py"
run_test "Frozen manifests" "tests/fundamentals/test_frozen_manifests.py"
run_test "Amendment records" "tests/fundamentals/test_amendment_records.py"
run_test "Pilot" "${PILOT_TARGET}"

# Authoritative full scope: .codex/project/verification.md. No PG/retained exclusions.
run_command "Pytest" uv run pytest tests/fundamentals
run_command "Mypy" uv run mypy --strict src
run_command "Ruff" uv run ruff check src tests/fundamentals
run_command "Ruff format" uv run ruff format --check src tests/fundamentals

if [ "${failed}" -ne 0 ] || [ "${not_built}" -ne 0 ]; then
  printf 'Project incomplete: %s failed, %s not built.\n' "${failed}" "${not_built}"
  exit 1
fi
printf 'Every required exit, governance and quality check passed.\n'
