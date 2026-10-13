"""Closed vendor producer mechanics over marked synthetic source bodies and publications.

These are characterization tests for the new producer API, not a claimed pre-existing RED.
The permanent existing-API behavioral RED lives in test_compare_vendor_runs.py.
"""

from __future__ import annotations

import hashlib
import threading
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml
from pg_support import PgTestDatabase
from psycopg import sql
from vendor_inputs_support import (
    arguments,
    fixture,
    fixture_identity,
    schedule_fixture,
)

from fundamentals.compare.run_models import RunScope, VendorSurfaceRequest
from fundamentals.compare.vendor_inputs import (
    append_vendor_generation,
    compose_vendor_generation,
    prepare_vendor_generation,
)
from fundamentals.compare.vendor_request import (
    VendorGenerationError,
    logical_scope_sha256,
)
from fundamentals.contracts.canonical import Basis, StatementFamily
from fundamentals.contracts.measurement_key import PeriodInterval
from fundamentals.evidence.repository import EvidenceRepository
from fundamentals.evidence.vendor_common import VendorRequest, VendorRetainedBinding
from fundamentals.ingest.screener_financials_models import Section
from fundamentals.pg.identity_seed import (
    EvidenceInputKind,
    seed_issuer_identity,
)

SOURCE = "screener-subscriber"
SURFACE = "SCREENER_FINANCIALS"
SCHEMA = "screener-financials-html-v1"
QUARTER = PeriodInterval.duration(date(2025, 7, 1), date(2025, 9, 30))
YEAR = PeriodInterval.duration(date(2025, 4, 1), date(2026, 3, 31))
NOW = datetime(2026, 10, 13, 7, 0, tzinfo=UTC)
TABLES = ("capture_refs", "occurrences", "interpretations", "acquisition_attempts", "runs")


def test_legacy_declaration_json_and_full_scope_dedup_preserve_all_periods(tmp_path: Path) -> None:
    legacy = VendorSurfaceRequest(source_id=SOURCE, surface=SURFACE)
    assert legacy.model_dump(mode="json") == {"source_id": SOURCE, "surface": SURFACE}
    case = fixture(tmp_path)
    declaration = case[3]
    later = declaration.model_copy(update={"period": YEAR})
    scope = RunScope(
        entity_ids=(1,),
        period_ends=(date(2025, 9, 30),),
        bases=(Basis.CONSOLIDATED,),
        sources=("NSE_XBRL_INSTANCE",),
        vendor_sources=(declaration, later, declaration),
    )
    assert len(scope.vendor_sources) == 2
    assert {d.period for d in scope.vendor_sources} == {QUARTER, YEAR}


def test_logical_scope_excludes_body_binding_but_closes_semantic_period_and_extractor(
    tmp_path: Path,
) -> None:
    case = fixture(tmp_path)
    config, declaration, context = case[2:5]
    assert config.vendor_config is not None
    pin = config.vendor_config.extractor_pins[0]
    generation = compose_vendor_generation(**arguments(case))
    request = generation.request
    original = logical_scope_sha256(request, extractor_pin=pin, composer_context=context)
    changed = request.model_copy(
        update={
            "retained": VendorRetainedBinding(
                relative_path=Path("other.html"), expected_sha256="f" * 64
            )
        }
    )
    missing = request.model_copy(update={"retained": None})
    for candidate in (changed, missing):
        assert (
            logical_scope_sha256(candidate, extractor_pin=pin, composer_context=context) == original
        )
        assert candidate.identity_sha256() != request.identity_sha256()
    for candidate in (
        request.model_copy(update={"period": YEAR}),
        request.model_copy(update={"schema_identity": "another-schema"}),
        request.model_copy(update={"statement_family": StatementFamily.CASH_FLOW}),
    ):
        assert (
            logical_scope_sha256(candidate, extractor_pin=pin, composer_context=context) != original
        )
    assert (
        logical_scope_sha256(
            request,
            extractor_pin=pin.model_copy(update={"content_sha256": "e" * 64}),
            composer_context=context,
        )
        != original
    )
    assert declaration.expected_logical_scope_sha256 == original


