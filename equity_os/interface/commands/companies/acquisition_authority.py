"""What authorises ``onboard --acquire``: the Stage 4 freeze protocol (C5) or a committed,
reviewed sanction (FIVE-1 Task 1), and the protected roots no sanctioned write may touch.

The sanction route never reads the held-out record, the manifest or the freeze descriptor."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any

import yaml

from equity_os.contracts.companies.onboarding import ONBOARDING_VERSIONS
from equity_os.contracts.verification.config_versions import ConfigVersions

DEFAULT_CONFIG_ROOT = "config"
SOURCE_CHECKOUT = Path(__file__).resolve().parents[4]  # the checkout this code runs from
IMPLEMENTATION_PATHS = (
    "equity_os",
    "src",
    "config",
    "migrations",
    "scripts",
    "pyproject.toml",
    "uv.lock",
)
HOLDOUT_RECORD = "tests/fundamentals/fixtures/data_foundation/stage4_holdout.yaml"
SANCTIONS = Path(DEFAULT_CONFIG_ROOT) / "acquisition" / "sanctions"
PROTECTED_ROOTS = (Path("data/raw/onboarding"), Path("data/holdout"))
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
_SANCTION_KEYS = frozenset({"symbols", "purpose", "plan", "plan_commit", "review"})
_SANCTION_REVIEW_KEYS = frozenset(
    {"reviewer", "verdict", "date", "review_commit", "payload_sha256"}
)
_NEEDS_DESCRIPTOR = "--acquire needs --freeze-descriptor"
_UNFROZEN = "the checkout does not satisfy the freeze protocol: {why}"
_UNSANCTIONED = "the sanction does not authorise this acquisition: {why}"
_PROTECTED = "{root} lies under a protected root"


def ordinary_roots(*roots: Path) -> None:
    """Refuse any root that resolves (symlinks followed) under a protected root of the running
    checkout; nothing but ``resolve`` touches the filesystem."""
    checkout = SOURCE_CHECKOUT.resolve()
    for root in roots:
        if any(root.resolve().is_relative_to(checkout / held) for held in PROTECTED_ROOTS):
            raise ValueError(_PROTECTED.format(root=root))


def sanctioned(path: Path, config_root: Path, symbol: str) -> dict[str, Any]:
    """The sanction's checks: committed unchanged at ``HEAD`` in the running checkout's sanctions
    directory, with its own ``config``; exactly the schema's fields; the payload digest (D1.1
    rule) matching; plan and review commits ancestors of ``HEAD``; an ``APPROVE``; ``symbol``
    listed. Returns what the acquisition records of it."""

    def need(ok: bool, why: str) -> None:
        if not ok:
            raise ValueError(_UNSANCTIONED.format(why=why))

    repo = SOURCE_CHECKOUT.resolve()
    resolved = path.resolve()
    need(resolved.is_relative_to(repo / SANCTIONS), "not in the checkout's sanctions directory")
    need(
        config_root.resolve() == (repo / DEFAULT_CONFIG_ROOT).resolve(),
        "--config-root is not the config",
    )
    relative = str(resolved.relative_to(repo))
    need(not _git(repo, "status", "--porcelain", "--", *IMPLEMENTATION_PATHS), "uncommitted")
    head = _git(repo, "rev-parse", "HEAD")
    committed = subprocess.run(
        ["git", "-C", str(repo), "show", f"{head}:{relative}"], check=True, capture_output=True
    ).stdout
    need(resolved.read_bytes() == committed, "differs from HEAD")
    sanction = yaml.safe_load(committed)
    need(isinstance(sanction, dict) and set(sanction) == _SANCTION_KEYS, "sanction fields")
    review = sanction["review"]
    need(isinstance(review, dict) and set(review) == _SANCTION_REVIEW_KEYS, "review fields")
    payload = {key: value for key, value in sanction.items() if key != "review"}
    digest = _sha256(yaml.safe_dump(payload, sort_keys=True).encode())
    need(review["payload_sha256"] == digest, "payload digest")
    for commit in (sanction["plan_commit"], review["review_commit"]):
        _git(repo, "merge-base", "--is-ancestor", str(commit), head)
    need(review["verdict"] == _APPROVE, "review is not APPROVE")
    need(symbol in sanction["symbols"], "symbol not listed")
    return {
        "sanction": relative,
        "sanction_sha256": _sha256(committed),
        "acquisition_head": head,
    }


def frozen(descriptor: Path | None, config_root: Path) -> dict[str, Any]:
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


def _sha256(body: bytes) -> str:
    """Hex SHA-256."""
    return hashlib.sha256(body).hexdigest()
