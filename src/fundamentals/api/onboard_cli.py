"""The ``onboard`` command: discover, verify and record one NSE symbol (plan D6 D4).

    onboard <SYMBOL> --raw-root <dir> --snapshot-root <dir> [--config-root config]
        [--acquire --freeze-descriptor <path> | --generation <n>]

Replay (the default) reads ``gen-<n>`` under ``--raw-root`` (``--generation``, else the highest
complete one: its manifest present, valid and naming it) and never opens a socket.
``--acquire`` writes the next generation through the live transport, and only on a checkout
that satisfies the freeze protocol (C5): the descriptor's current entry complete, approved,
bound to the current held-out attempt and committed at ``HEAD``, its implementation commit an
ancestor of the first commit holding the entry, no commit since touching an implementation path
and none uncommitted, the descriptor in the running checkout and ``--config-root`` its
``config``. The live transport keeps the real HTTP status, follows no redirect and bounds
every body. An admitted issuer
(``ONBOARDED``/``PARTIAL``) then gets its derived settings, the latest verified filing as an
XBRL-only package, each verified vendor capture, the R-PDF exclusion attempt (D5) and the
printed ``compare run`` command under ``ONBOARDING_VERSIONS``; an ingest that does not complete
fails the command. The record is written before settings and ingest, so such a failure leaves
admitted identity evidence without completed ingest (D4.6 orders them). Exit: ``ONBOARDED`` 0,
``PARTIAL`` 4, anything else (including an abort) 5. Failures never echo a transport message,
so a credential a server reflects lands nowhere.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, date, datetime
from functools import partial
from pathlib import Path
from types import SimpleNamespace
from typing import Any, LiteralString
from urllib.parse import urlsplit

import psycopg
import structlog
import yaml
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, ConfigDict

from fundamentals.api.env_credentials import (
    _screener_credentials_from_env,
    _tijori_credentials_from_env,
    _upstox_credentials_from_env,
)
from fundamentals.compare.run_config import LoadedConfig, load_run_config
from fundamentals.compare.run_models import RunExitStatus
from fundamentals.contracts.acquisition_outcome import ExtractionOutcome
from fundamentals.contracts.canonical import Basis, Representation
from fundamentals.contracts.config_versions import ConfigVersions
from fundamentals.contracts.evidence import (
    AcquisitionAttempt,
    AttemptStage,
    CaptureReference,
    FilingFamily,
)
from fundamentals.contracts.observation import AccountingFramework
from fundamentals.contracts.onboarding import (
    ONBOARDING_VERSIONS,
    UNIT_SURFACES,
    OnboardingOutcome,
    Verdict,
    VerificationState,
    VerificationUnit,
)
from fundamentals.contracts.retention import OriginalExpiredError
from fundamentals.contracts.snapshot import SnapshotError
from fundamentals.contracts.source_catalog import (
    BSE_PEER_SEARCH,
    BUILTIN_SOURCES,
    SCREENER_PAGE,
    TIJORI_PAGE,
    TIJORI_SEARCH,
    UPSTOX_ROUTED,
    UPSTOX_STATEMENT,
    VENDOR_SURFACES,
)
from fundamentals.entity import derived_settings, discovery
from fundamentals.entity.derived_settings import DerivedSettings, Filing, derive
from fundamentals.entity.discovery import (
    MANIFEST_NAME,
    Discovery,
    DiscoveryManifest,
    OnboardingAbortError,
    Recorded,
    Request,
    Send,
    acquiring_fetch,
    discover,
    record,
    store_captures,
    write_generation,
)
from fundamentals.entity.discovery_origins import ORIGINS
from fundamentals.entity.verification import outcome, tijori_candidate
from fundamentals.evidence import vendor_screener, vendor_tijori, vendor_upstox
from fundamentals.evidence.capture_intake import (
    NSE_FILED_AT_FORMAT,
    XBRL_INPUT_DIR,
    FirstPartySurface,
    retained_intake_from_manifest,
)
from fundamentals.evidence.capture_retention import ingest_vendor_retained
from fundamentals.evidence.discovery_gate import IneligibleCaptureError
from fundamentals.evidence.first_party_extract import IngestError
from fundamentals.evidence.first_party_ingest import ingest_first_party
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.evidence.vendor_ingest import VendorExtraction, VendorIngestRequest
from fundamentals.evidence.vendor_screener import ScreenerIssuerBinding
from fundamentals.ingest.http_session import NoRedirectHandler, read_bounded
from fundamentals.ingest.nse_filings import NSE_API
from fundamentals.ingest.screener_financials_models import Section
from fundamentals.ingest.screener_session_models import DEFAULT_USER_AGENT, BasisTopology
from fundamentals.ingest.screener_session_page import parse_document, read_identity
from fundamentals.ingest.tijori_capture import COMPANY_DETAILS_ISLAND, FINANCIALS_PAGE_LABEL
from fundamentals.ingest.tijori_page import JsonScriptCollector, decode_document
from fundamentals.pg.identity_seed import SettingKey
from fundamentals.pg.pool import DatabaseUnavailableError, open_pool
from fundamentals.pg.settings import PgRole, PgSettings
from fundamentals.store.snapshot_store import MAX_BODY_BYTES, SnapshotStore

ONBOARD_COMMAND = "onboard"
DEFAULT_CONFIG_ROOT = "config"
SOURCE_CHECKOUT = Path(__file__).resolve().parents[3]  # the checkout this code runs from
ACQUISITION_NAME = "acquisition.json"
GENERATION_PREFIX = "gen-"
IMPLEMENTATION_PATHS = ("src", "config", "migrations", "scripts", "pyproject.toml", "uv.lock")
HOLDOUT_RECORD = "tests/fundamentals/fixtures/data_foundation/stage4_holdout.yaml"
TIMEOUT_SECONDS = 30
RETRIEVAL_NAME = "retrieval-manifest.json"
XBRL_KIND = "xbrl-consolidated"
TIJORI_DISPLAY = Path("mappings/tijori/v1/display.yaml")
SCREENER_SECTIONS = (
    Section.QUARTERS,
    Section.PROFIT_LOSS,
    Section.BALANCE_SHEET,
    Section.CASH_FLOW,
)
# The capture-less PDF exclusion attempt (D5 C1); no results-PDF source exists for a new issuer.
NSE_RESULTS_PDF_SOURCE = "nse-results-pdf"
RULING_PDF = "R-PDF"
COMPARE_PREFIX = "compare: "
_ADMITTED = (OnboardingOutcome.ONBOARDED, OnboardingOutcome.PARTIAL)
_TIJORI_COMPANY_ID = "company_id"
_EVIDENCE_REF = "evidence_input:{id}"
_ENTITY_KEY_SQL: LiteralString = "SELECT entity_key FROM eqos.reporting_entities WHERE id = %s"
# ``record`` returns no id; this single-writer CLI's record is the symbol's latest (discovery.py
# is at its line cap).
_RECORD_ID_SQL: LiteralString = "SELECT max(id) FROM eqos.onboarding_records WHERE identifier = %s"
_FREEZES = "freezes"
_IMPLEMENTATION = "implementation_commit"
_ENTRY_KEYS = frozenset(
    {
        *("attempt", "implementation_commit", "inputs", "tree", "holdout_payload_sha256"),
        *("onboarding_versions", "review"),
    }
)
_REVIEW_KEYS = frozenset({"reviewer", "verdict", "date"})
_APPROVE = "APPROVE"
_AGENT = "Mozilla/5.0 (X11; Linux x86_64)"  # Task 0b probe UA; BSE refuses a custom one (403)
# Task 0b (d6-capability.md §7): the exchange page's own same-origin headers; the bse library's
# request shape is refused (§8).
_BSE_HEADERS = {
    "Referer": "https://www.bseindia.com/",
    "Origin": "https://www.bseindia.com",
    "Accept": "application/json, text/plain, */*",
}
_SESSION_COOKIE = "sessionid={value}"
_HELP = "discover, verify and record one NSE symbol (D6)"
_NEEDS_DESCRIPTOR = "--acquire needs --freeze-descriptor"
_ACQUIRE_GENERATION = "--acquire writes the next generation; --generation selects a replay"
_WRONG_GENERATION = "gen-{n}'s manifest does not name generation {n}"
_INGEST_FAILED = "onboarding ingest of {what} did not complete: {outcome}"
_UNFROZEN = "the checkout does not satisfy the freeze protocol: {why}"
_SEVERITY_HIGH = "HIGH"
_EXIT = {
    OnboardingOutcome.ONBOARDED: RunExitStatus.SUCCESS,
    OnboardingOutcome.PARTIAL: RunExitStatus.INCOMPLETE,
}


class OnboardingIngestError(RuntimeError):
    """An admitted issuer's ingest did not complete."""


