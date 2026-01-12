"""Git progress detection for circuit breaker."""

import hashlib
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class GitSnapshot:
    """Snapshot of git state at a point in time."""
    status_hash: str  # Hash of git status --porcelain output
    head_hash: str    # Current HEAD commit
    combined_hash: str  # Hash of both for easy comparison

    def __eq__(self, other):
        if not isinstance(other, GitSnapshot):
            return False
        return self.combined_hash == other.combined_hash


def take_snapshot(worktree: Path) -> Optional[GitSnapshot]:
    """
    Take a snapshot of the current git state.

    Args:
        worktree: Path to the git worktree

    Returns:
        GitSnapshot or None if not a git repo
    """
    if isinstance(worktree, str):
        worktree = Path(worktree).expanduser()

    try:
        # Get git status (staged + unstaged changes)
        status_result = subprocess.run(
            ["git", "-C", str(worktree), "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if status_result.returncode != 0:
            return None
        status_output = status_result.stdout

        # Get HEAD commit hash
        head_result = subprocess.run(
            ["git", "-C", str(worktree), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if head_result.returncode != 0:
            return None
        head_hash = head_result.stdout.strip()

        # Create hashes
        status_hash = hashlib.sha256(status_output.encode()).hexdigest()[:16]
        combined = f"{status_output}\n{head_hash}"
        combined_hash = hashlib.sha256(combined.encode()).hexdigest()[:16]

        return GitSnapshot(
            status_hash=status_hash,
            head_hash=head_hash[:12],  # Short hash for display
            combined_hash=combined_hash,
        )

    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def has_progress(before: Optional[GitSnapshot], after: Optional[GitSnapshot]) -> bool:
    """
    Check if there was progress between two snapshots.

    Progress = any change in git status or new commits.

    Args:
        before: Snapshot before work
        after: Snapshot after work

    Returns:
        True if any changes detected
    """
    if before is None or after is None:
        # Can't determine, assume progress to avoid false circuit opens
        return True

    return before != after


def get_recent_commits(worktree: Path, count: int = 3) -> list[str]:
    """
    Get recent commit messages for context.

    Args:
        worktree: Path to the git worktree
        count: Number of commits to fetch

    Returns:
        List of commit messages (one-line format)
    """
    if isinstance(worktree, str):
        worktree = Path(worktree).expanduser()

    try:
        result = subprocess.run(
            ["git", "-C", str(worktree), "log", f"-{count}", "--oneline"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip().split("\n")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return []
