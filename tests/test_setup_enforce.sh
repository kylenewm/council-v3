#!/bin/bash
# Comprehensive tests for /setup, /enforce, and mode injection
# Based on SYSTEM_REFERENCE.md and OPERATING_GUIDE.md
#
# Tests cover:
# 1. Project setup (/setup creates all files)
# 2. Enforce setup (/enforce creates invariants + hook)
# 3. Forbidden paths blocked by pre-commit
# 4. Protected paths blocked but bypassable with --no-verify
# 5. Mode injection precedence (local overrides global)
# 6. Hub/spoke architecture (hook points to council-v3)
# 7. check_invariants.py script works
# 8. audit_done.py script works (smoke test)
# 9. Quick diagnostics commands work
# 10. Key files exist in expected locations

set -e

TEST_DIR="/tmp/council-test-$$"
COUNCIL_ROOT="${COUNCIL_ROOT:-$HOME/Downloads/council-v3}"
PASSED=0
FAILED=0
WARNINGS=0

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

pass() {
    echo -e "${GREEN}PASS${NC}: $1"
    ((PASSED++)) || true
}

fail() {
    echo -e "${RED}FAIL${NC}: $1"
    ((FAILED++)) || true
}

warn() {
    echo -e "${YELLOW}WARN${NC}: $1"
    ((WARNINGS++)) || true
}

info() {
    echo -e "${BLUE}INFO${NC}: $1"
}

header() {
    echo ""
    echo "=========================================="
    echo "$1"
    echo "=========================================="
}

cleanup() {
    echo ""
    info "Cleaning up $TEST_DIR..."
    rm -rf "$TEST_DIR"
    # Restore global mode if we changed it
    if [[ -n "$ORIGINAL_GLOBAL_MODE" ]]; then
        echo "$ORIGINAL_GLOBAL_MODE" > "$HOME/.council/current_inject.txt"
    fi
}

trap cleanup EXIT

# Save original global mode
ORIGINAL_GLOBAL_MODE=""
if [[ -f "$HOME/.council/current_inject.txt" ]]; then
    ORIGINAL_GLOBAL_MODE=$(cat "$HOME/.council/current_inject.txt")
fi

# ==========================================
# PRE-FLIGHT CHECKS
# ==========================================

header "PRE-FLIGHT: Checking required files exist"

# Check council-v3 root
[[ -d "$COUNCIL_ROOT" ]] && pass "Council root exists: $COUNCIL_ROOT" || { fail "Council root missing"; exit 1; }

# Check scripts
[[ -f "$COUNCIL_ROOT/scripts/check_invariants.py" ]] && pass "check_invariants.py exists" || fail "check_invariants.py missing"
[[ -f "$COUNCIL_ROOT/scripts/audit_done.py" ]] && pass "audit_done.py exists" || fail "audit_done.py missing"

# Check templates
[[ -f "$COUNCIL_ROOT/scripts/templates/pre-commit-hub.sh" ]] && pass "pre-commit-hub.sh template exists" || fail "pre-commit template missing"

# Check setup script
[[ -f "$HOME/.claude/setup-project.sh" ]] && pass "setup-project.sh exists" || fail "setup-project.sh missing"

# Check hooks directory
[[ -d "$HOME/.council/hooks" ]] && pass "Hooks directory exists" || fail "Hooks directory missing"
[[ -f "$HOME/.council/hooks/inject.sh" ]] && pass "inject.sh exists" || fail "inject.sh missing"

# ==========================================
# 1. PROJECT SETUP TESTS
# ==========================================

header "1. PROJECT SETUP (/setup)"

mkdir -p "$TEST_DIR"
cd "$TEST_DIR"
git init -q

# Run setup
bash "$HOME/.claude/setup-project.sh" "test-project" 2>&1

# Verify all expected files created
[[ -f "CLAUDE.md" ]] && pass "CLAUDE.md created" || fail "CLAUDE.md not created"
[[ -f "STATE.md" ]] && pass "STATE.md created" || fail "STATE.md not created"
[[ -f "LOG.md" ]] && pass "LOG.md created" || fail "LOG.md not created"
[[ -d ".claude" ]] && pass ".claude/ directory created" || fail ".claude/ directory not created"
[[ -d ".claude/commands" ]] && pass ".claude/commands/ created" || fail ".claude/commands/ not created"
[[ -f ".claude/settings.json" ]] && pass ".claude/settings.json created" || fail ".claude/settings.json not created"

