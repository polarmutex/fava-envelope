from __future__ import annotations

import collections
import datetime
import logging
import re
from dataclasses import dataclass

import polars as pl
from beancount.core import (
    account_types,
    amount,
    convert,
    data,
    inventory,
    prices,
)
from beancount.core.data import Custom
from beancount.core.number import Decimal
from beancount.parser import options
from beanquery import query
from dateutil.relativedelta import relativedelta


@dataclass
class EnvelopeSettings:
    """Configuration extracted from ``custom "envelope"`` directives in a
            beancount file.

    Attributes:
        start_date: First budget month in ``YYYY-MM`` format.
        budget_accounts: Compiled regexes matching accounts whose balance
            defines the total funds available (e.g. ``Assets:Checking``).
        mappings: List of ``(pattern, target)`` pairs that rename accounts
            before bucketing activity (e.g. collapse sub-accounts).
        income_accounts: Compiled regexes for accounts that should be treated
            as income sources even if beancount does not classify them under
            the ``Income`` account type.
        months_ahead: How many months beyond today to extend the budget view.
        currency: Override for the reporting currency; if ``None`` the
            operating currency from ``options_map`` is used.
        negative_rollover: When ``True``, a negative available balance rolls
            forward into the next month instead of being reset to zero.
    """

    start_date: str
    budget_accounts: list
    mappings: list
    income_accounts: list
    months_ahead: int
    currency: str | None = None
    negative_rollover: bool = False


def _find_envelope_settings(entries, etype: str) -> EnvelopeSettings:
    """Scan *entries* for ``Custom`` directives of type *etype* and build an
    :class:`EnvelopeSettings` instance.

    Recognised directive values
    ---------------------------
    ``"start date"``
        Sets the first budget month (``YYYY-MM`` string).
    ``"budget account"``
        Appends a compiled regex to ``budget_accounts``.
    ``"mapping"``
        Appends a ``(pattern, target)`` rename rule to ``mappings``.
    ``"income account"``
        Appends a compiled regex to ``income_accounts``.
    ``"currency"``
        Overrides the reporting currency.
    ``"negative rollover" "allow"``
        Enables carrying a negative available balance forward.
    ``"months ahead"``
        Integer number of future months to include in the view.

    Returns a fully populated :class:`EnvelopeSettings`; fields that were not
    found in *entries* retain their defaults (empty lists / ``None`` / ``0``).
    """
    start_date = None
    budget_accounts = []
    mappings = []
    income_accounts = []
    months_ahead = 0
    currency = None
    negative_rollover = False

    for e in entries:
        if isinstance(e, Custom) and e.type == etype:
            val = e.values[0].value
            if val == "start date":
                start_date = e.values[1].value
            elif val == "budget account":
                budget_accounts.append(re.compile(e.values[1].value))
            elif val == "mapping":
                mappings.append(
                    (re.compile(e.values[1].value), e.values[2].value)
                )
            elif val == "income account":
                income_accounts.append(re.compile(e.values[1].value))
            elif val == "currency":
                currency = e.values[1].value
            elif val == "negative rollover" and e.values[1].value == "allow":
                negative_rollover = True
            elif val == "months ahead":
                months_ahead = int(e.values[1].value)

    return EnvelopeSettings(
        start_date=start_date,
        budget_accounts=budget_accounts,
        mappings=mappings,
        income_accounts=income_accounts,
        months_ahead=months_ahead,
        currency=currency,
        negative_rollover=negative_rollover,
    )


def _find_currency(options_map) -> str:
    """Return the reporting currency from *options_map*.

    Reads ``operating_currency[0]``; falls back to ``"USD"`` if the key is
    absent or the value is not a three-character string, logging a warning in
    the latter case.
    """
    default_currency = "USD"
    opt_currency = options_map.get("operating_currency")
    currency = opt_currency[0] if opt_currency else default_currency
    if len(currency) == 3:
        return currency
    logging.warning(
        f"invalid operating currency: {currency},"
        + f"defaulting to {default_currency}"
    )
    return default_currency


def _convert_posting(posting, currency, price_map):
    """Attempt to convert *posting* to *currency*.

    Conversion is tried in order:
    1. If the posting is already in *currency*, it is returned unchanged.
    2. If a ``price`` annotation is present, the converted amount is computed
       as ``price.number × units.number`` and a new
        :class:`~beancount.core.data.Posting` is returned.
    3. Otherwise ``None`` is returned, signalling that the posting must be
       skipped by the caller.

    Note: *price_map* is accepted for API symmetry but is not currently used;
    future versions may do a full price-map lookup here.
    """
    if posting.units.currency == currency:
        return posting
    if posting.price is not None:
        converted = posting.price.number * posting.units.number
        return data.Posting(
            posting.account,
            amount.Amount(converted, currency),
            posting.cost,
            None,
            posting.flag,
            posting.meta,
        )
    return None


