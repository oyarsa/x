import argparse
import sys
from collections.abc import Sequence
from typing import Any, NoReturn, override


class ArgumentDefaultsRawDescriptionFormatter(
    argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter
):
    """`formater_class` that shows the raw description text and adds default to help.

    The raw description text is useful when printing pre-formatted text (e.g. bullet
    lists, hard-wrapped text), such as when using a docstring for the `description`.

    The defaults are only added to options that define a `help` text. It's added as
    `(default: x)` at the end.
    """

    pass


class HelpOnErrorArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that prints the full help text on error."""

    @override
    def error(self, message: str) -> NoReturn:
        self.print_help(sys.stderr)
        self.exit(2, f"\nError: {message}\n")

    def __init__(
        self,
        description: str | None = None,
        prog: str | None = None,
        usage: str | None = None,
        epilog: str | None = None,
        parents: Sequence[argparse.ArgumentParser] = (),
        formatter_class: type[
            argparse.HelpFormatter
        ] = ArgumentDefaultsRawDescriptionFormatter,
        prefix_chars: str = "-",
        fromfile_prefix_chars: str | None = None,
        argument_default: Any = None,
        conflict_handler: str = "error",
        add_help: bool = True,
        allow_abbrev: bool = False,
        exit_on_error: bool = True,
    ) -> None:
        """Override `ArgumentParser.__init__` to make `description` the first parameter.

        Sets default `formatter_class` to be `ArgumentDefaultsRawDescriptionFormatter`
        since we're using the full module docstring as usage text, and includes the
        default value for all flags with defined help text. Also sets `allow_abbrev` to
        `False`, so that only real flags are accepted.

        The goal is to allow the most common case (use the module docstring as the
        description) to be just:

        Example:
            >>> parser = HelpOnErrorArgumentParser(__doc__)

        If the docstring contains a line with `---`, the text after that is not included
        in the help text.
        """
        if description:
            description = description.split("\n---", maxsplit=1)[0]
        super().__init__(
            prog=prog,
            usage=usage,
            description=description,
            epilog=epilog,
            parents=parents,
            formatter_class=formatter_class,
            prefix_chars=prefix_chars,
            fromfile_prefix_chars=fromfile_prefix_chars,
            argument_default=argument_default,
            conflict_handler=conflict_handler,
            add_help=add_help,
            allow_abbrev=allow_abbrev,
            exit_on_error=exit_on_error,
        )
