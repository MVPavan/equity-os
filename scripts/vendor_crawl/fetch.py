"""Polite fetch gateway shared by every vendor-surface crawler (run with python3 -I).

usage: python3 -I scripts/vendor_crawl/fetch.py <crawler-id> <url>

- GET only, to www.screener.in or www.tijorifinance.com. Redirects are recorded, never followed.
- One global gap per site across all crawlers (a file lock plus a last-request time).
- A daily cap per site. Any 429, 503, 403 or login redirect writes STOP-<site>, after which
  every later fetch to that site refuses until the orchestrator removes the file.
- Identical URLs come from the shared cache for the current UTC date (cache/<date>/<site>/), so each
  day's run fetches fresh. Crawlers must not list or read the cache directly.
- Prints one JSON line with status, size, sha256, content type, cached flag and the body path.
  Never prints cookies or bodies.
"""

import fcntl
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

# Runtime state (cache, request log, STOP files) stays in the gitignored scratchpad.
ROOT = Path(__file__).resolve().parents[2] / "scratchpad" / "vendor-crawl"
SITES = {"www.screener.in": "screener", "www.tijorifinance.com": "tijori"}
GAP_SECONDS = 8.0
DAILY_CAP = 1200
MAX_BYTES = 32 * 1024 * 1024
STOP_STATUSES = {403, 429, 503}
LOGIN_MARKERS = ("/login", "/accounts/login", "/register", "/account/signin", "/signin")
SECRETS = Path.home() / ".secrets"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return None


def emit(**fields: object) -> None:
    print(json.dumps(fields, sort_keys=True))


def main() -> int:
    crawler, url = sys.argv[1], sys.argv[2]
    host = urlsplit(url).hostname or ""
    site = SITES.get(host)
    if site is None or urlsplit(url).scheme != "https":
        emit(refused="host not allowed", url=url)
        return 2
    key = hashlib.sha256(url.encode()).hexdigest()
    cache = ROOT / "cache" / datetime.now(UTC).date().isoformat() / site
    cache.mkdir(parents=True, exist_ok=True)
    meta_path, body_path = cache / f"{key}.json", cache / f"{key}.body"
    if meta_path.exists():
        emit(cached=True, body=str(body_path), **json.loads(meta_path.read_text()))
        return 0
    stop = ROOT / f"STOP-{site}"
    with open(ROOT / f"{site}.lock", "a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if stop.exists():
            emit(refused=f"{site} stopped: {stop.read_text().strip()}", url=url)
            return 3
        state_path = ROOT / f"{site}.state.json"
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        today = datetime.now(UTC).date().isoformat()
        count = state.get("count", 0) if state.get("day") == today else 0
        if count >= DAILY_CAP:
            emit(refused=f"{site} daily cap {DAILY_CAP} reached", url=url)
            return 3
        wait = state.get("last", 0.0) + GAP_SECONDS - time.time()
        if wait > 0:
            time.sleep(wait)
        cookie = (SECRETS / f"{site}_session").read_text().strip()
        request = urllib.request.Request(
            url, headers={"User-Agent": "EquityOS Research", "Cookie": f"sessionid={cookie}"}
        )
        status, headers, body, error = 0, {}, b"", ""
        started = time.time()
        try:
            with urllib.request.build_opener(NoRedirect).open(request, timeout=30) as response:
                status, headers, body = (
                    response.status,
                    dict(response.headers),
                    response.read(MAX_BYTES + 1),
                )
        except urllib.error.HTTPError as http_error:
            status, headers, body = (
                http_error.code,
                dict(http_error.headers),
                http_error.read(MAX_BYTES + 1),
            )
        except (urllib.error.URLError, TimeoutError, OSError) as transport:
            error = type(transport).__name__
        state_path.write_text(json.dumps({"day": today, "count": count + 1, "last": time.time()}))
        location = headers.get("Location", "")
        if status in STOP_STATUSES or (
            300 <= status < 400 and any(m in location for m in LOGIN_MARKERS)
        ):
            stop.write_text(f"{status} {location} on {url} at {datetime.now(UTC).isoformat()}")
    meta = {
        "url": url,
        "status": status,
        "error": error,
        "location": location,
        "content_type": headers.get("Content-Type", ""),
        "bytes": len(body),
        "truncated": len(body) > MAX_BYTES,
        "sha256": hashlib.sha256(body).hexdigest(),
        "fetched_at": datetime.fromtimestamp(started, UTC).isoformat(),
        "crawler": crawler,
    }
    body_path.write_bytes(body[:MAX_BYTES])
    if status == 200:
        meta_path.write_text(json.dumps(meta))
    with open(ROOT / "requests.jsonl", "a") as log:
        log.write(json.dumps(meta) + "\n")
    emit(cached=False, body=str(body_path), **meta)
    return 0


if __name__ == "__main__":
    sys.exit(main())