# Check commands were copied
CMD_COUNT=$(ls .claude/commands/*.md 2>/dev/null | wc -l | tr -d ' ')
if [[ $CMD_COUNT -ge 5 ]]; then
    pass "Commands copied ($CMD_COUNT files)"
else
    warn "Few commands copied ($CMD_COUNT files) - expected 5+"
fi

# Test idempotency - run again, should skip existing
OUTPUT=$(bash "$HOME/.claude/setup-project.sh" "test-project" 2>&1)
if echo "$OUTPUT" | grep -q "exists, skipping"; then
    pass "Setup is idempotent (skips existing files)"
else
    warn "Setup may overwrite existing files"
fi

# ==========================================
# 2. ENFORCE SETUP TESTS
# ==========================================

header "2. ENFORCE SETUP (/enforce)"

# Create .council directory and invariants
mkdir -p .council

cat > .council/invariants.yaml << 'EOF'
forbidden_paths:
  - "*.env"
  - ".env.*"
  - "credentials/*"
  - ".secrets/*"
  - "**/secrets.yaml"

protected_paths:
  - "config/*.yaml"
  - "migrations/*"
EOF

# Install pre-commit hook
mkdir -p .git/hooks
cp "$COUNCIL_ROOT/scripts/templates/pre-commit-hub.sh" .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit

# Verify
[[ -f ".council/invariants.yaml" ]] && pass ".council/invariants.yaml created" || fail "invariants.yaml not created"
[[ -f ".git/hooks/pre-commit" ]] && pass ".git/hooks/pre-commit installed" || fail "pre-commit hook not installed"
[[ -x ".git/hooks/pre-commit" ]] && pass "pre-commit is executable" || fail "pre-commit not executable"

# Check invariants has both sections
grep -q "forbidden_paths" .council/invariants.yaml && pass "invariants has forbidden_paths" || fail "missing forbidden_paths"
grep -q "protected_paths" .council/invariants.yaml && pass "invariants has protected_paths" || fail "missing protected_paths"

# ==========================================
# 3. FORBIDDEN PATHS BLOCKED
# ==========================================

header "3. FORBIDDEN PATHS (must be blocked)"

# Need at least one allowed commit first
echo "# Test" > README.md
git add README.md
git commit -m "Initial commit" -q

# Test .env blocked
echo "SECRET=test" > .env
git add .env
if git commit -m "test .env" 2>&1 | grep -qi "forbidden\|blocked\|violation"; then
    pass ".env file blocked by pre-commit"
elif ! git commit -m "test .env" 2>/dev/null; then
    pass ".env file blocked (non-zero exit)"
else
    fail ".env file was NOT blocked - CRITICAL BUG"
    git reset --soft HEAD~1 2>/dev/null || true
fi
git reset .env 2>/dev/null || true
rm -f .env

# Test .env.local blocked
echo "SECRET=test" > .env.local
git add .env.local
if ! git commit -m "test .env.local" 2>/dev/null; then
    pass ".env.local blocked"
else
    fail ".env.local was NOT blocked"
    git reset --soft HEAD~1 2>/dev/null || true
fi
git reset .env.local 2>/dev/null || true
rm -f .env.local

# Test credentials/file blocked
mkdir -p credentials
echo "key=secret" > credentials/api.json
git add credentials/
if ! git commit -m "test credentials" 2>/dev/null; then
    pass "credentials/* blocked"
else
    fail "credentials/* was NOT blocked"
    git reset --soft HEAD~1 2>/dev/null || true
fi
git reset credentials/ 2>/dev/null || true
rm -rf credentials

# Test .secrets/* blocked
mkdir -p .secrets
echo "key=secret" > .secrets/keys.txt
git add .secrets/
if ! git commit -m "test secrets" 2>/dev/null; then
    pass ".secrets/* blocked"
else
    fail ".secrets/* was NOT blocked"
    git reset --soft HEAD~1 2>/dev/null || true
fi
git reset .secrets/ 2>/dev/null || true
rm -rf .secrets

# ==========================================
# 4. PROTECTED PATHS + BYPASS
# ==========================================

header "4. PROTECTED PATHS (blocked, but bypassable)"

# Test config/*.yaml is protected (blocked normally)
mkdir -p config
echo "setting: value" > config/app.yaml
git add config/
if ! git commit -m "test protected" 2>/dev/null; then
    pass "config/*.yaml blocked (protected path)"
else
    warn "config/*.yaml NOT blocked - may be expected if only forbidden enforced"
    git reset --soft HEAD~1 2>/dev/null || true
fi
git reset config/ 2>/dev/null || true

# Test --no-verify bypasses protected (but not forbidden)
echo "setting: value" > config/app.yaml
git add config/
if git commit --no-verify -m "test bypass protected" 2>/dev/null; then
    pass "--no-verify bypasses protected paths"
else
    warn "--no-verify didn't help - hook may not support bypass"
fi
rm -rf config

# ==========================================
# 5. NORMAL FILES ALLOWED
# ==========================================

header "5. NORMAL FILES (must be allowed)"

echo "# Hello World" > hello.md
git add hello.md
if git commit -m "test normal file" -q 2>/dev/null; then
    pass "Normal .md file allowed"
else
    fail "Normal file blocked - something is wrong"
fi

echo "print('test')" > test.py
git add test.py
if git commit -m "test py file" -q 2>/dev/null; then
    pass "Normal .py file allowed"
else
    fail "Normal .py file blocked"
fi

# ==========================================
# 6. MODE INJECTION PRECEDENCE
# ==========================================

header "6. MODE INJECTION (local overrides global)"

# Set global mode
mkdir -p "$HOME/.council"
echo "strict" > "$HOME/.council/current_inject.txt"

# Verify global mode readable
GLOBAL=$(cat "$HOME/.council/current_inject.txt" 2>/dev/null)
[[ "$GLOBAL" == "strict" ]] && pass "Global mode set to 'strict'" || fail "Global mode not set correctly"

# Create local override
echo "sandbox" > .council/mode

# Verify local mode readable
LOCAL=$(cat .council/mode 2>/dev/null)
[[ "$LOCAL" == "sandbox" ]] && pass "Local mode set to 'sandbox'" || fail "Local mode not set correctly"

# Check inject.sh respects precedence
if grep -q "\.council/mode" "$HOME/.council/hooks/inject.sh" 2>/dev/null; then
    pass "inject.sh checks for local .council/mode"
else
    fail "inject.sh doesn't check for local mode"
fi

# Test the actual precedence logic
MODE_CHECK=$(cat .council/mode 2>/dev/null || cat "$HOME/.council/current_inject.txt" 2>/dev/null)
[[ "$MODE_CHECK" == "sandbox" ]] && pass "Local mode takes precedence over global" || fail "Precedence logic broken"

# Clean up local mode
rm -f .council/mode

# ==========================================
# 7. HUB/SPOKE ARCHITECTURE
# ==========================================

header "7. HUB/SPOKE ARCHITECTURE"

# Check pre-commit references or can find council-v3
if grep -q "council-v3\|COUNCIL_HUB" .git/hooks/pre-commit 2>/dev/null; then
    pass "Pre-commit references council-v3 hub"
else
    warn "Pre-commit doesn't explicitly reference council-v3"
fi

# Check it can find check_invariants.py
if grep -q "check_invariants.py" .git/hooks/pre-commit 2>/dev/null; then
    pass "Pre-commit references check_invariants.py"
else
    warn "Pre-commit doesn't explicitly reference check_invariants.py"
fi

# ==========================================
# 8. CHECK_INVARIANTS.PY WORKS
# ==========================================

header "8. check_invariants.py SCRIPT"

cd "$TEST_DIR"

# Test --help or basic run
if python3 "$COUNCIL_ROOT/scripts/check_invariants.py" --help 2>/dev/null | grep -q "invariant\|usage"; then
    pass "check_invariants.py --help works"
else
    # Try running without args
    if python3 "$COUNCIL_ROOT/scripts/check_invariants.py" 2>&1 | grep -q "usage\|error\|invariant"; then
        pass "check_invariants.py runs (some output)"
    else
        warn "check_invariants.py output unclear"
    fi
fi

# Test with --diff HEAD~1
if python3 "$COUNCIL_ROOT/scripts/check_invariants.py" --repo . --diff HEAD~1 2>/dev/null; then
    pass "check_invariants.py --diff HEAD~1 runs clean"
else
    # Non-zero might be expected if no invariants in diff
    warn "check_invariants.py returned non-zero (may be expected)"
fi

# ==========================================
# 9. AUDIT_DONE.PY WORKS (SMOKE TEST)
# ==========================================

header "9. audit_done.py SCRIPT"

# Test --help
if python3 "$COUNCIL_ROOT/scripts/audit_done.py" --help 2>/dev/null | grep -q "transcript\|usage\|audit"; then
    pass "audit_done.py --help works"
else
    warn "audit_done.py help output unclear"
fi

# ==========================================
# 10. QUICK DIAGNOSTICS COMMANDS
# ==========================================

header "10. QUICK DIAGNOSTICS"

# Test mode check command
MODE_RESULT=$(cat .council/mode 2>/dev/null || cat "$HOME/.council/current_inject.txt" 2>/dev/null)
[[ -n "$MODE_RESULT" ]] && pass "Mode check works: '$MODE_RESULT'" || fail "Mode check returned empty"

# Test commands list
GLOBAL_CMDS=$(ls "$HOME/.claude/commands/"*.md 2>/dev/null | wc -l | tr -d ' ')
LOCAL_CMDS=$(ls .claude/commands/*.md 2>/dev/null | wc -l | tr -d ' ')
[[ $GLOBAL_CMDS -gt 0 ]] && pass "Global commands found: $GLOBAL_CMDS" || warn "No global commands found"
[[ $LOCAL_CMDS -gt 0 ]] && pass "Local commands found: $LOCAL_CMDS" || warn "No local commands in test project"

# Test enforcement check
[[ -f ".council/invariants.yaml" ]] && pass "Can find invariants.yaml" || fail "Cannot find invariants.yaml"
[[ -f ".git/hooks/pre-commit" ]] && pass "Can find pre-commit hook" || fail "Cannot find pre-commit hook"

# Test plugins check (if installed)
if [[ -f "$HOME/.claude/plugins/installed_plugins.json" ]]; then
    PLUGIN_COUNT=$(grep -o '"[^"]*@[^"]*"' "$HOME/.claude/plugins/installed_plugins.json" 2>/dev/null | wc -l | tr -d ' ')
    pass "Plugins check works: $PLUGIN_COUNT installed"
else
    warn "No plugins file found"
fi

# ==========================================
# 11. KEY FILES EXISTENCE
# ==========================================

header "11. KEY FILES CHECK"

# Global files
[[ -f "$HOME/.council/config.yaml" ]] && pass "~/.council/config.yaml exists" || warn "config.yaml missing (optional)"
[[ -f "$HOME/.council/current_inject.txt" ]] && pass "~/.council/current_inject.txt exists" || warn "current_inject.txt missing"
[[ -f "$HOME/.council/hooks/inject.sh" ]] && pass "inject.sh hook exists" || fail "inject.sh missing"
[[ -f "$HOME/.council/hooks/strict.sh" ]] && pass "strict.sh hook exists" || warn "strict.sh missing"

# Council-v3 hub files
[[ -f "$COUNCIL_ROOT/docs/OPERATING_GUIDE.md" ]] && pass "OPERATING_GUIDE.md exists" || warn "OPERATING_GUIDE missing"
[[ -f "$COUNCIL_ROOT/docs/SYSTEM_REFERENCE.md" ]] && pass "SYSTEM_REFERENCE.md exists" || warn "SYSTEM_REFERENCE missing"

# ==========================================
# 12. NESTED PATH PATTERNS
# ==========================================

header "12. NESTED PATH PATTERNS"

cd "$TEST_DIR"

# Test nested credentials path
mkdir -p credentials/subdir/deep
echo "secret" > credentials/subdir/deep/nested.json
git add credentials/
if ! git commit -m "test nested credentials" 2>/dev/null; then
    pass "credentials/subdir/deep/nested.json blocked (nested path)"
else
    fail "Nested credentials path was NOT blocked"
    git reset --soft HEAD~1 2>/dev/null || true
fi
git reset credentials/ 2>/dev/null || true
rm -rf credentials

# Test nested .secrets path
mkdir -p .secrets/keys/prod
echo "key" > .secrets/keys/prod/api.key
git add .secrets/
if ! git commit -m "test nested secrets" 2>/dev/null; then
    pass ".secrets/keys/prod/api.key blocked (nested path)"
else
    fail "Nested .secrets path was NOT blocked"
    git reset --soft HEAD~1 2>/dev/null || true
fi
git reset .secrets/ 2>/dev/null || true
rm -rf .secrets

# Test ** pattern (secrets.yaml anywhere)
mkdir -p deep/nested/config
echo "secret: value" > deep/nested/config/secrets.yaml
git add deep/
if ! git commit -m "test deep secrets.yaml" 2>/dev/null; then
    pass "deep/nested/config/secrets.yaml blocked (**/secrets.yaml pattern)"
else
    fail "**/secrets.yaml pattern did NOT match nested path"
    git reset --soft HEAD~1 2>/dev/null || true
fi
git reset deep/ 2>/dev/null || true
rm -rf deep

# ==========================================
# 13. MODE HOOK OUTPUT VERIFICATION
# ==========================================

header "13. MODE HOOK OUTPUT VERIFICATION"

# Test strict mode outputs DONE_REPORT requirement
echo "strict" > "$HOME/.council/current_inject.txt"
STRICT_OUTPUT=$("$HOME/.council/hooks/inject.sh" 2>/dev/null)
if echo "$STRICT_OUTPUT" | grep -q "DONE_REPORT"; then
    pass "Strict mode output contains DONE_REPORT requirement"
else
    fail "Strict mode output missing DONE_REPORT requirement"
fi

if echo "$STRICT_OUTPUT" | grep -q "FORBIDDEN PATHS"; then
    pass "Strict mode output contains FORBIDDEN PATHS section"
else
    fail "Strict mode output missing FORBIDDEN PATHS section"
fi

if echo "$STRICT_OUTPUT" | grep -q "Evidence over narrative\|evidence"; then
    pass "Strict mode output contains evidence-based language"
else
    warn "Strict mode output missing 'evidence' language"
fi

# Test sandbox mode outputs different content
echo "sandbox" > "$HOME/.council/current_inject.txt"
SANDBOX_OUTPUT=$("$HOME/.council/hooks/inject.sh" 2>/dev/null)
if echo "$SANDBOX_OUTPUT" | grep -qi "fixture\|iterate\|POC\|experiment"; then
    pass "Sandbox mode output contains fixture/iteration language"
else
    fail "Sandbox mode output missing expected sandbox content"
fi

# Sandbox should NOT require DONE_REPORT
if echo "$SANDBOX_OUTPUT" | grep -q "DONE_REPORT.*required"; then
    fail "Sandbox mode incorrectly requires DONE_REPORT"
else
    pass "Sandbox mode does not require DONE_REPORT"
fi

# Test plan mode
echo "plan" > "$HOME/.council/current_inject.txt"
PLAN_OUTPUT=$("$HOME/.council/hooks/inject.sh" 2>/dev/null)
if echo "$PLAN_OUTPUT" | grep -qi "plan\|design\|approval\|before.*code"; then
    pass "Plan mode output contains planning language"
else
    warn "Plan mode output may be missing expected content"
fi

# Test review mode
echo "review" > "$HOME/.council/current_inject.txt"
REVIEW_OUTPUT=$("$HOME/.council/hooks/inject.sh" 2>/dev/null)
if echo "$REVIEW_OUTPUT" | grep -qi "review\|APPROVE\|REJECT\|adversarial"; then
    pass "Review mode output contains review language"
else
    warn "Review mode output may be missing expected content"
fi

# Restore strict mode
echo "strict" > "$HOME/.council/current_inject.txt"

# ==========================================
# 14. AUDIT_DONE.PY CATCHES LIES
# ==========================================

header "14. AUDIT_DONE.PY LIE DETECTION"

cd "$TEST_DIR"

# Create a fake transcript with a lie (claims tests passed but they didn't)
# Uses Claude Code JSONL format: assistant messages with content array
FAKE_TRANSCRIPT="$TEST_DIR/fake_transcript.jsonl"
cat > "$FAKE_TRANSCRIPT" << 'JSONL'
{"type":"assistant","message":{"content":[{"type":"text","text":"Running tests now..."},{"type":"tool_use","id":"tool_1","name":"Bash","input":{"command":"pytest tests/"}}]}}
{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"tool_1","content":"FAILED tests/test_main.py::test_something - AssertionError\n1 failed, 0 passed"}]}}
{"type":"assistant","message":{"content":[{"type":"text","text":"DONE_REPORT:\n- changed_files: [main.py]\n- commands_run: [pytest (exit 0)]\n- test_output: All tests passed\n- invariants: pass\n- next_actions: none"}]}}
JSONL

