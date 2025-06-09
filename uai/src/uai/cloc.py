"""Convert CLOC JSON output to formatted table with additional metrics."""

import json
import subprocess
import sys
from typing import Any, cast

from pydantic import BaseModel


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


class ClocData(BaseModel):
    """Complete CLOC data structure."""

    header: ClocHeader
    languages: list[LanguageStats]
    sum_stats: LanguageStats

    @classmethod
    def from_json_dict(cls, data: dict[str, Any]) -> "ClocData":
        """Create ClocData from raw JSON dictionary."""
        header = ClocHeader(**data["header"])

        languages: list[LanguageStats] = []
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

        # Sort languages by code lines (descending)
        languages.sort(key=lambda x: x.code, reverse=True)

        sum_data = cast(dict[str, Any], data["SUM"])
        sum_stats = LanguageStats(
            name="SUM",
            files=int(sum_data["nFiles"]),
            blank=int(sum_data["blank"]),
            comment=int(sum_data["comment"]),
            code=int(sum_data["code"]),
        )

        return cls(header=header, languages=languages, sum_stats=sum_stats)


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

    # Create separator line
    separator = f" {'-' * (name_width + 75)}"

    # Header row
    lines.append(separator)
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


def main() -> None:
    """Run cloc command and print formatted table to stdout."""
    # Run cloc command and capture output
    try:
        result = subprocess.run(
            ["cloc", "--vcs", "git", ".", "--json"],
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
    cloc_data = ClocData.from_json_dict(raw_data)

    # Format and print the table
    table = format_cloc_table(cloc_data)
    print(table)


if __name__ == "__main__":
    main()
