#!/bin/bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
export MISE_YES=1
export GITHUB_TOKEN="${GITHUB_TOKEN:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$SCRIPT_DIR/config"

echo "==> Allowing fzf docs (vim plugin) despite any dpkg excludes..."
echo 'path-include=/usr/share/doc/fzf/*' | sudo tee /etc/dpkg/dpkg.cfg.d/fzf > /dev/null

echo "==> Installing system packages..."
sudo apt-get update && sudo apt-get install -y \
	git \
	curl \
	sudo \
	fish \
	build-essential \
	python3-dev \
	kitty-terminfo \
	zstd \
	ca-certificates \
	unzip \
	lsof \
	psmisc \
	htop \
	cloc \
	fzf

echo "==> Setting up PATH..."
export PATH="$HOME/.local/share/mise/shims:$HOME/.local/bin:$HOME/.npm-global/bin:$HOME/.cargo/bin:$PATH"

echo "==> Linking config files..."

# Transform dot_ prefix to . and create symlinks
for src in $(find "$CONFIG_DIR" -type f); do
	rel="${src#$CONFIG_DIR/}"
	# Transform dot_ prefix to . in path components
	dst="$HOME/$(echo "$rel" | sed 's/dot_/./g')"
	mkdir -p "$(dirname "$dst")"
	ln -sf "$src" "$dst"
done

echo "==> Installing mise..."
curl https://mise.run | sh

echo "==> Installing mise tools..."
~/.local/bin/mise install

echo "==> Installing Claude Code..."
curl -fsSL https://claude.ai/install.sh | bash

echo "==> Installing Playwright with Chromium..."
npx playwright install --with-deps chromium
claude mcp remove --scope user playwright 2>/dev/null || true
claude mcp add --scope user playwright -- npx @playwright/mcp@latest --headless --no-sandbox --isolated --browser chromium

echo "==> Installing Fisher and plugins..."
for i in 1 2 3; do
	timeout 60 fish -c "curl -sL https://raw.githubusercontent.com/jorgebucaran/fisher/main/functions/fisher.fish | source && fisher install jorgebucaran/fisher" && break
	echo "Fisher install attempt $i failed, retrying..."
	sleep 2
done
for i in 1 2 3; do
	timeout 60 fish -c "fisher install gazorby/fifc" && break
	echo "fifc install attempt $i failed, retrying..."
	sleep 2
done

echo "==> Configuring git..."
git config --global credential.helper store
git config --global user.email "italo@maleldil.com"
git config --global user.name "Italo Silva"
git config --global init.defaultBranch master

echo "==> Changing default shell to fish..."
sudo chsh -s /usr/bin/fish "$USER"

echo "==> Done! Log out and back in (or run 'fish') to start using the new setup."
