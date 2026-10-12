"""D1a tracer end to end (Task 10, stage eqos-3f9.7).

Apar Q2 FY26 consolidated goes from the retained first-party captures (XBRL and results PDF)
through the real CLI path — ``evidence ingest``, ``compare run``, ``compare report`` — on a
test database, and the printed report shows the spec-stated values. The report layout is not
frozen, so rows are found by ``row_id`` and fields by their tab-separated position.
"""

from __future__ import annotations

import pytest
from evidence_support import (
    CONFIG,
    PDF_KIND,
    Q2_END,
    Q2_FY26,
    XBRL_KIND,
    Ingest,
    dictionary,
    ingest,
    mapping_set,
    policy,
)
from retained_support import APAR_ISSUER_CONFIG, APAR_MANIFEST, INPUTS_DIR, STORE_DIR

from fundamentals.api.cli import main
from fundamentals.compare.run import RunExitStatus, RunStatus
from fundamentals.contracts.canonical import Representation

__all__ = ["dictionary", "ingest", "mapping_set", "policy"]

# Expected values are literals, never read from code output. Source: data spec
# docs/specs/2026-10-11-canonical-financial-data-and-cross-source-comparison.md, Success
# Criteria, Stage 1 happy path (PBT 340.56 crore, PBT including associates 340.53 crore,
# headline 340.53, OPM 8.06% with a stored trace; the five rows with extraction AGREE) and the
# Stage 2 Apar Q2 FY26 consumer report (PAT 251.70). The filing is the retained Q2 FY26
# consolidated XBRL (SHA-256 90baae0babfa7724e652def20f613efbf33bdadbbbe545e97ff77617d467d799)
# and results PDF (SHA-256 8be1b8de71997d30f2dccd78cfc42d87c5564e2ab16357ca611763c1f3784ae5),
# both verified against the retrieval manifest pins by ``apar_original`` before ingest.
Q2_PERIOD = "2025-07-01..2025-09-30"
AGREE_ROWS = (
    "revenue_from_operations",
    "total_income",
    "total_expenses",
    "profit_for_period",
    "eps_basic",
)
CRORE_VALUES = {
    "profit_before_tax": "340.56",
    "profit_before_tax_incl_associates": "340.53",
    "profit_for_period": "251.70",
}
HEADLINE_PBT = "profit_before_tax_incl_associates"
OPM = "opm_pct"
OPM_PERCENT = "8.06"
# Finance-cost and D&A operands carry no alignment proof in v1 (plan Task 10).
OPM_EXTRACTION = "AGREE_UNQUALIFIED"
AGREE = "AGREE"
HEADLINE_MARKER = "*"
ROW_PREFIX = "row\t"
EXTRACTION_LABEL = "extraction"
VALUE_STATE = "VALUE"
CRORE_SUFFIX = " crore"
TRACE_PREFIX = "trace="
REPRESENTATIONS = (Representation.XBRL.value, Representation.PDF.value)


def _row_id(canonical_id: str, value_identity: str = "REPORTED") -> str:
    """A Q2 FY26 consolidated, undimensioned row id."""
    return f"{canonical_id}|{Q2_PERIOD}|CONSOLIDATED|-|{value_identity}"


class ReportRow:
    """One parsed report block: headline marker, extraction status and per-source fields."""

    def __init__(self, lines: list[str], *, headline: bool) -> None:
        self.headline = headline
        self.extraction = ""
        self.sources: dict[str, list[str]] = {}
        for line in lines:
            fields = line.strip().split("\t")
            if fields[0] == EXTRACTION_LABEL:
                self.extraction = fields[1]
            elif len(fields) > 1 and fields[1] in REPRESENTATIONS:
                self.sources[fields[1]] = fields[2:]

    def field(self, representation: str, suffix: str) -> str:
        """The one field of a source line that ends (or starts) with a marker, marker removed."""
        found = [
            item.removesuffix(CRORE_SUFFIX).removeprefix(TRACE_PREFIX)
            for item in self.sources[representation]
            if item.endswith(suffix) or item.startswith(suffix)
        ]
        assert len(found) == 1, (representation, suffix, self.sources)
        return found[0]


def _parse(report: str) -> dict[str, ReportRow]:
    """The report's row blocks keyed by ``row_id``."""
    blocks: dict[str, tuple[bool, list[str]]] = {}
    current: list[str] = []
    for line in report.splitlines():
        if line.startswith(ROW_PREFIX):
            row_id = line.removeprefix(ROW_PREFIX)
            current = []
            headline = row_id.endswith(HEADLINE_MARKER)
            blocks[row_id.removesuffix(HEADLINE_MARKER)] = (headline, current)
        else:
            current.append(line)
    return {key: ReportRow(lines, headline=flag) for key, (flag, lines) in blocks.items()}


def _header(text: str) -> dict[str, str]:
    """Leading ``name<TAB>value`` lines up to the first row block."""
    header: dict[str, str] = {}
    for line in text.splitlines():
        if line.startswith(ROW_PREFIX):
            break
        name, _, value = line.partition("\t")
        header[name] = value
    return header


@pytest.mark.pg
@pytest.mark.retained
def test_tracer_reports_the_spec_stated_q2_fy26_values(
    ingest: Ingest, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Ingest, run and report Apar Q2 FY26 through the CLI; the report carries the spec values."""
    for name, value in ingest.pg_db.cli_env().items():
        monkeypatch.setenv(name, value)
    ingest.intake()
    scope = ["--period-end", Q2_END.isoformat(), "--basis", "consolidated"]
    ingest_argv = [
        *("evidence", "ingest", "--retrieval-manifest", str(APAR_MANIFEST)),
        *("--issuer", "APARINDS", "--quarter", Q2_FY26, *scope),
        *("--raw-root", str(ingest.tmp_path / INPUTS_DIR)),
        *("--snapshot-root", str(ingest.tmp_path / STORE_DIR)),
        *("--member", f"xbrl={XBRL_KIND}", "--member", f"pdf={PDF_KIND}"),
        *("--issuer-config", str(APAR_ISSUER_CONFIG), "--config-root", str(CONFIG)),
    ]
    assert main(ingest_argv) == 0
    capsys.readouterr()

    assert main(["compare", "run", "--entity", "APARINDS", *scope]) == RunExitStatus.SUCCESS
    summary = _header(capsys.readouterr().out)
    assert summary["status"] == RunStatus.COMPLETE.value
    assert main(["compare", "report", "--entity", "APARINDS", *scope]) == RunExitStatus.SUCCESS
    report = capsys.readouterr().out

    header = _header(report)
    assert header["run"] == summary["run"]
    assert header["status"] == RunStatus.COMPLETE.value
    rows = _parse(report)
    for canonical_id in AGREE_ROWS:
        assert rows[_row_id(canonical_id)].extraction == AGREE, canonical_id
    for canonical_id, crore in CRORE_VALUES.items():
        row = rows[_row_id(canonical_id)]
        for representation in REPRESENTATIONS:
            assert row.sources[representation][0] == VALUE_STATE, (canonical_id, representation)
            assert row.field(representation, CRORE_SUFFIX) == crore, (canonical_id, representation)
    assert rows[_row_id(HEADLINE_PBT)].headline
    assert not rows[_row_id("profit_before_tax")].headline

    opm = rows[_row_id(OPM, "DERIVED")]
    assert opm.extraction == OPM_EXTRACTION
    for representation in REPRESENTATIONS:
        assert opm.sources[representation][:2] == [VALUE_STATE, OPM_PERCENT], representation
        assert opm.field(representation, TRACE_PREFIX).isdigit(), representation
