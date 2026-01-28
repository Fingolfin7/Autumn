from autumn_cli.utils.resolvers import (
    resolve_context_param,
    resolve_tag_params,
    resolve_project_param,
    resolve_subproject_params,
)


def test_resolve_context_param_case_insensitive_name_to_id():
    contexts = [
        {"id": 1, "name": "General"},
        {"id": 2, "name": "Work"},
    ]

    res = resolve_context_param(context="general", contexts=contexts)
    assert res.value == "1"

    res = resolve_context_param(context="GENERAL", contexts=contexts)
    assert res.value == "1"


def test_resolve_tag_params_case_insensitive_names_to_ids():
    known_tags = [
        {"id": 10, "name": "Code"},
        {"id": 11, "name": "DeepWork"},
    ]

    resolved, warnings = resolve_tag_params(tags=["code", "DEEPWORK"], known_tags=known_tags)
    assert resolved == ["10", "11"]
    assert warnings == []


def test_resolve_tag_params_mixed_ids_and_unknown():
    known_tags = [
        {"id": 10, "name": "Code"},
    ]

    resolved, warnings = resolve_tag_params(tags=["10", "UnknownTag"], known_tags=known_tags)
    assert resolved == ["10", "UnknownTag"]
    assert len(warnings) == 1


def test_resolve_project_param_case_insensitive():
    projects = [
        {"name": "Autumn CLI", "status": "active"},
        {"name": "MyProject", "status": "active"},
    ]

    res = resolve_project_param(project="autumn cli", projects=projects)
    assert res.value == "Autumn CLI"
    assert res.warning is None

    res = resolve_project_param(project="MYPROJECT", projects=projects)
    assert res.value == "MyProject"
    assert res.warning is None


def test_resolve_project_param_unknown_warns():
    projects = [
        {"name": "Autumn CLI", "status": "active"},
    ]

    res = resolve_project_param(project="NonExistent", projects=projects)
    assert res.value == "NonExistent"
    assert res.warning is not None
    assert "Unknown project" in res.warning


def test_resolve_subproject_params_case_insensitive():
    known_subs = [
        {"name": "Documentation"},
        {"name": "Testing"},
    ]

    resolved, warnings = resolve_subproject_params(
        subprojects=["documentation", "TESTING"], known_subprojects=known_subs
    )
    assert resolved == ["Documentation", "Testing"]
    assert warnings == []


def test_resolve_subproject_params_string_list():
    # Test with compact format (list of strings)
    known_subs = ["Docs", "Tests", "Code"]

    resolved, warnings = resolve_subproject_params(
        subprojects=["docs", "CODE"], known_subprojects=known_subs
    )
    assert resolved == ["Docs", "Code"]
    assert warnings == []


def test_resolve_subproject_params_unknown_warns():
    known_subs = [{"name": "Documentation"}]

    resolved, warnings = resolve_subproject_params(
        subprojects=["Unknown"], known_subprojects=known_subs
    )
    assert resolved == ["Unknown"]
    assert len(warnings) == 1
    assert "Unknown subproject" in warnings[0]

