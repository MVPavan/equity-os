"""D1a.2 acceptance: dictionary v1 loads, matches its manifest, and every defect class fails loudly.

Each failure case loads a temporary copy of v1 with one defect introduced, so a passing
case proves the loader catches that defect in otherwise valid content.
"""

from __future__ import annotations

import re
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from fundamentals.canon.dictionary import (
    FORMULA_SET_FILE,
    TEMPLATES_FILE,
    DictionaryDefect,
    DictionaryLoadError,
    DimensionalAggregation,
    MemberBinding,
    load_dictionary,
)
from fundamentals.contracts.canonical import StatementFamily

REPO_ROOT = Path(__file__).resolve().parents[2]
DICTIONARY_ROOT = REPO_ROOT / "config" / "dictionary"
MANIFEST = REPO_ROOT / "docs" / "specs" / "artifacts" / "dictionary-v1-manifest.md"
VERSION = "v1"
SEGMENT_TOTAL = "segment_revenue_members_total"
APAR_SEGMENTS = ["conductors", "transformer_and_speciality_oils", "power_telecom_cables", "others"]
COUNT_ROW = re.compile(r"^\| ([A-Z_]+) \| (\d+) \|$")

Doc = dict[str, Any]
Edit = Callable[[Path], None]


def _edit(file_name: str, change: Callable[[Doc], None]) -> Edit:
    """Return an edit that loads one YAML file of the copy, changes it and writes it back."""

    def apply(directory: Path) -> None:
        path = directory / file_name
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        change(doc)
        path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")

    return apply


def _row(doc: Doc, canonical_id: str) -> Doc:
    """Find one row of a family file by id."""
    return next(row for row in doc["rows"] if row["canonical_id"] == canonical_id)


def _operand(doc: Doc, canonical_id: str, name: str) -> Doc:
    """Find one operand of a derived row's formula."""
    operands: list[Doc] = _row(doc, canonical_id)["formula"]["operands"]
    return next(operand for operand in operands if operand["name"] == name)


def _segment_aggregation(doc: Doc) -> Doc:
    """The segment total's aggregation, as written in derived.yaml."""
    aggregation: Doc = _operand(doc, SEGMENT_TOTAL, "segment_revenue")["aggregation"]
    return aggregation


def _list_apar_members(doc: Doc) -> None:
    """Write Apar's members into the segment total as a dictionary-declared list."""
    aggregation = _segment_aggregation(doc)
    aggregation.update(member_binding="DECLARED", input_members=APAR_SEGMENTS)


def _dii_aggregation(input_members: list[str]) -> Callable[[Doc], None]:
    """Add a derived row aggregating shareholding categories into ``dii``."""

    def change(doc: Doc) -> None:
        doc["rows"].append(
            {
                "canonical_id": "shp_dii_from_subcategories_pct",
                "value_kind": "PERCENTAGE",
                "period_nature": "INSTANT",
                "applicability_rule_id": "shareholding.every_period",
                "dimension_template": "shareholding_category",
                "meaning": "Test row: DII from its named subcategories.",
                "formula": {
                    "formula_id": "shp_dii_from_subcategories_pct",
                    "version": "1",
                    "operands": [
                        {
                            "name": "holding",
                            "canonical_id": "shp_holding_pct",
                            "temporal_role": "CLOSING",
                            "aggregation": {
                                "axis": "shareholding_category",
                                "input_members": input_members,
                                "output_member": "dii",
                            },
                        }
                    ],
                    "expression": {"op": "OPERAND", "operand": "holding"},
                    "output_kind": "PERCENTAGE",
                    "evidence": "test",
                },
            }
        )

    return change


def _segment_total_keyed_by(elimination_members: list[str]) -> Edit:
    """Key the segment total by a new template: the segment axis kept, the elimination
    basis axis with ``elimination_members`` in place of the operand's members."""

    def add_template(doc: Doc) -> None:
        segment = next(t for t in doc["templates"] if t["template_id"] == "segment")
        segment_axis, elimination_axis = (dict(axis) for axis in segment["axes"])
        elimination_axis["members"] = [{"member": member} for member in elimination_members]
        doc["templates"].append(
            {"template_id": "segment_total", "axes": [segment_axis, elimination_axis]}
        )

    def point_total(doc: Doc) -> None:
        _row(doc, SEGMENT_TOTAL).update(dimension_template="segment_total")

    def apply(directory: Path) -> None:
        _edit(TEMPLATES_FILE, add_template)(directory)
        _edit(FORMULA_SET_FILE, point_total)(directory)

    return apply


