"""Shared fixtures of the D6 onboarding tests: fixture worlds, replay roots and database reads.

Worlds are built from ``fixtures/onboarding`` (retained originals pinned by SHA-256, committed
rows, labelled synthetic edits). Synthetic identifiers are ``ZZ``-prefixed. No socket is opened.
"""

from __future__ import annotations

import gzip
import hashlib
import os
import subprocess
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml
from pg_support import PgTestDatabase, create_database, drop_database, mint_name
from retained_support import REPO_ROOT

from fundamentals.api import onboard_cli
from fundamentals.api.cli import main
from fundamentals.api.onboard_cli import HOLDOUT_RECORD, IMPLEMENTATION_PATHS
from fundamentals.contracts.basis_status import BasisStatus
from fundamentals.contracts.entity_identity import IdentifierNamespace
from fundamentals.contracts.onboarding import (
    OnboardingOutcome,
    OnboardingReason,
    VerificationState,
    VerificationUnit,
)
from fundamentals.entity.discovery import (
    MANIFEST_NAME,
    DiscoveryManifest,
    ManifestEntry,
    request_key,
)
from fundamentals.entity.entity_map import isin_check_digit
from fundamentals.entity.identity_layers import (
    IdentifierRef,
    IdentityEventKind,
    latest_slice,
    record_event,
)
from fundamentals.pg.identity_seed import (
    EvidenceInputKind,
    IssuerIdentityInput,
    seed_issuer_identity,
)

FIXTURES = Path(__file__).parent / "fixtures" / "onboarding"
SPEC = yaml.safe_load((FIXTURES / "fixtures.yaml").read_text())
DEV = REPO_ROOT / "data" / "raw" / "onboarding-dev"
U, S, R, OC = VerificationUnit, VerificationState, OnboardingReason, OnboardingOutcome
APAR, APAR_ISIN, APAR_SCRIP = "APARINDS", "INE372A01015", "532259"
JUN, MAR = "1701114", "1675395"  # the two latest consolidated Apar instances (FY27 Q1, FY26 Q4)
AS_OF = date(2026, 10, 16)
FAILURE, INCOMPLETE = 5, 4
VERIFIED_FIVE = {U.EXCHANGE, U.XBRL_ENTITY, U.SCREENER, U.TIJORI, U.UPSTOX}
SENTINEL = "zzSENTINELcredential0123456789"
SYNTHETIC_NOTICE = b"SYNTHETIC identity notice for tests; no exchange published this."


def synthetic_isin(body: str) -> str:
    """A synthetic ISIN with a valid check digit."""
    return body + isin_check_digit(body)


ZZ_ISIN = synthetic_isin("INZZ0000001")


def world(symbol: str) -> list[dict[str, Any]]:
    """The company's fixture responses with their bytes, retained ones pinned."""
    served = []
    for item in SPEC["companies"][symbol]:
        if "retained" in item:
            path = REPO_ROOT / item["retained"]["path"]
            if not path.is_file():
                pytest.fail(f"retained original missing: {path}", pytrace=False)
            body = path.read_bytes()
            if hashlib.sha256(body).hexdigest() != item["retained"]["sha256"]:
                pytest.fail(f"retained original {path} differs from its pin", pytrace=False)
        else:
            body = (FIXTURES / item["file"]).read_bytes()
            if item.get("gzip"):
                body = gzip.compress(body, mtime=0)
        served.append({**item, "body": body, "outcome": "OK"})
    return served


def edit(served: list[dict[str, Any]], url_part: str, old: bytes, new: bytes) -> None:
    """SYNTHETIC: replace bytes in every response whose URL contains ``url_part``."""
    hits = [item for item in served if url_part in item["url"]]
    assert hits and all(old in item["body"] for item in hits), url_part
    for item in hits:
        item["body"] = item["body"].replace(old, new)


def rename(served: list[dict[str, Any]], old: str, new: str, keep: tuple[str, ...] = ()) -> None:
    """SYNTHETIC: carry ``new`` instead of ``old`` everywhere (URLs too) except ``keep``."""
    for item in served:
        item["url"] = item["url"].replace(old, new)
        if not any(part in item["url"] for part in keep):
            body = item["body"]
            if item.get("gzip"):
                body = gzip.decompress(body).replace(old.encode(), new.encode())
                item["body"] = gzip.compress(body, mtime=0)
            else:
                item["body"] = body.replace(old.encode(), new.encode())


