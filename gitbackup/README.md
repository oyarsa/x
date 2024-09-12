# Git Backup

Clone all repositories from a GitHub user, including the private ones. Requires a GitHub
API token to list the repositories, and set up SSH keys to clone the private
repositories.

## Usage

Requires [`uv` version 0.4 or later.](https://docs.astral.sh/uv/)

Assumes GITHUB_TOKEN is set in the environment:

```bash
uv run backup.py
```

Otherwise, you can pass the token as an argument:

```bash
uv run backup.py --token <token>
```

Preference is given to the token passed as the argument.


Clones the repositories to a temporary directory  and compresses it to `backup.tar.gz`.
See `uv run backup.py --help` for more options.
