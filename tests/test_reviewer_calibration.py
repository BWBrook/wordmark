from pathlib import Path

import yaml


FIXTURE_PATH = Path("examples/reviewer_calibration/critical_line_edits.yaml")

LINE_EDIT_CATEGORIES = {
    "british_english",
    "clarity",
    "concision",
    "grammar_agreement",
    "punctuation_hyphenation",
    "sentence_flow",
}

COMMENT_ONLY_CATEGORIES = {
    "interpretation_choice",
    "methods_detail",
    "missing_evidence",
    "structure",
}


def load_fixture() -> dict:
    return yaml.safe_load(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_reviewer_calibration_fixture_schema() -> None:
    payload = load_fixture()

    assert payload["schema_version"] == 1
    assert payload["purpose"]
    assert isinstance(payload["cases"], list)
    assert len(payload["cases"]) >= 10

    ids = [case["id"] for case in payload["cases"]]
    assert len(ids) == len(set(ids))

    categories = {case["category"] for case in payload["cases"]}
    assert LINE_EDIT_CATEGORIES.issubset(categories)
    assert COMMENT_ONLY_CATEGORIES.issubset(categories)


def test_line_edit_cases_have_precise_tracked_replacements() -> None:
    payload = load_fixture()

    line_edit_cases = [
        case for case in payload["cases"] if case["decision"] == "tracked_edit"
    ]
    assert len(line_edit_cases) >= 8

    for case in line_edit_cases:
        assert case["category"] in LINE_EDIT_CATEGORIES
        assert case["source"]
        assert case["weak_feedback"]
        assert case["rationale"]
        assert case["preferred_comments"] == []
        assert case["preferred_tracked_edits"]

        for edit in case["preferred_tracked_edits"]:
            assert edit["find"]
            assert edit["replace"]
            assert edit["find"] != edit["replace"]
            assert edit["rationale"]


def test_comment_only_cases_do_not_smuggle_line_edits() -> None:
    payload = load_fixture()

    comment_cases = [case for case in payload["cases"] if case["decision"] == "comment"]
    assert len(comment_cases) >= 4

    for case in comment_cases:
        assert case["category"] in COMMENT_ONLY_CATEGORIES
        assert case["source"]
        assert case["weak_feedback"]
        assert case["rationale"]
        assert case["preferred_tracked_edits"] == []
        assert case["preferred_comments"]

        for comment in case["preferred_comments"]:
            assert comment["anchor"]
            assert comment["text"]
            assert comment["rationale"]