def test_fixed_composer_preserves_printed_values_clocks_and_actual_intervals(
    tmp_path: Path,
) -> None:
    case = fixture(tmp_path)
    generation = compose_vendor_generation(**arguments(case))
    prepared = prepare_vendor_generation(generation, **arguments(case))
    cell = next(
        row
        for row in generation.occurrences
        if row.native_field == "Sales" and row.period == QUARTER
    )
    # Hand-read committed synthetic row: Sep 2025 Sales is exactly 1,200 crore.
    assert cell.raw_value_text == "1,200" and cell.raw_scale == 7
    assert cell.first_seen_at == NOW
    assert all(
        attempt.input_sha256 == generation.request.identity_sha256()
        for attempt in generation.attempts
    )
    assert all(
        attempt.extraction_context_sha256 == prepared.logical_scope_sha256
        for attempt in generation.attempts
    )
    assert prepared.generation == generation
    assert prepared.evidence_identity_sha256 != prepared.logical_scope_sha256


@pytest.mark.parametrize(
    "field",
    [
        "capture",
        "occurrence",
        "attempt",
        "publication",
        "extractor",
        "occurrence_id",
        "attempt_clock",
    ],
)
def test_forged_claim_refuses_before_generation_write(tmp_path: Path, field: str) -> None:
    case = fixture(tmp_path)
    generation = compose_vendor_generation(**arguments(case))
    assert generation.capture is not None
    if field == "capture":
        forged = generation.model_copy(
            update={"capture": generation.capture.model_copy(update={"record_sha256": "f" * 64})}
        )
    elif field == "occurrence":
        forged = generation.model_copy(
            update={
                "occurrences": (
                    generation.occurrences[0].model_copy(update={"raw_value_text": "999999"}),
                    *generation.occurrences[1:],
                )
            }
        )
    elif field == "attempt":
        forged = generation.model_copy(
            update={
                "attempts": (generation.attempts[0].model_copy(update={"reason": "forged reason"}),)
            }
        )
    elif field == "publication":
        forged = generation.model_copy(update={"published_config_sha256": "f" * 64})
    elif field == "extractor":
        forged = generation.model_copy(
            update={
                "extractor_pin": generation.extractor_pin.model_copy(
                    update={"content_sha256": "f" * 64}
                )
            }
        )
    elif field == "occurrence_id":
        forged = generation.model_copy(
            update={
                "occurrences": (
                    generation.occurrences[0].model_copy(update={"occurrence_id": 999999}),
                    *generation.occurrences[1:],
                )
            }
        )
    else:
        forged = generation.model_copy(
            update={"attempts": (generation.attempts[0].model_copy(update={"attempted_at": NOW}),)}
        )
    with pytest.raises(VendorGenerationError):
        append_vendor_generation(forged, **arguments(case))


def test_raw_reread_refuses_content_drift(tmp_path: Path) -> None:
    case = fixture(tmp_path)
    generation = compose_vendor_generation(**arguments(case))
    (case[1] / "synthetic.html").write_bytes(b"marked synthetic drift")
    with pytest.raises(ValueError, match="source-pinned hash"):
        append_vendor_generation(generation, **arguments(case))


