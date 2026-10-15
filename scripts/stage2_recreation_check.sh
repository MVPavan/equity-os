#!/usr/bin/env bash
# Stage 2 recreation and fresh-instance check (plan D2, Task 8). Exits 0 only when every step passes.
# Works only on its own compose projects and data dirs under a mktemp root; every guard runs
# before the first lifecycle call, and cleanup never touches the live project or any volume.
set -euo pipefail
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)
cd "$REPO"
MAIN_DB=eqos_stage2_main
APAR=data/raw/watchlist/aparinds
LEDGER=data/ledger/aparinds-management-ledger.json
STAGE2=tests/fundamentals/fixtures/data_foundation/stage2_manifest.yaml
die() { echo "stage2-check: FAIL: $*" >&2; exit 1; }
say() { echo "stage2-check: $*" >&2; }
hex() { od -An -N"$1" -tx1 /dev/urandom | tr -d ' \n'; }
dotenv() { grep -E "^$1=" .env | tail -n1 | cut -d= -f2-; }  # read, never sourced
sha() { sha256sum "$1" | cut -d' ' -f1; }
# Run a child with only PATH, HOME and one instance's env file (process env outranks .env).
in_env() {
  local vars
  mapfile -t vars <"$ROOT/$1.env"
  shift
  env -i "PATH=$PATH" "HOME=$HOME" "${vars[@]}" "$@"
}
dc() { in_env "$1" docker compose -p "$1" --env-file "$ROOT/$1.env" -f compose.yaml "${@:2}"; }

# Guard 1: owned root, outside the live data dir and the repo.
ROOT=$(mktemp -d -t eqos-stage2.XXXXXXXX)
TOKEN=$(hex 16)
printf '%s\n' "$TOKEN" >"$ROOT/.owner"
P="eqos-stage2-${TOKEN:0:8}" F="eqos-stage2-${TOKEN:0:8}-fresh"
cleanup() {
  local status=$?
  for project in "$P" "$F"; do
    [ -f "$ROOT/$project.validated" ] && dc "$project" down >/dev/null 2>&1 || true
  done
  if [ "$(cat "$ROOT/.owner" 2>/dev/null)" = "$TOKEN" ]; then
    docker run --rm -v "$ROOT:/owned" postgres:18.6 sh -c \
      '[ "$(cat /owned/.owner)" = "$1" ] && rm -rf /owned/data /owned/data-fresh' sh "$TOKEN" \
      >/dev/null 2>&1 || true
    rm -rf "$ROOT"
  fi
  say "exit $status"
  exit "$status"
}
trap cleanup EXIT
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

# Guard 3: a complete 0600 env file per instance, with throwaway credentials never printed.
write_env() {
  (umask 077 && cat >"$ROOT/$1.env" <<EOF
EQOS_PG_HOST=127.0.0.1
EQOS_PG_PORT=$2
EQOS_PG_DB=$MAIN_DB
EQOS_PG_USER=eqos_stage2_admin
EQOS_PG_PASSWORD=$(hex 24)
EQOS_PG_MIGRATOR_PASSWORD=$(hex 24)
EQOS_PG_RUNTIME_PASSWORD=$(hex 24)
EQOS_PG_TEST_DB_PREFIX=eqos_test_
EQOS_PG_CONNECT_TIMEOUT_S=5
EQOS_PG_STATEMENT_TIMEOUT_MS=30000
EQOS_PG_POOL_MIN_SIZE=1
EQOS_PG_POOL_MAX_SIZE=4
EQOS_PG_DATA_DIR=$3
EOF
  )
  mkdir -m 755 "$3"  # the postgres user must traverse the bind mount, as on the live dir
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
  touch "$ROOT/$1.validated"  # cleanup runs `down` only on a validated project
}
validate "$P" "$PORT" "$ROOT/data"
validate "$F" "$FRESH_PORT" "$ROOT/data-fresh"

up() {
  dc "$1" up -d --wait >/dev/null 2>&1 || { dc "$1" logs --tail 40 >&2; die "$1 is not healthy"; }
  [ "$(dc "$1" port postgres 5432)" = "127.0.0.1:$2" ] || die "$1 is not published on 127.0.0.1:$2"
}

# 1. Up, loopback only.
say "up $P on 127.0.0.1:$PORT"
up "$P" "$PORT"

