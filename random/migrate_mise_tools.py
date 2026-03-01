#!/usr/bin/env python3
"""Migrate [tools] entries from mise config.local.toml into config.toml."""

import re
import sys
from pathlib import Path

MISE_DIR = Path.home() / ".config" / "mise"
LOCAL_PATH = MISE_DIR / "config.local.toml"
MAIN_PATH = MISE_DIR / "config.toml"

SECTION_RE = re.compile(r"^\[([^\]]+)\]\s*$")


def extract_section(text: str, section: str) -> tuple[list[str], list[str]]:
    """Split file text into (section body lines, remaining lines).

    Returns the key=value lines belonging to `section` and the file
    contents with that section (header + body) removed.
    """
    lines = text.splitlines(keepends=True)
    body: list[str] = []
    rest: list[str] = []
    in_section = False

    for line in lines:
        if m := SECTION_RE.match(line):
            if m.group(1) == section:
                in_section = True
                continue  # skip the header itself
            else:
                in_section = False

        if in_section:
            body.append(line)
        else:
            rest.append(line)

    return body, rest


def find_section_end(text: str, section: str) -> int | None:
    """Return the character offset just after the last line of `section`.

    Returns None if the section does not exist.
    """
    lines = text.splitlines(keepends=True)
    offset = 0
    in_section = False
    end = None

    for line in lines:
        if m := SECTION_RE.match(line):
            if m.group(1) == section:
                in_section = True
            elif in_section:
                break  # hit the next section
        if in_section:
            end = offset + len(line)
        offset += len(line)

    return end


def main() -> None:
    if not LOCAL_PATH.exists():
        print(f"{LOCAL_PATH} does not exist, nothing to do.")
        return

    local_text = LOCAL_PATH.read_text()
    body, rest = extract_section(local_text, "tools")

    if not body or all(l.strip() == "" for l in body):
        print("No [tools] entries in config.local.toml, nothing to migrate.")
        return

    main_text = MAIN_PATH.read_text() if MAIN_PATH.exists() else ""
    insertion = "".join(body)

    end = find_section_end(main_text, "tools")
    if end is not None:
        # Ensure a newline separates existing entries from new ones.
        if main_text[end - 1 : end] != "\n":
            insertion = "\n" + insertion
        new_main = main_text[:end] + insertion + main_text[end:]
    else:
        # No [tools] section yet — append one.
        sep = "\n" if main_text and not main_text.endswith("\n") else ""
        new_main = main_text + sep + "[tools]\n" + insertion

    MAIN_PATH.write_text(new_main)
    LOCAL_PATH.write_text("".join(rest))

    n = sum(1 for l in body if l.strip() and not l.lstrip().startswith("#"))
    print(f"Migrated {n} tool(s) from config.local.toml → config.toml.")


if __name__ == "__main__":
    main()
