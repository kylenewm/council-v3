# Project: Council v3

## Overview

Voice/phone command router for multiple Claude Code agents in tmux panes.

**What it does:**
- Routes commands from FIFO (voice), Pushover (phone), Telegram to tmux panes
- Auto-continue with circuit breaker (git-based progress detection)
- Notifications (Mac + Pushover)

**What agents do themselves:**
- Task management (TodoWrite)
- Work verification
- Deciding when they're done

## Before Anything Else

Read STATE.md for current status.

---

## Stack

- Python 3.9+
- tmux (raw subprocess, not libtmux)
- PyYAML for config
- terminal-notifier for Mac notifications
- Pushover for phone notifications
- Telegram bot via curl

## Commands

```bash
# Run dispatcher
python -m council.dispatcher.simple

# Or with explicit config
python -m council.dispatcher.simple ~/.council/config.yaml
```

## Testing

```bash
pytest tests/ -v
```

## Dispatcher Commands

| Command | What |
|---------|------|
| `1: <text>` | Send text to agent 1 |
| `auto 1` | Enable auto-continue for agent 1 |
| `stop 1` | Disable auto-continue |
| `reset 1` | Reset circuit breaker |
| `status` | Show all agents |
| `quit` | Exit |

---

## Invariants

### tmux
- Always use stable pane IDs (`%N`) not indexes
- Always use `send-keys -l` for literal text
- Always send Enter as separate call
- Never send to panes in copy mode

### Circuit Breaker
- Opens after 3 iterations without git progress
- Reset with `reset N` command
- Agents with open circuit don't auto-continue

### Notifications
- 30 second cooldown per agent
- Mac notification + Pushover (if configured)

---

## Key Files

| File | Purpose |
|------|---------|
| `council/dispatcher/simple.py` | Main dispatcher (~650 lines) |
| `council/dispatcher/gitwatch.py` | Git progress detection |
| `council/dispatcher/telegram.py` | Telegram bot (curl-based) |
| `~/.council/config.yaml` | Runtime config |
| `~/.council/state.json` | Persisted state |

## Config Example

```yaml
agents:
  1:
    pane_id: "%0"
    name: "Agent 1"
    worktree: ~/projects/my-project
  2:
    pane_id: "%1"
    name: "Agent 2"
    worktree: ~/projects/other-project

fifo_path: ~/.council/in.fifo
poll_interval: 2.0

pushover:
  user_key: "xxx"
  api_token: "xxx"
  email: "you@email.com"
  password: "xxx"
  device_name: "council"

telegram:
  bot_token: "xxx"
  allowed_user_ids: [123456789]
```

---

## Slash Commands

| Command | What |
|---------|------|
| `/test` | Run pytest |
| `/commit` | Stage and commit changes |
| `/ship` | Test, commit, push, PR |
| `/done` | Verify before marking complete |
| `/review` | Spawn review subagent |

## Subagents

| Agent | Purpose |
|-------|---------|
| `code-architect` | Design before implementing |
| `verify-app` | Test implementation works |
| `code-simplifier` | Reduce complexity |
| `build-validator` | Check deployment readiness |

---

## Context Files

| File | Purpose |
|------|---------|
| STATE.md | Current work, decisions |
| LOG.md | History (append-only) |
