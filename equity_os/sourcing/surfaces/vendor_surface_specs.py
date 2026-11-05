"""Finite capture specifications checked against the catalog of record."""

from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from equity_os.sourcing.surfaces.vendor_surface_fetch import Site

SITE_NAME = {Site.SCREENER: "screener", Site.TIJORI: "tijori"}


class ParseGroup(StrEnum):
    """The finite parser families."""

    SERIES = "SERIES"
    TABLE = "TABLE"
    CELLS = "CELLS"
    TEXT = "TEXT"
    DISCOVERY = "DISCOVERY"
    READER = "READER"
    NONE = "NONE"


class Cadence(StrEnum):
    """Acquisition schedules."""

    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    AFTER_RESULTS = "AFTER_RESULTS"


class Scope(StrEnum):
    """Company or market requests."""

    COMPANY = "COMPANY"
    MARKET = "MARKET"


class SurfaceSpec(BaseModel):
    """One fetched catalog surface, with separately parsed logical sections."""

    model_config = ConfigDict(frozen=True)
    site: Site
    id: str
    scope: Scope
    path: str
    group: ParseGroup
    cadence: Cadence
    xhr: bool = False
    expand: str | None = None
    sections: tuple[str, ...] = ()
    selector: str | None = None
    feed: bool = False
    enabled: bool = True  # False stops new fetches; retained captures and parsers stay.


def load_specs(path: Path, catalog: Path) -> tuple[SurfaceSpec, ...]:
    """Validate configured paths and scope against their catalog entries."""
    reference = yaml.safe_load(catalog.read_text())
    specs = tuple(SurfaceSpec.model_validate(row) for row in yaml.safe_load(path.read_text()))
    for spec in specs:
        entry = next(
            row for row in reference[SITE_NAME[spec.site]]["entries"] if row["id"] == spec.id
        )
        if spec.path != entry["url_pattern"] or spec.scope.value.lower() != entry["scope"]:
            raise ValueError(f"catalog mismatch: {SITE_NAME[spec.site]}:{spec.id}")
    return specs
