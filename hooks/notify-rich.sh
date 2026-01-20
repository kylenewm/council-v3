#!/bin/bash
# Rich notification hook - reads current_task.txt for context

TASK_FILE="$HOME/.council/current_task.txt"

# Default values
AGENT_NAME="Agent"
PROJECT="unknown"
TASK="needs attention"

# Source task context if available
if [[ -f "$TASK_FILE" ]]; then
    source "$TASK_FILE"
fi

# Truncate task for notification
SHORT_TASK="${TASK:0:60}"
[[ ${#TASK} -gt 60 ]] && SHORT_TASK="${SHORT_TASK}..."

# Mac notification
osascript -e "display notification \"$SHORT_TASK\" with title \"$AGENT_NAME ($PROJECT)\" sound name \"Blow\""

# Pushover notification (if configured)
PUSHOVER_USER="${PUSHOVER_USER_KEY:-}"
PUSHOVER_TOKEN="${PUSHOVER_API_TOKEN:-}"

if [[ -n "$PUSHOVER_USER" && -n "$PUSHOVER_TOKEN" ]]; then
    curl -s \
        --form-string "token=$PUSHOVER_TOKEN" \
        --form-string "user=$PUSHOVER_USER" \
        --form-string "title=$AGENT_NAME ($PROJECT)" \
        --form-string "message=$SHORT_TASK" \
        https://api.pushover.net/1/messages.json > /dev/null
fi
