#!/usr/bin/env python3
"""
Telegram bot for receiving commands and routing to agents.
Uses curl subprocess to avoid Python SSL/LibreSSL issues.

Usage:
    from council.dispatcher.telegram import TelegramBot, start_telegram_bot

    bot = start_telegram_bot(config, command_callback)
    # bot runs in background thread

    bot.stop()  # to stop
"""

import json
import subprocess
import sys
import threading
import time
from typing import Callable, Optional


def _log(msg: str):
    """Print to stderr immediately (no buffering)."""
    print(msg, file=sys.stderr, flush=True)


class TelegramBot:
    """Telegram bot that routes commands to agents using curl."""

    def __init__(
        self,
        token: str,
        allowed_user_ids: list[int],
        command_callback: Callable[[str], None],
    ):
        """
        Initialize the Telegram bot.

        Args:
            token: Telegram bot token from @BotFather
            allowed_user_ids: List of Telegram user IDs allowed to send commands
            command_callback: Function to call with command text (e.g., "1: do task")
        """
        self.token = token
        self.allowed_user_ids = set(allowed_user_ids)
        self.command_callback = command_callback
        self.base_url = f"https://api.telegram.org/bot{token}"

        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._last_update_id = 0
        self._last_chat_id: Optional[int] = None

    def _curl_request(self, method: str, data: Optional[dict] = None, timeout: int = 10) -> Optional[dict]:
        """Make a request to Telegram API using curl."""
        url = f"{self.base_url}/{method}"

        cmd = ["curl", "-s", "--connect-timeout", "5", "-m", str(timeout)]

        if data:
            cmd.extend(["-X", "POST", "-H", "Content-Type: application/json", "-d", json.dumps(data)])

        cmd.append(url)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
            if result.returncode == 0 and result.stdout:
                response = json.loads(result.stdout)
                if response.get("ok"):
                    return response.get("result")
                else:
                    _log(f"[TELEGRAM] API error: {response.get('description')}")
            return None
        except subprocess.TimeoutExpired:
            _log("[TELEGRAM] Request timed out")
            return None
        except json.JSONDecodeError:
            _log(f"[TELEGRAM] Invalid JSON response")
            return None
        except Exception as e:
            _log(f"[TELEGRAM] Request error: {e}")
            return None

    def _handle_update(self, update: dict) -> None:
        """Process a single update from Telegram."""
        message = update.get("message")
        if not message:
            return

        user = message.get("from", {})
        user_id = user.get("id")
        username = user.get("username", "unknown")
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "").strip()

        if not text or not chat_id:
            return

        self._last_chat_id = chat_id

        # Check authorization
        if user_id not in self.allowed_user_ids:
            _log(f"[TELEGRAM] Unauthorized: {username} ({user_id})")
            # Reply with user ID so they can add it to config
            self.send_message(chat_id, f"Unauthorized. Your user ID: {user_id}\nAdd to allowed_user_ids in config.")
            return

        # Handle /start command
        if text == "/start":
            self.send_message(chat_id,
                f"Council Dispatcher ready.\n"
                f"Your user ID: {user_id}\n\n"
                f"Commands:\n"
                f"  1: <task> - send to agent 1\n"
                f"  status - show all agents\n"
                f"  auto 1 - enable auto-continue"
            )
            return

        # Route command to dispatcher
        _log(f"[TELEGRAM] Command from {username}: {text[:50]}...")
        self.send_message(chat_id, f"-> {text[:50]}...")

        try:
            self.command_callback(text)
        except Exception as e:
            _log(f"[TELEGRAM] Callback error: {e}")
            self.send_message(chat_id, f"Error: {e}")

    def send_message(self, chat_id: int, text: str) -> bool:
        """Send a message to a chat."""
        result = self._curl_request("sendMessage", {
            "chat_id": chat_id,
            "text": text
        })
        return result is not None

    def _poll_loop(self) -> None:
        """Main polling loop."""
        _log("[TELEGRAM] Starting poll loop")

        while self._running:
            try:
                # Long poll for updates (30s timeout)
                updates = self._curl_request("getUpdates", {
                    "offset": self._last_update_id + 1,
                    "timeout": 25
                }, timeout=30)

                if updates:
                    for update in updates:
                        update_id = update.get("update_id", 0)
                        if update_id > self._last_update_id:
                            self._last_update_id = update_id
                            self._handle_update(update)

                # Small delay between polls
                time.sleep(0.5)

            except Exception as e:
                _log(f"[TELEGRAM] Poll error: {e}")
                time.sleep(5)  # Wait before retry

        _log("[TELEGRAM] Poll loop stopped")

    def start(self) -> None:
        """Start the bot in a background thread."""
        if self._thread and self._thread.is_alive():
            _log("[TELEGRAM] Bot already running")
            return

        # Test connection first (short timeout to fail fast)
        _log("[TELEGRAM] Testing connection...")
        me = self._curl_request("getMe", timeout=5)
        if not me:
            _log("[TELEGRAM] Failed to connect - check token and network")
            return

        _log(f"[TELEGRAM] Bot @{me.get('username')} connected")

        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        _log("[TELEGRAM] Bot thread started")

    def stop(self) -> None:
        """Stop the bot."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        _log("[TELEGRAM] Bot stopped")


def start_telegram_bot(
    token: str,
    allowed_user_ids: list[int],
    command_callback: Callable[[str], None],
) -> Optional[TelegramBot]:
    """
    Start a Telegram bot for receiving commands.

    Args:
        token: Telegram bot token
        allowed_user_ids: List of allowed Telegram user IDs
        command_callback: Function to call with command text

    Returns:
        TelegramBot instance, or None if failed to start
    """
    if not token:
        _log("[TELEGRAM] No bot token provided")
        return None

    if not allowed_user_ids:
        _log("[TELEGRAM] No allowed user IDs - bot will reject all messages")

    bot = TelegramBot(
        token=token,
        allowed_user_ids=allowed_user_ids,
        command_callback=command_callback,
    )
    bot.start()

    # Check if it actually started
    if not bot._running:
        return None

    return bot
