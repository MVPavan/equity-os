"""Acceptance tests for slice phase05-s1b: per-issuer config knobs.

Four declared-per-issuer knobs let ``fundamentals run`` serve an issuer whose XBRL
uses a non-default taxonomy prefix, whose entity is identified by a scrip code, and
whose scanned results PDF prints an OCR-corrupted unit marker and a non-default
net-profit label. Everything below is synthetic: no real issuer, scrip code, hash,
or captured document text appears here.

``PdfPrintedUnit`` is imported inside the tests that need it so that each
acceptance test fails on its own before the enum exists, rather than the whole
module failing to collect.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest

from fundamentals.api.config import (
    FundamentalsConfig,
    PdfParseConfig,
    load_config,
)
from fundamentals.api.pipeline import _normalize_entity, _pdf_parse_spec
from fundamentals.contracts.observation import (
    AccountingFramework,
    Observation,
    PeriodType,
    Scope,
)
from fundamentals.contracts.provenance import Provenance, SourceAnchorType
from fundamentals.extract.pdf_column_geometry import (
    NumberParseError,
    _detect_unit_factor,
)
from fundamentals.extract.pdf_number_parser import PdfTargetLine
from fundamentals.ingest.pdf_source import PageWord

_SYNTH_SHA_RESULTS = "1a" * 32
_SYNTH_SHA_TRANSCRIPT = "2b" * 32
_SYNTH_SCRIP = "999001"
_SYNTH_SYMBOL = "SYNTH"
_ISSUER_SCHEME = "nse-symbol"
_SCRIP_SCHEME = "http://www.sebi.gov.in/in-capmkt/ScripCode"
_OTHER_SCHEME = "http://synthetic.example/OtherIdentifier"
_SYNTH_PREFIX = "in-synth"
_DEFAULT_PREFIX = "in-bse-fin"
_NET_PROFIT_LOCAL = "ProfitLossForPeriod"
_OVERRIDE_LABEL = "Profit after tax"
_RETRIEVED_AT = datetime(2027, 7, 20, tzinfo=UTC)

_BASE_YAML = f"""
issuer:
  name: "Synthetic Manufacturing Limited"
  nse_symbol: "{_SYNTH_SYMBOL}"
  entity_scheme: "{_ISSUER_SCHEME}"

quarter:
  issuer_quarter: "FY27_Q1"
  program_quarter: "QUARTER_1"
  label: "Q1 FY27 (quarter ended 2027-06-30)"
  period_start: "2027-04-01"
  period_end: "2027-06-30"
  knowledge_cutoff: "2027-07-20T00:00:00Z"

raw_dir: "data/raw/synth-fy27"
store_db: ":memory:"

results_pdf:
  source_id: "synth-q1-fy27-results-pdf"
  source_class: "first_party"
  filename: "SYNTH-FY27-Q1-results.pdf"
  sha256: "{_SYNTH_SHA_RESULTS}"

transcript_pdf:
  source_id: "synth-q1-fy27-transcript-pdf"
  source_class: "first_party"
  filename: "SYNTH-FY27-Q1-transcript.pdf"
  sha256: "{_SYNTH_SHA_TRANSCRIPT}"

xbrl:
  source_id: "synth-xbrl-consolidated"
  mode: "local"
  local_path: "tests/fundamentals/fixtures/synthetic_q1_fy27_consolidated.xml"
  symbol: "{_SYNTH_SYMBOL}"
