# Agent 1 Task: Rich Notifications System

## Objective

Enhance council-v3's notification system so you know WHAT an agent is working on and WHAT input it needs, not just "agent finished."

## Current State

**Stop hook** (`settings.json`):
```json
"Stop": [{
  "matcher": ".*",
  "hooks": [{
    "type": "command",
    "command": "terminal-notifier -title 'Council v3' -message 'Agent finished in $(basename $(pwd))' -sound default 2>/dev/null || true"
  }]
}]
```

**Problem:** Just says "agent finished" - no context about what was done or what's needed.

**Pushover:** Currently used by dispatcher for basic alerts.

## Requirements

### 1. Status File System

Before Claude stops, it should write a brief status to a known location:

```
~/.council/status/<agent_id>.json
```

Format:
```json
{
  "agent": "Council",
  "timestamp": "2026-01-12T10:30:00",
  "task": "Implementing history feature for calculator",
  "status": "completed|needs_input|blocked|error",
  "summary": "Added get_history() and clear_history() functions. All 12 tests passing.",
  "needs_input": null,  // or "Which database backend should I use?"
  "files_changed": ["calculator.py", "test_calculator.py"],
  "next_step": "Ready for review"
}
```

### 2. Enhanced Stop Hook

Read the status file and send rich notification:

```bash
# Read status and format notification
STATUS_FILE=~/.council/status/$(basename $(pwd)).json
if [ -f "$STATUS_FILE" ]; then
  TITLE=$(jq -r '.agent' "$STATUS_FILE")
  SUBTITLE=$(jq -r '.task' "$STATUS_FILE")
  MESSAGE=$(jq -r '.summary' "$STATUS_FILE")
  NEEDS=$(jq -r '.needs_input // empty' "$STATUS_FILE")

  if [ -n "$NEEDS" ]; then
    MESSAGE="NEEDS INPUT: $NEEDS"
  fi

  terminal-notifier -title "$TITLE" -subtitle "$SUBTITLE" -message "$MESSAGE" -sound default
fi
```

### 3. Pushover Integration

Send rich notifications to Pushover with context:

```bash
curl -s \
  --form-string "token=$PUSHOVER_TOKEN" \
  --form-string "user=$PUSHOVER_USER" \
  --form-string "title=$TITLE: $STATUS" \
  --form-string "message=$SUMMARY" \
  --form-string "priority=$([ "$STATUS" = "needs_input" ] && echo 1 || echo 0)" \
  https://api.pushover.net/1/messages.json
```

Priority levels:
- `needs_input` → Priority 1 (high, makes sound)
- `completed` → Priority 0 (normal)
- `error` → Priority 1 (high)

### 4. CLAUDE.md Instruction

Add to CLAUDE.md so agents know to write status:

```markdown
## Before Stopping

Before completing a task, write status to `~/.council/status/<project>.json`:
- task: What you were working on
- status: completed|needs_input|blocked|error
- summary: 1-2 sentence summary
- needs_input: Question if you need human input
- files_changed: List of modified files
```

## Files to Create/Modify

1. **Create:** `~/.council/status/` directory
2. **Create:** `council/dispatcher/notifications.py` - Rich notification sender
3. **Modify:** `.claude/settings.json` - Enhanced Stop hook
4. **Modify:** `CLAUDE.md` - Add status writing instructions

## Constraints

- Do NOT modify `council/dispatcher/simple.py` (Agent 2 may be working there)
- Do NOT modify any files in `council/dispatcher/` except creating new ones
- Keep notifications under 256 chars for Pushover
- Use jq for JSON parsing (should be installed)

## Success Criteria

1. Agent writes status file before stopping
2. Stop hook reads status and sends rich notification
3. Mac notification shows task + summary
4. Pushover notification includes context
5. "needs_input" notifications are high priority

## Test Plan

1. Have agent do a simple task
2. Verify status file created
3. Verify Mac notification has context
4. Verify Pushover notification received with details
