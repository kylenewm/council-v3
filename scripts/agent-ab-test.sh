#!/bin/bash
# A/B Test: Compare strict agent vs vanilla Claude on identical tasks
#
# Usage: ./scripts/agent-ab-test.sh "task description"
#
# Creates a sandbox, runs both agents, captures outputs for comparison

set -e

TASK="$1"
if [[ -z "$TASK" ]]; then
    echo "Usage: $0 \"task description\""
    echo "Example: $0 \"Add retry logic to the API client with exponential backoff\""
    exit 1
fi

SANDBOX_DIR="/tmp/agent-ab-test-$(date +%s)"
mkdir -p "$SANDBOX_DIR"/{vanilla,strict}

echo "=== Agent A/B Test ==="
echo "Task: $TASK"
echo "Sandbox: $SANDBOX_DIR"
echo ""

# Create identical test environments
for env in vanilla strict; do
    cd "$SANDBOX_DIR/$env"
    git init -q

    # Create a simple Python project to work on
    cat > main.py << 'EOF'
"""Simple API client for testing."""
import requests

class APIClient:
    def __init__(self, base_url):
        self.base_url = base_url

    def get(self, endpoint):
        return requests.get(f"{self.base_url}/{endpoint}")

    def post(self, endpoint, data):
        return requests.post(f"{self.base_url}/{endpoint}", json=data)
EOF

    cat > CLAUDE.md << 'EOF'
# Test Project
Simple API client. Modify main.py as requested.
EOF

    git add -A
    git commit -q -m "Initial commit"
done

echo "Running Vanilla Claude (no agent)..."
cd "$SANDBOX_DIR/vanilla"
START_VANILLA=$(date +%s)
timeout 120 claude --print --dangerously-skip-permissions -p "$TASK" > output.txt 2>&1 || true
END_VANILLA=$(date +%s)
VANILLA_TIME=$((END_VANILLA - START_VANILLA))

echo "Running Strict Agent..."
cd "$SANDBOX_DIR/strict"
# Copy the strict agent
mkdir -p .claude/agents
cp /Users/kylenewman/Downloads/council-v3/.claude/agents/strict.md .claude/agents/

START_STRICT=$(date +%s)
timeout 120 claude --print --dangerously-skip-permissions --agent strict -p "$TASK" > output.txt 2>&1 || true
END_STRICT=$(date +%s)
STRICT_TIME=$((END_STRICT - START_STRICT))

echo ""
echo "=== Results ==="
echo ""

# Compare outputs
echo "--- Vanilla Agent (${VANILLA_TIME}s) ---"
echo "Output length: $(wc -c < "$SANDBOX_DIR/vanilla/output.txt") bytes"
echo "Questions asked: $(grep -c '?' "$SANDBOX_DIR/vanilla/output.txt" 2>/dev/null || echo 0)"
echo "Assumptions: $(grep -ci 'assume\|assuming\|I.ll assume' "$SANDBOX_DIR/vanilla/output.txt" 2>/dev/null || echo 0)"
echo "Code changes:"
cd "$SANDBOX_DIR/vanilla" && git diff --stat HEAD~1 2>/dev/null || echo "  (none)"
echo ""

echo "--- Strict Agent (${STRICT_TIME}s) ---"
echo "Output length: $(wc -c < "$SANDBOX_DIR/strict/output.txt") bytes"
echo "Questions asked: $(grep -c '?' "$SANDBOX_DIR/strict/output.txt" 2>/dev/null || echo 0)"
echo "Assumptions: $(grep -ci 'assume\|assuming\|I.ll assume' "$SANDBOX_DIR/strict/output.txt" 2>/dev/null || echo 0)"
echo "Code changes:"
cd "$SANDBOX_DIR/strict" && git diff --stat HEAD~1 2>/dev/null || echo "  (none)"
echo ""

echo "=== Full Outputs ==="
echo "Vanilla: $SANDBOX_DIR/vanilla/output.txt"
echo "Strict:  $SANDBOX_DIR/strict/output.txt"
echo ""
echo "Compare with: diff $SANDBOX_DIR/vanilla/main.py $SANDBOX_DIR/strict/main.py"
echo ""

# Quick behavioral diff
echo "=== Behavioral Analysis ==="
echo ""
echo "Vanilla first 10 lines:"
head -10 "$SANDBOX_DIR/vanilla/output.txt"
echo "..."
echo ""
echo "Strict first 10 lines:"
head -10 "$SANDBOX_DIR/strict/output.txt"
echo "..."
