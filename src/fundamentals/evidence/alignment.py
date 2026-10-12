"""Filing-specific XBRL–PDF alignment proofs per measurement key (D1a Task 7; data spec §2).

A proof counts as demonstrated for one filing and one key only, and is never generalised
into a mapping tier. A ``SUBTOTAL_IDENTITY`` holds when the identity holds within interval
tolerance in both representations from that key's own values (same period and dimensions);
a ``LAYOUT_POSITION`` holds when both representations' anchors supplied the key. A rule
with any participant missing or without a value in either representation yields no proof.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from enum import StrEnum
from fractions import Fraction
from pathlib import Path
from types import MappingProxyType
from typing import Annotated

import yaml
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    ValidationError,
    model_validator,
)

from fundamentals.canon.dictionary import FormulaNode, FormulaOp
from fundamentals.contracts.canonical import Representation
from fundamentals.contracts.comparison import SourceState
from fundamentals.contracts.evidence import FilingPackage, InterpretationStatus, KeySelection
from fundamentals.contracts.interval import Interval, UndefinedDivisionError
from fundamentals.contracts.measurement_key import MeasurementKey

_SUBTOTAL_SHAPE = "a SUBTOTAL_IDENTITY rule has an identity and no layout anchor"
_LAYOUT_SHAPE = "a LAYOUT_POSITION rule has an anchor per representation and no identity"
_BAD_FILE = "alignment rule file {path} is invalid: {detail}"
_DUPLICATE_RULE = "alignment rule ids repeat: {ids}"
_REPRESENTATIONS = (Representation.XBRL, Representation.PDF)

Selections = Mapping[tuple[str, Representation], KeySelection]


class AlignmentRuleKind(StrEnum):
    """How a rule proves one key's alignment in one filing."""

    SUBTOTAL_IDENTITY = "SUBTOTAL_IDENTITY"
    LAYOUT_POSITION = "LAYOUT_POSITION"


class AlignmentLoadError(ValueError):
    """The alignment rule file is malformed."""


def _frozen_anchor(value: Mapping[Representation, str]) -> Mapping[Representation, str]:
    """Copy an anchor mapping into a read-only view."""
    return MappingProxyType(dict(value))


class AlignmentRule(BaseModel):
    """One declared alignment rule for one canonical id."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str = Field(min_length=1)
    kind: AlignmentRuleKind
    canonical_id: str = Field(min_length=1)
    identity: FormulaNode | None = None
    layout_anchor: (
        Annotated[
            Mapping[Representation, str],
            AfterValidator(_frozen_anchor),
            PlainSerializer(dict),
        ]
        | None
    ) = None
    evidence_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def _shape(self) -> AlignmentRule:
        """A subtotal rule carries an identity; a layout rule an anchor for both sides."""
        if self.kind is AlignmentRuleKind.SUBTOTAL_IDENTITY:
            if self.identity is None or self.layout_anchor is not None:
                raise ValueError(_SUBTOTAL_SHAPE)
        elif self.identity is not None or set(self.layout_anchor or {}) != set(_REPRESENTATIONS):
            raise ValueError(_LAYOUT_SHAPE)
        return self


class AlignmentRuleSet(BaseModel):
    """A versioned, content-pinned set of alignment rules."""

    model_config = ConfigDict(frozen=True)

    version: str
    content_sha256: str
    rules: tuple[AlignmentRule, ...]


class _RuleFile(BaseModel):
    """The rule file as written."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str = Field(min_length=1)
    rules: tuple[AlignmentRule, ...]


class AlignmentProof(BaseModel):
    """Whether one rule held for one key of one package, naming every participating row."""

    model_config = ConfigDict(frozen=True)

    proof_id: int | None
    package_id: int
    key: MeasurementKey
    rule_id: str
    rule_set_version: str
    xbrl_interpretation_id: int
    pdf_interpretation_id: int
    participants: tuple[tuple[int, Representation], ...]
    holds: bool

    def participants_digest(self) -> str:
        """SHA-256 of the sorted participant list (the proof's identity within its key)."""
        payload = sorted(
            [item_id, representation.value] for item_id, representation in self.participants
        )
        text = json.dumps(payload, separators=(",", ":"))
        return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_alignment_rules(path: Path) -> AlignmentRuleSet:
    """Load and validate one alignment rule file; its bytes are its content hash."""
    body = path.read_bytes()
    try:
        parsed = _RuleFile.model_validate(yaml.safe_load(body))
    except (ValidationError, yaml.YAMLError) as error:
        raise AlignmentLoadError(_BAD_FILE.format(path=path, detail=error)) from error
    ids = [rule.rule_id for rule in parsed.rules]
    repeated = sorted({rule_id for rule_id in ids if ids.count(rule_id) > 1})
    if repeated:
        raise AlignmentLoadError(_DUPLICATE_RULE.format(ids=repeated))
    return AlignmentRuleSet(
        version=parsed.version,
        content_sha256=hashlib.sha256(body).hexdigest(),
        rules=parsed.rules,
    )


