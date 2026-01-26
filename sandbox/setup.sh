#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$SCRIPT_DIR/config"

echo "==> Installing system packages..."
sudo apt-get update && sudo apt-get install -y \
	git \
	curl \
	sudo \
	fish \
	build-essential \
	kitty-terminfo \
	zstd \
	ca-certificates \
	unzip \
	lsof \
	psmisc \
	htop

echo "==> Setting up PATH..."
export PATH="$HOME/.local/share/mise/shims:$HOME/.local/bin:$HOME/.npm-global/bin:$HOME/.cargo/bin:$PATH"

echo "==> Installing mise..."
curl https://mise.run | sh

echo "==> Configuring mise..."
mkdir -p ~/.config/mise
ln -sf "$CONFIG_DIR/mise.toml" ~/.config/mise/config.toml

echo "==> Installing mise tools..."
~/.local/bin/mise install

echo "==> Installing Claude Code..."
curl -fsSL https://claude.ai/install.sh | bash

echo "==> Installing Playwright with Chromium..."
npx playwright install --with-deps chromium
claude mcp add --scope user playwright -- npx @playwright/mcp@latest --headless --no-sandbox

echo "==> Linking config files..."

# tmux
ln -sf "$CONFIG_DIR/tmux.conf" ~/.tmux.conf

# neovim
mkdir -p ~/.config/nvim/lua
ln -sf "$CONFIG_DIR/nvim/init.vim" ~/.config/nvim/init.vim
ln -sf "$CONFIG_DIR/nvim/lua/config.lua" ~/.config/nvim/lua/config.lua
ln -sf "$CONFIG_DIR/nvim/lua/lsp.lua" ~/.config/nvim/lua/lsp.lua

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

echo "==> Installing Fisher and plugins..."
fish -c "curl -sL https://raw.githubusercontent.com/jorgebucaran/fisher/main/functions/fisher.fish | source && fisher install jorgebucaran/fisher"
fish -c "fisher install gazorby/fifc"

echo "==> Configuring git..."
git config --global credential.helper store
git config --global user.email "italo@maleldil.com"
git config --global user.name "Italo Silva"
git config --global init.defaultBranch master

echo "==> Changing default shell to fish..."
sudo chsh -s /usr/bin/fish "$USER"

echo "==> Fixing cache directory ownership..."
sudo chown -R "$USER:$USER" ~/.cache

echo "==> Done! Log out and back in (or run 'fish') to start using the new setup."