_FAILURES = (
    OnboardingAbortError,
    OnboardingIngestError,
    IneligibleCaptureError,
    IngestError,
    OSError,
    LookupError,
    ValueError,
    subprocess.SubprocessError,
    psycopg.Error,
    DatabaseUnavailableError,
    SnapshotError,
)

# Seams the tests replace: the authority table, the live transport, the clock, the replay.
SURFACES = VENDOR_SURFACES
replay_fetch = discovery.replay_fetch


def now() -> datetime:
    """The acquisition clock."""
    return datetime.now(UTC)


@contextmanager
def nse_session() -> Iterator[Any]:
    """The ``nse`` client's ``requests`` session, primed with its cookies."""
    from nse import NSE  # type: ignore[import-untyped]

    with tempfile.TemporaryDirectory() as folder, NSE(folder, timeout=TIMEOUT_SECONDS) as client:
        yield client._session


def _nse_send(url: str) -> tuple[int, bytes]:
    """One NSE API GET on the primed session: the real status, no redirect, a bounded body. A
    timeout or connection failure, during the request or the streamed body read, is the
    built-in ``TimeoutError`` or ``ConnectionError`` the acquiring fetch records."""
    import requests
    import urllib3

    with nse_session() as session:
        try:
            response = session.get(url, timeout=TIMEOUT_SECONDS, allow_redirects=False, stream=True)
            with response:
                if response.status_code != 200:
                    return int(response.status_code), b""
                body = SimpleNamespace(read=partial(response.raw.read, decode_content=True))
                return 200, read_bounded(body, MAX_BODY_BYTES)
        except (requests.Timeout, urllib3.exceptions.TimeoutError) as error:
            raise TimeoutError from error
        except (requests.RequestException, urllib3.exceptions.HTTPError) as error:
            raise ConnectionError from error


