# fava-envelope

A Beancount Fava extension that implements envelope budgeting methodology for personal finance management.

## Project Overview

**fava-envelope** is a Python package that extends [Fava](https://github.com/beancount/fava) (the web interface for [Beancount](https://github.com/beancount/beancount)) with envelope budgeting capabilities. The project provides both a Fava web extension and CLI tools to help users manage their finances using the envelope budgeting method.

### Key Features
- Envelope budgeting within Fava interface  
- Custom Beancount directives for budget configuration
- Multi-currency support (with single currency per budget)
- Income/expense tracking and categorization
- Budget allocation and rollover functionality
- Clean web interface for budget visualization

## Architecture

### Core Components

1. **FavaExtensionBase Integration** (`src/fava_envelope/__init__.py`)
   - Main extension class `EnvelopeBudget` 
   - Extends Fava's `FavaExtensionBase`
   - Handles configuration parsing and budget processing
   - Provides web API endpoints for the frontend

2. **Budget Engine** (`src/fava_envelope/modules/beancount_envelope.py`)
   - `BeancountEnvelope` class - core budget calculation logic
   - Processes Beancount transactions and custom directives
   - Generates pandas DataFrames for income and envelope data
   - Handles currency conversion and account mappings

3. **CLI Interface** (`src/fava_envelope/cli/__main__.py`)
   - Command-line tool for budget processing
   - Uses Click for argument parsing
   - Provides standalone budget analysis without web interface

4. **Web Template** (`src/fava_envelope/templates/EnvelopeBudget.html`)
   - Jinja2 template for Fava web interface
   - Budget and month selection interface
   - Modern Svelte component rendering for query tables

### Data Flow

1. **Configuration**: Budget settings defined via Beancount custom directives
2. **Transaction Processing**: Beancount entries filtered and categorized
3. **Budget Calculation**: Income, expenses, and allocations computed per month
4. **Data Presentation**: Results formatted for web interface or CLI output

### Key Classes

- `EnvelopeBudget`: Main Fava extension class
- `BeancountEnvelope`: Core budget calculation engine  
- `BudgetConfig`: Configuration data structure
- `BudgetCtx`: Computed budget context with DataFrames

## Development Setup

### Prerequisites
- Python 3.9+
- Nix (recommended) or uv for dependency management

### Nix Development (Recommended)
```bash
# Enter development shell
nix develop

# Pre-commit hooks are automatically installed
# Python environment with all dependencies is available
```

### Alternative: uv Development
```bash
# Install dependencies
uv sync

# Activate virtual environment  
source .venv/bin/activate

# Install pre-commit hooks
pre-commit install
```

### Development Tools

- **Build System**: Hatchling
- **Dependency Management**: uv with pyproject.toml
- **Linting**: ruff
- **Type Checking**: basedpyright/mypy with pandas-stubs
- **Testing**: pytest with pytest-cov, pytest-django
- **Pre-commit**: Black, ruff
- **Nix**: Complete reproducible environment

## Key Commands

### Development Commands
```bash
# Linting and formatting (using nix environment)
nix develop --command ruff check src/
nix develop --command ruff format src/

# Alternative using uv
uv run ruff check src/
uv run ruff format src/

# Type checking
nix develop --command mypy src/

# Run tests
uv run python -m pytest

# Run tests with coverage
uv run python -m pytest --cov=fava_envelope --cov-report=html

# Pre-commit (all checks)
nix develop --command pre-commit run --all-files
```

### Legacy Makefile Commands
```bash
# Install requirements (if not using nix/uv)
make install_reqs

# Run pre-commit
make pre-commit
```

### Package Installation
```bash
# Install from PyPI
pip install fava-envelope

# Install for development
pip install -e .
```

## Beancount Integration

### Fava Extension Setup
Add to your Beancount file:
```beancount
2000-01-01 custom "fava-extension" "fava_envelope" "{
    'budgets': [
        {
            'name': 'USD Budget',
            'currency': 'USD', 
            'start date': '2024-01',
            'budget accounts': [
                'Assets:Checking',
                'Assets:Savings'
            ],
            'mappings': [
                {'from': 'Expenses:Food:*', 'to': 'Expenses:Food'}
            ]
        }
    ]
}"
```

### Budget Configuration Directives
```beancount
; Budget allocation
2024-01-31 custom "envelope" "allocate" "Expenses:Food" 500.00

; Account mappings (optional)
2024-01-01 custom "envelope" "mapping" "Expenses:Food:*" "Expenses:Food"

; Budget accounts (optional, defaults to Assets:*)
2024-01-01 custom "envelope" "budget account" "Assets:Checking"
```

### Operating Currency
```beancount
option "operating_currency" "USD"
```

## File Structure

```
src/fava_envelope/
├── __init__.py              # Main extension class
├── cli/
│   └── __main__.py         # CLI interface
├── modules/
│   ├── __init__.py
│   ├── main.py             # CLI main function
│   └── beancount_envelope.py  # Core budget engine
└── templates/
    └── EnvelopeBudget.html  # Fava web template

tests/                       # Comprehensive test suite
├── __init__.py
├── conftest.py             # Pytest configuration
├── pytest.ini             # Test settings
├── README.md               # Test documentation
├── fixtures/               # Test data and utilities
│   ├── __init__.py
│   ├── test_data.py        # Mock data and fixtures
│   └── sample.beancount    # Sample Beancount file
├── unit/                   # Unit tests
│   ├── __init__.py
│   ├── test_config.py      # Configuration parsing tests
│   ├── test_envelope_budget.py  # Main class tests
│   ├── test_budget_calculations.py  # Calculation logic tests
│   └── test_cli.py         # CLI functionality tests
└── integration/            # Integration tests
    ├── __init__.py
    └── test_full_workflow.py  # End-to-end tests

pyproject.toml               # Project configuration
tox.ini                      # Testing configuration
flake.nix                    # Nix development environment  
Makefile                     # Legacy build commands
example.beancount            # Example/test data
```

## Dependencies

### Core Runtime
- `beancount>=3.0.0` - Core accounting engine
- `fava>=1.26` - Web interface framework
- `pandas>=2.2.2` - Data manipulation
- `beanquery>=0.1.0` - Query engine
- `Click>=7` - CLI framework

### Development
- `ruff>=0.7.2` - Linting and formatting
- `mypy>=1.13.0` - Type checking
- `pytest>=8.3.3` - Testing framework  
- `pandas-stubs>=2.2.2` - Type stubs

## Testing

The project includes a comprehensive test suite with 59 tests covering unit, integration, and CLI functionality.

### Test Structure
- **Unit Tests** (49 tests): Configuration parsing, main class methods, budget calculations, CLI
- **Integration Tests** (10 tests): End-to-end workflows with real Beancount data
- **Test Coverage**: 93% on main extension module, 53% overall
- **Test Framework**: pytest with coverage reporting and fixtures

### Test Categories
- `tests/unit/test_config.py` - Configuration parsing and validation (13 tests)
- `tests/unit/test_envelope_budget.py` - Core EnvelopeBudget class functionality (15 tests)
- `tests/unit/test_budget_calculations.py` - Budget calculation logic (8 tests)
- `tests/unit/test_cli.py` - Command-line interface (13 tests)
- `tests/integration/test_full_workflow.py` - End-to-end scenarios (10 tests)

### Running Tests
```bash
# Run all tests
uv run python -m pytest

# Run with coverage
uv run python -m pytest --cov=fava_envelope --cov-report=html

# Run specific test categories
uv run python -m pytest tests/unit/          # Unit tests only
uv run python -m pytest tests/integration/   # Integration tests only

# Run with verbose output
uv run python -m pytest -v

# Using nix development environment
nix develop --command pytest
```

### Test Features
- **Mock data and fixtures** for consistent testing
- **Sample Beancount files** for realistic integration testing
- **Comprehensive coverage** of configuration scenarios, error handling, and edge cases
- **Performance testing** to ensure reasonable execution times
- **CLI testing** with real file processing

## Key Configuration Files

- `pyproject.toml`: Modern Python packaging, dependencies, tool config
- `flake.nix`: Nix development environment with uv integration  
- `tox.ini`: Multi-environment testing
- `uv.lock`: Locked dependency versions
- `.pre-commit-config.yaml`: Git hooks (implied, not visible)

## Extension API

### Web Interface Methods
- `bootstrap(id, month)`: Initialize budget data for web interface
- `get_budget_months(id)`: Get available months for budget
- `generate_income_query_table()`: Generate QueryResultTable for income data (modern Svelte)
- `generate_envelope_query_table()`: Generate QueryResultTable for envelope data (modern Svelte)

### Core Processing Methods  
- `process_budget(cfg)`: Main budget calculation
- `calc_budget_account_activity()`: Process transactions
- `build_envelope_df()`: Create envelope DataFrame
- `build_top_df()`: Create income summary DataFrame

## Common Workflows

### Adding New Budget Features
1. Extend `BudgetConfig` dataclass if needed
2. Add parsing logic in `read_extension_config()`
3. Implement calculation in `process_budget()` or related methods
4. Update web template if UI changes needed
5. Add tests for new functionality

### Debugging Budget Calculations
1. Use CLI tool for isolated testing: `python -m fava_envelope.cli example.beancount`
2. Add debug prints in `process_budget()` method
3. Examine pandas DataFrames: `budget_ctx.envelopes`, `budget_ctx.top`
4. Verify custom directive parsing in `_find_envelop_settings()`

### Testing Changes
```bash
# Quick smoke test
python -m fava_envelope.modules.main example.beancount

# Full test suite
pytest

# Pre-commit all checks
pre-commit run --all-files
```

## Known Issues & TODOs

From code analysis:
- Add comprehensive testing suite
- Improve example files for screenshots/testing  
- Add charting capabilities
- Better error handling for malformed configurations
- Documentation improvements