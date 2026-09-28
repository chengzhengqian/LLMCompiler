"""Stage: plan (intent.md + spec.md), maintained by the LLM from human input.md.

    ic plan <unit>            input.md non-empty → run a round
                              input.md empty     → show status
    ic plan <unit> --accept   mark the current plan as usable downstream

First round vs. later rounds is decided by whether intent.md and spec.md exist.
"""

import os
import re
import shutil
import sys

from .config import Config, Endpoint
from .display import LiveLine, stream_report, summary
from .llm import chat
from .prompt import render
from .record import (
    ACCEPTED, accepted, build_dir, last_successful_round, new_round, round_dir,
    rounds, short_hash, write_json,
)
from .unit import Unit, load_unit

INPUT, INTENT, SPEC = "input.md", "intent.md", "spec.md"
SECTIONS = ["INTENT", "SPEC", "CHOICES", "QUESTIONS"]


# ---------------------------------------------------------------- helpers

def _strip_outer_fence(text: str) -> str:
    lines = text.strip().splitlines()
    if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return text.strip()


def parse_reply(text: str) -> dict[str, str]:
    """Split the reply on '=== NAME ===' marker lines."""
    pattern = re.compile(r"^=== (" + "|".join(SECTIONS) + r") ===\s*$", re.M)
    matches = list(pattern.finditer(text))
    parts = {}
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        parts[m.group(1)] = _strip_outer_fence(text[m.end():end])
    missing = [s for s in ("INTENT", "SPEC") if not parts.get(s)]
    if missing:
        raise ValueError(f"reply is missing section(s): {', '.join(missing)}")
    for s in ("CHOICES", "QUESTIONS"):
        if parts.get(s, "").strip().strip("-*() ").lower() in ("", "none"):
            parts[s] = ""
    return parts


def plan_state(unit: Unit) -> str:
    """'none', 'present', or raise if only one of the two files exists."""
    has_i, has_s = unit.has(INTENT), unit.has(SPEC)
    if has_i and has_s:
        return "present"
    if not has_i and not has_s:
        return "none"
    missing = SPEC if has_i else INTENT
    raise FileNotFoundError(
        f"{unit.name}: {missing} is missing but its partner exists. Restore it from "
        f"the last round in .build/, or run `ic clean {unit.name}` to start over.")


def hand_edited(unit: Unit) -> list[str]:
    """Plan files whose content differs from what the last round wrote."""
    last = last_successful_round(unit)
    if not last:
        return []
    outputs = last[1].get("outputs", {})
    return [f for f in (INTENT, SPEC)
            if unit.has(f) and outputs.get(f) != short_hash(unit.read(f))]


def _write_atomic(unit: Unit, files: dict[str, str]) -> None:
    for name, text in files.items():
        unit.path(name + ".tmp").write_text(text)
    for name in files:
        os.replace(unit.path(name + ".tmp"), unit.path(name))


# ---------------------------------------------------------------- inputs

def gather(cfg: Config, unit: Unit) -> tuple[dict[str, str], dict[str, str]]:
    """Template values and input hashes for the record."""
    human = unit.read(INPUT)
    hashes = {f"{unit.name}/{INPUT}": short_hash(human)}

    dep_parts = []
    for dep in unit.deps():
        du = load_unit(cfg.root, dep)
        acc = accepted(du)
        if not acc or not du.has(SPEC) or acc["outputs"][SPEC] != short_hash(du.read(SPEC)):
            raise FileNotFoundError(
                f"dependency '{dep}' has no accepted plan matching its current spec.md "
                f"— run `ic plan {dep} --accept` first")
        text = du.read(SPEC)
        hashes[f"{dep}/{SPEC}"] = short_hash(text)
        dep_parts.append(f"## Dependency: unit \"{dep}\"\n\n{text.strip()}")
    deps_section = ("# Dependency specifications\n\n" + "\n\n".join(dep_parts)
                    if dep_parts else "(This unit has no dependencies.)")

    if plan_state(unit) == "present":
        intent, spec = unit.read(INTENT), unit.read(SPEC)
        hashes[f"{unit.name}/{INTENT}"] = short_hash(intent)
        hashes[f"{unit.name}/{SPEC}"] = short_hash(spec)
        current = (f"# Current plan\n\n=== INTENT ===\n{intent.strip()}\n\n"
                   f"=== SPEC ===\n{spec.strip()}")
    else:
        current = "(No plan exists yet. Write it from the human input.)"

    values = {"unit": unit.name, "input": human.strip(), "deps_section": deps_section,
              "current_plan": current, "language": cfg.language}
    return values, hashes


