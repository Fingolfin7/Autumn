"""Coverage for commitment and metadata editing command surfaces."""

from click.testing import CliRunner

from autumn_cli.commands.commitments import commitments
from autumn_cli.commands.projects import project_details
from autumn_cli.commands.meta import context, tag


class _CommitmentClient:
    created = None

    def __init__(self, *args, **kwargs):
        pass

    def list_commitments(self, **kwargs):
        return {
            "ok": True,
            "count": 1,
            "commitments": [
                {
                    "id": 12,
                    "agg": "project",
                    "name": "Autumn",
                    "type": "time",
                    "period": "weekly",
                    "target": 300,
                    "bal": 60,
                    "active": True,
                    "prog": {"actual": 240, "pct": 80, "status": "on-track"},
                }
            ],
        }

    def get_discovery_projects(self):
        return {"projects": [{"name": "Work"}]}

    def create_commitment(self, data):
        type(self).created = data
        return {"ok": True, "commitment": {"id": 12}}


def test_commitments_list_renders_goal_and_progress(monkeypatch):
    monkeypatch.setattr("autumn_cli.commands.commitments.APIClient", _CommitmentClient)

    result = CliRunner().invoke(commitments, ["list"])

    assert result.exit_code == 0
    assert "5h/week" in result.output
    assert "80%" in result.output
    assert "on-track" in result.output


def test_commitments_new_converts_duration_to_minutes(monkeypatch):
    _CommitmentClient.created = None
    monkeypatch.setattr("autumn_cli.commands.commitments.APIClient", _CommitmentClient)

    result = CliRunner().invoke(
        commitments, ["new", "Work", "--target-value", "5h"]
    )

    assert result.exit_code == 0
    assert _CommitmentClient.created == {
        "aggregation_type": "project",
        "target": "Work",
        "target_value": 300,
        "commitment_type": "time",
        "period": "weekly",
    }


class _ProjectEditClient:
    calls = []

    def __init__(self, *args, **kwargs):
        pass

    def list_projects_grouped(self):
        return {
            "projects": {
                "active": [
                    {"name": "Autumn", "context": "Work", "tags": ["python", "cli"]}
                ]
            }
        }

    def update_project_metadata(self, project, **data):
        type(self).calls.append((project, data))
        return {"ok": True, "project": {"name": project, **data}}


def test_project_edit_add_tag_merges_current_tags(monkeypatch):
    _ProjectEditClient.calls = []
    monkeypatch.setattr("autumn_cli.commands.projects.APIClient", _ProjectEditClient)
    monkeypatch.setattr("autumn_cli.commands.projects.clear_cached_projects", lambda: None)
    monkeypatch.setattr("autumn_cli.commands.projects.clear_cached_snapshot", lambda: None)

    result = CliRunner().invoke(project_details, ["edit", "autumn", "--add-tag", "server"])

    assert result.exit_code == 0
    assert _ProjectEditClient.calls == [("Autumn", {"tags": ["python", "cli", "server"]})]


def test_project_edit_clear_context_sends_null(monkeypatch):
    _ProjectEditClient.calls = []
    monkeypatch.setattr("autumn_cli.commands.projects.APIClient", _ProjectEditClient)
    monkeypatch.setattr("autumn_cli.commands.projects.clear_cached_projects", lambda: None)
    monkeypatch.setattr("autumn_cli.commands.projects.clear_cached_snapshot", lambda: None)

    result = CliRunner().invoke(project_details, ["edit", "Autumn", "--clear-context"])

    assert result.exit_code == 0
    assert _ProjectEditClient.calls == [("Autumn", {"context": None})]


def test_project_edit_rejects_replace_and_add_together():
    result = CliRunner().invoke(
        project_details, ["edit", "Autumn", "--tags", "one", "--add-tag", "two"]
    )

    assert result.exit_code != 0
    assert "cannot be combined" in result.output


class _MetadataClient:
    deleted_context = None
    renamed_tag = None

    def __init__(self, *args, **kwargs):
        pass

    def create_context(self, name, description=None):
        return {"ok": True, "context": {"id": 1, "name": name, "description": description}}

    def list_contexts(self, compact=False):
        return {"contexts": [{"id": 1, "name": "Work"}]}

    def delete_context(self, context_id):
        type(self).deleted_context = context_id
        return {"ok": True}

    def list_tags(self, compact=False):
        return {"tags": [{"id": 2, "name": "urgent"}]}

    def update_tag(self, tag_id, **data):
        type(self).renamed_tag = (tag_id, data)
        return {"ok": True, "tag": {"id": tag_id, **data}}


def test_context_new_and_delete_and_tag_rename(monkeypatch):
    _MetadataClient.deleted_context = None
    _MetadataClient.renamed_tag = None
    monkeypatch.setattr("autumn_cli.commands.meta.APIClient", _MetadataClient)
    monkeypatch.setattr("autumn_cli.commands.meta._clear_metadata_caches", lambda: None)
    runner = CliRunner()

    assert runner.invoke(context, ["new", "Work", "--description", "Office"]).exit_code == 0
    assert runner.invoke(context, ["delete", "work", "--yes"]).exit_code == 0
    assert _MetadataClient.deleted_context == 1
    assert runner.invoke(tag, ["rename", "URGENT", "Now"]).exit_code == 0
    assert _MetadataClient.renamed_tag == (2, {"name": "Now"})
