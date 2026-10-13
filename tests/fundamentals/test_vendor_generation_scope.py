"""A vendor generation cannot attach another entity/basis/framework to the same capture."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from selection_support import interpretation, key, member

from fundamentals.contracts.canonical import Representation
from fundamentals.contracts.evidence import VendorExtractorPin, VersionPin
from fundamentals.evidence.vendor_common import VendorGeneration, VendorRequest

NOW = datetime(2026, 10, 13, tzinfo=UTC)


@pytest.mark.parametrize(
    "changes",
    [
        {"entity_id": 2},
        {"basis": "STANDALONE"},
        {"framework": "IFRS"},
    ],
)
def test_same_vendor_capture_does_not_authorize_another_interpretation_scope(changes) -> None:
    owner = member(Representation.XBRL, 1, NOW, NOW)
    capture = owner.capture.model_copy(update={"source_id": "constructed", "surface": "HTML"})
    request = VendorRequest(
        source_id="constructed",
        surface="HTML",
        representation=Representation.HTML,
        schema_identity="constructed",
        entity_id=1,
        period=key().period,
        basis=key().basis,
        framework=key().framework,
        statement_family="PL",
    )
    row = interpretation(1, owner).model_copy(
        update={
            "representation": Representation.HTML,
            **changes,
        }
    )
    with pytest.raises(ValidationError, match="scope"):
        VendorGeneration(
            request=request,
            capture=capture,
            interpretations=(row,),
            extractor_pin=VendorExtractorPin(
                source_id="constructed", surface="HTML", version="test", content_sha256="a" * 64
            ),
            source_authority_pin=VersionPin(version="test", content_sha256="b" * 64),
        )