def test_missing_binding_is_failed_not_not_published_and_has_same_logical_scope(
    tmp_path: Path,
) -> None:
    case = fixture(tmp_path)
    generation = compose_vendor_generation(**arguments(case))
    root, inputs, config, declaration, context, repository = case
    missing = declaration.model_copy(update={"retained": None, "capture_ref_id": None})
    missing_case = (root, inputs, config, missing, context, repository)
    failure = compose_vendor_generation(**arguments(missing_case))
    actual = prepare_vendor_generation(failure, **arguments(missing_case))
    original = prepare_vendor_generation(generation, **arguments(case))
    assert actual.logical_scope_sha256 == original.logical_scope_sha256
    assert actual.evidence_identity_sha256 != original.evidence_identity_sha256
    assert failure.capture is None and not failure.occurrences and not failure.interpretations
    assert failure.attempts[0].outcome.value == "FAILED"
    assert "RETAINED_INPUT_UNAVAILABLE" in (failure.attempts[0].reason or "")


def test_annual_body_is_not_stamped_with_quarter_and_undated_ttm_refuses(tmp_path: Path) -> None:
    annual = fixture(tmp_path, section=Section.PROFIT_LOSS, period=YEAR)
    generation = compose_vendor_generation(**arguments(annual))
    assert any(row.period == YEAR for row in generation.occurrences)
    assert not any(row.period == QUARTER for row in generation.occurrences)
    ttm = [
        row for row in generation.occurrences if row.native_context["native_period_kind"] == "ttm"
    ]
    assert ttm and all(row.period is None for row in ttm)
    bad = annual[3].model_copy(update={"period": QUARTER})
    request = generation.request.model_copy(update={"period": QUARTER})
    assert annual[2].vendor_config is not None
    pin = annual[2].vendor_config.extractor_pins[0]
    bad = bad.model_copy(
        update={
            "expected_logical_scope_sha256": logical_scope_sha256(
                request, extractor_pin=pin, composer_context=annual[4]
            )
        }
    )
    with pytest.raises(VendorGenerationError, match="source headers"):
        compose_vendor_generation(**arguments((*annual[:3], bad, *annual[4:])))


@pytest.mark.parametrize(
    "source,surface,schema",
    [
        ("upstox", "income-statement", "upstox-income-v1"),
        ("upstox", "balance-sheet", "upstox-balance-v1"),
        ("upstox", "cash-flow", "upstox-cash-v1"),
        ("upstox", "key-ratios", "upstox-ratios-v1"),
        ("tijori", "TIJORI_FINANCIALS", "invented-tijori-v1"),
        (SOURCE, SURFACE, "invented-screener-schema"),
    ],
)
def test_missing_rights_extractor_or_schema_refuses_without_attempt_write(
    tmp_path: Path, source: str, surface: str, schema: str
) -> None:
    case = fixture(tmp_path)
    declaration = case[3].model_copy(
        update={
            "source_id": source,
            "surface": surface,
            "schema_identity": schema,
            "retained": None,
            "capture_ref_id": None,
        }
    )
    with pytest.raises(VendorGenerationError, match="(EXCLUDED|undeclared|bundle|schema)"):
        compose_vendor_generation(**arguments((*case[:3], declaration, *case[4:])))


