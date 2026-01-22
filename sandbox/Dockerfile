FROM ubuntu:25.10

ARG UID=501
ENV DEBIAN_FRONTEND=noninteractive

# Core packages
RUN apt-get update && apt-get install -y \
    git \
    curl \
    wget \
    sudo \
    tmux \
    vim \
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
    pandoc \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user with sudo access (UID matches host user)
RUN useradd -m -s /usr/bin/fish -u $UID dev && \
    echo "dev ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Switch to dev user for remaining setup
USER dev
ENV HOME=/home/dev
ENV PATH="/home/dev/.local/share/mise/shims:/home/dev/.local/bin:/home/dev/.npm-global/bin:/home/dev/.cargo/bin:${PATH}"
WORKDIR /home/dev

# Create symlinks for bat and fd (Ubuntu uses different names)
RUN mkdir -p ~/.local/bin && \
    ln -sf /usr/bin/batcat ~/.local/bin/bat && \
    ln -sf /usr/bin/fdfind ~/.local/bin/fd

# Install mise and tools
ENV MISE_YES=1
RUN curl https://mise.run | sh
RUN mkdir -p ~/.config/mise
COPY --chown=dev:dev config/mise.toml /home/dev/.config/mise/config.toml
RUN --mount=type=secret,id=gh_token \
    export GITHUB_TOKEN="$(cat /run/secrets/gh_token 2>/dev/null)" && \
    for i in 1 2 3; do mise install && break || sleep 5; done

# Install fleche (notification helper)
RUN cargo install --git https://github.com/oyarsa/fleche

# Install fx (JSON viewer)
RUN go install github.com/antonmedv/fx@latest

# Install Claude Code
RUN curl -fsSL https://claude.ai/install.sh | bash

# Copy configuration files
COPY --chown=dev:dev config/tmux.conf /home/dev/.tmux.conf
COPY --chown=dev:dev config/vimrc /home/dev/.vimrc
RUN mkdir -p ~/.config/fish/conf.d
COPY --chown=dev:dev config/config.fish /home/dev/.config/fish/config.fish
COPY --chown=dev:dev config/conf.d/ /home/dev/.config/fish/conf.d/

# Git configuration
RUN git config --global credential.helper store && \
    git config --global user.email "italo@maleldil.com" && \
    git config --global user.name "Italo Silva" && \
    git config --global init.defaultBranch main

# jj configuration
COPY --chown=dev:dev config/jjconfig.toml /home/dev/.jjconfig.toml

# Create directories for transfer and workspace (need sudo for /workspace)
RUN sudo mkdir -p /transfer /workspace && \
    sudo chown dev:dev /transfer /workspace

# Default to fish shell
CMD ["fish"]