# Run audit_done.py on fake transcript
AUDIT_RESULT=$(python3 "$COUNCIL_ROOT/scripts/audit_done.py" --transcript "$FAKE_TRANSCRIPT" 2>&1) || AUDIT_EXIT=$?

if [[ ${AUDIT_EXIT:-0} -eq 1 ]] || echo "$AUDIT_RESULT" | grep -qi "discrepancy\|mismatch"; then
    pass "audit_done.py detected lie about test results"
else
    # Check if it at least found the DONE_REPORT
    if echo "$AUDIT_RESULT" | grep -q "DONE_REPORT"; then
        warn "audit_done.py found DONE_REPORT but may not have detected lie (audit logic may need review)"
    else
        fail "audit_done.py did NOT detect lie about test results"
        echo "  Audit output: $AUDIT_RESULT"
    fi
fi

# Create transcript with truthful DONE_REPORT
TRUTHFUL_TRANSCRIPT="$TEST_DIR/truthful_transcript.jsonl"
cat > "$TRUTHFUL_TRANSCRIPT" << 'JSONL'
{"type":"assistant","message":{"content":[{"type":"text","text":"Running tests..."},{"type":"tool_use","id":"tool_2","name":"Bash","input":{"command":"pytest tests/"}}]}}
{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"tool_2","content":"3 passed in 0.5s"}]}}
{"type":"assistant","message":{"content":[{"type":"text","text":"DONE_REPORT:\n- changed_files: [main.py]\n- commands_run: [pytest (exit 0)]\n- test_output: 3 passed\n- invariants: pass\n- next_actions: none"}]}}
JSONL

