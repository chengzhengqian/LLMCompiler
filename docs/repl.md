# The `ic` shell

The shell keeps one unit in focus, so you can read, edit and run rounds
without typing paths or unit names. Every stage command calls the same code
as the one-shot CLI (`ic plan <unit>`, `ic plan <unit> --accept`, …), so
a round run from the shell is recorded exactly like one run from the
command line.

## Starting

    ic                      start the shell
    ic repl                 same
    ic repl fock-basis      start with a unit already in focus
    ic --root PATH          use the project at PATH instead of searching

Like every `ic` command, the shell finds its project by looking for
`ic.toml` in the current directory and then in each parent. So you can
start it from the project root or from inside a unit directory:

    $ cd example/second_quantization
    $ uv run ic
    IntentCompiler shell. `help` lists commands, `quit` or Ctrl-D leaves.
    ic>

## The prompt

The prompt shows what the next command will act on:

    ic>                        no unit in focus
    ic:fock-basis>             commands act on units/fock-basis/
    ic:fock-basis @hudson>     ...and rounds use the `hudson` endpoint

Most commands need a unit in focus. If none is set, they reply with
`error: no unit in focus — use <unit> (or units to list)`.

## A first session

This session creates a unit, runs two rounds and accepts the result. Output
is abridged: the streaming statistics are cut, and your hashes, timings and
the model's wording will differ.

    ic> new bits
    created units/bits/ — `edit` to write its input

`new` creates `units/bits/input.md` and puts the new unit in focus. Now write
the input. `edit` opens `input.md` in your editor. For a single line, `add`
is quicker:

    ic:bits> add Helpers for UInt occupation bitsets: occupied(s, l), flip, count.
    input.md: 1 line(s)
    ic:bits> input
    ── bits/input.md ──
    Helpers for UInt occupation bitsets: occupied(s, l), flip, count.

