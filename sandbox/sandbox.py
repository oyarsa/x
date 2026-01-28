#!/usr/bin/env python3
"""Docker-based sandbox for running Claude Code in dangerous mode."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    image_name: str = "claude-sandbox"
    container_prefix: str = "claude-sandbox"
    snapshot_prefix: str = "claude-sandbox-snapshot"

    def container_name(self, name: str) -> str:
        return f"{self.container_prefix}-{name}"

    def snapshot_name(self, name: str) -> str:
        return f"{self.snapshot_prefix}:{name}"

    @property
    def script_dir(self) -> Path:
        return Path(__file__).parent.resolve()

    @property
    def transfer_dir(self) -> Path:
        return self.script_dir / "transfer"

    @property
    def out_dir(self) -> Path:
        return self.script_dir / "out"


@dataclass
class SandboxConfig:
    """Per-project sandbox configuration from .mysandbox.toml"""

    branch: str = "master"
    setup: str | None = None
    check: str | None = None
    files: list[str] = field(default_factory=list)
    ports: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path | None = None) -> SandboxConfig:
        """Load config from .mysandbox.toml in the current directory or git root."""
        if path is None:
            path = Path.cwd() / ".mysandbox.toml"
        if not path.exists():
            return cls()
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return cls(
            branch=data.get("branch", "master"),
            setup=data.get("setup"),
            check=data.get("check"),
            files=data.get("files", []),
            ports=data.get("ports", []),
        )


# -- Logging ------------------------------------------------------------------


class Colors:
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[0;34m"
    NC = "\033[0m"


def log_info(msg: str) -> None:
    print(f"{Colors.BLUE}ℹ{Colors.NC} {msg}")


def log_success(msg: str) -> None:
    print(f"{Colors.GREEN}✓{Colors.NC} {msg}")


def log_warn(msg: str) -> None:
    print(f"{Colors.YELLOW}⚠{Colors.NC} {msg}")


def log_error(msg: str) -> None:
    print(f"{Colors.RED}✗{Colors.NC} {msg}", file=sys.stderr)


# -- Subprocess helpers -------------------------------------------------------


def run(
    cmd: list[str],
    *,
    capture: bool = False,
    check: bool = True,
    **kwargs,
) -> subprocess.CompletedProcess:
    if capture:
        kwargs.setdefault("stdout", subprocess.PIPE)
        kwargs.setdefault("stderr", subprocess.PIPE)
        kwargs.setdefault("text", True)
    return subprocess.run(cmd, check=check, **kwargs)


def run_quiet(cmd: list[str]) -> bool:
    result = subprocess.run(
        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False
    )
    return result.returncode == 0


# -- Docker operations --------------------------------------------------------


class Docker:
    def __init__(self, config: Config, name: str | None = None) -> None:
        self.config = config
        self.name = name

    @property
    def container_name(self) -> str:
        if not self.name:
            raise ValueError("Workspace name not set")
        return self.config.container_name(self.name)

    def image_exists(self) -> bool:
        return run_quiet(["docker", "image", "inspect", self.config.image_name])

    def container_exists(self) -> bool:
        return run_quiet(["docker", "container", "inspect", self.container_name])

    def container_running(self) -> bool:
        if not self.container_exists():
            return False
        result = run(
            [
                "docker",
                "container",
                "inspect",
                "-f",
                "{{.State.Running}}",
                self.container_name,
            ],
            capture=True,
            check=False,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"

    def build(self, *, force: bool = False) -> None:
        if force or not self.image_exists():
            log_info("Building Docker image...")
            cmd = ["docker", "build", "-t", self.config.image_name]
            # Pass GitHub token via secret to avoid rate limits during mise install
            github_token = os.environ.get("GITHUB_TOKEN")
            if not github_token:
                # Try getting token from gh CLI
                result = run(["gh", "auth", "token"], capture=True, check=False)
                if result.returncode == 0:
                    github_token = result.stdout.strip()
            token_file = self.config.script_dir / ".gh_token"
            try:
                if github_token:
                    token_file.write_text(github_token)
                    cmd.extend(["--secret", f"id=gh_token,src={token_file}"])
                cmd.append(str(self.config.script_dir))
                run(cmd)
            finally:
                token_file.unlink(missing_ok=True)
            log_success("Image built successfully")
        else:
            log_info("Image already exists (use 'rebuild' to force)")

    def rm_container(self) -> None:
        if self.container_exists():
            run(
                ["docker", "rm", "-f", self.container_name],
                capture=True,
                check=False,
            )

    def stop(self, *, kill: bool = False, timeout: int | None = None) -> None:
        if kill:
            run(["docker", "kill", self.container_name], capture=True, check=False)
        elif timeout is not None:
            run(
                ["docker", "stop", "-t", str(timeout), self.container_name],
                capture=True,
                check=False,
            )
        else:
            run(["docker", "stop", self.container_name], capture=True, check=False)

    def start(self) -> None:
        run(["docker", "start", self.container_name], capture=True, check=False)

    def list_containers(self) -> list[str]:
        """List all sandbox containers."""
        result = run(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                f"name={self.config.container_prefix}-",
                "--format",
                "{{.Names}}",
            ],
            capture=True,
            check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return []
        return result.stdout.strip().split("\n")

    def start_container(
        self,
        *,
        repo_name: str,
        repo_url: str,
        ports: list[str] | None = None,
        snapshot: str | None = None,
    ) -> None:
        # Create out directory for this repo
        out_dir = self.config.out_dir / repo_name
        out_dir.mkdir(parents=True, exist_ok=True)

        # Use snapshot image if provided, otherwise base image
        image = (
            self.config.snapshot_name(snapshot)
            if snapshot
            else self.config.image_name
        )

        cmd = [
            "docker",
            "run",
            "-d",
            "--name",
            self.container_name,
            "-v",
            f"{self.config.transfer_dir}:/transfer:ro",
            "-v",
            f"{out_dir}:/out",
            "-v",
            "claude-sandbox-uv-cache:/home/dev/.cache/uv",
            "-e",
            "UV_LINK_MODE=copy",
            "-e",
            f"REPO_URL={repo_url}",
            "-e",
            f"REPO_NAME={repo_name}",
        ]

        # Add port mappings
        for port in ports or []:
            cmd.extend(["-p", port])

        cmd.extend(["-it", image, "sleep", "infinity"])
        run(cmd)

    def exec(
        self,
        cmd: list[str],
        *,
        workdir: str | None = None,
        interactive: bool = False,
        capture: bool = False,
        check: bool = False,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess:
        docker_cmd = ["docker", "exec"]
        if interactive:
            docker_cmd.append("-it")
        if workdir:
            docker_cmd.extend(["-w", workdir])
        if env:
            for key, value in env.items():
                docker_cmd.extend(["-e", f"{key}={value}"])
        docker_cmd.append(self.container_name)
        docker_cmd.extend(cmd)
        return run(docker_cmd, capture=capture, check=check)

    def get_env(self, var: str) -> str | None:
        result = self.exec(["printenv", var], capture=True)
        return result.stdout.strip() if result.returncode == 0 else None

    def path_exists(self, path: str) -> bool:
        return self.exec(["test", "-d", path]).returncode == 0

    def get_workdir(self) -> str:
        repo_name = self.get_env("REPO_NAME")
        if repo_name:
            workspace = f"/workspace/{repo_name}"
            if self.path_exists(workspace):
                return workspace
        return "/root"

    def copy_from(self, src: str, dst: Path) -> None:
        run(["docker", "cp", f"{self.container_name}:{src}", str(dst)])

    def snapshot(self, snapshot_name: str) -> None:
        """Create a snapshot of the current container."""
        image_name = self.config.snapshot_name(snapshot_name)
        run(["docker", "commit", self.container_name, image_name])

    def list_snapshots(self) -> list[tuple[str, str, str]]:
        """List all snapshots. Returns list of (name, created, size) tuples."""
        result = run(
            [
                "docker",
                "images",
                "--filter",
                f"reference={self.config.snapshot_prefix}:*",
                "--format",
                "{{.Tag}}\t{{.CreatedSince}}\t{{.Size}}",
            ],
            capture=True,
            check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return []
        snapshots = []
        for line in result.stdout.strip().split("\n"):
            parts = line.split("\t")
            if len(parts) == 3:
                snapshots.append((parts[0], parts[1], parts[2]))
        return snapshots

    def snapshot_exists(self, snapshot_name: str) -> bool:
        """Check if a snapshot exists."""
        image_name = self.config.snapshot_name(snapshot_name)
        return run_quiet(["docker", "image", "inspect", image_name])

    def delete_snapshot(self, snapshot_name: str) -> None:
        """Delete a snapshot."""
        image_name = self.config.snapshot_name(snapshot_name)
        run(["docker", "rmi", image_name], capture=True)


# -- Git operations -----------------------------------------------------------


class Git:
    @staticmethod
    def is_repo() -> bool:
        return run_quiet(["git", "rev-parse", "--is-inside-work-tree"])

    @staticmethod
    def get_remote_url() -> str | None:
        result = run(["git", "remote", "get-url", "origin"], capture=True, check=False)
        return result.stdout.strip() if result.returncode == 0 else None

    @staticmethod
    def normalize_url(url: str) -> str:
        # Convert SSH to HTTPS
        if url.startswith("git@github.com:"):
            url = "https://github.com/" + url.removeprefix("git@github.com:")
        # Ensure .git suffix
        if not url.endswith(".git"):
            url += ".git"
        return url

    @staticmethod
    def repo_name_from_url(url: str) -> str:
        return Path(url).stem  # removes .git


# -- VCS helpers --------------------------------------------------------------


def check_workspace_dirty(docker: Docker) -> tuple[bool, str]:
    """Check if the workspace has uncommitted changes (git or jj).

    Returns (is_dirty, message) tuple.
    """
    if not docker.container_running():
        return False, ""

    workdir = docker.get_workdir()
    if workdir == "/root":
        return False, ""

    messages = []

    # Check git status
    result = docker.exec(
        ["git", "status", "--porcelain"],
        workdir=workdir,
        capture=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        messages.append("Git has uncommitted changes")

    # Check jj status (non-empty working copy)
    result = docker.exec(
        ["jj", "diff", "--stat"],
        workdir=workdir,
        capture=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        messages.append("Current jj change is non-empty")

    if messages:
        return True, "; ".join(messages)
    return False, ""


# -- Commands -----------------------------------------------------------------


@dataclass
class UpOptions:
    """CLI options for the up command."""

    setup: str | None = None
    check: str | None = None
    files: list[str] = field(default_factory=list)
    ports: list[str] = field(default_factory=list)
    snapshot: str | None = None


def cmd_up(config: Config, docker: Docker, opts: UpOptions | None = None) -> int:
    if not Git.is_repo():
        log_error("Not in a git repository")
        return 1

    remote_url = Git.get_remote_url()
    if not remote_url:
        log_error("No 'origin' remote found")
        return 1

    # Load per-project config and merge with CLI options
    sandbox_config = SandboxConfig.load()
    opts = opts or UpOptions()

    # CLI options override config file
    setup = opts.setup if opts.setup is not None else sandbox_config.setup
    check = opts.check if opts.check is not None else sandbox_config.check
    files = opts.files if opts.files else sandbox_config.files
    ports = opts.ports if opts.ports else sandbox_config.ports

    repo_url = Git.normalize_url(remote_url)
    repo_name = Git.repo_name_from_url(repo_url)

    log_info(f"Repository: {repo_url}")
    log_info(f"Branch: {sandbox_config.branch}")
    log_info(f"Name: {repo_name}")
    if ports:
        log_info(f"Ports: {', '.join(ports)}")
    if opts.snapshot:
        log_info(f"Snapshot: {opts.snapshot}")

    # When using a snapshot, verify it exists; otherwise build base image
    if opts.snapshot:
        if not docker.snapshot_exists(opts.snapshot):
            log_error(f"Snapshot '{opts.snapshot}' not found")
            return 1
    else:
        docker.build()

    # Create directories
    config.transfer_dir.mkdir(exist_ok=True)
    config.out_dir.mkdir(exist_ok=True)

    if docker.container_exists():
        log_warn("Removing existing container...")
        docker.rm_container()

    log_info("Starting container...")
    docker.start_container(
        repo_name=repo_name, repo_url=repo_url, ports=ports, snapshot=opts.snapshot
    )
    log_success("Container started")

    container_workspace = f"/workspace/{repo_name}"

    # Create workspace directory inside container
    docker.exec(["mkdir", "-p", container_workspace], check=True)

    # Skip clone when using a snapshot (workspace is already in the image)
    if opts.snapshot:
        log_info("Using snapshot, skipping clone")
    else:
        # Clone if workspace is empty
        result = docker.exec(["ls", "-A", container_workspace], capture=True)
        workspace_empty = result.returncode == 0 and not result.stdout.strip()

        if workspace_empty:
            log_info("Cloning repository...")
            clone_url = repo_url.replace("https://", "https://oyarsa@")
            docker.exec(
                ["git", "clone", "-b", sandbox_config.branch, clone_url, "."],
                workdir=container_workspace,
                check=True,
            )
            # Set up jj colocated with git
            docker.exec(
                ["jj", "git", "init", "--colocate", "."],
                workdir=container_workspace,
                check=True,
            )
            log_success(f"Repository cloned to {container_workspace}")
        else:
            log_info("Workspace already has content, skipping clone")

    # Copy files into workspace
    for file_path in files:
        src = Path(file_path).expanduser()
        if not src.exists():
            log_warn(f"File not found, skipping: {src}")
            continue
        dst = f"{container_workspace}/{src.name}"
        run(["docker", "cp", str(src), f"{docker.container_name}:{dst}"])
        docker.exec(["chown", "-R", "dev:dev", dst])
        log_info(f"Copied {src} to {dst}")

    # Run optional setup commands from config
    if setup:
        log_info(f"Running setup: {setup}")
        docker.exec(["sh", "-c", setup], workdir=container_workspace)

    if check:
        log_info(f"Running check: {check}")
        docker.exec(["sh", "-c", check], workdir=container_workspace)

    log_success("Setup complete!")
    print()
    log_info("Sandbox is ready. Commands:")
    print("  sandbox shell      - Enter the sandbox")
    print("  sandbox cp-in X    - Copy X to transfer/ (at /transfer in container)")
    print("  sandbox cp-out X   - Copy X from container to ./out/")
    print("  sandbox down       - Stop the sandbox")
    print()
    log_info("Inside the sandbox, run 'yolo' to start Claude")
    log_info("Write to /out inside container - files appear in ./out/")
    log_warn("Workspace lives inside container - use cp-out to save work")
    return 0


def cmd_shell(config: Config, docker: Docker, workdir: str | None = None) -> int:
    if not docker.container_running():
        if docker.container_exists():
            # Container stopped - start it
            log_info("Container stopped, starting it...")
            docker.start()
        else:
            # Container doesn't exist - create it
            log_info("Container not found, creating it...")
            result = cmd_up(config, docker)
            if result != 0:
                return result

    workdir = workdir or docker.get_workdir()
    term_env = {"TERM": os.environ.get("TERM", "xterm-256color")}
    docker.exec(["fish"], workdir=workdir, interactive=True, env=term_env)
    return 0


def cmd_exec(
    config: Config, docker: Docker, cmd: list[str], workdir: str | None = None
) -> int:
    if not docker.container_running():
        log_error("Container is not running. Run 'sandbox up' first.")
        return 1

    workdir = workdir or docker.get_workdir()
    term_env = {"TERM": os.environ.get("TERM", "xterm-256color")}
    result = docker.exec(cmd, workdir=workdir, interactive=True, env=term_env)
    return result.returncode


def cmd_cp_in(config: Config, docker: Docker, path: str) -> int:
    src = Path(path)
    if not src.exists():
        log_error(f"Source does not exist: {src}")
        return 1

    config.transfer_dir.mkdir(exist_ok=True)
    dst = config.transfer_dir / src.name

    if src.is_dir():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)

    log_success(f"Copied '{src}' to transfer/")
    log_info(f"Available in container at: /transfer/{src.name}")
    return 0


def cmd_cp_out(config: Config, docker: Docker, path: str | None) -> int:
    if not docker.container_running():
        log_error("Container is not running. Run 'sandbox up' first.")
        return 1

    # Get workspace name for per-project output directory
    repo_name = docker.get_env("REPO_NAME")
    if repo_name:
        out_dir = config.out_dir / repo_name
    else:
        out_dir = config.out_dir

    # If no path provided, just print the output directory
    if path is None:
        out_dir.mkdir(parents=True, exist_ok=True)
        print(out_dir)
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)

    # Resolve relative paths against workspace
    if not path.startswith("/"):
        if repo_name:
            path = f"/workspace/{repo_name}/{path}"

    try:
        docker.copy_from(path, out_dir)
        dest_path = out_dir / Path(path).name
        print(f"{Colors.GREEN}✓{Colors.NC} Copied '{path}' to {out_dir}", file=sys.stderr)
        print(dest_path)
        return 0
    except subprocess.CalledProcessError:
        log_error(f"Failed to copy '{path}'")
        return 1


def cmd_down(config: Config, docker: Docker, yes: bool = False) -> int:
    if docker.container_exists():
        # Check for uncommitted changes
        is_dirty, dirty_msg = check_workspace_dirty(docker)
        if is_dirty and not yes:
            log_warn(f"Workspace has uncommitted changes: {dirty_msg}")
            response = input("Continue anyway? [y/N] ")
            if response.lower() != "y":
                return 1

        log_info("Stopping container...")
        docker.rm_container()
        log_success("Container removed (workspace preserved)")
    else:
        log_info("Container doesn't exist")
    return 0


def cmd_stop(
    config: Config, docker: Docker, *, kill: bool = False, timeout: int | None = None
) -> int:
    if docker.container_running():
        if kill:
            log_info("Killing container...")
        else:
            log_info("Stopping container...")
        docker.stop(kill=kill, timeout=timeout)
        log_success("Container stopped (can resume with 'sandbox start')")
    elif docker.container_exists():
        log_info("Container already stopped")
    else:
        log_error("Container doesn't exist. Run 'sandbox up' first.")
        return 1
    return 0


def cmd_start(config: Config, docker: Docker) -> int:
    if docker.container_running():
        log_info("Container already running")
    elif docker.container_exists():
        log_info("Starting container...")
        docker.start()
        log_success("Container started")
    else:
        log_error("Container doesn't exist. Run 'sandbox up' first.")
        return 1
    return 0


def cmd_status(config: Config, docker: Docker) -> int:
    print(f"Image: {config.image_name}")
    if docker.image_exists():
        print(f"  Status: {Colors.GREEN}exists{Colors.NC}")
    else:
        print(f"  Status: {Colors.YELLOW}not built{Colors.NC}")

    print()
    print(f"Container: {docker.container_name}")
    if docker.container_running():
        print(f"  Status: {Colors.GREEN}running{Colors.NC}")
        repo_name = docker.get_env("REPO_NAME") or "unknown"
        print(f"  Repository: {repo_name}")
        print(f"  Workspace: /workspace/{repo_name}")
    elif docker.container_exists():
        print(f"  Status: {Colors.YELLOW}stopped{Colors.NC}")
    else:
        print(f"  Status: {Colors.RED}not created{Colors.NC}")

    return 0


def cmd_logs(config: Config, docker: Docker) -> int:
    if not docker.container_exists():
        log_error("Container doesn't exist")
        return 1
    run(["docker", "logs", docker.container_name])
    return 0


def cmd_rebuild(config: Config, docker: Docker) -> int:
    docker.build(force=True)
    return 0


def cmd_list(config: Config, docker: Docker) -> int:
    containers = docker.list_containers()
    if not containers:
        log_info("No sandbox containers found")
        return 0

    print("Sandbox containers:")
    for name in containers:
        # Check if container is running
        result = run(
            ["docker", "inspect", "-f", "{{.State.Running}}", name],
            capture=True,
            check=False,
        )
        is_running = result.returncode == 0 and result.stdout.strip() == "true"
        status = (
            f"{Colors.GREEN}running{Colors.NC}"
            if is_running
            else f"{Colors.YELLOW}stopped{Colors.NC}"
        )

        # Extract workspace name from container name
        workspace = name.removeprefix(f"{config.container_prefix}-")
        print(f"  {workspace}: {status}")

    return 0


def cmd_destroy(config: Config, docker: Docker, yes: bool = False) -> int:
    if not docker.container_exists():
        log_info("No container to destroy")
        return 0

    # Check for uncommitted changes
    is_dirty, dirty_msg = check_workspace_dirty(docker)
    if is_dirty:
        log_warn(f"Workspace has uncommitted changes: {dirty_msg}")

    if not yes:
        response = input(
            "This will delete the container and all workspace data. Continue? [y/N] "
        )
        if response.lower() != "y":
            return 1

    if docker.container_running():
        log_info("Stopping container...")
        docker.rm_container()
    else:
        docker.rm_container()

    log_success("Container removed")
    return 0


def cmd_snapshot(config: Config, docker: Docker, snapshot_name: str) -> int:
    if not docker.container_exists():
        log_error("Container doesn't exist. Run 'sandbox up' first.")
        return 1

    if docker.snapshot_exists(snapshot_name):
        log_error(f"Snapshot '{snapshot_name}' already exists")
        return 1

    log_info(f"Creating snapshot '{snapshot_name}'...")
    docker.snapshot(snapshot_name)
    log_success(f"Snapshot '{snapshot_name}' created")
    log_info(f"Use 'sandbox up --snapshot {snapshot_name}' to restore")
    return 0


def cmd_snapshot_list(config: Config, docker: Docker) -> int:
    snapshots = docker.list_snapshots()
    if not snapshots:
        log_info("No snapshots found")
        return 0

    print("Snapshots:")
    for name, created, size in snapshots:
        print(f"  {name}: {created} ({size})")
    return 0


def cmd_snapshot_delete(
    config: Config, docker: Docker, snapshot_name: str, yes: bool = False
) -> int:
    if not docker.snapshot_exists(snapshot_name):
        log_error(f"Snapshot '{snapshot_name}' not found")
        return 1

    if not yes:
        response = input(f"Delete snapshot '{snapshot_name}'? [y/N] ")
        if response.lower() != "y":
            return 1

    log_info(f"Deleting snapshot '{snapshot_name}'...")
    docker.delete_snapshot(snapshot_name)
    log_success(f"Snapshot '{snapshot_name}' deleted")
    return 0


def cmd_init() -> int:
    config_file = Path.cwd() / ".mysandbox.toml"
    if config_file.exists():
        log_error(f"{config_file} already exists")
        return 1

    config_file.write_text("""\
