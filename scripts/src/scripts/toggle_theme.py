#!/usr/bin/env python3
"""Toggle between light and dark themes in various config files.

Currently supports the following config files:
- Neovim
- Kitty
- Delta
- Tmux
- Fzf/fd/eza/LS_COLORS-supporting programs
- Bat
- Fish
- Lazygit
"""

import argparse
import os
import subprocess
import sys
from enum import Enum
from pathlib import Path

import yaml

from scripts.util import HelpOnErrorArgumentParser

config_files = {
    # Neovim
    "~/.config/nvim/lua/config/plugins.lua": {
        "light": 'theme = "latte"',
        "dark": 'theme = "mocha"',
    },
    # Kitty
    "~/.config/kitty/kitty.conf": {
        "light": "Catppuccin-Latte",
        "dark": "Catppuccin-Mocha",
    },
    # Delta
    "~/.config/git/config": {
        "light": "catppuccin-mocha",
        "dark": "catppuccin-latte",
    },
    # Tmux
    "~/.config/tmux/tmux.conf": {
        "light": "catppuccin_flavour = 'latte'",
        "dark": "catppuccin_flavour = 'mocha'",
    },
    # Fzf/fd/eza/LS_COLORS-supporting programs
    "~/.config/fish/conf.d/colours.fish": {
        "light": "IS_COLOUR_THEME catppuccin-latte",
        "dark": "IS_COLOUR_THEME catppuccin-mocha",
    },
    # Bat
    "~/.config/bat/config": {
        "light": 'theme="Catppuccin Latte"',
        "dark": 'theme="Catppuccin Mocha"',
    },
}


def fish_theme(theme: str) -> None:
    """Set the fish theme through `fish_config` CLI."""
    try:
        subprocess.run(
            ["fish", "-c", f'yes | fish_config theme save "{theme}"'], check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"Warning: failed to change fish theme: {e.output}")


def lazygit_theme(theme: str) -> None:
    """Read theme from a file and updates the config file's `gui` key."""
    config_dir = Path("~/.config/lazygit").expanduser()

    config_path = config_dir / "config.yml"
    config = yaml.safe_load(config_path.read_text())
    theme = yaml.safe_load((config_dir / "themes" / f"{theme}.yml").read_text())

    config["gui"] = theme
    config_path.write_text(yaml.dump(config))


# Conifgurations that can't be done by simple string replacement
config_funcs = {
    fish_theme: {
        "light": "Catppuccin Latte",
        "dark": "Catppuccin Mocha",
    },
    lazygit_theme: {
        "light": "catppuccin-latte",
        "dark": "catppuccin-mocha",
    },
}


class Theme(Enum):
    CATPPUCCIN_LATTE = "catppuccin-latte"
    CATPPUCCIN_MOCHA = "catppuccin-mocha"


def replace_in_file(file_path: Path, old: str, new: str) -> int:
    file_path = file_path.expanduser()
    content = file_path.read_text()
    count = content.count(old)
    changed = content.replace(old, new)
    file_path.write_text(changed)
    return count


def main() -> None:
    parser = HelpOnErrorArgumentParser(__doc__)
    parser.add_argument(
        "--warn-multiple",
        action=argparse.BooleanOptionalAction,
        type=bool,
        default=True,
        help="Warn if more than one replacement is made in a file",
    )
    args = parser.parse_args()

    valid_themes = ", ".join(f"'{theme.value}'" for theme in Theme)
    theme_msg = f"Choose from: {valid_themes}"
    try:
        current_theme = Theme(os.environ["ILS_COLOUR_THEME"])
    except KeyError:
        print(f"ILS_COLOUR_THEME environment variable is not set. {theme_msg}")
        sys.exit(1)
    except ValueError:
        print(f"Invalid theme. {theme_msg}")
        sys.exit(1)

    match current_theme:
        case Theme.CATPPUCCIN_LATTE:
            current, new = "light", "dark"
        case Theme.CATPPUCCIN_MOCHA:
            current, new = "dark", "light"

    for file, values in config_files.items():
        count = replace_in_file(Path(file), values[current], values[new])
        if args.warn_multiple and count > 1:
            print(f"Warning: more than one replacement made in {file}.")

    for func, values in config_funcs.items():
        func(values[new])


if __name__ == "__main__":
    main()
