"""Convert CLOC JSON output to formatted table with additional metrics."""

import json
import subprocess
import sys
from enum import StrEnum
from typing import Annotated, Any, cast

import typer
from pydantic import BaseModel


class SortColumn(StrEnum):
    """Valid column names for sorting."""

    FILES = "files"
    BLANK = "blank"
    COMMENT = "comment"
    CODE = "code"
    CODE_COMMENT = "code+comment"
    COMMENT_PERCENT = "comment%"
    TOTAL = "total"


class ClocHeader(BaseModel):
    """CLOC header information."""

    cloc_url: str
    cloc_version: str
    elapsed_seconds: float
    files_per_second: float
    lines_per_second: float


class LanguageStats(BaseModel):
    """Statistics for a single language."""

    name: str
    files: int
    blank: int
    comment: int
    code: int

    @property
    def code_comment(self) -> int:
        """Total lines of code and comments."""
        return self.code + self.comment

    @property
    def comment_percentage(self) -> float:
        """Percentage of comments in code+comment lines."""
        return (
            (self.comment / self.code_comment * 100) if self.code_comment > 0 else 0.0
        )

    @property
    def total(self) -> int:
        """Total lines including blank lines."""
        return self.blank + self.comment + self.code


class FileStats(BaseModel):
    """Statistics for a single file."""

    path: str
    language: str
    blank: int
    comment: int
    code: int

    @property
    def code_comment(self) -> int:
        """Total lines of code and comments."""
        return self.code + self.comment

    @property
    def comment_percentage(self) -> float:
        """Percentage of comments in code+comment lines."""
        return (
            (self.comment / self.code_comment * 100) if self.code_comment > 0 else 0.0
        )

    @property
    def total(self) -> int:
        """Total lines including blank lines."""
        return self.blank + self.comment + self.code


class ClocData(BaseModel):
    """Complete CLOC data structure."""

    header: ClocHeader
    languages: list[LanguageStats]
    sum_stats: LanguageStats
    files: list[FileStats] | None = None

    @classmethod
    def from_json_dict(
        cls,
        data: dict[str, Any],
        include_files: bool = False,
        sort_by: SortColumn = SortColumn.CODE,
    ) -> "ClocData":
        """Create ClocData from raw JSON dictionary."""
        header = ClocHeader(**data["header"])

        languages: list[LanguageStats] = []
        if not include_files:
            # Only parse language stats when not using --by-file
            for key, value in data.items():
                if key not in ("header", "SUM") and isinstance(value, dict):
                    lang_data = cast(dict[str, Any], value)
                    languages.append(
                        LanguageStats(
                            name=key,
                            files=int(lang_data["nFiles"]),
                            blank=int(lang_data["blank"]),
                            comment=int(lang_data["comment"]),
                            code=int(lang_data["code"]),
                        )
                    )

            # Sort languages by specified column (descending)
            match sort_by:
                case SortColumn.FILES:
                    languages.sort(key=lambda x: x.files, reverse=True)
                case SortColumn.BLANK:
                    languages.sort(key=lambda x: x.blank, reverse=True)
                case SortColumn.COMMENT:
                    languages.sort(key=lambda x: x.comment, reverse=True)
                case SortColumn.CODE_COMMENT:
                    languages.sort(key=lambda x: x.code_comment, reverse=True)
                case SortColumn.COMMENT_PERCENT:
                    languages.sort(key=lambda x: x.comment_percentage, reverse=True)
                case SortColumn.TOTAL:
                    languages.sort(key=lambda x: x.total, reverse=True)
                case SortColumn.CODE:
                    languages.sort(key=lambda x: x.code, reverse=True)

        files: list[FileStats] | None = None
        if include_files:
            files = []
            # When using --by-file, files are at the root level
            for key, value in data.items():
                if key not in ("header", "SUM") and isinstance(value, dict):
                    file_dict = cast(dict[str, Any], value)
                    # When using --by-file, the key is the file path
                    if "language" in file_dict:
                        files.append(
                            FileStats(
                                path=key,
                                language=file_dict["language"],
                                blank=int(file_dict.get("blank", 0)),
                                comment=int(file_dict.get("comment", 0)),
                                code=int(file_dict.get("code", 0)),
                            )
                        )
            # Sort files by specified column (descending)
            if files:
                match sort_by:
                    case SortColumn.BLANK:
                        files.sort(key=lambda x: x.blank, reverse=True)
                    case SortColumn.COMMENT:
                        files.sort(key=lambda x: x.comment, reverse=True)
                    case SortColumn.CODE_COMMENT:
                        files.sort(key=lambda x: x.code_comment, reverse=True)
                    case SortColumn.COMMENT_PERCENT:
                        files.sort(key=lambda x: x.comment_percentage, reverse=True)
                    case SortColumn.TOTAL:
                        files.sort(key=lambda x: x.total, reverse=True)
                    case SortColumn.FILES | SortColumn.CODE:
                        # FILES column doesn't apply to individual files, fallback to code
                        files.sort(key=lambda x: x.code, reverse=True)

        # Calculate sum_stats
        if include_files and files:
            # When using --by-file, calculate sum from files
            sum_stats = LanguageStats(
                name="SUM",
                files=len(files),
                blank=sum(f.blank for f in files),
                comment=sum(f.comment for f in files),
                code=sum(f.code for f in files),
            )
        else:
            # When not using --by-file, get sum from JSON
            sum_data = cast(dict[str, Any], data.get("SUM", {}))
            if sum_data:
                sum_stats = LanguageStats(
                    name="SUM",
                    files=int(sum_data["nFiles"]),
                    blank=int(sum_data["blank"]),
                    comment=int(sum_data["comment"]),
                    code=int(sum_data["code"]),
                )
            else:
                # Fallback if no SUM in data
                sum_stats = LanguageStats(
                    name="SUM",
                    files=sum(lang.files for lang in languages),
                    blank=sum(lang.blank for lang in languages),
                    comment=sum(lang.comment for lang in languages),
                    code=sum(lang.code for lang in languages),
                )

        return cls(header=header, languages=languages, sum_stats=sum_stats, files=files)


