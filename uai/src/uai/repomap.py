"""Generate an interactive treemap for a code repository using Git for file discovery.

Shows individual files with specific text formats and colouring.
Uses internal logic for simplified line counting, except for Python, where we do
it properly.
"""

from __future__ import annotations

import fnmatch
import subprocess
import tokenize
import webbrowser
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import plotly.graph_objects as go
import typer

# --- Colour Configuration ---
DEFAULT_DIR_COLOUR = "rgb(211, 211, 211)"  # lightgrey as RGB for directories
DEFAULT_FILE_COLOUR = "rgb(128, 128, 128)"  # grey as RGB fallback for files
COLOUR_MAP = {
    ".py": "#3572A5",  # Blue
    ".rs": "#DEA584",  # Light Orange/Peach
    ".go": "#00ADD8",  # Bright Blue
    ".java": "#B07219",  # Brown
    ".js": "#F7DF1E",  # Yellow
    ".ts": "#3178C6",  # Blue
    ".jsx": "#61DAFB",  # Light Blue
    ".tsx": "#3178C6",  # Blue
    ".html": "#E34F26",  # Orange/Red
    ".css": "#1572B6",  # Blue
    ".scss": "#C6538C",  # Pink
    ".c": "#555555",  # Dark Gray
    ".cpp": "#F34B7D",  # Pink/Red
    ".h": "#555555",  # Dark Gray
    ".hpp": "#F34B7D",  # Pink/Red
    ".cs": "#178600",  # Green
    ".rb": "#CC342D",  # Red
    ".php": "#777BB4",  # Purple
    ".swift": "#F05138",  # Orange/Red
    ".kt": "#7F52FF",  # Purple
    ".scala": "#DC322F",  # Red
    ".pl": "#0298C3",  # Blue
    ".pm": "#0298C3",  # Blue
    ".r": "#276DC3",  # Blue
    ".sh": "#4EAA25",  # Green
    ".toml": "#1d6d70",  # Teal
    ".json": "#F1C40F",  # Gold/Yellow
    ".yml": "#CB171E",  # Red
    ".yaml": "#CB171E",  # Red
    ".xml": "#00A900",  # Green
    ".md": "#083FA1",  # Dark Blue
    ".sql": "#CC6600",  # Orange/Brown
    ".csv": "#27AE60",  # Green
    ".txt": "#CCCCCC",  # Light Gray
    ".lock": "#A0A0A0",  # Gray
    ".dockerfile": "#384D54",  # Dark Gray/Slate
}


# --- Git File Discovery ---
def get_git_files(repo_path: Path) -> list[Path]:
    """Use 'git ls-files -z' to get a list of tracked files.

    Args:
        repo_path: Path to the repository root.

    Returns:
        A list of Path objects relative to the repo root.
        Returns an empty list if not a git repo or on error.
    """
    if not (repo_path / ".git").is_dir():
        print(f"Error: '{repo_path}' does not appear to be a git repository.")
        return []

    try:
        # Use -z for null termination, safer for complex filenames
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=repo_path,
            check=True,
            capture_output=True,
            encoding="utf-8",  # Git output is usually UTF-8
        )
    except FileNotFoundError:
        print("Error: 'git' command not found. Is Git installed and in PATH?")
        return []
    except subprocess.CalledProcessError as e:
        print(f"Error running 'git ls-files' in '{repo_path}':")
        print(f"Stderr:\n{e.stderr}")
        return []
    except Exception as e:
        print(f"Unexpected error getting git files: {e}")
        return []
    else:
        # Split by null character and filter out empty strings
        return [Path(p) for p in result.stdout.split("\0") if p]


