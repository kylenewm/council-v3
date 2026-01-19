"""Tests for task context handling.

These tests verify that task files are written correctly and that
short/meaningless commands don't overwrite real task descriptions.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch

from council.dispatcher.simple import (
    Agent, write_current_task, get_task_context,
    CURRENT_TASK_DIR,
)


@pytest.fixture
def mock_agent():
    """Create a mock agent for testing."""
    return Agent(
        id=99,  # Use high ID to avoid conflicts
        pane_id="%99",
        name="TaskTestAgent",
        worktree=Path("/tmp/test-project"),
    )


@pytest.fixture
def temp_task_dir(tmp_path):
    """Use temporary directory for task files."""
    with patch.object(
        __import__("council.dispatcher.simple", fromlist=["CURRENT_TASK_DIR"]),
        "CURRENT_TASK_DIR",
        tmp_path,
    ):
        yield tmp_path


class TestWriteCurrentTask:
    """Tests for write_current_task function."""

    def test_real_task_written(self, mock_agent):
        """A real task description should be written to file."""
        write_current_task(mock_agent, "Implement the new feature for user authentication")

        ctx = get_task_context(mock_agent)
        assert "Implement the new feature" in ctx["task"]

    def test_skip_continue_command(self, mock_agent):
        """'continue' should not overwrite existing task."""
        # First write a real task
        write_current_task(mock_agent, "Real task description here")

        # Then try to overwrite with 'continue'
        write_current_task(mock_agent, "continue")

        # Should still have the real task
        ctx = get_task_context(mock_agent)
        assert "Real task description" in ctx["task"]

    def test_skip_y_command(self, mock_agent):
        """'y' should not overwrite existing task."""
        write_current_task(mock_agent, "Real task")
        write_current_task(mock_agent, "y")

        ctx = get_task_context(mock_agent)
        assert "Real task" in ctx["task"]

    def test_skip_yes_command(self, mock_agent):
        """'yes' should not overwrite existing task."""
        write_current_task(mock_agent, "Real task")
        write_current_task(mock_agent, "yes")

        ctx = get_task_context(mock_agent)
        assert "Real task" in ctx["task"]

    def test_skip_no_command(self, mock_agent):
        """'no' should not overwrite existing task."""
        write_current_task(mock_agent, "Real task")
        write_current_task(mock_agent, "no")

        ctx = get_task_context(mock_agent)
        assert "Real task" in ctx["task"]

    def test_skip_ok_command(self, mock_agent):
        """'ok' should not overwrite existing task."""
        write_current_task(mock_agent, "Real task")
        write_current_task(mock_agent, "ok")

        ctx = get_task_context(mock_agent)
        assert "Real task" in ctx["task"]

    def test_skip_empty_string(self, mock_agent):
        """Empty string should not overwrite existing task."""
        write_current_task(mock_agent, "Real task")
        write_current_task(mock_agent, "")

        ctx = get_task_context(mock_agent)
        assert "Real task" in ctx["task"]

    def test_case_insensitive_skip(self, mock_agent):
        """Skip commands should be case-insensitive."""
        write_current_task(mock_agent, "Real task")
        write_current_task(mock_agent, "CONTINUE")

        ctx = get_task_context(mock_agent)
        assert "Real task" in ctx["task"]


class TestTaskContextShortCommands:
    """Tests for filtering short/meaningless commands."""

    def test_skip_single_digit(self, mock_agent):
        """Single digit '1' should not overwrite existing task."""
        write_current_task(mock_agent, "Real task")
        write_current_task(mock_agent, "1")

        ctx = get_task_context(mock_agent)
        assert "Real task" in ctx["task"]

    def test_skip_very_short_strings(self, mock_agent):
        """Very short strings like 'yeah' should not overwrite."""
        write_current_task(mock_agent, "Real task")
        write_current_task(mock_agent, "yeah")

        ctx = get_task_context(mock_agent)
        assert "Real task" in ctx["task"]

    def test_skip_double_digit(self, mock_agent):
        """Double digits like '12' should not overwrite."""
        write_current_task(mock_agent, "Real task")
        write_current_task(mock_agent, "12")

        ctx = get_task_context(mock_agent)
        assert "Real task" in ctx["task"]

    def test_real_task_still_written(self, mock_agent):
        """Longer real commands should still be written."""
        write_current_task(mock_agent, "Fix the authentication bug")

        ctx = get_task_context(mock_agent)
        assert "Fix the authentication bug" in ctx["task"]


class TestGetTaskContext:
    """Tests for get_task_context function."""

    def test_returns_agent_name(self, mock_agent):
        """Should include agent name in context."""
        write_current_task(mock_agent, "Some task")
        ctx = get_task_context(mock_agent)
        assert ctx["agent_name"] == mock_agent.name

    def test_returns_project_name(self, mock_agent):
        """Should include project name from worktree."""
        write_current_task(mock_agent, "Some task")
        ctx = get_task_context(mock_agent)
        assert ctx["project"] == "test-project"

    def test_truncates_long_task(self, mock_agent):
        """Long task descriptions should be truncated."""
        long_task = "x" * 100
        write_current_task(mock_agent, long_task)
        ctx = get_task_context(mock_agent)
        assert len(ctx["task"]) <= 63  # 60 + "..."

    def test_missing_task_file_returns_empty(self, mock_agent):
        """Missing task file should return empty task."""
        # Create agent with different ID (no file exists)
        other_agent = Agent(
            id=9999,
            pane_id="%9999",
            name="NoFile",
            worktree=Path("/tmp/test"),
        )
        ctx = get_task_context(other_agent)
        assert ctx["task"] == ""


class TestTaskContextStripping:
    """Tests for context prefix stripping."""

    def test_strips_context_injection_prefix(self, mock_agent):
        """Should strip 'CONTEXT FROM COUNCIL AGENT:' prefix."""
        write_current_task(
            mock_agent,
            "CONTEXT FROM COUNCIL AGENT: Implement the feature"
        )
        ctx = get_task_context(mock_agent)
        assert "CONTEXT FROM" not in ctx["task"]
        assert "Implement the feature" in ctx["task"]

    def test_strips_strict_mode_prefix(self, mock_agent):
        """Should strip '[STRICT MODE]' prefix."""
        write_current_task(mock_agent, "[STRICT MODE] Fix the bug")
        ctx = get_task_context(mock_agent)
        assert "[STRICT MODE]" not in ctx["task"]
        assert "Fix the bug" in ctx["task"]