def format_cloc_table(cloc_data: ClocData) -> str:
    """Format CLOC JSON data into a table with code+comment and comment percentage columns."""
    # Extract header information
    header = cloc_data.header

    # Build the output
    lines: list[str] = []
    lines.append(
        f"{header.cloc_url} v {header.cloc_version} T={header.elapsed_seconds:.2f} s "
        f"({header.files_per_second:.1f} files/s, {header.lines_per_second:.1f} lines/s)"
    )

    # Combine languages and sum for table display
    all_entries = [*cloc_data.languages, cloc_data.sum_stats]

    # Calculate column widths
    name_width = max(len(entry.name) for entry in all_entries)
    name_width = max(name_width, len("Language"))

    # Header row
    header_row = (
        f" {'Language':<{name_width}} "
        f"{'files':>8} "
        f"{'blank':>8} "
        f"{'comment':>8} "
        f"{'code':>8} "
        f"{'code+comment':>13} "
        f"{'comment %':>10} "
        f"{'Total':>8}"
    )

    # Create separator line based on actual header length
    separator = " " + "-" * (len(header_row) - 1)

    lines.append(separator)
    lines.append(header_row)
    lines.append(separator)

    # Data rows
    for entry in all_entries:
        # Add separator before SUM row
        if entry.name == "SUM":
            lines.append(separator)

        row = (
            f" {entry.name:<{name_width}} "
            f"{entry.files:>8} "
            f"{entry.blank:>8} "
            f"{entry.comment:>8} "
            f"{entry.code:>8} "
            f"{entry.code_comment:>13} "
            f"{entry.comment_percentage:>9.1f}% "
            f"{entry.total:>8}"
        )
        lines.append(row)

    lines.append(separator)

    return "\n".join(lines)


def format_files_table(files: list[FileStats], sum_stats: LanguageStats) -> str:
    """Format file statistics into a table with SUM row."""
    lines: list[str] = []

    # Calculate column widths
    path_width = max(len(file.path) for file in files)
    path_width = max(path_width, len("File"), len("SUM"))

    # Header row
    header_row = (
        f" {'File':<{path_width}} "
        f"{'blank':>8} "
        f"{'comment':>8} "
        f"{'code':>8} "
        f"{'code+comment':>13} "
        f"{'comment %':>10} "
        f"{'Total':>8}"
    )

    # Create separator line based on actual header length
    separator = " " + "-" * (len(header_row) - 1)

    lines.append(separator)
    lines.append(header_row)
    lines.append(separator)

    # Data rows
    for file in files:
        row = (
            f" {file.path:<{path_width}} "
            f"{file.blank:>8} "
            f"{file.comment:>8} "
            f"{file.code:>8} "
            f"{file.code_comment:>13} "
            f"{file.comment_percentage:>9.1f}% "
            f"{file.total:>8}"
        )
        lines.append(row)

    # Add SUM row
    lines.append(separator)
    row = (
        f" {'SUM':<{path_width}} "
        f"{sum_stats.blank:>8} "
        f"{sum_stats.comment:>8} "
        f"{sum_stats.code:>8} "
        f"{sum_stats.code_comment:>13} "
        f"{sum_stats.comment_percentage:>9.1f}% "
        f"{sum_stats.total:>8}"
    )
    lines.append(row)
    lines.append(separator)

    return "\n".join(lines)


def main(
    files: Annotated[
        bool, typer.Option("--files", "-f", help="Show lines per file")
    ] = False,
    sort: Annotated[
        SortColumn,
        typer.Option("--sort", "-s", help="Sort by column"),
    ] = SortColumn.CODE,
    cloc_args: Annotated[
        list[str] | None,
        typer.Argument(help="Additional arguments to pass to cloc"),
    ] = None,
) -> None:
    """Run cloc command and print formatted table to stdout."""
    # Build cloc command
    cloc_cmd = ["cloc", "--vcs", "git", "--json"]
    if files:
        cloc_cmd.append("--by-file")
    
    # Add any additional cloc arguments
    if cloc_args:
        cloc_cmd.extend(cloc_args)
    else:
        # Default behavior if no args provided
        cloc_cmd.append(".")

    # Run cloc command and capture output
    try:
        result = subprocess.run(
            cloc_cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        json_input = result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error running cloc: {e}", file=sys.stderr)
        print(f"stderr: {e.stderr}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("Error: cloc command not found. Please install cloc.", file=sys.stderr)
        sys.exit(1)

    raw_data = json.loads(json_input)

    # Parse into Pydantic models
    cloc_data = ClocData.from_json_dict(raw_data, include_files=files, sort_by=sort)

    # Format and print the table
    if files and cloc_data.files:
        table = format_files_table(cloc_data.files, cloc_data.sum_stats)
    else:
        table = format_cloc_table(cloc_data)
    print(table)


if __name__ == "__main__":
    main()
