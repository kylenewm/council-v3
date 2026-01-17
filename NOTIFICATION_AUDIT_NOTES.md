# Notification System Audit Notes

## Current Problem
Notifications fire at wrong times and with wrong content. User gets spammed with useless "Awaiting next task" messages.

## What We've Discovered

### 1. State Detection Race Condition
- When command is sent, we set `agent.state = "working"`
- On next poll (could be immediate), `detect_state()` checks tmux output
- If Claude hasn't started processing yet, it still shows "ready" prompt
- State change detected: "working" → "ready" → notification fires
- **Root cause**: We're trusting tmux visual state as ground truth, but there's lag

### 2. Task Context is Global (FIXED to per-agent)
- Was: Single `~/.council/current_task.txt` for all agents
- Now: `~/.council/tasks/agent_{id}.txt` per agent
- Still has issues with what gets written there

### 3. Non-meaningful Commands Overwrite Real Tasks
- "continue", "y", "n" etc. would overwrite the actual task description
- Added skip list but it's incomplete

### 4. Startup Spam
- When dispatcher starts, it polls all agents
- Any agent in "ready" state triggers notification
- Even if no work was done since last session

## Patches Applied (HACKY - need proper fix)
1. Per-agent task files
2. Skip "continue" etc. from task file
3. Command grace period (5s)
4. Startup grace period (10s) - partially implemented

## What Actually Needs to Happen

### Real Questions to Answer
1. **When should a notification fire?**
   - Only when agent transitions from actively-working to ready
   - AND there's meaningful task context
   - AND it's not a false positive (agent just slow to start)

2. **What is "meaningful task context"?**
   - The original task that was sent (not "continue")
   - Should persist until a NEW real task is sent

3. **How do we know agent actually worked?**
   - Git progress? (already have this)
   - Time spent in "working" state?
   - DONE_REPORT detection?

4. **What's the right state machine?**
   - Current: unknown → ready ↔ working → ready (fires notification)
   - Problem: "ready" is detected by visual prompt, which lags

### Potential Real Fixes
1. **Don't trust visual state for "done"** - Use DONE_REPORT detection or git progress
2. **Track "confirmed working" state** - Only count as working if we see thinking indicator
3. **Persist original task separately** - Don't let "continue" touch it
4. **Debounce state changes** - Require state to be stable for N seconds

## Files Changed
- `council/dispatcher/simple.py` - Multiple patches
- `~/.council/hooks/notify-rich.sh` - Created (unused now)
- `~/.claude/settings.json` - Updated notification hook

## Testing Needed
- Send real task, wait for completion, verify notification content
- Send "continue", verify no notification
- Restart dispatcher, verify no startup spam
- Multiple agents working simultaneously

## Next Steps
1. Do proper audit of state machine
2. Understand detect_state() logic
3. Understand poll loop timing
4. Design proper fix, not patches
