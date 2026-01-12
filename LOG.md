# LOG.md

> Append-only. Never edit old entries.

---

## 2026-01-11

### Project Created: council-v3

**Goal:** Hybrid of council-v2 dispatcher + Boris-style Claude Code setup.

**Sources:**
- council-v2: Working dispatcher with FIFO, Pushover, Telegram, tmux, circuit breaker
- bcherny-claude: Boris Cherny's .claude/ setup (agents, commands, settings)
- Agent 1's suggest_plan.md: Simplification recommendations

**Decision: Option D (Modular Hybrid)**

Keep unique value:
- FIFO input (voice)
- Pushover in/out (phone)
- Telegram bot (phone commands)
- tmux routing
- Simple circuit breaker (no-progress detection only)

Remove:
- tasks.py (agents use TodoWrite)
- Error signature extraction (overkill)
- Task file parsing logic

Add:
- .claude/agents/ (code-architect, verify-app, code-simplifier, build-validator, oncall-guide)
- .claude/commands/ (commit-push-pr, quick-commit, test-and-fix, review-changes, first-principles)
- .claude/settings.json (permissions + Stop hooks)

**Research Summary:**
- Boris runs 5+ parallel Claude sessions with plan mode + verification loops
- Ralph provides circuit breaker via iteration limits
- Native Stop hooks can replace custom notification logic
- Agents should be self-sufficient with Boris-style config

---

### Implementation Complete

**Files created:**
```
council-v3/
├── .claude/
│   ├── agents/           # 5 subagents from Boris template
│   ├── commands/         # 5 commands from Boris template
│   ├── skills/           # first-principles skill
│   └── settings.json     # Permissions + Stop hook for notifications
├── council/dispatcher/
│   ├── simple.py         # Simplified dispatcher (875 lines, down from 1095)
│   ├── gitwatch.py       # Git progress detection (unchanged)
│   └── telegram.py       # Telegram bot (unchanged)
├── config/
│   └── config.yaml.example
├── CLAUDE.md
├── STATE.md
├── LOG.md
└── pyproject.toml
```

**Line count comparison:**
- council-v2 simple.py: 1095 lines
- council-v3 simple.py: 875 lines (-20%)

**What was removed:**
- tasks.py (agents use TodoWrite)
- Task file parsing in simple.py
- Error signature extraction

**What was kept:**
- FIFO input (voice)
- Pushover in/out (phone)
- Telegram bot (phone commands)
- tmux routing
- Circuit breaker (git-based progress detection)
- State persistence

**What was added:**
- Boris subagents (code-architect, verify-app, code-simplifier, build-validator, oncall-guide)
- Boris commands (commit-push-pr, quick-commit, test-and-fix, review-changes, first-principles)
- Stop hook for native notifications
- Python permissions in settings.json

---
