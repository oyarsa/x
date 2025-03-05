from datetime import datetime
from pathlib import Path

from scripts.util import HelpOnErrorArgumentParser


def modified_time(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime)


def get_total_size(path: Path) -> int:
    return sum(file.stat().st_size for file in path.rglob("*") if file.exists())


def get_latest_modified_time(path: Path) -> datetime:
    return max(
        (modified_time(file) for file in path.rglob("*") if file.exists()),
        default=modified_time(path),
    )


def is_code_file(path: Path) -> bool:
    extension = path.suffix.lower()
    if extension in {".py", ".sh", ".bash", ".fish"}:
        return True

    try:
        first_line = path.read_text().splitlines()[0].strip()
        if first_line.startswith("#!"):  # First line is a shebang
            shells = ["python", "bash", "fish", "/bin/sh", "env"]
            return any(shell in first_line for shell in shells)
    except (UnicodeDecodeError, IndexError):
        return False

    return False


COLOURS = {
    "blue": "\033[94m",
    "dark_blue": "\033[36m",
    "green": "\033[92m",
    "magenta": "\033[95m",
    "white": "\033[97m",
    "reset": "\033[0m",
}


def coloured(text: object, colour: str) -> str:
    return f"{colour}{text}{COLOURS['reset']}"


def underlined(text: object) -> str:
    return f"\033[4m{text}{COLOURS['reset']}"


def path_color(path: Path) -> str:
    if path.is_dir():
        return COLOURS["blue"]
    if is_code_file(path):
        return COLOURS["green"]
    if path.suffix.lower() == ".json":
        return COLOURS["magenta"]
    return COLOURS["white"]


def human_size(num: float, suffix: str = "B") -> str:
    for unit in ("", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"):
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"


def pretty_print_entries(paths: list[Path], reverse: bool = False) -> str:
    entries = sorted(
        (
            (
                get_latest_modified_time(subpath),
                human_size(get_total_size(subpath)),
                subpath,
            )
            for path in paths
            for subpath in path.glob("*")
            if subpath.is_file() or subpath.is_dir()
        ),
        reverse=reverse,
    )

    date_fmt = "%a %Y-%m-%d %H:%M:%S"
    fmt_entries = [
        (
            time.strftime(date_fmt),
            coloured(size, COLOURS["dark_blue"]),
            coloured(path, path_color(path)),
        )
        for time, size, path in entries
    ]
    date_padding = max(len(time) for time, _, _ in fmt_entries) + 1
    size_padding = max(len(size) for _, size, _ in fmt_entries) + 1

    # The padding is based on the string + ANSI codes, so they're different between
    # header and entries.
    date_header = underlined("Datetime")
    size_header = underlined("Size")
    path_header = underlined("Path")
    header_date_padding = (
        max(
            len(date_header),
            *(len(underlined(time.strftime(date_fmt))) for time, _, _ in entries),
        )
        + 1
    )
    header_size_padding = (
        max(len(size_header), *(len(underlined(size)) for _, size, _ in entries)) + 1
    )
    header_path_padding = (
        max(len(path_header), *(len(str(path)) for _, _, path in entries)) + 1
    )

    return (
        f"{date_header:{header_date_padding}}  {size_header:{header_size_padding}}"
        f"  {path_header:{header_path_padding}}\n"
        + "\n".join(
            f"{time:{date_padding}}  {size:{size_padding}}  {path}"
            for time, size, path in fmt_entries
        )
    )


def main() -> None:
    parser = HelpOnErrorArgumentParser(__doc__)
    parser.add_argument(
        "paths",
        type=Path,
        nargs="*",
        default=[Path(".")],
        help="Paths to pretty print (default: current directory)",
    )
    parser.add_argument(
        "-r", "--reverse", action="store_true", help="Reverse the order of the entries"
    )
    args = parser.parse_args()

    output = pretty_print_entries(args.paths, args.reverse)
    print(output)


if __name__ == "__main__":
    main()
