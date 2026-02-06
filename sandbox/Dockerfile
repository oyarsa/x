FROM ubuntu:25.10

ENV DEBIAN_FRONTEND=noninteractive

# Add Fish 4 PPA and install core packages
COPY packages.txt /tmp/packages.txt
RUN apt-get update && apt-get install -y software-properties-common && \
    apt-add-repository -y ppa:fish-shell/release-4 && \
    apt-get update && apt-get install -y $(cat /tmp/packages.txt) && \
    rm -rf /var/lib/apt/lists/* /tmp/packages.txt

# Create non-root user with sudo access (UID matches host user)
RUN useradd -m -s /usr/bin/fish -u $UID dev && \
    echo "dev ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Switch to dev user for remaining setup
USER dev
ENV HOME=/home/dev
ENV PATH="/home/dev/.local/share/mise/shims:/home/dev/.local/bin:/home/dev/.npm-global/bin:/home/dev/.cargo/bin:${PATH}"
WORKDIR /home/dev

# Git configuration and credentials
RUN git config --global credential.helper store && \
    git config --global user.email "italo@maleldil.com" && \
    git config --global user.name "Italo Silva" && \
    git config --global init.defaultBranch master

# Install chezmoi and apply dotfiles
RUN --mount=type=secret,id=gh_token \
    export GITHUB_TOKEN="$(cat /run/secrets/gh_token 2>/dev/null)" && \
    if [ -n "$GITHUB_TOKEN" ]; then echo "https://oyarsa:$GITHUB_TOKEN@github.com" > ~/.git-credentials; fi && \
    sh -c "$(curl -fsLS get.chezmoi.io)" -- -b ~/.local/bin && \
    ~/.local/bin/chezmoi init --apply oyarsa

# Install mise and tools
ENV MISE_YES=1
RUN curl https://mise.run | sh
COPY --chown=dev:dev mise.toml /home/dev/.config/mise/config.toml
RUN --mount=type=secret,id=gh_token \
    export GITHUB_TOKEN="$(cat /run/secrets/gh_token 2>/dev/null)" && \
    for i in 1 2 3; do mise install && break || sleep 5; done

# Install Claude Code
RUN curl -fsSL https://claude.ai/install.sh | bash

# Install Playwright with Chromium and configure MCP
RUN npx playwright install --with-deps chromium && \
    (claude mcp remove --scope user playwright 2>/dev/null || true) && \
    claude mcp add --scope user playwright -- npx @playwright/mcp@latest --headless --no-sandbox --isolated --browser chromium

# Install Fisher and plugins
RUN fish -c "curl -sL https://raw.githubusercontent.com/jorgebucaran/fisher/main/functions/fisher.fish | source && fisher install jorgebucaran/fisher"
RUN fish -c "fisher install gazorby/fifc"

# Install tmux plugin manager
RUN git clone https://github.com/tmux-plugins/tpm ~/.tmux/plugins/tpm

# Create directories for transfer and workspace (need sudo for /workspace)
RUN sudo mkdir -p /transfer /workspace && \
    sudo chown dev:dev /transfer /workspace

# Fix any cache directories that may have been created as root (e.g., by playwright --with-deps)
RUN sudo chown -R dev:dev ~/.cache

# Default to fish shell
CMD ["fish"]
