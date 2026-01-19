"""Tests for notification trigger conditions.

These tests verify when notifications should and should not fire
based on state transitions and timing guards.
"""

import pytest
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

from council.dispatcher.simple import (
    Agent, Config, check_agents,
    READY_NOTIFY_DELAY, NOTIFY_COOLDOWN,
)


@pytest.fixture
def mock_agent():
    """Create a mock agent for testing."""
    return Agent(
        id=1,
        pane_id="%0",
        name="TestAgent",
        worktree=None,  # No git tracking
        state="unknown",
        last_command_sent=0,
        last_notify=0,
    )


@pytest.fixture
def mock_config(mock_agent):
    """Create a mock config for testing."""
    return Config(
        agents={1: mock_agent},
        poll_interval=2.0,
    )


class TestNotificationTransitions:
    """Tests for which state transitions trigger notifications."""

    @patch("council.dispatcher.simple.tmux_capture")
    @patch("council.dispatcher.simple.notify_agent_ready")
    def test_working_to_ready_triggers_notification(
        self, mock_notify, mock_capture, mock_config
    ):
        """working→ready should trigger notification (after delay)."""
        agent = mock_config.agents[1]
        agent.state = "working"
        agent.last_command_sent = time.time() - READY_NOTIFY_DELAY - 1
        agent.last_notify = time.time() - NOTIFY_COOLDOWN - 1

        # Simulate ready state
        mock_capture.return_value = "❯"

        check_agents(mock_config)

        mock_notify.assert_called_once()

    @patch("council.dispatcher.simple.tmux_capture")
    @patch("council.dispatcher.simple.notify_agent_ready")
    def test_unknown_to_ready_no_notification(
        self, mock_notify, mock_capture, mock_config
    ):
        """unknown→ready should NOT trigger notification."""
        agent = mock_config.agents[1]
        agent.state = "unknown"
        agent.last_command_sent = time.time() - READY_NOTIFY_DELAY - 1
        agent.last_notify = time.time() - NOTIFY_COOLDOWN - 1

        # Simulate ready state
        mock_capture.return_value = "❯"

        check_agents(mock_config)

        mock_notify.assert_not_called()

    @patch("council.dispatcher.simple.tmux_capture")
    @patch("council.dispatcher.simple.notify_agent_ready")
    def test_dialog_to_ready_no_notification(
        self, mock_notify, mock_capture, mock_config
    ):
        """dialog→ready should NOT trigger notification."""
        agent = mock_config.agents[1]
        agent.state = "dialog"
        agent.last_command_sent = time.time() - READY_NOTIFY_DELAY - 1
        agent.last_notify = time.time() - NOTIFY_COOLDOWN - 1

        # Simulate ready state
        mock_capture.return_value = "❯"

        check_agents(mock_config)

        mock_notify.assert_not_called()

    @patch("council.dispatcher.simple.tmux_capture")
    @patch("council.dispatcher.simple.notify_agent_ready")
    def test_ready_to_ready_no_notification(
        self, mock_notify, mock_capture, mock_config
    ):
        """ready→ready (no change) should NOT trigger notification."""
        agent = mock_config.agents[1]
        agent.state = "ready"
        agent.last_command_sent = time.time() - READY_NOTIFY_DELAY - 1
        agent.last_notify = time.time() - NOTIFY_COOLDOWN - 1

        # Simulate ready state (same as current)
        mock_capture.return_value = "❯"

        check_agents(mock_config)

        mock_notify.assert_not_called()


class TestNotificationGuards:
    """Tests for notification timing guards."""

    @patch("council.dispatcher.simple.tmux_capture")
    @patch("council.dispatcher.simple.notify_agent_ready")
    def test_notification_skipped_if_command_too_recent(
        self, mock_notify, mock_capture, mock_config
    ):
        """Notification should be skipped if command sent < 10s ago."""
        agent = mock_config.agents[1]
        agent.state = "working"
        agent.last_command_sent = time.time() - 2  # Only 2 seconds ago
        agent.last_notify = time.time() - NOTIFY_COOLDOWN - 1

        mock_capture.return_value = "❯"

        changes = check_agents(mock_config)

        mock_notify.assert_not_called()
        assert any("wait" in c.lower() for c in changes)

    @patch("council.dispatcher.simple.tmux_capture")
    @patch("council.dispatcher.simple.notify_agent_ready")
    def test_notification_skipped_if_cooldown_active(
        self, mock_notify, mock_capture, mock_config
    ):
        """Notification should be skipped if last notify < 30s ago."""
        agent = mock_config.agents[1]
        agent.state = "working"
        agent.last_command_sent = time.time() - READY_NOTIFY_DELAY - 1
        agent.last_notify = time.time() - 10  # Only 10 seconds ago

        mock_capture.return_value = "❯"

        changes = check_agents(mock_config)

        mock_notify.assert_not_called()
        assert any("cooldown" in c.lower() for c in changes)

    @patch("council.dispatcher.simple.tmux_capture")
    @patch("council.dispatcher.simple.notify_agent_ready")
    def test_notification_sent_when_both_guards_pass(
        self, mock_notify, mock_capture, mock_config
    ):
        """Notification should fire when both time guards are satisfied."""
        agent = mock_config.agents[1]
        agent.state = "working"
        agent.last_command_sent = time.time() - READY_NOTIFY_DELAY - 1
        agent.last_notify = time.time() - NOTIFY_COOLDOWN - 1

        mock_capture.return_value = "❯"

        changes = check_agents(mock_config)

        mock_notify.assert_called_once()
        assert any("notification sent" in c.lower() for c in changes)


class TestNotificationCooldown:
    """Tests for notification cooldown behavior."""

    @patch("council.dispatcher.simple.tmux_capture")
    @patch("council.dispatcher.simple.notify_agent_ready")
    def test_rapid_transitions_single_notification(
        self, mock_notify, mock_capture, mock_config
    ):
        """Rapid working→ready transitions should only send one notification."""
        agent = mock_config.agents[1]
        agent.last_command_sent = time.time() - READY_NOTIFY_DELAY - 1
        agent.last_notify = time.time() - NOTIFY_COOLDOWN - 1

        # First transition: working → ready
        agent.state = "working"
        mock_capture.return_value = "❯"
        check_agents(mock_config)

        # Should have notified
        assert mock_notify.call_count == 1

        # Simulate quick working → ready again (within cooldown)
        agent.state = "working"
        mock_capture.return_value = "❯"
        check_agents(mock_config)

        # Should NOT have notified again (cooldown)
        assert mock_notify.call_count == 1
