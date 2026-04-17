from __future__ import annotations

from click.testing import CliRunner

from autumn_cli.commands.projects import projects_list, subprojects


class _ProjectsSearchListClient:
    def __init__(self, *args, **kwargs):
        pass

    def search_projects(self, search_term, status=None):
        return [
            {
                "name": "First Ascent",
                "status": "active",
                "description": "Climbing project",
            }
        ]


class _SubprojectsSearchListClient:
    def __init__(self, *args, **kwargs):
        pass

    def get_discovery_projects(self, ttl_seconds=300, refresh=False):
        return {"projects": [{"name": "First Ascent", "status": "active"}]}

    def search_subprojects(self, project, search_term):
        return [{"name": "Meals", "description": "Meal prep"}]


def test_projects_search_accepts_list_response(monkeypatch):
    printed = []

    monkeypatch.setattr(
        "autumn_cli.commands.projects.APIClient", _ProjectsSearchListClient
    )
    monkeypatch.setattr(
        "autumn_cli.commands.projects.console.print",
        lambda *args, **kwargs: printed.append(args),
    )

    runner = CliRunner()
    result = runner.invoke(projects_list, ["--status", "all", "--desc", "-q", "First Ascent"])

    assert result.exit_code == 0
    assert printed


def test_subprojects_search_accepts_list_response(monkeypatch):
    printed = []

    monkeypatch.setattr(
        "autumn_cli.commands.projects.APIClient", _SubprojectsSearchListClient
    )
    monkeypatch.setattr(
        "autumn_cli.commands.projects.console.print",
        lambda *args, **kwargs: printed.append(args),
    )

    runner = CliRunner()
    result = runner.invoke(subprojects, ["First Ascent", "--desc", "-q", "Meal"])

    assert result.exit_code == 0
    assert printed
