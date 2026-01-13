#!/bin/bash

# Ralph Queue Stop Hook
# Runs AFTER Ralph's stop hook to check if we should start next queued task
# Priority 100 ensures this runs AFTER ralph-loop's hook (default priority 0)

set -euo pipefail

# Prevent re-entry loop
LOCK_FILE="/tmp/ralph-queue-processing.lock"
if [[ -f "$LOCK_FILE" ]]; then
    exit 0
fi
trap "rm -f $LOCK_FILE" EXIT
touch "$LOCK_FILE"

QUEUE_FILE=".claude/ralph-queue.local.json"
RALPH_STATE_FILE=".claude/ralph-loop.local.md"
QUEUE_MANAGER="${CLAUDE_PLUGIN_ROOT}/scripts/queue-manager.sh"

# Read hook input from stdin
HOOK_INPUT=$(cat)

# Check if ralph-loop plugin is available (required dependency)
if ! command -v claude &>/dev/null; then
    echo "Ralph Queue: claude command not found" >&2
    exit 0
fi

# Only act if queue file exists and has running task
if [[ ! -f "$QUEUE_FILE" ]]; then
    exit 0
fi

# Check if there's a running task in queue
RUNNING_COUNT=$(jq '[.tasks[] | select(.status == "running")] | length' "$QUEUE_FILE" 2>/dev/null || echo "0")

if [[ "$RUNNING_COUNT" -eq 0 ]]; then
    exit 0
fi

# Wait for ralph-loop's hook to complete (removes state file)
# Use retry loop instead of fixed sleep to handle variable timing
MAX_RETRIES=25  # 25 * 0.2s = 5s max wait
RETRIES=0

while [[ -f "$RALPH_STATE_FILE" ]]; do
    RETRIES=$((RETRIES + 1))
    if [[ $RETRIES -ge $MAX_RETRIES ]]; then
        # Ralph loop still active after max wait, let Ralph handle it
        exit 0
    fi
    sleep 0.2
done

# State file gone - Ralph completed

# Ralph completed! Mark current queue task complete
"$QUEUE_MANAGER" complete

# Check for next pending task
NEXT_TASK=$("$QUEUE_MANAGER" next 2>/dev/null || echo "")

if [[ -z "$NEXT_TASK" ]] || [[ "$NEXT_TASK" == "" ]]; then
    # No more tasks - queue complete!
    echo "Ralph Queue: All tasks complete!"
    exit 0
fi

# Extract task details
PROMPT=$(echo "$NEXT_TASK" | jq -r '.prompt')
MAX_ITER=$(echo "$NEXT_TASK" | jq -r '.max_iterations')
PROMISE=$(echo "$NEXT_TASK" | jq -r '.completion_promise')

# Create new Ralph state file for next task
mkdir -p .claude
cat > "$RALPH_STATE_FILE" << EOF
---
iteration: 1
max_iterations: $MAX_ITER
completion_promise: "$PROMISE"
---

$PROMPT
EOF

echo "Ralph Queue: Starting next task ($MAX_ITER max iterations)"
echo "Task: ${PROMPT:0:60}..."

# Block exit and feed next task prompt
jq -n \
    --arg prompt "$PROMPT" \
    --arg msg "Ralph Queue: Starting next task ($(jq '[.tasks[] | select(.status == "pending")] | length' "$QUEUE_FILE") remaining)" \
    '{
        "decision": "block",
        "reason": $prompt,
        "systemMessage": $msg
    }'

exit 0
