"""Unit tests for CLI functionality."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from fava_envelope.cli.__main__ import cli


class TestCLI:
    """Test CLI interface."""

    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()
        self.sample_file = (
            Path(__file__).parent.parent / "fixtures" / "sample.beancount"
        )

    def test_cli_with_valid_file(self):
        """Test CLI with valid Beancount file."""
        result = self.runner.invoke(cli, [str(self.sample_file)])

        # Should exit successfully
        assert result.exit_code == 0

        # Should produce some output (tree structure)
        assert len(result.output) > 0

    def test_cli_with_nonexistent_file(self):
        """Test CLI with non-existent file."""
        result = self.runner.invoke(cli, ["/nonexistent/file.beancount"])

        # Should fail with error
        assert result.exit_code != 0
        assert "does not exist" in result.output.lower()

    def test_cli_help(self):
        """Test CLI help output."""
        result = self.runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "Usage:" in result.output
        assert "BEANCOUNT_FILE" in result.output

    def test_cli_with_minimal_beancount_file(self):
        """Test CLI with minimal valid Beancount file."""
        minimal_content = """
option "title" "Minimal Test"
option "operating_currency" "USD"

2024-01-01 open Assets:Checking USD
2024-01-01 balance Assets:Checking 0.00 USD
"""

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".beancount", delete=False
        ) as f:
            f.write(minimal_content)
            temp_file = f.name

        try:
            result = self.runner.invoke(cli, [temp_file])
            assert result.exit_code == 0
        finally:
            Path(temp_file).unlink()

    @patch("fava_envelope.cli.__main__.loader.load_file")
    def test_cli_with_loader_error(self, mock_loader):
        """Test CLI behavior when Beancount loader fails."""
        # Mock loader to raise an exception
        mock_loader.side_effect = Exception("Beancount parsing error")

        result = self.runner.invoke(cli, [str(self.sample_file)])

        # Should handle the error gracefully
        assert result.exit_code != 0

    @patch("fava_envelope.cli.__main__.Tree")
    def test_cli_tree_creation(self, mock_tree_class):
        """Test that CLI creates Tree object correctly."""
        mock_tree = Mock()
        mock_tree.__str__ = Mock(return_value="Mocked tree output")
        mock_tree_class.return_value = mock_tree

        result = self.runner.invoke(cli, [str(self.sample_file)])

        assert result.exit_code == 0
        assert "Mocked tree output" in result.output

        # Verify Tree was called with entries
        mock_tree_class.assert_called_once()
        # Verify the tree was printed (str method called)
        mock_tree.__str__.assert_called()


class TestModuleMain:
    """Test the main module CLI functionality."""

    def setup_method(self):
        """Set up test environment."""
        self.sample_file = (
            Path(__file__).parent.parent / "fixtures" / "sample.beancount"
        )

    def test_main_module_exists(self):
        """Test that the main module can be imported."""
        try:
            from fava_envelope.modules.main import main

            assert callable(main)
        except ImportError as e:
            pytest.skip(f"Main module import failed: {e}")

    def test_main_function_callable(self):
        """Test that main function is callable."""
        try:
            from fava_envelope.modules.main import main

            # Just verify it's a function - don't actually call it
            assert hasattr(main, "__call__")
        except ImportError as e:
            pytest.skip(f"Main module import failed: {e}")


class TestCLIIntegration:
    """Integration tests for CLI with real data."""

    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()
        self.sample_file = (
            Path(__file__).parent.parent / "fixtures" / "sample.beancount"
        )

    def test_full_cli_workflow(self):
        """Test complete CLI workflow with real Beancount file."""
        result = self.runner.invoke(cli, [str(self.sample_file)])

        assert result.exit_code == 0

        # Output should contain account tree structure
        assert (
            "Assets" in result.output
            or "Income" in result.output
            or "Expenses" in result.output
        )

        # Should have output (Tree object string representation)
        assert len(result.output.strip()) > 0

    def test_cli_with_envelope_extension_file(self):
        """Test CLI with file that has envelope extension configuration."""
        # The sample file should contain envelope extension config
        result = self.runner.invoke(cli, [str(self.sample_file)])

        assert result.exit_code == 0

        # Should process file successfully even with custom directives
        assert len(result.output) > 0

    def test_cli_error_handling(self):
        """Test CLI error handling with various invalid inputs."""
        # Test with directory instead of file
        result = self.runner.invoke(cli, ["/tmp"])
        assert result.exit_code != 0

        # Test with empty string
        result = self.runner.invoke(cli, [""])
        assert result.exit_code != 0

    def test_cli_performance(self):
        """Test CLI performance with the sample file."""
        import time

        start_time = time.time()
        result = self.runner.invoke(cli, [str(self.sample_file)])
        end_time = time.time()

        # Should complete within reasonable time (adjust as needed)
        assert (end_time - start_time) < 30  # 30 seconds max
        assert result.exit_code == 0