# --- Simplified Line Counting ---
def count_lines_simple(file_path: Path) -> int:
    """Count code lines using simple prefix rules.

    Empty lines and those whose first non-whitespace characters are '#', '//' or '--'
    are ignored.

    Args:
        file_path: The absolute path to the file to count.

    Returns:
        Count of code lines. Returns 0 on error.
    """
    count = 0
    comment_prefixes = ("#", "//", "--")  # Add more if needed

    try:
        for line in file_path.read_text().splitlines():
            stripped_line = line.strip()
            if stripped_line and not stripped_line.startswith(comment_prefixes):
                count += 1
    except OSError as e:
        print(f"Warning: Could not read file '{file_path}': {e}")
    except Exception as e:  # Catch potential decoding errors not covered by 'ignore'
        print(f"Warning: Error processing file '{file_path}': {e}")

    return count


# --- Filtering Helper ---
def should_ignore(
    relative_file_path: Path,
    ignore_ext: set[str],
    ignore_dir: set[str],
    ignore_path: list[str],
) -> bool:
    """Check if a file should be ignored based on provided criteria."""
    # Use relative path for pattern matching
    if ignore_ext and relative_file_path.suffix.lower() in ignore_ext:
        return True

    # Check parts of the relative path
    if ignore_dir and any(part in ignore_dir for part in relative_file_path.parts):
        return True

    # Match glob patterns against the relative path string (POSIX format)
    return bool(
        ignore_path
        and any(
            fnmatch.fnmatch(relative_file_path.as_posix(), pattern)
            for pattern in ignore_path
        )
    )


# --- Dataclass Definitions ---
@dataclass(frozen=True, kw_only=True)
class NodeData:
    """Data structure for a node in the treemap."""

    loc: int
    files: int
    label: str
    parent: str
    is_file: bool
    colour: str


@dataclass(frozen=True, kw_only=True)
class PlotlyData:
    """Data structure for Plotly treemap input."""

    ids: list[str]
    labels: list[str]
    parents: list[str]
    loc: list[int]
    files: list[int]
    is_file: list[bool]
    colours: list[str]


# --- Data Gathering ---
def get_loc_data(
    repo_path: Path, ignore_ext: set[str], ignore_dir: set[str], ignore_path: list[str]
) -> dict[str, int]:
    """Get tracked files via Git, filter them, count lines, and return structured data.

    Args:
        repo_path: Path to the repository root.
        ignore_ext: Set of extensions to ignore.
        ignore_dir: Set of directory names to ignore.
        ignore_path: List of glob patterns to ignore.

    Returns:
        Dictionary mapping relative file paths (str) to number of code lines.
    """
    print(f"Discovering tracked files in '{repo_path}'...")
    relative_files = get_git_files(repo_path)
    if not relative_files:
        print("No tracked files found or error occurred.")
        # Return empty dict instead of None to allow plotting an empty repo
        return {}

    print(f"Found {len(relative_files)} tracked files. Counting lines...")
    loc_data: dict[str, int] = {}
    processed_files_count = 0
    ignored_files_count = 0

    for rel_path in relative_files:
        # Apply filtering based on the relative path
        if should_ignore(rel_path, ignore_ext, ignore_dir, ignore_path):
            ignored_files_count += 1
            continue

        full_path = repo_path / rel_path
        if not full_path.is_file():
            print(f"Warning: Skipping non-file path from git ls-files: {rel_path}")
            continue

        # Count lines for non-ignored files
        if full_path.suffix.lower() == ".py":
            counts = count_lines_python(full_path)
        else:
            counts = count_lines_simple(full_path)

        # Store result using the relative path string as key
        # We only strictly need 'code' for the next step's LOC metric
        loc_data[rel_path.as_posix()] = counts
        processed_files_count += 1

    print(
        f"Counted lines in {processed_files_count} files, ignored "
        f"{ignored_files_count} files based on filters."
    )
    if processed_files_count == 0:
        print("Warning: No files were processed after filtering.")

    return loc_data


