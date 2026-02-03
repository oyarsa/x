# Claude Code Sandbox

A Docker-based sandbox for running Claude Code in "dangerous mode" safely, isolated from your host system.

## Requirements

- A Docker-compatible runtime (e.g. colima on macOS)
- Git
- Python 3.10+

## Setup

1. Copy this directory somewhere permanent (e.g., `~/tools/claude-sandbox/`)
2. Optionally symlink `sandbox.py` to your PATH:
   ```bash
   ln -s ~/tools/claude-sandbox/sandbox.py ~/.local/bin/sandbox
   chmod +x ~/tools/claude-sandbox/sandbox.py
   ```

## Usage

From any git repository directory:

```bash
# Start the sandbox (clones your repo inside, runs setup)
sandbox up

# Enter the sandbox shell
sandbox shell

# Inside the sandbox, run Claude Code
yolo  # Enables dangerous mode

# Copy files into the sandbox (they appear at /transfer/)
sandbox cp-in data.csv

# Copy files out of the sandbox (they appear in ./out/)
sandbox cp-out output/results.json

# Stop the sandbox (container is deleted but workspace persists!)
sandbox down

# Stops the container without deleting content
sandbox stop

# Restarts container
sandbox start
```

## How It Works

1. **Isolation**: Your code runs inside a Docker container. Claude Code can do whatever it wants there without affecting your host system.

2. **Repository cloning**: When you run `sandbox up` from a git repo, it detects the remote URL and clones a fresh copy inside a persistent workspace.

3. **Persistent workspaces**: Each repository gets its own workspace directory at `workspaces/<repo-name>/`. This persists across `down`/`up` cycles—your work is never lost.

4. **File transfer**:
   - `cp-in`: Copies files to `./transfer/`, mounted read-only at `/transfer` in the container
   - `cp-out`: Copies files from the container to `./out/` on the host
   - `files` field: configuration allows listing files to be copied to the repo (e.g. `.env`)

## Directory Structure

```
claude-sandbox/
├── Dockerfile          # Container image definition
├── sandbox.py          # Main helper script
├── config/             # Configuration files copied into container
│   ├── config.fish
│   ├── tmux.conf
│   └── vimrc
├── transfer/           # Files to transfer INTO the container (read-only)
├── out/                # Files copied OUT of the container
└── workspaces/         # Persistent workspaces (one per repo)
    └── <repo-name>/    # Mounted at /workspace/<repo-name> in container
```

## Commands

| Command | Description |
|---------|-------------|
| `init` | Create .mysandbox.toml config file |
| `up` | Start sandbox, clone repo, run setup |
| `shell` | Enter interactive fish shell |
| `exec <cmd>` | Run a single command |
| `cp-in <path>` | Copy file/dir to transfer/ |
| `cp-out <path>` | Copy file/dir from container to out/ |
| `stop` | Stop container (preserves state, use `start` to resume) |
| `start` | Start a stopped container |
| `down` | Remove container (workspace persists, but state is lost) |
| `status` | Show sandbox status |
| `logs` | Show container logs |
| `rebuild` | Force rebuild the Docker image |
| `list` | List all workspaces |
| `destroy <name>` | Remove a workspace |

## Installed Tools

The sandbox includes:
- **Shell**: fish, tmux, fzf
- **Python**: uv, mise
- **Node.js**: npm, Claude Code CLI
- **Rust**: rustup, cargo, clippy, rustfmt
- **Go**: go 1.23
- **Version control**: git, jj
- **CLI tools**: eza, bat, fd, ripgrep, just, zoxide, atuin, mdcat

## Tips

### Authenticating with GitHub

On first `git push` inside the sandbox, you'll be prompted for credentials. Use a GitHub Personal Access Token as the password. The credential helper will store it for the session.

### Claude Code Authentication

Run `claude` inside the sandbox and follow the interactive login prompts.

### Persistent Workspaces

Workspaces persist in `workspaces/<repo-name>/`. When you run `sandbox down`, the container stops but your files remain. Next time you run `sandbox up` from the same repo, it will reuse the existing workspace.

To remove a workspace: `sandbox destroy <repo-name>`

### Multiple Projects

You can run `sandbox up` from different git repos—it will stop the existing container and start a new one. Each repo has its own persistent workspace, so switching projects doesn't lose work.

### Project Configuration

Create a `.mysandbox.toml` file in your project root to customize sandbox behavior:

```toml
branch = "main"           # Branch to clone (default: "master")
setup = "uv sync"         # Command to run after cloning
check = "uv run pytest"   # Command to run after setup
files = [                 # Files to copy into the workspace
    ".env",               # Relative to repo root
    "~/.secrets.json"     # Absolute or ~ paths work too
]
```

All fields are optional. Setup and check commands run inside the cloned repo and support shell features like `&&`.
