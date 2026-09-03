"""Slice 4 acquisition contract: the two requests, their coupling, and what binds them.

Companion to :mod:`test_screener_watchlist`, which pins how each rendering is
read and how the two are compared. This file pins the seam itself: the GET
that authorises the POST, the cookie and token that travel between them, the
form action taken verbatim from the page, the id that binds both artifacts to
the requested list, and the page-level shapes — no session, a pagination
control, no export form — that must refuse before anything is compared.

No test opens a socket. The opener is pinned in :mod:`screener_watchlist_fixtures`
so that every request, GET or POST, arrives at the fake or raises.
"""

from __future__ import annotations

from typing import Any

import pytest
import screener_watchlist_fixtures as fx

from fundamentals.ingest.screener_session_models import SCREENER_ORIGIN

_ROSTER = fx.members()


def _incomplete(run: Any, refusal: str | None = None) -> Any:
    """Assert a run refused, optionally by the named typed error, and return its artifact."""
    artifact = run.artifact
    assert artifact.outcome is fx.models.WatchlistOutcome.INCOMPLETE
    assert artifact.failure is not None
    assert artifact.incomplete_reason
    if refusal is not None:
        assert artifact.failure.refusal == refusal
    return artifact


# --------------------------------------------------------------------------
# The seam: no network, and the harness proves it
# --------------------------------------------------------------------------


def test_a_request_the_harness_never_offered_raises_instead_of_dialling_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A26.3: the seam is the opener, so no code path can reach the real host.

    Slice 3's fakes replace ``_fetch_bytes``; the export POST does not go through
    it, and a fake that stops there leaves the POST live. Pinning the opener
    catches every request. Offering only the page proves the POST is intercepted
    too — it must surface as a retained refusal naming the harness error, never
    as a response.
    """
    run, transport = fx.acquire(monkeypatch, page=fx.watchlist_page(_ROSTER), export=None)

    artifact = _incomplete(run)
    assert fx.UnofferedRequestError.__name__ in artifact.failure.detail
    assert [exchange.method for exchange in transport.exchanges] == ["GET", "POST"]
    assert len(run.documents) == 1


def test_the_opener_is_looked_up_at_request_time_and_never_cached_on_the_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A26.2: seams pin ``build_opener`` by module attribute, so it is called per request.

    A source that built its opener at construction would hold one from before
    the seam was installed — here a sentinel that raises, in production the real
    network — and every guard in this suite would be bypassed silently.
    """
    with monkeypatch.context() as patcher:
        fx.refuse_dial_out(patcher)
        injected = fx.source()
        run, _ = fx.acquire_roster(patcher, _ROSTER, injected=injected)

    assert run.artifact.outcome is fx.models.WatchlistOutcome.RESULTS


# --------------------------------------------------------------------------
# Two requests, and what travels between them
# --------------------------------------------------------------------------


