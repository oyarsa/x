# Codebase Guidelines

## Workflow Rules
- **ALWAYS run `just lint`** after code changes before considering the task complete
- **ALWAYS notify the user** when done, even without needing input

## Commands
- `just lint` - Main check: fix, fmt, spell, pre-commit, test, type

## Code Style
- **All files must be shorter than 1000 non-empty lines** (blank lines don't count). If
  a file exceeds this limit, split it into smaller, well-organized modules.
- Python 3.12+ with strict typing (no exceptions)
- Functional programming with dataclasses over OOP
- British English everywhere
- Absolute imports from `parch` package
- Google-style docstrings
- Never use hasattr/getattr - get proper type and access fields

## Version Control
- Use **jujutsu** (`jj`), not git
- Do NOT add `Co-Authored-By` lines to commits
- `jj commit -m "<message>"` to commit (no staging needed)
- Only commit when requested
- First line of commit messages <= 69 chars
