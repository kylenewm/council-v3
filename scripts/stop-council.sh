#!/bin/bash
# Stop Council - kill session and dispatcher
# Usage: ./scripts/stop-council.sh

echo "=== Stopping Council ==="

# Kill dispatcher if running
if pgrep -f "council.dispatcher" > /dev/null; then
    echo "Killing dispatcher..."
    pkill -f "council.dispatcher"
fi

# Kill tmux session
if tmux has-session -t council 2>/dev/null; then
    echo "Killing tmux session..."
    tmux kill-session -t council
fi

echo "Done."
