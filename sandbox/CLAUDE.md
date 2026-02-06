# Sandbox

Development environment setup for containerized or VM-based workspaces.

## Structure

- `Dockerfile`: Container-based setup (Ubuntu 25.10)
- `setup.sh`: VM/bare-metal setup script (Ubuntu 24.04)
- `packages.txt`: System packages installed by both Dockerfile and setup.sh
- `mise.toml`: Mise tool configuration (copied to `~/.config/mise/config.toml`)
- `sandbox.py`: Python script for managing container workspaces

Dotfiles are managed separately via chezmoi from `github.com/oyarsa/dotfiles`.

## Important

**Dockerfile and setup.sh must stay in sync.** Any changes to package installation, tool setup, or configuration in one file must be replicated in the other. They serve the same purpose for different environments:

- `Dockerfile` → container environments
- `setup.sh` → cloud VMs / bare-metal machines

When modifying either file, always update the other to match.