"""


def _write_config(tmp_path: Path, extra_yaml: str = "", xbrl_extra: str = "") -> Path:
    """Write a synthetic composition-root YAML and return its path.

    ``xbrl_extra`` continues the trailing ``xbrl`` block (indented lines);
    ``extra_yaml`` adds further top-level blocks.
    """
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / "fundamentals.yaml"
    path.write_text(_BASE_YAML + xbrl_extra + extra_yaml, encoding="utf-8")
    return path


def _header_words(*texts: str) -> tuple[PageWord, ...]:
    """Build a statement-header word row from bare text tokens."""
    return tuple(
        PageWord(
            x0=100.0 + 40.0 * index,
            y0=50.0,
            x1=135.0 + 40.0 * index,
            y1=60.0,
            text=text,
            block=0,
            line=0,
            word_no=index,
        )
        for index, text in enumerate(texts)
    )


def _effective_lines(pdf_parse: PdfParseConfig) -> tuple[PdfTargetLine, ...]:
    """Read ``effective_target_lines`` whether it is exposed as a property or a method."""
    value: object = pdf_parse.effective_target_lines
    if callable(value):
        value = value()
    return cast("tuple[PdfTargetLine, ...]", value)


def _line_by_local_name(lines: tuple[PdfTargetLine, ...], local_name: str) -> PdfTargetLine:
    """Return the single target line whose concept qname ends with ``local_name``."""
    matches = [line for line in lines if line.concept_qname.split(":", 1)[-1] == local_name]
    assert len(matches) == 1, f"expected one {local_name} line, got {len(matches)}"
    return matches[0]


def _all_concept_qnames(config: FundamentalsConfig) -> list[str]:
    """Every configured concept qname: roles, aux, cross-checks, identities, PDF lines."""
    qnames = [role.concept_qname for role in config.concepts.roles]
    qnames += [aux.concept_qname for aux in config.concepts.aux]
    qnames += list(config.concepts.cross_check)
    for identity in config.concepts.identities:
        qnames.append(identity.lhs_concept)
        qnames += [term.concept_qname for term in identity.terms]
    qnames += [line.concept_qname for line in config.pdf_parse.target_lines]
    return qnames


def _observation(entity_scheme: str, entity_id: str) -> Observation:
    """A minimal synthetic XBRL-sourced observation carrying the entity under test."""
    return Observation(
        concept_qname=f"{_SYNTH_PREFIX}:RevenueFromOperations",
        raw_value="12340000000",
        normalized_value=Decimal("1234.00"),
        normalized_unit="INR crore",
        context_ref="SynthOneD",
        entity_scheme=entity_scheme,
        entity_id=entity_id,
        scope=Scope.CONSOLIDATED,
        accounting_basis=AccountingFramework.IND_AS,
        period_type=PeriodType.DURATION,
        period_start=datetime(2027, 4, 1, tzinfo=UTC).date(),
        period_end=datetime(2027, 6, 30, tzinfo=UTC).date(),
        currency="INR",
        scale=10_000_000,
        decimals=-7,
        provenance=Provenance(
            source_id="synth-xbrl-consolidated",
            file_sha256="3c" * 32,
            anchor_type=SourceAnchorType.XBRL_CONTEXT,
            context_ref="SynthOneD",
            retrieved_at=_RETRIEVED_AT,
        ),
    )


# --------------------------------------------------------------------------- #
# A. Declared printed unit                                                    #
# --------------------------------------------------------------------------- #


def test_unit_declared_fills_missing_marker() -> None:
    """An OCR-mangled unit word must not abort a run whose unit is declared per issuer."""
    from fundamentals.extract.pdf_column_geometry import PdfPrintedUnit

    words = _header_words("Quarter", "ended", "30", "June", "2027", "(Ra.in", "cronesx)")

    factor = _detect_unit_factor(words, declared=PdfPrintedUnit.CRORE)

    assert factor == Decimal(1)


def test_unit_declared_conflicts_with_printed() -> None:
    """A declared scale must never override a legible printed one — it would rescale every value."""
    from fundamentals.extract.pdf_column_geometry import PdfPrintedUnit

    words = _header_words("Quarter", "ended", "30", "June", "2027", "(Rs.", "in", "lakh)")

    with pytest.raises(NumberParseError) as excinfo:
        _detect_unit_factor(words, declared=PdfPrintedUnit.CRORE)

    message = str(excinfo.value)
    assert "conflicts" in message
    assert "lakh" in message
    assert "crore" in message


def test_unit_undeclared_missing_marker_still_fails() -> None:
    """With no declaration the parser must still refuse to guess a scale from an unmarked header."""
    words = _header_words("Quarter", "ended", "30", "June", "2027")

    with pytest.raises(NumberParseError):
        _detect_unit_factor(words, declared=None)


def test_unit_declared_agrees_with_printed() -> None:
    """A declaration that matches the printed unit is a no-op, so declaring it is always safe."""
    from fundamentals.extract.pdf_column_geometry import PdfPrintedUnit

    words = _header_words("(Rs.", "in", "crores)")

    assert _detect_unit_factor(words, declared=PdfPrintedUnit.CRORE) == Decimal(1)


# --------------------------------------------------------------------------- #
# B. Per-issuer label overrides                                               #
# --------------------------------------------------------------------------- #


def test_label_override_appends_to_matching_line() -> None:
    """An issuer label is appended, not substituted, so default wordings keep matching."""
    defaults = PdfParseConfig()
    overridden = PdfParseConfig(label_overrides={_NET_PROFIT_LOCAL: (_OVERRIDE_LABEL,)})

    effective = _effective_lines(overridden)
    net_profit = _line_by_local_name(effective, _NET_PROFIT_LOCAL)
    default_net_profit = _line_by_local_name(defaults.target_lines, _NET_PROFIT_LOCAL)

    assert net_profit.labels == (*default_net_profit.labels, _OVERRIDE_LABEL)
    untouched = {
        line.concept_qname: line.labels
        for line in effective
        if line.concept_qname != net_profit.concept_qname
    }
    assert untouched == {
        line.concept_qname: line.labels
        for line in defaults.target_lines
        if line.concept_qname != default_net_profit.concept_qname
    }


def test_label_override_unknown_concept_rejected(tmp_path: Path) -> None:
    """A typo'd override key would silently do nothing; failing closed names the key instead."""
    config_path = _write_config(
        tmp_path,
        '\npdf_parse:\n  label_overrides:\n    NotAConfiguredConcept: ["Some printed label"]\n',
    )

    with pytest.raises(ValueError, match="NotAConfiguredConcept"):
        load_config(config_path)


