"""Structural and semantic validation of canonical dictionary definitions.

Validation order and complete offender sets are part of the dictionary loader contract.
The loader imports this module only after its definition models have been constructed.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from decimal import Decimal

from fundamentals.canon.applicability import ApplicabilityRule
from fundamentals.canon.dictionary import (
    AggregationBehaviour,
    DictionaryDefect,
    DictionaryLoadError,
    DimensionalAggregation,
    DimensionTemplate,
    Formula,
    FormulaNode,
    FormulaOp,
    FormulaOperand,
    MemberBinding,
    MemberSource,
    PeriodAggregationKind,
    TemplateAxis,
    _FamilyRow,
    _RowSpec,
)
from fundamentals.contracts.canonical import PeriodNature, StatementFamily, TemporalRole, ValueKind

PBT_IDS = frozenset({"profit_before_tax", "profit_before_tax_incl_associates"})
PERCENT_SCALE = Decimal(100)


def validate_dictionary(
    rows: Sequence[_FamilyRow],
    templates: Sequence[DimensionTemplate],
    rules: Sequence[ApplicabilityRule],
) -> None:
    """Run the existing fail-closed checks in their declared first-defect order."""
    by_id = {row.canonical_id: row for row, _ in rows}
    _check_schema(rows, rules)
    _check_dangling(rows, by_id, templates, rules)
    _check_dimensions(rows, by_id, templates)
    _check_temporal_roles(rows, by_id)
    _check_unit_algebra(rows, by_id)
    _check_cycles(rows)
    _check_member_of_member(rows, templates)
    _check_duplicates(rows, templates)


def _raise_if(defect: DictionaryDefect, offenders: Iterable[str]) -> None:
    """Raise ``defect`` naming every offender, if there are any."""
    found = set(offenders)
    if found:
        raise DictionaryLoadError(defect, found)


def _formula_rows(rows: Sequence[_FamilyRow]) -> Iterable[tuple[_RowSpec, Formula]]:
    """Yield each row that carries a formula, with its formula."""
    for row, _ in rows:
        if row.formula is not None:
            yield row, row.formula


def _check_schema(rows: Sequence[_FamilyRow], rules: Sequence[ApplicabilityRule]) -> None:
    """Structural rules the models alone cannot express."""
    offenders: set[str] = set()
    rule_ids = [rule.rule_id for rule in rules]
    offenders.update(rule_id for rule_id in rule_ids if rule_ids.count(rule_id) > 1)
    for row, family in rows:
        derived = family is StatementFamily.DERIVED
        if derived != (row.formula is not None):
            offenders.add(row.canonical_id)
        if row.period_aggregation is PeriodAggregationKind.ADDITIVE_DURATION and (
            row.value_kind is not ValueKind.CURRENCY_AMOUNT
            or row.period_nature is not PeriodNature.DURATION
        ):
            offenders.add(row.canonical_id)
        if row.formula is not None and not _formula_well_formed(row, row.formula):
            offenders.add(row.canonical_id)
    _raise_if(DictionaryDefect.SCHEMA, offenders)


def _formula_well_formed(row: _RowSpec, formula: Formula) -> bool:
    """Output kind matches the row, operands are unique and used, and the PBT id is named."""
    names = [operand.name for operand in formula.operands]
    pbt_operands = {op.canonical_id for op in formula.operands} & PBT_IDS
    pbt_named = formula.pbt_id is None if not pbt_operands else pbt_operands == {formula.pbt_id}
    return (
        formula.output_kind is row.value_kind
        and len(set(names)) == len(names)
        and formula.expression.operand_names() == set(names)
        and pbt_named
    )


def _check_dangling(
    rows: Sequence[_FamilyRow],
    by_id: Mapping[str, _RowSpec],
    templates: Sequence[DimensionTemplate],
    rules: Sequence[ApplicabilityRule],
) -> None:
    """Every referenced id — row, template, rule, axis, member, parent — must exist."""
    template_by_id = {template.template_id: template for template in templates}
    rule_ids = {rule.rule_id for rule in rules}
    offenders: set[str] = set()
    for template in templates:
        for axis in template.axes:
            declared = {member.member for member in axis.members}
            offenders.update(
                f"{template.template_id}.{axis.axis}.{member.parent}"
                for member in axis.members
                if member.parent is not None and member.parent not in declared
            )
    for row, _ in rows:
        if row.applicability_rule_id not in rule_ids:
            offenders.add(row.applicability_rule_id)
        if row.deprecated_by is not None and row.deprecated_by not in by_id:
            offenders.add(row.deprecated_by)
        if row.dimension_template is not None and row.dimension_template not in template_by_id:
            offenders.add(row.dimension_template)
    for _, formula in _formula_rows(rows):
        conditions = (
            formula.qualification.conditions + formula.qualification.exclusions
            if (formula.qualification is not None)
            else ()
        )
        offenders.update(c.canonical_id for c in conditions if c.canonical_id not in by_id)
        if formula.pbt_id is not None and formula.pbt_id not in by_id:
            offenders.add(formula.pbt_id)
        for operand in formula.operands:
            target = by_id.get(operand.canonical_id)
            if target is None:
                offenders.add(operand.canonical_id)
            elif operand.aggregation is not None:
                offenders.update(_dangling_members(operand, target, template_by_id))
    _raise_if(DictionaryDefect.DANGLING_ID, offenders)


def _dangling_members(
    operand: FormulaOperand, target: _RowSpec, templates: Mapping[str, DimensionTemplate]
) -> set[str]:
    """Aggregation axis and members must be declared by the operand row's template."""
    assert operand.aggregation is not None
    aggregation = operand.aggregation
    template = templates.get(target.dimension_template or "")
    axis = template.axis(aggregation.axis) if template is not None else None
    if axis is None:
        return {f"{operand.canonical_id}.{aggregation.axis}"}
    if aggregation.output_member not in _declared(axis):
        return {f"{aggregation.axis}.{aggregation.output_member}"}
    if axis.member_source is MemberSource.ENTITY_EVIDENCE:
        return set()
    return {
        f"{aggregation.axis}.{member}"
        for member in aggregation.input_members
        if member not in _declared(axis)
    }