# ---------------------------------------------------------------- commands

def status(unit: Unit) -> int:
    state = plan_state(unit)
    nums = rounds(unit)
    print(f"unit:     {unit.name}")
    print(f"plan:     {'exists' if state == 'present' else 'not yet created'}")
    print(f"rounds:   {len(nums)}" + (f" (latest {nums[-1]:03d})" if nums else ""))
    last = last_successful_round(unit)
    acc = accepted(unit)
    if acc:
        current = last and acc["round"] == last[0]
        print(f"accepted: round {acc['round']:03d}" + ("" if current else "  (newer rounds exist)"))
    else:
        print("accepted: no")
    edited = hand_edited(unit)
    if edited:
        print(f"warning:  {', '.join(edited)} changed since the last round wrote it")
    if last:
        q = round_dir(unit, last[0]) / "questions.md"
        if q.is_file():
            print(f"\nopen questions from round {last[0]:03d}:\n{q.read_text().rstrip()}")
    if not unit.has(INPUT) or not unit.read(INPUT).strip():
        print(f"\n{INPUT} is empty — write your input there to run a round.")
    return 0


def brief(unit: Unit) -> str:
    """One-line state of a unit, for listings."""
    try:
        state = plan_state(unit)
    except FileNotFoundError:
        return "broken: intent.md/spec.md out of pair"
    nums = rounds(unit)
    parts = [f"{len(nums)} round{'' if len(nums) == 1 else 's'}",
             "plan" if state == "present" else "no plan"]
    acc, last = accepted(unit), last_successful_round(unit)
    if acc:
        parts.append(f"accepted {acc['round']:03d}"
                     + ("" if last and acc["round"] == last[0] else " (stale)"))
    if unit.has(INPUT) and unit.read(INPUT).strip():
        parts.append("input pending")
    if hand_edited(unit):
        parts.append("hand-edited")
    if last and (round_dir(unit, last[0]) / "questions.md").is_file():
        parts.append("open questions")
    return " · ".join(parts)


def run_round(cfg: Config, unit: Unit, endpoint: Endpoint,
              dry_run: bool = False, full: bool = False) -> int:
    values, hashes = gather(cfg, unit)
    first = plan_state(unit) == "none"
    prompt = render("plan", cfg.root, values)

    print(f"endpoint: {endpoint.name}  ({endpoint.model} @ {endpoint.url})")
    print(f"template: {prompt.source}")
    print(f"round:    {'first' if first else 'revision'}")
    for path, h in hashes.items():
        print(f"input:    {path}  {h}")
    edited = hand_edited(unit)
    if edited:
        print(f"warning:  {', '.join(edited)} were edited by hand; the edits go in as current plan")

    if dry_run:
        print("\n" + prompt.as_text())
        return 0

    n, rdir = new_round(unit)
    prev = last_successful_round(unit)
    shutil.copy(unit.path(INPUT), rdir / INPUT)
    (rdir / "prompt.md").write_text(prompt.as_text())
    meta = {"stage": "plan", "round": n, "parent": prev[0] if prev else None,
            "endpoint": endpoint.name, "model": endpoint.model, "url": endpoint.url,
            "template": prompt.source, "inputs": hashes, "status": "running"}
    write_json(rdir / "meta.json", meta)
    print(f"record:   {rdir.relative_to(cfg.root)}")

    try:
        if full:
            print("-" * 60)
            reply = chat(endpoint, prompt.system, prompt.user,
                         on_chunk=lambda kind, text: (sys.stdout.write(text), sys.stdout.flush()))
            print("\n" + "-" * 60)
        else:
            with LiveLine() as live:
                reply = chat(endpoint, prompt.system, prompt.user, on_chunk=live.feed)
    except BaseException as e:
        meta["status"] = "failed"
        meta["error"] = str(e) or type(e).__name__
        write_json(rdir / "meta.json", meta)
        raise
    print(summary(reply))
    print(stream_report(reply.stream))
    write_json(rdir / "stream.json", reply.stream.to_dict())

    (rdir / "response.md").write_text(reply.text + "\n")
    if reply.thinking:
        (rdir / "thinking.md").write_text(reply.thinking + "\n")
    meta.update(seconds=round(reply.seconds, 1), eval_count=reply.eval_count,
                tokens_per_second=round(reply.rate, 2) if reply.rate else None,
                prompt_tokens=reply.prompt_count)

    try:
        parts = parse_reply(reply.text)
    except ValueError as e:
        meta.update(status="unparsed", error=str(e))
        write_json(rdir / "meta.json", meta)
        raise ValueError(f"{e}. Plan and {INPUT} left unchanged; "
                         f"raw reply is in {rdir.relative_to(cfg.root)}/response.md")

    intent, spec = parts["INTENT"] + "\n", parts["SPEC"] + "\n"
    _write_atomic(unit, {INTENT: intent, SPEC: spec})
    for key in ("CHOICES", "QUESTIONS"):
        if parts[key]:
            (rdir / f"{key.lower()}.md").write_text(parts[key] + "\n")
    unit.path(INPUT).write_text("")          # consumed; archived in the record

    meta.update(status="ok", outputs={INTENT: short_hash(intent), SPEC: short_hash(spec)})
    write_json(rdir / "meta.json", meta)

    print(f"round {n:03d} done: wrote {INTENT}, {SPEC}")
    if parts["CHOICES"]:
        print(f"\nchoices made:\n{parts['CHOICES']}")
    if parts["QUESTIONS"]:
        print(f"\nquestions for you:\n{parts['QUESTIONS']}")
    print(f"\nnext: review, then write changes in {INPUT} and rerun, "
          f"or `ic plan {unit.name} --accept`")
    return 0


