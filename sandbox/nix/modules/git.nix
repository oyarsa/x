{ config, pkgs, lib, userConfig, ... }:

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

  # Jujutsu (jj) configuration
  home.file.".jjconfig.toml".text = ''
    [ui]
    default-command = "log"
    pager = "delta"
    diff-editor = ":builtin"
    diff-formatter = ":git"

    [user]
    name = "${userConfig.fullName}"
    email = "${userConfig.email}"

    [template-aliases]
    commit_description_verbose = '''
    concat(
      description,
      "\n",
      "JJ: This commit contains the following changes:\n",
      indent("JJ:    ", diff.stat(72)),
      indent("JJ:    ", diff.summary()),
      "JJ: ignore-rest\n",
      diff.git(),
    )
    '''
    annotate_commit_summary_full = '''
    separate(" ",
      change_id.shortest(8),
      pad_end(8, truncate_end(8, author.email().local())),
      commit_timestamp(self).local().format('%Y-%m-%d '),
      pad_end(70, truncate_end(70, self.description().first_line())),
    )
    '''

    [templates]
    draft_commit_description = "commit_description_verbose"

    [git]
    colocate = true

    [aliases]
    tug = ["bookmark", "move", "--from", "heads(::@- & bookmarks())", "--to", "@-"]
  '';

  # GitHub CLI configuration
  programs.gh = {
    enable = true;
    settings = {
      git_protocol = "https";
      prompt = "enabled";
    };
  };
}
