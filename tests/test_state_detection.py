"""Tests for agent state detection."""

import pytest
from council.dispatcher.simple import detect_state


class TestDetectState:
    """Test detect_state function."""

    def test_empty_output_returns_unknown(self):
        assert detect_state("") == "unknown"
        assert detect_state(None) == "unknown"

    def test_ready_prompt_detected(self):
        """Claude's ready prompt starts with ❯"""
        output = """
Some previous output
❯
"""
        assert detect_state(output) == "ready"

    def test_ready_shortcuts_hint_detected(self):
        """Alternative ready indicator."""
        output = """
  ? for shortcuts
"""
        assert detect_state(output) == "ready"

    def test_dialog_numbered_options(self):
        """Dialog with numbered options."""
        output = """
❯ 1. Option one
  2. Option two
  3. Option three
"""
        assert detect_state(output) == "dialog"

    def test_dialog_do_you_want(self):
        """Dialog asking for confirmation."""
        output = """
Do you want to proceed?
"""
        assert detect_state(output) == "dialog"

    def test_dialog_esc_to_cancel(self):
        """Dialog with escape hint."""
        output = """
Select an option (Esc to cancel)
"""
        assert detect_state(output) == "dialog"

    def test_working_state(self):
        """No ready or dialog patterns means working."""
        output = """
Thinking about the problem...
Let me analyze this code...
"""
        assert detect_state(output) == "working"

    def test_dialog_takes_precedence_over_ready(self):
        """Dialog patterns should match before ready patterns."""
        output = """
❯ 1. Yes
  2. No
"""
        assert detect_state(output) == "dialog"

    def test_real_world_ready_output(self):
        """Test with realistic Claude ready output."""
        output = """
I've completed the changes.

❯
"""
        assert detect_state(output) == "ready"

    def test_real_world_working_output(self):
        """Test with realistic Claude working output."""
        output = """
Let me read the file first...

Reading /path/to/file.py...
"""
        assert detect_state(output) == "working"
