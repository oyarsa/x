{ config, pkgs, lib, ... }:

{
  home.packages = with pkgs; [
    # ============================================================
    # Core Build Tools (replaces build-essential)
    # ============================================================
    gcc
    gnumake
    binutils
    pkg-config

    # ============================================================
    # System Utilities (from apt)
    # ============================================================
    cacert              # ca-certificates
    curl
    wget
    unzip
    zstd
    htop
    btop                # Also from mise
    lsof
    psmisc              # killall, pstree, etc.
    cloc
    kitty.terminfo      # kitty-terminfo

    # ============================================================
    # Programming Languages (from mise)
    # ============================================================
    # Node.js LTS
    nodejs_22
    nodePackages.npm

    # Go (latest)
    go

    # Rust (stable toolchain from nixpkgs)
    rustc
    cargo
    clippy
    rustfmt
    # rust-analyzer is in Language Servers section

    # Python via uv
    uv

    # Lua (for neovim plugins)
    lua5_1
    luajit

    # ============================================================
    # Development Tools (from mise)
    # ============================================================
    neovim
    just                # Task runner
    jujutsu             # jj - Git alternative
    gh                  # GitHub CLI
    delta               # Git diff viewer
    pandoc              # Document converter

    # ============================================================
    # CLI Utilities (from mise)
    # ============================================================
    fzf                 # Fuzzy finder
    fd                  # Fast find alternative
    ripgrep             # Fast grep alternative (rg)
    bat                 # Cat with syntax highlighting
    eza                 # Modern ls replacement
    zoxide              # Smarter cd command
    jq                  # JSON processor
    fx                  # JSON viewer
    glow                # Markdown pager

    # ============================================================
    # Language Servers (for neovim LSP)
    # ============================================================
    lua-language-server
    nodePackages.typescript-language-server
    nodePackages.eslint
    pyright
    ruff
    rust-analyzer

    # ============================================================
    # Shell & Terminal
    # ============================================================
    fish
    starship            # Cross-shell prompt
    tmux

    # ============================================================
    # Additional Tools
    # ============================================================
    # Playwright with browser dependencies
    playwright-driver.browsers

    # Git (core)
    git

    # Tree-sitter for neovim
    tree-sitter

    # Nix tools
    nil                 # Nix LSP
    nixfmt-rfc-style    # Nix formatter
  ];

  # Programs that need special configuration beyond just installation
  programs = {
    # Direnv for automatic environment loading
    direnv = {
      enable = true;
      nix-direnv.enable = true;
    };

    # FZF integration
    fzf = {
      enable = true;
      enableFishIntegration = true;
    };

    # Zoxide integration
    zoxide = {
      enable = true;
      enableFishIntegration = true;
      options = [ "--cmd" "k" ];  # Use 'k' instead of 'z'
    };

    # Bat configuration
    bat = {
      enable = true;
      config = {
        theme = "base16";
        style = "numbers,changes";
      };
    };
  };
}
