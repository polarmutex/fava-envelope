# Debug
try:
    import ipdb
except ImportError:
    pass

import datetime
import collections
import re

from beancount.core.number import Decimal
from beancount.core import data
#from beancount.core import prices
from beancount.core import convert
from beancount.core import inventory
from beancount.core import account_types
from beancount.parser import options

def envelope_tables(ledger, start_date, budget_accounts, mappings):

    entries = ledger.all_entries
    #price_map = prices.build_price_map(entries)
    price_map = ledger.price_map
    #acctypes = options.get_account_types(options_map)
    acctypes = options.get_account_types(ledger.options)

    decimal_precison = '0.00'
    Q = Decimal(decimal_precison)

    # Compute start of period
    today = datetime.date.today()
    date_start = datetime.date(2020,1,1)

    # Compute end of period
    date_end = datetime.date(today.year, today.month, today.day)

    # Accumulate expenses for the period
    balances = collections.defaultdict(
        lambda: collections.defaultdict(inventory.Inventory))
    all_months = set()

    for entry in data.filter_txns(entries):

        # Check entry in date range
        if entry.date < date_start or entry.date > date_end:
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
            if account_type != acctypes.expenses:
                continue
            #if any(regexp.match(posting.account) for regexp in EXCLUDES):
            #    continue
            if posting.units.currency != "USD":
                continue

            account = posting.account
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
            balance = balance.reduce(convert.get_value, price_map, date)
            balance = balance.reduce(
                convert.convert_position, "USD", price_map, date)
            try:
                pos = balance.get_only_position()
            except AssertionError:
                print(balance)
                raise
            total = pos.units.number if pos and pos.units else None
            sbalances[account][month] = total

    # Pivot the table

    account_type = ("account", str(str))
    total_type = ("total", str(Decimal))
    types = [account_type, total_type]

    header_months = sorted(all_months)
    header = ['account'] + ['{}-{:02d}'.format(*m) for m in header_months]
    rows = []
    for account in sorted(sbalances.keys()):
        row = {}
        row["account"] = account
        #for month in header_months:
        #    total = sbalances[account].get(month, None)
        row["total"] = Decimal(0.00)
        #row.append(str(total.quantize(Q)) if total else '')
        rows.append(row)

    #breakpoint()
    return types, rows
