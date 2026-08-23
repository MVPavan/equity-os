"""Shared XBRL taxonomy registry for every first-party filing path."""

from fundamentals.extract.xbrl_parser import DEFAULT_TAXONOMIES, TaxonomySpec

IN_CAPMKT_NAMESPACE = "http://www.sebi.gov.in/xbrl/2023-03-31/in-capmkt"
IN_CAPMKT_PREFIX = "in-capmkt"
IN_CAPMKT_REGISTRY_VERSION = "in-capmkt/2023-03-31"

_ALL_TAXONOMIES: tuple[TaxonomySpec, ...] = (
    *DEFAULT_TAXONOMIES,
    TaxonomySpec(
        namespace=IN_CAPMKT_NAMESPACE,
        prefix=IN_CAPMKT_PREFIX,
        registry_version=IN_CAPMKT_REGISTRY_VERSION,
    ),
)