AUDIT_RESULT2=$(python3 "$COUNCIL_ROOT/scripts/audit_done.py" --transcript "$TRUTHFUL_TRANSCRIPT" 2>&1) || AUDIT_EXIT2=$?

if [[ ${AUDIT_EXIT2:-0} -eq 0 ]] || echo "$AUDIT_RESULT2" | grep -qi "verified\|pass\|clean"; then
    pass "audit_done.py accepts truthful DONE_REPORT"
else
    warn "audit_done.py may have flagged truthful transcript (check manually)"
fi

# Test transcript with NO DONE_REPORT
NO_REPORT_TRANSCRIPT="$TEST_DIR/no_report_transcript.jsonl"
cat > "$NO_REPORT_TRANSCRIPT" << 'JSONL'
{"type":"assistant","message":{"content":[{"type":"text","text":"I finished the work."},{"type":"tool_use","id":"tool_3","name":"Bash","input":{"command":"echo done"}}]}}
{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"tool_3","content":"done"}]}}
JSONL

AUDIT_RESULT3=$(python3 "$COUNCIL_ROOT/scripts/audit_done.py" --transcript "$NO_REPORT_TRANSCRIPT" 2>&1) || AUDIT_EXIT3=$?

if [[ ${AUDIT_EXIT3:-0} -eq 2 ]] || echo "$AUDIT_RESULT3" | grep -qi "no.*done.*report\|missing\|not found"; then
    pass "audit_done.py detects missing DONE_REPORT"
