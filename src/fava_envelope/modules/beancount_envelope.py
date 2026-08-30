from __future__ import annotations

import collections
import datetime
import logging
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
from dateutil.relativedelta import relativedelta


@dataclass
class EnvelopeSettings:
    """Configuration extracted from ``fava-extension "fava_envelope"`` directives in a
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

    Structural configuration is provided via :class:`EnvelopeSettings` (parsed
    from the fava-extension config block).  Budget allocations are read from
    ``custom "envelope" "allocate" …`` directives in the journal.
    """

    def __init__(
        self,
        entries,
        options_map,
        currency: str | None = None,
        end_date: datetime.date | None = None,
        settings: EnvelopeSettings | None = None,
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
            settings: Pre-parsed :class:`EnvelopeSettings` from the fava
                extension config block.  If provided, structural config
                (start date, budget accounts, etc.) is taken from here and
                journal ``custom "envelope"`` directives are only scanned for
                ``allocate``.  If ``None``, structural config is read from
                the journal directives (legacy / standalone behaviour).
        """
        self.entries = entries
        self.options_map = options_map
        self.currency = currency

        if settings is None:
            raise ValueError(
                "EnvelopeSettings must be provided. Structural envelope "
                "configuration is read from the fava-extension config block, "
                "not from journal custom directives."
            )

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
        elif currency:
            self.currency = currency
        else:
            self.currency = _find_currency(options_map)

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

    def _starting_balance(self, first_month: str) -> Decimal:
        """Return the balance of all budget accounts on the first day of *first_month*.

        This represents funds already present before the budget period begins.
        """
        year, mth = (int(p) for p in first_month.split("-"))
        cutoff = datetime.date(year, mth, 1)
        bal = inventory.Inventory()
        for entry in data.filter_txns(self.entries):
            if entry.date >= cutoff:
                continue
            for posting in entry.postings:
                if any(r.match(posting.account) for r in self.budget_accounts):
                    p = _convert_posting(
                        posting, self.currency, self.price_map
                    )
                    if p is not None:
                        bal.add_position(p)
        bal = bal.reduce(convert.get_value, self.price_map, cutoff)
        bal = bal.reduce(
            convert.convert_position, self.currency, self.price_map, cutoff
        )
        pos = bal.get_only_position()
        total = pos.units.number if pos and pos.units else Decimal(0)
        return total.quantize(Decimal("0.00"))

    def envelope_tables(self):

        months = _build_month_list(self.date_start, self.date_end)

        budgeted = self._collect_budgeted()  # {account: {month_str: Decimal}}
        activity, income = self._collect_activity_and_income()
        budgeted = self._collect_budgeted()  # {account: {month_str: Decimal}}
        starting = self._starting_balance(months[0])

        envelope_df = self._compute_envelopes(months, activity, budgeted)
        income_df = self._compute_income(months, income, starting, envelope_df)

        return income_df, envelope_df, self.currency

    # ------------------------------------------------------------------
    # Data collection: read entries, return plain dicts. No mutation of self.
    # ------------------------------------------------------------------

    def _collect_activity_and_income(
        self,
    ) -> tuple[dict[str, dict[str, Decimal]], dict[str, Decimal]]:
        """Single-pass collection of expense activity and income.

        Returns:
            activity: {account: {month_str: Decimal}} — expense postings,
                negated so spending is negative.
            income:   {month_str: Decimal} — income totals, negated so
                cash-in is positive.
        """
        activity_bal: dict[str, dict[tuple, inventory.Inventory]] = (
            collections.defaultdict(
                lambda: collections.defaultdict(inventory.Inventory)
            )
        )
        income_bal: dict[tuple, inventory.Inventory] = collections.defaultdict(
            inventory.Inventory
        )

        for entry in data.filter_txns(self.entries):
            if entry.date < self.date_start or entry.date >= self.date_end:
                continue
            month = (entry.date.year, entry.date.month)
            if not any(
                r.match(p.account)
                for r in self.budget_accounts
                for p in entry.postings
            ):
                continue
            for posting in entry.postings:
                account = self._apply_mappings(posting.account)
                converted = _convert_posting(
                    posting, self.currency, self.price_map
                )
                if converted is None:
                    continue
                account_type = account_types.get_account_type(account)
                is_income = account_type == self.acctypes.income or any(
                    r.match(account) for r in self.income_accounts
                )
                is_budget = any(
                    r.match(posting.account) for r in self.budget_accounts
                )
                if is_income:
                    income_bal[month].add_position(converted)
                elif not is_budget:
                    activity_bal[account][month].add_position(converted)

        # Reduce income inventories to scalar Decimals
        income: dict[str, Decimal] = {}
        for month, bal in sorted(income_bal.items()):
            year, mth = month
            date = datetime.date(year, mth, 1)
            bal = bal.reduce(convert.get_value, self.price_map, date)
            bal = bal.reduce(
                convert.convert_position, self.currency, self.price_map, date
            )
            pos = bal.get_only_position()
            total = pos.units.number if pos and pos.units else Decimal(0)
            month_str = f"{year}-{mth:02}"
            income[month_str] = (-total).quantize(Decimal("0.00"))

        return self._reduce_balances(activity_bal), income

    def _collect_budgeted(self) -> dict[str, dict[str, Decimal]]:
        """Return {account: {month_str: Decimal}} from 'allocate' directives."""
        budgeted: dict[str, dict[str, Decimal]] = collections.defaultdict(
            lambda: collections.defaultdict(Decimal)
        )
        for e in self.entries:
            if isinstance(e, Custom) and e.type == "envelope":
                if len(e.values) != 3 or e.values[0].value != "allocate":
                    raise AssertionError(
                        f"Bad envelope directive: {e}\n"
                        'Expected: YYYY-MM-DD custom "envelope" "allocate" '
                        '"Expenses:X" 10.00 EUR'
                    )
                month_str = f"{e.date.year}-{e.date.month:02}"
                account = e.values[1].value
                budgeted[account][month_str] += Decimal(e.values[2].value)
        return dict(budgeted)

    def _reduce_balances(
        self, balances: dict[str, dict[tuple, inventory.Inventory]]
    ) -> dict[str, dict[str, Decimal]]:
        result: dict[str, dict[str, Decimal]] = {}
        for account, months in sorted(balances.items()):
            result[account] = {}
            for month, bal in sorted(months.items()):
                year, mth = month
                date = datetime.date(year, mth, 1)
                bal = bal.reduce(convert.get_value, self.price_map, date)
                bal = bal.reduce(
                    convert.convert_position,
                    self.currency,
                    self.price_map,
                    date,
                )
                pos = bal.get_only_position()
                total = pos.units.number if pos and pos.units else Decimal(0)
                month_str = f"{year}-{mth:02}"
                result[account][month_str] = (-total).quantize(Decimal("0.00"))
        return result

    def _apply_mappings(self, account: str) -> str:
        for regexp, target in self.mappings:
            if regexp.match(account):
                return target
        return account

    # ------------------------------------------------------------------
    # Computation: pure math over the collected data. Returns DataFrames.
    # ------------------------------------------------------------------

    def _compute_envelopes(
        self,
        months: list[str],
        activity: dict[str, dict[str, Decimal]],
        budgeted: dict[str, dict[str, Decimal]],
    ) -> pl.DataFrame:
        """Compute budgeted / activity / available for every envelope × month.

        available[m] = budgeted[m] + activity[m] + carry[m-1]
        carry[m]     = available[m]  (if negative_rollover)
                     = max(0, available[m])  (otherwise)
        """
        q = Decimal("0.00")
        zero = Decimal(0)
        all_accounts = sorted(set(activity) | set(budgeted))
        rows = []
        for account in all_accounts:
            row = {"account": account}
            carry = zero
            for month in months:
                b = budgeted.get(account, {}).get(month, zero)
                a = activity.get(account, {}).get(month, zero)
                avail = (carry + b + a).quantize(q)
                row[f"{month}_budgeted"] = float(b)
                row[f"{month}_activity"] = float(a)
                row[f"{month}_available"] = float(avail)
                carry = avail if self.negative_rollover else max(zero, avail)
            rows.append(row)

        col_names = ["account"] + [
            f"{m}_{c}"
            for m in months
            for c in ("budgeted", "activity", "available")
        ]
        return (
            pl.DataFrame(rows)
            if rows
            else pl.DataFrame(schema={n: pl.Float64 for n in col_names})
        )

    def _compute_income(
        self,
        months: list[str],
        income: dict[str, Decimal],
        starting_balance: Decimal,
        envelope_df: pl.DataFrame,
    ) -> pl.DataFrame:
        """Compute the income summary table.

        avail[m]  = income[m] + starting (month 0 only)
                  + avail[m-1] + overspent[m-1] + budgeted_total[m-1]
        overspent[m]       = sum(min(0, available[a, m-1]) for a in envelopes)
        budgeted_total[m]  = -sum(budgeted[a, m] for a in envelopes)
        budgeted_future[m] = min allocated next month vs current surplus
        tbb[m]             = avail[m] + overspent[m] + budgeted_total[m]
                                      + budgeted_future[m]
        """
        q = Decimal("0.00")
        zero = Decimal(0)

        def env_col(month: str, col: str) -> list[float]:
            c = f"{month}_{col}"
            return envelope_df[c].to_list() if c in envelope_df.columns else []

        # Pre-compute per-month envelope aggregates from the already-built DataFrame
        overspent_row: dict[str, Decimal] = {}
        budgeted_total_row: dict[str, Decimal] = {}
        for month in months:
            overspent_row[month] = sum(
                (
                    Decimal(str(v))
                    for v in env_col(month, "available")
                    if v < 0
                ),
                zero,
            ).quantize(q)
            budgeted_total_row[month] = (
                -sum(
                    (Decimal(str(v)) for v in env_col(month, "budgeted")), zero
                )
            ).quantize(q)

        avail_row: dict[str, Decimal] = {}
        for i, month in enumerate(months):
            base = income.get(month, zero)
            if i == 0:
                base += starting_balance
                avail_row[month] = base.quantize(q)
            else:
                prev = months[i - 1]
                avail_row[month] = (
                    base
                    + avail_row[prev]
                    + overspent_row[prev]
                    + budgeted_total_row[prev]
                ).quantize(q)

        # Note: overspent for month 0 is always 0 (no prior month)
        overspent_row[months[0]] = zero

        budgeted_future_row: dict[str, Decimal] = {}
        for i, month in enumerate(months):
            surplus = (
                avail_row[month]
                + overspent_row[month]
                + budgeted_total_row[month]
            )
            if i == len(months) - 1 or surplus <= zero:
                budgeted_future_row[month] = zero
            else:
                next_allocated = -budgeted_total_row[months[i + 1]]
                budgeted_future_row[month] = -min(next_allocated, surplus)

        tbb_row: dict[str, Decimal] = {
            month: (
                avail_row[month]
                + overspent_row[month]
                + budgeted_total_row[month]
                + budgeted_future_row[month]
            ).quantize(q)
            for month in months
        }

        rows = [
            {
                "row": "Avail Income",
                **{m: float(avail_row[m]) for m in months},
            },
            {
                "row": "Overspent",
                **{m: float(overspent_row[m]) for m in months},
            },
            {
                "row": "Budgeted",
                **{m: float(budgeted_total_row[m]) for m in months},
            },
            {
                "row": "Budgeted Future",
                **{m: float(budgeted_future_row[m]) for m in months},
            },
            {
                "row": "To Be Budgeted",
                **{m: float(tbb_row[m]) for m in months},
            },
        ]
        return pl.DataFrame(rows)