def _declared(axis: TemplateAxis) -> set[str]:
    """Members an axis declares itself: its closed list and its aggregate members."""
    return {member.member for member in axis.members} | set(axis.aggregate_members)


def _check_dimensions(
    rows: Sequence[_FamilyRow],
    by_id: Mapping[str, _RowSpec],
    templates: Sequence[DimensionTemplate],
) -> None:
    """The output must carry exactly its operands' axes, and aggregations must fit their axis.

    Operands share the output's dimension set (data spec §1), so an operand's template
    axes equal the output's. An aggregation keeps its axis on the output with the output
    member declared there; a ``DECLARED`` list needs a closed-list axis and an
    ``ENTITY_EVIDENCE`` binding an entity-evidence axis with no members listed here.
    Each shared axis keeps its member source and closed members on the output.
    """
    template_by_id = {template.template_id: template for template in templates}
    offenders: set[str] = set()
    for row, formula in _formula_rows(rows):
        output = template_by_id.get(row.dimension_template or "")
        for operand in formula.operands:
            source = template_by_id.get(by_id[operand.canonical_id].dimension_template or "")
            if (
                _axis_names(source) != _axis_names(output)
                or not _members_carry_over(operand.aggregation, source, output)
                or (
                    operand.aggregation is not None
                    and not _aggregation_fits(operand.aggregation, source, output)
                )
            ):
                offenders.add(f"{row.canonical_id}.{operand.name}")
    _raise_if(DictionaryDefect.DIMENSION_MISFIT, offenders)


def _axis_names(template: DimensionTemplate | None) -> frozenset[str]:
    """The axes a template's keys carry; none without a template."""
    return frozenset() if template is None else frozenset(axis.axis for axis in template.axes)


def _members_carry_over(
    aggregation: DimensionalAggregation | None,
    source: DimensionTemplate | None,
    output: DimensionTemplate | None,
) -> bool:
    """Every axis keeps its member source and closed members from operand to output.

    A retained axis also keeps its aggregate members; only the aggregated axis may differ
    there, since the output declares the aggregate member it produces.
    """
    if source is None or output is None:
        return source is output
    for source_axis in source.axes:
        output_axis = output.axis(source_axis.axis)
        if (
            output_axis is None
            or output_axis.member_source is not source_axis.member_source
            or output_axis.members != source_axis.members
        ):
            return False
        aggregated = aggregation is not None and aggregation.axis == source_axis.axis
        if not aggregated and output_axis.aggregate_members != source_axis.aggregate_members:
            return False
    return True