# --------------------------------------------------------------------------- #
# C. Taxonomy prefix                                                          #
# --------------------------------------------------------------------------- #


def test_taxonomy_prefix_rewrites_defaults(tmp_path: Path) -> None:
    """Another taxonomy shares the local names; without the rewrite role selection fails closed."""
    default_config = load_config(_write_config(tmp_path / "default"))
    rewritten = load_config(
        _write_config(tmp_path / "synth", f'\ntaxonomy_prefix: "{_SYNTH_PREFIX}"\n')
    )

    rewritten_qnames = _all_concept_qnames(rewritten)
    assert rewritten_qnames, "expected configured concepts to compare"
    assert all(qname.startswith(f"{_SYNTH_PREFIX}:") for qname in rewritten_qnames)
    assert [qname.split(":", 1)[1] for qname in rewritten_qnames] == [
        qname.split(":", 1)[1] for qname in _all_concept_qnames(default_config)
    ]


def test_taxonomy_prefix_default_leaves_qnames(tmp_path: Path) -> None:
    """The default prefix must be a no-op, so the existing filer keeps its exact qnames."""
    absent = load_config(_write_config(tmp_path / "absent"))
    explicit = load_config(
        _write_config(tmp_path / "explicit", f'\ntaxonomy_prefix: "{_DEFAULT_PREFIX}"\n')
    )

    assert explicit.taxonomy_prefix == _DEFAULT_PREFIX
    assert absent.taxonomy_prefix == _DEFAULT_PREFIX
    assert _all_concept_qnames(explicit) == _all_concept_qnames(absent)
    assert all(qname.startswith(f"{_DEFAULT_PREFIX}:") for qname in _all_concept_qnames(explicit))


# --------------------------------------------------------------------------- #
# D. Entity id alias                                                          #
# --------------------------------------------------------------------------- #


