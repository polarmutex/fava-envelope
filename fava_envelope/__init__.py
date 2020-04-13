"""
"""

from fava.ext import FavaExtensionBase
from beancount.core.number import Decimal, D

from .modules.beancount_envelope import BeancountEnvelope


class EnvelopeBudget(FavaExtensionBase):
    '''
    '''
    report_title = "Envelope Budget"

    def build_envelope_budget_tables(self, begin=None, end=None):
        module = BeancountEnvelope(
            self.ledger.entries,
            self.ledger.options
        )
        income_tables, envelope_tables = module.envelope_tables()
        return self.generate_envelope_query_table(
            income_tables, envelope_tables)

    def generate_envelope_query_table(self, income_tables, envelope_tables):

        tables = []

        income_table_types = []
        income_table_types.append(("Funds for mmonth", str(Decimal)))
        income_table_types.append(("Overspent in prev month", str(Decimal)))
        income_table_types.append(("Budgeted for month", str(Decimal)))
        income_table_types.append(("To be budgeted for month", str(Decimal)))

        envelope_table_types = []
        envelope_table_types.append(("Account", str(str)))
        envelope_table_types.append(("Budgeted", str(Decimal)))
        envelope_table_types.append(("Activity", str(Decimal)))
        envelope_table_types.append(("Available", str(Decimal)))

        income_table_rows = []
        for month in income_tables.columns:
            row = {}
            row["Funds for month"] = income_tables[month]["Avail Income"]
            row["Overspent in prev month"] = income_tables[month]["Overspent"]
            row["Budgeted for month"] = income_tables[month]["Budgeted"]
            row["To be budgeted for month"] = income_tables[month]["To Be Budgeted"]
            income_table_rows.append(row)


            envelope_table_rows = []
            for index, e_row in envelope_tables.iterrows():
                row = {}
                row["Account"] = index
                row["Budgeted"] = e_row[month, "budgeted"]
                row["Activity"] = e_row[month, "activity"]
                row["Available"] = e_row[month, "available"]
                envelope_table_rows.append(row)

            tables.append((
                month,
                {
                    "income_table": (
                        income_table_types,
                        income_table_rows),
                    "envelope_table": (
                        envelope_table_types,
                        envelope_table_rows)
                }
            ))

        return tables
