import pytest

from ic.plan import parse_reply
from conftest import reply_text


def test_sections_split():
    parts = parse_reply(reply_text(intent="I.", spec="S.", choices="- a\n- b", questions="- q?"))
    assert parts == {"INTENT": "I.", "SPEC": "S.", "CHOICES": "- a\n- b", "QUESTIONS": "- q?"}


@pytest.mark.parametrize("word", ["none", "None", "- none", "(none)", "*none*", ""])
def test_none_means_empty(word):
    parts = parse_reply(reply_text(choices=word, questions=word))
    assert parts["CHOICES"] == "" and parts["QUESTIONS"] == ""


def test_outer_fence_stripped():
    parts = parse_reply(reply_text(spec="```markdown\n## Representation\nx\n```"))
    assert parts["SPEC"] == "## Representation\nx"


def test_inner_fences_kept():
    spec = "## Interface\n```julia\nf(x::Int)::Int\n```\nmore"
    assert parse_reply(reply_text(spec=spec))["SPEC"] == spec


def test_missing_section_raises():
    with pytest.raises(ValueError, match="SPEC"):
        parse_reply("=== INTENT ===\nonly intent\n")


def test_marker_must_be_whole_line():
    text = "=== INTENT ===\nsee === SPEC === inline\n=== SPEC ===\nS\n"
    assert parse_reply(text)["INTENT"] == "see === SPEC === inline"


def test_optional_sections_may_be_absent():
    parts = parse_reply("=== INTENT ===\nI\n=== SPEC ===\nS\n")
    assert parts.get("CHOICES", "") == "" and parts.get("QUESTIONS", "") == ""