@pytest.mark.pg
def test_guarded_postgres_generation_is_by_id_closed_and_idempotent(
    pg_db: PgTestDatabase, tmp_path: Path
) -> None:
    identity, _ = fixture_identity()
    with pg_db.migrator_connection() as connection:
        entity_id = seed_issuer_identity(connection, identity).entity_ids["FIXTURECO"]
    with pg_db.runtime_pool() as pool:
        repository = EvidenceRepository(pool)
        case = fixture(tmp_path, repository=repository, entity_id=entity_id)
        generation = compose_vendor_generation(**arguments(case))
        first = append_vendor_generation(generation, **arguments(case))
        second = append_vendor_generation(generation, **arguments(case))
        stored_claim = append_vendor_generation(first.generation, **arguments(case))
        assert first == second == stored_claim
        assert first.occurrences == repository.get_occurrences(list(first.occurrence_ids))
        assert first.interpretations == repository.get_interpretations(
            list(first.interpretation_ids)
        )
        assert first.attempts == repository.get_attempts(list(first.attempt_ids))
        assert first.settings_record is not None and first.identity_evidence
        with pool.connection() as connection:
            assert (
                connection.execute("SELECT count(*) FROM eqos.filing_packages").fetchone()[0] == 0
            )
        assert all(
            row.extraction_context_sha256 == first.logical_scope_sha256 for row in first.attempts
        )
        assert all(
            row.attempted_at is not None and row.attempted_at > generation.capture.registered_at
            for row in first.attempts
        )
        assert all(
            row.recorded_at > generation.capture.registered_at for row in first.interpretations
        )
        with pool.connection() as connection:
            before = tuple(
                connection.execute(
                    sql.SQL("SELECT count(*) FROM eqos.{}").format(sql.Identifier(table))
                ).fetchone()[0]
                for table in TABLES
            )
        assert generation.capture is not None
        assert first.interpretations
        forged_claims = (
            generation.model_copy(
                update={
                    "capture": generation.capture.model_copy(update={"record_sha256": "f" * 64})
                }
            ),
            generation.model_copy(
                update={
                    "occurrences": (
                        generation.occurrences[0].model_copy(update={"raw_value_text": "999999"}),
                        *generation.occurrences[1:],
                    )
                }
            ),
            generation.model_copy(
                update={
                    "attempts": (
                        generation.attempts[0].model_copy(update={"input_sha256": "f" * 64}),
                    )
                }
            ),
            first.generation.model_copy(
                update={
                    "interpretations": (
                        first.interpretations[0].model_copy(update={"value": Decimal("999999")}),
                        *first.interpretations[1:],
                    )
                }
            ),
            first.generation.model_copy(update={"interpretations": first.interpretations[:-1]}),
        )
        for forged in forged_claims:
            with pytest.raises(VendorGenerationError):
                append_vendor_generation(forged, **arguments(case))
        with pool.connection() as connection:
            after = tuple(
                connection.execute(
                    sql.SQL("SELECT count(*) FROM eqos.{}").format(sql.Identifier(table))
                ).fetchone()[0]
                for table in TABLES
            )
        assert before == after
        missing = case[3].model_copy(update={"retained": None, "capture_ref_id": None})
        missing_case = (*case[:3], missing, *case[4:])
        failure = compose_vendor_generation(**arguments(missing_case))
        failed_scope = append_vendor_generation(failure, **arguments(missing_case))
        assert failed_scope.capture is None
        assert not failed_scope.occurrence_ids and not failed_scope.interpretation_ids
        assert len(failed_scope.attempt_ids) == 1
        assert failed_scope.attempts == repository.get_attempts(list(failed_scope.attempt_ids))
        assert failed_scope.logical_scope_sha256 == first.logical_scope_sha256
        assert failed_scope.evidence_identity_sha256 != first.evidence_identity_sha256
        assert failed_scope.attempts[0].outcome.value == "FAILED"
        assert failed_scope.attempts[0].extraction_context_sha256 == first.logical_scope_sha256


def test_schedule_recomposes_separate_capture_with_exact_supporting_page(tmp_path: Path) -> None:
    case = schedule_fixture(tmp_path)
    generation = compose_vendor_generation(**arguments(case))
    prepared = prepare_vendor_generation(generation, **arguments(case))
    cell = next(
        row
        for row in generation.occurrences
        if row.native_field == "Exceptional items" and row.period == QUARTER
    )
    # Independent committed synthetic JSON explicitly prints Exceptional items / Sep 2025 = 12.
    assert cell.raw_value_text == "12" and cell.declared_precision == 0
    assert cell.capture.capture_ref_id == 2
    assert cell.disclosure["supporting_page_capture_id"] == "marked-synthetic-page"
    assert len(prepared.supporting_captures) == 1
    assert prepared.supporting_captures[0].capture_ref_id == 1
    assert generation.attempts[0].extraction_context_sha256 == prepared.logical_scope_sha256


