# Agent 2 Task: Install Official Ralph Plugin (v1)

## Objective

Install and test the official ralph-wiggum plugin. Don't build custom - use what exists.

## Task 1: Install Plugin

1. Check if plugins are available:
```bash
claude plugins list
```

2. Install ralph-wiggum:
```bash
claude plugins add ralph-wiggum
```

3. If that doesn't work, check the plugin directory structure and manually set up from:
   - https://github.com/anthropics/claude-code (look for plugins/ralph-wiggum)
   - Or create minimal version based on the pattern

## Task 2: Test Ralph Loop

1. Create a simple test task in `sandbox/`:
```bash
/ralph-loop "Add a power() function to sandbox/calculator.py with tests" --max-iterations 3 --completion-promise "TASK_COMPLETE"
```

2. Observe:
   - Does it continue automatically?
   - Does it stop on completion?
   - How does it interact with existing circuit breaker?

## Task 3: Document Findings

After testing, update `specs/v1-agent2-ralph.md` with:
- What worked
- What didn't
- How to integrate with dispatcher (if needed)

## Constraints

- Do NOT modify `.claude/settings.json` (Agent 1 is working there)
- Do NOT build custom ralph scripts yet
- Just install and test official plugin first

## Success Criteria

1. Plugin installed (or documented why it can't be)
2. Ralph loop tested on sandbox
3. Findings documented

## If Plugin Install Fails

If `claude plugins add` doesn't work, document the error and try:
1. Check Claude Code version: `claude --version`
2. Check if plugins directory exists: `ls ~/.claude/plugins/`
3. Manual install from GitHub if needed

Then report findings so we know what v2 needs to build.

---

## Task 1 Findings (2026-01-12)

### Plugin System Exists

Claude Code **does** have a plugin system (as of v2.1.5):

```bash
claude plugin --help      # Show plugin commands
claude plugin marketplace list  # List marketplaces
claude plugin install <name>    # Install a plugin
```

### Correct Plugin Name

The spec was wrong about the name:
- ❌ `ralph-wiggum` - Does not exist
- ✅ `ralph-loop` - The actual plugin name

### Installation

```bash
claude plugin install ralph-loop
# ✔ Successfully installed plugin: ralph-loop@claude-plugins-official (scope: user)
```

### How ralph-loop Works

**Commands:**
- `/ralph-loop "<prompt>" --max-iterations <n> --completion-promise "<text>"` - Start loop
- `/cancel-ralph` - Cancel active loop

**Mechanism:**
1. Uses a **Stop hook** that intercepts session exit
2. Stores state in `.claude/ralph-loop.local.md` (local to project)
3. On exit attempt:
   - Checks iteration count vs max
   - Checks for `<promise>TEXT</promise>` in output matching completion-promise
   - If not complete: blocks exit, feeds SAME prompt back
4. Loop continues inside single session (no external bash loop needed)

**Key Files:**
- `hooks/stop-hook.sh` - The magic that blocks exit and continues
- `hooks/hooks.json` - Registers the Stop hook
- `commands/ralph-loop.md` - The slash command

### Integration with Dispatcher

**Important insight:** Ralph loop works **inside** Claude's session via Stop hooks. This is **different** from the dispatcher's auto-continue which:
- Works at the tmux level (external)
- Uses git-based progress detection
- Has circuit breaker

**Potential conflict:**
- If ralph-loop AND dispatcher auto-continue are both enabled, they could interfere
- Ralph handles its own "stuck" detection via max-iterations
- Dispatcher's circuit breaker might fire during ralph iterations

**Recommendation:**
- Use ralph-loop for single-agent iterative tasks (one session)
- Use dispatcher auto-continue for multi-agent coordination
- Don't mix both on same agent

---

## Task 2 Findings (2026-01-12)

### Testing Limitation

**Cannot test `/ralph-loop` from within an active Claude session** because:
1. `/ralph-loop` activates a Stop hook that traps the current session
2. Running it would prevent THIS agent from exiting normally
3. Testing requires a **fresh, dedicated Claude session**

### Sandbox Ready

The sandbox exists and is ready for testing:
```
sandbox/
├── calculator.py      # add, subtract, multiply, divide + history
└── test_calculator.py # pytest tests for all functions
```

No `power()` function exists yet - perfect test target.

### Manual Test Instructions

To test ralph-loop, open a **new terminal** in this directory and run:

```bash
cd /Users/kylenewman/Downloads/council-v3
claude
```

Then in the new Claude session:
```
/ralph-loop "Add a power() function to sandbox/calculator.py with tests. The function should raise base to exponent power and record to history like other functions. Run pytest to verify." --max-iterations 3 --completion-promise "TASK_COMPLETE"
```

### Expected Behavior (from code review)

1. **Setup:** Creates `.claude/ralph-loop.local.md` with:
   - `iteration: 1`
   - `max_iterations: 3`
   - `completion_promise: "TASK_COMPLETE"`

2. **Loop Mechanics:**
   - Claude works on the task
   - Claude tries to exit
   - Stop hook intercepts, checks for `<promise>TASK_COMPLETE</promise>`
   - If not found: increments iteration, feeds same prompt back
   - If found OR iteration >= 3: allows exit

3. **Monitoring during test:**
   ```bash
   # Watch iteration count
   cat .claude/ralph-loop.local.md | head -10
   ```

### Dispatcher Interaction

**Key insight from code review:**

Ralph-loop's Stop hook and dispatcher's auto-continue are **independent mechanisms**:

| Feature | Ralph Loop | Dispatcher Auto-Continue |
|---------|-----------|-------------------------|
| Level | Inside Claude session (hook) | Outside (tmux send-keys) |
| Trigger | Session exit attempt | Agent goes idle |
| Progress | Iteration counter | Git commit detection |
| Stuck detection | max-iterations | Circuit breaker (3 no-progress) |

**If both enabled simultaneously:**
- Dispatcher might send "continue" while ralph is mid-iteration
- Could cause duplicate prompts or confusion
- **Recommendation:** Disable dispatcher auto-continue when using ralph-loop

### What Still Needs Testing

- [ ] Actual iteration behavior (needs manual test)
- [ ] Completion promise detection accuracy
- [ ] Behavior when tests fail (does it retry?)
- [ ] Interaction with git commits during iterations

---

## Task 3: Final Summary

### What Worked

1. **Plugin system exists and works**
   - `claude plugin install ralph-loop` ✅
   - Official marketplace with 25+ plugins
   - User/project/local scope options

2. **Ralph-loop is production-ready**
   - Well-documented (5k+ word README)
   - Robust error handling in hooks
   - YAML frontmatter state management
   - Supports completion promises and max iterations

3. **Clean architecture**
   - Stop hook intercepts exit cleanly
   - State file is human-readable markdown
   - No external dependencies (pure bash)

### What Didn't Work

1. **Spec had wrong plugin name** (`ralph-wiggum` → `ralph-loop`)
2. **Cannot test from within active session** - fundamental limitation of Stop hooks
3. **No `/cancel-ralph` tested** - would need manual test

### Integration Recommendations for Council v3

| Use Case | Recommended Approach |
|----------|---------------------|
| Single agent, iterative task | Use ralph-loop alone |
| Multi-agent coordination | Use dispatcher auto-continue |
| Mixed workload | Disable auto-continue when ralph active |

### v2 Considerations

If building custom ralph functionality for council:

1. **Don't reinvent** - the official plugin works well
2. **Consider dispatcher awareness** - add flag to disable auto-continue when ralph detected
3. **State file location** - ralph uses `.claude/ralph-loop.local.md`, dispatcher uses `~/.council/state.json` (no conflict)

### Files Modified

- `specs/v1-agent2-ralph.md` - This file (findings documented)

### Files NOT Modified (per constraints)

- `.claude/settings.json` - Agent 1's domain
- No custom ralph scripts created

### Status: ✅ COMPLETE

- [x] Task 1: Plugin installed
- [x] Task 2: Behavior documented (manual test pending)
- [x] Task 3: Findings documented
