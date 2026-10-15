"""Memory supports resolved to references, and the text the panel reviews (ledger spec §2; plan
D4, M2, M6, M9).

A support resolves to a :class:`SupportRef` whose version status is derived at ``as_of``: a
claim with its version's identity, figures, guidance contract, citation and capture blob; a
version with one claim reference per claim; any other target with its row.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, LiteralString

from psycopg import Cursor, sql
from psycopg.rows import dict_row

from fundamentals.contracts.ledger import Citation, CitationKind, GuidanceContract
from fundamentals.contracts.memory import SupportRef, SupportTarget
from fundamentals.contracts.snapshot import canonical_json
from fundamentals.ledger import store
from fundamentals.ledger.citations import bound_contract, contract_bindings
from fundamentals.ledger.display import narrative
from fundamentals.ledger.lifecycle import version_status

_ITEM: LiteralString = (
    "SELECT to_jsonb(i) - 'statement_search' AS item FROM eqos.memory_items i WHERE i.id = %s"
)
_SUPPORTS: LiteralString = "SELECT * FROM eqos.memory_supports WHERE item_id = %s ORDER BY id"
_VERSION: LiteralString = """SELECT v.id AS version_id, e.entity_key AS stock, r.period,
    r.kind AS report_kind, r.entity_id
FROM eqos.report_versions v JOIN eqos.reports r ON r.id = v.report_id
JOIN eqos.reporting_entities e ON e.id = r.entity_id WHERE v.id = %s"""
_CLAIMS: LiteralString = """SELECT c.*, cap.blob_sha256 FROM eqos.numeric_claims c
LEFT JOIN eqos.capture_refs cap ON cap.id = c.capture_ref_id
WHERE {} ORDER BY c.id"""
_ROW: LiteralString = "SELECT to_jsonb(t) AS row FROM {} t WHERE t.id = %s"
_TABLES = {
    SupportTarget.DEFINITION_RECORD: "definition_records",
    SupportTarget.DISPOSITION: "queue_dispositions",
    SupportTarget.DECISION: "decisions",
    SupportTarget.CAPTURE: "capture_refs",
}


def support_refs(
    cursor: Cursor[Any], item_id: int, as_of: datetime | None
) -> tuple[SupportRef, ...]:
    """The item's supports in id order, statuses derived at ``as_of`` (``None``: now)."""
    return tuple(_ref(cursor, row, as_of) for row in _rows(cursor, _SUPPORTS, item_id))


def review_text(cursor: Cursor[Any], item_id: int) -> str:
    """Canonical JSON of the item and its resolved supports, with each quote claim's bound
    contract and its bindings and each version's narrative, as the panel reviewer reads it."""
    ((item,),) = cursor.execute(_ITEM, (item_id,)).fetchall()
    shown = [_shown(cursor, ref) for ref in support_refs(cursor, item_id, None)]
    return canonical_json({"item": item, "supports": shown})


def _rows(
    cursor: Cursor[Any], query: LiteralString | sql.Composed, value: int
) -> list[dict[str, Any]]:
    """Every row of a one-parameter read, as dicts."""
    with cursor.connection.cursor(row_factory=dict_row) as own:
        return own.execute(query, (value,)).fetchall()


def _ref(cursor: Cursor[Any], row: dict[str, Any], as_of: datetime | None) -> SupportRef:
    """One support row as its reference."""
    target = next(target for target in SupportTarget if row[target.value] is not None)
    target_id = int(row[target.value])
    if target is SupportTarget.CLAIM:
        (claim,) = _claims(cursor, "c.id", target_id, as_of)
        return claim
    if target is SupportTarget.VERSION:
        return SupportRef(
            target=target,
            target_id=target_id,
            claims=_claims(cursor, "c.version_id", target_id, as_of),
            **_identity(cursor, target_id, as_of),
        )
    query = sql.SQL(_ROW).format(sql.Identifier("eqos", _TABLES[target]))
    ((found,),) = cursor.execute(query, (target_id,)).fetchall()
    blob = found["blob_sha256"] if target is SupportTarget.CAPTURE else None
    return SupportRef(target=target, target_id=target_id, row=found, blob_sha256=blob)


def _claims(
    cursor: Cursor[Any], column: LiteralString, value: int, as_of: datetime | None
) -> tuple[SupportRef, ...]:
    """Claim references for the claims where ``column`` is ``value``."""
    refs = []
    for row in _rows(cursor, sql.SQL(_CLAIMS).format(sql.SQL(column + " = %s")), value):
        citation = Citation.model_validate({**row, "kind": row["citation_kind"]})
        quoted = citation.kind is CitationKind.SOURCE_QUOTE
        refs.append(
            SupportRef(
                target=SupportTarget.CLAIM,
                target_id=row["id"],
                claim_key=row["claim_key"],
                value=row["value"],
                lower_bound=row["lower_bound"],
                upper_bound=row["upper_bound"],
                unit=row["unit"],
                qualifiers=tuple(row["qualifiers"]),
                contract=GuidanceContract.model_validate(row) if quoted else None,
                citation=citation,
                blob_sha256=row["blob_sha256"],
                **_identity(cursor, row["version_id"], as_of),
            )
        )
    return tuple(refs)


def _identity(cursor: Cursor[Any], version_id: int, as_of: datetime | None) -> dict[str, Any]:
    """A version's stock, report period and kind, and its status at ``as_of``."""
    (version,) = _rows(cursor, _VERSION, version_id)
    status = version_status(cursor, version_id, as_of=as_of)
    return {key: version[key] for key in ("version_id", "stock", "period", "report_kind")} | {
        "version_status": status
    }


def _shown(cursor: Cursor[Any], ref: SupportRef) -> dict[str, Any]:
    """A reference as reviewed: a version adds its narrative, a quote claim the contract the
    sealed imports bind (plan D4, M9) and each binding's claim and ledger source."""
    shown = ref.model_dump(mode="json", exclude={"claims"})
    shown["claims"] = [_shown(cursor, claim) for claim in ref.claims]
    if ref.version_id is None:
        return shown
    draft = store.read_version(cursor, ref.version_id)
    if ref.target is SupportTarget.VERSION:
        shown["narrative"] = narrative(draft.sections, draft.claims).decode()
    elif ref.contract is not None:
        claim = next(claim for claim in draft.claims if claim.claim_key == ref.claim_key)
        (version,) = _rows(cursor, _VERSION, ref.version_id)
        bound = bound_contract(cursor, claim, version["entity_id"])
        bindings = contract_bindings(cursor, claim, version["entity_id"])
        shown["bound_contract"] = None if bound is None else bound.model_dump(mode="json")
        shown["bindings"] = [binding.model_dump(mode="json") for binding in bindings]
    return shown
