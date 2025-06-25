import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterator


def is_git_repo(path: Path) -> bool:
    """Check if the given path is a git repository."""
    try:
        subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def get_last_commit_author(path: Path) -> str | None:
    """Get the author of the last commit in the repository."""
    try:
        return subprocess.run(
            ["git", "log", "-1", "--format=%an"],
            cwd=path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True,
        ).stdout.strip()
    except subprocess.CalledProcessError:
        return None


def find_repos_by_last_author(start_path: Path, author: str) -> Iterator[Path]:
    """Find all git repositories where the last commit was made by the specified author."""
    for dir in start_path.iterdir():
        if not dir.is_dir():
            continue
        if ".git" in str(dir):
            continue

        if is_git_repo(dir):
            last_author = get_last_commit_author(dir)
            if last_author == author:
                yield dir


def get_cloc_sum_total(path: Path) -> int | None:
    """Run uai cloc -C and extract the last column value from SUM row."""
    try:
        result = subprocess.run(
            ["uai", "cloc", "-C", str(path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True,
        )

        # Parse the output to find the SUM row
        for line in result.stdout.splitlines():
            if line.strip().startswith("SUM"):
                # Split by whitespace and get the last column
                if parts := line.split():
                    return int(parts[-1])
        return None
    except (subprocess.CalledProcessError, ValueError):
        return None


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <author_name>")
        sys.exit(1)

    author = sys.argv[1]
    start_dir = Path(".")

    print(f"Finding git repositories with last commit by '{author}'...")

    repos = find_repos_by_last_author(start_dir, author)

    with ThreadPoolExecutor() as executor:
        path_from_future = {
            executor.submit(get_cloc_sum_total, repo): repo for repo in repos
        }

        results = [
            (path_from_future[f].name, total)
            for f in as_completed(path_from_future)
            if (total := f.result()) is not None
        ]

    # Sort by repo name and print with padding
    results.sort(key=lambda x: x[1], reverse=True)
    max_name_len = max(len(name) for name, _ in results)
    for name, total in results:
        print(f"{name:{max_name_len}}  {total}")


if __name__ == "__main__":
    main()