def prove_alignment(
    package: FilingPackage, selections: Selections, rules: AlignmentRuleSet
) -> tuple[AlignmentProof, ...]:
    """Every proof the rules yield for the package's selected keys.

    ``selections`` are keyed by (measurement-key digest, representation), so each period
    and each dimension member is proven separately and never names another key's rows.
    """
    if package.package_id is None:
        raise ValueError("package is not stored")
    proofs: list[AlignmentProof] = []
    targets = {
        selection.key
        for selection in selections.values()
        if selection.package_id == package.package_id
    }
    for rule in rules.rules:
        for key in sorted(
            (item for item in targets if item.canonical_id == rule.canonical_id),
            key=lambda item: item.digest(),
        ):
            proof = _prove(rule, key, package.package_id, selections, rules.version)
            if proof is not None:
                proofs.append(proof)
    return tuple(proofs)


def _prove(
    rule: AlignmentRule,
    key: MeasurementKey,
    package_id: int,
    selections: Selections,
    version: str,
) -> AlignmentProof | None:
    """One rule over one key, or ``None`` when a participant is missing on either side."""
    names = sorted(rule.identity.operand_names()) if rule.identity is not None else []
    participants: list[tuple[int, Representation]] = []
    targets: dict[Representation, int] = {}
    holds = True
    for representation in _REPRESENTATIONS:
        target = _valued(selections, key, representation, package_id)
        if target is None:
            return None
        target_id, target_interval, entry_id = target
        targets[representation] = target_id
        participants.append((target_id, representation))
        if rule.kind is AlignmentRuleKind.LAYOUT_POSITION:
            assert rule.layout_anchor is not None
            holds = holds and _anchored(entry_id, rule.layout_anchor[representation])
            continue
        values: dict[str, Interval] = {}
        for name in names:
            operand = _valued(
                selections,
                key.model_copy(update={"canonical_id": name}),
                representation,
                package_id,
            )
            if operand is None:
                return None
            participants.append((operand[0], representation))
            values[name] = operand[1]
        assert rule.identity is not None
        try:
            computed = _interval(rule.identity, values)
        except UndefinedDivisionError:
            return None
        holds = holds and computed.intersects(target_interval)
    return AlignmentProof(
        proof_id=None,
        package_id=package_id,
        key=key,
        rule_id=rule.rule_id,
        rule_set_version=version,
        xbrl_interpretation_id=targets[Representation.XBRL],
        pdf_interpretation_id=targets[Representation.PDF],
        participants=tuple(sorted(participants, key=lambda item: (item[1].value, item[0]))),
        holds=holds,
    )


def _valued(
    selections: Selections, key: MeasurementKey, representation: Representation, package_id: int
) -> tuple[int, Interval, str | None] | None:
    """The selected, mapped, bounded interpretation of one key in one representation."""
    selection = selections.get((key.digest(), representation))
    if selection is None or selection.package_id != package_id:
        return None
    chosen = selection.interpretation
    if (
        selection.state is not SourceState.VALUE
        or chosen is None
        or chosen.interpretation_id is None
        or chosen.status is not InterpretationStatus.MAPPED
        or chosen.interval is None
    ):
        return None
    return chosen.interpretation_id, chosen.interval, chosen.mapping_entry_id


def _anchored(entry_id: str | None, anchor: str) -> bool:
    """Whether a mapping entry is the anchor or a member of its entry-id family."""
    return entry_id is not None and (entry_id == anchor or entry_id.startswith(anchor + "."))


def _interval(node: FormulaNode, values: Mapping[str, Interval]) -> Interval:
    """Evaluate an identity over intervals, exactly."""
    if node.op is FormulaOp.OPERAND:
        assert node.operand is not None
        return values[node.operand]
    if node.op is FormulaOp.LITERAL:
        assert node.value is not None
        return Interval.exact(Fraction(node.value))
    args = [_interval(arg, values) for arg in node.args]
    if node.op is FormulaOp.ADD:
        total = args[0]
        for item in args[1:]:
            total = total.add(item)
        return total
    left, right = args
    if node.op is FormulaOp.SUB:
        return left.sub(right)
    if node.op is FormulaOp.MUL:
        return left.mul(right)
    return left.div(right)
