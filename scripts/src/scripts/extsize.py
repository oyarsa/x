"""Show space and number of used by files in `root_dir` (recursive) grouped by extension."""

import contextlib
from collections import defaultdict
from pathlib import Path
from typing import Annotated

import typer


def get_size_by_extension(root_dir: Path) -> tuple[dict[str, int], dict[str, int]]:
    """Find total size and count of files per extension in bytes.

    Args:
        root_dir: Directory to be recursively crawled to gather all files.

    Returns:
        Tuple of two mappings: extension to size in bytes, and extension to count of
        files.
    """
    # Dictionary to store total size for each extension
    ext_sizes: dict[str, int] = defaultdict(int)
    ext_counts: dict[str, int] = defaultdict(int)

    # Walk through all directories and files
    for path in root_dir.rglob("*"):
        if not path.is_file():
            continue

        with contextlib.suppress(OSError, FileNotFoundError):
            size = path.stat().st_size

            # Get extension (or "no_extension" if none)
            ext = path.suffix[1:] if path.suffix else "no_extension"  # Remove the dot

            # Add to the totals
            ext_sizes[ext] += size
            ext_counts[ext] += 1

    return ext_sizes, ext_counts


def human_readable_size(size: float) -> str:
    """Convert bytes to human-readable format."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024 or unit == "TB":
            return f"{size:.2f} {unit}"
        size /= 1024

    raise ValueError("unreachable")


app = typer.Typer(
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
    rich_markup_mode="rich",
    pretty_exceptions_show_locals=False,
)


@app.command(help=__doc__)
def main(
    root_dir: Annotated[
        Path, typer.Argument(help="Starting directory to find files.")
    ] = Path(),
) -> None:
    """Show sum of space and number of files per extension."""
    ext_sizes, ext_counts = get_size_by_extension(root_dir)

    # Sort extensions by size
    sorted_exts = sorted(ext_sizes.items(), key=lambda x: x[1], reverse=True)

    # Calculate the maximum extension length for proper padding
    max_ext_len = max(len(ext) for ext in ext_sizes) + 3
    ext_col_width = max(max_ext_len, len("Extension"))

    # Print the results
    print(f"{'Extension':<{ext_col_width}} {'Count':<10} {'Human Readable':<15}")
    print("-" * (ext_col_width + 26))

    for ext, size in sorted_exts:
        print(
            f"{ext:<{ext_col_width}} {ext_counts[ext]:<10} {human_readable_size(size):<15}"
        )

    total_size = sum(ext_sizes.values())
    total_count = sum(ext_counts.values())
    print("-" * (ext_col_width + 26))
    print(
        f"{'TOTAL':<{ext_col_width}} {total_count:<10} {human_readable_size(total_size):<15}"
    )


if __name__ == "__main__":
    app()