def _build_month_list(
    date_start: datetime.date, date_end: datetime.date
) -> list[str]:
    """Return an ordered list of ``"YYYY-MM"`` strings for every calendar month
    in ``[date_start, date_end)``.

    *date_start* is included; *date_end* is excluded.  Both arguments must be
    the first day of their respective months (only the year/month fields are
    used, but passing non-first-day dates will produce an infinite loop or
    incorrect results).
    """
    months = []
    date_current = date_start
    while date_current < date_end:
        months.append(
            f"{date_current.year}-{str(date_current.month).zfill(2)}"
        )
        month = date_current.month - 1 + 1
        year = date_current.year + month // 12
        month = month % 12 + 1
        date_current = datetime.date(year, month, 1)
    return months


class BeancountEnvelope:
    """Envelope-budget calculator built on top of a beancount ledger.

    This class reads a beancount file (already parsed into *entries* /
    *options_map*) and computes a monthly envelope budget, producing two
    `polars <https://pola.rs>`_ DataFrames:

    **income_df** — wide-format, one row per summary metric:

    ==================  =====================================================
    ``Avail Income``    Funds available at the start of the month (income
                        received + starting balance ± prior-month carry).
    ``Overspent``       Negative available balances from the previous month.
    ``Budgeted``        Total allocated to envelopes this month (negative).
    ``Budgeted Future`` Portion of surplus already committed next month.
    ``To Be Budgeted``  Remaining unallocated funds.
    ==================  =====================================================

    **envelope_df** — wide-format, one row per expense account, columns
    ``{month}_budgeted``, ``{month}_activity``, ``{month}_available`` for
    every month in the date range.

    Configuration is driven entirely by ``custom "envelope" …`` directives
    inside the beancount file; see :func:`_find_envelope_settings` for the
    full list of recognised keys.
    """

    @classmethod
    def from_entries(
        cls,
        entries,
        options_map,
        currency: str | None = None,
        end_date: datetime.date | None = None,
    ) -> BeancountEnvelope:
        instance = cls.__new__(cls)
        instance._init(entries, options_map, currency, end_date)
        return instance

    def __init__(
        self,
        entries,
        options_map,
        currency: str | None = None,
        end_date: datetime.date | None = None,
    ):
        """Initialise the envelope calculator.

        Args:
            entries: Flat list of beancount AST nodes as returned by
                :func:`beancount.loader.load_file` / ``load_string``.
            options_map: Options dict from the same loader call.
            currency: Reporting currency override.  If ``None`` or empty,
                the file's ``operating_currency`` is used.
            end_date: Last date (exclusive) of the budget view.  Defaults to
                today plus ``months_ahead`` months as configured in the file.
        """
        self._init(entries, options_map, currency, end_date)

    def _init(self, entries, options_map, currency, end_date):
        """Shared initialisation logic called by both ``__init__`` and
        :meth:`from_entries`.  Sets all instance attributes; heavy computation
        is deferred to :meth:`envelope_tables`."""
        self.entries = entries
        self.options_map = options_map
        self.currency = currency

        if self.currency:
            self.etype = "envelope" + self.currency
        else:
            self.etype = "envelope"

        settings = _find_envelope_settings(entries, self.etype)
        # Fall back to plain "envelope" if currency-specific etype found nothing
        if settings.start_date is None and self.etype != "envelope":
            settings = _find_envelope_settings(entries, "envelope")
            if settings.start_date is not None:
                self.etype = "envelope"
        self.start_date = settings.start_date
        if self.start_date is None:
            self.date_start = None
            self.date_end = None
            return
        self.budget_accounts = settings.budget_accounts
        self.mappings = settings.mappings
        self.income_accounts = settings.income_accounts
        self.months_ahead = settings.months_ahead
        self.negative_rollover = settings.negative_rollover
        if settings.currency:
            self.currency = settings.currency
        else:
            self.currency = _find_currency(options_map)

        decimal_precison = "0.00"
        self.Q = Decimal(decimal_precison)

        self.date_start = datetime.datetime.strptime(
            self.start_date, "%Y-%m"
        ).date()
        if end_date is not None:
            self.date_end = end_date
        else:
            today = datetime.date.today()
            self.date_end = today + relativedelta(months=+self.months_ahead)

        self.price_map = prices.build_price_map(entries)
        self.acctypes = options.get_account_types(options_map)
        # Internal state initialized lazily in envelope_tables()
        self._income: dict[str, dict[str, Decimal]] = {}
        self._envelopes: dict[str, dict[str, Decimal]] = {}

    def envelope_tables(self):
        """Compute and return the envelope budget tables.

        This is the main public entry point for results.  It orchestrates the
        full calculation pipeline:

        1. :meth:`_calculate_budget_activity` — aggregate income and expense
           postings from the ledger into per-account, per-month totals.
        2. :meth:`_calc_budget_budgeted` — apply ``allocate`` directives to
           set each envelope's budgeted amount.
        3. :meth:`_starting_balance` — query the checking-account balance on
           the first day of the budget to seed month-0 available income.
        4. Derived metrics: available, overspent, budgeted-for-month,
           propagated available income, budgeted-future, to-be-budgeted.
        5. Convert internal dicts to polars DataFrames.

        Returns:
            ``(income_df, envelope_df, currency)`` — see class docstring for
            the schema of each DataFrame.  *currency* is the three-letter
            reporting currency string.

        This method is idempotent: calling it multiple times on the same
        instance resets and recomputes all internal state, returning equal
        DataFrames each time.
        """
        months = _build_month_list(self.date_start, self.date_end)
        self._income: dict[str, dict[str, Decimal]] = {}
        self._envelopes: dict[str, dict[str, Decimal]] = {}

        self._calculate_budget_activity()
        self._calc_budget_budgeted()

        # Ensure all envelope cells exist
        for account in self._envelopes:
            for month in months:
                for col in ("budgeted", "activity", "available"):
                    key = f"{month}_{col}"
                    if key not in self._envelopes[account]:
                        self._envelopes[account][key] = Decimal("0.00")
        # Starting balance
        sb = self._starting_balance(months[0])
        self._income_set(
            "Avail Income",
            months[0],
            self._income_get("Avail Income", months[0]) + sb,
        )
        self._set_available(months)
        self._set_overspent(months)
        self._set_budgeted_for_month(months)
        self._propagate_avail_income(months)
        self._set_budgeted_future(months)
        self._set_to_be_budgeted(months)
        return (
            self._build_income_df(months),
            self._build_envelope_df(months),
            self.currency,
        )

    # ------------------------------------------------------------------
    # Internal helpers for dict-based storage
    # ------------------------------------------------------------------

    def _income_get(self, row: str, month: str) -> Decimal:
        return self._income.get(row, {}).get(month, Decimal("0.00"))

    def _income_set(self, row: str, month: str, value: Decimal):
        if row not in self._income:
            self._income[row] = {}
        self._income[row][month] = value

    def _env_get(self, account: str, month: str, col: str) -> Decimal:
        """Return the envelope value for *account* / *month* / *col*
        (``"budgeted"``, ``"activity"``, or ``"available"``), defaulting to
        ``Decimal("0.00")``."""
        return self._envelopes.get(account, {}).get(
            f"{month}_{col}", Decimal("0.00")
        )

    def _env_set(self, account: str, month: str, col: str, value: Decimal):
        if account not in self._envelopes:
            self._envelopes[account] = {}
        self._envelopes[account][f"{month}_{col}"] = value

    def _build_income_df(self, months: list[str]) -> pl.DataFrame:
        """Convert the internal ``_income`` dict to a polars DataFrame.

        The returned DataFrame has a string column ``"row"`` followed by one
        ``Float64`` column per month in *months*.  Rows appear in canonical
        display order (Avail Income → Overspent → Budgeted → Budgeted Future
        → To Be Budgeted), with any extra rows appended afterwards.
        """
        rows_order = [
            "Avail Income",
            "Overspent",
            "Budgeted",
            "Budgeted Future",
            "To Be Budgeted",
        ]
        data_rows = []
        all_rows = list(self._income.keys())
        # Keep canonical order but include any extra rows
        ordered = [r for r in rows_order if r in all_rows] + [
            r for r in all_rows if r not in rows_order
        ]
        for row_label in ordered:
            record = {"row": row_label}
            for month in months:
                record[month] = float(self._income_get(row_label, month))
            data_rows.append(record)
        return pl.DataFrame(data_rows)

    def _build_envelope_df(self, months: list[str]) -> pl.DataFrame:
        """Convert the internal ``_envelopes`` dict to a polars DataFrame.

        The returned DataFrame has a string column ``"account"`` followed by
        three ``Float64`` columns per month — ``{month}_budgeted``,
        ``{month}_activity``, ``{month}_available`` — for every month in
        *months*.  Accounts are sorted alphabetically.  If no envelopes exist,
        an empty DataFrame with the correct schema is returned.
        """
        col_names = ["account"] + [
            f"{m}_{c}"
            for m in months
            for c in ("budgeted", "activity", "available")
        ]
        data_rows = []
        for account in sorted(self._envelopes.keys()):
            record = {"account": account}
            for month in months:
                for col in ("budgeted", "activity", "available"):
                    record[f"{month}_{col}"] = float(
                        self._env_get(account, month, col)
                    )
            data_rows.append(record)
        return (
            pl.DataFrame(data_rows)
            if data_rows
            else pl.DataFrame(schema={n: pl.Float64 for n in col_names})
        )

    def _calculate_budget_activity(self):
        """Scan all transactions in the budget date range and accumulate
        per-account, per-month activity into ``_income`` and ``_envelopes``.

        Algorithm
        ---------
        For each transaction whose date falls in ``[date_start, date_end)``:

        1. Skip the transaction if none of its postings touch a budget account.
        2. For each posting on a transaction that *does* touch a budget account:

           a. Apply :attr:`mappings` to rename the account (e.g. collapse
              sub-categories).
           b. Convert the posting to :attr:`currency`; skip if impossible.
           c. If the account is an income type (or matches
              :attr:`income_accounts`), bucket it under the synthetic
              ``"Income"`` account.
           d. If the account is itself a budget account, skip it (internal
              transfer).
           e. Otherwise treat it as an expense envelope.

        3. Reduce each accumulated :class:`~beancount.core.inventory.Inventory`
           to a single number in :attr:`currency` via the price map.
        4. Store income totals in ``_income["Avail Income"][month]`` and
           expense totals in ``_envelopes[account][month_activity]``.

        Activity values are negated so that spending shows as negative numbers
        and income shows as positive.
        """
        balances = collections.defaultdict(
            lambda: collections.defaultdict(inventory.Inventory)
        )
        all_months = set()

        for entry in data.filter_txns(self.entries):
            # Check entry in date range
            if entry.date < self.date_start or entry.date >= self.date_end:
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
        self._income_set("Avail Income", "__init__", Decimal("0.00"))

        for account in sorted(sbalances.keys()):
            for month in header_months:
                total = sbalances[account].get(month, None)
                temp = total.quantize(self.Q) if total else 0.00
                temp *= -1

                month_str = f"{str(month[0])}-{str(month[1]).zfill(2)}"
                if account == "Income":
                    self._income_set("Avail Income", month_str, Decimal(temp))
                else:
                    self._env_set(
                        account, month_str, "budgeted", Decimal("0.00")
                    )
                    self._env_set(
                        account, month_str, "activity", Decimal(temp)
                    )
                    self._env_set(
                        account, month_str, "available", Decimal("0.00")
                    )

    def _calc_budget_budgeted(self):
        # rows = {}
        for e in self.entries:
            if isinstance(e, Custom) and e.type == self.etype:
                if e.values[0].value == "allocate":
                    month = f"{e.date.year}-{e.date.month:02}"
                    account = e.values[1].value
                    current = self._env_get(account, month, "budgeted")
                    self._env_set(
                        account,
                        month,
                        "budgeted",
                        current + Decimal(e.values[2].value),
                    )

    def _starting_balance(self, first_month: str) -> Decimal:
        """Query the total balance of all budget accounts on the first day of
        *first_month* and return it as a :class:`~decimal.Decimal`.

        Uses :func:`beanquery.query.run_query` with a ``close on`` clause so
        that all transactions up to (but not including) *first_month* are
        reflected in the balance.  This seeds the ``"Avail Income"`` row for
        month 0 with any pre-existing funds in the tracked accounts.

        Args:
            first_month: A ``"YYYY-MM"`` string; the query closes the books on
                ``{first_month}-01``.

        Returns:
            Sum of all matching account balances converted to
            :attr:`currency`, or ``Decimal(0)`` if no matches are found.
        """
        starting_balance = Decimal(0.0)
        query_str = (
            f"select account, convert(sum(position),'{self.currency}')"
            + f" from close on {first_month}-01 group by 1 order by 1;"
        )
        rows = query.run_query(
            self.entries, self.options_map, query_str, numberify=True
        )
        for row in rows[1]:
            if any(regexp.match(row[0]) for regexp in self.budget_accounts):
                if len(row) > 1 and row[1] is not None:
                    starting_balance += row[1]
        return starting_balance

    def _set_available(self, months):
        """Compute the ``available`` cell for every account and month.

        For month 0: ``available = budgeted + activity``.

        For subsequent months: if the previous month's available balance is
        positive (or :attr:`negative_rollover` is ``True``), carry it forward:
        ``available = prev_available + budgeted + activity``.  Otherwise only
        ``budgeted + activity`` is used, effectively resetting a deficit to
        zero.
        """
        for account in self._envelopes:
            for index2, month in enumerate(months):
                budgeted = self._env_get(account, month, "budgeted")
                activity = self._env_get(account, month, "activity")
                if index2 == 0:
                    self._env_set(
                        account, month, "available", budgeted + activity
                    )
                else:
                    prev_available = self._env_get(
                        account, months[index2 - 1], "available"
                    )
                    if prev_available > 0 or self.negative_rollover:
                        self._env_set(
                            account,
                            month,
                            "available",
                            prev_available + budgeted + activity,
                        )
                    else:
                        self._env_set(
                            account, month, "available", budgeted + activity
                        )

    def _set_overspent(self, months):
        """Populate the ``"Overspent"`` income row for each month.

        For month 0 the value is always ``0``.  For subsequent months it is
        the sum of all *negative* ``available`` balances from the previous
        month across all envelopes, representing money that was spent but
        not budgeted.
        """
        for index, month in enumerate(months):
            if index == 0:
                self._income_set("Overspent", month, Decimal("0.00"))
            else:
                overspent = Decimal(0.00)
                for account in self._envelopes:
                    av = self._env_get(account, months[index - 1], "available")
                    if av < Decimal("0.00"):
                        overspent += av
                self._income_set("Overspent", month, overspent)

    def _set_budgeted_for_month(self, months):
        """Populate the ``"Budgeted"`` income row for each month as the
        negative sum of all envelope ``budgeted`` amounts, so that allocating
        money to envelopes reduces the displayed "available to budget" figure.
        """
        for month in months:
            total = sum(
                self._env_get(a, month, "budgeted") for a in self._envelopes
            )
            self._income_set("Budgeted", month, Decimal(-1) * total)

    def _propagate_avail_income(self, months):
        """Roll the available-income figure forward from one month to the next.

        Starting from month 1, each month's ``"Avail Income"`` is updated to:

        ``avail[m] += avail[m-1] + overspent[m-1] + budgeted[m-1]``

        This reflects that unspent / unallocated funds from a prior month
        carry into the current month's pool.  Month 0 is left as set by
        :meth:`_calculate_budget_activity` plus the starting balance.
        """
        for index, month in enumerate(months):
            if index == 0:
                continue
            prev_month = months[index - 1]
            new_val = (
                self._income_get("Avail Income", month)
                + self._income_get("Avail Income", prev_month)
                + self._income_get("Overspent", prev_month)
                + self._income_get("Budgeted", prev_month)
            )
            self._income_set("Avail Income", month, new_val)

    def _set_budgeted_future(self, months):
        """Populate the ``"Budgeted Future"`` income row.

        For each month, if there is a surplus (sum of all income rows > 0) and
        a next month exists, ``"Budgeted Future"`` is set to the *lesser* of:

        * the total budgeted in the *next* month (i.e. what is already
          committed), or
        * the current surplus.

        The value is stored as a negative number so it reduces the displayed
        "To Be Budgeted" total.  If the current month is the last one, or if
        the sum is already negative, ``"Budgeted Future"`` is set to zero.
        """
        for index, month in enumerate(months):
            sum_total = sum(self._income_get(r, month) for r in self._income)
            if (index == len(months) - 1) or sum_total < 0:
                self._income_set("Budgeted Future", month, Decimal("0.00"))
            else:
                next_month = months[index + 1]
                opp_budgeted_next_month = (
                    self._income_get("Budgeted", next_month) * -1
                )
                if opp_budgeted_next_month < sum_total:
                    self._income_set(
                        "Budgeted Future",
                        month,
                        Decimal(-1) * opp_budgeted_next_month,
                    )
                else:
                    self._income_set(
                        "Budgeted Future", month, Decimal(-1) * sum_total
                    )

    def _set_to_be_budgeted(self, months):
        """Populate the ``"To Be Budgeted"`` income row for each month as the
        sum of *all* income-table rows for that month, giving the net
        unallocated funds remaining after accounting for income, overspending,
        budgeted amounts, and future commitments.
        """
        for month in months:
            total = sum(self._income_get(r, month) for r in self._income)
            self._income_set("To Be Budgeted", month, total)