def _aggregation_fits(
    aggregation: DimensionalAggregation,
    source: DimensionTemplate | None,
    output: DimensionTemplate | None,
) -> bool:
    """The output declares the aggregate member, and the binding matches the axis's source."""
    source_axis = source.axis(aggregation.axis) if source is not None else None
    output_axis = output.axis(aggregation.axis) if output is not None else None
    if source_axis is None or output_axis is None:
        return False
    if aggregation.member_binding is MemberBinding.DECLARED:
        binding_fits = source_axis.member_source is MemberSource.CLOSED_LIST
    else:
        binding_fits = (
            source_axis.member_source is MemberSource.ENTITY_EVIDENCE
            and not aggregation.input_members
        )
    if output_axis.member_source is MemberSource.ENTITY_EVIDENCE:
        output_declared = aggregation.output_member in output_axis.aggregate_members
    else:
        output_declared = aggregation.output_member in _declared(output_axis)
    return binding_fits and output_declared


def _check_temporal_roles(rows: Sequence[_FamilyRow], by_id: Mapping[str, _RowSpec]) -> None:
    """Each operand role must fit the operand's and the output's period nature."""
    offenders: set[str] = set()
    for row, formula in _formula_rows(rows):
        for operand in formula.operands:
            nature = by_id[operand.canonical_id].period_nature
            if not _role_fits(operand.temporal_role, nature, row.period_nature) or (
                operand.temporal_role is TemporalRole.AVERAGE and operand.aggregation is not None
            ):
                offenders.add(f"{row.canonical_id}.{operand.name}")
    _raise_if(DictionaryDefect.TEMPORAL_ROLE_MISFIT, offenders)


def _role_fits(role: TemporalRole, operand: PeriodNature, output: PeriodNature) -> bool:
    """``DURATION`` joins durations; ``CLOSING`` reads an instant at the output's end;
    ``OPENING`` and ``AVERAGE`` need a duration output with a start."""
    if role is TemporalRole.DURATION:
        return operand is PeriodNature.DURATION and output is PeriodNature.DURATION
    if role is TemporalRole.CLOSING:
        return operand is PeriodNature.INSTANT
    return operand is PeriodNature.INSTANT and output is PeriodNature.DURATION


# Unit algebra over value kinds; ``None`` is a dimensionless literal.
_Kind = ValueKind | None
_AMOUNT_DIVISIONS: Mapping[tuple[ValueKind, ValueKind], ValueKind] = {
    (ValueKind.CURRENCY_AMOUNT, ValueKind.PER_SHARE_AMOUNT): ValueKind.COUNT,
    (ValueKind.CURRENCY_AMOUNT, ValueKind.COUNT): ValueKind.PER_SHARE_AMOUNT,
}


class _UnitAlgebraError(ValueError):
    """An expression combines kinds the algebra does not allow."""


def _check_unit_algebra(rows: Sequence[_FamilyRow], by_id: Mapping[str, _RowSpec]) -> None:
    """Every expression must reduce to the declared output kind (days via the day count)."""
    offenders: set[str] = set()
    for row, formula in _formula_rows(rows):
        operand_kinds: dict[str, ValueKind] = {}
        for operand in formula.operands:
            target = by_id[operand.canonical_id]
            if (
                operand.aggregation is not None
                and target.aggregation_behaviour is not AggregationBehaviour.SUMMABLE_ACROSS_MEMBERS
            ):
                offenders.add(f"{row.canonical_id}.{operand.name}")
            operand_kinds[operand.name] = target.value_kind
        try:
            kind = _kind_of(formula.expression, operand_kinds.__getitem__)
        except _UnitAlgebraError:
            offenders.add(row.canonical_id)
            continue
        if formula.day_count is not None:
            fits = (
                kind is ValueKind.RATIO
                and formula.output_kind is ValueKind.DAYS
                and row.period_nature is PeriodNature.DURATION
            )
        else:
            fits = kind is formula.output_kind
        if not fits:
            offenders.add(row.canonical_id)
    _raise_if(DictionaryDefect.UNIT_ALGEBRA, offenders)


def _kind_of(node: FormulaNode, operand_kind: Callable[[str], ValueKind]) -> _Kind:
    """Reduce an expression to its value kind, or raise ``_UnitAlgebraError``."""
    if node.op is FormulaOp.OPERAND:
        assert node.operand is not None
        return operand_kind(node.operand)
    if node.op is FormulaOp.LITERAL:
        return None
    kinds = [_kind_of(arg, operand_kind) for arg in node.args]
    if node.op in (FormulaOp.ADD, FormulaOp.SUB):
        if len(set(kinds)) != 1:
            raise _UnitAlgebraError(node.op)
        return kinds[0]
    left, right = kinds
    if node.op is FormulaOp.MUL:
        return _multiply(node, left, right)
    if right is None or left == right:
        return left if right is None else ValueKind.RATIO
    if left is not None and (left, right) in _AMOUNT_DIVISIONS:
        return _AMOUNT_DIVISIONS[(left, right)]
    raise _UnitAlgebraError(node.op)


