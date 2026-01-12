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
    1: <text>    Send <text> to agent 1
    auto 1       Enable auto-continue for agent 1
    stop 1       Disable auto-continue for agent 1
    reset 1      Reset circuit breaker for agent 1
    status       Show agent status
    quit         Exit
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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

# Thread-safe queue for commands from background threads (Telegram)
_command_queue: queue.Queue = queue.Queue()

# Lock for state file access
_state_lock = threading.Lock()

STATE_FILE = Path.home() / ".council" / "state.json"
CURRENT_TASK_FILE = Path.home() / ".council" / "current_task.txt"

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


NOTIFY_COOLDOWN = 30.0  # Seconds between notifications per agent
MAX_NO_PROGRESS = 3  # Open circuit after this many iterations without progress


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
    state = {"version": 1, "agents": {}}
    for agent_id, agent in config.agents.items():
        state["agents"][str(agent_id)] = {
            "auto_enabled": agent.auto_enabled,
            "circuit_state": agent.circuit_state,
            "no_progress_streak": agent.no_progress_streak,
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
            print(f"[STATE] Restored from {STATE_FILE}")
        except Exception as e:
            print(f"[WARN] Could not load state: {e}")


def write_current_task(agent: Agent, task: str):
    """Write current task to file for rich notifications."""
    try:
        CURRENT_TASK_FILE.parent.mkdir(parents=True, exist_ok=True)
        content = f"{agent.name}: {task}\n"
        CURRENT_TASK_FILE.write_text(content)
    except Exception as e:
        print(f"[WARN] Could not write current task: {e}")


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
        agents[int(agent_id)] = Agent(
            id=int(agent_id),
            pane_id=agent_cfg.get("pane_id", ""),
            name=agent_cfg.get("name", f"Agent {agent_id}"),
            worktree=worktree,
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

            new_state = detect_state(output)
            if new_state != agent.state:
                old_state = agent.state
                agent.state = new_state

                if new_state == "ready":
                    changes.append(f"{agent.name} is READY")

                    # Check progress via git (if we have a previous snapshot)
                    if agent.worktree and agent.last_snapshot:
                        new_snapshot = take_snapshot(agent.worktree)
                        if has_progress(agent.last_snapshot, new_snapshot):
                            agent.no_progress_streak = 0
                            changes.append(f"  -> progress detected, streak reset")
                        else:
                            agent.no_progress_streak += 1
                            changes.append(f"  -> no progress ({agent.no_progress_streak}/{MAX_NO_PROGRESS})")
                        agent.last_snapshot = new_snapshot

                    # Circuit breaker check
                    if agent.no_progress_streak >= MAX_NO_PROGRESS:
                        if agent.circuit_state != "open":
                            agent.circuit_state = "open"
                            changes.append(f"  -> CIRCUIT OPEN (no progress)")
                            notify(f"{agent.name}: circuit open - no progress", config)
                            save_state(config)

                    # Auto-continue (simplified - just send "continue")
                    if agent.auto_enabled and agent.circuit_state == "closed":
                        if agent.worktree:
                            agent.last_snapshot = take_snapshot(agent.worktree)
                        if tmux_send(agent.pane_id, "continue"):
                            changes.append(f"  -> auto-continue sent")
                            agent.state = "working"
                    elif not agent.auto_enabled:
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
        print("  1: <text>  - Send <text> to agent 1")
        print("  auto 1     - Enable auto-continue for agent 1")
        print("  stop 1     - Disable auto-continue for agent 1")
        print("  reset 1    - Reset circuit breaker for agent 1")
        print("  status     - Show agent status")
        print("  quit       - Exit\n")
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
            print(f"{agent.name}: circuit RESET")
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
            if agent.worktree:
                agent.last_snapshot = take_snapshot(agent.worktree)
            if tmux_send(agent.pane_id, command):
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


def main():
    kill_old_dispatchers()

    config_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / ".council" / "config.yaml"

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
    load_state(config)

    print("=== Council Dispatcher v3 ===")
    print(f"Loaded {len(config.agents)} agents from {config_path}")
    print()

    # Validate panes
    for agent in config.agents.values():
        if tmux_pane_exists(agent.pane_id):
            print(f"  {agent.name}: {agent.pane_id}")
        else:
            print(f"  {agent.name}: {agent.pane_id} NOT FOUND")
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
