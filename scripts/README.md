# scripts

Repository for random scripts that I write over time.

Random Python things, which are collected in a single project and installed as package.
The project is maintained with uv and can be installed as a package, so each individual
script can be run as a standalone command.

## Installation

Requirements:
- Python 3.12
- uv, pipx or others

```bash
> git clone git@github.com:oyarsa/scripts.git
# Install with uv
> uv tool install --editable scripts
# Or with pipx
> pipx install --editable scripts
```

Scripts should be named with a lead `,` (e.g. `,ntok`) so that they are easy to find in
the shell.

## License

This project is licensed under the GPL version 3 or later.
