"""F02 judgment fields cannot borrow matching amounts from unrelated facts."""

import pytest
from test_thesis import _draft, _fact_set

from equity_os.analysis.thesis_models import JudgmentSection, build_prompt, cross_verify


@pytest.mark.parametrize("subject", ["Revenue", "Profit"])
@pytest.mark.parametrize("section", list(JudgmentSection))
def test_unbound_amounts_are_unsourced(subject: str, section: JudgmentSection) -> None:
    text = f"{subject} is 174.455 crore."
    draft = _draft("audit", sections={section: [text]}, raw_text=text)
    assert len(cross_verify(_fact_set(), [draft]).unsourced_claims) == 1


def test_prompt_requires_qualitative_judgment() -> None:
    prompt = build_prompt(_fact_set())
    assert "no analytical amounts" in prompt
    assert "facts are shown by code" in prompt
