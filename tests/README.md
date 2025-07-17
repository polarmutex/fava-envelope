# fava-envelope Test Suite

This directory contains comprehensive tests for the fava-envelope project, including unit tests, integration tests, and CLI tests.

## Test Structure

```
tests/
├── __init__.py              # Test package initialization
├── conftest.py              # Pytest configuration and shared fixtures
├── pytest.ini              # Pytest configuration file
├── README.md                # This file
├── fixtures/                # Test data and fixtures
│   ├── __init__.py
│   ├── test_data.py         # Mock data and sample objects
│   └── sample.beancount     # Sample Beancount file for testing
├── unit/                    # Unit tests
│   ├── __init__.py
│   ├── test_config.py       # Configuration parsing tests
│   ├── test_envelope_budget.py  # Main extension class tests
│   ├── test_budget_calculations.py  # Budget calculation logic tests
│   └── test_cli.py          # CLI functionality tests
└── integration/             # Integration tests
    ├── __init__.py
    └── test_full_workflow.py # End-to-end workflow tests
```

## Test Categories

### Unit Tests

1. **Configuration Tests** (`test_config.py`)
   - Configuration parsing and validation
   - Default value handling
   - Multiple budget configurations
   - Error handling for invalid configurations

2. **EnvelopeBudget Class Tests** (`test_envelope_budget.py`)
   - Basic class functionality
   - Bootstrap method testing
   - Query table generation
   - Error handling

3. **Budget Calculation Tests** (`test_budget_calculations.py`)
   - Envelope available amount calculations
   - Income adjustments across months
   - Overspent amount tracking
   - Budget allocation logic

4. **CLI Tests** (`test_cli.py`)
   - Command-line interface functionality
   - Error handling
   - File processing

### Integration Tests

1. **Full Workflow Tests** (`test_full_workflow.py`)
   - End-to-end processing with real Beancount data
   - Complex account mapping scenarios
   - Multi-month budget workflows
   - Real-world use case validation

## Running Tests

### Prerequisites

Ensure you have the development environment set up:

```bash
# Using Nix (recommended)
nix develop

# Or using uv
uv sync
source .venv/bin/activate
```

### Running All Tests

```bash
# Run all tests
uv run python -m pytest

# Run with verbose output
uv run python -m pytest -v

# Run with coverage
uv run python -m pytest --cov=fava_envelope --cov-report=html
```

### Running Specific Test Categories

```bash
# Unit tests only
uv run python -m pytest tests/unit/

# Integration tests only
uv run python -m pytest tests/integration/

# Configuration tests only
uv run python -m pytest tests/unit/test_config.py

# CLI tests only
uv run python -m pytest tests/unit/test_cli.py
```

### Running Individual Tests

```bash
# Run a specific test class
uv run python -m pytest tests/unit/test_config.py::TestConfigurationParsing

# Run a specific test method
uv run python -m pytest tests/unit/test_config.py::TestConfigurationParsing::test_empty_config

# Run tests matching a pattern
uv run python -m pytest -k "config"
```

### Test Markers

Tests are marked with the following categories:

```bash
# Run only unit tests
uv run python -m pytest -m unit

# Run only integration tests  
uv run python -m pytest -m integration

# Run only CLI tests
uv run python -m pytest -m cli

# Skip slow tests
uv run python -m pytest -m "not slow"
```

## Test Coverage

The test suite aims for comprehensive coverage of:

- Configuration parsing and validation
- Budget calculation logic
- Query table generation
- Error handling
- CLI functionality
- Integration with Beancount data

Coverage reports are generated in `htmlcov/` directory when running with `--cov-report=html`.

## Test Data and Fixtures

### Shared Fixtures (`conftest.py`)

- `mock_ledger`: Mock Beancount ledger for testing
- `sample_dataframes`: Pre-built DataFrames for testing
- `sample_config`: Standard test configuration
- `empty_config`: Empty configuration for edge case testing
- `multi_budget_config`: Configuration with multiple budgets

### Test Data (`fixtures/test_data.py`)

- Sample Beancount entries
- Mock configuration data
- Helper functions for creating test objects

### Sample Beancount File (`fixtures/sample.beancount`)

Real Beancount file with:
- Multiple account types (Assets, Income, Expenses)
- Various transaction types
- Budget allocation directives
- Account mappings

## Writing New Tests

### Unit Test Guidelines

1. **Test Structure**: Use descriptive class and method names
2. **Setup**: Use `setup_method()` for test initialization
3. **Assertions**: Use specific assertions with clear error messages
4. **Mocking**: Mock external dependencies appropriately
5. **Coverage**: Test both happy path and error conditions

### Example Unit Test

```python
class TestNewFeature:
    def setup_method(self):
        """Set up test environment."""
        self.ledger = create_mock_ledger()
        self.extension = EnvelopeBudget(self.ledger)
    
    def test_feature_with_valid_input(self):
        """Test feature with valid input."""
        result = self.extension.new_feature("valid_input")
        assert result == expected_value
    
    def test_feature_with_invalid_input(self):
        """Test feature error handling."""
        with pytest.raises(ValueError):
            self.extension.new_feature("invalid_input")
```

### Integration Test Guidelines

1. **Real Data**: Use actual Beancount files when possible
2. **End-to-End**: Test complete workflows
3. **Edge Cases**: Test boundary conditions and complex scenarios
4. **Performance**: Include basic performance checks

## Continuous Integration

Tests are configured to run automatically on code changes with:

- Coverage requirements (minimum 80%)
- Multiple Python versions support
- Linting and type checking integration
- Performance regression detection

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure the package is installed in development mode
2. **Missing Dependencies**: Run `uv sync` to install test dependencies
3. **Fixture Errors**: Check that mock objects match expected interfaces
4. **Path Issues**: Use absolute paths or Path objects for file operations

### Debug Mode

```bash
# Run with debugging output
uv run python -m pytest -v -s

# Drop into debugger on failure
uv run python -m pytest --pdb

# Run with extra output
uv run python -m pytest --tb=long
```

## Test Performance

- Unit tests should complete in under 5 seconds
- Integration tests should complete in under 30 seconds
- Full test suite should complete in under 2 minutes

## Contributing

When adding new features:

1. Add unit tests for new functionality
2. Add integration tests for complex workflows
3. Update test documentation
4. Ensure tests pass with good coverage
5. Add appropriate test markers

For questions about testing, refer to the main project documentation or open an issue.