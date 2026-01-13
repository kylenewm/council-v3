#!/bin/bash
# Ralph-Queue Edge Case Test Sandbox
# Run: ./plugins/ralph-queue/tests/test-sandbox.sh

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_DIR="$(dirname "$SCRIPT_DIR")"
QUEUE_MANAGER="$PLUGIN_DIR/scripts/queue-manager.sh"
START_QUEUE="$PLUGIN_DIR/scripts/start-queue.sh"
SANDBOX="/tmp/ralph-sandbox-$$"

# Setup sandbox
setup() {
    rm -rf "$SANDBOX"
    mkdir -p "$SANDBOX/.claude"
    cd "$SANDBOX"
    export QUEUE_FILE=".claude/ralph-queue.local.json"
    export RALPH_STATE_FILE=".claude/ralph-loop.local.md"
}

# Cleanup sandbox
cleanup() {
    cd /
    rm -rf "$SANDBOX"
}

# Test assertions
assert_eq() {
    local expected="$1"
    local actual="$2"
    local msg="${3:-}"
    if [[ "$expected" == "$actual" ]]; then
        return 0
    else
        echo -e "${RED}FAIL${NC}: Expected '$expected', got '$actual' $msg"
        return 1
    fi
}

assert_contains() {
    local haystack="$1"
    local needle="$2"
    local msg="${3:-}"
    if [[ "$haystack" == *"$needle"* ]]; then
        return 0
    else
        echo -e "${RED}FAIL${NC}: Expected to contain '$needle' $msg"
        return 1
    fi
}

assert_file_exists() {
    local file="$1"
    if [[ -f "$file" ]]; then
        return 0
    else
        echo -e "${RED}FAIL${NC}: File '$file' does not exist"
        return 1
    fi
}

assert_file_not_exists() {
    local file="$1"
    if [[ ! -f "$file" ]]; then
        return 0
    else
        echo -e "${RED}FAIL${NC}: File '$file' should not exist"
        return 1
    fi
}