@pytest.fixture
def v1_copy(tmp_path: Path) -> Path:
    """A writable copy of dictionary v1 under a temporary root."""
    shutil.copytree(DICTIONARY_ROOT / VERSION, tmp_path / VERSION)
    return tmp_path


def _manifest_counts() -> dict[StatementFamily, int]:
    """Read the hand-authored counts table from the committed manifest."""
    lines = MANIFEST.read_text(encoding="utf-8").split("## Counts per family", 1)[1]
    counts: dict[StatementFamily, int] = {}
    for line in lines.splitlines():
        match = COUNT_ROW.match(line.strip())
        if match:
            counts[StatementFamily(match.group(1))] = int(match.group(2))
        elif counts and not line.startswith("|"):
            break
    return counts


def test_v1_family_counts_equal_the_committed_manifest() -> None:
    """The resolved v1 counts per family are the manifest's hand-counted ones."""
    dictionary = load_dictionary(DICTIONARY_ROOT, VERSION)

    assert dict(dictionary.family_counts()) == _manifest_counts()
    assert set(_manifest_counts()) == set(StatementFamily)


def test_average_dimensional_aggregate_is_rejected_before_evaluation(v1_copy: Path) -> None:
    """Unsupported composition must fail at load, before tuple-unpacking at runtime."""

    def change(doc: Doc) -> None:
        _operand(doc, SEGMENT_TOTAL, "segment_revenue").update(
            canonical_id="segment_capital_employed", temporal_role="AVERAGE"
        )
        _row(doc, "segment_capital_employed")["aggregation_behaviour"] = "SUMMABLE_ACROSS_MEMBERS"

    _edit(FORMULA_SET_FILE, change)(v1_copy / VERSION)
    with pytest.raises(DictionaryLoadError) as error:
        load_dictionary(v1_copy, VERSION)
    assert error.value.defect is DictionaryDefect.TEMPORAL_ROLE_MISFIT
    assert error.value.ids == ("segment_revenue_members_total.segment_revenue",)


def test_separately_printed_apar_derivatives_and_segment_reconciling_lines_have_rows() -> None:
    """Retained Apar FY26 Q2 p6/p4 file six measures beyond folded XBRL subtotals."""
    dictionary = load_dictionary(DICTIONARY_ROOT, VERSION)
    expected = {
        "derivative_financial_assets_noncurrent": StatementFamily.BALANCE_SHEET,
        "derivative_financial_assets_current": StatementFamily.BALANCE_SHEET,
        "derivative_financial_liabilities_noncurrent": StatementFamily.BALANCE_SHEET,
        "derivative_financial_liabilities_current": StatementFamily.BALANCE_SHEET,
        "segment_other_elimination": StatementFamily.SEGMENT,
        "inter_segment_liabilities": StatementFamily.SEGMENT,
    }
    assert {
        row.canonical_id: row.family for row in dictionary.rows if row.canonical_id in expected
    } == expected
    assert sum(dictionary.family_counts().values()) == 259  # 253 existing + six filed measures


