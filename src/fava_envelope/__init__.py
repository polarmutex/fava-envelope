# from beancount.core.number import Decimal
# from fava import __version__ as fava_version
# from fava.context import g
from fava.ext import FavaExtensionBase
import pandas as pd
from collections import namedtuple, defaultdict
from beancount.core import inventory, data, account_types, amount, convert
from beancount.parser import options
from beancount.query import query
import datetime
import re
from typing import Dict, List, Tuple
from decimal import Decimal
from dataclasses import dataclass
from fava.helpers import FavaAPIError

# from .modules.beancount_envelope import BeancountEnvelope

ExtensionConfig = namedtuple("ExtensionConfig", ["budgets"])
BudgetConfig = namedtuple(
    "BudgetConfig",
    [
        "name",
        "start_date",
        "end_date",
        "budget_accounts",
        "mappings",
        "income_accounts",
        "currency",
    ],
)
Account = str
Month = int
Year = int
MonthTuple = Tuple[Year, Month]


@dataclass(frozen=True)
class BudgetCtx:
    months: List[str]
    top: pd.DataFrame
    envelopes: pd.DataFrame


class EnvelopeBudget(FavaExtensionBase):
    report_title = "Envelope Budget"

    # config is only loaded on fava start and will not be reloaed on file change
    def read_extension_config(self) -> ExtensionConfig:
        cfg = self.config if isinstance(self.config, dict) else {}

        procesed_config: ExtensionConfig = ExtensionConfig(budgets=[])

        for b in cfg.get("budgets", []):
            start_date_str = b.get("start date", "2000-01")  # TODO
            start_date = datetime.datetime.strptime(start_date_str, "%Y-%m").date()

            today = datetime.date.today()
            end_date = datetime.date(today.year, today.month, today.day)

            processed_budget_accounts = []
            for ba in b.get("budget accounts", ["Assets:*"]):
                processed_budget_accounts.append(re.compile(ba))

            processed_mappings = []
            for m in b.get("mappings", []):
                map_set = (re.compile(m.get("from")), m.get("to"))
                processed_mappings.append(map_set)

            processed_budget = BudgetConfig(
                name=b.get("name", ""),
                start_date=start_date,
                end_date=end_date,
                budget_accounts=processed_budget_accounts,
                mappings=processed_mappings,
                income_accounts=b.get("inc account", ""),  # TODO
                currency=b.get("currency", "USD"),  # TODO
            )
            procesed_config.budgets.append(processed_budget)

        return procesed_config

    def after_load_file(self) -> None:
        self.extension_config = self.read_extension_config()

        self.budgets = []

        for budget in self.extension_config.budgets:
            print(f"processiing budget {budget}")
            bc = self.process_budget(budget)
            self.budgets.append(bc)
        print(self.budgets[0].top)
        print(self.budgets[0].envelopes)

    def process_budget(self, cfg: BudgetConfig) -> BudgetCtx:
        months = []
        cur = cfg.start_date
        end = cfg.end_date
        while cur < end:
            months.append(f"{cur.year}-{str(cur.month).zfill(2)}")
            month = cur.month - 1 + 1
            year = cur.year + month // 12
            month = month % 12 + 1
            cur = datetime.date(year, month, 1)

        activity = self.calc_budget_accconut_activity(cfg)
        envelope_df = self.build_envelope_df(months, activity)
        top_df = self.build_top_df(cfg, months, activity)

        # Set available
        for index, row in envelope_df.iterrows():
            for index2, month in enumerate(months):
                if index2 == 0:
                    row[month, "available"] = (
                        row[month, "budgeted"] + row[month, "activity"]
                    )
                else:
                    prev_available = row[months[index2 - 1], "available"]
                    if prev_available > 0:
                        row[month, "available"] = (
                            prev_available
                            + row[month, "budgeted"]
                            + row[month, "activity"]
                        )
                    else:
                        row[month, "available"] = (
                            row[month, "budgeted"] + row[month, "activity"]
                        )
        # Set overspent
        for index, month in enumerate(months):
            if index == 0:
                top_df.loc["Overspent", month] = Decimal(0.00)
            else:
                overspent = Decimal(0.00)
                for index2, row in envelope_df.iterrows():
                    if row[months[index - 1], "available"] < Decimal(0.00):
                        overspent += Decimal(row[months[index - 1], "available"])
                top_df.loc["Overspent", month] = overspent

        # Set Budgeted for month
        for month in months:
            top_df.loc["Budgeted", month] = Decimal(
                -1 * envelope_df[month, "budgeted"].sum()
            )

        # Adjust Avail Income
        for index, month in enumerate(months):
            if index == 0:
                continue
            else:
                prev_month = months[index - 1]
                top_df.loc["Avail Income", month] = (
                    top_df.loc["Avail Income", month]
                    + top_df.loc["Avail Income", prev_month]
                    + top_df.loc["Overspent", prev_month]
                    + top_df.loc["Budgeted", prev_month]
                )

        # Set Budgeted in the future
        for index, month in enumerate(months):
            sum_total = top_df[month].sum()
            if (index == len(months) - 1) or sum_total < 0:
                top_df.loc["Budgeted Future", month] = Decimal(0.00)
            else:
                next_month = months[index + 1]
                opp_budgeted_next_month = top_df.loc["Budgeted", next_month] * -1
                if opp_budgeted_next_month < sum_total:
                    top_df.loc["Budgeted Future", month] = Decimal(
                        -1 * opp_budgeted_next_month
                    )
                else:
                    top_df.loc["Budgeted Future", month] = Decimal(-1 * sum_total)

        # Set to be budgeted
        for index, month in enumerate(months):
            top_df.loc["To Be Budgeted", month] = Decimal(top_df[month].sum())

        return BudgetCtx(months=months, top=top_df, envelopes=envelope_df)

    def bootstrap(self, id: int, month: Month):
        if not 0 <= id < len(self.budgets):
            raise FavaAPIError(f"invalid dashboard ID: {id}, maybe no budgets defined")
        return {
            "budgets": self.extension_config.budgets,
            "months": self.budgets[id].months,
            "top": self.generate_income_query_tables(self.budgets[id].top, month),
            "envelopes": self.generate_envelope_query_tables(
                self.budgets[id].envelopes, month
            ),
        }

    def build_top_df(self, cfg, months, balances) -> pd.DataFrame:
        df = pd.DataFrame(columns=months)

        # Calculate Starting Balance Income
        starting_balance = Decimal(0.0)
        query_str = f"select account, convert(sum(position),'{cfg.currency}') from close on {months[0]}-01 group by 1 order by 1;"
        rows = query.run_query(
            self.ledger.all_entries, self.ledger.options, query_str, numberify=True
        )
        for row in rows[1]:
            if any(regexp.match(row[0]) for regexp in cfg.budget_accounts):
                if row[1] is not None:
                    starting_balance += row[1]
        print(starting_balance)

        df.loc["Avail Income", months[0]] = starting_balance

        df = df.fillna(Decimal(0.00))

        print(df)

        for account in balances.keys():
            if account != "Income":
                continue
            for month in balances[account]:
                month_str = f"{str(month[0])}-{str(month[1]).zfill(2)}"
                total = balances[account].get(month) * -1
                df.loc["Avail Income", month_str] = Decimal(total)

        print(df)

        return df

    def build_envelope_df(self, months, balances) -> pd.DataFrame:
        column_index = pd.MultiIndex.from_product(
            [months, ["budgeted", "activity", "available"]], names=["Month", "col"]
        )
        df = pd.DataFrame(columns=column_index)
        df.index.name = "Envelopes"

        for account in balances.keys():
            if account == "Income":
                continue
            for month in balances[account]:
                month_str = f"{str(month[0])}-{str(month[1]).zfill(2)}"
                total = balances[account].get(month) * -1
                df.loc[account, (month_str, "activity")] = amount.Decimal(total)

        df = df.fillna(Decimal(0.00))

        # Set available
        for index, row in df.iterrows():
            for index2, month in enumerate(months):
                if index2 == 0:
                    row[month, "available"] = (
                        row[month, "budgeted"] + row[month, "activity"]
                    )
                else:
                    prev_available = row[months[index2 - 1], "available"]
                    if prev_available > 0:
                        row[month, "available"] = (
                            prev_available
                            + row[month, "budgeted"]
                            + row[month, "activity"]
                        )
                    else:
                        row[month, "available"] = (
                            row[month, "budgeted"] + row[month, "activity"]
                        )
        return df

    def calc_budget_accconut_activity(
        self, cfg
    ) -> Dict[Account, Dict[MonthTuple, amount.Decimal]]:
        acctypes = options.get_account_types(self.ledger.options)

        balances = defaultdict(lambda: defaultdict(inventory.Inventory))
        for entry in data.filter_txns(self.ledger.all_entries):
            # Check entry in date range
            if entry.date < cfg.start_date or entry.date > cfg.end_date:
                continue
            month = (entry.date.year, entry.date.month)

            contains_budget_accounts = False
            for posting in entry.postings:
                if any(regexp.match(posting.account) for regexp in cfg.budget_accounts):
                    contains_budget_accounts = True
                    break
            if not contains_budget_accounts:
                continue

            for posting in entry.postings:
                account = posting.account
                for regexp, target_account in cfg.mappings:
                    if regexp.match(account):
                        account = target_account
                        break
                account_type = account_types.get_account_type(account)
                if posting.units.currency != cfg.currency:
                    orig = posting.units.number
                    if posting.price is not None:
                        converted = posting.price.number * orig
                        posting = data.Posting(
                            posting.account,
                            amount.Amount(converted, cfg.currency),
                            posting.cost,
                            None,
                            posting.flag,
                            posting.meta,
                        )
                    else:
                        continue

                if account_type == acctypes.income or (
                    any(regexp.match(account) for regexp in cfg.income_accounts)
                ):
                    account = "Income"
                elif any(
                    regexp.match(posting.account) for regexp in cfg.budget_accounts
                ):
                    continue

                balances[account][month].add_position(posting)

        # Reduce the final balances to numbers
        sbalances: Dict[Account, Dict[MonthTuple, amount.Decimal]] = defaultdict(dict)
        for account, months in sorted(balances.items()):
            for month, balance in sorted(months.items()):
                year, mth = month
                date = datetime.date(year, mth, 1)
                balance = balance.reduce(convert.get_value, self.ledger.prices, date)
                balance = balance.reduce(
                    convert.convert_position, cfg.currency, self.ledger.prices, date
                )
                try:
                    pos = balance.get_only_position()
                except AssertionError:
                    raise
                total = pos.units.number if pos and pos.units else amount.Decimal(0)
                sbalances[account][month] = total

        return sbalances

    # def get_currencies(self):
    #     if "currencies" in self.config:
    #         return self.config["currencies"]
    #     else:
    #         return None

    # def check_month_in_available_months(self, month, currency):
    #     if month:
    #         if month in self.get_budgets_months_available(currency):
    #             return True
    #     return False

    # def generate_budget_df(self, currency):
    #     self.currency = currency
    #     module = BeancountEnvelope(
    #         g.ledger.all_entries, self.ledger.options, self.currency
    #     )
    #     (
    #         self.income_tables,
    #         self.envelope_tables,
    #         self.currency,
    #     ) = module.envelope_tables()

    def get_budget_months(self, id: int):
        if not 0 <= id < len(self.budgets):
            raise FavaAPIError(f"invalid dashboard ID: {id}, maybe no budgets defined")
        return self.budgets[id].months

    def generate_income_query_tables(self, df, month):
        income_table_types = []
        income_table_types.append(("Name", str(str)))
        income_table_types.append(("Amount", str(Decimal)))

        income_table_rows = []

        if month is not None:
            income_table_rows.append(
                {
                    "Name": "Funds for month",
                    "Amount": df.loc["Avail Income", month],
                }
            )
            income_table_rows.append(
                {
                    "Name": "Overspent in prev month",
                    "Amount": df.loc["Overspent", month],
                }
            )
            income_table_rows.append(
                {
                    "Name": "Budgeted for month",
                    "Amount": df.loc["Budgeted", month],
                }
            )
            income_table_rows.append(
                {
                    "Name": "To be budgeted for month",
                    "Amount": df.loc["To Be Budgeted", month],
                }
            )
            income_table_rows.append(
                {
                    "Name": "Budgeted in the future",
                    "Amount": df.loc["Budgeted Future", month],
                }
            )

        return income_table_types, income_table_rows

    def generate_envelope_query_tables(self, df, month):
        envelope_table_types = []
        envelope_table_types.append(("Account", str(str)))
        envelope_table_types.append(("Budgeted", str(Decimal)))
        envelope_table_types.append(("Activity", str(Decimal)))
        envelope_table_types.append(("Available", str(Decimal)))

        envelope_table_rows = []

        if month is not None:
            for index, e_row in df.iterrows():
                row = {}
                row["Account"] = index
                row["Budgeted"] = e_row[month, "budgeted"]
                row["Activity"] = e_row[month, "activity"]
                row["Available"] = e_row[month, "available"]
                envelope_table_rows.append(row)

        return envelope_table_types, envelope_table_rows
