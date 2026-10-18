"""The citation-graph holds and retention facts of every non-expired capture (plan D9 R4, R5).

Holds are one recursive walk from every root over the R4 edges. Node kinds: ``V`` report
version, ``K`` numeric claim, ``Q`` queue item, ``I`` interpretation, ``T`` calculation trace,
``C`` capture. An interpretation's occurrence shares its capture (0001), so reaching the
interpretation reaches it. Run manifests and outcomes are never roots.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any, LiteralString

import psycopg
import yaml
from psycopg.rows import dict_row

from fundamentals.contracts.retention import CaptureFacts, HoldRoot
from fundamentals.ledger.numeral_scan import LOCATION_MARKER

HOLDS_FILE = Path("retention") / "holds.yaml"
MAPPINGS_DIR = "mappings"
FIXTURE_KEY = "capture_sha256"
_SHA256 = re.compile(r"[0-9a-f]{64}")

_FACTS: LiteralString = """
WITH RECURSIVE edges(from_kind, from_id, to_kind, to_id) AS MATERIALIZED (
    SELECT 'V', version_id, 'K', id FROM eqos.numeric_claims
    UNION ALL SELECT 'V', s.version_id, 'C', m[1]::bigint
        FROM eqos.report_sections s, regexp_matches(s.body, %(marker)s, 'g') m
        WHERE m[1] ~ '^[0-9]+$'
    UNION ALL SELECT 'K', id, 'C', capture_ref_id FROM eqos.numeric_claims
    UNION ALL SELECT 'K', id, 'I', interpretation_id FROM eqos.numeric_claims
    UNION ALL SELECT 'K', id, 'T', calculation_trace_id FROM eqos.numeric_claims
    UNION ALL SELECT 'K', c.id, 'C', b.capture_ref_id FROM eqos.numeric_claims c
        JOIN eqos.fact_rows f ON (f.origin, f.origin_id) = (c.fact_origin, c.fact_origin_id)
        JOIN eqos.legacy_evidence_bindings b
            ON (b.target_store, b.row_handle) = (f.target_store, f.handle)
    UNION ALL SELECT 'K', c.id, 'I', a.interpretation_id FROM eqos.numeric_claims c
        JOIN eqos.fact_admissions a
            ON (a.fact_origin, a.fact_origin_id) = (c.fact_origin, c.fact_origin_id)
    UNION ALL SELECT 'K', c.id, s.kind, s.id FROM eqos.numeric_claims c
        JOIN eqos.pair_outcomes p ON p.id = c.pair_outcome_id
        JOIN eqos.result_source_values v ON v.id IN (p.left_value_id, p.right_value_id)
        CROSS JOIN LATERAL (VALUES ('I', v.interpretation_id), ('T', v.calculation_trace_id))
            s(kind, id)
    UNION ALL SELECT 'Q', item_id, 'I', interpretation_id FROM eqos.queue_item_inputs
    UNION ALL SELECT 'Q', i.item_id, 'C', o.capture_ref_id FROM eqos.queue_item_inputs i
        JOIN eqos.occurrences o ON o.id = i.occurrence_id
    UNION ALL SELECT 'Q', i.item_id, 'C', a.capture_ref_id FROM eqos.queue_item_inputs i
        JOIN eqos.acquisition_attempts a ON a.id = i.attempt_id
    UNION ALL SELECT 'Q', item_id, 'T', calculation_trace_id FROM eqos.queue_item_traces
    UNION ALL SELECT 'I', id, 'C', capture_ref_id FROM eqos.interpretations
    UNION ALL SELECT 'I', interpretation_id, 'I', operand_interpretation_id
        FROM eqos.interpretation_operands
    UNION ALL SELECT 'I', interpretation_id, 'I', evidence_interpretation_id
        FROM eqos.interpretation_condition_evidence
    UNION ALL SELECT 'I', interpretation_id, 'T', calculation_trace_id
        FROM eqos.construction_traces
    UNION ALL SELECT 'T', calculation_trace_id, 'I', interpretation_id
        FROM eqos.calculation_trace_operands
    UNION ALL SELECT 'T', calculation_trace_id, 'T', operand_trace_id
        FROM eqos.calculation_trace_operands
), roots(root, kind, id) AS (
    SELECT 'REPORT_VERSION', 'V', id FROM eqos.report_versions
    UNION ALL SELECT 'MEMORY_SUPPORT', t.kind, t.id FROM eqos.memory_supports s
        LEFT JOIN eqos.queue_dispositions d ON d.id = s.disposition_id
        CROSS JOIN LATERAL (VALUES ('C', s.capture_ref_id), ('K', s.claim_id),
                                   ('V', s.version_id), ('Q', d.item_id)) t(kind, id)
    UNION ALL SELECT CASE WHEN EXISTS (SELECT 1 FROM eqos.queue_dispositions d
                                       WHERE d.item_id = q.id)
                     THEN 'QUEUE_ITEM' ELSE 'OPEN_QUEUE_ITEM' END, 'Q', q.id
        FROM eqos.queue_items q
    UNION ALL SELECT 'OPEN_SCREEN_REVIEW', 'C', c.id FROM eqos.screen_run_pairs p
        JOIN eqos.screen_runs r ON r.id IN (p.screener_run_id, p.tijori_run_id)
        CROSS JOIN LATERAL (SELECT r.definition_capture_ref_id UNION SELECT r.capture_ref_id
            UNION SELECT capture_ref_id FROM eqos.screen_other_vendor_reads o
            WHERE o.pair_id = p.id) c(id)
        WHERE p.id IN (SELECT pair_id FROM eqos.screen_review_pending)
    UNION ALL SELECT 'LEGACY_BINDING', 'C', capture_ref_id FROM eqos.legacy_evidence_bindings
    UNION ALL SELECT 'IDENTITY_EVENT', 'C', c.capture_ref_id FROM eqos.identity_events e
        JOIN eqos.evidence_input_captures c ON c.evidence_input_id = e.evidence_input_id
    UNION ALL SELECT 'ONBOARDING_RECORD', 'C', c.capture_ref_id FROM eqos.onboarding_records o
        LEFT JOIN eqos.namespace_verifications v ON v.onboarding_record_id = o.id
        JOIN eqos.evidence_input_captures c
            ON c.evidence_input_id IN (o.evidence_input_id, v.evidence_input_id)
    UNION ALL SELECT 'QUALIFICATION_FIXTURE', 'C', id FROM eqos.capture_refs
        WHERE blob_sha256 = ANY (%(fixtures)s)
    UNION ALL SELECT 'MANIFEST_INPUT', 'C', id FROM eqos.capture_refs
        WHERE blob_sha256 = ANY (%(manifests)s)
), reach(root, kind, id) AS (
    SELECT root, kind, id FROM roots WHERE id IS NOT NULL
    UNION
    SELECT r.root, e.to_kind, e.to_id FROM reach r
        JOIN edges e ON (e.from_kind, e.from_id) = (r.kind, r.id)
    WHERE e.to_id IS NOT NULL
), held AS (
    SELECT id, array_agg(DISTINCT root) AS holds FROM reach WHERE kind = 'C' GROUP BY id
), package_items AS (
    SELECT DISTINCT m.package_id, i.item_id FROM eqos.queue_item_inputs i
    LEFT JOIN eqos.occurrences o ON o.id = i.occurrence_id
    LEFT JOIN eqos.interpretations n ON n.id = i.interpretation_id
    LEFT JOIN eqos.acquisition_attempts a ON a.id = i.attempt_id
    JOIN eqos.package_members m
        ON m.capture_ref_id = coalesce(o.capture_ref_id, n.capture_ref_id, a.capture_ref_id)
), package_queue AS (
    SELECT p.package_id, bool_or(d.id IS NULL) AS open, max(d.recorded_at) AS last_disposed
    FROM package_items p LEFT JOIN eqos.queue_dispositions d ON d.item_id = p.item_id
    GROUP BY p.package_id
), verified AS (
    SELECT m.capture_ref_id, min(greatest(r.created_at, q.last_disposed)) AS verified_at
    FROM eqos.package_members m
    JOIN eqos.run_inputs i ON i.package_id = m.package_id
        AND i.input_kind = 'PACKAGE' AND i.disposition = 'SELECTED'
    JOIN eqos.runs r ON r.id = i.run_id AND r.status = 'COMPLETE'
    LEFT JOIN package_queue q ON q.package_id = m.package_id
    WHERE q.open IS NOT TRUE
    GROUP BY m.capture_ref_id
)
SELECT r.id AS capture_ref_id, r.source_id, r.surface, r.blob_sha256,
    coalesce(k.retention_class, 'UNCLASSIFIED') AS base_class,
    eqos.capture_covered(r.id) AS covered, eqos.is_vendor_source(r.source_id) AS vendor_bounded,
    r.registered_at, v.verified_at, coalesce(h.holds, '{}') AS holds,
    l.ended_at AS licence_ended_at, eqos.capture_state(r.id) AS state, a.url
