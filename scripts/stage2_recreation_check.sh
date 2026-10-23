#!/usr/bin/env bash
# Stage 2 recreation and fresh-instance check (plan D2, Task 8). Exits 0 only when every step passes.
# Works only on its own compose projects and data dirs under a mktemp root; every guard runs
# before the first lifecycle call, container cleanup is armed only after the guards pass, and
# cleanup never touches the live project or any volume. Every docker call is time-bounded.
set -euo pipefail
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)
cd "$REPO"
MAIN_DB=eqos_stage2_main
APAR=data/raw/watchlist/aparinds
PAYLOAD_OUT=${1:-}  # optional: where a passing run copies its reconciliation payload
die() { echo "stage2-check: FAIL: $*" >&2; exit 1; }
say() { echo "stage2-check: $*" >&2; }
hex() { od -An -N"$1" -tx1 /dev/urandom | tr -d ' \n'; }
dotenv() { grep -E "^$1=" .env | tail -n1 | cut -d= -f2-; }  # read, never sourced
sha() { sha256sum "$1" | cut -d' ' -f1; }
# Run a child with only PATH, HOME and one instance's env file (process env outranks .env).
# Values are exported by builtins in a subshell, so no credential reaches any process argv.
in_env() {
  (
    for name in $(compgen -e); do
      case "$name" in PATH | HOME) ;; *) unset "$name" 2>/dev/null || true ;; esac
    done
    while IFS= read -r line; do export "${line?}"; done <"$ROOT/$1.env"
    shift
    "$@"
  )
}
# Run "$2..." killed after $1 seconds; a timeout is reported, never silent.
bounded() {
  local secs=$1 status=0
  shift
  timeout -k 10 "$secs" "$@" || status=$?
  [ "$status" != 124 ] || say "TIMEOUT after ${secs}s: $1 ${2:-}"
  return "$status"
}
dc() {
  in_env "$1" bounded "${DC_TIMEOUT:-120}" \
    docker compose -p "$1" --env-file "$ROOT/$1.env" -f compose.yaml "${@:2}"
}

