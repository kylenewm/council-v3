# STATE.md

## Current Phase: Ready to Use (2026-01-12)

Building council-v3 as hybrid of:
1. **Dispatcher** (from council-v2) - FIFO, Pushover, Telegram, tmux routing
2. **Boris Setup** (community interpretation) - .claude/agents, commands, settings, CLAUDE.md
3. **Simplified guardrails** - circuit breaker (no-progress only), optional gitwatch

## Research Complete

See `CLAUDE-RESEARCH.md` for full analysis.

**Key finding:** The bcherny-claude repo is a community interpretation, not Boris's actual files.

**Council-v3 has 80-90% of Boris's PUBLIC setup:**
- ✅ All 5 agents (identical structure)
- ✅ 13 commands (superset of Boris's 5)
- ✅ PostToolUse, Stop, Notification hooks
- ❌ MCP integrations (Slack, BigQuery, Sentry)
- ❌ GitHub action (@.claude on PRs)

**Better repos exist** (claude-code-showcase has 4.1k stars) but council-v3's unique value is the dispatcher (voice, phone, multi-agent routing).

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
- [x] Test with real agents - ALL 4 DETECTED, ROUTING WORKS
- [x] Copy custom commands from council-v2
- [x] Merge Boris + custom commands + Notification hook
- [x] Update config to 2 agents (Council + DeepResearch)
- [x] Reset state.json for clean circuits
- [x] Sandbox test Boris components - ALL PASSED
- [x] Research Boris's actual setup vs community repos
- [x] Document findings in CLAUDE-RESEARCH.md

## Current Agent Configuration

| Agent | Project | Status |
|-------|---------|--------|
| Agent 1 (Council) | council-v3 | Ready |
| Agent 2 (DeepResearch) | deep-research-v0 | Ready |

**Shared setup copied to deep-research-v0:**
- ✅ 5 Boris agents (code-architect, verify-app, etc.)
- ✅ Stop hook for rich notifications

## v1 Features Complete

- [x] Rich notifications (Stop hook + Pushover)
- [x] Ralph plugin installed and documented
- [x] power() function added to sandbox calculator
- [x] modulo() function added to sandbox calculator
- [x] CLAUDE-RESEARCH.md with Boris comparison
- [x] QUIRKS.md with common issues
- [x] Push to GitHub - all changes pushed to origin
- [x] Notification system tested end-to-end (Mac + Pushover)
- [x] Dispatcher writes current_task.txt for rich notifications

## How to Run

```bash
# Start dispatcher
python -m council.dispatcher.simple

# Commands:
#   1: <text>    Send to agent 1
#   status       Show all agents
#   quit         Exit
```
