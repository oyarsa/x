"""Random utility scripts."""

import importlib.metadata
import sys
from typing import Annotated

import typer

from uai import (
    blame,
    cloc,
    confusion_matrix,
    count_hf_tokens,
    estimate_tokens,
    extsize,
    getschema,
    json_freq,
    json_head,
    json_keys,
    json_rename,
    json_shuf,
    json_to_table,
    listdir,
    readtable,
    repomap,
    tablefmt,
    toggle_theme,
)

app = typer.Typer(
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
    rich_markup_mode="rich",
    pretty_exceptions_show_locals=False,
    no_args_is_help=True,
    help=__doc__,
)

cmds = [
    (blame, "blame"),
    (confusion_matrix, "confusion"),
    (count_hf_tokens, "ntok-hf"),
    (estimate_tokens, "ntok"),
    (extsize, "extsize"),
    (listdir, "ld"),
    (toggle_theme, "toggle_theme"),
    (readtable, "table2json"),
    (getschema, "jschema"),
    (json_freq, "jfreq"),
    (json_head, "jhead"),
    (json_keys, "jkeys"),
    (json_shuf, "jshuf"),
    (json_to_table, "json2table"),
    (json_rename, "jrename"),
    (repomap, "repomap"),
    (cloc, "cloc"),
    (tablefmt, "tablefmt"),
    # TODO: convert tg_notify
]

for mod, name in cmds:
    app.command(name=name, help=mod.__doc__)(mod.main)


def _version_callback(show: bool) -> None:
    if show:
        name = "uai"
        version = importlib.metadata.version(name)
        print(f"{name} {version}")
        sys.exit()


@app.callback()
def main(
    _: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            help="Show version and exit.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = False,
):
    pass


if __name__ == "__main__":
    app()
