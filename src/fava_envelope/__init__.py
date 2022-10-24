"""
"""
from __future__ import annotations

from beancount.core.number import Decimal
from fava import __version__ as fava_version
from fava.context import g
from fava.ext import FavaExtensionBase

from .modules.beancount_envelope import BeancountEnvelope


class EnvelopeBudget(FavaExtensionBase):
    """ """

    report_title = "Envelope Budget"

    def generate_budget_df(self, currency):
        self.currency = currency
        module = BeancountEnvelope(
            g.ledger.all_entries, self.ledger.options, self.currency
        )
        (
            self.income_tables,
            self.envelope_tables,
            self.currency,
        ) = module.envelope_tables()

    def get_budgets_months_available(self, currency):
        self.generate_budget_df(currency)
        return self.income_tables.columns

    def check_month_in_available_months(self, month, currency):
        if month:
            if month in self.get_budgets_months_available(currency):
                return True
        return False

    def get_currencies(self):
        if "currencies" in self.config:
            return self.config["currencies"]
        else:
            return None

    def generate_income_query_tables(self, month):

        income_table_types = []
        income_table_types.append(("Name", str(str)))
        income_table_types.append(("Amount", str(Decimal)))

        income_table_rows = []

        if month is not None:
            income_table_rows.append(
                {
                    "Name": "Funds for month",
                    "Amount": self.income_tables[month]["Avail Income"],
                }
            )
            income_table_rows.append(
                {
                    "Name": "Overspent in prev month",
                    "Amount": self.income_tables[month]["Overspent"],
                }
            )
            income_table_rows.append(
                {
                    "Name": "Budgeted for month",
                    "Amount": self.income_tables[month]["Budgeted"],
                }
            )
            income_table_rows.append(
                {
                    "Name": "To be budgeted for month",
                    "Amount": self.income_tables[month]["To Be Budgeted"],
                }
            )
            income_table_rows.append(
                {
                    "Name": "Budgeted in the future",
                    "Amount": self.income_tables[month]["Budgeted Future"],
                }
            )

        return income_table_types, income_table_rows

    def generate_envelope_query_tables(self, month):

        envelope_table_types = []
        envelope_table_types.append(("Account", str(str)))
        envelope_table_types.append(("Budgeted", str(Decimal)))
        envelope_table_types.append(("Activity", str(Decimal)))
        envelope_table_types.append(("Available", str(Decimal)))

        envelope_table_rows = []

        if month is not None:
            for index, e_row in self.envelope_tables.iterrows():
                row = {}
                row["Account"] = index
                row["Budgeted"] = e_row[month, "budgeted"]
                row["Activity"] = e_row[month, "activity"]
                row["Available"] = e_row[month, "available"]
                envelope_table_rows.append(row)

        return envelope_table_types, envelope_table_rows

    def use_new_querytable(self):
        """
        from redstreet/fava_investor
        fava added the ledger as a first required argument to
        querytable.querytable after version 1.18, so in order to support both,
        we have to detect the version and adjust how we call it from inside our
        template
        """
        split_version = fava_version.split(".")
        if len(split_version) != 2:
            split_version = split_version[:2]
        major, minor = split_version
        return int(major) > 1 or (int(major) == 1 and int(minor) > 18)