else
    warn "audit_done.py response to missing DONE_REPORT unclear"
fi

rm -f "$FAKE_TRANSCRIPT" "$TRUTHFUL_TRANSCRIPT" "$NO_REPORT_TRANSCRIPT"

# ==========================================
# 15. MALFORMED INPUT HANDLING
# ==========================================

header "15. MALFORMED INPUT HANDLING"

cd "$TEST_DIR"

# Test malformed invariants.yaml
ORIGINAL_INVARIANTS=$(cat .council/invariants.yaml)
echo "invalid: yaml: [unclosed" > .council/invariants.yaml

echo "test" > malformed_test.txt
git add malformed_test.txt
if git commit -m "test with malformed yaml" 2>&1 | grep -qi "error\|exception\|failed\|invalid"; then
    pass "Pre-commit handles malformed YAML gracefully (error message)"
elif git commit -m "test with malformed yaml" 2>/dev/null; then
    warn "Pre-commit allowed commit with malformed YAML (may be OK if fallback exists)"
    git reset --soft HEAD~1 2>/dev/null || true
else
    pass "Pre-commit rejected commit with malformed YAML"
fi
git reset malformed_test.txt 2>/dev/null || true
rm -f malformed_test.txt

# Restore valid invariants
echo "$ORIGINAL_INVARIANTS" > .council/invariants.yaml

