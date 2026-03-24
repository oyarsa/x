#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["tomlkit"]
# ///
"""Scaffold a new Python project with opinionated defaults.

Runs `uv init --app --package <name>`, merges in tool config (ruff, ty,
license), and installs dependencies via `uv add` so uv resolves the latest
compatible versions.

Usage:
    init-project.py <name> [--dir <parent-dir>]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import tomlkit

# ──────────────────────────────────────────────────────────────────────
# Configuration — edit these to taste.
# ──────────────────────────────────────────────────────────────────────

DEPENDENCIES = ["typer", "rich", "tqdm"]
DEV_DEPENDENCIES = ["ty", "ruff", "pytest"]

# Everything here is deep-merged into the generated pyproject.toml.
# Dependencies are handled separately by `uv add`, not listed here.
DEFAULTS_TOML = """\
license = {text = "GPL-3.0-or-later"}

[tool.ruff]
src = ["src", "tests"]

[tool.ruff.lint]
select = ["ALL"]
# I try to enable as many reasonable rules as possible, but sometimes it's too much:
ignore = [
    "FIX",      # Allow FIX/TODO/XXX comments.
    "TD",       # Allow TODO comments without author/link
    "COM",      # Let ruff take care of trailing commas
    "T",        # Allow print
    "FLY",      # Allow static string joins
    "FBT",      # Allow positional boolean arguments
    "EM",       # Exception messages with literals/f-strings
    "A",        # Allow shadowing built-ins
    "ARG",      # Allow unused arguments
    "BLE",      # Allow blind excepts
    "PLR",      # "Too many" warnings
    #
    "ANN401",   # Allow usage of Any
    "B905",     # `zip` without `strict`
    "C901",     # "too complex" functions
    "D107",     # Allow no docstring in __init__
    "D202",     # Empty lines between function docstring and body
    "E501",     # Line too long (let ruff format take care of this)
    "G004",     # f-strings in logging
    "ISC001",   # Incompatible with the formatter
    "PERF401",  # Manual list comprehensions
    "PERF203",  # Allow try/except inside loops
    "PGH003",   # Allow blanket type: ignore statements
    "PLC0206",  # Dictionary iteration without items
    "PLC0414",  # Allow redundant alias to re-export items
    "PTH123",   # Allow `open(p)` instead of `Path(p).open`
    "RET505",   # Allow `else` after `return`. I like this symmetry in some cases.
    "RET504",   # Allow 'unnecessary' assignment before return.
    "S101",     # Allow assert
    "S311",     # Allow regular `random.Random` (not crypto safe, but that's fine)
    "S603",     # Allow subprocess with 'untrusted' input
    "S607",     # Allow subprocess with relative path (usually `uv run`)
    "SIM108",   # Use ternary operation instead of if-else block
    "TC",       # PEP 649 (Python 3.14) makes TYPE_CHECKING guards unnecessary for
                # annotation-only imports. Keep heavy guards (transformers, etc.) by
                # choice, but don't lint for them.
    "TRY003",   # Long messages outside exception class
    "INP001",   # Disable annoying error about implicit namespaces
    "TRY301",   # Enable raise inside try/except
    "PYI025",   # Allow `collections.abc.Set` without aliasing to `AbstractSet`
    "D",        # TODO: Remove once we have proper documentation
]

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = [
    "SLF001",  # Allow private member access in tests
    "D100",    # Missing docstring in public module
    "D101",    # Missing docstring in public class
    "D102",    # Missing docstring in public method
    "D103",    # Missing docstring in public function
]

[tool.ruff.lint.pydocstyle]
convention = "google"

