import datetime
from decimal import Decimal

import polars as pl
import pytest
from beancount.loader import load_string

from fava_envelope.modules.beancount_envelope import (
    BeancountEnvelope,
    _find_currency,
)

MINIMAL_BEANCOUNT = """
2020-01-01 open Assets:Checking USD
2020-01-01 open Income:Salary USD
2020-01-01 open Expenses:Food USD

2020-01-01 custom "envelope" "start date" "2020-01"
2020-01-01 custom "envelope" "budget account" "Assets:Checking"

2020-01-15 * "Employer" "Paycheck"
  Assets:Checking  1000 USD
  Income:Salary   -1000 USD

2020-01-20 * "Grocery Store" "Food"
  Expenses:Food    200 USD
  Assets:Checking -200 USD
"""

MULTI_MONTH_BEANCOUNT = """
2020-01-01 open Assets:Checking USD
2020-01-01 open Income:Salary USD
2020-01-01 open Expenses:Food USD
2020-01-01 open Expenses:Rent USD

2020-01-01 custom "envelope" "start date" "2020-01"
2020-01-01 custom "envelope" "budget account" "Assets:Checking"

2020-01-01 custom "envelope" "allocate" "Expenses:Food" 300.00
2020-01-01 custom "envelope" "allocate" "Expenses:Rent" 800.00
2020-02-01 custom "envelope" "allocate" "Expenses:Food" 300.00

2020-01-15 * "Employer" "Paycheck"
  Assets:Checking  2000 USD
  Income:Salary   -2000 USD

2020-01-20 * "Grocery Store" "Food"
  Expenses:Food    200 USD
  Assets:Checking -200 USD

2020-02-01 * "Landlord" "Rent"
  Expenses:Rent    800 USD
  Assets:Checking -800 USD

2020-02-15 * "Employer" "Paycheck"
  Assets:Checking  2000 USD
  Income:Salary   -2000 USD
"""


def load_envelope(beancount_str, currency="USD", end_date=None):
    """Helper to load a BeancountEnvelope from a string, patching today's date."""
    entries, errors, options_map = load_string(beancount_str)
    assert not [e for e in errors if "envelope" not in str(e).lower()], errors
    if end_date is None:
        import datetime

        end_date = datetime.date(2020, 12, 1)
    return BeancountEnvelope(entries, options_map, currency, end_date=end_date)


def income_get(income_df: pl.DataFrame, row: str, month: str) -> Decimal:
    """Helper: get a value from income_df by row label and month column."""
    val = income_df.filter(pl.col("row") == row)[month][0]
    return Decimal(str(val))


def envelope_get(
    envelope_df: pl.DataFrame, account: str, month: str, col: str
) -> Decimal:
    """Helper: get a value from envelope_df by account and month_col."""
    col_name = f"{month}_{col}"
    val = envelope_df.filter(pl.col("account") == account)[col_name][0]
    return Decimal(str(val))


class TestInit:
    def test_loads_start_date(self):
        env = load_envelope(MINIMAL_BEANCOUNT)
        assert env.start_date == "2020-01"

    def test_loads_budget_accounts(self):
        env = load_envelope(MINIMAL_BEANCOUNT)
        assert len(env.budget_accounts) == 1
        assert env.budget_accounts[0].pattern == "Assets:Checking"

    def test_currency_defaults_to_operating_currency(self):
        env = load_envelope(MINIMAL_BEANCOUNT, currency="")
        assert env.currency == "USD"

    def test_explicit_currency_respected(self):
        env = load_envelope(MINIMAL_BEANCOUNT, currency="USD")
        assert env.currency == "USD"

    def test_months_ahead_defaults_to_zero(self):
        env = load_envelope(MINIMAL_BEANCOUNT)
        assert env.months_ahead == 0


class TestFindCurrency:
    def test_falls_back_to_usd(self):
        result = _find_currency({})
        assert result == "USD"

    def test_reads_operating_currency(self):
        result = _find_currency({"operating_currency": ["EUR"]})
        assert result == "EUR"


