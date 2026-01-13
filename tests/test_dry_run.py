"""Tests for --dry-run mode."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import io
import sys

from council.dispatcher.simple import (
    send_to_agent, Config, Agent, parse_args
)


def make_config(dry_run: bool = False) -> Config:
    """Create a Config with given dry_run setting."""
    return Config(agents={}, dry_run=dry_run)


def make_agent(agent_id: int = 1) -> Agent:
    """Create a test Agent."""
    return Agent(id=agent_id, pane_id=f"%{agent_id}", name=f"Agent {agent_id}")


class TestSendToAgent:
    """Test send_to_agent function."""

    @patch("council.dispatcher.simple.tmux_send")
    def test_normal_mode_calls_tmux_send(self, mock_tmux_send):
        """In normal mode, tmux_send is called."""
        mock_tmux_send.return_value = True
        config = make_config(dry_run=False)
        agent = make_agent()

        result = send_to_agent(agent, "hello", config)

        assert result is True
        mock_tmux_send.assert_called_once_with("%1", "hello")

    @patch("council.dispatcher.simple.tmux_send")
    def test_dry_run_mode_skips_tmux_send(self, mock_tmux_send):
        """In dry-run mode, tmux_send is NOT called."""
        config = make_config(dry_run=True)
        agent = make_agent()

        result = send_to_agent(agent, "hello", config)

        assert result is True
        mock_tmux_send.assert_not_called()

    @patch("council.dispatcher.simple.tmux_send")
    def test_dry_run_mode_prints_message(self, mock_tmux_send, capsys):
        """In dry-run mode, prints what would be sent."""
        config = make_config(dry_run=True)
        agent = make_agent()

        send_to_agent(agent, "hello world", config)

        captured = capsys.readouterr()
        assert "[DRY-RUN]" in captured.out
        assert "Agent 1" in captured.out
        assert "hello world" in captured.out

    @patch("council.dispatcher.simple.tmux_send")
    def test_dry_run_truncates_long_messages(self, mock_tmux_send, capsys):
        """In dry-run mode, long messages are truncated."""
        config = make_config(dry_run=True)
        agent = make_agent()
        long_msg = "x" * 200

        send_to_agent(agent, long_msg, config)

        captured = capsys.readouterr()
        assert "..." in captured.out
        # Should only show first 80 chars
        assert "x" * 80 in captured.out
        assert "x" * 200 not in captured.out


class TestParseArgs:
    """Test parse_args function."""

    def test_default_config_path(self):
        """Default config path is ~/.council/config.yaml."""
        with patch.object(sys, 'argv', ['dispatcher']):
            config_path, dry_run = parse_args()
            assert config_path == Path.home() / ".council" / "config.yaml"
            assert dry_run is False

    def test_custom_config_path(self):
        """Custom config path is accepted."""
        with patch.object(sys, 'argv', ['dispatcher', '/custom/config.yaml']):
            config_path, dry_run = parse_args()
            assert config_path == Path("/custom/config.yaml")
            assert dry_run is False

    def test_dry_run_flag(self):
        """--dry-run flag sets dry_run to True."""
        with patch.object(sys, 'argv', ['dispatcher', '--dry-run']):
            config_path, dry_run = parse_args()
            assert dry_run is True

    def test_dry_run_with_custom_config(self):
        """--dry-run works with custom config path."""
        with patch.object(sys, 'argv', ['dispatcher', '/custom/config.yaml', '--dry-run']):
            config_path, dry_run = parse_args()
            assert config_path == Path("/custom/config.yaml")
            assert dry_run is True

    def test_dry_run_before_config(self):
        """--dry-run can come before config path."""
        with patch.object(sys, 'argv', ['dispatcher', '--dry-run', '/custom/config.yaml']):
            config_path, dry_run = parse_args()
            assert config_path == Path("/custom/config.yaml")
            assert dry_run is True
