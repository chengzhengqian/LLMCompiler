"""Build records: one directory per stage run under <unit>/.build/."""

import hashlib
import json
from datetime import datetime
from pathlib import Path

from .unit import Unit


def short_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def new_run_dir(unit: Unit, stage: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    d = unit.dir / ".build" / f"{stage}-{stamp}"
    d.mkdir(parents=True, exist_ok=False)
    return d


def write_meta(run_dir: Path, meta: dict) -> None:
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")

    