def test_one_run_is_exactly_one_navigation_get_and_one_export_post(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL4-13: read-only, always — no request other than the page and its export.

    ``/watchlist/add/`` creates state, and the membership editor mutates it. A
    run that issued anything beyond the authorising GET and the export POST
    could not be shown to be incapable of writing.
    """
    run, transport = fx.acquire_roster(monkeypatch, _ROSTER)

    assert run.artifact.outcome is fx.models.WatchlistOutcome.RESULTS
    assert [(exchange.method, exchange.url) for exchange in transport.exchanges] == [
        ("GET", fx.WATCHLIST_PAGE_URL),
        ("POST", fx.export_url()),
    ]


def test_the_post_carries_the_session_and_the_csrf_cookie_the_get_set_in_one_cookie_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL4-11 / SL4-24 / A31: the cookie state is serialised manually, and the token is the GET's.

    A jar attached to the opener adds nothing when a ``Cookie`` header is already
    present — which the transport always sets — so the token would never leave
    the process and Django's 403 would read as an account block. The csrftoken
    is the *second* ``Set-Cookie`` here, so collapsing the headers loses it too.
    """
    _, transport = fx.acquire_roster(monkeypatch, _ROSTER)

    cookies = fx.cookies_of(transport.posts[0])
    assert cookies[fx.SESSION_COOKIE_NAME] == fx.SESSION_TOKEN
    assert cookies[fx.CSRF_COOKIE_NAME] == fx.CSRF_COOKIE_VALUE


def test_the_form_token_travels_as_a_form_field_and_never_as_the_cookie(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL4-11 / A26.8: the page-embedded token is a form field; the cookie is the cookie.

    Django once accepted the form token as the cookie value by a compatibility
    path that is not promised and that no browser exercises. The two values
    differ in this fixture so the substitution is visible.
    """
    _, transport = fx.acquire_roster(monkeypatch, _ROSTER)

    post = transport.posts[0]
    assert fx.form_of(post)[fx.CSRF_FORM_FIELD] == [fx.CSRF_FORM_TOKEN]
    assert fx.cookies_of(post)[fx.CSRF_COOKIE_NAME] != fx.CSRF_FORM_TOKEN


def test_the_post_is_shaped_like_a_browser_form_submission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL4-11 / A26.6: Referer, Origin and a form content type; no XHR marker.

    The site routes on ``X-Requested-With`` and the capture probes did not send
    it; the CSRF check reads ``Referer`` and ``Origin``. A POST missing any of
    these is a request the source has never been seen to answer with CSV.
    """
    _, transport = fx.acquire_roster(monkeypatch, _ROSTER)

    post = transport.posts[0]
    assert post.headers["referer"] == fx.WATCHLIST_PAGE_URL
    assert post.headers["origin"] == SCREENER_ORIGIN
    assert post.headers["content-type"].startswith("application/x-www-form-urlencoded")
    assert "x-requested-with" not in post.headers
    assert "x-requested-with" not in transport.exchanges[0].headers


def test_a_get_that_sets_no_csrftoken_cookie_refuses_before_any_post(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A26.4 / SL4-24: a missing cookie is a refusal, never a fallback to the form token.

    Letting Django's 403 be the first sign points the operator at a blocked
    account. Refusing locally, before the POST, names the real cause and spends
    no request.
    """
    run, transport = fx.acquire_roster(
        monkeypatch, _ROSTER, set_cookie=("fixture_notice=seen; Path=/",)
    )

    artifact = _incomplete(run)
    assert transport.posts == []
    assert fx.CSRF_FORM_TOKEN not in artifact.failure.detail
    assert len(run.documents) == 1


@pytest.mark.parametrize(
    "attribute",
    ["Partitioned", "Priority=High"],
    ids=["unknown-valueless-attribute", "attribute-with-a-value"],
)
def test_the_csrf_cookie_is_read_past_any_attribute_the_source_adds(
    monkeypatch: pytest.MonkeyPatch, attribute: str
) -> None:
    """SL4-30 / A42: the pair is what matters; the attributes are not this adapter's business.

    ``http.cookies.SimpleCookie`` is not an RFC 6265 parser. Probed on this
    interpreter, an unknown valueless attribute — CHIPS ``Partitioned`` is the
    obvious next one — makes it discard the *whole* header silently, and
    ``Priority=High`` comes back as a second cookie that would then be sent to
    the host. Either way the run reports that the page set no csrftoken, which
    is false and points the operator at the wrong cause. Reading the ``name=value``
    pair before the first ``;`` and ignoring the rest is drift-proof.
    """
    run, transport = fx.acquire_roster(
        monkeypatch,
        _ROSTER,
        set_cookie=(f"{fx.CSRF_COOKIE_NAME}={fx.CSRF_COOKIE_VALUE}; Path=/; {attribute}",),
    )

    assert run.artifact.outcome is fx.models.WatchlistOutcome.RESULTS
    assert fx.cookies_of(transport.posts[0]) == {
        fx.SESSION_COOKIE_NAME: fx.SESSION_TOKEN,
        fx.CSRF_COOKIE_NAME: fx.CSRF_COOKIE_VALUE,
    }


@pytest.mark.parametrize(
    ("set_cookie", "cause"),
    [
        (("fixture_notice=seen; Path=/",), "set no csrftoken"),
        (("csrftoken; Path=/",), "could not read"),
        ((f"{fx.CSRF_COOKIE_NAME}=; Max-Age=0; Path=/",), "empty csrftoken"),
    ],
    ids=["none-sent", "unreadable", "deleted"],
)
def test_the_three_ways_the_csrf_cookie_can_be_missing_are_told_apart(
    monkeypatch: pytest.MonkeyPatch, set_cookie: tuple[str, ...], cause: str
) -> None:
    """SL4-30 / A42: a symptom that names the wrong cause is the dangerous kind of refusal.

    "The page set no csrftoken" is a true statement about one of these and a
    false one about the other two: a header the reader could not parse, and
    Django's own deletion shape (``csrftoken=; Max-Age=0``), which today passes
    a bare presence check and would send an empty token to the host. Each must
    say which of the three actually happened, and none may spend the POST.
    """
    run, transport = fx.acquire_roster(monkeypatch, _ROSTER, set_cookie=set_cookie)

    artifact = _incomplete(run, "WatchlistPageError")
    assert cause in artifact.failure.detail
    assert transport.posts == []


@pytest.mark.parametrize(
    ("header", "secret"),
    [
        (f"{fx.CSRF_COOKIE_NAME}=fixture-csrf\nfolded; Path=/", "fixture-csrf\nfolded"),
        (f"{fx.CSRF_COOKIE_NAME}=fixture-csrf\x7fdelete; Path=/", "fixture-csrf\x7fdelete"),
        ("csrf\ntoken=fixture-csrf-cookie-value; Path=/", "fixture-csrf-cookie-value"),
    ],
    ids=["newline-in-the-value", "delete-in-the-value", "newline-in-the-name"],
)
def test_a_cookie_carrying_a_control_character_never_reaches_a_header(
    monkeypatch: pytest.MonkeyPatch, header: str, secret: str
) -> None:
    """SL4-28 / A39, guard one: a cookie is not trusted merely because the source sent it.

    An obs-folded ``Set-Cookie`` arrives from the header parser with a real
    newline inside its value, which is also what any RFC 6265 reader produces
    from a quoted ``\\012`` escape. Serialised into the outbound ``Cookie``
    header it makes ``http.client`` raise a ``ValueError`` whose message quotes
    that whole header — the session cookie and the CSRF token together — into
    the artifact and onto the terminal. The value is refused before a header is
    built, and the refusal echoes neither the cookie text nor the offending byte
    — a name can carry one as easily as a value can.
    """
    run, transport = fx.acquire_roster(monkeypatch, _ROSTER, set_cookie=(header,))

    artifact = _incomplete(run, "WatchlistPageError")
    assert "control character" in artifact.failure.detail
    assert secret not in artifact.failure.detail
    assert transport.posts == []


def test_an_error_this_code_did_not_write_is_recorded_without_its_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL4-28 / A39, guard two: the class is closed by redaction, not by enumeration.

    ``http.client`` raises a bare ``ValueError`` — not a ``URLError``, so the
    transport does not wrap it — whose message is the whole outbound ``Cookie``
    header. SL4-15's retention handler writes that message into the artifact and
    onto stderr, so the type is recorded and every secret this run knows is
    removed from the message. Enumerating which exception types can carry a
    secret is how this was missed once; keeping the secret out of the text is
    what closes it.
    """
    leaked = ValueError(
        f"Invalid header value b'{fx.SESSION_COOKIE_NAME}={fx.SESSION_TOKEN}; "
        f"{fx.CSRF_COOKIE_NAME}={fx.CSRF_COOKIE_VALUE}' while posting {fx.CSRF_FORM_TOKEN}"
    )

    run, _ = fx.acquire_roster(monkeypatch, _ROSTER, export_error=leaked)

    artifact = _incomplete(run, "ValueError")
    published = artifact.model_dump_json()
    for secret in (fx.SESSION_TOKEN, fx.CSRF_COOKIE_VALUE, fx.CSRF_FORM_TOKEN):
        assert secret not in artifact.failure.detail
        assert secret not in published
    assert "ValueError" in artifact.failure.detail


def test_a_page_supplied_session_cookie_can_never_displace_the_injected_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A44 / SL4-11: the override is made impossible rather than merely unreached.

    ``_cookie_state`` refuses a re-issued session cookie before the POST, so
    nothing in this seam reaches the transport with one today. That is one
    refusal away from a page-supplied ``sessionid`` being serialised into the
    outbound header in place of the one this process was configured with, so the
    transport drops it whatever the caller passes.
    """
    transport = fx.serve(
        monkeypatch, page=fx.watchlist_page(_ROSTER), export=fx.export_csv(_ROSTER)
    )

    fx.source().post_form(
        url=fx.export_url(),
        fields={fx.CSRF_FORM_FIELD: fx.CSRF_FORM_TOKEN},
        referer=fx.WATCHLIST_PAGE_URL,
        cookies={
            fx.SESSION_COOKIE_NAME: "fixture-attacker-session",
            fx.CSRF_COOKIE_NAME: fx.CSRF_COOKIE_VALUE,
        },
    )

    cookies = fx.cookies_of(transport.posts[0])
    assert cookies[fx.SESSION_COOKIE_NAME] == fx.SESSION_TOKEN
    assert cookies[fx.CSRF_COOKIE_NAME] == fx.CSRF_COOKIE_VALUE


def test_a_get_that_reissues_the_session_cookie_fails_closed_before_any_post(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A26.7: the session cookie was never re-issued live; if it is, stop.

    A re-issued session is a value this adapter did not mint and must never
    write back into configuration or carry onward as if it had.
    """
    run, transport = fx.acquire_roster(
        monkeypatch,
        _ROSTER,
        set_cookie=(*fx.DEFAULT_SET_COOKIE, "sessionid=fixture-reissued-session; Path=/"),
    )

    _incomplete(run)
    assert transport.posts == []


@pytest.mark.parametrize("status", [403, 451], ids=["forbidden", "unavailable-for-legal-reasons"])
def test_a_refused_export_names_both_readings_and_the_status_it_actually_saw(
    monkeypatch: pytest.MonkeyPatch,
    status: int,
) -> None:
    """A26.5 / A44: a POST 403 may be a stale CSRF token, not a block on the account.

    The shipped transport calls every terminal status terminal and tells the
    operator to stop. On the export that advice is wrong half the time for a
    403, so the failure must say both readings are possible — but a 451 is not a
    stale-token candidate at all, and a refusal that announces "HTTP 403"
    whatever the host actually said sends the operator to re-fetch a page over a
    legal block. The status seen is part of the diagnosis.
    """
    run, _ = fx.acquire_roster(
        monkeypatch, _ROSTER, export_error=fx.http_error(fx.export_url(), status, "Refused")
    )

    artifact = _incomplete(run)
    detail = artifact.failure.detail.lower()
    assert "csrf" in detail
    assert "block" in detail
    assert f"status {status}" in detail
    assert len(run.documents) == 1


def test_a_two_hundred_html_export_is_retained_and_refused_not_parsed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL4-12 through the run: a login page is a 200, and it is not a CSV.

    Parsed as CSV it is a one-column table of markup that would fail the
    cross-check for confusing reasons; the honest refusal is the media type,
    with the body kept so the operator can see what the host actually sent.
    """
    run, _ = fx.acquire(
        monkeypatch,
        page=fx.watchlist_page(_ROSTER),
        export="<html><body><form action='/login/'></form></body></html>",
        export_content_type="text/html; charset=utf-8",
    )

    artifact = _incomplete(run, "WatchlistExportError")
    assert artifact.rows == ()
    assert len(run.documents) == 2


def test_a_page_body_that_does_not_parse_is_retained_evidence_and_not_a_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL4-15 / A11: once a body is retained, no ``Exception`` may discard it.

    An empty 2xx is a real answer from the host and the one most worth keeping.
    ``parse_document`` raises a parser error that is not a session error, so
    without this rule the run dies with a traceback and the body is lost. The
    original type stays in the detail so a page failure is distinguishable
    from a bug.
    """
    run, transport = fx.acquire(monkeypatch, page="", export=fx.export_csv(_ROSTER))

    artifact = _incomplete(run)
    assert "ParserError" in artifact.failure.detail
    assert len(run.documents) == 1
    assert transport.posts == []


def test_an_export_body_that_is_not_utf8_is_retained_evidence_and_not_a_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL4-15 after both bodies: the decode error is caught after the second retention too.

    ``UnicodeDecodeError`` is a ``ValueError``, not a session error. Both bodies
    were received, so both must be in the run for the refusal to be examinable.
    """
    run, _ = fx.acquire(
        monkeypatch, page=fx.watchlist_page(_ROSTER), export=b"\xff\xfe\x00not text"
    )

    artifact = _incomplete(run)
    assert "UnicodeDecodeError" in artifact.failure.detail
    assert len(run.documents) == 2


def test_a_cross_check_refusal_is_never_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    """A25: a value tick is a decision for the operator, not a reflex for the code.

    A silent second pair would spend budget and hide a real disagreement behind
    a lucky agreement. Exactly two requests are made whatever the outcome.
    """
    member = _ROSTER[0]
    changed = fx.with_member(_ROSTER, member.serial, values=("999.99", *member.values[1:]))

    run, transport = fx.acquire(
        monkeypatch, page=fx.watchlist_page(_ROSTER), export=fx.export_csv(changed)
    )

    _incomplete(run, "WatchlistCrossCheckError")
    assert len(transport.exchanges) == 2


# --------------------------------------------------------------------------
# The page must authorise the export, and both must be the requested list
# --------------------------------------------------------------------------


@pytest.mark.parametrize("forms", [0, 2], ids=["no-export-form", "two-export-forms"])
def test_a_page_without_exactly_one_export_form_refuses_before_any_post(
    monkeypatch: pytest.MonkeyPatch, forms: int
) -> None:
    """SL4-17 / A18: the form is the only authority for where the export goes.

    Zero forms is a page that offers no export — an anonymous or changed shell.
    Two make the target a matter of document order, and posting to a form the
    page did not single out is a request no browser would make.
    """
    run, transport = fx.acquire(
        monkeypatch,
        page=fx.watchlist_page(_ROSTER, forms=forms),
        export=fx.export_csv(_ROSTER),
    )

    _incomplete(run, "WatchlistPageError")
    assert transport.posts == []


def test_the_export_is_posted_to_the_form_action_read_verbatim_from_the_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL4-17 / A18: no export URL is ever constructed; the page's action is posted as-is.

    The two page shapes carry two different actions and the export endpoint is
    parameterised by the view name. A reader rebuilding the URL from an id
    would post something the fetched page never offered — the marker parameter
    here survives only if the action is taken whole.
    """
    action = f"{fx.export_action()}&fixture_marker=verbatim"

    run, transport = fx.acquire(
        monkeypatch,
        page=fx.watchlist_page(_ROSTER, form_action=action),
        export=fx.export_csv(_ROSTER),
        export_target=f"{SCREENER_ORIGIN}{action}",
    )

    assert run.artifact.outcome is fx.models.WatchlistOutcome.RESULTS
    assert transport.posts[0].url == f"{SCREENER_ORIGIN}{action}"


def test_an_off_origin_export_action_is_never_posted_to(monkeypatch: pytest.MonkeyPatch) -> None:
    """A44 / SL4-11: the form action is read verbatim, which is why the origin must be pinned.

    The page is the authority for *where* the export goes, and the page is the
    thing that may have been tampered with. An action on another host is the one
    shape where taking it verbatim would carry the subscriber session cookie
    off-origin, so the transport's origin pin is what stands between the two —
    and until now no watchlist test held it there.
    """
    action = "https://fixture-not-screener.invalid/api/export/screen/?url_name=goto_sublist"

    run, transport = fx.acquire(
        monkeypatch,
        page=fx.watchlist_page(_ROSTER, form_action=action),
        export=fx.export_csv(_ROSTER),
        export_target=action,
    )

    artifact = _incomplete(run)
    assert artifact.rows == ()
    assert transport.posts == []
    assert [exchange.method for exchange in transport.exchanges] == ["GET"]


def test_a_selector_marking_two_lists_as_the_open_one_refuses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A44: an ambiguous selector is not a name to choose from, it is a page to refuse.

    Keeping the first marked entry and filing the second under
    ``other_watchlist_names`` publishes a name for a list this page may not be
    rendering, and tells the operator that list was skipped. The name binds
    nothing, which is why an *unmarked* selector is tolerated — but two marks
    are a page this reader does not understand.
    """
    run, transport = fx.acquire(
        monkeypatch,
        page=fx.watchlist_page(
            _ROSTER, names=(fx.WATCHLIST_NAME, fx.OTHER_WATCHLIST_NAME), selected=(0, 1)
        ),
        export=fx.export_csv(_ROSTER),
    )

    _incomplete(run, "WatchlistPageError")
    assert transport.posts == []


@pytest.mark.parametrize("shape_id", [fx.WATCHLIST_ID, None], ids=["sublist-form", "default-form"])
def test_the_watchlist_id_is_read_from_the_form_action_or_else_from_the_stocks_link(
    monkeypatch: pytest.MonkeyPatch, shape_id: int | None
) -> None:
    """SL4-17 / A18: the id is provenance, taken from the page and never guessed.

    The ``goto_sublist`` form carries it as ``sublist_id``; the default-list
    form carries none, and the ``/user/stocks/?next=/watchlist/<id>/`` link is
    present on both shapes. The dropdown carries no id at all, so a reader
    looking there records nothing.
    """
    run, _ = fx.acquire(
        monkeypatch,
        page=fx.watchlist_page(_ROSTER, form_action=fx.export_action(shape_id)),
        export=fx.export_csv(_ROSTER),
        export_target=fx.export_url(shape_id),
    )

    assert run.artifact.outcome is fx.models.WatchlistOutcome.RESULTS
    assert run.artifact.watchlist_id == fx.WATCHLIST_ID


def test_a_requested_watchlist_id_selects_the_named_page(monkeypatch: pytest.MonkeyPatch) -> None:
    """SL4-17: ``--watchlist-id`` GETs ``/watchlist/<id>/``, which renders the id-bearing form.

    Fetching the default list instead would silently acquire whichever list is
    the account's default under the requested id's name.
    """
    run, transport = fx.acquire_roster(
        monkeypatch,
        _ROSTER,
        watchlist_id=fx.WATCHLIST_ID,
        page_url=f"{fx.WATCHLIST_PAGE_URL}{fx.WATCHLIST_ID}/",
    )

    assert run.artifact.outcome is fx.models.WatchlistOutcome.RESULTS
    assert transport.urls[0] == f"{fx.WATCHLIST_PAGE_URL}{fx.WATCHLIST_ID}/"


def test_a_page_whose_id_differs_from_the_requested_one_refuses_before_any_post(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL4-17: the id read back must equal the id requested, or neither artifact is bound.

    A redirect-free 200 for another list is a plausible page. Posting its form
    would export that other list under the requested id, and both renderings
    would agree with each other perfectly.
    """
    run, transport = fx.acquire(
        monkeypatch,
        page=fx.watchlist_page(_ROSTER, watchlist_id=fx.OTHER_WATCHLIST_ID),
        export=fx.export_csv(_ROSTER),
        watchlist_id=fx.WATCHLIST_ID,
        page_url=f"{fx.WATCHLIST_PAGE_URL}{fx.WATCHLIST_ID}/",
        export_target=fx.export_url(fx.OTHER_WATCHLIST_ID),
    )

    _incomplete(run, "WatchlistPageError")
    assert transport.posts == []


def test_the_selected_dropdown_entry_names_the_watchlist_on_the_artifact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL4-17 / A18: the dropdown supplies the name only, marked by its check icon.

    The name is provenance for a human reading ``data/raw``; it is never an
    identifier. When several lists are offered, only the selected one is what
    this page renders, so only its name may be recorded.
    """
    run, _ = fx.acquire(
        monkeypatch,
        page=fx.watchlist_page(
            _ROSTER, names=(fx.OTHER_WATCHLIST_NAME, fx.WATCHLIST_NAME), selected=1
        ),
        export=fx.export_csv(_ROSTER),
    )

    assert run.artifact.outcome is fx.models.WatchlistOutcome.RESULTS
    assert run.artifact.watchlist_name == fx.WATCHLIST_NAME


def test_a_dropdown_with_no_selected_entry_leaves_the_name_unset_without_refusing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A34: the name is provenance only, so its absence is a ``None``, not a refusal.

    Refusing here would fail a run over a label that binds nothing; the id and
    the form action are what bind the artifacts.
    """
    run, _ = fx.acquire(
        monkeypatch,
        page=fx.watchlist_page(_ROSTER, selected=None),
        export=fx.export_csv(_ROSTER),
    )

    assert run.artifact.outcome is fx.models.WatchlistOutcome.RESULTS
    assert run.artifact.watchlist_name is None


def test_the_selector_is_read_from_its_own_menu_and_not_from_every_dropdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL4-25: the site's other menus are not watchlists, and must not be named as some.

    The live page carries four ``dropdown-content`` blocks; only one is the
    watchlist selector, and the rest are nav and promo menus whose ``<li>``
    entries read as plausible list names. A reader that matches them all still
    finds the right selected name — the check icon is unique — so the artifact
    looks correct while ``other_watchlist_names`` fills with marketing copy. The
    operator is then told the run skipped lists that do not exist, on a page
    offering exactly one, which is precisely the advisory they would act on.
    """
    run, _ = fx.acquire(monkeypatch, page=fx.watchlist_page(_ROSTER), export=fx.export_csv(_ROSTER))

    assert run.artifact.watchlist_name == fx.WATCHLIST_NAME
    assert run.artifact.other_watchlist_names == ()


def test_a_second_watchlist_in_the_selector_is_named_while_the_decoys_are_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SL4-25's other half: scoping must not cost the behaviour it protects.

    Narrowing to the selector's own menu would be worthless if it also dropped a
    genuine second list, so the same page that hides the decoys must still
    report a real sibling. One invocation acquires one list; the other is named
    so the caller knows what it did not get.
    """
    run, _ = fx.acquire(
        monkeypatch,
        page=fx.watchlist_page(_ROSTER, names=(fx.WATCHLIST_NAME, "Second Synth List")),
        export=fx.export_csv(_ROSTER),
    )

    assert run.artifact.watchlist_name == fx.WATCHLIST_NAME
    assert run.artifact.other_watchlist_names == ("Second Synth List",)


@pytest.mark.parametrize(
    ("account", "logout"), [(False, True), (True, False)], ids=["no-account-link", "no-logout-form"]
)
def test_a_page_that_does_not_prove_a_subscriber_session_refuses_before_any_post(
    monkeypatch: pytest.MonkeyPatch, account: bool, logout: bool
) -> None:
    """SL4-18 / A19: an expired cookie yields a valid anonymous page, not an error.

    The worst reachable shape is an anonymous shell with no rows beside a
    header-only CSV, agreeing on nothing. Both login markers are required on
    the page before anything is parsed from it, and no export is attempted on
    a page that did not prove who served it.
    """
    run, transport = fx.acquire(
        monkeypatch,
        page=fx.watchlist_page(_ROSTER, account=account, logout=logout),
        export=fx.export_csv(_ROSTER),
    )

    _incomplete(run, "AnonymousPageError")
    assert transport.posts == []
    assert run.artifact.rows == ()


@pytest.mark.parametrize(
    "extra", [fx.PAGINATION_BLOCK, fx.PAGE_INFO_BLOCK], ids=["pagination-block", "data-page-info"]
)
def test_a_page_that_starts_paginating_is_incomplete_not_ignored(
    monkeypatch: pytest.MonkeyPatch, extra: str
) -> None:
    """SL4-22 / A23: a cap was never disproved, so the first sign of one must refuse.

    A larger list that paginates would render its first page on both sides,
    the two would agree, and the run would publish N of M as consistent. The
    presence of either control is the tripwire.
    """
    run, _ = fx.acquire(
        monkeypatch,
        page=fx.watchlist_page(_ROSTER, extra=extra),
        export=fx.export_csv(_ROSTER),
    )

    artifact = _incomplete(run, "WatchlistPageError")
    assert artifact.rows == ()


def test_a_table_with_no_member_rows_is_incomplete_and_never_a_published_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A9: an empty list and a degraded page are indistinguishable, so neither publishes.

    Until the empty shape is captured live, a rowless table is a run that
    stopped short, with the reason naming it — never a successful ``EMPTY``.
    """
    run, _ = fx.acquire(
        monkeypatch,
        page=fx.page(fx.table_of(fx.header_row(fx.DEFAULT_COLUMNS))),
        export=fx.export_csv(()),
    )

    artifact = _incomplete(run)
    assert artifact.rows == ()
