# Council v3 Operating Guide

Practical guide for running and using the council multi-agent system.

---

## System Overview

**What Council v3 does:**
- Routes commands from voice (FIFO), phone (Pushover), Telegram to Claude Code agents in tmux panes
- Auto-continues agents with circuit breaker (git-based progress detection)
- Sends notifications (Mac + Pushover) when agents complete tasks
- Injects context via hooks to control agent behavior (strict/sandbox/plan/review modes)
- Enforces invariants and audits completion claims

**What agents do themselves:**
- Task management (TodoWrite tool)
- Work verification
- Deciding when they're done

**Architecture:**
```
┌─────────────────────────────────────────────────────────┐
│                      DISPATCHER                          │
│  Reads: FIFO (voice), Telegram, Pushover                │
│  Routes to: tmux panes running Claude Code              │
├─────────────────────────────────────────────────────────┤
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐  │
│   │ Agent 1  │  │ Agent 2  │  │ Agent 3  │  │ Agent 4│  │
│   │ Project A│  │ Project B│  │ Project C│  │Proj D  │  │
│   │ (tmux %0)│  │ (tmux %1)│  │ (tmux %3)│  │(tmux %4│  │
│   └──────────┘  └──────────┘  └──────────┘  └────────┘  │
│                                                          │
│   Each agent has:                                        │
│   - Own Claude Code session                              │
│   - Hooks injecting context per prompt                   │
│   - Circuit breaker (opens after 3 no-progress loops)   │
└─────────────────────────────────────────────────────────┘
```

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

**Mode Precedence (LOCAL overrides GLOBAL):**
```
1. .council/mode    (project-local, checked FIRST)
2. ~/.council/mode  (global fallback)
3. default: strict  (if no mode file exists)
```

**Set mode for one project only:**
```bash
echo "sandbox" > .council/mode
```

**Set mode globally (all projects):**
```bash
echo "strict" > ~/.council/mode
# OR
/inject strict
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
queue 1 "<task>" # Add task to queue
clear 1          # Clear queue
auto 1           # Enable auto-continue
stop 1           # Disable auto-continue
reset 1          # Reset circuit breaker
progress 1 mark  # Manually mark progress (resets streak)
status           # Show all agents
```

---

## Configuration Reference

All configurable files in one place:

| File | What It Controls | Location |
|------|------------------|----------|
| `config.yaml` | Agents, panes, Pushover, Telegram | `~/.council/` |
| `current_inject.txt` | Active mode (strict/plan/review/sandbox/off) | `~/.council/` |
| `state.json` | Runtime state (circuits, queues) | `~/.council/` |
| `auto-inject.sh` | Global rules (always injected) | `~/.council/hooks/` |
| `strict.sh` | Strict mode injection | `~/.council/hooks/` |
| `plan.sh` | Plan mode injection | `~/.council/hooks/` |
| `review.sh` | Review mode injection | `~/.council/hooks/` |
| `sandbox.sh` | Sandbox mode injection | `~/.council/hooks/` |
| `invariants.yaml` | Forbidden/protected paths | `.council/` (per-project) |
| `settings.json` | Hooks, plugins, permissions | `~/.claude/` |
| `commands/` | Global slash commands | `~/.claude/commands/` |
| `commands/` | Project-specific commands (overrides global) | `.claude/commands/` |

**How to check current state:**
```bash
# Current mode
cat ~/.council/current_inject.txt

# Project invariants
cat .council/invariants.yaml

# Dispatcher config
cat ~/.council/config.yaml

# Runtime state (queues, circuits)
cat ~/.council/state.json
```

**Hub/Spoke Architecture:**

Council-v3 is the central hub. Other projects are spokes.

```
Council-v3 (HUB)
├── Dispatcher
├── Scripts (check_invariants.py, audit_done.py)
├── Templates (hooks, invariants template)
└── Skills (/enforce, /inject, etc.)

Target Projects (SPOKES)
├── .council/invariants.yaml (project-specific paths)
└── .git/hooks/pre-commit (calls council-v3's script)
```

