# AGENTS.md

Guidance for coding agents (and humans) working on this repository.

## What this is

**IntentCompiler (`ic`)** compiles short, human-written intent into verified
code through stages whose every step is a visible file and every LLM call is
inspectable. Models run locally through Ollama; the author reaches them
through SSH port forwards (`localhost:11434`, `:11435`), so a live model is
usually **not** available in CI or a cloud sandbox. Develop against the fake
server in `tests/`.

The core ideas are in `README.md`; the interactive shell is in
`docs/repl.md`. Read both before changing behavior.

## Principles (do not break these)

1. **Everything is a file.** State lives in the unit directory, never in a
   hidden database or in memory between commands. A human with `cat` and
   `ls` can see everything `ic` knows.
2. **Every LLM call is recorded.** A round writes `.build/round-NNN/` with
   the archived input, the exact prompt, the raw response, thinking (if any),
   choices, questions and `meta.json` *before or as* it touches the unit's
   files. A failed or unparsed round is still recorded (`status: failed` /
   `unparsed`) and leaves `input.md`, `intent.md`, `spec.md` untouched.
3. **The human contribution is the ordered log of archived inputs.** Changes
   to the plan go through `input.md` → a round. Hand edits to `intent.md` or
   `spec.md` are detected by hash (`hand_edited`) and block `accept`.
4. **The model does not resolve conflicts.** Gaps it fills are reported as
   CHOICES; contradictions come back as QUESTIONS. Prompt changes must keep
   this contract.
5. **Dependencies consume accepted specs only.** `accepted.json` pins the
   output hashes of a round; a dependent round refuses to run if the
   dependency's current `spec.md` no longer matches.
6. **Standard library only at runtime.** `dependencies = []` in
   `pyproject.toml` is deliberate (the Ollama client is `urllib`). Dev-only
   tools go in `[dependency-groups] dev`. Ask before adding a runtime dep.

## Layout

    src/ic/
      cli.py        argparse entry point `ic`; no command → the shell
      repl.py       interactive shell (cmd.Cmd): focus a unit, view/edit, run stages
      plan.py       plan stage: gather → prompt → chat → parse → write; accept, clean, status, brief
      llm.py        Ollama /api/chat streaming client, /api/tags; StreamStats
      display.py    live status line while streaming; summary and stream report
      prompt.py     template loading (project override → builtin), $-substitution, system/user split
      record.py     round directories, meta.json, accepted.json, short_hash
      unit.py       Unit (a directory under units/), deps parsing, create/list
      config.py     ic.toml: language, [endpoints.*], [stages]
      templates/plan.md   builtin prompt for the plan stage
    tests/          pytest, fully offline (fake Ollama in conftest.py)
    docs/repl.md    user guide for the shell
    example/second_quantization/   real project: ic.toml + units/fock-basis (3 recorded rounds)
    script/test_ollama.sh          curl smoke test against a live Ollama

A project is any directory with `ic.toml`; units are `units/<name>/`.
Project-level `templates/<stage>.md` overrides the builtin template.

## Commands

    uv sync                         install (Python ≥ 3.11)
    uv run pytest -q                all tests, offline, < 1 s
    uv run ic --help
    cd example/second_quantization && uv run ic            shell on the example
    uv run ic --root example/second_quantization plan fock-basis -n   dry run

Run `uv run pytest -q` before every commit. There is no linter configured;
keep the existing style (below).

## Data formats

**Unit directory**

    input.md      human; emptied when a round consumes it
    deps          human, optional; lines `unit: <name>`, `#` comments
    intent.md     LLM; outward-facing purpose
    spec.md       LLM; contract for tests and code (sections fixed by the template)
    .build/round-NNN/   input.md prompt.md response.md meta.json
                        [thinking.md] [choices.md] [questions.md] [stream.json]
    .build/accepted.json   {"round": N, "outputs": {"intent.md": hash, "spec.md": hash}}

`thinking.md` and `stream.json` are git-ignored (`**/.build/**/…`); the rest
of `.build/` is meant to be committed as the project's history.

