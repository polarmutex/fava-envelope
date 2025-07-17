"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import pytest

from tests.fixtures.test_data import (
    create_mock_ledger,
    create_sample_dataframes,
)


@pytest.fixture
def mock_ledger():
    """Provide a mock ledger for testing."""
    return create_mock_ledger()


@pytest.fixture
def sample_dataframes():
    """Provide sample DataFrames for testing."""
    return create_sample_dataframes()


@pytest.fixture
def sample_config():
    """Provide sample configuration for testing."""
    return {
        "budgets": [
            {
                "name": "Test Budget",
                "currency": "USD",
                "start date": "2024-01",
                "budget accounts": ["Assets:Checking"],
                "mappings": [
                    {"from": "Expenses:Food:.*", "to": "Expenses:Food"}
                ],
            }
        ]
    }


@pytest.fixture
def empty_config():
    """Provide empty configuration for testing."""
    return {}


@pytest.fixture
def multi_budget_config():
    """Provide configuration with multiple budgets."""
    return {
        "budgets": [
            {
                "name": "USD Budget",
                "currency": "USD",
                "start date": "2024-01",
                "budget accounts": ["Assets:US:Checking"],
            },
            {
                "name": "EUR Budget",
                "currency": "EUR",
                "start date": "2024-01",
                "budget accounts": ["Assets:EU:Checking"],
            },
        ]
    }
