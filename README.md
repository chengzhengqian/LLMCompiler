# IntentCompiler

A compiler from short, human-written intent to verified code, where every
step is a visible file and every LLM call is inspectable.

## Idea

Each piece of work is a **unit**: a directory that moves through fixed stages.

    intent → spec → check → impl → verify
                              ↑       │
                              └ repair┘

- **intent** — written by you; short, not necessarily complete.
- **spec** — drafted by the LLM from the intent and dependency specs; reviewed by you.
- **check** — tests generated from the spec alone, never seeing the impl.
- **impl** — code generated from the spec and dependency specs.
- **verify** — the check is run for real; failures feed a bounded repair loop.

Prompts are assembled deterministically from declared files, and each stage
run leaves a record of its inputs, prompt, response, and result.

## Unit layout

    units/<name>/
      intent.md
      deps
      spec.md
      check.*
      impl.*
      .build/

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
