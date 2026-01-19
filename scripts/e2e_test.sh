#!/bin/bash
# E2E Test for Dispatcher (Socket Mode)
# Run this in a SEPARATE tmux pane, not from Claude Code
#
# Usage:
#   1. Open a new tmux pane: ctrl-b c
#   2. Run: ./scripts/e2e_test.sh
#   3. Watch output for pass/fail
#
# What it tests:
#   1. Dispatcher starts
#   2. Socket receives commands
#   3. Status command works
#   4. Agent command sends correctly
#   5. Rapid command stress test

set -e

SOCKET_PATH="${HOME}/.council/council.sock"
SEND_CMD="${HOME}/Downloads/council-v3/scripts/send_command.sh"
LOG_FILE="/tmp/dispatcher_e2e_$(date +%Y%m%d_%H%M%S).log"
TIMEOUT=10

echo "=== E2E Dispatcher Test (Socket Mode) ==="
echo "Log: $LOG_FILE"
echo ""

# Cleanup from previous runs
pkill -f "council.dispatcher" 2>/dev/null || true
rm -f "$SOCKET_PATH" 2>/dev/null || true
sleep 1

# Start dispatcher in background with output capture
echo "1. Starting dispatcher..."
cd /Users/kylenewman/Downloads/council-v3
python3 -u -m council.dispatcher.simple > "$LOG_FILE" 2>&1 &
DISPATCHER_PID=$!
sleep 2

# Check it started
if ! ps -p $DISPATCHER_PID > /dev/null 2>&1; then
    echo "FAIL: Dispatcher didn't start"
    cat "$LOG_FILE"
    exit 1
fi
echo "   PASS: Dispatcher running (PID $DISPATCHER_PID)"

# Check socket exists
if [ ! -S "$SOCKET_PATH" ]; then
    echo "FAIL: Socket not created at $SOCKET_PATH"
    cat "$LOG_FILE"
    kill $DISPATCHER_PID 2>/dev/null
    exit 1
fi
echo "   PASS: Socket created"

# Test 2: Socket receives status command
echo "2. Testing socket reception (status)..."
echo "status" | nc -U "$SOCKET_PATH"
sleep 1

if grep -q "\[SOCKET\] status" "$LOG_FILE"; then
    echo "   PASS: Socket received 'status'"
else
    echo "   FAIL: No [SOCKET] output"
    echo "   Log contents:"
    cat "$LOG_FILE"
    kill $DISPATCHER_PID 2>/dev/null
    exit 1
fi

# Test 3: Status output shown
echo "3. Testing status output..."
if grep -q "Agent Status" "$LOG_FILE" || grep -q "No agents configured" "$LOG_FILE"; then
    echo "   PASS: Status command executed"
else
    echo "   WARN: Status output unclear (may be OK)"
fi

# Test 4: Agent command (if agents configured)
echo "4. Testing agent command..."
echo "1: test hello" | nc -U "$SOCKET_PATH"
sleep 1

if grep -q "\[SOCKET\] 1: test hello" "$LOG_FILE"; then
    echo "   PASS: Agent command received"
    # Check if it was sent or rejected
    if grep -q "Unknown agent: 1" "$LOG_FILE"; then
        echo "   INFO: Agent 1 not configured (expected in test env)"
    elif grep -q "->.*test hello" "$LOG_FILE"; then
        echo "   PASS: Command sent to agent"
    fi
else
    echo "   WARN: Agent command may not have been received"
fi

# Test 5: Rapid command stress test
echo "5. Testing rapid commands..."
for i in $(seq 1 20); do
    echo "rapid_test_$i" | nc -U "$SOCKET_PATH" &
done
wait
sleep 2

RAPID_COUNT=$(grep -c "rapid_test_" "$LOG_FILE" || echo "0")
echo "   Received $RAPID_COUNT of 20 rapid commands"
if [ "$RAPID_COUNT" -ge 18 ]; then
    echo "   PASS: Rapid command handling OK (>= 90%)"
else
    echo "   WARN: Some rapid commands may have been lost"
fi

# Test 6: Help command
echo "6. Testing help command..."
echo "help" | nc -U "$SOCKET_PATH"
sleep 0.5

if grep -q "Commands:" "$LOG_FILE"; then
    echo "   PASS: Help command works"
else
    echo "   WARN: Help output unclear"
fi

# Cleanup
echo ""
echo "7. Cleanup..."
kill $DISPATCHER_PID 2>/dev/null || true
sleep 1
echo "   Dispatcher stopped"

# Verify socket removed
if [ -S "$SOCKET_PATH" ]; then
    echo "   WARN: Socket file still exists"
else
    echo "   PASS: Socket cleaned up"
fi

echo ""
echo "=== Test Complete ==="
echo "Full log at: $LOG_FILE"
echo ""
echo "To manually test:"
echo "  1. Start dispatcher: python3 -u -m council.dispatcher.simple"
echo "  2. Send command: echo '1: test' | nc -U ~/.council/council.sock"
echo "  3. Or use: ./scripts/send_command.sh '1: test'"
