# Nix VM Provisioning

Declarative cloud VM provisioning using Nix + Home Manager on Ubuntu 24.04.

## Overview

This configuration provides a fully declarative way to provision cloud VMs,
replacing the previous apt + mise + manual configuration approach. All software
and configuration files are managed through Nix, making it easy to:

- Reproduce identical environments across multiple VMs
- Keep configurations in sync with version control
- Roll back to previous configurations
- Understand exactly what's installed and configured

## Quick Start

On a fresh Ubuntu 24.04 VM:

```bash
# Clone the repository
git clone https://github.com/oyarsa/x.git
cd x/sandbox/nix

# Run the bootstrap script
./bootstrap.sh
```

The bootstrap script will:
1. Install Nix using the Determinate Systems installer
2. Enable flakes support
3. Apply the home-manager configuration (installs all packages)
4. Set fish as the default shell

All tools are managed declaratively by Nix, including:
- **Rust**: rustc, cargo, clippy, rustfmt from nixpkgs
- **Playwright**: Browsers managed via `playwright-driver.browsers`
- **Claude Code**: Installed automatically via home-manager activation

## Structure

```
nix/
├── flake.nix           # Main entry point, user config, file path mappings
├── flake.lock          # Locked dependency versions
├── home.nix            # Core home-manager configuration
├── bootstrap.sh        # One-command installation script
├── README.md           # This file
├── config/             # Actual config files (edit these for customization)
│   ├── nvim/
│   │   ├── init.vim    # Main neovim config
│   │   ├── .luarc.json # Lua language server config
│   │   ├── lua/        # Lua modules (config, lsp, git, symbols)
│   │   └── lsp/        # LSP server configurations
│   ├── fish/
│   │   ├── config.fish # Main fish config
│   │   ├── conf.d/     # Additional config (env_vars, jj aliases)
│   │   └── functions/  # Fish functions
│   ├── tmux/
│   │   └── tmux.conf   # Tmux configuration
│   └── jjconfig.toml   # Jujutsu configuration
└── modules/            # Nix modules (define what gets installed where)
    ├── packages.nix    # All installed packages
    ├── fish.nix        # Fish shell module
    ├── neovim.nix      # Neovim module
    ├── tmux.nix        # Tmux module
    ├── git.nix         # Git and Jujutsu module
    └── starship.nix    # Prompt module
```

**Key design**: Configuration files live in `config/` as regular files with
full editor support (syntax highlighting, LSP, etc.). The Nix modules in
`modules/` just wire these files to the right locations.

## Customization

### Changing User Details

Edit `flake.nix` and modify the `userConfig` block:

```nix
userConfig = {
  username = "dev";
  fullName = "Your Name";
  email = "you@example.com";
  homeDirectory = "/home/dev";
};
```

### Adding Packages

Edit `modules/packages.nix` and add packages to the `home.packages` list:

```nix
home.packages = with pkgs; [
  # ... existing packages ...
  your-new-package
];
```

### Modifying Shell Configuration

Edit the files in `config/fish/`:
- `config.fish` - Main fish configuration
- `conf.d/env_vars.fish` - Environment variables
- `conf.d/jj.fish` - Jujutsu aliases
- `functions/*.fish` - Custom fish functions

Shell abbreviations and aliases that need Nix paths are in `modules/fish.nix`.

### Modifying Editor Configuration

Edit the files in `config/nvim/`:
- `init.vim` - VimScript settings (keybindings, options)
- `lua/config.lua` - Lua config (FZF, completion, etc.)
- `lua/lsp.lua` - LSP client setup
- `lua/git.lua` - Git integration
- `lua/symbols.lua` - Symbol picker
- `lsp/*.lua` - Per-language LSP configurations

### Modifying Tmux Configuration

Edit `config/tmux/tmux.conf` directly. The shell path is set by Nix.

### Modifying Jujutsu Configuration

Edit `config/jjconfig.toml` directly.

## Common Commands

### Apply Configuration Changes

After modifying any files (config or `.nix`):

```bash
cd ~/x/sandbox/nix
home-manager switch --flake .#dev
```

Note: Changes to config files in `config/` require running this command
to copy them to the right locations.

### Update All Packages

```bash
cd ~/x/sandbox/nix
nix flake update
home-manager switch --flake .#dev
```

### List Installed Packages

```bash
home-manager packages
```

### Check Configuration

```bash
nix flake check
```

### Enter Development Shell

For working on the Nix configuration itself:

```bash
nix develop
```

This provides `nil` (Nix LSP) and `nixfmt-rfc-style` (formatter).

## What's Included

### Packages (replaces apt + mise)

**Languages & Runtimes:**
- Node.js 22 (LTS)
- Go
- Rust (rustc, cargo, clippy, rustfmt)
- Python (via uv)
- Lua/LuaJIT

**Development Tools:**
- Neovim
- Git
- Jujutsu (jj)
- Just (task runner)
- GitHub CLI (gh)
- Delta (git diff viewer)
- Claude Code CLI
- Playwright (with Chromium)

**CLI Utilities:**
- fzf (fuzzy finder)
- fd (fast find)
- ripgrep (fast grep)
- bat (cat with syntax highlighting)
- eza (modern ls)
- zoxide (smart cd)
- jq, fx (JSON tools)
- glow (markdown viewer)
- htop, btop (system monitors)

**Language Servers:**
- lua-language-server
- typescript-language-server
- pyright
- ruff
- rust-analyzer
- eslint

**Shell & Terminal:**
- Fish shell
- Starship prompt
- Tmux

### Configuration

All dotfiles are managed declaratively:
- Fish shell config with custom functions and abbreviations
- Neovim with LSP, FZF integration, and custom keybindings
- Tmux with vim-aware pane navigation
- Git with delta pager
- Jujutsu (jj) configuration
- Starship prompt (minimal, fast)

## Differences from Container Setup

| Feature | Container (Docker) | VM (Nix) |
|---------|-------------------|----------|
| Base | Ubuntu 25.10 | Ubuntu 24.04 |
| Package Manager | apt + mise | Nix |
| Config Management | File copies | Declarative (home-manager) |
| Reproducibility | Dockerfile | Flake lock |
| Updates | Rebuild container | `nix flake update` |
| Rollback | Manual | Built-in generations |

## Troubleshooting

### Nix command not found after install

Source the Nix profile:
```bash
source /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh
```

### Fish shell not in /etc/shells

Add it manually (requires sudo):
```bash
echo "$HOME/.nix-profile/bin/fish" | sudo tee -a /etc/shells
chsh -s "$HOME/.nix-profile/bin/fish"
```

### Home-manager switch fails

Check the error output. Common issues:
- Missing internet connection
- Conflicting files (backup and remove them)
- Syntax errors in `.nix` files

### Packages not available in PATH

Ensure the Nix profile is sourced. In fish:
```fish
fish_add_path ~/.nix-profile/bin
```

## Architecture Notes

This setup uses:

- **Nix Flakes**: For reproducible, hermetic builds with locked dependencies
- **Home Manager**: For user-level package and configuration management
- **Determinate Nix Installer**: For reliable Nix installation with good defaults

Unlike NixOS, this runs on top of Ubuntu, so:
- System services are managed by systemd (not NixOS modules)
- The base system (kernel, init, etc.) is Ubuntu
- Only user-level packages and configs are managed by Nix

This approach gives you the benefits of declarative configuration while
maintaining compatibility with standard Ubuntu cloud images.
