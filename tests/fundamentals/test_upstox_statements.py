"""Lane B statement parsing: the traps the 2026-09-04 live verification found.

Every assertion here traces to something observed in the 29 live responses, not
to the vendor's documentation. Four of them describe ways a strict parser reads
a well-formed HTTP 200 as data it is not.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from tests.fundamentals.upstox_fixtures import (
    ANNUAL_PERIODS,
    QUARTERLY_PERIODS,
    balance_sheet_body,
    cash_flow_body,
    income_statement_body,
    key_ratios_body,
    statement_fetch,
)

from fundamentals.ingest.upstox_source import AcquisitionOutcome, UpstoxSurface
from fundamentals.ingest.upstox_statements import (
    FULL_STATEMENT_IS_ALWAYS_ANNUAL,
    INCOME_SUMMARY_IDENTITIES,
    StatementBasis,
    StatementPeriodicity,
    read_balance_sheet,
    read_cash_flow,
    read_income_statement,
    read_key_ratios,
)

INCOME = UpstoxSurface.INCOME_STATEMENT
BALANCE = UpstoxSurface.BALANCE_SHEET
CASH = UpstoxSurface.CASH_FLOW
RATIOS = UpstoxSurface.KEY_RATIOS


def _income(**kwargs: object) -> object:
    return read_income_statement(
        statement_fetch(income_statement_body(**kwargs), surface=INCOME),  # type: ignore[arg-type]
        requested_basis=StatementBasis.STANDALONE,
        requested_periodicity=StatementPeriodicity.YEARLY,
    )


class TestIncomeStatement:
    def test_summary_and_full_statement_are_both_read(self) -> None:
        doc = _income()
        assert doc.outcome is AcquisitionOutcome.OK  # type: ignore[attr-defined]
        assert [s.category for s in doc.summary] == [  # type: ignore[attr-defined]
            "revenue",
            "operating_profit",
            "net_profit",
        ]
        assert len(doc.full_statement) == 9  # type: ignore[attr-defined]

    def test_values_are_decimals_never_floats(self) -> None:
        """A float round-trip would break the half-ULP tolerance Lane B derives."""
        point = _income().summary[0].history[0]  # type: ignore[attr-defined]
        assert isinstance(point.value, Decimal)
        assert point.value == Decimal("200.0")

    def test_change_is_absent_on_the_oldest_period(self) -> None:
        """Live: `change` was missing on the oldest point of all 18 series seen."""
        history = _income().summary[0].history  # type: ignore[attr-defined]
        assert history[0].change == "+10.0%"
        assert history[-1].change is None

    def test_full_statement_periodicity_is_annual_even_when_quarterly_was_asked(self) -> None:
        """The response says quarterly; `full_statement` stays annual. Verified live."""
        doc = read_income_statement(
            statement_fetch(
                income_statement_body(time_period="quarterly", summary_periods=QUARTERLY_PERIODS),
                surface=INCOME,
            ),
            requested_basis=StatementBasis.STANDALONE,
            requested_periodicity=StatementPeriodicity.QUARTERLY,
        )
        assert doc.summary_periodicity is StatementPeriodicity.QUARTERLY
        assert doc.full_statement_periodicity is StatementPeriodicity.YEARLY
        assert [p.period for p in doc.summary[0].history] == QUARTERLY_PERIODS
        assert [p.period for p in doc.full_statement[0].history] == ANNUAL_PERIODS
        assert FULL_STATEMENT_IS_ALWAYS_ANNUAL in doc.anomalies

    def test_a_quarterly_request_runs_no_identity_check(self) -> None:
        """The blocks carry different periodicities, so the period label is not a key.

        Under `time_period=quarterly` the summary's "Mar 2026" is the quarter
        and `full_statement`'s "Mar 2026" is the financial year. Comparing them
        reported three confident false disagreements per company on the live
        TITAN response.
        """
        doc = read_income_statement(
            statement_fetch(
                income_statement_body(
                    time_period="quarterly",
                    summary_periods=["Mar 2026", "Dec 2025"],
                    revenue=(500.0, 400.0),
                ),
                surface=INCOME,
            ),
            requested_basis=StatementBasis.STANDALONE,
            requested_periodicity=StatementPeriodicity.QUARTERLY,
        )
        assert doc.anomalies == (FULL_STATEMENT_IS_ALWAYS_ANNUAL,)

    def test_full_statement_periodicity_is_annual_on_an_annual_request_too(self) -> None:
        """It is a property of the block, not of the request — and no anomaly then."""
        doc = _income()
        assert doc.full_statement_periodicity is StatementPeriodicity.YEARLY  # type: ignore[attr-defined]
        assert FULL_STATEMENT_IS_ALWAYS_ANNUAL not in doc.anomalies  # type: ignore[attr-defined]

    def test_the_summary_disagreeing_with_the_full_statement_is_recorded(self) -> None:
        """NETWEB Mar-2025: operating_profit 153.0 vs Profit Before Tax 153.97.

        Both blocks arrive in one HTTP response, so "Upstox says X" is not well
        defined for that issuer and period. Recorded, never silently preferred.
        """
        body = income_statement_body(net_profit=(30.0, 22.0))
        # Restate one full_statement particular so the payload contradicts itself.
        for row in body["data"]["full_statement"]:
            if row["particular"] == "Profit After Tax":
                row["history"][0]["value"] = 31.5
        doc = read_income_statement(
            statement_fetch(body, surface=INCOME),
            requested_basis=StatementBasis.STANDALONE,
            requested_periodicity=StatementPeriodicity.YEARLY,
        )
        assert any("net_profit" in a and "Profit After Tax" in a for a in doc.anomalies)
        assert doc.outcome is AcquisitionOutcome.OK

    def test_agreement_within_half_a_ulp_is_not_an_anomaly(self) -> None:
        """NETWEB Mar-2024: 735.97 vs 735.96 is one ULP apart, not a defect."""
        body = income_statement_body()
        for row in body["data"]["full_statement"]:
            if row["particular"] == "Total Revenue":
                row["history"][0]["value"] = 200.01
        doc = read_income_statement(
            statement_fetch(body, surface=INCOME),
            requested_basis=StatementBasis.STANDALONE,
            requested_periodicity=StatementPeriodicity.YEARLY,
        )
        assert doc.anomalies == ()

    def test_the_identity_map_names_what_the_vendor_label_actually_means(self) -> None:
        assert dict(INCOME_SUMMARY_IDENTITIES)["operating_profit"] == "Profit Before Tax"

    def test_an_empty_company_parses_as_ok_empty_not_as_a_failure(self) -> None:
        """NETWEB publishes no consolidated statements. That is a real answer."""
        body = income_statement_body(basis="consolidated")
        for row in body["data"]["income_statement"]:
            row["history"] = []
        body["data"]["full_statement"] = []
        doc = read_income_statement(
            statement_fetch(body, surface=INCOME),
            requested_basis=StatementBasis.CONSOLIDATED,
            requested_periodicity=StatementPeriodicity.YEARLY,
        )
        assert doc.outcome is AcquisitionOutcome.OK_EMPTY
        assert doc.summary != ()

    def test_a_null_full_statement_is_read_as_empty_and_recorded(self) -> None:
        """Only the invalid-ISIN probe produced `null`; it must not crash a parse."""
        body = income_statement_body()
        body["data"]["full_statement"] = None
        doc = read_income_statement(
            statement_fetch(body, surface=INCOME),
            requested_basis=StatementBasis.STANDALONE,
            requested_periodicity=StatementPeriodicity.YEARLY,
        )
        assert doc.full_statement == ()
        assert any("full_statement" in a and "null" in a for a in doc.anomalies)

    def test_a_basis_the_response_does_not_echo_back_is_drift(self) -> None:
        doc = read_income_statement(
            statement_fetch(income_statement_body(basis="consolidated"), surface=INCOME),
            requested_basis=StatementBasis.STANDALONE,
            requested_periodicity=StatementPeriodicity.YEARLY,
        )
        assert doc.outcome is AcquisitionOutcome.SCHEMA_DRIFT

    def test_a_non_success_status_is_drift(self) -> None:
        body = income_statement_body()
        body["status"] = "error"
        doc = read_income_statement(
            statement_fetch(body, surface=INCOME),
            requested_basis=StatementBasis.STANDALONE,
            requested_periodicity=StatementPeriodicity.YEARLY,
        )
        assert doc.outcome is AcquisitionOutcome.SCHEMA_DRIFT

    def test_units_other_than_crore_are_drift(self) -> None:
        """Every one of the 22 live envelopes said crore. A change silently rescales."""
        body = income_statement_body()
        body["data"]["units_in"] = "million"
        doc = read_income_statement(
            statement_fetch(body, surface=INCOME),
            requested_basis=StatementBasis.STANDALONE,
            requested_periodicity=StatementPeriodicity.YEARLY,
        )
        assert doc.outcome is AcquisitionOutcome.SCHEMA_DRIFT

    def test_unparseable_json_yields_drift_carrying_the_captures_hash(self) -> None:
        fetch = statement_fetch({"status": "success"}, surface=INCOME)
        broken = fetch.model_copy(update={"raw_body": b"{not json"})
        doc = read_income_statement(
            broken,
            requested_basis=StatementBasis.STANDALONE,
            requested_periodicity=StatementPeriodicity.YEARLY,
        )
        assert doc.outcome is AcquisitionOutcome.SCHEMA_DRIFT
        assert doc.content_sha256 == fetch.capture.content_sha256


class TestBalanceSheet:
    def test_the_summary_uses_singular_total_asset_keys(self) -> None:
        doc = read_balance_sheet(
            statement_fetch(balance_sheet_body(), surface=BALANCE),
            requested_basis=StatementBasis.STANDALONE,
        )
        assert doc.outcome is AcquisitionOutcome.OK
        assert doc.history[0].total_asset == Decimal("600.0")
        assert doc.history[0].total_liability == Decimal("440.0")
        assert doc.history[0].period == "Mar 2026"

    def test_it_carries_no_total_liabilities_particular(self) -> None:
        """The 8 live particulars have no `Total Liabilities`. Lane B must not invent one."""
        doc = read_balance_sheet(
            statement_fetch(balance_sheet_body(), surface=BALANCE),
            requested_basis=StatementBasis.STANDALONE,
        )
        assert "Total Liabilities" not in {row.particular for row in doc.full_statement}


class TestCashFlow:
    def test_the_three_categories_are_read_with_signed_values(self) -> None:
        doc = read_cash_flow(
            statement_fetch(cash_flow_body(), surface=CASH),
            requested_basis=StatementBasis.STANDALONE,
        )
        assert [s.category for s in doc.summary] == ["operating", "investing", "financing"]
        assert doc.summary[1].history[0].value == Decimal("-30.0")

    def test_cash_flow_history_carries_the_same_optional_change(self) -> None:
        doc = read_cash_flow(
            statement_fetch(cash_flow_body(), surface=CASH),
            requested_basis=StatementBasis.STANDALONE,
        )
        assert doc.summary[0].history[-1].change is None


class TestKeyRatios:
    def test_the_row_set_is_not_fixed(self) -> None:
        """One live issuer returned six rows; two returned seven. Both are valid."""
        seven = read_key_ratios(
            statement_fetch(key_ratios_body(), surface=RATIOS),
            requested_basis=StatementBasis.STANDALONE,
        )
        six = read_key_ratios(
            statement_fetch(key_ratios_body(include_quick_ratio=False), surface=RATIOS),
            requested_basis=StatementBasis.STANDALONE,
        )
        assert len(seven.ratios) == 7
        assert len(six.ratios) == 6
        assert six.outcome is AcquisitionOutcome.OK
        assert "Quick Ratio" not in {r.name for r in six.ratios}

    def test_string_values_are_kept_verbatim_and_parsed_alongside(self) -> None:
        doc = read_key_ratios(
            statement_fetch(key_ratios_body(), surface=RATIOS),
            requested_basis=StatementBasis.STANDALONE,
        )
        roe = next(r for r in doc.ratios if r.name == "ROE")
        assert roe.company_value == "32.31%"
        assert roe.company_number == Decimal("32.31")
        assert roe.is_percentage is True

    def test_a_negative_sector_value_parses(self) -> None:
        doc = read_key_ratios(
            statement_fetch(key_ratios_body(), surface=RATIOS),
            requested_basis=StatementBasis.STANDALONE,
        )
        ev = next(r for r in doc.ratios if r.name == "EV/EBITDA")
        assert ev.sector_number == Decimal("-9.01")
        assert ev.is_percentage is False

    def test_the_requested_basis_is_recorded_because_the_payload_cannot_say(self) -> None:
        """key-ratios honours `?type=` but echoes nothing. The caller must carry it."""
        doc = read_key_ratios(
            statement_fetch(key_ratios_body(), surface=RATIOS),
            requested_basis=StatementBasis.CONSOLIDATED,
        )
        assert doc.basis is StatementBasis.CONSOLIDATED

    def test_a_data_object_instead_of_an_array_is_drift(self) -> None:
        body = key_ratios_body()
        body["data"] = {"ratios": body["data"]}
        doc = read_key_ratios(
            statement_fetch(body, surface=RATIOS),
            requested_basis=StatementBasis.STANDALONE,
        )
        assert doc.outcome is AcquisitionOutcome.SCHEMA_DRIFT

    def test_a_value_that_is_not_a_number_is_drift_not_a_silent_zero(self) -> None:
        body = key_ratios_body()
        body["data"][0]["company_value"] = "-"
        doc = read_key_ratios(
            statement_fetch(body, surface=RATIOS),
            requested_basis=StatementBasis.STANDALONE,
        )
        assert doc.outcome is AcquisitionOutcome.SCHEMA_DRIFT


class TestSurfaceBinding:
    @pytest.mark.parametrize(
        ("reader", "wrong_surface"),
        [
            (read_income_statement, UpstoxSurface.BALANCE_SHEET),
            (read_balance_sheet, UpstoxSurface.CASH_FLOW),
            (read_cash_flow, UpstoxSurface.KEY_RATIOS),
            (read_key_ratios, UpstoxSurface.INCOME_STATEMENT),
        ],
    )
    def test_a_reader_refuses_a_capture_from_another_surface(
        self, reader: object, wrong_surface: UpstoxSurface
    ) -> None:
        """The four bodies are similar enough to half-parse each other."""
        fetch = statement_fetch({"status": "success", "data": []}, surface=wrong_surface)
        with pytest.raises(ValueError, match="surface"):
            reader(fetch, requested_basis=StatementBasis.STANDALONE)  # type: ignore[operator]
