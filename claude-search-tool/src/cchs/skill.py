"""Claude Code skill content and installation."""

import sys
from pathlib import Path

SKILL_PATH = Path.home() / ".claude/skills/search-history/SKILL.md"

SKILL_CONTENT = """\
---
name: search-history
description: >
  Search past Claude Code conversation history for this project.
  Use when the user asks about previous conversations, past decisions,
  how something was done before, or wants to recall prior work.
  Trigger phrases: "check our conversation history", "how did we do X",
  "do you remember when", "search our past sessions", "what did we discuss".
---

# Search Conversation History

You have access to `cchs`, a CLI tool that searches past Claude Code
conversation history for the current project using full-text search.

## Commands

### Search

```bash
cchs search "<query>" --json
```

Searches all past conversations in this project. Returns matching messages
with surrounding context.

Options:
- `--context`, `-c` (default: 3): messages before/after each match
- `--limit`, `-n` (default: 10): max results
- `--session <id>`: restrict to a specific session
- `--since <YYYY-MM-DD>`: only search on or after this date (inclusive)
- `--until <YYYY-MM-DD>`: only search on or before this date (inclusive)

### Expand

```bash
cchs expand <message-uuid> --json
```

Get more context around a specific message from a previous search.

Options:
- `--before`, `-B` (default: 10): messages before
- `--after`, `-A` (default: 10): messages after
- `--full`: return the entire session

## Workflow

1. Run `cchs search "<query>" --json` to find matching messages
2. Review the results — each result includes the matching message and context
3. If you need more context, use `cchs expand <uuid> --json` on promising matches
4. Synthesize your findings into an answer for the user

## Search Query Tips

The search engine automatically preprocesses queries:
- Natural language queries like "How was PFA calculated" are converted to
  OR-based searches with stop words removed (becomes `PFA OR calculated`)
- This means both keywords and natural language questions work
- For exact phrase matching, use double quotes: `"pooled PFA"`
- For explicit boolean logic, use FTS5 operators: `PFA AND pooled`
- If results are too broad, use AND: `PFA AND calculation AND pooled`
- If results are too narrow or empty, use fewer keywords

## Important

- Always use `--json` flag when calling from within Claude Code
- Start with a broad query, then narrow down or expand as needed
- If no results, try alternative keywords or check --since/--until range
- The tool auto-indexes on first use, so the first search may take a moment
"""


def get_skill_content() -> str:
    """Return the skill markdown content."""
    return SKILL_CONTENT


def install_skill() -> bool:
    """Install the skill to ~/.claude/skills/search-history.md.

    Returns True if installed successfully, False otherwise.
    """
    try:
        SKILL_PATH.parent.mkdir(parents=True, exist_ok=True)
        SKILL_PATH.write_text(SKILL_CONTENT)
    except OSError as e:
        print(f"Error: Cannot write to {SKILL_PATH}: {e}", file=sys.stderr)
        return False
    return True
