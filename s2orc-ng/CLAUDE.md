# Development

After making changes to Python files, always run:

```bash
just lint
```

This runs ruff (format + check) and pyright for type checking.

## Running scripts

Use `uv run script.py` instead of `uv run python script.py` - uv will pick the right Python automatically.
