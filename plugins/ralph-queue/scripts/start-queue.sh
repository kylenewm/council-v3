#!/bin/bash

# Start Ralph Queue Execution
# Gets the first pending task and sets up Ralph loop state

set -euo pipefail

QUEUE_FILE=".claude/ralph-queue.local.json"
RALPH_STATE_FILE=".claude/ralph-loop.local.md"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
QUEUE_MANAGER="$SCRIPT_DIR/queue-manager.sh"

# Check queue exists
if [[ ! -f "$QUEUE_FILE" ]]; then
    echo "No queue file found. Use /ralph-queue to add tasks first."
    exit 1
fi

# Check for pending tasks
PENDING=$("$QUEUE_MANAGER" has-pending)
if [[ "$PENDING" != "yes" ]]; then
    echo "No pending tasks in queue."
    "$QUEUE_MANAGER" status
    exit 0
fi

# Check if Ralph loop already active
if [[ -f "$RALPH_STATE_FILE" ]]; then
    echo "Ralph loop already active. Cancel it first with /cancel-ralph"
    exit 1
fi

# Get next task
NEXT_TASK=$("$QUEUE_MANAGER" next)

if [[ -z "$NEXT_TASK" ]]; then
    echo "Failed to get next task"
    exit 1
fi

# Extract task details
PROMPT=$(echo "$NEXT_TASK" | jq -r '.prompt')
MAX_ITER=$(echo "$NEXT_TASK" | jq -r '.max_iterations')
PROMISE=$(echo "$NEXT_TASK" | jq -r '.completion_promise')

# Create Ralph state file
mkdir -p .claude
cat > "$RALPH_STATE_FILE" << EOF
---
iteration: 1
max_iterations: $MAX_ITER
completion_promise: "$PROMISE"
---

$PROMPT
EOF

echo "Starting Ralph Queue execution"
echo "=============================="
echo "Task: $PROMPT"
echo "Max iterations: $MAX_ITER"
echo "Completion promise: $PROMISE"
echo ""
echo "Remaining in queue: $(jq '[.tasks[] | select(.status == "pending")] | length' "$QUEUE_FILE")"
echo ""
echo "OUTPUT_PROMPT:$PROMPT"
