"""Tests for tmux interaction functions."""

import pytest
from unittest.mock import patch, MagicMock

from council.dispatcher.simple import (
    tmux_capture, tmux_send, tmux_pane_exists, tmux_pane_in_copy_mode
)


class TestTmuxCapture:
    """Test tmux_capture function."""

    @patch("council.dispatcher.simple.subprocess.run")
    def test_capture_success(self, mock_run):
        """Successful capture returns output."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="line1\nline2\nline3\n",
        )
        result = tmux_capture("%0")
        assert result == "line1\nline2\nline3"

    @patch("council.dispatcher.simple.subprocess.run")
    def test_capture_failure_returns_none(self, mock_run):
        """Failed capture returns None."""
        mock_run.return_value = MagicMock(returncode=1)
        result = tmux_capture("%0")
        assert result is None

    @patch("council.dispatcher.simple.subprocess.run")
    def test_capture_limits_lines(self, mock_run):
        """Capture should return last N lines."""
        lines = "\n".join([f"line{i}" for i in range(100)])
        mock_run.return_value = MagicMock(returncode=0, stdout=lines)

        result = tmux_capture("%0", lines=10)
        result_lines = result.split("\n")
        assert len(result_lines) == 10

    @patch("council.dispatcher.simple.subprocess.run")
    def test_capture_timeout_returns_none(self, mock_run):
        """Timeout should return None."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired("tmux", 5)
        result = tmux_capture("%0")
        assert result is None

    @patch("council.dispatcher.simple.subprocess.run")
    def test_capture_command_not_found_returns_none(self, mock_run):
        """Missing tmux should return None."""
        mock_run.side_effect = FileNotFoundError()
        result = tmux_capture("%0")
        assert result is None

    @patch("council.dispatcher.simple.subprocess.run")
    def test_capture_uses_correct_command(self, mock_run):
        """Verify correct tmux command is called."""
        mock_run.return_value = MagicMock(returncode=0, stdout="test")
        tmux_capture("%5")

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "tmux"
        assert args[1] == "capture-pane"
        assert "-t" in args
        assert "%5" in args


class TestTmuxSend:
    """Test tmux_send function."""

    @patch("council.dispatcher.simple.subprocess.run")
    def test_send_success(self, mock_run):
        """Successful send returns True."""
        mock_run.return_value = MagicMock(returncode=0)
        result = tmux_send("%0", "hello")
        assert result is True

    @patch("council.dispatcher.simple.subprocess.run")
    def test_send_failure_returns_false(self, mock_run):
        """Failed send returns False."""
        mock_run.return_value = MagicMock(returncode=1)
        result = tmux_send("%0", "hello")
        assert result is False

    @patch("council.dispatcher.simple.subprocess.run")
    def test_send_calls_twice(self, mock_run):
        """Send should call tmux twice (text + Enter)."""
        mock_run.return_value = MagicMock(returncode=0)
        tmux_send("%0", "hello")

        assert mock_run.call_count == 2

    @patch("council.dispatcher.simple.subprocess.run")
    def test_send_uses_literal_flag(self, mock_run):
        """Send should use -l flag for literal text."""
        mock_run.return_value = MagicMock(returncode=0)
        tmux_send("%0", "hello")

        first_call = mock_run.call_args_list[0]
        args = first_call[0][0]
        assert "-l" in args

    @patch("council.dispatcher.simple.subprocess.run")
    def test_send_timeout_returns_false(self, mock_run):
        """Timeout should return False."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired("tmux", 5)
        result = tmux_send("%0", "hello")
        assert result is False


class TestTmuxPaneExists:
    """Test tmux_pane_exists function."""

    @patch("council.dispatcher.simple.subprocess.run")
    def test_pane_exists(self, mock_run):
        """Existing pane returns True."""
        mock_run.return_value = MagicMock(returncode=0)
        assert tmux_pane_exists("%0") is True

    @patch("council.dispatcher.simple.subprocess.run")
    def test_pane_not_exists(self, mock_run):
        """Non-existing pane returns False."""
        mock_run.return_value = MagicMock(returncode=1)
        assert tmux_pane_exists("%99") is False

    @patch("council.dispatcher.simple.subprocess.run")
    def test_pane_check_timeout(self, mock_run):
        """Timeout returns False."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired("tmux", 5)
        assert tmux_pane_exists("%0") is False


class TestTmuxPaneInCopyMode:
    """Test tmux_pane_in_copy_mode function."""

    @patch("council.dispatcher.simple.subprocess.run")
    def test_pane_in_copy_mode(self, mock_run):
        """Pane in copy mode returns True."""
        mock_run.return_value = MagicMock(returncode=0, stdout="1")
        assert tmux_pane_in_copy_mode("%0") is True

    @patch("council.dispatcher.simple.subprocess.run")
    def test_pane_not_in_copy_mode(self, mock_run):
        """Pane not in copy mode returns False."""
        mock_run.return_value = MagicMock(returncode=0, stdout="0")
        assert tmux_pane_in_copy_mode("%0") is False

    @patch("council.dispatcher.simple.subprocess.run")
    def test_pane_check_fails(self, mock_run):
        """Failed check returns False."""
        mock_run.return_value = MagicMock(returncode=1)
        assert tmux_pane_in_copy_mode("%0") is False
