
# Table of Contents

1.  [Envelope Budget Extension for Fava/Beancount](#orgd267e81)
    1.  [Overview](#orgd2941c3)
    2.  [Public Interface](#org9b51b64)
        1.  [Fava Extension: `EnvelopeBudget`](#orgf6b245d)
        2.  [Core Calculator: `BeancountEnvelope`](#org1fb8cbb)
        3.  [Configuration Dataclass: `EnvelopeSettings`](#org00ed4a3)
        4.  [Journal Directives](#orgdaca3c5)
    3.  [Key Concepts](#org3c4fa0d)
        1.  [Available Balance](#org70722a5)
        2.  [To Be Budgeted](#orge293b7f)
        3.  [Starting Balance](#orgd8eb675)
    4.  [Architecture](#org182bf5a)
    5.  [Limitations](#orgd132a3d)


# Envelope Budget Extension for Fava/Beancount


## Overview

This extension adds envelope-style budgeting to [Fava](<https://beancount.github.io/fava/>), the web interface for [Beancount](<https://beancount.github.io/>). It works entirely as a reporting layer — no automatic transactions are generated and your journal is never modified. Budget allocations are expressed as `custom "envelope"` directives in your `.beancount` file, and structural configuration (which accounts to watch, currency, etc.) lives in the `fava-extension` config block.


## Public Interface


### Fava Extension: `EnvelopeBudget`

**Class:** `fava_envelope.EnvelopeBudget` (subclass of `FavaExtensionBase`)

Registered in your beancount file as:

    2024-01-01 custom "fava-extension" "fava_envelope" "{
        'budgets': [
            {
                'start date': '2024-01',
                'budget accounts': ['Assets:Checking'],
                'currency': 'USD'
            }
        ]
    }"

1.  `after_load_file() -> None`

    Called automatically by Fava after the ledger is loaded. Runs the full envelope computation and stores the result internally. There is no return value; call `bootstrap()` to retrieve results.

2.  `bootstrap(month: str | None = None) -> dict`

    Returns all data needed to render the budget view for a given month.
    
        {
            "months":    ["2024-01", "2024-02", ...],   # all budget months in range
            "currency":  "USD",
            "top":       [...],                          # income summary rows (see below)
            "envelopes": [...],                          # per-envelope rows (see below)
        }
    
    **`top` rows** — one dict per summary metric, in this order:
    
    <table border="2" cellspacing="0" cellpadding="6" rules="groups" frame="hsides">
    
    
    <colgroup>
    <col  class="org-left" />
    
    <col  class="org-left" />
    </colgroup>
    <thead>
    <tr>
    <th scope="col" class="org-left"><code>Name</code></th>
    <th scope="col" class="org-left">Meaning</th>
    </tr>
    </thead>
    <tbody>
    <tr>
    <td class="org-left"><code>"Funds for month"</code></td>
    <td class="org-left">Available income this month (including starting balance and carry-forward)</td>
    </tr>
    
    <tr>
    <td class="org-left"><code>"Overspent in prev month"</code></td>
    <td class="org-left">Negative envelope balances from the prior month</td>
    </tr>
    
    <tr>
    <td class="org-left"><code>"Budgeted for month"</code></td>
    <td class="org-left">Total allocated to envelopes (negative)</td>
    </tr>
    
    <tr>
    <td class="org-left"><code>"Budgeted in the future"</code></td>
    <td class="org-left">Surplus already committed to next month</td>
    </tr>
    
    <tr>
    <td class="org-left"><code>"To be budgeted for month"</code></td>
    <td class="org-left">Remaining unallocated funds</td>
    </tr>
    </tbody>
    </table>
    
    Each row: `{"Name": str, "Amount": float}`
    
    **`envelopes` rows** — one dict per expense account:
    
        {"Account": "Expenses:Food", "Budgeted": 400.0, "Activity": -312.50, "Available": 87.50}

3.  `get_budget_months() -> list[str]`

    Returns the list of `"YYYY-MM"` month strings covered by the budget. Falls back to `[current month]` if no budget is configured.
    

### Core Calculator: `BeancountEnvelope`

**Class:** `fava_envelope.modules.beancount_envelope.BeancountEnvelope`

Can be used standalone (e.g. in tests or a CLI) without Fava.

    from beancount.loader import load_file
    from fava_envelope.modules.beancount_envelope import BeancountEnvelope, EnvelopeSettings
    import re, datetime
    
    entries, errors, options_map = load_file("my.beancount")
    
    settings = EnvelopeSettings(
        start_date="2024-01",
        budget_accounts=[re.compile("Assets:Checking")],
        mappings=[],
        income_accounts=[],
        months_ahead=2,
        currency="USD",
        negative_rollover=False,
    )
    
    calc = BeancountEnvelope(entries, options_map, settings=settings)
    income_df, envelope_df, currency = calc.envelope_tables()

1.  `__init__(entries, options_map, *, settings, currency=None, end_date=None)`

    <table border="2" cellspacing="0" cellpadding="6" rules="groups" frame="hsides">
    
    
    <colgroup>
    <col  class="org-left" />
    
    <col  class="org-left" />
    
    <col  class="org-left" />
    </colgroup>
    <thead>
    <tr>
    <th scope="col" class="org-left">Parameter</th>
    <th scope="col" class="org-left">Type</th>
    <th scope="col" class="org-left">Description</th>
    </tr>
    </thead>
    <tbody>
    <tr>
    <td class="org-left"><code>entries</code></td>
    <td class="org-left"><code>list</code></td>
    <td class="org-left">Beancount AST nodes from <code>load_file</code> / <code>load_string</code></td>
    </tr>
    
    <tr>
    <td class="org-left"><code>options_map</code></td>
    <td class="org-left"><code>dict</code></td>
    <td class="org-left">Options dict from the same loader call</td>
    </tr>
    
    <tr>
    <td class="org-left"><code>settings</code></td>
    <td class="org-left"><code>EnvelopeSettings</code></td>
    <td class="org-left">Required. All structural config.</td>
    </tr>
    
    <tr>
    <td class="org-left"><code>currency</code></td>
    <td class="org-left">=str \</td>
    <td class="org-left">None=</td>
    <td class="org-left">Override reporting currency (lower priority than <code>settings.currency</code>)</td>
    </tr>
    
    <tr>
    <td class="org-left"><code>end_date</code></td>
    <td class="org-left">=date \</td>
    <td class="org-left">None=</td>
    <td class="org-left">Last date (exclusive) of the view; defaults to today + <code>months_ahead</code></td>
    </tr>
    </tbody>
    </table>

2.  `envelope_tables() -> tuple[pl.DataFrame, pl.DataFrame, str]`

    The primary output method. Returns `(income_df, envelope_df, currency)`.
    
    **`income_df`** — 5 rows × (1 + N months) columns. Row labels in `"row"` column:
    
        Avail Income | Overspent | Budgeted | Budgeted Future | To Be Budgeted
    
    Month columns are `"YYYY-MM"` strings. All value cells are `Float64`.
    
    **`envelope_df`** — one row per expense account × (1 + 3·N months) columns:
    
    <table border="2" cellspacing="0" cellpadding="6" rules="groups" frame="hsides">
    
    
    <colgroup>
    <col  class="org-left" />
    
    <col  class="org-left" />
    
    <col  class="org-left" />
    </colgroup>
    <thead>
    <tr>
    <th scope="col" class="org-left">Column pattern</th>
    <th scope="col" class="org-left">Type</th>
    <th scope="col" class="org-left">Description</th>
    </tr>
    </thead>
    <tbody>
    <tr>
    <td class="org-left"><code>account</code></td>
    <td class="org-left"><code>String</code></td>
    <td class="org-left">Fully-qualified account name (after mappings applied)</td>
    </tr>
    
    <tr>
    <td class="org-left"><code>{YYYY-MM}_budgeted</code></td>
    <td class="org-left"><code>Float64</code></td>
    <td class="org-left">Amount allocated this month</td>
    </tr>
    
    <tr>
    <td class="org-left"><code>{YYYY-MM}_activity</code></td>
    <td class="org-left"><code>Float64</code></td>
    <td class="org-left">Actual spending (negative = spent)</td>
    </tr>
    
    <tr>
    <td class="org-left"><code>{YYYY-MM}_available</code></td>
    <td class="org-left"><code>Float64</code></td>
    <td class="org-left"><code>budgeted + activity + carry</code></td>
    </tr>
    </tbody>
    </table>
    
    Calling `envelope_tables()` multiple times on the same instance is safe and produces identical results.
    

### Configuration Dataclass: `EnvelopeSettings`

**Class:** `fava_envelope.modules.beancount_envelope.EnvelopeSettings`

<table border="2" cellspacing="0" cellpadding="6" rules="groups" frame="hsides">


<colgroup>
<col  class="org-left" />

<col  class="org-left" />

<col  class="org-left" />
</colgroup>
<thead>
<tr>
<th scope="col" class="org-left">Field</th>
<th scope="col" class="org-left">Type</th>
<th scope="col" class="org-left">Description</th>
</tr>
</thead>
<tbody>
<tr>
<td class="org-left"><code>start_date</code></td>
<td class="org-left"><code>str</code></td>
<td class="org-left">First budget month, <code>"YYYY-MM"</code>. Required.</td>
</tr>

<tr>
<td class="org-left"><code>budget_accounts</code></td>
<td class="org-left"><code>list[re.Pattern]</code></td>
<td class="org-left">Compiled regexes matching accounts whose balance defines available funds.</td>
</tr>

<tr>
<td class="org-left"><code>mappings</code></td>
<td class="org-left"><code>list[tuple[re.Pattern, str]]</code></td>
<td class="org-left">Rename/collapse accounts before bucketing. Applied to posting accounts before classification.</td>
</tr>

<tr>
<td class="org-left"><code>income_accounts</code></td>
<td class="org-left"><code>list[re.Pattern]</code></td>
<td class="org-left">Extra accounts to treat as income (in addition to beancount&rsquo;s <code>Income:</code> type).</td>
</tr>

<tr>
<td class="org-left"><code>months_ahead</code></td>
<td class="org-left"><code>int</code></td>
<td class="org-left">Months beyond today to include in the view. Default <code>0</code>.</td>
</tr>

<tr>
<td class="org-left"><code>currency</code></td>
<td class="org-left">=str \</td>
<td class="org-left">None=</td>
<td class="org-left">Reporting currency override. Falls back to <code>operating_currency</code> from <code>options_map</code>.</td>
</tr>

<tr>
<td class="org-left"><code>negative_rollover</code></td>
<td class="org-left"><code>bool</code></td>
<td class="org-left">If <code>True</code>, a negative available balance carries forward. Default <code>False</code> (deficit dropped).</td>
</tr>
</tbody>
</table>


### Journal Directives

1.  Structural config (in the `fava-extension` block)

    All structural settings are passed via the Python dict in the `fava-extension` directive. The top-level key `budgets` holds a list of budget dicts (only the first is currently used):
    
        2024-01-01 custom "fava-extension" "fava_envelope" "{
            'budgets': [
                {
                    'start date': '2024-01',
                    'budget accounts': ['Assets:Checking', 'Assets:Savings'],
                    'mappings': [['Expenses:Food:.*', 'Expenses:Food']],
                    'income accounts': ['Income:Freelance'],
                    'currency': 'USD',
                    'months ahead': 2,
                    'negative rollover': false
                }
            ]
        }"

2.  Allocations (in the journal body)

        2024-01-01 custom "envelope" "allocate" "Expenses:Food" 400.00
    
    -   The **date** determines which budget month the allocation applies to.
    -   Multiple `allocate` directives for the same account and month **accumulate**.
    -   The amount is unitless (the budget currency is assumed).
    

## Key Concepts


### Available Balance

    available[m] = budgeted[m] + activity[m] + carry[m-1]
    carry[m]     = available[m]           (if negative_rollover=True)
                 = max(0, available[m])   (otherwise)


### To Be Budgeted

    TBB = Avail Income + Overspent + Budgeted + Budgeted Future

Target is zero: every dollar of income should be assigned to an envelope.

### Starting Balance

On the first budget month, all budget-account postings prior to the start date are summed. This seeds available income so pre-budget funds are accounted for.

## Architecture

    beancount loader  (entries, options_map)
          │
          ├── EnvelopeBudget._read_settings_from_config()
          │       └── EnvelopeSettings  (from fava-extension config block)
          │
          └── BeancountEnvelope(entries, options_map, settings)
                    │
                    ▼
              envelope_tables()
                    │
                    ├── _collect_activity_and_income()   single-pass over transactions
                    ├── _collect_budgeted()               reads "allocate" directives
                    ├── _starting_balance()               sums pre-period balance
                    ├── _compute_envelopes()              per-account × month math
                    └── _compute_income()                 summary row math
                    │
                    ▼
          (income_df, envelope_df, currency)  — polars DataFrames
                    │
                    ▼
          EnvelopeBudget.bootstrap(month)  → dict for Fava template


## Limitations

-   Foreign-currency postings without a `price` annotation are silently skipped.
-   Only a single budget (the first entry in `budgets`) is active at a time.
-   The extension is read-only; it cannot write allocations back to the file.
-   All computation runs on every Fava page load (`after_load_file`). Large journals may be slow.
-   Month columns are wide-format (`2024-01_budgeted`, …). Cross-month aggregations require reshaping.
