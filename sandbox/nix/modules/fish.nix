{ config, pkgs, lib, ... }:

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

    # Interactive shell initialization
    interactiveShellInit = ''
      # Start tmux if not already in a session
      if type -q tmux
          if not set -q TMUX
              tmux new -As0
          end
      end

      # Source completions from various tools
      if type -q uv
          uv generate-shell-completion fish | source
      end
      if type -q jj
          jj util completion fish | source
      end
      if type -q just
          just --completions fish | source
      end

      # FZF key bindings (from Nix package)
      if test -f ${pkgs.fzf}/share/fzf/key-bindings.fish
          source ${pkgs.fzf}/share/fzf/key-bindings.fish
      end
    '';

    # Shell initialization (always runs)
    shellInit = ''
      # Enable colors
      set -g fish_color_normal normal
      set -g fish_color_command green
      set -g fish_color_param cyan
      set -g fish_color_redirection normal
      set -g fish_color_comment red
      set -g fish_color_error red --bold
      set -g fish_color_escape cyan
      set -g fish_color_operator cyan
      set -g fish_color_quote yellow
      set -g fish_color_autosuggestion 555 yellow
      set -g fish_color_valid_path --underline
      set -g fish_color_cwd green
      set -g fish_color_cwd_root red

      # Environment variables
      set -gx EDITOR nvim
      set -gx NODE_OPTIONS "--max-old-space-size=3072"
      set -gx XDG_CONFIG_HOME "$HOME/.config"
      set -gx UV_LINK_MODE copy
      set -gx FZF_VIM_PATH "${pkgs.fzf}/share/vim-plugins/fzf"

      # fifc settings (if using fifc plugin)
      set -gx fifc_editor nvim
      set -gx fifc_keybinding \cx
    '';

    # Fish functions
    functions = {
      # Set terminal title
      fish_title = ''
        prompt_pwd
      '';

      # Source command output if the command exists
      source_if_exists = {
        argumentNames = [ "cmd" ];
        body = ''
          if type -q $cmd
              eval $cmd $argv[2..] | source
          end
        '';
      };

      # ll using eza
      ll = {
        wraps = "eza";
        description = "List files with eza";
        body = ''
          EZA_COLORS='da=30' eza --time-style=long-iso --long --header --icons --git --color-scale $argv
        '';
      };

      # glow with pager
      glow = {
        wraps = "glow";
        description = "Markdown renderer with pager";
        body = ''
          command glow --pager $argv
        '';
      };

      # git-recent: show recent commits
      git-recent = {
        description = "Show recent git commits";
        body = ''
          set -l count 5
          if test (count $argv) -gt 0
              set count $argv[1]
          end
          git log -$count --color=always --pretty=format:"%C(cyan)○  %C(magenta)%h%C(auto)%d %C(green)%an <%ae> %C(blue)%ad%C(reset)%n%C(blue)│  %C(reset)%s" --date=format:"%Y-%m-%d %H:%M:%S"
        '';
      };

      # rg with smart-case
      rg = {
        wraps = "rg";
        description = "ripgrep with smart-case";
        body = ''
          command rg --smart-case $argv
        '';
      };

      # yolo: run claude without permission prompts
      yolo = {
        wraps = "claude";
        description = "Run claude without permission prompts";
        body = ''
          claude --dangerously-skip-permissions $argv
        '';
      };

      # ,fx: fx wrapper for compressed files
      ",fx" = {
        description = "fx JSON viewer with compression support";
        body = ''
          if test (count $argv) -eq 1
              if not test -f "$argv[1]"
                  echo "File not found: $argv[1]"
                  return 1
              end

              if string match -q -- '*.gz' "$argv[1]"
                  gunzip -c "$argv[1]" | fx
              else if string match -q -- '*.zst' "$argv[1]"
                  zstd -dc "$argv[1]" | fx
              else
                  fx "$argv[1]"
              end
          else if test (count $argv) -eq 2
              if not test -f "$argv[2]"
                  echo "File not found: $argv[2]"
                  return 1
              end

              if string match -q -- '*.gz' "$argv[2]"
                  gunzip -c "$argv[2]" | fx $argv[1]
              else if string match -q -- '*.zst' "$argv[2]"
                  zstd -dc "$argv[2]" | fx $argv[1]
              else
                  fx $argv[1] <"$argv[2]"
              end
          else
              echo "Usage: ,fx [query] file"
              return 1
          end
        '';
      };

      # ,jq: jq wrapper for compressed files
      ",jq" = {
        description = "jq with compression support";
        body = ''
          if not test -f "$argv[2]"
              echo "File not found: $argv[2]"
              return 1
          end

          if string match -q -- '*.gz' "$argv[2]"
              gunzip -c "$argv[2]" | jq $argv[1]
          else if string match -q -- '*.zst' "$argv[2]"
              zstd -dc "$argv[2]" | jq $argv[1]
          else
              jq $argv[1] <"$argv[2]"
          end
        '';
      };

      # Key binding helper for listing current token
      __list_current_token = ''
        function ls
            EZA_COLORS='da=30' eza --time-style=long-iso --long --header --icons --git --color-scale $argv
        end
        __fish_list_current_token
      '';

      # Key binding helper for jj status
      __jj = ''
        printf "\n"
        jj log -n5 --no-pager && echo && jj status $argv
        printf "\n\n"
        commandline -f repaint
      '';

      # Key binding helper for git status
      __gg = ''
        printf "\n"
        git log --graph --oneline -n 5 && echo && git status --short
        printf "\n\n"
        commandline -f repaint
      '';

      # Custom key bindings
      fish_user_key_bindings = ''
        if type -q fzf_key_bindings
            fzf_key_bindings
        end
        bind alt-l __list_current_token
        bind alt-j __jj
        bind alt-g __gg
        bind tab complete
      '';

      # Jujutsu aliases
      jl1 = {
        wraps = "jj log";
        description = "jj log one-line format";
        body = "jj log -T builtin_log_oneline --no-graph -r '::@' $argv";
      };

      jen = {
        wraps = "jj next";
        description = "jj next --edit";
        body = "jj next --edit $argv";
      };

      jep = {
        wraps = "jj prev";
        description = "jj prev --edit";
        body = "jj prev --edit $argv";
      };

      jgm = {
        wraps = "jj bookmark";
        description = "Set bookmark to master and push";
        body = "jj bookmark set -r @- master && jj git push $argv";
      };

      js = {
        wraps = "jj split";
        description = "jj split";
        body = "jj split $argv";
      };

      jlf = {
        wraps = "jj log";
        description = "jj log with full descriptions";
        body = "jj log -r '::@' -T builtin_log_compact_full_description $argv";
      };

      jet = {
        wraps = "jj edit";
        description = "jj edit visible heads";
        body = "jj edit -r 'visible_heads()' $argv";
      };

      jci = {
        wraps = "jj commit";
        description = "jj commit -i";
        body = "jj commit -i $argv";
      };

      jco = {
        wraps = "jj commit";
        description = "jj commit";
        body = "jj commit $argv";
      };

      jlaf = {
        wraps = "jj log";
        description = "jj log -r all with full descriptions";
        body = "jj log -T builtin_log_compact_full_description -r 'all()' $argv";
      };

      jla = {
        wraps = "jj log";
        description = "jj log -r all";
        body = "jj log -r 'all()' $argv";
      };

      jl = {
        wraps = "jj log";
        description = "jj log -n10";
        body = "jj log -n10 $argv";
      };

      jdd = {
        wraps = "jj diff";
        description = "Interactive jj diff with fzf";
        body = ''
          jj diff --name-only | fzf \
              --multi \
              --preview 'jj diff --color=always {} | delta' \
              --preview-window=right:70% \
              --bind 'ctrl-d:preview-half-page-down,ctrl-u:preview-half-page-up' \
              --bind 'ctrl-s:execute-silent(jj squash {+})+reload(jj diff --name-only)'
        '';
      };

      jnm = {
        wraps = "jj new";
        description = "Create new change on trunk";
        body = "jj new 'trunk()'";
      };

      jlm = {
        wraps = "jj log";
        description = "jj log from master to @";
        body = "jj log -r 'master::@' $argv";
      };

      jll = {
        wraps = "jj log";
        description = "jj log -r ::@";
        body = "jj log -r '::@' $argv";
      };

      jpr = {
        wraps = "jj git fetch";
        description = "Fetch and create new change on trunk";
        body = "jj git fetch && jj new 'trunk()' && jj log $argv";
      };

      jgp = {
        wraps = "jj git push";
        description = "jj git push";
        body = "jj git push $argv";
      };

      jsq = {
        wraps = "jj squash";
        description = "jj squash";
        body = "jj squash $argv";
      };

      jna = {
        wraps = "jj new";
        description = "jj new -A";
        body = ''
          set -f args $argv
          test (count $args) -eq 0 && set args @
          jj new -A $args
        '';
      };

      jnb = {
        wraps = "jj new";
        description = "jj new -B";
        body = ''
          set -f args $argv
          test (count $args) -eq 0 && set args @
          jj new -B $args
        '';
      };

      jblamefull = {
        wraps = "jj file annotate";
        description = "jj file annotate with full commit summary";
        body = ''jj file annotate --config 'templates.annotate_commit_summary="annotate_commit_summary_full"' $argv'';
      };

      jgf = {
        wraps = "jj git fetch";
        description = "jj git fetch with status";
        body = ''
          jj git fetch $argv
          printf "\n"
          jj log -n5 --no-pager && echo && jj status $argv
        '';
      };

      jc = {
        wraps = "jj describe";
        description = "jj describe";
        body = "jj describe $argv";
      };

      jn = {
        wraps = "jj new";
        description = "jj new";
        body = "jj new $argv";
      };

      jdu = {
        wraps = "jj diff";
        description = "jj diff -r @-";
        body = "jj diff -r @- $argv";
      };

      jd = {
        wraps = "jj diff";
        description = "jj diff";
        body = "jj diff $argv";
      };

      je = {
        wraps = "jj edit";
        description = "jj edit";
        body = "jj edit $argv";
      };

      jbu = {
        wraps = "jj bookmark";
        description = "jj bookmark set -r @-";
        body = "jj bookmark set -r @- $argv";
      };

      jblame = {
        wraps = "jj file annotate";
        description = "jj file annotate";
        body = "jj file annotate $argv";
      };

      jsearch = {
        wraps = "jj log";
        description = "Search jj log by description";
        body = ''jj log -r "description(\"$argv\")" -T builtin_log_compact_full_description'';
      };

      jcu = {
        wraps = "jj describe";
        description = "jj describe -r @-";
        body = "jj describe -r @- $argv";
      };

      jtp = {
        wraps = "jj tug";
        description = "jj tug && jgp";
        body = "jj tug && jgp $argv";
      };

      jde = {
        wraps = "nvim";
        description = "Edit files changed in jj diff";
        body = "nvim (jj diff --summary | cut -d' ' -f2) $argv";
      };

      jup = {
        wraps = "jj rebase";
        description = "Rebase branch to target";
        body = ''
          switch (count $argv)
              case 0
                  jj rebase -b @ -A master
              case 1
                  jj rebase -b $argv[1] -A master
              case 2
                  jj rebase -b $argv[1] -A $argv[2]
              case '*'
                  echo "Usage: jup [branch] [target]"
                  return 1
          end
        '';
      };
    };

    # Fish plugins via fisher
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
}