To add enforcement to a new project:
```bash
# From council-v3
/enforce /path/to/target-project
```

---

## Enforcement System

### Authoritative Completion (The One Rule)

```
┌─────────────────────────────────────────────────────────────┐
│ AUTHORITATIVE COMPLETION (strict mode only)                 │
│                                                             │
│ A task is "complete" when ALL are true:                     │
│   1. DONE_REPORT present in transcript                      │
│   2. audit_done verifies claims (if auto_audit enabled)     │
│   3. check_invariants passes (if configured)                │
│                                                             │
│ In strict mode: DONE_REPORT is REQUIRED.                    │
│ If missing, task is marked INCOMPLETE even if agent is      │
│ "ready". No DONE_REPORT = not done.                         │
│                                                             │
│ Everything else (prompt appearing, "I'm done" text,         │
│ tmux idle) is NON-AUTHORITATIVE.                            │
└─────────────────────────────────────────────────────────────┘
```

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

### Audit Scope

**audit_done.py VERIFIES:**
- If DONE_REPORT claims "tests passed", transcript Bash output shows pass
- If DONE_REPORT claims `changed_files: [x,y]`, git diff output matches
- If DONE_REPORT claims "invariants: pass", check_invariants output is clean

**audit_done.py DOES NOT:**
- Run tests itself (post-hoc only)
- Prove correctness beyond observed evidence
- Block execution (manual audit only, unless `auto_audit` enabled)
- Connect to dispatcher or live agents in real-time

---

## Adding Enforcement to Other Projects

### Step-by-Step Setup

**1. Create project config directory:**
```bash
mkdir -p .council
```

**2. Copy invariants template and customize:**
```bash
# From council-v3 repo
cp ~/Downloads/council-v3/.council/invariants.example.yaml .council/invariants.yaml
```

Edit `.council/invariants.yaml` for your project:
```yaml
forbidden_paths:
  - "*.env"              # Always include
  - ".env.*"             # Always include
  - "credentials/*"      # Secrets
  - "**/api_keys.json"   # Project-specific secrets

protected_paths:
  - "api/schema.py"      # DB schema - ask before changing
  - "migrations/*"       # DB migrations - careful
  - "config/prod*.yaml"  # Production configs
```

**3. Copy scripts to project (optional):**
```bash
cp ~/Downloads/council-v3/scripts/check_invariants.py scripts/
cp ~/Downloads/council-v3/scripts/audit_done.py scripts/
```

Or reference them from council-v3 directly.

**4. Add CLAUDE.md to your project:**
```markdown
# Project: YourProject

## Before Anything Else
Read STATE.md. Then read this file.

## Testing
pytest tests/ -v   # or your test command

## Slash Commands
| Command | What |
|---------|------|
| `/test` | Run tests |
| `/done` | Verify before complete |
| `/commit` | Stage and commit |
```

**5. Set mode globally (affects all Claude sessions):**
```bash
/inject strict   # Most projects
```

### Dynamic Invariants Loading

The strict mode hook **automatically reads your project's `.council/invariants.yaml`** when it exists. No extra config needed.

- If `.council/invariants.yaml` exists → uses your project's paths
- If missing → falls back to sensible defaults (`.env`, `credentials/*`, etc.)

This means each project can have different forbidden/protected paths, and strict mode adapts automatically.

### Which Mode When

| Situation | Mode | Why |
|-----------|------|-----|
| Bug fix in production code | `strict` | Need verification, DONE_REPORT |
| New feature for shipping | `strict` | Same - real work needs audit trail |
| Quick experiment / POC | `sandbox` | Fast iteration, fixtures over real APIs |
| Designing before building | `plan` | Get approval before writing code |
| Reviewing someone's PR | `review` | Context-blind adversarial review |
| Documentation only | `off` or `sandbox` | Low risk, no strict overhead |

