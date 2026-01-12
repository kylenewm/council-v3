"""Shared fixtures for dispatcher tests."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from council.dispatcher.simple import Agent, Config


@pytest.fixture
def sample_agent():
    """Create a sample agent for testing."""
    return Agent(
        id=1,
        pane_id="%0",
        name="Test Agent",
        worktree=Path("/tmp/test-worktree"),
        state="unknown",
    )


@pytest.fixture
def sample_config(sample_agent):
    """Create a sample config for testing."""
    return Config(
        agents={1: sample_agent},
        poll_interval=2.0,
        fifo_path=Path("/tmp/test.fifo"),
    )


@pytest.fixture
def multi_agent_config():
    """Config with multiple agents."""
    return Config(
        agents={
            1: Agent(id=1, pane_id="%0", name="Agent 1"),
            2: Agent(id=2, pane_id="%1", name="Agent 2"),
            3: Agent(id=3, pane_id="%2", name="Agent 3"),
        },
        poll_interval=2.0,
    )


@pytest.fixture
def mock_subprocess():
    """Mock subprocess.run for tmux commands."""
    with patch("council.dispatcher.simple.subprocess.run") as mock:
        mock.return_value = MagicMock(returncode=0, stdout="", stderr="")
        yield mock