def count_lines_python(file_path: Path) -> int:
    """Count the number of code lines in a Python file.

    Excludes blank lines, comments, and docstrings.

    Args:
        file_path: Path to the Python source file.

    Returns:
        Number of code lines.
    """
    try:
        # Read the file content
        with file_path.open("rb") as file:
            # Get all tokens first to help with docstring identification
            tokens = list(tokenize.tokenize(file.readline))

        # Identify docstrings (as opposed to regular multiline strings)
        docstring_lines = find_docstring_lines(tokens)
        # Process all tokens again to identify code lines
        return len(find_code_lines(tokens, docstring_lines))

    except Exception as e:
        print(f"Error processing file {file_path}: {e}")
        return 0


def find_docstring_lines(tokens: list[tokenize.TokenInfo]) -> set[int]:
    """Find lines inside docstrings."""
    docstring_lines: set[int] = set()

    for i, token in enumerate(tokens):
        # Check for STRING tokens that might be docstrings
        if token.type != tokenize.STRING or not token.string.startswith(('"""', "'''")):
            continue

        is_docstring = False

        # Module docstring: at the beginning of the file
        if i <= 2:  # Could be preceded by ENCODING token
            is_docstring = True
        else:
            # Check if preceded by function/class def (followed by colon)
            prev_tokens = [tokens[j] for j in range(max(0, i - 5), i)]
            for prev_token in reversed(prev_tokens):
                if prev_token.type == tokenize.OP and prev_token.string == ":":
                    is_docstring = True
                    break

        if is_docstring:
            # Mark all lines in the docstring
            docstring_lines.update(range(token.start[0], token.end[0] + 1))

    return docstring_lines


def find_code_lines(
    tokens: list[tokenize.TokenInfo], docstring_lines: set[int]
) -> set[int]:
    """Count lines of code, excluding those that appear in docstrings."""
    return {
        token.start[0]
        for token in tokens
        if (
            token.type
            not in (
                tokenize.COMMENT,
                tokenize.NL,
                tokenize.NEWLINE,
                tokenize.ENDMARKER,
                tokenize.STRING,  # Handle strings separately
            )
            and token.start[0] not in docstring_lines
        )
        or (token.type == tokenize.STRING and token.start[0] not in docstring_lines)
    }


