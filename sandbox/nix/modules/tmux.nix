{ config, pkgs, lib, ... }:

{
  programs.tmux = {
    enable = true;
    shell = "${pkgs.fish}/bin/fish";
    terminal = "tmux-256color";
    prefix = "C-s";
    keyMode = "vi";
    escapeTime = 0;
    historyLimit = 999999999;
    baseIndex = 1;
    mouse = true;

    extraConfig = ''
      # Secondary prefix
      set-option -g prefix2 M-s
      bind-key C-s send-prefix

      # Status bar
      set -g status-bg black
      set -g status-fg white
      set-option -g status-right " %H:%M %Y-%m-%d"

      # New window in current path
      bind c new-window -c "#{pane_current_path}"

      # Vi copy mode bindings
      bind-key -T copy-mode-vi v send-keys -X begin-selection
      bind-key -T copy-mode-vi y send-keys -X copy-selection-and-cancel

      # Ensures that autoread works on nvim
      set-option -g focus-events on

      # Emacs key bindings for command mode
      set -g status-keys emacs

      # Renumber windows after closing one
      set-option -g renumber-windows on

      # Allow passthrough for special escape sequences
      set -g allow-passthrough all

      # Pane base index
      setw -g pane-base-index 1

      # Enable true color support for kitty
      set -as terminal-features ",xterm-kitty*:RGB"

      # Make pane switch non-repeatable
      bind-key Up    select-pane -U
      bind-key Down  select-pane -D
      bind-key Left  select-pane -L
      bind-key Right select-pane -R

      # Bind P and N (capitals) to moving the current window around
      bind-key N swap-window -t +1 \; next-window
      bind-key P swap-window -t -1 \; previous-window

      # Pane switching with C-hjkl (vim-aware - passes keys to vim if running)
      is_vim="ps -o state= -o comm= -t '#{pane_tty}' | grep -iqE '^[^TXZ ]+ +(\\S+\\/)?g?(view|n?vim?x?)(diff)?$'"
      bind-key -n C-h if-shell "$is_vim" "send-keys C-h" "select-pane -L"
      bind-key -n C-j if-shell "$is_vim" "send-keys C-j" "select-pane -D"
      bind-key -n C-k if-shell "$is_vim" "send-keys C-k" "select-pane -U"
      bind-key -n C-l if-shell "$is_vim" "send-keys C-l" "select-pane -R"

      # Same bindings for copy mode
      bind-key -T copy-mode-vi C-h select-pane -L
      bind-key -T copy-mode-vi C-j select-pane -D
      bind-key -T copy-mode-vi C-k select-pane -U
      bind-key -T copy-mode-vi C-l select-pane -R

      # Split panes with h and v (keeping current path)
      bind 'h' split-window -c "#{pane_current_path}"
      bind v split-window -h -c "#{pane_current_path}"
    '';
  };
}
