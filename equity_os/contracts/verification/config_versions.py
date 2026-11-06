"""Which version of each file-backed comparison artifact a run loads (contracts only, so shared
vocabularies such as onboarding's can pin versions without importing the comparison)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from equity_os.contracts.measurement.evidence import PinnedVersions, VersionPin

DEFAULT_VERSION = "v1"


class ConfigVersions(BaseModel):
    """Which version of each file-backed artifact a run loads."""

    model_config = ConfigDict(frozen=True)

    dictionary: str = DEFAULT_VERSION
    mapping_set: str = DEFAULT_VERSION
    normalisation_policy: str = DEFAULT_VERSION
    rounding_policy: str = DEFAULT_VERSION
    definition_set: str = DEFAULT_VERSION
    comparison_policy: str = DEFAULT_VERSION
    alignment_rules: str = DEFAULT_VERSION
    vendor_first_policy: str | None = DEFAULT_VERSION
    eligibility: str | None = None

    @classmethod
    def of(cls, pinned: PinnedVersions) -> ConfigVersions:
        """The file versions a pinned-version set names."""
        return cls(
            dictionary=pinned.dictionary.version,
            mapping_set=pinned.mapping_set.version,
            normalisation_policy=pinned.normalisation_policy.version,
            rounding_policy=pinned.rounding_policy.version,
            definition_set=pinned.definition_set.version,
            comparison_policy=pinned.comparison_policy.version,
            alignment_rules=pinned.alignment_rules.version,
            vendor_first_policy=_version(pinned.vendor_first_policy),
            eligibility=_version(pinned.eligibility),
        )


def _version(pin: VersionPin | None) -> str | None:
    """An optional pin's version."""
    return None if pin is None else pin.version
