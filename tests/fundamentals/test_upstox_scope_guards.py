"""Architecture rails for the Upstox lane, checked against the source tree itself.

These are the **secondary** checks. The enforcing bar is typed and lives at the
reconciliation entry point: ``SourceCatalog`` refuses an undeclared source id
outright, and ``EvidenceRole.DIAGNOSTIC_ONLY`` is rejected before any value can
vote (see ``test_source_catalog.py`` and ``test_reconcile.py``). An import scan
proves only that *these* modules do not import the store *today* — it cannot stop
a third module importing both, a consumer reconstructing an ``Observation``, a
dynamic import, or a future orchestration change adding ``upstox`` to source
collection.

Kept anyway, because a scan catches the accident and the typed bar catches the
design. The transport rails — pinned origins, the Bearer host, terminal 403,
bounded retries, token redaction — and the route registry itself are asserted in
``test_upstox_source.py`` against real request objects, which is stronger than
reading the source text for them.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src" / "fundamentals"

# Modules the acquisition lane must not reach. The fact store holds facts, and
# nothing Upstox returns is one; the reconciler decides what ships, and a source
# proven non-independent must never be an input to that decision.
BARRED_MODULES = ("fundamentals.store.fact_store", "fundamentals.reconcile")


def _upstox_modules() -> tuple[Path, ...]:
    """Every first-party module of the Upstox lane."""
    found = tuple(sorted(_SOURCE_ROOT.rglob("upstox*.py")))
    if not found:
        raise AssertionError("no upstox modules found; the guard would pass vacuously")
    return found


def _imported_modules(path: Path) -> set[str]:
    """Every module name one file imports, by parsing it rather than running it."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.add(node.module)
    return names


@pytest.mark.parametrize("path", _upstox_modules(), ids=lambda path: path.name)
def test_no_upstox_module_imports_the_fact_store_or_the_reconciler(path: Path) -> None:
    """Nothing this lane acquires may become a fact or take part in adjudication.

    Upstox shares upstream lineage with Screener — verified, not assumed — so it
    is diagnostic evidence, never a third opinion. An import here would be the
    first step toward a value proven non-independent carrying first-party weight.
    """
    imported = _imported_modules(path)
    for barred in BARRED_MODULES:
        assert not any(name.startswith(barred) for name in imported), (
            f"{path.name} imports {barred}"
        )


def _code_strings(path: Path) -> tuple[str, ...]:
    """Every string literal a module evaluates, with docstrings excluded.

    Docstrings and comments are prose about the code, not values it can send, so
    a rail that read them would fire on an accurate explanation of itself.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    documented = {
        id(node.body[0])
        for node in ast.walk(tree)
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    }
    return tuple(
        node.value
        for parent in ast.walk(tree)
        if id(parent) not in documented
        for node in ast.iter_child_nodes(parent)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    )


@pytest.mark.parametrize("path", _upstox_modules(), ids=lambda path: path.name)
def test_only_the_transport_module_names_an_upstox_origin(path: Path) -> None:
    """Every URL is built from the registry, so no other module writes a host.

    This is what keeps the scope boundary in one reviewable place: a module that
    spelled its own origin could reach a surface the registry never approved.
    """
    if path.name == "upstox_source.py":
        pytest.skip("the transport module is where the two pinned origins are declared")
    assert not [value for value in _code_strings(path) if "upstox.com" in value]


def test_the_lane_declares_no_shared_acquisition_taxonomy() -> None:
    """``AcquisitionOutcome`` stays local; ``eqos-kx4.4`` owns the shared one.

    Publishing a competing enum under ``contracts/`` is exactly the migration
    cost this lane's persistence decision exists to avoid.
    """
    contracts = _SOURCE_ROOT / "contracts"
    assert not list(contracts.glob("upstox*.py"))
    assert not any(
        "AcquisitionOutcome" in path.read_text(encoding="utf-8") for path in contracts.glob("*.py")
    )


def test_the_entity_adapter_reads_disk_and_declares_no_transport() -> None:
    """An entity-map build stays offline, matching the two existing adapters."""
    adapter = _SOURCE_ROOT / "entity" / "upstox_entity_source.py"
    imported = _imported_modules(adapter)
    assert not any(name.startswith(("urllib", "http", "socket", "requests")) for name in imported)
    assert "UpstoxSource" not in adapter.read_text(encoding="utf-8")
