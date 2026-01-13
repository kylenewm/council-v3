#!/bin/bash

# Ralph Queue Manager
# Manages a queue of tasks for sequential Ralph execution

set -euo pipefail

QUEUE_FILE=".claude/ralph-queue.local.json"
LOCK_DIR="/tmp/ralph-queue.lock"

# Portable exclusive lock using mkdir (atomic on POSIX)
# Usage: with_lock command args...
with_lock() {
    local max_attempts=50
    local attempt=0

    # Acquire lock (mkdir is atomic)
    while ! mkdir "$LOCK_DIR" 2>/dev/null; do
        attempt=$((attempt + 1))
        if [[ $attempt -ge $max_attempts ]]; then
            echo "ERROR: Could not acquire lock after ${max_attempts} attempts" >&2
            exit 1
        fi
        sleep 0.1
    done

    # Ensure lock is released on exit
    trap "rmdir '$LOCK_DIR' 2>/dev/null" EXIT

    # Run command
    "$@"
    local result=$?

    # Release lock
    rmdir "$LOCK_DIR" 2>/dev/null
    trap - EXIT

    return $result
}

# Initialize queue file if it doesn't exist
init_queue() {
    if [[ ! -f "$QUEUE_FILE" ]]; then
        echo '{"tasks": [], "current_index": 0}' > "$QUEUE_FILE"
    fi
}

# Add tasks to queue (pipe-separated)
# Usage: queue-manager.sh add "task1 | task2 | task3" [--max-iterations N] [--completion-promise TEXT]
add_tasks() {
    init_queue

    local tasks_str="$1"
    shift

    # Parse optional args
    local max_iterations="10"
    local completion_promise="DONE"

    while [[ $# -gt 0 ]]; do
        case $1 in
            --max-iterations)
                max_iterations="$2"
                shift 2
                ;;
            --completion-promise)
                completion_promise="$2"
                shift 2
                ;;
            *)
                shift
                ;;
        esac
    done

    # Handle escaped pipes: replace \| with placeholder before splitting
    local PIPE_PLACEHOLDER="__PIPE_CHAR__"
    tasks_str="${tasks_str//\\|/$PIPE_PLACEHOLDER}"

    # Split by pipe and add each task
    IFS='|' read -ra TASKS <<< "$tasks_str"

    for task in "${TASKS[@]}"; do
        # Trim whitespace and restore escaped pipes
        task=$(echo "$task" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        task="${task//$PIPE_PLACEHOLDER/|}"

        if [[ -n "$task" ]]; then
            # Add task to queue
            local temp_file="${QUEUE_FILE}.tmp.$$"
            jq --arg task "$task" \
               --arg max "$max_iterations" \
               --arg promise "$completion_promise" \
               '.tasks += [{
                   "prompt": $task,
                   "max_iterations": ($max | tonumber),
                   "completion_promise": $promise,
                   "status": "pending"
               }]' "$QUEUE_FILE" > "$temp_file"
            mv "$temp_file" "$QUEUE_FILE"

            echo "Queued: $task"
        fi
    done

    echo ""
    echo "Queue now has $(jq '.tasks | length' "$QUEUE_FILE") tasks"
}

# Get next pending task and mark it as running
get_next() {
    init_queue

    # Find first pending task
    local next_task=$(jq -r '
        .tasks | to_entries |
        map(select(.value.status == "pending")) |
        first |
        if . then .value else null end
    ' "$QUEUE_FILE")

    if [[ "$next_task" == "null" ]] || [[ -z "$next_task" ]]; then
        echo ""
        return 1
    fi

    # Mark it as running
    local temp_file="${QUEUE_FILE}.tmp.$$"
    jq '
        (.tasks | to_entries | map(select(.value.status == "pending")) | first | .key) as $idx |
        if $idx then .tasks[$idx].status = "running" else . end
    ' "$QUEUE_FILE" > "$temp_file"
    mv "$temp_file" "$QUEUE_FILE"

    echo "$next_task"
}

# Mark current running task as complete
complete_current() {
    init_queue

    local temp_file="${QUEUE_FILE}.tmp.$$"
    jq '
        (.tasks | to_entries | map(select(.value.status == "running")) | first | .key) as $idx |
        if $idx then .tasks[$idx].status = "complete" else . end
    ' "$QUEUE_FILE" > "$temp_file"
    mv "$temp_file" "$QUEUE_FILE"

    echo "Marked current task complete"
}

# Show queue status
status() {
    init_queue

    local total=$(jq '.tasks | length' "$QUEUE_FILE")
    local pending=$(jq '[.tasks[] | select(.status == "pending")] | length' "$QUEUE_FILE")
    local running=$(jq '[.tasks[] | select(.status == "running")] | length' "$QUEUE_FILE")
    local complete=$(jq '[.tasks[] | select(.status == "complete")] | length' "$QUEUE_FILE")

    echo "Ralph Queue Status"
    echo "=================="
    echo "Total: $total | Pending: $pending | Running: $running | Complete: $complete"
    echo ""

    # Show tasks with status
    jq -r '.tasks | to_entries[] |
        "\(.key + 1). [\(.value.status | ascii_upcase)] \(.value.prompt | .[0:60])..."
    ' "$QUEUE_FILE" 2>/dev/null || echo "Queue empty"
}

# Clear queue
clear_queue() {
    echo '{"tasks": [], "current_index": 0}' > "$QUEUE_FILE"
    echo "Queue cleared"
}

# Check if queue has pending tasks
has_pending() {
    init_queue
    local pending=$(jq '[.tasks[] | select(.status == "pending")] | length' "$QUEUE_FILE")
    [[ $pending -gt 0 ]]
}

# Main command dispatcher
# Wrap mutating operations with flock for atomicity
case "${1:-status}" in
    add)
        shift
        with_lock add_tasks "$@"
        ;;
    next)
        with_lock get_next
        ;;
    complete)
        with_lock complete_current
        ;;
    status)
        # Read-only, no lock needed
        status
        ;;
    clear)
        with_lock clear_queue
        ;;
    has-pending)
        # Read-only, no lock needed
        has_pending && echo "yes" || echo "no"
        ;;
    *)
        echo "Usage: queue-manager.sh {add|next|complete|status|clear|has-pending}"
        exit 1
        ;;
esac
