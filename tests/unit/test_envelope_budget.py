"""Unit tests for EnvelopeBudget class methods."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pandas as pd
import pytest
from fava.core.query import QueryResultTable
from fava.helpers import FavaAPIError

from fava_envelope import BudgetCtx, EnvelopeBudget
from tests.fixtures.test_data import (
    SAMPLE_CONFIG,
    create_mock_ledger,
    create_sample_dataframes,
)


class TestEnvelopeBudget:
    """Test EnvelopeBudget class methods."""

    def setup_method(self):
        """Set up test instance."""
        self.ledger = create_mock_ledger()
        self.extension = EnvelopeBudget(self.ledger)
        self.extension.config = SAMPLE_CONFIG
        self.extension.extension_config = (
            self.extension.read_extension_config()
        )

        # Create mock budget contexts
        top_df, envelope_df = create_sample_dataframes()
        self.mock_budget_ctx = BudgetCtx(
            months=["2024-01", "2024-02", "2024-03"],
            top=top_df,
            envelopes=envelope_df,
        )
        self.extension.budgets = [self.mock_budget_ctx]

    def test_initialization(self):
        """Test basic initialization."""
        ledger = create_mock_ledger()
        extension = EnvelopeBudget(ledger)
        assert extension.report_title == "Envelope Budget"

    def test_bootstrap_valid_id(self):
        """Test bootstrap method with valid budget ID."""
        result = self.extension.bootstrap(0, "2024-01")

        assert "budgets" in result
        assert "months" in result
        assert "top" in result
        assert "envelopes" in result

        assert result["budgets"] == self.extension.extension_config.budgets
        assert result["months"] == ["2024-01", "2024-02", "2024-03"]
        assert isinstance(result["top"], QueryResultTable)
        assert isinstance(result["envelopes"], QueryResultTable)

    def test_bootstrap_invalid_id_low(self):
        """Test bootstrap method with invalid budget ID (too low)."""
        with pytest.raises(FavaAPIError, match="invalid dashboard ID: -1"):
            self.extension.bootstrap(-1, "2024-01")

    def test_bootstrap_invalid_id_high(self):
        """Test bootstrap method with invalid budget ID (too high)."""
        with pytest.raises(FavaAPIError, match="invalid dashboard ID: 1"):
            self.extension.bootstrap(1, "2024-01")

    def test_get_budget_months_valid_id(self):
        """Test get_budget_months with valid ID."""
        months = self.extension.get_budget_months(0)
        assert months == ["2024-01", "2024-02", "2024-03"]

    def test_get_budget_months_invalid_id(self):
        """Test get_budget_months with invalid ID."""
        with pytest.raises(FavaAPIError, match="invalid dashboard ID: 5"):
            self.extension.get_budget_months(5)

    def test_generate_income_query_table_with_month(self):
        """Test income query table generation with valid month."""
        top_df, _ = create_sample_dataframes()
        result = self.extension.generate_income_query_table(top_df, "2024-01")

        assert isinstance(result, QueryResultTable)
        assert len(result.types) == 2
        assert result.types[0].name == "Name"
        assert result.types[1].name == "Amount"
        assert len(result.rows) == 5

        # Check specific row data
        expected_rows = [
            ("Funds for month", Decimal("3000.00")),
            ("Overspent in prev month", Decimal("0.00")),
            ("Budgeted for month", Decimal("-500.00")),
            ("To be budgeted for month", Decimal("2500.00")),
            ("Budgeted in the future", Decimal("0.00")),
        ]

        for i, (expected_name, expected_amount) in enumerate(expected_rows):
            assert result.rows[i][0] == expected_name
            assert result.rows[i][1] == expected_amount

    def test_generate_income_query_table_no_month(self):
        """Test income query table generation with no month."""
        top_df, _ = create_sample_dataframes()
        result = self.extension.generate_income_query_table(top_df, None)

        assert isinstance(result, QueryResultTable)
        assert len(result.rows) == 0

    def test_generate_envelope_query_table_with_month(self):
        """Test envelope query table generation with valid month."""
        _, envelope_df = create_sample_dataframes()
        result = self.extension.generate_envelope_query_table(
            envelope_df, "2024-01"
        )

        assert isinstance(result, QueryResultTable)
        assert len(result.types) == 4
        assert result.types[0].name == "Account"
        assert result.types[1].name == "Budgeted"
        assert result.types[2].name == "Activity"
        assert result.types[3].name == "Available"

        assert len(result.rows) == 1  # One envelope (Expenses:Food)

        row = result.rows[0]
        assert row[0] == "Expenses:Food"
        assert row[1] == Decimal("500.00")  # budgeted
        assert row[2] == Decimal("-150.00")  # activity
        assert row[3] == Decimal("350.00")  # available

    def test_generate_envelope_query_table_no_month(self):
        """Test envelope query table generation with no month."""
        _, envelope_df = create_sample_dataframes()
        result = self.extension.generate_envelope_query_table(
            envelope_df, None
        )

        assert isinstance(result, QueryResultTable)
        assert len(result.rows) == 0

    def test_after_load_file(self):
        """Test after_load_file method."""
        ledger = create_mock_ledger()
        extension = EnvelopeBudget(ledger)
        extension.config = SAMPLE_CONFIG

        # Mock the process_budget method to avoid complex calculation
        with patch.object(extension, "process_budget") as mock_process:
            mock_process.return_value = self.mock_budget_ctx

            extension.after_load_file()

            assert hasattr(extension, "extension_config")
            assert hasattr(extension, "budgets")
            assert len(extension.budgets) == 1
            assert mock_process.called

    def test_build_top_df_structure(self):
        """Test basic structure of build_top_df method."""
        ledger = create_mock_ledger()
        extension = EnvelopeBudget(ledger)
        extension.config = SAMPLE_CONFIG

        cfg = extension.read_extension_config().budgets[0]
        months = ["2024-01", "2024-02"]
        balances = {}

        # Mock the query.run_query to avoid database dependency
        with patch("fava_envelope.query.run_query") as mock_query:
            mock_query.return_value = ([], [])  # Empty result

            result = extension.build_top_df(cfg, months, balances)

            assert isinstance(result, pd.DataFrame)
            assert list(result.columns) == months
            assert "Avail Income" in result.index

    def test_build_envelope_df_structure(self):
        """Test basic structure of build_envelope_df method."""
        ledger = create_mock_ledger()
        extension = EnvelopeBudget(ledger)
        months = ["2024-01", "2024-02"]
        balances = {
            "Expenses:Food": {
                (2024, 1): Decimal("150.00"),
                (2024, 2): Decimal("120.00"),
            }
        }

        result = extension.build_envelope_df(months, balances)

        assert isinstance(result, pd.DataFrame)
        assert isinstance(result.columns, pd.MultiIndex)
        assert result.index.name == "Envelopes"
        assert "Expenses:Food" in result.index

    def test_calc_budget_account_activity_structure(self):
        """Test structure of calc_budget_account_activity method."""
        ledger = create_mock_ledger()
        extension = EnvelopeBudget(ledger)
        extension.config = SAMPLE_CONFIG
        cfg = extension.read_extension_config().budgets[0]

        result = extension.calc_budget_accconut_activity(cfg)

        assert isinstance(result, dict)
        # Result should be a nested dict: account -> month tuple -> Decimal
        for account, months in result.items():
            assert isinstance(account, str)
            assert isinstance(months, dict)
            for month_tuple, amount in months.items():
                assert isinstance(month_tuple, tuple)
                assert len(month_tuple) == 2  # (year, month)
                assert isinstance(amount, Decimal)


class TestBudgetCtx:
    """Test BudgetCtx dataclass."""

    def test_budget_ctx_creation(self):
        """Test BudgetCtx creation with sample data."""
        top_df, envelope_df = create_sample_dataframes()
        ctx = BudgetCtx(
            months=["2024-01", "2024-02"], top=top_df, envelopes=envelope_df
        )

        assert ctx.months == ["2024-01", "2024-02"]
        assert isinstance(ctx.top, pd.DataFrame)
        assert isinstance(ctx.envelopes, pd.DataFrame)

    def test_budget_ctx_immutability(self):
        """Test that BudgetCtx is frozen (immutable)."""
        top_df, envelope_df = create_sample_dataframes()
        ctx = BudgetCtx(months=["2024-01"], top=top_df, envelopes=envelope_df)

        # Should not be able to modify frozen dataclass
        with pytest.raises(AttributeError):
            ctx.months = ["2024-02"]
