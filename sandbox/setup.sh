#!/bin/bash
# Sets up VM with software and some configs. Can be run multiple
# times.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
export MISE_YES=1
export GITHUB_TOKEN="${GITHUB_TOKEN:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Adding Fish 4 PPA..."
sudo apt-get update
sudo apt-get install -y software-properties-common
sudo apt-add-repository -y ppa:fish-shell/release-4

echo "==> Installing system packages..."
sudo apt-get update
sudo apt-get install -y $(cat "$SCRIPT_DIR/packages.txt")

echo "==> Installing Docker..."
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"

echo "==> Installing NuShell..."
sudo bash "$SCRIPT_DIR/install-nushell.sh"

echo "==> Setting up PATH..."
export PATH="$HOME/.local/share/mise/shims:$HOME/.local/bin:$HOME/.npm-global/bin:$HOME/.cargo/bin:$PATH"

echo "==> Configuring git..."
git config --global credential.helper store
git config --global user.email "italo@maleldil.com"
git config --global user.name "Italo Silva"
git config --global init.defaultBranch master
if [ -n "$GITHUB_TOKEN" ]; then
	echo "https://oyarsa:$GITHUB_TOKEN@github.com" >~/.git-credentials
fi

echo "==> Installing chezmoi and applying dotfiles..."
sh -c "$(curl -fsLS get.chezmoi.io)" -- -b ~/.local/bin
~/.local/bin/chezmoi init --apply oyarsa

echo "==> Installing Rust via rustup..."
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
. "$HOME/.cargo/env"
rustup component add rust-analyzer

echo "==> Installing mise..."
curl https://mise.run | sh

echo "==> Copying mise configuration..."
mkdir -p ~/.config/mise
cp "$SCRIPT_DIR/mise.toml" ~/.config/mise/config.toml

echo "==> Installing mise tools..."
~/.local/bin/mise install

echo "==> Installing Homebrew..."
NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"

echo "==> Installing Claude Code..."
curl -fsSL https://claude.ai/install.sh | bash

echo "==> Installing Fisher and plugins..."
fish -c "curl -sL https://raw.githubusercontent.com/jorgebucaran/fisher/main/functions/fisher.fish | source && fisher install jorgebucaran/fisher"
fish -c "fisher update"

echo "==> Installing tmux plugin manager..."
[ -d ~/.tmux/plugins/tpm ] || git clone https://github.com/tmux-plugins/tpm ~/.tmux/plugins/tpm

echo "==> Changing default shell to fish..."
sudo chsh -s /usr/bin/fish "$USER"

echo "==> Done! Log out and back in (or run 'exec fish') to start using the new setup."
