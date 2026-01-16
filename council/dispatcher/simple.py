#!/usr/bin/env python3
"""
Council Dispatcher v3 - Simplified voice/phone to agent routing.

What it does:
- Routes commands from FIFO (voice), Pushover (phone), Telegram to tmux panes
- Monitors agent state (ready/working/dialog)
- Auto-continue with circuit breaker (git-based progress detection)
- Notifications (Mac + Pushover)

What it DOESN'T do (agents handle this themselves):
- Task file parsing (agents use TodoWrite)
- Complex error signature extraction

Usage:
    python -m council.dispatcher.simple [config.yaml]

Commands:
    1: <text>        Send <text> to agent 1
    queue 1 "<task>" Add <task> to agent 1's queue
    queue 1          Show queue for agent 1
    clear 1          Clear queue for agent 1
    auto 1           Enable auto-continue for agent 1
    stop 1           Disable auto-continue for agent 1
    reset 1          Reset circuit breaker for agent 1
    progress 1 mark  Manually mark progress (resets streak)
    status           Show agent status
    quit             Exit
"""

import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

# Thread-safe queue for commands from background threads (Telegram)
_command_queue: queue.Queue = queue.Queue()

# Lock for state file access
_state_lock = threading.Lock()

STATE_FILE = Path.home() / ".council" / "state.json"
CURRENT_TASK_FILE = Path.home() / ".council" / "current_task.txt"
LOG_DIR = Path.home() / ".council" / "logs"

# Run ID for this dispatcher session
_run_id: str = str(uuid.uuid4())[:8]
_log_lock = threading.Lock()


def get_log_file() -> Path:
    """Get today's log file path."""
    return LOG_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"


