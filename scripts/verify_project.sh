#!/usr/bin/env bash
# Run the core exit/governance/quality gates and the approved pilot exit when built.
# Registry authority: docs/workstreams/data-foundation/{core,roadmap}.md,
# docs/backend-roadmap.md and plans/D1b.md Task 12. PASS here does not close Beads
# epics or substitute for their required independent review/approval records.
set -uo pipefail

readonly REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# The pilot exit fixed by docs/plans/PREP-7.md (Decision 8); NOT BUILT until eqos-4j2.8 lands it.
readonly PILOT_TARGET="tests/equity_os/interface/workflows/test_pilot_e2e.py"

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
run_test "D1a" "tests/equity_os/verification/comparison/test_compare_tracer.py"
run_test "D1b" "tests/equity_os/interface/workflows/test_data_stage1_e2e.py"
run_test "D2" "tests/equity_os/interface/workflows/test_data_stage2_e2e.py"
run_test "D3" "tests/equity_os/interface/workflows/test_ledger_stage1_e2e.py"
run_test "D3 export" "tests/equity_os/publication/approval/test_ledger_export.py"
run_test "D4" "tests/equity_os/interface/workflows/test_ledger_stage2_e2e.py"
run_test "D5" "tests/equity_os/interface/workflows/test_ledger_stage3_e2e.py"
run_test "D6" "tests/equity_os/interface/workflows/test_data_stage4_e2e.py"
run_test "D7" "tests/equity_os/interface/workflows/test_ledger_stage4_e2e.py"
run_test "D8" "tests/equity_os/interface/workflows/test_data_stage3_e2e.py"
run_test "D9" "tests/equity_os/interface/workflows/test_ledger_stage5_e2e.py"
run_test "Frozen manifests" "tests/equity_os/interface/workflows/test_frozen_manifests.py"
run_test "Amendment records" "tests/equity_os/interface/workflows/test_amendment_records.py"
run_test "Pilot" "${PILOT_TARGET}"

# Authoritative full scope: .codex/project/verification.md. No PG/retained exclusions.
run_command "Pytest" uv run pytest tests/equity_os
run_command "Mypy" uv run mypy --strict equity_os
run_command "Ruff" uv run ruff check equity_os tests/equity_os
run_command "Ruff format" uv run ruff format --check equity_os tests/equity_os
# Live DB (bead eqos-px2): tests above use only eqos_test_* databases; this reads EQOS_PG_DB.
run_command "Live DB" uv run eqos db check-live

if [ "${failed}" -ne 0 ] || [ "${not_built}" -ne 0 ]; then
  printf 'Project incomplete: %s failed, %s not built.\n' "${failed}" "${not_built}"
  exit 1
fi
printf 'Every required exit, governance and quality check passed.\n'
