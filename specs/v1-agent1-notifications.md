# Agent 1 Task: Simple Rich Notifications (v1)

## Objective

Enhance Stop hook to show WHAT was done, not just "agent finished."

## Approach

Parse Claude's recent output for context. Don't require Claude to write anything special.

## Task 1: Install and Test

1. Read the current `.claude/settings.json`
2. Update the Stop hook to include recent git activity:

```json
"Stop": [{
  "matcher": ".*",
  "hooks": [{
    "type": "command",
    "command": "LAST_COMMIT=$(git log -1 --pretty='%s' 2>/dev/null || echo 'No commits'); terminal-notifier -title 'Council: $(basename $(pwd))' -subtitle \"$LAST_COMMIT\" -message 'Agent finished' -sound default 2>/dev/null || true"
  }]
}]
```

3. Test by making a small change and committing

## Task 2: Add Pushover Context

After Task 1 works, create a script that sends richer Pushover notifications:

Create `~/.council/scripts/rich-notify.sh`:
```bash
#!/bin/bash
PROJECT=$(basename $(pwd))
LAST_COMMIT=$(git log -1 --pretty='%s' 2>/dev/null || echo 'No recent commits')
FILES_CHANGED=$(git diff --name-only HEAD~1 2>/dev/null | head -3 | tr '\n' ', ')

# Send to Pushover (tokens from config)
curl -s \
  --form-string "token=${PUSHOVER_TOKEN}" \
  --form-string "user=${PUSHOVER_USER}" \
  --form-string "title=Council: $PROJECT" \
  --form-string "message=$LAST_COMMIT | Files: $FILES_CHANGED" \
  https://api.pushover.net/1/messages.json
```

## Constraints

- Do NOT modify `council/dispatcher/simple.py`
- Do NOT create complex status file systems
- Keep it simple - just enhance existing hooks

## Success Criteria

1. Stop hook shows last commit message
2. Mac notification has context
3. (Task 2) Pushover gets richer message

## Files to Modify

- `.claude/settings.json` - Update Stop hook
- `~/.council/scripts/rich-notify.sh` - Create notification script