def write_root(root: Path, served: list[dict[str, Any]], symbol: str, generation: int = 1) -> Path:
    """A replay generation in the discovery-manifest format."""
    folder = root / f"gen-{generation}"
    folder.mkdir(parents=True)
    retrieved_at = datetime.fromisoformat(SPEC["retrieved_at"])
    entries = []
    for index, item in enumerate(served):
        name = None
        if item["body"] is not None and item["outcome"] == "OK":
            name = f"{index:02d}.bin"
            (folder / name).write_bytes(item["body"])
        entries.append(
            ManifestEntry(
                request_key=request_key(item["surface"], item["url"]),
                source_id=item["source_id"],
                surface=item["surface"],
                unit=item["unit"],
                url=item["url"],
                filename=name,
                sha256=hashlib.sha256(item["body"]).hexdigest() if name else None,
                bytes=len(item["body"]) if name else None,
                retrieved_at=retrieved_at,
                outcome=item["outcome"],
            )
        )
    manifest = DiscoveryManifest(
        issuer=symbol,
        authorization="test fixtures",
        generation=generation,
        as_of=AS_OF,
        entries=tuple(entries),
    )
    (folder / MANIFEST_NAME).write_text(manifest.model_dump_json(indent=1))
    return root


@pytest.fixture
def cli(
    pg_db: PgTestDatabase, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Callable[..., int]:
    """``main(["onboard", …])`` in replay against this test's database."""
    for name, value in pg_db.cli_env().items():
        monkeypatch.setenv(name, value)

    def run(symbol: str, root: Path, *extra: str) -> int:
        return main(
            [
                "onboard",
                symbol,
                "--raw-root",
                str(root),
                "--snapshot-root",
                str(tmp_path / "snapshots"),
                *extra,
            ]
        )

    return run


@pytest.fixture
def requested(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Surfaces the replay fetch was asked for, in order (a fetch spy)."""
    seen: list[str] = []
    real = onboard_cli.replay_fetch

    def spied(folder: Path) -> Any:
        fetch = real(folder)

        def call(request: Any, allowed: bool) -> Any:
            seen.append(request.surface)
            return fetch(request, allowed)

        return call

    monkeypatch.setattr(onboard_cli, "replay_fetch", spied)
    return seen


@contextmanager
def fresh_db(pg_template: PgTestDatabase) -> Iterator[PgTestDatabase]:
    """A second fresh database cloned from the session template."""
    name = mint_name(pg_template.settings)
    create_database(pg_template.settings, name, template=pg_template.dbname)
    try:
        yield pg_template.model_copy(update={"dbname": name})
    finally:
        drop_database(pg_template.settings, name)


def rows(db: PgTestDatabase, query: str, *params: object) -> list[tuple[Any, ...]]:
    """Rows of one read on the database."""
    with db.runtime_pool() as pool, pool.connection() as conn:
        return conn.execute(query, params).fetchall()  # type: ignore[arg-type]


def count(db: PgTestDatabase, table: str) -> int:
    """Rows in one ``eqos`` table."""
    return int(rows(db, f"SELECT count(*) FROM eqos.{table}")[0][0])


def recorded(db: PgTestDatabase) -> tuple[tuple[Any, ...], dict[str, tuple[str, str | None]]]:
    """The one onboarding record and its unit states."""
    (record,) = rows(
        db, "SELECT id, outcome, severity, reason, entity_id FROM eqos.onboarding_records"
    )
    states = rows(
        db,
        "SELECT unit, state, reason FROM eqos.namespace_verifications "
        "WHERE onboarding_record_id = %s",
        record[0],
    )
    return record, {unit: (state, reason) for unit, state, reason in states}


def evidence_counts(db: PgTestDatabase) -> tuple[int, int]:
    """Occurrences and interpretations stored."""
    return count(db, "occurrences"), count(db, "interpretations")


def table_counts(db: PgTestDatabase) -> tuple[int, int, int]:
    """Entities, securities and listings."""
    return count(db, "reporting_entities"), count(db, "securities"), count(db, "listings")


def seed(db: PgTestDatabase, key: str, isin: str, nse: str, bse: str) -> int:
    """A synthetic D1a issuer; returns its entity id."""
    with db.runtime_pool() as pool, pool.connection() as conn:
        return seed_on(conn, key, isin, nse, bse)


def seed_on(conn: Any, key: str, isin: str, nse: str, bse: str) -> int:
    """:func:`seed` on ``conn`` (inside its open transaction, if any)."""
    identity = IssuerIdentityInput(
        entity_key=key,
        display_name=f"{key} Synthetic Limited",
        isin=isin,
        share_class="EQUITY",
        nse_symbol=nse,
        bse_scrip=bse,
        basis_status=BasisStatus.CONSOLIDATED_AND_STANDALONE,
        fiscal_year_end_month=3,
        citations=(),
        content_sha256=hashlib.sha256(key.encode()).hexdigest(),
    )
    return seed_issuer_identity(conn, identity).entity_ids[key]


def event(
    conn: Any,
    kind: IdentityEventKind,
    on: date,
    ref: tuple[IdentifierNamespace, str],
    new: str,
) -> None:
    """Record a synthetic change of the target currently holding ``ref`` to ``new``."""
    sha = hashlib.sha256(SYNTHETIC_NOTICE + f"{kind}{new}".encode()).hexdigest()
    notice = conn.execute(
        "INSERT INTO eqos.evidence_inputs (kind, label, content_sha256) "
        "VALUES (%s, %s, %s) RETURNING id",
        (EvidenceInputKind.DISCOVERY.value, "synthetic-notice", sha),
    ).fetchone()
    assert notice is not None
    namespace, value = ref
    (target,) = {
        v.security_id if namespace is IdentifierNamespace.ISIN else v.listing_id
        for v in latest_slice(conn)
        if v.namespace is namespace and v.value == value
    }
    assert target is not None
    held = IdentifierRef(namespace=namespace, target_id=target)
    record_event(conn, kind, on, int(notice[0]), ends=[held], starts=[(held, new)])


def db_event(
    db: PgTestDatabase,
    kind: IdentityEventKind,
    on: date,
    ref: tuple[IdentifierNamespace, str],
    new: str,
) -> None:
    """:func:`event`, committed on its own connection."""
    with db.runtime_pool() as pool, pool.connection() as conn:
        conn.autocommit = True
        event(conn, kind, on, ref, new)


REVIEW = {"reviewer": "gpt-6.1-sol", "verdict": "APPROVE", "date": "2026-10-16"}


# --- freeze repos and the fixture transport ---------------------------------------------------


def git(repo: Path, *args: str) -> str:
    """One git command's stripped stdout."""
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def yaml_sha(mapping: dict[str, Any]) -> str:
    """SHA-256 of ``yaml.safe_dump(sort_keys=True)`` (the D1.1 payload rule)."""
    return hashlib.sha256(yaml.safe_dump(mapping, sort_keys=True).encode()).hexdigest()


def freeze_repo(tmp_path: Path, burned: bool = False) -> tuple[Path, str, dict[str, Any]]:
    """A git repo whose implementation commit holds ``src/`` and a synthetic held-out record
    (one attempt, burned or current); returns the complete descriptor entry for it."""
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "t@example.invalid")
    git(repo, "config", "user.name", "t")
    (repo / "src" / "impl.py").write_text("x = 1\n")
    attempt: dict[str, Any] = {
        "n": 1,
        "identifier": "ZZSYNTH",
        "prediction": {"outcome": "PARTIAL"},
    }
    payload = yaml_sha(attempt)
    attempt["approval"] = {**REVIEW, "payload_sha256": payload}
    burns = [{"attempt": 1, "reason_code": "ZZ", "bead": "zz", "date": "2026-10-16"}]
    record = repo / HOLDOUT_RECORD
    record.parent.mkdir(parents=True)
    record.write_text(yaml.safe_dump({"attempts": [attempt], "burns": burns if burned else []}))
    git(repo, "add", "src/impl.py", HOLDOUT_RECORD)
    git(repo, "commit", "-qm", "impl")
    implementation = git(repo, "rev-parse", "HEAD")
    entry = {
        "attempt": 1,
        "implementation_commit": implementation,
        "inputs": list(IMPLEMENTATION_PATHS),
        "tree": {"src": git(repo, "rev-parse", f"{implementation}:src")},
        "holdout_payload_sha256": payload,
        "onboarding_versions": {"dictionary": "v2", "mapping_set": "v5"},
        "review": dict(REVIEW),
    }
    return repo, implementation, entry


def freeze(repo: Path, *entries: dict[str, Any]) -> Path:
    """Commit the descriptor holding ``entries`` (the last current)."""
    descriptor = repo / "freeze.yaml"
    descriptor.write_text(yaml.safe_dump({"freezes": list(entries)}))
    git(repo, "add", "freeze.yaml")
    git(repo, "commit", "-qm", "freeze")
    return descriptor


def serving_transport(
    served: list[dict[str, Any]], echo: bool = False, sent: list[str] | None = None
) -> Callable[[Any], tuple[int, bytes]]:
    """A fake transport serving the fixtures by URL; ``echo`` leaks a credential on failure;
    ``sent`` collects every URL it was asked for."""
    bodies = {request_key(item["surface"], item["url"]): item["body"] for item in served}

    def send(request: Any) -> tuple[int, bytes]:
        if sent is not None:
            sent.append(request.url)
        if echo and request.surface == "company_search":
            raise OSError(f"refused with cookie {os.environ['TIJORI_SESSION_COOKIE']}")
        if echo and request.surface == "instruments":
            return 302, f"Location: https://x.invalid/?token={SENTINEL}".encode()
        return 200, bodies[request_key(request.surface, request.url)]

    return send
