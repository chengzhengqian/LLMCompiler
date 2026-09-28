"""Round records: one directory per round under <unit>/.build/.

    .build/round-001/   input.md prompt.md response.md [thinking.md]
                        [choices.md] [questions.md] meta.json
    .build/accepted.json   which round downstream units may use
"""

import hashlib
import json
from pathlib import Path

from .unit import Unit

ACCEPTED = "accepted.json"


def short_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def build_dir(unit: Unit) -> Path:
    return unit.dir / ".build"


def rounds(unit: Unit) -> list[int]:
    """Existing round numbers, ascending."""
    d = build_dir(unit)
    if not d.is_dir():
        return []
    nums = []
    for p in d.glob("round-*"):
        try:
            nums.append(int(p.name.split("-", 1)[1]))
        except ValueError:
            pass
    return sorted(nums)


def round_dir(unit: Unit, n: int) -> Path:
    return build_dir(unit) / f"round-{n:03d}"


def new_round(unit: Unit) -> tuple[int, Path]:
    existing = rounds(unit)
    n = (existing[-1] + 1) if existing else 1
    d = round_dir(unit, n)
    d.mkdir(parents=True, exist_ok=False)
    return n, d


def read_json(path: Path) -> dict | None:
    return json.loads(path.read_text()) if path.is_file() else None


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def last_successful_round(unit: Unit) -> tuple[int, dict] | None:
    """Most recent round whose meta says it produced a plan."""
    for n in reversed(rounds(unit)):
        meta = read_json(round_dir(unit, n) / "meta.json")
        if meta and meta.get("status") == "ok":
            return n, meta
    return None


def accepted(unit: Unit) -> dict | None:
    return read_json(build_dir(unit) / ACCEPTED)
