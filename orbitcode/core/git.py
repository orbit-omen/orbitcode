"""Git integration for OrbitCode."""
import subprocess
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class GitStatus:
    """Git repository status."""
    is_repo: bool
    branch: str
    dirty: bool
    staged_files: list[str]
    unstaged_files: list[str]
    untracked_files: list[str]
    ahead: int
    behind: int


@dataclass
class GitCommit:
    """Git commit info."""
    hash: str
    short_hash: str
    message: str
    author: str
    date: datetime


class GitIntegration:
    """Git operations for the agent."""

    def __init__(self, working_dir: Path):
        self.working_dir = working_dir
        self._is_repo = None

    def _run(self, args: list[str], capture: bool = True) -> subprocess.CompletedProcess:
        """Run a git command."""
        cmd = ["git", "-C", str(self.working_dir)] + args
        return subprocess.run(cmd, capture_output=capture, text=True)

    def is_repo(self) -> bool:
        """Check if working directory is a git repo."""
        if self._is_repo is None:
            result = self._run(["rev-parse", "--git-dir"])
            self._is_repo = result.returncode == 0
        return self._is_repo

    def get_status(self) -> GitStatus:
        """Get detailed git status."""
        if not self.is_repo():
            return GitStatus(False, "", False, [], [], [], 0, 0)

        # Branch
        branch_result = self._run(["branch", "--show-current"])
        branch = branch_result.stdout.strip() or "detached"

        # Status
        status_result = self._run(["status", "--porcelain=v1"])
        staged = []
        unstaged = []
        untracked = []

        for line in status_result.stdout.strip().split("\n"):
            if not line:
                continue
            status = line[:2]
            file = line[3:]
            if status[0] in ("A", "M", "D", "R", "C"):
                staged.append(file)
            if status[1] in ("M", "D"):
                unstaged.append(file)
            if status == "??":
                untracked.append(file)

        # Ahead/behind
        ahead = behind = 0
        try:
            upstream_result = self._run(["rev-list", "--left-right", "--count", f"@{ {u}}...HEAD"])
            if upstream_result.returncode == 0:
                behind_str, ahead_str = upstream_result.stdout.strip().split("\t")
                behind, ahead = int(behind_str), int(ahead_str)
        except Exception:
            pass

        return GitStatus(
            is_repo=True,
            branch=branch,
            dirty=bool(staged or unstaged or untracked),
            staged_files=staged,
            unstaged_files=unstaged,
            untracked_files=untracked,
            ahead=ahead,
            behind=behind,
        )

    def get_diff(self, staged: bool = False, file: Optional[str] = None) -> str:
        """Get git diff."""
        args = ["diff"]
        if staged:
            args.append("--cached")
        if file:
            args.append(file)
        result = self._run(args)
        return result.stdout

    def get_log(self, limit: int = 10, oneline: bool = True) -> list[GitCommit]:
        """Get recent commits."""
        args = ["log", f"-{limit}", "--pretty=format:%H|%h|%s|%an|%ai"]
        if oneline:
            args.append("--oneline")
        result = self._run(args)

        commits = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("|", 4)
            if len(parts) == 5:
                commits.append(GitCommit(
                    hash=parts[0],
                    short_hash=parts[1],
                    message=parts[2],
                    author=parts[3],
                    date=datetime.fromisoformat(parts[4].replace("Z", "+00:00")),
                ))
        return commits

    def add(self, files: list[str]) -> bool:
        """Stage files."""
        result = self._run(["add"] + files)
        return result.returncode == 0

    def commit(self, message: str, author: Optional[str] = None) -> Optional[str]:
        """Create a commit."""
        args = ["commit", "-m", message]
        if author:
            args.extend(["--author", author])
        result = self._run(args)
        if result.returncode == 0:
            # Get the commit hash
            hash_result = self._run(["rev-parse", "HEAD"])
            return hash_result.stdout.strip()
        return None

    def push(self, remote: str = "origin", branch: Optional[str] = None) -> bool:
        """Push to remote."""
        args = ["push", remote]
        if branch:
            args.append(branch)
        result = self._run(args)
        return result.returncode == 0

    def create_branch(self, name: str, checkout: bool = True) -> bool:
        """Create a new branch."""
        args = ["checkout", "-b", name] if checkout else ["branch", name]
        result = self._run(args)
        return result.returncode == 0

    def checkout(self, branch: str) -> bool:
        """Checkout a branch."""
        result = self._run(["checkout", branch])
        return result.returncode == 0

    def get_remote_url(self, remote: str = "origin") -> Optional[str]:
        """Get remote URL."""
        result = self._run(["remote", "get-url", remote])
        if result.returncode == 0:
            return result.stdout.strip()
        return None

    def create_pr_title_body(self, base: str = "main") -> tuple[str, str]:
        """Generate PR title and body from commits."""
        commits = self.get_log(limit=20)
        if not commits:
            return "", ""

        # Use first commit as title, rest as body
        title = commits[0].message
        body_lines = ["## Changes"]
        for c in commits:
            body_lines.append(f"- {c.short_hash}: {c.message}")
        body_lines.append(f"\nBase branch: {base}")
        return title, "\n".join(body_lines)