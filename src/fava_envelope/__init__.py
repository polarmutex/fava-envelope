from __future__ import annotations

import datetime
import re
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import chain
from typing import Any

import polars as pl
from fava.ext import FavaExtensionBase
from fava.helpers import FavaAPIError

from .modules.beancount_envelope import BeancountEnvelope, EnvelopeSettings


def flatten(ible: Iterable[Any]) -> list[Any]:
    return list(chain.from_iterable(ible))


@dataclass(frozen=True)
class BudgetCtx:
    months: list[str]
    income_df: pl.DataFrame
    envelope_df: pl.DataFrame
    currency: str


class EnvelopeBudget(FavaExtensionBase):
    report_title = "Envelope Budget"
    _buget: BudgetCtx | None = None

    def _read_settings_from_config(self) -> EnvelopeSettings | None:
        """Parse structural envelope config from the fava extension config block.

        Expects self.config to be a dict with keys:
          - 'start date' (required)
          - 'budget accounts' (list of regex strings)
          - 'mappings' (list of [from, to] pairs)
          - 'income accounts' (list of regex strings)
          - 'currency' (string)
          - 'months ahead' (int)
          - 'negative rollover' (bool)
        """
        cfg = self.config if isinstance(self.config, dict) else {}
        start_date = cfg.get("start date")
        budgets = cfg.get("budgets", [])
        if not budgets:
            # Fall back to flat config as a single budget
            budgets = [cfg] if cfg.get("start date") else []

        if not budgets:
            raise FavaAPIError(
                "The envelope budget requires at least one budget account."
            )
        start_dates: list[str] = [bgt.get("start date") for bgt in budgets]
        if not start_dates:
            raise FavaAPIError(
                "The envelope budget requires at least one budget with a start date."
            )
        if not start_date:
            start_date = min(start_dates)
            if not start_date:
                raise FavaAPIError(
                    """The envelope budget requires at least \
                    a single budget account with a start date."""
                )

        currency = cfg.get("currency")
        budget_accounts = []
        mappings = []
        income_accounts = []
        for budget in cfg.get("budgets", []):
            budget_accounts += [
                re.compile(p) for p in budget.get("budget accounts", [])
            ]
            mappings += [
                (re.compile(x), y)
                for [x, y] in budget.get("mappings", budget.get("mapping", []))
            ]
            income_accounts += [
                re.compile(p) for p in budget.get("income accounts", [])
            ]
            if currency is None:
                currency = budget.get("currency") or None

        return EnvelopeSettings(
            start_date=start_date,
            budget_accounts=budget_accounts,
            mappings=mappings,
            income_accounts=income_accounts,
            months_ahead=int(cfg.get("months ahead", 0)),
            currency=cfg.get("currency") or None,
            negative_rollover=bool(cfg.get("negative rollover", False)),
        )

    def after_load_file(self) -> None:
        settings = self._read_settings_from_config()
        if settings is None:
            self._budget: BudgetCtx | None = None
            return
        module = BeancountEnvelope(
            self.ledger.all_entries,
            self.ledger.options,
            settings=settings,
        )
        income_df, envelope_df, currency = module.envelope_tables()
        months = list(income_df.columns[1:])  # drop 'row'
        self._budget = BudgetCtx(
            months=months,
            income_df=income_df,
            envelope_df=envelope_df,
            currency=currency,
        )

    def _require_budget(self) -> BudgetCtx:
        if self._budget is None:
            raise FavaAPIError(
                "No envelope budget configured in your beancount file."
            )
        return self._budget

    def bootstrap(self, month: str | None = None) -> dict:
        budget = self._require_budget()
        return {
            "months": budget.months,
            "currency": budget.currency,
            "top": self._income_table_rows(budget, month),
            "envelopes": self._envelope_table_rows(budget, month),
        }

    def get_budget_months(self) -> list[str]:
        try:
            return self._require_budget().months
        except FavaAPIError:
            return [str(datetime.date.today().month)]

    def _income_table_rows(
        self, budget: BudgetCtx, month: str | None
    ) -> list[dict]:
        if month is None:
            return []
        df = budget.income_df
        rows = []
        label_map = [
            ("Avail Income", "Funds for month"),
            ("Overspent", "Overspent in prev month"),
            ("Budgeted", "Budgeted for month"),
            ("Budgeted Future", "Budgeted in the future"),
            ("To Be Budgeted", "To be budgeted for month"),
        ]
        for key, label in label_map:
            filtered = df.filter(pl.col("row") == key)
            amount = filtered[month][0] if len(filtered) > 0 else 0.0
            rows.append({"Name": label, "Amount": amount})
        return rows

    def _envelope_table_rows(
        self, budget: BudgetCtx, month: str | None
    ) -> list[dict]:
        if month is None:
            return []
        df = budget.envelope_df
        return [
            {
                "Account": row["account"],
                "Budgeted": row[f"{month}_budgeted"],
                "Activity": row[f"{month}_activity"],
                "Available": row[f"{month}_available"],
            }
            for row in df.to_dicts()
        ]