def live_transport() -> Send:
    """``send(request) -> (status, body)`` over HTTPS with each source's own credential;
    redirects are refused (a login bounce is a failure, not a page). Discovery has already
    checked each URL against its surface's origin."""
    screener, tijori, upstox = (
        _screener_credentials_from_env(),
        _tijori_credentials_from_env(),
        _upstox_credentials_from_env(),
    )
    cookies = {
        "screener-subscriber": screener and screener.session_cookie,
        "tijori": tijori and tijori.session_cookie,
    }
    opener = urllib.request.build_opener(NoRedirectHandler())

    def send(request: Request) -> tuple[int, bytes]:
        if request.url.startswith(NSE_API):  # the NSE API needs the client's primed session
            return _nse_send(request.url)
        headers = {"User-Agent": _AGENT}
        if (request.source_id, request.surface) == BSE_PEER_SEARCH or urlsplit(
            request.url
        ).netloc == "www.bseindia.com":
            headers |= _BSE_HEADERS
        # Vendor sites get the honest project UA, never a browser's.
        if request.source_id in cookies:
            headers["User-Agent"] = DEFAULT_USER_AGENT
        cookie = cookies.get(request.source_id)
        if cookie:
            headers["Cookie"] = _SESSION_COOKIE.format(value=cookie.get_secret_value())
        api = urlsplit(request.url)[:2] == ("https", ORIGINS[UPSTOX_STATEMENT])
        if upstox and (request.source_id, request.surface) in UPSTOX_ROUTED and api:
            headers["Authorization"] = f"Bearer {upstox.access_token.get_secret_value()}"
        try:
            with opener.open(
                urllib.request.Request(request.url, headers=headers), timeout=TIMEOUT_SECONDS
            ) as response:
                return int(response.status), read_bounded(response, MAX_BODY_BYTES)
        except urllib.error.HTTPError as error:
            return int(error.code), b""

    return send


