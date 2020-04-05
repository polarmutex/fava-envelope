"""
"""

# Debug
try:
    import ipdb
    #ipdb.set_trace()
except ImportError:
    pass

from fava.ext import FavaExtensionBase
from beancount.core.number import Decimal, D

from .modules import beancount_envelope

class EnvelopeBudget(FavaExtensionBase):
    '''
    '''
    report_title = "Envelope Budget"

    def build_envelop_budget_table(self, begin=None, end=None):
        activity = beancount_envelope.envelope_tables(
            self.ledger,
            self.config.get('start_date'),
            self.config.get('budget_accounts'),
            self.config.get('mappings'),
        )
        return self.generate_envelope_query_table(activity)

    def generate_envelope_query_table(self, activity):
        account_type = ("Account", str(str))
        budgeted_type = ("Budgeted", str(Decimal))
        activity_type = ("Activity", str(Decimal))
        available_type = ("Available", str(Decimal))
        types = [account_type, budgeted_type, activity_type, available_type]

        activity_header = activity[0]
        activity_rows = activity[1]

        rows = []
        for act_row in activity_rows:
            row = {}
            row["Account"] = act_row[0]
            row["Budgeted"] = Decimal(0.00)
            row["Activity"] = D(act_row[1])
            row["Available"] = Decimal(0.00)
            rows.append(row)

        return types, rows

