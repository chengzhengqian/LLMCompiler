"""A unit is a directory under units/ holding one piece of intent and its artifacts."""

import re
from dataclasses import dataclass
from pathlib import Path

UNIT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")


@dataclass
class Unit:
    name: str
    dir: Path

    def path(self, filename: str) -> Path:
        return self.dir / filename

    def has(self, filename: str) -> bool:
        return self.path(filename).is_file()

    def read(self, filename: str) -> str:
        p = self.path(filename)
        if not p.is_file():
            raise FileNotFoundError(f"{self.name}: missing {filename}")
        return p.read_text()

    def deps(self) -> list[str]:
        """Dependency unit names from the deps file. No file means no deps.

        Format, one per line:   unit: <name>
        Blank lines and lines starting with # are ignored.
        """
        if not self.has("deps"):
            return []
        names = []
        for n, line in enumerate(self.read("deps").splitlines(), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            kind, _, value = line.partition(":")
            if kind.strip() != "unit" or not value.strip():
                raise ValueError(f"{self.name}/deps line {n}: expected 'unit: <name>'")
            names.append(value.strip())
        return names


def load_unit(root: Path, name: str) -> Unit:
    d = root / "units" / name
    if not d.is_dir():
        raise FileNotFoundError(f"unit directory not found: {d}")
    return Unit(name=name, dir=d)


def unit_names(root: Path) -> list[str]:
    """Names of all unit directories under units/, sorted."""
    d = root / "units"
    return sorted(p.name for p in d.iterdir() if p.is_dir()) if d.is_dir() else []


def create_unit(root: Path, name: str) -> Unit:
    """Make units/<name>/ with an empty input.md."""
    if not UNIT_NAME.fullmatch(name):
        raise ValueError(f"invalid unit name '{name}' (letters, digits, _ . -)")
    d = root / "units" / name
    if d.exists():
        raise FileExistsError(f"unit already exists: {d}")
    d.mkdir(parents=True)
    (d / "input.md").write_text("")
    return Unit(name=name, dir=d)