def add_onboard_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register ``onboard``."""
    parser = subparsers.add_parser(ONBOARD_COMMAND, help=_HELP)
    parser.add_argument("symbol")
    parser.add_argument("--raw-root", required=True, type=Path)
    parser.add_argument("--snapshot-root", required=True, type=Path)
    parser.add_argument("--config-root", type=Path, default=Path(DEFAULT_CONFIG_ROOT))
    parser.add_argument("--acquire", action="store_true")
    parser.add_argument("--freeze-descriptor", type=Path)
    parser.add_argument("--generation", type=int)


def dispatch_onboard_command(args: argparse.Namespace) -> int | None:
    """Run ``onboard``, or return ``None`` for any other command."""
    if args.command != ONBOARD_COMMAND:
        return None
    try:
        return _onboard(args)
    except OriginalExpiredError as error:  # R13: names the expired capture
        sys.stderr.write(f"onboard {args.symbol} refused: {error}\n")
        return RunExitStatus.FAILURE
    except _FAILURES as error:
        structlog.get_logger().error("onboard_failed", error=type(error).__name__)
        return RunExitStatus.FAILURE


class Onboarded(BaseModel):
    """What one onboarding recorded, the printed ``compare run`` command and its exit."""

    model_config = ConfigDict(frozen=True)

    outcome: OnboardingOutcome
    reason: str | None
    states: dict[VerificationUnit, Verdict]
    entity_id: int | None
    onboarding_record_id: int
    compare: str | None
    exit: int


def _onboard(args: argparse.Namespace) -> int:
    """Onboard and print the outcome, each unit's state and any ``compare run`` command."""
    done = onboard(args)
    sys.stdout.write(f"onboard {args.symbol}: {done.outcome.value}")
    if done.outcome is OnboardingOutcome.IDENTITY_CONFLICT:
        sys.stdout.write(f" severity {_SEVERITY_HIGH}")
    sys.stdout.write(f" {done.reason or ''}\n")
    for unit, (state, why) in done.states.items():
        sys.stdout.write(f"  {unit.value}: {state.value} {why or ''}\n")
    if done.compare is not None:
        sys.stdout.write(f"{COMPARE_PREFIX}{done.compare}\n")
    return done.exit


def onboard(args: argparse.Namespace) -> Onboarded:
    """Acquire or replay, discover, record; an admitted issuer's settings, ingest and the
    ``compare run`` command follow (D5). ``args`` is a parsed ``onboard`` command line."""
    if args.acquire and args.generation is not None:
        raise ValueError(_ACQUIRE_GENERATION)
    acquisition = _frozen(args.freeze_descriptor, args.config_root) if args.acquire else None
    config = load_run_config(args.config_root, ONBOARDING_VERSIONS)
    root: Path = args.raw_root
    taken = sorted(
        int(path.name.removeprefix(GENERATION_PREFIX))
        for path in root.glob(f"{GENERATION_PREFIX}*")
    )
    log: list[discovery.Capture] = []
    if acquisition is None:
        generation = args.generation
        if generation is None:
            generation = max(n for n in taken if _complete(root, n))
        folder = root / f"{GENERATION_PREFIX}{generation}"
        authorization = _manifest(root, generation).authorization
        fetch = replay_fetch(folder)
    else:
        generation = (taken[-1] if taken else 0) + 1
        folder = root / f"{GENERATION_PREFIX}{generation}"
        fetch = acquiring_fetch(live_transport(), now, log)
        authorization = f"freeze {acquisition['descriptor_commit']}"
        acquisition = {"generation": generation, **acquisition, "argv": _argv(args)}
    derived, package = None, None
    with open_pool(PgSettings(), PgRole.RUNTIME) as pool:
        try:
            with pool.connection() as conn:
                found = discover(args.symbol, fetch, conn, SURFACES, config.mapping_set)
            if outcome(found.states)[0] in _ADMITTED:
                derived = derive(found)
                package = package_manifest(args.symbol, authorization, derived.filings)
        finally:
            if acquisition is not None and log:
                write_generation(folder, args.symbol, authorization, generation, log)
                if package is not None:
                    (folder / RETRIEVAL_NAME).write_bytes(package)
                shas = {
                    "discovery_manifest_sha256": _sha256((folder / MANIFEST_NAME).read_bytes()),
                    "retrieval_manifest_sha256": package and _sha256(package),
                }
                document = json.dumps({**acquisition, **shas}, indent=1)
                (folder / ACQUISITION_NAME).write_text(document)
        store = SnapshotStore(args.snapshot_root)
        with store.prepare_ordinary_output():
            refs = store_captures(store, EvidenceRepository(pool), found.captures)
        with pool.connection() as conn:
            recorded = record(conn, found, refs)
            (record_id,) = conn.execute(_RECORD_ID_SQL, (args.symbol,)).fetchone() or (0,)
        command = None
        if derived is not None and package is not None and recorded.entity_id is not None:
            command = _ingest(pool, args, config, found, refs, derived, package, recorded, folder)
    return Onboarded(
        outcome=recorded.outcome,
        reason=recorded.reason,
        states=found.states,
        entity_id=recorded.entity_id,
        onboarding_record_id=record_id,
        compare=command,
        exit=_EXIT.get(recorded.outcome, RunExitStatus.FAILURE),
    )


