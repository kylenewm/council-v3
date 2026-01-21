# Council v3

Multi-agent orchestration for Claude Code.

- **Dispatcher** — Routes commands to Claude Code instances running in tmux panes
- **Input sources** — Unix socket (for voice via Shortcuts/Wispr), Telegram bot, Pushover
- **Task queue** — Queue tasks per agent, auto-dequeue when ready
- **Auto-continue** — Keeps agents working with circuit breaker (git-based progress detection)
- **Mode injection** — Inject context (strict/sandbox/plan/review) to control behavior
- **Quality hooks** — TDD enforcement, auto-formatting, lint checks via Claude Code hooks
- **Slash commands** — `/test`, `/commit`, `/ship`, `/review`, `/inject`, and more
- **LLM Council** — Optional multi-model planning (draft → critique → synthesize)
- **Plugins** — Ralph loop/queue for long-running and batched tasks

## Demo

https://github.com/user-attachments/assets/2b279dc6-2026-4c22-aab2-2c879b29f730

*Note: This demo shows an earlier version with just tmux panes and Pushover notifications. Current version includes mode injection, quality hooks, plugins, and more.*

## Architecture

```
Inputs (Voice/Telegram/Socket) → Dispatcher → Agents (tmux) → Outputs (Notifications/Git)
                                     ↑
                              LLM Council (optional multi-model planning)
```

**Full feature list:** [docs/FEATURES.md](docs/FEATURES.md)

---

## Quick Start

### 1. Install

```bash
git clone https://github.com/kylenewm/council-v3.git
cd council-v3
pip install -e .
```

### 2. Configure

```bash
cp config.example.yaml ~/.council/config.yaml
```

Edit `~/.council/config.yaml`:

```yaml
agents:
  1:
    pane_id: "%0"
    name: "Agent1"
    worktree: ~/projects/project1
  2:
    pane_id: "%1"
    name: "Agent2"
    worktree: ~/projects/project2

socket_path: ~/.council/council.sock

pushover:  # Optional - phone notifications
  user_key: "your-user-key"
  api_token: "your-api-token"

telegram:  # Optional - voice/phone commands
  bot_token: "your-bot-token"
  allowed_user_ids: [123456789]
```

### 3. Start tmux with agent panes

```bash
tmux new-session -d -s council
tmux split-window -h
tmux attach -t council
```

### 4. Run the dispatcher

```bash
python -m council.dispatcher.simple
```

---

## Dispatcher Commands

| Command | What |
|---------|------|
| `1: <text>` | Send to agent 1 |
| `queue 1 "task"` | Add task to agent's queue |
| `queue 1` | Show queue |
| `status` | Show all agents |
| `auto 1` / `stop 1` | Toggle auto-continue |
| `reset 1` | Reset circuit breaker |

Send via socket:
```bash
echo "1: do something" | nc -U ~/.council/council.sock
```

---

## Slash Commands (in Claude Code)

| Command | What |
|---------|------|
| `/test` | Run tests (auto-detects framework) |
| `/done` | Verify before marking complete |
| `/commit` | Stage and commit |
| `/ship` | test → commit → push → PR |
| `/review` | Code review via subagent |
| `/inject <mode>` | Set mode (strict/sandbox/plan/review) |

**Full command list:** [docs/FEATURES.md](docs/FEATURES.md#slash-commands)

---

## Mode Injection

Control agent behavior by injecting context into prompts.

| Mode | Purpose |
|------|---------|
| `strict` | Production: verify before done, don't touch scope |
| `sandbox` | Fast iteration, fixtures OK, skip edge cases |
| `plan` | Design before building, wait for approval |
| `review` | Adversarial critique, requires evidence |

```bash
/inject strict          # Set mode
echo "sandbox" > .council/mode  # Project-local override
```

---

## Debugging

Logs: `~/.council/logs/YYYY-MM-DD.jsonl`

```bash
tail -50 ~/.council/logs/$(date +%Y-%m-%d).jsonl | jq .
```

## Testing

```bash
pytest tests/ -v
```

---

## Documentation

| Doc | What |
|-----|------|
| [FEATURES.md](docs/FEATURES.md) | Complete feature reference |
| [SYSTEM_REFERENCE.md](docs/SYSTEM_REFERENCE.md) | Quick reference cheat sheet |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Architecture & execution traces |
| [OPERATING_GUIDE.md](docs/OPERATING_GUIDE.md) | Full operating guide |