def accept(cfg: Config, unit: Unit) -> int:
    if plan_state(unit) == "none":
        raise FileNotFoundError(f"{unit.name}: no plan to accept")
    last = last_successful_round(unit)
    if not last:
        raise FileNotFoundError(f"{unit.name}: no successful round recorded")
    edited = hand_edited(unit)
    if edited:
        raise ValueError(
            f"{', '.join(edited)} differ from what round {last[0]:03d} wrote. "
            f"Put the change in {INPUT} and run a round, so it is on record.")
    n, meta = last
    q = round_dir(unit, n) / "questions.md"
    write_json(build_dir(unit) / ACCEPTED, {"round": n, "outputs": meta["outputs"]})
    print(f"accepted round {n:03d} of {unit.name}")
    if q.is_file():
        print(f"note: round {n:03d} left open questions:\n{q.read_text().rstrip()}")
    return 0


def plan(cfg: Config, unit: Unit, endpoint: Endpoint, accept_flag: bool,
         dry_run: bool, full: bool = False) -> int:
    if accept_flag:
        return accept(cfg, unit)
    if not unit.has(INPUT) or not unit.read(INPUT).strip():
        if not unit.has(INPUT):
            unit.path(INPUT).write_text("")
        return status(unit)
    return run_round(cfg, unit, endpoint, dry_run, full)


# ---------------------------------------------------------------- clean

def clean(unit: Unit, yes: bool = False) -> int:
    """Remove intent.md, spec.md and .build/; keep input.md and deps.

    If input.md is empty, round 1's input is restored into it, so the unit
    restarts from where it began.
    """
    targets = [p for p in (unit.path(INTENT), unit.path(SPEC), build_dir(unit)) if p.exists()]
    targets += list(unit.dir.glob("*.tmp"))
    first_input = round_dir(unit, 1) / INPUT
    restore = first_input.is_file() and (not unit.has(INPUT) or not unit.read(INPUT).strip())

    if not targets:
        print(f"{unit.name}: nothing to clean")
        return 0
    print(f"will remove from {unit.name}/:")
    for p in targets:
        print(f"  {p.name}{'/' if p.is_dir() else ''}")
    if restore:
        print(f"and restore round 001's input into {INPUT}")
    if not yes:
        if input("proceed? [y/N] ").strip().lower() != "y":
            print("aborted")
            return 1

    restored = first_input.read_text() if restore else None
    for p in targets:
        shutil.rmtree(p) if p.is_dir() else p.unlink()
    if restored is not None:
        unit.path(INPUT).write_text(restored)
    print("clean")
    return 0
