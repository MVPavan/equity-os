"""Version-content pinning: a published version string never changes its content (data spec §1)."""

from __future__ import annotations

_DRIFT = "{artifact} version {version!r} is pinned to content {pinned} but now resolves to {actual}"


class VersionContentDriftError(ValueError):
    """A version string was reused with different resolved content."""

    def __init__(
        self, *, artifact: str, version: str, pinned_sha256: str, actual_sha256: str
    ) -> None:
        self.artifact = artifact
        self.version = version
        self.pinned_sha256 = pinned_sha256
        self.actual_sha256 = actual_sha256
        super().__init__(
            _DRIFT.format(
                artifact=artifact, version=version, pinned=pinned_sha256, actual=actual_sha256
            )
        )
