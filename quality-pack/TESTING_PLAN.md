# Quality Pack Testing Plan

This document outlines how to verify each phase of the quality-pack system works correctly.

## Overview

The quality-pack has multiple layers that need independent verification:

| Phase | Component | Status | Verification Method |
|-------|-----------|--------|---------------------|
| 1 | Template Pack Structure | Complete | Manual install test |
| 2 | Task-Type Commands | Complete | Real-world usage |
| 3 | RIPER Mode | Complete | Workflow test |
| 4 | Type Checking Hook | Complete | Type error detection |
| 5 | Blind Testing | Deferred | Needs design work |

---

## Phase 1: Template Pack Structure

### What to Test

1. **Global Installation**
   - `~/.claude/CLAUDE.md` created
   - `~/.council/hooks/inject.sh` installed and executable
   - `~/.council/hooks/auto-inject.sh` installed
   - `~/.council/hooks/type-check.sh` installed
   - `~/.council/hooks/notify-rich.sh` installed
   - All mode scripts in `~/.council/hooks/modes/`

2. **Project Installation**
   - `.claude/settings.json` created
   - `.claude/commands/` populated with all commands
   - `.claude/agents/` populated with agents
   - `.council/mode` set to `production`
   - `.council/invariants.yaml` created
   - `STATE.md` created
   - `CLAUDE.md` created (if didn't exist)

### Test Script

```bash
#!/bin/bash
# Run from quality-pack directory

# Test global install
./install.sh --force

# Verify global files
echo "=== Global Installation ==="
ls -la ~/.claude/CLAUDE.md
ls -la ~/.council/hooks/*.sh
ls -la ~/.council/hooks/modes/

# Test project install in temp dir
TEMP_DIR=$(mktemp -d)
cd "$TEMP_DIR"
/path/to/quality-pack/install.sh --project --force

# Verify project files
echo "=== Project Installation ==="
ls -la .claude/
ls -la .claude/commands/
ls -la .claude/agents/
ls -la .council/
cat .council/mode
cat STATE.md | head -10

# Cleanup
rm -rf "$TEMP_DIR"
echo "=== Tests Complete ==="
```

### Expected Results

- All files exist and are readable
- Hook scripts are executable
- Mode is set to `production`
- STATE.md has proper template structure

---

## Phase 2: Task-Type Commands

### What to Test

Each command should work as documented:

| Command | Test Scenario |
|---------|---------------|
| `/bug` | Fix a known bug, verify minimal diff |
| `/feature` | Implement small feature, verify plan-then-strict flow |
| `/refactor` | Refactor code, verify tests stay green throughout |
| `/setup` | Run in new project, verify structure created |

### Test: `/bug` Workflow

```
1. Create intentional bug in test file
2. Run /bug
3. Verify:
   - Mode set to strict
   - Bug reproduction attempted
   - Fix is minimal (no extra changes)
   - Tests pass after fix
   - Human approval requested before commit
```

### Test: `/feature` Workflow

```
1. Request small feature (e.g., "add version command")
2. Run /feature
3. Verify:
   - Mode starts in plan
   - Plan is presented before implementation
   - Mode switches to strict for implementation
   - Tests written
   - Final verification against requirements
```

### Test: `/refactor` Workflow

```
1. Request refactor (e.g., "rename function X to Y")
2. Run /refactor
3. Verify:
   - Tests run first (baseline)
   - Changes are incremental
   - Tests run after each change
   - No behavior changes
   - Dead code removed
```

### Test: `/setup` Workflow

```bash
mkdir /tmp/new-project
cd /tmp/new-project
# In Claude Code: /setup
# Verify structure matches expected
```

---

## Phase 3: RIPER Mode

### What to Test

The 5-phase workflow: Research-Innovate-Plan-Execute-Review

### Test Scenario

```
1. /inject riper
2. Request complex feature (e.g., "add caching layer")
3. Verify each phase:
   - RESEARCH: Codebase exploration, findings documented
   - INNOVATE: Multiple approaches brainstormed
   - PLAN: Detailed implementation plan
   - EXECUTE: Code written with strict mode
   - REVIEW: Final verification, DONE_REPORT
```

### Expected Output

Each phase should produce:
- Clear phase indicator in output
- Phase-specific deliverable
- Transition between phases is explicit

---

## Phase 4: Type Checking Hook

### What to Test

Type checking runs after Write/Edit on code files.

### Test: Python (mypy)

```bash
# Requires: pip install mypy

# Create file with type error
cat > /tmp/test_type.py << 'EOF'
def greet(name: str) -> str:
    return 42  # Should be string, not int
EOF

# Run hook
CLAUDE_FILE_PATH=/tmp/test_type.py ~/.council/hooks/type-check.sh

# Expected output:
# [TYPE CHECK] mypy found issues in /tmp/test_type.py:
# /tmp/test_type.py:2:12: error: Incompatible return value type (got "int", expected "str")
```

### Test: TypeScript (tsc)

```bash
# Requires: npm install -g typescript

# Create file with type error
cat > /tmp/test_type.ts << 'EOF'
function greet(name: string): string {
    return 42;  // Should be string, not number
}
EOF

# Run hook
CLAUDE_FILE_PATH=/tmp/test_type.ts ~/.council/hooks/type-check.sh

# Expected: tsc error about type mismatch
```

### Test: Graceful Skip

```bash
# With no type checker installed, should exit silently
CLAUDE_FILE_PATH=/tmp/some.py ~/.council/hooks/type-check.sh
echo "Exit code: $?"  # Should be 0
```

---

## Phase 5: Blind Testing (DEFERRED)

### Why Deferred

Blind testing requires careful design:
1. Spec extraction is non-trivial
2. Cursor integration needs manual workflow
3. Risk of tests that don't match actual requirements

### Design Questions to Answer

1. **Spec Format**: What format should the spec be in?
   - OpenAPI? TypeScript interfaces? Plain text requirements?
   - How to extract from existing code?

2. **Cursor Workflow**: How does handoff work?
   - Manual copy-paste of spec?
   - MCP server for spec sharing?
   - File-based spec storage?

3. **Test Location**: Where do blind tests go?
   - `tests/blind/` directory?
   - Same as regular tests with naming convention?
   - Separate test suite?

4. **Conflict Resolution**: What if blind tests contradict regular tests?
   - Blind tests take precedence?
   - Manual resolution required?

### Proposed Implementation (Future)

```
/blind-tests

1. Extract spec from current task context:
   - Read task description from STATE.md or conversation
   - Identify public interfaces being implemented
   - Generate spec document

2. Handoff to Cursor:
   - Save spec to .council/blind-test-spec.md
   - Prompt user to open in Cursor
   - Cursor generates tests from spec

3. Run blind tests:
   - Tests saved to tests/blind/
   - /test runs both regular and blind tests
   - Failures in blind tests indicate implementation issues (not test issues)
```

### Prerequisites for Phase 5

- [ ] Define spec format
- [ ] Document Cursor workflow
- [ ] Create spec extraction logic
- [ ] Decide on test location convention
- [ ] Handle test conflicts

---

## Integration Testing

### Full Workflow Test

```
1. Fresh machine setup:
   - Clone quality-pack
   - ./install.sh
   - Verify global hooks work

2. New project setup:
   - Create empty directory
   - ./install.sh --project
   - Start Claude Code in directory
   - Verify mode injection works

3. Complete workflow:
   - /inject strict
   - Create small feature
   - /test
   - /done
   - /commit
   - Verify all hooks fired correctly
```

### Regression Tests

After any changes to quality-pack:
1. Run install.sh and verify no errors
2. Test mode switching: /inject strict, /inject plan, /inject off
3. Test at least one task command: /bug or /feature
4. Verify type checking hook if tools installed

---

## Manual Verification Checklist

Run through this checklist when making changes to quality-pack:

- [ ] `install.sh --help` shows correct info
- [ ] `install.sh` completes without errors
- [ ] `install.sh --project` completes without errors
- [ ] Mode injection works (check prompt context)
- [ ] Invariants are displayed in strict mode
- [ ] Type checking fires on Python file edit (if mypy installed)
- [ ] Notification fires on Stop event (if enabled)
- [ ] All slash commands are recognized
- [ ] `/inject status` shows current mode

---

## Automation Opportunities

Future improvements:
1. **Automated install test** in CI
2. **Mode injection test** that verifies hook output
3. **Type check test** that creates files and verifies output
4. **Integration test** using Claude Code CLI in non-interactive mode

These require CI infrastructure and are out of scope for initial release.