def test_entity_id_alias_applies_after_scheme_alias() -> None:
    """The XBRL scrip id and PDF symbol must collapse to one entity, else no cross-check runs."""
    obs = _observation(_SCRIP_SCHEME, _SYNTH_SCRIP)

    normalized = _normalize_entity(
        obs,
        {_SCRIP_SCHEME: _ISSUER_SCHEME},
        {_SYNTH_SCRIP: _SYNTH_SYMBOL},
        _ISSUER_SCHEME,
    )

    assert (normalized.entity_scheme, normalized.entity_id) == (_ISSUER_SCHEME, _SYNTH_SYMBOL)


def test_entity_id_alias_ignored_for_other_scheme() -> None:
    """Aliasing outside the issuer scheme would let a wrong company's file pass the cross-check."""
    obs = _observation(_OTHER_SCHEME, _SYNTH_SCRIP)

    normalized = _normalize_entity(
        obs,
        {_OTHER_SCHEME: "other-identifier"},
        {_SYNTH_SCRIP: _SYNTH_SYMBOL},
        _ISSUER_SCHEME,
    )

    assert (normalized.entity_scheme, normalized.entity_id) == ("other-identifier", _SYNTH_SCRIP)


# --------------------------------------------------------------------------- #
# Wiring: pipeline spec and YAML round-trip                                   #
# --------------------------------------------------------------------------- #


def test_pipeline_spec_carries_unit_and_effective_lines(tmp_path: Path) -> None:
    """Knobs the run never reads are dead config; the parse spec is where they must arrive."""
    from fundamentals.extract.pdf_column_geometry import PdfPrintedUnit

    config = load_config(
        _write_config(
            tmp_path,
            "\npdf_parse:\n"
            '  printed_unit: "crore"\n'
            "  label_overrides:\n"
            f'    {_NET_PROFIT_LOCAL}: ["{_OVERRIDE_LABEL}"]\n',
        )
    )

    spec = _pdf_parse_spec(config)

    assert spec.printed_unit is PdfPrintedUnit.CRORE
    assert _line_by_local_name(spec.target_lines, _NET_PROFIT_LOCAL).labels[-1] == _OVERRIDE_LABEL
    assert (
        _line_by_local_name(spec.target_lines, _NET_PROFIT_LOCAL).labels[0]
        == (_line_by_local_name(PdfParseConfig().target_lines, _NET_PROFIT_LOCAL).labels[0])
    )


def test_config_yaml_loads_new_fields(tmp_path: Path) -> None:
    """The knobs are declared in YAML only; when absent the existing filer behaves unchanged."""
    from fundamentals.extract.pdf_column_geometry import PdfPrintedUnit

    configured = load_config(
        _write_config(
            tmp_path / "configured",
            f'\ntaxonomy_prefix: "{_SYNTH_PREFIX}"\n'
            "pdf_parse:\n"
            '  printed_unit: "crore"\n'
            "  label_overrides:\n"
            f'    {_NET_PROFIT_LOCAL}: ["{_OVERRIDE_LABEL}"]\n',
            xbrl_extra=f'  entity_id_aliases:\n    "{_SYNTH_SCRIP}": "{_SYNTH_SYMBOL}"\n',
        )
    )
    defaults = load_config(_write_config(tmp_path / "defaults"))

    assert configured.taxonomy_prefix == _SYNTH_PREFIX
    assert configured.pdf_parse.printed_unit is PdfPrintedUnit.CRORE
    assert configured.pdf_parse.label_overrides == {_NET_PROFIT_LOCAL: (_OVERRIDE_LABEL,)}
    assert configured.xbrl.entity_id_aliases == {_SYNTH_SCRIP: _SYNTH_SYMBOL}
    assert defaults.taxonomy_prefix == _DEFAULT_PREFIX
    assert defaults.pdf_parse.printed_unit is None
    assert defaults.pdf_parse.label_overrides == {}
    assert defaults.xbrl.entity_id_aliases == {}