def _manifest(root: Path, generation: int) -> DiscoveryManifest:
    """A generation's discovery manifest, which must name that generation."""
    folder = root / f"{GENERATION_PREFIX}{generation}"
    manifest = DiscoveryManifest.model_validate_json((folder / MANIFEST_NAME).read_bytes())
    if manifest.generation != generation:
        raise ValueError(_WRONG_GENERATION.format(n=generation))
    return manifest


def _complete(root: Path, generation: int) -> bool:
    """Its manifest is present and valid (an interrupted write leaves none)."""
    try:
        _manifest(root, generation)
    except (OSError, ValueError):
        return False
    return True


def _argv(args: argparse.Namespace) -> list[str]:
    """The acquiring command line, as parsed."""
    return [
        *(ONBOARD_COMMAND, args.symbol, "--raw-root", str(args.raw_root)),
        *("--snapshot-root", str(args.snapshot_root), "--config-root", str(args.config_root)),
        *("--acquire", "--freeze-descriptor", str(args.freeze_descriptor)),
    ]


def package_manifest(issuer: str, authorization: str, filings: Sequence[Filing]) -> bytes:
    """The XBRL-only ``retrieval-manifest.json`` of the verified filings, in the intake format
    (``quarter`` is the period end)."""
    entries = [
        {
            "quarter": filing.period_end.isoformat(),
            "kind": XBRL_KIND,
            "url": filing.url,
            "filename": _filename(filing),
            "sha256": _sha256(filing.body),
            "bytes": len(filing.body),
            "filed_at_nse": filing.filed_at.strftime(NSE_FILED_AT_FORMAT),
            "retrieved_at": filing.retrieved_at.isoformat(),
        }
        for filing in filings
    ]
    document = {"issuer": issuer, "authorization": authorization, "entries": entries}
    return json.dumps(document, indent=1).encode()