# Every line printed on p7 of the retained Apar FY26 Q2 results PDF (the H1 cash-flow statement),
# in page order, with the v1 row that carries it.
APAR_Q2_PAGE7_CASH_FLOW_LINES: dict[str, str] = {
    "Profit before tax & share in net profit / (loss) of associates": "cf_profit_before_tax",
    "Depreciation / amortisation": "cf_adj_depreciation",
    "(Gain)/loss on sale of property, plant and equipment": "cf_adj_gain_loss_sale_ppe",
    "Interest costs": "cf_adj_finance_costs",
    "Interest incomes": "cf_adj_interest_income",
    "Provision for Doubtful Debts / advances (net)": "cf_adj_provisions_current",
    "Unrealised exchange loss/(gain)": "cf_adj_unrealised_fx",
    "Share based payment expense": "cf_adj_share_based_payments",
    "Profit on sale of investments": "cf_adj_profit_sale_investments",
    "(Increase) / decrease in trade and other receivables": "cf_wc_trade_and_other_receivables",
    "(Increase) / decrease in inventories": "cf_wc_inventories",
    "Increase/ (decrease) in trade and other payables": "cf_wc_trade_and_other_payables",
    "Tax paid": "cf_income_taxes_paid",
    "Net cash generated from / (used in) operating activities": "cfo",
    "Acquisition of property, plant and equipment": "cf_capex_ppe",
    "Proceeds from sale of property, plant and equipment": "cf_sale_ppe",
    "Sale / (purchase) of investments- net": "cf_investments_net",
    "Interest received": "cf_interest_received_investing",
    "Net cash generated from / (used in) investing activities": "cfi",
    "Proceeds/(repayments) from short-term borrowings. net": "cf_short_term_borrowings_net",
    "Proceeds from long-term borrowings": "cf_proceeds_borrowings",
    "Repayments of long-term borrowings": "cf_repayment_borrowings",
    "Repayment of Lease Liabilities": "cf_lease_payments",
    "Interest paid": "cf_interest_paid_financing",
    "Dividend Payment": "cf_dividends_paid",
    "Net cash (used in) / generated from financing activities": "cff",
    "Net increase / (decrease)in cash and cash equivalents": "cf_net_change_before_fx",
    "Effect of exchanges rate changes on cash and cash equivalents": "cf_fx_effect",
    "Cash and cash equivalents at the beginning of the year": "cf_cash_opening",
    "Cash and cash equivalents at the end of the year": "cf_cash_closing",
}


def test_every_filed_apar_q2_cash_flow_line_has_a_v1_row() -> None:
    """Completeness is proven line by line, not by the family count: each of the 30 lines
    printed on the retained Q2 cash-flow page names an existing, distinct CASH_FLOW row."""
    dictionary = load_dictionary(DICTIONARY_ROOT, VERSION)
    ids = list(APAR_Q2_PAGE7_CASH_FLOW_LINES.values())

    assert len(ids) == 30
    assert len(set(ids)) == len(ids)
    for canonical_id in ids:
        assert dictionary.row(canonical_id).family is StatementFamily.CASH_FLOW, canonical_id


def test_loaded_dictionary_cannot_be_mutated() -> None:
    """Templates are an immutable tuple, so a frozen dictionary stays as loaded."""
    dictionary = load_dictionary(DICTIONARY_ROOT, VERSION)

    with pytest.raises(AttributeError):
        dictionary.templates.clear()  # type: ignore[attr-defined]
    assert dictionary.template("segment").axis("segment") is not None


def test_v1_pins_the_formula_set_separately_from_the_dictionary(v1_copy: Path) -> None:
    """Editing only derived.yaml moves the formula-set pin and leaves the dictionary pin."""
    before = load_dictionary(v1_copy, VERSION)
    _edit(FORMULA_SET_FILE, lambda doc: _row(doc, "opm_pct").update(meaning="Edited."))(
        v1_copy / VERSION
    )

    after = load_dictionary(v1_copy, VERSION)

    assert after.content_sha256 == before.content_sha256
    assert after.formula_set_sha256 != before.formula_set_sha256
    assert before.row("profit_before_tax_incl_associates").headline


