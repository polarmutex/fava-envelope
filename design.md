# Envelope Budget Extension for Fava/Beancount

## Overview

This extension adds envelope-style budgeting to [Fava](https://beancount.github.io/fava/), the web interface for [Beancount](https://beancount.github.io/). It works entirely as a reporting layer — no automatic transactions are generated, and your journal is never modified. Budget allocations are expressed as `custom` directives inside your `.beancount` file.

## Reference

- [Beancount Envelope Budgeting Discussion](https://groups.google.com/forum/m/#!msg/beancount/kQMPTY5Q4ko/49hbQdyKCgAJ)
- [Fava feature request](https://github.com/beancount/fava/issues/909)
- [You Need A Budget methodology](https://www.youneedabudget.com/the-four-rules/)

---

## How It Works

Each month, the extension:

1. Reads the balance of your designated budget accounts (e.g. `Assets:Checking`) to determine how much money is available.
2. Reads `allocate` directives to see how much you have assigned to each spending envelope.
3. Reads actual transactions to compute activity against each envelope.
4. Derives available balances, carries rollovers forward, and surfaces "To Be Budgeted" — the unallocated remainder.

The output is two tables displayed in Fava:

- **Income table** — where your money came from and how it was allocated.
- **Envelope table** — per-account budgeted, activity, and available balances for each month.

---

## Configuration

All configuration lives in your `.beancount` file as `custom "envelope"` directives.

### Minimal Setup

``` beancount
2024-01-01 custom "envelope" "start date" "2024-01"
2024-01-01 custom "envelope" "budget account" "Assets:Checking"
```

### Full Reference

| Directive | Example | Description |
|---|---|---|
| `start date` | `"2024-01"` | First month of the budget. Required. |
| `budget account` | `"Assets:Checking"` | Regex matching accounts whose balance counts as available funds. Repeat for multiple accounts. |
| `allocate` | `"Expenses:Food" 300.00` | Assign money to an envelope for the month of the directive's date. |
| `mapping` | `"Expenses:Food:.*" "Expenses:Food"` | Collapse sub-accounts into a single envelope. |
| `income account` | `"Income:Freelance"` | Treat a non-standard account as income. Usually not needed — beancount `Income:` accounts are detected automatically. |
| `currency` | `"EUR"` | Override the reporting currency (defaults to `operating_currency`). |
| `months ahead` | `"3"` | How many months beyond today to show in the budget view. |
| `negative rollover` `"allow"` | — | Carry a negative envelope balance forward into the next month instead of resetting to zero. |

### Example

``` beancount
2024-01-01 custom "envelope" "start date" "2024-01"
2024-01-01 custom "envelope" "budget account" "Assets:Checking"
2024-01-01 custom "envelope" "budget account" "Assets:Savings"
2024-01-01 custom "envelope" "mapping" "Expenses:Food:.*" "Expenses:Food"
2024-01-01 custom "envelope" "months ahead" "2"

2024-01-01 custom "envelope" "allocate" "Expenses:Food"      400.00
2024-01-01 custom "envelope" "allocate" "Expenses:Rent"     1500.00
2024-01-01 custom "envelope" "allocate" "Expenses:Transport"  150.00

2024-02-01 custom "envelope" "allocate" "Expenses:Food"      400.00
2024-02-01 custom "envelope" "allocate" "Expenses:Rent"     1500.00
```

---

## Key Concepts

### Budget Accounts

Only transactions that touch a budget account are considered. A transaction entirely within non-budget accounts (e.g. a credit card payment between two assets) is ignored for activity purposes.

### Envelopes

Each expense account that appears in a qualifying transaction becomes an envelope automatically. You do not need to declare them explicitly — only `allocate` directives and activity are needed.

### Available Balance

``` 
available = budgeted + activity (+ previous month's available, if positive)
```

Activity is negative (money spent), budgeted is positive (money assigned). If an envelope ends the month with a surplus, that surplus carries into the next month by default. If it ends with a deficit, the deficit is dropped (reset to zero) unless `negative rollover "allow"` is set.

### To Be Budgeted

``` 
To Be Budgeted = Avail Income + Overspent + Budgeted + Budgeted Future
```

This is the money you have received but not yet assigned to an envelope. The goal is to keep this at zero by allocating everything.

### Starting Balance

On the first budget month, the extension queries the balance of all budget accounts as of the first day of that month. This seeds the available income so that money you had before you started budgeting is accounted for.

---

## Architecture

.beancount file
      │
      ▼
beancount loader  (entries list + options_map)
      │
      ├──▶ _find_envelope_settings()  — reads Custom directives for config
      │
      └──▶ BeancountEnvelope._init()
                │
                ▼
           envelope_tables()
                │
                ├── _calculate_budget_activity()   — scans transactions
                ├── _calc_budget_budgeted()         — reads allocate directives
                ├── _starting_balance()             — beanquery for opening balance
                ├── _set_available()                — budgeted + activity ± rollover
                ├── _set_overspent()                — negative carry detection
                ├── _set_budgeted_for_month()       — negate total allocations
                ├── _propagate_avail_income()       — roll income forward
                ├── _set_budgeted_future()          — look-ahead clamp
                └── _set_to_be_budgeted()           — final sum
                │
                ▼
        (income_df, envelope_df, currency)   — polars DataFrames
                │
                ▼
        FavaExtensionBase (EnvelopeBudget)
                │
                ▼
        bootstrap(month) → JSON for Fava template

The intermediate state is stored in plain Python dicts (`_income[row][month]`, `_envelopes[account][month_col]`). Polars is used only for the final output DataFrames — it is not used for the computation itself.

---

## Making Changes

### Changing envelope allocations

Add or change `allocate` directives in your `.beancount` file. The date of the directive determines which month the allocation applies to. Multiple `allocate` directives for the same account and month accumulate.

### Collapsing sub-accounts

Use `mapping` to redirect activity from detailed sub-accounts into a single envelope:

``` beancount
2024-01-01 custom "envelope" "mapping" "Expenses:Food:.*" "Expenses:Food"
```

### Tracking a second currency

Use a currency-qualified envelope type. If your budget uses EUR:

``` beancount
2024-01-01 custom "envelopeEUR" "start date" "2024-01"
2024-01-01 custom "envelopeEUR" "budget account" "Assets:EuroAccount"
```

Then load the extension with `currency = "EUR"`. Currency-specific directives take precedence; the extension falls back to plain `"envelope"` directives if none are found.

---

## Limitations

- Foreign-currency postings without a `price` annotation are silently skipped and will not appear in activity.
- The extension is read-only: it cannot write allocations back to the file.
- All computation runs on every Fava page load (`after_load_file`). Very large journals with many years of history may be slow.
- Month columns are wide-format (`2024-01_budgeted`, `2024-01_activity`, …). This makes per-month display straightforward but cross-month aggregations require reshaping.
