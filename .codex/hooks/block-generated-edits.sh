#!/usr/bin/env bash
# PreToolUse(apply_patch) guard. Blocks hand-edits to bd-generated tracking mirrors.
set -euo pipefail

INPUT=$(cat)

if command -v jq >/dev/null 2>&1; then
  FILE_PATH=$(printf '%s' "$INPUT" | jq -r '
    if (.tool_input | type) == "object"
    then (.tool_input.file_path // .tool_input.path // empty)
    else empty
    end')
  PATCH_COMMAND=$(printf '%s' "$INPUT" | jq -r '
    if (.tool_input | type) == "string" then .tool_input
    elif (.tool_input | type) == "object" then
      (.tool_input.command // .tool_input.patch // .tool_input.input // empty)
    else empty
    end')
else
  FILE_PATH=$(printf '%s' "$INPUT" | grep -o '"file_path":"[^"]*"' | sed 's/"file_path":"//;s/"$//' || true)
  PATCH_COMMAND=$(printf '%s' "$INPUT" | sed -n 's/.*"command":"\([^"]*\)".*/\1/p' || true)
fi

is_generated_path() {
  printf '%s\n' "$1" | grep -qE 'docs/workstreams/(.+/tracking/[^/]+\.md|(status|ideas|backlog)\.md)$'
}

block_path() {
  echo "BLOCKED: '$1' is a bd-generated workstream mirror. Update bd, then regenerate it with the project renderer. Do not hand-edit generated mirrors." >&2
  exit 2
}

[ -n "${FILE_PATH:-}" ] && is_generated_path "$FILE_PATH" && block_path "$FILE_PATH"

while IFS= read -r path; do
  [ -z "${path:-}" ] && continue
  is_generated_path "$path" && block_path "$path"
done <<EOF
$(printf '%s\n' "${PATCH_COMMAND:-}" | sed -nE \
  -e 's/^\*\*\* (Add|Update|Delete) File: (.*)$/\2/p' \
  -e 's/^\*\*\* Move to: (.*)$/\1/p')
EOF

exit 0