DEFECTS: list[tuple[str, Edit, DictionaryDefect, set[str]]] = [
    (
        "dangling operand id",
        _edit(
            FORMULA_SET_FILE,
            lambda doc: _operand(doc, "opm_pct", "revenue").update(
                canonical_id="revenue_from_operation"
            ),
        ),
        DictionaryDefect.DANGLING_ID,
        {"revenue_from_operation"},
    ),
    (
        "dangling applicability rule",
        _edit("pl.yaml", lambda doc: _row(doc, "sales").update(applicability_rule_id="nope")),
        DictionaryDefect.DANGLING_ID,
        {"nope"},
    ),
    (
        "percentage without the x100 scale",
        _edit(
            FORMULA_SET_FILE,
            lambda doc: _row(doc, "effective_tax_rate_pct")["formula"].update(
                expression={
                    "op": "DIV",
                    "args": [
                        {"op": "OPERAND", "operand": "tax"},
                        {"op": "OPERAND", "operand": "pbt"},
                    ],
                }
            ),
        ),
        DictionaryDefect.UNIT_ALGEBRA,
        {"effective_tax_rate_pct"},
    ),
    (
        "amount minus a per-share amount",
        _edit(
            FORMULA_SET_FILE,
            lambda doc: _operand(doc, "opex_excl_finance_and_da", "finance_costs").update(
                canonical_id="eps_basic"
            ),
        ),
        DictionaryDefect.UNIT_ALGEBRA,
        {"opex_excl_finance_and_da"},
    ),
    (
        "formula cycle",
        _edit(
            FORMULA_SET_FILE,
            lambda doc: _operand(doc, "opex_excl_finance_and_da", "total_expenses").update(
                canonical_id="ebitda_excl_other_income"
            ),
        ),
        DictionaryDefect.CYCLE,
        {"opex_excl_finance_and_da", "ebitda_excl_other_income"},
    ),
    (
        "aggregation lists a member with its own aggregate",
        _edit(FORMULA_SET_FILE, _dii_aggregation(["mutual_funds", "other_dii", "insurance"])),
        DictionaryDefect.MEMBER_OF_MEMBER,
        {"shp_dii_from_subcategories_pct.holding"},
    ),
    (
        "aggregation output among its inputs",
        _edit(FORMULA_SET_FILE, _dii_aggregation(["fpi", "dii"])),
        DictionaryDefect.MEMBER_OF_MEMBER,
        {"shp_dii_from_subcategories_pct.holding"},
    ),
    (
        "aggregate output row without a dimension template",
        _edit(FORMULA_SET_FILE, lambda doc: _row(doc, SEGMENT_TOTAL).pop("dimension_template")),
        DictionaryDefect.DIMENSION_MISFIT,
        {f"{SEGMENT_TOTAL}.segment_revenue"},
    ),
    (
        "aggregate output template replacing a retained axis's members",
        _segment_total_keyed_by(["UNRELATED_ELIMINATION"]),
        DictionaryDefect.DIMENSION_MISFIT,
        {f"{SEGMENT_TOTAL}.segment_revenue"},
    ),
    (
        "one entity's segment members listed in the dictionary",
        _edit(FORMULA_SET_FILE, _list_apar_members),
        DictionaryDefect.DIMENSION_MISFIT,
        {f"{SEGMENT_TOTAL}.segment_revenue"},
    ),
    (
        "aggregate output keyed by another template's axes",
        _edit(
            FORMULA_SET_FILE,
            lambda doc: _row(doc, SEGMENT_TOTAL).update(dimension_template="other_expense_detail"),
        ),
        DictionaryDefect.DIMENSION_MISFIT,
        {f"{SEGMENT_TOTAL}.segment_revenue"},
    ),
    (
        "operand dimensions the output cannot carry",
        _edit(
            FORMULA_SET_FILE,
            lambda doc: _operand(doc, "opm_pct", "revenue").update(canonical_id="segment_revenue"),
        ),
        DictionaryDefect.DIMENSION_MISFIT,
        {"opm_pct.revenue"},
    ),
    (
        "duplicate canonical id across families",
        _edit("segment.yaml", lambda doc: doc["rows"].append(dict(_row(doc, "segment_result")))),
        DictionaryDefect.DUPLICATE_SELECTOR,
        {"segment_result"},
    ),
    (
        "duplicate template member",
        _edit(
            "templates.yaml",
            lambda doc: doc["templates"][0]["axes"][1]["members"].append(
                {"member": "PRE_ELIMINATION"}
            ),
        ),
        DictionaryDefect.DUPLICATE_SELECTOR,
        {"segment.elimination_basis.PRE_ELIMINATION"},
    ),
    (
        "instant operand read as a duration",
        _edit(
            FORMULA_SET_FILE,
            lambda doc: _operand(doc, "receivable_days", "receivables").update(
                temporal_role="DURATION"
            ),
        ),
        DictionaryDefect.TEMPORAL_ROLE_MISFIT,
        {"receivable_days.receivables"},
    ),
    (
        "closing stock read as a duration",
        _edit(
            FORMULA_SET_FILE,
            lambda doc: _operand(doc, "shares_outstanding", "paid_up").update(
                temporal_role="DURATION"
            ),
        ),
        DictionaryDefect.TEMPORAL_ROLE_MISFIT,
        {"shares_outstanding.paid_up"},
    ),
    (
        "opening balance of an instant output",
        _edit(
            FORMULA_SET_FILE,
            lambda doc: _operand(doc, "liabilities_incl_nci", "nci").update(
                temporal_role="OPENING"
            ),
        ),
        DictionaryDefect.TEMPORAL_ROLE_MISFIT,
        {"liabilities_incl_nci.nci"},
    ),
    (
        "per-share row declared period-additive",
        _edit(
            "pl.yaml",
            lambda doc: _row(doc, "eps_basic").update(period_aggregation="ADDITIVE_DURATION"),
        ),
        DictionaryDefect.SCHEMA,
        {"eps_basic"},
    ),
    (
        "formula naming no PBT id over a PBT operand",
        _edit(
            FORMULA_SET_FILE,
            lambda doc: _row(doc, "pbt_margin_pct")["formula"].pop("pbt_id"),
        ),
        DictionaryDefect.SCHEMA,
        {"pbt_margin_pct"},
    ),
    (
        "unknown field",
        _edit("pl.yaml", lambda doc: _row(doc, "sales").update(colour="blue")),
        DictionaryDefect.SCHEMA,
        {"sales"},
    ),
    (
        "two formulas share an identity with different definitions",
        _edit(
            FORMULA_SET_FILE,
            lambda doc: _row(doc, "pbt_margin_pct")["formula"].update(formula_id="opm_pct"),
        ),
        DictionaryDefect.DUPLICATE_SELECTOR,
        {"opm_pct@1"},
    ),
]


