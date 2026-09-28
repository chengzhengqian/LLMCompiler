import sys
import textwrap

import pytest

from ic import cli
from ic.record import rounds
from ic.repl import Repl
from ic.unit import load_unit


@pytest.fixture
def sh(cfg):
    return Repl(cfg)


def out_of(capsys, sh, *lines):
    for line in lines:
        sh.onecmd(line)
    return capsys.readouterr().out


def test_prompt_follows_focus(sh):
    assert sh.prompt == "ic> "
    sh.onecmd("use counter"); sh.postcmd(False, "")
    assert sh.prompt == "ic:counter> "
    sh.onecmd("endpoint other"); sh.postcmd(False, "")
    assert sh.prompt == "ic:counter @other> "


def test_commands_need_focus(sh, capsys):
    assert "no unit in focus" in out_of(capsys, sh, "spec")


def test_units_and_new(sh, capsys):
    out = out_of(capsys, sh, "units")
    assert "counter" in out and "input pending" in out
    out = out_of(capsys, sh, "new widget", "units")
    assert sh.unit.name == "widget"
    assert "* widget" in out
    assert "already exists" in out_of(capsys, sh, "new widget")


def test_add_show_clear(sh, capsys):
    out = out_of(capsys, sh, "use counter", "add Also decrement.", "input")
    assert "A counter.\nAlso decrement." in out
    out_of(capsys, sh, "clear")
    assert "(empty)" in out_of(capsys, sh, "input")


def test_plan_accept_and_views(sh, capsys, ollama):
    out = out_of(capsys, sh, "use counter", "plan")
    assert "round 001 done" in out
    out = out_of(capsys, sh, "spec", "intent", "show", "choices", "rounds")
    assert "An Int." in out and "Counts things." in out and "chose Int" in out
    assert "001  ok" in out
    out = out_of(capsys, sh, "accept", "rounds", "status")
    assert "accepted round 001" in out and "A 001" in out
    assert "input.md is empty" in out_of(capsys, sh, "plan")        # status, no round
    assert len(ollama.requests) == 1


def test_plan_options(sh, capsys, ollama):
    out = out_of(capsys, sh, "use counter", "plan -n")
    assert "=== system ===" in out and ollama.requests == []
    assert "unknown endpoint" in out_of(capsys, sh, "plan -e nope")
    assert "unrecognized" in out_of(capsys, sh, "plan --bogus")
    out_of(capsys, sh, "plan -e other")
    assert ollama.requests[0]["model"] == "other-model"


def test_session_endpoint(sh, capsys, ollama):
    out = out_of(capsys, sh, "endpoint other")
    assert "other-model" in out and "session" in out
    out_of(capsys, sh, "use counter", "plan")
    assert ollama.requests[0]["model"] == "other-model"
    assert "from ic.toml" in out_of(capsys, sh, "endpoint -")
    assert "unknown endpoint" in out_of(capsys, sh, "endpoint nope")


def test_show_rounds_by_number(sh, capsys, ollama):
    unit = load_unit(sh.cfg.root, "counter")
    out_of(capsys, sh, "use counter", "plan")
    unit.path("input.md").write_text("second\n")
    out_of(capsys, sh, "plan")
    assert "second" in out_of(capsys, sh, "show archived")
    assert "A counter." in out_of(capsys, sh, "show archived 1")
    assert "no round 007" in out_of(capsys, sh, "show archived 7")
    assert "no questions.md" in out_of(capsys, sh, "questions")
    assert "unknown file" in out_of(capsys, sh, "show bogus")


def test_edit_uses_editor(sh, capsys, tmp_path, monkeypatch):
    script = tmp_path / "fake_editor.py"
    script.write_text(textwrap.dedent("""
        import sys
        with open(sys.argv[1], "a") as f:
            f.write("unit: other\\n")
    """))
    monkeypatch.setenv("VISUAL", f"{sys.executable} {script}")
    out = out_of(capsys, sh, "use counter", "edit deps")
    assert "saved" in out
    assert load_unit(sh.cfg.root, "counter").deps() == ["other"]
    assert "can edit" in out_of(capsys, sh, "edit meta")


def test_empty_line_does_not_repeat(sh, capsys, ollama):
    out_of(capsys, sh, "use counter", "plan")
    load_unit(sh.cfg.root, "counter").path("input.md").write_text("more\n")
    sh.lastcmd = "plan"
    sh.onecmd("")
    assert rounds(load_unit(sh.cfg.root, "counter")) == [1]


def test_clean_and_quit(sh, capsys):
    out_of(capsys, sh, "use counter", "plan")
    assert "clean" in out_of(capsys, sh, "clean -y")
    assert sh.onecmd("quit") is True
    assert sh.onecmd("EOF") is True
    assert "unknown command" in out_of(capsys, sh, "frobnicate")


def test_cli_starts_repl(project, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO("use counter\nspec\nquit\n"))
    assert cli.main(["--root", str(project)]) == 0
    assert cli.main(["--root", str(project), "repl", "counter"]) == 0
    assert "IntentCompiler shell" in capsys.readouterr().out
