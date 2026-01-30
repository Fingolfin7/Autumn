"""Tests for alias command functionality."""

import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from autumn_cli.cli import cli
from autumn_cli.utils.resolvers import _get_subproject_alias, resolve_subproject_params


class TestSubprojectAliasLookup:
    """Test project-scoped subproject alias resolution."""

    def test_get_subproject_alias_finds_match(self):
        """Test that project-scoped subproject alias is found."""
        mock_config = {
            "aliases": {
                "subprojects": {
                    "Autumn CLI": {
                        "fe": "Frontend",
                        "be": "Backend",
                    }
                }
            }
        }

        with patch("autumn_cli.utils.resolvers.get_config_value") as mock_get:
            mock_get.return_value = mock_config["aliases"]["subprojects"]
            result = _get_subproject_alias("fe", "Autumn CLI")
            assert result == "Frontend"

    def test_get_subproject_alias_case_insensitive_project(self):
        """Test that project name matching is case-insensitive."""
        mock_config = {
            "Autumn CLI": {
                "fe": "Frontend",
            }
        }

        with patch("autumn_cli.utils.resolvers.get_config_value") as mock_get:
            mock_get.return_value = mock_config
            result = _get_subproject_alias("fe", "autumn cli")
            assert result == "Frontend"

    def test_get_subproject_alias_case_insensitive_alias(self):
        """Test that alias key matching is case-insensitive."""
        mock_config = {
            "Autumn CLI": {
                "FE": "Frontend",
            }
        }

        with patch("autumn_cli.utils.resolvers.get_config_value") as mock_get:
            mock_get.return_value = mock_config
            result = _get_subproject_alias("fe", "Autumn CLI")
            assert result == "Frontend"

    def test_get_subproject_alias_returns_none_wrong_project(self):
        """Test that alias is not found for different project."""
        mock_config = {
            "Autumn CLI": {
                "fe": "Frontend",
            }
        }

        with patch("autumn_cli.utils.resolvers.get_config_value") as mock_get:
            mock_get.return_value = mock_config
            result = _get_subproject_alias("fe", "Other Project")
            assert result is None

    def test_get_subproject_alias_returns_none_no_project(self):
        """Test that alias lookup requires project."""
        mock_config = {
            "Autumn CLI": {
                "fe": "Frontend",
            }
        }

        with patch("autumn_cli.utils.resolvers.get_config_value") as mock_get:
            mock_get.return_value = mock_config
            result = _get_subproject_alias("fe", None)
            assert result is None


class TestResolveSubprojectParamsWithProject:
    """Test resolve_subproject_params with project parameter."""

    def test_resolve_uses_project_scoped_alias(self):
        """Test that resolver uses project-scoped aliases."""
        known_subs = [{"name": "Frontend"}, {"name": "Backend"}]

        with patch("autumn_cli.utils.resolvers._get_subproject_alias") as mock_alias:
            mock_alias.return_value = "Frontend"
            resolved, warnings = resolve_subproject_params(
                subprojects=["fe"],
                known_subprojects=known_subs,
                project="Autumn CLI"
            )
            assert resolved == ["Frontend"]
            assert warnings == []
            mock_alias.assert_called_once_with("fe", "Autumn CLI")


class TestAliasCommandHelp:
    """Test that alias commands are properly registered."""

    def test_alias_command_exists(self):
        """Test that alias command group is registered."""
        runner = CliRunner()
        result = runner.invoke(cli, ["alias", "--help"])
        assert result.exit_code == 0
        assert "add" in result.output
        assert "list" in result.output
        assert "remove" in result.output

    def test_alias_add_requires_type(self):
        """Test that alias add requires a type argument."""
        runner = CliRunner()
        result = runner.invoke(cli, ["alias", "add"])
        assert result.exit_code != 0
        assert "Missing argument" in result.output or "Usage:" in result.output