@pytest.mark.parametrize(
    ("edit", "defect", "offenders"),
    [pytest.param(edit, defect, ids, id=name) for name, edit, defect, ids in DEFECTS],
)
def test_defective_copy_fails_the_load(
    v1_copy: Path, edit: Edit, defect: DictionaryDefect, offenders: set[str]
) -> None:
    """One introduced defect raises its defect class naming the offending ids."""
    edit(v1_copy / VERSION)

    with pytest.raises(DictionaryLoadError) as raised:
        load_dictionary(v1_copy, VERSION)

    assert raised.value.defect is defect
    assert offenders <= set(raised.value.ids)


def test_aggregation_over_disjoint_subcategories_loads(v1_copy: Path) -> None:
    """The member-of-member check refuses double counting only, not every aggregation."""
    _edit(FORMULA_SET_FILE, _dii_aggregation(["mutual_funds", "other_dii"]))(v1_copy / VERSION)

    dictionary = load_dictionary(v1_copy, VERSION)

    assert dictionary.row("shp_dii_from_subcategories_pct").formula is not None


def test_identical_formula_reuse_loads(v1_copy: Path) -> None:
    """One formula identity may serve two rows when the definitions are identical."""

    def reuse(doc: Doc) -> None:
        copy = dict(_row(doc, "opm_pct"), canonical_id="opm_pct_alias", meaning="Test alias.")
        doc["rows"].append(copy)

    _edit(FORMULA_SET_FILE, reuse)(v1_copy / VERSION)

    dictionary = load_dictionary(v1_copy, VERSION)

    assert dictionary.row("opm_pct_alias").formula == dictionary.row("opm_pct").formula


