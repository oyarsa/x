#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$SCRIPT_DIR/config"

echo "==> Installing system packages..."
sudo apt-get update && sudo apt-get install -y \
    git \
    curl \
    wget \
    sudo \
    tmux \
    fish \
    build-essential \
    kitty-terminfo \
    ncurses-term \
    zoxide \
    bat \
    fd-find \
    ripgrep \
    fzf \
    jq \
    zstd \
    ca-certificates \
    unzip \
    pandoc

echo "==> Creating symlinks for bat and fd..."
mkdir -p ~/.local/bin
ln -sf /usr/bin/batcat ~/.local/bin/bat
ln -sf /usr/bin/fdfind ~/.local/bin/fd

echo "==> Setting up PATH..."
export PATH="$HOME/.local/share/bob/nvim-bin:$HOME/.local/share/mise/shims:$HOME/.local/bin:$HOME/.npm-global/bin:$HOME/.cargo/bin:$PATH"

echo "==> Installing mise..."
curl https://mise.run | sh

echo "==> Configuring mise..."
mkdir -p ~/.config/mise
ln -sf "$CONFIG_DIR/mise.toml" ~/.config/mise/config.toml

echo "==> Installing mise tools..."
~/.local/bin/mise install

echo "==> Installing Neovim via bob..."
~/.local/share/mise/shims/bob use v0.11.2

echo "==> Installing fleche..."
~/.local/share/mise/shims/cargo install --git https://github.com/oyarsa/fleche

echo "==> Installing Claude Code..."
curl -fsSL https://claude.ai/install.sh | bash

echo "==> Installing Playwright with Chromium..."
npx playwright install --with-deps chromium
claude mcp add --scope user playwright -- npx @playwright/mcp@latest --headless --no-sandbox

echo "==> Linking config files..."

# tmux
ln -sf "$CONFIG_DIR/tmux.conf" ~/.tmux.conf

# neovim
mkdir -p ~/.config/nvim
ln -sf "$CONFIG_DIR/vimrc" ~/.config/nvim/init.vim
ln -sf ~/.config/nvim/init.vim ~/.vimrc

# fish
mkdir -p ~/.config/fish/conf.d ~/.config/fish/functions
ln -sf "$CONFIG_DIR/fish/config.fish" ~/.config/fish/config.fish
for f in "$CONFIG_DIR/fish/conf.d/"*; do
    ln -sf "$f" ~/.config/fish/conf.d/
done
for f in "$CONFIG_DIR/fish/functions/"*; do
    ln -sf "$f" ~/.config/fish/functions/
done

# jujutsu
ln -sf "$CONFIG_DIR/jjconfig.toml" ~/.jjconfig.toml

echo "==> Configuring git..."
git config --global credential.helper store
git config --global user.email "italo@maleldil.com"
git config --global user.name "Italo Silva"
git config --global init.defaultBranch main

echo "==> Changing default shell to fish..."
sudo chsh -s /usr/bin/fish "$USER"

echo "==> Done! Log out and back in (or run 'fish') to start using the new setup."
