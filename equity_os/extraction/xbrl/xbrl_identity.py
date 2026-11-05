"""Shared NSE XBRL entity identity policy for live and cached filings."""

from __future__ import annotations

from collections.abc import Collection

NSE_ENTITY_SCHEME = "http://www.nseindia.com/NSESymbol"
# Integrated Filings identify the entity by BSE scrip code instead of the NSE
# symbol; the scrip scheme is hosted by either SEBI or BSE, so both are accepted.
SEBI_SCRIP_ENTITY_SCHEME = "http://www.sebi.gov.in/in-capmkt/ScripCode"
BSE_SCRIP_ENTITY_SCHEME = "http://www.bseindia.com/in-capmkt/ScripCode"
ACCEPTED_NSE_ENTITY_SCHEMES: frozenset[str] = frozenset(
    {NSE_ENTITY_SCHEME, SEBI_SCRIP_ENTITY_SCHEME, BSE_SCRIP_ENTITY_SCHEME}
)


# Rename-stable issuer-identity registry. A company's ISIN never changes across a
# symbol/name rename, but a filing made *before* the rename still carries the OLD
# NSE symbol in its XBRL context entity, while ``financial_results`` now keys the
# row (and its ``isin``) under the NEW symbol. This maps the stable ISIN to the
# as-filed entity identifiers that legitimately belong to that issuer, so a
# pre-rename filing verifies without weakening the guard against a genuinely
# different company. Curated + auditable; keyed by ISIN so it survives future
# renames. (Zomato Limited -> Eternal Limited; symbol ZOMATO -> ETERNAL, effective
# 2025-04-09; ISIN INE758T01015 unchanged.)
ACCEPTED_ENTITY_IDS_BY_ISIN: dict[str, frozenset[str]] = {
    "INE758T01015": frozenset({"ZOMATO"}),
}


class NseEntityIdentityError(ValueError):
    """Raised when an XBRL context does not identify the requested NSE issuer."""


def validate_nse_entity_identities(
    identities: Collection[tuple[str, str]], accepted_entity_ids: Collection[str]
) -> None:
    """Require every context identity to use an accepted scheme and an accepted issuer id.

    Accepted schemes are the NSE symbol scheme and the SEBI- and BSE-hosted
    Integrated-Filing scrip schemes; issuer ids are never inferred, only matched.
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