**meta.json** keys: `stage round parent endpoint model url template inputs
status` plus, on success, `seconds eval_count tokens_per_second
prompt_tokens outputs`; on failure, `error`. `inputs`/`outputs` map
`unit/file` → `short_hash` (first 12 hex of sha256). `status` is one of
`running failed unparsed ok`; only `ok` rounds count for
`last_successful_round`.

**Reply format** (enforced by `parse_reply`): marker lines
`=== INTENT ===`, `=== SPEC ===`, `=== CHOICES ===`, `=== QUESTIONS ===`.
INTENT and SPEC are required; CHOICES/QUESTIONS of `none` become empty. A
single outer code fence around a section is stripped.

**Templates**: `=== system ===` and `=== user ===` marker lines;
placeholders are `string.Template` `$name` with `safe_substitute`, so values
containing `$` are safe but the template itself must not have stray `$`.
Plan template values: `unit input deps_section current_plan language`.

**ic.toml**: `language`, `[endpoints.NAME] url model [think] [options]`,
`[stages] plan = "NAME"`. Endpoint resolution: explicit `-e` → shell session
endpoint → `[stages]` → first defined.

## Code style

- Match the surrounding code: short module docstrings that show the on-disk
  layout or usage, one-line function docstrings, dataclasses for records,
  `# ----- section` banners in longer modules, lines ≲ 100 columns.
- Errors are raised as `FileNotFoundError`, `ValueError`, `KeyError` or
  `RuntimeError` with a message that says what to do next; `cli.main` and
  `Repl.onecmd` turn them into `error: …`. Do not `sys.exit` from library
  code; return an int status from commands.
- Unit files are written atomically for the plan pair (`_write_atomic`,
  `*.tmp` + `os.replace`).
- New stage? Follow `plan.py`: `gather` (values + input hashes) → `render` →
  record round → `chat` → parse → write outputs → `meta.status = ok`. Add a
  `do_<stage>` to `repl.py` calling the same function, and a CLI subparser.

## Tests

`tests/conftest.py` provides:

- `ollama` — a `FakeOllama` HTTP server. Append to `ollama.replies` a string
  (streamed in 7-char chunks with a final stats line) or a list of raw JSON
  dicts (sent verbatim, e.g. `{"error": ...}` or `{"message": {"thinking": ...}}`).
  Requests are captured in `ollama.requests`.
- `project` — a tmp project with `ic.toml` (endpoints `fake` and `other`,
  language julia) and a unit `counter` whose `input.md` is `A counter.`.
- `cfg` — `config.load(project)`.
- `reply_text(intent=, spec=, choices=, questions=)` — a well-formed reply.

Shell tests drive `Repl(cfg).onecmd(line)` and read `capsys`. Editor tests
set `VISUAL` to a small script; never let a test open a real editor
(`edit` blocks waiting for it).

## Current state and next steps

- Implemented: `plan` stage (rounds, accept, clean, status), the shell,
  endpoint checks. `check` and `impl` are CLI placeholders.
- Next, following the plan template's contract (tests and implementation
  generated separately from the SPEC): a **tests stage** that generates tests from an
  accepted spec, and an **impl stage** that generates code from the spec
  (independently, "by authors who never see each other's work"), then a
  check that runs the tests against the code in the target language
  (`language` in ic.toml; the example is Julia). Keep the same round/record
  model and dependency-acceptance rule.
- Known quirk: `plan.run_round` and the dependency error print the CLI form
  `ic plan <unit> --accept`; inside the shell the command is `accept`.
- `example/second_quantization/units/fock-basis` has three ok rounds and is
  not yet accepted. Its intent names the planned consumer units
  `fermion-ops` and `op-matrix`, which do not exist yet.

## Git

- Commit the example's `.build/` records (they are the history); don't
  commit `stream.json`/`thinking.md`, `.ic_history`, `.venv`, `*.tmp`.
- Keep `uv.lock` in sync with `pyproject.toml` (`uv sync` updates it).