# --- Data Processing ---
def build_plotly_data_custom(
    loc_data: dict[str, int], repo_root_name: str
) -> PlotlyData | None:
    """Transform file line count data into hierarchical lists for Plotly treemaps.

    Includes files as leaves, calculates aggregate stats for directories,
    and assigns colours based on node type / file extension.

    Args:
        loc_data: Dictionary mapping relative paths to count of code lines.
        repo_root_name: Label/ID for the root node.

    Returns:
        Dictionary containing lists for Plotly ('ids', 'labels', etc.), or None on
        failure.
    """
    root_id = "."
    path_data: dict[str, NodeData] = {
        root_id: NodeData(
            loc=0,
            files=0,
            label=repo_root_name,
            parent="",
            is_file=False,
            colour=DEFAULT_DIR_COLOUR,
        )
    }
    if not loc_data:  # Handle case where get_loc_data returned empty
        print("Warning: No line count data provided to build hierarchy.")
        # Return structure with just the root
        return PlotlyData(
            ids=[root_id],
            labels=[path_data[root_id].label],
            parents=[path_data[root_id].parent],
            loc=[path_data[root_id].loc],
            files=[path_data[root_id].files],
            is_file=[path_data[root_id].is_file],
            colours=[path_data[root_id].colour],
        )

    file_node_file_count = 1

    for file_path_str, loc in loc_data.items():
        # file_path_str is already relative POSIX path
        file_path = Path(file_path_str)
        parts = file_path.parts
        if not parts:
            continue

        current_parent_id = root_id
        current_path_parts: list[str] = []

        # Ensure directory nodes exist
        for part in parts[:-1]:
            current_path_parts.append(part)
            dir_id = "/".join(current_path_parts)
            if dir_id not in path_data:
                path_data[dir_id] = NodeData(
                    loc=0,
                    files=0,
                    label=part,
                    parent=current_parent_id,
                    is_file=False,
                    colour=DEFAULT_DIR_COLOUR,
                )
            current_parent_id = dir_id

        # Create file node
        file_node_id = file_path.as_posix()
        file_label = parts[-1]
        file_ext = file_path.suffix.lower()
        file_colour = COLOUR_MAP.get(file_ext, DEFAULT_FILE_COLOUR)

        if file_node_id in path_data:
            print(f"Warning: Duplicate node ID detected: {file_node_id}. Skipping.")
            continue

        path_data[file_node_id] = NodeData(
            loc=loc,
            files=file_node_file_count,
            label=file_label,
            parent=current_parent_id,
            is_file=True,
            colour=file_colour,
        )

        # Propagate metrics up
        ancestor_id: str | None = current_parent_id
        while ancestor_id is not None:
            if ancestor_id in path_data:
                # Create a new NodeData with updated values since dataclass is frozen
                ancestor_data = path_data[ancestor_id]
                path_data[ancestor_id] = NodeData(
                    loc=ancestor_data.loc + loc,
                    files=ancestor_data.files
                    + (0 if ancestor_data.is_file else file_node_file_count),
                    label=ancestor_data.label,
                    parent=ancestor_data.parent,
                    is_file=ancestor_data.is_file,
                    colour=ancestor_data.colour,
                )
                parent_of_ancestor = ancestor_data.parent
                ancestor_id = parent_of_ancestor or None
            else:
                print(f"Warn: Ancestor '{ancestor_id}' missing for {file_node_id}.")
                break

    if not path_data:
        return None

    # Extract lists for Plotly
    return PlotlyData(
        ids=list(path_data.keys()),
        labels=[d.label for d in path_data.values()],
        parents=[d.parent for d in path_data.values()],
        loc=[d.loc for d in path_data.values()],
        files=[d.files for d in path_data.values()],
        is_file=[d.is_file for d in path_data.values()],
        colours=[d.colour for d in path_data.values()],
    )


# --- Plotly Visualisation ---
def create_treemap(data: PlotlyData, metric: Metric, title: str) -> go.Figure | None:
    """Generate interactive Plotly treemap with specific text for files/directories.

    Uses file-extension based colouring for visual distinction.

    Args:
        plotly_data: Dictionary containing hierarchical data for the treemap.
        metric: Metric to use for sizing nodes ('loc' or 'files').
        title: Title to display on the treemap.

    Returns:
        Plotly figure object or None if generation fails.
    """
    # Check if plotly_data is valid
    if not data.ids:
        print("Error: Cannot generate treemap with empty 'ids'.")
        return None

    customdata = list(zip(data.loc, data.files, data.ids))  # For hover

    if metric is Metric.LOC:
        values = data.loc
        value_label = "Lines of Code"
    elif metric is Metric.FILES:
        values = data.files
        value_label = "Number of Files"

    hovertemplate = "<b>%{label}</b><br>Path: %{customdata[2]}<br>LOC (Code): %{customdata[0]:,d}<br>Files: %{customdata[1]:,d}<extra></extra>"
    texttemplate_list: list[str] = []
    for label, loc in zip(data.labels, data.loc):
        safe_label = str(label).replace("<", "<").replace(">", ">")
        texttemplate_list.append(f"<b>{safe_label}</b><br>{int(loc):,d} LoC")

    non_zero_values = [v for v in values if v > 0]
    if not non_zero_values:
        print(f"Warn: All values for metric '{metric}' are zero.")

    fig = go.Figure(
        go.Treemap(  # type: ignore[attr-defined]
            ids=data.ids,
            labels=data.labels,
            parents=data.parents,
            values=values,
            customdata=customdata,
            hovertemplate=hovertemplate,
            texttemplate=texttemplate_list,
            textfont={"size": 14},
            textinfo="none",
            marker_colors=data.colours,
            pathbar={"visible": True},
            branchvalues="total",
            marker={"cornerradius": 3},
        )
    )
    fig.update_layout(
        title=f"{title} by {value_label}", margin={"t": 50, "l": 10, "r": 10, "b": 10}
    )
    fig.update_traces(textposition="middle center", insidetextfont={"size": 12})
    return fig


