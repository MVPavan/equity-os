"""Shared XBRL taxonomy registry for every first-party filing path."""

from fundamentals.extract.xbrl_parser import DEFAULT_TAXONOMIES, TaxonomySpec

IN_CAPMKT_NAMESPACE = "http://www.sebi.gov.in/xbrl/2023-03-31/in-capmkt"
IN_CAPMKT_PREFIX = "in-capmkt"
IN_CAPMKT_REGISTRY_VERSION = "in-capmkt/2023-03-31"

# SEBI revises in-capmkt per filing season and instances declare the revision in
# their namespace URI; an unregistered revision fails closed, so every revision
# actually served (Integrated Filings since Mar-2025) is registered explicitly.
IN_CAPMKT_2025_NAMESPACE = "http://www.sebi.gov.in/xbrl/2025-01-31/in-capmkt"
IN_CAPMKT_2025_REGISTRY_VERSION = "in-capmkt/2025-01-31"
IN_CAPMKT_2026_NAMESPACE = "http://www.sebi.gov.in/xbrl/2026-01-31/in-capmkt"
IN_CAPMKT_2026_REGISTRY_VERSION = "in-capmkt/2026-01-31"

_ALL_TAXONOMIES: tuple[TaxonomySpec, ...] = (
    *DEFAULT_TAXONOMIES,
    TaxonomySpec(
        namespace=IN_CAPMKT_NAMESPACE,
        prefix=IN_CAPMKT_PREFIX,
        registry_version=IN_CAPMKT_REGISTRY_VERSION,
    ),
    TaxonomySpec(
        namespace=IN_CAPMKT_2025_NAMESPACE,
        prefix=IN_CAPMKT_PREFIX,
        registry_version=IN_CAPMKT_2025_REGISTRY_VERSION,
    ),
    TaxonomySpec(
        namespace=IN_CAPMKT_2026_NAMESPACE,
        prefix=IN_CAPMKT_PREFIX,
        registry_version=IN_CAPMKT_2026_REGISTRY_VERSION,
    ),
)