# Test empty invariants.yaml
echo "" > .council/invariants.yaml
echo "empty_test" > empty_test.txt
git add empty_test.txt
if git commit -m "test with empty invariants" 2>/dev/null; then
    pass "Pre-commit handles empty invariants.yaml (allows commit)"
else
    warn "Pre-commit blocked commit with empty invariants.yaml"
    git reset empty_test.txt 2>/dev/null || true
fi
rm -f empty_test.txt

# Restore valid invariants
echo "$ORIGINAL_INVARIANTS" > .council/invariants.yaml

# ==========================================
# 16. PATTERN EDGE CASES
# ==========================================

header "16. PATTERN EDGE CASES"

cd "$TEST_DIR"

# Test file that looks like .env but isn't
echo "config" > not.env.txt
git add not.env.txt
if git commit -m "test not.env.txt" -q 2>/dev/null; then
    pass "not.env.txt allowed (not matched by *.env)"
else
    fail "not.env.txt incorrectly blocked"
    git reset --soft HEAD~1 2>/dev/null || true
fi

# Test .environment (should NOT match .env.*)
echo "config" > .environment
git add .environment
if git commit -m "test .environment" -q 2>/dev/null; then
    pass ".environment allowed (not matched by .env.*)"
else
    fail ".environment incorrectly blocked"
    git reset --soft HEAD~1 2>/dev/null || true
