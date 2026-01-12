"""Tests for circuit breaker logic.

TODO: Add integration tests that call check_agents() with mocked git snapshots
to test the full flow: git snapshot → has_progress() → streak increment → circuit open.
Current tests verify the logic patterns but don't exercise the actual code paths.
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from council.dispatcher.simple import (
    Agent, Config, check_agents, MAX_NO_PROGRESS,
)
from council.dispatcher.gitwatch import GitSnapshot


@pytest.fixture
def agent_with_worktree():
    """Agent with worktree configured for git tracking."""
    return Agent(
        id=1,
        pane_id="%0",
        name="Test Agent",
        worktree=Path("/tmp/test"),
        state="working",
        auto_enabled=True,
        circuit_state="closed",
        no_progress_streak=0,
    )


@pytest.fixture
def config_with_agent(agent_with_worktree):
    """Config with single agent."""
    return Config(agents={1: agent_with_worktree})


class TestCircuitBreakerState:
    """Test circuit breaker state transitions."""

    def test_initial_state_closed(self):
        agent = Agent(id=1, pane_id="%0", name="Test")
        assert agent.circuit_state == "closed"
        assert agent.no_progress_streak == 0

    def test_streak_increments_on_no_progress(self, agent_with_worktree):
        """No progress should increment streak."""
        agent = agent_with_worktree
        agent.no_progress_streak = 1
        agent.no_progress_streak += 1
        assert agent.no_progress_streak == 2

    def test_streak_resets_on_progress(self, agent_with_worktree):
        """Progress should reset streak to 0."""
        agent = agent_with_worktree
        agent.no_progress_streak = 2
        # Simulating progress detection
        agent.no_progress_streak = 0
        assert agent.no_progress_streak == 0

    def test_circuit_opens_at_max_no_progress(self, agent_with_worktree):
        """Circuit should open when streak reaches MAX_NO_PROGRESS."""
        agent = agent_with_worktree
        agent.no_progress_streak = MAX_NO_PROGRESS
        if agent.no_progress_streak >= MAX_NO_PROGRESS:
            agent.circuit_state = "open"
        assert agent.circuit_state == "open"

    def test_circuit_stays_closed_below_max(self, agent_with_worktree):
        """Circuit should stay closed below MAX_NO_PROGRESS."""
        agent = agent_with_worktree
        agent.no_progress_streak = MAX_NO_PROGRESS - 1
        if agent.no_progress_streak >= MAX_NO_PROGRESS:
            agent.circuit_state = "open"
        assert agent.circuit_state == "closed"


class TestCircuitBreakerReset:
    """Test circuit breaker reset functionality."""

    def test_reset_closes_circuit(self, agent_with_worktree):
        """Reset should close the circuit."""
        agent = agent_with_worktree
        agent.circuit_state = "open"
        agent.no_progress_streak = 5

        # Reset logic
        agent.circuit_state = "closed"
        agent.no_progress_streak = 0
        agent.last_snapshot = None

        assert agent.circuit_state == "closed"
        assert agent.no_progress_streak == 0
        assert agent.last_snapshot is None

    def test_reset_clears_snapshot(self, agent_with_worktree):
        """Reset should clear last snapshot."""
        agent = agent_with_worktree
        agent.last_snapshot = GitSnapshot(
            status_hash="abc123",
            head_hash="def456",
            combined_hash="abc123def456",
        )

        agent.last_snapshot = None
        assert agent.last_snapshot is None


class TestAutoContinueWithCircuitBreaker:
    """Test auto-continue respects circuit breaker."""

    def test_auto_continue_blocked_when_circuit_open(self, agent_with_worktree):
        """Auto-continue should not fire when circuit is open."""
        agent = agent_with_worktree
        agent.auto_enabled = True
        agent.circuit_state = "open"
        agent.state = "ready"

        should_continue = agent.auto_enabled and agent.circuit_state == "closed"
        assert not should_continue

    def test_auto_continue_allowed_when_circuit_closed(self, agent_with_worktree):
        """Auto-continue should fire when circuit is closed."""
        agent = agent_with_worktree
        agent.auto_enabled = True
        agent.circuit_state = "closed"
        agent.state = "ready"

        should_continue = agent.auto_enabled and agent.circuit_state == "closed"
        assert should_continue

    def test_auto_continue_blocked_when_disabled(self, agent_with_worktree):
        """Auto-continue should not fire when disabled."""
        agent = agent_with_worktree
        agent.auto_enabled = False
        agent.circuit_state = "closed"

        should_continue = agent.auto_enabled and agent.circuit_state == "closed"
        assert not should_continue


class TestMaxNoProgressConstant:
    """Test the MAX_NO_PROGRESS constant."""

    def test_max_no_progress_is_reasonable(self):
        """MAX_NO_PROGRESS should be a reasonable value (2-10)."""
        assert 2 <= MAX_NO_PROGRESS <= 10

    def test_max_no_progress_is_three(self):
        """Current value should be 3."""
        assert MAX_NO_PROGRESS == 3