**Default recommendation:** Start in `strict`. Switch to `sandbox` only for throwaway experiments.

### Best Practices

**DO:**
- Set up `.council/invariants.yaml` even for small projects (takes 2 min)
- Add your actual secrets paths to forbidden (grep for `.env`, `credentials`, `secret`)
- Add schema/migration files to protected (not forbidden - sometimes you need them)
- Run `/inject status` to confirm your mode before starting work
- End tasks with DONE_REPORT in strict mode (audit will catch if you forget)

**DON'T:**
- Put everything in forbidden - use protected for "ask first" files
- Switch modes mid-task - finish current work first
- Skip invariants.yaml "because it's a small project" - that's when mistakes happen
- Ignore audit failures - if it says DISCREPANCY, investigate

### Minimal Setup (2 minutes)

For projects where you just want basic protection:

```bash
# In your project root
mkdir -p .council
cat > .council/invariants.yaml << 'EOF'
forbidden_paths:
  - "*.env"
  - ".env.*"
  - "**/secrets.*"
  - "**/credentials.*"
EOF
```

That's it. Strict mode will now block changes to any env/secrets files in this project.

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

### Input Sources

| Source | Setup | Use Case |
|--------|-------|----------|
| Socket | `socket_path` in config (default: `~/.council/council.sock`) | Voice via Wispr Flow |
| Telegram | Bot token + allowed_user_ids in config | Phone commands |
| Pushover | user_key + api_token in config | Receive notifications |
| Direct tmux | Manual `tmux send-keys` | Emergency intervention |

**Voice setup (Wispr Flow / macOS Shortcuts):**
```bash
# Option 1: Use helper script
~/path/to/council-v3/scripts/send_command.sh "1: build the feature"

# Option 2: Direct socket command
echo "1: build the feature" | nc -U ~/.council/council.sock
```

**Telegram setup:**
```yaml
# In ~/.council/config.yaml
telegram:
  bot_token: "123456:ABC..."
  allowed_user_ids: [your_telegram_id]
```

### Notifications

Dispatcher sends notifications when agents complete:
- Mac: via `terminal-notifier`
- Phone: via Pushover API

30-second cooldown per agent to prevent spam.

```yaml
# In ~/.council/config.yaml
pushover:
  user_key: "xxx"
  api_token: "xxx"
```

### Execution Flow

```
Voice/Telegram → FIFO → Dispatcher parses "1: build feature"
    ↓
Dispatcher checks: Agent 1 ready? Circuit closed? Queue empty?
    ↓
Routes to tmux pane %0 → sends text + Enter
    ↓
Agent executes → completes → pane shows prompt
    ↓
Dispatcher detects ready → sends notification
    ↓
If auto-continue ON and queue empty → sends "continue"
```

---

## Slash Commands

| Command | What It Does |
|---------|--------------|
| `/test` | Run tests (auto-detects pytest/jest/etc) |
| `/test-cycle` | Generate + run tests progressively |
| `/commit` | Stage and commit changes |
| `/ship` | Test → commit → push → PR |
| `/done` | Verify work before marking complete |
| `/review` | Code review (spawns review subagent) |
| `/inject <mode>` | Change injection mode (strict/sandbox/plan/review) |
| `/save` | Update STATE.md + LOG.md |
| `/summarize` | AI-generated summary of changes |
| `/setup` | Setup new project |

---

## Plugins

### Ralph Loop (Official Plugin)

Iterative agent loops - Claude keeps working until task complete.

```bash
/ralph-loop "Build REST API. Tests must pass. Output <promise>DONE</promise>" --max-iterations 20 --completion-promise "DONE"

/cancel-ralph         # Stop the loop
```

**How it works:**
1. You run `/ralph-loop` once with a prompt
2. Claude works on task
3. Stop hook intercepts exit, re-feeds same prompt
4. Claude sees previous work in files, continues improving
5. Loop until completion promise found or max iterations

