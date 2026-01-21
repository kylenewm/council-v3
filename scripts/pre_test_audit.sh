#!/bin/bash
# Pre-test audit to prevent freezes
# Run this BEFORE any dispatcher testing

set -e

echo "=== Pre-Test Audit ==="

# 1. Check for hanging dispatcher processes
echo -n "1. Dispatcher processes: "
PROCS=$(pgrep -f "council.dispatcher" 2>/dev/null || true)
if [ -n "$PROCS" ]; then
    echo "FOUND - killing..."
    pkill -9 -f "council.dispatcher" 2>/dev/null || true
    sleep 1
else
    echo "clean"
fi

# 2. Check for stuck python processes (simple.py specifically)
echo -n "2. Python simple.py: "
PROCS=$(pgrep -f "python.*simple\.py" 2>/dev/null || true)
if [ -n "$PROCS" ]; then
    echo "FOUND - killing..."
    pkill -9 -f "python.*simple\.py" 2>/dev/null || true
    sleep 1
else
    echo "clean"
fi

# 3. Check FIFO state
FIFO_PATH="${HOME}/.council/in.fifo"
echo -n "3. FIFO ($FIFO_PATH): "
if [ -p "$FIFO_PATH" ]; then
    # Check if anything is blocking on the FIFO
    FIFO_PROCS=$(lsof "$FIFO_PATH" 2>/dev/null | grep -v "^COMMAND" || true)
    if [ -n "$FIFO_PROCS" ]; then
        echo "BLOCKED - processes attached"
        echo "$FIFO_PROCS"
        echo "   Recreating FIFO..."
        rm -f "$FIFO_PATH"
        mkfifo "$FIFO_PATH"
    else
        echo "exists, clear"
    fi
else
    echo "missing - creating..."
    mkdir -p "$(dirname "$FIFO_PATH")"
    mkfifo "$FIFO_PATH"
fi

# 4. Check state.json for corruption
STATE_FILE="${HOME}/.council/state.json"
echo -n "4. State file: "
if [ -f "$STATE_FILE" ]; then
    if python3 -c "import json; json.load(open('$STATE_FILE'))" 2>/dev/null; then
        echo "valid JSON"
    else
        echo "CORRUPT - backing up and removing"
        mv "$STATE_FILE" "${STATE_FILE}.corrupt.$(date +%s)"
    fi
else
    echo "not found (will be created)"
fi

# 5. Check tmux session exists
echo -n "5. TMux council session: "
if tmux has-session -t council 2>/dev/null; then
    PANES=$(tmux list-panes -t council -F '#{pane_id}' 2>/dev/null | wc -l | tr -d ' ')
    echo "exists ($PANES panes)"
else
    echo "MISSING - create with: tmux new-session -d -s council"
fi

# 6. Quick syntax check on dispatcher
echo -n "6. Dispatcher syntax: "
if python3 -m py_compile council/dispatcher/simple.py 2>/dev/null; then
    echo "valid"
else
    echo "SYNTAX ERROR"
    exit 1
fi

echo ""
echo "=== Audit Complete ==="
echo "Safe to run dispatcher tests."