def _ingest(
    pool: ConnectionPool,
    args: argparse.Namespace,
    config: LoadedConfig,
    found: Discovery,
    refs: Sequence[tuple[VerificationUnit, CaptureReference]],
    derived: DerivedSettings,
    package: bytes,
    recorded: Recorded,
    folder: Path,
) -> str:
    """Settings, then the latest filing's XBRL-only package, each verified vendor capture and
    the PDF exclusion attempt; returns the ``compare run`` command."""
    entity_id = recorded.entity_id
    assert entity_id is not None
    with pool.connection() as conn:
        derived_settings.write(conn, entity_id, derived, recorded.inputs)
        (key,) = conn.execute(_ENTITY_KEY_SQL, (entity_id,)).fetchone() or ("",)
    repository = EvidenceRepository(pool)
    latest = derived.filings[0]
    period = latest.period_end
    month = int(derived.value(SettingKey.FISCAL_YEAR_END_MONTH, period))
    with tempfile.TemporaryDirectory(dir=args.raw_root) as staging:
        inputs = Path(staging)
        (inputs / XBRL_INPUT_DIR).mkdir()
        for filing in derived.filings:
            (inputs / XBRL_INPUT_DIR / _filename(filing)).write_bytes(filing.body)
        (inputs / RETRIEVAL_NAME).write_bytes(package)
        intake = retained_intake_from_manifest(
            inputs / RETRIEVAL_NAME,
            issuer=found.symbol,
            quarter=period.isoformat(),
            kinds={Representation.XBRL: XBRL_KIND},
            store_root=args.snapshot_root.absolute(),
            input_root=inputs.absolute(),
            issuer_config=None,
        )
        report = ingest_first_party(
            intake=intake,
            catalog=BUILTIN_SOURCES,
            snapshot_store=SnapshotStore(args.snapshot_root),
            repository=repository,
            dictionary=config.dictionary,
            mapping_set=config.mapping_set,
            policy=config.normalisation_policy,
            entity_id=entity_id,
            basis=Basis.CONSOLIDATED,
            framework=AccountingFramework.IND_AS,
            family=FilingFamily.FINANCIAL_RESULTS,
            reporting_period_end=period,
            pdf_specs=None,
        )
    failed = [a.outcome for a in report.attempts if a.outcome is not ExtractionOutcome.COMPLETE]
    if report.package_id is None or failed:
        raise OnboardingIngestError(_INGEST_FAILED.format(what=XBRL_KIND, outcome=failed))
    stored = {
        (item.request.source_id, item.request.surface): (item.response.body or b"", ref)
        for item, (_, ref) in zip(found.captures, refs, strict=True)
    }
    verified = {u for u, (state, _) in found.states.items() if state is VerificationState.VERIFIED}
    for pair, representation, extract, version in _vendor_adapters(
        args.config_root, found, stored, verified, month, recorded.inputs
    ):
        ref = stored[pair][1]
        vendor = ingest_vendor_retained(
            VendorIngestRequest(
                source_id=pair[0],
                surface=pair[1],
                request_key=ref.request_key,
                capture_id=ref.capture_id,
                representation=representation,
                entity_id=entity_id,
                period_end=period,
                basis=Basis.CONSOLIDATED,
                framework=AccountingFramework.IND_AS,
            ),
            extract=extract,
            extractor_version=version,
            snapshot_store=SnapshotStore(args.snapshot_root),
            repository=repository,
            dictionary=config.dictionary,
            mapping_set=config.mapping_set,
            policy=config.normalisation_policy,
            rounding_policy=config.rounding,
            fiscal_year_end_month=month,
        )
        if vendor.attempt.outcome is not ExtractionOutcome.COMPLETE:
            raise OnboardingIngestError(
                _INGEST_FAILED.format(what="/".join(pair), outcome=vendor.attempt.outcome)
            )
    exclude_pdf(repository, entity_id, period, _sha256((folder / MANIFEST_NAME).read_bytes()))
    return compare_command(key, period, args.config_root)


def compare_command(entity: str, period_end: date, config_root: Path) -> str:
    """The ``compare run`` command under ``ONBOARDING_VERSIONS`` and onboarding's config root,
    shell-quoted (an entity key such as ``M&M`` stays one argument)."""
    vendors = [
        arg
        for unit, surface in UNIT_SURFACES.items()
        if unit is not VerificationUnit.RESULTS_PDF
        for arg in ("--vendor", surface)
    ]
    return shlex.join(
        [
            *("fundamentals", "compare", "run", "--entity", entity),
            *("--period-end", period_end.isoformat(), "--basis", "consolidated"),
            *("--mode", "as_known", "--config-root", str(config_root)),
            *("--dictionary", ONBOARDING_VERSIONS.dictionary),
            *("--mapping-set", ONBOARDING_VERSIONS.mapping_set, *vendors),
        ]
    )


