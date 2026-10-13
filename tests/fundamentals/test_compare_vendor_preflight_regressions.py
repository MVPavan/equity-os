"""Current public preflight regressions for the three independent R1 findings.

Actual independently parsed synthetic source bytes and guarded PostgreSQL rows
exercise the existing callable APIs. Root owns RED/green execution and sealing.
"""

from datetime import date

import pytest
from pg_support import PgTestDatabase
from vendor_runs_support import FIRST_PARTY_BODY, VendorRunCase, build_case

from fundamentals.compare.engine_attempts import RunResolutionError
from fundamentals.compare.vendor_handoffs import validate_first_party_handoff
from fundamentals.compare.vendor_resolution import prepare_vendor_run
from fundamentals.evidence.interpret import SEGMENT_AXIS
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.evidence.repository_rows import SegmentMemberWrite
from fundamentals.evidence.xbrl_adapter import SEGMENT_DESCRIPTION_CONCEPT, member_slug
from fundamentals.store.snapshot_store import DirectoryAnchor

pytestmark = pytest.mark.pg


def _prepare(case: VendorRunCase, request=None):
    return prepare_vendor_run(
        request or case.request(),
        first_party_generation=case.first_party,
        vendor_generations=(case.generation,),
        config=case.producer_case[2],
        config_root=case.config_root,
        repository=case.repository,
        input_anchor=DirectoryAnchor(case.producer_case[1]),
    )


def test_eligible_package_without_cutoff_currency_refuses_before_vendor_and_pin_writes(
    pg_db, tmp_path
):
    with pg_db.runtime_pool() as pool:
        case = build_case(pg_db, pool, tmp_path, persist_vendor=False)
        request = case.request()
        boundary = max(
            clock
            for member in case.first_party.members
            for clock in (member.capture_registered_at, member.capture_first_seen_at)
        )
        request = request.model_copy(update={"cutoff": boundary})
        scope = validate_first_party_handoff(
            case.first_party,
            request=request,
            config=case.producer_case[2],
            config_root=case.config_root,
            repository=case.repository,
        )
        assert scope.package_eligible
        assert not scope.eligible_interpretation_ids

        def counts():
            result = case.counts()
            with pool.connection() as connection:
                for table in ("version_pins", "definition_sets", "definition_records"):
                    result[table] = int(
                        connection.execute("SELECT count(*) FROM eqos." + table).fetchone()[0]
                    )
            return result

        before = counts()
        # Accept the current downstream RuntimeError solely so the mutation
        # assertion is reached. Final behavior must be the typed prewrite refusal.
        with pytest.raises((ValueError, RunResolutionError)) as raised:
            case.execute(request)
        assert counts() == before
        assert isinstance(raised.value, ValueError)


def test_future_basis_record_does_not_change_historical_source_bound_preflight(pg_db, tmp_path):
    with pg_db.runtime_pool() as pool:
        case = build_case(pg_db, pool, tmp_path)
        request = case.request()
        before = _prepare(case, request)
        with pg_db.migrator_connection() as connection:
            connection.execute(
                "INSERT INTO eqos.entity_basis_status (entity_id, basis_status, evidence_input_id) "
                "VALUES (%s, 'STANDALONE_ONLY', %s)",
                (
                    case.first_party.entity_id,
                    case.first_party.fiscal_year_end_setting_evidence_input_id,
                ),
            )
        after = _prepare(case, request)
        assert after.base.basis_statuses == before.base.basis_statuses


