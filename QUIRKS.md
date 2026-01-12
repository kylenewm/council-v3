# QUIRKS.md

> Common issues and solutions for council-v3

---

## Dispatcher Issues

### Dispatcher won't start in tmux pane

**Symptom:** `tmux send-keys` sends command but nothing happens, pane shows old output.

**Cause:** tmux pane buffer not refreshing, or previous process state interfering.

**Solutions:**
1. Kill existing dispatchers first: `pkill -f "council.dispatcher.simple"`
2. Reset state.json to clear circuit breakers
3. Clear the pane: `tmux send-keys -t %1 'clear' Enter`
4. Run dispatcher directly: `PYTHONUNBUFFERED=1 python3 -m council.dispatcher.simple`

### Circuit breaker opens immediately

**Symptom:** Dispatcher shows "no progress (1/3)" right after sending command.

**Cause:** Git-based progress detection checks for new commits. If agent is just reading/planning, no commits = no progress.

**Solution:** This is expected behavior during planning phase. Circuit only opens after 3 consecutive no-progress checks.

### "zsh: killed" message

**Symptom:** Dispatcher shows `zsh: killed PYTHONUNBUFFERED=1 python3 -m council.di`

**Cause:** Process was killed (manually or by system).

**Solution:** Restart dispatcher. Check if multiple instances running with `pgrep -f "council.dispatcher"`.

---

## tmux Issues

### Can't see second agent pane

**Symptom:** Only one Claude Code instance visible.

**Solution:**
```bash
# Check existing panes
tmux list-panes -a -F "#{pane_id} #{pane_current_command}"

# Create new pane if needed
tmux split-window -h -t council -c ~/Downloads/council-v3

# Start Claude in new pane
tmux send-keys -t %3 'claude' Enter
```

### tmux capture-pane shows stale content

**Symptom:** `tmux capture-pane` returns old output even after commands sent.

**Cause:** Buffer lag or pane not active.

**Solution:** Wait a few seconds, or check process directly with `pgrep`.

---

## Agent Issues

### Agent not receiving prompts

**Symptom:** FIFO echo succeeds but agent doesn't respond.

**Cause:**
1. Dispatcher not running
2. Wrong pane ID in config
3. Agent in wrong directory

**Debug:**
```bash
# Check dispatcher running
pgrep -f "council.dispatcher.simple"

# Check dispatcher output
tail -f /tmp/claude/-Users-kylenewman-Downloads/tasks/*.output

# Verify pane IDs match config
tmux list-panes -a -F "#{pane_id} #{pane_current_path}"
```

### Both agents on same project = conflicts?

**Risk:** Two agents editing same file simultaneously.

**Prevention:**
- Assign clear file boundaries in specs
- Agent 1: settings.json, notification scripts
- Agent 2: simple.py, ralph scripts
- Use explicit "Do NOT modify X" in prompts

---

## Config Issues

### Agent 2 pointing to wrong project

**Symptom:** Agent 2 working on deep-research-v0 instead of council-v3.

**Solution:** Update `~/.council/config.yaml`:
```yaml
agents:
  2:
    worktree: ~/Downloads/council-v3  # Not deep-research-v0
```

Then restart dispatcher.

---

## Quick Diagnostics

```bash
# Is dispatcher running?
pgrep -f "council.dispatcher.simple"

# What's in each pane?
tmux list-panes -a -F "#{pane_id} #{pane_current_command} #{pane_current_path}"

# Check dispatcher log
tail -20 /tmp/claude/-Users-kylenewman-Downloads/tasks/*.output

# Reset everything
pkill -f "council.dispatcher.simple"
echo '{"version":1,"agents":{"1":{"auto_enabled":false,"circuit_state":"closed","no_progress_streak":0},"2":{"auto_enabled":false,"circuit_state":"closed","no_progress_streak":0}}}' > ~/.council/state.json
```
