"""Prompt templates: load (project override first), render, split into system/user.

Template files contain two sections, each starting with a marker line:

    === system ===
    ...
    === user ===
    ...

Placeholders use $name (string.Template). Values inserted are not re-expanded,
so $ inside intents or specs is safe; only the template itself must avoid stray $.
"""

from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from string import Template

SYSTEM_MARK = "=== system ==="
USER_MARK = "=== user ==="


@dataclass
class Prompt:
    system: str
    user: str
    source: str          # where the template came from, for the record

    def as_text(self) -> str:
        return f"{SYSTEM_MARK}\n{self.system}\n\n{USER_MARK}\n{self.user}\n"


def load_template(stage: str, root: Path) -> tuple[str, str]:
    override = root / "templates" / f"{stage}.md"
    if override.is_file():
        return override.read_text(), str(override)
    builtin = files("ic") / "templates" / f"{stage}.md"
    return builtin.read_text(), f"ic:templates/{stage}.md"


def render(stage: str, root: Path, values: dict[str, str]) -> Prompt:
    text, source = load_template(stage, root)
    filled = Template(text).safe_substitute(values)
    if SYSTEM_MARK not in filled or USER_MARK not in filled:
        raise ValueError(f"template {source}: needs '{SYSTEM_MARK}' and '{USER_MARK}' lines")
    _, rest = filled.split(SYSTEM_MARK, 1)
    system, user = rest.split(USER_MARK, 1)
    return Prompt(system=system.strip(), user=user.strip(), source=source)
