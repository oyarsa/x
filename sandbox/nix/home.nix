{ config, pkgs, lib, userConfig, ... }:

{
  # Home Manager needs a bit of information about you and the paths it should manage
  home.username = userConfig.username;
  home.homeDirectory = userConfig.homeDirectory;

  # This value determines the Home Manager release that your configuration is
  # compatible with. This helps avoid breakage when a new Home Manager release
  # introduces backwards incompatible changes.
  home.stateVersion = "24.05";

  # Let Home Manager install and manage itself
  programs.home-manager.enable = true;

  # Allow unfree packages
  nixpkgs.config.allowUnfree = true;

  # XDG Base Directory specification
  xdg.enable = true;

  # Environment variables
  home.sessionVariables = {
    EDITOR = "nvim";
    VISUAL = "nvim";
    NODE_OPTIONS = "--max-old-space-size=3072";
    UV_LINK_MODE = "copy";
    # FZF configuration
    FZF_DEFAULT_OPTS = "--height 40% --layout=reverse --border";
    FZF_VIM_PATH = "${pkgs.fzf}/share/vim-plugins/fzf";
  };

  # Additional PATH entries
  home.sessionPath = [
    "$HOME/.local/bin"
    "$HOME/.npm-global/bin"
    "$HOME/.cargo/bin"
    "$HOME/go/bin"
  ];

  # Create necessary directories
  home.activation.createDirs = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
    mkdir -p $HOME/.local/bin
    mkdir -p $HOME/.npm-global
    mkdir -p $HOME/.cache
    mkdir -p $HOME/workspace
  '';

  # Nix configuration
  nix = {
    package = pkgs.nix;
    settings = {
      experimental-features = [ "nix-command" "flakes" ];
      warn-dirty = false;
    };
  };
}
