"""Unit tests for configuration parsing in EnvelopeBudget."""

from __future__ import annotations

import datetime
import re

import pytest

from fava_envelope import EnvelopeBudget, ExtensionConfig
from tests.fixtures.test_data import SAMPLE_CONFIG, create_mock_ledger


class TestConfigurationParsing:
    """Test configuration parsing functionality."""

    def test_empty_config(self):
        """Test handling of empty configuration."""
        ledger = create_mock_ledger()
        extension = EnvelopeBudget(ledger)
        extension.config = {}

        config = extension.read_extension_config()

        assert isinstance(config, ExtensionConfig)
        assert config.budgets == []

    def test_basic_config_parsing(self):
        """Test parsing of basic configuration."""
        ledger = create_mock_ledger()
        extension = EnvelopeBudget(ledger)
        extension.config = SAMPLE_CONFIG

        config = extension.read_extension_config()

        assert len(config.budgets) == 1
        budget = config.budgets[0]

        assert budget.name == "Test Budget"
        assert budget.currency == "USD"
        assert budget.start_date == datetime.date(2024, 1, 1)
        assert len(budget.budget_accounts) == 1
        assert isinstance(budget.budget_accounts[0], re.Pattern)

    def test_default_values(self):
        """Test that default values are applied correctly."""
        config_with_defaults = {"budgets": [{"name": "Minimal Budget"}]}

        ledger = create_mock_ledger()
        extension = EnvelopeBudget(ledger)
        extension.config = config_with_defaults

        config = extension.read_extension_config()
        budget = config.budgets[0]

        assert budget.name == "Minimal Budget"
        assert budget.currency == "USD"
        assert budget.start_date == datetime.date(2000, 1, 1)
        assert len(budget.budget_accounts) == 1
        assert budget.budget_accounts[0].pattern == "Assets:*"
        assert budget.mappings == []

    def test_mappings_parsing(self):
        """Test parsing of account mappings."""
        config_with_mappings = {
            "budgets": [
                {
                    "name": "Budget with Mappings",
                    "mappings": [
                        {"from": "Expenses:Food:.*", "to": "Expenses:Food"},
                        {
                            "from": "Expenses:Transport:.*",
                            "to": "Expenses:Transport",
                        },
                    ],
                }
            ]
        }

        ledger = create_mock_ledger()
        extension = EnvelopeBudget(ledger)
        extension.config = config_with_mappings

        config = extension.read_extension_config()
        budget = config.budgets[0]

        assert len(budget.mappings) == 2

        # Test that mappings are compiled regex patterns paired with target accounts
        mapping1 = budget.mappings[0]
        assert isinstance(mapping1[0], re.Pattern)
        assert mapping1[0].pattern == "Expenses:Food:.*"
        assert mapping1[1] == "Expenses:Food"

        mapping2 = budget.mappings[1]
        assert isinstance(mapping2[0], re.Pattern)
        assert mapping2[0].pattern == "Expenses:Transport:.*"
        assert mapping2[1] == "Expenses:Transport"

    def test_multiple_budget_accounts(self):
        """Test parsing of multiple budget accounts."""
        config_multi_accounts = {
            "budgets": [
                {
                    "name": "Multi Account Budget",
                    "budget accounts": [
                        "Assets:Checking",
                        "Assets:Savings",
                        "Assets:Investment:.*",
                    ],
                }
            ]
        }

        ledger = create_mock_ledger()
        extension = EnvelopeBudget(ledger)
        extension.config = config_multi_accounts

        config = extension.read_extension_config()
        budget = config.budgets[0]

        assert len(budget.budget_accounts) == 3
        assert budget.budget_accounts[0].pattern == "Assets:Checking"
        assert budget.budget_accounts[1].pattern == "Assets:Savings"
        assert budget.budget_accounts[2].pattern == "Assets:Investment:.*"

    def test_start_date_parsing(self):
        """Test parsing of different start date formats."""
        test_cases = [
            ("2024-01", datetime.date(2024, 1, 1)),
            ("2023-12", datetime.date(2023, 12, 1)),
            ("2025-06", datetime.date(2025, 6, 1)),
        ]

        for date_str, expected_date in test_cases:
            config = {
                "budgets": [
                    {"name": f"Test Budget {date_str}", "start date": date_str}
                ]
            }

            ledger = create_mock_ledger()
            extension = EnvelopeBudget(ledger)
            extension.config = config

            parsed_config = extension.read_extension_config()
            budget = parsed_config.budgets[0]

            assert budget.start_date == expected_date

    def test_end_date_generation(self):
        """Test that end date is set to current date."""
        ledger = create_mock_ledger()
        extension = EnvelopeBudget(ledger)
        extension.config = SAMPLE_CONFIG

        config = extension.read_extension_config()
        budget = config.budgets[0]

        # End date should be today's date
        today = datetime.date.today()
        assert budget.end_date == datetime.date(
            today.year, today.month, today.day
        )

    def test_multiple_budgets(self):
        """Test parsing of multiple budgets."""
        multi_budget_config = {
            "budgets": [
                {"name": "USD Budget", "currency": "USD"},
                {"name": "EUR Budget", "currency": "EUR"},
            ]
        }

        ledger = create_mock_ledger()
        extension = EnvelopeBudget(ledger)
        extension.config = multi_budget_config

        config = extension.read_extension_config()

        assert len(config.budgets) == 2
        assert config.budgets[0].name == "USD Budget"
        assert config.budgets[0].currency == "USD"
        assert config.budgets[1].name == "EUR Budget"
        assert config.budgets[1].currency == "EUR"

    def test_invalid_config_types(self):
        """Test handling of invalid configuration types."""
        ledger = create_mock_ledger()
        extension = EnvelopeBudget(ledger)
        extension.config = "invalid string config"

        config = extension.read_extension_config()

        # Should handle non-dict config gracefully
        assert isinstance(config, ExtensionConfig)
        assert config.budgets == []

    @pytest.mark.parametrize("currency", ["USD", "EUR", "GBP", "CAD"])
    def test_currency_settings(self, currency):
        """Test different currency settings."""
        config = {
            "budgets": [{"name": f"{currency} Budget", "currency": currency}]
        }

        ledger = create_mock_ledger()
        extension = EnvelopeBudget(ledger)
        extension.config = config

        parsed_config = extension.read_extension_config()
        budget = parsed_config.budgets[0]

        assert budget.currency == currency