**Best for:** Well-defined tasks with clear success criteria (tests, linters).

**Not for:** Tasks needing human judgment or unclear goals.

### Ralph Queue (Council Plugin)

Queue multiple Ralph tasks for sequential execution:

```bash
/ralph-queue "task 1" | "task 2" | "task 3" --max-iterations 20
/ralph-queue-start     # Begin executing
/ralph-queue-status    # Check progress
/ralph-queue-clear     # Clear queue
```

Each task runs as full Ralph loop. When one completes, next auto-starts.

**Files:**
- `.claude/ralph-queue.local.json` - Queue state
- `.claude/ralph-loop.local.md` - Current task

### Standup (Council Plugin)

Generate daily standup from all agents:

```bash
/standup
```

Aggregates:
- Git activity (last 24h) from each agent's worktree
- STATE.md contents
- Blockers

Output grouped by agent.

---

## LLM Council (Multi-Model Planning)

Generate plans using multiple LLMs in parallel, then synthesize:

```bash
# Generate project plan
council plan "build a REST API for todos"

# Include context files
council plan "add auth to my app" --context README.md,src/app.py

# Get multi-model debate on decisions
council debate "should we use PostgreSQL or MongoDB?"

# Refine an existing plan
council refine "add more detail to the testing section"

# Bootstrap project files from plan
council bootstrap PLAN.md

# Query dispatcher logs
council logs --agent 1 --since "2h"
```

**How it works:**
1. **Draft phase** (parallel): 2 models generate independent plans
2. **Critique phase** (parallel): 2 models critique all drafts
3. **Synthesis**: Chair model combines into final PLAN.md

**Default models** (via OpenRouter):
- `anthropic/claude-opus-4.5` (drafting & chair)
- `openai/gpt-5.2` (drafting & critique)

**Output files:**
- `PLAN.md` - Generated plan
- `STATE.md`, `LOG.md`, `CLAUDE.md` - via `council bootstrap`

---

## Subagents

Agent definitions in `.claude/agents/` for specialized tasks:

| Agent | Purpose |
|-------|---------|
| `code-architect` | Design reviews, architecture decisions |
| `verify-app` | Test implementation, edge cases |
| `code-simplifier` | Reduce complexity, remove duplication |
| `build-validator` | Deployment readiness checks |
| `oncall-guide` | Debug production issues |

**How to use:**
```bash
claude --agent code-architect
# or
> "use code-architect to review this design"
```

These are prompt templates, not separate processes.

---

## Start/Stop Scripts

Quick setup for 4-agent tmux layout:

```bash
# Start council session with 4 panes
./scripts/start-council.sh

# Creates:
#   %0 → codeflow-viz
#   %1 → council-v3
#   %2 → deep-research-v0
#   %3 → voice-agent-eval

# Stop all agents
./scripts/stop-council.sh
```

After starting:
1. Attach: `tmux attach -t council`
2. Update config pane IDs if needed
3. Start dispatcher: `python -m council.dispatcher.simple`

---

## Recommended Workflow

For non-trivial tasks:

```
1. Plan      → /inject plan, design approach
2. Implement → /inject strict, write code
3. Test      → /test or /test-cycle
4. Verify    → /done (checks requirements)
5. Review    → /review (fresh eyes)
6. Ship      → /ship (test → commit → push → PR)
```

**Shortcuts:**
- Bug fix: implement → /test → /done → /commit
- Docs: edit → /commit

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

---

## Module Inventory

**LLM Council (Multi-Model Planning):**
| File | Lines | Purpose |
|------|-------|---------|
| `council/council.py` | ~346 | Multi-model draft, critique, synthesis |
| `council/client.py` | ~139 | OpenRouter API client with retry |
| `council/cli.py` | ~251 | CLI commands (plan, debate, refine, bootstrap) |
| `council/bootstrap.py` | ~314 | Generate project files from plan |

