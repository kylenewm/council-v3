"""Tests for config validation."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from council.dispatcher.simple import (
    validate_config, ConfigValidationError, Config, Agent
)


def make_config(agents: dict[int, Agent]) -> Config:
    """Create a Config with given agents."""
    return Config(agents=agents)


class TestValidateConfig:
    """Test validate_config function."""

    @patch("council.dispatcher.simple.tmux_pane_exists")
    def test_valid_config_returns_empty_warnings(self, mock_pane_exists):
        """Valid config with existing panes returns no warnings."""
        mock_pane_exists.return_value = True
        config = make_config({
            1: Agent(id=1, pane_id="%0", name="Agent 1", worktree=Path("/tmp")),
        })
        warnings = validate_config(config)
        assert warnings == []

    @patch("council.dispatcher.simple.tmux_pane_exists")
    def test_missing_pane_id_raises_error(self, mock_pane_exists):
        """Missing pane_id raises ConfigValidationError."""
        config = make_config({
            1: Agent(id=1, pane_id="", name="Agent 1"),
        })
        with pytest.raises(ConfigValidationError) as exc:
            validate_config(config)
        assert "missing pane_id" in str(exc.value)

    @patch("council.dispatcher.simple.tmux_pane_exists")
    def test_non_percent_pane_id_warns(self, mock_pane_exists):
        """pane_id not starting with % returns warning."""
        mock_pane_exists.return_value = True
        config = make_config({
            1: Agent(id=1, pane_id="0", name="Agent 1"),
        })
        warnings = validate_config(config)
        assert len(warnings) == 1
        assert "should start with '%'" in warnings[0]

    @patch("council.dispatcher.simple.tmux_pane_exists")
    def test_missing_pane_warns(self, mock_pane_exists):
        """Non-existing pane returns warning."""
        mock_pane_exists.return_value = False
        config = make_config({
            1: Agent(id=1, pane_id="%99", name="Agent 1"),
        })
        warnings = validate_config(config)
        assert len(warnings) == 1
        assert "not found" in warnings[0]

    @patch("council.dispatcher.simple.tmux_pane_exists")
    def test_nonexistent_worktree_warns_when_not_auto(self, mock_pane_exists):
        """Worktree that doesn't exist only warns when auto_enabled=False."""
        mock_pane_exists.return_value = True
        config = make_config({
            1: Agent(id=1, pane_id="%0", name="Agent 1", worktree=Path("/nonexistent/path/xyz"), auto_enabled=False),
        })
        warnings = validate_config(config)
        assert len(warnings) == 1
        assert "does not exist" in warnings[0]

    @patch("council.dispatcher.simple.tmux_pane_exists")
    def test_nonexistent_worktree_errors_when_auto_enabled(self, mock_pane_exists):
        """Worktree that doesn't exist raises error when auto_enabled=True."""
        mock_pane_exists.return_value = True
        config = make_config({
            1: Agent(id=1, pane_id="%0", name="Agent 1", worktree=Path("/nonexistent/path/xyz"), auto_enabled=True),
        })
        with pytest.raises(ConfigValidationError) as exc:
            validate_config(config)
        assert "does not exist" in str(exc.value)

    @patch("council.dispatcher.simple.tmux_pane_exists")
    def test_missing_worktree_errors_when_auto_enabled(self, mock_pane_exists):
        """Missing worktree raises error when auto_enabled=True."""
        mock_pane_exists.return_value = True
        config = make_config({
            1: Agent(id=1, pane_id="%0", name="Agent 1", worktree=None, auto_enabled=True),
        })
        with pytest.raises(ConfigValidationError) as exc:
            validate_config(config)
        assert "worktree required when auto_enabled" in str(exc.value)

    @patch("council.dispatcher.simple.tmux_pane_exists")
    def test_existing_worktree_passes(self, mock_pane_exists):
        """Existing worktree passes validation."""
        mock_pane_exists.return_value = True
        config = make_config({
            1: Agent(id=1, pane_id="%0", name="Agent 1", worktree=Path("/tmp")),
        })
        warnings = validate_config(config)
        assert warnings == []

    @patch("council.dispatcher.simple.tmux_pane_exists")
    def test_no_worktree_is_valid(self, mock_pane_exists):
        """Agent without worktree is valid."""
        mock_pane_exists.return_value = True
        config = make_config({
            1: Agent(id=1, pane_id="%0", name="Agent 1", worktree=None),
        })
        warnings = validate_config(config)
        assert warnings == []

    @patch("council.dispatcher.simple.tmux_pane_exists")
    def test_multiple_errors_all_reported(self, mock_pane_exists):
        """Multiple errors are all reported in exception."""
        mock_pane_exists.return_value = True
        config = make_config({
            1: Agent(id=1, pane_id="", name="Agent 1"),
            2: Agent(id=2, pane_id="", name="Agent 2"),
        })
        with pytest.raises(ConfigValidationError) as exc:
            validate_config(config)
        assert "Agent 1" in str(exc.value)
        assert "Agent 2" in str(exc.value)

    @patch("council.dispatcher.simple.tmux_pane_exists")
    def test_multiple_warnings_all_returned(self, mock_pane_exists):
        """Multiple warnings are all returned."""
        mock_pane_exists.return_value = False
        config = make_config({
            1: Agent(id=1, pane_id="%1", name="Agent 1"),
            2: Agent(id=2, pane_id="%2", name="Agent 2"),
        })
        warnings = validate_config(config)
        assert len(warnings) == 2