@pytest.mark.parametrize("failure", ["page_bytes", "page_capture", "page_scope", "parent"])
def test_schedule_supporting_bytes_scope_and_capture_drift_refuse_before_write(
    tmp_path: Path, failure: str
) -> None:
    case = schedule_fixture(tmp_path)
    generation = compose_vendor_generation(**arguments(case))
    if failure == "page_bytes":
        (case[1] / "synthetic.html").write_bytes(b"marked changed supporting page")
    elif failure == "page_capture":
        case[5].capture = case[5].capture.model_copy(update={"surface": "ANOTHER_SURFACE"})
    else:
        context = case[4]
        if failure == "page_scope":
            context = context.model_copy(
                update={
                    "supporting_page_request": context.supporting_page_request.model_copy(
                        update={"period": YEAR}
                    )
                }
            )
        else:
            context = context.model_copy(update={"parent": "Missing source parent"})
        declaration = case[3].model_copy(update={"composer_context": context})
        declaration = declaration.model_copy(
            update={
                "expected_logical_scope_sha256": logical_scope_sha256(
                    generation.request,
                    extractor_pin=generation.extractor_pin,
                    composer_context=context,
                )
            }
        )
        case = (*case[:3], declaration, context, case[5])
    with pytest.raises(ValueError):
        append_vendor_generation(generation, **arguments(case))


def test_two_physical_captures_share_availability_but_never_evidence_identity(
    tmp_path: Path,
) -> None:
    case = fixture(tmp_path)
    generation = compose_vendor_generation(**arguments(case))
    first = prepare_vendor_generation(generation, **arguments(case))
    body = (case[1] / "synthetic.html").read_bytes() + b"\n<!-- marked second physical capture -->"
    (case[1] / "second.html").write_bytes(body)
    request = generation.request.model_copy(
        update={
            "retained": VendorRetainedBinding(
                relative_path=Path("second.html"), expected_sha256=hashlib.sha256(body).hexdigest()
            )
        }
    )
    assert generation.capture is not None
    second_capture = generation.capture.model_copy(
        update={
            "capture_ref_id": 2,
            "capture_id": "marked-second-physical-capture",
            "blob_sha256": hashlib.sha256(body).hexdigest(),
            "record_sha256": "c" * 64,
            "request_key": request.identity_sha256(),
            "registered_at": NOW + timedelta(seconds=1),
            "first_seen_at": NOW + timedelta(seconds=1),
        }
    )
    case[5].captures[2] = second_capture
    declaration = case[3].model_copy(update={"retained": request.retained, "capture_ref_id": 2})
    second_case = (*case[:3], declaration, *case[4:])
    second_generation = compose_vendor_generation(**arguments(second_case))
    second = prepare_vendor_generation(second_generation, **arguments(second_case))
    assert first.logical_scope_sha256 == second.logical_scope_sha256
    assert first.evidence_identity_sha256 != second.evidence_identity_sha256
    assert generation.request.identity_sha256() != second_generation.request.identity_sha256()
    assert generation.capture != second_generation.capture
    assert second_generation.occurrences[0].first_seen_at == second_capture.first_seen_at
    assert all(row.capture == second_capture for row in second_generation.occurrences)


@pytest.mark.parametrize("field", ["kind", "label", "content_sha256"])
def test_vendor_fiscal_source_refuses_self_consistent_wrong_evidence_before_write(
    tmp_path: Path, field: str
) -> None:
    case = fixture(tmp_path)
    generation = compose_vendor_generation(**arguments(case))
    repository = case[5]
    value = (
        EvidenceInputKind.ISSUER_CONFIG
        if field == "kind"
        else "../../wrong-source"
        if field == "label"
        else "0" * 64
    )
    repository.evidence = repository.evidence.model_copy(update={field: value})
    with pytest.raises(ValueError, match="(source|artifact|evidence|identity)"):
        prepare_vendor_generation(generation, **arguments(case))