# Guard 1: owned root, outside the live data dir and the repo.
ROOT=$(mktemp -d -t eqos-stage2.XXXXXXXX)
TOKEN=$(hex 16)
printf '%s\n' "$TOKEN" >"$ROOT/.owner"
P="eqos-stage2-${TOKEN:0:8}" F="eqos-stage2-${TOKEN:0:8}-fresh"
# Until every guard passes nothing has started and the owned dirs hold only this script's files.
trap 'status=$?; rm -rf -- "$ROOT"; say "exit $status"' EXIT
cleanup() {
  local status=$?
  for project in "$P" "$F"; do
    dc "$project" down >/dev/null 2>&1 || say "down $project failed"
  done
  if [ "$(cat "$ROOT/.owner" 2>/dev/null)" = "$TOKEN" ]; then
    in_env "$P" bounded 120 docker run --rm -v "$ROOT:/owned" postgres:18.6 sh -c \
      '[ "$(cat /owned/.owner)" = "$1" ] && rm -rf /owned/data /owned/data-fresh' sh "$TOKEN" \
      >/dev/null 2>&1 || say "container-owned data dirs not removed under $ROOT"
    rm -rf "$ROOT"
  fi
  say "exit $status"
  exit "$status"
}
[ "$(realpath "$ROOT")" = "$ROOT" ] || die "owned root is an alias"
LIVE_DATA=$(dotenv EQOS_PG_DATA_DIR) LIVE_PORT=$(dotenv EQOS_PG_PORT)
[ -n "$LIVE_DATA" ] && [ -n "$LIVE_PORT" ] || die ".env lacks EQOS_PG_DATA_DIR or EQOS_PG_PORT"
LIVE_DATA=$(realpath -m "$LIVE_DATA")
overlaps() { case "$1/" in "$2"/*) return 0 ;; esac; case "$2/" in "$1"/*) return 0 ;; esac; return 1; }
for dir in "$ROOT" "$ROOT/data" "$ROOT/data-fresh"; do
  for other in "$LIVE_DATA" "$REPO"; do overlaps "$dir" "$other" && die "$dir overlaps $other"; done
done

# Guard 2: free loopback ports, distinct from the live port and from each other.
free_port() { python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1])'; }
PORT=$(free_port) FRESH_PORT=$(free_port)
[ "$PORT" != "$LIVE_PORT" ] && [ "$FRESH_PORT" != "$LIVE_PORT" ] && [ "$PORT" != "$FRESH_PORT" ] ||
  die "port collision"

# Guard 3: a complete 0600 env file per instance, with throwaway credentials never printed, and
# a 0700 secrets dir of randomized group-role, admin and migrator logins (both instances share
# the admin and migrator ones), so ~/.secrets is never read.
mkdir -m 700 "$ROOT/secrets"
ADMIN_PASSWORD=$(hex 24)
(umask 077 && printf 'eqos_stage2_admin:%s\n' "$ADMIN_PASSWORD" >"$ROOT/secrets/eqos_admin.login" &&
  printf 'eqos_migrator:%s\n' "$(hex 24)" >"$ROOT/secrets/eqos_migrator.login")
for file in $(uv run python -c 'from fundamentals.pg.role_secrets import LOGIN_SUFFIX
from fundamentals.pg.settings import GROUP_ROLES
print(*(group + LOGIN_SUFFIX for group in GROUP_ROLES.values()))'); do
  (umask 077 && printf '%s_stage2:%s\n' "${file%.login}" "$(hex 24)" >"$ROOT/secrets/$file")
done
write_env() {
  (umask 077 && cat >"$ROOT/$1.env" <<EOF
EQOS_PG_HOST=127.0.0.1
EQOS_PG_PORT=$2
EQOS_PG_DB=$MAIN_DB
EQOS_PG_USER=eqos_stage2_admin
EQOS_PG_PASSWORD=$ADMIN_PASSWORD
EQOS_PG_RUNTIME_PASSWORD=$(hex 24)
EQOS_PG_TEST_DB_PREFIX=eqos_test_
EQOS_PG_CONNECT_TIMEOUT_S=5
EQOS_PG_STATEMENT_TIMEOUT_MS=30000
EQOS_PG_POOL_MIN_SIZE=1
EQOS_PG_POOL_MAX_SIZE=4
EQOS_PG_DATA_DIR=$3
EQOS_SECRETS_DIR=$ROOT/secrets
EOF
  )
  mkdir -m 755 "$3"  # the postgres user must traverse the bind mount, as on the live dir
  touch "$3/.eqos-host-mount"  # compose refuses a data dir without it
}
write_env "$P" "$PORT" "$ROOT/data"
write_env "$F" "$FRESH_PORT" "$ROOT/data-fresh"

# Guard 4: the resolved compose config and PgSettings equal the env file, before any `up`.
validate() {
  dc "$1" config --format json | python3 -c '
import json, sys
config, (name, port, data, db) = json.load(sys.stdin), sys.argv[1:]
pg = config["services"]["postgres"]
(published,), (volume,) = pg["ports"], pg["volumes"]
assert config["name"] == name, "project name"
assert (published["host_ip"], str(published["published"])) == ("127.0.0.1", port), "port"
assert volume["source"] == data, "bind source"
assert pg["environment"]["POSTGRES_DB"] == db, "POSTGRES_DB"' "$1" "$2" "$3" "$MAIN_DB" ||
    die "resolved compose config of $1"
  [ "$(in_env "$1" uv run python -c 'from fundamentals.pg.settings import PgSettings
s = PgSettings(); print(s.host, s.port, s.db, s.test_db_prefix)')" = "127.0.0.1 $2 $MAIN_DB eqos_test_" ] ||
    die "resolved PgSettings of $1"
}
validate "$P" "$PORT" "$ROOT/data"
validate "$F" "$FRESH_PORT" "$ROOT/data-fresh"
trap cleanup EXIT  # every guard passed: cleanup of the two owned projects is now armed

up() {
  DC_TIMEOUT=240 dc "$1" up -d --wait >/dev/null 2>&1 ||
    { dc "$1" logs --tail 40 >&2 || true; die "$1 is not healthy within 240s"; }
  [ "$(dc "$1" port postgres 5432)" = "127.0.0.1:$2" ] || die "$1 is not published on 127.0.0.1:$2"
}

# 1. Up, loopback only.
say "up $P on 127.0.0.1:$PORT"
up "$P" "$PORT"

# 2. Rehearse runbook steps 6-10 on a rehearsal database and copies under the owned root.
D=$(in_env "$P" uv run fundamentals db create-test --suffix rehearsal)
renv() { in_env "$P" env "EQOS_PG_DB=$D" "$@"; }
fundamentals() { renv uv run fundamentals "$@"; }
mkdir -m 700 "$ROOT/legacy" "$ROOT/inputs" "$ROOT/snap"
cp data/store/aparinds.sqlite "$ROOT/legacy/aparinds.sqlite"
cp -r "$APAR/nse" "$APAR/nse_pdf" "$ROOT/inputs/"
LEGACY_SHA=$(sha data/store/aparinds.sqlite)
[ "$(sha "$ROOT/legacy/aparinds.sqlite")" = "$LEGACY_SHA" ] || die "legacy copy SHA-256"
approve() {
  printf 'approval: {reviewer: test-fixture, verdict: APPROVE, date: %s, payload_sha256: "%s"}\n' \
    "$(date -u +%F)" "$(sha "$1")" >>"$1"
}
M="$ROOT/legacy_import_manifest.yaml"
printf 'files:\n- label: aparinds\n  path: %s\n  sha256: %s\nsnapshot_root: %s\n' \
  "$ROOT/legacy/aparinds.sqlite" "$LEGACY_SHA" "$ROOT/snap" >"$M"
approve "$M"
fundamentals db bootstrap >/dev/null
fundamentals db migrate >/dev/null
renv uv run python -c 'import psycopg
from pathlib import Path
from fundamentals.pg.identity_seed import load_issuer_identity, seed_issuer_identity
from fundamentals.pg.settings import PgRole, PgSettings
with psycopg.connect(PgSettings().conninfo(PgRole.RUNTIME)) as conn:
    seed_issuer_identity(conn, load_issuer_identity(Path("config/identity/aparinds.yaml")))'
for quarter_end in FY26_Q2:2025-09-30 FY26_Q3:2025-12-31 FY26_Q4:2026-03-31 FY27_Q1:2026-06-30; do
  quarter=${quarter_end%%:*} ingested=0
  fundamentals evidence ingest --retrieval-manifest "$APAR/retrieval-manifest-v2.json" \
    --issuer APARINDS --quarter "$quarter" --period-end "${quarter_end#*:}" --basis consolidated \
    --raw-root "$ROOT/inputs" --snapshot-root "$ROOT/snap" --member xbrl=xbrl-consolidated \
    --member pdf=results --issuer-config "config/aparinds-$(echo "$quarter" | tr 'A-Z_' 'a-z-').yaml" \
    >/dev/null || ingested=$?
  # Bindings need only the registered originals: other quarters may be INCOMPLETE (4).
  [ "$ingested" = 0 ] || { [ "$quarter" != FY26_Q2 ] && [ "$ingested" = 4 ]; } ||
    die "evidence ingest $quarter exit $ingested"
done
compared=0
fundamentals compare run --entity APARINDS --period-end 2025-09-30 --basis consolidated >/dev/null ||
  compared=$?
[ "$compared" = 0 ] || [ "$compared" = 3 ] || die "compare run exit $compared"
fundamentals legacy preflight --manifest "$M" --out "$ROOT/preflight.yaml" >/dev/null
approve "$ROOT/preflight.yaml"
fundamentals legacy import --manifest "$M" --preflight "$ROOT/preflight.yaml" >/dev/null
fundamentals legacy reconcile --manifest "$M" --out "$ROOT/reconciliation.yaml" >/dev/null
cp "$ROOT/reconciliation.yaml" "$ROOT/reconciliation.payload"
approve "$ROOT/reconciliation.yaml"
legacy() { fundamentals legacy "$1" --manifest "$M" --report "$ROOT/reconciliation.yaml" >/dev/null; }
legacy cutover
legacy rollback
fundamentals legacy status --manifest "$M" | grep -q ROLLED_BACK || die "status after rollback"
fundamentals legacy reconcile --manifest "$M" --out "$ROOT/reconcile-again.yaml" >/dev/null
cmp -s "$ROOT/reconcile-again.yaml" "$ROOT/reconciliation.payload" || die "re-reconcile differs"
legacy cutover
legacy reopen
# `fundamentals run` is not rehearsed here: a shell run of Q2 FY26 refuses sources registered
# after the quarter's knowledge cutoff (the committed approved-intake proof records exactly that
# refusal), and this script never synthesizes possession evidence. Step 6's e2e covers the run.
[ "$(sha data/store/aparinds.sqlite)" = "$LEGACY_SHA" ] || die "production SQLite changed"
say "rehearsal passed on $D"

# 3-5. Identical deterministic inventory across down/up.
inventory() {
  fundamentals legacy reconcile --manifest "$M" --out "$ROOT/R$1.yaml" >/dev/null
  fundamentals db backup --out "$ROOT/B$1" --snapshot-root "$ROOT/snap" | cut -f2
}
B1=$(inventory 1)
dc "$P" down >/dev/null || die "down $P"
up "$P" "$PORT"
B2=$(inventory 2)
cmp -s "$ROOT/R1.yaml" "$ROOT/R2.yaml" || die "reconciliation differs after down/up"
in_env "$P" uv run python -c 'import sys, yaml
a, b = (yaml.safe_load(open(f"{path}/manifest.yaml")) for path in sys.argv[1:])
assert (a["table_counts"], a["captures"]) == (b["table_counts"], b["captures"])' "$B1" "$B2" ||
  die "backup inventory differs after down/up"
say "inventory identical across down/up"

# 6. The e2e on this instance (harness main database eqos_stage2_main).
in_env "$P" uv run pytest -q -p no:cacheprovider tests/fundamentals/test_data_stage2_e2e.py >&2

# 7. Fresh instance: restore B1 with replay.
say "up $F on 127.0.0.1:$FRESH_PORT"
up "$F" "$FRESH_PORT"
in_env "$F" uv run fundamentals db bootstrap >/dev/null  # group roles and the purge login
mkdir -m 700 "$ROOT/snap-fresh"  # empty; the store anchors an existing root under its owner
in_env "$F" uv run fundamentals db restore --set "$B1" --database "eqos_test_fresh_$(hex 6)" \
  --snapshot-root "$ROOT/snap-fresh" --live-snapshot-root "$ROOT/snap" --replay-runs >/dev/null ||
  die "fresh-instance restore"
[ -z "$PAYLOAD_OUT" ] || cp -- "$ROOT/reconciliation.payload" "$PAYLOAD_OUT"
say "PASS"
