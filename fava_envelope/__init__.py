"""
"""
try:
    import ipdb
    ipdb.set_trace()
except ImportError:
    pass

from fava.ext import FavaExtensionBase

class EnvelopeBudget(FavaExtensionBase):
    '''
    '''
    report_title = "Envelope Budget"

    def build_budget_tables(self, begin=None, end=None):
        return ""
