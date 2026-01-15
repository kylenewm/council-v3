# Council v3 Operating Guide

Practical guide for running and using the council multi-agent system.

---

## Quick Reference

### Mode Commands
```bash
/inject strict   # Production: verify before done, DONE_REPORT required
/inject sandbox  # POC: fast iteration with fixtures
/inject plan     # Design: plan before building
/inject review   # Adversarial: context-blind code review
/inject off      # Disable mode-specific injection
/inject status   # Show current mode
```

### Enforcement Commands
```bash
# Check for invariant violations
python scripts/check_invariants.py --diff HEAD~1
python scripts/check_invariants.py --diff main --allow-protected

# Audit a transcript for lies
python scripts/audit_done.py --transcript ~/.claude/projects/.../session.jsonl
python scripts/audit_done.py --transcript session.jsonl --json
```

### Dispatcher Commands
```bash
1: <text>        # Send to agent 1
1: t1 | t2 | t3  # Queue tasks for agent 1
queue 1          # Show queue
clear 1          # Clear queue
auto 1           # Enable auto-continue
stop 1           # Disable auto-continue
reset 1          # Reset circuit breaker
status           # Show all agents
```

---

## Enforcement System

### What It Does

Two layers of deterministic verification:

1. **Invariants Check** - Blocks changes to forbidden/protected paths
2. **Transcript Audit** - Catches lies in DONE_REPORTs

### Setting Up Invariants

Create `.council/invariants.yaml` in your project:

```yaml
# ALWAYS blocked - no override
forbidden_paths:
  - "*.env"
  - "credentials/*"
  - ".secrets/*"

# Blocked by default - --allow-protected to override
protected_paths:
  - "api/schema.py"
  - "migrations/*"
  - "config/production.yaml"
```

See `.council/invariants.example.yaml` for a full template.

### Running Invariants Check

```bash
# Check current changes against main
python scripts/check_invariants.py --diff main

# Check last commit
python scripts/check_invariants.py --diff HEAD~1

# Override protected (forbidden still blocked)
python scripts/check_invariants.py --diff HEAD~1 --allow-protected

# JSON output for automation
python scripts/check_invariants.py --diff HEAD~1 --json
```

**Exit codes:**
- `0` - Clean, no violations
- `1` - Violations found

### Running Transcript Audit

```bash
# Find your session transcript
ls ~/.claude/projects/-Users-*/

# Audit it
python scripts/audit_done.py --transcript ~/.claude/projects/.../session.jsonl

# Only check last 100 entries (faster for large files)
python scripts/audit_done.py --transcript session.jsonl --last-n 100
```

**What it catches:**
- Claims "tests passed" when Bash output shows failures
- Claims "invariants: pass" when check_invariants.py showed violations
- Missing DONE_REPORT entirely

**Exit codes:**
- `0` - VERIFIED (claims match evidence)
- `1` - DISCREPANCY (lies detected)
- `2` - NO_DONE_REPORT (missing report)

---

## Modes in Detail

### Strict Mode (Production)

**When:** Working on production code, features that ship, bug fixes.

**Behavior injected:**
```
BEFORE:
1. Read INVARIANTS.md, STATE.md, CLAUDE.md
2. Read files before editing - never guess
3. Large scope? State goal, constraints, acceptance criteria

DURING:
1. Test after each significant change
2. Don't add features beyond request
3. 2 failures on same error → STOP, summarize, propose alternative
4. Task > 30 min? Split into 3-7 micro-tasks

DONE (required):
DONE_REPORT with changed_files, commands_run, test_output, invariants, next_actions
```

**Activate:** `/inject strict`

### Sandbox Mode (POC)

**When:** Quick experiments, fixture capture, rapid iteration.

**Behavior injected:**
```
PATTERNS:
1. Fixtures first - capture real data once, iterate infinitely
2. Decouple expensive (API/LLM) from cheap (filtering/logic)
3. test_mode configs - smaller limits, skip reviews
4. Structured metrics: pass/fail + timing + quality scores

WORKFLOW:
1. Capture → 2. Iterate → 3. Validate
```

**Activate:** `/inject sandbox`

### Plan Mode (Design)

**When:** New features, architectural changes, uncertain scope.

**Behavior injected:**
```
BEFORE any code:
1. Break into phases with clear deliverables
2. Identify invariants that must not break
3. Define success metrics per phase

OUTPUT:
- Structured plan document
- Wait for approval before implementing
```

**Activate:** `/inject plan`

### Review Mode (Adversarial)

**When:** Code review before merge, second opinion on changes.

