"""Shared NSE XBRL entity identity policy for live and cached filings."""

from __future__ import annotations

from collections.abc import Collection

NSE_ENTITY_SCHEME = "http://www.nseindia.com/NSESymbol"
# SEBI Integrated Filings identify the entity by BSE scrip code under SEBI's own
# scheme instead of the NSE symbol, so both schemes are accepted.
SEBI_SCRIP_ENTITY_SCHEME = "http://www.sebi.gov.in/in-capmkt/ScripCode"
ACCEPTED_NSE_ENTITY_SCHEMES: frozenset[str] = frozenset(
    {NSE_ENTITY_SCHEME, SEBI_SCRIP_ENTITY_SCHEME}
)


class NseEntityIdentityError(ValueError):
    """Raised when an XBRL context does not identify the requested NSE issuer."""


def validate_nse_entity_identities(
    identities: Collection[tuple[str, str]], accepted_entity_ids: Collection[str]
) -> None:
    """Require every context identity to use an accepted scheme and an accepted issuer id.

    Accepted schemes are the NSE symbol scheme and SEBI's Integrated-Filing scrip
    scheme; the issuer ids themselves are never inferred, only matched.
    """
    normalized = {
        (scheme.strip(), entity_id.strip().upper())
        for scheme, entity_id in identities
        if scheme.strip() or entity_id.strip()
    }
    if not normalized:
        raise NseEntityIdentityError("XBRL carries no entity identities")

    invalid_schemes = sorted(
        {scheme for scheme, _entity_id in normalized if scheme not in ACCEPTED_NSE_ENTITY_SCHEMES}
    )
    if invalid_schemes:
        raise NseEntityIdentityError(
            f"entity scheme {invalid_schemes} is not an accepted NSE scheme"
        )

    accepted = {entity_id.strip().upper() for entity_id in accepted_entity_ids if entity_id.strip()}
    observed = {entity_id for _scheme, entity_id in normalized}
    if not observed.issubset(accepted):
        raise NseEntityIdentityError(
            f"entity {sorted(observed)} does not match requested issuer "
            f"(accepted entity ids: {sorted(accepted) or 'none'})"
        )