branch = "master"
# setup = "uv sync"
# check = "uv run pytest"
# files = [
#     "~/.env.local",
# ]
# ports = [
#     "8000:8000",
# ]
""")
    log_success(f"Created {config_file}")
    return 0


# -- Main ---------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Docker-based sandbox for Claude Code",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Options:
  -n, --name      Workspace name (defaults to repo name)
  -w, --workdir   Set working directory for shell/exec commands
  --kill          Force kill (SIGKILL) for stop command
  -t, --timeout   Seconds to wait before killing (for stop)
  -p, --port      Port mapping host:container (repeatable, for up)
  --setup         Setup command after cloning (for up)
  --check         Check command after setup (for up)
  -f, --file      File to copy into workspace (repeatable, for up)
  --snapshot      Create container from snapshot (for up)

Commands:
  init            Create .mysandbox.toml config file
  up [name]       Start sandbox, clone repo, run setup
  shell (s)       Enter the sandbox shell
  exec <cmd>      Run a command in the sandbox
  cp-in <path>    Copy file/directory to transfer/
  cp-out <path>   Copy file/directory from container to ./out/
  stop            Stop container (preserves state)
  start           Start stopped container
  down            Remove container (workspace preserved)
  status          Show sandbox status
  logs            Show container logs
  list            List all sandboxes
  rebuild         Force rebuild the image
  destroy         Remove container and workspace
  snapshot new <name>  Save container state as a snapshot
  snapshot ls          List all snapshots
  snapshot rm <name>   Delete a snapshot

Run from a git repository directory. The sandbox will clone that repo.
Workspace lives inside container - use cp-out to save work.
""",
    )
    parser.add_argument("command", help="Command to run")
    parser.add_argument("args", nargs="*", help="Command arguments")
    parser.add_argument("-n", "--name", help="Workspace name (defaults to repo name)")
    parser.add_argument(
        "-w", "--workdir", help="Working directory inside the container"
    )
    parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip confirmation prompts"
    )
    parser.add_argument(
        "--kill",
        action="store_true",
        help="Force kill (SIGKILL) instead of graceful stop",
    )
    parser.add_argument(
        "-t",
        "--timeout",
        type=int,
        help="Seconds to wait before killing (for stop command)",
    )
    parser.add_argument(
        "-p",
        "--port",
        action="append",
        dest="ports",
        default=[],
        help="Port mapping (host:container), can be repeated",
    )
    parser.add_argument(
        "--setup",
        help="Setup command to run after cloning (overrides config)",
    )
    parser.add_argument(
        "--check",
        help="Check command to run after setup (overrides config)",
    )
    parser.add_argument(
        "-f",
        "--file",
        action="append",
        dest="files",
        default=[],
        help="File to copy into workspace, can be repeated (overrides config)",
    )
    parser.add_argument(
        "--snapshot",
        help="Create container from snapshot instead of base image (for up)",
    )

    args = parser.parse_args()

    config = Config()

    # Determine workspace name
    name = args.name
    if (
        not name
        and args.args
        and args.command
        in ("up", "shell", "s", "down", "stop", "status", "logs", "destroy")
    ):
        name = args.args[0]
        args.args = args.args[1:]
    # Commands that don't require a workspace name
    no_name_commands = {"list", "rebuild", "init", "help", "-h", "--help"}
    # snapshot ls/rm don't need workspace, but snapshot new does
    if args.command == "snapshot" and args.args and args.args[0] in ("ls", "list", "rm", "delete"):
        no_name_commands.add("snapshot")

    if not name and args.command not in no_name_commands:
        # Try to get from git repo
        if Git.is_repo():
            remote_url = Git.get_remote_url()
            if remote_url:
                name = Git.repo_name_from_url(Git.normalize_url(remote_url))

    docker = Docker(config, name)

    match args.command:
        case "up":
            up_opts = UpOptions(
                setup=args.setup,
                check=args.check,
                files=args.files,
                ports=args.ports,
                snapshot=args.snapshot,
            )
            return cmd_up(config, docker, up_opts)
        case "shell" | "s":
            return cmd_shell(config, docker, args.workdir)
        case "exec":
            if not args.args:
                log_error("exec requires a command")
                return 1
            return cmd_exec(config, docker, args.args, args.workdir)
        case "cp-in" | "in":
            if not args.args:
                log_error("cp-in requires a path")
                return 1
            return cmd_cp_in(config, docker, args.args[0])
        case "cp-out" | "out":
            return cmd_cp_out(config, docker, args.args[0] if args.args else None)
        case "down":
            return cmd_down(config, docker, args.yes)
        case "stop":
            return cmd_stop(config, docker, kill=args.kill, timeout=args.timeout)
        case "start":
            return cmd_start(config, docker)
        case "status":
            return cmd_status(config, docker)
        case "logs":
            return cmd_logs(config, docker)
        case "list" | "ls":
            return cmd_list(config, docker)
        case "rebuild":
            return cmd_rebuild(config, docker)
        case "destroy":
            return cmd_destroy(config, docker, args.yes)
        case "init":
            return cmd_init()
        case "snapshot":
            if not args.args:
                log_error("snapshot requires a subcommand: new, ls, rm")
                return 1
            subcmd = args.args[0]
            subargs = args.args[1:]
            match subcmd:
                case "new":
                    if not subargs:
                        log_error("snapshot new requires a name")
                        return 1
                    return cmd_snapshot(config, docker, subargs[0])
                case "ls" | "list":
                    return cmd_snapshot_list(config, docker)
                case "rm" | "delete":
                    if not subargs:
                        log_error("snapshot rm requires a name")
                        return 1
                    return cmd_snapshot_delete(config, docker, subargs[0], args.yes)
                case _:
                    log_error(f"Unknown snapshot subcommand: {subcmd}")
                    return 1
        case "help" | "-h" | "--help":
            parser.print_help()
            return 0
        case _:
            log_error(f"Unknown command: {args.command}")
            parser.print_help()
            return 1


if __name__ == "__main__":
    sys.exit(main())
