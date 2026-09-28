"""Interactive shell: focus on a unit, view and edit its files, run stages.

    $ ic                       (or: ic repl [unit])
    ic> use fock-basis
    ic:fock-basis> edit        opens input.md in $VISUAL / $EDITOR
    ic:fock-basis> plan        runs a round
    ic:fock-basis> spec        view the result
    ic:fock-basis> accept

Every command maps onto the same functions as the one-shot CLI, so a round
run here is recorded exactly like `ic plan <unit>`.
"""

import argparse
import cmd
import inspect
import os
import pydoc
import shlex
import shutil
import subprocess
import sys

from . import plan
from .config import Config
from .llm import list_models
from .record import read_json, round_dir, rounds
from .unit import Unit, create_unit, load_unit, unit_names

HISTORY = ".ic_history"

# Files the `show` command knows. Unit files live in the unit directory;
# round files live in .build/round-NNN/ (latest round unless one is given).
UNIT_FILES = {"input": "input.md", "intent": "intent.md", "spec": "spec.md", "deps": "deps"}
ROUND_FILES = {"choices": "choices.md", "questions": "questions.md", "prompt": "prompt.md",
               "response": "response.md", "thinking": "thinking.md", "meta": "meta.json",
               "archived": "input.md"}
EDITABLE = ["input", "deps", "intent", "spec"]
DEPS_TEMPLATE = "# one dependency per line:  unit: <name>\n"


