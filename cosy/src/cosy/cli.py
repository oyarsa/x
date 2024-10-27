import typer

from cosy import find_base_models, find_default_args, find_imports, match_deps

commands = [
    (find_base_models, "records"),
    (find_default_args, "args"),
    (find_imports, "imports"),
    (match_deps, "deps"),
]

app = typer.Typer(
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
    rich_markup_mode="rich",
    pretty_exceptions_show_locals=False,
)
for pkg, name in commands:
    app.command(help=pkg.__doc__, name=name)(pkg.main)


if __name__ == "__main__":
    app()