def _multiply(node: FormulaNode, left: _Kind, right: _Kind) -> _Kind:
    """Scale by a literal keeps the kind, except ``ratio × 100`` which is a percentage."""
    literal = next((arg.value for arg in node.args if arg.op is FormulaOp.LITERAL), None)
    kinds = {left, right}
    if kinds == {ValueKind.RATIO, None} and literal == PERCENT_SCALE:
        return ValueKind.PERCENTAGE
    if None in kinds:
        return left if right is None else right
    if kinds == {ValueKind.RATIO}:
        return ValueKind.RATIO
    raise _UnitAlgebraError(node.op)


def _check_cycles(rows: Sequence[_FamilyRow]) -> None:
    """Depth-first search over formula operands; every row on a cycle is named."""
    edges = {
        row.canonical_id: [operand.canonical_id for operand in formula.operands]
        for row, formula in _formula_rows(rows)
    }
    offenders: set[str] = set()
    state: dict[str, int] = {}
    path: list[str] = []

    def visit(node: str) -> None:
        state[node] = 1
        path.append(node)
        for target in edges.get(node, []):
            if state.get(target) == 1:
                offenders.update(path[path.index(target) :])
            elif target not in state:
                visit(target)
        path.pop()
        state[node] = 2

    for node in edges:
        if node not in state:
            visit(node)
    _raise_if(DictionaryDefect.CYCLE, offenders)


def _check_member_of_member(
    rows: Sequence[_FamilyRow], templates: Sequence[DimensionTemplate]
) -> None:
    """Refuse aggregation lists that double count: a member with its own aggregate,
    a repeated member, or the output among the inputs."""
    aggregations = [
        (row.canonical_id, operand)
        for row, formula in _formula_rows(rows)
        for operand in formula.operands
        if operand.aggregation is not None
    ]
    children: dict[tuple[str, str], set[str]] = {}
    for template in templates:
        for axis in template.axes:
            for member in axis.members:
                if member.parent is not None:
                    children.setdefault((axis.axis, member.parent), set()).add(member.member)
    for _, operand in aggregations:
        assert operand.aggregation is not None
        key = (operand.aggregation.axis, operand.aggregation.output_member)
        children.setdefault(key, set()).update(operand.aggregation.input_members)
    offenders: set[str] = set()
    for row_id, operand in aggregations:
        assert operand.aggregation is not None
        aggregation = operand.aggregation
        inputs = aggregation.input_members
        double = len(set(inputs)) != len(inputs) or aggregation.output_member in inputs
        for name in inputs:
            below = _descendants(aggregation.axis, name, children)
            double = double or bool(below & set(inputs))
        if double:
            offenders.add(f"{row_id}.{operand.name}")
    _raise_if(DictionaryDefect.MEMBER_OF_MEMBER, offenders)


def _descendants(axis: str, member: str, children: Mapping[tuple[str, str], set[str]]) -> set[str]:
    """Every member that ``member`` aggregates, directly or through other aggregates."""
    found: set[str] = set()
    pending = [member]
    while pending:
        for child in children.get((axis, pending.pop()), set()):
            if child not in found and child != member:
                found.add(child)
                pending.append(child)
    return found


def _check_duplicates(rows: Sequence[_FamilyRow], templates: Sequence[DimensionTemplate]) -> None:
    """Two rows, templates, template instantiations or differing formula definitions must
    never share one selector; an identical formula may be reused."""
    offenders: set[str] = set()
    seen: set[str] = set()
    for row, _ in rows:
        if row.canonical_id in seen:
            offenders.add(row.canonical_id)
        seen.add(row.canonical_id)
    formulas: dict[tuple[str, str], Formula] = {}
    for _, formula in _formula_rows(rows):
        first = formulas.setdefault((formula.formula_id, formula.version), formula)
        if first != formula:
            offenders.add(f"{formula.formula_id}@{formula.version}")
    template_ids = [template.template_id for template in templates]
    offenders.update(t for t in template_ids if template_ids.count(t) > 1)
    for template in templates:
        axes = [axis.axis for axis in template.axes]
        offenders.update(f"{template.template_id}.{a}" for a in axes if axes.count(a) > 1)
        for axis in template.axes:
            members = [member.member for member in axis.members] + list(axis.aggregate_members)
            offenders.update(
                f"{template.template_id}.{axis.axis}.{m}" for m in members if members.count(m) > 1
            )
    _raise_if(DictionaryDefect.DUPLICATE_SELECTOR, offenders)
