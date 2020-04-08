# Debug
try:
    import ipdb
except ImportError:
    pass

import datetime
import collections
import logging
import pandas as pd
import numpy as np
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

        months = []
        date_current = self.date_start
        while date_current < self.date_end:
            months.append(f"{date_current.year}-{str(date_current.month).zfill(2)}")
            month = date_current.month -1 + 1
            year = date_current.year + month // 12
            month = month % 12  +1
            date_current = datetime.date(year, month,1)

        logging.info(months)

        # Create Income DataFrame
        column_index = pd.MultiIndex.from_product([months], names=['Month'])
        self.income_df = pd.DataFrame(columns=months)

        # Create Envelopes DataFrame
        column_index = pd.MultiIndex.from_product([months, ['budgeted', 'activity', 'available']], names=['Month','col'])
        self.envelope_df = pd.DataFrame(columns=column_index)
        self.envelope_df.index.name = "Envelopes"

        self._calculate_budget_activity()
        self._calc_budget_budgeted()

        # Set Budgeted for month
        for month in months:
            self.income_df.loc["Budgeted",month] = self.envelope_df[month,'budgeted'].sum()

        # Set available
        for index, row in self.envelope_df.iterrows():
            for index2, month in enumerate(months):
                if index2 == 0:
                    row[month, 'available'] = row[month, 'budgeted'] + row[month, 'activity']
                else:
                    prev_available = row[months[index2-1],'available']
                    if prev_available > 0:
                        row[month, 'available'] = prev_available + row[month, 'budgeted'] + row[month, 'activity']
                    else:
                        row[month, 'available'] = row[month, 'budgeted'] + row[month, 'activity']

        # Set overspent
        for index, month in enumerate(months):
            if index == 0:
                self.income_df.loc["Overspent", month] = Decimal(0.00)
            else:
                overspent = Decimal(0.00)
                for index2, row in self.envelope_df.iterrows():
                    if row[month,'available'] < Decimal(0.00):
                        overspent += Decimal(row[month, 'available'])
                self.income_df.loc["Overspent", month] = overspent



        return self.income_df, self.envelope_df

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

        for account in sorted(sbalances.keys()):
            for month in header_months:
                total = sbalances[account].get(month, None)
                temp = total.quantize(self.Q) if total else 0.00
                # swap sign to be more human readable
                temp *= -1

                month_str = f"{str(month[0])}-{str(month[1]).zfill(2)}"
                if account == "Income":
                    self.income_df.loc["Avail Income",month_str] = Decimal(temp)
                else:
                    self.envelope_df.loc[account,(month_str,'budgeted')] = Decimal(0.00)
                    self.envelope_df.loc[account,(month_str,'activity')] = Decimal(temp)
                    self.envelope_df.loc[account,(month_str,'available')] = Decimal(0.00)

    def _calc_budget_budgeted(self):
        rows = {}
        for e in self.entries:
            if isinstance(e, Custom) and e.type == "envelope":
                logging.info(e)
                if e.values[0].value == "transfer":
                    month = f"{e.date.year}-{e.date.month:02}"
                    self.envelope_df.loc[e.values[1].value,(month,'budgeted')] = Decimal(e.values[2].value)
