"""pax — A synchronous, dax-inspired shell toolkit for Python 3.10+

from pax import sh, raw

name = "hello world"
sh("echo {name}").text()           # → "hello world"  (auto-escaped!)

# Piping
(sh("cat {path}") | sh("grep {pattern}")).lines()

# Output formats
sh("echo hi").text()               # → str
sh("printf 'a\\nb'").lines()       # → list[str]
sh("echo '{{}}'").json()           # → dict   ({{ for literal {)
sh("echo hi").bytes()              # → bytes

# Builder pattern (immutable)
sh("curl -s {url}").env(TOKEN="abc").cwd("/tmp").timeout(30).json()

# Raw — bypass escaping for trusted shell fragments
flags = raw("-type f -name '*.py'")
sh("find . {flags}").lines()

# Error handling
result = sh("grep {pat} {file}").no_throw().run()
"""

from __future__ import annotations

import json as _json
import os
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Literal

# ---------------------------------------------------------------------------
# raw() — bypass escaping
# ---------------------------------------------------------------------------


class _RawValue:
    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        self._value = value

    def __str__(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return f"raw({self._value!r})"


def raw(value: str) -> _RawValue:
    """Mark a string as raw — it won't be shell-escaped.

        flags = raw("-type f -name '*.py'")
        sh("find . {flags}").lines()

    ⚠️  Never use with untrusted input.
    """
    return _RawValue(value)


# ---------------------------------------------------------------------------
# Parsed parts → shell command string
# ---------------------------------------------------------------------------


def _resolve(parts: list[str | Interp]) -> str:
    """Convert parsed template parts into a shell command string.

    Static parts pass through verbatim. Interpolated values are escaped
    via shlex.quote() unless wrapped in raw().
    """
    out: list[str] = []
    for part in parts:
        if isinstance(part, str):
            out.append(part)
            continue

        value = part.value
        if part.conversion == "s":
            value = str(value)
        elif part.conversion == "r":
            value = repr(value)
        elif part.conversion == "a":
            value = ascii(value)
        if part.format_spec:
            value = format(value, part.format_spec)

        if isinstance(value, _RawValue):
            out.append(str(value))
        elif isinstance(value, list | tuple):
            out.append(" ".join(shlex.quote(str(v)) for v in value))
        else:
            out.append(shlex.quote(str(value)))

    return "".join(out)


# ---------------------------------------------------------------------------
# CommandResult
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CommandResult:
    """The result of a completed shell command."""

    code: int
    stdout_bytes: bytes
    stderr_bytes: bytes

    @property
    def stdout(self) -> str:
        return self.stdout_bytes.decode("utf-8", errors="replace")

    @property
    def stderr(self) -> str:
        return self.stderr_bytes.decode("utf-8", errors="replace")

    @property
    def success(self) -> bool:
        return self.code == 0

    def text(self) -> str:
        return self.stdout.strip()

    def lines(self) -> list[str]:
        return [ln for ln in self.stdout.strip().splitlines() if ln]

    def json(self) -> Any:
        return _json.loads(self.stdout)

    def bytes(self) -> bytes:
        return self.stdout_bytes

    def __bool__(self) -> bool:
        return self.success


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class CommandError(subprocess.CalledProcessError):
    def __init__(self, result: CommandResult, cmd: str) -> None:
        self.result = result
        super().__init__(result.code, cmd, result.stdout_bytes, result.stderr_bytes)

    def __str__(self) -> str:
        return (
            f"Command failed with exit code {self.result.code}: {self.cmd}\n"
            f"stderr: {self.result.stderr.strip()}"
        )


class CommandTimeoutError(CommandError):
    pass


# ---------------------------------------------------------------------------
# Command config (internal, immutable)
# ---------------------------------------------------------------------------

StdioPipe = Literal["pipe", "inherit", "null"]


@dataclass(frozen=True, slots=True)
class _Cfg:
    cmd: str = ""
    working_dir: str | None = None
    env_vars: dict[str, str] = field(default_factory=dict)
    env_remove: set[str] = field(default_factory=set)
    stdin_data: bytes | None = None
    stdout_mode: StdioPipe = "inherit"
    stderr_mode: StdioPipe = "inherit"
    raise_on_error: bool = True
    timeout_secs: float | None = None
    retry_count: int = 0
    retry_delay: float = 1.0
    shell_executable: str | None = None
    pipe_from: Command | None = None


# ---------------------------------------------------------------------------
# Command (immutable builder + executor)
# ---------------------------------------------------------------------------


class Command:
    """Immutable, chainable shell command builder.

    Every method returns a new Command.
    """

    __slots__ = ("_cfg",)

    def __init__(self, cfg: _Cfg) -> None:
        self._cfg = cfg

    # -- Builder -----------------------------------------------------------

    def cwd(self, path: str | Path) -> Command:
        return Command(replace(self._cfg, working_dir=str(path)))

    def env(self, _remove: str | None = None, /, **kwargs: str) -> Command:
        new_vars = {**self._cfg.env_vars, **kwargs}
        new_remove = set(self._cfg.env_remove)
        if _remove is not None:
            new_remove.add(_remove)
        return Command(replace(self._cfg, env_vars=new_vars, env_remove=new_remove))

    def stdin(self, data: str | bytes, encoding: str = "utf-8") -> Command:
        if isinstance(data, str):
            data = data.encode(encoding)
        return Command(replace(self._cfg, stdin_data=data))

    def stdout(self, mode: StdioPipe) -> Command:
        return Command(replace(self._cfg, stdout_mode=mode))

    def stderr(self, mode: StdioPipe) -> Command:
        return Command(replace(self._cfg, stderr_mode=mode))

    def quiet(self) -> Command:
        return Command(replace(self._cfg, stdout_mode="pipe", stderr_mode="pipe"))

    def no_throw(self) -> Command:
        return Command(replace(self._cfg, raise_on_error=False))

    def timeout(self, seconds: float) -> Command:
        return Command(replace(self._cfg, timeout_secs=seconds))

    def retry(self, count: int = 3, delay: float = 1.0) -> Command:
        return Command(replace(self._cfg, retry_count=count, retry_delay=delay))

    def shell(self, executable: str) -> Command:
        return Command(replace(self._cfg, shell_executable=executable))

    # -- Pipe --------------------------------------------------------------

    def __or__(self, other: Command) -> Command:
        if not isinstance(other, Command):
            return NotImplemented
        return Command(replace(other._cfg, pipe_from=self))

    # -- Execution ---------------------------------------------------------

    def _stdio(self, mode: StdioPipe) -> int | None:
        if mode == "pipe":
            return subprocess.PIPE
        if mode == "null":
            return subprocess.DEVNULL
        return None

    def _env(self) -> dict[str, str] | None:
        if not self._cfg.env_vars and not self._cfg.env_remove:
            return None
        env = os.environ.copy()
        for k in self._cfg.env_remove:
            env.pop(k, None)
        env.update(self._cfg.env_vars)
        return env

    def _exec_once(self) -> CommandResult:
        c = self._cfg
        stdin_data = c.stdin_data

        if c.pipe_from is not None:
            up = c.pipe_from.stdout("pipe").no_throw()._exec_once()
            stdin_data = up.stdout_bytes

        try:
            proc = subprocess.run(
                c.cmd,
                check=False,
                shell=True,
                executable=c.shell_executable,
                cwd=c.working_dir,
                env=self._env(),
                input=stdin_data,
                stdout=self._stdio(c.stdout_mode),
                stderr=self._stdio(c.stderr_mode),
                timeout=c.timeout_secs,
            )
        except subprocess.TimeoutExpired as exc:
            r = CommandResult(-1, exc.stdout or b"", exc.stderr or b"")
            if c.raise_on_error:
                raise CommandTimeoutError(r, c.cmd) from exc
            return r

        return CommandResult(proc.returncode, proc.stdout or b"", proc.stderr or b"")

    def run(self) -> CommandResult:
        c = self._cfg
        last_err: CommandError | None = None
        attempts = max(1, c.retry_count + 1) if c.retry_count > 0 else 1

        for attempt in range(attempts):
            if attempt > 0:
                time.sleep(c.retry_delay)

            result = self._exec_once()
            if result.success or not c.raise_on_error:
                return result

            last_err = CommandError(result, c.cmd)
            if attempt < attempts - 1:
                print(
                    f"pax: command failed (attempt {attempt + 1}/{attempts}), "
                    f"retrying in {c.retry_delay}s...",
                    file=sys.stderr,
                )

        raise last_err  # type: ignore[misc]

    # -- Output convenience ------------------------------------------------

    def _captured(self) -> CommandResult:
        return self.stdout("pipe").run()

    def text(self) -> str:
        return self._captured().text()

    def lines(self) -> list[str]:
        return self._captured().lines()

    def json(self) -> Any:
        return self._captured().json()

    def bytes(self) -> bytes:
        return self._captured().bytes()

    # -- Repr --------------------------------------------------------------

    def __repr__(self) -> str:
        p = [f"Command({self._cfg.cmd!r})"]
        if self._cfg.working_dir:
            p.append(f".cwd({self._cfg.working_dir!r})")
        if self._cfg.env_vars:
            kv = ", ".join(f"{k}={v!r}" for k, v in self._cfg.env_vars.items())
            p.append(f".env({kv})")
        if not self._cfg.raise_on_error:
            p.append(".no_throw()")
        if self._cfg.timeout_secs:
            p.append(f".timeout({self._cfg.timeout_secs})")
        if self._cfg.pipe_from:
            return f"{self._cfg.pipe_from!r} | {''.join(p)}"
        return "".join(p)


# ---------------------------------------------------------------------------
# sh
# ---------------------------------------------------------------------------


def sh(template: str) -> Command:
    """Create a Command from a template string.

    {expressions} are resolved from the caller's scope and shell-escaped:

        name = "hello world"
        sh("echo {name}").text()       # → "hello world"
        # Executed as: echo 'hello world'

    Use raw() for trusted shell fragments:

        flags = raw("-type f")
        sh("find . {flags}").lines()

    Literal braces use {{ and }} (same as f-strings).
    """
    frame = sys._getframe(1)
    parts = parse(template, frame.f_locals, frame.f_globals)
    cmd = _resolve(parts)
    return Command(_Cfg(cmd=cmd))


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def which(name: str) -> Path | None:
    r = shutil.which(name)
    return Path(r) if r else None


def exists(path: str | Path) -> bool:
    return Path(path).exists()


def is_dir(path: str | Path) -> bool:
    return Path(path).is_dir()


def is_file(path: str | Path) -> bool:
    return Path(path).is_file()


# ---------------------------------------------------------------------------
# Logging (styled, to stderr, like dax)
# ---------------------------------------------------------------------------

_BOLD = "\033[1m"
_GREEN = "\033[32m"
_RED = "\033[31m"
_YELLOW = "\033[33m"
_GRAY = "\033[90m"
_RESET = "\033[0m"
_indent_level = 0


def _styled(text: str, color: str = "") -> None:
    indent = "  " * _indent_level
    if color:
        first, *rest = text.split(" ", 1)
        tail = f" {rest[0]}" if rest else ""
        print(f"{indent}{_BOLD}{color}{first}{_RESET}{tail}", file=sys.stderr)
    else:
        print(f"{indent}{text}", file=sys.stderr)


def log(*args: Any) -> None:
    _styled(" ".join(str(a) for a in args))


def log_step(*args: Any) -> None:
    _styled(" ".join(str(a) for a in args), _GREEN)


def log_error(*args: Any) -> None:
    _styled(" ".join(str(a) for a in args), _RED)


def log_warn(*args: Any) -> None:
    _styled(" ".join(str(a) for a in args), _YELLOW)


def log_light(*args: Any) -> None:
    indent = "  " * _indent_level
    print(f"{indent}{_GRAY}{' '.join(str(a) for a in args)}{_RESET}", file=sys.stderr)


# ruff: noqa: PLW0603
class _IndentContext:
    def __enter__(self) -> None:
        global _indent_level
        _indent_level += 1

    def __exit__(self, *_: Any) -> None:
        global _indent_level
        _indent_level = max(0, _indent_level - 1)


def log_indent() -> _IndentContext:
    return _IndentContext()


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    "Command",
    "CommandError",
    "CommandResult",
    "CommandTimeoutError",
    "exists",
    "is_dir",
    "is_file",
    "log",
    "log_error",
    "log_indent",
    "log_light",
    "log_step",
    "log_warn",
    "raw",
    "sh",
    "which",
]

