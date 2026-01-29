{ config, pkgs, lib, ... }:

{
  programs.starship = {
    enable = true;
    enableFishIntegration = true;

    settings = {
      # Minimal, fast prompt
      add_newline = false;

      # Show only what matters
      format = lib.concatStrings [
        "$directory"
        "$git_branch"
        "$git_status"
        "$character"
      ];

      # Directory config
      directory = {
        truncation_length = 3;
        truncate_to_repo = true;
        style = "bold cyan";
      };

      # Git branch
      git_branch = {
        format = "[$branch]($style) ";
        style = "bold purple";
      };

      # Git status
      git_status = {
        format = "([$all_status$ahead_behind]($style) )";
        style = "bold red";
        conflicted = "!";
        ahead = "+\${count}";
        behind = "-\${count}";
        diverged = "!\${ahead_count}/\${behind_count}";
        untracked = "?";
        stashed = "*";
        modified = "~";
        staged = "+";
        renamed = ">";
        deleted = "x";
      };

      # Prompt character
      character = {
        success_symbol = "[>](bold green)";
        error_symbol = "[>](bold red)";
      };

      # Disable modules we don't need for speed
      aws.disabled = true;
      azure.disabled = true;
      battery.disabled = true;
      buf.disabled = true;
      bun.disabled = true;
      c.disabled = true;
      cmake.disabled = true;
      cobol.disabled = true;
      conda.disabled = true;
      container.disabled = true;
      crystal.disabled = true;
      daml.disabled = true;
      dart.disabled = true;
      deno.disabled = true;
      docker_context.disabled = true;
      dotnet.disabled = true;
      elixir.disabled = true;
      elm.disabled = true;
      erlang.disabled = true;
      fennel.disabled = true;
      fossil_branch.disabled = true;
      gcloud.disabled = true;
      gleam.disabled = true;
      golang.disabled = true;
      gradle.disabled = true;
      guix_shell.disabled = true;
      haskell.disabled = true;
      haxe.disabled = true;
      helm.disabled = true;
      java.disabled = true;
      julia.disabled = true;
      kotlin.disabled = true;
      kubernetes.disabled = true;
      lua.disabled = true;
      memory_usage.disabled = true;
      meson.disabled = true;
      nim.disabled = true;
      nix_shell.disabled = true;
      nodejs.disabled = true;
      ocaml.disabled = true;
      opa.disabled = true;
      openstack.disabled = true;
      package.disabled = true;
      perl.disabled = true;
      php.disabled = true;
      pijul_channel.disabled = true;
      pulumi.disabled = true;
      purescript.disabled = true;
      python.disabled = true;
      quarto.disabled = true;
      raku.disabled = true;
      red.disabled = true;
      rlang.disabled = true;
      ruby.disabled = true;
      rust.disabled = true;
      scala.disabled = true;
      shlvl.disabled = true;
      singularity.disabled = true;
      solidity.disabled = true;
      spack.disabled = true;
      swift.disabled = true;
      terraform.disabled = true;
      typst.disabled = true;
      vagrant.disabled = true;
      vcsh.disabled = true;
      vlang.disabled = true;
      zig.disabled = true;
    };
  };
}
