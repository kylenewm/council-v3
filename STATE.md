# STATE.md

## Current Phase: Initial Setup (2026-01-11)

Building council-v3 as hybrid of:
1. **Dispatcher** (from council-v2) - FIFO, Pushover, Telegram, tmux routing
2. **Boris Setup** (from bcherny-claude) - .claude/agents, commands, settings, CLAUDE.md
3. **Simplified guardrails** - circuit breaker (no-progress only), optional gitwatch

## Architecture

```
council-v3/
├── council/dispatcher/
│   └── simple.py          # ~250 lines (routing + simple circuit breaker)
├── .claude/
│   ├── agents/            # code-architect, verify-app, code-simplifier, etc.
│   ├── commands/          # commit, ship, test-cycle, etc.
│   └── settings.json      # permissions + Stop hooks for notifications
├── CLAUDE.md              # Project memory
├── STATE.md               # Current work
└── LOG.md                 # History
```

## What's Different from council-v2

| Removed | Why |
|---------|-----|
| tasks.py | Agents use TodoWrite |
| Error signature extraction | Overkill |
| Task file parsing | Agents manage own todos |

| Kept | Why |
|------|-----|
| FIFO input | Voice routing (unique value) |
| Pushover | Phone notifications (unique value) |
| Telegram | Phone commands (unique value) |
| tmux routing | Multi-agent dispatch |
| Circuit breaker | Stuck detection (simplified) |

| Added | Why |
|-------|-----|
| .claude/agents/ | Boris-style subagents |
| .claude/commands/ | Workflow automation |
| Stop hooks | Native notifications |

## Implementation Progress

- [x] Create council-v3 repo
- [x] Clone Boris template
- [x] Copy Boris .claude/ structure (agents, commands, settings, skills)
- [x] Copy essential dispatcher from council-v2 (gitwatch.py, telegram.py)
- [x] Simplify simple.py (1095 -> 875 lines)
- [x] Add Stop hooks for notifications
- [x] Create CLAUDE.md
- [ ] Test with real agents

## How to Run

```bash
# Start dispatcher
python -m council.dispatcher.simple

# Commands:
#   1: <text>    Send to agent 1
#   status       Show all agents
#   quit         Exit
```
