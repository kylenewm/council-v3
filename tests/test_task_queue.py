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

    def test_queue_populated_on_pipe_command(self):
        """Pipe command should populate queue."""
        agent = Agent(id=1, pane_id="%0", name="Test", state="ready")
        config = Config(agents={1: agent})

        with patch("council.dispatcher.simple.tmux_send", return_value=True):
            with patch("council.dispatcher.simple.tmux_pane_in_copy_mode", return_value=False):
                with patch("council.dispatcher.simple.save_state"):
                    process_line("1: task1 | task2 | task3", config)

        assert agent.task_queue == ["task2", "task3"]

    def test_first_task_sent_immediately(self):
        """First task should be sent immediately."""
        agent = Agent(id=1, pane_id="%0", name="Test", state="ready")
        config = Config(agents={1: agent})

        with patch("council.dispatcher.simple.tmux_send", return_value=True) as mock_send:
            with patch("council.dispatcher.simple.tmux_pane_in_copy_mode", return_value=False):
                with patch("council.dispatcher.simple.save_state"):
                    process_line("1: task1 | task2", config)

        mock_send.assert_called_with("%0", "task1")

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
            assert state["version"] == 2

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

    def test_empty_tasks_filtered(self):
        """Empty tasks between pipes are filtered."""
        agent = Agent(id=1, pane_id="%0", name="Test", state="ready")
        config = Config(agents={1: agent})

        with patch("council.dispatcher.simple.tmux_send", return_value=True):
            with patch("council.dispatcher.simple.tmux_pane_in_copy_mode", return_value=False):
                with patch("council.dispatcher.simple.save_state"):
                    process_line("1: task1 |  | task2", config)

        assert agent.task_queue == ["task2"]

    def test_whitespace_trimmed(self):
        """Whitespace around tasks is trimmed."""
        agent = Agent(id=1, pane_id="%0", name="Test", state="ready")
        config = Config(agents={1: agent})

        with patch("council.dispatcher.simple.tmux_send", return_value=True):
            with patch("council.dispatcher.simple.tmux_pane_in_copy_mode", return_value=False):
                with patch("council.dispatcher.simple.save_state"):
                    process_line("1:   task1  |  task2  ", config)

        assert agent.task_queue == ["task2"]

    def test_queue_survives_failed_send(self):
        """Queue not modified if send fails."""
        agent = Agent(id=1, pane_id="%0", name="Test", state="ready")
        config = Config(agents={1: agent})

        with patch("council.dispatcher.simple.tmux_send", return_value=False):
            with patch("council.dispatcher.simple.tmux_pane_in_copy_mode", return_value=False):
                process_line("1: task1 | task2", config)

        # Queue should not be populated since first task failed
        assert agent.task_queue == []

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

    def test_empty_pipe_command(self, capsys):
        """Empty pipes should be handled gracefully."""
        agent = Agent(id=1, pane_id="%0", name="Test", state="ready")
        config = Config(agents={1: agent})

        with patch("council.dispatcher.simple.tmux_pane_in_copy_mode", return_value=False):
            result = process_line("1: | | ", config)

        assert result is True  # Should not crash
        out = capsys.readouterr().out
        assert "No valid tasks" in out

    def test_only_whitespace_tasks(self, capsys):
        """Tasks that are only whitespace should be filtered."""
        agent = Agent(id=1, pane_id="%0", name="Test", state="ready")
        config = Config(agents={1: agent})

        with patch("council.dispatcher.simple.tmux_pane_in_copy_mode", return_value=False):
            result = process_line("1:    |   |   ", config)

        assert result is True
        out = capsys.readouterr().out
        assert "No valid tasks" in out

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
