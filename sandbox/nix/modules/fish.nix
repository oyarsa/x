{ config, pkgs, lib, configFiles, ... }:

{
  programs.fish = {
    enable = true;

    # Shell abbreviations (expand on space)
    shellAbbrs = {
      v = "nvim";
      r = "uv run";
      j = "just";
      "..." = "../..";
      "...." = "../../..";
    };

    # Shell aliases (expand on enter)
    shellAliases = {
      vim = "nvim";
      tree = "eza --tree";
    };

    # Interactive shell initialization - only Nix-specific parts
    # The rest is in config.fish
    interactiveShellInit = ''
      # FZF key bindings (from Nix package)
      if test -f ${pkgs.fzf}/share/fzf/key-bindings.fish
          source ${pkgs.fzf}/share/fzf/key-bindings.fish
      end

      # Set FZF_VIM_PATH for neovim's fzf integration
      set -gx FZF_VIM_PATH "${pkgs.fzf}/share/vim-plugins/fzf"
    '';

    # Fish plugins
    plugins = [
      {
        name = "fifc";
        src = pkgs.fetchFromGitHub {
          owner = "gazorby";
          repo = "fifc";
          rev = "v0.6.1";
          sha256 = "sha256-aH0bVFb0oMUmJKL0t0sHvmUvT3GCYbUWMNvJlwm6I0Y=";
        };
      }
    ];
  };

  # Fish configuration files - using source to preserve editor support
  # Note: programs.fish generates its own config.fish, so we use conf.d for our config
  xdg.configFile = {
    # Main config goes in conf.d to be sourced by home-manager's generated config.fish
    "fish/conf.d/00-config.fish".source = configFiles.fish.config;

    # Environment variables
    "fish/conf.d/env_vars.fish".source = configFiles.fish.confD.envVars;

    # Jujutsu aliases
    "fish/conf.d/jj.fish".source = configFiles.fish.confD.jj;

    # Fish functions
    "fish/functions/vim.fish".source = configFiles.fish.functions.vim;
    "fish/functions/tree.fish".source = configFiles.fish.functions.tree;
    "fish/functions/rg.fish".source = configFiles.fish.functions.rg;
    "fish/functions/yolo.fish".source = configFiles.fish.functions.yolo;
    "fish/functions/,fx.fish".source = configFiles.fish.functions.fx;
    "fish/functions/,jq.fish".source = configFiles.fish.functions.jq;
  };
}