def _vendor_adapters(
    config_root: Path,
    found: Discovery,
    stored: Mapping[tuple[str, str], tuple[bytes, CaptureReference]],
    verified: set[VerificationUnit],
    month: int,
    inputs: Mapping[VerificationUnit, int],
) -> Iterator[tuple[tuple[str, str], Representation, Any, str]]:
    """Each verified vendor unit's comparison capture and adapter, its binding read from the
    verified bytes: Screener once per page section (as Stage 1), Tijori, Upstox."""
    if VerificationUnit.SCREENER in verified:
        page = stored[SCREENER_PAGE][0].decode("utf-8", errors="replace")
        company_id, warehouse_id = read_identity(parse_document(page))
        binding = ScreenerIssuerBinding(
            symbol=found.symbol,
            company_id=company_id,
            bse_code=found.scrip or "",
            topology=BasisTopology(consolidated_warehouse_id=warehouse_id),
            identity_evidence_ref=_EVIDENCE_REF.format(id=inputs[VerificationUnit.SCREENER]),
            fiscal_year_end_month=month,
        )
        for section in SCREENER_SECTIONS:
            yield (
                SCREENER_PAGE,
                Representation.HTML,
                partial(_screener, binding=binding, section=section),
                vendor_screener.EXTRACTOR_VERSION,
            )
    if VerificationUnit.TIJORI in verified:
        slug = tijori_candidate(stored[TIJORI_SEARCH][0])
        collector = JsonScriptCollector((COMPANY_DETAILS_ISLAND,))
        collector.feed(decode_document(stored[TIJORI_PAGE][0], page_label=FINANCIALS_PAGE_LABEL))
        collector.close()
        details = json.loads(collector.islands[COMPANY_DETAILS_ISLAND])
        tijori = partial(
            vendor_tijori.extract_tijori,
            binding=vendor_tijori.TijoriBinding(
                slug=str(slug), symbol=found.symbol, company_id=details[_TIJORI_COMPANY_ID]
            ),
            display=vendor_tijori.load_tijori_display(config_root / TIJORI_DISPLAY),
            basis=Basis.CONSOLIDATED,
        )
        yield (
            TIJORI_PAGE,
            Representation.HTML,
            tijori,
            vendor_tijori.EXTRACTOR_VERSION,
        )
    if VerificationUnit.UPSTOX in verified:
        upstox = partial(vendor_upstox.extract_upstox, basis=Basis.CONSOLIDATED)
        yield (
            UPSTOX_STATEMENT,
            Representation.JSON,
            upstox,
            vendor_upstox.EXTRACTOR_VERSION,
        )


def _screener(
    body: bytes,
    *,
    capture: CaptureReference,
    record: Any,
    extractor_version: str,
    binding: ScreenerIssuerBinding,
    section: Section,
) -> VendorExtraction:
    """The Screener page adapter in the ``ingest_vendor`` shape (it reads no record)."""
    del record
    return vendor_screener.extract_screener_page(
        body,
        capture=capture,
        binding=binding,
        basis=Basis.CONSOLIDATED,
        section=section,
        extractor_version=extractor_version,
    )


def exclude_pdf(
    repository: EvidenceRepository, entity_id: int, period_end: date, discovery_sha256: str
) -> None:
    """R-PDF (C1): a capture-less ``EXCLUDED_BY_RULE`` acquisition attempt, so the run imposes
    ``UNAVAILABLE`` on the PDF side rather than reading an absent member as ``NO_VALUE``."""
    repository.put_attempts(
        [
            AcquisitionAttempt(
                attempt_id=None,
                stage=AttemptStage.ACQUISITION,
                source_id=NSE_RESULTS_PDF_SOURCE,
                surface=FirstPartySurface.NSE_RESULTS_PDF.value,
                entity_id=entity_id,
                period_end=period_end,
                basis=Basis.CONSOLIDATED,
                framework=AccountingFramework.IND_AS,
                representation=Representation.PDF,
                statement_family=None,
                package_id=None,
                outcome=ExtractionOutcome.EXCLUDED_BY_RULE,
                reason=RULING_PDF,
                capture=None,
                input_sha256=discovery_sha256,
                extractor_version="",
                attempted_at=None,
            )
        ]
    )


def _filename(filing: Filing) -> str:
    """The instance's file name as NSE publishes it."""
    return filing.url.rsplit("/", 1)[-1]


def _sha256(body: bytes) -> str:
    """Hex SHA-256."""
    return hashlib.sha256(body).hexdigest()


