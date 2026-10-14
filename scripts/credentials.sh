# Source this file to export the vendor credentials the fundamentals CLI reads:
#   source scripts/credentials.sh
# Values live outside the repo, one value per file, mode 0600, in ${EQOS_SECRETS_DIR:-~/.secrets}:
#   screener_session -> SCREENER_SESSION_COOKIE  (Screener "sessionid" cookie value)
#   tijori_session   -> TIJORI_SESSION_COOKIE    (Tijori session cookie value)
#   upstox_token     -> UPSTOX_ANALYTICS_TOKEN   (Upstox Analytics Token)
# Stale Screener/Tijori sessions are refreshed first. Missing files are reported by name only;
# values are never printed.

_eqos_secrets="${EQOS_SECRETS_DIR:-$HOME/.secrets}"
# Re-login (scripts/refresh_sessions.py) when a session cookie is missing or over 6 days old.
if [ ! -s "${_eqos_secrets}/screener_session" ] || [ ! -s "${_eqos_secrets}/tijori_session" ] ||
  [ -n "$(find "${_eqos_secrets}" -maxdepth 1 -name '*_session' -mtime +6)" ]; then
  _eqos_repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  uv run --project "${_eqos_repo}" --group login python "${_eqos_repo}/scripts/refresh_sessions.py" >&2 ||
    echo "credentials: session refresh failed; see output above" >&2
fi
for _eqos_pair in screener_session:SCREENER_SESSION_COOKIE tijori_session:TIJORI_SESSION_COOKIE upstox_token:UPSTOX_ANALYTICS_TOKEN; do
  _eqos_file="${_eqos_secrets}/${_eqos_pair%%:*}"
  if [ -r "${_eqos_file}" ]; then
    export "${_eqos_pair##*:}=$(tr -d '\r\n' <"${_eqos_file}")"
  else
    echo "credentials: missing ${_eqos_file}" >&2
  fi
done
unset _eqos_secrets _eqos_pair _eqos_file _eqos_repo
