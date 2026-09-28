import json

import pytest

from ic import plan
from ic.record import accepted, round_dir, rounds
from ic.unit import load_unit
from conftest import reply_text


def run(cfg, name="counter", **kw):
    unit = load_unit(cfg.root, name)
    return plan.plan(cfg, unit, cfg.endpoint_for("plan"), accept_flag=False,
                     dry_run=kw.get("dry_run", False))


def test_first_round_writes_plan_and_record(cfg, ollama):
    ollama.replies.append(reply_text(questions="- which base?"))
    assert run(cfg) == 0
    unit = load_unit(cfg.root, "counter")
    assert unit.read("intent.md") == "Counts things.\n"
    assert unit.read("spec.md") == "## Representation\nAn Int.\n"
    assert unit.read("input.md") == ""                       # consumed
    d = round_dir(unit, 1)
    assert (d / "input.md").read_text() == "A counter.\n"    # archived
    assert (d / "choices.md").read_text() == "- chose Int\n"
    assert (d / "questions.md").read_text() == "- which base?\n"
    meta = json.loads((d / "meta.json").read_text())
    assert meta["status"] == "ok" and meta["parent"] is None
    assert set(meta["outputs"]) == {"intent.md", "spec.md"}
    assert "No plan exists yet" in (d / "prompt.md").read_text()


def test_revision_round_sends_current_plan(cfg, ollama):
    run(cfg)
    unit = load_unit(cfg.root, "counter")
    unit.path("input.md").write_text("Make it count down too.\n")
    ollama.replies.append(reply_text(spec="## Representation\nAn Int, down too."))
    run(cfg)
    user = ollama.requests[1]["messages"][1]["content"]
    assert "# Current plan" in user and "An Int." in user
    assert "Make it count down too." in user
    meta = json.loads((round_dir(unit, 2) / "meta.json").read_text())
    assert meta["parent"] == 1
    assert "down too" in unit.read("spec.md")


def test_empty_input_shows_status(cfg, capsys):
    unit = load_unit(cfg.root, "counter")
    unit.path("input.md").write_text("  \n")
    assert run(cfg) == 0
    assert "input.md is empty" in capsys.readouterr().out
    assert rounds(unit) == []


def test_dry_run_calls_nothing(cfg, ollama, capsys):
    run(cfg, dry_run=True)
    assert ollama.requests == []
    assert "=== system ===" in capsys.readouterr().out
    assert rounds(load_unit(cfg.root, "counter")) == []


def test_unparsed_reply_leaves_files(cfg, ollama):
    ollama.replies.append("I refuse to use the format.")
    with pytest.raises(ValueError, match="missing section"):
        run(cfg)
    unit = load_unit(cfg.root, "counter")
    assert unit.read("input.md") == "A counter.\n"
    assert not unit.has("intent.md")
    meta = json.loads((round_dir(unit, 1) / "meta.json").read_text())
    assert meta["status"] == "unparsed"


def test_failed_round_is_recorded(cfg, ollama):
    ollama.replies.append([{"error": "boom"}])
    with pytest.raises(RuntimeError):
        run(cfg)
    meta = json.loads((round_dir(load_unit(cfg.root, "counter"), 1) / "meta.json").read_text())
    assert meta["status"] == "failed" and "boom" in meta["error"]


def test_accept_and_hand_edit_guard(cfg):
    unit = load_unit(cfg.root, "counter")
    with pytest.raises(FileNotFoundError, match="no plan"):
        plan.accept(cfg, unit)
    run(cfg)
    unit.path("spec.md").write_text("edited by hand\n")
    assert plan.hand_edited(unit) == ["spec.md"]
    with pytest.raises(ValueError, match="differ"):
        plan.accept(cfg, unit)
    unit.path("spec.md").write_text("## Representation\nAn Int.\n")
    assert plan.accept(cfg, unit) == 0
    assert accepted(unit)["round"] == 1


def test_dependency_must_be_accepted(cfg, ollama):
    root = cfg.root
    (root / "units" / "user").mkdir()
    (root / "units" / "user" / "input.md").write_text("Uses the counter.\n")
    (root / "units" / "user" / "deps").write_text("unit: counter\n")
    with pytest.raises(FileNotFoundError, match="accept"):
        run(cfg, "user")
    run(cfg)
    plan.accept(cfg, load_unit(root, "counter"))
    run(cfg, "user")
    user = ollama.requests[-1]["messages"][1]["content"]
    assert '## Dependency: unit "counter"' in user and "An Int." in user
    # changing the dependency's spec invalidates its acceptance
    load_unit(root, "user").path("input.md").write_text("again\n")
    load_unit(root, "counter").path("spec.md").write_text("changed\n")
    with pytest.raises(FileNotFoundError, match="accept"):
        run(cfg, "user")


def test_half_plan_is_an_error(cfg):
    unit = load_unit(cfg.root, "counter")
    unit.path("intent.md").write_text("only intent\n")
    with pytest.raises(FileNotFoundError, match="spec.md is missing"):
        plan.plan_state(unit)


def test_clean_restores_first_input(cfg):
    run(cfg)
    unit = load_unit(cfg.root, "counter")
    assert plan.clean(unit, yes=True) == 0
    assert not unit.has("intent.md") and not unit.has("spec.md")
    assert not (unit.dir / ".build").exists()
    assert unit.read("input.md") == "A counter.\n"


def test_clean_keeps_pending_input(cfg):
    run(cfg)
    unit = load_unit(cfg.root, "counter")
    unit.path("input.md").write_text("new idea\n")
    plan.clean(unit, yes=True)
    assert unit.read("input.md") == "new idea\n"


def test_brief(cfg, ollama):
    unit = load_unit(cfg.root, "counter")
    assert plan.brief(unit) == "0 rounds · no plan · input pending"
    ollama.replies.append(reply_text(questions="- why?"))
    run(cfg)
    plan.accept(cfg, unit)
    assert plan.brief(unit) == "1 round · plan · accepted 001 · open questions"
