# Debug
try:
    import ipdb
except ImportError:
    pass

import datetime
import collections
import logging
import pandas as pd
import re

from beancount.core.number import Decimal
from beancount.core import data
from beancount.core import prices
from beancount.core import convert
from beancount.core import inventory
from beancount.core import account_types
from beancount.core.data import Custom
from beancount.parser import options

class BeancountEnvelope:

    def __init__(self, entries, options_map):

        self.entries = entries
        self.start_date, self.budget_accounts, self.mappings = self._find_envelop_settings()

        decimal_precison = '0.00'
        self.Q = Decimal(decimal_precison)

        # Compute start of period
        # TODO get start date from journal
        today = datetime.date.today()
        self.date_start = datetime.date(2020,1,1)

        # Compute end of period
        self.date_end = datetime.date(today.year, today.month, today.day)

        self.price_map = prices.build_price_map(entries)
        self.acctypes = options.get_account_types(options_map)

    def _find_envelop_settings(self):
        start_date = None
        budget_accounts= []
        mappings = []

        for e in self.entries:
            if isinstance(e, Custom) and e.type == "envelope":
                logging.info(e)
                if e.values[0].value == "start date":
                    start_date = e.values[1].value
                if e.values[0].value == "budget account":
                    budget_accounts.append(e.values[1].value)
                if e.values[0].value == "mapping":
                    mappings.append(e.values[1].value)
        return start_date, budget_accounts, mappings

    def envelope_tables(self):

        header, rows = self._calculate_budget_activity()

        # Create DataFrame
        column_index = pd.MultiIndex.from_product([header[1:], ['budgeted', 'activity', 'available']], names=['Month','col'])
        self.df = pd.DataFrame(columns=column_index)
        self.df.index.name = "Envelopes"

        # add in budget activity
        for row in rows:
            idx = 1
            for month in header[1:]:
                self.df.loc[row[0],(month,'budgeted')] = 0.00
                self.df.loc[row[0],(month,'activity')] = row[idx]
                self.df.loc[row[0],(month,'available')] = 0.00
                idx += 1

        self._calc_budget_budgeted()

        return self.df

    def _calculate_budget_activity(self):

        # Accumulate expenses for the period
        balances = collections.defaultdict(
            lambda: collections.defaultdict(inventory.Inventory))
        all_months = set()

        for entry in data.filter_txns(self.entries):

            # Check entry in date range
            if entry.date < self.date_start or entry.date > self.date_end:
                continue

            month = (entry.date.year, entry.date.month)
            # TODO domwe handle no transaction in a month?
            all_months.add(month);

            # TODO
            contains_no_budget_accounts = False
            if contains_no_budget_accounts:
                continue

            for posting in entry.postings:
                account_type = account_types.get_account_type(posting.account)
                if posting.units.currency != "USD":
                    continue
                if account_type == self.acctypes.expenses:
                    account = posting.account
                elif account_type == self.acctypes.income:
                    account = "Income"
                else:
                    continue
                #if any(regexp.match(posting.account) for regexp in EXCLUDES):
                #    continue

                # TODO
                #for regexp, target_account in MAPS:
                #    if regexp.match(account):
                #        account = target_account
                #        break
                balances[account][month].add_position(posting)

        # Reduce the final balances to numbers
        sbalances = collections.defaultdict(dict)
        for account, months in sorted(balances.items()):
            for month, balance in sorted(months.items()):
                year, mth = month
                date = datetime.date(year, mth, 1)
                balance = balance.reduce(convert.get_value, self.price_map, date)
                balance = balance.reduce(
                    convert.convert_position, "USD", self.price_map, date)
                try:
                    pos = balance.get_only_position()
                except AssertionError:
                    print(balance)
                    raise
                total = pos.units.number if pos and pos.units else None
                sbalances[account][month] = total

        # Pivot the table
        header_months = sorted(all_months)
        header = ['account'] + ['{}-{:02d}'.format(*m) for m in header_months]

        rows = []
        for account in sorted(sbalances.keys()):
            row = [account]
            for month in header_months:
                total = sbalances[account].get(month, None)
                temp = total.quantize(self.Q) if total else 0.00
                row.append(str(temp))
            rows.append(row)

        return header, rows

    def _calc_budget_budgeted(self):
        rows = {}
        for e in self.entries:
            if isinstance(e, Custom) and e.type == "envelope":
                logging.info(e)
                if e.values[0].value == "transfer":
                    month = f"{e.date.year}-{e.date.month:02}"
                    self.df.loc[e.values[1].value,(month,'budgeted')] = -1 * e.values[3].value
                    self.df.loc[e.values[2].value,(month,'budgeted')] = e.values[3].value