**Behavior injected:**
```
YOU RECEIVE: git diff, test results, invariants check
YOUR JOB:
1. Find risks, edge cases, failure modes
2. Identify simpler alternatives
3. "What would I delete from this?"

OUTPUT: BLOCKERS, SHOULD_FIX, SUGGESTIONS, VERDICT (APPROVE/REJECT)

DO NOT: Ask for context, suggest "just do it anyway", write code
```

**Activate:** `/inject review`

---

## Dispatcher Setup

### Configuration

Edit `~/.council/config.yaml`:

```yaml
agents:
  1:
    pane_id: "%0"
    name: "Council"
    worktree: ~/Downloads/council-v3
  2:
    pane_id: "%1"
    name: "JobFinder"
    worktree: ~/Downloads/job-finder
  3:
    pane_id: "%3"
    name: "VoiceEval"
    worktree: ~/Downloads/voice-agent-eval
  4:
    pane_id: "%4"
    name: "Other"
    worktree: ~/projects/other

fifo_path: ~/.council/in.fifo
poll_interval: 2.0

pushover:
  user_key: "xxx"
  api_token: "xxx"
```

### Starting

```bash
# Terminal 1: Start dispatcher
python -m council.dispatcher.simple

# Terminal 2+: Start agents in tmux panes
tmux
# Create panes, start claude in each
```

### Task Queue

Send multiple tasks to an agent:
```
1: implement auth | add tests | update docs
```

First task sent immediately. Rest queued. Auto-dequeues when agent becomes ready.

### Circuit Breaker

Opens after 3 iterations without git commits. Prevents infinite loops.

```bash
reset 1    # Reset circuit breaker for agent 1
```

---

## Workflow Examples

### Feature Development (Strict + Plan)

```bash
# 1. Plan first
/inject plan
> "Add user authentication"
# Review plan, approve

# 2. Switch to strict for implementation
/inject strict
> "Implement phase 1 from the plan"
# Work until DONE_REPORT

# 3. Verify
python scripts/check_invariants.py --diff HEAD~1
python scripts/audit_done.py --transcript <session.jsonl>
```

### Quick Experiment (Sandbox)

```bash
/inject sandbox
> "Test if the new API returns what we need"
# Capture fixtures, iterate fast
# No DONE_REPORT required
```

### Code Review (Review)

```bash
/inject review
> "Review the changes in this PR: <paste git diff>"
# Get structured feedback
# APPROVE or REJECT with reasons
```

### Multi-Agent Parallel Work

```bash
# In dispatcher
1: implement feature A
2: implement feature B
3: write integration tests
4: update documentation

status  # Check progress
```

---

## Troubleshooting

### Hook not injecting

1. Check settings.json has hook registered
2. Restart Claude session (settings read at start)
3. Verify hook script is executable: `chmod +x ~/.council/hooks/*.sh`

### Invariants check fails on valid changes

Use `--allow-protected` for protected paths:
```bash
python scripts/check_invariants.py --diff HEAD~1 --allow-protected
```

Forbidden paths cannot be overridden (by design).

### Audit shows discrepancy

Review the actual tool outputs vs DONE_REPORT claims. Fix the code or rerun tests.

### Circuit breaker keeps opening

Agent isn't making git commits. Either:
- Task is too large (break it down)
- Agent is stuck (check its output)
- Task doesn't involve code changes (use `stop N` to disable auto-continue)

### Mode not changing

1. Check `~/.council/current_inject.txt` was updated
2. Mode change takes effect next prompt (not retroactive)

---

## File Locations

```
~/.council/
├── hooks/
│   ├── inject.sh         # Router
│   ├── auto-inject.sh    # Global rules
│   ├── strict.sh         # Production mode
│   ├── sandbox.sh        # POC mode
│   ├── plan.sh           # Planning mode
│   └── review.sh         # Review mode
├── current_inject.txt    # Current mode
├── config.yaml           # Dispatcher config
└── state.json            # Queue/circuit state

~/Downloads/council-v3/
├── scripts/
│   ├── check_invariants.py
│   └── audit_done.py
├── .council/
│   └── invariants.yaml   # Project invariants
└── docs/
    ├── OPERATING_GUIDE.md
    └── SYSTEM_ARCHITECTURE.md
```

---

## DONE_REPORT Format

When in strict mode, end tasks with:

```
DONE_REPORT:
- changed_files: [list from git diff --name-only]
- commands_run: [pytest (exit 0), npm build (exit 0)]
- test_output: 15 passed in 2.3s
- invariants: pass (checked via check_invariants.py)
- next_actions: [if any remaining work]
```

This format is:
- Required in strict mode
- Auditable via `audit_done.py`
- Evidence-based (not narrative)
