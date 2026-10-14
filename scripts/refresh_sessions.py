"""Refresh the Screener and Tijori session cookies by logging in with a real browser.

    uv run --group login python scripts/refresh_sessions.py [screener] [tijori] [--headed]

Each site keeps a persistent browser profile in ~/.secrets/browser/<site>, so a login that is
still valid is reused. Otherwise the script signs in with ~/.secrets/<site>_email and
~/.secrets/<site>_password. With --headed and no stored password, it waits for you to log in
by hand in the window it opens. The fresh `sessionid` goes to ~/.secrets/<site>_session (0600),
which scripts/credentials.sh exports. Secret values are never printed.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import BrowserContext, Page, sync_playwright

SECRETS = Path(os.environ.get("EQOS_SECRETS_DIR", Path.home() / ".secrets"))
MANUAL_LOGIN_TIMEOUT_S = 300


def screener_logged_in(page: Page) -> bool:
    """Screener redirects an anonymous visit to /dash/ to its register or login page."""
    page.goto("https://www.screener.in/dash/")
    return urlparse(page.url).path == "/dash/"


def tijori_logged_in(page: Page) -> bool:
    """Tijori renders a logout link only for a signed-in visitor."""
    page.goto("https://www.tijorifinance.com/dashboard/")
    page.wait_for_timeout(3000)
    return "logout" in page.content().lower()


SITES = {
    "screener": {
        "login_url": "https://www.screener.in/login/",
        "email": "input[name=username]",
        "password": "input[name=password]",
        "submit": "form button[type=submit]",
        "cookie_domain": "screener.in",
        "check": screener_logged_in,
    },
    "tijori": {
        "login_url": "https://www.tijorifinance.com/account/signin/",
        "email": "#email",
        "password": "#pwd-field",
        "submit": "button:has-text('SIGN IN')",
        "cookie_domain": "tijorifinance.com",
        "check": tijori_logged_in,
    },
}


def secret(name: str) -> str | None:
    """Return the stored secret `name`, or None when it is absent."""
    path = SECRETS / name
    return path.read_text().strip() if path.exists() else None


def login(site: str, page: Page, headed: bool) -> None:
    """Sign in with the stored email/password, or wait for a manual login when headed."""
    spec = SITES[site]
    email, password = secret(f"{site}_email"), secret(f"{site}_password")
    page.goto(spec["login_url"])
    if email and password:
        page.fill(spec["email"], email)
        page.fill(spec["password"], password)
        page.click(spec["submit"])
        page.wait_for_load_state("load")
        page.wait_for_timeout(5000)
        return
    if not headed:
        print(
            f"{site}: no {site}_email/{site}_password in {SECRETS}; store them or use --headed"
        )
        return
    print(f"{site}: log in in the browser window (waiting up to {MANUAL_LOGIN_TIMEOUT_S}s)")
    deadline = time.monotonic() + MANUAL_LOGIN_TIMEOUT_S
    while time.monotonic() < deadline and not session_cookie(page.context, site):
        page.wait_for_timeout(2000)


def session_cookie(context: BrowserContext, site: str) -> str | None:
    """Return the site's `sessionid` cookie value from the browser profile, if any."""
    domain = SITES[site]["cookie_domain"]
    return next(
        (
            c["value"]
            for c in context.cookies()
            if c["name"] == "sessionid" and c["domain"].endswith(domain)
        ),
        None,
    )


def refresh(site: str, headed: bool) -> bool:
    """Ensure a logged-in profile for `site` and write its session cookie; return success."""
    profile = SECRETS / "browser" / site
    for directory in (SECRETS, profile.parent, profile):
        directory.mkdir(exist_ok=True, mode=0o700)
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            profile, channel="chromium", headless=not headed
        )
        page = context.new_page()
        check = SITES[site]["check"]
        if not check(page):
            login(site, page, headed)
        ok = check(page)
        cookie = session_cookie(context, site)
        context.close()
    if not (ok and cookie):
        print(f"{site}: login FAILED (rerun with --headed to watch or log in by hand)")
        return False
    target = SECRETS / f"{site}_session"
    tmp = target.with_suffix(".tmp")
    tmp.write_text(cookie)
    tmp.chmod(0o600)
    tmp.replace(target)
    print(f"{site}: session refreshed -> {target}")
    return True


def main() -> None:
    """Refresh the requested sites (both by default); exit 1 if any fails."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "sites", nargs="*", metavar="site", help=f"any of {', '.join(SITES)} (default: all)"
    )
    parser.add_argument(
        "--headed", action="store_true", help="show the browser; allows a manual login"
    )
    args = parser.parse_args()
    if unknown := set(args.sites) - set(SITES):
        parser.error(f"unknown site(s): {', '.join(sorted(unknown))}")
    results = [refresh(site, args.headed) for site in args.sites or SITES]
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
