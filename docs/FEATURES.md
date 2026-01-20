# Council v3 Features

Complete feature list with what it does, how to use it, and when.

---

## Core System

| Feature | What It Does | How to Use | When |
|---------|--------------|------------|------|
| **Dispatcher** | Routes commands from socket/Telegram/Pushover to Claude Code agents in tmux panes | `python -m council.dispatcher.simple` | Running multi-agent workflows |
| **Circuit Breaker** | Stops auto-continue after 3 iterations without git progress | Automatic; `reset N` to reset | Prevents infinite loops |
| **Task Queue** | Queue tasks for agents, dequeues when agent ready | `queue 1 "task"`, `queue 1` to view | Batching work for agents |
| **Auto-Continue** | Automatically sends "continue" when agent stops | `auto 1` to enable, `stop 1` to disable | Unattended overnight runs |

---

## Mode Injection

Inject context into every prompt to control Claude's behavior.

| Mode | What It Does | How to Use | When |
|------|--------------|------------|------|
| `strict` | DONE_REPORT required, don't touch scope, verify before done | `/inject strict` | Production code |
| `production` | Strict + "Right > Fast" mindset + forbidden/protected paths | `/inject production` | Real users depend on this |
| `plan` | Design before building, output structured plan, wait for approval | `/inject plan` | Complex features, architecture |
| `review` | Adversarial context-blind critique, requires evidence | `/inject review` | Code review, pre-merge |
| `critical` | High stakes, be thorough, resist rushing | `/inject critical` | Critical systems |
| `sandbox` | Fast POC iteration, fixtures OK, skip edge cases | `/inject sandbox` | Prototyping, experiments |
| `scrappy` | Rapid validation, brute force OK | `/inject scrappy` | Quick validation |
| `off` | Disable mode injection (global rules still apply) | `/inject off` | When modes get in the way |

**Set locally:** `echo "sandbox" > .council/mode`
**Set globally:** `/inject strict` or `echo "strict" > ~/.council/current_inject.txt`

---

## Quality Hooks

Hard enforcement via Claude Code hooks.

| Hook | Type | What It Does | How to Use | When |
|------|------|--------------|------------|------|
| **TDD Guard** | PreToolUse | Blocks Write/Edit on implementation files unless failing tests exist | Install via `quality-pack/install.sh` | Always (enforces TDD) |
| **File Checker** | PostToolUse | Auto-formats with ruff/black, runs lint/type checks | Install via `quality-pack/install.sh` | Python projects |

**Override TDD Guard:** Retry within 60 seconds after warning.

---

## Slash Commands

| Command | What It Does | When |
|---------|--------------|------|
| `/test` | Auto-detect and run tests (pytest, npm test, etc.) | After code changes |
| `/test-cycle` | Generate tests + run progressively | Building test coverage |
| `/done` | Verify work before marking complete | Before claiming done |
| `/commit` | Stage and commit with good message | After verified changes |
| `/ship` | test → commit → push → PR | Ready to merge |
| `/review` | Spawn subagent for code review | Before shipping |
| `/inject <mode>` | Change mode | Switching contexts |
| `/config-status` | Show all settings dashboard, explain topics, recommendations | Understanding current state |
| `/save` | Update STATE.md + LOG.md | Preserving context |
| `/summarize` | AI-generated summary of changes | Understanding what changed |
| `/setup` | Create CLAUDE.md, STATE.md, .claude/ structure | New projects |
| `/enforce` | Create invariants.yaml, pre-commit hook | New projects |
| `/framework <name>` | Set build framework (mvp, prove-first, etc.) | Starting a build |

### Project-Specific Commands

| Command | What It Does | When |
|---------|--------------|------|
| `/review-changes` | Review uncommitted changes | Before committing |
| `/test-and-fix` | Run tests, fix failures | Iterating on fixes |
| `/first-principles` | Deconstruct problem to fundamentals | When stuck or overcomplicated |
| `/standup` | Generate standup report | Daily updates |

---

## Agents (Subagents)

Invoke with `/review` or via Task tool.

