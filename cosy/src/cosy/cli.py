"""Utilities to analyse Python code."""

from importlib import metadata

import typer

from cosy import (
    code_size,
    count_items,
    find_base_models,
    find_default_args,
    find_imports,
    find_untyped_return,
    list_public_items,
    match_deps,
)

commands = [
    (find_base_models, "records"),
    (find_default_args, "args"),
    (find_imports, "imports"),
    (match_deps, "deps"),
    (code_size, "size"),
    (find_untyped_return, "untyped-return"),
    (list_public_items, "public"),
    (count_items, "counts"),
]


def version_callback(value: bool) -> None:
    if value:
        version = metadata.version("cosy")
        typer.echo(f"cosy version {version}")
        raise typer.Exit()


app = typer.Typer(
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
    rich_markup_mode="rich",
    pretty_exceptions_show_locals=False,
    no_args_is_help=True,
)


@app.callback(help=__doc__)
def callback(
    _: bool = typer.Option(
        None,
        "--version",
        "-V",
        help="Show version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    pass


for pkg, name in commands:
    app.command(help=pkg.__doc__, name=name)(pkg.main)


if __name__ == "__main__":
    app()
