"""Tests for task queue functionality."""

import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from council.dispatcher.simple import (
    Agent, Config, parse_command, process_line, check_agents,
    save_state, load_state, show_status,
)


class TestTaskQueueParsing:
    """Test pipe-separated task parsing."""

    def test_single_task_no_pipe(self):
        """Single task works as before."""
        agent_id, cmd = parse_command("1: do something")
        assert agent_id == 1
        assert cmd == "do something"
        assert "|" not in cmd

    def test_pipe_preserved_in_command(self):
        """Pipes are preserved in command string for later splitting."""
        agent_id, cmd = parse_command("1: task1 | task2 | task3")
        assert agent_id == 1
        assert cmd == "task1 | task2 | task3"

    def test_queue_command(self):
        """Queue command parsed correctly."""
        assert parse_command("queue 1") == (1, "queue")
        assert parse_command("QUEUE 2") == (2, "queue")
        assert parse_command("Queue 3") == (3, "queue")

    def test_clear_command(self):
        """Clear command parsed correctly."""
        assert parse_command("clear 1") == (1, "clear")
        assert parse_command("CLEAR 3") == (3, "clear")
        assert parse_command("Clear 2") == (2, "clear")

    def test_queue_without_agent_id(self):
        """Queue without agent ID returns None."""
        assert parse_command("queue") == (None, None)

    def test_clear_without_agent_id(self):
        """Clear without agent ID returns None."""
        assert parse_command("clear") == (None, None)


class TestTaskQueueExecution:
    """Test task queue execution flow."""

    @pytest.fixture
    def agent_ready(self):
        return Agent(
            id=1, pane_id="%0", name="Test",
            state="ready", task_queue=["task2", "task3"],
        )

    @pytest.fixture
    def config_with_queue(self, agent_ready):
        return Config(agents={1: agent_ready})

    def test_queue_add_command(self):
        """queue N 'task' should add task to queue."""
        agent = Agent(id=1, pane_id="%0", name="Test", state="ready")
        config = Config(agents={1: agent})

        with patch("council.dispatcher.simple.save_state"):
            process_line('queue 1 "task to queue"', config)

        assert agent.task_queue == ["task to queue"]

    def test_command_with_pipe_sent_literally(self):
        """Command containing pipe characters should be sent literally (no splitting)."""
        agent = Agent(id=1, pane_id="%0", name="Test", state="ready")
        config = Config(agents={1: agent})

        with patch("council.dispatcher.simple.tmux_send", return_value=True) as mock_send:
            with patch("council.dispatcher.simple.tmux_pane_in_copy_mode", return_value=False):
                process_line("1: grep 'foo|bar' file.txt", config)

        # Entire command with pipe should be sent (not split)
        mock_send.assert_called_with("%0", "grep 'foo|bar' file.txt")

    def test_single_task_no_queue(self):
        """Single task should not populate queue."""
        agent = Agent(id=1, pane_id="%0", name="Test", state="ready")
        config = Config(agents={1: agent})

        with patch("council.dispatcher.simple.tmux_send", return_value=True):
            with patch("council.dispatcher.simple.tmux_pane_in_copy_mode", return_value=False):
                process_line("1: just one task", config)

        assert agent.task_queue == []

    def test_dequeue_on_ready(self, config_with_queue):
        """Task dequeued when agent becomes ready."""
        agent = config_with_queue.agents[1]
        agent.state = "working"  # Start working

        with patch("council.dispatcher.simple.tmux_capture", return_value="some output\n❯"):
            with patch("council.dispatcher.simple.tmux_send", return_value=True) as mock_send:
                with patch("council.dispatcher.simple.save_state"):
                    with patch("council.dispatcher.simple.write_current_task"):
                        check_agents(config_with_queue)

        mock_send.assert_called_with("%0", "task2")
        assert agent.task_queue == ["task3"]

    def test_dequeue_blocked_by_circuit(self, config_with_queue):
        """Queue blocked when circuit open."""
        agent = config_with_queue.agents[1]
        agent.state = "working"
        agent.circuit_state = "open"

        with patch("council.dispatcher.simple.tmux_capture", return_value="some output\n❯"):
            with patch("council.dispatcher.simple.tmux_send", return_value=True) as mock_send:
                check_agents(config_with_queue)

        mock_send.assert_not_called()
        assert agent.task_queue == ["task2", "task3"]

    def test_queue_priority_over_auto_continue(self, config_with_queue):
        """Queue takes priority over auto-continue."""
        agent = config_with_queue.agents[1]
        agent.state = "working"
        agent.auto_enabled = True

        with patch("council.dispatcher.simple.tmux_capture", return_value="some output\n❯"):
            with patch("council.dispatcher.simple.tmux_send", return_value=True) as mock_send:
                with patch("council.dispatcher.simple.save_state"):
                    with patch("council.dispatcher.simple.write_current_task"):
                        check_agents(config_with_queue)

        # Should send queued task, not "continue"
        mock_send.assert_called_with("%0", "task2")


