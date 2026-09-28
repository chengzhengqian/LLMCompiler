# IntentCompiler

A compiler from short, human-written intent to verified code, where every
step is a visible file and every LLM call is inspectable.

## Idea

Each piece of work is a **unit**: a directory with one human-written file and
documents the LLM maintains from it.

- **input.md** — yours. The first round holds the rough intent and any details;
  later rounds hold change requests. Consumed and archived by each round.
- **intent.md** — LLM-maintained, faces outward: what the unit is for.
- **spec.md** — LLM-maintained, faces downward: the contract for tests and code.

Together, intent and spec are the unit's **plan**. Each round reads input.md
(plus the current plan, if one exists, and the accepted specs of dependencies)
and writes the updated plan. Gaps the model filled are reported as *choices*;
conflicts it would not resolve come back as *questions* for the next input.

The human contribution is exactly the ordered log of archived inputs.

## Commands

    ic plan <unit>            run a round if input.md has content, else show status
    ic plan <unit> --accept   mark the current plan as usable by dependents
    ic plan <unit> -n         dry run: print the assembled prompt
    ic plan <unit> -e NAME    use a specific endpoint from ic.toml
    ic clean <unit>           remove plan and history; keep input.md
    ic endpoints              check configured Ollama endpoints

## Unit layout

    units/<name>/
      input.md          human
      deps              human, optional:  unit: <name>  per line
      intent.md         llm
      spec.md           llm
      .build/
        round-NNN/      input, prompt, response, choices, questions, meta
        accepted.json

## Project layout

    src/ic/             compiler source
    src/ic/templates/   default prompt templates
    example/            example projects, each with its own ic.toml
    tests/

## Quickstart

    uv sync
    uv run ic --help

## Status

Early prototype. First example: `example/second_quantization`.
