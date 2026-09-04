"""Environment-sourced credentials for the Fundamentals composition root.

Extracted verbatim from :mod:`fundamentals.api.cli` so the composition root
stays inside its file-size bound. These are the only readers of the process
environment in the acquisition path: business-logic modules receive injected
credentials, and each reader returns ``None`` when no auth material is present
so the selected command decides for itself whether to refuse.
"""

from __future__ import annotations

import os

from pydantic import SecretStr

from fundamentals.api.upstox_cli import UPSTOX_TOKEN_ENV
from fundamentals.ingest.screener_session_models import ScreenerCredentials
from fundamentals.ingest.tijori_source import TijoriCredentials
from fundamentals.ingest.upstox_source import UpstoxCredentials

_TIJORI_EMAIL_ENV = "TIJORI_EMAIL"
_TIJORI_PASSWORD_ENV = "TIJORI_PASSWORD"
_TIJORI_SESSION_ENV = "TIJORI_SESSION_COOKIE"
_TIJORI_LOGIN_UNIMPLEMENTED = "set TIJORI_SESSION_COOKIE; automated login not yet implemented"
_SCREENER_SESSION_ENV = "SCREENER_SESSION_COOKIE"
_UPSTOX_TOKEN_ENV = UPSTOX_TOKEN_ENV


def _tijori_credentials_from_env() -> TijoriCredentials | None:
    """Read a pre-minted Tijori session cookie from the environment.

    Returns ``None`` when no auth material is present, so the runner skips Tijori
    cleanly. Email/password-only input fails because this round does not automate login.
    """
    email = os.environ.get(_TIJORI_EMAIL_ENV)
    password = os.environ.get(_TIJORI_PASSWORD_ENV)
    session_cookie = os.environ.get(_TIJORI_SESSION_ENV)
    if session_cookie is None:
        if email is not None or password is not None:
            raise SystemExit(_TIJORI_LOGIN_UNIMPLEMENTED)
        return None
    return TijoriCredentials(session_cookie=SecretStr(session_cookie))


def _screener_credentials_from_env() -> ScreenerCredentials | None:
    """Read a pre-minted Screener subscriber session cookie from the environment.

    Returns ``None`` when no cookie is present, so a Screener command refuses
    with a named environment variable instead of attempting an anonymous fetch
    that would silently return a valid logged-out page.
    """
    session_cookie = os.environ.get(_SCREENER_SESSION_ENV)
    if session_cookie is None:
        return None
    return ScreenerCredentials(session_cookie=SecretStr(session_cookie))


def _upstox_credentials_from_env() -> UpstoxCredentials | None:
    """Read the Upstox Analytics Token from the environment, if one is set.

    Returns ``None`` when unset rather than refusing: the instrument files are
    served unauthenticated, so a token-free run of Slice 1 is a supported use
    and not a misconfiguration. An authenticated surface refuses on its own,
    naming this variable.
    """
    token = os.environ.get(_UPSTOX_TOKEN_ENV)
    if token is None:
        return None
    return UpstoxCredentials(access_token=SecretStr(token))