"""
pax._template — Parse f-string-style strings into static parts + interpolated values.

Handles:
    {expr}          interpolation (evaluated + shell-escaped)
    {expr!r}        conversion (!r, !s, !a)
    {expr:.2f}      format spec
    {expr!r:.2f}    both
    {expr=}         debug specifier
    {{ / }}         literal { and }
    nested braces   dict literals, comprehensions, etc.
    string literals  quotes inside expressions
"""


@dataclass(frozen=True, slots=True)
class Interp:
    """An interpolated value extracted from a template string."""

    value: object
    expression: str = ""
    conversion: str | None = None
    format_spec: str = ""


def parse(
    text: str,
    local_vars: dict[str, Any],
    global_vars: dict[str, Any],
) -> list[str | Interp]:
    """Parse an f-string-style format string into a list of parts.

    Static text becomes str items. {expressions} become Interp items
    with values evaluated against the given scope.
    """
    parts: list[str | Interp] = []
    i = 0
    n = len(text)
    buf: list[str] = []

    while i < n:
        ch = text[i]

        # {{ → literal {
        if ch == "{" and i + 1 < n and text[i + 1] == "{":
            buf.append("{")
            i += 2
            continue
        # }} → literal }
        if ch == "}" and i + 1 < n and text[i + 1] == "}":
            buf.append("}")
            i += 2
            continue

        if ch == "}":
            raise ValueError(f"Single '}}' at position {i} in template string")

        if ch == "{":
            # Flush static text
            parts.append("".join(buf))
            buf.clear()

            # Extract field content between { and matching }
            i += 1
            raw_field, consumed = _extract_field(text, i)
            i += consumed

            interp, debug_prefix = _parse_field(raw_field, local_vars, global_vars)
            if debug_prefix:
                # For {expr=}, prepend "expr=" to the static text before the value
                if parts and isinstance(parts[-1], str):
                    parts[-1] += debug_prefix
                else:
                    parts.append(debug_prefix)
            parts.append(interp)
            continue

        buf.append(ch)
        i += 1

    if buf:
        parts.append("".join(buf))

    return parts


