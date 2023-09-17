# Debug
from __future__ import annotations

import collections
import datetime
import logging
import re

import pandas as pd
from beancount.core import account_types
from beancount.core import amount
from beancount.core import convert
from beancount.core import data
from beancount.core import inventory
from beancount.core import prices
from beancount.core.data import Custom
from beancount.core.number import Decimal
from beancount.parser import options
from beancount.query import query
from dateutil.relativedelta import relativedelta


class BeancountEnvelope:
    def __init__(self, entries, options_map, currency):
        self.entries = entries
        self.options_map = options_map
        self.currency = currency
        self.negative_rollover = False
        self.months_ahead = 0

        if self.currency:
            self.etype = "envelope" + self.currency
        else:
            self.etype = "envelope"

        (
            self.start_date,
            self.budget_accounts,
            self.mappings,
            self.income_accounts,
            self.months_ahead,
        ) = self._find_envelop_settings()

        if not self.currency:
            self.currency = self._find_currency(options_map)

        decimal_precison = "0.00"
        self.Q = Decimal(decimal_precison)

        # Compute start of period
        # TODO get start date from journal
        today = datetime.date.today()
        self.date_start = datetime.datetime.strptime(
            self.start_date, "%Y-%m"
        ).date()

        # TODO should be able to assert errors

        # Compute end of period
        self.date_end = datetime.date(
            today.year, today.month, today.day
        ) + relativedelta(months=+self.months_ahead)

        self.price_map = prices.build_price_map(entries)
        self.acctypes = options.get_account_types(options_map)

    def _find_currency(self, options_map):
        default_currency = "USD"
        opt_currency = options_map.get("operating_currency")
        currency = opt_currency[0] if opt_currency else default_currency
        if len(currency) == 3:
            return currency

        logging.warning(
            f"invalid operating currency: {currency},"
            + "defaulting to {default_currency}"
        )
        return default_currency

    def _find_envelop_settings(self):
        start_date = None
        budget_accounts = []
        mappings = []
        income_accounts = []
        months_ahead = 0

        for e in self.entries:
            if isinstance(e, Custom) and e.type == self.etype:
                if e.values[0].value == "start date":
                    start_date = e.values[1].value
                if e.values[0].value == "budget account":
                    budget_accounts.append(re.compile(e.values[1].value))
                if e.values[0].value == "mapping":
                    map_set = (
                        re.compile(e.values[1].value),
                        e.values[2].value,
                    )
                    mappings.append(map_set)
                if e.values[0].value == "income account":
                    income_accounts.append(re.compile(e.values[1].value))
                if e.values[0].value == "currency":
                    self.currency = e.values[1].value
                if e.values[0].value == "negative rollover":
                    if e.values[1].value == "allow":
                        self.negative_rollover = True
                if e.values[0].value == "months ahead":
                    months_ahead = int(e.values[1].value)
        return (
            start_date,
            budget_accounts,
            mappings,
            income_accounts,
            months_ahead,
        )

    def envelope_tables(self):
        months = []
        date_current = self.date_start
        while date_current < self.date_end:
            months.append(
                f"{date_current.year}-{str(date_current.month).zfill(2)}"
            )
            month = date_current.month - 1 + 1
            year = date_current.year + month // 12
            month = month % 12 + 1
            date_current = datetime.date(year, month, 1)

        # Create Income DataFrame
        column_index = pd.MultiIndex.from_product([months], names=["Month"])
        self.income_df = pd.DataFrame(columns=months)

        # Create Envelopes DataFrame
        column_index = pd.MultiIndex.from_product(
            [months, ["budgeted", "activity", "available"]],
            names=["Month", "col"],
        )
        self.envelope_df = pd.DataFrame(columns=column_index)
        self.envelope_df.index.name = "Envelopes"

        self._calculate_budget_activity()
        self._calc_budget_budgeted()

        # Calculate Starting Balance Income
        starting_balance = Decimal(0.0)
        query_str = (
            f"select account, convert(sum(position),'{self.currency}')"
            + f" from close on {months[0]}-01 group by 1 order by 1;"
        )
        rows = query.run_query(
            self.entries, self.options_map, query_str, numberify=True
        )
        for row in rows[1]:
            if any(regexp.match(row[0]) for regexp in self.budget_accounts):
                if row[1] is not None:
                    starting_balance += row[1]
        self.income_df[months[0]]["Avail Income"] += starting_balance

        self.envelope_df.fillna(Decimal(0.00), inplace=True)

        # Set available
        for index, row in self.envelope_df.iterrows():
            for index2, month in enumerate(months):
                if index2 == 0:
                    self.envelope_df[month, "available"][index] = (
                        row[month, "budgeted"] + row[month, "activity"]
                    )
                else:
                    prev_available = self.envelope_df[
                        months[index2 - 1], "available"
                    ][index]
                    if prev_available > 0 or self.negative_rollover:
                        self.envelope_df[month, "available"][index] = (
                            prev_available
                            + row[month, "budgeted"]
                            + row[month, "activity"]
                        )
                    else:
                        self.envelope_df[month, "available"][index] = (
                            row[month, "budgeted"] + row[month, "activity"]
                        )

        # Set overspent
        for index, month in enumerate(months):
            if index == 0:
                self.income_df.loc["Overspent", month] = Decimal(0.00)
            else:
                overspent = Decimal(0.00)
                for index2, row in self.envelope_df.iterrows():
                    if row[months[index - 1], "available"] < Decimal(0.00):
                        overspent += Decimal(
                            row[months[index - 1], "available"]
                        )
                self.income_df.loc["Overspent", month] = overspent

        # Set Budgeted for month
        for month in months:
            self.income_df.loc["Budgeted", month] = Decimal(
                -1 * self.envelope_df[month, "budgeted"].sum()
            )

        # Adjust Avail Income
        for index, month in enumerate(months):
            if index == 0:
                continue
            else:
                prev_month = months[index - 1]
                self.income_df.loc["Avail Income", month] = (
                    self.income_df.loc["Avail Income", month]
                    + self.income_df.loc["Avail Income", prev_month]
                    + self.income_df.loc["Overspent", prev_month]
                    + self.income_df.loc["Budgeted", prev_month]
                )

        # Set Budgeted in the future
        for index, month in enumerate(months):
            sum_total = self.income_df[month].sum()
            if (index == len(months) - 1) or sum_total < 0:
                self.income_df.loc["Budgeted Future", month] = Decimal(0.00)
            else:
                next_month = months[index + 1]
                opp_budgeted_next_month = (
                    self.income_df.loc["Budgeted", next_month] * -1
                )
                if opp_budgeted_next_month < sum_total:
                    self.income_df.loc["Budgeted Future", month] = Decimal(
                        -1 * opp_budgeted_next_month
                    )
                else:
                    self.income_df.loc["Budgeted Future", month] = Decimal(
                        -1 * sum_total
                    )

        # Set to be budgeted
        for index, month in enumerate(months):
            self.income_df.loc["To Be Budgeted", month] = Decimal(
                self.income_df[month].sum()
            )

        return self.income_df, self.envelope_df, self.currency

    def _calculate_budget_activity(self):
        # Accumulate expenses for the period
        balances = collections.defaultdict(
            lambda: collections.defaultdict(inventory.Inventory)
        )
        all_months = set()

        for entry in data.filter_txns(self.entries):
            # Check entry in date range
            if entry.date < self.date_start or entry.date > self.date_end:
                continue

            month = (entry.date.year, entry.date.month)
            # TODO domwe handle no transaction in a month?
            all_months.add(month)

            # TODO
            contains_budget_accounts = False
            for posting in entry.postings:
                if any(
                    regexp.match(posting.account)
                    for regexp in self.budget_accounts
                ):
                    contains_budget_accounts = True
                    break

            if not contains_budget_accounts:
                continue

            for posting in entry.postings:
                account = posting.account
                for regexp, target_account in self.mappings:
                    if regexp.match(account):
                        account = target_account
                        break

                account_type = account_types.get_account_type(account)
                if posting.units.currency != self.currency:
                    orig = posting.units.number
                    if posting.price is not None:
                        converted = posting.price.number * orig
                        posting = data.Posting(
                            posting.account,
                            amount.Amount(converted, self.currency),
                            posting.cost,
                            None,
                            posting.flag,
                            posting.meta,
                        )
                    else:
                        continue

                if account_type == self.acctypes.income or (
                    any(
                        regexp.match(account)
                        for regexp in self.income_accounts
                    )
                ):
                    account = "Income"
                elif any(
                    regexp.match(posting.account)
                    for regexp in self.budget_accounts
                ):
                    continue
                # TODO WARn of any assets / liabilities left

                # TODO
                balances[account][month].add_position(posting)

        # Reduce the final balances to numbers
        sbalances = collections.defaultdict(dict)
        for account, months in sorted(balances.items()):
            for month, balance in sorted(months.items()):
                year, mth = month
                date = datetime.date(year, mth, 1)
                balance = balance.reduce(
                    convert.get_value, self.price_map, date
                )
                balance = balance.reduce(
                    convert.convert_position,
                    self.currency,
                    self.price_map,
                    date,
                )
                try:
                    pos = balance.get_only_position()
                except AssertionError:
                    print(balance)
                    raise
                total = pos.units.number if pos and pos.units else None
                sbalances[account][month] = total

        # Pivot the table
        header_months = sorted(all_months)
        # header = ["account"]+["{}-{:02d}".format(*m) for m in header_months]
        self.income_df.loc["Avail Income", :] = Decimal(0.00)

        for account in sorted(sbalances.keys()):
            for month in header_months:
                total = sbalances[account].get(month, None)
                temp = total.quantize(self.Q) if total else 0.00
                # swap sign to be more human readable
                temp *= -1

                month_str = f"{str(month[0])}-{str(month[1]).zfill(2)}"
                if account == "Income":
                    self.income_df.loc["Avail Income", month_str] = Decimal(
                        temp
                    )
                else:
                    self.envelope_df.loc[
                        account, (month_str, "budgeted")
                    ] = Decimal(0.00)
                    self.envelope_df.loc[
                        account, (month_str, "activity")
                    ] = Decimal(temp)
                    self.envelope_df.loc[
                        account, (month_str, "available")
                    ] = Decimal(0.00)

    def _calc_budget_budgeted(self):
        # rows = {}
        for e in self.entries:
            if isinstance(e, Custom) and e.type == self.etype:
                if e.values[0].value == "allocate":
                    month = f"{e.date.year}-{e.date.month:02}"
                    self.envelope_df.loc[
                        e.values[1].value, (month, "budgeted")
                    ] = Decimal(e.values[2].value)