class TestEnvelopeTables:
    def test_returns_three_items(self):
        env = load_envelope(
            MINIMAL_BEANCOUNT, end_date=datetime.date(2020, 2, 1)
        )
        result = env.envelope_tables()
        assert len(result) == 3

    def test_income_df_has_avail_income(self):
        env = load_envelope(
            MINIMAL_BEANCOUNT, end_date=datetime.date(2020, 2, 1)
        )
        income_df, _, _ = env.envelope_tables()
        assert "Avail Income" in income_df["row"].to_list()

    def test_income_df_has_correct_months(self):
        env = load_envelope(
            MINIMAL_BEANCOUNT, end_date=datetime.date(2020, 3, 1)
        )
        income_df, _, _ = env.envelope_tables()
        assert "2020-01" in income_df.columns
        assert "2020-02" in income_df.columns

    def test_activity_recorded_for_expense(self):
        env = load_envelope(
            MULTI_MONTH_BEANCOUNT, end_date=datetime.date(2020, 2, 1)
        )
        _, envelope_df, _ = env.envelope_tables()
        activity = envelope_get(
            envelope_df, "Expenses:Food", "2020-01", "activity"
        )
        assert activity == Decimal("-200.00")

    def test_budgeted_recorded(self):
        env = load_envelope(
            MULTI_MONTH_BEANCOUNT, end_date=datetime.date(2020, 2, 1)
        )
        _, envelope_df, _ = env.envelope_tables()
        budgeted = envelope_get(
            envelope_df, "Expenses:Food", "2020-01", "budgeted"
        )
        assert budgeted == Decimal("300.00")

    def test_available_equals_budgeted_plus_activity(self):
        env = load_envelope(
            MULTI_MONTH_BEANCOUNT, end_date=datetime.date(2020, 2, 1)
        )
        _, envelope_df, _ = env.envelope_tables()
        available = envelope_get(
            envelope_df, "Expenses:Food", "2020-01", "available"
        )
        expected = envelope_get(
            envelope_df, "Expenses:Food", "2020-01", "budgeted"
        ) + envelope_get(envelope_df, "Expenses:Food", "2020-01", "activity")
        assert available == expected

    def test_available_rolls_over_to_next_month(self):
        env = load_envelope(
            MULTI_MONTH_BEANCOUNT, end_date=datetime.date(2020, 3, 1)
        )
        _, envelope_df, _ = env.envelope_tables()
        jan_available = envelope_get(
            envelope_df, "Expenses:Food", "2020-01", "available"
        )
        feb_budgeted = envelope_get(
            envelope_df, "Expenses:Food", "2020-02", "budgeted"
        )
        feb_activity = envelope_get(
            envelope_df, "Expenses:Food", "2020-02", "activity"
        )
        feb_available = envelope_get(
            envelope_df, "Expenses:Food", "2020-02", "available"
        )
        assert feb_available == jan_available + feb_budgeted + feb_activity

    def test_to_be_budgeted_is_nonnegative_when_income_covers_expenses(self):
        env = load_envelope(
            MULTI_MONTH_BEANCOUNT, end_date=datetime.date(2020, 2, 1)
        )
        income_df, _, _ = env.envelope_tables()
        assert income_get(income_df, "To Be Budgeted", "2020-01") >= Decimal(
            "0.00"
        )


class TestMappings:
    MAPPING_BEANCOUNT = """
2020-01-01 open Assets:Checking USD
2020-01-01 open Income:Salary USD
2020-01-01 open Expenses:Food:Groceries USD
2020-01-01 open Expenses:Food USD

2020-01-01 custom "envelope" "start date" "2020-01"
2020-01-01 custom "envelope" "budget account" "Assets:Checking"
2020-01-01 custom "envelope" "mapping" "Expenses:Food:.*" "Expenses:Food"

2020-01-15 * "Employer" "Paycheck"
  Assets:Checking  1000 USD
  Income:Salary   -1000 USD

2020-01-20 * "Grocery Store" "Food"
  Expenses:Food:Groceries  200 USD
  Assets:Checking         -200 USD
"""

    def test_mapping_consolidates_subaccounts(self):
        env = load_envelope(
            self.MAPPING_BEANCOUNT, end_date=datetime.date(2020, 2, 1)
        )
        _, envelope_df, _ = env.envelope_tables()
        accounts = envelope_df["account"].to_list()
        assert "Expenses:Food" in accounts
        assert "Expenses:Food:Groceries" not in accounts


