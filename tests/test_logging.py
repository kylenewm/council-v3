"""Tests for JSONL logging."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime
import tempfile
import os

from council.dispatcher.simple import (
    log_event, get_log_file, LOG_DIR, _run_id
)


class TestGetLogFile:
    """Test get_log_file function."""

    def test_returns_correct_path(self):
        """Returns path in LOG_DIR with date format."""
        log_file = get_log_file()
        assert log_file.parent == LOG_DIR
        # Should match YYYY-MM-DD.jsonl format
        assert log_file.suffix == ".jsonl"
        today = datetime.now().strftime("%Y-%m-%d")
        assert today in str(log_file.name)


class TestLogEvent:
    """Test log_event function."""

    def test_creates_log_entry(self, tmp_path):
        """Creates log entry with correct schema."""
        with patch("council.dispatcher.simple.LOG_DIR", tmp_path):
            log_event(1, "send", "%0", result="ok")

            # Find the log file
            log_files = list(tmp_path.glob("*.jsonl"))
            assert len(log_files) == 1

            # Read and verify
            with open(log_files[0]) as f:
                entry = json.loads(f.readline())

            assert entry["agent_id"] == 1
            assert entry["cmd_type"] == "send"
            assert entry["pane_id"] == "%0"
            assert entry["result"] == "ok"
            assert entry["error"] is None
            assert "ts" in entry
            assert "run_id" in entry

    def test_logs_error(self, tmp_path):
        """Logs error field correctly."""
        with patch("council.dispatcher.simple.LOG_DIR", tmp_path):
            log_event(1, "send", "%0", result="fail", error="tmux_send failed")

            log_files = list(tmp_path.glob("*.jsonl"))
            with open(log_files[0]) as f:
                entry = json.loads(f.readline())

            assert entry["result"] == "fail"
            assert entry["error"] == "tmux_send failed"

    def test_logs_extra_fields(self, tmp_path):
        """Logs extra fields."""
        with patch("council.dispatcher.simple.LOG_DIR", tmp_path):
            log_event(1, "circuit_open", "%0", extra={"streak": 3})

            log_files = list(tmp_path.glob("*.jsonl"))
            with open(log_files[0]) as f:
                entry = json.loads(f.readline())

            assert entry["streak"] == 3

    def test_appends_to_existing_file(self, tmp_path):
        """Appends to existing log file."""
        with patch("council.dispatcher.simple.LOG_DIR", tmp_path):
            log_event(1, "send", "%0")
            log_event(2, "send", "%1")

            log_files = list(tmp_path.glob("*.jsonl"))
            assert len(log_files) == 1

            with open(log_files[0]) as f:
                lines = f.readlines()

            assert len(lines) == 2
            assert json.loads(lines[0])["agent_id"] == 1
            assert json.loads(lines[1])["agent_id"] == 2

    def test_creates_log_directory(self, tmp_path):
        """Creates log directory if missing."""
        log_dir = tmp_path / "subdir" / "logs"
        with patch("council.dispatcher.simple.LOG_DIR", log_dir):
            log_event(1, "send", "%0")

            assert log_dir.exists()
            log_files = list(log_dir.glob("*.jsonl"))
            assert len(log_files) == 1

    def test_handles_none_agent_id(self, tmp_path):
        """Handles None agent_id (e.g., for startup)."""
        with patch("council.dispatcher.simple.LOG_DIR", tmp_path):
            log_event(None, "startup", extra={"agents": 2})

            log_files = list(tmp_path.glob("*.jsonl"))
            with open(log_files[0]) as f:
                entry = json.loads(f.readline())

            assert entry["agent_id"] is None
            assert entry["cmd_type"] == "startup"
            assert entry["agents"] == 2

    def test_timestamp_is_iso_format(self, tmp_path):
        """Timestamp is in ISO format."""
        with patch("council.dispatcher.simple.LOG_DIR", tmp_path):
            log_event(1, "send", "%0")

            log_files = list(tmp_path.glob("*.jsonl"))
            with open(log_files[0]) as f:
                entry = json.loads(f.readline())

            # Should be parseable as ISO datetime
            ts = entry["ts"]
            datetime.fromisoformat(ts)  # Raises if invalid

    def test_run_id_is_consistent(self, tmp_path):
        """Run ID is consistent across calls."""
        with patch("council.dispatcher.simple.LOG_DIR", tmp_path):
            log_event(1, "send", "%0")
            log_event(2, "send", "%1")

            log_files = list(tmp_path.glob("*.jsonl"))
            with open(log_files[0]) as f:
                entry1 = json.loads(f.readline())
                entry2 = json.loads(f.readline())

            assert entry1["run_id"] == entry2["run_id"]
            assert len(entry1["run_id"]) == 8  # Short UUID