@pytest.mark.pg
def test_vendor_preexisting_wrong_reason_attempt_refuses_before_generation_write(
    pg_db: PgTestDatabase, tmp_path: Path
) -> None:
    with pg_db.migrator_connection() as connection:
        entity_id = seed_issuer_identity(connection, fixture_identity()[0]).entity_ids["FIXTURECO"]
    with pg_db.runtime_pool() as pool:
        repository = EvidenceRepository(pool)
        case = fixture(tmp_path, repository=repository, entity_id=entity_id)
        generation = compose_vendor_generation(**arguments(case))
        repository.put_attempts(
            (generation.attempts[0].model_copy(update={"reason": "wrong existing reason"}),)
        )
        with pool.connection() as connection:
            before = tuple(
                connection.execute(
                    sql.SQL("SELECT count(*) FROM eqos.{}").format(sql.Identifier(table))
                ).fetchone()[0]
                for table in TABLES
            )
        with pytest.raises(ValueError, match="(attempt|payload|recompos)"):
            append_vendor_generation(generation, **arguments(case))
        with pool.connection() as connection:
            after = tuple(
                connection.execute(
                    sql.SQL("SELECT count(*) FROM eqos.{}").format(sql.Identifier(table))
                ).fetchone()[0]
                for table in TABLES
            )
        assert before == after


@pytest.mark.pg
def test_vendor_one_registered_page_supports_sequential_quarter_annual_balance_and_cash_flow(
    pg_db: PgTestDatabase, tmp_path: Path
) -> None:
    with pg_db.migrator_connection() as connection:
        entity_id = seed_issuer_identity(connection, fixture_identity()[0]).entity_ids["FIXTURECO"]
    with pg_db.runtime_pool() as pool:
        repository = EvidenceRepository(pool)
        case = fixture(tmp_path, repository=repository, entity_id=entity_id)
        root, inputs, config, declaration, context, _ = case
        drafts = []
        scopes = []
        for section, period, family in (
            (Section.QUARTERS, QUARTER, StatementFamily.PL),
            (Section.PROFIT_LOSS, YEAR, StatementFamily.PL),
            (
                Section.BALANCE_SHEET,
                PeriodInterval.at(date(2026, 3, 31)),
                StatementFamily.BALANCE_SHEET,
            ),
            (Section.CASH_FLOW, YEAR, StatementFamily.CASH_FLOW),
        ):
            semantic = context.model_copy(update={"section": section})
            full = declaration.model_copy(
                update={"period": period, "statement_family": family, "composer_context": semantic}
            )
            base_request = VendorRequest.model_validate(
                {field: getattr(full, field) for field in VendorRequest.model_fields}
            )
            assert config.vendor_config is not None
            pin = next(row for row in config.vendor_config.extractor_pins if row.surface == SURFACE)
            full = full.model_copy(
                update={
                    "expected_logical_scope_sha256": logical_scope_sha256(
                        base_request, extractor_pin=pin, composer_context=semantic
                    )
                }
            )
            group_case = (root, inputs, config, full, semantic, repository)
            draft = compose_vendor_generation(**arguments(group_case))
            try:
                scope = append_vendor_generation(draft, **arguments(group_case))
            except ValueError as error:
                pytest.fail(
                    f"legitimate shared capture section {section.value} was rejected: {error}"
                )
            drafts.append((draft, group_case))
            scopes.append(scope)
        assert {scope.capture_ref_id for scope in scopes} == {declaration.capture_ref_id}
        assert len({scope.logical_scope_sha256 for scope in scopes}) == 4
        for first, (draft, group_case) in zip(scopes, drafts, strict=True):
            assert append_vendor_generation(draft, **arguments(group_case)) == first
            assert append_vendor_generation(first.generation, **arguments(group_case)) == first