def test_every_schema_failure_is_named_by_row(v1_copy: Path) -> None:
    """Schema errors in several rows and files are all reported, each by its canonical id."""
    directory = v1_copy / VERSION
    _edit("pl.yaml", lambda doc: _row(doc, "sales").update(colour="blue"))(directory)
    _edit("cash_flow.yaml", lambda doc: _row(doc, "cfo").update(value_kind="MONEY"))(directory)
    _edit("segment.yaml", lambda doc: doc["rows"].append({"meaning": "No id."}))(directory)

    with pytest.raises(DictionaryLoadError) as raised:
        load_dictionary(v1_copy, VERSION)

    assert raised.value.defect is DictionaryDefect.SCHEMA
    rows_in_segment = len(yaml.safe_load((directory / "segment.yaml").read_text())["rows"])
    assert set(raised.value.ids) == {"sales", "cfo", f"segment.yaml[{rows_in_segment - 1}]"}


def test_aggregate_output_template_with_the_operand_members_loads(v1_copy: Path) -> None:
    """A separate output template is accepted when every retained axis keeps its members."""
    _segment_total_keyed_by(["PRE_ELIMINATION", "POST_ELIMINATION"])(v1_copy / VERSION)

    dictionary = load_dictionary(v1_copy, VERSION)

    assert dictionary.row(SEGMENT_TOTAL).dimension_template == "segment_total"


def test_a_malformed_row_does_not_hide_the_other_rows_of_its_file(v1_copy: Path) -> None:
    """A row that is not a mapping is named by position; its siblings are still checked."""
    directory = v1_copy / VERSION

    def break_rows(doc: Doc) -> None:
        _row(doc, "sales").update(colour="blue")
        doc["rows"].append("not a row")

    _edit("pl.yaml", break_rows)(directory)

    with pytest.raises(DictionaryLoadError) as raised:
        load_dictionary(v1_copy, VERSION)

    assert raised.value.defect is DictionaryDefect.SCHEMA
    rows_in_pl = len(yaml.safe_load((directory / "pl.yaml").read_text())["rows"])
    assert set(raised.value.ids) == {"sales", f"pl.yaml[{rows_in_pl - 1}]"}


def test_entity_segment_members_bind_at_evaluation() -> None:
    """The segment total binds the entity's evidenced members as its closed list, once."""
    dictionary = load_dictionary(DICTIONARY_ROOT, VERSION)
    formula = dictionary.row(SEGMENT_TOTAL).formula
    assert formula is not None
    aggregation = formula.operands[0].aggregation
    assert aggregation is not None
    assert aggregation.member_binding is MemberBinding.ENTITY_EVIDENCE
    assert aggregation.input_members == ()

    bound = aggregation.bind_members(APAR_SEGMENTS)

    assert bound.input_members == tuple(APAR_SEGMENTS)
    for bad in ([], ["others", "others"], ["others", "reportable_segments_total"]):
        with pytest.raises(ValueError):
            aggregation.bind_members(bad)
    with pytest.raises(ValueError):
        bound.bind_members(["others"])


def test_declared_aggregation_needs_its_members() -> None:
    """A dictionary-declared closed list cannot be empty."""
    with pytest.raises(ValueError):
        DimensionalAggregation(axis="shareholding_category", output_member="dii")


def test_every_offender_of_the_first_failing_class_is_named(v1_copy: Path) -> None:
    """Two dangling ids are both reported, and a later-class cycle does not mask them."""
    directory = v1_copy / VERSION
    _edit(
        FORMULA_SET_FILE,
        lambda doc: (
            _operand(doc, "opm_pct", "revenue").update(canonical_id="missing_a"),
            _operand(doc, "employee_cost_pct", "employee").update(canonical_id="missing_b"),
            _operand(doc, "opex_excl_finance_and_da", "total_expenses").update(
                canonical_id="ebitda_excl_other_income"
            ),
        ),
    )(directory)

    with pytest.raises(DictionaryLoadError) as raised:
        load_dictionary(v1_copy, VERSION)

    assert raised.value.defect is DictionaryDefect.DANGLING_ID
    assert {"missing_a", "missing_b"} <= set(raised.value.ids)


def test_requested_version_must_match_metadata(v1_copy: Path) -> None:
    """A directory whose metadata names another version is refused."""
    _edit("metadata.yaml", lambda doc: doc.update(version="v2"))(v1_copy / VERSION)

    with pytest.raises(DictionaryLoadError) as raised:
        load_dictionary(v1_copy, VERSION)

    assert raised.value.defect is DictionaryDefect.SCHEMA