| Agent | What It Does | When |
|-------|--------------|------|
| `strict` | Enforces strict mode behaviors | Production work |
| `code-architect` | Design reviews, architecture decisions | Planning |
| `verify-app` | Test implementation, edge cases | Verification |
| `code-simplifier` | Reduce complexity | Refactoring |
| `build-validator` | Deployment readiness checks | Pre-deploy |
| `oncall-guide` | Debug production issues | Incidents |

---

## Plugins

| Plugin | Commands | What It Does | When |
|--------|----------|--------------|------|
| **ralph-loop** | `/ralph-loop "prompt"`, `/cancel-ralph` | Continuous task execution with loop guard | Long-running tasks |
| **ralph-queue** | `/ralph-queue "t1" \| "t2"`, `-start`, `-status`, `-clear` | Queue multiple tasks for sequential execution | Batching work |
| **standup** | `/standup` | Generate daily standup from agent activity | Daily updates |

---

## LLM Council

Multi-model planning and debate.

| Command | What It Does | When |
|---------|--------------|------|
| `council plan "idea"` | Multi-model plan generation | Starting complex features |
| `council plan "idea" --context file.py` | Plan with context | Feature in existing code |
| `council debate "question?"` | Get opinions from multiple models | Architecture decisions |
| `council refine "more detail on X"` | Refine existing plan | Iterating on plans |
| `council bootstrap PLAN.md` | Generate files from plan | Executing a plan |

---

## Enforcement

| Feature | What It Does | How to Use | When |
|---------|--------------|------------|------|
| **Invariants** | Forbidden/protected paths | `.council/invariants.yaml` | Protecting critical files |
| **Pre-commit Hook** | Blocks commits touching forbidden paths | `/enforce` to install | All projects |
| **DONE_REPORT Audit** | Verifies completion claims against transcript | `python scripts/audit_done.py --transcript ...` | Catching lies |
| **Invariants Check** | Manual check for path violations | `python scripts/check_invariants.py --diff HEAD~1` | Pre-merge |

---

## Build Frameworks

| Framework | What It Does | Time vs MVP | When |
|-----------|--------------|-------------|------|
| `mvp` | Validate idea fast, cut corners OK | 1x | First version |
| `prove-first` | Prove in sandbox before integrating | 2x | Adding features |
| `showcase` | Polish for demos | 2-3x | Pitches, demos |
| `production` | Real users, full quality | 3-5x | Production release |

**Set:** `/framework mvp`
**Check:** `/framework status`
**Clear:** `/framework clear`

---

## Notifications

| Channel | What It Does | Config |
|---------|--------------|--------|
| **Mac** | terminal-notifier popup | Automatic |
| **Pushover** | Phone push notification | `pushover:` in config.yaml |
| **Telegram** | Telegram bot message | `telegram:` in config.yaml |

Notifications fire when agent completes task or circuit breaker opens.

---

## Input Sources

| Source | What It Does | Config |
|--------|--------------|--------|
| **Socket** | Voice commands via Unix socket | `~/.council/council.sock` |
| **Telegram** | Phone commands via bot | `telegram.bot_token` |
| **Pushover** | Phone commands via Pushover | `pushover.user_key` |

---

## Key Files

| File | Purpose |
|------|---------|
| `~/.council/config.yaml` | Agent config (panes, worktrees, notifications) |
| `~/.council/state.json` | Runtime state (queues, circuit breakers) |
| `~/.council/hooks/*.sh` | Mode injection scripts |
| `~/.council/hooks/python/*.py` | Quality hooks (TDD Guard, File Checker) |
| `.council/invariants.yaml` | Project path protection |
| `.council/mode` | Project-local mode override |
| `CLAUDE.md` | Project instructions |
| `STATE.md` | Current work state |

---

## Quick Reference

```bash
# Start dispatcher
python -m council.dispatcher.simple

# Send command to agent 1
echo "1: do something" | nc -U ~/.council/council.sock

# Check status
echo "status" | nc -U ~/.council/council.sock

# Install quality hooks
cd quality-pack && ./install.sh --project

# Switch mode
/inject strict

# Run tests
/test

# Ship it
/ship
```