Run a round:

    ic:bits> plan
    endpoint: littleisland  (qwen3.8:27b @ http://localhost:11434)
    template: ic:templates/plan.md
    round:    first
    input:    bits/input.md  a81badbccc6d
    record:   units/bits/.build/round-001
    ⠹ writing  412 tok  18.3 tok/s  31s │ … (live status line while streaming)
    ...
    round 001 done: wrote intent.md, spec.md

    choices made:
    - Modes are 1-indexed, mapped to bit l-1.
    - `popcount` is named `count_occupied`.

    questions for you:
    - Should modes above 64 be rejected or wrap?

The round has used up `input.md`: it is now empty, and a copy is kept in
`.build/round-001/input.md`. Read what the model wrote:

    ic:bits> intent
    ic:bits> spec
    ic:bits> show              (intent and spec, one after the other)

Answer the open question with another round:

    ic:bits> questions
    ── bits round 001 questions.md ──
    - Should modes above 64 be rejected or wrap?
    ic:bits> add Modes above 64 throw ArgumentError.
    ic:bits> plan
    ...
    round 002 done: wrote intent.md, spec.md

    choices made:
    - Out-of-range modes throw `ArgumentError`.

Look over the history and accept:

    ic:bits> rounds
      001  ok        qwen3.8:27b     269s  2 choices, 1 question    Helpers for UInt occupation bitsets: occupied(s, …
      002  ok        qwen3.8:27b     112s  1 choice                 Modes above 64 throw ArgumentError.
    ic:bits> accept
    accepted round 002 of bits

After a round, `plan` prints `next: ... or ic plan bits --accept`. That is
the CLI form of the command; in the shell, type `accept`.

## Several units and dependencies

`units` lists every unit with a one-line state. `*` marks the one in focus:

    ic:bits> units
    * bits        2 rounds · plan · accepted 002
      fock-basis  0 rounds · no plan · input pending

The state line can contain:

| Part | Meaning |
|---|---|
| `N rounds` | round records in `.build/` (ok, failed or unparsed) |
| `plan` / `no plan` | whether `intent.md` and `spec.md` exist |
| `accepted NNN` | the round dependents may use |
| `accepted NNN (stale)` | newer rounds exist since that acceptance |
| `input pending` | `input.md` has content; the next `plan` will run a round |
| `hand-edited` | `intent.md` or `spec.md` differs from what the last round wrote |
| `open questions` | the last round asked something |

Switch between units with `use` (or `cd`). Unit names tab-complete.

    ic:bits> use fock-basis
    fock-basis: 0 rounds · no plan · input pending

To make one unit depend on another, list the dependency in `deps`.
`edit deps` creates the file with a comment explaining the format:

    ic:fock-basis> edit deps
    deps: saved
    ic:fock-basis> show deps
    ── fock-basis/deps ──
    # one dependency per line:  unit: <name>
    unit: bits

A round of `fock-basis` reads the *accepted* `spec.md` of `bits`. If `bits`
has changed since it was accepted, the round refuses to run:

    ic:fock-basis> plan
    error: dependency 'bits' has no accepted plan matching its current spec.md — run `ic plan bits --accept` first
    ic:fock-basis> use bits
    ic:bits> accept
    ic:bits> use fock-basis
    ic:fock-basis> plan

## Command reference

`help` prints a one-screen summary; `help <command>` prints the details for
that command.

### Units

| Command | Does |
|---|---|
| `units`, `ls` | list units and their state |
| `use <unit>`, `cd <unit>` | focus on a unit; with no argument, print the focus |
| `new <unit>` | create `units/<unit>/input.md` and focus on it. Names: letters, digits, `_ . -` |
| `status`, `st` | rounds, acceptance, hand edits, open questions of the focused unit |
| `rounds`, `log` | one line per round: `A` if accepted, number, status, model, time, choices and questions, first line of that round's input |

### Viewing

| Command | Shows |
|---|---|
| `show` or `show plan` | `intent.md` then `spec.md` |
| `input`, `intent`, `spec` | that file (same as `show input` etc.) |
| `show deps` | the `deps` file |
| `questions [n]`, `choices [n]` | from the latest round, or round `n` |
| `show <file> [n]` | a file from the latest round, or round `n` (see below) |

Files kept for each round, under `.build/round-NNN/`:

| `show …` | File | Contents |
|---|---|---|
| `archived` | `input.md` | the input that round used up |
| `prompt` | `prompt.md` | exactly what was sent (system and user) |
| `response` | `response.md` | the model's raw reply |
| `thinking` | `thinking.md` | the reasoning channel, if the model produced one |
| `choices` | `choices.md` | gaps the model filled |
| `questions` | `questions.md` | conflicts the model would not resolve |
| `meta` | `meta.json` | endpoint, model, input and output hashes, timings, status |

A round that made no choices or asked no questions has no file for them,
and `show` says so (`round 003 has no questions.md`). `thinking.md` and
`stream.json` are git-ignored: they stay on disk but are not committed.

Output taller than the terminal goes through `$PAGER` (usually `less`;
press `q` to return).

### Editing

| Command | Does |
|---|---|
| `edit` | open `input.md` in your editor |
| `edit deps` | open `deps` (created with a format comment if missing) |
| `edit intent`, `edit spec` | open the plan files; see the warning below |
| `add <text>` | append one line to `input.md` |
| `clear` | empty `input.md` |

The editor is `$VISUAL`, or `$EDITOR` if that is unset, or `vi`. It can
include arguments, e.g. `export VISUAL="emacsclient -t"` or
`export EDITOR="code --wait"`. The shell waits for the editor to exit, then
reports `saved` or `unchanged`.

**Editing `intent.md` or `spec.md` directly** is allowed, but it takes the
change out of the record. The next round sends your edited version as the
current plan (and warns about it), and `accept` refuses until a round has
rewritten the files. The recorded way to change the plan is to describe the
change in `input.md` and run `plan`.

`clear` does not archive anything. Only a round archives input.

### Stages

| Command | Does |
|---|---|
| `plan` | if `input.md` has content, run a round; otherwise show `status` |
| `plan -n` | dry run: print the full prompt, call nothing, record nothing |
| `plan --full` | stream the whole reply instead of the one-line live status |
| `plan -e NAME` | use endpoint `NAME` for this round only |
| `accept` | mark the latest successful round as usable by dependents |
| `clean` | delete `intent.md`, `spec.md` and `.build/` after a `[y/N]` prompt; keeps `input.md`, and refills it with round 001's input if it is empty |
| `clean -y` | same, without the prompt |

When a round fails partway, nothing is lost. If the model is unreachable,
the reply is missing sections, or you press Ctrl-C, then `intent.md`,
`spec.md` and `input.md` are left as they were. The round directory records
the attempt with `status: failed` or `status: unparsed`, and `show response`
shows what came back.

### Endpoints

| Command | Does |
|---|---|
| `endpoint` | show the endpoint rounds will use, and where that choice came from |
| `endpoint NAME` | use `NAME` for the rest of the session (shown in the prompt) |
| `endpoint -` | go back to the `ic.toml` default |
| `endpoints` | check that each configured endpoint responds and has its model |

The endpoint for a round is picked in this order: `plan -e NAME`, then the
session `endpoint`, then `[stages] plan` in `ic.toml`, then the first
endpoint defined.

    ic:fock-basis> endpoint hudson
    hudson  (qwen3:8b @ http://localhost:11435, from session)
    ic:fock-basis @hudson> endpoint -
    littleisland  (qwen3.8:27b @ http://localhost:11434, from ic.toml)

### Other

| Command | Does |
|---|---|
| `!<command>` | run a shell command in the project root, e.g. `!git diff units/bits` |
| `help`, `help <command>` | summary, or details for one command |
| `quit`, `exit`, Ctrl-D | leave |

## Keys and conveniences

- **Tab** completes command names, unit names (`use`, `cd`), file names
  (`show`, `edit`) and endpoint names (`endpoint`). When several matches
  exist, press Tab twice to list them.
- **Up / Down** move through command history. History is saved to
  `.ic_history` in the project root (git-ignored) and loaded next time.
- **An empty line does nothing.** Python's `cmd` shell normally repeats the
  last command on an empty line; here that is turned off so Enter can never
  start another `plan` round by accident.
- **Ctrl-C** during a round stops it; the round is recorded as failed and
  you stay in the shell. Ctrl-C at the prompt clears the line.
- **Errors** print as `error: …` and never leave the shell.

## Shell and CLI side by side

| Shell (unit in focus) | One-shot CLI |
|---|---|
| `plan` | `ic plan <unit>` |
| `plan -n` | `ic plan <unit> -n` |
| `plan -e NAME` | `ic plan <unit> -e NAME` |
| `accept` | `ic plan <unit> --accept` |
| `clean -y` | `ic clean <unit> -y` |
| `status` | `ic plan <unit>` with an empty `input.md` |
| `endpoints` | `ic endpoints` |

The CLI is still the better fit for scripts. For example, to accept every
unit:

    for u in bits fock-basis; do ic plan "$u" --accept; done