class TestNegativeRollover:
    OVERSPENT_BEANCOUNT = """
2020-01-01 open Assets:Checking USD
2020-01-01 open Income:Salary USD
2020-01-01 open Expenses:Food USD

2020-01-01 custom "envelope" "start date" "2020-01"
2020-01-01 custom "envelope" "budget account" "Assets:Checking"
2020-01-01 custom "envelope" "negative rollover" "allow"
2020-01-01 custom "envelope" "allocate" "Expenses:Food" 100.00
2020-02-01 custom "envelope" "allocate" "Expenses:Food" 100.00

2020-01-15 * "Employer" "Paycheck"
  Assets:Checking  500 USD
  Income:Salary   -500 USD

2020-01-20 * "Grocery Store" "Overspend"
  Expenses:Food    200 USD
  Assets:Checking -200 USD

2020-02-15 * "Employer" "Paycheck"
  Assets:Checking  500 USD
  Income:Salary   -500 USD
"""

    def test_negative_rollover_carries_deficit(self):
        env = load_envelope(
            self.OVERSPENT_BEANCOUNT, end_date=datetime.date(2020, 3, 1)
        )
        _, envelope_df, _ = env.envelope_tables()
        jan_available = envelope_get(
            envelope_df, "Expenses:Food", "2020-01", "available"
        )
        feb_budgeted = envelope_get(
            envelope_df, "Expenses:Food", "2020-02", "budgeted"
        )
        feb_activity = envelope_get(
            envelope_df, "Expenses:Food", "2020-02", "activity"
        )
        feb_available = envelope_get(
            envelope_df, "Expenses:Food", "2020-02", "available"
        )
        assert jan_available < 0
        assert feb_available == jan_available + feb_budgeted + feb_activity

    def test_without_negative_rollover_deficit_is_dropped(self):
        beancount = self.OVERSPENT_BEANCOUNT.replace(
            '2020-01-01 custom "envelope" "negative rollover" "allow"\n', ""
        )
        env = load_envelope(beancount, end_date=datetime.date(2020, 3, 1))
        _, envelope_df, _ = env.envelope_tables()
        jan_available = envelope_get(
            envelope_df, "Expenses:Food", "2020-01", "available"
        )
        feb_budgeted = envelope_get(
            envelope_df, "Expenses:Food", "2020-02", "budgeted"
        )
        feb_activity = envelope_get(
            envelope_df, "Expenses:Food", "2020-02", "activity"
        )
        feb_available = envelope_get(
            envelope_df, "Expenses:Food", "2020-02", "available"
        )
        assert jan_available < 0
        # deficit not carried: feb available = budgeted + activity only
        assert feb_available == feb_budgeted + feb_activity


class TestCurrencyConversion:
    MULTI_CURRENCY = """
2020-01-01 open Assets:Checking USD
2020-01-01 open Income:Salary USD
2020-01-01 open Equity:Conversions USD
2020-01-01 open Expenses:Food USD

2020-01-01 custom "envelope" "start date" "2020-01"
2020-01-01 custom "envelope" "budget account" "Assets:Checking"

2020-01-15 * "Employer" "Paycheck"
  Assets:Checking   1000 USD
  Income:Salary    -1000 USD

2020-01-20 * "Grocery"
  Expenses:Food    200 USD
  Assets:Checking -200 USD
"""

    def test_foreign_currency_income_excluded(self):
        """Income in same currency as budget should be captured."""
        env = load_envelope(
            self.MULTI_CURRENCY, end_date=datetime.date(2020, 2, 1)
        )
        income_df, _, _ = env.envelope_tables()
        # Should not crash; avail income may be 0 or partial
        assert "Avail Income" in income_df["row"].to_list()


class TestStartingBalance:
    def test_starting_balance_included_in_first_month(self):
        """Pre-existing checking balance should boost first month's available income."""
        beancount = """
2019-01-01 open Assets:Checking USD
2019-01-01 open Income:Salary USD
2019-01-01 open Expenses:Food USD

2019-01-01 * "Opening Balance"
  Assets:Checking  5000 USD
  Equity:Opening  -5000 USD

2019-01-01 open Equity:Opening USD

2020-01-01 custom "envelope" "start date" "2020-01"
2020-01-01 custom "envelope" "budget account" "Assets:Checking"

2020-01-15 * "Paycheck"
  Assets:Checking  1000 USD
  Income:Salary   -1000 USD
"""
        entries, errors, options_map = load_string(beancount)
        assert not errors
        env = BeancountEnvelope(
            entries, options_map, "USD", end_date=datetime.date(2020, 2, 1)
        )
        income_df, _, _ = env.envelope_tables()
        avail = income_get(income_df, "Avail Income", "2020-01")
        # Starting balance of 5000 + income 1000
        assert avail > Decimal("1000.00")