def _segment_body(variant: str) -> bytes:
    prefix = "ext" if variant == "namespace" else "in-bse-fin"
    axis_prefix = "ext" if variant == "dimension" else "in-bse-fin"
    body = FIRST_PARTY_BODY.replace(
        b"xmlns:in-bse-fin=",
        b'xmlns:ext="urn:synthetic-foreign-semantics" '
        b'xmlns:xbrldi="http://xbrl.org/2006/xbrldi" xmlns:in-bse-fin=',
    )
    addition = f'''
 <xbrli:context id="SegmentOne"><xbrli:entity>
 <xbrli:identifier scheme="http://www.nseindia.com/NSESymbol">FIXTURECO</xbrli:identifier>
 </xbrli:entity><xbrli:period><xbrli:startDate>2025-07-01</xbrli:startDate>
 <xbrli:endDate>2025-09-30</xbrli:endDate></xbrli:period><xbrli:scenario>
 <xbrldi:explicitMember dimension="{axis_prefix}:ReportableSegmentsAxis">
in-bse-fin:SegmentOneMember
</xbrldi:explicitMember></xbrli:scenario></xbrli:context>
 <{prefix}:DescriptionOfReportableSegment contextRef="SegmentOne">
Synthetic segment
</{prefix}:DescriptionOfReportableSegment>
'''.encode()
    return body.replace(b"</xbrli:xbrl>", addition + b"</xbrli:xbrl>")


@pytest.mark.parametrize("variant", ("namespace", "dimension", "valid_from", "valid_to"))
def test_supplemental_segment_metadata_requires_native_dimension_and_validity_proof(
    pg_db: PgTestDatabase, tmp_path, monkeypatch, variant
):
    body = _segment_body(variant)

    def seed_unproved_end(repository, members):
        # Inject an actual append-only metadata row after its source occurrences
        # exist. The standard reuse selector requires a nullable end, so this
        # deliberately forged end and its associations use actual INSERTs only.
        # No existing row is changed and no clock is supplied.
        identifiers = []
        with pg_db.migrator_connection() as connection:
            for member in members:
                (member_id,) = connection.execute(
                    "INSERT INTO eqos.segment_members "
                    "(entity_id, axis, member, display_name, valid_from, valid_to) "
                    "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                    (
                        member.entity_id,
                        member.axis,
                        member.member,
                        member.display_name,
                        member.valid_from,
                        date(2025, 12, 31),
                    ),
                ).fetchone()
                identifiers.append(member_id)
                for occurrence_id in member.evidence_occurrence_ids:
                    connection.execute(
                        "INSERT INTO eqos.segment_member_evidence "
                        "(segment_member_id, occurrence_id) VALUES (%s, %s)",
                        (member_id, occurrence_id),
                    )
        return tuple(identifiers)

    with pg_db.runtime_pool() as pool:
        with monkeypatch.context() as scoped:
            if variant == "valid_to":
                scoped.setattr(EvidenceRepository, "put_segment_members", seed_unproved_end)
            case = build_case(pg_db, pool, tmp_path, first_party_body=body)
        (description,) = [
            row
            for row in case.repository.get_occurrences(case.first_party.members[0].occurrence_ids)
            if row.native_context.get("local_name") == SEGMENT_DESCRIPTION_CONCEPT
        ]
        if variant in ("namespace", "valid_from"):
            assert description.occurrence_id is not None
            case.repository.put_segment_members(
                (
                    SegmentMemberWrite(
                        entity_id=case.first_party.entity_id,
                        axis=SEGMENT_AXIS,
                        member=member_slug("Synthetic segment"),
                        display_name="Synthetic segment",
                        valid_from=date(2024, 1, 1)
                        if variant == "valid_from"
                        else date(2025, 7, 1),
                        evidence_occurrence_ids=(description.occurrence_id,),
                    ),
                )
            )
        before = case.counts()
        with pytest.raises(ValueError, match="(?i)segment"):
            _prepare(case)
        assert case.counts() == before


def test_actual_native_segment_metadata_has_closed_source_and_dimension_witness(pg_db, tmp_path):
    with pg_db.runtime_pool() as pool:
        case = build_case(pg_db, pool, tmp_path, first_party_body=_segment_body("positive"))
        prepared = _prepare(case)
        (segment,) = prepared.base.segment_members
        assert segment.member == member_slug("Synthetic segment")
        assert segment.valid_from == date(2025, 7, 1)
        assert segment.valid_to is None
        assert set(segment.evidence_occurrence_ids) <= {
            row.occurrence_id for row in prepared.base.occurrences
        }
