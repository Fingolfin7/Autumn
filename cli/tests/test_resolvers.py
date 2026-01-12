from autumn_cli.utils.resolvers import resolve_context_param, resolve_tag_params


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

