"""Tijori reads the screen export and its review make.

Kept out of ``tijori_source``: that file is one of the ``tijori`` extractor's pinned sources
(``compare.run_config.VENDOR_EXTRACTORS``), so a fetch change there would drift the pin.
"""

from __future__ import annotations

import urllib.error
import urllib.request

from fundamentals.ingest.tijori_capture import build_page_request, complete_body
from fundamentals.ingest.tijori_source import TijoriSource, _NoRedirectHandler
from fundamentals.ingest.tijori_tables import TijoriCredentialsError, TijoriFetchError

_NO_CREDENTIALS = "tijori credentials not provided"
_JSON_MEDIA_TYPE = "application/json"
_XHR_HEADER = ("X-Requested-With", "XMLHttpRequest")


def fetch_json(source: TijoriSource, url: str) -> bytes:
    """One authenticated JSON attempt; any status but 200, media type but JSON or an
    incomplete body refuses."""
    config = source.config
    if config.credentials is None:
        raise TijoriCredentialsError(_NO_CREDENTIALS)
    request = build_page_request(
        url, session_cookie=config.credentials.session_cookie, user_agent=config.user_agent
    )
    request.add_header(*_XHR_HEADER)
    opener = urllib.request.build_opener(_NoRedirectHandler())
    try:
        with opener.open(request, timeout=config.request_timeout_seconds) as response:
            payload: bytes = response.read(config.max_response_bytes + 1)
            status, headers = response.getcode(), response.headers
    except urllib.error.HTTPError as error:
        raise TijoriFetchError(f"tijori returned HTTP {error.code}, not 200") from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise TijoriFetchError(f"tijori fetch failed: {type(error).__name__}") from error
    if status != 200:
        raise TijoriFetchError(f"tijori returned HTTP {status}, not 200")
    media_type = headers.get("Content-Type")
    if (media_type or "").split(";", 1)[0].strip().lower() != _JSON_MEDIA_TYPE:
        raise TijoriFetchError(f"tijori media type is {media_type!r}, not {_JSON_MEDIA_TYPE}")
    incomplete = complete_body(payload, headers, max_bytes=config.max_response_bytes)
    if incomplete is not None:
        raise incomplete
    return payload


def fetch_overview_bytes(source: TijoriSource, slug: str) -> bytes:
    """The overview page's bytes, unparsed, so a caller can retain exactly what it then
    parses."""
    credentials = source.config.credentials
    if credentials is None:
        raise TijoriCredentialsError(_NO_CREDENTIALS)
    return source._fetch_overview_bytes(slug, credentials)
