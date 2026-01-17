# BROKEN STATE - 2026-01-17

## What's Broken

1. **Dispatcher not sending notifications** - Commands logged as "ok" but no notifications fire
2. **State detection may be wrong** - Agent stayed "ready" even after task sent
3. **Multiple restarts didn't fix it** - Restarted dispatcher 4+ times, same issue

## Root Causes (suspected)

1. **Dispatcher running in FIFO mode** - stdout goes to FIFO interaction, not visible
2. **No state transitions detected** - Agents already "ready", no working→ready transition = no notification
3. **Task files have stale/wrong content** - "1" as task, "what is useful here" in old file

## What Was Changed Today

1. Fixed `_startup_time` initialization
2. Added stuck thinking cooldown
3. Added `generate_rich_summary()` for Telegram
4. Added `notify_agent_ready()` and `notify_agent_dialog()`
5. Added dialog content extraction
6. Added dash separator support for commands (2-1, 2:1)
7. **Removed Claude Code Notification hook** from settings.json

## Files Modified

- `council/dispatcher/simple.py` - All notification logic
- `council/dispatcher/gitwatch.py` - Added git helpers
- `~/.claude/settings.json` - Removed Notification hook
- `NOTIFICATION_AUDIT_NOTES.md` - Created

## Commits Made

- b12957b - Accept dash separator
- 80b0239 - Add dialog notifications
- db64caa - Fix notification bugs and add rich Telegram summaries

## To Debug Next

1. Run dispatcher in foreground to see all output
2. Check why state transitions aren't being detected
3. Verify `check_agents()` is actually being called in poll loop
4. Check if FIFO mode breaks the poll loop
5. Test notification functions in isolation

## Quick Test

```bash
# Test notification directly
python3 -c "
from council.dispatcher.simple import Agent, Config, notify_agent_ready
from pathlib import Path

agent = Agent(id=1, pane_id='%0', name='Test', worktree=Path('.'))
config = Config(agents={}, telegram_bot_token='YOUR_TOKEN')
notify_agent_ready(agent, config)
"
```

## Current State

- Dispatcher process running but not polling correctly
- Telegram bot connected but no notifications sent
- All agents show "ready" state
- Logs show commands sent but no state change events