FROM eqos.capture_refs r
LEFT JOIN eqos.retention_classes k ON k.capture_ref_id = r.id
LEFT JOIN held h ON h.id = r.id
LEFT JOIN verified v ON v.capture_ref_id = r.id
LEFT JOIN eqos.licence_ends l ON l.source_id = r.source_id
LEFT JOIN eqos.capture_addresses a ON a.capture_ref_id = r.id
WHERE eqos.capture_state(r.id) <> 'EXPIRED'
ORDER BY r.id
"""


def pinned_roots(config_root: Path) -> dict[HoldRoot, frozenset[str]]:
    """The SHA-256s of qualification fixture captures and of frozen manifest inputs."""
    fixtures = {
        value
        for path in sorted((config_root / MAPPINGS_DIR).rglob("*.yaml"))
        for key, value in _hashes(yaml.safe_load(path.read_text()))
        if key == FIXTURE_KEY
    }
    listed = yaml.safe_load((config_root / HOLDS_FILE).read_text())["manifests"]
    manifests = {
        value
        for name in listed
        for _, value in _hashes(yaml.safe_load((config_root.parent / name).read_text()))
    }
    return {
        HoldRoot.QUALIFICATION_FIXTURE: frozenset(fixtures),
        HoldRoot.MANIFEST_INPUT: frozenset(manifests),
    }


def _hashes(node: object, key: str = "") -> Iterator[tuple[str, str]]:
    """Every SHA-256 string in a YAML tree with the mapping key it sits under."""
    if isinstance(node, dict):
        for name, value in node.items():
            yield from _hashes(value, str(name))
    elif isinstance(node, list):
        for value in node:
            yield from _hashes(value, key)
    elif isinstance(node, str) and _SHA256.fullmatch(node):
        yield key, node


def capture_facts(
    conn: psycopg.Connection[Any], pinned: dict[HoldRoot, frozenset[str]]
) -> tuple[CaptureFacts, ...]:
    """The retention facts of every non-expired capture, in one statement's snapshot."""
    params = {
        "marker": LOCATION_MARKER.pattern,
        "fixtures": sorted(pinned.get(HoldRoot.QUALIFICATION_FIXTURE, ())),
        "manifests": sorted(pinned.get(HoldRoot.MANIFEST_INPUT, ())),
    }
    with conn.cursor(row_factory=dict_row) as cursor:
        rows = cursor.execute(_FACTS, params).fetchall()
    return tuple(CaptureFacts.model_validate(row) for row in rows)
