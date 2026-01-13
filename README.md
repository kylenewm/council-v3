# Council v3

Most AI coding setups use one model, run one task at a time, and require you at the keyboard. This limits impact in a time where software development and product management are rapidly transforming.

Council v3 adds:
- **Multi-model planning** — Multiple models draft independently, critique each other, then synthesize a final plan
- **Parallel agents** — Run multiple Claude Code instances across projects with task queuing
- **Voice/phone input** — Send commands via Telegram, get notifications via Pushover
- **Auto-continue** — Circuit breaker catches stuck loops, keeps work moving without babysitting

Visual Overview:

https://github.com/user-attachments/assets/2b279dc6-2026-4c22-aab2-2c879b29f730


## Architecture

```
Inputs (Voice/Telegram/CLI) → LLM Council → Dispatcher → Agents (tmux) → Outputs (Notifications/Git)
```

**Detailed docs:** [Architecture & Execution Traces](docs/ARCHITECTURE.md)

## Setup

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

fifo_path: ~/.council/in.fifo

pushover:  # Optional - for phone notifications
  user_key: "your-user-key"
  api_token: "your-api-token"

telegram:  # Optional - for voice/phone commands
  bot_token: "your-bot-token"
  allowed_user_ids: [123456789]
```

### 3. Start tmux with agent panes

```bash
tmux new-session -d -s council
tmux split-window -h
# Add more panes as needed for more agents
tmux attach -t council
```

### 4. Run the dispatcher

```bash
python -m council.dispatcher.simple
```

## Commands

| Command | What |
|---------|------|
| `1: <text>` | Send to agent 1 |
| `1: t1 \| t2` | Queue multiple tasks |
| `status` | Show all agents |
| `auto 1` / `stop 1` | Toggle auto-continue |
| `reset 1` | Reset circuit breaker |

## Module Inventory

| File | Purpose |
|------|---------|
| `council/council.py` | Multi-model draft, critique, synthesis |
| `council/client.py` | OpenRouter API client |
| `council/cli.py` | CLI commands |
| `council/dispatcher/simple.py` | Main dispatcher (routing, queue, circuit breaker) |
| `council/dispatcher/telegram.py` | Telegram bot |
| `council/dispatcher/gitwatch.py` | Git progress detection |

## Testing

```bash
pytest tests/ -v  # 84 tests
```