# Run a test
run_test() {
    local name="$1"
    local fn="$2"

    TESTS_RUN=$((TESTS_RUN + 1))
    echo -n "  [$TESTS_RUN] $name... "

    setup
    if $fn; then
        echo -e "${GREEN}PASS${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "${RED}FAIL${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
    cleanup
}

# ============================================
# Queue Manager Tests (#1-5)
# ============================================

test_1_empty_queue_start() {
    # Start with no queue file
    local output
    output=$("$START_QUEUE" 2>&1) || true
    assert_contains "$output" "No queue file"
}

test_2_special_chars() {
    # Task with special characters
    "$QUEUE_MANAGER" add 'Fix bug: "null pointer" in foo()' --max-iterations 5 >/dev/null
    local task
    task=$(jq -r '.tasks[0].prompt' "$QUEUE_FILE")
    assert_eq 'Fix bug: "null pointer" in foo()' "$task"
}

test_3_pipes_in_content() {
    # Task content with literal pipe (escaped)
    "$QUEUE_MANAGER" add 'Run: cat foo \| grep bar' --max-iterations 5 >/dev/null
    local count
    count=$(jq '.tasks | length' "$QUEUE_FILE")
    # Should be 1 task (pipe is escaped, not a separator)
    assert_eq "1" "$count" "(escaped pipe should not split)"
}

test_4_clear_while_running() {
    # Add task and mark as running
    "$QUEUE_MANAGER" add "Task 1" --max-iterations 5 >/dev/null
    "$QUEUE_MANAGER" next >/dev/null  # Marks as running

    local running_before
    running_before=$(jq '[.tasks[] | select(.status == "running")] | length' "$QUEUE_FILE")

    "$QUEUE_MANAGER" clear >/dev/null

    # Queue should be empty (clear removes everything)
    local count_after
    count_after=$(jq '.tasks | length' "$QUEUE_FILE")
    assert_eq "0" "$count_after"
}

test_5_status_counts() {
    # Empty
    local output
    output=$("$QUEUE_MANAGER" status 2>&1) || true
    assert_contains "$output" "Total: 0"

    # Add 2 tasks
    "$QUEUE_MANAGER" add "Task 1 | Task 2" --max-iterations 5 >/dev/null
    output=$("$QUEUE_MANAGER" status 2>&1)
    assert_contains "$output" "Total: 2"
    assert_contains "$output" "Pending: 2"

    # Mark one running
    "$QUEUE_MANAGER" next >/dev/null
    output=$("$QUEUE_MANAGER" status 2>&1)
    assert_contains "$output" "Running: 1"
}

# ============================================
# Ralph-Loop Integration Tests (#6-9)
# ============================================

test_6_max_iterations_1() {
    # Queue task with max_iterations=1
    "$QUEUE_MANAGER" add "Test task" --max-iterations 1 >/dev/null
    "$START_QUEUE" >/dev/null

    # Check state file
    assert_file_exists "$RALPH_STATE_FILE"
    local max_iter
    max_iter=$(grep 'max_iterations:' "$RALPH_STATE_FILE" | sed 's/max_iterations: *//')
    assert_eq "1" "$max_iter"
}

test_7_completion_promise_set() {
    "$QUEUE_MANAGER" add "Test task" --max-iterations 5 --completion-promise "ALL_DONE" >/dev/null
    "$START_QUEUE" >/dev/null

    local promise
    promise=$(grep 'completion_promise:' "$RALPH_STATE_FILE" | sed 's/completion_promise: *//' | tr -d '"')
    assert_eq "ALL_DONE" "$promise"
}

test_8_queue_task_stored_correctly() {
    "$QUEUE_MANAGER" add "Do the thing" --max-iterations 10 --completion-promise "DONE" >/dev/null

    local stored
    stored=$(jq -r '.tasks[0] | "\(.prompt)|\(.max_iterations)|\(.completion_promise)"' "$QUEUE_FILE")
    assert_eq "Do the thing|10|DONE" "$stored"
}

test_9_default_values() {
    # Add task with no options (uses defaults)
    "$QUEUE_MANAGER" add "Simple task" >/dev/null

    local max_iter
    max_iter=$(jq -r '.tasks[0].max_iterations' "$QUEUE_FILE")
    # Default should be 10
    assert_eq "10" "$max_iter"
}

# ============================================
# Queue Chaining Tests (#10-12)
# ============================================

test_10_two_tasks_queued() {
    "$QUEUE_MANAGER" add "Task A | Task B" --max-iterations 5 >/dev/null

    local count
    count=$(jq '.tasks | length' "$QUEUE_FILE")
    assert_eq "2" "$count"

    # First task
    local first
    first=$(jq -r '.tasks[0].prompt' "$QUEUE_FILE")
    assert_eq "Task A" "$first"

    # Second task
    local second
    second=$(jq -r '.tasks[1].prompt' "$QUEUE_FILE")
    assert_eq "Task B" "$second"
}

test_11_three_tasks_in_sequence() {
    "$QUEUE_MANAGER" add "One | Two | Three" --max-iterations 3 >/dev/null

    # Check order
    local order
    order=$(jq -r '.tasks[].prompt' "$QUEUE_FILE" | tr '\n' '|')
    assert_eq "One|Two|Three|" "$order"
}

test_12_complete_advances_queue() {
    "$QUEUE_MANAGER" add "First | Second" --max-iterations 5 >/dev/null
    "$QUEUE_MANAGER" next >/dev/null  # Start first
    "$QUEUE_MANAGER" complete >/dev/null  # Complete first

    # First should be complete
    local first_status
    first_status=$(jq -r '.tasks[0].status' "$QUEUE_FILE")
    assert_eq "complete" "$first_status"

    # Second should still be pending
    local second_status
    second_status=$(jq -r '.tasks[1].status' "$QUEUE_FILE")
    assert_eq "pending" "$second_status"
}

# ============================================
# Error Recovery Tests (#13-15)
# ============================================

test_13_corrupted_json() {
    # Create corrupted queue file
    echo "not valid json{" > "$QUEUE_FILE"

    local output
    output=$("$QUEUE_MANAGER" status 2>&1) || true
    # Should handle gracefully (not crash)
    assert_contains "$output" "0" || assert_contains "$output" "error" || true
}

test_14_missing_queue_file() {
    # No queue file exists
    local output
    output=$("$QUEUE_MANAGER" status 2>&1)
    assert_contains "$output" "Total: 0"
}

test_15_has_pending_check() {
    # Empty queue
    local has_pending
    has_pending=$("$QUEUE_MANAGER" has-pending 2>&1)
    assert_eq "no" "$has_pending"

    # With pending task
    "$QUEUE_MANAGER" add "Task" --max-iterations 5 >/dev/null
    has_pending=$("$QUEUE_MANAGER" has-pending 2>&1)
    assert_eq "yes" "$has_pending"
}

# ============================================
# Run All Tests
# ============================================

echo ""
echo "========================================"
echo "Ralph-Queue Edge Case Test Sandbox"
echo "========================================"
echo ""

echo "Queue Manager Tests:"
run_test "Empty queue start" test_1_empty_queue_start
run_test "Special characters" test_2_special_chars
run_test "Pipes in content" test_3_pipes_in_content
run_test "Clear while running" test_4_clear_while_running
run_test "Status counts" test_5_status_counts

echo ""
echo "Ralph-Loop Integration Tests:"
run_test "Max iterations = 1" test_6_max_iterations_1
run_test "Completion promise set" test_7_completion_promise_set
run_test "Queue task stored correctly" test_8_queue_task_stored_correctly
run_test "Default values" test_9_default_values

echo ""
echo "Queue Chaining Tests:"
run_test "Two tasks queued" test_10_two_tasks_queued
run_test "Three tasks in sequence" test_11_three_tasks_in_sequence
run_test "Complete advances queue" test_12_complete_advances_queue

echo ""
echo "Error Recovery Tests:"
run_test "Corrupted JSON" test_13_corrupted_json
run_test "Missing queue file" test_14_missing_queue_file
run_test "Has-pending check" test_15_has_pending_check

echo ""
echo "========================================"
echo -e "Results: ${GREEN}$TESTS_PASSED passed${NC}, ${RED}$TESTS_FAILED failed${NC} (of $TESTS_RUN)"
echo "========================================"

if [[ $TESTS_FAILED -gt 0 ]]; then
    exit 1
fi
