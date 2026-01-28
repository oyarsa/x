FROM ubuntu:25.10

ENV DEBIAN_FRONTEND=noninteractive

# Allow fzf docs (vim plugin) despite docker image excludes
RUN echo 'path-include=/usr/share/doc/fzf/*' > /etc/dpkg/dpkg.cfg.d/fzf

# Core packages
RUN apt-get update && apt-get install -y \
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
    htop \
    cloc \
    fzf \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user with sudo access (UID matches host user)
RUN useradd -m -s /usr/bin/fish -u $UID dev && \
    echo "dev ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Switch to dev user for remaining setup
USER dev
ENV HOME=/home/dev
ENV PATH="/home/dev/.local/share/mise/shims:/home/dev/.local/bin:/home/dev/.npm-global/bin:/home/dev/.cargo/bin:${PATH}"
WORKDIR /home/dev

# Copy configuration files (dot_ prefix becomes . in destination)
COPY --chown=dev:dev config/ /tmp/config/
RUN for src in $(find /tmp/config -type f); do \
      rel="${src#/tmp/config/}"; \
      dst="$HOME/$(echo "$rel" | sed 's/dot_/./g')"; \
      mkdir -p "$(dirname "$dst")"; \
      cp "$src" "$dst"; \
    done && rm -rf /tmp/config

# Install mise and tools
ENV MISE_YES=1
RUN curl https://mise.run | sh
RUN --mount=type=secret,id=gh_token \
    export GITHUB_TOKEN="$(cat /run/secrets/gh_token 2>/dev/null)" && \
    for i in 1 2 3; do mise install && break || sleep 5; done

# Install Claude Code
RUN curl -fsSL https://claude.ai/install.sh | bash

# Install Playwright with Chromium and configure MCP
RUN npx playwright install --with-deps chromium && \
    claude mcp add --scope user playwright -- npx @playwright/mcp@latest --headless --no-sandbox

# Install Fisher and plugins
RUN fish -c "curl -sL https://raw.githubusercontent.com/jorgebucaran/fisher/main/functions/fisher.fish | source && fisher install jorgebucaran/fisher"
RUN fish -c "fisher install gazorby/fifc"

# Git configuration
RUN git config --global credential.helper store && \
    git config --global user.email "italo@maleldil.com" && \
    git config --global user.name "Italo Silva" && \
    git config --global init.defaultBranch master

# Create directories for transfer and workspace (need sudo for /workspace)
RUN sudo mkdir -p /transfer /workspace && \
    sudo chown dev:dev /transfer /workspace

# Fix any cache directories that may have been created as root (e.g., by playwright --with-deps)
RUN sudo chown -R dev:dev ~/.cache

# Default to fish shell
CMD ["fish"]