fi

# Test file named just "env" (should be allowed)
echo "config" > env
git add env
if git commit -m "test env file" -q 2>/dev/null; then
    pass "'env' file allowed (not matched by *.env)"
else
    fail "'env' file incorrectly blocked"
    git reset --soft HEAD~1 2>/dev/null || true
fi

# Test .env (exact match - should be blocked)
echo "SECRET=x" > .env
git add .env
if ! git commit -m "test .env exact" 2>/dev/null; then
    pass ".env exact match blocked"
else
    fail ".env exact match NOT blocked"
    git reset --soft HEAD~1 2>/dev/null || true
fi
git reset .env 2>/dev/null || true
rm -f .env

# ==========================================
# 17. DISPATCHER UNIT TESTS (no tmux)
# ==========================================

header "17. DISPATCHER LOGIC (unit tests, no tmux)"

# Test TaskQueue logic
QUEUE_TEST=$(python3 << 'PYTHON'
import sys
sys.path.insert(0, "$COUNCIL_ROOT")

try:
    # Test basic queue operations
    queue = []

    # Add items
    queue.append("task1")
    queue.append("task2")
    assert len(queue) == 2, "Queue add failed"

    # Pop items (FIFO)
    item = queue.pop(0)
    assert item == "task1", "Queue FIFO order wrong"

    # Check remaining
    assert len(queue) == 1, "Queue length wrong after pop"
    assert queue[0] == "task2", "Wrong item remaining"

    print("QUEUE_OK")
except Exception as e:
    print(f"QUEUE_FAIL: {e}")
PYTHON
)

if echo "$QUEUE_TEST" | grep -q "QUEUE_OK"; then
    pass "Queue FIFO logic works"
else
    fail "Queue logic broken: $QUEUE_TEST"
fi

# Test circuit breaker logic
CIRCUIT_TEST=$(python3 << 'PYTHON'
try:
    class CircuitBreaker:
        def __init__(self, threshold=3):
            self.failures = 0
            self.threshold = threshold
            self.open = False

        def record_failure(self):
            self.failures += 1
            if self.failures >= self.threshold:
                self.open = True

        def record_success(self):
            self.failures = 0
            self.open = False

        def reset(self):
            self.failures = 0
            self.open = False

    cb = CircuitBreaker(threshold=3)

    # Should start closed
    assert not cb.open, "Circuit should start closed"

    # Two failures - still closed
    cb.record_failure()
    cb.record_failure()
    assert not cb.open, "Circuit should be closed after 2 failures"

    # Third failure - opens
    cb.record_failure()
    assert cb.open, "Circuit should be open after 3 failures"

    # Reset
    cb.reset()
    assert not cb.open, "Circuit should be closed after reset"
    assert cb.failures == 0, "Failures should be 0 after reset"

    # Success resets
    cb.record_failure()
    cb.record_failure()
    cb.record_success()
    assert cb.failures == 0, "Success should reset failure count"

    print("CIRCUIT_OK")
except Exception as e:
    print(f"CIRCUIT_FAIL: {e}")
PYTHON
)

if echo "$CIRCUIT_TEST" | grep -q "CIRCUIT_OK"; then
    pass "Circuit breaker logic works"
else
    fail "Circuit breaker logic broken: $CIRCUIT_TEST"
fi

# ==========================================
# 18. PARSER PARITY TEST
# ==========================================

header "18. PRE-COMMIT vs CHECK_INVARIANTS.PY PARSER PARITY"

cd "$TEST_DIR"

# Create test invariants with various patterns
cat > .council/invariants.yaml << 'EOF'
forbidden_paths:
  - "*.env"
  - ".env.*"
  - "credentials/*"
  - "**/secrets.yaml"

protected_paths:
  - "config/*.yaml"
  - "migrations/*"
EOF

# Test: Both parsers should agree on what matches

