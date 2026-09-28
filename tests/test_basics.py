import pytest

from ic import config
from ic.prompt import render
from ic.unit import create_unit, load_unit, unit_names


def test_config_defaults_and_selection(cfg):
    assert cfg.language == "julia"
    assert cfg.endpoint_for("plan").name == "fake"
    assert cfg.endpoint_for("plan", "other").model == "other-model"
    assert cfg.endpoint_for("impl").name == "fake"          # first defined
    with pytest.raises(KeyError, match="unknown endpoint 'nope'"):
        cfg.endpoint_for("plan", "nope")


def test_config_requires_endpoints(tmp_path):
    (tmp_path / "ic.toml").write_text('language = "python"\n')
    with pytest.raises(ValueError, match="no \\[endpoints"):
        config.load(tmp_path)


def test_find_root_searches_upward(project):
    deep = project / "units" / "counter"
    assert config.find_root(deep) == project.resolve()


def test_render_does_not_reexpand_values(project):
    p = render("plan", project, {"unit": "u", "input": "costs $x and ${y}",
                                 "deps_section": "", "current_plan": "", "language": "julia"})
    assert "costs $x and ${y}" in p.user
    assert "Target language: julia" in p.system
    assert p.source == "ic:templates/plan.md"


def test_render_project_override(project):
    (project / "templates").mkdir()
    (project / "templates" / "plan.md").write_text("=== system ===\nS $unit\n=== user ===\nU\n")
    p = render("plan", project, {"unit": "u"})
    assert (p.system, p.user) == ("S u", "U")
    assert p.source.endswith("templates/plan.md")


def test_render_needs_markers(project):
    (project / "templates").mkdir()
    (project / "templates" / "plan.md").write_text("no markers")
    with pytest.raises(ValueError, match="needs"):
        render("plan", project, {})


def test_deps_parsing(project):
    unit = load_unit(project, "counter")
    assert unit.deps() == []
    unit.path("deps").write_text("# comment\n\nunit: a\nunit:  b \n")
    assert unit.deps() == ["a", "b"]
    unit.path("deps").write_text("lib: a\n")
    with pytest.raises(ValueError, match="line 1"):
        unit.deps()


def test_create_and_list_units(project):
    create_unit(project, "b-unit")
    assert unit_names(project) == ["b-unit", "counter"]
    assert load_unit(project, "b-unit").read("input.md") == ""
    with pytest.raises(FileExistsError):
        create_unit(project, "counter")
    with pytest.raises(ValueError, match="invalid"):
        create_unit(project, "../escape")
    with pytest.raises(FileNotFoundError):
        load_unit(project, "missing")