class Metric(StrEnum):
    """What metric to use for node size."""

    LOC = "loc"
    FILES = "files"


def main(
    repo_path: Annotated[Path, typer.Argument(help="Path to repo root.")] = Path(),
    metric: Annotated[
        Metric, typer.Option("--metric", "-m", help="Metric for area size.")
    ] = Metric.LOC,
    output: Annotated[
        str, typer.Option("--output", "-o", help="Output HTML file.")
    ] = "repomap.html",
    no_browser: Annotated[
        bool, typer.Option("--no-browser", help="Don't open browser.")
    ] = False,
    ignore_ext: Annotated[
        str | None, typer.Option("--ignore-ext", "-E", help="Extensions to ignore.")
    ] = None,
    ignore_dir: Annotated[
        str | None, typer.Option("--ignore-dir", "-D", help="Dir names to ignore.")
    ] = None,
    ignore_path: Annotated[
        str | None,
        typer.Option("--ignore-path", "-P", help="Glob path patterns to ignore."),
    ] = None,
) -> None:
    """Parse args, get LOC data, build structure, create plot, save/show."""
    # Prepare Ignore Sets/Lists
    ignore_ext_set: set[str] = set()
    if ignore_ext:
        ignore_ext_set = {
            ext.lower() if ext.startswith(".") else f".{ext.lstrip('.').lower()}"
            for ext in ignore_ext.split(",")
        }
        print(f"Ignoring extensions: {sorted(ignore_ext_set)}")

    ignore_dir_set: set[str] = set()
    if ignore_dir:
        ignore_dir_set = set(ignore_dir.split(","))
        print(f"Ignoring directories: {sorted(ignore_dir_set)}")

    ignore_path_list: list[str] = []
    if ignore_path:
        ignore_path_list = ignore_path.split(",")
        print(f"Ignoring paths: {ignore_path_list}")

    # --- Workflow Steps ---
    # 1. Get File List and Line Counts
    loc_data = get_loc_data(
        repo_path,
        ignore_ext=ignore_ext_set,
        ignore_dir=ignore_dir_set,
        ignore_path=ignore_path_list,
    )
    if not loc_data:
        typer.echo("Error: Failed to get line count data.")
        raise typer.Exit(code=1)

    repo_root_name = repo_path.resolve().name

    # 2. Process data into Plotly structure
    print("Building hierarchical data structure...")
    plotly_input_data = build_plotly_data_custom(loc_data, repo_root_name)
    if plotly_input_data is None:
        typer.echo("Exiting: Data processing failed.")
        raise typer.Exit(code=1)

    # 3. Create Plotly Figure
    print("Generating treemap visualization...")
    chart_title = f'"{repo_root_name}" Repository Structure'
    fig = create_treemap(plotly_input_data, metric=metric, title=chart_title)
    if fig is None:
        typer.echo("Exiting: Treemap generation failed.")
        raise typer.Exit(code=1)

    # 4. Save HTML and Optionally Show
    output_path = Path(output).resolve()
    print(f"Saving treemap to: {output_path}")
    try:
        fig.write_html(output_path, default_height="95vh", default_width="98vw")
    except Exception as e:
        typer.echo(f"Error saving HTML: {e}")
        raise typer.Exit(code=1) from e

    if not no_browser:
        try:
            webbrowser.open(output_path.as_uri())
            print("Opening treemap...")
        except Exception as e:
            print(f"Warn: Cannot open browser: {e}\nOpen manually: {output_path}")
