#!/bin/bash
# Cross-Project Workflow Simulation Cleanup
# Removes mock projects, tmux session, and test config.

echo "=== Cleaning up simulation ==="

# Kill tmux session
if tmux has-session -t sim 2>/dev/null; then
    echo "Killing tmux session 'sim'..."
    tmux kill-session -t sim
else
    echo "No tmux session 'sim' found."
fi

# Remove mock projects
for name in council research codeflow; do
    dir="/tmp/sim-$name"
    if [ -d "$dir" ]; then
        echo "Removing $dir..."
        rm -rf "$dir"
    fi
done

# Remove test config
if [ -f ~/.council/test-config.yaml ]; then
    echo "Removing test config..."
    rm -f ~/.council/test-config.yaml
fi

echo ""
echo "=== Cleanup complete ==="
