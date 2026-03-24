# Patterns and Style Guide (from genret)

## Python Code Style

- Python 3.12+ with strict typing (no exceptions)
- Functional programming with dataclasses over OOP
- Frozen dataclasses must also be `kw_only=True`: `@dataclass(frozen=True,
  kw_only=True)`
- In frozen dataclasses and Pydantic BaseModels, use `collections.abc` immutable
  protocols: `Sequence` instead of `list`, `Mapping` instead of `dict`, `Set` instead of
  `set`
- Function parameters: use `Mapping`, `Sequence`, `Set` when data is not mutated. Return
  types: always concrete (`dict`, `list`, `set`). Use `frozenset` where applicable but
  members/parameters should always be `Set`
- Use Pydantic `BaseModel` for types needing serialisation; dataclasses for
  internal/transitory models
- British English everywhere
- Absolute imports from the package root
- Google-style docstrings
- Never use `hasattr`/`getattr` — get proper type and access fields
- Avoid non-top-level imports; only acceptable to break circular references or very
  heavy dependencies that aren't always need (e.g. torch, transformers). Suppress
  the warning with a comment.
- Use `seed=0` as default for random seeds
- All `--output` CLI options are required (no default). Required options before optional
  ones in function signatures
- Never use plain `object`; use `Any` instead
- Use walrus operator where appropriate (including comprehensions)
- Conditional expressions (`x if cond else y`) only for simple two-way cases; never nest
  them
- All files must be shorter than 1000 non-empty lines (blank lines excluded)
- Avoid function longer than 100 non-empty lines. When they outgrow this, break them up
  into smaller functions, favouring testable pure functions.

## Docstrings

All of the following must have docstrings:

- **Modules** (top of file)
- **Classes** (including dataclasses and Pydantic models)
- **All functions and methods** (public and private), except nested closures/callbacks
- **Module-level variables** (public and private), except: `app` (Typer), `logger`,
  `_console` (Rich Console), type aliases

In docstrings use only single backticks (`` `name` ``). Never double backticks or
asterisks.

Variable docstrings: triple-quoted string on the line immediately after the assignment.
Group related constants without blank lines between them.

## Typing (cross-checker compatibility)

The codebase targets zero errors across multiple type checkers (pyrefly, pyright strict, etc.). Key rules:

- **Annotate untyped boundaries.** `json.loads()`, `dict.get()`, etc. return `Any` —
  always annotate the result. Favour BaseModel parsing instead of pure json.
- **Wrap `NewType` values explicitly.** Strict checkers reject bare literals where a
  `NewType` is expected
- **Use `Literal` mode strings instead of concatenation.** String arithmetic produces
  `str`, not the literal the callee expects
- **Favour `StrEnum` over `Literal`. `Literal` might required for some APIs, but use
  `StrEnum` wherever possible.
- **No cross-module private imports.** If used outside its module, give it a public name
- **Avoid variable shadowing.** Never reuse a name with a different type in the same
  scope
- **No inline type aliases** inside functions — use the type expression inline or a
  module-level `type` statement (PEP 695)
- **Typed constructor calls for empty collections** when the variable was already
  annotated by an earlier branch:
  ```python
  # Good:
  paragraphs = list[tuple[str, str]]()
  # Bad (re-annotates with a different apparent type):
  paragraphs: list[tuple[str, str]] = []
  ```
  This only applies is the variable has already been declared. If it's the first
  declaration, use a regular annotation.
- **Typed `default_factory`** in dataclass fields:
  `field(default_factory=set[CorpusId])`
- **Annotate exception tuples** explicitly: `tuple[type[Exception], ...]`
- **`cast()` after runtime type assertions** — not all checkers narrow from `assert
  is_type(...)`
- **`int()` wrapping for numpy indices** — numpy integer types aren't universally
  recognised as `int`
- **`list()` wrapping for `itertools.batched` results** — yields tuples, APIs may expect
  `list`
- **`Protocol` for structural typing** instead of complex union types for duck-typed
  objects

## Type-Unsafe Code Quarantine (`_shed` pattern)

All `type: ignore` comments and untyped library wrappers live in a single quarantine
module. Code outside it must not use type-checker suppression comments unless a specific
checker has a unique bug (use a checker-specific ignore with a comment explaining it).

Rules for quarantine code:
- One submodule per library (e.g. `torch.py`, `networkx.py`)
- Use `# pyright: basic` and `# type: ignore` freely — that's what the module is for
- Every function must have a fully-typed signature so callers get full type safety
- Keep wrappers minimal: just enough to hide the type gap, no extra logic

Rules for code outside:
- No `# type: ignore`, `# pyright: ignore`, etc. unless a checker-specific bug
- `# pyright: basic` allowed as file-level override for ML-heavy modules
- Minimise `assert` guards that exist only for type narrowing — prefer moving assertions
  into the quarantine wrapper

## Version Control

- Natural, descriptive commit messages (no conventional commits format)
- Commit messages explain what and why, not how
- Summary lines under 70 characters
- No `Co-Authored-By` lines

## Documentation Layout

- `docs/plans/` — implementation plans
- `docs/specs/` — specifications and design documents
- `docs/reference/` — living reference docs (updated alongside implementation)
- `docs/todos/` — task lists and tracking

Use `docs/reference/` for "how it works today". Use `docs/specs/` for historical or
governing design documents.

## Plan/Spec Document Format

Files named `YYYYMMDD-slug.md` with YAML front matter:

```yaml
---
description: >
  Concise summary wrapped at 80 columns.
created_at: YYYY-MM-DD
last_updated: YYYY-MM-DD
tags: [tag-a, tag-b]
---
```

Plans include: title, status/todo checklist, purpose, motivation, design, results.
Specs cover system architecture, data formats, governing design decisions.

## Experiment Logging

_Only applicable if the project is an ML project with experiments._

Log experiments to YAML with fields: `date`, `name`, `description`, `reason`, `command`,
`parameters`, `metrics`, `total_cost`, `conclusion`.

Log **all** meaningful outcomes promptly — including failed, cancelled, and rejected
runs. Don't wait for success only.

## Background Jobs

- Use a task queue (pueue) for long-running commands
- Either the agent or user can start jobs; the other can follow

## Passive Monitoring Pattern

For long-running remote jobs:
- Never busy-loop the main agent for monitoring
- Use a persistent background monitor that polls on an interval and writes alerts to
  state files
- Use a one-shot relay sidecar that blocks until the next alert, then reports it
- Main agent acts only on surfaced alerts, does not poll
- Only surface messages when something actionable happens (finish, fail, stall,
  intervention needed)
- Default polling interval: 2 minutes

## Linting

Use a Justfile for development tasks. After making changes to Python files, always run
the linter (ruff format + check, type checker) using `just lint`.
