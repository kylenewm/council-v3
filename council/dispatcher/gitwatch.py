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


def get_diff_summary(worktree: Path, since_commit: str = "HEAD~1") -> dict:
    """
    Get a summary of changes since a commit.

    Args:
        worktree: Path to the git worktree
        since_commit: Compare against this commit (default HEAD~1)

    Returns:
        dict with files_changed, insertions, deletions, file_list
    """
    if isinstance(worktree, str):
        worktree = Path(worktree).expanduser()

    result = {
        "files_changed": 0,
        "insertions": 0,
        "deletions": 0,
        "file_list": [],
    }

    try:
        # Get diff stat
        stat_result = subprocess.run(
            ["git", "-C", str(worktree), "diff", "--stat", "--stat-width=80", since_commit],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if stat_result.returncode == 0 and stat_result.stdout.strip():
            lines = stat_result.stdout.strip().split("\n")
            # Last line is summary: " 3 files changed, 10 insertions(+), 2 deletions(-)"
            if lines:
                for line in lines[:-1]:  # All but last line are file changes
                    parts = line.strip().split("|")
                    if len(parts) >= 1:
                        filename = parts[0].strip()
                        if filename:
                            result["file_list"].append(filename)

                # Parse summary line
                summary = lines[-1]
                import re
                files_match = re.search(r"(\d+) files? changed", summary)
                ins_match = re.search(r"(\d+) insertions?", summary)
                del_match = re.search(r"(\d+) deletions?", summary)
                if files_match:
                    result["files_changed"] = int(files_match.group(1))
                if ins_match:
                    result["insertions"] = int(ins_match.group(1))
                if del_match:
                    result["deletions"] = int(del_match.group(1))

    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return result


def get_uncommitted_summary(worktree: Path) -> dict:
    """
    Get a summary of uncommitted changes.

    Args:
        worktree: Path to the git worktree

    Returns:
        dict with staged, unstaged, untracked counts and file lists
    """
    if isinstance(worktree, str):
        worktree = Path(worktree).expanduser()

    result = {
        "staged": [],
        "unstaged": [],
        "untracked": [],
    }

    try:
        status_result = subprocess.run(
            ["git", "-C", str(worktree), "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if status_result.returncode == 0:
            for line in status_result.stdout.strip().split("\n"):
                if not line:
                    continue
                index_status = line[0] if len(line) > 0 else " "
                work_status = line[1] if len(line) > 1 else " "
                filename = line[3:] if len(line) > 3 else ""

                if index_status == "?":
                    result["untracked"].append(filename)
                elif index_status != " ":
                    result["staged"].append(filename)
                elif work_status != " ":
                    result["unstaged"].append(filename)

    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return result
