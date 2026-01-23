#!/bin/bash
set -euo pipefail

echo "==> Installing Docker..."
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"

echo "==> Installing GitHub CLI..."
sudo mkdir -p -m 755 /etc/apt/keyrings
wget -qO- https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg >/dev/null
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list >/dev/null
sudo apt-get update
sudo apt-get install -y gh

echo "==> Authenticating with GitHub..."
gh auth login

echo "==> Cloning repository..."
if [ ! -d "$HOME/x" ]; then
	gh repo clone oyarsa/x "$HOME/x"
else
	echo "    Repository already exists at ~/x"
fi

echo "==> Setting up sandbox command..."
mkdir -p ~/.local/bin
ln -sf "$HOME/x/sandbox/sandbox.py" ~/.local/bin/sandbox

echo "==> Building container image..."
sg docker -c "$HOME/.local/bin/sandbox rebuild"

# Ensure ~/.local/bin is in PATH
if ! echo "$PATH" | grep -q "$HOME/.local/bin"; then
	echo 'export PATH="$HOME/.local/bin:$PATH"' >>~/.bashrc
	echo "    Added ~/.local/bin to PATH in ~/.bashrc"
fi

echo "==> Done! Starting new shell with docker group..."
echo "    Run 'sandbox up' to start the container."
echo ""
exec newgrp docker