class TestConditionalValidation:
    """Tests for conditional config validation."""

    @patch("council.dispatcher.simple.tmux_pane_exists")
    def test_pushover_outbound_partial_user_key_errors(self, mock_pane_exists):
        """Pushover with api_token but no user_key raises error."""
        mock_pane_exists.return_value = True
        config = Config(
            agents={1: Agent(id=1, pane_id="%0", name="Agent 1")},
            pushover_api_token="token123",
            pushover_user_key=None,
        )
        with pytest.raises(ConfigValidationError) as exc:
            validate_config(config)
        assert "user_key required" in str(exc.value)

    @patch("council.dispatcher.simple.tmux_pane_exists")
    def test_pushover_outbound_partial_api_token_errors(self, mock_pane_exists):
        """Pushover with user_key but no api_token raises error."""
        mock_pane_exists.return_value = True
        config = Config(
            agents={1: Agent(id=1, pane_id="%0", name="Agent 1")},
            pushover_user_key="user123",
            pushover_api_token=None,
        )
        with pytest.raises(ConfigValidationError) as exc:
            validate_config(config)
        assert "api_token required" in str(exc.value)

    @patch("council.dispatcher.simple.tmux_pane_exists")
    def test_pushover_outbound_full_config_passes(self, mock_pane_exists):
        """Pushover with both user_key and api_token passes."""
        mock_pane_exists.return_value = True
        config = Config(
            agents={1: Agent(id=1, pane_id="%0", name="Agent 1")},
            pushover_user_key="user123",
            pushover_api_token="token123",
        )
        warnings = validate_config(config)
        assert warnings == []

    @patch("council.dispatcher.simple.tmux_pane_exists")
    def test_pushover_inbound_partial_email_errors(self, mock_pane_exists):
        """Pushover Open Client with password but no email raises error."""
        mock_pane_exists.return_value = True
        config = Config(
            agents={1: Agent(id=1, pane_id="%0", name="Agent 1")},
            pushover_password="pass123",
            pushover_email=None,
        )
        with pytest.raises(ConfigValidationError) as exc:
            validate_config(config)
        assert "email required" in str(exc.value)

    @patch("council.dispatcher.simple.tmux_pane_exists")
    def test_pushover_inbound_partial_password_errors(self, mock_pane_exists):
        """Pushover Open Client with email but no password raises error."""
        mock_pane_exists.return_value = True
        config = Config(
            agents={1: Agent(id=1, pane_id="%0", name="Agent 1")},
            pushover_email="email@test.com",
            pushover_password=None,
        )
        with pytest.raises(ConfigValidationError) as exc:
            validate_config(config)
        assert "password required" in str(exc.value)

    @patch("council.dispatcher.simple.tmux_pane_exists")
    def test_telegram_without_allowed_users_warns(self, mock_pane_exists):
        """Telegram with bot_token but no allowed_user_ids warns."""
        mock_pane_exists.return_value = True
        config = Config(
            agents={1: Agent(id=1, pane_id="%0", name="Agent 1")},
            telegram_bot_token="bot123",
            telegram_allowed_user_ids=[],
        )
        warnings = validate_config(config)
        assert len(warnings) == 1
        assert "no allowed_user_ids" in warnings[0]

    @patch("council.dispatcher.simple.tmux_pane_exists")
    def test_telegram_with_allowed_users_passes(self, mock_pane_exists):
        """Telegram with both bot_token and allowed_user_ids passes."""
        mock_pane_exists.return_value = True
        config = Config(
            agents={1: Agent(id=1, pane_id="%0", name="Agent 1")},
            telegram_bot_token="bot123",
            telegram_allowed_user_ids=[12345],
        )
        warnings = validate_config(config)
        assert warnings == []

    @patch("council.dispatcher.simple.tmux_pane_exists")
    def test_no_optional_config_passes(self, mock_pane_exists):
        """Config without optional features passes."""
        mock_pane_exists.return_value = True
        config = Config(
            agents={1: Agent(id=1, pane_id="%0", name="Agent 1")},
            # All optional fields default to None/empty
        )
        warnings = validate_config(config)
        assert warnings == []
