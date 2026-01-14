# Test Checklist

## Pre-Flight (Before Real Work)

### Dispatcher Basics
- [ ] `status` - shows all 4 agents
- [ ] `1: echo test` - reaches pane %0
- [ ] `2: echo test` - reaches pane %1
- [ ] `3: echo test` - reaches pane %3
- [ ] `4: echo test` - reaches pane %4

### Queue Features
- [ ] `1: task1 | task2` - queues correctly
- [ ] `queue 1` - shows queued tasks
- [ ] `clear 1` - empties queue

### Auto-Continue (Test Carefully)
- [ ] `auto 1` - enables (shows [AUTO])
- [ ] `stop 1` - disables
- [ ] `reset 1` - resets circuit breaker

### Telegram (If Configured)
- [ ] Send message to bot from phone
- [ ] Message routes to correct agent

### Notifications (If Configured)
- [ ] Agent completes task → Pushover notification received

---

## Known Limitations

1. **Circuit breaker trip** - Only testable with real Claude work (needs git commits)
2. **Auto-continue loop** - Only triggers when agent becomes "ready"
3. **FIFO input** - Requires Wispr Flow setup

---

## Quick Smoke Test

```bash
# 1. Start dispatcher
python3 -m council.dispatcher.simple

# 2. Check all agents
status

# 3. Send to each agent (safe - just echo)
1: echo hello from dispatcher
2: echo hello from dispatcher
3: echo hello from dispatcher
4: echo hello from dispatcher

# 4. Verify in tmux
# Ctrl-b then arrow keys to check each pane

# 5. Quit
quit
```

---

## If Something Breaks

```bash
# Check logs
tail -20 ~/.council/logs/$(date +%Y-%m-%d).jsonl | jq .

# Check pane status
tmux list-panes -a -F "#{pane_id} #{pane_current_command}"

# Kill stuck dispatcher
pkill -f "council.dispatcher"
```
