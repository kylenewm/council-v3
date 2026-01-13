#!/bin/bash
# Test simulation - sends commands directly to tmux panes
# Run after sim-setup.sh

set -e

# Check session exists
if ! tmux has-session -t sim 2>/dev/null; then
    echo "ERROR: No 'sim' session. Run sim-setup.sh first."
    exit 1
fi

# Get pane IDs from config
CONFIG=~/.council/test-config.yaml
if [ ! -f "$CONFIG" ]; then
    echo "ERROR: No config at $CONFIG"
    exit 1
fi

echo "=== Testing Simulation ==="

# Test 1: Send echo to each pane
echo "Test 1: Sending echo to each pane..."
for i in 0 1 2; do
    pane_id=$(tmux display-message -p -t "sim:main.$i" '#{pane_id}')
    tmux send-keys -t "$pane_id" "echo 'Hello from pane $i'" Enter
done
sleep 1

# Test 2: Verify panes received commands
echo "Test 2: Capturing pane output..."
for i in 0 1 2; do
    pane_id=$(tmux display-message -p -t "sim:main.$i" '#{pane_id}')
    output=$(tmux capture-pane -t "$pane_id" -p)
    if echo "$output" | grep -q "Hello from pane"; then
        echo "  Pane $i: OK"
    else
        echo "  Pane $i: FAILED - output was:"
        echo "$output" | tail -5
        exit 1
    fi
done

# Test 3: Git commit in one pane
echo "Test 3: Testing git commit in council pane..."
pane_council=$(tmux display-message -p -t "sim:main.0" '#{pane_id}')
tmux send-keys -t "$pane_council" "echo 'test' >> STATE.md && git add -A && git commit -m 'test commit'" Enter
sleep 1

# Verify commit happened
cd /tmp/sim-council
commit_count=$(git rev-list --count HEAD)
if [ "$commit_count" -ge 2 ]; then
    echo "  Git commit: OK ($commit_count commits)"
else
    echo "  Git commit: FAILED"
    exit 1
fi

echo ""
echo "=== All Tests Passed ==="
echo ""
echo "Simulation is ready for dispatcher testing:"
echo "  python -m council.dispatcher.simple ~/.council/test-config.yaml"
