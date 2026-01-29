{ config, pkgs, lib, userConfig, configFiles, ... }:

{
  # Git configuration
  programs.git = {
    enable = true;
    userName = userConfig.fullName;
    userEmail = userConfig.email;

    extraConfig = {
      init.defaultBranch = "master";
      credential.helper = "store";
      core.pager = "delta";
      interactive.diffFilter = "delta --color-only";
      merge.conflictstyle = "diff3";
      diff.colorMoved = "default";

      # Delta configuration
      delta = {
        navigate = true;
        light = false;
        line-numbers = true;
      };
    };

    # Git aliases
    aliases = {
      co = "checkout";
      br = "branch";
      ci = "commit";
      st = "status";
      lg = "log --graph --oneline --decorate";
    };
  };

  # Jujutsu (jj) configuration - using external file
  home.file.".jjconfig.toml".source = configFiles.jjconfig;

  # GitHub CLI configuration
  programs.gh = {
    enable = true;
    settings = {
      git_protocol = "https";
      prompt = "enabled";
    };
  };
}
