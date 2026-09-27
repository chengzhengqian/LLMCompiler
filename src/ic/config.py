"""Project configuration: locate and parse ic.toml."""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_NAME = "ic.toml"


@dataclass
class Endpoint:
    name: str
    url: str
    model: str
    think: bool | None = None          # None: don't send the flag at all
    options: dict = field(default_factory=dict)


@dataclass
class Config:
    root: Path
    language: str
    endpoints: dict[str, Endpoint]
    stages: dict[str, str]

    def endpoint_for(self, stage: str, override: str | None = None) -> Endpoint:
        """Pick an endpoint: --endpoint flag, then [stages], then the first defined."""
        name = override or self.stages.get(stage) or next(iter(self.endpoints))
        if name not in self.endpoints:
            known = ", ".join(self.endpoints)
            raise KeyError(f"unknown endpoint '{name}' (configured: {known})")
        return self.endpoints[name]


def find_root(start: Path) -> Path | None:
    """Search upward from start for a directory containing ic.toml."""
    start = start.resolve()
    for d in [start, *start.parents]:
        if (d / CONFIG_NAME).is_file():
            return d
    return None


def load(root: Path) -> Config:
    data = tomllib.loads((root / CONFIG_NAME).read_text())
    endpoints = {
        name: Endpoint(
            name=name,
            url=spec["url"].rstrip("/"),
            model=spec["model"],
            think=spec.get("think"),
            options=spec.get("options", {}),
        )
        for name, spec in data.get("endpoints", {}).items()
    }
    if not endpoints:
        raise ValueError(f"{root / CONFIG_NAME}: no [endpoints.*] defined")
    return Config(
        root=root,
        language=data.get("language", "python"),
        endpoints=endpoints,
        stages=data.get("stages", {}),
    )