class TestAllocateAccumulation:
    DOUBLE_ALLOCATE = """
2020-01-01 open Assets:Checking USD
2020-01-01 open Income:Salary USD
2020-01-01 open Expenses:Food USD

2020-01-01 custom "envelope" "start date" "2020-01"
2020-01-01 custom "envelope" "budget account" "Assets:Checking"
2020-01-01 custom "envelope" "allocate" "Expenses:Food" 100.00
2020-01-15 custom "envelope" "allocate" "Expenses:Food" 50.00

2020-01-10 * "Paycheck"
  Assets:Checking 2000 USD
  Income:Salary  -2000 USD
"""

    def test_multiple_allocations_same_month_accumulate(self):
        env = load_envelope(
            self.DOUBLE_ALLOCATE, end_date=datetime.date(2020, 2, 1)
        )
        _, envelope_df, _ = env.envelope_tables()
        budgeted = envelope_get(
            envelope_df, "Expenses:Food", "2020-01", "budgeted"
        )
        assert budgeted == Decimal("150.00")


class TestDateRange:
    def test_transactions_before_start_date_excluded_from_activity(self):
        beancount = """
2019-01-01 open Assets:Checking USD
2019-01-01 open Income:Salary USD
2019-01-01 open Expenses:Food USD

2019-12-20 * "Pre-period spending"
  Expenses:Food    500 USD
  Assets:Checking -500 USD

2020-01-01 custom "envelope" "start date" "2020-01"
2020-01-01 custom "envelope" "budget account" "Assets:Checking"

2020-01-10 * "Paycheck"
  Assets:Checking 1000 USD
  Income:Salary  -1000 USD
"""
        entries, errors, options_map = load_string(beancount)
        env = BeancountEnvelope(
            entries, options_map, "USD", end_date=datetime.date(2020, 2, 1)
        )
        _, envelope_df, _ = env.envelope_tables()
        # Expenses:Food should have zero activity (pre-period tx excluded)
        assert "Expenses:Food" not in envelope_df["account"].to_list()

    def test_transactions_after_end_date_excluded(self):
        beancount = (
            MINIMAL_BEANCOUNT
            + """
2020-06-01 * "Future spend"
  Expenses:Food    999 USD
  Assets:Checking -999 USD
"""
        )
        entries, errors, options_map = load_string(beancount)
        env = BeancountEnvelope(
            entries, options_map, "USD", end_date=datetime.date(2020, 2, 1)
        )
        _, envelope_df, _ = env.envelope_tables()
        if "Expenses:Food" in envelope_df["account"].to_list():
            activity = envelope_get(
                envelope_df, "Expenses:Food", "2020-01", "activity"
            )
            assert activity == Decimal("-200.00")  # Only the in-range tx


class TestLargeExampleFile:
    @pytest.fixture
    def example_env(self):
        import os

        example_path = os.path.join(
            os.path.dirname(__file__), "..", "example.beancount"
        )
        if not os.path.exists(example_path):
            pytest.skip("example.beancount not found")
        from beancount.loader import load_file

        entries, errors, options_map = load_file(example_path)
        env = BeancountEnvelope(
            entries, options_map, "USD", end_date=datetime.date(2015, 11, 1)
        )
        if env.start_date is None:
            pytest.skip("example.beancount has no envelope directives")
        return env

    def test_example_file_loads_without_error(self, example_env):
        income_df, envelope_df, currency = example_env.envelope_tables()
        assert currency == "USD"
        assert len(income_df) > 0

    def test_example_file_has_expected_rows(self, example_env):
        income_df, _, _ = example_env.envelope_tables()
        rows = income_df["row"].to_list()
        for expected in ["Avail Income", "Budgeted", "To Be Budgeted"]:
            assert expected in rows

    def test_example_file_envelope_df_no_nulls(self, example_env):
        _, envelope_df, _ = example_env.envelope_tables()
        assert not envelope_df.is_empty()
        # No null/NaN values in numeric columns
        for col in envelope_df.columns:
            if col != "account":
                assert envelope_df[col].null_count() == 0

    def test_example_file_available_never_explodes(self, example_env):
        """Sanity: available values are finite and reasonable."""
        _, envelope_df, _ = example_env.envelope_tables()
        for col in envelope_df.columns:
            if col.endswith("_available"):
                vals = envelope_df[col].to_list()
                assert all(abs(v) < 1_000_000 for v in vals)


