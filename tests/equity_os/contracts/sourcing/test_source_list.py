"""config/sourcing/sources.yaml names exactly the sources and surfaces the code registers."""

from pathlib import Path

import yaml

from equity_os.contracts.sourcing.source_catalog import BUILTIN_SOURCES, VENDOR_SURFACES
from equity_os.sourcing.vendors.upstox.upstox_source import ROUTES

SOURCING = Path(__file__).parents[4] / "config/sourcing"


def test_source_list_matches_the_code_registries() -> None:
    """A source or surface the code adds or drops must be added to or dropped from the list."""
    rows = yaml.safe_load((SOURCING / "sources.yaml").read_text())["sources"]
    listed = {(r["id"], "catalog", r["catalog"]) for r in rows if "catalog" in r}
    listed |= {(r["id"], s, role) for r in rows for s, role in r.get("surfaces", {}).items()}
    listed |= {
        (r["id"], s, k) for r in rows for k in ("capture_specs", "routes") for s in r.get(k, ())
    }
    code = {
        (e.source_id, "catalog", f"{e.source_class}/{e.evidence_role}")
        for e in BUILTIN_SOURCES.entries
    }
    code |= {(s.source_id, s.surface, s.role.lower()) for s in VENDOR_SURFACES}
    specs = yaml.safe_load((SOURCING / "vendor_surface/surfaces.yaml").read_text())
    code |= {(c["site"], c["id"], "capture_specs") for c in specs}
    code |= {("upstox", r.surface.value, "routes") for r in ROUTES}
    assert listed == code, {"missing from list": code - listed, "not in code": listed - code}
