# Project: Council v3

## Overview

Voice/phone command router for multiple Claude Code agents in tmux panes.

**What it does:**
- Routes commands from Unix socket (voice), Pushover (phone), Telegram to tmux panes
- Auto-continue with circuit breaker (git-based progress detection)
- Notifications (Mac + Pushover + Telegram)

**What agents do themselves:**
- Task management (TodoWrite)
- Work verification
- Deciding when they're done

## Before Anything Else

1. Read `docs/SYSTEM_REFERENCE.md` - Full system overview (modes, commands, plugins)
2. Read `STATE.md` - Current work status

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
# Unit tests (safe to run from Claude Code)
pytest tests/ -v

# Pre-test audit (run before any dispatcher testing)
./scripts/pre_test_audit.sh

# E2E tests (run in SEPARATE tmux pane, NOT from Claude Code)
./scripts/e2e_test.sh
```

**WARNING**: Never run the live dispatcher from Claude Code - it causes freezes due to blocking I/O. Always run `pre_test_audit.sh` first, then test in a separate tmux pane.

## Dispatcher Commands

| Command | What |
|---------|------|
| `1: <text>` | Send text to agent 1 |
| `queue 1 "<task>"` | Add task to agent 1's queue |
| `queue 1` | Show queue for agent 1 |
| `clear 1` | Clear queue for agent 1 |
| `auto 1` | Enable auto-continue for agent 1 |
| `stop 1` | Disable auto-continue |
| `reset 1` | Reset circuit breaker |
| `progress 1 mark` | Manually mark progress (resets streak) |
| `status` | Show all agents (includes Q:N for queue depth) |
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

### Task Queue
- Add tasks explicitly: `queue 1 "task text"`
- Dequeues automatically when agent becomes ready
- Queue takes priority over auto-continue
- Respects circuit breaker (no dequeue if open)
- Persists to state.json across restarts

### Notifications
- 30 second cooldown per agent
- Mac notification + Pushover (if configured)

---

## Key Files

| File | Purpose |
|------|---------|
| `council/dispatcher/simple.py` | Main dispatcher (~2000 lines) |
| `council/dispatcher/socket_server.py` | Unix socket server for commands |
| `council/dispatcher/gitwatch.py` | Git progress detection |
| `council/dispatcher/telegram.py` | Telegram bot (curl-based) |
| `council/council.py` | LLM Council - multi-model planning |
| `council/cli.py` | CLI: `council plan/debate/refine/bootstrap` |
| `scripts/send_command.sh` | Helper to send commands via socket |
| `scripts/check_invariants.py` | Path violation checker |
| `scripts/audit_done.py` | Transcript auditor |
| `scripts/pre_test_audit.sh` | Run BEFORE dispatcher testing |
| `scripts/e2e_test.sh` | E2E test (run in separate tmux pane) |
| `~/.council/config.yaml` | Runtime config |
| `~/.council/state.json` | Persisted state |
| `~/.council/council.sock` | Unix socket (created by dispatcher) |

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

# Socket path (default: ~/.council/council.sock)
socket_path: ~/.council/council.sock
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

## Sending Commands

```bash
# Via helper script
./scripts/send_command.sh "1: do something"

# Via netcat directly
echo "status" | nc -U ~/.council/council.sock

# Via Python
from council.dispatcher.socket_server import send_command
send_command("~/.council/council.sock", "1: task")
```

---

## Slash Commands

| Command | What |
|---------|------|
| `/test` | Run tests (auto-detects framework) |
| `/test-cycle` | Generate + run tests progressively |
| `/commit` | Stage and commit changes |
| `/ship` | Test, commit, push, PR |
| `/done` | Verify before marking complete |
| `/review` | Code review (subagent) |
| `/inject <mode>` | Set mode: strict/sandbox/plan/review |
| `/save` | Update STATE.md + LOG.md |

## Subagents

Agent definitions in `.claude/agents/` (invoke via `claude --agent <name>`):

| Agent | Purpose |
|-------|---------|
| `code-architect` | Design reviews, architecture decisions |
| `verify-app` | Test implementation, edge cases |
| `code-simplifier` | Reduce complexity |
| `build-validator` | Deployment readiness |
| `oncall-guide` | Debug production issues |

---

## Workflow

For non-trivial tasks:

```
1. Plan      → /inject plan OR council plan "idea"
2. Implement → /inject strict, write code
3. Test      → /test or /test-cycle
4. Verify    → /done (checks requirements)
5. Review    → /review (fresh eyes)
6. Ship      → /ship (test → commit → push → PR)
```

**Shortcuts:**
- Bug fix: implement → /test → /done → /commit
- Docs: edit → /commit

---

## Context Files

| File | Purpose |
|------|---------|
| STATE.md | Current work, decisions |
| LOG.md | History (append-only) |
| REFLECTIONS.md | Self-reflection on struggles, gaps, and future optimizations |

---

## Post-Task Reflection (This Project Only)

**Council-v3 is the meta project** - it defines the tooling other projects use. Reflections here improve the setup for all projects.

After completing work on council-v3, optionally note friction in REFLECTIONS.md:
- What was harder than expected?
- What tooling/commands didn't work well?
- What would make this easier?

**Don't copy REFLECTIONS.md to other projects** - it's only for improving council-v3 itself.

---

## Future Tasks

After completing current work, pick from this queue:

1. **Cross-agent visibility** - See what other agents produced
2. **Refactor simple.py** - 1400+ lines is unwieldy, split into modules
3. **Voice command parsing** - Better handling of complex multi-step voice input
4. **Status dashboard** - Web or TUI view of all agent states
5. **Jungle Gym web dashboard** - Real-time visual of E2E tests running, historical results, charts
6. **Auto-config from task description** - Infer strict/sandbox/plan mode from task text