class Quit(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    """argparse that raises instead of exiting the shell."""

    def error(self, message):
        raise ValueError(f"{self.prog}: {message}")

    def exit(self, status=0, message=None):
        if message:
            print(message, end="")
        raise _ParsedExit()


class _ParsedExit(Exception):
    """-h was given; help has been printed."""


def _plan_parser() -> _Parser:
    p = _Parser(prog="plan", description="run a plan round from input.md (status if empty)")
    p.add_argument("-e", "--endpoint", help="endpoint name for this round")
    p.add_argument("-n", "--dry-run", action="store_true", help="print the prompt only")
    p.add_argument("--full", action="store_true", help="stream the whole reply")
    return p


def page(text: str) -> None:
    """Print, through a pager when the text is taller than the terminal."""
    rows = shutil.get_terminal_size((80, 24)).lines
    if sys.stdout.isatty() and text.count("\n") >= rows - 2:
        pydoc.pager(text)
    else:
        print(text.rstrip("\n"))


def editor_command() -> list[str]:
    return shlex.split(os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vi")


class Repl(cmd.Cmd):
    intro = "IntentCompiler shell. `help` lists commands, `quit` or Ctrl-D leaves."

    def __init__(self, cfg: Config, unit: str | None = None):
        super().__init__()
        self.cfg = cfg
        self.unit: Unit | None = None
        self.endpoint: str | None = None      # session override for -e
        if unit:
            self.unit = load_unit(cfg.root, unit)
        self._update_prompt()

    # ------------------------------------------------------------ plumbing

    def _update_prompt(self) -> None:
        tag = self.unit.name if self.unit else ""
        ep = f" @{self.endpoint}" if self.endpoint else ""
        self.prompt = f"ic{':' if tag else ''}{tag}{ep}> "

    def _focus(self) -> Unit:
        if self.unit is None:
            raise ValueError("no unit in focus — `use <unit>` (or `units` to list)")
        return self.unit

    def onecmd(self, line: str) -> bool:
        try:
            return bool(super().onecmd(line))
        except Quit:
            return True
        except _ParsedExit:
            return False
        except (OSError, KeyError, ValueError, RuntimeError) as e:
            msg = e.args[0] if isinstance(e, KeyError) and e.args else e
            print(f"error: {msg}")
        except KeyboardInterrupt:
            print("\ninterrupted")
        return False

    def postcmd(self, stop, line):
        self._update_prompt()
        return stop

    def emptyline(self):
        # The cmd default repeats the last command; never rerun `plan` by accident.
        return False

    def default(self, line):
        print(f"unknown command: {line.split()[0]}  (try `help`)")

    def cmdloop(self, intro=None):
        self._history(load=True)
        try:
            while True:
                try:
                    super().cmdloop(intro)
                    break
                except KeyboardInterrupt:
                    print("^C")
                    intro = ""
        finally:
            self._history(load=False)

    def _history(self, load: bool) -> None:
        try:
            import readline
        except ImportError:
            return
        path = self.cfg.root / HISTORY
        try:
            if load:
                readline.set_completer_delims(" \t\n")
                if path.is_file():
                    readline.read_history_file(path)
            else:
                readline.set_history_length(1000)
                readline.write_history_file(path)
        except OSError:
            pass

    def _complete_from(self, options, text):
        return [o for o in options if o.startswith(text)]

    # ------------------------------------------------------------ units

    def do_units(self, arg):
        """units — list units with their state (* marks the focused one)."""
        names = unit_names(self.cfg.root)
        if not names:
            print("no units yet — `new <name>` creates one")
            return
        width = max(map(len, names))
        for name in names:
            mark = "*" if self.unit and self.unit.name == name else " "
            print(f"{mark} {name:{width}}  {plan.brief(load_unit(self.cfg.root, name))}")

    do_ls = do_units

    def do_use(self, arg):
        """use <unit> — focus on a unit; later commands act on it. No argument: show focus."""
        name = arg.strip()
        if not name:
            print(self.unit.name if self.unit else "no unit in focus")
            return
        self.unit = load_unit(self.cfg.root, name)
        print(f"{name}: {plan.brief(self.unit)}")

    do_cd = do_use

    def complete_use(self, text, *_):
        return self._complete_from(unit_names(self.cfg.root), text)

    complete_cd = complete_use

    def do_new(self, arg):
        """new <unit> — create units/<unit>/ with an empty input.md and focus on it."""
        name = arg.strip()
        if not name:
            raise ValueError("usage: new <unit>")
        self.unit = create_unit(self.cfg.root, name)
        print(f"created {self.unit.dir.relative_to(self.cfg.root)}/ — `edit` to write its input")

    def do_status(self, arg):
        """status — rounds, acceptance, hand edits and open questions of the focused unit."""
        plan.status(self._focus())

    do_st = do_status

    def do_rounds(self, arg):
        """rounds — one line per recorded round: status, model, time, choices/questions."""
        unit = self._focus()
        nums = rounds(unit)
        if not nums:
            print(f"{unit.name}: no rounds yet")
            return
        acc = plan.accepted(unit)
        for n in nums:
            d = round_dir(unit, n)
            meta = read_json(d / "meta.json") or {}
            flags = []
            for f, label in (("choices.md", "choices"), ("questions.md", "questions")):
                if (d / f).is_file():
                    count = sum(1 for ln in (d / f).read_text().splitlines()
                                if ln.lstrip().startswith(("-", "*")))
                    if count == 1:
                        label = label[:-1]
                    flags.append(f"{count or '?'} {label}")
            first = ""
            if (d / "input.md").is_file():
                lines = [ln for ln in (d / "input.md").read_text().splitlines()
                         if ln.strip() and not ln.lstrip().startswith("#")]
                first = lines[0].strip() if lines else ""
                if len(first) > 50:
                    first = first[:49] + "…"
            secs = f"{meta['seconds']:.0f}s" if meta.get("seconds") is not None else "-"
            mark = "A" if acc and acc["round"] == n else " "
            print(f"{mark} {n:03d}  {meta.get('status', '?'):9} {meta.get('model', '?'):14} "
                  f"{secs:>5}  {', '.join(flags) or '-':24} {first}")

    do_log = do_rounds

    # ------------------------------------------------------------ viewing

    def do_show(self, arg):
        """show [what] [round] — view a file of the focused unit (default: intent + spec).

        Unit files:   input intent spec deps plan
        Round files:  choices questions prompt response thinking meta archived
                      (latest round, or the round number given; `archived` is
                      the input.md that round consumed)"""
        unit = self._focus()
        words = arg.split()
        what = words[0] if words else "plan"
        if what == "plan":
            self._show_unit(unit, "intent")
            print()
            self._show_unit(unit, "spec")
        elif what in UNIT_FILES:
            if len(words) > 1:
                raise ValueError(f"`show {what}` takes no round number (it is the current file)")
            self._show_unit(unit, what)
        elif what in ROUND_FILES:
            n = self._round_arg(unit, words[1] if len(words) > 1 else None)
            path = round_dir(unit, n) / ROUND_FILES[what]
            if not path.is_file():
                print(f"round {n:03d} has no {path.name}")
                return
            page(f"── {unit.name} round {n:03d} {path.name} ──\n{path.read_text()}")
        else:
            known = ", ".join(["plan", *UNIT_FILES, *ROUND_FILES])
            raise ValueError(f"unknown file '{what}' (one of: {known})")

    def complete_show(self, text, *_):
        return self._complete_from(["plan", *UNIT_FILES, *ROUND_FILES], text)

    def _show_unit(self, unit: Unit, what: str) -> None:
        name = UNIT_FILES[what]
        if not unit.has(name):
            print(f"── {unit.name}/{name} ── (does not exist)")
            return
        text = unit.read(name)
        page(f"── {unit.name}/{name} ──\n{text if text.strip() else '(empty)'}")

    def _round_arg(self, unit: Unit, arg: str | None) -> int:
        nums = rounds(unit)
        if not nums:
            raise ValueError(f"{unit.name}: no rounds yet")
        if arg is None:
            return nums[-1]
        try:
            n = int(arg)
        except ValueError:
            raise ValueError(f"round must be a number, got '{arg}'")
        if n not in nums:
            raise ValueError(f"{unit.name}: no round {n:03d} (have {nums[0]:03d}–{nums[-1]:03d})")
        return n

    def do_input(self, arg):
        """input — show input.md of the focused unit."""
        self.do_show("input")

    def do_intent(self, arg):
        """intent — show intent.md of the focused unit."""
        self.do_show("intent")

    def do_spec(self, arg):
        """spec — show spec.md of the focused unit."""
        self.do_show("spec")

    def do_questions(self, arg):
        """questions [round] — open questions from the latest (or given) round."""
        self.do_show(f"questions {arg}".strip())

    def do_choices(self, arg):
        """choices [round] — choices the model made in the latest (or given) round."""
        self.do_show(f"choices {arg}".strip())

    # ------------------------------------------------------------ editing

    def do_edit(self, arg):
        """edit [input|deps|intent|spec] — open a unit file in $VISUAL / $EDITOR (default: input).

        Editing intent or spec by hand is allowed, but `accept` will refuse until
        the change has gone through a round; prefer writing it in input."""
        unit = self._focus()
        what = arg.strip() or "input"
        if what not in EDITABLE:
            raise ValueError(f"can edit: {', '.join(EDITABLE)}")
        path = unit.path(UNIT_FILES[what])
        if not path.exists():
            path.write_text(DEPS_TEMPLATE if what == "deps" else "")
        if what in ("intent", "spec"):
            print(f"note: hand edits to {path.name} block `accept` until a round records them")
        before = path.read_text()
        subprocess.run([*editor_command(), str(path)], check=False)
        after = path.read_text() if path.exists() else ""
        print(f"{path.name}: {'unchanged' if after == before else 'saved'}")

    def complete_edit(self, text, *_):
        return self._complete_from(EDITABLE, text)

    def do_add(self, arg):
        """add <text> — append a line to input.md without opening an editor."""
        unit = self._focus()
        if not arg.strip():
            raise ValueError("usage: add <text>")
        current = unit.read("input.md") if unit.has("input.md") else ""
        if current and not current.endswith("\n"):
            current += "\n"
        unit.path("input.md").write_text(current + arg.strip() + "\n")
        print(f"input.md: {len(unit.read('input.md').splitlines())} line(s)")

    def do_clear(self, arg):
        """clear — empty input.md (nothing is archived; only rounds archive input)."""
        unit = self._focus()
        unit.path("input.md").write_text("")
        print("input.md cleared")

    # ------------------------------------------------------------ stages

    def do_plan(self, arg):
        """plan [-n] [--full] [-e NAME] — run a round from input.md; status if input is empty."""
        unit = self._focus()
        opts = _plan_parser().parse_args(shlex.split(arg))
        endpoint = self.cfg.endpoint_for("plan", opts.endpoint or self.endpoint)
        plan.plan(self.cfg, unit, endpoint, accept_flag=False,
                  dry_run=opts.dry_run, full=opts.full)

    def do_accept(self, arg):
        """accept — mark the current plan as usable by dependent units."""
        plan.accept(self.cfg, self._focus())

    def do_clean(self, arg):
        """clean [-y] — remove plan and history of the focused unit; keep input.md."""
        plan.clean(self._focus(), yes=arg.strip() in ("-y", "--yes"))

    def do_endpoint(self, arg):
        """endpoint [NAME|-] — show or set the endpoint for this session (- resets to ic.toml)."""
        name = arg.strip()
        if not name:
            current = self.cfg.endpoint_for("plan", self.endpoint)
            src = "session" if self.endpoint else "ic.toml"
            print(f"{current.name}  ({current.model} @ {current.url}, from {src})")
            return
        if name == "-":
            self.endpoint = None
        else:
            self.cfg.endpoint_for("plan", name)       # validates the name
            self.endpoint = name
        self.do_endpoint("")

    def complete_endpoint(self, text, *_):
        return self._complete_from([*self.cfg.endpoints, "-"], text)

    def do_endpoints(self, arg):
        """endpoints — list configured endpoints and check each responds."""
        for name, ep in self.cfg.endpoints.items():
            try:
                status = "ok" if ep.model in list_models(ep) else "reachable, but model not found"
            except RuntimeError as e:
                status = str(e)
            print(f"{name:14} {ep.model:18} {ep.url:28} {status}")

    # ------------------------------------------------------------ misc

    def do_shell(self, arg):
        """!<command> — run a shell command in the project root."""
        subprocess.run(arg, shell=True, cwd=self.cfg.root, check=False)

    def do_quit(self, arg):
        """quit — leave the shell (also: exit, Ctrl-D)."""
        raise Quit()

    do_exit = do_quit

    def do_EOF(self, arg):
        print()
        raise Quit()

    def do_help(self, arg):
        if not arg:
            print(HELP)
            return
        doc = getattr(getattr(self, f"do_{arg}", None), "__doc__", None)
        print(inspect.cleandoc(doc) if doc else f"no help for '{arg}'")


HELP = """\
units | ls                 list units and their state
use | cd <unit>            focus on a unit
new <unit>                 create a unit and focus on it
status | st                state of the focused unit
rounds | log               one line per recorded round

show [what] [round]        view a file (default: intent + spec)
input  intent  spec        shortcuts for `show input` etc.
questions  choices [n]     from the latest (or given) round

edit [input|deps|intent|spec]   open in $VISUAL / $EDITOR (default: input)
add <text>                 append a line to input.md
clear                      empty input.md

plan [-n] [--full] [-e NAME]    run a round (status if input is empty)
accept                     mark the current plan usable by dependents
clean [-y]                 remove plan and history, keep input.md

endpoint [NAME|-]          show / set the session endpoint
endpoints                  check configured endpoints
!<command>                 shell command in the project root
help <command>             details;  quit | exit | Ctrl-D to leave"""


def run(cfg: Config, unit: str | None = None) -> int:
    Repl(cfg, unit).cmdloop()
    return 0
