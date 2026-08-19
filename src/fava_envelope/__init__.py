from __future__ import annotations

from dataclasses import dataclass

import polars as pl
from fava.ext import FavaExtensionBase
from fava.helpers import FavaAPIError

from .modules.beancount_envelope import BeancountEnvelope


@dataclass(frozen=True)
class BudgetCtx:
    months: list[str]
    income_df: pl.DataFrame
    envelope_df: pl.DataFrame
    currency: str


class EnvelopeBudget(FavaExtensionBase):
    report_title = "Envelope Budget"

    def after_load_file(self) -> None:
        module = BeancountEnvelope(
            self.ledger.all_entries,
            self.ledger.options,
        )
        if module.start_date is None:
            self._budget: BudgetCtx | None = None
            return
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
        return self._require_budget().months

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