[tool.ty.rules]
ambiguous-protocol-member = "error"
ineffective-final = "error"
invalid-enum-member-annotation = "error"
invalid-legacy-positional-parameter = "error"
possibly-missing-implicit-call = "error"
possibly-missing-submodule = "error"
redundant-cast = "error"
redundant-final-classvar = "error"
undefined-reveal = "error"
unresolved-global = "error"
unsupported-base = "error"
unsupported-dynamic-base = "error"
unused-awaitable = "error"
unused-type-ignore-comment = "ignore"
useless-overload-body = "error"
"""


# ──────────────────────────────────────────────────────────────────────
# Deep merge for tomlkit documents.
# ──────────────────────────────────────────────────────────────────────


def deep_merge(base: tomlkit.TOMLDocument, overrides: tomlkit.TOMLDocument) -> None:
    """Recursively merge *overrides* into *base*, preserving existing keys."""
    for key in overrides:
        if (
            key in base
            and isinstance(base[key], dict)
            and isinstance(overrides[key], dict)
        ):
            deep_merge(base[key], overrides[key])
        else:
            base[key] = overrides[key]


# ──────────────────────────────────────────────────────────────────────
# uv helpers.
# ──────────────────────────────────────────────────────────────────────


def _run(args: list[str], *, label: str | None = None) -> bool:
    """Run a command, printing it first. Returns True on success."""
    label = label or args[0]
    cmd_str = " ".join(args)
    print(f"  $ {cmd_str}")
    # Strip VIRTUAL_ENV so child `uv` doesn't warn about the script's
    # ephemeral venv conflicting with the project venv.
    import os

    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    result = subprocess.run(args, check=False, env=env)  # noqa: S603
    if result.returncode != 0:
        print(
            f"  warning: `{label}` failed (exit {result.returncode}).\n"
            f"  Run manually: {cmd_str}",
            file=sys.stderr,
        )
        return False
    return True


def uv_init(name: str, parent: Path) -> Path:
    """Run `uv init --app --package` and return the project directory."""
    project_dir = parent / name
    if project_dir.exists():
        sys.exit(f"error: {project_dir} already exists")

    ok = _run(
        ["uv", "init", "--app", "--package", "--name", name, str(project_dir)],
        label="uv init",
    )
    if not ok:
        sys.exit(1)

    return project_dir


def uv_add(project_dir: Path) -> None:
    """Run `uv add --project` for regular and dev dependencies."""
    project = str(project_dir)
    if DEPENDENCIES:
        _run(
            ["uv", "add", "--project", project, *DEPENDENCIES],
            label="uv add",
        )
    if DEV_DEPENDENCIES:
        _run(
            ["uv", "add", "--project", project, "--dev", *DEV_DEPENDENCIES],
            label="uv add --dev",
        )


# ──────────────────────────────────────────────────────────────────────
# Extra files to scaffold.
# ──────────────────────────────────────────────────────────────────────

TEST_HELLO_PY = """\
\"\"\"Placeholder tests.\"\"\"


def test_hello() -> None:
    \"\"\"Placeholder test.\"\"\"
    assert True
"""

JUSTFILE = """\
_default:
    @just --list

# Run ruff check with autofix
fix:
    uv run ruff check . --fix

# Run ruff check (no fix)
check:
    uv run ruff check .

# Run ruff format
fmt:
    uv run ruff format .

# Run ty
type:
    uv run ty check

# Run unit tests
test:
    uv run pytest --quiet tests/

# Run typecheck and tests in parallel
[parallel]
_type-test: test type

# Run ruff check, ruff format, and ty
lint: fix fmt _type-test
"""


def scaffold_files(project_dir: Path) -> None:
    """Create additional project files."""
    tests_dir = project_dir / "tests"
    tests_dir.mkdir(exist_ok=True)

    test_file = tests_dir / "test_hello.py"
    test_file.write_text(TEST_HELLO_PY)
    print(f"  Wrote {test_file}")

    justfile = project_dir / "Justfile"
    justfile.write_text(JUSTFILE)
    print(f"  Wrote {justfile}")


# ──────────────────────────────────────────────────────────────────────
# Main.
# ──────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "name", help="Package name (passed to `uv init --app --package`)"
    )
    parser.add_argument(
        "--dir",
        type=Path,
        default=Path.cwd(),
        help="Parent directory to create the project in (default: cwd)",
    )
    args = parser.parse_args()

    # 1. Scaffold with uv.
    project_dir = uv_init(args.name, args.dir.resolve())

    # 2. Merge tool config into pyproject.toml.
    pyproject_path = project_dir / "pyproject.toml"
    pyproject = tomlkit.parse(pyproject_path.read_text())
    deep_merge(pyproject, tomlkit.parse(DEFAULTS_TOML))
    pyproject_path.write_text(tomlkit.dumps(pyproject))
    print(f"  Wrote {pyproject_path}")

    # 3. Create extra files (tests, Justfile).
    scaffold_files(project_dir)

    # 4. Add dependencies via uv (resolves latest versions).
    uv_add(project_dir)

    print(f"\n  Done! Project ready at {project_dir}")


if __name__ == "__main__":
    main()