**Dispatcher (Multi-Agent Routing):**
| File | Lines | Purpose |
|------|-------|---------|
| `council/dispatcher/simple.py` | ~955 | Main dispatcher - routing, queue, circuit breaker |
| `council/dispatcher/telegram.py` | ~229 | Telegram bot for voice/text commands |
| `council/dispatcher/gitwatch.py` | ~120 | Git progress detection |

**Enforcement:**
| File | Lines | Purpose |
|------|-------|---------|
| `scripts/check_invariants.py` | ~260 | Path violation checker |
| `scripts/audit_done.py` | ~260 | Transcript auditor |

---

## tmux Invariants

Rules the dispatcher follows for tmux:

- **Always use stable pane IDs** (`%N`) not indexes - indexes shift when panes close
- **Always use `send-keys -l`** for literal text - prevents escape sequence issues
- **Always send Enter as separate call** - ensures reliable execution
- **Never send to panes in copy mode** - commands get lost

---

## First-Time Setup

```bash
# 1. Create directories
mkdir -p ~/.council/hooks

# 2. Create FIFO for voice input
mkfifo ~/.council/in.fifo

# 3. Copy hook scripts from council-v3
cp ~/Downloads/council-v3/examples/hooks/* ~/.council/hooks/ 2>/dev/null || \
  echo "Copy hooks manually from council-v3 repo"
chmod +x ~/.council/hooks/*.sh

# 4. Set initial mode
echo "strict" > ~/.council/current_inject.txt

# 5. Register hooks in Claude settings (~/.claude/settings.json):
# Add to "hooks" section:
#   "UserPromptSubmit": [{
#     "matcher": ".*",
#     "hooks": [{"type": "command", "command": "~/.council/hooks/inject.sh"}]
#   }]

# 6. Install plugins
# Ralph Loop: Enable "ralph-loop@claude-plugins-official" in settings.json
# Ralph Queue: Already in council-v3/plugins/

# 7. Create config
cp ~/Downloads/council-v3/config.example.yaml ~/.council/config.yaml
# Edit with your agent pane IDs, Pushover/Telegram credentials

# 8. Start council (creates tmux session with 4 panes)
./scripts/start-council.sh
tmux attach -t council

# 9. Start dispatcher (in separate terminal)
python -m council.dispatcher.simple
```

---

## File Structure

```
~/.council/
├── hooks/
│   ├── inject.sh           # Router (runs on every prompt)
│   ├── auto-inject.sh      # Global rules
│   ├── strict.sh           # Production mode
│   ├── sandbox.sh          # POC mode
│   ├── plan.sh             # Planning mode
│   └── review.sh           # Review mode
├── current_inject.txt      # Current mode (strict/sandbox/plan/review/off)
├── config.yaml             # Agent config, API keys
├── state.json              # Queue/circuit state
└── in.fifo                 # Voice input pipe

~/.claude/
├── settings.json           # Hooks, plugins registration
├── commands/               # Slash commands (/test, /commit, etc.)
├── plugins/                # Plugin cache
└── projects/               # Session transcripts (JSONL)

~/Downloads/council-v3/
├── council/dispatcher/     # Dispatcher code
├── plugins/                # Council plugins (ralph-queue, standup)
├── scripts/
│   ├── start-council.sh    # Start 4-agent tmux layout
│   ├── stop-council.sh     # Stop all agents
│   ├── check_invariants.py # Path violation checker
│   └── audit_done.py       # Transcript auditor
├── .council/
│   └── invariants.yaml     # Project path protection
└── docs/                   # Documentation
```

---

## Context Files

| File | Purpose |
|------|---------|
| `STATE.md` | Current work, decisions (update via /save) |
| `LOG.md` | History (append-only) |
| `CLAUDE.md` | Project-specific instructions |
| `.council/invariants.yaml` | Protected/forbidden paths |
| `.claude/ralph-queue.local.json` | Queue state (gitignored) |