class TestTaskQueuePersistence:
    """Test queue persistence."""

    def test_queue_saved_to_state(self, tmp_path):
        """Queue should be saved to state file."""
        agent = Agent(id=1, pane_id="%0", name="Test", task_queue=["a", "b"])
        config = Config(agents={1: agent})

        with patch("council.dispatcher.simple.STATE_FILE", tmp_path / "state.json"):
            save_state(config)

            state = json.loads((tmp_path / "state.json").read_text())
            assert state["agents"]["1"]["task_queue"] == ["a", "b"]
            assert state["version"] == 3

    def test_queue_restored_from_state(self, tmp_path):
        """Queue should be restored from state file."""
        state = {
            "version": 2,
            "agents": {"1": {"task_queue": ["x", "y"], "auto_enabled": False}}
        }
        (tmp_path / "state.json").write_text(json.dumps(state))

        agent = Agent(id=1, pane_id="%0", name="Test")
        config = Config(agents={1: agent})

        with patch("council.dispatcher.simple.STATE_FILE", tmp_path / "state.json"):
            load_state(config)

        assert agent.task_queue == ["x", "y"]

    def test_missing_queue_defaults_empty(self, tmp_path):
        """Missing queue in state defaults to empty list."""
        state = {"version": 1, "agents": {"1": {"auto_enabled": False}}}
        (tmp_path / "state.json").write_text(json.dumps(state))

        agent = Agent(id=1, pane_id="%0", name="Test")
        config = Config(agents={1: agent})

        with patch("council.dispatcher.simple.STATE_FILE", tmp_path / "state.json"):
            load_state(config)

        assert agent.task_queue == []


class TestTaskQueueCommands:
    """Test queue management commands."""

    def test_queue_display(self, capsys):
        """Queue command shows tasks."""
        agent = Agent(id=1, pane_id="%0", name="Test", task_queue=["a", "b"])
        config = Config(agents={1: agent})

        process_line("queue 1", config)

        out = capsys.readouterr().out
        assert "2 tasks" in out
        assert "a" in out
        assert "b" in out

    def test_queue_empty(self, capsys):
        """Queue command shows empty message."""
        agent = Agent(id=1, pane_id="%0", name="Test", task_queue=[])
        config = Config(agents={1: agent})

        process_line("queue 1", config)

        out = capsys.readouterr().out
        assert "empty" in out

    def test_clear_queue(self):
        """Clear command empties queue."""
        agent = Agent(id=1, pane_id="%0", name="Test", task_queue=["a", "b"])
        config = Config(agents={1: agent})

        with patch("council.dispatcher.simple.save_state"):
            process_line("clear 1", config)

        assert agent.task_queue == []

    def test_clear_queue_output(self, capsys):
        """Clear command shows count."""
        agent = Agent(id=1, pane_id="%0", name="Test", task_queue=["a", "b", "c"])
        config = Config(agents={1: agent})

        with patch("council.dispatcher.simple.save_state"):
            process_line("clear 1", config)

        out = capsys.readouterr().out
        assert "cleared 3" in out