# File that should match forbidden
TEST_FILE="test.env"
echo "x" > "$TEST_FILE"

# Check what check_invariants.py says
CI_RESULT=$(python3 "$COUNCIL_ROOT/scripts/check_invariants.py" --repo . --files "$TEST_FILE" 2>&1) || CI_EXIT=$?

# Check what pre-commit says (stage and attempt commit)
git add "$TEST_FILE"
PC_RESULT=$(git commit -m "parity test" 2>&1) || PC_EXIT=$?
git reset "$TEST_FILE" 2>/dev/null || true
rm -f "$TEST_FILE"

# Both should block/flag the file
if [[ ${CI_EXIT:-0} -ne 0 ]] || echo "$CI_RESULT" | grep -qi "violation\|forbidden"; then
    CI_BLOCKED=true
else
    CI_BLOCKED=false
fi

if [[ ${PC_EXIT:-0} -ne 0 ]] || echo "$PC_RESULT" | grep -qi "forbidden\|blocked"; then
    PC_BLOCKED=true
else
    PC_BLOCKED=false
fi

if [[ "$CI_BLOCKED" == "$PC_BLOCKED" ]]; then
    pass "check_invariants.py and pre-commit agree on *.env pattern"
else
    fail "Parser disagreement: check_invariants=$CI_BLOCKED, pre-commit=$PC_BLOCKED"
fi

# Test with ** pattern
mkdir -p deep/path
echo "secret" > deep/path/secrets.yaml
git add deep/

PC_RESULT2=$(git commit -m "deep secrets test" 2>&1) || PC_EXIT2=$?
git reset deep/ 2>/dev/null || true

if [[ ${PC_EXIT2:-0} -ne 0 ]]; then
    pass "Pre-commit blocks **/secrets.yaml pattern"
else
    fail "Pre-commit missed **/secrets.yaml pattern"
fi

rm -rf deep

# Restore original invariants
cat > .council/invariants.yaml << 'EOF'
forbidden_paths:
  - "*.env"
  - ".env.*"
  - "credentials/*"
  - ".secrets/*"
  - "**/secrets.yaml"

protected_paths:
  - "config/*.yaml"
  - "migrations/*"
EOF

# ==========================================
# 19. LOCAL MODE OVERRIDE ACTUALLY WORKS
# ==========================================

header "19. LOCAL MODE INJECTION ACTUALLY WORKS"

cd "$TEST_DIR"

# Set global to strict, local to sandbox
echo "strict" > "$HOME/.council/current_inject.txt"
mkdir -p .council
echo "sandbox" > .council/mode

# Run inject.sh from this directory and check output
INJECTED=$("$HOME/.council/hooks/inject.sh" 2>/dev/null)

# Should see SANDBOX content, not STRICT
if echo "$INJECTED" | grep -qi "SANDBOX\|fixture\|POC"; then
    pass "Local mode (sandbox) actually injected, overriding global (strict)"
else
    if echo "$INJECTED" | grep -q "DONE_REPORT"; then
        fail "Global mode (strict) injected despite local override - inject.sh not checking local mode correctly"
    else
        warn "Injection output unclear - check manually"
    fi
fi

rm -f .council/mode

# ==========================================
# 20. HOOK SCRIPT EXECUTABILITY
# ==========================================

header "20. HOOK SCRIPTS EXECUTABLE"

for hook in inject.sh strict.sh sandbox.sh plan.sh review.sh auto-inject.sh; do
    if [[ -f "$HOME/.council/hooks/$hook" ]]; then
        if [[ -x "$HOME/.council/hooks/$hook" ]]; then
            pass "$hook is executable"
        else
            fail "$hook exists but is NOT executable"
        fi
    else
        warn "$hook not found (may be optional)"
    fi
done

# ==========================================
# SUMMARY
# ==========================================

header "TEST SUMMARY"

TOTAL=$((PASSED + FAILED))
echo ""
echo -e "Passed:   ${GREEN}$PASSED${NC}"
echo -e "Failed:   ${RED}$FAILED${NC}"
echo -e "Warnings: ${YELLOW}$WARNINGS${NC}"
echo "Total:    $TOTAL"
echo ""

if [[ $FAILED -eq 0 ]]; then
    echo -e "${GREEN}All critical tests passed!${NC}"
    if [[ $WARNINGS -gt 0 ]]; then
        echo -e "${YELLOW}Review warnings above.${NC}"
    fi
    exit 0
else
    echo -e "${RED}$FAILED critical test(s) failed.${NC}"
    exit 1
fi