def log_event(
    agent_id: Optional[int],
    cmd_type: str,
    pane_id: Optional[str] = None,
    result: str = "ok",
    error: Optional[str] = None,
    extra: Optional[dict] = None,
) -> None:
    """Log an event to the JSONL log file."""
    entry = {
        "ts": datetime.now().isoformat(),
        "run_id": _run_id,
        "agent_id": agent_id,
        "cmd_type": cmd_type,
        "pane_id": pane_id,
        "result": result,
        "error": error,
    }
    if extra:
        entry.update(extra)

    with _log_lock:
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            with open(get_log_file(), "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            print(f"[LOG ERROR] {e}")


# Git progress detection
from council.dispatcher.gitwatch import take_snapshot, has_progress, GitSnapshot

# Telegram bot (optional)
try:
    from council.dispatcher.telegram import start_telegram_bot, TelegramBot
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    TelegramBot = None


@dataclass
class Agent:
    """An agent running in a tmux pane."""
    id: int
    pane_id: str
    name: str
    worktree: Optional[Path] = None
    state: str = "unknown"  # unknown, ready, working, dialog, missing
    last_check: float = 0
    last_notify: float = 0
    # Auto-continue
    auto_enabled: bool = False
    # Circuit breaker
    circuit_state: str = "closed"  # closed, open
    no_progress_streak: int = 0
    last_snapshot: Optional[GitSnapshot] = None
    # Task queue
    task_queue: list[str] = field(default_factory=list)
    # DONE_REPORT detection (transcript watching)
    transcript_path: Optional[Path] = None  # Path to Claude session JSONL
    last_transcript_offset: int = 0  # Byte offset for incremental reads
    last_transcript_size: int = 0  # For rotation detection
    last_done_report_ts: Optional[float] = None  # When last DONE_REPORT was detected
    awaiting_done_report: bool = False  # True after task sent in strict mode
    # Auto-audit
    auto_audit: bool = False  # Run audit automatically on DONE_REPORT
    invariants_path: Optional[Path] = None  # Path to invariants.yaml
    audit_fail_streak: int = 0  # Track consecutive audit failures
    last_audit_task_id: Optional[str] = None  # Hash of last audited task
    mode: str = "default"  # "strict", "sandbox", "plan", "review", or "default"


NOTIFY_COOLDOWN = 30.0  # Seconds between notifications per agent
MAX_NO_PROGRESS = 3  # Open circuit after this many iterations without progress
TAIL_BYTES = 500_000  # 500KB tail window for DONE_REPORT detection
MAX_AUDIT_RETRIES = 1  # Only auto-queue "fix audit issues" once per task


@dataclass
class Config:
    """Dispatcher configuration."""
    agents: dict[int, Agent]
    poll_interval: float = 2.0
    fifo_path: Optional[Path] = None
    input_pane: Optional[str] = None
    # Pushover (outbound notifications)
    pushover_user_key: Optional[str] = None
    pushover_api_token: Optional[str] = None
    # Pushover Open Client (inbound commands)
    pushover_email: Optional[str] = None
    pushover_password: Optional[str] = None
    pushover_device_name: str = "council"
    # Telegram bot
    telegram_bot_token: Optional[str] = None
    telegram_allowed_user_ids: list[int] = field(default_factory=list)
    # Runtime options
    dry_run: bool = False


@dataclass
class PushoverClient:
    """Pushover Open Client state for receiving messages."""
    secret: Optional[str] = None
    device_id: Optional[str] = None
    highest_message_id: int = 0
    last_poll: float = 0
    poll_interval: float = 5.0


# --- State Persistence ---

def save_state(config: Config):
    """Save agent state to JSON file."""
    state = {"version": 3, "agents": {}}
    for agent_id, agent in config.agents.items():
        state["agents"][str(agent_id)] = {
            "auto_enabled": agent.auto_enabled,
            "circuit_state": agent.circuit_state,
            "no_progress_streak": agent.no_progress_streak,
            "task_queue": agent.task_queue,
            # Transcript watching state
            "last_transcript_offset": agent.last_transcript_offset,
            "last_transcript_size": agent.last_transcript_size,
            "last_done_report_ts": agent.last_done_report_ts,
            "awaiting_done_report": agent.awaiting_done_report,
            # Auto-audit state
            "audit_fail_streak": agent.audit_fail_streak,
            "last_audit_task_id": agent.last_audit_task_id,
        }
    with _state_lock:
        try:
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            tmp_file = STATE_FILE.with_suffix(".tmp")
            tmp_file.write_text(json.dumps(state, indent=2))
            tmp_file.rename(STATE_FILE)
        except Exception as e:
            print(f"[WARN] Could not save state: {e}")


def load_state(config: Config):
    """Load agent state from JSON file."""
    with _state_lock:
        if not STATE_FILE.exists():
            return
        try:
            state = json.loads(STATE_FILE.read_text())
            for agent_id_str, agent_state in state.get("agents", {}).items():
                agent_id = int(agent_id_str)
                if agent_id in config.agents:
                    agent = config.agents[agent_id]
                    agent.auto_enabled = agent_state.get("auto_enabled", False)
                    agent.circuit_state = agent_state.get("circuit_state", "closed")
                    agent.no_progress_streak = agent_state.get("no_progress_streak", 0)
                    agent.task_queue = agent_state.get("task_queue", [])
                    # Transcript watching state
                    agent.last_transcript_offset = agent_state.get("last_transcript_offset", 0)
                    agent.last_transcript_size = agent_state.get("last_transcript_size", 0)
                    agent.last_done_report_ts = agent_state.get("last_done_report_ts")
                    agent.awaiting_done_report = agent_state.get("awaiting_done_report", False)
                    # Auto-audit state
                    agent.audit_fail_streak = agent_state.get("audit_fail_streak", 0)
                    agent.last_audit_task_id = agent_state.get("last_audit_task_id")
            print(f"[STATE] Restored from {STATE_FILE}")
        except Exception as e:
            print(f"[WARN] Could not load state: {e}")


def write_current_task(agent: Agent, task: str):
    """Write current task context for rich notifications.

    Format is source-able bash for the notification script:
        AGENT_ID=1
        AGENT_NAME="AgentName"
        PANE_ID="%0"
        PROJECT="project-name"
        TASK="task description"
    """
    try:
        CURRENT_TASK_FILE.parent.mkdir(parents=True, exist_ok=True)
        # Escape quotes in task for bash sourcing
        safe_task = task[:100].replace('"', '\\"').replace('\n', ' ')
        project = agent.worktree.name if agent.worktree else "unknown"
        content = f'''AGENT_ID={agent.id}
AGENT_NAME="{agent.name}"
PANE_ID="{agent.pane_id}"
PROJECT="{project}"
TASK="{safe_task}"
'''
        CURRENT_TASK_FILE.write_text(content)
    except Exception as e:
        print(f"[WARN] Could not write current task: {e}")


# --- DONE_REPORT Detection ---

def check_done_report(agent: Agent) -> bool:
    """Check if DONE_REPORT appears in transcript since last check.

    Uses tail-bytes search to reliably find DONE_REPORT even with verbose output.
    Handles file rotation/truncation.

    Returns True if DONE_REPORT found, False otherwise.
    """
    if not agent.transcript_path or not agent.transcript_path.exists():
        return False  # No transcript configured → N/A

    try:
        size = agent.transcript_path.stat().st_size

        # Handle file rotation/truncation
        if size < agent.last_transcript_size:
            agent.last_transcript_offset = 0

        # Read from tail window (not just since last offset)
        start = max(0, size - TAIL_BYTES)
        with open(agent.transcript_path, 'rb') as f:
            f.seek(start)
            content = f.read().decode('utf-8', errors='ignore')

        if 'DONE_REPORT' in content:
            agent.awaiting_done_report = False
            agent.last_done_report_ts = time.time()
            agent.last_transcript_offset = size
            agent.last_transcript_size = size
            return True

        agent.last_transcript_size = size
        return False
    except Exception as e:
        # Log but don't crash on transcript read errors
        return False


def format_done_status(agent: Agent) -> str:
    """Format DONE_REPORT status for status display.

    Returns:
        - "[DONE ✓ Xm ago]" if DONE_REPORT found recently
        - "[awaiting DONE_REPORT]" if waiting for completion
        - "[DONE: N/A]" if no transcript configured
    """
    if not agent.transcript_path:
        return "[DONE: N/A]"

    if agent.awaiting_done_report:
        return "[awaiting DONE_REPORT]"

    if agent.last_done_report_ts:
        elapsed = time.time() - agent.last_done_report_ts
        if elapsed < 60:
            return f"[DONE ✓ {int(elapsed)}s ago]"
        elif elapsed < 3600:
            return f"[DONE ✓ {int(elapsed / 60)}m ago]"
        else:
            return f"[DONE ✓ {int(elapsed / 3600)}h ago]"

    return ""  # No DONE_REPORT detected yet


def run_auto_audit(agent: Agent, config: Config) -> Optional[str]:
    """Run auto-audit on DONE_REPORT if configured.

    Returns status string or None if no action taken.
    Implements loop guard to prevent infinite "fix audit issues" cycles.
    """
    import hashlib
    import subprocess as audit_subprocess

    if not agent.transcript_path:
        return None

    # Compute task_id from current state (for loop guard)
    task_id = hashlib.sha256(
        f"{agent.transcript_path}:{agent.last_done_report_ts}".encode()
    ).hexdigest()[:16]

    # Run invariants check if configured
    invariants_passed = True
    invariants_output = ""
    if agent.invariants_path and agent.invariants_path.exists() and agent.worktree:
        try:
            result = audit_subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).parent.parent.parent / "scripts" / "check_invariants.py"),
                    "--diff", "HEAD~1",
                    "--invariants", str(agent.invariants_path),
                    "--repo", str(agent.worktree),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            invariants_passed = result.returncode == 0
            invariants_output = result.stdout
        except Exception as e:
            invariants_output = f"invariants check error: {e}"

    # Run audit_done.py
    audit_passed = True
    audit_output = ""
    try:
        result = audit_subprocess.run(
            [
                sys.executable,
                str(Path(__file__).parent.parent.parent / "scripts" / "audit_done.py"),
                "--transcript", str(agent.transcript_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        audit_passed = result.returncode == 0
        audit_output = result.stdout
    except Exception as e:
        audit_output = f"audit error: {e}"
        audit_passed = False

    # Determine verdict
    if invariants_passed and audit_passed:
        agent.audit_fail_streak = 0
        notify(f"✅ {agent.name}: APPROVED", config)
        log_event(agent.id, "audit_approved", agent.pane_id)
        return "APPROVED"

    # Handle failure with loop guard
    if task_id != agent.last_audit_task_id:
        # New task, reset counter
        agent.last_audit_task_id = task_id
        agent.audit_fail_streak = 1
    else:
        agent.audit_fail_streak += 1

    if agent.audit_fail_streak <= MAX_AUDIT_RETRIES:
        # Auto-queue fix task
        reasons = []
        if not invariants_passed:
            reasons.append(f"invariants failed: {invariants_output[:100]}")
        if not audit_passed:
            reasons.append(f"audit failed: {audit_output[:100]}")
        fix_task = f"Fix audit issues: {'; '.join(reasons)}"
        agent.task_queue.append(fix_task)
        save_state(config)
        notify(f"❌ {agent.name}: REJECTED - queued fix task", config)
        log_event(agent.id, "audit_rejected", agent.pane_id, extra={"reasons": reasons})
        return f"REJECTED (fix queued, streak={agent.audit_fail_streak})"
    else:
        # Cap reached, notify human
        notify(f"❌ {agent.name}: REQUIRES HUMAN - audit failed {agent.audit_fail_streak} times", config)
        log_event(agent.id, "audit_requires_human", agent.pane_id,
                  extra={"streak": agent.audit_fail_streak})
        return f"REQUIRES HUMAN (failed {agent.audit_fail_streak} times)"


# --- Pattern Detection ---

READY_PATTERNS = [
    re.compile(r"^❯", re.MULTILINE),
    re.compile(r"^\s*\?\s+for\s+shortcuts", re.MULTILINE),
]

DIALOG_PATTERNS = [
    re.compile(r"❯\s+\d+\.\s+", re.MULTILINE),
    re.compile(r"Do you want to", re.MULTILINE),
    re.compile(r"Esc to cancel", re.MULTILINE),
]


def detect_state(output: str) -> str:
    """Detect if Claude is ready for input or working."""
    if not output:
        return "unknown"
    for pattern in DIALOG_PATTERNS:
        if pattern.search(output):
            return "dialog"
    for pattern in READY_PATTERNS:
        if pattern.search(output):
            return "ready"
    return "working"


# Pattern to detect "thinking" with duration, e.g., "(27m 6s · thinking)"
THINKING_PATTERN = re.compile(r"\((\d+)m\s*(?:\d+s)?\s*·\s*thinking\)")
STUCK_THINKING_THRESHOLD = 600  # 10 minutes in seconds


def detect_stuck_thinking(output: str) -> Optional[int]:
    """Detect if Claude is stuck thinking. Returns duration in seconds, or None."""
    if not output:
        return None
    match = THINKING_PATTERN.search(output)
    if match:
        minutes = int(match.group(1))
        return minutes * 60
    return None


# --- tmux Functions ---

def tmux_capture(pane_id: str, lines: int = 30) -> Optional[str]:
    """Capture recent output from a tmux pane."""
    try:
        result = subprocess.run(
            ["tmux", "capture-pane", "-t", pane_id, "-p"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return None
        all_lines = result.stdout.strip().split("\n")
        return "\n".join(all_lines[-lines:])
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def tmux_send(pane_id: str, text: str) -> bool:
    """Send text to a tmux pane."""
    try:
        result = subprocess.run(
            ["tmux", "send-keys", "-l", "-t", pane_id, "--", text],
            capture_output=True, timeout=5,
        )
        if result.returncode != 0:
            return False
        result = subprocess.run(
            ["tmux", "send-keys", "-t", pane_id, "Enter"],
            capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def tmux_pane_exists(pane_id: str) -> bool:
    """Check if a tmux pane exists."""
    try:
        result = subprocess.run(
            ["tmux", "display", "-t", pane_id, "-p", "#{pane_id}"],
            capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def tmux_pane_in_copy_mode(pane_id: str) -> bool:
    """Check if pane is in copy/scroll mode."""
    try:
        result = subprocess.run(
            ["tmux", "display", "-t", pane_id, "-p", "#{pane_in_mode}"],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0 and result.stdout.strip() == "1"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def send_to_agent(agent: Agent, text: str, config: Config, cmd_type: str = "send") -> bool:
    """Send text to agent, respecting dry-run mode."""
    if config.dry_run:
        print(f"[DRY-RUN] Would send to {agent.name} ({agent.pane_id}): {text[:80]}{'...' if len(text) > 80 else ''}")
        log_event(agent.id, cmd_type, agent.pane_id, result="dry_run")
        return True
    success = tmux_send(agent.pane_id, text)
    log_event(
        agent.id, cmd_type, agent.pane_id,
        result="ok" if success else "fail",
        error=None if success else "tmux_send failed",
    )
    return success


# --- Notifications ---

def notify_pushover(message: str, title: str, user_key: str, api_token: str) -> bool:
    """Send a Pushover notification."""
    try:
        import urllib.request
        import urllib.parse
        data = urllib.parse.urlencode({
            "token": api_token, "user": user_key,
            "title": title, "message": message,
        }).encode()
        req = urllib.request.Request(
            "https://api.pushover.net/1/messages.json",
            data=data, method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"[PUSHOVER ERROR] {e}")
        return False


def notify(message: str, config: Config, title: str = "Council"):
    """Send a notification (Mac + Pushover)."""
    print(f"[NOTIFY] {message}")
    try:
        subprocess.run(
            ["terminal-notifier", "-title", title, "-message", message, "-sound", "default"],
            capture_output=True, timeout=5,
        )
    except FileNotFoundError:
        pass
    if config.pushover_user_key and config.pushover_api_token:
        notify_pushover(message, title, config.pushover_user_key, config.pushover_api_token)


# --- Pushover Open Client (inbound commands) ---

def pushover_login(email: str, password: str) -> Optional[str]:
    """Login to Pushover and get session secret."""
    try:
        import urllib.request
        import urllib.parse
        data = urllib.parse.urlencode({"email": email, "password": password}).encode()
        req = urllib.request.Request(
            "https://api.pushover.net/1/users/login.json",
            data=data, method="POST"
        )
        req.add_header("User-Agent", "Council-Dispatcher/3.0")
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                result = json.loads(resp.read().decode())
                if result.get("status") == 1:
                    return result.get("secret")
    except Exception as e:
        print(f"[PUSHOVER LOGIN ERROR] {e}")
    return None


def pushover_register_device(secret: str, device_name: str) -> Optional[str]:
    """Register a device with Pushover Open Client API."""
    try:
        import urllib.request
        import urllib.parse
        import urllib.error
        data = urllib.parse.urlencode({
            "secret": secret, "name": device_name, "os": "O",
        }).encode()
        req = urllib.request.Request(
            "https://api.pushover.net/1/devices.json",
            data=data, method="POST"
        )
        req.add_header("User-Agent", "Council-Dispatcher/3.0")
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                result = json.loads(resp.read().decode())
                if result.get("status") == 1:
                    return result.get("id")
    except Exception as e:
        if "400" in str(e):
            print(f"[PUSHOVER] Device may already exist, continuing")
            return None
        print(f"[PUSHOVER REGISTER ERROR] {e}")
    return None


def pushover_get_messages(secret: str, device_id: str) -> list[dict]:
    """Get pending messages from Pushover."""
    try:
        import urllib.request
        import urllib.parse
        params = urllib.parse.urlencode({"secret": secret, "device_id": device_id})
        req = urllib.request.Request(
            f"https://api.pushover.net/1/messages.json?{params}",
            method="GET"
        )
        req.add_header("User-Agent", "Council-Dispatcher/3.0")
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                result = json.loads(resp.read().decode())
                if result.get("status") == 1:
                    return result.get("messages", [])
    except Exception as e:
        print(f"[PUSHOVER MESSAGES ERROR] {e}")
    return []


def pushover_delete_messages(secret: str, device_id: str, highest_id: int) -> bool:
    """Delete messages up to highest_id."""
    try:
        import urllib.request
        import urllib.parse
        data = urllib.parse.urlencode({"secret": secret, "message": highest_id}).encode()
        req = urllib.request.Request(
            f"https://api.pushover.net/1/devices/{device_id}/update_highest_message.json",
            data=data, method="POST"
        )
        req.add_header("User-Agent", "Council-Dispatcher/3.0")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"[PUSHOVER DELETE ERROR] {e}")
    return False


def pushover_init_client(config: Config) -> Optional[PushoverClient]:
    """Initialize Pushover Open Client for receiving messages."""
    if not config.pushover_email or not config.pushover_password:
        return None
    print("[PUSHOVER] Initializing Open Client...")
    secret = pushover_login(config.pushover_email, config.pushover_password)
    if not secret:
        print("[PUSHOVER] Login failed")
        return None
    print("[PUSHOVER] Logged in")
    device_id = pushover_register_device(secret, config.pushover_device_name)
    if not device_id:
        device_id = config.pushover_device_name
    return PushoverClient(secret=secret, device_id=device_id)


def pushover_poll(client: PushoverClient, config: Config) -> list[str]:
    """Poll for Pushover messages and return command lines."""
    if not client or not client.secret:
        return []
    now = time.time()
    if now - client.last_poll < client.poll_interval:
        return []
    client.last_poll = now
    messages = pushover_get_messages(client.secret, client.device_id)
    if not messages:
        return []
    commands = []
    highest_id = client.highest_message_id
    for msg in messages:
        msg_id = msg.get("id", 0)
        if msg_id <= client.highest_message_id:
            continue
        body = msg.get("message", "").strip()
        if body:
            print(f"[PUSHOVER] Received: {body[:50]}...")
            commands.append(body)
        if msg_id > highest_id:
            highest_id = msg_id
    if highest_id > client.highest_message_id:
        if pushover_delete_messages(client.secret, client.device_id, highest_id):
            client.highest_message_id = highest_id
    return commands


# --- Config Validation ---

class ConfigValidationError(Exception):
    """Raised when config validation fails."""
    pass


def validate_config(config: Config) -> list[str]:
    """
    Validate configuration. Returns list of warnings.
    Raises ConfigValidationError for fatal issues.

    Conditional validation: only validate what's configured.
    """
    errors = []
    warnings = []

    # --- Agent validation (always) ---
    for agent in config.agents.values():
        # pane_id is always required
        if not agent.pane_id:
            errors.append(f"Agent {agent.id} ({agent.name}): missing pane_id")
        elif not agent.pane_id.startswith("%"):
            warnings.append(f"Agent {agent.id} ({agent.name}): pane_id '{agent.pane_id}' should start with '%' for stability")

        # Check pane exists (warning only)
        if agent.pane_id and not tmux_pane_exists(agent.pane_id):
            warnings.append(f"Agent {agent.id} ({agent.name}): pane {agent.pane_id} not found")

        # worktree only required if auto_enabled (circuit breaker needs git)
        if agent.auto_enabled:
            if not agent.worktree:
                errors.append(f"Agent {agent.id} ({agent.name}): worktree required when auto_enabled")
            elif not agent.worktree.exists():
                errors.append(f"Agent {agent.id} ({agent.name}): worktree '{agent.worktree}' does not exist")
        elif agent.worktree and not agent.worktree.exists():
            # Worktree configured but doesn't exist - just warn
            warnings.append(f"Agent {agent.id} ({agent.name}): worktree '{agent.worktree}' does not exist")

    # --- Pushover outbound (if either configured) ---
    if config.pushover_user_key or config.pushover_api_token:
        if not config.pushover_user_key:
            errors.append("Pushover: user_key required when api_token is set")
        if not config.pushover_api_token:
            errors.append("Pushover: api_token required when user_key is set")

    # --- Pushover inbound/Open Client (if either configured) ---
    if config.pushover_email or config.pushover_password:
        if not config.pushover_email:
            errors.append("Pushover Open Client: email required when password is set")
        if not config.pushover_password:
            errors.append("Pushover Open Client: password required when email is set")

    # --- Telegram (if bot_token configured) ---
    if config.telegram_bot_token:
        if not config.telegram_allowed_user_ids:
            warnings.append("Telegram: bot_token set but no allowed_user_ids - no users can send commands")

    # --- FIFO (if configured) ---
    if config.fifo_path and not config.fifo_path.exists():
        warnings.append(f"FIFO not found: {config.fifo_path} (create with: mkfifo {config.fifo_path})")

    if errors:
        raise ConfigValidationError("\n".join(errors))

    return warnings


# --- Config Loading ---

def load_config(path: Path) -> Config:
    """Load configuration from YAML file."""
    try:
        with open(path) as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"[ERROR] Invalid YAML in {path}: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Could not read config {path}: {e}")
        sys.exit(1)

    if not raw or not raw.get("agents"):
        print(f"[ERROR] No agents defined in config")
        sys.exit(1)

    agents = {}
    for agent_id, agent_cfg in raw.get("agents", {}).items():
        worktree = None
        if agent_cfg.get("worktree"):
            worktree = Path(os.path.expanduser(agent_cfg["worktree"]))
        transcript_path = None
        if agent_cfg.get("transcript_path"):
            transcript_path = Path(os.path.expanduser(agent_cfg["transcript_path"]))
        invariants_path = None
        if agent_cfg.get("invariants_path"):
            invariants_path = Path(os.path.expanduser(agent_cfg["invariants_path"]))
        agents[int(agent_id)] = Agent(
            id=int(agent_id),
            pane_id=agent_cfg.get("pane_id", ""),
            name=agent_cfg.get("name", f"Agent {agent_id}"),
            worktree=worktree,
            transcript_path=transcript_path,
            auto_audit=agent_cfg.get("auto_audit", False),
            invariants_path=invariants_path,
            mode=agent_cfg.get("mode", "default"),
        )

    fifo_path = None
    if raw.get("fifo_path"):
        fifo_path = Path(os.path.expanduser(raw["fifo_path"]))

    pushover = raw.get("pushover", {})
    return Config(
        agents=agents,
        poll_interval=raw.get("poll_interval", 2.0),
        fifo_path=fifo_path,
        input_pane=raw.get("input_pane"),
        pushover_user_key=pushover.get("user_key"),
        pushover_api_token=pushover.get("api_token"),
        pushover_email=pushover.get("email"),
        pushover_password=pushover.get("password"),
        pushover_device_name=pushover.get("device_name", "council"),
        telegram_bot_token=raw.get("telegram", {}).get("bot_token"),
        telegram_allowed_user_ids=raw.get("telegram", {}).get("allowed_user_ids", []),
    )


# --- Agent Monitoring ---

def check_agents(config: Config) -> list[str]:
    """Check all agents and return list of state changes."""
    changes = []

    for agent in config.agents.values():
        try:
            output = tmux_capture(agent.pane_id)
            if output is None:
                if agent.state != "missing":
                    agent.state = "missing"
                    changes.append(f"{agent.name}: pane not found")
                continue

            # Check for stuck thinking (notify has cooldown, won't spam)
            thinking_duration = detect_stuck_thinking(output)
            if thinking_duration and thinking_duration >= STUCK_THINKING_THRESHOLD:
                minutes = thinking_duration // 60
                changes.append(f"{agent.name}: stuck thinking ({minutes}m)")
                notify(f"[{agent.id}] {agent.name} stuck thinking for {minutes}min", config)

            new_state = detect_state(output)
            if new_state != agent.state:
                old_state = agent.state
                agent.state = new_state

                if new_state == "ready":
                    changes.append(f"{agent.name} is READY")

                    # Check for DONE_REPORT in transcript
                    done_report_found = check_done_report(agent)
                    if done_report_found:
                        changes.append(f"  -> DONE_REPORT detected")

                        # Run auto-audit if configured
                        if agent.auto_audit and agent.mode == "strict":
                            audit_result = run_auto_audit(agent, config)
                            if audit_result:
                                changes.append(f"  -> audit: {audit_result}")

                    # Check progress via git (if we have a previous snapshot)
                    if agent.worktree and agent.last_snapshot:
                        new_snapshot = take_snapshot(agent.worktree)
                        if has_progress(agent.last_snapshot, new_snapshot):
                            agent.no_progress_streak = 0
                            changes.append(f"  -> progress detected, streak reset")
                        elif agent.circuit_state != "open":
                            # Only increment streak if circuit not already open
                            agent.no_progress_streak += 1
                            changes.append(f"  -> no progress ({agent.no_progress_streak}/{MAX_NO_PROGRESS})")
                        agent.last_snapshot = new_snapshot

                    # Circuit breaker check
                    if agent.no_progress_streak >= MAX_NO_PROGRESS:
                        if agent.circuit_state != "open":
                            agent.circuit_state = "open"
                            changes.append(f"  -> CIRCUIT OPEN (no progress)")
                            log_event(agent.id, "circuit_open", agent.pane_id,
                                      extra={"streak": agent.no_progress_streak})
                            notify(f"{agent.name}: circuit open - no progress", config)
                            save_state(config)

                    # Dequeue from task queue (takes priority over auto-continue)
                    if agent.task_queue and agent.circuit_state == "closed":
                        next_task = agent.task_queue[0]  # Peek first
                        if agent.worktree:
                            agent.last_snapshot = take_snapshot(agent.worktree)
                        if send_to_agent(agent, next_task, config, cmd_type="dequeue"):
                            agent.task_queue.pop(0)  # Pop after successful send
                            changes.append(f"  -> queued task: {next_task[:40]}...")
                            changes.append(f"     [{len(agent.task_queue)} remaining]")
                            agent.state = "working"
                            write_current_task(agent, next_task)
                            save_state(config)
                    # Auto-continue (simplified - just send "continue")
                    elif agent.auto_enabled and agent.circuit_state == "closed":
                        if agent.worktree:
                            agent.last_snapshot = take_snapshot(agent.worktree)
                        if send_to_agent(agent, "continue", config, cmd_type="auto_continue"):
                            changes.append(f"  -> auto-continue sent")
                            agent.state = "working"
                    elif not agent.auto_enabled and not agent.task_queue:
                        # Notify user
                        now = time.time()
                        if now - agent.last_notify >= NOTIFY_COOLDOWN:
                            notify(f"{agent.name} needs input", config)
                            agent.last_notify = now

                elif new_state == "working" and old_state == "ready":
                    changes.append(f"{agent.name} is working...")

            agent.last_check = time.time()
        except Exception as e:
            changes.append(f"{agent.name}: check error - {e}")

    return changes


def show_status(config: Config):
    """Print status of all agents."""
    print("\n=== Agent Status ===")
    for agent in config.agents.values():
        status = agent.state
        if agent.state == "ready":
            status = "READY"
        elif agent.state == "working":
            status = "working..."
        elif agent.state == "dialog":
            status = "DIALOG (needs y/n)"
        elif agent.state == "missing":
            status = "MISSING"

        extras = []
        if agent.auto_enabled:
            extras.append("AUTO")
        if agent.circuit_state == "open":
            extras.append("CIRCUIT OPEN")
        if agent.task_queue:
            extras.append(f"Q:{len(agent.task_queue)}")

        # DONE_REPORT status
        done_status = format_done_status(agent)
        if done_status:
            extras.append(done_status)

        # Mode indicator
        if agent.mode != "default":
            extras.append(f"mode:{agent.mode}")

        extras_str = f" [{' '.join(extras)}]" if extras else ""

        print(f"  {agent.id}: {agent.name} [{agent.pane_id}] - {status}{extras_str}")
    print()


# --- Command Processing ---

def clean_text(s: str) -> str:
    """Remove zero-width characters that break parsing."""
    return ''.join(c for c in s if unicodedata.category(c) != 'Cf')


def parse_command(line: str) -> tuple[Optional[int], Optional[str]]:
    """Parse a command line like '1: do something' or 'status'."""
    line = clean_text(line).strip()
    if not line:
        return None, None

    # Meta commands
    if line.lower() in ("status", "s"):
        return None, "status"
    if line.lower() in ("quit", "q", "exit"):
        return None, "quit"
    if line.lower() in ("help", "h", "?"):
        return None, "help"

    # Auto-continue commands
    auto_match = re.match(r"^auto\s+(\d+)$", line, re.IGNORECASE)
    if auto_match:
        return int(auto_match.group(1)), "auto"

    stop_match = re.match(r"^stop\s+(\d+)$", line, re.IGNORECASE)
    if stop_match:
        return int(stop_match.group(1)), "stop"

    reset_match = re.match(r"^reset\s+(\d+)$", line, re.IGNORECASE)
    if reset_match:
        return int(reset_match.group(1)), "reset"

    # Queue management commands
    queue_show_match = re.match(r"^queue\s+(\d+)$", line, re.IGNORECASE)
    if queue_show_match:
        return int(queue_show_match.group(1)), "queue"

    # Queue add: queue 1 "task" or queue 1 'task'
    queue_add_match = re.match(r'^queue\s+(\d+)\s+["\'](.+)["\']$', line, re.IGNORECASE)
    if queue_add_match:
        return int(queue_add_match.group(1)), ("queue_add", queue_add_match.group(2))

    clear_match = re.match(r"^clear\s+(\d+)$", line, re.IGNORECASE)
    if clear_match:
        return int(clear_match.group(1)), "clear"

    # Progress mark: progress 1 mark
    progress_match = re.match(r"^progress\s+(\d+)\s+mark$", line, re.IGNORECASE)
    if progress_match:
        return int(progress_match.group(1)), "progress_mark"

    # Agent command: "1: do something"
    match = re.match(r"^(\d+)[:\s]+(.+)$", line)
    if match:
        return int(match.group(1)), match.group(2)

    return None, None


def process_line(line: str, config: Config) -> bool:
    """Process a command line. Returns False if should quit."""
    agent_id, command = parse_command(line)

    if command == "quit":
        print("Bye!")
        return False
    elif command == "status":
        check_agents(config)
        show_status(config)
    elif command == "help":
        print("\nCommands:")
        print('  1: <text>        - Send <text> to agent 1')
        print('  queue 1 "<task>" - Add <task> to agent 1\'s queue')
        print("  queue 1          - Show queue for agent 1")
        print("  clear 1          - Clear queue for agent 1")
        print("  auto 1           - Enable auto-continue for agent 1")
        print("  stop 1           - Disable auto-continue for agent 1")
        print("  reset 1          - Reset circuit breaker for agent 1")
        print("  progress 1 mark  - Manually mark progress (resets streak)")
        print("  status           - Show agent status")
        print("  quit             - Exit\n")
    elif command == "auto" and agent_id is not None:
        agent = config.agents.get(agent_id)
        if not agent:
            print(f"Unknown agent: {agent_id}")
        else:
            agent.auto_enabled = True
            if agent.worktree:
                agent.last_snapshot = take_snapshot(agent.worktree)
            print(f"{agent.name}: auto-continue ENABLED")
            save_state(config)
    elif command == "stop" and agent_id is not None:
        agent = config.agents.get(agent_id)
        if not agent:
            print(f"Unknown agent: {agent_id}")
        else:
            agent.auto_enabled = False
            print(f"{agent.name}: auto-continue DISABLED")
            save_state(config)
    elif command == "reset" and agent_id is not None:
        agent = config.agents.get(agent_id)
        if not agent:
            print(f"Unknown agent: {agent_id}")
        else:
            agent.circuit_state = "closed"
            agent.no_progress_streak = 0
            agent.last_snapshot = None
            log_event(agent.id, "circuit_reset", agent.pane_id)
            print(f"{agent.name}: circuit RESET")
            save_state(config)
    elif command == "queue" and agent_id is not None:
        agent = config.agents.get(agent_id)
        if not agent:
            print(f"Unknown agent: {agent_id}")
        elif not agent.task_queue:
            print(f"{agent.name}: queue is empty")
        else:
            print(f"\n{agent.name} queue ({len(agent.task_queue)} tasks):")
            for i, task in enumerate(agent.task_queue, 1):
                print(f"  {i}. {task[:60]}{'...' if len(task) > 60 else ''}")
            print()
    elif command == "clear" and agent_id is not None:
        agent = config.agents.get(agent_id)
        if not agent:
            print(f"Unknown agent: {agent_id}")
        else:
            cleared = len(agent.task_queue)
            agent.task_queue.clear()
            print(f"{agent.name}: cleared {cleared} queued tasks")
            save_state(config)
    elif isinstance(command, tuple) and command[0] == "queue_add" and agent_id is not None:
        task = command[1]
        agent = config.agents.get(agent_id)
        if not agent:
            print(f"Unknown agent: {agent_id}")
        else:
            agent.task_queue.append(task)
            print(f"{agent.name}: queued task ({len(agent.task_queue)} total)")
            print(f"  -> {task[:60]}{'...' if len(task) > 60 else ''}")
            save_state(config)
    elif command == "progress_mark" and agent_id is not None:
        agent = config.agents.get(agent_id)
        if not agent:
            print(f"Unknown agent: {agent_id}")
        else:
            # Mark progress manually - reset streak and update snapshot
            if agent.worktree:
                agent.last_snapshot = take_snapshot(agent.worktree)
            agent.no_progress_streak = 0
            log_event(agent.id, "progress_mark", agent.pane_id)
            print(f"{agent.name}: progress marked (streak reset)")
            save_state(config)
    elif agent_id is not None and command:
        agent = config.agents.get(agent_id)
        if not agent:
            print(f"Unknown agent: {agent_id}")
        elif agent.state == "missing":
            print(f"{agent.name}: pane not found")
        elif tmux_pane_in_copy_mode(agent.pane_id):
            print(f"{agent.name}: in scroll mode, exit first (q)")
        else:
            # Send command directly (no pipe splitting - use 'queue N' for multiple tasks)
            if agent.worktree:
                agent.last_snapshot = take_snapshot(agent.worktree)
            if send_to_agent(agent, command, config):
                if not config.dry_run:
                    print(f"-> {agent.name}: {command[:50]}...")
                agent.state = "working"
                write_current_task(agent, command)
            else:
                print(f"Failed to send to {agent.name}")
    elif line.strip():
        print(f"Unknown command. Type 'help' for usage.")

    return True


# --- Main Loop ---

def run_with_fifo(config: Config, pushover_client: Optional[PushoverClient] = None):
    """Run dispatcher reading from FIFO."""
    import select

    fifo_path = config.fifo_path
    print(f"Reading from FIFO: {fifo_path}")

    last_poll = time.time()
    fd = None
    fifo = None

    try:
        while True:
            try:
                if fd is None:
                    fd = os.open(fifo_path, os.O_RDONLY | os.O_NONBLOCK)
                    fifo = os.fdopen(fd, "r")

                if select.select([fifo], [], [], 0.5)[0]:
                    line = fifo.readline()
                    if not line:
                        fifo.close()
                        fd = None
                        fifo = None
                        continue
                    if not process_line(line, config):
                        return

                # Poll Pushover
                if pushover_client:
                    for cmd in pushover_poll(pushover_client, config):
                        print(f"[PUSHOVER CMD] {cmd}")
                        if not process_line(cmd, config):
                            return

                # Poll command queue (Telegram)
                while True:
                    try:
                        source, cmd = _command_queue.get_nowait()
                        print(f"[{source.upper()} CMD] {cmd}")
                        if not process_line(cmd, config):
                            return
                    except queue.Empty:
                        break

                # Periodic agent check
                if time.time() - last_poll >= config.poll_interval:
                    changes = check_agents(config)
                    for change in changes:
                        print(f"[{time.strftime('%H:%M:%S')}] {change}")
                    last_poll = time.time()

            except OSError:
                if fifo:
                    try:
                        fifo.close()
                    except Exception:
                        pass
                fd = None
                fifo = None
                time.sleep(1)

    except KeyboardInterrupt:
        print("\nBye!")
    finally:
        if fifo:
            try:
                fifo.close()
            except Exception:
                pass


def run_with_stdin(config: Config, pushover_client: Optional[PushoverClient] = None):
    """Run dispatcher reading from stdin."""
    import select

    print("Ready. Type commands (or 'help'):\n")
    last_poll = time.time()

    try:
        while True:
            if select.select([sys.stdin], [], [], 0.5)[0]:
                line = sys.stdin.readline()
                if not line:
                    break
                if not process_line(line, config):
                    return

            # Poll Pushover
            if pushover_client:
                for cmd in pushover_poll(pushover_client, config):
                    print(f"[PUSHOVER CMD] {cmd}")
                    if not process_line(cmd, config):
                        return

            # Poll command queue (Telegram)
            while True:
                try:
                    source, cmd = _command_queue.get_nowait()
                    print(f"[{source.upper()} CMD] {cmd}")
                    if not process_line(cmd, config):
                        return
                except queue.Empty:
                    break

            # Periodic agent check
            if time.time() - last_poll >= config.poll_interval:
                changes = check_agents(config)
                for change in changes:
                    print(f"[{time.strftime('%H:%M:%S')}] {change}")
                last_poll = time.time()

    except KeyboardInterrupt:
        print("\nBye!")


def kill_old_dispatchers():
    """Kill any old dispatcher processes."""
    my_pid = os.getpid()
    try:
        result = subprocess.run(
            ["pgrep", "-f", "council.dispatcher"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            pids = [int(p) for p in result.stdout.strip().split("\n") if p]
            killed = 0
            for pid in pids:
                if pid != my_pid:
                    try:
                        os.kill(pid, 9)
                        killed += 1
                    except ProcessLookupError:
                        pass
            if killed:
                print(f"[CLEANUP] Killed {killed} old dispatcher process(es)")
    except Exception:
        pass


def parse_args() -> tuple[Path, bool]:
    """Parse command line arguments. Returns (config_path, dry_run)."""
    import argparse
    parser = argparse.ArgumentParser(description="Council Dispatcher v3")
    parser.add_argument("config", nargs="?", default=str(Path.home() / ".council" / "config.yaml"),
                        help="Path to config file (default: ~/.council/config.yaml)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be sent without executing")
    args = parser.parse_args()
    return Path(args.config), args.dry_run


def main():
    kill_old_dispatchers()

    config_path, dry_run = parse_args()

    if not config_path.exists():
        print(f"Config not found: {config_path}")
        print("\nCreate a config file with:")
        print("""
agents:
  1:
    pane_id: "%0"
    name: "Agent 1"
    worktree: ~/projects/my-project
  2:
    pane_id: "%1"
    name: "Agent 2"

fifo_path: ~/.council/in.fifo
poll_interval: 2.0
""")
        sys.exit(1)

    config = load_config(config_path)
    config.dry_run = dry_run

    # Validate config (fail fast on errors)
    try:
        warnings = validate_config(config)
    except ConfigValidationError as e:
        print(f"[CONFIG ERROR]\n{e}")
        sys.exit(1)

    load_state(config)

    # Log startup
    log_event(None, "startup", extra={
        "agents": len(config.agents),
        "dry_run": config.dry_run,
        "config_path": str(config_path),
    })

    mode_str = " [DRY-RUN MODE]" if config.dry_run else ""
    print(f"=== Council Dispatcher v3{mode_str} ===")
    print(f"Loaded {len(config.agents)} agents from {config_path}")
    print()

    # Show agents and any warnings (smoke test)
    for agent in config.agents.values():
        if not tmux_pane_exists(agent.pane_id):
            status = "NOT FOUND"
        elif tmux_pane_in_copy_mode(agent.pane_id):
            status = "COPY MODE"
        else:
            status = "OK"
        print(f"  {agent.name}: {agent.pane_id} [{status}]")
    if warnings:
        print()
        for w in warnings:
            print(f"  [WARN] {w}")
    print()

    # Initialize Pushover
    pushover_client = None
    if config.pushover_email and config.pushover_password:
        pushover_client = pushover_init_client(config)

    # Initialize Telegram
    if config.telegram_bot_token and TELEGRAM_AVAILABLE:
        def telegram_callback(text: str):
            _command_queue.put(("telegram", text))

        telegram_bot = start_telegram_bot(
            token=config.telegram_bot_token,
            allowed_user_ids=config.telegram_allowed_user_ids,
            command_callback=telegram_callback,
        )
        if telegram_bot:
            print(f"  Telegram: enabled")
    print()

    # Initial check
    check_agents(config)
    show_status(config)

    # Run
    if config.fifo_path and config.fifo_path.exists():
        run_with_fifo(config, pushover_client)
    else:
        if config.fifo_path:
            print(f"FIFO not found: {config.fifo_path}")
            print(f"Create it with: mkfifo {config.fifo_path}")
            print("Falling back to stdin mode.\n")
        run_with_stdin(config, pushover_client)


if __name__ == "__main__":
    main()
