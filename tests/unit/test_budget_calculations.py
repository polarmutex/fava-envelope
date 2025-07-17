"""Unit tests for budget calculation logic."""

from __future__ import annotations

import datetime
from decimal import Decimal
from unittest.mock import patch

import pandas as pd

from fava_envelope import BudgetConfig, EnvelopeBudget
from tests.fixtures.test_data import (
    create_mock_ledger,
)


class TestBudgetCalculations:
    """Test budget calculation logic in detail."""

    def setup_method(self):
        """Set up test environment."""
        self.ledger = create_mock_ledger()
        self.extension = EnvelopeBudget(self.ledger)

        # Create a test budget config
        self.budget_config = BudgetConfig(
            name="Test Budget",
            start_date=datetime.date(2024, 1, 1),
            end_date=datetime.date(2024, 3, 31),
            budget_accounts=[],
            mappings=[],
            income_accounts="",
            currency="USD",
        )

    def test_month_generation(self):
        """Test month range generation in process_budget."""
        with patch.object(
            self.extension, "calc_budget_accconut_activity"
        ) as mock_calc:
            with patch.object(
                self.extension, "build_envelope_df"
            ) as mock_envelope:
                with patch.object(self.extension, "build_top_df") as mock_top:
                    mock_calc.return_value = {}

                    # Create proper mock DataFrames
                    envelope_df = pd.DataFrame(
                        columns=pd.MultiIndex.from_product(
                            [
                                ["2024-01", "2024-02", "2024-03"],
                                ["budgeted", "activity", "available"],
                            ],
                            names=["Month", "col"],
                        )
                    )
                    envelope_df.index.name = "Envelopes"
                    mock_envelope.return_value = envelope_df

                    top_df = pd.DataFrame(
                        columns=["2024-01", "2024-02", "2024-03"]
                    )
                    # Add required rows that process_budget expects
                    required_rows = [
                        "Avail Income",
                        "Overspent",
                        "Budgeted",
                        "To Be Budgeted",
                        "Budgeted Future",
                    ]
                    for row in required_rows:
                        top_df.loc[row, "2024-01"] = Decimal("0.00")
                        top_df.loc[row, "2024-02"] = Decimal("0.00")
                        top_df.loc[row, "2024-03"] = Decimal("0.00")
                    mock_top.return_value = top_df

                    result = self.extension.process_budget(self.budget_config)

                    expected_months = ["2024-01", "2024-02", "2024-03"]
                    assert result.months == expected_months

    def test_envelope_available_calculation_first_month(self):
        """Test available amount calculation for first month."""
        months = ["2024-01", "2024-02"]

        # Create envelope DataFrame with test data
        column_index = pd.MultiIndex.from_product(
            [months, ["budgeted", "activity", "available"]],
            names=["Month", "col"],
        )
        envelope_df = pd.DataFrame(columns=column_index)
        envelope_df.index.name = "Envelopes"

        # Set up test data
        envelope_df.loc["Expenses:Food", ("2024-01", "budgeted")] = Decimal(
            "500.00"
        )
        envelope_df.loc["Expenses:Food", ("2024-01", "activity")] = Decimal(
            "-150.00"
        )
        envelope_df.loc["Expenses:Food", ("2024-01", "available")] = Decimal(
            "0.00"
        )  # Will be calculated

        envelope_df.loc["Expenses:Food", ("2024-02", "budgeted")] = Decimal(
            "400.00"
        )
        envelope_df.loc["Expenses:Food", ("2024-02", "activity")] = Decimal(
            "-120.00"
        )
        envelope_df.loc["Expenses:Food", ("2024-02", "available")] = Decimal(
            "0.00"
        )  # Will be calculated

        envelope_df = envelope_df.fillna(Decimal("0.00"))

        # Apply the calculation logic from process_budget
        for index, row in envelope_df.iterrows():
            for index2, month in enumerate(months):
                if index2 == 0:  # First month
                    row[month, "available"] = (
                        row[month, "budgeted"] + row[month, "activity"]
                    )
                else:  # Subsequent months
                    prev_available = row[months[index2 - 1], "available"]
                    if prev_available > 0:
                        row[month, "available"] = (
                            prev_available
                            + row[month, "budgeted"]
                            + row[month, "activity"]
                        )
                    else:
                        row[month, "available"] = (
                            row[month, "budgeted"] + row[month, "activity"]
                        )

        # First month: 500.00 + (-150.00) = 350.00
        assert envelope_df.loc[
            "Expenses:Food", ("2024-01", "available")
        ] == Decimal("350.00")

        # Second month: 350.00 + 400.00 + (-120.00) = 630.00
        assert envelope_df.loc[
            "Expenses:Food", ("2024-02", "available")
        ] == Decimal("630.00")

    def test_envelope_available_calculation_negative_carryover(self):
        """Test available calculation when previous month is negative."""
        months = ["2024-01", "2024-02"]

        column_index = pd.MultiIndex.from_product(
            [months, ["budgeted", "activity", "available"]],
            names=["Month", "col"],
        )
        envelope_df = pd.DataFrame(columns=column_index)
        envelope_df.index.name = "Envelopes"

        # Set up test data with overspending in first month
        envelope_df.loc["Expenses:Food", ("2024-01", "budgeted")] = Decimal(
            "200.00"
        )
        envelope_df.loc["Expenses:Food", ("2024-01", "activity")] = Decimal(
            "-300.00"
        )  # Overspent
        envelope_df.loc["Expenses:Food", ("2024-01", "available")] = Decimal(
            "0.00"
        )

        envelope_df.loc["Expenses:Food", ("2024-02", "budgeted")] = Decimal(
            "400.00"
        )
        envelope_df.loc["Expenses:Food", ("2024-02", "activity")] = Decimal(
            "-150.00"
        )
        envelope_df.loc["Expenses:Food", ("2024-02", "available")] = Decimal(
            "0.00"
        )

        envelope_df = envelope_df.fillna(Decimal("0.00"))

        # Apply calculation logic
        for index, row in envelope_df.iterrows():
            for index2, month in enumerate(months):
                if index2 == 0:
                    row[month, "available"] = (
                        row[month, "budgeted"] + row[month, "activity"]
                    )
                else:
                    prev_available = row[months[index2 - 1], "available"]
                    if prev_available > 0:
                        row[month, "available"] = (
                            prev_available
                            + row[month, "budgeted"]
                            + row[month, "activity"]
                        )
                    else:
                        row[month, "available"] = (
                            row[month, "budgeted"] + row[month, "activity"]
                        )

        # First month: 200.00 + (-300.00) = -100.00
        assert envelope_df.loc[
            "Expenses:Food", ("2024-01", "available")
        ] == Decimal("-100.00")

        # Second month (negative carryover): 400.00 + (-150.00) = 250.00 (no carryover)
        assert envelope_df.loc[
            "Expenses:Food", ("2024-02", "available")
        ] == Decimal("250.00")

    def test_overspent_calculation(self):
        """Test overspent amount calculation in top_df."""
        months = ["2024-01", "2024-02", "2024-03"]

        # Create sample envelope data with proper MultiIndex structure
        column_index = pd.MultiIndex.from_product(
            [months, ["budgeted", "activity", "available"]],
            names=["Month", "col"],
        )
        envelope_df = pd.DataFrame(columns=column_index)
        envelope_df.index.name = "Envelopes"

        # Add sample data with overspending
        envelope_df.loc["Expenses:Food", ("2024-01", "available")] = Decimal(
            "-50.00"
        )
        envelope_df.loc["Expenses:Transport", ("2024-01", "available")] = (
            Decimal("-25.00")
        )
        envelope_df = envelope_df.fillna(Decimal("0.00"))

        # Create top_df
        top_df = pd.DataFrame(columns=months)
        top_df.loc["Overspent", "2024-01"] = Decimal("0.00")
        top_df.loc["Overspent", "2024-02"] = Decimal("0.00")
        top_df.loc["Overspent", "2024-03"] = Decimal("0.00")

        # Apply overspent calculation logic
        for index, month in enumerate(months):
            if index == 0:
                top_df.loc["Overspent", month] = Decimal("0.00")
            else:
                overspent = Decimal("0.00")
                for index2, row in envelope_df.iterrows():
                    prev_month = months[index - 1]
                    if row[prev_month, "available"] < Decimal("0.00"):
                        overspent += Decimal(row[prev_month, "available"])
                top_df.loc["Overspent", month] = overspent

        # Should be 0 for first month
        assert top_df.loc["Overspent", "2024-01"] == Decimal("0.00")

        # Should sum negative available amounts from previous month for
        # subsequent months
        expected_overspent = Decimal("-50.00") + Decimal(
            "-25.00"
        )  # Both negative amounts
        assert top_df.loc["Overspent", "2024-02"] == expected_overspent

    def test_budgeted_for_month_calculation(self):
        """Test budgeted amount calculation."""
        months = ["2024-01", "2024-02"]

        # Create envelope data
        column_index = pd.MultiIndex.from_product(
            [months, ["budgeted", "activity", "available"]],
            names=["Month", "col"],
        )
        envelope_df = pd.DataFrame(columns=column_index)
        envelope_df.index.name = "Envelopes"

        envelope_df.loc["Expenses:Food", ("2024-01", "budgeted")] = Decimal(
            "500.00"
        )
        envelope_df.loc["Expenses:Transport", ("2024-01", "budgeted")] = (
            Decimal("200.00")
        )
        envelope_df.loc["Expenses:Food", ("2024-02", "budgeted")] = Decimal(
            "450.00"
        )
        envelope_df.loc["Expenses:Transport", ("2024-02", "budgeted")] = (
            Decimal("180.00")
        )

        envelope_df = envelope_df.fillna(Decimal("0.00"))

        # Create top_df
        top_df = pd.DataFrame(columns=months)

        # Apply budgeted calculation
        for month in months:
            top_df.loc["Budgeted", month] = Decimal(
                -1 * envelope_df[month, "budgeted"].sum()
            )

        # January: -(500.00 + 200.00) = -700.00
        assert top_df.loc["Budgeted", "2024-01"] == Decimal("-700.00")

        # February: -(450.00 + 180.00) = -630.00
        assert top_df.loc["Budgeted", "2024-02"] == Decimal("-630.00")

    def test_available_income_adjustment(self):
        """Test available income adjustment across months."""
        months = ["2024-01", "2024-02", "2024-03"]

        # Create initial top_df
        top_df = pd.DataFrame(columns=months)
        top_df.loc["Avail Income", "2024-01"] = Decimal("3000.00")
        top_df.loc["Avail Income", "2024-02"] = Decimal(
            "3000.00"
        )  # New income
        top_df.loc["Avail Income", "2024-03"] = Decimal(
            "3000.00"
        )  # New income

        top_df.loc["Overspent", "2024-01"] = Decimal("0.00")
        top_df.loc["Overspent", "2024-02"] = Decimal("-50.00")
        top_df.loc["Overspent", "2024-03"] = Decimal("0.00")

        top_df.loc["Budgeted", "2024-01"] = Decimal("-2800.00")
        top_df.loc["Budgeted", "2024-02"] = Decimal("-2900.00")
        top_df.loc["Budgeted", "2024-03"] = Decimal("-2750.00")

        # Apply income adjustment logic
        for index, month in enumerate(months):
            if index == 0:
                continue
            else:
                prev_month = months[index - 1]
                top_df.loc["Avail Income", month] = (
                    top_df.loc["Avail Income", month]
                    + top_df.loc["Avail Income", prev_month]
                    + top_df.loc["Overspent", prev_month]
                    + top_df.loc["Budgeted", prev_month]
                )

        # January: 3000.00 (no change)
        assert top_df.loc["Avail Income", "2024-01"] == Decimal("3000.00")

        # February: 3000.00 + 3000.00 + 0.00 + (-2800.00) = 3200.00
        assert top_df.loc["Avail Income", "2024-02"] == Decimal("3200.00")

        # March: 3000.00 + 3200.00 + (-50.00) + (-2900.00) = 3250.00
        assert top_df.loc["Avail Income", "2024-03"] == Decimal("3250.00")

    def test_to_be_budgeted_calculation(self):
        """Test 'To Be Budgeted' calculation."""
        months = ["2024-01", "2024-02"]

        # Create top_df with sample data
        top_df = pd.DataFrame(
            {
                "2024-01": [
                    Decimal("3000.00"),
                    Decimal("0.00"),
                    Decimal("-2500.00"),
                    Decimal("0.00"),
                    Decimal("0.00"),
                ],
                "2024-02": [
                    Decimal("3500.00"),
                    Decimal("-50.00"),
                    Decimal("-2800.00"),
                    Decimal("0.00"),
                    Decimal("0.00"),
                ],
            },
            index=[
                "Avail Income",
                "Overspent",
                "Budgeted",
                "To Be Budgeted",
                "Budgeted Future",
            ],
        )

        # Apply to be budgeted calculation
        for month in months:
            top_df.loc["To Be Budgeted", month] = Decimal(top_df[month].sum())

        # January: 3000.00 + 0.00 + (-2500.00) + 0.00 + 0.00 = 500.00
        assert top_df.loc["To Be Budgeted", "2024-01"] == Decimal("500.00")

        # February: 3500.00 + (-50.00) + (-2800.00) + 0.00 + 0.00 = 650.00
        assert top_df.loc["To Be Budgeted", "2024-02"] == Decimal("650.00")

    def test_budgeted_future_calculation(self):
        """Test 'Budgeted Future' calculation."""
        months = ["2024-01", "2024-02", "2024-03"]

        # Create sample data
        top_df = pd.DataFrame(columns=months)
        top_df.loc["Avail Income", "2024-01"] = Decimal("3000.00")
        top_df.loc["Overspent", "2024-01"] = Decimal("0.00")
        top_df.loc["Budgeted", "2024-01"] = Decimal("-2000.00")
        top_df.loc["To Be Budgeted", "2024-01"] = Decimal("1000.00")
        top_df.loc["Budgeted Future", "2024-01"] = Decimal("0.00")

        top_df.loc["Budgeted", "2024-02"] = Decimal(
            "-800.00"
        )  # Next month budget

        top_df = top_df.fillna(Decimal("0.00"))

        # Apply budgeted future calculation
        for index, month in enumerate(months):
            sum_total = top_df[month].sum()
            if (index == len(months) - 1) or sum_total < 0:
                top_df.loc["Budgeted Future", month] = Decimal("0.00")
            else:
                next_month = months[index + 1]
                opp_budgeted_next_month = (
                    top_df.loc["Budgeted", next_month] * -1
                )
                if opp_budgeted_next_month < sum_total:
                    top_df.loc["Budgeted Future", month] = Decimal(
                        -1 * opp_budgeted_next_month
                    )
                else:
                    top_df.loc["Budgeted Future", month] = Decimal(
                        -1 * sum_total
                    )

        # Should allocate funds to future based on next month's budget
        # Min of available (1000.00) and needed (800.00) should be 800.00
        assert top_df.loc["Budgeted Future", "2024-01"] == Decimal("-800.00")
