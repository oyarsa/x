"""Clones all GitHub repositories and compresses them using tar.gz.

This script authenticates with GitHub, retrieves a list of non-forked repositories
(including private ones), clones them into a temporary directory under a "backup" folder
using SSH, and then compresses the entire directory using tar.gz compression.
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import requests
from git import Repo
from git.exc import GitCommandError
from tqdm import tqdm


def get_github_repos(token: str) -> list[dict[str, Any]]:
    """Retrieve a list of non-forked GitHub repositories for the authenticated user.

    Connects to the GitHub API and fetches all repositories, filtering out forks.

    Args:
        token: GitHub personal access token for authentication.

    Returns:
        A list of dictionaries containing repository information.

    Raises:
        requests.RequestException: If there's an issue with the API request.
    """
    headers = {"Authorization": f"token {token}"}
    repos: list[dict[str, Any]] = []
    page = 1

    while True:
        response = requests.get(
            f"https://api.github.com/user/repos?page={page}&per_page=100",
            headers=headers,
        )
        response.raise_for_status()

        page_repos = response.json()
        if not page_repos:
            break

        repos.extend(repo for repo in page_repos if not repo["fork"])
        page += 1

    return repos


def clone_repos(
    repos: list[dict[str, Any]], target_dir: Path, limit: int | None
) -> None:
    """Clone the given list of repositories into the target directory using SSH.

    Args:
        repos: List of repository information dictionaries.
        target_dir: Path to the directory where repositories will be cloned.
        limit: Optional number of repositories to clone. If None, all repos are cloned.
    """
    backup_dir = target_dir / "backup"
    backup_dir.mkdir(exist_ok=True)

    repos_to_clone = repos[:limit] if limit is not None else repos
    with tqdm(total=len(repos_to_clone), unit="repo") as pbar:
        for repo in repos_to_clone:
            repo_path = backup_dir / repo["name"]
            pbar.set_description(f"{repo['full_name']}")
            try:
                ssh_url = repo["ssh_url"]
                Repo.clone_from(ssh_url, repo_path)
            except GitCommandError as e:
                pbar.write(f"Error cloning {repo['full_name']}: {e}")
            pbar.update(1)


def compress_directory(source_dir: Path, output_file: Path) -> None:
    """Compress the given directory using tar.gz.

    Args:
        source_dir: Path to the directory to be compressed.
        output_file: Path to the output compressed file.
    """
    subprocess.run(
        [
            "tar",
            "-czf",
            str(output_file),
            "-C",
            str(source_dir),
            "backup",
        ],
        check=True,
    )


def main(token: str | None, output_file: Path, repo_limit: int | None = None) -> None:
    if token is None:
        if "GITHUB_TOKEN" not in os.environ:
            raise ValueError(
                "Provide a GitHub token or set the GITHUB_TOKEN environment variable."
            )
        token = os.environ["GITHUB_TOKEN"]

    repos = get_github_repos(token)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        print(f"Cloning {len(repos)} repositories...")
        clone_repos(repos, temp_path, repo_limit)
        print("Compressing backup...")
        compress_directory(temp_path, output_file)

    print(f"Backup completed and saved to {output_file}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--token", type=str, help="GitHub personal access token")
    parser.add_argument(
        "--output",
        "-o",
        default="backup.tar.gz",
        type=Path,
        help="Output file path for the compressed backup (default: %(default)s)",
    )
    parser.add_argument(
        "--limit",
        "-n",
        type=int,
        default=None,
        help="Limit the number of repositories to clone (for testing) (default: all)",
    )
    args = parser.parse_args()

    main(args.token, args.output, args.limit)
