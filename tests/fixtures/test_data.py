"""Test fixtures and sample data for fava-envelope tests."""

from __future__ import annotations

import datetime
from decimal import Decimal

import pandas as pd
from beancount.core import data
from beancount.core.amount import Amount
from beancount.core.data import Posting, Transaction
from beancount.parser import options

# Sample configuration for testing
SAMPLE_CONFIG = {
    "budgets": [
        {
            "name": "Test Budget",
            "currency": "USD",
            "start date": "2024-01",
            "budget accounts": ["Assets:Checking"],
            "mappings": [{"from": "Expenses:Food:.*", "to": "Expenses:Food"}],
        }
    ]
}


# Sample Beancount entries for testing
def create_sample_entries():
    """Create sample Beancount entries for testing."""
    entries = []

    # Opening balance
    entries.append(
        data.Open(
            meta={"filename": "test", "lineno": 1},
            date=datetime.date(2024, 1, 1),
            account="Assets:Checking",
            currencies=["USD"],
            booking=None,
        )
    )

    entries.append(
        data.Open(
            meta={"filename": "test", "lineno": 2},
            date=datetime.date(2024, 1, 1),
            account="Income:Salary",
            currencies=["USD"],
            booking=None,
        )
    )

    entries.append(
        data.Open(
            meta={"filename": "test", "lineno": 3},
            date=datetime.date(2024, 1, 1),
            account="Expenses:Food",
            currencies=["USD"],
            booking=None,
        )
    )

    # Income transaction
    entries.append(
        Transaction(
            meta={"filename": "test", "lineno": 4},
            date=datetime.date(2024, 1, 15),
            flag="*",
            payee=None,
            narration="Salary",
            tags=frozenset(),
            links=frozenset(),
            postings=[
                Posting(
                    account="Assets:Checking",
                    units=Amount(Decimal("3000.00"), "USD"),
                    cost=None,
                    price=None,
                    flag=None,
                    meta={},
                ),
                Posting(
                    account="Income:Salary",
                    units=Amount(Decimal("-3000.00"), "USD"),
                    cost=None,
                    price=None,
                    flag=None,
                    meta={},
                ),
            ],
        )
    )

    # Food expense transaction
    entries.append(
        Transaction(
            meta={"filename": "test", "lineno": 5},
            date=datetime.date(2024, 1, 20),
            flag="*",
            payee="Grocery Store",
            narration="Groceries",
            tags=frozenset(),
            links=frozenset(),
            postings=[
                Posting(
                    account="Expenses:Food",
                    units=Amount(Decimal("150.00"), "USD"),
                    cost=None,
                    price=None,
                    flag=None,
                    meta={},
                ),
                Posting(
                    account="Assets:Checking",
                    units=Amount(Decimal("-150.00"), "USD"),
                    cost=None,
                    price=None,
                    flag=None,
                    meta={},
                ),
            ],
        )
    )

    # Custom directive for envelope allocation
    entries.append(
        data.Custom(
            meta={"filename": "test", "lineno": 6},
            date=datetime.date(2024, 1, 31),
            type="envelope",
            values=[
                "allocate",
                "Expenses:Food",
                Amount(Decimal("500.00"), "USD"),
            ],
        )
    )

    return entries


def create_sample_options():
    """Create sample options map for testing."""
    return options.OPTIONS_DEFAULTS.copy()


def create_sample_dataframes():
    """Create sample DataFrames for testing."""
    months = ["2024-01", "2024-02", "2024-03"]

    # Sample top DataFrame (income summary)
    top_df = pd.DataFrame(
        {
            "2024-01": [
                Decimal("3000.00"),
                Decimal("0.00"),
                Decimal("-500.00"),
                Decimal("2500.00"),
                Decimal("0.00"),
            ],
            "2024-02": [
                Decimal("2500.00"),
                Decimal("0.00"),
                Decimal("-400.00"),
                Decimal("2100.00"),
                Decimal("0.00"),
            ],
            "2024-03": [
                Decimal("2100.00"),
                Decimal("0.00"),
                Decimal("-300.00"),
                Decimal("1800.00"),
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

    # Sample envelope DataFrame
    column_index = pd.MultiIndex.from_product(
        [months, ["budgeted", "activity", "available"]], names=["Month", "col"]
    )
    envelope_df = pd.DataFrame(columns=column_index)
    envelope_df.index.name = "Envelopes"

    # Add sample envelope data
    envelope_df.loc["Expenses:Food", ("2024-01", "budgeted")] = Decimal(
        "500.00"
    )
    envelope_df.loc["Expenses:Food", ("2024-01", "activity")] = Decimal(
        "-150.00"
    )
    envelope_df.loc["Expenses:Food", ("2024-01", "available")] = Decimal(
        "350.00"
    )

    envelope_df.loc["Expenses:Food", ("2024-02", "budgeted")] = Decimal(
        "400.00"
    )
    envelope_df.loc["Expenses:Food", ("2024-02", "activity")] = Decimal(
        "-120.00"
    )
    envelope_df.loc["Expenses:Food", ("2024-02", "available")] = Decimal(
        "630.00"
    )

    envelope_df.loc["Expenses:Food", ("2024-03", "budgeted")] = Decimal(
        "300.00"
    )
    envelope_df.loc["Expenses:Food", ("2024-03", "activity")] = Decimal(
        "-100.00"
    )
    envelope_df.loc["Expenses:Food", ("2024-03", "available")] = Decimal(
        "830.00"
    )

    envelope_df = envelope_df.fillna(Decimal("0.00"))

    return top_df, envelope_df


def create_mock_ledger():
    """Create a mock ledger object for testing."""

    class MockLedger:
        def __init__(self):
            self.all_entries = create_sample_entries()
            self.options = create_sample_options()
            self.prices = {}  # Empty price map for testing

    return MockLedger()