class TestTaskQueueStatus:
    """Test queue display in status."""

    def test_status_shows_queue_depth(self, capsys):
        """Status should show queue depth."""
        agent = Agent(id=1, pane_id="%0", name="Test", state="working", task_queue=["a", "b"])
        config = Config(agents={1: agent})

        show_status(config)

        out = capsys.readouterr().out
        assert "Q:2" in out

    def test_status_no_queue_indicator_when_empty(self, capsys):
        """Status should not show Q: when queue empty."""
        agent = Agent(id=1, pane_id="%0", name="Test", state="ready", task_queue=[])
        config = Config(agents={1: agent})

        show_status(config)

        out = capsys.readouterr().out
        assert "Q:" not in out


class TestTaskQueueEdgeCases:
    """Test edge cases."""

    def test_queue_add_single_quotes(self):
        """queue N 'task' should work with single quotes."""
        agent = Agent(id=1, pane_id="%0", name="Test", state="ready")
        config = Config(agents={1: agent})

        with patch("council.dispatcher.simple.save_state"):
            process_line("queue 1 'another task'", config)

        assert agent.task_queue == ["another task"]

    def test_queue_add_multiple(self):
        """Multiple queue commands should accumulate tasks."""
        agent = Agent(id=1, pane_id="%0", name="Test", state="ready")
        config = Config(agents={1: agent})

        with patch("council.dispatcher.simple.save_state"):
            process_line('queue 1 "task1"', config)
            process_line('queue 1 "task2"', config)

        assert agent.task_queue == ["task1", "task2"]

    def test_queue_add_preserves_pipes_in_task(self):
        """queue N 'task with | pipe' should preserve pipes in task text."""
        agent = Agent(id=1, pane_id="%0", name="Test", state="ready")
        config = Config(agents={1: agent})

        with patch("council.dispatcher.simple.save_state"):
            process_line('queue 1 "grep foo|bar file.txt"', config)

        assert agent.task_queue == ["grep foo|bar file.txt"]

    def test_dequeue_failure_keeps_task(self):
        """Task stays in queue if dequeue send fails."""
        agent = Agent(
            id=1, pane_id="%0", name="Test",
            state="working", task_queue=["task2", "task3"],
        )
        config = Config(agents={1: agent})

        with patch("council.dispatcher.simple.tmux_capture", return_value="some output\n❯"):
            with patch("council.dispatcher.simple.tmux_send", return_value=False):
                check_agents(config)

        # Task should still be in queue since send failed
        assert agent.task_queue == ["task2", "task3"]

    def test_progress_mark_command(self, capsys):
        """progress N mark should reset streak and mark progress."""
        agent = Agent(id=1, pane_id="%0", name="Test", state="ready", no_progress_streak=2)
        config = Config(agents={1: agent})

        with patch("council.dispatcher.simple.save_state"):
            with patch("council.dispatcher.simple.log_event"):
                process_line("progress 1 mark", config)

        assert agent.no_progress_streak == 0
        out = capsys.readouterr().out
        assert "progress marked" in out

    def test_progress_mark_unknown_agent(self, capsys):
        """progress N mark with unknown agent shows error."""
        config = Config(agents={})

        process_line("progress 99 mark", config)

        out = capsys.readouterr().out
        assert "Unknown agent" in out

    def test_unknown_agent_queue(self, capsys):
        """Queue command with unknown agent shows error."""
        config = Config(agents={})

        process_line("queue 99", config)

        out = capsys.readouterr().out
        assert "Unknown agent" in out

    def test_unknown_agent_clear(self, capsys):
        """Clear command with unknown agent shows error."""
        config = Config(agents={})

        process_line("clear 99", config)

        out = capsys.readouterr().out
        assert "Unknown agent" in out

    def test_long_task_truncated_in_queue_display(self, capsys):
        """Long tasks should be truncated in queue display."""
        long_task = "x" * 100
        agent = Agent(id=1, pane_id="%0", name="Test", task_queue=[long_task])
        config = Config(agents={1: agent})

        process_line("queue 1", config)

        out = capsys.readouterr().out
        assert "..." in out
        # Should show first 60 chars
        assert "x" * 60 in out
