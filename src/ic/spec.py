"""Stage: intent → spec.

Reads intent.md plus the approved spec.md of each dependency, renders the spec
template, calls the model, and writes spec.draft.md. Approval is a human act:
review the draft, edit if needed, and rename it to spec.md.
"""

import sys

from .config import Config, Endpoint
from .llm import chat
from .prompt import render
from .record import new_run_dir, short_hash, write_meta
from .unit import Unit, load_unit

DRAFT = "spec.draft.md"


def _strip_outer_fence(text: str) -> str:
    """Remove a single ```...``` wrapper if the model put one around everything."""
    lines = text.strip().splitlines()
    if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return text.strip()


def gather_inputs(cfg: Config, unit: Unit) -> tuple[dict[str, str], dict[str, str]]:
    """Template values, and a map of input file -> content hash for the record."""
    intent = unit.read("intent.md")
    hashes = {f"{unit.name}/intent.md": short_hash(intent)}

    parts = []
    for dep in unit.deps():
        dep_unit = load_unit(cfg.root, dep)
        if not dep_unit.has("spec.md"):
            raise FileNotFoundError(
                f"dependency '{dep}' has no approved spec.md — run and approve its spec first")
        text = dep_unit.read("spec.md")
        hashes[f"{dep}/spec.md"] = short_hash(text)
        parts.append(f"## Dependency: unit \"{dep}\"\n\n{text.strip()}")

    if parts:
        deps_section = "# Dependency specifications\n\n" + "\n\n".join(parts)
    else:
        deps_section = "(This unit has no dependencies.)"

    values = {
        "unit": unit.name,
        "intent": intent.strip(),
        "deps_section": deps_section,
        "language": cfg.language,
    }
    return values, hashes


def run(cfg: Config, unit: Unit, endpoint: Endpoint, dry_run: bool = False) -> int:
    values, hashes = gather_inputs(cfg, unit)
    prompt = render("spec", cfg.root, values)

    print(f"endpoint: {endpoint.name}  ({endpoint.model} @ {endpoint.url})")
    print(f"template: {prompt.source}")
    for path, h in hashes.items():
        print(f"input:    {path}  {h}")

    if dry_run:
        print("\n" + prompt.as_text())
        return 0

    run_dir = new_run_dir(unit, "spec")
    (run_dir / "prompt.md").write_text(prompt.as_text())
    print(f"record:   {run_dir.relative_to(cfg.root)}")
    print("-" * 60)

    reply = chat(endpoint, prompt.system, prompt.user, stream_to=sys.stdout)
    print("\n" + "-" * 60)

    (run_dir / "response.md").write_text(reply.text + "\n")
    if reply.thinking:
        (run_dir / "thinking.md").write_text(reply.thinking + "\n")

    spec_text = _strip_outer_fence(reply.text)
    unit.path(DRAFT).write_text(spec_text + "\n")

    write_meta(run_dir, {
        "stage": "spec",
        "unit": unit.name,
        "endpoint": endpoint.name,
        "model": endpoint.model,
        "url": endpoint.url,
        "template": prompt.source,
        "inputs": hashes,
        "output": {DRAFT: short_hash(spec_text)},
        "seconds": round(reply.seconds, 1),
        "eval_count": reply.eval_count,
    })

    print(f"wrote {unit.name}/{DRAFT}  ({reply.seconds:.0f}s)")
    print(f"review it, then approve with:  mv {DRAFT} spec.md")
    return 0