def _extract_field(text: str, start: int) -> tuple[str, int]:
    """Extract raw content between { and matching }. Returns (content, chars_consumed)."""
    i = start
    n = len(text)
    depth = 1
    chars: list[str] = []
    in_str: str | None = None

    while i < n and depth > 0:
        c = text[i]

        # Inside a string literal — only watch for the closing quote
        if in_str is not None:
            chars.append(c)
            if len(in_str) == 3:
                if text[i : i + 3] == in_str:
                    chars.append(text[i + 1])
                    chars.append(text[i + 2])
                    i += 3
                    in_str = None
                    continue
            elif c == in_str and (i == start or text[i - 1] != "\\"):
                in_str = None
            i += 1
            continue

        # String literal start
        if c in ("'", '"'):
            triple = text[i : i + 3]
            if triple in ('"""', "'''"):
                in_str = triple
                chars.extend(triple)
                i += 3
                continue
            in_str = c
            chars.append(c)
            i += 1
            continue

        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                i += 1  # consume closing }
                break

        chars.append(c)
        i += 1

    if depth != 0:
        raise ValueError(f"Unclosed '{{' in template string near position {start}")

    return "".join(chars), i - start


def _parse_field(
    raw_field: str,
    local_vars: dict[str, Any],
    global_vars: dict[str, Any],
) -> tuple[Interp, str]:
    """Parse a field like 'expr', 'expr!r', 'expr:.2f', 'expr='.

    Returns (Interp, debug_prefix). debug_prefix is "" normally,
    or "expr=" for debug fields.
    """
    expression = raw_field
    conversion: str | None = None
    format_spec = ""
    debug_prefix = ""

    # Debug: {expr=}
    if expression.endswith("=") and not expression.endswith(("==", "!=", "<=", ">=")):
        debug_prefix = expression  # preserves whitespace, e.g. "x ="
        expression = expression[:-1].rstrip()

    # Format spec (top-level :)
    pos = _find_top_level(expression, ":")
    if pos is not None:
        format_spec = expression[pos + 1 :]
        expression = expression[:pos]

    # Conversion (top-level !)
    pos = _find_top_level(expression, "!")
    if pos is not None:
        conv = expression[pos + 1 :]
        if conv in ("r", "s", "a"):
            conversion = conv
            expression = expression[:pos]

    # Debug defaults to !r
    if debug_prefix and conversion is None and not format_spec:
        conversion = "r"

    value = eval(expression, global_vars, local_vars)

    return Interp(value, expression.strip(), conversion, format_spec), debug_prefix


def _find_top_level(text: str, char: str) -> int | None:
    """Find first occurrence of `char` not inside brackets or strings."""
    depth = 0
    in_str: str | None = None
    i = 0
    n = len(text)

    while i < n:
        c = text[i]

        if in_str is not None:
            if len(in_str) == 3:
                if text[i : i + 3] == in_str:
                    i += 3
                    in_str = None
                    continue
            elif c == in_str and (i == 0 or text[i - 1] != "\\"):
                in_str = None
            i += 1
            continue

        if c in ("'", '"'):
            triple = text[i : i + 3]
            if triple in ('"""', "'''"):
                in_str = triple
                i += 3
                continue
            in_str = c
            i += 1
            continue

        if c in ("(", "[", "{"):
            depth += 1
        elif c in (")", "]", "}"):
            depth -= 1

        if depth == 0 and c == char:
            return i

        i += 1

    return None