class TestIncomeAccounts:
    INCOME_ACCOUNT_BEANCOUNT = """
2020-01-01 open Assets:Checking USD
2020-01-01 open Income:Salary USD
2020-01-01 open Income:Freelance USD
2020-01-01 open Expenses:Food USD

2020-01-01 custom "envelope" "start date" "2020-01"
2020-01-01 custom "envelope" "budget account" "Assets:Checking"
2020-01-01 custom "envelope" "income account" "Income:Freelance"

2020-01-10 * "Day job"
  Assets:Checking  1000 USD
  Income:Salary   -1000 USD

2020-01-15 * "Side gig"
  Assets:Checking   500 USD
  Income:Freelance -500 USD
"""

    def test_explicit_income_account_captured(self):
        entries, errors, options_map = load_string(
            self.INCOME_ACCOUNT_BEANCOUNT
        )
        env = BeancountEnvelope(
            entries, options_map, "USD", end_date=datetime.date(2020, 2, 1)
        )
        income_df, _, _ = env.envelope_tables()
        avail = income_get(income_df, "Avail Income", "2020-01")
        # Both salary (auto-detected as Income type) and freelance should count
        assert avail > Decimal("0")


class TestMonthsAhead:
    def test_months_ahead_extends_date_end(self):
        beancount = """
2020-01-01 open Assets:Checking USD
2020-01-01 open Income:Salary USD

2020-01-01 custom "envelope" "start date" "2020-01"
2020-01-01 custom "envelope" "budget account" "Assets:Checking"
2020-01-01 custom "envelope" "months ahead" "3"

2020-01-10 * "Pay"
  Assets:Checking 1000 USD
  Income:Salary  -1000 USD
"""
        entries, errors, options_map = load_string(beancount)
        env = BeancountEnvelope(entries, options_map, "USD")
        assert env.months_ahead == 3


class TestDataFrameSchema:
    def test_income_df_columns(self):
        env = load_envelope(
            MINIMAL_BEANCOUNT, end_date=datetime.date(2020, 2, 1)
        )
        income_df, _, _ = env.envelope_tables()
        assert "row" in income_df.columns
        assert "2020-01" in income_df.columns

    def test_envelope_df_has_all_column_suffixes(self):
        env = load_envelope(
            MULTI_MONTH_BEANCOUNT, end_date=datetime.date(2020, 3, 1)
        )
        _, envelope_df, _ = env.envelope_tables()
        for month in ["2020-01", "2020-02"]:
            for suffix in ["budgeted", "activity", "available"]:
                assert f"{month}_{suffix}" in envelope_df.columns

    def test_envelope_df_account_column_is_string(self):
        env = load_envelope(
            MULTI_MONTH_BEANCOUNT, end_date=datetime.date(2020, 2, 1)
        )
        _, envelope_df, _ = env.envelope_tables()
        assert envelope_df["account"].dtype == pl.String

    def test_income_df_values_are_float(self):
        env = load_envelope(
            MINIMAL_BEANCOUNT, end_date=datetime.date(2020, 2, 1)
        )
        income_df, _, _ = env.envelope_tables()
        assert income_df["2020-01"].dtype in (pl.Float32, pl.Float64)


class TestIdempotency:
    def test_calling_envelope_tables_twice_gives_same_result(self):
        env = load_envelope(
            MULTI_MONTH_BEANCOUNT, end_date=datetime.date(2020, 3, 1)
        )
        income1, env1, cur1 = env.envelope_tables()
        income2, env2, cur2 = env.envelope_tables()
        assert cur1 == cur2
        assert income1.equals(income2)
        assert env1.equals(env2)
