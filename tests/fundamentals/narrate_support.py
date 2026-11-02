"""RESEARCH-3 S3 support: what the pilot-backed narrate tests share.

Production names import through ``code``, so these files collect on pre-change source and each
node fails before it pays for a pilot."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any

import pytest
from evidence_support import ingest, policy
from prep2b_support import Pilot
from prep5_support import _rerun
from test_credibility_binding import all_counts
from test_ledger_panel import FakeReviewer
from test_prep2b_run_draft import dictionary, mapping_set, pilot

from fundamentals.contracts.ledger import SubjectKind, Verdict, VersionDraft
from fundamentals.ledger import lifecycle, panel, store
from fundamentals.ledger.display import narrative
from fundamentals.thesis.client import ModelResponse

__all__ = ["FakeReviewer", "all_counts", "code_exists", "dictionary", "ingest", "mapping_set"]
__all__ += ["pilot", "policy"]
CREDIBILITY, PROBE, IMPACT = "management_credibility", "risk_probe", "thesis_impact"
LABEL = "{{e:inferred}} "
THESES = (
    "SELECT v.id FROM eqos.report_versions v JOIN eqos.reports r ON r.id = v.report_id "
    "WHERE r.kind = 'BOOTSTRAP_THESIS'"
)
NOTE = "{{{{e:inferred}}}} This row leaves a question open {{{{c:{}|ref}}}}."


def code() -> SimpleNamespace:
    """The modules this slice adds."""
    from fundamentals.ledger import evidence_bundle, narrate, narrate_checks

    return SimpleNamespace(bundle=evidence_bundle, flow=narrate, checks=narrate_checks)


@pytest.fixture(autouse=True)
def code_exists() -> None:
    """A missing production module fails the node before its pilot is built."""
    code()


class FakeClient:
    """A ``ThesisModelClient`` answering one fixed draft."""

    label, name = "fake-model", "fake"

    def __init__(self, text: str = "") -> None:
        self.text, self.prompts = text, list[str]()

    def generate(self, prompt: str) -> ModelResponse:
        self.prompts.append(prompt)
        return ModelResponse(text=self.text, duration_seconds=0)


def limits(**over: int) -> Any:
    """Generous limits, ``over`` applied."""
    held = {"max_span_chars": 4_000, "max_total_bytes": 300_000}
    held |= {"max_prompt_bytes": 131_072, "max_response_bytes": 40_000}
    return code().bundle.BundleLimits(**(held | over))


def body(version: VersionDraft, key: str) -> str:
    return next(s.body for s in version.sections if s.section_key == key)


def with_section(version: VersionDraft, key: str, text: str) -> VersionDraft:
    """A copy of ``version``, no write, with one section's body changed."""
    new = {"body": text}
    sections = [s.model_copy(update=new) if s.section_key == key else s for s in version.sections]
    return version.model_copy(update={"sections": tuple(sections)})


def draft(version: VersionDraft, **over: str) -> str:
    """The model's answer: clean, a note on every row due, in plan order; ``over`` replaces."""
    due = code().checks.notes_due(body(version, PROBE), body(version, CREDIBILITY))
    keys = [c.claim_key for c in version.claims]

    def notes(section: str) -> str:
        cited = (min(k for k in keys if k.startswith(p)) for p in due.get(section, ()))
        return "\n\n".join([NOTE.format(key) for key in cited] or ["{{e:inferred}} None is due."])

    bodies = {
        "drivers": "{{e:inferred}} The figure moved on its comparison {{c:fact.revenue|ref}}.",
        "risk_notes": notes("risk_notes"),
        "credibility_notes": notes("credibility_notes"),
        "thesis_narrative": "{{e:opinion}} The stance on the thesis is uncertain on this evidence.",
        "analyst_questions": "{{e:inferred}} What would settle the funding question, and why?",
    }
    return "".join(f"## {key}\n\n{text}\n\n" for key, text in (bodies | over).items())


def q2_draft(pilot: Pilot) -> int:
    version = pilot.run("FY26_Q2").draft_version_id
    assert version is not None
    return version


def rerun_draft(pilot: Pilot, **opts: Any) -> int:
    version = _rerun(pilot, **opts).draft_version_id
    assert version is not None
    return version


def prepared(pilot: Pilot) -> tuple[int, VersionDraft]:
    """FY26_Q2's run draft, approved: its id and content."""
    version = q2_draft(pilot)
    pilot.approve(version)
    return version, pilot.version(version)


def narrate(pilot: Pilot, version: int, client: FakeClient, held: Any = None) -> int:
    """``narrate`` as the runtime role."""
    opts = {"client": client, "limits": held or limits()} | pilot.sources()
    with pilot.pg_db.runtime_pool() as pool:
        return int(code().flow.narrate(pool, version, **opts))


def submit(pilot: Pilot, version: int) -> None:
    with pilot.pg_db.runtime_pool() as pool:
        lifecycle.submit(pool, version, **pilot.sources())


def decide(pilot: Pilot, version: int, verdict: Verdict = Verdict.APPROVE) -> FakeReviewer:
    """Submit the version and record the panel's verdict through a fake reviewer."""
    reviewer = FakeReviewer(verdict)
    submit(pilot, version)
    opts: dict[str, Any] = {"reviewer": reviewer, "limits": limits()} | pilot.sources()
    with pilot.pg_db.panel_pool() as pool:
        panel.review(pool, subject_kind=SubjectKind.REPORT_VERSION, subject_id=version, **opts)
    return reviewer


@contextmanager
def writes_nothing(pilot: Pilot, match: str, error: Any = None) -> Iterator[None]:
    """The block refuses naming ``match`` and every table's count stays."""
    before = all_counts(pilot)
    with pytest.raises(error or code().flow.NarrateRefusedError, match=match):
        yield
    assert all_counts(pilot) == before


def refused(
    pilot: Pilot, version: int, client: Any, cause: str, called: bool = False, kept: Any = None
) -> None:
    """Narrate refuses naming ``cause``, writes nothing; the model reached only if ``called``."""
    with writes_nothing(pilot, cause):
        narrate(pilot, version, client, kept)
    assert bool(client.prompts) is called


def reading(pilot: Pilot, read: Any, *args: Any) -> Any:
    """``read(cursor, *args)`` as the runtime role."""
    with pilot.pg_db.runtime_pool() as pool, pool.connection() as conn:
        return read(conn.cursor(), *args)


def plain_text(cursor: Any, version: int) -> str:
    held = store.read_version(cursor, version)
    return narrative(held.sections, held.claims).decode()


def quotes(version: VersionDraft) -> list[str]:
    return [c.citation.quote for c in version.claims if c.citation.quote]
