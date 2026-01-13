# Architecture

## Module Inventory

| File | Lines | Purpose |
|------|-------|---------|
| `council/council.py` | 345 | Multi-model draft, critique, synthesis via OpenRouter |
| `council/client.py` | 139 | OpenRouter API client with retry logic |
| `council/cli.py` | 251 | CLI commands (`council plan`, `council refine`) |
| `council/bootstrap.py` | 314 | Generate CLAUDE.md and project files from plan |
| `council/dispatcher/simple.py` | 955 | Main dispatcher - routing, queue, circuit breaker |
| `council/dispatcher/telegram.py` | 229 | Telegram bot for voice/text commands |
| `council/dispatcher/gitwatch.py` | 120 | Git progress detection for circuit breaker |

## Config Files

| File | Purpose |
|------|---------|
| `~/.council/config.yaml` | Agent definitions, API keys, input sources |
| `~/.council/state.json` | Persisted state (queues, circuit breaker status) |
| `~/.council/in.fifo` | Named pipe for voice input |

---

## Execution Traces

### 1. Voice Command → Agent

```
Telegram receives voice → transcribes → writes to FIFO
    ↓
Dispatcher reads FIFO → parses "1: build rate limiter"
    ↓
Checks agent 1: READY, circuit CLOSED, queue empty
    ↓
Routes to tmux pane %0 → sends text + Enter
    ↓
Agent executes → completes → pane shows prompt
    ↓
Dispatcher detects ready → sends notification
```

### 2. LLM Council Planning

```
council plan "build auth system"
    ↓
Draft phase (parallel):
  - Opus drafts approach A
  - GPT drafts approach B
    ↓
Critique phase:
  - Each model critiques all drafts
    ↓
Synthesis:
  - Chair (Opus) combines into PLAN.md
```

### 3. Task Queue

```
"1: task A | task B | task C"
    ↓
task A sent immediately, [B, C] queued
    ↓
A completes → dequeue B → send
    ↓
B completes → dequeue C → send
    ↓
C completes → queue empty → notify
```

### 4. Circuit Breaker

```
auto 1 enabled → agent loops without progress
    ↓
3 iterations, no git commits
    ↓
Circuit trips: CLOSED → OPEN
    ↓
Auto-continue disabled, user notified
    ↓
User runs "reset 1" → OPEN → CLOSED
```