# 2. Rehearse runbook steps 6-10 on a rehearsal database and copies under the owned root.
D=$(in_env "$P" uv run fundamentals db create-test --suffix rehearsal)
renv() { in_env "$P" env "EQOS_PG_DB=$D" "$@"; }
fundamentals() { renv uv run fundamentals "$@"; }
mkdir -m 700 "$ROOT/legacy" "$ROOT/config" "$ROOT/ledger" "$ROOT/inputs" "$ROOT/snap"
cp data/store/aparinds.sqlite "$ROOT/legacy/aparinds.sqlite"
cp -r "$APAR/nse" "$APAR/nse_pdf" "$ROOT/inputs/"
LEGACY_SHA=$(sha data/store/aparinds.sqlite) LEDGER_SHA=$(sha "$LEDGER")
[ "$(sha "$ROOT/legacy/aparinds.sqlite")" = "$LEGACY_SHA" ] || die "legacy copy SHA-256"
approve() {
  printf 'approval: {reviewer: test-fixture, verdict: APPROVE, date: %s, payload_sha256: "%s"}\n' \
    "$(date -u +%F)" "$(sha "$1")" >>"$1"
}
M="$ROOT/legacy_import_manifest.yaml"
printf 'files:\n- label: aparinds\n  path: %s\n  sha256: %s\nsnapshot_root: %s\n' \
  "$ROOT/legacy/aparinds.sqlite" "$LEGACY_SHA" "$ROOT/snap" >"$M"
approve "$M"
renv uv run python - "$ROOT" "sqlite-${LEGACY_SHA:0:16}" <<'PY'
# The issuer config copy: repo-absolute paths, the copied store, a fresh ledger (the production
# ledger is past Q2 FY26, so a replay refuses a copy of it) and the imported store id.
import sys
from pathlib import Path
import yaml
root, store = Path(sys.argv[1]), sys.argv[2]
repo, name = Path.cwd(), "aparinds-fy26-q2.yaml"
body = yaml.safe_load((repo / "config" / name).read_text(encoding="utf-8"))
body["raw_dir"] = str(repo / body["raw_dir"])
body["xbrl"]["local_path"] = str(repo / body["xbrl"]["local_path"])
for comparator in body["comparators"].values():
    comparator["local_path"] = str(repo / comparator["local_path"])
body |= {"store_db": str(root / "legacy/aparinds.sqlite"), "fact_store_id": store,
         "ledger_path": str(root / "ledger/ledger.json")}
(root / "config" / name).write_text(yaml.safe_dump(body, allow_unicode=True), encoding="utf-8")
PY
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
renv uv run python - "$ROOT" "$STAGE2" <<'PY'
# `fundamentals run` through the CLI composition root. A shell `run` refuses a retrieval after
# the quarter cutoff without an approved intake, so this admits the e2e's trusted fixture proof.
import json, sys
from pathlib import Path
import pytest, yaml
sys.path.insert(0, "tests/fundamentals")
from temporal_fixture_support import install_trusted_fixture_cli
from fundamentals.api.cli import main
root, manifest = Path(sys.argv[1]), yaml.safe_load(Path(sys.argv[2]).read_text(encoding="utf-8"))
install_trusted_fixture_cli(pytest.MonkeyPatch())
out, md = root / "run.json", root / "run.md"
argv = ["run", "--issuer", "APARINDS", "--quarter", "Q2-FY26", "--out", str(md),
        "--config", str(root / "config/aparinds-fy26-q2.yaml"), "--out-json", str(out)]
assert main(argv) == 0
results = {c["label"]: c["result"] for c in json.loads(out.read_text())["calculations"]}
for line in manifest["consumer_report"]:
    if line["line"] in results:
        assert results[line["line"]] == line.get("rendered", line.get("v")), line["line"]
    else:
        assert f"| {line['line']} | {line['v']} |" in md.read_text(encoding="utf-8"), line["line"]
PY
[ "$(sha data/store/aparinds.sqlite)" = "$LEGACY_SHA" ] || die "production SQLite changed"
[ "$(sha "$LEDGER")" = "$LEDGER_SHA" ] || die "production ledger changed"
say "rehearsal passed on $D"

# 3-5. Identical deterministic inventory across down/up.
inventory() {
  fundamentals legacy reconcile --manifest "$M" --out "$ROOT/R$1.yaml" >/dev/null
  fundamentals db backup --out "$ROOT/B$1" --snapshot-root "$ROOT/snap" | cut -f2
}
B1=$(inventory 1)
dc "$P" down >/dev/null
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
mkdir -m 700 "$ROOT/snap-fresh"  # empty; the store anchors an existing root under its owner
in_env "$F" uv run fundamentals db restore --set "$B1" --database "eqos_test_fresh_$(hex 6)" \
  --snapshot-root "$ROOT/snap-fresh" --replay-runs >/dev/null || die "fresh-instance restore"
say "PASS"