def _frozen(descriptor: Path | None, config_root: Path) -> dict[str, Any]:
    """C5: the freeze protocol's checks over ``HEAD``'s committed descriptor entry, in the
    running checkout with its own ``config``, and what the acquisition records of them
    (``freeze_descriptor_sha256`` hashes the entry as ``yaml.safe_dump(sort_keys=True)``, the
    D1.1 payload rule)."""
    if descriptor is None:
        raise ValueError(_NEEDS_DESCRIPTOR)
    repo = Path(_git(descriptor.resolve().parent, "rev-parse", "--show-toplevel")).resolve()
    if repo != SOURCE_CHECKOUT.resolve():
        raise ValueError(_UNFROZEN.format(why="the descriptor is not in the running checkout"))
    if config_root.resolve() != (repo / DEFAULT_CONFIG_ROOT).resolve():
        raise ValueError(_UNFROZEN.format(why="--config-root is not the checkout's config"))
    path = str(descriptor.resolve().relative_to(repo))
    if _git(repo, "status", "--porcelain", "--", *IMPLEMENTATION_PATHS, path, HOLDOUT_RECORD):
        raise ValueError(_UNFROZEN.format(why="uncommitted changes"))
    head = _git(repo, "rev-parse", "HEAD")
    entry = _freezes(repo, head, path)[-1]
    _check_entry(repo, head, entry)
    commits = _git(repo, "log", "--reverse", "--format=%H", "--", path).split()
    holding = [commit for commit in commits if entry in _freezes(repo, commit, path)]
    implementation = str(entry[_IMPLEMENTATION])
    _git(repo, "merge-base", "--is-ancestor", implementation, holding[0])
    if _git(repo, "rev-list", f"{implementation}..{head}", "--", *IMPLEMENTATION_PATHS):
        raise ValueError(_UNFROZEN.format(why="an implementation commit since the freeze"))
    return {
        "attempt": entry["attempt"],
        "freeze_descriptor_sha256": _sha256(yaml.safe_dump(entry, sort_keys=True).encode()),
        "descriptor_commit": holding[0],
        "acquisition_head": head,
        "implementation_commit": implementation,
    }


def _check_entry(repo: Path, head: str, entry: Any) -> None:
    """D6 step 2: every descriptor field present, an ``APPROVE`` review, the inputs, tree and
    configuration pin of the implementation commit, and the current unburned held-out attempt
    with its payload hash (D1.1)."""

    def need(ok: bool, why: str) -> None:
        if not ok:
            raise ValueError(_UNFROZEN.format(why=why))

    need(isinstance(entry, dict) and set(entry) == _ENTRY_KEYS, "descriptor entry fields")
    review = entry["review"]
    need(isinstance(review, dict) and set(review) == _REVIEW_KEYS, "review fields")
    need(review["verdict"] == _APPROVE, "review is not APPROVE")
    need(entry["inputs"] == list(IMPLEMENTATION_PATHS), "inputs")
    need(entry["tree"] == _tree(repo, str(entry[_IMPLEMENTATION])), "tree")
    pinned = ConfigVersions.model_validate(entry["onboarding_versions"])
    need(pinned == ONBOARDING_VERSIONS, "onboarding_versions")
    record = yaml.safe_load(_git(repo, "show", f"{head}:{HOLDOUT_RECORD}"))
    attempts, burns = record["attempts"], record["burns"] or []
    current = attempts[-1]
    need(len(burns) == len(attempts) - 1, "no current attempt")
    need(entry["attempt"] == current["n"], "not the current attempt")
    payload = {key: value for key, value in current.items() if key != "approval"}
    digest = _sha256(yaml.safe_dump(payload, sort_keys=True).encode())
    need(entry["holdout_payload_sha256"] == digest, "holdout payload")


def _tree(repo: Path, commit: str) -> dict[str, str]:
    """``{path: git object id}`` of each implementation path at ``commit``."""
    listing = _git(repo, "ls-tree", commit, "--", *IMPLEMENTATION_PATHS).splitlines()
    return {line.split("\t")[1]: line.split()[2] for line in listing}


def _freezes(repo: Path, commit: str, path: str) -> list[Any]:
    """The descriptor's entries at ``commit``."""
    return list(yaml.safe_load(_git(repo, "show", f"{commit}:{path}"))[_FREEZES])


def _git(repo: Path, *args: str) -> str:
    """One git command's stdout; a non-zero exit raises."""
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()
