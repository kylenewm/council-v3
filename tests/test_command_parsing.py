"""Tests for command parsing."""

import pytest
from council.dispatcher.simple import parse_command, clean_text


class TestCleanText:
    """Test clean_text function."""

    def test_normal_text_unchanged(self):
        assert clean_text("hello world") == "hello world"

    def test_removes_zero_width_chars(self):
        # Zero-width space (U+200B)
        text = "hello\u200bworld"
        assert clean_text(text) == "helloworld"

    def test_removes_zero_width_joiner(self):
        # Zero-width joiner (U+200D)
        text = "test\u200dtext"
        assert clean_text(text) == "testtext"

    def test_preserves_normal_unicode(self):
        assert clean_text("héllo wörld") == "héllo wörld"
        assert clean_text("日本語") == "日本語"


class TestParseCommand:
    """Test parse_command function."""

    # Meta commands
    def test_status_command(self):
        assert parse_command("status") == (None, "status")
        assert parse_command("Status") == (None, "status")
        assert parse_command("STATUS") == (None, "status")
        assert parse_command("s") == (None, "status")

    def test_quit_command(self):
        assert parse_command("quit") == (None, "quit")
        assert parse_command("q") == (None, "quit")
        assert parse_command("exit") == (None, "quit")

    def test_help_command(self):
        assert parse_command("help") == (None, "help")
        assert parse_command("h") == (None, "help")
        assert parse_command("?") == (None, "help")

    # Auto-continue commands
    def test_auto_command(self):
        assert parse_command("auto 1") == (1, "auto")
        assert parse_command("AUTO 2") == (2, "auto")
        assert parse_command("auto 99") == (99, "auto")

    def test_stop_command(self):
        assert parse_command("stop 1") == (1, "stop")
        assert parse_command("STOP 2") == (2, "stop")

    def test_reset_command(self):
        assert parse_command("reset 1") == (1, "reset")
        assert parse_command("RESET 3") == (3, "reset")

    # Agent commands
    def test_agent_command_with_colon(self):
        assert parse_command("1: hello world") == (1, "hello world")
        assert parse_command("2: do something") == (2, "do something")

    def test_agent_command_with_space(self):
        assert parse_command("1 hello world") == (1, "hello world")

    def test_agent_command_preserves_text(self):
        agent_id, text = parse_command("1: run pytest -v")
        assert agent_id == 1
        assert text == "run pytest -v"

    def test_agent_command_multi_digit_id(self):
        assert parse_command("10: test") == (10, "test")
        assert parse_command("99: test") == (99, "test")

    # Edge cases
    def test_empty_input(self):
        assert parse_command("") == (None, None)
        assert parse_command("   ") == (None, None)

    def test_whitespace_handling(self):
        assert parse_command("  status  ") == (None, "status")
        assert parse_command("  1: hello  ") == (1, "hello")

    def test_unknown_command(self):
        assert parse_command("unknown") == (None, None)
        assert parse_command("foobar") == (None, None)

    def test_malformed_agent_command(self):
        # No text after colon
        assert parse_command("1:") == (None, None)
        # Just a number
        assert parse_command("1") == (None, None)