@pytest.mark.parametrize(
    "failure", ["bytes", "symlink", "citations", "entity", "month", "separate_evidence"]
)
def test_vendor_actual_identity_artifact_or_secondary_evidence_refuses_before_write(
    tmp_path: Path, failure: str
) -> None:
    case = fixture(tmp_path)
    generation = compose_vendor_generation(**arguments(case))
    path = case[0] / "identity/fixtureco.yaml"
    if failure == "symlink":
        alternate = tmp_path / "marked-synthetic-identity-outside-config.yaml"
        alternate.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(alternate)
    elif failure == "separate_evidence":
        case[5].setting = case[5].setting.model_copy(update={"evidence_input_id": 2})
        case[5].extra_evidence = (
            case[5].evidence.model_copy(update={"id": 2, "kind": EvidenceInputKind.ISSUER_CONFIG}),
        )
    else:
        document = yaml.safe_load(path.read_bytes())
        if failure == "bytes":
            document["display_name"] = "Marked source-content drift"
        elif failure == "citations":
            document["citations"] = document["citations"][:-1]
        elif failure == "entity":
            document["entity_key"] = "ANOTHER-ENTITY"
        else:
            document["fiscal_year_end_month"] = 6
        path.write_text(yaml.safe_dump(document))
    with pytest.raises(ValueError):
        prepare_vendor_generation(generation, **arguments(case))


@pytest.mark.pg
def test_vendor_concurrent_shared_capture_semantic_groups_keep_exact_idempotent_closure(
    pg_db: PgTestDatabase, tmp_path: Path
) -> None:
    with pg_db.migrator_connection() as connection:
        entity_id = seed_issuer_identity(connection, fixture_identity()[0]).entity_ids["FIXTURECO"]
    with pg_db.runtime_pool() as pool:
        repository = EvidenceRepository(pool)
        case = fixture(tmp_path, repository=repository, entity_id=entity_id)
        requests = []
        assert case[2].vendor_config is not None
        pin = next(row for row in case[2].vendor_config.extractor_pins if row.surface == SURFACE)
        for section, period, family in (
            (Section.QUARTERS, QUARTER, StatementFamily.PL),
            (Section.PROFIT_LOSS, YEAR, StatementFamily.PL),
            (
                Section.BALANCE_SHEET,
                PeriodInterval.at(date(2026, 3, 31)),
                StatementFamily.BALANCE_SHEET,
            ),
            (Section.CASH_FLOW, YEAR, StatementFamily.CASH_FLOW),
        ):
            context = case[4].model_copy(update={"section": section})
            declaration = case[3].model_copy(
                update={"period": period, "statement_family": family, "composer_context": context}
            )
            request = VendorRequest.model_validate(
                {field: getattr(declaration, field) for field in VendorRequest.model_fields}
            )
            declaration = declaration.model_copy(
                update={
                    "expected_logical_scope_sha256": logical_scope_sha256(
                        request, extractor_pin=pin, composer_context=context
                    )
                }
            )
            group_case = (*case[:3], declaration, context, repository)
            requests.append((compose_vendor_generation(**arguments(group_case)), group_case))
        gate = threading.Barrier(len(requests))
        scopes: dict[int, Any] = {}
        errors: list[BaseException] = []

        def run(index: int) -> None:
            try:
                draft, group_case = requests[index]
                gate.wait(timeout=30)
                scopes[index] = append_vendor_generation(draft, **arguments(group_case))
            except BaseException as error:  # noqa: BLE001 - surfaced through the assertion
                errors.append(error)

        threads = [threading.Thread(target=run, args=(index,)) for index in range(len(requests))]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=45)
        assert not any(thread.is_alive() for thread in threads)
        assert errors == []
        assert len(scopes) == 4
        for index, (draft, group_case) in enumerate(requests):
            assert append_vendor_generation(draft, **arguments(group_case)) == scopes[index]
            assert (
                append_vendor_generation(scopes[index].generation, **arguments(group_case))
                == scopes[index]
            )
