"""
"""

# Debug
try:
    import ipdb
    #ipdb.set_trace()
except ImportError:
    pass

from fava.ext import FavaExtensionBase

from .modules import beancount_envelope

class EnvelopeBudget(FavaExtensionBase):
    '''
    '''
    report_title = "Envelope Budget"

    def build_envelop_budget_table(self, begin=None, end=None):
        return beancount_envelope.envelope_tables(
            self.ledger,
            self.config.get('start_date'),
            self.config.get('budget_accounts'),
            self.config.get('mappings'),
        )
