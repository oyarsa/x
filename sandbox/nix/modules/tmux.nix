{ config, pkgs, lib, configFiles, ... }:

{
  programs.tmux = {
    enable = true;
    # Shell path requires Nix interpolation
    shell = "${pkgs.fish}/bin/fish";

    # Source the rest from external config file
    extraConfig = builtins.readFile configFiles.tmux;
  };
}
