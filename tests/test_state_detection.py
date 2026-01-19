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


class TestDetectStuckThinking:
    """Tests for stuck thinking detection."""

    def test_stuck_thinking_detected(self):
        """Should detect thinking duration from output."""
        from council.dispatcher.simple import detect_stuck_thinking
        output = "(5m 23s · thinking)"
        duration = detect_stuck_thinking(output)
        assert duration is not None
        assert duration == 5 * 60  # 5 minutes = 300 seconds

    def test_no_thinking_returns_none(self):
        """Should return None if no thinking indicator."""
        from council.dispatcher.simple import detect_stuck_thinking
        output = "Some normal output\n❯"
        assert detect_stuck_thinking(output) is None

    def test_thinking_pattern_variations(self):
        """Should handle various thinking patterns."""
        from council.dispatcher.simple import detect_stuck_thinking
        assert detect_stuck_thinking("(1m · thinking)") == 60
        assert detect_stuck_thinking("(10m 30s · thinking)") == 600
        assert detect_stuck_thinking("(27m 6s · thinking)") == 27 * 60


class TestExtractDialogContent:
    """Tests for dialog content extraction."""

    def test_extract_numbered_options(self):
        """Should extract numbered options from dialog."""
        from council.dispatcher.simple import extract_dialog_content
        output = """
Which approach would you prefer?

❯ 1. Use the existing utility function (recommended)
  2. Create a new helper class
  3. Inline the logic directly
  4. Other (please specify)

Esc to cancel
"""
        result = extract_dialog_content(output)

        assert result["dialog_type"] == "numbered"
        assert len(result["options"]) == 4
        assert "Use the existing utility function" in result["options"][0]

    def test_empty_output(self):
        """Empty output should return empty dialog."""
        from council.dispatcher.simple import extract_dialog_content
        result = extract_dialog_content("")
        assert result["question"] == ""
        assert result["options"] == []
        assert result["dialog_type"] == "unknown"
