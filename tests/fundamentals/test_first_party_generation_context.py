"""Qualification-context race coverage for publication-bound first-party generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from evidence_support import Ingest, dictionary, ingest, mapping_set, policy
from test_first_party_generation import _append, _published_config

from fundamentals.contracts.evidence import Interpretation
from fundamentals.evidence import first_party_ingest
from fundamentals.evidence.first_party_generation import FirstPartyGenerationError
from fundamentals.pg.identity_seed import EvidenceInputKind, SettingKey

__all__ = ["dictionary", "ingest", "mapping_set", "policy"]

pytestmark = [pytest.mark.pg, pytest.mark.retained]


def test_concurrent_setting_change_retry_never_reuses_prior_context(
    ingest: Ingest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A rejected S1 generation cannot later be handed off as qualified under S2."""
    config_root, loaded = _published_config(tmp_path)
    original = first_party_ingest._interpretations
    changed = False

    def race_once(*args: Any, **kwargs: Any) -> tuple[Interpretation, ...]:
        nonlocal changed
        if not changed:
            changed = True
            current = ingest.repository.settings_as_of(
                ingest.entity_id,
                SettingKey.FISCAL_YEAR_END_MONTH,
                ingest.repository.store_clock(),
            )
            assert current is not None
            evidence_id = ingest.repository.put_evidence_input(
                EvidenceInputKind.ISSUER_CONFIG,
                "synthetic concurrent qualification-context change",
                "2" * 64,
            )
            ingest.repository.put_settings_record(
                ingest.entity_id,
                SettingKey.FISCAL_YEAR_END_MONTH,
                current.value_text,
                evidence_id,
            )
        return original(*args, **kwargs)

    monkeypatch.setattr(first_party_ingest, "_interpretations", race_once)
    before = ingest.table_counts()

    with ingest.pg_db.runtime_pool() as pool:
        with pytest.raises(FirstPartyGenerationError, match="changed during generation"):
            _append(ingest, config_root, loaded, pool)

        assert ingest.table_counts()["interpretations"] > before["interpretations"]
        with pytest.raises(FirstPartyGenerationError, match="fresh mapping version"):
            _append(ingest, config_root, loaded, pool)
