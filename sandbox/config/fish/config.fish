# Default fish configuration for sandbox

# Set terminal title to show current directory
function fish_title
    prompt_pwd
end

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

# Source command output if the command exists
function source_if_exists -a cmd
    if type -q $cmd
        eval $cmd $argv[2..] | source
    end
end

# ll using eza
function ll --wraps=ls --wraps=eza
    EZA_COLORS='da=30' eza --time-style=long-iso --long --header --icons --git --color-scale \
        $argv
end

# glow with pager
function glow --description 'alias glow glow --pager'
    command glow --pager $argv
end

# git-recent: show recent commits
function git-recent
    set -l count 5
    if test (count $argv) -gt 0
        set count $argv[1]
    end
    git log -$count --color=always --pretty=format:"%C(cyan)○  %C(magenta)%h%C(auto)%d %C(green)%an <%ae> %C(blue)%ad%C(reset)%n%C(blue)│  %C(reset)%s" --date=format:"%Y-%m-%d %H:%M:%S"
end

# Key bindings
function __list_current_token
    function ls
        EZA_COLORS='da=30' eza --time-style=long-iso --long --header --icons --git --color-scale \
            $argv
    end
    __fish_list_current_token
end

function __jj
    printf "\n"
    jj log -n5 --no-pager && echo && jj status $argv
    printf "\n\n"
    commandline -f repaint
end

function __gg
    printf "\n"
    git log --graph --oneline -n 5 && echo && git status --short
    printf "\n\n"
    commandline -f repaint
end

function fish_user_key_bindings
    fzf_key_bindings
    bind alt-l __list_current_token
    bind alt-j __jj
    bind alt-g __gg
end

if status is-interactive
    if type -q tmux
        if not set -q TMUX
            tmux new -As0
        end
    end

    source_if_exists starship init fish
    source_if_exists zoxide init fish --cmd k
    source_if_exists mise activate fish
    source_if_exists uv generate-shell-completion fish
    source_if_exists jj util completion fish
    source_if_exists just --completions fish

    # Source fzf keybindings
    if test -f ~/.fzf/shell/key-bindings.fish
        source ~/.fzf/shell/key-bindings.fish
    end

    set -gx EDITOR nvim
    set -gx NODE_OPTIONS "--max-old-space-size=3072"
    fish_add_path ~/.local/share/bob/nvim-bin
    fish_add_path ~/.local/bin
    fish_add_path ~/.npm-global/bin
    fish_add_path ~/.cargo/bin
    fish_add_path /usr/local/go/bin
    fish_add_path ~/go/bin
    fish_add_path ~/.fzf/bin

    abbr v nvim
    abbr r uv run
    abbr c claude
    abbr ... ../..
    abbr .... ../../..
    alias yolo 'claude --dangerously-skip-permissions'
end
