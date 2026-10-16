"""The ``onboard`` command: discover, verify and record one NSE symbol (plan D6 D4).

    onboard <SYMBOL> --raw-root <dir> --snapshot-root <dir> [--config-root config]
        [--acquire --freeze-descriptor <path>]

Replay (the default) reads the latest ``gen-<n>`` discovery generation under ``--raw-root`` and
never opens a socket. ``--acquire`` writes the next generation through the live transport, and
only on a checkout that satisfies the freeze protocol (C5): the descriptor's current entry
committed at ``HEAD``, its implementation commit an ancestor of the first commit holding the
entry, and no implementation path changed since or uncommitted. An admitted issuer
(``ONBOARDED``/``PARTIAL``) then gets its derived settings, the latest verified filing as an
XBRL-only package, each verified vendor capture, the R-PDF exclusion attempt (D5) and the
printed ``compare run`` command under ``ONBOARDING_VERSIONS``. Exit: ``ONBOARDED`` 0,
``PARTIAL`` 4, anything else (including an abort) 5. Failures never echo a transport message,
so a credential a server reflects lands nowhere.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from collections.abc import Iterator, Mapping, Sequence
from datetime import UTC, date, datetime
from functools import partial
from pathlib import Path
from typing import Any, LiteralString

import psycopg
import structlog
import yaml
from psycopg_pool import ConnectionPool

from fundamentals.api.env_credentials import (
    _screener_credentials_from_env,
    _tijori_credentials_from_env,
    _upstox_credentials_from_env,
)
from fundamentals.compare.run_config import LoadedConfig, load_run_config
from fundamentals.compare.run_models import RunExitStatus
from fundamentals.contracts.acquisition_outcome import ExtractionOutcome
from fundamentals.contracts.canonical import Basis, Representation
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
    VerificationState,
    VerificationUnit,
)
from fundamentals.contracts.snapshot import SnapshotError
from fundamentals.contracts.source_catalog import (
    BUILTIN_SOURCES,
    SCREENER_PAGE,
    TIJORI_PAGE,
    TIJORI_SEARCH,
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
from fundamentals.entity.verification import outcome, tijori_candidate
from fundamentals.evidence import vendor_screener, vendor_tijori, vendor_upstox
from fundamentals.evidence.capture_intake import (
    NSE_FILED_AT_FORMAT,
    XBRL_INPUT_DIR,
    FirstPartySurface,
    retained_intake_from_manifest,
)
from fundamentals.evidence.first_party_ingest import ingest_first_party
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.evidence.vendor_ingest import (
    VendorExtraction,
    VendorIngestRequest,
    ingest_vendor,
)
from fundamentals.evidence.vendor_screener import ScreenerIssuerBinding
from fundamentals.ingest.http_session import NoRedirectHandler, read_bounded
from fundamentals.ingest.nse_filings import NSE_API
from fundamentals.ingest.screener_financials_models import Section
from fundamentals.ingest.screener_session_models import BasisTopology
from fundamentals.ingest.screener_session_page import parse_document, read_identity
from fundamentals.ingest.tijori_capture import COMPANY_DETAILS_ISLAND, FINANCIALS_PAGE_LABEL
from fundamentals.ingest.tijori_page import JsonScriptCollector, decode_document
from fundamentals.pg.identity_seed import SettingKey
from fundamentals.pg.pool import DatabaseUnavailableError, open_pool
from fundamentals.pg.settings import PgRole, PgSettings
from fundamentals.store.snapshot_store import MAX_BODY_BYTES, SnapshotStore

ONBOARD_COMMAND = "onboard"
DEFAULT_CONFIG_ROOT = "config"
ACQUISITION_NAME = "acquisition.json"
GENERATION_PREFIX = "gen-"
IMPLEMENTATION_PATHS = ("src", "config", "migrations", "scripts", "pyproject.toml", "uv.lock")
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
COMPARE_COMMAND = (
    "fundamentals compare run --entity {entity} --period-end {period_end} --basis consolidated "
    "--mode as_known --dictionary {dictionary} --mapping-set {mapping_set}{vendors}"
)
_ADMITTED = (OnboardingOutcome.ONBOARDED, OnboardingOutcome.PARTIAL)
_TIJORI_COMPANY_ID = "company_id"
_EVIDENCE_REF = "evidence_input:{id}"
_ENTITY_KEY_SQL: LiteralString = "SELECT entity_key FROM eqos.reporting_entities WHERE id = %s"
_FREEZES = "freezes"
_IMPLEMENTATION = "implementation_commit"
_AGENT = "Mozilla/5.0 (equity-os onboarding)"
_SESSION_COOKIE = "sessionid={value}"
_HELP = "discover, verify and record one NSE symbol (D6)"
_NEEDS_DESCRIPTOR = "--acquire needs --freeze-descriptor"
_UNFROZEN = "the checkout does not satisfy the freeze protocol: {why}"
_SEVERITY_HIGH = "HIGH"
_EXIT = {
    OnboardingOutcome.ONBOARDED: RunExitStatus.SUCCESS,
    OnboardingOutcome.PARTIAL: RunExitStatus.INCOMPLETE,
}
_FAILURES = (
    OnboardingAbortError,
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


def live_transport() -> Send:
    """``send(request) -> (status, body)`` over HTTPS with each source's own credential;
    redirects are refused (a login bounce is a failure, not a page)."""
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
            from nse import NSE  # type: ignore[import-untyped]

            with (
                tempfile.TemporaryDirectory() as folder,
                NSE(folder, timeout=TIMEOUT_SECONDS) as client,
            ):
                response = client._req(request.url)
                return int(response.status_code), bytes(response.content)
        headers = {"User-Agent": _AGENT}
        cookie = cookies.get(request.source_id)
        if cookie:
            headers["Cookie"] = _SESSION_COOKIE.format(value=cookie.get_secret_value())
        if (request.source_id, request.surface) == UPSTOX_STATEMENT and upstox:
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


def dispatch_onboard_command(args: argparse.Namespace) -> int | None:
    """Run ``onboard``, or return ``None`` for any other command."""
    if args.command != ONBOARD_COMMAND:
        return None
    try:
        return _onboard(args)
    except _FAILURES as error:
        structlog.get_logger().error("onboard_failed", error=type(error).__name__)
        return RunExitStatus.FAILURE


def _onboard(args: argparse.Namespace) -> int:
    """Acquire or replay, discover, record; an admitted issuer's settings, ingest and the
    ``compare run`` command follow (D5)."""
    acquisition = _frozen(args.freeze_descriptor) if args.acquire else None
    config = load_run_config(args.config_root, ONBOARDING_VERSIONS)
    root: Path = args.raw_root
    taken = sorted(
        int(path.name.removeprefix(GENERATION_PREFIX))
        for path in root.glob(f"{GENERATION_PREFIX}*")
    )
    log: list[discovery.Capture] = []
    if acquisition is None:
        folder = root / f"{GENERATION_PREFIX}{taken[-1]}"
        fetch = replay_fetch(folder)
        authorization = DiscoveryManifest.model_validate_json(
            (folder / MANIFEST_NAME).read_bytes()
        ).authorization
    else:
        generation = (taken[-1] if taken else 0) + 1
        folder = root / f"{GENERATION_PREFIX}{generation}"
        fetch = acquiring_fetch(live_transport(), now, log)
        authorization = f"freeze {acquisition['descriptor_commit']}"
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
        command = None
        if derived is not None and package is not None and recorded.entity_id is not None:
            command = _ingest(pool, args, config, found, refs, derived, package, recorded, folder)
    result = recorded.outcome
    sys.stdout.write(f"onboard {args.symbol}: {result.value}")
    if result is OnboardingOutcome.IDENTITY_CONFLICT:
        sys.stdout.write(f" severity {_SEVERITY_HIGH}")
    sys.stdout.write(f" {recorded.reason or ''}\n")
    for unit, (state, why) in found.states.items():
        sys.stdout.write(f"  {unit.value}: {state.value} {why or ''}\n")
    if command is not None:
        sys.stdout.write(f"{COMPARE_PREFIX}{command}\n")
    return _EXIT.get(result, RunExitStatus.FAILURE)


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
        ingest_first_party(
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
    stored = {
        (item.request.source_id, item.request.surface): (item.response.body or b"", ref)
        for item, (_, ref) in zip(found.captures, refs, strict=True)
    }
    verified = {u for u, (state, _) in found.states.items() if state is VerificationState.VERIFIED}
    for pair, representation, extract, version in _vendor_adapters(
        args.config_root, found, stored, verified, month, recorded.inputs
    ):
        ref = stored[pair][1]
        ingest_vendor(
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
    exclude_pdf(repository, entity_id, period, _sha256((folder / MANIFEST_NAME).read_bytes()))
    vendors = "".join(
        f" --vendor {surface}"
        for unit, surface in UNIT_SURFACES.items()
        if unit is not VerificationUnit.RESULTS_PDF
    )
    return COMPARE_COMMAND.format(
        entity=key,
        period_end=period.isoformat(),
        dictionary=ONBOARDING_VERSIONS.dictionary,
        mapping_set=ONBOARDING_VERSIONS.mapping_set,
        vendors=vendors,
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


def _frozen(descriptor: Path | None) -> dict[str, str]:
    """C5: the freeze protocol's checks, and what the acquisition records of them."""
    if descriptor is None:
        raise ValueError(_NEEDS_DESCRIPTOR)
    repo = Path(_git(descriptor.resolve().parent, "rev-parse", "--show-toplevel"))
    path = str(descriptor.resolve().relative_to(repo.resolve()))
    if _git(repo, "status", "--porcelain", "--", *IMPLEMENTATION_PATHS, path):
        raise ValueError(_UNFROZEN.format(why="uncommitted changes"))
    entry = yaml.safe_load(descriptor.read_text())[_FREEZES][-1]
    head = _git(repo, "rev-parse", "HEAD")
    commits = _git(repo, "log", "--reverse", "--format=%H", "--", path).split()
    holding = [commit for commit in commits if entry in _freezes(repo, commit, path)]
    if not holding or entry not in _freezes(repo, head, path):
        raise ValueError(_UNFROZEN.format(why="entry not committed at HEAD"))
    implementation = str(entry[_IMPLEMENTATION])
    _git(repo, "merge-base", "--is-ancestor", implementation, holding[0])
    _git(repo, "diff", "--quiet", implementation, head, "--", *IMPLEMENTATION_PATHS)
    return {
        "acquisition_head": head,
        "descriptor_commit": holding[0],
        "implementation_commit": implementation,
        "freeze_descriptor": path,
    }


def _freezes(repo: Path, commit: str, path: str) -> list[Any]:
    """The descriptor's entries at ``commit``."""
    return list(yaml.safe_load(_git(repo, "show", f"{commit}:{path}"))[_FREEZES])


def _git(repo: Path, *args: str) -> str:
    """One git command's stdout; a non-zero exit raises."""
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()
